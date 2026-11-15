# Buscador de chollos Wallapop (RetrodelNorte). Uso: python3 -I scan_new.py [horas_atras] > out.json
import json,re,sys,time,statistics,unicodedata,urllib.request,urllib.parse
HOURS=float(sys.argv[1]) if len(sys.argv)>1 else 2.5
H={'X-DeviceOS':'0','Accept':'application/json','User-Agent':'Mozilla/5.0'}
LAT,LON=43.263,-2.935
def api(params=None,nxt=None):
    q={'next_page':nxt} if nxt else params
    url='https://api.wallapop.com/api/v3/search?'+urllib.parse.urlencode(q)
    for a in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(url,headers=H),timeout=25))
        except Exception: time.sleep(3*(a+1))
    return None
def search(kw,order='most_relevance',pages=1):
    out=[];d=api({'keywords':kw,'latitude':LAT,'longitude':LON,'source':'search_box','category_id':24200,'order_by':order})
    for p in range(pages):
        if not d: break
        out+=d['data']['section']['payload']['items']
        nx=d.get('meta',{}).get('next_page')
        if not nx or p==pages-1: break
        time.sleep(0.4); d=api(nxt=nx)
    return out
def nn(s):
    s=unicodedata.normalize('NFKD',(s or '').lower()); s=''.join(c for c in s if not unicodedata.combining(c))
    rom={'ii':'2','iii':'3','iv':'4','vi':'6'}
    return ' '+' '.join(rom.get(w,w) for w in re.sub(r'[^a-z0-9]+',' ',s).split())+' '
PLAT={'SNES':[' super nintendo ',' snes ',' supernintendo '],'NES':[' nes '],'N64':[' nintendo 64 ',' n64 '],'GC':[' gamecube ',' game cube '],
 'GB':[' game boy ',' gameboy '],'GBC':[' game boy color ',' gbc '],'GBA':[' game boy advance ',' gba '],'NDS':[' nintendo ds ',' nds '],'3DS':[' 3ds '],
 'MD':[' mega drive ',' megadrive '],'SMS':[' master system '],'GG':[' game gear ',' gamegear '],'SAT':[' saturn '],'DC':[' dreamcast '],
 'PS1':[' ps1 ',' psx ',' playstation 1 ',' psone '],'PS2':[' ps2 ',' playstation 2 '],'PSP':[' psp '],'VITA':[' vita '],'NGPC':[' neo geo pocket '],'WII':[' wii ']}
QUERIES=['super nintendo','snes','nes nintendo','nintendo 64','gamecube','game boy','game boy color','game boy advance','nintendo ds','nintendo 3ds','2ds',
 'mega drive','master system','game gear','sega saturn','dreamcast','ps1','psx','ps2','psp','ps vita','neo geo pocket','wii juego','consola nintendo 3ds','consola 2ds','new 3ds xl','nintendo ds lite','nintendo dsi','game boy advance sp','consola psp','consola ps vita','consola game boy','consola game gear','rog ally','legion go','msi claw','steam deck','psp go','ps vita slim']

MODELS=[('New Nintendo 2DS XL',[' new 2ds xl ',' new nintendo 2ds xl ',' 2ds xl ',' 2ds ll '],[]),
 ('New Nintendo 3DS XL',[' new 3ds xl ',' new nintendo 3ds xl ',' new 3ds ll '],[' 2ds ']),
 ('New Nintendo 3DS',[' new 3ds ',' new nintendo 3ds '],[' xl ',' ll ',' 2ds ']),
 ('Nintendo 3DS XL',[' 3ds xl ',' 3ds ll '],[' new ',' 2ds ']),
 ('Nintendo 2DS',[' 2ds '],[' new ',' xl ',' ll ']),
 ('Nintendo 3DS',[' 3ds '],[' new ',' xl ',' ll ',' 2ds ']),
 ('Nintendo DSi XL',[' dsi xl ',' dsi ll '],[]),('Nintendo DSi',[' dsi '],[' xl ',' ll ',' 3ds ']),
 ('Nintendo DS Lite',[' ds lite '],[' dsi ',' 3ds ']),('Nintendo DS',[' nintendo ds ',' nds '],[' lite ',' dsi ',' 3ds ',' 2ds ',' xl ']),
 ('Game Boy Micro',[' game boy micro ',' gameboy micro '],[]),('Game Boy Advance SP',[' advance sp ',' gba sp ',' game boy sp '],[' micro ']),
 ('Game Boy Advance',[' game boy advance ',' gameboy advance ',' gba '],[' sp ',' micro ']),('Game Boy Color',[' game boy color ',' gameboy color ',' gbc '],[' advance ']),
 ('Game Boy Pocket',[' game boy pocket ',' gameboy pocket '],[' color ']),('Game Boy',[' game boy ',' gameboy '],[' color ',' advance ',' pocket ',' micro ',' sp ',' light ']),
 ('PSP Go',[' psp go '],[]),('PSP Street',[' psp street ',' e1004 '],[]),('PSP',[' psp '],[' go ',' street ',' vita ']),
 ('PS Vita Slim',[' vita slim ',' vita 2000 ',' vita pch 2004 '],[]),('PS Vita',[' vita '],[' slim ',' 2000 ',' tv ']),
 ('Game Gear',[' game gear ',' gamegear '],[]),('Neo Geo Pocket',[' neo geo pocket ',' neogeo pocket '],[]),
 ('Mega Drive II',[' mega drive 2 ',' mega drive ii ',' megadrive 2 ',' megadrive ii '],[]),('Mega Drive',[' mega drive ',' megadrive '],[' mini ']),
 ('Master System',[' master system '],[]),('Super Nintendo',[' super nintendo ',' snes '],[' mini ',' classic ']),('NES',[' nes '],[' mini ',' snes ',' super ']),
 ('Nintendo 64',[' nintendo 64 ',' n64 '],[]),('GameCube',[' gamecube ',' game cube '],[]),('Dreamcast',[' dreamcast '],[]),('Saturn',[' saturn '],[]),
 ('PSone',[' psone ',' ps one '],[]),('PlayStation 2',[' ps2 ',' playstation 2 '],[]),('PlayStation 1',[' playstation 1 ',' ps1 ',' psx '],[])]
