"""Tests du classement du Journal fondé sur des preuves (journal_classement.py, mode « preuves »).

Règle du dépôt : toute fonction de comparaison est testée sur au moins 3 cas qui passent et 3 qui échouent.
"""
import random
import re
from pathlib import Path

import pytest

import generateur_tickets as gt
import journal_classement as jc
import journal_rentabilite as jr
import selection_adaptative as sa

CAL = {"n": 200, "a": 0.0, "b": 1.0, "c": 0.0}   # calibrage neutre : p_cal = p_lissée, borne basse = p - 1,96 * sqrt(p(1-p)/200)


def cand(i, cote=1.60, lissee=0.80, joues=10, stab=0.8, **extra):
    c = {"match_id": f"m{i}", "date": "2026-10-10", "domicile": f"D{i}", "exterieur": f"E{i}", "marche": "Victoire",
         "cote": cote, "lissee": lissee, "joues": joues, "stabilite": stab}
    c.update(extra)
    return c


# --- briques de calcul -------------------------------------------------------------------------------------------------

def test_borne_basse_wilson_valeurs_connues():
    assert jc.borne_basse_wilson(5, 5) == pytest.approx(0.5655, abs=1e-3)
    assert jc.borne_basse_wilson(0, 0) is None
    assert jc.borne_basse_wilson(8, 10) < 0.8 < jc.borne_basse_wilson(80, 100) + 0.1


@pytest.mark.parametrize("w,n,base", [(5, 5, 0.5), (8, 10, 0.4), (0, 6, 0.3), (6, 6, 0.0)])
def test_lissee_identique_a_selection_adaptative_cas_valides(w, n, base):
    assert jc.lissee(w, n, base) == pytest.approx(sa.journal_probabilite_lissee(w, n, base))


@pytest.mark.parametrize("w,n,base", [(5, 0, 0.5), (7, 5, 0.5), (3, 5, None), (3, 5, 1.2), (-1, 5, 0.5)])
def test_lissee_refuse_les_cas_invalides(w, n, base):
    assert jc.lissee(w, n, base) is None and sa.journal_probabilite_lissee(w, n, base) is None


def _donnees(n, regle):
    """n candidats passés : p_lissée alterne 0,5 / 0,7 et la cote cycle 1,5 / 2,0 / 2,5 (indépendantes l'une de l'autre) ;
    `regle(lissee, cote)` donne le résultat réel."""
    out = []
    for i in range(n):
        lis, cote = (0.5, 0.7)[i % 2], (1.5, 2.0, 2.5)[i % 3]
        out.append({"lissee": lis, "cote": cote, "resultat": 1 if regle(lis, cote) else -1})
    return out


@pytest.mark.parametrize("n", [0, 10, 29])
def test_calibrage_donnees_insuffisantes_rien_n_est_publiable(n):
    assert jc.ajuste_calibrage(_donnees(n, lambda l, c: True)) is None


def test_calibrage_ignore_les_lignes_sans_cote():
    sans_cote = [{"lissee": 0.6, "cote": None, "resultat": 1} for _ in range(50)]
    assert jc.ajuste_calibrage(sans_cote) is None
    assert jc.ajuste_calibrage(sans_cote + _donnees(30, lambda l, c: l > 0.6))["n"] == 30


def test_calibrage_garde_la_frequence_du_journal_seulement_si_elle_apporte_quelque_chose():
    utile = jc.ajuste_calibrage(_donnees(60, lambda l, c: l > 0.6))                  # le résultat suit la fréquence du Journal
    assert utile["modele"] == "a+b+c" and utile["b"] > 0.5 and abs(utile["c"]) < 1e-6
    marche = jc.ajuste_calibrage(_donnees(60, lambda l, c: c < 1.6))                 # le résultat suit la cote seulement
    assert marche["c"] > 0 and abs(marche["b"]) < 1e-6
    inutile = jc.ajuste_calibrage(_donnees(60, lambda l, c: l < 0.6 and c < 1.6))    # fréquence du Journal à contre-courant
    assert inutile["modele"] == "a+c" and inutile["b"] == 0.0 and inutile["c"] > 0


