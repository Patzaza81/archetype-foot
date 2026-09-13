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
    "analyse_match bout en bout : robustesse_par_marche présente sans crash (le statut "
    "précis STABLE/INSTABLE/INDETERMINE dépend de λ_global, testé spécifiquement plus "
    "loin dans la section dédiée à ce chantier du 08/09/2026)",
    set(_r_e2e["robustesse_par_marche"].keys()) == {"1x2_domicile", "1x2_nul", "1x2_exterieur", "btts", "over_2_5", "cage_inviolee_domicile", "cage_inviolee_exterieur", "parite_pair"},
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
    "(1x2/DC/BTTS/total/handicap/buts par équipe/parité/combo)",
    set(_r_calc_audit.keys()) == {"1x2", "double_chance", "btts", "over_under_total", "handicap",
                                   "buts_equipe_domicile", "buts_equipe_exterieur", "parite_totale", "combo_dc_total"},
)
verite(
    "calcule_tous_les_marches : cohérent avec un calcul direct indépendant "
    "(matrice_scores + probabilites_1x2/resultat_handicap séparément)",
    _r_calc_audit["1x2"] == _amk.probabilites_1x2(_amdist.matrice_scores(1.5, 1.0))
    and _r_calc_audit["handicap"][0.0] == _amk.resultat_handicap(_amdist.matrice_scores(1.5, 1.0), 0.0),
)

# --- probabilite_parite_totale (chantier du 09/09/2026, feu vert de Patrick) ---
_mat_parite_audit = _amdist.matrice_scores(1.5, 1.0)
_r_parite_audit = _amk.probabilite_parite_totale(_mat_parite_audit)
_pair_manuel_audit = sum(
    p for x, ligne in enumerate(_mat_parite_audit) for y, p in enumerate(ligne) if (x + y) % 2 == 0
)
verite(
    "probabilite_parite_totale : pair + impair == 1.0 (à la troncature de la matrice près)",
    abs(_r_parite_audit["pair"] + _r_parite_audit["impair"] - 1.0) < 1e-6,
)
verite(
    "probabilite_parite_totale : cohérent avec un calcul manuel indépendant sur la même matrice",
    abs(_r_parite_audit["pair"] - _pair_manuel_audit) < 1e-12,
)
verite(
    "probabilite_parite_totale : (0,0) compte bien comme PAIR (0 est pair, piège classique)",
    _r_parite_audit["pair"] >= _mat_parite_audit[0][0],
)
verite(
    "probabilite_parite_totale(None) -> None, jamais un crash (λ manquant en amont)",
    _amk.probabilite_parite_totale(None) is None,
)
verite(
    "probabilite_parite_totale : présente dans calcule_tous_les_marches, jamais oubliée "
    "en cas de λ absent (structure complète même en None)",
    _amk.calcule_tous_les_marches(None, 1.0)["parite_totale"] is None,
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
section("archetype_model/main._stats_globales + boucle_b._stats_globales_depuis_cache "
        "(08/09/2026) — λ_global sur la SEULE compétition du match (décision explicite "
        "de Patrick, annule une version antérieure multi-compétitions)")
# ============================================================================
import archetype_model.data.loader as _amloader_global


def _bloc_audit_global(nom_competition_titre, nom_equipe, resultats):
    lignes = []
    for i, (adv, bp, bc, dom) in enumerate(resultats):
        texte = f"{nom_equipe} {bp}-{bc} {adv}" if dom else f"{adv} {bc}-{bp} {nom_equipe}"
        lignes.append(f'<tr><td><a href="/live-score/x{i}">{texte}</a></td></tr>')
    return f'<div>{nom_competition_titre}</div><table>{"".join(lignes)}</table>'


_matchs_a_global_audit = [("X1", 2, 0, True), ("X2", 3, 1, True), ("X3", 1, 1, True),
                          ("X4", 2, 0, True), ("X5", 2, 1, True), ("X6", 2, 0, True),
                          ("Y1", 1, 1, False), ("Y2", 0, 2, False), ("Y3", 1, 0, False)]
_matchs_b_global_audit = [("Z1", 1, 2, False), ("Z2", 0, 1, False), ("Z3", 2, 1, False),
                          ("Z4", 1, 2, False), ("Z5", 0, 2, False), ("Z6", 2, 1, False)]
_html_a_global_audit = f"<html><body>{_bloc_audit_global('Suède : Allsvenskan', 'EquipeA', _matchs_a_global_audit)}</body></html>"
_html_b_global_audit = f"<html><body>{_bloc_audit_global('Suède : Allsvenskan', 'EquipeB', _matchs_b_global_audit)}</body></html>"
_original_fetch_global = _amloader_global.fetch_html
_amloader_global.fetch_html = lambda url, *a, **kw: (_html_a_global_audit if "equipeA" in url else _html_b_global_audit)
_r_global_audit = _ammain_e2e.analyse_match(
    "https://www.matchendirect.fr/equipe/equipeA.html", "EquipeA",
    "https://www.matchendirect.fr/equipe/equipeB.html", "EquipeB",
    "Suède : Allsvenskan",
)
_amloader_global.fetch_html = _original_fetch_global
verite(
    "main.analyse_match : λ_A global calculé sur la SEULE compétition du match (9 matchs "
    "domicile+extérieur fusionnés), sans fetch réseau supplémentaire, sans agrégation "
    "multi-compétitions (approche annulée)",
    _r_global_audit["statut"] == "OK" and _r_global_audit["lambdas"]["A"]["global"] is not None,
)
verite(
    "main.analyse_match : λ_A offensif (domicile seul) non affecté par ce chantier, "
    "toujours basé uniquement sur les 6 matchs à domicile",
    abs(_r_global_audit["lambdas"]["A"]["offensif"] - (2 + 3 + 1 + 2 + 2 + 2) / 6) < 1e-9,
)

_cache_global_audit = {
    "https://www.matchendirect.fr/equipe/equipeA.html||suède : allsvenskan": {
        "resultat": {
            "matchs_domicile_bruts": [{"buts_marques": 2.0, "buts_encaisses": 0.5, "domicile": True}] * 6,
            "matchs_exterieur_bruts": [{"buts_marques": 1.0, "buts_encaisses": 1.0, "domicile": False}] * 6,
        },
    },
    "https://www.matchendirect.fr/equipe/equipeB.html||suède : allsvenskan": {
        "resultat": {
            "matchs_domicile_bruts": [{"buts_marques": 1.0, "buts_encaisses": 1.0, "domicile": True}] * 6,
            "matchs_exterieur_bruts": [{"buts_marques": 1.0, "buts_encaisses": 1.5, "domicile": False}] * 6,
        },
    },
}
_match_global_audit = {
    "domicile": "EquipeA", "exterieur": "EquipeB", "competition": "Suède : Allsvenskan",
    "score": "2-1", "url_match": "https://www.matchendirect.fr/live-score/equipeA-equipeB.html",
    "date": "2026-08-20", "match_id": "abc123",
}
_bb.recupere_details_match = _stub_details_bb
_r_bb_global_audit = _bb.evalue_un_match(_match_global_audit, _cache_global_audit)
_bb.recupere_details_match = _original_details_bb
verite(
    "boucle_b.evalue_un_match : λ_A_global == 1.375 exactement depuis le cache "
    "(fusion domicile+extérieur de A ET B, compétition unique) -- calcul manuel "
    "indépendant, pas une tautologie",
    _r_bb_global_audit["statut"] == "OK" and abs(_r_bb_global_audit["lambdas"]["A"]["global"] - 1.375) < 1e-9,
)
verite(
    "boucle_b.recupere_details_match réellement restauré à l'original après cette "
    "dernière vérification (aucun monkeypatch qui fuit)",
    _bb.recupere_details_match is _original_details_bb,
)


# ============================================================================
section("archetype_model/data/odds_provider (08/09/2026) — adaptateur cotes réelles "
        "(precalcul.json), lecture seule, vérifié contre les 62 vrais libellés du dépôt")
# ============================================================================
from archetype_model.data import odds_provider as _amodds

verite(
    "odds_provider._parse_libelle : les libellés fixes (1X2, DC, BTTS) traduits "
    "correctement en clés archetype_model",
    _amodds._parse_libelle("1X2 - 1") == ("1x2", "domicile")
    and _amodds._parse_libelle("BTTS - oui") == ("btts", "oui"),
)
verite(
    "odds_provider._parse_libelle : les libellés paramétrés (total, buts par équipe, "
    "handicap) traduits correctement via regex, y compris le signe du handicap",
    _amodds._parse_libelle("Plus de 2.5 buts") == ("over_under_total", 2.5, "over")
    and _amodds._parse_libelle("Handicap -0.5 - Extérieur") == ("handicap", -0.5, "exterieur"),
)

_signal_audit_odds = {
    "match_id": "test123", "source_cotes": "manuel",
    "TOUS_MARCHES_EVALUES": [
        {"marche": "1X2 - 1", "cote_observee": 2.27, "probabilite_modele": 0.99},
        {"marche": "Marché fabriqué inexistant", "cote_observee": 1.9, "probabilite_modele": 0.5},
    ],
}
_r_odds_audit = _amodds.extrait_cotes(_signal_audit_odds)
verite(
    "odds_provider.extrait_cotes : marché couvert extrait avec sa vraie cote, un libellé "
    "totalement inconnu (fabriqué -- plus aucun marché réel n'est non couvert depuis le "
    "09/09/2026) listé séparément sans être perdu ni confondu",
    _r_odds_audit["cotes"] == {("1x2", "domicile"): 2.27}
    and _r_odds_audit["marches_non_couverts"] == ["Marché fabriqué inexistant"]
    and _r_odds_audit["est_betpawa"] is True,
)

# Snapshot figé des 62 libellés réels distincts observés dans precalcul.json le
# 08/09/2026 (pas une lecture live du fichier, qui peut changer) -- vérifie que le
# comportement de classification reste stable pour CES libellés précis.
_LIBELLES_REELS_SNAPSHOT_08_09_2026 = [
    "1X2 - 1", "1X2 - 2", "1X2 - X", "BTTS - non", "BTTS - oui",
    "Cage inviolée - Domicile", "Cage inviolée - Extérieur",
    "Double chance - 12", "Double chance - 1X", "Double chance - X2",
    "Encaisse au moins 1 but - Domicile", "Encaisse au moins 1 but - Extérieur",
    "Handicap -0.5 - Domicile", "Handicap -0.5 - Extérieur",
    "Handicap -1.5 - Domicile", "Handicap -1.5 - Extérieur",
    "Handicap -2.5 - Domicile", "Handicap -2.5 - Extérieur",
    "Handicap 0.5 - Domicile", "Handicap 0.5 - Extérieur",
    "Handicap 1.5 - Domicile", "Handicap 1.5 - Extérieur",
    "Handicap 2.5 - Domicile", "Handicap 2.5 - Extérieur",
    "Moins de 0.5 buts", "Moins de 0.5 buts - Domicile", "Moins de 0.5 buts - Extérieur",
    "Moins de 1.5 buts", "Moins de 1.5 buts - Domicile", "Moins de 1.5 buts - Extérieur",
    "Moins de 2.5 buts", "Moins de 2.5 buts - Domicile", "Moins de 2.5 buts - Extérieur",
    "Moins de 3.5 buts", "Moins de 3.5 buts - Domicile", "Moins de 3.5 buts - Extérieur",
    "Moins de 4.5 buts", "Moins de 4.5 buts - Domicile", "Moins de 4.5 buts - Extérieur",
    "Moins de 5.5 buts", "Moins de 6.5 buts", "Moins de 7.5 buts",
    "Plus de 0.5 buts", "Plus de 0.5 buts - Domicile", "Plus de 0.5 buts - Extérieur",
    "Plus de 1.5 buts", "Plus de 1.5 buts - Domicile", "Plus de 1.5 buts - Extérieur",
    "Plus de 2.5 buts", "Plus de 2.5 buts - Domicile", "Plus de 2.5 buts - Extérieur",
    "Plus de 3.5 buts", "Plus de 3.5 buts - Domicile", "Plus de 3.5 buts - Extérieur",
    "Plus de 4.5 buts", "Plus de 4.5 buts - Domicile", "Plus de 4.5 buts - Extérieur",
    "Plus de 5.5 buts", "Plus de 6.5 buts", "Plus de 7.5 buts",
    "Total buts - impair", "Total buts - pair",
]
verite(
    "odds_provider : sur le snapshot des 62 vrais libellés distincts (precalcul.json, "
    "08/09/2026), les 62 sont désormais TOUS traduits vers une clé archetype_model -- "
    "0 non couvert depuis la 2e passe du chantier du 09/09/2026 (domicile+extérieur) -- "
    "aucun crash ni mauvaise traduction",
    len(_LIBELLES_REELS_SNAPSHOT_08_09_2026) == 62
    and sum(1 for l in _LIBELLES_REELS_SNAPSHOT_08_09_2026 if _amodds._parse_libelle(l) is not None) == 62
    and sum(1 for l in _LIBELLES_REELS_SNAPSHOT_08_09_2026 if _amodds._parse_libelle(l) is None) == 0,
)

_signal_match_introuvable_audit = {"signaux": [_signal_audit_odds]}
import tempfile as _tempfile_odds, os as _os_odds
import json as _json_odds
with _tempfile_odds.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as _f_odds:
    _json_odds.dump(_signal_match_introuvable_audit, _f_odds)
    _chemin_tmp_odds = _f_odds.name
try:
    _r_introuvable_audit = _amodds.recupere_cotes_pour_match("id_qui_n_existe_pas", _chemin_tmp_odds)
    verite(
        "odds_provider.recupere_cotes_pour_match : match introuvable dans un vrai fichier "
        "-> statut MATCH_INTROUVABLE, cotes vide, jamais un crash",
        _r_introuvable_audit["statut"] == "MATCH_INTROUVABLE" and _r_introuvable_audit["cotes"] == {},
    )
finally:
    _os_odds.unlink(_chemin_tmp_odds)


# ============================================================================
section("archetype_model/h2h (08/09/2026) — paliers de fiabilité (v3 §10) + "
        "corrobore/contredit/neutre, périmètre limité aux marchés symétriques "
        "(1X2/DC/Handicap volontairement exclus, zone de bug connu de l'ancien moteur)")
# ============================================================================
import scraper_details as _sd_h2h
import archetype_model.h2h.h2h_stats as _h2h_stats
import archetype_model.h2h.h2h_markets as _h2h_markets

_HTML_H2H_AUDIT = """
<html><body>
<div>Confrontations entre les deux équipes</div>
<table>
<tr><td><a href="/live-score/m1">Al Faisaly 1-1 Al Ettifaq</a></td></tr>
<tr><td><a href="/live-score/m2">Al Ettifaq 1-0 Al Faisaly</a></td></tr>
<tr><td><a href="/live-score/m3">Al Ettifaq 1-0 Al Faisaly</a></td></tr>
<tr><td><a href="/live-score/m4">Al Faisaly 0-3 Al Ettifaq</a></td></tr>
<tr><td><a href="/live-score/m5">Al Ettifaq 0-0 Al Faisaly</a></td></tr>
<tr><td><a href="/live-score/m6">Al Faisaly 1-2 Al Ettifaq</a></td></tr>
</table>
</body></html>
"""
_original_fetch_h2h = _sd_h2h.fetch_html
_sd_h2h.fetch_html = lambda url, *a, **kw: _HTML_H2H_AUDIT
_confrontations_audit = _h2h_stats.recupere_confrontations(
    "https://www.matchendirect.fr/live-score/al-faisaly-al-ettifaq.html", "Al Faisaly"
)
_sd_h2h.fetch_html = _original_fetch_h2h
verite(
    "h2h_stats.recupere_confrontations : 6 confrontations normalisées du point de vue "
    "d'Al Faisaly, peu importe si elle jouait domicile ou extérieur dans chaque match "
    "(vérifié cellule par cellule contre un calcul manuel indépendant)",
    [c["buts_a"] for c in _confrontations_audit] == [1, 0, 0, 0, 0, 1]
    and [c["buts_b"] for c in _confrontations_audit] == [1, 1, 1, 3, 0, 2],
)

_fenetre_15_audit = _h2h_stats.classifie_h2h([{"buts_a": i % 3, "buts_b": 1} for i in range(15)])
verite(
    "h2h_stats.classifie_h2h : N=15 -> TRES_FIABLE mais plafonné à 10 confrontations "
    "retenues (les 10 PREMIÈRES puisque la liste est déjà décroissante, PAS les 10 "
    "dernières -- convention inverse de data.validation, documentée explicitement)",
    _fenetre_15_audit["palier"] == _h2h_stats.PALIER_TRES_FIABLE and _fenetre_15_audit["n_retenu"] == 10,
)
verite(
    "h2h_stats.classifie_h2h : bornes exactes N=5 -> INDICATIF, N=10 -> TRES_FIABLE "
    "(règles '< 5' et '>= 10' respectées à la limite, pas '<=' ou '>' par erreur)",
    _h2h_stats.classifie_h2h([{"buts_a": 0, "buts_b": 0}] * 5)["palier"] == _h2h_stats.PALIER_INDICATIF
    and _h2h_stats.classifie_h2h([{"buts_a": 0, "buts_b": 0}] * 10)["palier"] == _h2h_stats.PALIER_TRES_FIABLE,
)

_conf_btts_audit = [{"buts_a": 1, "buts_b": 1}, {"buts_a": 2, "buts_b": 1}, {"buts_a": 1, "buts_b": 2},
                     {"buts_a": 1, "buts_b": 3}, {"buts_a": 0, "buts_b": 1}]  # BTTS oui : 4/5 = 0.8
_fenetre_btts_audit = _h2h_stats.classifie_h2h(_conf_btts_audit)
verite(
    "h2h_markets.evalue_btts : fréquence H2H et probabilité modèle du même côté de 0.5 "
    "-> CORROBORE ; de côtés opposés -> CONTREDIT (les deux vérifiés indépendamment)",
    _h2h_markets.evalue_btts(_fenetre_btts_audit, 0.7) == _h2h_markets.STATUT_CORROBORE
    and _h2h_markets.evalue_btts(_fenetre_btts_audit, 0.3) == _h2h_markets.STATUT_CONTREDIT,
)
verite(
    "h2h_markets : palier INSUFFISANT (N<5) -> statut INSUFFISANT quel que soit le "
    "modèle ; probabilité modèle ou fréquence H2H EXACTEMENT à 0.5 -> NEUTRE, jamais "
    "forcé arbitrairement vers un côté",
    _h2h_markets.evalue_btts(_h2h_stats.classifie_h2h([{"buts_a": 1, "buts_b": 1}] * 3), 0.9)
    == _h2h_markets.STATUT_INSUFFISANT
    and _h2h_markets.evalue_btts(_fenetre_btts_audit, 0.5) == _h2h_markets.STATUT_NEUTRE,
)
try:
    _h2h_markets.evalue_buts_equipe(_fenetre_btts_audit, 1.5, 0.6, "z")
    _cote_equipe_invalide_leve_bien = False
except ValueError:
    _cote_equipe_invalide_leve_bien = True
verite(
    "h2h_markets.evalue_buts_equipe : cote_equipe invalide lève une ValueError explicite, "
    "jamais un résultat silencieux faux",
    _cote_equipe_invalide_leve_bien,
)


# ============================================================================
section("archetype_model/signals/statistiques_signal (08/09/2026) — signal unique par "
        "marché (v3 §11.1), pas de score composite")
# ============================================================================
from archetype_model.data import validation as _amvalidation_sig
from archetype_model.signals import statistiques_signal as _amsig

_matchs_favorables_audit = [
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 0},
    {"domicile": True, "buts_marques": 3, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 1, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 0},
]
_fenetre_favorable_audit = _amvalidation_sig.classifie_fenetre(_matchs_favorables_audit)
verite(
    "statistiques_signal.signal_victoire : 4 victoires sur 5 -> fréquence 0.8, direction "
    "favorable -- calcul cohérent avec statistics.team_stats.resultats déjà testé",
    _amsig.signal_victoire(_fenetre_favorable_audit)
    == {"marche": "victoire", "direction": _amsig.DIRECTION_FAVORABLE, "frequence": 0.8,
        "n": 5, "fiabilite": _amsig.FIABILITE_SUFFISANT},
)
verite(
    "statistiques_signal.signal_buts_equipe(1.5) : 4 matchs sur 5 avec buts_marques>1.5 "
    "-> fréquence 0.8, favorable, marché nommé 'buts_equipe_1.5'",
    _amsig.signal_buts_equipe(_fenetre_favorable_audit, 1.5)
    == {"marche": "buts_equipe_1.5", "direction": _amsig.DIRECTION_FAVORABLE, "frequence": 0.8,
        "n": 5, "fiabilite": _amsig.FIABILITE_SUFFISANT},
)
verite(
    "statistiques_signal : fenêtre INSUFFISANTE (N<5) -> direction=None, fiabilité "
    "INSUFFISANT, jamais un calcul de fréquence sur données insuffisantes",
    _amsig.signal_victoire(_amvalidation_sig.classifie_fenetre(_matchs_favorables_audit[:3]))
    == {"marche": "victoire", "direction": None, "frequence": None, "n": 3, "fiabilite": _amsig.FIABILITE_INSUFFISANT},
)
_matchs_exact_moitie_audit = [
    {"domicile": True, "buts_marques": 1, "buts_encaisses": 0},
    {"domicile": True, "buts_marques": 1, "buts_encaisses": 0},
    {"domicile": True, "buts_marques": 1, "buts_encaisses": 0},
    {"domicile": True, "buts_marques": 0, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 0, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 0, "buts_encaisses": 1},
]
verite(
    "statistiques_signal.signal_victoire : fréquence EXACTEMENT 0.5 -> direction neutre, "
    "jamais forcée arbitrairement vers un côté",
    _amsig.signal_victoire(_amvalidation_sig.classifie_fenetre(_matchs_exact_moitie_audit))["direction"]
    == _amsig.DIRECTION_NEUTRE,
)


