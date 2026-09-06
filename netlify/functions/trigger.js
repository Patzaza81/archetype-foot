// Netlify Function — passerelle sécurisée vers GitHub Actions.
//
// (29/08/2026 -- Supabase) Rôle inchangé sur le fond (déclencher
// pipeline.yml), mais reçoit désormais un panier_id au lieu du tableau de
// matchs en clair. Le panier existe déjà dans Supabase (créé par panier.js
// avec le jeton de l'utilisateur) -- cette fonction se contente de vérifier
// qu'il appartient bien à l'appelant avant de lancer le pipeline, pour
// qu'on ne puisse pas déclencher une analyse au nom du panier de quelqu'un
// d'autre en devinant/bricolant un panier_id.
//
// Variables d'environnement Netlify requises :
//   GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO
//   SUPABASE_URL, SUPABASE_ANON_KEY
// Variables optionnelles :
//   GITHUB_WORKFLOW_FILE (défaut : pipeline.yml)
//   GITHUB_REF           (défaut : main)

const MAX_BODY_BYTES = 4 * 1024; // un panier_id + un jeton, pas un tableau de matchs
const DEFAULT_WORKFLOW_FILE = "pipeline.yml";
const DEFAULT_REF = "main";
const GITHUB_API_VERSION = "2022-11-28";
const RE_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// AJOUT 06/09/2026 (bug #25) -- rate-limit + vérification "pas déjà en
// cours", appliqués tous deux via des requêtes Supabase avec le jeton de
// L'UTILISATEUR (pas service_role) -- RLS scope déjà tout à ses propres
// lignes, aucun filtre user_id explicite à ajouter ici, même principe que
// verifiePanierAppartientAUtilisateur() ci-dessous.
const LIMITE_PANIERS_PAR_FENETRE = 3;
const FENETRE_RATE_LIMIT_MINUTES = 10;

// AJOUT 06/09/2026 (bug #26) -- taille max de panier. Schéma Supabase non
// vérifiable depuis ce dépôt (pas de contrainte CHECK côté base à ce
// jour) -- appliqué ici, côté fonction, en relisant le panier déjà inséré
// (même requête que la vérification de propriété, `matchs` ajouté au
// select). Valeur choisie par défaut, jamais confirmée avec Patrick --
// À AJUSTER si besoin, une simple constante à changer.
const TAILLE_MAX_PANIER = 50;

function jsonResponse(statusCode, body) {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
    body: JSON.stringify(body),
  };
}

function getBody(event) {
  if (!event || typeof event.body !== "string") {
    throw new Error("INVALID_BODY");
  }
  const bodySize = Buffer.byteLength(event.body, "utf8");
  if (bodySize > MAX_BODY_BYTES) {
    throw new Error("PAYLOAD_TOO_LARGE");
  }
  try {
    return JSON.parse(event.body);
  } catch {
    throw new Error("INVALID_JSON");
  }
}

function getConfiguration() {
  const token = process.env.GITHUB_TOKEN;
  const owner = process.env.GITHUB_OWNER;
  const repo = process.env.GITHUB_REPO;
  const workflowFile = process.env.GITHUB_WORKFLOW_FILE || DEFAULT_WORKFLOW_FILE;
  const ref = process.env.GITHUB_REF || DEFAULT_REF;
  const supabaseUrl = process.env.SUPABASE_URL;
  const supabaseAnonKey = process.env.SUPABASE_ANON_KEY;

  if (!token || !owner || !repo || !supabaseUrl || !supabaseAnonKey) {
    return { valid: false, error: "Configuration serveur incomplète (GitHub ou Supabase)." };
  }
  if (!/^[A-Za-z0-9_.-]+$/.test(owner)) return { valid: false, error: "GITHUB_OWNER invalide." };
  if (!/^[A-Za-z0-9_.-]+$/.test(repo)) return { valid: false, error: "GITHUB_REPO invalide." };
  if (!/^[A-Za-z0-9_.-]+$/.test(workflowFile)) return { valid: false, error: "GITHUB_WORKFLOW_FILE invalide." };
  if (!/^[A-Za-z0-9_.\/-]+$/.test(ref)) return { valid: false, error: "GITHUB_REF invalide." };

  return { valid: true, token, owner, repo, workflowFile, ref, supabaseUrl, supabaseAnonKey };
}

