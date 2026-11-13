"""Pronostics du moteur Équipe nationale : matchs à venir (collecte Matchendirect) + historique public des sélections + méthode Analyse Verdict.
Écrit data/selections/pronostics.json. Aucune cote disponible pour les sélections : les paris sont donnés sans cote (« à vérifier »), jamais jouables.

    python -m moteur_selections.pronostics"""
import json, os, tempfile
from moteur_selections import donnees, noms, verdict

RACINE = donnees.RACINE
ENTREE = os.path.join(donnees.DOSSIER, "a_venir.json")
SORTIE = os.path.join(donnees.DOSSIER, "pronostics.json")


def calcule(a_venir, hist, cfg=None):
    cfg = cfg or verdict.config(); R = []
    for m in a_venir:
        d, e = noms.FR_EN.get(m["domicile"]), noms.FR_EN.get(m["exterieur"])
        base = {k: m.get(k) for k in ("match_id", "date", "heure", "heure_cameroun", "competition", "domicile", "exterieur")}
        if not d or not e:
            inconnus = [n for n, x in ((m["domicile"], d), (m["exterieur"], e)) if not x]
            R.append({**base, "statut": "non évaluable", "raison": f"Équipe non reconnue : {', '.join(inconnus)}.", "paris": []}); continue
        match = {"date": m["date"], "domicile": d, "exterieur": e, "neutre": False}
        paris = verdict.paris(hist, match, None, cfg)
        fr = lambda s: s.replace(d, m["domicile"]).replace(e, m["exterieur"])   # noms français à l'affichage
        if paris:
            R.append({**base, "statut": "analyse", "raison": None, "paris": [{"marche": p["marche"], "verdict": p["verdict"], "libelle": fr(p["libelle"]), "phrase": fr(p["phrase"]), "force": p["force"]} for p in paris]})
        else:
            sa = hist.meme_lieu(d, "dom", m["date"], cfg["fenetre_jours"], cfg["officiels_seulement"]); sb = hist.meme_lieu(e, "ext", m["date"], cfg["fenetre_jours"], cfg["officiels_seulement"])
            if len(sa) < cfg["nmin"] or len(sb) < cfg["nmin"]:
                raison = f"Moins de {cfg['nmin']} matchs officiels au même lieu ({m['domicile']} à domicile : {len(sa)}, {m['exterieur']} à l'extérieur : {len(sb)})."
                R.append({**base, "statut": "non évaluable", "raison": raison, "paris": []})
            else:
                R.append({**base, "statut": "analyse", "raison": "Aucun pari ne tient.", "paris": []})
    return R


def main():
    with open(ENTREE, encoding="utf-8") as f: a_venir = json.load(f)
    csv_tmp = os.path.join(tempfile.gettempdir(), "resultats_selections.csv")   # hors dépôt : le pipeline ne le versionne pas
    donnees.telecharger(csv_tmp)
    hist = donnees.Historique(donnees.charger(csv_tmp))
    R = calcule(a_venir, hist)
    with open(SORTIE, "w", encoding="utf-8") as f: json.dump(R, f, ensure_ascii=False, indent=1)
    print(f"selections: {len(R)} matchs, {sum(1 for r in R if r['paris'])} avec au moins un pari qui tient, "
          f"{sum(1 for r in R if r['statut'] == 'non évaluable')} non évaluables -> data/selections/pronostics.json")


if __name__ == "__main__":
    main()