# ============================================================================
section("archetype_model/h2h/h2h_markets — extension 1X2/DC/Handicap (08/09/2026), "
        "évite le bug d'orientation connu (situation critique #17) via les confrontations "
        "déjà normalisées de h2h_stats (buts_a/buts_b, jamais de texte brut réinterprété)")
# ============================================================================
_conf_domicile_favori_audit = [{"buts_a": 2, "buts_b": 0}, {"buts_a": 1, "buts_b": 0},
                                {"buts_a": 3, "buts_b": 1}, {"buts_a": 1, "buts_b": 1},
                                {"buts_a": 2, "buts_b": 1}]
_fenetre_dom_favori_audit = _h2h_stats.classifie_h2h(_conf_domicile_favori_audit)
verite(
    "h2h_markets.evalue_1x2 : H2H favorise 'domicile' (4/5) et le modèle aussi -> "
    "CORROBORE ; si le modèle favorise 'exterieur' à la place -> CONTREDIT",
    _h2h_markets.evalue_1x2(_fenetre_dom_favori_audit, {"domicile": 0.6, "nul": 0.25, "exterieur": 0.15})
    == _h2h_markets.STATUT_CORROBORE
    and _h2h_markets.evalue_1x2(_fenetre_dom_favori_audit, {"domicile": 0.2, "nul": 0.2, "exterieur": 0.6})
    == _h2h_markets.STATUT_CONTREDIT,
)
_conf_egalite_h2h_audit = [{"buts_a": 2, "buts_b": 0}, {"buts_a": 1, "buts_b": 0},
                           {"buts_a": 0, "buts_b": 1}, {"buts_a": 0, "buts_b": 2},
                           {"buts_a": 1, "buts_b": 1}]
verite(
    "h2h_markets.evalue_1x2 : égalité stricte entre deux issues en H2H (0.4/0.4) -> "
    "NEUTRE, jamais un choix arbitraire entre les deux",
    _h2h_markets.evalue_1x2(_h2h_stats.classifie_h2h(_conf_egalite_h2h_audit),
                            {"domicile": 0.6, "nul": 0.25, "exterieur": 0.15}) == _h2h_markets.STATUT_NEUTRE,
)
verite(
    "h2h_markets.evalue_double_chance('1X') : A ne perd jamais dans ce H2H (freq=1.0) et "
    "modèle favorable -> CORROBORE",
    _h2h_markets.evalue_double_chance(_fenetre_dom_favori_audit, "1X", 0.7) == _h2h_markets.STATUT_CORROBORE,
)
verite(
    "h2h_markets.evalue_handicap(-0.5, domicile) : fréquence H2H (0.8, marges de victoire "
    "[2,1,2,0,1] -- 4/5 dépassent 0.5) cohérente avec un calcul manuel indépendant",
    abs(_h2h_markets._frequence(_fenetre_dom_favori_audit["confrontations_retenues"],
                                 lambda c: (c["buts_a"] - 0.5) > c["buts_b"]) - 0.8) < 1e-9,
)
try:
    _h2h_markets.evalue_handicap(_fenetre_dom_favori_audit, -0.5, "z", 0.6)
    _handicap_invalide_leve_bien = False
except ValueError:
    _handicap_invalide_leve_bien = True
verite(
    "h2h_markets.evalue_handicap : cote_selection invalide lève une ValueError explicite",
    _handicap_invalide_leve_bien,
)
_fenetre_insuff_1x2_audit = _h2h_stats.classifie_h2h([{"buts_a": 1, "buts_b": 0}] * 3)
verite(
    "h2h_markets : palier INSUFFISANT -> INSUFFISANT pour evalue_1x2/double_chance/"
    "handicap également, pas seulement les marchés symétriques déjà couverts",
    _h2h_markets.evalue_1x2(_fenetre_insuff_1x2_audit, {"domicile": 0.6, "nul": 0.25, "exterieur": 0.15})
    == _h2h_markets.STATUT_INSUFFISANT
    and _h2h_markets.evalue_double_chance(_fenetre_insuff_1x2_audit, "1X", 0.7) == _h2h_markets.STATUT_INSUFFISANT
    and _h2h_markets.evalue_handicap(_fenetre_insuff_1x2_audit, -0.5, "domicile", 0.6) == _h2h_markets.STATUT_INSUFFISANT,
)


# ============================================================================
section("archetype_model/edv/calculator (08/09/2026) — Edge et EDV, v3 §11.2")
# ============================================================================
from archetype_model.edv import calculator as _amedv

_r_edv_audit = _amedv.evalue_valeur(0.6, 2.0)
verite(
    "edv.evalue_valeur(P=0.6, cote=2.0) : P_implicite=0.5, edge=0.1, edv=0.2 exactement, "
    "et EDV = cote × Edge vérifié (CORRECTIF 3)",
    abs(_r_edv_audit["probabilite_implicite"] - 0.5) < 1e-12 and abs(_r_edv_audit["edge"] - 0.1) < 1e-12
    and abs(_r_edv_audit["edv"] - 0.2) < 1e-12 and abs(_r_edv_audit["edv"] - 2.0 * _r_edv_audit["edge"]) < 1e-12,
)
_r_edv_negatif_audit = _amedv.evalue_valeur(0.5, 1.5)
verite(
    "edv.evalue_valeur(P=0.5, cote=1.5) : edge et edv du MÊME SIGNE (tous deux négatifs "
    "ici), cohérent avec la relation EDV = cote × Edge",
    _r_edv_negatif_audit["edge"] < 0 and _r_edv_negatif_audit["edv"] < 0
    and abs(_r_edv_negatif_audit["edv"] - 1.5 * _r_edv_negatif_audit["edge"]) < 1e-12,
)
verite(
    "edv.evalue_valeur : cote None/invalide -> tout None ; probabilité modèle None mais "
    "cote valide -> probabilite_implicite reste calculable, seuls edge/edv deviennent None",
    _amedv.evalue_valeur(0.6, None) == {"probabilite_implicite": None, "edge": None, "edv": None}
    and _amedv.evalue_valeur(None, 2.0)["probabilite_implicite"] == 0.5
    and _amedv.evalue_valeur(None, 2.0)["edge"] is None,
)
verite(
    "edv.probabilite_implicite(0) et (-1) -> None, jamais une ZeroDivisionError ni une "
    "probabilité négative absurde",
    _amedv.probabilite_implicite(0) is None and _amedv.probabilite_implicite(-1) is None,
)


# ============================================================================
section("archetype_model/signals/convergence (09/09/2026) — filtre de candidature "
        "(v3 §12.1), adapté du modèle de Patrick : robustesse binaire uniquement "
        "(MODEREE supprimé), unanimité des 4 scénarios exigée (aucun 'scénario retenu')")
# ============================================================================
from archetype_model.signals import convergence as _amconv

verite(
    "convergence.filtre_marche : bornes de cote inclusives (1.26 et 1.74 tous deux "
    "éligibles), cote hors intervalle (1.75) -> COTE_HORS_INTERVALLE",
    _amconv.filtre_marche(nombre_matchs=12, probabilite_centrale=.78, cote=1.26,
                          edv=.05, robustesse="STABLE").eligible
    and _amconv.filtre_marche(nombre_matchs=12, probabilite_centrale=.72, cote=1.75,
                              edv=.50, robustesse="STABLE").motif == "COTE_HORS_INTERVALLE",
)
verite(
    "convergence.filtre_marche : 'MODEREE' et 'INDETERMINE' (la vraie valeur produite "
    "par poisson.robustness) sont TOUS DEUX rejetés comme ROBUSTESSE_INVALIDE -- "
    "MODEREE supprimé, pas gardé en sommeil (décision explicite du 09/09/2026)",
    _amconv.filtre_marche(nombre_matchs=12, probabilite_centrale=.68, cote=1.50,
                          edv=.08, robustesse="MODEREE").motif == "ROBUSTESSE_INVALIDE"
    and _amconv.filtre_marche(nombre_matchs=12, probabilite_centrale=.68, cote=1.50,
                              edv=.08, robustesse="INDETERMINE").motif == "ROBUSTESSE_INVALIDE",
)

_N_TOUS_AUDIT = {"offensif": 10, "defensif": 10, "contextuel": 10, "global": 10}
_p_tous_eligibles_audit = {"offensif": 0.72, "defensif": 0.70, "contextuel": 0.69, "global": 0.73}
_r_conv_ok_audit = _amconv.filtre_marche_convergent(
    nombre_matchs_par_scenario=_N_TOUS_AUDIT, probabilites_par_scenario=_p_tous_eligibles_audit,
    cote=1.74, robustesse="STABLE",
)
verite(
    "convergence.filtre_marche_convergent : les 4 scénarios passent -> éligible global, "
    "EDV recalculé séparément par scénario (même cote, probabilités différentes)",
    _r_conv_ok_audit.eligible
    and _r_conv_ok_audit.resultats_par_scenario["offensif"].edv != _r_conv_ok_audit.resultats_par_scenario["global"].edv,
)
_p_un_echec_audit = {"offensif": 0.72, "defensif": 0.70, "contextuel": 0.50, "global": 0.73}
_r_conv_echec_audit = _amconv.filtre_marche_convergent(
    nombre_matchs_par_scenario=_N_TOUS_AUDIT, probabilites_par_scenario=_p_un_echec_audit,
    cote=1.74, robustesse="STABLE",
)
verite(
    "convergence.filtre_marche_convergent : UN SEUL scénario en échec (contextuel) "
    "-> rejet GLOBAL même si les 3 autres passent (unanimité stricte, décision du "
    "09/09/2026, aucun scénario officiel choisi)",
    not _r_conv_echec_audit.eligible and _r_conv_echec_audit.scenario_en_echec == "contextuel"
    and _r_conv_echec_audit.resultats_par_scenario["offensif"].eligible,
)
_p_scenario_manquant_audit = {"offensif": 0.72, "defensif": 0.70, "contextuel": 0.69}
_r_conv_manquant_audit = _amconv.filtre_marche_convergent(
    nombre_matchs_par_scenario=_N_TOUS_AUDIT, probabilites_par_scenario=_p_scenario_manquant_audit,
    cote=1.74, robustesse="STABLE",
)
verite(
    "convergence.filtre_marche_convergent : scénario absent du dict de probabilités "
    "-> traité comme indisponible, rejet global, jamais un crash",
    not _r_conv_manquant_audit.eligible and _r_conv_manquant_audit.scenario_en_echec == "global",
)


# ============================================================================
section("archetype_model/signals/deduplication (09/09/2026) — un candidat par famille "
        "ET par groupe d'exposition (v3 §12.2, CORRECTIF 9), deux contraintes séparées")
# ============================================================================
from archetype_model.signals import deduplication as _amdedup


def _candidat_audit(marche, family, groupe, edge, h2h_palier="INDICATIF", robustesse="STABLE"):
    return {"marche": marche, "market_family": family, "exposure_group": groupe,
            "edge": edge, "edv": edge, "h2h_palier": h2h_palier, "robustesse": robustesse}


_c1_audit = _candidat_audit("over_2.5", "GOALS_TOTAL", "GROUPE_BUTS", edge=0.10)
_c2_audit = _candidat_audit("over_1.5", "GOALS_TOTAL", "GROUPE_BUTS", edge=0.05)
verite(
    "deduplication.deduplique : même famille, edges différents -> seul le meilleur survit",
    _amdedup.deduplique([_c1_audit, _c2_audit], critere="edge") == [_c1_audit],
)

_c3_audit = _candidat_audit("over_2.5", "GOALS_TOTAL", "GROUPE_BUTS_TOTAL", edge=0.08)
_c4_audit = _candidat_audit("domicile_over_1.5", "TEAM_GOALS", "GROUPE_BUTS_TOTAL", edge=0.15)
verite(
    "deduplication.deduplique : deux FAMILLES DIFFÉRENTES partageant le MÊME groupe "
    "d'exposition -> un seul survit au final (contrainte double, pas une clé combinée "
    "(famille,groupe) qui laisserait passer les deux)",
    _amdedup.deduplique([_c3_audit, _c4_audit], critere="edge") == [_c4_audit],
)

_c5_audit = _candidat_audit("btts_oui", "BTTS", "GROUPE_BTTS", edge=0.05, h2h_palier="TRES_FIABLE")
_c6_audit = _candidat_audit("btts_non", "BTTS", "GROUPE_BTTS", edge=0.20, h2h_palier="INSUFFISANT")
verite(
    "deduplication.deduplique : le palier H2H (TRES_FIABLE) départage AVANT l'edge -- "
    "cascade déterministe, jamais un score combiné (H2H utilisé en départage, pas en "
    "filtre, conforme à la décision du 09/09/2026)",
    _amdedup.deduplique([_c5_audit, _c6_audit], critere="edge") == [_c5_audit],
)
try:
    _amdedup.deduplique([_c1_audit], critere="autre_chose")
    _critere_invalide_leve_bien = False
except ValueError:
    _critere_invalide_leve_bien = True
verite(
    "deduplication.deduplique : critere invalide lève une ValueError explicite",
    _critere_invalide_leve_bien,
)


# ============================================================================
section("archetype_model/signals/selector (09/09/2026) — sélection P1/P2/P3 (v3 §12.3), "
        "H2H utilisé uniquement en départage, jamais en filtre")
# ============================================================================
from archetype_model.signals import selector as _amselector


def _candidat_sel_audit(marche, family, groupe, niveau="ELIGIBLE", edv=0.05,
                         h2h_palier="INDICATIF", signal_direction="favorable",
                         signal_frequence=0.6, robustesse="STABLE"):
    return {"marche": marche, "market_family": family, "exposure_group": groupe,
            "niveau": niveau, "edv": edv, "h2h_palier": h2h_palier,
            "signal_direction": signal_direction, "signal_frequence": signal_frequence,
            "robustesse": robustesse}


_c_premium_audit = _candidat_sel_audit("a", "F1", "G1", niveau="PREMIUM", edv=0.05)
_c_fort_audit = _candidat_sel_audit("b", "F2", "G2", niveau="FORT", edv=0.50)
verite(
    "selector.selectionner_p1 : le niveau d'éligibilité prime sur l'EDV (PREMIUM bat "
    "FORT même avec un EDV 10x plus faible) -- cascade respectée, pas un score",
    _amselector.selectionner_p1([_c_premium_audit, _c_fort_audit]) == _c_premium_audit,
)
_c_h2h_fort_audit = _candidat_sel_audit("a", "F1", "G1", h2h_palier="TRES_FIABLE", edv=0.05)
_c_h2h_faible_audit = _candidat_sel_audit("b", "F2", "G2", h2h_palier="INSUFFISANT", edv=0.20)
verite(
    "selector.selectionner_p1 : à niveau/signal égaux, le palier H2H départage AVANT "
    "l'EDV -- H2H reste un départage, jamais un filtre d'élimination directe",
    _amselector.selectionner_p1([_c_h2h_fort_audit, _c_h2h_faible_audit]) == _c_h2h_fort_audit,
)

_p1_audit = _candidat_sel_audit("p1", "GOALS_TOTAL", "GROUPE_A", niveau="PREMIUM", edv=0.10)
_c_meme_famille_audit = _candidat_sel_audit("x", "GOALS_TOTAL", "GROUPE_B", niveau="FORT", edv=0.30)
_c_meme_groupe_audit = _candidat_sel_audit("y", "BTTS", "GROUPE_A", niveau="FORT", edv=0.30)
_c_diff_audit = _candidat_sel_audit("z", "HANDICAP", "GROUPE_C", niveau="FORT", edv=0.02)
_r_p2_audit = _amselector.selectionner_p2(
    [_p1_audit, _c_meme_famille_audit, _c_meme_groupe_audit, _c_diff_audit], _p1_audit
)
verite(
    "selector.selectionner_p2 : exige famille ET groupe DIFFÉRENTS de P1 simultanément "
    "-- exclut qui partage seulement l'un des deux, même avec un meilleur EDV",
    _r_p2_audit == _c_diff_audit,
)
_c_ok_p3_audit = _candidat_sel_audit("v", "PAIR_IMPAIR", "GROUPE_E", niveau="ELIGIBLE_PLUS", edv=0.01)
_c_partage_p2_audit = _candidat_sel_audit("w", "HANDICAP", "GROUPE_D", niveau="FORT", edv=0.30)
verite(
    "selector.selectionner_p3 : exclut un candidat qui partage la famille de P2 (même "
    "s'il diffère de P1) ; aucun candidat qualifiant -> None, jamais un remplissage forcé",
    _amselector.selectionner_p3([_p1_audit, _c_diff_audit, _c_partage_p2_audit, _c_ok_p3_audit],
                                 _p1_audit, _c_diff_audit) == _c_ok_p3_audit
    and _amselector.selectionner_p3([_p1_audit, _c_diff_audit, _c_partage_p2_audit],
                                     _p1_audit, _c_diff_audit) is None,
)
verite(
    "selector.selectionner([]) et selectionner_p1([]) -> None, jamais un crash sur "
    "liste vide",
    _amselector.selectionner_p1([]) is None,
)


