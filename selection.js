// selection.js — Refonte visuelle (25/08). Lignes simplifiées
// "☐ Équipe A — Équipe B", section par compétition en bande turquoise
// sombre, case cochée en turquoise via accent-color (pas de recoloration
// manuelle fragile). Aucune écriture automatique vers GitHub -- le bouton
// "Copier" produit le texte à coller à la main.

const selectionnes = new Set();

function metAJourCompteurEtBouton() {
  const n = selectionnes.size;
  document.getElementById("copier-btn").textContent = `copier la sélection (${n})`;
  document.getElementById("compteur").textContent =
    n === 0 ? "aucun match sélectionné." : `${n} match(s) sélectionné(s).`;
}

function copierSelection() {
  const idsTries = Array.from(selectionnes);
  const json = JSON.stringify(idsTries, null, 2);
  const zoneTexte = document.getElementById("sortie-json");
  zoneTexte.value = json;
  zoneTexte.select();
  if (navigator.clipboard) {
    navigator.clipboard.writeText(json).catch(() => {});
  }
}

fetch("matchs_du_jour.json?_=" + Date.now())
  .then((r) => {
    if (!r.ok) throw new Error("matchs_du_jour.json introuvable (status " + r.status + ")");
    return r.json();
  })
  .then((data) => {
    const matchs = Array.isArray(data) ? data : (data.matchs || []);
    document.getElementById("maj").textContent = matchs.length + " match(s) disponible(s) aujourd'hui";

    const liste = document.getElementById("liste");
    if (matchs.length === 0) {
      liste.innerHTML = "<p>aucun match disponible.</p>";
      return;
    }

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
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) selectionnes.add(m.match_id);
        else selectionnes.delete(m.match_id);
        metAJourCompteurEtBouton();
      });

      const label = document.createElement("label");
      label.htmlFor = checkbox.id;
      label.textContent = `${m.domicile} — ${m.exterieur}` + (m.score ? ` (${m.score})` : "");

      div.appendChild(checkbox);
      div.appendChild(label);
      liste.appendChild(div);
    });

    metAJourCompteurEtBouton();
  })
  .catch((err) => {
    document.getElementById("maj").textContent = "erreur de chargement : " + err.message;
    console.error(err);
  });

document.getElementById("copier-btn").addEventListener("click", copierSelection);
