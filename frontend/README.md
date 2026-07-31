# Carnet+ — Front-end (HTML / CSS / JS)

Interface de gestion de cabinet médical, en pages HTML séparées et lisibles.

## Structure
- Racine : index.html (connexion), choix-compte.html, inscription-patient.html,
  inscription-medecin.html, inscription-medecin-2.html, mot-de-passe-oublie.html,
  reinitialiser-mot-de-passe.html, confirmer-email.html, en-attente.html,
  admin-connexion.html, styles.css, app.js, auth.js, api.js
- admin/ : dashboard, demandes-medecins, reclamations
- medecin/ : dashboard, calendrier, creer-ordonnance, patients-chroniques, messages, profil
- patient/ : dashboard, consultations, messages, carnet (+ constantes, vaccins),
  ordonnances, evaluations, profil

## Interactions (app.js)
- Inscription en étapes (patient : 2, médecin : 3) avec coches.
- Pop-ups : Bientôt disponible, Prochaines consultations, Choix du mode de consultation,
  Demande envoyée (patient), Demande acceptée (médecin).
- Interrupteur Disponible / Indisponible (dashboard médecin).
- Logo (menu latéral) -> retour au tableau de bord ; flèche -> déconnexion (index.html).
- Créer une ordonnance : cliquer un patient affiche la partie 2 ; « Ajouter un
  médicament » ajoute une ligne.

## Note
Le module Auth (inscription patient/médecin, connexion, mot de passe oublié) est
branché au back-end FastAPI (`Backend-API/`) via `auth.js` (session JWT en
localStorage) et `api.js` (wrapper fetch). L'inscription patient déclenche désormais
un email de confirmation (`confirmer-email.html`) : la connexion est refusée (403)
tant que le lien n'a pas été cliqué. L'espace admin (`admin-connexion.html` + `admin/`)
est également branché : validation/rejet des médecins, réclamations, suppression de
compte médecin. Le reste des pages (dashboards, RDV, messagerie, carnet, etc.) affiche
encore des données d'exemple — leur branchement fera l'objet d'une prochaine tranche.
