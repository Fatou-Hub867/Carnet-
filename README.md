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

Le **backend** (10 modules) est entièrement implémenté et testé (suite `pytest` end-to-end, 48 tests verts). Côté **frontend**, sont branchés à ce jour :
- le module **Auth** complet (inscription patient/médecin, connexion, upload diplôme, mot de passe oublié/réinitialisation) ;
- la **vérification d'email patient** : l'inscription n'enchaîne plus sur une connexion automatique — un email de confirmation est envoyé (lien vers `confirmer-email.html`), et la connexion est refusée (403) tant que l'email n'est pas confirmé ;
- l'**espace admin** (`admin-connexion.html` + `admin/`) : validation/rejet des demandes de compte médecin (avec justificatif), consultation des réclamations patients, suppression de compte médecin depuis une réclamation ;
- l'**espace patient** : profil (avec groupe sanguin, poids, photo de profil), carnet de santé (documents, upload, téléchargement), consultations (recherche de médecin, réservation de créneau), ordonnances (liste, téléchargement PDF), messagerie (conversations, envoi de message et pièce jointe, démarrage d'une nouvelle conversation) ;
- l'**espace médecin** (minimum nécessaire pour produire les données ci-dessus) : profil (avec photo), publication de créneaux de disponibilité, calendrier du jour, acceptation/refus des demandes de RDV, clôture d'une consultation, rédaction d'ordonnance, messagerie.

Restent encore à brancher : le tableau de bord patient/médecin (traitements en cours, rappels, chiffres), les évaluations patient, et le suivi des patients chroniques — ces pages affichent toujours des données d'exemple codées en dur.

**Écart connu** : l'identité affichée dans le pied de la barre latérale (nom/email/initiales en bas à gauche) reste codée en dur sur les 15 pages authentifiées — elle ne reflète pas le patient/médecin réellement connecté, contrairement au contenu principal de chaque page (déjà branché sur l'API). `auth.js` ne garde en session que le token et le rôle, pas l'identité ; corriger ça suppose un petit helper (`renderSidebarUser()`) appelé sur chaque page, hors périmètre du chantier actuel.

---

## Démarrage en local

### Option A — tout en Docker (recommandé)

Prérequis : Docker uniquement.

```bash
cp Backend-API/.env.example Backend-API/.env
```
Renseigner dans `Backend-API/.env` : les identifiants de connexion à la base (`DATABASE_URL`), les clés S3/MinIO, `JWT_SECRET_KEY`, et `RESEND_API_KEY` (une clé de test suffit pour démarrer — l'envoi d'email échouera silencieusement en tâche de fond sans clé valide, ça ne bloque pas le reste).

```bash
docker compose up -d --build
```
Démarre l'API (avec hot-reload et migrations automatiques), PostgreSQL sur `5432` et MinIO sur `6002` (API) / `6001` (console) — un seul `docker compose up` pour tout le stack, depuis la racine du repo.

- **Frontend** : http://localhost:8010/index.html (page de connexion)
- **API — documentation interactive (Swagger)** : http://localhost:8010/docs

### Option B — en local (sans Docker pour l'API)

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

### 2. Infrastructure (PostgreSQL + MinIO uniquement)
```bash
docker compose up -d db minio
```
Depuis la racine du repo. Démarre PostgreSQL sur `5432` et MinIO sur `6002` (API) / `6001` (console).

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
- Pour un patient : après soumission, plus de connexion automatique — un panneau « Vérifiez votre boîte mail » s'affiche. Un email de confirmation est envoyé (lien vers `confirmer-email.html?token=...`) ; **tant que ce lien n'est pas cliqué, la connexion renvoie 403**. En mode test, Resend ne livre qu'à l'adresse du compte Resend — pour tester sans domaine vérifié, récupérer le token directement en base (table `email_verification_tokens`), puis naviguer vers `http://localhost:8010/confirmer-email.html?token=<token>`.
- **Se connecter** : sélectionner le rôle (Patient/Médecin) en haut du formulaire, entrer les identifiants.
- **Mot de passe oublié** : lien en bas du formulaire de connexion → email → (même limitation Resend que ci-dessus — récupérer le token en base, table `password_reset_tokens`, puis naviguer vers `http://localhost:8010/reinitialiser-mot-de-passe.html?token=<token>`).

### 7. Tester l'espace admin

Aucune interface ne permet de créer un premier compte admin (par design — un `Admin` se crée uniquement en base, comme le fait `Backend-API/tests/conftest.py`'s `admin_token` fixture). Pour tester en local, un script de seed fait ça directement :
```bash
cd Backend-API
uv run python scripts/seed_admin.py
```
Crée (ou signale l'existence de) l'admin `admin@carnetplus.dev` / `adminpassword1`. Identifiants personnalisables via les variables d'env `ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_FIRST_NAME` / `ADMIN_LAST_NAME` ; relancer avec `--reset-password` pour changer le mot de passe d'un admin déjà créé.

Ensuite, ouvrir http://localhost:8010/admin-connexion.html et se connecter :
- **Tableau de bord** (`admin/dashboard.html`) : compteurs de demandes médecins en attente et de réclamations.
- **Demandes médecins** (`admin/demandes-medecins.html`) : liste des comptes en attente, lien vers le diplôme, valider/rejeter.
- **Réclamations** (`admin/reclamations.html`) : liste des signalements patients contre des médecins, avec suppression de compte médecin (motif obligatoire) directement depuis une ligne.

### 8. Tests backend
```bash
cd Backend-API
uv run python -m pytest -q
```
