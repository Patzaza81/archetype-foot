/* Navigation visuelle par date — ne modifie aucune donnée ni aucun moteur. */
(() => {
  "use strict";
  const MONTHS = {jan:0, janvier:0, fev:1, fevr:1, fevrier:1, mar:2, mars:2, avr:3, avril:3, mai:4, juin:5, juil:6, juillet:6, aout:7, sep:8, sept:8, septembre:8, oct:9, octobre:9, nov:10, novembre:10, dec:11, decembre:11};
  const MONTH_LABELS = ["janv.","févr.","mars","avr.","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
  let mode = "all";
  let selectedDate = "";
  let selectedChampionship = "";
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
    const numeric = s.match(/\b(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](20\d{2}|\d{2}))?\b/);
    if (numeric) {
      const day = Number(numeric[1]), month = Number(numeric[2]) - 1;
      if (month < 0 || month > 11 || day < 1 || day > 31) return "";
      const now = new Date();
      let year = numeric[3] ? Number(numeric[3]) : now.getFullYear();
      if (year < 100) year += 2000;
      const candidate = new Date(year, month, day);
      if (candidate.getFullYear() !== year || candidate.getMonth() !== month || candidate.getDate() !== day) return "";
      if (!numeric[3]) {
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const deltaDays = Math.round((candidate - today) / 86400000);
        if (deltaDays < -180) year++;
      }
      return year+"-"+String(month+1).padStart(2,"0")+"-"+String(day).padStart(2,"0");
    }
    const m = s.match(/\b(\d{1,2})\s+([a-z]{3,9})\b/);
    if (!m) return "";
    const key = m[2].replace(/[^a-z]/g,"");
    let month = MONTHS[key];
    if (month === undefined) month = MONTHS[key.slice(0,4)];
    if (month === undefined) month = MONTHS[key.slice(0,3)];
    if (month === undefined) return "";
    const now = new Date();
    let year = now.getFullYear();
    const day = Number(m[1]);
    const candidate = new Date(year, month, day);
    if (candidate.getMonth() !== month || candidate.getDate() !== day) return "";
    const deltaDays = Math.round((candidate - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 86400000);
    if (deltaDays < -180) year++;
    return year+"-"+String(month+1).padStart(2,"0")+"-"+String(day).padStart(2,"0");
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
  function cardChampionship(card) {
    const competition = card.querySelector(".ax-competition");
    return String(competition ? competition.textContent : "").replace(/\s+/g, " ").trim();
  }
  function ensureBar() {
    const host = document.querySelector(".ax-conteneur");
    if (!host || document.getElementById("af-date-navigation")) return;
    const bar = document.createElement("section");
    bar.id = "af-date-navigation";
    bar.className = "af-date-navigation";
    bar.setAttribute("aria-label", "Filtrer les pronostics par date et championnat");
    bar.innerHTML = '<div class="af-date-heading"><strong>Pronostics par date et championnat</strong><span id="af-date-count" aria-live="polite">Chargement des filtres…</span></div>' +
      '<div class="af-date-controls" role="group" aria-label="Choisir une période">' +
      '<button type="button" data-mode="today">Aujourd’hui</button>' +
      '<button type="button" data-mode="tomorrow">Demain</button>' +
      '<button type="button" data-mode="all" class="is-active" aria-pressed="true">Toutes les dates</button>' +
      '<label class="af-date-select-label" for="af-date-select">Date précise</label><select id="af-date-select"><option value="">Choisir une date…</option></select>' +
      '<label class="af-championship-select-label" for="af-championship-select">Championnat</label><select id="af-championship-select"><option value="">Tous les championnats</option></select></div>';
    const heading = host.querySelector(".ax-entete");
    if (heading) heading.insertAdjacentElement("afterend", bar);
    else host.insertAdjacentElement("afterbegin", bar);
    bar.querySelectorAll("button[data-mode]").forEach(button => button.addEventListener("click", () => {
      mode = button.dataset.mode;
      selectedDate = "";
      applyFilter();
    }));
    bar.querySelector("#af-date-select").addEventListener("change", event => {
      selectedDate = event.target.value;
      mode = selectedDate ? "date" : "all";
      applyFilter();
    });
    bar.querySelector("#af-championship-select").addEventListener("change", event => {
      selectedChampionship = event.target.value;
      applyFilter();
    });
  }
  function updateChampionshipOptions(cards) {
    const select = document.getElementById("af-championship-select");
    if (!select) return;
    const prior = selectedChampionship || select.value;
    const competitions = Array.from(new Set(cards.map(cardChampionship).filter(Boolean)))
      .sort((a,b) => a.localeCompare(b, "fr", {sensitivity:"base"}));
    const expected = ["", ...competitions];
    const current = Array.from(select.options, option => option.value);
    if (current.length !== expected.length || current.some((value,index) => value !== expected[index])) {
      const options = expected.map((value,index) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = index === 0 ? "Tous les championnats" : value;
        return option;
      });
      select.replaceChildren(...options);
    }
    if (competitions.includes(prior)) {
      selectedChampionship = prior;
      select.value = prior;
    } else {
      selectedChampionship = "";
      select.value = "";
    }
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
  function applyFilter() {
    ensureBar();
    const cards = getCards();
    updateDateOptions(cards);
    updateChampionshipOptions(cards);
    const today = localIso(new Date());
    const tomorrowDate = new Date(); tomorrowDate.setDate(tomorrowDate.getDate()+1);
    const tomorrow = localIso(tomorrowDate);
    let shown = 0;
    cards.forEach(card => {
      const date = cardDate(card);
      const dateVisible = mode === "all" || (mode === "today" && date === today) ||
        (mode === "tomorrow" && date === tomorrow) || (mode === "date" && date === selectedDate);
      const championshipVisible = !selectedChampionship || cardChampionship(card) === selectedChampionship;
      const visible = dateVisible && championshipVisible;
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
    const championshipSelect = bar.querySelector("#af-championship-select");
    if (championshipSelect) championshipSelect.value = selectedChampionship;
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