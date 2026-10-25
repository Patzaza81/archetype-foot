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
  let donnees = null, jour = null, mise = 500, longueur = null;   // longueur : nombre de matchs choisis dans le ticket du jour
  try { const v = Number(localStorage.getItem(CLE_MISE)); if (v > 0) mise = v; } catch (e) { /* stockage indisponible */ }

  function ligneSelection(c) {
    return `<li class="at-sel">` +
      `<div class="at-sel-haut"><span class="at-heure">${esc(c.match.heure)}</span><span class="at-match">${esc(c.match.domicile)} – ${esc(c.match.exterieur)}</span><strong class="at-cote">${cote(c.cote)}</strong></div>` +
      `<div class="at-sel-pari">${typeof afMarcheHtml === "function" ? afMarcheHtml(c.marche, clair(c)) : esc(c.marche)}</div>` +
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
  function ticketDuJour(a) {
    const etapes = a.methodeA;
    if (!etapes.length) return `<section class="ax-carte at-carte at-simple"><h2 class="at-simple-titre">Pas de ticket ce jour-là</h2><p class="at-vide">Aucun match ne remplit nos règles entre 10 h et minuit. Mieux vaut ne pas jouer que jouer au hasard.</p></section>`;
    const n = Math.min(longueur || etapes.length, etapes.length), e = etapes[n - 1], choisis = etapes.slice(0, n);
    const retour = mise * e.cote;
    const choix = etapes.length > 1 ? `<div class="at-choix" role="group" aria-label="Nombre de matchs dans le ticket">${etapes.map((x, i) => `<button type="button" data-longueur="${i + 1}" aria-pressed="${i + 1 === n}">${i + 1} match${i ? "s" : ""}<small>× ${cote(x.cote)}</small></button>`).join("")}</div>` +
      `<p class="at-aide">Moins de matchs = gain plus petit, mais plus de chances que le ticket passe.</p>` : "";
    const lignes = choisis.map((x, i) => `<li><span class="at-num">${i + 1}</span><div><p class="at-qui"><b>${esc(x.ajout.match.heure)}</b> · ${esc(x.ajout.match.domicile)} – ${esc(x.ajout.match.exterieur)}</p>` +
      `<p class="at-quoi">${esc(clair(x.ajout) || x.ajout.marche)}</p><p class="at-ou">${esc(compet(x.ajout.match))} · sur Betpawa : « ${esc(x.ajout.marche)} » à ${cote(x.ajout.cote)}</p></div></li>`).join("");
    return `<section class="ax-carte at-carte at-simple">` +
      `<h2 class="at-simple-titre">Le ticket du jour</h2>` +
      `<p class="at-phrase">Mets ces ${n} match${n > 1 ? "s" : ""} sur <b>un seul ticket</b>, avant ${esc(choisis[0].ajout.match.heure)}.</p>` +
      choix +
      `<div class="at-gros"><div><small>Tu mises</small><strong>${fcfa(mise)}</strong></div><div class="at-fleche" aria-hidden="true">→</div><div><small>Si tout passe, tu reçois</small><strong class="at-plus">${fcfa(retour)}</strong></div></div>` +
      `<p class="at-risque">Si <b>un seul</b> de ces matchs rate, tu perds tes ${fcfa(mise)}.</p>` +
      `<ol class="at-liste-simple">${lignes}</ol></section>`;
  }

  function commentCaMarche() {
    return `<details class="ax-carte at-carte at-regles"><summary>Comment ces matchs sont choisis ?</summary><ul>` +
      `<li>Le moteur alpha regarde les derniers matchs de chaque équipe : à domicile pour celle qui reçoit, à l'extérieur pour l'autre.</li>` +
      `<li>On garde seulement les paris que ces matchs confirment presque à chaque fois, avec une cote Betpawa.</li>` +
      `<li>On prend le meilleur pari de chaque créneau de 2 heures, de 10 h à minuit.</li>` +
      `<li>Rien n'est sûr à 100 % : un match peut toujours surprendre. Ne mise que ce que tu peux te permettre de perdre.</li></ul></details>`;
  }

  function rendu() {
    const zone = document.getElementById("tickets");
    if (!donnees || !zone) return;
    const a = T.analyse(donnees, jour);
    zone.innerHTML =
      ticketDuJour(a) +
      commentCaMarche() +
      `<details class="at-expert"><summary>Pour les connaisseurs : autres façons de jouer</summary>` +
      comparaison(a) +
      `<h2 class="at-h2">Tickets par tranche de 2 heures</h2>${a.tranches.filter((t) => t.candidats.length).map(carteTranche).join("") || '<p class="at-vide">Aucun match ce jour-là.</p>'}` +
      (a.methodeA.length ? `<h2 class="at-h2">Ticket progressif</h2>${sectionA(a.methodeA)}` : "") +
      (a.chaines.length ? `<h2 class="at-h2">Réinvestir les gains d'une tranche à l'autre</h2>${a.chaines.slice(0, 3).map(carteChaine).join("")}` : "") +
      regles() + `</details>`;
    zone.querySelectorAll("[data-longueur]").forEach((b) => b.addEventListener("click", () => { longueur = Number(b.dataset.longueur); rendu(); }));
  }

  function controles() {
    const z = document.getElementById("at-controles"), js = T.jours(donnees, aujourdhui());
    if (!js.includes(jour)) jour = js[0] || aujourdhui();
    z.innerHTML =
      `<div class="at-jours" role="group" aria-label="Choix du jour">${js.slice(0, 4).map((j) => `<button type="button" data-jour="${j}" aria-pressed="${j === jour}">${esc(dateLongue(j).split(" ").slice(0, 2).join(" "))}</button>`).join("")}</div>` +
      `<label class="at-mise"><span>Ta mise</span><input id="at-mise" type="number" inputmode="numeric" min="5" step="5" value="${mise}"><span>FCFA</span></label>` +
      `<div class="at-presets">${[100, 500, 1000].map((v) => `<button type="button" data-mise="${v}">${v.toLocaleString("fr-FR")}</button>`).join("")}</div>`;
    z.querySelectorAll("[data-jour]").forEach((b) => b.addEventListener("click", () => { jour = b.dataset.jour; longueur = null; controles(); rendu(); }));
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
