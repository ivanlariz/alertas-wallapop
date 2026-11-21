#!/usr/bin/env python3
"""Bot de ventas de revendedores (RetrodelNorte).

Cada 8 horas (GitHub Actions, workflow revendedores.yml):
  1. Mira las valoraciones de los revendedores que sigue Iván: cada valoración de venta es un artículo vendido,
     con su título, el último precio que tenía y la fecha.
  2. Apunta las ventas nuevas desde la última vez.
  3. Para las que cumplen los criterios retro de Iván (juego completo PAL España de sus plataformas, o portátil con
     caja), busca en Wallapop el mismo producto más barato que lo que lo vendió el revendedor.
  4. Manda UN correo a Iván con las ventas y los anuncios más baratos encontrados.

Variables de entorno:
  REVENDEDORES        ids de usuario de Wallapop de los revendedores, separados por comas o espacios (secreto de GitHub).
                      Si falta, se leen de revendedores.txt (no se sube al repositorio).
  GMAIL_USER, GMAIL_APP_PASSWORD, ALERT_TO   como en alerta_wallapop.py
  VENTANA_HORAS       ventas de las últimas N horas en la primera ejecución sin estado (por defecto 72)
Sin GMAIL_USER/GMAIL_APP_PASSWORD no envía nada: imprime el resumen (modo prueba).
Los registros de GitHub son públicos: aquí solo se imprimen recuentos, nunca nombres de vendedores.
"""
import html, json, os, re, smtplib, sys, time, urllib.parse
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

import alerta_wallapop as aw
import retro as R

AQUI = os.path.dirname(os.path.abspath(__file__))
ESTADO = os.path.join(AQUI, '.revendedores_estado.json')
API = 'https://api.wallapop.com/api/v3/'


def ids_revendedores():
    txt = os.environ.get('REVENDEDORES', '').strip()
    if not txt and os.path.exists(os.path.join(AQUI, 'revendedores.txt')):
        txt = open(os.path.join(AQUI, 'revendedores.txt')).read()
    ids = re.findall(r'[a-z0-9]{12}', txt)
    return list(dict.fromkeys(ids))


def cargar_estado():
    try:
        return json.load(open(ESTADO))
    except Exception:
        return {}


def ventas_nuevas(uid, desde_ms, vistos):
    """Ventas (valoraciones de tipo 'sell') del revendedor posteriores a desde_ms y no vistas."""
    out = []
    for pagina in range(3):
        r = aw.get_json(API + f'users/{uid}/reviews?' + urllib.parse.urlencode({'init': pagina * 40}))
        if not r:
            break
        parar = False
        for x in r:
            fecha = (x.get('review') or {}).get('date') or 0
            iid = (x.get('item') or {}).get('id')
            if fecha < desde_ms:
                parar = True
                continue
            if x.get('type') == 'sell' and iid and iid not in vistos:
                out.append(x)
        if parar or len(r) < 40:
            break
        time.sleep(0.4)
    return out


def detalle(x):
    """Datos del artículo vendido (el anuncio sigue accesible tras la venta, con su último precio)."""
    it = x['item']
    d = aw.get_json(API + 'items/' + it['id']) or {}
    titulo = ((d.get('title') or {}).get('original')) or it.get('title') or ''
    desc = ((d.get('description') or {}).get('original')) or ''
    precio = ((d.get('price') or {}).get('cash') or {}).get('amount')
    return {'id': it['id'], 'titulo': titulo, 'desc': desc, 'precio': precio,
            'fecha': time.strftime('%d/%m %H:%M', time.localtime(x['review']['date'] / 1000)),
            'envio': bool(x['review'].get('is_shipping_transaction')),
            'url': 'https://es.wallapop.com/item/' + (it.get('web_link') or it['id']),
            'img': ((it.get('image') or {}).get('medium')) or ''}


RESTO_CONSOLA = set('nintendo sony sega consola console portatil caja original originales completa completo con en su y de la el '
                   'instrucciones manual cargador funda edicion color colour pocket advance sp classic clasica negra negro blanca '
                   'blanco azul roja rojo verde amarilla amarillo morada transparente plata plateada gris rosa'.split())


ROMANOS = {'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'}


def numeros(t):
    """Números de entrega del título (2, II, 3…), sin los que forman parte del nombre de la plataforma."""
    t = re.sub(r' (nintendo 64|n64|ps1|ps2|playstation [12]|mega drive (ii|2)|16 bit|64 bit|32x) ', ' ', t)
    return {ROMANOS.get(w, w) for w in t.split() if (w.isdigit() and len(w) <= 2) or w in ROMANOS}


