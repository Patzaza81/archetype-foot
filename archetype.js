// archetype.js — présentation uniquement (réécriture complète du 20/09/2026).
// Le navigateur ne choisit aucun pronostic et ne calcule aucune statistique :
// tout ce qui est affiché vient de precalcul_leger.json (archetype_model.selection).
//
// Contrat conservé pour panier.js : construitCarte(), regroupeMatchs(),
// estArchetypeGo(), echappeHtml() gardent leur nom, et chaque carte contient
// un <details class="details-analyse"> (panier.js l'ouvre via "Voir l'analyse").

const RANGS = [
  { cle: "P1", classe: "rang-1", titre: "Pronostic principal" },
  { cle: "P2", classe: "rang-2", titre: "Deuxième choix" },
  { cle: "P3", classe: "rang-3", titre: "Troisième choix" },
];

// "Forme récente" n'accepte que des preuves qui décrivent réellement la forme
// (règle du 18/09/2026) : jamais une statistique de buts croisée.
const TYPES_FORME_RECENTE = new Set(["home_unbeaten_streak", "away_concede_pct"]);

const CLE_THEME_NUIT = "archetype_theme_nuit"; // même clé que theme.js
let compteurCartes = 0;

/* ───────────────────────── outils ───────────────────────── */

function estArchetypeGo(m) {
  return !!(m && m.moteur_utilise === "archetype_model" && m.archetype_model &&
    m.archetype_model.statut === "OK" && m.archetype_model.selection && m.archetype_model.selection.P1);
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
  div.innerHTML = RANGS.map((info) => {
    const c = selection[info.cle];
    if (!c) {
      return `<div class="ax-resume-rang ax-${info.classe} ax-vide">` +
        `<span class="ax-resume-etiquette">${echappeHtml(info.titre)}</span>` +
        `<span class="ax-resume-indispo">Non disponible pour ce match</span></div>`;
    }
    return `<div class="ax-resume-rang ax-${info.classe}">` +
      `<div class="ax-resume-corps">` +
      `<div class="ax-resume-tete"><span class="ax-resume-etiquette">${echappeHtml(info.titre)}</span>` +
      `<span class="ax-resume-cote">Cote <strong>${formatCote(c.cote)}</strong></span></div>` +
      `<h3 class="ax-resume-marche">${echappeHtml(traduitMarche(c.marche, equipes))}</h3></div>` +
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

// Détails techniques (un seul <details> par carte : panier.js l'ouvre via .details-analyse).
function construitDetails(selection, equipes) {
  const details = document.createElement("details");
  details.className = "details-analyse ax-details";
  const blocs = RANGS.filter((r) => selection[r.cle]).map((r) => {
    const c = selection[r.cle];
    const preuves = (c.justification && Array.isArray(c.justification.preuves)) ? c.justification.preuves.filter((p) => p && p.texte) : [];
    return `<div class="ax-detail-rang ax-${r.classe}">` +
      `<h3>${echappeHtml(r.titre)} — ${echappeHtml(traduitMarche(c.marche, equipes))}</h3>` +
      (preuves.length ? `<ul>${preuves.map((p) => `<li>${echappeHtml(p.texte)}</li>`).join("")}</ul>` : "") +
      `<dl><div><dt>Solidité du pari</dt><dd>${echappeHtml(traduitNiveau(c.niveau).texte)}</dd></div>` +
      `<div><dt>Stabilité du calcul</dt><dd>${echappeHtml(traduitRobustesse(c.robustesse))}</dd></div></dl></div>`;
  }).join("");
  details.innerHTML = `<summary><span>Détails de l'analyse</span><span class="ax-chevron" aria-hidden="true"></span></summary><div class="ax-details-corps">${blocs}</div>`;
  return details;
}

function construitCarte(m, options) {
  const opt = options || {};
  const id = ++compteurCartes;
  const equipes = { domicile: m.domicile || "Équipe à domicile", exterieur: m.exterieur || "Équipe à l'extérieur" };
  const heure = m.heure_cameroun || m.heure || "—";
  const date = formatDate(m.date);
  const competition = String(m.competition || "").replace(/\s+/g, " ").trim();
  const selection = (m.archetype_model && m.archetype_model.selection) || {};

  const section = document.createElement("section");
  section.className = "ax-carte";
  section.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match">` +
      `<span class="ax-equipe ax-dom">${echappeHtml(equipes.domicile)}</span>` +
      `<div class="ax-horaire"><strong>${echappeHtml(heure)}</strong><span>${echappeHtml(date)}</span></div>` +
      `<span class="ax-equipe ax-ext">${echappeHtml(equipes.exterieur)}</span></div>` +
      `<div class="ax-match-bas"><p class="ax-competition">${echappeHtml(competition)}</p><div class="ax-actions-tete"></div></div>` +
    `</div>`;

  section.appendChild(construitResume(selection, equipes));

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
  const active = (cible) => actifs.forEach(({ bouton, panneau }) => {
    const oui = bouton === cible;
    bouton.classList.toggle("ax-actif", oui); bouton.setAttribute("aria-selected", String(oui)); bouton.tabIndex = oui ? 0 : -1;
    panneau.hidden = !oui;
  });
  actifs.forEach(({ bouton, panneau }) => { bouton.addEventListener("click", () => active(bouton)); panneaux.appendChild(panneau); });
  if (actifs.length) { active(actifs[0].bouton); section.appendChild(onglets); section.appendChild(panneaux); }

  section.appendChild(construitDetails(selection, equipes));

  // Deux boutons pour le même geste : "Déplier" dans l'en-tête (carte repliée, compacte)
  // et "Plier" en bas de carte (carte dépliée, comme sur la maquette). Un seul est visible à la fois.
  const deplier = document.createElement("button");
  deplier.type = "button"; deplier.className = "ax-deplier";
  const pied = document.createElement("div");
  pied.className = "ax-pied";
  const plier = document.createElement("button");
  plier.type = "button"; plier.className = "ax-plier";
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
  pied.appendChild(plier); section.appendChild(pied);

  // Action facultative (ex. « Retirer » dans le panier). Même principe que Déplier/Plier :
  // en-tête quand la carte est repliée, pied de carte quand elle est dépliée -> la hauteur de la
  // carte est strictement la même avec ou sans l'action (panier identique à la page principale).
  if (opt.action && typeof opt.action.onClick === "function") {
    const cree = (classe) => {
      const bouton = document.createElement("button");
      bouton.type = "button"; bouton.className = `ax-retirer ${classe}`;
      bouton.textContent = opt.action.libelle || "Retirer";
      if (opt.action.aria) bouton.setAttribute("aria-label", opt.action.aria);
      bouton.addEventListener("click", (e) => { e.stopPropagation(); opt.action.onClick(); });
      return bouton;
    };
    section.querySelector(".ax-actions-tete").prepend(cree("ax-retirer-tete"));
    pied.prepend(cree("ax-retirer-pied"));
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
  const retenus = regroupeMatchs(matchs).filter(estArchetypeGo).sort((a, b) => cleTri(a).localeCompare(cleTri(b)));
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
