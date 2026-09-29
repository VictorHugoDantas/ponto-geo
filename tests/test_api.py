from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app import config
from app.database import get_session
from app.main import app
from app.models import Registro

ADMIN = {"X-Admin-Token": config.ADMIN_TOKEN}
SEDE = {"nome": "Sede", "latitude": -15.7939, "longitude": -47.8828, "raio_metros": 150}


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(engine):
    def sessao_teste():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = sessao_teste
    with TestClient(app) as c:
        c.post("/api/funcionarios", json={"nome": "Ana", "matricula": "1001"}, headers=ADMIN)
        c.post("/api/locais", json=SEDE, headers=ADMIN)
        yield c
    app.dependency_overrides.clear()


def ponto(client, lat=-15.7939, lon=-47.8828, precisao=10, matricula="1001"):
    return client.post("/api/ponto", json={
        "matricula": matricula, "latitude": lat, "longitude": lon, "precisao": precisao,
    })


def envelhecer_registros(engine, minutos=5):
    """Simula passagem de tempo para contornar o intervalo mínimo entre pontos."""
    with Session(engine) as s:
        for r in s.exec(select(Registro)).all():
            r.data_hora -= timedelta(minutes=minutos)
            s.add(r)
        s.commit()


def test_ponto_dentro_da_area(client):
    r = ponto(client)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["aceito"] is True
    assert corpo["tipo"] == "entrada"
    assert corpo["funcionario"] == "Ana"


def test_ponto_fora_da_area(client):
    r = ponto(client, lat=-15.80, lon=-47.89)  # ~1 km de distância
    corpo = r.json()
    assert corpo["aceito"] is False
    assert "Fora da área" in corpo["motivo"]


def test_precisao_ruim_e_recusada(client):
    corpo = ponto(client, precisao=500).json()
    assert corpo["aceito"] is False
    assert "Precisão" in corpo["motivo"]


def test_matricula_inexistente(client):
    assert ponto(client, matricula="9999").status_code == 404


def test_alterna_entrada_e_saida(client, engine):
    assert ponto(client).json()["tipo"] == "entrada"
    envelhecer_registros(engine)
    assert ponto(client).json()["tipo"] == "saida"
    envelhecer_registros(engine)
    assert ponto(client).json()["tipo"] == "entrada"


def test_bloqueia_ponto_duplicado(client):
    assert ponto(client).status_code == 200
    assert ponto(client).status_code == 429


def test_registro_guarda_ip_e_coordenadas(client):
    ponto(client)
    registros = client.get("/api/registros", headers=ADMIN).json()
    assert len(registros) == 1
    reg = registros[0]
    assert reg["ip"] == "testclient"
    assert reg["latitude"] == -15.7939
    assert reg["matricula"] == "1001"


def test_rotas_admin_exigem_token(client):
    assert client.get("/api/registros").status_code == 401
    assert client.post("/api/locais", json=SEDE).status_code == 401


def test_exporta_csv(client):
    ponto(client)
    r = client.get("/api/registros.csv", headers=ADMIN)
    assert r.status_code == 200
    linhas = r.text.strip().splitlines()
    assert linhas[0].startswith("data_hora,nome,matricula")
    assert len(linhas) == 2


def test_matricula_duplicada(client):
    r = client.post("/api/funcionarios", json={"nome": "Outra", "matricula": "1001"}, headers=ADMIN)
    assert r.status_code == 409


# ---------- Validação de entrada (422) ----------

@pytest.mark.parametrize("payload", [
    {"matricula": "1001", "latitude": 91, "longitude": 0, "precisao": 10},
    {"matricula": "1001", "latitude": -91, "longitude": 0, "precisao": 10},
    {"matricula": "1001", "latitude": 0, "longitude": 181, "precisao": 10},
    {"matricula": "1001", "latitude": 0, "longitude": -181, "precisao": 10},
    {"matricula": "1001", "latitude": 0, "longitude": 0, "precisao": -1},
    {"matricula": "", "latitude": 0, "longitude": 0, "precisao": 10},
    {"matricula": "1001", "latitude": "abc", "longitude": 0, "precisao": 10},
    {"matricula": "1001", "longitude": 0, "precisao": 10},
    {},
])
def test_payload_invalido(client, payload):
    assert client.post("/api/ponto", json=payload).status_code == 422
    assert client.get("/api/registros", headers=ADMIN).json() == []


@pytest.mark.parametrize("local", [
    {**SEDE, "raio_metros": 0},
    {**SEDE, "raio_metros": 20_000},
    {**SEDE, "latitude": 100},
    {**SEDE, "nome": ""},
])
def test_local_invalido(client, local):
    assert client.post("/api/locais", json=local, headers=ADMIN).status_code == 422


# ---------- Regras de negócio ----------

def test_funcionario_inativo(client, engine):
    from app.models import Funcionario
    with Session(engine) as s:
        f = s.exec(select(Funcionario)).first()
        f.ativo = False
        s.add(f)
        s.commit()
    assert ponto(client).status_code == 404


def test_sem_locais_cadastrados(client):
    local_id = client.get("/api/locais").json()[0]["id"]
    assert client.delete(f"/api/locais/{local_id}", headers=ADMIN).status_code == 204
    corpo = ponto(client).json()
    assert corpo["aceito"] is False
    assert "Nenhum local" in corpo["motivo"]


