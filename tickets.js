(function(){
"use strict";

var MAXTICKETS=10,MIN=2,MAX=20,DEF=10,TOL=[0.05,0.10,0.25],TENTATIVES=4000,MAXLEGS=12;
var DATA=null,CHK={};

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

/* ---------- Tirage au hasard dans les matchs cochés ---------- */
function tier(prod,target){
 for(var k=0;k<TOL.length;k++){
  var lo=Math.max(MIN,target*(1-TOL[k])),hi=Math.min(MAX,target*(1+TOL[k]));
  if(prod>=lo-1e-9&&prod<=hi+1e-9)return k;
 }
 return -1;
}
function melange(a,rnd){
 var t=a.slice();
 for(var i=t.length-1;i>0;i--){var j=Math.floor(rnd()*(i+1)),x=t[i];t[i]=t[j];t[j]=x}
 return t;
}
/* Même principe que tirage_cible() de generateur_tickets.py : taille et paris tirés au hasard, un seul pari par match,
   on garde le tirage de la fenêtre de proximité la plus serrée trouvée. Rien de possible : liste vide. */
function tirageCible(pool,target,rnd,tentatives){
 rnd=rnd||Math.random;tentatives=tentatives||TENTATIVES;
 var dispo=pool.filter(function(x){return Number(x.cote)>1});
 var vus={};dispo.forEach(function(x){vus[x.cle_match]=1});
 var nb=Object.keys(vus).length;
 if(nb<2)return [];
 var bestTier=-1,best=[];
 for(var n=0;n<tentatives;n++){
  var size=2+Math.floor(rnd()*(Math.min(MAXLEGS,nb)-1));
  var ordre=melange(dispo,rnd),pris={},chosen=[];
  for(var i=0;i<ordre.length&&chosen.length<size;i++){
   if(pris[ordre[i].cle_match])continue;
   pris[ordre[i].cle_match]=1;chosen.push(ordre[i]);
  }
  if(chosen.length<size)continue;
  var prod=1;chosen.forEach(function(x){prod*=Number(x.cote)});
  var t=tier(prod,target);
  if(t>=0&&(bestTier<0||t<bestTier)){bestTier=t;best=chosen;if(t===0)break}
 }
 return best;
}
/* Plusieurs tickets : n tickets de k paris, tirés au hasard dans les matchs cochés, aucun match utilisé deux fois
   (ni dans un ticket, ni entre tickets). Chaque ticket a une cote totale entre 2 et 20. S'il n'y a pas la place pour
   tous les tickets demandés, on s'arrête au dernier possible : rien n'est forcé. */
function tirageTickets(pool,n,k,rnd,tentatives){
 rnd=rnd||Math.random;tentatives=tentatives||TENTATIVES;
 var utilises={},tickets=[];
 var base=pool.filter(function(x){return Number(x.cote)>1});
 for(var t=0;t<n;t++){
  var dispo=base.filter(function(x){return !utilises[x.cle_match]});
  var vus={};dispo.forEach(function(x){vus[x.cle_match]=1});
  if(Object.keys(vus).length<k)break;
  var trouve=null;
  for(var i=0;i<tentatives&&!trouve;i++){
   var ordre=melange(dispo,rnd),pris={},chosen=[];
   for(var j=0;j<ordre.length&&chosen.length<k;j++){
    if(pris[ordre[j].cle_match])continue;
    pris[ordre[j].cle_match]=1;chosen.push(ordre[j]);
   }
   if(chosen.length<k)continue;
   var prod=1;chosen.forEach(function(x){prod*=Number(x.cote)});
   if(prod>=MIN-1e-9&&prod<=MAX+1e-9)trouve=chosen;
  }
  if(!trouve)break;
  trouve.forEach(function(x){utilises[x.cle_match]=1});
  tickets.push(trouve);
 }
 return tickets;
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
   else if(x.probabilite_source==="JOURNAL_REGULARITE"){if(x.journal_taux_lisse!=null)details.push("lissé "+pct(x.journal_taux_lisse))}
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

function parseTarget(raw){
 var v=parseFloat(String(raw).replace(",",".").replace(/\s/g,""));
 return Number.isFinite(v)?v:NaN;
}
function cleLigne(x){return String(x.cle_match)+"|"+String(x.marche)}
/* Matchs utilisés par le moteur : ceux que le parieur a cochés ; s'il n'en a coché aucun (dans la liste affichée),
   le moteur tire lui-même dans toute la liste. */
function cochesListe(){
 var pool=(DATA&&DATA.pool)||[];
 return pool.filter(function(x){return CHK[cleLigne(x)]});
}
function selection(){
 var pool=(DATA&&DATA.pool)||[],c=cochesListe();
 return c.length?c:pool;
}
function build(raw,defile){
 var msg=document.getElementById("cible-msg"),out=document.getElementById("ticket-cible");
 var v=parseTarget(raw);
 if(!Number.isFinite(v)){msg.textContent="Saisissez une cote entre "+MIN+" et "+MAX+".";out.innerHTML="";return}
 var note="";
 if(v<MIN){v=MIN;note="2 appliqué : la cote minimale est 2."}
 if(v>MAX){v=MAX;note="20 appliqué : la cote maximale est 20."}
 document.getElementById("cible").value=String(v).replace(".",",");
 try{localStorage.setItem("archetype_cote_cible",String(v))}catch(e){}
 var pool=selection();
 var matchs={};pool.forEach(function(x){matchs[x.cle_match]=1});
 if(Object.keys(matchs).length<2){
  msg.textContent="Pas assez de matchs différents ("+Object.keys(matchs).length+"). Cochez-en davantage ou changez de dates. Aucun ticket ne sera créé artificiellement.";
  out.innerHTML="";return;
 }
 document.getElementById("tickets-multi").innerHTML="";document.getElementById("multi-msg").textContent="";
 var rows=tirageCible(pool,v);
 var t={scenario:"VOTRE_TICKET_COTE_"+String(v).replace(".",","),statut:rows.length?"OK":"AUCUN_TICKET_SOLIDE",selection:rows,metrics:metrics(rows,v)};
 msg.textContent=note||(rows.length?"Objectif "+cote(v)+" · "+rows.length+" paris tirés au hasard parmi "+(cochesListe().length?"vos matchs cochés":"tous les matchs de la liste")+". Appuyez sur Générer pour un autre tirage.":"Les matchs disponibles ne permettent pas de s'approcher de "+cote(v)+". Cochez-en d'autres.");
 out.innerHTML=ticketHtml(t,"Votre ticket");
 if(defile&&rows.length&&out.scrollIntoView)out.scrollIntoView({behavior:"smooth",block:"start"});
}

function entier(raw,min,max){
 var v=parseInt(String(raw).replace(/\s/g,""),10);
 if(!Number.isFinite(v))return NaN;
 return Math.max(min,Math.min(max,v));
}
function buildMulti(){
 var msg=document.getElementById("multi-msg"),out=document.getElementById("tickets-multi");
 var n=entier(document.getElementById("nb-tickets").value,1,MAXTICKETS);
 var k=entier(document.getElementById("nb-paris").value,1,MAXLEGS);
 if(!Number.isFinite(n)||!Number.isFinite(k)){msg.textContent="Saisissez des nombres entiers (tickets : 1 à "+MAXTICKETS+", pronostics : 1 à "+MAXLEGS+").";out.innerHTML="";return}
 document.getElementById("nb-tickets").value=String(n);document.getElementById("nb-paris").value=String(k);
 try{localStorage.setItem("archetype_multi",n+","+k)}catch(e){}
 var pool=selection(),m={};pool.forEach(function(x){m[x.cle_match]=1});
 var dispo=Object.keys(m).length;
 if(dispo<k){msg.textContent="Il faut au moins "+k+" matchs différents (vous en avez "+dispo+"). Cochez-en davantage ou changez de dates. Aucun ticket ne sera créé artificiellement.";out.innerHTML="";return}
 var liste=tirageTickets(pool,n,k);
 document.getElementById("ticket-cible").innerHTML="";
 if(!liste.length){
  msg.textContent="Les matchs disponibles ne permettent pas de faire un ticket de "+k+" pronostics avec une cote entre 2 et 20. Cochez-en d'autres ou changez le nombre.";
  out.innerHTML="";return;
 }
 msg.textContent=liste.length===n
  ?n+" ticket(s) de "+k+" pronostic(s), aucun match répété. Appuyez sur Générer pour un autre tirage."
  :liste.length+" ticket(s) sur "+n+" demandés : pas assez de matchs pour les autres ("+(n*k)+" matchs différents seraient nécessaires, vous en avez "+dispo+"). Rien n'est forcé.";
 out.innerHTML=liste.map(function(rows,i){
  return ticketHtml({scenario:"TICKET_"+(i+1),statut:"OK",selection:rows,metrics:metrics(rows,null)},"Ticket "+(i+1)+" sur "+liste.length);
 }).join("");
 if(out.scrollIntoView)out.scrollIntoView({behavior:"smooth",block:"start"});
}

function init(){
 var form=document.getElementById("cible-form"),inp=document.getElementById("cible"),start=DEF;
 try{var s=parseFloat(localStorage.getItem("archetype_cote_cible"));if(Number.isFinite(s)&&s>=MIN&&s<=MAX)start=s}catch(e){}
 inp.value=String(start).replace(".",",");
 form.addEventListener("submit",function(e){e.preventDefault();build(inp.value,true)});
 Array.prototype.forEach.call(document.querySelectorAll("[data-cible]"),function(b){
  b.addEventListener("click",function(){build(b.getAttribute("data-cible"),true)});
 });
 document.getElementById("multi-form").addEventListener("submit",function(e){e.preventDefault();buildMulti()});
 try{var mm=(localStorage.getItem("archetype_multi")||"").split(",");
  if(mm.length===2&&Number.isFinite(parseInt(mm[0],10))&&Number.isFinite(parseInt(mm[1],10))){document.getElementById("nb-tickets").value=String(entier(mm[0],1,MAXTICKETS));document.getElementById("nb-paris").value=String(entier(mm[1],1,MAXLEGS))}}catch(e){}
 document.getElementById("tout-cocher").addEventListener("click",function(){
  ((DATA&&DATA.pool)||[]).forEach(function(x){CHK[cleLigne(x)]=1});renderMatchs();
 });
 document.getElementById("tout-decocher").addEventListener("click",function(){
  ((DATA&&DATA.pool)||[]).forEach(function(x){delete CHK[cleLigne(x)]});renderMatchs();
 });
}

/* ---------- Dates et liste des matchs ---------- */
function jourCourt(iso){
 var d=new Date(iso+"T12:00:00");
 return isNaN(d.getTime())?String(iso):d.toLocaleDateString("fr-FR",{weekday:"short",day:"numeric",month:"short"});
}
function jourLong(iso){
 var d=new Date(iso+"T12:00:00");
 return isNaN(d.getTime())?String(iso):d.toLocaleDateString("fr-FR",{weekday:"long",day:"numeric",month:"long"});
}
function plageLabel(p){
 if(p.debut===p.fin)return jourCourt(p.debut);
 var a=new Date(p.debut+"T12:00:00"),b=new Date(p.fin+"T12:00:00");
 if(isNaN(a.getTime())||isNaN(b.getTime()))return p.debut+" → "+p.fin;
 var mois=function(d){return d.toLocaleDateString("fr-FR",{month:"short"})};
 return a.getDate()+(mois(a)!==mois(b)?" "+mois(a):"")+" → "+b.getDate()+" "+mois(b);
}

function renderMatchs(){
 var root=document.getElementById("matchs"),pool=((DATA&&DATA.pool)||[]).slice();
 if(!pool.length){
  root.innerHTML='<div class="empty">Aucun pari disponible pour ces dates. Le système n\'en ajoute pas de force.</div>';
  document.getElementById("compteur").textContent="";
  return;
 }
 pool.sort(function(a,b){return String(a.date).localeCompare(String(b.date))||String(a.heure||"").localeCompare(String(b.heure||""))});
 var html="",jour=null;
 pool.forEach(function(x){
  if(x.date!==jour){jour=x.date;html+='<div class="jour-titre">'+esc(jourLong(x.date))+'</div>'}
  var k=cleLigne(x),coche=!!CHK[k];
  var proba=x.probabilite_estimee!=null?pct(x.probabilite_estimee):"—";
  html+='<label class="match-row"><input type="checkbox" data-k="'+esc(k)+'"'+(coche?" checked":"")+'>'+
   '<div class="corps"><div class="paris-top"><strong>'+esc(x.domicile)+" — "+esc(x.exterieur)+'</strong><span class="odds">'+cote(x.cote)+'</span></div>'+
   '<div class="small">'+esc((x.heure?x.heure+" · ":"")+marketLabel(x.marche))+" · chance estimée "+proba+'</div>'+
   '<div>'+badge(sourceLabel(x.source))+(x.rang?badge(x.rang):"")+'</div></div></label>';
 });
 root.innerHTML=html;
 Array.prototype.forEach.call(root.querySelectorAll("input[data-k]"),function(c){
  c.addEventListener("change",function(){
   if(c.checked)CHK[c.getAttribute("data-k")]=1;else delete CHK[c.getAttribute("data-k")];
   compteur();
  });
 });
 compteur();
}
function compteur(){
 var pool=(DATA&&DATA.pool)||[],c=cochesListe(),m={};
 selection().forEach(function(x){m[x.cle_match]=1});
 document.getElementById("compteur").textContent=c.length
  ?c.length+" pari(s) coché(s) sur "+pool.length+" · "+Object.keys(m).length+" match(s) différent(s). Le moteur n'utilisera que ceux-là."
  :"Aucun pari coché : le moteur tire lui-même dans les "+pool.length+" paris de la liste ("+Object.keys(m).length+" matchs différents).";
}

var RAW=null;
function afficherPlage(id){
 var p=null;
 ((RAW&&RAW.plages)||[]).forEach(function(x){if(x.id===id)p=x});
 if(!p)return;
 DATA={pool:p.pool||[],sources:p.sources||{}};
 var src=DATA.sources;
 document.getElementById("pool-note").textContent=
  "Paris retenus du "+plageLabel(p)+" : V2 "+(src.moteur_v2_6_10||0)+" · V3 "+(src.moteur_v3||0)+" · Journal "+(src.journal||0)+
  " (30 au maximum). Cochez les matchs que vous voulez ; si vous n'en cochez aucun, le moteur tire dans toute la liste.";
 Array.prototype.forEach.call(document.querySelectorAll("[data-plage]"),function(b){
  b.className=b.getAttribute("data-plage")===id?"chip active":"chip";
 });
 try{localStorage.setItem("archetype_plage",id)}catch(e){}
 renderMatchs();
 document.getElementById("ticket-cible").innerHTML="";
 document.getElementById("cible-msg").textContent="";
 document.getElementById("tickets-multi").innerHTML="";
 document.getElementById("multi-msg").textContent="";
}
function renderPlages(){
 var root=document.getElementById("plages");
 root.innerHTML="";
 ((RAW&&RAW.plages)||[]).forEach(function(p){
  var b=document.createElement("button");
  b.type="button";b.className="chip";b.setAttribute("data-plage",p.id);
  b.textContent=plageLabel(p);
  b.addEventListener("click",function(){afficherPlage(p.id)});
  root.appendChild(b);
 });
}

fetch("data/tickets.json?_="+Date.now(),{cache:"no-store"})
 .then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.json()})
 .then(function(d){
  RAW=d;
  document.getElementById("maj").textContent=d.genere_le?"Dernière génération : "+new Date(d.genere_le).toLocaleString("fr-FR"):"";
  renderPlages();init();
  var choix=d.plage_par_defaut;
  try{var m=localStorage.getItem("archetype_plage");if(m&&(d.plages||[]).some(function(p){return p.id===m}))choix=m}catch(e){}
  if((d.plages||[]).length)afficherPlage(choix);
  else document.getElementById("pool-note").textContent="Aucune plage de dates disponible.";
 })
 .catch(function(e){
  document.getElementById("maj").textContent="Impossible de charger les tickets";
  document.getElementById("pool-note").textContent="Les données ne sont pas disponibles pour le moment.";
  DATA={pool:[]};init();
 });
})();
