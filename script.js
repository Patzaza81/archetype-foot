// script.js — Module 4, hiérarchie visuelle à 5 niveaux (25/08) :
// 1. identification (équipes/compétition) 2. statut (verdict, texte +
// couleur, jamais couleur seule) 3. donnée principale (p(1), plus grosse
// taille de l'écran) 4. détails (paris, risques) 5. action secondaire
// (détail N1/N2, repliée par défaut).

const RAISONS_LISIBLES = {
  "donnees_de_base_manquantes": "données de base manquantes (équipe/compétition non identifiée)",
  "url_equipe_introuvable_sur_page_match": "page équipe introuvable sur matchendirect",
  "historique_domicile_ou_exterieur_vide": "aucun historique domicile ou extérieur exploitable",
};

function traduireRaison(raison) {
  if (!raison) return "raison inconnue";
  const m = raison.match(/^(domicile|exterieur):\s*(.+)$/);
  if (m) {
    const cote = m[1] === "domicile" ? "équipe à domicile" : "équipe à l'extérieur";
    const code = m[2];
    if (code.startsWith("aucun_match_joue")) {
      return `${cote} : aucun match joué cette saison ni la précédente dans cette compétition`;
    }
    return `${cote} : ${code}`;
  }
  if (raison.startsWith("erreur_technique:")) {
    return "erreur technique : " + raison.replace("erreur_technique:", "").trim();
  }
  return RAISONS_LISIBLES[raison] || raison;
}

function formatPct(x) { return (x * 100).toFixed(1) + "%"; }

function construitBlocParisRecommandes(listeB) {
  if (!listeB || listeB.length === 0) return "";
  const parisTries = [...listeB].sort((a, b) => b.probabilite_modele - a.probabilite_modele);
  const pariEnOr = parisTries[0];
  const lignes = listeB.map((p) => {
    const estPariEnOr = p === pariEnOr;
    return `<div class="pari-ligne${estPariEnOr ? " pari-en-or" : ""}">
      <span class="pari-marche">${p.marche}${estPariEnOr ? " ★ pari en or" : ""}</span>
      <span class="pari-cote">cote ${p.cote_observee.toFixed(2)}</span>
      <span class="pari-mise">${(p.mise_pct_bankroll * 100).toFixed(2)}% bankroll</span>
    </div>`;
  }).join("");
  return `<div class="bloc-paris">${lignes}</div>`;
}

function construitBlocRisques(m) {
  const lignes = [];
  if (m.coefficients_empiriques === false) {
    lignes.push("les seuils de ce système n'ont pas encore été validés sur un historique de résultats réels.");
  }
  if (m.confiance === "FAIBLE") {
    lignes.push(`confiance faible -- construit sur ${m.nb_matchs_domicile_utilises} matchs domicile / ${m.nb_matchs_exterieur_utilises} matchs extérieur.`);
  }
  if (m.avertissement_cotes || m.avertissement_classement || m.avertissement_h2h) {
    lignes.push("certaines données contextuelles n'ont pas pu être récupérées -- calcul poursuivi avec les données disponibles.");
  }
  if (lignes.length === 0) return "";
  return `<div class="bloc-risques">
    <div class="risques-titre">⚠ à lire avant de parier</div>
    ${lignes.map(l => `<div class="risque-ligne">${l}</div>`).join("")}
  </div>`;
}

function construitBlocPourquoi(m) {
  const lam = m.lambda;
  if (!lam) return "";
  return `<p class="detail-pourquoi">
    lambda domicile : ${lam.lambda_home.toFixed(2)} (base ${lam.audit.lambda_home_base.toFixed(2)},
    ajustement contexte ${(lam.audit.ajustement_home*100).toFixed(1)}%) —
    lambda extérieur : ${lam.lambda_away.toFixed(2)} (base ${lam.audit.lambda_away_base.toFixed(2)},
    ajustement contexte ${(lam.audit.ajustement_away*100).toFixed(1)}%).
  </p>`;
}

function construitTableListeA(listeA) {
  if (!listeA || listeA.length === 0) {
    return `<p class="detail-vide">aucun marché n'a passé le filtre EV + fourchette de cote.</p>`;
  }
  const lignes = listeA.map(c => `<tr>
    <td>${c.marche}</td><td>${c.cote_observee.toFixed(2)}</td>
    <td>${formatPct(c.probabilite_modele)}</td><td>${formatPct(c.ev_brut)}</td>
  </tr>`).join("");
  return `<table class="detail-table">
    <thead><tr><th>marché</th><th>cote</th><th>proba</th><th>ev</th></tr></thead>
    <tbody>${lignes}</tbody>
  </table>`;
}

function construitAutresMarches(marches) {
  if (!marches) return "";
  const lignesOU = Object.entries(marches.over_under || {})
    .sort((a, b) => parseFloat(a[0]) - parseFloat(b[0]))
    .map(([ligne, p]) => `<div class="detail-marche-ligne">plus de ${ligne} buts : ${formatPct(p.plus)}</div>`)
    .join("");
  const autres = [
    marches.btts ? `<div class="detail-marche-ligne">btts oui : ${formatPct(marches.btts.oui)}</div>` : "",
    marches.pair_impair ? `<div class="detail-marche-ligne">total pair : ${formatPct(marches.pair_impair.pair)}</div>` : "",
    marches.cages_inviolees_domicile ? `<div class="detail-marche-ligne">cage inviolée domicile : ${formatPct(marches.cages_inviolees_domicile.oui)}</div>` : "",
    marches.cages_inviolees_exterieur ? `<div class="detail-marche-ligne">cage inviolée extérieur : ${formatPct(marches.cages_inviolees_exterieur.oui)}</div>` : "",
  ].join("");
  return `<div class="detail-autres-marches">
    <p class="detail-sous-titre">tous les marchés calculés</p>
    ${lignesOU}${autres}
  </div>`;
}

