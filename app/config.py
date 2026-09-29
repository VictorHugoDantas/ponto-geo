import os
import secrets
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(RAIZ / 'ponto.db').as_posix()}")
# Sem ADMIN_TOKEN definido, um token aleatório é gerado a cada inicialização e exibido no console.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN") or secrets.token_urlsafe(24)
ADMIN_TOKEN_GERADO = not os.getenv("ADMIN_TOKEN")
# Só confie no cabeçalho X-Forwarded-For quando o app estiver atrás de um proxy reverso.
CONFIAR_PROXY = os.getenv("CONFIAR_PROXY", "false").lower() == "true"
# Precisão mínima exigida do GPS (em metros). Leituras piores são recusadas.
PRECISAO_MAXIMA_M = float(os.getenv("PRECISAO_MAXIMA_M", "100"))
# Fuso usado para definir o "dia" (alternância entrada/saída e filtros).
FUSO_HORARIO = os.getenv("FUSO_HORARIO", "America/Sao_Paulo")
