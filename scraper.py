"""Scraper de TikTok (sin iniciar sesión).

Idea general:
1. Se abre un navegador real con Playwright (TikTok no entrega los videos con una petición simple).
2. Se intenta primero el "embed" público del creador; si no sirve, se usa el perfil normal y se
   ESCUCHAN las respuestas que la propia página ya pide (/api/post/item_list).
3. Si TikTok muestra un captcha, la app NO lo resuelve: espera a que lo resuelva una persona.
4. El HTML se lee con el Selector de Scrapy y todo se devuelve como diccionarios simples.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from scrapy import Selector

CARPETA = Path(__file__).resolve().parent
ESPERA_PERSONA = 180  # segundos que se espera a que una persona resuelva un captcha
MARGEN_FIJADOS = 3  # los videos fijados pueden ser viejos: se piden de más
CAMPOS = ("descripcion", "fecha", "portada", "vistas", "likes", "comentarios_total", "compartidos")
CAPTCHA = ("#captcha_container", ".captcha_verify_container", "[class*='captcha_verify']",
           "iframe[src*='captcha']", "[id*='captcha']")


class ErrorScrape(Exception):
    """Error previsto con un mensaje que se le muestra al usuario."""


# --------------------------------------------------------------------------- #
# 1. Funciones pequeñas para limpiar datos
# --------------------------------------------------------------------------- #
def validar_usuario(texto):
    usuario = (texto or "").strip().removeprefix("@")
    if not re.fullmatch(r"[A-Za-z0-9_.]{2,24}", usuario) or usuario.endswith("."):
        raise ErrorScrape("Usuario no válido. Usa letras, números, guion bajo o punto (2 a 24 caracteres).")
    return usuario


def numero(valor):
    """Convierte a entero. Si no se puede devuelve None (desconocido), nunca 0."""
    try:
        n = int(valor)
        return n if n >= 0 else None
    except (TypeError, ValueError):
        return None


def convertir_video(raw, usuario):
    """Convierte un video crudo de TikTok en un diccionario ordenado. None si no es un video."""
    if not isinstance(raw, dict) or not str(raw.get("id", "")).isdigit():
        return None
    stats = raw.get("statsV2") or raw.get("stats") or raw
    video = raw.get("video") if isinstance(raw.get("video"), dict) else {}
    return {
        "id": str(raw["id"]),
        "url": f"https://www.tiktok.com/@{usuario}/video/{raw['id']}",
        "descripcion": raw.get("desc") if isinstance(raw.get("desc"), str) else None,
        "fecha": numero(raw.get("createTime")) or None,  # segundos desde 1970
        "portada": video.get("cover") or video.get("originCover") or raw.get("cover"),
        "vistas": numero(stats.get("playCount")),
        "likes": numero(stats.get("diggCount")),
        "comentarios_total": numero(stats.get("commentCount")),
        "compartidos": numero(stats.get("shareCount")),
        "comentarios": [],
        "estado_comentarios": "no_solicitados",  # no_solicitados | ok | no_disponibles
        "nota_comentarios": None,
    }


def convertir_comentario(raw):
    usuario = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    return {
        "texto": raw["text"],
        "autor": usuario.get("unique_id") or usuario.get("nickname"),
        "fecha": numero(raw.get("create_time")) or None,
        "likes": numero(raw.get("digg_count")),
        "respuestas": numero(raw.get("reply_comment_total")),
    }


def leer_json(html, id_script):
    """Lee el JSON que TikTok deja dentro de una etiqueta <script> (con el Selector de Scrapy)."""
    texto = Selector(text=html).css(f"script#{id_script}::text").get()
    try:
        return json.loads(texto) if texto else None
    except json.JSONDecodeError:
        return None


def buscar_videos(dato):
    """Recorre un JSON entero y devuelve todo lo que tenga forma de video (aguanta cambios de estructura)."""
    encontrados, pendientes = [], [(dato, 0)]
    while pendientes:
        nodo, profundidad = pendientes.pop()
        if profundidad > 12:
            continue
        hijos = nodo if isinstance(nodo, list) else list(nodo.values()) if isinstance(nodo, dict) else []
        for hijo in hijos:
            es_video = (isinstance(hijo, dict) and str(hijo.get("id", "")).isdigit()
                        and any(k in hijo for k in ("desc", "stats", "statsV2", "video", "playCount")))
            if es_video:
                encontrados.append(hijo)
            else:
                pendientes.append((hijo, profundidad + 1))
    return encontrados


def faltan_datos(video):
    return any(video[campo] is None for campo in CAMPOS)


def traducir_error(error):
    """Convierte cualquier excepción en un mensaje comprensible."""
    texto = str(error)
    if isinstance(error, ErrorScrape):
        return texto
    if "Executable doesn't exist" in texto:
        return "Falta el navegador de Playwright. Ejecuta: playwright install chromium"
    if type(error).__name__ == "TimeoutError":
        return "TikTok tardó demasiado en responder."
    if "net::ERR" in texto:
        return "Error de conexión. Revisa tu internet."
    return f"Error inesperado ({type(error).__name__})."


# --------------------------------------------------------------------------- #
# 2. Navegador (Playwright)
# --------------------------------------------------------------------------- #
def guardar_respuesta(respuesta, fragmento, lista):
    """Guarda el JSON de las respuestas cuya URL contiene `fragmento`."""
    if fragmento in respuesta.url:
        try:
            lista.append(respuesta.json())
        except Exception:
            pass


def captcha_visible(pagina):
    for selector in CAPTCHA:
        try:
            if pagina.locator(selector).first.is_visible():
                return True
        except Exception:
            continue
    return False


def esperar_captcha(pagina, mostrar):
    """Si hay captcha, espera a que lo resuelva UNA PERSONA. Devuelve True si hubo captcha."""
    if not captcha_visible(pagina):
        return False
    if not mostrar:
        raise ErrorScrape("TikTok pidió una verificación humana. Marca «Mostrar ventana del navegador» "
                          "y consulta de nuevo para resolverla tú; la app no la evade.")
    for _ in range(ESPERA_PERSONA // 2):
        pagina.wait_for_timeout(2000)
        if not captcha_visible(pagina):
            pagina.wait_for_timeout(2000)
            return True
    raise ErrorScrape("La verificación no se resolvió a tiempo. Inténtalo de nuevo.")


def recolectar(respuestas, usuario, videos):
    """Pasa las respuestas escuchadas a la lista de videos (sin repetir)."""
    for datos in respuestas:
        lista = datos.get("itemList") if isinstance(datos, dict) else None
        for raw in lista or []:
            video = convertir_video(raw, usuario)
            if video:
                videos.setdefault(video["id"], video)


def leer_embed(pagina, usuario, videos):
    """Ruta 1: el 'embed' público del creador (no pide sesión)."""
    try:
        pagina.goto(f"https://www.tiktok.com/embed/@{usuario}", wait_until="domcontentloaded", timeout=30000)
        pagina.wait_for_timeout(2500)
        datos = leer_json(pagina.content(), "__FRONTITY_CONNECT_STATE__")
        for raw in buscar_videos(datos):
            video = convertir_video(raw, usuario)
            if video:
                videos.setdefault(video["id"], video)
    except Exception:
        videos.clear()  # el embed es opcional: se pasa a la ruta 2


def leer_perfil(pagina, respuestas, usuario, videos, cantidad, mostrar):
    """Ruta 2: perfil normal. Se escuchan las respuestas que la página ya pide."""
    pagina.goto(f"https://www.tiktok.com/@{usuario}", wait_until="domcontentloaded", timeout=30000)
    pagina.wait_for_timeout(4000)
    if esperar_captcha(pagina, mostrar):
        pagina.reload(wait_until="domcontentloaded", timeout=30000)
        pagina.wait_for_timeout(4000)
    recolectar(respuestas, usuario, videos)

    # Con ventana abierta y sin videos (p. ej. captcha no detectado): se da tiempo a una persona.
    if not videos and mostrar:
        for _ in range(ESPERA_PERSONA // 2):
            pagina.wait_for_timeout(2000)
            recolectar(respuestas, usuario, videos)
            if videos:
                break
        if not videos:
            pagina.reload(wait_until="domcontentloaded", timeout=30000)
            pagina.wait_for_timeout(5000)
            recolectar(respuestas, usuario, videos)

    # Scroll para que TikTok cargue más videos
    for _ in range(5):
        if len(videos) >= cantidad + MARGEN_FIJADOS:
            break
        antes = len(videos)
        pagina.mouse.wheel(0, 3000)
        pagina.wait_for_timeout(2500)
        recolectar(respuestas, usuario, videos)
        if len(videos) == antes:
            break


def visitar_video(contexto, video, usuario, con_comentarios, por_post, mostrar):
    """Abre la página de un video: completa datos que falten y lee comentarios si se pidió."""
    pagina = contexto.new_page()
    respuestas = []
    pagina.on("response", lambda r: guardar_respuesta(r, "/api/comment/list/", respuestas)
              if "/reply" not in r.url else None)
    try:
        pagina.goto(video["url"], wait_until="domcontentloaded", timeout=30000)
        pagina.wait_for_timeout(4000)
        if esperar_captcha(pagina, mostrar):
            pagina.wait_for_timeout(3000)
        datos = leer_json(pagina.content(), "__UNIVERSAL_DATA_FOR_REHYDRATION__")
    finally:
        pagina.close()

    # Rellena SOLO los campos que estaban desconocidos
    for raw in buscar_videos(datos):
        nuevo = convertir_video(raw, usuario)
        if nuevo and nuevo["id"] == video["id"]:
            for campo in CAMPOS:
                if video[campo] is None:
                    video[campo] = nuevo[campo]
            break

    if not con_comentarios:
        return
    lista = next((r["comments"] for r in respuestas
                  if isinstance(r, dict) and isinstance(r.get("comments"), list)), None)
    if lista is None:
        video["estado_comentarios"] = "no_disponibles"
        video["nota_comentarios"] = "TikTok no entregó los comentarios. Sin sesión iniciada suele ser así."
    else:
        validos = [c for c in lista if isinstance(c, dict) and isinstance(c.get("text"), str)]
        video["comentarios"] = [convertir_comentario(c) for c in validos[:por_post]]
        video["estado_comentarios"] = "ok"


def scrapear(usuario, cantidad, con_comentarios, por_post, mostrar):
    from playwright.sync_api import sync_playwright  # se importa aquí para dar un error claro si falta

    videos, avisos, respuestas = {}, [], []
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(headless=not mostrar)
        try:
            contexto = navegador.new_context(locale="es-ES")
            pagina = contexto.new_page()
            pagina.on("response", lambda r: guardar_respuesta(r, "/api/post/item_list", respuestas))

            leer_embed(pagina, usuario, videos)
            if videos:
                avisos.append("Publicaciones leídas del «embed» público de TikTok: algunas métricas pueden faltar.")
            else:
                leer_perfil(pagina, respuestas, usuario, videos, cantidad, mostrar)

            if not videos:
                raise ErrorScrape("TikTok no entregó las publicaciones sin iniciar sesión. Si no usaste la "
                                  "ventana, márcala y vuelve a intentar. Si sigue igual, es un bloqueo de TikTok.")

            # Las más recientes primero (los fijados pueden ser viejos y venir antes)
            ordenados = sorted(videos.values(), key=lambda v: v["fecha"] or 0, reverse=True)[:cantidad]
            if len(ordenados) < cantidad:
                avisos.append(f"TikTok entregó solo {len(ordenados)} de las {cantidad} publicaciones pedidas.")

            for i, video in enumerate(ordenados):
                if not con_comentarios and not faltan_datos(video):
                    continue
                try:
                    visitar_video(contexto, video, usuario, con_comentarios, por_post, mostrar)
                except Exception as error:
                    avisos.append(f"No se pudieron completar todos los datos: {traducir_error(error)}")
                    if con_comentarios:
                        for resto in ordenados[i:]:
                            resto["estado_comentarios"] = "no_disponibles"
                            resto["nota_comentarios"] = traducir_error(error)
                    break
                pagina.wait_for_timeout(1500)  # ritmo pausado

            ordenados.sort(key=lambda v: v["fecha"] or 0, reverse=True)
            return {"usuario": usuario, "fuente": "real", "publicaciones": ordenados, "avisos": avisos}
        finally:
            navegador.close()


# --------------------------------------------------------------------------- #
# 3. Conexión con app.py
# --------------------------------------------------------------------------- #
def consultar(usuario, cantidad, con_comentarios=False, mostrar=False):
    """Lo llama la app. Ejecuta este mismo archivo en un subproceso (así Playwright
    funciona estable dentro de Streamlit en Windows) y lee su respuesta JSON."""
    comando = [sys.executable, str(Path(__file__).resolve()), "--usuario", usuario, "--cantidad", str(cantidad)]
    if con_comentarios:
        comando.append("--comentarios")
    if mostrar:
        comando.append("--mostrar-navegador")
    try:
        hecho = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8",
                               timeout=900, cwd=CARPETA)
        respuesta = json.loads(hecho.stdout.strip().splitlines()[-1])  # la última línea es la respuesta
    except subprocess.TimeoutExpired:
        raise ErrorScrape("La consulta tardó demasiado y se canceló.") from None
    except (IndexError, json.JSONDecodeError):
        raise ErrorScrape("La consulta terminó sin una respuesta válida.") from None
    if not respuesta["ok"]:
        raise ErrorScrape(respuesta["error"])
    return respuesta["resultado"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--usuario", required=True)
    parser.add_argument("--cantidad", type=int, default=5)
    parser.add_argument("--comentarios", action="store_true")
    parser.add_argument("--mostrar-navegador", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        resultado = scrapear(validar_usuario(args.usuario), args.cantidad, args.comentarios, 20,
                             args.mostrar_navegador)
        salida = {"ok": True, "resultado": resultado}
    except Exception as error:
        salida = {"ok": False, "error": traducir_error(error)}
    print(json.dumps(salida, ensure_ascii=False))
