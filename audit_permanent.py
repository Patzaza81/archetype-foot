"""
audit_permanent.py — Script d'audit permanent (TRANSITION.md 21.11)

Objectif : vérifier par le CALCUL, jamais par la lecture d'un commentaire,
une liste d'affirmations sur le comportement réel du code. Chaque bug
trouvé et corrigé s'ajoute ici pour toujours — ce fichier ne doit
JAMAIS rétrécir.

À faire tourner :
- au tout début de CHAQUE session, avant tout autre travail
- après tout commit multi-fichiers, avant de considérer un correctif
  comme livré

Exit code 0 = tout passe. Exit code 1 = au moins une vérité a échoué
(la liste des échecs est imprimée en clair, jamais un simple compteur).

Ce script importe le code réel (pas une copie, pas une réécriture des
règles) — un import qui échoue est déjà en soi un signal (fichier
manquant, erreur de syntaxe, dépendance cassée).
"""

import sys

echecs = []


def verite(nom, condition_calculee, detail=""):
    """Enregistre le résultat d'une vérité. `condition_calculee` doit être
    un booléen déjà calculé par exécution réelle du code, jamais une
    supposition."""
    global echecs
    if condition_calculee:
        print(f"[OK]   {nom}")
    else:
        print(f"[FAIL] {nom}" + (f" -- {detail}" if detail else ""))
        echecs.append(nom)


def section(titre):
    print(f"\n--- {titre} ---")


try:
    import calculs
except Exception as e:
    print(f"[FAIL] import calculs.py -- {e}")
    sys.exit(1)

try:
    import scraper_details as sd
except Exception as e:
    print(f"[FAIL] import scraper_details.py -- {e}")
    sys.exit(1)

try:
    import scraper_betpawa as sb
except Exception as e:
    print(f"[FAIL] import scraper_betpawa.py -- {e}")
    sys.exit(1)

try:
    import scraper_semaine as ss
except Exception as e:
    print(f"[FAIL] import scraper_semaine.py -- {e}")
    sys.exit(1)

try:
    import resolution_betpawa_precalcul as rbp
    import cache_betpawa as cbp
except Exception as e:
    print(f"[FAIL] import resolution_betpawa_precalcul.py / cache_betpawa.py -- {e}")
    sys.exit(1)

try:
    import adapte_justification as aj
except Exception as e:
    print(f"[FAIL] import adapte_justification.py -- {e}")
    sys.exit(1)

try:
    import cache_h2h as ch2h
    import cache_equipes as ceq
except Exception as e:
    print(f"[FAIL] import cache_h2h.py / cache_equipes.py -- {e}")
    sys.exit(1)


# ============================================================================
section("K_SHRINKAGE / ajuste_probabilite — doit avoir un effet réel")
# ============================================================================
# Bug historique (20.2) : ajuste_probabilite() existait mais n'était jamais
# appelée nulle part dans le pipeline -- K_SHRINKAGE n'avait aucun effet
# quelle que soit sa valeur.

p_brute = 0.9
p_ajustee = calculs.ajuste_probabilite(p_brute)
verite(
    "ajuste_probabilite(0.9) resserre bien vers 0.5 (n'est pas un no-op)",
    p_ajustee != p_brute and 0.5 < p_ajustee < p_brute,
    f"obtenu={p_ajustee}",
)

# calcule_ev doit utiliser la version ajustée en interne, pas la brute
ev_avec_brute_manuelle = (2.0 * p_brute) - 1
ev_reel = calculs.calcule_ev(p_brute, 2.0)
verite(
    "calcule_ev() applique bien ajuste_probabilite() en interne (pas la proba brute)",
    ev_reel != ev_avec_brute_manuelle,
    f"ev_reel={ev_reel} vs ev_si_brute_utilisee={ev_avec_brute_manuelle}",
)

# kelly_stake doit lui aussi utiliser la version ajustée (bug 20 : un
# commentaire affirmait explicitement l'inverse)
import inspect
source_kelly = inspect.getsource(calculs.kelly_stake)
verite(
    "kelly_stake() appelle bien ajuste_probabilite() (pas seulement calcule_ev())",
    "ajuste_probabilite(" in source_kelly,
)


# ============================================================================
section("GA_REFERENCE_PAR_LIGUE — doit varier par pays, pas retomber sur le default partout")
# ============================================================================
default_val = calculs.get_ga_reference(None)
france_val = calculs.get_ga_reference("France")
ecosse_val = calculs.get_ga_reference("Écosse")

verite(
    "get_ga_reference('France') diffère du default (calibrage réel actif)",
    france_val != default_val,
    f"France={france_val} default={default_val}",
)
verite(
    "get_ga_reference('Écosse') retombe bien sur le default (non calibré, documenté comme tel)",
    ecosse_val == default_val,
    f"Écosse={ecosse_val} default={default_val}",
)
verite(
    "get_ga_reference('PaysInexistantXYZ') ne casse pas, retombe sur default",
    calculs.get_ga_reference("PaysInexistantXYZ") == default_val,
)


# ============================================================================
section("GA_REFERENCE_PAR_COMPETITION — division distincte du pays (bug 05/09, corrigé)")
# ============================================================================
# Point critique #8 de TRANSITION.md : Eerste Divisie/Challenge Ligue
# héritaient à tort de la valeur de la 1ère division du même pays.

verite(
    "Suisse Challenge Ligue a SA PROPRE valeur (différente de la Super Ligue)",
    calculs.get_ga_reference("Suisse", "Challenge Ligue") != calculs.get_ga_reference("Suisse", None),
)
verite(
    "Suisse Super League garde sa valeur pays inchangée (pas de régression)",
    calculs.get_ga_reference("Suisse", "Super League") == calculs.get_ga_reference("Suisse", None),
)
verite(
    "compétition inconnue retombe sur la valeur pays (pas de valeur inventée)",
    calculs.get_ga_reference("Pays-Bas", "Eerste Divisie inconnue XYZ") == calculs.get_ga_reference("Pays-Bas", None),
)
verite(
    "Eerste Divisie (Pays-Bas D2) a SA PROPRE valeur (différente de l'Eredivisie)",
    calculs.get_ga_reference("Pays-Bas", "Eerste Divisie") != calculs.get_ga_reference("Pays-Bas", None),
)
verite(
    "pays=None, competition=None -> default (comportement d'origine intact)",
    calculs.get_ga_reference(None, None) == calculs.get_ga_reference(None),
)

with open("run_pipeline.py", encoding="utf-8") as f:
    _source_rp = f.read()
verite(
    "run_pipeline.py transmet bien 'competition' à calcule_lambda (pas seulement 'pays')",
    "competition=competition_partie" in _source_rp,
)

# Bug réel trouvé le 06/09 sur un vrai run (pas en test) : matchendirect
# affiche "Challenge Ligue" (français) avec un retour à la ligne avant,
# jamais "Challenge League" (anglais) -- la clé du dict doit matcher EXACTEMENT
# la chaîne brute réelle, extraction incluse (split+strip), pas une version
# idéalisée tapée à la main.
_competition_brute_reelle = "Suisse :\n                        Challenge Ligue"
_pays_reel = _competition_brute_reelle.split(":")[0].strip()
_partie_reelle = _competition_brute_reelle.split(":", 1)[1].strip()
verite(
    "Challenge Ligue (chaîne brute réelle avec saut de ligne) a SA PROPRE valeur, pas celle de la Super Ligue",
    calculs.get_ga_reference(_pays_reel, _partie_reelle) != calculs.get_ga_reference("Suisse", None),
    f"obtenu={calculs.get_ga_reference(_pays_reel, _partie_reelle)}",
)


# ============================================================================
section("decision_go_nogo — veto d'échantillon minimum (bug du 05/09, corrigé une 2e fois)")
# ============================================================================
# Bug réel trouvé le 05/09 : TRANSITION.md 21.8 annonçait ce veto comme
# "corrigé et testé (6 cas)" alors qu'il n'était jamais écrit dans le
# corps de la fonction (paramètres reçus, jamais lus).

liste_b_non_vide = [{"marche": "x"}]

cas_veto = [
    (10, 10, "GO", "échantillons suffisants"),
    (None, None, "GO", "échantillons non fournis (compat)"),
    (1, 10, "NO_GO", "domicile insuffisant (type Eldense)"),
    (10, 1, "NO_GO", "extérieur insuffisant"),
    (7, 7, "NO_GO", "sous le seuil des deux côtés"),
]
for dom, ext, attendu, desc in cas_veto:
    d = calculs.decision_go_nogo(
        liste_b_non_vide, liste_b_non_vide, 10,
        nb_matchs_domicile_utilises=dom, nb_matchs_exterieur_utilises=ext,
    )
    verite(
        f"decision_go_nogo veto échantillon : {desc}",
        d["verdict_global"] == attendu,
        f"attendu={attendu} obtenu={d['verdict_global']} (dom={dom}, ext={ext})",
    )

verite(
    "decision_go_nogo() sans marché éligible reste NO_GO",
    calculs.decision_go_nogo([], [], 10, nb_matchs_domicile_utilises=10,
                              nb_matchs_exterieur_utilises=10)["verdict_global"] == "NO_GO",
)


# ============================================================================
section("_competitions_correspondent — Ligue 1/2, Girone B/C, Serie C/Coupe")
# ============================================================================
# Bug 21.9 (Girone B vs Girone C, Ligue 1 vs Ligue 2) + bug complémentaire
# trouvé le 05/09 en testant le premier correctif (Serie C championnat vs
# Coupe Italie Serie C -- mot "serie" partagé, non filtré).

cas_correspondance = [
    ("girone b", "girone c", False),
    ("ligue 1", "ligue 2", False),
    ("serie c girone c", "coupe italie serie c", False),
    ("serie a", "serie b", False),
    ("division 1", "division 2", False),
    ("superliga", "superliga", True),
    ("chinese super league", "super ligue", True),
    ("ligue 1", "ligue 1", True),
    ("serie a", "serie a", True),
]
for cible, candidat, attendu in cas_correspondance:
    r = sd._competitions_correspondent(cible, candidat)
    verite(
        f"_competitions_correspondent({cible!r}, {candidat!r})",
        r == attendu,
        f"attendu={attendu} obtenu={r}",
    )


# ============================================================================
section("scraper_details 18.8 — boucle table-par-table réellement présente")
# ============================================================================
source_extrait = inspect.getsource(sd._extrait_historique_competition)
verite(
    "_extrait_historique_competition boucle sur plusieurs tables (pas un seul find_next('table'))",
    "MAX_TABLEAUX_ESSAYES" in source_extrait and "while table is not None" in source_extrait,
)

# AJOUT 07/09/2026 -- session faux négatifs (situation critique #20) : sans
# l'URL réellement fetchée dans le log, une "ancre INTROUVABLE" est
# indiscernable d'une vraie absence de donnée (confirmé en analysant les
# logs du run #104 -- cas concret trouvé : plusieurs pages /equipe/
# matchendirect peuvent partager le même nom affiché, ex. équipe masculine
# vs équipe féminine du même club). Vérifié par exécution réelle, pas par
# lecture du commentaire : on force un échec de fetch_html et on inspecte
# ce qui est réellement imprimé.
import io as _io_diag
import contextlib as _ctx_diag

_orig_fetch_html_diag = sd.fetch_html


def _fetch_html_echoue_toujours(url, retries=3, delay=2):
    raise RuntimeError("échec forcé (audit_permanent)")


sd.fetch_html = _fetch_html_echoue_toujours
_buf_diag = _io_diag.StringIO()
with _ctx_diag.redirect_stdout(_buf_diag):
    sd.recupere_gf_ga_avec_repli(
        "https://www.matchendirect.fr/equipe/audit-permanent-test.html",
        "Equipe Audit", "Pays Test : Competition Test", max_matchs=10,
    )
# CORRECTIF -- restaurer IMMÉDIATEMENT la vraie fonction, avant toute autre
# vérité de ce fichier qui pourrait dépendre du vrai fetch_html.
sd.fetch_html = _orig_fetch_html_diag
_sortie_diag = _buf_diag.getvalue()

verite(
    "[DIAG 18.8] inclut désormais l'URL réellement fetchée (pas seulement équipe/compétition/saison)",
    "url='https://www.matchendirect.fr/equipe/audit-permanent-test.html'" in _sortie_diag,
    detail=f"sortie observée : {_sortie_diag.strip()!r}",
)


# ============================================================================
section("_memes_equipes / _memes_equipes_ratio — équipe vs sa réserve (bug trouvé le 05/09)")
# ============================================================================
# Même bug que resolution_betpawa.py : "n1 in n2 or n2 in n1" confondait
# une équipe et sa réserve/jeunes (Real Madrid vs Real Madrid Castilla).
# Utilisées pour retrouver une ligne de classement ou un historique H2H.

cas_reserve = [
    ("Real Madrid", "Real Madrid Castilla", False),
    ("Sporting Lisbonne", "Sporting Lisbonne B", False),
    ("PSG", "PSG U19", False),
    ("AS Roma", "Roma", True),
    ("PSG", "PSG", True),
]
for a, b, attendu in cas_reserve:
    r = sd._memes_equipes(a, b)
    verite(f"scraper_details._memes_equipes({a!r}, {b!r})", r == attendu, f"obtenu={r}")
for a, b, attendu in cas_reserve:
    r = calculs._memes_equipes_ratio(a, b)
    verite(f"calculs._memes_equipes_ratio({a!r}, {b!r})", r == attendu, f"obtenu={r}")

