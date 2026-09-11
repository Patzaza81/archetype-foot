// archetype.js — affichage public des sélections Archetype.
//
// RESPONSABILITÉ UNIQUE : présenter proprement les résultats déjà produits
// par archetype_model. Ce fichier ne calcule aucune probabilité, ne choisit
// aucun marché, ne modifie aucun rang et n'applique aucun filtre métier.
// Il transforme uniquement les données reçues en une interface lisible.
//
// HIÉRARCHIE D'AFFICHAGE :
// 1. match et contexte ;
// 2. trois sélections lorsqu'elles existent ;
// 3. marché en français ;
// 4. cote et probabilité déjà produites par le moteur ;
// 5. niveau de confiance déjà produit par le moteur ;
// 6. justification historique déjà produite par le moteur ;
// 7. métriques secondaires ;
// 8. détails techniques uniquement sur demande.

function estArchetypeGo(m) {
  return m
    && m.moteur_utilise === "archetype_model"
    && m.archetype_model
    && m.archetype_model.statut === "OK"
    && !!(m.archetype_model.selection && m.archetype_model.selection.P1);
}

function echappeHtml(texte) {
  if (texte === null || texte === undefined) return "";

  return String(texte)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatPct(x) {
  if (
    x === null ||
    x === undefined ||
    !Number.isFinite(Number(x))
  ) {
    return "—";
  }

  const valeur = Number(x) * 100;

  return `${valeur.toFixed(1).replace(".", ",")} %`;
}

function formatPctEntier(x) {
  if (
    x === null ||
    x === undefined ||
    !Number.isFinite(Number(x))
  ) {
    return "—";
  }

  return `${Math.round(Number(x) * 100)} %`;
}

function formatCote(cote) {
  if (
    cote === null ||
    cote === undefined ||
    !Number.isFinite(Number(cote))
  ) {
    return "—";
  }

  return Number(cote)
    .toFixed(2)
    .replace(".", ",");
}

function formatDate(dateIso) {
  if (!dateIso) return "";

  const d = new Date(`${dateIso}T12:00:00`);

  if (Number.isNaN(d.getTime())) {
    return dateIso;
  }

  return d
    .toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    })
    .replace(".", "");
}

function initialesEquipe(nom) {
  const propre = String(nom || "?").trim();

  if (!propre) return "?";

  const morceaux = propre
    .split(/\s+/)
    .filter(Boolean);

  if (morceaux.length === 1) {
    return morceaux[0]
      .slice(0, 2)
      .toUpperCase();
  }

  return (
    morceaux[0][0] +
    morceaux[morceaux.length - 1][0]
  ).toUpperCase();
}

const RANGS = [
  {
    cle: "P1",
    classe: "rang-1",
    icone: "♛",
    pastille: "Le meilleur choix",
    sousTitre: "Pronostic principal",
  },

  {
    cle: "P2",
    classe: "rang-2",
    icone: "◆",
    pastille: "Meilleure rentabilité",
    sousTitre: "Deuxième choix",
  },

  {
    cle: "P3",
    classe: "rang-3",
    icone: "+",
    pastille: "Pronostic bonus",
    sousTitre: "Troisième choix",
  },
];

function construitPhraseConfirmation(
  marche,
  confirmation,
  equipes
) {
  if (
    !confirmation ||
    !confirmation.nb_echantillon
  ) {
    return null;
  }

  const nbConfirmant =
    Number(confirmation.nb_confirmant);

  const nbEchantillon =
    Number(confirmation.nb_echantillon);

  if (
    !Number.isFinite(nbConfirmant) ||
    !Number.isFinite(nbEchantillon) ||
    nbEchantillon <= 0
  ) {
    return null;
  }

  const pct = Math.round(
    (nbConfirmant / nbEchantillon) * 100
  );

  const dom =
    equipes.domicile ||
    "L'équipe à domicile";

  const ext =
    equipes.exterieur ||
    "L'équipe à l'extérieur";

  let sujet = "Les deux équipes";
  let verbe = "confirment";
  let possessif = "leurs";

  if (
    marche === "1x2_domicile" ||
    marche === "double_chance_1X" ||
    /^buts_equipe_domicile_|^cage_inviolee_domicile$|^encaisse_domicile$|^handicap_domicile_/.test(
      marche
    )
  ) {
    sujet = dom;
    verbe = "confirme";
    possessif = "ses";
  } else if (
    marche === "1x2_exterieur" ||
    marche === "double_chance_X2" ||
    /^buts_equipe_exterieur_|^cage_inviolee_exterieur$|^encaisse_exterieur$|^handicap_exterieur_/.test(
      marche
    )
  ) {
    sujet = ext;
    verbe = "confirme";
    possessif = "ses";
  }

  return `${sujet} ${verbe} cette tendance sur ${nbConfirmant} de ${possessif} ${nbEchantillon} derniers matchs comparables (${pct} %).`;
}