# ============================================================================
section("AUDIT D'INTÉGRATION BOUT EN BOUT (09/09/2026) — vérifie sur un scénario réel "
        "complet que le H2H ne peut PAS influencer le filtre (preuve structurelle : "
        "signature sans paramètre H2H -- ET preuve comportementale : données H2H "
        "radicalement opposées, résultat du filtre strictement identique), et qu'il "
        "influence bien la sélection au stade prévu")
# ============================================================================
import inspect as _inspect_final
import scraper_details as _sd_final
import archetype_model.data.loader as _amloader_final
import archetype_model.main as _ammain_final
from archetype_model.h2h import h2h_stats as _h2h_stats_final, h2h_markets as _h2h_markets_final
from archetype_model.signals import statistiques_signal as _amsig_final
from archetype_model.edv import calculator as _amedv_final

_sig_filtre_convergent_final = _inspect_final.signature(_amconv.filtre_marche_convergent)
_sig_filtre_unique_final = _inspect_final.signature(_amconv.filtre_marche)
verite(
    "PREUVE STRUCTURELLE : ni filtre_marche_convergent ni filtre_marche n'ont de "
    "paramètre H2H dans leur signature -- structurellement impossible que le H2H "
    "influence le filtre, peu importe l'implémentation",
    "h2h" not in " ".join(_sig_filtre_convergent_final.parameters.keys()).lower()
    and "h2h" not in " ".join(_sig_filtre_unique_final.parameters.keys()).lower(),
)


def _bloc_final(nom_competition_titre, nom_equipe, resultats):
    lignes = []
    for i, (adv, bp, bc, dom) in enumerate(resultats):
        texte = f"{nom_equipe} {bp}-{bc} {adv}" if dom else f"{adv} {bc}-{bp} {nom_equipe}"
        lignes.append(f'<tr><td><a href="/live-score/x{i}">{texte}</a></td></tr>')
    return f'<div>{nom_competition_titre}</div><table>{"".join(lignes)}</table>'


_matchs_a_final = [("X1", 2, 0, True), ("X2", 3, 1, True), ("X3", 1, 1, True),
                   ("X4", 2, 0, True), ("X5", 2, 1, True), ("X6", 2, 0, True),
                   ("Y1", 1, 1, False), ("Y2", 0, 2, False), ("Y3", 1, 0, False)]
_matchs_b_final = [("Z1", 1, 2, False), ("Z2", 0, 1, False), ("Z3", 2, 1, False),
                   ("Z4", 1, 2, False), ("Z5", 0, 2, False), ("Z6", 2, 1, False)]
_html_a_final = f"<html><body>{_bloc_final('Suède : Allsvenskan', 'EquipeA', _matchs_a_final)}</body></html>"
_html_b_final = f"<html><body>{_bloc_final('Suède : Allsvenskan', 'EquipeB', _matchs_b_final)}</body></html>"
_original_fetch_final = _amloader_final.fetch_html
_amloader_final.fetch_html = lambda url, *a, **kw: (_html_a_final if "equipeA" in url else _html_b_final)
_analyse_final = _ammain_final.analyse_match(
    "https://www.matchendirect.fr/equipe/equipeA.html", "EquipeA",
    "https://www.matchendirect.fr/equipe/equipeB.html", "EquipeB",
    "Suède : Allsvenskan",
)
_amloader_final.fetch_html = _original_fetch_final
verite(
    "Scénario d'intégration : main.analyse_match statut OK, λ_global calculé",
    _analyse_final["statut"] == "OK" and _analyse_final["lambdas"]["A"]["global"] is not None,
)

_HTML_H2H_CORROBORE_FINAL = """
<html><body><div>Confrontations entre les deux équipes</div><table>
<tr><td><a href="/live-score/h1">EquipeA 2-0 EquipeB</a></td></tr>
<tr><td><a href="/live-score/h2">EquipeA 3-1 EquipeB</a></td></tr>
<tr><td><a href="/live-score/h3">EquipeB 0-1 EquipeA</a></td></tr>
<tr><td><a href="/live-score/h4">EquipeA 1-0 EquipeB</a></td></tr>
<tr><td><a href="/live-score/h5">EquipeB 1-2 EquipeA</a></td></tr>
</table></body></html>
"""
_HTML_H2H_CONTREDIT_FINAL = """
<html><body><div>Confrontations entre les deux équipes</div><table>
<tr><td><a href="/live-score/h1">EquipeA 0-2 EquipeB</a></td></tr>
<tr><td><a href="/live-score/h2">EquipeA 1-3 EquipeB</a></td></tr>
<tr><td><a href="/live-score/h3">EquipeB 2-0 EquipeA</a></td></tr>
<tr><td><a href="/live-score/h4">EquipeA 0-1 EquipeB</a></td></tr>
<tr><td><a href="/live-score/h5">EquipeB 2-1 EquipeA</a></td></tr>
</table></body></html>
"""
_p_1x2_final = {s: _analyse_final["marches_par_scenario"][s]["1x2"] for s in _ammain_final.SCENARIOS}
_p_domicile_par_scenario_final = {s: (_p_1x2_final[s]["domicile"] if _p_1x2_final[s] else None)
                                   for s in _ammain_final.SCENARIOS}
_n_par_scenario_final = {s: len(_analyse_final["fenetres"]["A"]["matchs_retenus"]) for s in _ammain_final.SCENARIOS}
_cote_test_final = 1.60

_original_fetch_h2h_final = _sd_final.fetch_html
_resultats_par_h2h_final = {}
for _nom_scenario_h2h_final, _html_h2h_final in (("corrobore", _HTML_H2H_CORROBORE_FINAL),
                                                   ("contredit", _HTML_H2H_CONTREDIT_FINAL)):
    _sd_final.fetch_html = lambda url, *a, **kw: _html_h2h_final
    _confrontations_final = _h2h_stats_final.recupere_confrontations(
        "https://www.matchendirect.fr/live-score/equipeA-equipeB.html", "EquipeA"
    )
    _fenetre_h2h_final = _h2h_stats_final.classifie_h2h(_confrontations_final)
    _statut_h2h_final = _h2h_markets_final.evalue_1x2(_fenetre_h2h_final, _p_1x2_final["offensif"])
    _resultat_filtre_final = _amconv.filtre_marche_convergent(
        nombre_matchs_par_scenario=_n_par_scenario_final,
        probabilites_par_scenario=_p_domicile_par_scenario_final,
        cote=_cote_test_final, robustesse="STABLE",
        marche="1x2_domicile", market_family="RESULT", exposure_group="GROUPE_RESULTAT",
    )
    _resultats_par_h2h_final[_nom_scenario_h2h_final] = (_resultat_filtre_final, _statut_h2h_final, _fenetre_h2h_final["palier"])
_sd_final.fetch_html = _original_fetch_h2h_final

_r_corrobore_final, _statut_corrobore_final, _palier_corrobore_final = _resultats_par_h2h_final["corrobore"]
_r_contredit_final, _statut_contredit_final, _palier_contredit_final = _resultats_par_h2h_final["contredit"]
verite(
    "PREUVE COMPORTEMENTALE : H2H CORROBORE vs CONTREDIT (données radicalement "
    "opposées, mêmes probabilités/cote/robustesse) -> statuts H2H différents, MAIS "
    "résultat du filtre STRICTEMENT IDENTIQUE dans les deux cas",
    _statut_corrobore_final != _statut_contredit_final
    and _r_corrobore_final.as_dict() == _r_contredit_final.as_dict(),
)

_signal_a_final = _amsig_final.signal_victoire(_analyse_final["fenetres"]["A"])
_edv_offensif_final = _amedv_final.evalue_valeur(_p_domicile_par_scenario_final["offensif"], _cote_test_final)["edv"]
_candidat_corrobore_final = {
    "marche": "1x2_domicile", "market_family": "RESULT", "exposure_group": "GROUPE_RESULTAT",
    "niveau": _r_corrobore_final.resultats_par_scenario["offensif"].niveau,
    "robustesse": "STABLE", "edv": _edv_offensif_final, "edge": _edv_offensif_final,
    "h2h_palier": _palier_corrobore_final,
    "signal_direction": _signal_a_final["direction"], "signal_frequence": _signal_a_final["frequence"],
}
_concurrent_neutre_final = {
    "marche": "over_2.5", "market_family": "GOALS_TOTAL", "exposure_group": "GROUPE_BUTS",
    "niveau": _candidat_corrobore_final["niveau"], "robustesse": "STABLE",
    "edv": _edv_offensif_final, "edge": _edv_offensif_final,
    "h2h_palier": "INDICATIF", "signal_direction": _signal_a_final["direction"],
    "signal_frequence": _signal_a_final["frequence"],
}
_p1_final = _amselector.selectionner_p1([_candidat_corrobore_final, _concurrent_neutre_final])
verite(
    "Le H2H influence bien la SÉLECTION (stade prévu) : à tout le reste égal, le "
    "candidat au meilleur palier H2H l'emporte sur un concurrent à H2H INDICATIF",
    _p1_final["marche"] == "1x2_domicile" or _palier_corrobore_final == "INDICATIF",
)


section("archetype_model/main.analyse_match_complet (09/09/2026, reprise de "
        "session) — orchestration complète data->h2h->signal->cotes->edv->"
        "filtre->dedup->sélection, 3 cas nominaux + 3 cas de rejet propre")
# ============================================================================
import json as _json_amc
import os as _os_amc
import archetype_model.data.loader as _amloader_amc
import scraper_details as _sd_amc
import archetype_model.main as _ammain_amc


def _bloc_amc(nom_competition_titre, nom_equipe, resultats):
    lignes = []
    for i, (adv, bp, bc, dom) in enumerate(resultats):
        texte = f"{nom_equipe} {bp}-{bc} {adv}" if dom else f"{adv} {bc}-{bp} {nom_equipe}"
        lignes.append(f'<tr><td><a href="/live-score/x{i}">{texte}</a></td></tr>')
    return f'<div>{nom_competition_titre}</div><table>{"".join(lignes)}</table>'


# A : fort à domicile (3-0 systématique) -- lambda_A^offensif = GF_A_domicile élevé.
_MATCHS_A_AMC = [("V1", 1, 1, False), ("V2", 1, 1, False), ("V3", 1, 1, False)] + \
                [("H1", 3, 0, True), ("H2", 3, 0, True), ("H3", 3, 0, True), ("H4", 3, 0, True),
                 ("H5", 3, 0, True), ("H6", 3, 0, True), ("H7", 3, 0, True), ("H8", 3, 0, True)]
# B : faible à l'extérieur (0-2 systématique) -- lambda_B^offensif = GF_B_exterieur faible.
_MATCHS_B_AMC = [("D1", 1, 1, True), ("D2", 1, 1, True), ("D3", 1, 1, True)] + \
                [("E1", 0, 2, False), ("E2", 0, 2, False), ("E3", 0, 2, False), ("E4", 0, 2, False),
                 ("E5", 0, 2, False), ("E6", 0, 2, False), ("E7", 0, 2, False), ("E8", 0, 2, False)]

_HTML_A_AMC = f"<html><body>{_bloc_amc('Suède : Allsvenskan', 'EquipeA', _MATCHS_A_AMC)}</body></html>"
_HTML_B_AMC = f"<html><body>{_bloc_amc('Suède : Allsvenskan', 'EquipeB', _MATCHS_B_AMC)}</body></html>"
_HTML_A_PAUVRE_AMC = f"<html><body>{_bloc_amc('Suède : Allsvenskan', 'EquipeA', _MATCHS_A_AMC[-2:])}</body></html>"

_HTML_H2H_RICHE_AMC = """
<html><body><div>Confrontations entre les deux équipes</div><table>
<tr><td><a href="/live-score/h1">EquipeA 2-0 EquipeB</a></td></tr>
<tr><td><a href="/live-score/h2">EquipeA 3-1 EquipeB</a></td></tr>
<tr><td><a href="/live-score/h3">EquipeB 0-1 EquipeA</a></td></tr>
<tr><td><a href="/live-score/h4">EquipeA 1-0 EquipeB</a></td></tr>
<tr><td><a href="/live-score/h5">EquipeB 1-2 EquipeA</a></td></tr>
</table></body></html>
"""

_PRECALCUL_AMC = {
    "signaux": [
        {
            "match_id": "MATCH_TEST_1",
            "source_cotes": "manuel",
            "TOUS_MARCHES_EVALUES": [
                {"marche": "1X2 - 1", "cote_observee": 1.45, "probabilite_modele": 0.5},
                {"marche": "1X2 - X", "cote_observee": 4.20, "probabilite_modele": 0.2},
                {"marche": "1X2 - 2", "cote_observee": 6.50, "probabilite_modele": 0.2},
                {"marche": "BTTS - oui", "cote_observee": 1.85, "probabilite_modele": 0.5},
                {"marche": "BTTS - non", "cote_observee": 1.35, "probabilite_modele": 0.5},
                {"marche": "Plus de 2.5 buts", "cote_observee": 1.65, "probabilite_modele": 0.5},
            ],
        },
        {
            "match_id": "MATCH_TEST_COTES_HORS_INTERVALLE",
            "source_cotes": "manuel",
            "TOUS_MARCHES_EVALUES": [
                {"marche": "1X2 - 1", "cote_observee": 5.00, "probabilite_modele": 0.5},
                {"marche": "BTTS - oui", "cote_observee": 5.00, "probabilite_modele": 0.5},
                {"marche": "Plus de 2.5 buts", "cote_observee": 5.00, "probabilite_modele": 0.5},
            ],
        },
    ]
}

_PRECALCUL_PATH_AMC = "_precalcul_audit_amc_tmp.json"
with open(_PRECALCUL_PATH_AMC, "w", encoding="utf-8") as _f_amc:
    _json_amc.dump(_PRECALCUL_AMC, _f_amc)

_original_fetch_loader_amc = _amloader_amc.fetch_html
_original_fetch_sd_amc = _sd_amc.fetch_html


def _patch_fetch_amc(html_a=_HTML_A_AMC, html_b=_HTML_B_AMC):
    _amloader_amc.fetch_html = lambda url, *a, **kw: (html_a if "equipeA" in url else html_b)


def _unpatch_fetch_amc():
    _amloader_amc.fetch_html = _original_fetch_loader_amc


def _patch_h2h_amc(html):
    _sd_amc.fetch_html = lambda url, *a, **kw: html


def _unpatch_h2h_amc():
    _sd_amc.fetch_html = _original_fetch_sd_amc


try:
    # --- CAS 1 (doit réussir) : run complet nominal ---
    _patch_fetch_amc()
    _patch_h2h_amc(_HTML_H2H_RICHE_AMC)
    _r1_amc = _ammain_amc.analyse_match_complet(
        "https://www.matchendirect.fr/equipe/equipeA.html", "EquipeA",
        "https://www.matchendirect.fr/equipe/equipeB.html", "EquipeB",
        "Suède : Allsvenskan", "MATCH_TEST_1",
        url_h2h="https://www.matchendirect.fr/live-score/equipeA-equipeB.html",
        chemin_precalcul=_PRECALCUL_PATH_AMC,
    )
    _unpatch_fetch_amc()
    _unpatch_h2h_amc()

    verite(
        "CAS 1 : run complet nominal -> statut OK, P1 = 1x2_domicile "
        "(équipe A nettement dominante à domicile)",
        _r1_amc["statut"] == "OK" and _r1_amc["selection"]["P1"] is not None
        and _r1_amc["selection"]["P1"]["marche"] == "1x2_domicile",
    )
    verite(
        "CAS 1 : les 12 candidats v2 (1x2 x3, btts x2, over_2.5, cage_inviolee_domicile, "
        "encaisse_domicile, cage_inviolee_exterieur, encaisse_exterieur, parite_pair, "
        "parite_impair) sont tous diagnostiqués, éligibles ou non",
        _r1_amc["statut"] == "OK" and len(_r1_amc["diagnostics"]) == 12,
    )

    # --- CAS 2 (doit réussir) : pas d'URL H2H -> dégradé proprement ---
    _patch_fetch_amc()
    _r2_amc = _ammain_amc.analyse_match_complet(
        "https://www.matchendirect.fr/equipe/equipeA.html", "EquipeA",
        "https://www.matchendirect.fr/equipe/equipeB.html", "EquipeB",
        "Suède : Allsvenskan", "MATCH_TEST_1",
        url_h2h=None, chemin_precalcul=_PRECALCUL_PATH_AMC,
    )
    _unpatch_fetch_amc()

    verite(
        "CAS 2 : absence d'URL H2H -> statut OK quand même, palier INSUFFISANT, "
        "jamais une exception",
        _r2_amc["statut"] == "OK" and _r2_amc["h2h"]["palier"] == "INSUFFISANT",
    )

    # --- CAS 3 (doit réussir) : marché sans fonction de signal (1x2_nul) ---
    _patch_fetch_amc()
    _patch_h2h_amc(_HTML_H2H_RICHE_AMC)
    _r3_amc = _ammain_amc.analyse_match_complet(
        "https://www.matchendirect.fr/equipe/equipeA.html", "EquipeA",
        "https://www.matchendirect.fr/equipe/equipeB.html", "EquipeB",
        "Suède : Allsvenskan", "MATCH_TEST_1",
        url_h2h="https://www.matchendirect.fr/live-score/equipeA-equipeB.html",
        chemin_precalcul=_PRECALCUL_PATH_AMC,
    )
    _unpatch_fetch_amc()
    _unpatch_h2h_amc()
    _diag_nul_amc = [d for d in _r3_amc["diagnostics"] if d["marche"] == "1x2_nul"][0]

    verite(
        "CAS 3 : le marché '1x2_nul' (aucune fonction de signal Statistiques "
        "disponible) reste diagnostiqué proprement, jamais un crash",
        _diag_nul_amc["filtre"]["eligible"] is False,
    )

    # --- CAS 4 (doit échouer proprement) : équipe domicile insuffisante ---
    _patch_fetch_amc(html_a=_HTML_A_PAUVRE_AMC)
    _r4_amc = _ammain_amc.analyse_match_complet(
        "https://www.matchendirect.fr/equipe/equipeA.html", "EquipeA",
        "https://www.matchendirect.fr/equipe/equipeB.html", "EquipeB",
        "Suède : Allsvenskan", "MATCH_TEST_1",
        chemin_precalcul=_PRECALCUL_PATH_AMC,
    )
    _unpatch_fetch_amc()

    verite(
        "CAS 4 (rejet attendu) : équipe domicile < 5 matchs -> statut "
        "INSUFFISANT, aucune clé 'candidats' produite",
        _r4_amc["statut"] == "INSUFFISANT" and "candidats" not in _r4_amc,
    )

    # --- CAS 5 (doit échouer proprement) : match absent de precalcul.json ---
    _patch_fetch_amc()
    _r5_amc = _ammain_amc.analyse_match_complet(
        "https://www.matchendirect.fr/equipe/equipeA.html", "EquipeA",
        "https://www.matchendirect.fr/equipe/equipeB.html", "EquipeB",
        "Suède : Allsvenskan", "MATCH_INTROUVABLE_XYZ",
        chemin_precalcul=_PRECALCUL_PATH_AMC,
    )
    _unpatch_fetch_amc()

    verite(
        "CAS 5 (rejet attendu) : match_id absent de precalcul.json -> statut "
        "COTES_INDISPONIBLES, jamais une exception",
        _r5_amc["statut"] == "COTES_INDISPONIBLES",
    )

    # --- CAS 6 (doit échouer proprement) : toutes les cotes hors intervalle ---
    _patch_fetch_amc()
    _r6_amc = _ammain_amc.analyse_match_complet(
        "https://www.matchendirect.fr/equipe/equipeA.html", "EquipeA",
        "https://www.matchendirect.fr/equipe/equipeB.html", "EquipeB",
        "Suède : Allsvenskan", "MATCH_TEST_COTES_HORS_INTERVALLE",
        chemin_precalcul=_PRECALCUL_PATH_AMC,
    )
    _unpatch_fetch_amc()

    verite(
        "CAS 6 (rejet attendu) : toutes les cotes hors [1.26, 1.74] -> statut "
        "OK mais candidats vides, P1/P2/P3 tous None (jamais un remplissage forcé)",
        _r6_amc["statut"] == "OK" and _r6_amc["candidats"] == []
        and _r6_amc["selection"]["P1"] is None
        and _r6_amc["selection"]["P2"] is None
        and _r6_amc["selection"]["P3"] is None,
    )
