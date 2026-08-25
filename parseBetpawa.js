// parseBetpawa.js -- portage JS de parse_betpawa.py, comportement identique
// (même découpage en lignes, mêmes regex, mêmes règles de rupture).

function lignesNonVides(texte) {
  return texte.split("\n").map((l) => l.trim()).filter((l) => l.length > 0);
}

function versNombre(s) {
  const n = parseFloat(s.replace(",", "."));
  return Number.isNaN(n) ? null : n;
}

function lirePaires(lignes, i, n) {
  const resultat = {};
  let idx = i;
  for (let k = 0; k < n; k++) {
    if (idx + 1 >= lignes.length) break;
    const label = lignes[idx];
    const valeur = versNombre(lignes[idx + 1]);
    if (valeur === null) break;
    resultat[label] = valeur;
    idx += 2;
  }
  return { paires: resultat, index: idx };
}

function lirePairesJusquaRupture(lignes, i, motifLabel) {
  const resultat = {};
  let idx = i;
  while (idx + 1 < lignes.length && motifLabel.test(lignes[idx])) {
    const label = lignes[idx];
    const valeur = versNombre(lignes[idx + 1]);
    if (valeur === null) break;
    resultat[label] = valeur;
    idx += 2;
  }
  return { paires: resultat, index: idx };
}

function parseBetpawa(texte, nomDomicile, nomExterieur) {
  const lignes = lignesNonVides(texte);
  const cotes = {};
  let i = 0;

  const REGEX_OU = /^(Plus|Moins) de (\d+\.5)$/;
  const REGEX_OU_RUPTURE = /^(Plus|Moins) de \d+\.5$/;
  const REGEX_HANDICAP_LIGNE = /^[+-]\d+\.5$/;
  const REGEX_SCORE_RUPTURE = /^(\d+-\d+|Other|Autre)$/;
  const REGEX_SCORE = /^\d+-\d+$/;
  const REGEX_NB_BUTS_RUPTURE = /^(\d+|\d+\+)$/;

  while (i < lignes.length) {
    const titre = lignes[i];

    if (titre === "1X2 | Fin de Match") {
      const { paires, index } = lirePaires(lignes, i + 1, 3);
      i = index;
      if (Object.keys(paires).length === 3) {
        cotes["1x2"] = { "1": paires["1"], "N": paires["X"], "2": paires["2"] };
      }
      continue;
    }

    if (titre === "Double Chance | Fin de Match") {
      const { paires, index } = lirePaires(lignes, i + 1, 3);
      i = index;
      if (Object.keys(paires).length === 3) {
        cotes["double_chance"] = { "1N": paires["1X"], "N2": paires["X2"], "12": paires["12"] };
      }
      continue;
    }

    if (titre === "Les Deux Équipes Marquent | Fin de Match") {
      const { paires, index } = lirePaires(lignes, i + 1, 2);
      i = index;
      if (Object.keys(paires).length === 2) {
        cotes["btts"] = { "Oui": paires["Oui"], "Non": paires["Non"] };
      }
      continue;
    }

    if (titre === "Plus de/Moins de | Fin de Match") {
      const { paires, index } = lirePairesJusquaRupture(lignes, i + 1, REGEX_OU_RUPTURE);
      i = index;
      for (const [label, valeur] of Object.entries(paires)) {
        const m = label.match(REGEX_OU);
        const cleSel = m[1] === "Plus" ? "plus" : "moins";
        const cleMarche = `over_under_${m[2]}`;
        cotes[cleMarche] = cotes[cleMarche] || {};
        cotes[cleMarche][cleSel] = valeur;
      }
      continue;
    }

    const mEquipe = titre.match(/^Plus de\/Moins de \| (.+) \| Fin de [Mm]atch$/);
    if (mEquipe) {
      const nom = mEquipe[1];
      let prefixe = null;
      if (nom === nomDomicile) prefixe = "over_under_domicile";
      else if (nom === nomExterieur) prefixe = "over_under_exterieur";
      const { paires, index } = lirePairesJusquaRupture(lignes, i + 1, REGEX_OU_RUPTURE);
      i = index;
      if (prefixe) {
        for (const [label, valeur] of Object.entries(paires)) {
          const m = label.match(REGEX_OU);
          const cleSel = m[1] === "Plus" ? "plus" : "moins";
          const cleMarche = `${prefixe}_${m[2]}`;
          cotes[cleMarche] = cotes[cleMarche] || {};
          cotes[cleMarche][cleSel] = valeur;
        }
      }
      continue;
    }

    if (titre === "Handicap À 2 Choix | Fin de Match") {
      i += 1;
      if (i < lignes.length && lignes[i] === "1") i += 1;
      if (i < lignes.length && lignes[i] === "2") i += 1;
      while (i + 3 < lignes.length && REGEX_HANDICAP_LIGNE.test(lignes[i])) {
        const labelDom = lignes[i], valDom = lignes[i + 1], labelExt = lignes[i + 2], valExt = lignes[i + 3];
        if (REGEX_HANDICAP_LIGNE.test(labelExt)) {
          const cleLigne = labelDom.startsWith("+") ? labelDom.slice(1) : labelDom;
          const vd = versNombre(valDom), ve = versNombre(valExt);
          if (vd !== null && ve !== null) {
            cotes[`handicap_${cleLigne}`] = { domicile: vd, exterieur: ve };
          }
          i += 4;
        } else break;
      }
      continue;
    }

    if (titre === "Impair/Pair | Fin de Match") {
      const { paires, index } = lirePaires(lignes, i + 1, 2);
      i = index;
      if (Object.keys(paires).length === 2) {
        cotes["pair_impair"] = { pair: paires["Pair"], impair: paires["Impair"] };
      }
      continue;
    }

    const mCages = titre.match(/^Cages Inviolées \| (.+) \| Fin de Match$/);
    if (mCages) {
      const nom = mCages[1];
      const { paires, index } = lirePaires(lignes, i + 1, 2);
      i = index;
      if (Object.keys(paires).length === 2) {
        if (nom === nomDomicile) cotes["cages_inviolees_domicile"] = { oui: paires["Oui"], non: paires["Non"] };
        else if (nom === nomExterieur) cotes["cages_inviolees_exterieur"] = { oui: paires["Oui"], non: paires["Non"] };
      }
      continue;
    }

    if (titre === "Score Exact | Fin de Match") {
      const { paires, index } = lirePairesJusquaRupture(lignes, i + 1, REGEX_SCORE_RUPTURE);
      i = index;
      const scores = {};
      for (const [k, v] of Object.entries(paires)) if (REGEX_SCORE.test(k)) scores[k] = v;
      if (Object.keys(scores).length > 0) cotes["score_exact"] = scores;
      continue;
    }

    if (titre === "Nombre Exact de Buts | Fin de Match") {
      const { paires, index } = lirePairesJusquaRupture(lignes, i + 1, REGEX_NB_BUTS_RUPTURE);
      i = index;
      if (Object.keys(paires).length > 0) cotes["nombre_exact_buts"] = paires;
      continue;
    }

    i += 1; // section non reconnue -- ignorée sans message, c'est voulu
  }

  return cotes;
}

if (typeof module !== "undefined") module.exports = { parseBetpawa };
