import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS publicacoes (
        id SERIAL PRIMARY KEY,
        fonte TEXT,
        processo TEXT,
        data_publicacao TEXT,
        texto TEXT,
        relevante BOOLEAN DEFAULT FALSE,
        motivo_filtro TEXT,
        hash_unico TEXT UNIQUE,
        enviado_email BOOLEAN DEFAULT FALSE,
        criado_em TIMESTAMP DEFAULT NOW()
    );
    """)

    cur.execute("""
    ALTER TABLE publicacoes
    ADD COLUMN IF NOT EXISTS parte_autora TEXT,
    ADD COLUMN IF NOT EXISTS parte_re TEXT,
    ADD COLUMN IF NOT EXISTS tribunal TEXT,
    ADD COLUMN IF NOT EXISTS resumo_ia TEXT,
    ADD COLUMN IF NOT EXISTS o_que_fazer TEXT,
    ADD COLUMN IF NOT EXISTS prazo TEXT,
    ADD COLUMN IF NOT EXISTS urgencia TEXT;
    """)

    conn.commit()
    cur.close()
    conn.close()


def publicacao_existe_por_hash(hash_unico: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM publicacoes WHERE hash_unico = %s LIMIT 1",
        (hash_unico,),
    )
    found = cur.fetchone() is not None
    cur.close()
    conn.close()
    return found


def inserir_publicacao(
    fonte,
    processo,
    data_publicacao,
    texto,
    relevante,
    motivo_filtro,
    hash_unico,
    parte_autora="",
    parte_re="",
    tribunal="",
    resumo_ia="",
    o_que_fazer="",
    prazo="",
    urgencia="",
):
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO publicacoes (
                fonte, processo, data_publicacao, texto,
                relevante, motivo_filtro, hash_unico,
                parte_autora, parte_re, tribunal,
                resumo_ia, o_que_fazer, prazo, urgencia
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (hash_unico) DO NOTHING
        """, (
            fonte, processo, data_publicacao, texto,
            relevante, motivo_filtro, hash_unico,
            parte_autora, parte_re, tribunal,
            resumo_ia, o_que_fazer, prazo, urgencia
        ))

        inserted = cur.rowcount > 0
        conn.commit()
        return inserted
    finally:
        cur.close()
        conn.close()


def fetch_publicacoes():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            fonte,
            processo,
            data_publicacao,
            texto,
            relevante,
            motivo_filtro,
            hash_unico,
            enviado_email,
            criado_em,
            parte_autora,
            parte_re,
            tribunal,
            resumo_ia,
            o_que_fazer,
            prazo,
            urgencia
        FROM publicacoes
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def buscar_publicacoes_pendentes_alerta():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            fonte,
            processo,
            data_publicacao,
            texto,
            relevante,
            motivo_filtro,
            hash_unico,
            enviado_email,
            criado_em,
            parte_autora,
            parte_re,
            tribunal,
            resumo_ia,
            o_que_fazer,
            prazo,
            urgencia
        FROM publicacoes
        WHERE enviado_email = FALSE
        ORDER BY id ASC
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def marcar_email_enviado(publicacao_id: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "UPDATE publicacoes SET enviado_email = TRUE WHERE id = %s",
        (publicacao_id,),
    )

    conn.commit()
    cur.close()
    conn.close()