def test_calibrage_repli_sur_le_marche_quand_rien_n_est_utile():
    cal = jc.ajuste_calibrage(_donnees(60, lambda l, c: c > 2.2))                   # les favoris perdent : aucune pente positive
    assert cal == {"n": 60, "a": 0.0, "b": 0.0, "c": 1.0, "modele": "marche"}
    # le repli reproduit la probabilité du marché : jamais d'avantage, jamais d'admissible
    assert jc.proba_calibree(cal, 0.99, 0.5) == pytest.approx(0.5)
    assert not jc.evalue(cand(1, 2.00, 0.99), cal)["admissible"]


def test_proba_calibree_bornee():
    assert jc.proba_calibree({"n": 40, "a": 2.0, "b": 0.0, "c": 0.0}, 0.5) == 0.99
    assert jc.proba_calibree({"n": 40, "a": -2.0, "b": 0.0, "c": 0.0}, 0.5) == 0.01
    assert jc.proba_calibree({"n": 40, "a": 0.0, "b": 1.0}, 0.7) == pytest.approx(0.7)       # ancienne forme sans « c »


@pytest.mark.parametrize("cal,cote,attendu", [
    ({"n": 200, "a": 0.20, "b": 0.0, "c": 0.90}, 2.50, True),    # p = 0,56 pour 40 % impliqué : écart démontré
    ({"n": 400, "a": 0.30, "b": 0.0, "c": 0.80}, 3.00, True),
    ({"n": 200, "a": 0.00, "b": 0.5, "c": 0.60}, 2.00, True),    # 0,35 + 0,30 = 0,65 pour 50 %
    ({"n": 200, "a": -0.10, "b": 0.0, "c": 1.06}, 2.00, False),  # le marché moins une marge : jamais d'avantage
    ({"n": 200, "a": 0.0, "b": 0.0, "c": 1.0}, 1.60, False),
    ({"n": 30, "a": 0.20, "b": 0.0, "c": 0.90}, 2.50, False),    # même modèle, trop peu d'observations : borne trop large
])
def test_le_marche_est_le_point_de_depart(cal, cote, attendu):
    assert jc.evalue(cand(1, cote, 0.99), cal)["admissible"] is attendu


# --- admissibilité -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("c", [cand(1, 1.60, 0.85), cand(2, 1.40, 0.95), cand(3, 2.00, 0.85)])
def test_evalue_admissibles(c):
    e = jc.evalue(c, CAL)
    assert e["admissible"] and e["motifs"] == [] and e["borne_basse"] >= 1 / c["cote"]
    assert e["ev"] == pytest.approx(e["p_cal"] * c["cote"] - 1)


@pytest.mark.parametrize("c,cal,motif", [
    (cand(1, 1.80, 0.56), CAL, "BORNE_BASSE_INF_IMPLICITE"),    # 56 % annoncé pour une cote 1,80 (55,6 % impliqué) : écart non démontré
    (cand(2, 1.60, 0.62), CAL, "BORNE_BASSE_INF_IMPLICITE"),    # borne basse 55 % < 62,5 % impliqué
    (cand(3, 1.20, 0.99), CAL, "COTE_HORS_FENETRE"),
    (cand(4, 3.50, 0.99), CAL, "COTE_HORS_FENETRE"),
    (cand(5, None, 0.80), CAL, "COTE_ABSENTE"),
    (cand(6, 1.60, 0.80), None, "CALIBRAGE_ABSENT"),
    (cand(7, 1.60, None), CAL, "PROBABILITE_NON_VERIFIABLE"),
])
def test_evalue_rejets(c, cal, motif):
    e = jc.evalue(c, cal)
    assert not e["admissible"] and motif in e["motifs"]


# --- sélection : maximum, rien de forcé, doublons, ordre, déterminisme -------------------------------------------------

def test_maximum_quinze_meme_avec_quarante_admissibles():
    cs = [cand(i, 1.60, 0.90 - i * 0.001) for i in range(40)]
    retenus, rejetes = jc.selectionne(cs, CAL)
    assert len(retenus) == 15 and len(rejetes) == 25 and all(r["motifs"] == ["AU_DELA_DU_MAXIMUM"] for r in rejetes)


