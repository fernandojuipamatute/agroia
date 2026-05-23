# Guía de despliegue de AgroIA en Render.com

Esta guía te lleva de "tengo el código en mi laptop" a "mi app está en internet"
en aproximadamente 30-45 minutos.

## Lo que vas a lograr

Al final tendrás:
- Una URL pública para tu API: https://agroia-api.onrender.com
- Una URL pública para tu app: https://agroia-app.onrender.com
- La app instalable en cualquier celular (Android, iPhone)
- Todo gratis (sin tarjeta de crédito)

---

# PASO 1: Crear cuenta en GitHub (5 minutos)

Si ya tienes cuenta, salta al Paso 2.

1. Ve a https://github.com/
2. Click en "Sign up" arriba a la derecha
3. Pon tu email (puede ser personal o universitario)
4. Crea una contraseña fuerte
5. Elige un nombre de usuario (ejemplo: jhonny-huipama)
6. Verifica tu email

---

# PASO 2: Crear el repositorio (5 minutos)

1. Inicia sesión en GitHub
2. Click en el "+" arriba a la derecha → "New repository"
3. En "Repository name" escribe: agroia
4. Marca "Public" (debe ser público para Render gratis)
5. Marca "Add a README file"
6. Click "Create repository"

---

# PASO 3: Subir el código a GitHub

Hay dos formas. Elige la que te resulte más fácil.

## OPCIÓN A: Subir desde la web (más fácil)

1. En tu repositorio nuevo, click en "Add file" → "Upload files"
2. Arrastra TODO el contenido de la carpeta `agroia_pwa/` (server.py,
   public/, requirements.txt, render.yaml, README.md, .gitignore)
3. Espera a que se carguen los archivos
4. En "Commit changes" escribe: "Versión inicial"
5. Click "Commit changes"

## OPCIÓN B: Usar Git (si lo tienes instalado)

```bash
cd ruta/donde/tengas/agroia_pwa
git init
git add .
git commit -m "Versión inicial"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/agroia.git
git push -u origin main
```

---

# PASO 4: Crear cuenta en Render.com (5 minutos)

1. Ve a https://render.com/
2. Click "Get Started" o "Sign up"
3. Elige "Sign up with GitHub" (más fácil)
4. Autoriza a Render para acceder a tus repositorios
5. Confirma tu email

---

# PASO 5: Desplegar el servidor (API Backend)

Ahora viene la magia. Vamos a hacer que tu servidor Python esté en internet.

1. En Render.com, click "New +" arriba a la derecha
2. Elige "Web Service"
3. Verás tus repositorios de GitHub. Busca "agroia" y click en "Connect"

4. Te aparecen muchas opciones. Llena así:
   - **Name**: agroia-api (importante: este nombre será parte de tu URL)
   - **Region**: Oregon (USA) - el más rápido para Perú
   - **Branch**: main
   - **Root Directory**: (déjalo vacío)
   - **Runtime**: Python 3
   - **Build Command**: pip install -r requirements.txt
   - **Start Command**: gunicorn server:app
   - **Instance Type**: Free

5. Antes de hacer click en "Create Web Service", baja a "Advanced":
   - Click en "Add Environment Variable"
   - **Key**: DATADOG_API_KEY
   - **Value**: pega tu API key real de Datadog (la que termina en 6648)
   - Click "Add another"
   - **Key**: DATADOG_SITE
   - **Value**: us5.datadoghq.com

6. Ahora SÍ, click en "Create Web Service" abajo.

7. Render comienza a desplegar. Tarda 3-5 minutos la primera vez.
   - Verás logs en pantalla, espera hasta que diga "Live"
   - Si hay error, mándame foto y te ayudo

8. Cuando esté "Live", tu URL será algo como:
   https://agroia-api.onrender.com
   ANOTA esta URL, la vas a necesitar.

---

# PASO 6: Actualizar la URL en index.html

Importante: tu app HTML está apuntando a una URL que es ejemplo. Hay que
cambiarla a tu URL real de Render.

1. En tu repositorio de GitHub, ve a `public/index.html`
2. Click en el ícono de lápiz para editar
3. Busca esta línea (usa Ctrl+F):
   ```
   : 'https://agroia-api.onrender.com'
   ```
4. Reemplaza con tu URL real, por ejemplo:
   ```
   : 'https://agroia-api-XXXX.onrender.com'
   ```
   (Render a veces agrega caracteres al nombre, copia tu URL exacta)
