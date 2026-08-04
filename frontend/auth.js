/* ============================================================
   Carnet+ — Session (JWT en localStorage)
   Chargé avant api.js sur toutes les pages qui font des appels
   authentifiés ou qui doivent connaître le rôle courant.
   ============================================================ */

var CarnetAuth = (function () {
  var TOKEN_KEY = 'cp_token';
  var ROLE_KEY = 'cp_role';
  var IDENTITY_KEY = 'cp_identity';

  function saveSession(token, role) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(ROLE_KEY, role);
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function getRole() {
    return localStorage.getItem(ROLE_KEY);
  }

  // identity: { firstName, lastName, email, photoUrl }. Saved once at login
  // (see index.html) so the sidebar footer and dashboard greeting can show
  // the real logged-in user instead of the hardcoded mockup name — see
  // app.js's sidebar-identity block for where this is read back.
  function saveIdentity(identity) {
    localStorage.setItem(IDENTITY_KEY, JSON.stringify(identity));
  }

  function getIdentity() {
    var raw = localStorage.getItem(IDENTITY_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ROLE_KEY);
    localStorage.removeItem(IDENTITY_KEY);
  }

  function logout() {
    clearSession();
    window.location.href = '/index.html';
  }

  function requireAuth(expectedRole, redirectTo) {
    var token = getToken();
    var role = getRole();
    if (!token || role !== expectedRole) {
      window.location.href = redirectTo || '/index.html';
    }
  }

  return {
    saveSession: saveSession,
    getToken: getToken,
    getRole: getRole,
    saveIdentity: saveIdentity,
    getIdentity: getIdentity,
    clearSession: clearSession,
    logout: logout,
    requireAuth: requireAuth,
  };
})();

window.CarnetAuth = CarnetAuth;
