// panier.js — RÉÉCRIT le 13/09/2026, décision de Patrick.
//
// Ancienne fonction (supprimée) : envoyer le panier à Supabase, déclencher
// une analyse GitHub Actions (dispatch_pipeline.py -> run_pipeline.py,
// avec option de cotes manuelles). Patrick n'utilise plus la saisie
// manuelle de cotes -- cette fonction n'a plus de raison d'être.
//
// Nouvelle fonction : le panier est une liste de matchs qu'on choisit sur
// la page d'accueil (mécanisme inchangé, voir index.js -- CLE_PANIER
// partagée, ne JAMAIS diverger). Cette page se contente d'aller chercher,
// pour chaque match du panier, sa sélection archetype_model DÉJÀ CALCULÉE
// dans precalcul_leger.json -- aucun run, aucune attente, aucun réseau
// externe (Supabase retiré entièrement).
//
// Réutilise construitCarte()/afficheSelections()/estArchetypeGo()/
// echappeHtml() d'archetype.js (inclus juste avant ce script dans
// panier.html, avec traduction_marches.js dont il dépend) -- jamais
// dupliqués ici, pour ne jamais diverger visuellement de la page
// Archetype. Le conteneur de cette page s'appelle "panier-cartes", PAS
// "matches", précisément pour ne jamais déclencher l'auto-chargement
// intégré à archetype.js (voir le garde-fou ajouté dans ce fichier).

const CLE_PANIER = "archetype_panier"; // identique à index.js -- ne jamais diverger

function chargePanier() {
  try {
    const brut = localStorage.getItem(CLE_PANIER);
    if (!brut) return [];
    const panier = JSON.parse(brut);
    return Array.isArray(panier) ? panier : [];
  } catch {
    return [];
  }
}

function sauvePanier(liste) {
  localStorage.setItem(CLE_PANIER, JSON.stringify(liste));
}

function retirerDuPanier(matchId) {
  const panier = chargePanier().filter(
    (m) => String(m.match_id) !== String(matchId)
  );
  sauvePanier(panier);
  affichePanier();
}

function construitCartePanier(item, signal) {
  const conteneur = document.createElement("div");
  conteneur.className = "carte-panier";

  const barre = document.createElement("div");
  barre.className = "barre-panier";
  const boutonRetirer = document.createElement("button");
  boutonRetirer.className = "bouton-retirer-panier";
  boutonRetirer.textContent = "Retirer du panier";
  boutonRetirer.addEventListener("click", () => retirerDuPanier(item.match_id));
  barre.appendChild(boutonRetirer);
  conteneur.appendChild(barre);

  if (signal && estArchetypeGo(signal)) {
    conteneur.appendChild(construitCarte(signal));
  } else {
    const vide = document.createElement("div");
    vide.className = "etat-vide";
    vide.innerHTML = `<strong>${echappeHtml(item.domicile || "Équipe à domicile")} – ${echappeHtml(item.exterieur || "Équipe à l'extérieur")}</strong><p>Aucune sélection Archetype pour ce match pour l'instant.</p>`;
    conteneur.appendChild(vide);
  }
  return conteneur;
}

function affichePanier() {
  const root = document.getElementById("panier-cartes");
  const statut = document.getElementById("statut-panier");
  const panier = chargePanier();

  if (!panier.length) {
    statut.textContent = "Ton panier est vide.";
    root.innerHTML = "";
    return;
  }

  statut.textContent = "Chargement…";

  fetch(`precalcul_leger.json?_=${Date.now()}`)
    .then((r) => {
      if (!r.ok) throw new Error(`precalcul_leger.json introuvable (${r.status})`);
      return r.json();
    })
    .then((d) => {
      const signaux = d.signaux || [];
      const parId = new Map(signaux.map((s) => [String(s.match_id), s]));
      root.innerHTML = "";
      let nbAvecSelection = 0;

      panier.forEach((item) => {
        const signal = parId.get(String(item.match_id));
        if (signal && estArchetypeGo(signal)) nbAvecSelection++;
        root.appendChild(construitCartePanier(item, signal));
      });

      statut.textContent = `${panier.length} match${panier.length > 1 ? "s" : ""} dans le panier — ${nbAvecSelection} avec une sélection Archetype.`;
    })
    .catch((e) => {
      statut.textContent = "Erreur de chargement : " + e.message;
      console.error(e);
    });
}

affichePanier();
