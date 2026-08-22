fetch("data.json?_=" + Date.now())
  .then((r) => r.json())
  .then((data) => {
    document.getElementById("maj").textContent =
      "Mis à jour : " + (data.genere_le || "inconnu") + " — " + data.nb_matchs + " match(s)";

    const container = document.getElementById("matches");
    if (!data.matchs || data.matchs.length === 0) {
      container.innerHTML = "<p>Aucun match pour le moment.</p>";
      return;
    }

    data.matchs.forEach((m) => {
      const div = document.createElement("div");
      div.className = "match" + (m.standout ? " standout" : "");

      let signalHtml = "";
      if (m.traite && m.mise_kelly_victoire_domicile > 0) {
        signalHtml = `<div class="signal">
          P(1) modèle : ${(m.probabilite_victoire_domicile * 100).toFixed(1)}%
          — EV : ${(m.ev_victoire_domicile * 100).toFixed(1)}%
          — <span class="mise">Mise conseillée : ${(m.mise_kelly_victoire_domicile * 100).toFixed(2)}% bankroll</span>
        </div>`;
      } else if (m.traite) {
        signalHtml = `<div class="signal">Analysé — aucun pari ne passe les filtres.</div>`;
      } else {
        signalHtml = `<div class="signal">Données insuffisantes pour le calcul.</div>`;
      }

      div.innerHTML = `
        <div class="teams"><span>${m.domicile}</span><span>${m.score || m.heure || ""}</span><span>${m.exterieur}</span></div>
        <div class="meta">${m.competition || ""}</div>
        ${signalHtml}
      `;
      container.appendChild(div);
    });
  })
  .catch((err) => {
    document.getElementById("maj").textContent = "Erreur de chargement des données.";
    console.error(err);
  });
