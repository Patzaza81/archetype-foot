// af-alpha-selection.js — règle définitive d'affichage du moteur alpha (24/10/2026, décision de Patrick).
// Présentation seulement : aucun calcul de moteur, les marchés viennent tels quels de data/alpha_serie/pronostics.json.
// 1. Cinq catégories indépendantes : Buts, Multigoals, Équipes, Multiscores, Calibrés. Aucun classement entre catégories.
// 2. Meilleur marché d'une catégorie = le premier selon le classement propre à la catégorie (valeur décroissante, ordre du fichier à égalité).
// 3. Buts, Équipes, Calibrés : ce meilleur marché n'est affiché que si sa cote BetPawa est connue ; sinon la catégorie est masquée.
// 4. Multigoals et Multiscores : affichés même sans cote (cote facultative).
// 5. Jamais de marché inférieur en remplacement ; doublons retirés à l'intérieur de chaque catégorie seulement.
// 6. (24/10/2026) Partout sur la page, y compris dans les onglets dépliés : un pronostic de Buts, Équipes ou Calibrés n'apparaît JAMAIS sans
//    sa cote BetPawa. Une catégorie dont le meilleur marché n'a pas de cote est entièrement masquée (onglet vide). Multigoals et Multiscores : cote facultative.
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
  // Meilleur marché affichable : le PREMIER de la catégorie ; s'il ne remplit pas la condition de cote, rien (aucun remplaçant).
  function meilleurAffichable(m, cat) {
    const l = lignesCategorie(m, cat);
    if (!l.length) return null;
    const meilleur = l[0];
    if (cat.coteObligatoire && !aUneCoteAlpha(meilleur.cote)) return null;
    return meilleur;
  }
  function carteAffichable(m) { return CATEGORIES_ALPHA.some((c) => meilleurAffichable(m, c)); }
  // Marchés montrés dans l'onglet déplié d'une catégorie : uniquement ceux qui ont une cote (sauf Multigoals / Multiscores),
  // et rien du tout si le meilleur marché de la catégorie n'est pas affichable (aucun remplaçant).
  function marchesAffiches(m, cat) {
    if (!meilleurAffichable(m, cat)) return [];
    const l = lignesCategorie(m, cat);
    return cat.coteObligatoire ? l.filter((s) => aUneCoteAlpha(s.cote)) : l;
  }
  const api = { CATEGORIES_ALPHA, lignesCategorie, meilleurAffichable, carteAffichable, marchesAffiches, aUneCoteAlpha };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else Object.assign(racine, api);
})(typeof window !== "undefined" ? window : globalThis);
