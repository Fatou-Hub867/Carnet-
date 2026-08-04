# Carnet+ — Fonctionnement de l'application

Ce document explique ce que fait l'application, qui l'utilise et comment les
différentes parties du système s'articulent. Il complète (sans les remplacer)
le [README](../README.md) racine, [Backend-API/Readme.md](../Backend-API/Readme.md)
et [frontend/README.md](../frontend/README.md), qui restent la référence pour
le démarrage local et le détail fichier par fichier.

## 1. Objectif

Carnet+ met en relation des **patients** et des **médecins** pour la gestion
d'un cabinet médical : prise de rendez-vous, messagerie, ordonnances, carnet
de santé numérique, suivi des patients chroniques. Un troisième rôle,
**administrateur**, modère la plateforme : validation des comptes médecin sur
justificatif, traitement des réclamations, suppression de comptes.

Le principe directeur : un médecin ne peut exercer sur la plateforme qu'après
vérification humaine de son diplôme par un admin ; un patient peut s'inscrire
librement mais doit confirmer son email avant de se connecter.

## 2. Les trois rôles

### Patient
- Crée un compte (état civil, adresse, mot de passe ≥ 10 caractères), reçoit
  un **email de confirmation** — impossible de se connecter tant que le lien
  n'a pas été cliqué (protection contre les faux emails / les comptes créés
  pour un tiers).
- Cherche un médecin (spécialité, ville), consulte sa fiche publique, réserve
  un créneau qu'il a publié.
- Échange par messagerie avec ses médecins, peut joindre des fichiers.
- Consulte ses ordonnances (PDF téléchargeables) et son carnet de santé :
  documents (uploadés manuellement, ou classés automatiquement depuis une
  ordonnance ou une pièce jointe envoyée par un médecin — voir/télécharger
  séparément), constantes vitales (bilan tension/glycémie/fréq. cardiaque
  saisi à la main ; le poids n'est éditable que depuis le profil et se
  répercute automatiquement dans le carnet), vaccinations (ajout/modif/
  suppression, nom libre, sans calendrier vaccinal officiel).
