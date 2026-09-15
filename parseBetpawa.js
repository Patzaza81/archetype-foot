// parseBetpawa.js -- portage JS de parse_betpawa.py

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
    const valeur = versNombre(lignes[idx + 1]);
    if (valeur === null) break;
    resultat[lignes[idx]] = valeur;
    idx += 2;
  }
  return { paires: resultat, index: idx };
}

function lirePairesJusquaRupture(lignes, i, motifLabel) {
  const resultat = {};
  let idx = i;
  while (idx + 1 < lignes.length && motifLabel.test(lignes[idx])) {
    const valeur = versNombre(lignes[idx + 1]);
    if (valeur === null) break;
    resultat[lignes[idx]] = valeur;
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

  while (i < lignes.length) {
    const titre = lignes[i];

    if (titre === "1X2 | Fin de Match") {
      const r = lirePaires(lignes, i + 1, 3); i = r.index;
      if (Object.keys(r.paires).length === 3) cotes["1x2"] = { "1": r.paires["1"], "N": r.paires["X"], "2": r.paires["2"] };
      continue;
    }

    if (titre === "Double Chance | Fin de Match") {
      const r = lirePaires(lignes, i + 1, 3); i = r.index;
      if (Object.keys(r.paires).length === 3) cotes["double_chance"] = { "1N": r.paires["1X"], "N2": r.paires["X2"], "12": r.paires["12"] };
      continue;
    }

    if (titre === "Les Deux Équipes Marquent | Fin de Match") {
      const r = lirePaires(lignes, i + 1, 2); i = r.index;
      if (Object.keys(r.paires).length === 2) cotes["btts"] = { "Oui": r.paires["Oui"], "Non": r.paires["Non"] };
      continue;
    }

    if (titre === "Plus de/Moins de | Fin de Match") {
      const r = lirePairesJusquaRupture(lignes, i + 1, REGEX_OU_RUPTURE); i = r.index;
      for (const [label, valeur] of Object.entries(r.paires)) {
        const m = label.match(REGEX_OU);
        cotes[`over_under_${m[2]}`] = cotes[`over_under_${m[2]}`] || {};
        cotes[`over_under_${m[2]}`][m[1] === "Plus" ? "plus" : "moins"] = valeur;
      }
      continue;
    }

    const mEquipe = titre.match(/^Plus de\/Moins de \| (.+) \| Fin de [Mm]atch$/);
    if (mEquipe) {
      const r = lirePairesJusquaRupture(lignes, i + 1, REGEX_OU_RUPTURE); i = r.index;
      const prefixe = mEquipe[1] === nomDomicile ? "over_under_domicile" : (mEquipe[1] === nomExterieur ? "over_under_exterieur" : null);
      if (prefixe) for (const [label, valeur] of Object.entries(r.paires)) {
        const m = label.match(REGEX_OU);
        cotes[`${prefixe}_${m[2]}`] = cotes[`${prefixe}_${m[2]}`] || {};
        cotes[`${prefixe}_${m[2]}`][m[1] === "Plus" ? "plus" : "moins"] = valeur;
      }
      continue;
    }

    if (titre === "Handicap À 3 Choix | Fin de Match") {
      i += 1;
      while (i < lignes.length && ["1", "X", "2"].includes(lignes[i])) i += 1;
      while (i + 5 < lignes.length) {
        const l1 = lignes[i], l2 = lignes[i + 2], l3 = lignes[i + 4];
        if (!/^Domicile\s+-\d+$/i.test(l1) || !/^Nul\s+-\d+$/i.test(l2) || !/^Extérieur\s+\+\d+$/i.test(l3)) break;
        const ligne = parseInt(l1.match(/-\d+$/)[0].slice(1), 10);
        const vd = versNombre(lignes[i + 1]), vn = versNombre(lignes[i + 3]), ve = versNombre(lignes[i + 5]);
        if (vd === null || vn === null || ve === null) break;
        cotes[`handicap_3choix_${ligne}`] = { domicile: vd, nul: vn, exterieur: ve };
        i += 6;
      }
      continue;
    }

    if (titre === "Impair/Pair | Fin de Match") {
      const r = lirePaires(lignes, i + 1, 2); i = r.index;
      if (Object.keys(r.paires).length === 2) cotes["pair_impair"] = { pair: r.paires["Pair"], impair: r.paires["Impair"] };
      continue;
    }

    i += 1;
  }
  return cotes;
}

if (typeof module !== "undefined") module.exports = { parseBetpawa };