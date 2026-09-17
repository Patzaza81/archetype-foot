// archetype.js — présentation uniquement.
// Le navigateur ne choisit aucun pronostic et ne calcule aucune statistique.

const RANGS = [
  { cle: "P1", classe: "rang-1", titre: "Pronostic principal" },
  { cle: "P2", classe: "rang-2", titre: "Deuxième choix" },
  { cle: "P3", classe: "rang-3", titre: "Troisième choix" },
];

function estArchetypeGo(m) {
  return !!(m && m.moteur_utilise === "archetype_model" && m.archetype_model &&
    m.archetype_model.statut === "OK" && m.archetype_model.selection && m.archetype_model.selection.P1);
}
function echappeHtml(x) { return x === null || x === undefined ? "" : String(x).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#39;"); }
function formatCote(x) { const n = Number(x); return Number.isFinite(n) ? n.toFixed(2).replace(".", ",") : "—"; }
function formatPct(x) { const n = Number(x); return Number.isFinite(n) ? `${(n * 100).toFixed(1).replace(".", ",")} %` : "—"; }
function formatPctEntier(x) { const n = Number(x); return Number.isFinite(n) ? `${Math.round(n * 100)} %` : "—"; }
function formatDate(dateIso) { if (!dateIso) return ""; const d = new Date(`${dateIso}T12:00:00`); if (Number.isNaN(d.getTime())) return dateIso; return d.toLocaleDateString("fr-FR", { weekday: "short", day: "2-digit", month: "short" }).replace(/\./g, "").replace(/^./, c => c.toUpperCase()); }
function initialesEquipe(nom) { const mots = String(nom || "?").trim().split(/\s+/).filter(Boolean); if (!mots.length) return "?"; return mots.length === 1 ? mots[0].slice(0, 2).toUpperCase() : (mots[0][0] + mots[mots.length - 1][0]).toUpperCase(); }
// AJOUT 17/09/2026 (Patrick, jargon désynchronisé du moteur réel) --
// traduitConfiance() dupliquait, avec un texte moins précis, ce que
// traduction_marches.js fait déjà correctement (traduitNiveau) --
// cette dernière fonction porte un commentaire explicite : "niveau"
// est un niveau d'éligibilité du filtre, pas une probabilité empirique
// de gain, on ne l'appelle plus "Confiance" dans l'UI. archetype.js ne
// suivait pas cette règle malgré sa présence documentée dans le même
// projet -- supprimé, traduitNiveau() est utilisée directement plus bas.
function construitJauge(probabilite) {
  const n = Number(probabilite); if (!Number.isFinite(n)) return "";
  const v = Math.max(0, Math.min(1, n)); const r = 31, c = 2 * Math.PI * r;
  return `<div class="jauge" aria-label="Probabilité du modèle : ${Math.round(v * 100)} %"><svg viewBox="0 0 76 76" aria-hidden="true"><circle class="fond" cx="38" cy="38" r="${r}"></circle><circle class="valeur" cx="38" cy="38" r="${r}" stroke-dasharray="${c.toFixed(2)}" stroke-dashoffset="${(c * (1 - v)).toFixed(2)}"></circle></svg><strong>${Math.round(v * 100)}%</strong></div>`;
}
function construitPourquoi(candidat) {
  const j = candidat && candidat.justification;
  if (!j) return "";
  const morceaux = [];
  if (j.resume) morceaux.push(`<p class="resume-preuve">${echappeHtml(j.resume)}</p>`);
  if (Array.isArray(j.preuves) && j.preuves.length) {
    morceaux.push(`<details class="preuves-cachees"><summary>Voir les preuves statistiques ▾</summary>${j.preuves.map(p => p && p.texte ? `<div class="preuve"><span class="preuve-titre">${echappeHtml(p.titre || "Statistique clé")}</span><span class="preuve-texte">${echappeHtml(p.texte)}</span></div>` : "").join("")}</details>`);
  }
  return morceaux.join("");
}
function construitStatsRapides(candidat) {
  const preuves = (candidat.justification && candidat.justification.preuves) || [];
  const h2h = preuves.find((p) => p && typeof p.type === "string" && p.type.startsWith("h2h_"));
  const forme = preuves.find((p) => p && p !== h2h && p.type !== "ev_percentage") || null;
  const { texte: niveauTexte } = traduitNiveau(candidat.niveau);
  const cases = [
    { icone: "📊", titre: "Forme récente", texte: forme ? forme.texte : "Non disponible" },
    { icone: "🛡️", titre: "Confrontations directes", texte: h2h ? h2h.texte : "Non disponible" },
    { icone: "⭐", titre: "Solidité", texte: niveauTexte },
  ];
  return `<div class="stats-rapides">${cases.map((c) => `<div class="stat-rapide"><span class="icone-stat" aria-hidden="true">${c.icone}</span><div><span class="stat-titre">${echappeHtml(c.titre)}</span><span class="stat-texte">${echappeHtml(c.texte)}</span></div></div>`).join("")}</div>`;
}
function construitBlocCandidat(info, candidat, equipes) {
  if (!candidat) return null;
  const article = document.createElement("article"); article.className = `selection ${info.classe}`;
  article.dataset.cle = info.cle;
  const { etoiles, texte: niveauTexte } = traduitNiveau(candidat.niveau);
  const stars = "★".repeat(etoiles) + `<span class="etoiles-vides">${"★".repeat(5 - etoiles)}</span>`;
  const libelle = traduitMarche(candidat.marche, equipes);
  article.innerHTML = `<div class="selection-inner">
    <h2 class="libelle-marche">${echappeHtml(libelle)}</h2>
    ${candidat.justification && candidat.justification.resume ? `<p class="resume-marche">${echappeHtml(candidat.justification.resume)}</p>` : ""}
    ${construitStatsRapides(candidat)}
    <div class="donnees-principales">
      <div>
        <span class="etiquette">Cote</span>
        <strong class="cote">${formatCote(candidat.cote)}</strong>
        <span class="etiquette">Probabilité du modèle</span>
        <div class="probabilite-ligne"><strong>${formatPctEntier(candidat.probabilite)}</strong><span class="etiquette">estimation statistique</span></div>
      </div>
      ${construitJauge(candidat.probabilite)}
    </div>
    <div class="ligne-confiance"><span>Solidité</span><span class="etoiles" aria-label="Solidité : ${etoiles} sur 5">${stars}</span><strong>${echappeHtml(niveauTexte)}</strong></div>
    <div class="bloc-pourquoi"><div class="titre">Pourquoi ce choix ?</div>${construitPourquoi(candidat)}</div>
    <div class="metriques"><div class="metrique" title="Écart entre la probabilité calculée par le modèle et celle qui serait 'normale' vu la cote proposée."><span>Avantage potentiel</span><strong>${formatPct(candidat.edge)}</strong></div><div class="metrique" title="Ce que rapporterait ce pari en moyenne si on le rejouait de nombreuses fois, selon le modèle."><span>Gain potentiel</span><strong>${formatPct(candidat.edv)}</strong></div></div>
  </div>`;
  article.style.setProperty("--accent", `var(--${info.classe === "rang-1" ? "ref-gold" : info.classe === "rang-2" ? "ref-blue-tab" : "ref-violet"})`);
  return article;
}
function construitDetails(m) {
  const details = document.createElement("details"); details.className = "details-analyse";
  const equipes = { domicile: m.domicile || "Équipe à domicile", exterieur: m.exterieur || "Équipe à l'extérieur" };
  const selection = (m.archetype_model && m.archetype_model.selection) || {}; const lignes = [];
  RANGS.forEach(r => { const c = selection[r.cle]; if (!c) return;
    // AJOUT 17/09/2026 (Patrick, jargon technique pas toujours compris) --
    // marche/niveau/robustesse étaient affichés en valeurs brutes du
    // moteur ("1x2_domicile", "PREMIUM", "STABLE"), illisibles pour qui
    // ne connaît pas le code -- traduites comme partout ailleurs sur la carte.
    const { texte: niveauTexte } = traduitNiveau(c.niveau);
    lignes.push(`<div class="ligne-detail"><span class="cle">${echappeHtml(r.titre)}</span><span class="val">${echappeHtml(traduitMarche(c.marche, equipes))}</span></div>`);
    lignes.push(`<div class="ligne-detail"><span class="cle">Solidité du pari</span><span class="val">${echappeHtml(niveauTexte)}</span></div>`);
    lignes.push(`<div class="ligne-detail"><span class="cle">Stabilité du calcul</span><span class="val">${echappeHtml(traduitRobustesse(c.robustesse))}</span></div>`);
  });
  details.innerHTML = `<summary><span><span class="details-titre">Détails de l'analyse</span><span class="details-sous-titre">Éléments techniques ayant accompagné la sélection</span></span><span class="chevron">⌄</span></summary><div class="contenu-details">${lignes.join("") || "Aucun détail technique disponible."}</div>`;
  return details;
}
function identiteMatch(m) {
  if (m && m.match_id !== undefined && m.match_id !== null && String(m.match_id).trim() !== "") return `id:${String(m.match_id)}`;
  return `match:${String(m?.date || "").trim()}|${String(m?.heure_cameroun || m?.heure || "").trim()}|${String(m?.domicile || "").trim().toLowerCase()}|${String(m?.exterieur || "").trim().toLowerCase()}`;
}
function regroupeMatchs(matchs) {
  const groupes = new Map();
  (matchs || []).forEach(m => {
    const cle = identiteMatch(m);
    if (!groupes.has(cle)) { groupes.set(cle, m); return; }
    const actuel = groupes.get(cle);
    if (m.archetype_model && actuel.archetype_model) {
      actuel.archetype_model.selection = { ...(actuel.archetype_model.selection || {}), ...(m.archetype_model.selection || {}) };
    }
  });
  return Array.from(groupes.values());
}
function construitApercuRang(info, candidat, equipes, accentClasse) {
  const div = document.createElement("div");
  div.className = `apercu-rang apercu-${info.cle}`;
  if (!candidat) {
    div.classList.add("indisponible");
    div.innerHTML = `<div class="apercu-etiquette"><span class="puce-rang" aria-hidden="true"></span>${echappeHtml(info.titre)}</div><p class="apercu-marche">Non disponible pour ce match</p>`;
    return div;
  }
  const libelle = traduitMarche(candidat.marche, equipes);
  div.innerHTML = `
    <div class="apercu-etiquette"><span class="puce-rang" aria-hidden="true"></span>${echappeHtml(info.titre)}</div>
    <div class="apercu-corps">
      <div>
        <h2 class="apercu-marche">${echappeHtml(libelle)}</h2>
        <div class="apercu-donnees"><span>Cote<strong>${formatCote(candidat.cote)}</strong></span><span>Probabilité<strong>${formatPctEntier(candidat.probabilite)}</strong></span></div>
      </div>
      ${construitJauge(candidat.probabilite)}
    </div>`;
  return div;
}
function construitApercuListe(selection, equipes) {
  const div = document.createElement("div"); div.className = "apercu-liste";
  RANGS.forEach(info => div.appendChild(construitApercuRang(info, selection[info.cle], equipes)));
  return div;
}
function construitCarte(m) {
  const section = document.createElement("section"); section.className = "carte-match";
  const equipes = { domicile: m.domicile || "Équipe à domicile", exterieur: m.exterieur || "Équipe à l'extérieur" };
  const heure = m.heure_cameroun || m.heure || "—"; const date = formatDate(m.date); const competition = String(m.competition || "").replace(/\s+/g, " ").trim();
  const selection = (m.archetype_model && m.archetype_model.selection) || {};
  const disponibles = RANGS.filter(r => selection[r.cle]);
  const premier = disponibles[0] || RANGS[0];
  section.innerHTML = `<header class="entete-match"><div class="ligne-match">
    <div class="equipe domicile"><span class="ecusson-equipe">${echappeHtml(initialesEquipe(equipes.domicile))}</span><span>${echappeHtml(equipes.domicile)}</span></div>
    <div class="bloc-horaire"><strong>${echappeHtml(heure)}</strong><span>${echappeHtml(date)}</span></div>
    <div class="equipe exterieur"><span>${echappeHtml(equipes.exterieur)}</span><span class="ecusson-equipe">${echappeHtml(initialesEquipe(equipes.exterieur))}</span></div>
  </div>${competition ? `<div class="competition">${echappeHtml(competition)}</div>` : ""}</header>`;
  section.appendChild(construitApercuListe(selection, equipes));
  const boutonRepliHtml = document.createElement("button");
  boutonRepliHtml.type = "button"; boutonRepliHtml.className = "bouton-repli"; boutonRepliHtml.setAttribute("aria-expanded", "true");
  boutonRepliHtml.innerHTML = `Replier <span aria-hidden="true">⌃</span>`;
  section.appendChild(boutonRepliHtml);

  const tabs = document.createElement("nav"); tabs.className = "selection-tabs"; tabs.setAttribute("aria-label", "Choix du pronostic");
  const selections = document.createElement("div"); selections.className = "contenu-carte";
  const blocs = [];
  // AJOUT 17/09/2026 (Patrick) : les 3 onglets sont TOUJOURS construits,
  // même quand un rang n'a pas de candidat -- affiché "en veille"
  // (assombri, non cliquable) plutôt que masqué, pour que la structure
  // à 3 choix reste visible même quand un seul pronostic existe.
  RANGS.forEach(info => {
    const candidat = selection[info.cle];
    const tab = document.createElement("button"); tab.type = "button"; tab.className = "selection-tab"; tab.dataset.cle = info.cle;
    if (!candidat) {
      tab.classList.add("indisponible"); tab.disabled = true;
      tab.innerHTML = `${echappeHtml(info.titre)}<small>Non disponible</small>`;
      tabs.appendChild(tab);
      return;
    }
    const libelle = traduitMarche(candidat.marche, equipes);
    tab.innerHTML = `${echappeHtml(info.titre)}<small>${echappeHtml(libelle)}</small>`;
    const bloc = construitBlocCandidat(info, candidat, equipes); if (!bloc) return;
    tab.addEventListener("click", () => {
      tabs.querySelectorAll(".selection-tab").forEach(t => t.classList.toggle("actif", t === tab));
      selections.querySelectorAll(".selection").forEach(b => b.classList.toggle("actif", b === bloc));
    });
    tabs.appendChild(tab); blocs.push({tab, bloc});
  });
  if (blocs.length) {
    blocs.forEach(x => selections.appendChild(x.bloc));
    const actif = blocs.find(x => x.tab.dataset.cle === premier.cle) || blocs[0];
    actif.tab.classList.add("actif"); actif.bloc.classList.add("actif");
    section.appendChild(tabs); section.appendChild(selections);
  }
  section.appendChild(construitDetails(m));

  const boutonRepli = section.querySelector(".bouton-repli");
  boutonRepli.addEventListener("click", () => {
    const replie = section.classList.toggle("carte-repliee"); boutonRepli.setAttribute("aria-expanded", String(!replie));
    boutonRepli.firstChild.textContent = replie ? "Déplier " : "Replier "; boutonRepli.querySelector("span").textContent = replie ? "⌄" : "⌃";
  });
  return section;
}
function afficheSelections(matchs) {
  const root = document.getElementById("matches"), maj = document.getElementById("maj"); root.innerHTML = "";
  const retenus = regroupeMatchs(matchs).filter(estArchetypeGo).sort((a, b) => `${a.date || ""}${a.heure_cameroun || a.heure || ""}`.localeCompare(`${b.date || ""}${b.heure_cameroun || b.heure || ""}`));
  maj.textContent = retenus.length ? `${retenus.length} match${retenus.length > 1 ? "s" : ""} analysé${retenus.length > 1 ? "s" : ""} aujourd'hui` : "Aucune sélection pour le moment";
  if (!retenus.length) { root.innerHTML = `<div class="etat-vide"><strong>Aucune sélection pour le moment</strong><p>Aucun match ne remplit actuellement tous les critères du modèle. Le système préfère ne rien proposer plutôt que de forcer une sélection.</p></div>`; return; }
  retenus.forEach((m, index) => {
    const carte = construitCarte(m);
    // Un seul match est ouvert à l'arrivée : la page reste compacte et chaque autre carte peut être dépliée à la demande.
    if (index > 0) {
      carte.classList.add("carte-repliee");
      const bouton = carte.querySelector(".bouton-repli");
      if (bouton) { bouton.setAttribute("aria-expanded", "false"); bouton.firstChild.textContent = "Déplier "; bouton.querySelector("span").textContent = "⌄"; }
    }
    root.appendChild(carte);
  });
}
if (document.getElementById("matches")) {
  fetch(`precalcul_leger.json?_=${Date.now()}`)
    .then(r => { if (!r.ok) throw new Error(`precalcul_leger.json introuvable (${r.status})`); return r.json(); })
    .then(d => afficheSelections(d.signaux || []))
    .catch(e => { document.getElementById("maj").textContent = "Erreur de chargement : " + e.message; console.error(e); });
}
