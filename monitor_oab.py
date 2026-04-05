from playwright.sync_api import sync_playwright
import time

OAB_NUMERO = "113674"
CPF = "06819623640"  # SEM PONTUAÇÃO
IDENTIDADE = "12989116"

URL = "https://recortedigital.oabmg.org.br/"

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🚀 Abrindo OAB...")
        page.goto(URL, timeout=60000)

        time.sleep(3)

        print("🔐 Preenchendo login...")

        inputs = page.locator("input").all()

        inputs_visiveis = [i for i in inputs if i.is_visible()]

        print(f"Inputs visíveis encontrados: {len(inputs_visiveis)}")

        if len(inputs_visiveis) < 3:
            raise Exception("Não encontrou campos suficientes")

        # ORDEM CORRETA
        inputs_visiveis[0].fill(OAB_NUMERO)
        inputs_visiveis[1].fill(CPF)
        inputs_visiveis[2].fill(IDENTIDADE)

        page.locator("button:has-text('ENTRAR')").click()

        print("⏳ Confirmando login...")
        time.sleep(5)

        html = page.content()

        if "Dados incorretos" in html:
            raise Exception("❌ LOGIN INVÁLIDO - verifique CPF/OAB")

        print("✅ Login OK")

        print("📍 Indo para histórico...")
        page.goto("https://recortedigital.oabmg.org.br/historico/historicodata.aspx")

        time.sleep(5)

        print("📅 Preenchendo datas...")

        inputs = page.locator("input").all()
        inputs_visiveis = [i for i in inputs if i.is_visible()]

        if len(inputs_visiveis) >= 2:
            inputs_visiveis[0].fill("01/02/2026")
            inputs_visiveis[1].fill("05/04/2026")

        print("🔍 Clicando consultar...")

        page.locator("button:has-text('Consultar')").click()

        time.sleep(5)

        print("📄 Clicando visualizar tudo...")

        try:
            page.locator("button:has-text('Visualizar tudo')").click()
        except:
            print("⚠️ Botão visualizar tudo não encontrado")

        time.sleep(5)

        print("📥 Capturando conteúdo...")

        content = page.inner_text("body")

        print("\n========== RESULTADO ==========\n")
        print(content[:3000])

        browser.close()

if __name__ == "__main__":
    run()
