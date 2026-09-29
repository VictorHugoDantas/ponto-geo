# Ponto Geo 📍

Sistema de **registro de ponto com validação por georreferenciamento**. Quando o funcionário bate o ponto pelo navegador, o sistema captura a localização do aparelho (GPS/Wi‑Fi) e verifica, pela **fórmula de Haversine**, se ele está dentro do raio de algum local de trabalho cadastrado. Todo registro, aceito ou recusado, é salvo com coordenadas, distância, precisão, IP e navegador, para auditoria.

> Projeto de extensão desenvolvido por conta própria com Python + FastAPI.

## Funcionalidades

- **Bater ponto** com um clique: entrada e saída se alternam automaticamente ao longo do dia
- **Validação geográfica**: o ponto é aceito só dentro da área permitida (centro + raio em metros)
- **Controle de precisão**: leituras de GPS imprecisas (acima de 100 m, configurável) são recusadas
- **Proteção contra duplicidade**: bloqueia dois pontos em menos de 1 minuto
- **Mapa interativo** (Leaflet + OpenStreetMap) com a posição do usuário e as áreas permitidas
- **Painel administrativo** protegido por token:
  - cadastro de funcionários
  - cadastro de locais clicando no mapa
  - consulta de registros com filtro por dia e matrícula
  - exportação em **CSV**
- **API REST documentada** automaticamente em `/docs` (Swagger)
- **Testes automatizados** com pytest

## Como funciona

```
Navegador                         Servidor (FastAPI)
─────────                         ──────────────────
navigator.geolocation  ──►  POST /api/ponto {matricula, lat, lon, precisão}
                                  │
                                  ├─ matrícula existe e está ativa?
                                  ├─ precisão do GPS ≤ limite?
                                  ├─ Haversine → local mais próximo
                                  ├─ distância ≤ raio do local?
                                  └─ salva registro (aceito/recusado + IP + user‑agent)
```

A localização vem da **API de Geolocalização do navegador**, e não do IP. A geolocalização por IP só indica a cidade ou o provedor, com erro de quilômetros, então o IP é guardado apenas como dado auxiliar de auditoria.

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLModel (SQLAlchemy + Pydantic) |
| Banco | SQLite (troca para PostgreSQL via `DATABASE_URL`) |
| Frontend | HTML, CSS e JavaScript puro, Leaflet |
| Testes | pytest + TestClient |

## Rodando localmente

```bash
git clone https://github.com/VictorHugoDantas/ponto-geo.git
cd ponto-geo
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt

# cria funcionário demo (matrícula 1001) e um local; passe SUAS coordenadas para testar
python seed.py -15.7939 -47.8828

uvicorn app.main:app --reload
```

- Bater ponto: http://localhost:8000
- Painel admin: http://localhost:8000/admin (use o `ADMIN_TOKEN` definido; se não definir, um token temporário aparece no console ao iniciar)
- Documentação da API: http://localhost:8000/docs

> O navegador só libera a geolocalização em **HTTPS** ou em `localhost`. Para testar pelo celular, publique o projeto (veja abaixo) ou use um túnel como `ngrok http 8000`.

### Configuração

Variáveis de ambiente (veja `.env.example`):

| Variável | Padrão | Descrição |
|---|---|---|
| `ADMIN_TOKEN` | aleatório a cada início | Token do painel administrativo. **Defina um valor longo em produção.** |
| `DATABASE_URL` | `ponto.db` na raiz do projeto | URL do banco |
| `PRECISAO_MAXIMA_M` | `100` | Precisão máxima aceita do GPS, em metros |
| `FUSO_HORARIO` | `America/Sao_Paulo` | Fuso usado para definir o "dia" |
| `CONFIAR_PROXY` | `false` | Use `true` só atrás de proxy reverso (Render, Railway, Nginx) para registrar o IP real via `X-Forwarded-For` |

## Testes

```bash
pytest
```

## Docker / Deploy

```bash
docker build -t ponto-geo .
docker run -p 8000:8000 -e ADMIN_TOKEN=um-token-forte -e CONFIAR_PROXY=true ponto-geo
```

O projeto sobe direto em serviços como Render, Railway ou Fly.io. Todos fornecem HTTPS, que é necessário para a geolocalização funcionar.

## Endpoints

| Método | Rota | Acesso | Descrição |
|---|---|---|---|
| `POST` | `/api/ponto` | público | Registra ponto com coordenadas |
| `GET` | `/api/locais` | público | Lista áreas permitidas |
| `POST` | `/api/locais` | admin | Cadastra local |
| `DELETE` | `/api/locais/{id}` | admin | Remove local |
| `GET` / `POST` | `/api/funcionarios` | admin | Lista / cadastra funcionários |
| `GET` | `/api/registros` | admin | Lista registros (`?dia=AAAA-MM-DD&matricula=`) |
| `GET` | `/api/registros.csv` | admin | Exporta registros em CSV |

Rotas admin exigem o cabeçalho `X-Admin-Token`.

## Segurança

- Token de admin nunca tem valor fixo no código e é comparado em tempo constante
- IP de auditoria só usa `X-Forwarded-For` quando `CONFIAR_PROXY=true`, evitando IP forjado
- Exportação CSV neutraliza fórmulas (proteção contra *CSV injection*)
- Cabeçalhos `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` e `Permissions-Policy`
- Todo conteúdo exibido no painel é escapado (proteção contra XSS)
- Validação de todos os dados de entrada (faixas de coordenadas, tamanhos de texto)
- Container Docker roda com usuário sem privilégios de root

## Limitações conhecidas

- A localização é informada pelo navegador, então um usuário com ferramentas de GPS falso consegue burlar a validação. Mitigações possíveis: app nativo com detecção de mock location, foto/selfie no registro, validação por rede Wi‑Fi da empresa.
- A identificação é só por matrícula. Um próximo passo natural é adicionar login com senha (JWT).

## Próximos passos

- [ ] Autenticação de funcionários (JWT)
- [ ] Relatório de horas trabalhadas por período
- [ ] PWA para instalar no celular
- [ ] Deploy com PostgreSQL

## Licença

[MIT](LICENSE)