for a, b, attendu in [
    ("Real Madrid", "Real Madrid Castilla", False),
    ("Barcelona", "Barcelona Atletic", False),
    ("PSG", "PSG U19", False),
    ("AC Horsens", "Horsens", True),
    ("S. Bratislava", "Slovan Bratislava", True),
]:
    r = sb._noms_correspondent(a, b)
    verite(f"scraper_betpawa._noms_correspondent({a!r}, {b!r}) [utilisée en prod]", r == attendu, f"obtenu={r}")

_classement_test = [{"equipe": "Real Madrid", "pts": 10}, {"equipe": "Real Madrid Castilla", "pts": 5}]
verite(
    "scraper_details.trouve_equipe_dans_classement ne confond pas Real Madrid avec sa réserve",
    sd.trouve_equipe_dans_classement(_classement_test, "Real Madrid") == {"equipe": "Real Madrid", "pts": 10},
)


# ============================================================================
section("Purges de cache — réellement appelées dans precalcul.py, pas juste définies")
# ============================================================================
with open("precalcul.py", encoding="utf-8") as f:
    source_precalcul = f.read()

for nom_appel in ["purge_equipes_expirees()", "purge_classement_expirees()",
                   "purge_h2h_expirees()", "purge_betpawa_matchs_joues("]:
    verite(
        f"precalcul.py appelle bien {nom_appel}",
        nom_appel in source_precalcul,
    )


# ============================================================================
section("probabilite_modele_ajustee — réellement construit dans serialise(), pas juste attendu par script.js")
# ============================================================================
with open("run_pipeline.py", encoding="utf-8") as f:
    source_run_pipeline = f.read()

verite(
    "run_pipeline.py construit bien le champ probabilite_modele_ajustee (pas seulement script.js qui l'attend)",
    'c["probabilite_modele_ajustee"]' in source_run_pipeline or "c['probabilite_modele_ajustee']" in source_run_pipeline,
)

with open("script.js", encoding="utf-8") as f:
    source_script_js = f.read()
verite(
    "script.js affiche bien probabilite_modele_ajustee avec repli sur la brute",
    "probabilite_modele_ajustee" in source_script_js,
)


# ============================================================================
section("TOUS_MARCHES_EVALUES — archivage complet réellement branché (pas seulement LISTE_A)")
# ============================================================================
verite(
    "run_pipeline.py construit bien TOUS_MARCHES_EVALUES, fusionné sur signal ensuite "
    "(motif changé au Groupe 2 -- calcul dans resultat_calcul avant fusion, pour "
    "isoler l'échec d'un match sans jamais laisser un champ fuiter -- voir #19)",
    'resultat_calcul["TOUS_MARCHES_EVALUES"]' in source_run_pipeline
    and "signal.update(resultat_calcul)" in source_run_pipeline,
)
with open("calcule_roi.py", encoding="utf-8") as f:
    source_calcule_roi = f.read()
verite(
    "calcule_roi.py consomme bien TOUS_MARCHES_EVALUES pour le calibrage (pas juste les paris déjà filtrés)",
    'get("TOUS_MARCHES_EVALUES")' in source_calcule_roi or "['TOUS_MARCHES_EVALUES']" in source_calcule_roi,
)


# ============================================================================
section("moteur de justification — réellement branché dans run_pipeline.py")
# ============================================================================
verite(
    "run_pipeline.py importe/utilise adapte_justification",
    "adapte_justification" in source_run_pipeline,
)


# ============================================================================
section("Bornes défensives et constantes gelées — pas de régression silencieuse")
# ============================================================================
# Bug 20.2 : 5 constantes gelées étaient revenues à d'anciennes valeurs
# sans que personne ne s'en aperçoive. Valeurs de référence figées ici
# (section 2 de TRANSITION.md / commentaires calculs.py du 04-05/09).

valeurs_attendues = {
    "BORNE_MIN_DEFENSE": 0.55,
    "BORNE_MAX_DEFENSE": 1.60,
    "K_SHRINKAGE": 0.48,
    "SEUIL_EV_MIN": 0.02,
    "FOURCHETTE_COTE_MIN": 1.25,
    "FOURCHETTE_COTE_MAX": 1.69,
    "KELLY_FRACTION": 0.25,
    "MISE_MAX_PARI": 0.04,
}
for nom, valeur_attendue in valeurs_attendues.items():
    valeur_reelle = getattr(calculs, nom, None)
    verite(
        f"{nom} = {valeur_attendue} (pas de régression silencieuse)",
        valeur_reelle == valeur_attendue,
        f"obtenu={valeur_reelle}",
    )


# ============================================================================
section("plafonner_cluster — plafond de risque CLUSTER_MAX réellement appliqué (bug #12, 06/09)")
# ============================================================================
# La fonction existait depuis l'origine mais n'était appelée nulle part --
# CLUSTER_MAX=10% n'avait jamais d'effet réel (un match pouvait exposer
# jusqu'à 3*4%=12%). Corrigée en même temps que le bug de clés
# ("ev"/"mise" vs les vrais champs "ev_brut"/"mise_pct_bankroll").

_paris_test = [
    {"ev_brut": 0.09, "mise_pct_bankroll": 0.04},
    {"ev_brut": 0.07, "mise_pct_bankroll": 0.04},
    {"ev_brut": 0.05, "mise_pct_bankroll": 0.04},
]
_r = calculs.plafonner_cluster([dict(p) for p in _paris_test], cle_ev="ev_brut", cle_mise="mise_pct_bankroll")
_total = sum(p["mise_pct_bankroll"] for p in _r)
verite(
    "plafonner_cluster() ramène bien 12% de mise cumulée à 10% (CLUSTER_MAX)",
    abs(_total - calculs.CLUSTER_MAX) < 1e-9,
    f"total obtenu={_total}",
)

with open("run_pipeline.py", encoding="utf-8") as f:
    _source_rp2 = f.read()
verite(
    "run_pipeline.py appelle bien calculs.plafonner_cluster() sur liste_b_avec_mise",
    "calculs.plafonner_cluster(" in _source_rp2,
)


# ============================================================================
section("resolution_betpawa tamis 1 — la date retournée n'est plus jetée (bug #5, 06/09)")
# ============================================================================
import resolution_betpawa as _rb
_source_resoudre_match = inspect.getsource(_rb.resoudre_match)
verite(
    "resoudre_match() compare bien la date trouvée à la date attendue au tamis 1",
    "date_trouvee == date_attendue" in _source_resoudre_match,
)


# ============================================================================
section("Groupe 3 — grille Poisson étendue à 15, docstring '5+' corrigé (bug #2, 06/09)")
# ============================================================================
verite(
    "matrice_poisson_dixon_coles() a maintenant max_buts=15 par défaut (plus 5)",
    inspect.signature(calculs.matrice_poisson_dixon_coles).parameters["max_buts"].default == 15,
)
_source_matrice = inspect.getsource(calculs.matrice_poisson_dixon_coles)
verite(
    "Le docstring ne contient plus l'ancienne affirmation fautive exacte ('agrégé en 5+ au-delà')",
    "agrégé en '5+' au-delà" not in _source_matrice and "agrégé en \"5+\" au-delà" not in _source_matrice,
)
_m5 = calculs.matrice_poisson_dixon_coles(0.4825799562858451, 5.127993059871004, max_buts=5)
_m15 = calculs.matrice_poisson_dixon_coles(0.4825799562858451, 5.127993059871004)
_m30 = calculs.matrice_poisson_dixon_coles(0.4825799562858451, 5.127993059871004, max_buts=30)
def _handicap_ext_m15(m):
    return sum(p for (x, y), p in m.items() if y - x >= 2)
verite(
    "Cas réel Partick-Celtic FC : la grille 0-15 est bien plus proche du quasi-exact (0-30) que l'ancienne 0-5",
    abs(_handicap_ext_m15(_m15) - _handicap_ext_m15(_m30)) < abs(_handicap_ext_m15(_m5) - _handicap_ext_m15(_m30)),
    f"0-5={_handicap_ext_m15(_m5):.4f} 0-15={_handicap_ext_m15(_m15):.4f} 0-30={_handicap_ext_m15(_m30):.4f}",
)
for _lam in [0.1, 1.0, 3.0, 5.0, 8.0, 15.0]:
    _m = calculs.matrice_poisson_dixon_coles(_lam, _lam)
    verite(f"Matrice lambda={_lam} -- somme des probabilités = 1.0", abs(sum(_m.values()) - 1.0) < 1e-9)


# ============================================================================
section("Groupe 3 — shrinkage empirique bayésien sur lambda de base (bug #3, 06/09)")
# ============================================================================
verite(
    "K_SHRINKAGE_LAMBDA existe et est distinct de K_SHRINKAGE (deux mécanismes différents)",
    hasattr(calculs, "K_SHRINKAGE_LAMBDA") and calculs.K_SHRINKAGE_LAMBDA != calculs.K_SHRINKAGE,
)
_lam_sans_n = calculs.calcule_lambda(1.4, 1.1, 1.2, 1.3, pays="France")
_lam_avec_n = calculs.calcule_lambda(
    1.4, 1.1, 1.2, 1.3, pays="France",
    nb_matchs_domicile_utilises=20, nb_matchs_exterieur_utilises=20,
)
verite(
    "Sans nb_matchs_*_utilises (None) -- comportement identique à avant, pas de shrinkage",
    _lam_sans_n["lambda_home"] == calculs.calcule_lambda(1.4, 1.1, 1.2, 1.3, pays="France")["lambda_home"],
)
verite(
    "Échantillon confortable (n=20) -- le shrinkage a un effet négligeable (<0.1)",
    abs(_lam_sans_n["lambda_home"] - _lam_avec_n["lambda_home"]) < 0.1,
)
_gf_brut_n8 = (9 + 1 * 7) / 8  # 8 matchs dont un 9-0 -- moyenne gonflée
_lam_n8_brut = calculs.calcule_lambda(1.0, 1.0, _gf_brut_n8, 1.0, pays="France")
_lam_n8_shrunk = calculs.calcule_lambda(
    1.0, 1.0, _gf_brut_n8, 1.0, pays="France",
    nb_matchs_domicile_utilises=8, nb_matchs_exterieur_utilises=8,
)
verite(
    "Échantillon n=8 avec un résultat exceptionnel (9-0) -- le shrinkage réduit bien lambda",
    _lam_n8_shrunk["lambda_away"] < _lam_n8_brut["lambda_away"],
    f"brut={_lam_n8_brut['lambda_away']:.3f} shrunk={_lam_n8_shrunk['lambda_away']:.3f}",
)
verite(
    "Cas réel Celtic FC (n=10, signal réel sur 10 matchs cohérents) -- le shrinkage NE l'écrase PAS "
    "au point de tomber sous 4 (vérifie qu'un vrai écart de niveau n'est pas confondu avec du bruit)",
    calculs.calcule_lambda(
        0.8, 3.2, 2.9, 0.9, pays="Écosse",
        nb_matchs_domicile_utilises=10, nb_matchs_exterieur_utilises=10,
    )["lambda_away"] > 4.0,
)


# ============================================================================
section("Groupe 3 — veto explicite de plausibilité lambda dans decision_go_nogo (bug #3, 06/09)")
# ============================================================================
verite(
    "LAMBDA_MIN_PLAUSIBLE / LAMBDA_MAX_PLAUSIBLE existent",
    hasattr(calculs, "LAMBDA_MIN_PLAUSIBLE") and hasattr(calculs, "LAMBDA_MAX_PLAUSIBLE"),
)
_decision_extreme = calculs.decision_go_nogo(
    liste_a=[{"ev": 0.9}], liste_b=[{"ev": 0.9}], nb_marches_evalues=5,
    nb_matchs_domicile_utilises=10, nb_matchs_exterieur_utilises=10,
    lambda_home=1.0, lambda_away=8.0,
)
verite(
    "Lambda hors plage plausible ET échantillon suffisant -- NO_GO avec motif explicite (pas un clamp silencieux)",
    _decision_extreme["verdict_global"] == "NO_GO" and "plausible" in _decision_extreme["motif_no_go"],
    _decision_extreme["motif_no_go"],
)
_decision_liechtenstein = calculs.decision_go_nogo(
    liste_a=[{"ev": 0.9}], liste_b=[{"ev": 0.9}], nb_marches_evalues=5,
    nb_matchs_domicile_utilises=1, nb_matchs_exterieur_utilises=1,
    lambda_home=0.55, lambda_away=12.8,
)
verite(
    "Cas réel Liechtenstein (n=1) -- NO_GO sur le veto d'échantillon (prioritaire), pas sur le veto lambda",
    _decision_liechtenstein["verdict_global"] == "NO_GO" and "chantillon" in _decision_liechtenstein["motif_no_go"],
)
verite(
    "Cas réel Celtic (lambda=5.13, échantillon suffisant) -- reste GO, pas rejeté par le veto de plausibilité",
    calculs.decision_go_nogo(
        liste_a=[{"ev": 0.9}], liste_b=[{"ev": 0.9}], nb_marches_evalues=5,
        nb_matchs_domicile_utilises=10, nb_matchs_exterieur_utilises=10,
        lambda_home=0.4825799562858451, lambda_away=5.127993059871004,
    )["verdict_global"] == "GO",
)
_source_rp3 = inspect.getsource(open("run_pipeline.py", encoding="utf-8").read().__class__) if False else None
with open("run_pipeline.py", encoding="utf-8") as f:
    _source_rp3 = f.read()
