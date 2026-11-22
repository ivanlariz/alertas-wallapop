# RetrodelNorte – contexto para Claude Code

Iván lleva RetrodelNorte, una tienda de videojuegos retro (Shopify: retrodelnorte.com). Contesta siempre en español.

## Qué hay en este repositorio
- `alerta_wallapop.py`: el bot de GitHub Actions (`.github/workflows/alertas.yml`). Corre cada 10 minutos y avisa por email y Telegram.
- `revendedores.py` + `.github/workflows/revendedores.yml` (21-22/11): cada 8 h apunta las ventas de los revendedores (valoraciones de sus perfiles) en un historial de 90 días y busca en Wallapop chollos de CUALQUIER producto retro de ese historial (más baratos que la mediana a la que lo vendieron), con las fotos revisadas por Claude; lo manda por email sin repetir anuncios. La lista de revendedores va en el secreto `REVENDEDORES` (ids de usuario de Wallapop), nunca en el repo. Vinted no: su protección anti-bots bloquea el acceso automático y no se salta.
- `retro.py`: el modo retro, con `MODO_RETRO=True`. Define las plataformas, la valoración de juegos COMPLETOS PAL España y las consolas portátiles con caja.
- `pasadas/`: los scripts de la revisión horaria a mano.
  - `retro_pasada.py [horas]`: los anuncios retro nuevos. Usa 1.3 en las pasadas normales y 8 en la de las 7:07. La salida va a retro.json, con candidatos y lotes.
  - `retro_stock.py`: anuncios que ya llevan días publicados (stock). Se ejecuta a las 7:07 y a las 14:07; los ids revisados se añaden a `vistos_stock_retro.txt`.
  - `track.py activos.json > hist.json`: historial de ventas probables y cambios de precio. Necesita el fichero de estado `activos.json`, que no está en el repo. Si falta, empieza de cero.
  - `ritmo.py > ritmo_filas.json`: ritmo de venta por modelo.
  - `enviar_consejos.py fichas.json`: manda fichas revisadas a mano a través del bot. Usa `gh workflow dispatch`, con el input público `consejos`.
- `ritmo.json`: el ritmo de venta, que se actualiza a diario.

## Criterios de compra (decididos por Iván)
- **Juegos:** de Mega Drive, SNES, Saturn, Dreamcast, GB/GBC, GBA, PS1, PS2, PSP y N64. Siempre COMPLETOS (caja, manual y juego) y PAL ESPAÑA.
  - PAL Europa multiidioma con español solo si no existe edición española de ese título.
  - Nunca UK, FR, IT, DE, NTSC ni japonés.
  - Platinum, Classics y Essentials valen menos.
- **Consolas:** solo portátiles (GB, Pocket, Color, Advance, SP, PSP), completas con caja e instrucciones. Nada de sobremesa suelta; en lotes con juegos sí.
- **En pausa:** PS5, Switch 2, portátiles de PC, PS Vita y DS/3DS.
- **Lotes (15/11):** le interesa cualquier lote de juegos completos PAL España, también los de juegos baratos de PS2 y los que traen consola de sobremesa. Se valora todo: cada juego por separado, de forma conservadora (un juego común de PS2 completo se vende a unos 8-15 €), más la consola. Merece la pena con un margen de 30 € o más, o del 40 % o más.
- **Prioridad por demanda:** Pokémon de GBA y Game Boy (mira la placa y la etiqueta: es lo más falsificado), Golden Sun, Zelda, Mega Man X, Super Metroid, Chrono Trigger, Terranigma, Budokai Tenkaichi 3, Sly, Jak, CTR, MediEvil, GTA Stories, Peace Walker, Mario 64 y Banjo-Kazooie.
- **Entrega:** en mano interesa hasta unos 25-30 km del norte de Madrid. Más lejos, solo con envío.

## Reglas fijas
- No comprar nada ni escribir a vendedores. Avisar solo a Iván, por email y por su Telegram.
- Las fichas del bot salen en los registros públicos de GitHub: pon "Madrid", nunca el barrio, y no pongas nombres de vendedores.
- Los secretos (Gmail, Telegram, ANTHROPIC_API_KEY) van solo en los secretos del repositorio, nunca en el chat ni en el código.
- No saltarse protecciones anti-bot. No usar fotos de otras tiendas ni de vendedores en la web.
- Shopify: no se puede editar el tema publicado; trabaja sobre una copia sin publicar.

## Recursos
- **Hoja de historial** "Historial ventas Wallapop RetrodelNorte": id `1mqh1iXELqwvGOv1etw6h9_AVh8SQu29DwVoFxAhfdpA`. Pestañas: Ventas probables (A:N), Cambios de precio (A:G), Activos por modelo y Ritmo de venta.
- **Shopify:** blog "Noticias" (gid://shopify/Blog/126259331415). Posts publicados: top 20 de terror de PS2 y top 20 de shoot 'em up de Saturn, con carátulas, versiones y precios. La página "Compramos tus juegos" usa el handle compramos_tu_juego.
- **DataForSEO:** location 2724, idioma "es".

## Pendiente
- Verificar retrodelnorte.com en Google Search Console (cuenta dosmediabilbao): falta la etiqueta meta o hacerlo con Chrome.
- "Compramos tus juegos": confirmar la frase de la FAQ "si no te convence, te lo devolvemos".
- Fotos propias del interior de los juegos para los posts y las fichas.
- Más posts por género: coches PS2/PSP, guerra PS2, Pokémon GBA…
- Evercade: la colección existe pero está vacía.
- Configurar TELEGRAM_TOKEN.
