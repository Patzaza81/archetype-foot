import json,math,collections,itertools
R=json.load(open('rep1x2.json'))
CUT='2026-04-01'
def wil(k,n):
    z=1.96;p=k/n;d=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/d
mean=lambda l:sum(l)/len(l)
for r in R:
    r['gfh']=mean(r['hm']);r['gah']=mean(r['hc']);r['gfa']=mean(r['am']);r['gaa']=mean(r['ac'])
    r['xh']=(r['gfh']+r['gaa'])/2;r['xa']=(r['gfa']+r['gah'])/2
    r['res']='H' if r['h']>r['a'] else ('A' if r['a']>r['h'] else 'N')
def bil(S):
    n=len(S);c=collections.Counter(r['res'] for r in S);return n,c['H'],c['N'],c['A']
def ligne(nm,S):
    n,h,d,a=bil(S)
    if not n: print('  %-70s aucun match'%nm);return
    print('  %-70s n=%4d | dom %5.1f%% | nul %5.1f%% | ext %5.1f%%'%(nm,n,100*h/n,100*d/n,100*a/n))
print('Matchs analysés',len(R),'| base : dom %.1f%% nul %.1f%% ext %.1f%%'%tuple(100*x/len(R) for x in bil(R)[1:]))
print('\n== TON SCÉNARIO : domicile marque ~3,2 et encaisse ~0,75 ; extérieur marque ~0,75 et encaisse ~2,8')
for tol,lab in ((0.3,'±0,3'),(0.5,'±0,5'),(0.7,'±0,7')):
    S=[r for r in R if abs(r['gfh']-3.2)<=tol and abs(r['gah']-0.75)<=tol and abs(r['gfa']-0.75)<=tol and abs(r['gaa']-2.8)<=tol]
    ligne('chaque moyenne à %s près'%lab,S)
print('  version large : dom marque >=2,5 et encaisse <=1,0 ; ext marque <=1,0 et encaisse >=2,3')
S=[r for r in R if r['gfh']>=2.5 and r['gah']<=1.0 and r['gfa']<=1.0 and r['gaa']>=2.3]
ligne('  >> tous',S);ligne('  >> avant 01/04',[r for r in S if r['jour']<CUT]);ligne('  >> après 01/04',[r for r in S if r['jour']>=CUT])
json.dump(R,open('scen.json','w'))