- Suit ses traitements en cours et confirme la prise de chaque dose depuis
  son tableau de bord *(le tableau de bord affiche encore des données
  d'exemple codées en dur — voir §7)*.
- Après une consultation terminée, la voit apparaître dans « à évaluer » et
  peut y laisser une note (1 à 5) ; peut aussi déposer une réclamation
  motivée contre le médecin (pas liée à la note, voir §3 Modération).

### Médecin
- Crée un compte avec infos pro (spécialité, numéro d'ordre, établissement,
  tarif de consultation) et **upload son diplôme**. Le compte reste en statut
  `pending_validation` — il peut se connecter mais n'apparaît pas dans la
  recherche publique tant qu'un admin ne l'a pas validé.
- Publie ses créneaux de disponibilité ; chaque réservation patient reste
  `pending` tant que le médecin ne l'a pas explicitement acceptée ou refusée.
- Une fois une consultation marquée `completed`, peut rédiger une
  **ordonnance** (génère un PDF, crée les traitements/posologies associés,
  classe automatiquement le PDF dans le carnet du patient).
- Suit ses **patients chroniques** : dashboard (patients suivis, plans
  actifs, alertes, RDV de la semaine), recherche, plans de soins, alertes
  combinant un signalement manuel et un calcul automatique (doses manquées,
  RDV de suivi manqué).
- Depuis la liste des patients chroniques, peut ouvrir le **carnet complet
  d'un patient qu'il a consulté** (résumé, documents, constantes vitales,
  vaccinations) en lecture seule — accès conditionné à l'existence d'un RDV
  `confirmed` ou `completed` avec ce patient, 404 sinon.
- Consulte son tableau de bord (consultations du jour/du mois, RDV en
  attente, revenus du mois) et son calendrier.
- En cas d'accumulation de réclamations (5 réclamations actives), le compte
  est **suspendu automatiquement 1 mois**, avec réactivation automatique à
  l'échéance (vérifiée paresseusement à la prochaine tentative de connexion).

### Administrateur
- Aucune interface publique ne permet de créer un admin — le compte se crée
  uniquement en base (voir §6, script `seed_admin.py`). C'est volontaire :
  il n'y a pas de surface d'attaque « inscription admin ».
- Valide ou rejette les demandes de compte médecin après consultation du
  diplôme (deux actions séparées, voir/télécharger, chacune via une URL
  présignée générée à la demande — pas de lien mis en cache dans la liste,
  donc jamais périmé) ; le médecin reçoit un email de décision dans les deux
  cas.
- Consulte la liste des réclamations patients contre des médecins.
- Peut supprimer un compte (patient ou médecin) — toujours en **soft
  delete** (statut `deleted`), jamais de suppression définitive des données
  de santé.

## 3. Grands flux

**Inscription patient → activation**
`POST /auth/patients/register` → email de confirmation envoyé (Resend) →
`POST /auth/patients/confirm-email` (lien cliqué) → `email_verified=true` →
`POST /auth/patients/login` accepté (403 avant confirmation).

**Inscription médecin → validation admin**
`POST /auth/doctors/register` → `POST /auth/doctors/me/diploma` (upload,
notifie l'admin) → admin consulte `GET /admin/doctors/pending` → `POST
/admin/doctors/{id}/validate` (`approve: true/false`) → email de décision au
médecin → si validé, visible dans `GET /doctors`.

**Prise de rendez-vous**
Médecin : `POST /appointments/availabilities` (créneau `FREE`). Patient :
`GET /appointments/doctors/{id}/availabilities` puis `POST /appointments`
(réservation sous verrou pour éviter le double-booking, créneau → `BOOKED`,
RDV → `pending`). Médecin : `POST /appointments/{id}/decision` (accepte —
snapshote le tarif dans `Appointment.amount` — ou refuse, ce qui libère le
créneau). Après la consultation : `POST /appointments/{id}/complete`.

**Ordonnance et carnet de santé**
Une fois le RDV `completed`, `POST /prescriptions` génère le PDF, l'upload
sur S3/MinIO, crée les lignes de traitement/posologie, et ajoute
automatiquement le PDF au carnet du patient (`HealthRecordDocument`, source
`PRESCRIPTION`). Le patient télécharge via `GET
/prescriptions/{id}/download` (URL présignée).

**Messagerie**
`POST /messaging/conversations` (patient initie avec un médecin validé),
`POST /messaging/conversations/{id}/messages` (texte + pièce jointe
optionnelle). Une pièce jointe envoyée par un **médecin** est classée
automatiquement dans le carnet du patient ; l'inverse non (le patient a déjà
la fonction d'upload manuel dans son carnet).

**Modération**
`POST /doctors/{id}/reviews` et `POST /doctors/{id}/complaints` (patient,
exige un RDV `completed` avec ce médecin). Chaque réclamation est comptée
« active » ; au 5ᵉ signalement actif, suspension automatique d'un mois et le
lot de réclamations déclencheur est marqué résolu (il faut 5 nouvelles
réclamations pour re-suspendre après réactivation). Note (`Review`, 1-5) et
signalement (`Complaint`, motif + description) sont deux entités
indépendantes — **une mauvaise note seule ne déclenche jamais de
suspension**, seuls les signalements comptent pour le seuil de 5.
`GET /patients/me/pending-reviews` liste les consultations terminées pas
encore notées, `GET /patients/me/reviews` les avis déjà publiés.

**Carnet — constantes vitales & vaccinations**
Le patient saisit un bilan (`POST /health-records/me/vitals` — tension,
glycémie, fréq. cardiaque, au moins un champ requis) ; seul le dernier bilan
est modifiable/supprimable (`PATCH|DELETE .../vitals/latest`). Le poids
n'a pas de formulaire dans le carnet : chaque `PATCH /patients/me` qui
change `weight_kg` crée automatiquement un nouveau point dans le même
historique (`VitalSignBilan`). Vaccinations : CRUD classique, nom libre,
aucun statut « à jour » calculé.

**Accès médecin au carnet d'un patient**
`GET /health-records/patients/{patient_id}` (+ `/documents`,
`/vitals`, `/vaccinations`) — 404 si le médecin n'a aucun RDV `confirmed`
ou `completed` avec ce patient. Le dépôt de document médecin
(`POST .../documents`) est gardé par la même règle.

## 4. Architecture technique

```
CarnetPlus/
├── Backend-API/    API FastAPI (async), sert aussi le frontend
│   ├── core/       config, DB (SQLAlchemy async), sécurité (bcrypt+JWT),
│   │               stockage S3/MinIO, envoi d'email (Resend)
│   ├── features/   10 modules métier (voir §5)
│   ├── alembic/    migrations de schéma
│   ├── scripts/    scripts d'exploitation (seed_admin.py)
│   └── tests/      suite pytest end-to-end (81 tests)
├── frontend/       pages HTML/CSS/JS statiques, sans framework ni build
└── docs/           specs, plans, ce document
```

- **Un seul serveur** : `app.py` monte `frontend/` en fichiers statiques sur
  la racine FastAPI — pas de CORS à gérer, pas de second process.
- **Authentification** : JWT (`core/security.py`), un token par rôle
  (patient/médecin/admin) ; le frontend le garde en `localStorage`
  (`frontend/auth.js`) et l'attache aux requêtes via `frontend/api.js`.
- **Fichiers** (diplômes, pièces jointes, documents carnet, PDF
  d'ordonnance) : stockés sur S3/MinIO, jamais d'URL publique en base —
  génération d'une URL présignée à la demande. Deux URL distinctes par
  fichier carnet/diplôme : une pour l'affichage inline, une pour forcer le
  téléchargement (`Content-Disposition: attachment`).
- **Email** (Resend) : confirmation patient, décision de validation médecin,
  notification admin à l'upload d'un diplôme.
- **Base de données** : PostgreSQL, schéma versionné par Alembic.

## 5. Les 10 modules métier (`Backend-API/features/`)

| Module | Rôle | Endpoints clés |
|---|---|---|
| `Auth` | Inscription, connexion, reset mot de passe, confirmation email | `/auth/*` |
| `Patients` | Profil et tableau de bord patient | `/patients/me`, `/patients/me/dashboard` |
| `Doctors` | Recherche publique, fiche, profil, tableau de bord médecin | `/doctors`, `/doctors/{id}`, `/doctors/me*` |
| `Appointments` | Créneaux, réservation, décision, calendrier | `/appointments/*` |
| `Prescriptions` | Génération PDF, suivi des prises de traitement | `/prescriptions/*` |
| `HealthRecords` | Carnet de santé (documents, constantes vitales, vaccinations) + lecture médecin | `/health-records/*` |
| `Messaging` | Conversations et messages patient ↔ médecin | `/messaging/*` |
| `ChronicCare` | Suivi des patients chroniques, plans de soins, alertes | `/chronic-care/*` |
| `Admin` | Validation médecin, réclamations, suppression de compte ; + avis/réclamations patient | `/admin/*`, `/doctors/{id}/reviews`, `/doctors/{id}/complaints` |
| `Notifications` | Envoi d'email (utilisé par les autres modules, pas de routes propres) | — |

Chaque module suit le même découpage : `models.py` (SQLAlchemy),
`schemas.py` (Pydantic), `logic.py` (règles métier), `routes.py` (endpoints
FastAPI).

## 6. Faire tourner et tester en local

Démarrage complet détaillé dans le [README racine](../README.md#démarrage-en-local) :
`docker compose up -d` (Postgres + MinIO) → `uv run alembic upgrade head` →
`uv run uvicorn app:app --port 8010 --reload`.

Pour se connecter en admin sans manipuler la base à la main :
```bash
cd Backend-API
uv run python scripts/seed_admin.py
```
crée `admin@carnetplus.dev` / `adminpassword1` (personnalisable via les
variables d'env `ADMIN_EMAIL`/`ADMIN_PASSWORD`/`ADMIN_FIRST_NAME`/
`ADMIN_LAST_NAME`, `--reset-password` pour changer le mot de passe d'un admin
existant).

Tests backend : `cd Backend-API && uv run python -m pytest -q` (81 tests,
harnais SQLite en mémoire, réseau neutralisé — pas de vrai Postgres/S3/email
requis).

## 7. Ce qui n'est pas encore branché

*(dernière vérification : 2026-08-04)*

Le backend est entièrement implémenté et testé pour les 10 modules. Côté
frontend, tout est désormais branché sur l'API sauf un point :

- **Tableau de bord patient/médecin** (`patient/dashboard.html`,
  `medecin/dashboard.html`) : le bloc « traitements en cours »/rappels
  affiche encore des données d'exemple codées en dur, alors que le backend
  (`GET /patients/me/dashboard`) est déjà prêt et testé. Reste juste le
  branchement frontend, comme ça a été fait pour `carnet-constantes.html`,
  `evaluations.html` ou `patients-chroniques.html`.

Tout le reste est branché : Auth, Admin (dont vue/téléchargement du diplôme
en deux actions séparées), l'espace patient au complet (profil, carnet —
documents + constantes vitales + vaccinations —, consultations, ordonnances,
messagerie, évaluations), et côté médecin (profil, créneaux, calendrier,
décisions de RDV, ordonnance, messagerie, patients chroniques, et le
nouveau carnet en lecture seule d'un patient consulté).

**Écart connu, autre module** : `Prescriptions` (téléchargement d'ordonnance
PDF, `GET /prescriptions/{id}/download`) n'a pas encore été aligné sur le
système voir/télécharger à deux URL (`DocumentUrlsOut`) déployé partout
ailleurs — il ne renvoie encore qu'une seule URL. Pas un bug, juste un
reliquat à uniformiser si besoin.

**Résolu depuis la dernière version de ce document** : l'identité affichée
dans le pied de la barre latérale (nom/email/initiales) et sur la
salutation des dashboards reflète maintenant le compte réellement connecté
(`CarnetAuth.saveIdentity()` + `app.js`, voir
[frontend/README.md](../frontend/README.md)) — une session ouverte avant ce
correctif doit se reconnecter une fois pour en bénéficier.
