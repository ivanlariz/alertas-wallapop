#!/usr/bin/env python3
"""Bot de alertas Wallapop (RetrodelNorte).

Cada vez que se ejecuta (GitHub Actions lo lanza cada 10 minutos):
  1. Lee la lista de vigilancia (hoja de Google publicada como CSV, o watchlist.csv local).
  2. Busca en Wallapop los anuncios más recientes de cada producto por debajo del precio máximo.
  3. Manda UN correo con lo nuevo: anuncios recién subidos y anuncios ya vistos que han bajado de precio.
  4. Guarda en vistos.json lo ya avisado para no repetir.

Variables de entorno:
  WATCHLIST_CSV_URL   enlace CSV de la hoja de vigilancia (por defecto, HOJA_CSV)
  GMAIL_USER          cuenta Gmail que envía el aviso
  GMAIL_APP_PASSWORD  contraseña de aplicación de esa cuenta (secreto de GitHub)
  ALERT_TO            destinatario (por defecto, el mismo GMAIL_USER)
  VENTANA_HORAS       solo avisa de anuncios publicados en las últimas N horas (por defecto 3)
  TELEGRAM_TOKEN      token del bot de Telegram (opcional): si está, los avisos también llegan a Telegram con foto
  CONSEJOS            JSON con fichas ya revisadas a mano (lo usan las pasadas horarias para enviar con el mismo formato)
Sin GMAIL_USER/GMAIL_APP_PASSWORD no envía nada: imprime los avisos (modo prueba).
"""
import csv, io, json, os, re, smtplib, sys, time, unicodedata, urllib.parse, urllib.request
from email.mime.text import MIMEText
from email.utils import formatdate

AQUI = os.path.dirname(os.path.abspath(__file__))
VISTOS = os.path.join(AQUI, 'vistos.json')
H = {'X-DeviceOS': '0', 'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'}
LAT, LON = 40.4168, -3.7038          # centro de España: Wallapop exige coordenadas; con envío da igual
# Hoja "Alertas Wallapop RetrodelNorte", pestaña Vigilancia, publicada como CSV
HOJA_CSV = ('https://docs.google.com/spreadsheets/d/e/2PACX-1vS7XKyB2snAKjoa70AH0m5twsE7cwms92L6kPMNKzXddXrK73F9EMhVpy37Fp39iLEUV8ti12jo5Avh'
            '/pub?gid=0&single=true&output=csv')
VENTANA = float(os.environ.get('VENTANA_HORAS', '3'))

# Palabras que descartan un anuncio siempre (además de las de la columna "Excluir")
EXCLUIR_SIEMPRE = ['repro', 'reproduccion', 'replica', 'copia', 'no original', 'no funciona', 'no enciende',
                   'averiad', 'para piezas', 'piezas', 'reparar', 'roto', 'rota', 'busco', 'compro',
                   'cambio por', 'solo caja', 'caja vacia', 'sin cartucho', 'r4', 'fuera de la app', 'baneada', 'baneado', 'ban',
                   'solo mando', 'solo el mando', 'sin consola', 'alquiler', 'alquilo',
                   'no carga', 'no lee', 'sin joystick', 'se apaga', 'defecto', 'defectuosa', 'averia', 'falla', 'icloud',
                   'bloqueada', 'bloqueado', 'pantalla rota', 'para reparar',
                   # averías y defectos (Iván no quiere nada con fallos)
                   'fallo', 'fallos', 'falla', 'fallan', 'fallando', 'rota', 'rotas', 'rotos', 'roto', 'rompio', 'rompio',
                   'averia', 'averias', 'averiada', 'averiado', 'estropeada', 'estropeado', 'defectuoso', 'defectos',
                   'no funciona', 'no funcionan', 'no va', 'no anda', 'no responde', 'no detecta', 'no reconoce',
                   'no lee', 'no carga', 'no enciende', 'no arranca', 'no da imagen', 'sin imagen', 'sin sonido',
                   'se apaga', 'se cuelga', 'se reinicia', 'parpadea', 'pixel muerto', 'pixeles muertos',
                   'mancha', 'manchas', 'raya en la pantalla', 'drift', 'joystick roto', 'boton roto', 'botones rotos',
                   'bisagra rota', 'tapa rota', 'carcasa rota', 'reparar', 'a reparar', 'reparacion', 'despiece',
                   'tal cual', 'tal y como esta', 'sin probar', 'no probada', 'no probado', 'sin garantia de funcionamiento']


