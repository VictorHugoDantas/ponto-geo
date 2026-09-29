# Ponto Geo 📍

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white)
![Leaflet](https://img.shields.io/badge/Leaflet-OpenStreetMap-199900?logo=leaflet&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-non--root-2496ED?logo=docker&logoColor=white)
![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=white)
![Tests](https://img.shields.io/badge/tests-45%20passing-brightgreen?logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

Sistema de **registro de ponto com validação por georreferenciamento (geofencing)**. Quando o funcionário bate o ponto pelo navegador, o sistema captura a localização do aparelho (GPS/Wi‑Fi) e verifica, pela **fórmula de Haversine**, se ele está dentro do raio de um local de trabalho cadastrado. Todo registro, aceito ou recusado, é armazenado com coordenadas, distância, precisão, IP e navegador para fins de auditoria.

## 🔗 Demo

| | Link |
|---|---|
| **Bater ponto** | [https://ponto-geo.onrender.com](https://ponto-geo.onrender.com) |
| **Painel admin** | [https://ponto-geo.onrender.com/admin](https://ponto-geo.onrender.com/admin) |
| **Documentação da API** | [https://ponto-geo.onrender.com/docs](https://ponto-geo.onrender.com/docs) |

> Hospedado no plano gratuito do Render: o primeiro acesso após um período de inatividade pode levar alguns segundos para responder.

## ✨ Funcionalidades

- **Bater ponto com um clique**: entrada e saída se alternam automaticamente ao longo do dia
- **Geofencing**: o ponto só é aceito dentro da área permitida (centro + raio, padrão de 150 m)
- **Controle de precisão**: leituras de GPS acima de 100 m de imprecisão são recusadas
- **Trava de duplicidade**: bloqueia um novo ponto em menos de 60 segundos
- **Mapa interativo** com a posição do usuário e as áreas permitidas
- **Painel administrativo** protegido por token:
  - cadastro de funcionários
  - cadastro de locais clicando no mapa
  - consulta de registros com filtros por dia e matrícula
  - exportação em CSV
- **API REST** documentada automaticamente (Swagger em `/docs`)

## 🏗️ Arquitetura

```
┌──────────────────────┐        HTTPS         ┌──────────────────────────┐        ┌──────────────────┐
│      Navegador       │ ───────────────────► │   FastAPI (Render/Docker) │ ─────► │ PostgreSQL (Neon)│
│ navigator.geolocation│  POST /api/ponto     │                          │        └──────────────────┘
│ Leaflet + OSM        │  {matricula, lat,    │  1. matrícula ativa?     │
└──────────────────────┘   lon, precisao}     │  2. ponto há < 60 s?     │
                                              │  3. precisão ≤ 100 m?    │
                                              │  4. Haversine → local    │
                                              │     mais próximo         │
                                              │  5. distância ≤ raio?    │
                                              │  6. grava registro       │
                                              │     (aceito/recusado +   │
                                              │      IP + user-agent)    │
                                              └──────────────────────────┘
```

A localização vem da **API de Geolocalização do navegador**, e não do endereço IP. A geolocalização por IP indica apenas a cidade ou o provedor, com erro de quilômetros, por isso o IP é armazenado somente como dado auxiliar de auditoria.

## 🧠 Regras de negócio e engenharia

| Regra | Implementação |
|---|---|
| **Geofencing** | Distância calculada pela fórmula de Haversine até o local cadastrado mais próximo; aceito se estiver dentro do raio (padrão de 150 m, configurável por local) |
| **Precisão do GPS** | Leituras com imprecisão acima de `PRECISAO_MAXIMA_M` (padrão de 100 m) são recusadas |
| **Trava de duplicidade** | Novo ponto em menos de 60 s após o último aceito retorna `429` |
| **Entrada/saída** | Alternância automática dentro do mesmo dia; o primeiro ponto do dia é sempre uma entrada |
| **Fuso horário** | Datas armazenadas em UTC; o "dia" é calculado em `America/Sao_Paulo` |
| **IP real** | Lido de `X-Forwarded-For` quando `CONFIAR_PROXY=true` (atrás do proxy do Render); caso contrário, o cabeçalho é ignorado para impedir IP forjado |
| **Auditoria** | Pontos recusados também são gravados, com o motivo da recusa, sem afetar a alternância nem a trava |

## 🔒 Segurança

- Token de admin sem valor fixo no código, comparado em tempo constante (`secrets.compare_digest`)
- Sanitização contra **CSV Injection** na exportação (células iniciadas por `=`, `+`, `-`, `@` são neutralizadas)
- Cabeçalhos `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Permissions-Policy` e `Referrer-Policy: strict-origin-when-cross-origin` (compatível com a política de uso de tiles do OpenStreetMap)
- Escape de todo conteúdo exibido no painel (proteção contra XSS)
- Validação de todas as entradas com Pydantic (faixas de coordenadas, tamanhos de texto)
- Container Docker executado com usuário **não-root**

## 🛠️ Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLModel (SQLAlchemy + Pydantic) |
| Banco de dados | PostgreSQL (Neon Cloud) em produção, SQLite em desenvolvimento |
| Frontend | HTML, CSS e JavaScript puro, Leaflet.js + OpenStreetMap |
| Infraestrutura | Docker (usuário não-root), Render PaaS |
| Testes | pytest + TestClient (45 testes) |

## 📁 Estrutura

```
ponto-geo/
├── app/
│   ├── main.py        # rotas, regras de negócio e middlewares de segurança
│   ├── geo.py         # fórmula de Haversine e busca do local mais próximo
│   ├── models.py      # tabelas Funcionario, Local e Registro
│   ├── database.py    # engine e sessão do banco
│   ├── config.py      # variáveis de ambiente
│   └── static/        # páginas de ponto e admin (HTML, CSS, JS)
├── tests/             # testes de geolocalização e da API
├── seed.py            # dados de demonstração
├── Dockerfile
└── requirements.txt
```

## ⚙️ Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `DATABASE_URL` | SQLite `ponto.db` na raiz | URL do banco. Em produção: `postgresql://usuario:senha@host/banco?sslmode=require` |
| `ADMIN_TOKEN` | aleatório a cada inicialização | Token do painel administrativo. **Obrigatório definir em produção** |
| `CONFIAR_PROXY` | `false` | `true` para ler o IP real de `X-Forwarded-For` (use apenas atrás de proxy reverso) |
| `PRECISAO_MAXIMA_M` | `100` | Imprecisão máxima aceita do GPS, em metros |
| `FUSO_HORARIO` | `America/Sao_Paulo` | Fuso usado para definir o "dia" |

## 🌐 Endpoints

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| `GET` | `/` | público | Página de bater ponto |
| `GET` | `/admin` | público | Painel administrativo (login por token) |
| `POST` | `/api/ponto` | público | Registra ponto com coordenadas |
| `GET` | `/api/locais` | público | Lista áreas permitidas |
| `POST` | `/api/locais` | admin | Cadastra local |
| `DELETE` | `/api/locais/{id}` | admin | Remove local |
| `GET` | `/api/funcionarios` | admin | Lista funcionários |
| `POST` | `/api/funcionarios` | admin | Cadastra funcionário |
| `GET` | `/api/registros` | admin | Lista registros (`?dia=AAAA-MM-DD&matricula=`) |
| `GET` | `/api/registros.csv` | admin | Exporta registros em CSV |

Rotas admin exigem o cabeçalho `X-Admin-Token`.

## 💻 Execução local

```bash
git clone https://github.com/VictorHugoDantas/ponto-geo.git
cd ponto-geo
python -m venv .venv
```

```bash
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

```bash
pip install -r requirements-dev.txt
python seed.py -15.7939 -47.8828
uvicorn app.main:app --reload
```

- Bater ponto: http://localhost:8000
- Painel admin: http://localhost:8000/admin (o token temporário aparece no console)
- Documentação: http://localhost:8000/docs

> O navegador só libera a geolocalização em **HTTPS** ou em `localhost`.

### Testes

```bash
pytest
```

## 🐳 Docker

```bash
docker build -t ponto-geo .
docker run -p 8000:8000 \
  -e ADMIN_TOKEN=um-token-longo-e-aleatorio \
  -e DATABASE_URL=postgresql://usuario:senha@host/banco?sslmode=require \
  -e CONFIAR_PROXY=true \
  ponto-geo
```

## ⚠️ Limitações conhecidas

- A localização é informada pelo navegador; ferramentas de GPS falso podem burlar a validação. Mitigações possíveis: app nativo com detecção de *mock location*, selfie no registro ou validação pela rede Wi‑Fi da empresa.
- A identificação do funcionário é feita apenas pela matrícula.

## 🚀 Próximos passos

- [ ] Autenticação de funcionários com JWT
- [ ] Relatório de horas trabalhadas por período
- [ ] PWA para instalação no celular

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE).
