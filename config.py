import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_FILE = DATA_DIR / "publicacoes.db"
LOG_FILE = DATA_DIR / "log.txt"
PAGINA_FILE = DATA_DIR / "pagina.txt"
EXTRAIDAS_FILE = DATA_DIR / "publicacoes_extraidas.txt"

EMAIL = os.getenv("EMAIL", "adadjammmal@gmail.com")
SENHA_APP = os.getenv("SENHA_APP", "COLE_SUA_SENHA_DE_APP_AQUI")

OAB = os.getenv("OAB", "113674")
CPF = os.getenv("CPF", "06819623640")
RG = os.getenv("RG", "12989116")
UF = os.getenv("UF", "MG")

MAX_PAGINAS = int(os.getenv("MAX_PAGINAS", "10"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
