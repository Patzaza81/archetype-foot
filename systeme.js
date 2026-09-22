// systeme.js — présentation uniquement, aucun calcul.
// Affiche etat_systeme.json : bilan du moteur_v2_6_9 et suivi de shrink_v1.

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

function construitBlocComparaison(bilanPrincipal, bilanShrink) {
  const div = document.createElement("div");
  div.className = "bloc-systeme";
  const gP = (bilanPrincipal && bilanPrincipal.global) || {};
  const gS = (bilanShrink && bilanShrink.global) || {};
  const ligne = (label, a, b) => `<tr><td>${label}</td><td>${a}</td><td>${b}</td></tr>`;
  const roiTxt = (g) => (g.roi_flat === null || g.roi_flat === undefined ? "—" : formatPctSysteme(g.roi_flat));
  div.innerHTML = `
    <h2>Comparaison des moteurs</h2>
    <p class="ax-bandeau" style="margin-bottom:0.75rem;">shrink_v1 est en test. Ce tableau suit son évolution réelle au fil des matchs.</p>
    <table class="tableau-systeme">
      <thead><tr><th></th><th>moteur_v2_6_9 (actuel)</th><th>shrink_v1 (en test)</th></tr></thead>
      <tbody>
        ${ligne("Observations résolues", gP.observations ?? 0, gS.observations ?? 0)}
        ${ligne("Gagnées", gP.gagnes ?? 0, gS.gagnes ?? 0)}
        ${ligne("Perdues", gP.perdus ?? 0, gS.perdus ?? 0)}
        ${ligne("ROI (mise flat)", roiTxt(gP), roiTxt(gS))}
      </tbody>
    </table>`;
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

function afficheEtatSysteme(etat) {
  const racine = document.getElementById("contenu-systeme");
  const maj = document.getElementById("maj-systeme");
  racine.innerHTML = "";
  maj.textContent = etat.genere_le ? `Dernière mise à jour : ${new Date(etat.genere_le).toLocaleString("fr-FR")}` : "";

  racine.appendChild(construitBlocGlobal(etat.bilan_comportemental));
  racine.appendChild(construitBlocComparaison(etat.bilan_comportemental, etat.bilan_shrink_v1));
  racine.appendChild(construitTableauFamilles(etat.bilan_comportemental));
}

fetch(`etat_systeme.json?_=${Date.now()}`)
  .then((r) => { if (!r.ok) throw new Error(`etat_systeme.json introuvable (${r.status})`); return r.json(); })
  .then(afficheEtatSysteme)
  .catch((e) => {
    document.getElementById("maj-systeme").textContent = "Erreur de chargement : " + e.message;
    console.error(e);
  });
