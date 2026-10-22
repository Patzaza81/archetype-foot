// traduction_marches.js — présentation des marchés, sans calcul ni décision.

// ── Mots simples pour tout le monde (22/10/2026, demande de Patrick) : « Plus de 2,5 buts » = « Au moins 3 buts dans le match » ──
const _butsN = (n) => `${n} but${n > 1 ? "s" : ""}`;
const _auMoins = (ligne) => Math.floor(Number(String(ligne).replace(",", "."))) + 1;   // 1,5 -> 2 ; 2,5 -> 3 ; 0,5 -> 1
function phraseTotalButs(sens, ligne) {                 // total du match
  const n = _auMoins(ligne);
  if (sens === "over") return `Au moins ${_butsN(n)} dans le match`;
  return n - 1 === 0 ? "Aucun but dans le match" : `${_butsN(n - 1)} au maximum dans le match`;
}
function phraseButsEquipe(equipe, sens, ligne) {         // buts d'une équipe
  const n = _auMoins(ligne);
  if (sens === "over") return `${equipe} marque au moins ${_butsN(n)}`;
  return n - 1 === 0 ? `${equipe} ne marque pas` : `${equipe} marque ${_butsN(n - 1)} au maximum`;
}
function phraseHandicap(ligne, equipe) {                 // buts marqués + ligne > buts encaissés, du point de vue de l'équipe
  const m = Math.floor(-ligne) + 1;
  if (m >= 1) return `${equipe} gagne${m > 1 ? ` par ${_butsN(m)} d'écart ou plus` : ""}`;
  return m === 0 ? `${equipe} ne perd pas` : `${equipe} ne perd pas par ${_butsN(1 - m)} d'écart ou plus`;
}
// Libellés « texte » des moteurs V3 / Europe (écrits par le pipeline, jamais modifiés) -> mots simples. Inconnu : renvoyé tel quel.
function clarifieLibelle(texte, equipes) {
  const t = String(texte || ""), d = (equipes && equipes.domicile) || "L'équipe à domicile", e = (equipes && equipes.exterieur) || "L'équipe à l'extérieur";
  let r;
  const fixes = {
    "Victoire domicile": `${d} gagne`, "Victoire extérieur": `${e} gagne`, "Match nul": "Match nul (égalité, quel que soit le score)",
    "Double chance 1X": `${d} ne perd pas (victoire ou nul)`, "Double chance X2": `${e} ne perd pas (victoire ou nul)`,
    "Double chance 12": "Pas de match nul (l'une des deux équipes gagne)",
    "Les deux équipes marquent": "Les deux équipes marquent (au moins 1 but chacune)",
    "Les deux équipes ne marquent pas toutes les deux": "Au moins une équipe ne marque pas",
    "Domicile n'encaisse pas": `${d} n'encaisse aucun but`, "Extérieur n'encaisse pas": `${e} n'encaisse aucun but`,
    "Domicile encaisse au moins un but": `${d} encaisse au moins 1 but`, "Extérieur encaisse au moins un but": `${e} encaisse au moins 1 but`,
    "Total de buts pair": "Nombre total de buts pair (0, 2, 4…)", "Total de buts impair": "Nombre total de buts impair (1, 3, 5…)",
    "6 buts ou plus": "6 buts ou plus dans le match",
  };
  if (fixes[t]) return fixes[t];
  if ((r = t.match(/^Score exact (\d+)-(\d+)$/))) return `Score exact : ${d} ${r[1]}-${r[2]} ${e}`;
  if ((r = t.match(/^Exactement (\d+) buts?$/))) return `Exactement ${_butsN(Number(r[1]))} dans le match`;
  if ((r = t.match(/^(Plus|Moins) de ([\d,.]+) buts?$/))) return phraseTotalButs(r[1] === "Plus" ? "over" : "under", r[2]);
  if ((r = t.match(/^(Domicile|Extérieur) marque (plus|moins) de ([\d,.]+) buts?$/))) return phraseButsEquipe(r[1] === "Domicile" ? d : e, r[2] === "plus" ? "over" : "under", r[3]);
  return t;
}

