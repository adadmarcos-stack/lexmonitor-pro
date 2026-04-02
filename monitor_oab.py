import time
from db import inserir_publicacao
from datetime import datetime


def capturar_publicacoes_fake():
    # Simulação (depois ligamos no site real)
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    publicacoes = [
        {
            "processo": "0001234-56.2024.8.13.0001",
            "data": agora,
            "texto": "Intimação para manifestação no prazo de 5 dias.",
        },
        {
            "processo": "0009876-11.2023.8.13.0001",
            "data": agora,
            "texto": "Despacho ordinatório sem conteúdo relevante.",
        },
    ]

    return publicacoes


def analisar_relevancia(texto):
    palavras_chave = [
        "intimação",
        "prazo",
        "manifestação",
        "sentença",
        "decisão",
    ]

    texto_lower = texto.lower()

    for palavra in palavras_chave:
        if palavra in texto_lower:
            return True, f"Contém '{palavra}'"

    return False, ""


def executar_monitor():
    print("🔎 Iniciando monitor...")

    publicacoes = capturar_publicacoes_fake()

    for pub in publicacoes:
        relevante, motivo = analisar_relevancia(pub["texto"])

        inserir_publicacao(
            processo=pub["processo"],
            data_publicacao=pub["data"],
            texto=pub["texto"],
            relevante=relevante,
            motivo_filtro=motivo,
            enviado_email=False,
        )

        print(f"✔ Inserido: {pub['processo']} | Relevante: {relevante}")


if __name__ == "__main__":
    executar_monitor()
