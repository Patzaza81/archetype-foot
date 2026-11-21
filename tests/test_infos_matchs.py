"""infos_matchs : hors-ligne, avec de fausses reponses du service. Aucun appel reseau."""
import datetime
import json
import os
import pathlib
import re

import pytest

import infos_matchs as I

CFG = {"modele": "gemini-2.5-flash", "fenetre_heures": 30, "ttl_heures": 6, "max_appels_par_run": 3, "plafond_appels_par_jour": 400, "pause_secondes": 0, "jours_gardes": 7}
NOW = datetime.datetime(2026, 11, 21, 8, 0, tzinfo=datetime.timezone.utc)
SRC = [{"web": {"uri": "https://www.sportsmole.co.uk/x", "title": "sportsmole.co.uk"}}]


def rep(texte, sources=SRC):
    return {"candidates": [{"content": {"parts": [{"text": texte}]}, "groundingMetadata": {"groundingChunks": sources}}]}


def match(i, h=14, statut="a_venir", date="2026-11-21"):
    ko = (NOW.replace(hour=0) + datetime.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"match_id": f"m{i}", "date": date, "coup_d_envoi_utc": ko, "statut": statut, "domicile": "Southampton", "exterieur": "Derby County", "competition": "Angleterre : Championnat"}


def ecrire_page(tmp_path, matchs):
    p = tmp_path / "page.json"
    p.write_text(json.dumps({"matchs": matchs}), encoding="utf-8")
    return str(p)


JSON_OK = '```json\n{"absents":[{"equipe":"Southampton","joueur":"K. Schlotterbeck","statut":"blessé","raison":"épaule","source":"Sports Mole"},' \
          '{"equipe":"Derby","joueur":"X. Y","statut":"suspendu","raison":"carton rouge","source":"BBC"}]}\n```'


# ---- lecture de la reponse
def test_lecture_complete_deux_equipes():
    r = I.analyser(JSON_OK, I.sources_de(rep(JSON_OK)), "Southampton", "Derby County")
    assert r["statut"] == "ok" and [(a["equipe"], a["statut"]) for a in r["absents"]] == [("dom", "blesse"), ("ext", "suspendu")]


def test_aucune_source_tout_est_jete():
    r = I.analyser(JSON_OK, [], "Southampton", "Derby County")
    assert r == {"statut": "sans_source", "absents": []}


def test_reponse_sans_recherche_reelle_ne_passe_pas():
    assert I.interroger(match(1), CFG, "k", post=lambda *a: rep(JSON_OK, sources=[]))["statut"] == "sans_source"


@pytest.mark.parametrize("ligne", [
    {"equipe": "Chelsea", "joueur": "A", "statut": "blesse"},                    # equipe etrangere au match
    {"equipe": "Southampton", "joueur": "", "statut": "blesse"},                 # pas de joueur
    {"equipe": "Southampton", "joueur": "A", "statut": "probablement"},          # statut inconnu
    {"equipe": "", "joueur": "A", "statut": "blesse"},                           # pas d'equipe
    {"equipe": "Southampton", "joueur": "A" * 80, "statut": "blesse"},           # nom absurde
])
def test_lignes_invalides_jetees(ligne):
    t = json.dumps({"absents": [ligne]})
    assert I.analyser(t, I.sources_de(rep(t)), "Southampton", "Derby County")["absents"] == []


def test_equipe_ambigue_jetee():
    # « Manchester » designe les deux equipes : le doute = rien
    t = json.dumps({"absents": [{"equipe": "Manchester", "joueur": "A", "statut": "blesse"}]})
    assert I.analyser(t, SRC and I.sources_de(rep(t)), "Manchester United", "Manchester City")["absents"] == []


def test_doublon_et_texte_illisible():
    t = json.dumps({"absents": [{"equipe": "Southampton", "joueur": "A B", "statut": "blesse"}, {"equipe": "Southampton", "joueur": "a b", "statut": "absent"}]})
    assert len(I.analyser(t, I.sources_de(rep(t)), "Southampton", "Derby County")["absents"]) == 1
    assert I.analyser("pas de json", I.sources_de(rep("x")), "A", "B")["statut"] == "illisible"
    assert I.analyser('{"absents": 3}', I.sources_de(rep("x")), "A", "B")["statut"] == "illisible"


def test_deux_formes_de_reponse_pour_les_sources():
    inter = {"steps": [{"type": "model_output", "content": [{"text": "{}", "annotations": [{"type": "url_citation", "url": "https://bbc.com/a", "title": "BBC"}]}]}]}
    assert I.sources_de(inter) == [{"titre": "BBC", "url": "https://bbc.com/a"}]
    assert I.texte_de(inter) == "{}"
    assert I.sources_de(rep("x", [{"web": {"uri": "http://pas-https.com", "title": "t"}}])) == []      # https seulement


# ---- choix des matchs, cache, plafonds
def test_choix_fenetre_statut_et_ttl():
    page = {"matchs": [match(1, 14), match(2, 14, statut="termine"), match(3, 6),                                   # passe, deja commence
                       {**match(4), "coup_d_envoi_utc": "2026-11-23T20:00:00Z"}]}                                    # hors fenetre (> 30 h)
    assert [m["match_id"] for m in I.choisir(page, NOW, CFG, {})] == ["m1"]
    frais = {"m1": {"consulte_le": "2026-11-21T05:00:00Z"}}
    assert I.choisir(page, NOW, CFG, frais) == []                                                                   # consulte il y a 3 h < 6 h
    vieux = {"m1": {"consulte_le": "2026-11-21T01:00:00Z"}}
    assert len(I.choisir(page, NOW, CFG, vieux)) == 1                                                               # 7 h : on rafraichit
    assert len(I.choisir(page, NOW, CFG, {"m1": {"consulte_le": "2026-11-21T07:00:00Z", "erreur": "HTTP 500"}})) == 1  # une erreur est retentee


