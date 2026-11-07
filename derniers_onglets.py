"""Donnees « Derniers matchs » a trois onglets (A domicile / A l'exterieur / H2H) pour TOUS les moteurs (07/11/2026, demande de Patrick).
Source unique : le meme calcul que la page P1 (p1_page_donnees.derniers_matchs) sur l'historique reel de la competition (archives Football-Data + saison courante, ou Matchendirect pour les championnats servis par lui),
strictement AVANT le jour du match. Cle = match_id du flux commun (data/archive_test), le meme que celui utilise par les moteurs.
Un match dont les deux equipes ne sont pas reliees a une competition couverte n'a AUCUNE entree : les pages gardent alors leur affichage actuel (aucune valeur inventee).
Format compact (3G) : listes d'equipes [date, adversaire, buts marques, buts encaisses] ; h2h [date, 1 si l'equipe qui recoit aujourd'hui recevait ce jour-la, marques, encaisses] (point de vue de l'equipe qui recoit).
Sortie : data/derniers_onglets.json (recalcule de zero, deterministe)."""
import datetime, json, os
import integration_calibration as ic
import p1_page_donnees as pd
import pouvoir_predictif as pp

SORTIE = os.path.join(ic.RACINE, "data", "derniers_onglets.json")
FENETRE_JOURS = 3       # jours passes conserves (les pages montrent surtout les matchs du jour et a venir) ; au-dela, les pages gardent leur affichage actuel

def _ligne(x): return [x["date"], x["adversaire"], x["marques"], x["encaisses"]]

def construire(aujourdhui=None, flux=ic.FLUX):
    aujourdhui = aujourdhui or datetime.datetime.now(datetime.timezone.utc).date()
    depuis = (aujourdhui - datetime.timedelta(days=FENETRE_JOURS)).isoformat(); H = {}; out = {}; sans = 0
    for m in ic.lire_flux(depuis, None, tous=True):
        if not (m.get("division") and m.get("fd_dom") and m.get("fd_ext")): sans += 1; continue
        code = m["division"]
        if code not in H: H[code] = ic.historique(code)
        jour = pp._date(m["date"])
        if jour is None: sans += 1; continue
        d = pd.derniers_matchs(H[code], m["fd_dom"], m["fd_ext"], jour)
        if not any(d[k] for k in ("dom", "ext", "dom_ext", "ext_dom", "h2h")): sans += 1; continue
        out[m["match_id"]] = {"dom": [_ligne(x) for x in d["dom"]], "ext": [_ligne(x) for x in d["ext"]], "dom_ext": [_ligne(x) for x in d["dom_ext"]], "ext_dom": [_ligne(x) for x in d["ext_dom"]],
                              "h2h": [[x["date"], 1 if x["domicile"] else 0, x["marques"], x["encaisses"]] for x in d["h2h"]]}
    return {"genere_le": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "depuis": depuis, "matchs_couverts": len(out), "matchs_sans_donnees": sans, "matchs": out}

def ecrire(d=None, chemin=SORTIE):
    d = d or construire(); json.dump(d, open(chemin, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":")); return d

if __name__ == "__main__":
    d = ecrire(); print(json.dumps({k: d[k] for k in ("depuis", "matchs_couverts", "matchs_sans_donnees")}), os.path.getsize(SORTIE), "octets")
