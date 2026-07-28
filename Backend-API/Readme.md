# Backend API — Gestion de cabinet médical

API backend d'une application web de **gestion de cabinet médical** mettant en relation **patients** et **médecins**, avec un espace **administrateur** pour la modération.

Un patient crée un compte, prend rendez-vous avec un médecin, échange par messagerie, consulte ses ordonnances et son carnet de santé. Un médecin publie ses disponibilités, accepte/refuse les rendez-vous, rédige des ordonnances (PDF), suit ses patients chroniques. Un administrateur valide les comptes médecin (sur justificatif), traite les avis et signalements, et peut suspendre ou supprimer des comptes.

Le projet est **100 % asynchrone** (FastAPI + SQLAlchemy async), découpé par **fonctionnalités** (feature-based), et couvert par une suite de tests end-to-end.

---

## Technologies

| Domaine | Technologie | Rôle |
|---|---|---|
| Framework API | **FastAPI** 0.136 (async) | Endpoints REST, injection de dépendances, OpenAPI |
| Validation | **Pydantic** v2 | Schémas d'entrée/sortie, validation |
| ORM | **SQLAlchemy** 2.0 (async) | Modèles, requêtes async |
| Migrations | **Alembic** (template async) | Versionnage du schéma SQL |
| Base de données | **PostgreSQL** 16 (`asyncpg`) | Persistance |
| Stockage fichiers | **S3 / MinIO** (`boto3`) | Diplômes, ordonnances PDF, documents carnet — clés privées + URL présignées |
| Email | **Resend** | Notifications (validation médecin, reset mot de passe…) |
| Génération PDF | **fpdf2** | Ordonnances |
| OCR | **pytesseract** + **PyMuPDF** | Vérification des justificatifs médecin *(déclaré, non encore branché)* |
| Auth | **bcrypt** + **PyJWT** | Hash mots de passe, tokens JWT |
| Tests | **pytest**, **pytest-asyncio**, **httpx**, **aiosqlite** | Tests end-to-end sur SQLite async |
| Outillage | **uv**, **ruff** | Gestion des dépendances, lint/format |

---

## Architecture

Découpage **feature-based** : chaque fonctionnalité est un module autonome à 4 couches.

```
Backend-API/
├── app.py                     # Point d'entrée FastAPI + lifespan (création auto du bucket S3)
├── core/                      # Briques transverses
│   ├── config.py              # Settings via .env (Pydantic Settings)
│   ├── database.py            # Engine + session async, Base déclarative
│   ├── security.py            # bcrypt (mots de passe) + JWT
│   ├── storage.py             # S3/MinIO : upload, URL présignée, ensure_bucket_exists
│   ├── email.py               # Envoi via Resend
│   └── deps.py                # Dépendances d'auth (get_current_patient/doctor/admin/participant)
├── features/                  # Modules métier
│   ├── Auth/                  # Inscription, connexion, reset mot de passe
│   ├── Patients/              # Profil + dashboard patient
│   ├── Doctors/               # Profil, recherche publique, dashboard médecin
│   ├── Appointments/          # Disponibilités, réservation, cycle de vie du RDV
│   ├── Prescriptions/         # Ordonnances (PDF), traitements, suivi des prises
│   ├── HealthRecords/         # Carnet de santé (documents)
│   ├── Messaging/             # Messagerie patient-médecin (REST + polling)
│   ├── Admin/                 # Validation médecin, avis, signalements, suppression
│   ├── ChronicCare/           # Suivi des patients chroniques, plans de soins, alertes
│   └── Notifications/         # Templates + envoi des emails
├── alembic/                   # Migrations (env.py, versions/)
├── tests/                     # Suite end-to-end (conftest + tests par domaine)
├── docker-compose.yml         # PostgreSQL (5432) + MinIO (6000 API / 6001 console)
├── requirements.text          # Dépendances runtime
├── requirements-dev.txt       # Runtime + outils de test
└── .env                       # Configuration locale (non versionné)
```

**Chaque module `features/<X>/` contient :**
- `models.py` — modèles SQLAlchemy
- `schemas.py` — schémas Pydantic (entrée/sortie)
- `logic.py` — logique métier (aucune dépendance FastAPI hormis `HTTPException`)
- `routes.py` — endpoints FastAPI, câblage auth + appels à `logic`

**Décisions d'architecture notables :**
- **Fichiers privés** : on stocke des **clés d'objet** en base, jamais d'URL publique — génération d'**URL présignée** à la demande.
- **Dashboards passifs** : rappels (traitements, prochains RDV) et alertes chroniques **calculés à la lecture**, pas de scheduler ni de push.
- **Tarif figé** : `Appointment.amount` est *snapshoté* depuis `Doctor.consultation_fee` au moment de la confirmation.
- **Anti double-réservation** : verrou `SELECT ... FOR UPDATE` sur le créneau lors de la réservation.
- **Carnet auto-alimenté** : ordonnances et pièces jointes médecin classées automatiquement dans le carnet (écrit inline par le producteur).
- **Suppression = soft delete** : statut `deleted`, jamais d'effacement des données de santé.
- **Suspension médecin** : automatique au 5ᵉ signalement actif (1 mois), réactivation automatique au login.

---

## Commandes de base

