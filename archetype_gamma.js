// Page Gamma (moteur DC : moteur_dc/) : affiche data/dc/pronostics.json (écrit par moteur_dc.suivi). Lecture seule, aucun calcul métier.
// Même présentation que la page Omega (archetype_omega.js), adaptée aux données du moteur Gamma.
"use strict";
const GA_CLE_THEME = "archetype_theme_nuit";

function gaE(x) {
  return String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function gaCote(x) { const n = Number(x); return x != null && Number.isFinite(n) && n > 1 ? n.toFixed(2).replace(".", ",") : "—"; }
function gaPct(x) { const n = Number(x); return Number.isFinite(n) ? Math.round(n * 100) + " %" : "—"; }
function gaPct1(x) { const n = Number(x); return Number.isFinite(n) ? (n * 100).toFixed(1).replace(".", ",") + " %" : "—"; }
function gaSigne(x) { const n = Number(x); return Number.isFinite(n) ? (n >= 0 ? "+" : "−") + Math.abs(n * 100).toFixed(1).replace(".", ",") + " %" : "—"; }
function gaFr(x, d) { const n = Number(x); return Number.isFinite(n) ? n.toFixed(d == null ? 1 : d).replace(".", ",") : "—"; }
function gaDate(iso) {
  const d = new Date(`${iso}T12:00:00`); if (Number.isNaN(d.getTime())) return iso || "";
  const t = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
function gaHoraire(ko) {          // coup d'envoi UTC -> heure du Cameroun (UTC+1)
  const d = ko ? new Date(ko) : null; if (!d || Number.isNaN(d.getTime())) return { heure: "—", date: "" };
  const c = new Date(d.getTime() + 3600000);
  return { heure: c.toISOString().slice(11, 16).replace(":", "h"), date: gaDate(c.toISOString().slice(0, 10)) };
}
const gaButs = (n) => `${n} but${n > 1 ? "s" : ""}`;
const gaVirg = (t) => String(t).replace(".", ",");

// Phrase du pari à partir de sa clé (groupe, sélection), avec le nom des équipes et la valeur réelle en buts entiers.
function gaPhrase(cle, dom, ext) {
  const g = String(cle[0]), s = String(cle[1]);
  const res = { "1": `Victoire ${dom}`, "N": "Match nul", "2": `Victoire ${ext}` };
  const dc = { "1N": `${dom} ou match nul`, "N2": `Match nul ou ${ext}`, "12": `${dom} ou ${ext} (pas de match nul)` };
  const total = (ligne, sens) => {
    const l = Number(ligne);
    return sens === "plus" ? `au moins ${gaButs(Math.ceil(l))} dans le match` : (Math.floor(l) ? `pas plus de ${gaButs(Math.floor(l))} dans le match` : "aucun but dans le match");
  };
  let r;
  if (g === "1x2") return { titre: res[s] };
  if (g === "double_chance") return { titre: dc[s] };
  if (g === "btts") return { titre: s === "Oui" ? "Les deux équipes marquent" : "Au moins une équipe ne marque pas" };
  if (g === "multigoal") return { titre: { "0-1": "0 ou 1 but dans le match", "2-3": "2 ou 3 buts dans le match", "4+": "4 buts ou plus dans le match" }[s] || `${g} ${s}` };
  if ((r = g.match(/^cages_inviolees_(domicile|exterieur)$/))) {
    const eq = r[1] === "domicile" ? dom : ext;
    return { titre: s === "oui" ? `${eq} n'encaisse aucun but` : `${eq} encaisse au moins 1 but` };
  }
  if ((r = g.match(/^over_under_(domicile|exterieur)_(\d+\.5)$/))) {
    const eq = r[1] === "domicile" ? dom : ext, l = Number(r[2]);
    return { titre: `${s === "plus" ? "Plus" : "Moins"} de ${gaVirg(r[2])} buts pour ${eq}`,
      reel: s === "plus" ? `${eq} marque au moins ${gaButs(Math.ceil(l))}` : (Math.floor(l) ? `${eq} marque au plus ${gaButs(Math.floor(l))}` : `${eq} ne marque pas`) };
  }
  if ((r = g.match(/^over_under_(\d+\.5)$/))) return { titre: `${s === "plus" ? "Plus" : "Moins"} de ${gaVirg(r[1])} buts`, reel: total(r[1], s) };
  if ((r = g.match(/^handicap_(-?\d+\.5)$/))) {
    const h = s === "domicile" ? Number(r[1]) : -Number(r[1]), eq = s === "domicile" ? dom : ext;
    const phrase = h > 0 ? (h < 1 ? `${eq} ne perd pas` : `${eq} ne perd pas par ${gaButs(Math.ceil(h))} d'écart ou plus`)
      : (h > -1 ? `${eq} gagne` : `${eq} gagne par ${gaButs(Math.ceil(-h))} d'écart ou plus`);
    return { titre: phrase, reel: `handicap ${h > 0 ? "+" : "−"}${gaVirg(Math.abs(h))}` };
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
function gaBadge(p) {
  return p && p.resultat ? `<span class="om-badge om-${gaE(p.resultat)}">${p.resultat === "WIN" ? "GAGNÉ" : "PERDU"}</span>` : "";
}
function gaMoy(v) { return Array.isArray(v) && v.length ? v.reduce((a, b) => a + b, 0) / v.length : NaN; }

// « Pourquoi ce pari » : quelques paramètres du Module 1 des deux équipes (calculés en Python).
function gaPourquoi(f) {
  const e = f.equipes || {}, l = [];
  const t = (x, nom) => x ? `${gaE(nom)} : ${x.position}e (${x.Pts} pts en ${x.J} matchs), forme ${gaFr(x.forme_ppm, 2)} pt par match, profil ${gaE(x.profil || "—")}` : "";
  if (e.dom) l.push(t(e.dom, f.domicile));
  if (e.ext) l.push(t(e.ext, f.exterieur));
  return l.length ? `<div class="om-pourquoi">${l.map((x) => `<div>${x}</div>`).join("")}</div>` : "";
}
// Probabilité du modèle (Dixon-Coles du championnat entier) et avertissement Wilson (calculés en Python, moteur_dc/selecteur.py).
function gaProba(p) {
  const s = Number(p && p.p);
  return Number.isFinite(s) ? `<small class="om-sol" style="--s:${Math.max(0, Math.min(100, Math.round(s * 100)))}">Probabilité <b>${Math.round(s * 100)} %</b></small>` : "";
}
function gaAlerte(p) {
  return p && p.avertissement ? `<small class="om-alerte">Confiance réduite : le modèle sort de ce que montrent les matchs</small>` : "";
}
// Preuve du pari : base du championnat, avantage (Edge), seuil du marché, matchs comparables.
function gaPreuve(p) {
  if (!p) return "";
  const pr = p.preuve || {}, l = [];
  if (p.base != null) l.push(`Base du championnat <b>${gaPct(p.base)}</b> · avantage <b>${gaSigne(p.edge)}</b>`);
  if (p.seuil != null) l.push(`Seuil de ce marché : <b>${gaPct(p.seuil)}</b>`);
  if (pr.n) l.push(`Matchs comparables : <b>${pr.k} sur ${pr.n}</b>` + (Array.isArray(pr.wilson) ? ` (intervalle ${gaPct(pr.wilson[0])} – ${gaPct(pr.wilson[1])})` : ""));
  return l.length ? `<div class="om-pond"><div class="om-pond-t">Preuve</div>${l.map((x) => `<div class="om-info">${x}</div>`).join("")}</div>` : "";
}
function gaLigne(p, f, principal) {
  const ph = gaPhrase(p.cle, f.domicile, f.exterieur);
  return `<div class="om-ligne ${principal ? "om-principal" : ""}"><span>${gaE(ph.titre)}${ph.reel ? `<small class="om-sous">${gaE(ph.reel)}</small>` : ""}` +
    gaProba(p) + gaAlerte(p) + `</span>` +
    `<span><span class="om-cote">Cote ${gaCote(p.cote)}</span> ${gaBadge(p)}</span></div>`;
}
// Derniers matchs des deux équipes (à domicile pour l'une, à l'extérieur pour l'autre : ceux qu'utilise le modèle) : date, adversaire, score, résultat.
function gaRes(m, e) { return m > e ? ["V", "om-v"] : m < e ? ["D", "om-d"] : ["N", "om-n"]; }
function gaJourCourt(iso) {
  const d = new Date(`${iso}T12:00:00`); if (Number.isNaN(d.getTime())) return gaE(iso || "");
  return gaE(d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" }).replace(/\./g, ""));
}
function gaEquipeDerniers(nom, lieu, liste, total, domicile) {
  const l = Array.isArray(liste) ? liste : [];
  const moy = (k) => (l.length ? l.reduce((a, x) => a + Number(x[k] || 0), 0) / l.length : NaN);
  const lignes = l.map((x) => {
    const [lettre, cls] = gaRes(x.marques, x.encaisses);
    const m = Number(x.marques), e = Number(x.encaisses);
    // Score dans l'ordre d'un match : l'équipe qui reçoit en premier. Les buts de l'équipe affichée sont en gras.
    const score = domicile ? `<b>${m}</b> – ${e}` : `${e} – <b>${m}</b>`;
    return `<li class="om-dm"><span class="om-dm-date">${gaJourCourt(x.date)}</span>` +
      `<span class="om-dm-adv">${gaE(x.adversaire || "Adversaire inconnu")}</span>` +
      `<span class="om-dm-score">${score}</span><span class="om-dm-res ${cls}">${lettre}</span></li>`;
  }).join("");
  return `<div class="om-dm-eq"><div class="om-dm-tete"><span class="om-dm-nom">${gaE(nom)}</span>` +
    `<span class="om-dm-lieu">${lieu} · ${total || l.length} match${(total || l.length) > 1 ? "s" : ""}</span></div>` +
    (l.length ? `<div class="om-dm-puces"><span>Marque <b>${gaFr(moy("marques"))}</b></span><span>Encaisse <b>${gaFr(moy("encaisses"))}</b></span></div><ul class="om-dm-liste">${lignes}</ul>`
              : `<p class="om-info">Matchs indisponibles.</p>`) + `</div>`;
}
function gaDerniers(f) {
  const d = f.derniers_matchs || {};
  if (!(d.dom && d.dom.length) && !(d.ext && d.ext.length)) return "";
  return `<div class="om-bloc"><div class="om-bloc-titre">Derniers matchs</div><div class="om-dm-grille">` +
    gaEquipeDerniers(f.domicile, "À domicile", d.dom, f.n_domicile, true) + gaEquipeDerniers(f.exterieur, "À l'extérieur", d.ext, f.n_exterieur, false) + `</div></div>`;
}
function gaScores(f) {
  const sc = (f.scores_probables || []).map((x) => `${gaE(x.score)} (${gaPct(x.p)})`).join(" · ");
  return sc ? `<div class="om-bloc"><div class="om-bloc-titre">Scores les plus probables</div><div>${sc}</div></div>` : "";
}
// Phrase vraie, propre au type de pari : simple décompte sur les derniers matchs affichés (aucune estimation).
const gaN = (liste, test) => liste.filter(test).length;
function gaPhrasePari(p, f) {
  const d = f.derniers_matchs, cle = Array.isArray(p.cle) ? p.cle : [];
  if (!d || !d.dom || !d.ext || !d.dom.length || !d.ext.length) return "";
  const g = String(cle[0] || ""), s = String(cle[1] || ""), D = d.dom, X = d.ext, nd = D.length, nx = X.length;
  const dom = gaE(f.domicile), ext = gaE(f.exterieur);
  const b = (k, n) => `<b>${k} sur ${n}</b>`;
  const dd = (t) => b(gaN(D, t), nd), xx = (t) => b(gaN(X, t), nx);
  const tot = (x) => x.marques + x.encaisses;
  let m = g.match(/^over_under_(\d+(?:\.\d+)?)$/);
  if (m) {
    const k = Math.floor(Number(m[1])), plus = s === "plus";
    const t = plus ? (x) => tot(x) > k : (x) => tot(x) <= k;
    const txt = plus ? `au moins ${k + 1} but${k + 1 > 1 ? "s" : ""}` : (k === 0 ? "aucun but" : `${k} but${k > 1 ? "s" : ""} ou moins`);
    return `Matchs terminés avec ${txt} : ${dd(t)} pour ${dom} à domicile, ${xx(t)} pour ${ext} à l'extérieur.`;
  }
  m = g.match(/^over_under_(domicile|exterieur)_(\d+(?:\.\d+)?)$/);
  if (m) {
    const k = Math.floor(Number(m[2])), plus = s === "plus", home = m[1] === "domicile";
    const txt = plus ? `au moins ${k + 1} but${k + 1 > 1 ? "s" : ""}` : (k === 0 ? "aucun but" : `${k} but${k > 1 ? "s" : ""} ou moins`);
    const own = plus ? (x) => x.marques > k : (x) => x.marques <= k, opp = plus ? (x) => x.encaisses > k : (x) => x.encaisses <= k;
    const [eq, lq, el, ll, nm] = home ? [dom, "à domicile", ext, "à l'extérieur", 0] : [ext, "à l'extérieur", dom, "à domicile", 1];
    const L1 = home ? D : X, L2 = home ? X : D;
    return `${eq} a marqué ${txt} dans ${b(gaN(L1, own), L1.length)} de ses derniers matchs ${lq} ; ${el} en a encaissé ${plus ? "autant" : "aussi peu"} dans ${b(gaN(L2, opp), L2.length)} ${ll === "à l'extérieur" ? "à l'extérieur" : "à domicile"}.`;
  }
  if (g === "btts") {
    const oui = s === "Oui", t = oui ? (x) => x.marques > 0 && x.encaisses > 0 : (x) => x.marques === 0 || x.encaisses === 0;
    return `${oui ? "Les deux équipes ont marqué" : "Une équipe au moins est restée à zéro"} dans ${dd(t)} matchs de ${dom} à domicile et ${xx(t)} matchs de ${ext} à l'extérieur.`;
  }
  if (g === "cages_inviolees_domicile" || g === "cages_inviolees_exterieur") {
    const home = g.endsWith("domicile"), oui = s === "oui";
    const [T, LT, A, LA] = home ? [dom, D, ext, X] : [ext, X, dom, D];
    const lieuT = home ? "à domicile" : "à l'extérieur", lieuA = home ? "à l'extérieur" : "à domicile";
    const tn = oui ? (x) => x.encaisses === 0 : (x) => x.encaisses > 0, an = oui ? (x) => x.marques === 0 : (x) => x.marques > 0;
    return `${T} ${oui ? "n'a pas encaissé" : "a encaissé"} dans ${b(gaN(LT, tn), LT.length)} de ses matchs ${lieuT} ; ${A} ${oui ? "n'a pas marqué" : "a marqué"} dans ${b(gaN(LA, an), LA.length)} de ses matchs ${lieuA}.`;
  }
  const v = (x) => x.marques > x.encaisses, nul = (x) => x.marques === x.encaisses, dft = (x) => x.marques < x.encaisses;
  const de = (k, n) => `<b>${k}</b> de ses ${n} derniers`, des = (k, n) => `<b>${k}</b> des ${n} siens`;
  if (g === "1x2" && s === "1") return `${dom} a gagné ${de(gaN(D, v), nd)} matchs à domicile ; ${ext} en a perdu ${des(gaN(X, dft), nx)} à l'extérieur.`.replace(" en a perdu", " a perdu").replace(/ des (\d+) siens/, " des $1 siens");
  if (g === "1x2" && s === "2") return `${ext} a gagné ${de(gaN(X, v), nx)} matchs à l'extérieur ; ${dom} a perdu ${des(gaN(D, dft), nd)} à domicile.`;
  if (g === "1x2" && s === "N") return `Match nul dans ${dd(nul)} matchs de ${dom} à domicile et ${xx(nul)} matchs de ${ext} à l'extérieur.`;
  if (g === "double_chance" && s === "1N") return `${dom} n'a pas perdu dans ${dd((x) => !dft(x))} de ses matchs à domicile ; ${ext} n'a pas gagné dans ${xx((x) => !v(x))} des siens à l'extérieur.`;
  if (g === "double_chance" && s === "N2") return `${ext} n'a pas perdu dans ${xx((x) => !dft(x))} de ses matchs à l'extérieur ; ${dom} n'a pas gagné dans ${dd((x) => !v(x))} des siens à domicile.`;
  if (g === "double_chance" && s === "12") return `Match décidé (sans nul) dans ${dd((x) => !nul(x))} matchs de ${dom} à domicile et ${xx((x) => !nul(x))} matchs de ${ext} à l'extérieur.`;
  m = g.match(/^handicap_(-?\d+(?:\.\d+)?)$/);
  if (m && (s === "domicile" || s === "exterieur")) {
    const home = s === "domicile", h = home ? Number(m[1]) : -Number(m[1]);
    const t = Math.floor(-h) + 1;                       // l'équipe soutenue doit avoir une marge >= t
    const mq = (x) => x.marques - x.encaisses;
    const verbe = t >= 2 ? `a gagné d'au moins ${t} buts` : t === 1 ? "a gagné" : t === 0 ? "n'a pas perdu" : `n'a pas perdu de ${1 - t} buts ou plus`;
    const u = -t, verbeA = u <= -2 ? `a perdu d'au moins ${-u} buts` : u === -1 ? "a perdu" : u === 0 ? "n'a pas gagné" : `n'a pas gagné de ${u + 1} buts ou plus`;
    const [T, LT, lt, A, LA, la] = home ? [dom, D, "à domicile", ext, X, "à l'extérieur"] : [ext, X, "à l'extérieur", dom, D, "à domicile"];
    const okT = gaN(LT, (x) => mq(x) >= t), okA = gaN(LA, (x) => mq(x) <= u);
    return `${T} ${verbe} dans ${b(okT, LT.length)} de ses matchs ${lt} ; ${A} ${verbeA} dans ${b(okA, LA.length)} des siens ${la}.`;
  }
  const c = f.pari_sur_derniers;
  if (c && c.dom && c.ext && c.dom.n && c.ext.n) {
    return `Les deux conditions du pari réunies : ${b(c.dom.ok, c.dom.n)} matchs de ${dom} à domicile, ${b(c.ext.ok, c.ext.n)} matchs de ${ext} à l'extérieur.`;
  }
  return "";
}
// Cercle du pourcentage (le plus prudent des deux : modèle ou cote) + la phrase propre au type de pari.
function gaPourquoiCourt(p, f) {
  const anneau = "";                                                // 28/10/2026 (Patrick) : le pourcentage du modèle dans le cercle ne s'affiche plus ; seule la Solidité reste
  const phrase = gaPhrasePari(p, f);
  // Buts attendus des deux équipes (c'est ce chiffre, croisé avec la défense adverse, qui décide les paris sur les buts) : juste sous le pari, plus dans les détails.
  const ba = f.buts_attendus || {};
  const attendus = ba.dom != null && ba.ext != null && Number.isFinite(Number(ba.dom)) && Number.isFinite(Number(ba.ext))
    ? `<span class="om-attendus">Buts attendus : <b>${gaE(f.domicile)} ${gaFr(ba.dom)}</b> – <b>${gaFr(ba.ext)} ${gaE(f.exterieur)}</b></span>` : "";
  return anneau || phrase || attendus ? `<div class="om-pq">${anneau}<p class="om-pq-txt">${attendus}${phrase}</p></div>` : "";
}
function gaCarte(f) {
  const h = gaHoraire(f.coup_d_envoi_utc), p = f.principal || {};
  const score = Array.isArray(f.score) ? `${f.score[0]} - ${f.score[1]}` : "";
  const autres = Array.isArray(f.autres) ? f.autres : [];
  const section = document.createElement("section");
  section.className = "ax-carte ax-replie";
  section.setAttribute("aria-expanded", "false");
  section.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match">` +
      `<span class="ax-equipe ax-dom">${gaE(f.domicile)}</span>` +
      `<div class="ax-horaire"><strong>${gaE(h.heure)}</strong><span>${gaE(h.date)}</span></div>` +
      `<span class="ax-equipe ax-ext">${gaE(f.exterieur)}</span></div>` +
      `<div class="ax-match-bas"><p class="ax-competition">${gaE(String(f.competition || "").replace(/\s+/g, " ").trim())}</p><div class="ax-actions-tete"></div></div>` +
    `</div>` +
    `<div class="om-corps">` +
      (score ? `<div class="om-info">Score final <strong>${gaE(score)}</strong></div>` : "") +
      `<div class="om-info"><b>Pari proposé</b></div>` + gaLigne(p, f, true) +
      gaPourquoiCourt(p, f) + gaPreuve(p) +
    `</div>` +
    `<details class="ax-details" open><summary class="ax-summary-cache" tabindex="-1">Détails</summary><div class="ax-details-corps">` +
      gaPourquoi(f) +
      `<div class="om-autres"><div class="om-autres-titre">Autres paris possibles</div>` +
        (autres.length ? autres.map((x) => gaLigne(x, f, false)).join("") : `<div class="om-info">Aucun autre pari ne remplit les règles.</div>`) + `</div>` +
      gaDerniers(f) + gaScores(f) +
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
function gaListe(id, liste, vide) {
  const el = document.getElementById(id); if (!el) return;
  el.innerHTML = "";
  if (liste && liste.length) liste.forEach((f) => el.appendChild(gaCarte(f)));
  else el.innerHTML = `<p class="om-vide">${gaE(vide)}</p>`;
}
function gaBilan(b) {
  const ligne = (nom, s) => s && s.regles > 0
    ? `<tr><td>${nom}</td><td>${s.regles}</td><td>${gaPct1(s.reussite)}</td><td>${gaPct1(s.annonce)}</td><td>${gaCote(s.cote_moyenne)}</td></tr>` : "";
  const corps = ligne("Principal", b.principal) + ligne("Autres", b.autres);
  if (!corps) return `<p class="om-info" style="margin:8px 14px">Aucun pari réglé pour l'instant : le tableau « annoncé contre réel » apparaîtra avec les premiers résultats.</p>`;
  return `<table class="om-table"><tr><th>Pari</th><th>Réglés</th><th>Réussite réelle</th><th>Annoncée</th><th>Cote moy.</th></tr>${corps}</table>`;
}
function gaAffiche(d) {
  document.getElementById("om-bilan").innerHTML = gaBilan(d.bilan || {});
  gaListe("om-avenir", d.a_venir, "Aucun pari à venir pour l'instant.");
  const sans = Number(d.sans_pronostic) || 0;
  document.getElementById("om-sans").textContent = sans ? `${sans} autre${sans > 1 ? "s" : ""} match${sans > 1 ? "s" : ""} analysé${sans > 1 ? "s" : ""} sans pari : aucun marché ne remplit les règles (on ne force jamais).` : "";
  gaListe("om-encours", d.en_cours, "Aucun match en cours.");
  gaListe("om-regles", d.reglees, "Aucun pari réglé pour l'instant.");
  const g = d.genere_le ? new Date(d.genere_le) : null;
  document.getElementById("maj").textContent = g && !Number.isNaN(g.getTime())
    ? `Mis à jour le ${g.toLocaleDateString("fr-FR")} à ${g.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}` : "";
}
function gaTheme() {
  const bouton = document.getElementById("ax-bouton-theme"); if (!bouton) return;
  const applique = (nuit) => {
    document.body.classList.toggle("theme-nuit", nuit);
    bouton.textContent = nuit ? "☀" : "☾";
    bouton.setAttribute("aria-label", nuit ? "Activer le mode clair" : "Activer le mode nuit");
  };
  let nuit = false;
  try { nuit = localStorage.getItem(GA_CLE_THEME) === "1"; } catch (e) { /* stockage indisponible */ }
  applique(nuit);
  bouton.addEventListener("click", () => {
    const suivant = !document.body.classList.contains("theme-nuit");
    try { localStorage.setItem(GA_CLE_THEME, suivant ? "1" : "0"); } catch (e) { /* ignoré */ }
    applique(suivant);
  });
}
gaTheme();
if (document.getElementById("om-avenir")) {
  fetch(`data/dc/pronostics.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`données gamma introuvables (${r.status}) : le moteur n'a pas encore tourné`); return r.json(); })
    .then(gaAffiche)
    .catch((e) => { document.getElementById("maj").textContent = "Erreur de chargement : " + e.message; console.error(e); });
}
if (typeof module !== "undefined") module.exports = { gaPhrase, gaPreuve, gaCarte };
