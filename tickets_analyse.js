/* Marge d'erreur et rentabilité d'un ticket — même calcul que analyse_ticket() de generateur_tickets.py.
   Format « k parmi n » : mise répartie sur les C(n, k) combinés de k paris (k = n : combiné, k = 1 : simples).
   Espérance de gain par unité misée = e_k(p·cote) / C(n, k) − 1. Paris supposés indépendants. */
(function(root){
"use strict";
function comb(n,k){if(k<0||k>n)return 0;var r=1;for(var i=1;i<=k;i++)r=r*(n-k+i)/i;return Math.round(r)}
function pbDist(ps){
 var d=[1];
 ps.forEach(function(p){var nd=new Array(d.length+1).fill(0);d.forEach(function(v,k){nd[k]+=v*(1-p);nd[k+1]+=v*p});d=nd});
 return d;
}
function elementary(vals,kmax){
 var e=[1];for(var i=0;i<kmax;i++)e.push(0);
 vals.forEach(function(v){for(var k=kmax;k>0;k--)e[k]+=e[k-1]*v});
 return e;
}
function formatName(k,size){return k===size?"COMBINE":(k===1?"SIMPLES":"SYSTEME_"+k+"_SUR_"+size)}
function round(x,d){var m=Math.pow(10,d);return Math.round(x*m)/m}
function analyse(rows){
 var size=rows.length;if(size<2)return null;
 var ps=[],os=[];
 for(var i=0;i<size;i++){
  var raw=rows[i].probabilite_estimee,p=Number(raw),o=Number(rows[i].cote);
  if(raw==null||!(p>0&&p<1)||!(o>1))return null;
  ps.push(p);os.push(o);
 }
 var dist=pbDist(ps),atLeast=[];
 for(var m=0;m<=size;m++){var s=0;for(var j=m;j<=size;j++)s+=dist[j];atLeast.push(s)}
 var geo=Math.exp(os.reduce(function(a,o){return a+Math.log(o)},0)/size);
 var e=elementary(ps.map(function(p,i){return p*os[i]}),size);
 var ks=[1];for(var k=Math.max(2,size-3);k<=size;k++)if(ks.indexOf(k)<0)ks.push(k);
 ks.sort(function(a,b){return a-b});
 var formats=ks.map(function(k){
  var combos=comb(size,k),needed=size;
  for(var m2=k;m2<=size;m2++){if(comb(m2,k)*Math.pow(geo,k)>=combos*(1-1e-12)){needed=m2;break}}
  return{nom:formatName(k,size),paris_par_combine:k,combines:combos,esperance_gain:round(e[k]/combos-1,4),
   bonnes_requises:needed,erreurs_tolerees:size-needed,proba_atteindre:round(atLeast[needed],4)};
 });
 var best=formats[0];formats.forEach(function(f){if(f.esperance_gain>best.esperance_gain)best=f});
 var reg=null;
 formats.forEach(function(f){
  if(!(f.esperance_gain>0))return;
  if(!reg||f.proba_atteindre>reg.proba_atteindre||(f.proba_atteindre===reg.proba_atteindre&&f.esperance_gain>reg.esperance_gain))reg=f;
 });
 var sum=ps.reduce(function(a,b){return a+b},0);
 return{paris:size,probabilite_bonnes:dist.map(function(v){return round(v,6)}),paris_justes_attendus:round(sum,4),
  taux_estime_moyen:round(sum/size,4),taux_requis_simples:round(1/geo,4),formats:formats,
  meilleur_format:best.nom,format_le_plus_regulier:reg?reg.nom:null,rentable:best.esperance_gain>0};
}
var api={analyse:analyse};
if(typeof module!=="undefined"&&module.exports)module.exports=api;else root.ArchetypeAnalyse=api;
})(typeof window!=="undefined"?window:this);
