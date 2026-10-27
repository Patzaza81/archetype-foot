// Page Omega : affiche data/omega/pronostics.json (écrit par moteur_omega.suivi). Lecture seule, aucun calcul métier.
"use strict";
const OM_CLE_THEME = "archetype_theme_nuit";

function omE(x) {
  return String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function omCote(x) { const n = Number(x); return Number.isFinite(n) ? n.toFixed(2).replace(".", ",") : "—"; }
function omPct(x) { const n = Number(x); return Number.isFinite(n) ? Math.round(n * 100) + " %" : "—"; }
function omPct1(x) { const n = Number(x); return Number.isFinite(n) ? (n * 100).toFixed(1).replace(".", ",") + " %" : "—"; }
function omSigne(x) { const n = Number(x); return Number.isFinite(n) ? (n >= 0 ? "+" : "−") + Math.abs(n * 100).toFixed(1).replace(".", ",") + " %" : "—"; }
function omFr(x, d) { const n = Number(x); return Number.isFinite(n) ? n.toFixed(d == null ? 1 : d).replace(".", ",") : "—"; }
function omDate(iso) {
  const d = new Date(`${iso}T12:00:00`); if (Number.isNaN(d.getTime())) return iso || "";
  const t = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
function omHoraire(ko) {          // coup d'envoi UTC -> heure du Cameroun (UTC+1)
  const d = ko ? new Date(ko) : null; if (!d || Number.isNaN(d.getTime())) return { heure: "—", date: "" };
  const c = new Date(d.getTime() + 3600000);
  return { heure: c.toISOString().slice(11, 16).replace(":", "h"), date: omDate(c.toISOString().slice(0, 10)) };
}
const omButs = (n) => `${n} but${n > 1 ? "s" : ""}`;
const omVirg = (t) => String(t).replace(".", ",");

// Phrase du pari à partir de sa clé (groupe, sélection), avec le nom des équipes et la valeur réelle en buts entiers.
function omPhrase(cle, dom, ext) {
  const g = String(cle[0]), s = String(cle[1]);
  const res = { "1": `Victoire ${dom}`, "N": "Match nul", "2": `Victoire ${ext}` };
  const dc = { "1N": `${dom} ou match nul`, "N2": `Match nul ou ${ext}`, "12": `${dom} ou ${ext} (pas de match nul)` };
  const total = (ligne, sens) => {
    const l = Number(ligne);
    return sens === "plus" ? `au moins ${omButs(Math.ceil(l))} dans le match` : (Math.floor(l) ? `pas plus de ${omButs(Math.floor(l))} dans le match` : "aucun but dans le match");
  };
  let r;
  if (g === "1x2") return { titre: res[s] };
  if (g === "double_chance") return { titre: dc[s] };
  if (g === "btts") return { titre: s === "Oui" ? "Les deux équipes marquent" : "Au moins une équipe ne marque pas" };
  if ((r = g.match(/^cages_inviolees_(domicile|exterieur)$/))) {
    const eq = r[1] === "domicile" ? dom : ext;
    return { titre: s === "oui" ? `${eq} n'encaisse aucun but` : `${eq} encaisse au moins 1 but` };
  }
  if ((r = g.match(/^over_under_(domicile|exterieur)_(\d+\.5)$/))) {
    const eq = r[1] === "domicile" ? dom : ext, l = Number(r[2]);
    return { titre: `${s === "plus" ? "Plus" : "Moins"} de ${omVirg(r[2])} buts pour ${eq}`,
      reel: s === "plus" ? `${eq} marque au moins ${omButs(Math.ceil(l))}` : (Math.floor(l) ? `${eq} marque au plus ${omButs(Math.floor(l))}` : `${eq} ne marque pas`) };
  }
  if ((r = g.match(/^over_under_(\d+\.5)$/))) return { titre: `${s === "plus" ? "Plus" : "Moins"} de ${omVirg(r[1])} buts`, reel: total(r[1], s) };
  if ((r = g.match(/^handicap_(-?\d+\.5)$/))) {
    const h = s === "domicile" ? Number(r[1]) : -Number(r[1]), eq = s === "domicile" ? dom : ext;
    const phrase = h > 0 ? (h < 1 ? `${eq} ne perd pas` : `${eq} ne perd pas par ${omButs(Math.ceil(h))} d'écart ou plus`)
      : (h > -1 ? `${eq} gagne` : `${eq} gagne par ${omButs(Math.ceil(-h))} d'écart ou plus`);
    return { titre: phrase, reel: `handicap ${h > 0 ? "+" : "−"}${omVirg(Math.abs(h))}` };
  }
  if (s.includes("|")) {
    const [a, b] = s.split("|");
    const debut = g.startsWith("dc_") ? dc[a] : res[a];
    let fin;
    if (g.endsWith("btts")) fin = b === "Oui" ? "les deux équipes marquent" : "au moins une équipe ne marque pas";
    else fin = total(g.split("_").pop(), b);
    return { titre: `${debut} et ${fin}` };
  }
  return { titre: `${g} ${s}` };
}
function omBadge(p) {
  return p && p.resultat ? `<span class="om-badge om-${omE(p.resultat)}">${p.resultat === "WIN" ? "GAGNÉ" : "PERDU"}</span>` : "";
}
function omMoy(v) { return Array.isArray(v) && v.length ? v.reduce((a, b) => a + b, 0) / v.length : NaN; }

// « Pourquoi ce pari » : en positif, avec les chiffres réels des matchs des deux équipes.
function omPourquoi(f) {
  const s = f.series || {}, p = f.principal || {}, l = [];
  l.push(`Buts attendus : <b>${omE(f.domicile)} ${omFr((f.buts_attendus || {}).dom)}</b> – <b>${omFr((f.buts_attendus || {}).ext)} ${omE(f.exterieur)}</b>`);
  l.push(`${omE(f.domicile)} à domicile : ${omFr(omMoy(s.dom_marques))} but marqué et ${omFr(omMoy(s.dom_encaisses))} encaissé par match (${f.n_domicile} matchs)`);
  l.push(`${omE(f.exterieur)} à l'extérieur : ${omFr(omMoy(s.ext_marques))} but marqué et ${omFr(omMoy(s.ext_encaisses))} encaissé par match (${f.n_exterieur} matchs)`);
  if (p.p_modele != null && p.p_cote != null) l.push(`Les chiffres des deux équipes donnent ${omPct(p.p_modele)} et la cote BetPawa ${omPct(p.p_cote)} : les deux sont d'accord`);
  return `<div class="om-pourquoi">${l.map((x) => `<div>${x}</div>`).join("")}</div>`;
}
function omLigne(p, f, principal) {
  const ph = omPhrase(p.cle, f.domicile, f.exterieur);
  return `<div class="om-ligne ${principal ? "om-principal" : ""}"><span>${omE(ph.titre)}${ph.reel ? `<small class="om-sous">${omE(ph.reel)}</small>` : ""}` +
    (principal ? "" : `<small class="om-sous">réussite attendue ${omPct(p.p)}</small>`) + `</span>` +
    `<span><span class="om-cote">Cote ${omCote(p.cote)}</span> ${omBadge(p)}</span></div>`;
}
function omCroisements(f) {
  const s = f.series || {};
  const v = (x) => `<span class="om-buts">${(x || []).join(" · ") || "—"}</span> <small>(moy. ${omFr(omMoy(x))})</small>`;
  return `<div class="om-bloc"><div class="om-bloc-titre">Les 4 croisements (buts par match, du plus ancien au plus récent)</div><div class="om-croix">` +
    `<div><b>Attaque ${omE(f.domicile)} × attaque ${omE(f.exterieur)}</b>${v(s.dom_marques)}<br>${v(s.ext_marques)}</div>` +
    `<div><b>Défense ${omE(f.domicile)} × défense ${omE(f.exterieur)}</b>${v(s.dom_encaisses)}<br>${v(s.ext_encaisses)}</div>` +
    `<div><b>Attaque ${omE(f.domicile)} × défense ${omE(f.exterieur)}</b>${v(s.dom_marques)}<br>${v(s.ext_encaisses)}</div>` +
    `<div><b>Attaque ${omE(f.exterieur)} × défense ${omE(f.domicile)}</b>${v(s.ext_marques)}<br>${v(s.dom_encaisses)}</div>` +
    `</div></div>`;
}
// Derniers matchs des deux équipes (ceux du même lieu, utilisés par le modèle) : date, adversaire, score, résultat.
function omRes(m, e) { return m > e ? ["V", "om-v"] : m < e ? ["D", "om-d"] : ["N", "om-n"]; }
function omJourCourt(iso) {
  const d = new Date(`${iso}T12:00:00`); if (Number.isNaN(d.getTime())) return omE(iso || "");
  return omE(d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" }).replace(/\./g, ""));
}
function omEquipeDerniers(nom, lieu, liste, total) {
  const l = Array.isArray(liste) ? liste : [];
  const moy = (k) => (l.length ? l.reduce((a, x) => a + Number(x[k] || 0), 0) / l.length : NaN);
  const lignes = l.map((x) => {
    const [lettre, cls] = omRes(x.marques, x.encaisses);
    return `<li class="om-dm"><span class="om-dm-date">${omJourCourt(x.date)}</span>` +
      `<span class="om-dm-adv">${omE(x.adversaire || "Adversaire inconnu")}</span>` +
      `<b class="om-dm-score">${Number(x.marques)} – ${Number(x.encaisses)}</b><span class="om-dm-res ${cls}">${lettre}</span></li>`;
  }).join("");
  return `<div class="om-dm-eq"><div class="om-dm-tete"><span class="om-dm-nom">${omE(nom)}</span>` +
    `<span class="om-dm-lieu">${lieu} · ${total || l.length} match${(total || l.length) > 1 ? "s" : ""}</span></div>` +
    (l.length ? `<div class="om-dm-puces"><span>Marque <b>${omFr(moy("marques"))}</b></span><span>Encaisse <b>${omFr(moy("encaisses"))}</b></span></div><ul class="om-dm-liste">${lignes}</ul>`
              : `<p class="om-info">Matchs indisponibles.</p>`) + `</div>`;
}
function omDerniers(f) {
  const d = f.derniers_matchs || {};
  if (!(d.dom && d.dom.length) && !(d.ext && d.ext.length)) return "";
  return `<div class="om-bloc"><div class="om-bloc-titre">Derniers matchs</div><div class="om-dm-grille">` +
    omEquipeDerniers(f.domicile, "À domicile", d.dom, f.n_domicile) + omEquipeDerniers(f.exterieur, "À l'extérieur", d.ext, f.n_exterieur) + `</div></div>`;
}
function omScores(f) {
  const sc = (f.scores_probables || []).map((x) => `${omE(x.score)} (${omPct(x.p)})`).join(" · ");
  return sc ? `<div class="om-bloc"><div class="om-bloc-titre">Scores les plus probables</div><div>${sc}</div></div>` : "";
}
function omCarte(f) {
  const h = omHoraire(f.coup_d_envoi_utc), p = f.principal || {};
  const score = Array.isArray(f.score) ? `${f.score[0]} - ${f.score[1]}` : "";
  const autres = Array.isArray(f.autres) ? f.autres : [];
  const r = Math.round(Number(p.p) * 100);
  const section = document.createElement("section");
  section.className = "ax-carte ax-replie";
  section.setAttribute("aria-expanded", "false");
  section.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match">` +
      `<span class="ax-equipe ax-dom">${omE(f.domicile)}</span>` +
      `<div class="ax-horaire"><strong>${omE(h.heure)}</strong><span>${omE(h.date)}</span></div>` +
      `<span class="ax-equipe ax-ext">${omE(f.exterieur)}</span></div>` +
      `<div class="ax-match-bas"><p class="ax-competition">${omE(String(f.competition || "").replace(/\s+/g, " ").trim())}</p><div class="ax-actions-tete"></div></div>` +
    `</div>` +
    `<div class="om-corps">` +
      (score ? `<div class="om-info">Score final <strong>${omE(score)}</strong></div>` : "") +
      `<div class="om-info"><b>Pari proposé</b></div>` + omLigne(p, f, true) +
      `<div class="om-info">Réussite attendue : <b>${Number.isFinite(r) ? r : "—"} sur 100</b></div>` +
      `<div class="om-jauge" aria-hidden="true"><i style="width:${Number.isFinite(r) ? r : 0}%"></i></div>` +
    `</div>` +
    `<details class="ax-details" open><summary class="ax-summary-cache" tabindex="-1">Détails</summary><div class="ax-details-corps">` +
      omPourquoi(f) +
      `<div class="om-autres"><div class="om-autres-titre">Autres paris possibles</div>` +
        (autres.length ? autres.map((x) => omLigne(x, f, false)).join("") : `<div class="om-info">Aucun autre pari ne remplit les règles.</div>`) + `</div>` +
      omDerniers(f) + omCroisements(f) + omScores(f) +
    `</div></details>`;
  section.addEventListener("click", (e) => {      // carte repliée au départ ; un toucher la déplie ou la replie
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
function omListe(id, liste, vide) {
  const el = document.getElementById(id); if (!el) return;
  el.innerHTML = "";
  if (liste && liste.length) liste.forEach((f) => el.appendChild(omCarte(f)));
  else el.innerHTML = `<p class="om-vide">${omE(vide)}</p>`;
}
function omBilan(b) {
  const ligne = (nom, s) => s && s.regles > 0
    ? `<tr><td>${nom}</td><td>${s.regles}</td><td>${omPct1(s.reussite)}</td><td>${omPct1(s.annonce)}</td><td>${omCote(s.cote_moyenne)}</td><td>${omSigne(s.rendement)}</td></tr>` : "";
  const corps = ligne("Principal", b.principal) + ligne("Autres", b.autres);
  if (!corps) return `<p class="om-info" style="margin:8px 14px">Aucun pari réglé pour l'instant : le tableau « annoncé contre réel » apparaîtra avec les premiers résultats.</p>`;
  return `<table class="om-table"><tr><th>Pari</th><th>Réglés</th><th>Réussite réelle</th><th>Annoncée</th><th>Cote moy.</th><th>Rendement</th></tr>${corps}</table>`;
}
function omAffiche(d) {
  document.getElementById("om-bilan").innerHTML = omBilan(d.bilan || {});
  omListe("om-avenir", d.a_venir, "Aucun pari à venir pour l'instant.");
  const sans = Number(d.sans_pronostic) || 0;
  document.getElementById("om-sans").textContent = sans ? `${sans} autre${sans > 1 ? "s" : ""} match${sans > 1 ? "s" : ""} analysé${sans > 1 ? "s" : ""} sans pari : aucun marché ne remplit les règles (on ne force jamais).` : "";
  omListe("om-encours", d.en_cours, "Aucun match en cours.");
  omListe("om-regles", d.reglees, "Aucun pari réglé pour l'instant.");
  const g = d.genere_le ? new Date(d.genere_le) : null;
  document.getElementById("maj").textContent = g && !Number.isNaN(g.getTime())
    ? `Mis à jour le ${g.toLocaleDateString("fr-FR")} à ${g.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}` : "";
}
function omTheme() {
  const bouton = document.getElementById("ax-bouton-theme"); if (!bouton) return;
  const applique = (nuit) => {
    document.body.classList.toggle("theme-nuit", nuit);
    bouton.textContent = nuit ? "☀" : "☾";
    bouton.setAttribute("aria-label", nuit ? "Activer le mode clair" : "Activer le mode nuit");
  };
  let nuit = false;
  try { nuit = localStorage.getItem(OM_CLE_THEME) === "1"; } catch (e) { /* stockage indisponible */ }
  applique(nuit);
  bouton.addEventListener("click", () => {
    const suivant = !document.body.classList.contains("theme-nuit");
    try { localStorage.setItem(OM_CLE_THEME, suivant ? "1" : "0"); } catch (e) { /* ignoré */ }
    applique(suivant);
  });
}
omTheme();
if (document.getElementById("om-avenir")) {
  fetch(`data/omega/pronostics.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`données omega introuvables (${r.status}) : le moteur n'a pas encore tourné`); return r.json(); })
    .then(omAffiche)
    .catch((e) => { document.getElementById("maj").textContent = "Erreur de chargement : " + e.message; console.error(e); });
}
if (typeof module !== "undefined") module.exports = { omPhrase };
