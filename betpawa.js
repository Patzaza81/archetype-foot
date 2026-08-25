// betpawa.js — page dédiée au dépôt Betpawa (26/08quinquies). Parse le
// texte brut côté client (parseBetpawa.js, portage exact de
// parse_betpawa.py -- vérifié identique sur 5 matchs réels) et pousse
// l'entrée dans le MÊME localStorage que index.js/panier.js/selection.js :
// un seul panier, peu importe la source du match.

const CLE_PANIER = "archetype_panier";

function chargePanier() {
  try {
    const brut = localStorage.getItem(CLE_PANIER);
    return brut ? JSON.parse(brut) : [];
  } catch (e) {
    console.error("panier illisible, réinitialisé", e);
    return [];
  }
}

function sauvePanier(liste) {
  localStorage.setItem(CLE_PANIER, JSON.stringify(liste));
}

function metAJourBoutonPanier() {
  const n = chargePanier().length;
  document.getElementById("nav-panier").textContent = `🧺 Panier (${n})`;
}

function slug(s) {
  return s
    .toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function dateDuJourISO() {
  return new Date().toISOString().slice(0, 10);
}

function genererMatchId(domicile, exterieur) {
  // Déterministe (pas de composant aléatoire) sauf la date -- deux dépôts du
  // même match le même jour fusionnent naturellement (le panier dédoublonne
  // déjà par match_id), un dépôt le lendemain crée une entrée distincte.
  return `betpawa_${slug(domicile)}_${slug(exterieur)}_${dateDuJourISO()}`;
}

function afficheResultat(message, ok) {
  const div = document.getElementById("resultat-ajout");
  div.textContent = message;
  div.className = ok ? "ok" : "erreur";
}

function afficheApercu(cotes) {
  const div = document.getElementById("apercu-marches");
  const cles = Object.keys(cotes);
  if (cles.length === 0) {
    div.className = "";
    div.textContent = "";
    return;
  }
  div.className = "visible";
  div.innerHTML = `<strong>${cles.length} marché(s) reconnu(s) :</strong> ` + cles.join(", ");
}

document.getElementById("ajouter-btn").addEventListener("click", () => {
  const domicile = document.getElementById("bp-domicile").value.trim();
  const exterieur = document.getElementById("bp-exterieur").value.trim();
  const competition = document.getElementById("bp-competition").value.trim();
  const url = document.getElementById("bp-url").value.trim();
  const brut = document.getElementById("brut-betpawa").value;

  if (!domicile || !exterieur || !competition) {
    afficheResultat("Équipe domicile, extérieur et compétition sont obligatoires.", false);
    return;
  }
  if (!brut.trim()) {
    afficheResultat("Colle le texte brut Betpawa avant d'ajouter.", false);
    return;
  }

  let cotes;
  try {
    cotes = parseBetpawa(brut, domicile, exterieur);
  } catch (e) {
    afficheResultat("Erreur d'analyse du texte collé : " + e.message, false);
    return;
  }

  if (Object.keys(cotes).length === 0) {
    afficheResultat(
      "Aucun marché reconnu dans le texte collé. Vérifie que les noms " +
      "d'équipes saisis correspondent EXACTEMENT à ceux affichés sur Betpawa " +
      "(accents, abréviations) -- les marchés par équipe (over/under, cages " +
      "inviolées) en dépendent.",
      false
    );
    afficheApercu({});
    return;
  }

  const matchId = genererMatchId(domicile, exterieur);
  const panier = chargePanier();
  const indexExistant = panier.findIndex((p) => p.match_id === matchId);
  const dejaPresent = indexExistant !== -1;

  const entree = {
    match_id: matchId,
    domicile, exterieur, competition,
    url_match: url || null,
    source: "betpawa",
    cotes_manuelles: cotes,
  };

  if (dejaPresent) {
    panier[indexExistant] = entree;
  } else {
    panier.push(entree);
  }
  sauvePanier(panier);

  afficheApercu(cotes);
  afficheResultat(
    (dejaPresent
      ? `${domicile} — ${exterieur} déjà présent aujourd'hui -- cotes remplacées`
      : `${domicile} — ${exterieur} ajouté au panier`) +
      ` (${Object.keys(cotes).length} marché(s)).` +
      (url ? "" : " Sans URL matchendirect -- sera marqué non traité tant qu'une source de forme n'est pas branchée."),
    true
  );
  metAJourBoutonPanier();

  document.getElementById("brut-betpawa").value = "";
});

metAJourBoutonPanier();
