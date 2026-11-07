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
const FAMILLES = [["buts", "Marchés de buts"], ["equipes", "Marchés d'équipes"], ["combos", "Marchés combos"]];
const NB_VISIBLES = 3;
const maj1 = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");

function ligne(p, fini) {
  const pct = Math.round(Number(p.taux) * 100), [kd, nd] = p.reussite_dom, [ke, ne] = p.reussite_ext, tient = p.verdict === "TIENT";
  const badge = fini && p.gagne != null ? `<span class="om-badge om-${p.gagne ? "WIN" : "LOSS"}">${p.gagne ? "GAGNÉ" : "PERDU"}</span>` : "";
  return `<div class="vf-pari"><div class="om-ligne"><span>${e(p.libelle)}<small class="om-sous">Réussi ${kd} sur ${nd} (domicile) et ${ke} sur ${ne} (extérieur) · ${e(maj1(p.lecture_xg))}</small></span>` +
    `<span class="vf-droite"><span class="om-cote">Cote ${fr(p.cote)}</span> <span class="vf-verdict vf-${tient ? "tient" : "reserve"}">${tient ? "Tient" : "Tient avec réserve"}</span> ${badge}</span></div>` +
    `<div class="vf-taux"><div class="om-jauge"><i style="width:${pct}%"></i></div><span>${pct} %</span></div></div>`;
}
function familles(m) {
  const fini = m.statut === "termine";
  return FAMILLES.map(([k, titre]) => {
    const L = (m.paris && m.paris[k]) || []; if (!L.length) return "";
    const vis = L.slice(0, NB_VISIBLES).map((p) => ligne(p, fini)).join(""), reste = L.slice(NB_VISIBLES);
    return `<div class="om-bloc vf-famille"><div class="om-bloc-titre">${titre} (${L.length})</div>${vis}` +
      (reste.length ? `<details class="vf-reste"><summary>Voir les ${reste.length} autre${reste.length > 1 ? "s" : ""}</summary>${reste.map((p) => ligne(p, fini)).join("")}</details>` : "") + `</div>`;
  }).join("");
}
function tableau(m) {
  const q = m.equipes || {}, d = q.dom || {}, x = q.ext || {}, c = q.championnat || {};
  const estime = m.xg_source === "estimé";
  const xgChamp = c.xg != null ? fr(c.xg) : (c.buts != null ? `${fr(c.buts)} (estimé : buts de la saison)` : "—");
  let h = `<div class="om-bloc"><div class="om-bloc-titre">Les deux équipes (saison entière, ${e(d.n ?? "—")} et ${e(x.n ?? "—")} matchs)</div><table class="om-table"><tr><th></th><th>${e(m.domicile)}</th><th>${e(m.exterieur)}</th><th>Moyenne du championnat</th></tr>` +
    `<tr><td>xG créés par match</td><td>${fr(d.xg_cree)}</td><td>${fr(x.xg_cree)}</td><td>${xgChamp}</td></tr>` +
    `<tr><td>xG concédés par match</td><td>${fr(d.xg_concede)}</td><td>${fr(x.xg_concede)}</td><td>—</td></tr>` +
    `<tr><td>Buts marqués par match</td><td>${fr(d.buts_marques, 1)}</td><td>${fr(x.buts_marques, 1)}</td><td>${fr(c.buts, 1)}</td></tr>` +
    `<tr><td>Buts encaissés par match</td><td>${fr(d.buts_encaisses, 1)}</td><td>${fr(x.buts_encaisses, 1)}</td><td>${fr(c.buts, 1)}</td></tr>` +
    `<tr><td>Écart xG (créés − concédés)</td><td><b>${d.ecart_xg == null ? "—" : (d.ecart_xg >= 0 ? "+" : "−") + fr(Math.abs(d.ecart_xg))}</b></td><td><b>${x.ecart_xg == null ? "—" : (x.ecart_xg >= 0 ? "+" : "−") + fr(Math.abs(x.ecart_xg))}</b></td><td></td></tr></table>`;
  if (m.buts_attendus) h += `<div class="om-info">${estime ? "xG estimé avec les buts de la saison (Matchendirect) et la moyenne du championnat" : "Buts attendus d'après le xG de la saison"}, avantage du terrain compris : <b>${fr(m.buts_attendus[0], 1)} – ${fr(m.buts_attendus[1], 1)}</b>.</div>`;
  else h += `<div class="om-info">xG indisponible : trop peu de matchs pour l'estimer.</div>`;
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
function carte(m) {
  const h = horaire(m.coup_d_envoi_utc), fin = m.statut === "termine" && m.resultat;
  const section = document.createElement("section"); section.className = "ax-carte ax-replie"; section.setAttribute("aria-expanded", "false");
  let corps = familles(m); if (m.statut === "en_cours_ou_resultat_attendu") corps += `<div class="om-info">Coup d'envoi passé : résultat pas encore enregistré.</div>`;
  section.innerHTML = `<div class="ax-match"><div class="ax-ligne-match"><span class="ax-equipe ax-dom">${e(m.domicile)}</span><div class="ax-horaire"><strong>${fin ? e(m.resultat.buts_dom + " - " + m.resultat.buts_ext) : e(h.heure)}</strong><span>${e(h.date)}</span></div><span class="ax-equipe ax-ext">${e(m.exterieur)}</span></div>` +
    `<div class="ax-match-bas"><p class="ax-competition">${e(String(m.competition || "").replace(/\s+/g, " ").trim())}</p><div class="ax-actions-tete"></div></div></div>` +
    `<div class="om-corps">${corps}</div><details class="ax-details" open><summary class="ax-summary-cache" tabindex="-1">Détails</summary><div class="ax-details-corps">${tableau(m)}${derniers(m)}</div></details>`;
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
  if (L.length) L.forEach((m) => el.appendChild(carte(m))); else el.innerHTML = `<p class="om-vide">${e(vide)}</p>`;
}
function bilan(d) {
  const B = d.bilan || {}, cles = Object.keys(B);
  if (!cles.length) return `<p class="om-info" style="margin:8px 14px">Aucun pari gelé n'est encore terminé : le bilan réel apparaîtra avec les premiers matchs terminés.</p>`;
  const ordre = ["TIENT", "TIENT AVEC RÉSERVE", "NE TIENT PAS"];
  return `<table class="om-table"><tr><th>Verdict gelé avant le match</th><th>Paris terminés</th><th>Réussis</th><th>Réussite réelle</th></tr>` +
    ordre.filter((k) => B[k]).map((k) => `<tr><td style="text-align:left">${e(maj1(k.toLowerCase()))}</td><td>${e(B[k].paris)}</td><td>${e(B[k].reussis)}</td><td>${Math.round(B[k].taux_reel * 100)} %</td></tr>`).join("") + `</table>`;
}
function affiche(d) {
  const L = d.matchs || [], av = L.filter((m) => m.statut === "a_venir"), ec = L.filter((m) => m.statut === "en_cours_ou_resultat_attendu"), tm = L.filter((m) => m.statut === "termine").reverse();
  document.getElementById("vf-bilan").innerHTML = bilan(d);
  liste("om-avenir", av, "Aucun match à venir avec un pari qui passe les filtres."); liste("om-encours", ec, "Aucun match en cours."); liste("om-regles", tm, "Aucun match terminé pour l'instant.");
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
