# Doctor Availability Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the doctor dashboard's "Disponible / Indisponible" toggle real — when a doctor marks themself unavailable, patients can no longer book a new appointment with them (enforced server-side, not just visually).

**Architecture:** A new `is_available` boolean column on `Doctor` (default `true`), exposed through the existing `PATCH /doctors/me` (write) and `GET /doctors` / `GET /doctors/{id}` (read) endpoints — no new routes. `Appointments.book_appointment` rejects booking with `409` when the target doctor is unavailable. Three frontend pages read/write the flag: the doctor dashboard toggle persists it; the patient search grid and doctor detail page grey out booking when it's `false`.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic (backend), vanilla JS + `fetch` via `api.js` (frontend). Backend tests: `pytest` against SQLite (`tests/conftest.py`).

**Spec:** `docs/superpowers/specs/2026-08-06-doctor-availability-toggle-design.md`

---

### Task 1: `Doctor.is_available` column + migration

**Files:**
- Modify: `Backend-API/features/Auth/models.py:1-104`
- Create: `Backend-API/alembic/versions/bd13bdd8f230_add_doctor_is_available.py`

- [ ] **Step 1: Add the column to the `Doctor` model**

In `Backend-API/features/Auth/models.py`, the import line (line 7) currently reads:

```python
from sqlalchemy import Date, DateTime, Enum, Numeric, String, false, func
```

Change it to also import `true`:

```python
from sqlalchemy import Date, DateTime, Enum, Numeric, String, false, func, true
```

Then, in the `Doctor` class (starts at line 73), add the new column right after `consultation_fee` and before `status`:

```python
    consultation_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    is_available: Mapped[bool] = mapped_column(default=True, server_default=true())
    status: Mapped[DoctorStatus] = mapped_column(
        Enum(DoctorStatus), default=DoctorStatus.PENDING_VALIDATION
    )
```

(Same pattern as `Patient.email_verified: Mapped[bool] = mapped_column(default=False, server_default=false())` a few lines above in the same file — a Python-level default for the ORM, plus a `server_default` so the column is safe to add as `NOT NULL` on a table that may already have rows.)

- [ ] **Step 2: Verify the module still imports cleanly**

Run: `cd Backend-API && uv run python -c "import features.Auth.models"`
Expected: no output, exit code 0.

- [ ] **Step 3: Write the Alembic migration**

Create `Backend-API/alembic/versions/bd13bdd8f230_add_doctor_is_available.py`:

```python
"""add doctor is_available

Revision ID: bd13bdd8f230
Revises: 753e41e43e00
Create Date: 2026-08-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bd13bdd8f230"
down_revision: Union[str, Sequence[str], None] = "753e41e43e00"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "doctors",
        sa.Column(
            "is_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("doctors", "is_available")
```

`753e41e43e00` is the current migration head (`Backend-API/alembic/versions/753e41e43e00_prescription_appointment_id_nullable.py`) — verify this is still true before creating the file:

Run: `cd Backend-API && uv run alembic heads`
Expected: `753e41e43e00 (head)`. If a different revision is now the head, use that one as `down_revision` instead.

- [ ] **Step 4: Commit**

```bash
git add Backend-API/features/Auth/models.py Backend-API/alembic/versions/bd13bdd8f230_add_doctor_is_available.py
git commit -m "feat: add Doctor.is_available column"
```

---

### Task 2: Expose `is_available` through the Doctors API (read + write)

**Files:**
- Modify: `Backend-API/features/Doctors/schemas.py`
- Modify: `Backend-API/features/Doctors/logic.py:24-36`
- Test: `Backend-API/tests/test_appointments_flow.py`

- [ ] **Step 1: Write the failing tests**

Append to `Backend-API/tests/test_appointments_flow.py`:

```python
async def test_doctor_defaults_available_in_search(client, validated_doctor):
    resp = await client.get("/doctors", params={"specialty": "Cardio"})
    assert resp.status_code == 200
    doctor = next(d for d in resp.json() if d["id"] == validated_doctor["id"])
    assert doctor["is_available"] is True


async def test_doctor_can_toggle_availability(client, validated_doctor):
    patch = await client.patch(
        "/doctors/me",
        json={"is_available": False},
        headers=_auth(validated_doctor["token"]),
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["is_available"] is False

    resp = await client.get(f"/doctors/{validated_doctor['id']}")
    assert resp.status_code == 200
    assert resp.json()["is_available"] is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd Backend-API && uv run python -m pytest tests/test_appointments_flow.py -k "availab" -v`
