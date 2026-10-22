# ScrapeTikTok · Análisis de comentarios de TikTok para empresas

Aplicación web que, a partir del usuario de una cuenta pública de TikTok, **extrae sus últimas publicaciones y comentarios sin iniciar sesión**, y los analiza con **modelos de lenguaje locales** (sin API keys ni servicios externos) para mostrar, en un dashboard:

- la opinión de las personas (**positiva, negativa o neutral**),
- los **temas frecuentes**, **quejas**, **elogios**, **preguntas** y **sugerencias**,
- **estadísticas, conclusiones y recomendaciones** para un negocio,
- un **perfil de personalidad Big Five** de la audiencia y del creador.

> Proyecto académico. Solo cuentas públicas. Ver [Aviso ético y legal](#13-aviso-ético-y-legal).

---

## Índice

1. [Qué hace el proyecto](#1-qué-hace-el-proyecto)
2. [Arquitectura y flujo de datos](#2-arquitectura-y-flujo-de-datos)
3. [Estructura de archivos](#3-estructura-de-archivos)
4. [Tecnologías y librerías (con enlaces de descarga)](#4-tecnologías-y-librerías-con-enlaces-de-descarga)
5. [Instalación paso a paso](#5-instalación-paso-a-paso)
6. [Ejecución y uso](#6-ejecución-y-uso)
7. [Cómo funciona el scraping](#7-cómo-funciona-el-scraping)
8. [Modelos locales de IA](#8-modelos-locales-de-ia)
9. [Cómo se hizo el análisis de comentarios para empresas](#9-cómo-se-hizo-el-análisis-de-comentarios-para-empresas)
10. [Cómo se hizo el análisis Big Five](#10-cómo-se-hizo-el-análisis-big-five)
11. [El dashboard](#11-el-dashboard)
12. [Limitaciones](#12-limitaciones)
13. [Aviso ético y legal](#13-aviso-ético-y-legal)
14. [Solución de problemas](#14-solución-de-problemas)

---

## 1. Qué hace el proyecto

| Función | Descripción |
|---|---|
| **Extracción de publicaciones** | Descripción, fecha, portada, visualizaciones, me gusta, número de comentarios y compartidos. El usuario elige cuántas publicaciones (1 a 50). |
| **Extracción de comentarios** | Comentarios principales de cada publicación (1 a 100 por publicación), **sin iniciar sesión**. |
| **Clasificación de comentarios** | Cada comentario se clasifica por **sentimiento**, **tipo** (elogio, queja, pregunta, sugerencia) y **tema** (precio, calidad, envío…). |
| **Estadísticas y recomendaciones** | Porcentajes, rankings, comentarios más relevantes y conclusiones calculadas con reglas en Python. |
| **Perfil Big Five** | Estimación de los 5 rasgos de personalidad de la audiencia (comentarios) y del creador (descripciones). |
| **Dashboard** | Métricas, gráficos y pestañas en Streamlit. |
| **Modo demostración** | Datos ficticios, claramente marcados, para probar la interfaz sin TikTok. |

**Todo el análisis de IA se hace en el propio computador** con modelos locales: no se necesita ninguna API key y los comentarios no salen de la máquina.

---

## 2. Arquitectura y flujo de datos

```
┌──────────────────────────┐
│  app.py  (Streamlit)     │  interfaz: formulario, botones, dashboard
└───────────┬──────────────┘
            │ consultar()                                  ┌──────────────────────────┐
            ▼                                              │  analisis.py             │
┌──────────────────────────┐                               │  llama a Ollama (local)  │
│  scraper.py (subproceso) │                               │  http://localhost:11434  │
│  Playwright + Scrapy     │                               └────────────▲─────────────┘
└───────────┬──────────────┘                                            │
            │ JSON (última línea de stdout)                             │ clasificar_comentarios()
            ▼                                                           │ analizar()  (Big Five)
   st.session_state["resultado"]  ──── botones «Analizar» ──────────────┘
   (memoria RAM de la sesión)
            │
            ▼
   Estadísticas + recomendaciones (Python puro) → Dashboard
```

**Recorrido completo:**

1. Escribes un usuario y pulsas **Consultar**. `app.py` llama a `consultar()` de `scraper.py`.
2. `consultar()` lanza `scraper.py` como un **subproceso**. Ahí Playwright abre Chromium, lee las publicaciones y (opcionalmente) los comentarios.
3. El subproceso imprime el resultado como JSON; `app.py` lo lee y lo guarda en `st.session_state` (memoria RAM).
4. Pulsas **Analizar comentarios** y/o **Analizar Big Five**: `analisis.py` envía los textos al modelo local por HTTP y devuelve los resultados.
5. Python calcula estadísticas y recomendaciones, y `app.py` dibuja el dashboard.

**Dónde viven los datos:** los **videos no se descargan nunca**. Los comentarios **no se guardan en disco**: solo existen en memoria durante la sesión de Streamlit y se pierden al cerrar la pestaña o reiniciar. Las portadas se guardan únicamente como URL (las descarga el navegador del usuario para mostrarlas).

---

## 3. Estructura de archivos

```
ScrapeTikTok/
├── app.py             Interfaz y dashboard (Streamlit)
├── scraper.py         Extracción de publicaciones y comentarios (Playwright + Scrapy)
├── analisis.py        Análisis con modelos locales: clasificación, estadísticas, recomendaciones y Big Five
├── requirements.txt   Dependencias de Python
├── README.md          Este archivo
└── EXPLICACION.md     Guía de estudio detallada del código (función por función)
```

---

## 4. Tecnologías y librerías (con enlaces de descarga)

### Software que se instala en el computador

| Herramienta | Para qué se usa | Descarga |
|---|---|---|
| **Python 3.10 o superior** | Lenguaje del proyecto | https://www.python.org/downloads/ |
| **Ollama** | Ejecuta los modelos de IA en local y expone una API en `localhost:11434` | https://ollama.com/download |
| **Chromium** (de Playwright) | Navegador real que visita TikTok | Se instala con el comando `playwright install chromium` |

### Librerías de Python (`requirements.txt`)

| Librería | Versión mínima | Para qué se usa | Dónde se usa | Enlace |
|---|---|---|---|---|
| **Scrapy** | 2.11 | Su `Selector` lee el HTML de TikTok y extrae el JSON escondido en las etiquetas `<script>` | `scraper.py`, función `leer_json()` | https://scrapy.org · https://pypi.org/project/Scrapy/ |
| **Playwright** | 1.45 | Controla un navegador real: navega, espera, hace scroll, escucha respuestas y ejecuta el `fetch` de comentarios | `scraper.py`, funciones `leer_embed`, `leer_perfil`, `visitar_video`, `scrapear` | https://playwright.dev/python/ · https://pypi.org/project/playwright/ |
| **Streamlit** | 1.40 | Construye la aplicación web (formulario, tarjetas, gráficos, pestañas) | `app.py` | https://streamlit.io · https://pypi.org/project/streamlit/ |
| **pandas** | — | Tablas para los gráficos de barras. **Se instala solo junto con Streamlit.** | `app.py` | https://pypi.org/project/pandas/ |

### Módulos de la biblioteca estándar de Python (no se instalan)

| Módulo | Uso |
|---|---|
| `subprocess` | Ejecutar `scraper.py` como proceso aparte (`consultar()`) |
| `urllib` | Llamar a la API local de Ollama (`llamar_ollama()`) |
| `json` | Leer y escribir JSON |
| `re` | Validar el nombre de usuario |
| `argparse` | Argumentos de línea de comandos de `scraper.py` |
| `collections.Counter` | Conteos para las estadísticas |
| `unicodedata` | Quitar acentos al normalizar las etiquetas del modelo |
| `pathlib`, `sys`, `datetime` | Rutas, intérprete actual y formato de fechas |

> No se usa ninguna API de pago ni ninguna API key.

---

## 5. Instalación paso a paso

### 5.1 Requisitos del equipo

- **Sistema:** Windows 10/11, macOS o Linux.
- **RAM:** 8 GB como mínimo (16 GB recomendado) para el modelo de 7B.
- **Disco libre:** unos 10 GB (modelos de IA y navegador).
- **Internet:** necesario para descargar las herramientas y para consultar TikTok. El análisis de IA funciona sin internet.
- Una tarjeta gráfica no es obligatoria, pero acelera mucho el análisis. Solo con CPU puede tardar varios minutos.

### 5.2 Pasos (Windows, PowerShell)

**Paso 1. Instalar Python 3.10 o superior.**
Descárgalo de https://www.python.org/downloads/ y durante la instalación marca **«Add Python to PATH»**. Comprueba:

```powershell
python --version
```

**Paso 2. Instalar Ollama.**
Descárgalo de https://ollama.com/download e instálalo. Comprueba:

```powershell
ollama --version
```

**Paso 3. Descargar los modelos de IA.** (Pesan varios GB; se hace una sola vez.)

```powershell
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull gemma3:4b
```

Comprueba que aparezcan:

```powershell
ollama list
```

Páginas oficiales de los modelos:
- Qwen2.5: https://ollama.com/library/qwen2.5
- Gemma 3: https://ollama.com/library/gemma3

**Paso 4. Obtener el proyecto.**
Descomprime el ZIP del proyecto y abre PowerShell dentro de la carpeta `ScrapeTikTok`:

```powershell
cd ruta\a\ScrapeTikTok
```

**Paso 5. Crear y activar un entorno virtual.**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> Si PowerShell bloquea el script, ejecuta primero: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y vuelve a activar.

**Paso 6. Instalar las librerías de Python.**

```powershell
pip install -r requirements.txt
```

**Paso 7. Instalar el navegador de Playwright.**

```powershell
playwright install chromium
```

### 5.3 Pasos (macOS / Linux)

Son los mismos, cambiando solo la creación y activación del entorno:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

En Linux, si Chromium pide dependencias del sistema: `playwright install-deps chromium`.

---

## 6. Ejecución y uso

### 6.1 Arrancar

1. **Ollama debe estar encendido.** En Windows y macOS suele quedar en segundo plano (icono en la bandeja). Si no, abre otra terminal y ejecuta `ollama serve`.
2. Con el entorno virtual activado, dentro de la carpeta del proyecto:

```powershell
streamlit run app.py
```

3. Se abre el navegador en **http://localhost:8501**.

### 6.2 Usar la aplicación

1. **Barra lateral:**
   - Marca **«Incluir comentarios»** y elige cuántos por publicación (para el análisis conviene tener al menos 30 en total).
   - Marca **«Mostrar ventana del navegador»** en la primera prueba, por si TikTok pide una verificación.
   - Elige el **modelo local** (`qwen2.5:7b-instruct-q4_K_M` recomendado, `gemma3:4b` si tu equipo va justo).
   - Opcional: escribe la **marca / producto / campaña** para darle contexto al modelo.
2. Escribe el **usuario de TikTok** (con o sin `@`), el **número de publicaciones** y pulsa **Consultar**.
3. Si TikTok muestra un **captcha**, **resuélvelo tú** en la ventana (la app espera hasta 3 minutos). La app nunca lo resuelve sola.
4. Con los resultados en pantalla, pulsa:
   - **📈 Analizar comentarios** → clasificación y dashboard de negocio.
   - **🧠 Analizar Big Five** → perfil de audiencia y de creador.
5. Revisa las pestañas del dashboard.

> **Probar sin TikTok:** activa **«Modo demostración»** para ver la interfaz con datos ficticios (el análisis de IA está desactivado en ese modo, porque no tendría sentido analizar datos inventados).

---

## 7. Cómo funciona el scraping

El archivo es `scraper.py`.

### 7.1 Por qué hace falta un navegador real

TikTok **no incluye la lista de videos en el HTML inicial** del perfil: la pide después con JavaScript, y esa petición va firmada por el propio código de TikTok. Una petición simple (por ejemplo, solo Scrapy) recibe una página sin videos. Por eso se usa **Playwright**, que controla un Chromium real.

### 7.2 Cómo se usa Scrapy

Scrapy se usa **solo por su `Selector`** (un analizador de HTML con selectores CSS). No hay spider, ni `settings.py`, ni middlewares. Es deliberado: el motor de Scrapy (Twisted) no se puede reiniciar dentro de Streamlit y fallaría en la segunda consulta.

```python
def leer_json(html, id_script):
    texto = Selector(text=html).css(f"script#{id_script}::text").get()
    return json.loads(texto) if texto else None
```

1. Playwright descarga la página y entrega su HTML.
2. El `Selector` busca la etiqueta `<script id="...">` con un selector CSS.
3. Dentro hay un JSON con los datos de la página; `json.loads` lo convierte en diccionarios de Python.

Ids que se leen: `__FRONTITY_CONNECT_STATE__` (página embed) y `__UNIVERSAL_DATA_FOR_REHYDRATION__` (página de cada video).

### 7.3 Las dos rutas para obtener las publicaciones

| Ruta | Función | Qué hace |
|---|---|---|
| **1. Embed público** | `leer_embed()` | Abre `tiktok.com/embed/@usuario`, la página que TikTok ofrece para incrustar un perfil. Trae unas 10 publicaciones. |
| **2. Perfil normal** | `leer_perfil()` | Abre `tiktok.com/@usuario` y **escucha** la respuesta que la propia página pide a `/api/post/item_list`. Hace scroll para cargar más. |

Si la ruta 1 no devuelve videos, se pasa a la ruta 2. **No se copia ninguna firma ni se evade ninguna protección:** solo se leen las respuestas que la página ya pide por sí sola.

### 7.4 Comentarios sin iniciar sesión

La función `leer_comentarios()` (con `JS_FETCH`) abre cada video y, **desde esa misma página**, el propio navegador ejecuta un `fetch` al servicio público `/api/comment/list/`. Pide los comentarios principales de 50 en 50 hasta juntar los solicitados. No se disfraza el cliente ni se cambian cabeceras de red.

### 7.5 Paginación

- **Publicaciones:** scroll infinito. `mouse.wheel` hace que la página pida la siguiente tanda; el número de scrolls crece con lo pedido (`max(5, cantidad // 5 + 3)`).
- **Comentarios:** paginación por `cursor` (0, 50, 100…). Tope de cursor 500 y corte tras 3 páginas vacías seguidas.
- **Lotes para la IA:** los comentarios se dividen en grupos de 25 para no saturar al modelo (no es paginación de TikTok).

### 7.6 Ritmo (rate limit) y bloqueos

No hay un límite formal de peticiones por minuto; hay un **ritmo pausado** con esperas fijas:

| Dónde | Espera |
|---|---|
| Carga del embed | 2,5 s |
| Carga del perfil | 4 s |
| Entre scrolls | 2,5 s |
| Carga de la página de un video | 4 s |
| **Entre páginas de comentarios** | **0,8 s** |
| **Entre un video y el siguiente** | **1,5 s** (los videos se visitan de uno en uno, nunca en paralelo) |

Si TikTok bloquea (HTTP 403, 429 o 503), la app **se detiene y lo informa**; no reintenta ni insiste.

### 7.7 Captcha

La app **nunca intenta resolver ni saltar** una verificación. `captcha_visible()` detecta si hay un captcha **visible** y `esperar_captcha()`, con la ventana del navegador abierta, espera hasta 180 segundos a que **una persona** lo resuelva.

### 7.8 Cookies y sesión

- No se configura ninguna cookie a mano ni se guarda nada en disco, y **no se inicia sesión**.
- `new_context()` de Playwright crea un contexto limpio. TikTok asigna sus cookies de visitante y se **comparten entre las pestañas de esa consulta** (el `fetch` de comentarios las envía con `credentials: 'include'`).
- Al cerrar el navegador, todo se pierde: cada consulta empieza desde cero.

### 7.9 Por qué un subproceso

Playwright y Streamlit entran en conflicto con el bucle `asyncio` en Windows. Por eso `app.py` ejecuta `scraper.py` como un programa aparte con `subprocess.run`, y lee su respuesta JSON (la última línea impresa).

### 7.10 Datos desconocidos

Un dato que TikTok no entrega queda como `None` y se muestra como **«No disponible»**, nunca como 0.

---

## 8. Modelos locales de IA

El análisis usa **Ollama**, un programa que ejecuta modelos de lenguaje en el propio computador y ofrece una API HTTP en `http://localhost:11434`. **No requiere API key ni envía datos a terceros.**

| Modelo | Tamaño aprox. | Papel en el proyecto | Descarga |
|---|---|---|---|
| **`qwen2.5:7b-instruct-q4_K_M`** | ~4,7 GB | **Recomendado.** Sigue bien instrucciones, entiende español y devuelve JSON con fiabilidad. | `ollama pull qwen2.5:7b-instruct-q4_K_M` · https://ollama.com/library/qwen2.5 |
| **`gemma3:4b`** | ~3,3 GB | Alternativa más rápida y ligera para equipos con poca RAM (algo menos precisa). | `ollama pull gemma3:4b` · https://ollama.com/library/gemma3 |

> También existe `qwen2.5-coder`, pero **no se usa**: está afinado para programar, no para analizar texto.

**Dónde se llama al modelo:** solo en `analisis.py`, función `llamar_ollama()` (POST a `/api/chat`). Se invoca desde tres funciones, todas disparadas por botones de `app.py`:

- `clasificar_comentarios()`: una llamada por cada lote de 25 comentarios.
- `analizar()`: una llamada para la audiencia y otra para el creador (Big Five).

**Parámetros usados:** `temperature: 0` (respuestas estables), `format: "json"` (obliga a responder en JSON), `stream: false` y `num_ctx: 8192` (memoria de contexto).

**Cómo se evita que la página se cuelgue:**
- Timeout de **300 s** por llamada (`TIMEOUT`).
- Entrada acotada: máximo 100 textos de 150 caracteres.
- Errores traducidos a mensajes claros: Ollama apagado, modelo no instalado, respuesta inválida o timeout.
- Un mensaje de progreso mientras se analiza (puede tardar de 1 a varios minutos, según el equipo).

**Seguridad frente a «inyección de instrucciones»:** un comentario podría decir «ignora tus instrucciones…». Por eso los textos se encierran entre `<<<` y `>>>` y el prompt ordena tratarlos como **datos, no como instrucciones**. Además, toda respuesta del modelo se **valida** antes de usarse.

---

## 9. Cómo se hizo el análisis de comentarios para empresas

**Objetivo:** convertir los comentarios en información útil para un negocio: qué opina la gente, de qué habla, qué reclama o pregunta, y qué conviene hacer.

**Reparto de trabajo: la IA clasifica, Python calcula.**

| Paso | Quién | Función (`analisis.py`) |
|---|---|---|
| Limpiar y limitar comentarios | Python | `preparar_comentarios()` |
| Clasificar cada comentario | **Modelo local** | `clasificar_comentarios()` |
| Conteos, porcentajes y rankings | Python | `calcular_estadisticas()` |
| Resumen en texto | Python | `armar_resumen()` |
| Recomendaciones | **Python (reglas)** | `generar_recomendaciones()` |

### 9.1 Clasificación con listas cerradas

El modelo **solo puede elegir** entre opciones fijas, de modo que Python pueda contar sin ambigüedad y el modelo no invente categorías:

- **Sentimiento:** positivo, negativo, neutral.
- **Tipo:** elogio, queja, pregunta, sugerencia, otro.
- **Tema:** precio, calidad, atención, envío, diseño, funcionamiento, contenido, otro.

Se envían lotes de 25 comentarios y el modelo responde un JSON compacto, una fila por comentario: `[número, sentimiento, tipo, tema]`. La función `leer_clasificacion()` valida cada fila, ignora acentos y mayúsculas, y reemplaza cualquier valor fuera de las listas por uno neutro. Si un lote falla, se salta y se avisa cuántos comentarios se clasificaron; si Ollama deja de responder, se conserva lo ya clasificado.

### 9.2 Estadísticas (Python puro)

`calcular_estadisticas()` obtiene: porcentajes por sentimiento, ranking de temas, sentimiento por tema, sentimiento por publicación, tipos de comentario y los **comentarios más relevantes** (los de más «me gusta») de cada tipo.

### 9.3 Recomendaciones basadas en reglas

Cada recomendación se activa por un número real, así que **es rastreable y no la inventa el modelo**:

| Si ocurre… | La recomendación dice… |
|---|---|
| ≥ 40 % de comentarios negativos | Revisar la causa antes de seguir invirtiendo. |
| ≥ 60 % positivos | Repetir el formato y pedir reseñas. |
| Ninguno de los dos | La opinión está dividida: mirar los temas. |
| Un tema concentra ≥ 2 de los negativos (con ≥ 3 negativos) | Es la prioridad de mejora. |
| Un tema concentra ≥ 2 de los positivos (con ≥ 3 positivos) | Destacarlo en la comunicación. |
| ≥ 3 preguntas | Responderlas y hacer un video de preguntas frecuentes. |
| ≥ 1 sugerencia | Revisarlas: son ideas gratuitas de mejora. |
| Una publicación tiene ≥ 50 % de los negativos | Revisar ese contenido. |
| Menos de 30 comentarios | La muestra es pequeña: usar como orientación. |

---

## 10. Cómo se hizo el análisis Big Five

El modelo Big Five describe la personalidad en 5 rasgos: **apertura a la experiencia, responsabilidad, extraversión, amabilidad y neuroticismo**.

### 10.1 Método

1. `preparar_textos()` limpia los textos: quita espacios raros, vacíos y duplicados, recorta cada uno a 150 caracteres y deja máximo 100.
2. `crear_prompt()` arma **un solo prompt** con todos los textos y pide un JSON con los 5 rasgos: puntaje de 0 a 100 y una justificación breve.
3. `llamar_ollama()` lo envía al modelo local.
4. `leer_respuesta()` **valida** el JSON, fuerza los puntajes al rango 0 a 100 y falla con un mensaje claro si falta algún rasgo.
5. `confianza()` calcula una confianza **«baja / media / alta» según cuántos textos había** (la decide el código, no el modelo).

### 10.2 Dos análisis separados

| Análisis | Fuente | Nota |
|---|---|---|
| **Audiencia** | Comentarios | Los comentarios los escriben **otras personas**, así que describen a la audiencia, **no al dueño de la cuenta**. También genera recomendaciones de comunicación para una marca o colaborador. |
| **Creador** | Descripciones de sus videos | Solo se hace si hay al menos 3 descripciones. La muestra suele ser pequeña, por eso la confianza suele salir «baja». |

> **Importante:** no es un test psicométrico ni un diagnóstico. Son señales aproximadas del lenguaje de un conjunto de textos, estimadas por un modelo pequeño que puede equivocarse.

---

## 11. El dashboard

Se muestra después de pulsar los botones de análisis, en pestañas:

| Pestaña | Contenido |
|---|---|
| **📊 Resumen** | Total de comentarios, % positivos / negativos / neutrales, resumen en texto, gráfico de tipos de comentario y gráfico de sentimiento por publicación. |
| **🧩 Temas** | Barras apiladas por tema, coloreadas por sentimiento (verde, rojo, gris). |
| **👍 Elogios y quejas** | Los comentarios más relevantes (más «me gusta») y las sugerencias. |
| **❓ Preguntas** | Las preguntas de los usuarios. |
| **💡 Recomendaciones** | Conclusiones basadas en reglas (sección 9.3). |
| **🧠 Big Five** | Barras por rasgo, justificación, confianza y recomendaciones de comunicación para la audiencia. |

Los gráficos usan `st.bar_chart` (de Streamlit) y `pandas`. **No se muestra el nombre de usuario de quien comenta**, solo el texto y los «me gusta».

---

## 12. Limitaciones

- **Alcance:** solo se analizan los comentarios de **los videos de la cuenta consultada**, no todo lo que se dice de una marca en TikTok.
- **Sin iniciar sesión, TikTok limita los datos:** suele entregar solo unas **10 publicaciones recientes**; si se piden más, se muestran las disponibles con un aviso. Los comentarios pueden llegar pocos o ninguno.
- **Solo comentarios principales:** no se leen las respuestas a los comentarios.
- **Bloqueos:** TikTok puede pedir un captcha o bloquear por IP o por exceso de peticiones. Entonces la app se detiene e informa; no lo evade.
- **Fragilidad:** las rutas internas de TikTok (`/api/post/item_list`, `/api/comment/list/`) y los ids de sus `<script>` pueden cambiar sin aviso.
- **Precisión de la IA:** un modelo de 7B o 4B se equivoca con sarcasmo, ironía y jerga local. Es clasificación automática, no una verdad.
- **Muestra:** se analizan como máximo 100 comentarios (los primeros, no los más populares, para no sesgar el resultado). Con menos de 30, el dashboard advierte «muestra pequeña».
- **Tiempo:** depende del equipo; con GPU son segundos por lote y solo con CPU pueden ser varios minutos.
- **Sin detección de cuenta privada o vacía:** esos casos muestran un mensaje general de que TikTok no entregó publicaciones.

---

## 13. Aviso ético y legal

- Proyecto con **fines académicos**; se trabaja únicamente con **cuentas y contenido públicos**.
- Los términos de uso de TikTok restringen el acceso automatizado. La aplicación procura ser respetuosa: ritmo pausado, no inicia sesión, **no evade captchas**, no copia firmas, no disfraza el cliente y se detiene ante un bloqueo.
- **Privacidad:** no se guarda nada en disco; los datos viven en memoria durante la sesión. No se muestran nombres de usuarios que comentan. Todo el análisis de IA ocurre en el propio computador.
- **Uso responsable de los resultados:** el Big Five es una estimación aproximada de un conjunto de textos, no un diagnóstico de nadie. Las recomendaciones son de comunicación y mejora de negocio, **no** para perfilar ni acercarse a una persona concreta.

---

## 14. Solución de problemas

| Mensaje o síntoma | Causa y solución |
|---|---|
| «Falta el navegador de Playwright» | Ejecuta `playwright install chromium`. |
| «No se pudo conectar con Ollama» | Abre Ollama (o ejecuta `ollama serve`) y vuelve a intentar. |
| «El modelo … no está instalado» | Ejecuta `ollama pull nombre-del-modelo` (ver sección 5, paso 3). |
| «TikTok pidió una verificación humana» | Marca **«Mostrar ventana del navegador»**, consulta de nuevo y resuelve el captcha tú. |
| «TikTok no entregó las publicaciones» | Bloqueo de TikTok. Espera un rato, prueba con la ventana visible o con otra red. |
| «TikTok bloqueó la lectura de comentarios» | Límite por IP o exceso de peticiones. Espera y baja la cantidad de publicaciones o comentarios. |
| Comentarios «no disponibles» | Pueden estar desactivados o TikTok no los entrega sin sesión. |
| «El modelo tardó más de 300 segundos» | Usa `gemma3:4b` o pide menos comentarios. |
| «El modelo no devolvió un JSON válido» | Inténtalo de nuevo o cambia de modelo. |
| PowerShell no deja activar el entorno | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y reactiva. |
| `streamlit` no se reconoce como comando | El entorno virtual no está activado; actívalo (paso 5) o usa `python -m streamlit run app.py`. |

---

**Más detalle del código:** ver `EXPLICACION.md`, una guía de estudio que explica el proyecto función por función.