def es_consola_portatil(t, plat):
    """Título de una consola portátil (no un juego que nombra la consola, p. ej. «UNO Game Boy Color»)."""
    m = R.modelo_consola(t, plat)
    if not m or re.search(r' (juego|videojuego|cartucho|umd) ', t):
        return False
    resto = [w for w in aw.nn(re.sub(m[3], ' ', t)).split() if w not in RESTO_CONSOLA and not w.isdigit()]
    return not resto


def clasificar(v):
    """¿Cumple los criterios retro de Iván? Devuelve (tipo, plataforma, etiqueta, motivo_si_no)."""
    raw = v['titulo'] + ' ' + v['desc']
    t, full = aw.nn(v['titulo']), aw.nn(raw)
    # Solo el título: las descripciones de los revendedores llevan listas de etiquetas de todas las consolas
    plat, nombre = R.plataforma(t)
    if not plat or re.search(r' (ps3|ps4|ps5|xbox|switch|wii|nes|gamecube|3ds|2ds|nds|master system|game gear) ', t):
        return None, None, None, 'no es de tus plataformas retro'
    if re.search(R.EXCLUIR_TITULO, t) or re.search(R.EXCLUIR_TEXTO, full):
        return None, plat, None, 'lote, repro o accesorio'
    if re.search(R.INCOMPLETO, full):
        return None, plat, None, 'incompleto'
    modelo = R.modelo_consola(t, plat)
    es_consola = es_consola_portatil(t, plat)
    if not es_consola and re.search(r' (consola|console) ', t):
        return None, plat, None, 'consola de sobremesa suelta'
    if es_consola:
        if not (re.search(R.CAJA_CONSOLA, full) or re.search(r' (en caja|en su caja|con caja|con su caja|caja original) ', full)):
            return None, plat, None, 'consola sin caja'
        return R.CONSOLAS, plat, f'consola {modelo[0]} con caja', None
    # Los revendedores casi nunca escriben «completo» al vender: basta con que no sea extranjero.
    # Los anuncios más baratos sí tienen que ser completos y PAL España (ver mas_baratos).
    if re.search(R.ESP_NO, re.sub(R.QUITAR_ESP, ' ', full)):
        return None, plat, None, 'versión extranjera'
    completo = bool(re.search(R.COMPLETO, full))
    return R.JUEGOS, plat, f'juego {nombre}' + (' completo' if completo else ''), None


