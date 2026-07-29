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

// Indicatifs téléphoniques par pays (inscription patient/médecin) : évite de
// figer le préfixe sur +221 quel que soit le pays choisi. Couvre les 54 pays
// d'Afrique + France (diaspora). "Autre" laisse le champ libre (l'utilisateur
// saisit son numéro complet, indicatif inclus). Les clés doivent matcher
// exactement la valeur des <option> du select "PAYS DE RÉSIDENCE".
var COUNTRY_PHONE_PREFIXES = {
  'Sénégal': { flag: '🇸🇳', code: '+221' },
  'Afrique du Sud': { flag: '🇿🇦', code: '+27' },
  'Algérie': { flag: '🇩🇿', code: '+213' },
  'Angola': { flag: '🇦🇴', code: '+244' },
  'Bénin': { flag: '🇧🇯', code: '+229' },
  'Botswana': { flag: '🇧🇼', code: '+267' },
  'Burkina Faso': { flag: '🇧🇫', code: '+226' },
  'Burundi': { flag: '🇧🇮', code: '+257' },
  'Cameroun': { flag: '🇨🇲', code: '+237' },
  'Cap-Vert': { flag: '🇨🇻', code: '+238' },
  'Comores': { flag: '🇰🇲', code: '+269' },
  'Congo': { flag: '🇨🇬', code: '+242' },
  "Côte d'Ivoire": { flag: '🇨🇮', code: '+225' },
  'Djibouti': { flag: '🇩🇯', code: '+253' },
  'Égypte': { flag: '🇪🇬', code: '+20' },
  'Érythrée': { flag: '🇪🇷', code: '+291' },
  'Eswatini': { flag: '🇸🇿', code: '+268' },
  'Éthiopie': { flag: '🇪🇹', code: '+251' },
  'Gabon': { flag: '🇬🇦', code: '+241' },
  'Gambie': { flag: '🇬🇲', code: '+220' },
  'Ghana': { flag: '🇬🇭', code: '+233' },
  'Guinée': { flag: '🇬🇳', code: '+224' },
  'Guinée équatoriale': { flag: '🇬🇶', code: '+240' },
  'Guinée-Bissau': { flag: '🇬🇼', code: '+245' },
  'Kenya': { flag: '🇰🇪', code: '+254' },
  'Lesotho': { flag: '🇱🇸', code: '+266' },
  'Libéria': { flag: '🇱🇷', code: '+231' },
  'Libye': { flag: '🇱🇾', code: '+218' },
  'Madagascar': { flag: '🇲🇬', code: '+261' },
  'Malawi': { flag: '🇲🇼', code: '+265' },
  'Mali': { flag: '🇲🇱', code: '+223' },
  'Maroc': { flag: '🇲🇦', code: '+212' },
  'Maurice': { flag: '🇲🇺', code: '+230' },
  'Mauritanie': { flag: '🇲🇷', code: '+222' },
  'Mozambique': { flag: '🇲🇿', code: '+258' },
  'Namibie': { flag: '🇳🇦', code: '+264' },
  'Niger': { flag: '🇳🇪', code: '+227' },
  'Nigeria': { flag: '🇳🇬', code: '+234' },
  'Ouganda': { flag: '🇺🇬', code: '+256' },
  'RD Congo': { flag: '🇨🇩', code: '+243' },
  'République centrafricaine': { flag: '🇨🇫', code: '+236' },
  'Rwanda': { flag: '🇷🇼', code: '+250' },
  'Sao Tomé-et-Principe': { flag: '🇸🇹', code: '+239' },
  'Seychelles': { flag: '🇸🇨', code: '+248' },
  'Sierra Leone': { flag: '🇸🇱', code: '+232' },
  'Somalie': { flag: '🇸🇴', code: '+252' },
  'Soudan': { flag: '🇸🇩', code: '+249' },
  'Soudan du Sud': { flag: '🇸🇸', code: '+211' },
  'Tanzanie': { flag: '🇹🇿', code: '+255' },
  'Tchad': { flag: '🇹🇩', code: '+235' },
  'Togo': { flag: '🇹🇬', code: '+228' },
  'Tunisie': { flag: '🇹🇳', code: '+216' },
  'Zambie': { flag: '🇿🇲', code: '+260' },
  'Zimbabwe': { flag: '🇿🇼', code: '+263' },
  'France': { flag: '🇫🇷', code: '+33' },
  'Autre': { flag: '🌍', code: '' },
};
function getPhonePrefix(country) {
  return COUNTRY_PHONE_PREFIXES[country] || COUNTRY_PHONE_PREFIXES['Autre'];
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
