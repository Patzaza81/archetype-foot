(function(){
"use strict";
var MIN=2,MAX=20,DEF=10,TOL=[0.05,0.10,0.25],WIDTH=600,MAXLEGS=12;
var DATA=null;
function esc(x){return x==null?"":String(x).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;")}
function pct(x){return Number.isFinite(Number(x))&&x!==null?(Number(x)*100).toFixed(1).replace(".",",")+" %":"—"}
function cote(x){return Number.isFinite(Number(x))&&x!==null?Number(x).toFixed(2).replace(".",","):"—"}

/* ---------- Construction d'un ticket pour une cote totale choisie (2 à 20) ---------- */
function tier(prod,target){
 for(var k=0;k<TOL.length;k++){
  var lo=Math.max(MIN,target/(1+TOL[k])),hi=Math.min(MAX,target*(1+TOL[k]));
  if(prod>=lo-1e-9&&prod<=hi+1e-9)return k;
 }
 return -1;
}
function beam(pool,size,target){
 if(size<1||pool.length<size)return null;
 var logT=Math.log(target),logCap=Math.log(Math.min(MAX,target*(1+TOL[TOL.length-1])));
 var states=[{idx:[],lp:0}];
 for(var d=1;d<=size;d++){
  var goal=logT*d/size,nxt=[];
  states.forEach(function(s){
   var start=s.idx.length?s.idx[s.idx.length-1]+1:0,used={};
   s.idx.forEach(function(i){used[pool[i].cle_match]=1});
   for(var i=start;i<pool.length;i++){
    if(used[pool[i].cle_match])continue;
    var o=Number(pool[i].cote);if(!(o>1))continue;
    var lp=s.lp+Math.log(o);if(lp>logCap+1e-12)continue;
    nxt.push({idx:s.idx.concat(i),lp:lp});
   }
  });
  nxt.sort(function(a,b){return Math.abs(a.lp-goal)-Math.abs(b.lp-goal)});
  states=nxt.slice(0,WIDTH);
  if(!states.length)return null;
 }
 var best=null,bestKey=null;
 states.forEach(function(s){
  var t=tier(Math.exp(s.lp),target);if(t<0)return;
  var joint=0;s.idx.forEach(function(i){joint+=Math.log(Number(pool[i].probabilite_estimee))});
  var key=[-t,joint,-Math.abs(s.lp-logT)];
  if(!bestKey||key[0]>bestKey[0]||(key[0]===bestKey[0]&&(key[1]>bestKey[1]||(key[1]===bestKey[1]&&key[2]>bestKey[2])))){bestKey=key;best=s.idx.map(function(i){return pool[i]})}
 });
 return best?{rows:best,key:bestKey}:null;
}
function bestTicket(pool,target){
 var best=null;
 for(var size=2;size<=MAXLEGS;size++){
  var r=beam(pool,size,target);if(!r)continue;
  var k=r.key;
  if(!best||k[0]>best.key[0]||(k[0]===best.key[0]&&(k[1]>best.key[1]||(k[1]===best.key[1]&&k[2]>best.key[2]))))best=r;
 }
 return best?best.rows:[];
}
function metrics(rows,target){
 var prod=1,joint=1,okp=rows.length>0,src={};
 rows.forEach(function(x){prod*=Number(x.cote);var p=Number(x.probabilite_estimee);if(Number.isFinite(p)&&x.probabilite_estimee!=null)joint*=p;else okp=false;if(x.source)src[x.source]=1});
 return{matchs:rows.length,cote_totale:rows.length?prod:null,ecart_objectif:rows.length&&target?Math.abs(prod-target):null,
  diversite_sources:Object.keys(src).length,probabilite_independante_theorique:okp?joint:null,ev_theorique:okp?joint*prod-1:null};
}

/* ---------- Affichage ---------- */
function legsHtml(sel){
 return (sel||[]).map(function(x){
  var det=[esc(x.marche)];
  if(x.probabilite_estimee!=null)det.push("proba estimée "+pct(x.probabilite_estimee));
  if(x.marge_modele!=null)det.push("avantage modèle "+pct(x.marge_modele));
  if(x.niveau_confiance)det.push("historique : "+esc(x.niveau_confiance));
  return '<div class="leg"><span class="cote">'+cote(x.cote)+'</span><strong>'+esc(x.domicile)+" — "+esc(x.exterieur)+'</strong><span class="source">'+esc(x.source||"")+(x.rang?" · "+esc(x.rang):"")+'</span><small>'+det.join(" · ")+'</small></div>';
 }).join("");
}
function ticketHtml(t){
 var m=t.metrics||{},ok=t.statut==="OK";
 return '<h2>'+esc(t.scenario)+'</h2><div class="meta"><span class="badge '+(ok?"ok":"none")+'">'+(ok?"Ticket disponible":"Aucun ticket solide")+'</span><span class="badge">'+esc(m.matchs||0)+" matchs</span><span class="badge">Cote "+cote(m.cote_totale)+"</span>"+(m.ecart_objectif!=null?'<span class="badge">Écart cible '+cote(m.ecart_objectif)+'</span>':"")+(m.diversite_sources?'<span class="badge">'+esc(m.diversite_sources)+" sources</span>":"")+'</div>'+legsHtml(t.selection)+(m.probabilite_independante_theorique!=null?'<p class="note">Probabilité théorique sous indépendance : '+pct(m.probabilite_independante_theorique)+' — ce n’est pas une probabilité jointe garantie.</p>':"");
}
function renderScenarios(data){
 var root=document.getElementById("tickets");root.innerHTML="";
 var hasPool=data&&data.pool&&data.pool.length;
 var list=((data&&data.scenarios)||[]).filter(function(t){return !(hasPool&&/^OBJECTIF_COTE/.test(t.scenario))});
 if(!list.length)return;
 list.forEach(function(t){var s=document.createElement("section");s.className="ticket";s.innerHTML=ticketHtml(t);root.appendChild(s)});
}
function parseTarget(raw){
 var v=parseFloat(String(raw).replace(",",".").replace(/\s/g,""));
 return Number.isFinite(v)?v:NaN;
}
function build(raw){
 var msg=document.getElementById("cible-msg"),out=document.getElementById("ticket-cible");
 var v=parseTarget(raw);
 if(!Number.isFinite(v)){msg.textContent="Saisissez une cote totale entre "+MIN+" et "+MAX+".";return}
 var note="";
 if(v<MIN){v=MIN;note="La cote totale ne peut pas être inférieure à "+MIN+" : "+MIN+" appliqué."}
 if(v>MAX){v=MAX;note="La cote totale ne peut pas dépasser "+MAX+" : "+MAX+" appliqué."}
 document.getElementById("cible").value=String(v).replace(".",",");
 try{localStorage.setItem("archetype_cote_cible",String(v))}catch(e){}
 var pool=(DATA&&DATA.pool)||[];
 if(!pool.length){msg.textContent="Aucun candidat disponible pour le moment : le système ne force pas la création d’un ticket.";out.innerHTML="";return}
 var rows=bestTicket(pool,v);
 var t={scenario:"VOTRE_TICKET_COTE_"+String(v).replace(".",","),statut:rows.length?"OK":"AUCUN_TICKET_SOLIDE",selection:rows,metrics:metrics(rows,v)};
 msg.textContent=note||(rows.length?"Cote visée "+cote(v)+" — ticket construit avec les choix des moteurs.":"Aucune combinaison de matchs distincts ne s’approche de la cote "+cote(v)+" (maximum ±25 %, toujours entre 2 et 20).");
 out.innerHTML='<section class="ticket">'+ticketHtml(t)+'</section>';
}
function init(){
 var form=document.getElementById("cible-form"),inp=document.getElementById("cible");
 var start=DEF;try{var s=parseFloat(localStorage.getItem("archetype_cote_cible"));if(Number.isFinite(s)&&s>=MIN&&s<=MAX)start=s}catch(e){}
 inp.value=String(start).replace(".",",");
 form.addEventListener("submit",function(e){e.preventDefault();build(inp.value)});
 Array.prototype.forEach.call(document.querySelectorAll("[data-cible]"),function(b){b.addEventListener("click",function(){build(b.getAttribute("data-cible"))})});
 build(inp.value);
}
fetch("data/tickets.json?_="+Date.now(),{cache:"no-store"}).then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}).then(function(d){
 DATA=d;
 document.getElementById("maj").textContent=d.genere_le?"Dernière génération : "+new Date(d.genere_le).toLocaleString("fr-FR"):"";
 var src=d.sources||{};var note=document.getElementById("pool-note");
 note.textContent="Pool actuel : V2.6.10 "+(src.moteur_v2_6_10||0)+" · V3 "+(src.moteur_v3||0)+" · Journal "+(src.journal||0)+" (maximum "+(d.maximum_par_source||10)+" par source).";
 renderScenarios(d);init();
}).catch(function(e){document.getElementById("maj").textContent="Erreur de chargement : "+e.message;DATA={pool:[],scenarios:[]};renderScenarios(DATA);init();});
})();
