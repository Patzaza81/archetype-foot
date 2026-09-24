/* pronostics_shrink.js — page des pronostics du second moteur (shrink_v1), AJOUT 24/09/2026.
   Lit journal.json (section "pronostics.shrink_v1" et "moteurs.shrink_v1"), produit chaque nuit par
   journal_rentabilite.py. Affichage seul. */
(function () {
  "use strict";
  var MOTEUR = "shrink_v1";
  var NOMS_STATUT = { A_JOUER: "À jouer", A_SURVEILLER: "À surveiller", A_EVITER: "À éviter", NEUTRE: "Neutre",
                      INCONNU: "Zone inconnue", COTE_NON_BETPAWA: "Cote non BetPawa" };
  var NOMS_NIVEAU = { ligue_marche: "ce championnat, ce marché", ligue_famille: "ce championnat, cette famille",
                      marches: "ce marché, tous championnats" };

  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function pct(x, signe) {
    if (x == null || isNaN(x)) return "—";
    return (signe && x > 0 ? "+" : "") + (x * 100).toFixed(1).replace(".", ",") + " %";
  }
  function classe(x) { return x == null ? "" : (x > 0 ? "pos" : (x < 0 ? "neg" : "")); }
  function badge(st) { return '<span class="jr-badge b-' + esc(st) + '">' + esc(NOMS_STATUT[st] || st) + "</span>"; }
  function lisible(lib) {
    var m = /^Handicap (-?\d+(?:\.\d+)?) - (Domicile|Extérieur|Exterieur)$/.exec(String(lib || "").trim());
    if (!m) return lib;
    var ligne = parseFloat(m[1]), dom = m[2] === "Domicile", propre = dom ? ligne : -ligne;
    return "Handicap " + (dom ? "domicile " : "extérieur ") + (propre > 0 ? "+" : "") + String(propre).replace(".", ",");
  }
  function ic(s) { return s && s.ic95 ? "[" + pct(s.ic95[0], true) + " ; " + pct(s.ic95[1], true) + "]" : "—"; }

  function carte(x) {
    var p = x.preuve;
    var preuve = p ? "Zone (" + esc(NOMS_NIVEAU[p.niveau] || p.niveau) + ") : " + p.matchs + " matchs, ROI " + pct(p.roi, true) +
      ", IC 95 % " + ic(p) + "." : "";
    return '<div class="jr-carte" data-statut="' + esc(x.statut_journal) + '"><div class="jr-carte-haut"><div><div class="jr-match">' +
      esc(x.domicile) + " – " + esc(x.exterieur) + '</div><div class="jr-meta">' + esc(x.date) + " · " + esc(x.heure || "") + " · " +
      esc(x.ligue) + "</div></div>" + badge(x.statut_journal) + '</div><div class="jr-marche">' + esc(x.rang) + " · " +
      esc(lisible(x.marche)) + " — cote <b>" + esc(x.cote == null ? "—" : x.cote) + "</b>" +
      (x.probabilite != null ? ' <span class="jr-meta">(probabilité moteur ' + pct(x.probabilite) + ")</span>" : "") + "</div>" +
      (preuve ? '<div class="jr-preuve">' + preuve + "</div>" : "") +
      (x.justification ? '<div class="jr-justif">' + esc(x.justification) + "</div>" : "") +
      (x.betpawa_url && x.cotes_betpawa ? '<a class="jr-lien" href="' + esc(x.betpawa_url) + '" target="_blank" rel="noopener">Ouvrir sur BetPawa</a>' : "") +
      "</div>";
  }

  function filtrer(f) {
    document.querySelectorAll("#liste .jr-carte").forEach(function (el) {
      var st = el.getAttribute("data-statut");
      var voir = f === "tous" || (f === "jouables" && st !== "A_EVITER" && st !== "COTE_NON_BETPAWA") ||
                 (f === "favorables" && (st === "A_JOUER" || st === "A_SURVEILLER"));
      el.style.display = voir ? "" : "none";
    });
    var visibles = Array.prototype.filter.call(document.querySelectorAll("#liste .jr-carte"), function (el) { return el.style.display !== "none"; });
    document.getElementById("vide").style.display = visibles.length ? "none" : "";
  }

  function afficher(j) {
    var pr = (j.pronostics || {})[MOTEUR] || {};
    var m = (j.moteurs || {})[MOTEUR] || {};
    document.getElementById("maj").textContent = "Journal du " + (j.genere_le || "—") + " · sélections calculées le " + (pr.genere_le || "—");
    var g = m.global;
    document.getElementById("bilan").innerHTML = "<h2>Résultats réels de shrink_v1 sur BetPawa</h2>" + (g
      ? '<p class="jr-aide">' + g.paris + " sélections réglées — ROI <span class=\"" + classe(g.roi) + "\">" + pct(g.roi, true) +
        "</span>, IC 95 % " + ic(g) + ", réussite " + pct(g.reussite) + ".</p>"
      : '<p class="jr-vide">' + esc(m.note || "Pas encore de sélection réglée.") + " Le bilan se remplit automatiquement au fil des nuits.</p>");
    var sel = pr.selections || [];
    document.getElementById("liste").innerHTML = sel.map(carte).join("") +
      '<p id="vide" class="jr-vide" style="display:none">Aucune sélection dans ce filtre pour les matchs à venir.</p>';
    document.querySelectorAll("#filtres button").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#filtres button").forEach(function (x) { x.classList.remove("actif"); });
        b.classList.add("actif");
        filtrer(b.getAttribute("data-f"));
      });
    });
    filtrer("favorables");
  }

  fetch("journal.json?t=" + Date.now(), { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(afficher)
    .catch(function (e) {
      document.getElementById("maj").textContent = "Journal indisponible (" + e.message + "). Il est produit chaque nuit par le pipeline.";
    });
})();
