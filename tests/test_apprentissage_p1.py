import gzip, json, math, os, pytest
import apprentissage_p1 as ap, integration_calibration as ic, calibration_p1 as cp

def jeu(p, f, jours=10, par_jour=20):
    """Jeu deterministe : chaque jour, `par_jour` matchs de probabilite p, dont exactement round(f*par_jour) realises."""
    k = round(f * par_jour); return [(f"2026-10-{j + 1:02d}", p, 1 if i < k else 0) for j in range(jours) for i in range(par_jour)]

# ---- decalage : valeurs connues
def test_decalage_valeur_connue():
    b, se = ap.decalage([.5] * 10, [1] * 7 + [0] * 3); assert abs(b - math.log(.7 / .3)) < 1e-9 and se > 0
def test_decalage_nul_si_calibre():
    b, _ = ap.decalage([.7] * 10, [1] * 7 + [0] * 3); assert abs(b) < 1e-9
def test_decalage_negatif_si_surestime():
    b, _ = ap.decalage([.7] * 10, [1] * 4 + [0] * 6); assert b < 0
@pytest.mark.parametrize("ps,ys", [([], []), ([.5, .6], [1, 1]), ([.5, .6, .7], [0, 0, 0])])
def test_decalage_non_identifiable(ps, ys): assert ap.decalage(ps, ys) is None

# ---- validation : 3 cas qui DOIVENT etre valides (biais net, plusieurs jours)
@pytest.mark.parametrize("p,f", [(.7, .4), (.3, .6), (.55, .25)])
def test_biais_net_est_valide(p, f):
    r = ap.evaluer_marche(jeu(p, f)); assert r["statut"] == "CORRECTION VALIDEE" and r["z_gain"] > ap.Z_SEUIL and r["gain_prospectif_moyen"] > 0 and (r["b"] < 0) == (f < p)

# ---- validation : cas qui NE DOIVENT PAS etre valides
@pytest.mark.parametrize("p,f", [(.5, .5), (.7, .7), (.4, .4)])
def test_marche_calibre_non_valide(p, f):
    r = ap.evaluer_marche(jeu(p, f)); assert r["statut"] == "EN OBSERVATION"
def test_petit_ecart_bruit_non_valide():
    assert ap.evaluer_marche(jeu(.5, .55, jours=2))["statut"] == "EN OBSERVATION"
def test_un_seul_jour_pas_de_prospectif():
    r = ap.evaluer_marche(jeu(.7, .2, jours=1)); assert r["statut"] == "EN OBSERVATION" and r["n_prospectif"] == 0
def test_un_seul_match_et_aucun_match():
    assert ap.evaluer_marche([("2026-11-05", .6, 1)])["statut"] == "EN OBSERVATION" and ap.evaluer_marche([])["statut"] == "EN OBSERVATION"
def test_resultats_tous_identiques():
    r = ap.evaluer_marche([(f"2026-10-{j + 1:02d}", .6, 1) for j in range(8) for _ in range(3)]); assert r["statut"] == "EN OBSERVATION" and r["b"] is None

# ---- pas de fuite : le premier jour n'est jamais evalue, un jour n'utilise que les jours precedents
def test_premier_jour_jamais_evalue():
    r = ap.evaluer_marche(jeu(.7, .4, jours=3)); assert r["n_prospectif"] == 2 * 20
def test_gain_prospectif_recalcule_a_la_main():
    o = jeu(.7, .4, jours=3); g = []
    for j in ("2026-10-02", "2026-10-03"):
        b = ap.decalage([x[1] for x in o if x[0] < j], [x[2] for x in o if x[0] < j])[0]
        g += [ap._perte(x[1], x[2]) - ap._perte(ap._sigm(ap._logit(x[1]) + b), x[2]) for x in o if x[0] == j]
    assert abs(ap.evaluer_marche(o)["gain_prospectif_moyen"] - sum(g) / len(g)) < 1e-12

# ---- application
ETAT = {"marches": {"o15": {"statut": "EN OBSERVATION", "b": .5}, "o25": {"statut": "CORRECTION VALIDEE", "b": -.8}, "o35": {"statut": "EN OBSERVATION", "b": 0}, "btts": {"statut": "CORRECTION VALIDEE", "b": .3}}}
P = {"dom": .5, "nul": .3, "ext": .2, "o15": .8, "o25": .55, "o35": .3, "btts": .5}
def test_corriger_applique_seulement_les_valides():
    q = ap.corriger(ETAT, P); assert q["o25"] < P["o25"] and q["btts"] > P["btts"] and q["o15"] == P["o15"] and q["o35"] == P["o35"] and all(q[k] == P[k] for k in ("dom", "nul", "ext"))
def test_corriger_garde_l_ordre_des_buts():
    q = ap.corriger({"marches": {"o15": {"statut": "CORRECTION VALIDEE", "b": -3}}}, P); assert q["o15"] >= q["o25"] >= q["o35"]
def test_corriger_sans_etat_ou_observation_est_identite():
    assert ap.corriger(None, P) == P and ap.corriger({"marches": {k: {"statut": "EN OBSERVATION", "b": 1} for k in ap.MARCHES}}, P) == P

# ---- journal reel : seulement les matchs gele AVANT le coup d'envoi ET termines ; refus si journal altere
def _rec(i, ko): return {"statut": "OK", "match_id": f"m{i}", "date": ko[:10], "competition": "C", "division": "E0", "domicile": "A", "exterieur": "B", "coup_d_envoi_utc": ko, "mode": "parallele", "p1_original": P, "p1_calibre": P, "methode": {}, "detail": {}, "n_historique_competition": 9}
def _monde(tmp, scores):
    ic.ecrire([_rec(i, "2026-11-02T19:00:00Z") for i in (1, 2, 3)], cp.charger(), str(tmp), maintenant="2026-11-01T10:00:00Z"); f = tmp / "f"; os.makedirs(f)
    with gzip.open(f / "2026-11-10.json.gz", "wt") as h: json.dump({k: {"match_id": k, "score": v} for k, v in scores.items()}, h)
    return str(tmp), str(f)
def test_construire_compte_seulement_les_termines(tmp_path):
    d, f = _monde(tmp_path, {"m1": {"buts_dom": 2, "buts_ext": 1}, "m2": {"buts_dom": 0, "buts_ext": 0}, "m3": None})
    e = ap.construire(d, f); assert e["matchs_termines"] == 2 and e["corrections_validees"] == [] and e["marches"]["o25"]["n"] == 2
def test_construire_refuse_un_journal_altere(tmp_path):
    d, f = _monde(tmp_path, {"m1": {"buts_dom": 2, "buts_ext": 1}}); ch = os.path.join(d, "journal.jsonl"); t = open(ch).read().replace('"domicile":"A"', '"domicile":"Z"', 1); open(ch, "w").write(t)
    with pytest.raises(RuntimeError): ap.construire(d, f)
def test_construire_est_deterministe(tmp_path):
    d, f = _monde(tmp_path, {"m1": {"buts_dom": 2, "buts_ext": 1}}); assert ap.construire(d, f) == ap.construire(d, f)
