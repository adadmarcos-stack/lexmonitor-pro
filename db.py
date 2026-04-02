import os
import psycopg2
import psycopg2.extras


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada.")
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
        sslmode="require",
    )


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS publicacoes (
            id SERIAL PRIMARY KEY,
            processo TEXT,
            data_publicacao TEXT,
            texto TEXT NOT NULL,
            relevante BOOLEAN NOT NULL DEFAULT FALSE,
            motivo_filtro TEXT,
            enviado_email BOOLEAN NOT NULL DEFAULT FALSE,
            criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publicacoes_processo
        ON publicacoes (processo);
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_publicacoes_relevante
        ON publicacoes (relevante);
        """
    )

    conn.commit()
    cur.close()
    conn.close()


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
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
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

    novo_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return novo_id


def marcar_enviado(publicacao_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE publicacoes
        SET enviado_email = TRUE
        WHERE id = %s;
        """,
        (publicacao_id,),
    )

    conn.commit()
    cur.close()
    conn.close()
