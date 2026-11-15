# Portátiles (ROG Ally, Legion Go, MSI Claw, PSP, PS Vita, Switch 2, PS5): anuncios de las últimas N horas por debajo del máximo
import sys,time,json
H=float(sys.argv[1]) if len(sys.argv)>1 else 1.3
g={'__file__':__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))),'alerta_wallapop.py'),'__name__':'lib'}
exec(open(g['__file__']).read(),g)
nn=g['nn']
def row(busco,venta,margen,mn,debe,excl):
  mx=int((venta-margen-5)/1.05)
  return {'busco':busco,'venta':venta,'max':mx,'min':mn,'grupos':[[nn(a).strip() for a in x.split('/')] for x in debe.split(',')],'excluir':[nn(w).strip() for w in excl.split(',') if w.strip()],'solo_envio':False}
R=[row('rog ally',380,15,200,'ally','ally x'),row('rog ally x',680,15,350,'ally x',''),row('lenovo legion go',450,15,200,'legion go','go s, go 2'),row('legion go s',420,15,200,'legion go s',''),row('legion go 2',900,15,500,'legion go 2',''),row('msi claw',370,15,180,'claw','claw 8, claw 7, 8 ai, 7 ai'),row('msi claw 8 ai',760,15,350,'claw 8',''),
 row('consola psp',100,15,25,'psp, consola/console/sony psp/psp 1000/psp 2000/psp 3000/psp 1004/psp 2004/psp 3004/psp slim','go, vita, street, e1004, umd, pelicula'),row('psp go',140,15,50,'psp go',''),
 row('ps vita',140,15,50,'ps vita/psvita/playstation vita, consola/console/sony/slim/pch/oled/wifi/3g','tv, umd, pelicula'),
 row('switch 2',350,15,200,'switch 2/switch2','solo dock, solo caja, solo mando, oled, lite'),
 row('ps5 digital',480,15,250,'ps5/playstation 5, digital','slim, pro, vr, vr2, portal'),row('ps5',550,15,250,'ps5/playstation 5','slim, pro, digital, vr, vr2, portal'),row('ps5 slim digital',530,15,250,'ps5/playstation 5, slim, digital','pro, vr, vr2, portal'),row('ps5 slim',550,15,250,'ps5/playstation 5, slim','digital, pro, vr, vr2, portal'),row('ps5 pro',1000,15,600,'ps5 pro/playstation 5 pro','slim, vr, vr2, portal, edge')]
now=time.time()*1000; out=[]
for v in R:
  for i in g['buscar'](v):
    if now-i['created_at']>H*3600e3: continue
    v2=dict(v); v2['max']=min(v['max'],v['venta']*0.8)
    if g['encaja'](v2,i): out.append({'fila':v['busco'],'venta':v['venta'],'precio':i['price']['amount'],'titulo':i['title'],'url':'https://es.wallapop.com/item/'+i['web_slug'],'id':i['id'],'user':i['user_id'],'envio':(i.get('shipping') or {}).get('user_allows_shipping'),'desc':(i.get('description') or '')[:400],'ciudad':(i.get('location') or {}).get('city'),'fotos':[im['urls']['medium'] for im in i.get('images',[])[:3]]})
  time.sleep(0.4)
print(json.dumps(out,ensure_ascii=False,indent=1))
