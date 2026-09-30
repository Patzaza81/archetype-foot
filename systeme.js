// systeme.js — tableau de contrôle des deux moteurs. Aucun calcul métier.
const $ = (id) => document.getElementById(id);

function pct(x, digits=1) {
  const n = Number(x);
  return Number.isFinite(n) ? `${(n * 100).toFixed(digits).replace(".", ",")} %` : "—";
}
function num(x) {
  const n = Number(x);
  return Number.isFinite(n) ? n.toLocaleString("fr-FR") : "—";
}
function roiClass(x) {
  const n = Number(x);
  return !Number.isFinite(n) ? "" : n > 0 ? "positif" : n < 0 ? "negatif" : "";
}
function esc(x) {
  return x == null ? "" : String(x).replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function bar(value, max=100) {
  const n = Math.max(0, Math.min(max, Number(value)||0));
  return `<span class="bar"><i style="width:${(n/max)*100}%"></i></span>`;
}

function moteurCarte(m, couleur) {
  const g = m.global || {};
  const c = m.calibration || {};
  const v3 = m.role === "EXPERIMENTAL";
  const calibration = v3
    ? `${num(c.observations)} / ${num(c.minimum_observations)} obs. · ${num(c.matchs)} / ${num(c.minimum_matchs)} matchs`
    : "Production active";
  const progress = v3 ? Math.min(100, (Number(c.observations||0)/Math.max(1,Number(c.minimum_observations||1)))*100) : 100;
  return `
    <article class="moteur-card ${couleur}">
      <div class="moteur-head"><div><span class="sur-titre">${v3 ? "MOTEUR EXPÉRIMENTAL" : "MOTEUR DE PRODUCTION"}</span><h2>${esc(m.nom)}</h2></div>
      <span class="pill ${v3 ? "pill-v3" : "pill-ok"}">${v3 ? "NON VALIDÉ" : "ACTIF"}</span></div>
      <p class="moteur-note">${v3 ? "Suivi séparé : les aperçus non calibrés ne sont jamais présentés comme des performances réalisées." : "Référence de production. Les résultats sont suivis sur les paris effectivement réglés."}</p>
      <div class="stats-hero">
        <div><b>${num(g.observations ?? g.matchs)}</b><small>${v3 ? "matchs suivis" : "paris réglés"}</small></div>
        <div><b>${num(g.gagnes ?? g.selections ?? 0)}</b><small>${v3 ? "sélections" : "gagnés"}</small></div>
        <div><b class="${roiClass(g.roi)}">${v3 ? "—" : pct(g.roi)}</b><small>${v3 ? "ROI validé" : "ROI flat"}</small></div>
      </div>
      <div class="progress-label"><span>${v3 ? "Progression calibration" : "État du moteur"}</span><strong>${v3 ? Math.round(progress)+" %" : "100 %"}</strong></div>
      ${bar(progress)}
      <div class="mini-line">${esc(calibration)}</div>
    </article>`;
}

function blocControle() {
  return `<section class="section-card compact"><div class="section-title"><div><span class="sur-titre">SURVEILLANCE</span><h2>Contrôles d'intégrité</h2></div></div>
  <p class="section-sub">Les contrôles de saison et Football-Data restent indépendants des statistiques des moteurs.</p>
  <div id="controles-systeme" class="control-grid"><div class="control-placeholder">Chargement des contrôles…</div></div></section>`;
}

function blocV2(m) {
  const rows = (m.par_marche || []).map(r => `
    <tr data-marche="${esc(r.marche).toLowerCase()}">
      <td><strong>${esc(r.marche)}</strong></td><td>${num(r.observations)}</td><td>${num(r.gagnes)}</td>
      <td class="${roiClass(r.roi)}">${pct(r.roi)}</td><td>${pct(r.reussite)}</td><td>${esc(r.statut || "—")}</td>
    </tr>`).join("");
  return `<section class="section-card"><div class="section-title"><div><span class="sur-titre">MARCHÉS · V2</span><h2>Performance réalisée par marché</h2></div><span class="source-tag">Réglé</span></div>
  <p class="section-sub">Uniquement les paris effectivement réglés. Aucun résultat V3 n'est mélangé à cette série.</p>
  <input class="market-search" id="search-v2" placeholder="Rechercher un marché…" aria-label="Rechercher un marché V2">
  <div class="table-wrap"><table class="market-table"><thead><tr><th>Marché</th><th>Paris</th><th>Gagnés</th><th>ROI</th><th>Réussite</th><th>Statut</th></tr></thead><tbody id="rows-v2">${rows || '<tr><td colspan="6">Aucune donnée.</td></tr>'}</tbody></table></div></section>`;
}

function blocV3(m) {
  const c = m.calibration || {}, g = m.global || {};
  const rows = (m.par_marche || []).map(r => `
    <tr data-marche="${esc(r.marche).toLowerCase()}">
      <td><strong>${esc(r.marche)}</strong></td><td>${num(r.calculs)}</td><td>${num(r.apercus)}</td>
      <td>${num(r.selections)}</td><td>${r.probabilite_moyenne == null ? "—" : pct(r.probabilite_moyenne)}</td><td>${r.edv_moyenne == null ? "—" : r.edv_moyenne.toFixed(2).replace(".",",")}</td>
    </tr>`).join("");
  const rejet = Object.entries(m.raisons_rejet || {}).sort((a,b)=>b[1]-a[1]).slice(0,8).map(([k,v])=>`<div class="reject-row"><span>${esc(k)}</span><b>${num(v)}</b></div>`).join("");
  return `<section class="section-card"><div class="section-title"><div><span class="sur-titre">MARCHÉS · V3</span><h2>Couverture et comportement expérimental</h2></div><span class="source-tag v3">Non calibré</span></div>
  <div class="v3-summary">
    <div><span>Matchs évalués</span><b>${num(g.evalues)} / ${num(g.matchs)}</b></div>
    <div><span>Calculs de marchés</span><b>${num(g.marches_cotes_calcules)}</b></div>
    <div><span>Aperçus</span><b>${num(g.apercus_non_calibres)}</b></div>
    <div><span>Sélections validées</span><b>${num(g.selections)}</b></div>
  </div>
  <div class="table-wrap"><input class="market-search" id="search-v3" placeholder="Rechercher un marché…" aria-label="Rechercher un marché V3">
  <table class="market-table"><thead><tr><th>Marché</th><th>Calculs</th><th>Aperçus</th><th>Sélections</th><th>P moy.</th><th>EDV moy.</th></tr></thead><tbody id="rows-v3">${rows || '<tr><td colspan="6">Aucune donnée.</td></tr>'}</tbody></table></div>
  <details class="details-control"><summary>Pourquoi les candidats sont écartés</summary><div class="reject-list">${rejet || "Aucun rejet enregistré."}</div></details>
  </section>`;
}

function blocEvolution(m) {
  const hist = m.evolution || [];
  const rows = hist.map(x=>`<tr><td><strong>${esc(x.date)}</strong></td><td>${num(x.matchs)}</td><td>${num(x.evalues)}</td><td>${num(x.apercus)}</td><td>${num(x.selections)}</td></tr>`).join("");
  return `<section class="section-card"><div class="section-title"><div><span class="sur-titre">RÉTROSPECTIVE</span><h2>Évolution quotidienne du V3</h2></div></div>
  <p class="section-sub">Historique réellement présent dans les journaux V3. Une sélection « aperçu » reste explicitement non calibrée.</p>
  <div class="table-wrap"><table class="market-table"><thead><tr><th>Date</th><th>Matchs</th><th>Évalués</th><th>Aperçus</th><th>Sélections</th></tr></thead><tbody>${rows || '<tr><td colspan="5">Pas encore d’historique.</td></tr>'}</tbody></table></div></section>`;
}

function afficher(etat) {
  const v2 = etat.moteurs?.moteur_v2_6_9 || etat.bilan_comportemental || {};
  const v3 = etat.moteurs?.moteur_v3 || etat.bilan_v3 || {};
  $("maj-systeme").textContent = etat.genere_le ? `État consolidé · ${new Date(etat.genere_le).toLocaleString("fr-FR")}` : "";
  $("contenu-systeme").innerHTML =
    moteurCarte(v2,"v2") + moteurCarte(v3,"v3") +
    blocV2(v2) + blocV3(v3) + blocEvolution(v3) + blocControle();
  bindSearch("search-v2","rows-v2"); bindSearch("search-v3","rows-v3");
  chargerControles();
}
function bindSearch(inputId, rowsId) {
  const input=$(inputId); if(!input) return;
  input.addEventListener("input",()=>{const q=input.value.toLowerCase().trim(); $(rowsId)?.querySelectorAll("tr").forEach(tr=>tr.style.display=tr.dataset.marche?.includes(q)?"":"none");});
}
function chargerControles() {
  Promise.all([
    fetch(`controle_saisons.json?_=${Date.now()}`).then(r=>r.ok?r.json():null).catch(()=>null),
    fetch(`data/controles/football_data.json?_=${Date.now()}`).then(r=>r.ok?r.json():null).catch(()=>null)
  ]).then(([s,f])=>{
    const root=$("controles-systeme"); if(!root)return;
    root.innerHTML="";
    if(s) root.appendChild(carteControle("Saisons",s.resume||{},s.genere_le));
    if(f) root.appendChild(carteControle("Football-Data",f.resume||{},f.genere_le));
    if(!root.children.length) root.innerHTML='<div class="control-placeholder">Contrôles indisponibles pour le moment.</div>';
  });
}
function carteControle(t,r,date) {
  const d=document.createElement("div"); d.className="control-card";
  const ok=t==="Saisons" ? Number(r.incoherentes||0)===0 : !!r.critere_atteint;
  d.innerHTML=`<div><b>${t}</b><span class="pill ${ok?"pill-ok":"pill-warn"}">${ok?"OK":"À contrôler"}</span></div>
  <strong>${t==="Saisons"?num(r.verifiables):num(r.matchs_communs_compares)}</strong>
  <small>${t==="Saisons"?"équipes vérifiables":"matchs comparés"} · ${esc(date||"")}</small>`;
  return d;
}

fetch(`etat_systeme.json?_=${Date.now()}`)
  .then(r=>{if(!r.ok)throw new Error(`etat_systeme.json introuvable (${r.status})`);return r.json();})
  .then(afficher)
  .catch(e=>{$("maj-systeme").textContent="Erreur de chargement : "+e.message;console.error(e);});
