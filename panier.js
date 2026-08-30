// panier.js — page dédiée au panier. Lit/écrit le même localStorage que
// index.js pour LA CONSTRUCTION du panier (cocher/décocher des matchs) --
// ça ne change pas. Ce qui change (29/08/2026 -- Supabase) : "Analyser tout
// le panier" n'envoie plus le tableau de matchs brut à trigger.js. Il :
//   1. s'assure d'une session Supabase (anonyme, pas de mot de passe --
//      créée automatiquement au premier envoi, réutilisée ensuite tant que
//      le navigateur garde la session) ;
//   2. insère le panier comme une ligne dans la table `paniers`, avec le
//      user_id de cette session (RLS empêche toute autre personne de la
//      lire) ;
//   3. transmet seulement l'id de cette ligne (panier_id) + le jeton de
//      session à trigger.js, qui vérifie l'appartenance avant de déclencher
//      le pipeline.
// Chaque personne a désormais son propre panier ET son propre résultat --
// plus de fichier panier.json partagé, plus d'écrasement entre deux envois
// simultanés.

// À REMPLACER par tes vraies valeurs (Project Settings > API sur supabase.com).
// SUPABASE_ANON_KEY est publique par design (RLS protège les données même
// si cette clé est visible dans le code source du site) -- rien à cacher ici.
const SUPABASE_URL = "https://hjrcqodwfjxqcjvjoxzq.supabase.co";
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhqcmNxb2R3Zmp4cWNqdmpveHpxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgxMTU3NjUsImV4cCI6MjEwMzY5MTc2NX0.rxJ2W-2UI0oQrGAprqnrPJM3WO1HCoYft0ZeS38oZfY";

// Nécessite d'avoir ajouté dans panier.html, avant panier.js :
// <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
//
// (30/08/2026 -- correctif) Tant que ce script n'est pas ajouté ET que
// SUPABASE_URL n'est pas remplacé, window.supabase n'existe pas -- appeler
// window.supabase.createClient() plantait alors TOUTE la page dès le
// chargement (avant même rafraichit()), ce qui empêchait le panier de
// s'afficher (0 au lieu du vrai nombre, même quand localStorage en
// contenait déjà). SUPABASE_CONFIGURE permet à la page de fonctionner
// normalement pour CONSTRUIRE le panier (cocher/décocher, copier) tant que
// Supabase n'est pas prêt -- seul "Analyser tout le panier" restera
// indisponible jusqu'à la configuration réelle (voir assureSession()).
const SUPABASE_CONFIGURE = !SUPABASE_URL.includes("TON-PROJET") && !!window.supabase;
// (30/08/2026 -- correctif critique) "const supabase = ..." plantait TOUT
// le fichier avec "SyntaxError: Can't create duplicate variable that
// shadows a global property: 'supabase'" -- la librairie
// @supabase/supabase-js crée déjà, toute seule, une variable globale
// nommée "supabase" dans le navigateur ; la redéclarer avec const/let est
// interdit en JavaScript. Renommé en "supabaseClient" partout dans ce
// fichier -- aucun rapport avec Supabase lui-même, uniquement un conflit
// de nom avec notre propre code.
const supabaseClient = SUPABASE_CONFIGURE ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null;

const CLE_PANIER = "archetype_panier";
const RE_MATCH_URL = /\/live-score\/([a-z0-9-]+)_([a-z0-9]+)\.html/i;

function chargePanier() {
  try {
    const brut = localStorage.getItem(CLE_PANIER);
    return brut ? JSON.parse(brut) : [];
  } catch (e) {
    console.error("panier illisible, réinitialisé", e);
    return [];
  }
}

function sauvePanier(liste) {
  localStorage.setItem(CLE_PANIER, JSON.stringify(liste));
}

function construitItemsEnvoi(panier) {
  return panier.map((item) => ({
    match_id: item.match_id,
    domicile: item.domicile,
    exterieur: item.exterieur,
    competition: item.competition,
    url_match: item.url_match,
    source: item.source,
    cotes_manuelles: item.cotes_manuelles,
  }));
}

// (29/08/2026 -- Supabase) Session anonyme : réutilise celle déjà en cours
// dans ce navigateur, ou en crée une nouvelle sinon. C'est cette session
// (via son user_id) qui isole le panier et le résultat de chaque personne.
async function assureSession() {
  if (!SUPABASE_CONFIGURE) {
    throw new Error(
      "Supabase pas encore configuré (SUPABASE_URL/clé, script @supabase/supabase-js dans panier.html) -- " +
      "voir TRANSITION.md section 0.5. Le panier fonctionne (cocher, copier), mais l'analyse en ligne pas encore."
    );
  }
  const { data: { session } } = await supabaseClient.auth.getSession();
  if (session) return session;

  const { data, error } = await supabaseClient.auth.signInAnonymously();
  if (error) throw new Error("Connexion anonyme impossible : " + error.message);
  return data.session;
}

