// Page du moteur MEGAPOWER v2 (le modèle n'utilise aucune cote ; la cote Betpawa ≥ 1,26 est seulement un filtre d'affichage) : lecture seule de data/megapower/pronostics.json (écrit par `python -m megapower.suivi`). Aucun calcul ici.
const MP_CLE_THEME = "archetype_theme_nuit";
function mpE(x) { return String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function mpPct(x) { const n = Number(x); return Number.isFinite(n) ? Math.round(n * 100) + " %" : "—"; }
function mpNb(x) { const n = Number(x); return Number.isFinite(n) ? n.toFixed(1).replace(".", ",") : "—"; }
function mpHoraire(ko) {          // coup d'envoi UTC -> heure du Cameroun (UTC+1)
  const d = new Date(ko);
  if (Number.isNaN(d.getTime())) return { heure: "", date: "" };
  const l = new Date(d.getTime() + 3600000);
  const p = (n) => String(n).padStart(2, "0");
  const jours = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"];
  return { heure: `${p(l.getUTCHours())}:${p(l.getUTCMinutes())}`, date: `${p(l.getUTCDate())}/${p(l.getUTCMonth() + 1)}`, jour: jours[l.getUTCDay()] };
}
function mpCote(x) { const n = Number(x); return x != null && Number.isFinite(n) && n > 1 ? "cote " + n.toFixed(2).replace(".", ",") : ""; }
function mpSur10(x) { const n = Number(x); return Number.isFinite(n) ? Math.round(n * 10) : null; }
function mpLigne(p) {
  const badge = p.resultat ? `<span class="om-badge om-${mpE(p.resultat)}">${p.resultat === "WIN" ? "GAGNÉ" : "PERDU"}</span>` : "";
  const s = mpSur10(p.fiabilite);
  return `<div class="om-ligne mp-pari"><span>${mpE(p.libelle)}</span><span><b class="om-cote">${mpCote(p.cote)}</b> · <span class="mp-fiab">${s == null ? "—" : s + " sur 10"}</span> ${badge}</span></div>`;
}
function mpDetail(f) {
  const l = (f.paris || []).map((p) => `<tr><td style="text-align:left">${mpE(p.libelle)}</td><td>${mpCote(p.cote).replace("cote ", "")}</td><td>${mpPct(p.fiabilite)}</td><td>${mpPct(p.modele)}</td><td>${mpPct(p.catastrophe)}</td></tr>`).join("");
  return `<details class="mp-det"><summary>Les chiffres</summary><div class="mp-table-zone"><table class="om-table"><tr><th>Pronostic</th><th>Cote</th><th>Fiabilité mesurée</th><th>Cas normal</th><th>Pire cas</th></tr>${l}</table></div>` +
    `<div class="om-info">Fiabilité mesurée = part des pronostics de ce type qui se sont réalisés sur des matchs comparables jamais vus par le moteur.</div></details>`;
}
function mpCarte(f) {
  const h = mpHoraire(f.coup_d_envoi_utc), ba = f.buts_attendus || [];
  const s = document.createElement("section");
  s.className = "ax-carte";
  s.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match"><span class="ax-equipe ax-dom">${mpE(f.domicile)}</span>` +
    `<div class="ax-horaire"><strong>${mpE(h.heure)}</strong><span>${mpE(h.jour)} ${mpE(h.date)}</span></div><span class="ax-equipe ax-ext">${mpE(f.exterieur)}</span></div>` +
    `<div class="ax-match-bas"><p class="ax-competition">${mpE(String(f.competition || "").replace(/\s+/g, " ").trim())}</p><div class="ax-actions-tete"></div></div></div>` +
    `<div class="om-corps">` + (f.score ? `<div class="om-info">Score final <strong>${mpE(f.score.join("-"))}</strong></div>` : "") +
    (ba.length === 2 ? `<div class="om-info">Buts attendus : ${mpE(f.domicile)} ${mpNb(ba[0])} · ${mpE(f.exterieur)} ${mpNb(ba[1])} (sur ${f.n_domicile} matchs à domicile et ${f.n_exterieur} à l'extérieur)</div>` : "") +
    (f.paris || []).map(mpLigne).join("") + mpDetail(f) + `</div>`;
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
  if (n) return `<div class="mp-verdict mp-ok"><b class="mp-gros">${n} match${n > 1 ? "s" : ""} avec des pronostics fiables</b><p>Sur ${a} match${a > 1 ? "s" : ""} analysé${a > 1 ? "s" : ""}. Chaque pronostic est classé du plus fiable au moins fiable.</p></div>`;
  return `<div class="mp-verdict"><b class="mp-gros">Aucun pronostic assez fiable pour l'instant</b><p>${a} match${a > 1 ? "s" : ""} à venir analysé${a > 1 ? "s" : ""}.</p></div>`;
}
function mpTable(titre, note, entetes, lignes) {
  return `<div class="om-bloc"><div class="om-bloc-titre">${titre}</div>${note ? `<div class="om-info">${note}</div>` : ""}<div class="mp-table-zone"><table class="om-table"><tr>${entetes.map((e) => `<th>${e}</th>`).join("")}</tr>${lignes.join("")}</table></div></div>`;
}
function mpChiffres(d) {
  const b = d.bilan || {}, v = d.marche_avant || {}, blocs = [];
  if (b.pronostics > 0) {
    blocs.push(mpTable("Résultats réels de Megapower", `Pronostics enregistrés avant le coup d'envoi, matchs terminés (${mpE(b.du)} → ${mpE(b.au)}).`,
      ["Matchs", "Pronostics", "Réussite", "Fiabilité annoncée"], [`<tr><td>${b.matchs}</td><td>${b.pronostics}</td><td>${mpPct(b.reussite)}</td><td>${mpPct(b.fiabilite_annoncee)}</td></tr>`]));
  } else {
    blocs.push(`<div class="om-bloc"><div class="om-bloc-titre">Résultats réels de Megapower</div><div class="om-info">Aucun match terminé avec des pronostics enregistrés à l'avance pour l'instant.</div></div>`);
  }
  if (v.periode) {
    const h = v.par_moitie || [];
    blocs.push(mpTable(`Test sur des matchs jamais vus (${mpE(v.periode[0])} → ${mpE(v.periode[1])})`,
      "Chaque jour, le moteur apprend sur les jours d'avant puis juge les matchs du jour. Ce n'est pas un résultat réel : ces pronostics n'étaient pas enregistrés à l'avance.",
      ["Matchs", "Pronostics", "Réussite", "1re moitié", "2e moitié"],
      [`<tr><td>${v.matchs}</td><td>${v.pronostics}</td><td>${mpPct(v.reussite)}</td><td>${h[0] ? mpPct(h[0].reussite) : "—"}</td><td>${h[1] ? mpPct(h[1].reussite) : "—"}</td></tr>`]));
    const fam = Object.entries(v.par_famille || {}).sort((x, y) => y[1].reussite - x[1].reussite);
    if (fam.length) blocs.push(mpTable("Réussite par type de pronostic", "Un type en dessous du niveau demandé est écarté.", ["Type", "Pronostics", "Réussite", "Gardé"],
      fam.map(([n, r]) => `<tr><td style="text-align:left">${mpE(n)}</td><td>${r.pronostics}</td><td>${mpPct(r.reussite)}</td><td>${r.autorisee ? "oui" : "non"}</td></tr>`)));
  }
  const ab = (d.modele || {}).ablation_seconde_moitie;
  if (ab) {
    const noms = { complet: "Moteur complet", sans_xg: "Sans le xG (buts seuls)", sans_tendance: "Sans tendance", sans_classement: "Sans le classement", sans_correction_adversaires: "Sans correction des adversaires" };
    blocs.push(mpTable("Ce que chaque ingrédient apporte", "Erreur du modèle de buts sur la 2e moitié des matchs (plus bas = meilleur).", ["Variante", "Erreur"],
      Object.entries(ab).map(([k, x]) => `<tr><td style="text-align:left">${mpE(noms[k] || k)}</td><td>${Number(x).toFixed(4).replace(".", ",")}</td></tr>`)));
  }
  return blocs.join("<br>");
}
function mpAffiche(d) {
  document.getElementById("mp-verdict").innerHTML = mpVerdict(d);
  mpListe("mp-avenir", d.a_venir, "Aucun pronostic fiable à venir.");
  mpListe("mp-encours", d.en_cours, "Aucun match en cours.");
  mpListe("mp-regles", d.reglees, "Aucun pronostic réglé pour l'instant.");
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
if (typeof module !== "undefined") module.exports = { mpVerdict, mpChiffres, mpLigne, mpSur10, mpHoraire, mpCote };
