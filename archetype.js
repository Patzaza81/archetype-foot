// archetype.js — créé le 10/09/2026, à la demande explicite de Patrick :
// "une page unique pour les pronostics retenus du nouveau moteur", après
// confusion sur pronostics.html où les sélections archetype_model étaient
// noyées parmi tout l'historique de l'ancien moteur (verdict_global,
// GO/NO_GO...). Cette page ne connaît qu'UN SEUL critère de tri : la
// sélection réelle d'archetype_model (voir estArchetypeGo). Rien d'autre à
// parcourir, rien de l'ancien moteur affiché ici.

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
  // Même plafond que script.js::formatPct -- une proba à 99.95%+ (mais
  // pas exactement 1.0) ne doit jamais s'afficher "100.0%".
  if (pct >= 99.95 && x < 1) return "99.9%";
  return pct.toFixed(1) + "%";
}

function construitLigneCandidat(rang, c) {
  if (!c) return "";
  return `<div class="am-ligne am-candidat">
    <strong>${echappeHtml(rang)}</strong> — ${echappeHtml(c.marche)}
    (niveau ${echappeHtml(c.niveau || "?")}, edge ${formatPctSur(c.edge)}, edv ${formatPctSur(c.edv)},
    H2H ${echappeHtml(c.h2h_palier || "?")})
  </div>`;
}

function construitCarte(m) {
  const div = document.createElement("div");
  div.className = "match";

  const heureAffichee = m.heure_cameroun || m.heure || "";
  const dateHeure = `${m.date || ""}${heureAffichee ? " à " + heureAffichee : ""}${m.heure_cameroun ? " (heure Cameroun)" : ""}`;
  const selection = m.archetype_model.selection || {};

  div.innerHTML = `
    <div class="teams"><span>${echappeHtml(m.domicile)}</span><span>${echappeHtml(m.score || heureAffichee || "")}</span><span>${echappeHtml(m.exterieur)}</span></div>
    <div class="meta">${echappeHtml((m.competition || "").replace(/\s+/g, " ").trim())}${dateHeure ? " — " + echappeHtml(dateHeure) : ""}</div>
    <div class="ligne-verdict"><span class="badge badge-archetype">★ ARCHETYPE</span></div>
    ${construitLigneCandidat("P1", selection.P1)}
    ${construitLigneCandidat("P2", selection.P2)}
    ${construitLigneCandidat("P3", selection.P3)}
  `;
  return div;
}

function afficheSelections(matchs) {
  const container = document.getElementById("matches");
  const maj = document.getElementById("maj");
  container.innerHTML = "";

  const retenus = (matchs || []).filter(estArchetypeGo);
  // Tri chronologique (date puis heure) -- le match le plus proche en premier.
  retenus.sort((a, b) => {
    const cleA = (a.date || "") + (a.heure_cameroun || a.heure || "");
    const cleB = (b.date || "") + (b.heure_cameroun || b.heure || "");
    return cleA.localeCompare(cleB);
  });

  maj.textContent = retenus.length
    ? `${retenus.length} sélection(s) archetype_model`
    : "aucune sélection archetype_model pour le moment";

  if (retenus.length === 0) {
    container.innerHTML = "<p class=\"detail-vide\">Aucun match n'a actuellement de sélection archetype_model (P1 réel). Ce n'est pas une erreur -- voir le filtre de convergence (unanimité des 4 scénarios).</p>";
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
