# Auth frontend/backend wiring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the static Carnet+ frontend (HTML/CSS/JS, no framework) to the existing FastAPI Auth module — registration, login, diploma upload, password reset — replacing hardcoded links with real API calls, while keeping `styles.css` untouched (no Tailwind).

**Architecture:** FastAPI serves `frontend/` as static files (single origin, no CORS). Two new shared scripts, `auth.js` (localStorage session) and `api.js` (fetch wrapper with auto Authorization header and typed errors), are loaded on every touched page before the page's own inline script.

**Tech Stack:** FastAPI `StaticFiles`, vanilla JS (`fetch`, `localStorage`, `sessionStorage`), existing `styles.css` classes (`.tabs`/`.tab`, `.hidden`) plus one new `.form-error` rule.

**Corrections found during planning vs. the approved spec** (`docs/superpowers/specs/2026-07-28-auth-frontend-backend-design.md`):
1. The spec assumed step 2 of doctor registration (`inscription-medecin.html`) could call `POST /auth/doctors/register` directly. It can't: `DoctorRegisterRequest` requires `specialty`/`license_number`/`practice_name`/`consultation_fee`, which are only collected in step 3. Fixed here: step 2 stores its fields in `sessionStorage` and only step 3 calls `register` (with the combined payload), then `login`, then diploma upload.
2. `inscription-medecin-2.html` has no field for `consultation_fee` (required, `float`, no default) — the mockup never included one. Task 7 adds a "Tarif de consultation" number input; without it every doctor registration would 422.
3. `Gender` only has two values in the backend. The forms currently offer a third "Autre" option. Task 5/6 drop "Autre" from the two registration forms' sex `<select>` (patient and doctor) — keeping it would 422 on submit.
4. **(Found during Task 4, 2026-07-28)** The user is independently changing the `Gender` enum values in `Backend-API/features/Auth/models.py` from `MALE`/`FEMALE` to `HOMME`/`FEMME` (in progress outside this plan — Alembic migration and tests to be updated by the user, not by this plan). Tasks 5/6 below use `value="homme"`/`value="femme"` on the sex `<select>` accordingly. If that backend change isn't finished yet when Tasks 5/6/7 are verified end-to-end, registration will 500 until it is — that's expected and out of scope for this plan to fix.

**No git repository exists in this project** (verified: `git rev-parse --is-inside-work-tree` fails at the project root). Every task below ends with a "Commit" step per the standard template; since there is nothing to commit to, that step is replaced with a one-line note. If the user initializes git later, these changes can be committed in one pass.

---

### Task 1: Backend serves the frontend

**Files:**
- Modify: `Backend-API/app.py`
- Test: `Backend-API/tests/test_static_frontend.py` (new)

- [ ] **Step 1: Write the failing test**

Create `Backend-API/tests/test_static_frontend.py`:

```python
async def test_frontend_index_served(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Carnet+" in resp.text


async def test_frontend_static_page_served(client):
    resp = await client.get("/choix-compte.html")
    assert resp.status_code == 200
    assert "Choisissez votre profil" in resp.text


async def test_api_routes_not_shadowed_by_static_mount(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd Backend-API && uv run pytest tests/test_static_frontend.py -v`
Expected: FAIL — `GET /` and `GET /choix-compte.html` return 404 (no static mount yet).

- [ ] **Step 3: Mount `frontend/` as static files in `app.py`**

Modify `Backend-API/app.py`. Add the import near the top (after the `fastapi` import):

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
```

Add this constant right after the router imports, before `lifespan`:

```python
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
```

Add the mount as the **very last statement** in the file, after the existing `@app.get("/health")` handler (mount order matters: routes registered earlier are matched first, so the catch-all mount for `/` must come last or it would never let `/health` or any other API route resolve):

```python
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd Backend-API && uv run pytest tests/test_static_frontend.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the full existing suite to confirm no regression**

Run: `cd Backend-API && uv run pytest -q`
Expected: all 27+ previous tests still pass, plus the 3 new ones (30 total).

- [ ] **Step 6: Commit**

No git repository — skip. (Files touched: `Backend-API/app.py`, `Backend-API/tests/test_static_frontend.py`.)

---

### Task 2: Shared frontend infrastructure — `auth.js` and `api.js`

No JS test runner exists in this project (no `package.json`, no bundler) and the approved design doesn't call for adding one — verification for this task is manual, via browser dev tools, in Step 3.

**Files:**
- Create: `frontend/auth.js`
- Create: `frontend/api.js`

- [ ] **Step 1: Create `frontend/auth.js`**

```javascript
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

  function requireAuth(expectedRole) {
    var token = getToken();
    var role = getRole();
    if (!token || role !== expectedRole) {
      window.location.href = '/index.html';
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
```

- [ ] **Step 2: Create `frontend/api.js`**

```javascript
/* ============================================================
   Carnet+ — Client API (fetch centralisé)
   Toute requête vers le backend passe par ici : header
   Authorization automatique, parsing JSON, erreurs typées.
   Nécessite auth.js chargé avant ce fichier.
   ============================================================ */

function ApiError(status, detail) {
  this.name = 'ApiError';
  this.status = status;
  this.detail = detail;
  this.message = typeof detail === 'string' ? detail : 'Une erreur est survenue.';
}
ApiError.prototype = Object.create(Error.prototype);

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
```

- [ ] **Step 3: Manual verification**

Run: `cd Backend-API && uv run uvicorn app:app --port 8010 --reload`
Open `http://localhost:8010/index.html`, open the browser dev tools console, and run:

```javascript
apiPost('/auth/patients/login', { email: 'nobody@example.com', password: 'wrongpassword' })
  .catch(e => console.log(e.status, e.detail));
```

Expected console output: `401 "Invalid credentials"` (or whatever the exact detail string is — check the actual response body in the Network tab). This confirms `api.js` correctly propagates FastAPI error bodies before any page wires a real form to it.

- [ ] **Step 4: Commit**

No git repository — skip. (Files touched: `frontend/auth.js`, `frontend/api.js`.)

---

### Task 3: `.form-error` style

**Files:**
- Modify: `frontend/styles.css:114-122` (Forms section)

- [ ] **Step 1: Add the rule**

In `frontend/styles.css`, right after the `.input-group input:focus { box-shadow: none; }` line (end of the "Forms" section, line 122), add:

```css
.form-error { color: var(--red); font-size: 13px; font-weight: 600; margin: 8px 0 0; }
```

- [ ] **Step 2: Manual verification**

