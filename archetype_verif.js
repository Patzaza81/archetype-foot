// Page « Vérification des pronostics » : affiche data/verif_pronostics/page_verif.json (écrit par verif_pronostic.py page). Lecture seule : AUCUN calcul ici.
"use strict";
const VF_URL = "data/verif_pronostics/page_verif.json";
const e = (x) => String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (x) => (x != null && Number.isFinite(Number(x)) ? Number(x) : null);
const fr = (x, d) => (num(x) == null ? "—" : Number(x).toFixed(d == null ? 2 : d).replace(".", ","));
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
const ONGLETS_PAGE = [["tous", "Tous"], ["top20", "Top 20"], ["regles", "Règles"], ["buts", "Buts"], ["equipes", "Équipes"], ["combos", "Combos"], ["victoire", "Victoire"]];
const TITRES = { buts: "Marchés de buts", equipes: "Marchés d'équipes", combos: "Marchés combos", victoire: "Marchés de victoire", regles: "Marchés à règle validée" };
const COTE_TOP = 1.34;
const ORDRE_FAMILLES = ["buts", "equipes", "victoire", "combos"];
let ONGLET = "tous", DONNEES = null;
const maj1 = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");
let TOP = new Map();
const paris = (m, onglet) => (onglet === "tous" || onglet === "top20" ? ORDRE_FAMILLES.flatMap((k) => (m.paris && m.paris[k]) || []) : onglet === "regles" ? ORDRE_FAMILLES.flatMap((k) => ((m.paris && m.paris[k]) || []).filter((p) => p.regle)) : (m.paris && m.paris[onglet]) || []);
const meilleur = (L) => L.slice().sort((a, b) => b.taux - a.taux || (a.verdict === b.verdict ? 0 : a.verdict === "TIENT" ? -1 : 1) || (b.reussite_dom[1] + b.reussite_ext[1]) - (a.reussite_dom[1] + a.reussite_ext[1]))[0];