// Vérifie que le panier existe ET appartient à l'appelant. On interroge
// Supabase AVEC le jeton de l'utilisateur (pas la clé service_role) --
// c'est ça qui active RLS : si le panier appartient à quelqu'un d'autre,
// la policy "chacun voit ses propres paniers" fait que la requête renvoie
// un tableau vide, comme si le panier n'existait pas. Aucune vérification
// manuelle de propriétaire à coder ici -- la base la fait toute seule.
//
// CORRECTIF 06/09/2026 (bug #26) : select étendu à "id,matchs" (avant :
// "id" seul) pour pouvoir vérifier la taille du panier dans le même
// aller-retour réseau, sans requête supplémentaire. Retourne désormais
// { ok, matchs } au lieu d'un simple booléen -- ok=false couvre les deux
// anciens cas (panier introuvable OU n'appartenant pas à l'appelant,
// RLS renvoie un tableau vide dans les deux cas, indiscernables et c'est
// voulu -- jamais révéler qu'un panier_id existe chez quelqu'un d'autre).
async function verifiePanierAppartientAUtilisateur(config, panierId, jetonUtilisateur) {
  const url = `${config.supabaseUrl}/rest/v1/paniers?id=eq.${encodeURIComponent(panierId)}&select=id,matchs`;
  const response = await fetch(url, {
    headers: {
      apikey: config.supabaseAnonKey,
      Authorization: `Bearer ${jetonUtilisateur}`,
    },
  });
  if (!response.ok) return { ok: false, matchs: null };
  const lignes = await response.json();
  if (!Array.isArray(lignes) || lignes.length !== 1) return { ok: false, matchs: null };
  return { ok: true, matchs: lignes[0].matchs };
}

// AJOUT 06/09/2026 (bug #25, partie 1/2) -- un panier "en_cours" existe
// déjà pour cet utilisateur (statut posé par dispatch_pipeline.py une
// fois le run GitHub Actions réellement démarré, voir marque_panier_en_cours()) ?
// LIMITE CONNUE, acceptée : workflow_dispatch est asynchrone (jusqu'à
// ~1 min avant que le run démarre côté GitHub) -- une double soumission
// très rapprochée, avant que le premier run n'ait eu le temps de poser
// "en_cours", peut passer ce contrôle. Le rate-limit ci-dessous couvre ce
// cas résiduel en bornant le nombre total de soumissions, pas seulement
// les "en_cours" détectées.
async function utilisateurADejaUnePanierEnCours(config, jetonUtilisateur) {
  const url = `${config.supabaseUrl}/rest/v1/paniers?select=id&statut=eq.en_cours`;
  const response = await fetch(url, {
    headers: {
      apikey: config.supabaseAnonKey,
      Authorization: `Bearer ${jetonUtilisateur}`,
    },
  });
  // Échec technique de la vérification elle-même -- ne bloque jamais
  // l'utilisateur pour une panne de CE contrôle précis (même philosophie
  // que le reste du dépôt : mieux vaut laisser passer que faire échouer
  // tout le monde sur un contrôle annexe en panne).
  if (!response.ok) return false;
  const lignes = await response.json();
  return Array.isArray(lignes) && lignes.length > 0;
}

// AJOUT 06/09/2026 (bug #25, partie 2/2) -- nombre de paniers créés par
// cet utilisateur dans la fenêtre récente (inclut le panier qui vient
// d'être inséré par panier.js juste avant cet appel -- c'est voulu, il
// compte dans le total). Retourne null sur échec technique (jamais 0 --
// 0 affirmerait à tort "aucune activité récente" et lèverait le
// rate-limit par erreur si la requête a juste échoué).
async function compteParisRecents(config, jetonUtilisateur) {
  const depuis = new Date(Date.now() - FENETRE_RATE_LIMIT_MINUTES * 60 * 1000).toISOString();
  const url = `${config.supabaseUrl}/rest/v1/paniers?select=id&created_at=gte.${encodeURIComponent(depuis)}`;
  const response = await fetch(url, {
    headers: {
      apikey: config.supabaseAnonKey,
      Authorization: `Bearer ${jetonUtilisateur}`,
    },
  });
  if (!response.ok) return null;
  const lignes = await response.json();
  return Array.isArray(lignes) ? lignes.length : null;
}

