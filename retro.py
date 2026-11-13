"""Vigilancia retro de RetrodelNorte: juegos de Mega Drive, Super Nintendo, Saturn, Game Boy, Game Boy Advance, PS1 y PS2
y consolas PORTÁTILES (Game Boy, Color, Pocket, Advance, Advance SP), solo COMPLETOS (caja e instrucciones) y
PAL ESPAÑA (o PAL Europa multiidioma con español cuando lo indica el anuncio).

Para cada anuncio nuevo que pasa los filtros busca en Wallapop anuncios comparables (mismo juego o consola, misma
plataforma, completos y no extranjeros) y usa su precio como referencia de venta. Si el margen limpio compensa,
devuelve un aviso con la referencia para que alerta_wallapop.py lo valore y lo mande.
"""
import re, statistics, time, urllib.parse

# Subcategorías de Wallapop
JUEGOS, CONSOLAS = '10093', '10088'

# Plataformas (el orden importa: GBA antes que GB y PS2 antes que PS1)
PLATAFORMAS = [
    ('gba', 'Game Boy Advance', r' (game ?boy advance|gameboy advance|gba|game boy advanced) ', ['game boy advance', 'gba']),
    ('gb', 'Game Boy', r' (game ?boy|gameboy|game boy color|gameboy color|gbc|game boy pocket) ', ['game boy', 'gameboy color']),
    ('snes', 'Super Nintendo', r' (super nintendo|snes|super nes) ', ['super nintendo', 'snes']),
    ('md', 'Mega Drive', r' (mega ?drive|megadrive|mega drive ii|mega drive 2) ', ['mega drive', 'megadrive']),
    ('saturn', 'Saturn', r' (sega saturn|saturn) ', ['sega saturn', 'saturn']),
    ('ps2', 'PS2', r' (ps2|playstation 2|play station 2|play 2) ', ['ps2', 'playstation 2']),
    ('ps1', 'PS1', r' (ps1|psx|psone|ps one|playstation 1|play station 1|playstation one|play 1) ', ['ps1', 'psx playstation']),
]
# Consolas: modelo -> (plataforma, búsqueda, regex del modelo)
# Consolas: SOLO PORTÁTILES (Iván no quiere cajas grandes de sobremesa). modelo -> (plataforma, búsqueda, regex)
CONSOLAS_MODELOS = [
    ('Game Boy Advance SP', 'gba', 'game boy advance sp caja', r' (advance sp|gba sp) '),
    ('Game Boy Advance', 'gba', 'consola game boy advance caja', r' (game ?boy advance|gameboy advance|gba) '),
    ('Game Boy Color', 'gb', 'consola game boy color caja', r' (game ?boy colou?r|gameboy colou?r|gbc) '),
    ('Game Boy Pocket', 'gb', 'game boy pocket caja', r' (game ?boy pocket|gameboy pocket) '),
    ('Game Boy', 'gb', 'consola game boy clasica caja', r' (game ?boy|gameboy|dmg) '),
]

COMPLETO = r' (completo|completa|completos|cib|caja y manual|caja manual|caja e instrucciones|caja instrucciones|con manual|con instrucciones|manual incluido|precintado|precintada|sellado|nuevo a estrenar) '
INCOMPLETO = (r' (sin manual|sin instrucciones|sin caja|solo cartucho|solo el cartucho|solo disco|solo el disco|solo caja|solo la caja|'
              r'caja vacia|falta el manual|falta manual|no incluye manual|manual no incluido|incompleto|incompleta|loose|suelto|suelta|'
              r'sin folleto|caja repro|caja no original|manual fotocopia|fotocopia) ')
CAJA_CONSOLA = (r' (completa|completo|cib|caja y manual|caja manual|caja e instrucciones|caja y instrucciones|caja con instrucciones|'
                r'con manual|con instrucciones|manual incluido|instrucciones incluidas|precintada|nueva a estrenar) ')
ESP_SI = (r' (pal esp|pal espana|pal es|pal spain|version espanola|version espana|version esp|edicion espanola|en espanol|'
          r'en castellano|castellano|idioma espanol|textos en espanol|espanol|espanola|esp) ')
ESP_NO = (r' (pal uk|ukv|uk|fah|fra|frances|francesa|ita|italiano|italiana|aleman|alemana|ger|noe|ntsc|usa|jap|japon|japones|'
          r'japonesa|famicom|super famicom|scn|holandes|portugues|ingles|inglesa|nordic|aus|'
          r'genesis|import|importacion|gioco|giochi|scatola|jeu|spiel) ')
EUR = r' (pal eur|eur|euro|europea|europeo|pal europa|europa) '
MULTI = (r' (multi ?idioma|multiidioma|multilenguaje|multilingue|multi ?language|varios idiomas|incluye espanol|espanol incluido|'
         r'en espanol|en castellano|castellano|textos en espanol|idioma espanol|espanol) ')
