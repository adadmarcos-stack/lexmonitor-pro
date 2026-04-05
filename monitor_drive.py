import json
from typing import Dict, List

from db import (
    init_db,
    log_monitor,
    mark_drive_file_processed,
    save_drive_file,
    upsert_publication,
)
from drive_service import extract_text_from_file, list_recent_files
from process_ai import analyze_text


def _to_publication_record(file_meta: Dict, extracted_text: str, analysis: Dict) -> Dict:
    legacy_payload = {
        "processo": analysis.get("process_number", ""),
        "data_publicacao": file_meta.get("modifiedTime", ""),
        "texto": extracted_text,
        "relevante": bool(analysis.get("is_relevant", 1)),
        "motivo_filtro": analysis.get("risk_level", ""),
        "parte_autora": "",
        "parte_re": "",
        "tribunal": "GOOGLE DRIVE",
        "resumo_ia": analysis.get("ai_summary", ""),
        "o_que_fazer": analysis.get("ai_action", ""),
        "prazo": analysis.get("deadline_date", "") or "",
        "urgencia": analysis.get("risk_level", "") or "",
        "enviado_email": 0,
        "hash_unico": file_meta.get("id"),
        "fonte_legacy": "Google Drive",
    }

    return {
        "source": "google_drive",
        "external_id": file_meta.get("id"),
        "process_number": analysis.get("process_number"),
        "title": file_meta.get("name"),
        "content": extracted_text,
        "url": file_meta.get("webViewLink"),
        "publication_date": file_meta.get("modifiedTime"),
        "deadline_date": analysis.get("deadline_date"),
        "risk_level": analysis.get("risk_level"),
        "ai_summary": analysis.get("ai_summary"),
        "ai_action": analysis.get("ai_action"),
        "ai_tags": analysis.get("ai_tags"),
        "is_relevant": analysis.get("is_relevant", 1),
        "alert_sent": 0,
        "raw_json": json.dumps(
            {
                "legacy": legacy_payload,
                "file_meta": file_meta,
                "analysis": analysis,
            },
            ensure_ascii=False,
        ),
    }


def monitor_drive_once(page_size: int = 20) -> List[Dict]:
    init_db()
    processed_items = []

    try:
        files = list_recent_files(page_size=page_size)
        log_monitor("monitor_drive", "success", f"{len(files)} arquivo(s) localizado(s) no Drive.")
    except Exception as e:
        log_monitor("monitor_drive", "error", f"Erro ao listar arquivos do Drive: {e}")
        raise

    for file_meta in files:
        file_id = file_meta.get("id")
        file_name = file_meta.get("name", "")
        mime_type = file_meta.get("mimeType", "")

        save_drive_file(
            {
                "file_id": file_id,
                "file_name": file_name,
                "mime_type": mime_type,
                "modified_time": file_meta.get("modifiedTime"),
                "web_view_link": file_meta.get("webViewLink"),
                "processed": 0,
            }
        )

        try:
            extracted_text = extract_text_from_file(file_id, mime_type)
            if not extracted_text.strip():
                log_monitor(
                    "monitor_drive",
                    "warning",
                    f"Arquivo sem texto extraível: {file_name} ({file_id})",
                )
                mark_drive_file_processed(file_id)
                continue

            analysis = analyze_text(
                text=extracted_text,
                title=file_name,
                source="google_drive",
            )

            publication = _to_publication_record(file_meta, extracted_text, analysis)
            publication_id = upsert_publication(publication)
            mark_drive_file_processed(file_id)

            processed_items.append(
                {
                    "publication_id": publication_id,
                    "file_id": file_id,
                    "file_name": file_name,
                    "risk_level": analysis.get("risk_level"),
                    "is_relevant": analysis.get("is_relevant", 1),
                }
            )

        except Exception as e:
            log_monitor(
                "monitor_drive",
                "error",
                f"Erro ao processar arquivo {file_name} ({file_id}): {e}",
            )

    return processed_items


def run_monitor() -> List[Dict]:
    return monitor_drive_once()


if __name__ == "__main__":
    items = monitor_drive_once()
    print(f"Processados no Drive: {len(items)}")
    for item in items:
        print(item)
