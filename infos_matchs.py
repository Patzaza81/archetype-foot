"""Infos de match : blesses, absents, suspendus, cartons rouges (decision de Patrick, 21/11/2026).

Source : API Gemini avec la recherche Google, en acces GRATUIT (jamais de facturation sur la cle).
MODE MESURE : ces infos s'AFFICHENT sur la page de verification (« non confirme »). Aucun moteur, aucune collecte,
aucun pronostic gele ne les lit (tests/test_infos_matchs.py::test_aucun_moteur_ne_lit_les_infos).
Sans cle GEMINI_API_KEY : rien n'est appele, rien n'est ecrit. Voir docs/INFOS_MATCHS.md.
"""
import datetime
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request

DOSSIER = os.path.join("data", "infos_matchs")
SORTIE = os.path.join(DOSSIER, "infos.json")
CONFIG = os.path.join("config", "infos_matchs.json")
PAGE = os.path.join("data", "verif_pronostics", "page_verif.json")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent"
STATUTS = ("blesse", "suspendu", "absent", "incertain")


class QuotaAtteint(Exception):
    """Le service refuse (429) : on s'arrete pour ce passage, on ne force jamais."""


def config(chemin=CONFIG):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def _norm(s):
    t = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


def _equipe_de(nom, dom, ext):
    """'dom' ou 'ext' si le nom designe UNE seule des deux equipes, sinon None (le doute = rien)."""
    n = _norm(nom)
    if not n:
        return None
    paires = (("dom", _norm(dom)), ("ext", _norm(ext)))
    exact = [c for c, v in paires if v and v == n]
    if len(exact) == 1:
        return exact[0]
    partiel = [c for c, v in paires if v and (n in v or v in n)]
    return partiel[0] if len(partiel) == 1 else None


def prompt(m):
    return (f"Match de football : {m['domicile']} contre {m['exterieur']} ({m.get('competition') or 'championnat inconnu'}), le {m['date']}. "
            "Cherche sur le web les informations ACTUELLES, sans rien deviner : joueurs blesses ou absents, joueurs suspendus, "
            "cartons rouges recents qui entrainent une suspension, pour chacune des deux equipes. "
            'Reponds UNIQUEMENT par un JSON de la forme {"absents":[{"equipe":"nom exact de l\'equipe","joueur":"nom du joueur",'
            '"statut":"blesse|suspendu|absent|incertain","raison":"courte","source":"nom du site"}]}. '
            'Si tu ne trouves rien de fiable, reponds {"absents":[]}. N\'invente aucun joueur.')


def corps(m, cfg):
    return {"contents": [{"parts": [{"text": prompt(m)}]}], "tools": [{"google_search": {}}], "generationConfig": {"temperature": 0}}


