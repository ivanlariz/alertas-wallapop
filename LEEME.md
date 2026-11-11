# Bot de alertas Wallapop – RetrodelNorte

Cada 10 minutos mira en Wallapop los productos de tu hoja **Alertas Wallapop RetrodelNorte**. Si alguien sube uno por debajo de tu precio máximo, o baja el precio de uno que ya estaba, te manda un correo. El correo lleva foto, precio, margen estimado, enlace y avisos de posible estafa: anuncio reutilizado, sin mando o solo en mano.

Funciona gratis en GitHub Actions, con tu ordenador apagado.

## Puesta en marcha (unos 15 minutos, una sola vez)

### 1. Contraseña de aplicación de Gmail (para que el bot pueda enviar correos)
1. Entra en https://myaccount.google.com/security con la cuenta que enviará los avisos (puede ser ivanlariz@gmail.com, que se los manda a sí misma).
2. Activa la **Verificación en 2 pasos** si no la tienes.
3. Entra en https://myaccount.google.com/apppasswords, crea una con el nombre «Bot Wallapop» y copia el código de 16 letras.
   No lo pegues en ningún chat: va solo en GitHub (paso 4).

### 2. Publicar la hoja de vigilancia como CSV
1. Abre la hoja **Alertas Wallapop RetrodelNorte** y ve a *Archivo → Compartir → Publicar en la web*.
2. Elige la pestaña **Vigilancia** y el formato **Valores separados por comas (.csv)**, y pulsa *Publicar*.
3. Copia el enlace que aparece.

### 3. Crear el repositorio en GitHub
1. Crea una cuenta en https://github.com si no tienes.
2. Pulsa *New repository*, ponle de nombre `alertas-wallapop` y márcalo como **Public**.
   Así los minutos son gratis e ilimitados. En uno privado, cada 10 minutos se pasa del límite gratuito. En el código no hay nada privado.
3. En el repositorio, pulsa *Add file → Upload files* y arrastra **todo el contenido** de esta carpeta: `alerta_wallapop.py`, `vistos.json`, `LEEME.md` y la carpeta `.github`.
   - Si la carpeta `.github` no se sube, créala a mano: *Add file → Create new file*, nombre `.github/workflows/alertas.yml`, y pega el contenido de ese archivo.

### 4. Guardar las claves en GitHub
En el repositorio, ve a *Settings → Secrets and variables → Actions → New repository secret* y crea estas cuatro:

| Nombre | Valor |
|---|---|
| `GMAIL_USER` | la cuenta Gmail del paso 1 |
| `GMAIL_APP_PASSWORD` | el código de 16 letras del paso 1 |
| `WATCHLIST_CSV_URL` | el enlace CSV del paso 2 |
| `ALERT_TO` | ivanlariz@gmail.com |

### 5. Arrancar
1. Ve a la pestaña **Actions**, pulsa *Alertas Wallapop* y luego **Run workflow**.
2. La primera ejecución solo memoriza los anuncios que ya existen y no manda correo. Su registro debe decir algo como «5 búsquedas activas, 0 avisos (primera ejecución…)».
3. Desde ahí funciona solo, cada 10 minutos. GitHub a veces lo retrasa unos minutos en horas punta.

## Uso diario
- **Añadir o quitar productos:** edita la hoja desde el móvil. Una fila por producto, y SI/NO en «Activo» para activarlo o pausarlo. El cambio vale desde la siguiente vuelta.
- **Precio máximo de compra:** se calcula solo a partir del precio de venta y el margen limpio que quieras (descuenta unos 5 € de envío y protección y un 5 % de comisión). También puedes escribirlo a mano.
- **Debe contener:** grupos separados por comas que tienen que aparecer todos en el título. Dentro de un grupo, las alternativas van con `/`. Ejemplo: `ps5/playstation 5, slim`.
- **Excluir:** palabras que descartan el anuncio. Además, siempre se descartan repros, rotos, piezas, consolas baneadas, «busco/compro» y accesorios sueltos.
- **Pararlo:** en *Actions → Alertas Wallapop → ⋯ → Disable workflow*.
