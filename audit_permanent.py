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
    "run_pipeline.py construit bien signal['TOUS_MARCHES_EVALUES']",
    'signal["TOUS_MARCHES_EVALUES"]' in source_run_pipeline,
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
print("\n" + "=" * 70)
if echecs:
    print(f"AUDIT ÉCHOUÉ -- {len(echecs)} vérité(s) fausse(s) :")
    for e in echecs:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("AUDIT OK -- toutes les vérités connues sont confirmées par calcul.")
    sys.exit(0)