def poster(url, charge, cle, delai=60):
    req = urllib.request.Request(url, data=json.dumps(charge).encode("utf-8"), headers={"Content-Type": "application/json", "x-goog-api-key": cle}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            return json.load(r)
    except urllib.error.HTTPError as err:       # le message ne contient jamais la cle
        if err.code == 429:
            raise QuotaAtteint("HTTP 429") from None
        raise RuntimeError(f"HTTP {err.code}") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        raise RuntimeError(type(err).__name__) from None


def texte_de(rep):
    """Texte de la reponse : forme generateContent (candidates) ou forme Interactions (steps)."""
    t = []
    for c in (rep.get("candidates") or [])[:1]:
        for p in (c.get("content") or {}).get("parts") or []:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                t.append(p["text"])
    for s in rep.get("steps") or []:
        if isinstance(s, dict) and s.get("type") == "model_output":
            for b in s.get("content") or []:
                if isinstance(b, dict) and isinstance(b.get("text"), str):
                    t.append(b["text"])
    return "".join(t)


def sources_de(rep):
    """Pages web que la recherche a REELLEMENT utilisees (groundingChunks ou annotations url_citation), https seulement."""
    vus, sortie = set(), []

    def ajoute(titre, url):
        if isinstance(url, str) and url.startswith("https://") and url not in vus:
            vus.add(url)
            sortie.append({"titre": str(titre or "")[:80], "url": url})

    def marche(x):
        if isinstance(x, dict):
            w = x.get("web")
            if isinstance(w, dict):
                ajoute(w.get("title"), w.get("uri"))
            if x.get("type") == "url_citation":
                ajoute(x.get("title"), x.get("url"))
            for v in x.values():
                marche(v)
        elif isinstance(x, list):
            for v in x:
                marche(v)
    marche(rep)
    return sortie


def extraire_json(texte):
    t = re.sub(r"```(?:json)?", "", texte or "")
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        return json.loads(t[a:b + 1])
    except ValueError:
        return None


def analyser(texte, sources, dom, ext):
    """Regles strictes : aucune source de recherche = tout est jete ; joueur sans equipe claire ou statut inconnu = ligne jetee."""
    if not sources:
        return {"statut": "sans_source", "absents": []}
    j = extraire_json(texte)
    if not isinstance(j, dict) or not isinstance(j.get("absents"), list):
        return {"statut": "illisible", "absents": []}
    sortie, vus = [], set()
    for a in j["absents"]:
        if not isinstance(a, dict):
            continue
        cle = _equipe_de(a.get("equipe"), dom, ext)
        joueur = str(a.get("joueur") or "").strip()
        statut = _norm(a.get("statut")).replace(" ", "")
        if cle is None or not joueur or len(joueur) > 60 or statut not in STATUTS or (cle, _norm(joueur)) in vus:
            continue
        vus.add((cle, _norm(joueur)))
        sortie.append({"equipe": cle, "joueur": joueur, "statut": statut, "raison": str(a.get("raison") or "").strip()[:120], "source": str(a.get("source") or "").strip()[:60]})
    return {"statut": "ok", "absents": sortie}


def interroger(m, cfg, cle, post=poster):
    rep = post(URL.format(modele=cfg["modele"]), corps(m, cfg), cle)
    sources = sources_de(rep)
    return {**analyser(texte_de(rep), sources, m["domicile"], m["exterieur"]), "sources": sources[:8]}


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def choisir(page, maintenant, cfg, deja):
    """Matchs a venir dans la fenetre, pas deja consultes depuis moins de ttl_heures, du plus proche au plus lointain, plafonne par run."""
    fin = maintenant + datetime.timedelta(hours=cfg["fenetre_heures"])
    L = []
    for m in page.get("matchs") or []:
        ko = _dt(m.get("coup_d_envoi_utc"))
        if m.get("statut") != "a_venir" or ko is None or not (maintenant <= ko <= fin):
            continue
        e = deja.get(m["match_id"])
        vu = _dt(e.get("consulte_le")) if e else None
        if e and not e.get("erreur") and vu and maintenant - vu < datetime.timedelta(hours=cfg["ttl_heures"]):
            continue
        L.append(m)
    L.sort(key=lambda m: m["coup_d_envoi_utc"])
    return L[:cfg["max_appels_par_run"]]


def run(maintenant=None, cle=None, post=poster, pause=time.sleep, page_chemin=PAGE, sortie=SORTIE, cfg=None):
    cle = cle if cle is not None else os.environ.get("GEMINI_API_KEY", "")
    if not cle:
        return {"statut": "non_configure", "appels": 0}
    cfg = cfg or config()
    maintenant = maintenant or datetime.datetime.now(datetime.timezone.utc)
    if not os.path.exists(page_chemin):
        return {"statut": "page_absente", "appels": 0}
    with open(page_chemin, encoding="utf-8") as f:
        page = json.load(f)
    ancien = {}
    if os.path.exists(sortie):
        with open(sortie, encoding="utf-8") as f:
            ancien = json.load(f)
    jour = maintenant.strftime("%Y-%m-%d")
    compteur = ancien.get("compteur") if (ancien.get("compteur") or {}).get("jour") == jour else {"jour": jour, "appels": 0}
    matchs = dict(ancien.get("matchs") or {})
    appels, arret = 0, None
    for m in choisir(page, maintenant, cfg, matchs):
        if compteur["appels"] >= cfg["plafond_appels_par_jour"]:
            arret = "plafond_jour"
            break
        base = {"match_id": m["match_id"], "date": m["date"], "domicile": m["domicile"], "exterieur": m["exterieur"], "competition": m.get("competition"),
                "coup_d_envoi_utc": m.get("coup_d_envoi_utc"), "consulte_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"), "modele": cfg["modele"]}
        compteur["appels"] += 1
        appels += 1
        try:
            matchs[m["match_id"]] = {**base, **interroger(m, cfg, cle, post)}
        except QuotaAtteint:
            matchs[m["match_id"]] = {**base, "erreur": "quota", "absents": [], "sources": []}
            arret = "quota"
            break
        except RuntimeError as err:
            matchs[m["match_id"]] = {**base, "erreur": str(err), "absents": [], "sources": []}
        pause(cfg["pause_secondes"])
    limite = (maintenant - datetime.timedelta(days=cfg["jours_gardes"])).strftime("%Y-%m-%d")
    matchs = {k: v for k, v in matchs.items() if str(v.get("date")) >= limite}
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump({"genere_le": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"), "modele": cfg["modele"], "compteur": compteur, "matchs": matchs}, f, ensure_ascii=False, separators=(",", ":"))
    return {"statut": arret or "ok", "appels": appels}


def essai(dom, ext, post=poster):
    """Un seul appel reel, sans rien ecrire : montre ce que le service renvoie (a lancer une fois la cle en place)."""
    cle = os.environ.get("GEMINI_API_KEY", "")
    if not cle:
        return "GEMINI_API_KEY absente : aucun appel."
    cfg = config()
    m = {"domicile": dom, "exterieur": ext, "competition": "", "date": datetime.date.today().isoformat()}
    rep = post(URL.format(modele=cfg["modele"]), corps(m, cfg), cle)
    r = {**analyser(texte_de(rep), sources_de(rep), dom, ext), "sources": len(sources_de(rep))}
    return json.dumps({"cles_reponse": sorted(rep), "texte": texte_de(rep)[:600], "lecture": r}, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "essai":
        print(essai(sys.argv[2], sys.argv[3]))
    else:
        print(json.dumps(run(), ensure_ascii=False))
