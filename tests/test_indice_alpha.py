"""Onglet « Indice Alpha » (26/10/2026) : calculs, regroupement par marché, absence de doublons, traçabilité, suivi nocturne, affichage."""
import copy
import inspect
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from alpha_serie import indice_alpha as I, suivi as S, tickets as T

RACINE = Path(__file__).resolve().parent.parent


def paris(spec, rid="x"):
    """spec : liste de (match_id, date, gagne)."""
    return [{"id": f"{m}|{rid}", "match_id": m, "date": d, "gagne": g, "cote": 1.4} for m, d, g in spec]


def source(spec, geles_en_plus=0, doublons=0):
    p = paris(spec)
    dates = [x[1] for x in spec] or []
    return {"geles": [{"date": d} for d in dates] + [{"date": dates[-1]}] * geles_en_plus if dates else [], "paris": p, "doublons": doublons,
            "dates_gelees": dates + ([dates[-1]] * geles_en_plus if dates else []), "gel_apres_coup_d_envoi": 0}


def indice(**k):
    base = {"id": "t", "nom": "Test", "famille": "1X2", "marche": "m", "statut": "en_validation", "source": "inconnue:x", "conditions": "c",
            "objectif_reussite": 0.7, "modifications": []}
    return {**base, **k}


# ---- calculs ----
def test_taux_wilson_frequence_et_semaines():
    spec = [("a", "2026-11-02", True), ("b", "2026-11-02", False), ("c", "2026-11-03", True), ("d", "2026-11-09", True)]
    r = I.rapport_indice(indice(), {"t": source(spec, geles_en_plus=1)})
    assert (r["matchs"], r["gagnes"], r["perdus"]) == (4, 3, 1) and r["taux"] == 0.75
    assert r["wilson_bas_95"] == S.wilson_bas(3, 4)
    assert r["geles"] == 5 and r["en_attente"] == 1
    assert r["periode"] == {"debut": "2026-11-02", "fin": "2026-11-09", "jours": 8} and r["par_jour"] == round(5 / 8, 2)
    assert [(s["semaine"], s["matchs"], s["gagnes"]) for s in r["par_semaine"]] == [("2026-S45", 3, 2), ("2026-S46", 1, 1)]
    assert [(s["semaine"], s["matchs"], s["gagnes"]) for s in r["cumule_par_semaine"]] == [("2026-S45", 3, 2), ("2026-S46", 4, 3)]


def test_indice_sans_donnee_est_vide_et_jamais_fiable():
    r = I.rapport_indice(indice(statut="valide"))
    assert r["matchs"] == 0 and r["taux"] is None and r["wilson_bas_95"] is None and r["par_jour"] is None
    assert r["fiabilite"]["niveau"] == "non_fiable"


def test_tendance_baisse_stable_insuffisant():
    bons = [(f"m{i}", "2026-11-02", True) for i in range(30)]
    mauvais = [(f"n{i}", "2026-11-09", False) for i in range(5)]
    assert I.rapport_indice(indice(), {"t": source(bons + mauvais)})["tendance"]["signal"] == "baisse"
    assert I.rapport_indice(indice(), {"t": source(bons + [(f"o{i}", "2026-11-09", True) for i in range(5)])})["tendance"]["signal"] == "stable"
    assert I.rapport_indice(indice(), {"t": source(bons)})["tendance"]["signal"] == "insuffisant"


def test_fiabilite_exige_validation_et_borne_basse_a_l_objectif():
    tous = [(f"m{i}", "2026-11-02", True) for i in range(40)]
    peu = [("a", "2026-11-02", True), ("b", "2026-11-02", True)]
    assert I.rapport_indice(indice(statut="en_validation"), {"t": source(tous)})["fiabilite"]["niveau"] == "non_fiable"      # 100 % mais pas validé
    assert I.rapport_indice(indice(statut="en_etude"), {"t": source(tous)})["fiabilite"]["niveau"] == "non_fiable"
    assert I.rapport_indice(indice(statut="valide"), {"t": source(peu)})["fiabilite"]["niveau"] == "a_confirmer"             # validé mais échantillon trop petit
    assert I.rapport_indice(indice(statut="valide"), {"t": source(tous)})["fiabilite"]["niveau"] == "fiable"


