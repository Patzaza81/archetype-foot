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
      '<div class="jr-chiffre"><span>Cotes réglées</span><b>' + (d.cotes_reglees || 0) + "</b></div>" +
      '<div class="jr-chiffre"><span>Marchés rentables</span><b class="pos">' + rentables.length + "</b></div>" +
      '<div class="jr-chiffre"><span>Prouvés ou à surveiller</span><b class="pos">' + nbFiables + "</b></div>" +
      '</div><p class="jr-aide" style="margin:10px 0 0">' + Object.keys(ligues).length + " championnat(s) avec au moins un marché rentable · période " + esc(p) + ".</p>" +
      '<p class="jr-source"><b>D\'où viennent ces chiffres ?</b> D\'aucun moteur de prédiction. Chaque nuit, le script du journal prend les cotes relevées avant chaque match terminé et les compare au score final : c\'est une comptabilité de résultats réels. Aucune rubrique moteur n’est publiée ici.</p>';
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

  /* Indice de performance (calculé par journal_indice.py, jamais ici). 3/4 et 4/4 = « bon indice ». Marché d'une seule
     équipe (2 scénarios) : phrase plutôt qu'une note sur 2. */
  function indiceTexte(p) {
    if (!p || typeof p.indice !== "number") return "";
    return p.sur === 2 && p.phrase ? p.libelle + " · " + String(p.phrase).replace(/\.$/, "") : p.indice + "/" + p.sur + " · " + p.libelle;
  }
  function indiceBon(p) { return !!p && (p.niveau === "SUR" || p.niveau === "RECOMMANDE"); }
  function indiceBadge(p) {
    if (!p || typeof p.indice !== "number") return "";
    return ' <span class="jr-indice jr-indice-' + esc(String(p.niveau || "").toLowerCase().replace(/_/g, "-")) +
      '" title="Marché testé sur les scénarios moyen et pire de chaque équipe. Information seulement.">Indice ' + esc(indiceTexte(p)) + "</span>";
  }

  /* ─────────── Équipes à suivre (marché récurrent >= 70 %) ───────────
     Classées PAR JOUR de leur prochain match (puis par heure), une carte par match, même présentation que les moteurs
     (heure, date, drapeau du championnat, carte repliée qui se déplie au toucher). Les deux équipes d'un même match
     partagent la même carte. Les équipes sans match connu sont regroupées à la fin. Aucun calcul métier ici. */
  var JOURS = ["dim", "lun", "mar", "mer", "jeu", "ven", "sam"], MOIS = ["janv", "févr", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"];
  function jourLisible(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    if (!m) return esc(iso);
    var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], 12));
    var t = JOURS[d.getUTCDay()] + " " + (+m[3]) + " " + MOIS[+m[2] - 1];
    return t.charAt(0).toUpperCase() + t.slice(1);
  }
  function maintenantCameroun() { return new Date(Date.now() + 3600000).toISOString().slice(0, 16).replace("T", " "); }   // « AAAA-MM-JJ HH:MM », heure du Cameroun
  function etiquetteJour(iso, aujourdhui) {
    var demain = new Date(Date.parse(aujourdhui + "T12:00:00Z") + 86400000).toISOString().slice(0, 10);
    return (iso === aujourdhui ? "Aujourd'hui · " : iso === demain ? "Demain · " : "") + jourLisible(iso);
  }
  /* Regroupe les lignes (équipe × marché) en matchs : { cle, date, heure, dom, ext, ligue, equipes: [{equipe, ligue, lignes}] } triés par date puis heure. */
  function groupeParMatch(lignes) {
    var matchs = {}, ordre = [], sans = {}, ordreSans = [];
    lignes.forEach(function (l) {
      var pm = l.prochain_match;
      if (!pm || !pm.date) {
        var c0 = l.equipe + " | " + l.ligue;
        if (!sans[c0]) { sans[c0] = { equipe: l.equipe, ligue: l.ligue, lignes: [] }; ordreSans.push(c0); }
        sans[c0].lignes.push(l); return;
      }
      var chez = pm.lieu === "domicile", dom = chez ? l.equipe : pm.adversaire, ext = chez ? pm.adversaire : l.equipe;
      var cle = [pm.date, pm.heure || "", dom, ext].join("|");
      if (!matchs[cle]) { matchs[cle] = { cle: cle, date: pm.date, heure: pm.heure || "", dom: dom, ext: ext, ligue: l.ligue, equipes: {}, ordreEq: [] }; ordre.push(cle); }
      var m = matchs[cle];
      if (!m.equipes[l.equipe]) { m.equipes[l.equipe] = { equipe: l.equipe, ligue: l.ligue, joues: l.joues, lignes: [] }; m.ordreEq.push(l.equipe); }
      m.equipes[l.equipe].lignes.push(l);
    });
    var liste = ordre.map(function (c) {
      var m = matchs[c]; m.equipes = m.ordreEq.map(function (e) { return m.equipes[e]; }); return m;
    }).sort(function (a, b) { return (a.date + " " + a.heure).localeCompare(b.date + " " + b.heure) || a.dom.localeCompare(b.dom); });
    return { matchs: liste, sans: ordreSans.map(function (c) { return sans[c]; }) };
  }
  function blocMarches(ls) {
    return ls.map(function (l) {
      var rent = l.roi_betpawa == null ? "Cote : pas encore assez de relevés."
        : (l.roi_betpawa > 0 ? 'Rentabilité observée : <span class="pos">' + pct(l.roi_betpawa, true) + "</span> sur " + l.paris_cotes + " cote(s) relevée(s)."
          : "Rendement insuffisant sur la période observée.");
      var cotePm = l.prochain_match && l.prochain_match.cote_betpawa ? ' <span class="jr-cote-pm">cote ' + cote(l.prochain_match.cote_betpawa) + "</span>" : "";
      return '<div class="jr-eq-marche"><div class="jr-eq-ligne"><b>' + esc(l.marche) + "</b>" + cotePm + indiceBadge(l.indice_performance) + '<span class="jr-eq-freq">' +
        l.gagnes + "/" + l.joues + " · " + pct(l.frequence) + "</span></div>" +
        '<div class="jr-eq-detail">En général : ' + pct(l.frequence_generale) + " des matchs. " + rent + "</div></div>";
    }).join("");
  }
  function resumeEquipe(eq) {
    var resume = eq.lignes.map(function (l) { return l.marche + " " + pct(l.frequence); }).join(" · ");
    var bons = eq.lignes.filter(function (l) { return indiceBon(l.indice_performance); });
    var badges = bons.length ? '<div class="jr-eq-bons">' + bons.map(function (l) {
      return '<span class="jr-indice jr-indice-' + esc(String(l.indice_performance.niveau).toLowerCase().replace(/_/g, "-")) + '">' + esc(l.marche) + " · " + esc(indiceTexte(l.indice_performance)) + "</span>";
    }).join(" ") + "</div>" : "";
    return { resume: resume, badges: badges, bon: bons.length > 0 };
  }
  function carteMatch(m, maintenant) {
    var passe = (m.date + " " + (m.heure || "23:59")) < maintenant;
    var bon = false, lien = "";
    var corps = m.equipes.map(function (eq) {
      var r = resumeEquipe(eq); if (r.bon) bon = true;
      return '<div class="jr-eq-corps"><div class="jr-eq-tete"><span class="jr-fiche-nom">' + esc(eq.equipe) + '</span><span class="jr-badge b-A_JOUER">À suivre</span></div>' +
        '<div class="jr-fiche-info">' + eq.joues + " matchs analysés</div><div class=\"jr-eq-resume\">" + esc(r.resume) + "</div>" + r.badges + "</div>";
    }).join("");
    var details = m.equipes.map(function (eq) {
      var u = ""; eq.lignes.forEach(function (l) { if (l.prochain_match && l.prochain_match.betpawa_url) u = l.prochain_match.betpawa_url; });
      return '<div class="jr-eq-detail-eq"><div class="jr-eq-detail-nom">' + esc(eq.equipe) + "</div>" + blocMarches(eq.lignes) +
        (u ? '<a class="jr-lien" href="' + esc(u) + '" target="_blank" rel="noopener">Voir la cote →</a>' : "") + "</div>";
    }).join("");
    var s = document.createElement("section");
    s.className = "ax-carte ax-replie jr-match" + (passe ? " jr-passe" : "");
    s.setAttribute("aria-expanded", "false");
    s.setAttribute("data-prochain", "1"); s.setAttribute("data-bon", bon ? "1" : "0");
    s.innerHTML = '<div class="ax-match"><div class="ax-ligne-match"><span class="ax-equipe ax-dom">' + esc(m.dom) + "</span>" +
      '<div class="ax-horaire"><strong>' + esc(m.heure || "—") + "</strong><span>" + esc(jourLisible(m.date)) + "</span></div>" +
      '<span class="ax-equipe ax-ext">' + esc(m.ext) + "</span></div>" +
      '<div class="ax-match-bas"><p class="ax-competition">' + esc(m.ligue) + "</p><div class=\"ax-actions-tete\"></div></div></div>" +
      '<div class="jr-match-corps">' + (passe ? '<p class="jr-eq-passe">Match déjà commencé ou terminé.</p>' : "") + corps + "</div>" +
      '<details class="ax-details" open><summary class="ax-summary-cache" tabindex="-1">Détail des marchés</summary><div class="ax-details-corps">' + details + "</div></details>";
    s.addEventListener("click", function (e) {
      if (e.target.closest("button, a, summary")) return;
      var sel = window.getSelection && window.getSelection();
      if (sel && String(sel).length) return;
      var avant = s.getBoundingClientRect().top;
      var replie = !s.classList.contains("ax-replie");
      s.classList.toggle("ax-replie", replie); s.setAttribute("aria-expanded", String(!replie));
      var apres = s.getBoundingClientRect().top;
      if (Math.abs(apres - avant) > 1) window.scrollBy(0, apres - avant);
    });
    return s;
  }
  function afficherEquipes(j) {
    var lignes = j.equipes_a_suivre || [];
    var zone = document.getElementById("equipes");
    var r = j.regles_equipes || {};
    zone.innerHTML = "";
    if (!lignes.length) {
      zone.innerHTML = '<p class="jr-vide">Aucune équipe n\'atteint encore 70 % sur un marché avec au moins ' + (r.min_matchs || 5) + " matchs.</p>";
      return;
    }
    var g = groupeParMatch(lignes), maintenant = maintenantCameroun(), aujourdhui = maintenant.slice(0, 10);
    var jours = [], parJour = {};
    g.matchs.forEach(function (m) { if (!parJour[m.date]) { parJour[m.date] = []; jours.push(m.date); } parJour[m.date].push(m); });
    jours.forEach(function (d) {
      var groupe = document.createElement("div"); groupe.className = "jr-jour-groupe";
      var nbEq = parJour[d].reduce(function (n, m) { return n + m.equipes.length; }, 0);
      groupe.innerHTML = '<h3 class="jr-jour">' + esc(etiquetteJour(d, aujourdhui)) + "<small>" + parJour[d].length + " match" + (parJour[d].length > 1 ? "s" : "") +
        " · " + nbEq + " équipe" + (nbEq > 1 ? "s" : "") + " à suivre</small></h3>";
      parJour[d].forEach(function (m) { groupe.appendChild(carteMatch(m, maintenant)); });
      zone.appendChild(groupe);
    });
    if (g.sans.length) {
      var groupe = document.createElement("div"); groupe.className = "jr-jour-groupe jr-sans";
      groupe.innerHTML = '<h3 class="jr-jour">Sans match connu<small>' + g.sans.length + " équipe" + (g.sans.length > 1 ? "s" : "") + " à suivre</small></h3>";
      var bloc = document.createElement("section"); bloc.className = "ax-carte jr-bloc";
      bloc.innerHTML = g.sans.map(function (eq) {
        var rs = resumeEquipe(eq);
        return '<details class="jr-equipe" data-prochain="0" data-bon="' + (rs.bon ? 1 : 0) + '"><summary><div class="jr-eq-tete"><span class="jr-fiche-nom">' + esc(eq.equipe) +
          '</span><span class="jr-badge b-A_JOUER">À suivre</span></div><div class="jr-fiche-info">' + esc(eq.ligue) + " · " + eq.lignes[0].joues + " matchs analysés</div>" +
          '<div class="jr-eq-resume">' + esc(rs.resume) + "</div>" + rs.badges + "</summary>" + blocMarches(eq.lignes) + "</details>";
      }).join("");
      groupe.appendChild(bloc); zone.appendChild(groupe);
    }
    document.querySelectorAll("#filtres-equipes button").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll("#filtres-equipes button").forEach(function (x) { x.classList.remove("actif"); });
        b.classList.add("actif");
        var f = b.getAttribute("data-f");
        zone.querySelectorAll("[data-prochain]").forEach(function (el) {
          var ok = f === "toutes" || (f === "bon" ? el.getAttribute("data-bon") === "1" && el.getAttribute("data-prochain") === "1" : el.getAttribute("data-prochain") === "1");
          el.style.display = ok ? "" : "none";
        });
        zone.querySelectorAll(".jr-jour-groupe").forEach(function (gr) {
          var visibles = Array.prototype.some.call(gr.querySelectorAll("[data-prochain]"), function (el) { return el.style.display !== "none"; });
          gr.style.display = visibles ? "" : "none";
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
    return "<b>Base :</b> " + esc(lieuPreuve(p)) + " a été observé sur " + p.matchs + " match(s) déjà joué(s) : " +
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
    return x.betpawa_url ? '<a class="jr-lien" href="' + esc(x.betpawa_url) + '" target="_blank" rel="noopener">Voir la cote →</a>' : "";
  }

  /* Affichage tolérant : le Journal principal reste indépendant de l'Observatoire. */
  function afficherObservatoire(data) {
    var zone = document.getElementById("observatoire-resume");
    if (!zone) return;
    var d = data && data.donnees ? data.donnees : {};
    var c = data && data.comptage_statuts ? data.comptage_statuts : {};
    var aJouer = Number((c.ligues || {}).A_JOUER || 0) + Number((c.marches || {}).A_JOUER || 0);
    zone.innerHTML = '<div class="jr-chiffres">' +
      '<div class="jr-chiffre"><span>Matchs observés</span><b>' + Number(d.matchs || 0) + '</b></div>' +
      '<div class="jr-chiffre"><span>Cotes réglées</span><b>' + Number(d.cotes_reglees || 0) + '</b></div>' +
      '<div class="jr-chiffre"><span>Segments prouvés</span><b>' + aJouer + '</b></div>' +
      '</div><p class="jr-aide">Observatoire généré le ' + esc(data && data.genere_le || "—") + '. Les croisements et contrôles sont calculés en arrière-plan.</p>';
  }

  function afficherRegles(j) {
    var zone = document.getElementById("regles");
    if (!zone) return;
    var r = j && j.regles ? j.regles : {};
    zone.innerHTML = '<div class="jr-regles">' +
      '<p><b>À jouer :</b> ' + esc(r.A_JOUER || "—") + '</p>' +
      '<p><b>À surveiller :</b> ' + esc(r.A_SURVEILLER || "—") + '</p>' +
      '<p><b>À éviter :</b> ' + esc(r.A_EVITER || "—") + '</p>' +
      '<p><b>Neutre :</b> ' + esc(r.NEUTRE || "—") + '</p>' +
      (r.avertissement ? '<p class="jr-aide">' + esc(r.avertissement) + '</p>' : '') +
      '</div>';
  }

  function afficherOpportunites(j) {
    var zone = document.getElementById("opportunites");
    if (!zone) return;
    var rows = j.opportunites_futures || [];
    if (!rows.length) {
      zone.innerHTML = '<p class="jr-vide">Aucune opportunité future suffisamment documentée pour l’instant.</p>';
      return;
    }
    var ordre = { EMERGENCE: 0, RENFORCEMENT: 1, RUPTURE: 2 };
    rows.sort(function(a,b){ return (ordre[a.statut]-ordre[b.statut]) || ((b.frequence_recente||0)-(a.frequence_recente||0)); });
    zone.innerHTML = rows.map(function(o) {
      var pm = o.prochain_match || {};
      var badge = o.statut === "RUPTURE" ? "b-NEUTRE" : (o.statut === "EMERGENCE" ? "b-A_SURVEILLER" : "b-A_JOUER");
      var prix = pm.cote_betpawa == null ? "Cote non disponible" : (pm.prix_compatible_historique === true ? "Prix dans la plage historique" : pm.prix_compatible_historique === false ? "Prix hors plage historique" : "Prix non comparable");
      var roi = o.roi_betpawa == null ? "ROI : insuffisant" : "ROI : " + pct(o.roi_betpawa, true);
      return '<details class="jr-equipe"><summary><div class="jr-eq-tete"><span class="jr-fiche-nom">' + esc(o.equipe) + '</span><span class="jr-badge ' + badge + '">' + esc(o.statut) + '</span></div><div class="jr-fiche-info">' + esc(o.ligue) + " · " + esc(o.marche) + " · tendance récente " + pct(o.frequence_recente) + '</div><div class="jr-eq-resume">' + esc(o.niveau) + " · " + esc(roi) + '</div></summary><div class="jr-eq-marche"><div class="jr-eq-detail"><b>Historique :</b> ' + o.observations + " matchs · global " + pct(o.frequence) + " · récent " + pct(o.frequence_recente) + (o.frequence_precedente == null ? "" : " · précédent " + pct(o.frequence_precedente)) + " · évolution " + pct(o.delta_recent, true) + '.</div><div class="jr-eq-prochain">Prochain match : ' + dateCourte(pm.date) + " à " + esc(pm.heure || "—") + " contre " + esc(pm.adversaire || "—") + " (" + esc(pm.lieu || "—") + ")" + (pm.cote_betpawa == null ? "" : " · cote " + cote(pm.cote_betpawa)) + " · " + esc(prix) + '</div><div class="jr-eq-detail"><b>Règle :</b> signal calculé hors moteur. Il sert à surveiller une configuration et peut disparaître si la tendance se dégrade.</div></div></details>';
    }).join("");
  }

  function afficher(j) {
    document.getElementById("maj").textContent = "Mis à jour : " + (j.genere_le || "—");
    var rentables = ((j.segments || {}).ligue_marche || []).filter(positif);
    afficherResume(j, rentables);
    afficherRentables(j, rentables);
    afficherEquipes(j);
    afficherOpportunites(j);
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
