#!/usr/bin/env python3
"""Bot de ventas de revendedores (RetrodelNorte).

Cada 8 horas (GitHub Actions, workflow revendedores.yml):
  1. Mira las valoraciones de los revendedores que sigue Iván: cada valoración de venta es un artículo vendido,
     con su título, el último precio que tenía y la fecha.
  2. Apunta las ventas nuevas y guarda un historial de 90 días de todo lo retro que han vendido (la primera vez lo
     rellena hacia atrás).
  3. Para CADA producto retro del historial (juego de las plataformas de Iván o portátil con caja), busca en Wallapop
     anuncios del mismo producto más baratos que la mediana a la que lo han vendido los revendedores, comprueba con
     Claude en las fotos que estén completos y no repite anuncios ya enviados (salvo que bajen de precio).
  4. Manda UN correo a Iván con los chollos y las ventas nuevas.

Variables de entorno:
  REVENDEDORES        ids de usuario de Wallapop de los revendedores, separados por comas o espacios (secreto de GitHub).
                      Si falta, se leen de revendedores.txt (no se sube al repositorio).
  GMAIL_USER, GMAIL_APP_PASSWORD, ALERT_TO   como en alerta_wallapop.py
  DIAS_HISTORIAL      días de ventas que se guardan y se usan como referencia (por defecto 90)
Sin GMAIL_USER/GMAIL_APP_PASSWORD no envía nada: imprime el resumen (modo prueba).
Los registros de GitHub son públicos: aquí solo se imprimen recuentos, nunca nombres de vendedores.
"""
import html, json, os, re, smtplib, statistics, sys, time, urllib.parse
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


def ventas_nuevas(uid, desde_ms, vistos, paginas=3):
    """Ventas (valoraciones de tipo 'sell') del revendedor posteriores a desde_ms y no vistas."""
    out = []
    for pagina in range(paginas):
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


GENERICAS = R.PALABRAS_VACIAS | set('''the of and le la saturn sega ss gb gbc version versio pal espana spain spanish edition
    edicion clasico classic retro coleccion coleccionista impecable excelente nuevo nueva completo completa caja manual
    instrucciones mapa poster registro tarjeta inserto inlay jap europa europeo europea hedgehog jogo videojogo erbe
    konami capcom nintendo ubisoft electronic arts ea namco tecmo sunsoft acclaim activision midway thq'''.split())
MARCAS = set('erbe konami capcom nintendo sega sony ubisoft electronic arts ea namco tecmo sunsoft acclaim activision midway thq'.split())


def palabras(titulo):
    """Palabras que identifican el juego (sin plataforma, estado, versión ni relleno)."""
    t = re.sub(r'\([^)]*\)|\[[^\]]*\]', ' ', titulo)
    return [w for w in aw.nn(t).split() if w not in GENERICAS and len(w) >= 2 and not w.isdigit() and w not in ROMANOS]


def clave_producto(tipo, plat, titulo):
    """Identificador del producto para agrupar ventas: plataforma + palabras del título + número de entrega."""
    t = aw.nn(titulo)
    if tipo == R.CONSOLAS:
        return f'c|{plat}|{(R.modelo_consola(t, plat) or ("?",))[0]}'
    claves = palabras(titulo)
    if not [w for w in claves if w not in MARCAS]:
        return None
    return f'j|{plat}|{" ".join(sorted(set(claves)))}|{" ".join(sorted(numeros(t)))}'


def mirar_fotos(c, est):
    """Análisis de fotos con Claude, guardado por anuncio y precio para no pagarlo dos veces."""
    cache = est.setdefault('fotos', {})
    k = f"{c['id']}|{c['price']['amount']}"
    if k in cache:
        return cache[k]
    f = aw.analizar_fotos(c)
    if f is not None:
        cache[k] = f
    return f


