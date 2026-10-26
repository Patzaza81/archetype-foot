// af-selection-alpha.js — page « Sélection » du moteur alpha (26/10/2026). Ne calcule rien : affiche data/alpha_serie/selection_provisoire_page.json
// (écrit chaque nuit par alpha_serie/selection_provisoire.py : pronostics gelés avant le match avec leur cote BetPawa figée, résultats, suivi réel).
// Tout texte venant des données est échappé.
(function () {
  "use strict";
  const esc = (x) => String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (x, d) => (x === null || x === undefined ? "—" : `${(x * 100).toFixed(d === undefined ? 1 : d).replace(".", ",")} %`);
  const cote = (x) => (x === null || x === undefined ? null : Number(x).toFixed(2).replace(".", ","));
  const jourFr = (iso) => (iso ? iso.split("-").reverse().join("/") : "—");
  const auj = (() => { try { return new Intl.DateTimeFormat("fr-CA", { timeZone: "Africa/Douala" }).format(new Date()); } catch (e) { return new Date().toISOString().slice(0, 10); } })();
  const titreJour = (iso) => (iso === auj ? `Aujourd'hui · ${jourFr(iso)}` : iso < auj ? `Hier et avant · ${jourFr(iso)}` : jourFr(iso));
  let D = null, vue = "pronostics", filtre = "tous";

  const gros = (l) => `<div class="ia-gros">${l.map(([t, v]) => `<div><small>${esc(t)}</small><strong>${esc(v)}</strong></div>`).join("")}</div>`;

  function carte(p) {
    const res = p.resultat === "gagne" ? `<span class="ia-badge res-gagne">Gagné ${esc(p.score.buts_dom)}-${esc(p.score.buts_ext)}</span>`
      : p.resultat === "perdu" ? `<span class="ia-badge res-perdu">Perdu ${esc(p.score.buts_dom)}-${esc(p.score.buts_ext)}</span>` : "";
    const c = cote(p.cote);
    return `<article class="sa-prono"><div class="sa-haut"><b>${esc(p.heure || "—")}</b><span>${esc(p.competition)}</span></div>` +
      `<p class="sa-match">${esc(p.domicile)} – ${esc(p.exterieur)}</p>` +
      `<div class="sa-marche"><strong>${esc(p.marche)}</strong>${c ? `<span class="sa-cote">Cote ${esc(c)}</span>` : `<span class="sa-sans">Multigoal : sans cote BetPawa</span>`}</div>` +
      `<div class="ia-badges"><span class="ia-badge niv-${esc(p.niveau)}">Niveau ${p.niveau === "maximal" ? "maximal" : "normal"}</span>${res}</div></article>`;
  }

  function vuePronostics() {
    const regles = D.regles;
    const chips = `<div class="ia-chips" role="group" aria-label="Filtrer par marché"><button type="button" data-filtre="tous" aria-pressed="${filtre === "tous"}">Tous</button>` +
      regles.map((r) => `<button type="button" data-filtre="${esc(r.id)}" aria-pressed="${filtre === r.id}">${esc(r.nom)}</button>`).join("") + `</div>`;
    const liste = D.pronostics.filter((p) => filtre === "tous" || p.regle === filtre);
    if (!liste.length) return chips + `<p class="ia-vide">Aucun pronostic de la sélection pour l'instant${filtre === "tous" ? "" : " pour ce marché"}. Ils sont ajoutés chaque nuit, avant les matchs, seulement quand les conditions sont réunies.</p>`;
    let html = chips, jour = null;
    for (const p of liste) {
      if (p.date !== jour) { jour = p.date; html += `<h2 class="sa-jour">${esc(titreJour(jour))}</h2>`; }
      html += carte(p);
    }
    return html;
  }

  function vueSuivi() {
    const t = D.suivi.total;
    let html = `<section class="ia-carte"><h2>Suivi réel de la sélection</h2>` +
      (t.regles ? gros([["Pronostics réglés", t.regles], ["Réussite réelle", pct(t.taux)], ["Gagnés", t.gagnes], ["Borne basse 95 %", pct(t.wilson_bas_95)]])
        : `<p class="ia-vide">Aucun pronostic réglé pour l'instant : le suivi réel commence avec les premiers résultats.</p>`) +
      `<p class="ia-doux">Chaque pronostic est gelé avant le coup d'envoi avec sa cote BetPawa figée, défaites comprises. La réussite et le rendement sont mesurés séparément.</p></section>`;
    for (const r of D.regles) {
      const s = D.suivi.par_marche[r.id] || {};
      const h = r.reference_historique, pb = h.publiables_betpawa;
      html += `<section class="ia-carte"><h3>${esc(r.nom)}</h3><div class="ia-badges"><span class="ia-badge niv-${esc(r.niveau)}">Niveau ${esc(r.niveau)}</span>` +
        `<span class="ia-badge">${r.sans_cote ? "Sans cote BetPawa" : `Cote BetPawa ≥ ${esc(cote(r.cote_min))}`}</span></div>` +
        gros([["Réglés", s.regles || 0], ["Réussite réelle", pct(s.taux)], ["Gagnés / perdus", `${s.gagnes || 0} / ${s.perdus || 0}`], ["En attente", s.en_attente || 0],
          ["Rendement réel", s.rendement === null || s.rendement === undefined ? (r.sans_cote ? "sans cote" : "—") : `${s.rendement >= 0 ? "+" : ""}${pct(s.rendement)}`], ["Paris avec cote", s.paris_avec_cote || 0]]) +
        `<div class="ia-ref"><b>Étude historique (à part, aucune garantie)</b>` +
        `<span>${esc(h.decouverte.periode)} : ${pct(h.decouverte.gagnes / h.decouverte.matchs)} sur ${esc(h.decouverte.matchs)}</span>` +
        `<span>${esc(h.controle.periode)} : ${pct(h.controle.gagnes / h.controle.matchs)} sur ${esc(h.controle.matchs)}</span>` +
        `<span>${esc(pb.periode)} : ${pct(pb.gagnes / pb.matchs)} sur ${esc(pb.matchs)}` +
        (pb.rendement === null || pb.rendement === undefined ? "" : ` · rendement ${pb.rendement >= 0 ? "+" : ""}${pct(pb.rendement, 0)} (non démontré)`) + `</span></div></section>`;
    }
    return html;
  }

  function rendre() {
    document.getElementById("sa").innerHTML = vue === "suivi" ? vueSuivi() : vuePronostics();
    document.querySelectorAll("#sa-vues button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.vue === vue)));
  }

  document.addEventListener("click", (e) => {
    if (!D) return;
    const v = e.target.closest("#sa-vues button");
    if (v) { vue = v.dataset.vue; rendre(); return; }
    const f = e.target.closest("[data-filtre]");
    if (f) { filtre = f.dataset.filtre; rendre(); }
  });

  fetch(`data/alpha_serie/selection_provisoire_page.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then((d) => {
      D = d;
      document.getElementById("maj").textContent = `Mis à jour le ${d.genere_le.slice(8, 10)}/${d.genere_le.slice(5, 7)} à ${d.genere_le.slice(11, 16)} UTC · ${d.pronostics.length} pronostic(s) affiché(s).`;
      document.getElementById("sa-vues").hidden = false;
      rendre();
    })
    .catch((e) => { document.getElementById("maj").textContent = `Impossible de charger la sélection (${e.message}). Rien n'est affiché plutôt que des données fausses.`; });
})();