QUITAR_ESP = r' (toda espana|en espana|a espana|de espana|para espana|peninsula|envios? a espana) '
# Se miran en el título: lotes, accesorios y otras cosas que no son un juego o una consola sueltos
EXCLUIR_TITULO = (r' (repro|reproduccion|replica|copia|lote|lotes|pack|coleccion|juegos|cartuchos|consolas|busco|compro|cambio|'
                  r'solo caja|caja vacia|solo manual|manual|guia|poster|funda|carcasa|protector|figura|amiibo|mando|mandos|'
                  r'cable|cables|adaptador|cargador|memory card|tarjeta de memoria) ')
# Se miran en título y descripción: falsificaciones y fallos
EXCLUIR_TEXTO = (r' (repro|reproduccion|replica|no original|no es original|flash|everdrive|r4|no funciona|no carga|no lee|'
                 r'averiad|para piezas|roto|rota|reparar|defectuos|falla|fallo|fallos|chip|chipeada|chipeado|modificada|'
                 r'modificado|pirata) ')
# Si el título nombra otra plataforma, no es retro aunque la descripción hable de Game Boy o PS2
OTRAS = (r' (switch|3ds|2ds|nds|ds|wii|wii u|gamecube|game cube|n64|nintendo 64|nes|master system|dreamcast|game gear|'
         r'ps3|ps4|ps5|playstation 3|playstation 4|playstation 5|psp|vita|xbox|pc|neo geo) ')
PALABRAS_VACIAS = set('''completo completa completos cib pal esp espana espanol espanola version edicion juego videojuego para consola
    nintendo sega sony playstation ps1 ps2 psx psone super snes nes mega drive megadrive game boy gameboy advance gba gbc color colour
    con caja manual instrucciones original originales de del la el los las y en a un una muy buen bueno buena estado perfecto
    perfecta precintado nuevo usado funciona cartucho disco uk es eur castellano envio incluido incluye vendo venta ntsc'''.split())


def _pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    i = int(k)
    return xs[i] + (xs[min(i + 1, len(xs) - 1)] - xs[i]) * (k - i)


def plataforma(texto):
    for clave, nombre, rx, _ in PLATAFORMAS:
        if re.search(rx, texto):
            return clave, nombre
    return None, None


def es_espanol(raw, texto):
    t = re.sub(QUITAR_ESP, ' ', texto)
    if re.search(ESP_NO, t):
        return False
    if re.search(EUR, t):                 # PAL Europa: vale si es multiidioma con español
        return bool(re.search(MULTI, t))
    return '🇪🇸' in raw or '🇪🇦' in raw or bool(re.search(ESP_SI, t))


def claves_titulo(titulo, nn):
    t = re.sub(r'\([^)]*\)|\[[^\]]*\]', ' ', titulo)
    out = []
    for w in nn(t).split():
        if w in PALABRAS_VACIAS or len(w) < 2 or (w.isdigit() and len(w) > 2):
            continue
        out.append(w)
    return out[:5]


def modelo_consola(t, plat):
    """Primer modelo de CONSOLAS_MODELOS (de más a menos específico) que encaja con el título."""
    return next((m for m in CONSOLAS_MODELOS if m[1] == plat and re.search(m[3], t)), None)


def referencia(it, tipo, plat, claves, consulta, get_json, nn, lat, lon, modelo=None):
    """Mediana conservadora (percentil 40) de anuncios comparables completos y no extranjeros."""
    q = {'keywords': consulta, 'latitude': lat, 'longitude': lon, 'source': 'search_box',
         'category_ids': '24200', 'subcategory_ids': tipo}
    d = get_json('https://api.wallapop.com/api/v3/search?' + urllib.parse.urlencode(q))
    if not d:
        return None
    precios, ejemplos = [], []
    for c in d['data']['section']['payload']['items']:
        if c['id'] == it['id']:
            continue
        t = nn(c['title'])
        full = nn(c['title'] + ' ' + (c.get('description') or ''))
        if not all(f' {k} ' in t for k in claves):
            continue
        if plataforma(t)[0] != plat and plataforma(full)[0] != plat:
            continue
        if modelo and (modelo_consola(t, plat) or (None,))[0] != modelo:
            continue
        if re.search(EXCLUIR_TITULO, t) or re.search(EXCLUIR_TEXTO, full) or re.search(INCOMPLETO, full):
            continue
        if tipo == CONSOLAS and re.match(r' (juego|videojuego) ', t):
            continue
        if tipo == JUEGOS and not re.search(COMPLETO, full):
            continue
        if tipo == CONSOLAS and not re.search(CAJA_CONSOLA, full):
            continue
        tq = re.sub(QUITAR_ESP, ' ', full)
        if re.search(ESP_NO, tq) or (re.search(EUR, tq) and not re.search(MULTI, tq)):
            continue
        precios.append(c['price']['amount'])
        ejemplos.append((c['price']['amount'], c['title'][:60]))
    if len(precios) < 3:
        return None
    med = statistics.median(precios)
    ejemplos = [e for e in ejemplos if med / 3 <= e[0] <= med * 3]       # fuera precios absurdos
    precios = [e[0] for e in ejemplos]
    if len(precios) < 3:
        return None
    return {'venta': round(_pct(precios, 0.4), 2), 'n': len(precios), 'mediana': round(statistics.median(precios), 2),
            'min': min(precios), 'ejemplos': sorted(ejemplos)[:3]}


