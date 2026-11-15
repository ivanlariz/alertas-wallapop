# Historial de ventas Wallapop (consolas). Uso: python3 -I track.py activos_prev.json > salida.json
# Uso: python3 -I track.py activos.json  -> actualiza activos.json (estado) e imprime ventas, cambios y resumen por modelo
import json,re,sys,time,urllib.request,urllib.error,urllib.parse,unicodedata
src=open(__file__.replace('track.py','scan_new.py')).read()
exec(src.replace("HOURS=float(sys.argv[1]) if len(sys.argv)>1 else 2.5","HOURS=2.5").split("now=time.time()*1000")[0])
now=time.time(); hoy=time.strftime('%Y-%m-%d %H:%M',time.localtime(now))
import os
STATE=sys.argv[1]
prev={r['id']:r for r in json.load(open(STATE))} if os.path.exists(STATE) else {}
BADK=BAD.replace('|funda|carcasa|cargador|cable|mando|placa','|placa|solo carcasa|sin pantalla')
INICIO_CONSOLA=r' (nintendo|super nintendo|supernintendo|snes|sega|sony|playstation|ps|ps1|ps2|psx|psone|psp|ps vita|psvita|game boy|gameboy|game gear|gamegear|game cube|gamecube|consola|console|consolle|new|neo geo|mega drive|megadrive|master system|dreamcast|saturn|xbox|wii|nes|famicom|atari|commodore|gba|nds|ds|ds lite|dsi|3ds|2ds|n64|lotto|lote|pack|2 consolas) '
def parece_juego(titulo, desc=''):
    # juegos o accesorios que el vendedor ha subido en la categoria de consolas
    t=nn(titulo); d=nn((desc or '')[:80])
    if re.search(r' (consola|consolas|console|consolle) ',t): return False
    if re.match(r' (juego|videojuego|jogo|gioco|cartucho|cartuccia|cartridge) ',t): return True
    if re.match(r' (videojuego|juego|jogo|cartucho) ',d): return True
    if not re.match(INICIO_CONSOLA,t) and re.search(r' para |[(]',titulo.lower()): return True
    return False
cur={}
for m,_,_ in MODELS:
    for q,o,pg in (('consola '+m.lower(),'most_relevance',3),(m.lower(),'newest',1)):
        for i in search(q,o,pg):
            if kind(i)!='consola': continue
            t=nn(i['title']); full=nn(i['title']+' '+(i.get('description') or ''))
            if model(t)!=m or re.search(BADK,t) or re.search(BADK,full) or isfake(i) or re.search(r' (juegos|lote|pack|\+) ',t): continue
            if i['price']['amount']<10: continue
            if parece_juego(i['title'],i.get('description')): continue
            caja='con caja' if re.search(r' (en su caja|con caja|caja original|en caja|completa|cib|embalaje original) ',full) and not re.search(r' sin caja ',full) else 'suelta'
            cur[i['id']]=dict(id=i['id'],modelo=m,estado=caja,precio=i['price']['amount'],reservado='SÍ' if i.get('reserved',{}).get('flag') else '',
                publicado=time.strftime('%Y-%m-%d',time.localtime(i['created_at']/1000)),titulo=i['title'][:80],ciudad=i['location'].get('city') or '',url='https://es.wallapop.com/item/'+i['web_slug'])
            time.sleep(0.05)
        time.sleep(0.4)
def gone(iid):
    try: urllib.request.urlopen(urllib.request.Request('https://api.wallapop.com/api/v3/items/'+iid,headers=H),timeout=15); return False
    except urllib.error.HTTPError as e: return e.code in (404,410)
    except Exception: return False
