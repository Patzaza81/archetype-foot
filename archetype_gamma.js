// Page Gamma (moteur Omega V3 : moteur_omega_v3/, depuis le 02/11/2026) : affiche data/gamma/pronostics.json (écrit par moteur_omega_v3.suivi). Lecture seule, aucun calcul métier.
// Même présentation que la page Omega (archetype_omega.js). Les fréquences affichées sont des FRÉQUENCES de scénarios, jamais des probabilités.
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
  if ((r = g.match(/^over_under_(\d+)$/))) return { titre: `${s === "plus" ? "Plus" : "Moins"} de ${r[1]} buts (remboursé si exactement ${r[1]})` };
  if (g === "handicap_0") return { titre: `${s === "domicile" ? dom : ext} gagne (remboursé si match nul)` };
  if (g === "victoire_sans_encaisser_domicile") return { titre: `${dom} gagne sans encaisser` };
  if (g === "victoire_sans_encaisser_exterieur") return { titre: `${ext} gagne sans encaisser` };
  if (g === "score_exact") return { titre: s === "autre" ? "Un autre score (6 buts ou plus pour une équipe)" : `Score exact ${s.replace("-", " - ")}` };
  if ((r = g.match(/^handicap_(-?\d+\.5)$/))) {
    const h = s === "domicile" ? Number(r[1]) : -Number(r[1]), eq = s === "domicile" ? dom : ext;
    const phrase = h > 0 ? (h < 1 ? `${eq} ne perd pas` : `${eq} ne perd pas par ${gaButs(Math.ceil(h))} d'écart ou plus`)
      : (h > -1 ? `${eq} gagne` : `${eq} gagne par ${gaButs(Math.ceil(-h))} d'écart ou plus`);
    return { titre: phrase, reel: `handicap ${h > 0 ? "+" : "−"}${gaVirg(Math.abs(h))}` };
  }
  if ((r = g.match(/^handicap_3issues_(-?\d+)$/))) {
    const k = Number(r[1]);
    const marge = (eq, m) => m >= 1 ? `${eq} gagne par ${gaButs(m)} d'écart ou plus` : (m === 0 ? `${eq} ne perd pas` : `${eq} ne perd pas de plus de ${gaButs(-m)} d'écart`);
    const ex = (eq, n) => `${eq} ${n > 0 ? "gagne" : "perd"} d'exactement ${gaButs(Math.abs(n))} d'écart`;
    const reel = `handicap ${k > 0 ? "+" : "−"}${Math.abs(k)} sur ${dom}`;
    if (s === "1") return { titre: marge(dom, 1 - k), reel };
    if (s === "2") return { titre: marge(ext, k + 1), reel };
    return { titre: ex(dom, -k), reel };
  }
  if (g === "nombre_exact_buts") return { titre: /\+$/.test(s) ? `${gaButs(parseInt(s, 10))} ou plus dans le match` : `Exactement ${gaButs(Number(s))} dans le match` };
  if (s.includes("|")) {
    const [a, b] = s.split("|");
    if (g.startsWith("btts_total_")) return { titre: `${a === "Oui" ? "Les deux équipes marquent" : "Au moins une équipe ne marque pas"} et ${total(g.split("_").pop(), b)}` };
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

// --- Omega V3 : fréquences, paliers de compatibilité, stabilité (spécification Omega V1 §5, §8, §10) ---
function gaEv(p) { return p && p.ev != null && Number.isFinite(Number(p.ev)) ? `EV <b>${gaSigne(p.ev)}</b>` : ""; }
let GA_CLES = [];
let GA_ORDRE = "";
const GA_STATUTS = {
  0: "aucun seuil calibré (jamais 70 % de réussite sur l'archive)", 1: "fréquence robuste sous le seuil du marché", 2: "score exact : jamais retenu",
  3: "à surveiller : aucune cote disponible", 4: "à surveiller : cote trop basse", 5: "à surveiller : même événement qu'un pari retenu", 6: "retenu", 7: "non évalué",
};
function gaStatut(code) { return GA_STATUTS[code] || "—"; }
function gaFreqPari(p, f) {
  if (!p) return "";
  const nv = p.niveaux || {}, st = p.stabilite || {}, dv = p.diversite || {};
  const pal = (nom, k) => {
    const x = nv[k]; if (!x || !x.n) return `<tr><td>${nom}</td><td colspan="2">aucun scénario</td></tr>`;
    return `<tr><td>${nom}</td><td>${x.k} sur ${x.n}</td><td>${gaPct(x.f)}${x.faible ? ' <small>(trop peu représenté)</small>' : ""}</td></tr>`;
  };
  const l = [];
  l.push(`<div class="om-info">Fréquence brute : <b>${p.k} scénarios sur ${p.n}</b> (${gaPct(p.f)}). Une fréquence de scénarios n'est pas une probabilité.</div>`);
  l.push(`<div class="om-info">Fréquence robuste (une observation retirée à la fois) : <b>${gaPct(p.g)}</b> (de ${gaPct(st.f_min)} à ${gaPct(st.f_max)}).</div>`);
  if (p.seuil != null) l.push(`<div class="om-info">Seuil de ce marché appris sur l'archive : <b>${gaPct(p.seuil)}</b>${p.p_calibree != null ? ` · réussite observée sur l'archive à ce niveau, parmi les paris jouables : <b>${gaPct(p.p_calibree)}</b>` : ""}</div>`);
  if (p.cote) l.push(`<div class="om-info">Cote <b>${gaCote(p.cote)}</b> = probabilité implicite ${gaPct(p.p_implicite)}${p.p_implicite_corrigee != null ? ` (${gaPct(p.p_implicite_corrigee)} marge retirée, marge ${gaPct1(p.marge)})` : ""}${p.ev != null ? ` · ${gaEv(p)} <small>(information)</small>` : ""}</div>`);
  l.push(`<table class="om-table"><tr><th>Palier défensif</th><th>Scénarios</th><th>Fréquence</th></tr>` +
    `<tr><td>Brut (tous)</td><td>${p.k} sur ${p.n}</td><td>${gaPct(p.f)}</td></tr>${pal("Strict", "strict")}${pal("Intermédiaire", "intermediaire")}${pal("Élargi", "elargi")}</table>`);
  if (dv.configurations) l.push(`<div class="om-info">Configurations offensives favorables : ${dv.configurations_favorables} sur ${dv.configurations} · plus grande part portée par une seule observation : ${gaPct(dv.part_max_observation)}</div>`);
  if (p.contradiction && p.contradiction.length) l.push(`<div class="om-info"><b>Contradiction</b> : le palier ${p.contradiction.map(gaE).join(", ")} va dans l'autre sens que le brut (passe de l'autre côté de 50 %).</div>`);
  return `<div class="om-pond"><div class="om-pond-t">Fréquences et stabilité</div>${l.join("")}</div>`;
}
function gaFreqCourte(p) {
  const l = [`fréquence robuste ${gaPct(p.g)}`];
  if (p.p_calibree != null) l.push(`réussite observée ${gaPct(p.p_calibree)}`);
  if (p.seuil != null) l.push(`seuil ${gaPct(p.seuil)}`);
  return `<small class="om-sous">${l.join(" · ")}</small>`;
}
function gaLigne(p, f, principal) {
  const ph = gaPhrase(p.cle, f.domicile, f.exterieur);
  return `<div class="om-ligne ${principal ? "om-principal" : ""}"><span>${gaE(ph.titre)}${ph.reel ? `<small class="om-sous">${gaE(ph.reel)}</small>` : ""}` +
    (principal ? `<small class="om-sol" style="--s:${Math.round((Number(p.g) || 0) * 100)}">Fréquence robuste <b>${gaPct(p.g)}</b></small>` : gaFreqCourte(p)) + `</span>` +
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
// Données utilisées (§16.A) : les quatre séquences, rendues telles que le moteur les lit (du plus ancien au plus récent).
function gaSequences(f) {
  const s = f.donnees && f.donnees.sequences; if (!s) return "";
  const fm = (a) => `[${(a || []).join(", ")}]`;
  return `<div class="om-bloc"><div class="om-bloc-titre">Les quatre séquences (${(s.att_a || []).length} matchs au même lieu chacune)</div>` +
    `<div class="om-info">Attaque ${gaE(f.domicile)} (à domicile) = <b>${fm(s.att_a)}</b> · Défense = <b>${fm(s.def_a)}</b></div>` +
    `<div class="om-info">Attaque ${gaE(f.exterieur)} (à l'extérieur) = <b>${fm(s.att_b)}</b> · Défense = <b>${fm(s.def_b)}</b></div>` +
    `<div class="om-info"><small>Source : ${gaE(f.donnees.source || "")}. Les scénarios sont des combinaisons de ces observations, pas des matchs indépendants.</small></div></div>`;
}
// Exploration brute (§16.B) et paliers (§16.C).
function gaExploration(f) {
  const x = f.exploration; if (!x) return "";
  const nv = f.niveaux || {};
  const lignes = (x.top_scores || []).map((s) => `<tr><td>${gaE(s.score.replace("-", " - "))}</td><td>${s.occurrences}</td><td>${gaPct1(s.f)}</td>` +
    ["strict", "intermediaire", "elargi"].map((k) => `<td>${s.par_niveau && s.par_niveau[k] != null ? gaPct1(s.par_niveau[k]) : "—"}</td>`).join("") + `</tr>`).join("");
  const is = x.issues || {};
  const part = (k, nom) => nv[k] ? `${nom} <b>${nv[k].n}</b> (${gaPct(nv[k].part)})${nv[k].faible ? " <small>trop peu représenté</small>" : ""}` : "";
  return `<div class="om-bloc"><div class="om-bloc-titre">Exploration : ${x.combinaisons} scénarios, ${x.scores_distincts} scores distincts</div>` +
    `<div class="om-info">Victoire de ${gaE(f.domicile)} <b>${is.A || 0}</b> · nul <b>${is.N || 0}</b> · victoire de ${gaE(f.exterieur)} <b>${is.B || 0}</b> (sur ${x.combinaisons})</div>` +
    `<div class="om-info">Compatibilité défensive : ${[part("strict", "stricte"), part("intermediaire", "intermédiaire"), part("elargi", "élargie"), part("incompatible", "incompatible")].join(" · ")}</div>` +
    `<table class="om-table"><tr><th>Score</th><th>Occ.</th><th>Brut</th><th>Strict</th><th>Interm.</th><th>Élargi</th></tr>${lignes}</table>` +
    `<div class="om-info"><small>Les trois scores les plus fréquents pèsent ${gaPct(x.concentration_top3)} de la distribution. Un score fréquent n'est jamais un pronostic retenu.</small></div></div>`;
}
function gaConclusion(f) {
  const c = f.conclusion; if (!c || !c.length) return "";
  return `<div class="om-bloc"><div class="om-bloc-titre">Conclusion</div>${c.map((x) => `<div class="om-info">${gaE(x).replace(/·/g, "–")}</div>`).join("")}</div>`;
}
// La raison gelée cite parfois la clé technique d'un autre marché : on la remplace par sa phrase.
function gaRaison(r, f) {
  return String(r || "").replace(/(même événement que )([a-z0-9_.\-]+)\|(\S+)/i, (m, d, g, s) => d + gaPhrase([g, s], f.domicile, f.exterieur).titre);
}
function gaSurveiller(f) {
  const l = f.a_surveiller || []; if (!l.length) return "";
  return `<div class="om-autres"><div class="om-autres-titre">À surveiller (seuil atteint, pari non jouable)</div>` +
    l.slice(0, 12).map((x) => `<div class="om-info">${gaE(gaPhrase(x.cle, f.domicile, f.exterieur).titre)} — ${gaE(gaRaison(x.raison, f))}</div>`).join("") + (l.length > 12 ? `<div class="om-info">… et ${l.length - 12} autres.</div>` : "") + `</div>`;
}
// Tous les marchés explorés (§16.D) : aucun marché n'est caché, rejetés et raison comprise. Lignes positionnelles : voir moteur_omega_v3/suivi.py (_compact).
function gaTousMarches(f) {
  const t = f.tous_marches; if (!t || !t.length) return "";
  if (f.ordre_marches && GA_ORDRE && f.ordre_marches !== GA_ORDRE) return `<details class="ax-calcul"><summary>Tous les marchés explorés</summary><p class="om-info">Liste des marchés d'une autre version du moteur : affichage indisponible pour ce pronostic.</p></details>`;
  const nv = f.niveaux || {}, n = f.exploration ? f.exploration.combinaisons : 0;
  const ordre = t.map((r, i) => i).sort((a, b) => (t[b][5] - t[a][5]) || (t[b][0] - t[a][0]) || (a - b));
  const corps = ordre.map((i) => {
    const r = t[i], c = GA_CLES[i]; if (!c) return "";
    const pc = (k, tot) => tot ? gaPct(k / tot) : "—";
    const st = r[10] === 1 && r[12] != null ? `fréquence robuste ${gaPct(r[5])} sous le seuil ${gaPct(r[12])}` : gaStatut(r[10]);
    return `<tr><td>${gaE(gaPhrase(c, f.domicile, f.exterieur).titre)}</td><td>${pc(r[0], n)}</td><td>${pc(r[2], (nv.strict || {}).n)}</td><td>${pc(r[3], (nv.intermediaire || {}).n)}</td><td>${pc(r[4], (nv.elargi || {}).n)}</td>` +
      `<td>${gaPct(r[6])}–${gaPct(r[7])}${r[9] ? " ⚠" : ""}</td><td>${r[11] ? gaCote(r[11]) : "—"}</td><td>${gaE(st)}</td></tr>`;
  }).join("");
  return `<details class="ax-calcul"><summary>Tous les marchés explorés (${t.length})</summary><div class="ax-details-corps" style="overflow-x:auto">` +
    `<p class="om-info">Fréquences de scénarios, triées par fréquence robuste. ⚠ = le marché disparaît si on retire une seule observation.</p>` +
    `<table class="om-table"><tr><th>Marché</th><th>Brut</th><th>Strict</th><th>Interm.</th><th>Élargi</th><th>Stabilité</th><th>Cote</th><th>Statut</th></tr>${corps}</table></div></details>`;
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
function gaPourquoiCourt(p, f) {
  const phrase = gaPhrasePari(p, f);
  return phrase ? `<div class="om-pq"><p class="om-pq-txt">${phrase}</p></div>` : "";
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
      gaPourquoiCourt(p, f) + gaFreqPari(p, f) +
    `</div>` +
    `<details class="ax-details" open><summary class="ax-summary-cache" tabindex="-1">Détails</summary><div class="ax-details-corps">` +
      `<div class="om-autres"><div class="om-autres-titre">Autres paris retenus (du plus au moins fiable)</div>` +
        (autres.length ? autres.map((x) => gaLigne(x, f, false)).join("") : `<div class="om-info">Aucun autre marché ne remplit les règles.</div>`) + `</div>` +
      gaSurveiller(f) + gaSequences(f) + gaDerniers(f) + gaExploration(f) + gaConclusion(f) + gaTousMarches(f) +
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
    ? `<tr><td>${nom}</td><td>${s.regles}</td><td>${gaPct1(s.reussite)}</td><td>${s.annonce != null ? gaPct1(s.annonce) : "—"}</td><td>${gaCote(s.cote_moyenne)}</td></tr>` : "";
  const corps = ligne("Principal", b.principal) + ligne("Autres", b.autres);
  if (!corps) return `<p class="om-info" style="margin:8px 14px">Aucun pari réglé pour l'instant : le tableau « annoncé contre réel » apparaîtra avec les premiers résultats.</p>`;
  return `<table class="om-table"><tr><th>Pari</th><th>Réglés</th><th>Réussite réelle</th><th>Réussite observée à l'apprentissage</th><th>Cote moy.</th></tr>${corps}</table>`;
}
function gaAffiche(d) {
  GA_CLES = d.cles_marches || []; GA_ORDRE = d.ordre_marches || "";
  document.getElementById("om-bilan").innerHTML = gaBilan(d.bilan || {});
  gaListe("om-avenir", d.a_venir, "Aucun pari à venir pour l'instant.");
  const sans = Number(d.sans_pronostic) || 0, exclus = Number(d.nb_exclus) || 0;
  const raisons = Object.entries(d.exclus || {}).map(([r, n]) => `${gaE(r)} : ${n}`).join(" · ");
  document.getElementById("om-sans").innerHTML = (sans ? `${sans} autre${sans > 1 ? "s" : ""} match${sans > 1 ? "s" : ""} analysé${sans > 1 ? "s" : ""} sans pari : aucun marché ne remplit les règles (le moteur ne force jamais une sélection).` : "") +
    (exclus ? `${sans ? "<br>" : ""}${exclus} match${exclus > 1 ? "s" : ""} non analysé${exclus > 1 ? "s" : ""} (${raisons}) : le moteur n'invente aucune donnée manquante.` : "");
  gaListe("om-encours", d.en_cours, "Aucun match en cours.");
  gaListe("om-regles", d.reglees, "Aucun pari réglé pour l'instant.");
  const g = d.derniere_analyse || d.genere_le ? new Date(d.derniere_analyse || d.genere_le) : null;
  document.getElementById("maj").textContent = g && !Number.isNaN(g.getTime())
    ? `Dernière analyse du moteur Gamma (Omega V3) : ${g.toLocaleDateString("fr-FR")} à ${g.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}` : "";
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
  fetch(`data/gamma/pronostics.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`données gamma introuvables (${r.status}) : le moteur n'a pas encore tourné`); return r.json(); })
    .then(gaAffiche)
    .catch((e) => { document.getElementById("maj").textContent = "Erreur de chargement : " + e.message; console.error(e); });
}
if (typeof module !== "undefined") module.exports = { gaPhrase, gaCarte, gaEv, gaFreqPari, gaStatut, gaSequences, gaExploration, gaTousMarches, gaAffiche, gaSurveiller };