# ---- regroupement par marché, doublons ----
def match(i, c1, c2):
    return {"match_id": f"m{i}", "date": "2026-11-02", "coup_d_envoi_utc": "2026-11-02T14:00:00Z", "competition": "T", "domicile": f"D{i}", "exterieur": f"E{i}",
            "cotes_betpawa": {"1x2": {"1": c1, "2": c2, "N": 3.3}}, "assemblage": {}, "score_final": None}


def test_bandes_regroupees_par_marche_et_identiques_au_rapport_de_validation(tmp_path):
    from datetime import datetime, timezone
    j = tmp_path / "j.jsonl"
    ms = [match(1, 1.4, 9), match(2, 1.45, 1.5), match(3, 9, 1.6), match(4, 2.5, 2.5)]
    S.geler_bandes(datetime(2026, 11, 2, 1, tzinfo=timezone.utc), j, ms, params={})
    fini = [dict(m, score_final=sc) for m, sc in zip(ms, [{"buts_dom": 2, "buts_ext": 0}, {"buts_dom": 0, "buts_ext": 1}, {"buts_dom": 0, "buts_ext": 2}, {"buts_dom": 1, "buts_ext": 1}])]
    S.resultats_bandes(j, fini)
    dom, ext = I._source_bandes("domicile", j), I._source_bandes("exterieur", j)
    assert {p["match_id"] for p in dom["paris"]} == {"m1", "m2"} and {p["match_id"] for p in ext["paris"]} == {"m2", "m3"}
    b = S.bilan_bandes(j, ecrire=False)["regles"]
    for nom, src in (("domicile", dom), ("exterieur", ext)):
        assert (len(src["paris"]), sum(p["gagne"] for p in src["paris"])) == (b[nom]["cumule"]["matchs"], b[nom]["cumule"]["gagnes"])
    assert dom["doublons"] == 0 and dom["gel_apres_coup_d_envoi"] == 0


def test_ligne_dupliquee_dans_le_journal_comptee_une_fois_et_signalee(tmp_path):
    from datetime import datetime, timezone
    j = tmp_path / "j.jsonl"
    S.geler_bandes(datetime(2026, 11, 2, 1, tzinfo=timezone.utc), j, [match(1, 1.4, 9)], params={})
    ligne = j.read_text(encoding="utf-8")
    j.write_text(ligne + ligne, encoding="utf-8")                     # corruption volontaire : le même gel deux fois
    s = I._source_bandes("domicile", j)
    assert len(s["geles"]) == 1 and s["doublons"] == 1


def test_vue_globale_ne_compte_pas_deux_fois_et_n_additionne_pas_les_pourcentages():
    a = paris([("m1", "2026-11-02", True), ("m2", "2026-11-02", False), ("m2", "2026-11-02", False)], "a")      # m2 deux fois dans le même indice
    b = paris([("m1", "2026-11-02", False), ("m3", "2026-11-09", True)], "b")                                   # m1 aussi dans l'autre indice : autre pari
    ra, rb = (I.rapport_indice(indice(id=i), {i: {"geles": [], "paris": p, "doublons": 0, "dates_gelees": ["2026-11-02"], "gel_apres_coup_d_envoi": 0}})
              for i, p in (("a", a), ("b", b)))
    g = I.vue_globale([ra, rb], {"a": a, "b": b})
    assert g["doublons_ecartes"] == 1
    assert (g["paris_distincts"]["matchs"], g["paris_distincts"]["gagnes"]) == (4, 2)         # m1/a, m2/a, m1/b, m3/b
    assert g["matchs_distincts"] == 3 and g["matchs_avec_plusieurs_indices"] == 1
    assert g["paris_distincts"]["taux"] == 0.5 and g["paris_distincts"]["taux"] != round(ra["taux"] + rb["taux"], 4)


def test_plus15_max_un_pari_par_match_et_par_jour_quel_que_soit_le_palier(tmp_path):
    j = tmp_path / "t.jsonl"
    c = lambda mid, mx: {"match_id": mid, "cote": 1.3, "chances_max": mx}
    lignes = [{"type": "tickets", "jour": "2026-11-02", "gele_le": "2026-11-02T01:00:00Z", "palier1": [c("a", True), c("b", False)], "palier2": [c("a", True)],
               "accueil_1": [c("a", True), c("z", True)]},
              {"type": "resultat_tickets", "jour": "2026-11-02", "palier1": [True, True], "palier2": [True], "accueil_1": [True, False]}]
    j.write_text("\n".join(json.dumps(l) for l in lignes), encoding="utf-8")
    s = I._source_plus15_max(j)
    assert sorted((p["match_id"], p["gagne"]) for p in s["paris"]) == [("a", True), ("z", False)] and len(s["geles"]) == 2


