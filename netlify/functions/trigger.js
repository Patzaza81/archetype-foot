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
async function verifiePanierAppartientAUtilisateur(config, panierId, jetonUtilisateur) {
  const url = `${config.supabaseUrl}/rest/v1/paniers?id=eq.${encodeURIComponent(panierId)}&select=id`;
  const response = await fetch(url, {
    headers: {
      apikey: config.supabaseAnonKey,
      Authorization: `Bearer ${jetonUtilisateur}`,
    },
  });
  if (!response.ok) return false;
  const lignes = await response.json();
  return Array.isArray(lignes) && lignes.length === 1;
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
    const appartientBienAUtilisateur = await verifiePanierAppartientAUtilisateur(config, panierId, jetonUtilisateur);
    if (!appartientBienAUtilisateur) {
      return jsonResponse(404, { ok: false, error: "Panier introuvable." });
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