Open any page in a browser later in this plan once `.form-error` elements exist (Task 4+) and confirm the text renders in red, 13px, bold-ish — no dedicated test, this is a one-line visual CSS addition.

- [ ] **Step 3: Commit**

No git repository — skip. (File touched: `frontend/styles.css`.)

---

### Task 4: `index.html` — connexion

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Replace the login card markup**

In `frontend/index.html`, replace this block (lines 56–85):

```html
          <div class="card" style="border-radius:20px;padding:28px;box-shadow:var(--sh-form);">
            <label class="label">ADRESSE EMAIL</label>
            <div class="input-group" style="margin-bottom:20px;">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="5" width="18" height="14" rx="2" />
                <path d="m3 7 9 6 9-6" />
              </svg>
              <input type="email" placeholder="votre@email.com">
            </div>
            <label class="label">MOT DE PASSE</label>
            <div class="input-group">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="4" y="10" width="16" height="10" rx="2" />
                <path d="M8 10V7a4 4 0 0 1 8 0v3" />
              </svg>
              <input type="password" placeholder="Mot de passe">
            </div>
            <div style="text-align:right;margin:12px 0 20px;">
              <a href="#" style="font-size:14px;font-weight:600;">Mot de passe oublié ?</a>
            </div>
            <a href="patient/dashboard.html" style="text-decoration:none;display:block;">
              <button class="btn btn--primary btn--block">Se connecter <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            </a>
          </div>
```

with:

```html
          <div class="card" style="border-radius:20px;padding:28px;box-shadow:var(--sh-form);">
            <div class="tabs" style="margin-bottom:20px;">
              <button type="button" class="tab active" id="role-patient" data-role="patient">Patient</button>
              <button type="button" class="tab" id="role-doctor" data-role="doctor">Médecin</button>
            </div>
            <form id="login-form">
              <label class="label">ADRESSE EMAIL</label>
              <div class="input-group" style="margin-bottom:20px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="5" width="18" height="14" rx="2" />
                  <path d="m3 7 9 6 9-6" />
                </svg>
                <input type="email" id="login-email" placeholder="votre@email.com" required>
              </div>
              <label class="label">MOT DE PASSE</label>
              <div class="input-group">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="4" y="10" width="16" height="10" rx="2" />
                  <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                </svg>
                <input type="password" id="login-password" placeholder="Mot de passe" required>
              </div>
              <p class="form-error hidden" id="login-error"></p>
              <div style="text-align:right;margin:12px 0 20px;">
                <a href="mot-de-passe-oublie.html" style="font-size:14px;font-weight:600;">Mot de passe oublié ?</a>
              </div>
              <button type="submit" class="btn btn--primary btn--block">Se connecter <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            </form>
          </div>
```

- [ ] **Step 2: Wire the scripts**

Replace the closing script line (line 99):

```html
  <script src="app.js"></script>
```

with:

```html
  <script src="auth.js"></script>
  <script src="api.js"></script>
  <script src="app.js"></script>
  <script>
    (function () {
      var selectedRole = 'patient';
      var patientTab = document.getElementById('role-patient');
      var doctorTab = document.getElementById('role-doctor');

      patientTab.addEventListener('click', function () {
        selectedRole = 'patient';
        patientTab.classList.add('active');
        doctorTab.classList.remove('active');
      });
      doctorTab.addEventListener('click', function () {
        selectedRole = 'doctor';
        doctorTab.classList.add('active');
        patientTab.classList.remove('active');
      });

      document.getElementById('login-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        var errorEl = document.getElementById('login-error');
        errorEl.classList.add('hidden');
        var email = document.getElementById('login-email').value;
        var password = document.getElementById('login-password').value;
        var path = selectedRole === 'patient' ? '/auth/patients/login' : '/auth/doctors/login';
        try {
          var data = await apiPost(path, { email: email, password: password });
          CarnetAuth.saveSession(data.access_token, selectedRole);
          window.location.href = selectedRole === 'patient' ? 'patient/dashboard.html' : 'medecin/dashboard.html';
        } catch (err) {
          errorEl.textContent = err.status === 401
            ? 'Email ou mot de passe incorrect.'
            : 'Une erreur est survenue, réessayez.';
          errorEl.classList.remove('hidden');
        }
      });
    })();
  </script>
```

- [ ] **Step 3: Manual verification**

With `uvicorn app:app --port 8010 --reload` running:
1. `POST /auth/patients/register` a test patient via `curl` (or reuse one from Task 5 once done).
2. Open `http://localhost:8010/index.html`, keep "Patient" selected, enter that email/password, submit.
3. Expected: redirected to `patient/dashboard.html`; dev tools → Application → Local Storage shows `cp_token` and `cp_role=patient`.
4. Reload `index.html`, submit with a wrong password.
5. Expected: red "Email ou mot de passe incorrect." message appears under the password field, no redirect, no `alert()`.

- [ ] **Step 4: Commit**

No git repository — skip. (File touched: `frontend/index.html`.)

---

### Task 5: `inscription-patient.html`

**Files:**
- Modify: `frontend/inscription-patient.html`

**Field mapping** (`PatientRegisterRequest`, `Backend-API/features/Auth/schemas.py:10-22`):

