"""Cotes Betpawa des matchs de sélections : réutilise TELLE QUELLE la résolution Betpawa existante (resolution_betpawa_precalcul.resout_cotes_betpawa),
sans la modifier. Écrit data/selections/cotes.json {match_id: cotes} (même format que cotes_manuelles / cotes_betpawa du flux).
Ne tourne que dans le pipeline (Playwright, accès betpawa.cm) ; ne peut jamais le faire échouer.
Betpawa ne connaît parfois que le nom anglais : un match non résolu est retenté une fois avec les noms anglais (noms.FR_EN).

    python -m moteur_selections.cotes"""
import copy, json, os
from moteur_selections import donnees, noms

ENTREE = os.path.join(donnees.DOSSIER, "a_venir.json")
SORTIE = os.path.join(donnees.DOSSIER, "cotes.json")
DIAGNOSTIC = os.path.join(donnees.DOSSIER, "diagnostic_betpawa.txt")   # n'écrase pas le diagnostic du pré-calcul


def main():
    import resolution_betpawa_precalcul as R
    R.FICHIER_DIAGNOSTIC = DIAGNOSTIC
    with open(ENTREE, encoding="utf-8") as f: a_venir = json.load(f)
    fenetre = [{"match_id": m["match_id"], "domicile": m["domicile"], "exterieur": m["exterieur"], "date": m["date"], "competition": m.get("competition")} for m in a_venir]
    R.resout_cotes_betpawa(fenetre)
    rate = [m for m in fenetre if not m.get("cotes_manuelles") and m["domicile"] in noms.FR_EN and m["exterieur"] in noms.FR_EN]
    if rate:
        essai = [{**m, "domicile": noms.FR_EN[m["domicile"]], "exterieur": noms.FR_EN[m["exterieur"]]} for m in rate]
        R.resout_cotes_betpawa(essai)
        for m, x in zip(rate, essai):
            if x.get("cotes_manuelles"): m["cotes_manuelles"] = x["cotes_manuelles"]
    cotes = {m["match_id"]: m["cotes_manuelles"] for m in fenetre if m.get("cotes_manuelles")}
    with open(SORTIE, "w", encoding="utf-8") as f: json.dump(cotes, f, ensure_ascii=False)
    print(f"selections: cotes Betpawa trouvées pour {len(cotes)} match(s) sur {len(fenetre)}")


if __name__ == "__main__":
    try: main()
    except Exception as err: print(f"selections: cotes non récupérées ({err})")
