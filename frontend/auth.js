/* ============================================================
   Carnet+ — Session (JWT en localStorage)
   Chargé avant api.js sur toutes les pages qui font des appels
   authentifiés ou qui doivent connaître le rôle courant.
   ============================================================ */

var CarnetAuth = (function () {
  var TOKEN_KEY = 'cp_token';
  var ROLE_KEY = 'cp_role';

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

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(ROLE_KEY);
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
    clearSession: clearSession,
    logout: logout,
    requireAuth: requireAuth,
  };
})();

window.CarnetAuth = CarnetAuth;
