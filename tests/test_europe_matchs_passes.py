"""Page Europe : les matchs des jours passés (hier, avant-hier) ne s'affichent plus ; ceux d'aujourd'hui et à venir restent."""
import json
import pathlib
import shutil
import subprocess

import pytest

JS = (pathlib.Path(__file__).parent.parent / "archetype_europe.js").read_text(encoding="utf-8")
DEBUT = JS.index("function dateDuJourCameroun")
FIN = JS.index("function afficheSelections")
PURES = JS[DEBUT:FIN]
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node absent")


def node(expr):
    r = subprocess.run(["node", "-e", PURES + "\nconsole.log(JSON.stringify(" + expr + "))"], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def dates(ms, jour):
    return [m["date"] for m in node("matchsNonPasses(" + json.dumps(ms) + ", " + json.dumps(jour) + ")")]


def test_matchs_passes_retires_cas_qui_passent():
    ms = [dict(date="2026-10-13"), dict(date="2026-10-14"), dict(date="2026-10-15"), dict(date="2026-10-12")]
    assert dates(ms, "2026-10-14") == ["2026-10-14", "2026-10-15"]                    # hier et avant-hier retirés
    assert dates([dict(date="2026-10-13")], "2026-10-14") == []                        # le match de LdC d'hier disparaît
    assert dates([dict(date="2026-10-14", heure_cameroun="02:00")], "2026-10-14") == ["2026-10-14"]   # aujourd'hui, même commencé : gardé


def test_matchs_passes_cas_qui_echouent_ou_limites():
    assert dates([dict(date="2026-10-16")], "2026-10-14") == ["2026-10-16"]            # futur gardé
    assert node("matchsNonPasses(null, '2026-10-14')") == [] and node("matchsNonPasses(undefined)") == []   # pas de liste : pas d'erreur
    assert node("matchsNonPasses([{}, {date:''}, {date:'2026-10-01'}], '2026-10-14')") == [{}, {"date": ""}]   # sans date : gardé (pas masqué à tort)


def test_date_du_jour_est_celle_du_cameroun():
    # 23h30 UTC le 13/10 = 00h30 le 14/10 au Cameroun (UTC+1)
    assert node("dateDuJourCameroun(Date.UTC(2026,9,13,23,30))") == "2026-10-14"
    assert node("dateDuJourCameroun(Date.UTC(2026,9,14,10,0))") == "2026-10-14"
    assert node("dateDuJourCameroun(Date.UTC(2026,9,14,22,59))") == "2026-10-14" and node("dateDuJourCameroun(Date.UTC(2026,9,14,23,0))") == "2026-10-15"


def test_la_liste_affichee_passe_par_le_filtre():
    assert "regroupeMatchs(matchsNonPasses(matchs))" in JS