def test_borda_do_raio(client, engine):
    # raio da sede = 150 m; 0,0013° de latitude ≈ 145 m e 0,0014° ≈ 156 m
    assert ponto(client, lat=-15.7939 + 0.0013).json()["aceito"] is True
    envelhecer_registros(engine)
    corpo = ponto(client, lat=-15.7939 + 0.0014).json()
    assert corpo["aceito"] is False
    assert corpo["distancia_metros"] == pytest.approx(156, abs=1)


def test_borda_da_precisao(client, engine):
    assert ponto(client, precisao=config.PRECISAO_MAXIMA_M).json()["aceito"] is True
    envelhecer_registros(engine)
    assert ponto(client, precisao=config.PRECISAO_MAXIMA_M + 0.1).json()["aceito"] is False


def test_valida_contra_local_mais_proximo(client):
    filial = {"nome": "Filial", "latitude": -23.5505, "longitude": -46.6333, "raio_metros": 150}
    client.post("/api/locais", json=filial, headers=ADMIN)
    corpo = ponto(client, lat=-23.5506, lon=-46.6334).json()
    assert corpo["aceito"] is True
    assert "Filial" in corpo["motivo"]


def test_recusado_nao_bloqueia_nem_alterna(client):
    assert ponto(client, lat=-15.80).json()["aceito"] is False
    corpo = ponto(client).json()  # logo em seguida, dentro da área
    assert corpo["aceito"] is True
    assert corpo["tipo"] == "entrada"


def test_virada_do_dia_reinicia_como_entrada(client, engine):
    assert ponto(client).json()["tipo"] == "entrada"
    envelhecer_registros(engine, minutos=60 * 25)
    assert ponto(client).json()["tipo"] == "entrada"


def test_inicio_do_dia_usa_fuso_de_brasilia():
    from datetime import date, datetime, timezone
    from app.main import inicio_do_dia
    assert inicio_do_dia(date(2026, 9, 29)) == datetime(2026, 9, 29, 3, tzinfo=timezone.utc)


def test_ip_via_proxy_so_quando_configurado(client, monkeypatch):
    cabecalho = {"X-Forwarded-For": "200.1.2.3, 10.0.0.1"}
    corpo = {"matricula": "1001", "latitude": -15.7939, "longitude": -47.8828, "precisao": 10}

    # Sem CONFIAR_PROXY o cabeçalho é ignorado (evita IP forjado)
    client.post("/api/ponto", headers=cabecalho, json=corpo)
    assert client.get("/api/registros", headers=ADMIN).json()[0]["ip"] == "testclient"


def test_ip_via_proxy(client, monkeypatch):
    monkeypatch.setattr(config, "CONFIAR_PROXY", True)
    client.post("/api/ponto", headers={"X-Forwarded-For": "200.1.2.3, 10.0.0.1"}, json={
        "matricula": "1001", "latitude": -15.7939, "longitude": -47.8828, "precisao": 10,
    })
    assert client.get("/api/registros", headers=ADMIN).json()[0]["ip"] == "200.1.2.3"


# ---------- Admin ----------

def test_token_errado(client):
    assert client.get("/api/registros", headers={"X-Admin-Token": "errado"}).status_code == 401
    assert client.get("/api/registros.csv").status_code == 401
    assert client.get("/api/funcionarios").status_code == 401
    assert client.delete("/api/locais/1").status_code == 401


def test_remover_local_inexistente(client):
    assert client.delete("/api/locais/999", headers=ADMIN).status_code == 404


def test_filtros_de_registros(client):
    from datetime import date
    client.post("/api/funcionarios", json={"nome": "Bruno", "matricula": "1002"}, headers=ADMIN)
    ponto(client)
    ponto(client, matricula="1002")
    assert len(client.get("/api/registros", headers=ADMIN).json()) == 2
    so_bruno = client.get("/api/registros?matricula=1002", headers=ADMIN).json()
    assert [r["nome"] for r in so_bruno] == ["Bruno"]
    hoje = date.today().isoformat()
    assert len(client.get(f"/api/registros?dia={hoje}", headers=ADMIN).json()) == 2
    assert client.get("/api/registros?dia=2000-01-01", headers=ADMIN).json() == []
    assert client.get("/api/registros?dia=invalido", headers=ADMIN).status_code == 422


def test_paginas_e_estaticos(client):
    for caminho in ["/", "/admin", "/static/app.js", "/static/admin.js", "/static/style.css", "/docs"]:
        assert client.get(caminho).status_code == 200


def test_csv_neutraliza_formulas(client):
    client.post("/api/funcionarios", json={"nome": "=HYPERLINK(\"http://x\")", "matricula": "666"}, headers=ADMIN)
    ponto(client, matricula="666")
    linha = client.get("/api/registros.csv", headers=ADMIN).text.splitlines()[1]
    assert "'=HYPERLINK" in linha


def test_cabecalhos_de_seguranca(client):
    r = client.get("/admin")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_nome_muito_longo(client):
    r = client.post("/api/funcionarios", json={"nome": "a" * 121, "matricula": "9"}, headers=ADMIN)
    assert r.status_code == 422