def nn(s):
    s = unicodedata.normalize('NFKD', (s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' ' + ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split()) + ' '


def num(x):
    x = (x or '').strip().replace('€', '').replace(' ', '')
    if not x:
        return None
    if ',' in x and '.' in x:
        x = x.replace('.', '').replace(',', '.')
    else:
        x = x.replace(',', '.')
    try:
        return float(x)
    except ValueError:
        return None


def get_json(url):
    for intento in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=25))
        except Exception as e:
            err = e
            time.sleep(3 * (intento + 1))
    print('ERROR', url[:120], err, file=sys.stderr)
    return None


def leer_vigilancia():
    url = os.environ.get('WATCHLIST_CSV_URL', '').strip() or HOJA_CSV
    if url:
        txt = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}),
                                     timeout=30).read().decode('utf-8-sig')
    else:
        txt = open(os.path.join(AQUI, 'watchlist.csv'), encoding='utf-8-sig').read()
    filas = list(csv.reader(io.StringIO(txt)))
    # La cabecera es la fila que empieza por "Activo"; las columnas se localizan por su nombre
    ini = next(i for i, f in enumerate(filas) if f and nn(f[0]).strip() == 'activo')
    cab = [nn(c).strip() for c in filas[ini]]
    def col(fila, *prefijos):
        for j, c in enumerate(cab):
            if any(c.startswith(p) for p in prefijos) and j < len(fila):
                return fila[j].strip()
        return ''
    out = []
    for f in filas[ini + 1:]:
        busco = col(f, 'busco')
        if not busco or nn(col(f, 'activo')).strip() not in ('si', 's', 'x', '1', 'yes'):
            continue
        pmax = num(col(f, 'precio maximo'))
        if not pmax:
            continue
        pmin = num(col(f, 'precio minimo'))
        contiene = col(f, 'debe contener')
        grupos = [[nn(a).strip() for a in g.split('/') if a.strip()] for g in contiene.split(',') if g.strip()]
        if not grupos:                                   # por defecto: todas las palabras de "Busco"
            grupos = [[w] for w in nn(busco).split() if len(w) >= 2]
        out.append({'busco': busco, 'max': pmax, 'min': pmin if pmin is not None else round(pmax * 0.2, 2),
                    'grupos': grupos,
                    'excluir': [nn(w).strip() for w in col(f, 'excluir').split(',') if w.strip()],
                    'solo_envio': nn(col(f, 'solo con envio')).strip() in ('si', 's', 'x', '1', 'yes'),
                    'nota': col(f, 'notas'), 'venta': num(col(f, 'precio de venta')),
                    'margen_obj': num(col(f, 'margen limpio')),
                    'solo_consolas': nn(col(f, 'solo consolas')).strip() in ('si', 's', 'x', '1', 'yes')})
    return out


def buscar(v):
    q = {'keywords': v['busco'], 'latitude': LAT, 'longitude': LON, 'order_by': 'newest',
         'max_sale_price': int(v['max']) + 1, 'min_sale_price': int(v['min']), 'source': 'search_box'}
    items, d = [], get_json('https://api.wallapop.com/api/v3/search?' + urllib.parse.urlencode(q))
    for _ in range(2):                                   # 2 páginas = 80 anuncios más nuevos
        if not d:
            break
        items += d['data']['section']['payload']['items']
        nxt = d.get('meta', {}).get('next_page')
        if not nxt:
            break
        time.sleep(0.5)
        d = get_json('https://api.wallapop.com/api/v3/search?' + urllib.parse.urlencode({'next_page': nxt}))
    return items


INICIO_CONSOLA = re.compile(r' (nintendo|super nintendo|supernintendo|snes|sega|sony|playstation|ps|ps1|ps2|ps3|ps4|ps5|psx|psone|psp|ps vita|psvita|'
    r'game boy|gameboy|game gear|gamegear|game cube|gamecube|consola|console|consolle|new|neo geo|mega drive|megadrive|master system|'
    r'dreamcast|saturn|xbox|wii|nes|famicom|atari|commodore|gba|nds|ds|ds lite|dsi|3ds|2ds|n64|asus|rog|lenovo|legion|msi|claw|'
    r'steam|valve|ayn|anbernic|switch|pack|lote) ')


