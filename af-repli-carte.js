/* Replier une carte de match : la page ne « saute » plus.
   Quand on replie une carte (classe ax-replie ajoutée sur .ax-carte) dont le haut est sorti de l'écran (on était en bas d'une carte dépliée),
   on remet le haut de cette carte juste sous la barre fixe : la carte suivante apparaît tout de suite dessous, sans défiler.
   Si le haut de la carte est déjà visible, rien ne bouge. Fichier commun à tous les moteurs ; aucune donnée touchée. Sert aussi à centrer l'onglet courant de la barre. */
(function () {
  "use strict";
  if (!window.MutationObserver) return;
  var MARGE = 8;

  function hauteurBarre() {
    var b = document.querySelector(".af-barre");
    if (!b) return 0;
    var pos = window.getComputedStyle(b).position;
    return pos === "sticky" || pos === "fixed" ? b.getBoundingClientRect().bottom : 0;
  }

  function recaler(carte) {
    var haut = hauteurBarre() + MARGE;
    var top = carte.getBoundingClientRect().top;
    if (top >= haut) return;                                   // haut de carte déjà visible : on ne touche à rien
    window.scrollTo(0, Math.max(0, window.pageYOffset + top - haut));
  }

  new MutationObserver(function (liste) {
    liste.forEach(function (m) {
      var el = m.target;
      if (!(el instanceof Element) || !el.classList.contains("ax-carte") || !el.classList.contains("ax-replie")) return;
      if ((m.oldValue || "").split(/\s+/).indexOf("ax-replie") !== -1) return;   // elle était déjà repliée
      window.requestAnimationFrame(function () { recaler(el); });
    });
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["class"], attributeOldValue: true, subtree: true });

  // Barre d'onglets : l'onglet de la page courante est ramené dans la zone visible (la liste défile à l'horizontale).
  function centrerOnglet() {
    var nav = document.querySelector(".af-nav"), cur = nav && nav.querySelector('[aria-current="page"]');
    if (!cur) return;
    nav.scrollLeft = Math.max(0, cur.offsetLeft - (nav.clientWidth - cur.offsetWidth) / 2);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", centrerOnglet); else centrerOnglet();
})();
