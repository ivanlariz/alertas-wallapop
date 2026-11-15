# Uso: python3 -I build_ref.py carpeta_sold carpeta_active ref.json  -> precios de venta reales por modelo y estado
import json,glob,re,sys,time,statistics,unicodedata,os,collections
SRC=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'scan_new.py')).read()
exec(SRC.replace("HOURS=float(sys.argv[1]) if len(sys.argv)>1 else 2.5","HOURS=1").split("now=time.time()*1000")[0])
NOISE=set('nuev precint precinta precintad estrenar'.split())|set('nuevo nueva nuevos sin uso abrir como 100 99 98 97 96 95 94 recibo ticket cobertura garantia applecare con y de del la el los las para disparos dis consola camara objetivo excelente estado perfecto perfecta impecable precintada precintado oferta envio gratis incluye original originales firmware ciclos ciclo version edicion juego juegos videojuego pal esp espana espanol castellano the of a en cartucho disco nintendo sega sony pack lote buen muy funciona funcionando probado'.split())
def mkey(title):
    t=nn(re.sub(r'\(.*?\)|\|.*$|\[.*?\]','',title))
    t=re.sub(r' \d+k? (disparos|dis|ciclos) ',' ',t)
    t=t.replace(' series x ',' seriesx ').replace(' series s ',' seriess ').replace(' one x ',' onex ').replace(' one s ',' ones ')
    return [w for w in t.split() if (w not in NOISE and len(w)>1 and not w.startswith(('precint','nuev'))) or w.isdigit()]
cut=time.time()-90*86400   # solo ventas de los ultimos 3 meses
g=collections.defaultdict(list)
for fn in glob.glob(os.path.join(sys.argv[1],'*.json')):
    seller=os.path.basename(fn)[:-5]
    for s in json.load(open(fn)):
        p=s.get('precio')
        if not p or p<=2: continue
        try:
            if time.mktime(time.strptime(s['fecha'],'%Y-%m-%d'))<cut: continue
        except Exception: continue
        toks=mkey(s['titulo'])
        if len(toks)<2: continue
        txt=nn(s['titulo']+' '+(s.get('desc') or ''))
        c=cond(txt)
        g[(' '.join(toks),c)].append(dict(precio=p,fecha=s['fecha'],titulo=s['titulo'],url=s['url'],vendedor=seller))
act=collections.defaultdict(list)
for fn in glob.glob(os.path.join(sys.argv[2],'*.json')):
    seller=os.path.basename(fn)[:-5]
    for s in json.load(open(fn)):
        p=s.get('precio')
        if not p or p<=2: continue
        toks=mkey(s['titulo'])
        if len(toks)<2: continue
        act[(' '.join(toks),cond(nn(s['titulo']+' '+(s.get('desc') or ''))))].append(dict(precio=p,titulo=s['titulo'],url=s['url'],vendedor=seller))
ref=[]
for (k,c),v in act.items():
    ps=sorted(x['precio'] for x in v)
    pl=collections.Counter(plat(nn(x['titulo']+' '+(x.get('desc') or '')[:120])) for x in v).most_common(1)[0][0]
    ref.append(dict(plat=pl,fuente='activos',key=k,estado=c,n=len(v),mediana=statistics.median(ps),min=ps[0],max=ps[-1],vendedores=len({x['vendedor'] for x in v}),ventas=v[:6]))
for (k,c),v in g.items():
    ps=sorted(x['precio'] for x in v)
    pl=collections.Counter(plat(nn(x['titulo'])) for x in v).most_common(1)[0][0]
    ref.append(dict(plat=pl,fuente='vendidos',key=k,estado=c,n=len(v),mediana=statistics.median(ps),min=ps[0],max=ps[-1],ultima=max(x['fecha'] for x in v),vendedores=len({x['vendedor'] for x in v}),ventas=sorted(v,key=lambda x:x['fecha'],reverse=True)[:6]))
ref.sort(key=lambda r:-r['n'])
json.dump(ref,open(sys.argv[3],'w'),ensure_ascii=False)
V=[r for r in ref if r['fuente']=='vendidos']; A=[r for r in ref if r['fuente']=='activos']
print('modelos vendidos',len(V),'ventas',sum(r['n'] for r in V),'| modelos en activo',len(A),'anuncios',sum(r['n'] for r in A))