def parece_juego(it):
    """Juegos o accesorios sueltos subidos con el nombre de la consola (p. ej. «Super Mario World (Super Nintendo)»)."""
    t, d = nn(it['title']), nn((it.get('description') or '')[:80])
    if re.search(r' (consola|consolas|console|consolle) ', t):
        return False
    if re.match(r' (juego|videojuego|jogo|gioco|cartucho|cartuccia|cartridge) ', t):
        return True
    if re.match(r' (videojuego|juego|jogo|cartucho|accesorio|funda|mando) ', d):
        return True
    if not INICIO_CONSOLA.match(t) and re.search(r' para |[(]', it['title'].lower()):
        return True
    return False


CONSOLAS = 10088      # categoría «Consolas» de Wallapop
NO_CONSOLA_INICIO = re.compile(r' (mando|mandos|controller|cable|cables|cargador|manual|manuales|caja|scatola|lote|lotto|pack|juego|juegos|'
                               r'videojuego|videojuegos|\d+ juegos|\d+ videojuegos|\d+ giochi|bateria|memory|tarjeta|funda|carcasa|adaptador) ')
NO_CONSOLA = re.compile(r' (manual de instrucciones|caja vacia|scatola vuota|solo caja|ntsc|ntsc j|jap|japonesa|japones|giapponese|'
                        r'giapponesa|japan|usa|transfer pak|expansion pak|vmu|repuesto) ')


def es_consola(it):
    ids = {x.get('id') for x in (it.get('taxonomy') or [])}
    t = nn(it['title'])
    return CONSOLAS in ids and not NO_CONSOLA_INICIO.match(t) and not NO_CONSOLA.search(t)


ACCESORIO_INICIO = re.compile(r' (funda|carcasa|protector|protectores|cargador|cable|mando|mandos|dock|base de carga|soporte|estuche|bolsa) ')


def encaja(v, it):
    t, td = nn(it['title']), nn(it['title'] + ' ' + (it.get('description') or ''))
    precio = it['price']['amount']
    if not (v['min'] <= precio <= v['max']):
        return False
    # Cada grupo de "Debe contener" tiene que aparecer en el título (vale cualquiera de sus alternativas)
    for g in v['grupos']:
        if not any(f' {a} ' in t for a in g):
            return False
    for w in EXCLUIR_SIEMPRE + v['excluir']:
        if f' {nn(w).strip()} ' in td:
            return False
    if (it.get('reserved') or {}).get('flag'):
        return False
    if parece_juego(it) or ACCESORIO_INICIO.match(t):
        return False
    if v.get('solo_consolas') and not es_consola(it):
        return False
    if v['solo_envio'] and not (it.get('shipping') or {}).get('user_allows_shipping'):
        return False
    return True


def eur(x, dec=2):
    return f'{x:,.{dec}f} €'.replace(',', 'X').replace('.', ',').replace('X', '.')


def vendedor(uid):
    """Datos de confianza del vendedor: antigüedad, valoraciones, ventas, denuncias, foto de perfil y verificaciones."""
    u = get_json('https://api.wallapop.com/api/v3/users/' + uid)
    st = get_json('https://api.wallapop.com/api/v3/users/' + uid + '/stats') or {}
    ex = get_json('https://api.wallapop.com/api/v3/users/' + uid + '/extra-info') or {}
    val = ex.get('validations') or {}
    reg = (u or {}).get('register_date')
    cnt = {c.get('type'): c.get('value') for c in st.get('counters', [])}
    v = {'borrado': u is None,
         'dias': int((time.time() * 1000 - reg) / 86400000) if reg else None,
         'reviews': cnt.get('reviews') or 0, 'ventas': cnt.get('sells') or 0,
         'denuncias': cnt.get('reports_received') or 0,
         'foto': bool((u or {}).get('image')) or bool(val.get('picture')),
         'dni': bool(val.get('kyc')), 'movil': bool(val.get('mobile'))}
    rojas = []
    if v['borrado']:
        rojas.append('perfil borrado')
    if v['dias'] is not None and v['dias'] < 30:
        rojas.append(f'perfil creado hace {v["dias"]} días')
    if not v['reviews']:
        rojas.append('sin valoraciones')
    if not v['foto']:
        rojas.append('sin foto de perfil')
    if not v['dni']:
        rojas.append('identidad sin verificar')
    if not v['movil']:
        rojas.append('móvil sin verificar')
    if v['denuncias'] >= 5:
        rojas.append(f'{v["denuncias"]} denuncias')
    v['rojas'] = rojas
    return v


