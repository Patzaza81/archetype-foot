// index.js — v5
// Correction du panier : les matchs sélectionnés dans l'onglet "7 jours"
// sont maintenant enregistrés dans localStorage.
// Le fonctionnement existant des onglets et du bouton "Analyser" est conservé.

const CLE_PANIER = "archetype_panier";

const donnees = {
  aujourdhui: null,
  demain: null,
  semaine: null
};

let ongletActif = "aujourdhui";
let selectionCourante = null;

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
    demain: "demain",
    semaine: "7 prochains jours"
  };

  return `${nbMatchs} match(s) disponible(s) ${labels[jour] || jour}`;
}

function afficheListe(jour) {
  const matchs = donnees[jour];

  const maj = document.getElementById("maj");
  const liste = document.getElementById("liste");
  const boutonAnalyser = document.getElementById("btn-analyser");

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

    if (boutonAnalyser) {
      boutonAnalyser.classList.remove("visible");
    }

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

        selectionCourante = m;

        if (
          jour === "semaine" &&
          boutonAnalyser
        ) {
          boutonAnalyser.classList.add("visible");
        }

      } else {
        retirerDuPanier(m.match_id);

        if (
          selectionCourante &&
          String(selectionCourante.match_id) ===
            String(m.match_id)
        ) {
          selectionCourante = null;
        }

        if (
          jour === "semaine" &&
          boutonAnalyser
        ) {
          const aUneSelection = matchs.some(
            (match) =>
              chargePanier().some(
                (p) =>
                  String(p.match_id) ===
                  String(match.match_id)
              )
          );

          boutonAnalyser.classList.toggle(
            "visible",
            aUneSelection
          );
        }
      }
    });

    const heure = document.createElement("span");

    heure.className = "heure";

    heure.textContent = m.heure || "--:--";

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

  if (boutonAnalyser) {
    if (jour !== "semaine") {
      boutonAnalyser.classList.remove("visible");

    } else {
      const aUneSelection = matchs.some(
        (match) =>
          chargePanier().some(
            (p) =>
              String(p.match_id) ===
              String(match.match_id)
          )
      );

      boutonAnalyser.classList.toggle(
        "visible",
        aUneSelection
      );
    }
  }
}

function activeOnglet(jour) {
  ongletActif = jour;

  const ids = [
    ["onglet-aujourdhui", "aujourdhui"],
    ["onglet-demain", "demain"],
    ["onglet-semaine", "semaine"]
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
  ),

  chargeJour(
    "semaine",
    "catalogue_unifie.json"
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

const boutonSemaine =
  document.getElementById(
    "onglet-semaine"
  );

if (boutonSemaine) {
  boutonSemaine.addEventListener(
    "click",
    () => activeOnglet("semaine")
  );
}

const boutonAnalyser =
  document.getElementById(
    "btn-analyser"
  );

if (boutonAnalyser) {
  boutonAnalyser.addEventListener(
    "click",
    async () => {

      if (!selectionCourante) {
        const panier = chargePanier();

        if (panier.length > 0) {
          selectionCourante =
            panier[panier.length - 1];
        }
      }

      if (!selectionCourante) return;

      const status =
        document.getElementById(
          "status-analyse"
        );

      boutonAnalyser.disabled = true;

      if (status) {
        status.textContent =
          "Envoi au pipeline…";

        status.style.color = "";
      }

      const payload = {
        equipe_dom:
          selectionCourante.domicile,

        equipe_ext:
          selectionCourante.exterieur,

        date:
          selectionCourante.date,

        heure:
          selectionCourante.heure ||
          "00:00",

        url_matchendirect:
          selectionCourante.url_matchendirect ||
          selectionCourante.url_match ||
          null
      };

      try {
        const res = await fetch(
          "/.netlify/functions/trigger",
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body: JSON.stringify(
              payload
            )
          }
        );

        let data = {};

        try {
          data = await res.json();
        } catch (e) {
          data = {};
        }

        if (
          res.ok &&
          data.ok
        ) {
          if (status) {
            status.textContent =
              "✅ Analyse lancée. Résultat dans ~2 min.";

            status.style.color =
              "#14b8a6";
          }

        } else {
          if (status) {
            status.textContent =
              "❌ " +
              (
                data.error ||
                "Erreur serveur"
              );

            status.style.color =
              "#ef4444";
          }
        }

      } catch (e) {
        console.error(
          "Erreur trigger :",
          e
        );

        if (status) {
          status.textContent =
            "❌ Impossible de joindre le serveur";

          status.style.color =
            "#ef4444";
        }

      } finally {
        boutonAnalyser.disabled =
          false;
      }
    }
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