| Label mockup | id | champ API |
|---|---|---|
| NOM | `reg-last-name` | `last_name` |
| PRÉNOM | `reg-first-name` | `first_name` |
| DATE DE NAISSANCE | `reg-dob` | `date_of_birth` |
| LIEU DE NAISSANCE | `reg-pob` | `place_of_birth` |
| ADRESSE EMAIL | `reg-email` | `email` |
| TÉLÉPHONE | `reg-phone` | `phone_number` (préfixé `+221` en dur, cohérent avec l'indicatif affiché) |
| PAYS DE RÉSIDENCE | `reg-country` | `country_of_residence` |
| SEXE | `reg-gender` | `gender` (`homme`/`femme` — voir correction n°4 en tête de plan) |
| VILLE | `reg-city` | `city` |
| MOT DE PASSE | `reg-password` | `password` |
| CONFIRMER LE MOT DE PASSE | `reg-password-confirm` | `password_confirmation` |
| (fixe) | — | `address` — pas de champ "adresse" distinct dans le mockup ; réutilise `reg-pob` (lieu de naissance) comme valeur d'`address` faute de champ dédié — **limite connue**, à corriger si un vrai champ adresse est ajouté plus tard. |

- [ ] **Step 1: Replace the form markup**

Replace this block (lines 56–145):

```html
          <div class="card" style="border-radius:20px;padding:26px;box-shadow:var(--sh-form);">
            <div class="row" style="justify-content:space-between;margin-bottom:20px;">
              <a href="choix-compte.html" style="display:flex;align-items:center;gap:6px;font-weight:600;font-size:14px;color:var(--muted);">← Retour</a>
              <div class="row" style="gap:8px;background:#eef2ff;color:#5b6ef5;padding:6px 13px;border-radius:20px;font-weight:700;font-size:13px;">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#5b6ef5" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
                </svg>Patient
              </div>
            </div>
            <div class="grid-2" style="gap:14px;">
              <div>
                <label class="label" style="letter-spacing:0;">NOM</label>
                <input class="input" placeholder="Diallo">
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">PRÉNOM</label>
                <input class="input" placeholder="Fanta">
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">DATE DE NAISSANCE</label>
                <input class="input" type="date" placeholder="">
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">LIEU DE NAISSANCE</label>
                <input class="input" placeholder="Dakar">
              </div>
              <div style="grid-column:1 / -1;">
                <div>
                  <label class="label" style="letter-spacing:0;">ADRESSE EMAIL</label>
                  <input class="input" type="email" placeholder="votre@email.com">
                </div>
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">TÉLÉPHONE</label>
                <div class="input-group" style="border-radius:11px;">
                  <span style="font-size:16px;">🇸🇳</span>
                  <span style="font-weight:600;color:var(--muted);font-size:14px;">+221</span>
                  <input style="padding:12px 0;font-size:14.5px;">
                </div>
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">PAYS DE RÉSIDENCE</label>
                <select class="select">
                  <option>Sénégal</option>
                  <option>Congo</option>
                  <option>RD Congo</option>
                  <option>Cameroun</option>
                  <option>Gabon</option>
                  <option>Côte d'Ivoire</option>
                  <option>France</option>
                  <option>Autre</option>
                </select>
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">SEXE</label>
                <select class="select">
                  <option>Femme</option>
                  <option>Homme</option>
                  <option>Autre</option>
                </select>
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">VILLE</label>
                <input class="input" placeholder="Dakar">
              </div>
              <div style="grid-column:1 / -1;">
                <div>
                  <label class="label" style="letter-spacing:0;">MOT DE PASSE</label>
                  <input class="input" type="password" placeholder="Min. 10 caractères">
                </div>
              </div>
              <div style="grid-column:1 / -1;">
                <div>
                  <label class="label" style="letter-spacing:0;">CONFIRMER LE MOT DE PASSE</label>
                  <input class="input" type="password" placeholder="Confirmer">
                </div>
              </div>
            </div>
            <label style="display:flex;align-items:center;gap:12px;margin-top:18px;font-size:13.5px;color:var(--slate);cursor:pointer;line-height:1.5;background:var(--field);border:1px solid var(--border-2);border-radius:12px;padding:14px 16px;">
              <input type="checkbox" style="flex:none;width:18px;height:18px;accent-color:#10b981;cursor:pointer;">
              <span>J'ai lu et j'accepte la <a href="#">politique de confidentialité</a> de Carnet+.</span>
            </label>
            <a href="patient/dashboard.html" style="text-decoration:none;display:block;">
              <button class="btn btn--primary btn--block" style="margin-top:18px;">Soumettre <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            </a>
          </div>
```

with (only the `id`/`value` attributes, the "Autre" option removal, the `<form>` wrapper, the error paragraph, and the submit button change are new — everything else, including inline styles, is unchanged):

```html
          <div class="card" style="border-radius:20px;padding:26px;box-shadow:var(--sh-form);">
            <div class="row" style="justify-content:space-between;margin-bottom:20px;">
              <a href="choix-compte.html" style="display:flex;align-items:center;gap:6px;font-weight:600;font-size:14px;color:var(--muted);">← Retour</a>
              <div class="row" style="gap:8px;background:#eef2ff;color:#5b6ef5;padding:6px 13px;border-radius:20px;font-weight:700;font-size:13px;">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#5b6ef5" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
                </svg>Patient
              </div>
            </div>
            <form id="register-form">
              <div class="grid-2" style="gap:14px;">
                <div>
                  <label class="label" style="letter-spacing:0;">NOM</label>
                  <input class="input" id="reg-last-name" placeholder="Diallo" required>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">PRÉNOM</label>
                  <input class="input" id="reg-first-name" placeholder="Fanta" required>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">DATE DE NAISSANCE</label>
                  <input class="input" id="reg-dob" type="date" required>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">LIEU DE NAISSANCE</label>
                  <input class="input" id="reg-pob" placeholder="Dakar" required>
                </div>
                <div style="grid-column:1 / -1;">
                  <div>
                    <label class="label" style="letter-spacing:0;">ADRESSE EMAIL</label>
                    <input class="input" id="reg-email" type="email" placeholder="votre@email.com" required>
                  </div>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">TÉLÉPHONE</label>
                  <div class="input-group" style="border-radius:11px;">
                    <span style="font-size:16px;">🇸🇳</span>
                    <span style="font-weight:600;color:var(--muted);font-size:14px;">+221</span>
                    <input id="reg-phone" style="padding:12px 0;font-size:14.5px;" required>
                  </div>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">PAYS DE RÉSIDENCE</label>
                  <select class="select" id="reg-country">
                    <option>Sénégal</option>
                    <option>Congo</option>
                    <option>RD Congo</option>
                    <option>Cameroun</option>
                    <option>Gabon</option>
                    <option>Côte d'Ivoire</option>
                    <option>France</option>
                    <option>Autre</option>
                  </select>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">SEXE</label>
                  <select class="select" id="reg-gender">
                    <option value="femme">Femme</option>
                    <option value="homme">Homme</option>
                  </select>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">VILLE</label>
                  <input class="input" id="reg-city" placeholder="Dakar" required>
                </div>
                <div style="grid-column:1 / -1;">
                  <div>
                    <label class="label" style="letter-spacing:0;">MOT DE PASSE</label>
                    <input class="input" id="reg-password" type="password" placeholder="Min. 10 caractères" required minlength="10">
                  </div>
                </div>
                <div style="grid-column:1 / -1;">
                  <div>
                    <label class="label" style="letter-spacing:0;">CONFIRMER LE MOT DE PASSE</label>
                    <input class="input" id="reg-password-confirm" type="password" placeholder="Confirmer" required>
                  </div>
                </div>
              </div>
              <p class="form-error hidden" id="register-error"></p>
              <label style="display:flex;align-items:center;gap:12px;margin-top:18px;font-size:13.5px;color:var(--slate);cursor:pointer;line-height:1.5;background:var(--field);border:1px solid var(--border-2);border-radius:12px;padding:14px 16px;">
                <input type="checkbox" id="reg-consent" style="flex:none;width:18px;height:18px;accent-color:#10b981;cursor:pointer;" required>
                <span>J'ai lu et j'accepte la <a href="#">politique de confidentialité</a> de Carnet+.</span>
              </label>
              <button type="submit" class="btn btn--primary btn--block" style="margin-top:18px;">Soumettre <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            </form>
          </div>
```

- [ ] **Step 2: Wire the script**

Replace the closing script line (line 150):

```html
  <script src="app.js"></script>
```

with:

```html
  <script src="auth.js"></script>
  <script src="api.js"></script>
  <script src="app.js"></script>
  <script>
    (function () {
      document.getElementById('register-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        var errorEl = document.getElementById('register-error');
        errorEl.classList.add('hidden');

        var password = document.getElementById('reg-password').value;
        var passwordConfirm = document.getElementById('reg-password-confirm').value;
        if (password !== passwordConfirm) {
          errorEl.textContent = 'Les mots de passe ne correspondent pas.';
          errorEl.classList.remove('hidden');
          return;
        }

        var email = document.getElementById('reg-email').value;
        var placeOfBirth = document.getElementById('reg-pob').value;
        var payload = {
          first_name: document.getElementById('reg-first-name').value,
          last_name: document.getElementById('reg-last-name').value,
          date_of_birth: document.getElementById('reg-dob').value,
          place_of_birth: placeOfBirth,
          address: placeOfBirth,
          phone_number: '+221' + document.getElementById('reg-phone').value,
          country_of_residence: document.getElementById('reg-country').value,
          gender: document.getElementById('reg-gender').value,
          city: document.getElementById('reg-city').value,
          email: email,
          password: password,
          password_confirmation: passwordConfirm,
        };

        try {
          await apiPost('/auth/patients/register', payload);
          var loginData = await apiPost('/auth/patients/login', { email: email, password: password });
          CarnetAuth.saveSession(loginData.access_token, 'patient');
          window.location.href = 'patient/dashboard.html';
        } catch (err) {
          errorEl.textContent = err.status === 409
            ? 'Cet email est déjà utilisé.'
            : 'Vérifiez les champs renseignés.';
          errorEl.classList.remove('hidden');
        }
      });
    })();
  </script>
```

- [ ] **Step 3: Manual verification**

With uvicorn running, open `http://localhost:8010/inscription-patient.html`, fill every field (password ≥ 10 chars, matching confirmation), check the consent box, submit.
Expected: redirected to `patient/dashboard.html`, `cp_token`/`cp_role=patient` present in Local Storage.
Resubmit the exact same form (same email) a second time (reload the page first).
Expected: red "Cet email est déjà utilisé." message, no redirect.

- [ ] **Step 4: Commit**

No git repository — skip. (File touched: `frontend/inscription-patient.html`.)

---

### Task 6: `inscription-medecin.html` (étape 2 — pas d'appel API)

Per correction n°1: this step only collects fields locally and hands off to step 3 via `sessionStorage`. No backend call happens here.

**Files:**
- Modify: `frontend/inscription-medecin.html`

- [ ] **Step 1: Replace the form markup**

Replace this block (lines 60–145):

```html
          <div class="card" style="border-radius:20px;padding:26px;box-shadow:var(--sh-form);">
            <div class="row" style="justify-content:space-between;margin-bottom:20px;">
              <a href="choix-compte.html" style="display:flex;align-items:center;gap:6px;font-weight:600;font-size:14px;color:var(--muted);">← Retour</a>
              <div class="row" style="gap:8px;background:#eef2ff;color:#5b6ef5;padding:6px 13px;border-radius:20px;font-weight:700;font-size:13px;">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#5b6ef5" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
                </svg>Médecin
              </div>
            </div>
            <div class="grid-2" style="gap:14px;">
              <div>
                <label class="label" style="letter-spacing:0;">NOM</label>
                <input class="input" placeholder="Diallo">
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">PRÉNOM</label>
                <input class="input" placeholder="Fanta">
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">DATE DE NAISSANCE</label>
                <input class="input" type="date" placeholder="">
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">LIEU DE NAISSANCE</label>
                <input class="input" placeholder="Dakar">
              </div>
              <div style="grid-column:1 / -1;">
                <div>
                  <label class="label" style="letter-spacing:0;">ADRESSE EMAIL</label>
                  <input class="input" type="email" placeholder="votre@email.com">
                </div>
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">TÉLÉPHONE</label>
                <div class="input-group" style="border-radius:11px;">
                  <span style="font-size:16px;">🇸🇳</span>
                  <span style="font-weight:600;color:var(--muted);font-size:14px;">+221</span>
                  <input style="padding:12px 0;font-size:14.5px;">
                </div>
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">PAYS DE RÉSIDENCE</label>
                <select class="select">
                  <option>Sénégal</option>
                  <option>Congo</option>
                  <option>RD Congo</option>
                  <option>Cameroun</option>
                  <option>Gabon</option>
                  <option>Côte d'Ivoire</option>
                  <option>France</option>
                  <option>Autre</option>
                </select>
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">SEXE</label>
                <select class="select">
                  <option>Femme</option>
                  <option>Homme</option>
                  <option>Autre</option>
                </select>
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">VILLE</label>
                <input class="input" placeholder="Dakar">
              </div>
              <div style="grid-column:1 / -1;">
                <div>
                  <label class="label" style="letter-spacing:0;">MOT DE PASSE</label>
                  <input class="input" type="password" placeholder="Min. 10 caractères">
                </div>
              </div>
              <div style="grid-column:1 / -1;">
                <div>
                  <label class="label" style="letter-spacing:0;">CONFIRMER LE MOT DE PASSE</label>
                  <input class="input" type="password" placeholder="Confirmer">
                </div>
              </div>
            </div>
            <a href="inscription-medecin-2.html" style="text-decoration:none;display:block;">
              <button class="btn btn--primary btn--block" style="margin-top:18px;">Continuer <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            </a>
          </div>
```

with:

```html
          <div class="card" style="border-radius:20px;padding:26px;box-shadow:var(--sh-form);">
            <div class="row" style="justify-content:space-between;margin-bottom:20px;">
              <a href="choix-compte.html" style="display:flex;align-items:center;gap:6px;font-weight:600;font-size:14px;color:var(--muted);">← Retour</a>
              <div class="row" style="gap:8px;background:#eef2ff;color:#5b6ef5;padding:6px 13px;border-radius:20px;font-weight:700;font-size:13px;">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#5b6ef5" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
                </svg>Médecin
              </div>
            </div>
            <form id="step2-form">
              <div class="grid-2" style="gap:14px;">
                <div>
                  <label class="label" style="letter-spacing:0;">NOM</label>
                  <input class="input" id="reg-last-name" placeholder="Diallo" required>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">PRÉNOM</label>
                  <input class="input" id="reg-first-name" placeholder="Fanta" required>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">DATE DE NAISSANCE</label>
                  <input class="input" id="reg-dob" type="date" required>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">LIEU DE NAISSANCE</label>
                  <input class="input" id="reg-pob" placeholder="Dakar" required>
                </div>
                <div style="grid-column:1 / -1;">
                  <div>
                    <label class="label" style="letter-spacing:0;">ADRESSE EMAIL</label>
                    <input class="input" id="reg-email" type="email" placeholder="votre@email.com" required>
                  </div>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">TÉLÉPHONE</label>
                  <div class="input-group" style="border-radius:11px;">
                    <span style="font-size:16px;">🇸🇳</span>
                    <span style="font-weight:600;color:var(--muted);font-size:14px;">+221</span>
                    <input id="reg-phone" style="padding:12px 0;font-size:14.5px;" required>
                  </div>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">PAYS DE RÉSIDENCE</label>
                  <select class="select" id="reg-country">
                    <option>Sénégal</option>
                    <option>Congo</option>
                    <option>RD Congo</option>
                    <option>Cameroun</option>
                    <option>Gabon</option>
                    <option>Côte d'Ivoire</option>
                    <option>France</option>
                    <option>Autre</option>
                  </select>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">SEXE</label>
                  <select class="select" id="reg-gender">
                    <option value="femme">Femme</option>
                    <option value="homme">Homme</option>
                  </select>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">VILLE</label>
                  <input class="input" id="reg-city" placeholder="Dakar" required>
                </div>
                <div style="grid-column:1 / -1;">
                  <div>
                    <label class="label" style="letter-spacing:0;">MOT DE PASSE</label>
                    <input class="input" id="reg-password" type="password" placeholder="Min. 10 caractères" required minlength="10">
                  </div>
                </div>
                <div style="grid-column:1 / -1;">
                  <div>
                    <label class="label" style="letter-spacing:0;">CONFIRMER LE MOT DE PASSE</label>
                    <input class="input" id="reg-password-confirm" type="password" placeholder="Confirmer" required>
                  </div>
                </div>
              </div>
              <p class="form-error hidden" id="step2-error"></p>
              <button type="submit" class="btn btn--primary btn--block" style="margin-top:18px;">Continuer <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            </form>
          </div>
```

- [ ] **Step 2: Wire the script**

Replace the closing script line (line 150):

```html
  <script src="app.js"></script>
```

with:

```html
  <script src="app.js"></script>
  <script>
    (function () {
      document.getElementById('step2-form').addEventListener('submit', function (e) {
        e.preventDefault();
        var errorEl = document.getElementById('step2-error');
        errorEl.classList.add('hidden');

        var password = document.getElementById('reg-password').value;
        var passwordConfirm = document.getElementById('reg-password-confirm').value;
        if (password !== passwordConfirm) {
          errorEl.textContent = 'Les mots de passe ne correspondent pas.';
          errorEl.classList.remove('hidden');
          return;
        }

        var placeOfBirth = document.getElementById('reg-pob').value;
        var step2Data = {
          first_name: document.getElementById('reg-first-name').value,
          last_name: document.getElementById('reg-last-name').value,
          date_of_birth: document.getElementById('reg-dob').value,
          place_of_birth: placeOfBirth,
          email: document.getElementById('reg-email').value,
          phone_number: '+221' + document.getElementById('reg-phone').value,
          country_of_residence: document.getElementById('reg-country').value,
          gender: document.getElementById('reg-gender').value,
          city: document.getElementById('reg-city').value,
          password: password,
          password_confirmation: passwordConfirm,
        };

        sessionStorage.setItem('cp_doctor_step2', JSON.stringify(step2Data));
        window.location.href = 'inscription-medecin-2.html';
      });
    })();
  </script>
```

Note: this page does not need `auth.js`/`api.js` since it makes no API call — only `app.js` (already present) is kept.

- [ ] **Step 3: Manual verification**

Open `http://localhost:8010/inscription-medecin.html`, fill all fields with mismatched passwords, submit.
Expected: red "Les mots de passe ne correspondent pas." message, stays on the page.
Fix the confirmation to match, submit again.
Expected: navigates to `inscription-medecin-2.html`; dev tools → Application → Session Storage shows `cp_doctor_step2` with the entered JSON.

- [ ] **Step 4: Commit**

No git repository — skip. (File touched: `frontend/inscription-medecin.html`.)

---

### Task 7: `inscription-medecin-2.html` (étape 3 — register + login + diplôme)

Per correction n°2, this task adds a "Tarif de consultation" field that doesn't exist in the current mockup.

**Files:**
- Modify: `frontend/inscription-medecin-2.html`

- [ ] **Step 1: Replace the form markup**

Replace this block (lines 64–117):

```html
          <div class="card" style="border-radius:20px;padding:26px;box-shadow:var(--sh-form);">
            <div class="row" style="justify-content:space-between;margin-bottom:20px;">
              <a href="inscription-medecin.html" style="display:flex;align-items:center;gap:6px;font-weight:600;font-size:14px;color:var(--muted);">← Retour</a>
              <div class="row" style="gap:8px;background:#eef2ff;color:#5b6ef5;padding:6px 13px;border-radius:20px;font-weight:700;font-size:13px;">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#5b6ef5" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
                </svg>Médecin
              </div>
            </div>
            <div class="grid-2" style="gap:14px;">
              <div>
                <label class="label" style="letter-spacing:0;">SPÉCIALITÉ</label>
                <input class="input" placeholder="Médecine générale">
              </div>
              <div>
                <label class="label" style="letter-spacing:0;">N° D'ORDRE (ONM)</label>
                <input class="input" placeholder="SN-00000">
              </div>
              <div style="grid-column:1 / -1;">
                <div>
                  <label class="label" style="letter-spacing:0;">ÉTABLISSEMENT / CABINET</label>
                  <input class="input" placeholder="Cabinet Elikia, CHU Brazzaville…">
                </div>
              </div>
              <div style="grid-column:1 / -1;">
                <label class="label" style="letter-spacing:0;">DIPLÔME / JUSTIFICATIF</label>
                <div style="border:1.5px dashed #cfd8dd;border-radius:11px;padding:16px;text-align:center;color:var(--muted);font-size:13.5px;background:var(--field);cursor:pointer;">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 16V4M6 10l6-6 6 6" />
                    <path d="M4 20h16" />
                  </svg>
                  <div style="margin-top:6px;">Téléverser votre diplôme (PDF, JPG)</div>
                </div>
              </div>
            </div>
            <div style="display:flex;gap:10px;background:var(--amber-bg);border:1px solid #fed7aa;border-radius:12px;padding:13px 15px;margin-top:18px;">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ea8a12" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 9v4M12 17h.01" />
                <path d="M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6A2 2 0 0 0 22 18L13.7 3.9a2 2 0 0 0-3.4 0Z" />
              </svg>
              <div style="font-size:13px;color:var(--amber-ink);line-height:1.5;">Le compte médecin doit être <strong>validé par un administrateur</strong> après vérification de vos justificatifs avant d'être activé.</div>
            </div>
            <label style="display:flex;align-items:center;gap:12px;margin-top:18px;font-size:13.5px;color:var(--slate);cursor:pointer;line-height:1.5;background:var(--field);border:1px solid var(--border-2);border-radius:12px;padding:14px 16px;">
              <input type="checkbox" style="flex:none;width:18px;height:18px;accent-color:#10b981;cursor:pointer;">
              <span>J'ai lu et j'accepte la <a href="#">politique de confidentialité</a> de Carnet+.</span>
            </label>
            <a href="en-attente.html" style="text-decoration:none;display:block;">
              <button class="btn btn--primary btn--block" style="margin-top:18px;">Soumettre <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            </a>
          </div>
```

with:

```html
          <div class="card" style="border-radius:20px;padding:26px;box-shadow:var(--sh-form);">
            <div class="row" style="justify-content:space-between;margin-bottom:20px;">
              <a href="inscription-medecin.html" style="display:flex;align-items:center;gap:6px;font-weight:600;font-size:14px;color:var(--muted);">← Retour</a>
              <div class="row" style="gap:8px;background:#eef2ff;color:#5b6ef5;padding:6px 13px;border-radius:20px;font-weight:700;font-size:13px;">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#5b6ef5" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="8" r="4" />
                  <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
                </svg>Médecin
              </div>
            </div>
            <form id="step3-form">
              <div class="grid-2" style="gap:14px;">
                <div>
                  <label class="label" style="letter-spacing:0;">SPÉCIALITÉ</label>
                  <input class="input" id="reg-specialty" placeholder="Médecine générale" required>
                </div>
                <div>
                  <label class="label" style="letter-spacing:0;">N° D'ORDRE (ONM)</label>
                  <input class="input" id="reg-license" placeholder="SN-00000" required>
                </div>
                <div style="grid-column:1 / -1;">
                  <div>
                    <label class="label" style="letter-spacing:0;">ÉTABLISSEMENT / CABINET</label>
                    <input class="input" id="reg-practice" placeholder="Cabinet Elikia, CHU Brazzaville…" required>
                  </div>
                </div>
                <div style="grid-column:1 / -1;">
                  <div>
                    <label class="label" style="letter-spacing:0;">TARIF DE CONSULTATION (FCFA)</label>
                    <input class="input" id="reg-fee" type="number" min="0" step="0.01" placeholder="15000" required>
                  </div>
                </div>
                <div style="grid-column:1 / -1;">
                  <label class="label" style="letter-spacing:0;">DIPLÔME / JUSTIFICATIF</label>
                  <label for="reg-diploma" style="display:block;border:1.5px dashed #cfd8dd;border-radius:11px;padding:16px;text-align:center;color:var(--muted);font-size:13.5px;background:var(--field);cursor:pointer;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M12 16V4M6 10l6-6 6 6" />
                      <path d="M4 20h16" />
                    </svg>
                    <div style="margin-top:6px;" id="reg-diploma-label">Téléverser votre diplôme (PDF, JPG)</div>
                    <input type="file" id="reg-diploma" class="hidden" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/*" required>
                  </label>
                </div>
              </div>
              <div style="display:flex;gap:10px;background:var(--amber-bg);border:1px solid #fed7aa;border-radius:12px;padding:13px 15px;margin-top:18px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ea8a12" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M12 9v4M12 17h.01" />
                  <path d="M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6A2 2 0 0 0 22 18L13.7 3.9a2 2 0 0 0-3.4 0Z" />
                </svg>
                <div style="font-size:13px;color:var(--amber-ink);line-height:1.5;">Le compte médecin doit être <strong>validé par un administrateur</strong> après vérification de vos justificatifs avant d'être activé.</div>
              </div>
              <p class="form-error hidden" id="step3-error"></p>
              <label style="display:flex;align-items:center;gap:12px;margin-top:18px;font-size:13.5px;color:var(--slate);cursor:pointer;line-height:1.5;background:var(--field);border:1px solid var(--border-2);border-radius:12px;padding:14px 16px;">
                <input type="checkbox" id="reg-consent" style="flex:none;width:18px;height:18px;accent-color:#10b981;cursor:pointer;" required>
                <span>J'ai lu et j'accepte la <a href="#">politique de confidentialité</a> de Carnet+.</span>
              </label>
              <button type="submit" class="btn btn--primary btn--block" style="margin-top:18px;" id="step3-submit">Soumettre <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            </form>
          </div>
```

- [ ] **Step 2: Wire the script**

Replace the closing script line (line 122):

```html
  <script src="app.js"></script>
```

with:

```html
  <script src="auth.js"></script>
  <script src="api.js"></script>
  <script src="app.js"></script>
  <script>
    (function () {
      var step2Raw = sessionStorage.getItem('cp_doctor_step2');
      if (!step2Raw) {
        window.location.href = 'inscription-medecin.html';
        return;
      }
      var step2Data = JSON.parse(step2Raw);

      document.getElementById('reg-diploma').addEventListener('change', function (e) {
        var file = e.target.files[0];
        document.getElementById('reg-diploma-label').textContent = file ? file.name : 'Téléverser votre diplôme (PDF, JPG)';
      });

      document.getElementById('step3-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        var errorEl = document.getElementById('step3-error');
        errorEl.classList.add('hidden');
        var submitBtn = document.getElementById('step3-submit');

        var diplomaFile = document.getElementById('reg-diploma').files[0];
        if (!diplomaFile) {
          errorEl.textContent = 'Le diplôme est obligatoire.';
          errorEl.classList.remove('hidden');
          return;
        }

        var payload = Object.assign({}, step2Data, {
          specialty: document.getElementById('reg-specialty').value,
          license_number: document.getElementById('reg-license').value,
          practice_name: document.getElementById('reg-practice').value,
          consultation_fee: parseFloat(document.getElementById('reg-fee').value),
        });

        submitBtn.disabled = true;
        try {
          await apiPost('/auth/doctors/register', payload);
          var loginData = await apiPost('/auth/doctors/login', {
            email: step2Data.email,
            password: step2Data.password,
          });
          CarnetAuth.saveSession(loginData.access_token, 'doctor');

          var formData = new FormData();
          formData.append('diploma_file', diplomaFile);
          await apiPostForm('/auth/doctors/me/diploma', formData);

          CarnetAuth.clearSession();
          sessionStorage.removeItem('cp_doctor_step2');
          window.location.href = 'en-attente.html';
        } catch (err) {
          submitBtn.disabled = false;
          errorEl.textContent = err.status === 409
            ? 'Cet email est déjà utilisé.'
            : 'Une erreur est survenue, réessayez.';
          errorEl.classList.remove('hidden');
        }
      });
    })();
  </script>
```

- [ ] **Step 3: Manual verification**

Complete Task 6's manual verification first (so `cp_doctor_step2` is populated), then on `inscription-medecin-2.html`: fill specialty/license/practice/fee, choose any small file for the diploma, check consent, submit.
Expected: redirected to `en-attente.html`; Local Storage has no `cp_token`/`cp_role` (cleared); Session Storage no longer has `cp_doctor_step2`.
Verify server-side: `curl -X POST http://localhost:8010/auth/admin/login -H "Content-Type: application/json" -d '{"email":"<admin email>","password":"<admin password>"}'` then `GET /admin/doctors/pending` with that token — the new doctor should appear with a `diploma_url`.
Also test the guard: open `inscription-medecin-2.html` directly in a fresh tab (no `cp_doctor_step2` in session storage) — expect immediate redirect to `inscription-medecin.html`.

- [ ] **Step 4: Commit**

No git repository — skip. (File touched: `frontend/inscription-medecin-2.html`.)

---

### Task 8: `mot-de-passe-oublie.html` (new page)

**Files:**
- Create: `frontend/mot-de-passe-oublie.html`

- [ ] **Step 1: Create the page**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mot de passe oublié — Carnet+</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="auth">
    <div class="auth__brand">
      <div class="auth__blob" style="top:-90px;right:-60px;width:340px;height:340px;"></div>
      <div class="auth__blob" style="bottom:60px;right:-40px;width:260px;height:260px;background:rgba(255,255,255,.06);"></div>
      <div class="row" style="gap:13px;position:relative;">
        <div class="logo-mark" style="width:52px;height:52px;">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
            <path d="M2 21c0-3 1.85-5.36 5.08-6" />
          </svg>
        </div>
        <div style="font-size:26px;font-weight:800;letter-spacing:-.02em;">Carnet<span class="brand-accent">+</span>
        </div>
      </div>
      <div style="position:relative;">
        <h1>Votre santé,
          <br>
          <span class="brand-accent">connectée</span> et
          <br>simplifiée.
        </h1>
        <p>Téléconsultation, ordonnances, carnet de santé et suivi médical — tout le cabinet en un seul endroit.</p>
      </div>
      <div style="position:relative;font-size:13px;color:rgba(255,255,255,.7);">© 2026 Carnet+ — Plateforme de santé numérique</div>
    </div>
    <div class="auth__form">
      <div class="auth__inner">
        <div class="fade">
          <h2 style="font-size:34px;font-weight:800;letter-spacing:-.02em;margin:0 0 8px;">Mot de passe oublié ?</h2>
          <p class="subtitle" style="margin-bottom:30px;">Indiquez votre email, nous vous enverrons un lien de réinitialisation.</p>
          <div class="card" style="border-radius:20px;padding:28px;box-shadow:var(--sh-form);">
            <form id="forgot-form">
              <label class="label">ADRESSE EMAIL</label>
              <div class="input-group" style="margin-bottom:12px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="3" y="5" width="18" height="14" rx="2" />
                  <path d="m3 7 9 6 9-6" />
                </svg>
                <input type="email" id="forgot-email" placeholder="votre@email.com" required>
              </div>
              <p class="form-error hidden" id="forgot-message"></p>
              <button type="submit" class="btn btn--primary btn--block" style="margin-top:6px;">Envoyer le lien</button>
            </form>
          </div>
          <div style="text-align:center;margin-top:26px;">
            <a href="index.html" style="font-weight:700;font-size:15px;">← Retour à la connexion</a>
          </div>
        </div>
      </div>
    </div>
  </div>
  <script src="auth.js"></script>
  <script src="api.js"></script>
  <script src="app.js"></script>
  <script>
    (function () {
      document.getElementById('forgot-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        var messageEl = document.getElementById('forgot-message');
        var email = document.getElementById('forgot-email').value;
        try {
          await apiPost('/auth/forgot-password', { email: email });
        } catch (err) {
          // L'API renvoie toujours 202 par design anti-énumération d'emails ;
          // seule une erreur réseau/serveur atteint ce bloc.
        }
        messageEl.style.color = 'var(--green-text)';
        messageEl.textContent = 'Si cet email est enregistré, un lien de réinitialisation a été envoyé.';
        messageEl.classList.remove('hidden');
      });
    })();
  </script>
