// betpawa.js — page dédiée au dépôt Betpawa (26/08sexies). Parse le texte
// brut côté client (parseBetpawa.js, portage exact de parse_betpawa.py --
// vérifié identique sur 5 matchs réels) et pousse l'entrée dans le MÊME
// localStorage que index.js/panier.js : un seul panier, peu importe la
// source du match.

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

// CORRECTIF (26/08sexies) : détecte domicile/extérieur directement dans le
// texte collé -- le format Betpawa observé sur tous les matchs testés place
// toujours les deux noms d'équipe juste après la ligne "Retour" (ou juste
// avant "Football//" en repli si "Retour" est absent). Évite la confusion
// entre placeholder grisé et valeur réellement saisie qui bloquait l'ajout.
function detecteEquipes(texte) {
  const lignes = texte.split("\n").map((l) => l.trim()).filter((l) => l.length > 0);
  const idxRetour = lignes.indexOf("Retour");
  if (idxRetour !== -1 && idxRetour + 2 < lignes.length) {
    return { domicile: lignes[idxRetour + 1], exterieur: lignes[idxRetour + 2] };
  }
  const idxFootball = lignes.findIndex((l) => l.startsWith("Football"));
  if (idxFootball >= 2) {
    return { domicile: lignes[idxFootball - 2], exterieur: lignes[idxFootball - 1] };
  }
  return null;
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

function rafraichitListeSession() {
  const conteneur = document.getElementById("items-session");
  const betpawaItems = chargePanier()
    .map((item, i) => ({ item, i }))
    .filter(({ item }) => item.source === "betpawa");

  conteneur.innerHTML = "";
  if (betpawaItems.length === 0) {
    conteneur.innerHTML = "<div class='item-session'>Aucun match Betpawa dans le panier pour l'instant.</div>";
    return;
  }

  betpawaItems.forEach(({ item }) => {
    const div = document.createElement("div");
    div.className = "item-session";
    const nbMarches = item.cotes_manuelles ? Object.keys(item.cotes_manuelles).length : 0;
    const texte = document.createElement("span");
    texte.innerHTML = `${item.domicile} — ${item.exterieur}` +
      `<span class="tag">${item.competition} · ${nbMarches} marché(s)` +
      (item.url_match ? "" : " · sans URL matchendirect") + `</span>`;

    const retirer = document.createElement("button");
    retirer.textContent = "✕";
    retirer.title = "Retirer du panier";
    retirer.style.cssText = "background:none;border:none;color:#C84E50;font-size:1.1em;cursor:pointer;padding:4px 8px;";
    retirer.addEventListener("click", () => {
      const p = chargePanier().filter((x) => x.match_id !== item.match_id);
      sauvePanier(p);
      metAJourBoutonPanier();
      rafraichitListeSession();
    });

    div.appendChild(texte);
    div.appendChild(retirer);
    conteneur.appendChild(div);
  });
}

// Auto-détection à la saisie -- ne remplace que des champs vides, pour ne
// jamais écraser une correction manuelle que Patrick aurait déjà faite.
document.getElementById("brut-betpawa").addEventListener("input", () => {
  const texte = document.getElementById("brut-betpawa").value;
  const detecte = detecteEquipes(texte);
  if (!detecte) return;

  const champDomicile = document.getElementById("bp-domicile");
  const champExterieur = document.getElementById("bp-exterieur");

  if (!champDomicile.value.trim()) {
    champDomicile.value = detecte.domicile;
    document.getElementById("detecte-domicile").classList.add("visible");
  }
  if (!champExterieur.value.trim()) {
    champExterieur.value = detecte.exterieur;
    document.getElementById("detecte-exterieur").classList.add("visible");
  }
});

document.getElementById("ajouter-btn").addEventListener("click", () => {
  const domicile = document.getElementById("bp-domicile").value.trim();
  const exterieur = document.getElementById("bp-exterieur").value.trim();
  const competition = document.getElementById("bp-competition").value.trim();
  const url = document.getElementById("bp-url").value.trim();
  const brut = document.getElementById("brut-betpawa").value;

  // CORRECTIF (26/08septies) : signale précisément LE(S) champ(s) vide(s)
  // au lieu d'un message générique -- deux confusions de suite (placeholder
  // pris pour une valeur remplie) montrent que "les 3 sont obligatoires"
  // ne suffit pas à localiser le problème quand 2 champs sur 3 sont déjà
  // corrects. Le champ fautif est aussi entouré en rouge, pas seulement
  // nommé dans le texte.
  const champsRequis = [
    { id: "bp-domicile", valeur: domicile, nom: "Équipe domicile" },
    { id: "bp-exterieur", valeur: exterieur, nom: "Équipe extérieur" },
    { id: "bp-competition", valeur: competition, nom: "Compétition" },
  ];
  const manquants = champsRequis.filter((c) => !c.valeur);
  champsRequis.forEach((c) => {
    document.getElementById(c.id).style.borderColor = manquants.includes(c) ? "#C84E50" : "";
  });
  if (manquants.length > 0) {
    afficheResultat(
      "Champ manquant : " + manquants.map((c) => c.nom).join(", ") + ".",
      false
    );
    document.getElementById(manquants[0].id).focus();
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
      ` (${Object.keys(cotes).length} marché(s)). Prêt pour le match suivant.` +
      (url ? "" : " Sans URL matchendirect -- sera marqué non traité tant qu'une source de forme n'est pas branchée."),
    true
  );
  metAJourBoutonPanier();
  rafraichitListeSession();

  // CORRECTIF (26/08sexies) : les 4 champs sont désormais réinitialisés (pas
  // seulement le texte collé), pour enchaîner plusieurs matchs sans jamais
  // laisser une équipe ou une compétition du match précédent traîner dans
  // le formulaire.
  document.getElementById("brut-betpawa").value = "";
  document.getElementById("bp-domicile").value = "";
  document.getElementById("bp-exterieur").value = "";
  document.getElementById("bp-competition").value = "";
  document.getElementById("bp-url").value = "";
  document.getElementById("bp-domicile").style.borderColor = "";
  document.getElementById("bp-exterieur").style.borderColor = "";
  document.getElementById("bp-competition").style.borderColor = "";
  document.getElementById("detecte-domicile").classList.remove("visible");
  document.getElementById("detecte-exterieur").classList.remove("visible");
});

metAJourBoutonPanier();
rafraichitListeSession();