function construitPourquoi(
  candidat,
  equipes
) {
  const phrases = [];

  const phraseHistorique =
    construitPhraseConfirmation(
      candidat.marche,
      candidat.confirmation_historique,
      equipes
    );

  if (phraseHistorique) {
    phrases.push(phraseHistorique);
  }

  const h2h =
    traduitPalierH2H(
      candidat.h2h_palier
    );

  if (h2h) {
    phrases.push(`${h2h}.`);
  }

  if (phrases.length > 0) {
    return phrases.join(" ");
  }

  const niveau =
    traduitNiveau(candidat.niveau);

  return `Le modèle statistique classe ce pronostic parmi ses sélections ${niveau.texte.toLowerCase()}.`;
}

function construitJauge(
  probabilite,
  classe
) {
  const connue =
    probabilite !== null &&
    probabilite !== undefined &&
    Number.isFinite(Number(probabilite));

  if (!connue) {
    return `
      <div class="probabilite-indisponible">
        <span>Probabilité</span>
        <strong>—</strong>
      </div>
    `;
  }

  const valeur =
    Math.max(
      0,
      Math.min(
        1,
        Number(probabilite)
      )
    );

  const pourcentage =
    Math.round(valeur * 100);

  const rayon = 30;

  const circonference =
    2 * Math.PI * rayon;

  const progression =
    circonference * (1 - valeur);

  return `
    <div
      class="jauge-probabilite ${classe}"
      aria-label="Probabilité estimée ${pourcentage} %"
    >
      <svg
        viewBox="0 0 76 76"
        aria-hidden="true"
      >
        <circle
          class="fond-anneau"
          cx="38"
          cy="38"
          r="${rayon}"
        ></circle>

        <circle
          class="valeur-anneau"
          cx="38"
          cy="38"
          r="${rayon}"
          stroke-dasharray="${circonference.toFixed(2)}"
          stroke-dashoffset="${progression.toFixed(2)}"
        ></circle>
      </svg>

      <strong>${pourcentage}%</strong>
    </div>
  `;
}

