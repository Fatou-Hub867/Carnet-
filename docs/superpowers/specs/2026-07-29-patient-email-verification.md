# Vérification d'email patient + lien de connexion dans l'email de validation médecin

Date : 2026-07-29
Statut : Approuvé — prêt pour l'implémentation

## Contexte

Aujourd'hui, un patient qui s'inscrit est automatiquement connecté et redirigé vers son
dashboard — aucune vérification que l'adresse email fournie est réelle/accessible. Le
médecin, lui, reçoit déjà un email quand l'admin valide son compte (`notify_doctor_validated`),
mais ce mail ne contient pas de lien vers l'application.

Cette tranche ajoute :
1. Une vraie vérification d'email à l'inscription patient (nouveau flux, aucune notion
   de ce type n'existe actuellement dans le backend — confirmé par lecture complète de
   `features/Auth/*` : pas de champ `verified`, pas de table de token dédiée, aucun
   gate au login).
2. Un lien de connexion dans l'email de validation médecin déjà existant (changement
   minimal, pas de nouvelle table/colonne côté médecin).

Hors périmètre explicite (confirmé avec l'utilisateur) : panel admin frontend (back-office,
gestion des réclamations patients) — traité dans une tranche ultérieure séparée. Pas de
vérification d'email pour les médecins (leur gate d'activation reste la validation admin).

## Flux patient (nouveau)

1. Le patient soumet le formulaire d'inscription (`inscription-patient.html`, inchangé
   côté champs).
2. `POST /auth/patients/register` crée le compte avec `email_verified=false`, génère un
   token de confirmation (même mécanique que le reset de mot de passe : `secrets.token_urlsafe`,
   stocké en base, expiration, usage unique — mais dans une **table séparée**, jamais
   mélangée avec les tokens de reset de mot de passe), et envoie un email contenant un
   lien `confirmer-email.html?token=...`. **Cet email remplace l'email de bienvenue actuel**
   (un seul email, pas deux).
3. Le frontend n'enchaîne plus sur une connexion automatique : il affiche directement,
   sur la même page, un panneau « Vérifiez votre boîte mail » à la place du formulaire
   (pas de redirection).
4. Le patient clique sur le lien reçu → atterrit sur une nouvelle page
   `confirmer-email.html`, qui appelle automatiquement `POST /auth/patients/confirm-email`
   avec le token lu dans l'URL, et affiche soit un succès (« Email confirmé ! » + bouton
   *Se connecter*), soit une erreur (lien invalide/expiré).
5. Le patient se connecte lui-même sur `index.html` (page de connexion existante, inchangée)
   avec les identifiants saisis à l'inscription.
6. **Tant que l'email n'est pas confirmé, la connexion échoue** avec un 403 et un message
   clair. Le contrôle se fait *après* validation des identifiants (email+mot de passe),
   jamais avant — pour ne pas laisser deviner si un email existe/est vérifié à partir du
   seul couple email+mot de passe faux.

## Flux médecin (changement minimal)

`notify_doctor_validated` reçoit un paramètre `login_link` en plus de `first_name`, et le
template ajoute un lien `{frontend_base_url}/index.html` sous le texte existant. Le
contenu de l'email est traduit en français au passage (comme le nouvel email patient),
pour rester cohérent — c'était en anglais jusqu'ici, comme tous les templates email
existants, mais rien d'autre ne change dans ce module (pas de nouvelle table, pas de
nouveau champ, pas de nouvelle route).

## Modèle de données

### `Patient` (modifié)
Ajout d'un champ `email_verified: bool` (défaut `false`), juste après `password_hash`.

### `EmailVerificationToken` (nouveau modèle, nouvelle table)
Structurellement identique à `PasswordResetToken` (polymorphe `user_type`/`user_id`,
`token` unique indexé, `expires_at`, `used`, `created_at`) mais **dans sa propre table** —
volontairement séparée du reset de mot de passe : mélanger les deux dans une même table
sans colonne « objet » serait un vrai risque (un token de confirmation d'email pourrait
alors être utilisable pour réinitialiser un mot de passe). Utilisée uniquement pour les
patients dans cette tranche (le champ `user_type` reste générique pour permettre une
extension future sans nouvelle migration).

