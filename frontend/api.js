/* ============================================================
   Carnet+ — Client API (fetch centralisé)
   Toute requête vers le backend passe par ici : header
   Authorization automatique, parsing JSON, erreurs typées.
   Nécessite auth.js chargé avant ce fichier.
   ============================================================ */

// Petit utilitaire partagé (inscription patient/médecin, réinitialisation) :
// évite de dupliquer la comparaison mot de passe / confirmation dans chaque page.
function passwordsMatch(password, confirmation) {
  return password === confirmation;
}

// .detail is FastAPI's raw error body: usually a string, but an array of
// {msg, loc, type} objects for 422 validation errors. Prefer .message for display.
function ApiError(status, detail) {
  Error.call(this, typeof detail === 'string' ? detail : 'Une erreur est survenue.');
  this.name = 'ApiError';
  this.status = status;
  this.detail = detail;
  this.message = typeof detail === 'string' ? detail : 'Une erreur est survenue.';
}
ApiError.prototype = Object.create(Error.prototype);
ApiError.prototype.constructor = ApiError;

async function apiRequest(method, path, options) {
  options = options || {};
  var headers = {};
  var fetchOptions = { method: method, headers: headers };

  if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json';
    fetchOptions.body = JSON.stringify(options.json);
  } else if (options.form !== undefined) {
    fetchOptions.body = options.form; // FormData: le navigateur pose le Content-Type lui-même
  }

  var token = options.token || (window.CarnetAuth && window.CarnetAuth.getToken());
  if (token) headers['Authorization'] = 'Bearer ' + token;

  var response = await fetch(path, fetchOptions);

  if (response.status === 204) return null;

  var text = await response.text();
  var body = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch (e) {
      body = text;
    }
  }

  if (!response.ok) {
    if (
      (response.status === 401 || response.status === 403) &&
      window.CarnetAuth && CarnetAuth.sessionMismatch && CarnetAuth.sessionMismatch()
    ) {
      CarnetAuth.clearSession();
      window.alert('Votre session a changé (connexion depuis un autre onglet ?). Merci de vous reconnecter.');
      window.location.href = '/index.html';
      return new Promise(function () {}); // navigation is already underway, nothing left to do here
    }
    var detail = body && body.detail ? body.detail : response.statusText;
    throw new ApiError(response.status, detail);
  }

  return body;
}

function apiGet(path) {
  return apiRequest('GET', path);
}
function apiPost(path, json) {
  return apiRequest('POST', path, { json: json });
}
function apiPostForm(path, formData, tokenOverride) {
  return apiRequest('POST', path, { form: formData, token: tokenOverride });
}

// Le backend lève ses erreurs (HTTPException) en anglais par convention du
// projet (voir Backend-API/CLAUDE.md). Plutôt que de traduire le backend
// lui-même (romprait avec Swagger/les tests), cette table traduit les
// messages connus pour l'affichage ; tout message non répertorié retombe sur
// un texte français générique plutôt que de fuiter tel quel.
var API_ERROR_TRANSLATIONS = {
  'Cannot open a slot in the past': "Impossible de publier un créneau dans le passé.",
  'This slot overlaps an existing availability': 'Ce créneau chevauche une disponibilité existante.',
  'end_time must be after start_time': "L'heure de fin doit être après l'heure de début.",
  'This slot is no longer available': "Ce créneau n'est plus disponible.",
  'This slot is in the past': 'Ce créneau est déjà passé.',
  'This doctor is not accepting new appointments right now': "Ce médecin n'accepte pas de nouveaux rendez-vous pour le moment.",
  'Availability not found': 'Créneau introuvable.',
  'This slot has already been booked and cannot be removed': 'Ce créneau a déjà été réservé, il ne peut plus être supprimé.',
  'Appointment not found': 'Rendez-vous introuvable.',
  'Patient not found': 'Patient introuvable.',
  'Follow-up not found': 'Suivi introuvable.',
  'The consultation must be completed before prescribing': 'La consultation doit être terminée avant de pouvoir prescrire.',
  "A treatment's end_date is before its start_date": 'La date de fin d’un traitement ne peut pas précéder sa date de début.',
  'Each treatment needs at least one intake time': 'Chaque traitement doit avoir au moins un horaire de prise.',
  'Current password is incorrect': 'Le mot de passe actuel est incorrect.',
};

function translateApiError(err) {
  var detail = err && typeof err.detail === 'string' ? err.detail : null;
  return (detail && API_ERROR_TRANSLATIONS[detail]) || 'Une erreur est survenue, réessayez.';
}
