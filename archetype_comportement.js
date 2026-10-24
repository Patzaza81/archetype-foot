// archetype_comportement.js — page du moteur alpha « séries » (remplace l'ancien alpha le 20/10/2026, demande de Patrick).
// Présentation uniquement : le navigateur ne calcule rien, tout vient de data/alpha_serie/pronostics.json
// (écrit par python -m alpha_serie.suivi pipeline). Même carte que la page V3 (classes ax-*) ; trois onglets par match :
// marchés de buts, marchés d'équipes, multiscores. Seuls les marchés retenus figurent dans les listes ; le registre des exclus est dans « Détails ».
// Affichage (22/10/2026) : carte repliée = le meilleur marché de chaque onglet est lisible dès l'entrée (aperçu .ax-resume) ;
// carte dépliée = une ligne par marché, pensée pour l'écran du téléphone (plus de tableau à 5 colonnes) ; alertes écrites en toutes lettres.
const CLE_THEME_NUIT = "archetype_theme_nuit"; // même clé que theme.js
// 24/10/2026 : onglet « Calibrés » = règles exploitables de la campagne d'optimisation (alpha_serie/calibrees.py).
// Règle définitive d'affichage (24/10/2026, Patrick) : cinq catégories indépendantes, voir af-alpha-selection.js.
const BILAN_ONGLETS = [["buts", "Buts"], ["equipes", "Équipes"], ["multiscores", "Multiscores"], ["calibrees", "Calibrés"]];   // bilan gelé : onglets du fichier

