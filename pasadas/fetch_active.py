# Uso: python3 -I fetch_active.py profiles.json carpeta_salida
import json,sys,time,urllib.request,urllib.parse,os
H={'X-DeviceOS':'0','Accept':'application/json','User-Agent':'Mozilla/5.0'}
P=json.load(open(sys.argv[1])); out=sys.argv[2]
for p in P:
    if not p.get('id'): continue
    fn=os.path.join(out,p['slug']+'.json')
    allit=[];nxt=None
    for _ in range(120):
        u=f"https://api.wallapop.com/api/v3/users/{p['id']}/items"+('?'+urllib.parse.urlencode({'since':nxt}) if nxt else '')
        try: r=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=25))
        except Exception: time.sleep(3); continue
        allit+=[dict(id=i['id'],titulo=i['title'],precio=i['price']['amount'],desc=(i.get('description') or '')[:300],url='https://es.wallapop.com/item/'+i['slug'],reservado=bool((i.get('reserved') or {}).get('flag'))) for i in r['data']]
        nxt=(r.get('meta') or {}).get('next')
        if not nxt or not r['data']: break
        time.sleep(0.25)
    json.dump(allit,open(fn,'w'),ensure_ascii=False); print(p['slug'],len(allit),flush=True)
print('TODO_TERMINADO')