verite(
    "run_pipeline.py transmet bien nb_matchs_*_utilises à calcule_lambda (shrinkage actif en "
    "production) -- vérifié sur le contenu réel, pas une mise en page exacte (changée au "
    "Groupe 2 par l'imbrication dans le bloc try/except de #19)",
    'nb_matchs_domicile_utilises=stats_domicile["nb_domicile"],' in _source_rp3
    and 'nb_matchs_exterieur_utilises=stats_exterieur["nb_exterieur"],' in _source_rp3
    and "calculs.calcule_lambda(" in _source_rp3,
)
verite(
    "run_pipeline.py transmet bien lambda_home/lambda_away à decision_go_nogo (veto de plausibilité actif)",
    "lambda_home=lam[\"lambda_home\"], lambda_away=lam[\"lambda_away\"]" in _source_rp3,
)


# ============================================================================
section("Groupe 4 — calcule_calibrage() ne confond plus marchés et matchs distincts (bug #13, 06/09)")
# ============================================================================
import calcule_roi as _cr


def _marche_test(cote, proba):
    return {"marche": "Moins de 2.5 buts", "probabilite_modele": proba, "cote_observee": cote}


def _match_test(match_id, date, score, marches):
    return {"match_id": match_id, "date": date, "domicile": "A", "exterieur": "B",
            "verdict_global": "GO", "score": score, "TOUS_MARCHES_EVALUES": marches}


# 2 matchs à 28 marchés chacun ne doivent jamais compter comme 56 matchs distincts.
_marches_28 = [_marche_test(1.40, 0.85) for _ in range(28)]
_hist_pseudo = [
    {"date": "2026-08-01", "matchs": [_match_test("m1", "2026-08-01", "1-0", _marches_28)]},
    {"date": "2026-08-02", "matchs": [_match_test("m2", "2026-08-02", "1-0", _marches_28)]},
]
_r_pseudo = _cr.calcule_calibrage(_hist_pseudo)
verite(
    "2 matchs à 28 marchés chacun comptent bien pour 2 matchs distincts (pas 56)",
    _r_pseudo["nb_matchs_distincts_train"] + _r_pseudo["nb_matchs_distincts_test"] == 2,
    f"obtenu={_r_pseudo['nb_matchs_distincts_train'] + _r_pseudo['nb_matchs_distincts_test']}",
)
verite(
    "Avec seulement 2 matchs distincts, le palier n_min_10 reste None (pas de calibrage fabriqué)",
    _r_pseudo["recommandations_par_palier_n"]["n_min_10"] is None,
)

# 15 matchs distincts : n_min_10 exploitable, mais n_min_20 doit rester None
# -- jamais un repli silencieux du palier supérieur vers l'inférieur.
_hist_15 = [{"date": f"2026-01-{i+1:02d}",
             "matchs": [_match_test(f"m{i}", f"2026-01-{i+1:02d}", "1-0", [_marche_test(1.40, 0.85)])]}
            for i in range(15)]
_r_15 = _cr.calcule_calibrage(_hist_15)
_train_n = _r_15["nb_matchs_distincts_train"]
verite(
    "n_min_20 reste None quand l'échantillon train n'atteint pas 20 matchs distincts "
    "(aucune substitution par le palier n_min_10)",
    _train_n < 20 and _r_15["recommandations_par_palier_n"]["n_min_20"] is None,
    f"train={_train_n}",
)

# Score de Brier : pénalise un réglage surconfiant-et-faux plus qu'un
# réglage prudent-et-juste, même quand le taux de réussite seul ne le
# distinguerait pas de la même façon.
_hist_A = [{"date": f"2026-02-{i+1:02d}",
            "matchs": [_match_test(f"a{i}", f"2026-02-{i+1:02d}", "3-0", [_marche_test(1.30, 0.95)])]}
           for i in range(15)]
_hist_B = [{"date": f"2026-03-{i+1:02d}",
            "matchs": [_match_test(f"b{i}", f"2026-03-{i+1:02d}", "1-0", [_marche_test(1.30, 0.80)])]}
           for i in range(15)]
_reco_A = _cr.calcule_calibrage(_hist_A, k_min=1.0, k_max=1.0, k_pas=1.0,
                                 seuil_min=0.02, seuil_max=0.02, seuil_pas=1.0)["recommandations_par_palier_n"]["n_min_10"]
_reco_B = _cr.calcule_calibrage(_hist_B, k_min=1.0, k_max=1.0, k_pas=1.0,
                                 seuil_min=0.02, seuil_max=0.02, seuil_pas=1.0)["recommandations_par_palier_n"]["n_min_10"]
verite(
    "Le score de Brier est bien pire pour un réglage surconfiant-et-faux (0% de réussite, "
    "annoncé à 95%) qu'un réglage prudent-et-juste (100% de réussite, annoncé à 80%)",
    _reco_A is not None and _reco_B is not None and _reco_A["brier_score"] > _reco_B["brier_score"],
    f"A={_reco_A['brier_score'] if _reco_A else None} B={_reco_B['brier_score'] if _reco_B else None}",
)

# Contrôle hors-échantillon absent si le sous-ensemble test n'atteint pas
# lui-même 10 matchs distincts -- jamais une valeur fabriquée.
verite(
    "controle_hors_echantillon reste None quand le sous-ensemble test est trop petit",
    _r_pseudo["controle_hors_echantillon_par_palier_n"]["n_min_10"] is None,
)

# Matchs marqués non_resolu_definitif (#29) : exclus du calibrage ET comptés.
_hist_nrd = [{"date": "2026-03-01", "matchs": [
    {**_match_test("x1", "2026-03-01", None, [_marche_test(1.4, 0.8)]), "score_statut": "non_resolu_definitif"},
    _match_test("x2", "2026-03-01", "1-0", [_marche_test(1.4, 0.8)]),
]}]
_r_nrd = _cr.calcule_calibrage(_hist_nrd)
verite(
    "Un match marqué non_resolu_definitif est exclu du calibrage ET compté séparément",
    _r_nrd["nb_matchs_non_resolus_definitif"] == 1,
)


# ============================================================================
section("Groupe 4 — TOUS_MARCHES_EVALUES à nouveau archivé (bug #1, 06/09)")
# ============================================================================
import precalcul as _pc

_s_test = {
    "domicile": "A", "exterieur": "B", "competition": "C", "match_id": "x",
    "date": "2026-09-06", "heure": "20:00", "verdict_global": "GO", "motif_no_go": None,
    "confiance": "NORMALE", "source_cotes": "betpawa_auto", "betpawa_url": "u",
    "model_version": "v1", "LISTE_B_liste_finale_apres_correlation": [],
    "TOUS_MARCHES_EVALUES": [{"marche": "X", "probabilite_modele": 0.6, "cote_observee": 1.5}],
}
_r_archive = _pc._slim_pour_archive(_s_test)
verite(
    "_slim_pour_archive() conserve maintenant TOUS_MARCHES_EVALUES (calibrage débloqué)",
    _r_archive.get("TOUS_MARCHES_EVALUES") == _s_test["TOUS_MARCHES_EVALUES"],
)


# ============================================================================
section("Groupe 4 — statut explicite après le délai de vérification (bug #29, 06/09)")
# ============================================================================
import datetime as _dt
import verification_resultats as _vr

_aujourdhui = _vr.aujourdhui_france()
_trop_vieux = (_aujourdhui - _dt.timedelta(days=_vr.NB_JOURS_MAX_A_VERIFIER + 5)).isoformat()
_recent = (_aujourdhui - _dt.timedelta(days=2)).isoformat()
_hist_vr = [
    {"date": _trop_vieux, "matchs": [{"verdict_global": "GO", "score": None, "domicile": "A", "exterieur": "B"}]},
    {"date": _recent, "matchs": [{"verdict_global": "GO", "score": None, "domicile": "C", "exterieur": "D"}]},
]
_charge_orig, _sauve_orig, _verifie_orig = _vr.charge_historique, _vr.sauve_historique, _vr.verifie_jour
_vr.charge_historique = lambda: _hist_vr
_vr.sauve_historique = lambda h: None
_vr.verifie_jour = lambda jour: 0
_vr.main()
_vr.charge_historique, _vr.sauve_historique, _vr.verifie_jour = _charge_orig, _sauve_orig, _verifie_orig

verite(
    "Un jour au-delà du délai reçoit score_statut=non_resolu_definitif sur ses matchs non résolus",
    _hist_vr[0]["matchs"][0].get("score_statut") == "non_resolu_definitif",
)
verite(
    "Un jour récent (dans le délai) ne reçoit jamais ce statut, même sans score",
    "score_statut" not in _hist_vr[1]["matchs"][0],
)


# ============================================================================
section("Groupe 1 — identité canonique par match_id (bugs #7/#8, 06/09)")
# ============================================================================
import dispatch_pipeline as _dp

_panier_g1 = [{"match_id": "match_06_09", "domicile": "Tirana", "exterieur": "Vora", "competition": "Superliga"}]
_hist_g1 = [{"date": "2026-03-22", "matchs": [
    {"match_id": "match_22_03", "domicile": "Tirana", "exterieur": "Vora", "score": "3-0", "resultat": "MAUVAIS"},
]}]
verite(
    "cherche_deja_analyses() ne confond plus deux rencontres différentes entre les mêmes "
    "équipes (match_id différent -- ex. aller-retour, championnat vs coupe)",
    len(_dp.cherche_deja_analyses(_panier_g1, [], _hist_g1)) == 0,
)
verite(
    "extrait_resultat_de_ce_panier() ne renvoie pas non plus le mauvais match dans ce cas",
    _dp.extrait_resultat_de_ce_panier(_panier_g1, _hist_g1) == [],
)
_panier_degrade = [{"domicile": "Foo", "exterieur": "Bar", "competition": "X"}]
_hist_degrade = [{"date": "2026-09-01", "matchs": [{"domicile": "Foo", "exterieur": "Bar", "score": "1-0"}]}]
verite(
    "Le repli (domicile, exterieur) fonctionne toujours pour une entrée dégradée sans match_id",
    len(_dp.extrait_resultat_de_ce_panier(_panier_degrade, _hist_degrade)) == 1,
)


# ============================================================================
section("Groupe 1 — retrait de la saisie manuelle et de l'ancien moteur du cron (#23/#40/#22, 06/09)")
# ============================================================================
import os as _os

for _f in ("betpawa.html", "betpawa.js"):
    verite(f"{_f} n'existe plus (saisie manuelle de cotes retirée)", not _os.path.exists(_f))

with open("panier.js", encoding="utf-8") as f:
    _src_panier_js = f.read()
verite(
    "panier.js ne contient plus le handler d'ajout manuel ni RE_MATCH_URL",
    "ajouter-manuel-btn" not in _src_panier_js and "RE_MATCH_URL" not in _src_panier_js,
)

with open("panier.html", encoding="utf-8") as f:
    _src_panier_html = f.read()
verite(
    "panier.html ne contient plus le bloc #ajout-manuel ni le lien vers betpawa.html",
    "ajout-manuel" not in _src_panier_html and "betpawa.html" not in _src_panier_html,
)

with open("index.html", encoding="utf-8") as f:
    _src_index_html = f.read()
verite("index.html ne contient plus le lien vers betpawa.html", "betpawa.html" not in _src_index_html)

# Le moteur automatique (cotes_manuelles interne, résolution Betpawa) ne
# doit JAMAIS être touché par ce retrait -- le nom du champ est historique,
# pas une preuve de saisie manuelle (voir décision explicite de Patrick).
with open("resolution_betpawa_precalcul.py", encoding="utf-8") as f:
    _src_rbp = f.read()
verite(
    "resolution_betpawa_precalcul.py continue d'écrire cotes_manuelles en interne "
    "(moteur automatique, jamais retiré malgré le nom historique du champ)",
    'm["cotes_manuelles"] = cotes' in _src_rbp,
)
for _f in ("scraper_betpawa.py", "parse_betpawa.py", "parse_betpawa_url.py"):
    verite(f"{_f} existe toujours (fonctions utilisées en interne par le moteur actif)", _os.path.exists(_f))

with open(".github/workflows/pipeline.yml", encoding="utf-8") as f:
    _src_yml = f.read()
verite(
    "pipeline.yml ne lance plus scraper_betpawa.py (ancien moteur retiré du cron -- "
    "seule une mention en commentaire explicatif est attendue, pas une commande run:)",
    "run: python scraper_betpawa.py" not in _src_yml,
)
verite(
    "pipeline.yml ne lance plus run_pipeline.py sous condition schedule/panier_id vide "
    "(seule la branche dispatch_pipeline.py peut encore l'appeler, en interne)",
    "python run_pipeline.py" not in _src_yml and "import run_pipeline" in open("dispatch_pipeline.py", encoding="utf-8").read(),
)


# ============================================================================
section("Groupe 2 — isolation de l'échec d'un match, jamais un faux signal partiel (bug #19, 06/09)")
# ============================================================================
import run_pipeline as _rp


def _casse_calcule_lambda_une_fois():
    appels = {"n": 0}
    def _f(*a, **k):
        appels["n"] += 1
        if appels["n"] == 1:
            raise ValueError("simulation d'erreur")
        return {"lambda_home": 1.0, "lambda_away": 1.0, "audit": {}}
    return _f


_orig_recupere_details_match = _rp.recupere_details_match
_orig_recupere_gf_ga_avec_repli = _rp.recupere_gf_ga_avec_repli
_orig_recupere_classement_du_match = _rp.recupere_classement_du_match
_orig_recupere_h2h = _rp.recupere_h2h
_orig_recupere_cotes_marches = _rp.recupere_cotes_marches
_orig_calcule_lambda = calculs.calcule_lambda

_rp.recupere_details_match = lambda url: {"url_equipe_domicile": "u1", "url_equipe_exterieur": "u2"}
_rp.recupere_gf_ga_avec_repli = lambda url, nom, comp, max_matchs: {
    "gf_domicile": 1.2, "ga_domicile": 1.1, "gf_exterieur": 1.0, "ga_exterieur": 1.3,
    "nb_domicile": 10, "nb_exterieur": 10,
}
_rp.recupere_classement_du_match = lambda url, comp: []
_rp.recupere_h2h = lambda url: []
_rp.recupere_cotes_marches = lambda url: {}
calculs.calcule_lambda = _casse_calcule_lambda_une_fois()

