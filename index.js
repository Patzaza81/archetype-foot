// index.js — v6
// CORRECTIF 03/09/2026 -- suppression de l'onglet "semaine" et du bouton
// "Analyser" associé : code mort confirmé (index.html ne contient ni
// #onglet-semaine, ni #btn-analyser, ni #status-analyse -- tous les
// document.getElementById() correspondants renvoyaient déjà null en
// production). L'onglet "semaine" chargeait "catalogue_unifie.json", un
// fichier que plus aucun script de ce dépôt ne génère. Comportement des
// onglets "aujourd'hui" et "demain" strictement inchangé.

const CLE_PANIER = "archetype_panier";

const donnees = {
  aujourdhui: null,
  demain: null
};

let ongletActif = "aujourdhui";

function chargePanier() {
  try {
    const brut = localStorage.getItem(CLE_PANIER);
    if (!brut) return [];

    const panier = JSON.parse(brut);
    return Array.isArray(panier) ? panier : [];
  } catch (e) {
    console.error("Panier illisible, réinitialisé :", e);
    return [];
  }
}

function sauvePanier(liste) {
  localStorage.setItem(CLE_PANIER, JSON.stringify(liste));
}

function metAJourBoutonPanier() {
  const bouton = document.getElementById("nav-panier");
  if (!bouton) return;

  bouton.textContent = `🧺 Panier (${chargePanier().length})`;
}

function ajouterAuPanier(match) {
  if (!match || !match.match_id) return;

  const panier = chargePanier();

  const existe = panier.some(
    (m) => String(m.match_id) === String(match.match_id)
  );

  if (!existe) {
    panier.push({
      ...match,
      source: match.source || "liste"
    });

    sauvePanier(panier);
  }

  metAJourBoutonPanier();
}

function retirerDuPanier(matchId) {
  const panier = chargePanier().filter(
    (m) => String(m.match_id) !== String(matchId)
  );

  sauvePanier(panier);
  metAJourBoutonPanier();
}

function formatEnTete(jour, nbMatchs) {
  const labels = {
    aujourdhui: "aujourd'hui",
    demain: "demain"
  };

  return `${nbMatchs} match(s) disponible(s) ${labels[jour] || jour}`;
}

function afficheListe(jour) {
  const matchs = donnees[jour];

  const maj = document.getElementById("maj");
  const liste = document.getElementById("liste");

  if (maj) {
    maj.textContent = formatEnTete(
      jour,
      matchs ? matchs.length : 0
    );
  }

  if (!liste) return;

  liste.innerHTML = "";

  if (!matchs || matchs.length === 0) {
    liste.innerHTML = "<p>aucun match disponible.</p>";
    return;
  }

  const idsAuPanier = new Set(
    chargePanier().map((m) => String(m.match_id))
  );

  let competitionCourante = null;

  matchs.forEach((m) => {
    if (!m || !m.match_id) return;

    if (m.competition !== competitionCourante) {
      competitionCourante = m.competition;

      const entete = document.createElement("div");

      entete.className = "selection-competition";

      entete.textContent = (
        competitionCourante || "compétition inconnue"
      )
        .replace(/\s+/g, " ")
        .trim();

      liste.appendChild(entete);
    }

    const div = document.createElement("div");

    div.className = "selection-item";

    const input = document.createElement("input");

    input.type = "checkbox";
    input.id = "match-" + m.match_id;

    input.checked = idsAuPanier.has(
      String(m.match_id)
    );

    input.addEventListener("change", () => {
      if (input.checked) {
        ajouterAuPanier({
          ...m,
          source: "liste"
        });
      } else {
        retirerDuPanier(m.match_id);
      }
    });

    const heure = document.createElement("span");

    heure.className = "heure";

    // AJOUT (04/09/2026 soir) -- affiche l'heure Cameroun (Africa/Douala)
    // quand elle a pu être calculée (heure_cameroun, voir scraper.py),
    // repli sur m.heure brute (France) si absente -- statuts en direct
    // ("83'", "MT", "TER"...) n'ont jamais de heure_cameroun, donc
    // s'affichent toujours tels quels via ce repli, sans "(FR)" à côté.
    heure.textContent = m.heure_cameroun
      ? `${m.heure_cameroun} (heure Cameroun)`
      : (m.heure || "--:--");

    const label = document.createElement("label");

    label.htmlFor = input.id;

    label.textContent =
      `${m.domicile || "Équipe domicile"} — ` +
      `${m.exterieur || "Équipe extérieur"}` +
      (m.score ? ` (${m.score})` : "");

    div.appendChild(input);
    div.appendChild(heure);
    div.appendChild(label);

    liste.appendChild(div);
  });
}

function activeOnglet(jour) {
  ongletActif = jour;

  const ids = [
    ["onglet-aujourdhui", "aujourdhui"],
    ["onglet-demain", "demain"]
  ];

  ids.forEach(([id, valeur]) => {
    const element = document.getElementById(id);

    if (element) {
      element.classList.toggle(
        "actif",
        jour === valeur
      );
    }
  });

  afficheListe(jour);
}

function chargeJour(jour, fichier) {
  return fetch(
    fichier + "?_=" + Date.now()
  )
    .then((r) => {
      if (!r.ok) {
        throw new Error(
          `${fichier} introuvable (status ${r.status})`
        );
      }

      return r.json();
    })
    .then((data) => {
      donnees[jour] = Array.isArray(data)
        ? data
        : (
            data &&
            Array.isArray(data.matchs)
              ? data.matchs
              : []
          );
    })
    .catch((err) => {
      donnees[jour] = [];

      console.error(jour, err);
    });
}

Promise.all([
  chargeJour(
    "aujourdhui",
    "matchs_du_jour_filtre.json"
  ),

  chargeJour(
    "demain",
    "matchs_demain_filtre.json"
  )
]).then(() => {
  activeOnglet(ongletActif);
  metAJourBoutonPanier();
});

const boutonAujourdhui =
  document.getElementById(
    "onglet-aujourdhui"
  );

if (boutonAujourdhui) {
  boutonAujourdhui.addEventListener(
    "click",
    () => activeOnglet("aujourdhui")
  );
}

const boutonDemain =
  document.getElementById(
    "onglet-demain"
  );

if (boutonDemain) {
  boutonDemain.addEventListener(
    "click",
    () => activeOnglet("demain")
  );
}

window.addEventListener(
  "storage",
  (event) => {

    if (
      event.key ===
      CLE_PANIER
    ) {
      metAJourBoutonPanier();

      if (
        donnees[ongletActif]
      ) {
        afficheListe(
          ongletActif
        );
      }
    }
  }
);
