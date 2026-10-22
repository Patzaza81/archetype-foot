"""Affichage V2R aligné sur les autres moteurs (date, heure, drapeau, carte dépliable) + derniers scores des deux équipes."""
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from moteur_v2r import modere as MOD, pronostics as P, regles as R  # noqa: E402
from tests.test_v2r_autonome import joues, match  # noqa: E402

RACINE = pathlib.Path(__file__).parent.parent


def h(date, dom, bm, be, adv="X"):
    return dict(date=date, domicile=dom, buts_marques=bm, buts_encaisses=be, adversaire=adv)


# ---- forme : 3 cas qui passent, 3 qui échouent
def test_forme_cas_qui_passent():
    hist = [h("2026-09-01", True, 2, 1), h("2026-09-20", False, 0, 3, "Lyon"), h("2026-09-10", True, 1, 1)]
    f = P.forme(hist)
    assert [x["date"] for x in f] == ["2026-09-20", "2026-09-10", "2026-09-01"]                      # du plus récent au plus ancien
    assert f[0] == dict(date="2026-09-20", adversaire="Lyon", lieu="E", bm=0, be=3)                   # lieu E pour un match à l'extérieur
    assert f[1]["lieu"] == "D" and (f[1]["bm"], f[1]["be"]) == (1, 1)
    assert len(P.forme([h(f"2026-09-{i:02d}", True, 1, 0) for i in range(1, 15)])) == P.NB_FORME == 6  # 6 derniers seulement
    assert P.forme([h("2026-09-01", True, 1, 0)], n=3)[0]["bm"] == 1


def test_forme_cas_qui_echouent():
    assert P.forme([]) == [] and P.forme(None) == []                                                  # pas d'historique : liste vide, pas d'erreur
    longue = [h(f"2026-09-{i:02d}", True, 1, 0) for i in range(1, 15)]
    assert "2026-09-01" not in [x["date"] for x in P.forme(longue)]                                   # les plus anciens sont écartés
    assert all(x["lieu"] == "E" for x in P.forme([h("2026-09-01", False, 0, 0)]))                     # extérieur ≠ domicile
    sans_adv = P.forme([dict(date="2026-09-01", domicile=True, buts_marques=1, buts_encaisses=1)])
    assert sans_adv[0]["adversaire"] is None                                                          # adversaire absent toléré


def test_le_pari_officiel_porte_la_forme_et_pas_les_variantes_modérées():
    r = R.entraine(joues(12), "2026-10-13")
    m = match("n", "2026-10-14", h=None, a=None, kickoff="2026-10-14T18:00:00Z")
    p = P.proposer(m, r)
    assert set(p["forme"]) == {"domicile", "exterieur"} and len(p["forme"]["domicile"]) <= 6
    v = MOD.variante(p, m["cotes"], 1)
    assert v is not None and "forme" not in v                                                         # carnets modérés non alourdis
    assert "forme" in p                                                                               # le pari officiel garde sa forme


# ---- page
def test_page_utilise_la_meme_carte_que_les_autres_moteurs():
    js = (RACINE / "archetype_v2r.js").read_text(encoding="utf-8")
    html = (RACINE / "pronostics_v2r.html").read_text(encoding="utf-8")
    corps = js[js.index("function v2rCarte"):js.index("function v2rListe")]
    for classe in ("ax-carte", "ax-replie", "ax-match", "ax-ligne-match", "ax-equipe ax-dom", "ax-horaire", "ax-competition", "ax-details"):
        assert classe in corps, classe
    assert "ax-hist" in js and "ax-res-v" in js and "ax-res-n" in js and "ax-res-d" in js          # pastilles colorées comme les autres moteurs
    assert "af-drapeaux-cartes.js" in html and "drapeaux.js" in html                                 # drapeau du pays du championnat
    assert 'class="ax-liste-matchs v2r-tout"' in html and html.count("<main") == 1                  # le script drapeaux observe main.ax-liste-matchs
    assert corps.index("ax-horaire") < corps.index("v2r-corps") < corps.index("ax-details")        # en-tête, pari, puis derniers scores
    assert "Derniers scores indisponibles" in js
    assert "function v2rExplication(l)" in js
    assert "meilleur rendement dans les données ayant servi à établir ses règles" in js
    assert "ne suffisent pas à justifier ce choix" in js                                                      # anciens paris sans forme : message, pas d'erreur
    assert corps.index("v2rBlocModere(l, mode)") < corps.index("ax-details")                         # pari modéré toujours sous le pari d'origine


def test_cartes_v2r_construites_par_dom_pas_par_chaine():
    js = (RACINE / "archetype_v2r.js").read_text(encoding="utf-8")
    assert "document.createElement(\"section\")" in js and "el.appendChild(v2rCarte(l, mode))" in js
