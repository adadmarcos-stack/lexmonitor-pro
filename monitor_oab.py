import asyncio
import re
from datetime import datetime, timedelta
from playwright.async_api import async_playwright


from config import OAB_LOGIN_URL, OAB_NUMERO, OAB_UF, OAB_CPF, OAB_IDENTIDADE


OAB_HISTORICO_URL = "https://recortedigital.oabmg.org.br/historico/historicodata.aspx"


# ===============================
# LOGIN ROBUSTO
# ===============================
async def fill_oab_login(page):
    print("🔐 Preenchendo login OAB...")

    await page.wait_for_timeout(3000)

    numero = re.sub(r"\D", "", OAB_NUMERO)
    cpf = re.sub(r"\D", "", OAB_CPF)
    identidade = re.sub(r"\D", "", OAB_IDENTIDADE)

    inputs = page.locator("input")
    count = await inputs.count()

    if count < 3:
        raise RuntimeError("Campos de login não encontrados.")

    await inputs.nth(0).fill(numero)
    await page.wait_for_timeout(500)

    await inputs.nth(1).fill(cpf)
    await page.wait_for_timeout(500)

    await inputs.nth(2).fill(identidade)
    await page.wait_for_timeout(500)

    try:
        await page.locator("button:has-text('Entrar')").click()
    except:
        await page.locator("input[type='submit']").click()

    print("✅ Login enviado")


# ===============================
# FLUXO PÓS LOGIN (SEU CAMINHO)
# ===============================
async def fluxo_pos_login(page):
    print("⏳ Aguardando tela após login...")
    await page.wait_for_timeout(5000)

    print("Indo para histórico...")
    await page.goto(OAB_HISTORICO_URL)
    await page.wait_for_timeout(5000)

    # ===============================
    # DEFINIR DATAS AUTOMÁTICAS
    # ===============================
    hoje = datetime.now()
    inicio = hoje - timedelta(days=60)

    data_inicio = inicio.strftime("%d/%m/%Y")
    data_fim = hoje.strftime("%d/%m/%Y")

    print(f"Preenchendo datas: {data_inicio} até {data_fim}")

    inputs = page.locator("input")

    try:
        await inputs.nth(0).fill(data_inicio)
        await inputs.nth(1).fill(data_fim)
    except:
        print("⚠️ Não conseguiu preencher datas (segue mesmo assim)")

    await page.wait_for_timeout(1000)

    # ===============================
    # CLICAR CONSULTAR
    # ===============================
    try:
        await page.locator("button:has-text('Consultar')").click()
        print("Clicou CONSULTAR")
    except:
        print("❌ Botão CONSULTAR não encontrado")

    await page.wait_for_timeout(4000)

    # ===============================
    # CLICAR VISUALIZAR TUDO
    # ===============================
    try:
        await page.locator("button:has-text('Visualizar tudo')").click()
        print("Clicou VISUALIZAR TUDO")
    except:
        print("⚠️ Botão VISUALIZAR TUDO não apareceu")

    await page.wait_for_timeout(5000)


# ===============================
# SCRAPER PRINCIPAL
# ===============================
async def scrape_oab():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        context = await browser.new_context()
        page = await context.new_page()

        print("🚀 Abrindo OAB...")
        await page.goto(OAB_LOGIN_URL)
        await page.wait_for_timeout(4000)

        await fill_oab_login(page)
        await fluxo_pos_login(page)

        print("📄 Capturando conteúdo...")
        texto = await page.locator("body").inner_text()

        print("\n========== RESULTADO ==========\n")
        print(texto[:2000])  # preview

        await browser.close()

        return texto


# ===============================
# EXECUÇÃO
# ===============================
def executar_monitor():
    try:
        resultado = asyncio.run(scrape_oab())

        return {
            "captured": 1 if resultado else 0,
            "persisted": 0,
        }

    except Exception as e:
        print(f"Erro ao capturar OAB: {e}")
        return {"captured": 0, "persisted": 0}


if __name__ == "__main__":
    print(executar_monitor())