const echappeHtml = (x) => (x === null || x === undefined ? "" : String(x)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;"));
const aUneCote = (x) => x !== null && x !== undefined && Number.isFinite(Number(x));
const formatCote = (x) => (aUneCote(x) ? Number(x).toFixed(2).replace(".", ",") : "à lire");
const formatPct = (x) => (x === null || x === undefined || !Number.isFinite(Number(x)) ? "—" : `${Math.round(Number(x) * 100)} %`);
function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  const t = d.toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
// Jour courant à Douala (les dates des matchs sont à l'heure du Cameroun) : on n'affiche que les matchs d'aujourd'hui et à venir.
// Ne pas dépendre du rendu local de "en-CA" (Safari peut retourner MM/DD/YYYY).
// Le JSON utilise strictement YYYY-MM-DD : les deux formats doivent être identiques.
const aujourdhui = () => {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Africa/Douala",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).formatToParts(new Date());
  const valeurs = Object.fromEntries(parts.filter((p) => p.type !== "literal").map((p) => [p.type, p.value]));
  return `${valeurs.year}-${valeurs.month}-${valeurs.day}`;
};
let compteurCartes = 0;

// ── Libellés en mots simples (présentation seulement : la clé du marché dans le fichier de données reste inchangée) ──
const butsN = (n) => `${n} but${n > 1 ? "s" : ""}`;
const auMoins = (ligne) => Math.floor(ligne) + 1;               // 1,5 -> 2 ; 2,5 -> 3 ; 0,5 -> 1
const nombre = (t) => Number(String(t).replace(",", "."));
function sensHandicap(L, eq) {                                   // buts marqués + L > buts encaissés, du point de vue de l'équipe
  const m = Math.floor(-L) + 1;
  if (m >= 1) return `${eq} gagne${m > 1 ? ` par ${butsN(m)} d'écart ou plus` : ""}`;
  return m === 0 ? `${eq} ne perd pas` : `${eq} ne perd pas par ${butsN(1 - m)} d'écart ou plus`;
}
function libelleClair(marche, dom, ext) {
  const m = String(marche || ""), d = dom || "L'équipe à domicile", e = ext || "L'équipe à l'extérieur";
  let r;
  const fixes = {
    "Victoire domicile": `${d} gagne`, "Victoire extérieur": `${e} gagne`, "Match nul": "Match nul (égalité, quel que soit le score)",
    "Domicile ne perd pas (1N)": `${d} ne perd pas (victoire ou nul)`, "Extérieur ne perd pas (N2)": `${e} ne perd pas (victoire ou nul)`,
    "Pas de nul (12)": "Pas de match nul (l'une des deux équipes gagne)",
    "Les deux marquent : oui": "Les deux équipes marquent (au moins 1 but chacune)", "Les deux marquent : non": "Au moins une équipe ne marque pas",
    "Total de buts pair": "Nombre total de buts pair (0, 2, 4…)", "Total de buts impair": "Nombre total de buts impair (1, 3, 5…)",
    "Cage du domicile inviolée": `${d} n'encaisse aucun but`, "Le domicile encaisse": `${d} encaisse au moins 1 but`,
    "Cage de l'extérieur inviolée": `${e} n'encaisse aucun but`, "L'extérieur encaisse": `${e} encaisse au moins 1 but`,
    "1:0 / 2:0 / 3:0": `${d} gagne 1-0, 2-0 ou 3-0`, "2:1 / 3:1 / 4:1": `${d} gagne 2-1, 3-1 ou 4-1`,
    "0:1 / 0:2 / 0:3": `${e} gagne 1-0, 2-0 ou 3-0 (scores 0-1, 0-2, 0-3)`, "1:2 / 1:3 / 1:4": `${e} gagne 2-1, 3-1 ou 4-1 (scores 1-2, 1-3, 1-4)`,
  };
  if (fixes[m]) return fixes[m];
  if ((r = m.match(/^Multigoals (\d+)-(\d+)$/))) return `Entre ${r[1]} et ${r[2]} buts dans le match`;
  if ((r = m.match(/^(Plus|Moins) de ([\d,]+) buts( du domicile| de l'extérieur)?$/))) {
    const L = nombre(r[2]), n = auMoins(L), plus = r[1] === "Plus";
    if (!r[3]) return plus ? `Au moins ${butsN(n)} dans le match` : n - 1 === 0 ? "Aucun but dans le match" : `${butsN(n - 1)} au maximum dans le match`;
    const eq = r[3].trim() === "du domicile" ? d : e;
    return plus ? `${eq} marque au moins ${butsN(n)}` : n - 1 === 0 ? `${eq} ne marque pas` : `${eq} marque ${butsN(n - 1)} au maximum`;
  }
  if ((r = m.match(/^Handicap ([+\-−]?[\d,]+) (domicile|extérieur)$/))) {
    const L = nombre(r[1].replace("−", "-")), eq = r[2] === "domicile" ? d : e;
    return `${sensHandicap(L, eq)} (handicap ${r[1]})`;
  }
  if ((r = m.match(/^Exactement (\d+)(\+)? buts$/))) return r[2] ? `${butsN(Number(r[1]))} ou plus dans le match` : `Exactement ${butsN(Number(r[1]))} dans le match`;
  if ((r = m.match(/^Score exact (\d+)-(\d+)$/))) return `Score exact : ${d} ${r[1]}-${r[2]} ${e}`;
  return m;
}

// Marchés d'un onglet (= catégorie) : classés à l'intérieur de la catégorie seulement (af-alpha-selection.js).
const lignesDe = (m, cat) => lignesCategorie(m, cat);
const pluriel = (n, mot) => `${n} ${mot}${n > 1 ? "s" : ""}`;
const detailBranches = (cle, s) => (cle === "calibrees"
  ? `gagné ${formatPct(s.reussite_test_final)} des fois au test sur matchs jamais vus (${formatPct(s.reussite_sans_filtre)} sans le filtre)`
  : cle === "multiscores"
  ? `arrivé dans ${Number(s.scenarios)} des ${Number(s.sur)} comparaisons de matchs`
  : `buts marqués ${formatPct(s.offensive)} · buts encaissés ${formatPct(s.defensive)}`);

// ── Carte dépliée : une ligne par marché (nom, valeur, cote, branches, alerte) ──
function ligneMarche(cle, s, m) {
  const pct = Number.isFinite(Number(s.valeur)) && s.valeur !== null ? Math.max(0, Math.min(100, Math.round(Number(s.valeur) * 100))) : null;
  const barre = pct === null ? "" : `<span class="ax-mk-barre" aria-hidden="true"><i style="--v:${pct}"></i></span>`;
  const cote = aUneCote(s.cote)
    ? `<span class="ax-mk-cote"><small>Cote</small><strong>${formatCote(s.cote)}</strong></span>`
    : `<span class="ax-mk-cote ax-mk-cote-lire"><small>Cote</small><strong>à lire</strong></span>`;
  const branches = cle === "calibrees"
    ? `<span>Gagné <b>${formatPct(s.reussite_test_final)}</b> des fois sur <b>${Number(s.paris_test_final)}</b> matchs jamais vus</span><span>Sans le filtre : <b>${formatPct(s.reussite_sans_filtre)}</b></span>`
    : cle === "multiscores"
    ? `<span>Arrivé dans <b>${Number(s.scenarios)}</b> des <b>${Number(s.sur)}</b> comparaisons de matchs</span>`
    : `<span>Sur les buts marqués : <b>${formatPct(s.offensive)}</b></span><span>Sur les buts encaissés : <b>${formatPct(s.defensive)}</b></span>`;
  const alerte = s.alerte ? `<p class="ax-mk-alerte"><span aria-hidden="true">⚠</span> ${echappeHtml(s.alerte)}</p>` : "";
  return `<li class="ax-mk"><span class="ax-mk-nom">${afMarcheHtml(s.marche, libelleClair(s.marche, m.domicile, m.exterieur))}</span>${cote}` +
    `<div class="ax-mk-valeur">${barre}<b>${formatPct(s.valeur)}</b><small>${cle === "calibrees" ? "réussite" : "valeur"}</small></div>` +
    `<p class="ax-mk-branches">${branches}</p>${alerte}</li>`;
}

function liste(cle, lignes, m) {
  if (!lignes.length) return `<p class="ax-texte-resume">Aucun marché retenu dans cet onglet pour ce match.</p>`;
  const legende = cle === "calibrees"
    ? "Calibrés : marchés dont la règle a été réglée sur plus de 10 000 matchs passés puis confirmée sur des matchs jamais vus. Le pourcentage est la réussite observée à ce test ; il gagne plus souvent que sans le filtre, mais aucune rentabilité n'est démontrée face à la cote."
    : cle === "multiscores"
    ? "Valeur : part des comparaisons de matchs où ce résultat est arrivé, ajustée à la taille de l'échantillon. Plus elle est haute, plus le résultat est fréquent dans les derniers matchs des deux équipes."
    : "Valeur : part des comparaisons de matchs où ce résultat est arrivé (moyenne « buts marqués » et « buts encaissés », ajustée à la taille de l'échantillon). Plus elle est haute, plus le résultat est fréquent dans les derniers matchs des deux équipes.";
  return `<ul class="ax-mk-liste">${lignes.map((s) => ligneMarche(cle, s, m)).join("")}</ul><p class="ax-mk-legende">${legende}</p>`;
}

// ── Carte repliée : chaque catégorie montre SON meilleur marché, indépendamment des autres ──
// Buts, Équipes, Calibrés : affiché seulement si sa cote BetPawa est connue, sinon catégorie masquée (aucun marché inférieur en remplacement).
// Multigoals, Multiscores : affichés même sans cote (cote facultative).
function construitResume(m) {
  const racine = document.createElement("div");
  racine.className = "ax-resume";
  CATEGORIES_ALPHA.forEach((cat, i) => {
    const s = meilleurAffichable(m, cat);
    if (!s) return;
    const cle = cat.source, nom = cat.nom, l = lignesDe(m, cat);
    const plus = l.length > 1 ? `<span class="ax-resume-plus"> · +${l.length - 1} autre${l.length > 2 ? "s" : ""}</span>` : "";
    const cote = aUneCote(s.cote) ? `<strong>${formatCote(s.cote)}</strong>` : `<strong class="ax-cote-lire">facultative</strong>`;
    const alerte = s.alerte ? `<p class="ax-resume-alerte"><span aria-hidden="true">⚠</span> ${echappeHtml(s.alerte)}</p>` : "";
    const rang = document.createElement("div");
    rang.className = `ax-resume-rang ax-rang-${Math.min(i + 1, 3)}`;
    rang.innerHTML = `<div class="ax-resume-corps"><div class="ax-resume-tete">` +
      `<span class="ax-resume-etiquette">${nom}${plus}</span><span class="ax-resume-cote">Cote${cote}</span></div>` +
      `<p class="ax-resume-marche">${afMarcheHtml(s.marche, libelleClair(s.marche, m.domicile, m.exterieur))}</p>` +
      `<p class="ax-resume-texte">${cle === "calibrees" ? "Réussite" : "Valeur"} <b>${formatPct(s.valeur)}</b> · ${detailBranches(cle, s)}</p>${alerte}</div>`;
    racine.appendChild(rang);
  });
  return racine;
}

function remplitDetails(details, m) {
  const sc = (l) => (l || []).map(([h, a]) => `${Number(h)}-${Number(a)}`).join(" · ");
  const rej = (m.rejetes || []).map((r) => `<li><strong>${echappeHtml(libelleClair(r.marche, m.domicile, m.exterieur))}</strong> — ${echappeHtml(r.raison)}</li>`).join("");
  const niv = m.niveaux ? `Buts attendus : domicile ${Number(m.niveaux.dom).toFixed(2)}, extérieur ${Number(m.niveaux.ext).toFixed(2)}, total ${Number(m.niveaux.total).toFixed(2)}. ` : "";
  details.innerHTML = `<summary class="ax-summary-cache" tabindex="-1">Détails de l'analyse</summary><div class="ax-details-corps">` +
    `<div class="ax-tab"><h4 class="ax-tab-titre">Scénarios appariés (${Number(m.n_domicile)} matchs à domicile, ${Number(m.n_exterieur)} à l'extérieur, k = ${Number(m.k)})</h4>` +
    `<p class="ax-preuve-texte">${niv}</p><p class="ax-preuve-texte">Offensive : ${sc(m.scenarios_offensifs)}</p><p class="ax-preuve-texte">Défensive : ${sc(m.scenarios_defensifs)}</p></div>` +
    `<div class="ax-tab"><h4 class="ax-tab-titre">Marchés exclus et raison</h4><ul class="ax-v3-lignes">${rej || "<li>Aucun</li>"}</ul></div></div>`;
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
  const actifs = CATEGORIES_ALPHA.map((cat, i) => {
    const cle = cat.source, nom = cat.nom;
    const lignes = lignesDe(m, cat);
    const idO = `ax-onglet-${id}-${i}`, idP = `ax-panneau-${id}-${i}`;
    const bouton = document.createElement("button");
    bouton.type = "button"; bouton.id = idO; bouton.className = `ax-onglet ax-rang-${Math.min(i + 1, 3)}${lignes.length ? "" : " ax-vide"}`;
    bouton.setAttribute("role", "tab"); bouton.setAttribute("aria-controls", idP);
    bouton.innerHTML = `<span>${nom} (${lignes.length})</span>`;
    onglets.appendChild(bouton);
    const panneau = document.createElement("div");
    panneau.className = `ax-panneau ax-rang-${Math.min(i + 1, 3)}`; panneau.id = idP; panneau.setAttribute("role", "tabpanel"); panneau.setAttribute("aria-labelledby", idO);
    panneau.hidden = true;
    panneaux.appendChild(panneau);
    return { cle, bouton, panneau, lignes, n: lignes.length };
  });
  const blocDetails = document.createElement("details");
  blocDetails.className = "details-analyse ax-details"; blocDetails.id = idDetails;
  section.appendChild(onglets); section.appendChild(construitResume(m)); section.appendChild(panneaux); section.appendChild(blocDetails);

  // Le contenu lourd (listes de marchés, registre des exclus) n'est construit qu'au premier dépliage : la page reste fluide sur téléphone.
  let pret = false;
  const prepare = () => {
    if (pret) return;
    pret = true;
    actifs.forEach(({ cle, panneau, lignes }) => { panneau.innerHTML = liste(cle, lignes, m); });
    remplitDetails(blocDetails, m);
  };
  let courant = (actifs.find((a) => a.n) || actifs[0]);
  const applique = (replie) => {
    if (!replie) prepare();
    section.classList.toggle("ax-replie", replie);
    section.setAttribute("aria-expanded", String(!replie));
    actifs.forEach((a) => {
      const oui = !replie && a === courant;
      a.bouton.classList.toggle("ax-actif", oui); a.bouton.setAttribute("aria-selected", String(oui));
      a.bouton.tabIndex = a === courant ? 0 : -1; a.panneau.hidden = !oui;
    });
  };
  // Une pression sur un onglet déplie la carte sur cet onglet (avant : la carte restait fermée et rien ne se passait).
  actifs.forEach((a) => a.bouton.addEventListener("click", () => { courant = a; applique(false); }));

  const pied = document.createElement("div");
  pied.className = "ax-pied";
  const boutonReplier = document.createElement("button");
  boutonReplier.type = "button"; boutonReplier.className = "ax-bouton-replier"; boutonReplier.textContent = "Replier";
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
  // Bascule en gardant l'en-tête du match au même endroit de l'écran ; en repliant, on remonte à l'en-tête s'il est sorti de l'écran.
  const bascule = (replie) => {
    const avant = section.getBoundingClientRect().top;
    applique(replie);
    const apres = section.getBoundingClientRect().top;
    if (Math.abs(apres - avant) > 1) window.scrollBy(0, apres - avant);
    const haut = section.getBoundingClientRect().top;
    if (replie && haut < 0) window.scrollBy(0, haut - 8);
  };
  boutonReplier.addEventListener("click", (e) => { e.stopPropagation(); bascule(true); });
  section.addEventListener("click", (e) => {
    if (e.target.closest("button, a, summary, [role=tab], .ax-mk-liste, .ax-details")) return;
    const sel = window.getSelection && window.getSelection();
    if (sel && String(sel).length) return;
    bascule(!section.classList.contains("ax-replie"));
  });
  applique(true);
  pied.appendChild(boutonReplier); pied.appendChild(boutonDetails); section.appendChild(pied);
  return section;
}

// ── Bilan réel : trois pastilles lisibles d'un coup d'œil (avant : une longue phrase grise) ──
function afficheBilan(b, perf) {
  if (!perf) return;
  const tuiles = b ? BILAN_ONGLETS.map(([c, nom]) => {
    const o = (b.onglets || {})[c];
    return o && o.cas ? `<div class="ax-perf-tuile"><span class="ax-perf-nom">${nom}</span><strong>${formatPct(o.reussite)}</strong><small>sur ${Number(o.cas)} cas</small></div>` : "";
  }).join("") : "";
  perf.innerHTML = tuiles
    ? `<p class="ax-perf-titre">Réussite réelle — pronostics gelés avant le match</p><div class="ax-perf-grille">${tuiles}</div><p class="ax-perf-note">Aucune rentabilité démontrée.</p>`
    : `<p class="ax-perf-note">Aucun résultat sur des pronostics gelés pour l'instant : la réussite réelle s'affichera ici. Aucune rentabilité démontrée.</p>`;
}

function afficheSelections(d) {
  const racine = document.getElementById("matches"), maj = document.getElementById("maj"), perf = document.getElementById("perf");
  const jour = aujourdhui();
  const cleTri = (m) => `${m.date || ""}${m.heure || ""}`;
  const aUnMarche = (m) => carteAffichable(m);              // au moins une catégorie affichable selon la règle d'affichage
  const retenus = (d.matchs || []).filter((m) => m.statut === "analyse" && m.date >= jour && aUnMarche(m)).sort((a, b) => cleTri(a).localeCompare(cleTri(b)));
  maj.innerHTML = retenus.length
    ? `<strong>${pluriel(retenus.length, "match")}</strong> avec au moins un marché affichable · cote BetPawa obligatoire (sauf multigoals et multiscores), minimum ${formatCote(d.cote_min)}`
    : "Aucun pronostic pour le moment";
  afficheBilan(d.bilan_gele, perf);
  racine.innerHTML = "";
  if (!retenus.length) {
    racine.innerHTML = `<div class="ax-etat-vide"><strong>Aucun pronostic pour le moment</strong>` +
      `<p>Aucun match à venir n'a de marché affichable (meilleur marché de chaque catégorie avec cote BetPawa connue, ou multigoal / multiscore).</p></div>`;
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