def model(t):
    for m,req,forb in MODELS:
        if any(r in t for r in req) and not any(f in t for f in forb): return m
    return None
def counters(iid):
    try: return json.load(urllib.request.urlopen(urllib.request.Request('https://api.wallapop.com/api/v3/items/'+iid+'/counters',headers=H),timeout=20))
    except Exception: return {}
MODEL_CACHE={}
GAMES,CONSOLES=10093,10088
BAD=r' (lote|pack|repro|reproduccion|replica|copia|custom|reemplazo|no original|no es original|eprom|everdrive|flash|r4|busco|compro|cambio|solo caja|caja vacia|solo manual|sin juego|sin cartucho|averiad\w*|no funciona|no enciende|para piezas|piezas|reparar|pantalla rota|bisagra rota|no lee|falla|defecto|ntsc|usa|japon|japones|japonesa|jap|jp|import|aleman|alemana|frances|francesa|italiano|italiana|mini|classic mini|clon|tipo|estilo|emulador|anbernic|retroid|miyoo|modificad\w*|chipead\w*|ips|lona|poster|cuadro|figura|amiibo|funda|carcasa|cargador|cable|mando|placa) '
def isfake(i): return bool(re.search(r'r[\W_]{0,3}[e€3][\W_]{0,3}p[\W_]{0,3}r',(i['title']+' '+(i.get('description') or '')).lower()))
def cond(t):
    if re.search(r' (precintad\w*|precinto|sellad\w*|sigillat\w*|sealed|nuevo a estrenar|sin abrir|nuevo sin estrenar|factory sealed) ',t): return 'precintado'
    if re.search(r' (sin manual|sin instrucciones) ',t) and re.search(r' (caja|box|scatola) ',t) and not re.search(r' sin caja ',t): return 'sin manual'
    if re.search(r' (sin caja|solo cartucho|solo el cartucho|cartucho suelto|suelto|loose|solo juego|solo disco|solo el disco) ',t): return 'suelto'
    if re.search(r' (completo|completa|cib|caja|manual|insert|instrucciones|scatola|box|como nuevo|estuche original) ',t): return 'completo'
    return 'suelto'   # sin especificar: se trata como suelto, y como comparable solo cuenta si no menciona caja, manual ni precinto
def plat(t):
    hits=[(len(a),p) for p,al in PLAT.items() for a in al if a in t]
    return max(hits)[1] if hits else None
def kind(i):
    ids={x.get('id') for x in i.get('taxonomy',[])}
    return 'juego' if GAMES in ids else 'consola' if CONSOLES in ids else None
now=time.time()*1000; cutoff=now-HOURS*3600*1000
new={}
for q in QUERIES:
    for i in search(q,'newest',2):
        if i['created_at']>=cutoff: new[i['id']]=i
    time.sleep(0.4)
