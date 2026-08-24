const RAISONS_LISIBLES = {
  "donnees_de_base_manquantes": "Données de base manquantes (équipe/compétition non identifiée)",
  "url_equipe_introuvable_sur_page_match": "Page équipe introuvable sur matchendirect",
  "historique_domicile_ou_exterieur_vide": "Aucun historique domicile ou extérieur exploitable",
};

function traduireRaison(raison) {
  if (!raison) return "Raison inconnue";
  // Cas "domicile: xxx" / "exterieur: xxx" -- garde le préfixe, traduit le code connu si possible
  const match = raison.match(/^(domicile|exterieur):\s*(.+)$/);
  if (match) {
    const cote = match[1] === "domicile" ? "Équipe à domicile" : "Équipe à l'extérieur";
    const code = match[2];
    if (code.startsWith("aucun_match_joue")) {
      return `${cote} : aucun match joué cette saison ni la précédente dans cette compétition`;
    }
    return `${cote} : ${code}`;
  }
  if (raison.startsWith("erreur_technique:")) {
    return "Erreur technique : " + raison.replace("erreur_technique:", "").trim();
  }
  return RAISONS_LISIBLES[raison] || raison;
}

fetch("data.json?_=" + Date.now())
  .then((r) => r.json())
  .then((data) => {
    const nbDispo = data.nb_matchs_du_jour_disponibles;
    const nbSelect = data.nb_matchs_selectionnes;
    document.getElementById("maj").textContent =
      "Mis à jour : " + (data.genere_le || "inconnu") +
      " — " + data.nb_matchs + " match(s) traité(s)" +
      (nbSelect != null ? ` sur ${nbSelect} sélectionné(s)` : "") +
      (nbDispo != null ? ` (${nbDispo} disponibles aujourd'hui)` : "");

    const container = document.getElementById("matches");
    if (!data.matchs || data.matchs.length === 0) {
      container.innerHTML = "<p>Aucun match traité pour le moment. As-tu mis à jour matchs_selectionnes.json ?</p>";
      return;
    }

    data.matchs.forEach((m) => {
      const div = document.createElement("div");
      div.className = "match" + (m.standout ? " standout" : "");

      let signalHtml = "";
      if (m.traite) {
        const proba = (m.probabilite_victoire_domicile * 100).toFixed(1);
        const coteTxt = m.cote_1 != null ? m.cote_1.toFixed(2) : "indisponible";
        const confianceTxt = m.confiance || "INCONNUE";
        const nbMatchsTxt = (m.nb_matchs_domicile_utilises != null && m.nb_matchs_exterieur_utilises != null)
          ? `${m.nb_matchs_domicile_utilises} dom. / ${m.nb_matchs_exterieur_utilises} ext.`
          : "n/d";

        let ligneParis = "";
        if (m.mise_kelly_victoire_domicile > 0) {
          ligneParis = `<div class="mise">Mise conseillée : ${(m.mise_kelly_victoire_domicile * 100).toFixed(2)}% bankroll` +
            (m.standout ? " — ⭐ Pari en or" : "") + `</div>`;
        } else if (m.cote_1 != null) {
          ligneParis = `<div class="mise-nulle">Aucun pari ne passe les filtres (cote hors fourchette ou EV insuffisant)</div>`;
        } else {
          ligneParis = `<div class="mise-nulle">Cote indisponible — EV non calculable</div>`;
        }

        signalHtml = `<div class="signal">
          P(1) modèle : ${proba}% — Cote retenue : ${coteTxt}
          ${m.ev_victoire_domicile != null ? `— EV : ${(m.ev_victoire_domicile * 100).toFixed(1)}%` : ""}
          ${ligneParis}
          <div class="meta-confiance">Confiance : ${confianceTxt} (${nbMatchsTxt})</div>
        </div>`;
      } else {
        signalHtml = `<div class="signal signal-non-traite">
          Non analysé — ${traduireRaison(m.raison_non_traite)}
        </div>`;
      }

      div.innerHTML = `
        <div class="teams"><span>${m.domicile}</span><span>${m.score || m.heure || ""}</span><span>${m.exterieur}</span></div>
        <div class="meta">${(m.competition || "").replace(/\s+/g, " ").trim()}</div>
        ${signalHtml}
      `;
      container.appendChild(div);
    });
  })
  .catch((err) => {
    document.getElementById("maj").textContent = "Erreur de chargement des données.";
    console.error(err);
  });
