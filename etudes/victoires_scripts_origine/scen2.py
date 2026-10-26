import json,math,collections
R=json.load(open('scen.json'));CUT='2026-04-01'
def wil(k,n):
    z=1.96;p=k/n;d=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/d
def terc(key):
    v=sorted(r[key] for r in R);return v[len(v)//3],v[2*len(v)//3]
T={k:terc(k) for k in ('gfh','gah','gfa','gaa')}
print('Seuils (tiers des données) : domicile marque %.2f/%.2f, encaisse %.2f/%.2f ; extérieur marque %.2f/%.2f, encaisse %.2f/%.2f'%(*T['gfh'],*T['gah'],*T['gfa'],*T['gaa']))
lv=lambda k,x:0 if x<=T[k][0] else (1 if x<=T[k][1] else 2)
NA=['attaque faible','attaque moyenne','attaque forte'];ND=['défense solide','défense moyenne','défense friable']
for r in R: r['sc']=(lv('gfh',r['gfh']),lv('gah',r['gah']),lv('gfa',r['gfa']),lv('gaa',r['gaa']))
G=collections.defaultdict(list)
for r in R: G[r['sc']].append(r)
def st(S,y):
    n=len(S);k=sum(r['res']==y for r in S);return n,k
rows=[]
for sc,S in G.items():
    if len(S)<80: continue
    a=[r for r in S if r['jour']<CUT];b=[r for r in S if r['jour']>=CUT]
    if len(a)<30 or len(b)<30: continue
    for y,nm in (('H','DOMICILE'),('A','EXTÉRIEUR')):
        n,k=st(S,y);na,ka=st(a,y);nb,kb=st(b,y)
        rows.append((nm,sc,n,k/n,wil(k,n),ka/na,kb/nb,len(S)/517))
lab=lambda sc:'DOM %s + %s | EXT %s + %s'%(NA[sc[0]],ND[sc[1]],NA[sc[2]],ND[sc[3]])
for nm in ('DOMICILE','EXTÉRIEUR'):
    print('\n== Scénarios où la VICTOIRE %s est la plus fréquente (n>=80, >=30 matchs avant et après)'%nm)
    L=sorted([x for x in rows if x[0]==nm],key=lambda x:-x[4])[:8]
    for x in L: print('  %s | n=%d | %.1f%% (bas %.1f) | avant %.1f%% / après %.1f%% | %.2f/jour'%(lab(x[1]),x[2],100*x[3],100*x[4],100*x[5],100*x[6],x[7]))
json.dump({'T':T},open('seuils.json','w'))