function ligne(p, fini, reco) {
  const pct = Math.round(Number(p.taux) * 100), [kd, nd] = p.reussite_dom, [ke, ne] = p.reussite_ext, tient = p.verdict === "TIENT";
  const badge = fini && p.gagne != null ? `<span class="om-badge om-${p.gagne ? "WIN" : "LOSS"}">${p.gagne ? "GAGNÉ" : "PERDU"}</span>` : "";
  return `<div class="vf-pari"><div class="om-ligne"><span>${e(p.libelle)}<small class="om-sous">Réussi ${kd} sur ${nd} (domicile) et ${ke} sur ${ne} (extérieur) · ${e(maj1(p.lecture_xg))}</small></span>` +
    `<span class="vf-droite"><span class="om-cote">Cote ${fr(p.cote)}</span> <span class="vf-verdict vf-${tient ? "tient" : "reserve"}">${tient ? "Tient" : "Tient avec réserve"}</span>${reco ? ` <span class="vf-reco">Recommandé</span>` : ""}${p.regle ? ` <span class="vf-regle" title="Ce marché a une condition validée sur les résultats passés, et elle est remplie pour ce match">Règle validée</span>` : ""} ${badge}</span></div>` +
    `<div class="vf-taux"><div class="om-jauge"><i style="width:${pct}%"></i></div><span>${pct} %</span></div></div>`;
}
// Critère du Top 20 (09/11, d'après les résultats réels des 7 et 8 nov) : la réussite observée seule ne classe pas (les paris « les plus solides » sont les moins réussis),
// la probabilité du marché (1 / cote) classe mieux. On garde donc la plus prudente des deux : un pari n'est haut placé que si l'historique ET la cote le jugent sûr.
const score = (p) => Math.min(Number(p.taux), 1 / Number(p.cote));
function top20(d) {   // les 20 meilleurs paris de chaque journée, toutes familles, cote >= 1,34, un pari (le mieux noté) par match
  const jours = {};
  (d.matchs || []).forEach((m) => {
    const L = paris(m, "tous").filter((x) => Number(x.cote) >= COTE_TOP); if (!L.length) return;
    const p = L.slice().sort((a, b) => score(b) - score(a) || b.taux - a.taux)[0], j = horaire(m.coup_d_envoi_utc).date;
    (jours[j] = jours[j] || []).push({ m, p });
  });
  const sortie = new Map();
  Object.values(jours).forEach((L) => L.sort((a, b) => score(b.p) - score(a.p) || b.p.taux - a.p.taux).slice(0, 20).forEach((x, i) => sortie.set(x.m.match_id, { p: x.p, rang: i + 1, nb: Math.min(20, L.length) })));
  return sortie;
}
function resume(m, onglet) {
  if (onglet === "top20") {
    const t = TOP.get(m.match_id); if (!t) return "";
    return `<div class="om-bloc vf-famille"><div class="om-bloc-titre">Top 20 du jour · n° ${t.rang}</div>${ligne(t.p, m.statut === "termine", true)}</div>`;
  }            // carte repliée : UN SEUL pari, le mieux classé de l'onglet
  const p = meilleur(paris(m, onglet)); if (!p) return "";
  return `<div class="om-bloc vf-famille"><div class="om-bloc-titre">${onglet === "tous" ? "Meilleur pari du match" : "Meilleur : " + TITRES[onglet].toLowerCase()}</div>${ligne(p, m.statut === "termine")}</div>`;
}
function listes(m, onglet) {            // carte dépliée : tous les paris de l'onglet, du plus au moins réussi
  const fini = m.statut === "termine", cles = onglet === "tous" || onglet === "regles" ? ORDRE_FAMILLES : [onglet];
  return cles.map((k) => {
    const L0 = (m.paris && m.paris[k]) || [], L = onglet === "regles" ? L0.filter((p) => p.regle) : L0; if (!L.length) return "";
    return `<div class="om-bloc vf-famille"><div class="om-bloc-titre">${TITRES[k]} (${L.length}) · du plus au moins réussi</div>${L.map((p) => ligne(p, fini)).join("")}</div>`;
  }).join("");
}
function tableau(m) {
  const q = m.equipes || {}, d = q.dom || {}, x = q.ext || {}, c = q.championnat || {};
  const estime = m.xg_source === "estimé", ap = (q, v) => (v == null ? "—" : (q.xg_est ? "≈ " : "") + fr(v));
  const xgChamp = c.xg != null ? (c.xg_est ? "≈ " : "") + fr(c.xg) : "—";
  const signe = (q) => (q.ecart_xg == null ? "—" : (q.xg_est ? "≈ " : "") + (q.ecart_xg >= 0 ? "+" : "−") + fr(Math.abs(q.ecart_xg)));
  let h = `<div class="om-bloc"><div class="om-bloc-titre">Les deux équipes (saison entière, ${e(d.n ?? "—")} et ${e(x.n ?? "—")} matchs)</div><table class="om-table"><tr><th></th><th>${e(m.domicile)}</th><th>${e(m.exterieur)}</th><th>Moyenne du championnat</th></tr>` +
    `<tr><td>xG créés par match</td><td>${ap(d, d.xg_cree)}</td><td>${ap(x, x.xg_cree)}</td><td>${xgChamp}</td></tr>` +
    `<tr><td>xG concédés par match</td><td>${ap(d, d.xg_concede)}</td><td>${ap(x, x.xg_concede)}</td><td>—</td></tr>` +
    `<tr><td>Buts marqués par match</td><td>${fr(d.buts_marques, 1)}</td><td>${fr(x.buts_marques, 1)}</td><td>${fr(c.buts, 1)}</td></tr>` +
    `<tr><td>Buts encaissés par match</td><td>${fr(d.buts_encaisses, 1)}</td><td>${fr(x.buts_encaisses, 1)}</td><td>${fr(c.buts, 1)}</td></tr>` +
    `<tr><td>Écart xG (créés − concédés)</td><td><b>${signe(d)}</b></td><td><b>${signe(x)}</b></td><td></td></tr></table>`;
  if (m.buts_attendus) h += `<div class="om-info">${estime ? "xG estimé avec les buts de la saison (Matchendirect), formule apprise sur Football-Data" : "Buts attendus d'après le xG de la saison"}, avantage du terrain compris : <b>${fr(m.buts_attendus[0], 1)} – ${fr(m.buts_attendus[1], 1)}</b>.</div>`;
  else h += `<div class="om-info">xG indisponible : trop peu de matchs pour l'estimer.</div>`;
  if (estime || d.xg_est || x.xg_est) h += `<div class="om-info">≈ = xG estimé (le xG manque) : formule apprise sur les équipes Football-Data, appliquée aux buts de la saison.</div>`;
  return h + `</div>`;
}
const ONGLETS = [["dom", "À domicile"], ["ext", "À l'extérieur"], ["h2h", "H2H"]];
function derniers(m) {
  const d = m.derniers_matchs || {}, L = (k) => (Array.isArray(d[k]) ? d[k] : []);
  if (!["dom", "ext", "dom_ext", "ext_dom", "h2h"].some((k) => L(k).length)) return "";
  const lignes = (l) => l.map((x) => {
    const a = Number(x.marques), b = Number(x.encaisses), lettre = a > b ? "V" : a < b ? "D" : "N", cls = a > b ? "om-v" : a < b ? "om-d" : "om-n";
    const score = x.dom ? `<b>${a}</b> – ${b}` : `${b} – <b>${a}</b>`;
    return `<li class="om-dm" data-date="${e(x.date)}"><span class="om-dm-date">${jourCourt(x.date)}</span><span class="om-dm-adv">${e(x.adv || "Adversaire inconnu")}</span><span class="om-dm-score">${score}</span><span class="om-dm-res ${cls}">${lettre}</span></li>`;
  }).join("");
  const panneau = (l, vide) => {
    const moy = (k) => (l.length ? l.reduce((s, x) => s + Number(x[k] || 0), 0) / l.length : NaN);
    return l.length ? `<div class="om-dm-puces"><span>Marque <b>${fr(moy("marques"), 1)}</b></span><span>Encaisse <b>${fr(moy("encaisses"), 1)}</b></span><span>${l.length} match${l.length > 1 ? "s" : ""}</span></div><ul class="om-dm-liste">${lignes(l)}</ul>` : `<p class="om-vide">${vide}</p>`;
  };
  const eq = (nom, defaut, ens) => `<div class="om-dm-eq"><div class="om-dm-tete"><span class="om-dm-nom">${e(nom)}</span></div>` +
    `<div class="om-onglets" role="tablist">${ONGLETS.map(([k, t]) => `<button type="button" class="om-onglet${k === defaut ? " om-onglet-actif" : ""}" role="tab" aria-selected="${k === defaut}" data-onglet="${k}">${t}</button>`).join("")}</div>` +
    ONGLETS.map(([k]) => `<div class="om-dm-panneau" data-panneau="${k}"${k === defaut ? "" : " hidden"}>${panneau(ens[k], k === "h2h" ? "Aucune confrontation trouvée dans les données." : "Matchs indisponibles.")}</div>`).join("") + `</div>`;
  const li = (liste, dom) => liste.map((x) => ({ date: x.date, adv: x.adversaire, marques: x.marques, encaisses: x.encaisses, dom }));
  const h2h = L("h2h");
  const ensDom = { dom: li(L("dom"), true), ext: li(L("dom_ext"), false), h2h: h2h.map((x) => ({ date: x.date, adv: m.exterieur, marques: x.marques, encaisses: x.encaisses, dom: x.domicile })) };
  const ensExt = { dom: li(L("ext_dom"), true), ext: li(L("ext"), false), h2h: h2h.map((x) => ({ date: x.date, adv: m.domicile, marques: x.encaisses, encaisses: x.marques, dom: !x.domicile })) };
  return `<div class="om-bloc"><div class="om-bloc-titre">Derniers matchs</div><div class="om-dm-grille">${eq(m.domicile, "dom", ensDom)}${eq(m.exterieur, "ext", ensExt)}</div></div>`;
}
function carte(m, onglet) {
  const h = horaire(m.coup_d_envoi_utc), fin = m.statut === "termine" && m.resultat;
  const section = document.createElement("section"); section.className = "ax-carte ax-replie"; section.setAttribute("aria-expanded", "false");
  let corps = resume(m, onglet); if (m.statut === "en_cours_ou_resultat_attendu") corps += `<div class="om-info">Coup d'envoi passé : résultat pas encore enregistré.</div>`;
  section.innerHTML = `<div class="ax-match"><div class="ax-ligne-match"><span class="ax-equipe ax-dom">${e(m.domicile)}</span><div class="ax-horaire"><strong>${fin ? e(m.resultat.buts_dom + " - " + m.resultat.buts_ext) : e(h.heure)}</strong><span>${e(h.date)}</span></div><span class="ax-equipe ax-ext">${e(m.exterieur)}</span></div>` +
    `<div class="ax-match-bas"><p class="ax-competition">${e(String(m.competition || "").replace(/\s+/g, " ").trim())}</p><div class="ax-actions-tete"></div></div></div>` +
    `<div class="om-corps">${corps}</div><details class="ax-details" open><summary class="ax-summary-cache" tabindex="-1">Détails</summary><div class="ax-details-corps">${listes(m, onglet)}${tableau(m)}${derniers(m)}</div></details>`;
  section.addEventListener("click", (ev2) => {
    const bo = ev2.target.closest(".om-onglet");
    if (bo) {
      const eq = bo.closest(".om-dm-eq");
      eq.querySelectorAll(".om-onglet").forEach((x) => { x.classList.toggle("om-onglet-actif", x === bo); x.setAttribute("aria-selected", String(x === bo)); });
      eq.querySelectorAll(".om-dm-panneau").forEach((x) => { x.hidden = x.dataset.panneau !== bo.dataset.onglet; });
      return;
    }
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
  if (L.length) L.forEach((m) => el.appendChild(carte(m, ONGLET))); else el.innerHTML = `<p class="om-vide">${e(vide)}</p>`;
}
function barreOnglets(d) {
  const n = (o) => o === "top20" ? TOP.size : (d.matchs || []).filter((m) => paris(m, o).length).length;
  return `<div class="om-onglets vf-onglets" role="tablist">${ONGLETS_PAGE.map(([k, t]) => `<button type="button" class="om-onglet${k === ONGLET ? " om-onglet-actif" : ""}" role="tab" aria-selected="${k === ONGLET}" data-vf="${k}">${t} <small>${n(k)}</small></button>`).join("")}</div>`;
}
function rendu(d) {
  TOP = top20(d);
  let L = (d.matchs || []).filter((m) => paris(m, ONGLET).length);
  if (ONGLET === "top20") L = L.filter((m) => TOP.has(m.match_id)).sort((a, b) => String(a.coup_d_envoi_utc).slice(0, 10) === String(b.coup_d_envoi_utc).slice(0, 10) && 0 || (horaire(a.coup_d_envoi_utc).date === horaire(b.coup_d_envoi_utc).date ? TOP.get(a.match_id).rang - TOP.get(b.match_id).rang : String(a.coup_d_envoi_utc).localeCompare(b.coup_d_envoi_utc)));
  const av = L.filter((m) => m.statut === "a_venir"), ec = L.filter((m) => m.statut === "en_cours_ou_resultat_attendu"), tm = L.filter((m) => m.statut === "termine").reverse();
  document.getElementById("vf-onglets").innerHTML = barreOnglets(d);
  liste("om-avenir", av, "Aucun match à venir pour cet onglet."); liste("om-encours", ec, "Aucun match en cours."); liste("om-regles", tm, "Aucun match terminé pour l'instant.");
}
// Réussite réelle du Top 20 et de l'onglet Règles : leur dernier état gelé avant le coup d'envoi (journal_selections.jsonl), matchs terminés. Rien n'est affiché tant qu'aucun n'est terminé.
function selectionsGelees(d) {
  const S = d.bilan_selections || {}, noms = [["top20", "Top 20 (recommandé)"], ["regles", "Onglet Règles"]];
  return noms.filter(([k]) => S[k] && S[k].paris).map(([k, t]) => `<tr><td style="text-align:left">${t}</td><td>${e(S[k].paris)}</td><td>${e(S[k].reussis)}</td><td>${Math.round(S[k].taux_reel * 100)} %</td></tr>`).join("");
}
function bilan(d) {
  const B = d.bilan || {}, cles = Object.keys(B);
  if (!cles.length) return `<p class="om-info" style="margin:8px 14px">Aucun pari gelé n'est encore terminé : le bilan réel apparaîtra avec les premiers matchs terminés.</p>`;
  const ordre = ["TIENT", "TIENT AVEC RÉSERVE", "NE TIENT PAS"];
  return `<table class="om-table"><tr><th>Verdict gelé avant le match</th><th>Paris terminés</th><th>Réussis</th><th>Réussite réelle</th></tr>` +
    ordre.filter((k) => B[k]).map((k) => `<tr><td style="text-align:left">${e(maj1(k.toLowerCase()))}</td><td>${e(B[k].paris)}</td><td>${e(B[k].reussis)}</td><td>${Math.round(B[k].taux_reel * 100)} %</td></tr>`).join("") +
    selectionsGelees(d) + `</table>`;
}
function affiche(d) {
  const L = d.matchs || []; DONNEES = d;
  document.getElementById("vf-bilan").innerHTML = bilan(d); rendu(d);
  document.getElementById("vf-onglets").addEventListener("click", (ev) => { const b = ev.target.closest("[data-vf]"); if (!b) return; ONGLET = b.dataset.vf; rendu(DONNEES); });
  const g = d.genere_le ? new Date(d.genere_le) : null;
  document.getElementById("maj").textContent = g && !Number.isNaN(g.getTime()) ? `Données du ${g.toLocaleString("fr-FR", { timeZone: "Africa/Douala", dateStyle: "medium", timeStyle: "short" })} (heure du Cameroun) · ${L.length} match(s) · cote minimale ${fr(d.cote_min)} · au moins ${e(d.minimum_matchs_meme_lieu)} matchs au même lieu par équipe` : "";
}
(function theme() {
  const bouton = document.getElementById("ax-bouton-theme"); if (!bouton) return;
  const applique = (nuit) => { document.body.classList.toggle("theme-nuit", nuit); bouton.textContent = nuit ? "☀" : "☾"; bouton.setAttribute("aria-label", nuit ? "Activer le mode clair" : "Activer le mode nuit"); };
  let nuit = false; try { nuit = localStorage.getItem("archetype_theme_nuit") === "1"; } catch (x) { /* stockage indisponible */ }
  applique(nuit);
  bouton.addEventListener("click", () => { const s = !document.body.classList.contains("theme-nuit"); try { localStorage.setItem("archetype_theme_nuit", s ? "1" : "0"); } catch (x) { /* ignoré */ } applique(s); });
})();
fetch(`${VF_URL}?t=${Date.now()}`, { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then(affiche)
  .catch((err) => { document.getElementById("maj").textContent = "Données indisponibles : aucune valeur n'est affichée."; console.error(err); });
