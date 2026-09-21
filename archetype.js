// archetype.js — présentation uniquement (réécriture complète du 20/09/2026).
// Le navigateur ne choisit aucun pronostic et ne calcule aucune statistique :
// tout ce qui est affiché vient de precalcul_leger.json (archetype_model.selection).
//
// Contrat conservé pour panier.js : construitCarte(), regroupeMatchs(),
// estArchetypeGo(), echappeHtml() gardent leur nom, et chaque carte contient
// un <details class="details-analyse"> (panier.js l'ouvre via "Voir l'analyse").

const RANGS = [
  { cle: "P1", classe: "rang-1", titre: "Favori du Modèle" },
  { cle: "P2", classe: "rang-2", titre: "Value Bet" },
  { cle: "P3", classe: "rang-3", titre: "Coup de Poker" },
];

// Seuils de sélection des onglets (étape 6).
const SEUIL_COUP_DE_POKER_COTE = 2.91;
const SEUIL_COUP_DE_POKER_PROBA = 0.20;

// "Forme récente" n'accepte que des preuves qui décrivent réellement la forme
// (règle du 18/09/2026) : jamais une statistique de buts croisée.
const TYPES_FORME_RECENTE = new Set(["home_unbeaten_streak", "away_concede_pct"]);

const CLE_THEME_NUIT = "archetype_theme_nuit"; // même clé que theme.js
let compteurCartes = 0;

/* ───────────────────────── outils ───────────────────────── */

// estArchetypeGo : conservée telle quelle pour compatibilité panier.js.
// Sens historique : match avec un candidat P1 minimum.
function estArchetypeGo(m) {
  return !!(m && m.moteur_utilise === "archetype_model" && m.archetype_model &&
    m.archetype_model.statut === "OK" && m.archetype_model.selection && m.archetype_model.selection.P1);
}

// aAuMoinsUnCandidat : filtre d'affichage de la page principale.
function aAuMoinsUnCandidat(m) {
  if (!m || m.moteur_utilise !== "archetype_model" || !m.archetype_model) return false;
  const sel = m.archetype_model.selection;
  if (!sel) return false;
  return !!(sel.P1 || sel.P2 || sel.P3);
}

// remappeEnOngletsApp : transforme les candidats {P1, P2, P3} de precalcul_leger.json
// en 3 onglets sémantiques {Favori du Modèle, Value Bet, Coup de Poker} selon les
// règles métier de la maquette. Chaque candidat n'apparaît que dans un seul onglet.
function remappeEnOngletsApp(selectionBrute) {
  const candidats = ["P1", "P2", "P3"].map((cle) => selectionBrute[cle]).filter(Boolean);
  if (!candidats.length) return {};

  // Favori du Modèle = plus forte probabilité du modèle.
  const favori = candidats.reduce((best, c) =>
    (Number(c.probabilite) || 0) > (Number(best.probabilite) || 0) ? c : best);

  // Value Bet = meilleur EV parmi les candidats restants.
  const restantsPourValue = candidats.filter((c) => c !== favori);
  const value = restantsPourValue.length
    ? restantsPourValue.reduce((best, c) =>
        (Number(c.edv) || 0) > (Number(best.edv) || 0) ? c : best)
    : null;

  // Coup de Poker = premier candidat restant satisfaisant cote >= 2.91 et P >= 0.20.
  const restantsPourPoker = candidats.filter((c) => c !== favori && c !== value);
  const poker = restantsPourPoker.find((c) =>
    (Number(c.cote) || 0) >= SEUIL_COUP_DE_POKER_COTE &&
    (Number(c.probabilite) || 0) >= SEUIL_COUP_DE_POKER_PROBA) || null;

  return { P1: favori, P2: value, P3: poker };
}

