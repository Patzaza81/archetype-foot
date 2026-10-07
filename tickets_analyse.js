/* Marge d'erreur et rentabilité d'un ticket — même calcul que analyse_ticket() de generateur_tickets.py.
   Plan = les n paris répartis en t tickets disjoints (ex. 12 paris en 4 tickets de 3).
   Mise au prorata de 1/cote du ticket : un ticket gagnant rapporte R = 1 / Σ(1/cote_ticket) par unité misée.
   Gagnants requis = ceil(1/R) ; erreurs garanties = t − gagnants requis. Paris supposés indépendants. */
(function(root){
"use strict";
function pbDist(ps){
 var d=[1];
 ps.forEach(function(p){var nd=new Array(d.length+1).fill(0);d.forEach(function(v,k){nd[k]+=v*(1-p);nd[k+1]+=v*p});d=nd});
 return d;
}
function round(x,d){var m=Math.pow(10,d);return Math.round(x*m)/m}
function planSizes(size,t){var base=Math.floor(size/t),extra=size%t,r=[];for(var i=0;i<t;i++)r.push(i<extra?base+1:base);return r}
function planPartition(odds,t){
 var caps=planSizes(odds.length,t),groups=[],sums=[],i,j;
 for(j=0;j<t;j++){groups.push([]);sums.push(0)}
 var order=odds.map(function(_,i){return i});
 order.sort(function(a,b){var d=Math.log(odds[b])-Math.log(odds[a]);return d!==0?d:a-b});
 order.forEach(function(i){
  var bj=-1;
  for(j=0;j<t;j++){if(groups[j].length>=caps[j])continue;if(bj<0||sums[j]<sums[bj])bj=j}
  groups[bj].push(i);sums[bj]+=Math.log(odds[i]);
 });
 return groups.map(function(g){return g.slice().sort(function(a,b){return a-b})});
}
function planName(sizes,size){
 var t=sizes.length,mn=Math.min.apply(null,sizes),mx=Math.max.apply(null,sizes);
 if(t===1)return"COMBINE";
 if(t===size)return"SIMPLES";
 return mn===mx?"TICKETS_"+t+"X"+mn:"TICKETS_"+t+"_DE_"+mn+"_A_"+mx;
}
function analysePlan(probs,odds,t){
 var size=probs.length,groups=planPartition(odds,t),tOdds=[],tProbs=[];
 groups.forEach(function(g){var o=1,p=1;g.forEach(function(i){o*=odds[i];p*=probs[i]});tOdds.push(o);tProbs.push(p)});
 var inv=tOdds.reduce(function(a,o){return a+1/o},0),ret=1/inv,need=Math.ceil(1/ret-1e-12);
 var dist=pbDist(tProbs),feasible=need<=t,pp=0;
 if(feasible)for(var k=need;k<=t;k++)pp+=dist[k];
 var sumP=tProbs.reduce(function(a,b){return a+b},0);
 return{nom:planName(groups.map(function(g){return g.length}),size),tickets:t,tailles:groups.map(function(g){return g.length}),
  composition:groups.map(function(g,j){return{paris:g,cote:round(tOdds[j],4),probabilite:round(tProbs[j],6),mise:round((1/tOdds[j])/inv,4)}}),
  retour_garanti:round(ret,4),gagnants_requis:feasible?need:null,erreurs_garanties:feasible?t-need:null,
  proba_profit:feasible?round(pp,4):0,esperance_gain:round(ret*sumP-1,4)};
}
function analyse(rows){
 var size=rows.length;if(size<2)return null;
 var ps=[],os=[];
 for(var i=0;i<size;i++){
  var raw=rows[i].probabilite_estimee,p=Number(raw),o=Number(rows[i].cote);
  if(raw==null||!(p>0&&p<1)||!(o>1))return null;
  ps.push(p);os.push(o);
 }
 var dist=pbDist(ps),counts=[1,size];
 for(var t=2;t<=Math.floor(size/2);t++)if(counts.indexOf(t)<0)counts.push(t);
 counts.sort(function(a,b){return a-b});
 var plans=counts.map(function(t){return analysePlan(ps,os,t)});
 var best=plans[0];plans.forEach(function(p){if(p.esperance_gain>best.esperance_gain)best=p});
 var reg=null,marge=null;
 plans.forEach(function(p){
  if(!(p.esperance_gain>0)||p.gagnants_requis==null)return;
  if(!reg||p.proba_profit>reg.proba_profit||(p.proba_profit===reg.proba_profit&&p.esperance_gain>reg.esperance_gain))reg=p;
  if(!marge||p.erreurs_garanties>marge.erreurs_garanties||(p.erreurs_garanties===marge.erreurs_garanties&&p.esperance_gain>marge.esperance_gain))marge=p;
 });
 var sum=ps.reduce(function(a,b){return a+b},0);
 return{paris:size,probabilite_bonnes:dist.map(function(v){return round(v,6)}),paris_justes_attendus:round(sum,4),
  taux_estime_moyen:round(sum/size,4),plans:plans,meilleur_plan:best.nom,
  plan_le_plus_regulier:reg?reg.nom:null,plan_marge_max:marge?marge.nom:null,rentable:best.esperance_gain>0};
}
var api={analyse:analyse};
if(typeof module!=="undefined"&&module.exports)module.exports=api;else root.ArchetypeAnalyse=api;
})(typeof window!=="undefined"?window:this);
