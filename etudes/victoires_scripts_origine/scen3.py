import json,math,collections
R=json.load(open('scen.json'));CUT='2026-04-01'
def wil(k,n):
    z=1.96;p=k/n;d=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/d
for r in R:
    r['dh']=r['gfh']-r['gah'];r['da']=r['gfa']-r['gaa'];r['D']=r['dh']-r['da']      # D>0 : le domicile domine
days=517
def st(S):
    n=len(S);c=collections.Counter(r['res'] for r in S);return n,c['H'],c['N'],c['A']
print('D = (buts marqués − encaissés du domicile à domicile) − (buts marqués − encaissés de l\'extérieur à l\'extérieur)\n')
print('%-14s %5s | %6s %6s %6s | %-13s | %s'%('intervalle de D','n','dom','nul','ext','avant / après','par jour'))
edges=[-9,-3,-2.5,-2,-1.5,-1,-0.5,0,0.5,1,1.5,2,2.5,3,9]
for lo,hi in zip(edges,edges[1:]):
    S=[r for r in R if lo<=r['D']<hi];n,h,d,a=st(S)
    if n<30: continue
    a1=[r for r in S if r['jour']<CUT];b1=[r for r in S if r['jour']>=CUT]
    f=lambda L,i:100*st(L)[i]/max(1,st(L)[0])
    best='H' if h>=a else 'A'
    print('%-14s %5d | %5.1f%% %5.1f%% %5.1f%% | dom %.0f/%.0f ext %.0f/%.0f | %.2f'%('[%s ; %s['%(lo if lo>-9 else '−∞',hi if hi<9 else '+∞'),n,100*h/n,100*d/n,100*a/n,f(a1,1),f(b1,1),f(a1,3),f(b1,3),n/days))
print('\n== Cumulatif : D >= seuil (victoire domicile) | D <= −seuil (victoire extérieur)')
for s in (1,1.5,2,2.5,3,3.5,4):
    S=[r for r in R if r['D']>=s];n,h,d,a=st(S);a1=[r for r in S if r['jour']<CUT];b1=[r for r in S if r['jour']>=CUT]
    S2=[r for r in R if r['D']<=-s];n2,h2,d2,a2=st(S2);a3=[r for r in S2 if r['jour']<CUT];b3=[r for r in S2 if r['jour']>=CUT]
    f=lambda L,i:100*st(L)[i]/max(1,st(L)[0])
    print('  s=%.1f | D>=s : n=%4d dom %.1f%% (avant %.0f / après %.0f) %.2f/j | D<=-s : n=%4d ext %.1f%% (avant %.0f / après %.0f) %.2f/j'%(s,n,100*h/max(n,1),f(a1,1),f(b1,1),n/days,n2,100*a2/max(n2,1),f(a3,3),f(b3,3),n2/days))