function construitDetails(m) {
  if (!m.traite) return "";
  return `<details class="details-niveau1">
    <summary>voir les détails</summary>
    ${construitBlocPourquoi(m)}
    <p class="detail-sous-titre">marchés évalués avant filtre de corrélation</p>
    ${construitTableListeA(m.LISTE_A_marches_passant_EV_et_cote)}
    ${construitAutresMarches(m.marches)}
  </details>`;
}

// Niveau 3 -- donnée principale. CORRIGÉ (25/08) : n'affiche PLUS la
// probabilité de victoire domicile par défaut, quel que soit le pari
// retenu -- c'était trompeur (ex. le pari en or est "Moins de 2.5 buts",
// mais le site affichait "p(1) victoire domicile : 27%" sans rapport).
// Affiche désormais la probabilité du PARI RÉELLEMENT RETENU (le pari en
// or de LISTE_B, probabilité la plus haute), avec le nom du marché et une
// justification chiffrée. Rien n'est affiché si NO_GO -- aucun pari
// retenu, rien à mettre en avant ni à justifier.
function construitNiveau3(m) {
  if (m.verdict_global !== "GO") return "";
  const listeB = m.LISTE_B_liste_finale_apres_correlation;
  if (!listeB || listeB.length === 0) return "";
  const pariEnOr = [...listeB].sort((a, b) => b.probabilite_modele - a.probabilite_modele)[0];
  return `<div class="proba-1">
    ${formatPct(pariEnOr.probabilite_modele)}
    <span class="proba-1-label">probabilité modèle — ${pariEnOr.marche}</span>
  </div>
  <p class="pourquoi-pari">
    pourquoi ce pari : cote ${pariEnOr.cote_observee.toFixed(2)}, ev ${formatPct(pariEnOr.ev_brut)},
    confiance ${m.confiance || "n/d"} (${m.nb_matchs_domicile_utilises ?? "?"} matchs domicile /
    ${m.nb_matchs_exterieur_utilises ?? "?"} matchs extérieur utilisés).
  </p>`;
}

// Filet de sécurité (25/08sexies) : sur connexion lente, si la requête ne
// répond pas du tout (ni succès ni échec réseau), rien n'indiquait pourquoi
// la page restait bloquée sur "Chargement...". Un délai explicite rend
// l'attente visible plutôt que silencieuse.
const delaiDepasse = new Promise((_, reject) =>
  setTimeout(() => reject(new Error("délai dépassé (15s) -- vérifie ta connexion, ou que data.json existe bien à la racine du site")), 15000)
);

Promise.race([fetch("data.json?_=" + Date.now()), delaiDepasse])
  .then((r) => r.json())
  .then((data) => {
    const nbDispo = data.nb_matchs_du_jour_disponibles;
    const nbDemain = data.nb_matchs_demain_disponibles;
    const nbPanier = data.nb_entrees_panier;
    document.getElementById("maj").textContent =
      "mis à jour : " + (data.genere_le || "inconnu") +
      " — " + data.nb_matchs + " match(s) traité(s)" +
      (nbPanier != null ? ` sur ${nbPanier} entrée(s) du panier` : "") +
      (nbDispo != null ? ` (${nbDispo} dispo. aujourd'hui` : "") +
      (nbDemain != null ? `, ${nbDemain} demain)` : (nbDispo != null ? ")" : ""));

    const container = document.getElementById("matches");
    if (!data.matchs || data.matchs.length === 0) {
      container.innerHTML = "<p>aucun match traité pour le moment -- as-tu ajouté des matchs au panier (page \"sélectionner des matchs\") et copié panier.json avant de lancer le workflow ?</p>";
      return;
    }

    data.matchs.forEach((m) => {
      const div = document.createElement("div");
      div.className = "match";

      // Niveau 1 -- identification
      let html = `
        <div class="teams"><span>${m.domicile}</span><span>${m.score || m.heure || ""}</span><span>${m.exterieur}</span></div>
        <div class="meta">${(m.competition || "").replace(/\s+/g, " ").trim()}</div>
      `;

      if (!m.traite) {
        // Statut seul quand non analysé -- pas de niveau 3/4 à afficher
        html += `<div class="signal-non-traite">non analysé — ${traduireRaison(m.raison_non_traite)}</div>`;
      } else {
        const estGo = m.verdict_global === "GO";
        // Niveau 2 -- statut (texte ET couleur, jamais couleur seule)
        html += `<div class="ligne-verdict">
          <span class="badge ${estGo ? "badge-go" : "badge-nogo"}">${estGo ? "✓ GO" : "✕ NO_GO"}</span>
        </div>`;
        // Niveau 3 -- probabilité du pari RETENU uniquement, jamais la
        // victoire domicile par défaut (voir construitNiveau3 ci-dessus).
        html += construitNiveau3(m);

        // Niveau 4 -- détails
        if (!estGo && m.motif_no_go) {
          html += `<div class="motif-no-go">${m.motif_no_go}</div>`;
        }
        if (estGo) {
          html += construitBlocParisRecommandes(m.LISTE_B_liste_finale_apres_correlation);
        }
        html += construitBlocRisques(m);

        // Niveau 5 -- action secondaire, repliée
        html += construitDetails(m);
      }

      div.innerHTML = html;
      container.appendChild(div);
    });
  })
  .catch((err) => {
    document.getElementById("maj").textContent = "erreur de chargement : " + err.message;
    console.error(err);
  });
