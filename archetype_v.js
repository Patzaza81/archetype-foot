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
    return `${r[2] === "Domicile" ? dom : ext} · handicap ${x > 0 ? "+" : x < 0 ? "−" : ""}${virg(String(Math.abs(x)))}`;
  }
  if ((r = m.match(/^(Plus|Moins) de (.+) buts - (Domicile|Extérieur)$/))) return `${r[3] === "Domicile" ? dom : ext} : ${r[1].toLowerCase()} de ${virg(r[2])} buts`;
  if ((r = m.match(/^(Plus|Moins) de (.+) buts$/))) return `${r[1]} de ${virg(r[2])} buts`;
  return virg(m);
}
function mvNiveau(n) {
  const cls = { "SÛR": "SUR", "MOYEN": "MOYEN", "RISQUÉ": "RISQUE" }[n] || "NC";
  return `<span class="mv-niv mv-niv-${cls}">${mvEchappe(n || "NON CALIBRÉ")}</span>`;
}
function mvBadge(p) {
  return p && p.resultat ? `<span class="mv-badge mv-${mvEchappe(p.resultat)}">${p.resultat === "WIN" ? "GAGNÉ" : "PERDU"}</span>` : "";
}
function mvFiab(p) {            // fiabilité MESURÉE (jamais le score brut du modèle comme probabilité)
  return p.p_honnete == null ? "fiabilité non mesurée" : `fiabilité mesurée ${mvPct0(p.p_honnete)}`;
}
function mvHistorique(l) {
  const f = l.forme; if (!f) return "";
  const bloc = (nom, liste) => {
    if (!Array.isArray(liste) || !liste.length) return "";
    const pastilles = liste.map((x) => {
      const bm = Number(x.bm), be = Number(x.be); if (!Number.isFinite(bm) || !Number.isFinite(be)) return "";
      const res = bm > be ? "ax-res-v" : bm === be ? "ax-res-n" : "ax-res-d";
      const titre = `${bm > be ? "Gagné" : bm === be ? "Nul" : "Perdu"} · ${x.lieu === "D" ? "à domicile" : "à l'extérieur"}${x.adversaire ? " contre " + x.adversaire : ""}${x.date ? " · " + x.date : ""}`;
      // bm = buts marqués par l'équipe, be = buts encaissés. Score écrit comme au tableau d'affichage (domicile-extérieur) ;
      // le chiffre coloré est TOUJOURS celui de l'équipe (corrigé le 16/10/2026 : à l'extérieur, c'était le chiffre de l'adversaire).
      const suivi = `<span class="ax-but ${res}" title="${mvEchappe(titre)}">${bm}</span>`;
      const autre = be;
      return `<span class="ax-res">${x.lieu === "D" ? suivi + "-" + autre : autre + "-" + suivi}<small class="mv-lieu">${x.lieu}</small></span>`;
    }).join("");
    return pastilles ? `<div class="ax-hist"><span class="ax-hist-eq">${mvEchappe(nom)}</span><span class="ax-hist-liste">${pastilles}</span></div>` : "";
  };
  const corps = bloc(l.domicile || "Domicile", f.domicile) + bloc(l.exterieur || "Extérieur", f.exterieur);
  return corps ? `<div class="ax-hist-bloc"><div class="mv-hist-titre">Derniers matchs (du plus récent au plus ancien)</div><div class="mv-info" style="margin:0 0 6px">Score comme au tableau (domicile – extérieur). Chiffre en couleur = buts de l'équipe : vert gagné, orange nul, rouge perdu. D = joué à domicile, E = à l'extérieur. Tous lieux confondus (le moteur, lui, ne lit que les matchs au même lieu).</div>${corps}</div>` : "";
}
function mvContexte(l) {
  const c = l.contexte || {}, morceaux = [];
  if (Number.isFinite(Number(c.ecart_points)) && c.ecart_points !== null) morceaux.push(`écart de points ${Number(c.ecart_points) >= 0 ? "+" : "−"}${Math.abs(Number(c.ecart_points)).toFixed(2).replace(".", ",")} (domicile − extérieur)`);
  if (Number.isFinite(Number(c.ecart_rang)) && c.ecart_rang !== null) morceaux.push(`écart de rang ${Number(c.ecart_rang) >= 0 ? "+" : "−"}${Math.abs(Number(c.ecart_rang)).toFixed(2).replace(".", ",")}`);
  return morceaux.length ? `<div class="mv-info">Contexte : ${mvEchappe(morceaux.join(" · "))}</div>` : "";
}
function mvLignePari(p, l, principal) {
  const lib = mvEchappe(mvMarche(p.marche, l.domicile, l.exterieur));
  return `<div class="mv-ligne ${principal ? "mv-principal" : ""}"><span>${lib}</span>` +
    `<span><span class="mv-cote">Cote ${mvCote(p.cote)}</span> ${mvBadge(p)}</span></div>` +
    `<div class="mv-ligne mv-info"><span>${mvNiveau(p.niveau)} ${mvEchappe(mvFiab(p))} · score du modèle ${mvPct0(p.p_modele)}</span>` +
    `${p.resultat ? `<small>${mvUnites(p.profit)}</small>` : ""}</div>`;
}
function mvCarte(l, mode) {
  const score = Array.isArray(l.score) ? `${l.score[0]} - ${l.score[1]}` : "";
  const h = mvHoraire(l.coup_d_envoi_utc);
  const section = document.createElement("section");
  section.className = "ax-carte ax-replie mv-ax";
  section.setAttribute("aria-expanded", "false");
  const histo = mvHistorique(l);
  const autres = Array.isArray(l.autres) ? l.autres : [];
  const blocAutres = `<div class="mv-autres"><div class="mv-autres-titre">Autres pronostics acceptables</div>` +
    (autres.length ? autres.map((p) => `<div>${mvLignePari(p, l, false)}</div>`).join("") : `<div class="mv-info">Aucun autre pronostic acceptable.</div>`) + `</div>`;
  const alertes = Array.isArray(l.alertes) && l.alertes.length ? `<div class="mv-alerte">Alertes : ${mvEchappe(l.alertes.join(" · "))}</div>` : "";
  section.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match">` +
      `<span class="ax-equipe ax-dom">${mvEchappe(l.domicile)}</span>` +
      `<div class="ax-horaire"><strong>${mvEchappe(h.heure)}</strong><span>${mvEchappe(h.date)}</span></div>` +
      `<span class="ax-equipe ax-ext">${mvEchappe(l.exterieur)}</span></div>` +
      `<div class="ax-match-bas"><p class="ax-competition">${mvEchappe(String(l.competition || "").replace(/\s+/g, " ").trim())}</p><div class="ax-actions-tete"></div></div>` +
    `</div>` +
    `<div class="mv-corps">` +
      (score ? `<div class="mv-score">Score final <strong>${mvEchappe(score)}</strong></div>` : "") +
      `<div class="mv-info"><b>Pronostic principal</b></div>` + mvLignePari(l.principal || {}, l, true) +
      mvContexte(l) + alertes + blocAutres +
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
  if (!(((b.principal || {}).regles) > 0)) return `<p class="mv-info" style="margin:8px 14px">Aucun pronostic réglé pour l'instant : le tableau de fiabilité par niveau apparaîtra avec les premiers résultats.</p>`;
  const niveaux = ["SÛR", "MOYEN", "RISQUÉ", "NON CALIBRÉ"];
  const ligne = (role, nom) => niveaux.map((n) => {
    const s = (((b.par_niveau || {})[role]) || {})[n] || {};
    if (!(Number(s.regles) > 0)) return "";
    const ic = Array.isArray(s.ic95) ? `${mvPct0(s.ic95[0])}–${mvPct0(s.ic95[1])}` : "—";
    return `<tr><td>${mvEchappe(nom)} · ${mvNiveau(n)}</td><td>${Number(s.regles) || 0}</td><td>${s.reussite == null ? "—" : mvPct(s.reussite)}</td>` +
      `<td>${s.annonce == null ? "n/d" : mvPct(s.annonce)}</td><td>${s.ecart == null ? "—" : mvPct(s.ecart, true)}</td><td>${mvEchappe(ic)}</td></tr>`;
  }).join("");
  return `<table class="mv-table"><tr><th>Pari · niveau</th><th>Réglés</th><th>Réussite</th><th>Fiabilité annoncée</th><th>Écart</th><th>IC95</th></tr>` +
    ligne("principal", "Principal") + ligne("autres", "Autres") + `</table>`;
}
function mvAffiche(d) {
  const b = d.bilan || {};
  const noms = { observation: "OBSERVATION — ne pas miser", controle_ok: "CONTRÔLE OK — fiabilités tenues (rentabilité non démontrée)", gel: "GEL — une fiabilité annoncée n'est pas tenue" };
  const gele = Array.isArray(b.niveaux_geles) && b.niveaux_geles.length ? ` Niveaux gelés : ${b.niveaux_geles.join(", ")}.` : "";
  document.getElementById("mv-statut").innerHTML =
    `<div class="mv-statut ${mvEchappe(d.statut)}">${mvEchappe(noms[d.statut] || d.statut)}` +
    `<small>${mvEchappe(d.avertissement || "Réussite réelle au carnet comparée à la fiabilité annoncée par niveau.")}${mvEchappe(gele)} Paramètres du ${mvEchappe(d.parametres_version)}.</small></div>`;
  document.getElementById("mv-bilan").innerHTML = mvTableauBilan(b);
  const zones = Array.isArray(d.zones) ? d.zones.map((z) => `${mvCote(z.cote_min)}–${mvCote(z.cote_max)} : ${mvEchappe(z.niveau)} ${mvPct0(z.fiabilite)}`).join(" · ") : "";
  document.getElementById("mv-zones").innerHTML = zones ? `<p class="mv-info" style="margin:6px 14px">Fiabilité mesurée par zone de cote (440 matchs passés) — ${zones}. Au-dessus de 1,81 : non calibré, à éviter.</p>` : "";
  mvListe("mv-avenir", d.a_venir, "avenir", "Aucun pronostic à venir.");
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
