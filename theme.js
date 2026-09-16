/* Thème global — mode nuit mémorisé */
(function(){
  const KEY = "archetype_theme_nuit";
  const root = document.body;

  function applique(nuit){
    root.classList.toggle("theme-nuit", nuit);
    const bouton = document.getElementById("bouton-mode-nuit");
    if (bouton) {
      bouton.textContent = nuit ? "☀" : "☾";
      bouton.setAttribute("aria-label", nuit ? "Activer le mode clair" : "Activer le mode nuit");
      bouton.title = nuit ? "Mode clair" : "Mode nuit";
    }
  }

  const prefere = localStorage.getItem(KEY) === "1";
  applique(prefere);

  function installe(){
    if (!document.body || document.getElementById("bouton-mode-nuit")) return;
    const bouton = document.createElement("button");
    bouton.id = "bouton-mode-nuit";
    bouton.className = "bouton-mode-nuit";
    bouton.type = "button";
    bouton.addEventListener("click", function(){
      const nuit = !document.body.classList.contains("theme-nuit");
      localStorage.setItem(KEY, nuit ? "1" : "0");
      applique(nuit);
    });
    const cible = document.querySelector(".header-top, .header-archetype, header");
    if (cible) cible.appendChild(bouton);
    applique(document.body.classList.contains("theme-nuit"));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", installe);
  else installe();
})();