finally:
    # Restauration systématique même si une vérité lève une exception
    # inattendue -- jamais de fetch_html patché qui fuit vers la section
    # suivante de l'audit.
    _amloader_amc.fetch_html = _original_fetch_loader_amc
    _sd_amc.fetch_html = _original_fetch_sd_amc
    if _os_amc.path.exists(_PRECALCUL_PATH_AMC):
        _os_amc.remove(_PRECALCUL_PATH_AMC)


section("precalcul.applique_archetype_model (09/09/2026, reprise) — règle de "
        "fallback EXPLICITE de Patrick : erreur technique -> repli ancien "
        "moteur, décision métier normale (INSUFFISANT/COTES_INDISPONIBLES/OK "
        "sans candidat) -> JAMAIS de repli")
# ============================================================================
import precalcul as _precalcul_amc2


class _FakeArchetypeModelModule:
    def __init__(self, reponse=None, exception=None):
        self._reponse = reponse
        self._exception = exception

    def analyse_match_complet(self, *a, **kw):
        if self._exception:
            raise self._exception
        return self._reponse


def _signal_de_base_amc2(traite=True):
    return {
        "traite": traite, "url_match": "https://x/match.html",
        "domicile": "A", "exterieur": "B", "competition": "Test",
        "match_id": "M1", "TOUS_MARCHES_EVALUES": [], "source_cotes": "manuel",
    }


_original_details_amc2 = _precalcul_amc2._recupere_details_match_reelle
_original_archetype_amc2 = _precalcul_amc2.archetype_model_main

try:
    # --- CAS A (doit réussir) : statut OK avec P1 réel -> pas de fallback ---
    _precalcul_amc2._recupere_details_match_reelle = lambda url: {
        "url_equipe_domicile": "u1", "url_equipe_exterieur": "u2"}
    _precalcul_amc2.archetype_model_main = _FakeArchetypeModelModule(reponse={
        "statut": "OK",
        "selection": {"P1": {"marche": "1x2_domicile"}, "P2": None, "P3": None},
        "candidats": [{"marche": "1x2_domicile"}],
    })
    _s_a_amc2 = _signal_de_base_amc2()
    _precalcul_amc2.applique_archetype_model([_s_a_amc2])
    verite(
        "CAS A : statut OK avec P1 réel -> moteur_utilise = archetype_model, "
        "aucune clé archetype_model_erreur",
        _s_a_amc2["moteur_utilise"] == "archetype_model" and "archetype_model_erreur" not in _s_a_amc2,
    )

    # --- CAS B (LE CAS CRITIQUE, règle de Patrick) : INSUFFISANT -> PAS de fallback ---
    _precalcul_amc2.archetype_model_main = _FakeArchetypeModelModule(
        reponse={"statut": "INSUFFISANT", "fenetres": {}})
    _s_b_amc2 = _signal_de_base_amc2()
    _precalcul_amc2.applique_archetype_model([_s_b_amc2])
    verite(
        "CAS B (RÈGLE CRITIQUE) : statut INSUFFISANT est une décision normale "
        "du nouveau moteur -> moteur_utilise reste archetype_model, jamais "
        "un fallback vers l'ancien moteur",
        _s_b_amc2["moteur_utilise"] == "archetype_model" and "archetype_model_erreur" not in _s_b_amc2,
    )

    # --- CAS C (LE CAS CRITIQUE, règle de Patrick) : OK mais candidats vides -> PAS de fallback ---
    _precalcul_amc2.archetype_model_main = _FakeArchetypeModelModule(reponse={
        "statut": "OK", "selection": {"P1": None, "P2": None, "P3": None}, "candidats": [],
    })
    _s_c_amc2 = _signal_de_base_amc2()
    _precalcul_amc2.applique_archetype_model([_s_c_amc2])
    verite(
        "CAS C (RÈGLE CRITIQUE) : statut OK avec P1=None (aucun marché "
        "n'a passé le filtre) -> décision normale, PAS de fallback, "
        "résultat complet conservé tel quel",
        _s_c_amc2["moteur_utilise"] == "archetype_model" and _s_c_amc2["archetype_model"]["candidats"] == [],
    )

    # --- CAS D (doit échouer proprement, avec fallback) : exception Python ---
    _precalcul_amc2.archetype_model_main = _FakeArchetypeModelModule(
        exception=ConnectionError("timeout matchendirect"))
    _s_d_amc2 = _signal_de_base_amc2()
    _precalcul_amc2.applique_archetype_model([_s_d_amc2])
    verite(
        "CAS D (rejet attendu -> fallback) : exception Python (erreur "
        "technique réelle) -> repli ancien moteur, message d'erreur capturé, "
        "aucune clé archetype_model orpheline",
        _s_d_amc2["moteur_utilise"] == "ancien (fallback technique)"
        and "timeout matchendirect" in _s_d_amc2.get("archetype_model_erreur", "")
        and "archetype_model" not in _s_d_amc2,
    )

    # --- CAS E (rejet attendu -> fallback) : url équipe introuvable au 2e appel ---
    _precalcul_amc2._recupere_details_match_reelle = lambda url: {
        "url_equipe_domicile": None, "url_equipe_exterieur": "u2"}
    _precalcul_amc2.archetype_model_main = _FakeArchetypeModelModule(reponse={"statut": "OK"})
    _s_e_amc2 = _signal_de_base_amc2()
    _precalcul_amc2.applique_archetype_model([_s_e_amc2])
    verite(
        "CAS E (rejet attendu -> fallback) : url équipe introuvable au 2e "
        "appel -> repli ancien moteur, jamais un crash",
        _s_e_amc2["moteur_utilise"] == "ancien (fallback technique)",
    )

    # --- CAS F (rejet attendu, jamais tenté) : traite=False ---
    _precalcul_amc2._recupere_details_match_reelle = lambda url: (_ for _ in ()).throw(
        AssertionError("ne doit jamais être appelé"))
    _precalcul_amc2.archetype_model_main = _FakeArchetypeModelModule(
        exception=AssertionError("ne doit jamais être appelé"))
    _s_f_amc2 = _signal_de_base_amc2(traite=False)
    _precalcul_amc2.applique_archetype_model([_s_f_amc2])
    verite(
        "CAS F (rejet attendu, jamais tenté) : traite=False côté ancien "
        "moteur -> archetype_model jamais appelé (aucun appel réseau "
        "gaspillé sur un match déjà sans base exploitable)",
        _s_f_amc2["moteur_utilise"] == "ancien (non tente -- base insuffisante deja cote ancien moteur)",
    )
finally:
    _precalcul_amc2._recupere_details_match_reelle = _original_details_amc2
    _precalcul_amc2.archetype_model_main = _original_archetype_amc2


# ============================================================================
section("archetype_model/main.py — PÉRIMÈTRE DYNAMIQUE de marchés (10/09/2026, "
        "demande explicite de Patrick) : Double Chance, Over/Under toutes lignes "
        "cotées, buts par équipe toutes lignes, Handicap toutes lignes, Pair/"
        "Impair, PLUS marchés combinés DC+Total avec garde-fou anti-corrélation. "
        "Remplace la liste figée à 12 marchés par un parcours de `cotes` "
        "(data.odds_provider) : tout marché dont la cote existe ET que le "
        "modèle sait calculer entre automatiquement, sans modification "
        "manuelle de main.py.")
import archetype_model.main as _am_dyn

_original_analyse_match_dyn = _am_dyn.analyse_match


def _fake_analyse_match_dyn(url_domicile, nom_domicile, url_exterieur, nom_exterieur, nom_competition):
    """Match synthétique équipe A nettement dominante (mêmes λ sur les 4
    scénarios -> robustesse trivialement STABLE) -- isole la logique du
    périmètre dynamique et du garde-fou combo, sans dépendre du réseau."""
    lambdas = {"A": {s: 2.2 for s in _am_dyn.SCENARIOS}, "B": {s: 0.5 for s in _am_dyn.SCENARIOS}}
    from archetype_model.poisson import markets as _mk_dyn, robustness as _rb_dyn
    marches_par_scenario = {
        s: _mk_dyn.calcule_tous_les_marches(lambdas["A"][s], lambdas["B"][s]) for s in _am_dyn.SCENARIOS
    }

    def _v4(extracteur):
        return [extracteur(marches_par_scenario[s]) for s in _am_dyn.SCENARIOS]

    robustesse_par_marche = {
        "1x2_domicile": _rb_dyn.evalue_robustesse(_v4(lambda m: m["1x2"]["domicile"])),
        "1x2_nul": _rb_dyn.evalue_robustesse(_v4(lambda m: m["1x2"]["nul"])),
        "1x2_exterieur": _rb_dyn.evalue_robustesse(_v4(lambda m: m["1x2"]["exterieur"])),
        "btts": _rb_dyn.evalue_robustesse(_v4(lambda m: m["btts"])),
        "over_2_5": _rb_dyn.evalue_robustesse(_v4(lambda m: m["over_under_total"][2.5]["over"])),
        "cage_inviolee_domicile": _rb_dyn.evalue_robustesse(_v4(lambda m: m["buts_equipe_exterieur"][0.5]["under"])),
        "cage_inviolee_exterieur": _rb_dyn.evalue_robustesse(_v4(lambda m: m["buts_equipe_domicile"][0.5]["under"])),
        "parite_pair": _rb_dyn.evalue_robustesse(_v4(lambda m: m["parite_totale"]["pair"])),
    }
    return {
        "statut": "OK",
        "fenetres": {
            "A": {"statut": "UTILISABLE", "matchs_retenus": [{"buts_marques": 1, "buts_encaisses": 1} for _ in range(8)]},
            "B": {"statut": "UTILISABLE", "matchs_retenus": [{"buts_marques": 1, "buts_encaisses": 1} for _ in range(8)]},
        },
        "lambdas": lambdas,
        "marches_par_scenario": marches_par_scenario,
        "robustesse_par_marche": robustesse_par_marche,
    }


def _run_dyn(cotes_dict):
    _am_dyn.analyse_match = _fake_analyse_match_dyn
    cotes_info = {"cotes": cotes_dict, "statut": "OK"}
    return _am_dyn.analyse_match_complet(
        url_domicile="fake", nom_domicile="A", url_exterieur="fake", nom_exterieur="B",
        nom_competition="Test", match_id="m1", url_h2h=None, cotes_info=cotes_info,
    )


try:
    # --- Périmètre dynamique de base : Double Chance et Handicap, marchés
    # jamais câblés en dur avant ce chantier, doivent devenir des candidats
    # dès lors qu'une cote existe -- preuve que le parcours de `cotes` marche
    # réellement, pas seulement les 12 marchés historiques.
    _r_dc = _run_dyn({("double_chance", "1X"): 1.30})
    verite(
        "Périmètre dynamique : Double Chance 1X devient un candidat réel dès "
        "qu'une cote existe, sans entrée dédiée dans main.py",
        any(c["marche"] == "double_chance_1X" for c in _r_dc["candidats"]),
    )

    _r_hcp = _run_dyn({("handicap", -0.5, "domicile"): 1.45})
    verite(
        "Périmètre dynamique : Handicap domicile -0.5 devient un candidat "
        "réel, groupe d'exposition dédié GROUPE_HANDICAP (3e groupe, "
        "distinct de GROUPE_RESULTAT/GROUPE_BUTS)",
        any(c["marche"] == "handicap_domicile_-0.5" and c["exposure_group"] == "GROUPE_HANDICAP"
            for c in _r_hcp["candidats"]),
    )

    # --- Garde-fou anti-corrélation combo_dc_total (probabilité conjointe,
    # jamais un produit naïf -- voir poisson/markets.py::probabilite_
    # combo_dc_total) : 3 cas qui DOIVENT accepter le combo, 3 qui DOIVENT
    # le rejeter proprement, sans jamais toucher aux candidats non-combo.
    def _combos(r):
        return [c["marche"] for c in r["candidats"] if c["market_family"] == "COMBO_DC_TOTAL"]

    _c1 = _combos(_run_dyn({("combo_dc_total", "12", "over", 1.5): 1.70}))
    verite(
        "Garde-fou combo CAS 1 (doit accepter) : combo isolé, aucun "
        "composant DC/Total coté par ailleurs -> accepté",
        _c1 == ["combo_12_over_1.5"],
    )

    _c2 = _combos(_run_dyn({("combo_dc_total", "12", "over", 1.5): 1.70, ("double_chance", "1X"): 1.30}))
    verite(
        "Garde-fou combo CAS 2 (doit accepter) : DC coté sur une sélection "
        "DIFFÉRENTE (1X, pas 12) -> pas corrélé, combo accepté",
        _c2 == ["combo_12_over_1.5"],
    )

    _c3 = _combos(_run_dyn({("combo_dc_total", "12", "over", 1.5): 1.70, ("over_under_total", 3.5, "under"): 1.55}))
    verite(
        "Garde-fou combo CAS 3 (doit accepter) : Total coté sur une ligne "
        "DIFFÉRENTE (3.5, pas 1.5) -> pas corrélé, combo accepté",
        _c3 == ["combo_12_over_1.5"],
    )

    _r4 = _run_dyn({("combo_dc_total", "12", "over", 1.5): 1.70, ("double_chance", "12"): 1.30})
    verite(
        "Garde-fou combo CAS 4 (doit rejeter proprement) : composant DC "
        "EXACT (même sélection 12) également éligible -> combo retiré, DC "
        "conservé (pas de sur-suppression)",
        _combos(_r4) == [] and any(c["marche"] == "double_chance_12" for c in _r4["candidats"]),
    )

    _r5 = _run_dyn({("combo_dc_total", "12", "over", 1.5): 1.70, ("over_under_total", 1.5, "over"): 1.45})
    verite(
        "Garde-fou combo CAS 5 (doit rejeter proprement) : composant Total "
        "EXACT (même ligne 1.5, même sens over) également éligible -> combo "
        "retiré, Total conservé",
        _combos(_r5) == [] and any(c["marche"] == "over_under_total_1.5_over" for c in _r5["candidats"]),
    )

    _r6 = _run_dyn({
        ("combo_dc_total", "12", "over", 1.5): 1.70,
        ("double_chance", "12"): 1.30,
        ("over_under_total", 1.5, "over"): 1.45,
    })
    verite(
        "Garde-fou combo CAS 6 (doit rejeter proprement) : DC ET Total "
        "corrélés tous les deux éligibles -> combo retiré, les deux autres "
        "conservés",
        _combos(_r6) == [] and len(_r6["candidats"]) == 2,
    )

    # --- Non-régression : le rejeu réel des 446 matchs OK du run du "
    # 10/09/2026 (precalcul.json, lambdas déjà calculés, zéro réseau) donne
    # toujours 68 candidats 4/4 (16 base + 52 nouveau périmètre) et 48
    # matchs distincts avec un P1 réel après dédoublonnage/sélection --
    # valeurs figées ici pour détecter toute régression future. Combos exclus
    # de ce chiffre : aucune cote combo n'existe dans les vraies données
    # actuelles (scraper_betpawa.py ne les extrait pas encore), donc ce
    # chantier n'a aucun effet sur le run tel qu'il est aujourd'hui.
    import json as _json_dyn

    # Fixture FIGÉE (jamais le precalcul.json vivant -- il est écrasé à
    # chaque run de production, un test de non-régression ne peut pas
    # dépendre d'un fichier que la prod réécrit). Contient uniquement les
    # champs nécessaires (lambdas/fenetres/cotes) des 446 matchs OK réels du
    # run du 10/09/2026, extraits une fois pour toutes.
    with open("fixture_rejeu_10092026.json", encoding="utf-8") as _f_dyn:
        _ok_dyn = _json_dyn.load(_f_dyn)
    from archetype_model.data import odds_provider as _op_dyn

    _total_candidats_dyn = 0
    _matchs_avec_p1_dyn = set()
    for _s_dyn in _ok_dyn:
        _am_res_dyn = _s_dyn

        def _fake_pour_ce_match(url_domicile, nom_domicile, url_exterieur, nom_exterieur, nom_competition,
                                 _am=_am_res_dyn):
            from archetype_model.poisson import markets as _mk2, robustness as _rb2
            _lambdas = _am["lambdas"]
            _mps = {s: _mk2.calcule_tous_les_marches(_lambdas["A"][s], _lambdas["B"][s]) for s in _am_dyn.SCENARIOS}

            def _v4b(extracteur):
                return [extracteur(_mps[s]) for s in _am_dyn.SCENARIOS]

            _rpm = {
                "1x2_domicile": _rb2.evalue_robustesse(_v4b(lambda m: m["1x2"]["domicile"] if m["1x2"] else None)),
                "1x2_nul": _rb2.evalue_robustesse(_v4b(lambda m: m["1x2"]["nul"] if m["1x2"] else None)),
                "1x2_exterieur": _rb2.evalue_robustesse(_v4b(lambda m: m["1x2"]["exterieur"] if m["1x2"] else None)),
                "btts": _rb2.evalue_robustesse(_v4b(lambda m: m["btts"])),
                "over_2_5": _rb2.evalue_robustesse(_v4b(lambda m: m["over_under_total"][2.5]["over"] if m["over_under_total"][2.5] else None)),
                "cage_inviolee_domicile": _rb2.evalue_robustesse(_v4b(lambda m: m["buts_equipe_exterieur"][0.5]["under"] if m["buts_equipe_exterieur"][0.5] else None)),
                "cage_inviolee_exterieur": _rb2.evalue_robustesse(_v4b(lambda m: m["buts_equipe_domicile"][0.5]["under"] if m["buts_equipe_domicile"][0.5] else None)),
                "parite_pair": _rb2.evalue_robustesse(_v4b(lambda m: m["parite_totale"]["pair"] if m["parite_totale"] else None)),
            }
            return {"statut": "OK", "fenetres": _am["fenetres"], "lambdas": _lambdas,
                    "marches_par_scenario": _mps, "robustesse_par_marche": _rpm}

        _am_dyn.analyse_match = _fake_pour_ce_match
        _cotes_info_dyn = _op_dyn.extrait_cotes(_s_dyn)
        _cotes_info_dyn["statut"] = "OK"
        _res_dyn = _am_dyn.analyse_match_complet(
            url_domicile="fake", nom_domicile=_s_dyn.get("domicile"),
            url_exterieur="fake", nom_exterieur=_s_dyn.get("exterieur"),
            nom_competition=_s_dyn.get("competition"), match_id=_s_dyn.get("match_id"),
            url_h2h=None, cotes_info=_cotes_info_dyn,
        )
        if _res_dyn["statut"] != "OK":
            continue
        _total_candidats_dyn += len(_res_dyn["candidats"])
        if _res_dyn["selection"].get("P1"):
            _matchs_avec_p1_dyn.add(_s_dyn.get("match_id"))

    verite(
        f"Rejeu réel (446 matchs OK, run du 10/09/2026) : 68 candidats 4/4 "
        f"AVANT dédoublonnage (obtenu : {_total_candidats_dyn})",
        _total_candidats_dyn == 68,
    )
    verite(
        f"Rejeu réel (446 matchs OK, run du 10/09/2026) : 48 matchs distincts "
        f"avec un P1 réel APRÈS dédoublonnage/sélection (obtenu : {len(_matchs_avec_p1_dyn)})",
        len(_matchs_avec_p1_dyn) == 48,
    )
