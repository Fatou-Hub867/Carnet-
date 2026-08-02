# Branchement frontend — espace patient + minimum espace médecin

Date : 2026-08-02
Statut : Approuvé — prêt pour l'implémentation

## Contexte

Aucune page patient n'appelle l'API aujourd'hui : `carnet.html`, `consultations.html`,
`messages.html`, `ordonnances.html` et `profil.html` sont 100% HTML statique avec des
données en dur (jusqu'au bouton « Ajouter un document » qui n'a même pas de handler de
clic). Le backend, lui, a déjà tous les endpoints nécessaires (`Patients`, `HealthRecords`,
`Doctors`, `Appointments`, `Messaging`, `Prescriptions` sont complets et testés côté API,
27 tests verts).

Dépendance cachée découverte pendant le brainstorming : pour que `consultations.html`
affiche de vrais créneaux et que `ordonnances.html` affiche une vraie ordonnance, il faut
que l'espace médecin (publier un créneau, accepter un RDV, le compléter, rédiger une
ordonnance) soit lui aussi branché a minima — sinon brancher le patient seul donne des
listes vides. Décision : on branche donc le minimum côté médecin dans la foulée.

La base contient aussi des données de test accumulées lors des sessions précédentes
(6 médecins, 10 patients — pas un seed dans une migration, juste des comptes créés
manuellement pendant les tests). Elles seront vidées avant de commencer (tranche 1).

## Approche technique

Même pattern que Auth/Admin (déjà en place, à garder pour cohérence) : un `<script>`
inline en bas de chaque page HTML, utilisant `apiGet`/`apiPost`/`apiPostForm` (`api.js`)
et manipulant le DOM directement. Pas de framework, pas de nouvelle couche de rendu
partagée — les pages sont assez petites pour que la duplication reste gérable, et une
abstraction commune casserait la cohérence avec le reste du code pour un gain marginal.

