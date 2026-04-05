from playwright.sync_api import sync_playwright
import time
import re
import json
from pathlib import Path

URL = "https://recortedigital.oabmg.org.br/"
HISTORICO_URL = "https://recortedigital.oabmg.org.br/historico/historicodata.aspx"

# PREENCHA COM SEUS DADOS EXATOS
OAB_NUMERO = "113674"
OAB_UF = "MG"
CPF = "06819623640"      # sem pontuação
IDENTIDADE = "12989116"  # exatamente como funciona no portal

# período de busca
DATA_INICIAL = "01/02/2026"
DATA_FINAL = "29/03/2026"

OUTPUT_JSON = "oab_resultado.json"
OUTPUT_TXT = "oab_resultado.txt"
OUTPUT_HTML = "oab_resultado.html"
SCREEN_DIR = "screens_oab"


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def save_screen(page, name: str) -> None:
    ensure_dir(SCREEN_DIR)
    page.screenshot(path=str(Path(SCREEN_DIR) / name), full_page=True)


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
                print(f"[OK] Clicou em: {label}")
                time.sleep(wait_seconds)
                return True
        except Exception:
            continue

    print(f"[AVISO] Não encontrou: {label}")
    return False


def abrir_oab(page):
    print("Abrindo OAB...")
    page.goto(URL, wait_until="domcontentloaded", timeout=120000)
    time.sleep(8)
    save_screen(page, "01_login.png")


def preencher_login(page):
    print("Preenchendo login...")

    numero = only_digits(OAB_NUMERO)
    cpf = only_digits(CPF)
    identidade = IDENTIDADE.strip()

    visiveis = visible_inputs(page)
    print(f"Inputs visíveis encontrados no login: {len(visiveis)}")

    if len(visiveis) < 3:
        raise Exception("Não encontrou 3 campos visíveis no login.")

    # campo OAB
    visiveis[0].click()
    visiveis[0].fill(numero)
    time.sleep(0.5)

    # UF - só garante se precisar
    try:
        selects = page.locator("select")
        if selects.count() > 0:
            try:
                valor_atual = selects.first.input_value()
                if valor_atual != OAB_UF:
                    selects.first.select_option(label=OAB_UF)
            except Exception:
                try:
                    selects.first.select_option(label=OAB_UF)
                except Exception:
                    pass
    except Exception:
        pass

    # CPF
    visiveis[1].click()
    visiveis[1].fill(cpf)
    time.sleep(0.5)

    # Identidade
    visiveis[2].click()
    visiveis[2].fill(identidade)
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

    save_screen(page, "02_pos_login.png")

    html = page.content()
    body = page.inner_text("body")

    if "Dados incorretos" in html or "Dados incorretos" in body:
        raise Exception("Login inválido. O portal rejeitou os dados.")

    if "Seja bem vindo" in body or "Portal de PUBLICAÇÕES" in body or "Histórico - Publicações por Data" in body:
        print("[OK] Login confirmado.")
        return

    print("Trecho da tela após login:")
    print(body[:1500])
    raise Exception("Login não foi confirmado pelo portal.")


def abrir_historico(page):
    print("Indo para histórico...")
    page.goto(HISTORICO_URL, wait_until="domcontentloaded", timeout=120000)
    time.sleep(8)
    save_screen(page, "03_historico.png")

    body = page.inner_text("body")
    if "Dados incompletos. Favor preencher nome de usuário e senha." in body:
        raise Exception("Sessão não autenticada ao abrir histórico.")


def preencher_datas(page):
    print("Preenchendo datas...")

    visiveis = visible_inputs(page)
    print(f"Inputs visíveis no histórico: {len(visiveis)}")

    if len(visiveis) >= 2:
        visiveis[0].click()
        visiveis[0].fill(DATA_INICIAL)
        time.sleep(0.5)

        visiveis[1].click()
        visiveis[1].fill(DATA_FINAL)
        time.sleep(0.5)

        print("[OK] Datas preenchidas.")
    else:
        raise Exception("Campos de data não encontrados.")


def consultar(page):
    print("Clicando consultar...")
    clicou = click_if_exists(
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

    if not clicou:
        raise Exception("Botão Consultar não encontrado.")

    save_screen(page, "04_consulta.png")


def visualizar_tudo(page):
    print("Clicando visualizar tudo...")
    clicou = click_if_exists(
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

    if not clicou:
        raise Exception("Botão Visualizar tudo não encontrado.")

    save_screen(page, "05_visualizar_tudo.png")


def capturar(page):
    print("Capturando dados...")
    body = page.inner_text("body")
    html = page.content()

    Path(OUTPUT_TXT).write_text(body, encoding="utf-8")
    Path(OUTPUT_HTML).write_text(html, encoding="utf-8")

    processos = re.findall(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b", body)
    datas = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", body)

    resultado = {
        "ok": True,
        "titulo": "Portal de Publicações",
        "url_final": page.url,
        "processos_encontrados": sorted(list(set(processos))),
        "datas_encontradas": sorted(list(set(datas))),
        "preview_texto": body[:12000],
    }

    Path(OUTPUT_JSON).write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Finalizado com sucesso.")
    print(f"Processos encontrados: {len(resultado['processos_encontrados'])}")
    print(f"Arquivo TXT: {OUTPUT_TXT}")
    print(f"Arquivo JSON: {OUTPUT_JSON}")
    print(f"Arquivo HTML: {OUTPUT_HTML}")

    return resultado


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # local: melhor deixar visível
            args=["--disable-dev-shm-usage"],
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

            print("\n[OK] SUCESSO: encontrou publicações")
            print(json.dumps(resultado, ensure_ascii=False, indent=2)[:4000])

        finally:
            browser.close()


if __name__ == "__main__":
    run()
