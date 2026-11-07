// Derniers matchs à trois onglets (À domicile / À l'extérieur / H2H), commun à tous les moteurs (07/11/2026, Patrick). Lecture seule : AUCUN calcul de probabilité.
// Données : data/derniers_onglets.json (derniers_onglets.py), clé = match_id. Match sans entrée => bloc() renvoie "" et la page garde son affichage actuel.
"use strict";
(function () {
  const URL_DONNEES = "data/derniers_onglets.json";
  let DONNEES = null;
  const e = (x) => String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fr1 = (x) => (Number.isFinite(x) ? x.toFixed(1).replace(".", ",") : "—");
  const jourCourt = (iso) => { const d = new Date(`${iso}T12:00:00`); return Number.isNaN(d.getTime()) ? e(iso || "") : e(d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" }).replace(/\./g, "")); };
  const pret = fetch(`${URL_DONNEES}?_=${Date.now()}`, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)).then((d) => { DONNEES = d && d.matchs ? d.matchs : null; }).catch(() => { DONNEES = null; });
  const ONGLETS = [["dom", "À domicile"], ["ext", "À l'extérieur"], ["h2h", "H2H"]];
  const equipe = (liste, dom) => (liste || []).map((x) => ({ date: x[0], adv: x[1], marques: x[2], encaisses: x[3], dom }));
  function lignes(l) {
    return l.map((x) => {
      const a = Number(x.marques), b = Number(x.encaisses), lettre = a > b ? "V" : a < b ? "D" : "N", cls = a > b ? "afd-v" : a < b ? "afd-d" : "afd-n";
      const score = x.dom ? `<b>${a}</b> – ${b}` : `${b} – <b>${a}</b>`;
      return `<li class="afd-dm"><span class="afd-dm-date">${jourCourt(x.date)}</span><span class="afd-dm-adv">${e(x.adv || "Adversaire inconnu")}</span><span class="afd-dm-score">${score}</span><span class="afd-dm-res ${cls}">${lettre}</span></li>`;
    }).join("");
  }
  function panneau(l, vide) {
    if (!l.length) return `<p class="afd-info">${vide}</p>`;
    const moy = (k) => l.reduce((s, x) => s + Number(x[k] || 0), 0) / l.length;
    return `<div class="afd-dm-puces"><span>Marque <b>${fr1(moy("marques"))}</b></span><span>Encaisse <b>${fr1(moy("encaisses"))}</b></span><span>${l.length} match${l.length > 1 ? "s" : ""}</span></div><ul class="afd-dm-liste">${lignes(l)}</ul>`;
  }
  function carteEquipe(nom, defaut, ens) {
    return `<div class="afd-dm-eq"><div class="afd-dm-tete"><span class="afd-dm-nom">${e(nom)}</span></div>` +
      `<div class="afd-onglets" role="tablist">${ONGLETS.map(([k, t]) => `<button type="button" class="afd-onglet${k === defaut ? " afd-onglet-actif" : ""}" role="tab" aria-selected="${k === defaut}" data-onglet="${k}">${t}</button>`).join("")}</div>` +
      ONGLETS.map(([k]) => `<div class="afd-dm-panneau" data-panneau="${k}"${k === defaut ? "" : " hidden"}>${panneau(ens[k], k === "h2h" ? "Aucune confrontation trouvée dans les données." : "Matchs indisponibles.")}</div>`).join("") + `</div>`;
  }
  // f : objet match d'un moteur (match_id, domicile, exterieur). Renvoie "" si aucune donnée pour ce match.
  function bloc(f) {
    const d = DONNEES && f && f.match_id ? DONNEES[f.match_id] : null; if (!d) return "";
    const h = d.h2h || [];
    const ensDom = { dom: equipe(d.dom, true), ext: equipe(d.dom_ext, false), h2h: h.map((x) => ({ date: x[0], adv: f.exterieur, marques: x[2], encaisses: x[3], dom: x[1] === 1 })) };
    const ensExt = { dom: equipe(d.ext_dom, true), ext: equipe(d.ext, false), h2h: h.map((x) => ({ date: x[0], adv: f.domicile, marques: x[3], encaisses: x[2], dom: x[1] !== 1 })) };
    return `<div class="afd-bloc"><div class="afd-bloc-titre">Derniers matchs</div><div class="afd-dm-grille">${carteEquipe(f.domicile, "dom", ensDom)}${carteEquipe(f.exterieur, "ext", ensExt)}</div></div>`;
  }
  // Retarde la suite du traitement d'une page jusqu'à ce que les données soient chargées (réponse inchangée, jamais d'échec bloquant).
  const attend = (p) => p.then((r) => pret.then(() => r));
  document.addEventListener("click", (ev) => {
    const bo = ev.target.closest && ev.target.closest(".afd-onglet"); if (!bo) return;
    const eq = bo.closest(".afd-dm-eq"); if (!eq) return;
    eq.querySelectorAll(".afd-onglet").forEach((x) => { x.classList.toggle("afd-onglet-actif", x === bo); x.setAttribute("aria-selected", String(x === bo)); });
    eq.querySelectorAll(".afd-dm-panneau").forEach((x) => { x.hidden = x.dataset.panneau !== bo.dataset.onglet; });
    ev.stopPropagation();   // un toucher sur un onglet ne replie pas la carte
  }, true);
  window.AFDerniers = { bloc, attend, pret };
  window.afAttend = attend;
})();
