// index.js — page d'accueil. Parcourir + cocher (ancien système, inchangé)
// + bouton "Analyser" par match (nouveau, appelle trigger.js directement).

const CLE_PANIER = "archetype_panier";
const donnees = { aujourdhui: null, demain: null };
let ongletActif = "aujourdhui";

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

function formatEnTete(jour, nbMatchs) {
  return jour === "aujourdhui"
    ? `${nbMatchs} match(s) disponible(s) aujourd'hui`
    : `${nbMatchs} match(s) disponible(s) demain`;
}

// Envoie ce match précis à GitHub Actions via trigger.js. Utilise les
// vraies date/heure du match (pas de valeur codée en dur) -- si l'une des
// deux manque dans les données scrapées, on prévient au lieu de deviner.
async function analyserMatch(m, boutonEl, statutEl) {
  if (!m.date || !m.heure) {
    statutEl.textContent = "❌ Date ou heure manquante pour ce match -- impossible d'analyser.";
    statutEl.className = "statut-analyse erreur";
    return;
  }

  boutonEl.disabled = true;
  statutEl.textContent = "Envoi au pipeline…";
  statutEl.className = "statut-analyse";

  const payload = {
    equipe_dom: m.domicile,
    equipe_ext: m.exterieur,
    date: m.date,
    heure: m.heure,
    url_matchendirect: m.url_match || null,
  };

  try {
    const res = await fetch("/.netlify/functions/trigger", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.ok && data.ok) {
      statutEl.textContent = "✅ Analyse lancée. Résultat dans quelques minutes sur \"Voir les pronostics\".";
      statutEl.className = "statut-analyse ok";
    } else {
      statutEl.textContent = "❌ " + (data.error || "Erreur serveur");
      statutEl.className = "statut-analyse erreur";
    }
  } catch (e) {
    statutEl.textContent = "❌ Impossible de joindre le serveur.";
    statutEl.className = "statut-analyse erreur";
  } finally {
    boutonEl.disabled = false;
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

  const panierActuel = chargePanier();
  const idsAuPanier = new Set(panierActuel.map((m) => m.match_id));

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
    checkbox.checked = idsAuPanier.has(m.match_id);
    checkbox.addEventListener("change", () => {
      const panier = chargePanier();
      const idx = panier.findIndex((p) => p.match_id === m.match_id);
      if (checkbox.checked) {
        if (idx === -1) panier.push({ ...m, source: "liste" });
      } else {
        if (idx !== -1) panier.splice(idx, 1);
      }
      sauvePanier(panier);
      metAJourBoutonPanier();
    });

    const heure = document.createElement("span");
    heure.className = "heure";
    heure.textContent = m.heure || "--:--";

    const label = document.createElement("label");
    label.htmlFor = checkbox.id;
    label.textContent = `${m.domicile} — ${m.exterieur}` + (m.score ? ` (${m.score})` : "");

    const btnAnalyser = document.createElement("button");
    btnAnalyser.className = "btn-analyser";
    btnAnalyser.textContent = "🔬 Analyser";

    const statut = document.createElement("div");
    statut.className = "statut-analyse";

    btnAnalyser.addEventListener("click", () => analyserMatch(m, btnAnalyser, statut));

    div.appendChild(checkbox);
    div.appendChild(heure);
    div.appendChild(label);
    div.appendChild(btnAnalyser);
    div.appendChild(statut);
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
  metAJourBoutonPanier();
});

document.getElementById("onglet-aujourdhui").addEventListener("click", () => activeOnglet("aujourdhui"));
document.getElementById("onglet-demain").addEventListener("click", () => activeOnglet("demain"));