5. Baja al final, en "Commit changes" pon: "Actualizar URL del API"
6. Click "Commit changes"

---

# PASO 7: Desplegar el frontend (la app HTML)

1. En Render.com, click "New +" → "Static Site"
2. Elige el mismo repositorio "agroia"
3. Llena así:
   - **Name**: agroia-app (este será tu URL público)
   - **Branch**: main
   - **Root Directory**: (déjalo vacío)
   - **Build Command**: (déjalo vacío)
   - **Publish directory**: public

4. Click "Create Static Site"

5. Espera 1-2 minutos. Cuando esté "Live", tu URL será:
   https://agroia-app.onrender.com

---

# PASO 8: ¡Probar la app!

1. Abre la URL de tu app en tu computadora primero (https://agroia-app.onrender.com)
2. Verifica que:
   - Se ve el dashboard correctamente
   - Aparece "Datadog conectado" en verde (después de unos segundos)
   - Puedes registrar una pesada

## Si dice "Modo offline"

Es porque el servidor está "dormido" (Render Free se duerme tras 15 min sin uso).
Espera 30-60 segundos y refresca. Debería conectar.

## Si hay otro error

Toma foto y mándamela. Errores comunes y rápidos de resolver:
- API Key mal configurada en variables de entorno
- URL del API mal copiada en index.html
- CORS bloqueando peticiones (le agrego un fix)

---

# PASO 9: Instalar como app en celular

## En Android (Chrome o Edge)

1. Abre la URL en Chrome del celular
2. Esperan unos segundos
3. Aparecerá automáticamente un banner verde: "Instalar AgroIA"
4. Click "Instalar"
5. Listo: aparece el ícono en tu escritorio

Si no aparece el banner:
1. Toca los 3 puntos arriba a la derecha
2. Click "Instalar app" o "Agregar a pantalla de inicio"

## En iPhone (Safari)

iOS requiere instalación manual (es así para todas las PWAs):

1. Abre la URL en Safari (no Chrome)
2. Aparecerá un banner verde con instrucciones
3. Toca el botón "Compartir" (cuadrado con flecha hacia arriba) abajo
4. Desplázate y toca "Agregar a Pantalla de Inicio"
5. Click "Agregar" arriba a la derecha
6. El ícono aparece en tu pantalla de inicio

---

# PASO 10: Mostrar al profesor

Una vez instalada, dile al profesor:

1. Que abra https://agroia-app.onrender.com en su celular
2. Que siga las instrucciones del banner para instalar
3. Que abra la app desde su escritorio (no desde el navegador)

Tendrá la app de AgroIA como cualquier otra app instalada.

---

# Limitaciones que debes saber

Te lo digo para que no te sorprendas:

1. **El servidor "se duerme" tras 15 min sin uso**
   - Primera petición tras estar dormido: tarda 30-60 segundos
   - Después funciona normal
   - Mitigación: abre el servidor 5 minutos antes de presentar

2. **Es plan gratuito de Render**
   - 750 horas/mes (suficiente para un proyecto académico)
   - El servidor reinicia si se queda sin memoria
   - Suficiente para demos pero no para producción real

3. **Cambios al código requieren re-despliegue**
   - Cada vez que cambies algo, súbelo a GitHub
   - Render detecta el cambio y re-despliega automáticamente (5 min)

---

# Si algo sale mal

Pasos de diagnóstico:

1. **Verificar que el API esté corriendo**
   Abre https://agroia-api.onrender.com en el navegador.
   Si ves "404 Not Found" sin más detalles, el servidor está bien.
   Si ves "Application failed to respond", está dormido (espera 60 seg).

2. **Verificar que el frontend cargue**
   Abre https://agroia-app.onrender.com
   Si carga el HTML, está bien.

3. **Verificar que se comunican**
   En la app, deberías ver "Datadog conectado" en verde.
   Si dice "Modo offline", el problema está en:
   - Servidor dormido (espera)
   - URL del API mal en index.html
   - Variable DATADOG_API_KEY mal en Render

4. **Ver logs en Render**
   Render Dashboard → tu servicio → "Logs"
   Te muestra todo lo que está pasando en tiempo real.

---

# Listo para presentar

Una vez todo funciona, tu presentación al profesor cambia COMPLETAMENTE:

ANTES: "Profe, abra mi laptop"
AHORA: "Profe, instale esta app en su celular abriendo este link"

Ese es el salto cualitativo que te exigía. Felicitaciones, has llevado tu
proyecto académico a una app real funcionando en internet.
