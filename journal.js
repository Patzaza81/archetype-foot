/* Journal autonome : aucune décision de moteur n'est consommée ou publiée ici. */
(function () {
  "use strict";

  var MIN_MATCHS_AFFICHAGE = 10;
  var FIABILITE = { A_JOUER: "Prouvé", A_SURVEILLER: "À surveiller", NEUTRE: "Non confirmé" };
  var RANG_LIB = { P1: "Favori du Modèle", P2: "Value Bet", P3: "Coup de Poker" };
  var ORDRE = { A_JOUER: 0, A_SURVEILLER: 1, NEUTRE: 2 };

  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function pct(x, signe) {
    if (x == null || isNaN(x)) return "—";
    return (signe && x > 0 ? "+" : "") + (x * 100).toFixed(1).replace(".", ",") + " %";
  }
  function cote(x) { return x == null ? "—" : Number(x).toFixed(2).replace(".", ","); }
  function fiabilite(st) {
    var cls = st === "A_JOUER" ? "b-A_JOUER" : (st === "A_SURVEILLER" ? "b-A_SURVEILLER" : "b-NEUTRE");
    return '<span class="jr-badge ' + cls + '">' + esc(FIABILITE[st] || "Non confirmé") + "</span>";
  }
  var FIABILITE_COURT = { A_JOUER: "Prouvé", A_SURVEILLER: "Surveiller", NEUTRE: "Non conf." };
  function fiabiliteCourte(st) {
    var cls = st === "A_JOUER" ? "b-A_JOUER" : (st === "A_SURVEILLER" ? "b-A_SURVEILLER" : "b-NEUTRE");
    return '<span class="jr-badge jr-badge-court ' + cls + '">' + esc(FIABILITE_COURT[st] || "Non conf.") + "</span>";
  }
  function positif(s) { return s && s.roi > 0 && s.matchs >= MIN_MATCHS_AFFICHAGE; }
  function fiable(s) { return s && (s.statut === "A_JOUER" || s.statut === "A_SURVEILLER"); }
  function triGagnants(a, b) { return (ORDRE[a.statut] - ORDRE[b.statut]) || (b.roi - a.roi); }

  /* Handicaps : la ligne des libellés est celle de l'équipe à domicile (« Handicap -0.5 - Extérieur » = extérieur +0.5),
     même convention que journal_rentabilite.ligne_propre. */
  function lisible(lib) {
    var m = /^Handicap (-?\d+(?:\.\d+)?) - (Domicile|Extérieur|Exterieur)$/.exec(String(lib || "").trim());
    if (!m) return lib;
    var ligne = parseFloat(m[1]), dom = m[2] === "Domicile", propre = dom ? ligne : -ligne;
    return "Handicap " + (dom ? "domicile " : "extérieur ") + (propre > 0 ? "+" : "") + String(propre).replace(".", ",");
  }
  function dateCourte(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    return m ? m[3] + "/" + m[2] : esc(iso);
  }
  function gagnesTxt(s) { return s.gagnes + "/" + (s.paris - (s.rembourses || 0)); }

  function tableau(lignes, titre, nom) {
    var html = '<div class="jr-table-wrap"><table class="jr-table"><thead><tr><th>' + esc(titre) +
      "</th><th>Gagnés</th><th>Cote</th><th>ROI</th><th>Niveau</th></tr></thead><tbody>";
    lignes.forEach(function (s) {
      html += '<tr data-fiable="' + (fiable(s) ? 1 : 0) + '"><td>' + esc(nom(s.segment)) + "</td><td>" + gagnesTxt(s) + "<br><small>" + pct(s.reussite) + "</small>" +
        "</td><td>" + cote(s.cote_moyenne) + '</td><td class="pos">' + pct(s.roi, true) + "</td><td>" + fiabiliteCourte(s.statut) + "</td></tr>";
    });
    return html + "</tbody></table></div>";
  }

  /* ─────────── Résumé ─────────── */
  function afficherResume(j, rentables) {
    var d = j.donnees || {};
    var nbFiables = rentables.filter(fiable).length;
    var ligues = {};
    rentables.forEach(function (s) { ligues[String(s.segment).split(" | ")[0]] = 1; });
    var p = d.periode ? dateCourte(d.periode[0]) + " → " + dateCourte(d.periode[1]) : "—";
    document.getElementById("resume").innerHTML = '<h2 class="jr-titre">En bref</h2><div class="jr-chiffres">' +
      '<div class="jr-chiffre"><span>Matchs analysés</span><b>' + (d.matchs || 0) + "</b></div>" +
      '<div class="jr-chiffre"><span>Cotes BetPawa réglées</span><b>' + (d.cotes_reglees || 0) + "</b></div>" +
      '<div class="jr-chiffre"><span>Marchés rentables</span><b class="pos">' + rentables.length + "</b></div>" +
      '<div class="jr-chiffre"><span>Prouvés ou à surveiller</span><b class="pos">' + nbFiables + "</b></div>" +
      '</div><p class="jr-aide" style="margin:10px 0 0">' + Object.keys(ligues).length + " championnat(s) avec au moins un marché rentable · période " + esc(p) + ".</p>" +
      '<p class="jr-source"><b>D\'où viennent ces chiffres ?</b> D\'aucun moteur de prédiction. Chaque nuit, le script du journal prend les cotes BetPawa relevées avant chaque match terminé et les compare au score final : c\'est une comptabilité de résultats réels. Aucune rubrique moteur n’est publiée ici.</p>';
  }

  /* ─────────── Scrutage : marchés rentables par championnat ─────────── */
  function afficherRentables(j, rentables) {
    var s = j.segments || {};
    var parLigue = {};
    rentables.forEach(function (x) {
      var l = String(x.segment).split(" | ")[0];
      (parLigue[l] = parLigue[l] || []).push(x);
    });
    var ligues = Object.keys(parLigue).map(function (l) {
      var v = parLigue[l].sort(triGagnants);
      return { nom: l, marches: v, fiables: v.filter(fiable).length, meilleur: v[0] };
    }).sort(function (a, b) { return (b.fiables - a.fiables) || (b.marches.length - a.marches.length); });

    var generaux = (s.marches || []).filter(positif).sort(triGagnants);
    var html = "";
    if (generaux.length) {
      html += '<details class="jr-fiche" data-fiables="' + generaux.filter(fiable).length + '" open><summary><span class="jr-fiche-nom">Tous championnats confondus</span>' +
        '<span class="jr-fiche-info">' + generaux.length + " marché(s) rentable(s)</span></summary>" +
        '<div class="jr-lignes" data-tous="1">' + tableau(generaux, "Marché", lisible) + "</div></details>";
    }
    ligues.forEach(function (lg) {
      html += '<details class="jr-fiche" data-fiables="' + lg.fiables + '"><summary><span class="jr-fiche-nom">' + esc(lg.nom) + "</span>" +
        '<span class="jr-fiche-info">' + lg.marches.length + " marché(s) rentable(s)" + (lg.fiables ? " · " + lg.fiables + " prouvé(s) ou à surveiller" : "") +
        " · meilleur : " + esc(lisible(String(lg.meilleur.segment).split(" | ")[1])) + " " + pct(lg.meilleur.roi, true) + "</span></summary>" +
        tableau(lg.marches, "Marché", function (seg) { return lisible(String(seg).split(" | ")[1]); }) + "</details>";
    });
    var zone = document.getElementById("rentables");
    zone.innerHTML = html || '<p class="jr-vide">Aucun marché rentable pour l\'instant.</p>';

    document.querySelectorAll("#filtres-fiabilite button").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#filtres-fiabilite button").forEach(function (x) { x.classList.remove("actif"); });
        b.classList.add("actif");
        var seulFiables = b.getAttribute("data-f") === "fiables";
        zone.querySelectorAll(".jr-fiche").forEach(function (f) {
          f.style.display = (!seulFiables || Number(f.getAttribute("data-fiables")) > 0) ? "" : "none";
          f.querySelectorAll("tbody tr").forEach(function (tr) {
            tr.style.display = (!seulFiables || tr.getAttribute("data-fiable") === "1") ? "" : "none";
          });
        });
      });
    });
  }

  /* ─────────── Équipes à suivre (marché récurrent >= 70 %) ─────────── */
  function afficherEquipes(j) {
    var lignes = j.equipes_a_suivre || [];
    var zone = document.getElementById("equipes");
    var r = j.regles_equipes || {};
    if (!lignes.length) {
      zone.innerHTML = '<p class="jr-vide">Aucune équipe n\'atteint encore 70 % sur un marché avec au moins ' + (r.min_matchs || 5) + " matchs.</p>";
      return;
    }
    var parEquipe = {}, ordre = [];
    lignes.forEach(function (l) {
      var cle = l.equipe + " | " + l.ligue;
      if (!parEquipe[cle]) { parEquipe[cle] = []; ordre.push(cle); }
      parEquipe[cle].push(l);
    });
    zone.innerHTML = ordre.map(function (cle) {
      var ls = parEquipe[cle], t = ls[0], pm = null;
      ls.forEach(function (l) { if (l.prochain_match) pm = l.prochain_match; });
      var marches = ls.map(function (l) {
        var rent = l.roi_betpawa == null ? "Cote BetPawa : pas encore assez de relevés."
          : (l.roi_betpawa > 0 ? 'Rentable sur BetPawa : <span class="pos">' + pct(l.roi_betpawa, true) + "</span> sur " + l.paris_cotes + " cote(s) relevée(s)."
            : "Cote BetPawa souvent trop basse pour être rentable.");
        var cotePm = l.prochain_match && l.prochain_match.cote_betpawa ? ' <span class="jr-cote-pm">cote ' + cote(l.prochain_match.cote_betpawa) + "</span>" : "";
        return '<div class="jr-eq-marche"><div class="jr-eq-ligne"><b>' + esc(l.marche) + "</b>" + cotePm + '<span class="jr-eq-freq">' +
          l.gagnes + "/" + l.joues + " · " + pct(l.frequence) + "</span></div>" +
          '<div class="jr-eq-detail">En général : ' + pct(l.frequence_generale) + " des matchs. " + rent + "</div></div>";
      }).join("");
      var prochain = pm ? '<div class="jr-eq-prochain">Prochain match : ' + dateCourte(pm.date) + " à " + esc(pm.heure || "—") + " contre " +
        esc(pm.adversaire) + " (" + esc(pm.lieu) + ")" + (pm.betpawa_url ? ' · <a class="jr-lien" href="' + esc(pm.betpawa_url) +
        '" target="_blank" rel="noopener">BetPawa →</a>' : "") + "</div>" : "";
      var resume = ls.map(function (l) { return l.marche + " " + pct(l.frequence); }).join(" · ");
      return '<details class="jr-equipe" data-prochain="' + (pm ? 1 : 0) + '"><summary><div class="jr-eq-tete"><span class="jr-fiche-nom">' + esc(t.equipe) +
        '</span><span class="jr-badge b-A_JOUER">À suivre</span></div><div class="jr-fiche-info">' + esc(t.ligue) + " · " + t.joues + " matchs analysés</div>" +
        '<div class="jr-eq-resume">' + esc(resume) + "</div>" + prochain + "</summary>" + marches + "</details>";
    }).join("");
    document.querySelectorAll("#filtres-equipes button").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#filtres-equipes button").forEach(function (x) { x.classList.remove("actif"); });
        b.classList.add("actif");
        var f = b.getAttribute("data-f");
        zone.querySelectorAll(".jr-equipe").forEach(function (el) {
          el.style.display = (f === "toutes" || el.getAttribute("data-prochain") === "1") ? "" : "none";
        });
      });
    });
  }

  /* ─────────── Base d'un conseil, en clair ─────────── */
  function lieuPreuve(p) {
    var parties = String(p.segment || "").split(" | ");
    if (p.niveau === "ligue_marche") return "Dans " + parties[0] + ", ce marché";
    if (p.niveau === "ligue_famille") return "Dans " + parties[0] + ", la famille « " + parties[1] + " »";
    return "Tous championnats confondus, ce marché";
  }
  function preuveTexte(p) {
    return "<b>Base :</b> " + esc(lieuPreuve(p)) + " a été coté par BetPawa sur " + p.matchs + " match(s) déjà joué(s) : " +
      gagnesTxt(p) + " gagnés (" + pct(p.reussite) + "), cotes de " + cote(p.cote_min) + " à " + cote(p.cote_max) +
      " (moyenne " + cote(p.cote_moyenne) + "). En misant 1 à chaque fois : " +
      '<span class="pos">' + pct(p.roi, true) + "</span>. Fiabilité : " + fiabilite(p.statut) + ".";
  }
  function enteteMatch(x, sousTitre, st) {
    return '<div class="ax-match"><div class="ax-ligne-match">' +
      '<span class="ax-equipe ax-dom">' + esc(x.domicile) + "</span>" +
      '<div class="ax-horaire"><strong>' + esc(x.heure || "—") + "</strong><span>" + dateCourte(x.date) + "</span></div>" +
      '<span class="ax-equipe ax-ext">' + esc(x.exterieur) + "</span></div>" +
      '<div class="ax-match-bas"><p class="ax-competition">' + esc(sousTitre) + "</p>" + fiabilite(st) + "</div></div>";
  }
  function lienBetpawa(x) {
    return x.betpawa_url ? '<a class="jr-lien" href="' + esc(x.betpawa_url) + '" target="_blank" rel="noopener">Ouvrir sur BetPawa →</a>' : "";
  }

  function afficher(j) {
    document.getElementById("maj").textContent = "Mis à jour : " + (j.genere_le || "—");
    var rentables = ((j.segments || {}).ligue_marche || []).filter(positif);
    afficherResume(j, rentables);
    afficherRentables(j, rentables);
    afficherEquipes(j);
    afficherRegles(j);
  }

  /* Rubriques : un bouton par rubrique, une seule affichée à la fois (mémorisée dans l'adresse : journal.html#equipes). */
  (function installeOnglets() {
    var boutons = document.querySelectorAll("#onglets button");
    var noms = Array.prototype.map.call(boutons, function (b) { return b.getAttribute("data-onglet"); });
    function montre(nom, defiler) {
      if (noms.indexOf(nom) < 0) nom = noms[0];
      document.querySelectorAll(".jr-onglet").forEach(function (el) { el.hidden = el.getAttribute("data-onglet") !== nom; });
      boutons.forEach(function (b) { b.classList.toggle("actif", b.getAttribute("data-onglet") === nom); });
      if (defiler) document.getElementById("onglets").scrollIntoView({ behavior: "smooth", block: "start" });
    }
    boutons.forEach(function (b) {
      b.addEventListener("click", function () {
        var nom = b.getAttribute("data-onglet");
        try { history.replaceState(null, "", "#" + nom); } catch (e) { /* ignoré */ }
        montre(nom, true);
      });
    });
    montre((location.hash || "").replace("#", ""), false);
  })();

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

  fetch("data/journal_intelligence.json?t=" + Date.now(), { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(afficherObservatoire)
    .catch(function () {
      document.getElementById("observatoire-resume").innerHTML =
        '<p class="jr-aide">Observatoire en attente de sa première génération nocturne.</p>';
    });

  fetch("journal.json?t=" + Date.now(), { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(afficher)
    .catch(function (e) {
      document.getElementById("maj").textContent = "Journal indisponible (" + e.message + "). Il est produit chaque nuit par le pipeline.";
    });
})();