def sospechoso(v, precio):
    """True si el perfil tiene pinta de estafa y no merece aviso."""
    if v['borrado']:
        return True
    nuevo = v['dias'] is not None and v['dias'] < 30
    if nuevo and not v['reviews']:
        return True                                    # cuenta recién creada sin valoraciones
    if not v['reviews'] and precio >= 250:
        return True                                    # artículos caros: solo vendedores con alguna valoración
    graves = sum([nuevo, not v['reviews'], not v['foto'], not v['dni'], v['denuncias'] >= 5])
    return graves >= 3


RITMO = json.load(open(os.path.join(AQUI, 'ritmo.json'))) if os.path.exists(os.path.join(AQUI, 'ritmo.json')) else {}


def ritmo_venta(it):
    """Busca en ritmo.json (historial de ventas) el modelo del anuncio y devuelve su resumen."""
    t = nn(it['title'])
    full = nn(it['title'] + ' ' + (it.get('description') or ''))
    caja = 'con caja' if re.search(r' (en su caja|con caja|caja original|en caja|completa|cib) ', full) and not re.search(r' sin caja ', full) else 'suelta'
    mejor = None
    for k, r in RITMO.items():
        m = nn(r['modelo']).strip()
        if f' {m} ' in t and r['estado'] == caja and (not mejor or len(m) > len(nn(mejor['modelo']))):
            mejor = r
    if not mejor or not mejor.get('vendidas'):
        return ''
    return f"{mejor['modelo']} ({caja}): {mejor['resumen']}"


def interes(vis, fav):
    """Regla de RetrodelNorte: a buen precio, los favoritos suelen ser ~10 % de las visitas."""
    if vis < 25:
        return 'aún pocas visitas para juzgar'
    p = 100 * fav / vis
    if p >= 10:
        return f'{p:.0f} % favoritos/visitas: precio atractivo'
    if p >= 6:
        return f'{p:.0f} % favoritos/visitas: interés normal'
    return f'{p:.0f} % favoritos/visitas: poco interés, el precio no engancha' + (' (muchas visitas)' if vis >= 100 else '')


def senales(iid):
    c = get_json('https://api.wallapop.com/api/v3/items/' + iid + '/counters') or {}
    return c.get('views', 0), c.get('favorites', 0), c.get('conversations', 0)


def antiguedad(dias):
    if dias is None:
        return 'cuenta de antigüedad desconocida'
    return f'cuenta de {dias} días' if dias < 60 else (f'cuenta de {dias // 30} meses' if dias < 730 else f'cuenta de {dias // 365} años')


