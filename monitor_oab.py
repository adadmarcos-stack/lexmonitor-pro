from playwright.sync_api import sync_playwright
import time
import re

URL = "https://recortedigital.oabmg.org.br/"
HISTORICO_URL = "https://recortedigital.oabmg.org.br/historico/historicodata.aspx"

OAB_NUMERO = "113674"
CPF = "06819623640"
IDENTIDADE = "12989116"


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
    cpf = only_digits(CPF)
    identidade = IDENTIDADE.strip()

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
            # não força mudança se já estiver MG, mas garante caso precise
            try:
                valor_atual = selects.first.input_value()
                if valor_atual != "MG":
                    selects.first.select_option(label="MG")
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


def run():
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
            print({"captured": 1 if resultado else 0, "persisted": 0})
        finally:
            browser.close()


if __name__ == "__main__":
    run()