def test_plus15_max_pari_gele_sans_resultat_reste_en_attente(tmp_path):
    j = tmp_path / "t.jsonl"
    j.write_text(json.dumps({"type": "tickets", "jour": "2026-11-02", "palier1": [{"match_id": "a", "cote": 1.3, "chances_max": True}]}), encoding="utf-8")
    s = I._source_plus15_max(j)
    assert len(s["geles"]) == 1 and s["paris"] == []


# ---- registre, traçabilité, indépendance ----
def test_registre_actuel_coherent_et_aucun_indice_valide_d_office():
    reg = I.charger_registre()
    assert I.verifier_registre(reg) == []
    ids = [i["id"] for i in reg["indices"]]
    assert ids == ["victoire_domicile", "victoire_exterieur", "plus_de_1_5_maximal"] and len(set(ids)) == 3
    assert all(i["statut"] == "en_validation" for i in reg["indices"])


def test_les_seuils_affiches_sont_ceux_que_le_suivi_lit_vraiment():
    reg = I.charger_registre()
    d, e, p = (I.seuils_reels(i) for i in reg["indices"])
    regles = json.loads((RACINE / "data/alpha_serie/bandes_1x2.json").read_text(encoding="utf-8"))["regles"]
    assert (d["cote_min"], d["cote_max"]) == (regles["domicile"]["cote_min"], regles["domicile"]["cote_max"]) == (1.33, 1.5)
    assert (e["cote_min"], e["cote_max"]) == (regles["exterieur"]["cote_min"], regles["exterieur"]["cote_max"]) == (1.38, 1.7)
    assert p["total_attendu_min"] == T.palier_plus15() and d["probabilite_min"] is None


def test_modification_de_seuil_non_tracee_signalee_et_independante_des_autres_marches(tmp_path, monkeypatch):
    reg = I.charger_registre()
    avant = {i["id"]: I.rapport_indice(i) for i in reg["indices"]}
    f = tmp_path / "bandes.json"
    d = json.loads((RACINE / "data/alpha_serie/bandes_1x2.json").read_text(encoding="utf-8"))
    d["regles"]["domicile"]["cote_max"] = 1.6                                    # on change UNE règle sans toucher à l'historique
    f.write_text(json.dumps(d), encoding="utf-8")
    monkeypatch.setattr(S, "BANDES", f)
    alertes = I.verifier_registre(reg)
    assert len(alertes) == 1 and alertes[0].startswith("victoire_domicile")
    apres = {i["id"]: I.rapport_indice(i) for i in reg["indices"]}
    assert apres["victoire_domicile"]["seuils"]["cote_max"] == 1.6
    for autre in ("victoire_exterieur", "plus_de_1_5_maximal"):                   # les autres marchés ne bougent pas, empreinte comprise
        assert apres[autre] == avant[autre]
    reg2 = copy.deepcopy(reg)                                                    # la modification devient tracée : plus d'alerte
    i0 = reg2["indices"][0]
    i0["modifications"].append({"date": "2026-11-03", "auteur": "t", "champ": "cote_max", "ancien": 1.5, "nouveau": 1.6, "motif": "test", "empreinte_apres": I.empreinte(i0)})
    assert I.verifier_registre(reg2) == []


def test_statut_modifie_sans_historique_signale_et_statut_inconnu_refuse():
    reg = copy.deepcopy(I.charger_registre())
    reg["indices"][1]["statut"] = "valide"
    assert [a.split(" :")[0] for a in I.verifier_registre(reg)] == ["victoire_exterieur"]
    reg["indices"][1]["statut"] = "parfait"
    assert any("statut inconnu" in a for a in I.verifier_registre(reg))


def test_identifiant_en_double_signale():
    reg = copy.deepcopy(I.charger_registre())
    reg["indices"].append(copy.deepcopy(reg["indices"][0]))
    assert any("double" in a for a in I.verifier_registre(reg))


# ---- suivi nocturne ----
def test_le_pipeline_nocturne_construit_l_indice_alpha_apres_les_journaux():
    src = inspect.getsource(S.pipeline)
    assert src.index("geler_bandes(matchs=matchs)") < src.index("indice_alpha.construire()") and "except Exception" in src