def ficha_auto(a):
    """Convierte un aviso automático en una ficha con consejo (vendedor, señales, números y veredicto)."""
    it, v = a['it'], a['v']
    precio = it['price']['amount']
    envio = bool((it.get('shipping') or {}).get('user_allows_shipping'))
    hace = int((time.time() * 1000 - it['created_at']) / 60000)
    hace = f'hace {hace} min' if hace < 120 else f'hace {hace // 60} h'
    vd = a.get('vend') or {'dias': None, 'reviews': 0, 'ventas': 0, 'denuncias': 0, 'rojas': []}
    d, r, ven, den = vd['dias'], vd['reviews'], vd['ventas'], vd['denuncias']
    vis, fav, conv = senales(it['id'])
    avisos = []
    slug = set(nn(re.sub(r'-\d+$', '', it['web_slug'])).split())
    tit = {w for w in nn(it['title']).split() if len(w) > 2}
    if tit and not slug & tit:
        avisos.append('anuncio reutilizado (el enlace es de otro producto): posible estafa')
    if re.search(r' sin mando', nn(it['title'] + ' ' + (it.get('description') or ''))):
        avisos.append('no incluye mando')
    if not envio:
        avisos.append('solo entrega en mano')
    if vd.get('rojas'):
        avisos.append('perfil: ' + ', '.join(vd['rojas']) + ' → paga solo dentro de Wallapop')
    coste = precio * 1.05 + 5 if envio else precio
    venta, margen = v.get('venta'), None
    numeros = f'Coste ~{eur(coste, 0)}' + (' (con envío y protección)' if envio else ' (en mano)')
    if venta:
        margen = venta - coste
        if 'no incluye mando' in avisos and venta >= 250:
            margen -= 50
            numeros += ' + ~50 € de mando'
        numeros += f' · venta ~{eur(venta, 0)} · <b>margen ~{eur(margen, 0)}</b>'
    # Veredicto automático
    objetivo = v.get('margen_obj') or 25
    fiable = (r or 0) >= 3 and den < 5 and len(vd.get('rojas', [])) <= 1
    if margen is not None and margen >= objetivo and fiable:
        veredicto = 'COMPRAR' + (' rápido' if conv >= 5 else '') + ('' if envio else ' (recogida en mano)')
    elif margen is not None and (r or 0) >= 1 and den < 5 and margen >= objetivo * 0.6:
        oferta = int((precio - max(0, objetivo - margen)) // 5 * 5)
        if oferta >= precio:
            veredicto = 'COMPRAR, pagando dentro de Wallapop (vendedor con poco historial)'
        else:
            veredicto = f'OFRECER {eur(oferta, 0)}' + ('' if envio else ' (recogida en mano)')
    else:
        veredicto = 'VERIFICAR antes: pide una foto real con su nombre y paga dentro de Wallapop'
    ritmo = interes(vis, fav) + ('; muchas conversaciones, se irá rápido' if conv >= 5 else '')
    motivo = (f'BAJADA de {eur(a["antes"], 0)} a {eur(precio, 0)}' if a.get('antes') else f'Nuevo · publicado {hace}')
    return {
        'titulo': it['title'], 'url': 'https://es.wallapop.com/item/' + it['web_slug'],
        'img': ((it.get('images') or [{}])[0].get('urls') or {}).get('medium', ''),
        'precio': precio, 'envio': envio, 'ciudad': (it.get('location') or {}).get('city', ''),
        'cabecera': f'{motivo} · alerta «{v["busco"]}» ≤ {eur(v["max"], 0)}',
        'lineas': [
            ('Anuncio', (it.get('description') or '').replace('\n', ' ')[:220]),
            ('Vendedor', f'{antiguedad(d)}, {r or 0} valoraciones, {ven or 0} ventas' + (f', {den} denuncias' if den else ', sin denuncias')
             + (', con foto' if vd.get('foto') else ', sin foto') + (', DNI verificado' if vd.get('dni') else '')),
            ('Números', numeros + (f' · {v["nota"]}' if v.get('nota') else '')),
            ('Señales', f'{vis} visitas, {fav} favoritos, {conv} conversaciones → {ritmo}'),
            ('Ritmo', ritmo_venta(it)),
        ],
        'avisos': avisos, 'veredicto': veredicto,
    }


def ficha_html(f):
    lineas = ''.join(f'<b>{k}:</b> {t}<br>' for k, t in f['lineas'] if t)
    avisos = ('<b style="color:#d35400">⚠️ ' + ' · '.join(f['avisos']) + '</b><br>') if f.get('avisos') else ''
    color = '#27ae60' if f['veredicto'].upper().startswith('COMPRAR') else ('#2471a3' if f['veredicto'].upper().startswith('OFRECER') else '#d35400')
    return (f'<tr><td style="padding:10px;vertical-align:top;width:170px"><a href="{f["url"]}"><img src="{f["img"]}" width="160" style="border-radius:6px"></a></td>'
            f'<td style="padding:10px;vertical-align:top;font-family:Arial;font-size:14px;line-height:1.45">'
            f'<a href="{f["url"]}" style="font-size:16px"><b>{f["titulo"]}</b></a><br>'
            f'<b style="font-size:19px">{eur(f["precio"])}</b> · {"con envío" if f["envio"] else "solo en mano"} · {f["ciudad"]}<br>'
            f'<span style="color:#555">{f["cabecera"]}</span><br>{lineas}{avisos}'
            f'<span style="display:inline-block;margin-top:4px;padding:3px 8px;border-radius:4px;background:{color};color:#fff"><b>{f["veredicto"]}</b></span>'
            f'</td></tr>')


def ficha_telegram(f):
    import html as _h
    lineas = '\n'.join(f'<b>{k}:</b> {_h.escape(re.sub("<[^>]+>", "", t))}' for k, t in f['lineas'] if t and k != 'Anuncio')
    avisos = ('\n⚠️ ' + _h.escape(' · '.join(f['avisos']))) if f.get('avisos') else ''
    cabeza = (f'<b>{_h.escape(f["titulo"])}</b>\n💶 <b>{eur(f["precio"])}</b> · {"con envío" if f["envio"] else "solo en mano"} · {_h.escape(f["ciudad"])}\n'
              f'👉 <b>{_h.escape(f["veredicto"])}</b> · <a href="{f["url"]}">Abrir en Wallapop</a>\n')
    cuerpo = f'{_h.escape(f["cabecera"])}\n{lineas}{avisos}'
    hueco = 1020 - len(cabeza)
    if len(cuerpo) > hueco:                      # recorta sin dejar etiquetas abiertas
        cuerpo = re.sub(r'<[^>]*$', '', cuerpo[:hueco - 1]) + '…'
        cuerpo = re.sub(r'<b>([^<]*)$', r'\1', cuerpo)
    return cabeza + cuerpo


def telegram_chat(token):
    """Chat de Telegram al que mandar: TELEGRAM_CHAT_ID, el guardado en .telegram_chat o el último que escribió al bot."""
    chat = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    fichero = os.path.join(AQUI, '.telegram_chat')
    if not chat and os.path.exists(fichero):
        chat = open(fichero).read().strip()
    if not chat:
        d = get_json(f'https://api.telegram.org/bot{token}/getUpdates') or {}
        for u in reversed(d.get('result', [])):
            m = u.get('message') or u.get('edited_message') or {}
            if m.get('chat', {}).get('id'):
                chat = str(m['chat']['id'])
                break
        if chat:
            open(fichero, 'w').write(chat)
    return chat


def enviar_telegram(fichas, cabecera):
    token = os.environ.get('TELEGRAM_TOKEN', '').strip()
    if not token:
        return
    chat = telegram_chat(token)
    if not chat:
        print('Telegram: no hay chat; escribe algo al bot desde Telegram para activarlo')
        return
    def post(metodo, datos):
        req = urllib.request.Request(f'https://api.telegram.org/bot{token}/{metodo}',
                                     data=urllib.parse.urlencode(datos).encode(), method='POST')
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:
            print('Telegram error', metodo, e)
    post('sendMessage', {'chat_id': chat, 'text': cabecera, 'parse_mode': 'HTML', 'disable_web_page_preview': 'true'})
    for f in fichas:
        r = None
        if f.get('img'):
            r = post('sendPhoto', {'chat_id': chat, 'photo': f['img'], 'caption': ficha_telegram(f), 'parse_mode': 'HTML'})
        if not r or not r.get('ok'):
            post('sendMessage', {'chat_id': chat, 'text': ficha_telegram(f), 'parse_mode': 'HTML'})
        time.sleep(0.4)
    print('Telegram enviado:', len(fichas), 'avisos')


def enviar(fichas, asunto, intro, prueba=False):
    asunto = ('[PRUEBA] ' if prueba else '') + asunto
    html = (f'<p style="font-family:Arial;font-size:14px">{intro}</p><table>' + ''.join(ficha_html(f) for f in fichas) +
            '</table><p style="font-family:Arial;color:#999;font-size:12px">Bot de alertas RetrodelNorte. '
            'Edita la hoja de vigilancia para añadir o quitar productos. Antes de pagar, revisa fotos y descripción.</p>')
    enviar_telegram(fichas, f'<b>{asunto}</b>')
    user, pwd = os.environ.get('GMAIL_USER'), os.environ.get('GMAIL_APP_PASSWORD')
    if not (user and pwd):
        print('[modo prueba, sin correo]', asunto)
        for f in fichas:
            print('  ', f['precio'], f['titulo'], f['url'], '→', f['veredicto'])
        return
    m = MIMEText(html, 'html', 'utf-8')
    m['Subject'], m['From'], m['To'], m['Date'] = asunto, user, (os.environ.get('ALERT_TO') or user), formatdate()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as s:
        s.login(user, pwd)
        s.send_message(m)
    print('Correo enviado:', asunto)


def consejos():
    """Revisión hecha a mano (pasadas horarias): llega como JSON en CONSEJOS y se envía con el mismo formato."""
    datos = json.loads(os.environ['CONSEJOS'])
    fichas = []
    for c in datos.get('fichas', []):
        fichas.append({'titulo': c['titulo'], 'url': c['url'], 'img': c.get('img', ''), 'precio': float(c['precio']),
                       'envio': bool(c.get('envio')), 'ciudad': c.get('ciudad', ''), 'cabecera': c.get('cabecera', ''),
                       'lineas': [tuple(x) for x in c.get('lineas', [])], 'avisos': c.get('avisos', []),
                       'veredicto': c.get('veredicto', '')})
    if fichas:
        enviar(fichas, datos.get('asunto', 'Chollos Wallapop RetrodelNorte'), datos.get('intro', ''))


def prueba():
    """Correo de prueba: hasta 6 anuncios que cumplen la lista ahora mismo. No toca vistos.json."""
    avisos = []
    for v in leer_vigilancia():
        avisos += [{'it': it, 'v': v} for it in buscar(v) if encaja(v, it)][:2]
    print(f'PRUEBA: {len(avisos)} anuncios encontrados')
    for a in avisos:
        a['vend'] = vendedor(a['it']['user_id'])
    avisos = [a for a in avisos if not sospechoso(a['vend'], a['it']['price']['amount'])]
    if avisos:
        fichas = [ficha_auto(a) for a in avisos[:6]]
        enviar(fichas, f'🔔 Wallapop: {len(fichas)} aviso(s)', 'Anuncios que cumplen ahora mismo tu lista de vigilancia.', prueba=True)


def main():
    if os.environ.get('CONSEJOS', '').strip():
        return consejos()
    if os.environ.get('PRUEBA') == '1':
        return prueba()
    vistos = json.load(open(VISTOS)) if os.path.exists(VISTOS) else {}
    primera = not vistos
    ahora = time.time() * 1000
    avisos = []
    lista = leer_vigilancia()
    for v in lista:
        for it in buscar(v):
            if not encaja(v, it):
                continue
            iid, precio = it['id'], it['price']['amount']
            antes = vistos.get(iid)
            reciente = ahora - it['created_at'] < VENTANA * 3600 * 1000
            if antes is None and reciente and not primera:
                avisos.append({'it': it, 'v': v})
            elif antes is not None and precio < antes - 0.5 and not primera:
                avisos.append({'it': it, 'v': v, 'antes': antes})
            vistos[iid] = precio
        time.sleep(0.5)
    print(f'{len(lista)} búsquedas activas, {len(avisos)} avisos' + (' (primera ejecución: solo se memoriza)' if primera else ''))
    if avisos:
        uniq = list({a['it']['id']: a for a in avisos}.values())
        buenos = []
        for a in uniq:
            a['vend'] = vendedor(a['it']['user_id'])
            if sospechoso(a['vend'], a['it']['price']['amount']):
                print('Descartado por perfil sospechoso:', a['it']['title'], a['vend']['rojas'])
                continue
            buenos.append(a)
        if buenos:
            fichas = [ficha_auto(a) for a in buenos]
            nombres = ', '.join(sorted({a['v']['busco'] for a in buenos}))[:110]
            enviar(fichas, f'🔔 Wallapop: {len(fichas)} aviso(s) – {nombres}',
                   'Anuncios recién subidos (o rebajados) que cumplen tu lista de vigilancia, con mi valoración.')
    if len(vistos) > 20000:                       # recorta la memoria si crece demasiado
        vistos = dict(list(vistos.items())[-15000:])
    json.dump(vistos, open(VISTOS, 'w'), separators=(',', ':'))


if __name__ == '__main__':
    main()
