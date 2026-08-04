je suis entrain de travailler sur une application de gestion de cabinet medical qui met en relation un patient et un medecin . 

- interaction patients : 
Je travaille sur un projet qui consiste à développer une application web de gestion de cabinet médical entre un patient et un médecin. Commençons par la création du compte. Donc, le patient doit remplir des champs, notamment son nom, son prénom, la date de naissance, le lieu de naissance, l'adresse, son numéro, son pays de résidence, son sexe, sa ville et mettre un mot de passe, minimum 10 caractères, et le confirmer pour pouvoir créer son compte. Après ceci, on accède au compte et donc la première page étant le tableau de bord présentant un petit tableau qui montre donc les traitements que le patient suit actuellement, un bouton nouvelle consultation qui va directement l'amener dans une page où il aura le choix entre les médecins ou le médecin qui lui convient et prendre un rendez-vous. Il y a également d'autres boutons, notamment le bouton vers la messagerie, la liste des médecins qu'il a eu à contacter, l'autre bouton vers ses ordonnances, donc les ordonnances que chaque médecin ou son médecin lui a prescrites, et enfin son carnet de santé. Son carnet de santé qui contient toutes les informations Comme son nom, son prénom, son groupe sanguin, ses allergies et le nombre de documents qu'il stocke dans ce carnet de santé et même les documents qu'il a eu pendant ses consultations précédentes. Et sur dans cette page de carnet de santé, on a un bouton ajouter un document qui va donc lui permettre d'enregistrer ou de garder les ordonnances que son médecin lui a envoyées et tous les documents concernant ses consultations à travers la messagerie entre lui et son médecin. quant à cette page sur les ordonnances, effectivement, il y aura la liste de toutes ces ordonnances depuis la création de son compte, et il aura la possibilité de télécharger le en PDF. Il y aura également une partie pour le profil du patient, donc on va dire toutes les informations que la personne a eu à donner pendant la création du compte sont gardées dans la page profil, avec le nom, le prénom, l'email, le téléphone, pays de résidence, date de naissance, lieu de naissance. sur le tableau de bord du patient, il y aura aussi des rappels sur les traitements qu'il est en train de suivre. Et là, on rappelle à chaque heure qu'il doit prendre dans la journée et la dose. Il y a également un petit rappel de ses prochaines consultations pour qu'il soit à temps.

- interaction medecin : 
C'est pratiquement la même démarche pour le médecin également. Concernant la création de son compte, il devra mettre des informations personnelles et professionnelles. Le nom, le prénom, date et lieu de naissance, adresse email, téléphone, pays de résidence, le sexe, la ville. Et les informations professionnelles sont bien évidemment la spécialité, le numéro d'ordre, l'établissement ou le cabinet où il travaille, son diplôme ou un justificatif. Et également, la personne doit créer un mot de passe minimum 10 caractères, qu'il doit ensuite confirmer. Pour qu'une personne puisse avoir un compte médecin, il aurait besoin de la validation par un administrateur après vérification des justificatifs avant d'être activé. Ensuite, viendra la page où le compte sera mis en attente de validation. Donc la demande sera reçue, la vérification est en cours et donc la personne concernée devrait recevoir un email de confirmation lui permettant donc d'avoir un compte. Après toutes ces démarches, Le médecin pourra par la suite accéder à son compte qui présentera un tableau de bord avec beaucoup d'informations, notamment le nombre de consultations par jour, le nombre de consultations qu'il n'a pas encore acceptées, qui sont donc en attente. Parce que le patient, quand il va prendre rendez-vous, c'est au médecin d'accepter ce rendez-vous pour qu'il puisse avoir lieu. Sinon, la personne sera mise en attente. Ensuite viendra le nombre de consultations que le patient a eu à contracter pendant le mois et la somme totale de ses revenus du mois. Ensuite, concernant les demandes en attente, il mettra la liste, la liste de ces demandes-là, des patients concernés et à côté, le nombre de consultations, la liste des personnes dont la consultation est confirmée. tout en bas, il y aura donc les actions rapides, donc une prescription, donc créer une ordonnance. En cliquant dessus, on va donc directement vers une page où il y aura la liste des patients qui ont déjà fait leur consultation et que donc le médecin leur créera une ordonnance. Le deuxième bouton rapide donc les patients chroniques. Il y aura donc un suivi des patients chroniques, le suivi des patients avec des maladies chroniques et plan de soins. Donc sur l'interface, on aura bien évidemment le nombre de patients suivis, le nombre de plans actifs et le nombre de patients qui sont en alerte, le nombre de RDV pour ces patients chroniques pour la semaine. Juste en dessous, il y aura donc la liste de ces patients chroniques qui sont sous suivi. En mettant juste à côté le prochain rendez-vous, si le plan il est actif ou non, dans le plan, le plan de soins, et en mettant une icône d'alerte pour les patients qui sont en alerte. Et au dessus De cette liste, on a une barre de recherche qui facilitera donc de trouver un quelconque patient. Il y a également le calendrier pour le médecin. Il aura la liste des consultations qui sont prévues chaque jour avec l'heure, le nom du patient, et le mode de consultation, si c'est en présentiel ou c'est par message. Également pour le patient, le médecin, il a une messagerie donc entre lui et ses différents patients. Et enfin, son profil, comme pour le patient, toutes ses informations personnelles.










