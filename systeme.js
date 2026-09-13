// systeme.js — présentation uniquement, aucun calcul.
// Affiche etat_systeme.json (construit_etat_systeme.py) : bilan
// comportemental, paramètres calibrables actifs, dernières promotions,
// rapport de calibration des tickets fictifs.

function formatPctSysteme(x) {
  const n = Number(x);
  return Number.isFinite(n) ? `${(n * 100).toFixed(1).replace(".", ",")} %` : "—";
}

function formatNombreSysteme(x, decimales = 4) {
  const n = Number(x);
  return Number.isFinite(n) ? n.toFixed(decimales).replace(".", ",") : "—";
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

function construitTableauParametres(parametres, etatCalibration) {
  const noms = Object.keys(parametres || {});
  const div = document.createElement("div");
  div.className = "bloc-systeme";
  const valeursActives = (etatCalibration && etatCalibration.parametres) || {};
  const lignes = noms.map((nom) => {
    const p = parametres[nom];
    const modifie = nom in valeursActives;
    return `<tr class="${modifie ? "ligne-modifiee" : ""}"><td>${echappeHtmlSysteme(nom)}</td><td>${formatNombreSysteme(p.valeur)}</td><td>${formatNombreSysteme(p.valeur_origine)}</td><td>${modifie ? "Calibré" : "Jamais calibré"}</td></tr>`;
  }).join("");
  div.innerHTML = `<h2>Paramètres calibrables actifs</h2>
    <table class="tableau-systeme"><thead><tr><th>Paramètre</th><th>Valeur actuelle</th><th>Valeur d'origine</th><th>Statut</th></tr></thead><tbody>${lignes}</tbody></table>
    <p class="note-systeme">Dernier cycle de calibration : ${echappeHtmlSysteme((etatCalibration && etatCalibration.dernier_cycle) || "jamais encore exécuté")}</p>`;
  return div;
}

function construitListePromotions(promotions) {
  const div = document.createElement("div");
  div.className = "bloc-systeme";
  if (!promotions || !promotions.length) {
    div.innerHTML = `<h2>Dernières promotions</h2><p class="etat-vide-systeme">Aucun paramètre n'a encore été calibré automatiquement.</p>`;
    return div;
  }
  const lignes = promotions.map((p) => `<li><strong>${echappeHtmlSysteme(p.date_cycle)}</strong> — ${echappeHtmlSysteme(p.parametre)} : ${formatNombreSysteme(p.avant)} → ${formatNombreSysteme(p.apres)}</li>`).join("");
  div.innerHTML = `<h2>Dernières promotions</h2><ul class="liste-promotions">${lignes}</ul>`;
  return div;
}

function construitBlocTickets(rapport, nbPending) {
  const div = document.createElement("div");
  div.className = "bloc-systeme";
  if (!rapport || !rapport.nb_tickets_resolus) {
    div.innerHTML = `<h2>Tickets fictifs (mode observation)</h2><p class="etat-vide-systeme">Aucun ticket fictif résolu pour l'instant${nbPending ? ` (${nbPending} en attente)` : ""}.</p>`;
    return div;
  }
  const ecart = rapport.ecart;
  const classeEcart = ecart >= 0 ? "ecart-positif" : "ecart-negatif";
  div.innerHTML = `
    <h2>Tickets fictifs (mode observation)</h2>
    <div class="grille-stats">
      <div class="stat"><span class="etiquette">Tickets résolus</span><strong>${rapport.nb_tickets_resolus}</strong></div>
      <div class="stat"><span class="etiquette">En attente</span><strong>${nbPending || 0}</strong></div>
      <div class="stat"><span class="etiquette">Probabilité annoncée moy.</span><strong>${formatPctSysteme(rapport.probabilite_annoncee_moyenne)}</strong></div>
      <div class="stat"><span class="etiquette">Taux de réussite réel</span><strong>${formatPctSysteme(rapport.taux_reussite_reel)}</strong></div>
    </div>
    <p class="note-systeme ${classeEcart}">Écart annoncé/réel : ${ecart >= 0 ? "+" : ""}${formatPctSysteme(ecart)} ${ecart < -0.05 ? "— l'annonce paraît optimiste, à surveiller." : ""}</p>`;
  return div;
}

function afficheEtatSysteme(etat) {
  const racine = document.getElementById("contenu-systeme");
  const maj = document.getElementById("maj-systeme");
  racine.innerHTML = "";
  maj.textContent = etat.genere_le ? `Dernière mise à jour : ${new Date(etat.genere_le).toLocaleString("fr-FR")}` : "";

  racine.appendChild(construitBlocGlobal(etat.bilan_comportemental));
  racine.appendChild(construitTableauFamilles(etat.bilan_comportemental));
  racine.appendChild(construitTableauParametres(etat.parametres_actifs, etat.etat_calibration));
  racine.appendChild(construitListePromotions(etat.dernieres_promotions));
  racine.appendChild(construitBlocTickets(etat.rapport_tickets_observation, etat.nb_tickets_observation_pending));
}

fetch(`etat_systeme.json?_=${Date.now()}`)
  .then((r) => { if (!r.ok) throw new Error(`etat_systeme.json introuvable (${r.status})`); return r.json(); })
  .then(afficheEtatSysteme)
  .catch((e) => {
    document.getElementById("maj-systeme").textContent = "Erreur de chargement : " + e.message;
    console.error(e);
  });
