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
function echappeHtml(x) { return x === null || x === undefined ? "" : String(x).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\"/g, "&quot;").replace(/'/g, "&#39;"); }
function formatCote(x) { const n = Number(x); return Number.isFinite(n) ? n.toFixed(2).replace(".", ",") : "—"; }
function formatPct(x) { const n = Number(x); return Number.isFinite(n) ? `${(n * 100).toFixed(1).replace(".", ",")} %` : "—"; }
function formatPctEntier(x) { const n = Number(x); return Number.isFinite(n) ? `${Math.round(n * 100)} %` : "—"; }
function formatDate(dateIso) { if (!dateIso) return ""; const d = new Date(`${dateIso}T12:00:00`); if (Number.isNaN(d.getTime())) return dateIso; return d.toLocaleDateString("fr-FR", { weekday: "long", day: "2-digit", month: "short", year: "numeric" }).replace(/\./g, "").replace(/^./, c => c.toUpperCase()); }
function initialesEquipe(nom) { const mots = String(nom || "?").trim().split(/\s+/).filter(Boolean); if (!mots.length) return "?"; return mots.length === 1 ? mots[0].slice(0, 2).toUpperCase() : (mots[0][0] + mots[mots.length - 1][0]).toUpperCase(); }
function traduitConfiance(niveau) {
  const map = {
    PREMIUM: [5, "Éligibilité maximale"], TRES_FORT: [4, "Éligibilité très forte"], FORT: [3, "Éligibilité forte"],
    ELIGIBLE: [2, "Éligibilité validée"], ELIGIBLE_PLUS: [1, "Éligibilité minimale"],
  };
  return map[niveau] || [1, "Éligibilité minimale"];
}
function construitJauge(probabilite) { const n = Number(probabilite); if (!Number.isFinite(n)) return ""; const v = Math.max(0, Math.min(1, n)); const r = 31, c = 2 * Math.PI * r; return `<div class="jauge" aria-label="Probabilité du modèle : ${Math.round(v * 100)} %"><svg viewBox="0 0 76 76" aria-hidden="true"><circle class="fond" cx="38" cy="38" r="${r}"></circle><circle class="valeur" cx="38" cy="38" r="${r}" stroke-dasharray="${c.toFixed(2)}" stroke-dashoffset="${(c * (1 - v)).toFixed(2)}"></circle></svg><strong>${Math.round(v * 100)}%</strong></div>`; }
function construitPourquoi(candidat) { const j = candidat && candidat.justification; const morceaux = []; if (j && j.resume) morceaux.push(`<p class="resume-preuve">${echappeHtml(j.resume)}</p>`); if (j && Array.isArray(j.preuves)) j.preuves.forEach(p => { if (p && p.texte) morceaux.push(`<div class="preuve"><span class="preuve-titre">${echappeHtml(p.titre || "Statistique clé")}</span><span class="preuve-texte">${echappeHtml(p.texte)}</span></div>`); }); return morceaux.length ? morceaux.join("") : `<p class="resume-preuve">Cette sélection ressort de la convergence des analyses statistiques du match.</p>`; }
function construitBlocCandidat(info, candidat, equipes) {
  if (!candidat) return null;
  const article = document.createElement("article"); article.className = `selection ${info.classe}`;
  const [etoiles, niveau] = traduitConfiance(candidat.niveau); const stars = "★".repeat(etoiles) + `<span class="etoiles-vides">${"★".repeat(5 - etoiles)}</span>`; const libelle = traduitMarche(candidat.marche, equipes);
  article.innerHTML = `<div class="selection-inner"><div class="selection-head"><span class="icone-rang" aria-hidden="true">${info.icone}</span><div><div class="rang-titre">${echappeHtml(info.titre)}</div><div class="rang-sous-titre">${echappeHtml(info.sousTitre)}</div></div></div><h2 class="libelle-marche">${echappeHtml(libelle)}</h2>${candidat.justification && candidat.justification.resume ? `<p class="resume-marche">${echappeHtml(candidat.justification.resume)}</p>` : ""}<div class="donnees-principales"><div><span class="etiquette">Cote</span><strong class="cote">${formatCote(candidat.cote)}</strong><span class="etiquette" style="margin-top:12px">Probabilité du modèle</span><strong>${formatPctEntier(candidat.probabilite)}</strong><span class="etiquette">estimation statistique, non garantie</span></div>${construitJauge(candidat.probabilite)}</div><div class="ligne-confiance"><span class="etoiles">${stars}</span><span><strong>${echappeHtml(niveau)}</strong></span></div><div class="bloc-pourquoi"><div class="titre">Pourquoi ce choix ?</div>${construitPourquoi(candidat)}</div><div class="metriques"><div class="metrique"><span>Avantage potentiel</span><strong>${formatPct(candidat.edge)}</strong></div><div class="metrique"><span>Gain potentiel</span><strong>${formatPct(candidat.edv)}</strong></div></div></div>`;
  return article;
}
function construitDetails(m) { const details = document.createElement("details"); details.className = "details-analyse"; const selection = (m.archetype_model && m.archetype_model.selection) || {}; const lignes = []; RANGS.forEach(r => { const c = selection[r.cle]; if (!c) return; lignes.push(`<div class="ligne-detail"><span class="cle">${echappeHtml(r.titre)}</span><span class="val">${echappeHtml(c.marche || "—")}</span></div>`); lignes.push(`<div class="ligne-detail"><span class="cle">Niveau d'éligibilité</span><span class="val">${echappeHtml(c.niveau || "—")}</span></div>`); lignes.push(`<div class="ligne-detail"><span class="cle">Stabilité</span><span class="val">${echappeHtml(c.robustesse || "—")}</span></div>`); }); details.innerHTML = `<summary><span><span class="details-titre">Détails de l'analyse</span><span class="details-sous-titre">Éléments techniques ayant accompagné la sélection</span></span><span class="chevron">⌄</span></summary><div class="contenu-details">${lignes.join("") || "Aucun détail technique disponible."}</div>`; return details; }
function identiteMatch(m) { if (m && m.match_id !== undefined && m.match_id !== null && String(m.match_id).trim() !== "") return `id:${String(m.match_id)}`; return `match:${String(m?.date || "").trim()}|${String(m?.heure_cameroun || m?.heure || "").trim()}|${String(m?.domicile || "").trim().toLowerCase()}|${String(m?.exterieur || "").trim().toLowerCase()}`; }
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
function construitCarte(m) {
  const section = document.createElement("section"); section.className = "carte-match";
  const equipes = { domicile: m.domicile || "Équipe à domicile", exterieur: m.exterieur || "Équipe à l'extérieur" }; const heure = m.heure_cameroun || m.heure || "—"; const date = formatDate(m.date); const competition = String(m.competition || "").replace(/\s+/g, " ").trim();
  section.innerHTML = `<header class="entete-match"><div class="ligne-match"><div class="equipe domicile"><span class="ecusson-equipe">${echappeHtml(initialesEquipe(equipes.domicile))}</span><span>${echappeHtml(equipes.domicile)}</span></div><div class="bloc-horaire"><strong>${echappeHtml(heure)}</strong><span>${echappeHtml(date)}</span></div><div class="equipe exterieur"><span>${echappeHtml(equipes.exterieur)}</span><span class="ecusson-equipe">${echappeHtml(initialesEquipe(equipes.exterieur))}</span></div></div>${competition ? `<div class="competition">● &nbsp;${echappeHtml(competition)}</div>` : ""}<button type="button" class="bouton-repli" aria-expanded="true">Replier <span aria-hidden="true">⌃</span></button></header>`;
  const boutonRepli = section.querySelector(".bouton-repli");
  const selections = document.createElement("div"); selections.className = "contenu-carte";
  const selection = (m.archetype_model && m.archetype_model.selection) || {};
  const blocs = RANGS.map(info => construitBlocCandidat(info, selection[info.cle], equipes)).filter(Boolean);
  blocs.forEach(bloc => selections.appendChild(bloc));
  section.appendChild(selections); section.appendChild(construitDetails(m));
  boutonRepli.addEventListener("click", () => { const replie = section.classList.toggle("carte-repliee"); boutonRepli.setAttribute("aria-expanded", String(!replie)); boutonRepli.firstChild.textContent = replie ? "Déplier " : "Replier "; boutonRepli.querySelector("span").textContent = replie ? "⌄" : "⌃"; });
  return section;
}
function afficheSelections(matchs) {
  const root = document.getElementById("matches"), maj = document.getElementById("maj"); root.innerHTML = "";
  const retenus = regroupeMatchs(matchs).filter(estArchetypeGo).sort((a, b) => `${a.date || ""}${a.heure_cameroun || a.heure || ""}`.localeCompare(`${b.date || ""}${b.heure_cameroun || b.heure || ""}`));
  maj.textContent = retenus.length ? `${retenus.length} match${retenus.length > 1 ? "s" : ""} analysé${retenus.length > 1 ? "s" : ""} aujourd'hui` : "Aucune sélection pour le moment";
  if (!retenus.length) { root.innerHTML = `<div class="etat-vide"><strong>Aucune sélection pour le moment</strong><p>Aucun match ne remplit actuellement tous les critères du modèle. Le système préfère ne rien proposer plutôt que de forcer une sélection.</p></div>`; return; }
  retenus.forEach(m => root.appendChild(construitCarte(m)));
}
if (document.getElementById("matches")) { fetch(`precalcul_leger.json?_=${Date.now()}`).then(r => { if (!r.ok) throw new Error(`precalcul_leger.json introuvable (${r.status})`); return r.json(); }).then(d => afficheSelections(d.signaux || [])).catch(e => { document.getElementById("maj").textContent = "Erreur de chargement : " + e.message; console.error(e); }); }
