import asyncio
import re
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config import OAB_LOGIN_URL, OAB_NUMERO, OAB_UF, OAB_CPF, OAB_IDENTIDADE

OAB_HISTORICO_URL = "https://recortedigital.oabmg.org.br/historico/historicodata.aspx"


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


async def first_working_locator(page, selectors):
    for sel in selectors:
        try:
            locator = page.locator(sel)
            if await locator.count():
                return locator.first
        except Exception:
            continue
    return None


async def click_first_working(page, selectors, label: str, wait_ms: int = 4000) -> bool:
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


async def fill_oab_login(page):
    print("🔐 Preenchendo login OAB...")

    await page.wait_for_timeout(3000)

    numero = only_digits(OAB_NUMERO)
    cpf = only_digits(OAB_CPF)
    identidade = only_digits(OAB_IDENTIDADE)

    numero_field = await first_working_locator(
        page,
        [
            "#txbOAB",
            "input[name='txbOAB']",
            "input[id*='OAB']",
            "input[placeholder*='OAB']",
        ],
    )
    if not numero_field:
        raise RuntimeError("Campo OAB não encontrado.")

    await numero_field.click()
    await numero_field.fill(numero)

    try:
        uf_select = page.locator("select")
        if await uf_select.count():
            try:
                await uf_select.first.select_option(label=OAB_UF)
            except Exception:
                await uf_select.first.select_option(value=OAB_UF)
    except Exception:
        pass

    cpf_field = await first_working_locator(
        page,
        [
            "#txbCPF",
            "input[name='txbCPF']",
            "input[id*='CPF']",
            "input[placeholder*='CPF']",
        ],
    )
    if not cpf_field:
        raise RuntimeError("Campo CPF não encontrado.")

    await cpf_field.click()
    await cpf_field.fill(cpf)

    ci_field = await first_working_locator(
        page,
        [
            "#txbCI",
            "input[name='txbCI']",
            "input[id*='CI']",
            "input[placeholder*='identidade']",
            "input[placeholder*='Identidade']",
        ],
    )
    if not ci_field:
        raise RuntimeError("Campo identidade não encontrado.")

    await ci_field.click()
    await ci_field.fill(identidade)

    clicked = await click_first_working(
        page,
        [
            "#btnEntrar",
            "button:has-text('Entrar')",
            "input[type='submit']",
            "input[value='Entrar']",
        ],
        "ENTRAR",
        wait_ms=5000,
    )

    if not clicked:
        raise RuntimeError("Botão ENTRAR não encontrado.")

    print("⏳ Confirmando login...")
    await page.wait_for_timeout(4000)

    body_text = await page.locator("body").inner_text()
    body_lower = body_text.lower()

    if (
        "seja bem vindo" in body_lower
        or "portal de publicações" in body_lower
        or "histórico - publicações por data" in body_lower
    ):
        print("✅ Login confirmado.")
        return

    print("⚠️ Login não confirmado. Trecho da página:")
    print(body_text[:1200])
    raise RuntimeError("Login da OAB não concluiu corretamente.")


async def fill_history_filters(page, days_back: int = 60):
    inicio = (datetime.now() - timedelta(days=days_back)).strftime("%d/%m/%Y")
    fim = datetime.now().strftime("%d/%m/%Y")

    print(f"Preenchendo datas: {inicio} até {fim}")

    inputs = page.locator("input")
    visible_text_inputs = []

    count = await inputs.count()
    for i in range(count):
        try:
            item = inputs.nth(i)
            input_type = (await item.get_attribute("type") or "").lower()
            if input_type in {"hidden", "submit", "button", "checkbox", "radio"}:
                continue
            if await item.is_visible():
                visible_text_inputs.append(item)
        except Exception:
            continue

    if len(visible_text_inputs) >= 2:
        await visible_text_inputs[0].click()
        await visible_text_inputs[0].fill(inicio)
        await page.wait_for_timeout(400)

        await visible_text_inputs[1].click()
        await visible_text_inputs[1].fill(fim)
        await page.wait_for_timeout(400)

        print("Datas preenchidas.")
    else:
        print("⚠️ Campos de data não encontrados.")


async def fluxo_pos_login(page):
    print("📂 Abrindo histórico...")
    await page.goto(OAB_HISTORICO_URL, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(5000)

    body_text = await page.locator("body").inner_text()
    if "Dados incompletos. Favor preencher nome de usuário e senha." in body_text:
        raise RuntimeError("Sessão não autenticada ao abrir histórico.")

    await fill_history_filters(page, days_back=60)

    await click_first_working(
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

    await click_first_working(
        page,
        [
            "button:has-text('Visualizar tudo')",
            "text=Visualizar tudo",
            "input[value='Visualizar tudo']",
        ],
        "VISUALIZAR TUDO",
        wait_ms=7000,
    )


async def scrape_oab():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("🚀 Abrindo OAB...")
            await page.goto(OAB_LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(4000)

            await fill_oab_login(page)
            await fluxo_pos_login(page)

            print("📄 Capturando conteúdo...")
            texto = await page.locator("body").inner_text()

            print("\n========== RESULTADO ==========\n")
            print(texto[:3000])

            return texto
        finally:
            await browser.close()


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