function construitBlocCandidat(
  rangInfo,
  candidat,
  equipes
) {
  const div =
    document.createElement("article");

  if (!candidat) {
    div.className =
      `carte-pronostic ${rangInfo.classe} vide`;

    div.innerHTML = `
      <div class="entete-rang">
        <span
          class="icone-rang"
          aria-hidden="true"
        >${rangInfo.icone}</span>

        <div>
          <div class="pastille-rang">
            ${echappeHtml(rangInfo.pastille)}
          </div>

          <div class="sous-titre-rang">
            ${echappeHtml(rangInfo.sousTitre)}
          </div>
        </div>
      </div>

      <p class="absence-selection">
        Aucun pronostic n'a passé tous les critères
        du modèle pour ce rang.
      </p>
    `;

    return div;
  }

  div.className =
    `carte-pronostic ${rangInfo.classe}`;

  const libelle =
    traduitMarche(
      candidat.marche,
      equipes
    );

  const confiance =
    traduitNiveau(candidat.niveau);

  const etoiles =
    "★".repeat(confiance.etoiles) +
    `<span class="vide">${
      "★".repeat(5 - confiance.etoiles)
    }</span>`;

  const pourquoi =
    construitPourquoi(
      candidat,
      equipes
    );

  div.innerHTML = `
    <div class="entete-rang">

      <span
        class="icone-rang"
        aria-hidden="true"
      >${rangInfo.icone}</span>

      <div>
        <div class="pastille-rang">
          ${echappeHtml(rangInfo.pastille)}
        </div>

        <div class="sous-titre-rang">
          ${echappeHtml(rangInfo.sousTitre)}
        </div>
      </div>

    </div>

    <h2 class="libelle-marche">
      ${echappeHtml(libelle)}
    </h2>

    <div class="bloc-principal-resultat">

      <div class="bloc-cote">
        <span class="etiquette">Cote</span>

        <strong class="valeur-cote">
          ${formatCote(candidat.cote)}
        </strong>
      </div>

      ${construitJauge(
        candidat.probabilite,
        rangInfo.classe
      )}

      <div class="bloc-proba-texte">

        <span class="etiquette">
          Chances de réussite
        </span>

        <strong>
          ${
            candidat.probabilite !== null &&
            candidat.probabilite !== undefined
              ? formatPctEntier(
                  candidat.probabilite
                )
              : "Non communiquée"
          }
        </strong>

        <small>
          estimées par le modèle
        </small>

      </div>

    </div>

    <div class="ligne-confiance">

      <span
        class="etoiles"
        aria-label="${confiance.etoiles} étoiles sur 5"
      >
        ${etoiles}
      </span>

      <span>
        <strong>Confiance</strong>
        ·
        ${echappeHtml(confiance.texte)}
      </span>

    </div>

    <div class="bloc-pourquoi">

      <div class="titre">
        Pourquoi ce choix ?
      </div>

      <p class="texte">
        ${echappeHtml(pourquoi)}
      </p>

    </div>

    <div class="metriques-secondaires">

      <div class="metrique">

        <span class="etiquette">
          Avantage potentiel
        </span>

        <strong class="valeur">
          ${formatPct(candidat.edge)}
        </strong>

      </div>

      <div class="metrique">

        <span class="etiquette">
          Gain potentiel
        </span>

        <strong class="valeur">
          ${formatPct(candidat.edv)}
        </strong>

      </div>

    </div>
  `;

  return div;
}

function construitDetails(m) {
  const details =
    document.createElement("details");

  details.className =
    "details-analyse";

  const selection =
    (
      m.archetype_model &&
      m.archetype_model.selection
    ) || {};

  const lignes = [];

  RANGS.forEach((rang) => {
    const candidat =
      selection[rang.cle];

    if (!candidat) return;

    lignes.push(`
      <div class="ligne-detail">
        <span class="cle">
          Marché technique
        </span>

        <span class="val">
          ${echappeHtml(
            candidat.marche || "—"
          )}
        </span>
      </div>
    `);

    lignes.push(`
      <div class="ligne-detail">
        <span class="cle">
          Niveau produit par le modèle
        </span>

        <span class="val">
          ${echappeHtml(
            candidat.niveau || "—"
          )}
        </span>
      </div>
    `);

    lignes.push(`
      <div class="ligne-detail">
        <span class="cle">
          Stabilité
        </span>

        <span class="val">
          ${echappeHtml(
            candidat.robustesse || "—"
          )}
        </span>
      </div>
    `);

    lignes.push(`
      <div class="ligne-detail">
        <span class="cle">
          Historique direct
        </span>

        <span class="val">
          ${echappeHtml(
            candidat.h2h_palier || "—"
          )}
        </span>
      </div>
    `);
  });

  details.innerHTML = `
    <summary>

      <span>
        <strong>
          Détails de l'analyse
        </strong>

        <small>
          Éléments techniques ayant accompagné la sélection
        </small>
      </span>

      <span
        class="chevron"
        aria-hidden="true"
      >⌄</span>

    </summary>

    <div class="contenu-details">

      ${
        lignes.join("") ||
        '<p class="detail-vide">Aucun détail technique disponible.</p>'
      }

    </div>
  `;

  return details;
}