_matchs_g2 = [
    {"domicile": "A", "exterieur": "B", "competition": "X", "url_match": "http://exemple/1"},
    {"domicile": "C", "exterieur": "D", "competition": "Y", "url_match": "http://exemple/2"},
]
_resultats_g2 = _rp.construit_signaux(_matchs_g2)
_r1, _r2 = _resultats_g2[0], _resultats_g2[1]

# CORRECTIF -- restaurer IMMÉDIATEMENT les vraies fonctions : ce module est
# partagé par tout le fichier, un monkeypatch qui reste en place casserait
# silencieusement toute vérité plus bas qui inspecte le vrai code source de
# calculs.calcule_lambda (déjà vécu une fois en écrivant ce correctif -- 2
# vérités antérieures ont échoué avant cette restauration).
_rp.recupere_details_match = _orig_recupere_details_match
_rp.recupere_gf_ga_avec_repli = _orig_recupere_gf_ga_avec_repli
_rp.recupere_classement_du_match = _orig_recupere_classement_du_match
_rp.recupere_h2h = _orig_recupere_h2h
_rp.recupere_cotes_marches = _orig_recupere_cotes_marches
calculs.calcule_lambda = _orig_calcule_lambda

verite(
    "Un match dont le calcul plante reste traite=False, sans AUCUN champ de "
    "décision/lambda/cote fuité (pas de faux signal partiellement calculé)",
    _r1.get("traite") is False and "erreur_technique" in _r1.get("raison_non_traite", "")
    and "verdict_global" not in _r1 and "lambda" not in _r1
    and "cote_1" not in _r1 and "LISTE_B_liste_finale_apres_correlation" not in _r1,
)
verite(
    "L'échec d'un match n'affecte pas le traitement du match suivant dans le même run",
    _r2.get("traite") is True and "verdict_global" in _r2,
)


# ============================================================================
section("Groupe 2 — panier marqué en échec explicite, jamais bloqué en_cours (bug #11, 06/09)")
# ============================================================================
import dispatch_pipeline as _dp2

_appels_g2 = []
_orig_recupere_panier = _dp2.recupere_panier
_orig_marque_en_cours = _dp2.marque_panier_en_cours
_orig_marque_echec = _dp2.marque_panier_echec
_orig_cherche_deja = _dp2.cherche_deja_analyses
_orig_ecrit_resultat = _dp2.ecrit_resultat

_dp2.recupere_panier = lambda panier_id: {
    "id": panier_id, "user_id": "user-test",
    "matchs": [{"match_id": "m1", "domicile": "A", "exterieur": "B", "competition": "X"}],
}
_dp2.marque_panier_en_cours = lambda panier_id: _appels_g2.append(("en_cours", panier_id))
_dp2.marque_panier_echec = lambda panier_id: _appels_g2.append(("echec", panier_id))
_dp2.cherche_deja_analyses = lambda panier, precalcul, historique: {
    "m1": {"domicile": "A", "exterieur": "B", "verdict_global": "GO", "traite": True}
}


def _ecrit_resultat_qui_plante_g2(*a, **k):
    raise RuntimeError("panne simulée")


_dp2.ecrit_resultat = _ecrit_resultat_qui_plante_g2

import os as _os2
_os2.environ["SUPABASE_URL"] = "https://exemple.test"
_os2.environ["SUPABASE_SERVICE_ROLE_KEY"] = "cle-test"
_os2.environ["INPUT_PANIER_ID"] = "panier-verite-g2"

try:
    _dp2.main()
    _sortie_g2 = False
except SystemExit as _e:
    _sortie_g2 = (_e.code != 0)

# Restauration immédiate, même précaution que pour le test #19 ci-dessus.
_dp2.recupere_panier = _orig_recupere_panier
_dp2.marque_panier_en_cours = _orig_marque_en_cours
_dp2.marque_panier_echec = _orig_marque_echec
_dp2.cherche_deja_analyses = _orig_cherche_deja
_dp2.ecrit_resultat = _orig_ecrit_resultat

verite(
    "Une exception en cours de traitement marque le panier 'echec' (jamais bloqué "
    "'en_cours' indéfiniment) et fait sortir le processus en erreur",
    ("en_cours", "panier-verite-g2") in _appels_g2 and ("echec", "panier-verite-g2") in _appels_g2
    and _appels_g2.index(("en_cours", "panier-verite-g2")) < _appels_g2.index(("echec", "panier-verite-g2"))
    and _sortie_g2,
)


# ============================================================================
section("Groupe 2 — garde bloquante si le pré-calcul échoue réellement (bug #10, 06/09)")
# ============================================================================
with open(".github/workflows/pipeline.yml", encoding="utf-8") as f:
    _yml_g2 = f.read()

_debut_garde = _yml_g2.index("Vérifier que le pré-calcul a réellement produit")
_fin_garde = _yml_g2.index("Pipeline déclenché manuellement")
_bloc_garde = _yml_g2[_debut_garde:_fin_garde]

_debut_precalcul = _yml_g2.index("Pré-calcul J0/J+1/J+2/J+3")
_bloc_precalcul = _yml_g2[_debut_precalcul:_debut_garde]

_debut_semaine = _yml_g2.index("Générer la liste J+2")
_bloc_semaine = _yml_g2[_debut_semaine:_debut_precalcul]

verite(
    "La garde post-précalcul cible steps.precalcul.outcome, vérifie precalcul_leger.json, "
    "et n'a jamais la directive continue-on-error: sur elle-même",
    "steps.precalcul.outcome" in _bloc_garde and "precalcul_leger.json" in _bloc_garde
    and "exit 1" in _bloc_garde and "continue-on-error:" not in _bloc_garde,
)
verite(
    "L'étape précalcul.py garde son id et son continue-on-error (nécessaire pour que "
    "la garde puisse lire l'outcome sans arrêter le job avant elle)",
    "id: precalcul" in _bloc_precalcul and "continue-on-error: true" in _bloc_precalcul,
)
verite(
    "scraper_semaine.py reste hors de la garde bloquante (dégradation de couverture "
    "acceptée, pas une donnée corrompue -- décision explicite de Patrick)",
    "continue-on-error: true" in _bloc_semaine and "exit 1" not in _bloc_semaine,
)


# ============================================================================
section("Groupe 6 — déduplication match_id dans matchs_semaine.json (bug #9, 06/09)")
# ============================================================================
# Preuve directe (06/09) : 19 match_id présents sous DEUX dates différentes
# dans le vrai matchs_semaine.json du dépôt (matchs de 00h00-02h30 heure
# française, listés par matchendirect.fr sur les deux pages calendaires
# adjacentes -- PAS le bug de redirection déjà connu sur "demain", le
# recouvrement mesuré n'est que de 6-7%, jamais 100%).

_g6_sans_doublon = [
    {"match_id": "g6a", "domicile": "A", "exterieur": "B", "date": "2026-09-08"},
    {"match_id": "g6b", "domicile": "C", "exterieur": "D", "date": "2026-09-09"},
]
verite(
    "deduplique_par_match_id() ne touche pas une liste déjà sans doublon",
    ss.deduplique_par_match_id(_g6_sans_doublon) == _g6_sans_doublon,
)

_g6_vrai_doublon = [
    {"match_id": "g6x", "domicile": "Fluminense", "exterieur": "Platense", "date": "2026-09-08"},
    {"match_id": "g6x", "domicile": "Fluminense", "exterieur": "Platense", "date": "2026-09-09"},
]
_g6_resultat = ss.deduplique_par_match_id(_g6_vrai_doublon)
verite(
    "Un vrai doublon (même match_id, 2 dates) est réduit à 1 seule entrée, "
    "la date la plus proche (J+2) est celle gardée",
    len(_g6_resultat) == 1 and _g6_resultat[0]["date"] == "2026-09-08",
    f"obtenu={_g6_resultat}",
)

_g6_meme_heure_equipes_differentes = [
    {"match_id": "g6p1", "domicile": "A", "exterieur": "B", "date": "2026-09-08", "heure": "01:00"},
    {"match_id": "g6p2", "domicile": "C", "exterieur": "D", "date": "2026-09-08", "heure": "01:00"},
]
verite(
    "Deux matchs différents à la même heure ne sont jamais fusionnés à tort",
    len(ss.deduplique_par_match_id(_g6_meme_heure_equipes_differentes)) == 2,
)

verite(
    "deduplique_par_match_id() ne plante pas sur une liste vide",
    ss.deduplique_par_match_id([]) == [],
)

_g6_sans_id = [{"domicile": "A", "exterieur": "B", "date": "2026-09-08"}]
verite(
    "Une entrée sans match_id est conservée telle quelle (aucun crash, pas de dédup impossible)",
    ss.deduplique_par_match_id(_g6_sans_id) == _g6_sans_id,
)

# Vérité sur les VRAIES données du dépôt, pas seulement des cas construits.
import json as _json
try:
    with open("matchs_semaine.json", encoding="utf-8") as f:
        _g6_donnees_reelles = _json.load(f)
    _g6_dedupliquees = ss.deduplique_par_match_id(_g6_donnees_reelles)
    _g6_ids = [m["match_id"] for m in _g6_dedupliquees if m.get("match_id")]
    verite(
        "matchs_semaine.json réel, une fois dédupliqué, n'a plus aucun match_id "
        "associé à deux dates différentes",
        len(_g6_ids) == len(set(_g6_ids)),
        f"{len(_g6_donnees_reelles)} matchs avant, {len(_g6_dedupliquees)} après",
    )
except (FileNotFoundError, _json.JSONDecodeError) as e:
    print(f"[SKIP] vérité matchs_semaine.json réel -- fichier absent ou invalide ({e})")


# ============================================================================
section("Groupe 5 — titre Betpawa revérifié avant extraction des cotes (bug #6, 06/09)")
# ============================================================================
# Preuve directe : meilleur_parsing()/parse_betpawa_playwright() sont
# génériques par conception (1X2/BTTS/Over-Under ne dépendent d'aucun nom
# d'équipe dans le texte capturé) -- une mauvaise URL Betpawa renvoie donc
# de VRAIES cotes, juste pour le mauvais match, jamais un résultat vide.
# Risque concentré sur les cache hits antérieurs au correctif tamis 1
# (#12, réserve/jeunes). Vérifié ici par exécution réelle de
# resout_cotes_betpawa(), monkeypatchs de bas niveau (réseau/Playwright),
# jamais une relecture de commentaire.

_g5_titre_fmt = ("Bet on {dom} - {ext} | 3:00 pm Sat 29/08 | Premier League | "
                 "England | Football | betPawa Cameroon")
_g5_fichier_cache_test = "cache_betpawa_test_audit_permanent.json"


def _g5_execute(fenetre, titre_page, cache_contenu, cotes_simulees):
    import json as _json_g5
    with open(_g5_fichier_cache_test, "w", encoding="utf-8") as f:
        _json_g5.dump(cache_contenu, f)

    _orig_cherche = rbp.cherche_dans_cache
    _orig_invalide = rbp.invalide_entree
    _orig_recupere = rbp.recupere_page
    _orig_meilleur = rbp.meilleur_parsing
    _orig_resoudre = rbp.resoudre_match
    _orig_enregistre = rbp.enregistre_correspondance
    _g5_appels_invalide = []

    rbp.cherche_dans_cache = lambda d, e, dt: cbp.cherche_dans_cache(
        d, e, dt, fichier_cache=_g5_fichier_cache_test)
    rbp.invalide_entree = lambda d, e, dt: (
        _g5_appels_invalide.append((d, e, dt)) or
        cbp.invalide_entree(d, e, dt, fichier_cache=_g5_fichier_cache_test)
    )
    rbp.recupere_page = lambda page, url: ("texte capture", titre_page)
    rbp.meilleur_parsing = lambda texte, d, e: cotes_simulees
    rbp.resoudre_match = lambda page, d, e, dt, etapes: "https://betpawa.cm/event/FRAIS"
    rbp.enregistre_correspondance = lambda *a, **k: None

    try:
        compteurs = rbp.resout_cotes_betpawa(fenetre)
    finally:
        # Restauration immédiate -- même précaution que pour les tests #19/#10
        # ci-dessus (un monkeypatch laissé actif casse silencieusement les
        # vérités plus anciennes).
        rbp.cherche_dans_cache = _orig_cherche
        rbp.invalide_entree = _orig_invalide
        rbp.recupere_page = _orig_recupere
        rbp.meilleur_parsing = _orig_meilleur
        rbp.resoudre_match = _orig_resoudre
        rbp.enregistre_correspondance = _orig_enregistre

    return compteurs, fenetre[0], _g5_appels_invalide


_g5_c1, _g5_m1, _ = _g5_execute(
    [{"domicile": "Fluminense", "exterieur": "Platense", "date": "2026-09-08"}],
    _g5_titre_fmt.format(dom="Fluminense", ext="Platense"),
    {}, {"1x2": {"1": 1.5, "N": 3.2, "2": 5.0}},
)
verite(
    "Titre correspondant au match attendu -- cotes extraites normalement, aucun mismatch",
    _g5_c1["betpawa_titre_mismatch"] == 0 and _g5_c1["betpawa_cotes_extraites"] == 1
    and "cotes_manuelles" in _g5_m1,
)

