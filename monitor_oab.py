import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config import (
    OAB_LOGIN_URL,
    OAB_NUMERO,
    OAB_UF,
    OAB_CPF,
    OAB_IDENTIDADE,
    JUSBRASIL_ENABLED,
    JUSBRASIL_LOGIN_URL,
    JUSBRASIL_PROCESSOS_URL,
    JUSBRASIL_EMAIL,
    JUSBRASIL_PASSWORD,
)
from db import init_db, log_monitor, upsert_publication
from process_ai import analyze_text

OAB_HISTORICO_URL = "https://recortedigital.oabmg.org.br/historico/historicodata.aspx"
DEBUG_SCREENSHOT_DIR = "/tmp"


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def sha_key(*parts) -> str:
    raw = "|".join(normalize(str(p)) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def extract_processo(text: str) -> str:
    patterns = [
        r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b",
        r"\b\d{20}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            return match.group(0)
    return ""


def extract_datestr(text: str) -> str:
    patterns = [
        r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            return match.group(0)
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def parse_date_br(value: str) -> Optional[datetime]:
    value = normalize(value)
    if not value:
        return None

    formats = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


def to_iso_br(value: str) -> str:
    dt = parse_date_br(value)
    if dt:
        return dt.isoformat(timespec="seconds")
    return datetime.now().isoformat(timespec="seconds")


def extrair_partes(texto: str):
    texto_norm = normalize(texto)

    patterns_autor = [
        r"(?:autor|autora|requerente|impetrante|exequente)\s*:\s*([^.;\n]+)",
    ]
    patterns_reu = [
        r"(?:réu|reu|ré|re|requerido|requerida|impetrado|executado)\s*:\s*([^.;\n]+)",
    ]

    parte_autora = ""
    parte_re = ""

    for pat in patterns_autor:
        match = re.search(pat, texto_norm, flags=re.IGNORECASE)
        if match:
            parte_autora = normalize(match.group(1))
            break

    for pat in patterns_reu:
        match = re.search(pat, texto_norm, flags=re.IGNORECASE)
        if match:
            parte_re = normalize(match.group(1))
            break

    return parte_autora, parte_re


def identificar_tribunal(processo: str, texto: str) -> str:
    texto_all = f"{processo} {texto}".lower()

    if ".8.13." in texto_all:
        return "TJMG"
    if "tribunal de justiça de minas gerais" in texto_all:
        return "TJMG"
    if "superior tribunal de justiça" in texto_all or " stj " in f" {texto_all} ":
        return "STJ"
    if "supremo tribunal federal" in texto_all or " stf " in f" {texto_all} ":
        return "STF"
    if "tribunal regional federal" in texto_all or " trf " in f" {texto_all} ":
        return "TRF"
    if "justiça do trabalho" in texto_all or " trt " in f" {texto_all} ":
        return "TRT"

    return "OAB"


def is_date_line(line: str) -> bool:
    return bool(re.fullmatch(r"\d{2}/\d{2}/\d{4}( \d{2}:\d{2}(:\d{2})?)?", line.strip()))


def is_ignorable_line(line: str) -> bool:
    value = normalize(line).lower()
    if not value:
        return True

    exacts = {
        "oab",
        "jusbrasil",
        "none",
        "geral",
        "pendente",
        "relevante",
        "histórico",
        "histórico de publicações",
    }
    if value in exacts:
        return True

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
        "termos de uso",
        "dúvidas comuns",
        "whatsapp",
        "todos os direitos reservados",
        "atendimento & suporte",
        "limpar filtro",
        "oabmg@recortedigitaladv.br",
        "pesquisar",
        "filtro",
        "filtrar",
        "consulta",
        "menu",
        "sair",
    ]

    return any(term in value for term in boilerplates)


def clean_lines(text: str) -> List[str]:
    lines = []
    prev = ""

    for raw in (text or "").splitlines():
        line = normalize(raw)
        if not line:
            continue
        if line == prev:
            continue
        prev = line
        lines.append(line)

    return lines


def finalize_item(source: str, processo: str, data_publicacao: str, text_lines: List[str]):
    texto = normalize(" ".join(text_lines))
    if not processo:
        return None
    if len(texto) < 15:
        return None
    if is_ignorable_line(texto):
        return None

    parte_autora, parte_re = extrair_partes(texto)
    tribunal = identificar_tribunal(processo, texto)
    hash_unico = sha_key(source, processo, data_publicacao, texto[:2000])

    return {
        "fonte": source,
        "processo": processo,
        "data_publicacao": data_publicacao or datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "texto": texto[:12000],
        "hash_unico": hash_unico,
        "parte_autora": parte_autora,
        "parte_re": parte_re,
        "tribunal": tribunal,
    }


def parse_cards_from_text(body_text: str, source: str) -> List[Dict]:
    lines = clean_lines(body_text)
    items = []

    current_processo = ""
    current_date = ""
    current_text_lines: List[str] = []
    pending_date = ""

    for line in lines:
        if is_ignorable_line(line):
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

            remainder = normalize(line.replace(processo_found, "", 1))
            if remainder and not is_ignorable_line(remainder):
                current_text_lines.append(remainder)
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


async def save_debug_screenshot(page, label: str):
    try:
        path = f"{DEBUG_SCREENSHOT_DIR}/oab_debug_{label}.png"
        await page.screenshot(path=path, full_page=True)
        print(f"Screenshot salva em: {path}")
    except Exception as e:
        print(f"Falha ao salvar screenshot ({label}): {e}")


async def open_oab_with_retry(page):
    errors = []

    for attempt in range(1, 3):
        try:
            print(f"Abrindo OAB, tentativa #{attempt}...")
            try:
                await page.goto(OAB_LOGIN_URL, wait_until="commit", timeout=90000)
            except Exception:
                await page.goto(OAB_LOGIN_URL, wait_until="domcontentloaded", timeout=90000)

            await page.wait_for_timeout(5000)
            await save_debug_screenshot(page, f"open_{attempt}")
            return
        except Exception as e:
            errors.append(str(e))
            await page.wait_for_timeout(3000)

    raise RuntimeError("Não foi possível abrir a OAB. " + " | ".join(errors))


async def fill_oab_login(page):
    print("Preenchendo login OAB...")

    numero_limpo = re.sub(r"\D", "", OAB_NUMERO or "")
    cpf_limpo = re.sub(r"\D", "", OAB_CPF or "")
    identidade_limpa = re.sub(r"\D", "", OAB_IDENTIDADE or "")

    selectors_numero = ["#txbOAB", "input[name='txbOAB']", "input[id*='OAB']"]
    selectors_cpf = ["#txbCPF", "input[name='txbCPF']", "input[id*='CPF']"]
    selectors_ci = ["#txbCI", "input[name='txbCI']", "input[id*='CI']"]
    selectors_submit = [
        "#btnEntrar",
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Entrar')",
        "input[value='Entrar']",
    ]

    filled = False
    for sel in selectors_numero:
        try:
            if await page.locator(sel).count():
                await page.locator(sel).first.fill(numero_limpo or OAB_NUMERO)
                filled = True
                break
        except Exception:
            pass

    if not filled:
        inputs = page.locator("input")
        if await inputs.count() >= 1:
            await inputs.nth(0).fill(numero_limpo or OAB_NUMERO)

    try:
        selects = page.locator("select")
        if await selects.count():
            try:
                await selects.nth(0).select_option(label=OAB_UF)
            except Exception:
                await selects.nth(0).select_option(value=OAB_UF)
    except Exception:
        pass

    filled = False
    for sel in selectors_cpf:
        try:
            if await page.locator(sel).count():
                await page.locator(sel).first.fill(cpf_limpo)
                filled = True
                break
        except Exception:
            pass

    if not filled:
        inputs = page.locator("input")
        if await inputs.count() >= 2:
            await inputs.nth(1).fill(cpf_limpo)

    filled = False
    for sel in selectors_ci:
        try:
            if await page.locator(sel).count():
                await page.locator(sel).first.fill(identidade_limpa)
                filled = True
                break
        except Exception:
            pass

    if not filled:
        inputs = page.locator("input")
        if await inputs.count() >= 3:
            await inputs.nth(2).fill(identidade_limpa)

    clicked = False
    for sel in selectors_submit:
        try:
            if await page.locator(sel).count():
                await page.locator(sel).first.click()
                clicked = True
                break
        except Exception:
            pass

    if not clicked:
        raise RuntimeError("Não encontrei o botão Entrar da OAB.")


async def wait_for_oab_result(page):
    await page.wait_for_timeout(5000)

    for _ in range(10):
        current_url = page.url.lower()
        if "historico" in current_url or "historicodata" in current_url:
            print("OAB redirecionou para histórico.")
            return
        await page.wait_for_timeout(1500)

    print("Indo diretamente ao histórico OAB...")
    await page.goto(OAB_HISTORICO_URL, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(6000)


async def try_fill_date_filters(page, days_back: int = 60):
    start = (datetime.now() - timedelta(days=days_back)).strftime("%d/%m/%Y")
    end = datetime.now().strftime("%d/%m/%Y")

    possible_start = [
        "input[name*='DataInicial']",
        "input[name*='DtInicial']",
        "input[name*='dtInicial']",
        "input[id*='DataInicial']",
        "input[id*='DtInicial']",
        "input[id*='dtInicial']",
        "input[name*='txtDataIni']",
        "input[id*='txtDataIni']",
    ]

    possible_end = [
        "input[name*='DataFinal']",
        "input[name*='DtFinal']",
        "input[name*='dtFinal']",
        "input[id*='DataFinal']",
        "input[id*='DtFinal']",
        "input[id*='dtFinal']",
        "input[name*='txtDataFim']",
        "input[id*='txtDataFim']",
    ]

    possible_submit = [
        "button:has-text('Pesquisar')",
        "button:has-text('Filtrar')",
        "input[value='Pesquisar']",
        "input[value='Filtrar']",
        "button[type='submit']",
        "input[type='submit']",
    ]

    start_filled = False
    end_filled = False

    for sel in possible_start:
        try:
            if await page.locator(sel).count():
                await page.locator(sel).first.fill(start)
                start_filled = True
                break
        except Exception:
            pass

    for sel in possible_end:
        try:
            if await page.locator(sel).count():
                await page.locator(sel).first.fill(end)
                end_filled = True
                break
        except Exception:
            pass

    if start_filled or end_filled:
        for sel in possible_submit:
            try:
                if await page.locator(sel).count():
                    await page.locator(sel).first.click()
                    await page.wait_for_timeout(5000)
                    return
            except Exception:
                pass


async def scrape_oab(days_back: int = 60) -> List[Dict]:
    if not OAB_NUMERO or not OAB_CPF or not OAB_IDENTIDADE:
        raise RuntimeError("Variáveis OAB_NUMERO, OAB_CPF e OAB_IDENTIDADE não configuradas.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1400, "height": 1000},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )

        page = await context.new_page()

        try:
            await open_oab_with_retry(page)
            await fill_oab_login(page)
            await save_debug_screenshot(page, "after_login")
            await wait_for_oab_result(page)
            await try_fill_date_filters(page, days_back=days_back)
            await save_debug_screenshot(page, "historico")

            body_text = await page.locator("body").inner_text()
            items = parse_cards_from_text(body_text, "OAB Recorte Digital")

            if not items:
                print("OAB sem itens parseados. Trecho inicial:")
                print(body_text[:2000])

            cutoff = datetime.now() - timedelta(days=days_back)
            filtered = []
            for item in items:
                dt = parse_date_br(item.get("data_publicacao", ""))
                if dt and dt >= cutoff:
                    filtered.append(item)
                elif not dt:
                    filtered.append(item)

            return filtered

        finally:
            await context.close()
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


async def scrape_jusbrasil(days_back: int = 60) -> List[Dict]:
    if not JUSBRASIL_ENABLED:
        return []

    if not JUSBRASIL_EMAIL or not JUSBRASIL_PASSWORD:
        raise RuntimeError("Variáveis JUSBRASIL_EMAIL e JUSBRASIL_PASSWORD não configuradas.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1400, "height": 1000},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
        page = await context.new_page()

        try:
            print("Abrindo login do JusBrasil...")
            await page.goto(JUSBRASIL_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(2500)

            print("Preenchendo login JusBrasil...")
            await fill_jus_login(page)

            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except PlaywrightTimeoutError:
                pass

            await page.wait_for_timeout(4000)

            print("Abrindo área de processos do JusBrasil...")
            await page.goto(JUSBRASIL_PROCESSOS_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)

            body_text = await page.locator("body").inner_text()
            items = parse_cards_from_text(body_text, "JusBrasil")

            cutoff = datetime.now() - timedelta(days=days_back)
            filtered = []
            for item in items:
                dt = parse_date_br(item.get("data_publicacao", ""))
                if dt and dt >= cutoff:
                    filtered.append(item)
                elif not dt:
                    filtered.append(item)

            return filtered

        finally:
            await context.close()
            await browser.close()


def legacy_payload_from_item(item: Dict, analysis: Dict) -> Dict:
    return {
        "processo": item.get("processo", ""),
        "data_publicacao": item.get("data_publicacao", ""),
        "texto": item.get("texto", ""),
        "relevante": bool(analysis.get("is_relevant", 0)),
        "motivo_filtro": analysis.get("risk_level", ""),
        "parte_autora": item.get("parte_autora", ""),
        "parte_re": item.get("parte_re", ""),
        "tribunal": item.get("tribunal", ""),
        "resumo_ia": analysis.get("ai_summary", ""),
        "o_que_fazer": analysis.get("ai_action", ""),
        "prazo": analysis.get("deadline_date", "") or "",
        "urgencia": analysis.get("risk_level", "") or "",
        "enviado_email": 0,
        "hash_unico": item.get("hash_unico", ""),
        "fonte_legacy": item.get("fonte", ""),
    }


def to_publication_record(item: Dict) -> Dict:
    analysis = analyze_text(
        text=item.get("texto", ""),
        title=f"{item.get('fonte', '')} - {item.get('processo', '')}",
        source=item.get("fonte", "oab"),
    )

    legacy_payload = legacy_payload_from_item(item, analysis)
    external_id = item.get("hash_unico") or sha_key(
        item.get("fonte", ""),
        item.get("processo", ""),
        item.get("data_publicacao", ""),
        item.get("texto", "")[:2000],
    )

    return {
        "source": item.get("fonte", "OAB"),
        "external_id": external_id,
        "process_number": item.get("processo", ""),
        "title": f"{item.get('fonte', '')} - {item.get('processo', '')}".strip(" -"),
        "content": item.get("texto", ""),
        "url": OAB_HISTORICO_URL if "OAB" in item.get("fonte", "") else JUSBRASIL_PROCESSOS_URL,
        "publication_date": to_iso_br(item.get("data_publicacao", "")),
        "deadline_date": analysis.get("deadline_date"),
        "risk_level": analysis.get("risk_level"),
        "ai_summary": analysis.get("ai_summary"),
        "ai_action": analysis.get("ai_action"),
        "ai_tags": analysis.get("ai_tags"),
        "is_relevant": analysis.get("is_relevant", 1),
        "alert_sent": 0,
        "raw_json": json.dumps(
            {
                "legacy": legacy_payload,
                "item_original": item,
                "analysis": analysis,
            },
            ensure_ascii=False,
        ),
    }


def persist_items(items: List[Dict]) -> int:
    inserted = 0

    for item in items:
        try:
            record = to_publication_record(item)
            upsert_publication(record)
            inserted += 1
        except Exception as e:
            log_monitor("monitor_oab", "error", f"Erro ao persistir item {item.get('processo', '')}: {e}")

    return inserted


def run_monitor(days_back: int = 60) -> Dict:
    init_db()

    all_items: List[Dict] = []
    inserted = 0

    try:
        oab_items = asyncio.run(scrape_oab(days_back=days_back))
        log_monitor("monitor_oab", "success", f"OAB retornou {len(oab_items)} item(ns).")
        all_items.extend(oab_items)
    except Exception as e:
        log_monitor("monitor_oab", "error", f"Erro ao capturar OAB: {e}")

    try:
        jb_items = asyncio.run(scrape_jusbrasil(days_back=days_back))
        if jb_items:
            log_monitor("monitor_oab", "success", f"JusBrasil retornou {len(jb_items)} item(ns).")
            all_items.extend(jb_items)
    except Exception as e:
        log_monitor("monitor_oab", "warning", f"JusBrasil indisponível: {e}")

    if all_items:
        inserted = persist_items(all_items)

    log_monitor(
        "monitor_oab",
        "success",
        f"Monitor finalizado. Capturados: {len(all_items)} | Persistidos: {inserted}",
    )

    return {
        "captured": len(all_items),
        "persisted": inserted,
    }


def executar_monitor(days_back: int = 60) -> Dict:
    return run_monitor(days_back=days_back)


if __name__ == "__main__":
    result = run_monitor(days_back=60)
    print(json.dumps(result, ensure_ascii=False, indent=2))
