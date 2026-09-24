/* journal.js — page Journal de rentabilité (AJOUT 24/09/2026). Lit journal.json (produit chaque nuit par
   journal_rentabilite.py dans le pipeline GitHub Actions). Aucune donnée n'est calculée ici : affichage seul. */
(function () {
  "use strict";

  var NOMS_STATUT = { A_JOUER: "À jouer", A_SURVEILLER: "À surveiller", A_EVITER: "À éviter", NEUTRE: "Neutre",
                      INCONNU: "Inconnu", COTE_NON_BETPAWA: "Cote non BetPawa" };
  var NOMS_NIVEAU = { ligue_marche: "ce championnat, ce marché", ligue_famille: "ce championnat, cette famille de marchés",
                      marches: "ce marché, tous championnats", ligues: "ce championnat", tranches_de_cote: "cette tranche de cote" };
  var NOMS_MOTEUR = { moteur_v2_6_9: "Moteur principal (v2.6.9)", shrink_v1: "Moteur shrink_v1 (en test)" };

  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function pct(x, signe) {
    if (x == null || isNaN(x)) return "—";
    var v = (x * 100).toFixed(1).replace(".", ",") + " %";
    return (signe && x > 0 ? "+" : "") + v;
  }
  function classe(x) { return x == null ? "" : (x > 0 ? "pos" : (x < 0 ? "neg" : "")); }
  function badge(st) { return '<span class="jr-badge b-' + esc(st) + '">' + esc(NOMS_STATUT[st] || st) + "</span>"; }

  /* Libellé BetPawa -> texte lisible. Handicaps : la ligne des libellés est celle de l'équipe à domicile
     (« Handicap -0.5 - Extérieur » = extérieur +0.5) -- même convention que journal_rentabilite.ligne_propre. */
  function lisible(lib) {
    var m = /^Handicap (-?\d+(?:\.\d+)?) - (Domicile|Extérieur|Exterieur)$/.exec(String(lib || "").trim());
    if (!m) return lib;
    var ligne = parseFloat(m[1]);
    var dom = m[2] === "Domicile";
    var propre = dom ? ligne : -ligne;
    var txt = (propre > 0 ? "+" : "") + String(propre).replace(".", ",");
    return "Handicap " + (dom ? "domicile " : "extérieur ") + txt;
  }
  function segmentLisible(seg) {
    return String(seg).split(" | ").map(lisible).join(" — ");
  }
  function ic(s) { return s.ic95 ? "[" + pct(s.ic95[0], true) + " ; " + pct(s.ic95[1], true) + "]" : "—"; }

  function tableau(lignes, opts) {
    opts = opts || {};
    if (!lignes || !lignes.length) return '<p class="jr-vide">Pas encore assez de données.</p>';
    var limite = opts.limite || 12;
    var id = "t" + Math.random().toString(36).slice(2);
    var html = '<div class="jr-table-wrap"><table class="jr-table" id="' + id + '"><thead><tr><th>' + esc(opts.titre || "Segment") +
      "</th><th>Matchs</th><th>ROI</th><th>IC 95 %</th><th>1re / 2e moitié</th><th>Statut</th></tr></thead><tbody>";
    lignes.forEach(function (s, i) {
      html += '<tr class="' + (i >= limite ? "cache" : "") + '"' + (i >= limite ? ' style="display:none"' : "") + "><td>" +
        esc(segmentLisible(s.segment)) + "</td><td>" + s.matchs + '</td><td class="' + classe(s.roi) + '">' + pct(s.roi, true) +
        "</td><td>" + ic(s) + "</td><td>" + pct(s.roi_moitie_1, true) + " / " + pct(s.roi_moitie_2, true) + "</td><td>" +
        badge(s.statut) + "</td></tr>";
    });
    html += "</tbody></table></div>";
    if (lignes.length > limite) html += '<button class="jr-plus" data-table="' + id + '">Afficher les ' + lignes.length + " lignes</button>";
    return html;
  }

  function brancherBoutonsPlus(racine) {
    racine.querySelectorAll(".jr-plus").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#" + b.getAttribute("data-table") + " tr.cache").forEach(function (tr) { tr.style.display = ""; });
        b.remove();
      });
    });
  }

  function preuveTexte(p) {
    if (!p) return "";
    return "Preuve (" + esc(NOMS_NIVEAU[p.niveau] || p.niveau) + ") : " + p.matchs + " matchs, ROI " + pct(p.roi, true) +
      ", IC 95 % " + ic(p) + ", moitiés " + pct(p.roi_moitie_1, true) + " / " + pct(p.roi_moitie_2, true) + ".";
  }

  function carteConseil(c) {
    return '<div class="jr-carte" data-statut="' + esc(c.statut_journal) + '"><div class="jr-carte-haut"><div><div class="jr-match">' +
      esc(c.domicile) + " – " + esc(c.exterieur) + '</div><div class="jr-meta">' + esc(c.date) + " · " + esc(c.heure || "") +
      " · " + esc(c.ligue) + "</div></div>" + badge(c.statut_journal) + '</div><div class="jr-marche">' + esc(lisible(c.marche)) +
      " — cote <b>" + esc(c.cote) + '</b></div><div class="jr-preuve">' + preuveTexte(c.preuve) + "</div>" +
      (c.betpawa_url ? '<a class="jr-lien" href="' + esc(c.betpawa_url) + '" target="_blank" rel="noopener">Ouvrir sur BetPawa</a>' : "") +
      "</div>";
  }

  function afficherConseils(j) {
    var zone = document.getElementById("conseils");
    var c = j.conseils || [];
    var nbJouer = c.filter(function (x) { return x.statut_journal === "A_JOUER"; }).length;
    var alerte = nbJouer
      ? '<div class="jr-alerte ok">' + nbJouer + " marché(s) « à jouer » : preuve statistique complète sur les données passées.</div>"
      : '<div class="jr-alerte info">Aucun marché n\'a encore de preuve statistique complète. Les marchés « à surveiller » sont positifs mais pas prouvés : mise symbolique uniquement, le journal les confirmera ou les écartera au fil des nuits.</div>';
    if (!c.length) { zone.innerHTML = alerte + '<p class="jr-vide">Aucun marché à venir dans une zone favorable.</p>'; return; }
    zone.innerHTML = alerte + c.map(carteConseil).join("");
    document.querySelectorAll("#filtres-conseils button").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#filtres-conseils button").forEach(function (x) { x.classList.remove("actif"); });
        b.classList.add("actif");
        var f = b.getAttribute("data-f");
        zone.querySelectorAll(".jr-carte").forEach(function (el) {
          el.style.display = (f === "tous" || el.getAttribute("data-statut") === f) ? "" : "none";
        });
      });
    });
  }

  function afficherResume(j) {
    var d = j.donnees || {};
    var cg = d.cout_global_betpawa || {};
    var p = d.periode ? d.periode[0] + " → " + d.periode[1] : "—";
    var cs = j.comptage_statuts || {};
    function compte(st) {
      var n = 0;
      ["ligues", "marches", "ligue_famille", "ligue_marche"].forEach(function (k) { n += (cs[k] || {})[st] || 0; });
      return n;
    }
    document.getElementById("resume").innerHTML = '<div class="jr-chiffres">' +
      '<div class="jr-chiffre"><span>Matchs BetPawa terminés</span><b>' + (d.matchs || 0) + "</b></div>" +
      '<div class="jr-chiffre"><span>Cotes réglées</span><b>' + (d.cotes_reglees || 0) + "</b></div>" +
      '<div class="jr-chiffre"><span>Coût moyen BetPawa</span><b class="' + classe(cg.roi) + '">' + pct(cg.roi, true) + "</b></div>" +
      '<div class="jr-chiffre"><span>Segments à jouer / à surveiller</span><b>' + compte("A_JOUER") + " / " + compte("A_SURVEILLER") + "</b></div>" +
      '</div><p class="jr-aide" style="margin-top:8px">Période : ' + esc(p) +
      ". Le « coût moyen » est ce que l'on perd en misant 1 sur toutes les cotes BetPawa relevées.</p>";
  }

  function afficherMoteurs(j) {
    var m = j.moteurs || {};
    var html = "";
    Object.keys(NOMS_MOTEUR).forEach(function (k) {
      var e = m[k] || {};
      html += "<h3 style=\"font-size:16px;margin:10px 0 6px\">" + esc(NOMS_MOTEUR[k]) + "</h3>";
      if (!e.global) { html += '<p class="jr-vide">' + esc(e.note || "Pas encore de résultat.") + "</p>"; return; }
      var g = e.global;
      html += '<p class="jr-aide">' + g.paris + " sélections réglées sur " + g.matchs + " matchs BetPawa — ROI <span class=\"" + classe(g.roi) + "\">" +
        pct(g.roi, true) + "</span>, IC 95 % " + ic(g) + ", réussite " + pct(g.reussite) + ", cote moyenne " + g.cote_moyenne + ".</p>";
      html += tableau(e.familles, { titre: "Famille de marchés", limite: 8 });
    });
    document.getElementById("moteurs").innerHTML = html;
  }

  function afficherRegles(j) {
    var r = j.regles || {};
    var d = j.donnees || {};
    var inc = d.cotes_incoherentes_retirees || {};
    var nbInc = Object.keys(inc).reduce(function (a, k) { return a + inc[k]; }, 0);
    var inconnus = Object.keys(d.libelles_non_reconnus || {});
    var html = "<ul style=\"margin:0;padding-left:18px;font-size:14px\">" +
      "<li>" + badge("A_JOUER") + " " + esc(r.A_JOUER) + "</li>" +
      "<li>" + badge("A_SURVEILLER") + " " + esc(r.A_SURVEILLER) + "</li>" +
      "<li>" + badge("A_EVITER") + " " + esc(r.A_EVITER) + "</li>" +
      "<li>" + badge("NEUTRE") + " " + esc(r.NEUTRE) + "</li></ul>" +
      '<p class="jr-aide" style="margin-top:8px">' + esc(r.avertissement || "") + "</p>" +
      '<p class="jr-aide">L\'intervalle de confiance (IC 95 %) est calculé en tirant au hasard des matchs entiers : les cotes d\'un même match sont liées entre elles.</p>' +
      '<p class="jr-aide">Qualité : ' + nbInc + " cote(s) de handicap incohérente(s) avec le 1X2 du même match ont été retirées (erreurs de relevé probables)." +
      (inconnus.length ? " Libellés non reconnus : " + esc(inconnus.join(", ")) + "." : "") + "</p>";
    document.getElementById("regles").innerHTML = html;
  }

  function afficher(j) {
    document.getElementById("maj").textContent = "Mis à jour : " + (j.genere_le || "—");
    afficherResume(j);
    afficherConseils(j);
    var s = j.segments || {};
    document.getElementById("ligues").innerHTML = tableau(s.ligues, { titre: "Championnat" });
    document.getElementById("marches").innerHTML = tableau(s.marches, { titre: "Marché" });
    var lm = (s.ligue_marche || []).filter(function (x) { return x.statut !== "NEUTRE" && x.matchs >= 25; });
    document.getElementById("ligue_marche").innerHTML = tableau(lm, { titre: "Championnat — marché" });
    var ev = [];
    ["familles", "tranches_de_cote", "marches", "ligues"].forEach(function (k) {
      (s[k] || []).forEach(function (x) { if (x.statut === "A_EVITER") ev.push(x); });
    });
    ev.sort(function (a, b) { return a.roi - b.roi; });
    document.getElementById("eviter").innerHTML = tableau(ev, { titre: "Zone", limite: 10 });
    afficherMoteurs(j);
    afficherRegles(j);
    brancherBoutonsPlus(document);
  }

  fetch("journal.json?t=" + Date.now(), { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(afficher)
    .catch(function (e) {
      document.getElementById("maj").textContent = "Journal indisponible (" + e.message + "). Il est produit chaque nuit par le pipeline.";
    });
})();
