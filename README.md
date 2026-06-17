# InfoGlobe

App FastAPI inicial com estrutura organizada por modulos e application factory.

## Estrutura

```text
infoglobe/
├── app/
│   ├── api/routes/
│   ├── core/
│   ├── services/
│   ├── schemas/
│   └── main.py
├── .env.example
├── main.py
└── requirements.txt
```

## Rodar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Factory principal:

```python
from app.main import create_app
```

## Variaveis de ambiente

Copie `.env.example` para `.env` e preencha:

- `API_KEY_REST_COUNTRIES`
- `API_KEY_OPENROUTER`
- `MONGO_DB_URL_CONN`
- `OPENROUTER_MODEL` opcional
- `CORS_ALLOW_ORIGINS` opcional (`*` libera todas as origens)
- `RATE_LIMIT_REQUESTS_PER_MINUTE` opcional
- `RATE_LIMIT_WINDOW_SECONDS` opcional

## Deploy

O projeto esta pronto para deploy com Docker.

Build:

```bash
docker build -t infoglobe-api .
```

Run:

```bash
docker run --env-file .env -p 8000:8000 infoglobe-api
```

Tambem existe um `Procfile` para plataformas que aceitam comando de processo web.

## Endpoints

- `GET /`
- `GET /health`
- `GET /headlines`
- `POST /country-info`

Exemplo do `POST /country-info`:

```json
{
  "country_name": "Brazil"
}
```