Scenario (a revoir dans le brainstorming)

Compte patient
Patient (Nom, Prenom, Date de naissance, lieu de naissance, adresse email, telephone, sexe, ville de residence, mot de passe, confirmation du mot de passe)
Consultations (nom du medecin, prenom du medecin, specialité, etablissement/cabinet)
Carnet de santé ( nom et prenom du patient, groupe sanguin, allergies, nombre de documents)
Ordonnances 
Rendez_vous ( prenom et nom du patient, heure, jour, mode ) 

Compte médecin
Medecin (Nom, Prenom, Date de naissance, lieu de naissance, adresse email, telephone, sexe, ville de residence, mot de passe, confirmation du mot de passe)( informations pro : spécialité, Numero d’ordre, etablissement/cabinet, Diplôme /justificatif)
Calendrier ( prenom et nom du patient, heure, jour, mode)
Message
Patients chronique


a chaque fois que un medecin creer un compte l'admin doit etre notifier par mail pour procedder a la validation du compte du medecin ayant fait la demande de creation de compte 

dans la partie admin : validation du compte medecin  sur verification de ses dossiers et diplome des que le compte est valider il recoit un mail pour se connecter a son compte si les information ne sont pas correct au fauuse  il recoit un mail de refus tout cela ce gere dans l'espace admin, possibilite de voir la notation des patients sur des medecins si des patients se plaigne trop sur un medecin il recoit une demande de justification sur mail et si il les justificatif ne sont pas valable son compte est supprimer  depuis l'espace admin , la possibilite aussi de supprimer le compte d'un patient et medecin 

## État d'avancement technique (mis à jour le 2026-07-23)

Ce qui suit sert de repère pour reprendre le travail d'une session à l'autre — ne pas re-brainstormer ces points, ils sont déjà tranchés.

### Décisions d'architecture validées
- **Backend** : FastAPI (async), Pydantic v2, SQLAlchemy 2.0 async + Alembic, PostgreSQL.
- **Stockage fichiers** (diplômes, documents carnet, ordonnances PDF) : S3-compatible (MinIO en dev, S3 en prod). On stocke des clés d'objet privées en base, jamais d'URL publique — génération d'URL présignée à la demande (`core/storage.py`).
- **Email** : Resend (`pip install resend`, clé via `RESEND_API_KEY`).
- **Messagerie patient-médecin** : REST + polling, pas de WebSocket pour la V1.
- **Rappels dashboard** (traitements + prochaines consultations) : calcul passif à l'ouverture du dashboard, pas de scheduler ni de push/email proactif.
- **OCR** (pytesseract + PyMuPDF) : uniquement pour la vérification des justificatifs médecin à l'inscription — pas de RAG/LLM pour l'instant (torch/transformers/chromadb/sentence-transformers/mistralai retirés de `requirements.text`).
- **Tarif de consultation** : fixe par médecin, snapshoté sur le RDV au moment de la confirmation (`Appointment.amount`).
- **Créneaux de RDV** : le médecin publie ses disponibilités (`Availability`), le patient réserve un créneau libre, mais le RDV reste `pending` jusqu'à acceptation explicite du médecin.
- **Avis vs Signalement** : deux entités séparées — une note 1-5 (`Review`) et une plainte motivée distincte (`Complaint`).
- **Suspension médecin** : automatique dès le 5ᵉ signalement actif (pas de demande de justification), suspension de 1 mois, **réactivation automatique** à l'issue du mois ; l'admin peut supprimer directement le compte si les signalements persistent après réactivation.
- **Suppression de compte** (patient ou médecin) : soft delete uniquement (statut `deleted`), jamais de suppression définitive des données de santé.
- **Carnet de santé** (`HealthRecordDocument`) : alimenté par 4 sources — upload manuel patient, ajout auto à la création d'une ordonnance, ajout auto quand un médecin envoie une pièce jointe en messagerie, et dépôt direct par le médecin.
- **Suivi chronique** (`ChronicFollowUp`) : un suivi par médecin + pathologie (pas un statut global patient) ; l'alerte affichée combine un flag manuel ET un calcul automatique (doses manquées, RDV de suivi manqué).

