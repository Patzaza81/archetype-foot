// script.js — Module 4 complet (25/08). Vue par défaut (verdict, paris
// recommandés, risques) + niveau de détail N1/N2 dans une section
// dépliable native (<details>), pour combler les 4 manques identifiés :
// bloc "pourquoi", LISTE_A visible, lambda/ajustements (N2), et tous les
// marchés calculés même ceux hors LISTE_A/B (over/under complet, BTTS,
// pair/impair, cages inviolées -- ces trois derniers sans cote scrapée,
// affichés en probabilité modèle seule, jamais présentés comme jouables).

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
      <span class="pari-marche">${p.marche}${estPariEnOr ? " ⭐" : ""}</span>
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
    lignes.push(`confiance faible sur ce calcul -- construit sur ${m.nb_matchs_domicile_utilises} matchs domicile / ${m.nb_matchs_exterieur_utilises} matchs extérieur.`);
  }
  if (m.avertissement_cotes || m.avertissement_classement || m.avertissement_h2h) {
    lignes.push("certaines données contextuelles (cotes, classement ou historique direct) n'ont pas pu être récupérées -- calcul poursuivi avec les données disponibles.");
  }
  if (lignes.length === 0) return "";
  return `<div class="bloc-risques">
    <div class="risques-titre">⚠ à lire avant de parier</div>
    ${lignes.map(l => `<div class="risque-ligne">${l}</div>`).join("")}
  </div>`;
}

// --- NIVEAU DE DÉTAIL (N1/N2), dans <details>, jamais affiché par défaut ---

function construitBlocPourquoi(m) {
  const lam = m.lambda;
  if (!lam) return "";
  return `<p class="detail-pourquoi">
    lambda domicile : ${lam.lambda_home.toFixed(2)} (base ${lam.audit.lambda_home_base.toFixed(2)},
    ajustement contexte ${(lam.audit.ajustement_home*100).toFixed(1)}%) —
    lambda extérieur : ${lam.lambda_away.toFixed(2)} (base ${lam.audit.lambda_away_base.toFixed(2)},
    ajustement contexte ${(lam.audit.ajustement_away*100).toFixed(1)}%).
    confiance : ${m.confiance || "n/d"} (${m.nb_matchs_domicile_utilises ?? "?"} dom. / ${m.nb_matchs_exterieur_utilises ?? "?"} ext.)
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
    <thead><tr><th>marché</th><th>cote</th><th>proba modèle</th><th>ev</th></tr></thead>
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
    <p class="detail-sous-titre">tous les marchés calculés (probabilité modèle seule, pas nécessairement cotés)</p>
    ${lignesOU}${autres}
  </div>`;
}

function construitDetails(m) {
  if (!m.traite) return "";
  return `<details class="details-niveau1">
    <summary>voir le détail (n1/n2)</summary>
    ${construitBlocPourquoi(m)}
    <p class="detail-sous-titre">liste_a — marchés évalués, avant filtre de corrélation</p>
    ${construitTableListeA(m.LISTE_A_marches_passant_EV_et_cote)}
    ${construitAutresMarches(m.marches)}
  </details>`;
}

fetch("data.json?_=" + Date.now())
  .then((r) => r.json())
  .then((data) => {
    const nbDispo = data.nb_matchs_du_jour_disponibles;
    const nbSelect = data.nb_matchs_selectionnes;
    document.getElementById("maj").textContent =
      "mis à jour : " + (data.genere_le || "inconnu") +
      " — " + data.nb_matchs + " match(s) traité(s)" +
      (nbSelect != null ? ` sur ${nbSelect} sélectionné(s)` : "") +
      (nbDispo != null ? ` (${nbDispo} disponibles aujourd'hui)` : "");

    const container = document.getElementById("matches");
    if (!data.matchs || data.matchs.length === 0) {
      container.innerHTML = "<p>aucun match traité pour le moment. as-tu mis à jour matchs_selectionnes.json ?</p>";
      return;
    }

    data.matchs.forEach((m) => {
      const div = document.createElement("div");
      const estGo = m.verdict_global === "GO";
      div.className = "match" + (estGo ? " match-go" : " match-nogo");

      let corpsHtml;
      if (!m.traite) {
        corpsHtml = `<div class="signal signal-non-traite">non analysé — ${traduireRaison(m.raison_non_traite)}</div>`;
      } else {
        const badge = `<span class="badge ${estGo ? "badge-go" : "badge-nogo"}">${m.verdict_global || "?"}</span>`;
        const motif = (!estGo && m.motif_no_go) ? `<div class="motif-no-go">${m.motif_no_go}</div>` : "";
        const paris = estGo ? construitBlocParisRecommandes(m.LISTE_B_liste_finale_apres_correlation) : "";
        const risques = construitBlocRisques(m);
        corpsHtml = `
          <div class="ligne-verdict">${badge}<span class="proba-1">p(1) modèle : ${formatPct(m.probabilite_victoire_domicile)}</span></div>
          ${motif}${paris}${risques}${construitDetails(m)}
        `;
      }

      div.innerHTML = `
        <div class="teams"><span>${m.domicile}</span><span>${m.score || m.heure || ""}</span><span>${m.exterieur}</span></div>
        <div class="meta">${(m.competition || "").replace(/\s+/g, " ").trim()}</div>
        ${corpsHtml}
      `;
      container.appendChild(div);
    });
  })
  .catch((err) => {
    document.getElementById("maj").textContent = "erreur de chargement des données.";
    console.error(err);
  });