### Prérequis
- Python 3.12+ (validé sur 3.14), [uv](https://docs.astral.sh/uv/), Docker.

### 1. Configuration
```bash
cp .env.example .env          # puis renseigner les valeurs (DB, S3, RESEND_API_KEY…)
```

### 2. Infrastructure (PostgreSQL + MinIO)
```bash
docker compose up -d          # PostgreSQL:5432, MinIO API:6000, console:6001
```

### 3. Dépendances
```bash
uv venv
uv pip install -r requirements-dev.txt   # runtime + outils de test
# (prod uniquement : uv pip install -r requirements.text)
```

### 4. Migrations
```bash
uv run alembic upgrade head              # applique le schéma
uv run alembic revision --autogenerate -m "message"   # nouvelle migration
uv run alembic downgrade -1              # revenir en arrière
```

### 5. Lancer l'API
```bash
uv run uvicorn app:app --port 8010 --reload
```
- Documentation interactive (Swagger) : **http://localhost:8010/docs**
- Schéma OpenAPI : http://localhost:8010/openapi.json
- Health check : http://localhost:8010/health

### 6. Tests
```bash
uv run pytest                 # suite end-to-end complète (SQLite async, sans service externe)
uv run pytest tests/test_appointments_flow.py -q   # un fichier
```

---

## Ce qui est implémenté

Les **10 modules** sont fonctionnels. Suite de tests end-to-end **verte (27 tests)**, migration Alembic initiale en place, validé en run réel (PostgreSQL + MinIO).

### `Auth` — `/auth`
Inscription patient/médecin (mot de passe ≥ 10 caractères + confirmation), connexion JWT, upload du diplôme médecin (en 2 appels), reset de mot de passe (token à usage unique).
- `POST /auth/patients/register`, `POST /auth/doctors/register`, `POST /auth/doctors/me/diploma`
- `POST /auth/patients/login`, `POST /auth/doctors/login`, `POST /auth/admin/login`
- `POST /auth/forgot-password`, `POST /auth/reset-password`

### `Patients` — `/patients`
Profil patient et tableau de bord (traitements actifs, doses du jour, prochains RDV — agrégés à la lecture).
- `GET /patients/me`, `PATCH /patients/me`, `GET /patients/me/dashboard`

### `Doctors` — `/doctors`
Recherche publique (spécialité/ville, médecins validés uniquement), fiche publique, profil et dashboard (consultations du jour/mois, en attente, revenus).
- `GET /doctors` (recherche), `GET /doctors/{id}`
- `GET /doctors/me`, `PATCH /doctors/me`, `GET /doctors/me/dashboard`

### `Appointments` — `/appointments`
Publication de disponibilités (anti-chevauchement), réservation par le patient (verrou anti double-réservation → RDV `pending`), acceptation/refus, complétion, calendrier médecin. Le tarif est snapshoté à la confirmation.
- `POST /appointments/availabilities`, `GET /appointments/doctors/{id}/availabilities`
- `POST /appointments` (réserver), `POST /appointments/{id}/decision` (accepter/refuser)
- `POST /appointments/{id}/complete`, `GET /appointments/pending`, `GET /appointments/calendar`

### `Prescriptions` — `/prescriptions`
Création d'ordonnance par le médecin (RDV complété requis) : génération du **PDF** (fpdf2) → stockage S3, création des traitements + horaires de prise, **classement auto au carnet**. Liste + téléchargement (URL présignée) côté patient, confirmation des prises.
- `POST /prescriptions`, `GET /prescriptions`
- `GET /prescriptions/{id}/download`, `POST /prescriptions/treatment-intakes/confirm`

### `HealthRecords` — `/health-records`
Carnet de santé : résumé (infos santé + nombre de documents), liste, upload manuel patient, dépôt médecin, téléchargement (URL présignée). Alimenté par 4 sources (upload patient, ordonnance, pièce jointe messagerie, dépôt médecin).
- `GET /health-records/me`, `GET /health-records/me/documents`
- `POST /health-records/me/documents`, `GET /health-records/me/documents/{id}/download`
- `POST /health-records/patients/{patient_id}/documents` (médecin)

### `Messaging` — `/messaging`
Messagerie patient-médecin en **REST + polling** (pas de WebSocket en V1). Bi-rôle, autorisation par conversation, marquage « lu » au fetch, pièce jointe médecin classée automatiquement au carnet.
- `POST /messaging/conversations`, `GET /messaging/conversations`
- `GET|POST /messaging/conversations/{id}/messages`
- `GET /messaging/conversations/{id}/messages/{message_id}/attachment`

### `Admin` — `/admin` (+ dépôt avis/signalements côté patient)
Validation/refus des comptes médecin (sur justificatif, avec emails), liste des demandes en attente (avec URL présignée du diplôme), soft delete de comptes. Côté patient : dépôt d'avis (note 1-5, RDV complété requis) et de signalements (→ **suspension auto au 5ᵉ signalement actif**).
- `GET /admin/doctors/pending`, `POST /admin/doctors/{id}/validate`, `DELETE /admin/{user_type}/{user_id}`
- `POST /doctors/{id}/reviews`, `POST /doctors/{id}/complaints` (patient authentifié)

### `ChronicCare` — `/chronic-care`
Suivi des patients chroniques (par médecin + pathologie), plans de soins, tableau de bord (patients suivis, plans actifs, en alerte, RDV de la semaine), recherche. **Alerte combinée** : flag manuel OU RDV de suivi manqué OU doses manquées (calcul passif sur 7 jours).
- `GET /chronic-care/dashboard`, `GET /chronic-care/patients`
- `POST /chronic-care/follow-ups`, `POST /chronic-care/follow-ups/{id}/alert`
- `PUT /chronic-care/follow-ups/{id}/care-plan`

---

## Notes

- **Emails (Resend)** : en mode test (`onboarding@resend.dev`), Resend ne livre qu'à l'adresse du compte Resend. Vérifier un domaine pour la prod.
- **Secrets** : toute la configuration sensible passe par `.env` (non versionné, dans `.gitignore`).
- **Non encore fait** : branchement OCR des justificatifs, dépendances installées dans un venv officiel de prod.
