// admin.js — page d'audit/contrôle. Présentation uniquement, aucun calcul
// de fond : lit data/audit_status.json (report.py) et
// data/audit_telemetry.json (telemetry.py), déjà produits par le pipeline
// nocturne. NETTOYAGE 22/09/2026 : le bloc "Journal d'étalonnage &
// calibration" (config/journal_promotion.jsonl, calibre_archetype_model.py)
// est retiré -- ce système a été supprimé entièrement (demande de
// Patrick). Le reste de cette page (cockpit, disjoncteurs, télémétrie)
// appartient à l'audit passif de l'ancien modèle, déjà figé depuis le
// 21/09/2026 (plus alimenté) -- hors périmètre de ce nettoyage.
//
// AUTHENTIFICATION -- LIMITE CONNUE, À GARDER EN TÊTE : cette vérification
// est côté client uniquement (pas de backend sur un hébergement statique).
// Elle empêche un visiteur occasionnel de tomber sur cette page par
// hasard, PAS un accès délibéré : le mot de passe est visible en clair
// dans ce fichier (donc dans le dépôt GitHub public), et les fichiers
// JSON eux-mêmes (data/, config/) restent atteignables directement par
// leur URL, gate ou pas. Une vraie protection nécessiterait une couche
// serveur (ex. protection par mot de passe côté hébergeur, fonction
// serverless) -- hors périmètre de ce chantier, signalé tel quel.

