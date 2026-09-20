// panier.js — présentation du panier uniquement.
// Aucun calcul, aucune sélection, aucun nouveau run.
const CLE_PANIER = "archetype_panier";
function chargePanier(){try{const brut=localStorage.getItem(CLE_PANIER);if(!brut)return[];const panier=JSON.parse(brut);return Array.isArray(panier)?panier:[]}catch{return[]}}
function sauvePanier(liste){localStorage.setItem(CLE_PANIER,JSON.stringify(liste))}
function identitePanier(m){if(m&&m.match_id!==undefined&&m.match_id!==null&&String(m.match_id).trim()!=="")return `id:${String(m.match_id)}`;return `match:${String(m?.date||"").trim()}|${String(m?.heure_cameroun||m?.heure||"").trim()}|${String(m?.domicile||"").trim().toLowerCase()}|${String(m?.exterieur||"").trim().toLowerCase()}`}
function panierUnique(liste){const vu=new Set();return (liste||[]).filter(m=>{const cle=identitePanier(m);if(vu.has(cle))return false;vu.add(cle);return true})}
function retirerDuPanier(item){sauvePanier(chargePanier().filter(m=>identitePanier(m)!==identitePanier(item)));affichePanier()}
function construitEtatVide(item){
  const bloc=document.createElement("div");bloc.className="ax-etat-vide";
  bloc.innerHTML=`<strong>${echappeHtml(item.domicile||"Équipe à domicile")} – ${echappeHtml(item.exterieur||"Équipe à l'extérieur")}</strong><p>Aucune sélection Archetype pour ce match pour l'instant.</p>`;
  const retirer=document.createElement("button");retirer.type="button";retirer.className="ax-retirer ax-retirer-bloc";retirer.textContent="Retirer";
  retirer.setAttribute("aria-label","Retirer du panier");retirer.addEventListener("click",()=>retirerDuPanier(item));
  bloc.appendChild(retirer);return bloc}
// Même carte que sur la page principale (construitCarte) : seule différence, le bouton « Retirer » dans l'en-tête.
// Même règle d'ouverture : le premier match est déplié, les suivants repliés.
function construitCartePanier(item,signal,index){
  if(signal&&estArchetypeGo(signal))return construitCarte(signal,{replie:index>0,action:{libelle:"Retirer",aria:"Retirer du panier",onClick:()=>retirerDuPanier(item)}});
  return construitEtatVide(item)}
function affichePanier(){const root=document.getElementById("panier-cartes"),statut=document.getElementById("statut-panier"),panier=panierUnique(chargePanier());if(!panier.length){statut.textContent="Ton panier est vide.";root.innerHTML="";return}sauvePanier(panier);statut.textContent="Chargement…";fetch(`precalcul_leger.json?_=${Date.now()}`).then(r=>{if(!r.ok)throw new Error(`precalcul_leger.json introuvable (${r.status})`);return r.json()}).then(d=>{const signaux=regroupeMatchs(d.signaux||[]);const parId=new Map(signaux.map(s=>[identitePanier(s),s]));root.innerHTML="";let nbAvecSelection=0;panier.forEach((item,index)=>{const signal=parId.get(identitePanier(item));if(signal&&estArchetypeGo(signal))nbAvecSelection++;root.appendChild(construitCartePanier(item,signal,index))});statut.textContent=`${panier.length} match${panier.length>1?"s":""} dans le panier — ${nbAvecSelection} avec une sélection Archetype.`}).catch(e=>{statut.textContent="Erreur de chargement : "+e.message;console.error(e)})}
affichePanier();
