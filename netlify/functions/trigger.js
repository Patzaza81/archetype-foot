const ALLOWED_METHODS = ["POST"];
const MAX_BODY_BYTES = 16 * 1024;
const DEFAULT_WORKFLOW_FILE = "pipeline.yml";
const DEFAULT_REF = "main";

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
  if (!event || typeof event.body !== "string") return null;
  const bodySize = Buffer.byteLength(event.body, "utf8");
  if (bodySize > MAX_BODY_BYTES) throw new Error("PAYLOAD_TOO_LARGE");
  try { return JSON.parse(event.body); } catch { throw new Error("INVALID_JSON"); }
}

function cleanString(value, maxLength = 300) {
  if (typeof value !== "string") return null;
  const cleaned = value.trim();
  if (!cleaned || cleaned.length > maxLength) return null;
  return cleaned;
}

function validatePayload(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return { valid: false, error: "Le payload doit être un objet JSON." };
  }
  const equipeDom = cleanString(payload.equipe_dom, 150);
  const equipeExt = cleanString(payload.equipe_ext, 150);
  const date = cleanString(payload.date, 20);
  const heure = cleanString(payload.heure, 20);

  if (!equipeDom || !equipeExt || !date || !heure) {
    return { valid: false, error: "Champs obligatoires manquants." };
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return { valid: false, error: "Format date invalide (YYYY-MM-DD)." };
  }
  if (!/^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(heure)) {
    return { valid: false, error: "Format heure invalide (HH:MM)." };
  }

  let urlMatchendirect = null;
  if (payload.url_matchendirect !== undefined) {
    urlMatchendirect = cleanString(payload.url_matchendirect, 1000);
    if (urlMatchendirect !== null && !/^https?:\/\/[^/\s]+(?:\/[^\s]*)?$/i.test(urlMatchendirect)) {
      return { valid: false, error: "URL invalide." };
    }
  }

  return {
    valid: true,
    payload: { equipe_dom: equipeDom, equipe_ext: equipeExt, date, heure, url_matchendirect: urlMatchendirect },
  };
}

function getConfiguration() {
  const token = process.env.GITHUB_TOKEN;
  const owner = process.env.GITHUB_OWNER;
  const repo = process.env.GITHUB_REPO;
  const workflowFile = process.env.GITHUB_WORKFLOW_FILE || DEFAULT_WORKFLOW_FILE;
  const ref = process.env.GITHUB_REF || DEFAULT_REF;

  if (!token || !owner || !repo) {
    return { valid: false, error: "Configuration serveur incomplète." };
  }
  return { valid: true, token, owner, repo, workflowFile, ref };
}

async function dispatchWorkflow(config, payload) {
  const url = `https://api.github.com/repos/${encodeURIComponent(config.owner)}/${encodeURIComponent(config.repo)}/actions/workflows/${encodeURIComponent(config.workflowFile)}/dispatches`;

  const inputs = {
    equipe_dom: payload.equipe_dom,
    equipe_ext: payload.equipe_ext,
    date: payload.date,
    heure: payload.heure,
  };
  if (payload.url_matchendirect) inputs.url_matchendirect = payload.url_matchendirect;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${config.token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "archetype-foot-trigger",
    },
    body: JSON.stringify({ ref: config.ref, inputs }),
  });

  if (response.status === 204) return { ok: true };
  return { ok: false, status: response.status };
}

exports.handler = async (event) => {
  if (!ALLOWED_METHODS.includes(event?.httpMethod)) {
    return jsonResponse(405, { ok: false, error: "Méthode non autorisée." });
  }
  const config = getConfiguration();
  if (!config.valid) return jsonResponse(500, { ok: false, error: config.error });

  let rawPayload;
  try { rawPayload = getBody(event); } catch (e) {
    return jsonResponse(e.message === "PAYLOAD_TOO_LARGE" ? 413 : 400, { ok: false, error: "JSON invalide." });
  }

  const validation = validatePayload(rawPayload);
  if (!validation.valid) return jsonResponse(400, { ok: false, error: validation.error });

  try {
    const result = await dispatchWorkflow(config, validation.payload);
    if (!result.ok) return jsonResponse(502, { ok: false, error: "Déclenchement GitHub refusé." });
    return jsonResponse(202, { ok: true, message: "Analyse envoyée." });
  } catch (e) {
    return jsonResponse(502, { ok: false, error: "Erreur de connexion à GitHub." });
  }
};
