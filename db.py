import psycopg2
import psycopg2.extras
from config import DATABASE_URL

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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS publicacoes (
            id SERIAL PRIMARY KEY,
            fonte TEXT NOT NULL DEFAULT 'oab',
            processo TEXT,
            data_publicacao TEXT,
            texto TEXT NOT NULL,
            relevante BOOLEAN NOT NULL DEFAULT FALSE,
            motivo_filtro TEXT DEFAULT '',
            enviado_email BOOLEAN NOT NULL DEFAULT FALSE,
            evento_calendario_criado BOOLEAN NOT NULL DEFAULT FALSE,
            hash_unico TEXT UNIQUE,
            criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def fetch_publicacoes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, fonte, processo, data_publicacao, texto, relevante, motivo_filtro,
               enviado_email, evento_calendario_criado, criado_em
        FROM publicacoes
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def publicacao_existe_por_hash(hash_unico):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM publicacoes WHERE hash_unico = %s LIMIT 1", (hash_unico,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None

def inserir_publicacao(fonte, processo, data_publicacao, texto, relevante, motivo_filtro, hash_unico):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO publicacoes (
            fonte, processo, data_publicacao, texto, relevante,
            motivo_filtro, enviado_email, evento_calendario_criado, hash_unico
        )
        VALUES (%s, %s, %s, %s, %s, %s, FALSE, FALSE, %s)
        ON CONFLICT (hash_unico) DO NOTHING
        RETURNING id
    """, (fonte, processo, data_publicacao, texto, relevante, motivo_filtro, hash_unico))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return row["id"] if row else None

def buscar_publicacoes_pendentes_alerta():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, fonte, processo, data_publicacao, texto, relevante, motivo_filtro
        FROM publicacoes
        WHERE relevante = TRUE AND enviado_email = FALSE
        ORDER BY id ASC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def marcar_email_enviado(publicacao_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE publicacoes SET enviado_email = TRUE WHERE id = %s", (publicacao_id,))
    conn.commit()
    cur.close()
    conn.close()

def marcar_evento_calendario(publicacao_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE publicacoes SET evento_calendario_criado = TRUE WHERE id = %s", (publicacao_id,))
    conn.commit()
    cur.close()
    conn.close()
