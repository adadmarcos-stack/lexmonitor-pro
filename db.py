import os
import sqlite3

DB_PATH = os.getenv("DATABASE_PATH", "/tmp/lexmonitor.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def publicacao_existe_por_hash(hash_unico):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM publicacoes WHERE hash_unico = ?", (hash_unico,))
    result = cur.fetchone()

    cur.close()
    conn.close()

    return result is not None


def inserir_publicacao(
    fonte,
    processo,
    data_publicacao,
    texto,
    relevante,
    motivo_filtro,
    hash_unico,
):
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO publicacoes (
                fonte,
                processo,
                data_publicacao,
                texto,
                relevante,
                motivo_filtro,
                hash_unico
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            fonte,
            processo,
            data_publicacao,
            texto,
            int(relevante),
            motivo_filtro,
            hash_unico
        ))

        conn.commit()
        return True

    except Exception as e:
        print("Erro ao inserir:", e)
        return False

    finally:
        cur.close()
        conn.close()


# 🔥 NOVAS FUNÇÕES (QUE ESTAVAM FALTANDO)

def buscar_publicacoes_pendentes_alerta():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, processo, texto
        FROM publicacoes
        WHERE alerta_enviado IS NULL OR alerta_enviado = 0
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def marcar_email_enviado(publicacao_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE publicacoes
        SET alerta_enviado = 1
        WHERE id = ?
    """, (publicacao_id,))

    conn.commit()

    cur.close()
    conn.close()


def marcar_evento_calendario(publicacao_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE publicacoes
        SET evento_calendario = 1
        WHERE id = ?
    """, (publicacao_id,))

    conn.commit()

    cur.close()
    conn.close()
