// archetype.js — révisé le 10/09/2026 à la demande de Patrick : la carte
// précédente affichait une ligne technique brute ("over_under_total_3.5_under
// (niveau PREMIUM, edge 12.4%, edv 16.0%, H2H FIABLE)"), illisible pour un
// parieur. Nouvelle hiérarchie : PRONOSTIC > COTE > PROBABILITÉ > CONFIANCE >
// POURQUOI > métriques secondaires. Voir traduction_marches.js pour la
// traduction pure clé-technique -> texte, chargé avant ce fichier.
//
// RÈGLE INCHANGÉE (déjà en vigueur, réaffirmée explicitement par Patrick le
// 10/09/2026) : ce fichier ne recalcule rien, ne choisit pas les rangs, ne
// vérifie aucun filtre, ne fabrique aucune statistique. Il affiche
// uniquement ce qu'archetype_model a déjà décidé.

function estArchetypeGo(m) {
  return m.moteur_utilise === "archetype_model"
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

function formatPctSur(x) {
  if (x === null || x === undefined) return "?";
  const pct = x * 100;
  if (pct >= 99.95 && x < 1) return "99.9%";
  return pct.toFixed(1).replace(".", ",") + "%";
}

function formatPctEntier(x) {
  if (x === null || x === undefined) return "?";
  return Math.round(x * 100) + " %";
}

function formatCote(cote) {
  if (cote === null || cote === undefined) return "?";
  return cote.toFixed(2).replace(".", ",");
}

const RANGS = [
  { cle: "P1", classe: "rang-1", pastille: "Le meilleur choix", sousTitre: "Pronostic principal" },
  { cle: "P2", classe: "rang-2", pastille: "Meilleure rentabilité", sousTitre: "Deuxième choix" },
  { cle: "P3", classe: "rang-3", pastille: "Pronostic bonus", sousTitre: "Troisième choix" },
];

/** Construit la phrase "Pourquoi ?". Priorité à la phrase chiffrée et
 * réelle (construitPhraseConfirmation, basée sur un vrai comptage de
 * matchs passés) ; repli sur une phrase générique UNIQUEMENT si ce
 * comptage n'est pas disponible pour ce marché (jamais un chiffre
 * inventé pour combler l'absence). */
function construitPourquoi(candidat, equipes) {
  const phrases = [];
  const phraseChiffree = construitPhraseConfirmation(candidat.marche, candidat.confirmation_historique, equipes);
  if (phraseChiffree) {
    phrases.push(phraseChiffree);
  } else {
    const { texte: texteConfiance } = traduitNiveau(candidat.niveau);
    phrases.push(`Le modèle statistique juge ce pronostic avec une confiance ${texteConfiance.toLowerCase()}.`);
  }
  const phraseH2H = traduitPalierH2H(candidat.h2h_palier);
  if (phraseH2H) phrases.push(phraseH2H + ".");
  return phrases.join(" ");
}

function construitBlocCandidat(rangInfo, candidat, equipes) {
  const div = document.createElement("div");
  if (!candidat) {
    div.className = "carte-pronostic vide";
    div.innerHTML = `<span class="pastille-rang" style="opacity:.5">${echappeHtml(rangInfo.pastille)}</span><p style="margin-top:10px">Aucun pronostic n'a passé tous les critères du modèle pour ce rang.</p>`;
    return div;
  }

  div.className = `carte-pronostic ${rangInfo.classe}`;
  const libelle = traduitMarche(candidat.marche, equipes);
  const { etoiles, texte: texteConfiance } = traduitNiveau(candidat.niveau);
  const etoilesHtml = "★".repeat(etoiles) + `<span class="vide">${"★".repeat(5 - etoiles)}</span>`;
  const pct = candidat.edge !== null && candidat.edge !== undefined
    ? null // edge n'est pas la probabilité -- ne pas confondre les deux dans la jauge
    : null;
  // La probabilité affichée dans la jauge est la probabilité du modèle,
  // pas l'edge ni l'EDV -- si le champ n'est pas exposé par le moteur sur
  // ce candidat, on masque la jauge plutôt que d'afficher un faux chiffre.
  const probaModele = candidat.probabilite;
  const probaConnue = probaModele !== null && probaModele !== undefined;
  const pctEntier = probaConnue ? Math.round(probaModele * 100) : null;

  div.innerHTML = `
    <div class="entete-rang">
      <span class="pastille-rang">${echappeHtml(rangInfo.pastille)}</span>
      <span class="sous-titre-rang">${echappeHtml(rangInfo.sousTitre)}</span>
    </div>
    <div class="libelle-marche">${echappeHtml(libelle)}</div>
    <div class="ligne-cote-proba">
      <div class="bloc-cote">
        <div class="etiquette">COTE</div>
        <div class="valeur-cote">${formatCote(candidat.cote)}</div>
      </div>
      ${probaConnue ? `
      <div class="jauge-probabilite">
        <svg width="68" height="68" viewBox="0 0 68 68">
          <circle class="fond-anneau" cx="34" cy="34" r="28"></circle>
          <circle class="valeur-anneau" cx="34" cy="34" r="28"
            stroke-dasharray="${(2 * Math.PI * 28).toFixed(1)}"
            stroke-dashoffset="${(2 * Math.PI * 28 * (1 - pctEntier / 100)).toFixed(1)}"></circle>
        </svg>
        <div class="texte-anneau">${pctEntier}%</div>
      </div>
      <div class="bloc-proba-texte">
        <div class="etiquette">CHANCES DE RÉUSSITE ESTIMÉES</div>
      </div>` : `<div class="bloc-proba-texte"><div class="etiquette">Probabilité non communiquée pour ce marché</div></div>`}
    </div>
    <div class="ligne-confiance">
      <span class="etoiles">${etoilesHtml}</span>
      <span class="texte-confiance">Confiance ${texteConfiance.toLowerCase()}</span>
    </div>
    <div class="bloc-pourquoi">
      <div class="titre">Pourquoi ce choix ?</div>
      <div class="texte">${echappeHtml(construitPourquoi(candidat, equipes))}</div>
    </div>
    <div class="metriques-secondaires">
      <div class="metrique">
        <div class="etiquette">AVANTAGE ESTIMÉ</div>
        <div class="valeur">+${formatPctSur(candidat.edge)}</div>
      </div>
      <div class="metrique">
        <div class="etiquette">GAIN POTENTIEL</div>
        <div class="valeur">+${formatPctSur(candidat.edv)}</div>
      </div>
    </div>
  `;
  return div;
}

function construitDetails(m) {
  const details = document.createElement("details");
  details.className = "details-analyse";
  const selection = m.archetype_model.selection || {};
  const lignes = [];
  ["P1", "P2", "P3"].forEach((cle) => {
    const c = selection[cle];
    if (!c) return;
    lignes.push(`<div class="ligne-detail"><span class="cle">${cle} — marché technique</span><span class="val">${echappeHtml(c.marche)}</span></div>`);
    lignes.push(`<div class="ligne-detail"><span class="cle">${cle} — niveau</span><span class="val">${echappeHtml(c.niveau || "?")}</span></div>`);
    lignes.push(`<div class="ligne-detail"><span class="cle">${cle} — stabilité</span><span class="val">${echappeHtml(c.robustesse || "?")}</span></div>`);
    lignes.push(`<div class="ligne-detail"><span class="cle">${cle} — historique direct</span><span class="val">${echappeHtml(c.h2h_palier || "?")}</span></div>`);
  });
  details.innerHTML = `
    <summary>Détails techniques de l'analyse</summary>
    <div class="contenu-details">${lignes.join("")}</div>
  `;
  return details;
}

function construitCarte(m) {
  const conteneur = document.createElement("div");
  conteneur.className = "carte-match";

  const equipes = { domicile: m.domicile, exterieur: m.exterieur };
  const heureAffichee = m.heure_cameroun || m.heure || "";
  const competition = (m.competition || "").replace(/\s+/g, " ").trim();

  const entete = document.createElement("div");
  entete.className = "entete-match";
  entete.innerHTML = `
    <div class="equipes">
      <div class="nom-equipe domicile">${echappeHtml(m.domicile)}</div>
      <div class="heure-match">${echappeHtml(heureAffichee)}${m.date ? "<br>" + echappeHtml(m.date) : ""}</div>
      <div class="nom-equipe exterieur">${echappeHtml(m.exterieur)}</div>
    </div>
    ${competition ? `<div class="info-competition">${echappeHtml(competition)}</div>` : ""}
  `;
  conteneur.appendChild(entete);

  const selection = m.archetype_model.selection || {};
  RANGS.forEach((rangInfo) => {
    conteneur.appendChild(construitBlocCandidat(rangInfo, selection[rangInfo.cle], equipes));
  });

  conteneur.appendChild(construitDetails(m));

  return conteneur;
}

function afficheSelections(matchs) {
  const container = document.getElementById("matches");
  const maj = document.getElementById("maj");
  container.innerHTML = "";

  const retenus = (matchs || []).filter(estArchetypeGo);
  retenus.sort((a, b) => {
    const cleA = (a.date || "") + (a.heure_cameroun || a.heure || "");
    const cleB = (b.date || "") + (b.heure_cameroun || b.heure || "");
    return cleA.localeCompare(cleB);
  });

  maj.textContent = retenus.length
    ? `${retenus.length} match${retenus.length > 1 ? "s" : ""} analysé${retenus.length > 1 ? "s" : ""} aujourd'hui`
    : "Aucune sélection pour le moment";

  if (retenus.length === 0) {
    container.innerHTML = "<p class=\"detail-vide\">Aucun match ne remplit actuellement tous les critères du modèle. Ce n'est pas une erreur : le modèle préfère ne rien proposer plutôt que de proposer un pari incertain.</p>";
    return;
  }

  retenus.forEach((m) => container.appendChild(construitCarte(m)));
}

fetch("precalcul_leger.json?_=" + Date.now())
  .then((r) => {
    if (!r.ok) throw new Error("precalcul_leger.json introuvable (status " + r.status + ")");
    return r.json();
  })
  .then((data) => afficheSelections(data.signaux || []))
  .catch((err) => {
    document.getElementById("maj").textContent = "erreur de chargement : " + err.message;
    console.error(err);
  });
