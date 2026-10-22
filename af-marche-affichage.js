// af-marche-affichage.js — présentation commune d'un pronostic (22/10/2026, demande de Patrick) :
// le nom du marché en gras, puis dessous une phrase simple qui dit ce qu'il faut pour que le pari passe
// (ex. « Plus de 2,5 buts » / « Au moins 3 buts dans le match »), comme sur le moteur V2R.
// Présentation uniquement : aucun calcul, aucune décision. Le texte d'origine n'est jamais modifié ni masqué.
(function () {
  "use strict";
  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
  }
  function norme(t) { return String(t == null ? "" : t).replace(/\s+/g, " ").replace(/\./g, ",").trim().toLowerCase(); }
  // HTML sûr : nom en gras + explication dessous. Sans explication (ou identique au nom) : le nom seul.
  window.afMarcheHtml = function (titre, explication) {
    var nom = String(titre == null ? "" : titre).trim();
    var expl = String(explication == null ? "" : explication).trim();
    if (!nom) nom = expl, expl = "";
    var html = '<span class="mk-nom">' + esc(nom) + "</span>";
    if (expl && norme(expl) !== norme(nom)) html += '<small class="mk-expl">' + esc(expl) + "</small>";
    return html;
  };
  try {
    if (!document.getElementById("af-marche-affichage-css")) {
      var st = document.createElement("style");
      st.id = "af-marche-affichage-css";
      st.textContent = ".mk-nom{display:block;min-width:0;overflow-wrap:anywhere}" +
        ".mk-expl{display:block;white-space:normal;font-size:.78em;font-weight:400;line-height:1.35;opacity:.78;margin-top:2px;overflow-wrap:anywhere}";
      document.head.appendChild(st);
    }
  } catch (e) { /* présentation seulement */ }
})();