function construitCarte(m) {
  const conteneur =
    document.createElement("section");

  conteneur.className =
    "carte-match";

  const equipes = {
    domicile:
      m.domicile ||
      "Équipe à domicile",

    exterieur:
      m.exterieur ||
      "Équipe à l'extérieur",
  };

  const heure =
    m.heure_cameroun ||
    m.heure ||
    "—";

  const date =
    formatDate(m.date);

  const competition =
    (m.competition || "")
      .replace(/\s+/g, " ")
      .trim();

  const entete =
    document.createElement("header");

  entete.className =
    "entete-match";

  entete.innerHTML = `
    <div class="match-equipes">

      <div class="bloc-equipe domicile">

        <div class="ecusson-equipe">
          ${echappeHtml(
            initialesEquipe(
              equipes.domicile
            )
          )}
        </div>

        <div class="nom-equipe">
          ${echappeHtml(
            equipes.domicile
          )}
        </div>

      </div>

      <div class="bloc-horaire">

        <strong>
          ${echappeHtml(heure)}
        </strong>

        <span>
          ${echappeHtml(date)}
        </span>

      </div>

      <div class="bloc-equipe exterieur">

        <div class="nom-equipe">
          ${echappeHtml(
            equipes.exterieur
          )}
        </div>

        <div class="ecusson-equipe">
          ${echappeHtml(
            initialesEquipe(
              equipes.exterieur
            )
          )}
        </div>

      </div>

    </div>

    ${
      competition
        ? `
          <div class="info-competition">
            <span
              class="point-pays"
              aria-hidden="true"
            ></span>

            ${echappeHtml(
              competition
            )}
          </div>
        `
        : ""
    }
  `;

  conteneur.appendChild(entete);

  const selection =
    (
      m.archetype_model &&
      m.archetype_model.selection
    ) || {};

  RANGS.forEach((rangInfo) => {
    conteneur.appendChild(
      construitBlocCandidat(
        rangInfo,
        selection[rangInfo.cle],
        equipes
      )
    );
  });

  conteneur.appendChild(
    construitDetails(m)
  );

  return conteneur;
}

function afficheSelections(matchs) {
  const container =
    document.getElementById("matches");

  const maj =
    document.getElementById("maj");

  container.innerHTML = "";

  const retenus =
    (matchs || [])
      .filter(estArchetypeGo);

  retenus.sort((a, b) => {
    const cleA =
      `${a.date || ""}${
        a.heure_cameroun ||
        a.heure ||
        ""
      }`;

    const cleB =
      `${b.date || ""}${
        b.heure_cameroun ||
        b.heure ||
        ""
      }`;

    return cleA.localeCompare(cleB);
  });

  maj.innerHTML =
    retenus.length
      ? `
        <span
          class="point-live"
          aria-hidden="true"
        ></span>

        <strong>
          ${retenus.length}
        </strong>

        match${
          retenus.length > 1
            ? "s"
            : ""
        }

        analysé${
          retenus.length > 1
            ? "s"
            : ""
        }

        aujourd'hui
      `
      : "Aucune sélection pour le moment";

  if (retenus.length === 0) {
    container.innerHTML = `
      <div class="etat-vide">

        <strong>
          Aucune sélection pour le moment
        </strong>

        <p>
          Aucun match ne remplit actuellement
          tous les critères du modèle.
          Ce n'est pas une erreur :
          le modèle préfère ne rien proposer
          plutôt que de proposer un pari
          insuffisamment étayé.
        </p>

      </div>
    `;

    return;
  }

  retenus.forEach((m) => {
    container.appendChild(
      construitCarte(m)
    );
  });
}

fetch(
  "precalcul_leger.json?_=" +
  Date.now()
)
  .then((r) => {
    if (!r.ok) {
      throw new Error(
        `precalcul_leger.json introuvable (status ${r.status})`
      );
    }

    return r.json();
  })

  .then((data) => {
    afficheSelections(
      data.signaux || []
    );
  })

  .catch((err) => {
    document.getElementById(
      "maj"
    ).textContent =
      "Erreur de chargement : " +
      err.message;

    console.error(err);
  });
