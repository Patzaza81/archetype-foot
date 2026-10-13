"""Tests de base_protocole.py (protocole BASE / SUPER BASE v4, docs/PROTOCOLE_BASE.md).

Les données sont synthétiques, sauf la reproduction du § 10, qui lit l'archive au commit 7c532a7 (ignorée si ce commit
n'est pas disponible dans le clone)."""
import datetime as dt
import gzip
import json
import os
import subprocess
from pathlib import Path

import pytest

import base_protocole as bp

np = bp.np   # numpy arrive avec pandas sur le runner ; pas d'import direct dans les tests (test_integrite_du_depot)

UTC = dt.timezone.utc
MAINT = dt.datetime(2026, 12, 20, 12, tzinfo=UTC)


def fiche(mid, ko, cote=1.33, plus=3.2, score=(1, 1), pris_delta_h=8, date=None, **extra):
    ko_dt = ko if isinstance(ko, dt.datetime) else dt.datetime.fromisoformat(ko).replace(tzinfo=UTC)
    m = {"match_id": mid, "date": date or ko_dt.date().isoformat(), "coup_d_envoi_utc": ko_dt.isoformat().replace("+00:00", "Z"),
         "run": {"pris_le": (ko_dt - dt.timedelta(hours=pris_delta_h)).isoformat().replace("+00:00", "Z")},
         "cotes_betpawa": {"over_under_3.5": {"moins": cote, "plus": plus}},
         "domicile": f"Dom {mid}", "exterieur": f"Ext {mid}", "competition": "Pays : Ligue",
         "score": {"buts_dom": score[0], "buts_ext": score[1]} if score else {},
         "equipe_dom": {"matchs": []}, "equipe_ext": {"matchs": []}}
    m.update(extra)
    return m


def admet(*fiches, statuts=None, maintenant=MAINT, modifies=frozenset()):
    return bp.admet({"f.json.gz": {f["match_id"]: f for f in fiches}}, statuts or {}, maintenant, set(modifies))


# --- § 4.2 : admission -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("cote,dedans", [(1.27, True), (1.39, True), (1.33, True), (1.26, False), (1.40, False), (1.5, False)])
def test_bornes_de_h1_incluses(cote, dedans):
    a = admet(fiche("a", "2026-10-20T15:00:00", cote=cote))
    assert (len(a.matchs) == 1) is dedans


@pytest.mark.parametrize("modif,motif", [
    ({"run": {}}, "HORODATAGE_ABSENT"),
    ({"coup_d_envoi_utc": None}, "HORODATAGE_ABSENT"),
    ({"run": {"pris_le": "2026-10-20T15:30:00Z"}}, "RELEVE_APRES_COUP_D_ENVOI"),
    ({"run": {"pris_le": "2026-10-20T15:00:00Z"}}, "RELEVE_APRES_COUP_D_ENVOI"),   # égalité = après
    ({"cotes_betpawa": {"over_under_3.5": {"moins": "abc"}}}, "ERREUR_COLLECTE"),
    ({"score": {"buts_dom": "x", "buts_ext": 1}}, "ERREUR_COLLECTE"),
])
def test_chaque_motif_d_exclusion_est_compte(modif, motif):
    f = fiche("a", "2026-10-20T15:00:00")
    f.update(modif)
    a = admet(f)
    assert a.matchs == [] and a.exclusions[motif] == ["a"]


def test_cote_absente_est_hors_univers_et_pas_une_exclusion():
    f = fiche("a", "2026-10-20T15:00:00")
    f["cotes_betpawa"] = {}
    a = admet(f)
    assert a.matchs == [] and a.hors_univers == 1 and a.exclusions == {}


def test_modification_detectee_exclut_le_match():
    a = admet(fiche("a", "2026-10-20T15:00:00"), modifies={"a"})
    assert a.exclusions["MODIFICATION_DETECTEE"] == ["a"]


def test_meme_match_avec_deux_scores_differents_est_une_erreur_de_collecte():
    f1 = fiche("a", "2026-10-20T15:00:00", score=(1, 0), pris_delta_h=20)
    f2 = fiche("a", "2026-10-20T15:00:00", score=(3, 2), pris_delta_h=5)
    a = bp.admet({"j1.json.gz": {"a": f1}, "j2.json.gz": {"a": f2}}, {}, MAINT)
    assert a.matchs == [] and a.exclusions["ERREUR_COLLECTE"] == ["a"]


