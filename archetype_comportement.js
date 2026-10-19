// archetype_comportement.js — page du moteur alpha (refonte du 19/10/2026, demande de Patrick : « même thème et présentation que V3 »).
// Présentation uniquement : le navigateur ne calcule rien, tout vient de data/comportement/pronostics_comportement.json
// (écrit par python -m matrice_scenarios.suivi_comportement pipeline).
// Même carte que la page V3 (mêmes classes ax-*) : carte REPLIÉE au départ, un toucher la déplie ; au premier plan le MARCHÉ et sa COTE ;
// la tendance tient en une phrase pour le parieur ; les chiffres complets sont dans « Détails de l'analyse ».
// Aucun lien avec V2, V3, V2R, Europe ni le générateur de tickets.
const CLE_THEME_NUIT = "archetype_theme_nuit"; // même clé que theme.js

const echappeHtml = (x) => (x === null || x === undefined ? "" : String(x)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"));
const formatCote = (x) => { const n = Number(x); return Number.isFinite(n) ? n.toFixed(2).replace(".", ",") : "—"; };
const formatPct = (x) => `${(Number(x) * 100).toFixed(1).replace(".", ",")} %`;
function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  const t = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
// Jour courant à Douala (les dates des matchs sont à l'heure du Cameroun) : on n'affiche que les matchs d'aujourd'hui et à venir.
const aujourdhui = () => new Date().toLocaleDateString("en-CA", { timeZone: "Africa/Douala" });

const ICONES = {
  forme: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V11h4v9H4zm6 0V4h4v16h-4zm6 0v-6h4v6h-4z"/></svg>',
  balle: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 3.2 3.1 2.2-1.2 3.7h-3.8L8.9 7.4 12 5.2zM6 10l2.6 1.9-1 3.1-3-.4A8 8 0 0 1 6 10zm12 0a8 8 0 0 1 2.4 4.6l-3 .4-1-3.1L18 10zm-8.1 6.4h4.2l1 2.9a8 8 0 0 1-6.2 0l1-2.9z"/></svg>',
  but: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 21v-6h4v6H3zm7 0v-10h4v10h-4zm7 0V7h4v14h-4zM4 9l6-5 4 3 6-5v3l-6 5-4-3-6 4V9z"/></svg>',
};
const ICONE_TENDANCE = { resultat: ICONES.forme, dom_buts: ICONES.balle, ext_buts: ICONES.balle, buts: ICONES.but, deux_marquent: ICONES.but };
const CLASSES = ["rang-1", "rang-2", "rang-3", "rang-3", "rang-3"];
let compteurCartes = 0;

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

// Nom court de l'onglet : « Principal », puis la tendance du pari.
function etiquette(s) {
  if (s.role === "principal") return "Principal";
  const t = String(s.tendance || "");
  if (t === "Résultat") return "Résultat";
  if (t === "Buts du match") return "Total buts";
  if (t === "Les deux marquent") return "2 marquent";
  return t.startsWith("Buts de ") ? "Buts équipe" : t;
}
// La phrase « parieur » de la tendance qui a produit ce pari (absente pour les anciennes données : repli sur le texte chiffré).
function tendanceDe(m, s) {
  const t = (m.tendances || []).find((x) => x.titre === s.tendance || x.cle === s.tendance);
  return t ? (t.court || t.texte || "") : "";
}
function issue(s) {
  if (s.gagne === undefined || s.gagne === null) return "";
  return s.gagne ? "✔ Gagné" : "✘ Perdu";
}

function construitResume(m) {
  const div = document.createElement("div");
  div.className = "ax-resume";
  div.innerHTML = m.selections.map((s, i) => {
    const texte = tendanceDe(m, s), fin = issue(s);
    return `<div class="ax-resume-rang ax-${CLASSES[i]}" data-cle="${i}">` +
      `<div class="ax-resume-corps">` +
      `<div class="ax-resume-tete"><span class="ax-resume-etiquette">${echappeHtml(etiquette(s))}</span>` +
      `<span class="ax-resume-cote">Cote <strong>${formatCote(s.cote)}</strong></span></div>` +
      `<h3 class="ax-resume-marche">${echappeHtml(s.libelle)}</h3>` +
      (texte ? `<p class="ax-resume-texte">${echappeHtml(texte)}</p>` : "") +
      (fin ? `<p class="ax-resume-texte"><strong>${fin}</strong></p>` : "") + `</div>` +
      `${construitJauge(s.probabilite, "ax-jauge-mini")}</div>`;
  }).join("");
  return div;
}

// Carte dépliée : le marché et la cote d'abord, puis les tendances du match (une ligne chacune).
function construitPanneau(m, s, i, idPanneau, idOnglet) {
  const lignes = (m.tendances || []).filter((t) => t.court).map((t) =>
    `<div class="ax-preuve"><span class="ax-icone">${ICONE_TENDANCE[t.cle] || ICONES.forme}</span><div>` +
    `<span class="ax-preuve-titre">${echappeHtml(t.titre)}</span><span class="ax-preuve-texte">${echappeHtml(t.court)}</span></div></div>`).join("");
  const el = document.createElement("div");
  el.className = `ax-panneau ax-${CLASSES[i]}`;
  el.id = idPanneau; el.setAttribute("role", "tabpanel"); el.setAttribute("aria-labelledby", idOnglet); el.dataset.cle = String(i);
  el.innerHTML =
    `<h2 class="ax-marche">${echappeHtml(s.libelle)}</h2>` +
    `<div class="ax-ligne-cote"><p class="ax-texte-resume">${echappeHtml(tendanceDe(m, s))}</p>` +
    `<div class="ax-badge-cote"><span>Cote</span><strong>${formatCote(s.cote)}</strong></div></div>` +
    `<div class="ax-preuves"><div class="ax-preuves-liste">${lignes}</div>` +
    `<div class="ax-proba">${construitJauge(s.probabilite, "")}<span class="ax-proba-legende">Probabilité du modèle</span>` +
    (issue(s) ? `<span class="ax-solidite"><span class="ax-solidite-titre">Résultat :</span> ${issue(s)}</span>` : "") + `</div></div>`;
  return el;
}

// « Détails de l'analyse » : les chiffres complets pour qui veut vérifier.
function construitDetails(m, idDetails) {
  const details = document.createElement("details");
  details.className = "details-analyse ax-details";
  details.id = idDetails;
  const lignes = (m.tendances || []).map((t) => `<li><strong>${echappeHtml(t.titre)}</strong> — ${echappeHtml(t.texte)}</li>`).join("");
  const sr = m.series ? `<p class="ax-preuve-texte">Séries analysées : ${Number(m.series.domicile)} derniers matchs du domicile, ${Number(m.series.exterieur)} de l'extérieur.</p>` : "";
  details.innerHTML = `<summary class="ax-summary-cache" tabindex="-1">Détails de l'analyse</summary><div class="ax-details-corps">` +
    `<div class="ax-tab"><h4 class="ax-tab-titre">Tendances du match (chiffres)</h4><ul class="ax-v3-lignes">${lignes}</ul>${sr}</div></div>`;
  return details;
}

function construitCarte(m) {
  const id = ++compteurCartes, idDetails = `ax-details-${id}`;
  const section = document.createElement("section");
  section.className = "ax-carte";
  const score = m.score && m.score.buts_dom !== undefined && m.score.buts_dom !== null ? ` · Score final ${Number(m.score.buts_dom)}-${Number(m.score.buts_ext)}` : "";
  section.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match">` +
      `<span class="ax-equipe ax-dom">${echappeHtml(m.domicile)}</span>` +
      `<div class="ax-horaire"><strong>${echappeHtml(m.heure || "—")}</strong><span>${echappeHtml(formatDate(m.date))}</span></div>` +
      `<span class="ax-equipe ax-ext">${echappeHtml(m.exterieur)}</span></div>` +
      `<div class="ax-match-bas"><p class="ax-competition">${echappeHtml(String(m.competition || "").replace(/\s+/g, " ").trim() + score)}</p><div class="ax-actions-tete"></div></div>` +
    `</div>`;

  const onglets = document.createElement("div");
  onglets.className = "ax-onglets"; onglets.setAttribute("role", "tablist"); onglets.setAttribute("aria-label", "Choix du pronostic");
  const panneaux = document.createElement("div");
  panneaux.className = "ax-panneaux";
  const actifs = m.selections.map((s, i) => {
    const idO = `ax-onglet-${id}-${i}`, idP = `ax-panneau-${id}-${i}`;
    const bouton = document.createElement("button");
    bouton.type = "button"; bouton.id = idO; bouton.className = `ax-onglet ax-${CLASSES[i]}`;
    bouton.setAttribute("role", "tab"); bouton.setAttribute("aria-controls", idP); bouton.dataset.cle = String(i);
    bouton.innerHTML = `<span>${echappeHtml(etiquette(s))}</span>`;
    onglets.appendChild(bouton);
    return { bouton, panneau: construitPanneau(m, s, i, idP, idO) };
  });
  const resume = construitResume(m), blocDetails = construitDetails(m, idDetails);
  const active = (cible) => {
    actifs.forEach(({ bouton, panneau }) => {
      const oui = bouton === cible;
      bouton.classList.toggle("ax-actif", oui); bouton.setAttribute("aria-selected", String(oui)); bouton.tabIndex = oui ? 0 : -1; panneau.hidden = !oui;
    });
    resume.querySelectorAll(".ax-resume-rang").forEach((l) => { l.hidden = l.dataset.cle !== cible.dataset.cle; });
  };
  actifs.forEach(({ bouton, panneau }) => { bouton.addEventListener("click", () => active(bouton)); panneaux.appendChild(panneau); });
  onglets.style.gridTemplateColumns = `repeat(${Math.min(3, Math.max(1, actifs.length))},minmax(0,1fr))`;
  if (actifs.length > 3) onglets.classList.add("ax-onglets-defilent");
  active(actifs[0].bouton);
  section.appendChild(onglets); section.appendChild(panneaux); section.appendChild(resume); section.appendChild(blocDetails);

  const pied = document.createElement("div");
  pied.className = "ax-pied";
  const boutonDetails = document.createElement("button");
  boutonDetails.type = "button"; boutonDetails.className = "ax-bouton-details";
  boutonDetails.textContent = "Détails de l'analyse";
  boutonDetails.setAttribute("aria-controls", idDetails); boutonDetails.setAttribute("aria-expanded", "false");
  boutonDetails.addEventListener("click", (e) => {
    e.stopPropagation();
    blocDetails.open = !blocDetails.open;
    boutonDetails.textContent = blocDetails.open ? "Masquer les détails" : "Détails de l'analyse";
    boutonDetails.setAttribute("aria-expanded", String(blocDetails.open));
  });
  const applique = (replie) => { section.classList.toggle("ax-replie", replie); section.setAttribute("aria-expanded", String(!replie)); };
  // Toucher n'importe où sur la carte la plie / la déplie ; la carte garde sa position à l'écran.
  section.addEventListener("click", (e) => {
    if (e.target.closest("button, a, summary, [role=tab]")) return;
    const sel = window.getSelection && window.getSelection();
    if (sel && String(sel).length) return;
    const avant = section.getBoundingClientRect().top;
    applique(!section.classList.contains("ax-replie"));
    const apres = section.getBoundingClientRect().top;
    if (Math.abs(apres - avant) > 1) window.scrollBy(0, apres - avant);
  });
  applique(true);                                   // repliée au départ, comme V3
  pied.appendChild(boutonDetails); section.appendChild(pied);
  return section;
}

function afficheSelections(d) {
  const racine = document.getElementById("matches"), maj = document.getElementById("maj"), perf = document.getElementById("perf");
  const jour = aujourdhui();
  const cleTri = (m) => `${m.date || ""}${m.heure || ""}`;
  const retenus = (d.matchs || []).filter((m) => m.statut === "OK" && m.date >= jour && (m.selections || []).length).sort((a, b) => cleTri(a).localeCompare(cleTri(b)));
  maj.textContent = retenus.length ? `${retenus.length} match${retenus.length > 1 ? "s" : ""} avec au moins un pronostic · cote minimale ${formatCote(d.cote_min)}` : "Aucun pronostic pour le moment";
  const p = d.performance_archive;
  if (p && perf) {
    perf.textContent = `Réussite réelle : ${formatPct(p.reussite)} sur ${p.matchs} matchs (${Math.round(p.ic95[0] * 100)}–${Math.round(p.ic95[1] * 100)} %). Les % affichés sont surestimés d'environ 10 points.`;
  }
  racine.innerHTML = "";
  if (!retenus.length) {
    racine.innerHTML = `<div class="ax-etat-vide"><strong>Aucun pronostic pour le moment</strong>` +
      `<p>Aucun match à venir ne remplit les critères du moteur (marché le plus probable avec une cote d'au moins ${formatCote(d.cote_min)}).</p></div>`;
    return;
  }
  retenus.forEach((m) => racine.appendChild(construitCarte(m)));
}

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
  fetch(`data/comportement/pronostics_comportement.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`données introuvables (${r.status})`); return r.json(); })
    .then(afficheSelections)
    .catch((e) => { document.getElementById("maj").textContent = "Données du moteur alpha indisponibles : " + e.message; console.error(e); });
}