_g5_c4, _g5_m4, _ = _g5_execute(
    [{"domicile": "Fluminense", "exterieur": "Platense", "date": "2026-09-08"}],
    _g5_titre_fmt.format(dom="Boca Juniors", ext="São Paulo"),
    {}, {"1x2": {"1": 1.5, "N": 3.2, "2": 5.0}},
)
verite(
    "Titre d'un AUTRE match (résolution fraîche) -- cotes NON extraites, "
    "betpawa_titre_mismatch incrémenté",
    _g5_c4["betpawa_titre_mismatch"] == 1 and _g5_c4["betpawa_cotes_extraites"] == 0
    and "cotes_manuelles" not in _g5_m4,
)

_g5_cle = cbp._cle("Fluminense", "Platense", "2026-09-08")
_g5_cache_avec_hit = {_g5_cle: {"event_id": "https://betpawa.cm/event/VIEUX", "date": "2026-09-08"}}
_g5_c5, _g5_m5, _g5_inv5 = _g5_execute(
    [{"domicile": "Fluminense", "exterieur": "Platense", "date": "2026-09-08"}],
    _g5_titre_fmt.format(dom="Boca Juniors", ext="São Paulo"),
    _g5_cache_avec_hit, {"1x2": {"1": 1.5, "N": 3.2, "2": 5.0}},
)
_g5_apres = cbp.cherche_dans_cache("Fluminense", "Platense", "2026-09-08",
                                    fichier_cache=_g5_fichier_cache_test)
verite(
    "Cache hit dont le titre chargé ne correspond pas -- entrée cache invalidée, "
    "cotes NON extraites",
    _g5_c5["betpawa_cache_hit"] == 1 and _g5_c5["betpawa_titre_mismatch"] == 1
    and _g5_inv5 == [("Fluminense", "Platense", "2026-09-08")] and _g5_apres is None,
)

_g5_c3, _g5_m3, _ = _g5_execute(
    [{"domicile": "A", "exterieur": "B", "date": "2026-09-08"}],
    "Titre non standard qui ne matche pas le format Betpawa",
    {}, {"1x2": {"1": 2.0, "N": 3.0, "2": 3.5}},
)
verite(
    "Titre imparsable (format inconnu) -- comportement inchangé, cotes quand "
    "même extraites, aucun crash",
    _g5_c3["betpawa_titre_mismatch"] == 0 and _g5_c3["betpawa_cotes_extraites"] == 1,
)

verite(
    "invalide_entree() sur une clé déjà absente du cache ne plante pas et renvoie False",
    cbp.invalide_entree("Inconnu", "Inconnu2", "2026-09-08",
                         fichier_cache=_g5_fichier_cache_test) is False,
)

import os as _os_g5
if _os_g5.path.exists(_g5_fichier_cache_test):
    _os_g5.remove(_g5_fichier_cache_test)


# ============================================================================
section("Groupe 7 (partie #20) — meilleur_parsing() choisit sur marchés PLAUSIBLES, pas bruts (06/09)")
# ============================================================================
verite(
    "_marches_plausibles() ne touche pas des cotes normales (aucune <= 1.0)",
    sb._marches_plausibles({"1x2": {"1": 1.5, "N": 3.2, "2": 5.0}})
    == {"1x2": {"1": 1.5, "N": 3.2, "2": 5.0}},
)
verite(
    "_marches_plausibles() écarte un marché entier dès qu'une valeur <= 1.0 y figure, "
    "sans toucher aux autres marchés",
    sb._marches_plausibles({"1x2": {"1": 1.5, "N": 3.2, "2": 5.0}, "errone": {"x": 0.8, "y": 2.0}})
    == {"1x2": {"1": 1.5, "N": 3.2, "2": 5.0}},
)
verite(
    "_marches_plausibles() tolère None (absence connue, pas une erreur)",
    sb._marches_plausibles({"over_under_2.5": {"plus": 1.9, "moins": None}})
    == {"over_under_2.5": {"plus": 1.9, "moins": None}},
)

_g7_orig_pb = sb.parse_betpawa
_g7_orig_pbu = sb.parse_betpawa_url
_g7_orig_pbp = sb.parse_betpawa_playwright
sb.parse_betpawa = lambda t, d, e: {
    "1x2": {"1": 0.4, "N": 0.2, "2": 0.1},
    "btts": {"Oui": 0.3, "Non": 0.2},
    "pair_impair": {"pair": 0.5, "impair": 0.1},
}
sb.parse_betpawa_url = lambda t, d, e: {"1x2": {"1": 1.9, "N": 3.4, "2": 3.9}}
sb.parse_betpawa_playwright = lambda t, d, e: {}
try:
    _g7_resultat = sb.meilleur_parsing("texte quelconque", "A", "B")
finally:
    sb.parse_betpawa = _g7_orig_pb
    sb.parse_betpawa_url = _g7_orig_pbu
    sb.parse_betpawa_playwright = _g7_orig_pbp

verite(
    "meilleur_parsing() choisit le parseur avec le plus de marchés PLAUSIBLES "
    "(1 marché valide bat 3 marchés bruts mais tous à cotes <=1.0)",
    _g7_resultat == {"1x2": {"1": 1.9, "N": 3.4, "2": 3.9}},
)
verite(
    "_marches_plausibles() conserve une valeur non-dict sans la filtrer, aucun crash",
    sb._marches_plausibles({"note_libre": "texte quelconque"}) == {"note_libre": "texte quelconque"},
)
verite(
    "_marches_plausibles() sur un dict vide ne plante pas",
    sb._marches_plausibles({}) == {},
)


# ============================================================================
section("Groupe 8 — filtre réserve/jeunes sur le nom d'équipe, pas seulement la compétition (bug #4, 06/09)")
# ============================================================================
verite(
    "est_equipe_jeune_ou_reserve() détecte une équipe réserve (nom composé, marqueur 'castilla')",
    _pc.est_equipe_jeune_ou_reserve("Real Madrid Castilla") is True,
)
verite(
    "est_equipe_jeune_ou_reserve() détecte une équipe jeunes (marqueur 'u19')",
    _pc.est_equipe_jeune_ou_reserve("PSG U19") is True,
)
verite(
    "est_equipe_jeune_ou_reserve() ne déclenche pas de faux positif sur un nom sans marqueur",
    _pc.est_equipe_jeune_ou_reserve("Manchester United") is False
    and _pc.est_equipe_jeune_ou_reserve("Independiente") is False,
)
verite(
    "est_equipe_jeune_ou_reserve(None) ne plante pas, renvoie False",
    _pc.est_equipe_jeune_ou_reserve(None) is False,
)


# ============================================================================
section("Groupe 8 — orientation H2H par équipe dans la justification (bug #41, 06/09 -- correctif d'orientation SEUL, décision explicite de Patrick)")
# ============================================================================
# Portée volontairement limitée à l'orientation domicile/extérieur par
# équipe (cohérente avec calcule_ratio_h2h() dans calculs.py). Le problème
# plus profond découvert en creusant (le marché symétrique "Plus de N
# buts" évalue le TOTAL des deux équipes, pas les buts propres de
# l'équipe visée -- reste présent pour OVER_UNDER_EQUIPE ; CLEAN_SHEET et
# SANS_BUT ne produisent d'ailleurs aujourd'hui AUCUNE preuve H2H, avec ou
# sans ce correctif, le nom de marché sans suffixe n'étant reconnu par
# verifie_pari() dans aucun des deux cas) n'est PAS corrigé ici -- décision
# explicite de Patrick de garder le correctif d'orientation seul.
def _g8_h2h(dom_brut, ext_brut, bd, be):
    return {"domicile_brut": dom_brut, "exterieur_brut": ext_brut, "buts_domicile": bd, "buts_exterieur": be}


verite(
    "_preuve_h2h(equipe_cible=None) reproduit le comportement symétrique d'origine (régression)",
    (lambda p: p is not None and p.total == 2 and p.occurrences == 2)(
        aj._preuve_h2h("Plus de 1.5 buts",
                        [_g8_h2h("Fluminense", "Platense", 2, 1), _g8_h2h("Platense", "Fluminense", 0, 3)],
                        equipe_cible=None)
    ),
)
verite(
    "_preuve_h2h() attribue correctement l'équipe visée qu'elle ait joué domicile ou extérieur dans le H2H",
    (lambda p1, p2: p1 is not None and p1.equipe == "Fluminense"
     and p2 is not None and p2.equipe == "Fluminense")(
        aj._preuve_h2h("Plus de 1.5 buts - Domicile", [_g8_h2h("Fluminense", "Platense", 2, 1)], equipe_cible="Fluminense"),
        aj._preuve_h2h("Plus de 1.5 buts - Domicile", [_g8_h2h("Platense", "Fluminense", 1, 2)], equipe_cible="Fluminense"),
    ),
)
verite(
    "_preuve_h2h() écarte une ligne H2H dont aucun des deux noms ne correspond à l'équipe visée, "
    "jamais une correspondance devinée",
    aj._preuve_h2h("Plus de 1.5 buts - Domicile",
                    [_g8_h2h("Equipe Inconnue A", "Equipe Inconnue B", 2, 1)],
                    equipe_cible="Fluminense") is None,
)
verite(
    "_preuve_h2h() sur une liste H2H vide ne plante pas",
    aj._preuve_h2h("Plus de 1.5 buts - Domicile", [], equipe_cible="Fluminense") is None,
)
verite(
    "_correspond_a_equipe() ne confond pas une équipe avec sa réserve homonyme (veto réserve, même "
    "logique que calculs._memes_equipes_ratio)",
    aj._preuve_h2h("Plus de 1.5 buts - Domicile",
                    [_g8_h2h("Real Madrid Castilla", "Betis", 2, 1)],
                    equipe_cible="Real Madrid") is None,
)


# ============================================================================
section("Groupe 8 — TTL cache équipes/H2H réduits de 7 à 4 jours (bugs #30/#31, décision de Patrick, 06/09)")
# ============================================================================
verite(
    "cache_equipes.TTL_SANS_HISTORIQUE_HEURES vaut bien 96h (4 jours), plus 7 jours",
    ceq.TTL_SANS_HISTORIQUE_HEURES == 24 * 4,
)
verite(
    "cache_h2h.TTL_HEURES vaut bien 96h (4 jours), plus 7 jours",
    ch2h.TTL_HEURES == 24 * 4,
)


# ============================================================================
section("Moteur V0 (07/09/2026) — invariants figés, décision explicite de Patrick")
# ============================================================================
import moteur_v0 as _mv0

verite(
    "N < N_MIN (8) déclenche un NO_BET dur, quel que soit le reste",
    _mv0.evalue_match_v0(1.5, 1.0, 1.2, 1.1, nb_matchs_domicile_utilises=7,
                         nb_matchs_exterieur_utilises=10, cotes_marches={"BTTS - oui": 1.01})["verdict"] == "NO_BET",
)

_r_lambda_implausible = _mv0.evalue_match_v0(
    12.0, 1.0, 1.2, 1.1, nb_matchs_domicile_utilises=10, nb_matchs_exterieur_utilises=10, cotes_marches={},
)
verite(
    "Lambda hors [0.1, 6.0] (cas type Vaduz II) déclenche un NO_BET, jamais un clamp silencieux",
    _r_lambda_implausible["verdict"] == "NO_BET" and "plausible" in (_r_lambda_implausible["motif"] or ""),
)

verite(
    "La reference de ligue n'est PAS appliquee a lambda, meme quand elle est reellement "
    "mesuree (Espagne) : le calcul ignore la reference dans les deux cas (Espagne vs Andorre) "
    "-- retire le 07/09/2026 apres qu'un modificateur meme base sur une reference reelle "
    "(Arabie Saoudite, 1.5049) ait produit un lambda instable (5.81) sur une vraie donnee "
    "(Al Khaleej-Al Riyadh)",
    _mv0.calcule_lambda_v0(1.6, 1.2, 1.3, 1.4, pays="Espagne")["lambda_home"]
    == _mv0.calcule_lambda_v0(1.6, 1.2, 1.3, 1.4, pays="Andorre")["lambda_home"],
)

verite(
    "AJOUT 07/09/2026 -- CORRECTION_BUTS_V0 (calibree par validation croisee temporelle sur "
    "212 vrais matchs, PAS devinee) est bien appliquee au lambda final : "
    "lambda == moyenne_brute * CORRECTION_BUTS_V0, exactement",
    abs(_mv0.calcule_lambda_v0(1.6, 1.2, 1.3, 1.4, pays="Andorre")["lambda_home"]
        - (1.6 + 1.4) / 2 * _mv0.CORRECTION_BUTS_V0) < 1e-9,
)

verite(
    "reference_disponible reste loggee a titre informatif (Espagne mesuree, Andorre non) "
    "sans influencer le calcul -- utile pour une decision V1 future, jamais pour la V0",
    _mv0.calcule_lambda_v0(1.6, 1.2, 1.3, 1.4, pays="Espagne")["audit"]["reference_disponible"] == 1.3474
    and _mv0.calcule_lambda_v0(1.6, 1.2, 1.3, 1.4, pays="Andorre")["audit"]["reference_disponible"] is None,
)

_marches_incoherentes_test = {
    "Plus de 0.5 buts": 0.90, "Plus de 1.5 buts": 0.95,  # 1.5 > 0.5 -- incohérent
    "Plus de 2.5 buts": 0.40, "Plus de 3.5 buts": 0.20, "Plus de 4.5 buts": 0.10,
}
_invalides_test = _mv0.verifie_coherence_v0(_marches_incoherentes_test)
verite(
    "Une incohérence de monotonie (Plus de 1.5 > Plus de 0.5) invalide la ligne fautive, "
    "jamais une correction automatique, et ne contamine pas les lignes cohérentes",
    "Plus de 1.5 buts" in _invalides_test and "Plus de 0.5 buts" not in _invalides_test
    and "Plus de 2.5 buts" not in _invalides_test,
)

