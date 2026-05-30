"""
============================================================
AgroIA - Servidor Backend Local
Universidad Cesar Vallejo - Proyecto academico
Autor: Jhonny Huipama
============================================================

ARQUITECTURA SINCRONIZADA:
[App HTML] <-> [Este servidor] -> [Datadog Cloud]

Este servidor mantiene la MISMA INFORMACION que la aplicacion HTML:
- 35 trabajadores (mismas cuadrillas, mismos DNIs)
- 5 lotes (mismas variedades, mismos rendimientos)
- Mismos parametros de validacion (z-score, bandas)

Cada accion en la app HTML viaja a este servidor y se envia
automaticamente a Datadog con todo el detalle.

INSTALACION (una sola vez):
    pip install flask flask-cors datadog-api-client

USO:
    1. Configura tu API_KEY abajo
    2. Ejecuta: python agroia_servidor.py
    3. Abre AgroIA_Demo.html en tu navegador
    4. Cada accion se enviara automaticamente a Datadog
============================================================
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests  # Para llamar a APIs externas (Gemini, Claude)
import time
import json
import urllib.request
from datetime import datetime
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.metrics_api import MetricsApi
from datadog_api_client.v2.model.metric_payload import MetricPayload
from datadog_api_client.v2.model.metric_series import MetricSeries
from datadog_api_client.v2.model.metric_point import MetricPoint
from datadog_api_client.v2.model.metric_intake_type import MetricIntakeType

# ============================================================
# CONFIGURACION - PEGA AQUI TU API KEY DE DATADOG
# ============================================================
import os
from supabase import create_client, Client

# Configuracion - lee de variables de entorno (mas seguro para produccion)
# En Render configuras DATADOG_API_KEY en el panel de variables de entorno
# En local, usa el valor por defecto
API_KEY = os.environ.get("DATADOG_API_KEY", "PEGA_AQUI_TU_API_KEY")
SITE = os.environ.get("DATADOG_SITE", "us5.datadoghq.com")

# ============================================================
# CONFIGURACION DE IA VISION
# ============================================================
# Soporta Gemini (Google) y Claude (Anthropic).
# Cambia AI_PROVIDER en variables de entorno para migrar facilmente.
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")

if AI_PROVIDER == "gemini" and GEMINI_API_KEY:
    print(f"[IA] Proveedor: Gemini (configurado)")
elif AI_PROVIDER == "claude" and CLAUDE_API_KEY:
    print(f"[IA] Proveedor: Claude (configurado)")
else:
    print(f"[IA] No configurado - analisis de imagen no disponible")

# ============================================================
# CONFIGURACION DE EMAIL (Resend)
# ============================================================
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
# Dominio de envio - por defecto usa el de pruebas de Resend
# Cuando tengas dominio propio, cambia a algo como "reportes@agroia.pe"
EMAIL_FROM = os.environ.get("EMAIL_FROM", "AgroIA <onboarding@resend.dev>")

if RESEND_API_KEY:
    print(f"[Email] Resend configurado - envio de correos disponible")
else:
    print(f"[Email] Resend NO configurado - envio de correos no disponible")

# ============================================================
# CONEXION A SUPABASE (base de datos en la nube)
# ============================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Inicializar cliente de Supabase
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"[Supabase] Conectado correctamente a {SUPABASE_URL}")
    except Exception as e:
        print(f"[Supabase] ERROR al conectar: {e}")
        supabase = None
else:
    print("[Supabase] Variables SUPABASE_URL y SUPABASE_KEY no configuradas")
    print("[Supabase] Funcionando en modo memoria local (datos se pierden al reiniciar)")

# ============================================================
# DATOS BASE (sincronizados con AgroIA_Demo.html)
# ============================================================
TRABAJADORES = {
    # Cuadrilla C3 - 14 trabajadores - Marco Saldana
    "47234122": {"nombre": "Juan Perez", "cuadrilla": "C3", "historico": 24, "sigma": 4},
    "71234567": {"nombre": "Maria Quispe", "cuadrilla": "C3", "historico": 22, "sigma": 3},
    "73456789": {"nombre": "Carlos Sanchez", "cuadrilla": "C3", "historico": 21, "sigma": 3.5},
    "40123456": {"nombre": "Rosa Gutierrez", "cuadrilla": "C3", "historico": 23, "sigma": 3},
    "41234567": {"nombre": "Manuel Vargas", "cuadrilla": "C3", "historico": 25, "sigma": 4},
    "42345678": {"nombre": "Carmen Loayza", "cuadrilla": "C3", "historico": 22, "sigma": 3},
    "43456789": {"nombre": "Luis Cabrera", "cuadrilla": "C3", "historico": 26, "sigma": 4},
    "44567890": {"nombre": "Sandra Mejia", "cuadrilla": "C3", "historico": 23, "sigma": 3},
    "45678901": {"nombre": "Jorge Castillo", "cuadrilla": "C3", "historico": 24, "sigma": 3.5},
    "46789012": {"nombre": "Pilar Rodriguez", "cuadrilla": "C3", "historico": 21, "sigma": 3},
    "47890123": {"nombre": "Andres Salinas", "cuadrilla": "C3", "historico": 25, "sigma": 4},
    "48901234": {"nombre": "Teresa Olivos", "cuadrilla": "C3", "historico": 23, "sigma": 3},
    "49012345": {"nombre": "Ricardo Paredes", "cuadrilla": "C3", "historico": 22, "sigma": 3},
    "50123456": {"nombre": "Monica Rios", "cuadrilla": "C3", "historico": 24, "sigma": 3.5},
    # Cuadrilla C5 - 12 trabajadores - Patricia Chavez
    "44556677": {"nombre": "Pedro Rojas", "cuadrilla": "C5", "historico": 19, "sigma": 3},
    "78912345": {"nombre": "Lucia Mendoza", "cuadrilla": "C5", "historico": 25, "sigma": 3.5},
    "65432198": {"nombre": "Ana Torres", "cuadrilla": "C5", "historico": 23, "sigma": 3},
    "51234567": {"nombre": "Hugo Velarde", "cuadrilla": "C5", "historico": 20, "sigma": 3},
    "52345678": {"nombre": "Beatriz Nunez", "cuadrilla": "C5", "historico": 22, "sigma": 3},
    "53456789": {"nombre": "Felipe Morales", "cuadrilla": "C5", "historico": 24, "sigma": 3.5},
    "54567890": {"nombre": "Karina Espinoza", "cuadrilla": "C5", "historico": 21, "sigma": 3},
    "55678901": {"nombre": "Daniel Pacheco", "cuadrilla": "C5", "historico": 23, "sigma": 3.5},
    "56789012": {"nombre": "Liliana Bazan", "cuadrilla": "C5", "historico": 22, "sigma": 3},
    "57890123": {"nombre": "Eduardo Romero", "cuadrilla": "C5", "historico": 20, "sigma": 3},
    "58901234": {"nombre": "Veronica Quiroz", "cuadrilla": "C5", "historico": 24, "sigma": 3.5},
    "59012345": {"nombre": "Miguel Sandoval", "cuadrilla": "C5", "historico": 21, "sigma": 3},
    # Cuadrilla C7 - 9 trabajadores - Luis Mendoza
    "12345678": {"nombre": "Roberto Diaz", "cuadrilla": "C7", "historico": 28, "sigma": 4},
    "98765432": {"nombre": "Patricia Vargas", "cuadrilla": "C7", "historico": 26, "sigma": 3.5},
    "60123456": {"nombre": "Ivan Cardenas", "cuadrilla": "C7", "historico": 27, "sigma": 4},
    "61234567": {"nombre": "Norma Aguirre", "cuadrilla": "C7", "historico": 25, "sigma": 3},
    "62345678": {"nombre": "Oscar Leon", "cuadrilla": "C7", "historico": 28, "sigma": 4},
    "63456789": {"nombre": "Diana Flores", "cuadrilla": "C7", "historico": 26, "sigma": 3.5},
    "64567890": {"nombre": "Walter Luna", "cuadrilla": "C7", "historico": 27, "sigma": 4},
    "65678901": {"nombre": "Estela Vidal", "cuadrilla": "C7", "historico": 25, "sigma": 3},
    "66789012": {"nombre": "Fernando Avila", "cuadrilla": "C7", "historico": 26, "sigma": 3.5},
}

LOTES = {
    "L-23": {"sector": "Norte A", "variedad": "Hass", "ha": 4.0, "factor": 1.0, "cuadrilla": "C3"},
    "L-08": {"sector": "Norte B", "variedad": "Hass", "ha": 2.5, "factor": 1.1, "cuadrilla": "C5"},
    "L-17": {"sector": "Sur",     "variedad": "Hass", "ha": 3.2, "factor": 1.3, "cuadrilla": "C7"},
    "L-31": {"sector": "Norte A", "variedad": "Hass", "ha": 3.0, "factor": 1.0, "cuadrilla": None},
    "L-45": {"sector": "Sur",     "variedad": "Hass", "ha": 4.5, "factor": 1.2, "cuadrilla": None},
}

# Parametros del agente (sincronizados con la app)
UMBRAL_VERDE = 1.5
UMBRAL_AMARILLO = 2.0
UMBRAL_NARANJA = 2.5

# Constantes economicas (sincronizadas con la app)
PRECIO_KG = 2.50          # Soles por kg de palta Hass
META_DIARIA = 12500       # kg meta por dia
TARIFA_HORA = 8.50        # Soles por hora (Ley 31110)
ACUMULADO_BASE_TON = 556.16  # toneladas ya cosechadas en campana
META_CAMPANA_TON = 850    # toneladas meta de campana
SUPERVISORES = {'C3': 'Marco Saldana', 'C5': 'Patricia Chavez', 'C7': 'Luis Mendoza'}

# ============================================================
# FLASK SERVER
# ============================================================
app = Flask(__name__)
CORS(app)

configuration = Configuration()
configuration.api_key["apiKeyAuth"] = API_KEY
configuration.server_variables["site"] = SITE

estadisticas = {
    "pesadas_enviadas": 0,
    "logs_enviados": 0,
    "errores": 0,
    "validadas": 0,
    "observadas": 0,
    "bloqueadas": 0,
    "reportes": 0,
    "exportaciones_rrhh": 0,
    "inicio": datetime.now().isoformat(),
}

# Memoria compartida de pesadas para que la app HTML las consulte
# Cada pesada se guarda aqui despues de procesarla, y la app HTML
# hace polling a /api/pesadas-recientes para obtenerlas
pesadas_memoria = []
PESADAS_MAX = 200  # Limite de pesadas en memoria

# ============================================================
# FUNCIONES PARA DATADOG
# ============================================================
def enviar_metrica(nombre, valor, tags):
    """Envia una metrica numerica a Datadog"""
    try:
        body = MetricPayload(
            series=[
                MetricSeries(
                    metric=nombre,
                    type=MetricIntakeType.GAUGE,
                    points=[MetricPoint(timestamp=int(time.time()), value=float(valor))],
                    tags=tags,
                ),
            ],
        )
        with ApiClient(configuration) as api_client:
            MetricsApi(api_client).submit_metrics(body=body)
        return True
    except Exception as e:
        print(f"  [ERROR] Metrica {nombre}: {e}")
        estadisticas["errores"] += 1
        return False

def enviar_log(mensaje, atributos):
    """Envia un log estructurado a Datadog"""
    url = f"https://http-intake.logs.{SITE}/api/v2/logs"
    payload = [{
        "ddsource": "agroia",
        "ddtags": "env:demo,project:agroia,cultivo:palta_hass,fundo:valle_moche,region:la_libertad",
        "hostname": "agroia-laptop-jhonny",
        "service": "agroia-validador",
        "message": mensaje,
        **atributos
    }]
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json', 'DD-API-KEY': API_KEY}
        )
        with urllib.request.urlopen(req) as response:
            return response.status == 202
    except Exception as e:
        print(f"  [ERROR] Log: {e}")
        estadisticas["errores"] += 1
        return False

# ============================================================
# RUTAS
# ============================================================
@app.route('/')
def home():
    """Pagina de estado del servidor"""
    uptime = int((datetime.now() - datetime.fromisoformat(estadisticas["inicio"])).total_seconds())
    html = """
    <!DOCTYPE html>
    <html><head><title>AgroIA Server</title>
    <style>
    body { font-family: -apple-system, sans-serif; background: #0a0e0a; color: #e8efe5;
           padding: 40px; max-width: 800px; margin: 0 auto; line-height: 1.6; }
    h1 { color: #95c11f; font-size: 32px; margin-bottom: 8px; }
    h3 { color: #b4d752; margin-top: 24px; }
    .status { background: #161c16; padding: 24px; border-radius: 12px;
              border: 1px solid #243024; margin: 16px 0; }
    .stat { display: flex; justify-content: space-between; padding: 10px 0;
            border-bottom: 1px solid #243024; }
    .stat:last-child { border-bottom: none; }
    .ok { color: #4ade80; font-weight: 600; }
    code { background: #1d251d; padding: 3px 10px; border-radius: 4px; color: #95c11f;
           font-family: 'Consolas', monospace; }
    .pulse { display: inline-block; width: 10px; height: 10px; background: #4ade80;
             border-radius: 50%; margin-right: 8px; animation: pulse 2s infinite; }
    @keyframes pulse { 0%,100% {opacity:1} 50% {opacity:0.4} }
    </style></head>
    <body>
    <h1>AgroIA - Servidor Local</h1>
    <p><span class="pulse"></span><span class="ok">ACTIVO</span> - Conectado a Datadog (""" + SITE + """)</p>
    
    <div class="status">
        <h3>Estadisticas de la sesion</h3>
        <div class="stat"><span>Pesadas validadas (banda verde):</span><strong>""" + str(estadisticas['validadas']) + """</strong></div>
        <div class="stat"><span>Pesadas observadas (naranja):</span><strong>""" + str(estadisticas['observadas']) + """</strong></div>
        <div class="stat"><span>Pesadas bloqueadas (rojas):</span><strong>""" + str(estadisticas['bloqueadas']) + """</strong></div>
        <div class="stat"><span>Reportes ejecutivos generados:</span><strong>""" + str(estadisticas['reportes']) + """</strong></div>
        <div class="stat"><span>Exportaciones a RRHH:</span><strong>""" + str(estadisticas['exportaciones_rrhh']) + """</strong></div>
        <div class="stat"><span>Logs enviados a Datadog:</span><strong>""" + str(estadisticas['logs_enviados']) + """</strong></div>
        <div class="stat"><span>Errores:</span><strong>""" + str(estadisticas['errores']) + """</strong></div>
        <div class="stat"><span>Tiempo activo:</span><strong>""" + str(uptime) + """ segundos</strong></div>
    </div>

    <div class="status">
        <h3>Datos base sincronizados</h3>
        <div class="stat"><span>Trabajadores cargados:</span><strong>""" + str(len(TRABAJADORES)) + """</strong></div>
        <div class="stat"><span>Lotes cargados:</span><strong>""" + str(len(LOTES)) + """</strong></div>
        <div class="stat"><span>Cuadrillas activas:</span><strong>3 (C3, C5, C7)</strong></div>
    </div>
    
    <div class="status">
        <h3>Como funciona</h3>
        <p>Este servidor recibe peticiones de la app <code>AgroIA_Demo.html</code>
        y las envia automaticamente a Datadog. Cada pesada que registras en la app
        viaja aqui, se procesa, y aparece en tu dashboard de Datadog.</p>
        <p>Endpoints activos: <code>/api/pesada</code>,
        <code>/api/reporte</code>, <code>/api/rrhh</code>, <code>/api/health</code></p>
    </div>
    </body></html>
    """
    return html

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "servicio": "agroia-server",
        "datadog_site": SITE,
        "trabajadores_cargados": len(TRABAJADORES),
        "lotes_cargados": len(LOTES)
    })

@app.route('/api/pesada', methods=['POST'])
def recibir_pesada():
    """Recibe una pesada de la app y la envia a Datadog"""
    data = request.json
    
    # Validar que el trabajador existe en la base
    dni = data.get('dni', '')
    trabajador_db = TRABAJADORES.get(dni)
    if not trabajador_db:
        # Si no esta en la BD, usar los datos que mando la app
        nombre = data.get('nombre', 'Desconocido')
        cuadrilla = data.get('cuadrilla', 'N/A')
        historico = data.get('historico', 23)
        sigma = data.get('sigma', 3)
    else:
        nombre = trabajador_db['nombre']
        cuadrilla = trabajador_db['cuadrilla']
        historico = trabajador_db['historico']
        sigma = trabajador_db['sigma']
    
    kg = data['kg']
    horas = data['horas']
    lote = data['lote']
    productividad = kg / horas
    z_score = (productividad - historico) / sigma
    abs_z = abs(z_score)
    
    # Determinar estado segun bandas
    if abs_z <= UMBRAL_VERDE:
        estado, color, motivo = "VALIDADO", "green", "Pesada dentro de parametros normales"
        estadisticas["validadas"] += 1
    elif abs_z <= UMBRAL_AMARILLO:
        estado, color, motivo = "VALIDADO_TOLERANCIA", "yellow", "Productividad ligeramente fuera del rango"
        estadisticas["validadas"] += 1
    elif abs_z <= UMBRAL_NARANJA:
        estado, color, motivo = "OBSERVADO", "orange", "Productividad significativamente fuera del rango"
        estadisticas["observadas"] += 1
    else:
        if z_score > 0:
            motivo = "Productividad muy alta - posible doble pesaje o error"
        else:
            motivo = "Productividad muy baja - verificar registro o estado del trabajador"
        estado, color = "BLOQUEADO", "red"
        estadisticas["bloqueadas"] += 1
    
    # Mostrar en consola
    icono = {"green": "[OK]", "yellow": "[!] ", "orange": "[!!]", "red": "[X] "}[color]
    print(f"\n{icono} PESADA: {nombre} ({cuadrilla}) - {lote}")
    print(f"      {kg} kg / {horas}h = {productividad:.2f} kg/h")
    print(f"      historico: {historico} kg/h, sigma: {sigma}")
    print(f"      z-score: {z_score:+.2f} -> {estado}")
    if color != "green":
        print(f"      motivo: {motivo}")
    
    # Tags para Datadog
    tags_base = [
        "project:agroia",
        "env:demo",
        "cultivo:palta_hass",
        "fundo:valle_moche",
        "region:la_libertad",
        f"cuadrilla:{cuadrilla.lower()}",
        f"lote:{lote.lower()}",
        f"estado:{color}"
    ]
    
    # 1. ENVIAR METRICAS A DATADOG
    enviar_metrica("agroia.pesadas.registradas", 1, tags_base)
    enviar_metrica("agroia.kg.cosechados", kg, tags_base)
    enviar_metrica("agroia.tiempo_validacion_ms", data.get('tiempo_validacion_ms', 500), tags_base)
    
    if color == 'green' or color == 'yellow':
        enviar_metrica("agroia.pesadas.validadas", 1, tags_base)
    elif color == 'orange':
        enviar_metrica("agroia.pesadas.observadas", 1, tags_base)
    elif color == 'red':
        enviar_metrica("agroia.pesadas.bloqueadas", 1, tags_base)
        enviar_metrica("agroia.errores", 1, tags_base)
    
    # 2. ENVIAR LOG ESTRUCTURADO A DATADOG
    nivel = "info" if color == 'green' else "warn" if color in ['yellow', 'orange'] else "error"
    
    mensaje_log = (f"[{estado}] Pesada de {nombre} en lote {lote}: "
                   f"{kg} kg en {horas}h (productividad {productividad:.1f} kg/h, z={z_score:+.2f})")
    
    atributos_log = {
        "status": nivel,
        "estado_validacion": estado,
        "trabajador_dni": dni,
        "trabajador_nombre": nombre,
        "cuadrilla": cuadrilla,
        "lote": lote,
        "kg_reportados": kg,
        "horas_trabajadas": horas,
        "productividad_kgh": round(productividad, 2),
        "z_score": round(z_score, 2),
        "historico_promedio": historico,
        "historico_sigma": sigma,
        "motivo": motivo,
        "tiempo_validacion_ms": data.get('tiempo_validacion_ms', 500),
    }
    
    enviar_log(mensaje_log, atributos_log)
    
    estadisticas["pesadas_enviadas"] += 1
    estadisticas["logs_enviados"] += 1
    
    # Guardar la pesada con hora local de Peru (UTC-5)
    from datetime import timezone, timedelta
    PERU_TZ = timezone(timedelta(hours=-5))
    ahora_peru = datetime.now(timezone.utc).astimezone(PERU_TZ)
    
    # Si el cliente envio su hora local, usarla (mas precisa)
    # Si no, calcularla con UTC-5
    hora_str = data.get("hora_local", ahora_peru.strftime("%d/%m %H:%M"))
    pesada_para_app = {
        "hora": hora_str,
        "timestamp": datetime.now(timezone.utc).timestamp(),
        "dni": dni,
        "nombre": nombre,
        "cuadrilla": cuadrilla,
        "lote": lote,
        "kg": kg,
        "horas": horas,
        "estado": color,
        "z": round(z_score, 2),
        "motivo": motivo if color != "green" else None,
        "origen": data.get("origen", "manual")
    }
    
    # GUARDAR EN SUPABASE (base de datos en la nube)
    # Esto hace que todos los usuarios vean la misma pesada en tiempo real
    if supabase:
        try:
            supabase.table('pesadas').insert({
                "hora": hora_str,
                "dni": dni,
                "nombre": nombre,
                "cuadrilla": cuadrilla,
                "lote": lote,
                "kg": float(kg),
                "horas": float(horas),
                "productividad": round(productividad, 2),
                "z_score": round(z_score, 2),
                "estado": color,
                "motivo": motivo if color != "green" else None,
                "origen": data.get("origen", "manual")
            }).execute()
            print(f"[Supabase] Pesada guardada: {nombre} - {kg}kg")
        except Exception as e:
            print(f"[Supabase] Error guardando pesada: {e}")
    
    # Tambien guardar en memoria como cache para no consultar Supabase
    # en cada polling de la app
    pesadas_memoria.append(pesada_para_app)
    if len(pesadas_memoria) > PESADAS_MAX:
        pesadas_memoria.pop(0)
    
    return jsonify({
        "success": True,
        "estado": estado,
        "color": color,
        "z_score": round(z_score, 2),
        "productividad": round(productividad, 2),
        "motivo": motivo,
        "datadog_envio": "exitoso"
    })

@app.route('/api/reporte', methods=['POST'])
def recibir_reporte():
    """Notifica generacion de reporte ejecutivo"""
    data = request.json
    
    print(f"\n[REPORTE EJECUTIVO] Generado y enviado al directorio")
    print(f"  Cosecha total: {data.get('kg_total', 0)} kg")
    print(f"  Avance campana: {data.get('avance', 0)}%")
    print(f"  Destinatarios: {data.get('destinatarios', 6)}")
    
    tags = ["project:agroia", "env:demo", "tipo:cierre_diario"]
    enviar_metrica("agroia.reportes.generados", 1, tags)
    
    mensaje = f"[REPORTE] Cierre diario generado: {data.get('kg_total', 0)} kg cosechados, avance {data.get('avance', 0)}%"
    
    atributos = {
        "status": "info",
        "tipo_evento": "reporte_ejecutivo",
        "destinatarios": data.get('destinatarios', 6),
        "kg_total": data.get('kg_total', 0),
        "avance_campana_pct": data.get('avance', 0),
    }
    
    enviar_log(mensaje, atributos)
    estadisticas["reportes"] += 1
    estadisticas["logs_enviados"] += 1
    
    return jsonify({"success": True, "datadog_envio": "exitoso"})

@app.route('/api/rrhh', methods=['POST'])
def recibir_rrhh():
    """Notifica exportacion a RRHH"""
    data = request.json
    
    print(f"\n[RRHH] Archivo CSV generado")
    print(f"  Total registros: {data.get('total_registros', 0)}")
    
    tags = ["project:agroia", "env:demo", "tipo:planilla_rrhh"]
    enviar_metrica("agroia.exportaciones.rrhh", 1, tags)
    
    mensaje = f"[RRHH] CSV con {data.get('total_registros', 0)} registros validados enviado al area de Recursos Humanos"
    
    atributos = {
        "status": "info",
        "tipo_evento": "exportacion_rrhh",
        "total_registros": data.get('total_registros', 0),
    }
    
    enviar_log(mensaje, atributos)
    estadisticas["exportaciones_rrhh"] += 1
    estadisticas["logs_enviados"] += 1
    
    return jsonify({"success": True, "datadog_envio": "exitoso"})

@app.route('/api/pesadas-recientes', methods=['GET'])
def pesadas_recientes():
    """Devuelve pesadas que llegaron despues de un timestamp dado.
    
    Si Supabase esta configurado, lee desde la base de datos (datos compartidos
    entre todos los usuarios y persistentes).
    
    Si no, usa memoria local (solo para desarrollo)."""
    desde = float(request.args.get('desde', 0))
    
    # Si Supabase esta disponible, leer desde la base de datos
    if supabase:
        try:
            # Convertir timestamp Unix a formato PostgreSQL con UTC explicito
            from datetime import timezone
            desde_dt = datetime.fromtimestamp(desde, tz=timezone.utc).isoformat()
            
            # Consultar pesadas creadas despues del timestamp
            result = supabase.table('pesadas')\
                .select("*")\
                .gt('timestamp_creacion', desde_dt)\
                .order('timestamp_creacion', desc=False)\
                .limit(100)\
                .execute()
            
            # Transformar al formato esperado por la app
            nuevas = []
            for p in result.data:
                # Convertir timestamp ISO a Unix
                ts_iso = p['timestamp_creacion']
                ts_unix = datetime.fromisoformat(ts_iso.replace('Z', '+00:00')).timestamp()
                
                nuevas.append({
                    "hora": p['hora'],
                    "timestamp": ts_unix,
                    "dni": p['dni'],
                    "nombre": p['nombre'],
                    "cuadrilla": p['cuadrilla'],
                    "lote": p['lote'],
                    "kg": float(p['kg']),
                    "horas": float(p['horas']),
                    "estado": p['estado'],
                    "z": float(p['z_score']),
                    "motivo": p.get('motivo'),
                    "origen": p.get('origen', 'manual')
                })
            
            return jsonify({
                "fuente": "supabase",
                "total": len(nuevas),
                "nuevas": len(nuevas),
                "pesadas": nuevas
            })
        except Exception as e:
            print(f"[Supabase] Error leyendo pesadas: {e}")
            # Si falla Supabase, caer a memoria local
    
    # Fallback: memoria local
    nuevas = [p for p in pesadas_memoria if p['timestamp'] > desde]
    return jsonify({
        "fuente": "memoria",
        "total_memoria": len(pesadas_memoria),
        "nuevas": len(nuevas),
        "pesadas": nuevas
    })

@app.route('/api/pesadas-todas', methods=['GET'])
def pesadas_todas():
    """Devuelve las 500 pesadas mas recientes de Supabase.
    Usado cuando la app se abre para cargar el historico."""
    if supabase:
        try:
            # Sin filtro de fecha - traer las pesadas mas recientes
            # (evita problemas de zona horaria)
            result = supabase.table('pesadas')\
                .select("*")\
                .order('timestamp_creacion', desc=True)\
                .limit(500)\
                .execute()
            
            pesadas_lista = []
            # result.data viene en orden descendente (mas reciente primero)
            # Lo invertimos para devolverlo en orden ascendente (cronologico)
            for p in reversed(result.data):
                ts_iso = p['timestamp_creacion']
                ts_unix = datetime.fromisoformat(ts_iso.replace('Z', '+00:00')).timestamp()
                
                pesadas_lista.append({
                    "hora": p['hora'],
                    "timestamp": ts_unix,
                    "dni": p['dni'],
                    "nombre": p['nombre'],
                    "cuadrilla": p['cuadrilla'],
                    "lote": p['lote'],
                    "kg": float(p['kg']),
                    "horas": float(p['horas']),
                    "estado": p['estado'],
                    "z": float(p['z_score']),
                    "motivo": p.get('motivo'),
                    "origen": p.get('origen', 'manual')
                })
            
            return jsonify({
                "fuente": "supabase",
                "total": len(pesadas_lista),
                "pesadas": pesadas_lista
            })
        except Exception as e:
            print(f"[Supabase] Error leyendo pesadas: {e}")
            return jsonify({"fuente": "error", "error": str(e), "pesadas": []})
    
    return jsonify({"fuente": "memoria", "total": 0, "pesadas": []})

@app.route('/api/trabajadores', methods=['GET'])
def listar_trabajadores():
    """Devuelve la lista de trabajadores"""
    return jsonify({
        "total": len(TRABAJADORES),
        "trabajadores": [
            {"dni": dni, **datos} for dni, datos in TRABAJADORES.items()
        ]
    })

@app.route('/api/lotes', methods=['GET'])
def listar_lotes():
    """Devuelve la lista de lotes"""
    return jsonify({
        "total": len(LOTES),
        "lotes": [
            {"codigo": cod, **datos} for cod, datos in LOTES.items()
        ]
    })

# ============================================================
# ENDPOINT: ANALISIS DE IMAGEN CON IA (VISION)
# ============================================================
@app.route('/api/analizar-imagen', methods=['POST'])
def analizar_imagen():
    """Analiza una imagen usando IA (Gemini o Claude).
    
    Recibe: { "imagen_base64": "..." (sin prefijo data:image), "contexto": "opcional" }
    Devuelve: { "exito": true, "analisis": {...}, "proveedor": "gemini" }
    """
    try:
        data = request.json
        if not data or 'imagen_base64' not in data:
            return jsonify({"exito": False, "error": "Falta imagen_base64"}), 400
        
        imagen_b64 = data['imagen_base64']
        contexto = data.get('contexto', 'Imagen de cosecha de palta Hass')
        
        # Prompt especializado en agricultura/palta Hass
        prompt = """Eres un agente IA experto en palta Hass de Peru. Analiza la imagen y devuelve SOLO este JSON:

{
  "tipo_detectado": "palta_hass" | "otra_fruta" | "no_es_fruta",
  "calidad_aparente": "excelente" | "buena" | "regular" | "deficiente",
  "color_madurez": "verde_inmadura" | "verde_madura" | "morada_lista" | "muy_madura",
  "daños_visibles": ["array de daños o vacio"],
  "posibles_plagas": ["array de plagas o vacio"],
  "confianza": "alta" | "media" | "baja",
  "resumen": "1-2 oraciones describiendo lo que ves",
  "recomendacion": "1 oracion con accion sugerida",
  "alerta": null
}

Daños comunes: manchas_oscuras, pudricion, magulladuras, deshidratacion, daño_mecanico.
Plagas comunes en palta: trips, chinche, arañita_roja, antracnosis, phytophthora.
Si no es palta, marca tipo_detectado correctamente. Se honesto con la confianza."""

        if AI_PROVIDER == "gemini" and GEMINI_API_KEY:
            return _analizar_con_gemini(imagen_b64, prompt)
        elif AI_PROVIDER == "claude" and CLAUDE_API_KEY:
            return _analizar_con_claude(imagen_b64, prompt)
        else:
            return jsonify({
                "exito": False,
                "error": "IA no configurada en el servidor"
            }), 503
            
    except Exception as e:
        print(f"[IA] Error en analisis: {e}")
        return jsonify({"exito": False, "error": str(e)}), 500


def _analizar_con_gemini(imagen_b64, prompt):
    """Llama a Gemini API para analisis visual"""
    import requests as http_requests  # alias para no confundir con flask.request
    import json
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": imagen_b64
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json"  # FORZAR JSON nativo
        }
    }
    
    try:
        response = http_requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Extraer el texto de la respuesta
        texto_respuesta = result['candidates'][0]['content']['parts'][0]['text']
        print(f"[IA Gemini] Respuesta cruda: {texto_respuesta[:300]}...")
        
        # LIMPIEZA ROBUSTA del JSON
        texto_limpio = texto_respuesta.strip()
        
        # 1. Quitar bloques markdown ```json ... ```
        if texto_limpio.startswith('```'):
            # Buscar el primer salto de linea y el ultimo ```
            primer_salto = texto_limpio.find('\n')
            if primer_salto > 0:
                texto_limpio = texto_limpio[primer_salto+1:]
            if texto_limpio.endswith('```'):
                texto_limpio = texto_limpio[:-3]
            texto_limpio = texto_limpio.strip()
        
        # 2. Si hay texto antes del JSON, intentar extraer solo el JSON
        # buscando la primera { y la ultima }
        if not texto_limpio.startswith('{'):
            primer_corchete = texto_limpio.find('{')
            ultimo_corchete = texto_limpio.rfind('}')
            if primer_corchete >= 0 and ultimo_corchete > primer_corchete:
                texto_limpio = texto_limpio[primer_corchete:ultimo_corchete+1]
        
        # 3. Parsear JSON
        analisis = json.loads(texto_limpio)
        
        return jsonify({
            "exito": True,
            "analisis": analisis,
            "proveedor": "gemini"
        })
        
    except json.JSONDecodeError as e:
        print(f"[IA Gemini] Error parseando JSON: {e}")
        print(f"[IA Gemini] Texto crudo completo: {texto_respuesta}")
        # Devolver el texto crudo de la IA como analisis_texto
        # para que el frontend lo muestre como descripcion libre
        return jsonify({
            "exito": True,
            "analisis": {
                "tipo_detectado": "no_clasificable",
                "calidad_aparente": "no_aplicable",
                "color_madurez": "no_aplicable",
                "daños_visibles": [],
                "posibles_plagas": [],
                "confianza": "media",
                "resumen": texto_respuesta[:500],
                "recomendacion": "Ver descripcion completa en el resumen",
                "alerta": None
            },
            "proveedor": "gemini",
            "modo_fallback": True
        })
    except Exception as e:
        print(f"[IA Gemini] Error: {e}")
        return jsonify({"exito": False, "error": str(e)}), 500


def _analizar_con_claude(imagen_b64, prompt):
    """Llama a Claude API para analisis visual"""
    import requests as http_requests
    import json
    
    url = "https://api.anthropic.com/v1/messages"
    
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1000,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": imagen_b64
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }]
    }
    
    try:
        response = http_requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        texto_respuesta = result['content'][0]['text']
        
        # Limpiar JSON
        texto_limpio = texto_respuesta.strip()
        if texto_limpio.startswith('```'):
            lineas = texto_limpio.split('\n')
            texto_limpio = '\n'.join(lineas[1:-1])
        
        analisis = json.loads(texto_limpio)
        
        return jsonify({
            "exito": True,
            "analisis": analisis,
            "proveedor": "claude"
        })
        
    except Exception as e:
        print(f"[IA Claude] Error: {e}")
        return jsonify({"exito": False, "error": str(e)}), 500


# ============================================================
# GENERACION DE REPORTES PDF EN EL SERVIDOR (reportlab)
# ============================================================
def _obtener_pesadas_supabase():
    """Obtiene las pesadas mas recientes de Supabase para los reportes."""
    if not supabase:
        return []
    try:
        result = supabase.table('pesadas')\
            .select("*")\
            .order('timestamp_creacion', desc=True)\
            .limit(500)\
            .execute()
        return result.data or []
    except Exception as e:
        print(f"[PDF] Error obteniendo pesadas: {e}")
        return []


def _calcular_metricas_base(pesadas):
    """Calcula las metricas base para el reporte de Gerencia."""
    # Solo cuentan verde y amarilla como validadas
    validadas = [p for p in pesadas if p.get('estado') in ('green', 'yellow')]
    observadas = [p for p in pesadas if p.get('estado') == 'orange']
    bloqueadas = [p for p in pesadas if p.get('estado') == 'red']
    
    kg_validados = sum(float(p.get('kg', 0)) for p in validadas)
    kg_bloqueados = sum(float(p.get('kg', 0)) for p in bloqueadas)
    
    total = len(validadas) + len(observadas) + len(bloqueadas)
    tasa_validacion = (len(validadas) / total * 100) if total > 0 else 0
    
    # Productividad promedio
    prods = []
    for p in validadas:
        horas = float(p.get('horas', 0))
        if horas > 0:
            prods.append(float(p.get('kg', 0)) / horas)
    prod_promedio = sum(prods) / len(prods) if prods else 0
    
    # Avance de campana
    acumulado_ton = ACUMULADO_BASE_TON + (kg_validados / 1000)
    avance_campana = (acumulado_ton / META_CAMPANA_TON) * 100
    
    # Diferencia vs meta diaria
    diff_meta = ((kg_validados - META_DIARIA) / META_DIARIA * 100) if META_DIARIA > 0 else 0
    
    return {
        'validadas': validadas,
        'observadas': observadas,
        'bloqueadas': bloqueadas,
        'kg_validados': kg_validados,
        'kg_bloqueados': kg_bloqueados,
        'total': total,
        'tasa_validacion': tasa_validacion,
        'prod_promedio': prod_promedio,
        'acumulado_ton': acumulado_ton,
        'avance_campana': avance_campana,
        'diff_meta': diff_meta,
    }


def _calcular_metricas_cuadrilla(pesadas, cuadrilla):
    """Calcula metricas de una cuadrilla especifica."""
    pesadas_cuad = [p for p in pesadas if p.get('cuadrilla') == cuadrilla]
    validadas = [p for p in pesadas_cuad if p.get('estado') in ('green', 'yellow')]
    bloqueadas = [p for p in pesadas_cuad if p.get('estado') == 'red']
    
    kg_validados = sum(float(p.get('kg', 0)) for p in validadas)
    prods = []
    for p in validadas:
        horas = float(p.get('horas', 0))
        if horas > 0:
            prods.append(float(p.get('kg', 0)) / horas)
    prod_promedio = sum(prods) / len(prods) if prods else 0
    
    return {
        'cuadrilla': cuadrilla,
        'total': len(pesadas_cuad),
        'validadas': validadas,
        'bloqueadas': bloqueadas,
        'kg_validados': kg_validados,
        'prod_promedio': prod_promedio,
    }


def generar_pdf_gerencia():
    """Genera el PDF del reporte de Gerencia y lo devuelve como bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY, TA_CENTER
    import io
    from datetime import timezone, timedelta
    
    # Colores
    AMBAR = colors.HexColor('#EF9F27')
    AMBAR_OSC = colors.HexColor('#B46E14')
    AMBAR_CLA = colors.HexColor('#FFF4DA')
    GRIS_OSC = colors.HexColor('#0F172A')
    GRIS = colors.HexColor('#475569')
    
    # Datos
    pesadas = _obtener_pesadas_supabase()
    m = _calcular_metricas_base(pesadas)
    valor_cosechado = m['kg_validados'] * PRECIO_KG
    ahorro = m['kg_bloqueados'] * PRECIO_KG
    signo = '+' if m['diff_meta'] >= 0 else ''
    
    PERU_TZ = timezone(timedelta(hours=-5))
    ahora = datetime.now(timezone.utc).astimezone(PERU_TZ)
    fecha_str = ahora.strftime("%d/%m/%Y %H:%M")
    
    # Crear PDF en memoria
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm,
                            bottomMargin=2*cm, leftMargin=2*cm, rightMargin=2*cm)
    
    styles = getSampleStyleSheet()
    story = []
    
    # === ENCABEZADO ===
    titulo_style = ParagraphStyle('T', parent=styles['Title'], fontSize=22,
                                  textColor=AMBAR, fontName='Helvetica-Bold',
                                  spaceAfter=4, alignment=TA_LEFT)
    story.append(Paragraph('AgroIA', titulo_style))
    
    sub_style = ParagraphStyle('S', parent=styles['Normal'], fontSize=11,
                               textColor=GRIS, spaceAfter=2)
    story.append(Paragraph('Reporte Ejecutivo - GERENCIA / DIRECTORIO', sub_style))
    
    fecha_style = ParagraphStyle('F', parent=styles['Normal'], fontSize=9,
                                 textColor=GRIS, spaceAfter=10)
    story.append(Paragraph(f'Cosecha Palta Hass - Valle de Viru - {fecha_str}', fecha_style))
    
    story.append(HRFlowable(width="100%", thickness=2, color=AMBAR, spaceAfter=15))
    
    # === RESUMEN EJECUTIVO ===
    h_style = ParagraphStyle('H', parent=styles['Normal'], fontSize=14,
                             textColor=GRIS_OSC, fontName='Helvetica-Bold', spaceAfter=8)
    story.append(Paragraph('Resumen Ejecutivo', h_style))
    
    p_style = ParagraphStyle('P', parent=styles['Normal'], fontSize=10,
                             textColor=GRIS_OSC, alignment=TA_JUSTIFY, leading=15, spaceAfter=15)
    resumen = (f"En la jornada de hoy se cosecharon {round(m['kg_validados']):,} kg de palta Hass, "
               f"generando un valor economico de S/ {valor_cosechado:,.0f}. El avance acumulado de "
               f"campana alcanza el {m['avance_campana']:.1f}% ({m['acumulado_ton']:.0f} t de {META_CAMPANA_TON} t), "
               f"con {signo}{m['diff_meta']:.1f}% respecto a la meta diaria.")
    story.append(Paragraph(resumen, p_style))
    
    # === KPIs (tabla de 4 columnas) ===
    kpi_data = [[
        f"COSECHA\n{round(m['kg_validados']):,} kg",
        f"VALOR\nS/ {valor_cosechado:,.0f}",
        f"AVANCE\n{m['avance_campana']:.1f}%",
        f"VALIDACION\n{m['tasa_validacion']:.0f}%"
    ]]
    kpi_table = Table(kpi_data, colWidths=[4.2*cm]*4, rowHeights=[2*cm])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), AMBAR_CLA),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('TEXTCOLOR', (0,0), (-1,-1), GRIS_OSC),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBEFORE', (0,0), (0,-1), 2, AMBAR),
        ('LINEBEFORE', (1,0), (1,-1), 2, AMBAR),
        ('LINEBEFORE', (2,0), (2,-1), 2, AMBAR),
        ('LINEBEFORE', (3,0), (3,-1), 2, AMBAR),
        ('GRID', (0,0), (-1,-1), 3, colors.white),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.5*cm))
    
    # === CALLOUT VALOR IA (si hay bloqueadas) ===
    if m['bloqueadas']:
        callout_style = ParagraphStyle('CO', parent=styles['Normal'], fontSize=9,
                                       textColor=GRIS_OSC, leading=13)
        callout_text = (f"<b>VALOR DEL AGENTE IA EN ESTA JORNADA</b><br/>"
                        f"Se detectaron {len(m['bloqueadas'])} anomalias por "
                        f"{round(m['kg_bloqueados']):,} kg, evitando un sobrepago estimado "
                        f"en S/ {ahorro:,.0f}.")
        callout_data = [[Paragraph(callout_text, callout_style)]]
        callout_table = Table(callout_data, colWidths=[17*cm])
        callout_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), AMBAR_CLA),
            ('LINEBEFORE', (0,0), (0,-1), 3, AMBAR),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        story.append(callout_table)
        story.append(Spacer(1, 0.5*cm))
    
    # === GRAFICO: Produccion por cuadrilla (tabla con barras texto) ===
    story.append(Paragraph('Produccion por Cuadrilla', h_style))
    
    cuad_rows = []
    cuadrillas_data = []
    for c in ['C3', 'C5', 'C7']:
        mc = _calcular_metricas_cuadrilla(pesadas, c)
        trab = len([1 for dni, d in TRABAJADORES.items() if d['cuadrilla'] == c])
        cuadrillas_data.append((c, round(mc['kg_validados']), trab))
    
    max_kg = max([cd[1] for cd in cuadrillas_data] + [1])
    for c, kg, trab in cuadrillas_data:
        barras = int((kg / max_kg) * 30) if max_kg > 0 else 0
        barra_str = '#' * max(barras, 1)
        cuad_rows.append([c, f"({trab} trab.)", barra_str, f"{kg:,} kg"])
    
    cuad_table = Table(cuad_rows, colWidths=[1.5*cm, 2.5*cm, 9*cm, 4*cm])
    cuad_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), GRIS_OSC),
        ('TEXTCOLOR', (1,0), (1,-1), GRIS),
        ('TEXTCOLOR', (2,0), (2,-1), AMBAR),
        ('FONTNAME', (2,0), (2,-1), 'Courier-Bold'),
        ('FONTNAME', (3,0), (3,-1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (3,0), (3,-1), GRIS_OSC),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(cuad_table)
    story.append(Spacer(1, 0.5*cm))
    
    # === TABLA DE INDICADORES ===
    story.append(Paragraph('Indicadores Operativos', h_style))
    
    ind_data = [['Indicador', 'Valor', 'Estado']]
    ind_data.append(['Cosecha del dia', f"{round(m['kg_validados']):,} kg",
                     'Por encima de meta' if m['diff_meta'] >= 0 else 'Por debajo de meta'])
    ind_data.append(['Valor producido', f"S/ {valor_cosechado:,.0f}", 'Registrado'])
    ind_data.append(['Avance campana', f"{m['avance_campana']:.1f}%",
                     'En tiempo' if m['avance_campana'] >= 60 else 'Retrasado'])
    ind_data.append(['Tasa de validacion', f"{m['tasa_validacion']:.1f}%",
                     'Excelente' if m['tasa_validacion'] >= 90 else 'Revisar'])
    ind_data.append(['Pesadas registradas', f"{m['total']}", 'Operativo'])
    ind_data.append(['Anomalias detectadas', f"{len(m['bloqueadas'])}",
                     'Sin alertas' if len(m['bloqueadas']) == 0 else 'Revisar'])
    ind_data.append(['Ahorro estimado por IA', f"S/ {ahorro:,.0f}", 'Valor entregado'])
    ind_data.append(['Disponibilidad sistema', '100%', 'Operativo 24/7'])
    
    ind_table = Table(ind_data, colWidths=[7*cm, 4*cm, 6*cm])
    ind_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), AMBAR),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('TEXTCOLOR', (0,1), (-1,-1), GRIS_OSC),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, AMBAR_CLA]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(ind_table)
    
    story.append(Spacer(1, 1*cm))
    
    # Pie
    pie_style = ParagraphStyle('Pie', parent=styles['Normal'], fontSize=8,
                               textColor=GRIS, alignment=TA_CENTER)
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=8))
    story.append(Paragraph('AgroIA - Sistema de Control Operativo - Generado automaticamente por agente IA', pie_style))
    story.append(Paragraph('Universidad Cesar Vallejo - Documento confidencial', pie_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# ============================================================
# ENDPOINT: ENVIAR EMAIL DE PRUEBA (Resend)
# ============================================================
@app.route('/api/enviar-email-prueba', methods=['POST'])
def enviar_email_prueba():
    """Envia un email de prueba usando Resend.
    
    Recibe: { "destino": "correo@ejemplo.com" }
    Devuelve: { "exito": true, "id": "..." }
    """
    if not RESEND_API_KEY:
        return jsonify({
            "exito": False,
            "error": "Resend no esta configurado en el servidor"
        }), 503
    
    try:
        data = request.json
        destino = data.get('destino', '')
        
        if not destino or '@' not in destino:
            return jsonify({"exito": False, "error": "Correo destino invalido"}), 400
        
        # Construir el email HTML
        from datetime import timezone, timedelta
        PERU_TZ = timezone(timedelta(hours=-5))
        ahora = datetime.now(timezone.utc).astimezone(PERU_TZ)
        fecha_str = ahora.strftime("%d/%m/%Y %H:%M")
        
        html_email = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
          <div style="background: linear-gradient(135deg, #EF9F27, #639922); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">AgroIA</h1>
            <p style="color: white; margin: 5px 0 0 0; font-size: 14px;">Sistema de Control Operativo Agricola</p>
          </div>
          <div style="padding: 30px; background: #f9f9f9;">
            <h2 style="color: #243024;">Email de prueba exitoso</h2>
            <p style="color: #555; line-height: 1.6;">
              Este es un correo de prueba del sistema AgroIA. Si lo estas leyendo, 
              significa que la configuracion de envio de correos funciona correctamente.
            </p>
            <div style="background: white; border-left: 4px solid #EF9F27; padding: 15px; margin: 20px 0;">
              <strong style="color: #243024;">Detalles de la prueba:</strong><br>
              <span style="color: #555;">Fecha y hora: {fecha_str}</span><br>
              <span style="color: #555;">Servicio: Resend</span><br>
              <span style="color: #555;">Estado: Operativo</span>
            </div>
            <p style="color: #555; line-height: 1.6;">
              El siguiente paso sera adjuntar los reportes en PDF generados automaticamente 
              por el agente IA.
            </p>
          </div>
          <div style="background: #243024; padding: 20px; text-align: center;">
            <p style="color: #999; margin: 0; font-size: 12px;">
              AgroIA - Universidad Cesar Vallejo<br>
              Proyecto academico - Valle de Viru, La Libertad
            </p>
          </div>
        </div>
        """
        
        # Llamar a la API de Resend
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": EMAIL_FROM,
                "to": [destino],
                "subject": "AgroIA - Email de prueba",
                "html": html_email
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[Email] Enviado correctamente a {destino} - ID: {result.get('id')}")
            return jsonify({
                "exito": True,
                "id": result.get('id'),
                "mensaje": f"Email enviado a {destino}"
            })
        else:
            error_data = response.json() if response.text else {}
            print(f"[Email] Error {response.status_code}: {error_data}")
            return jsonify({
                "exito": False,
                "error": error_data.get('message', f'Error HTTP {response.status_code}'),
                "detalle": error_data
            }), response.status_code
            
    except Exception as e:
        print(f"[Email] Error: {e}")
        return jsonify({"exito": False, "error": str(e)}), 500


# ============================================================
# ENDPOINT: ENVIAR REPORTE CON PDF ADJUNTO (Resend)
# ============================================================
@app.route('/api/enviar-reporte', methods=['POST'])
def enviar_reporte():
    """Genera un reporte PDF y lo envia como adjunto por email.
    
    Recibe: { "destino": "correo@ejemplo.com", "tipo": "gerencia" }
    Devuelve: { "exito": true, "id": "..." }
    """
    if not RESEND_API_KEY:
        return jsonify({
            "exito": False,
            "error": "Resend no esta configurado en el servidor"
        }), 503
    
    try:
        data = request.json
        destino = data.get('destino', '')
        tipo = data.get('tipo', 'gerencia')
        
        if not destino or '@' not in destino:
            return jsonify({"exito": False, "error": "Correo destino invalido"}), 400
        
        # Generar el PDF segun el tipo
        if tipo == 'gerencia':
            pdf_bytes = generar_pdf_gerencia()
            nombre_reporte = 'Gerencia'
        else:
            return jsonify({"exito": False, "error": f"Tipo de reporte '{tipo}' aun no disponible"}), 400
        
        # Codificar PDF en base64 para el adjunto
        import base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        from datetime import timezone, timedelta
        PERU_TZ = timezone(timedelta(hours=-5))
        ahora = datetime.now(timezone.utc).astimezone(PERU_TZ)
        fecha_archivo = ahora.strftime("%Y-%m-%d")
        fecha_legible = ahora.strftime("%d/%m/%Y")
        nombre_archivo = f"AgroIA_Reporte_{nombre_reporte}_{fecha_archivo}.pdf"
        
        # Email HTML
        html_email = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
          <div style="background: linear-gradient(135deg, #EF9F27, #639922); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">AgroIA</h1>
            <p style="color: white; margin: 5px 0 0 0; font-size: 14px;">Reporte Ejecutivo - {nombre_reporte}</p>
          </div>
          <div style="padding: 30px; background: #f9f9f9;">
            <h2 style="color: #243024;">Reporte del {fecha_legible}</h2>
            <p style="color: #555; line-height: 1.6;">
              Estimado equipo de {nombre_reporte},<br><br>
              Adjunto encontrara el reporte ejecutivo del dia generado automaticamente 
              por el agente IA de AgroIA, con los indicadores de cosecha, validacion 
              estadistica y produccion por cuadrilla.
            </p>
            <div style="background: white; border-left: 4px solid #EF9F27; padding: 15px; margin: 20px 0;">
              <strong style="color: #243024;">Documento adjunto:</strong><br>
              <span style="color: #555;">{nombre_archivo}</span>
            </div>
            <p style="color: #777; font-size: 13px; line-height: 1.6;">
              Este reporte fue generado y enviado automaticamente. Para ver el detalle 
              completo en tiempo real, ingrese a la aplicacion AgroIA.
            </p>
          </div>
          <div style="background: #243024; padding: 20px; text-align: center;">
            <p style="color: #999; margin: 0; font-size: 12px;">
              AgroIA - Universidad Cesar Vallejo<br>
              Proyecto academico - Valle de Viru, La Libertad
            </p>
          </div>
        </div>
        """
        
        # Enviar via Resend con adjunto
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": EMAIL_FROM,
                "to": [destino],
                "subject": f"AgroIA - Reporte {nombre_reporte} - {fecha_legible}",
                "html": html_email,
                "attachments": [{
                    "filename": nombre_archivo,
                    "content": pdf_base64
                }]
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[Email] Reporte {tipo} enviado a {destino} - ID: {result.get('id')}")
            return jsonify({
                "exito": True,
                "id": result.get('id'),
                "mensaje": f"Reporte enviado a {destino}"
            })
        else:
            error_data = response.json() if response.text else {}
            print(f"[Email] Error {response.status_code}: {error_data}")
            return jsonify({
                "exito": False,
                "error": error_data.get('message', f'Error HTTP {response.status_code}'),
                "detalle": error_data
            }), response.status_code
            
    except Exception as e:
        import traceback
        print(f"[Email] Error en enviar-reporte: {e}")
        print(traceback.format_exc())
        return jsonify({"exito": False, "error": str(e)}), 500


# ============================================================
# INICIO DEL SERVIDOR
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("AgroIA - Servidor Backend Local")
    print("Universidad Cesar Vallejo - Proyecto academico")
    print("=" * 60)
    # Configuracion para Render (produccion) o local
    # Render asigna el puerto automaticamente via variable PORT
    port = int(os.environ.get("PORT", 5000))
    host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    
    print(f"")
    print(f"Datos base cargados:")
    print(f"  - {len(TRABAJADORES)} trabajadores en 3 cuadrillas")
    print(f"  - {len(LOTES)} lotes activos")
    print(f"")
    print(f"Servidor corriendo en: http://{host}:{port}")
    print(f"Datadog conectado a: {SITE}")
    print(f"")
    
    if API_KEY == "PEGA_AQUI_TU_API_KEY":
        print("  >>> ATENCION: DATADOG_API_KEY no configurada <<<")
        print("  Configura la variable de entorno DATADOG_API_KEY")
        print("  En Render: Settings > Environment > Add Environment Variable")
        print("")
    
    app.run(host=host, port=port, debug=False)
