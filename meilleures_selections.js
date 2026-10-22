// meilleures_selections.js — onglet « Meilleures sélections » des pages V2 et V3 (22/10/2026).
// Présentation uniquement : tout vient de data/meilleures_selections/classement.json, recalculé chaque nuit par
// meilleures_selections/suivi.py (recalibrage automatique chaque semaine). Le navigateur ne choisit ni ne calcule rien.
// Le moteur de la page est lu dans la classe du <body> (af-v2 ou af-v3).
(function () {
  "use strict";
  var MOTEUR = document.body.classList.contains("af-v3") ? "V3" : document.body.classList.contains("af-v2") ? "V2" : "";
  var ZONE = document.getElementById("matches");
  if (!MOTEUR || !ZONE) return;

  var FAMILLES = {
    total_moins: "Total de buts : moins de", total_plus: "Total de buts : plus de",
    equipe_moins: "Buts d'une équipe : moins de", equipe_plus: "Buts d'une équipe : plus de",
    handicap: "Handicap", double_chance: "Double chance", victoire: "Victoire d'une équipe", nul: "Match nul",
    btts_oui: "Les deux équipes marquent : oui", btts_non: "Les deux équipes marquent : non", cage: "Cage inviolée"
  };

  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
  }
  function nombre(x, d) { return Number(x).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function pct(x) { return x == null ? "—" : nombre(x * 100, 0) + " %"; }
  function signe(x) { return (x > 0 ? "+" : x < 0 ? "−" : "") + nombre(Math.abs(x), 1); }
  function jourLisible(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    return m ? m[3] + "/" + m[2] : "";
  }
  function nomMarche(s) {
    var eq = { domicile: s.domicile || "Équipe à domicile", exterieur: s.exterieur || "Équipe à l'extérieur" };
    try {
      if (s.libelle && typeof clarifieLibelle === "function") return clarifieLibelle(s.libelle, eq);
      if (typeof traduitMarche === "function") return traduitMarche(s.marche_affiche || s.marche, eq);
    } catch (e) { /* repli ci-dessous */ }
    return s.libelle || s.marche_affiche || s.marche;
  }
  function phraseGroupe(g) {
    var palier = g.palier > 0 ? " avec un indice d'au moins " + nombre(g.palier * 4, 0) + " sur 4 (ou équivalent)" : "";
    return (FAMILLES[g.famille] || g.famille) + palier;
  }
  function ligneBilan(titre, b, note) {
    if (!b || !b.n) return "<li><strong>" + esc(titre) + " :</strong> aucun pari pour l'instant." + (note ? " " + esc(note) : "") + "</li>";
    return "<li><strong>" + esc(titre) + " :</strong> " + b.gagnes + " gagnés sur " + b.n + " (" + pct(b.reussite) + "), alors que les cotes en exigeaient " +
      pct(b.base) + ". Pour 100 misés à chaque pari : " + signe(b.rendement * 100) + "." + (note ? " " + esc(note) : "") + "</li>";
  }

  function carte(s) {
    var g = s.groupe, conf = g.statut === "confirme";
    return '<article class="ms-carte' + (conf ? " ms-confirme" : "") + '">' +
      '<div class="ms-tete"><span class="ms-rang">' + s.rang + '</span><div class="ms-match"><strong>' + esc(s.domicile) + " — " + esc(s.exterieur) + "</strong>" +
      '<span class="ms-quand">' + esc(jourLisible(s.date)) + " · " + esc(s.heure || "") + " · " + esc(s.competition || "") + "</span></div>" +
      '<span class="ms-badge ' + (conf ? "ms-b-conf" : "ms-b-obs") + '">' + (conf ? "Confirmée" : "En observation") + "</span></div>" +
      '<p class="ms-marche">' + esc(nomMarche(s)) + "</p>" +
      '<ul class="ms-chiffres"><li><span>Cote</span><strong>' + (s.cote != null ? nombre(s.cote, 2) : "—") + "</strong></li>" +
      "<li><span>Indice</span><strong>" + (s.indice != null ? s.indice + "/" + s.sur : "—") + "</strong></li>" +
      "<li><span>Probabilité</span><strong>" + (s.probabilite != null ? pct(s.probabilite) : "—") + "</strong></li></ul>" +
      '<p class="ms-groupe">Ce type de pari a gagné ' + pct(g.reussite) + " du temps (" + g.gagnes + " sur " + g.n + ") alors que les cotes en exigeaient " + pct(g.base) + ".</p>" +
      "</article>";
  }

  function rend(d) {
    var propres = (d.selections || []).filter(function (s) { return s.moteur === MOTEUR; });
    var groupes = (d.groupes || []).filter(function (g) { return g.moteur === MOTEUR; });
    propres.forEach(function (s, i) { s.rang = i + 1; });   // rang propre à ce moteur (le fichier classe V2 et V3 ensemble)
    var conf = propres.filter(function (s) { return s.groupe.statut === "confirme"; });
    var obs = propres.filter(function (s) { return s.groupe.statut !== "confirme"; });
    var h = "";
    h += '<section class="ms-bloc ms-explique"><h2>Meilleures sélections ' + esc(MOTEUR) + "</h2>" +
      "<p>Seuls les paris qui appartiennent à un type de pari ayant <strong>battu les cotes</strong> dans l'historique sont listés ici. " +
      "Le classement se recalibre <strong>tout seul chaque semaine</strong> : un type de pari qui cesse de gagner sort de la liste, un autre peut y entrer.</p>" +
      '<p class="ms-meta">Dernier recalibrage : ' + esc(jourLisible(d.calibre_le)) + " · prochain : " + esc(jourLisible(d.prochain_recalibrage)) +
      " · " + (d.nb_paris_calibrage || 0) + " paris passés analysés (V2 et V3).</p></section>";

    h += '<section class="ms-bloc"><h3>Ce que ça donne vraiment</h3><ul class="ms-bilan">' +
      ligneBilan("Sur l'historique", (d.bilan_historique || {})[MOTEUR], "Attention : ces paris ont servi à choisir les types retenus, ce résultat est donc flatteur.") +
      ligneBilan("Depuis le recalibrage (vérifié sans triche)", agrege(d.hors_echantillon), "Ce sont les seuls paris joués après le choix du type : c'est la vraie mesure.") +
      ligneBilan("Rejeu semaine par semaine sur le passé", agrege((d.rejeu || {}).bilan), "Même méthode appliquée au passé sans regarder l'avenir.") +
      "</ul></section>";

    if (!propres.length) {
      h += '<div class="ms-vide"><strong>Aucune sélection ne remplit les critères pour le moment</strong><p>Le système préfère ne rien proposer plutôt que de forcer un pari.</p></div>';
    } else {
      if (conf.length) h += '<section class="ms-bloc"><h3>Confirmées (' + conf.length + ")</h3>" + conf.map(carte).join("") + "</section>";
      if (obs.length) h += '<section class="ms-bloc"><h3>En observation (' + obs.length + ')</h3><p class="ms-note">Types de pari prometteurs mais pas encore assez prouvés : une partie peut simplement être due au hasard. À suivre, pas à miser en confiance.</p>' + obs.map(carte).join("") + "</section>";
    }

    h += '<details class="ms-bloc ms-regle"><summary>Types de pari retenus cette semaine (' + groupes.length + ")</summary>" +
      (groupes.length ? "<ul>" + groupes.map(function (g) {
        return "<li><strong>" + esc(phraseGroupe(g)) + "</strong> — " + (g.statut === "confirme" ? "confirmé" : "en observation") + " : " + g.gagnes + " gagnés sur " + g.n + " (" + pct(g.reussite) + " contre " + pct(g.base) + " exigés).</li>";
      }).join("") + "</ul>" : "<p>Aucun type de pari ne remplit les critères.</p>") +
      "<p class=\"ms-note\">Critères : le type de pari doit gagner plus souvent que ce que les cotes exigent, rapporter de l'argent à mise égale et tenir dans chacune des deux moitiés de la période. " +
      "Pour être « confirmé », la probabilité que ce soit dû au hasard doit être inférieure à " + pct(d.seuil_confirme) + " ; pour être « en observation », inférieure à " + pct(d.seuil_observation) +
      ". Ces seuils se calculent à partir du nombre de combinaisons possibles (type de pari × niveau d'indice × moteur : " + (d.m_tests || 0) + ") et changent donc tout seuls avec les données.</p></details>";
    return h;
  }

  function agrege(bilan) {
    if (!bilan) return null;
    var t = ["confirme", "observation"].map(function (k) { return bilan[k]; }).filter(function (b) { return b && b.n; });
    return fusion(t);
  }
  function fusion(lots) {
    var n = 0, g = 0, base = 0, rend = 0;
    lots.forEach(function (b) { n += b.n; g += b.gagnes; base += b.base * b.n; rend += b.rendement * b.n; });
    return n ? { n: n, gagnes: g, reussite: g / n, base: base / n, rendement: rend / n } : { n: 0 };
  }

  var barre = document.createElement("div");
  barre.className = "ms-onglets"; barre.setAttribute("role", "tablist"); barre.setAttribute("aria-label", "Affichage");
  barre.innerHTML = '<button type="button" role="tab" class="ms-onglet ms-actif" data-vue="tous" aria-selected="true">Tous les pronostics</button>' +
    '<button type="button" role="tab" class="ms-onglet" data-vue="meilleures" aria-selected="false">Meilleures sélections</button>';
  var panneau = document.createElement("section");
  panneau.id = "ms-panneau"; panneau.className = "ms-panneau"; panneau.style.display = "none"; panneau.setAttribute("aria-live", "polite");
  panneau.innerHTML = '<p class="ms-chargement">Chargement…</p>';
  var maj = document.getElementById("maj");
  (maj || ZONE).insertAdjacentElement(maj ? "beforebegin" : "beforebegin", barre);
  ZONE.insertAdjacentElement("afterend", panneau);

  var charge = false;
  function bascule(vue) {
    var meilleures = vue === "meilleures";
    barre.querySelectorAll("button").forEach(function (b) {
      var actif = b.getAttribute("data-vue") === vue;
      b.classList.toggle("ms-actif", actif); b.setAttribute("aria-selected", String(actif));
    });
    ZONE.style.display = meilleures ? "none" : "";
    if (maj) maj.style.display = meilleures ? "none" : "";
    var nav = document.getElementById("af-date-navigation");
    if (nav) nav.style.display = meilleures ? "none" : "";
    panneau.style.display = meilleures ? "" : "none";
    if (meilleures && !charge) {
      charge = true;
      fetch("data/meilleures_selections/classement.json?_=" + Date.now())
        .then(function (r) { if (!r.ok) throw new Error("classement introuvable (" + r.status + ") : le suivi nocturne n'a pas encore tourné"); return r.json(); })
        .then(function (d) { panneau.innerHTML = rend(d); })
        .catch(function (e) { charge = false; panneau.innerHTML = '<div class="ms-vide"><strong>Erreur de chargement</strong><p>' + esc(e.message) + "</p></div>"; });
    }
  }
  barre.addEventListener("click", function (ev) {
    var b = ev.target.closest("button[data-vue]");
    if (b) bascule(b.getAttribute("data-vue"));
  });
})();