def buscar_nuevos(get_json, lat, lon):
    """Anuncios más recientes de juegos y consolas de las plataformas retro."""
    vistos, out = set(), []
    tareas = [(JUEGOS, q) for _, _, _, qs in PLATAFORMAS for q in qs] + [(CONSOLAS, m[2]) for m in CONSOLAS_MODELOS]
    for tipo, q in tareas:
        p = {'keywords': q, 'latitude': lat, 'longitude': lon, 'order_by': 'newest', 'source': 'search_box',
             'category_ids': '24200', 'subcategory_ids': tipo, 'min_sale_price': 8, 'max_sale_price': 800}
        d = get_json('https://api.wallapop.com/api/v3/search?' + urllib.parse.urlencode(p))
        for it in (d or {}).get('data', {}).get('section', {}).get('payload', {}).get('items', []):
            if it['id'] not in vistos:
                vistos.add(it['id'])
                out.append((tipo, it))
        time.sleep(0.4)
    return out


def valorar(tipo, it, get_json, nn, lat, lon, margen_min=15, estricto_esp=True):
    """Devuelve (motivo_descartado, None) o (None, datos del aviso)."""
    raw = it['title'] + ' ' + (it.get('description') or '')
    t, full = nn(it['title']), nn(raw)
    precio = it['price']['amount']
    if (it.get('reserved') or {}).get('flag'):
        return 'reservado', None
    if re.search(EXCLUIR_TITULO, t) or re.search(EXCLUIR_TEXTO, full):
        return 'excluido (repro, lote, accesorio, fallos…)', None
    plat, nombre = plataforma(t)
    if not plat and not re.search(OTRAS, t) and not re.search(OTRAS, full):
        plat, nombre = plataforma(full)
    if not plat:
        return 'sin plataforma retro', None
    if re.search(INCOMPLETO, full):
        return 'incompleto', None
    if tipo == JUEGOS and not re.search(COMPLETO, full):
        return 'no dice completo', None
    if tipo == CONSOLAS and not re.search(CAJA_CONSOLA, full):
        return 'consola sin caja', None
    esp = es_espanol(raw, full)
    if not esp and (estricto_esp or re.search(ESP_NO, re.sub(QUITAR_ESP, ' ', full)) or re.search(EUR, re.sub(QUITAR_ESP, ' ', full))):
        return 'no consta PAL España', None
    if tipo == CONSOLAS:
        modelo = modelo_consola(t, plat)
        if not modelo:
            return 'modelo de consola no reconocido', None
        etiqueta = f'consola {modelo[0]} con caja'
        ref = referencia(it, tipo, plat, [], modelo[2], get_json, nn, lat, lon, modelo=modelo[0])
    else:
        claves = claves_titulo(it['title'], nn)
        if not claves:
            return 'título sin nombre de juego', None
        consulta = ' '.join(claves) + ' ' + next(qs[0] for c, _, _, qs in PLATAFORMAS if c == plat)
        etiqueta = f'juego {nombre} completo'
        ref = referencia(it, tipo, plat, claves, consulta, get_json, nn, lat, lon)
    if not ref:
        return 'sin referencia suficiente', None
    envio = bool((it.get('shipping') or {}).get('user_allows_shipping'))
    coste = precio * 1.05 + 5 if envio else precio
    venta = ref['venta'] * 0.95
    margen = venta - coste
    objetivo = margen_min if margen_min < 0 else max(margen_min, round(coste * 0.3))
    if margen < objetivo:
        return f'margen {margen:.0f} € < {objetivo} €', None
    return None, {'esp_confirmado': esp, 'margen': round(margen, 2), 'plataforma': nombre, 'etiqueta': etiqueta, 'ref': ref, 'venta': round(venta, 2),
                  'objetivo': objetivo, 'max': round(((venta - objetivo) - 5) / 1.05, 2)}
