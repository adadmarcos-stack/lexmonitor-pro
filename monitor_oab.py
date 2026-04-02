import asyncio
import hashlib
import re
import subprocess
import urllib.request
import json

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config import (
    OAB_LOGIN_URL, OAB_NUMERO, OAB_UF, OAB_CPF, OAB_IDENTIDADE,
    OPENAI_ENABLED, OPENAI_API_KEY, OPENAI_MODEL,
    JUSBRASIL_ENABLED, JUSBRASIL_LOGIN_URL, JUSBRASIL_PROCESSOS_URL,
    JUSBRASIL_EMAIL, JUSBRASIL_PASSWORD,
)
from db import publicacao_existe_por_hash, inserir_publicacao
from alert import process_alerts

def ensure_playwright():
    subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)

def normalize(s):
    return re.sub(r"\s+", " ", (s or "")).strip()

def sha_key(*parts):
    raw = "|".join(normalize(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def extract_processo(text):
    patterns = [
        r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b",
        r"\b\d{20}\b",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(0)
    return ""

def extract_datestr(text):
    patterns = [
        r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\b",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(0)
    from datetime import datetime
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def ai_classify(text):
    if not OPENAI_ENABLED or not OPENAI_API_KEY:
        return None
    body = {
        "model": OPENAI_MODEL,
        "input": (
            "Classifique a publicação jurídica a seguir como relevante ou não relevante. "
            "Responda APENAS em JSON com chaves: relevante (true/false) e motivo (string curta).\n\n"
            f"PUBLICAÇÃO:\n{text[:4000]}"
        ),
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read().decode("utf-8").lower()
        if "true" in data:
            return True, "IA marcou como relevante"
        if "false" in data:
            return False, "IA marcou como não relevante"
    except Exception as e:
        print(f"IA desabilitada por erro: {e}")
    return None

def rule_classify(text):
    tl = (text or "").lower()
    hits = [
        "intimação", "prazo", "manifestação", "sentença", "decisão",
        "audiência", "urgente", "cumprimento", "citação", "embargos",
        "apelação", "contestação", "liminar", "despacho", "julgamento",
        "sessão virtual", "ordem do dia",
    ]
    for h in hits:
        if h in tl:
            return True, f"Contém a palavra-chave: {h}"
    return False, ""

def classify_publicacao(text):
    ai = ai_classify(text)
    if ai is not None:
        return ai
    return rule_classify(text)

def parse_cards_from_text(body_text, source):
    body_text = normalize(body_text)
    chunks = re.split(r"\n\s*\d+\.\s*|\n{2,}", body_text)
    items = []
    for chunk in chunks:
        chunk = normalize(chunk)
        if len(chunk) < 40:
            continue
        processo = extract_processo(chunk)
        data_publicacao = extract_datestr(chunk)
        relevante, motivo = classify_publicacao(chunk)
        key = sha_key(source, processo, data_publicacao, chunk[:2000])
        items.append({
            "fonte": source,
            "processo": processo,
            "data_publicacao": data_publicacao,
            "texto": chunk[:10000],
            "relevante": relevante,
            "motivo_filtro": motivo,
            "hash_unico": key,
        })
    return items

async def fill_oab_login(page):
    inputs = page.locator("input")
    try:
        if await page.locator("#txbOAB").count():
            await page.locator("#txbOAB").fill(OAB_NUMERO)
        else:
            await inputs.nth(0).fill(OAB_NUMERO)
    except Exception:
        pass
    try:
        selects = page.locator("select")
        if await selects.count():
            try:
                await selects.nth(0).select_option(label=OAB_UF)
            except Exception:
                await selects.nth(0).select_option(value=OAB_UF)
    except Exception:
        pass
    try:
        if await page.locator("#txbCPF").count():
            await page.locator("#txbCPF").fill(re.sub(r"\D", "", OAB_CPF))
        else:
            await inputs.nth(1).fill(re.sub(r"\D", "", OAB_CPF))
    except Exception:
        pass
    try:
        if await page.locator("#txbCI").count():
            await page.locator("#txbCI").fill(re.sub(r"\D", "", OAB_IDENTIDADE))
        else:
            await inputs.nth(2).fill(re.sub(r"\D", "", OAB_IDENTIDADE))
    except Exception:
        pass
    for sel in ["#btnEntrar", "button[type='submit']", "input[type='submit']", "button:has-text('Entrar')", "input[value='Entrar']"]:
        try:
            if await page.locator(sel).count():
                await page.locator(sel).first.click()
                return
        except Exception:
            continue
    raise RuntimeError("Não encontrei o botão Entrar da OAB.")

async def scrape_oab():
    if not OAB_NUMERO or not OAB_CPF or not OAB_IDENTIDADE:
        raise RuntimeError("Variáveis OAB_NUMERO, OAB_CPF e OAB_IDENTIDADE não configuradas.")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            print("Abrindo Recorte Digital...")
            await page.goto(OAB_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2000)
            print("Preenchendo login OAB...")
            await fill_oab_login(page)
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                pass
            await page.wait_for_timeout(5000)
            try:
                if "historico" not in page.url.lower():
                    await page.goto("https://recortedigital.oabmg.org.br/historico/historicodata.aspx", wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)
            except Exception:
                pass
            body_text = await page.locator("body").inner_text()
            return parse_cards_from_text(body_text, "oab")
        finally:
            await browser.close()

async def fill_jus_login(page):
    email_selectors = ["input[type='email']", "input[name='email']", "input[placeholder*='mail']", "input[placeholder*='E-mail']"]
    password_selectors = ["input[type='password']", "input[name='password']", "input[placeholder*='senha']", "input[placeholder*='Senha']"]
    for sel in email_selectors:
        try:
            if await page.locator(sel).count():
                await page.locator(sel).first.fill(JUSBRASIL_EMAIL)
                break
        except Exception:
            continue
    else:
        raise RuntimeError("Não encontrei o campo de e-mail do JusBrasil.")
    for sel in ["button:has-text('Continuar')", "button:has-text('Próximo')", "button[type='submit']"]:
        try:
            if await page.locator(sel).count():
                await page.locator(sel).first.click()
                break
        except Exception:
            continue
    await page.wait_for_timeout(2500)
    for sel in password_selectors:
        try:
            if await page.locator(sel).count():
                await page.locator(sel).first.fill(JUSBRASIL_PASSWORD)
                break
        except Exception:
            continue
    else:
        raise RuntimeError("Não encontrei o campo de senha do JusBrasil.")
    for sel in ["button[type='submit']", "button:has-text('Entrar')", "button:has-text('Continuar')", "input[type='submit']"]:
        try:
            if await page.locator(sel).count():
                await page.locator(sel).first.click()
                return
        except Exception:
            continue
    raise RuntimeError("Não encontrei o botão de login do JusBrasil.")

async def scrape_jusbrasil():
    if not JUSBRASIL_ENABLED:
        return []
    if not JUSBRASIL_EMAIL or not JUSBRASIL_PASSWORD:
        raise RuntimeError("Variáveis JUSBRASIL_EMAIL e JUSBRASIL_PASSWORD não configuradas.")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            print("Abrindo login do JusBrasil...")
            await page.goto(JUSBRASIL_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2000)
            print("Preenchendo login JusBrasil...")
            await fill_jus_login(page)
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                pass
            await page.wait_for_timeout(5000)
            print("Abrindo área de processos do JusBrasil...")
            await page.goto(JUSBRASIL_PROCESSOS_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)
            body_text = await page.locator("body").inner_text()
            return parse_cards_from_text(body_text, "jusbrasil")
        finally:
            await browser.close()

def persist_items(items):
    inserted = 0
    for item in items:
        if publicacao_existe_por_hash(item["hash_unico"]):
            continue
        if inserir_publicacao(
            fonte=item["fonte"],
            processo=item["processo"],
            data_publicacao=item["data_publicacao"],
            texto=item["texto"],
            relevante=item["relevante"],
            motivo_filtro=item["motivo_filtro"],
            hash_unico=item["hash_unico"],
        ):
            inserted += 1
    return inserted

def executar_monitor():
    print("== Iniciando monitor profissional ==")
    ensure_playwright()
    all_items = []
    try:
        oab_items = asyncio.run(scrape_oab())
        print(f"OAB retornou {len(oab_items)} itens.")
        all_items.extend(oab_items)
    except Exception as e:
        print(f"Erro na captura OAB: {e}")
    try:
        jb_items = asyncio.run(scrape_jusbrasil())
        print(f"JusBrasil retornou {len(jb_items)} itens.")
        all_items.extend(jb_items)
    except Exception as e:
        print(f"Erro na captura JusBrasil: {e}")
    inserted = persist_items(all_items)
    print(f"Novas publicações inseridas: {inserted}")
    process_alerts()
    print("== Monitor finalizado ==")

if __name__ == "__main__":
    executar_monitor()