function traduitMarche(marche, equipes) {
  const dom = equipes.domicile || "Domicile";
  const ext = equipes.exterieur || "Extérieur";

  if (marche === "1x2_domicile") return `Victoire ${dom}`;
  if (marche === "1x2_nul") return "Match nul";
  if (marche === "1x2_exterieur") return `Victoire ${ext}`;

  if (marche === "double_chance_1X") return `${dom} ne perd pas`;
  if (marche === "double_chance_X2") return `${ext} ne perd pas`;
  if (marche === "double_chance_12") return "Pas de match nul";

  if (marche === "btts_oui") return "Les deux équipes marquent";
  if (marche === "btts_non") return "Une des deux équipes ne marque pas";

  if (marche === "over_2_5") return phraseTotalButs("over", 2.5);
  {
    const m = marche.match(/^over_under_total_(-?\d+(?:\.\d+)?)_(over|under)$/);
    if (m) {
      const ligne = m[1].replace(".", ",");
      return phraseTotalButs(m[2], ligne);
    }
  }

  if (marche === "cage_inviolee_domicile") return `${dom} garde sa cage inviolée`;
  if (marche === "cage_inviolee_exterieur") return `${ext} garde sa cage inviolée`;
  if (marche === "encaisse_domicile") return `${dom} encaisse au moins un but`;
  if (marche === "encaisse_exterieur") return `${ext} encaisse au moins un but`;

  {
    const m = marche.match(/^buts_equipe_(domicile|exterieur)_(-?\d+(?:\.\d+)?)_(over|under)$/);
    if (m) {
      const equipe = m[1] === "domicile" ? dom : ext;
      const ligne = m[2].replace(".", ",");
      return phraseButsEquipe(equipe, m[3], ligne);
    }
  }


  {
    const m = marche.match(/^handicap_(domicile|exterieur)_(-?\d+(?:\.\d+)?)$/);
    if (m) {
      const equipe = m[1] === "domicile" ? dom : ext;
      const ligneNum = parseFloat(m[2]);
      const ligneAffichee = (ligneNum > 0 ? "+" : "") + m[2].replace(".", ",");
      return `${phraseHandicap(ligneNum, equipe)} (handicap ${ligneAffichee})`;
    }
  }

  return marche.replace(/_/g, " ");
}