activos=[];ventas=[];cambios=[]
for iid,c in cur.items():
    p=prev.get(iid)
    if p:
        c['primera_vista']=p['primera_vista']; c['precio_inicial']=p['precio_inicial']
        c['precio_anterior']=p.get('precio_anterior',''); c['fecha_cambio']=p.get('fecha_cambio','')
        c['reservado_desde']=p.get('reservado_desde','')
        for k in ('visitas','favs','cnt_ts'): c[k]=p.get(k)
        if float(p['precio'])!=c['precio']:
            cambios.append([hoy,c['modelo'],c['estado'],float(p['precio']),c['precio'],c['titulo'],c['url']])
            c['precio_anterior']=float(p['precio']); c['fecha_cambio']=hoy
        if c['reservado'] and not p.get('reservado'):
            c['reservado_desde']=hoy
            ventas.append([hoy,'reservado',c['modelo'],c['estado'],c['precio'],c.get('precio_anterior',''),c['precio'] if not c['precio_anterior'] or float(c['precio_anterior'])<=c['precio'] else float(c['precio_anterior']),c['publicado'],c['titulo'],c['ciudad'],c['url'],round((now-time.mktime(time.strptime(c['publicado'],'%Y-%m-%d')))/86400),c.get('visitas') or '',c.get('favs') or ''])
    else:
        c.update(primera_vista=hoy,precio_inicial=c['precio'],precio_anterior='',fecha_cambio='',reservado_desde=hoy if c['reservado'] else '')
    c['ultima_vista']=hoy; activos.append(c)
# los que ya no salen en la busqueda: comprobar si el anuncio existe
for iid,p in prev.items():
    if iid in cur: continue
    if parece_juego(p['titulo']): continue      # se clasifico mal como consola: se descarta sin contarlo como venta
    if gone(iid):
        pa=p.get('precio_anterior'); pr=float(p['precio'])
        # si bajó el precio en las ultimas 48 h antes de desaparecer, el precio real suele ser el anterior
        real=pr
        if pa not in ('',None) and float(pa)>pr and p.get('fecha_cambio'):
            try:
                if now-time.mktime(time.strptime(p['fecha_cambio'],'%Y-%m-%d %H:%M'))<=48*3600: real=float(pa)
            except Exception: pass
        dias=round((now-time.mktime(time.strptime(p['publicado'],'%Y-%m-%d')))/86400)
        ventas.append([hoy,'desaparecido' if not p.get('reservado') else 'desaparecido (estaba reservado)',p['modelo'],p['estado'],pr,pa,real,p['publicado'],p['titulo'],p['ciudad'],p['url'],dias,p.get('visitas') or '',p.get('favs') or ''])
    else:
        activos.append(p)   # sigue publicado aunque no haya salido en esta búsqueda
    time.sleep(0.3)
import statistics
# visitas y favoritos: refresca hasta 300 anuncios por pasada (los que nunca se miraron o hace >12 h)
pend=sorted([a for a in activos if not a.get('cnt_ts') or now-a['cnt_ts']>12*3600],key=lambda a:a.get('cnt_ts') or 0)[:300]
for a in pend:
    try:
        cc=json.load(urllib.request.urlopen(urllib.request.Request('https://api.wallapop.com/api/v3/items/'+a['id']+'/counters',headers=H),timeout=15))
        a['visitas'],a['favs'],a['cnt_ts']=cc.get('views',0),cc.get('favorites',0),now
    except Exception: pass
    time.sleep(0.12)
# historial acumulado de ventas para el ritmo de venta
VH=STATE.replace('activos.json','ventas_hist.json')
vh=json.load(open(VH)) if os.path.exists(VH) else {}
for v in ventas:
    k=v[10].rsplit('-',1)[-1]
    if k in vh and vh[k]['senal']=='reservado' and v[1].startswith('desaparecido'): continue   # ya contada al reservarse
    vh[k]=dict(fecha=v[0][:10],senal='reservado' if v[1]=='reservado' else 'desaparecido',modelo=v[2],estado=v[3],precio=float(v[6]),
               dias=v[11] if len(v)>11 else None,visitas=(v[12] or None) if len(v)>12 else None,favs=(v[13] or None) if len(v)>13 else None)
json.dump(vh,open(VH,'w'),ensure_ascii=False)
json.dump(activos,open(STATE,'w'),ensure_ascii=False)
g={}
for a in activos: g.setdefault((a['modelo'],a['estado']),[]).append(float(a['precio']))
por_modelo=[[m,e,len(v),min(v),statistics.median(v)] for (m,e),v in sorted(g.items())]
print(json.dumps(dict(fecha=hoy,n_activos=len(activos),ventas=ventas,cambios=cambios,por_modelo=por_modelo),ensure_ascii=False))