def test_construction_reelle_sur_les_journaux_du_depot(tmp_path):
    out = tmp_path / "ia.json"
    r = I.construire(sortie=out)
    assert json.loads(out.read_text(encoding="utf-8"))["indices"][0]["id"] == "victoire_domicile" and r["alerte_registre"] == []
    assert [x["id"] for x in r["global"]["classement"]].count("victoire_domicile") == 1
    for x in r["indices"]:
        assert x["controles"] == {"doublons": 0, "gels_non_anterieurs_au_coup_d_envoi": 0}


def test_le_fichier_publie_a_la_structure_attendue_par_la_page():
    d = json.loads((RACINE / "data/alpha_serie/indice_alpha.json").read_text(encoding="utf-8"))
    assert {"genere_le", "alerte_registre", "global", "indices"} <= set(d)
    for x in d["indices"]:
        assert {"id", "nom", "statut", "statut_libelle", "conditions", "seuils", "matchs", "gagnes", "perdus", "taux", "wilson_bas_95", "par_jour", "periode",
                "par_semaine", "cumule_par_semaine", "tendance", "reference_rejeu", "fiabilite", "controles", "empreinte", "modifications"} <= set(x)


# ---- affichage ----
def test_la_page_est_dans_la_navigation_du_site():
    for f in ("pronostics_comportement.html", "tickets_alpha.html", "indice_alpha.html", "index.html"):
        assert 'href="indice_alpha.html"' in (RACINE / f).read_text(encoding="utf-8"), f
    h = (RACINE / "indice_alpha.html").read_text(encoding="utf-8")
    assert 'name="viewport"' in h and "af-indice-alpha.js" in h and "af-indice-alpha.css" in h and 'aria-current="page">Indice Alpha' in h


def test_css_mobile_sans_largeur_fixe_ni_texte_qui_deborde():
    css = (RACINE / "af-indice-alpha.css").read_text(encoding="utf-8")
    assert not re.findall(r"(?<![-\w])(?:min-)?width:\s*(?:[4-9]\d\d|\d{4,})px", css)
    assert "nowrap" not in css


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent")
def test_la_page_s_affiche_sans_erreur_et_echappe_le_texte(tmp_path):
    data = json.loads((RACINE / "data/alpha_serie/indice_alpha.json").read_text(encoding="utf-8"))
    data["indices"][0]["nom"] = "<img src=x onerror=alert(1)>"
    data["global"]["classement"][0]["nom"] = "<img src=x onerror=alert(1)>"
    (tmp_path / "d.json").write_text(json.dumps(data), encoding="utf-8")
    js = r"""
const fs=require('fs');const els={};const mk=(id)=>els[id]||(els[id]={id,innerHTML:'',textContent:'',hidden:true});
let click=null;
global.window={scrollTo(){}};
global.document={getElementById:mk,querySelectorAll:()=>[],addEventListener:(t,f)=>{click=f}};
global.fetch=()=>Promise.resolve({ok:true,json:()=>Promise.resolve(JSON.parse(fs.readFileSync(process.argv[2],'utf8')))});
eval(fs.readFileSync(process.argv[3],'utf8'));
const tick=()=>new Promise(r=>setTimeout(r,20));
(async()=>{await tick();const out={};
 out.total=mk('ia').innerHTML;
 const btn=(vue)=>({closest:(s)=>s==='#ia-vues button'?{dataset:{vue}}:null});
 click({target:btn('marche')});out.marche=mk('ia').innerHTML;
 click({target:btn('gestion')});out.gestion=mk('ia').innerHTML;
 out.maj=mk('maj').textContent;console.log(JSON.stringify(out));})();
"""
    (tmp_path / "t.js").write_text(js, encoding="utf-8")
    r = subprocess.run(["node", str(tmp_path / "t.js"), str(tmp_path / "d.json"), str(RACINE / "af-indice-alpha.js")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout)
    for vue in ("total", "marche", "gestion"):
        assert o[vue] and "undefined" not in o[vue] and "NaN" not in o[vue] and "<img" not in o[vue], vue
    assert "Victoire à l&#39;extérieur" in o["total"] and "&lt;img" in o["total"]
    assert "Historique des modifications" in o["gestion"]
    assert "Suivi réel" in o["marche"] and "Étude historique" in o["marche"]