async function dispatchWorkflow(config, panierId) {
  const url =
    `https://api.github.com/repos/` +
    `${encodeURIComponent(config.owner)}/` +
    `${encodeURIComponent(config.repo)}/` +
    `actions/workflows/` +
    `${encodeURIComponent(config.workflowFile)}/dispatches`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${config.token}`,
      "X-GitHub-Api-Version": GITHUB_API_VERSION,
      "Content-Type": "application/json",
      "User-Agent": "archetype-foot-netlify-trigger",
    },
    body: JSON.stringify({ ref: config.ref, inputs: { panier_id: panierId } }),
  });

  if (response.status === 204) return true;

  let githubMessage = null;
  try {
    const data = await response.json();
    if (data && typeof data.message === "string") githubMessage = data.message;
  } catch {}

  console.error("GitHub workflow_dispatch refusé", { status: response.status, message: githubMessage });
  return false;
}

exports.handler = async (event) => {
  if (!event || event.httpMethod !== "POST") {
    return jsonResponse(405, { ok: false, error: "Méthode non autorisée." });
  }

  const config = getConfiguration();
  if (!config.valid) {
    console.error(config.error);
    return jsonResponse(500, { ok: false, error: "Configuration serveur incomplète." });
  }

  const authHeader = event.headers?.authorization || event.headers?.Authorization || "";
  const jetonUtilisateur = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : null;
  if (!jetonUtilisateur) {
    return jsonResponse(401, { ok: false, error: "Authentification manquante." });
  }

  let rawPayload;
  try {
    rawPayload = getBody(event);
  } catch (error) {
    if (error.message === "PAYLOAD_TOO_LARGE") {
      return jsonResponse(413, { ok: false, error: "Payload trop volumineux." });
    }
    return jsonResponse(400, { ok: false, error: "JSON invalide." });
  }

  const panierId = rawPayload && typeof rawPayload.panier_id === "string" ? rawPayload.panier_id : null;
  if (!panierId || !RE_UUID.test(panierId)) {
    return jsonResponse(400, { ok: false, error: "panier_id manquant ou invalide." });
  }

  try {
    const { ok: appartientBienAUtilisateur, matchs } =
      await verifiePanierAppartientAUtilisateur(config, panierId, jetonUtilisateur);
    if (!appartientBienAUtilisateur) {
      return jsonResponse(404, { ok: false, error: "Panier introuvable." });
    }

    // CORRECTIF 06/09/2026 (bug #26) : taille max de panier, vérifiée
    // AVANT tout déclenchement -- un panier trop gros ne consomme jamais
    // de minutes GitHub Actions ni de résolution Betpawa pour rien.
    const nbMatchs = Array.isArray(matchs) ? matchs.length : 0;
    if (nbMatchs > TAILLE_MAX_PANIER) {
      return jsonResponse(400, {
        ok: false,
        error: `Panier trop volumineux (${nbMatchs} match(s), maximum ${TAILLE_MAX_PANIER}).`,
      });
    }

    // CORRECTIF 06/09/2026 (bug #25) : "pas déjà en_cours" avant le
    // rate-limit -- message plus précis pour l'utilisateur dans le cas le
    // plus probable (relance impatiente pendant qu'une analyse tourne
    // déjà), le rate-limit couvrant le reste (spam, ou double clic trop
    // rapide pour que "en_cours" soit déjà posé -- voir la limite connue
    // documentée sur utilisateurADejaUnePanierEnCours()).
    const dejaEnCours = await utilisateurADejaUnePanierEnCours(config, jetonUtilisateur);
    if (dejaEnCours) {
      return jsonResponse(429, {
        ok: false,
        error: "Une analyse est déjà en cours pour ce compte -- attends qu'elle se termine avant d'en lancer une nouvelle.",
      });
    }

    const nbRecents = await compteParisRecents(config, jetonUtilisateur);
    if (nbRecents !== null && nbRecents > LIMITE_PANIERS_PAR_FENETRE) {
      return jsonResponse(429, {
        ok: false,
        error: `Trop de demandes récentes (maximum ${LIMITE_PANIERS_PAR_FENETRE} par ${FENETRE_RATE_LIMIT_MINUTES} minutes) -- réessaie plus tard.`,
      });
    }

    const accepted = await dispatchWorkflow(config, panierId);
    if (!accepted) {
      return jsonResponse(502, { ok: false, error: "GitHub n'a pas accepté le déclenchement du workflow." });
    }
    return jsonResponse(202, { ok: true, message: "Analyse envoyée." });
  } catch (error) {
    console.error("Erreur lors du déclenchement GitHub", error);
    return jsonResponse(502, { ok: false, error: "Impossible de joindre GitHub ou Supabase." });
  }
};
