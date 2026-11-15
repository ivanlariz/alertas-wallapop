# Búsqueda de STOCK retro (anuncios ya publicados, no solo los nuevos). Uso: python3 -I retro_stock.py > stock_retro.json
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import alerta_wallapop as a, retro
D = os.path.dirname(os.path.abspath(__file__))
VP = os.path.join(D, 'vistos_stock_retro.txt')
vistos = set(open(VP).read().split()) if os.path.exists(VP) else set()
items = retro.buscar_stock(a.get_json, a.LAT, a.LON)
out = []
for tipo, it in items:
    if it['id'] in vistos:
        continue
    if time.time() * 1000 - it['created_at'] > 30 * 86400 * 1000:     # Iván: más de 1 mes publicado = mala señal
        continue
    motivo, d = retro.valorar(tipo, it, a.get_json, a.nn, a.LAT, a.LON, margen_min=12, estricto_esp=False)
    if not d:
        continue
    out.append({'tipo': 'consola' if tipo == retro.CONSOLAS else 'juego', 'titulo': it['title'], 'precio': it['price']['amount'],
                'url': 'https://es.wallapop.com/item/' + it['web_slug'], 'id': it['id'], 'user_id': it['user_id'],
                'ciudad': (it.get('location') or {}).get('city'), 'km_madrid': round(a.km_madrid(it) or -1),
                'envio': bool((it.get('shipping') or {}).get('user_allows_shipping')),
                'publicado': time.strftime('%Y-%m-%d', time.localtime(it['created_at'] / 1000)),
                'descripcion': (it.get('description') or '')[:600], 'fotos': [im['urls']['big'] for im in it.get('images', [])[:6]],
                'valoracion': d})
print(json.dumps({'mirados': len(items), 'candidatos': sorted(out, key=lambda c: -c['valoracion']['margen'])}, ensure_ascii=False, indent=1))
