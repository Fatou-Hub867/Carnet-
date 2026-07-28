/* ============================================================
   Carnet+ — Client API (fetch centralisé)
   Toute requête vers le backend passe par ici : header
   Authorization automatique, parsing JSON, erreurs typées.
   Nécessite auth.js chargé avant ce fichier.
   ============================================================ */

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

  var token = window.CarnetAuth && window.CarnetAuth.getToken();
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
function apiPostForm(path, formData) {
  return apiRequest('POST', path, { form: formData });
}
