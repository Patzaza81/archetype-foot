// systeme.js — présentation uniquement, aucun calcul.
// Affiche l’état statistique du système et la comparaison V2.6.10 / V3.

function formatPctSysteme(x) {
  const n = Number(x);
  return Number.isFinite(n) ? `${(n * 100).toFixed(1).replace(".", ",")} %` : "—";
}

function echappeHtmlSysteme(x) {
  return x === null || x === undefined ? "" : String(x)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function construitBlocGlobal(bilan) {
  const g = (bilan && bilan.global) || {};
  const div = document.createElement("div");
  div.className = "bloc-systeme";
  div.innerHTML = `
    <h2>Bilan comportemental global</h2>
    <div class="grille-stats">
      <div class="stat"><span class="etiquette">Observations résolues</span><strong>${g.observations ?? 0}</strong></div>
      <div class="stat"><span class="etiquette">Gagnées</span><strong>${g.gagnes ?? 0}</strong></div>
      <div class="stat"><span class="etiquette">Perdues</span><strong>${g.perdus ?? 0}</strong></div>
      <div class="stat"><span class="etiquette">ROI (mise flat)</span><strong>${g.roi_flat === null || g.roi_flat === undefined ? "—" : formatPctSysteme(g.roi_flat)}</strong></div>
    </div>`;
  return div;
}

function construitTableauFamilles(bilan) {
  const parFamille = (bilan && bilan.par_famille) || {};
  const familles = Object.keys(parFamille);
  const div = document.createElement("div");
  div.className = "bloc-systeme";
  if (!familles.length) {
    div.innerHTML = `<h2>Par famille de marché</h2><p class="etat-vide-systeme">Aucune observation résolue pour l'instant.</p>`;
    return div;
  }
  const lignes = familles.map((famille) => {
    const r = parFamille[famille].resume || {};
    return `<tr><td>${echappeHtmlSysteme(famille)}</td><td>${r.observations ?? 0}</td><td>${r.gagnes ?? 0}</td><td>${r.perdus ?? 0}</td><td>${r.roi_flat === null || r.roi_flat === undefined ? "—" : formatPctSysteme(r.roi_flat)}</td></tr>`;
  }).join("");
  div.innerHTML = `<h2>Par famille de marché</h2>
    <table class="tableau-systeme"><thead><tr><th>Famille</th><th>Obs.</th><th>Gagnées</th><th>Perdues</th><th>ROI</th></tr></thead><tbody>${lignes}</tbody></table>`;
  return div;
}

function construitBlocComparaisonMoteurs(d) {
  const v2 = d.v2 || {}, v3 = d.v3 || {}, c = d.comparaison || {}, cal = d.calibration_v3 || {};
  const pct = c.taux_accord_sur_matchs_communs == null ? "—" : (c.taux_accord_sur_matchs_communs * 100).toFixed(1).replace(".", ",") + " %";
  const div = document.createElement("section");
  div.className = "bloc-systeme";
  div.innerHTML = `
    <h2>Comparaison des moteurs</h2>
    <p style="margin:0 0 9px;font-size:12.5px;color:var(--text-secondary)">V2.6.10 est le moteur actif. V3 fonctionne en production parallèle. Cette page est la seule publication du comparatif.</p>
    <div class="grille-stats">
      <div class="stat"><span class="etiquette">Choix V2.6.10</span><strong>${v2.choix ?? 0}</strong></div>
      <div class="stat"><span class="etiquette">Choix V3</span><strong>${v3.choix ?? 0}</strong></div>
      <div class="stat"><span class="etiquette">Accord marchés</span><strong>${pct}</strong></div>
      <div class="stat"><span class="etiquette">Divergences</span><strong>${c.divergence_marche ?? 0}</strong></div>
    </div>
    <p style="margin:9px 0 0;font-size:12px;color:var(--text-secondary)">Calibration V3 : ${cal.prete ? "prête" : "en attente"} · Matchs communs : ${c.matchs_communs ?? 0}.</p>`;
  return div;
}


function construitBlocIntelligenceSelection(d) {
  const evo = d.evolution || {};
  const moteurs = evo.moteurs || {};
  const marches = evo.marches || {};
  const lignes = Object.keys(moteurs).map(function(k) {
    const x = moteurs[k] || {};
    const taux = x.taux_reussite == null ? "—" : formatPctSysteme(x.taux_reussite);
    const lcb = x.borne_basse_95 == null ? "—" : formatPctSysteme(x.borne_basse_95);
    const roi = x.roi == null ? "—" : formatPctSysteme(x.roi);
    return "<tr><td><b>" + echappeHtmlSysteme(k) + "</b></td><td>" + (x.observations ?? 0) +
      "</td><td>" + taux + "</td><td>" + lcb + "</td><td>" + roi + "</td></tr>";
  }).join("");
  const familles = {};
  Object.keys(marches).forEach(function(k) {
    const x = marches[k] || {};
    const fam = String(x.marche || "").split("_")[0] || "marché";
    familles[fam] = (familles[fam] || 0) + Number(x.observations || 0);
  });
  const div = document.createElement("section");
  div.className = "bloc-systeme";
  div.innerHTML = "<h2>Intelligence de sélection</h2>" +
    "<p style=\"margin:0 0 9px;font-size:12.5px;color:var(--text-secondary)\">Les deux moteurs coexistent. La sélection cherche où chacun apporte un avantage réel ; le Journal apporte une troisième source indépendante. La marge de succès est la probabilité estimée moins la probabilité implicite de la cote. Pour le Journal, la probabilité est lissée (réglable ou retour à Wilson dans config/journal_calibrage.json).</p>" +
    "<div class=\"grille-stats\">" +
      "<div class=\"stat\"><span class=\"etiquette\">Moteurs suivis</span><strong>" + Object.keys(moteurs).length + "</strong></div>" +
      "<div class=\"stat\"><span class=\"etiquette\">Marchés suivis</span><strong>" + Object.keys(marches).length + "</strong></div>" +
      "<div class=\"stat\"><span class=\"etiquette\">V2.6.10 résolu</span><strong>" + ((moteurs.moteur_v2_6_10 || {}).observations ?? 0) + "</strong></div>" +
      "<div class=\"stat\"><span class=\"etiquette\">V3 résolu</span><strong>" + ((moteurs.moteur_v3 || {}).observations ?? 0) + "</strong></div>" +
    "</div>" +
    (lignes ? "<div style=\"overflow-x:auto;margin-top:10px\"><table class=\"tableau-systeme\"><thead><tr><th>Moteur</th><th>Résolus</th><th>Réussite</th><th>Borne 95 %</th><th>ROI</th></tr></thead><tbody>" + lignes + "</tbody></table></div>" : "") +
    "<p style=\"margin:9px 0 0;font-size:11.5px;color:var(--text-secondary)\">Ordre de sélection : preuve empirique → marge de succès → marge modèle → probabilité → EDV → taille d'échantillon. Aucun coefficient arbitraire.</p>" + (Object.keys(marches).length ? "<div style=\"overflow-x:auto;margin-top:10px\"><table class=\"tableau-systeme\"><thead><tr><th>Moteur</th><th>Marché</th><th>Obs.</th><th>Réussite</th><th>Borne 95 %</th><th>ROI</th></tr></thead><tbody>" + Object.keys(marches).sort(function(a,b){return Number((marches[b]||{}).observations||0)-Number((marches[a]||{}).observations||0)}).slice(0,20).map(function(k){var x=marches[k]||{};return "<tr><td>"+echappeHtmlSysteme(x.moteur||"—")+"</td><td>"+echappeHtmlSysteme(x.marche||"—")+"</td><td>"+(x.observations??0)+"</td><td>"+(x.taux_reussite==null?"—":formatPctSysteme(x.taux_reussite))+"</td><td>"+(x.borne_basse_95==null?"—":formatPctSysteme(x.borne_basse_95))+"</td><td>"+(x.roi==null?"—":formatPctSysteme(x.roi))+"</td></tr>"}).join("")+"</tbody></table></div>" : "") + (Object.keys(evo.avantage_par_marche || {}).length ? "<div style=\"overflow-x:auto;margin-top:10px\"><table class=\"tableau-systeme\"><thead><tr><th>Marché</th><th>Avantage empirique</th></tr></thead><tbody>" + Object.keys(evo.avantage_par_marche).slice(0,20).map(function(k){var x=evo.avantage_par_marche[k]||{};return "<tr><td>"+echappeHtmlSysteme(k)+"</td><td>"+echappeHtmlSysteme(x.meilleur||"Données insuffisantes")+"</td></tr>"}).join("")+"</tbody></table></div>" : "");
  return div;
}

function construitBlocSuiviTickets(d) {
  const b = d.bilan || {}, c = b.comptes || {}, sc = b.par_scenario || {}, src = b.par_source || {};
  const pc = function(x) { return x == null ? "—" : formatPctSysteme(x); };
  const lignesPlans = [];
  Object.keys(sc).forEach(function(nom) {
    const plans = sc[nom].plans || {};
    Object.keys(plans).forEach(function(pn) {
      const p = plans[pn];
      lignesPlans.push("<tr><td>" + echappeHtmlSysteme(nom) + "</td><td>" + echappeHtmlSysteme(pn) + "</td><td>" + p.tickets_regles +
        "</td><td>" + pc(p.proba_profit_prevue) + "</td><td>" + pc(p.taux_rentable_observe) + "</td><td>" + pc(p.esperance_prevue) + "</td><td>" + pc(p.roi_observe) + "</td></tr>");
    });
  });
  const lignesScen = Object.keys(sc).map(function(nom) {
    const x = sc[nom];
    const err = Object.keys(x.erreurs || {}).map(function(k) { return k + " err. : " + x.erreurs[k]; }).join(" · ");
    return "<tr><td>" + echappeHtmlSysteme(nom) + "</td><td>" + x.tickets_regles + "</td><td>" + String(x.justes_attendus).replace(".", ",") +
      " / " + x.paris + "</td><td>" + x.justes_observes + " / " + x.paris + "</td><td>" + echappeHtmlSysteme(err) + "</td></tr>";
  }).join("");
  const lignesSrc = Object.keys(src).map(function(k) {
    return "<tr><td>" + echappeHtmlSysteme(k) + "</td><td>" + src[k].paris + "</td><td>" + pc(src[k].proba_moyenne_estimee) + "</td><td>" + pc(src[k].taux_reussite) + "</td></tr>";
  }).join("");
  const recents = (d.recents || []).slice(0, 12).map(function(e) {
    const r = e.resultat || {};
    const res = e.statut === "RESOLVED" ? (r.paris_justes + " justes, " + r.erreurs + " erreur(s)") : (e.statut === "EXCLU" ? "exclu" : "en attente");
    return "<tr><td>" + echappeHtmlSysteme(e.date) + "</td><td>" + echappeHtmlSysteme(e.scenario) + "</td><td>" + e.paris + "</td><td>" + echappeHtmlSysteme(res) + "</td></tr>";
  }).join("");
  const table = function(tete, lignes) { return lignes ? "<div style=\"overflow-x:auto;margin-top:10px\"><table class=\"tableau-systeme\"><thead><tr>" + tete.map(function(t) { return "<th>" + t + "</th>"; }).join("") + "</tr></thead><tbody>" + lignes + "</tbody></table></div>" : ""; };
  const div = document.createElement("section");
  div.className = "bloc-systeme";
  div.innerHTML = "<h2>Suivi des tickets générés</h2>" +
    "<p style=\"margin:0 0 9px;font-size:12.5px;color:var(--text-secondary)\">Chaque ticket généré est enregistré puis réglé avec les scores réels. On compare ce que le moteur prévoyait (paris justes, chance d'être rentable) à ce qui s'est passé. Les tickets à cote choisie dans le navigateur ne sont pas suivis.</p>" +
    "<div class=\"grille-stats\">" +
      "<div class=\"stat\"><span class=\"etiquette\">Enregistrés</span><strong>" + (c.total ?? 0) + "</strong></div>" +
      "<div class=\"stat\"><span class=\"etiquette\">Réglés</span><strong>" + (c.regles ?? 0) + "</strong></div>" +
      "<div class=\"stat\"><span class=\"etiquette\">En attente</span><strong>" + (c.en_attente ?? 0) + "</strong></div>" +
      "<div class=\"stat\"><span class=\"etiquette\">Exclus</span><strong>" + (c.exclus ?? 0) + "</strong></div>" +
    "</div>" +
    table(["Scénario", "Réglés", "Justes prévus", "Justes observés", "Erreurs"], lignesScen) +
    table(["Scénario", "Plan", "Réglés", "Rentable prévu", "Rentable observé", "Gain prévu", "ROI observé"], lignesPlans) +
    table(["Source", "Paris", "Proba estimée", "Réussite"], lignesSrc) +
    table(["Date", "Scénario", "Paris", "Résultat"], recents) +
    "<p style=\"margin:9px 0 0;font-size:11.5px;color:var(--text-secondary)\">" + echappeHtmlSysteme(b.avertissement || "") + " « Rentable » = mise au moins remboursée.</p>";
  return div;
}

function afficheEtatSysteme(etat) {
  const racine = document.getElementById("contenu-systeme");
  const maj = document.getElementById("maj-systeme");
  racine.innerHTML = "";
  maj.textContent = etat.genere_le ? `Dernière mise à jour : ${new Date(etat.genere_le).toLocaleString("fr-FR")}` : "";

  racine.appendChild(construitBlocGlobal(etat.bilan_comportemental));
  racine.appendChild(construitTableauFamilles(etat.bilan_comportemental));
  if (etat.comparaison_moteurs && Object.keys(etat.comparaison_moteurs).length) racine.appendChild(construitBlocComparaisonMoteurs(etat.comparaison_moteurs));
  if (etat.selection_intelligence && Object.keys(etat.selection_intelligence).length) racine.appendChild(construitBlocIntelligenceSelection(etat.selection_intelligence));
  if (etat.suivi_tickets && etat.suivi_tickets.bilan && Object.keys(etat.suivi_tickets.bilan).length) racine.appendChild(construitBlocSuiviTickets(etat.suivi_tickets));
  if (window.__controleSaisons) racine.insertBefore(construitBlocControleSaisons(window.__controleSaisons), racine.firstChild);
  if (window.__controleFootballData) racine.insertBefore(construitBlocControleFootballData(window.__controleFootballData), racine.firstChild);
}

fetch(`etat_systeme.json?_=${Date.now()}`)
  .then((r) => { if (!r.ok) throw new Error(`etat_systeme.json introuvable (${r.status})`); return r.json(); })
  .then(afficheEtatSysteme)
  .catch((e) => {
    document.getElementById("maj-systeme").textContent = "Erreur de chargement : " + e.message;
    console.error(e);
  });

/* AJOUT 24/09/2026 — Contrôle des données de saison (controle_saisons.py, workflow journal.yml).
   Bloc indépendant : il s'affiche même si etat_systeme.json est indisponible, et son échec n'affecte pas le reste. */
function construitBlocControleSaisons(rapport) {
  const div = document.createElement("section");
  div.className = "bloc-systeme";
  div.id = "bloc-controle-saisons";
  const r = rapport.resume || {};
  const taux = r.taux_incoherence === null || r.taux_incoherence === undefined ? "—" : formatPctSysteme(r.taux_incoherence);
  const lignes = (rapport.incoherentes || []).map((l) => {
    const manq = (l.manquants || []).map((m) =>
      `${echappeHtmlSysteme(m.date.slice(8, 10) + "/" + m.date.slice(5, 7))} ${echappeHtmlSysteme(m.lieu === "domicile" ? "dom." : "ext.")} ` +
      `contre ${echappeHtmlSysteme(m.adversaire)} (${echappeHtmlSysteme(m.score_equipe)})`).join("<br>");
    return `<tr><td><b>${echappeHtmlSysteme(l.equipe)}</b><br><span style="color:var(--text-secondary)">${echappeHtmlSysteme(l.competition)}</span></td>` +
      `<td>${l.matchs_enregistres}</td><td>${manq}</td></tr>`;
  }).join("");
  div.innerHTML = `<h2>Contrôle des données de saison</h2>
    <p style="margin:0 0 9px;font-size:12.5px;color:var(--text-secondary)">Chaque match connu par les pages de match doit figurer dans la saison enregistrée de l'équipe (même compétition, même lieu, même score). Sinon la saison enregistrée est fausse et le moteur analyse l'équipe sur de mauvais chiffres. Contrôle du ${echappeHtmlSysteme(rapport.genere_le || "—")}.</p>
    <div class="grille-stats">
      <div class="stat"><span class="etiquette">Équipes vérifiables</span><strong>${r.verifiables ?? 0}</strong></div>
      <div class="stat"><span class="etiquette">Cohérentes</span><strong style="color:var(--green)">${r.coherentes ?? 0}</strong></div>
      <div class="stat"><span class="etiquette">Incohérentes</span><strong style="color:var(--red)">${r.incoherentes ?? 0}</strong></div>
      <div class="stat"><span class="etiquette">Taux d'erreur</span><strong style="color:var(--red)">${taux}</strong></div>
    </div>` + (lignes ? `<div style="overflow-x:auto;margin-top:10px"><table class="tableau-systeme"><thead><tr><th>Équipe</th><th>Matchs enregistrés</th><th>Match réel absent de la saison enregistrée</th></tr></thead><tbody>${lignes}</tbody></table></div>`
      : `<p class="etat-vide-systeme">Aucune incohérence détectée.</p>`);
  return div;
}

fetch(`controle_saisons.json?_=${Date.now()}`)
  .then((r) => { if (!r.ok) throw new Error(`controle_saisons.json introuvable (${r.status})`); return r.json(); })
  .then((rapport) => {
    window.__controleSaisons = rapport;
    const racine = document.getElementById("contenu-systeme");
    const ancien = document.getElementById("bloc-controle-saisons");
    if (ancien) ancien.remove();
    racine.insertBefore(construitBlocControleSaisons(rapport), racine.firstChild);
  })
  .catch((e) => console.error(e));


/* AJOUT 24/09/2026 — A4 : contrôle qualité Football-Data (controle_football_data.py). Bloc indépendant. */
function construitBlocControleFootballData(rapport) {
  const div = document.createElement("section");
  div.className = "bloc-systeme";
  div.id = "bloc-controle-football-data";
  const r = rapport.resume || {};
  const taux = r.taux_accord === null || r.taux_accord === undefined ? "—" : formatPctSysteme(r.taux_accord);
  const lignes = (rapport.desaccords || []).map((d) =>
    `<tr><td><b>${echappeHtmlSysteme(d.match)}</b><br><span style="color:var(--text-secondary)">${echappeHtmlSysteme(d.division)} · ${echappeHtmlSysteme(d.date_football_data)}</span></td>` +
    `<td>${echappeHtmlSysteme(d.score_football_data)}</td><td>${echappeHtmlSysteme(d.score_matchendirect)} (${echappeHtmlSysteme(d.date_matchendirect)})</td></tr>`).join("");
  div.innerHTML = `<h2>Contrôle des données Football-Data</h2>
    <p style="margin:0 0 9px;font-size:12.5px;color:var(--text-secondary)">Scores Football-Data comparés à Matchendirect sur les matchs communs (mêmes équipes, date à ± 1 jour). ${echappeHtmlSysteme(rapport.critere || "")}. Contrôle du ${echappeHtmlSysteme(rapport.genere_le || "—")}.</p>
    <div class="grille-stats">
      <div class="stat"><span class="etiquette">Matchs comparés</span><strong>${r.matchs_communs_compares ?? 0}</strong></div>
      <div class="stat"><span class="etiquette">Accord</span><strong style="color:${r.critere_atteint ? "var(--green)" : "var(--red)"}">${taux}</strong></div>
      <div class="stat"><span class="etiquette">Désaccords</span><strong>${r.desaccords ?? 0}</strong></div>
      <div class="stat"><span class="etiquette">Doublons / dates</span><strong>${(r.doublons ?? 0) + (r.dates_invalides ?? 0) + (r.dates_futures ?? 0)}</strong></div>
    </div>` + (lignes ? `<div style="overflow-x:auto;margin-top:10px"><table class="tableau-systeme"><thead><tr><th>Match</th><th>Football-Data</th><th>Matchendirect</th></tr></thead><tbody>${lignes}</tbody></table></div>` : "");
  return div;
}

fetch(`data/controles/football_data.json?_=${Date.now()}`)
  .then((r) => { if (!r.ok) throw new Error(`football_data.json introuvable (${r.status})`); return r.json(); })
  .then((rapport) => {
    window.__controleFootballData = rapport;
    const racine = document.getElementById("contenu-systeme");
    const ancien = document.getElementById("bloc-controle-football-data");
    if (ancien) ancien.remove();
    racine.insertBefore(construitBlocControleFootballData(rapport), racine.firstChild);
  })
  .catch((e) => console.error(e));
