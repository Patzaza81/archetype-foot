"""E18 : table « étude complète ». Pour chaque match (bloc, 2 saisons, 38 divisions), uniquement avec des résultats connus avant le jour du match :
 - classement réel de la division-saison à la date du match (points, points par match, différence de buts, goal-average, rang, écarts de points / rang / goal-average), classements domicile et extérieur, forme des 5 derniers ;
 - attaque et défense RÉCIPROQUES AU MÊME LIEU, corrigées de l'adversaire (A à domicile × B à l'extérieur, et inversement) ;
 - nature du championnat sur 300 jours (buts, avantage du terrain, nuls, BTTS, +2,5, équilibre des équipes), niveau (division), continent ;
 - cotes de clôture moyennes du bloc : SEULEMENT mises de côté pour étudier le filtre et les intervalles de cote après la prédiction (jamais une variable du modèle)."""
import time, collections, numpy as np
import commun as C
from commun import *
t0 = time.time(); C.MEQ = 32.0
import json, gzip
raw = {r["id"]: r for r in json.load(gzip.open(ROOT / "data" / "bloc_saisons" / "bloc_2526_2627.json.gz"))["liste"]}
mb, sb, _ = C.charger_bloc(); C.MEQ = 32.0
lig = {k: M.Ligue(v) for k, v in M.index_ligues(mb).items()}
T = np.load("sorties/table2_bloc_tous.npz", allow_pickle=True); ids = list(T["id"]); pos = {i: k for k, i in enumerate(ids)}
D = lambda s: int(np.datetime64(s, "D").astype(int))
EUR = lambda c: not c in ("ARG", "BRA", "MEX", "USA", "CHN", "JPN")
def tier(c):
    d = [ch for ch in c if ch.isdigit()]
    return int(d[0]) + 1 if d and c not in ("B1", "N1", "P1", "T1", "G1") and not c.startswith(("D", "F", "I", "SP")) else (int(d[0]) if d else 1)
TIER = {"E0": 1, "E1": 2, "E2": 3, "E3": 4, "EC": 5, "SC0": 1, "SC1": 2, "SC2": 3, "SC3": 4, "D1": 1, "D2": 2, "I1": 1, "I2": 2, "SP1": 1, "SP2": 2, "F1": 1, "F2": 2}
CONT = {"ARG": 1, "BRA": 1, "MEX": 1, "USA": 1, "CHN": 2, "JPN": 2}
# équipes de chaque division-saison (structure du championnat, pas des résultats)
equipes = collections.defaultdict(set)
for m in mb: equipes[(m["saison"], m["competition"])].update((m["domicile"], m["exterieur"]))
st = collections.defaultdict(lambda: collections.defaultdict(lambda: {"n": 0, "pts": 0, "gf": 0, "ga": 0, "nh": 0, "pth": 0, "gfh": 0, "gah": 0, "na": 0, "pta": 0, "gfa": 0, "gaa": 0, "last": []}))
hist_div = collections.defaultdict(list)       # division -> [(jour_ordinal, h, a)] résultats connus
names = ["pts_A", "pts_B", "ppg_A", "ppg_B", "ppg_gap", "pts_gap", "gdpg_A", "gdpg_B", "gdpg_gap", "ga_ratio_A", "ga_ratio_B", "ga_ratio_gap", "rank_A", "rank_B", "rank_gap", "rank_gap_n", "nteams", "stage",
         "vppg_A", "vppg_B", "vppg_gap", "vgdpg_A", "vgdpg_B", "vgdpg_gap", "vga_ratio_A", "vga_ratio_B", "vga_ratio_gap", "form5_A", "form5_B", "form5_gap",
         "idx_attA", "idx_defA", "idx_attB", "idx_defB", "recip_1", "recip_2", "recip_diff", "recip_lratio", "recip_sum",
         "lg_goals", "lg_hgoals", "lg_agoals", "lg_homewin", "lg_draw", "lg_btts", "lg_o25", "lg_o15", "lg_balance", "lg_tier", "lg_cont"]
