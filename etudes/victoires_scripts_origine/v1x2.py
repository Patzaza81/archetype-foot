import json,math,itertools,collections
R=json.load(open('rep1x2.json'))
def wil(k,n):
    if not n:return 0
    z=1.96;p=k/n;d=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/d
for r in R:
    hm,hc,am,ac=r['hm'],r['hc'],r['am'],r['ac']
    nh,na=len(hm),len(am)
    r['wh']=sum(a>c for a,c in zip(hm,hc))/nh; r['lh']=sum(a<c for a,c in zip(hm,hc))/nh; r['dh']=sum(a==c for a,c in zip(hm,hc))/nh
    r['wa']=sum(a>c for a,c in zip(am,ac))/na; r['la']=sum(a<c for a,c in zip(am,ac))/na
    r['gdh']=sum(a-c for a,c in zip(hm,hc))/nh; r['gda']=sum(a-c for a,c in zip(am,ac))/na   # différence de buts moyenne
    off,de=r['off'],r['de']
    # pour chaque paire: buts dom prévus=(A+C)/2 avec A=off[i][0] (marqués dom), C=de[i][0] (encaissés ext); buts ext=(B+D)/2
    ph=0;pe=0;pn=len(off)
    for o,d in zip(off,de):
        gh=(o[0]+d[0])/2; ge=(o[1]+d[1])/2
        ph+=gh>ge; pe+=ge>gh
    r['ph']=ph/pn if pn else 0; r['pe']=pe/pn if pn else 0
    r['dd']=r['niv']['dom']-r['niv']['ext']
    r['yh']=int(r['h']>r['a']); r['ya']=int(r['a']>r['h'])
CUT='2026-04-01'
dev=[r for r in R if r['jour']<CUT];te=[r for r in R if r['jour']>=CUT]
days=len({r['jour'] for r in R})
print('matchs',len(R),'jours',days,'| victoire dom %.1f%% ext %.1f%% nul %.1f%%'%(100*sum(r['yh'] for r in R)/len(R),100*sum(r['ya'] for r in R)/len(R),100*(1-sum(r['yh'] for r in R)/len(R)-sum(r['ya'] for r in R)/len(R))))
def f(S,y):
    n=len(S);k=sum(r[y] for r in S);return '%5d %5.1f%% (bas %4.1f)'%(n,100*k/n if n else 0,100*wil(k,n)) if n else '    0'
for lab,key,y in (('VICTOIRE DOMICILE','1','yh'),('VICTOIRE EXTÉRIEUR','2','ya')):
    P=[r for r in R if key in r['picks']]
    print('\n== Choix actuels d\'alpha :',lab,'| n=%d (%.1f/jour)'%(len(P),len(P)/days),'| avant',f([r for r in P if r['jour']<CUT],y),'| après',f([r for r in P if r['jour']>=CUT],y))
    for nm,fn in (('valeur>=0.9',lambda r:r['picks'][key]['valeur']>=0.9),('valeur>=0.8',lambda r:r['picks'][key]['valeur']>=0.8)):
        S=[r for r in P if fn(r)];print('   ',nm,f(S,y))
json.dump(R,open('rep1x2_feat.json','w'))