def mas_baratos(v, tipo, plat, revendedores, est):
    """Anuncios activos del mismo producto, completos y PAL España, que dejan margen frente al precio de venta."""
    venta = v['precio']
    enviados = est.setdefault('enviados', {})
    if tipo == R.CONSOLAS:
        modelo = R.modelo_consola(aw.nn(v['titulo']), plat)
        if not modelo:
            return []
        claves, consulta = [], modelo[2].replace(' caja', '')
    else:
        modelo = None
        claves = list(dict.fromkeys(palabras(v['titulo'])))
        if not [w for w in claves if w not in MARCAS] or venta < 25:
            return []
        consulta = ' '.join(claves[:6]) + ' ' + next(qs[0] for c, _, _, qs in R.PLATAFORMAS if c == plat)
    q = {'keywords': consulta, 'latitude': aw.LAT, 'longitude': aw.LON, 'source': 'search_box',
         'category_ids': '24200', 'subcategory_ids': tipo, 'order_by': 'price_low_to_high',
         'min_sale_price': max(3, int(venta * 0.15)), 'max_sale_price': int(venta)}
    d = aw.get_json(API + 'search?' + urllib.parse.urlencode(q))
    out = []
    for c in (d or {}).get('data', {}).get('section', {}).get('payload', {}).get('items', []):
        if c.get('user_id') in revendedores or (c.get('reserved') or {}).get('flag'):
            continue
        if c['id'] in enviados and c['price']['amount'] >= enviados[c['id']]:
            continue                                   # ya enviado y no ha bajado de precio
        raw = c['title'] + ' ' + (c.get('description') or '')
        t, full = aw.nn(c['title']), aw.nn(raw)
        if claves and not all(f' {k} ' in t for k in claves):
            continue
        if claves and [w for w in palabras(c['title']) if w not in claves and len(w) >= 4]:
            continue                                   # otro juego: Top Gear Rally ≠ Top Gear, Paper Mario ≠ Super Mario
        if re.search(r' (ps3|ps4|ps5|xbox|switch|wii|nes|gamecube|3ds|2ds|nds|ds|master system|game gear|genesis) ', t):
            continue
        if numeros(t) != numeros(aw.nn(v['titulo'])):
            continue                                   # Mega Games 2 ≠ Mega Games I, Sonic Adventure ≠ Sonic Adventure 2
        if re.search(r' (trial|demo|promo|promocional|not for resale) ', full):
            continue
        if R.plataforma(t)[0] != plat:
            continue                                   # la plataforma tiene que estar en el título
        if modelo and ((R.modelo_consola(t, plat) or (None,))[0] != modelo[0] or not es_consola_portatil(t, plat)):
            continue
        if tipo == R.JUEGOS and es_consola_portatil(t, plat):
            continue
        if re.search(R.EXCLUIR_TITULO, t) or re.search(R.EXCLUIR_TEXTO, full) or re.search(R.INCOMPLETO, full):
            continue
        if re.search(R.ESP_NO, re.sub(R.QUITAR_ESP, ' ', full)) or '🇯🇵' in raw or '🇺🇸' in raw:
            continue
        # No hace falta que diga «completo»: lo comprueba Claude en las fotos y la descripción (abajo)
        if len(c.get('images') or []) < 2:
            continue
        completo = bool(re.search(R.COMPLETO if tipo == R.JUEGOS else R.CAJA_CONSOLA, full))
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
        if any(o['titulo'] == c['title'] and o['precio'] == precio for o in out):
            continue                                   # el mismo anuncio resubido
        out.append({'id': c['id'], 'titulo': c['title'], 'precio': precio, 'envio': envio, 'km': km, 'margen': round(margen),
                    'completo': completo, 'esp': esp, 'item': c,
                    'url': 'https://es.wallapop.com/item/' + c.get('web_slug', c['id']), 'user_id': c.get('user_id'),
                    'ciudad': (c.get('location') or {}).get('city') or ''})
    out.sort(key=lambda a: -a['margen'])
    sel = []
    for a in out[:6]:
        c = a.pop('item')
        vv = aw.vendedor(a['user_id']) if a.get('user_id') else None
        if vv and aw.sospechoso(vv, a['precio']):
            continue                                   # perfil con pinta de estafa
        f = mirar_fotos(c, est)
        if f is None and not a['completo']:
            continue                                   # sin poder mirar las fotos, no se manda
        a['avisos'] = []
        if f:
            if f['descartar'] or f['completo'] == 'no' or f['version'] in ('pal_otro', 'ntsc') or f['fotos_de_internet']:
                continue
            if f['completo'] != 'si' and not a['completo']:
                continue
            if f['completo'] != 'si':
                a['avisos'].append('la descripción dice completo, pero en las fotos no se ve todo')
            if not a['esp'] and f['version'] not in ('pal_esp', 'pal_eur_multi'):
                a['avisos'].append('no se ve si es PAL España: pide foto de la contraportada')
            a['fotos'] = f['resumen']
        vv = vv or {'rojas': []}
        a['vendedor'] = ', '.join(vv['rojas']) if vv['rojas'] else 'sin señales raras'
        sel.append(a)
        if len(sel) == 3:
            break
    return sel


