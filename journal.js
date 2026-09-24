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

  function reussiteTxt(s) {
    var joues = s.paris - (s.rembourses || 0);
    return (s.gagnes != null ? s.gagnes + "/" + joues + " · " : "") + pct(s.reussite);
  }

  function tableau(lignes, opts) {
    opts = opts || {};
    if (!lignes || !lignes.length) return '<p class="jr-vide">Pas encore assez de données.</p>';
    var limite = opts.limite || 12;
    var id = "t" + Math.random().toString(36).slice(2);
    var nomSeg = opts.nom || segmentLisible;
    var html = '<div class="jr-table-wrap"><table class="jr-table" id="' + id + '"><thead><tr><th>' + esc(opts.titre || "Segment") +
      "</th><th>Matchs</th><th>Réussite</th><th>Il faut</th><th>Cote moy.</th><th>ROI</th><th>Statut</th></tr></thead><tbody>";
    lignes.forEach(function (s, i) {
      var cache = i >= limite;
      html += "<tr" + (cache ? ' class="cache" style="display:none"' : "") + "><td>" + esc(nomSeg(s.segment)) + "</td><td>" + s.matchs +
        "</td><td>" + reussiteTxt(s) + "</td><td>" + pct(s.reussite_necessaire) + "</td><td>" +
        (s.cote_moyenne != null ? String(s.cote_moyenne).replace(".", ",") : "—") + '</td><td class="' + classe(s.roi) + '">' +
        pct(s.roi, true) + "</td><td>" + badge(s.statut) + "</td></tr>";
    });
    html += "</tbody></table></div>";
    if (lignes.length > limite) html += '<button type="button" class="jr-plus" data-table="' + id + '">Afficher les ' + lignes.length + " lignes</button>";
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

  var PHRASE_STATUT = {
    A_JOUER: "Rentable de façon prouvée : gain sur toute la période, sur chacune de ses deux moitiés, et marge d'erreur entièrement positive.",
    A_SURVEILLER: "Gagnant sur toute la période et sur chacune de ses deux moitiés, mais pas encore assez de matchs pour exclure la chance : mise symbolique.",
    A_EVITER: "Perdant de façon prouvée : à ne pas jouer.",
    NEUTRE: "Ni gagnant ni perdant de façon nette."
  };

  function lieuPreuve(p) {
    var parties = String(p.segment || "").split(" | ");
    if (p.niveau === "ligue_marche") return "dans " + parties[0] + ", ce marché";
    if (p.niveau === "ligue_famille") return "dans " + parties[0] + ", la famille « " + parties[1] + " »";
    if (p.niveau === "marches") return "tous championnats confondus, ce marché";
    return "ce segment";
  }

  /* Texte de la base d'un conseil, en clair : quels matchs, combien de gains, quelle rentabilité. */
  function preuveTexte(p) {
    if (!p) return "Base : aucune donnée passée pour ce championnat et ce marché.";
    var joues = p.paris - (p.rembourses || 0);
    return "<b>Base :</b> " + esc(lieuPreuve(p)) + " a été coté par BetPawa sur " + p.matchs + " match(s) déjà joué(s). " +
      "Il a gagné " + (p.gagnes != null ? p.gagnes + " fois sur " + joues : pct(p.reussite)) + " (" + pct(p.reussite) + "), à une cote moyenne de " +
      String(p.cote_moyenne).replace(".", ",") + " ; il fallait " + pct(p.reussite_necessaire) + " pour ne rien perdre. " +
      "En misant 1 à chaque fois : " + '<span class="' + classe(p.roi) + '">' + pct(p.roi, true) + "</span>" +
      " (1re moitié " + pct(p.roi_moitie_1, true) + ", 2e moitié " + pct(p.roi_moitie_2, true) + "). " + esc(PHRASE_STATUT[p.statut] || "");
  }

  function dateCourte(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    return m ? m[3] + "/" + m[2] : esc(iso);
  }

  /* Même en-tête que les cartes de match d'archetype.html (.ax-match / .ax-ligne-match / .ax-horaire). */
  function carteConseil(c) {
    return '<section class="ax-carte jr-conseil" data-statut="' + esc(c.statut_journal) + '">' +
      '<div class="ax-match"><div class="ax-ligne-match">' +
      '<span class="ax-equipe ax-dom">' + esc(c.domicile) + "</span>" +
      '<div class="ax-horaire"><strong>' + esc(c.heure || "—") + "</strong><span>" + dateCourte(c.date) + "</span></div>" +
      '<span class="ax-equipe ax-ext">' + esc(c.exterieur) + "</span></div>" +
      '<div class="ax-match-bas"><p class="ax-competition">' + esc(c.ligue) + "</p>" + badge(c.statut_journal) + "</div></div>" +
      '<div class="jr-conseil-corps"><div class="jr-marche"><span>' + esc(lisible(c.marche)) + '</span><span class="jr-cote">' +
      esc(String(c.cote).replace(".", ",")) + "</span></div>" +
      '<div class="jr-preuve">' + preuveTexte(c.preuve) + "</div>" +
      (c.betpawa_url ? '<a class="jr-lien" href="' + esc(c.betpawa_url) + '" target="_blank" rel="noopener">Ouvrir sur BetPawa →</a>' : "") +
      "</div></section>";
  }

  function afficherConseils(j) {
    var zone = document.getElementById("conseils");
    var c = j.conseils || [];
    var nbJouer = c.filter(function (x) { return x.statut_journal === "A_JOUER"; }).length;
    var alerte = nbJouer
      ? '<div class="jr-alerte ok">' + nbJouer + " marché(s) « à jouer » : preuve statistique complète sur les données passées.</div>"
      : '<div class="jr-alerte info">Aucun marché n\'a encore de preuve statistique complète. Les marchés « à surveiller » sont positifs mais pas prouvés : mise symbolique uniquement, le journal les confirmera ou les écartera au fil des nuits.</div>';
    document.getElementById("filtres-conseils").insertAdjacentHTML("afterend", alerte);
    if (!c.length) {
      zone.innerHTML = '<div class="ax-etat-vide"><strong>Aucun conseil pour le moment</strong><p>Aucun marché à venir dans une zone favorable.</p></div>';
      return;
    }
    zone.innerHTML = c.map(carteConseil).join("");
    document.querySelectorAll("#filtres-conseils button").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#filtres-conseils button").forEach(function (x) { x.classList.remove("actif"); });
        b.classList.add("actif");
        var f = b.getAttribute("data-f");
        zone.querySelectorAll(".jr-conseil").forEach(function (el) {
          el.style.display = (f === "tous" || el.getAttribute("data-statut") === f) ? "" : "none";
        });
      });
    });
  }

  function afficherFiches(j) {
    var s = j.segments || {};
    var parLigue = {};
    (s.ligue_marche || []).forEach(function (x) {
      var l = String(x.segment).split(" | ")[0];
      (parLigue[l] = parLigue[l] || []).push(x);
    });
    var ligues = (s.ligues || []).slice().sort(function (a, b) { return b.matchs - a.matchs; });
    var html = "";
    ligues.forEach(function (lg) {
      var marches = (parLigue[lg.segment] || []).slice().sort(function (a, b) { return (b.reussite || 0) - (a.reussite || 0); });
      if (!marches.length) return;
      var gagnants = marches.filter(function (m) { return m.roi > 0; }).length;
      var piege = marches.filter(function (m) { return (m.reussite || 0) >= 0.65 && m.roi < 0; }).length;
      html += '<details class="jr-fiche"><summary><span class="jr-fiche-nom">' + esc(lg.segment) + "</span>" +
        '<span class="jr-fiche-info">' + lg.matchs + " matchs · " + gagnants + " marché(s) gagnant(s)</span></summary>" +
        '<p class="jr-aide" style="margin:8px 0">Coût moyen BetPawa dans ce championnat : <span class="' + classe(lg.roi) + '">' + pct(lg.roi, true) + "</span>." +
        (piege ? " " + piege + " marché(s) gagnent souvent (65 % ou plus) mais perdent de l'argent : BetPawa les cote trop bas." : "") + "</p>" +
        tableau(marches, { titre: "Marché", limite: 10, nom: function (seg) { return lisible(String(seg).split(" | ")[1]); } }) + "</details>";
    });
    document.getElementById("fiches").innerHTML = html || '<p class="jr-vide">Pas encore assez de données.</p>';
  }

  var RANG_LIB = { P1: "Favori du Modèle", P2: "Value Bet", P3: "Coup de Poker" };

  function carteSelection(x, moteur) {
    return '<section class="ax-carte jr-selection" data-moteur="' + esc(moteur) + '">' +
      '<div class="ax-match"><div class="ax-ligne-match">' +
      '<span class="ax-equipe ax-dom">' + esc(x.domicile) + "</span>" +
      '<div class="ax-horaire"><strong>' + esc(x.heure || "—") + "</strong><span>" + dateCourte(x.date) + "</span></div>" +
      '<span class="ax-equipe ax-ext">' + esc(x.exterieur) + "</span></div>" +
      '<div class="ax-match-bas"><p class="ax-competition">' + esc(x.ligue) + " · " + esc(NOMS_MOTEUR[moteur] || moteur) + "</p>" +
      badge(x.statut_journal) + "</div></div>" +
      '<div class="jr-conseil-corps"><div class="jr-marche"><span>' + esc(RANG_LIB[x.rang] || x.rang) + " · " + esc(lisible(x.marche)) +
      '</span><span class="jr-cote">' + esc(x.cote == null ? "—" : String(x.cote).replace(".", ",")) + "</span></div>" +
      (x.justification ? '<div class="jr-preuve"><b>Raison du moteur :</b> ' + esc(x.justification) +
        (x.probabilite != null ? " (probabilité modèle " + pct(x.probabilite) + ")" : "") + "</div>" : "") +
      '<div class="jr-preuve">' + (x.statut_journal === "COTE_NON_BETPAWA"
        ? "<b>Base :</b> la cote de ce match ne vient pas de BetPawa : pari non vérifiable sur BetPawa."
        : preuveTexte(x.preuve)) + "</div>" +
      (x.betpawa_url && x.cotes_betpawa ? '<a class="jr-lien" href="' + esc(x.betpawa_url) + '" target="_blank" rel="noopener">Ouvrir sur BetPawa →</a>' : "") +
      "</div></section>";
  }

  function afficherSelectionsMoteurs(j) {
    var zone = document.getElementById("selections-moteurs");
    var pr = j.pronostics || {};
    var html = "";
    Object.keys(NOMS_MOTEUR).forEach(function (m) {
      var sel = (pr[m] || {}).selections || [];
      html += sel.length ? sel.map(function (x) { return carteSelection(x, m); }).join("")
        : '<div class="ax-etat-vide jr-selection" data-moteur="' + m + '"><strong>Aucune sélection à venir</strong><p>' +
          esc(NOMS_MOTEUR[m]) + " n'a retenu aucun marché pour les prochains matchs.</p></div>";
    });
    zone.innerHTML = html;
    function filtre(m) {
      zone.querySelectorAll(".jr-selection").forEach(function (el) { el.style.display = el.getAttribute("data-moteur") === m ? "" : "none"; });
    }
    document.querySelectorAll("#filtres-moteurs button").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#filtres-moteurs button").forEach(function (x) { x.classList.remove("actif"); });
        b.classList.add("actif");
        filtre(b.getAttribute("data-f"));
      });
    });
    filtre("moteur_v2_6_9");
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
    document.getElementById("resume").innerHTML = '<h2 class="jr-titre">En bref</h2><div class="jr-chiffres">' +
      '<div class="jr-chiffre"><span>Matchs BetPawa terminés</span><b>' + (d.matchs || 0) + "</b></div>" +
      '<div class="jr-chiffre"><span>Cotes réglées</span><b>' + (d.cotes_reglees || 0) + "</b></div>" +
      '<div class="jr-chiffre"><span>Coût moyen BetPawa</span><b class="' + classe(cg.roi) + '">' + pct(cg.roi, true) + "</b></div>" +
      '<div class="jr-chiffre"><span>Zones à jouer / à surveiller</span><b>' + compte("A_JOUER") + " / " + compte("A_SURVEILLER") + "</b></div>" +
      '</div><p class="jr-aide" style="margin:10px 0 0">Période : ' + esc(p) +
      ". Le « coût moyen » est ce que l'on perd en misant 1 sur toutes les cotes BetPawa relevées.</p>";
  }

  function afficherMoteurs(j) {
    var m = j.moteurs || {};
    var html = "";
    Object.keys(NOMS_MOTEUR).forEach(function (k) {
      var e = m[k] || {};
      html += '<h3 class="jr-sous-titre">' + esc(NOMS_MOTEUR[k]) + "</h3>";
      if (!e.global) { html += '<p class="jr-vide">' + esc(e.note || "Pas encore de résultat.") + "</p>"; return; }
      var g = e.global;
      html += '<p class="jr-aide">' + g.paris + " sélections réglées sur " + g.matchs + " matchs BetPawa — ROI <span class=\"" + classe(g.roi) + "\">" +
        pct(g.roi, true) + "</span>, IC 95 % " + ic(g) + ", réussite " + pct(g.reussite) + ", cote moyenne " + g.cote_moyenne + ".</p>";
      html += tableau(e.familles, { titre: "Famille de marchés", limite: 8 });
      html += '<p class="jr-aide" style="margin:10px 0 4px">Par championnat :</p>' + tableau(e.ligues, { titre: "Championnat", limite: 8 });
    });
    document.getElementById("moteurs").innerHTML = html;
  }

  function afficherRegles(j) {
    var r = j.regles || {};
    var d = j.donnees || {};
    var inc = d.cotes_incoherentes_retirees || {};
    var nbInc = Object.keys(inc).reduce(function (a, k) { return a + inc[k]; }, 0);
    var inconnus = Object.keys(d.libelles_non_reconnus || {});
    var html = '<ul class="jr-liste">' +
      "<li>" + badge("A_JOUER") + " " + esc(r.A_JOUER) + "</li>" +
      "<li>" + badge("A_SURVEILLER") + " " + esc(r.A_SURVEILLER) + "</li>" +
      "<li>" + badge("A_EVITER") + " " + esc(r.A_EVITER) + "</li>" +
      "<li>" + badge("NEUTRE") + " " + esc(r.NEUTRE) + "</li></ul>" +
      '<p class="jr-aide" style="margin-top:10px">' + esc(r.avertissement || "") + "</p>" +
      '<p class="jr-aide">L\'intervalle de confiance (IC 95 %) est calculé en tirant au hasard des matchs entiers : les cotes d\'un même match sont liées entre elles.</p>' +
      '<p class="jr-aide">Qualité : ' + nbInc + " cote(s) de handicap incohérente(s) avec le 1X2 du même match ont été retirées (erreurs de relevé probables)." +
      (inconnus.length ? " Libellés non reconnus : " + esc(inconnus.join(", ")) + "." : "") + "</p>";
    document.getElementById("regles").innerHTML = html;
  }

  function afficher(j) {
    document.getElementById("maj").textContent = "Mis à jour : " + (j.genere_le || "—");
    afficherResume(j);
    afficherConseils(j);
    afficherFiches(j);
    afficherSelectionsMoteurs(j);
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

  /* Mode nuit : même bascule et même clé que archetype.js (archetype_theme_nuit). */
  (function installeThemeNuit() {
    var bouton = document.getElementById("ax-bouton-theme");
    if (!bouton) return;
    function applique(nuit) {
      document.body.classList.toggle("theme-nuit", nuit);
      bouton.textContent = nuit ? "\u2600" : "\u263E";
      bouton.setAttribute("aria-label", nuit ? "Activer le mode clair" : "Activer le mode nuit");
    }
    var nuit = false;
    try { nuit = localStorage.getItem("archetype_theme_nuit") === "1"; } catch (e) { /* stockage indisponible */ }
    applique(nuit);
    bouton.addEventListener("click", function () {
      var suivant = !document.body.classList.contains("theme-nuit");
      try { localStorage.setItem("archetype_theme_nuit", suivant ? "1" : "0"); } catch (e) { /* ignoré */ }
      applique(suivant);
    });
  })();

  fetch("journal.json?t=" + Date.now(), { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(afficher)
    .catch(function (e) {
      document.getElementById("maj").textContent = "Journal indisponible (" + e.message + "). Il est produit chaque nuit par le pipeline.";
    });
})();
