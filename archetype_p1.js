// Page P1 – Analyse statistique : affiche data/calibration_p1/page_p1.json (écrit par p1_page_donnees.py à partir du journal gelé). Lecture seule : AUCUN calcul de probabilité ici.
"use strict";
const P1_URL = "data/calibration_p1/page_p1.json";
const P1_MARCHES = [["o15", "Plus de 1,5 but"], ["o25", "Plus de 2,5 buts"], ["o35", "Plus de 3,5 buts"], ["btts", "Les deux marquent"]];
const P1_NOMS = { dom: "Domicile", nul: "Nul", ext: "Extérieur" };
let P1 = null, P1_ONGLET = "avenir", P1_DATE = "", P1_COMP = "";

const e = (x) => String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (x) => (x != null && Number.isFinite(Number(x)) ? Number(x) : null);
const pct0 = (x) => (num(x) == null ? "—" : Math.round(Number(x) * 100) + " %");
const pct1 = (x) => (num(x) == null ? "—" : (Number(x) * 100).toFixed(1).replace(".", ",") + " %");
const fr = (x, d) => (num(x) == null ? "—" : Number(x).toFixed(d == null ? 2 : d).replace(".", ","));
function jourFr(iso) {
  const d = new Date(`${iso}T12:00:00`); if (Number.isNaN(d.getTime())) return iso || "";
  const t = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim(); return t.charAt(0).toUpperCase() + t.slice(1);
}
function horaire(ko) {           // UTC -> heure du Cameroun (UTC+1)
  const d = ko ? new Date(ko) : null; if (!d || Number.isNaN(d.getTime())) return { heure: "—", date: "" };
  const c = new Date(d.getTime() + 3600000); return { heure: c.toISOString().slice(11, 16).replace(":", "h"), date: jourFr(c.toISOString().slice(0, 10)), iso: c.toISOString().slice(0, 10) };
}
const nomComp = (m) => String(m.competition || "").replace(/\s+/g, " ").trim();
const memeValeurs = (m) => ["dom", "nul", "ext", "o15", "o25", "o35", "btts"].every((k) => m.p1_original[k] === m.p1_calibre[k]);
const complet = (m) => m.p1_original && ["dom", "nul", "ext"].every((k) => num(m.p1_original[k]) != null);

