// Page V : affiche data/v/pronostics_v.json (écrit par moteur_v.execution). Lecture seule, aucun calcul métier.
"use strict";
const CLE_THEME_NUIT_V = "archetype_theme_nuit";

function mvEchappe(x) {
  return String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function mvCote(x) { const n = Number(x); return Number.isFinite(n) ? n.toFixed(2).replace(".", ",") : "—"; }
function mvPct(x, signe) {
  const n = Number(x); if (!Number.isFinite(n)) return "—";
  const t = Math.abs(n * 100).toFixed(1).replace(".", ",") + " %";
  return signe ? (n >= 0 ? "+" : "−") + t : t;
}
function mvPct0(x) { const n = Number(x); return Number.isFinite(n) ? Math.round(n * 100) + " %" : "n/d"; }
function mvUnites(x) {
  const n = Number(x); if (!Number.isFinite(n)) return "—";
  return `${n >= 0 ? "+" : "−"}${Math.abs(n).toFixed(2).replace(".", ",")} u`;
}
function mvDate(iso) {
  const d = new Date(`${iso}T12:00:00`); if (Number.isNaN(d.getTime())) return iso;
  const t = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
function mvHoraire(ko) {          // coup d'envoi UTC -> heure du Cameroun (UTC+1)
  const d = ko ? new Date(ko) : null; if (!d || Number.isNaN(d.getTime())) return { heure: "—", date: "" };
  const c = new Date(d.getTime() + 3600000);
  return { heure: c.toISOString().slice(11, 16).replace(":", "h"), date: mvDate(c.toISOString().slice(0, 10)) };
}
function mvMarche(marche, dom0, ext0) {
  const m = String(marche || ""), dom = dom0 || "Domicile", ext = ext0 || "Extérieur";
  const virg = (t) => t.replace(/(\d)\.(\d)/g, "$1,$2");
  let r;
  if ((r = m.match(/^1X2 - (1|X|2)$/))) return r[1] === "1" ? `Victoire ${dom}` : r[1] === "X" ? "Match nul" : `Victoire ${ext}`;
  if ((r = m.match(/^Double chance - (1X|X2|12)$/))) return r[1] === "1X" ? `${dom} ou match nul` : r[1] === "X2" ? `Match nul ou ${ext}` : `${dom} ou ${ext} (pas de nul)`;
  if ((r = m.match(/^Cage inviolée - (Domicile|Extérieur)$/))) return `${r[1] === "Domicile" ? dom : ext} garde sa cage inviolée`;
  if ((r = m.match(/^Encaisse au moins (\d+) but - (Domicile|Extérieur)$/))) return `${r[2] === "Domicile" ? dom : ext} encaisse au moins ${r[1]} but`;
  if (m === "BTTS - oui") return "Les deux équipes marquent";
  if (m === "BTTS - non") return "Une des deux équipes ne marque pas";
  if ((r = m.match(/^Handicap (.+) - (Domicile|Extérieur)$/))) {      // ligne affichée = ligne du domicile ; l'extérieur reçoit l'inverse
    const x = r[2] === "Domicile" ? Number(r[1]) : -Number(r[1]);
    const eq = r[2] === "Domicile" ? dom : ext, mm = Math.floor(-x) + 1, b = (n) => `${n} but${n > 1 ? "s" : ""}`;
    const sens = mm >= 1 ? `${eq} gagne${mm > 1 ? ` par ${b(mm)} d'écart ou plus` : ""}` : mm === 0 ? `${eq} ne perd pas` : `${eq} ne perd pas par ${b(1 - mm)} d'écart ou plus`;
    return `${sens} (handicap ${x > 0 ? "+" : x < 0 ? "−" : ""}${virg(String(Math.abs(x)))})`;
  }
  if ((r = m.match(/^(Plus|Moins) de (.+) buts - (Domicile|Extérieur)$/))) return phraseButsEquipe(r[3] === "Domicile" ? dom : ext, r[1] === "Plus" ? "over" : "under", r[2]);
  if ((r = m.match(/^(Plus|Moins) de (.+) buts$/))) return phraseTotalButs(r[1] === "Plus" ? "over" : "under", r[2]);
  return virg(m);
}
function mvNiveau(n) { return mvVerdict(n); }
function mvBadge(p) {
  return p && p.resultat ? `<span class="mv-badge mv-${mvEchappe(p.resultat)}">${p.resultat === "WIN" ? "GAGNÉ" : "PERDU"}</span>` : "";
}
// Le mot décrit la CHANCE que le pari passe, jamais sa rentabilité (un pari très probable peut être mal payé : voir mvChance).
const MV_VERDICT = { "SÛR": ["TRÈS PROBABLE", "SUR"], "MOYEN": ["PROBABLE", "MOYEN"], "RISQUÉ": ["INCERTAIN", "RISQUE"] };
function mvVerdict(n) { const v = MV_VERDICT[n] || ["NON ÉVALUÉ", "NC"]; return `<span class="mv-niv mv-niv-${v[1]}">${v[0]}</span>`; }
function mvFr(x, d) { const n = Number(x); return Number.isFinite(n) ? n.toFixed(d == null ? 1 : d).replace(".", ",") : "—"; }
function mvFcfa(x) { return `${x >= 0 ? "+" : "−"}${Math.abs(x).toLocaleString("fr-FR")} F`; }
// Bloc « chances » : deux questions séparées, deux réponses séparées — (1) est-ce que ça passe souvent ? (2) est-ce que la cote paie assez ?
function mvChance(p) {
  const cote = Number(p.cote); if (!Number.isFinite(cote) || cote <= 1) return "";
  const seuil = Math.round(100 / cote);
  if (p.p_honnete == null) {
    return `<div class="mv-chance"><div class="mv-rente mv-rente-inconnu">Cote non évaluée (trop haute) : seuil ${seuil} sur 100.</div></div>`;
  }
  const r = Math.round(p.p_honnete * 100), sous = r < seuil;
  const gain = Math.round(((p.p_honnete * cote - 1) * 1000) / 10) * 10;
  const verdict = sous
    ? `⚠ Cote trop basse : <b>${mvFcfa(gain)}</b> par 1 000 F misés`
    : `✔ Cote correcte : <b>${mvFcfa(gain)}</b> par 1 000 F misés`;
  return `<div class="mv-chance"><div>Réussite mesurée : <b>${r}</b> sur 100</div>` +
    `<div class="mv-jauge" aria-hidden="true"><i style="width:${r}%"></i><b style="left:${seuil}%"></b></div>` +
    `<div class="mv-legende">Trait noir = seuil pour ne pas perdre (${seuil})</div>` +
    `<div class="mv-rente ${sous ? "mv-rente-non" : "mv-rente-oui"}">${verdict}</div></div>`;
}
function mvAlerteTexte(a, l) {
  let r;
  if (a === "côté parié très défavorisé aux points") return "Le côté choisi est très défavorisé au nombre de points";
  if (a === "côté parié très mal classé") return "Le côté choisi est très mal classé";
  if ((r = a.match(/^musique (dom|ext):(rupture|pic|instable)$/))) {
    const nom = r[1] === "dom" ? l.domicile : l.exterieur;
    return { rupture: `${nom} : série de résultats récemment cassée`, pic: `${nom} : forme au plus haut (peut retomber)`, instable: `${nom} : résultats irréguliers` }[r[2]];
  }
  return a;
}
function mvPourquoi(l) {
  const lignes = [];
  if (Array.isArray(l.attendus)) lignes.push(`Buts attendus : <b>${mvEchappe(l.domicile)} ${mvFr(l.attendus[0])}</b> – <b>${mvFr(l.attendus[1])} ${mvEchappe(l.exterieur)}</b>`);
  if (Array.isArray(l.lecture)) lignes.push(`Déjà passé : ${mvPct0(l.lecture[0])} (${mvEchappe(l.domicile)} à dom.) · ${mvPct0(l.lecture[1])} (${mvEchappe(l.exterieur)} à l'ext.)`);
  if (Number(l.n_matchs_lieu) > 0 && Number(l.n_matchs_lieu) < 6) lignes.push(`<span class="mv-prudence">Peu de recul : ${Number(l.n_matchs_lieu)} matchs seulement</span>`);
  return lignes.length ? `<div class="mv-pourquoi">${lignes.map((x) => `<div>${x}</div>`).join("")}</div>` : "";
}
function mvHistorique(l) {
  const f = l.forme; if (!f) return "";
  const bloc = (nom, liste) => {
    if (!Array.isArray(liste) || !liste.length) return "";
    const puces = liste.map((x) => {
      const bm = Number(x.bm), be = Number(x.be); if (!Number.isFinite(bm) || !Number.isFinite(be)) return "";
      const lettre = bm > be ? "G" : bm === be ? "N" : "P";
      const titre = `${lettre === "G" ? "Gagné" : lettre === "N" ? "Nul" : "Perdu"} ${bm}-${be} ${x.lieu === "D" ? "à domicile" : "à l'extérieur"}${x.adversaire ? " contre " + x.adversaire : ""}${x.date ? " · " + x.date : ""}`;
      return `<span class="mv-puce" title="${mvEchappe(titre)}"><i class="mv-lettre mv-l-${lettre}">${lettre}</i> ${bm}-${be}<small class="mv-lieu">${x.lieu === "D" ? "dom." : "ext."}</small>${x.adversaire ? `<small class="mv-adv">${mvEchappe(x.adversaire)}</small>` : ""}</span>`;
    }).join("");
    return puces ? `<div class="mv-forme-eq"><b>${mvEchappe(nom)}</b><div class="mv-puces">${puces}</div></div>` : "";
  };
  const corps = bloc(l.domicile || "Domicile", f.domicile) + bloc(l.exterieur || "Extérieur", f.exterieur);
  return corps ? `<div class="mv-hist-titre">6 derniers matchs, du plus récent au plus ancien</div>` +
    `<div class="mv-info" style="margin:0 0 6px">Score = buts de l'équipe – buts de l'adversaire. G gagné · N nul · P perdu. dom. = à domicile, ext. = à l'extérieur.</div>${corps}` : "";
}
function mvDetailsTechniques(l) {
  const c = l.contexte || {}, p = l.principal || {}, lignes = [];
  lignes.push(`Estimation brute du moteur pour ce pari : ${mvPct0(p.p_modele)} (toujours trop optimiste, ne pas s'y fier : c'est la réussite mesurée qui compte).`);
  if (c.ecart_points != null) lignes.push(`Écart de points au classement : ${Number(c.ecart_points) >= 0 ? "+" : "−"}${mvFr(Math.abs(c.ecart_points), 2)} (positif = avantage pour ${mvEchappe(l.domicile)}).`);
  if (c.ecart_rang != null) lignes.push(`Écart de rang : ${Number(c.ecart_rang) >= 0 ? "+" : "−"}${mvFr(Math.abs(c.ecart_rang), 2)}.`);
  (l.alertes || []).filter((a) => a.startsWith("musique")).forEach((a) => lignes.push(mvEchappe(mvAlerteTexte(a, l))));
  return `<details class="mv-tech"><summary>Détails techniques</summary>${lignes.map((x) => `<div class="mv-info">${x}</div>`).join("")}</details>`;
}
function mvLignePari(p, l, principal) {
  const lib = marcheAvecExplication(p.marche, mvMarche(p.marche, l.domicile, l.exterieur));
  return `<div class="mv-ligne ${principal ? "mv-principal" : ""}"><span>${lib}</span>` +
    `<span><span class="mv-cote">Cote ${mvCote(p.cote)}</span> ${mvBadge(p)}</span></div>` +
    (p.resultat ? `<div class="mv-info">Pour 1 de mise : ${mvUnites(p.profit).replace(" u", "")}</div>` : "");
}
function mvLigneAutre(p, l) {
  const lib = marcheAvecExplication(p.marche, mvMarche(p.marche, l.domicile, l.exterieur));
  const r = p.p_honnete == null ? "non évalué" : `réussite mesurée ${mvPct0(p.p_honnete)}`;
  return `<div class="mv-ligne"><span>${lib}<small class="mv-sous-titre">${mvEchappe(r)}</small></span>` +
    `<span><span class="mv-cote">Cote ${mvCote(p.cote)}</span> ${mvVerdict(p.niveau)} ${mvBadge(p)}</span></div>`;
}
function mvCarte(l, mode) {
  const score = Array.isArray(l.score) ? `${l.score[0]} - ${l.score[1]}` : "";
  const h = mvHoraire(l.coup_d_envoi_utc);
  const section = document.createElement("section");
  section.className = "ax-carte ax-replie mv-ax";
  section.setAttribute("aria-expanded", "false");
  const histo = mvHistorique(l);
  const p = l.principal || {};
  const autres = Array.isArray(l.autres) ? l.autres : [];
  const blocAutres = `<div class="mv-autres"><div class="mv-autres-titre">Autres paris possibles</div>` +
    (autres.length ? autres.map((x) => mvLigneAutre(x, l)).join("") : `<div class="mv-info">Aucun autre pari.</div>`) + `</div>`;
  const alertes = (Array.isArray(l.alertes) ? l.alertes : []).filter((a) => !a.startsWith("musique") || /:rupture$/.test(a)).map((a) => mvAlerteTexte(a, l));
  const blocAlertes = alertes.length ? `<div class="mv-alerte">⚠ ${alertes.map(mvEchappe).join("<br>⚠ ")}</div>` : "";
  section.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match">` +
      `<span class="ax-equipe ax-dom">${mvEchappe(l.domicile)}</span>` +
      `<div class="ax-horaire"><strong>${mvEchappe(h.heure)}</strong><span>${mvEchappe(h.date)}</span></div>` +
      `<span class="ax-equipe ax-ext">${mvEchappe(l.exterieur)}</span></div>` +
      `<div class="ax-match-bas"><p class="ax-competition">${mvEchappe(String(l.competition || "").replace(/\s+/g, " ").trim())}</p><div class="ax-actions-tete"></div></div>` +
    `</div>` +
    `<div class="mv-corps">` +
      (score ? `<div class="mv-score">Score final <strong>${mvEchappe(score)}</strong></div>` : "") +
      `<div class="mv-info"><b>Pari proposé</b> ${mvVerdict(p.niveau)}</div>` + mvLignePari(p, l, true) +
      mvChance(p) + mvPourquoi(l) + blocAlertes + blocAutres + mvDetailsTechniques(l) +
    `</div>` +
    `<details class="ax-details" open><summary class="ax-summary-cache" tabindex="-1">Derniers scores</summary><div class="ax-details-corps">` +
      (histo || `<p class="mv-vide">Derniers scores indisponibles pour ce pronostic.</p>`) +
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
function mvListe(id, liste, mode, vide) {
  const el = document.getElementById(id); if (!el) return;
  el.innerHTML = "";
  if (liste && liste.length) liste.forEach((l) => el.appendChild(mvCarte(l, mode)));
  else el.innerHTML = `<p class="mv-vide">${mvEchappe(vide)}</p>`;
}
function mvSans(liste, plancher) {
  const el = document.getElementById("mv-sans"); if (!el) return;
  if (!(liste && liste.length)) { el.innerHTML = `<p class="mv-vide">Aucun match écarté.</p>`; return; }
  el.innerHTML = `<p class="mv-info" style="margin:0 14px 6px">Le meilleur pari du modèle reste sous ${mvPct0(plancher == null ? 0.5 : plancher)} : aucun pronostic n'est proposé.</p>` +
    liste.map((l) => {
      const h = mvHoraire(l.coup_d_envoi_utc, l.date);
      return `<div class="mv-corps"><div class="mv-ligne"><span><b>${mvEchappe(l.domicile)}</b> – <b>${mvEchappe(l.exterieur)}</b></span>` +
        `<span class="mv-info">${mvEchappe(h.date)} ${mvEchappe(h.heure)}</span></div>` +
        `<div class="mv-info">${mvEchappe(String(l.competition || "").replace(/\s+/g, " ").trim())} · meilleur score du modèle ${mvPct0(l.meilleur_score)} · aucun pronostic fiable</div></div>`;
    }).join("");
}
function mvTableauBilan(b) {
  if (!(((b.principal || {}).regles) > 0)) return `<p class="mv-info" style="margin:8px 14px">Aucun pari réglé pour l'instant : le tableau « annoncé contre réel » apparaîtra avec les premiers résultats.</p>`;
  const niveaux = ["SÛR", "MOYEN", "RISQUÉ", "NON CALIBRÉ"];
  const ligne = (role, nom) => niveaux.map((n) => {
    const s = (((b.par_niveau || {})[role]) || {})[n] || {};
    if (!(Number(s.regles) > 0)) return "";
    const ic = Array.isArray(s.ic95) ? `${mvPct0(s.ic95[0])}–${mvPct0(s.ic95[1])}` : "—";
    return `<tr><td>${mvEchappe(nom)} · ${mvNiveau(n)}</td><td>${Number(s.regles) || 0}</td><td>${s.reussite == null ? "—" : mvPct(s.reussite)}</td>` +
      `<td>${s.annonce == null ? "n/d" : mvPct(s.annonce)}</td><td>${s.ecart == null ? "—" : mvPct(s.ecart, true)}</td><td>${mvEchappe(ic)}</td></tr>`;
  }).join("");
  return `<table class="mv-table"><tr><th>Pari · verdict</th><th>Réglés</th><th>Réussite réelle</th><th>Annoncée</th><th>Écart</th><th>Fourchette (95 %)</th></tr>` +
    ligne("principal", "Principal") + ligne("autres", "Autres") + `</table>`;
}
let mvDonnees = null, mvFiltre = "tous";
const MV_FILTRES = [["tous", "Tous", () => true], ["solide", "Très probables", (l) => (l.principal || {}).niveau === "SÛR"],
  ["moyen", "Probables", (l) => (l.principal || {}).niveau === "MOYEN"], ["risque", "Incertains / non évalués", (l) => !["SÛR", "MOYEN"].includes((l.principal || {}).niveau)]];
function mvRendAvenir() {
  const f = MV_FILTRES.find((x) => x[0] === mvFiltre) || MV_FILTRES[0];
  mvListe("mv-avenir", ((mvDonnees || {}).a_venir || []).filter(f[2]), "avenir", "Aucun pari dans cette catégorie.");
}
function mvFiltres() {
  const el = document.getElementById("mv-filtres"); if (!el) return;
  const liste = (mvDonnees || {}).a_venir || [];
  el.innerHTML = MV_FILTRES.map((f) => `<button type="button" class="mv-filtre${f[0] === mvFiltre ? " mv-actif" : ""}" data-f="${f[0]}" aria-pressed="${f[0] === mvFiltre}">${f[1]} (${liste.filter(f[2]).length})</button>`).join("");
  el.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { mvFiltre = b.dataset.f; mvFiltres(); mvRendAvenir(); }));
}
function mvAffiche(d) {
  const b = d.bilan || {};
  const noms = { observation: "EN OBSERVATION — ne mise pas encore", controle_ok: "CONTRÔLE OK — les réussites annoncées sont tenues (rentabilité non démontrée)", gel: "GEL — une réussite annoncée n'est pas tenue : ne pas miser" };
  const gele = Array.isArray(b.niveaux_geles) && b.niveaux_geles.length ? ` Verdicts gelés : ${b.niveaux_geles.map((n) => (MV_VERDICT[n] || [n])[0]).join(", ")}.` : "";
  document.getElementById("mv-statut").innerHTML =
    `<div class="mv-statut ${mvEchappe(d.statut)}">${mvEchappe(noms[d.statut] || d.statut)}` +
    `<small>${mvEchappe(d.avertissement || "Réussite réelle comparée à la réussite annoncée pour chaque verdict.")}${mvEchappe(gele)}</small></div>`;
  document.getElementById("mv-bilan").innerHTML = mvTableauBilan(b);
  const zones = Array.isArray(d.zones) ? d.zones.map((z) => `${mvCote(z.cote_min)}–${mvCote(z.cote_max)} → ${mvPct0(z.fiabilite)}`).join(" · ") : "";
  document.getElementById("mv-zones").innerHTML = zones ? `<p class="mv-info" style="margin:6px 14px"><b>Réussite mesurée sur 440 matchs passés :</b> ${zones}. Au-dessus de 1,81 : non évalué.</p>` : "";
  mvDonnees = d;
  mvFiltres();
  mvRendAvenir();
  mvSans(d.sans_pronostic, d.plancher_principal);
  mvListe("mv-encours", d.en_cours, "encours", "Aucun match en cours.");
  mvListe("mv-regles", d.reglees, "regle", "Aucun pronostic réglé pour l'instant.");
  const g = d.genere_le ? new Date(d.genere_le) : null;
  document.getElementById("maj").textContent = g && !Number.isNaN(g.getTime())
    ? `Mis à jour le ${g.toLocaleDateString("fr-FR")} à ${g.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}` : "";
}
function mvThemeNuit() {
  const bouton = document.getElementById("ax-bouton-theme"); if (!bouton) return;
  const applique = (nuit) => {
    document.body.classList.toggle("theme-nuit", nuit);
    bouton.textContent = nuit ? "☀" : "☾";
    bouton.setAttribute("aria-label", nuit ? "Activer le mode clair" : "Activer le mode nuit");
  };
  let nuit = false;
  try { nuit = localStorage.getItem(CLE_THEME_NUIT_V) === "1"; } catch (e) { /* stockage indisponible */ }
  applique(nuit);
  bouton.addEventListener("click", () => {
    const suivant = !document.body.classList.contains("theme-nuit");
    try { localStorage.setItem(CLE_THEME_NUIT_V, suivant ? "1" : "0"); } catch (e) { /* ignoré */ }
    applique(suivant);
  });
}
mvThemeNuit();
if (document.getElementById("mv-avenir")) {
  fetch(`data/v/pronostics_v.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`données v introuvables (${r.status}) : le moteur n'a pas encore tourné`); return r.json(); })
    .then(mvAffiche)
    .catch((e) => { document.getElementById("maj").textContent = "Erreur de chargement : " + e.message; console.error(e); });
}
