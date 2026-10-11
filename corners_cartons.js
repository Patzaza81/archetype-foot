/* Page Corners & Cartons : lit data/corners_cartons.json (produit par corners_cartons.py). Aucun calcul ici. */
(function () {
  "use strict";
  var ONGLETS = [
    { id: "corners", titre: "Corners" },
    { id: "cartons", titre: "Cartons" },
    { id: "rouge", titre: "Carton rouge" }
  ];
  var etat = { doc: null, onglet: "corners", date: "tout" };

  function el(tag, classe, texte) {
    var e = document.createElement(tag);
    if (classe) e.className = classe;
    if (texte !== undefined && texte !== null) e.textContent = texte;
    return e;
  }
  function pct(p) { return Math.round(p * 100) + "%"; }
  function ligneNum(l) { return String(l).replace(".", ","); }

  function jourLisible(iso) {
    var p = iso.split("-");
    var d = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]));
    var t = d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
    return t.charAt(0).toUpperCase() + t.slice(1);
  }

  function barre(p) {
    var b = el("div", "barre");
    var i = el("i");
    i.style.width = Math.max(2, Math.min(100, Math.round(p * 100))) + "%";
    b.appendChild(i);
    return b;
  }

  function ligne(libelle, p) {
    var l = el("div", "ligne");
    l.appendChild(el("span", "", libelle));
    l.appendChild(barre(p));
    l.appendChild(el("b", "", pct(p)));
    return l;
  }

  function blocLignes(titre, dico, deux) {
    var w = el("div");
    w.appendChild(el("div", "titre-bloc", titre));
    Object.keys(dico).sort(function (a, b) { return parseFloat(a) - parseFloat(b); }).forEach(function (l) {
      w.appendChild(ligne((deux ? "+" : "Plus de ") + ligneNum(l), dico[l]));
    });
    return w;
  }

  function carteMatch(m) {
    var c = el("article", "match");
    var tete = el("div", "match-tete");
    var g = el("div");
    g.appendChild(el("strong", "", m.domicile + " – " + m.exterieur));
    g.appendChild(el("div", "meta", m.competition + " · " + (m.heure || "")));
    tete.appendChild(g);
    var pv = m.previsions;
    var tag = el("span", "tag " + pv.fiabilite, "Données : " + pv.fiabilite);
    tag.title = "Selon le nombre de matchs déjà joués par les deux équipes";
    tete.appendChild(tag);
    c.appendChild(tete);

    if (etat.onglet === "rouge") {
      var r = pv.rouge;
      var att = el("div", "attendu");
      [["Carton rouge", pct(r.oui)], ["Pas de rouge", pct(1 - r.oui)], ["Rouges / match (champ.)", r.taux_division.toFixed(2).replace(".", ",")]]
        .forEach(function (x) { var d = el("div"); d.appendChild(el("b", "", x[1])); d.appendChild(el("span", "", x[0])); att.appendChild(d); });
      c.appendChild(att);
      return c;
    }

    var f = pv[etat.onglet];
    var unite = etat.onglet === "corners" ? "corners" : "cartons";
    var att2 = el("div", "attendu");
    [[f.attendu_domicile, m.domicile], [f.attendu_total, "Total " + unite], [f.attendu_exterieur, m.exterieur]].forEach(function (x) {
      var d = el("div");
      d.appendChild(el("b", "", x[0].toFixed(1).replace(".", ",")));
      d.appendChild(el("span", "", x[1]));
      att2.appendChild(d);
    });
    c.appendChild(att2);
    c.appendChild(blocLignes("Total " + unite, f.total, false));
    var duo = el("div", "deux");
    duo.appendChild(blocLignes(m.domicile, f.domicile, true));
    duo.appendChild(blocLignes(m.exterieur, f.exterieur, true));
    c.appendChild(duo);
    return c;
  }

  function rendBilan() {
    var corps = document.getElementById("bilan-corps");
    corps.textContent = "";
    var b = etat.doc.bilan || { matchs_regles: 0, familles: {} };
    if (!b.matchs_regles) {
      corps.appendChild(el("p", "help", "Aucun match réglé pour l'instant. Football-Data publie les résultats avec 1 à 4 jours de retard : les premières prévisions seront comparées aux résultats réels dès leur publication."));
      return;
    }
    corps.appendChild(el("p", "help", b.matchs_regles + " match(s) réglé(s). « Annoncé » = probabilité moyenne donnée par le modèle, « Observé » = fréquence réelle. Perte log : plus bas = mieux ; la colonne « Champ. seul » est la même mesure avec la seule moyenne du championnat."));
    var t = el("table");
    var h = el("tr");
    ["Famille", "Lignes", "Annoncé", "Observé", "Perte log", "Champ. seul"].forEach(function (x) { h.appendChild(el("th", "", x)); });
    t.appendChild(h);
    var noms = { corners_total: "Corners total", corners_domicile: "Corners domicile", corners_exterieur: "Corners extérieur",
      cartons_total: "Cartons total", cartons_domicile: "Cartons domicile", cartons_exterieur: "Cartons extérieur", rouge_match: "Carton rouge" };
    Object.keys(b.familles).forEach(function (k) {
      var x = b.familles[k], tr = el("tr");
      [noms[k] || k, x.lignes_evaluees, pct(x.proba_moyenne_annoncee), pct(x.taux_observe),
        x.logloss === null ? "–" : x.logloss.toFixed(3), x.logloss_moyenne_division_seule === null ? "–" : x.logloss_moyenne_division_seule.toFixed(3)]
        .forEach(function (v) { tr.appendChild(el("td", "", String(v))); });
      t.appendChild(tr);
    });
    corps.appendChild(t);
  }

  function rendOnglets() {
    var z = document.getElementById("onglets");
    z.textContent = "";
    ONGLETS.forEach(function (o) {
      var b = el("button", "chip" + (etat.onglet === o.id ? " actif" : ""), o.titre);
      b.type = "button";
      b.addEventListener("click", function () { etat.onglet = o.id; rend(); });
      z.appendChild(b);
    });
  }

  function rendDates() {
    var z = document.getElementById("dates");
    z.textContent = "";
    var dates = [];
    etat.doc.matchs.forEach(function (m) { if (dates.indexOf(m.date) < 0) dates.push(m.date); });
    dates.sort();
    [["tout", "Toutes les dates"]].concat(dates.map(function (d) { return [d, jourLisible(d)]; })).forEach(function (x) {
      var b = el("button", "chip" + (etat.date === x[0] ? " actif" : ""), x[1]);
      b.type = "button";
      b.addEventListener("click", function () { etat.date = x[0]; rend(); });
      z.appendChild(b);
    });
  }

  function rendMatchs() {
    var z = document.getElementById("matchs");
    z.textContent = "";
    var liste = etat.doc.matchs.filter(function (m) { return etat.date === "tout" || m.date === etat.date; });
    if (!liste.length) {
      z.appendChild(el("div", "vide", "Aucun match à afficher pour cette date."));
      return;
    }
    var jour = null;
    liste.forEach(function (m) {
      if (m.date !== jour) {
        jour = m.date;
        z.appendChild(el("div", "titre-bloc", jourLisible(m.date)));
      }
      z.appendChild(carteMatch(m));
    });
  }

  function rendRefus() {
    var r = etat.doc.refus || {};
    var libelles = {
      equipes_non_reliees_a_football_data: "équipes ou championnat absents de Football-Data",
      corners_cartons_non_publies_pour_ce_championnat: "championnat sans corners/cartons publiés",
      echantillon_insuffisant: "moins de 3 matchs joués par une équipe",
      deja_joue_dans_football_data: "match déjà joué"
    };
    var parts = Object.keys(r).map(function (k) { return r[k] + " " + (libelles[k] || k); });
    document.getElementById("refus").textContent = parts.length ? "Matchs écartés : " + parts.join(" · ") + "." : "";
  }

  function rend() { rendOnglets(); rendDates(); rendMatchs(); }

  function init(doc) {
    etat.doc = doc;
    document.getElementById("maj").textContent = "Mis à jour : " + doc.genere_le + " · saison " + doc.saison_football_data;
    rendBilan();
    rendRefus();
    rend();
  }

  fetch("data/corners_cartons.json?t=" + Date.now(), { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(init)
    .catch(function (e) {
      document.getElementById("maj").textContent = "Données indisponibles (" + e.message + ").";
    });
})();
