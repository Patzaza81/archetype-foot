// Netlify Function — passerelle sécurisée vers GitHub Actions.
//
// Rôle unique : recevoir un PANIER de plusieurs matchs, le valider,
// puis déclencher le workflow pipeline.yml avec la liste complète en
// un seul run -- pas un run par match, pour économiser les minutes
// GitHub Actions.
//
// Variables d'environnement Netlify requises :
//   GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO
// Variables optionnelles :
//   GITHUB_WORKFLOW_FILE (défaut : pipeline.yml)
//   GITHUB_REF           (défaut : main)

const MAX_BODY_BYTES = 32 * 1024;
const MAX_MATCHS = 30;
const DEFAULT_WORKFLOW_FILE = "pipeline.yml";
const DEFAULT_REF = "main";
const GITHUB_API_VERSION = "2022-11-28";

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

function cleanString(value, maxLength) {
  if (typeof value !== "string") return null;
  const cleaned = value.trim();
  if (!cleaned || cleaned.length > maxLength) return null;
  return cleaned;
}

function isAllowedMatchendirectUrl(value) {
  if (value === null) return true;
  try {
    const url = new URL(value);
    const hostname = url.hostname.toLowerCase();
    return (
      url.protocol === "https:" &&
      (hostname === "matchendirect.fr" || hostname.endsWith(".matchendirect.fr"))
    );
  } catch {
    return false;
  }
}

function validateMatch(m, index) {
  if (!m || typeof m !== "object" || Array.isArray(m)) {
    return { valid: false, error: `Match ${index + 1} : doit être un objet.` };
  }

  const domicile = cleanString(m.domicile, 150);
  const exterieur = cleanString(m.exterieur, 150);
  const competition = cleanString(m.competition, 200);

  if (!domicile || !exterieur || !competition) {
    return {
      valid: false,
      error: `Match ${index + 1} (${m.domicile || "?"} - ${m.exterieur || "?"}) : domicile, exterieur et competition sont obligatoires.`,
    };
  }

  let urlMatch = null;
  if (m.url_match !== undefined && m.url_match !== null && m.url_match !== "") {
    urlMatch = cleanString(m.url_match, 1000);
    if (!urlMatch || !isAllowedMatchendirectUrl(urlMatch)) {
      return {
        valid: false,
        error: `Match ${index + 1} (${domicile} - ${exterieur}) : url_match doit être une URL HTTPS Matchendirect valide.`,
      };
    }
  }

  const matchId = cleanString(m.match_id, 200);
  const source = cleanString(m.source, 50) || "panier_web";

  let cotesManuelles = null;
  if (m.cotes_manuelles && typeof m.cotes_manuelles === "object" && !Array.isArray(m.cotes_manuelles)) {
    cotesManuelles = m.cotes_manuelles;
  }

  return {
    valid: true,
    match: { domicile, exterieur, competition, url_match: urlMatch, match_id: matchId, source, cotes_manuelles: cotesManuelles },
  };
}

function validatePayload(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return { valid: false, error: "Le payload doit être un objet JSON." };
  }
  if (!Array.isArray(payload.matchs) || payload.matchs.length === 0) {
    return { valid: false, error: "Le champ matchs doit être un tableau non vide." };
  }
  if (payload.matchs.length > MAX_MATCHS) {
    return { valid: false, error: `Trop de matchs (${payload.matchs.length}) -- maximum ${MAX_MATCHS} par envoi.` };
  }

  const matchsValides = [];
  for (let i = 0; i < payload.matchs.length; i++) {
    const resultat = validateMatch(payload.matchs[i], i);
    if (!resultat.valid) {
      return { valid: false, error: resultat.error };
    }
    matchsValides.push(resultat.match);
  }

  return { valid: true, payload: { matchs: matchsValides } };
}

function getConfiguration() {
  const token = process.env.GITHUB_TOKEN;
  const owner = process.env.GITHUB_OWNER;
  const repo = process.env.GITHUB_REPO;
  const workflowFile = process.env.GITHUB_WORKFLOW_FILE || DEFAULT_WORKFLOW_FILE;
  const ref = process.env.GITHUB_REF || DEFAULT_REF;

  if (!token || !owner || !repo) {
    return { valid: false, error: "Configuration GitHub serveur incomplète." };
  }
  if (!/^[A-Za-z0-9_.-]+$/.test(owner)) return { valid: false, error: "GITHUB_OWNER invalide." };
  if (!/^[A-Za-z0-9_.-]+$/.test(repo)) return { valid: false, error: "GITHUB_REPO invalide." };
  if (!/^[A-Za-z0-9_.-]+$/.test(workflowFile)) return { valid: false, error: "GITHUB_WORKFLOW_FILE invalide." };
  if (!/^[A-Za-z0-9_.\/-]+$/.test(ref)) return { valid: false, error: "GITHUB_REF invalide." };

  return { valid: true, token, owner, repo, workflowFile, ref };
}

async function dispatchWorkflow(config, payload) {
  const url =
    `https://api.github.com/repos/` +
    `${encodeURIComponent(config.owner)}/` +
    `${encodeURIComponent(config.repo)}/` +
    `actions/workflows/` +
    `${encodeURIComponent(config.workflowFile)}/dispatches`;

  const inputs = {
    matchs_json: JSON.stringify(payload.matchs),
  };

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${config.token}`,
      "X-GitHub-Api-Version": GITHUB_API_VERSION,
      "Content-Type": "application/json",
      "User-Agent": "archetype-foot-netlify-trigger",
    },
    body: JSON.stringify({ ref: config.ref, inputs }),
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

  let rawPayload;
  try {
    rawPayload = getBody(event);
  } catch (error) {
    if (error.message === "PAYLOAD_TOO_LARGE") {
      return jsonResponse(413, { ok: false, error: "Payload trop volumineux." });
    }
    return jsonResponse(400, { ok: false, error: "JSON invalide." });
  }

  const validation = validatePayload(rawPayload);
  if (!validation.valid) {
    return jsonResponse(400, { ok: false, error: validation.error });
  }

  try {
    const accepted = await dispatchWorkflow(config, validation.payload);
    if (!accepted) {
      return jsonResponse(502, { ok: false, error: "GitHub n'a pas accepté le déclenchement du workflow." });
    }
    return jsonResponse(202, {
      ok: true,
      message: `Analyse envoyée pour ${validation.payload.matchs.length} match(s).`,
    });
  } catch (error) {
    console.error("Erreur lors du déclenchement GitHub", error);
    return jsonResponse(502, { ok: false, error: "Impossible de joindre GitHub Actions." });
  }
};
