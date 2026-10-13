// af-drapeaux-cartes.js — présentation seule (branche accueil-prototype).
// Ajoute devant chaque libellé de compétition (.ax-competition) le drapeau du PAYS DU CHAMPIONNAT,
// calculé par drapeaux.js à partir du libellé « Pays : Nom ». Jamais le pays d'une équipe.
// Pays non reconnu ou sans drapeau officiel : rien n'est ajouté, le texte reste seul.
// Ne lit ni ne modifie aucune donnée, cote, probabilité ou sélection ; ne touche pas aux scripts métier.
// Le span ajouté est aria-hidden (le pays est déjà écrit en clair) et marqué .af-drapeau (retrait trivial).
(function () {
  "use strict";
  if (typeof window.drapeauCompetition !== "function") return;
  function decore(racine) {
    racine.querySelectorAll(".ax-competition").forEach(function (el) {
      if (el.querySelector(".af-drapeau")) return;
      var d = window.drapeauCompetition(el.textContent);
      if (!d.symbole) return;
      var s = document.createElement("span");
      s.className = "af-drapeau"; s.setAttribute("aria-hidden", "true");
      s.title = d.pays; s.textContent = d.symbole;
      el.insertBefore(s, el.firstChild);
    });
  }
  function demarre() {
    // Liste des cartes : #matches (V2, V3), #panier-cartes (panier), main du Journal — toutes en main.ax-liste-matchs.
    var liste = document.querySelector("main.ax-liste-matchs");
    if (!liste) return;
    decore(liste);
    // Les cartes sont construites après le chargement des données : on décore au fil des ajouts.
    new MutationObserver(function () { decore(liste); }).observe(liste, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", demarre);
  else demarre();
})();
