# Busqueda completa: cada venta real reciente de los revendedores (>=40 EUR, ultimos 90 dias) se busca en TODO Wallapop.
# Uso: python3 -I stock_scan.py carpeta_sold > stock.json
import json,glob,os,re,sys,time,statistics,collections,urllib.request,urllib.parse
D=os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(D,'scan_new.py')).read().replace("HOURS=float(sys.argv[1]) if len(sys.argv)>1 else 2.5","HOURS=1").split("now=time.time()*1000")[0])
B=open(os.path.join(D,'build_ref.py')).read()
exec("NOISE="+B.split("NOISE=")[1].split("\n")[0]); exec("def mkey"+B.split("def mkey")[1].split("cut=")[0])
RES=set(json.load(open(os.path.join(D,'reseller_ids.json'))))
VARIANT=['pro','max','ultra','slim','digital','xl','ii','iii','iv','mini','plus','lite','oled','air','new','2ds','3ds','dsi','go','street','advance','color','pocket','micro']
BADX=r' (despiece|folleto|solo el folleto|ssd|disco duro|carcasa para|funda|protector|no funciona|no enciende|averiad\w*|para piezas|para reparar|no carga|no lee|se apaga|falla|defecto|carcasa (nueva|de reemplazo|custom|no original)|fuera de la (app|aplicacion)|solo caja|caja vacia|solo manual|busco|compro|cambio) '
cut=time.time()-90*86400
sales=[]
for fn in glob.glob(os.path.join(sys.argv[1],'*.json')):
    for s in json.load(open(fn)):
        if not s.get('precio') or s['precio']<40: continue
        try:
            if time.mktime(time.strptime(s['fecha'],'%Y-%m-%d'))<cut: continue
        except Exception: continue
        s['vendedor']=os.path.basename(fn)[:-5]; sales.append(s)
groups=collections.defaultdict(list)
for s in sales:
    toks=mkey(s['titulo'])
    if len(toks)<2: continue
    c=cond(nn(s['titulo']+' '+(s.get('desc') or '')))
    groups[(' '.join(toks),c)].append(s)
out=[]; n=0
for (k,c),ss in groups.items():
    n+=1
    toks=k.split(); ref=statistics.median([x['precio'] for x in ss]); pl=plat(nn(ss[0]['titulo']))
    var=[v for v in VARIANT if v in toks]
    seen=set(); found=[]
    for j in search(' '.join(toks[:6]),'most_relevance',2):
        if j['id'] in seen or j.get('user_id') in RES or j.get('reserved',{}).get('flag'): continue
        seen.add(j['id'])
        tj=nn(j['title']); fj=nn(j['title']+' '+(j.get('description') or ''))
        jt=set(mkey(j['title']))
        if not set(toks)<=jt: continue
        if re.search(r'^ (caja|manual|folleto|insert|funda) ',tj): continue
        if any(v in jt and v not in var for v in VARIANT): continue
        if any(w.isdigit() and len(w)<=2 and w not in toks for w in jt) : continue
        pj=plat(tj)
        if pl and pj and pj!=pl: continue
        if re.search(BAD,tj) or re.search(BADX,fj) or isfake(j): continue
        if cond(fj)!=c: continue
        p=j['price']['amount']
        if p<0.4*ref: continue
        cost=p+((4+1+0.05*p) if j['shipping'].get('user_allows_shipping') else 0)
        net=ref*0.95-cost
        if p<=0.8*ref and net>=15:
            found.append(dict(precio=p,margen=round(net),titulo=j['title'],url='https://es.wallapop.com/item/'+j['web_slug'],ciudad=j['location'].get('city'),envio=j['shipping'].get('user_allows_shipping'),
                dias=round((time.time()*1000-j['created_at'])/864e5),desc=(j.get('description') or '')[:400],fotos=[x['urls']['medium'] for x in j.get('images',[])[:3]],id=j['id']))
    if found:
        found.sort(key=lambda x:-x['margen'])
        out.append(dict(modelo=k,estado=c,ref_mediana=ref,n_ventas=len(ss),ventas=[dict(fecha=x['fecha'],precio=x['precio'],titulo=x['titulo'],url=x['url'],vendedor=x['vendedor']) for x in sorted(ss,key=lambda x:x['fecha'],reverse=True)[:4]],baratos=found[:4]))
    if n%50==0: print(n,len(groups),len(out),file=sys.stderr,flush=True)
    time.sleep(0.4)
out.sort(key=lambda o:-o['baratos'][0]['margen'])
print(json.dumps(out,ensure_ascii=False,indent=1))