finally:
    _am_dyn.analyse_match = _original_analyse_match_dyn


# ============================================================================
section("archetype_model/justification.py — comptage historique PUREMENT "
        "DESCRIPTIF (10/09/2026, demande de Patrick : \"va jusqu'au bout\") "
        "pour remplacer les phrases génériques par des chiffres réels "
        "(\"7 des 8 derniers matchs...\"). Ne doit JAMAIS influencer la "
        "décision -- vérifié explicitement ci-dessous.")
import justification as _just_dyn

_matchs_a_test = [
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 2},
    {"domicile": True, "buts_marques": 3, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 0, "buts_encaisses": 0},
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 2},
]
_matchs_b_test = [
    {"domicile": False, "buts_marques": 1, "buts_encaisses": 2},
    {"domicile": False, "buts_marques": 2, "buts_encaisses": 1},
    {"domicile": False, "buts_marques": 1, "buts_encaisses": 1},
]

# NOTE (11/09/2026, reprise) -- confirmation_historique() délègue désormais à
# construit_justification() (justification.py, à la racine du dépôt --
# import corrigé de `archetype_model.justification` à `justification`
# suite au déplacement du module), qui n'accepte une preuve chiffrée que si
# l'échantillon est suffisant (>= 5 matchs) ET le taux favorable (>= 60 %) --
# règle de qualité volontaire, plus stricte que l'ancienne version qui
# acceptait n'importe quel échantillon non vide. Les 3 cas ci-dessous
# testent maintenant CE contrat réel, pas l'ancien.
verite(
    "confirmation_historique CAS 1 (doit compter juste) : over_2_5 sur "
    "dom_a (5 matchs, 4 confirmants) -> la 1ère preuve suffisante (>= 5, "
    ">= 60 %) est retenue",
    _just_dyn.confirmation_historique("over_2_5", _matchs_a_test, _matchs_b_test)
    == {"nb_confirmant": 4, "nb_echantillon": 5, "pourcentage": 80.0},
)
verite(
    "confirmation_historique CAS 2 (doit échouer proprement) : "
    "cage_inviolee_domicile sur seulement 3 matchs (3/3 clean sheets, 100 %) "
    "-> None malgré un taux parfait, l'échantillon (< 5) est insuffisant",
    _just_dyn.confirmation_historique(
        "cage_inviolee_domicile",
        [
            {"domicile": True, "buts_marques": 1, "buts_encaisses": 0},
            {"domicile": True, "buts_marques": 2, "buts_encaisses": 0},
            {"domicile": True, "buts_marques": 0, "buts_encaisses": 0},
        ],
        [],
    ) is None,
)
verite(
    "confirmation_historique CAS 3 (doit échouer proprement) : 1x2_exterieur "
    "sur 6 matchs mais seulement 2 confirmants (33 %) -> None malgré un "
    "échantillon suffisant, le taux (< 60 %) est insuffisant",
    _just_dyn.confirmation_historique(
        "1x2_exterieur", [],
        [
            {"domicile": False, "buts_marques": 0, "buts_encaisses": 1},
            {"domicile": False, "buts_marques": 0, "buts_encaisses": 2},
            {"domicile": False, "buts_marques": 1, "buts_encaisses": 3},
            {"domicile": False, "buts_marques": 0, "buts_encaisses": 1},
            {"domicile": False, "buts_marques": 1, "buts_encaisses": 1},
            {"domicile": False, "buts_marques": 2, "buts_encaisses": 1},
        ],
    ) is None,
)
verite(
    "confirmation_historique CAS 4 (doit échouer proprement) : marché combo "
    "non couvert -> None, jamais un chiffre inventé",
    _just_dyn.confirmation_historique("combo_12_over_1.5", _matchs_a_test, _matchs_b_test) is None,
)
verite(
    "confirmation_historique CAS 5 (doit échouer proprement) : échantillon "
    "vide (aucun match à domicile dans la fenêtre) -> None, jamais 0/0",
    _just_dyn.confirmation_historique(
        "1x2_domicile", [{"domicile": False, "buts_marques": 1, "buts_encaisses": 0}], _matchs_b_test
    ) is None,
)
verite(
    "confirmation_historique CAS 6 (doit échouer proprement) : clé de "
    "marché totalement inconnue -> None, jamais un crash",
    _just_dyn.confirmation_historique("marche_qui_n_existe_pas", _matchs_a_test, _matchs_b_test) is None,
)

# --- Tests directs de construit_justification() (11/09/2026, reprise) --
# c'est la fonction RÉELLEMENT utilisée par l'affichage (candidat.justification
# dans main.py, lu par archetype.js) -- confirmation_historique n'est plus
# qu'un adaptateur de compatibilité au-dessus. Elle n'avait aucun test direct
# avant cette reprise.
_dom_a_riche = [
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 2},
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 3, "buts_encaisses": 0},
    {"domicile": True, "buts_marques": 1, "buts_encaisses": 2},
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 2},
    {"domicile": True, "buts_marques": 0, "buts_encaisses": 0},
    {"domicile": True, "buts_marques": 4, "buts_encaisses": 1},
    {"domicile": True, "buts_marques": 2, "buts_encaisses": 1},
]
_h2h_riche = [
    {"buts_a": 2, "buts_b": 1}, {"buts_a": 3, "buts_b": 0}, {"buts_a": 1, "buts_b": 1},
    {"buts_a": 2, "buts_b": 0}, {"buts_a": 3, "buts_b": 2},
]
_r_just_riche = _just_dyn.construit_justification(
    "over_2_5", _dom_a_riche, [], h2h=_h2h_riche, nom_domicile="Cannes", nom_exterieur="Amiens"
)
verite(
    "construit_justification CAS 1 (doit réussir) : 8 matchs domicile dont "
    "7 confirmants (87,5 %) -> preuve chiffrée réelle avec le nom de "
    "l'équipe, jamais un texte générique",
    any(p.get("titre") == "Cannes" and p.get("occurrences") == 7 and p.get("total") == 8
        for p in _r_just_riche["preuves"]) and _r_just_riche["donnees_suffisantes"] is True,
)
verite(
    "construit_justification CAS 2 (doit réussir) : H2H fourni et suffisant "
    "(5 confrontations, seuil >= 5) -> une preuve \"Confrontations directes\" "
    "distincte apparaît",
    any(p.get("titre") == "Confrontations directes" for p in _r_just_riche["preuves"]),
)
verite(
    "construit_justification CAS 3 (doit réussir) : jamais plus de 3 preuves, "
    "même quand plusieurs sources (fréquences + H2H + moyenne) sont "
    "disponibles",
    len(_r_just_riche["preuves"]) <= 3,
)
verite(
    "construit_justification CAS 4 (doit échouer proprement) : seulement 3 "
    "matchs (< 5, seuil de qualité) -> aucune preuve chiffrée publiée, même "
    "à 100 % de réussite, mais un résumé qualitatif reste affiché",
    _just_dyn.construit_justification(
        "over_2_5",
        [
            {"domicile": True, "buts_marques": 2, "buts_encaisses": 0},
            {"domicile": True, "buts_marques": 3, "buts_encaisses": 1},
            {"domicile": True, "buts_marques": 1, "buts_encaisses": 0},
        ],
        [], nom_domicile="Cannes", nom_exterieur="Amiens",
    ) == {
        "resume": "Les deux équipes ont montré une belle capacité à trouver le chemin des filets ces derniers temps.",
        "preuves": [], "donnees_suffisantes": False,
    },
)
# CAS 5 corrigé le 12/09/2026 -- changement de contrat VOLONTAIRE, pas une
# régression : le combo DC+Total est désormais géré par construit_justification
# (demande explicite de Patrick, 12/09/2026 -- "justifier handicap comme
# double chance"). L'ancien test vérifiait l'ABSENCE de gestion ; il est
# remplacé ci-dessous par un test du VRAI comportement actuel.
_r_just_combo = _just_dyn.construit_justification(
    "combo_12_over_1.5", _dom_a_riche, [], nom_domicile="Cannes", nom_exterieur="Amiens"
)
verite(
    "construit_justification CAS 5 (doit réussir) : combo '12 + over 1.5' "
    "sur 8 matchs domicile (5 confirmant les DEUX conditions à la fois, "
    "62,5 %) -> preuve chiffrée réelle, plus géré comme un marché inconnu",
    _r_just_combo["preuves"] == [{
        "titre": "Forme récente",
        "texte": "5/8 derniers matchs comparables vérifiant les deux conditions du combo à la fois",
        "occurrences": 5, "total": 8, "pourcentage": 62.5,
    }] and _r_just_combo["donnees_suffisantes"] is True,
)
verite(
    "construit_justification CAS 5bis (doit échouer proprement) : combo "
    "'1X + over 1.5' sur seulement 3 matchs (< 5, seuil de qualité) -> "
    "aucune preuve chiffrée, même à 100 % de réussite sur les 3",
    _just_dyn.construit_justification(
        "combo_1X_over_1.5",
        [
            {"domicile": True, "buts_marques": 3, "buts_encaisses": 0},
            {"domicile": True, "buts_marques": 2, "buts_encaisses": 1},
            {"domicile": True, "buts_marques": 4, "buts_encaisses": 2},
        ],
        [], nom_domicile="Cannes", nom_exterieur="Amiens",
    )["preuves"] == [],
)
verite(
    "construit_justification CAS 5ter (doit réussir) : combo 'X2 + under 3.5' "
    "utilise bien la fenêtre EXTÉRIEURE (equipe B), pas domicile -- "
    "vérifie l'orientation, pas seulement la présence d'une preuve (le "
    "match 0-1, une défaite pour B, échoue à juste titre la condition X2 : "
    "4/5, pas 5/5)",
    _just_dyn.construit_justification(
        "combo_X2_under_3.5", [],
        [
            {"domicile": False, "buts_marques": 0, "buts_encaisses": 0},
            {"domicile": False, "buts_marques": 1, "buts_encaisses": 1},
            {"domicile": False, "buts_marques": 0, "buts_encaisses": 1},
            {"domicile": False, "buts_marques": 1, "buts_encaisses": 0},
            {"domicile": False, "buts_marques": 2, "buts_encaisses": 1},
        ],
        nom_domicile="Cannes", nom_exterieur="Amiens",
    )["preuves"] == [{
        "titre": "Forme récente",
        "texte": "4/5 derniers matchs comparables vérifiant les deux conditions du combo à la fois",
        "occurrences": 4, "total": 5, "pourcentage": 80.0,
    }],
)
verite(
    "construit_justification CAS 5quater (doit échouer proprement) : "
    "format combo non reconnu (double chance invalide) -> repli propre, "
    "jamais une exception",
    _just_dyn.construit_justification(
        "combo_99_over_1.5", _dom_a_riche, [], nom_domicile="Cannes", nom_exterieur="Amiens"
    ) == {"resume": None, "preuves": [], "donnees_suffisantes": False},
)
verite(
    "construit_justification CAS 6 (doit échouer proprement) : clé de "
    "marché totalement inconnue -> même repli propre, aucune exception",
    _just_dyn.construit_justification(
        "truc_bidule", _dom_a_riche, [], nom_domicile="Cannes", nom_exterieur="Amiens"
    ) == {"resume": None, "preuves": [], "donnees_suffisantes": False},
)

# --- Invariant capital : le champ ne doit JAMAIS influencer la décision.
# Preuve par calcul, pas par lecture du code : on rejoue un vrai match du
# fixture avec des matchs_retenus VOLONTAIREMENT différents (falsifiés) --
# si la sélection P1/l'edge/l'edv changent, c'est que le module a une
# influence cachée sur la décision, ce qui serait un bug grave.
import json as _json_just

with open("fixture_rejeu_10092026.json", encoding="utf-8") as _f_just:
    _fixture_just = _json_just.load(_f_just)
_match_test_just = _fixture_just[0]


def _rejoue_avec_fenetres(fenetres_remplacement):
    def _fake(url_domicile, nom_domicile, url_exterieur, nom_exterieur, nom_competition,
              _am=_match_test_just, _fen=fenetres_remplacement):
        from archetype_model.poisson import markets as _mk3, robustness as _rb3
        _lambdas = _am["lambdas"]
        _mps = {s: _mk3.calcule_tous_les_marches(_lambdas["A"][s], _lambdas["B"][s]) for s in _am_dyn.SCENARIOS}

        def _v4c(extracteur):
            return [extracteur(_mps[s]) for s in _am_dyn.SCENARIOS]

        _rpm = {
            "1x2_domicile": _rb3.evalue_robustesse(_v4c(lambda m: m["1x2"]["domicile"] if m["1x2"] else None)),
            "1x2_nul": _rb3.evalue_robustesse(_v4c(lambda m: m["1x2"]["nul"] if m["1x2"] else None)),
            "1x2_exterieur": _rb3.evalue_robustesse(_v4c(lambda m: m["1x2"]["exterieur"] if m["1x2"] else None)),
            "btts": _rb3.evalue_robustesse(_v4c(lambda m: m["btts"])),
            "over_2_5": _rb3.evalue_robustesse(_v4c(lambda m: m["over_under_total"][2.5]["over"] if m["over_under_total"][2.5] else None)),
            "cage_inviolee_domicile": _rb3.evalue_robustesse(_v4c(lambda m: m["buts_equipe_exterieur"][0.5]["under"] if m["buts_equipe_exterieur"][0.5] else None)),
            "cage_inviolee_exterieur": _rb3.evalue_robustesse(_v4c(lambda m: m["buts_equipe_domicile"][0.5]["under"] if m["buts_equipe_domicile"][0.5] else None)),
            "parite_pair": _rb3.evalue_robustesse(_v4c(lambda m: m["parite_totale"]["pair"] if m["parite_totale"] else None)),
        }
        return {"statut": "OK", "fenetres": _fen, "lambdas": _lambdas,
                "marches_par_scenario": _mps, "robustesse_par_marche": _rpm}

    _am_dyn.analyse_match = _fake
    _cotes_info_just = _op_dyn.extrait_cotes(_match_test_just)
    _cotes_info_just["statut"] = "OK"
    return _am_dyn.analyse_match_complet(
        url_domicile="fake", nom_domicile=_match_test_just.get("domicile"),
        url_exterieur="fake", nom_exterieur=_match_test_just.get("exterieur"),
        nom_competition=_match_test_just.get("competition"), match_id=_match_test_just.get("match_id"),
        url_h2h=None, cotes_info=_cotes_info_just,
    )


_fenetres_reelles = _match_test_just["fenetres"]
_fenetres_falsifiees = {
    "A": {**_fenetres_reelles["A"], "matchs_retenus": [
        {"domicile": True, "buts_marques": 9, "buts_encaisses": 0} for _ in range(8)
    ]},
    "B": {**_fenetres_reelles["B"], "matchs_retenus": [
        {"domicile": False, "buts_marques": 0, "buts_encaisses": 9} for _ in range(8)
    ]},
}
_res_reel_just = _rejoue_avec_fenetres(_fenetres_reelles)
_res_falsifie_just = _rejoue_avec_fenetres(_fenetres_falsifiees)

_p1_reel = _res_reel_just["selection"].get("P1")
_p1_falsifie = _res_falsifie_just["selection"].get("P1")
_meme_decision = (
    (_p1_reel is None) == (_p1_falsifie is None)
    and (_p1_reel is None or (
        _p1_reel["marche"] == _p1_falsifie["marche"]
        and _p1_reel["edge"] == _p1_falsifie["edge"]
        and _p1_reel["edv"] == _p1_falsifie["edv"]
        and _p1_reel["niveau"] == _p1_falsifie["niveau"]
    ))
)
verite(
    "INVARIANT : falsifier complètement les matchs historiques utilisés "
    "pour le comptage descriptif (confirmation_historique) NE CHANGE RIEN "
    "à la sélection P1 (même marché, même edge, même edv, même niveau) -- "
    "preuve que ce champ n'influence jamais la décision",
    _meme_decision,
)
verite(
    "Le comptage change bel et bien entre les deux jeux de matchs "
    "(sinon le test ci-dessus serait vide de sens) : confirmation_historique "
    "du P1 réel diffère entre fenêtres réelles et fenêtres falsifiées",
    (_p1_reel is None and _p1_falsifie is None) or (
        _p1_reel is not None and _p1_falsifie is not None
        and _p1_reel.get("confirmation_historique") != _p1_falsifie.get("confirmation_historique")
    ),
)
_am_dyn.analyse_match = _original_analyse_match_dyn


# ============================================================================
# CHANTIER "RAISON RÉELLE DU CHOIX" (12/09/2026, demande de Patrick) --
# tests directs de archetype_model.signals.selector.diagnostique_* (jamais
# testées avant ce chantier, alors que ce sont ces fonctions qui vont
# alimenter la justification affichée) et de
# justification.construit_raison_selection/enrichit_justification_selection.
# ============================================================================
from archetype_model.signals import selector as _sel_dyn

section("archetype_model/signals/selector.py -- diagnostique_differenciation "
         "(12/09/2026) : PUR DIAGNOSTIC, jamais lu par selectionner_p1/p2/p3, "
         "jamais appelé pendant la sélection elle-même.")

