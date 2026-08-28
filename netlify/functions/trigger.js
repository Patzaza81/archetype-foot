// Netlify Function — passerelle sécurisée vers GitHub Actions.
//
// Rôle unique : recevoir la sélection depuis le site, la valider,
// puis déclencher le workflow pipeline.yml sans exposer le token GitHub.
//
// Variables d'environnement Netlify requises :
//   GITHUB_TOKEN
//   GITHUB_OWNER
//   GITHUB_REPO
//
// Variables optionnelles :
//   GITHUB_WORKFLOW_FILE (défaut : pipeline.yml)
//   GITHUB_REF           (défaut : main)

const MAX_BODY_BYTES = 16 * 1024;
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
  if (typeof value !== "string") {
    return null;
  }

  const cleaned = value.trim();

  if (!cleaned || cleaned.length > maxLength) {
    return null;
  }

  return cleaned;
}

function isValidDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }

  const [year, month, day] = value.split("-").map(Number);

  const date = new Date(Date.UTC(year, month - 1, day));

  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

function isValidTime(value) {
  return /^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(value);
}

function isAllowedMatchendirectUrl(value) {
  if (value === null) {
    return true;
  }

  try {
    const url = new URL(value);
    const hostname = url.hostname.toLowerCase();

    return (
      url.protocol === "https:" &&
      (
        hostname === "matchendirect.fr" ||
        hostname.endsWith(".matchendirect.fr")
      )
    );
  } catch {
    return false;
  }
}

function validatePayload(payload) {
  if (
    !payload ||
    typeof payload !== "object" ||
    Array.isArray(payload)
  ) {
    return {
      valid: false,
      error: "Le payload doit être un objet JSON.",
    };
  }

  const equipeDom = cleanString(payload.equipe_dom, 150);
  const equipeExt = cleanString(payload.equipe_ext, 150);
  const date = cleanString(payload.date, 10);
  const heure = cleanString(payload.heure, 8);

  if (!equipeDom || !equipeExt || !date || !heure) {
    return {
      valid: false,
      error:
        "Les champs equipe_dom, equipe_ext, date et heure sont obligatoires.",
    };
  }

  if (!isValidDate(date)) {
    return {
      valid: false,
      error:
        "Le champ date doit être une date valide au format YYYY-MM-DD.",
    };
  }

  if (!isValidTime(heure)) {
    return {
      valid: false,
      error:
        "Le champ heure doit être au format HH:MM ou HH:MM:SS.",
    };
  }

  let urlMatchendirect = null;

  if (
    payload.url_matchendirect !== undefined &&
    payload.url_matchendirect !== null
  ) {
    urlMatchendirect = cleanString(
      payload.url_matchendirect,
      1000
    );

    if (
      !urlMatchendirect ||
      !isAllowedMatchendirectUrl(urlMatchendirect)
    ) {
      return {
        valid: false,
        error:
          "url_matchendirect doit être une URL HTTPS Matchendirect valide.",
      };
    }
  }

  return {
    valid: true,
    payload: {
      equipe_dom: equipeDom,
      equipe_ext: equipeExt,
      date,
      heure,
      url_matchendirect: urlMatchendirect,
    },
  };
}

function getConfiguration() {
  const token = process.env.GITHUB_TOKEN;
  const owner = process.env.GITHUB_OWNER;
  const repo = process.env.GITHUB_REPO;

  const workflowFile =
    process.env.GITHUB_WORKFLOW_FILE ||
    DEFAULT_WORKFLOW_FILE;

  const ref =
    process.env.GITHUB_REF ||
    DEFAULT_REF;

  if (!token || !owner || !repo) {
    return {
      valid: false,
      error: "Configuration GitHub serveur incomplète.",
    };
  }

  if (!/^[A-Za-z0-9_.-]+$/.test(owner)) {
    return {
      valid: false,
      error: "GITHUB_OWNER invalide.",
    };
  }

  if (!/^[A-Za-z0-9_.-]+$/.test(repo)) {
    return {
      valid: false,
      error: "GITHUB_REPO invalide.",
    };
  }

  if (!/^[A-Za-z0-9_.-]+$/.test(workflowFile)) {
    return {
      valid: false,
      error: "GITHUB_WORKFLOW_FILE invalide.",
    };
  }

  if (!/^[A-Za-z0-9_.\/-]+$/.test(ref)) {
    return {
      valid: false,
      error: "GITHUB_REF invalide.",
    };
  }

  return {
    valid: true,
    token,
    owner,
    repo,
    workflowFile,
    ref,
  };
}

