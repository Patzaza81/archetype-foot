// archetype_comportement.js — page du moteur « Comportement » (19/10/2026). Présentation uniquement : le navigateur ne calcule rien,
// tout vient de data/comportement/pronostics_comportement.json (écrit par python -m matrice_scenarios.page_comportement).
// Même habillage que les autres moteurs (classes ax-*). Aucun lien avec V2, V3, V2R, Europe, Journal ni le pipeline.
const echappe = (x) => String(x ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fCote = (x) => Number(x).toFixed(2).replace(".", ",");
const fDate = (iso) => {
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso || "";
  const t = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
};
const CLASSES = ["rang-1", "rang-2", "rang-3", "rang-3", "rang-3"];
let compteur = 0;

function jauge(p) {
  const v = Math.max(0, Math.min(1, Number(p) || 0)), r = 42, c = 2 * Math.PI * r, pct = Math.round(v * 100);
  return `<div class="ax-jauge" role="img" aria-label="Probabilité du modèle : ${pct} %"><svg viewBox="0 0 100 100" aria-hidden="true">` +
    `<circle class="ax-jauge-fond" cx="50" cy="50" r="${r}"></circle>` +
    `<circle class="ax-jauge-valeur" cx="50" cy="50" r="${r}" stroke-dasharray="${(c * v).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 50 50)"></circle>` +
    `<circle class="ax-jauge-centre" cx="50" cy="50" r="33"></circle><text class="ax-jauge-texte" x="50" y="51">${pct}%</text></svg></div>`;
}

function resultat(s) {
  if (s.gagne === undefined) return "";
  return `<span class="ax-solidite"><span class="ax-solidite-titre">Résultat :</span> ${s.gagne ? "✔ gagné" : "✘ perdu"}</span>`;
}

function panneau(s, m, id, idOnglet) {
  const el = document.createElement("div");
  el.className = `ax-panneau ax-${CLASSES[s.rang - 1]}`;
  el.id = id; el.setAttribute("role", "tabpanel"); el.setAttribute("aria-labelledby", idOnglet);
  const role = s.role === "principal" ? "Pronostic principal" : `Tendance : ${s.tendance}`;
  el.innerHTML =
    `<h2 class="ax-marche">${echappe(s.libelle)}</h2>` +
    `<div class="ax-ligne-cote"><p class="ax-texte-resume">${echappe(role)}</p>` +
    `<div class="ax-badge-cote"><span>Cote</span><strong>${fCote(s.cote)}</strong></div></div>` +
    `<div class="ax-proba">${jauge(s.probabilite)}<span class="ax-proba-legende">Probabilité du modèle (surestimée)</span>${resultat(s)}</div>`;
  return el;
}

function tendances(m) {
  const lignes = (m.tendances || []).map((t) =>
    `<div class="ax-preuve"><div><span class="ax-preuve-titre">${echappe(t.titre)}</span><span class="ax-preuve-texte">${echappe(t.texte)}</span></div></div>`).join("");
  const s = m.series || {};
  const pied = s.domicile ? `<div class="ax-preuve"><div><span class="ax-preuve-titre">Séries</span><span class="ax-preuve-texte">${s.domicile} et ${s.exterieur} derniers matchs analysés.</span></div></div>` : "";
  return `<div class="ax-preuves"><div class="ax-preuves-liste">${lignes}${pied}</div></div>`;
}

function carte(m) {
  const id = ++compteur;
  const section = document.createElement("section");
  section.className = "ax-carte";
  section.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match"><span class="ax-equipe ax-dom">${echappe(m.domicile)}</span>` +
    `<div class="ax-horaire"><strong>${echappe(m.heure || "—")}</strong><span>${echappe(fDate(m.date))}</span></div>` +
    `<span class="ax-equipe ax-ext">${echappe(m.exterieur)}</span></div>` +
    `<div class="ax-match-bas"><p class="ax-competition">${echappe(String(m.competition || "").replace(/\s+/g, " ").trim())}${m.score ? ` · Score final ${m.score.buts_dom}-${m.score.buts_ext}` : ""}</p></div></div>`;
  section.insertAdjacentHTML("beforeend", tendances(m));
  const onglets = document.createElement("div");
  onglets.className = "ax-onglets"; onglets.setAttribute("role", "tablist"); onglets.setAttribute("aria-label", "Pronostics du match");
  onglets.style.gridTemplateColumns = `repeat(${Math.min(3, m.selections.length)},minmax(0,1fr))`;
  const zone = document.createElement("div");
  zone.className = "ax-panneaux";
  const actifs = m.selections.map((s) => {
    const idO = `ax-c-onglet-${id}-${s.rang}`, idP = `ax-c-panneau-${id}-${s.rang}`;
    const b = document.createElement("button");
    b.type = "button"; b.id = idO; b.className = `ax-onglet ax-${CLASSES[s.rang - 1]}`; b.setAttribute("role", "tab"); b.setAttribute("aria-controls", idP);
    b.innerHTML = `<span>${s.role === "principal" ? "Principal" : echappe(s.tendance)}</span>`;
    onglets.appendChild(b);
    const p = panneau(s, m, idP, idO); zone.appendChild(p);
    return { b, p };
  });
  const active = (cible) => actifs.forEach(({ b, p }) => {
    const oui = b === cible; b.classList.toggle("ax-actif", oui); b.setAttribute("aria-selected", String(oui)); b.tabIndex = oui ? 0 : -1; p.hidden = !oui;
  });
  actifs.forEach(({ b }) => b.addEventListener("click", () => active(b)));
  active(actifs[0].b);
  section.appendChild(onglets); section.appendChild(zone);
  return section;
}

function affiche(d) {
  const racine = document.getElementById("matches"), maj = document.getElementById("maj"), perf = document.getElementById("perf");
  const retenus = (d.matchs || []).filter((m) => m.statut === "OK" && m.selections.length).sort((a, b) => `${a.date}${a.heure || ""}`.localeCompare(`${b.date}${b.heure || ""}`));
  maj.textContent = retenus.length ? `${retenus.length} matchs avec pronostic · cote minimale ${fCote(d.cote_min)} · généré le ${d.genere_le}` : "Aucun pronostic pour le moment";
  const p = d.performance_archive;
  if (p) perf.textContent = `Réussite mesurée sur ${p.matchs} matchs joués : ${(p.reussite * 100).toFixed(1).replace(".", ",")} % (intervalle ${(p.ic95[0] * 100).toFixed(0)}–${(p.ic95[1] * 100).toFixed(0)} %). ${p.note}` + (d.pronostics_autres_tendances_archive ? ` Pronostics des autres tendances : ${(d.pronostics_autres_tendances_archive.reussite * 100).toFixed(0)} % sur ${d.pronostics_autres_tendances_archive.matchs} cas.` : "");
  racine.innerHTML = "";
  retenus.forEach((m) => racine.appendChild(carte(m)));
}

(function () {
  try { if (localStorage.getItem("archetype_theme_nuit") === "1") document.body.classList.add("theme-nuit"); } catch (e) {}
  const maj = document.getElementById("maj");
  fetch(`data/comportement/pronostics_comportement.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(affiche)
    .catch(() => { maj.textContent = "Données du moteur Comportement indisponibles."; });
})();
