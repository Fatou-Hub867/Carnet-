# Dockerisation complète du stack de dev — design

Date : 2026-08-06

## Contexte

Le `Backend-API/docker-compose.yml` actuel ne contient que `db` (Postgres 16)
et `minio` (MinIO). L'API FastAPI (qui sert aussi le frontend statique via
`StaticFiles` mount dans `app.py`) tourne en dehors de Docker, lancée
manuellement avec `uv run uvicorn app:app --port 8010 --reload`.

Objectif : qu'un seul `docker compose up` fasse tourner l'intégralité du
stack (API + frontend + Postgres + MinIO), sans installation locale de
Python/uv.

## Décisions actées (brainstorming du 2026-08-06)

- **Usage cible : dev reproductible avec hot-reload**, pas une image de
  prod. Pas de build multi-stage, pas d'optimisation de taille d'image pour
  cette itération.
- **Migrations Alembic automatiques** au démarrage du conteneur `api`
  (`alembic upgrade head` avant `uvicorn`), pas de commande manuelle à courir
  à part.
- **Image basée sur `requirements-dev.txt`** (pas seulement
  `requirements.text`) : `pytest` et `ruff` doivent être utilisables
  directement via `docker compose exec api pytest` / `... ruff check .`.

## Architecture

Un `docker-compose.yml` à la racine du repo (remplace celui de
`Backend-API/`) avec 3 services :

- **`db`** — Postgres 16, inchangé, + un `healthcheck` (`pg_isready`) ajouté
  pour que `api` attende que la base soit réellement prête (pas juste que le
  conteneur ait démarré).
- **`minio`** — inchangé.
- **`api`** — nouveau. Construit depuis `Backend-API/Dockerfile`. Sert API +
  frontend (le mount statique existant dans `app.py` continue de fonctionner
  tel quel). Hot-reload via bind-mount du code + `uvicorn --reload`.

### Dockerfile (`Backend-API/Dockerfile`)

- Base `python:3.14-slim` (version déjà validée dans le projet — voir
  `Backend-API/CLAUDE.md`, section "Install requirements.text sur Python
  3.14").
- `apt-get install -y --no-install-recommends tesseract-ocr` : requis par
  `pytesseract` (vérification OCR du diplôme à l'inscription médecin) — sans
  ce paquet système, l'appel `pytesseract` échoue au runtime même si le
  package Python est installé.
- `pip install -r requirements-dev.txt` (inclut `requirements.text` +
  pytest/ruff/httpx/aiosqlite).
- `WORKDIR /app/Backend-API`.
- `COPY` du code au build (pour que l'image soit utilisable seule, hors
  compose, si besoin) ; en dev, le bind-mount de compose écrase ce contenu
  au runtime pour le hot-reload.
- `CMD` : `sh -c "alembic upgrade head && uvicorn app:app --host 0.0.0.0 --port 8010 --reload"`.

### Service `api` dans docker-compose.yml

```yaml
api:
  build:
    context: .
    dockerfile: Backend-API/Dockerfile
  working_dir: /app/Backend-API
  command: sh -c "alembic upgrade head && uvicorn app:app --host 0.0.0.0 --port 8010 --reload"
  volumes:
    - .:/app
  ports:
    - "8010:8010"
  env_file:
    - Backend-API/.env
  environment:
    DATABASE_URL: postgresql+asyncpg://medical_practice:medical_practice@db:5432/medical_practice
    S3_ENDPOINT_URL: http://minio:9000
  depends_on:
    db:
      condition: service_healthy
```

Le contexte de build est la **racine du repo** (pas `Backend-API/`), pour
pouvoir copier aussi `frontend/` dans l'image et préserver le chemin relatif
`Path(__file__).resolve().parent.parent / "frontend"` que `app.py` calcule
déjà (Backend-API/app.py:20) — sans ça, `FRONTEND_DIR` pointerait vers un
chemin inexistant dans le conteneur.

**Gestion des variables d'environnement** : `Backend-API/.env` (gitignoré,
déjà utilisé pour le run local) reste la source pour tous les secrets (JWT,
Resend, clés/bucket S3, etc.) via `env_file:`. Le bloc `environment:` du
service `api` **surcharge uniquement** `DATABASE_URL` et `S3_ENDPOINT_URL`
avec les noms de service réseau Docker (`db`, `minio`) — ce sont les deux
seules valeurs qui diffèrent entre un run local (`localhost`) et un run
Docker (nom de service). Pas de nouveau fichier `.env.docker` : une seule
source de vérité pour les secrets, une surcharge ciblée pour le réseau.

### `.dockerignore`

Ajouté à la racine du repo pour exclure `__pycache__`, `.venv`, `.git`,
`node_modules` (si présent), et autres artefacts, du contexte de build.

## Ce qui ne change pas

- Ports publiés côté host : `8010` (API+frontend), `5432` (Postgres),
  `6001`/`6002` (MinIO) — inchangés, accessibles depuis des outils externes
  (psql, console MinIO, client HTTP).
- `Backend-API/.env` reste gitignoré ; aucun secret nouveau à gérer.
- Le fichier `Backend-API/docker-compose.yml` existant est déplacé/fusionné
  à la racine — pas de doublon de configuration `db`/`minio`.

## Hors scope (itération future si besoin)

- Image de production optimisée (multi-stage, sans bind-mount ni
  `--reload`).
- Intégration CI utilisant cette image.
- `docker-compose.override.yml` séparant dev/prod.

## Impact sur la documentation existante

`CLAUDE.md` (racine) documente aujourd'hui le workflow `uv venv` / `uv run
uvicorn` comme unique façon de lancer le projet. La section "Commands" sera
mise à jour pour présenter `docker compose up` comme le nouveau chemin
principal, en gardant le workflow `uv` local comme alternative (utile pour
un dev qui préfère ne pas tout conteneuriser).