(function () {
  "use strict";

  const CLE_SESSION = "admin_auth";
  const UTILISATEUR_ATTENDU = "admin";
  const MOT_DE_PASSE_ATTENDU = "Patricia@2010";

  function estAuthentifie() {
    return sessionStorage.getItem(CLE_SESSION) === "true";
  }

  function afficheConnexion() {
    document.getElementById("admin-login-overlay").hidden = false;
    document.getElementById("admin-main").hidden = true;
  }

  function afficheTableauDeBord() {
    document.getElementById("admin-login-overlay").hidden = true;
    document.getElementById("admin-main").hidden = false;
    chargeEtAffiche();
  }

  function installeAuthentification() {
    const formulaire = document.getElementById("admin-login-form");
    const erreur = document.getElementById("admin-login-erreur");

    formulaire.addEventListener("submit", function (e) {
      e.preventDefault();
      const utilisateur = document.getElementById("admin-user").value;
      const motDePasse = document.getElementById("admin-pass").value;
      if (utilisateur === UTILISATEUR_ATTENDU && motDePasse === MOT_DE_PASSE_ATTENDU) {
        sessionStorage.setItem(CLE_SESSION, "true");
        erreur.hidden = true;
        formulaire.reset();
        afficheTableauDeBord();
      } else {
        erreur.hidden = false;
      }
    });

    document.getElementById("admin-logout").addEventListener("click", function () {
      sessionStorage.removeItem(CLE_SESSION);
      afficheConnexion();
    });

    if (estAuthentifie()) afficheTableauDeBord();
    else afficheConnexion();
  }

  // -------------------------------------------------------------------
  // Utilitaires de formatage/échappement (mêmes conventions que systeme.js)
  // -------------------------------------------------------------------

  function echappeHtml(x) {
    return x === null || x === undefined ? "" : String(x)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function formatPct(x, decimales = 1) {
    const n = Number(x);
    return Number.isFinite(n) ? `${(n * 100).toFixed(decimales).replace(".", ",")} %` : "—";
  }

  function formatNombre(x, decimales = 3) {
    const n = Number(x);
    return Number.isFinite(n) ? n.toFixed(decimales).replace(".", ",") : "—";
  }

  function formatDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? echappeHtml(iso) : d.toLocaleString("fr-FR");
  }

  function ratioSur(numerateur, denominateur) {
    const n = Number(numerateur), d = Number(denominateur);
    if (!Number.isFinite(n) || !Number.isFinite(d) || d <= 0) return null;
    return n / d;
  }

  // -------------------------------------------------------------------
  // Bloc 1 — Cockpit de santé
  // -------------------------------------------------------------------

  function construitBlocCockpit(status) {
    const div = document.createElement("div");
    div.className = "bloc-systeme";

    if (!status) {
      div.innerHTML = `<h2>🩺 Cockpit de santé</h2><p class="etat-vide-systeme">Aucun contrôle d'audit n'a encore tourné.</p>`;
      return div;
    }

    const statutGlobal = status.statut_global || "INCONNU";
    const brier = status.brier_score_global;
    const brierAlerte = Number.isFinite(Number(brier)) && Number(brier) > 0.20;
    const run = status.run || {};
    const p1 = (run.qualifies_selection_finale || {}).P1 || 0;
    const tauxRetention = ratioSur(p1, run.matchs_scannes);

    div.innerHTML = `
      <h2>🩺 Cockpit de santé</h2>
      <p><span class="pastille-statut pastille-${echappeHtml(statutGlobal)}"></span><span class="statut-libelle">${echappeHtml(statutGlobal)}</span></p>
      <div class="grille-stats">
        <div class="stat">
          <span class="etiquette">Brier Score actuel${brierAlerte ? " ⚠️" : ""}</span>
          <strong style="${brierAlerte ? "color:var(--red)" : ""}">${brier === null || brier === undefined ? "—" : formatNombre(brier)}</strong>
        </div>
        <div class="stat">
          <span class="etiquette">Matchs scannés (dernier run)</span>
          <strong>${run.matchs_scannes ?? 0}</strong>
        </div>
        <div class="stat">
          <span class="etiquette">Taux de rétention global (P1)</span>
          <strong>${tauxRetention === null ? "—" : formatPct(tauxRetention)}</strong>
        </div>
        <div class="stat">
          <span class="etiquette">Marchés scannés</span>
          <strong>${run.marches_scannes ?? 0}</strong>
        </div>
      </div>
      <p class="note-systeme">Seuils du statut : GREEN ${echappeHtml((status.seuils_statut || {}).GREEN || "≤ 0,20")} · YELLOW ${echappeHtml((status.seuils_statut || {}).YELLOW || "≤ 0,23")} · RED au-delà. Dernier contrôle : ${formatDate(status.horodatage_controle)}.</p>`;
    return div;
  }

  // -------------------------------------------------------------------
  // Bloc 2 — Filtre d'intégrité & disjoncteurs
  // -------------------------------------------------------------------

  const LIBELLES_BADGE_MOTIF = {
    TAUX_DONNEES_MANQUANTES_ELEVE: { classe: "badge-motif-taux", texte: "Taux manquant > 15 %" },
    VARIATION_COTE_BRUTALE: { classe: "badge-motif-variation", texte: "Variation cote > 15 %" },
    ECHANTILLON_INSUFFISANT: { classe: "badge-motif-echantillon", texte: "Échantillon < 5" },
  };

  function construitBadgeMotif(motif) {
    const lib = LIBELLES_BADGE_MOTIF[motif] || { classe: "badge-motif-echantillon", texte: motif };
    return `<span class="badge-motif ${lib.classe}">${echappeHtml(lib.texte)}</span>`;
  }

  function construitBlocDisjoncteurs(dernierRun) {
    const div = document.createElement("div");
    div.className = "bloc-systeme";
    const matchs = (dernierRun && dernierRun.matchs_neutralises) || [];

    if (!matchs.length) {
      div.innerHTML = `<h2>⛔ Filtre d'intégrité & disjoncteurs</h2><p class="etat-vide-systeme">Aucun match neutralisé sur le dernier run -- toutes les données passées au crible étaient exploitables.</p>`;
      return div;
    }

    const lignes = matchs.map((m) => `
      <tr>
        <td>${echappeHtml(m.domicile || "—")}</td>
        <td>${echappeHtml(m.exterieur || "—")}</td>
        <td>${echappeHtml(m.date || "—")}</td>
        <td>${(m.motifs || []).map(construitBadgeMotif).join(" ") || "—"}</td>
      </tr>`).join("");

    div.innerHTML = `
      <h2>⛔ Filtre d'intégrité & disjoncteurs</h2>
      <table class="tableau-systeme">
        <thead><tr><th>Domicile</th><th>Extérieur</th><th>Date</th><th>Motif</th></tr></thead>
        <tbody>${lignes}</tbody>
      </table>
      <p class="note-systeme">Neutralisé = signalé par le disjoncteur d'intégrité, jamais rejeté par lui -- le match continue son traitement normal (voir archetype_model/audit/circuit_breaker.py, module purement passif).</p>`;
    return div;
  }

  // -------------------------------------------------------------------
  // Bloc 3 — Télémétrie par étage réel du pipeline
  // -------------------------------------------------------------------

  function construitJaugePeage(etiquette, ratio, note) {
    const pct = ratio === null ? 0 : Math.max(0, Math.min(100, ratio * 100));
    return `
      <div class="jauge-peage">
        <div class="jauge-peage-etiquette"><span>${echappeHtml(etiquette)}</span><strong>${ratio === null ? "—" : formatPct(ratio)}</strong></div>
        <div class="jauge-peage-piste"><div class="jauge-peage-remplissage" style="width:${pct}%"></div></div>
        ${note ? `<p class="jauge-peage-note">${echappeHtml(note)}</p>` : ""}
      </div>`;
  }

  const LIBELLES_H2H = {
    CORROBORE: "Corroboré",
    CONTREDIT: "Contredit",
    NEUTRE: "Neutre",
    INSUFFISANT: "Insuffisant",
  };

  function construitDistributionH2H(h2hInformatif) {
    const total = Object.values(h2hInformatif || {}).reduce((a, b) => a + b, 0);
    if (!total) {
      return `<p class="etat-vide-systeme">Aucune donnée H2H informative sur ce run.</p>`;
    }
    const segments = Object.keys(LIBELLES_H2H).map((cle) => {
      const n = (h2hInformatif || {})[cle] || 0;
      const pct = (n / total) * 100;
      return pct > 0 ? `<span class="h2h-${cle}" style="width:${pct}%"></span>` : "";
    }).join("");
    const legende = Object.keys(LIBELLES_H2H).map((cle) => {
      const n = (h2hInformatif || {})[cle] || 0;
      return `<span><span class="puce h2h-${cle}" style="background:var(--surface-2)"></span>${echappeHtml(LIBELLES_H2H[cle])} : ${n}</span>`;
    }).join("");
    return `<div class="distribution-h2h">${segments}</div><div class="legende-h2h">${legende}</div>`;
  }

  function construitBlocTelemetrie(dernierRun) {
    const div = document.createElement("div");
    div.className = "bloc-systeme";

    if (!dernierRun) {
      div.innerHTML = `<h2>📊 Télémétrie par étage</h2><p class="etat-vide-systeme">Aucun run enregistré pour l'instant.</p>`;
      return div;
    }

    const peage1 = dernierRun.peage1 || {};
    const conv = dernierRun.filtre_convergence || {};
    const totalConv = (conv.eligibles || 0) + (conv.rejetes || 0);
    const motifs = conv.motifs_rejet || {};

    const rejetsProbabilite = (motifs.PROBABILITE_TROP_FAIBLE || 0) + (motifs.PROBABILITE_INDISPONIBLE || 0) + (motifs.PROBABILITE_INVALIDE || 0);
    const rejetsEdvCote = (motifs.COTE_HORS_INTERVALLE || 0) + (motifs.COTE_INVALIDE || 0) + (motifs.EDV_INSUFFISANTE || 0) + (motifs.EDV_INVALIDE || 0) + (motifs.EDV_INDISPONIBLE || 0);

    const ratioP1 = ratioSur(peage1.passes, dernierRun.marches_scannes);
    const ratioP2 = totalConv > 0 ? ratioSur(totalConv - rejetsProbabilite, totalConv) : null;
    const ratioP3 = totalConv > 0 ? ratioSur(totalConv - rejetsEdvCote, totalConv) : null;

    div.innerHTML = `
      <h2>📊 Télémétrie par étage (entonnoir réel du pipeline)</h2>
      ${construitJaugePeage("P1 (Matrice) — score ≥ 0,85", ratioP1, "Part des marchés ayant passé le Péage 1 (matrice_croisement).")}
      ${construitJaugePeage("P2 (Poisson) — probabilité ≥ 60 %", ratioP2, "Approximation : évaluation séquentielle avec sortie anticipée -- un marché rejeté plus loin (cote, EDV, robustesse) a déjà passé ce test.")}
      ${construitJaugePeage("P3 (EDV / cote) — fenêtre [1,26 - 1,80]", ratioP3, "Regroupe cote hors intervalle ET EDV insuffisante -- deux vérifications distinctes dans le code, agrégées ici.")}
      <div class="jauge-peage">
        <div class="jauge-peage-etiquette"><span>P4 (H2H) — distribution de fiabilité</span></div>
        ${construitDistributionH2H(dernierRun.h2h_informatif)}
        <p class="jauge-peage-note">Le H2H est un arbitre informatif -- il n'élimine jamais un marché, contrairement aux trois étages ci-dessus.</p>
      </div>`;
    return div;
  }

  // -------------------------------------------------------------------
  // Orchestration
  // -------------------------------------------------------------------

  function chargeEtAffiche() {
    const maj = document.getElementById("maj-admin");
    const racine = document.getElementById("contenu-admin");
    maj.textContent = "Chargement…";

    const chargeJson = (url) => fetch(`${url}?_=${Date.now()}`).then((r) => (r.ok ? r.json() : null)).catch(() => null);

    Promise.all([
      chargeJson("data/audit_status.json"),
      chargeJson("data/audit_telemetry.json"),
    ]).then(([status, telemetrie]) => {
      racine.innerHTML = "";
      const runs = (telemetrie && telemetrie.runs) || [];
      const dernierRun = runs.length ? runs[runs.length - 1] : null;

      racine.appendChild(construitBlocCockpit(status));
      racine.appendChild(construitBlocDisjoncteurs(dernierRun));
      racine.appendChild(construitBlocTelemetrie(dernierRun));

      maj.textContent = status && status.horodatage_controle
        ? `Dernier contrôle d'audit : ${formatDate(status.horodatage_controle)}`
        : "Aucune donnée d'audit disponible pour l'instant.";
    }).catch((e) => {
      maj.textContent = "Erreur de chargement : " + e.message;
      console.error(e);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", installeAuthentification);
  else installeAuthentification();
})();
