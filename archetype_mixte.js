// Page d'essai « pourcentage mixte » (moteur_omega_v3/mixte.py) : affiche data/gamma/mixte.json. Lecture seule, aucun calcul métier.
// Le pourcentage affiché est une réussite OBSERVÉE sur l'archive à ce niveau (calibrée) ; la cote n'est qu'une information d'accès.
"use strict";
const MX_CLE_THEME = "archetype_theme_nuit";
function mxE(x) { return String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function mxPct(x) { const n = Number(x); return Number.isFinite(n) ? Math.round(n * 100) + " %" : "—"; }
function mxCote(x) { const n = Number(x); return x != null && Number.isFinite(n) && n > 1 ? n.toFixed(2).replace(".", ",") : "—"; }
function mxModele(m) {
  return m === "MIXTE" ? "Modèle mixte (5 derniers matchs au même lieu + forces du championnat)"
    : m === "FORCE" ? "Forces du championnat seules (moins de 5 matchs au même lieu)" : "Aucun modèle";
}
function mxLigne(x) {
  const hab = x.habituel != null ? `<span class="om-sous">habituellement ${mxPct(x.habituel)} pour ce marché</span>` : "";
  return `<div class="om-ligne"><span>${mxE(x.libelle)}${hab}</span><span class="om-cote">${mxPct(x.p)} <small>· cote ${mxCote(x.cote)}</small></span></div>`;
}
function mxHeure(ko) {          // coup d'envoi UTC -> heure du Cameroun (UTC+1), même présentation que les autres pages
  const d = ko ? new Date(ko) : null; if (!d || Number.isNaN(d.getTime())) return { heure: "—", date: "" };
  const c = new Date(d.getTime() + 3600000);
  const t = new Date(`${c.toISOString().slice(0, 10)}T12:00:00`).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" }).replace(/\./g, "").trim();
  return { heure: c.toISOString().slice(11, 16).replace(":", "h"), date: t.charAt(0).toUpperCase() + t.slice(1) };
}
function mxCarte(f) {
  const h = mxHeure(f.coup_d_envoi_utc), L = f.marches || [];
  const haut = L.slice(0, 3).map(mxLigne).join("") || `<p class="om-vide">Aucun marché coté ne ressort plus que d'habitude pour ce match.</p>`;
  const reste = L.slice(3).map(mxLigne).join("");
  const section = document.createElement("section");
  section.className = "ax-carte ax-replie";
  section.setAttribute("aria-expanded", "false");
  section.innerHTML =
    `<div class="ax-match"><div class="ax-ligne-match"><span class="ax-equipe ax-dom">${mxE(f.domicile)}</span>` +
    `<div class="ax-horaire"><strong>${mxE(h.heure)}</strong><span>${mxE(h.date)}</span></div><span class="ax-equipe ax-ext">${mxE(f.exterieur)}</span></div>` +
    `<div class="ax-match-bas"><p class="ax-competition">${mxE(String(f.competition || "").replace(/\s+/g, " ").trim())}</p><div class="ax-actions-tete"></div></div></div>` +
    `<div class="om-corps"><div class="om-info"><b>Marchés les plus probables</b> (pourcentage calibré)</div>${haut}</div>` +
    `<details class="ax-details" open><summary class="ax-summary-cache" tabindex="-1">Détails</summary><div class="ax-details-corps"><div class="om-corps">${reste}` +
    `<div class="om-info">${mxE(mxModele(f.modele))}. Le pourcentage est la réussite observée sur l'archive pour les marchés annoncés à ce niveau.</div></div></div></details>`;
  section.addEventListener("click", (e) => {
    if (e.target.closest("button, a, summary")) return;
    const sel = window.getSelection && window.getSelection();
    if (sel && String(sel).length) return;
    const replie = !section.classList.contains("ax-replie");
    section.classList.toggle("ax-replie", replie);
    section.setAttribute("aria-expanded", String(!replie));
  });
  return section;
}
function mxBilan(b) {
  if (!b || !b.matchs) return `<p class="om-info" style="margin:8px 14px">Aucun match terminé suivi pour l'instant : le tableau « annoncé contre réel » apparaîtra avec les premiers résultats.</p>`;
  const l = (b.tranches || []).map((t) => `<tr><td>${mxE(t.tranche)}</td><td>${t.n}</td><td>${mxPct(t.annonce)}</td><td>${mxPct(t.reel)}</td></tr>`).join("");
  return `<p class="om-info" style="margin:8px 14px">${b.matchs} match${b.matchs > 1 ? "s" : ""} terminé${b.matchs > 1 ? "s" : ""} suivi${b.matchs > 1 ? "s" : ""} (pronostic gelé avant le coup d'envoi), ${b.marches_evalues} marchés évalués : annoncé ${mxPct(b.annonce_moyenne)}, réel ${mxPct(b.reel)}.</p>` +
    `<table class="om-table"><tr><th>Annoncé</th><th>Marchés</th><th>Moyenne annoncée</th><th>Réussite réelle</th></tr>${l}</table>`;
}
function mxAffiche(d) {
  document.getElementById("om-bilan").innerHTML = mxBilan(d.bilan);
  const el = document.getElementById("om-avenir"); el.innerHTML = "";
  if (d.a_venir && d.a_venir.length) d.a_venir.forEach((f) => el.appendChild(mxCarte(f)));
  else el.innerHTML = `<p class="om-vide">Aucun match à venir pour l'instant.</p>`;
  const s = (d.sans_pronostic || []).length;
  document.getElementById("om-sans").textContent = s ? `${s} match${s > 1 ? "s" : ""} non analysé${s > 1 ? "s" : ""} : historique insuffisant, aucune donnée inventée.` : "";
  const g = d.genere_le ? new Date(d.genere_le) : null;
  document.getElementById("maj").textContent = g && !Number.isNaN(g.getTime()) ? `Dernière analyse : ${g.toLocaleDateString("fr-FR")} à ${g.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}` : "";
}
function mxTheme() {
  const bouton = document.getElementById("ax-bouton-theme"); if (!bouton) return;
  const applique = (nuit) => { document.body.classList.toggle("theme-nuit", nuit); bouton.textContent = nuit ? "☀" : "☾"; };
  let nuit = false;
  try { nuit = localStorage.getItem(MX_CLE_THEME) === "1"; } catch (e) { /* ignoré */ }
  applique(nuit);
  bouton.addEventListener("click", () => {
    const suivant = !document.body.classList.contains("theme-nuit");
    try { localStorage.setItem(MX_CLE_THEME, suivant ? "1" : "0"); } catch (e) { /* ignoré */ }
    applique(suivant);
  });
}
mxTheme();
if (document.getElementById("om-avenir")) {
  fetch(`data/gamma/mixte.json?_=${Date.now()}`)
    .then((r) => { if (!r.ok) throw new Error(`données introuvables (${r.status}) : le calcul n'a pas encore tourné`); return r.json(); })
    .then(mxAffiche)
    .catch((e) => { document.getElementById("maj").textContent = "Erreur de chargement : " + e.message; console.error(e); });
}
if (typeof module !== "undefined") module.exports = { mxLigne, mxCarte, mxBilan, mxModele, mxPct, mxCote };
