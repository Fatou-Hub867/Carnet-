# Back-office admin (validation médecin, réclamations, suppression de compte)

Date : 2026-07-29
Statut : Approuvé — prêt pour l'implémentation

## Contexte

Aucune interface admin n'existe aujourd'hui : `POST /auth/admin/login` fonctionne côté
backend mais rien ne l'appelle côté frontend, et `GET /admin/doctors/pending` /
`POST /admin/doctors/{id}/validate` / `DELETE /admin/{user_type}/{user_id}` sont
opérationnels mais inaccessibles sans un client. Il n'existe non plus aucune route pour
lister les réclamations (`Complaint` existe en base, alimentée par
`POST /doctors/{id}/complaints` côté patient, mais rien ne l'expose côté admin).

Cette tranche construit ce qui manque : un endpoint de lecture des réclamations, et
4 pages frontend formant le back-office. C'est le second volet de la tranche démarrée
avec `docs/superpowers/specs/2026-07-29-patient-email-verification.md` — même plan
d'implémentation, deux specs séparées car ce sont deux sujets distincts.

Hors périmètre (confirmé) : recherche générale de comptes patient/médecin (aucune liste
de patients n'existe côté admin) — la suppression de compte se fait uniquement de façon
contextuelle, depuis la liste des réclamations pour un médecin, pas via une recherche libre.

## Backend

### Nouveau : `GET /admin/complaints`

Nouveau schéma `ComplaintOut` (`features/Admin/schemas.py`) :
```python
class ComplaintOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    doctor_id: int
    doctor_name: str
    doctor_status: str
    reason: str
    description: str
    status: str
    created_at: datetime
```

Nouvelle fonction `list_complaints` (`features/Admin/logic.py`), jointure
`Complaint`→`Patient`→`Doctor` pour construire `patient_name`/`doctor_name`
(`f"{first_name} {last_name}"`), triée par `created_at` décroissant. `doctor_status`
permet à l'admin de voir en un coup d'œil si le médecin est déjà suspendu.

Nouvelle route (`features/Admin/routes.py`), même style que `list_pending_doctors`
(gated `get_current_admin`) :
```python
@router.get("/complaints", response_model=list[ComplaintOut])
async def list_complaints(_admin: Admin = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await logic.list_complaints(db)
```

Rien d'autre ne change côté backend — validation, rejet et suppression utilisent les
endpoints déjà existants et déjà testés (`POST /admin/doctors/{id}/validate`,
`DELETE /admin/{user_type}/{user_id}`).

## Frontend — 4 nouvelles pages

Toutes les pages `admin/*` chargent `auth.js`/`api.js`/`app.js` et appellent
`CarnetAuth.requireAuth('admin')` au chargement (garde de session, redirige vers
`admin-connexion.html` si absent/rôle incorrect) — première utilisation réelle de cette
fonction, écrite lors du premier chantier Auth mais jamais encore appelée par aucune page.

### `admin-connexion.html` (racine, à côté de `index.html`)
Formulaire email/mot de passe minimal (mêmes classes CSS que `index.html` : `.auth`,
`.card`, `.input-group`). Soumission → `POST /auth/admin/login` → `CarnetAuth.saveSession(token,
'admin')` → redirection `admin/dashboard.html`. Erreur 401 → message inline (même pattern
que les autres pages : pas d'`alert()`).

### `admin/dashboard.html`
En-tête simple (logo Carnet+, « Espace Admin », bouton déconnexion appelant
`CarnetAuth.logout()`). Deux tuiles de navigation (classe `.tile` déjà existante dans
`styles.css`, utilisée par les dashboards patient/médecin) :
- **Demandes médecins** → `demandes-medecins.html`
- **Réclamations** → `reclamations.html`

Chaque tuile affiche un compteur (nombre de demandes en attente / nombre de réclamations
actives), calculé en appelant les deux endpoints au chargement de la page.

### `admin/demandes-medecins.html`
Liste (via `GET /admin/doctors/pending`) : nom, email, spécialité, n° d'ordre, cabinet,
lien « Voir le diplôme » (`diploma_url`, `target="_blank"`, absent si `null`). Par ligne :
- Bouton **Valider** → confirmation → `POST /admin/doctors/{id}/validate` `{approve: true}`
  → retire la ligne de la liste affichée, toast de succès.
- Bouton **Rejeter** → petit champ de motif (optionnel) → `POST /admin/doctors/{id}/validate`
  `{approve: false, rejection_reason}` → même comportement.

### `admin/reclamations.html`
Liste (via `GET /admin/complaints`) : patient, médecin, statut du médecin (badge — actif/
suspendu/rejeté...), motif, description, statut de la réclamation (badge actif/résolu),
date. Par ligne : bouton **Supprimer ce compte médecin** → modal de confirmation avec un
champ motif **obligatoire** (`AccountDeletionRequest.reason`) → `DELETE
/admin/doctors/{doctor_id}` avec ce corps → retire toutes les lignes de ce médecin de la
liste affichée, toast de succès.

## Gestion des erreurs
Même convention que le reste de l'app : messages inline (`.form-error`/toast), jamais
d'`alert()`. Pas de pagination pour cette V1 (les listes admin restent courtes en usage
réel initial) — à revoir si le volume grandit.

## Ce qui reste explicitement hors périmètre
- Recherche générale de comptes patient/médecin.
- Suppression de compte patient (aucune liste de patients n'existe côté admin — seuls
  les médecins sont atteignables via ce back-office pour l'instant).
- Pagination, tri, filtres sur les listes.
- Tableaux de statistiques avancés au-delà des deux compteurs du dashboard.