async function dispatchWorkflow(config, payload) {
  const url =
    `https://api.github.com/repos/` +
    `${encodeURIComponent(config.owner)}/` +
    `${encodeURIComponent(config.repo)}/` +
    `actions/workflows/` +
    `${encodeURIComponent(config.workflowFile)}/dispatches`;

  const inputs = {
    equipe_dom: payload.equipe_dom,
    equipe_ext: payload.equipe_ext,
    date: payload.date,
    heure: payload.heure,
  };

  // URL conservée uniquement comme mécanisme de secours
  // pendant la migration.
  if (payload.url_matchendirect) {
    inputs.url_matchendirect =
      payload.url_matchendirect;
  }

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${config.token}`,
      "X-GitHub-Api-Version": GITHUB_API_VERSION,
      "Content-Type": "application/json",
      "User-Agent": "archetype-foot-netlify-trigger",
    },
    body: JSON.stringify({
      ref: config.ref,
      inputs,
    }),
  });

  // GitHub retourne 204 lorsque workflow_dispatch
  // a été accepté.
  if (response.status === 204) {
    return true;
  }

  let githubMessage = null;

  try {
    const data = await response.json();

    if (
      data &&
      typeof data.message === "string"
    ) {
      githubMessage = data.message;
    }
  } catch {
    // Réponse non JSON : aucun détail supplémentaire
    // n'est nécessaire côté client.
  }

  console.error(
    "GitHub workflow_dispatch refusé",
    {
      status: response.status,
      message: githubMessage,
    }
  );

  return false;
}

exports.handler = async (event) => {
  // Seul POST est accepté.
  if (
    !event ||
    event.httpMethod !== "POST"
  ) {
    return jsonResponse(405, {
      ok: false,
      error: "Méthode non autorisée.",
    });
  }

  // Vérification de la configuration serveur.
  const config = getConfiguration();

  if (!config.valid) {
    console.error(config.error);

    return jsonResponse(500, {
      ok: false,
      error: "Configuration serveur incomplète.",
    });
  }

  // Lecture du payload.
  let rawPayload;

  try {
    rawPayload = getBody(event);
  } catch (error) {
    if (
      error.message ===
      "PAYLOAD_TOO_LARGE"
    ) {
      return jsonResponse(413, {
        ok: false,
        error: "Payload trop volumineux.",
      });
    }

    return jsonResponse(400, {
      ok: false,
      error: "JSON invalide.",
    });
  }

  // Validation métier minimale.
  const validation =
    validatePayload(rawPayload);

  if (!validation.valid) {
    return jsonResponse(400, {
      ok: false,
      error: validation.error,
    });
  }

  // Déclenchement du workflow GitHub.
  try {
    const accepted =
      await dispatchWorkflow(
        config,
        validation.payload
      );

    if (!accepted) {
      return jsonResponse(502, {
        ok: false,
        error:
          "GitHub n'a pas accepté le déclenchement du workflow.",
      });
    }

    return jsonResponse(202, {
      ok: true,
      message:
        "Analyse envoyée au pipeline.",
    });
  } catch (error) {
    console.error(
      "Erreur lors du déclenchement GitHub",
      error
    );

    return jsonResponse(502, {
      ok: false,
      error:
        "Impossible de joindre GitHub Actions.",
    });
  }
};
