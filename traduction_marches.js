// traduction_marches.js — présentation des marchés, sans calcul ni décision.

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

  if (marche === "over_2_5") return "Plus de 2,5 buts";
  {
    const m = marche.match(/^over_under_total_(-?\d+(?:\.\d+)?)_(over|under)$/);
    if (m) {
      const ligne = m[1].replace(".", ",");
      return m[2] === "over" ? `Plus de ${ligne} buts` : `Moins de ${ligne} buts`;
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
      if (m[2] === "0.5" && m[3] === "under") return `${equipe} garde sa cage inviolée`;
      if (m[2] === "0.5" && m[3] === "over") return `${equipe} marque au moins un but`;
      return m[3] === "over"
        ? `${equipe} marque plus de ${ligne} but(s)`
        : `${equipe} marque moins de ${ligne} but(s)`;
    }
  }

  if (marche === "parite_pair") return "Nombre de buts pair";
  if (marche === "parite_impair") return "Nombre de buts impair";

  {
    const m = marche.match(/^handicap_(domicile|exterieur)_(-?\d+(?:\.\d+)?)$/);
    if (m) {
      const equipe = m[1] === "domicile" ? dom : ext;
      const ligneNum = parseFloat(m[2]);
      const ligneAffichee = (ligneNum > 0 ? "+" : "") + m[2].replace(".", ",");
      return `${equipe} avec un handicap de ${ligneAffichee}`;
    }
  }

  {
    const m = marche.match(/^combo_(1X|X2|12)_(over|under)_(-?\d+(?:\.\d+)?)$/);
    if (m) {
      const dc = m[1] === "1X" ? `${dom} ne perd pas` : m[1] === "X2" ? `${ext} ne perd pas` : "pas de match nul";
      const ligne = m[3].replace(".", ",");
      const total = m[2] === "over" ? `plus de ${ligne} buts` : `moins de ${ligne} buts`;
      return `${dc} et ${total}`;
    }
  }

  return marche.replace(/_/g, " ");
}

// IMPORTANT : "niveau" est un niveau d'éligibilité du filtre, pas une
// probabilité empirique de gain. On ne l'appelle plus "Confiance" dans l'UI.
const NIVEAU_VERS_CONFIANCE = {
  PREMIUM: { etoiles: 5, texte: "Éligibilité maximale" },
  TRES_FORT: { etoiles: 4, texte: "Éligibilité très forte" },
  FORT: { etoiles: 3, texte: "Éligibilité forte" },
  ELIGIBLE: { etoiles: 2, texte: "Éligibilité validée" },
  ELIGIBLE_PLUS: { etoiles: 1, texte: "Éligibilité minimale" },
};
function traduitNiveau(niveau) {
  return NIVEAU_VERS_CONFIANCE[niveau] || { etoiles: 1, texte: "Éligibilité minimale" };
}

function traduitPalierH2H(palier) {
  switch (palier) {
    case "TRES_FIABLE": return "Confirmé fortement par les confrontations directes passées";
    case "FIABLE": return "Confirmé par les confrontations directes passées";
    case "INDICATIF": return "Légèrement appuyé par l'historique direct, à prendre avec prudence";
    default: return null;
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
  module.exports = { traduitMarche, traduitNiveau, traduitPalierH2H, construitPhraseConfirmation };
}
