from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def agora() -> datetime:
    return datetime.now(timezone.utc)


class Funcionario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    matricula: str = Field(index=True, unique=True)
    ativo: bool = True


class Local(SQLModel, table=True):
    """Área onde o ponto é permitido (centro + raio)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    latitude: float
    longitude: float
    raio_metros: float = 150


class Registro(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    funcionario_id: int = Field(foreign_key="funcionario.id", index=True)
    tipo: str  # "entrada" | "saida"
    data_hora: datetime = Field(default_factory=agora, index=True)
    latitude: float
    longitude: float
    precisao_metros: float
    local_id: Optional[int] = Field(default=None, foreign_key="local.id")
    distancia_metros: Optional[float] = None
    aceito: bool
    motivo: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None