def test_six_admissibles_donnent_six_jamais_complete():
    cs = [cand(i) for i in range(6)] + [cand(10 + i, 1.80, 0.56) for i in range(30)]
    retenus, rejetes = jc.selectionne(cs, CAL)
    assert len(retenus) == 6 and all(r["motifs"] == ["BORNE_BASSE_INF_IMPLICITE"] for r in rejetes)


def test_aucun_admissible_donne_liste_vide():
    retenus, rejetes = jc.selectionne([cand(i, 1.80, 0.56) for i in range(12)], CAL)
    assert retenus == [] and len(rejetes) == 12
    assert jc.selectionne([cand(i) for i in range(5)], None)[0] == []                             # sans calibrage : rien n'est fiable


def test_un_seul_pari_par_match_le_mieux_classe():
    a = cand(1, 1.60, 0.90, marche="Match à moins de 3,5 buts")
    b = {**a, "marche": "Les deux équipes marquent", "lissee": 0.84}
    retenus, rejetes = jc.selectionne([b, a], CAL)
    assert [r["marche"] for r in retenus] == ["Match à moins de 3,5 buts"]
    assert [r["motifs"] for r in rejetes] == [["MEME_MATCH_MIEUX_CLASSE"]]


def test_priorite_fiabilite_avant_esperance_avant_stabilite_avant_volume():
    sure = cand(1, 1.40, 0.97, stab=0.1, joues=5)                      # très fiable, faible espérance
    risquee = cand(2, 2.00, 0.88, stab=0.9, joues=40)                  # espérance plus forte, fiabilité plus basse
    assert [r["match_id"] for r in jc.selectionne([risquee, sure], CAL)[0]] == ["m1", "m2"]
    # fiabilité et probabilité égales : l'espérance départage, puis la stabilité, puis le volume
    base = dict(cote=1.60, lissee=0.90)
    x, y = cand(3, stab=0.9, joues=10, **base), cand(4, stab=0.5, joues=10, **base)
    assert [r["match_id"] for r in jc.selectionne([y, x], CAL)[0]] == ["m3", "m4"]
    p, q = cand(5, stab=0.7, joues=30, **base), cand(6, stab=0.7, joues=8, **base)
    assert [r["match_id"] for r in jc.selectionne([q, p], CAL)[0]] == ["m5", "m6"]


def test_classement_deterministe_quel_que_soit_l_ordre_d_entree():
    cs = [cand(i, 1.50 + (i % 5) * 0.1, 0.80 + (i % 7) * 0.02, joues=5 + i % 9) for i in range(40)]
    ref = [r["match_id"] for r in jc.selectionne(cs, CAL)[0]]
    for graine in (1, 2, 3):
        m = cs[:]
        random.Random(graine).shuffle(m)
        assert [r["match_id"] for r in jc.selectionne(m, CAL)[0]] == ref


def test_un_rejete_ne_reintegre_jamais_la_selection():
    cs = [cand(i) for i in range(8)] + [cand(20 + i, 1.80, 0.56) for i in range(8)] + [cand(40, 5.0, 0.99)]
    retenus, rejetes = jc.selectionne(cs, CAL)
    assert {r["match_id"] for r in retenus}.isdisjoint({r["match_id"] for r in rejetes})
    assert all(jc.evalue(r, CAL)["admissible"] for r in retenus)


# --- anti-fuite et reconstruction --------------------------------------------------------------------------------------

def _synth(seed=7, equipes=8, jours=30):
    rnd = random.Random(seed)
    noms = [f"Eq{i}" for i in range(equipes)]
    out, k = [], 0
    for j in range(jours):
        ordre = noms[:]
        rnd.shuffle(ordre)
        for i in range(0, equipes, 2):
            h, a = ordre[i], ordre[i + 1]
            gh = rnd.choice([0, 1, 2, 3]) if h != "Eq0" else rnd.choice([2, 3, 3, 4])
            ga = rnd.choice([0, 1, 2]) if a != "Eq0" else rnd.choice([2, 3, 3])
            k += 1
            out.append({"match_id": f"m{k}", "date": f"2026-09-{1 + j:02d}", "ligue": "Ligue Test", "domicile": h,
                        "exterieur": a, "buts": (gh, ga),
                        "cotes": {lib: 1.8 for ld, le in jr.MARCHES_EQUIPE.values() for lib in (ld, le)}})
    return out


