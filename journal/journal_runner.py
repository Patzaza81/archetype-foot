from __future__ import annotations
import datetime, json, os
from .journal_observatoire import charger_archives, construire_fiche
from .journal_memoire import construire_historique
from .journal_cotes import statistiques_prix

def run(archive_dir="data/archive_test", out_dir="data"):
    records = charger_archives(archive_dir)
    scored = [r for r in records if isinstance(r.get("score"), dict)]
    upcoming = [r for r in records if r.get("score") is None]
    fiches = [construire_fiche(r, records) for r in sorted(upcoming, key=lambda x:(str(x.get("date")),str(x.get("match_id"))))]
    hist = construire_historique(scored)
    grouped = {}
    for team in sorted({r.equipe for r in hist}):
        for market in sorted({r.marche for r in hist if r.equipe == team}):
            rows = [r for r in hist if r.equipe == team and r.marche == market]
            if rows:
                grouped[f"{team}|{market}"] = {"equipe":team,"marche":market,"echantillon":len(rows),"frequence":round(sum(r.resultat for r in rows)/len(rows),4),"prix":statistiques_prix(rows)}
    os.makedirs(out_dir, exist_ok=True)
    generated = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    intelligence = {"schema_version":1,"genere_le":generated,"source":"data/archive_test","anti_fuite":"strictement_avant_date_du_match","n1_disponible":False,"statut_n1":"DONNEES_N_1_NON_PRESENTES_DANS_ARCHIVE_TEST","resume":{"archives":len(records),"scores":len(scored),"matchs_a_venir":len(upcoming),"fiches":len(fiches)},"fiches":fiches}
    memory = {"schema_version":1,"genere_le":generated,"source":"data/archive_test","observations":len(hist),"team_market":grouped}
    with open(os.path.join(out_dir,"journal_intelligence.json"),"w",encoding="utf-8") as f: json.dump(intelligence,f,ensure_ascii=False,indent=2)
    with open(os.path.join(out_dir,"journal_memoire.json"),"w",encoding="utf-8") as f: json.dump(memory,f,ensure_ascii=False,indent=2)
    return intelligence["resume"]

if __name__ == "__main__": print(run())
