// selection.js — v3 (25/08ter) : panier unifié (checkbox + ajout manuel),
// barre fixe toujours visible en bas d'écran, un seul bouton "Tout copier"
// -> un seul fichier panier.json. Remplace l'ancien flux à deux fichiers
// (matchs_selectionnes.json / matchs_manuels.json) et la textarea perdue en
// bas de page, signalés comme pénibles à l'usage.

const donnees = { aujourdhui: null, demain: null };
let ongletActif = "aujourdhui";
// Panier : Map match_id -> item complet (domicile, exterieur, competition,
// url_match, match_id, source: "liste"|"manuel"). Une Map (pas un Set)
// pour pouvoir réafficher noms/compétition dans le panneau du panier sans
// re-chercher dans donnees.aujourdhui/demain à chaque fois.
const panier = new Map();

function formatEnTete(jour, nbMatchs) {
  return jour === "aujourdhui"
    ? `${nbMatchs} match(s) disponible(s) aujourd'hui`
    : `${nbMatchs} match(s) disponible(s) demain`;
}

function metAJourBarrePanier() {
  document.getElementById("barre-panier-texte").textContent = `🧺 Panier (${panier.size})`;
}

function rafraichitPanneauPanier() {
  const panneau = document.getElementById("panneau-panier");
  panneau.innerHTML = "";

  if (panier.size === 0) {
    panneau.innerHTML = "<div class='vide'>Panier vide.</div>";
    metAJourBarrePanier();
    return;
  }

  panier.forEach((item, matchId) => {
    const div = document.createElement("div");
    div.className = "item-panier";

    const texte = document.createElement("span");
    const tagTexte = item.source === "manuel" ? "manuel" : "liste";
    texte.innerHTML = `${item.domicile} — ${item.exterieur}<span class="tag">(${item.competition || "?"} · ${tagTexte})</span>`;

    const retirer = document.createElement("button");
    retirer.textContent = "✕";
    retirer.title = "Retirer du panier";
    retirer.addEventListener("click", () => {
      panier.delete(matchId);
      // Décoche aussi la case correspondante si elle est visible dans
      // l'onglet courant, pour rester synchronisé dans les deux sens.
      const checkbox = document.getElementById("match-" + matchId);
      if (checkbox) checkbox.checked = false;
      rafraichitPanneauPanier();
    });

    div.appendChild(texte);
    div.appendChild(retirer);
    panneau.appendChild(div);
  });

  const boutonCopier = document.createElement("button");
  boutonCopier.id = "tout-copier-btn";
  boutonCopier.textContent = `Tout copier (${panier.size})`;
  boutonCopier.addEventListener("click", copierPanier);
  panneau.appendChild(boutonCopier);

  const fallback = document.createElement("textarea");
  fallback.id = "copie-fallback";
  fallback.readOnly = true;
  fallback.placeholder = "Si la copie automatique échoue, le JSON apparaît ici -- sélectionne-le à la main.";
  panneau.appendChild(fallback);

  metAJourBarrePanier();
}

function copierPanier() {
  const items = Array.from(panier.values()).map((item) => ({
    match_id: item.match_id,
    domicile: item.domicile,
    exterieur: item.exterieur,
    competition: item.competition,
    url_match: item.url_match,
  }));
  const json = JSON.stringify(items, null, 2);
  const bouton = document.getElementById("tout-copier-btn");

  const confirmeVisuellement = () => {
    if (!bouton) return;
    const texteOriginal = bouton.textContent;
    bouton.textContent = "Copié ✓";
    bouton.classList.add("copie");
    setTimeout(() => {
      bouton.textContent = texteOriginal;
      bouton.classList.remove("copie");
    }, 1500);
  };

  if (navigator.clipboard) {
    navigator.clipboard.writeText(json).then(confirmeVisuellement).catch(() => {
      // Échec silencieux de l'API clipboard (permissions, contexte non
      // sécurisé...) -- on retombe sur la textarea visible, jamais une
      // action qui ne fait rien sans explication.
      const fallback = document.getElementById("copie-fallback");
      fallback.value = json;
      fallback.style.display = "block";
      fallback.select();
    });
  } else {
    const fallback = document.getElementById("copie-fallback");
    fallback.value = json;
    fallback.style.display = "block";
    fallback.select();
  }
}

