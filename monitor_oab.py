from playwright.sync_api import sync_playwright
import time
import re
import json
import hashlib
from datetime import datetime

try:
    from config import OAB_NUMERO, OAB_CPF, OAB_IDENTIDADE, OAB_UF, OAB_LOGIN_URL
except Exception:
    OAB_NUMERO = "113674"
    OAB_CPF = "06819623640"
    OAB_IDENTIDADE = "12989116"
    OAB_UF = "MG"
    OAB_LOGIN_URL = "https://recortedigital.oabmg.org.br/"

from db import init_db, upsert_publication, log_monitor
from process_ai import analyze_text

URL = OAB_LOGIN_URL or "https://recortedigital.oabmg.org.br/"
HISTORICO_URL = "https://recortedigital.oabmg.org.br/historico/historicodata.aspx"


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def visible_inputs(page):
    inputs = page.locator("input").all()
    visiveis = []

    for inp in inputs:
        try:
            tipo = (inp.get_attribute("type") or "").lower()
            if tipo in {"hidden", "submit", "button", "checkbox", "radio"}:
                continue
            if inp.is_visible():
                visiveis.append(inp)
        except Exception:
            continue

    return visiveis


def click_if_exists(page, selectors, label, wait_seconds=4):
    for sel in selectors:
        try:
            locator = page.locator(sel)
            if locator.count() > 0:
                locator.first.click()
                print(f"Clicou em: {label}")
                time.sleep(wait_seconds)
                return True
        except Exception:
            continue

    print(f"Não encontrou: {label}")
    return False


def abrir_oab(page):
    print("🚀 Abrindo OAB...")
    page.goto(URL, wait_until="domcontentloaded", timeout=120000)
    time.sleep(8)


def preencher_login(page):
    print("🔐 Preenchendo login...")

    numero = only_digits(OAB_NUMERO)
    cpf = only_digits(OAB_CPF)
    identidade = (OAB_IDENTIDADE or "").strip()

    inputs_visiveis = visible_inputs(page)
    print(f"Inputs visíveis encontrados: {len(inputs_visiveis)}")

    if len(inputs_visiveis) < 3:
        raise Exception("Não encontrou campos suficientes para o login.")

    inputs_visiveis[0].click()
    inputs_visiveis[0].fill(numero)
    time.sleep(0.5)

    try:
        selects = page.locator("select")
        if selects.count() > 0:
            try:
                valor_atual = selects.first.input_value()
                if valor_atual != OAB_UF:
                    selects.first.select_option(label=OAB_UF)
            except Exception:
                pass
    except Exception:
        pass

    inputs_visiveis[1].click()
    inputs_visiveis[1].fill(cpf)
    time.sleep(0.5)

    inputs_visiveis[2].click()
    inputs_visiveis[2].fill(identidade)
    time.sleep(0.5)

    clicou = click_if_exists(
        page,
        [
            "#btnEntrar",
            "button:has-text('ENTRAR')",
            "button:has-text('Entrar')",
            "input[type='submit']",
            "input[value='ENTRAR']",
            "input[value='Entrar']",
        ],
        "ENTRAR",
        wait_seconds=6,
    )

    if not clicou:
        raise Exception("Botão ENTRAR não encontrado.")

    html = page.content()
    if "Dados incorretos" in html:
        raise Exception("Login inválido. O portal rejeitou OAB/CPF/identidade.")

    body = page.inner_text("body")
    if "Seja bem vindo" in body or "Portal de PUBLICAÇÕES" in body or "Histórico - Publicações por Data" in body:
        print("✅ Login confirmado")
        return

    print("⚠️ Trecho da tela após login:")
    print(body[:1500])
    raise Exception("Login não foi confirmado pelo portal.")


def abrir_historico(page):
    print("📂 Indo para histórico...")
    page.goto(HISTORICO_URL, wait_until="domcontentloaded", timeout=120000)
    time.sleep(8)

    body = page.inner_text("body")
    if "Dados incompletos. Favor preencher nome de usuário e senha." in body:
        raise Exception("Sessão não autenticada ao abrir histórico.")


def preencher_datas(page):
    print("📅 Preenchendo datas...")

    inputs_visiveis = visible_inputs(page)

    if len(inputs_visiveis) >= 2:
        try:
            inputs_visiveis[0].click()
            inputs_visiveis[0].fill("01/02/2026")
            time.sleep(0.5)

            inputs_visiveis[1].click()
            inputs_visiveis[1].fill("29/03/2026")
            time.sleep(0.5)

            print("Datas preenchidas")
        except Exception:
            print("⚠️ Não conseguiu preencher datas")
    else:
        print("⚠️ Campos de data não encontrados")


def consultar(page):
    print("🔍 Clicando consultar...")
    click_if_exists(
        page,
        [
            "button:has-text('Consultar')",
            "button:has-text('CONSULTAR')",
            "text=Consultar",
            "text=CONSULTAR",
            "input[value='Consultar']",
            "input[value='CONSULTAR']",
            "button[type='submit']",
        ],
        "CONSULTAR",
        wait_seconds=6,
    )


