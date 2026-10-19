import json
from datetime import datetime, timezone

from matrice_scenarios import suivi_comportement as K
from tests.test_page_comportement import COTES, _match

MAINT = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def _m(mid, ko, score=None):
    m = _match(COTES)
    m.update({"match_id": mid, "coup_d_envoi_utc": ko, "score_final": score})
    return m


def test_gele_un_match_futur(tmp_path):
    j = tmp_path / "j.jsonl"
    assert K.geler(MAINT, j, [_m("a", "2026-10-19T15:00:00Z")]) == 1
    l = json.loads(j.read_text().splitlines()[0])
    assert l["type"] == "pronostic" and l["selections"] and l["gele_le"] == "2026-10-19T12:00:00Z"


def test_ne_gele_jamais_un_match_commence(tmp_path):
    j = tmp_path / "j.jsonl"
    assert K.geler(MAINT, j, [_m("a", "2026-10-19T11:59:00Z"), _m("b", "2026-10-19T12:00:00Z")]) == 0
    assert not j.exists()


def test_ne_gele_pas_un_match_deja_joue(tmp_path):
    assert K.geler(MAINT, tmp_path / "j.jsonl", [_m("a", "2026-10-20T15:00:00Z", {"buts_dom": 1, "buts_ext": 0})]) == 0


def test_ne_regele_jamais(tmp_path):
    j = tmp_path / "j.jsonl"
    ms = [_m("a", "2026-10-19T15:00:00Z")]
    K.geler(MAINT, j, ms)
    avant = j.read_text()
    assert K.geler(datetime(2026, 10, 19, 13, 0, tzinfo=timezone.utc), j, ms) == 0
    assert j.read_text() == avant


def test_resultat_ajoute_sans_modifier_le_pronostic(tmp_path):
    j = tmp_path / "j.jsonl"
    K.geler(MAINT, j, [_m("a", "2026-10-19T15:00:00Z")])
    premiere = j.read_text().splitlines()[0]
    assert K.resultats(j, [_m("a", "2026-10-19T15:00:00Z", {"buts_dom": 3, "buts_ext": 0})]) == 1
    lignes = j.read_text().splitlines()
    assert lignes[0] == premiere and json.loads(lignes[1])["type"] == "resultat"
    assert K.resultats(j, [_m("a", "2026-10-19T15:00:00Z", {"buts_dom": 3, "buts_ext": 0})]) == 0


def test_resultat_ignore_pour_match_non_gele(tmp_path):
    assert K.resultats(tmp_path / "j.jsonl", [_m("zzz", "2026-10-19T15:00:00Z", {"buts_dom": 1, "buts_ext": 1})]) == 0


def test_bilan_ne_compte_que_les_matchs_geles_et_termines(tmp_path):
    j = tmp_path / "j.jsonl"
    K.geler(MAINT, j, [_m("a", "2026-10-19T15:00:00Z"), _m("b", "2026-10-19T16:00:00Z")])
    K.resultats(j, [_m("a", "2026-10-19T15:00:00Z", {"buts_dom": 3, "buts_ext": 0})])
    b = K.bilan(j, ecrire=False)
    assert b["pronostics_geles"] == 2 and b["matchs_termines"] == 1 and b["en_attente"] == 1


def test_variable_archive_est_utilisee(tmp_path, monkeypatch):
    import gzip
    from matrice_scenarios import page_comportement as PC
    (tmp_path / "2026-10-30.json.gz").write_bytes(gzip.compress(json.dumps({"z": {"match_id": "z", "date": "2026-10-30"}}).encode()))
    monkeypatch.setenv("COMPORTEMENT_ARCHIVE", str(tmp_path))
    assert [m["match_id"] for m in PC.charger_matchs()] == ["z"]


def test_sans_variable_archive_du_depot(monkeypatch):
    from matrice_scenarios import page_comportement as PC
    monkeypatch.delenv("COMPORTEMENT_ARCHIVE", raising=False)
    assert len(PC.charger_matchs()) > 1000


# --- intégration pipeline (moteur alpha, production parallèle, hors tickets) ---
def _pipeline_yml() -> str:
    from pathlib import Path
    return (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "pipeline.yml").read_text(encoding="utf-8")


def test_pipeline_mode_ne_touche_pas_a_git(monkeypatch):
    import subprocess
    from matrice_scenarios import suivi_comportement as S
    monkeypatch.setattr(S, "geler", lambda *a, **k: 0)
    monkeypatch.setattr(S, "resultats", lambda *a, **k: 0)
    monkeypatch.setattr(S, "bilan", lambda *a, **k: {})
    monkeypatch.setattr(S.P, "ecrire_page", lambda *a, **k: {"matchs": []})
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("git appelé")))
    assert S.pipeline() == {"geles": 0, "resultats": 0, "page_matchs": 0, "bilan": {}}


def test_etape_alpha_est_dans_le_pipeline_nocturne_et_ne_peut_pas_le_casser():
    y = _pipeline_yml()
    i = y.index("Moteur alpha en production parallèle")
    bloc = y[i: y.index("      - name:", i + 10)]
    assert "continue-on-error: true" in bloc and "suivi_comportement pipeline" in bloc
    assert "github.event_name == 'schedule'" in bloc                                  # jamais sur un run de panier
    assert y.index("moteur_v3_pipeline.py") < i < y.index("python generateur_tickets.py")


def test_alpha_nest_pas_une_source_de_tickets():
    import generateur_tickets as G
    assert set(G.SOURCES) == {"moteur_v3", "journal"} and not any("alpha" in s or "comportement" in s for s in G.SOURCES)


# --- cas qui doivent échouer ---
def test_une_etape_sans_continue_on_error_serait_refusee():
    y = _pipeline_yml().replace("        continue-on-error: true\n        run: python -m matrice_scenarios.suivi_comportement pipeline",
                                "        run: python -m matrice_scenarios.suivi_comportement pipeline")
    i = y.index("Moteur alpha en production parallèle")
    assert "continue-on-error: true" not in y[i: y.index("      - name:", i + 10)]       # le contrôle ci-dessus détecte bien l'absence


def test_commande_inconnue_ne_lance_rien(capsys):
    import subprocess, sys
    r = subprocess.run([sys.executable, "-m", "matrice_scenarios.suivi_comportement", "nimporte"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and r.stdout.strip() == ""                          # commande inconnue : rien n'est exécuté, rien n'est écrit


def test_le_pipeline_reste_hors_du_mode_panier():
    y = _pipeline_yml()
    i = y.index("Moteur alpha en production parallèle")
    assert "panier_id == ''" in y[i: i + 400]
