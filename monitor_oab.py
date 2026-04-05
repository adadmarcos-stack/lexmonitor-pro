import asyncio
import re
from datetime import datetime, timedelta
from playwright.async_api import async_playwright


from config import OAB_LOGIN_URL, OAB_NUMERO, OAB_UF, OAB_CPF, OAB_IDENTIDADE


OAB_HISTORICO_URL = "https://recortedigital.oabmg.org.br/historico/historicodata.aspx"


async def get_visible_inputs(page):
    inputs = page.locator("input")
    total = await inputs.count()
    visible = []

    for i in range(total):
        try:
            item = inputs.nth(i)
            if await item.is_visible():
                visible.append(item)
        except Exception:
            continue

    return visible


async def fill_oab_login(page):
    print("🔐 Preenchendo login OAB...")

    await page.wait_for_timeout(3000)

    numero = re.sub(r"\D", "", OAB_NUMERO)
    cpf = re.sub(r"\D", "", OAB_CPF)
    identidade = re.sub(r"\D", "", OAB_IDENTIDADE)

    visible_inputs = await get_visible_inputs(page)

    print(f"Inputs visíveis encontrados: {len(visible_inputs)}")

    if len(visible_inputs) < 3:
        raise RuntimeError("Campos visíveis de login não encontrados.")

    await visible_inputs[0].fill(numero)
    await page.wait_for_timeout(500)

    try:
        selects = page.locator("select")
        if await selects.count():
            try:
                await selects.nth(0).select_option(label=OAB_UF)
            except Exception:
                await selects.nth(0).select_option(value=OAB_UF)
    except Exception:
        pass

    await visible_inputs[1].fill(cpf)
    await page.wait_for_timeout(500)

    await visible_inputs[2].fill(identidade)
    await page.wait_for_timeout(500)

    try:
        await page.locator("button:has-text('Entrar')").click()
    except Exception:
        try:
            await page.locator("input[type='submit']").click()
        except Exception:
            raise RuntimeError("Botão ENTRAR não encontrado.")

    print("✅ Login enviado")


async def click_if_exists(page, selectors, label, wait_ms=4000):
    for sel in selectors:
        try:
            locator = page.locator(sel)
            if await locator.count():
                await locator.first.click()
                print(f"Clicou em: {label}")
                await page.wait_for_timeout(wait_ms)
                return True
        except Exception:
            continue
    print(f"Não encontrou: {label}")
    return False


async def fluxo_pos_login(page):
    print("⏳ Aguardando tela após login...")
    await page.wait_for_timeout(5000)

    print("Indo para histórico...")
    await page.goto(OAB_HISTORICO_URL)
    await page.wait_for_timeout(5000)

    hoje = datetime.now()
    inicio = hoje - timedelta(days=60)

    data_inicio = inicio.strftime("%d/%m/%Y")
    data_fim = hoje.strftime("%d/%m/%Y")

    print(f"Preenchendo datas: {data_inicio} até {data_fim}")

    visible_inputs = await get_visible_inputs(page)

    if len(visible_inputs) >= 2:
        try:
            await visible_inputs[0].fill(data_inicio)
            await visible_inputs[1].fill(data_fim)
            print("Datas preenchidas.")
        except Exception:
            print("⚠️ Não conseguiu preencher datas.")
    else:
        print("⚠️ Campos de data não encontrados.")

    await page.wait_for_timeout(1000)

    await click_if_exists(
        page,
        [
            "button:has-text('Consultar')",
            "text=Consultar",
            "input[value='Consultar']",
            "button[type='submit']",
        ],
        "CONSULTAR",
        wait_ms=5000,
    )

    await click_if_exists(
        page,
        [
            "button:has-text('Visualizar tudo')",
            "text=Visualizar tudo",
            "input[value='Visualizar tudo']",
        ],
        "VISUALIZAR TUDO",
        wait_ms=6000,
    )


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
        print(texto[:3000])

        await browser.close()

        return texto


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
