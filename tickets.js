(function(){
"use strict";
function esc(x){return x==null?"":String(x).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;")}
function pct(x){return Number.isFinite(Number(x))?(Number(x)*100).toFixed(1).replace(".",",")+" %":"—"}
function cote(x){return Number.isFinite(Number(x))?Number(x).toFixed(2).replace(".",","):"—"}
function render(data){
 var root=document.getElementById("tickets");root.innerHTML="";
 if(!data||!data.scenarios||!data.scenarios.length){root.innerHTML='<section class="ticket"><strong>Aucun ticket solide disponible.</strong><p class="note">Les données nécessaires ou les opportunités répondant aux critères ne sont pas suffisantes. Le système ne force pas la création d’un ticket.</p></section>';return}
 data.scenarios.forEach(function(t){
   var s=document.createElement("section");s.className="ticket";
   var m=t.metrics||{};var ok=t.statut==="OK";
   var legs=(t.selection||[]).map(function(x){
     return '<div class="leg"><span class="cote">'+cote(x.cote)+'</span><strong>'+esc(x.domicile)+" — "+esc(x.exterieur)+'</strong><span class="source">'+esc(x.source||"")+(x.rang?" · "+esc(x.rang):"")+'</span><small>'+esc(x.marche)+" · "+esc(x.niveau_confiance||"")+(x.marge_succes!=null?" · marge succès "+pct(x.marge_succes):"")+'</small></div>';
   }).join("");
   s.innerHTML='<h2>'+esc(t.scenario)+'</h2><div class="meta"><span class="badge '+(ok?"ok":"none")+'">'+(ok?"Ticket disponible":"Aucun ticket solide")+'</span><span class="badge">'+esc(m.matchs||0)+" matchs</span><span class="badge">Cote "+cote(m.cote_totale)+"</span>"+(m.ecart_objectif!=null?'<span class="badge">Écart cible '+cote(m.ecart_objectif)+'</span>':"")+(m.diversite_sources?'<span class="badge">'+esc(m.diversite_sources)+" sources</span>":"")+'</div>'+legs+(m.probabilite_independante_theorique!=null?'<p class="note">Probabilité théorique sous indépendance : '+pct(m.probabilite_independante_theorique)+' — ce n’est pas une probabilité jointe garantie.</p>':"");
   root.appendChild(s);
 });
}
fetch("data/tickets.json?_="+Date.now(),{cache:"no-store"}).then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}).then(function(d){
 document.getElementById("maj").textContent=d.genere_le?"Dernière génération : "+new Date(d.genere_le).toLocaleString("fr-FR"):"";
 render(d);
}).catch(function(e){document.getElementById("maj").textContent="Erreur de chargement : "+e.message;render({scenarios:[]});});
})();