### Structure du code
- `core/` : `config.py` (settings via `.env`), `database.py` (engine + session async), `security.py` (bcrypt + JWT), `storage.py` (S3/MinIO), `email.py` (Resend), `deps.py` (`get_current_patient` / `get_current_doctor` / `get_current_admin` via JWT — réutilisable par toutes les features).
- `features/` — 9 modules, noms en anglais (identifiants de code, la règle du CLAUDE.md global s'applique) : `Auth`, `Admin`, `Patients`, `Doctors`, `Appointments`, `Prescriptions`, `HealthRecords`, `Messaging`, `ChronicCare`, `Notifications`.
- Chaque feature a son `models.py` (SQLAlchemy) et `schemas.py` (Pydantic) déjà écrits. `logic.py`/`routes.py` sont encore des stubs (`raise NotImplementedError`), **sauf `Auth`**.

### Implémenté et testé
- **`features/Auth` est complet** : inscription patient/médecin/admin, connexion (JWT), upload du diplôme médecin en deux appels (JSON puis multipart — FastAPI ne mélange pas les deux dans une requête), notification automatique de l'admin à l'upload du diplôme, reset de mot de passe complet (token à usage unique avec expiration).
- Testé de bout en bout sur SQLite en mémoire (script jetable hors repo) : tous les cas passent (inscription, doublon d'email → 409, mauvais mot de passe → 401, médecin en attente peut se connecter, notification admin, reset password, ancien mot de passe rejeté, token non réutilisable).
- Bug réel trouvé et corrigé pendant les tests : la comparaison de la date d'expiration du token de reset plantait avec un datetime naïf renvoyé par certains drivers (ex. SQLite) — fix dans `_is_expired()` (`features/Auth/logic.py`), qui normalise en UTC avant de comparer.
- **`features/Doctors` est complet** (2026-07-23) : recherche publique `GET /doctors` (filtre `specialty`/`city` en `ilike`, uniquement statut `validated`), fiche publique `GET /doctors/{id}` (404 si non validé), profil authentifié `GET/PATCH /doctors/me` (le `GET` renvoie l'objet du token sans requête ; le `PATCH` n'applique que les champs fournis via `exclude_unset`), dashboard `GET /doctors/me/dashboard` (consultations du jour/du mois, en attente, revenus du mois). Le dashboard joint `Appointment`→`Availability` car `Appointment` n'a pas de date propre ; revenus = somme de `Appointment.amount` (déjà snapshoté) des RDV `confirmed`/`completed` du mois. Vérifié uniquement par `py_compile` (deps non installées dans le venv, pas de test runtime cette fois).
- **`features/Patients` est complet** (2026-07-23) : profil `GET/PATCH /patients/me` (même pattern que Doctors — `GET` renvoie l'objet du token, `PATCH` en `exclude_unset`), dashboard `GET /patients/me/dashboard`. Le dashboard (schémas `PatientDashboardOut`/`TreatmentSummary`/`DoseReminder`/`UpcomingAppointment` ajoutés dans `schemas.py`) agrège en 3 blocs : traitements actifs (`Treatment`→`Prescription` du patient, `is_active` + `end_date >= today`), doses du jour dérivées **en live** des `TreatmentSchedule` (pas de scheduler → on ne s'appuie pas sur des `TreatmentIntake` pré-générés ; le flag `taken` vient d'un `TreatmentIntake` du jour à `TAKEN`), et prochains RDV `confirmed` (`Appointment`→`Availability`+`Doctor`, `date >= today`). Le stub `get_patient_profile` a été retiré (aucun endpoint public patient ne l'utilisait). `py_compile` OK, pas de test runtime.
- **`features/Appointments` est complet** (2026-07-23) : `POST /appointments/availabilities` (médecin publie un créneau ; refus si `end<=start`, date passée, ou chevauchement d'un créneau existant), `GET /appointments/doctors/{id}/availabilities?from_date=` (public, créneaux `FREE` uniquement), `POST /appointments` (patient réserve → RDV `pending`, le créneau passe `BOOKED` sous **verrou `with_for_update`** anti-double-réservation), `POST /appointments/{id}/decision` (médecin, corps `{approve: bool}` → confirm/refuse ; la confirmation **snapshote `Doctor.consultation_fee` dans `Appointment.amount`**, le refus rend le créneau `FREE`), `POST /appointments/{id}/complete` (médecin, `CONFIRMED`→`COMPLETED` — **transition ajoutée** car elle manquait et sert de porte à la prescription), `GET /appointments/pending` (médecin), `GET /appointments/calendar?day=` (médecin). Schéma enrichi `DoctorCalendarEntryOut` ajouté (le calendrier a besoin de l'heure du créneau + nom patient via jointure, absents de `AppointmentOut`). **Pas d'email sur les RDV** (le module Notifications ne couvre que le cycle de vie des comptes ; les RDV en attente sont vus passivement sur le dashboard médecin). Stub `get_upcoming_appointments_for_patient` retiré (le dashboard patient fait déjà la requête en ligne avec la jointure `Doctor`). `py_compile` OK, pas de test runtime.
- **`features/Prescriptions` est complet** (2026-07-23) : `POST /prescriptions` (médecin ; **exige `Appointment.status == COMPLETED`**, génère le PDF via fpdf2, l'upload sur S3/MinIO, crée les `Treatment` + `TreatmentSchedule` à partir des lignes soumises, et **classe auto le PDF au carnet** via `HealthRecordDocument` source `PRESCRIPTION`/`SYSTEM`), `GET /prescriptions` (patient, liste triée desc), `GET /prescriptions/{id}/download` (patient, renvoie `{download_url}` = URL présignée, 404 si pas le sien), `POST /prescriptions/treatment-intakes/confirm` (patient marque une prise → `TreatmentIntake` `TAKEN`, 204 ; vérifie la propriété via `Schedule→Treatment→Prescription`). PDF en core-font Helvetica → helper `_latin1()` qui remplace les caractères hors latin-1 pour éviter un crash fpdf2. Transaction : `flush()` pour récupérer `prescription.id` puis `treatment.id` avant les FKs. Stub `get_today_intakes_for_patient` retiré (redondant avec le dashboard patient). `py_compile` OK, pas de test runtime.

- **`features/HealthRecords` est complet** (2026-07-23) : `GET /health-records/me` (résumé carnet : nom/prénom + groupe sanguin + allergies du patient + compteur de documents), `GET /health-records/me/documents` (liste, tri desc), `POST /health-records/me/documents` (upload patient multipart → storage + doc source `MANUAL_UPLOAD`/`PATIENT`), `GET /health-records/me/documents/{id}/download` (**endpoint ajouté** : URL présignée, sinon les clés S3 privées sont illisibles ; 404 si pas le sien), `POST /health-records/patients/{patient_id}/documents` (médecin dépose sur le carnet d'un patient → source `DOCTOR_UPLOAD`/`DOCTOR`, 404 si patient inexistant/supprimé). **Décision d'archi confirmée** : HealthRecords ne possède QUE les 2 sources manuelles + les lectures ; les 2 sources auto sont écrites *inline par leur producteur* (Prescriptions le fait déjà ; Messaging le fera). Les stubs `add_document_from_prescription`/`add_document_from_message` ont été retirés — signature `(patient_id, message_id)` inexploitable car `Message` ne stocke pas le nom de fichier original et `file_key={uuid}-{filename}` n'est pas re-découpable. `py_compile` OK, pas de test runtime.

- **`features/Messaging` est complet** (2026-07-23) : `POST /messaging/conversations` (**route ajoutée** ; patient initie avec un médecin `validated`, get-or-create), `GET /messaging/conversations` (bi-rôle), `GET /messaging/conversations/{id}/messages` (bi-rôle ; **le fetch marque comme lus** les messages de l'autre partie — pas de route dédiée pour ça, cohérent avec le polling), `POST /messaging/conversations/{id}/messages` (multipart `content` en `Form` + `file` optionnel ; **pièce jointe médecin → carnet inline** source `MESSAGE`/`DOCTOR`), `GET /.../{message_id}/attachment` (**route ajoutée** : URL présignée, sinon `file_key` seul est inutilisable). **Nouvelle dépendance `core/deps.get_current_participant`** → `(user_type, user_id)` résolvant patient OU médecin (messaging est bi-rôle, les dépendances mono-rôle existantes ne suffisaient pas). Autorisation par conversation via `logic.authorize_conversation` (404/403). `send_message` reçoit l'objet `Conversation` (déjà autorisé) pour éviter un re-fetch. `py_compile` OK, pas de test runtime.

- **`features/Admin` est complet** (2026-07-23) : `GET /admin/doctors/pending` (liste + **`diploma_url` présignée** pour que l'admin voie le justificatif), `POST /admin/doctors/{id}/validate` (corps `{approve, rejection_reason?}` → validated/rejected + email `notify_doctor_validated`/`notify_doctor_rejected` ; exige statut `pending_validation`), `DELETE /admin/{user_type}/{user_id}` (**soft delete** → statut `deleted`), et côté public patient : `POST /doctors/{id}/reviews` (note 1-5, exige un RDV `COMPLETED` du patient avec ce médecin, une seule review/RDV), `POST /doctors/{id}/complaints` (signalement → **suspension auto 1 mois au 5ᵉ**). ⚠️ **Limite connue** : `Complaint` n'a pas de champ statut, donc « signalement actif » = total ; la suspension ne se déclenche que sur la transition (médecin `VALIDATED` atteignant 5), mais après réactivation le prochain signalement re-suspend (total déjà ≥5). Sémantique stricte « 5 par cycle » = ajouter une colonne `status`/`resolved` à `Complaint`. **Réactivation auto sans scheduler** : `reactivate_expired_suspensions` (sweep batch) est appelée **paresseusement au login médecin** (`Auth/logic.authenticate_doctor`, import local pour éviter tout cycle). Garde-fou `doctor_id` path==body sur review/complaint. `py_compile` OK, pas de test runtime.

- **`features/ChronicCare` est complet** (2026-07-23) — **dernier module, plus aucun stub `NotImplementedError` dans tout le projet** : `GET /chronic-care/dashboard` (nb patients suivis / plans actifs / patients en alerte / RDV chroniques de la semaine ISO lun-dim), `GET /chronic-care/patients?search=` (liste des suivis actifs du médecin + prochain RDV + plan actif + alerte ; recherche `ilike` sur nom/pathologie), `POST /chronic-care/follow-ups`, `POST /chronic-care/follow-ups/{id}/alert` (flag manuel), `PUT /chronic-care/follow-ups/{id}/care-plan` (upsert, 1 plan par suivi). **Alerte combinée** `_compute_alert` = `manual_alert` OU RDV de suivi manqué (RDV `CONFIRMED` à date passée jamais `COMPLETED`) OU **doses manquées ≥ 3 calculées passivement** (attendues d'après `TreatmentSchedule` bornées par la période du traitement, sur 7 j, moins les `TreatmentIntake` `TAKEN`) — car rien ne crée de lignes `MISSED` (pas de scheduler), un simple comptage `MISSED` serait toujours 0. N+1 borné assumé sur la liste. Toutes les routes gated médecin. `py_compile` + `compileall` du projet entier OK, pas de test runtime.

### État global (2026-07-23)
**Les 10 features sont implémentées** (`logic.py`/`routes.py` complets partout ; `compileall` du projet OK).

**Tests end-to-end (2026-07-23) : `tests/` — 26 tests, tous verts.** Harnais dans `tests/conftest.py` : app FastAPI réelle sur SQLite async (fichier temp), réseau neutralisé par 2 patches (`core.storage._s3_client` = faux client ; `features.Notifications.logic.send_email` = no-op). `pytest.ini` avec `asyncio_mode = auto`. Fixtures d'état : `admin_token`, `patient`, `validated_doctor` (register→diplôme→validation admin), `completed_appointment` (book→confirm→complete). Fichiers : `test_smoke`, `test_appointments_flow` (snapshot `amount`, double-réservation 409, chevauchement, refus libère le créneau, calendrier), `test_prescriptions_and_carnet` (PDF+carnet auto, download, doses dashboard, pièce jointe médecin→carnet mais pas patient, marquage lu au fetch), `test_moderation` (review unique, mismatch path/body 400, 5ᵉ signalement→suspension, réactivation au login, soft delete), `test_chronic_care` (dashboard, alerte manuelle, upsert plan idempotent, **alerte auto doses manquées passives**).
- **Dépendances de test** : installées via `uv` dans un venv éphémère hors repo (`scratchpad/testenv`) — Python 3.14, versions non épinglées + `aiosqlite` (à ajouter à un futur `requirements-dev`). Lancement : `PYTHONPATH=. <venv>/bin/python -m pytest tests/`.
- **2 bugs réels trouvés et corrigés par les tests** : (1) `Prescriptions/logic._build_prescription_pdf` — `multi_cell` de fpdf2 laisse le curseur au bord droit par défaut (`new_x`), d'où « Not enough horizontal space » à la 2ᵉ ligne ; fix = `new_x=XPos.LMARGIN, new_y=YPos.NEXT` sur chaque ligne. (2) `PrescriptionOut.created_at` typé `date` alors que le modèle stocke un `DateTime` → `ResponseValidationError` Pydantic v2 ; fix = `created_at: datetime` (cohérent avec les autres schémas Out).

### Sémantique signalements — RÉSOLUE (2026-07-23)
`Complaint` a désormais une colonne `status` (`ComplaintStatus` ACTIVE/RESOLVED, défaut ACTIVE). `submit_complaint` compte les **ACTIVE**, et à la suspension **marque le lot déclencheur RESOLVED** → chaque cycle repart d'un compteur propre (il faut 5 nouveaux signalements pour re-suspendre après réactivation). Couvert par `test_moderation.test_reactivated_doctor_needs_a_fresh_batch_to_resuspend`. Suite complète : **27 tests verts**.

### Alembic — FAIT (2026-07-23)
`alembic init -t async alembic` + 1ʳᵉ migration `6c332ff88425_initial_schema` (les 18 tables, enums nommés, `complaints.status` inclus). Config : `alembic/env.py` importe tous les modules de modèles (`Base.metadata`), injecte l'URL depuis `settings.database_url` (source unique, via `.env`), et active `compare_type`/`compare_server_default`. `alembic.ini` : `prepend_sys_path = .`, URL placeholder overridée par env.py.
- **Bug corrigé dans la migration** : sur Postgres, `op.drop_table` **ne supprime pas** les types enum créés implicitement → un re-upgrade après downgrade échouait sur `CREATE TYPE gender ... already exists`. Le `downgrade()` droppe désormais explicitement les 14 types (guardé `if bind.dialect.name == "postgresql"`).
- **Vérifié contre une vraie Postgres 16** (`docker compose up -d db`, driver asyncpg) : aller-retour `upgrade → downgrade (0 type résiduel) → re-upgrade → 18 tables` OK. Conteneur ensuite arrêté (`docker compose stop db`) ; volume/schéma persistent.
- Lancement en dev : avec un `.env` renseigné, `alembic upgrade head` fonctionne directement (env.py lit `settings.database_url`).

### Run réel — FAIT (2026-07-23)
App lancée en conditions réelles (`uvicorn app:app`) contre Postgres 16 + MinIO réels, schéma appliqué via Alembic. Smoke end-to-end concluant : inscription patient (write Postgres, id=1) → login JWT → upload document carnet (PUT réel sur MinIO) → résumé carnet (`document_count=1`) → download (URL présignée MinIO) → **récupération de l'objet depuis MinIO : bytes identiques** = roundtrip stockage complet OK. Rows vérifiés en base (`patients=1`, `health_record_documents=1` source `MANUAL_UPLOAD`).
- **`.env` créé** (dev, gitignoré) : creds Docker (`medical_practice`/`minioadmin`), bucket `medical-practice-documents`. Point d'attention host : ports 9000 (MinIO) et 8000 (uvicorn) étaient déjà pris par d'autres services → run fait avec MinIO autonome sur **9100** et uvicorn sur **8010** (le `.env` pointe S3 sur 9100 ; à réaligner sur 9000 quand le compose MinIO peut tourner). Sur un host propre, `docker compose up -d` + `uvicorn app:app` suffisent.
- **Seule erreur observée** : envoi d'email en tâche de fond échoue (`RESEND_API_KEY` factice) — non bloquant (BackgroundTask après la réponse) ; mettre une vraie clé Resend pour l'activer.
- Deps de run installées dans le venv scratchpad : `uvicorn`, `asyncpg` (en plus des deps de test). Conteneurs arrêtés après le run (volumes conservés).

### requirements-dev — FAIT (2026-07-23)
Séparation runtime/dev : `requirements.text` = runtime prod uniquement (bloc `# Testing` retiré) ; nouveau **`requirements-dev.txt`** = `-r requirements.text` + `pytest==9.0.3`, `pytest-asyncio==1.4.0`, `httpx==0.28.1`, `aiosqlite==0.22.1`. Aussi corrigé dans `requirements.text` : `sqlalchemy` → `sqlalchemy[asyncio]` (le projet est full async → `greenlet` doit être garanti). Install dev : `uv pip install -r requirements-dev.txt` puis `pytest`. Suite re-vérifiée verte (27) avec le `.env` présent (le `conftest` force SQLite via `os.environ`, prioritaire sur `.env`).
### Install `requirements.text` sur Python 3.14 — VALIDÉ (2026-07-23)
Venv neuf (`uv venv --python 3.14`) + `uv pip install -r requirements.text` : **install réussie, tous les wheels 3.14 disponibles, aucun échec de build** (y compris `pydantic_core==2.46.4`, `PyMuPDF==1.27.2.3`, `bcrypt==5.0.0`, `sqlalchemy==2.0.51`+greenlet, `asyncpg==0.31.0`). Tous les packages critiques s'importent aux versions épinglées, l'app complète s'importe, et **la suite (27 tests) passe sur ce venv aux pins exacts** (avec `pytest==9.0.3`/`pytest-asyncio==1.4.0` déclarés). Les pins de `requirements.text` sont donc bons pour la prod en 3.14.

### Bucket S3 auto au démarrage — FAIT (2026-07-23)
`core/storage.ensure_bucket_exists()` (idempotent : `head_bucket` → `create_bucket` si absent ; gère le quirk `LocationConstraint` hors us-east-1 ; re-raise sur 403/erreur ≠ « missing » pour ne pas masquer une vraie mauvaise config). Câblé dans un **lifespan** FastAPI (`app.py`), exécuté via `asyncio.to_thread` (boto3 est sync). **Validé en réel** : MinIO vierge (0 bucket) → démarrage de l'app → bucket `medical-practice-documents` présent → upload/download OK. Le faux client S3 des tests a un `head_bucket` no-op (mais httpx ASGITransport n'exécute pas le lifespan de toute façon). 27 tests toujours verts.

### Email Resend — configuré (2026-07-23)
`.env` : `EMAIL_FROM_ADDRESS=onboarding@resend.dev` (expéditeur de test Resend, pas de domaine à vérifier ; **ne livre qu'à l'email du compte Resend**). `RESEND_API_KEY` laissé en placeholder `re_REPLACE_WITH_YOUR_REAL_KEY` — **l'utilisateur pose sa vraie clé lui-même** dans `.env` (hors conversation). Aucun changement de code (le câblage `settings.resend_api_key`→`resend.api_key` est déjà bon ; `resend.api_key` fixé à l'import → redémarrer l'app après édition de `.env`). Validation : `curl` direct sur l'API Resend (voir historique). Pour la prod : vérifier un domaine dans Resend puis passer `EMAIL_FROM_ADDRESS` sur `no-reply@<domaine>`.

### Reste à faire
1. **Prochaine session (prévu 2026-07-25)** : configurer un **domaine vérifié dans Resend** pour envoyer les emails à des destinataires arbitraires (actuellement `onboarding@resend.dev` = envoi limité à l'email du compte Resend `dakar08octobre2024@gmail.com`). Guide pas-à-pas déjà rédigé : **`docs/configuration-domaine-email.md`**. Après vérification : passer `EMAIL_FROM_ADDRESS` sur `no-reply@<domaine>` dans `.env` + redémarrer (aucun changement de code). La vraie `RESEND_API_KEY` est déjà posée par l'utilisateur dans `.env`.
2. MinIO tourne maintenant sur **6000** (host) : `docker-compose.yml` (`6000:9000`/`6001:9001`) + `.env`/`.env.example` (`S3_ENDPOINT_URL=http://localhost:6000`) alignés.
3. (Optionnel proposé, non fait) rendre l'échec d'envoi email non bloquant + loggé proprement dans `core/email.py` au lieu d'une stack trace en tâche de fond.

### Pas encore fait
- `alembic init` + première migration.
- Installation réelle des dépendances dans le venv du projet (`uv pip install -r requirements.text` ou migration vers `uv add`).
- `docker compose up` pour lancer Postgres/MinIO réellement (le fichier a été renommé `docker-compose.yml`, il était mal nommé `docker compose.yml`).
- Faire tourner l'app en conditions réelles (vérifié pour l'instant uniquement via import direct + génération OpenAPI avec les dépendances installées dans un dossier temporaire, et via un test end-to-end sur SQLite en mémoire pour Auth).

**Note** : les trois points ci-dessus sont des notes historiques d'une session bien
antérieure (Alembic, Docker et le run réel sont en fait faits depuis longtemps —
voir les sections « Alembic — FAIT », « Run réel — FAIT » plus haut). Ne pas s'y
fier, se référer plutôt à la section « Reste à faire » ci-dessous et à la session
du 2026-08-04.

## Session du 2026-08-04 — carnet (constantes/vaccins), accès médecin, corrections

Point de départ de la session : bug remonté par l'utilisateur (traitements en
cours affichés en dur sur le dashboard patient). Diagnostic → brainstorming de
découpage en 8 sujets (A-G) sur l'ensemble du frontend patient/médecin/admin
encore câblé en dur. Traités ce soir : **B, D, E, F, G, A** (+ 2 correctifs de
sécurité et une fonctionnalité transverse non prévue au découpage initial).
**Reste : C** (dashboard patient/médecin — traitements/rappels, backend déjà
prêt) — voir `docs/fonctionnement-application.md` §7 pour le détail à jour.

**B — Carnet : constantes vitales & vaccinations** (nouveau, exécuté via
subagent-driven-development sur un plan à 8 tâches, `docs/superpowers/plans/
2026-08-03-carnet-constantes-vaccins.md`) : nouvelles tables `VitalSignBilan`
(bilans manuels tension/glycémie/fréq. cardiaque **+ snapshot auto du poids**,
une seule table pour les deux — le poids n'est éditable que via
`PATCH /patients/me`, jamais directement dans le carnet) et `Vaccination`
(texte libre, pas de statut « à jour »). CRUD complet
(`/health-records/me/vitals*`, `/health-records/me/vaccinations*`), 2 pages
frontend branchées (`carnet-constantes.html`, `carnet-vaccins.html`). 3 bugs
réels trouvés et corrigés par les revues de code pendant l'implémentation :
PATCH pouvant vider un bilan sans le supprimer réellement (orphelin invisible),
poids effacé (`null`) créant un snapshot fantôme, et une course POST/PATCH sur
double-clic avant le premier chargement.

**G — Admin : diplôme médecin invisible** (bug remonté par l'utilisateur —
clic sur « Voir les justificatifs » ouvrait une page vide) : la liste
`GET /admin/doctors/pending` générait l'URL présignée une seule fois au
chargement ; un admin cliquant plus tard (ex. après l'email de notification)
tombait sur un lien expiré. Nouvelle route
`GET /admin/doctors/{id}/diploma/download`, URL fraîche à chaque clic. **Non
vérifié en direct** (pas de Docker/navigateur dans l'environnement de session) —
diagnostic déduit du code, à confirmer par l'utilisateur.

**D — Patients chroniques (médecin)** : branchement frontend pur,
`patients-chroniques.html` sur `GET /chronic-care/dashboard` et
`GET /chronic-care/patients?search=` — backend déjà complet et testé de longue
date. Ajout d'un lien « Voir le carnet » par ligne.

**F — Carnet de santé lu par le médecin** : nouvelles routes
`GET /health-records/patients/{patient_id}` (+ `/documents`, `/vitals`,
`/vaccinations`), gardées par `_authorize_doctor_for_patient` (RDV
`confirmed`/`completed` requis avec ce patient, 404 sinon — jamais 403, pour
ne pas confirmer l'existence du patient à un médecin non autorisé). Nouvelle
page `medecin/patient-carnet.html`, lecture seule, accessible depuis
`patients-chroniques.html`.

**Correctif de sécurité (trouvé en marge de F)** :
`POST /health-records/patients/{patient_id}/documents` (dépôt de document par
un médecin) n'avait **aucune vérification d'autorisation** — n'importe quel
médecin authentifié pouvait déposer un fichier dans le carnet de n'importe
quel patient. Gardé maintenant par la même règle que F. La pièce jointe
messagerie (auto-classée au carnet) n'est pas concernée, elle écrit
`HealthRecordDocument` inline sans passer par cette fonction.

**E — Évaluations patient** : `evaluations.html` était 100 % codé en dur.
Nouvelles routes `GET /patients/me/pending-reviews` (consultations terminées
non notées) et `GET /patients/me/reviews` (avis publiés), jointes au nom/
spécialité du médecin. **Clarification actée avec l'utilisateur** : une
mauvaise note (`Review`, 1-5) ne déclenche **jamais** de suspension — seul le
mécanisme `Complaint` (signalement motivé, déjà existant) compte pour le seuil
de 5. Étoiles de notation rendues réellement interactives (c'était purement
décoratif avant). Bouton « Modifier un avis » retiré (pas de route pour ça).

**A — Identité sidebar/dashboard codée en dur** : `auth.js` ne gardait que le
token/rôle. Ajout de `CarnetAuth.saveIdentity()` (appelé une fois à la
connexion dans `index.html`, via `GET /patients/me`/`/doctors/me`) + un bloc
dans `app.js` qui applique automatiquement nom/email/photo partout où le bloc
sidebar existe (identique sur les ~15 pages, donc un seul changement suffit)
et sur la salutation des 2 dashboards. **Une session ouverte avant ce
correctif doit se reconnecter une fois.**

**Fonctionnalité transverse (hors découpage initial, demandée en cours de
session)** : séparation voir/télécharger pour tout fichier privé.
`core/storage.get_file_url()` accepte un `download_filename` optionnel qui
ajoute un `ResponseContentDisposition` présigné (RFC 6266, fallback ASCII +
variante UTF-8) ; `original_filename_from_key()` récupère le nom d'origine
pour les objets qui ne le stockent pas séparément (diplôme médecin), en
s'appuyant sur le format de clé fixe d'`upload_file()` (`uuid4()` = toujours
36 caractères, vérifié empiriquement). Appliqué à `HealthRecords` (documents
patient + lecture médecin) et `Admin` (diplôme). **Pas encore appliqué à
`Prescriptions`** (`GET /prescriptions/{id}/download` ne renvoie encore
qu'une seule URL) — signalé à l'utilisateur, pas demandé explicitement.

**Tests** : 48 → **81 tests**, tous verts (`uv run python -m pytest -q`).
Nouveaux fichiers : `tests/test_vitals_and_vaccinations.py`,
`tests/test_doctor_patient_access.py`, `tests/test_storage.py`. Le faux client
S3 de `tests/conftest.py` reflète désormais `ResponseContentDisposition` dans
l'URL renvoyée, pour pouvoir vérifier que voir/télécharger diffèrent
réellement.

**Process** : après le chantier B (fait via le pipeline complet
implémenteur + 2 revues par tâche, coûteux en tokens), l'utilisateur a demandé
de continuer sans ce pipeline pour économiser les tokens — tout le reste de la
session (D, F, E, A, le correctif de sécurité, voir/télécharger) a été fait en
implémentation directe dans la session principale, tests à l'appui mais sans
sous-agents.