function echappeHtml(x) {
  return x === null || x === undefined ? "" : String(x)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function formatCote(x) { const n = Number(x); return Number.isFinite(n) ? n.toFixed(2).replace(".", ",") : "—"; }
function formatPctEntier(x) { const n = Number(x); return Number.isFinite(n) ? `${Math.round(n * 100)} %` : "—"; }
function formatPctSigne(x) {
  const n = Number(x); if (!Number.isFinite(n)) return "—";
  return `${n >= 0 ? "+" : "−"}${Math.abs(n * 100).toFixed(1).replace(".", ",")} %`;
}
function formatDate(dateIso) {
  if (!dateIso) return "";
  const d = new Date(`${dateIso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return dateIso;
  const t = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

const ICONES = {
  forme: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V11h4v9H4zm6 0V4h4v16h-4zm6 0v-6h4v6h-4z"/></svg>',
  h2h: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 4 5v6c0 5 3.4 9.3 8 11 4.6-1.7 8-6 8-11V5l-8-3zm-1.2 14.2-3.5-3.5 1.4-1.4 2.1 2.1 4.6-4.6 1.4 1.4-6 6z"/></svg>',
  avantage: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 21v-6h4v6H3zm7 0v-10h4v10h-4zm7 0V7h4v14h-4zM4 9l6-5 4 3 6-5v3l-6 5-4-3-6 4V9z"/></svg>',
  gain: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4l8 8-8 8v-5H3V9h11V4z"/></svg>',
};

function construitJauge(probabilite, classe) {
  const n = Number(probabilite); if (!Number.isFinite(n)) return "";
  const v = Math.max(0, Math.min(1, n)), r = 42, c = 2 * Math.PI * r, pct = Math.round(v * 100);
  return `<div class="ax-jauge ${classe || ""}" role="img" aria-label="Probabilité du modèle : ${pct} %">` +
    `<svg viewBox="0 0 100 100" aria-hidden="true">` +
    `<circle class="ax-jauge-fond" cx="50" cy="50" r="${r}"></circle>` +
    `<circle class="ax-jauge-valeur" cx="50" cy="50" r="${r}" stroke-dasharray="${(c * v).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 50 50)"></circle>` +
    `<circle class="ax-jauge-centre" cx="50" cy="50" r="33"></circle>` +
    `<text class="ax-jauge-texte" x="50" y="51">${pct}%</text></svg></div>`;
}

function construitEtoiles(etoiles) {
  const n = Math.max(0, Math.min(5, Number(etoiles) || 0));
  return `<span class="ax-etoiles" role="img" aria-label="Solidité : ${n} sur 5">` +
    `${"★".repeat(n)}<span class="ax-etoiles-vides">${"★".repeat(5 - n)}</span></span>`;
}

/* ───────────────────── blocs de la carte ───────────────────── */

// Aperçu compact (carte repliée) : les 3 rangs, chacun avec marché, cote, probabilité et jauge.
function construitResume(selection, equipes) {
  const div = document.createElement("div");
  div.className = "ax-resume";
  // Un choix sans candidat n'a pas de ligne ici : son onglet, juste au-dessus, indique déjà « Non disponible ».
  div.innerHTML = RANGS.map((info) => {
    const c = selection[info.cle];
    if (!c) return "";
    // Phrase de justification qui accompagne le marché (même source que le panneau déplié : justification.resume).
    const texte = c.justification && c.justification.resume ? c.justification.resume : "";
    return `<div class="ax-resume-rang ax-${info.classe}" data-cle="${info.cle}">` +
      `<div class="ax-resume-corps">` +
      `<div class="ax-resume-tete"><span class="ax-resume-etiquette">${echappeHtml(info.titre)}</span>` +
      `<span class="ax-resume-cote">Cote <strong>${formatCote(c.cote)}</strong></span></div>` +
      `<h3 class="ax-resume-marche">${echappeHtml(traduitMarche(c.marche, equipes))}</h3>` +
      (texte ? `<p class="ax-resume-texte">${echappeHtml(texte)}</p>` : "") + `</div>` +
      `${construitJauge(c.probabilite, "ax-jauge-mini")}</div>`;
  }).join("");
  return div;
}

// Panneau détaillé d'un rang (carte dépliée) — structure de la maquette.
function construitPanneau(info, c, equipes, idPanneau, idOnglet) {
  const preuves = (c.justification && Array.isArray(c.justification.preuves)) ? c.justification.preuves : [];
  const resume = c.justification && c.justification.resume ? c.justification.resume : "";
  const h2h = preuves.find((p) => p && typeof p.type === "string" && p.type.startsWith("h2h_"));
  const forme = preuves.find((p) => p && typeof p.type === "string" && TYPES_FORME_RECENTE.has(p.type));
  const niveau = traduitNiveau(c.niveau);
  const el = document.createElement("div");
  el.className = `ax-panneau ax-${info.classe}`;
  el.id = idPanneau; el.setAttribute("role", "tabpanel"); el.setAttribute("aria-labelledby", idOnglet);
  el.dataset.cle = info.cle;
  el.innerHTML =
    `<h2 class="ax-marche">${echappeHtml(traduitMarche(c.marche, equipes))}</h2>` +
    `<div class="ax-ligne-cote">` +
      `<p class="ax-texte-resume">${echappeHtml(resume)}</p>` +
      `<div class="ax-badge-cote"><span>Cote</span><strong>${formatCote(c.cote)}</strong></div>` +
    `</div>` +
    `<div class="ax-preuves">` +
      `<div class="ax-preuves-liste">` +
        `<div class="ax-preuve"><span class="ax-icone">${ICONES.forme}</span><div><span class="ax-preuve-titre">Forme récente</span>` +
          `<span class="ax-preuve-texte">${echappeHtml(forme ? forme.texte : "Non disponible")}</span></div></div>` +
        `<div class="ax-preuve"><span class="ax-icone">${ICONES.h2h}</span><div><span class="ax-preuve-titre">Confrontations directes</span>` +
          `<span class="ax-preuve-texte">${echappeHtml(h2h ? h2h.texte : "Non disponible")}</span></div></div>` +
      `</div>` +
      `<div class="ax-proba">${construitJauge(c.probabilite, "")}` +
        `<span class="ax-proba-legende">Probabilité du modèle</span>` +
        `${construitEtoiles(niveau.etoiles)}<span class="ax-solidite">${/solidit/i.test(niveau.texte) ? "" : '<span class="ax-solidite-titre">Solidité :</span> '}${echappeHtml(niveau.texte)}</span></div>` +
    `</div>` +
    `<ul class="ax-metriques">` +
      `<li title="Écart entre la probabilité calculée par le modèle et celle qui serait 'normale' vu la cote proposée."><span class="ax-icone">${ICONES.avantage}</span><strong>${formatPctSigne(c.edge)}</strong><span>Avantage potentiel</span></li>` +
      `<li title="Ce que rapporterait ce pari en moyenne si on le rejouait de nombreuses fois, selon le modèle."><span class="ax-icone">${ICONES.gain}</span><strong>${formatPctSigne(c.edv)}</strong><span>Gain potentiel</span></li>` +
    `</ul>`;
  return el;
}

/* ═════════ Détails de l'analyse : tableaux alimentés par la bibliothèque de justification ═════════
   Règles d'affichage (elles traduisent la règle « calculable exactement » de la bibliothèque) :
   1. jamais de tableau vide : sans aucune ligne, le tableau n'existe pas ;
   2. jamais de « — », « N/A » ou « null » : une valeur non calculable n'a pas de ligne ;
   3. la preuve EV a un badge distinct, jamais noyée parmi les preuves métier ;
   4. le résumé ne remplace pas les preuves : il sert de synthèse, les preuves sont le corps ;
   5. donnees_suffisantes === false : un seul message neutre, aucun tableau ;
   6. le site ne recalcule rien : il lit resume, preuves et bibliotheque et les affiche. */
const estNombre = (x) => typeof x === "number" && Number.isFinite(x);
const fmtNombre = (x, dec) => x.toFixed(dec).replace(".", ",");
const fmtPct = (x) => `${fmtNombre(x, 1)} %`;
const fmtMatchs = (n) => `${n} match${n > 1 ? "s" : ""}`;

function iconeAnalyse(nom) {
  const chemin = ICONES_ANALYSE[nom] || ICONES_ANALYSE.info;
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${chemin}</svg>`;
}

// Une ligne n'existe que si sa valeur est calculable.
function lig(libelle, valeur, formate) { return estNombre(valeur) ? [libelle, formate(valeur)] : null; }

function tableauLignes(titre, lignes, pied) {
  const l = lignes.filter(Boolean);
  if (!l.length) return "";
  return `<div class="ax-tab"><h4 class="ax-tab-titre">${echappeHtml(titre)}</h4>` +
    `<table class="ax-tab-lignes"><tbody>${l.map(([lib, val]) => `<tr><th scope="row">${echappeHtml(lib)}</th><td>${echappeHtml(val)}</td></tr>`).join("")}</tbody></table>` +
    (pied ? `<p class="ax-tab-pied">${echappeHtml(pied)}</p>` : "") + `</div>`;
}

function tableauResume(resume) {
  if (!resume) return "";
  return `<div class="ax-tab ax-tab-resume"><p class="ax-tab-etiquette">Synthèse du modèle</p><p class="ax-tab-resume-texte">${echappeHtml(resume)}</p></div>`;
}

function tableauPreuves(preuves, b) {
  const liste = (Array.isArray(preuves) ? preuves : []).filter((p) => p && p.texte);
  const lignes = liste.map((p) => {
    const meta = PREUVE_META[p.type] || { ...PREUVE_META_INCONNUE, label: p.type };
    const ev = p.type === "ev_percentage";
    const badge = ev && estNombre(p.valeur) ? `<span class="ax-ev-badge">+${fmtNombre(p.valeur, 1)} %</span>` : "";
    return `<li class="ax-preuve-ligne${ev ? " ax-ev" : ""}">` +
      `<span class="ax-ico" style="color:${echappeHtml(meta.color)};background:${echappeHtml(meta.color)}22">${iconeAnalyse(meta.icon)}</span>` +
      `<div class="ax-preuve-corps"><span class="ax-preuve-lib">${echappeHtml(meta.label)}</span><span class="ax-preuve-txt">${echappeHtml(p.texte)}</span></div>${badge}</li>`;
  });
  // Badge EV « si disponible » : la preuve peut avoir été écartée de la liste (3 maximum) alors que la valeur existe.
  if (!liste.some((p) => p.type === "ev_percentage") && estNombre(b.ev_percentage)) {
    const meta = PREUVE_META.ev_percentage;
    lignes.push(`<li class="ax-preuve-ligne ax-ev"><span class="ax-ico" style="color:${meta.color};background:${meta.color}22">${iconeAnalyse(meta.icon)}</span>` +
      `<div class="ax-preuve-corps"><span class="ax-preuve-lib">${meta.label}</span></div><span class="ax-ev-badge">+${fmtNombre(b.ev_percentage, 1)} %</span></li>`);
  }
  if (!lignes.length) return "";
  return `<div class="ax-tab"><h4 class="ax-tab-titre">Preuves du modèle</h4><ul class="ax-preuve-liste">${lignes.join("")}</ul></div>`;
}

function tableauForme(titre, b, domicile) {
  const lignes = domicile ? [
    lig("Série sans défaite", b.home_unbeaten_streak, fmtMatchs),
    lig("Série sans victoire", b.home_winless_streak, fmtMatchs),
    lig("Taux de victoire", b.home_win_rate, fmtPct),
    lig("Taux de défaite", b.home_loss_rate, fmtPct),
    lig("Matchs avec ≥1 but encaissé", b.home_concede_rate, fmtPct),
  ] : [
    lig("Série sans défaite", b.away_unbeaten_streak, fmtMatchs),
    lig("Série sans victoire", b.away_winless_streak, fmtMatchs),
    lig("Taux de victoire", b.away_win_rate, fmtPct),
    lig("Taux de défaite", b.away_loss_rate, fmtPct),
    lig("Matchs avec ≥1 but encaissé", b.away_concede_pct, fmtPct),
    lig("Matchs avec ≥1 but marqué", b.away_score_rate, fmtPct),
  ];
  return tableauLignes(titre, lignes);
}

function tableauH2H(b) {
  const total = b.h2h_total;
  if (!estNombre(total) || total <= 0) return "";
  const cible = estNombre(b.target_goals) ? fmtNombre(b.target_goals, 1) : null;
  const lignes = [
    estNombre(b.h2h_unbeaten_count) ? ["Domicile invaincu", `${b.h2h_unbeaten_count} / ${total}`] : null,
    estNombre(b.h2h_draw_count) ? ["Matchs nuls", `${b.h2h_draw_count} / ${total}`] : null,
    cible && estNombre(b.h2h_over_count)
      ? [`Matchs > ${cible} buts`, `${b.h2h_over_count} / ${total}` + (estNombre(b.h2h_over_rate) ? ` (${fmtNombre(b.h2h_over_rate, 1)} %)` : "")]
      : null,
  ];
  return tableauLignes("Confrontations directes", lignes, `${total} confrontation${total > 1 ? "s" : ""} analysée${total > 1 ? "s" : ""}`);
}

function tableauCombine(b) {
  const cible = estNombre(b.target_goals) ? fmtNombre(b.target_goals, 1) : null;
  const lignes = [
    lig("Matchs > 1,5 but (combiné)", b.over_15_rate_combined, fmtPct),
    // la ligne 1,5 est déjà couverte par over_15_rate_combined : pas de doublon
    cible && b.target_goals !== 1.5 ? lig(`Matchs > ${cible} buts (combiné)`, b.over_rate_combined, fmtPct) : null,
    lig("Moyenne buts encaissés", b.avg_goals_conceded_combined, (x) => fmtNombre(x, 2)),
    lig("Les 2 équipes marquent", b.both_teams_score_rate, fmtPct),
    lig("Matchs nuls (combiné)", b.draw_rate_combined, fmtPct),
  ];
  return tableauLignes("Métriques combinées", lignes);
}

function construitAnalyse(info, c, equipes) {
  const j = c.justification || {};
  const b = j.bibliotheque && typeof j.bibliotheque === "object" ? j.bibliotheque : {};
  const tete = `<h3>${echappeHtml(info.titre)} — ${echappeHtml(traduitMarche(c.marche, equipes))}</h3>`;
  const ouvre = `<div class="ax-detail-rang ax-${info.classe}" data-cle="${info.cle}" hidden>`;
  if (!j.donnees_suffisantes) {
    return ouvre + tete + `<div class="ax-analyse-vide"><strong>Analyse non disponible</strong>` +
      `<p>Données historiques insuffisantes pour justifier ce marché.</p></div></div>`;
  }
  return ouvre + tete +
    tableauResume(j.resume) +
    tableauPreuves(j.preuves, b) +
    tableauForme(`Forme récente — ${equipes.domicile} (à domicile)`, b, true) +
    tableauForme(`Forme récente — ${equipes.exterieur} (à l'extérieur)`, b, false) +
    tableauH2H(b) +
    tableauCombine(b) +
    `<dl class="ax-fiabilite"><div><dt>Solidité du pari</dt><dd>${echappeHtml(traduitNiveau(c.niveau).texte)}</dd></div>` +
    `<div><dt>Stabilité du calcul</dt><dd>${echappeHtml(traduitRobustesse(c.robustesse))}</dd></div></dl></div>`;
}

// Bloc <details class="details-analyse"> : conservé pour panier.js. Le <summary> est masqué
// (.ax-summary-cache) ; c'est le bouton « Détails de l'analyse » du pied de carte qui l'ouvre.
// Un panneau par choix disponible ; seul celui de l'onglet actif est affiché (voir construitCarte).
function construitDetails(selection, equipes, idDetails) {
  const details = document.createElement("details");
  details.className = "details-analyse ax-details";
  details.id = idDetails;
  const blocs = RANGS.filter((r) => selection[r.cle]).map((r) => construitAnalyse(r, selection[r.cle], equipes)).join("");
  details.innerHTML = `<summary class="ax-summary-cache" tabindex="-1">Détails de l'analyse</summary><div class="ax-details-corps">${blocs}</div>`;
  return details;
}

function construitCarte(m, options) {
  const opt = options || {};
  const id = ++compteurCartes;
  const idDetails = `ax-details-${id}`;
  const equipes = { domicile: m.domicile || "Équipe à domicile", exterieur: m.exterieur || "Équipe à l'extérieur" };
  const heure = m.heure_cameroun || m.heure || "—";
  const date = formatDate(m.date);
  const competition = String(m.competition || "").replace(/\s+/g, " ").trim();
  // Étape 6 : les candidats bruts P1/P2/P3 sont remappés en 3 onglets sémantiques.
  const selection = remappeEnOngletsApp((m.archetype_model && m.archetype_model.selection) || {});

  const section = document.createElement("section");
  section.className = "ax-carte";
  section.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match">` +
      `<span class="ax-equipe ax-dom">${echappeHtml(equipes.domicile)}</span>` +
      `<div class="ax-horaire"><strong>${echappeHtml(heure)}</strong><span>${echappeHtml(date)}</span></div>` +
      `<span class="ax-equipe ax-ext">${echappeHtml(equipes.exterieur)}</span></div>` +
      `<div class="ax-match-bas"><p class="ax-competition">${echappeHtml(competition)}</p><div class="ax-actions-tete"></div></div>` +
    `</div>`;

  // Onglets : les 3 sont toujours affichés ; un rang sans candidat est grisé et non cliquable.
  const onglets = document.createElement("div");
  onglets.className = "ax-onglets"; onglets.setAttribute("role", "tablist"); onglets.setAttribute("aria-label", "Choix du pronostic");
  const panneaux = document.createElement("div");
  panneaux.className = "ax-panneaux";
  const actifs = [];
  RANGS.forEach((info) => {
    const c = selection[info.cle];
    const idOnglet = `ax-onglet-${id}-${info.cle}`, idPanneau = `ax-panneau-${id}-${info.cle}`;
    const bouton = document.createElement("button");
    bouton.type = "button"; bouton.id = idOnglet; bouton.className = `ax-onglet ax-${info.classe}`;
    bouton.setAttribute("role", "tab"); bouton.dataset.cle = info.cle;
    if (!c) {
      bouton.disabled = true; bouton.classList.add("ax-vide");
      bouton.innerHTML = `<span>${echappeHtml(info.titre)}</span><small>Non disponible</small>`;
      onglets.appendChild(bouton); return;
    }
    bouton.setAttribute("aria-controls", idPanneau);
    bouton.innerHTML = `<span>${echappeHtml(info.titre)}</span>`;
    const panneau = construitPanneau(info, c, equipes, idPanneau, idOnglet);
    onglets.appendChild(bouton); actifs.push({ bouton, panneau });
  });
  // Résumé compact (visible carte repliée) : placé SOUS les onglets ; il n'affiche que le choix de l'onglet actif.
  const resume = construitResume(selection, equipes);
  // Bloc <details> (repliable) placé juste avant le pied ; son <summary> est caché, c'est le bouton
  // « Détails de l'analyse » dans le pied qui l'ouvre. Il montre l'analyse de l'onglet actif.
  const blocDetails = construitDetails(selection, equipes, idDetails);
  const active = (cible) => {
    actifs.forEach(({ bouton, panneau }) => {
      const oui = bouton === cible;
      bouton.classList.toggle("ax-actif", oui); bouton.setAttribute("aria-selected", String(oui)); bouton.tabIndex = oui ? 0 : -1;
      panneau.hidden = !oui;
    });
    resume.querySelectorAll(".ax-resume-rang").forEach((ligne) => { ligne.hidden = ligne.dataset.cle !== cible.dataset.cle; });
    blocDetails.querySelectorAll(".ax-detail-rang").forEach((bloc) => { bloc.hidden = bloc.dataset.cle !== cible.dataset.cle; });
  };
  actifs.forEach(({ bouton, panneau }) => { bouton.addEventListener("click", () => active(bouton)); panneaux.appendChild(panneau); });
  if (actifs.length) { active(actifs[0].bouton); section.appendChild(onglets); section.appendChild(panneaux); }

  section.appendChild(resume);

  section.appendChild(blocDetails);

  // Pied de carte : bouton « Détails de l'analyse » (secondaire) et bouton
  // « Plier » (principal), les deux alignés à droite.
  const deplier = document.createElement("button");
  deplier.type = "button"; deplier.className = "ax-deplier";
  const pied = document.createElement("div");
  pied.className = "ax-pied";
  const boutonDetails = document.createElement("button");
  boutonDetails.type = "button"; boutonDetails.className = "ax-bouton-details";
  boutonDetails.textContent = "Détails de l'analyse";
  boutonDetails.setAttribute("aria-controls", idDetails);
  boutonDetails.setAttribute("aria-expanded", "false");
  const plier = document.createElement("button");
  plier.type = "button"; plier.className = "ax-plier";

  boutonDetails.addEventListener("click", (e) => {
    e.stopPropagation();
    blocDetails.open = !blocDetails.open;
    boutonDetails.textContent = blocDetails.open ? "Masquer les détails" : "Détails de l'analyse";
    boutonDetails.setAttribute("aria-expanded", String(blocDetails.open));
  });

  const applique = (replie) => {
    section.classList.toggle("ax-replie", replie);
    deplier.setAttribute("aria-expanded", String(!replie)); plier.setAttribute("aria-expanded", String(!replie));
    deplier.innerHTML = `Déplier <span aria-hidden="true">⌄</span>`;
    plier.innerHTML = `Plier <span aria-hidden="true">⌃</span>`;
  };
  const bascule = () => applique(!section.classList.contains("ax-replie"));
  deplier.addEventListener("click", (e) => { e.stopPropagation(); bascule(); });
  plier.addEventListener("click", bascule);
  // Carte repliée : toucher n'importe où sur la carte la déplie (grande zone tactile).
  section.addEventListener("click", (e) => {
    if (section.classList.contains("ax-replie") && !e.target.closest("button, a, summary")) bascule();
  });
  applique(!!opt.replie);
  section.querySelector(".ax-actions-tete").appendChild(deplier);
  pied.appendChild(boutonDetails);
  pied.appendChild(plier);
  section.appendChild(pied);

  // Action facultative (ex. « Retirer » dans le panier) : toujours dans l'en-tête, carte dépliée comme
  // repliée. Le pied de carte est réservé à « Détails de l'analyse » et « Plier » (il ne peut pas en
  // accueillir un troisième sur 375px). La ligne d'en-tête a la même hauteur avec ou sans action
  // (.ax-match-bas{min-height}) : le panier reste strictement identique à la page principale.
  if (opt.action && typeof opt.action.onClick === "function") {
    const bouton = document.createElement("button");
    bouton.type = "button"; bouton.className = "ax-retirer";
    bouton.textContent = opt.action.libelle || "Retirer";
    if (opt.action.aria) bouton.setAttribute("aria-label", opt.action.aria);
    bouton.addEventListener("click", (e) => { e.stopPropagation(); opt.action.onClick(); });
    section.querySelector(".ax-actions-tete").prepend(bouton);
  }
  return section;
}

/* ───────────────── regroupement et affichage ───────────────── */

function identiteMatch(m) {
  if (m && m.match_id !== undefined && m.match_id !== null && String(m.match_id).trim() !== "") return `id:${String(m.match_id)}`;
  return `match:${String(m?.date || "").trim()}|${String(m?.heure_cameroun || m?.heure || "").trim()}|${String(m?.domicile || "").trim().toLowerCase()}|${String(m?.exterieur || "").trim().toLowerCase()}`;
}
function regroupeMatchs(matchs) {
  const groupes = new Map();
  (matchs || []).forEach((m) => {
    const cle = identiteMatch(m);
    if (!groupes.has(cle)) { groupes.set(cle, m); return; }
    const actuel = groupes.get(cle);
    if (m.archetype_model && actuel.archetype_model) {
      actuel.archetype_model.selection = { ...(actuel.archetype_model.selection || {}), ...(m.archetype_model.selection || {}) };
    }
  });
  return Array.from(groupes.values());
}

function afficheSelections(matchs) {
  const racine = document.getElementById("matches"), maj = document.getElementById("maj");
  racine.innerHTML = "";
  const cleTri = (m) => `${m.date || ""}${m.heure_cameroun || m.heure || ""}`;
  const retenus = regroupeMatchs(matchs).filter(aAuMoinsUnCandidat).sort((a, b) => cleTri(a).localeCompare(cleTri(b)));
  maj.textContent = retenus.length
    ? `${retenus.length} match${retenus.length > 1 ? "s" : ""} analysé${retenus.length > 1 ? "s" : ""} aujourd'hui`
    : "Aucune sélection pour le moment";
  if (!retenus.length) {
    racine.innerHTML = `<div class="ax-etat-vide"><strong>Aucune sélection pour le moment</strong>` +
      `<p>Aucun match ne remplit actuellement tous les critères du modèle. Le système préfère ne rien proposer plutôt que de forcer une sélection.</p></div>`;
    return;
  }
  // Un seul match est ouvert à l'arrivée ; les autres se déplient à la demande.
  retenus.forEach((m, index) => racine.appendChild(construitCarte(m, { replie: index > 0 })));
}

/* ───────────────── page Archetype : thème + chargement ───────────────── */

function installeThemeNuit() {
  const bouton = document.getElementById("ax-bouton-theme");
  if (!bouton) return;
  const applique = (nuit) => {
    document.body.classList.toggle("theme-nuit", nuit);
    bouton.textContent = nuit ? "☀" : "☾";
    bouton.setAttribute("aria-label", nuit ? "Activer le mode clair" : "Activer le mode nuit");
  };
  let nuit = false;
  try { nuit = localStorage.getItem(CLE_THEME_NUIT) === "1"; } catch (e) { /* stockage indisponible */ }
  applique(nuit);
  bouton.addEventListener("click", () => {
    const suivant = !document.body.classList.contains("theme-nuit");
    try { localStorage.setItem(CLE_THEME_NUIT, suivant ? "1" : "0"); } catch (e) { /* ignoré */ }
    applique(suivant);
  });
}

installeThemeNuit();
if (document.getElementById("matches")) {
  fetch(`precalcul_leger.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`precalcul_leger.json introuvable (${r.status})`); return r.json(); })
    .then((d) => afficheSelections(d.signaux || []))
    .catch((e) => { document.getElementById("maj").textContent = "Erreur de chargement : " + e.message; console.error(e); });
}