def test_plafond_par_run(tmp_path):
    page = ecrire_page(tmp_path, [match(i, 10 + i % 5) for i in range(10)])
    appels = []
    r = I.run(NOW, "k", lambda *a: appels.append(1) or rep(JSON_OK), lambda s: None, page, str(tmp_path / "o.json"), CFG)
    assert r == {"statut": "ok", "appels": 3} and len(appels) == 3


def test_plafond_du_jour_et_compteur(tmp_path):
    page, sortie = ecrire_page(tmp_path, [match(1)]), str(tmp_path / "o.json")
    cfg = {**CFG, "plafond_appels_par_jour": 1}
    assert I.run(NOW, "k", lambda *a: rep(JSON_OK), lambda s: None, page, sortie, cfg)["appels"] == 1
    page2 = ecrire_page(tmp_path, [match(2)])
    r = I.run(NOW + datetime.timedelta(hours=1), "k", lambda *a: rep(JSON_OK), lambda s: None, page2, sortie, cfg)
    assert r == {"statut": "plafond_jour", "appels": 0}
    r = I.run(NOW + datetime.timedelta(days=1), "k", lambda *a: rep(JSON_OK), lambda s: None, ecrire_page(tmp_path, [{**match(3), "coup_d_envoi_utc": "2026-11-22T20:00:00Z"}]), sortie, cfg)
    assert r["appels"] == 1                                                                                          # nouveau jour : compteur remis a zero


def test_quota_429_arrete_sans_forcer(tmp_path):
    page, sortie = ecrire_page(tmp_path, [match(i) for i in range(3)]), str(tmp_path / "o.json")
    n = []

    def post(*a):
        n.append(1)
        raise I.QuotaAtteint("HTTP 429")
    r = I.run(NOW, "k", post, lambda s: None, page, sortie, CFG)
    assert r["statut"] == "quota" and len(n) == 1
    assert json.load(open(sortie))["matchs"]["m0"]["erreur"] == "quota"


def test_erreur_reseau_noter_et_continuer(tmp_path):
    page, sortie = ecrire_page(tmp_path, [match(0), match(1)]), str(tmp_path / "o.json")
    etat = {"n": 0}

    def post(*a):
        etat["n"] += 1
        if etat["n"] == 1:
            raise RuntimeError("HTTP 500")
        return rep(JSON_OK)
    r = I.run(NOW, "k", post, lambda s: None, page, sortie, CFG)
    d = json.load(open(sortie))["matchs"]
    assert r["appels"] == 2 and d["m0"]["erreur"] == "HTTP 500" and d["m1"]["statut"] == "ok"


def test_sans_cle_rien_n_est_appele_ni_ecrit(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sortie = tmp_path / "o.json"
    r = I.run(NOW, None, lambda *a: pytest.fail("appel reseau sans cle"), lambda s: None, ecrire_page(tmp_path, [match(1)]), str(sortie), CFG)
    assert r["statut"] == "non_configure" and not sortie.exists()


def test_vieilles_entrees_purgees(tmp_path):
    sortie = tmp_path / "o.json"
    sortie.write_text(json.dumps({"compteur": {"jour": "2026-11-21", "appels": 0}, "matchs": {"vieux": {"date": "2026-11-01"}, "recent": {"date": "2026-11-19"}}}))
    I.run(NOW, "k", lambda *a: rep(JSON_OK), lambda s: None, ecrire_page(tmp_path, []), str(sortie), CFG)
    assert set(json.load(open(sortie))["matchs"]) == {"recent"}


def test_la_cle_n_apparait_jamais_dans_la_sortie(tmp_path):
    sortie = tmp_path / "o.json"
    I.run(NOW, "SECRET-123", lambda *a: rep(JSON_OK), lambda s: None, ecrire_page(tmp_path, [match(1)]), str(sortie), CFG)
    assert "SECRET-123" not in sortie.read_text(encoding="utf-8")


def test_config_et_prompt():
    c = I.config()
    assert c["modele"] == "gemini-2.5-flash" and c["plafond_appels_par_jour"] < 500            # quota gratuit documente : 500 par jour
    p = I.prompt(match(1))
    assert "Southampton" in p and "Derby County" in p and "N'invente aucun joueur" in p
    assert I.corps(match(1), c)["tools"] == [{"google_search": {}}]


# ---- mode mesure : rien ne lit ces infos hors de la page
def test_aucun_moteur_ne_lit_les_infos():
    racine = pathlib.Path(__file__).resolve().parent.parent
    autorises = {"infos_matchs.py"}
    fautifs = []
    for f in racine.rglob("*.py"):
        rel = f.relative_to(racine)
        if rel.parts[0] in ("tests", ".git", "node_modules") or rel.name in autorises:
            continue
        t = f.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"\bimport infos_matchs\b|\bfrom infos_matchs\b|infos_matchs/infos\.json", t):
            fautifs.append(str(rel))
    assert fautifs == [], f"un module lit les infos IA, interdit (mode mesure) : {fautifs}"


def test_la_page_affiche_non_confirme_et_charge_sans_bloquer():
    js = (pathlib.Path(__file__).resolve().parent.parent / "archetype_verif.js").read_text(encoding="utf-8")
    assert "Non confirmé" in js and "infosMatch(m)" in js and ".catch(() => ({}))" in js
