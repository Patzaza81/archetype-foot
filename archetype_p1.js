// Page P1 – Analyse statistique, présentation calquée sur Gamma. Affiche data/calibration_p1/page_p1.json (écrit par p1_page_donnees.py à partir du journal gelé). Lecture seule : AUCUN calcul de probabilité ici.
"use strict";
const P1_URL = "data/calibration_p1/page_p1.json";
const P1_CLES = ["dom", "nul", "ext", "o15", "o25", "o35", "btts"];
const P1_NOMS = { dom: "Victoire domicile", nul: "Match nul", ext: "Victoire extérieur", o15: "Plus de 1,5 but", o25: "Plus de 2,5 buts", o35: "Plus de 3,5 buts", btts: "Les deux équipes marquent" };
const e = (x) => String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (x) => (x != null && Number.isFinite(Number(x)) ? Number(x) : null);
const pct = (x) => (num(x) == null ? "—" : Math.round(Number(x) * 100) + " %");
const pct1 = (x) => (num(x) == null ? "—" : (Number(x) * 100).toFixed(1).replace(".", ",") + " %");
const fr = (x, d) => (num(x) == null ? "—" : Number(x).toFixed(d == null ? 2 : d).replace(".", ","));
const signe = (x) => (num(x) == null ? "—" : (x >= 0 ? "+" : "−") + Math.abs(x * 100).toFixed(1).replace(".", ",") + " %");
const sur100 = (p) => Math.round(Number(p) * 100);
function jourFr(iso) {
  const d = new Date(`${iso}T12:00:00`); if (Number.isNaN(d.getTime())) return iso || "";
  const t = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim(); return t.charAt(0).toUpperCase() + t.slice(1);
}
function jourCourt(iso) {
  const d = new Date(`${iso}T12:00:00`); if (Number.isNaN(d.getTime())) return e(iso || "");
  return e(d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" }).replace(/\./g, ""));
}
function horaire(ko) {           // UTC -> heure du Cameroun (UTC+1)
  const d = ko ? new Date(ko) : null; if (!d || Number.isNaN(d.getTime())) return { heure: "—", date: "" };
  const c = new Date(d.getTime() + 3600000); return { heure: c.toISOString().slice(11, 16).replace(":", "h"), date: jourFr(c.toISOString().slice(0, 10)) };
}
const complet = (m) => m.p1_original && ["dom", "nul", "ext"].every((k) => num(m.p1_original[k]) != null);

function derniers(m) {
  const d = m.derniers_matchs; if (!d || !((d.dom && d.dom.length) || (d.ext && d.ext.length))) return "";
  const eq = (nom, lieu, liste, domicile) => {
    const l = Array.isArray(liste) ? liste : [], moy = (k) => (l.length ? l.reduce((a, x) => a + Number(x[k] || 0), 0) / l.length : NaN);
    const lignes = l.map((x) => {
      const a = Number(x.marques), b = Number(x.encaisses), lettre = a > b ? "V" : a < b ? "D" : "N", cls = a > b ? "om-v" : a < b ? "om-d" : "om-n";
      const score = domicile ? `<b>${a}</b> – ${b}` : `${b} – <b>${a}</b>`;
      return `<li class="om-dm"><span class="om-dm-date">${jourCourt(x.date)}</span><span class="om-dm-adv">${e(x.adversaire || "Adversaire inconnu")}</span><span class="om-dm-score">${score}</span><span class="om-dm-res ${cls}">${lettre}</span></li>`;
    }).join("");
    return `<div class="om-dm-eq"><div class="om-dm-tete"><span class="om-dm-nom">${e(nom)}</span><span class="om-dm-lieu">${lieu} · ${l.length} match${l.length > 1 ? "s" : ""}</span></div>` +
      (l.length ? `<div class="om-dm-puces"><span>Marque <b>${fr(moy("marques"), 1)}</b></span><span>Encaisse <b>${fr(moy("encaisses"), 1)}</b></span></div><ul class="om-dm-liste">${lignes}</ul>` : `<p class="om-info">Matchs indisponibles.</p>`) + `</div>`;
  };
  return `<div class="om-bloc"><div class="om-bloc-titre">Derniers matchs</div><div class="om-dm-grille">${eq(m.domicile, "À domicile", d.dom, true)}${eq(m.exterieur, "À l'extérieur", d.ext, false)}</div></div>`;
}
function ligne(x, m, principal, ev) {
  const badge = principal && ev && ev.pari ? `<span class="om-badge om-${ev.pari.gagne ? "WIN" : "LOSS"}">${ev.pari.gagne ? "GAGNÉ" : "PERDU"}</span>` : "";
  return `<div class="om-ligne ${principal ? "om-principal" : ""}"><span>${e(x.libelle)}<small class="om-sous">Chances selon P1 : ${sur100(x.p1)} sur 100</small></span><span><span class="om-cote">Cote ${fr(x.cote)}</span> ${badge}</span></div>`;
}
function pourquoi(m, r) {
  const p = m.p1_original, d = m.detail || {};
  const fav = ["dom", "nul", "ext"].reduce((a, k) => (p[k] > p[a] ? k : a), "dom"), nomFav = fav === "dom" ? m.domicile : fav === "ext" ? m.exterieur : "le match nul";
  const memeFav = (r.cle === "1" && fav === "dom") || (r.cle === "2" && fav === "ext") || (r.cle === "N" && fav === "nul");
  const buts = num(d.buts_attendus_dom) != null && num(d.buts_attendus_ext) != null ? `<span class="om-attendus">Buts attendus par P1 : ${e(m.domicile)} ${fr(d.buts_attendus_dom, 1)} – ${fr(d.buts_attendus_ext, 1)} ${e(m.exterieur)}.</span>` : "";
  return `<div class="om-pq"><p class="om-pq-txt">${buts}<b>Pourquoi ?</b> P1 estime que ce pari se réalise environ ${sur100(r.p1)} fois sur 100. La cote ${fr(r.cote)} correspond à ${Math.round(100 / r.cote)} fois sur 100 : elle est plus généreuse que le risque réel (avantage ${signe(r.valeur)}). ` +
    `${r.p1 < 0.5 ? "Pari risqué : il se perd plus souvent qu'il ne se gagne, mais la cote paie en conséquence." : "Pari qui se réalise plus souvent qu'il ne rate."} Favori du match selon P1 : ${e(nomFav)} (${sur100(p[fav])} sur 100)${memeFav ? "" : " ; la proposition ne suit pas forcément le favori, elle cherche la meilleure cote par rapport au risque"}.</p></div>`;
}
function stats(m) {
  const p = m.p1_original, lignes = P1_CLES.map((k) => `<tr><td>${e(P1_NOMS[k].replace("domicile", m.domicile).replace("extérieur", m.exterieur))}</td><td class="p1-v" data-k="${k}">${pct(p[k])}</td></tr>`).join("");
  const memes = P1_CLES.every((k) => m.p1_original[k] === m.p1_calibre[k]);
  const cal = memes ? `<div class="om-info">P1 calibré = P1 original (aucune correction validée pour cette compétition).</div>` :
    `<div class="om-info"><b>P1 original et P1 calibré diffèrent.</b></div><table class="om-table"><tr><th>Marché</th><th>Original</th><th>Calibré</th><th>Méthode</th></tr>${P1_CLES.map((k) => `<tr><td>${e(P1_NOMS[k])}</td><td>${pct1(m.p1_original[k])}</td><td>${pct1(m.p1_calibre[k])}</td><td>${e((m.methode || {})[k] || "—")}</td></tr>`).join("")}</table>`;
  const d = m.detail || {}, L = (m.pari && m.pari.marches) || [], ret = m.pari && m.pari.retenu ? m.pari.retenu.cle : null;
  const marches = L.length ? `<div class="om-bloc"><div class="om-bloc-titre">Tous les marchés évalués (${L.length})</div><table class="om-table"><tr><th>Marché</th><th>P1</th><th>Cote</th><th>Avantage</th></tr>` +
    L.map((x) => `<tr${x.cle === ret ? ' style="font-weight:800"' : ""}><td style="text-align:left">${e(x.libelle)}</td><td>${pct1(x.p1)}</td><td>${fr(x.cote)}</td><td>${signe(x.valeur)}</td></tr>`).join("") + `</table></div>` : "";
  return `<div class="om-bloc"><div class="om-bloc-titre">Probabilités de P1</div><table class="om-table p1-tabstats"><tr><th>Événement</th><th>P1</th></tr>${lignes}</table>${cal}</div>${marches}` +
    `<div class="om-bloc"><div class="om-info">Buts attendus : ${fr(d.buts_attendus_dom)} – ${fr(d.buts_attendus_ext)} · matchs antérieurs : ${e(d.matchs_anterieurs_dom ?? "—")} / ${e(d.matchs_anterieurs_ext ?? "—")} · lissage k ${e(d.k ?? "—")} · demi-vie ${d.demi_vie_jours == null ? "aucune" : e(d.demi_vie_jours) + " jours"}</div>` +
    `<div class="om-info">Gelé le ${e(m.gele_le || "—")} (UTC) · empreinte <span class="p1-mono">${e(String(m.empreinte || "").slice(0, 16))}…</span></div></div>`;
}
function carte(m) {
  const h = horaire(m.coup_d_envoi_utc), fin = m.statut === "termine" && m.resultat, ev = fin ? m.evaluation : null, pa = m.pari, r = pa && pa.retenu;
  const section = document.createElement("section"); section.className = "ax-carte ax-replie"; section.setAttribute("aria-expanded", "false");
  let corps;
  if (!complet(m)) corps = `<div class="om-info"><b>Pas de proposition</b></div><p class="om-vide">Prédiction P1 indisponible pour ce match.</p>`;
  else if (r) {
    const autres = (pa.marches || []).filter((x) => x.valeur > 0 && x.cle !== r.cle).sort((a, b) => b.p1 - a.p1);
    corps = `<div class="om-info"><b>Pari proposé</b></div>${ligne(r, m, true, ev)}${pourquoi(m, r)}` +
      (autres.length ? `<div class="om-autres"><div class="om-autres-titre">Autres options intéressantes</div>${autres.map((x) => `<div class="om-ligne"><span>${e(x.libelle)}<small class="om-sous">Chances selon P1 : ${sur100(x.p1)} sur 100</small></span><span class="om-cote">Cote ${fr(x.cote)}</span></div>`).join("")}</div>` : "");
  } else corps = `<div class="om-info"><b>Pas de proposition</b></div><p class="om-vide">${pa && pa.cotes_disponibles ? "P1 ne trouve aucune cote plus généreuse que le risque réel : il ne propose rien sur ce match." : "Les cotes ne sont pas disponibles : P1 ne peut pas proposer de pari. Ses probabilités restent consultables dans les détails."}</p>`;
  if (m.statut === "en_cours_ou_resultat_attendu") corps += `<div class="om-info">Coup d'envoi passé : résultat pas encore enregistré.</div>`;
  section.innerHTML = `<div class="ax-match"><div class="ax-ligne-match"><span class="ax-equipe ax-dom">${e(m.domicile)}</span><div class="ax-horaire"><strong>${fin ? e(m.resultat.buts_dom + " - " + m.resultat.buts_ext) : e(h.heure)}</strong><span>${e(h.date)}</span></div><span class="ax-equipe ax-ext">${e(m.exterieur)}</span></div>` +
    `<div class="ax-match-bas"><p class="ax-competition">${e(String(m.competition || "").replace(/\s+/g, " ").trim())}</p><div class="ax-actions-tete"></div></div></div>` +
    `<div class="om-corps">${corps}</div><details class="ax-details" open><summary class="ax-summary-cache" tabindex="-1">Détails</summary><div class="ax-details-corps">${derniers(m)}${complet(m) ? stats(m) : ""}</div></details>`;
  section.addEventListener("click", (ev2) => {
    if (ev2.target.closest("button, a, summary")) return;
    const sel = window.getSelection && window.getSelection(); if (sel && String(sel).length) return;
    const avant = section.getBoundingClientRect().top, replie = !section.classList.contains("ax-replie");
    section.classList.toggle("ax-replie", replie); section.setAttribute("aria-expanded", String(!replie));
    const apres = section.getBoundingClientRect().top; if (Math.abs(apres - avant) > 1) window.scrollBy(0, apres - avant);
  });
  return section;
}
function liste(id, L, vide) {
  const el = document.getElementById(id); if (!el) return; el.innerHTML = "";
  if (L.length) L.forEach((m) => el.appendChild(carte(m))); else el.innerHTML = `<p class="om-vide">${e(vide)}</p>`;
}
function bilan(d) {
  const p = d.performance || {}, q = d.performance_paris || {}, c = d.calibration || {};
  const ok = (c.couples_valides || 0) > 0;
  let h = `<div class="p1-statut ${ok ? "p1-valide" : "p1-neutre"}"><b>Calibration : ${ok ? c.couples_valides + " correction(s) validée(s)" : "aucune correction validée"}</b> (${e(c.couples_valides)} sur ${e(c.couples_total)} couples compétition × marché). ${ok ? e(c.texte) : "P1 calibré est donc identique à P1 original."} Mode : <b>${e(d.mode)}</b>${d.mode === "parallele" ? " (enregistrement en parallèle)" : ""}.</div>`;
  if (!q.paris) return [h, `<p class="om-info" style="margin:8px 14px">${e(q.note || "Aucun pari mesurable.")} Le bilan apparaîtra avec les premiers matchs terminés (${e(p.matchs_termines || 0)} terminé(s) à ce jour).</p>`];
  const o = (p.par_version || {}).original || {};
  return [h, `<table class="om-table"><tr><th>Paris P1 réglés</th><th>Gagnés</th><th>Réussite</th><th>Rendement moyen par mise</th></tr><tr><td>${e(q.paris)} (sur ${e(q.matchs_termines)} matchs, du ${e(jourFr(p.periode[0]))} au ${e(jourFr(p.periode[1]))})</td><td>${e(q.gagnes)}</td><td>${pct1(q.taux)} ± ${pct1(q.taux_erreur_type)}</td><td>${signe(q.rendement_moyen)} ± ${pct1(q.rendement_erreur_type)}</td></tr></table>` +
    (o.logloss_1x2 != null ? `<p class="om-info" style="margin:4px 14px">Résultats 1/N/2 : perte logarithmique ${fr(o.logloss_1x2, 3)} · favori correct ${e(o.favori_correct)}/${e(p.matchs_termines)} (${pct1(o.favori_taux)} ± ${pct1(o.favori_erreur_type)}).</p>` : "")];
}
function histo(d) {
  const j = d.journal || {}, rows = d.matchs.slice().sort((a, b) => (a.gele_le < b.gele_le ? 1 : -1)).map((m) => `<tr><td>${e(m.gele_le)}</td><td>${e(m.coup_d_envoi_utc)}</td><td style="text-align:left">${e(m.domicile)} – ${e(m.exterieur)}</td><td class="p1-mono">${e(String(m.empreinte || "").slice(0, 12))}</td></tr>`).join("");
  return `<details class="ax-calcul"><summary>Historique gelé des prédictions (${e(j.lignes)})</summary><div class="ax-details-corps" style="overflow-x:auto"><p class="om-info">Journal immuable : chaque ligne est chaînée à la précédente par empreinte SHA-256 et enregistrée avant le coup d'envoi. ${(j.anomalies || []).length ? `<b>${j.anomalies.length} anomalie(s) détectée(s).</b>` : "Contrôle d'intégrité : aucune anomalie."}</p><table class="om-table"><tr><th>Gelé le (UTC)</th><th>Coup d'envoi (UTC)</th><th>Match</th><th>Empreinte</th></tr>${rows}</table></div></details>`;
}
function affiche(d) {
  const L = d.matchs || [], av = L.filter((m) => m.statut === "a_venir"), ec = L.filter((m) => m.statut === "en_cours_ou_resultat_attendu"), tm = L.filter((m) => m.statut === "termine").reverse();
  const [a, b] = bilan(d); document.getElementById("p1-statut").innerHTML = a; document.getElementById("om-bilan").innerHTML = b;
  liste("om-avenir", av, "Aucun match à venir dans le journal P1."); liste("om-encours", ec, "Aucun match en cours."); liste("om-regles", tm, "Aucun match terminé avec prédiction gelée pour l'instant.");
  const sans = av.filter((m) => m.pari && !m.pari.retenu).length;
  document.getElementById("om-sans").textContent = sans ? `${sans} match${sans > 1 ? "s" : ""} à venir sans proposition : aucune cote n'est plus généreuse que le risque réel, ou les cotes manquent (P1 ne force jamais un pari).` : "";
  document.getElementById("p1-histo").innerHTML = histo(d);
  const g = d.genere_le ? new Date(d.genere_le) : null;
  document.getElementById("maj").textContent = g && !Number.isNaN(g.getTime()) ? `Données du ${g.toLocaleString("fr-FR", { timeZone: "Africa/Douala", dateStyle: "medium", timeStyle: "short" })} (heure du Cameroun) · ${L.length} match(s) dans le journal` : "";
}
(function theme() {
  const bouton = document.getElementById("ax-bouton-theme"); if (!bouton) return;
  const applique = (nuit) => { document.body.classList.toggle("theme-nuit", nuit); bouton.textContent = nuit ? "☀" : "☾"; bouton.setAttribute("aria-label", nuit ? "Activer le mode clair" : "Activer le mode nuit"); };
  let nuit = false; try { nuit = localStorage.getItem("archetype_theme_nuit") === "1"; } catch (x) { /* stockage indisponible */ }
  applique(nuit);
  bouton.addEventListener("click", () => { const s = !document.body.classList.contains("theme-nuit"); try { localStorage.setItem("archetype_theme_nuit", s ? "1" : "0"); } catch (x) { /* ignoré */ } applique(s); });
})();
fetch(`${P1_URL}?t=${Date.now()}`, { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(affiche)
  .catch((err) => { document.getElementById("maj").textContent = "Données P1 indisponibles : aucune valeur n'est affichée."; console.error(err); });
