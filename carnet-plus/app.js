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
