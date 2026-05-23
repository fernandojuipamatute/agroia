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
    
    # Guardar la pesada
    ahora = datetime.now()
    hora_str = ahora.strftime("%H:%M")
    pesada_para_app = {
        "hora": hora_str,
        "timestamp": ahora.timestamp(),
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
    """Devuelve TODAS las pesadas guardadas en Supabase de las ultimas 24 horas.
    Usado cuando la app se abre por primera vez para cargar el historico."""
    if supabase:
        try:
            # Pesadas de las ultimas 24 horas (en UTC, sin importar zona horaria)
            # Esto evita problemas de timezone entre el servidor (UTC) y el usuario (Lima)
            from datetime import timezone, timedelta
            desde = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            
            result = supabase.table('pesadas')\
                .select("*")\
                .gt('timestamp_creacion', desde)\
                .order('timestamp_creacion', desc=False)\
                .limit(500)\
                .execute()
            
            pesadas_lista = []
            for p in result.data:
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
