// af-alpha-tickets-vue.js — affichage de l'onglet « Traitement séquentiel des tickets (Moteur Alpha) » (25/10/2026, Patrick).
// Tout le calcul est dans af-alpha-tickets.js ; ce fichier ne fait que présenter. Libellés en mots simples : libelleClair
// (archetype_comportement.js, chargé avant). Les montants sont des mises simulées : rien n'est joué depuis le site.
(function () {
  "use strict";
  const T = window.AlphaTickets;
  const CLE_MISE = "alpha_tickets_mise";
  const esc = (x) => String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fcfa = (n) => `${Math.round(n).toLocaleString("fr-FR")} FCFA`;
  const cote = (x) => Number(x).toFixed(2).replace(".", ",");
  const pct = (x) => (x === null || x === undefined ? "—" : `${Math.round(x * 100)} %`);
  const clair = (c) => (typeof libelleClair === "function" ? libelleClair(c.marche, c.match.domicile, c.match.exterieur) : "");
  const compet = (m) => String(m.competition || "").replace(/\s+/g, " ").trim();
  const dateLongue = (iso) => {
    const d = new Date(`${iso}T12:00:00`);
    const t = d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
    return t.charAt(0).toUpperCase() + t.slice(1);
  };
  const aujourdhui = () => {
    const p = Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: "Africa/Douala", year: "numeric", month: "2-digit", day: "2-digit" })
      .formatToParts(new Date()).filter((x) => x.type !== "literal").map((x) => [x.type, x.value]));
    return `${p.year}-${p.month}-${p.day}`;
  };

  // « 2026-10-24 12:47 UTC » -> « 24/10 à 13 h 47 » (heure de Douala, UTC+1 toute l'année).
  const majDouala = (g) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(String(g || ""));
    if (!m) return String(g || "");
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4] + 1, +m[5]));
    return `${String(d.getUTCDate()).padStart(2, "0")}/${String(d.getUTCMonth() + 1).padStart(2, "0")} à ${d.getUTCHours()} h ${String(d.getUTCMinutes()).padStart(2, "0")}`;
  };
  let donnees = null, jour = null, mise = 500, longueurs = {};   // nombre de matchs choisis dans chaque palier
  try { const v = Number(localStorage.getItem(CLE_MISE)); if (v > 0) mise = v; } catch (e) { /* stockage indisponible */ }

  // Deux indices pour le « Plus de 1,5 buts » (af-alpha-tickets.js, REGLES.plus15*) : maximal (prioritaire) et normal (information seulement).
  const badgeMax = (c) => (c.indicePlus15 === "maximal"
    ? `<span class="at-max" title="Plus de 1,5 buts à indice maximal">★ Indice maximal</span>`
    : c.indicePlus15 === "normal" ? `<span class="at-normal" title="Plus de 1,5 buts à indice normal">Indice normal</span>` : "");
  const phraseMax = (c) => {
    const buts = c.totalAttendu === undefined ? "" : String(c.totalAttendu).replace(".", ",");
    const R = T.REGLES;
    if (c.indicePlus15 === "maximal")
      return `<li class="at-max-phrase"><b>Indice maximal :</b> on attend ${buts} buts dans ce match et, chez les deux équipes, au plus un match récent s'est fini à 0 ou 1 but. Les « plus de 1,5 buts » de ce niveau sont passés ${Math.round(R.plus15Taux * 100)} fois sur 100 (${R.plus15Matchs.toLocaleString("fr-FR")} matchs testés).</li>`;
    if (c.indicePlus15 === "normal")
      return `<li class="at-max-phrase"><b>Indice normal :</b> on attend ${buts} buts dans ce match, mais plusieurs matchs récents des deux équipes se sont finis à 0 ou 1 but. Les « plus de 1,5 buts » de ce niveau sont passés ${Math.round(R.plus15NormalTaux * 100)} fois sur 100 (${R.plus15NormalMatchs.toLocaleString("fr-FR")} matchs testés).</li>`;
    return "";
  };

  function ligneSelection(c) {
    return `<li class="at-sel${c.chancesMax ? " at-sel-max" : ""}">` +
      `<div class="at-sel-haut"><span class="at-heure">${esc(c.match.heure)}</span><span class="at-match">${esc(c.match.domicile)} – ${esc(c.match.exterieur)}</span><strong class="at-cote">${cote(c.cote)}</strong></div>` +
      `<div class="at-sel-pari">${typeof afMarcheHtml === "function" ? afMarcheHtml(c.marche, clair(c)) : esc(c.marche)} ${badgeMax(c)}</div>` +
      `<div class="at-sel-bas"><span>${esc(compet(c.match))}</span><span>${esc(c.nomCategorie)} · ${pct(c.valeur)} de chances · confirmé ${pct(c.confirmation)} · ${c.matchs} matchs comparés</span></div>` +
      `</li>`;
  }

  function blocMontants(c, m) {
    const retour = m * c;
    return `<div class="at-montants">` +
      `<div><small>Cote totale</small><strong title="${c.toFixed(6)}">${cote(c)}</strong></div>` +
      `<div><small>Mise</small><strong>${fcfa(m)}</strong></div>` +
      `<div><small>Retour si tout passe</small><strong>${fcfa(retour)}</strong></div>` +
      `<div><small>Bénéfice</small><strong class="at-plus">+${fcfa(retour - m)}</strong></div>` +
      `<div><small>Si le ticket perd</small><strong class="at-moins">−${fcfa(m)}</strong></div></div>`;
  }

  function carteTranche(t) {
    const ecartes = t.candidats.filter((c) => !c.rang);
    const corps = t.ticket.length
      ? `<ul class="at-sels">${t.ticket.map(ligneSelection).join("")}</ul>${blocMontants(t.cote, mise)}`
      : `<p class="at-vide">Aucun pari ne remplit les règles dans cette tranche.</p>`;
    const liste = ecartes.length
      ? `<details class="at-ecartes"><summary>Pourquoi les autres paris ne sont pas pris (${ecartes.length})</summary><ul>` +
        ecartes.map((c) => `<li><b>${esc(c.match.heure)} ${esc(c.match.domicile)} – ${esc(c.match.exterieur)}</b> · ${esc(c.nomCategorie)} : ${esc(c.marche)} (${cote(c.cote)}) — ${esc(c.statut)}</li>`).join("") +
        `</ul></details>` : "";
    return `<section class="ax-carte at-carte"><h3 class="at-titre"><span>${esc(t.nom)}</span><small>${t.candidats.length ? `${t.admissibles.length} pari${t.admissibles.length > 1 ? "s" : ""} sur ${t.candidats.length} rempli${t.admissibles.length > 1 ? "ssent" : "t"} les règles` : "aucun match"}</small></h3>${corps}${liste}</section>`;
  }

  function sectionA(etapes) {
    if (!etapes.length) return "";
    const lignes = etapes.map((e, i) => {
      const r = mise * e.cote;
      return `<li class="at-etape"><div class="at-etape-tete"><span class="at-num">${e.selections}</span><div><b>${esc(e.tranche)}</b> · + ${esc(e.ajout.match.domicile)} – ${esc(e.ajout.match.exterieur)}<br><small>${esc(clair(e.ajout) || e.ajout.marche)} · ${cote(e.ajout.cote)}</small></div></div>` +
        `<div class="at-etape-chiffres"><span>Cote <b>${cote(e.cote)}</b></span><span>Retour <b>${fcfa(r)}</b></span><span>Bénéfice <b class="at-plus">+${fcfa(r - mise)}</b></span>${i ? `<span>+${fcfa(r - mise * etapes[i - 1].cote)} par rapport au précédent</span>` : ""}</div></li>`;
    }).join("");
    return `<section class="ax-carte at-carte"><h3 class="at-titre"><span>Méthode A — un seul ticket qui s'allonge</span><small>Validé avant le premier match. On ajoute le meilleur pari de chaque tranche. Mise de ${fcfa(mise)} ; si un seul pari perd, le ticket perd ${fcfa(mise)}.</small></h3><ol class="at-etapes">${lignes}</ol></section>`;
  }

  function carteChaine(c) {
    const f = T.finances(c, mise);
    const etapes = c.etapes.map((e, i) => {
      const t = f.total[i], p = f.prudent[i];
      const delai = i ? `<p class="at-delai${e.conditionnel ? " at-alerte" : ""}">Matchs précédents finis vers ${T.heure(e.finPrecedente)} ; premier match de cette étape à ${esc(e.selections[0].match.heure)}${e.conditionnel ? " : marge courte, à jouer seulement si le gain précédent est déjà payé" : ""}.${e.partiel ? " Seuls les matchs qui commencent après ce délai sont gardés." : ""}</p>` : "";
      return `<li class="at-etape"><div class="at-etape-tete"><span class="at-num">${i + 1}</span><div><b>${esc(e.tranche)}</b> · cote ${cote(t.cote)}</div></div>` +
        `<ul class="at-sels at-sels-court">${e.selections.map((s) => `<li>${esc(s.match.heure)} ${esc(s.match.domicile)} – ${esc(s.match.exterieur)} · ${esc(clair(s) || s.marche)} (${cote(s.cote)})</li>`).join("")}</ul>${delai}` +
        `<div class="at-deux"><div><small>Tout réinvestir</small><span>Mise ${fcfa(t.mise)} → ${fcfa(t.retour)}</span><span class="at-moins">Si perd : il reste ${fcfa(0)} (perte ${fcfa(t.siPerdPerteTotale)}${t.siPerdBeneficesPerdus > 0 ? ` + ${fcfa(t.siPerdBeneficesPerdus)} déjà gagnés` : ""})</span></div>` +
        `<div><small>Prudent : ${fcfa(mise)} mis de côté après le 1er gain</small><span>Mise ${fcfa(p.mise)} → ${fcfa(p.retour)}${i === 0 ? ` (garder ${fcfa(mise)}, rejouer ${fcfa(p.retour - mise)})` : ""}</span><span class="${i ? "at-plus" : "at-moins"}">Si perd : il reste ${fcfa(p.siPerdSolde)}${i ? ` (bénéfice perdu ${fcfa(p.siPerdBeneficePerdu)})` : ` (perte ${fcfa(mise)})`}</span></div></div></li>`;
    }).join("");
    return `<section class="ax-carte at-carte"><h3 class="at-titre"><span>${esc(c.nom)} — ${c.etapes.length} étapes, ${c.selections} paris</span><small>Tout réinvestir : ${fcfa(f.finalTotal)} si tout passe. Prudent : ${fcfa(f.finalPrudent)}.</small></h3><ol class="at-etapes">${etapes}</ol></section>`;
  }

  function comparaison(a) {
    const lignes = [];
    if (a.methodeA.length) {
      const e = a.methodeA[a.methodeA.length - 1];
      lignes.push(["Méthode A", `${e.selections} paris, un seul ticket`, mise * e.cote, "Non"]);
    }
    for (const c of a.chaines.slice(0, 3)) {
      const f = T.finances(c, mise);
      lignes.push([`${c.nom} tout réinvestir`, `${c.selections} paris, ${c.etapes.length} étapes`, f.finalTotal, "Oui"]);
      lignes.push([`${c.nom} prudent`, `${c.selections} paris, ${c.etapes.length} étapes`, f.finalPrudent, "Oui"]);
    }
    if (!lignes.length) return "";
    return `<section class="ax-carte at-carte at-resume"><h3 class="at-titre"><span>Comparer les stratégies</span><small>Avec ${fcfa(mise)}, on n'en choisit qu'une : elles utilisent la même mise et en partie les mêmes matchs. Les gains ne s'additionnent pas.</small></h3>` +
      `<ul class="at-strats">${lignes.map(([n, d, r, dep]) => `<li><div><b>${esc(n)}</b><small>${esc(d)}${dep === "Oui" ? " · dépend des résultats précédents" : " · validé d'avance"}</small></div><div><strong>${fcfa(r)}</strong><small>si tout passe · perte max. ${fcfa(mise)}</small></div></li>`).join("")}</ul></section>`;
  }

  function regles() {
    const R = T.REGLES;
    return `<details class="ax-carte at-carte at-regles"><summary>Les règles utilisées</summary><ul>` +
      `<li>Seulement les catégories Buts, Équipes et Calibrés du moteur alpha, avec leur cote BetPawa affichée (au moins ${cote(R.coteMin)}). Pas de Multigoals ni de Multiscores.</li>` +
      `<li>Un pari est pris s'il a au moins ${Math.round(R.valeurMin * 100)} % de chances selon l'alpha, s'il est confirmé dans au moins ${Math.round(R.confirmationMin * 100)} % des matchs des deux équipes, avec au moins ${R.matchsMin} matchs comparés, et si ce n'est pas un pari de remplacement.</li>` +
      `<li>Dans chaque tranche de 2 heures (à partir de 10 h) : les ${R.parTranche} meilleurs, un seul pari par match. À égalité : la cote la plus basse.</li>` +
      `<li>Réinvestir n'est possible que si les matchs précédents sont finis et payés : on compte ${R.dureeMatch} minutes par match et ${R.delaiReglement} minutes pour le paiement.</li>` +
      `<li>Ces règles sont celles de l'analyse validée le 25/10/2026 ; elles ne changent pas le moteur alpha. Aucun gain n'est garanti.</li></ul></details>`;
  }

  // Vue simple (25/10/2026, Patrick : « un utilisateur qui n'a jamais entendu parler de ça doit comprendre ») :
  // un seul ticket, les matchs dans l'ordre, ce qu'on gagne et ce qu'on perd ; tout le reste est replié pour les connaisseurs.
  const ptsMatch = (x) => Number(x).toFixed(2).replace(".", ",");
  // Les éléments qui ont décidé le choix, écrits en clair (25/10/2026, Patrick : « ces paramètres ne sont marqués nulle part »).
  function pourquoiCeMatch(c) {
    const m = c.match, e = (c.pronostic && c.pronostic.explication) || {}, g = m.graduation || {};
    const conf = Array.isArray(e.domicile) && Array.isArray(e.exterieur)
      ? `Ce pari serait passé dans ${e.domicile[0]} des ${e.domicile[1]} matchs de ${esc(m.domicile)} à domicile et dans ${e.exterieur[0]} des ${e.exterieur[1]} matchs de ${esc(m.exterieur)} à l'extérieur.` : "";
    const niv = g.dom && g.ext && Number.isFinite(Number(g.dom.pts_match)) && Number.isFinite(Number(g.ext.pts_match))
      ? `Classement : ${esc(m.domicile)} ${ptsMatch(g.dom.pts_match)} point par match, ${esc(m.exterieur)} ${ptsMatch(g.ext.pts_match)}.` : "Classement non disponible.";
    return `<ul class="at-pourquoi">${phraseMax(c)}<li>Chances selon le moteur : <b>${pct(c.valeur)}</b> · comparé sur <b>${Number(m.n_domicile) || 0} et ${Number(m.n_exterieur) || 0} matchs</b>.</li>` +
      (conf ? `<li>${conf}</li>` : "") + `<li>${niv}</li></ul>`;
  }

  // Un ticket de palier : les paris dans l'ordre du classement (le multiplicateur s'ajoute dans cet ordre), affichés par heure.
  function carteTicket(cle, titre, phrase, picks, classe) {
    if (!picks.length) return "";
    let c = 1;
    const etapes = picks.map((x) => ({ ajout: x, cote: (c *= x.cote) }));
    const n = Math.min(longueurs[cle] || etapes.length, etapes.length), e = etapes[n - 1];
    const choisis = etapes.slice(0, n).map((x) => x.ajout).sort((x, y) => x.debut - y.debut);
    const choix = etapes.length > 1 ? `<div class="at-choix" role="group" aria-label="Nombre de matchs dans le ticket">${etapes.map((x, i) => `<button type="button" data-palier="${cle}" data-longueur="${i + 1}" aria-pressed="${i + 1 === n}">${i + 1} match${i ? "s" : ""}<small>× ${cote(x.cote)}</small></button>`).join("")}</div>` +
      `<p class="at-aide">Plus de matchs = gain plus grand, mais beaucoup plus de risques que le ticket perde. Les matchs s'ajoutent du plus sûr au moins sûr.</p>` : "";
    const lignes = choisis.map((x, i) => `<li><span class="at-num">${i + 1}</span><div><p class="at-qui"><b>${esc(x.match.heure)}</b> · ${esc(x.match.domicile)} – ${esc(x.match.exterieur)}</p>` +
      `<p class="at-quoi">${esc(clair(x) || x.marche)} ${badgeMax(x)}</p><p class="at-ou">${esc(compet(x.match))} · sur Betpawa : « ${esc(x.marche)} » à ${cote(x.cote)}</p>${pourquoiCeMatch(x)}</div></li>`).join("");
    return `<section class="ax-carte at-carte at-simple ${classe || ""}"><h2 class="at-simple-titre">${titre}</h2>` +
      `<p class="at-phrase">${phrase} Mets ces ${n} match${n > 1 ? "s" : ""} sur <b>un seul ticket</b>, avant ${esc(choisis[0].match.heure)}.</p>` + choix +
      `<div class="at-gros"><div><small>Tu mises</small><strong>${fcfa(mise)}</strong></div><div class="at-fleche" aria-hidden="true">→</div><div><small>Si tout passe, tu reçois</small><strong class="at-plus">${fcfa(mise * e.cote)}</strong></div></div>` +
      `<p class="at-risque">Si <b>un seul</b> de ces matchs rate, tu perds tes ${fcfa(mise)}.</p><ol class="at-liste-simple">${lignes}</ol></section>`;
  }

  function ticketDuJour(a) {
    if (!a.palier1.length) return `<section class="ax-carte at-carte at-simple"><h2 class="at-simple-titre">Pas de ticket ce jour-là</h2><p class="at-vide">Aucun match ne remplit nos règles entre 10 h et minuit. Mieux vaut ne pas jouer que jouer au hasard.</p></section>`;
    return carteTicket("p1", "Palier 1 — le ticket du jour", "Le meilleur pari de chaque créneau de 2 heures.", a.palier1, "") +
      carteTicket("p2", "Palier 2 — les suivants", `Les ${a.palier2.length} meilleurs paris restants de la journée, choisis avec les mêmes règles que le palier 1 (aucun match du palier 1).`, a.palier2, "at-palier2");
  }

  function commentCaMarche() {
    return `<details class="ax-carte at-carte at-regles"><summary>Comment ces matchs sont choisis ?</summary><ul>` +
      `<li>Le moteur alpha regarde les derniers matchs de chaque équipe : à domicile pour celle qui reçoit, à l'extérieur pour l'autre.</li>` +
      `<li>On garde seulement les paris que ces matchs confirment presque à chaque fois, avec une cote Betpawa.</li>` +
      `<li>Un pari est gardé si le moteur lui donne au moins ${Math.round(T.REGLES.valeurMin * 100)} % de chances, s'il serait passé dans au moins ${Math.round(T.REGLES.confirmationMin * 100)} % des derniers matchs de chaque équipe, avec au moins ${T.REGLES.matchsMin} matchs comparés de chaque côté.</li>` +
      `<li>Palier 1 : le meilleur pari de chaque créneau de 2 heures, de 10 h à minuit. Palier 2 : les ${T.REGLES.palier2Max} meilleurs paris restants de la journée, mêmes règles.</li>` +
      `<li>Rien n'est sûr à 100 % : un match peut toujours surprendre. Ne mise que ce que tu peux te permettre de perdre.</li></ul></details>`;
  }

  // Palier 3 — en test (25/10/2026) : « le domicile ne marque pas plus de 2 buts » quand nos chiffres battent la cote (alpha_serie/palier2.py).
  function palierTrois() {
    const lst = (donnees.matchs || []).filter((m) => m.date === jour && m.statut === "analyse" && (m.palier2 || []).length)
      .map((m) => ({ m, p: m.palier2[0], debut: T.minutes(m.heure) }))
      .filter((x) => x.debut !== null && x.debut >= T.REGLES.debut && x.debut < T.REGLES.fin).sort((a, b) => a.debut - b.debut);
    if (!lst.length) return "";
    const cote2 = lst.reduce((c, x) => c * Number(x.p.cote), 1);
    const lignes = lst.map((x, i) => `<li><span class="at-num">${i + 1}</span><div><p class="at-qui"><b>${esc(x.m.heure)}</b> · ${esc(x.m.domicile)} – ${esc(x.m.exterieur)}</p>` +
      `<p class="at-quoi">${esc(x.m.domicile)} ne marque pas plus de 2 buts</p><p class="at-ou">${esc(compet(x.m))} · sur Betpawa : « ${esc(x.m.domicile)} moins de 2,5 » à ${cote(x.p.cote)}</p>` +
      `<ul class="at-pourquoi"><li>Nos chiffres : <b>${pct(x.p.p_estimee)}</b> de chances ; la cote en donne ${pct(x.p.p_cote)}.</li>` +
      `<li>${esc(x.m.domicile)} a marqué 2 buts ou moins dans ${x.p.domicile_au_plus_2[0]} de ses ${x.p.domicile_au_plus_2[1]} derniers matchs à domicile ; ` +
      `${esc(x.m.exterieur)} en a encaissé 2 ou moins dans ${x.p.exterieur_encaisse_au_plus_2[0]} de ses ${x.p.exterieur_encaisse_au_plus_2[1]} matchs à l'extérieur.</li></ul></div></li>`).join("");
    return `<section class="ax-carte at-carte at-simple at-palier3"><h2 class="at-simple-titre">Palier 3 — en test</h2>` +
      `<p class="at-phrase">Un ticket à part, sur un pari où nos chiffres donnent plus de chances que Betpawa. <b>En test</b> : il a gagné 77 % du temps sur un mois de matchs passés ; ses vrais résultats sont suivis chaque jour.</p>` +
      `<div class="at-gros"><div><small>Tu mises</small><strong>${fcfa(mise)}</strong></div><div class="at-fleche" aria-hidden="true">→</div><div><small>Si tout passe, tu reçois</small><strong class="at-plus">${fcfa(mise * cote2)}</strong></div></div>` +
      `<p class="at-risque">${lst.length} match${lst.length > 1 ? "s" : ""}, cote ${cote(cote2)}. Si un seul rate, tu perds ta mise.</p><ol class="at-liste-simple">${lignes}</ol></section>`;
  }

  // Vrais résultats des tickets gelés avant les matchs (alpha_serie/tickets.py, suivi chaque nuit).
  function resultatsTickets() {
    const b = donnees.bilan_tickets;
    if (!b) return "";
    if (!b.jours_regles) return `<p class="at-aide at-suivi">Suivi des tickets commencé le 25/10/2026 : les vrais résultats s'afficheront ici après le premier jour joué.</p>`;
    const tuile = (nom, x) => (x && x.tickets ? `<div class="ax-perf-tuile"><span class="ax-perf-nom">${nom}</span><strong>${x.gagnes}/${x.tickets}</strong><small>tickets gagnés · ${x.paris_gagnes}/${x.paris} matchs</small></div>` : "");
    return `<section class="ax-perf" aria-label="Vrais résultats des tickets"><p class="ax-perf-titre">Vrais résultats des tickets (gelés avant les matchs, ${b.jours_regles} jour${b.jours_regles > 1 ? "s" : ""})</p>` +
      `<div class="ax-perf-grille">${tuile("Palier 1", b.palier1)}${tuile("Palier 2", b.palier2)}${tuile("Palier 3 (test)", b.palier3)}</div></section>`;
  }

  function rendu() {
    const zone = document.getElementById("tickets");
    if (!donnees || !zone) return;
    const a = T.analyse(donnees, jour);
    zone.innerHTML =
      resultatsTickets() +
      ticketDuJour(a) +
      palierTrois() +
      commentCaMarche() +
      `<details class="at-expert"><summary>Pour les connaisseurs : autres façons de jouer</summary>` +
      comparaison(a) +
      `<h2 class="at-h2">Tickets par tranche de 2 heures</h2>${a.tranches.filter((t) => t.candidats.length).map(carteTranche).join("") || '<p class="at-vide">Aucun match ce jour-là.</p>'}` +
      (a.methodeA.length ? `<h2 class="at-h2">Ticket progressif</h2>${sectionA(a.methodeA)}` : "") +
      (a.chaines.length ? `<h2 class="at-h2">Réinvestir les gains d'une tranche à l'autre</h2>${a.chaines.slice(0, 3).map(carteChaine).join("")}` : "") +
      regles() + `</details>`;
    zone.querySelectorAll("[data-longueur]").forEach((b) => b.addEventListener("click", () => { longueurs[b.dataset.palier] = Number(b.dataset.longueur); rendu(); }));
  }

  function controles() {
    const z = document.getElementById("at-controles"), js = T.jours(donnees, aujourdhui());
    if (!js.includes(jour)) jour = js[0] || aujourdhui();
    z.innerHTML =
      `<div class="at-jours" role="group" aria-label="Choix du jour">${js.slice(0, 4).map((j) => `<button type="button" data-jour="${j}" aria-pressed="${j === jour}">${esc(dateLongue(j).split(" ").slice(0, 2).join(" "))}</button>`).join("")}</div>` +
      `<label class="at-mise"><span>Ta mise</span><input id="at-mise" type="number" inputmode="numeric" min="5" step="5" value="${mise}"><span>FCFA</span></label>` +
      `<div class="at-presets">${[100, 500, 1000].map((v) => `<button type="button" data-mise="${v}">${v.toLocaleString("fr-FR")}</button>`).join("")}</div>`;
    z.querySelectorAll("[data-jour]").forEach((b) => b.addEventListener("click", () => { jour = b.dataset.jour; longueurs = {}; controles(); rendu(); }));
    const champ = z.querySelector("#at-mise");
    const fixe = (v) => { if (v > 0) { mise = v; try { localStorage.setItem(CLE_MISE, String(v)); } catch (e) { /* ignoré */ } champ.value = v; rendu(); } };
    champ.addEventListener("input", () => fixe(Number(champ.value)));
    z.querySelectorAll("[data-mise]").forEach((b) => b.addEventListener("click", () => fixe(Number(b.dataset.mise))));
  }

  if (document.getElementById("tickets")) {
    fetch(`data/alpha_serie/pronostics.json?_=${Date.now()}`)
      .then((r) => { if (!r.ok) throw new Error(`données introuvables (${r.status})`); return r.json(); })
      .then((d) => {
        donnees = d;
        const maj = document.getElementById("maj");
        if (maj) maj.innerHTML = `Pronostics et cotes du moteur alpha mis à jour le <strong>${esc(majDouala(d.genere_le))}</strong>. Les cotes peuvent avoir changé depuis : vérifie-les avant de jouer.`;
        controles(); rendu();
      })
      .catch((e) => { const maj = document.getElementById("maj"); if (maj) maj.textContent = "Données du moteur alpha indisponibles : " + e.message; console.error(e); });
  }
})();
