async def wait_for_oab_result(page):
    print("Aguardando tela após login...")

    await page.wait_for_timeout(5000)

    # 🔥 PASSO 1 — garantir que está no histórico
    if "historico" not in page.url.lower():
        print("Indo para histórico manual...")
        await page.goto(OAB_HISTORICO_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

    # 🔥 PASSO 2 — clicar em CONSULTAR
    print("Clicando em CONSULTAR...")

    try:
        await page.locator("button:has-text('Consultar')").first.click()
    except:
        try:
            await page.locator("text=Consultar").first.click()
        except:
            print("⚠️ Não encontrou botão Consultar")

    await page.wait_for_timeout(4000)

    # 🔥 PASSO 3 — clicar em VISUALIZAR TUDO
    print("Clicando em VISUALIZAR TUDO...")

    try:
        await page.locator("button:has-text('Visualizar tudo')").first.click()
    except:
        try:
            await page.locator("text=Visualizar tudo").first.click()
        except:
            print("⚠️ Não encontrou botão Visualizar tudo")

    await page.wait_for_timeout(6000)

    print("Tela de publicações carregada.")
