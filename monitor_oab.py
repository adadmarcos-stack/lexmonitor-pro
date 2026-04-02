from datetime import datetime
from db import get_conn


def publicacao_existe(processo, texto):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id
        FROM publicacoes
        WHERE processo = %s AND texto = %s
        LIMIT 1;
        """,
        (processo, texto),
    )

    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def inserir_publicacao(processo, data_publicacao, texto, relevante=False, motivo_filtro="", enviado_email=False):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO publicacoes (
            processo,
            data_publicacao,
            texto,
            relevante,
            motivo_filtro,
            enviado_email
        )
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (
            processo,
            data_publicacao,
            texto,
            relevante,
            motivo_filtro,
            enviado_email,
        ),
    )

    conn.commit()
    cur.close()
    conn.close()


def analisar_relevancia(texto):
    texto_lower = (texto or "").lower()

    palavras_chave = [
        "intimação",
        "prazo",
        "manifestação",
        "sentença",
        "decisão",
        "audiência",
        "urgente",
        "cumprimento",
        "citação",
    ]

    for palavra in palavras_chave:
        if palavra in texto_lower:
            return True, f"Contém a palavra-chave: {palavra}"

    return False, ""


def capturar_publicacoes():
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    return [
        {
            "processo": "0001234-56.2025.8.13.0701",
            "data_publicacao": agora,
            "texto": "Intimação da parte autora para manifestação no prazo de 5 dias.",
        },
        {
            "processo": "0009876-11.2024.8.13.0701",
            "data_publicacao": agora,
            "texto": "Despacho de mero expediente sem conteúdo urgente.",
        },
    ]


def executar_monitor():
    publicacoes = capturar_publicacoes()

    for item in publicacoes:
        processo = item["processo"]
        data_publicacao = item["data_publicacao"]
        texto = item["texto"]

        if publicacao_existe(processo, texto):
            print(f"Já existe: {processo}")
            continue

        relevante, motivo = analisar_relevancia(texto)

        inserir_publicacao(
            processo=processo,
            data_publicacao=data_publicacao,
            texto=texto,
            relevante=relevante,
            motivo_filtro=motivo,
            enviado_email=False,
        )

        print(f"Inserido: {processo} | relevante={relevante}")


if __name__ == "__main__":
    executar_monitor()