</body>
</html>
```

- [ ] **Step 2: Manual verification**

Open `http://localhost:8010/mot-de-passe-oublie.html`, submit with any email (registered or not).
Expected: green confirmation message appears in both cases, no redirect. Check the backend log / Resend dashboard (or the no-op stub in dev if no real key is set) to confirm `POST /auth/forgot-password` was called.

- [ ] **Step 3: Commit**

No git repository — skip. (File created: `frontend/mot-de-passe-oublie.html`.)

---

### Task 9: `reinitialiser-mot-de-passe.html` (new page)

**Files:**
- Create: `frontend/reinitialiser-mot-de-passe.html`

- [ ] **Step 1: Create the page**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Réinitialiser le mot de passe — Carnet+</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="auth">
    <div class="auth__brand">
      <div class="auth__blob" style="top:-90px;right:-60px;width:340px;height:340px;"></div>
      <div class="auth__blob" style="bottom:60px;right:-40px;width:260px;height:260px;background:rgba(255,255,255,.06);"></div>
      <div class="row" style="gap:13px;position:relative;">
        <div class="logo-mark" style="width:52px;height:52px;">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
            <path d="M2 21c0-3 1.85-5.36 5.08-6" />
          </svg>
        </div>
        <div style="font-size:26px;font-weight:800;letter-spacing:-.02em;">Carnet<span class="brand-accent">+</span>
        </div>
      </div>
      <div style="position:relative;">
        <h1>Votre santé,
          <br>
          <span class="brand-accent">connectée</span> et
          <br>simplifiée.
        </h1>
        <p>Téléconsultation, ordonnances, carnet de santé et suivi médical — tout le cabinet en un seul endroit.</p>
      </div>
      <div style="position:relative;font-size:13px;color:rgba(255,255,255,.7);">© 2026 Carnet+ — Plateforme de santé numérique</div>
    </div>
    <div class="auth__form">
      <div class="auth__inner">
        <div class="fade" id="reset-panel">
          <h2 style="font-size:34px;font-weight:800;letter-spacing:-.02em;margin:0 0 8px;">Nouveau mot de passe</h2>
          <p class="subtitle" style="margin-bottom:30px;">Choisissez un nouveau mot de passe (10 caractères minimum).</p>
          <div class="card" style="border-radius:20px;padding:28px;box-shadow:var(--sh-form);">
            <form id="reset-form">
              <label class="label">NOUVEAU MOT DE PASSE</label>
              <div class="input-group" style="margin-bottom:20px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="4" y="10" width="16" height="10" rx="2" />
                  <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                </svg>
                <input type="password" id="reset-password" placeholder="Min. 10 caractères" required minlength="10">
              </div>
              <label class="label">CONFIRMER LE MOT DE PASSE</label>
              <div class="input-group">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9aa7b4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="4" y="10" width="16" height="10" rx="2" />
                  <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                </svg>
                <input type="password" id="reset-password-confirm" placeholder="Confirmer" required>
              </div>
              <p class="form-error hidden" id="reset-error"></p>
              <button type="submit" class="btn btn--primary btn--block" style="margin-top:16px;">Réinitialiser</button>
            </form>
          </div>
        </div>
        <div class="fade hidden" id="reset-success" style="text-align:center;">
          <div style="width:84px;height:84px;border-radius:24px;background:var(--green-soft);display:flex;align-items:center;justify-content:center;margin:0 auto 24px;">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 6 9 17l-5-5" />
            </svg>
          </div>
          <h2 style="font-size:28px;font-weight:800;letter-spacing:-.02em;margin:0 0 12px;">Mot de passe mis à jour</h2>
          <p style="color:var(--muted);font-size:15px;line-height:1.6;margin:0 auto 26px;max-width:360px;">Vous pouvez maintenant vous connecter avec votre nouveau mot de passe.</p>
          <a href="index.html" style="text-decoration:none;display:block;">
            <button class="btn btn--primary btn--block">Se connecter</button>
          </a>
        </div>
      </div>
    </div>
  </div>
  <script src="auth.js"></script>
  <script src="api.js"></script>
  <script src="app.js"></script>
  <script>
    (function () {
      var token = new URLSearchParams(window.location.search).get('token');

      document.getElementById('reset-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        var errorEl = document.getElementById('reset-error');
        errorEl.classList.add('hidden');

        if (!token) {
          errorEl.textContent = 'Lien invalide : aucun token trouvé dans l\'URL.';
          errorEl.classList.remove('hidden');
          return;
        }

        var password = document.getElementById('reset-password').value;
        var passwordConfirm = document.getElementById('reset-password-confirm').value;
        if (password !== passwordConfirm) {
          errorEl.textContent = 'Les mots de passe ne correspondent pas.';
          errorEl.classList.remove('hidden');
          return;
        }

        try {
          await apiPost('/auth/reset-password', {
            token: token,
            new_password: password,
            new_password_confirmation: passwordConfirm,
          });
          document.getElementById('reset-panel').classList.add('hidden');
          document.getElementById('reset-success').classList.remove('hidden');
        } catch (err) {
          errorEl.textContent = 'Ce lien est invalide ou a expiré.';
          errorEl.classList.remove('hidden');
        }
      });
    })();
  </script>