function rafraichit() {
  const panier = chargePanier();
  const conteneur = document.getElementById("liste-panier");
  conteneur.innerHTML = "";

  if (panier.length === 0) {
    conteneur.innerHTML = "<div class='vide'>Panier vide -- retourne à l'accueil pour cocher des matchs.</div>";
  } else {
    panier.forEach((item, i) => {
      const div = document.createElement("div");
      div.className = "item-panier";

      const texte = document.createElement("span");
      const tagTexte = item.source === "betpawa" ? "bookmaker"
        : item.source === "manuel" ? "manuel" : "liste";
      const nbMarches = item.cotes_manuelles ? Object.keys(item.cotes_manuelles).length : 0;
      const suffixeCotes = nbMarches > 0 ? ` · ${nbMarches} marché(s) fournis` : "";
      texte.innerHTML = `${item.domicile} — ${item.exterieur}<span class="tag">${item.competition || "?"} · ${tagTexte}${suffixeCotes}</span>`;

      const retirer = document.createElement("button");
      retirer.textContent = "✕";
      retirer.title = "Retirer du panier";
      retirer.addEventListener("click", () => {
        const p = chargePanier();
        p.splice(i, 1);
        sauvePanier(p);
        rafraichit();
      });

      div.appendChild(texte);
      div.appendChild(retirer);
      conteneur.appendChild(div);
    });
  }

  document.getElementById("tout-copier-btn").textContent = `Tout copier (${panier.length})`;
  document.getElementById("analyser-panier-btn").textContent = `🔬 Analyser tout le panier (${panier.length})`;
}

function copierPanier() {
  const panier = chargePanier();
  const items = construitItemsEnvoi(panier);
  const json = JSON.stringify(items, null, 2);
  const bouton = document.getElementById("tout-copier-btn");

  const confirmeVisuellement = () => {
    const texteOriginal = `Tout copier (${panier.length})`;
    bouton.textContent = "Copié ✓";
    bouton.classList.add("copie");
    setTimeout(() => {
      bouton.textContent = texteOriginal;
      bouton.classList.remove("copie");
    }, 1500);
  };

  if (navigator.clipboard) {
    navigator.clipboard.writeText(json).then(confirmeVisuellement).catch(() => {
      const fallback = document.getElementById("copie-fallback");
      fallback.value = json;
      fallback.style.display = "block";
      fallback.select();
    });
  } else {
    const fallback = document.getElementById("copie-fallback");
    fallback.value = json;
    fallback.style.display = "block";
    fallback.select();
  }
}

async function analyserPanier() {
  const panier = chargePanier();
  const statut = document.getElementById("statut-analyse-panier");
  const bouton = document.getElementById("analyser-panier-btn");

  if (panier.length === 0) {
    statut.textContent = "❌ Panier vide -- coche au moins un match avant d'analyser.";
    statut.className = "erreur";
    return;
  }

  bouton.disabled = true;
  statut.textContent = `Envoi de ${panier.length} match(s) au pipeline…`;
  statut.className = "";

  try {
    // (29/08/2026 -- Supabase) 1. session anonyme, 2. la ligne panier est
    // créée directement depuis le navigateur (pas via trigger.js) -- RLS
    // (policy "chacun crée ses propres paniers") vérifie que user_id
    // correspond bien au jeton envoyé, donc personne ne peut créer un
    // panier au nom de quelqu'un d'autre même en bricolant la requête.
    const session = await assureSession();

    const { data: panierInsere, error: erreurInsertion } = await supabaseClient
      .from("paniers")
      .insert({ user_id: session.user.id, matchs: construitItemsEnvoi(panier) })
      .select()
      .single();

    if (erreurInsertion) throw new Error(erreurInsertion.message);

    // 3. trigger.js ne reçoit plus que l'id + le jeton -- jamais les
    // matchs eux-mêmes en clair dans cette requête-ci.
    const res = await fetch("/.netlify/functions/trigger", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({ panier_id: panierInsere.id }),
    });
    const data = await res.json();
    if (res.ok && data.ok) {
      statut.textContent = "✅ " + data.message + " Résultat dans quelques minutes sur \"Voir les pronostics\".";
      statut.className = "ok";
      sauvePanier([]);
      rafraichit();
    } else {
      statut.textContent = "❌ " + (data.error || "Erreur serveur");
      statut.className = "erreur";
    }
  } catch (e) {
    statut.textContent = "❌ " + (e.message || "Impossible de joindre le serveur.");
    statut.className = "erreur";
  } finally {
    bouton.disabled = false;
  }
}

document.getElementById("tout-copier-btn").addEventListener("click", copierPanier);
document.getElementById("analyser-panier-btn").addEventListener("click", analyserPanier);

document.getElementById("ajouter-manuel-btn").addEventListener("click", () => {
  const url = document.getElementById("manuel-url").value.trim();
  const domicile = document.getElementById("manuel-domicile").value.trim();
  const exterieur = document.getElementById("manuel-exterieur").value.trim();
  const competition = document.getElementById("manuel-competition").value.trim();

  const trouve = url.match(RE_MATCH_URL);
  if (!trouve) {
    alert("URL matchendirect invalide -- doit ressembler à https://www.matchendirect.fr/live-score/xxx_id.html");
    return;
  }
  if (!domicile || !exterieur || !competition) {
    alert("Domicile, extérieur et compétition sont obligatoires.");
    return;
  }

  const matchId = trouve[2];
  const panier = chargePanier();
  if (!panier.some((p) => p.match_id === matchId)) {
    panier.push({ match_id: matchId, url_match: url, domicile, exterieur, competition, source: "manuel" });
    sauvePanier(panier);
  }
  rafraichit();

  document.getElementById("manuel-url").value = "";
  document.getElementById("manuel-domicile").value = "";
  document.getElementById("manuel-exterieur").value = "";
  document.getElementById("manuel-competition").value = "";
});

rafraichit();
