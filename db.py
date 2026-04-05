import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional


# ─── Detecção de banco (PostgreSQL ou SQLite) ─────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Render entrega URLs no formato "postgres://..." — psycopg2 exige "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

USE_POSTGRES = DATABASE_URL.startswith("postgresql://")

if USE_POSTGRES:
    try:
        import psycopg2
        import psycopg2.extras
        print("[db] Usando PostgreSQL:", DATABASE_URL[:40], "...")
    except ImportError:
        USE_POSTGRES = False
        print("[db] psycopg2 não encontrado — usando SQLite.")

# ─── SQLite (fallback / desenvolvimento local) ────────────────────────────────

def _get_db_path() -> str:
    try:
        import config  # type: ignore
        db_path = getattr(config, "DB_PATH", None)
        if db_path:
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            return db_path
    except Exception:
        pass

    default_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(default_dir, exist_ok=True)
    return os.path.join(default_dir, "jammal_control.db")


DB_PATH = _get_db_path()


# ─── Context managers unificados ─────────────────────────────────────────────

@contextmanager
def get_conn():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _placeholder() -> str:
    """Retorna o placeholder correto para o banco ativo."""
    return "%s" if USE_POSTGRES else "?"


def _execute(cursor, sql: str, params=None):
    """Executa SQL adaptando placeholders automaticamente."""
    if USE_POSTGRES:
        sql = sql.replace("?", "%s")
        sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT",
                          "SERIAL PRIMARY KEY")
    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)


def _fetchone_dict(cursor) -> Optional[Dict]:
    if USE_POSTGRES:
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))
    else:
        row = cursor.fetchone()
        return dict(row) if row else None