def test_doublon_on_garde_le_releve_le_plus_recent_avant_le_coup_d_envoi():
    vieux = fiche("a", "2026-10-20T15:00:00", cote=1.30, pris_delta_h=30)
    recent = fiche("a", "2026-10-20T15:00:00", cote=1.36, pris_delta_h=2)
    a = bp.admet({"j1.json.gz": {"a": recent}, "j2.json.gz": {"a": vieux}}, {}, MAINT)
    assert len(a.matchs) == 1 and a.matchs[0].cote == 1.36 and a.doublons[0]["releves"] == 2


# --- § 4.3 : résultats manquants --------------------------------------------------------------------------------------

@pytest.mark.parametrize("score,statut_src,age_j,attendu", [
    ((1, 1), None, 10, "REGLE"),
    (None, None, 3, "NON_REGLE"),
    (None, "REP", 10, "ANNULE"),
    (None, "ANL", 10, "ANNULE"),
    (None, "SUS", 10, "SUSPENDU"),
    (None, None, 10, "RESULTAT_MANQUANT"),
    ((2, 0), "REP", 10, "REGLE"),          # statut source périmé : le score l'emporte
])
def test_statut_de_resultat(score, statut_src, age_j, attendu):
    ko = MAINT - dt.timedelta(days=age_j)
    a = admet(fiche("a", ko, score=score), statuts={"a": statut_src} if statut_src else {})
    assert a.matchs[0].statut == attendu


def test_un_resultat_absent_n_est_jamais_compte_perdu():
    jours = ["2026-10-20"]
    gagne = fiche("g", "2026-10-20T12:00:00", score=(1, 0))
    absent = fiche("x", "2026-10-20T15:00:00", score=None)
    m = admet(gagne, absent).matchs
    mes = bp.mesures(m, jours, 0.025, None)
    assert mes["matchs"] == 1 and mes["reussite"] == 1.0 and mes["roi"] == pytest.approx(0.33)


def test_un_pari_perdu_est_compte():
    m = admet(fiche("p", "2026-10-20T12:00:00", score=(3, 1)), fiche("g", "2026-10-20T15:00:00", score=(0, 0))).matchs
    mes = bp.mesures(m, ["2026-10-20"], 0.025, None)
    assert mes["matchs"] == 2 and mes["roi"] == pytest.approx((0.33 - 1) / 2)


# --- § 6.2 : rapprochement du Journal (3 doivent correspondre, 3 ne doivent pas) ---------------------------------------

def _m(dom="Queen's Park", ext="Inverness CT", date="2026-10-20", ko="2026-10-20T18:00:00"):
    f = fiche("z", ko, date=date)
    f["domicile"], f["exterieur"] = dom, ext
    return admet(f).matchs[0]


def _pari(dom="Queen's Park", ext="Inverness CT", date="2026-10-20", vu="2026-10-20T06:00:00+00:00"):
    return [(date, bp.nom_normalise(dom), bp.nom_normalise(ext), bp.instant(vu))]


@pytest.mark.parametrize("pari", [
    _pari(),                                         # identique
    _pari(dom="QUEEN'S PARK", ext="inverness ct"),   # casse
    _pari(dom="  Queen's   Park ", ext="Invérness CT"),   # espaces en trop, accent
])
def test_journal_rapproche(pari):
    assert bp.rapproche_journal(_m(), pari)


@pytest.mark.parametrize("pari", [
    _pari(dom="Inverness CT", ext="Queen's Park"),   # équipes inversées
    _pari(date="2026-10-19"),                        # autre date
    _pari(vu="2026-10-20T18:30:00+00:00"),           # vu après le coup d'envoi
])
def test_journal_ne_rapproche_pas(pari):
    assert not bp.rapproche_journal(_m(), pari)


def test_limite_connue_apostrophe_typographique_non_rapprochee():
    """Même normalisation que generateur_tickets._nom_normalise : « ’ » est supprimé, « ' » devient un espace. Les deux
    sources (archive et générateur) viennent de Matchendirect et écrivent le même caractère ; la limite est documentée."""
    assert not bp.rapproche_journal(_m(), _pari(dom="Queen’s Park"))