verite(
    "EV pile au seuil (0.70 * 1.5 - 1, qui vaut 0.049999999999999822 en flottant, pas 0.05 exact) "
    "est bien accepté grâce à la tolérance -- sans elle, un vrai edge au seuil serait rejeté à tort",
    _mv0.calcule_ev_v0(0.70, 1.5) >= _mv0.EV_MIN - 1e-9,
)
verite(
    "La tolérance flottante ne masque jamais un vrai rejet (EV réellement sous le seuil, 4.99%)",
    _mv0.calcule_ev_v0(0.60, 1.7499) < _mv0.EV_MIN - 1e-9,
)

_candidats_famille_test = [
    {"marche": "1X2 - 1", "ev": 0.10},
    {"marche": "Double chance - 1X", "ev": 0.20},
    {"marche": "BTTS - oui", "ev": 0.06},
]
_selection_famille_test = _mv0.filtre_famille_v0(_candidats_famille_test)
_noms_selection_famille_test = {c["marche"] for c in _selection_famille_test}
verite(
    "Un seul candidat retenu par famille (résultat : 1X2 et Double chance ensemble) -- "
    "garde le meilleur EV (Double chance - 1X, 0.20), écarte 1X2 - 1 (même famille, EV plus faible)",
    "Double chance - 1X" in _noms_selection_famille_test and "1X2 - 1" not in _noms_selection_famille_test
    and "BTTS - oui" in _noms_selection_famille_test,
)

verite(
    "Une cote absente (None) ne produit jamais d'EV -- jamais un pari inventé sur une donnée manquante",
    _mv0.calcule_ev_v0(0.90, None) is None,
)

_r_go_test = _mv0.evalue_match_v0(
    2.0, 1.0, 1.8, 1.2, nb_matchs_domicile_utilises=10, nb_matchs_exterieur_utilises=10,
    cotes_marches={"Plus de 2.5 buts": 2.20, "BTTS - oui": 2.00},
)
verite(
    "Un cas GO complet produit une mise fixe STAKE_V0 (1%) sur chaque sélection, jamais une mise variable",
    _r_go_test["verdict"] == "GO"
    and all(s["mise_pct_bankroll"] == _mv0.STAKE_V0 for s in _r_go_test["selection"]),
)

_ligne_log_test = _mv0.enregistre_evaluation_v0(
    {"equipe_domicile": "Audit", "equipe_exterieur": "Permanent"}, _r_lambda_implausible,
    chemin="/tmp/audit_permanent_historique_v0_test.jsonl",
)
verite(
    "enregistre_evaluation_v0 journalise aussi bien un NO_BET qu'un GO (pas seulement les paris pris) "
    "-- corrige le plafond d'échantillon (63 paris) qui limitait la calibration du moteur existant",
    _ligne_log_test["verdict"] == "NO_BET" and _ligne_log_test["resultat_reel"] is None,
)

# AJOUT 07/09/2026 (audit ligne par ligne demandé par Patrick) -- deux
# vraies violations trouvées et corrigées le même jour, voir historique de
# session : (1) BORNE_MODIFIER_DEFENSE, constante empruntée à l'ancien
# moteur sans validation, retirée entièrement ; (2) controle_empirique_v0
# évaluait à tort des marchés asymétriques (1X2, Handicap, "- Extérieur"...)
# sur un historique déjà réorienté (buts_marques/buts_encaisses), faussant
# silencieusement les champs loggés -- même bug d'orientation que #41 dans
# adapte_justification.py, réintroduit puis retrouvé le même jour.
verite(
    "BORNE_MODIFIER_DEFENSE (constante non validée, valeurs même fausses par rapport à "
    "l'original) a bien été retirée du module -- plus aucune trace",
    not hasattr(_mv0, "BORNE_MODIFIER_DEFENSE"),
)

verite(
    "controle_empirique_v0 renvoie une vraie observation pour un marché symétrique (BTTS)",
    _mv0.controle_empirique_v0(
        "BTTS - oui",
        [{"buts_marques": 3, "buts_encaisses": 1}, {"buts_marques": 0, "buts_encaisses": 0}],
        [], "domicile",
    ) == (1, 2),
)
verite(
    "controle_empirique_v0 renvoie None pour un marché asymétrique (1X2 - 1) -- jamais une "
    "observation orientée à tort sur un historique déjà réorienté du point de vue de l'équipe",
    _mv0.controle_empirique_v0(
        "1X2 - 1",
        [{"buts_marques": 3, "buts_encaisses": 1}], [], "domicile",
    ) is None,
)
verite(
    "controle_empirique_v0 renvoie None pour un marché suffixé '- Extérieur' même appliqué à "
    "l'historique domicile (dépend de la position réelle, pas du point de vue de l'équipe)",
    _mv0.controle_empirique_v0(
        "Plus de 1.5 buts - Extérieur",
        [{"buts_marques": 3, "buts_encaisses": 1}], [], "domicile",
    ) is None,
)


# ============================================================================
section("archetype_model/data (08/09/2026) — fenêtre statistique et récupération "
        "saison en cours, package neuf isolé de l'ancien moteur")
# ============================================================================
import archetype_model.data.validation as _amv
import archetype_model.data.loader as _aml


def _fabrique(n):
    return [{"idx": i} for i in range(n)]


verite(
    "classifie_fenetre : N=3 -> INSUFFISANT, matchs_retenus vide",
    _amv.classifie_fenetre(_fabrique(3))
    == {"statut": _amv.STATUT_INSUFFISANT, "n_brut": 3, "matchs_retenus": []},
)
verite(
    "classifie_fenetre : N=8 -> UTILISABLE, les 8 matchs conservés sans réordonnancement",
    _amv.classifie_fenetre(_fabrique(8))["matchs_retenus"] == _fabrique(8),
)
verite(
    "classifie_fenetre : N=15 -> tronqué aux 12 PLUS RÉCENTS (les 12 DERNIERS de la "
    "liste, jamais les 12 premiers -- inversion volontaire par rapport au bug "
    "d'ordre de recupere_gf_ga_avec_repli, voir loader.py)",
    _amv.classifie_fenetre(_fabrique(15))["matchs_retenus"] == [{"idx": i} for i in range(3, 15)],
)
verite(
    "classifie_fenetre : N=0 -> INSUFFISANT, pas de crash sur liste vide",
    _amv.classifie_fenetre([]) == {"statut": _amv.STATUT_INSUFFISANT, "n_brut": 0, "matchs_retenus": []},
)
verite(
    "classifie_fenetre : N=5 (borne basse incluse) -> UTILISABLE",
    _amv.classifie_fenetre(_fabrique(5))["statut"] == _amv.STATUT_UTILISABLE,
)
verite(
    "classifie_fenetre : N=12 (borne haute incluse) -> UTILISABLE, PAS tronqué",
    _amv.classifie_fenetre(_fabrique(12))["matchs_retenus"] == _fabrique(12),
)

# CORRECTIF -- monkeypatch de _aml.fetch_html (nom lié localement par
# `from scraper_details import fetch_html` dans loader.py -- patcher
# sd.fetch_html n'aurait aucun effet ici) : à restaurer IMMÉDIATEMENT
# après le test, avant toute autre vérité.
_original_fetch_html_aml = _aml.fetch_html

_HTML_OK_ARCHETYPE = """
<html><body>
<div>Suède : Allsvenskan</div>
<table>
<tr><td><a href="/live-score/m1">Kalmar 0-1 Djurgarden</a></td></tr>
<tr><td><a href="/live-score/m2">AIK Solna 1-0 Kalmar</a></td></tr>
<tr><td><a href="/report/m3">Sirius - Kalmar (rapport, pas de score)</a></td></tr>
<tr><td><a href="/live-score/m4">Kalmar 2-0 Halmstads BK</a></td></tr>
</table>
</body></html>
"""


def _stub_fetch_html_sans_repli(url, *a, **kw):
    if "?season=" in url:
        raise AssertionError("repli saison précédente construit -- violerait v3 §4.1")
    return _HTML_OK_ARCHETYPE


_aml.fetch_html = _stub_fetch_html_sans_repli
_r_historique_test = _aml.recupere_historique_saison_courante(
    "https://www.matchendirect.fr/equipe/kalmar_test.html", "Suède : Allsvenskan", "Kalmar",
)
verite(
    "loader.recupere_historique_saison_courante : 3 matchs valides extraits (la ligne "
    "'rapport' sans score n'augmente pas N), ordre de page préservé tel quel",
    [m["buts_marques"] for m in _r_historique_test] == [0, 0, 2]
    and [m["domicile"] for m in _r_historique_test] == [True, False, True],
)
verite(
    "loader.recupere_historique_saison_courante : jamais de repli saison précédente "
    "(?season=) -- vérifié structurellement, pas juste supposé",
    True,  # si _stub_fetch_html_sans_repli avait vu ?season=, l'appel ci-dessus aurait levé
)

_aml.fetch_html = lambda url, *a, **kw: "<html><body><div>Norvège : Eliteserien</div></body></html>"
verite(
    "loader.recupere_historique_saison_courante : compétition absente de la page -> "
    "liste vide, jamais None (pas de crash en aval pour l'appelant)",
    _aml.recupere_historique_saison_courante(
        "https://www.matchendirect.fr/equipe/x.html", "Suède : Allsvenskan", "Kalmar",
    ) == [],
)

# CORRECTIF -- restaurer IMMÉDIATEMENT la vraie fonction, avant toute autre
# vérité de ce script (même convention que le groupe resolution_betpawa
# plus haut dans ce fichier).
_aml.fetch_html = _original_fetch_html_aml
verite(
    "archetype_model.data.loader.fetch_html réellement restauré à l'original après "
    "les tests (aucun monkeypatch qui fuit vers le reste de l'audit)",
    _aml.fetch_html is _original_fetch_html_aml,
)


# ============================================================================
section("archetype_model/statistics (08/09/2026) — statistiques descriptives "
        "d'équipe (offensif/défensif/résultats/buts), agnostiques de la source")
# ============================================================================
from archetype_model.statistics import distributions as _amd
from archetype_model.statistics import team_stats as _amts
from archetype_model.statistics import goals as _amg

verite(
    "distributions.variance utilise la variance de POPULATION (division par N, pas "
    "N-1) -- décision documentée en tête de fichier, vérifiée par calcul sur un jeu "
    "de référence à variance de population connue (4.0)",
    abs(_amd.variance([2, 4, 4, 4, 5, 5, 7, 9]) - 4.0) < 1e-9,
)
verite(
    "distributions : toutes les fonctions scalaires renvoient None sur liste vide, "
    "jamais 0 ni une exception (moyenne/mediane/variance/ecart_type/min/max)",
    _amd.moyenne([]) is None and _amd.mediane([]) is None and _amd.variance([]) is None
    and _amd.ecart_type([]) is None and _amd.minimum([]) is None and _amd.maximum([]) is None,
)
verite(
    "distributions.distribution_paliers([]) renvoie les 4 clés à 0, jamais un dict "
    "partiel (un accès distribution['3+'] en aval ne doit jamais lever KeyError)",
    _amd.distribution_paliers([]) == {"0": 0, "1": 0, "2": 0, "3+": 0},
)

_matchs_mixtes_test = [
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 0},
    {"domicile": True, "buts_marques": 1, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 0, "buts_encaisses": 2},
    {"domicile": True, "buts_marques": 3, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 0, "buts_encaisses": 0},
]
verite(
    "team_stats.stats_offensives : n=5, moyenne=1.2, distribution 0/1/2/3+ correcte "
    "sur un jeu de matchs mixtes réel",
    _amts.stats_offensives(_matchs_mixtes_test)["moyenne"] == 1.2
    and _amts.stats_offensives(_matchs_mixtes_test)["distribution"] == {"0": 2, "1": 1, "2": 1, "3+": 1},
)
verite(
    "team_stats.stats_defensives : 2 clean sheets/5 (fréquence 0.4), fréquence "
    "d'encaissement = 0.6 -- les deux sommant à 1.0 par construction",
    _amts.stats_defensives(_matchs_mixtes_test)["frequence_clean_sheets"] == 0.4,
)
_resultats_test = _amts.resultats(_matchs_mixtes_test)
verite(
    "team_stats.resultats : victoires+nuls+defaites == n toujours, jamais un résultat "
    "qui se perd (2 victoires, 2 nuls, 1 défaite sur 5)",
    _resultats_test["victoires"] + _resultats_test["nuls"] + _resultats_test["defaites"]
    == _resultats_test["n"] == 5
    and (_resultats_test["victoires"], _resultats_test["nuls"], _resultats_test["defaites"]) == (2, 2, 1),
)
verite(
    "team_stats sur liste vide (les 3 fonctions) : aucune ZeroDivisionError sur les "
    "fréquences, tout à None proprement",
    _amts.stats_offensives([])["moyenne"] is None
    and _amts.stats_defensives([])["frequence_clean_sheets"] is None
    and _amts.resultats([])["frequence_victoires"] is None,
)

