import sys,json,time
sys.path.insert(0,'/home/claude/archetype-foot')
from alpha_serie import coeur, robustesse as R
params=coeur.P.charger();out=[];t=time.time()
for src,loader in (('FD',R.charger_bloc),('ARCH',R.charger_archive_archetype)):
    for m in loader():
        try: r=coeur.analyser_match(m['dom'],m['ext'],m['jour'],params)
        except Exception: continue
        if r.get('statut')!='analyse': continue
        picks={}
        for x in r['onglets'].get('equipes',[]):
            if list(x['cle']) in (['1x2','1'],['1x2','2']):
                picks[x['cle'][1]]={'valeur':x['valeur'],'off':x.get('offensive'),'de':x.get('defensive'),'niveau':x.get('ecart_niveau')}
        hm,hc=coeur.serie_lieu(m['dom'],True,m['jour']);am,ac=coeur.serie_lieu(m['ext'],False,m['jour'])
        out.append(dict(src=src,id=m['id'],jour=m['jour'],h=m['h'],a=m['a'],picks=picks,hm=hm,hc=hc,am=am,ac=ac,niv=r['niveaux'],
                        off=r['scenarios_offensifs'],de=r['scenarios_defensifs']))
print(len(out),time.time()-t)
json.dump(out,open('/tmp/claude-0/a/rep1x2.json','w'))
