// ARCHETYPE — affichage uniquement.
// Aucun choix, filtre, probabilité ou statistique n'est calculé dans le navigateur.

const RANGS = [
  { key: "P1", cls: "p1", icon: "♛", title: "Le meilleur choix", sub: "Pronostic principal" },
  { key: "P2", cls: "p2", icon: "◆", title: "Meilleure rentabilité", sub: "Deuxième choix" },
  { key: "P3", cls: "p3", icon: "+", title: "Pronostic bonus", sub: "Troisième choix" },
];

function esc(v) {
  return v == null ? "" : String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function num(v) { const n = Number(v); return Number.isFinite(n) ? n : null; }
function pct(v, digits = 1) { const n = num(v); return n == null ? "—" : `${(n * 100).toFixed(digits).replace(".", ",")} %`; }
function cote(v) { const n = num(v); return n == null ? "—" : n.toFixed(2).replace(".", ","); }
function dateFr(iso) {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("fr-FR", { weekday:"long", day:"2-digit", month:"short", year:"numeric" }).replace(/\./g, "").replace(/^./, c => c.toUpperCase());
}
function initials(name) {
  const a = String(name || "?").trim().split(/\s+/).filter(Boolean);
  if (!a.length) return "?";
  return a.length === 1 ? a[0].slice(0,2).toUpperCase() : (a[0][0] + a[a.length-1][0]).toUpperCase();
}
function confidence(level) {
  const map = { PREMIUM:[5,"Exceptionnelle"], TRES_FORT:[4,"Très forte"], FORT:[3,"Forte"], ELIGIBLE:[2,"Correcte"], ELIGIBLE_PLUS:[1,"Suffisante"] };
  return map[level] || [1,"Suffisante"];
}
function translateMarket(m, teams) {
  const s = String(m || "");
  const total = s.match(/^total_(over|under)_([0-9.]+)$/) || s.match(/^over_under_total_([0-9.]+)_(over|under)$/);
  if (total) {
    const sens = total[1] === "over" || total[2] === "over" ? "Plus de" : "Moins de";
    const line = total[2] || total[1];
    return `${sens} ${line.replace(".", ",")} buts`;
  }
  if (s === "btts_oui") return "Les deux équipes marquent";
  if (s === "btts_non") return "Les deux équipes ne marquent pas";
  if (s === "double_chance_1X") return `${teams.home} ou nul`;
  if (s === "double_chance_X2") return `${teams.away} ou nul`;
  if (s === "double_chance_12") return "Victoire de l'une des deux équipes";
  if (s === "1x2_domicile") return `Victoire de ${teams.home}`;
  if (s === "1x2_exterieur") return `Victoire de ${teams.away}`;
  if (s === "1x2_nul") return "Match nul";
  const tg = s.match(/^buts_equipe_(domicile|exterieur)_(over|under)_([0-9.]+)$/);
  if (tg) {
    const team = tg[1] === "domicile" ? teams.home : teams.away;
    const sens = tg[2] === "over" ? "marque +" : "marque moins de";
    return `${team} ${sens} ${tg[3].replace(".", ",")} but(s)`;
  }
  const hc = s.match(/^handicap_(domicile|exterieur)_(-?[0-9.]+)$/);
  if (hc) {
    const team = hc[1] === "domicile" ? teams.home : teams.away;
    return `${team} avec un handicap de ${hc[2].replace(".", ",")}`;
  }
  if (s === "parite_pair") return "Nombre de buts pair";
  if (s === "parite_impair") return "Nombre de buts impair";
  if (s === "cage_inviolee_domicile") return `${teams.home} garde sa cage inviolée`;
  if (s === "cage_inviolee_exterieur") return `${teams.away} garde sa cage inviolée`;
  if (s === "encaisse_domicile") return `${teams.home} encaisse au moins un but`;
  if (s === "encaisse_exterieur") return `${teams.away} encaisse au moins un but`;
  return s.replaceAll("_", " ");
}
function gauge(prob, accentClass) {
  const p = num(prob);
  if (p == null) return "";
  const v = Math.max(0, Math.min(1, p));
  const r = 46, c = 2 * Math.PI * r;
  return `<div class="gauge ${accentClass}" aria-label="${Math.round(v*100)} % de chances de réussite"><svg viewBox="0 0 110 110"><circle class="track" cx="55" cy="55" r="${r}"></circle><circle class="value" cx="55" cy="55" r="${r}" stroke-dasharray="${c.toFixed(2)}" stroke-dashoffset="${(c*(1-v)).toFixed(2)}"></circle></svg><strong>${Math.round(v*100)}%</strong></div>`;
}
function stars(level) {
  const [n] = confidence(level);
  return `<span class="stars">${"★".repeat(n)}<span style="opacity:.22">${"★".repeat(5-n)}</span></span>`;
}
function whyBlock(c) {
  const j = c && c.justification;
  const js = c && c.justification_selection;
  const pieces = [];
  if (js && js.texte) pieces.push(`<p class="why-selection">${esc(js.texte)}</p>`);
  if (j && Array.isArray(j.preuves)) {
    j.preuves.forEach(p => {
      if (!p || !p.texte) return;
      pieces.push(`<div class="proof"><span class="proof-title">${esc(p.titre || "Statistiques clés")}</span><span class="proof-text">${esc(p.texte)}</span></div>`);
    });
  }
  if (!pieces.length) {
    // Pas de mensonge de remplacement : la raison décisionnelle est toujours
    // fournie par justification_selection lorsque le moteur a produit la sélection.
    pieces.push(`<p class="why-selection">La sélection est expliquée par la trace réelle de la décision du modèle.</p>`);
  }
  return pieces.join("");
}
function candidate(info, c, teams) {
  if (!c) return null;
  const [n, conf] = confidence(c.niveau);
  const market = translateMarket(c.marche, teams);
  const j = c.justification || {};
  const selectionReason = c.justification_selection || {};
  const intro = j.resume ? `<p class="intro">${esc(j.resume)}</p>` : "";
  const detail = [
    ["Marché", market], ["Niveau", c.niveau || "—"], ["Stabilité", c.robustesse || "—"],
    ["Convergence", `${selectionReason.scenarios_valides ?? 0}/${selectionReason.scenarios_total ?? 4} scénarios`],
    ["Confrontations directes", c.h2h_palier || "—"]
  ];
  return `<article class="selection ${info.cls}">
    <div class="choice-head"><div class="choice-icon">${info.icon}</div><div><div class="choice-kicker">${info.title}</div><div class="choice-sub">${info.sub}</div></div></div>
    <h2 class="market">${esc(market)}</h2>
    ${intro}
    <div class="metrics"><div><span class="label">Cote</span><strong class="odds">${cote(c.cote)}</strong><span class="label success-label">Chances de réussite</span><strong class="success">${pct(c.probabilite,0)}</strong><span class="label">estimées par le modèle</span></div>${gauge(c.probabilite, info.cls)}</div>
    <div class="confidence">${stars(c.niveau)}<span><strong>Confiance</strong> · ${esc(conf)}</span></div>
    <div class="why"><div class="why-title">Pourquoi ce choix ?</div>${whyBlock(c)}</div>
    <div class="financial"><div><span class="label">Avantage potentiel</span><strong>${pct(c.edge)}</strong></div><div><span class="label">Gain potentiel</span><strong>${pct(c.edv)}</strong></div></div>
    <details class="details"><summary><span><span class="details-title">Détails de l'analyse</span><span class="details-sub">Éléments techniques ayant accompagné la sélection</span></span><span class="details-arrow">⌄</span></summary><div class="details-body">${detail.map(x => `<div class="detail"><span class="detail-label">${esc(x[0])}</span><span class="detail-value">${esc(x[1])}</span></div>`).join("")}</div></details>
  </article>`;
}
function matchCard(m) {
  const am = m.archetype_model || {};
  const sel = am.selection || {};
  if (am.statut !== "OK" || !sel.P1) return "";
  const teams = {home:m.domicile || "Équipe à domicile", away:m.exterieur || "Équipe à l'extérieur"};
  const choices = RANGS.map(r => candidate(r, sel[r.key], teams)).filter(Boolean).join("");
  const competition = String(m.competition || "").replace(/\s+/g," ").trim();
  return `<section class="match"><header class="match-head"><div class="match-line"><div class="team home"><span class="crest">${esc(initials(teams.home))}</span><span>${esc(teams.home)}</span></div><div class="kick"><strong>${esc(m.heure_cameroun || m.heure || "—")}</strong><span>${esc(dateFr(m.date))}</span></div><div class="team away"><span>${esc(teams.away)}</span><span class="crest">${esc(initials(teams.away))}</span></div></div>${competition ? `<div class="competition">● &nbsp;${esc(competition)}</div>` : ""}</header><div class="choices">${choices}</div></section>`;
}
function render(data) {
  const root = document.getElementById("matches");
  const all = Array.isArray(data?.signaux) ? data.signaux : [];
  const matches = all.filter(m => m && m.moteur_utilise === "archetype_model" && m.archetype_model?.statut === "OK" && m.archetype_model?.selection?.P1);
  matches.sort((a,b) => `${a.date||""}${a.heure_cameroun||a.heure||""}`.localeCompare(`${b.date||""}${b.heure_cameroun||b.heure||""}`));
  document.getElementById("maj").innerHTML = matches.length ? `<strong>${matches.length}</strong> match${matches.length>1?"s":""} analysé${matches.length>1?"s":""} aujourd'hui` : "Aucune sélection pour le moment";
  root.innerHTML = matches.length ? matches.map(matchCard).join("") : `<div class="empty"><strong>Aucune sélection pour le moment</strong><p>Le modèle n'a retenu aucun match répondant à ses critères actuels.</p></div>`;
}
fetch(`precalcul_leger.json?_=${Date.now()}`).then(r => { if (!r.ok) throw new Error(`precalcul_leger.json introuvable (${r.status})`); return r.json(); }).then(render).catch(e => { document.getElementById("maj").textContent = `Erreur de chargement : ${e.message}`; console.error(e); });