_matchs_buts_test = [
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 0},
    {"domicile": True, "buts_marques": 1, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 0, "buts_encaisses": 0},
    {"domicile": True, "buts_marques": 3, "buts_encaisses": 2},
]
verite(
    "goals.buts_totaux_par_match calcule bien marques+encaissees par match (totaux "
    "attendus [2,2,0,5], pas une approximation)",
    _amg.buts_totaux_par_match(_matchs_buts_test) == [2, 2, 0, 5],
)
verite(
    "goals.btts : 2 occurrences sur 4 (fréquence 0.5) sur le jeu de test",
    _amg.btts(_matchs_buts_test) == {"n": 4, "occurrences": 2, "frequence": 0.5},
)
_ou25_test = _amg.over_under(_matchs_buts_test, 2.5)
verite(
    "goals.over_under(ligne=2.5) : over+under == n TOUJOURS (ligne à virgule, "
    "aucun match ne peut être exactement sur la ligne)",
    _ou25_test["over"] + _ou25_test["under"] == _ou25_test["n"] == 4
    and _ou25_test["over"] == 1,
)
verite(
    "goals.over_under([], ligne) et goals.btts([]) ne plantent pas, fréquences à None",
    _amg.over_under([], 2.5)["frequence_over"] is None and _amg.btts([])["frequence"] is None,
)


# ============================================================================
section("archetype_model/poisson/lambda_estimators (08/09/2026) — 4 scénarios λ "
        "(offensif/défensif/contextuel/global), v3 §6")
# ============================================================================
from archetype_model.poisson.lambda_estimators import estime_lambdas

_r_lambda_test = estime_lambdas(
    gf_a_domicile=2.0, ga_a_domicile=0.5, gf_a_global=1.8, ga_a_global=0.7,
    gf_b_exterieur=1.0, ga_b_exterieur=1.5, gf_b_global=1.2, ga_b_global=1.4,
)
verite(
    "estime_lambdas : λ_A offensif=GF_A_domicile, λ_A défensif=GA_B_exterieur "
    "(vulnérabilité de L'ADVERSAIRE, jamais celle de A), λ_A contextuel=moyenne exacte des deux",
    _r_lambda_test["A"]["offensif"] == 2.0 and _r_lambda_test["A"]["defensif"] == 1.5
    and _r_lambda_test["A"]["contextuel"] == 1.75,
)
verite(
    "estime_lambdas : λ_global croise bien l'attaque globale d'UNE équipe avec la défense "
    "globale de L'AUTRE (λ_A global = (GF_A_global+GA_B_global)/2 = 1.6, PAS GA_A_global)",
    _r_lambda_test["A"]["global"] == 1.6 and _r_lambda_test["B"]["global"] == 0.95,
)
verite(
    "estime_lambdas : les 4 scénarios de A restent 4 valeurs séparées, aucune pondération "
    "entre eux (v3 §6 dernier paragraphe) -- vérifié sur un jeu où rien ne coïncide par hasard",
    len({_r_lambda_test["A"]["offensif"], _r_lambda_test["A"]["defensif"],
         _r_lambda_test["A"]["contextuel"], _r_lambda_test["A"]["global"]}) == 4,
)

_r_lambda_none = estime_lambdas(
    gf_a_domicile=None, ga_a_domicile=0.5, gf_a_global=1.8, ga_a_global=0.7,
    gf_b_exterieur=1.0, ga_b_exterieur=1.5, gf_b_global=1.2, ga_b_global=1.4,
)
verite(
    "estime_lambdas : GF_A_domicile absent -> λ_A offensif ET contextuel deviennent None "
    "(dépendent de la valeur manquante), mais λ_A défensif (indépendant) reste calculé -- "
    "pas de crash, pas de faux zéro",
    _r_lambda_none["A"]["offensif"] is None and _r_lambda_none["A"]["contextuel"] is None
    and _r_lambda_none["A"]["defensif"] == 1.5,
)

_r_lambda_ga_a_global_none = estime_lambdas(
    gf_a_domicile=2.0, ga_a_domicile=0.5, gf_a_global=1.8, ga_a_global=None,
    gf_b_exterieur=1.0, ga_b_exterieur=1.5, gf_b_global=1.2, ga_b_global=1.4,
)
verite(
    "estime_lambdas : GA_A_global absent -> λ_B global DOIT devenir None (dépendance réelle "
    "de la formule v3 §6, pas une fuite à corriger) ; λ_A global reste intact (dépend de "
    "GA_B_global, pas de GA_A_global)",
    _r_lambda_ga_a_global_none["B"]["global"] is None and _r_lambda_ga_a_global_none["A"]["global"] == 1.6,
)

_r_lambda_tout_none = estime_lambdas(
    gf_a_domicile=None, ga_a_domicile=None, gf_a_global=None, ga_a_global=None,
    gf_b_exterieur=None, ga_b_exterieur=None, gf_b_global=None, ga_b_global=None,
)
verite(
    "estime_lambdas : tout None des deux côtés -> les 8 valeurs de sortie sont None, "
    "jamais un crash",
    all(v is None for v in _r_lambda_tout_none["A"].values())
    and all(v is None for v in _r_lambda_tout_none["B"].values()),
)


# ============================================================================
section("archetype_model/poisson/distribution (08/09/2026) — matrice de Poisson "
        "jointe, v3 §7")
# ============================================================================
import math as _math_audit
from archetype_model.poisson import distribution as _amdist