def e(s):
    return html.escape(str(s or ''))


def correo(chollos, nuevas, n_hist, n_prod):
    partes = [f'<p style="font-family:Arial;font-size:15px">Historial de ventas de tus revendedores: <b>{n_hist}</b> ventas retro '
              f'en los últimos {DIAS} días ({n_prod} productos distintos). En esta pasada: <b>{len(chollos)}</b> productos con '
              f'anuncios más baratos que lo que los venden ellos y <b>{len(nuevas)}</b> ventas nuevas.</p>']
    if chollos:
        partes.append('<h3 style="font-family:Arial">Chollos: más baratos que lo que venden los revendedores</h3>')
        for p in chollos:
            ult = p['ultima']
            partes.append('<div style="font-family:Arial;border:1px solid #ddd;border-radius:8px;padding:10px;margin:8px 0">'
                          f'<b>{e(ult["titulo"])}</b> ({e(ult["etiqueta"])})<br>'
                          f'Los revendedores lo han vendido <b>{p["n"]} {"vez" if p["n"] == 1 else "veces"}</b> en {DIAS} días, '
                          f'a <b>{aw.eur(p["ref"])}</b> de mediana (de {aw.eur(min(p["precios"]))} a {aw.eur(max(p["precios"]))}). '
                          f'Última: {aw.eur(ult["precio"])} el {e(ult["fecha"])} por {e(ult.get("nombre") or "un revendedor")} · '
                          f'<a href="{e(ult["url"])}">ver venta</a><ul>')
            for a in p['baratos']:
                entrega = 'con envío' if a['envio'] else f'solo en mano a ~{a["km"]:.0f} km'
                partes.append(f'<li><a href="{e(a["url"])}">{e(a["titulo"])}</a> · <b>{aw.eur(a["precio"])}</b> · {entrega} · '
                              f'{e(a["ciudad"])} · margen ~{a["margen"]} € · vendedor: {e(a["vendedor"])}'
                              + (f'<br><span style="color:#555">📷 {e(a["fotos"])}</span>' if a.get('fotos') else '')
                              + ''.join(f'<br><span style="color:#b45309">⚠ {e(x)}</span>' for x in a['avisos']) + '</li>')
            partes.append('</ul></div>')
    if nuevas:
        partes.append('<h3 style="font-family:Arial">Ventas nuevas de los revendedores</h3>'
                      '<table style="font-family:Arial;font-size:13px;border-collapse:collapse" cellpadding="4">'
                      '<tr style="background:#eee"><th align="left">Fecha</th><th align="left">Revendedor</th>'
                      '<th align="left">Artículo</th><th align="right">Precio</th><th align="left">Criterios retro</th></tr>')
        for v in sorted(nuevas, key=lambda v: v['ts'], reverse=True):
            nota = v['etiqueta'] if v.get('tipo') else v.get('motivo', '')
            partes.append(f'<tr><td>{e(v["fecha"])}</td><td>{e(v.get("nombre"))}</td>'
                          f'<td><a href="{e(v["url"])}">{e(v["titulo"])}</a></td>'
                          f'<td align="right">{aw.eur(v["precio"]) if v["precio"] else "?"}</td><td>{e(nota)}</td></tr>')
        partes.append('</table>')
    partes.append('<p style="font-family:Arial;color:#999;font-size:12px">Bot de revendedores RetrodelNorte, cada 8 horas. '
                  'El precio de venta es el último que tenía el anuncio al venderse. Las fotos las revisa Claude; '
                  'antes de pagar, compruébalas tú también, junto con la versión y el vendedor.</p>')
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


