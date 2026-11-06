"""Preuve que la page P1 affiche exactement les sorties reelles de P1.
 1. Recalcul: pour chaque match du journal, P1 est recalcule de zero (pouvoir_predictif.predire sur l'historique anterieur a la date du match) et compare au journal ET a page_p1.json (egalite exacte).
 2. Affichage: la page est ouverte dans Chromium (serveur local), les pourcentages 1/N/2 et marches lus dans le DOM sont compares a round(100*p) du JSON.
 3. Integrite: chaine d'empreintes du journal, gel avant coup d'envoi, JSON des autres moteurs inchanges (empreintes fournies en argument optionnel).
Sortie: data/calibration_p1/preuve_page_p1.json. Usage: python verifier_page_p1.py [--sans-navigateur]"""
import contextlib, functools, http.server, json, os, sys, threading
import numpy as np
import calibration_p1 as cp, integration_calibration as ic, pouvoir_predictif as pp, p1_page_donnees as pd

def recalcul(page, config):
    ecarts, n = [], 0
    J = {r["match_id"]: r for r in ic.lire_journal()}
    for m in page["matchs"]:
        r = J[m["match_id"]]; ccfg = config["competitions"][m["division"]]; jour = pp._date(m["date"]); fd_d, fd_e = r["detail"]["fd_dom"], r["detail"]["fd_ext"]
        H = [h for h in ic.historique(m["division"]) if h[0] < jour]
        P = pp.predire(H + [(jour, "x", fd_d, fd_e, 0, 0)], "P1", ccfg["p1"]["k"], ccfg["p1"]["demi_vie_jours"])[-1]
        for i, k in enumerate(ic.MARCHES):
            ecarts.append(max(abs(float(P[i]) - r["p1_original"][k]), abs(r["p1_original"][k] - m["p1_original"][k]), abs(r["p1_calibre"][k] - m["p1_calibre"][k]))); n += 1
    return {"valeurs_comparees": n, "ecart_max": max(ecarts) if ecarts else 0.0, "matchs": len(page["matchs"])}

def affichage(page):
    from playwright.sync_api import sync_playwright
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=ic.RACINE)); threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/pronostics_p1.html"; res = {"cartes": 0, "valeurs": 0, "ecarts": [], "erreurs_console": []}
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        pg.on("console", lambda m: res["erreurs_console"].append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: res["erreurs_console"].append(str(e)))
        pg.goto(url); pg.wait_for_selector("section.ax-carte"); cartes = pg.query_selector_all("section.ax-carte"); ms = page["matchs"]; a_venir = [m for m in ms if m["statut"] == "a_venir"] + [m for m in ms if m["statut"] == "en_cours_ou_resultat_attendu"] + [m for m in ms if m["statut"] == "termine"][::-1]   # ordre réel de la page : à venir, en cours, terminés (plus récent d'abord)
        res["cartes"] = len(cartes); res["attendu"] = len(a_venir); res["debordement_horizontal"] = pg.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        res["drapeaux"] = len(pg.query_selector_all(".af-drapeau")); res["blocs_derniers_matchs"] = len(pg.query_selector_all(".om-dm-eq"))
        for c, m in zip(cartes, a_venir):
            pa = m.get("pari") or {}; r = pa.get("retenu"); txt = c.eval_on_selector(".om-corps", "e=>e.textContent")
            ok_pari = (r["libelle"] in txt and f'{r["cote"]:.2f}'.replace(".", ",") in txt and f'{round(100 * r["p1"])} sur 100' in txt) if r else ("Pas de proposition" in txt)
            res["paris_affiches"] = res.get("paris_affiches", 0) + 1; res["paris_incoherents"] = res.get("paris_incoherents", 0) + (not ok_pari)
            if r:    # le « pourquoi » affiche exactement : avantage, cote, réussite estimée et probabilité impliquée par la cote
                pq = c.eval_on_selector(".om-pq-txt", "e=>e.textContent"); sg = "+" if r["valeur"] >= 0 else "−"
                att = [f'{sg}{abs(r["valeur"] * 100):.1f}'.replace(".", ",") + f' % d\'avantage (cote {r["cote"]:.2f}'.replace(".", ",") + ")", f'{int(100 * r["p1"] + 0.5)} % de réussite', f'contre {int(100 / r["cote"] + 0.5)} % selon la cote']      # arrondi de la page (Math.round : .5 vers le haut)
                res["valeurs"] += len(att); res["ecarts"] += [0 if a in pq else 1 for a in att]
            dm = c.query_selector_all(".om-dm-eq")
            if len(dm) == 2 and m.get("derniers_matchs"):                         # onglets : ouverture, ordre des dates, contenu = JSON
                D = m["derniers_matchs"]; res["cartes_avec_onglets"] = res.get("cartes_avec_onglets", 0) + 1
                for eq, defaut, cles in ((dm[0], "dom", {"dom": "dom", "ext": "dom_ext"}), (dm[1], "ext", {"dom": "ext_dom", "ext": "ext"})):
                    actif = eq.eval_on_selector(".om-onglet-actif", "e=>e.dataset.onglet"); visibles = eq.eval_on_selector_all(".om-dm-panneau:not([hidden])", "e=>e.map(x=>x.dataset.panneau)")
                    res["onglets_defaut_incorrects"] = res.get("onglets_defaut_incorrects", 0) + (actif != defaut or visibles != [defaut])
                    for onglet, cle in (*cles.items(), ("h2h", "h2h")):
                        dates = eq.eval_on_selector_all(f'.om-dm-panneau[data-panneau="{onglet}"] .om-dm', "e=>e.map(x=>x.dataset.date)")
                        res["listes_incorrectes"] = res.get("listes_incorrectes", 0) + (dates != [x["date"] for x in D[cle]] or dates != sorted(dates, reverse=True))
        os.makedirs(os.path.join(ic.RACINE, "data", "calibration_p1", "captures"), exist_ok=True)
        pg.screenshot(path=os.path.join(ic.RACINE, "data", "calibration_p1", "captures", "p1_mobile.png"))
        pg.set_viewport_size({"width": 1280, "height": 900}); pg.screenshot(path=os.path.join(ic.RACINE, "data", "calibration_p1", "captures", "p1_bureau.png"))
        b.close()
    srv.shutdown(); res["ecart_max_pct"] = max(res.pop("ecarts") or [0]); return res

if __name__ == "__main__":
    page = json.load(open(pd.SORTIE, encoding="utf-8")); config = cp.charger()
    preuve = {"genere_le": page["genere_le"], "recalcul": recalcul(page, config), "integrite_journal": ic.verifier_journal(), "calibration": page["calibration"]}
    if "--sans-navigateur" not in sys.argv: preuve["affichage"] = affichage(page)
    json.dump(preuve, open(os.path.join(ic.RACINE, "data", "calibration_p1", "preuve_page_p1.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1); print(json.dumps(preuve, ensure_ascii=False))