def test_walk_forward_ne_voit_pas_le_futur():
    ms = _synth()
    complet = jc.candidats_walk_forward(jr, ms, premier_jour="2026-09-01")
    assert len(complet) > 50
    jour = "2026-09-15"
    avant = [r for r in complet if r["date"] <= jour]
    # 1. retirer tout le futur ne change aucun candidat passé
    assert jc.candidats_walk_forward(jr, [m for m in ms if m["date"] <= jour], premier_jour="2026-09-01") == avant
    # 2. changer les scores du futur ne change aucun candidat passé
    bouge = [{**m, "buts": (m["buts"][1] + 3, m["buts"][0])} if m["date"] > jour else m for m in ms]
    assert [r for r in jc.candidats_walk_forward(jr, bouge, premier_jour="2026-09-01") if r["date"] <= jour] == avant


def test_les_candidats_d_un_jour_n_utilisent_que_les_matchs_anterieurs():
    ms = _synth()
    jour = "2026-09-20"
    rows = [r for r in jc.candidats_walk_forward(jr, ms, premier_jour="2026-09-01") if r["date"] == jour]
    assert rows
    for r in rows:
        passes = [m for m in ms if m["date"] < jour and r["equipe"] in (m["domicile"], m["exterieur"])]
        assert r["joues"] == len(passes)


def test_marche_du_match_entier_compte_une_fois_par_match():
    rows = jc.candidats_walk_forward(jr, _synth(), premier_jour="2026-09-01")
    entier = jc.marches_du_match_entier(jr)
    assert entier and "Match à plus de 2,5 buts" in entier and "Victoire" not in entier
    vus = [(r["match_id"], r["marche"]) for r in rows if r["marche"] in entier]
    assert len(vus) == len(set(vus))


def test_charge_calibrage_avec_donnees_valides_et_erreur_remontee():
    ok = jc.charge_calibrage("2026-09-30", matchs=_synth())
    assert ok["erreur"] is None and ok["calibrage"] is not None and ok["observations"] > 0 and isinstance(ok["stabilite"], dict)
    ko = jc.charge_calibrage("2026-09-30", matchs=[{"date": "2026-09-01"}])                       # données corrompues
    assert ko["calibrage"] is None and ko["erreur"]                                              # erreur visible, jamais masquée
    vide = jc.charge_calibrage("2026-09-30", matchs=[])
    assert vide["calibrage"] is None


def test_le_journal_reste_independant_des_moteurs():
    src = Path(jc.__file__).read_text(encoding="utf-8")
    imports = re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][\w.]*)", src, flags=re.M)
    assert set(imports) <= {"__future__", "math", "collections", "typing", "journal_rentabilite"}, imports
    assert "moteur_v2" not in src.replace("V2 et V3", "") and "moteur_v3" not in src


# --- intégration : selection_adaptative (mode « preuves ») -------------------------------------------------------------

def _ligne(**extra):
    row = {"equipe": "Equipe Test", "ligue": "Ligue Test", "marche": "Match à moins de 3,5 buts", "gagnes": 8, "joues": 10,
           "frequence": 0.8, "frequence_generale": 0.5, "roi_betpawa": 0.1,
           "prochain_match": {"date": "2099-10-10", "heure": "15:00", "adversaire": "Adv", "lieu": "domicile",
                              "cote_betpawa": 1.60, "betpawa_url": "https://example.invalid/e"}}
    row.update(extra)
    return row


CLASSEMENT = {"calibrage": {"n": 400, "a": 0.0, "b": 1.0},
              "stabilite": {("Equipe Test", "Ligue Test", "Match à moins de 3,5 buts"): 0.75}}


def test_mode_preuves_utilise_la_probabilite_calibree_et_marque_l_admissibilite():
    c = sa._journal_team_market_candidate(_ligne(), "preuves", CLASSEMENT)
    lis = (8 + 20 * 0.5) / 30
    assert c["probabilite_source"] == "JOURNAL_CALIBRE" and c["probabilite_estimee"] == pytest.approx(lis, abs=1e-5)
    assert c["journal_stabilite"] == pytest.approx(0.75) and c["journal_calibrage"] == "preuves"
    assert c["journal_admissible"] is False and "BORNE_BASSE_INF_IMPLICITE" in c["journal_motifs_rejet"]   # 60 % annoncé, cote 1,60
    fort = sa._journal_team_market_candidate(_ligne(gagnes=40, joues=40, frequence=1.0, frequence_generale=0.9), "preuves", CLASSEMENT)
    assert fort["journal_admissible"] is True and fort["journal_motifs_rejet"] == []


