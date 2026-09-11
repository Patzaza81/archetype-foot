// archetype.js — présentation uniquement.
// Le navigateur ne choisit aucun pronostic et ne calcule aucune statistique.

const RANGS = [
  { cle: "P1", classe: "rang-1", icone: "♛", titre: "Le meilleur choix", sousTitre: "Pronostic principal" },
  { cle: "P2", classe: "rang-2", icone: "◆", titre: "Meilleure rentabilité", sousTitre: "Deuxième choix" },
  { cle: "P3", classe: "rang-3", icone: "+", titre: "Pronostic bonus", sousTitre: "Troisième choix" },
];

function estArchetypeGo(m) {
  return !!(m && m.moteur_utilise === "archetype_model" && m.archetype_model &&
    m.archetype_model.statut === "OK" && m.archetype_model.selection && m.archetype_model.selection.P1);
}

function echappeHtml(x) {
  return x === null || x === undefined ? "" : String(x)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function formatCote(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n.toFixed(2).replace(".", ",") : "—";
}
function formatPct(x) {
  const n = Number(x);
  return Number.isFinite(n) ? `${(n * 100).toFixed(1).replace(".", ",")} %` : "—";
}
function formatPctEntier(x) {
  const n = Number(x);
  return Number.isFinite(n) ? `${Math.round(n * 100)} %` : "—";
}
function formatDate(dateIso) {
  if (!dateIso) return "";
  const d = new Date(`${dateIso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return dateIso;
  return d.toLocaleDateString("fr-FR", { weekday: "long", day: "2-digit", month: "short", year: "numeric" })
    .replace(/\./g, "").replace(/^./, c => c.toUpperCase());
}
function initialesEquipe(nom) {
  const mots = String(nom || "?").trim().split(/\s+/).filter(Boolean);
  if (!mots.length) return "?";
  return mots.length === 1 ? mots[0].slice(0, 2).toUpperCase() : (mots[0][0] + mots[mots.length - 1][0]).toUpperCase();
}
function traduitConfiance(niveau) {
  const map = {
    PREMIUM: [5, "Exceptionnelle"], TRES_FORT: [4, "Très forte"], FORT: [3, "Forte"],
    ELIGIBLE: [2, "Correcte"], ELIGIBLE_PLUS: [1, "Suffisante"],
  };
  return map[niveau] || [1, "Suffisante"];
}
function construitJauge(probabilite) {
  const n = Number(probabilite);
  if (!Number.isFinite(n)) return "";
  const v = Math.max(0, Math.min(1, n));
  const r = 31, c = 2 * Math.PI * r;
  return `<div class="jauge" aria-label="${Math.round(v * 100)} % de chances de réussite"><svg viewBox="0 0 76 76" aria-hidden="true"><circle class="fond" cx="38" cy="38" r="${r}"></circle><circle class="valeur" cx="38" cy="38" r="${r}" stroke-dasharray="${c.toFixed(2)}" stroke-dashoffset="${(c * (1 - v)).toFixed(2)}"></circle></svg><strong>${Math.round(v * 100)}%</strong></div>`;
}
function construitPourquoi(candidat) {
  const j = candidat && candidat.justification;
  const morceaux = [];
  if (j && j.resume) morceaux.push(`<p class="resume-preuve">${echappeHtml(j.resume)}</p>`);
  if (j && Array.isArray(j.preuves)) {
    j.preuves.forEach(p => {
      if (!p || !p.texte) return;
      morceaux.push(`<div class="preuve"><span class="preuve-titre">${echappeHtml(p.titre || "Statistique clé")}</span><span class="preuve-texte">${echappeHtml(p.texte)}</span></div>`);
    });
  }
  if (morceaux.length) return morceaux.join("");
  return `<p class="resume-preuve">Cette sélection ressort de la convergence des analyses statistiques du match.</p>`;
}
function construitBlocCandidat(info, candidat, equipes) {
  if (!candidat) return null;
  const article = document.createElement("article");
  article.className = `selection ${info.classe}`;
  const [etoiles, confiance] = traduitConfiance(candidat.niveau);
  const stars = "★".repeat(etoiles) + `<span class="etoiles-vides">${"★".repeat(5 - etoiles)}</span>`;
  const libelle = traduitMarche(candidat.marche, equipes);
  article.innerHTML = `<div class="selection-inner">
    <div class="selection-head"><span class="icone-rang" aria-hidden="true">${info.icone}</span><div><div class="rang-titre">${echappeHtml(info.titre)}</div><div class="rang-sous-titre">${echappeHtml(info.sousTitre)}</div></div></div>
    <h2 class="libelle-marche">${echappeHtml(libelle)}</h2>
    ${candidat.justification && candidat.justification.resume ? `<p class="resume-marche">${echappeHtml(candidat.justification.resume)}</p>` : ""}
    <div class="donnees-principales"><div><span class="etiquette">Cote</span><strong class="cote">${formatCote(candidat.cote)}</strong><span class="etiquette" style="margin-top:12px">Chances de réussite</span><strong>${formatPctEntier(candidat.probabilite)}</strong><span class="etiquette">estimées par le modèle</span></div>${construitJauge(candidat.probabilite)}</div>
    <div class="ligne-confiance"><span class="etoiles">${stars}</span><span><strong>Confiance</strong> · ${echappeHtml(confiance)}</span></div>
    <div class="bloc-pourquoi"><div class="titre">Pourquoi ce choix ?</div>${construitPourquoi(candidat)}</div>
    <div class="metriques"><div class="metrique"><span>Avantage potentiel</span><strong>${formatPct(candidat.edge)}</strong></div><div class="metrique"><span>Gain potentiel</span><strong>${formatPct(candidat.edv)}</strong></div></div>
  </div>`;
  return article;
}
function construitDetails(m) {
  const details = document.createElement("details");
  details.className = "details-analyse";
  const selection = (m.archetype_model && m.archetype_model.selection) || {};
  const lignes = [];
  RANGS.forEach(r => {
    const c = selection[r.cle];
    if (!c) return;
    lignes.push(`<div class="ligne-detail"><span class="cle">${echappeHtml(r.titre)}</span><span class="val">${echappeHtml(c.marche || "—")}</span></div>`);
    lignes.push(`<div class="ligne-detail"><span class="cle">Niveau</span><span class="val">${echappeHtml(c.niveau || "—")}</span></div>`);
    lignes.push(`<div class="ligne-detail"><span class="cle">Stabilité</span><span class="val">${echappeHtml(c.robustesse || "—")}</span></div>`);
  });
  details.innerHTML = `<summary><span><span class="details-titre">Détails de l'analyse</span><span class="details-sous-titre">Éléments techniques ayant accompagné la sélection</span></span><span class="chevron">⌄</span></summary><div class="contenu-details">${lignes.join("") || "Aucun détail technique disponible."}</div>`;
  return details;
}
function construitCarte(m) {
  const section = document.createElement("section");
  section.className = "carte-match";
  const equipes = { domicile: m.domicile || "Équipe à domicile", exterieur: m.exterieur || "Équipe à l'extérieur" };
  const heure = m.heure_cameroun || m.heure || "—";
  const date = formatDate(m.date);
  const competition = String(m.competition || "").replace(/\s+/g, " ").trim();
  section.innerHTML = `<header class="entete-match"><div class="ligne-match"><div class="equipe domicile"><span class="ecusson-equipe">${echappeHtml(initialesEquipe(equipes.domicile))}</span><span>${echappeHtml(equipes.domicile)}</span></div><div class="bloc-horaire"><strong>${echappeHtml(heure)}</strong><span>${echappeHtml(date)}</span></div><div class="equipe exterieur"><span>${echappeHtml(equipes.exterieur)}</span><span class="ecusson-equipe">${echappeHtml(initialesEquipe(equipes.exterieur))}</span></div></div>${competition ? `<div class="competition">● &nbsp;${echappeHtml(competition)}</div>` : ""}</header>`;
  const selection = (m.archetype_model && m.archetype_model.selection) || {};
  const selections = document.createElement("div"); selections.className = "selections";
  RANGS.forEach(info => { const bloc = construitBlocCandidat(info, selection[info.cle], equipes); if (bloc) selections.appendChild(bloc); });
  section.appendChild(selections);
  section.appendChild(construitDetails(m));
  return section;
}
function afficheSelections(matchs) {
  const root = document.getElementById("matches"), maj = document.getElementById("maj");
  root.innerHTML = "";
  const retenus = (matchs || []).filter(estArchetypeGo).sort((a, b) => `${a.date || ""}${a.heure_cameroun || a.heure || ""}`.localeCompare(`${b.date || ""}${b.heure_cameroun || b.heure || ""}`));
  maj.textContent = retenus.length ? `${retenus.length} match${retenus.length > 1 ? "s" : ""} analysé${retenus.length > 1 ? "s" : ""} aujourd'hui` : "Aucune sélection pour le moment";
  if (!retenus.length) { root.innerHTML = `<div class="etat-vide"><strong>Aucune sélection pour le moment</strong><p>Aucun match ne remplit actuellement tous les critères du modèle. Le système préfère ne rien proposer plutôt que de forcer une sélection.</p></div>`; return; }
  retenus.forEach(m => root.appendChild(construitCarte(m)));
}
fetch(`precalcul_leger.json?_=${Date.now()}`).then(r => { if (!r.ok) throw new Error(`precalcul_leger.json introuvable (${r.status})`); return r.json(); }).then(d => afficheSelections(d.signaux || [])).catch(e => { document.getElementById("maj").textContent = "Erreur de chargement : " + e.message; console.error(e); });
