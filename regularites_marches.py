"""Premiere exploitation statistique (descriptive, sans modele): frequences de marches deduits des SCORES JOUES des archives, par competition et saison,
et stabilite d'une saison a la suivante comparee au bruit d'echantillonnage. Lecture seule des archives; aucune cote, aucune prediction.
Les scores sont ceux de l'archive (joues); aucun score attribue n'est substitue. Chronologie: la stabilite compare la saison s a la saison s-1 seulement."""
import csv, json, math, os, sys
RACINE = os.path.dirname(os.path.abspath(__file__))
SNAP = os.path.join(RACINE, "data", "football_data", "snapshots")
SAISONS = ["2122", "2223", "2324", "2425", "2526"]
MARCHES = {"dom": lambda h, a: h > a, "nul": lambda h, a: h == a, "ext": lambda h, a: h < a,
           "o15": lambda h, a: h + a >= 2, "o25": lambda h, a: h + a >= 3, "o35": lambda h, a: h + a >= 4, "btts": lambda h, a: h > 0 and a > 0}

def lire(chemin):
    try:
        return list(csv.DictReader(open(chemin, encoding="utf-8-sig")))
    except UnicodeDecodeError:
        return list(csv.DictReader(open(chemin, encoding="latin-1")))

def scores(code, s):
    for p in (os.path.join(SNAP, s, "raw", code + ".csv"), os.path.join(SNAP, s, "nouvelles_ligues", "raw", code + ".csv")):
        if os.path.exists(p):
            R = lire(p)
            if not R: return []
            h, a = ("FTHG", "FTAG") if "FTHG" in R[0] else ("HG", "AG")
            out = []
            for r in R:
                try: out.append((int(float(r[h])), int(float(r[a]))))
                except (ValueError, TypeError, KeyError): pass
            return out
    return []

def main():
    cl = json.load(open(os.path.join(RACINE, "data", "inventaire", "classement_descriptif.json"), encoding="utf-8"))["competitions"]
    res = {}
    for code in sorted(cl):
        par = {}
        for s in SAISONS:
            sc = scores(code, s)
            if not sc: continue
            n = len(sc)
            par[s] = {"n": n, "buts_moy": round(sum(h + a for h, a in sc) / n, 3), **{m: round(sum(f(h, a) for h, a in sc) / n, 4) for m, f in MARCHES.items()}}
        # stabilite saison -> saison suivante: |p_s - p_(s-1)| compare au bruit attendu sqrt(p(1-p)(1/n1+1/n2))
        stab = {}
        for m in MARCHES:
            ecarts, bruits = [], []
            for s0, s1 in zip(SAISONS, SAISONS[1:]):
                if s0 in par and s1 in par:
                    p = (par[s0][m] * par[s0]["n"] + par[s1][m] * par[s1]["n"]) / (par[s0]["n"] + par[s1]["n"])
                    ecarts.append(abs(par[s1][m] - par[s0][m]))
                    bruits.append(math.sqrt(p * (1 - p) * (1 / par[s0]["n"] + 1 / par[s1]["n"])) * math.sqrt(2 / math.pi))  # ecart absolu moyen attendu du seul hasard
            if ecarts:
                stab[m] = {"ecart_abs_moyen": round(sum(ecarts) / len(ecarts), 4), "bruit_attendu": round(sum(bruits) / len(bruits), 4),
                           "ratio": round(sum(ecarts) / sum(bruits), 2), "paires_de_saisons": len(ecarts)}
        res[code] = {"saisons": par, "stabilite": stab,
                     "completude": cl[code]["completude_par_saison"], "archive": cl[code]["archive_par_saison"]}
    json.dump({"description": "Frequences de marches (scores joues des archives) et stabilite saison a saison vs bruit d'echantillonnage (ratio ~1 = variation compatible avec le hasard; >1 = derive reelle). Descriptif, sans modele ni cote.", "competitions": res},
              open(os.path.join(RACINE, "data", "inventaire", "regularites_marches.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = ["# Regularites par competition (scores joues, sans modele)", "",
         "Frequence moyenne des marches sur les saisons disponibles et ratio de stabilite (ecart saison a saison / ecart du seul hasard; ~1 = stable comme un tirage, >1 = la frequence bouge reellement d'une saison a l'autre).", "",
         "| Comp | Matchs | Dom | Nul | Ext | Buts | >=2 buts | >=3 | >=4 | BTTS | Ratio 1X2 | Ratio >=3 | Ratio BTTS |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for code, d in res.items():
        S = d["saisons"]; N = sum(x["n"] for x in S.values())
        if not N: continue
        mo = lambda m: sum(x[m] * x["n"] for x in S.values()) / N
        st = d["stabilite"]; r = lambda m: st[m]["ratio"] if m in st else "-"
        r1x2 = round((r("dom") + r("nul") + r("ext")) / 3, 2) if all(m in st for m in ("dom", "nul", "ext")) else "-"
        L.append(f"| {code} | {N} | {mo('dom'):.3f} | {mo('nul'):.3f} | {mo('ext'):.3f} | {sum(x['buts_moy'] * x['n'] for x in S.values()) / N:.2f} | {mo('o15'):.3f} | {mo('o25'):.3f} | {mo('o35'):.3f} | {mo('btts'):.3f} | {r1x2} | {r('o25')} | {r('btts')} |")
    L += ["", "Limites: archives telles quelles (65 saisons sans examen individuel des phases finales, 9 saisons non verifiees, voir `docs/BILAN_ARCHIVE_FD.md`); les formats multi-phases melangent saison reguliere et phases finales presentes dans l'archive; aucune validation de modele ici."]
    open(os.path.join(RACINE, "data", "inventaire", "regularites_marches.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[:48]))
if __name__ == "__main__": main()
