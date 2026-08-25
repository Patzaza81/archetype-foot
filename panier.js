// panier.js — page dédiée au panier (25/08quinquies). Lit/écrit le même
// localStorage que index.js -- c'est le seul lien entre les deux pages,
// puisqu'une navigation complète recharge tout le JS.

const CLE_PANIER = "archetype_panier";
const RE_MATCH_URL = /\/live-score\/([a-z0-9-]+)_([a-z0-9]+)\.html/i;

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

function rafraichit() {
  const panier = chargePanier();
  const conteneur = document.getElementById("liste-panier");
  conteneur.innerHTML = "";

  if (panier.length === 0) {
    conteneur.innerHTML = "<div class='vide'>Panier vide -- retourne à l'accueil pour cocher des matchs.</div>";
  } else {
    panier.forEach((item, i) => {
      const div = document.createElement("div");
      div.className = "item-panier";

      const texte = document.createElement("span");
      const tagTexte = item.source === "manuel" ? "manuel" : "liste";
      texte.innerHTML = `${item.domicile} — ${item.exterieur}<span class="tag">${item.competition || "?"} · ${tagTexte}</span>`;

      const retirer = document.createElement("button");
      retirer.textContent = "✕";
      retirer.title = "Retirer du panier";
      retirer.addEventListener("click", () => {
        const p = chargePanier();
        p.splice(i, 1);
        sauvePanier(p);
        rafraichit();
      });

      div.appendChild(texte);
      div.appendChild(retirer);
      conteneur.appendChild(div);
    });
  }

  document.getElementById("tout-copier-btn").textContent = `Tout copier (${panier.length})`;
}

function copierPanier() {
  const panier = chargePanier();
  const items = panier.map((item) => ({
    match_id: item.match_id,
    domicile: item.domicile,
    exterieur: item.exterieur,
    competition: item.competition,
    url_match: item.url_match,
  }));
  const json = JSON.stringify(items, null, 2);
  const bouton = document.getElementById("tout-copier-btn");

  const confirmeVisuellement = () => {
    const texteOriginal = `Tout copier (${panier.length})`;
    bouton.textContent = "Copié ✓";
    bouton.classList.add("copie");
    setTimeout(() => {
      bouton.textContent = texteOriginal;
      bouton.classList.remove("copie");
    }, 1500);
  };

  if (navigator.clipboard) {
    navigator.clipboard.writeText(json).then(confirmeVisuellement).catch(() => {
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

document.getElementById("tout-copier-btn").addEventListener("click", copierPanier);

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
  const panier = chargePanier();
  if (!panier.some((p) => p.match_id === matchId)) {
    panier.push({ match_id: matchId, url_match: url, domicile, exterieur, competition, source: "manuel" });
    sauvePanier(panier);
  }
  rafraichit();

  document.getElementById("manuel-url").value = "";
  document.getElementById("manuel-domicile").value = "";
  document.getElementById("manuel-exterieur").value = "";
  document.getElementById("manuel-competition").value = "";
});

rafraichit();
