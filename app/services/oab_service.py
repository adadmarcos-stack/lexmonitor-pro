from playwright.sync_api import sync_playwright
import re
import time


def clicar_como_humano(page, selector):
    btn = page.locator(selector)
    btn.wait_for(timeout=30000)

    box = btn.bounding_box()
    if not box:
        raise Exception("Botão não encontrado na tela")

    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2

    page.mouse.move(x, y)
    page.wait_for_timeout(300)
    page.mouse.click(x, y)


def consultar_publicacoes():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # IMPORTANTE
            context = browser.new_context(
                viewport={"width": 1400, "height": 2200}
            )
            page = context.new_page()

            for tentativa in range(3):
                print(f"\n--- TENTATIVA {tentativa + 1} ---")

                try:
                    print("Acessando login...")

                    page.goto(
                        "https://recortedigital.oabmg.org.br/",
                        timeout=120000,
                        wait_until="domcontentloaded"
                    )

                    page.wait_for_timeout(5000)

                    print("Preenchendo dados...")

                    page.wait_for_selector("#txbOAB", timeout=30000)

                    page.fill("#txbOAB", "113674")
                    page.fill("#txbCPF", "06819623640")
                    page.fill("#txbCI", "12989116")

                    try:
                        page.select_option("#ddlSiglaUF", "MG")
                    except:
                        pass

                    page.wait_for_timeout(2000)

                    print("Clicando entrar...")

                    clicar_como_humano(page, "#btnEntrar")

                    page.wait_for_load_state("networkidle", timeout=60000)
                    page.wait_for_timeout(5000)

                    print("Indo para histórico...")

                    page.goto(
                        "https://recortedigital.oabmg.org.br/historico/historicodata.aspx",
                        timeout=120000,
                        wait_until="domcontentloaded"
                    )

                    page.wait_for_timeout(6000)

                    print("Clicando consultar...")

                    try:
                        clicar_como_humano(page, "text=Consultar")
                    except:
                        page.evaluate("""
                            () => {
                                const els = [...document.querySelectorAll('button, input, a, span, div')];
                                const el = els.find(e => (e.innerText || e.value || '').toLowerCase().includes('consultar'));
                                if (el) el.click();
                            }
                        """)

                    page.wait_for_timeout(6000)

                    print("Clicando visualizar tudo...")

                    try:
                        clicar_como_humano(page, "text=Visualizar tudo")
                    except:
                        pass

                    page.wait_for_timeout(8000)

                    print("Forçando carregamento...")

                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(3000)

                    print("Capturando dados...")

                    texto = page.locator("body").inner_text(timeout=30000)
                    html = page.content()

                    if len(texto) < 100:
                        print("Nenhum dado encontrado, tentando novamente...")
                        continue

                    processos = re.findall(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", texto)
                    processos = list(dict.fromkeys(processos))

                    datas = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", texto)
                    datas = list(dict.fromkeys(datas))

                    print("Finalizado com sucesso")

                    browser.close()

                    return {
                        "ok": True,
                        "processos": processos[:100],
                        "datas": datas[:100],
                        "preview": texto[:5000]
                    }

                except Exception as e:
                    print("Erro na tentativa:", e)
                    time.sleep(3)

            browser.close()

            return {
                "ok": False,
                "erro": "Falhou após várias tentativas"
            }

    except Exception as e:
        return {
            "ok": False,
            "erro": str(e)
        }


if __name__ == "__main__":
    resultado = consultar_publicacoes()
    print("\nRESULTADO FINAL:")
    print(resultado)