### Configuration
Nouveau réglage `email_verification_token_expire_minutes: int = 1440` (24h — contre 30
minutes pour le reset de mot de passe, car un email de confirmation est souvent consulté
plus tard qu'une demande de reset faite dans la foulée).

## Endpoints

- `POST /auth/patients/register` (existant, comportement modifié) : envoie l'email de
  confirmation au lieu de l'email de bienvenue ; ne change pas la réponse (toujours
  `PatientOut`, 201).
- `POST /auth/patients/confirm-email` (nouveau) — corps `{token: str}` → 200
  `{"status": "email confirmed"}` si le token est valide/non expiré/non utilisé et
  appartient bien à un patient (`user_type == PATIENT`) ; 400 `"Invalid or expired
  confirmation token"` sinon (même style de réponse que `reset-password`).
- `POST /auth/patients/login` (existant, comportement modifié) : 403 si
  `email_verified` est `false`, après vérification des identifiants.

## Emails

| Email | Avant | Après |
|---|---|---|
| Inscription patient | `notify_patient_welcome` (« Welcome to your patient account ») | `notify_patient_confirm_email(to, first_name, confirm_link)` — sujet « Confirmez votre adresse email », contient le lien `confirmer-email.html?token=...` |
| Validation médecin | `notify_doctor_validated(to, first_name)` sans lien | `notify_doctor_validated(to, first_name, login_link)` — même contenu + lien `index.html`, traduit en français |

`notify_patient_welcome` et son template `welcome_patient_email` sont supprimés (plus
aucun appelant après ce changement).

## Frontend

- `inscription-patient.html` : le panneau de formulaire (`<div class="fade">` existant)
  reçoit un `id="register-panel"` ; un nouveau panneau frère `id="register-success"`
  (masqué par défaut, même pattern de bascule que `reinitialiser-mot-de-passe.html`)
  affiche le message « Vérifiez votre boîte mail » avec l'email soumis. Le script ne fait
  plus l'enchaînement register→login→redirection : juste register→bascule de panneau.
- `confirmer-email.html` (nouvelle page) : lit `?token=` dans l'URL, appelle
  automatiquement `POST /auth/patients/confirm-email` au chargement (pas d'action
  utilisateur requise), affiche un panneau de chargement puis succès ou erreur.
- `index.html` : ajoute un message d'erreur dédié pour le cas 403 (« Veuillez confirmer
  votre adresse email avant de vous connecter. »), distinct du message 401 existant.

## Impact sur les tests existants

`tests/conftest.py`'s `register_and_login_patient` (utilisé par la quasi-totalité de la
suite : `test_smoke`, et en cascade par les fixtures `patient`/`completed_appointment`
utilisées dans `test_appointments_flow`, `test_prescriptions_and_carnet`,
`test_moderation`, `test_chronic_care`) doit être mis à jour pour simuler la confirmation
d'email avant de se connecter : après l'inscription, va chercher le token en base
(`EmailVerificationToken` créé pour ce patient) et appelle réellement
`POST /auth/patients/confirm-email` avec, avant d'appeler `/login` — même niveau de
réalisme que la fixture `validated_doctor` existante, qui simule déjà tout le parcours
d'un médecin (inscription→login→diplôme→validation admin) plutôt que de bidouiller l'état
en base directement.

## Ce qui reste explicitement hors périmètre
- Panel admin frontend (back-office, gestion des réclamations patients) — tranche ultérieure.
- Vérification d'email pour les médecins.
- Renvoi de l'email de confirmation si le lien a expiré (pas de bouton « renvoyer » dans
  cette tranche — l'utilisateur devra recréer un compte ou on ajoutera cette action plus
  tard si besoin).
- Le bug préexistant du lien de reset de mot de passe (`/reset-password?token=` ne
  correspond pas au vrai fichier `reinitialiser-mot-de-passe.html`) — repéré lors d'une
  revue de code antérieure, non lié à cette tranche, pas corrigé ici.