# --- § 5 : traçabilité -------------------------------------------------------------------------------------------------

def test_registre_en_ajout_seul(tmp_path):
    reg = tmp_path / "e.jsonl"
    bp.ajoute_registre([{"evenement": "reference", "match_id": "a", "type": "score", "sha256": "1"}], reg)
    avant = reg.read_text()
    bp.ajoute_registre([{"evenement": "reference", "match_id": "a", "type": "score", "sha256": "2"}], reg)
    assert reg.read_text().startswith(avant)
    assert bp.references(bp.lit_registre(reg))[("", "a", "score")] == "1"     # la première référence fait foi


def test_detection_des_modifications():
    f = fiche("a", "2026-10-20T15:00:00", score=(1, 0))
    avant, score = bp.empreintes(f)
    refs = {("j", "a", "avant_match"): avant, ("j", "a", "score"): score}
    assert bp.detecte({"j": {"a": f}}, refs, MAINT) == []
    f2 = json.loads(json.dumps(f)); f2["cotes_betpawa"]["over_under_3.5"]["moins"] = 1.30
    f3 = json.loads(json.dumps(f)); f3["score"]["buts_dom"] = 2
    assert [e["type"] for e in bp.detecte({"j": {"a": f2}}, refs, MAINT)] == ["avant_match"]
    assert [e["type"] for e in bp.detecte({"j": {"a": f3}}, refs, MAINT)] == ["score"]
    f4 = json.loads(json.dumps(f)); f4["score"]["ecrit_le"] = "2026-10-21T04:00:00Z"   # horodatage seul réécrit
    assert bp.detecte({"j": {"a": f4}}, refs, MAINT) == []
    assert bp.detecte({"autre": {"a": f2}}, refs, MAINT) == []   # même match, autre fichier : sa propre référence


def _commit(repo, contenu, date):
    p = repo / "data/archive_test/2026-10-20.json.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(json.dumps(contenu).encode()))
    env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", date], check=True, env=env)


def test_premiere_observation_reconstruite_depuis_git(tmp_path):
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    sans = fiche("a", "2026-10-20T15:00:00", score=None)
    _commit(tmp_path, {"a": sans}, "2026-10-20T10:00:00+00:00")                         # avant le coup d'envoi
    fige = json.loads(json.dumps(sans)); fige["run"]["pris_le"] = "2026-10-20T14:00:00Z"
    _commit(tmp_path, {"a": fige}, "2026-10-20T20:00:00+00:00")                         # premier commit après
    avec = json.loads(json.dumps(fige)); avec["score"] = {"buts_dom": 1, "buts_ext": 0}
    _commit(tmp_path, {"a": avec}, "2026-10-21T02:00:00+00:00")
    triche = json.loads(json.dumps(avec)); triche["cotes_betpawa"]["over_under_3.5"]["moins"] = 1.39
    _commit(tmp_path, {"a": triche}, "2026-10-22T02:00:00+00:00")
    src = bp.Source("main", tmp_path)
    chemin = "data/archive_test/2026-10-20.json.gz"
    refs = bp.premieres_observations(bp.versions_git(src, chemin), chemin)
    r = {(l["type"]): l for l in refs}
    assert r["avant_match"]["date_commit"].startswith("2026-10-20T20") and r["avant_match"]["sha256"] == bp.empreintes(fige)[0]
    assert r["score"]["date_commit"].startswith("2026-10-21T02")
    ev = bp.detecte({chemin: {"a": triche}}, bp.references(refs), MAINT)
    assert [e["type"] for e in ev] == ["avant_match"]


# --- § 7, § 9 : mesures, statuts, points de contrôle --------------------------------------------------------------------

def test_student_et_bootstrap_encadrent_le_roi():
    rng = np.random.default_rng(1)
    s, n = rng.normal(0, 3, 30), np.full(30, 15.0)
    st = bp.student_grappes(s, n, 0.025)
    bs = bp.bootstrap_roi(s, n, 0.025, bp.tirages_jours(30, 5000, 1))
    roi = s.sum() / n.sum()
    assert st[0] < roi < st[1] and bs[0] < roi < bs[1]


