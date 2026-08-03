# Carnet de santé — Constantes vitales & Vaccinations

Date : 2026-08-03
Statut : Approuvé — prêt pour l'implémentation

## Contexte

`patient/carnet-constantes.html` et `patient/carnet-vaccins.html` affichent aujourd'hui
des données 100% en dur (4 cartes de constantes, 4 lignes de vaccins), et ne chargent
même pas `auth.js`/`api.js` — contrairement à `carnet.html` (onglet Documents), déjà
branché. Aucune table backend n'existe pour ces deux notions : `Patient.weight_kg` est un
scalaire unique (le poids « actuel »), pas un historique, et rien ne modélise une
tension/glycémie/fréquence cardiaque ou un vaccin.

Ce chantier couvre aussi la cohérence du poids entre le profil patient et le carnet
(signalée séparément dans la demande initiale, mais qui s'avère être une simple décision
d'architecture à l'intérieur de celui-ci plutôt qu'un sujet à part).

## Décisions validées en brainstorming

- **Poids** : le profil reste l'unique point de saisie (déjà le cas via `PATCH
  /patients/me`). Le carnet n'a pas de formulaire de poids séparé — il affiche la
  dernière valeur, dérivée automatiquement des modifications de profil.
- **Constantes (tension, glycémie, fréq. cardiaque)** : saisies par « bilan » groupé — un
  seul formulaire avec les 3 champs (chacun optionnel), pour une date donnée.
- **Affichage des constantes** : dernière valeur uniquement (4 cartes, comme la maquette
  actuelle) — pas de vue historique dans cette version.
- **Modification/suppression** : autorisée, mais seulement sur le dernier bilan (puisque
  seule la dernière valeur est visible/actionnable côté UI).
- **Vaccins** : nom en texte libre (pas de catalogue prédéfini), dose optionnelle, date.
  Pas de badge « à jour/à faire » (retiré — nécessiterait un calendrier vaccinal officiel,
  hors périmètre). Affichage en liste complète, modifiable/supprimable ligne par ligne.

## Modèle de données (`features/HealthRecords/models.py`)

```python
class VitalSignBilan(Base):
    __tablename__ = "vital_sign_bilans"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    systolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diastolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    glycemia_g_l: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    heart_rate_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Vaccination(Base):
    __tablename__ = "vaccinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    vaccine_name: Mapped[str] = mapped_column(String(255))
    dose_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    administered_at: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`VitalSignBilan` porte à la fois les bilans saisis manuellement (3 champs remplis, jamais
`weight_kg`) et les snapshots de poids générés automatiquement (seul `weight_kg` rempli).
Une seule table plutôt que deux, pour garder un historique unique des mesures — cohérent
avec l'usage qu'en fait `GET /vitals` (voir plus bas), qui doit de toute façon requêter
« la dernière valeur non nulle par colonne » indépendamment de la ligne d'origine.

**Écriture inline du poids** : `Patients/logic.py` (fonction de mise à jour du profil)
crée une ligne `VitalSignBilan(patient_id=..., weight_kg=nouvelle_valeur)` uniquement
quand `weight_kg` fait partie des champs modifiés **et** que la valeur change réellement
(`exclude_unset` ne suffit pas à lui seul — il faut comparer à l'ancienne valeur pour ne
pas polluer l'historique sur un `PATCH` qui renvoie la même valeur). Import direct de
`HealthRecords.models.VitalSignBilan` depuis `Patients/logic.py` — même pattern que
Prescriptions qui écrit son propre `HealthRecordDocument` inline plutôt que via un
callback partagé (décision d'architecture déjà actée dans `CLAUDE.md`).

Migration Alembic pour les 2 nouvelles tables.

## Endpoints API (`features/HealthRecords/routes.py`)

```
GET    /health-records/me/vitals
GET    /health-records/me/vaccinations
POST   /health-records/me/vitals
POST   /health-records/me/vaccinations
PATCH  /health-records/me/vitals/latest
PATCH  /health-records/me/vaccinations/{id}
DELETE /health-records/me/vitals/latest
DELETE /health-records/me/vaccinations/{id}
```

Tous gated `get_current_patient` (même pattern que l'existant du module).

**`GET /vitals`** répond :
```python
class VitalValueOut(BaseModel):
    value: ...  # int, Decimal ou objet {systolic, diastolic} pour la tension
    recorded_at: datetime | None

class VitalsSummaryOut(BaseModel):
    tension: TensionValueOut | None   # {systolic, diastolic, recorded_at}
    glycemia: VitalValueOut | None
    heart_rate: VitalValueOut | None
    weight: VitalValueOut | None
```
La requête cherche, **pour chaque colonne indépendamment**, la ligne la plus récente où
cette colonne n'est pas nulle (4 requêtes ciblées ou une requête avec `MAX` conditionnel
par colonne) — pas un simple `ORDER BY recorded_at DESC LIMIT 1`, car un bilan peut ne
remplir qu'un sous-ensemble des champs, et le poids vient toujours d'une ligne distincte.

**`POST /vitals`** : `systolic` et `diastolic` doivent être fournis ensemble ou pas du tout
(422 si un seul des deux est présent — une tension n'a pas de sens à moitié) ; et au moins
un des 3 groupes (tension complète, `glycemia_g_l`, `heart_rate_bpm`) doit être fourni —
422 si les 3 sont absents. `weight_kg` n'est jamais accepté ici (400 si présent), pour
empêcher un contournement du profil comme point de saisie du poids.

**`PATCH/DELETE .../vitals/latest`** : opèrent sur la ligne la plus récente qui contient
au moins un des 3 champs bilan (jamais une ligne créée par le profil). 404 si aucun bilan
n'a encore été saisi.

**Vaccinations** : CRUD classique scoping `patient_id`, 404 si l'entrée n'appartient pas
au patient courant (même garde que pour les documents du carnet).

## Frontend

### `patient/carnet-constantes.html`
- Ajout de `auth.js` + `api.js` + garde `CarnetAuth.requireAuth('patient')` (absents
  aujourd'hui — trou de sécurité mineur puisque la page n'est même pas protégée).
- 4 cartes chargées via `GET /vitals`, chacune à `—` si `null`.
- Bouton unique "Ajouter/Modifier un bilan" → modale avec les 3 champs, pré-remplie si un
  bilan existe déjà. Soumission : `POST` si aucun bilan n'existe encore, sinon `PATCH
  .../latest` (le frontend sait lequel appeler grâce à la réponse de `GET /vitals` déjà
  chargée). Bouton "Supprimer" → `DELETE .../latest`.
- Carte Poids : pas de bouton d'édition, juste un lien vers `profil.html`.

### `patient/carnet-vaccins.html`
- Même ajout `auth.js`/`api.js`/garde.
- Liste chargée via `GET /vaccinations`, message "Aucun vaccin enregistré." si vide.
- Bouton "Ajouter un vaccin" → modale (nom texte libre, dose optionnelle, date) → `POST`.
- Par ligne : "Modifier" (ouvre la même modale pré-remplie → `PATCH`) / "Supprimer" →
  `DELETE`. Badge "à jour/à faire" retiré du HTML.

### `patient/profil.html`
Aucun changement de comportement (le `PATCH /patients/me` existant suffit) — seul le
backend gagne un effet de bord (écriture inline dans `VitalSignBilan`).

## Gestion des erreurs
Convention du projet : messages inline, jamais d'`alert()`.

## Tests
- `POST /vitals` sans aucun champ rempli → 422.
- `POST /vitals` avec `weight_kg` → 400.
- `PATCH /patients/me` changeant `weight_kg` → une ligne `VitalSignBilan(weight_kg=...)`
  créée ; renvoyer la même valeur → aucune ligne créée.
- `GET /vitals` avec des bilans partiels à des dates différentes → chaque champ renvoie
  sa propre `recorded_at` correcte.
- `PATCH/DELETE .../vitals/latest` sans bilan existant → 404.
- Vaccinations : CRUD + 404 sur une entrée d'un autre patient.

## Ce qui reste explicitement hors périmètre
- Historique complet des bilans de constantes (seule la dernière valeur est exposée).
- Calendrier vaccinal officiel / calcul automatique "à jour vs à faire".
- Accès médecin à ces données (carnet de santé consultable par le médecin — sujet séparé,
  sa propre spec après celle-ci).
- Validation de plausibilité médicale des valeurs saisies (ex. fréquence cardiaque hors
  bornes physiologiques).
