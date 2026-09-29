import csv
import io
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from . import config
from .database import criar_tabelas, get_session
from .geo import local_mais_proximo
from .models import Funcionario, Local, Registro

STATIC = Path(__file__).parent / "static"
INTERVALO_MINIMO = timedelta(minutes=1)
FUSO = ZoneInfo(config.FUSO_HORARIO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    criar_tabelas()
    if config.ADMIN_TOKEN_GERADO:
        print(f"ADMIN_TOKEN não definido. Token temporário do painel: {config.ADMIN_TOKEN}")
    yield


app = FastAPI(title="Ponto Geo", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def cabecalhos_seguranca(request: Request, call_next):
    resposta = await call_next(request)
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Referrer-Policy"] = "same-origin"
    resposta.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
    return resposta


# ---------- Schemas de entrada ----------

class BaterPonto(BaseModel):
    matricula: str = Field(min_length=1, max_length=50)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    precisao: float = Field(ge=0, description="Precisão informada pelo GPS, em metros")


class NovoFuncionario(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    matricula: str = Field(min_length=1, max_length=50)


class NovoLocal(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    raio_metros: float = Field(default=150, gt=0, le=10_000)


# ---------- Helpers ----------

def exigir_admin(x_admin_token: str = Header(default="")) -> None:
    if not secrets.compare_digest(x_admin_token.encode(), config.ADMIN_TOKEN.encode()):
        raise HTTPException(401, "Token de administrador inválido")


def ip_cliente(request: Request) -> Optional[str]:
    encaminhado = request.headers.get("x-forwarded-for")
    if config.CONFIAR_PROXY and encaminhado:
        return encaminhado.split(",")[0].strip()
    return request.client.host if request.client else None


def inicio_do_dia(dia: Optional[date] = None) -> datetime:
    """Meia-noite (no fuso configurado) do dia informado ou de hoje, em UTC."""
    dia = dia or datetime.now(FUSO).date()
    return datetime(dia.year, dia.month, dia.day, tzinfo=FUSO).astimezone(timezone.utc)


def como_utc(dt: datetime) -> datetime:
    # SQLite devolve datetimes sem fuso; os valores são sempre gravados em UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------- Páginas ----------

@app.get("/", include_in_schema=False)
def pagina_ponto():
    return FileResponse(STATIC / "index.html")


@app.get("/admin", include_in_schema=False)
def pagina_admin():
    return FileResponse(STATIC / "admin.html")


# ---------- API pública ----------

@app.get("/api/locais")
def listar_locais(session: Session = Depends(get_session)):
    return session.exec(select(Local)).all()


@app.post("/api/ponto")
def bater_ponto(dados: BaterPonto, request: Request, session: Session = Depends(get_session)):
    funcionario = session.exec(
        select(Funcionario).where(Funcionario.matricula == dados.matricula)
    ).first()
    if not funcionario or not funcionario.ativo:
        raise HTTPException(404, "Matrícula não encontrada ou inativa")

    ultimo = session.exec(
        select(Registro)
        .where(Registro.funcionario_id == funcionario.id, Registro.aceito == True)  # noqa: E712
        .order_by(Registro.data_hora.desc())
    ).first()
    agora = datetime.now(timezone.utc)
    if ultimo and agora - como_utc(ultimo.data_hora) < INTERVALO_MINIMO:
        raise HTTPException(429, "Ponto já registrado há menos de 1 minuto")

    # Entrada/saída alternam dentro do mesmo dia.
    ultimo_hoje = ultimo if ultimo and como_utc(ultimo.data_hora) >= inicio_do_dia() else None
    tipo = "saida" if ultimo_hoje and ultimo_hoje.tipo == "entrada" else "entrada"

    locais = session.exec(select(Local)).all()
    local, distancia = local_mais_proximo(dados.latitude, dados.longitude, locais)

    if dados.precisao > config.PRECISAO_MAXIMA_M:
        aceito, motivo = False, f"Precisão do GPS insuficiente ({dados.precisao:.0f} m)"
    elif local is None:
        aceito, motivo = False, "Nenhum local de trabalho cadastrado"
    elif distancia > local.raio_metros:
        aceito, motivo = False, f"Fora da área permitida: {distancia:.0f} m de {local.nome}"
    else:
        aceito, motivo = True, f"Dentro da área de {local.nome}"

    registro = Registro(
        funcionario_id=funcionario.id,
        tipo=tipo,
        data_hora=agora,
        latitude=dados.latitude,
        longitude=dados.longitude,
        precisao_metros=dados.precisao,
        local_id=local.id if local else None,
        distancia_metros=round(distancia, 1) if distancia is not None else None,
        aceito=aceito,
        motivo=motivo,
        ip=ip_cliente(request),
        user_agent=request.headers.get("user-agent"),
    )
    session.add(registro)
    session.commit()
    session.refresh(registro)

    return {
        "aceito": aceito,
        "tipo": tipo,
        "motivo": motivo,
        "funcionario": funcionario.nome,
        "data_hora": agora,
        "distancia_metros": registro.distancia_metros,
    }


# ---------- API administrativa ----------

admin = [Depends(exigir_admin)]


@app.get("/api/funcionarios", dependencies=admin)
def listar_funcionarios(session: Session = Depends(get_session)):
    return session.exec(select(Funcionario).order_by(Funcionario.nome)).all()


@app.post("/api/funcionarios", dependencies=admin, status_code=201)
def criar_funcionario(dados: NovoFuncionario, session: Session = Depends(get_session)):
    if session.exec(select(Funcionario).where(Funcionario.matricula == dados.matricula)).first():
        raise HTTPException(409, "Matrícula já cadastrada")
    funcionario = Funcionario(**dados.model_dump())
    session.add(funcionario)
    session.commit()
    session.refresh(funcionario)
    return funcionario


@app.post("/api/locais", dependencies=admin, status_code=201)
def criar_local(dados: NovoLocal, session: Session = Depends(get_session)):
    local = Local(**dados.model_dump())
    session.add(local)
    session.commit()
    session.refresh(local)
    return local


@app.delete("/api/locais/{local_id}", dependencies=admin, status_code=204)
def remover_local(local_id: int, session: Session = Depends(get_session)):
    local = session.get(Local, local_id)
    if not local:
        raise HTTPException(404, "Local não encontrado")
    session.delete(local)
    session.commit()


def consultar_registros(session: Session, dia: Optional[date], matricula: Optional[str]):
    consulta = (
        select(Registro, Funcionario)
        .join(Funcionario, Registro.funcionario_id == Funcionario.id)
        .order_by(Registro.data_hora.desc())
    )
    if dia:
        inicio = inicio_do_dia(dia)
        consulta = consulta.where(Registro.data_hora >= inicio, Registro.data_hora < inicio + timedelta(days=1))
    if matricula:
        consulta = consulta.where(Funcionario.matricula == matricula)
    return [
        {**registro.model_dump(), "nome": f.nome, "matricula": f.matricula}
        for registro, f in session.exec(consulta).all()
    ]


@app.get("/api/registros", dependencies=admin)
def listar_registros(
    dia: Optional[date] = None,
    matricula: Optional[str] = None,
    session: Session = Depends(get_session),
):
    return consultar_registros(session, dia, matricula)


def celula_segura(valor):
    """Evita injeção de fórmulas ao abrir o CSV no Excel/Sheets."""
    if isinstance(valor, str) and valor.startswith(("=", "+", "-", "@", chr(9), chr(13))):
        return "'" + valor
    return valor


@app.get("/api/registros.csv", dependencies=admin)
def exportar_csv(
    dia: Optional[date] = None,
    matricula: Optional[str] = None,
    session: Session = Depends(get_session),
):
    linhas = consultar_registros(session, dia, matricula)
    buffer = io.StringIO()
    campos = ["data_hora", "nome", "matricula", "tipo", "aceito", "motivo",
              "latitude", "longitude", "precisao_metros", "distancia_metros", "ip"]
    writer = csv.DictWriter(buffer, fieldnames=campos, extrasaction="ignore")
    writer.writeheader()
    writer.writerows({k: celula_segura(v) for k, v in linha.items()} for linha in linhas)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=registros.csv"},
    )