@pytest.mark.parametrize("st,bs,attendu", [
    ([0.01, 0.05], [0.02, 0.06], "VALIDE"),
    ([0.01, 0.05], [-0.01, 0.06], "NEUTRE"),       # une seule méthode positive : pas VALIDÉ
    ([-0.08, -0.01], [-0.07, -0.02], "DEFAVORABLE"),
    ([-0.08, 0.01], [-0.07, -0.02], "NEUTRE"),
])
def test_valide_exige_les_deux_methodes(st, bs, attendu):
    assert bp.statut_b0({"roi_intervalle_student": st, "roi_intervalle_bootstrap": bs}) == attendu


def _archive_test(jours=45, par_jour=16, p=0.80, debut="2026-10-13", manquants=0, graine=3):
    rng = np.random.default_rng(graine)
    d0 = dt.date.fromisoformat(debut)
    out = {}
    for j in range(jours):
        jour = d0 + dt.timedelta(days=j)
        fiches = {}
        for i in range(par_jour):
            mid = f"m{j}_{i}"
            sc = (1, 1) if rng.random() < p else (3, 1)
            if manquants and i < manquants:
                sc = None
            fiches[mid] = fiche(mid, dt.datetime(jour.year, jour.month, jour.day, 15, tzinfo=UTC), cote=1.33, score=sc)
        out[f"data/archive_test/{jour.isoformat()}.json.gz"] = fiches
    return out


def _ecrit(racine, archive):
    for chemin, contenu in archive.items():
        p = racine / chemin
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(gzip.compress(json.dumps(contenu).encode()))


def test_prefixe_independant_du_jour_de_calcul():
    a = admet(*[f for c in _archive_test().values() for f in c.values()])
    f1 = bp.fenetre(a.matchs, dt.datetime(2026, 11, 20, tzinfo=UTC))
    f2 = bp.fenetre(a.matchs, dt.datetime(2026, 12, 20, tzinfo=UTC))
    p1, p2 = bp.prefixe(f1, 300, 20), bp.prefixe(f2, 300, 20)
    assert [m.match_id for m in p1] == [m.match_id for m in p2]
    assert len({m.jour for m in p1}) == 20 and len(p1) >= 300


def test_le_statut_ne_change_qu_a_un_point_de_controle_et_ecrit_seulement_dans_la_sortie(tmp_path):
    racine, sortie = tmp_path / "depot", tmp_path / "depot/data/base"
    _ecrit(racine, _archive_test(jours=45, p=0.95))
    avant = {p for p in racine.rglob("*") if p.is_file()}
    src = bp.Source(None, racine)
    e1 = bp.execute(src, dt.datetime(2026, 10, 25, tzinfo=UTC), sortie, n_sim=2000, b=2000)
    assert e1["statut_B0"] in ("NON_EVALUE", "EN_COURS") and e1["points_de_controle_atteints"] == []
    e2 = bp.execute(src, dt.datetime(2026, 11, 12, tzinfo=UTC), sortie, n_sim=2000, b=2000)
    assert e2["points_de_controle_atteints"] == ["C1"]
    c1 = json.loads((sortie / "points_de_controle.json").read_text())[0]
    e3 = bp.execute(src, dt.datetime(2026, 11, 20, tzinfo=UTC), sortie, n_sim=2000, b=2000)
    assert e3["points_de_controle_atteints"] == ["C1"] and e3["statut_B0"] == c1["statut_B0"]
    apres = {p for p in racine.rglob("*") if p.is_file()}
    assert {p.relative_to(racine).parts[:2] for p in apres - avant} == {("data", "base")}


def test_controle_de_sensibilite_rend_non_concluant():
    archive = _archive_test(jours=22, par_jour=18, p=0.9, manquants=3)
    a = admet(*[f for c in archive.values() for f in c.values()])
    pris = bp.prefixe(bp.fenetre(a.matchs, MAINT), 300, 20)
    c = bp.evalue_controle("C1", pris, [], [], n_sim=2000, b=2000)
    assert c["statut_B0"] == "NON_CONCLUANT" and c["part_sans_resultat"] > 0.05


