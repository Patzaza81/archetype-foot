// af-alpha-selection.js — règle définitive d'affichage du moteur alpha (24/10/2026, décision de Patrick).
// Présentation seulement : aucun calcul de moteur, les marchés viennent tels quels de data/alpha_serie/pronostics.json.
// 1. Cinq catégories indépendantes : Buts, Multigoals, Équipes, Multiscores, Calibrés. Aucun classement entre catégories.
// 2. Meilleur marché d'une catégorie = le premier selon le classement propre à la catégorie (valeur décroissante, ordre du fichier à égalité).
// 3. Buts, Équipes, Calibrés : un pronostic n'apparaît JAMAIS sans sa cote BetPawa, nulle part sur la page (onglets dépliés compris).
// 4. Multigoals et Multiscores : affichés même sans cote (cote facultative).
// 5. (24/10/2026, Patrick) Si le marché principal d'une catégorie n'a pas de cote, le meilleur marché INFÉRIEUR de la même catégorie qui a une
//    cote est retenu à sa place. « Pourcentage acceptable » = marché retenu par le moteur lui-même dans cette catégorie (normes de l'alpha :
//    deux branches et marge de niveau ; Calibrés : règle exploitable validée) : aucun seuil ajouté ici. Le remplacement est signalé à l'écran.
// 6. Doublons retirés à l'intérieur de chaque catégorie seulement ; aucun classement entre catégories.
(function (racine) {
  const CATEGORIES_ALPHA = [
    { cle: "buts", nom: "Buts", source: "buts", garde: (s) => !estMultigoal(s), coteObligatoire: true },
    { cle: "multigoals", nom: "Multigoals", source: "buts", garde: (s) => estMultigoal(s), coteObligatoire: false },
    { cle: "equipes", nom: "Équipes", source: "equipes", garde: () => true, coteObligatoire: true },
    { cle: "multiscores", nom: "Multiscores", source: "multiscores", garde: () => true, coteObligatoire: false },
    { cle: "calibrees", nom: "Calibrés", source: "calibrees", garde: () => true, coteObligatoire: true },
  ];
  function estMultigoal(s) {
    return Array.isArray(s.cle) ? s.cle[0] === "multigoals" : /^Multigoals /.test(String(s.marche || ""));
  }
  function aUneCoteAlpha(x) { return x !== null && x !== undefined && x !== "" && Number.isFinite(Number(x)) && Number(x) > 1; }
  function signature(s) { return Array.isArray(s.cle) ? s.cle.join("|") : String(s.marche || ""); }
  // Marchés d'une catégorie, classés par la catégorie elle-même, sans doublon à l'intérieur de la catégorie.
  function lignesCategorie(m, cat) {
    const brutes = ((m && m.onglets && m.onglets[cat.source]) || []).filter(cat.garde);
    const vus = new Set();
    const uniques = brutes.filter((s) => { const k = signature(s); if (vus.has(k)) return false; vus.add(k); return true; });
    return uniques.map((s, i) => [s, i]).sort((a, b) => ((Number(b[0].valeur) || 0) - (Number(a[0].valeur) || 0)) || (a[1] - b[1])).map((x) => x[0]);
  }
  // Marché affiché en tête de la catégorie : le premier de la catégorie qui remplit la condition de cote.
  // Si le marché principal n'a pas de cote, c'est le meilleur marché inférieur coté de la même catégorie (tous sont déjà retenus par le moteur).
  function meilleurAffichable(m, cat) {
    const l = marchesAffiches(m, cat);
    return l.length ? l[0] : null;
  }
  // Vrai quand le marché affiché remplace le marché principal de la catégorie (resté sans cote).
  function estRemplacant(m, cat) {
    const l = lignesCategorie(m, cat), a = meilleurAffichable(m, cat);
    return Boolean(a && l.length && l[0] !== a);
  }
  function carteAffichable(m) { return CATEGORIES_ALPHA.some((c) => meilleurAffichable(m, c)); }
  // Marchés montrés dans l'onglet déplié : seulement ceux qui ont une cote (sauf Multigoals / Multiscores), dans l'ordre de la catégorie.
  function marchesAffiches(m, cat) {
    const l = lignesCategorie(m, cat);
    return cat.coteObligatoire ? l.filter((s) => aUneCoteAlpha(s.cote)) : l;
  }
  const api = { CATEGORIES_ALPHA, lignesCategorie, meilleurAffichable, estRemplacant, carteAffichable, marchesAffiches, aUneCoteAlpha };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else Object.assign(racine, api);
})(typeof window !== "undefined" ? window : globalThis);
