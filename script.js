// script.js — Module 4, hiérarchie visuelle à 5 niveaux (25/08) :
// 1. identification (équipes/compétition) 2. statut (verdict, texte +
// couleur, jamais couleur seule) 3. donnée principale (p(1), plus grosse
// taille de l'écran) 4. détails (paris, risques) 5. action secondaire
// (détail N1/N2, repliée par défaut).

// AJOUT 06/09/2026 (bug #27) -- échappe le texte inséré dans du HTML
// construit par concaténation de chaînes (les fonctions construit*
// ci-dessous). Choix délibéré, différent de la reformulation littérale de
// l'audit ("textContent/construction DOM") : une conversion complète de
// tout ce fichier en construction DOM nœud par nœud est un chantier bien
// plus large que ce que l'audit qualifiait de "peu coûteux" -- ce module
// est un arbre de ~10 fonctions imbriquées qui se passent du HTML en
// chaîne. echappeHtml() neutralise le même vecteur (impossible d'injecter
// une balise/script actif) avec un risque de régression bien moindre sur
// un rendu déjà complexe. Appliqué à toute valeur qui peut transporter du
// texte scrapé/généré (domicile, extérieur, compétition, raison,
// justification) -- jamais aux nombres déjà formatés (toFixed/formatPct),
// qui ne peuvent pas contenir de balise par construction.
function echappeHtml(texte) {
  if (texte === null || texte === undefined) return "";
  return String(texte)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

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

function formatPct(x) {
  const pct = x * 100;
  // AJOUT 05/09/2026 -- une proba comme 0.9995 à 0.99999 arrondissait à
  // "100.0%", donnant une fausse impression de certitude absolue alors
  // que le modèle ne l'affirme jamais vraiment à 100% pile. Plafonné à
  // 99.9% tant que ce n'est pas EXACTEMENT 1.0.
  if (pct >= 99.95 && x < 1) return "99.9%";
  return pct.toFixed(1) + "%";
}

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
  // AJOUT (04/09/2026 soir) -- colonne "proba" de ce tableau de détail
  // affiche désormais l'ajustée, cohérent avec la colonne "ev" juste à
  // côté (qui, elle, reflétait déjà la version corrigée malgré son nom
  // "ev_brut" -- voir run_pipeline.py). Repli sur la brute si absente.
  const lignes = listeA.map(c => `<tr>
    <td>${echappeHtml(c.marche)}</td><td>${c.cote_observee.toFixed(2)}</td>
    <td>${formatPct(c.probabilite_modele_ajustee ?? c.probabilite_modele)}</td><td>${formatPct(c.ev_brut)}</td>
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
    <summary><span class="texte-ferme">voir les détails</span><span class="texte-ouvert">masquer les détails</span></summary>
    ${construitBlocPourquoi(m)}
    <p class="detail-sous-titre">marchés évalués avant filtre de corrélation</p>
    ${construitTableListeA(m.LISTE_A_marches_passant_EV_et_cote)}
    ${construitAutresMarches(m.marches)}
  </details>`;
}

function construitNiveau3(m) {
  if (m.verdict_global !== "GO") return "";
  const listeB = m.LISTE_B_liste_finale_apres_correlation;
  if (!listeB || listeB.length === 0) return "";
  const pariEnOr = [...listeB].sort((a, b) => b.probabilite_modele - a.probabilite_modele)[0];

  const cat = categorieMarche(pariEnOr.marche);
  const stats = roiDashboardCharge?.par_marche?.[cat];
  const assezDeRecul = stats && stats.nb_paris >= SEUIL_MIN_PARIS_POUR_TAUX_REEL;

  // REFAIT 05/09/2026 -- avant, le badge et l'explication étaient deux
  // blocs indépendants, chacun avec son propre repli "pas de données" --
  // sur un pari sans historique de marché ET sans preuve de justification,
  // ça affichait DEUX phrases vagues qui se répétaient (retour utilisateur :
  // "incompréhensible, très mal formulé"). Un seul bloc maintenant, un seul
  // message par situation, texte en couleur principale (pas grisé) pour la
  // partie qui compte vraiment.
  let badge;
  if (assezDeRecul) {
    badge = `<div class="proba-1">
      ${stats.taux_reussite_pct.toFixed(1)}%
      <span class="proba-1-label">de réussite sur les ${stats.nb_paris} derniers paris du type "${echappeHtml(cat)}" (${stats.nb_gagnes} gagnés) — pari recommandé ici : ${echappeHtml(pariEnOr.marche)}</span>
    </div>`;
  } else {
    const nb = stats ? stats.nb_paris : 0;
    badge = `<div class="proba-1 proba-1-insuffisant">
      pas assez de recul
      <span class="proba-1-label">seulement ${nb} pari(s) "${echappeHtml(pariEnOr.marche)}" enregistré(s) jusqu'ici (il en faut au moins ${SEUIL_MIN_PARIS_POUR_TAUX_REEL})</span>
    </div>`;
  }

  return `${badge}
  ${construitBlocJustification(m, pariEnOr)}`;
}

// AJOUT 04/09/2026 (soir) -- rendu du vrai moteur de justification
// (moteur_justification.py + adapte_justification.py), qui remplace le
// résumé technique "cote/ev/confiance" par des faits statistiques réels
// (fréquences comptées sur l'historique réel, jamais inventées -- voir
// adapte_justification.py). m.justification est None si le marché
// recommandé n'a pas de preuve fiable construite pour lui (Handicap, Score
// exact -- voir en-tête d'adapte_justification.py) ou si le match a été
// archivé avant ce correctif -- repli sur l'ancien résumé dans ce cas,
// pour ne jamais laisser un GO sans aucune explication affichée.
function construitBlocJustification(m, pariEnOr) {
  const j = m.justification;
  if (!j || !j.justifications || j.justifications.length === 0) {
    // REFAIT 05/09/2026 -- l'ancien texte ("pourquoi ce pari : cote X, ev Y,
    // confiance Z...") était un jargon technique redondant avec le badge
    // juste au-dessus. Remplacé par une seule ligne factuelle et courte.
    return `<p class="pourquoi-pari">
      Cote ${pariEnOr.cote_observee.toFixed(2)} · ${m.nb_matchs_domicile_utilises ?? "?"} matchs domicile
      et ${m.nb_matchs_exterieur_utilises ?? "?"} matchs extérieur analysés pour ce pronostic.
    </p>`;
  }
  const lignes = j.justifications
    .map(just => `<li class="justification-ligne">${echappeHtml(just.texte)}</li>`)
    .join("");
  const solidite = j.solidite_donnees
    ? `<p class="justification-solidite">Basé sur : ${echappeHtml(j.solidite_donnees)}</p>`
    : "";
  return `<div class="bloc-justification">
    <p class="justification-titre">${echappeHtml(j.titre)}</p>
    <ul class="justification-liste">${lignes}</ul>
    ${solidite}
  </div>`;
}

const SUPABASE_URL = "https://hjrcqodwfjxqcjvjoxzq.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhqcmNxb2R3Zmp4cWNqdmpveHpxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgxMTU3NjUsImV4cCI6MjEwMzY5MTc2NX0.rxJ2W-2UI0oQrGAprqnrPJM3WO1HCoYft0ZeS38oZfY";
const SUPABASE_CONFIGURE = !SUPABASE_URL.includes("TON-PROJET") && !!window.supabase;
const supabaseClient = SUPABASE_CONFIGURE ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;

const DELAI_ATTENTE_MS = 15000;
const INTERVALLE_RAFRAICHISSEMENT_MS = 20000;
const NB_RAFRAICHISSEMENTS_MAX = 15;
// AJOUT 06/09/2026 (bug #24) -- même clé que panier.js, voir son
// commentaire pour le détail. Lue ici, jamais écrite -- seul panier.js
// écrit cette clé, sur un envoi réellement accepté.
const CLE_DERNIER_PANIER_ID = "archetype_dernier_panier_id";

function afficheErreur(message) {
  document.getElementById("maj").textContent = "erreur de chargement : " + message;
}

// AJOUT 10/09/2026 (correctif urgent) -- jusqu'ici, "retenu" ne voulait dire
// qu'une seule chose : verdict_global === "GO" (ancien moteur). Un match où
// archetype_model trouve un P1 réel mais où l'ancien moteur dit NO_GO était
// invisible sur cette page (trié en bas, masqué par le filtre GO, badgé
// "✕ NO_GO" à tort) -- alors que la donnée elle-même était correcte, voir
// script.js::construitBlocArchetypeModel. Ne remplace RIEN de l'ancien
// moteur, ajoute seulement un second critère de "retenu".
function estArchetypeGo(m) {
  return m.moteur_utilise === "archetype_model"
    && m.archetype_model
    && m.archetype_model.statut === "OK"
    && !!(m.archetype_model.selection && m.archetype_model.selection.P1);
}

function meilleurEv(m) {
  if (m.verdict_global !== "GO") return -Infinity;
  const listeB = m.LISTE_B_liste_finale_apres_correlation;
  if (!listeB || listeB.length === 0) return -Infinity;
  return Math.max(...listeB.map((p) => p.ev_brut));
}

function trieEtFiltre(matchs) {
  const copie = [...(matchs || [])];
  copie.sort((a, b) => {
    const rangA = (a.verdict_global === "GO" || estArchetypeGo(a)) ? 0 : (a.traite ? 1 : 2);
    const rangB = (b.verdict_global === "GO" || estArchetypeGo(b)) ? 0 : (b.traite ? 1 : 2);
    if (rangA !== rangB) return rangA - rangB;
    if (rangA === 0) return meilleurEv(b) - meilleurEv(a);
    return 0;
  });
  const filtreGo = document.getElementById("filtre-go");
  if (filtreGo && filtreGo.checked) {
    return copie.filter((m) => m.verdict_global === "GO" || estArchetypeGo(m));
  }
  return copie;
}

// 03/09/2026 -- extrait de afficheMatchs() pour être réutilisable par la
// vue "par catégorie" (afficheMatchsGroupe) sans dupliquer le HTML d'une
// carte. Comportement strictement identique à avant.
// AJOUT 09/09/2026 (reprise de session) -- affichage TEMPORAIRE et
// TOLÉRANT du nouveau moteur (archetype_model), en PLUS de l'affichage
// existant de l'ancien moteur ci-dessus (jamais remplacé, jamais masqué,
// jamais modifié) -- objectif unique : permettre à Patrick de VÉRIFIER
// par comparaison visuelle sur un vrai run avant toute bascule
// définitive (voir precalcul.py::applique_archetype_model et sa règle de
// fallback -- erreur technique uniquement, jamais une décision métier).
//
// Ce bloc ne doit JAMAIS faire planter une carte si les champs sont
// absents (matchs archivés avant ce correctif, ou match jamais tenté par
// archetype_model, ex. traite=false côté ancien moteur) -- tout est lu
// avec des valeurs par défaut explicites, jamais une supposition sur la
// structure de m.archetype_model.
function construitBlocArchetypeModel(m) {
  const moteur = m.moteur_utilise;
  if (!moteur) return ""; // rien à afficher pour un match jamais passé par ce correctif

  const formatPctSur = (x) => (x !== null && x !== undefined ? formatPct(x) : "?");

  let contenu = `<div class="am-ligne am-moteur">moteur utilisé : <strong>${echappeHtml(moteur)}</strong></div>`;

  if (moteur === "ancien (fallback technique)") {
    const erreur = m.archetype_model_erreur || "raison non précisée";
    contenu += `<div class="am-ligne am-erreur">archetype_model indisponible sur ce match : ${echappeHtml(erreur)}</div>`;
  } else {
    const am = m.archetype_model;
    if (am) {
      contenu += `<div class="am-ligne">statut archetype_model : ${echappeHtml(am.statut || "?")}</div>`;
      const selection = am.selection;
      if (selection) {
        ["P1", "P2", "P3"].forEach((rang) => {
          const c = selection[rang];
          contenu += c
            ? `<div class="am-ligne am-candidat">${rang} : ${echappeHtml(c.marche)}` +
              ` (niveau ${echappeHtml(c.niveau || "?")}, edge ${formatPctSur(c.edge)}, edv ${formatPctSur(c.edv)},` +
              ` H2H ${echappeHtml(c.h2h_palier || "?")})</div>`
            : `<div class="am-ligne am-candidat-vide">${rang} : aucun</div>`;
        });
      }
    }
  }

  return `<details class="details-niveau1 am-bloc">
    <summary><span class="texte-ferme">voir archetype_model (nouveau moteur, vérification)</span><span class="texte-ouvert">masquer archetype_model</span></summary>
    ${contenu}
  </details>`;
}

function construitCarteMatch(m) {
  const div = document.createElement("div");
  div.className = "match";

  // AJOUT 03/09/2026 -- date exacte + heure sur chaque carte, en plus du
  // regroupement par onglet (demande de Patrick) : utile notamment en vue
  // "par catégorie", où les cartes de plusieurs championnats se suivent
  // sans repère de date visible ailleurs que l'onglet actif.
  // AJOUT (04/09/2026 soir) -- heureAffichee préfère heure_cameroun
  // (Africa/Douala) sur m.heure brute (France) -- voir scraper.py. Repli
  // sur m.heure pour les statuts en direct ("83'", "MT"...), qui n'ont
  // jamais de heure_cameroun.
  const heureAffichee = m.heure_cameroun || m.heure || "";
  const dateAffichee = m.date ? dateLisible(m.date) : "";
  const dateHeure = dateAffichee
    ? `${dateAffichee}${heureAffichee ? " à " + heureAffichee : ""}${m.heure_cameroun ? " (heure Cameroun)" : ""}`
    : "";

  let html = `
    <div class="teams"><span>${echappeHtml(m.domicile)}</span><span>${echappeHtml(m.score || heureAffichee || "")}</span><span>${echappeHtml(m.exterieur)}</span></div>
    <div class="meta">${echappeHtml((m.competition || "").replace(/\s+/g, " ").trim())}${dateHeure ? " — " + echappeHtml(dateHeure) : ""}</div>
  `;

  if (!m.traite) {
    html += `<div class="signal-non-traite">non analysé — ${echappeHtml(traduireRaison(m.raison_non_traite))}</div>`;
  } else {
    const estGo = m.verdict_global === "GO";
    const estArchGo = !estGo && estArchetypeGo(m);
    const classeBadge = estGo ? "badge-go" : (estArchGo ? "badge-archetype" : "badge-nogo");
    const texteBadge = estGo ? "✓ GO" : (estArchGo ? "★ ARCHETYPE" : "✕ NO_GO");
    html += `<div class="ligne-verdict">
      <span class="badge ${classeBadge}">${texteBadge}</span>
    </div>`;
    html += construitNiveau3(m);
    if (!estGo && m.motif_no_go) {
      html += `<div class="motif-no-go">${echappeHtml(m.motif_no_go)}</div>`;
    }
    if (estGo) {
      html += construitBlocParisRecommandes(m.LISTE_B_liste_finale_apres_correlation);
    }
    html += construitBlocRisques(m);
    html += construitDetails(m);
  }

  html += construitBlocArchetypeModel(m);

  div.innerHTML = html;
  return div;
}

function afficheMatchs(matchs, enTete) {
  document.getElementById("maj").textContent = enTete;

  const container = document.getElementById("matches");
  container.className = "grille";
  container.innerHTML = "";
  if (!matchs || matchs.length === 0) {
    container.innerHTML = "<p>aucun résultat pour le moment.</p>";
    return;
  }

  matchs.forEach((m) => {
    container.appendChild(construitCarteMatch(m));
  });
}

// 03/09/2026 -- vue "par catégorie" : mêmes cartes que afficheMatchs(),
// mais regroupées sous un en-tête par championnat, sur le même principe
// que le regroupement déjà utilisé sur l'accueil (index.js). L'ordre
// GO-d'abord de trieEtFiltre() n'a pas de sens ici (on parcourt par
// championnat, pas par pertinence) -- tri alphabétique du championnat,
// puis par heure de coup d'envoi à l'intérieur d'un même championnat.
function groupeParCompetition(matchs) {
  const copie = [...matchs];
  copie.sort((a, b) => {
    const ca = (a.competition || "").replace(/\s+/g, " ").trim();
    const cb = (b.competition || "").replace(/\s+/g, " ").trim();
    if (ca !== cb) return ca.localeCompare(cb, "fr");
    return (a.heure || "").localeCompare(b.heure || "");
  });
  return copie;
}

function afficheMatchsGroupe(matchs, enTete) {
  document.getElementById("maj").textContent = enTete;

  const container = document.getElementById("matches");
  container.className = "";
  container.innerHTML = "";
  if (!matchs || matchs.length === 0) {
    container.innerHTML = "<p>aucun résultat pour le moment.</p>";
    return;
  }

  const groupes = groupeParCompetition(matchs);
  let competitionCourante = null;
  let sousConteneur = null;

  groupes.forEach((m) => {
    const nomCompetition = (m.competition || "compétition inconnue").replace(/\s+/g, " ").trim();
    if (nomCompetition !== competitionCourante) {
      competitionCourante = nomCompetition;
      const entete = document.createElement("div");
      entete.className = "entete-categorie";
      entete.textContent = nomCompetition;
      container.appendChild(entete);
      sousConteneur = document.createElement("div");
      sousConteneur.className = "grille";
      container.appendChild(sousConteneur);
    }
    sousConteneur.appendChild(construitCarteMatch(m));
  });
}

let jetonAffichage = 0;
let dernierEnsembleBrut = [];
let dernierEnTeteBase = "";
let modeAffichage = "liste"; // 03/09/2026 -- "liste" ou "categorie"

function reaffiche() {
  const trie = trieEtFiltre(dernierEnsembleBrut);
  const nbGo = dernierEnsembleBrut.filter((m) => m.verdict_global === "GO").length;
  const nbArchGo = dernierEnsembleBrut.filter((m) => m.verdict_global !== "GO" && estArchetypeGo(m)).length;
  const enTete = `${dernierEnTeteBase} — ${nbGo} GO${nbArchGo ? ` + ${nbArchGo} ARCHETYPE` : ""}`;
  if (modeAffichage === "categorie") {
    afficheMatchsGroupe(trie, enTete);
  } else {
    afficheMatchs(trie, enTete);
  }
}

const FORMAT_DATE_ONGLET = { weekday: "short", day: "numeric", month: "short" };

function dateIsoDansNJours(n) {
  // CORRECTIF FUSEAU HORAIRE 04/09/2026 -- toISOString() convertit en UTC
  // avant de lire la date, ce qui décale la date locale française de -1
  // jour entre 22h00 et 00h00 UTC (0h-2h heure française l'été). Le
  // pipeline calcule désormais "aujourd'hui" en heure française
  // (aujourdhui_france() côté serveur, precalcul.py) -- ce front-end doit
  // faire pareil, sinon les onglets afficheraient parfois un jour
  // différent de celui réellement servi par precalcul_leger.json.
  const fmt = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Paris" });
  const [an, mois, jour] = fmt.format(new Date()).split("-").map(Number);
  const d = new Date(Date.UTC(an, mois - 1, jour));
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

function dateLisible(dateIso) {
  const [an, mois, jour] = dateIso.split("-").map(Number);
  return new Date(an, mois - 1, jour).toLocaleDateString("fr-FR", FORMAT_DATE_ONGLET);
}

// AJOUT 03/09/2026 -- j0 (aujourd'hui) rejoint la fenêtre affichée, en plus
// de j1/j2/j3 -- voir precalcul.py (charge_matchs_fenetre) pour le
// changement côté données : ce fichier n'avait rien à changer sur le fond,
// DATES_FENETRE et le tableau d'onglets ci-dessous étaient déjà génériques.
const DATES_FENETRE = {
  j0: dateIsoDansNJours(0),
  j1: dateIsoDansNJours(1),
  j2: dateIsoDansNJours(2),
  j3: dateIsoDansNJours(3),
};

// Libellé affiché sur le bouton et dans l'en-tête -- "Aujourd'hui" est plus
// lisible que "J0" pour l'utilisateur, contrairement à j1/j2/j3 qui restent
// tels quels.
const LIBELLE_ONGLET = { j0: "Aujourd'hui", j1: "J+1", j2: "J+2", j3: "J+3" };

let precalculCharge = null;

// AJOUT 05/09/2026 -- vraies performances mesurées (roi_dashboard.json,
// calcule_roi.py), pour remplacer le badge de probabilité du MODÈLE
// (jamais fiable -- voir TRANSITION.md : gagnants 0.84 vs perdants 0.79
// de probabilité annoncée, à peine 5 points d'écart) par le vrai taux de
// réussite mesuré sur les paris déjà résolus. Chargé une fois, en
// parallèle du reste -- un échec ici ne doit jamais bloquer l'affichage
// des pronostics, juste faire retomber sur "pas encore assez de données".
let roiDashboardCharge = null;
async function chargeRoiDashboard() {
  try {
    const r = await fetch("roi_dashboard.json?_=" + Date.now());
    if (!r.ok) return;
    roiDashboardCharge = await r.json();
    reaffiche();
  } catch (err) {
    console.error("roi_dashboard.json indisponible -- vrais taux masqués, sans impact sur le reste :", err);
  }
}

// Port JS EXACT de categorie_marche() (calcule_roi.py) -- ne jamais avoir
// deux définitions différentes du même regroupement de marché dans le
// dépôt (même piège que celui déjà évité dans adapte_justification.py).
function categorieMarche(marche) {
  if (!marche) return "inconnu";
  const prefixe = marche.split(" - ")[0];
  const SANS_LIGNE_VARIABLE = ["1X2", "Double chance", "BTTS", "Total buts", "Cage inviolée", "Encaisse au moins 1 but"];
  if (SANS_LIGNE_VARIABLE.includes(prefixe)) return prefixe;
  return prefixe.replace(/\d+(\.\d+)?/g, "N").trim();
}

// Nombre minimum de paris résolus avant d'afficher un taux -- sous ce
// seuil, un "100%" sur 1 ou 2 paris serait aussi trompeur que le badge de
// probabilité qu'on retire. Pas de valeur "scientifique" ici, juste évite
// l'exemple le plus flagrant (voir TRANSITION.md, fragilité déjà démontrée
// sur de petits échantillons lors du calibrage K_SHRINKAGE).
const SEUIL_MIN_PARIS_POUR_TAUX_REEL = 15;

// CHANGÉ 02/09/2026 -- fetch precalcul_leger.json (sans marches/lambda) au
// lieu de precalcul.json (9,2 Mo au 02/09) -- voir precalcul.py pour le détail.
async function chargePrecalcul() {
  if (precalculCharge) return precalculCharge;
  const r = await fetch("precalcul_leger.json?_=" + Date.now());
  if (!r.ok) throw new Error(`precalcul_leger.json introuvable (status ${r.status})`);
  precalculCharge = await r.json();
  return precalculCharge;
}

async function afficheOngletJour(cle, monJeton) {
  try {
    const data = await chargePrecalcul();
    if (monJeton !== jetonAffichage) return;
    const dateIso = DATES_FENETRE[cle];
    const signaux = (data.signaux || []).filter((s) => s.date === dateIso);
    const nbReady = signaux.filter((s) => s.traite).length;
    dernierEnsembleBrut = signaux;
    dernierEnTeteBase = `${LIBELLE_ONGLET[cle] || cle.toUpperCase()} — ${dateLisible(dateIso)} — ${nbReady}/${signaux.length} match(s) analysé(s) (mis à jour : ${data.genere_le || "inconnu"})`;
    reaffiche();
  } catch (err) {
    if (monJeton !== jetonAffichage) return;
    afficheErreur(err.message);
    console.error(err);
  }
}

async function chargeDepuisDataJson(monJeton) {
  const delaiDepasse = new Promise((_, reject) =>
    setTimeout(() => reject(new Error("délai dépassé (15s) -- vérifie ta connexion, ou que data.json existe bien à la racine du site.")), DELAI_ATTENTE_MS)
  );
  const r = await Promise.race([fetch("data.json?_=" + Date.now()), delaiDepasse]);
  const data = await r.json();
  if (monJeton !== jetonAffichage) return data.genere_le || null;
  dernierEnsembleBrut = data.matchs || [];
  dernierEnTeteBase = "mis à jour : " + (data.genere_le || "inconnu") + " — " + dernierEnsembleBrut.length + " match(s) traité(s)";
  reaffiche();
  return data.genere_le || null;
}

async function chargeDernierResultat(monJeton) {
  if (!SUPABASE_CONFIGURE) {
    return await chargeDepuisDataJson(monJeton);
  }

  const { data: { session } } = await supabaseClient.auth.getSession();
  if (monJeton !== jetonAffichage) return null;
  if (!session) {
    dernierEnsembleBrut = [];
    dernierEnTeteBase = "aucun panier envoyé depuis cet appareil pour le moment.";
    reaffiche();
    return null;
  }

  const delaiDepasse = new Promise((_, reject) =>
    setTimeout(() => reject(new Error("délai dépassé (15s) -- vérifie ta connexion.")), DELAI_ATTENTE_MS)
  );

  // CORRECTIF 06/09/2026 (bug #24) : avant, cette requête ne filtrait que
  // par user_id et prenait le résultat le plus récent TOUTES soumissions
  // confondues -- si une soumission plus ancienne finissait de se calculer
  // APRÈS une soumission plus récente, son résultat s'affichait à la
  // place du bon. panier_id (persisté par panier.js sur un envoi
  // réellement accepté) cible désormais précisément LE panier envoyé en
  // dernier depuis cet appareil, quand on le connaît. Repli sur l'ancien
  // comportement (dernier résultat toutes soumissions confondues) sinon --
  // ex. première visite sur cet appareil avant ce correctif, ou
  // localStorage vidé -- jamais un écran vide là où l'ancien comportement
  // affichait quelque chose.
  const panierIdActuel = localStorage.getItem(CLE_DERNIER_PANIER_ID);
  let requete = supabaseClient
    .from("resultats_pipeline")
    .select("data, created_at, panier_id")
    .eq("user_id", session.user.id);
  if (panierIdActuel) {
    requete = requete.eq("panier_id", panierIdActuel);
  }
  requete = requete.order("created_at", { ascending: false }).limit(1);

  const { data: lignes, error } = await Promise.race([requete, delaiDepasse]);
  if (monJeton !== jetonAffichage) return null;
  if (error) throw new Error(error.message);

  if (!lignes || lignes.length === 0) {
    dernierEnsembleBrut = [];
    dernierEnTeteBase = "aucun résultat pour le moment -- l'analyse est peut-être encore en cours.";
    reaffiche();
    return null;
  }

  const ligne = lignes[0];
  dernierEnsembleBrut = ligne.data || [];
  dernierEnTeteBase = "mis à jour : " + ligne.created_at + " — " + dernierEnsembleBrut.length + " match(s) traité(s)";
  reaffiche();
  return ligne.created_at;
}

let compteurRafraichissements = 0;
let ongletActif = "j0";

async function activeOngletPronostics(cle) {
  ongletActif = cle;
  jetonAffichage += 1;
  const monJeton = jetonAffichage;

  ["j0", "j1", "j2", "j3", "panier"].forEach((c) => {
    const bouton = document.getElementById("onglet-" + c);
    if (bouton) bouton.classList.toggle("actif", c === cle);
  });

  compteurRafraichissements = 0;
  if (cle === "panier") {
    await chargeDernierResultat(monJeton);
    if (SUPABASE_CONFIGURE) setTimeout(boucleRafraichissement, INTERVALLE_RAFRAICHISSEMENT_MS);
  } else {
    await afficheOngletJour(cle, monJeton);
  }
}

async function boucleRafraichissement() {
  if (ongletActif !== "panier" || !SUPABASE_CONFIGURE) return;
  const monJeton = jetonAffichage;
  try {
    await chargeDernierResultat(monJeton);
  } catch (err) {
    if (monJeton !== jetonAffichage) return;
    afficheErreur(err.message);
    console.error(err);
    return;
  }
  compteurRafraichissements += 1;
  if (compteurRafraichissements < NB_RAFRAICHISSEMENTS_MAX && monJeton === jetonAffichage) {
    setTimeout(boucleRafraichissement, INTERVALLE_RAFRAICHISSEMENT_MS);
  }
}

["j0", "j1", "j2", "j3", "panier"].forEach((cle) => {
  const bouton = document.getElementById("onglet-" + cle);
  if (!bouton) return;
  if (cle !== "panier") {
    bouton.textContent = `${LIBELLE_ONGLET[cle] || cle.toUpperCase()} — ${dateLisible(DATES_FENETRE[cle])}`;
  }
  bouton.addEventListener("click", () => activeOngletPronostics(cle));
});

const filtreGo = document.getElementById("filtre-go");
if (filtreGo) filtreGo.addEventListener("change", reaffiche);

// 03/09/2026 -- bascule liste complète / par catégorie. Ne recharge rien
// depuis le réseau : on retrie/regroupe l'ensemble déjà en mémoire
// (dernierEnsembleBrut), exactement comme le fait déjà le filtre GO.
["liste", "categorie"].forEach((mode) => {
  const bouton = document.getElementById("mode-" + mode);
  if (!bouton) return;
  bouton.addEventListener("click", () => {
    if (modeAffichage === mode) return;
    modeAffichage = mode;
    ["liste", "categorie"].forEach((m) => {
      const b = document.getElementById("mode-" + m);
      if (b) b.classList.toggle("actif", m === mode);
    });
    reaffiche();
  });
});

activeOngletPronostics("j0");
chargeRoiDashboard();
