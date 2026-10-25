// af-alpha-tickets.js — Traitement séquentiel des tickets du moteur alpha (25/10/2026, demande de Patrick).
// Code la procédure de l'audit validé le 25/10/2026 (tranches de 2 heures à partir de 10 h, ticket progressif,
// réinvestissement conditionnel et variante prudente). Présentation et calcul seulement :
// - aucune donnée nouvelle : les marchés, valeurs et cotes sont ceux déjà publiés par l'alpha (data/alpha_serie/pronostics.json) ;
// - le meilleur marché de chaque catégorie est celui du site (af-alpha-selection.js, meilleurAffichable), jamais recalculé ici ;
// - le moteur alpha (alpha_serie/) n'est ni appelé ni modifié ; aucun résultat passé n'entre dans la sélection.
//
// Règles de cette procédure (règles de l'analyse validée, PAS des paramètres du moteur alpha) :
//  1. Catégories Buts, Équipes, Calibrés (Multigoals et Multiscores exclus) : le meilleur marché affiché de chaque catégorie.
//  2. Admissible si : cote ≥ 1,25 ; pas un marché remplaçant ; valeur alpha ≥ 80 % ; confirmation sur les matchs propres
//     des deux équipes ≥ 75 % (la plus faible des deux) ; au moins 5 matchs comparés pour chaque équipe.
//  3. Ticket d'une tranche : admissibles classés par valeur, puis confirmation, puis matchs comparés, puis cote la plus basse
//     (convention de départage) ; un seul marché par match ; au plus 2 matchs.
//  4. Ticket progressif (méthode A) : le premier de chaque tranche, ajouté tranche après tranche, validé d'avance.
//  5. Réinvestissement (méthode B) : le ticket suivant ne peut être joué que si les matchs du ticket précédent sont finis
//     et réglés : fin estimée = dernier coup d'envoi + 115 min, plus 15 min de règlement ; marge < 30 min = « conditionnel ».
//     Seuls les matchs de la tranche suivante qui commencent après ce délai sont gardés.
(function (racine) {
  const REGLES = Object.freeze({
    categories: ["buts", "equipes", "calibrees"],
    coteMin: 1.25, valeurMin: 0.80, confirmationMin: 0.75, matchsMin: 5, parTranche: 2,
    debut: 10 * 60, pas: 120, fin: 24 * 60, palier2Max: 10,
    dureeMatch: 115, delaiReglement: 15, margeConfortable: 30,
  });

  const sel = () => (typeof module !== "undefined" && module.exports ? require("./af-alpha-selection.js") : racine);
  const minutes = (h) => { const m = /^(\d{1,2}):(\d{2})$/.exec(String(h || "")); return m ? Number(m[1]) * 60 + Number(m[2]) : null; };
  const heure = (mn) => `${String(Math.floor(mn / 60) % 24).padStart(2, "0")}:${String(mn % 60).padStart(2, "0")}`;
  const nomTranche = (d) => `${Math.floor(d / 60)}h–${Math.floor((d + REGLES.pas) / 60)}h`;

  // Part des matchs propres (domicile de l'équipe qui reçoit, extérieur de l'autre) où le pari serait passé : la plus faible des deux.
  function confirmation(s) {
    const e = (s && s.explication) || {};
    const parts = ["domicile", "exterieur"].map((k) => (Array.isArray(e[k]) && Number(e[k][1]) > 0 ? Number(e[k][0]) / Number(e[k][1]) : null)).filter((x) => x !== null);
    return parts.length ? Math.min(...parts) : null;
  }

  function raisonsExclusion(c) {
    const r = [];
    if (!(c.cote >= REGLES.coteMin)) r.push(`cote inférieure à ${String(REGLES.coteMin).replace(".", ",")}`);
    if (c.remplacant) r.push("marché remplaçant (le premier marché de la catégorie n'a pas de cote)");
    if (!(c.valeur >= REGLES.valeurMin - 1e-9)) r.push(`chances alpha ${Math.round(c.valeur * 100)} %, moins de ${Math.round(REGLES.valeurMin * 100)} %`);
    if (c.confirmation === null) r.push("confirmation sur les matchs des équipes indisponible");
    else if (c.confirmation < REGLES.confirmationMin - 1e-9) r.push(`confirmé dans ${Math.round(c.confirmation * 100)} % des matchs des équipes, moins de ${Math.round(REGLES.confirmationMin * 100)} %`);
    if (!(c.matchs >= REGLES.matchsMin)) r.push(`${c.matchs} matchs comparés, moins de ${REGLES.matchsMin}`);
    return r;
  }

  // Meilleur marché affiché de chaque catégorie (Buts, Équipes, Calibrés) pour les matchs du jour, avec son admissibilité.
  function candidats(matchs, jour) {
    const S = sel(), out = [];
    for (const m of matchs || []) {
      if (m.statut !== "analyse" || m.date !== jour) continue;
      const debut = minutes(m.heure);
      if (debut === null) continue;
      for (const cat of S.CATEGORIES_ALPHA.filter((c) => REGLES.categories.includes(c.cle))) {
        const s = S.meilleurAffichable(m, cat);
        if (!s) continue;
        const c = {
          id: `${m.match_id}|${cat.cle}`, match_id: m.match_id, match: m, categorie: cat.cle, nomCategorie: cat.nom, marche: s.marche,
          cote: Number(s.cote), valeur: Number(s.valeur) || 0, confirmation: confirmation(s),
          matchs: Math.min(Number(m.n_domicile) || 0, Number(m.n_exterieur) || 0), remplacant: S.estRemplacant(m, cat), debut, pronostic: s,
        };
        c.raisons = raisonsExclusion(c);
        c.admissible = c.raisons.length === 0;
        out.push(c);
      }
    }
    return out;
  }

  // Classement écrit : valeur, confirmation, matchs comparés, cote la plus basse ; puis ordre stable (heure, identifiant).
  function compare(a, b) {
    return (b.valeur - a.valeur) || ((b.confirmation || 0) - (a.confirmation || 0)) || (b.matchs - a.matchs) || (a.cote - b.cote) ||
      (a.debut - b.debut) || String(a.id).localeCompare(String(b.id));
  }
  const coteTotale = (sels) => sels.reduce((p, s) => p * s.cote, 1);

  function tranches(cands) {
    const out = [];
    for (let d = REGLES.debut; d < REGLES.fin; d += REGLES.pas) {
      const ici = cands.filter((c) => c.debut >= d && c.debut < d + REGLES.pas);
      const admis = ici.filter((c) => c.admissible).sort(compare);
      const ticket = [], vus = new Set();
      for (const c of admis) {
        if (vus.has(c.match_id)) { c.statut = "écarté : un autre marché de ce match est déjà retenu"; continue; }
        if (ticket.length < REGLES.parTranche) { ticket.push(c); vus.add(c.match_id); c.statut = `retenu (rang ${ticket.length})`; c.rang = ticket.length; }
        else c.statut = `admissible, non retenu : au-delà des ${REGLES.parTranche} meilleurs de la tranche`;
      }
      for (const c of ici) if (!c.admissible) c.statut = `écarté : ${c.raisons.join(" ; ")}`;
      out.push({ nom: nomTranche(d), debut: d, fin: d + REGLES.pas, candidats: ici.sort((a, b) => a.debut - b.debut || compare(a, b)), admissibles: admis, ticket, cote: ticket.length ? coteTotale(ticket) : null });
    }
    return out;
  }

  // Méthode A : un seul ticket validé d'avance ; on ajoute le premier de chaque tranche non vide.
  function methodeA(trs) {
    const etapes = []; let cote = 1;
    for (const t of trs) {
      if (!t.ticket.length) continue;
      cote *= t.ticket[0].cote;
      etapes.push({ tranche: t.nom, ajout: t.ticket[0], cote, selections: etapes.length + 1 });
    }
    return etapes;
  }

  // Ticket du jour (vue simple) : d'abord le premier de chaque tranche (= méthode A), puis le deuxième de chaque tranche.
  // Plus de matchs = multiplicateur plus grand mais ticket plus fragile ; l'utilisateur choisit la longueur.
  function ticketLong(trs) {
    const ordre = [...trs.map((t) => t.ticket[0]), ...trs.map((t) => t.ticket[1])].filter(Boolean);
    let cote = 1;
    return ordre.map((ajout, i) => { cote *= ajout.cote; return { ajout, cote, selections: i + 1 }; });
  }

  // Palier 2 (25/10/2026, Patrick) : les 10 meilleurs pronostics RESTANTS après le palier 1, avec la même rigueur (mêmes règles
  // d'admissibilité, même classement), sur toute la journée ; un seul pari par match, aucun match du palier 1.
  function palier2(cands, p1) {
    const pris = new Set(p1.map((c) => c.match_id)), out = [];
    for (const c of cands.filter((x) => x.admissible && x.debut >= REGLES.debut && x.debut < REGLES.fin).sort(compare)) {
      if (pris.has(c.match_id) || out.length >= REGLES.palier2Max) continue;
      out.push(c); pris.add(c.match_id);
    }
    return out;
  }

  const finEstimee = (sels) => Math.max(...sels.map((s) => s.debut)) + REGLES.dureeMatch;

  // Méthode B : à partir de chaque tranche, enchaîne les tickets dont les matchs commencent après la fin et le règlement du précédent.
  function chaines(trs) {
    const brutes = [];
    trs.forEach((t0, i) => {
      if (!t0.ticket.length) return;
      const etapes = [{ tranche: t0.nom, selections: t0.ticket.slice(), partiel: false, marge: null, conditionnel: false }];
      let fin = finEstimee(t0.ticket);
      for (let j = i + 1; j < trs.length; j++) {
        const dispo = trs[j].ticket.filter((s) => s.debut >= fin + REGLES.delaiReglement);
        if (!dispo.length) continue;
        const marge = Math.min(...dispo.map((s) => s.debut)) - fin;
        etapes.push({ tranche: trs[j].nom, selections: dispo, partiel: dispo.length < trs[j].ticket.length, marge, finPrecedente: fin, conditionnel: marge < REGLES.margeConfortable });
        fin = finEstimee(dispo);
      }
      if (etapes.length >= 2) brutes.push(etapes);
    });
    // Une chaîne contenue dans une plus longue (mêmes étapes à partir d'un point) n'apporte rien : retirée.
    const cle = (e) => e.map((x) => x.selections.map((s) => s.id).join("+")).join(">");
    const retenues = brutes.filter((c) => !brutes.some((d) => d !== c && d.length > c.length && cle(d).endsWith(cle(c))));
    return retenues
      .map((etapes) => ({ etapes, selections: etapes.reduce((n, e) => n + e.selections.length, 0), cote: etapes.reduce((p, e) => p * coteTotale(e.selections), 1) }))
      .sort((a, b) => (b.etapes.length - a.etapes.length) || (b.selections - a.selections) || (a.etapes[0].selections[0].debut - b.etapes[0].selections[0].debut))
      .map((c, k) => ({ nom: `B${k + 1}`, ...c }));
  }

  // Montants d'une chaîne : réinvestissement total et variante prudente (mise initiale protégée après le premier gain).
  function finances(chaine, mise) {
    const total = [], prudent = [];
    let m = mise;
    chaine.etapes.forEach((e, i) => {
      const c = coteTotale(e.selections), retour = m * c;
      total.push({ etape: i + 1, mise: m, cote: c, retour, siPerdSolde: 0, siPerdPerteTotale: mise, siPerdBeneficesPerdus: m - mise });
      m = retour;
    });
    let reinvesti = null;
    chaine.etapes.forEach((e, i) => {
      const c = coteTotale(e.selections);
      if (i === 0) {
        const retour = mise * c;
        prudent.push({ etape: 1, protege: 0, mise, cote: c, retour, siPerdSolde: 0, siPerdPerteTotale: mise, siPerdBeneficePerdu: 0 });
        reinvesti = retour - mise;
      } else {
        const retour = reinvesti * c;
        prudent.push({ etape: i + 1, protege: mise, mise: reinvesti, cote: c, retour, siPerdSolde: mise, siPerdPerteTotale: 0, siPerdBeneficePerdu: reinvesti });
        reinvesti = retour;
      }
    });
    return { total, prudent, finalTotal: m, finalPrudent: mise + (reinvesti || 0) };
  }

  function analyse(donnees, jour) {
    const cands = candidats((donnees && donnees.matchs) || [], jour), trs = tranches(cands), a = methodeA(trs);
    return { jour, regles: REGLES, tranches: trs, methodeA: a, palier1: a.map((e) => e.ajout), palier2: palier2(cands, a.map((e) => e.ajout)),
      ticketLong: ticketLong(trs), chaines: chaines(trs) };
  }

  // Jours disponibles (au moins un match analysé avec une heure), du plus proche au plus lointain, à partir de `depuis`.
  function jours(donnees, depuis) {
    return [...new Set(((donnees && donnees.matchs) || []).filter((m) => m.statut === "analyse" && minutes(m.heure) !== null && m.date >= depuis).map((m) => m.date))].sort();
  }

  const api = { REGLES, minutes, heure, confirmation, candidats, compare, tranches, coteTotale, methodeA, palier2, ticketLong, chaines, finances, analyse, jours, finEstimee };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else racine.AlphaTickets = api;
})(typeof window !== "undefined" ? window : globalThis);
