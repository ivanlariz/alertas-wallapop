# Uso: python3 -I reviews_sold.py user_id out.json  -> ventas reales (titulo, precio, fecha) a partir de las valoraciones
import json,sys,time,urllib.request,urllib.error,urllib.parse
from concurrent.futures import ThreadPoolExecutor
H={'X-DeviceOS':'0','Accept':'application/json','User-Agent':'Mozilla/5.0'}
uid=sys.argv[1]; MAXP=int(sys.argv[3]) if len(sys.argv)>3 else 50
revs=[];seen=set()
for page in range(MAXP):
    u=f'https://api.wallapop.com/api/v3/users/{uid}/reviews?'+urllib.parse.urlencode({'init':page*40})
    try: r=json.load(urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=20))
    except Exception: break
    new=[x for x in r if x.get('item',{}).get('id') and x['item']['id'] not in seen]
    if not new: break
    for x in new: seen.add(x['item']['id'])
    revs+=new; time.sleep(0.3)
def det(x):
    iid=x['item']['id']
    try:
        d=json.load(urllib.request.urlopen(urllib.request.Request('https://api.wallapop.com/api/v3/items/'+iid,headers=H),timeout=15))
        p=(d.get('price') or {}).get('cash',{}).get('amount')
        return dict(fecha=time.strftime('%Y-%m-%d',time.localtime(x['review']['date']/1000)),titulo=x['item']['title'],precio=p,vendido=bool((d.get('sold') or {}).get('flag')),
                    estado=((d.get('type_attributes') or {}).get('condition') or {}).get('text'),desc=((d.get('description') or {}).get('original') or '')[:300],url='https://es.wallapop.com/item/'+x['item']['web_link'],id=iid,envio=x['review'].get('is_shipping_transaction'))
    except Exception: return dict(fecha=time.strftime('%Y-%m-%d',time.localtime(x['review']['date']/1000)),titulo=x['item']['title'],precio=None,url='https://es.wallapop.com/item/'+x['item']['web_link'],id=iid)
with ThreadPoolExecutor(6) as ex: S=list(ex.map(det,revs))
json.dump(S,open(sys.argv[2],'w'),ensure_ascii=False)
ok=[s for s in S if s.get('precio') and s['precio']>2]
print('valoraciones',len(revs),'con precio real',len(ok),'precio 0/1',len([s for s in S if s.get('precio') is not None and s['precio']<=2]),'sin datos',len([s for s in S if s.get('precio') is None]))