DIAS = int(os.environ.get('DIAS_HISTORIAL', '90'))


def main():
    ids = ids_revendedores()
    if not ids:
        sys.exit('Falta la lista de revendedores (secreto REVENDEDORES o revendedores.txt)')
    est = cargar_estado()
    ahora = time.time()
    primera = 'historial' not in est                   # primera vez: rellena el historial hacia atrás
    desde = ahora - DIAS * 86400 if primera else est['ultima']
    vistos = set(est.get('vistos', []))
    historial = est.get('historial', [])
    revendedores = set(ids)
    nuevas = []
    for uid in ids:
        lista = ventas_nuevas(uid, int(desde * 1000) - 3600 * 1000, vistos, paginas=25 if primera else 3)
        nombre = ((aw.get_json(API + 'users/' + uid) or {}).get('micro_name') or '') if lista else ''
        for x in lista:
            vistos.add(x['item']['id'])
            if primera and not R.plataforma(aw.nn(x['item'].get('title') or ''))[0]:
                continue                               # al rellenar el historial, solo se piden los detalles de lo retro
            v = detalle(x)
            v['uid'], v['ts'], v['nombre'] = uid, x['review']['date'], nombre
            if v['precio'] and v['precio'] > 2:
                v['tipo'], v['plat'], v['etiqueta'], v['motivo'] = clasificar(v)
            else:
                v['tipo'], v['motivo'] = None, 'sin precio (anuncio a 0-1 €)'
            if v['tipo']:
                v['clave'] = clave_producto(v['tipo'], v['plat'], v['titulo'])
                if v['clave']:
                    historial.append({k: v[k] for k in ('id', 'titulo', 'precio', 'ts', 'fecha', 'nombre', 'tipo', 'plat',
                                                         'etiqueta', 'clave', 'url')})
            if not primera:
                nuevas.append(v)
            time.sleep(0.3)
        time.sleep(0.4)
    historial = [h for h in historial if h['ts'] >= (ahora - DIAS * 86400) * 1000]
    est['historial'] = historial
    # Productos del historial: referencia = mediana de lo que han vendido los revendedores
    grupos = {}
    for h in historial:
        k = clave_producto(h['tipo'], h['plat'], h['titulo'])     # se recalcula: así los ajustes valen para lo ya guardado
        if k:
            grupos.setdefault(k, []).append(h)
    chollos = []
    for clave, hs in grupos.items():
        hs.sort(key=lambda h: h['ts'])
        precios = [h['precio'] for h in hs]
        ref = statistics.median(precios)
        ult = hs[-1]
        rep = {'titulo': ult['titulo'], 'precio': ref}
        baratos = mas_baratos(rep, ult['tipo'], ult['plat'], revendedores, est)
        if baratos:
            for a in baratos:
                est['enviados'][a['id']] = a['precio']
            chollos.append({'ultima': ult, 'n': len(hs), 'ref': ref, 'precios': precios, 'baratos': baratos})
        time.sleep(0.4)
    chollos.sort(key=lambda p: -max(a['margen'] for a in p['baratos']))
    print(f'revendedores: {len(ids)} · ventas nuevas: {len(nuevas)} · historial retro: {len(historial)} '
          f'({len(grupos)} productos) · productos con chollos: {len(chollos)}')
    if chollos or nuevas:
        asunto = 'Revendedores Wallapop: ' + (f'{len(chollos)} chollos' if chollos else 'sin chollos') + \
                 (f', {len(nuevas)} ventas nuevas' if nuevas else '')
        enviar(asunto, correo(chollos, nuevas, len(historial), len(grupos)))
    else:
        print('Nada nuevo: no se envía correo')
    est['ultima'], est['vistos'] = ahora, list(vistos)[-30000:]
    est['fotos'] = dict(list(est.get('fotos', {}).items())[-3000:])
    json.dump(est, open(ESTADO, 'w'))


if __name__ == '__main__':
    main()
