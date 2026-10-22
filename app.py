"""Interfaz de ScrapeTikTok. Ejecutar con: streamlit run app.py"""
from datetime import datetime, timezone
 
import pandas as pd  # ya viene instalado con Streamlit
import streamlit as st
 
from analisis import (MODELOS, RASGOS, SENTIMIENTOS, ErrorAnalisis, analizar, armar_resumen, calcular_estadisticas,
                      clasificar_comentarios, generar_recomendaciones, nombre_tema, porcentaje, preparar_textos)
from scraper import MAX_COMENTARIOS, MAX_PUBLICACIONES, ErrorScrape, consultar, validar_usuario
 
st.set_page_config(page_title="ScrapeTikTok", page_icon="🎵", layout="centered")
 
 
def numero_txt(valor):
    return "No disponible" if valor is None else f"{valor:,}".replace(",", ".")
 
 
def fecha_txt(segundos):
    if not segundos:
        return "Fecha no disponible"
    return datetime.fromtimestamp(segundos, tz=timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
 
 
def datos_demo(usuario, cantidad):
    """Datos FICTICIOS para probar la interfaz sin TikTok."""
    posts = []
    for i in range(cantidad):
        post = {"id": str(i), "url": f"https://www.tiktok.com/@{usuario}/video/{i}",
                "descripcion": f"[DEMO] Publicación de ejemplo {i + 1}", "fecha": 1790000000 - i * 86400,
                "portada": None, "vistas": 1000 * (i + 1), "likes": 100 * (i + 1),
                "comentarios_total": 12, "compartidos": 5 * (i + 1),
                "comentarios": [], "estado_comentarios": "no_solicitados", "nota_comentarios": None}
        if i % 3 == 0:  # con comentarios
            post["estado_comentarios"] = "ok"
            post["comentarios"] = [{"texto": "[DEMO] Comentario de ejemplo", "autor": "usuario_demo",
                                    "fecha": 1790000000, "likes": 4, "respuestas": 1}]
        elif i % 3 == 1:  # sin comentarios disponibles
            post["estado_comentarios"] = "no_disponibles"
            post["nota_comentarios"] = "[DEMO] TikTok no entregó los comentarios."
        posts.append(post)
    return {"usuario": usuario, "fuente": "demo", "publicaciones": posts,
            "avisos": ["Estos datos son ficticios y sirven solo para probar la interfaz."]}
 
 
def mostrar_comentarios(post):
    estado = post["estado_comentarios"]
    if estado == "no_solicitados":
        titulo = "Comentarios (no solicitados)"
    else:
        titulo = (f"Comentarios: {len(post['comentarios'])} recuperados de "
                  f"{numero_txt(post['comentarios_total'])} en TikTok")
    with st.expander(titulo):
        if estado == "no_solicitados":
            st.info("Activa «Incluir comentarios» en la barra lateral y vuelve a consultar.")
        elif estado == "no_disponibles":
            st.warning(post["nota_comentarios"] or "Los comentarios no están disponibles.")
        elif not post["comentarios"]:
            st.info("No se recuperó ningún comentario de esta publicación.")
        for c in post["comentarios"]:
            st.text(c["texto"])
            st.caption(f"{c['autor'] or 'autor desconocido'} · {fecha_txt(c['fecha'])}"
                       f" · Me gusta: {numero_txt(c['likes'])} · Respuestas: {numero_txt(c['respuestas'])}")
 
 
def mostrar_publicacion(post, indice, demo):
    with st.container(border=True):
        col_img, col_info = st.columns([1, 3])
        with col_img:
            if post["portada"]:
                st.image(post["portada"])
            else:
                st.caption("Sin portada")
        with col_info:
            st.markdown(f"**Publicación {indice}** · {fecha_txt(post['fecha'])}")
            if post["descripcion"] is None:
                st.text("Descripción no disponible")
            else:
                st.text(post["descripcion"] or "(sin descripción)")
 
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Visualizaciones", numero_txt(post["vistas"]))
        c2.metric("Me gusta", numero_txt(post["likes"]))
        c3.metric("Comentarios (total)", numero_txt(post["comentarios_total"]))
        c4.metric("Compartidos", numero_txt(post["compartidos"]))
 
        st.link_button("Abrir en TikTok", post["url"], disabled=demo)
        mostrar_comentarios(post)
 
 
def nivel(puntaje):
    return "Bajo" if puntaje < 40 else "Alto" if puntaje >= 60 else "Medio"
 
 
def mostrar_rasgos(analisis, tipo):
    """Una barra por rasgo Big Five, con su justificación."""
    st.caption(f"{tipo}: {analisis['n']} · Confianza: {analisis['confianza']} · Modelo: {analisis['modelo']}")
    if analisis["confianza"] == "baja":
        st.warning("Muestra pequeña: toma este resultado con mucha cautela.")
    for clave, nombre in RASGOS.items():
        rasgo = analisis["rasgos"][clave]
        st.progress(rasgo["puntaje"] / 100, text=f"{nombre}: {rasgo['puntaje']}/100 ({nivel(rasgo['puntaje'])})")
        st.caption(rasgo["justificacion"])
 
 
def mostrar_bigfive(resultado):
    if not resultado:
        st.info("Pulsa «🧠 Analizar Big Five» para ver el perfil de la audiencia y del creador.")
        return
    st.caption("Estimación aproximada del lenguaje hecha por un modelo local. No es un test psicométrico "
               "ni un diagnóstico, y los comentarios son de la audiencia, no del dueño de la cuenta.")
    tab_audiencia, tab_creador = st.tabs(["👥 Audiencia (comentarios)", "✍️ Creador (descripciones)"])
    with tab_audiencia:
        mostrar_rasgos(resultado["audiencia"], "Comentarios analizados")
        st.markdown("#### 💬 Recomendaciones de comunicación")
        for recomendacion in resultado["audiencia"]["recomendaciones"] or ["El modelo no dio recomendaciones."]:
            st.markdown(f"- {recomendacion}")
    with tab_creador:
        if resultado["creador"]:
            mostrar_rasgos(resultado["creador"], "Descripciones analizadas")
        else:
            st.info("Hay muy pocas descripciones (mínimo 3) para analizar al creador.")
 
 
COLORES = ["#2ecc71", "#e74c3c", "#95a5a6"]  # positivo, negativo, neutral (mismo orden que SENTIMIENTOS)
 
 
def grafico_sentimientos(datos, etiqueta):
    """Barras apiladas por sentimiento. `datos`: {clave: {sentimiento: cantidad}}."""
    tabla = pd.DataFrame({s.capitalize(): [v.get(s, 0) for v in datos.values()] for s in SENTIMIENTOS},
                         index=[etiqueta(k) for k in datos])
    st.bar_chart(tabla, color=COLORES)
 
 
def lista_comentarios(lista, vacio):
    """Muestra comentarios con sus likes. No se muestra el nombre de usuario (privacidad)."""
    if not lista:
        st.info(vacio)
    for c in lista:
        st.text(c["texto"])
        st.caption(f"👍 {numero_txt(c['likes'])} · Publicación {c['publicacion']} · Tema: {nombre_tema(c['tema'])}")
 
 
def sin_datos(negocio):
    if negocio:
        return False
    st.info("Pulsa «📈 Analizar comentarios» para clasificar los comentarios con el modelo local.")
    return True
 
 
def mostrar_resumen(negocio):
    if sin_datos(negocio):
        return
    est, n = negocio["estadisticas"], negocio["estadisticas"]["n"]
    if negocio["aviso"]:
        st.warning(negocio["aviso"])
    if n < 30:
        st.warning("Muestra pequeña: las estadísticas son orientativas.")
    st.caption(f"Clasificación automática con {negocio['modelo']}"
               + (f" · Marca/campaña: {negocio['marca']}" if negocio["marca"] else "")
               + ". Puede equivocarse con sarcasmo o jerga.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Comentarios", n)
    for columna, sentimiento, titulo in zip((c2, c3, c4), SENTIMIENTOS, ("Positivos", "Negativos", "Neutrales")):
        cantidad = est["sentimiento"].get(sentimiento, 0)
        columna.metric(titulo, f"{porcentaje(cantidad, n)} %", f"{cantidad} comentarios", delta_color="off")
    st.info(negocio["resumen"])
    st.markdown("##### Tipo de comentario")
    st.bar_chart(pd.DataFrame({"Comentarios": est["tipo"]}))
    st.markdown("##### Sentimiento por publicación")
    grafico_sentimientos(dict(sorted(est["por_publicacion"].items())), lambda p: f"Pub. {p:02d}")
 
 
def mostrar_temas(negocio):
    if sin_datos(negocio):
        return
    st.markdown("##### Temas más frecuentes (coloreados por sentimiento)")
    datos = dict(sorted(negocio["estadisticas"]["tema_sentimiento"].items(), key=lambda x: -sum(x[1].values())))
    grafico_sentimientos(datos, nombre_tema)
 
 
def mostrar_opiniones(negocio):
    if sin_datos(negocio):
        return
    est = negocio["estadisticas"]
    st.markdown("##### 😠 Quejas más relevantes")
    lista_comentarios(est["quejas"], "No se detectaron quejas.")
    st.markdown("##### 😍 Elogios más relevantes")
    lista_comentarios(est["elogios"], "No se detectaron elogios.")
    st.markdown("##### 💡 Sugerencias")
    lista_comentarios(est["sugerencias"], "No se detectaron sugerencias.")
    st.caption("Los más relevantes son los que tienen más «me gusta».")
 
 
def mostrar_preguntas(negocio):
    if sin_datos(negocio):
        return
    st.markdown("##### ❓ Preguntas de los usuarios")
    lista_comentarios(negocio["estadisticas"]["preguntas"], "No se detectaron preguntas.")
 
 
def mostrar_recomendaciones(negocio):
    if sin_datos(negocio):
        return
    st.markdown("##### 💡 Recomendaciones basadas en los datos")
    for recomendacion in negocio["recomendaciones"]:
        st.markdown(f"- {recomendacion}")
    st.caption("Generadas con reglas en Python a partir de los números del análisis; no las inventa el modelo.")
 
 
# ------------------------------- Barra lateral ------------------------------ #
with st.sidebar:
    st.header("Opciones")
    modo_demo = st.toggle("Modo demostración (datos ficticios)")
    incluir_comentarios = st.checkbox("Incluir comentarios",
                                      help="Más lento: abre cada video y lee sus comentarios principales.")
    comentarios_por_post = st.number_input("Comentarios por publicación", min_value=1, max_value=MAX_COMENTARIOS,
                                           value=30, step=1, disabled=not incluir_comentarios,
                                           help="Para el análisis Big Five conviene tener al menos 30 en total.")
    mostrar_navegador = st.checkbox("Mostrar ventana del navegador",
                                    help="Útil si TikTok pide una verificación: la resuelves tú.")
    st.divider()
    modelo = st.selectbox("Modelo local (Ollama) para el análisis", MODELOS)
    marca = st.text_input("Marca / producto / campaña (opcional)",
                          help="Se le indica al modelo para que entienda de qué hablan los comentarios.")
 
# --------------------------------- Principal -------------------------------- #
st.title("🎵 ScrapeTikTok")
st.write("Proyecto académico: consulta las últimas publicaciones públicas de una cuenta de TikTok, "
         "sus métricas y los comentarios que TikTok permita ver, y analiza lo que dicen las personas "
         "(opiniones, temas, quejas, preguntas y perfil Big Five).")
 
with st.form("consulta"):
    usuario = st.text_input("Usuario de TikTok", placeholder="@usuario")
    cantidad = st.number_input("Número de publicaciones a mostrar", min_value=1, max_value=MAX_PUBLICACIONES,
                               value=5, step=1,
                               help="Sin iniciar sesión, TikTok suele entregar solo unas 10 recientes.")
    enviar = st.form_submit_button("Consultar", type="primary")
 
if enviar:
    try:
        nombre = validar_usuario(usuario)
        if modo_demo:
            resultado = datos_demo(nombre, int(cantidad))
        else:
            with st.status("Consultando TikTok… Si aparece una verificación en la ventana, resuélvela tú "
                           "(hay hasta 3 minutos).", expanded=True) as estado:
                resultado = consultar(nombre, int(cantidad), incluir_comentarios,
                                      int(comentarios_por_post), mostrar_navegador)
                estado.update(label="Consulta terminada", state="complete", expanded=False)
        st.session_state["resultado"] = resultado
        for clave in ("analisis", "negocio"):  # un análisis viejo no corresponde a la consulta nueva
            st.session_state.pop(clave, None)
    except ErrorScrape as error:
        for clave in ("resultado", "analisis", "negocio"):
            st.session_state.pop(clave, None)
        st.error(str(error))
 
resultado = st.session_state.get("resultado")
if resultado:
    es_demo = resultado["fuente"] == "demo"
    if es_demo:
        st.warning("🧪 DATOS DE DEMOSTRACIÓN: son ficticios y no provienen de TikTok.")
    else:
        st.success(f"✅ Datos reales de TikTok para @{resultado['usuario']}.")
    for aviso in resultado["avisos"]:
        st.info(aviso)
 
    # ---- Análisis con el modelo local ----
    publicaciones = resultado["publicaciones"]
    comentarios = [c["texto"] for p in publicaciones for c in p["comentarios"]]
    comentarios_ricos = [{"texto": c["texto"], "likes": c["likes"] or 0, "publicacion": i}
                         for i, p in enumerate(publicaciones, start=1) for c in p["comentarios"]]
    descripciones = [p["descripcion"] for p in publicaciones if p["descripcion"]]
    col_negocio, col_bigfive = st.columns(2)
    quiere_negocio = col_negocio.button("📈 Analizar comentarios", type="primary", disabled=es_demo,
                                        use_container_width=True,
                                        help="Clasifica cada comentario (sentimiento, tipo y tema) con el modelo local.")
    quiere_bigfive = col_bigfive.button("🧠 Analizar Big Five", disabled=es_demo, use_container_width=True,
                                        help="Perfil de la audiencia y del creador. Solo con datos reales.")
    sin_comentarios = "Tip: marca «Incluir comentarios» y vuelve a consultar para tener textos que analizar."
 
    if quiere_negocio:
        try:
            with st.status("Clasificando comentarios con el modelo local… puede tardar varios minutos.",
                           expanded=True) as estado:
                barra = st.progress(0.0)
                clasificados, aviso = clasificar_comentarios(comentarios_ricos, modelo, marca,
                                                             progreso=lambda hechos, total: barra.progress(hechos / total))
                estadisticas = calcular_estadisticas(clasificados)
                estado.update(label="Clasificación terminada", state="complete", expanded=False)
            st.session_state["negocio"] = {"estadisticas": estadisticas, "resumen": armar_resumen(estadisticas),
                                           "recomendaciones": generar_recomendaciones(estadisticas),
                                           "aviso": aviso, "modelo": modelo, "marca": marca.strip()}
        except ErrorAnalisis as error:
            st.error(str(error))
            if not comentarios:
                st.caption(sin_comentarios)
 
    if quiere_bigfive:
        try:
            with st.status("Analizando con el modelo local… puede tardar de 1 a 3 minutos.",
                           expanded=True) as estado:
                st.write("Analizando la audiencia (comentarios)…")
                audiencia = analizar(comentarios, "audiencia", modelo)
                creador = None
                if len(preparar_textos(descripciones)) >= 3:
                    st.write("Analizando al creador (descripciones)…")
                    creador = analizar(descripciones, "creador", modelo)
                estado.update(label="Análisis terminado", state="complete", expanded=False)
            st.session_state["analisis"] = {"audiencia": audiencia, "creador": creador}
        except ErrorAnalisis as error:
            st.error(str(error))
            if not comentarios:
                st.caption(sin_comentarios)
    if es_demo:
        st.caption("El análisis de comentarios y el Big Five solo están disponibles con datos reales.")
 
    negocio, bigfive = st.session_state.get("negocio"), st.session_state.get("analisis")
    if negocio or bigfive:
        st.subheader("📊 Dashboard")
        pestanas = st.tabs(["📊 Resumen", "🧩 Temas", "👍 Elogios y quejas", "❓ Preguntas",
                            "💡 Recomendaciones", "🧠 Big Five"])
        for pestana, mostrar, datos in zip(pestanas, (mostrar_resumen, mostrar_temas, mostrar_opiniones,
                                                      mostrar_preguntas, mostrar_recomendaciones, mostrar_bigfive),
                                           (negocio,) * 5 + (bigfive,)):
            with pestana:
                mostrar(datos)
 
    st.divider()
    st.subheader("📱 Publicaciones")
    for numero, publicacion in enumerate(resultado["publicaciones"], start=1):
        mostrar_publicacion(publicacion, numero, demo=es_demo)
 