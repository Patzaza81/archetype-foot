// ui_mappings.js — contrat visuel du jargon de la bibliothèque de justification.
// Présentation UNIQUEMENT : associe chaque type de preuve (champ `type` produit par
// bibliotheque_justification.py) à une icône, une couleur et un libellé français.
// Le site ne recalcule rien : il affiche ce que la bibliothèque a produit.
// L'objet est figé (Object.freeze) : aucune autre partie du code ne doit le modifier.

const ICONES_ANALYSE = Object.freeze({
  "shield-check": '<path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6z"/><polyline points="9 12 11 14 15 10"/>',
  "trending-up": '<polyline points="3 17 9 11 13 15 21 7"/><polyline points="15 7 21 7 21 13"/>',
  "trending-down": '<polyline points="3 7 9 13 13 9 21 17"/><polyline points="15 17 21 17 21 11"/>',
  "goal": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="0.9" fill="currentColor"/>',
  "swords": '<path d="M5 19 19 5"/><polyline points="14 5 19 5 19 10"/><path d="M19 19 5 5"/><polyline points="5 10 5 5 10 5"/>',
  "flame": '<path d="M12 3c.6 3.2 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3.2 2.2-4.2.1 1.6.9 2.6 1.8 2.6.4-2.6-.2-5.2 1-8.4z"/>',
  "snowflake": '<path d="M12 3v18"/><path d="M4.2 7.5l15.6 9"/><path d="M4.2 16.5l15.6-9"/>',
  "history": '<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1"/><polyline points="3.5 4 3.5 9 8.5 9"/><polyline points="12 7.5 12 12 15 14"/>',
  "swap": '<polyline points="17 4 21 8 17 12"/><path d="M21 8H8"/><polyline points="7 20 3 16 7 12"/><path d="M3 16h13"/>',
  "cash": '<circle cx="12" cy="12" r="9"/><path d="M12 6.5v11"/><path d="M14.8 9.2c0-1.1-1.2-1.7-2.8-1.7s-2.8.7-2.8 1.8c0 2.6 5.6 1.4 5.6 4 0 1.1-1.2 1.9-2.8 1.9s-2.8-.6-2.8-1.7"/>',
  "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6"/><path d="M12 7.6v.4"/>',
});

const VERT = "#2E7D32", BLEU = "#1565C0", ROUGE = "#C62828", ORANGE = "#E65100", VIOLET = "#6A1B9A",
  BRUN = "#D84315", CIEL = "#0277BD", SARCELLE = "#00838F", VERT_FONCE = "#1B5E20";

// Types produits aujourd'hui par la bibliothèque. Un type inconnu s'affiche avec l'icône « info »
// et son nom brut : rien n'est inventé, et l'oubli se voit tout de suite.
const PREUVE_META = Object.freeze({
  // forme récente
  home_unbeaten_streak: Object.freeze({ icon: "shield-check", color: VERT, label: "Invincibilité domicile" }),
  away_unbeaten_streak: Object.freeze({ icon: "shield-check", color: VERT, label: "Invincibilité extérieur" }),
  away_winless_streak: Object.freeze({ icon: "trending-down", color: ROUGE, label: "Série à l'extérieur" }), // ancien type (données d'avant le 21/09)
  home_win_rate: Object.freeze({ icon: "trending-up", color: BLEU, label: "Taux de victoire domicile" }),
  home_loss_rate: Object.freeze({ icon: "trending-down", color: ROUGE, label: "Taux de défaite domicile" }),
  away_loss_rate: Object.freeze({ icon: "trending-down", color: ROUGE, label: "Taux de défaite extérieur" }),
  away_concede_pct: Object.freeze({ icon: "goal", color: ORANGE, label: "Fragilité défensive" }),
  // confrontations directes
  h2h_unbeaten_count: Object.freeze({ icon: "swords", color: VIOLET, label: "Avantage H2H" }),
  h2h_x2_unbeaten_count: Object.freeze({ icon: "swords", color: VIOLET, label: "Avantage H2H" }),
  h2h_over_count: Object.freeze({ icon: "history", color: VIOLET, label: "Historique prolifique" }),
  h2h_under_count: Object.freeze({ icon: "history", color: VIOLET, label: "Historique fermé" }),
  h2h_no_draw_count: Object.freeze({ icon: "swords", color: VIOLET, label: "Historique décisif" }),
  h2h_draw_count: Object.freeze({ icon: "swords", color: VIOLET, label: "Historique serré" }),
  // rythme des deux équipes
  over_15_rate_combined: Object.freeze({ icon: "flame", color: BRUN, label: "Rythme offensif" }),
  over_line_rate_combined: Object.freeze({ icon: "flame", color: BRUN, label: "Rythme offensif" }),
  under_15_rate_combined: Object.freeze({ icon: "snowflake", color: CIEL, label: "Rythme fermé" }),
  under_line_rate_combined: Object.freeze({ icon: "snowflake", color: CIEL, label: "Rythme fermé" }),
  avg_goals_conceded_combined: Object.freeze({ icon: "goal", color: ORANGE, label: "Série ouverte" }),
  // les deux équipes marquent / ne marquent pas
  both_teams_score_rate: Object.freeze({ icon: "swap", color: SARCELLE, label: "Efficacité croisée" }),
  away_score_rate_home_concede_rate: Object.freeze({ icon: "swap", color: SARCELLE, label: "Match ouvert" }),
  both_teams_score_rate_low: Object.freeze({ icon: "snowflake", color: CIEL, label: "Match fermé" }),
  away_score_rate_low: Object.freeze({ icon: "snowflake", color: CIEL, label: "Attaque muette" }),
  home_clean_sheet_rate: Object.freeze({ icon: "shield-check", color: VERT, label: "Défense solide" }),
  // nuls
  draw_rate_combined_low: Object.freeze({ icon: "trending-up", color: BLEU, label: "Peu de nuls" }),
  draw_rate_combined_high: Object.freeze({ icon: "swap", color: SARCELLE, label: "Nuls fréquents" }),
  // buts d'une équipe
  team_goals_over_rate: Object.freeze({ icon: "flame", color: BRUN, label: "Attaque en forme" }),
  opp_concede_over_rate: Object.freeze({ icon: "goal", color: ORANGE, label: "Défense adverse fragile" }),
  team_goals_under_rate: Object.freeze({ icon: "snowflake", color: CIEL, label: "Attaque limitée" }),
  opp_concede_under_rate: Object.freeze({ icon: "shield-check", color: VERT, label: "Défense adverse solide" }),
  // avantage statistique (cote supérieure à la valeur jugée équitable)
  ev_percentage: Object.freeze({ icon: "cash", color: VERT_FONCE, label: "Value Bet" }),
});

const PREUVE_META_INCONNUE = Object.freeze({ icon: "info", color: "#555555" });