def _fetchall_dict(cursor) -> List[Dict]:
    if USE_POSTGRES:
        rows = cursor.fetchall()
        if not rows:
            return []
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in rows]
    else:
        return [dict(row) for row in cursor.fetchall()]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _safe_json_load(value: Any) -> Dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def _iso_to_br(iso_value: Optional[str]) -> str:
    if not iso_value:
        return ""
    try:
        value = str(iso_value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(iso_value)


# ─── DDL ─────────────────────────────────────────────────────────────────────

def init_db() -> None:
    with get_conn() as conn:
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS publications (
                    id SERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT,
                    process_number TEXT,
                    title TEXT,
                    content TEXT,
                    url TEXT,
                    publication_date TEXT,
                    deadline_date TEXT,
                    risk_level TEXT,
                    ai_summary TEXT,
                    ai_action TEXT,
                    ai_tags TEXT,
                    is_relevant INTEGER DEFAULT 1,
                    alert_sent INTEGER DEFAULT 0,
                    raw_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(source, external_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS monitor_logs (
                    id SERIAL PRIMARY KEY,
                    monitor_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS drive_files (
                    id SERIAL PRIMARY KEY,
                    file_id TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    mime_type TEXT,
                    modified_time TEXT,
                    web_view_link TEXT,
                    processed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        else:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS publications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    external_id TEXT,
                    process_number TEXT,
                    title TEXT,
                    content TEXT,
                    url TEXT,
                    publication_date TEXT,
                    deadline_date TEXT,
                    risk_level TEXT,
                    ai_summary TEXT,
                    ai_action TEXT,
                    ai_tags TEXT,
                    is_relevant INTEGER DEFAULT 1,
                    alert_sent INTEGER DEFAULT 0,
                    raw_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(source, external_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS monitor_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    monitor_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS drive_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    mime_type TEXT,
                    modified_time TEXT,
                    web_view_link TEXT,
                    processed INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )


# ─── Operações ───────────────────────────────────────────────────────────────

def log_monitor(monitor_name: str, status: str, message: str = "") -> None:
    with get_conn() as conn:
        cursor = conn.cursor()
        sql = "INSERT INTO monitor_logs (monitor_name, status, message, created_at) VALUES (?, ?, ?, ?)"
        _execute(cursor, sql, (monitor_name, status, message, now_iso()))


def upsert_publication(data: Dict[str, Any]) -> int:
    source = data.get("source", "unknown")
    external_id = data.get("external_id")
    created_at = now_iso()
    updated_at = now_iso()

    with get_conn() as conn:
        cursor = conn.cursor()

        if external_id:
            _execute(
                cursor,
                "SELECT id FROM publications WHERE source = ? AND external_id = ? LIMIT 1",
                (source, external_id),
            )
            existing = _fetchone_dict(cursor)

            if existing:
                _execute(
                    cursor,
                    """
                    UPDATE publications
                    SET process_number = ?, title = ?, content = ?, url = ?,
                        publication_date = ?, deadline_date = ?, risk_level = ?,
                        ai_summary = ?, ai_action = ?, ai_tags = ?,
                        is_relevant = ?, alert_sent = ?, raw_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        data.get("process_number"),
                        data.get("title"),
                        data.get("content"),
                        data.get("url"),
                        data.get("publication_date"),
                        data.get("deadline_date"),
                        data.get("risk_level"),
                        data.get("ai_summary"),
                        data.get("ai_action"),
                        data.get("ai_tags"),
                        int(bool(data.get("is_relevant", 1))),
                        int(bool(data.get("alert_sent", 0))),
                        data.get("raw_json"),
                        updated_at,
                        existing["id"],
                    ),
                )
                return int(existing["id"])

        if USE_POSTGRES:
            _execute(
                cursor,
                """
                INSERT INTO publications (
                    source, external_id, process_number, title, content, url,
                    publication_date, deadline_date, risk_level, ai_summary,
                    ai_action, ai_tags, is_relevant, alert_sent, raw_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    source, external_id, data.get("process_number"),
                    data.get("title"), data.get("content"), data.get("url"),
                    data.get("publication_date"), data.get("deadline_date"),
                    data.get("risk_level"), data.get("ai_summary"),
                    data.get("ai_action"), data.get("ai_tags"),
                    int(bool(data.get("is_relevant", 1))),
                    int(bool(data.get("alert_sent", 0))),
                    data.get("raw_json"), created_at, updated_at,
                ),
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        else:
            _execute(
                cursor,
                """
                INSERT INTO publications (
                    source, external_id, process_number, title, content, url,
                    publication_date, deadline_date, risk_level, ai_summary,
                    ai_action, ai_tags, is_relevant, alert_sent, raw_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source, external_id, data.get("process_number"),
                    data.get("title"), data.get("content"), data.get("url"),
                    data.get("publication_date"), data.get("deadline_date"),
                    data.get("risk_level"), data.get("ai_summary"),
                    data.get("ai_action"), data.get("ai_tags"),
                    int(bool(data.get("is_relevant", 1))),
                    int(bool(data.get("alert_sent", 0))),
                    data.get("raw_json"), created_at, updated_at,
                ),
            )
            return int(cursor.lastrowid)


def save_drive_file(data: Dict[str, Any]) -> None:
    created_at = now_iso()
    updated_at = now_iso()

    with get_conn() as conn:
        cursor = conn.cursor()
        _execute(cursor, "SELECT id FROM drive_files WHERE file_id = ?", (data["file_id"],))
        existing = _fetchone_dict(cursor)

        if existing:
            _execute(
                cursor,
                """
                UPDATE drive_files
                SET file_name = ?, mime_type = ?, modified_time = ?,
                    web_view_link = ?, processed = ?, updated_at = ?
                WHERE file_id = ?
                """,
                (
                    data.get("file_name"), data.get("mime_type"),
                    data.get("modified_time"), data.get("web_view_link"),
                    int(bool(data.get("processed", 0))), updated_at, data["file_id"],
                ),
            )
        else:
            _execute(
                cursor,
                """
                INSERT INTO drive_files (
                    file_id, file_name, mime_type, modified_time,
                    web_view_link, processed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["file_id"], data.get("file_name"), data.get("mime_type"),
                    data.get("modified_time"), data.get("web_view_link"),
                    int(bool(data.get("processed", 0))), created_at, updated_at,
                ),
            )


def mark_drive_file_processed(file_id: str) -> None:
    with get_conn() as conn:
        cursor = conn.cursor()
        _execute(
            cursor,
            "UPDATE drive_files SET processed = 1, updated_at = ? WHERE file_id = ?",
            (now_iso(), file_id),
        )


def mark_alert_sent(publication_id: int) -> None:
    with get_conn() as conn:
        cursor = conn.cursor()
        _execute(
            cursor,
            "UPDATE publications SET alert_sent = 1, updated_at = ? WHERE id = ?",
            (now_iso(), publication_id),
        )


# aliases legacy usados em alert.py
def marcar_email_enviado(publication_id: int) -> None:
    mark_alert_sent(publication_id)


def marcar_evento_calendario(publication_id: int) -> None:
    pass  # placeholder — implemente integração com Google Calendar se necessário


def buscar_publicacoes_pendentes_alerta(limit: int = 20) -> List[Dict[str, Any]]:
    return get_unalerted_publications(limit=limit)


def get_unalerted_publications(limit: int = 20) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor()
        _execute(
            cursor,
            """
            SELECT * FROM publications
            WHERE is_relevant = 1 AND alert_sent = 0
            ORDER BY publication_date DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return _fetchall_dict(cursor)


def get_recent_publications(limit: int = 50) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor()
        _execute(
            cursor,
            """
            SELECT * FROM publications
            ORDER BY publication_date DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return _fetchall_dict(cursor)


def get_publication_by_id(publication_id: int) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor()
        _execute(cursor, "SELECT * FROM publications WHERE id = ? LIMIT 1", (publication_id,))
        return _fetchone_dict(cursor)


def get_publication_by_external_id(source: str, external_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor()
        _execute(
            cursor,
            "SELECT * FROM publications WHERE source = ? AND external_id = ? LIMIT 1",
            (source, external_id),
        )
        return _fetchone_dict(cursor)


def get_unprocessed_drive_files(limit: int = 50) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        cursor = conn.cursor()
        _execute(
            cursor,
            """
            SELECT * FROM drive_files
            WHERE processed = 0
            ORDER BY modified_time DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return _fetchall_dict(cursor)


def _row_to_legacy_publicacao(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = _safe_json_load(row.get("raw_json"))
    legacy = _safe_json_load(raw.get("legacy"))

    processo = legacy.get("processo") or row.get("process_number") or ""
    data_publicacao = legacy.get("data_publicacao") or _iso_to_br(row.get("publication_date"))
    texto = legacy.get("texto") or row.get("content") or ""
    relevante = legacy.get("relevante")
    if relevante is None:
        relevante = bool(row.get("is_relevant", 0))

    motivo_filtro = legacy.get("motivo_filtro") or row.get("risk_level") or ""
    parte_autora = legacy.get("parte_autora") or ""
    parte_re = legacy.get("parte_re") or ""
    tribunal = legacy.get("tribunal") or ""
    resumo_ia = legacy.get("resumo_ia") or row.get("ai_summary") or ""
    o_que_fazer = legacy.get("o_que_fazer") or row.get("ai_action") or ""
    prazo = legacy.get("prazo") or row.get("deadline_date") or ""
    urgencia = legacy.get("urgencia") or row.get("risk_level") or ""
    enviado_email = legacy.get("enviado_email")
    if enviado_email is None:
        enviado_email = int(bool(row.get("alert_sent", 0)))

    hash_unico = legacy.get("hash_unico") or row.get("external_id") or ""
    fonte = legacy.get("fonte_legacy") or row.get("source") or ""

    return {
        "id": row.get("id"),
        "fonte": fonte,
        "processo": processo,
        "data_publicacao": data_publicacao,
        "texto": texto,
        "relevante": bool(relevante),
        "motivo_filtro": motivo_filtro,
        "parte_autora": parte_autora,
        "parte_re": parte_re,
        "tribunal": tribunal,
        "resumo_ia": resumo_ia,
        "o_que_fazer": o_que_fazer,
        "prazo": prazo,
        "urgencia": urgencia,
        "enviado_email": int(bool(enviado_email)),
        "hash_unico": hash_unico,
        "source": row.get("source"),
        "external_id": row.get("external_id"),
        "url": row.get("url"),
    }


def fetch_publicacoes(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        rows = get_recent_publications(limit=limit)
        return [_row_to_legacy_publicacao(row) for row in rows]
    except Exception:
        return []


def fetch_publicacoes_recentes(limit: int = 50) -> List[Dict[str, Any]]:
    return fetch_publicacoes(limit=limit)


def buscar_publicacoes(limit: int = 50) -> List[Dict[str, Any]]:
    return fetch_publicacoes(limit=limit)


def initialize_database() -> None:
    init_db()


def init_database() -> None:
    init_db()