</body>
</html>
```

- [ ] **Step 2: Manual verification**

Trigger `POST /auth/forgot-password` for a registered patient (via Task 8's page or `curl`), retrieve the reset token (dev: read it directly from the `password_reset_tokens` table since Resend test mode only delivers to the Resend account's own email — see `Backend-API/CLAUDE.md`).
Open `http://localhost:8010/reinitialiser-mot-de-passe.html?token=<token>`, set a new password (≥10 chars, matching confirmation), submit.
Expected: success panel replaces the form; logging in on `index.html` with the new password succeeds; the old password is rejected (401).
Also test with `?token=invalid`: expect "Ce lien est invalide ou a expiré."

- [ ] **Step 3: Commit**

No git repository — skip. (File created: `frontend/reinitialiser-mot-de-passe.html`.)

---

### Task 10: Full end-to-end walkthrough

**Files:** none (verification only)

- [ ] **Step 1: Run the backend test suite one more time**

Run: `cd Backend-API && uv run pytest -q`
Expected: all tests pass (no regression introduced by the frontend changes, which don't touch backend logic besides the Task 1 static mount).

- [ ] **Step 2: Full manual walkthrough with a fresh browser profile (or Incognito, to start with empty storage)**

With `uv run uvicorn app:app --port 8010 --reload` running:
1. `http://localhost:8010/index.html` → "Créer un compte" → `choix-compte.html` → "Patient".
2. Fill and submit `inscription-patient.html` → expect landing on `patient/dashboard.html` (still showing example data — out of scope for this tranche) with a valid session in Local Storage.
3. Log out manually (dev tools: clear Local Storage), go back to `index.html`, log back in as that same patient → expect success.
4. `index.html` → "Créer un compte" → `choix-compte.html` → "Médecin" → fill `inscription-medecin.html` → fill `inscription-medecin-2.html` including a diploma file → expect landing on `en-attente.html`.
5. Log in as an admin (existing test tooling or a manually seeded admin — see `tests/conftest.py:admin_token` for the pattern) via `POST /admin/doctors/{id}/validate` to validate that doctor, then confirm `POST /auth/doctors/login` on `index.html` (role "Médecin") now succeeds and redirects toward `medecin/dashboard.html`.
6. `index.html` → "Mot de passe oublié ?" → request a reset for the patient created in step 2 → retrieve the token from the database → complete `reinitialiser-mot-de-passe.html` → confirm login with the new password works and the old one is rejected.

Expected: every step above completes without a raw `alert()`, without an uncaught JS error in the console, and without a broken redirect.

- [ ] **Step 3: Commit**

No git repository — skip. This closes the Auth tranche; the next tranche (dashboards) gets its own spec and plan.
