import pickle,math
A,B,C=pickle.load(open('odds_sets.pkl','rb'))
def wil(k,n):
    if n==0:return 0
    z=1.96;p=k/n;d=1+z*z/n;c=p+z*z/(2*n);s=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n));return (c-s)/d
def st(S,side,pmin,cmin=None,cmax=None,pmax=9):
    i=0 if side=='H' else 2;ck='c1' if side=='H' else 'c2';tag='H' if side=='H' else 'A'
    sel=[r for r in S if pmin<=r['p'][i]<pmax and (cmin is None or (r[ck] is not None and r[ck]>=cmin)) and (cmax is None or (r[ck] is not None and r[ck]<cmax))]
    n=len(sel);w=sum(r['res']==tag for r in sel);j=len({r['jour'] for r in S});return n,w,n-w,(100*w/n if n else 0),n/j,100*wil(w,n)
def row(lbl,S,side,pmin,**k):
    n,w,l,t,f,lo=st(S,side,pmin,**k);return '  %-34s n=%4d  G=%4d P=%4d  %5.1f%%  (bas %4.1f%%)  %.2f/j'%(lbl,n,w,l,t,lo,f)
AB=[r for r in A+B if r['src']=='PIN'];BP=[r for r in C if r['src']=='BP']
Call=C
for side,nm,pg,cmin,bands in (('H','VICTOIRE DOMICILE',(0.50,0.55,0.60,0.65,0.70),1.33,((1.33,1.5),(1.5,1.8),(1.8,9))),('A','VICTOIRE EXTÉRIEUR',(0.35,0.40,0.45,0.50,0.55),1.38,((1.38,1.7),(1.7,2.2),(2.2,99)))):
    print('\n=====',nm,'=====')
    print('[1] Tranches de probabilité, sans filtre de cote — A (2025, appris) | B (janv–mars 26, hors apprentissage) | C réservée (≥01/04/26)')
    for p in pg:
        print(' p>=%.2f'%p); print(row('A  2025',A,side,p));print(row('B  janv–mars 2026',B,side,p));print(row('C  réservée',C,side,p))
    print('[2] Cotes BetPawa réelles (archive 28/09–25/10, %d matchs, période réservée) — sans filtre vs cote min %.2f'%(len(BP),cmin))
    for p in pg:
        print(' p>=%.2f'%p);print(row('sans filtre de cote',BP,side,p));print(row('cote >= %.2f'%cmin,BP,side,p,cmin=cmin))
        for lo,hi in bands: print(row('  cote %.2f–%s'%(lo,'+' if hi>=9 else '%.2f'%hi),BP,side,p,cmin=lo,cmax=hi))
    print('[3] Cotes Pinnacle de clôture (PROXY, 2025–mars 2026, %d matchs avec cote) — effet de la cote à probabilité égale'%len(AB))
    for p in pg:
        print(' p>=%.2f'%p);print(row('sans filtre de cote',AB,side,p));print(row('cote >= %.2f'%cmin,AB,side,p,cmin=cmin))
        for lo,hi in bands: print(row('  cote %.2f–%s'%(lo,'+' if hi>=9 else '%.2f'%hi),AB,side,p,cmin=lo,cmax=hi))