def mas_baratos(v, tipo, plat, revendedores):
    """Anuncios activos del mismo producto, completos y PAL España, que dejan margen frente al precio de venta."""
    venta = v['precio']
    if tipo == R.CONSOLAS:
        modelo = R.modelo_consola(aw.nn(v['titulo']), plat)
        claves, consulta = [], modelo[2].replace(' caja', '')
    else:
        modelo = None
        claves = R.claves_titulo(v['titulo'], aw.nn)
        if not claves:
            return []
        consulta = ' '.join(claves) + ' ' + next(qs[0] for c, _, _, qs in R.PLATAFORMAS if c == plat)
    q = {'keywords': consulta, 'latitude': aw.LAT, 'longitude': aw.LON, 'source': 'search_box',
         'category_ids': '24200', 'subcategory_ids': tipo, 'order_by': 'price_low_to_high',
         'min_sale_price': max(3, int(venta * 0.15)), 'max_sale_price': int(venta)}
    d = aw.get_json(API + 'search?' + urllib.parse.urlencode(q))
    out = []
    for c in (d or {}).get('data', {}).get('section', {}).get('payload', {}).get('items', []):
        if c['id'] == v['id'] or (c.get('user_id') in revendedores) or (c.get('reserved') or {}).get('flag'):
            continue
        raw = c['title'] + ' ' + (c.get('description') or '')
        t, full = aw.nn(c['title']), aw.nn(raw)
        if claves and not all(f' {k} ' in t for k in claves):
            continue
        if numeros(t) != numeros(aw.nn(v['titulo'])):
            continue                                   # Mega Games 2 ≠ Mega Games I, Sonic Adventure ≠ Sonic Adventure 2
        if re.search(r' (trial|demo|promo|promocional|not for resale) ', full):
            continue
        if R.plataforma(t)[0] != plat and R.plataforma(full)[0] != plat:
            continue
        if modelo and ((R.modelo_consola(t, plat) or (None,))[0] != modelo[0] or not es_consola_portatil(t, plat)):
            continue
        if tipo == R.JUEGOS and es_consola_portatil(t, plat):
            continue
        if re.search(R.EXCLUIR_TITULO, t) or re.search(R.EXCLUIR_TEXTO, full) or re.search(R.INCOMPLETO, full):
            continue
        # Muchos anuncios no escriben «completo» ni «PAL España» aunque lo sean: valen con 3 o más fotos y sin
        # señales de ser extranjeros, y se marcan para comprobarlo en las fotos (como la pasada a mano).
        if re.search(R.ESP_NO, re.sub(R.QUITAR_ESP, ' ', full)) or '🇯🇵' in raw or '🇺🇸' in raw:
            continue
        fotos = len(c.get('images') or [])
        completo = bool(re.search(R.COMPLETO if tipo == R.JUEGOS else R.CAJA_CONSOLA, full))
        if not completo and (fotos < 3 or re.search(r' (cartucho|solo disco|suelto|suelta) ', t)
                             or (tipo == R.CONSOLAS and not re.search(r' caja ', full))):
            continue
        esp = R.es_espanol(raw, full)
        precio = c['price']['amount']
        envio = bool((c.get('shipping') or {}).get('user_allows_shipping'))
        km = aw.km_madrid(c)
        if not envio and (km is None or km > 30):
            continue                                   # solo en mano y lejos de Madrid: no compensa
        coste = precio * 1.05 + 5 if envio else precio
        margen = venta * 0.95 - coste
        if margen < max(15, round(coste * 0.3)):
            continue
        if any(o['titulo'] == c['title'] and o['precio'] == c['price']['amount'] for o in out):
            continue                                   # el mismo anuncio resubido
        avisos = ([] if completo else ['no dice completo: mira en las fotos caja y manual']) + \
                 ([] if esp else ['no dice PAL España: compruébalo en las fotos'])
        out.append({'titulo': c['title'], 'precio': precio, 'envio': envio, 'km': km, 'margen': round(margen), 'avisos': avisos,
                    'url': 'https://es.wallapop.com/item/' + c.get('web_slug', c['id']), 'user_id': c.get('user_id'),
                    'ciudad': (c.get('location') or {}).get('city') or ''})
    out.sort(key=lambda a: -a['margen'])
    sel = []
    for a in out:                                      # descarta perfiles con pinta de estafa
        vv = aw.vendedor(a['user_id']) if a.get('user_id') else None
        if vv and aw.sospechoso(vv, a['precio']):
            continue
        a['vendedor'] = ', '.join(vv['rojas']) if vv and vv['rojas'] else 'sin señales raras'
        sel.append(a)
        if len(sel) == 3:
            break
    return sel


def e(s):
    return html.escape(str(s or ''))


def correo(ventas, nombres, desde_txt):
    con = [v for v in ventas if v.get('baratos')]
    retro = [v for v in ventas if v.get('tipo')]
    partes = [f'<p style="font-family:Arial;font-size:15px">Ventas de tus revendedores desde {e(desde_txt)}: '
              f'<b>{len(ventas)}</b> en total, <b>{len(retro)}</b> cumplen tus criterios retro y en '
              f'<b>{len(con)}</b> hay el mismo producto más barato en Wallapop.</p>']
    if con:
        partes.append('<h3 style="font-family:Arial">Más barato que lo que vendió el revendedor</h3>')
        for v in con:
            partes.append('<div style="font-family:Arial;border:1px solid #ddd;border-radius:8px;padding:10px;margin:8px 0">'
                          f'<b>{e(v["titulo"])}</b> ({e(v["etiqueta"])})<br>'
                          f'Vendido por {e(nombres.get(v["uid"], "revendedor"))} a <b>{aw.eur(v["precio"])}</b> el {e(v["fecha"])} · '
                          f'<a href="{e(v["url"])}">ver venta</a><ul>')
            for a in v['baratos']:
                entrega = 'con envío' if a['envio'] else f'solo en mano a ~{a["km"]:.0f} km'
                partes.append(f'<li><a href="{e(a["url"])}">{e(a["titulo"])}</a> · <b>{aw.eur(a["precio"])}</b> · {entrega} · '
                              f'{e(a["ciudad"])} · margen ~{a["margen"]} € · vendedor: {e(a["vendedor"])}'
                              + ''.join(f'<br><span style="color:#b45309">⚠ {e(x)}</span>' for x in a['avisos']) + '</li>')
            partes.append('</ul></div>')
    partes.append('<h3 style="font-family:Arial">Todas las ventas registradas</h3>'
                  '<table style="font-family:Arial;font-size:13px;border-collapse:collapse" cellpadding="4">'
                  '<tr style="background:#eee"><th align="left">Fecha</th><th align="left">Revendedor</th>'
                  '<th align="left">Artículo</th><th align="right">Precio</th><th align="left">Criterios retro</th></tr>')
    for v in sorted(ventas, key=lambda v: v['ts'], reverse=True):
        nota = v['etiqueta'] if v.get('tipo') else v.get('motivo', '')
        partes.append(f'<tr><td>{e(v["fecha"])}</td><td>{e(nombres.get(v["uid"], ""))}</td>'
                      f'<td><a href="{e(v["url"])}">{e(v["titulo"])}</a></td>'
                      f'<td align="right">{aw.eur(v["precio"]) if v["precio"] else "?"}</td><td>{e(nota)}</td></tr>')
    partes.append('</table><p style="font-family:Arial;color:#999;font-size:12px">Bot de revendedores RetrodelNorte, cada 8 horas. '
                  'El precio es el último que tenía el anuncio al venderse. Antes de pagar, revisa fotos, versión y vendedor.</p>')
    return ''.join(partes)