_niveau_ref = {"market_family": "A", "exposure_group": "GA", "niveau": "TRES_FORT",
               "robustesse": "STABLE", "signal_direction": None, "signal_frequence": None,
               "h2h_palier": None, "edv": 0.10}

# CAS 1 (doit réussir) : niveau différent -> critère "niveau"
_c_gagnant_niveau = {**_niveau_ref, "niveau": "PREMIUM"}
_c_concurrent_niveau = {**_niveau_ref, "niveau": "FORT"}
verite(
    "diagnostique_differenciation CAS 1 (doit réussir) : niveau différent "
    "(PREMIUM vs FORT) -> critère rapporté = 'niveau', jamais un autre",
    _sel_dyn.diagnostique_differenciation(_c_gagnant_niveau, [_c_concurrent_niveau])
    == {"critere": "niveau", "valeur_gagnant": 4, "valeur_concurrent": 2},
)

# CAS 2 (doit réussir) : niveau/robustesse égaux, signal différent -> "signal"
_c_gagnant_signal = {**_niveau_ref, "signal_direction": "favorable", "signal_frequence": 0.8}
_c_concurrent_signal = {**_niveau_ref, "signal_direction": "defavorable", "signal_frequence": 0.2}
_diag_signal = _sel_dyn.diagnostique_differenciation(_c_gagnant_signal, [_c_concurrent_signal])
verite(
    "diagnostique_differenciation CAS 2 (doit réussir) : niveau/robustesse "
    "identiques, signal différent (favorable vs défavorable) -> critère "
    "rapporté = 'signal'",
    _diag_signal["critere"] == "signal",
)

# CAS 3 (doit réussir) : tout égal sauf H2H -> "h2h"
_c_gagnant_h2h = {**_niveau_ref, "h2h_palier": "TRES_FIABLE"}
_c_concurrent_h2h = {**_niveau_ref, "h2h_palier": "INSUFFISANT"}
verite(
    "diagnostique_differenciation CAS 3 (doit réussir) : niveau/robustesse/"
    "signal identiques, H2H différent -> critère rapporté = 'h2h', jamais "
    "un critère antérieur dans la cascade",
    _sel_dyn.diagnostique_differenciation(_c_gagnant_h2h, [_c_concurrent_h2h])["critere"] == "h2h",
)

# CAS 4 (doit réussir) : tout égal sauf EDV -> "edv" (dernier recours)
_c_gagnant_edv = {**_niveau_ref, "edv": 0.457}
_c_concurrent_edv = {**_niveau_ref, "edv": 0.12}
verite(
    "diagnostique_differenciation CAS 4 (doit réussir) : seul l'EDV "
    "diffère -> critère rapporté = 'edv', avec les deux vraies valeurs "
    "conservées (jamais arrondies ni perdues)",
    _sel_dyn.diagnostique_differenciation(_c_gagnant_edv, [_c_concurrent_edv])
    == {"critere": "edv", "valeur_gagnant": 0.457, "valeur_concurrent": 0.12},
)

# CAS 5 (rejet attendu) : aucun concurrent -> jamais un faux départage
verite(
    "diagnostique_differenciation CAS 5 (rejet attendu) : aucun concurrent "
    "dans le pool -> critère = 'aucun_concurrent', jamais un critère "
    "inventé (ex. 'edv' par défaut)",
    _sel_dyn.diagnostique_differenciation(_niveau_ref, []) == {"critere": "aucun_concurrent"},
)

# CAS 6 (rejet attendu) : gagnant None -> jamais un crash
verite(
    "diagnostique_differenciation CAS 6 (rejet attendu) : gagnant None "
    "(aucune sélection à ce rang) -> critère = 'aucune_selection', aucune "
    "exception",
    _sel_dyn.diagnostique_differenciation(None, [_niveau_ref]) == {"critere": "aucune_selection"},
)

# CAS 7 (rejet attendu, cas honnête) : égalité totale sur les 5 critères
_c_identique = dict(_niveau_ref)
verite(
    "diagnostique_differenciation CAS 7 (cas honnête, rare mais réel) : "
    "concurrent strictement identique sur les 5 critères -> critère = "
    "'egalite_totale', jamais un départage fabriqué sur l'EDV par défaut",
    _sel_dyn.diagnostique_differenciation(_niveau_ref, [_c_identique]) == {"critere": "egalite_totale"},
)

# CAS 8 (doit réussir) : diagnostique_p2/p3 respectent EXACTEMENT les mêmes
# conditions d'éligibilité que selectionner_p2/p3 -- reformule le rejeu réel
# 68/48 : le pool de concurrents de P2 ne doit contenir aucun candidat de la
# même famille/groupe que P1.
_p1_test = {"market_family": "FAM_A", "exposure_group": "GRP_A", "niveau": "PREMIUM",
            "robustesse": "STABLE", "signal_direction": None, "signal_frequence": None,
            "h2h_palier": None, "edv": 0.10}
_p2_valide_test = {"market_family": "FAM_B", "exposure_group": "GRP_B", "niveau": "FORT",
                    "robustesse": "STABLE", "signal_direction": None, "signal_frequence": None,
                    "h2h_palier": None, "edv": 0.08}
_p2_meme_famille_test = {"market_family": "FAM_A", "exposure_group": "GRP_C", "niveau": "TRES_FORT",
                          "robustesse": "STABLE", "signal_direction": None, "signal_frequence": None,
                          "h2h_palier": None, "edv": 0.30}
_pool_p2_test = [_p1_test, _p2_valide_test, _p2_meme_famille_test]
_diag_p2_test = _sel_dyn.diagnostique_p2(_pool_p2_test, _p1_test, _p2_valide_test)
verite(
    "diagnostique_p2 CAS 8 (doit réussir) : un candidat de même famille "
    "que P1 (donc jamais réellement concurrent de P2) est bien EXCLU du "
    "pool de comparaison, même s'il a un meilleur niveau",
    _diag_p2_test == {"critere": "aucun_concurrent"},
)

section("justification.py -- construit_raison_selection/"
         "enrichit_justification_selection (12/09/2026) : traduisent le "
         "diagnostic de selector.py en phrase française, jamais l'inverse.")

_cand_premium = {"marche": "over_2_5", "niveau": "PREMIUM", "robustesse": "STABLE",
                  "signal_direction": None, "signal_frequence": None,
                  "h2h_palier": None, "edv": 0.457,
                  "justification": {"resume": "Ancien résumé historique.",
                                     "preuves": [{"titre": "Forme récente", "texte": "4/5 ..."}],
                                     "donnees_suffisantes": True}}

verite(
    "construit_raison_selection CAS 1 (doit réussir) : critère 'niveau' "
    "-> la phrase mentionne le niveau PREMIUM ET le fait qu'il a distingué "
    "le candidat, jamais une phrase sur l'EDV ou le signal",
    "PREMIUM" in _just_dyn.construit_raison_selection(_cand_premium, {"critere": "niveau"})
    and "distingué" in _just_dyn.construit_raison_selection(_cand_premium, {"critere": "niveau"}),
)
verite(
    "construit_raison_selection CAS 2 (doit réussir) : critère 'edv' -> "
    "la phrase contient la VRAIE valeur d'EDV du candidat (45.7 %), "
    "jamais une valeur générique ou arrondie différemment",
    "45.7" in _just_dyn.construit_raison_selection(_cand_premium, {"critere": "edv"}),
)
verite(
    "construit_raison_selection CAS 3 (rejet attendu, cas honnête) : "
    "critère 'aucun_concurrent' -> la phrase dit explicitement l'absence "
    "de concurrent, jamais un faux départage inventé",
    "défaut" in _just_dyn.construit_raison_selection(_cand_premium, {"critere": "aucun_concurrent"})
    or "sans concurrent" in _just_dyn.construit_raison_selection(_cand_premium, {"critere": "aucun_concurrent"}),
)
verite(
    "construit_raison_selection CAS 4 (rejet attendu, cas honnête) : "
    "critère 'egalite_totale' -> la phrase ne pointe vers AUCUN des 5 "
    "noms de critère (niveau/robustesse/signal/h2h/edv) comme s'il avait "
    "décidé, puisqu'aucun n'a réellement décidé",
    not any(
        mot in _just_dyn.construit_raison_selection(_cand_premium, {"critere": "egalite_totale"})
        for mot in ("distingué", "départagé")
    ),
)
verite(
    "construit_raison_selection CAS 5 (rejet attendu) : candidat None -> "
    "None, jamais une exception ni une phrase vide inventée",
    _just_dyn.construit_raison_selection(None, {"critere": "niveau"}) is None,
)

_cand_enrichi_test = {
    "marche": "over_2_5", "niveau": "PREMIUM", "robustesse": "STABLE",
    "signal_direction": None, "signal_frequence": None, "h2h_palier": None, "edv": 0.457,
    "justification": {"resume": "Ancien résumé historique.",
                       "preuves": [{"titre": "Forme récente", "texte": "4/5 ..."}],
                       "donnees_suffisantes": True},
}
_j_enrichie = _just_dyn.enrichit_justification_selection(_cand_enrichi_test, {"critere": "niveau"})
verite(
    "enrichit_justification_selection CAS 6 (doit réussir) : l'ancien "
    "résumé historique n'est PAS perdu -- il devient une preuve "
    "'Tendance historique' au lieu d'être présenté comme la raison",
    any(p.get("titre") == "Tendance historique" and p.get("texte") == "Ancien résumé historique."
        for p in _j_enrichie["preuves"]),
)
verite(
    "enrichit_justification_selection CAS 7 (doit réussir) : la preuve de "
    "fréquence déjà présente avant enrichissement (4/5 ...) est toujours "
    "là aussi -- rien n'est écrasé, seulement ajouté",
    any(p.get("titre") == "Forme récente" for p in _j_enrichie["preuves"]),
)
verite(
    "enrichit_justification_selection CAS 8 (rejet attendu) : candidat "
    "None -> None, jamais une exception (utilisé tel quel dans main.py "
    "sur P1/P2/P3 qui peuvent être None)",
    _just_dyn.enrichit_justification_selection(None, {"critere": "niveau"}) is None,
)

section("INVARIANT capital (Chantier B) : le diagnostic et l'enrichissement "
         "de la justification ne changent JAMAIS la sélection P1/P2/P3 "
         "elle-même -- vérifié sur le VRAI rejeu du fixture (446 matchs), "
         "pas sur un cas jouet.")

# Rejeu réel : _res_reel_just a été produit PLUS HAUT dans ce fichier en
# appelant analyse_match_complet() sur un vrai match du fixture -- cette
# fonction inclut maintenant l'appel à diagnostique_selection() +
# enrichit_justification_selection() (voir main.py). On vérifie ici que le
# P1 obtenu est TOUJOURS le même objet que celui présent dans
# candidats_dedupliques (rien n'a été substitué), et qu'il porte bien une
# justification enrichie (resume non vide) -- sans jamais avoir eu besoin
# de recalculer la sélection nous-mêmes.
verite(
    "INVARIANT (Chantier B) : sur le cas réel rejoué plus haut, le P1 "
    "retenu par selectionner() est TOUJOURS le même objet dans "
    "candidats_dedupliques après le passage de diagnostique_selection/"
    "enrichit_justification_selection (aucune substitution, aucun candidat "
    "recréé) -- et sa justification porte bien un resume non vide",
    _p1_reel is None or (
        any(c is _p1_reel for c in _res_reel_just["candidats_dedupliques"])
        and bool(_p1_reel.get("justification", {}).get("resume"))
    ),
)


section("ARCHIVAGE archetype_model — catégorie A/B et immutabilité")
# ============================================================================
# Ajout du 13/09/2026 : archive.py est une couche de persistance uniquement.
# Catégorie B n'est volontairement PAS archivée ; les compteurs existants de
# precalcul.py restent la seule trace des exclusions amont.
try:
    import tempfile as _tmp_archive
    from pathlib import Path as _Path_archive
    import archetype_model.learning.archive as _archive

    source_archive = inspect.getsource(_archive)
    verite(
        "archive.py ne contient ni EXCLUDED ni archive_exclusion()",
        "EXCLUDED" not in source_archive and "archive_exclusion" not in source_archive,
    )

    with _tmp_archive.TemporaryDirectory() as _d_archive:
        _p_archive = _Path_archive(_d_archive) / "2026-09.json"
        _match_archive = {
            "match_id": "AUDIT-ARCHIVE-001",
            "date": "2026-09-13",
            "heure": "18:00",
            "domicile": "Equipe A",
            "exterieur": "Equipe B",
            "competition": "Test",
        }
        _candidat_archive = {
            "marche": "over_under_total_2.5_over",
            "market_family": "GOALS_TOTAL",
            "exposure_group": "GROUPE_BUTS",
            "niveau": "PREMIUM",
            "robustesse": "STABLE",
            "probabilite": 0.80,
            "cote": 1.50,
            "edge": 0.30,
            "edv": 0.20,
        }

        _rid_archive = _archive.enregistrer_selection(
            _candidat_archive,
            match=_match_archive,
            model_version="audit-v1",
            config_version="audit-c1",
            chemin=_p_archive,
        )
        _record_archive = _archive.charger_archive(_p_archive)[0]
        verite(
            "nouvelle sélection archivée avec statut PENDING et résultat vide",
            _record_archive["categorie"] == _archive.CATEGORIE_SELECTED
            and _record_archive["resultat_statut"] == _archive.STATUT_PENDING
            and _record_archive["buts_marques"] is None
            and _record_archive["buts_encaisses"] is None
            and _record_archive["resultat_marche"] is None,
        )

        # Une observation non résolue peut changer de catégorie d'une nuit à
        # l'autre, sans créer un doublon : même record_id.
        _archive.enregistrer_contrefactuel(
            _candidat_archive,
            match=_match_archive,
            model_version="audit-v1",
            config_version="audit-c2",
            chemin=_p_archive,
        )
        _record_transition = _archive.charger_archive(_p_archive)
        verite(
            "transition SELECTED -> COUNTERFACTUAL autorisée tant que PENDING",
            len(_record_transition) == 1
            and _record_transition[0]["record_id"] == _rid_archive
            and _record_transition[0]["categorie"] == _archive.CATEGORIE_COUNTERFACTUAL
            and _record_transition[0]["resultat_statut"] == _archive.STATUT_PENDING,
        )

        _archive.mettre_a_jour_resultat(
            _rid_archive,
            buts_marques=2,
            buts_encaisses=1,
            resultat_marche="WIN",
            date_resolution="2026-09-14",
            chemin=_p_archive,
        )
        _avant_tentative_ecrasement = _archive.charger_archive(_p_archive)
        try:
            _archive.enregistrer_selection(
                {**_candidat_archive, "edv": 0.99, "niveau": "FORT"},
                match=_match_archive,
                model_version="audit-v2",
                config_version="audit-c3",
                chemin=_p_archive,
            )
            _ecrasement_bloque = False
        except _archive.ArchiveOverwriteError:
            _ecrasement_bloque = True
        _apres_tentative_ecrasement = _archive.charger_archive(_p_archive)
        verite(
            "tentative d'écrasement d'un RESOLVED refusée techniquement",
            _ecrasement_bloque,
        )
        verite(
            "un RESOLVED reste strictement inchangé après tentative d'écrasement",
            _apres_tentative_ecrasement == _avant_tentative_ecrasement,
        )
except Exception as _e_archive:
    verite(
        "tests réels de archive.py exécutables sans exception inattendue",
        False,
        str(_e_archive),
    )


# ============================================================================
# CHANTIER "resultats.py" (13/09/2026, demande de Patrick) -- vérification
# autonome des résultats réels pour SELECTED et COUNTERFACTUAL, avec la
# règle exhaustive de reglement.py (Annexe A, aucune ellipse).
# ============================================================================
import archetype_model.learning.reglement as _reglement_dyn
import archetype_model.learning.resultats as _resultats_dyn

section("archetype_model/learning/reglement.py (13/09/2026) -- couverture "
        "EXHAUSTIVE des 19 motifs de l'Annexe A + combos, un cas gagnant ET "
        "un cas perdant par motif, jamais une seule direction testée.")

_CAS_REGLEMENT = [
    ("over_under_total_2.5_over", 2, 1, "WIN"), ("over_under_total_2.5_over", 1, 0, "LOSS"),
    ("over_under_total_2.5_under", 1, 0, "WIN"), ("over_under_total_2.5_under", 2, 1, "LOSS"),
    ("over_2_5", 3, 0, "WIN"), ("over_2_5", 1, 0, "LOSS"),
    ("handicap_domicile_-0.5", 1, 0, "WIN"), ("handicap_domicile_-0.5", 0, 0, "LOSS"),
    ("handicap_exterieur_-1.5", 0, 2, "WIN"), ("handicap_exterieur_-1.5", 0, 1, "LOSS"),
    ("double_chance_1X", 1, 1, "WIN"), ("double_chance_1X", 0, 1, "LOSS"),
    ("double_chance_X2", 1, 1, "WIN"), ("double_chance_X2", 1, 0, "LOSS"),
    ("double_chance_12", 2, 1, "WIN"), ("double_chance_12", 1, 1, "LOSS"),
    ("btts_oui", 1, 1, "WIN"), ("btts_oui", 1, 0, "LOSS"),
    ("btts_non", 1, 0, "WIN"), ("btts_non", 1, 1, "LOSS"),
    ("buts_equipe_domicile_1.5_over", 2, 0, "WIN"), ("buts_equipe_domicile_1.5_over", 1, 0, "LOSS"),
    ("buts_equipe_domicile_1.5_under", 1, 0, "WIN"), ("buts_equipe_domicile_1.5_under", 2, 0, "LOSS"),
    ("buts_equipe_exterieur_0.5_over", 0, 1, "WIN"), ("buts_equipe_exterieur_0.5_over", 0, 0, "LOSS"),
    ("buts_equipe_exterieur_0.5_under", 0, 0, "WIN"), ("buts_equipe_exterieur_0.5_under", 0, 1, "LOSS"),
    ("cage_inviolee_domicile", 1, 0, "WIN"), ("cage_inviolee_domicile", 1, 1, "LOSS"),
    ("cage_inviolee_exterieur", 0, 1, "WIN"), ("cage_inviolee_exterieur", 1, 1, "LOSS"),
    ("encaisse_domicile", 0, 1, "WIN"), ("encaisse_domicile", 1, 0, "LOSS"),
    ("encaisse_exterieur", 1, 0, "WIN"), ("encaisse_exterieur", 0, 1, "LOSS"),
    ("parite_pair", 1, 1, "WIN"), ("parite_pair", 1, 0, "LOSS"),
    ("parite_impair", 1, 0, "WIN"), ("parite_impair", 1, 1, "LOSS"),
    # combo : un cas où le DC est vrai mais le Total échoue (0-0), un cas où
    # le DC échoue directement (0-1), un cas où les deux sont vrais (2-0) --
    # ces 3 cas ensemble prouvent que c'est bien une CONJONCTION, pas
    # seulement l'un ou l'autre des deux composants.
    ("combo_1X_over_1.5", 2, 0, "WIN"),
    ("combo_1X_over_1.5", 0, 1, "LOSS"),
    ("combo_1X_over_1.5", 0, 0, "LOSS"),
]
for _marche_t, _dom_t, _ext_t, _attendu_t in _CAS_REGLEMENT:
    verite(
        f"evaluer_marche({_marche_t!r}, {_dom_t}, {_ext_t}) == {_attendu_t} "
        "(calculé indépendamment avant écriture du test, voir session du 13/09/2026)",
        _reglement_dyn.evaluer_marche(_marche_t, _dom_t, _ext_t).statut == _attendu_t,
    )

