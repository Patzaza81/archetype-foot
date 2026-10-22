// Page V2R : affiche data/v2r/pronostics_v2r.json (écrit par moteur_v2r.execution). Lecture seule, aucun calcul métier.
"use strict";
const CLE_THEME_NUIT_V2R = "archetype_theme_nuit";

function v2rEchappe(x) {
  return String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function v2rCote(x) { const n = Number(x); return Number.isFinite(n) ? n.toFixed(2).replace(".", ",") : "—"; }
function v2rPct(x, signe) {
  const n = Number(x); if (!Number.isFinite(n)) return "—";
  const t = Math.abs(n * 100).toFixed(1).replace(".", ",") + " %";
  return signe ? (n >= 0 ? "+" : "−") + t : t;
}
function v2rHeure(ko) {          // coup d'envoi UTC -> heure du Cameroun (UTC+1)
  if (!ko) return "";
  const d = new Date(ko); if (Number.isNaN(d.getTime())) return "";
  const c = new Date(d.getTime() + 3600000);
  const j = c.toISOString().slice(0, 10), h = c.toISOString().slice(11, 16);
  return `${v2rDate(j)} · ${h.replace(":", "h")}`;
}
function v2rDate(iso) {
  const d = new Date(`${iso}T12:00:00`); if (Number.isNaN(d.getTime())) return iso;
  const t = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
function v2rMarche(l) {
  const m = String(l.marche || ""), dom = l.domicile || "Domicile", ext = l.exterieur || "Extérieur";
  const virg = (t) => t.replace(/(\d)\.(\d)/g, "$1,$2");
  let r;
  if ((r = m.match(/^1X2 - (1|X|2)$/))) return r[1] === "1" ? `Victoire ${dom}` : r[1] === "X" ? "Match nul" : `Victoire ${ext}`;
  if ((r = m.match(/^Double chance - (1X|X2|12)$/))) return r[1] === "1X" ? `${dom} ou match nul` : r[1] === "X2" ? `Match nul ou ${ext}` : `${dom} ou ${ext} (pas de nul)`;
  if ((r = m.match(/^Cage inviolée - (Domicile|Extérieur)$/))) return `${r[1] === "Domicile" ? dom : ext} garde sa cage inviolée`;
  if (m === "BTTS - oui") return "Les deux équipes marquent";
  if (m === "BTTS - non") return "Une des deux équipes ne marque pas";
  if (m === "Total buts - pair") return "Total de buts pair";
  if (m === "Total buts - impair") return "Total de buts impair";
  if ((r = m.match(/^Handicap (.+) - (Domicile|Extérieur)$/))) {      // ligne affichée = ligne du domicile ; l'extérieur reçoit l'inverse
    const x = r[2] === "Domicile" ? Number(r[1]) : -Number(r[1]);
    return `${r[2] === "Domicile" ? dom : ext} · handicap ${x > 0 ? "+" : x < 0 ? "−" : ""}${virg(String(Math.abs(x)))}`;
  }
  if ((r = m.match(/^(Plus|Moins) de (.+) buts - (Domicile|Extérieur)$/))) return `${r[3] === "Domicile" ? dom : ext} : ${r[1].toLowerCase()} de ${virg(r[2])} buts`;
  if ((r = m.match(/^(Plus|Moins) de (.+) buts$/))) return `${r[1]} de ${virg(r[2])} buts`;
  return virg(m);
}
// --- Paris modérés (moteur_v2r/modere.py) : affichés SOUS le pari d'origine, qui reste inchangé.
let v2rModeres = null;        // {match_id: {1: ligne, 2: ligne}} ; null = variantes indisponibles (rien n'est affiché)
let v2rPlancher = 1.4;
function v2rIndexModeres(d) {
  const m = d && d.modere; if (!m || m.erreur) return null;
  const idx = {};
  [[1, m["1_cran"]], [2, m["2_crans"]]].forEach(([k, b]) => {
    if (!b) return;
    ["a_venir", "en_cours", "reglees"].forEach((liste) => (b[liste] || []).forEach((l) => { (idx[l.match_id] = idx[l.match_id] || {})[k] = l; }));
  });
  return idx;
}
function v2rUnites(x) {
  const n = Number(x); if (!Number.isFinite(n)) return "—";
  return `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(2).replace(".", ",")} u`;
}
function v2rBadge(l) {
  return l.resultat ? `<span class="v2r-badge v2r-${v2rEchappe(l.resultat)}">${l.resultat === "WIN" ? "GAGNÉ" : l.resultat === "LOSS" ? "PERDU" : "REMBOURSÉ"}</span>` : "";
}
function v2rLigneModere(k, l, mode) {
  const nom = k === 0 ? "1 et 2 crans" : k === 1 ? "1 cran" : "2 crans";
  if (!l) return mode === "avenir" ? `<div class="v2r-ligne v2r-modere-vide"><span><b>${nom}</b> · aucun pari (cote sous ${v2rCote(v2rPlancher)})</span></div>` : "";
  const meme = l.marche === l.marche_v2r;
  const gain = l.resultat ? ` <small>${v2rUnites(l.profit)}</small>` : "";
  const ind = Number.isFinite(Number(l.indice_pct)) && l.indice_pct !== null ? Number(l.indice_pct) : null;
  const super_ = l.super_favori ? ` <span class="v2r-super">SUPER FAVORI · ${v2rEchappe(String(Math.round(ind)))} %</span>`
    : ind !== null ? ` <small>indice ${v2rEchappe(String(Math.round(ind)))} %</small>` : "";
  return `<div class="v2r-ligne"><span><b>${nom}</b> · ${v2rEchappe(v2rMarche(l))}${meme ? " <small>(pas de version modérée)</small>" : ""}${super_}</span>` +
    `<span><span class="v2r-cote">Cote ${v2rCote(l.cote)}</span> ${v2rBadge(l)}${gain}</span></div>`;
}
function v2rBlocModere(l, mode) {
  if (!v2rModeres) return "";
  const m = v2rModeres[l.match_id] || {};
  const sansVersion = (x) => x && x.marche === x.marche_v2r;          // famille sans marché plus prudent : pari gardé tel quel
  const lignes = sansVersion(m[1]) && sansVersion(m[2]) ? v2rLigneModere(0, m[1], mode)
    : v2rLigneModere(1, m[1], mode) + v2rLigneModere(2, m[2], mode);
  return lignes ? `<div class="v2r-modere"><div class="v2r-modere-titre">Pari modéré associé</div>${lignes}</div>` : "";
}
// Date / heure du Cameroun (UTC+1) : même présentation que les autres moteurs (heure en gras, date dessous).
function v2rHoraire(ko) {
  const d = ko ? new Date(ko) : null; if (!d || Number.isNaN(d.getTime())) return { heure: "—", date: "" };
  const c = new Date(d.getTime() + 3600000);
  return { heure: c.toISOString().slice(11, 16).replace(":", "h"), date: v2rDate(c.toISOString().slice(0, 10)) };
}
// Derniers matchs de chaque équipe (moteur_v2r/pronostics.py : forme). Même rendu que les autres moteurs (.ax-hist) :
// score écrit domicile-extérieur, seuls les buts de l'équipe suivie sont colorés (vert gagné, orange nul, rouge perdu).
function v2rHistorique(l) {
  const f = l.forme; if (!f) return "";
  const bloc = (nom, liste) => {
    if (!Array.isArray(liste) || !liste.length) return "";
    const pastilles = liste.map((x) => {
      const bm = Number(x.bm), be = Number(x.be); if (!Number.isFinite(bm) || !Number.isFinite(be)) return "";
      const res = bm > be ? "ax-res-v" : bm === be ? "ax-res-n" : "ax-res-d";
      const titre = `${bm > be ? "Gagné" : bm === be ? "Nul" : "Perdu"} · ${x.lieu === "D" ? "à domicile" : "à l'extérieur"}${x.adversaire ? " contre " + x.adversaire : ""}${x.date ? " · " + x.date : ""}`;
      const suivi = `<span class="ax-but ${res}" title="${v2rEchappe(titre)}">${x.lieu === "D" ? bm : be}</span>`;
      const autre = x.lieu === "D" ? be : bm;
      return `<span class="ax-res">${x.lieu === "D" ? suivi + "-" + autre : autre + "-" + suivi}<small class="v2r-lieu">${x.lieu}</small></span>`;
    }).join("");
    return pastilles ? `<div class="ax-hist"><span class="ax-hist-eq">${v2rEchappe(nom)}</span><span class="ax-hist-liste">${pastilles}</span></div>` : "";
  };
  const corps = bloc(l.domicile || "Domicile", f.domicile) + bloc(l.exterieur || "Extérieur", f.exterieur);
  return corps ? `<div class="ax-hist-bloc"><div class="v2r-hist-titre">Derniers matchs (du plus récent au plus ancien)</div>${corps}</div>` : "";
}
// Explication courte : le critère décisif et les données historiques de la cellule.
function v2rExplication(l) {
  const roi = Number(l && l.roi_cellule);
  const rendement = Number.isFinite(roi) ? (roi >= 0 ? "+" : "−") + Math.abs(roi * 100).toFixed(1).replace(".", ",") + " %" : "indisponible";
  const n = Number(l && l.cellule_n);
  const echantillon = Number.isFinite(n) ? `${n} paris` : "effectif inconnu";
  const tr = Array.isArray(l && l.cellule_tranche_cote) ? `${v2rCote(l.cellule_tranche_cote[0])}–${v2rCote(l.cellule_tranche_cote[1])}` : "inconnue";
  return `<div class="v2r-explication"><strong>Pourquoi ce choix ?</strong><p>Sur ${v2rEchappe(echantillon)} comparables, cette option a généré historiquement <b>${v2rEchappe(rendement)} de gain net pour 100 unités misées</b> (cotes ${v2rEchappe(tr)}). La matrice la privilégie car ses résultats passés sont les meilleurs parmi les options admissibles. Cela ne garantit pas le prochain résultat.</p></div>`;
}
function v2rCarte(l, mode) {
  const score = Array.isArray(l.score) ? `${l.score[0]} - ${l.score[1]}` : "";
  const badge = v2rBadge(l);
  const profit = l.resultat ? ` · ${v2rUnites(l.profit)}` : "";
  const h = v2rHoraire(l.coup_d_envoi_utc);
  const section = document.createElement("section");
  section.className = "ax-carte ax-replie v2r-ax";
  section.setAttribute("aria-expanded", "false");
  const histo = v2rHistorique(l);
  section.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match">` +
      `<span class="ax-equipe ax-dom">${v2rEchappe(l.domicile)}</span>` +
      `<div class="ax-horaire"><strong>${v2rEchappe(h.heure)}</strong><span>${v2rEchappe(h.date)}</span></div>` +
      `<span class="ax-equipe ax-ext">${v2rEchappe(l.exterieur)}</span></div>` +
      `<div class="ax-match-bas"><p class="ax-competition">${v2rEchappe(String(l.competition || "").replace(/\s+/g, " ").trim())}</p><div class="ax-actions-tete"></div></div>` +
    `</div>` +
    `<div class="v2r-corps">` +
      (score ? `<div class="v2r-score">Score final <strong>${v2rEchappe(score)}</strong></div>` : "") +
      `<div class="v2r-ligne"><span>${v2rEchappe(v2rMarche(l))}</span><span class="v2r-cote">Cote ${v2rCote(l.cote)}</span></div>` +
      v2rExplication(l) +
      `<div class="v2r-ligne v2r-info"><span>ROI de la cellule sur l'échantillon : ${v2rPct(l.roi_cellule, true)} · buts attendus ${v2rEchappe((l.buts_attendus || []).join(" / "))}</span>${badge}</div>` +
      (mode === "regle" && profit ? `<div class="v2r-info">Mise 1 u${profit}</div>` : "") +
      v2rBlocModere(l, mode) +
    `</div>` +
    `<details class="ax-details" open><summary class="ax-summary-cache" tabindex="-1">Derniers scores</summary><div class="ax-details-corps">` +
      (histo || `<p class="v2r-vide">Derniers scores indisponibles pour ce pari (écrit avant l'ajout de cette rubrique).</p>`) +
    `</div></details>`;
  // Comme les autres moteurs : carte repliée au départ ; toucher la carte la déplie (derniers scores visibles) ou la replie.
  section.addEventListener("click", (e) => {
    if (e.target.closest("button, a, summary")) return;
    const sel = window.getSelection && window.getSelection();
    if (sel && String(sel).length) return;
    const avant = section.getBoundingClientRect().top;
    const replie = !section.classList.contains("ax-replie");
    section.classList.toggle("ax-replie", replie);
    section.setAttribute("aria-expanded", String(!replie));
    const apres = section.getBoundingClientRect().top;
    if (Math.abs(apres - avant) > 1) window.scrollBy(0, apres - avant);
  });
  return section;
}
function v2rListe(id, liste, mode, vide) {
  const el = document.getElementById(id); if (!el) return;
  el.innerHTML = "";
  if (liste && liste.length) liste.forEach((l) => el.appendChild(v2rCarte(l, mode)));
  else el.innerHTML = `<p class="v2r-vide">${v2rEchappe(vide)}</p>`;
}
function v2rAffiche(d) {
  const b = d.bilan || {};
  v2rModeres = v2rIndexModeres(d);
  if (d.modere && Number.isFinite(Number(d.modere.plancher))) v2rPlancher = Number(d.modere.plancher);
  const noms = { observation: "OBSERVATION — ne pas miser", actif: "ACTIF — rentabilité démontrée", non_rentable: "NON RENTABLE — ne pas miser" };
  document.getElementById("v2r-statut").innerHTML =
    `<div class="v2r-statut ${v2rEchappe(d.statut)}">${v2rEchappe(noms[d.statut] || d.statut)}` +
    `<small>${v2rEchappe(d.avertissement || "Borne basse de l'IC95 du ROI au-dessus de 0 sur 300 paris réglés au moins.")}` +
    ` Règles v${v2rEchappe(d.regles_version)} · ${Number(d.regles_cellules) || 0} cellules.</small></div>`;
  const ic = Array.isArray(b.ic95) ? `${v2rPct(b.ic95[0], true)} à ${v2rPct(b.ic95[1], true)}` : "—";
  document.getElementById("v2r-bilan").innerHTML =
    `<div class="v2r-bilan"><div><strong>${Number(b.regles) || 0}</strong>réglés</div>` +
    `<div><strong>${b.reussite == null ? "—" : v2rPct(b.reussite)}</strong>réussite</div>` +
    `<div><strong>${b.roi == null ? "—" : v2rPct(b.roi, true)}</strong>ROI</div>` +
    `<div><strong style="font-size:12px">${v2rEchappe(ic)}</strong>IC95</div></div>`;
  v2rListe("v2r-avenir", d.a_venir, "avenir", "Aucun pari à venir.");
  v2rListe("v2r-encours", d.en_cours, "encours", "Aucun match en cours.");
  v2rListe("v2r-regles", d.reglees, "regle", "Aucun pari réglé pour l'instant.");
  const g = d.genere_le ? new Date(d.genere_le) : null;
  document.getElementById("maj").textContent = g && !Number.isNaN(g.getTime())
    ? `Mis à jour le ${g.toLocaleDateString("fr-FR")} à ${g.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}` : "";
}
function v2rThemeNuit() {
  const bouton = document.getElementById("ax-bouton-theme"); if (!bouton) return;
  const applique = (nuit) => {
    document.body.classList.toggle("theme-nuit", nuit);
    bouton.textContent = nuit ? "☀" : "☾";
    bouton.setAttribute("aria-label", nuit ? "Activer le mode clair" : "Activer le mode nuit");
  };
  let nuit = false;
  try { nuit = localStorage.getItem(CLE_THEME_NUIT_V2R) === "1"; } catch (e) { /* stockage indisponible */ }
  applique(nuit);
  bouton.addEventListener("click", () => {
    const suivant = !document.body.classList.contains("theme-nuit");
    try { localStorage.setItem(CLE_THEME_NUIT_V2R, suivant ? "1" : "0"); } catch (e) { /* ignoré */ }
    applique(suivant);
  });
}
v2rThemeNuit();
if (document.getElementById("v2r-avenir")) {
  fetch(`data/v2r/pronostics_v2r.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`données v2r introuvables (${r.status}) : le moteur n'a pas encore tourné`); return r.json(); })
    .then(v2rAffiche)
    .catch((e) => { document.getElementById("maj").textContent = "Erreur de chargement : " + e.message; console.error(e); });
}
