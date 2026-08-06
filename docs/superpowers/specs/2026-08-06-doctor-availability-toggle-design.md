# Disponibilité médecin — bloquer la prise de RDV

Date : 2026-08-06
Statut : Approuvé — prêt pour l'implémentation

## Contexte

Le dashboard médecin (`medecin/dashboard.html`) affiche un interrupteur
"Disponible / Indisponible" (`data-avail-toggle`, `app.js`) qui est purement
cosmétique : il change juste le texte/la couleur du toggle en JS, sans appel
API ni persistance. Aucun champ de disponibilité n'existe sur `Doctor`, et la
réservation (`Appointments/logic.book_appointment`,
`GET /appointments/doctors/{id}/availabilities`) ne vérifie que le statut du
créneau (`FREE`/`BOOKED`) — jamais un état global du médecin.

Objectif : rendre ce toggle réel — quand un médecin se marque indisponible,
les patients ne peuvent plus prendre de nouveau rendez-vous avec lui.

## Décisions validées en brainstorming

- **Visibilité** : un médecin indisponible reste visible dans la recherche
  patient (`consultations.html`) et sur sa fiche (`medecin-detail.html`) — il
  ne disparaît pas des résultats. Seule la section de prise de RDV est
  grisée/désactivée, avec un message explicite.
- **Garantie côté API, pas seulement UI** : le blocage doit être appliqué dans
  `book_appointment`, pas uniquement masqué côté frontend — sinon un onglet
  ouvert avant le passage en indisponible (ou un appel direct à l'API)
  contournerait le grisage visuel.
- **Périmètre limité à la réservation** : la messagerie, les ordonnances, le
  carnet, et les rendez-vous déjà `pending`/`confirmed` ne sont pas affectés.
  Ce n'est pas une suspension de compte — juste un frein sur les *nouvelles*
  demandes de RDV.
- **Pas de filtrage de `GET /appointments/doctors/{id}/availabilities`** : les
  créneaux `FREE` déjà publiés restent listés tels quels (le médecin peut
  redevenir disponible sans avoir à republier ses créneaux) ; le blocage se
  fait uniquement à la réservation (`POST /appointments`).

## Modèle de données (`features/Auth/models.py`)

```python
class Doctor(Base):
    ...
    is_available: Mapped[bool] = mapped_column(default=True, server_default=true())
```

Migration Alembic : ajout de la colonne `is_available` (boolean, not null,
défaut `true`) sur `doctors`.

## Endpoints API

Pas de nouvelle route — réutilisation des endpoints existants.

**`features/Doctors/schemas.py`**
- `DoctorProfileUpdateRequest` gagne `is_available: bool | None = None` (même
  pattern `exclude_unset` que les autres champs de ce schéma — `PATCH
  /doctors/me` applique déjà seulement les champs fournis).
- `DoctorPublicOut` (et donc `DoctorProfileOut` qui en hérite) gagne
  `is_available: bool` — nécessaire pour que le frontend patient sache s'il
  doit griser la prise de RDV.

**`features/Doctors/logic.py`**
- `build_public_out` inclut `is_available=doctor.is_available`.

**`features/Appointments/logic.py`**
- `book_appointment` : avant de verrouiller le créneau (`with_for_update`),
  charge le `Doctor` via `availability.doctor_id` et vérifie
  `doctor.is_available`. Si `False` → `HTTPException(409, "Ce médecin
  n'accepte pas de nouveaux rendez-vous pour le moment")`. Placé avant le
  verrou sur `Availability` (pas besoin de verrouiller un créneau qu'on va de
  toute façon refuser).

## Frontend

### `medecin/dashboard.html` / interrupteur (`app.js`)
- Au chargement du dashboard, l'état initial du toggle est fixé depuis
  `GET /doctors/me` (`is_available`) au lieu de toujours démarrer sur
  "Disponible".
- Le handler de clic existant (`data-avail-toggle`) appelle désormais
  `apiRequest('PATCH', '/doctors/me', {json: {is_available: <nouvel état>}})`
  (pattern déjà utilisé par `patient/profil.html` pour `PATCH /patients/me` —
  il n'y a pas de helper `apiPatch` dédié dans `api.js`, seulement
  `apiRequest(method, path, options)`) ; le rendu visuel
  (texte/couleur/position du curseur) n'est appliqué qu'après la réponse OK
  de l'API (pas en optimiste, pour rester cohérent avec le reste du projet —
  cf. patterns d'erreur inline existants). En cas d'échec, le toggle ne
  change pas d'état et une erreur inline s'affiche à proximité.

### `patient/consultations.html`
- Chaque carte médecin de `#doctor-grid` affiche un badge "Indisponible"
  quand `is_available === false` (le payload `DoctorPublicOut` de
  `GET /doctors` le porte déjà).
- Cliquer sur une carte indisponible ouvre quand même `rdv-modal` (on ne
  cache pas la fiche), mais à la place du sélecteur de créneau + bouton
  "Confirmer", un message "Ce médecin n'accepte pas de nouveaux rendez-vous
  pour le moment." s'affiche — pas d'appel à
  `GET /appointments/doctors/{id}/availabilities` dans ce cas.

### `patient/medecin-detail.html`
- Le bouton "Prendre RDV" (`href="consultations.html"`) devient un bouton
  désactivé avec le même message quand `d.is_available === false` (le `GET
  /doctors/{id}` déjà appelé par cette page porte le champ).

## Gestion des erreurs

Convention du projet : messages inline, jamais d'`alert()` (exception déjà
existante : le flux "ordonnance depuis une conversation" utilise `alert()`
ponctuellement, mais ce n'est pas le pattern à suivre ici). Le 409 de
`book_appointment` est affiché comme les autres conflits de créneau déjà
gérés par `consultations.html`.

## Tests

- `test_appointments_flow.py` : un médecin avec `is_available=False` reçoit
  409 sur `POST /appointments` même avec un créneau `FREE` valide ; le
  créneau reste `FREE` après le refus (pas de verrouillage partiel).
- `is_available=True` par défaut (nouveau médecin) ne casse aucun test
  existant de réservation.
- `PATCH /doctors/me` avec `{is_available: false}` puis `GET /doctors/{id}`
  (recherche publique) reflète bien le changement.

## Ce qui reste explicitement hors périmètre

- Pas de programmation à l'avance ("indisponible du X au Y") — bascule
  manuelle uniquement, comme demandé.
- Pas de retrait/annulation automatique des créneaux `FREE` déjà publiés au
  moment du passage en indisponible.
- Pas d'effet sur la messagerie, les ordonnances, le carnet, ou les
  rendez-vous déjà acceptés.
- Pas de notification aux patients ayant un RDV `pending` en cours si le
  médecin passe indisponible entre-temps (un `pending` déjà créé continue son
  cycle normal accepter/refuser).