def enviar(asunto, cuerpo):
    user, pwd = os.environ.get('GMAIL_USER'), os.environ.get('GMAIL_APP_PASSWORD')
    if not (user and pwd):
        print('[modo prueba, sin correo]', asunto)
        open(os.path.join(AQUI, 'revendedores_prueba.html'), 'w').write(cuerpo)
        return
    m = MIMEText(cuerpo, 'html', 'utf-8')
    dest = os.environ.get('ALERT_TO') or user
    m['Subject'], m['From'], m['To'], m['Date'] = asunto, user, dest, formatdate()
    m['Message-ID'] = make_msgid(domain='revendedores-wallapop')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as s:
        s.login(user, pwd)
        s.send_message(m)
    print('Correo enviado')
    if dest.lower() == user.lower():
        aw.etiquetar(user, pwd, m['Message-ID'])


def main():
    ids = ids_revendedores()
    if not ids:
        sys.exit('Falta la lista de revendedores (secreto REVENDEDORES o revendedores.txt)')
    est = cargar_estado()
    ahora = time.time()
    desde = est.get('ultima') or ahora - float(os.environ.get('VENTANA_HORAS', '72')) * 3600
    vistos = set(est.get('vistos', []))
    revendedores = set(ids)
    ventas, nombres = [], {}
    for uid in ids:
        nuevas = ventas_nuevas(uid, int(desde * 1000) - 3600 * 1000, vistos)   # 1 h de solape por si acaso
        if nuevas:
            u = aw.get_json(API + 'users/' + uid) or {}
            nombres[uid] = u.get('micro_name') or ''
        for x in nuevas:
            v = detalle(x)
            v['uid'], v['ts'] = uid, x['review']['date']
            vistos.add(v['id'])
            if v['precio'] and v['precio'] > 2:
                v['tipo'], v['plat'], v['etiqueta'], v['motivo'] = clasificar(v)
                if v['tipo']:
                    v['baratos'] = mas_baratos(v, v['tipo'], v['plat'], revendedores)
                    time.sleep(0.4)
            else:
                v['tipo'], v['motivo'] = None, 'sin precio (anuncio a 0-1 €)'
            ventas.append(v)
            time.sleep(0.3)
        time.sleep(0.4)
    print(f'revendedores: {len(ids)} · ventas nuevas: {len(ventas)} · retro: {sum(1 for v in ventas if v.get("tipo"))} · '
          f'con más baratos: {sum(1 for v in ventas if v.get("baratos"))}')
    desde_txt = time.strftime('%d/%m %H:%M', time.localtime(desde))
    if ventas:
        n = sum(1 for v in ventas if v.get('baratos'))
        asunto = f'Revendedores Wallapop: {len(ventas)} ventas' + (f', {n} con el mismo producto más barato' if n else '')
        enviar(asunto, correo(ventas, nombres, desde_txt))
    else:
        print('Sin ventas nuevas: no se envía correo')
    json.dump({'ultima': ahora, 'vistos': list(vistos)[-20000:]}, open(ESTADO, 'w'))


if __name__ == '__main__':
    main()
