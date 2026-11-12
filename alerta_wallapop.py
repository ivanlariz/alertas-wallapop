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
                   'cambio por', 'solo caja', 'caja vacia', 'sin cartucho', 'r4', 'funda', 'carcasa',
                   'protector', 'cargador', 'fuera de la app', 'baneada', 'baneado', 'ban',
                   'solo mando', 'solo el mando', 'sin consola', 'alquiler', 'alquilo',
                   'no carga', 'no lee', 'sin joystick', 'se apaga', 'defecto', 'defectuosa', 'averia', 'falla', 'icloud',
                   'bloqueada', 'bloqueado', 'pantalla rota', 'para reparar']


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
    if parece_juego(it):
        return False
    if v.get('solo_consolas') and not es_consola(it):
        return False
    if v['solo_envio'] and not (it.get('shipping') or {}).get('user_allows_shipping'):
        return False
    return True


def eur(x, dec=2):
    return f'{x:,.{dec}f} €'.replace(',', 'X').replace('.', ',').replace('X', '.')


def vendedor(uid):
    """Antigüedad de la cuenta (días) y nº de valoraciones del vendedor. None si no se puede saber."""
    u = get_json('https://api.wallapop.com/api/v3/users/' + uid) or {}
    st = get_json('https://api.wallapop.com/api/v3/users/' + uid + '/stats') or {}
    reg = u.get('register_date')
    dias = int((time.time() * 1000 - reg) / 86400000) if reg else None
    cnt = {c.get('type'): c.get('value') for c in st.get('counters', [])}
    return dias, cnt.get('reviews'), cnt.get('sells')


def tarjeta(a):
    it, v = a['it'], a['v']
    img = ((it.get('images') or [{}])[0].get('urls') or {}).get('medium', '')
    url = 'https://es.wallapop.com/item/' + it['web_slug']
    envio = 'con envío' if (it.get('shipping') or {}).get('user_allows_shipping') else 'solo en mano'
    hace = int((time.time() * 1000 - it['created_at']) / 60000)
    hace = f'hace {hace} min' if hace < 120 else f'hace {hace // 60} h'
    motivo = (f'<b style="color:#c0392b">BAJADA de {eur(a["antes"], 0)} a {eur(it["price"]["amount"], 0)}</b>'
              if a.get('antes') else f'Nuevo · publicado {hace}')
    desc = (it.get('description') or '').replace('\n', ' ')[:220]
    alertas = []
    slug = set(nn(re.sub(r'-\d+$', '', it['web_slug'])).split())
    tit = {w for w in nn(it['title']).split() if len(w) > 2}
    if tit and not slug & tit:
        alertas.append('anuncio reutilizado (el enlace es de otro producto): posible estafa')
    if re.search(r' sin mando', nn(it['title'] + ' ' + (it.get('description') or ''))):
        alertas.append('sin mando')
    if not (it.get('shipping') or {}).get('user_allows_shipping'):
        alertas.append('solo en mano')
    if a.get('vend'):
        d, r, ven = a['vend']
        if r == 0:
            alertas.append(f'vendedor sin valoraciones (cuenta de {d} días): paga solo dentro de Wallapop')
    margen = ''
    if v.get('venta'):
        m = v['venta'] - it['price']['amount'] * 1.05 - 5
        margen = f' <span style="color:#27ae60">(margen limpio ~{eur(m, 0)} vendiendo a {eur(v["venta"], 0)})</span>'
    aviso = ('<br><b style="color:#d35400">⚠️ ' + ' · '.join(alertas) + '</b>') if alertas else ''
    return (f'<tr><td style="padding:8px;vertical-align:top"><a href="{url}"><img src="{img}" width="120"></a></td>'
            f'<td style="padding:8px;vertical-align:top;font-family:Arial;font-size:14px">'
            f'<a href="{url}" style="font-size:16px"><b>{it["title"]}</b></a><br>'
            f'<b style="font-size:18px">{eur(it["price"]["amount"])}</b>{margen} · {envio} · {(it.get("location") or {}).get("city", "")}<br>'
            f'{motivo} · alerta «{v["busco"]}» ≤ {eur(v["max"], 0)}' + (f' · {v["nota"]}' if v.get('nota') else '') + '<br>'
            f'<span style="color:#666">{desc}</span>{aviso}</td></tr>')


def enviar(avisos, prueba=False):
    asunto = ('[PRUEBA] ' if prueba else '') + f'🔔 Wallapop: {len(avisos)} aviso(s) – ' + ', '.join(sorted({a["v"]["busco"] for a in avisos}))[:120]
    html = ('<p style="font-family:Arial">Anuncios que cumplen tu lista de vigilancia. '
            'Revisa fotos y descripción antes de comprar.</p><table>' + ''.join(tarjeta(a) for a in avisos) +
            '</table><p style="font-family:Arial;color:#999;font-size:12px">Bot de alertas RetrodelNorte. '
            'Edita la hoja de vigilancia para añadir o quitar productos.</p>')
    user, pwd = os.environ.get('GMAIL_USER'), os.environ.get('GMAIL_APP_PASSWORD')
    if not (user and pwd):
        print('[modo prueba, sin correo]', asunto)
        for a in avisos:
            print('  ', a['it']['price']['amount'], a['it']['title'], 'https://es.wallapop.com/item/' + a['it']['web_slug'])
        return
    m = MIMEText(html, 'html', 'utf-8')
    m['Subject'], m['From'], m['To'], m['Date'] = asunto, user, (os.environ.get('ALERT_TO') or user), formatdate()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30) as s:
        s.login(user, pwd)
        s.send_message(m)
    print('Correo enviado:', asunto)


def prueba():
    """Correo de prueba: hasta 6 anuncios que cumplen la lista ahora mismo. No toca vistos.json."""
    avisos = []
    for v in leer_vigilancia():
        avisos += [{'it': it, 'v': v} for it in buscar(v) if encaja(v, it)][:2]
    print(f'PRUEBA: {len(avisos)} anuncios encontrados')
    for a in avisos:
        a['vend'] = vendedor(a['it']['user_id'])
    avisos = [a for a in avisos if not (a['vend'][0] is not None and a['vend'][0] < 15 and not a['vend'][1])]
    if avisos:
        enviar(avisos[:6], prueba=True)


def main():
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
            d, r, _ = a['vend']
            if d is not None and d < 15 and not r:      # cuenta recién creada y sin valoraciones: estafa típica
                print('Descartado por cuenta nueva:', a['it']['title'], d, 'días')
                continue
            if not r and a['it']['price']['amount'] >= 250:   # artículos caros: solo vendedores con alguna valoración
                print('Descartado por vendedor sin valoraciones:', a['it']['title'], a['it']['price']['amount'])
                continue
            buenos.append(a)
        if buenos:
            enviar(buenos)
    if len(vistos) > 20000:                       # recorta la memoria si crece demasiado
        vistos = dict(list(vistos.items())[-15000:])
    json.dump(vistos, open(VISTOS, 'w'), separators=(',', ':'))


if __name__ == '__main__':
    main()