def test_mode_preuves_sans_calibrage_rien_n_est_admissible():
    for classement in (None, {}, {"calibrage": None, "erreur": "boom"}):
        c = sa._journal_team_market_candidate(_ligne(), "preuves", classement)
        assert c["journal_admissible"] is False and "CALIBRAGE_ABSENT" in c["journal_motifs_rejet"]
        assert gt.eligible({**c, "cote": 1.6}) is False


def test_enrich_garde_la_probabilite_calibree_et_classe_les_non_admissibles_en_dernier():
    bon = sa._journal_team_market_candidate(_ligne(gagnes=40, joues=40, frequence=1.0, frequence_generale=0.9), "preuves", CLASSEMENT)
    mauvais = sa._journal_team_market_candidate(_ligne(equipe="Autre"), "preuves", CLASSEMENT)
    out = sa.enrich([mauvais, bon], {"par_marche": {}}, None)
    assert all(x["probabilite_source"] == "JOURNAL_CALIBRE" for x in out)
    assert out[1]["probabilite_estimee"] == pytest.approx(bon["probabilite_estimee"])
    assert out[1]["_ordre"] > out[0]["_ordre"]


def test_extract_journal_candidates_mode_preuves_et_diagnostic():
    journal = {"equipes_a_suivre": [_ligne()]}
    rows = sa.extract_journal_candidates(journal, {"signaux": []}, "preuves", CLASSEMENT)
    assert rows[0]["probabilite_source"] == "JOURNAL_CALIBRE" and sa.DIAGNOSTIC_CLASSEMENT["n"] == 400
    sa.extract_journal_candidates(journal, {"signaux": []}, "wilson")
    assert sa.DIAGNOSTIC_CLASSEMENT == {}                                                        # autres modes : rien de changé


@pytest.mark.parametrize("contenu,attendu", [('{"mode": "preuves"}', "preuves"), ('{"mode": "PREUVES"}', "preuves"),
                                             ('{"mode": "wilson"}', "wilson"), ('{"mode": "inconnu"}', "wilson"),
                                             ('pas du json', "wilson")])
def test_interrupteur_accepte_preuves_et_retombe_sur_wilson_sinon(tmp_path, contenu, attendu):
    f = tmp_path / "cfg.json"
    f.write_text(contenu, encoding="utf-8")
    assert sa.journal_mode(f) == attendu
    assert sa.journal_mode(tmp_path / "absent.json") == "wilson"


# --- intégration : générateur de tickets -------------------------------------------------------------------------------

def _pari(i, admissible, low=0.70, p=0.80, cote=1.60, **extra):
    c = {"source": "journal", "probabilite_source": "JOURNAL_CALIBRE", "match_id": None, "date": "2099-10-10", "heure": "15:00",
         "domicile": f"D{i}", "exterieur": f"E{i}", "marche": "Match à moins de 3,5 buts", "cote": cote,
         "probabilite_estimee": p, "journal_admissible": admissible, "journal_borne_basse_calibree": low,
         "journal_stabilite": 0.8, "journal_observations": 10}
    c.update(extra)
    return c


def test_eligibilite_exige_l_admissibilite_pour_le_journal_calibre():
    assert gt.eligible(_pari(1, True)) is True
    assert gt.eligible(_pari(2, False)) is False                       # rejeté : probabilité haute et marge positive n'y changent rien
    assert gt.eligible(_pari(3, None)) is False
    assert gt.eligible(_pari(4, False), "prudent") is False
    assert gt.eligible({**_pari(5, False), "probabilite_source": "JOURNAL_WILSON"}) is True       # anciens modes inchangés