Expected: both tests FAIL — `test_doctor_defaults_available_in_search` with a `KeyError: 'is_available'`, `test_doctor_can_toggle_availability` with `422 Unprocessable Entity` (the field isn't accepted yet) or a similar schema-validation failure.

- [ ] **Step 3: Add `is_available` to the schemas**

In `Backend-API/features/Doctors/schemas.py`, `DoctorPublicOut` currently ends with `photo_url`:

```python
class DoctorPublicOut(BaseModel):
    """What a patient sees when searching for a doctor to book with."""

    id: int
    first_name: str
    last_name: str
    specialty: str
    practice_name: str
    city: str
    consultation_fee: float
    photo_url: str | None
    is_available: bool

    model_config = {"from_attributes": True}
```

(`DoctorProfileOut` inherits from `DoctorPublicOut`, so it picks up the field automatically — no change needed there.)

`DoctorProfileUpdateRequest` currently reads:

```python
class DoctorProfileUpdateRequest(BaseModel):
    phone_number: str | None = None
    practice_name: str | None = None
    consultation_fee: float | None = None
```

Add the new optional field:

```python
class DoctorProfileUpdateRequest(BaseModel):
    phone_number: str | None = None
    practice_name: str | None = None
    consultation_fee: float | None = None
    is_available: bool | None = None
```

(`update_doctor_profile` in `logic.py` already applies whichever fields are set via `data.model_dump(exclude_unset=True)` — no change needed there.)

- [ ] **Step 4: Add `is_available` to `build_public_out`**

In `Backend-API/features/Doctors/logic.py`, `build_public_out` (lines 24-36) currently reads:

```python
def build_public_out(doctor: Doctor) -> DoctorPublicOut:
    return DoctorPublicOut(
        id=doctor.id,
        first_name=doctor.first_name,
        last_name=doctor.last_name,
        specialty=doctor.specialty,
        practice_name=doctor.practice_name,
        city=doctor.city,
        consultation_fee=float(doctor.consultation_fee),
        photo_url=get_file_url(doctor.photo_file_key)
        if doctor.photo_file_key
        else None,
    )
```

Add the new field:

```python
def build_public_out(doctor: Doctor) -> DoctorPublicOut:
    return DoctorPublicOut(
        id=doctor.id,
        first_name=doctor.first_name,
        last_name=doctor.last_name,
        specialty=doctor.specialty,
        practice_name=doctor.practice_name,
        city=doctor.city,
        consultation_fee=float(doctor.consultation_fee),
        photo_url=get_file_url(doctor.photo_file_key)
        if doctor.photo_file_key
        else None,
        is_available=doctor.is_available,
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd Backend-API && uv run python -m pytest tests/test_appointments_flow.py -k "availab" -v`
Expected: both tests PASS.

- [ ] **Step 6: Run the full backend suite to check nothing else broke**

Run: `cd Backend-API && uv run python -m pytest -q`
Expected: all tests pass (the suite was at 81 tests before this plan; expect 81 + new tests, all green).

- [ ] **Step 7: Commit**

```bash
git add Backend-API/features/Doctors/schemas.py Backend-API/features/Doctors/logic.py Backend-API/tests/test_appointments_flow.py
git commit -m "feat: expose Doctor.is_available on the public/profile API"
```

---

### Task 3: Reject booking when the doctor is unavailable

**Files:**
- Modify: `Backend-API/features/Appointments/logic.py:86-120`
- Test: `Backend-API/tests/test_appointments_flow.py`

- [ ] **Step 1: Write the failing test**

Append to `Backend-API/tests/test_appointments_flow.py`:

```python
async def test_booking_rejected_when_doctor_unavailable(client, patient, validated_doctor):
    doctor_headers = _auth(validated_doctor["token"])
    slot = await client.post(
        "/appointments/availabilities",
        json={
            "date": date.today().isoformat(),
            "start_time": "13:00:00",
            "end_time": "13:30:00",
        },
        headers=doctor_headers,
    )
    assert slot.status_code == 201, slot.text
    availability_id = slot.json()["id"]

    toggle = await client.patch(
        "/doctors/me", json={"is_available": False}, headers=doctor_headers
    )
    assert toggle.status_code == 200, toggle.text

    booking = await client.post(
        "/appointments",
        json={"availability_id": availability_id, "mode": "in_person"},
        headers=_auth(patient["token"]),
    )
    assert booking.status_code == 409, booking.text

    # The rejected attempt must not have partially mutated the slot: it should
    # still be bookable once the doctor is available again.
    toggle_back = await client.patch(
        "/doctors/me", json={"is_available": True}, headers=doctor_headers
    )
    assert toggle_back.status_code == 200, toggle_back.text
    retry = await client.post(
        "/appointments",
        json={"availability_id": availability_id, "mode": "in_person"},
        headers=_auth(patient["token"]),
    )
    assert retry.status_code == 201, retry.text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd Backend-API && uv run python -m pytest tests/test_appointments_flow.py -k unavailable -v`
Expected: FAIL at `assert booking.status_code == 409` — the current code returns `201` because nothing checks the doctor's availability yet.

- [ ] **Step 3: Add the guard in `book_appointment`**

In `Backend-API/features/Appointments/logic.py`, `book_appointment` (lines 86-120) currently reads:

```python
async def book_appointment(
    db: AsyncSession, patient_id: int, data: AppointmentCreateRequest
) -> Appointment:
    """Marks the availability as booked and creates the appointment as pending."""
    # Lock the slot row so two patients can't book it concurrently (no-op on
    # SQLite, enforced on Postgres); re-check FREE after acquiring the lock.
    availability = (
        await db.scalars(
            select(Availability)
            .where(Availability.id == data.availability_id)
            .with_for_update()
        )
    ).first()
    if availability is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Availability not found")
    if availability.status != AvailabilityStatus.FREE:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This slot is no longer available"
        )
    if availability.date < date.today():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This slot is in the past")

    availability.status = AvailabilityStatus.BOOKED
    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=availability.doctor_id,
        availability_id=availability.id,
        mode=data.mode,
        status=AppointmentStatus.PENDING,
        reason=data.reason,
    )
    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)
    return appointment
```

Add a doctor-availability check alongside the existing post-lock validation (same place as the `FREE`/past-date checks — before anything is mutated or committed):

```python
async def book_appointment(
    db: AsyncSession, patient_id: int, data: AppointmentCreateRequest
) -> Appointment:
    """Marks the availability as booked and creates the appointment as pending."""
    # Lock the slot row so two patients can't book it concurrently (no-op on
    # SQLite, enforced on Postgres); re-check FREE after acquiring the lock.
    availability = (
        await db.scalars(
            select(Availability)
            .where(Availability.id == data.availability_id)
            .with_for_update()
        )
    ).first()
    if availability is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Availability not found")
    if availability.status != AvailabilityStatus.FREE:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This slot is no longer available"
        )
    if availability.date < date.today():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This slot is in the past")

    doctor = await db.get(Doctor, availability.doctor_id)
    if doctor is not None and not doctor.is_available:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This doctor is not accepting new appointments right now",
        )

    availability.status = AvailabilityStatus.BOOKED
    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=availability.doctor_id,
        availability_id=availability.id,
        mode=data.mode,
        status=AppointmentStatus.PENDING,
        reason=data.reason,
    )
    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)
    return appointment
```

`Doctor` is already imported at the top of this file (`from features.Auth.models import Doctor, Patient`), so no new import is needed.

Note: the error message is in English to match every other `HTTPException` string in this file (`"This slot is no longer available"`, `"This slot is in the past"`, `"Availability not found"`) — the project's backend error strings are English throughout (see e.g. `Prescriptions/logic.py`'s `"The consultation must be completed before prescribing"`); the frontend displays `err.message` (the raw `detail`) verbatim for this class of error today (see `consultations.html`'s existing `errorEl.textContent = err.message || '...'` pattern), so this is consistent with how every other booking conflict already reads to a French-speaking user — not a new problem introduced by this task.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd Backend-API && uv run python -m pytest tests/test_appointments_flow.py -k unavailable -v`
Expected: PASS.

- [ ] **Step 5: Run the full backend suite**

Run: `cd Backend-API && uv run python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add Backend-API/features/Appointments/logic.py Backend-API/tests/test_appointments_flow.py
git commit -m "feat: reject appointment booking when the doctor is unavailable"
```

---

### Task 4: Wire the doctor dashboard toggle to the API

**Files:**
- Modify: `frontend/app.js:99-112`
- Modify: `frontend/medecin/dashboard.html:95-102,275-298`

- [ ] **Step 1: Add an inline error slot next to the toggle**

In `frontend/medecin/dashboard.html`, the toggle markup (lines 95-102) currently reads:

```html
          <div class="row" style="gap:14px;">
            <div class="row" data-avail-toggle style="gap:9px;font-weight:700;font-size:14px;cursor:pointer;user-select:none;">
              <span class="avail-label">Disponible</span>
              <span class="avail-track" style="width:42px;height:24px;border-radius:20px;background:#10b981;position:relative;display:inline-block;transition:background .2s;">
                <span class="avail-knob" style="position:absolute;top:3px;left:21px;width:18px;height:18px;border-radius:50%;background:#fff;transition:left .2s;"></span>
              </span>
            </div>
          </div>
```

Replace with:

```html
          <div class="col" style="gap:4px;align-items:flex-end;">
            <div class="row" style="gap:14px;">
              <div class="row" data-avail-toggle style="gap:9px;font-weight:700;font-size:14px;cursor:pointer;user-select:none;">
                <span class="avail-label">Disponible</span>
                <span class="avail-track" style="width:42px;height:24px;border-radius:20px;background:#10b981;position:relative;display:inline-block;transition:background .2s;">
                  <span class="avail-knob" style="position:absolute;top:3px;left:21px;width:18px;height:18px;border-radius:50%;background:#fff;transition:left .2s;"></span>
                </span>
              </div>
            </div>
            <p class="form-error hidden" id="avail-toggle-error" style="margin:0;font-size:12px;"></p>
          </div>
```

- [ ] **Step 2: Make the `app.js` toggle handler call the API**

In `frontend/app.js`, the toggle block (lines 99-112) currently reads:

```javascript
// --- Interrupteur "Disponible / Indisponible" (dashboard médecin) ---
document.addEventListener('click', function (e) {
  var t = e.target.closest('[data-avail-toggle]');
  if (!t) return;
  var on = t.getAttribute('data-on') !== 'false'; // disponible par défaut
  on = !on;
  t.setAttribute('data-on', on ? 'true' : 'false');
  var label = t.querySelector('.avail-label');
  var track = t.querySelector('.avail-track');
  var knob = t.querySelector('.avail-knob');
  if (label) label.textContent = on ? 'Disponible' : 'Indisponible';
  if (track) track.style.background = on ? '#10b981' : '#cbd5e1';
  if (knob) knob.style.left = on ? '21px' : '3px';
});
```

Replace with:

```javascript
// --- Interrupteur "Disponible / Indisponible" (dashboard médecin) ---
function setAvailabilityToggleState(t, on) {
  t.setAttribute('data-on', on ? 'true' : 'false');
  var label = t.querySelector('.avail-label');
  var track = t.querySelector('.avail-track');
  var knob = t.querySelector('.avail-knob');
  if (label) label.textContent = on ? 'Disponible' : 'Indisponible';
  if (track) track.style.background = on ? '#10b981' : '#cbd5e1';
  if (knob) knob.style.left = on ? '21px' : '3px';
}

document.addEventListener('click', function (e) {
  var t = e.target.closest('[data-avail-toggle]');
  if (!t) return;
  var on = t.getAttribute('data-on') !== 'false'; // disponible par défaut
  on = !on;
  var errorEl = document.getElementById('avail-toggle-error');
  if (errorEl) errorEl.classList.add('hidden');
  apiRequest('PATCH', '/doctors/me', { json: { is_available: on } })
    .then(function () {
      setAvailabilityToggleState(t, on);
    })
    .catch(function (err) {
      if (errorEl) {
        errorEl.textContent = err.message || 'Impossible de mettre à jour votre disponibilité.';
        errorEl.classList.remove('hidden');
      }
    });
});
```

The toggle's visual state now only changes after the `PATCH` succeeds (no optimistic update) — this matches the project's existing convention of not showing a state change until the API confirms it (see e.g. `patient/consultations.html`'s booking confirm button, which stays disabled until the request resolves and only then swaps the modal).

- [ ] **Step 3: Load the real initial state on dashboard load**

In `frontend/medecin/dashboard.html`, the `loadStats` block (lines 285-298) currently reads:

```javascript
      async function loadStats() {
        try {
          var data = await apiGet('/doctors/me/dashboard');
          document.getElementById('stat-today').textContent = data.consultations_today;
          document.getElementById('stat-pending').textContent = data.pending_appointments;
          document.getElementById('stat-month').textContent = data.consultations_this_month;
          document.getElementById('stat-revenue').textContent = data.revenue_this_month + ' FCFA';
        } catch (err) {
          ['stat-today', 'stat-pending', 'stat-month', 'stat-revenue'].forEach(function (id) {
            document.getElementById(id).textContent = '—';
          });
        }
      }
      loadStats();
```

Add a new function right after it (still inside the same IIFE):

```javascript
      async function loadAvailabilityToggle() {
        try {
          var me = await apiGet('/doctors/me');
          var toggle = document.querySelector('[data-avail-toggle]');
          if (toggle) setAvailabilityToggleState(toggle, me.is_available);
        } catch (err) {
          // Leave the default "Disponible" markup as-is — non-blocking for the
          // rest of the dashboard.
        }
      }
      loadAvailabilityToggle();
```

- [ ] **Step 4: Manual verification**

Run: `cd Backend-API && uv run uvicorn app:app --port 8010 --reload`

In a browser: log in as a validated doctor (seed one via the normal registration + `scripts/seed_admin.py` + admin validation flow, or reuse an existing dev account), open `medecin/dashboard.html`, confirm:
- The toggle shows "Disponible" on load (or "Indisponible" if you'd previously set it false via the API).
- Clicking it flips to "Indisponible", and a page reload keeps it "Indisponible" (proves persistence).
- Temporarily stopping the backend and clicking the toggle shows the inline error message and leaves the toggle unchanged.

- [ ] **Step 5: Commit**

```bash
git add frontend/app.js frontend/medecin/dashboard.html
git commit -m "feat: persist the doctor availability toggle to the API"
```

---

### Task 5: Grey out booking on the patient search page

**Files:**
- Modify: `frontend/patient/consultations.html:113,117-147,175-239,263-321`

- [ ] **Step 1: Add an "unavailable" badge to doctor cards**

In `frontend/patient/consultations.html`, `renderDoctors` (lines 175-239) builds each card's `feeDiv` right after `headerRow`:

```javascript
          var feeDiv = document.createElement('div');
          feeDiv.style.cssText = 'font-weight:800;font-size:16px;margin-bottom:8px;';
          feeDiv.textContent = d.consultation_fee + ' FCFA';
          card.appendChild(feeDiv);
```

Insert a badge before that block, right after `card.appendChild(headerRow);`:

```javascript
          card.appendChild(headerRow);

          if (!d.is_available) {
            var unavailableBadge = document.createElement('span');
            unavailableBadge.className = 'chip';
            unavailableBadge.style.cssText = 'background:#fef3c7;color:#b45309;margin-bottom:8px;display:inline-block;';
            unavailableBadge.textContent = 'Indisponible';
            card.appendChild(unavailableBadge);
          }

          var feeDiv = document.createElement('div');
          feeDiv.style.cssText = 'font-weight:800;font-size:16px;margin-bottom:8px;';
          feeDiv.textContent = d.consultation_fee + ' FCFA';
          card.appendChild(feeDiv);
```

- [ ] **Step 2: Split the booking modal into a fields section and an unavailable message**

The `rdv-modal` markup (lines 117-147) currently reads:

```html
  <div class="modal__backdrop" id="rdv-modal" style="display:none;">
    <div class="modal">
      <div class="row" style="justify-content:space-between;margin-bottom:18px;">
        <div style="font-size:19px;font-weight:800;">Prendre rendez-vous</div>
        <button class="modal__close" data-close>✕</button>
      </div>
      <div class="row" id="rdv-doctor-summary" style="gap:14px;background:var(--green-soft);border-radius:14px;padding:15px;margin-bottom:18px;"></div>
      <label class="label" style="margin-bottom:8px;display:block;">CRÉNEAU</label>
      <select class="select" id="rdv-availability-select" style="margin-bottom:16px;"></select>
      <label class="label" style="margin-bottom:8px;display:block;">MODE</label>
      <div class="col" style="gap:10px;margin-bottom:16px;">
        <div class="mode-opt" data-modeopt data-c="#8b5cf6" data-mode="message">
          <div class="mode-dot" style="border-color:#8b5cf6;"></div>
          <div class="mode-tag" style="background:#8b5cf618;color:#8b5cf6;">M</div>
          <div style="font-weight:700;font-size:15px;">Message</div>
        </div>
        <div class="mode-opt" data-modeopt data-c="#0d9488" data-mode="presentiel">
          <div class="mode-dot"></div>
          <div class="mode-tag" style="background:#0d948818;color:#0d9488;">P</div>
          <div style="font-weight:700;font-size:15px;">Présentiel</div>
        </div>
      </div>
      <label class="label" style="margin-bottom:8px;display:block;">MOTIF (OPTIONNEL)</label>
      <input class="input" id="rdv-reason" style="margin-bottom:16px;" placeholder="Ex. Douleurs thoraciques">
      <p class="form-error hidden" id="rdv-error"></p>
      <button class="btn btn--primary btn--block" data-rdvconfirm>Confirmer le rendez-vous <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
      </button>
    </div>
  </div>
```

Replace with (wraps everything from CRÉNEAU to the confirm button in `#rdv-booking-fields`, and adds a sibling `#rdv-unavailable-msg`):

```html
  <div class="modal__backdrop" id="rdv-modal" style="display:none;">
    <div class="modal">
      <div class="row" style="justify-content:space-between;margin-bottom:18px;">
        <div style="font-size:19px;font-weight:800;">Prendre rendez-vous</div>
        <button class="modal__close" data-close>✕</button>
      </div>
      <div class="row" id="rdv-doctor-summary" style="gap:14px;background:var(--green-soft);border-radius:14px;padding:15px;margin-bottom:18px;"></div>
      <div class="hidden" id="rdv-unavailable-msg" style="color:var(--muted);font-size:14px;line-height:1.5;padding:4px 0 8px;">Ce médecin n'accepte pas de nouveaux rendez-vous pour le moment.</div>
      <div id="rdv-booking-fields">
        <label class="label" style="margin-bottom:8px;display:block;">CRÉNEAU</label>
        <select class="select" id="rdv-availability-select" style="margin-bottom:16px;"></select>
        <label class="label" style="margin-bottom:8px;display:block;">MODE</label>
        <div class="col" style="gap:10px;margin-bottom:16px;">
          <div class="mode-opt" data-modeopt data-c="#8b5cf6" data-mode="message">
            <div class="mode-dot" style="border-color:#8b5cf6;"></div>
            <div class="mode-tag" style="background:#8b5cf618;color:#8b5cf6;">M</div>
            <div style="font-weight:700;font-size:15px;">Message</div>
          </div>
          <div class="mode-opt" data-modeopt data-c="#0d9488" data-mode="presentiel">
            <div class="mode-dot"></div>
            <div class="mode-tag" style="background:#0d948818;color:#0d9488;">P</div>
            <div style="font-weight:700;font-size:15px;">Présentiel</div>
          </div>
        </div>
        <label class="label" style="margin-bottom:8px;display:block;">MOTIF (OPTIONNEL)</label>
        <input class="input" id="rdv-reason" style="margin-bottom:16px;" placeholder="Ex. Douleurs thoraciques">
        <p class="form-error hidden" id="rdv-error"></p>
        <button class="btn btn--primary btn--block" data-rdvconfirm>Confirmer le rendez-vous <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>
      </div>
    </div>
  </div>
```

- [ ] **Step 3: Branch on availability when the modal opens**

In the same file, the `[data-book]` click handler (lines 263-321) currently ends its summary-building block with:

```javascript
        summary.appendChild(summaryAvatar);
        summary.appendChild(summaryInfo);
        renderAvatar(summaryAvatar, selectedDoctor.photo_url);

        document.getElementById('rdv-reason').value = '';
        var select = document.getElementById('rdv-availability-select');
        select.innerHTML = '<option>Chargement…</option>';
        var today = new Date().toISOString().slice(0, 10);
        try {
          var slots = await apiGet('/appointments/doctors/' + doctorId + '/availabilities?from_date=' + today);
          select.innerHTML = '';
          if (slots.length === 0) {
            var noneOpt = document.createElement('option');
            noneOpt.value = '';
            noneOpt.textContent = 'Aucun créneau disponible';
            select.appendChild(noneOpt);
          } else {
            slots.forEach(function (s) {
              var opt = document.createElement('option');
              opt.value = s.id;
              opt.textContent = s.date + ' · ' + s.start_time.slice(0, 5) + '-' + s.end_time.slice(0, 5);
              select.appendChild(opt);
            });
          }
        } catch (err) {
          select.innerHTML = '';
          var errOpt = document.createElement('option');
          errOpt.value = '';
          errOpt.textContent = 'Erreur de chargement des créneaux';
          select.appendChild(errOpt);
        }
      });
```

Replace with (adds the branch right after the summary is built, before touching the availability select):

```javascript
        summary.appendChild(summaryAvatar);
        summary.appendChild(summaryInfo);
        renderAvatar(summaryAvatar, selectedDoctor.photo_url);

        var bookingFields = document.getElementById('rdv-booking-fields');
        var unavailableMsg = document.getElementById('rdv-unavailable-msg');
        if (!selectedDoctor.is_available) {
          bookingFields.classList.add('hidden');
          unavailableMsg.classList.remove('hidden');
          return;
        }
        bookingFields.classList.remove('hidden');
        unavailableMsg.classList.add('hidden');

        document.getElementById('rdv-reason').value = '';
        var select = document.getElementById('rdv-availability-select');
        select.innerHTML = '<option>Chargement…</option>';
        var today = new Date().toISOString().slice(0, 10);
        try {
          var slots = await apiGet('/appointments/doctors/' + doctorId + '/availabilities?from_date=' + today);
          select.innerHTML = '';
          if (slots.length === 0) {
            var noneOpt = document.createElement('option');
            noneOpt.value = '';
            noneOpt.textContent = 'Aucun créneau disponible';
            select.appendChild(noneOpt);
          } else {
            slots.forEach(function (s) {
              var opt = document.createElement('option');
              opt.value = s.id;
              opt.textContent = s.date + ' · ' + s.start_time.slice(0, 5) + '-' + s.end_time.slice(0, 5);
              select.appendChild(opt);
            });
          }
        } catch (err) {
          select.innerHTML = '';
          var errOpt = document.createElement('option');
          errOpt.value = '';
          errOpt.textContent = 'Erreur de chargement des créneaux';
          select.appendChild(errOpt);
        }
      });
```

- [ ] **Step 4: Manual verification**

With the backend running (`uv run uvicorn app:app --port 8010 --reload`):
- Use `PATCH /doctors/me` (e.g. via `/docs` Swagger UI, authenticated as a doctor) to set `is_available: false`.
- Open `patient/consultations.html`, confirm the doctor's card shows the "Indisponible" badge.
- Click "Prendre RDV" on that card, confirm the modal shows the summary + the unavailable message, with no créneau selector, mode buttons, or confirm button.
- Click "Prendre RDV" on a different, available doctor's card, confirm the normal booking flow still works end-to-end (book a slot successfully).

- [ ] **Step 5: Commit**

```bash
git add frontend/patient/consultations.html
git commit -m "feat: grey out booking for unavailable doctors on the search page"
```

---

### Task 6: Disable "Prendre RDV" on the doctor detail page

**Files:**
- Modify: `frontend/patient/medecin-detail.html:109-112,144-160`

- [ ] **Step 1: Add a disabled state + message next to the button**

In `frontend/patient/medecin-detail.html`, lines 109-112 currently read:

```html
          <div class="row" style="gap:10px;">
            <a class="btn btn--primary" href="consultations.html">Prendre RDV</a>
            <button class="btn btn--ghost" id="report-btn" type="button">Signaler ce médecin</button>
          </div>
```

Replace with:

```html
          <div class="col" style="gap:10px;">
            <div class="row" style="gap:10px;">
              <a class="btn btn--primary" href="consultations.html" id="detail-book-link">Prendre RDV</a>
              <button class="btn btn--ghost" id="report-btn" type="button">Signaler ce médecin</button>
            </div>
            <p class="hidden" id="detail-book-unavailable" style="margin:0;color:var(--muted);font-size:13.5px;">Ce médecin n'accepte pas de nouveaux rendez-vous pour le moment.</p>
          </div>
```

- [ ] **Step 2: Disable the link when the doctor is unavailable**

Lines 144-160 currently read:

```javascript
        apiGet('/doctors/' + doctorId)
          .then(function (d) {
            document.getElementById('detail-name').textContent = 'Dr. ' + d.first_name + ' ' + d.last_name;
            document.getElementById('detail-specialty').textContent = d.specialty;
            document.getElementById('detail-practice').textContent = d.practice_name;
            document.getElementById('detail-city').textContent = d.city;
            document.getElementById('detail-fee').textContent = d.consultation_fee + ' FCFA';
            var avatar = document.getElementById('detail-avatar');
            avatar.textContent = (d.first_name.charAt(0) + d.last_name.charAt(0)).toUpperCase();
            renderAvatar(avatar, d.photo_url);
            document.getElementById('detail-content').classList.remove('hidden');
          })
          .catch(function () {
            document.getElementById('detail-error').textContent = 'Impossible de charger ce médecin.';
            document.getElementById('detail-error').classList.remove('hidden');
          });
```

Replace with:

```javascript
        apiGet('/doctors/' + doctorId)
          .then(function (d) {
            document.getElementById('detail-name').textContent = 'Dr. ' + d.first_name + ' ' + d.last_name;
            document.getElementById('detail-specialty').textContent = d.specialty;
            document.getElementById('detail-practice').textContent = d.practice_name;
            document.getElementById('detail-city').textContent = d.city;
            document.getElementById('detail-fee').textContent = d.consultation_fee + ' FCFA';
            var avatar = document.getElementById('detail-avatar');
            avatar.textContent = (d.first_name.charAt(0) + d.last_name.charAt(0)).toUpperCase();
            renderAvatar(avatar, d.photo_url);
            if (!d.is_available) {
              var bookLink = document.getElementById('detail-book-link');
              bookLink.removeAttribute('href');
              bookLink.setAttribute('aria-disabled', 'true');
              bookLink.style.cssText = 'opacity:.5;pointer-events:none;cursor:not-allowed;';
              document.getElementById('detail-book-unavailable').classList.remove('hidden');
            }
            document.getElementById('detail-content').classList.remove('hidden');
          })
          .catch(function () {
            document.getElementById('detail-error').textContent = 'Impossible de charger ce médecin.';
            document.getElementById('detail-error').classList.remove('hidden');
          });
```

- [ ] **Step 3: Manual verification**

With a doctor set to `is_available: false` (as in Task 5's verification), open `patient/medecin-detail.html?doctor_id=<id>` for that doctor, confirm the "Prendre RDV" button is visibly disabled (greyed, no click) and the message shows underneath. Open the page for an available doctor, confirm the button still links to `consultations.html` normally.

- [ ] **Step 4: Commit**

```bash
git add frontend/patient/medecin-detail.html
git commit -m "feat: disable Prendre RDV on the doctor detail page when unavailable"
```

---

### Task 7: Final full-suite check

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `cd Backend-API && uv run python -m pytest -q`
Expected: all tests pass, including the 3 new ones added in Tasks 2 and 3.

- [ ] **Step 2: Run lint**

Run: `cd Backend-API && uv run ruff check .`
Expected: no errors (or only pre-existing ones unrelated to the files touched by this plan).

- [ ] **Step 3: Confirm migration applies cleanly**

If a local Postgres is available (`docker compose up -d` from `Backend-API/`):

Run: `cd Backend-API && uv run alembic upgrade head`
Expected: applies `bd13bdd8f230` on top of the existing head with no errors.

Run: `cd Backend-API && uv run alembic downgrade -1 && uv run alembic upgrade head`
Expected: round-trips cleanly (proves the `downgrade()` in Task 1 is correct).

If no local Postgres is running, skip this step and note it as unverified — do not claim it was tested.