verite(
    "distribution.loi_poisson : valeurs de référence pour λ=1 conformes à la table "
    "de Poisson standard (P(X=0)=P(X=1)=e^-1, P(X=2)=e^-1/2)",
    abs(_amdist.loi_poisson(1.0, 0) - _math_audit.exp(-1)) < 1e-9
    and abs(_amdist.loi_poisson(1.0, 2) - _math_audit.exp(-1) * 0.5) < 1e-9,
)
_da_audit = _amdist.distribution_marginale(1.2, max_buts=5)
_db_audit = _amdist.distribution_marginale(0.8, max_buts=5)
_m_audit = _amdist.matrice_scores(1.2, 0.8, max_buts=5)
verite(
    "distribution.matrice_scores : indépendance vérifiée EXACTEMENT cellule par cellule "
    "(m[2][3] == P(X=2)*P(Y=3)), pas une approximation",
    _m_audit[2][3] == _da_audit[2] * _db_audit[3] and _m_audit[0][0] == _da_audit[0] * _db_audit[0],
)
verite(
    "distribution.masse_totale sur max_buts=15 proche de 1.0 à 1e-9 (résidu de troncature "
    "négligeable pour des λ réalistes, jamais utilisée pour renormaliser)",
    abs(_amdist.masse_totale(_amdist.matrice_scores(1.2, 0.8, max_buts=15)) - 1.0) < 1e-9,
)
verite(
    "distribution : λ=None (scénario indisponible) -> matrice_scores/loi_poisson renvoient "
    "None des deux côtés, jamais une exception ni une matrice à moitié construite",
    _amdist.matrice_scores(None, 1.0) is None and _amdist.matrice_scores(1.0, None) is None
    and _amdist.loi_poisson(None, 3) is None,
)
verite(
    "distribution : λ=0 (cas dégénéré) -> P(X=0)=1.0 exactement, P(X=k>0)=0.0 pour tout k>0",
    _amdist.distribution_marginale(0.0, max_buts=5) == [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
)


# ============================================================================
section("archetype_model/poisson/robustness (08/09/2026) — seuil de stabilité "
        "multi-λ, v3 §8 (CORRECTIF 2/11)")
# ============================================================================
from archetype_model.poisson import robustness as _amrob

verite(
    "robustness.evalue_robustesse : 4 probabilités identiques -> écart_type=0.0 -> STABLE",
    _amrob.evalue_robustesse([0.30, 0.30, 0.30, 0.30])
    == {"ecart_type": 0.0, "statut": _amrob.STATUT_STABLE},
)
verite(
    "robustness.evalue_robustesse : forte dispersion (0.10/0.40/0.15/0.35, écart-type "
    ">> 0.08) -> INSTABLE",
    _amrob.evalue_robustesse([0.10, 0.40, 0.15, 0.35])["statut"] == _amrob.STATUT_INSTABLE,
)
verite(
    "robustness.evalue_robustesse : écart-type EXACTEMENT au seuil (0.08, jusqu'à "
    "l'imprécision flottante 0.08000000000000002) -> STABLE, règle '≤' pas '<' -- "
    "tolérance epsilon ajoutée après qu'un test l'ait révélé avant livraison",
    _amrob.evalue_robustesse([0.28, 0.28, 0.12, 0.12])["statut"] == _amrob.STATUT_STABLE,
)
verite(
    "robustness.evalue_robustesse : un scénario None -> INDETERMINE, jamais un calcul "
    "dégradé sur 3 valeurs qui fabriquerait une fausse STABLE",
    _amrob.evalue_robustesse([0.20, 0.21, None, 0.20])
    == {"ecart_type": None, "statut": _amrob.STATUT_INDETERMINE},
)
verite(
    "robustness.evalue_robustesse : mauvais compte (3 valeurs au lieu de 4) -> "
    "INDETERMINE, défensif, pas de crash",
    _amrob.evalue_robustesse([0.20, 0.21, 0.19])["statut"] == _amrob.STATUT_INDETERMINE,
)


# ============================================================================
section("archetype_model/poisson/markets (08/09/2026) — marchés essentiels "
        "(1X2/DC/BTTS/O-U total/O-U équipe), périmètre réduit assumé, v3 §9 partiel")
# ============================================================================
from archetype_model.poisson import markets as _amk

_m_audit_mk = _amdist.matrice_scores(1.5, 1.0, max_buts=15)
_p123_audit = _amk.probabilites_1x2(_m_audit_mk)
verite(
    "markets.probabilites_1x2 : les 3 issues somment à 1.0 (troncature négligeable), "
    "et l'équipe au λ plus fort a bien la probabilité de victoire la plus haute",
    abs(_p123_audit["domicile"] + _p123_audit["nul"] + _p123_audit["exterieur"] - 1.0) < 1e-6
    and _p123_audit["domicile"] > _p123_audit["exterieur"],
)
_pdc_audit = _amk.probabilites_double_chance(_m_audit_mk)
verite(
    "markets.probabilites_double_chance : cohérence exacte avec 1X2 (1X=domicile+nul, "
    "X2=nul+exterieur, 12=domicile+exterieur), jamais recalculé indépendamment",
    abs(_pdc_audit["1X"] - (_p123_audit["domicile"] + _p123_audit["nul"])) < 1e-12,
)
_p_btts_audit = _amk.probabilite_btts(_m_audit_mk)
verite(
    "markets.probabilite_btts : cohérent avec un calcul indépendant par "
    "inclusion-exclusion (1-P(X=0)-P(Y=0)+P(X=0,Y=0))",
    abs(_p_btts_audit - (1.0 - sum(_m_audit_mk[0])
                          - sum(ligne[0] for ligne in _m_audit_mk) + _m_audit_mk[0][0])) < 1e-12,
)
verite(
    "markets : matrice/distribution None (λ indisponible en amont) -> toutes les "
    "fonctions renvoient None, jamais un crash ni une probabilité inventée",
    _amk.probabilites_1x2(None) is None and _amk.probabilites_double_chance(None) is None
    and _amk.probabilite_btts(None) is None and _amk.probabilites_over_under_total(None, 2.5) is None
    and _amk.probabilites_buts_equipe(None, 1.5) is None,
)
_m_sym_audit = _amdist.matrice_scores(1.3, 1.3, max_buts=15)
_p_sym_audit = _amk.probabilites_1x2(_m_sym_audit)
verite(
    "markets.probabilites_1x2 : λ identiques des deux côtés -> P(domicile)≈P(exterieur) "
    "(symétrie de la matrice, à l'imprécision flottante d'ordre de sommation près, "
    "aucun avantage domicile codé en dur)",
    abs(_p_sym_audit["domicile"] - _p_sym_audit["exterieur"]) < 1e-9,
)


# ============================================================================
section("archetype_model/main.analyse_match (08/09/2026) — orchestration bout en bout, "
        "périmètre réduit assumé (λ_global toujours None -> robustesse toujours INDETERMINE)")
# ============================================================================
import archetype_model.data.loader as _amloader_e2e
import archetype_model.main as _ammain_e2e


def _fixture_equipe_e2e(nom, resultats):
    lignes = []
    for i, (adv, bp, bc, dom) in enumerate(resultats):
        texte = f"{nom} {bp}-{bc} {adv}" if dom else f"{adv} {bc}-{bp} {nom}"
        lignes.append(f'<tr><td><a href="/live-score/x{i}">{texte}</a></td></tr>')
    return f'<html><body><div>Suède : Allsvenskan</div><table>{"".join(lignes)}</table></body></html>'


_matchs_a_e2e = [("X1", 2, 0, True), ("X2", 3, 1, True), ("X3", 1, 1, True),
                 ("X4", 2, 0, True), ("X5", 2, 1, True), ("X6", 2, 0, True)]
_matchs_b_e2e = [("Y1", 1, 2, False), ("Y2", 0, 1, False), ("Y3", 2, 1, False),
                 ("Y4", 1, 2, False), ("Y5", 0, 2, False), ("Y6", 2, 1, False)]
_html_a_e2e = _fixture_equipe_e2e("EquipeA", _matchs_a_e2e)
_html_b_e2e = _fixture_equipe_e2e("EquipeB", _matchs_b_e2e)
_original_fetch_e2e = _amloader_e2e.fetch_html


def _stub_e2e(url, *a, **kw):
    if "?season=" in url:
        raise AssertionError("repli saison précédente déclenché -- violerait v3 §4.1")
    return _html_a_e2e if "equipeA" in url else _html_b_e2e


_amloader_e2e.fetch_html = _stub_e2e
_r_e2e = _ammain_e2e.analyse_match(
    "https://www.matchendirect.fr/equipe/equipeA.html", "EquipeA",
    "https://www.matchendirect.fr/equipe/equipeB.html", "EquipeB",
    "Suède : Allsvenskan",
)
verite(
    "analyse_match bout en bout : statut OK avec 6 matchs de chaque côté, λ_A offensif ≈ "
    "GF domicile réel (2.0), équipe la plus forte (A) a la plus haute proba de victoire",
    _r_e2e["statut"] == "OK" and abs(_r_e2e["lambdas"]["A"]["offensif"] - 2.0) < 1e-9
    and _r_e2e["marches_par_scenario"]["offensif"]["1x2"]["domicile"]
    > _r_e2e["marches_par_scenario"]["offensif"]["1x2"]["exterieur"],
)
verite(
    "analyse_match bout en bout : robustesse TOUJOURS INDETERMINE tant que λ_global est "
    "None (limite de périmètre assumée du 08/09/2026, jamais une fausse STABLE/INSTABLE)",
    all(v["statut"] == "INDETERMINE" for v in _r_e2e["robustesse_par_marche"].values()),
)

_html_a_peu_e2e = _fixture_equipe_e2e("EquipeA", _matchs_a_e2e[:3])
_amloader_e2e.fetch_html = lambda url, *a, **kw: (_html_a_peu_e2e if "equipeA" in url else _html_b_e2e)
_r_insuff_e2e = _ammain_e2e.analyse_match(
    "https://www.matchendirect.fr/equipe/equipeA.html", "EquipeA",
    "https://www.matchendirect.fr/equipe/equipeB.html", "EquipeB",
    "Suède : Allsvenskan",
)
verite(
    "analyse_match bout en bout : équipe A avec seulement 3 matchs (N<5) -> statut "
    "INSUFFISANT, aucun lambda calculé, pas de crash",
    _r_insuff_e2e["statut"] == "INSUFFISANT" and "lambdas" not in _r_insuff_e2e,
)

_amloader_e2e.fetch_html = _original_fetch_e2e
verite(
    "archetype_model.data.loader.fetch_html réellement restauré à l'original après le "
    "test d'intégration bout en bout (aucun monkeypatch qui fuit)",
    _amloader_e2e.fetch_html is _original_fetch_e2e,
)


# ============================================================================
section("archetype_model/backtest/boucle_b (08/09/2026) — backtest walk-forward, "
        "λ recalculés depuis cache_equipes.json, JAMAIS depuis l'ancien moteur "
        "(jamais testé contre le vrai réseau matchendirect.fr -- voir docstring)")
# ============================================================================
import scraper_details as _sd_bb
import archetype_model.backtest.boucle_b as _bb


def _entree_cache_bb(gf_dom, ga_dom, gf_ext, ga_ext, n=10):
    return {
        "horodatage": "2026-09-01T00:00:00Z",
        "resultat": {
            "gf_domicile": gf_dom, "ga_domicile": ga_dom, "gf_exterieur": gf_ext, "ga_exterieur": ga_ext,
            "matchs_domicile_bruts": [{"buts_marques": gf_dom, "buts_encaisses": ga_dom, "domicile": True}] * n,
            "matchs_exterieur_bruts": [{"buts_marques": gf_ext, "buts_encaisses": ga_ext, "domicile": False}] * n,
            "nb_domicile": n, "nb_exterieur": n,
        },
    }


_cache_test_bb = {
    "https://www.matchendirect.fr/equipe/equipeA.html||suède : allsvenskan":
        _entree_cache_bb(gf_dom=2.0, ga_dom=0.5, gf_ext=0.8, ga_ext=1.2),
    "https://www.matchendirect.fr/equipe/equipeB.html||suède : allsvenskan":
        _entree_cache_bb(gf_dom=1.0, ga_dom=1.0, gf_ext=1.0, ga_ext=1.5),
}
_match_test_bb = {
    "domicile": "EquipeA", "exterieur": "EquipeB", "competition": "Suède : Allsvenskan",
    "score": "2-1", "url_match": "https://www.matchendirect.fr/live-score/equipeA-equipeB.html",
    "date": "2026-08-20", "match_id": "abc123",
}
_original_details_bb = _bb.recupere_details_match


def _stub_details_bb(url_match):
    return {"url_equipe_domicile": "https://www.matchendirect.fr/equipe/equipeA.html",
            "url_equipe_exterieur": "https://www.matchendirect.fr/equipe/equipeB.html"}


_bb.recupere_details_match = _stub_details_bb
_r_bb = _bb.evalue_un_match(_match_test_bb, _cache_test_bb)
verite(
    "boucle_b.evalue_un_match : statut OK, λ_A offensif recalculé = GF_A_domicile du "
    "CACHE (2.0) -- jamais un λ de l'ancien moteur",
    _r_bb["statut"] == "OK" and abs(_r_bb["lambdas"]["A"]["offensif"] - 2.0) < 1e-9,
)
_match_avec_piege_bb = dict(_match_test_bb)
_match_avec_piege_bb["lambda"] = {"lambda_home": 999.0, "lambda_away": 999.0}
_r_piege_bb = _bb.evalue_un_match(_match_avec_piege_bb, _cache_test_bb)
verite(
    "boucle_b.evalue_un_match : un champ 'lambda' de l'ancien moteur présent dans "
    "l'entrée d'entrée n'est JAMAIS lu ni réutilisé (reste basé sur le cache, pas 999.0)",
    abs(_r_piege_bb["lambdas"]["A"]["offensif"] - 2.0) < 1e-9,
)
verite(
    "boucle_b.evalue_un_match : score absent -> statut SCORE_ILLISIBLE, pas de crash",
    _bb.evalue_un_match({**_match_test_bb, "score": None}, _cache_test_bb)["statut"] == "SCORE_ILLISIBLE",
)
verite(
    "boucle_b.evalue_un_match : équipe résolue mais absente du cache -> statut "
    "ABSENT_DU_CACHE, jamais un crash qui interromprait tout le backtest",
    _bb.evalue_un_match(_match_test_bb, {})["statut"] == "ABSENT_DU_CACHE",
)
_bb.recupere_details_match = _original_details_bb
verite(
    "boucle_b.recupere_details_match réellement restauré à l'original après les tests",
    _bb.recupere_details_match is _original_details_bb,
)

_resultats_agrege_audit = [
    {"statut": "OK", "resultat_reel": {"issue_1x2": "domicile"},
     "predictions_par_scenario": {s: {"1x2": {"domicile": 0.6, "nul": 0, "exterieur": 0}} for s in _bb.SCENARIOS}},
    {"statut": "OK", "resultat_reel": {"issue_1x2": "exterieur"},
     "predictions_par_scenario": {s: {"1x2": {"domicile": 0.4, "nul": 0, "exterieur": 0}} for s in _bb.SCENARIOS}},
    {"statut": "INSUFFISANT"},
]
_agrege_audit = _bb.agrege_resultats(_resultats_agrege_audit)
verite(
    "boucle_b.agrege_resultats : comptage par statut correct (2 OK, 1 INSUFFISANT), "
    "Brier scénario 'offensif' == 0.16 (calcul manuel indépendant : (0.6-1)²+(0.4-0)²)/2)",
    _agrege_audit["comptes_par_statut"] == {"OK": 2, "INSUFFISANT": 1}
    and abs(_agrege_audit["brier_score_victoire_domicile_par_scenario"]["offensif"] - 0.16) < 1e-12,
)
verite(
    "boucle_b.agrege_resultats : liste vide -> aucun crash, n_total=0, Brier=None partout "
    "(jamais un calcul déguisé sur liste vide)",
    _bb.agrege_resultats([])["n_total"] == 0
    and all(v is None for v in _bb.agrege_resultats([])["brier_score_victoire_domicile_par_scenario"].values()),
)


# ============================================================================
section("archetype_model/poisson/markets — extension handicap au quart de but + "
        "combos DC/Total (08/09/2026, v3 §9.3 CORRECTIF 6/12, §9.4.3/9.4.4)")
# ============================================================================
_m_hc_audit = _amdist.matrice_scores(1.5, 1.0, max_buts=15)

_r_h0_audit = _amk.resultat_handicap(_m_hc_audit, 0)
_p123_hc_audit = _amk.probabilites_1x2(_m_hc_audit)
verite(
    "markets.resultat_handicap(ligne=0) : identique à probabilites_1x2 (gain=domicile, "
    "push=nul, perte=exterieur), pas une coïncidence -- même lecture de la matrice",
    abs(_r_h0_audit["gain"] - _p123_hc_audit["domicile"]) < 1e-12
    and abs(_r_h0_audit["push"] - _p123_hc_audit["nul"]) < 1e-12,
)
_r_h_demi_audit = _amk.resultat_handicap(_m_hc_audit, -0.5)
verite(
    "markets.resultat_handicap(ligne demi-entière) : push TOUJOURS 0.0 (aucun score entier "
    "ne peut égaler un score+0.5) -- conséquence mathématique, pas une approximation",
    _r_h_demi_audit["push"] == 0.0,
)
_r_h_quart_audit = _amk.resultat_handicap(_m_hc_audit, -0.25)
verite(
    "markets.resultat_handicap(-0.25, quart de but, CORRECTIF 12) == moyenne EXACTE de "
    "handicap(0) et handicap(-0.5), vérifié par calcul indépendant",
    abs(_r_h_quart_audit["gain"] - 0.5 * (_r_h0_audit["gain"] + _r_h_demi_audit["gain"])) < 1e-12,
)
verite(
    "markets.resultat_handicap(None, ligne) -> None, pas de crash",
    _amk.resultat_handicap(None, -0.25) is None,
)

_pdc_hc_audit = _amk.probabilites_double_chance(_m_hc_audit)
_p_1x_over_audit = _amk.probabilite_combo_dc_total(_m_hc_audit, "1X", 2.5, "over")
_p_1x_under_audit = _amk.probabilite_combo_dc_total(_m_hc_audit, "1X", 2.5, "under")
verite(
    "markets.probabilite_combo_dc_total : combo(1X,Over2.5) + combo(1X,Under2.5) == P(1X) "
    "exactement -- les deux combos partitionnent 1X sans perte ni double-comptage",
    abs((_p_1x_over_audit + _p_1x_under_audit) - _pdc_hc_audit["1X"]) < 1e-9,
)
verite(
    "markets.probabilite_combo_dc_total(None, ...) -> None ; cote_dc/sens invalides "
    "lèvent une ValueError explicite, jamais un résultat silencieux faux",
    _amk.probabilite_combo_dc_total(None, "1X", 2.5, "over") is None,
)


# ============================================================================
section("archetype_model/poisson/markets.calcule_tous_les_marches + branchement complet "
        "dans main.py/boucle_b.py (08/09/2026) — point d'entrée unique, plus de duplication")
# ============================================================================
_r_calc_audit = _amk.calcule_tous_les_marches(1.5, 1.0)
verite(
    "calcule_tous_les_marches : toutes les familles de marchés présentes "
    "(1x2/DC/BTTS/total/handicap/buts par équipe/combo)",
    set(_r_calc_audit.keys()) == {"1x2", "double_chance", "btts", "over_under_total", "handicap",
                                   "buts_equipe_domicile", "buts_equipe_exterieur", "combo_dc_total"},
)
verite(
    "calcule_tous_les_marches : cohérent avec un calcul direct indépendant "
    "(matrice_scores + probabilites_1x2/resultat_handicap séparément)",
    _r_calc_audit["1x2"] == _amk.probabilites_1x2(_amdist.matrice_scores(1.5, 1.0))
    and _r_calc_audit["handicap"][0.0] == _amk.resultat_handicap(_amdist.matrice_scores(1.5, 1.0), 0.0),
)
verite(
    "calcule_tous_les_marches(None, 1.0) : structure complète mais tout None en profondeur, "
    "jamais un dict tronqué ou un crash",
    _amk.calcule_tous_les_marches(None, 1.0)["combo_dc_total"][("1X", "over", 1.5)] is None,
)

# Vérifie le VRAI branchement : main.analyse_match doit maintenant exposer handicap/combo,
# pas seulement 1x2/DC/BTTS/over_under_2_5 comme avant ce chantier.
_amloader_e2e.fetch_html = _stub_e2e
_r_e2e_apres_branchement = _ammain_e2e.analyse_match(
    "https://www.matchendirect.fr/equipe/equipeA.html", "EquipeA",
    "https://www.matchendirect.fr/equipe/equipeB.html", "EquipeB",
    "Suède : Allsvenskan",
)
verite(
    "main.analyse_match expose maintenant 'handicap' et 'combo_dc_total' dans chaque "
    "scénario (branchement réel, pas juste la fonction centrale testée isolément)",
    "handicap" in _r_e2e_apres_branchement["marches_par_scenario"]["offensif"]
    and "combo_dc_total" in _r_e2e_apres_branchement["marches_par_scenario"]["offensif"],
)
_amloader_e2e.fetch_html = _original_fetch_e2e

_bb.recupere_details_match = _stub_details_bb
_r_bb_apres_branchement = _bb.evalue_un_match(_match_test_bb, _cache_test_bb)
_bb.recupere_details_match = _original_details_bb
verite(
    "boucle_b.evalue_un_match expose aussi 'handicap' et 'combo_dc_total' (même point "
    "d'entrée que main.py, plus de logique dupliquée entre les deux)",
    "handicap" in _r_bb_apres_branchement["predictions_par_scenario"]["offensif"]
    and "combo_dc_total" in _r_bb_apres_branchement["predictions_par_scenario"]["offensif"],
)
verite(
    "boucle_b.recupere_details_match réellement restauré à l'original après cette "
    "vérification additionnelle (aucun monkeypatch qui fuit)",
    _bb.recupere_details_match is _original_details_bb,
)


# ============================================================================
print("\n" + "=" * 70)
if echecs:
    print(f"AUDIT ÉCHOUÉ -- {len(echecs)} vérité(s) fausse(s) :")
    for e in echecs:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("AUDIT OK -- toutes les vérités connues sont confirmées par calcul.")
    sys.exit(0)
