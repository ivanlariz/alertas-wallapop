# Pasada horaria retro (revisión a mano): candidatos de las últimas H horas con red más amplia que el bot.
# Uso: python3 -I retro_pasada.py H > retro.json
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import alerta_wallapop as a, retro
H = float(sys.argv[1]) if len(sys.argv) > 1 else 1.3
D = os.path.dirname(os.path.abspath(__file__))
VP = os.path.join(D, 'vistos_retro.txt')
vistos = set(open(VP).read().split()) if os.path.exists(VP) else set()
ahora = time.time() * 1000
out, nuevos, n = [], [], 0
for tipo, it in retro.buscar_nuevos(a.get_json, a.LAT, a.LON):
    if ahora - it['created_at'] > H * 3600 * 1000 or it['id'] in vistos:
        continue
    n += 1
    nuevos.append(it['id'])
    motivo, d = retro.valorar(tipo, it, a.get_json, a.nn, a.LAT, a.LON, margen_min=10, estricto_esp=False, requiere_completo=False)
    if not d:
        continue
    v = a.vendedor(it['user_id'])
    vis, fav, conv = a.senales(it['id'])
    out.append({'tipo': 'consola' if tipo == retro.CONSOLAS else 'juego', 'titulo': it['title'], 'precio': it['price']['amount'],
                'url': 'https://es.wallapop.com/item/' + it['web_slug'], 'id': it['id'], 'ciudad': (it.get('location') or {}).get('city'),
                'km_madrid': round(a.km_madrid(it) or -1), 'envio': bool((it.get('shipping') or {}).get('user_allows_shipping')),
                'descripcion': (it.get('description') or '')[:700], 'fotos': [im['urls']['big'] for im in it.get('images', [])[:6]],
                'valoracion': d, 'vendedor': v, 'senales': {'visitas': vis, 'favoritos': fav, 'conversaciones': conv},
                'publicado_hace_min': int((ahora - it['created_at']) / 60000)})
# LOTES (Iván 13/11): colecciones de juegos de las plataformas retro, para valorarlos a mano
import urllib.parse, re
lotes = []
LOTE_Q = ['lote juegos mega drive', 'lote juegos super nintendo', 'lote juegos snes', 'lote juegos saturn', 'lote juegos game boy',
          'lote juegos game boy advance', 'lote juegos ps1', 'lote juegos playstation', 'lote juegos ps2', 'coleccion juegos retro',
          'lote videojuegos retro']
vl = set()
for q in LOTE_Q:
    p = {'keywords': q, 'latitude': a.LAT, 'longitude': a.LON, 'order_by': 'newest', 'source': 'search_box',
         'category_ids': '24200', 'min_sale_price': 20, 'max_sale_price': 3000}
    d = a.get_json('https://api.wallapop.com/api/v3/search?' + urllib.parse.urlencode(p)) or {}
    for it in d.get('data', {}).get('section', {}).get('payload', {}).get('items', []):
        if it['id'] in vistos or it['id'] in vl or ahora - it['created_at'] > H * 3600 * 1000:
            continue
        t, full = a.nn(it['title']), a.nn(it['title'] + ' ' + (it.get('description') or ''))
        if not re.search(r' (lote|lotes|pack|coleccion|juegos|cartuchos) ', t) or re.search(retro.EXCLUIR_TEXTO, full):
            continue
        if not (retro.plataforma(t)[0] or retro.plataforma(full)[0]) or (it.get('reserved') or {}).get('flag'):
            continue
        vl.add(it['id'])
        v = a.vendedor(it['user_id'])
        lotes.append({'titulo': it['title'], 'precio': it['price']['amount'], 'url': 'https://es.wallapop.com/item/' + it['web_slug'],
                      'ciudad': (it.get('location') or {}).get('city'), 'km_madrid': round(a.km_madrid(it) or -1),
                      'envio': bool((it.get('shipping') or {}).get('user_allows_shipping')),
                      'descripcion': (it.get('description') or '')[:1500], 'fotos': [im['urls']['big'] for im in it.get('images', [])[:10]],
                      'vendedor': v, 'publicado_hace_min': int((ahora - it['created_at']) / 60000)})
    time.sleep(0.4)
nuevos += list(vl)
open(VP, 'a').write('\n'.join(nuevos) + '\n')
print(json.dumps({'mirados': n, 'candidatos': out, 'lotes': lotes}, ensure_ascii=False, indent=1))