feat = {}; cote = {}
par_jour = collections.defaultdict(list)
for m in mb: par_jour[m["jour"]].append(m)
for jour in sorted(par_jour):
    dj = D(jour)
    for m in par_jour[jour]:
        if m["id"] not in pos: continue
        F = C.features(m, lig)
        if F is None: continue
        S = st[(m["saison"], m["competition"])]; a, b = S[m["domicile"]], S[m["exterieur"]]; nt = len(equipes[(m["saison"], m["competition"])])
        ppg = lambda s: s["pts"] / s["n"] if s["n"] else 0.0
        gdpg = lambda s: (s["gf"] - s["ga"]) / s["n"] if s["n"] else 0.0
        gar = lambda gf, ga: np.log(max(gf, 1) / max(ga, 1))          # goal-average : log du rapport buts marqués / encaissés (bornes à 1 pour éviter la division par 0)
        key = lambda s: (s["pts"], s["gf"] - s["ga"], s["gf"])
        rk = lambda team: 1 + sum(1 for t, s in S.items() if s["n"] and key(s) > key(S[team]))
        ra, rb = rk(m["domicile"]), rk(m["exterieur"])
        v = {"pts_A": a["pts"], "pts_B": b["pts"], "ppg_A": ppg(a), "ppg_B": ppg(b), "ppg_gap": ppg(a) - ppg(b), "pts_gap": a["pts"] - b["pts"], "gdpg_A": gdpg(a), "gdpg_B": gdpg(b), "gdpg_gap": gdpg(a) - gdpg(b),
             "ga_ratio_A": gar(a["gf"], a["ga"]), "ga_ratio_B": gar(b["gf"], b["ga"]), "rank_A": ra, "rank_B": rb, "rank_gap": rb - ra, "rank_gap_n": (rb - ra) / nt, "nteams": nt, "stage": (a["n"] + b["n"]) / 2 / max(2 * (nt - 1), 1),
             "vppg_A": a["pth"] / a["nh"] if a["nh"] else 0.0, "vppg_B": b["pta"] / b["na"] if b["na"] else 0.0,
             "vgdpg_A": (a["gfh"] - a["gah"]) / a["nh"] if a["nh"] else 0.0, "vgdpg_B": (b["gfa"] - b["gaa"]) / b["na"] if b["na"] else 0.0,
             "vga_ratio_A": gar(a["gfh"], a["gah"]), "vga_ratio_B": gar(b["gfa"], b["gaa"]),
             "form5_A": np.mean(a["last"][-5:]) if a["last"] else 0.0, "form5_B": np.mean(b["last"][-5:]) if b["last"] else 0.0}
        v["ga_ratio_gap"] = v["ga_ratio_A"] - v["ga_ratio_B"]; v["vppg_gap"] = v["vppg_A"] - v["vppg_B"]; v["vgdpg_gap"] = v["vgdpg_A"] - v["vgdpg_B"]; v["vga_ratio_gap"] = v["vga_ratio_A"] - v["vga_ratio_B"]; v["form5_gap"] = v["form5_A"] - v["form5_B"]
        v.update({"idx_attA": F["attA"]["idx"], "idx_defA": F["defA"]["idx"], "idx_attB": F["attB"]["idx"], "idx_defB": F["defB"]["idx"]})
        v["recip_1"] = v["idx_attA"] * v["idx_defB"]; v["recip_2"] = v["idx_attB"] * v["idx_defA"]; v["recip_diff"] = v["recip_1"] - v["recip_2"]; v["recip_lratio"] = np.log(v["recip_1"] / v["recip_2"]); v["recip_sum"] = v["recip_1"] + v["recip_2"]
        H = [x for x in hist_div[m["competition"]] if dj - 300 <= x[0] < dj]
        if len(H) >= 30:
            h = np.array([x[1] for x in H], float); g = np.array([x[2] for x in H], float)
            v.update({"lg_goals": (h + g).mean(), "lg_hgoals": h.mean(), "lg_agoals": g.mean(), "lg_homewin": (h > g).mean(), "lg_draw": (h == g).mean(), "lg_btts": ((h > 0) & (g > 0)).mean(), "lg_o25": ((h + g) > 2.5).mean(), "lg_o15": ((h + g) > 1.5).mean()})
        else: v.update({k: np.nan for k in ("lg_goals", "lg_hgoals", "lg_agoals", "lg_homewin", "lg_draw", "lg_btts", "lg_o25", "lg_o15")})
        pp = [ppg(s) for s in S.values() if s["n"] >= 3]; v["lg_balance"] = float(np.std(pp)) if len(pp) >= 6 else np.nan
        v["lg_tier"] = TIER.get(m["competition"], 1); v["lg_cont"] = CONT.get(m["competition"], 0)
        feat[m["id"]] = v
        r = raw[m["id"]]["cotes"]; c1 = (r.get("1x2_cloture") or {}).get("moy"); c2 = (r.get("plus_moins_2_5_cloture") or {}).get("moy")
        cote[m["id"]] = (c1 if c1 else [np.nan] * 3) + (c2 if c2 else [np.nan] * 2)
    for m in par_jour[jour]:       # mise à jour APRÈS tous les matchs du jour
        h, g = sb[m["id"]]; S = st[(m["saison"], m["competition"])]; a, b = S[m["domicile"]], S[m["exterieur"]]
        pa, pb = (3, 0) if h > g else ((1, 1) if h == g else (0, 3))
        for s, pts, gf, ga, ven in ((a, pa, h, g, "h"), (b, pb, g, h, "a")):
            s["n"] += 1; s["pts"] += pts; s["gf"] += gf; s["ga"] += ga; s["n" + ven] += 1; s["pt" + ven] += pts; s["gf" + ven] += gf; s["ga" + ven] += ga; s["last"].append(pts)
        hist_div[m["competition"]].append((dj, h, g))
ok = [i for i in ids if i in feat]
X3 = np.array([[feat[i][k] for k in names] for i in ok], float); O = np.array([cote[i] for i in ok], float)
sel = np.array([pos[i] for i in ok])
np.savez_compressed("sorties/table3_bloc.npz", X3=X3, names3=np.array(names), odds=O, ids=np.array(ok), jour=T["jour"][sel], comp=T["comp"][sel], P=T["P"][sel], Y=T["Y"][sel], X2=T["X"][sel], names2=T["names"])
print(len(ok), "matchs", len(names), "variables nouvelles", round(time.time() - t0), "s ; cotes 1x2 connues", int((~np.isnan(O[:, 0])).sum()), "; cotes ±2,5", int((~np.isnan(O[:, 3])).sum()), "; NaN nature championnat", np.isnan(X3[:, names.index("lg_goals")]).mean().round(3))