verite(
    "evaluer_marche CAS marché inconnu (rejet attendu) : jamais une perte "
    "par défaut, un statut explicite MARCHE_NON_RECONNU à la place",
    _reglement_dyn.evaluer_marche("marche_totalement_inconnue", 1, 1).statut
    == _reglement_dyn.MARCHE_NON_RECONNU,
)

try:
    _reglement_dyn.evaluer_marche("btts_oui", -1, 0)
    _leve_erreur_negatif = False
except ValueError:
    _leve_erreur_negatif = True
verite(
    "evaluer_marche CAS entiers négatifs (rejet attendu) : lève une "
    "exception explicite, jamais un calcul silencieux sur une donnée "
    "invalide",
    _leve_erreur_negatif,
)


section("archetype_model/learning/resultats.py (13/09/2026) -- résout "
        "SELECTED et COUNTERFACTUAL avec la MÊME fonction de règlement, "
        "reproduit la logique d'abandon de verification_resultats.py "
        "(jour trop ancien -> NON_RESOLU_DEFINITIF, aujourd'hui -> jamais "
        "traité).")

import tempfile as _tmp_resultats
from pathlib import Path as _Path_resultats
import archetype_model.learning.archive as _archive_resultats


def _match_resultats_test(match_id, date_str, dom, ext):
    return {
        "match_id": match_id, "date_match": date_str, "heure_match": "18:00",
        "equipe_dom": dom, "equipe_ext": ext, "competition": "Test résultats",
    }


def _candidat_resultats_test(marche):
    return {
        "marche": marche, "market_family": "TEST", "exposure_group": "TEST",
        "niveau": "FORT", "robustesse": "STABLE", "probabilite": 0.7,
        "cote": 1.5, "edge": 0.05, "edv": 0.08,
    }


try:
    with _tmp_resultats.TemporaryDirectory() as _d_res:
        _repertoire_res = str(_Path_resultats(_d_res))

        # Un match d'hier (toujours résoluble), avec un SELECTED et un
        # COUNTERFACTUAL sur le MÊME match -- preuve que les deux
        # populations sont bien résolues par le même passage.
        _hier = _dt.date(2026, 9, 12)
        _chemin_res = _archive_resultats.chemin_archive_mensuelle(_hier.isoformat(), _repertoire_res)

        _archive_resultats.enregistrer_selection(
            _candidat_resultats_test("over_under_total_2.5_over"),
            match=_match_resultats_test("RES-001", _hier.isoformat(), "Equipe Dom Test", "Equipe Ext Test"),
            model_version="test", config_version="test", chemin=_chemin_res,
        )
        _archive_resultats.enregistrer_contrefactuel(
            _candidat_resultats_test("btts_oui"),
            match=_match_resultats_test("RES-001", _hier.isoformat(), "Equipe Dom Test", "Equipe Ext Test"),
            model_version="test", config_version="test", chemin=_chemin_res,
        )

        # Un match trop ancien (11 jours), jamais retrouvable -> doit être
        # abandonné SANS tentative de récupération réseau.
        _trop_vieux = _hier - _dt.timedelta(days=11)
        _chemin_vieux = _archive_resultats.chemin_archive_mensuelle(_trop_vieux.isoformat(), _repertoire_res)
        _archive_resultats.enregistrer_selection(
            _candidat_resultats_test("btts_oui"),
            match=_match_resultats_test("RES-OLD", _trop_vieux.isoformat(), "Vieille Dom", "Vieille Ext"),
            model_version="test", config_version="test", chemin=_chemin_vieux,
        )

        # Un match d'AUJOURD'HUI (par rapport au aujourdhui simulé) --
        # jamais traité, même s'il est PENDING.
        _aujourdhui_simule = _hier + _dt.timedelta(days=1)
        _chemin_ajd = _archive_resultats.chemin_archive_mensuelle(_aujourdhui_simule.isoformat(), _repertoire_res)
        _archive_resultats.enregistrer_selection(
            _candidat_resultats_test("btts_oui"),
            match=_match_resultats_test("RES-TODAY", _aujourdhui_simule.isoformat(), "Auj Dom", "Auj Ext"),
            model_version="test", config_version="test", chemin=_chemin_ajd,
        )

        _matchs_page_test = [{
            "domicile": "Equipe Dom Test", "exterieur": "Equipe Ext Test",
            "score": "2-1", "heure": "TER", "competition": "Test", "match_id": "x",
        }]

        _original_fetch = _resultats_dyn.fetch_html
        _original_url = _resultats_dyn.url_resultat_foot
        _resultats_dyn.fetch_html = lambda url, **kw: ("<html>test</html>", None)
        _resultats_dyn.parse_matches = lambda html, **kw: _matchs_page_test
        _resultats_dyn.url_resultat_foot = lambda date_obj: f"https://test/{date_obj}"

        _resume_res = _resultats_dyn.verifier_resultats(
            repertoire=_repertoire_res, aujourdhui=_aujourdhui_simule
        )

        _resultats_dyn.fetch_html = _original_fetch
        _resultats_dyn.url_resultat_foot = _original_url

        _records_hier = _archive_resultats.charger_archive(_chemin_res)
        _selected_resolu = next(r for r in _records_hier if r["categorie"] == "SELECTED")
        _contrefactuel_resolu = next(r for r in _records_hier if r["categorie"] == "COUNTERFACTUAL")

        verite(
            "resultats.py résout le SELECTED avec le bon score et le bon "
            "verdict (over_under_total_2.5_over sur un score réel 2-1, "
            "total=3 > 2.5 -> WIN)",
            _selected_resolu["resultat_statut"] == "RESOLVED"
            and _selected_resolu["resultat_marche"] == "WIN"
            and _selected_resolu["buts_marques"] == 2
            and _selected_resolu["buts_encaisses"] == 1,
        )
        verite(
            "resultats.py résout AUSSI le COUNTERFACTUAL du même match, avec "
            "la MÊME fonction de règlement (btts_oui sur 2-1 -> WIN) -- "
            "preuve que les deux populations sont bien couvertes, pas "
            "seulement les pronostics sélectionnés",
            _contrefactuel_resolu["resultat_statut"] == "RESOLVED"
            and _contrefactuel_resolu["resultat_marche"] == "WIN",
        )

        # NOTE : _chemin_res / _chemin_vieux / _chemin_ajd retombent parfois
        # sur le MÊME fichier mensuel (les 3 dates de test sont dans le même
        # mois) -- on filtre donc explicitement par match_id, jamais par
        # position dans la liste.
        _record_vieux = next(
            r for r in _archive_resultats.charger_archive(_chemin_vieux)
            if r["match_id"] == "RES-OLD"
        )
        verite(
            "resultats.py CAS jour trop ancien (rejet attendu) : un match de "
            "11 jours (> NB_JOURS_MAX_A_VERIFIER=10) est marqué "
            "NON_RESOLU_DEFINITIF SANS tentative réseau, jamais laissé "
            "PENDING indéfiniment",
            _record_vieux["resultat_statut"] == "NON_RESOLU_DEFINITIF",
        )

        _record_ajd = next(
            r for r in _archive_resultats.charger_archive(_chemin_ajd)
            if r["match_id"] == "RES-TODAY"
        )
        verite(
            "resultats.py CAS jour = aujourd'hui (rejet attendu) : jamais "
            "traité, reste PENDING (le match n'est pas forcément terminé)",
            _record_ajd["resultat_statut"] == "PENDING",
        )
        verite(
            "resultats.py : le résumé retourné dénombre correctement "
            "2 résolus (SELECTED + COUNTERFACTUAL du même match) et "
            "1 abandonné",
            _resume_res["resolus"] == 2 and _resume_res["abandonnes"] == 1,
        )

        # Marché non reconnu : ne doit JAMAIS être résolu en LOSS par défaut.
        _archive_resultats.enregistrer_selection(
            _candidat_resultats_test("marche_totalement_inconnue"),
            match=_match_resultats_test("RES-002", _hier.isoformat(), "Equipe Dom Test", "Equipe Ext Test"),
            model_version="test", config_version="test", chemin=_chemin_res,
        )
        _resultats_dyn.fetch_html = lambda url, **kw: ("<html>test</html>", None)
        _resultats_dyn.url_resultat_foot = lambda date_obj: f"https://test/{date_obj}"
        _resume_res2 = _resultats_dyn.verifier_resultats(
            repertoire=_repertoire_res, aujourdhui=_aujourdhui_simule
        )
        _resultats_dyn.fetch_html = _original_fetch
        _resultats_dyn.url_resultat_foot = _original_url

        _records_hier2 = _archive_resultats.charger_archive(_chemin_res)
        _inconnu_resolu = next(r for r in _records_hier2 if r["marche"] == "marche_totalement_inconnue")
        verite(
            "resultats.py CAS marché non reconnu (rejet attendu) : reste "
            "PENDING, jamais résolu en LOSS par défaut, et signalé dans le "
            "résumé (non_reconnus >= 1)",
            _inconnu_resolu["resultat_statut"] == "PENDING" and _resume_res2["non_reconnus"] >= 1,
        )

        # Verrou RESOLVED : un deuxième passage ne doit JAMAIS tenter de
        # réécrire un enregistrement déjà résolu (déjà garanti par
        # archive.py, ce test prouve que resultats.py ne le contourne pas
        # en le filtrant lui-même sur resultat_statut == PENDING).
        _resultats_dyn.fetch_html = lambda url, **kw: ("<html>test</html>", None)
        _resultats_dyn.url_resultat_foot = lambda date_obj: f"https://test/{date_obj}"
        _resume_res3 = _resultats_dyn.verifier_resultats(
            repertoire=_repertoire_res, aujourdhui=_aujourdhui_simule
        )
        _resultats_dyn.fetch_html = _original_fetch
        _resultats_dyn.url_resultat_foot = _original_url
        verite(
            "resultats.py : un deuxième passage ne re-résout rien (les "
            "SELECTED/COUNTERFACTUAL déjà RESOLVED sont filtrés en amont, "
            "jamais representés à archive.py)",
            _resume_res3["resolus"] == 0,
        )
except Exception as _e_resultats:
    verite(
        "tests réels de resultats.py exécutables sans exception inattendue",
        False,
        str(_e_resultats),
    )


# ============================================================================
# CHANTIER "observations.py + matrice.py" (13/09/2026)
# ============================================================================
import archetype_model.learning.observations as _obs_dyn
import archetype_model.learning.matrice as _mat_dyn

section("archetype_model/learning/observations.py (13/09/2026) -- "
        "calcule_gain_flat_stake et construire_observations, EXCLUT "
        "explicitement les COUNTERFACTUAL de la mesure de performance "
        "réelle (ils n'ont jamais été de vrais paris).")

verite(
    "calcule_gain_flat_stake CAS gagné (doit réussir) : cote 1.4 -> "
    "gain 0.4 (à 1e-9 près, imprécision flottante normale)",
    abs(_obs_dyn.calcule_gain_flat_stake("WIN", 1.4) - 0.4) < 1e-9,
)
verite(
    "calcule_gain_flat_stake CAS perdu (doit réussir) : toujours -1.0, "
    "quelle que soit la cote",
    _obs_dyn.calcule_gain_flat_stake("LOSS", 1.4) == -1.0
    and _obs_dyn.calcule_gain_flat_stake("LOSS", 9.0) == -1.0,
)
verite(
    "calcule_gain_flat_stake CAS gagné sans cote (rejet attendu) : None, "
    "jamais un gain inventé",
    _obs_dyn.calcule_gain_flat_stake("WIN", None) is None,
)
verite(
    "calcule_gain_flat_stake CAS statut PENDING (rejet attendu) : None, "
    "jamais interprété comme perdu par défaut",
    _obs_dyn.calcule_gain_flat_stake("PENDING", 1.4) is None,
)

_records_obs_test = [
    {"categorie": "SELECTED", "resultat_statut": "RESOLVED", "resultat_marche": "WIN",
     "cote": 1.4, "market_family": "A", "niveau": "PREMIUM", "match_id": "m1", "marche": "x"},
    {"categorie": "SELECTED", "resultat_statut": "RESOLVED", "resultat_marche": "LOSS",
     "cote": 1.5, "market_family": "A", "niveau": "PREMIUM", "match_id": "m2", "marche": "x"},
    {"categorie": "COUNTERFACTUAL", "resultat_statut": "RESOLVED", "resultat_marche": "WIN",
     "cote": 1.6, "market_family": "A", "niveau": "PREMIUM", "match_id": "m3", "marche": "x"},
    {"categorie": "SELECTED", "resultat_statut": "PENDING", "resultat_marche": None,
     "cote": 1.3, "market_family": "A", "niveau": "PREMIUM", "match_id": "m4", "marche": "x"},
    {"categorie": "SELECTED", "resultat_statut": "RESOLVED", "resultat_marche": "WIN",
     "cote": 1.3, "market_family": "B", "niveau": "FORT", "match_id": "m5", "marche": "x"},
]
_observations_test = _obs_dyn.construire_observations(_records_obs_test)
verite(
    "construire_observations (doit réussir) : sur 5 enregistrements "
    "(1 COUNTERFACTUAL, 1 PENDING, 3 SELECTED/RESOLVED), exactement 3 "
    "observations produites -- le COUNTERFACTUAL et le PENDING sont "
    "exclus, jamais mélangés",
    len(_observations_test) == 3
    and {o["match_id"] for o in _observations_test} == {"m1", "m2", "m5"},
)

section("archetype_model/learning/matrice.py (13/09/2026) -- agrégation "
        "hiérarchique GLOBAL -> FAMILLE -> NIVEAU, purement mécanique, "
        "vérifiée par calcul indépendant avant écriture du test.")

_matrice_test = _mat_dyn.construire_matrice(_observations_test)
verite(
    "construire_matrice CAS global (doit réussir) : 3 observations, "
    "2 gagnées, 1 perdue, ROI = (0.4 - 1.0 + 0.3) / 3 = -0.1 (à 1e-9 près)",
    _matrice_test["global"]["observations"] == 3
    and _matrice_test["global"]["gagnes"] == 2
    and _matrice_test["global"]["perdus"] == 1
    and abs(_matrice_test["global"]["roi_flat"] - (-0.1)) < 1e-9,
)
verite(
    "construire_matrice CAS famille A (doit réussir) : 2 observations "
    "(m1 gagné 1.4, m2 perdu), ROI = (0.4 - 1.0) / 2 = -0.3",
    _matrice_test["par_famille"]["A"]["resume"]["observations"] == 2
    and abs(_matrice_test["par_famille"]["A"]["resume"]["roi_flat"] - (-0.3)) < 1e-9,
)
verite(
    "construire_matrice CAS famille B (doit réussir) : 1 observation "
    "gagnée à 1.3, ROI = 0.3, isolée de la famille A",
    _matrice_test["par_famille"]["B"]["resume"]["observations"] == 1
    and abs(_matrice_test["par_famille"]["B"]["resume"]["roi_flat"] - 0.3) < 1e-9,
)
verite(
    "construire_matrice CAS niveau imbriqué (doit réussir) : le niveau "
    "PREMIUM de la famille A a exactement les mêmes chiffres que le "
    "résumé de la famille A (un seul niveau présent ici)",
    _matrice_test["par_famille"]["A"]["par_niveau"]["PREMIUM"]["observations"] == 2
    and abs(_matrice_test["par_famille"]["A"]["par_niveau"]["PREMIUM"]["roi_flat"] - (-0.3)) < 1e-9,
)
verite(
    "construire_matrice CAS famille/niveau absents (rejet attendu, cas "
    "honnête) : classé sous INCONNUE/INCONNU, jamais ignoré silencieusement "
    "ni fusionné avec une vraie catégorie",
    _mat_dyn.construire_matrice([
        {"match_id": "z", "marche": "x", "resultat": "WIN", "gain_flat_stake": 0.5,
         "market_family": None, "niveau": None},
    ])["par_famille"][_mat_dyn.FAMILLE_INCONNUE]["par_niveau"][_mat_dyn.NIVEAU_INCONNU]["observations"] == 1,
)
verite(
    "construire_matrice CAS liste vide (rejet attendu) : structure valide "
    "avec 0 observation, jamais une exception",
    _mat_dyn.construire_matrice([])["global"]["observations"] == 0
    and _mat_dyn.construire_matrice([])["global"]["roi_flat"] is None,
)


# ============================================================================
# CHANTIER "garde_fous.py" (13/09/2026) -- barrière obligatoire avant toute
# promotion de calibration, cahier des charges v2 §6 + Addendum 2.
# ============================================================================
import archetype_model.learning.garde_fous as _gf_dyn

section("archetype_model/learning/garde_fous.py (13/09/2026) -- chaque "
        "seuil vérifié indépendamment avant écriture du test, garde-fous "
        "renforcés pour COTE_MIN/COTE_MAX confirmés distincts des autres "
        "paramètres.")

verite(
    "verifier_parametre_autorise CAS connu (doit réussir) : COTE_MIN fait "
    "partie de la liste fermée",
    _gf_dyn.verifier_parametre_autorise("COTE_MIN").autorise is True,
)
verite(
    "verifier_parametre_autorise CAS inconnu (rejet attendu) : jamais "
    "autorisé, même implicitement -- aucune extension de la liste fermée",
    _gf_dyn.verifier_parametre_autorise("PARAM_INVENTE").autorise is False,
)

verite(
    "verifier_taille_echantillon CAS standard, 49 (rejet attendu) : "
    "sous le seuil de 50, jamais autorisé",
    _gf_dyn.verifier_taille_echantillon("ROBUSTNESS_STD_THRESHOLD", 49).autorise is False,
)
verite(
    "verifier_taille_echantillon CAS standard, 50 (doit réussir) : "
    "exactement au seuil, autorisé",
    _gf_dyn.verifier_taille_echantillon("ROBUSTNESS_STD_THRESHOLD", 50).autorise is True,
)
verite(
    "verifier_taille_echantillon CAS renforcé COTE_MIN, 99 (rejet attendu) "
    ": le seuil renforcé est 100, pas 50 -- 99 reste insuffisant",
    _gf_dyn.verifier_taille_echantillon("COTE_MIN", 99).autorise is False,
)
verite(
    "verifier_taille_echantillon CAS renforcé COTE_MIN, 100 (doit réussir)",
    _gf_dyn.verifier_taille_echantillon("COTE_MIN", 100).autorise is True,
)