def test_exploration_ne_donne_jamais_valide():
    archive = _archive_test(jours=30, par_jour=16, p=0.99)
    a = admet(*[f for c in archive.values() for f in c.values()])
    regles = [m for m in a.matchs if m.statut == "REGLE"]
    jours = sorted({m.jour for m in regles})
    tous = bp.Filtre("BX", lambda m: True, lambda m: int(m.match_id.split("_")[1]) < 12)
    out = bp.evalue_exploration(regles, jours, [tous], bp.tirages_jours(len(jours), 2000, 1))
    assert out["BX"]["statut"] in ("SIGNAL_EXPLORATOIRE", "SANS_SIGNAL", "NON_EVALUE", "EN_COURS")


# --- lois de Student et bêta sans scipy (valeurs de référence : scipy 1.18) ----------------------------------------------

@pytest.mark.parametrize("q,df,ref", [(0.9985, 19, 3.400657786284448), (0.9985, 39, 3.1656153816178314),
                                       (0.975, 12, 2.1788128296672284), (0.995, 5, 4.032142983555228)])
def test_quantile_de_student(q, df, ref):
    assert bp.t_ppf(q, df) == pytest.approx(ref, abs=1e-9)
    assert bp.t_ppf(1 - q, df) == pytest.approx(-ref, abs=1e-9)


@pytest.mark.parametrize("q,a,b,ref", [(0.975, 911, 199090, 0.004854750265821134), (0.025, 910, 199091, 0.004259750014824329),
                                        (0.975, 1, 200000, 1.8444227173720117e-05)])
def test_quantile_beta(q, a, b, ref):
    assert bp.beta_ppf(q, a, b) == pytest.approx(ref, rel=1e-9)


# --- § 9.5 : simulation -----------------------------------------------------------------------------------------------

def test_simulation_reproduit_l_ordre_de_grandeur_du_protocole():
    cotes = np.round(np.random.default_rng(0).uniform(1.27, 1.39, 300), 2)
    r997 = bp.simule_risque(cotes, (20, 40), 0.0015, 40_000, 11)
    r995 = bp.simule_risque(cotes, (20, 40), 0.0025, 40_000, 11)
    assert 0.0030 < r997["risque"] < 0.0060          # protocole : 0,455 %
    assert r995["risque"] > r997["risque"] and r995["risque"] > 0.0050   # protocole : 0,69 %
    assert bp.simule_risque(cotes, (20, 40), 0.0015, 5_000, 3) == bp.simule_risque(cotes, (20, 40), 0.0015, 5_000, 3)


# --- § 10 : reproduction des chiffres de départ (archive au commit 7c532a7) --------------------------------------------

