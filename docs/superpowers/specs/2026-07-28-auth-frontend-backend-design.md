# Brancher l'Auth du frontend Carnet+ au backend FastAPI

Date : 2026-07-28
Statut : Approuvé — prêt pour l'implémentation

## Contexte

Le frontend (`frontend/`) est du HTML/CSS/JS statique : pages séparées, navigation par
`<a href>` en dur, données d'exemple codées dans le HTML, aucun appel réseau. Le backend
(`Backend-API/`) est une API FastAPI complète et testée (10 modules). Cette spec couvre la
**première tranche** de branchement : le module **Auth** uniquement. Les autres modules
(dashboards, RDV, ordonnances, messagerie, carnet, chronique, admin) sont hors périmètre et
feront l'objet de tranches ultérieures, chacune avec sa propre spec.

Pas d'introduction de Tailwind CSS dans cette tranche : `styles.css` (308 lignes, design
system déjà cohérent avec variables CSS, `.btn`, `.card`, `.input`...) reste tel quel.

## Pages concernées

- `index.html` — connexion
- `choix-compte.html` — sélection type de compte (aucun appel API, juste des liens)
- `inscription-patient.html` — inscription patient
- `inscription-medecin.html` (étape 2) + `inscription-medecin-2.html` (étape 3, diplôme) — inscription médecin
- `en-attente.html` — page d'attente validation médecin (statique, informatif)
- **Nouvelles pages** : `mot-de-passe-oublie.html`, `reinitialiser-mot-de-passe.html`

## Architecture

### Service unique (pas de CORS)
`Backend-API/app.py` monte `frontend/` en fichiers statiques via `fastapi.staticfiles.StaticFiles`
(`html=True` pour servir `index.html` par défaut). Un seul serveur (`uvicorn app:app --port 8010`),
une seule origine — pas de middleware CORS nécessaire. C'est un choix pragmatique pour le dev ;
il pourra être revu si une vraie séparation front/back est voulue plus tard.

### `frontend/api.js` (nouveau)
Wrapper `fetch` centralisé :
- Base URL vide (`""`, chemins relatifs — même origine).
- Sérialise le JSON, lit `Authorization: Bearer <token>` depuis `auth.js` si un token existe.
- Une fonction par verbe (`apiGet`, `apiPost`, `apiPostForm` pour les endpoints multipart comme
  l'upload du diplôme) qui renvoie soit les données JSON, soit lève une erreur typée
  `{status, detail}` construite depuis le corps d'erreur FastAPI (`{"detail": "..."}`).
- Pas de retry, pas de cache — hors périmètre.

### `frontend/auth.js` (nouveau)
- `saveSession(token, role)` → `localStorage.setItem('cp_token', token)`, idem pour `cp_role`.
- `getToken()`, `getRole()`.
- `requireAuth(expectedRole)` — à appeler en haut des pages protégées (dashboards, etc., hors
  périmètre de cette tranche mais le helper est écrit maintenant) : redirige vers `index.html`
  si pas de token ou rôle différent.
- `logout()` → vide le localStorage, redirige vers `index.html`.
- Préfixe `cp_` sur les clés localStorage pour éviter toute collision.

### Champs de formulaire
Les inputs HTML actuels n'ont ni `id` ni `name`. Chaque page listée ci-dessus reçoit des
`id` explicites sur ses champs pour que le JS puisse lire les valeurs (`document.getElementById`).
Aucun changement visuel — uniquement des attributs ajoutés.

### Affichage des erreurs
Pas de `alert()`. Un élément d'erreur (ex. `<p class="form-error" id="err-email"></p>`, caché
par défaut) inséré sous le champ concerné ou en bas du formulaire selon le cas, stylé en rouge
discret cohérent avec le design existant (nouvelle règle CSS minimale ajoutée à `styles.css`
si besoin, pas de refonte).

## Flux détaillés

### `index.html` — connexion
- Ajout d'un sélecteur de rôle (2 boutons/tabs "Patient" / "Médecin") au-dessus du formulaire
  existant, pour savoir quel endpoint appeler. État par défaut : Patient.