Chaque page authentifiée appelle `CarnetAuth.requireAuth('patient'|'doctor')` au
chargement (garde de session déjà écrite, déjà utilisée par l'espace admin). Erreurs :
messages inline (`.form-error` ou équivalent), jamais d'`alert()` — convention déjà
établie.

## Tranche 1 — Nettoyage des données de test

Nouveau script `Backend-API/scripts/reset_dev_data.py` (réutilisable, même esprit que
`seed_admin.py`) : `TRUNCATE` en cascade sur les tables métier (`doctors`, `patients`,
`appointments`, `availabilities`, `prescriptions`, `treatments`, `treatment_schedules`,
`treatment_intakes`, `health_record_documents`, `conversations`, `messages`, `reviews`,
`complaints`, `chronic_follow_ups`, `care_plans`), en conservant `admins`. Confirmation
requise avant exécution (`--yes` ou prompt) puisque c'est destructif.

## Tranche 2 — Profil patient + médecin, photo de profil, Carnet de santé

### Backend — nouveaux champs et endpoints

**Poids patient** : nouvelle colonne `Patient.weight_kg` (`Numeric(5,2)`, nullable),
migration Alembic. Ajouté à `PatientProfileOut`/`PatientProfileUpdateRequest` au même
titre que `blood_type`/`allergies` — même statut : absent à l'inscription, éditable
uniquement depuis le profil.

**Photo de profil (patient ET médecin)** : nouvelle colonne `photo_file_key`
(`String(500)`, nullable) sur `Patient` et sur `Doctor`, migration Alembic. Upload via le
même mécanisme que le diplôme médecin (fichier → `core/storage.upload_file` → clé S3
privée stockée en base, jamais d'URL publique) :
- `POST /patients/me/photo` (multipart, patient authentifié) → remplace la clé existante.
- `POST /doctors/me/photo` (multipart, médecin authentifié) → idem.

`PatientProfileOut`, `DoctorProfileOut` et `DoctorPublicOut` gagnent un champ
`photo_url: str | None` (URL présignée générée à la lecture, `None` si pas de photo —
même pattern que `diploma_url` dans `PendingDoctorOut`).

**Messagerie** : `ConversationOut` (`features/Messaging/schemas.py`) ne renvoie
aujourd'hui que des IDs bruts, ni noms ni photos des deux côtés — trou pré-existant,
comblé ici puisque la photo en dépend directement :
```python
class ConversationOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_photo_url: str | None
    doctor_id: int
    doctor_name: str
    doctor_photo_url: str | None
    created_at: datetime
```
Toujours les deux côtés (même choix que `ComplaintOut` côté Admin) — le frontend affiche
celui qui n'est pas l'utilisateur courant, pas de logique de « point de vue » côté API.

### `patient/profil.html`
Le mock actuel n'a pas de champ groupe sanguin/allergies/poids/photo, et « NOM COMPLET »
est un seul champ alors que l'API attend `first_name`/`last_name` séparés. Refonte du
formulaire :

- **Chargé** depuis `GET /patients/me` au montage.
- **Éditable** (soumis via `PATCH /patients/me`, `exclude_unset` côté backend donc on
  n'envoie que les champs modifiés) : prénom, nom, adresse, téléphone, pays de
  résidence, ville, **groupe sanguin**, **allergies**, **poids**.
- **Lecture seule** (non modifiable par l'API, affiché mais désactivé) : email, date de
  naissance, lieu de naissance, sexe.
- **Photo de profil** : au-dessus du formulaire, remplace l'avatar initiales actuel ;
  clic → sélection fichier → `POST /patients/me/photo` (multipart, `accept="image/*"`
  côté input, pas de validation stricte serveur au-delà de ce qui existe déjà pour les
  autres uploads) → rafraîchit l'avatar avec la nouvelle URL présignée.
- Bouton **Enregistrer** → `PATCH`, toast de succès, re-remplit le formulaire avec la
  réponse. Bouton **Annuler** → recharge les valeurs d'origine sans appel réseau.

### `medecin/profil.html`
Actuellement statique lui aussi (pas dans le périmètre initial, ajouté ici pour la
symétrie photo). Même traitement que le patient pour la partie photo : avatar
remplaçable → `POST /doctors/me/photo`. Les autres champs du profil médecin (déjà
couverts par `GET/PATCH /doctors/me`, existant) sont branchés à la même occasion plutôt
que de laisser la page à moitié en dur.

### `patient/carnet.html`
- Bandeau résumé (`GET /health-records/me`) : nom/prénom, groupe sanguin, allergies,
  **poids**, nombre de documents — plus besoin de dupliquer la saisie, c'est un miroir du
  profil (le résumé carnet devra exposer `weight_kg`, à ajouter à
  `HealthRecordSummaryOut`).
- Liste des documents (`GET /health-records/me/documents`), triée desc.
- Bouton **Ajouter un document** → modale simple (input `type="file"`) →
  `POST /health-records/me/documents` (multipart) → ajoute la nouvelle carte en tête de
  liste sans recharger toute la page.
- Le modèle `HealthRecordDocument` n'a **pas de champ catégorie** — les chips « Analyse »,
  « Vaccination » du mock sont fictives. Remplacées par un badge dérivé de
  `source_type` : Upload manuel / Ordonnance / Message / Médecin.
- Chaque carte a un bouton **Télécharger** → `GET .../documents/{id}/download` →
  ouvre l'URL présignée retournée dans un nouvel onglet.

### Avatars partout ailleurs
Chaque endroit de l'UI qui affiche aujourd'hui un avatar en dur (initiales sur fond
coloré — barre latérale, listes de RDV, dashboard médecin...) doit afficher la vraie
photo dès qu'un `photo_url` est disponible dans la réponse API consommée par cette page,
sinon garder le repli initiales existant. Pas de nouveau composant : juste un
`if (photo_url) <img> else <div initiales>` répété là où c'est pertinent.

## Tranche 3 — Créneaux (médecin) + Consultations (patient)

### `medecin/calendrier.html`
Aucune UI de publication de créneau n'existe actuellement. Ajout d'un bouton
**Ajouter une disponibilité** → modale (date, heure de début, heure de fin) →
`POST /appointments/availabilities`. `Availability` est un slot simple (une date + une
plage horaire), pas de récurrence à gérer en V1.

### `patient/consultations.html`
- Liste des médecins depuis `GET /doctors` (l'API n'a que `specialty`/`city`, pas de
  recherche plein texte) : le menu déroulant spécialité relié au paramètre `specialty`
  côté serveur ; le champ recherche texte filtre côté client sur le nom, dans la liste
  déjà récupérée (échelle de l'app trop faible pour justifier un nouveau paramètre
  serveur).
- La modale « Prendre RDV » ne propose actuellement que Message/Présentiel sans jamais
  choisir de créneau. Refonte : à l'ouverture, `GET /doctors/{id}/availabilities?from_date=`
  (créneaux `FREE`, regroupés par date) → le patient choisit un créneau, un mode
  (existant), et un champ texte optionnel **motif** (`AppointmentCreateRequest.reason`,
  déjà supporté côté API) → confirmer → `POST /appointments`.
- Si un médecin n'a aucun créneau libre, sa carte affiche « Aucun créneau disponible » à
  la place du bouton (pas de modale vide).

## Tranche 4 — Accepter/Refuser RDV + Calendrier (médecin)

### `medecin/dashboard.html`
Le squelette existe déjà (section « Demandes en attente », bouton **Accepter**, modale de
confirmation) — branchement :
- `GET /appointments/pending` remplace la liste en dur.
- Bouton **Accepter** → `POST /appointments/{id}/decision` `{approve: true}`.
- Nouveau bouton **Refuser** (absent du mock, à ajouter à côté d'Accepter) →
  `POST /appointments/{id}/decision` `{approve: false}`.
- Retire la ligne de la liste affichée après décision, sans recharger la page.

### `medecin/calendrier.html`
Affichage des RDV réels du jour via `GET /appointments/calendar?day=` (heure, nom
patient, mode). Sur un RDV `confirmed` dont l'heure est passée, bouton **Terminer la
consultation** → `POST /appointments/{id}/complete` — c'est la porte d'entrée obligatoire
vers la prescription (l'API refuse `POST /prescriptions` sur un RDV non `COMPLETED`).

## Tranche 5 — Ordonnance (médecin) + Mes ordonnances (patient)

### Gap backend à combler
`PrescriptionOut` (`features/Prescriptions/schemas.py`) ne renvoie que des IDs
(`doctor_id`, `appointment_id`), sans nom du médecin ni détail des traitements —
insuffisant pour une carte utile côté patient. Enrichissement :
```python
class TreatmentLineOut(BaseModel):
    medication_name: str
    dosage: str
    start_date: date
    end_date: date

class PrescriptionOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    doctor_name: str
    appointment_id: int
    notes: str | None
    created_at: datetime
    treatments: list[TreatmentLineOut]

    model_config = {"from_attributes": True}
```
`logic.list_prescriptions` (ou équivalent) fait la jointure `Prescription`→`Doctor` et
charge `treatments` (relation déjà existante sur `Prescription`).

### `medecin/creer-ordonnance.html`
Nouvel endpoint `GET /appointments/completed-awaiting-prescription` (doctor-scoped,
même module `Appointments`) : `Appointment` du médecin courant, statut `COMPLETED`,
`LEFT JOIN Prescription ON Prescription.appointment_id = Appointment.id` filtré sur
`Prescription.id IS NULL` (rien n'empêche aujourd'hui plusieurs prescriptions pour un
même RDV côté backend — hors périmètre de cette tranche, on filtre juste ceux qui n'en
ont encore aucune). Répond avec patient + date/heure du RDV, pour l'affichage en liste.
Sélection d'un patient → formulaire des lignes de traitement (médicament, dosage, dates,
horaires de prise) → `POST /prescriptions`.

### `patient/ordonnances.html`
`GET /prescriptions` (liste enrichie ci-dessus), affichage par carte (médicament(s),
médecin, date, posologie). Bouton **Télécharger PDF** → `GET /prescriptions/{id}/download`
→ ouvre l'URL présignée. Bouton **Envoyer à la pharmacie** reste désactivé (aucune
fonctionnalité correspondante côté backend, hors périmètre).

## Tranche 6 — Messagerie (patient + médecin)

Bi-rôle des deux côtés (`messaging` gère déjà patient et médecin via
`get_current_participant`) :
- Liste des conversations : `GET /messaging/conversations`.
- Fil de messages : `GET /messaging/conversations/{id}/messages` avec un polling léger
  (cohérent avec la décision d'archi « REST + polling, pas de WebSocket pour la V1 »).
- Envoi : `POST /messaging/conversations/{id}/messages` (multipart, `content` + pièce
  jointe optionnelle).
- Bouton **Nouveau** (patient uniquement — un médecin ne peut pas initier une
  conversation) → modale de choix de médecin (réutilise `GET /doctors`) →
  `POST /messaging/conversations` (get-or-create) → ouvre le fil.

## Gestion des erreurs
Convention déjà établie : messages inline, jamais d'`alert()`. Pas de pagination sur les
listes (carnet, ordonnances, conversations) pour cette V1.

## Ce qui reste explicitement hors périmètre
- Étape de consentement séparée avant qu'un médecin voie la photo d'un patient (ou
  inversement) : dès qu'une conversation existe, les deux parties voient nom + photo,
  comme c'est déjà le cas pour le nom aujourd'hui côté RDV.
- Validation stricte du format/poids des photos uploadées (type, taille max) au-delà de
  ce qui existe déjà pour les autres uploads du projet.
- Récurrence des créneaux de disponibilité (un slot = un formulaire, pas de génération
  en masse).
- Catégorisation manuelle des documents du carnet (pas de champ en base).
- « Envoyer à la pharmacie » (aucune intégration pharmacie n'existe).
- WebSocket / temps réel sur la messagerie.
- Pagination, tri, filtres avancés sur les listes.
- Le chatbot symptômes (Mistral) — sujet séparé, sa propre spec après celle-ci.
