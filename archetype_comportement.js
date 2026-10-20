// archetype_comportement.js — page du moteur alpha « séries » (remplace l'ancien alpha le 20/10/2026, demande de Patrick).
// Présentation uniquement : le navigateur ne calcule rien, tout vient de data/alpha_serie/pronostics.json
// (écrit par python -m alpha_serie.suivi pipeline). Même carte que la page V3 (classes ax-*), repliée au départ ; trois onglets par match :
// marchés de buts, marchés d'équipes, multiscores. Seuls les marchés retenus figurent dans les tableaux ; le registre des exclus est dans « Détails ».
const CLE_THEME_NUIT = "archetype_theme_nuit"; // même clé que theme.js
const NOMS_ONGLETS = [["buts", "Buts"], ["equipes", "Équipes"], ["multiscores", "Multiscores"]];

const echappeHtml = (x) => (x === null || x === undefined ? "" : String(x)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"));
const formatCote = (x) => { const n = Number(x); return Number.isFinite(n) && x !== null ? n.toFixed(2).replace(".", ",") : "à lire"; };
const formatPct = (x) => (x === null || x === undefined || !Number.isFinite(Number(x)) ? "—" : `${Math.round(Number(x) * 100)} %`);
function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  const t = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
// Jour courant à Douala (les dates des matchs sont à l'heure du Cameroun) : on n'affiche que les matchs d'aujourd'hui et à venir.
const aujourdhui = () => new Date().toLocaleDateString("en-CA", { timeZone: "Africa/Douala" });
let compteurCartes = 0;

function tableau(onglet, lignes) {
  if (!lignes.length) return `<p class="ax-texte-resume">Aucun marché retenu dans cet onglet pour ce match.</p>`;
  if (onglet === "multiscores") {
    return `<table class="ax-table"><thead><tr><th>Groupe de scores</th><th>Scénarios</th><th>Valeur</th><th>Cote</th></tr></thead><tbody>` +
      lignes.map((s) => `<tr><td>${echappeHtml(s.marche)}</td><td>${Number(s.scenarios)}/${Number(s.sur)}</td><td>${formatPct(s.valeur)}</td><td>${formatCote(s.cote)}</td></tr>`).join("") + `</tbody></table>`;
  }
  return `<table class="ax-table"><thead><tr><th>Marché</th><th>Offensive</th><th>Défensive</th><th>Valeur</th><th>Cote</th></tr></thead><tbody>` +
    lignes.map((s) => `<tr><td>${echappeHtml(s.marche)}${s.alerte ? `<span class="ax-alerte" title="${echappeHtml(s.alerte)}"> ⚠</span>` : ""}</td>` +
      `<td>${formatPct(s.offensive)}</td><td>${formatPct(s.defensive)}</td><td>${formatPct(s.valeur)}</td><td>${formatCote(s.cote)}</td></tr>`).join("") + `</tbody></table>`;
}

function construitDetails(m, idDetails) {
  const details = document.createElement("details");
  details.className = "details-analyse ax-details";
  details.id = idDetails;
  const sc = (l) => (l || []).map(([h, a]) => `${Number(h)}-${Number(a)}`).join(" · ");
  const rej = (m.rejetes || []).map((r) => `<li><strong>${echappeHtml(r.marche)}</strong> — ${echappeHtml(r.raison)}</li>`).join("");
  const niv = m.niveaux ? `Buts attendus : domicile ${Number(m.niveaux.dom).toFixed(2)}, extérieur ${Number(m.niveaux.ext).toFixed(2)}, total ${Number(m.niveaux.total).toFixed(2)}. ` : "";
  details.innerHTML = `<summary class="ax-summary-cache" tabindex="-1">Détails de l'analyse</summary><div class="ax-details-corps">` +
    `<div class="ax-tab"><h4 class="ax-tab-titre">Scénarios appariés (${Number(m.n_domicile)} matchs à domicile, ${Number(m.n_exterieur)} à l'extérieur, k = ${Number(m.k)})</h4>` +
    `<p class="ax-preuve-texte">${niv}</p><p class="ax-preuve-texte">Offensive : ${sc(m.scenarios_offensifs)}</p><p class="ax-preuve-texte">Défensive : ${sc(m.scenarios_defensifs)}</p></div>` +
    `<div class="ax-tab"><h4 class="ax-tab-titre">Marchés exclus et raison</h4><ul class="ax-v3-lignes">${rej || "<li>Aucun</li>"}</ul></div></div>`;
  return details;
}

function construitCarte(m) {
  const id = ++compteurCartes, idDetails = `ax-details-${id}`;
  const section = document.createElement("section");
  section.className = "ax-carte";
  const score = m.score && m.score.buts_dom !== undefined && m.score.buts_dom !== null ? ` · Score final ${Number(m.score.buts_dom)}-${Number(m.score.buts_ext)}` : "";
  section.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match">` +
      `<span class="ax-equipe ax-dom">${echappeHtml(m.domicile)}</span>` +
      `<div class="ax-horaire"><strong>${echappeHtml(m.heure || "—")}</strong><span>${echappeHtml(formatDate(m.date))}</span></div>` +
      `<span class="ax-equipe ax-ext">${echappeHtml(m.exterieur)}</span></div>` +
      `<div class="ax-match-bas"><p class="ax-competition">${echappeHtml(String(m.competition || "").replace(/\s+/g, " ").trim() + score)}</p><div class="ax-actions-tete"></div></div>` +
    `</div>`;
  const onglets = document.createElement("div");
  onglets.className = "ax-onglets"; onglets.setAttribute("role", "tablist"); onglets.setAttribute("aria-label", "Choix de l'onglet");
  const panneaux = document.createElement("div");
  panneaux.className = "ax-panneaux";
  const actifs = NOMS_ONGLETS.map(([cle, nom], i) => {
    const lignes = (m.onglets && m.onglets[cle]) || [];
    const idO = `ax-onglet-${id}-${i}`, idP = `ax-panneau-${id}-${i}`;
    const bouton = document.createElement("button");
    bouton.type = "button"; bouton.id = idO; bouton.className = `ax-onglet ax-rang-${Math.min(i + 1, 3)}`;
    bouton.setAttribute("role", "tab"); bouton.setAttribute("aria-controls", idP);
    bouton.innerHTML = `<span>${nom} (${lignes.length})</span>`;
    onglets.appendChild(bouton);
    const panneau = document.createElement("div");
    panneau.className = `ax-panneau ax-rang-${Math.min(i + 1, 3)}`; panneau.id = idP; panneau.setAttribute("role", "tabpanel"); panneau.setAttribute("aria-labelledby", idO);
    panneau.innerHTML = tableau(cle, lignes);
    panneaux.appendChild(panneau);
    return { bouton, panneau, n: lignes.length };
  });
  onglets.style.gridTemplateColumns = "repeat(3,minmax(0,1fr))";
  const active = (cible) => actifs.forEach(({ bouton, panneau }) => {
    const oui = bouton === cible;
    bouton.classList.toggle("ax-actif", oui); bouton.setAttribute("aria-selected", String(oui)); bouton.tabIndex = oui ? 0 : -1; panneau.hidden = !oui;
  });
  actifs.forEach(({ bouton }) => bouton.addEventListener("click", () => active(bouton)));
  active((actifs.find((a) => a.n) || actifs[0]).bouton);
  const blocDetails = construitDetails(m, idDetails);
  section.appendChild(onglets); section.appendChild(panneaux); section.appendChild(blocDetails);

  const pied = document.createElement("div");
  pied.className = "ax-pied";
  const boutonDetails = document.createElement("button");
  boutonDetails.type = "button"; boutonDetails.className = "ax-bouton-details";
  boutonDetails.textContent = "Détails de l'analyse";
  boutonDetails.setAttribute("aria-controls", idDetails); boutonDetails.setAttribute("aria-expanded", "false");
  boutonDetails.addEventListener("click", (e) => {
    e.stopPropagation();
    blocDetails.open = !blocDetails.open;
    boutonDetails.textContent = blocDetails.open ? "Masquer les détails" : "Détails de l'analyse";
    boutonDetails.setAttribute("aria-expanded", String(blocDetails.open));
  });
  const applique = (replie) => { section.classList.toggle("ax-replie", replie); section.setAttribute("aria-expanded", String(!replie)); };
  section.addEventListener("click", (e) => {
    if (e.target.closest("button, a, summary, [role=tab], table")) return;
    const sel = window.getSelection && window.getSelection();
    if (sel && String(sel).length) return;
    const avant = section.getBoundingClientRect().top;
    applique(!section.classList.contains("ax-replie"));
    const apres = section.getBoundingClientRect().top;
    if (Math.abs(apres - avant) > 1) window.scrollBy(0, apres - avant);
  });
  applique(true);
  pied.appendChild(boutonDetails); section.appendChild(pied);
  return section;
}

function afficheSelections(d) {
  const racine = document.getElementById("matches"), maj = document.getElementById("maj"), perf = document.getElementById("perf");
  const jour = aujourdhui();
  const cleTri = (m) => `${m.date || ""}${m.heure || ""}`;
  const aUnMarche = (m) => Object.values(m.onglets || {}).some((l) => (l || []).length);
  const retenus = (d.matchs || []).filter((m) => m.statut === "analyse" && m.date >= jour && aUnMarche(m)).sort((a, b) => cleTri(a).localeCompare(cleTri(b)));
  maj.textContent = retenus.length ? `${retenus.length} match${retenus.length > 1 ? "s" : ""} avec au moins un marché retenu · cote minimale ${formatCote(d.cote_min)} (buts et équipes)` : "Aucun pronostic pour le moment";
  const b = d.bilan_gele;
  if (perf) {
    const lignes = b ? NOMS_ONGLETS.map(([c, nom]) => ((b.onglets || {})[c] || {}).cas ? `${nom} : ${formatPct(b.onglets[c].reussite)} sur ${b.onglets[c].cas} cas` : "").filter(Boolean) : [];
    perf.textContent = lignes.length ? `Réussite réelle (pronostics gelés avant le match) — ${lignes.join(" · ")}. Aucune rentabilité démontrée.` :
      "Aucun résultat sur des pronostics gelés pour l'instant : la réussite réelle s'affichera ici. Aucune rentabilité démontrée.";
  }
  racine.innerHTML = "";
  if (!retenus.length) {
    racine.innerHTML = `<div class="ax-etat-vide"><strong>Aucun pronostic pour le moment</strong>` +
      `<p>Aucun match à venir ne respecte les normes du moteur (les deux branches à 50 % au moins et la marge de niveau).</p></div>`;
    return;
  }
  retenus.forEach((m) => racine.appendChild(construitCarte(m)));
}

function installeThemeNuit() {
  const bouton = document.getElementById("ax-bouton-theme");
  if (!bouton) return;
  const applique = (nuit) => {
    document.body.classList.toggle("theme-nuit", nuit);
    bouton.textContent = nuit ? "☀" : "☾";
    bouton.setAttribute("aria-label", nuit ? "Activer le mode clair" : "Activer le mode nuit");
  };
  let nuit = false;
  try { nuit = localStorage.getItem(CLE_THEME_NUIT) === "1"; } catch (e) { /* stockage indisponible */ }
  applique(nuit);
  bouton.addEventListener("click", () => {
    const suivant = !document.body.classList.contains("theme-nuit");
    try { localStorage.setItem(CLE_THEME_NUIT, suivant ? "1" : "0"); } catch (e) { /* ignoré */ }
    applique(suivant);
  });
}

installeThemeNuit();
if (document.getElementById("matches")) {
  fetch(`data/alpha_serie/pronostics.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`données introuvables (${r.status})`); return r.json(); })
    .then(afficheSelections)
    .catch((e) => { document.getElementById("maj").textContent = "Données du moteur alpha indisponibles : " + e.message; console.error(e); });
}
