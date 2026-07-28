# Carnet+

Application web de **gestion de cabinet médical** mettant en relation **patients** et **médecins**, avec un espace **administrateur** pour la modération.

Un patient crée un compte, prend rendez-vous avec un médecin, échange par messagerie, consulte ses ordonnances et son carnet de santé. Un médecin publie ses disponibilités, accepte/refuse les rendez-vous, rédige des ordonnances, suit ses patients chroniques. Un administrateur valide les comptes médecin (sur justificatif) et modère avis/signalements.

---

## Structure du dépôt

```
CarnetPlus/
├── Backend-API/    # API FastAPI (async), 10 modules métier — voir Backend-API/Readme.md
├── frontend/       # Interface HTML/CSS/JS (pages séparées, sans framework) — voir frontend/README.md
└── docs/           # Specs et plans de développement (docs/superpowers/)
```

### Backend (`Backend-API/`)

**FastAPI** (100 % async) + **SQLAlchemy 2.0** + **Alembic** (migrations) + **PostgreSQL** + **S3/MinIO** (fichiers) + **Resend** (emails) + **JWT** (auth). Découpage **feature-based** : chaque module (`Auth`, `Patients`, `Doctors`, `Appointments`, `Prescriptions`, `HealthRecords`, `Messaging`, `Admin`, `ChronicCare`, `Notifications`) a ses propres `models.py` / `schemas.py` / `logic.py` / `routes.py`. Détails complets : [Backend-API/Readme.md](Backend-API/Readme.md).

### Frontend (`frontend/`)

Pages **HTML/CSS/JS statiques**, sans framework ni build. Depuis le branchement du module Auth, **le backend sert directement le frontend** (`app.py` monte `frontend/` en fichiers statiques) : un seul serveur à lancer, pas de CORS à configurer. `auth.js` gère la session (JWT en `localStorage`), `api.js` centralise les appels `fetch` vers l'API. Détails : [frontend/README.md](frontend/README.md).

---

## État d'avancement

Le **backend** (10 modules) est entièrement implémenté et testé (suite `pytest` end-to-end). Côté **frontend**, seul le module **Auth** est branché à ce jour (inscription patient/médecin, connexion, upload diplôme, mot de passe oublié/réinitialisation) — les autres pages (dashboards, RDV, messagerie, carnet, ordonnances, patients chroniques) affichent encore des données d'exemple codées en dur ; leur branchement fera l'objet de tranches ultérieures.

⚠️ **Point de vigilance en cours** : une modification de l'énumération `Gender` (`Backend-API/features/Auth/models.py`) est en cours côté backend et n'a pas encore sa migration Alembic associée. Tant qu'elle n'est pas terminée, **inscription, connexion et mot de passe oublié échouent en 500** (la lecture de la ligne `Patient`/`Doctor` en base plante sur la valeur d'enum). Voir la note en fin de ce fichier.

---

## Démarrage en local

### Prérequis
- [uv](https://docs.astral.sh/uv/) (gestion Python/dépendances)
- Docker (pour PostgreSQL + MinIO)
- Python 3.12+ (validé sur 3.14)

### 1. Configuration
```bash
cd Backend-API
cp .env.example .env
```
Renseigner dans `.env` : les identifiants de connexion à la base (`DATABASE_URL`), les clés S3/MinIO, `JWT_SECRET_KEY`, et `RESEND_API_KEY` (une clé de test suffit pour démarrer — l'envoi d'email échouera silencieusement en tâche de fond sans clé valide, ça ne bloque pas le reste).

### 2. Infrastructure (PostgreSQL + MinIO)
```bash
docker compose up -d
```
Démarre PostgreSQL sur `5432` et MinIO sur `6000` (API) / `6001` (console).

### 3. Dépendances
```bash
uv venv
uv pip install -r requirements-dev.txt
```

### 4. Migrations
```bash
uv run alembic upgrade head
```

### 5. Lancer le serveur (backend + frontend, un seul processus)
```bash
uv run uvicorn app:app --port 8010 --reload
```

- **Frontend** : http://localhost:8010/index.html (page de connexion)
- **API — documentation interactive (Swagger)** : http://localhost:8010/docs
- **Health check** : http://localhost:8010/health

### 6. Tester le système d'authentification

Avec le serveur lancé, ouvrir http://localhost:8010/index.html dans un navigateur :

- **Créer un compte** → *Créer un compte* → choisir *Patient* ou *Médecin*, remplir le formulaire.
- Pour un médecin : 3 étapes (infos perso → infos pro + diplôme), puis redirection vers la page d'attente de validation.
- **Se connecter** : sélectionner le rôle (Patient/Médecin) en haut du formulaire, entrer les identifiants.
- **Mot de passe oublié** : lien en bas du formulaire de connexion → email → (le lien de réinitialisation part par Resend ; en mode test Resend ne livre qu'à l'adresse du compte Resend — pour tester sans domaine vérifié, récupérer le token directement en base, table `password_reset_tokens`, puis naviguer vers `http://localhost:8010/reinitialiser-mot-de-passe.html?token=<token>`).

Pour valider un compte médecin créé pendant les tests (nécessaire avant qu'il puisse réellement se connecter en tant que médecin *validé*, même s'il peut déjà se connecter en attente), passer par l'espace admin via l'API (`POST /admin/doctors/{id}/validate`, voir Swagger) — il n'y a pas encore d'interface frontend pour l'admin.

### 7. Tests backend
```bash
cd Backend-API
uv run pytest -q
```

---

## Note sur le blocage `Gender` en cours

Le backend est en train de passer l'énumération `Gender` de `MALE`/`FEMALE` à `HOMME`/`FEMME` (déjà répercuté côté frontend). Tant que la migration Alembic correspondante (renommage des labels de l'enum Postgres `gender`) n'est pas écrite et appliquée, et que `Backend-API/tests/conftest.py` n'est pas mis à jour avec les nouvelles valeurs, les parcours suivants renvoient une erreur 500 : inscription patient/médecin, connexion, mot de passe oublié. Une fois la migration posée, tout redevient fonctionnel sans changement côté frontend (le frontend envoie déjà `homme`/`femme`).
