// traduction_marches.js — créé le 10/09/2026, à la demande de Patrick :
// "pas d'abréviations (P1/P2/P3, H2H, EDV...), langage simple".
//
// RÈGLE ABSOLUE : ce fichier ne fait AUCUN calcul et ne prend AUCUNE
// décision. Il transforme uniquement des clés techniques déjà produites
// par archetype_model (marche, niveau, h2h_palier) en texte lisible. Si
// une clé est inconnue, on affiche un texte de repli lisible plutôt que
// de deviner ou de planter -- jamais un throw pour un marché qu'on ne
// reconnaît pas encore.

/**
 * Traduit une clé de marché technique (ex. "over_under_total_3.5_under",
 * "handicap_domicile_-0.5", "1x2_domicile") en libellé français.
 * @param {string} marche - la clé technique produite par archetype_model
 * @param {{domicile: string, exterieur: string}} equipes
 * @returns {string} libellé prêt à afficher
 */
function traduitMarche(marche, equipes) {
  const dom = equipes.domicile || "Domicile";
  const ext = equipes.exterieur || "Extérieur";

  // -- 1X2 --
  if (marche === "1x2_domicile") return `Victoire ${dom}`;
  if (marche === "1x2_nul") return "Match nul";
  if (marche === "1x2_exterieur") return `Victoire ${ext}`;

  // -- Double chance --
  if (marche === "double_chance_1X") return `${dom} ne perd pas`;
  if (marche === "double_chance_X2") return `${ext} ne perd pas`;
  if (marche === "double_chance_12") return "Pas de match nul";

  // -- BTTS --
  if (marche === "btts_oui") return "Les deux équipes marquent";
  if (marche === "btts_non") return "Une des deux équipes ne marque pas";

  // -- Over/Under total (base historique "over_2_5" OU périmètre
  // dynamique "over_under_total_{ligne}_{sens}") --
  if (marche === "over_2_5") return "Plus de 2,5 buts";
  {
    const m = marche.match(/^over_under_total_(-?\d+(?:\.\d+)?)_(over|under)$/);
    if (m) {
      const ligne = m[1].replace(".", ",");
      return m[2] === "over" ? `Plus de ${ligne} buts` : `Moins de ${ligne} buts`;
    }
  }

  // -- Cage inviolée / encaisse (base historique, toujours ligne 0.5) --
  if (marche === "cage_inviolee_domicile") return `${dom} garde sa cage inviolée`;
  if (marche === "cage_inviolee_exterieur") return `${ext} garde sa cage inviolée`;
  if (marche === "encaisse_domicile") return `${dom} encaisse au moins un but`;
  if (marche === "encaisse_exterieur") return `${ext} encaisse au moins un but`;

  // -- Buts par équipe, périmètre dynamique (lignes hors 0.5, ou toute
  // ligne si jamais le nom générique est utilisé) --
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

  // -- Parité --
  if (marche === "parite_pair") return "Nombre de buts pair";
  if (marche === "parite_impair") return "Nombre de buts impair";

  // -- Handicap --
  {
    const m = marche.match(/^handicap_(domicile|exterieur)_(-?\d+(?:\.\d+)?)$/);
    if (m) {
      const equipe = m[1] === "domicile" ? dom : ext;
      const ligneNum = parseFloat(m[2]);
      const ligneAffichee = (ligneNum > 0 ? "+" : "") + m[2].replace(".", ",");
      return `${equipe} avec un handicap de ${ligneAffichee}`;
    }
  }

  // -- Combinés Double Chance + Total --
  {
    const m = marche.match(/^combo_(1X|X2|12)_(over|under)_(-?\d+(?:\.\d+)?)$/);
    if (m) {
      const dc = m[1] === "1X" ? `${dom} ne perd pas` : m[1] === "X2" ? `${ext} ne perd pas` : "pas de match nul";
      const ligne = m[3].replace(".", ",");
      const total = m[2] === "over" ? `plus de ${ligne} buts` : `moins de ${ligne} buts`;
      return `${dc} et ${total}`;
    }
  }

  // Repli : jamais un plantage, un libellé un peu technique mais lisible
  // plutôt qu'un crash sur un marché pas encore traduit ici.
  return marche.replace(/_/g, " ");
}

/** Traduit le niveau technique du moteur en étoiles + texte de confiance. */
const NIVEAU_VERS_CONFIANCE = {
  PREMIUM: { etoiles: 5, texte: "Exceptionnelle" },
  TRES_FORT: { etoiles: 4, texte: "Très forte" },
  FORT: { etoiles: 3, texte: "Forte" },
  ELIGIBLE: { etoiles: 2, texte: "Correcte" },
  ELIGIBLE_PLUS: { etoiles: 1, texte: "Suffisante" },
};
function traduitNiveau(niveau) {
  return NIVEAU_VERS_CONFIANCE[niveau] || { etoiles: 1, texte: "Suffisante" };
}

/** Traduit le palier H2H technique en phrase compréhensible, ou null si
 * l'historique direct est trop pauvre pour dire quoi que ce soit. */
function traduitPalierH2H(palier) {
  switch (palier) {
    case "TRES_FIABLE":
      return "Confirmé fortement par les confrontations directes passées";
    case "FIABLE":
      return "Confirmé par les confrontations directes passées";
    case "INDICATIF":
      return "Légèrement appuyé par l'historique direct, à prendre avec prudence";
    default:
      return null; // INSUFFISANT ou inconnu : on ne dit rien plutôt que d'inventer
  }
}

/** Détermine le sujet de la phrase de confirmation selon le marché :
 * une équipe précise, ou "les deux équipes confondues" pour les marchés
 * qui combinent les matchs des deux (buts total, BTTS, parité...). Pure
 * traduction -- ne décide de rien, se contente de savoir quelle liste de
 * matchs le comptage (déjà calculé côté serveur) représente. */
function sujetConfirmation(marche, equipes) {
  const dom = equipes.domicile || "L'équipe à domicile";
  const ext = equipes.exterieur || "L'équipe à l'extérieur";
  if (marche === "1x2_domicile" || marche === "double_chance_1X") return { texte: dom, pluriel: false };
  if (marche === "1x2_exterieur" || marche === "double_chance_X2") return { texte: ext, pluriel: false };
  if (/^buts_equipe_domicile_|^cage_inviolee_domicile$|^encaisse_domicile$|^handicap_domicile_/.test(marche)) return { texte: dom, pluriel: false };
  if (/^buts_equipe_exterieur_|^cage_inviolee_exterieur$|^encaisse_exterieur$|^handicap_exterieur_/.test(marche)) return { texte: ext, pluriel: false };
  return { texte: "Les deux équipes (confondues)", pluriel: true };
}

/**
 * Construit la phrase "Pourquoi ?" chiffrée à partir du comptage réel
 * `confirmation` = {nb_confirmant, nb_echantillon} déjà calculé côté
 * serveur (archetype_model/justification.py) sur les matchs réellement
 * joués. Ne recalcule rien, ne fabrique aucun chiffre : si `confirmation`
 * est null (marché pas encore couvert par ce comptage), renvoie null --
 * l'appelant doit alors utiliser une phrase générique de repli.
 */
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
