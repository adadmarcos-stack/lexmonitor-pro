from fastapi import APIRouter
from app.services.oabmg_service import consultar_publicacoes
from app.services.monitor_oab_novo import monitorar_publicacoes_oab

router = APIRouter()


@router.get("/oab/publicacoes")
def get_publicacoes():
    try:
        return consultar_publicacoes()
    except Exception as e:
        return {
            "ok": False,
            "erro": str(e)
        }


@router.get("/oab/monitorar")
def monitorar_oab():
    try:
        return monitorar_publicacoes_oab()
    except Exception as e:
        return {
            "ok": False,
            "erro": str(e)
        }