def _commit_disponible(ref):
    return subprocess.run(["git", "cat-file", "-e", f"{ref}^{{commit}}"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _commit_disponible("7c532a7"), reason="commit 7c532a7 absent du clone")
def test_reproduction_des_chiffres_du_paragraphe_10():
    r = bp.reproduction(bp.Source("7c532a7"), dt.datetime(2026, 10, 13, 6, tzinfo=UTC), b=10_000)
    b0 = r["B0"]
    assert (b0["matchs"], b0["jours"]) == (253, 13)
    assert b0["reussite"] == pytest.approx(0.743, abs=5e-4)
    assert b0["roi"] == pytest.approx(-0.015, abs=5e-4)
    assert b0["probabilite_implicite_brute_moyenne"] == pytest.approx(0.755, abs=5e-4)
    assert r["admission"]["exclusions"] == {"RELEVE_APRES_COUP_D_ENVOI": 11, "HORODATAGE_ABSENT": 7}
    assert r["admission"]["statuts"]["RESULTAT_MANQUANT"] == 2
    assert r["tranches"]["H1-a"]["matchs"] == 149 and r["tranches"]["H1-b"]["matchs"] == 104
    ex = r["exploration"]
    assert ex["B1"]["retenus"]["matchs"] == 15 and ex["B2"]["retenus"]["matchs"] == 13
    assert ex["B4"]["retenus"]["matchs"] == 175 and ex["B4"]["non_retenus"] == 78


# --- Déclenchement automatique des points de contrôle (passage planifié) -----------------------------------------------

def _run(*args, cwd):
    return subprocess.run(list(args), cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _depot_avec_origine(tmp_path, archive):
    """origine nue + clone de travail ; main porte l'archive, la branche dédiée part de main."""
    origine, travail = tmp_path / "origine.git", tmp_path / "travail"
    _run("git", "init", "-q", "--bare", "-b", "main", str(origine), cwd=tmp_path)
    _run("git", "clone", "-q", str(origine), str(travail), cwd=tmp_path)
    _run("git", "checkout", "-q", "-b", "main", cwd=travail)
    _ecrit(travail, archive)
    (travail / "README").write_text("x")
    _run("git", "add", "-A", cwd=travail)
    _run("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "archive", cwd=travail)
    _run("git", "push", "-q", "origin", "main", cwd=travail)
    _run("git", "push", "-q", "origin", f"main:refs/heads/{bp.BRANCHE_BASE}", cwd=travail)
    return origine, travail


def _ajoute_sur_main(travail, archive):
    _run("git", "checkout", "-q", "-B", "maj", "origin/main", cwd=travail)
    _ecrit(travail, archive)
    _run("git", "add", "-A", cwd=travail)
    _run("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "nuit", cwd=travail)
    _run("git", "push", "-q", "origin", "HEAD:main", cwd=travail)
    _run("git", "checkout", "-q", bp.BRANCHE_BASE, cwd=travail) if _run("git", "branch", "--list", bp.BRANCHE_BASE, cwd=travail) else None


def _controles_distants(travail):
    _run("git", "fetch", "-q", "origin", bp.BRANCHE_BASE, cwd=travail)
    r = subprocess.run(["git", "show", f"origin/{bp.BRANCHE_BASE}:data/base/points_de_controle.json"], cwd=travail,
                       capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else []


AUTO = {"n_sim": 1000, "b": 1000}
QUAND = dt.datetime(2026, 12, 20, tzinfo=UTC)


def test_auto_ne_declenche_pas_avant_le_seuil_puis_declenche_c1_une_seule_fois(tmp_path):
    # 299 matchs réglés sur 20 jours : un de moins que le seuil
    archive = _archive_test(jours=20, par_jour=15, p=0.8)
    premier = sorted(archive)[0]
    mid = sorted(archive[premier])[0]
    archive[premier][mid]["score"] = {}
    _, travail = _depot_avec_origine(tmp_path, archive)
    r1 = bp.passage_automatique(travail, maintenant=QUAND, **AUTO)
    assert r1["resultat"] == "PUBLIE_SUR_BRANCHE" and r1["points"] == []
    assert _controles_distants(travail) == []
    # le score manquant arrive : 300 matchs réglés et 20 jours -> C1 se déclenche seul
    archive[premier][mid]["score"] = {"buts_dom": 1, "buts_ext": 0}
    _ajoute_sur_main(travail, {premier: archive[premier]})
    r2 = bp.passage_automatique(travail, maintenant=QUAND, **AUTO)
    assert r2["points"] == ["C1"] and [c["point"] for c in _controles_distants(travail)] == ["C1"]
    # relancé : rien ne change, pas de second C1
    r3 = bp.passage_automatique(travail, maintenant=QUAND, **AUTO)
    assert r3["resultat"] == "AUCUN_CHANGEMENT" and [c["point"] for c in _controles_distants(travail)] == ["C1"]


@pytest.mark.parametrize("jours,par_jour,attendu", [
    (20, 15, ["C1"]),      # 300 matchs, 20 jours : seuil atteint
    (19, 16, []),          # 304 matchs, 19 jours : minimum de jours non atteint
    (40, 15, ["C1", "C2"]),  # 600 matchs, 40 jours : C2 aussi
    (39, 16, ["C1"]),      # 624 matchs, 39 jours : pas encore C2
])
def test_seuils_exacts_des_points_de_controle(tmp_path, jours, par_jour, attendu):
    racine = tmp_path / "d"
    _ecrit(racine, _archive_test(jours=jours, par_jour=par_jour, p=0.8))
    e = bp.execute(bp.Source(None, racine), QUAND, racine / "data/base", **AUTO)
    assert e["points_de_controle_atteints"] == attendu


def test_c1_porte_sur_les_premiers_jours_meme_si_le_calcul_est_tardif(tmp_path):
    racine = tmp_path / "d"
    _ecrit(racine, _archive_test(jours=45, par_jour=15, p=0.8))
    bp.execute(bp.Source(None, racine), QUAND, racine / "data/base", **AUTO)
    c = json.loads((racine / "data/base/points_de_controle.json").read_text())
    assert (c[0]["point"], c[0]["jours"], c[0]["B0"]["matchs"]) == ("C1", 20, 300)
    assert (c[1]["point"], c[1]["jours"], c[1]["B0"]["matchs"]) == ("C2", 40, 600)


def test_aucun_point_de_controle_pour_des_matchs_de_moins_de_7_jours(tmp_path):
    racine = tmp_path / "d"
    _ecrit(racine, _archive_test(jours=25, par_jour=15, p=0.8))
    fin = dt.datetime(2026, 10, 13, tzinfo=UTC) + dt.timedelta(days=25)   # le dernier jour vient d'être joué
    e = bp.execute(bp.Source(None, racine), fin, racine / "data/base", **AUTO)
    assert e["points_de_controle_atteints"] == []          # 18 jours seulement ont 7 jours d'âge


def test_passages_concurrents_un_seul_c1(tmp_path, monkeypatch):
    archive = _archive_test(jours=20, par_jour=15, p=0.8)
    origine, a = _depot_avec_origine(tmp_path, archive)
    b = tmp_path / "b"
    _run("git", "clone", "-q", str(origine), str(b), cwd=tmp_path)
    vrai = bp.execute
    etat = {"fait": False}

    def execute_avec_concurrent(*args, **kw):
        if not etat["fait"]:                   # pendant le calcul de B, A publie son C1
            etat["fait"] = True
            monkeypatch.setattr(bp, "execute", vrai)
            # autre instant : commit différent (deux passages au même instant produisent le même commit, sans doublon)
            bp.passage_automatique(a, maintenant=QUAND + dt.timedelta(minutes=1), **AUTO)
            monkeypatch.setattr(bp, "execute", execute_avec_concurrent)
        return vrai(*args, **kw)

    monkeypatch.setattr(bp, "execute", execute_avec_concurrent)
    r = bp.passage_automatique(b, maintenant=QUAND, **AUTO)
    assert r["essai"] == 2, r                               # premier push refusé, reprise depuis la version distante
    assert r["resultat"] == "AUCUN_CHANGEMENT"              # C1 déjà publié par A : jamais recalculé
    assert [c["point"] for c in _controles_distants(b)] == ["C1"]


def test_passage_refuse_main_et_un_arbre_modifie(tmp_path):
    _, travail = _depot_avec_origine(tmp_path, _archive_test(jours=3, par_jour=2))
    with pytest.raises(bp.RefusAuto):
        bp.passage_automatique(travail, branche="main", maintenant=QUAND, **AUTO)
    (travail / "README").write_text("modifié")
    with pytest.raises(bp.RefusAuto, match="arbre de travail"):
        bp.passage_automatique(travail, maintenant=QUAND, **AUTO)


def test_verrou_empeche_deux_passages_simultanes(tmp_path):
    import fcntl
    _, travail = _depot_avec_origine(tmp_path, _archive_test(jours=3, par_jour=2))
    git_dir = Path(_run("git", "rev-parse", "--absolute-git-dir", cwd=travail))
    with open(git_dir / "base_protocole.lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        assert bp.passage_automatique(travail, maintenant=QUAND, **AUTO) == {"resultat": "DEJA_EN_COURS"}


def test_passage_ne_commite_que_data_base(tmp_path):
    _, travail = _depot_avec_origine(tmp_path, _archive_test(jours=20, par_jour=15, p=0.8))
    r = bp.passage_automatique(travail, maintenant=QUAND, **AUTO)
    fichiers = _run("git", "show", "--name-only", "--format=", r["commit"], cwd=travail).split()
    assert fichiers and all(f.startswith("data/base/") for f in fichiers)
    assert _run("git", "rev-parse", "origin/main", cwd=travail) != r["commit"]       # main intact
