import asyncio
import re
from datetime import datetime, timedelta

from playwright.async_api import async_playwright

from config import OAB_LOGIN_URL, OAB_NUMERO, OAB_UF, OAB_CPF, OAB_IDENTIDADE

OAB_HISTORICO_URL = "https://recortedigital.oabmg.org.br/historico/historicodata.aspx"


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


async def visible_inputs(page):
    inputs = page.locator("input")
    total = await inputs.count()
    visibles = []

    for i in range(total):
        try:
            item = inputs.nth(i)
            input_type = (await item.get_attribute("type") or "").lower()
            if input_type in {"hidden", "submit", "button", "checkbox", "radio"}:
                continue
            if await item.is_visible():
                visibles.append(item)
        except Exception:
            continue

    return visibles


async def click_first(page, selectors, label: str, wait_ms: int = 4000) -> bool:
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

    await page.wait_for_timeout(4000)

    numero = only_digits(OAB_NUMERO)
    cpf = only_digits(OAB_CPF)
    identidade = only_digits(OAB_IDENTIDADE)

    visiveis = await visible_inputs(page)
    print(f"Inputs visíveis encontrados: {len(visiveis)}")

    if len(visiveis) < 3:
        raise RuntimeError("Não encontrei 3 campos visíveis para login.")

    await visiveis[0].click()
    await visiveis[0].fill(numero)
    await page.wait_for_timeout(500)

    try:
        selects = page.locator("select")
        if await selects.count():
            try:
                await selects.first.select_option(label=OAB_UF)
            except Exception:
                await selects.first.select_option(value=OAB_UF)
    except Exception:
        pass

    await visiveis[1].click()
    await visiveis[1].fill(cpf)
    await page.wait_for_timeout(500)

    await visiveis[2].click()
    await visiveis[2].fill(identidade)
    await page.wait_for_timeout(500)

    clicou = await click_first(
        page,
        [
            "#btnEntrar",
            "button:has-text('Entrar')",
            "button:has-text('ENTRAR')",
            "input[type='submit']",
            "input[value='Entrar']",
            "input[value='ENTRAR']",
        ],
        "ENTRAR",
        wait_ms=6000,
    )

    if not clicou:
        raise RuntimeError("Botão ENTRAR não encontrado.")

    print("⏳ Confirmando login...")
    await page.wait_for_timeout(6000)

    body_text = await page.locator("body").inner_text()
    body_lower = body_text.lower()

    if (
        "seja bem vindo" in body_lower
        or "portal de publicações" in body_lower
        or "acesso publicações" in body_lower
        or "histórico - publicações por data" in body_lower
    ):
        print("✅ Login confirmado.")
        return

    print("⚠️ Login não confirmado. Trecho da página:")
    print(body_text[:1500])
    raise RuntimeError("Login da OAB não concluiu corretamente.")


async def preencher_datas_historico(page, days_back: int = 60):
    inicio = (datetime.now() - timedelta(days=days_back)).strftime("%d/%m/%Y")
    fim = datetime.now().strftime("%d/%m/%Y")

    print(f"Preenchendo datas: {inicio} até {fim}")

    visiveis = await visible_inputs(page)

    if len(visiveis) >= 2:
        try:
            await visiveis[0].click()
            await visiveis[0].fill(inicio)
            await page.wait_for_timeout(500)

            await visiveis[1].click()
            await visiveis[1].fill(fim)
            await page.wait_for_timeout(500)

            print("Datas preenchidas.")
            return
        except Exception:
            pass

    print("⚠️ Campos de data não encontrados.")


async def fluxo_pos_login(page):
    print("📂 Abrindo histórico...")
    await page.goto(OAB_HISTORICO_URL, wait_until="domcontentloaded", timeout=120000)
    await page.wait_for_timeout(8000)

    body_text = await page.locator("body").inner_text()

    if "Dados incompletos. Favor preencher nome de usuário e senha." in body_text:
        raise RuntimeError("Sessão não autenticada ao abrir histórico.")

    await preencher_datas_historico(page, days_back=60)

    await click_first(
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
        wait_ms=6000,
    )

    await click_first(
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
        wait_ms=8000,
    )


async def scrape_oab():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        context = await browser.new_context(
            viewport={"width": 1440, "height": 1100},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )
        page = await context.new_page()

        try:
            print("🚀 Abrindo OAB...")
            await page.goto(OAB_LOGIN_URL, wait_until="domcontentloaded", timeout=120000)
            await page.wait_for_timeout(8000)

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