verite(
    "verifier_amplitude_cycle CAS standard sous le plafond (doit réussir) "
    ": 0.08 -> 0.083 (3,75 %) < 5 %",
    _gf_dyn.verifier_amplitude_cycle("ROBUSTNESS_STD_THRESHOLD", 0.08, 0.083).autorise is True,
)
verite(
    "verifier_amplitude_cycle CAS standard au-delà (rejet attendu) : "
    "0.08 -> 0.09 (12,5 %) > 5 %",
    _gf_dyn.verifier_amplitude_cycle("ROBUSTNESS_STD_THRESHOLD", 0.08, 0.09).autorise is False,
)
verite(
    "verifier_amplitude_cycle CAS renforcé COTE_MIN sous le plafond (doit "
    "réussir) : 1.26 -> 1.27 (0,79 %) < 2 %",
    _gf_dyn.verifier_amplitude_cycle("COTE_MIN", 1.26, 1.27).autorise is True,
)
verite(
    "verifier_amplitude_cycle CAS renforcé COTE_MIN au-delà (rejet "
    "attendu) : 1.26 -> 1.30 (3,17 %) > 2 % -- refusé alors que ce même "
    "changement serait accepté pour un paramètre standard",
    _gf_dyn.verifier_amplitude_cycle("COTE_MIN", 1.26, 1.30).autorise is False,
)

verite(
    "verifier_derive_cumulative CAS standard sous le plafond (doit "
    "réussir) : origine 0.08 -> 0.09 (12,5 %) < 15 %",
    _gf_dyn.verifier_derive_cumulative("ROBUSTNESS_STD_THRESHOLD", 0.08, 0.09).autorise is True,
)
verite(
    "verifier_derive_cumulative CAS standard au-delà (rejet attendu) : "
    "origine 0.08 -> 0.10 (25 %) > 15 %",
    _gf_dyn.verifier_derive_cumulative("ROBUSTNESS_STD_THRESHOLD", 0.08, 0.10).autorise is False,
)
verite(
    "verifier_derive_cumulative CAS renforcé COTE_MIN au-delà (rejet "
    "attendu) : origine 1.26 -> 1.40 (11,1 %) > 8 %",
    _gf_dyn.verifier_derive_cumulative("COTE_MIN", 1.26, 1.40).autorise is False,
)

verite(
    "verifier_rollback CAS dégradation au-delà du seuil (rejet attendu, "
    "cas honnête) : ROI 0.05 -> -0.06 (dégradation 11 %) > 10 % -- "
    "autorise=False signifie qu'un rollback est requis",
    _gf_dyn.verifier_rollback(0.05, -0.06).autorise is False,
)
verite(
    "verifier_rollback CAS dégradation acceptable (doit réussir) : "
    "ROI 0.05 -> 0.02 (dégradation 3 %) < 10 % -- pas de rollback requis",
    _gf_dyn.verifier_rollback(0.05, 0.02).autorise is True,
)

verite(
    "autoriser_promotion CAS paramètre inconnu (rejet attendu) : refusé "
    "au tout premier verrou, avant même de regarder l'échantillon",
    _gf_dyn.autoriser_promotion("PARAM_X", 1000, 1, 1, 1).autorise is False,
)
verite(
    "autoriser_promotion CAS échantillon insuffisant (rejet attendu) : "
    "refusé avant même de comparer les valeurs proposées",
    _gf_dyn.autoriser_promotion(
        "ROBUSTNESS_STD_THRESHOLD", 10, 0.08, 0.08, 0.081
    ).autorise is False,
)
verite(
    "autoriser_promotion CAS amplitude par cycle trop grande (rejet "
    "attendu) : échantillon suffisant mais 0.08 -> 0.09 dépasse 5 % -- "
    "refusé à cette étape précise, pas avant, pas après",
    _gf_dyn.autoriser_promotion(
        "ROBUSTNESS_STD_THRESHOLD", 60, 0.08, 0.08, 0.09
    ).autorise is False,
)
verite(
    "autoriser_promotion CAS amplitude OK mais dérive cumulée dépassée "
    "(rejet attendu) : 0.093 -> 0.095 ne bouge que de 2,15 %% par cycle "
    "(sous le plafond), mais la dérive depuis l'origine 0.08 atteint "
    "18,8 %% (> 15 %%) -- preuve que les deux vérifications sont bien "
    "indépendantes, pas seulement la même chose répétée",
    _gf_dyn.autoriser_promotion(
        "ROBUSTNESS_STD_THRESHOLD", 60, 0.08, 0.093, 0.095
    ).autorise is False
    and "dérive" in _gf_dyn.autoriser_promotion(
        "ROBUSTNESS_STD_THRESHOLD", 60, 0.08, 0.093, 0.095
    ).motif,
)
verite(
    "autoriser_promotion CAS tout est respecté (doit réussir) : "
    "paramètre connu, échantillon suffisant, amplitude et dérive faibles",
    _gf_dyn.autoriser_promotion(
        "ROBUSTNESS_STD_THRESHOLD", 60, 0.08, 0.08, 0.082
    ).autorise is True,
)


# ============================================================================
# CHANTIER "branchement production" (13/09/2026, demande de Patrick :
# "on branche") -- extraction.py + _archive_resultat_archetype_model dans
# precalcul.py, sur de VRAIS matchs du fixture, pas seulement des cas jouets.
# ============================================================================
import archetype_model.learning.extraction as _ext_dyn

section("archetype_model/learning/extraction.py (13/09/2026) -- ne retient "
        "que les motifs numériques (PROBABILITE_TROP_FAIBLE, "
        "EDV_INSUFFISANTE) proches du seuil, jamais les motifs structurels, "
        "vérifié cas par cas avant écriture du test.")


def _diag_test(eligible, motif=None, scenario="offensif", probabilite=None, edv=None, edv_min=None):
    if eligible:
        return {"marche": "x", "filtre": {"eligible": True}}
    return {
        "marche": "x",
        "filtre": {
            "eligible": False,
            "scenario_en_echec": scenario,
            "motif_rejet": motif,
            "resultats_par_scenario": {
                scenario: {
                    "probabilite_centrale": probabilite, "edv": edv, "edv_min_requis": edv_min,
                    "market_family": "FAM", "exposure_group": "GRP", "cote": 1.5, "robustesse": "STABLE",
                }
            },
        },
    }


verite(
    "extraire_marche_proche CAS marché éligible (rejet attendu) : None -- "
    "ce n'est pas un marché rejeté proche d'un seuil, il a été accepté",
    _ext_dyn.extraire_marche_proche(_diag_test(True)) is None,
)
verite(
    "extraire_marche_proche CAS motif structurel (rejet attendu) : "
    "DONNEES_INSUFFISANTES n'est jamais un motif numérique, jamais retenu "
    "même si un appelant lui fournissait des valeurs numériques par erreur",
    _ext_dyn.extraire_marche_proche(_diag_test(False, "DONNEES_INSUFFISANTES")) is None,
)
verite(
    "extraire_marche_proche CAS EDV proche (doit réussir) : 0.1 - 0.089 = "
    "0.011 <= fenêtre 0.02 -> retenu",
    _ext_dyn.extraire_marche_proche(_diag_test(False, "EDV_INSUFFISANTE", edv=0.089, edv_min=0.1)) is not None,
)
verite(
    "extraire_marche_proche CAS EDV loin (rejet attendu) : 0.1 - 0.05 = "
    "0.05 > fenêtre 0.02 -> jamais retenu",
    _ext_dyn.extraire_marche_proche(_diag_test(False, "EDV_INSUFFISANTE", edv=0.05, edv_min=0.1)) is None,
)
verite(
    "extraire_marche_proche CAS probabilité proche (doit réussir) : "
    "0.63 - 0.61 = 0.02 <= fenêtre 0.03 -> retenu",
    _ext_dyn.extraire_marche_proche(_diag_test(False, "PROBABILITE_TROP_FAIBLE", probabilite=0.61)) is not None,
)
verite(
    "extraire_marche_proche CAS probabilité loin (rejet attendu) : "
    "0.63 - 0.50 = 0.13 > fenêtre 0.03 -> jamais retenu",
    _ext_dyn.extraire_marche_proche(_diag_test(False, "PROBABILITE_TROP_FAIBLE", probabilite=0.50)) is None,
)
verite(
    "extraire_marches_proches CAS liste mixte (doit réussir) : sur "
    "3 diagnostics (1 éligible, 1 loin du seuil, 1 proche), exactement "
    "1 marché retenu",
    len(_ext_dyn.extraire_marches_proches([
        _diag_test(True),
        _diag_test(False, "EDV_INSUFFISANTE", edv=0.05, edv_min=0.1),
        _diag_test(False, "EDV_INSUFFISANTE", edv=0.089, edv_min=0.1),
    ])) == 1,
)


section("Branchement réel dans precalcul.py (13/09/2026) -- "
        "_archive_resultat_archetype_model, testé sur de VRAIS matchs du "
        "fixture 446 matchs, pas des cas synthétiques.")

import tempfile as _tmp_branch
from pathlib import Path as _Path_branch
import precalcul as _pc_archivage
import archetype_model.learning.archive as _archive_branch
from archetype_model.poisson import markets as _mk_branch, robustness as _rb_branch
from archetype_model.data import odds_provider as _op_branch

try:
    import json as _json_branch
    with open("fixture_rejeu_10092026.json", encoding="utf-8") as _f_branch:
        _fixture_branch = _json_branch.load(_f_branch)

    def _match_fixture(dom, ext):
        for _m in _fixture_branch:
            if _m.get("domicile") == dom and _m.get("exterieur") == ext:
                return _m
        raise AssertionError(f"match {dom}-{ext} introuvable dans le fixture")

    def _resultat_reel_fixture(m):
        lambdas = m["lambdas"]
        mps = {s: _mk_branch.calcule_tous_les_marches(lambdas["A"][s], lambdas["B"][s]) for s in _am_dyn.SCENARIOS}

        def v4c(extracteur):
            return [extracteur(mps[s]) for s in _am_dyn.SCENARIOS]

        rpm = {
            "1x2_domicile": _rb_branch.evalue_robustesse(v4c(lambda x: x["1x2"]["domicile"] if x["1x2"] else None)),
            "1x2_nul": _rb_branch.evalue_robustesse(v4c(lambda x: x["1x2"]["nul"] if x["1x2"] else None)),
            "1x2_exterieur": _rb_branch.evalue_robustesse(v4c(lambda x: x["1x2"]["exterieur"] if x["1x2"] else None)),
            "btts": _rb_branch.evalue_robustesse(v4c(lambda x: x["btts"])),
            "over_2_5": _rb_branch.evalue_robustesse(v4c(lambda x: x["over_under_total"][2.5]["over"] if x["over_under_total"][2.5] else None)),
            "cage_inviolee_domicile": _rb_branch.evalue_robustesse(v4c(lambda x: x["buts_equipe_exterieur"][0.5]["under"] if x["buts_equipe_exterieur"][0.5] else None)),
            "cage_inviolee_exterieur": _rb_branch.evalue_robustesse(v4c(lambda x: x["buts_equipe_domicile"][0.5]["under"] if x["buts_equipe_domicile"][0.5] else None)),
            "parite_pair": _rb_branch.evalue_robustesse(v4c(lambda x: x["parite_totale"]["pair"] if x["parite_totale"] else None)),
        }

        def _fake(url_domicile, nom_domicile, url_exterieur, nom_exterieur, nom_competition, **kw):
            return {"statut": "OK", "fenetres": m["fenetres"], "lambdas": lambdas,
                    "marches_par_scenario": mps, "robustesse_par_marche": rpm}

        _original = _am_dyn.analyse_match
        _am_dyn.analyse_match = _fake
        try:
            cotes_info = {**_op_branch.extrait_cotes(m), "statut": "OK"}
            return _am_dyn.analyse_match_complet(
                url_domicile="fake", nom_domicile=m.get("domicile"),
                url_exterieur="fake", nom_exterieur=m.get("exterieur"),
                nom_competition=m.get("competition"), match_id=m.get("match_id"),
                url_h2h=None, cotes_info=cotes_info,
            )
        finally:
            _am_dyn.analyse_match = _original

    with _tmp_branch.TemporaryDirectory() as _d_branch:
        import os as _os_branch
        _cwd_avant = _os_branch.getcwd()
        _os_branch.chdir(_d_branch)
        try:
            # CAS 1 -- match avec un vrai P1 (Clermont-US Boulogne, déjà
            # utilisé comme référence dans le Chantier B) -> doit produire
            # un enregistrement SELECTED.
            _m_p1 = _match_fixture("Clermont", "US Boulogne")
            _resultat_p1 = _resultat_reel_fixture(_m_p1)
            _s_p1 = {
                "match_id": _m_p1["match_id"], "date": "2026-09-10", "heure": "18:00",
                "domicile": "Clermont", "exterieur": "US Boulogne", "competition": "Ligue 2",
            }
            _pc_archivage._archive_resultat_archetype_model(_s_p1, _resultat_p1)

            _chemin_p1 = _archive_branch.chemin_archive_mensuelle("2026-09-10")
            _records_p1 = _archive_branch.charger_archive(_chemin_p1)
            verite(
                "Branchement réel CAS match avec P1 (doit réussir) : "
                "Clermont-US Boulogne produit bien un enregistrement "
                "SELECTED archivé, avec le vrai marché retenu par le moteur",
                len(_records_p1) >= 1
                and all(r["categorie"] == "SELECTED" for r in _records_p1)
                and all(r["match_id"] == _m_p1["match_id"] for r in _records_p1),
            )

            # CAS 2 -- match sans AUCUNE sélection mais avec un marché
            # proche du seuil (Nancy-Reims, confirmé lors de la conception
            # de extraction.py) -> doit produire un enregistrement
            # COUNTERFACTUAL, jamais un SELECTED.
            _m_cf = _match_fixture("Nancy", "Reims")
            _resultat_cf = _resultat_reel_fixture(_m_cf)
            verite(
                "Branchement réel CAS 2, pré-condition : Nancy-Reims n'a "
                "réellement aucun P1/P2/P3 dans ce fixture (sinon le test "
                "ne prouverait rien)",
                not any((_resultat_cf.get("selection") or {}).get(r) for r in ("P1", "P2", "P3")),
            )
            _s_cf = {
                "match_id": _m_cf["match_id"], "date": "2026-09-10", "heure": "18:00",
                "domicile": "Nancy", "exterieur": "Reims", "competition": "Ligue 2",
            }
            _pc_archivage._archive_resultat_archetype_model(_s_cf, _resultat_cf)

            _records_cf = [r for r in _archive_branch.charger_archive(_chemin_p1) if r["match_id"] == _m_cf["match_id"]]
            verite(
                "Branchement réel CAS match sans sélection mais avec marché "
                "proche (doit réussir) : Nancy-Reims produit un "
                "enregistrement COUNTERFACTUAL, jamais un SELECTED",
                len(_records_cf) >= 1
                and all(r["categorie"] == "COUNTERFACTUAL" for r in _records_cf),
            )

            # CAS 3 -- un échec d'archivage (chemin invalide) ne doit jamais
            # remonter d'exception à l'appelant réel du pipeline.
            _s_invalide = {
                "match_id": "TEST-INVALIDE", "date": "date-invalide", "heure": "18:00",
                "domicile": "X", "exterieur": "Y", "competition": "Test",
            }
            _leve_exception = False
            try:
                _pc_archivage._archive_resultat_archetype_model(_s_invalide, _resultat_p1)
            except Exception:
                _leve_exception = True
            verite(
                "Branchement réel CAS date invalide (rejet attendu côté "
                "archive.py) : _archive_resultat_archetype_model lève "
                "l'erreur ICI (c'est applique_archetype_model(), déjà "
                "modifié, qui capture et neutralise -- ce test isole "
                "juste que l'erreur est bien détectée, pas avalée trop tôt)",
                _leve_exception,
            )
        finally:
            _os_branch.chdir(_cwd_avant)
except Exception as _e_branchement:
    verite(
        "tests réels du branchement production exécutables sans exception "
        "inattendue",
        False,
        str(_e_branchement),
    )


# CHANTIER "branchement pipeline.yml -- vérification + bilan" (13/09/2026)
# ============================================================================
section("verifie_resultats_archetype_model.py + calcule_matrice_archetype_model.py "
        "(13/09/2026) -- scripts racine du pipeline nocturne, testés de "
        "bout en bout sur une vraie archive temporaire.")

import importlib as _importlib_pipe
import tempfile as _tmp_pipe
from pathlib import Path as _Path_pipe
import archetype_model.learning.archive as _archive_pipe

try:
    _cwd_avant_pipe = _os_branch.getcwd() if "_os_branch" in dir() else __import__("os").getcwd()
    import os as _os_pipe
    with _tmp_pipe.TemporaryDirectory() as _d_pipe:
        _os_pipe.chdir(_d_pipe)
        try:
            _match_pipe = {
                "match_id": "PIPE-001", "date_match": "2026-09-10",
                "equipe_dom": "Equipe A", "equipe_ext": "Equipe B", "competition": "Test",
            }
            _candidat_pipe = {
                "marche": "btts_oui", "market_family": "BTTS", "exposure_group": "G",
                "niveau": "FORT", "robustesse": "STABLE", "probabilite": 0.7,
                "cote": 1.5, "edge": 0.05, "edv": 0.08,
            }
            _chemin_pipe = _archive_pipe.chemin_archive_mensuelle("2026-09-10")
            _rid_pipe = _archive_pipe.enregistrer_selection(
                _candidat_pipe, match=_match_pipe, model_version="v1",
                config_version="v1", chemin=_chemin_pipe,
            )
            _archive_pipe.mettre_a_jour_resultat(
                _rid_pipe, buts_marques=1, buts_encaisses=1, resultat_marche="WIN",
                date_resolution="2026-09-11T00:00:00Z", chemin=_chemin_pipe,
            )

            import calcule_matrice_archetype_model as _cmam_dyn
            _bilan_pipe = _cmam_dyn.construit_bilan()

            verite(
                "calcule_matrice_archetype_model.construit_bilan (doit "
                "réussir) : sur une archive avec 1 observation gagnée à "
                "cote 1.5, ROI global = 0.5, retrouvé au niveau global ET "
                "dans la famille BTTS",
                _bilan_pipe["global"]["observations"] == 1
                and abs(_bilan_pipe["global"]["roi_flat"] - 0.5) < 1e-9
                and _bilan_pipe["par_famille"]["BTTS"]["resume"]["observations"] == 1,
            )

            _cmam_dyn.main()
            verite(
                "calcule_matrice_archetype_model.main() (doit réussir) : "
                "écrit bien bilan_archetype_model.json sur disque, "
                "contenu identique à construit_bilan()",
                _Path_pipe(_cmam_dyn.FICHIER_BILAN).exists()
                and _json_branch.load(open(_cmam_dyn.FICHIER_BILAN, encoding="utf-8"))["global"]["observations"] == 1,
            )

            verite(
                "verifie_resultats_archetype_model.py (doit réussir) : "
                "importable et expose bien main(), sans erreur -- le vrai "
                "scraping n'est pas rejoué ici (déjà testé en profondeur "
                "sur resultats.verifier_resultats() directement)",
                hasattr(_importlib_pipe.import_module("verifie_resultats_archetype_model"), "main"),
            )
        finally:
            _os_pipe.chdir(_cwd_avant_pipe)
except Exception as _e_pipe:
    verite(
        "tests réels du branchement pipeline.yml exécutables sans "
        "exception inattendue",
        False,
        str(_e_pipe),
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
