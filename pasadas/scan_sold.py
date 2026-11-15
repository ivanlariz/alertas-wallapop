# Chollos frente a lo que VENDEN los revendedores (y, si no hay ventas, frente a lo que tienen en activo).
# Uso: python3 -I scan_sold.py ref.json [horas] > out.json
import json,re,sys,time,statistics,os,collections,urllib.request
REF=json.load(open(sys.argv[1])); HRS=float(sys.argv[2]) if len(sys.argv)>2 else 2.3
D=os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(D,'scan_new.py')).read().replace("HOURS=float(sys.argv[1]) if len(sys.argv)>1 else 2.5","HOURS=1").split("now=time.time()*1000")[0])
B=open(os.path.join(D,'build_ref.py')).read()
exec("NOISE="+B.split("NOISE=")[1].split("\n")[0]); exec("def mkey"+B.split("def mkey")[1].split("cut=")[0])
RESELLERS=set(json.load(open(os.path.join(D,'reseller_ids.json'))))
PLATW=set('game boy color advance gba gbc gb nintendo ds 3ds 2ds dsi switch oled ps1 ps2 ps3 ps4 ps5 psx psp vita playstation xbox one series wii gamecube cube mega drive megadrive super snes nes n64 64 sega master system saturn dreamcast neo geo pocket sony juegos consola consolas mando mandos cable cables cargador caja cajas lote coleccion retro edicion pal'.split())
idx=collections.defaultdict(list)
_R=[]
for r in REF:
    r['ktoks']=r['key'].split()
    spec=[w for w in r['ktoks'] if w not in PLATW and len(w)>=3]
    if not spec: continue
    if r['fuente']=='activos' and len(r['ktoks'])<3 and r['n']<2: continue
    _R.append(r)
REF=_R
for r in REF:
    idx[r['ktoks'][0]].append(r)
def best_ref(toks,c,pl=None):
    L=set(toks); cands=[]
    Lm=[w for w in L if w not in PLATW]
    for t in L:
        for r in idx.get(t,[]):
            if r['estado']!=c or not set(r['ktoks'])<=L: continue
            extra_digits=[w for w in L-set(r['ktoks']) if w.isdigit() and len(w)<=2]
            if extra_digits and not any(w.isdigit() for w in r['ktoks']): continue
            if any(v in L and v not in r['ktoks'] for v in ('pro','max','ultra','slim','xl','ii','iii','iv','mini','plus','lite','oled','new','2ds','3ds')): continue
            km=[w for w in r['ktoks'] if w not in PLATW]
            if Lm and len(km)/len(Lm)<0.75: continue
            if pl and r.get('plat') and r['plat']!=pl: continue
            cands.append(r)
    if not cands: return None
    sold=[r for r in cands if r['fuente']=='vendidos']
    pool=sold or cands
    return max(pool,key=lambda r:(len(r['ktoks']),r['n']))
now=time.time()*1000; cutoff=now-HRS*3600*1000
Q=list(QUERIES)+[r['key'] for r in sorted([r for r in REF if r['fuente']=='vendidos' and r['mediana']>=40],key=lambda r:-(r['n']*r['mediana']))[:150]]
new={}
for q in Q:
    for i in search(q,'newest',1 if q not in QUERIES else 2):
        if i['created_at']>=cutoff: new[i['id']]=i
    time.sleep(0.35)
ST=collections.Counter(); out=[]
for i in new.values():
    ST['nuevos']+=1
    if i.get('reserved',{}).get('flag'): continue
    t=nn(i['title']); full=nn(i['title']+' '+(i.get('description') or ''))
    if re.search(BAD,t) or re.search(r' (no funciona|no enciende|averiad\w*|para piezas|para reparar|no carga|no lee|se apaga|falla|defecto|carcasa (nueva|de reemplazo|custom|no original)|fuera de la (app|aplicacion)) ',full) or isfake(i): ST['filtro']+=1; continue
    c=cond(full)
    if c=='precintado' and not re.search(r' (precintad\w*|precinto|sellad\w*|nuevo a estrenar) ',t): c='completo'
    r=best_ref(mkey(i['title']),c,plat(t) or plat(full[:200]))
    if not r: ST['sin_referencia']+=1; continue
    ST['con_referencia']+=1
    price=i['price']['amount']
    if r['fuente']=='vendidos': refp=r['mediana'] if r['n']>=2 else r['mediana']*0.9
    else:
        if r['n']<2: ST['ref_activo_unico']+=1; continue   # un solo anuncio en activo no es referencia fiable
        refp=r['mediana']*0.85   # precio pedido en activo: se rebaja un 15% para estimar venta
    cost=price+((4+1+0.05*price) if i['shipping'].get('user_allows_shipping') else 0)
    net=refp*0.95-cost
    if price<=0.80*refp and net>=15 and price>=0.3*refp:
        out.append(dict(titulo=i['title'],precio=price,estado=c,coste_compra=round(cost,2),venta_estimada=round(refp*0.95,2),margen=round(net),url='https://es.wallapop.com/item/'+i['web_slug'],
            ciudad=i['location'].get('city'),envio=i['shipping'].get('user_allows_shipping'),es_revendedor=i.get('user_id') in RESELLERS,descripcion=(i.get('description') or '')[:500],
            fotos=[x['urls']['medium'] for x in i.get('images',[])[:3]],interes=counters(i['id']),
            referencia=dict(fuente=r['fuente'],modelo=r['key'],n=r['n'],mediana=r['mediana'],min=r['min'],max=r['max'],vendedores=r['vendedores'],ejemplos=r['ventas'][:5])))
    time.sleep(0.05)
out.sort(key=lambda x:-x['margen'])
print(json.dumps(dict(stats=ST,revisados=len(new),candidatos=out),ensure_ascii=False,indent=1))
