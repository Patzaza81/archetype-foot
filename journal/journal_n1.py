from __future__ import annotations
import csv, glob, os, re
from journal.journal_memoire import evaluer_marche

def _norm(s):
    return re.sub(r"[^a-z0-9]+","",str(s or "").lower().encode("ascii","ignore").decode())

def _num(v):
    try: return float(v)
    except (TypeError,ValueError): return None

def _date_csv(v):
    s = str(v or "").strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            import datetime
            return datetime.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None

def charger_n1(root="data/football_data/snapshots"):
    rows=[]
    for snapshot in sorted(glob.glob(os.path.join(root,"*"))):
        rawdir=os.path.join(snapshot,"raw")
        if not os.path.isdir(rawdir) or not os.path.exists(os.path.join(snapshot,"_SNAPSHOT_COMPLETE.json")): continue
        saison=os.path.basename(snapshot)
        for path in sorted(glob.glob(os.path.join(rawdir,"**","*.csv"), recursive=True)):
            try:
                with open(path,"r",encoding="utf-8-sig",errors="replace",newline="") as f:
                    reader=csv.DictReader(f)
                    for r in reader:
                        home,away=r.get("HomeTeam"),r.get("AwayTeam")
                        hg,ag=_num(r.get("FTHG")),_num(r.get("FTAG"))
                        if home and away and hg is not None and ag is not None:
                            rows.append({
                                "date": _date_csv(r.get("Date")),
                                "saison":saison,
                                "home":home,
                                "away":away,
                                "hg":hg,
                                "ag":ag,
                                "competition":(r.get("League") or r.get("Div") or os.path.splitext(os.path.basename(path))[0]),
                            })
            except (OSError,csv.Error):
                continue
    return rows

def stats_equipe_marche(rows, team, market, contexte=None, target_date=None):
    target=_norm(team)
    out=[]
    for r in rows:
        if target_date and r.get("date") and r["date"] >= str(target_date):
            continue
        if contexte=="DOMICILE" and _norm(r["home"])!=target: continue
        if contexte=="EXTERIEUR" and _norm(r["away"])!=target: continue
        if contexte is None and target not in {_norm(r["home"]),_norm(r["away"])}: continue
        result=evaluer_marche(market,r["hg"],r["ag"])
        if result is not None: out.append(bool(result))
    if not out:return {"disponible":False,"echantillon":0,"frequence":None}
    return {"disponible":True,"echantillon":len(out),"frequence":round(sum(out)/len(out),4)}

def disponibles(rows): return bool(rows)
