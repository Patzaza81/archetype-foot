/* Page Corners & Cartons : lit data/corners_cartons.json (produit par corners_cartons.py). Aucun calcul ici. */
(function () {
  "use strict";
  var ONGLETS = [
    { id: "corners", titre: "Corners" },
    { id: "cartons", titre: "Cartons" },
    { id: "rouge", titre: "Carton rouge" }
  ];
  var etat = { doc: null, onglet: "corners", date: "tout", seulCotes: false };

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

  function virgule(x, n) { return x.toFixed(n).replace(".", ","); }

  // Une case : cote en gros, puis modèle et seuil. cote absente -> « – ».
  function cellule(p, cote, seuil, top, ind) {
    var c = el("div", "cel" + (top ? " top" : ""));
    c.appendChild(el("span", "cote" + (cote ? "" : " nc"), cote ? virgule(cote, 2) : "–"));
    var info = el("span", "info");
    var m = el("b", "", pct(p));
    info.appendChild(document.createTextNode("Modèle "));
    info.appendChild(m);
    if (cote) info.appendChild(document.createTextNode(" · seuil " + pct(seuil)));
    c.appendChild(info);
    if (ind !== undefined && ind !== null) c.appendChild(el("span", "ind n" + ind, ind + "/4"));
    return c;
  }

  // Une ligne = libellé + case Plus + case Moins (ou Oui / Non).
  function rangee(g, libelle, pPlus, cotes, cles, ind) {
    ind = ind || {};
    var c = cotes || {};
    var k1 = cles[0], k2 = cles[1];
    g.appendChild(el("div", "lib", libelle));
    g.appendChild(cellule(pPlus, c[k1], c["seuil_" + k1], c.modele_au_dessus === k1, ind[k1]));
    g.appendChild(cellule(1 - pPlus, c[k2], c["seuil_" + k2], c.modele_au_dessus === k2, ind[k2]));
  }

  function grille(t1, t2, lignes, cotesZone, prefixe, indZone) {
    var g = el("div", "grille");
    g.appendChild(el("div", "tete", ""));
    g.appendChild(el("div", "tete", t1));
    g.appendChild(el("div", "tete", t2));
    Object.keys(lignes).sort(function (a, b) { return parseFloat(a) - parseFloat(b); }).forEach(function (l) {
      rangee(g, prefixe + ligneNum(l), lignes[l], cotesZone ? cotesZone[l] : null, ["plus", "moins"], indZone ? indZone[l] : null);
    });
    return g;
  }

  function aDesCotes(m) { return !!(m.cotes && (m.cotes.corners || m.cotes.cartons || m.cotes.rouge)); }

  function banniere(m, genre, cg) {
    var ch = m.choix[genre], b = el("div", "choix");
    var cote = cg.total && cg.total[ch.ligne] && cg.total[ch.ligne][ch.cote];
    b.appendChild(el("span", "choix-t", "Meilleur choix"));
    b.appendChild(el("b", "", (ch.cote === "plus" ? "Plus de " : "Moins de ") + ligneNum(ch.ligne) + " " + genre));
    b.appendChild(el("span", "choix-d", pct(ch.proba) + " · " + ch.indice + "/4 " + ch.niveau + (cote ? " · cote " + virgule(cote, 2) : "")));
    return b;
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
    var cotes = m.cotes || {};

    if (etat.onglet === "rouge") {
      var r = pv.rouge;
      c.appendChild(el("div", "titre-bloc", "Un joueur expulsé dans le match"));
      var gr = el("div", "grille");
      gr.appendChild(el("div", "tete", ""));
      gr.appendChild(el("div", "tete", "Oui"));
      gr.appendChild(el("div", "tete", "Non"));
      rangee(gr, "Rouge", r.oui, cotes.rouge, ["oui", "non"]);
      c.appendChild(gr);
      c.appendChild(el("p", "sans", "Moyenne du championnat : " + virgule(r.taux_division, 2) + " rouge par match."));
      return c;
    }

    var f = pv[etat.onglet];
    var cg = cotes[etat.onglet] || {};
    var unite = etat.onglet === "corners" ? "corners" : "cartons";
    var att = el("div", "attendu");
    [[f.attendu_domicile, m.domicile], [f.attendu_total, "Total attendu"], [f.attendu_exterieur, m.exterieur]].forEach(function (x) {
      var d = el("div");
      d.appendChild(el("b", "", virgule(x[0], 1)));
      d.appendChild(document.createTextNode(" " + x[1]));
      att.appendChild(d);
    });
    c.appendChild(att);

    c.appendChild(el("div", "titre-bloc", "Total " + unite));
    if (m.choix && m.choix[etat.onglet]) c.insertBefore(banniere(m, etat.onglet, cg), att);
    c.appendChild(grille("Plus", "Moins", f.total, cg.total, "", m.indices && m.indices[etat.onglet]));

    var det = el("details", "equipes");
    det.appendChild(el("summary", "", "Par équipe"));
    det.appendChild(el("div", "titre-bloc", m.domicile));
    det.appendChild(grille("Plus", "Moins", f.domicile, cg.domicile, ""));
    det.appendChild(el("div", "titre-bloc", m.exterieur));
    det.appendChild(grille("Plus", "Moins", f.exterieur, cg.exterieur, ""));
    det.appendChild(el("p", "sans", "Cote relevée seulement quand le même marché est disponible : « 7+ » pour Plus de 6,5 corners, « 0-1 » pour Moins de 1,5 carton."));
    c.appendChild(det);

    if (!aDesCotes(m)) c.appendChild(el("p", "sans", "Cotes non relevées pour ce match : probabilités du modèle seules."));
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
    [["tout", "Tout"]].concat(dates.map(function (d) { return [d, jourLisible(d)]; })).forEach(function (x) {
      var b = el("button", "chip" + (etat.date === x[0] ? " actif" : ""), x[1]);
      b.type = "button";
      b.addEventListener("click", function () { etat.date = x[0]; rend(); });
      z.appendChild(b);
    });
  }

  function rendOptions() {
    var z = document.getElementById("options");
    z.textContent = "";
    var b = el("button", "chip" + (etat.seulCotes ? " actif" : ""), "Avec cotes seulement");
    b.type = "button";
    b.addEventListener("click", function () { etat.seulCotes = !etat.seulCotes; rend(); });
    z.appendChild(b);
  }

  function rendMatchs() {
    var z = document.getElementById("matchs");
    z.textContent = "";
    var liste = etat.doc.matchs.filter(function (m) {
      return (etat.date === "tout" || m.date === etat.date) && (!etat.seulCotes || aDesCotes(m));
    });
    if (!liste.length) {
      z.appendChild(el("div", "vide", etat.seulCotes
        ? "Aucune cote corners/cartons relevée pour ces matchs. Les cotes apparaissent après la prochaine mise à jour des données."
        : "Aucun match à afficher pour cette date."));
      return;
    }
    var jour = null;
    liste.forEach(function (m) {
      if (m.date !== jour) {
        jour = m.date;
        z.appendChild(el("div", "jour", jourLisible(m.date)));
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

  function rend() { rendOnglets(); rendDates(); rendOptions(); rendMatchs(); }

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
