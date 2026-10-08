(function(){
"use strict";

var MIN=2,MAX=20,DEF=10,TOL=[0.05,0.10,0.25],WIDTH=600,MAXLEGS=12;
var DATA=null;

function esc(x){return x==null?"":String(x).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;")}
function pct(x){return Number.isFinite(Number(x))&&x!==null?(Number(x)*100).toFixed(1).replace(".",",")+" %":"—"}
function cote(x){return Number.isFinite(Number(x))&&x!==null?Number(x).toFixed(2).replace(".",","):"—"}
function gain(x){return (Number(x)>0?"+":"")+pct(x)}

function marketLabel(m){
 var map={
  "1x2_domicile":"Victoire domicile","1x2_nul":"Match nul","1x2_exterieur":"Victoire extérieur",
  "double_chance_1X":"Double chance 1X","double_chance_X2":"Double chance X2","double_chance_12":"Double chance 12",
  "btts_oui":"Les deux équipes marquent","btts_non":"Une équipe ne marque pas",
  "over_under_total_0.5_over":"Plus de 0,5 but","over_under_total_0.5_under":"Moins de 0,5 but",
  "over_under_total_1.5_over":"Plus de 1,5 buts","over_under_total_1.5_under":"Moins de 1,5 buts",
  "over_under_total_2.5_over":"Plus de 2,5 buts","over_under_total_2.5_under":"Moins de 2,5 buts",
  "over_under_total_3.5_over":"Plus de 3,5 buts","over_under_total_3.5_under":"Moins de 3,5 buts",
  "over_under_total_4.5_over":"Plus de 4,5 buts","over_under_total_4.5_under":"Moins de 4,5 buts",
  "over_under_total_5.5_over":"Plus de 5,5 buts","over_under_total_5.5_under":"Moins de 5,5 buts"
 };
 if(map[m])return map[m];
 return String(m||"Pari").replace(/_/g," ");
}
function sourceLabel(s){
 if(s==="moteur_v2_6_10")return "Moteur V2.6.10";
 if(s==="moteur_v3")return "Moteur V3";
 if(s==="journal")return "Journal";
 return s||"Source";
}

/* ---------- Construction de la meilleure combinaison ---------- */
function tier(prod,target){
 for(var k=0;k<TOL.length;k++){
  var lo=Math.max(MIN,target*(1-TOL[k])),hi=Math.min(MAX,target*(1+TOL[k]));
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
  if(!bestKey||key[0]>bestKey[0]||(key[0]===bestKey[0]&&(key[1]>bestKey[1]||(key[1]===bestKey[1]&&key[2]>bestKey[2])))){
   bestKey=key;best=s.idx.map(function(i){return pool[i]});
  }
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
 rows.forEach(function(x){
  prod*=Number(x.cote);
  var p=Number(x.probabilite_estimee);
  if(Number.isFinite(p)&&x.probabilite_estimee!=null)joint*=p;else okp=false;
  if(x.source)src[x.source]=1;
 });
 return{
  matchs:rows.length,cote_totale:rows.length?prod:null,
  ecart_objectif:rows.length&&target?Math.abs(prod-target):null,
  diversite_sources:Object.keys(src).length,
  probabilite_independante_theorique:okp?joint:null,
  ev_theorique:okp?joint*prod-1:null
 };
}

/* ---------- Affichage simple ---------- */
function badge(text){return '<span class="tag">'+esc(text)+'</span>'}

function legsHtml(rows){
 return (rows||[]).map(function(x){
  var details=[marketLabel(x.marche)];
  if(x.journal_frequency!=null){
   details.push("Journal "+pct(x.journal_frequency)+" ("+(x.journal_wins||0)+"/"+(x.journal_observations||0)+")");
   if(x.probabilite_source==="JOURNAL_LISSE"&&x.probabilite_estimee!=null)details.push("probabilité estimée "+pct(x.probabilite_estimee));
   else if(x.journal_lower_bound!=null)details.push("borne prudente "+pct(x.journal_lower_bound));
  }else if(x.probabilite_source==="MODELE_NON_CALIBRE"){
   details.push("modèle non calibré");
  }else if(x.probabilite_source==="HISTORIQUE_MOTEUR_WILSON"){
   details.push("historique moteur "+pct(x.probabilite_estimee));
  }else if(x.preuve_niveau==="ECHANTILLON_V3"){
   details.push("V3 · échantillon exploitable");
  }else if(x.niveau_confiance){
   details.push(x.niveau_confiance==="MODELE_SEUL"?"Analyse moteur":"Confiance "+x.niveau_confiance);
  }
  if(x.marge_modele!=null)details.push("avantage modèle "+pct(x.marge_modele));
  return '<div class="paris">'+
   '<div class="paris-top"><strong>'+esc(x.domicile)+" — "+esc(x.exterieur)+'</strong><span class="odds">'+cote(x.cote)+'</span></div>'+
   '<div class="small">'+esc(details.join(" · "))+'</div>'+
   '<div>'+badge(sourceLabel(x.source))+(x.rang?badge(x.rang):"")+'</div>'+
   (x.justification?'<div class="small">'+esc(x.justification)+'</div>':"")+
  '</div>';
 }).join("");
}

function resultStats(m){
 if(!m)return "";
 return '<div class="stats">'+
  '<div class="stat"><b>'+esc(m.matchs||0)+'</b><span>matchs</span></div>'+
  '<div class="stat"><b>'+cote(m.cote_totale)+'</b><span>cote totale</span></div>'+
  '<div class="stat"><b>'+pct(m.probabilite_independante_theorique)+'</b><span>chance estimée*</span></div>'+
 '</div>';
}

function planSimple(p,size){
 if(!p)return "";
 var label;
 if(p.nom==="COMBINE")label="1 combiné";
 else if(p.nom==="SIMPLES")label=size+" paris simples";
 else label=(p.tickets||0)+" tickets";
 var text=[];
 if(p.gagnants_requis!=null)text.push("rentable à partir de "+p.gagnants_requis+" ticket(s) gagnant(s)");
 if(p.erreurs_garanties!=null)text.push(p.erreurs_garanties+" erreur(s) tolérée(s)");
 text.push("chance de rentabilité "+pct(p.proba_profit));
 return '<div class="plan"><b>'+esc(label)+'</b><small>'+esc(text.join(" · "))+'</small></div>';
}

function analysisDetails(a,sel){
 if(!a||!a.plans||!a.plans.length)return "";
 var best=null,regular=null,margin=null;
 a.plans.forEach(function(p){
  if(!best||p.esperance_gain>best.esperance_gain)best=p;
  if(p.gagnants_requis!=null){
   if(!regular||p.proba_profit>regular.proba_profit)regular=p;
   if(!margin||p.erreurs_garanties>margin.erreurs_garanties)margin=p;
  }
 });
 var html='<details><summary>Voir l’analyse de la répartition</summary>';
 html+='<p class="detail-text"><strong>Le plus rentable :</strong> '+esc(best?best.nom:"—")+
  (regular?' · <strong>le plus régulier :</strong> '+esc(regular.nom):"")+
  (margin?' · <strong>le plus tolérant :</strong> '+esc(margin.nom):"")+'</p>';
 a.plans.forEach(function(p){html+=planSimple(p,a.paris)});
 html+='<p class="detail-text">* La chance affichée suppose que les paris sont indépendants. Elle reste une estimation, jamais une garantie.</p></details>';
 return html;
}

function ticketHtml(t,title){
 var m=t.metrics||{},ok=t.statut==="OK",sel=t.selection||[];
 var a=t.analyse||(sel.length>=2&&window.ArchetypeAnalyse?window.ArchetypeAnalyse.analyse(sel):null);
 var targetMatch=t.scenario&&/^VOTRE_TICKET/.test(t.scenario);
 var heading=title||(targetMatch?"Votre ticket":"Proposition");
 var html='<section class="section">'+
  '<div class="result-head"><div><p class="result-title">'+esc(heading)+'</p>'+
  (targetMatch?'<p class="help">La combinaison la plus proche de votre objectif parmi les candidats disponibles.</p>':"")+
  '</div><span class="status '+(ok?"ok":"none")+'">'+(ok?"Disponible":"Pas de combinaison solide")+'</span></div>';
 html+=resultStats(m);
 if(sel.length)html+='<div>'+legsHtml(sel)+'</div>';
 else html+='<div class="empty">Aucun ticket ne correspond actuellement à cette demande. Le système ne force pas un résultat.</div>';
 if(m.ecart_objectif!=null)html+='<p class="help">Écart par rapport à votre objectif : <strong>'+cote(m.ecart_objectif)+'</strong>.</p>';
 if(a)html+=analysisDetails(a,sel);
 html+='</section>';
 return html;
}

function scenarioTitle(name){
 var map={PRUDENT_3:"Ticket prudent",EQUILIBRE_4:"Ticket équilibré",EQUILIBRE_5:"Ticket équilibré renforcé"};
 return map[name]||name.replace(/_/g," ");
}

function renderOpportunities(data){
 var root=document.getElementById("opportunites");
 if(!root)return;
 var rows=(data&&data.opportunites)||[];
 if(!rows.length){
  root.innerHTML='<div class="empty">Aucune opportunité multi-source suffisamment documentée pour être mise en avant.</div>';
  return;
 }
 root.innerHTML=rows.slice(0,10).map(function(x){
  var evidence=x.journal_frequency!=null
    ? "Journal : "+pct(x.journal_frequency)+" ("+(x.journal_wins||0)+"/"+(x.journal_observations||0)+")"
    : (x.probabilite_source==="HISTORIQUE_MOTEUR_WILSON"
       ? "Historique moteur : borne prudente "+pct(x.probabilite_estimee)
       : "Moteur : signal non calibré");
  if(x.journal_roi!=null)evidence+=" · ROI historique "+gain(x.journal_roi);
  return '<div class="opportunity">'+
    '<div class="paris-top"><strong>'+esc(x.domicile)+" — "+esc(x.exterieur)+'</strong><span class="odds">'+cote(x.cote)+'</span></div>'+
    '<div class="small">'+esc(marketLabel(x.marche))+" · "+esc(sourceLabel(x.source))+'</div>'+
    '<div class="small">'+esc(evidence)+'</div>'+
    (x.justification?'<div class="small">'+esc(x.justification)+'</div>':"")+
  '</div>';
 }).join("");
}

function renderScenarios(data){
 var root=document.getElementById("tickets");root.innerHTML="";
 var list=((data&&data.scenarios)||[]).filter(function(t){return !/^OBJECTIF_COTE/.test(t.scenario)});
 if(!list.length){root.innerHTML='<div class="empty">Aucune autre proposition disponible pour le moment.</div>';return}
 list.forEach(function(t){
  var wrap=document.createElement("div");wrap.className="other-card";
  var m=t.metrics||{};
  wrap.innerHTML='<h3>'+esc(scenarioTitle(t.scenario))+'</h3>'+
   '<div class="meta">'+badge((m.matchs||0)+" matchs")+badge("cote "+cote(m.cote_totale))+badge(pct(m.probabilite_independante_theorique)+" estimée")+'</div>'+
   '<details><summary>Voir ce ticket</summary>'+legsHtml(t.selection||[])+
   (t.selection&&t.selection.length>=2&&window.ArchetypeAnalyse?analysisDetails(window.ArchetypeAnalyse.analyse(t.selection),t.selection):"")+
   '</details>';
  root.appendChild(wrap);
 });
}

function parseTarget(raw){
 var v=parseFloat(String(raw).replace(",",".").replace(/\s/g,""));
 return Number.isFinite(v)?v:NaN;
}
function build(raw){
 var msg=document.getElementById("cible-msg"),out=document.getElementById("ticket-cible");
 var v=parseTarget(raw);
 if(!Number.isFinite(v)){msg.textContent="Saisissez une cote entre "+MIN+" et "+MAX+".";out.innerHTML="";return}
 var note="";
 if(v<MIN){v=MIN;note="2 appliqué : la cote minimale est 2."}
 if(v>MAX){v=MAX;note="20 appliqué : la cote maximale est 20."}
 document.getElementById("cible").value=String(v).replace(".",",");
 try{localStorage.setItem("archetype_cote_cible",String(v))}catch(e){}
 var pool=(DATA&&DATA.pool)||[];
 if(!pool.length){
  msg.textContent="Aucun candidat disponible. Aucun ticket ne sera créé artificiellement.";
  out.innerHTML="";return;
 }
 var rows=bestTicket(pool,v);
 var t={scenario:"VOTRE_TICKET_COTE_"+String(v).replace(".",","),statut:rows.length?"OK":"AUCUN_TICKET_SOLIDE",selection:rows,metrics:metrics(rows,v)};
 msg.textContent=note||(rows.length?"Objectif "+cote(v)+" · "+rows.length+" paris sélectionnés.":"Aucune combinaison ne se rapproche suffisamment de "+cote(v)+".");
 out.innerHTML=ticketHtml(t,"Votre ticket");
 window.scrollTo({top:0,behavior:"smooth"});
}

function init(){
 var form=document.getElementById("cible-form"),inp=document.getElementById("cible"),start=DEF;
 try{var s=parseFloat(localStorage.getItem("archetype_cote_cible"));if(Number.isFinite(s)&&s>=MIN&&s<=MAX)start=s}catch(e){}
 inp.value=String(start).replace(".",",");
 form.addEventListener("submit",function(e){e.preventDefault();build(inp.value)});
 Array.prototype.forEach.call(document.querySelectorAll("[data-cible]"),function(b){
  b.addEventListener("click",function(){build(b.getAttribute("data-cible"))});
 });
 build(inp.value);
}

fetch("data/tickets.json?_="+Date.now(),{cache:"no-store"})
 .then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json()})
 .then(function(d){
  DATA=d;
  document.getElementById("maj").textContent=d.genere_le?"Dernière génération : "+new Date(d.genere_le).toLocaleString("fr-FR"):"";
  var src=d.sources||{};
  document.getElementById("pool-note").textContent=
   "Candidats retenus : V2 "+(src.moteur_v2_6_10||0)+" · V3 "+(src.moteur_v3||0)+" · Journal "+(src.journal||0)+
   " · le classement privilégie désormais les preuves réelles.";
  renderOpportunities(d);renderScenarios(d);init();
 })
 .catch(function(e){
  document.getElementById("maj").textContent="Impossible de charger les tickets";
  document.getElementById("pool-note").textContent="Les données ne sont pas disponibles pour le moment.";
  DATA={pool:[],opportunites:[],scenarios:[]};renderOpportunities(DATA);renderScenarios(DATA);init();
 });
})();