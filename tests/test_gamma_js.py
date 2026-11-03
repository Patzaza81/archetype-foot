"""Page Gamma = Omega V3 : exécute archetype_gamma.js sous Node avec un document factice (affichages, vocabulaire, aucune probabilité inventée)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node absent")

SCRIPT = """
global.document = {getElementById: () => null, body: {classList: {toggle() {}}}, createElement: () => ({})};
global.window = {};
const g = require(process.argv[1]);
const [fn, ...args] = JSON.parse(process.argv[2]);
console.log(JSON.stringify(g[fn](...args)));
"""


def appel(fn: str, *args):
    r = subprocess.run(["node", "-e", SCRIPT, str(ROOT / "archetype_gamma.js"), json.dumps([fn, *args])], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


F = {"domicile": "Arezzo", "exterieur": "Ascoli"}
PARI = {"k": 400, "n": 625, "f": 0.64, "g": 0.6, "seuil": 0.55, "p_calibree": 0.72, "cote": 1.4, "p_implicite": 0.714, "ev": 0.008,
        "niveaux": {"strict": {"k": 30, "n": 50, "f": 0.6}, "intermediaire": {"k": 100, "n": 200, "f": 0.5}, "elargi": {"k": 300, "n": 500, "f": 0.6, "faible": True}},
        "stabilite": {"f_min": 0.6, "f_max": 0.66}, "diversite": {}}


@pytest.mark.parametrize("cle,attendu", [
    (["1x2", "1"], "Victoire Arezzo"), (["1x2", "N"], "Match nul"), (["double_chance", "1N"], "Arezzo ou match nul"),
    (["btts", "Oui"], "Les deux équipes marquent"), (["over_under_2.5", "plus"], "Plus de 2,5 buts"),
])
def test_phrase_des_marches_qui_passent(cle, attendu):
    assert attendu in appel("gaPhrase", cle, "Arezzo", "Ascoli")["titre"]


@pytest.mark.parametrize("cle,interdit", [(["1x2", "1"], "Ascoli"), (["over_under_2.5", "plus"], "Moins de"), (["over_under_2.5", "moins"], "Plus de")])
def test_phrase_des_marches_qui_ne_doivent_pas_apparaitre(cle, interdit):
    assert interdit not in appel("gaPhrase", cle, "Arezzo", "Ascoli")["titre"]


def test_frequence_jamais_presentee_comme_une_probabilite():
    t = appel("gaFreqPari", PARI, F)
    assert "400 scénarios sur 625" in t and "n'est pas une probabilité" in t and "Fréquence robuste" in t
    assert "trop peu représenté" in t and "BetPawa" not in t
    assert "EV" not in t and "Edge" not in t                                            # ni EV ni Edge : la cote n'est qu'une condition d'accès
    assert appel("gaFreqPari", None, F) == ""


def test_aucune_ev_ni_edge_dans_la_page_ni_dans_le_moteur():
    import re
    from pathlib import Path
    racine = Path(__file__).resolve().parent.parent
    js = (racine / "archetype_gamma.js").read_text(encoding="utf-8")
    assert "gaEv" not in js and not re.search(r"\bEV\b|\bEdge\b|\bEDV\b", js)
    for f in ("coeur.py", "suivi.py"):
        t = (racine / "moteur_omega_v3" / f).read_text(encoding="utf-8")
        assert '"ev"' not in t and "ecart_implicite" not in t
    t = appel("gaFreqPari", {**PARI, "ev": 0.5}, F)
    assert "EV" not in t


def test_statuts_et_aucun_mot_betpawa():
    assert "retenu" in appel("gaStatut", 6) and appel("gaStatut", 99) == "—"
    assert all("BetPawa" not in appel("gaStatut", c) for c in range(8))


def test_sequences_affichees_et_absentes():
    f = {**F, "donnees": {"sequences": {"att_a": [2, 1, 0, 1, 3], "def_a": [0] * 5, "att_b": [1] * 5, "def_b": [2] * 5}, "source": "archive"}}
    t = appel("gaSequences", f)
    assert "[2, 1, 0, 1, 3]" in t and "5 matchs" in t and "pas des matchs indépendants" in t
    assert appel("gaSequences", F) == ""


def test_exploration_et_tous_marches_sans_donnees_ne_cassent_pas():
    assert appel("gaExploration", F) == "" and appel("gaTousMarches", F) == ""
    assert appel("gaSurveiller", F) == ""
    x = {**F, "exploration": {"combinaisons": 625, "scores_distincts": 12, "issues": {"A": 300, "N": 100, "B": 225}, "concentration_top3": 0.4,
                              "top_scores": [{"score": "2-1", "occurrences": 100, "f": 0.16}]},
         "niveaux": {"strict": {"n": 50, "part": 0.08}, "incompatible": {"n": 0, "part": 0}}}
    t = appel("gaExploration", x)
    assert "625 scénarios" in t and "Victoire de Arezzo" in t and "jamais un pronostic retenu" in t


@pytest.mark.parametrize("cle,attendu", [
    (["handicap_3issues_-1", "1"], "Arezzo gagne par 2 buts d'écart ou plus"), (["handicap_3issues_-1", "X"], "Arezzo gagne d'exactement 1 but d'écart"),
    (["handicap_3issues_-1", "2"], "Ascoli ne perd pas"), (["handicap_3issues_2", "2"], "Ascoli gagne par 3 buts d'écart ou plus"),
    (["nombre_exact_buts", "3"], "Exactement 3 buts dans le match"), (["nombre_exact_buts", "6+"], "6 buts ou plus dans le match"),
    (["btts_total_2.5", "Oui|plus"], "Les deux équipes marquent et au moins 3 buts dans le match"), (["over_under_9.5", "plus"], "Plus de 9,5 buts"),
])
def test_phrases_des_marches_ajoutes_par_l_audit(cle, attendu):
    assert appel("gaPhrase", cle, "Arezzo", "Ascoli")["titre"] == attendu


@pytest.mark.parametrize("cle", [["handicap_3issues_-1", "1"], ["nombre_exact_buts", "2"], ["btts_total_3.5", "Non|moins"], ["over_under_8.5", "moins"]])
def test_aucune_cle_technique_dans_les_phrases(cle):
    t = appel("gaPhrase", cle, "Arezzo", "Ascoli")["titre"]
    assert "_" not in t and "|" not in t


def test_raison_meme_evenement_affichee_en_clair():
    f = {**F, "a_surveiller": [{"cle": ["over_under_0.5", "plus"], "raison": "même événement que cages_inviolees_exterieur|non"}]}
    t = appel("gaSurveiller", f)
    assert "même événement que Ascoli encaisse au moins 1 but" in t and "cages_inviolees" not in t


def _surv(*entrees):
    return appel("gaSurveiller", {**F, "a_surveiller": list(entrees)})


CB = {"cle": ["over_under_domicile_0.5", "plus"], "g": 0.5, "cote": 1.22, "raison": "seuil atteint mais cote 1,22 < 1,26"}
SC = {"cle": ["handicap_1.5", "domicile"], "g": 0.8, "raison": "seuil atteint mais aucune cote disponible : pari injouable"}
DB = {"cle": ["double_chance", "1N"], "g": 0.75, "raison": "même événement que handicap_3issues_1|1"}


def test_surveiller_chaque_marche_avec_sa_frequence_robuste():
    t = _surv(CB, SC, DB)
    assert "fréquence robuste <b>50 %</b>" in t and "fréquence robuste <b>80 %</b>" in t and "fréquence robuste <b>75 %</b>" in t


def test_surveiller_groupes_par_cause():
    t = _surv(CB, SC, DB)
    i0, i1, i2 = t.index("Cote sous le minimum (1)"), t.index("Aucune cote disponible (1)"), t.index("Même événement qu'un pari retenu")
    assert i0 < t.index("fréquence robuste <b>50 %</b>") < i1 < t.index("fréquence robuste <b>80 %</b>") < i2 < t.index("fréquence robuste <b>75 %</b>")


def test_surveiller_tri_par_frequence_decroissante_dans_un_groupe():
    t = _surv(CB, {**CB, "cle": ["cages_inviolees_exterieur", "non"], "g": 0.7})
    assert t.index("<b>70 %</b>") < t.index("<b>50 %</b>")


def test_surveiller_un_groupe_vide_n_est_pas_affiche():
    t = _surv(CB)
    assert "Aucune cote disponible" not in t and "Même événement" not in t


def test_surveiller_sans_frequence_ne_casse_pas_et_aucune_cle_technique():
    t = _surv({"cle": ["double_chance", "1N"], "raison": "même événement que handicap_3issues_1|1"})
    assert "fréquence robuste" not in t and "handicap_3issues" not in t and "|" not in t


def test_surveiller_pas_de_coupure_a_12():
    t = _surv(*[{**CB, "cle": ["over_under_domicile_0.5", "plus"]} for _ in range(15)])
    assert t.count("fréquence robuste") == 15 and "… et" not in t
