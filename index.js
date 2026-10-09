// Accueil — affichage conjoint des matchs du jour et du lendemain.
const CLE_PANIER = "archetype_panier";
const donnees = { aujourdhui: [], demain: [] };

function chargePanier(){
  try {
    const brut = localStorage.getItem(CLE_PANIER);
    const liste = brut ? JSON.parse(brut) : [];
    return Array.isArray(liste) ? liste : [];
  } catch (e) { console.error("Panier illisible :", e); return []; }
}
function sauvePanier(liste){ localStorage.setItem(CLE_PANIER, JSON.stringify(liste)); }
function ajouterAuPanier(match){
  if (!match || !match.match_id) return;
  const panier = chargePanier();
  if (!panier.some(m => String(m.match_id) === String(match.match_id))) {
    panier.push({...match, source: match.source || "liste"});
    sauvePanier(panier);
  }
}
function retirerDuPanier(matchId){
  sauvePanier(chargePanier().filter(m => String(m.match_id) !== String(matchId)));
}
function afficheJour(jour, titre, liste){
  const section = document.createElement("section");
  section.className = "bloc-jour-matchs";
  const h2 = document.createElement("h2");
  h2.className = "titre-jour-matchs";
  h2.textContent = titre;
  section.appendChild(h2);
  if (!liste.length) {
    const vide = document.createElement("p");
    vide.className = "vide";
    vide.textContent = "Aucun match disponible pour cette journée.";
    section.appendChild(vide);
    return section;
  }
  const idsAuPanier = new Set(chargePanier().map(m => String(m.match_id)));
  let competitionCourante = null;
  liste.forEach(m => {
    if (!m || !m.match_id) return;
    if (m.competition !== competitionCourante) {
      competitionCourante = m.competition;
      const entete = document.createElement("div");
      entete.className = "selection-competition";
      entete.textContent = (competitionCourante || "Compétition inconnue").replace(/\s+/g, " ").trim();
      section.appendChild(entete);
    }
    const ligne = document.createElement("div");
    ligne.className = "selection-item";
    const heure = document.createElement("span");
    heure.className = "heure";
    heure.textContent = m.heure_cameroun || m.heure || "--:--";
    const equipes = document.createElement("span");
    equipes.className = "equipes-liste";
    equipes.textContent = `${m.domicile || "Équipe domicile"} — ${m.exterieur || "Équipe extérieure"}` + (m.score ? ` (${m.score})` : "");
    ligne.appendChild(heure);
    ligne.appendChild(equipes);
    section.appendChild(ligne);
  });
  return section;
}
function chargeJour(jour, fichier){
  return fetch(fichier + "?_=" + Date.now()).then(r => {
    if (!r.ok) throw new Error(`${fichier} introuvable (${r.status})`);
    return r.json();
  }).then(data => donnees[jour] = Array.isArray(data) ? data : (data && Array.isArray(data.matchs) ? data.matchs : []))
    .catch(err => { donnees[jour] = []; console.error(jour, err); });
}
Promise.all([
  chargeJour("aujourdhui", "matchs_du_jour_filtre.json"),
  chargeJour("demain", "matchs_demain_filtre.json")
]).then(() => {
  const liste = document.getElementById("liste");
  const maj = document.getElementById("maj");
  if (!liste) return;
  liste.replaceChildren(
    afficheJour("aujourdhui", "Matchs d’aujourd’hui", donnees.aujourdhui),
    afficheJour("demain", "Matchs de demain", donnees.demain)
  );
  if (maj) maj.textContent = `${donnees.aujourdhui.length} match(s) aujourd’hui · ${donnees.demain.length} demain`;
});