def visualizar_tudo(page):
    print("📄 Clicando visualizar tudo...")
    click_if_exists(
        page,
        [
            "button:has-text('Visualizar tudo')",
            "button:has-text('VISUALIZAR TUDO')",
            "text=Visualizar tudo",
            "text=VISUALIZAR TUDO",
            "input[value='Visualizar tudo']",
            "input[value='VISUALIZAR TUDO']",
        ],
        "VISUALIZAR TUDO",
        wait_seconds=8,
    )


def capturar(page):
    print("📥 Capturando conteúdo...")
    content = page.inner_text("body")

    print("\n========== RESULTADO ==========\n")
    print(content[:3000])

    return content


# ─── NOVO: parsing e persistência ────────────────────────────────────────────

def parse_publicacoes(content: str) -> list:
    """Extrai publicações individuais do texto bruto do portal OAB."""
    publicacoes = []

    # Encontra todos os números de processo no formato CNJ
    processos = list(dict.fromkeys(
        re.findall(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b", content)
    ))
    datas = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", content)
    data_padrao = datas[0] if datas else datetime.now().strftime("%d/%m/%Y")

    if processos:
        for i, processo in enumerate(processos):
            idx = content.find(processo)
            if idx == -1:
                continue
            start = max(0, idx - 300)
            # Tenta ir até o próximo processo ou até 3000 chars
            if i + 1 < len(processos):
                next_idx = content.find(processos[i + 1])
                end = next_idx if next_idx > idx else min(len(content), idx + 3000)
            else:
                end = min(len(content), idx + 3000)

            trecho = content[start:end].strip()
            data = datas[i] if i < len(datas) else data_padrao

            publicacoes.append({
                "processo": processo,
                "data": data,
                "texto": trecho,
            })
    else:
        # Nenhum número de processo encontrado — salva o conteúdo completo como uma publicação
        if len(content.strip()) > 100:
            publicacoes.append({
                "processo": "Sem número",
                "data": data_padrao,
                "texto": content[:8000],
            })

    return publicacoes


def salvar_publicacoes(publicacoes: list) -> int:
    """Salva as publicações no banco de dados."""
    init_db()
    count = 0

    for pub in publicacoes:
        try:
            analysis = analyze_text(
                text=pub["texto"],
                title=pub["processo"],
                source="recorte_digital",
            )

            hash_id = hashlib.md5(
                f"{pub['processo']}_{pub['data']}".encode()
            ).hexdigest()[:16]

            legacy_payload = {
                "processo": pub["processo"],
                "data_publicacao": pub["data"],
                "texto": pub["texto"],
                "relevante": bool(analysis.get("is_relevant", 1)),
                "motivo_filtro": analysis.get("risk_level", ""),
                "parte_autora": "",
                "parte_re": "",
                "tribunal": "OAB/MG - Recorte Digital",
                "resumo_ia": analysis.get("ai_summary", ""),
                "o_que_fazer": analysis.get("ai_action", ""),
                "prazo": analysis.get("deadline_date", "") or "",
                "urgencia": analysis.get("risk_level", ""),
                "enviado_email": 0,
                "hash_unico": hash_id,
                "fonte_legacy": "Recorte Digital OAB/MG",
            }

            data = {
                "source": "recorte_digital",
                "external_id": hash_id,
                "process_number": pub["processo"],
                "title": f"Publicação OAB - {pub['processo']}",
                "content": pub["texto"],
                "url": HISTORICO_URL,
                "publication_date": datetime.now().isoformat(),
                "deadline_date": analysis.get("deadline_date"),
                "risk_level": analysis.get("risk_level", "baixo"),
                "ai_summary": analysis.get("ai_summary", ""),
                "ai_action": analysis.get("ai_action", ""),
                "ai_tags": analysis.get("ai_tags", ""),
                "is_relevant": analysis.get("is_relevant", 1),
                "alert_sent": 0,
                "raw_json": json.dumps(
                    {"legacy": legacy_payload},
                    ensure_ascii=False,
                ),
            }

            upsert_publication(data)
            count += 1
            log_monitor("monitor_oab", "success", f"Publicação salva: {pub['processo']}")
            print(f"✅ Salvo: {pub['processo']}")

        except Exception as e:
            log_monitor("monitor_oab", "error", f"Erro ao salvar publicação: {e}")
            print(f"❌ Erro ao salvar {pub.get('processo')}: {e}")

    return count


# ─── FIM NOVO ─────────────────────────────────────────────────────────────────


def run():
    init_db()
    captured = 0
    persisted = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1100})

        try:
            abrir_oab(page)
            preencher_login(page)
            abrir_historico(page)
            preencher_datas(page)
            consultar(page)
            visualizar_tudo(page)
            resultado = capturar(page)

            if resultado:
                captured = 1
                publicacoes = parse_publicacoes(resultado)
                print(f"📋 Publicações encontradas: {len(publicacoes)}")
                persisted = salvar_publicacoes(publicacoes)
                print(f"💾 Publicações salvas no banco: {persisted}")
                log_monitor("monitor_oab", "success", f"{persisted} publicação(ões) salva(s).")
            else:
                log_monitor("monitor_oab", "warning", "Nenhum conteúdo capturado.")

        except Exception as e:
            log_monitor("monitor_oab", "error", str(e))
            print(f"❌ Erro no monitor OAB: {e}")
        finally:
            browser.close()

    print({"captured": captured, "persisted": persisted})
    return persisted


if __name__ == "__main__":
    run()
