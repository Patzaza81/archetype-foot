/* Navigation visuelle par date — ne modifie aucune donnée ni aucun moteur. */
(() => {
  "use strict";
  const MONTHS = {jan:0, janvier:0, fev:1, fevr:1, fevrier:1, mar:2, mars:2, avr:3, avril:3, mai:4, juin:5, juil:6, juillet:6, aout:7, sep:8, sept:8, septembre:8, oct:9, octobre:9, nov:10, novembre:10, dec:11, decembre:11};
  const MONTH_LABELS = ["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
  let mode = "all";
  let selectedDate = "";
  let selectedLeague = "";
  let leagueOpen = false;
  let leagueSearch = "";
  const expanded = new Set();
  let observer = null;
  let refreshQueued = false;

  function localIso(date) {
    return date.getFullYear() + "-" + String(date.getMonth()+1).padStart(2,"0") + "-" + String(date.getDate()).padStart(2,"0");
  }
  function parseDate(text) {
    const s = String(text || "").toLocaleLowerCase("fr-FR").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\./g, " ");
    if (/\baujourd'hui\b/.test(s)) return localIso(new Date());
    if (/\bdemain\b/.test(s)) { const d = new Date(); d.setDate(d.getDate()+1); return localIso(d); }
    const iso = s.match(/\b(20\d{2})-(\d{1,2})-(\d{1,2})\b/);
    if (iso) return iso[1]+"-"+String(iso[2]).padStart(2,"0")+"-"+String(iso[3]).padStart(2,"0");
    const m = s.match(/\b(\d{1,2})\s+([a-z]{3,9})\b/);
    if (!m) return "";
    const key = m[2].replace(/[^a-z]/g,"");
    let month = MONTHS[key];
    if (month === undefined) month = MONTHS[key.slice(0,4)];
    if (month === undefined) month = MONTHS[key.slice(0,3)];
    if (month === undefined) return "";
    const now = new Date();
    let year = now.getFullYear();
    const candidate = new Date(year, month, Number(m[1]));
    const deltaDays = Math.round((candidate - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 86400000);
    if (deltaDays < -180) year++;
    return year+"-"+String(month+1).padStart(2,"0")+"-"+String(Number(m[1])).padStart(2,"0");
  }
  function readable(iso) {
    const [y,m,d] = iso.split("-").map(Number);
    return d+" "+MONTH_LABELS[m-1]+" "+y;
  }
  function getCards() {
    return Array.from(document.querySelectorAll(".ax-carte"));
  }
  function cardDate(card) {
    const dateEl = card.querySelector(".ax-horaire span");
    return parseDate(dateEl ? dateEl.textContent : card.textContent);
  }
  // Championnat de la carte : texte de .ax-competition sans le drapeau ajouté par af-drapeaux-cartes.js
  // et sans le score final que certaines pages (alpha) ajoutent après le libellé. Lecture seule.
  function cardLeague(card) {
    const el = card.querySelector(".ax-competition");
    if (!el) return "";
    const text = Array.from(el.childNodes)
      .filter(n => !(n.nodeType === 1 && n.classList.contains("af-drapeau")))
      .map(n => n.textContent).join("");
    return text.replace(/\s*·\s*Score final.*$/i, "").replace(/\s+/g, " ").trim();
  }
  function ensureBar() {
    const host = document.querySelector(".ax-conteneur");
    if (!host || document.getElementById("af-date-navigation")) return;
    const bar = document.createElement("section");
    bar.id = "af-date-navigation";
    bar.className = "af-date-navigation";
    bar.setAttribute("aria-label", "Navigation des pronostics par date");
    bar.innerHTML = '<div class="af-date-heading"><strong>Pronostics par date</strong><span id="af-date-count" aria-live="polite">Chargement des dates…</span></div>' +
      '<div class="af-date-controls" role="group" aria-label="Choisir une période">' +
      '<button type="button" data-mode="today">Aujourd’hui</button>' +
      '<button type="button" data-mode="tomorrow">Demain</button>' +
      '<button type="button" data-mode="all" class="is-active" aria-pressed="true">Toutes les dates</button>' +
      '<label class="af-date-select-label" for="af-date-select">Date précise</label><select id="af-date-select"><option value="">Choisir une date…</option></select></div>' +
      '<div class="af-league-controls"><span class="af-date-select-label af-league-label">Championnat</span>' +
      '<button type="button" id="af-league-trigger" class="af-league-trigger" aria-haspopup="true" aria-expanded="false"></button>' +
      '<div id="af-league-panel" class="af-league-panel" hidden>' +
      '<input id="af-league-search" class="af-league-search" type="search" placeholder="Rechercher un championnat ou un pays" autocomplete="off" aria-label="Rechercher un championnat">' +
      '<div id="af-league-list" class="af-league-list"></div></div></div>';
    const heading = host.querySelector(".ax-entete");
    if (heading) heading.insertAdjacentElement("afterend", bar);
    else host.insertAdjacentElement("afterbegin", bar);
    bar.querySelectorAll("button[data-mode]").forEach(button => button.addEventListener("click", () => {
      mode = button.dataset.mode;
      selectedDate = "";
      applyFilter();
    }));
    bar.querySelector("#af-league-trigger").addEventListener("click", () => {
      leagueOpen = !leagueOpen;
      applyFilter();
    });
    bar.querySelector("#af-league-search").addEventListener("input", event => {
      leagueSearch = event.target.value;
      applyFilter();
    });
    bar.querySelector("#af-league-list").addEventListener("click", event => {
      const choice = event.target.closest("[data-league]");
      if (choice) { selectedLeague = choice.dataset.league; leagueOpen = false; leagueSearch = ""; applyFilter(); return; }
      const country = event.target.closest("[data-country]");
      if (country) {
        const c = country.dataset.country;
        if (expanded.has(c)) expanded.delete(c); else expanded.add(c);
        applyFilter();
      }
    });
    document.addEventListener("click", event => {
      // composedPath : le chemin du clic est figé à l'envoi, même si le bouton cliqué a été réécrit entre-temps.
      const inside = event.composedPath().some(el => el.classList && el.classList.contains("af-league-controls"));
      if (leagueOpen && !inside) { leagueOpen = false; applyFilter(); }
    });
    bar.querySelector("#af-date-select").addEventListener("change", event => {
      selectedDate = event.target.value;
      mode = selectedDate ? "date" : "all";
      applyFilter();
    });
  }
  function updateDateOptions(cards) {
    const select = document.getElementById("af-date-select");
    if (!select) return;
    const prior = select.value;
    const dates = Array.from(new Set(cards.map(cardDate).filter(Boolean))).sort();
    const markup = '<option value="">Choisir une date…</option>' + dates.map(d => '<option value="'+d+'">'+readable(d)+'</option>').join("");
    if (select.innerHTML !== markup) select.innerHTML = markup;
    if (dates.includes(prior)) select.value = prior;
    else if (selectedDate && !dates.includes(selectedDate)) { selectedDate = ""; mode = "all"; }
  }
  const escHtml = t => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const norm = t => String(t || "").toLocaleLowerCase("fr-FR").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  // « Pays : Championnat » -> {pays, nom}. Sans séparateur, le libellé entier sert de nom et de pays.
  function splitLeague(label) {
    const k = label.indexOf(" : ");
    return k > 0 ? { pays: label.slice(0, k).trim(), nom: label.slice(k + 3).trim() } : { pays: label, nom: label };
  }
  function flagOf(label) {
    try { const d = typeof window.drapeauCompetition === "function" ? window.drapeauCompetition(label) : null; return d && d.symbole ? d.symbole : ""; }
    catch (e) { return ""; }
  }
  function flagHtml(symbol) {
    return '<span class="af-flag" aria-hidden="true">' + (symbol ? escHtml(symbol) : "⚽") + "</span>";
  }
  function updateLeagueUI(cards) {
    const trigger = document.getElementById("af-league-trigger");
    const panel = document.getElementById("af-league-panel");
    const list = document.getElementById("af-league-list");
    if (!trigger || !panel || !list) return;
    const counts = new Map();
    cards.forEach(card => { const l = cardLeague(card); if (l) counts.set(l, (counts.get(l) || 0) + 1); });
    if (selectedLeague && !counts.has(selectedLeague)) selectedLeague = "";
    const byCountry = new Map();
    counts.forEach((n, label) => {
      const { pays, nom } = splitLeague(label);
      if (!byCountry.has(pays)) byCountry.set(pays, { symbole: flagOf(label), total: 0, ligues: [] });
      const c = byCountry.get(pays);
      c.total += n; c.ligues.push({ label, nom, n });
    });
    const q = norm(leagueSearch.trim());
    const countries = Array.from(byCountry.keys()).sort((a, b) => a.localeCompare(b, "fr"));
    let rows = '<button type="button" class="af-league-row af-league-all' + (selectedLeague ? "" : " is-selected") + '" data-league="">' +
      '<span class="af-flag af-flag-all" aria-hidden="true">🌐</span><span class="af-league-name">Tous les championnats</span>' +
      '<span class="af-league-count">' + cards.length + "</span></button>";
    let shownCountries = 0;
    countries.forEach(pays => {
      const c = byCountry.get(pays);
      c.ligues.sort((a, b) => a.nom.localeCompare(b.nom, "fr"));
      const ligues = q ? c.ligues.filter(l => norm(l.nom).includes(q) || norm(pays).includes(q)) : c.ligues;
      if (!ligues.length) return;
      shownCountries++;
      const open = q ? true : expanded.has(pays);
      rows += '<div class="af-league-country' + (open ? " is-open" : "") + '">' +
        '<button type="button" class="af-league-row af-league-head" data-country="' + escHtml(pays) + '" aria-expanded="' + open + '">' +
        flagHtml(c.symbole) + '<span class="af-league-name">' + escHtml(pays) + '</span>' +
        '<span class="af-league-count">' + c.total + '</span><span class="af-league-chevron" aria-hidden="true"></span></button>';
      if (open) {
        rows += '<div class="af-league-sub">' + ligues.map(l =>
          '<button type="button" class="af-league-row af-league-item' + (l.label === selectedLeague ? " is-selected" : "") + '" data-league="' + escHtml(l.label) + '">' +
          '<span class="af-league-name">' + escHtml(l.nom) + '</span><span class="af-league-count">' + l.n + "</span></button>").join("") + "</div>";
      }
      rows += "</div>";
    });
    if (q && !shownCountries) rows += '<p class="af-league-empty">Aucun championnat ne correspond.</p>';
    if (list.innerHTML !== rows) list.innerHTML = rows;
    const sel = selectedLeague ? splitLeague(selectedLeague) : null;
    const head = sel
      ? flagHtml(flagOf(selectedLeague)) + '<span class="af-league-name">' + escHtml(sel.nom) + '<small>' + escHtml(sel.pays) + "</small></span>"
      : '<span class="af-flag af-flag-all" aria-hidden="true">🌐</span><span class="af-league-name">Tous les championnats</span>';
    const label = head + '<span class="af-league-chevron' + (leagueOpen ? " is-up" : "") + '" aria-hidden="true"></span>';
    if (trigger.innerHTML !== label) trigger.innerHTML = label;
    trigger.setAttribute("aria-expanded", String(leagueOpen));
    panel.hidden = !leagueOpen;
  }
  function applyFilter() {
    ensureBar();
    const cards = getCards();
    updateDateOptions(cards);
    updateLeagueUI(cards);
    const today = localIso(new Date());
    const tomorrowDate = new Date(); tomorrowDate.setDate(tomorrowDate.getDate()+1);
    const tomorrow = localIso(tomorrowDate);
    let shown = 0;
    cards.forEach(card => {
      const date = cardDate(card);
      let visible = mode === "all" || (mode === "today" && date === today) ||
        (mode === "tomorrow" && date === tomorrow) || (mode === "date" && date === selectedDate);
      if (mode === "all") visible = true;
      if (selectedLeague && cardLeague(card) !== selectedLeague) visible = false;
      card.hidden = !visible;
      if (visible) shown++;
    });
    const bar = document.getElementById("af-date-navigation");
    if (!bar) return;
    bar.querySelectorAll("button[data-mode]").forEach(button => {
      const active = button.dataset.mode === mode;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const select = bar.querySelector("#af-date-select");
    if (select) select.value = mode === "date" ? selectedDate : "";
    const count = bar.querySelector("#af-date-count");
    if (count) count.textContent = cards.length ? shown+" pronostic(s) affiché(s) sur "+cards.length+" carte(s) chargée(s)" : "Aucun pronostic chargé pour le moment";
  }
  function scheduleRefresh() {
    if (refreshQueued) return;
    refreshQueued = true;
    requestAnimationFrame(() => { refreshQueued = false; applyFilter(); });
  }
  function init() {
    ensureBar();
    applyFilter();
    if (observer) observer.disconnect();
    observer = new MutationObserver(scheduleRefresh);
    observer.observe(document.querySelector(".ax-conteneur") || document.body, {childList:true, subtree:true});
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, {once:true});
  else init();
})();