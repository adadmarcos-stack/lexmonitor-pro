from app.services.config_store import get_config

def buscar_publicacoes():
    config = get_config()

    if not config:
        return {
            "ok": False,
            "message": "Preencha e salve primeiro a configuração OAB."
        }

    # Aqui futuramente entra scraping real
    return {
        "ok": True,
        "publicacoes": [
            {
                "processo": "0001234-56.2024.8.13.0701",
                "descricao": "Nova movimentação no processo",
                "data": "28/03/2026"
            }
        ]
    }