- Soumission → `POST /auth/patients/login` ou `/auth/doctors/login` selon le rôle sélectionné,
  avec `{email, password}`.
- Succès → `saveSession(access_token, role)` → redirection `patient/dashboard.html` ou
  `medecin/dashboard.html` (ces pages ne sont pas encore branchées sur l'API — elles continueront
  d'afficher leurs données d'exemple pour l'instant, mais `requireAuth` y sera ajouté).
- Échec (401) → message d'erreur inline : "Email ou mot de passe incorrect."
- Lien "Mot de passe oublié ?" → pointe vers `mot-de-passe-oublie.html`.

### `inscription-patient.html`
- Soumission → validation client minimale (mot de passe ≥ 10 caractères, confirmation identique
  — l'API valide aussi côté serveur, le client ne fait qu'éviter un aller-retour évident) →
  `POST /auth/patients/register` avec tous les champs du formulaire mappés sur
  `PatientRegisterRequest`.
- Succès (201) → enchaîne automatiquement `POST /auth/patients/login` avec les mêmes identifiants
  (l'endpoint register ne renvoie pas de token) → `saveSession` → redirection
  `patient/dashboard.html`.
- Erreur 409 (email déjà utilisé) → message inline sous le champ email.
- Erreur 422 (validation Pydantic) → message générique "Vérifiez les champs renseignés."

### `inscription-medecin.html` + `inscription-medecin-2.html`
- Étape 2 (`inscription-medecin.html`) soumet `POST /auth/doctors/register`
  (`DoctorRegisterRequest` : infos perso + pro). Succès → passe à l'étape 3 en gardant les
  identifiants en mémoire (variable JS, pas de persistance) pour le login qui suit.
- Étape 3 (`inscription-medecin-2.html`, upload diplôme) au chargement : si l'étape 2 n'a pas
  été complétée dans cette session (pas d'email en mémoire), redirection vers l'étape 2.
  Soumission → `POST /auth/doctors/login` (le statut `pending_validation` est autorisé à se
  connecter) → puis `POST /auth/doctors/me/diploma` (multipart, avec le token obtenu) →
  redirection `en-attente.html`. Le token obtenu ici n'est **pas** sauvegardé en session
  (le médecin n'est pas encore validé, `en-attente.html` est une page purement informative).
- Erreur à l'étape 2 (409 email dupliqué) → message inline, reste sur l'étape 2.

### `en-attente.html`
Page statique, aucun appel API — juste le message d'attente déjà en place.

### `mot-de-passe-oublie.html` (nouveau)
- Un champ email → `POST /auth/forgot-password`.
- Message affiché quel que soit le résultat (l'API renvoie toujours 202, par design anti
  énumération d'emails) : "Si cet email est enregistré, un lien de réinitialisation a été envoyé."

### `reinitialiser-mot-de-passe.html` (nouveau)
- Lit le `token` depuis le query string (`?token=...`, tel qu'il arrivera dans le lien reçu
  par email — cohérent avec `settings.frontend_base_url` côté backend).
- Champs nouveau mot de passe + confirmation → `POST /auth/reset-password` avec `{token,
  new_password}`.
- Succès → message de confirmation + lien vers `index.html`.
- Erreur (token invalide/expiré/déjà utilisé) → message inline.

## Ce qui reste explicitement hors périmètre
- Dashboards patient/médecin avec vraies données (tranche suivante).
- Toute page au-delà de l'Auth (RDV, ordonnances, carnet, messagerie, chronique, admin).
- Tailwind CSS.
- Rafraîchissement de token / expiration gérée côté client (le token expire silencieusement
  après `access_token_expire_minutes` ; un appel API échouant en 401 après coup n'est pas géré
  spécifiquement dans cette tranche — hors périmètre, à traiter avec les dashboards).

## Notes pour le plan d'implémentation
Pas de dépôt git initialisé sur ce projet à ce jour — cette spec ne peut pas être committée ;
seul le fichier est écrit sur disque.
