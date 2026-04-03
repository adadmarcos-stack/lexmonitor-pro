import asyncio
import hashlib
import re
import subprocess
import urllib.request
import json

from datetime import datetime
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


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def sha_key(*parts) -> str:
    raw = "|".join(normalize(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def extract_processo(text: str) -> str:
    patterns = [
        r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b",  # CNJ
        r"\b\d{20}\b",  # número corrido
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(0)
    return ""


def extract_datestr(text: str) -> str:
    patterns = [
        r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\b",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(0)
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def ai_classify(text: str):
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
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
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


def rule_classify(text: str):
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


def classify_publicacao(text: str):
    ai = ai_classify(text)
    if ai is not None:
        return ai
    return rule_classify(text)


def is_date_line(line: str) -> bool:
    return bool(re.fullmatch(r"\d{2}/\d{2}/\d{4}( \d{2}:\d{2}(:\d{2})?)?", line.strip()))


def is_chip_or_meta_line(line: str) -> bool:
    value = normalize(line).lower()
    if value in {"oab", "jusbrasil", "none", "geral", "pendente", "relevante"}:
        return True
    return False


def is_boilerplate_line(line: str) -> bool:
    value = normalize(line).lower()

    boilerplates = [
        "portal de publicações",
        "pesquisa de intimações publicadas em diários oficiais",
        "seja bem vindo",
        "página principal",
        "acesso publicações",
        "extras agenda",
        "painel histórico",
        "publicações por data",
        "data de disponibilização",
        "data de publicação",
        "data de envio entre",
        "todos dj",
        "dj acre",
        "dj alagoas",
        "dj amapá",
        "dj amazonas",
        "dj bahia",
        "dj ceará",
        "dj distrito federal",
        "dj espírito santo",
        "dj goias",
        "dj maranhão",
        "dj mato grosso",
        "dj mato grosso do sul",
        "dj minas gerais",
        "dj para",
        "dj paraíba",
        "dj paraná",
        "dj pernambuco",
        "dj piauí",
        "dj rio de janeiro",
        "dj rio grande do norte",
        "dj rio grande do sul",
        "dj rondonia",
        "dj roraima",
        "dj santa catarina",
        "dj são paulo",
        "dj sergipe",
        "dj tocantins",
        "dj união",
        "tribunais superiores",
        "diário oficial da união",
        "limpar filtro",
        "atendimento & suporte",
        "termos de uso",
        "dúvidas comuns",
        "whatsapp",
        "todos os direitos reservados",
        "email: oabmg@recortedigitaladv.br",
        "email oabmg@recortedigitaladv.br",
        "telefone:",
        "painel premium com oab",
    ]

    return any(term in value for term in boilerplates)


def clean_text_lines(text: str):
    raw_lines = text.splitlines()
    lines = []
    prev = ""

    for line in raw_lines:
        line = normalize(line)
        if not line:
            continue
        if line == prev:
            continue
        prev = line
        lines.append(line)

    return lines


def finalize_item(source: str, processo: str, data_publicacao: str, text_lines):
    texto = normalize(" ".join(text_lines))

    if not processo:
        return None

    if len(texto) < 20:
        return None

    if is_boilerplate_line(texto):
        return None

    relevante, motivo = classify_publicacao(texto)
    key = sha_key(source, processo, data_publicacao, texto[:2000])

    return {
        "fonte": source,
        "processo": processo,
        "data_publicacao": data_publicacao or datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "texto": texto[:10000],
        "relevante": relevante,
        "motivo_filtro": motivo,
        "hash_unico": key,
    }


def parse_cards_from_text(body_text: str, source: str):
    lines = clean_text_lines(body_text)
    items = []

    current_processo = ""
    current_date = ""
    current_text_lines = []
    pending_date = ""

    for line in lines:
        if is_chip_or_meta_line(line):
            continue

        if is_boilerplate_line(line):
            continue

        if is_date_line(line):
            if current_processo and current_text_lines:
                current_date = line
            else:
                pending_date = line
            continue

        processo_found = extract_processo(line)

        if processo_found:
            item = finalize_item(
                source=source,
                processo=current_processo,
                data_publicacao=current_date,
                text_lines=current_text_lines,
            )
            if item:
                items.append(item)

            current_processo = processo_found
            current_date = pending_date or ""
            pending_date = ""
            current_text_lines = []
            continue

        if current_processo:
            current_text_lines.append(line)

    item = finalize_item(
        source=source,
        processo=current_processo,
        data_publicacao=current_date,
        text_lines=current_text_lines,
    )
    if item:
        items.append(item)

    unique = []
    seen = set()
    for item in items:
        if item["hash_unico"] in seen:
            continue
        seen.add(item["hash_unico"])
        unique.append(item)

    return unique


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

    for sel in [
        "#btnEntrar",
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Entrar')",
        "input[value='Entrar']",
    ]:
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
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
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
                    await page.goto(
                        "https://recortedigital.oabmg.org.br/historico/historicodata.aspx",
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    await page.wait_for_timeout(3000)
            except Exception:
                pass

            body_text = await page.locator("body").inner_text()
            items = parse_cards_from_text(body_text, "oab")
            return items

        finally:
            await browser.close()


async def fill_jus_login(page):
    email_selectors = [
        "input[type='email']",
        "input[name='email']",
        "input[placeholder*='mail']",
        "input[placeholder*='E-mail']",
    ]
    password_selectors = [
        "input[type='password']",
        "input[name='password']",
        "input[placeholder*='senha']",
        "input[placeholder*='Senha']",
    ]

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
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
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
            items = parse_cards_from_text(body_text, "jusbrasil")
            return items

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
