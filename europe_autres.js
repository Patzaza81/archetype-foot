// europe_autres.js — page « Moteur Europe » : affiche TOUS les matchs européens qui n'ont pas d'aperçu, avec la raison
// (historique insuffisant, ou filtres). Aucun calcul dans le navigateur : les textes viennent de calibration_europe.py
// (data/europe/pronostics_europe.json, clé « autres »).
(function () {
  const racine = document.getElementById("autres");
  if (!racine) return;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
  const date = (iso) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || "")); return m ? `${m[3]}/${m[2]}` : "—"; };
  fetch(`data/europe/pronostics_europe.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then((d) => {
      const liste = Array.isArray(d.autres) ? d.autres : [];
      if (!liste.length) { racine.innerHTML = ""; return; }
      racine.innerHTML = `<h2 class="eu-titre">Autres matchs européens (${liste.length}) : aucun aperçu</h2>`;
      liste.forEach((m) => {
        const s = document.createElement("section");
        s.className = "ax-carte";
        s.innerHTML =
          `<div class="ax-match"><div class="ax-ligne-match">` +
          `<span class="ax-equipe ax-dom">${esc(m.domicile)}</span>` +
          `<div class="ax-horaire"><strong>${esc(m.heure || "—")}</strong><span>${esc(date(m.date))}</span></div>` +
          `<span class="ax-equipe ax-ext">${esc(m.exterieur)}</span></div>` +
          `<div class="ax-match-bas"><p class="ax-competition">${esc(String(m.competition || "").replace(/\s+/g, " ").trim())}</p></div></div>` +
          `<p class="eu-etat">${esc(m.etat)}</p><ul class="eu-lignes">${(m.lignes || []).map((l) => `<li>${esc(l)}</li>`).join("")}</ul>`;
        racine.appendChild(s);
      });
    })
    .catch((e) => { racine.innerHTML = `<p class="eu-etat">Autres matchs indisponibles : ${esc(e.message)}</p>`; });
})();
