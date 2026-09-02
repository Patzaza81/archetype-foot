// script.js — Module 4, hiérarchie visuelle à 5 niveaux (25/08) :
// 1. identification (équipes/compétition) 2. statut (verdict, texte +
// couleur, jamais couleur seule) 3. donnée principale (p(1), plus grosse
// taille de l'écran) 4. détails (paris, risques) 5. action secondaire
// (détail N1/N2, repliée par défaut).

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
  const lignes = listeA.map(c => `<tr>
    <td>${c.marche}</td><td>${c.cote_observee.toFixed(2)}</td>
    <td>${formatPct(c.probabilite_modele)}</td><td>${formatPct(c.ev_brut)}</td>
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
  return `<div class="proba-1">
    ${formatPct(pariEnOr.probabilite_modele)}
    <span class="proba-1-label">probabilité modèle — ${pariEnOr.marche}</span>
  </div>
  <p class="pourquoi-pari">
    pourquoi ce pari : cote ${pariEnOr.cote_observee.toFixed(2)}, ev ${formatPct(pariEnOr.ev_brut)},
    confiance ${m.confiance || "n/d"} (${m.nb_matchs_domicile_utilises ?? "?"} matchs domicile /
    ${m.nb_matchs_exterieur_utilises ?? "?"} matchs extérieur utilisés).
  </p>`;
}

const SUPABASE_URL = "https://hjrcqodwfjxqcjvjoxzq.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhqcmNxb2R3Zmp4cWNqdmpveHpxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgxMTU3NjUsImV4cCI6MjEwMzY5MTc2NX0.rxJ2W-2UI0oQrGAprqnrPJM3WO1HCoYft0ZeS38oZfY";
const SUPABASE_CONFIGURE = !SUPABASE_URL.includes("TON-PROJET") && !!window.supabase;
const supabaseClient = SUPABASE_CONFIGURE ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;

const DELAI_ATTENTE_MS = 15000;
const INTERVALLE_RAFRAICHISSEMENT_MS = 20000;
const NB_RAFRAICHISSEMENTS_MAX = 15;

function afficheErreur(message) {
  document.getElementById("maj").textContent = "erreur de chargement : " + message;
}

function afficheMatchs(matchs, enTete) {
  document.getElementById("maj").textContent = enTete;

  const container = document.getElementById("matches");
  container.innerHTML = "";
  if (!matchs || matchs.length === 0) {
    container.innerHTML = "<p>aucun résultat pour le moment.</p>";
    return;
  }

  matchs.forEach((m) => {
    const div = document.createElement("div");
    div.className = "match";

    let html = `
      <div class="teams"><span>${m.domicile}</span><span>${m.score || m.heure || ""}</span><span>${m.exterieur}</span></div>
      <div class="meta">${(m.competition || "").replace(/\s+/g, " ").trim()}</div>
    `;

    if (!m.traite) {
      html += `<div class="signal-non-traite">non analysé — ${traduireRaison(m.raison_non_traite)}</div>`;
    } else {
      const estGo = m.verdict_global === "GO";
      html += `<div class="ligne-verdict">
        <span class="badge ${estGo ? "badge-go" : "badge-nogo"}">${estGo ? "✓ GO" : "✕ NO_GO"}</span>
      </div>`;
      html += construitNiveau3(m);
      if (!estGo && m.motif_no_go) {
        html += `<div class="motif-no-go">${m.motif_no_go}</div>`;
      }
      if (estGo) {
        html += construitBlocParisRecommandes(m.LISTE_B_liste_finale_apres_correlation);
      }
      html += construitBlocRisques(m);
      html += construitDetails(m);
    }

    div.innerHTML = html;
    container.appendChild(div);
  });
}

// AJOUT 02/09/2026 (correctif race condition) -- jetonAffichage incrémenté
// à chaque changement d'onglet. Chaque fonction async capture le jeton au
// moment où elle démarre, et vérifie qu'il est TOUJOURS le plus récent
// avant d'écrire dans le DOM -- sinon elle abandonne silencieusement.
// Corrige le bug observé le 02/09 : un clic rapide entre onglets pouvait
// laisser un fetch obsolète (ex. Panier) écraser l'affichage d'un onglet
// déjà quitté (ex. J1), même si le bouton actif était le bon.
let jetonAffichage = 0;

const FORMAT_DATE_ONGLET = { weekday: "short", day: "numeric", month: "short" };

function dateIsoDansNJours(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function dateLisible(dateIso) {
  const [an, mois, jour] = dateIso.split("-").map(Number);
  return new Date(an, mois - 1, jour).toLocaleDateString("fr-FR", FORMAT_DATE_ONGLET);
}

const DATES_FENETRE = { j1: dateIsoDansNJours(1), j2: dateIsoDansNJours(2), j3: dateIsoDansNJours(3) };

let precalculCharge = null;

async function chargePrecalcul() {
  if (precalculCharge) return precalculCharge;
  const r = await fetch("precalcul.json?_=" + Date.now());
  if (!r.ok) throw new Error(`precalcul.json introuvable (status ${r.status})`);
  precalculCharge = await r.json();
  return precalculCharge;
}

async function afficheOngletJour(cle, monJeton) {
  try {
    const data = await chargePrecalcul();
    if (monJeton !== jetonAffichage) return; // un autre onglet a été demandé entre-temps
    const dateIso = DATES_FENETRE[cle];
    const signaux = (data.signaux || []).filter((s) => s.date === dateIso);
    const nbReady = signaux.filter((s) => s.traite).length;
    afficheMatchs(
      signaux,
      `${cle.toUpperCase()} — ${dateLisible(dateIso)} — ${nbReady}/${signaux.length} match(s) analysé(s) ` +
      `(mis à jour : ${data.genere_le || "inconnu"})`
    );
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
  afficheMatchs(data.matchs || [], "mis à jour : " + (data.genere_le || "inconnu") + " — " + (data.matchs || []).length + " match(s) traité(s)");
  return data.genere_le || null;
}

async function chargeDernierResultat(monJeton) {
  if (!SUPABASE_CONFIGURE) {
    return await chargeDepuisDataJson(monJeton);
  }

  const { data: { session } } = await supabaseClient.auth.getSession();
  if (monJeton !== jetonAffichage) return null;
  if (!session) {
    afficheMatchs([], "aucun panier envoyé depuis cet appareil pour le moment.");
    return null;
  }

  const delaiDepasse = new Promise((_, reject) =>
    setTimeout(() => reject(new Error("délai dépassé (15s) -- vérifie ta connexion.")), DELAI_ATTENTE_MS)
  );

  const requete = supabaseClient
    .from("resultats_pipeline")
    .select("data, created_at")
    .eq("user_id", session.user.id)
    .order("created_at", { ascending: false })
    .limit(1);

  const { data: lignes, error } = await Promise.race([requete, delaiDepasse]);
  if (monJeton !== jetonAffichage) return null;
  if (error) throw new Error(error.message);

  if (!lignes || lignes.length === 0) {
    afficheMatchs([], "aucun résultat pour le moment -- l'analyse est peut-être encore en cours.");
    return null;
  }

  const ligne = lignes[0];
  afficheMatchs(ligne.data || [], "mis à jour : " + ligne.created_at + " — " + (ligne.data || []).length + " match(s) traité(s)");
  return ligne.created_at;
}

let compteurRafraichissements = 0;
let ongletActif = "j1";

async function activeOngletPronostics(cle) {
  ongletActif = cle;
  jetonAffichage += 1;
  const monJeton = jetonAffichage;

  ["j1", "j2", "j3", "panier"].forEach((c) => {
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

["j1", "j2", "j3", "panier"].forEach((cle) => {
  const bouton = document.getElementById("onglet-" + cle);
  if (!bouton) return;
  if (cle !== "panier") {
    bouton.textContent = `${cle.toUpperCase()} — ${dateLisible(DATES_FENETRE[cle])}`;
  }
  bouton.addEventListener("click", () => activeOngletPronostics(cle));
});

activeOngletPronostics("j1");
