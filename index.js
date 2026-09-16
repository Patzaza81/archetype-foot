// index.js — v7
// Affichage de l'heure locale déjà préparée par le pipeline, sans libellé
// « heure Cameroun » : l'application est destinée au public camerounais.

const CLE_PANIER = "archetype_panier";
const donnees = { aujourdhui:null, demain:null };
let ongletActif = "aujourdhui";

function chargePanier(){
  try{
    const brut=localStorage.getItem(CLE_PANIER);
    if(!brut) return [];
    const panier=JSON.parse(brut);
    return Array.isArray(panier)?panier:[];
  }catch(e){ console.error("Panier illisible, réinitialisé :",e); return []; }
}
function sauvePanier(liste){ localStorage.setItem(CLE_PANIER,JSON.stringify(liste)); }
function metAJourBoutonPanier(){
  const bouton=document.getElementById("nav-panier");
  if(bouton) bouton.textContent=`🧺 Panier (${chargePanier().length})`;
}
function ajouterAuPanier(match){
  if(!match||!match.match_id) return;
  const panier=chargePanier();
  if(!panier.some(m=>String(m.match_id)===String(match.match_id))){
    panier.push({...match,source:match.source||"liste"});
    sauvePanier(panier);
  }
  metAJourBoutonPanier();
}
function retirerDuPanier(matchId){
  sauvePanier(chargePanier().filter(m=>String(m.match_id)!==String(matchId)));
  metAJourBoutonPanier();
}
function formatEnTete(jour,nbMatchs){
  const labels={aujourdhui:"aujourd'hui",demain:"demain"};
  return `${nbMatchs} match(s) disponible(s) ${labels[jour]||jour}`;
}
function afficheListe(jour){
  const matchs=donnees[jour], maj=document.getElementById("maj"), liste=document.getElementById("liste");
  if(maj) maj.textContent=formatEnTete(jour,matchs?matchs.length:0);
  if(!liste) return;
  liste.innerHTML="";
  if(!matchs||matchs.length===0){liste.innerHTML="<p>aucun match disponible.</p>";return;}
  const idsAuPanier=new Set(chargePanier().map(m=>String(m.match_id)));
  let competitionCourante=null;
  matchs.forEach(m=>{
    if(!m||!m.match_id) return;
    if(m.competition!==competitionCourante){
      competitionCourante=m.competition;
      const entete=document.createElement("div");
      entete.className="selection-competition";
      entete.textContent=(competitionCourante||"compétition inconnue").replace(/\s+/g," ").trim();
      liste.appendChild(entete);
    }
    const div=document.createElement("div");
    div.className="selection-item";
    const input=document.createElement("input");
    input.type="checkbox";
    input.id="match-"+m.match_id;
    input.checked=idsAuPanier.has(String(m.match_id));
    input.addEventListener("change",()=>{
      if(input.checked) ajouterAuPanier({...m,source:"liste"});
      else retirerDuPanier(m.match_id);
    });
    const heure=document.createElement("span");
    heure.className="heure";
    heure.textContent=m.heure_cameroun||m.heure||"--:--";
    const label=document.createElement("label");
    label.htmlFor=input.id;
    label.textContent=`${m.domicile||"Équipe domicile"} — ${m.exterieur||"Équipe extérieur"}`+(m.score?` (${m.score})`:"");
    div.appendChild(input); div.appendChild(heure); div.appendChild(label); liste.appendChild(div);
  });
}
function activeOnglet(jour){
  ongletActif=jour;
  [["onglet-aujourdhui","aujourdhui"],["onglet-demain","demain"]].forEach(([id,valeur])=>{
    const element=document.getElementById(id);
    if(element) element.classList.toggle("actif",jour===valeur);
  });
  afficheListe(jour);
}
function chargeJour(jour,fichier){
  return fetch(fichier+"?_="+Date.now()).then(r=>{
    if(!r.ok) throw new Error(`${fichier} introuvable (status ${r.status})`);
    return r.json();
  }).then(data=>{
    donnees[jour]=Array.isArray(data)?data:(data&&Array.isArray(data.matchs)?data.matchs:[]);
  }).catch(err=>{donnees[jour]=[];console.error(jour,err);});
}
Promise.all([chargeJour("aujourdhui","matchs_du_jour_filtre.json"),chargeJour("demain","matchs_demain_filtre.json")]).then(()=>{
  activeOnglet(ongletActif); metAJourBoutonPanier();
});
const boutonAujourdhui=document.getElementById("onglet-aujourdhui");
if(boutonAujourdhui) boutonAujourdhui.addEventListener("click",()=>activeOnglet("aujourdhui"));
const boutonDemain=document.getElementById("onglet-demain");
if(boutonDemain) boutonDemain.addEventListener("click",()=>activeOnglet("demain"));
window.addEventListener("storage",event=>{
  if(event.key===CLE_PANIER){metAJourBoutonPanier();if(donnees[ongletActif]) afficheListe(ongletActif);}
});