function blocStatut(d) {
  const c = d.calibration || {}, ok = (c.couples_valides || 0) > 0;
  return `<div class="p1-statut ${ok ? "p1-valide" : "p1-neutre"}"><b>Calibration : ${ok ? c.couples_valides + " correction(s) validée(s)" : "aucune correction validée"}</b> (${e(c.couples_valides)} sur ${e(c.couples_total)} couples compétition × marché, ${e(c.competitions)} compétitions). ` +
    `${ok ? e(c.texte) : "P1 calibré est donc identique à P1 original : aucune correction n'est appliquée."} Mode : <b>${e(d.mode)}</b>${d.mode === "parallele" ? " (enregistrement en parallèle, rien n'est modifié)" : ""}.</div>`;
}
function blocCalibration(m) {
  if (memeValeurs(m)) return `<div class="p1-cal">P1 calibré = P1 original (aucune correction validée pour cette compétition).</div>`;
  const ligne = (k) => `<tr><th>${e(P1_NOMS[k] || k)}</th><td>${pct1(m.p1_original[k])}</td><td>${pct1(m.p1_calibre[k])}</td><td>${e((m.methode || {})[k] || "—")}</td></tr>`;
  return `<div class="p1-cal p1-diff"><b>P1 original et P1 calibré diffèrent.</b><table><tr><th></th><th>Original</th><th>Calibré</th><th>Méthode</th></tr>${["dom", "nul", "ext", "o15", "o25", "o35", "btts"].map(ligne).join("")}</table></div>`;
}
function blocDetail(m) {
  const d = m.detail || {};
  const l = (a, b) => `<dt>${a}</dt><dd>${b}</dd>`;
  return `<details class="p1-det"><summary>Détail statistique</summary><dl>` +
    l("Buts attendus (dom.)", fr(d.buts_attendus_dom)) + l("Buts attendus (ext.)", fr(d.buts_attendus_ext)) +
    l("Matchs antérieurs de l'équipe dom.", e(d.matchs_anterieurs_dom ?? "—")) + l("Matchs antérieurs de l'équipe ext.", e(d.matchs_anterieurs_ext ?? "—")) +
    l("Historique de la compétition", e(m.n_historique_competition ?? "—")) +
    l("Lissage k", e(d.k ?? "—")) + l("Demi-vie", d.demi_vie_jours == null ? "aucune" : e(d.demi_vie_jours) + " jours") +
    l("Noms Football-Data", `${e(d.fd_dom || "—")} / ${e(d.fd_ext || "—")}`) +
    l("Gelé le (UTC)", e(m.gele_le || "—")) + l("Empreinte", `<span class="p1-mono">${e(String(m.empreinte || "").slice(0, 16) || "—")}…</span>`) +
    `</dl></details>`;
}
function carte(m) {
  const h = horaire(m.coup_d_envoi_utc), fin = m.statut === "termine" && m.resultat, ev = fin ? m.evaluation : null;
  if (!complet(m)) return `<article class="p1-carte"><div class="p1-tete"><p class="p1-comp-nom">${e(nomComp(m))}</p><div class="p1-equipes"><span class="p1-eq">${e(m.domicile)}</span><span class="p1-heure">${e(h.heure)}</span><span class="p1-eq p1-ext">${e(m.exterieur)}</span></div></div><p class="p1-vide">Prédiction P1 indisponible pour ce match.</p></article>`;
  const p = m.p1_original, fav = ["dom", "nul", "ext"].reduce((a, k) => (p[k] > p[a] ? k : a), "dom");
  const milieu = fin ? `<span class="p1-score">${e(m.resultat.buts_dom)} – ${e(m.resultat.buts_ext)}</span>` : `<span class="p1-heure"><strong>${e(h.heure)}</strong>${e(h.date)}</span>`;
  const trio = ["dom", "nul", "ext"].map((k) => `<div class="${k === fav ? "p1-fav" : ""} ${ev && ev.original.issue_1x2 === k ? "p1-reel" : ""}"><small>${k === "dom" ? "1 · " + e(m.domicile) : k === "nul" ? "N · Nul" : "2 · " + e(m.exterieur)}</small><b>${pct0(p[k])}</b></div>`).join("");
  const marches = P1_MARCHES.map(([k, nom]) => {
    const r = ev ? (ev.realise[k] ? '<span class="p1-ok"> ✓</span>' : '<span class="p1-ko"> ✗</span>') : "";
    return `<div><span>${nom}</span><b>${pct0(p[k])}${r}</b></div>`;
  }).join("");
  const etat = m.statut === "en_cours_ou_resultat_attendu" ? `<p class="p1-note">Coup d'envoi passé : résultat pas encore enregistré.</p>` : "";
  return `<article class="p1-carte"><div class="p1-tete"><p class="p1-comp-nom">${e(nomComp(m))}${fin ? " · " + e(h.date) : ""}</p><div class="p1-equipes"><span class="p1-eq">${e(m.domicile)}</span>${milieu}<span class="p1-eq p1-ext">${e(m.exterieur)}</span></div></div>` +
    `<div class="p1-corps"><div class="p1-1n2" role="group" aria-label="Probabilités 1 N 2">${trio}</div><div class="p1-marches">${marches}</div>${etat}${blocCalibration(m)}${blocDetail(m)}</div></article>`;
}
function filtres(liste) {
  const dates = [...new Set(liste.map((m) => horaire(m.coup_d_envoi_utc).iso).filter(Boolean))].sort();
  const comps = [...new Set(liste.map(nomComp).filter(Boolean))].sort((a, b) => a.localeCompare(b, "fr"));
  if (P1_DATE && !dates.includes(P1_DATE)) P1_DATE = ""; if (P1_COMP && !comps.includes(P1_COMP)) P1_COMP = "";
  document.getElementById("p1-dates").innerHTML = [`<button type="button" class="p1-puce" data-date="" aria-pressed="${P1_DATE === ""}">Toutes les dates</button>`].concat(dates.map((d) => `<button type="button" class="p1-puce" data-date="${e(d)}" aria-pressed="${P1_DATE === d}">${e(jourFr(d))}</button>`)).join("");
  const sel = document.getElementById("p1-competition"); sel.innerHTML = `<option value="">Toutes</option>` + comps.map((c) => `<option value="${e(c)}"${c === P1_COMP ? " selected" : ""}>${e(c)}</option>`).join("");
}
function tableauPerf(pv) {
  const lignes = P1_MARCHES.map(([k, nom]) => { const a = pv.original.marches[k], b = pv.calibre.marches[k];
    return `<tr><th>${nom}</th><td>${pct1(a.frequence_reelle)}</td><td>${pct1(a.probabilite_moyenne)}</td><td>${fr(a.brier, 3)}</td><td>${fr(b.brier, 3)}</td></tr>`; }).join("");
  return `<div class="p1-tabwrap"><table class="p1-tab"><tr><th>Marché</th><th>Fréquence réelle</th><th>Proba. moyenne P1</th><th>Brier original</th><th>Brier calibré</th></tr>${lignes}</table></div>`;
}
function vuePerf(d) {
  const p = d.performance || {};
  if (!p.matchs_termines) return `<p class="p1-vide pleine">${e(p.note || "Aucune performance mesurable.")} Les prédictions du journal sont gelées depuis le ${e((d.matchs[0] || {}).gele_le || "—")}.</p>`;
  const o = p.par_version.original, c = p.par_version.calibre;
  return `<div class="p1-pleine"><p class="p1-note"><b>${p.matchs_termines} match(s) terminé(s)</b>, du ${e(jourFr(p.periode[0]))} au ${e(jourFr(p.periode[1]))}. Mesures sur prédictions réellement gelées avant le coup d'envoi ; l'échantillon est celui-ci et rien d'autre : l'erreur-type indique l'incertitude.</p>` +
    `<div class="p1-tabwrap"><table class="p1-tab"><tr><th></th><th>Original</th><th>Calibré</th></tr>` +
    `<tr><th>Perte logarithmique 1/N/2</th><td>${fr(o.logloss_1x2, 3)}</td><td>${fr(c.logloss_1x2, 3)}</td></tr>` +
    `<tr><th>Brier 1/N/2</th><td>${fr(o.brier_1x2, 3)}</td><td>${fr(c.brier_1x2, 3)}</td></tr>` +
    `<tr><th>Favori correct</th><td>${e(o.favori_correct)}/${p.matchs_termines} (${pct1(o.favori_taux)} ± ${pct1(o.favori_erreur_type)})</td><td>${e(c.favori_correct)}/${p.matchs_termines} (${pct1(c.favori_taux)} ± ${pct1(c.favori_erreur_type)})</td></tr></table></div>${tableauPerf(p.par_version)}</div>`;
}
function vueHisto(d) {
  const j = d.journal || {}, rows = d.matchs.slice().sort((a, b) => (a.gele_le < b.gele_le ? 1 : -1)).map((m) => `<tr><td>${e(m.gele_le)}</td><td>${e(m.coup_d_envoi_utc)}</td><td>${e(m.domicile)} – ${e(m.exterieur)}</td><td class="p1-mono">${e(String(m.empreinte || "").slice(0, 12))}</td></tr>`).join("");
  return `<div class="p1-pleine"><p class="p1-note">Journal immuable : ${e(j.lignes)} prédiction(s), chaque ligne chaînée à la précédente par empreinte SHA-256 et enregistrée avant le coup d'envoi. ${(j.anomalies || []).length ? `<b class="p1-ko">${j.anomalies.length} anomalie(s) détectée(s).</b>` : "Contrôle d'intégrité : aucune anomalie."} Dernière empreinte : <span class="p1-mono">${e(String(j.derniere_empreinte || "—").slice(0, 16))}…</span></p>` +
    `<div class="p1-tabwrap"><table class="p1-tab"><tr><th>Gelé le (UTC)</th><th>Coup d'envoi (UTC)</th><th>Match</th><th>Empreinte</th></tr>${rows}</table></div></div>`;
}
function rendre() {
  if (!P1) return;
  const d = P1, liste = d.matchs || [];
  const base = P1_ONGLET === "termines" ? liste.filter((m) => m.statut === "termine") : P1_ONGLET === "avenir" ? liste.filter((m) => m.statut !== "termine") : [];
  const avecFiltres = P1_ONGLET === "avenir" || P1_ONGLET === "termines";
  document.getElementById("p1-filtres").hidden = !avecFiltres; const zone = document.getElementById("p1-contenu");
  if (!avecFiltres) { zone.innerHTML = P1_ONGLET === "perf" ? vuePerf(d) : vueHisto(d); return; }
  filtres(base);
  const sel = base.filter((m) => (!P1_DATE || horaire(m.coup_d_envoi_utc).iso === P1_DATE) && (!P1_COMP || nomComp(m) === P1_COMP));
  if (P1_ONGLET === "termines") sel.reverse();
  zone.innerHTML = sel.length ? sel.map(carte).join("") : `<p class="p1-vide p1-pleine">${base.length ? "Aucun match pour ces filtres." : P1_ONGLET === "termines" ? "Aucun match terminé avec prédiction gelée pour l'instant." : "Aucun match à venir dans le journal P1."}</p>`;
}
async function charger() {
  const maj = document.getElementById("maj");
  try {
    const r = await fetch(`${P1_URL}?t=${Date.now()}`, { cache: "no-store" }); if (!r.ok) throw new Error(r.status);
    P1 = await r.json(); const n = (P1.matchs || []).length;
    maj.textContent = `Données du ${P1.genere_le ? new Date(P1.genere_le).toLocaleString("fr-FR", { timeZone: "Africa/Douala", dateStyle: "medium", timeStyle: "short" }) : "—"} (heure du Cameroun) · ${n} match(s) dans le journal`;
    document.getElementById("p1-statut").innerHTML = blocStatut(P1); rendre();
  } catch (err) { maj.textContent = "Données P1 indisponibles."; document.getElementById("p1-contenu").innerHTML = `<p class="p1-vide">Impossible de charger les données P1. Aucune valeur n'est affichée.</p>`; }
}
document.addEventListener("click", (ev) => {
  const o = ev.target.closest("[data-onglet]"); if (o) { P1_ONGLET = o.dataset.onglet; document.querySelectorAll("[data-onglet]").forEach((b) => b.setAttribute("aria-selected", String(b === o))); rendre(); return; }
  const dt = ev.target.closest("[data-date]"); if (dt) { P1_DATE = dt.dataset.date; rendre(); }
});
document.getElementById("p1-competition").addEventListener("change", (ev) => { P1_COMP = ev.target.value; rendre(); });
(function theme() { const b = document.getElementById("ax-bouton-theme"); if (!b) return; b.addEventListener("click", () => { const n = document.body.classList.toggle("theme-nuit"); try { localStorage.setItem("archetype_theme_nuit", n ? "1" : "0"); } catch (x) {} }); })();
charger();
