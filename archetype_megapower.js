// Page du moteur MEGAPOWER : lecture seule de data/megapower/pronostics.json (écrit par `python -m megapower.suivi`). Aucun calcul ici.
const MP_CLE_THEME = "archetype_theme_nuit";
function mpE(x) { return String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function mpCote(x) { const n = Number(x); return Number.isFinite(n) && n > 1 ? n.toFixed(2).replace(".", ",") : "—"; }
function mpPct(x) { const n = Number(x); return Number.isFinite(n) ? Math.round(n * 100) + " %" : "—"; }
function mpSigne(x) {
  const n = Number(x);
  if (!Number.isFinite(n)) return "—";
  return `<span class="${n >= 0 ? "mp-pos" : "mp-neg"}">${n >= 0 ? "+" : "−"}${Math.abs(n * 100).toFixed(1).replace(".", ",")}</span>`;
}
function mpHoraire(ko) {          // coup d'envoi UTC -> heure du Cameroun (UTC+1)
  const d = new Date(ko);
  if (Number.isNaN(d.getTime())) return { heure: "", date: "" };
  const l = new Date(d.getTime() + 3600000);
  const p = (n) => String(n).padStart(2, "0");
  return { heure: `${p(l.getUTCHours())}:${p(l.getUTCMinutes())}`, date: `${p(l.getUTCDate())}/${p(l.getUTCMonth() + 1)}` };
}
function mpPourquoi(p) {
  const pour = (p.lectures || []).filter((x) => x.pour).map((x) => x.moteur), contre = (p.lectures || []).filter((x) => !x.pour).map((x) => x.moteur);
  const l = [];
  l.push(`<div class="om-info">Sur les matchs déjà joués, un pari de ce type à cette cote passe <b>${mpPct(p.reussite_apprise)}</b> du temps. Il faut <b>${mpPct(p.reussite_pour_rembourser)}</b> pour ne pas perdre d'argent à la cote ${mpCote(p.cote)}.</div>`);
  l.push(`<div class="om-info">Gain attendu pour 100 misés : ${mpSigne(p.gain_attendu)} (au pire, selon les données : ${mpSigne(p.gain_attendu_bas)}).</div>`);
  if (pour.length || contre.length) l.push(`<div class="om-info">Moteurs qui voient ce pari plus probable que la cote : <b>${pour.length ? pour.map(mpE).join(", ") : "aucun"}</b>${contre.length ? ` · moins probable : ${contre.map(mpE).join(", ")}` : ""}.</div>`);
  return l.join("");
}
function mpCarte(f) {
  const p = f.pari || {}, h = mpHoraire(f.coup_d_envoi_utc), prouve = p.statut === "prouvé";
  const badge = f.resultat ? `<span class="om-badge om-${mpE(f.resultat)}">${f.resultat === "WIN" ? "GAGNÉ" : "PERDU"}</span>` : "";
  const s = document.createElement("section");
  s.className = "ax-carte";
  s.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match"><span class="ax-equipe ax-dom">${mpE(f.domicile)}</span>` +
    `<div class="ax-horaire"><strong>${mpE(h.heure)}</strong><span>${mpE(h.date)}</span></div><span class="ax-equipe ax-ext">${mpE(f.exterieur)}</span></div>` +
    `<div class="ax-match-bas"><p class="ax-competition">${mpE(String(f.competition || "").replace(/\s+/g, " ").trim())}</p><div class="ax-actions-tete"></div></div></div>` +
    `<div class="om-corps">` + (f.score ? `<div class="om-info">Score final <strong>${mpE(f.score.join("-"))}</strong></div>` : "") +
    `<div class="om-ligne om-principal"><span>${mpE(p.libelle)}</span><span><span class="om-cote">Cote ${mpCote(p.cote)}</span> ${badge}</span></div>` +
    `<span class="mp-tag ${prouve ? "mp-tag-ok" : "mp-tag-non"}">${prouve ? "Pari prouvé : le gain reste positif même dans le pire cas mesuré" : "Sous observation : gain non prouvé, à ne pas jouer"}</span>` +
    mpPourquoi(p) + `</div>`;
  return s;
}
function mpListe(id, liste, vide) {
  const el = document.getElementById(id); if (!el) return;
  el.innerHTML = "";
  if (liste && liste.length) liste.forEach((f) => el.appendChild(mpCarte(f)));
  else el.innerHTML = `<p class="om-vide">${mpE(vide)}</p>`;
}
function mpVerdict(d) {
  const n = (d.a_venir || []).length, a = Number(d.matchs_a_venir_analyses) || 0;
  if (n) return `<div class="mp-verdict mp-ok"><b class="mp-gros">${n} pari${n > 1 ? "s" : ""} prouvé${n > 1 ? "s" : ""} à venir</b><p>Sur ${a} match${a > 1 ? "s" : ""} analysé${a > 1 ? "s" : ""}.</p></div>`;
  return `<div class="mp-verdict"><b class="mp-gros">Aujourd'hui : ne rien jouer</b>` +
    `<p>${a} match${a > 1 ? "s" : ""} à venir analysé${a > 1 ? "s" : ""}. Aucun pari ne rapporte de façon prouvée : la cote du bookmaker est trop basse par rapport à la réussite réelle.</p></div>`;
}
function mpLigneBilan(nom, s) {
  return s && s.paris > 0 ? `<tr><td>${nom}</td><td>${s.paris}</td><td>${mpPct(s.reussite)}</td><td>${mpCote(s.cote_moyenne)}</td><td>${mpSigne(s.rendement)}</td></tr>`
    : `<tr><td>${nom}</td><td>0</td><td>—</td><td>—</td><td>—</td></tr>`;
}
function mpChiffres(d) {
  const b = d.bilan || {}, v = d.marche_avant || {}, m = d.modele || {}, blocs = [];
  blocs.push(`<div class="om-bloc"><div class="om-bloc-titre">Résultats réels de Megapower (paris enregistrés avant le coup d'envoi, matchs terminés)</div><div class="mp-table-zone"><table class="om-table">` +
    `<tr><th>Paris</th><th>Nombre</th><th>Réussite</th><th>Cote moy.</th><th>Gain ou perte pour 100 misés</th></tr>${mpLigneBilan("Prouvés", b["prouvé"])}${mpLigneBilan("Sous observation", b["sous observation"])}</table></div></div>`);
  if (v.periode_testee) {
    blocs.push(`<div class="om-bloc"><div class="om-bloc-titre">Test sur des matchs jamais vus (${mpE(v.periode_testee[0])} → ${mpE(v.periode_testee[1])})</div>` +
      `<div class="om-info">Chaque jour, le moteur apprend sur les jours d'avant puis juge les matchs du jour. Ce n'est pas un résultat réel : ces paris n'étaient pas enregistrés à l'avance.</div>` +
      `<div class="mp-table-zone"><table class="om-table"><tr><th>Paris</th><th>Nombre</th><th>Réussite</th><th>Cote moy.</th><th>Gain ou perte pour 100 misés</th></tr>` +
      `${mpLigneBilan("Prouvés", v.prouves)}${mpLigneBilan("Sous observation", v.sous_observation)}</table></div></div>`);
  }
  const fam = Object.entries(m.familles || {}).sort((x, y) => y[1].rendement_de_tout_jouer - x[1].rendement_de_tout_jouer);
  if (fam.length) {
    blocs.push(`<div class="om-bloc"><div class="om-bloc-titre">Ce que coûte chaque type de pari (${m.matchs} matchs joués, cotes de ${mpCote(m.cote_min)} et plus)</div>` +
      `<div class="om-info">Si on avait joué tous les paris de ce type : gain ou perte pour 100 misés. Plus la perte est forte, plus le bookmaker se sert sur ce type de pari.</div>` +
      `<div class="mp-table-zone"><table class="om-table"><tr><th>Type de pari</th><th>Paris</th><th>Réussite</th><th>Gain ou perte pour 100 misés</th><th>Les moteurs aident ?</th></tr>` +
      fam.map(([nom, r]) => `<tr><td style="text-align:left">${mpE(nom)}</td><td>${r.paris}</td><td>${mpPct(r.reussite)}</td><td>${mpSigne(r.rendement_de_tout_jouer)}</td><td>${r.accord_garde ? (r.poids_accord > 0 ? "un peu" : "non, à contresens") : "non"}</td></tr>`).join("") +
      `</table></div></div>`);
  }
  const tri = (d.tri_moteurs || []).filter((x) => x.paris > 0);
  if (tri.length) {
    blocs.push(`<div class="om-bloc"><div class="om-bloc-titre">Résultats réels des autres moteurs (paris enregistrés avant le match)</div><div class="mp-table-zone"><table class="om-table">` +
      `<tr><th>Moteur</th><th>Paris</th><th>Réussite</th><th>Cote moy.</th><th>Gain ou perte pour 100 misés</th></tr>` +
      tri.map((x) => `<tr><td style="text-align:left">${mpE(x.moteur)}</td><td>${x.paris}</td><td>${mpPct(x.reussite)}</td><td>${mpCote(x.cote_moyenne)}</td><td>${mpSigne(x.rendement)}</td></tr>`).join("") + `</table></div></div>`);
  }
  return blocs.join("<br>");
}
function mpAffiche(d) {
  document.getElementById("mp-verdict").innerHTML = mpVerdict(d);
  mpListe("mp-avenir", d.a_venir, "Aucun pari prouvé à venir.");
  mpListe("mp-observation", d.sous_observation, "Aucun pari sous observation.");
  mpListe("mp-encours", d.en_cours, "Aucun match en cours.");
  mpListe("mp-regles", d.reglees, "Aucun pari réglé pour l'instant.");
  document.getElementById("mp-chiffres").innerHTML = mpChiffres(d);
  const g = d.genere_le ? new Date(d.genere_le) : null;
  document.getElementById("maj").textContent = g && !Number.isNaN(g.getTime())
    ? `Dernière analyse du moteur Megapower : ${g.toLocaleDateString("fr-FR")} à ${g.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}` : "";
}
function mpTheme() {
  const bouton = document.getElementById("ax-bouton-theme"); if (!bouton) return;
  const applique = (nuit) => {
    document.body.classList.toggle("theme-nuit", nuit);
    bouton.textContent = nuit ? "☀" : "☾";
    bouton.setAttribute("aria-label", nuit ? "Activer le mode clair" : "Activer le mode nuit");
  };
  let nuit = false;
  try { nuit = localStorage.getItem(MP_CLE_THEME) === "1"; } catch (e) { /* stockage indisponible */ }
  applique(nuit);
  bouton.addEventListener("click", () => {
    const suivant = !document.body.classList.contains("theme-nuit");
    try { localStorage.setItem(MP_CLE_THEME, suivant ? "1" : "0"); } catch (e) { /* ignoré */ }
    applique(suivant);
  });
}
if (typeof document !== "undefined") {
  mpTheme();
  if (document.getElementById("mp-avenir")) {
    fetch(`data/megapower/pronostics.json?_=${Date.now()}`)
      .then((r) => { if (!r.ok) throw new Error(`données Megapower introuvables (${r.status}) : le moteur n'a pas encore tourné`); return r.json(); })
      .then(mpAffiche)
      .catch((e) => { document.getElementById("maj").textContent = "Erreur de chargement : " + e.message; console.error(e); });
  }
}
if (typeof module !== "undefined") module.exports = { mpVerdict, mpChiffres, mpPourquoi, mpSigne };
