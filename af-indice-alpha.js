// af-indice-alpha.js — onglet « Indice Alpha » (26/10/2026). Ne calcule rien : affiche data/alpha_serie/indice_alpha.json
// (écrit chaque nuit par alpha_serie/indice_alpha.py à partir des journaux gelés). Texte inséré par textContent / échappement uniquement.
(function () {
  "use strict";
  const esc = (x) => String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (x, d) => (x === null || x === undefined ? "—" : `${(x * 100).toFixed(d === undefined ? 1 : d).replace(".", ",")} %`);
  const nb = (x) => (x === null || x === undefined ? "—" : String(x).replace(".", ","));
  const jourFr = (iso) => (iso ? iso.split("-").reverse().join("/") : "—");
  const FI = { non_fiable: "Pas encore fiable", a_confirmer: "À confirmer", fiable: "Fiable" };
  const TD = { baisse: "En baisse", stable: "Pas de baisse détectée", insuffisant: "Tendance : trop peu de semaines" };
  let D = null, R = null, vue = "total", choix = null;

  const gros = (l) => `<div class="ia-gros">${l.map(([t, v]) => `<div><small>${esc(t)}</small><strong>${esc(v)}</strong></div>`).join("")}</div>`;
  const badges = (r) => `<div class="ia-badges"><span class="ia-badge st-${esc(r.statut)}">${esc(r.statut_libelle)}</span>` +
    `<span class="ia-badge fi-${esc(r.fiabilite.niveau)}">${esc(FI[r.fiabilite.niveau] || "")}</span>` +
    (r.tendance.signal === "baisse" ? `<span class="ia-badge td-baisse">En baisse</span>` : "") + `</div>`;
  const periode = (p) => (p && p.debut ? `${jourFr(p.debut)} → ${jourFr(p.fin)} (${p.jours} j)` : "Aucun pari gelé pour l'instant");

  function lignesSemaines(l) {
    if (!l || !l.length) return `<p class="ia-vide">Aucune semaine mesurée : le suivi réel commence avec les premiers paris réglés.</p>`;
    return l.map((s) => `<div class="ia-ligne"><span>${esc(s.semaine)}</span><span class="ia-barre" aria-hidden="true"><i style="width:${Math.round((s.taux || 0) * 100)}%"></i></span>` +
      `<span>${s.gagnes}/${s.matchs} · ${pct(s.taux, 0)}</span></div>`).join("");
  }

  function carteClassement(c) {
    return `<article class="ia-carte"><h3>${esc(c.nom)}</h3>${badges({ statut: c.statut, statut_libelle: c.statut_libelle, fiabilite: { niveau: c.fiabilite }, tendance: { signal: c.tendance } })}` +
      gros([["Réglés", c.matchs], ["Taux réel", pct(c.taux)], ["Gagnés / perdus", `${c.gagnes} / ${c.perdus}`], ["Borne basse 95 %", pct(c.wilson_bas_95)], ["Par jour", nb(c.par_jour)], ["En attente", c.en_attente]]) +
      `<p class="ia-doux">Période : ${esc(periode(c.periode))}. ${esc(TD[c.tendance] || "")}.</p>` +
      `<p><button type="button" class="ia-voir" data-id="${esc(c.id)}">Voir la fiche du marché →</button></p></article>`;
  }

  function vueTotal() {
    const g = D.global, p = g.paris_distincts;
    const alertes = D.alerte_registre.length ? `<div class="ia-alerte">Registre à vérifier : ${D.alerte_registre.map(esc).join(" · ")}</div>` : "";
    return `${alertes}<section class="ia-carte" aria-label="Vue globale"><h2>Indice total</h2>` +
      (p.matchs ? gros([["Paris distincts réglés", p.matchs], ["Taux réel", pct(p.taux)], ["Gagnés / perdus", `${p.gagnes} / ${p.perdus}`], ["Borne basse 95 %", pct(p.wilson_bas_95)],
        ["Matchs distincts", g.matchs_distincts], ["Matchs à plusieurs indices", g.matchs_avec_plusieurs_indices]])
        : `<p class="ia-vide">Aucun pari réglé pour l'instant. Les paris sont gelés avant chaque match, puis réglés par le pipeline nocturne.</p>`) +
      `<p class="ia-doux">${esc(g.note)}</p>` +
      (g.par_semaine.length ? `<h3>Par semaine (tous indices, paris distincts)</h3>${lignesSemaines(g.par_semaine)}` : "") + `</section>` +
      `<h2 class="at-h2">Les indices, du plus sûr au moins sûr</h2><p class="ia-doux">Classés par borne basse de confiance à 95 % (les indices sans pari réglé sont en dernier). Une borne basse haute vaut mieux qu'un taux brut sur peu de matchs.</p>` +
      g.classement.map(carteClassement).join("") +
      (g.indices_en_baisse.length ? `<div class="ia-alerte">En baisse : ${g.indices_en_baisse.map((id) => esc((D.indices.find((r) => r.id === id) || { nom: id }).nom)).join(", ")}</div>` : "");
  }

  function ficheMarche(r) {
    const ref = r.reference_rejeu;
    const s = r.seuils || {};
    const seuils = s.conditions_texte ? `${s.conditions_texte} (cote BetPawa enregistrée, non filtrante)` : [s.cote_min != null ? `cote BetPawa ≥ ${nb(s.cote_min)}` : "", s.cote_max != null ? `cote ≤ ${nb(s.cote_max)}` : "",
      s.total_attendu_min != null ? `total de buts attendu ≥ ${nb(s.total_attendu_min)}` : "", s.probabilite_min != null ? `probabilité ≥ ${pct(s.probabilite_min, 0)}` : "aucun seuil de probabilité"].filter(Boolean).join(" · ");
    return `<section class="ia-carte"><h2>${esc(r.nom)}</h2>${badges(r)}<p>${esc(r.fiabilite.texte)}</p>` +
      `<p><b>Conditions :</b> ${esc(r.conditions)}</p><p><b>Seuils :</b> ${esc(seuils)}</p>` +
      (r.objectif_reussite != null ? `<p><b>Objectif :</b> borne basse réelle ≥ ${pct(r.objectif_reussite, 0)}.</p>` : "") + `</section>` +
      `<section class="ia-carte"><h3>Suivi réel (paris gelés avant le match)</h3>` +
      gros([["Évalués", r.matchs], ["Gagnés", r.gagnes], ["Perdus", r.perdus], ["Taux réel", pct(r.taux)], ["Borne basse 95 %", pct(r.wilson_bas_95)], ["Fréquence", r.par_jour == null ? "—" : `${nb(r.par_jour)} / jour`]]) +
      `<p class="ia-doux">Gelés : ${r.geles} dont ${r.en_attente} en attente de résultat. Période : ${esc(periode(r.periode))}. ${esc(r.tendance.texte)}</p>` +
      (r.dont_analyses_par_alpha ? `<p class="ia-doux">Dont matchs analysés par Alpha : ${r.dont_analyses_par_alpha.gagnes}/${r.dont_analyses_par_alpha.matchs}.</p>` : "") +
      `<h3>Résultats par semaine</h3>${lignesSemaines(r.par_semaine)}<h3>Cumulé semaine après semaine</h3>${lignesSemaines(r.cumule_par_semaine)}</section>` +
      (ref ? `<section class="ia-ref"><b>Étude historique (à part, jamais additionnée au suivi réel)</b><span>${esc(ref.nature)}</span>` +
        `<span>${ref.gagnes}/${ref.matchs} gagnés · ${pct(ref.taux)} · borne basse ${pct(ref.wilson_bas_95)} · ${esc(ref.periode)}</span></section>` : "") +
      (r.limites ? `<p class="ia-avert">${esc(r.limites)}</p>` : "") +
      `<p class="ia-doux">Contrôles : ${r.controles.doublons} doublon(s), ${r.controles.gels_non_anterieurs_au_coup_d_envoi} gel non antérieur au coup d'envoi (doivent valoir 0).</p>`;
  }

  function vueMarche() {
    const cur = D.indices.find((r) => r.id === choix) || D.indices[0];
    choix = cur.id;
    return `<div class="ia-chips" role="group" aria-label="Choisir un marché">${D.indices.map((r) => `<button type="button" data-id="${esc(r.id)}" aria-pressed="${r.id === cur.id}">${esc(r.nom)}</button>`).join("")}</div>` + ficheMarche(cur);
  }

  const VERD = { en_validation: "En validation", en_etude: "En étude (preuve insuffisante)", aucun_indice: "Aucun indice" };
  const st = (x) => (x ? `${x.gagnes}/${x.matchs} · ${pct(x.taux)} (bas ${pct(x.wilson_bas_95)}) · ${nb(x.par_jour)}/j` : "—");

  function carteRecherche(r) {
    const cote = r.cote_source ? " · avec la cote moyenne du marché" : "";
    const bp = r.cotes_betpawa, mm = r.cotes_moyenne_marche;
    return `<article class="ia-carte"><h3>${esc(r.nom || r.marche)}${esc(cote)}</h3><div class="ia-badges"><span class="ia-badge st-${r.verdict === "en_validation" ? "en_validation" : "en_etude"}">${esc(VERD[r.verdict] || r.verdict)}</span></div>` +
      (r.regle_texte ? `<p><b>Règle :</b> ${esc(r.regle_texte)}</p>` + (r.cote_source ? `<p class="ia-avert">Règle qui utilise la cote moyenne du marché (Football-Data) : elle n'est pas suivie en direct, car la cote BetPawa n'est pas la même. Information seulement.</p>` : `<p class="ia-doux">Suivie en direct (gel avant chaque match) si elle est en validation.</p>`) +
        `<div class="ia-ligne2"><span>Apprentissage 2025</span><span>${esc(st(r.apprentissage_A))}</span><span>Sélection janv.–mars 2026</span><span>${esc(st(r.selection_B))}</span>` +
        `<span><b>Vérification depuis avril</b></span><span><b>${esc(st(r.verification_C))}</b></span><span>Taux de base du marché</span><span>${pct(r.taux_de_base_C)}</span></div>` +
        (mm ? `<p class="ia-doux">Cotes moyennes du marché : ${mm.matchs} matchs, cote moyenne ${nb(mm.cote_moyenne)}, rendement ${pct(mm.rendement)}.</p>` : "") +
        (bp ? `<p class="ia-doux">Cotes BetPawa (28 jours) : ${bp.matchs} matchs, cote moyenne ${nb(bp.cote_moyenne)}, rendement ${pct(bp.rendement)} ; ${bp.jouables.matchs} à cote ≥ ${nb(bp.jouables.cote_min)} (${pct(bp.jouables.part, 0)}).</p>` : "") +
        `<p class="ia-doux">${esc(r.raison || "")}</p>` : `<p class="ia-vide">${esc(r.raison || "Aucune règle retenue.")}</p>`) + `</article>`;
  }

  function vueRecherche() {
    if (!R) return `<p class="ia-vide">Résultats de la recherche indisponibles.</p>`;
    const g = (v) => R.resultats.filter((r) => r.verdict === v);
    return `<section class="ia-carte"><h2>Recherche marché par marché</h2><p>Même protocole pour chaque marché : règle cherchée sur 2025, retenue sur janvier–mars 2026, vérifiée une seule fois depuis le 01/04/2026. ` +
      `Aucun seuil de réussite n'est imposé : une règle n'est « en validation » que si sa borne basse sur la vérification dépasse le taux de base du marché ET que son taux ne s'est pas dégradé. Aucun indice n'est « validé » ici : seul le suivi gelé en direct peut le dire.</p>` +
      `<p class="ia-doux">${nb(R.lignes_analysees)} matchs analysés par alpha · ${esc(R.genere_le)}.</p></section>` +
      ["en_validation", "en_etude", "aucun_indice"].map((v) => `<h2 class="at-h2">${esc(VERD[v])} — ${g(v).length}</h2>` + g(v).map(carteRecherche).join("")).join("");
  }

  function vueGestion() {
    return `<section class="ia-carte"><h2>Gestion des indices</h2><p>Règles actives, seuils et état de validation. Chaque indice est indépendant : modifier l'un ne change jamais les autres. ` +
      `Toute modification de règle, de seuil ou de statut doit être inscrite dans l'historique de l'indice ; sinon une alerte apparaît.</p>` +
      (D.alerte_registre.length ? `<div class="ia-alerte">${D.alerte_registre.map(esc).join("<br>")}</div>` : `<p class="ia-doux">Registre cohérent : aucune modification non tracée.</p>`) + `</section>` +
      D.indices.map((r) => `<section class="ia-carte"><h3>${esc(r.nom)}</h3>${badges(r)}<p><b>Marché :</b> ${esc(r.marche)}</p><p><b>Conditions :</b> ${esc(r.conditions)}</p>` +
        `<p><b>Seuils actifs :</b> <span class="ia-code">${esc(JSON.stringify(r.seuils))}</span></p>` +
        `<p class="ia-doux">Empreinte de la règle : <span class="ia-code">${esc(r.empreinte)}</span></p><h3>Historique des modifications</h3>` +
        `<ul class="ia-histo">${r.modifications.map((m) => `<li><b>${esc(jourFr(m.date))}</b> · ${esc(m.champ)} : ${esc(m.ancien == null ? "—" : m.ancien)} → ${esc(m.nouveau)}<br>${esc(m.motif)}<br><small>${esc(m.auteur)}</small></li>`).join("")}</ul></section>`).join("");
  }

  function rendre() {
    const el = document.getElementById("ia");
    el.innerHTML = vue === "total" ? vueTotal() : vue === "marche" ? vueMarche() : vue === "recherche" ? vueRecherche() : vueGestion();
    document.querySelectorAll("#ia-vues button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.vue === vue)));
  }

  document.addEventListener("click", (e) => {
    if (!D) return;
    const v = e.target.closest("#ia-vues button");
    if (v) { vue = v.dataset.vue; rendre(); return; }
    const b = e.target.closest("[data-id]");
    if (b && b.closest("#ia")) { choix = b.dataset.id; vue = "marche"; rendre(); window.scrollTo(0, 0); }
  });

  fetch(`data/alpha_serie/indice_alpha.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then((d) => {
      D = d;
      document.getElementById("maj").textContent = `Mis à jour le ${d.genere_le.slice(8, 10)}/${d.genere_le.slice(5, 7)} (pipeline de nuit).`;
      document.getElementById("ia-vues").hidden = false;
      rendre();
      fetch(`data/alpha_serie/decouverte_resultats.json?_=${Date.now()}`).then((r) => (r.ok ? r.json() : null)).then((x) => { R = x; if (vue === "recherche") rendre(); }).catch(() => {});
    })
    .catch((e) => { document.getElementById("maj").textContent = `Impossible de charger l'Indice Alpha (${e.message}). Aucune donnée n'est affichée plutôt que des chiffres faux.`; });
})();