// ── Nom d'origine du marché (code V2 -> nom court comme sur le moteur V2R), affiché en gras au-dessus de l'explication ──
// 22/10/2026 : présentation commune « nom + phrase simple dessous » ; ne change aucun calcul, traduitMarche() reste inchangée.
function nomOrigineMarche(marche, equipes) {
  const dom = (equipes && equipes.domicile) || "Domicile", ext = (equipes && equipes.exterieur) || "Extérieur";
  const m = String(marche || ""), pt = (x) => String(x).replace(",", ".");
  let r;
  if (m === "1x2_domicile") return `Victoire ${dom}`;
  if (m === "1x2_nul") return "Match nul";
  if (m === "1x2_exterieur") return `Victoire ${ext}`;
  if ((r = m.match(/^double_chance_(1X|X2|12)$/))) return `Double chance ${r[1]}`;
  if (m === "btts_oui") return "BTTS - oui";
  if (m === "btts_non") return "BTTS - non";
  if (m === "over_2_5") return "Plus de 2.5 buts";
  if ((r = m.match(/^over_under_total_(-?\d+(?:\.\d+)?)_(over|under)$/))) return `${r[2] === "over" ? "Plus" : "Moins"} de ${pt(r[1])} buts`;
  if (m === "cage_inviolee_domicile") return "Cage inviolée - Domicile";
  if (m === "cage_inviolee_exterieur") return "Cage inviolée - Extérieur";
  if (m === "encaisse_domicile") return "Encaisse au moins 1 but - Domicile";
  if (m === "encaisse_exterieur") return "Encaisse au moins 1 but - Extérieur";
  if ((r = m.match(/^buts_equipe_(domicile|exterieur)_(-?\d+(?:\.\d+)?)_(over|under)$/))) return `${r[1] === "domicile" ? dom : ext} ${r[3] === "over" ? "marque +" : "marque moins de "}${pt(r[2])} buts`;
  if ((r = m.match(/^handicap_(domicile|exterieur)_(-?\d+(?:\.\d+)?)$/))) return `Handicap ${(parseFloat(r[2]) > 0 ? "+" : "") + pt(r[2])} - ${r[1] === "domicile" ? "Domicile" : "Extérieur"}`;
  return m.replace(/_/g, " ");
}
// HTML d'un pronostic : nom d'origine en gras + explication simple dessous (identiques : une seule ligne). Échappé.
function marcheAvecExplication(titre, explication) {
  if (typeof afMarcheHtml === "function") return afMarcheHtml(titre, explication);
  return String(explication || titre || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// AJOUT 17/09/2026 (Patrick, jargon technique pas toujours compris) --
// texte simplifié, mais garde l'esprit du commentaire d'origine :
// "niveau" reste un palier du filtre, jamais une probabilité de gain --
// "Solidité" ne prétend pas plus qu'"Éligibilité", juste en langage
// courant.
const NIVEAU_VERS_CONFIANCE = {
  PREMIUM: { etoiles: 5, texte: "Solidité maximale" },
  TRES_FORT: { etoiles: 4, texte: "Très solide" },
  FORT: { etoiles: 3, texte: "Solide" },
  ELIGIBLE: { etoiles: 2, texte: "Suffisamment solide" },
  ELIGIBLE_PLUS: { etoiles: 1, texte: "Solidité de base" },
  // Catégories de moteur_v2_6_9 (A : EV <= 20 %, probabilité >= 45 %, aucun artefact ; B : EV <= 20 %,
  // probabilité >= 30 %, au plus un artefact ; C : le reste hors D, qui est écartée). Aucune n'atteint 4-5 étoiles :
  // le moteur n'a pas encore de mesure de calibration réelle.
  CAT_A: { etoiles: 3, texte: "Solide" },
  CAT_B: { etoiles: 2, texte: "Suffisamment solide" },
  CAT_C: { etoiles: 1, texte: "Solidité de base" },
};
function traduitNiveau(niveau) {
  return NIVEAU_VERS_CONFIANCE[niveau] || { etoiles: 1, texte: "Solidité de base" };
}

function traduitPalierH2H(palier) {
  switch (palier) {
    case "TRES_FIABLE": return "Confirmé fortement par les confrontations directes passées";
    case "FIABLE": return "Confirmé par les confrontations directes passées";
    case "INDICATIF": return "Légèrement appuyé par l'historique direct, à prendre avec prudence";
    default: return null;
  }
}

// AJOUT 17/09/2026 (Patrick, jargon technique pas toujours compris) --
// "STABLE"/"INSTABLE"/"INDETERMINE" sont des valeurs internes du moteur
// (archetype_model/poisson/robustness.py), jamais traduites avant :
// affichées telles quelles dans "Détails de l'analyse", illisibles pour
// un visiteur qui ne connaît pas le code.
function traduitRobustesse(robustesse) {
  switch (robustesse) {
    case "STABLE": return "Résultat stable sur les différents scénarios testés";
    case "INSTABLE": return "Résultat qui varie selon le scénario testé";
    default: return "Non déterminée";
  }
}

function sujetConfirmation(marche, equipes) {
  const dom = equipes.domicile || "L'équipe à domicile";
  const ext = equipes.exterieur || "L'équipe à l'extérieur";
  if (marche === "1x2_domicile" || marche === "double_chance_1X") return { texte: dom, pluriel: false };
  if (marche === "1x2_exterieur" || marche === "double_chance_X2") return { texte: ext, pluriel: false };
  if (/^buts_equipe_domicile_|^cage_inviolee_domicile$|^encaisse_domicile$|^handicap_domicile_/.test(marche)) return { texte: dom, pluriel: false };
  if (/^buts_equipe_exterieur_|^cage_inviolee_exterieur$|^encaisse_exterieur$|^handicap_exterieur_/.test(marche)) return { texte: ext, pluriel: false };
  return { texte: "Les deux équipes (confondues)", pluriel: true };
}

function construitPhraseConfirmation(marche, confirmation, equipes) {
  if (!confirmation || !confirmation.nb_echantillon) return null;
  const { nb_confirmant, nb_echantillon } = confirmation;
  const pct = Math.round((nb_confirmant / nb_echantillon) * 100);
  const { texte, pluriel } = sujetConfirmation(marche, equipes);
  const verbe = pluriel ? "confirment" : "confirme";
  const possessif = pluriel ? "leurs" : "ses";
  return `${texte} ${verbe} cette tendance sur ${nb_confirmant} de ${possessif} ${nb_echantillon} derniers matchs comparables (${pct} %).`;
}

if (typeof module !== "undefined") {
  module.exports = { clarifieLibelle, phraseTotalButs, phraseButsEquipe, phraseHandicap, traduitMarche, traduitNiveau, traduitPalierH2H, traduitRobustesse, construitPhraseConfirmation, nomOrigineMarche, marcheAvecExplication };
}
