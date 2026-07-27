/* ============================================================
   Carnet+ — Interactions front (version pages HTML séparées)
   Version allégée. La navigation entre pages se fait par de
   vrais liens <a href>. Ce fichier ne gère que quelques
   interactions : menu latéral et pop-up "Bientôt disponible".
   ============================================================ */

// --- Ouvrir / réduire le menu latéral ---
document.addEventListener('click', function (e) {
  var btn = e.target.closest('[data-action="toggle-sidebar"]');
  if (!btn) return;
  var app = document.querySelector('.app');
  if (app) app.classList.toggle('sidebar-closed');
});

// --- Pop-up "Bientôt disponible" (cartes Pharmacie / Laboratoire) ---
document.addEventListener('click', function (e) {
  // Ouverture : clic sur une carte marquée data-soon="Pharmacie" (ou Laboratoire)
  var card = e.target.closest('[data-soon]');
  if (card) {
    var espace = card.getAttribute('data-soon');
    var modal = document.getElementById('soon-modal');
    var msg = document.getElementById('soon-msg');
    if (msg) msg.textContent = "La création d'un espace " + espace +
      " arrive très prochainement sur Carnet+. Cet espace n'est pas encore ouvert à l'inscription.";
    if (modal) modal.style.display = 'flex';
    return;
  }
  // Fermeture : clic sur le bouton ✕, sur "J'ai compris", ou en dehors de la fenêtre
  var closeBtn = e.target.closest('[data-soon-close]');
  var backdrop = e.target.id === 'soon-modal';
  if (closeBtn || backdrop) {
    var m = document.getElementById('soon-modal');
    if (m) m.style.display = 'none';
  }
});

// --- Pop-ups génériques (Prendre RDV, Prochaines consultations…) ---
document.addEventListener('click', function (e) {
  // Ouverture : élément avec data-open="id-de-la-modale"
  var opener = e.target.closest('[data-open]');
  if (opener) {
    e.preventDefault();
    var m = document.getElementById(opener.getAttribute('data-open'));
    if (m) m.style.display = 'flex';
    return;
  }
  // Choix du mode de consultation (Message / Présentiel) — déplace aussi la coche
  var opt = e.target.closest('[data-modeopt]');
  if (opt) {
    var box = opt.closest('.modal__backdrop');
    var check = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
    if (box) box.querySelectorAll('[data-modeopt]').forEach(function (o) {
      o.style.borderColor = ''; o.style.background = '';
      var d = o.querySelector('.mode-dot');
      if (d) { d.style.borderColor = ''; d.style.background = ''; d.innerHTML = ''; }
    });
    var c = opt.getAttribute('data-c') || '#0d9488';
    opt.style.borderColor = c; opt.style.background = c + '12';
    var dot = opt.querySelector('.mode-dot');
    if (dot) { dot.style.borderColor = c; dot.style.background = c; dot.innerHTML = check; }
    return;
  }
  // Confirmer le rendez-vous -> ferme le choix du mode et affiche "Demande envoyée"
  var confirm = e.target.closest('[data-rdvconfirm]');
  if (confirm) {
    var rdv = document.getElementById('rdv-modal');
    if (rdv) rdv.style.display = 'none';
    var sent = document.getElementById('rdv-sent-modal');
    if (sent) sent.style.display = 'flex';
    return;
  }
  // Fermeture : bouton ✕ / Confirmer (data-close) ou clic sur le fond
  var closer = e.target.closest('[data-close]');
  if (closer) {
    var c = closer.closest('.modal__backdrop');
    if (c) c.style.display = 'none';
    return;
  }
  if (e.target.classList && e.target.classList.contains('modal__backdrop') && e.target.id !== 'soon-modal') {
    e.target.style.display = 'none';
  }
});

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

// --- Pop-up de confirmation "Accepter" (demandes en attente) ---
document.addEventListener('click', function (e) {
  var b = e.target.closest('[data-accept]');
  if (!b) return;
  var m = document.getElementById('accept-modal');
  if (m) m.style.display = 'flex';
});

// --- Page "Créer une ordonnance" ---
document.addEventListener('click', function (e) {
  // 1) Choisir un patient -> affiche la partie 2 et surligne la ligne
  var row = e.target.closest('[data-selectord]');
  if (row) {
    document.querySelectorAll('[data-selectord]').forEach(function (r) { r.classList.remove('sel'); });
    row.classList.add('sel');
    var step2 = document.getElementById('ordonnance-step2');
    if (step2) step2.style.display = '';
    return;
  }
  // 2) Ajouter un médicament -> nouvelle ligne
  var add = e.target.closest('[data-addmed]');
  if (add) {
    var list = document.getElementById('med-list');
    if (list) {
      var rows = list.querySelectorAll('.med-row');
      var clone = rows[rows.length - 1].cloneNode(true);
      clone.querySelectorAll('input').forEach(function (i) { i.value = ''; });
      list.appendChild(clone);
      renumberMeds();
    }
    return;
  }
  // 3) Supprimer un médicament
  var del = e.target.closest('[data-removemed]');
  if (del) {
    var r = del.closest('.med-row');
    var l = document.getElementById('med-list');
    if (r && l && l.querySelectorAll('.med-row').length > 1) { r.remove(); renumberMeds(); }
    return;
  }
});
function renumberMeds() {
  var list = document.getElementById('med-list');
  if (!list) return;
  list.querySelectorAll('.med-row').forEach(function (r, i) {
    var n = r.querySelector('.num');
    if (n) n.textContent = i + 1;
  });
}