function afficheListe(jour) {
  const matchs = donnees[jour];
  document.getElementById("maj").textContent = formatEnTete(jour, matchs ? matchs.length : 0);

  const liste = document.getElementById("liste");
  liste.innerHTML = "";
  if (!matchs || matchs.length === 0) {
    liste.innerHTML = "<p>aucun match disponible.</p>";
    return;
  }

  let competitionCourante = null;
  matchs.forEach((m) => {
    if (m.competition !== competitionCourante) {
      competitionCourante = m.competition;
      const entete = document.createElement("div");
      entete.className = "selection-competition";
      entete.textContent = (competitionCourante || "compétition inconnue").replace(/\s+/g, " ").trim();
      liste.appendChild(entete);
    }

    const div = document.createElement("div");
    div.className = "selection-item";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = "match-" + m.match_id;
    checkbox.checked = panier.has(m.match_id);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        panier.set(m.match_id, { ...m, source: "liste" });
      } else {
        panier.delete(m.match_id);
      }
      rafraichitPanneauPanier();
    });

    const heure = document.createElement("span");
    heure.className = "heure";
    heure.textContent = m.heure || "--:--";

    const label = document.createElement("label");
    label.htmlFor = checkbox.id;
    label.textContent = `${m.domicile} — ${m.exterieur}` + (m.score ? ` (${m.score})` : "");

    div.appendChild(checkbox);
    div.appendChild(heure);
    div.appendChild(label);
    liste.appendChild(div);
  });
}

function activeOnglet(jour) {
  ongletActif = jour;
  document.getElementById("onglet-aujourdhui").classList.toggle("actif", jour === "aujourdhui");
  document.getElementById("onglet-demain").classList.toggle("actif", jour === "demain");
  afficheListe(jour);
}

function chargeJour(jour, fichier) {
  return fetch(fichier + "?_=" + Date.now())
    .then((r) => {
      if (!r.ok) throw new Error(fichier + " introuvable (status " + r.status + ")");
      return r.json();
    })
    .then((data) => {
      donnees[jour] = Array.isArray(data) ? data : (data.matchs || []);
    })
    .catch((err) => {
      donnees[jour] = [];
      console.error(jour, err);
    });
}

Promise.all([
  chargeJour("aujourdhui", "matchs_du_jour.json"),
  chargeJour("demain", "matchs_demain.json"),
]).then(() => {
  activeOnglet(ongletActif);
  rafraichitPanneauPanier();
});

document.getElementById("onglet-aujourdhui").addEventListener("click", () => activeOnglet("aujourdhui"));
document.getElementById("onglet-demain").addEventListener("click", () => activeOnglet("demain"));

// --- Barre de panier : ouvre/ferme le panneau en tapant n'importe où dessus ---
document.getElementById("barre-panier").addEventListener("click", () => {
  const barre = document.getElementById("barre-panier");
  const panneau = document.getElementById("panneau-panier");
  barre.classList.toggle("ouvert");
  panneau.classList.toggle("ouvert");
});

// --- Ajout manuel : va directement dans le panier, comme une case cochée ---
const RE_MATCH_URL = /\/live-score\/([a-z0-9-]+)_([a-z0-9]+)\.html/i;

document.getElementById("ajouter-manuel-btn").addEventListener("click", () => {
  const url = document.getElementById("manuel-url").value.trim();
  const domicile = document.getElementById("manuel-domicile").value.trim();
  const exterieur = document.getElementById("manuel-exterieur").value.trim();
  const competition = document.getElementById("manuel-competition").value.trim();

  const trouve = url.match(RE_MATCH_URL);
  if (!trouve) {
    alert("URL matchendirect invalide -- doit ressembler à https://www.matchendirect.fr/live-score/xxx_id.html");
    return;
  }
  if (!domicile || !exterieur || !competition) {
    alert("Domicile, extérieur et compétition sont obligatoires.");
    return;
  }

  const matchId = trouve[2];
  panier.set(matchId, {
    match_id: matchId, url_match: url, domicile, exterieur, competition, source: "manuel",
  });
  rafraichitPanneauPanier();
  // Ouvre le panier automatiquement pour confirmer visuellement l'ajout,
  // sans forcer l'utilisateur à aller chercher la barre en bas.
  document.getElementById("barre-panier").classList.add("ouvert");
  document.getElementById("panneau-panier").classList.add("ouvert");

  document.getElementById("manuel-url").value = "";
  document.getElementById("manuel-domicile").value = "";
  document.getElementById("manuel-exterieur").value = "";
  document.getElementById("manuel-competition").value = "";
});