import collections
ST=collections.Counter()
cands=[]
for i in new.values():
    ST['nuevos']+=1
    if i.get('reserved',{}).get('flag'): continue
    k=kind(i); t=nn(i['title']); full=nn(i['title']+' '+(i.get('description') or ''))
    if not k: ST['sin_categoria']+=1; continue
    BADK=BAD if k=='juego' else BAD.replace('|funda|carcasa|cargador|cable|mando|placa','|placa|solo carcasa|sin pantalla')
    if re.search(BADK,t) or re.search(BADK,full) or isfake(i): ST['filtro']+=1; continue
    p=plat(t) or plat(full)
    if not p: continue
    price=i['price']['amount']
    if price<8: continue
    c=cond(full)
    if c=='precintado': continue
    if k=='consola' and re.search(r'\((nintendo|sega|sony|ps|game|gba|nds|3ds|psp)',i['title'].lower()): ST['juego_como_consola']+=1; continue
    if k=='consola':
        m=model(t)
        if not m or re.search(r' (juegos|lote|pack|\+) ',t): ST['consola_sin_modelo']+=1; continue
        if m not in MODEL_CACHE:
            L={}
            for q in ('consola '+m.lower(), m.lower()):
                for j in search(q,'most_relevance',3): L[j['id']]=j
                time.sleep(0.4)
            MODEL_CACHE[m]=list(L.values())
        pool=MODEL_CACHE[m]
    else:
        kw=re.sub(r'\(.*?\)|[^\w\s:\'-]',' ',i['title']).strip()
        toks=[w for w in nn(kw).split() if len(w)>2 and w not in ('juego','para','consola','nintendo','sega','sony','the','pal','esp','espana','original','edicion','version','con','del','los','las')][:4]
        if not toks: continue
        pool=search(kw,'most_relevance',2)
    comps=[]; reserved=[]; seen=set()
    for j in pool:
        if j['id'] in seen: continue
        seen.add(j['id'])
        if j['id']==i['id'] or kind(j)!=k: continue
        tj=nn(j['title']); fj=nn(j['title']+' '+(j.get('description') or ''))
        if k=='consola':
            if model(tj)!=m or re.search(r' (juegos|lote|pack|\+) ',tj): continue
        else:
            if not all(' '+w+' ' in tj for w in toks): continue
            fam={'GB','GBC','GBA'}
            pj=plat(tj)
            if pj not in (p,None) and not (pj in fam and p in fam and plat(fj)==p) and not (pj=='GB' and p in fam): continue
            if pj is None and plat(fj)!=p: continue
        BADJ=BAD if k=='juego' else BADK
        if re.search(BADJ,tj) or re.search(BADJ,fj) or isfake(j): continue
        if cond(fj)!=c: continue
        age=(now-j['created_at'])/86400000
        if j.get('reserved',{}).get('flag'): reserved.append((j['price']['amount'],j)); continue
        comps.append((j['price']['amount'],j,age))
    fresh=[x for x in comps if x[2]<=120]
    ST['analizados']+=1
    if len(comps)<3: ST['pocos_comparables']+=1; continue
    ST['con_comparables']+=1
    fresh.sort(key=lambda x:x[0]); comps.sort(key=lambda x:x[0])
    ref=comps[0][0]   # referencia: el comparable MAS BARATO del mismo estado (cualquier antiguedad). Chollo = 25% por debajo de todos los demas
    # costes de compra: envio ~4 EUR + proteccion Wallapop (~1 EUR + 5%); venta: 5% por debajo del mas barato para venderlo rapido
    cost=price+((4+1+0.05*price) if i['shipping'].get('user_allows_shipping') else 0)
    net=ref*0.95-cost
    if price<=0.80*ref and net>=15:
        ci=counters(i['id']); cc=[(x[0],counters(x[1]['id'])) for x in comps[:3]]
        cands.append(dict(tipo=k,plataforma=p,estado=c,precio=price,ref_mas_barato=ref,margen_estimado=round(net),
            coste_compra=round(cost,2),venta_estimada=round(ref*0.95,2),titulo=i['title'],ciudad=i['location'].get('city'),envio=i['shipping'].get('user_allows_shipping'),
            url='https://es.wallapop.com/item/'+i['web_slug'],descripcion=(i.get('description') or '')[:500],
            fotos=[x['urls']['medium'] for x in i.get('images',[])[:3]],
            modelo=(m if k=='consola' else None),
            interes_anuncio=ci, edad_anuncio_h=round((now-i['created_at'])/3600000,1),
            comparables=[dict(precio=x[0],dias_publicado=round(x[2]),estado_detectado=cond(nn(x[1]['title']+' '+(x[1].get('description') or ''))),descripcion=(x[1].get('description') or '')[:200],titulo=x[1]['title'],url='https://es.wallapop.com/item/'+x[1]['web_slug']) for x in comps[:8]],
            interes_3_mas_baratos=[dict(precio=a,**b) for a,b in cc],
            reservados=[dict(precio=x[0],titulo=x[1]['title'],url='https://es.wallapop.com/item/'+x[1]['web_slug']) for x in reserved[:5]],
            n_comparables=len(comps),n_frescos=len(fresh),n_reservados=len(reserved)))
    time.sleep(0.5)
cands.sort(key=lambda r:-r['margen_estimado'])
print(json.dumps(dict(stats=ST,revisados=len(new),candidatos=cands),ensure_ascii=False,indent=1))
