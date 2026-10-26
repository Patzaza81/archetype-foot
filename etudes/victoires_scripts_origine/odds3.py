import pickle,math,collections
exec(open('odds2.py').read().split("Call=C")[0])
print('Bande de cote seule (toutes probabilités) puis avec p; BP = BetPawa archive, PIN = Pinnacle 2025–mars 2026 (proxy)')
for side,lo,hi in (('H',1.33,1.50),('A',1.38,1.70)):
    print('\n',side,'bande %.2f–%.2f'%(lo,hi))
    for nm,S in (('BP',BP),('PIN',AB)):
        for p in (0,0.45,0.50,0.55):
            print(row('%s p>=%.2f'%(nm,p),S,side,p,cmin=lo,cmax=hi))
    # stabilité PIN par trimestre
    for nm,S in (('PIN',AB),):
        g=collections.defaultdict(list)
        for r in S:
            ck='c1' if side=='H' else 'c2'
            if r[ck] and lo<=r[ck]<hi: g[r['jour'][:7]].append(r['res']==('H' if side=='H' else 'A'))
        ms=sorted(g);tot=[(m,len(g[m]),sum(g[m])) for m in ms]
        print('  PIN par mois:',' '.join('%s %d/%d'%(m[2:],w,n) for m,n,w in tot))
    g=collections.defaultdict(list)
    for r in BP:
        ck='c1' if side=='H' else 'c2'
        if r[ck] and lo<=r[ck]<hi: g[r['jour'][:10]].append(r['res']==('H' if side=='H' else 'A'))
    sem=collections.defaultdict(lambda:[0,0])
    import datetime
    for d,l in g.items():
        wk=datetime.date.fromisoformat(d).isocalendar()[1];sem[wk][0]+=sum(l);sem[wk][1]+=len(l)
    print('  BP par semaine:',' '.join('S%d %d/%d'%(k,v[0],v[1]) for k,v in sorted(sem.items())))