def test_un_rejete_au_meilleur_rang_n_entre_ni_dans_le_pool_ni_dans_un_ticket():
    rejetes = [_pari(100 + i, False, low=0.99, p=0.99) for i in range(5)]                         # « meilleurs » sur le papier
    admis = [_pari(i, True, low=0.70 - i * 0.001) for i in range(8)]
    data = {"sources": {"journal": {"candidats": rejetes + admis}}}
    retenus, _ = gt.selection_par_source(data)
    assert {x["domicile"] for x in retenus["journal"]} == {f"D{i}" for i in range(8)}
    out = gt.build(data)
    interdits = {f"D{100 + i}" for i in range(5)}
    assert not interdits & {x["domicile"] for x in out["pool"]}
    for sc in out["scenarios"]:
        assert not interdits & {x["domicile"] for x in sc["selection"]}


def test_le_classement_calibre_prime_et_le_generateur_le_respecte():
    a, b = _pari(1, True, low=0.80, p=0.90), _pari(2, True, low=0.70, p=0.99, cote=1.5)
    assert gt.candidate_rank(a) > gt.candidate_rank(b)                                            # fiabilité avant probabilité
    assert gt.candidate_rank(_pari(3, True, low=0.50)) > gt.candidate_rank(_pari(4, False, low=0.99))
    retenus, _ = gt.selection_par_source({"sources": {"journal": {"candidats": [b, a]}}})
    assert [x["domicile"] for x in retenus["journal"]] == ["D1", "D2"]


def test_generateur_un_seul_pari_du_journal_par_match_et_quinze_au_maximum():
    m1 = _pari(1, True, low=0.80)
    m1b = {**m1, "marche": "Les deux équipes marquent", "journal_borne_basse_calibree": 0.75}
    beaucoup = [_pari(10 + i, True, low=0.70 - i * 0.001) for i in range(25)]
    retenus, _ = gt.selection_par_source({"sources": {"journal": {"candidats": [m1b, m1] + beaucoup}}})
    j = retenus["journal"]
    assert len(j) == 15 and [x["marche"] for x in j if x["domicile"] == "D1"] == ["Match à moins de 3,5 buts"]


def test_six_admis_six_publies_aucun_complement():
    data = {"sources": {"journal": {"candidats": [_pari(i, True) for i in range(6)] + [_pari(50 + i, False) for i in range(20)]}}}
    retenus, _ = gt.selection_par_source(data)
    assert len(retenus["journal"]) == 6


def test_resume_classement_compte_les_admissibles_et_les_motifs():
    bons = [sa._journal_team_market_candidate(_ligne(equipe=f"B{i}", gagnes=40, joues=40, frequence=1.0, frequence_generale=0.9),
                                              "preuves", {"calibrage": {"n": 400, "a": 0.0, "b": 1.0, "c": 0.0}, "stabilite": {}}) for i in range(2)]
    mauvais = [sa._journal_team_market_candidate(_ligne(equipe=f"M{i}"), "preuves", CLASSEMENT) for i in range(3)]
    r = sa.resume_classement(sa.enrich(bons + mauvais, {"par_marche": {}}, None))
    assert r["candidats"] == 5 and r["admissibles"] == 2 and r["motifs_de_rejet"] == {"BORNE_BASSE_INF_IMPLICITE": 3}
    assert len(r["plus_proches_du_seuil"]) == 3 and all(x["borne_basse"] < x["probabilite_implicite"] for x in r["plus_proches_du_seuil"])
    assert sa.resume_classement([]) == {"candidats": 0, "admissibles": 0, "motifs_de_rejet": {}, "plus_proches_du_seuil": []}


def test_le_script_de_backtest_s_execute_et_rapporte_les_quatre_variantes():
    import importlib.util
    chemin = Path(jc.__file__).parent / "evaluation" / "backtest_journal_preuves.py"
    spec = importlib.util.spec_from_file_location("backtest_journal_preuves", chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    res = mod.execute(jc.candidats_walk_forward(jr, _synth(), premier_jour="2026-09-01"))
    assert {"ANCIEN_WILSON", "ANCIEN_LISSE", "PROBABILITE_SEULE", "NOUVEAU_PREUVES", "TOUS_LES_CANDIDATS", "brier"} <= set(res)
    assert res["candidats"] > 50 and res["NOUVEAU_PREUVES"]["total"]["variante"] == "NOUVEAU_PREUVES"
