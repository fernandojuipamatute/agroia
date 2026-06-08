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
# CONFIGURACION DE DESTINATARIOS POR ROL
# ============================================================
# Para cambiar destinatarios, modifica esta tabla.
# Cuando tengas dominio propio verificado en Resend, puedes
# poner cualquier correo aqui.
# IMPORTANTE: con el dominio de prueba 'onboarding@resend.dev'
# solo se puede enviar al correo registrado en Resend.
DESTINATARIOS = {
    'gerencia':       [os.environ.get('EMAIL_GERENCIA', '')],
    'jefecampo':      [os.environ.get('EMAIL_JEFECAMPO', '')],
    'supervisor_C3':  [os.environ.get('EMAIL_SUPERVISOR_C3', '')],
    'supervisor_C5':  [os.environ.get('EMAIL_SUPERVISOR_C5', '')],
    'supervisor_C7':  [os.environ.get('EMAIL_SUPERVISOR_C7', '')],
    'rrhh':           [os.environ.get('EMAIL_RRHH', '')],
}

# ============================================================
# PROGRAMACION DE ENVIOS AUTOMATICOS
# ============================================================
# Configura cuando se envia cada reporte.
# Dia de la semana: 0=Lunes, 1=Martes, ..., 5=Sabado, 6=Domingo
# Hora en formato 24h (zona horaria de Peru UTC-5)
PROGRAMA_ENVIOS = [
    # GERENCIA: Lunes 8 AM (semanal)
    {'tipo': 'gerencia', 'dias': [0], 'hora': 8, 'minuto': 0},
    
    # JEFE DE CAMPO: Lunes a Sabado 8 PM (diario)
    {'tipo': 'jefecampo', 'dias': [0, 1, 2, 3, 4, 5], 'hora': 20, 'minuto': 0},
    
    # SUPERVISOR C3: Lunes a Sabado 7 PM (diario)
    {'tipo': 'supervisor', 'cuadrilla': 'C3', 'dias': [0, 1, 2, 3, 4, 5], 'hora': 19, 'minuto': 0},
    
    # SUPERVISOR C5: Lunes a Sabado 7 PM
    {'tipo': 'supervisor', 'cuadrilla': 'C5', 'dias': [0, 1, 2, 3, 4, 5], 'hora': 19, 'minuto': 0},
    
    # SUPERVISOR C7: Lunes a Sabado 7 PM
    {'tipo': 'supervisor', 'cuadrilla': 'C7', 'dias': [0, 1, 2, 3, 4, 5], 'hora': 19, 'minuto': 0},
    
    # RR.HH.: Sabado 9 PM (semanal con planilla acumulada)
    {'tipo': 'rrhh', 'dias': [5], 'hora': 21, 'minuto': 0},
]

# Tolerancia en minutos para considerar que es la "hora correcta"
# Si UptimeRobot llama cada 5 min, esta tolerancia debe ser >= 5
TOLERANCIA_MINUTOS = 6

# Registro en memoria de envios ya hechos hoy (evita duplicados)
# Se reinicia cada vez que el servidor reinicia.
ENVIOS_REALIZADOS = set()


# ============================================================
# RATE LIMITING + VALIDACION DE INPUTS (ISO 27001 - A.14)
# ============================================================
# Sistema de proteccion contra abuso y datos maliciosos.
# Cumple con OWASP Top 10: Injection, Broken Auth, XSS.

from functools import wraps
from collections import defaultdict
from threading import Lock
import re
import time as _time

# Limites de rate por minuto (por IP)
RATE_LIMITS = {
    'default': 60,           # 60 peticiones/min para endpoints normales
    'pesada': 60,            # 60 pesadas/min por IP
    'analizar_imagen': 20,   # 20 analisis IA/min (Gemini es caro)
    'enviar_reporte': 10,    # 10 envios de email/min
    'cron': 30,              # 30 llamadas de UptimeRobot/min
}

# Tracking de peticiones por IP (en memoria - se reinicia con el servidor)
# Formato: { ip: [(timestamp1, endpoint1), (timestamp2, endpoint2), ...] }
_rate_tracker = defaultdict(list)
_rate_lock = Lock()

def _obtener_ip_cliente():
    """Obtiene la IP del cliente, considerando proxies (Render, Cloudflare)."""
    # Render pone la IP real en X-Forwarded-For
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def rate_limit(categoria='default'):
    """Decorator que limita peticiones por IP por minuto.
    
    Uso:
        @app.route('/api/...')
        @rate_limit('pesada')
        def mi_endpoint():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ip = _obtener_ip_cliente()
            limite = RATE_LIMITS.get(categoria, RATE_LIMITS['default'])
            ahora = _time.time()
            ventana = 60  # 60 segundos
            
            with _rate_lock:
                # Limpiar registros viejos (mayores a 60 seg)
                _rate_tracker[ip] = [
                    (t, ep) for t, ep in _rate_tracker[ip]
                    if ahora - t < ventana
                ]
                
                # Contar peticiones recientes de esta categoria
                count_categoria = sum(1 for t, ep in _rate_tracker[ip] if ep == categoria)
                
                if count_categoria >= limite:
                    # Rate limit excedido
                    tiempos = [t for t, ep in _rate_tracker[ip] if ep == categoria]
                    siguiente = int(ventana - (ahora - min(tiempos))) if tiempos else ventana
                    
                    print(f"[RateLimit] Bloqueado: {ip} en {categoria} ({count_categoria}/{limite})")
                    
                    return jsonify({
                        'exito': False,
                        'error': 'Demasiadas peticiones',
                        'mensaje': f'Has hecho demasiadas peticiones. Espera unos segundos.',
                        'limite': f'{limite} peticiones/minuto',
                        'siguiente_intento_en': max(siguiente, 1)
                    }), 429
                
                # Registrar la peticion
                _rate_tracker[ip].append((ahora, categoria))
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# === VALIDADORES DE INPUTS ===

class ValidacionError(Exception):
    """Error de validacion con campo y mensaje claros."""
    def __init__(self, mensaje, campo=None):
        self.mensaje = mensaje
        self.campo = campo
        super().__init__(mensaje)


def validar_dni(valor, campo='dni'):
    """DNI peruano: exactamente 8 digitos."""
    if not valor:
        raise ValidacionError('El DNI es obligatorio', campo)
    valor_str = str(valor).strip()
    if not re.match(r'^\d{8}$', valor_str):
        raise ValidacionError('El DNI debe tener exactamente 8 dígitos', campo)
    return valor_str


def validar_numero(valor, minimo, maximo, campo='valor', tipo='float'):
    """Numero dentro de rango."""
    if valor is None or valor == '':
        raise ValidacionError(f'El campo {campo} es obligatorio', campo)
    try:
        num = float(valor) if tipo == 'float' else int(valor)
    except (ValueError, TypeError):
        raise ValidacionError(f'El campo {campo} debe ser un número válido', campo)
    if num < minimo:
        raise ValidacionError(f'{campo} no puede ser menor a {minimo}', campo)
    if num > maximo:
        raise ValidacionError(f'{campo} no puede ser mayor a {maximo}', campo)
    return num


def validar_cuadrilla(valor, campo='cuadrilla'):
    """Cuadrilla valida: C3, C5 o C7."""
    if not valor:
        raise ValidacionError(f'La cuadrilla es obligatoria', campo)
    valor_str = str(valor).strip().upper()
    if valor_str not in ('C3', 'C5', 'C7'):
        raise ValidacionError(f'Cuadrilla inválida. Debe ser C3, C5 o C7', campo)
    return valor_str


def validar_lote(valor, campo='lote'):
    """Lote valido (formato L-XX)."""
    if not valor:
        raise ValidacionError(f'El lote es obligatorio', campo)
    valor_str = str(valor).strip().upper()
    if not re.match(r'^L-\d{1,3}$', valor_str):
        raise ValidacionError(f'Formato de lote inválido (debe ser L-XX)', campo)
    return valor_str


def validar_email(valor, campo='email'):
    """Email basico."""
    if not valor:
        raise ValidacionError(f'El correo es obligatorio', campo)
    valor_str = str(valor).strip().lower()
    if not re.match(r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$', valor_str):
        raise ValidacionError(f'Formato de correo inválido', campo)
    if len(valor_str) > 200:
        raise ValidacionError(f'El correo es demasiado largo', campo)
    return valor_str


def validar_tipo_reporte(valor, campo='tipo'):
    """Tipo de reporte valido."""
    if not valor:
        raise ValidacionError(f'El tipo de reporte es obligatorio', campo)
    valor_str = str(valor).strip().lower()
    if valor_str not in ('gerencia', 'jefecampo', 'supervisor', 'rrhh'):
        raise ValidacionError(f'Tipo de reporte inválido', campo)
    return valor_str


def limpiar_string(texto, max_largo=500):
    """Limpia HTML/scripts y limita longitud.
    Previene XSS (Cross-Site Scripting).
    """
    if not texto:
        return ''
    texto_str = str(texto)
    # Quitar HTML/scripts
    texto_str = re.sub(r'<[^>]*>', '', texto_str)
    # Quitar caracteres de control
    texto_str = re.sub(r'[\x00-\x1f\x7f]', '', texto_str)
    # Limitar longitud
    return texto_str.strip()[:max_largo]


def manejar_error_validacion(func):
    """Decorator que captura ValidacionError y devuelve respuesta JSON limpia."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidacionError as e:
            return jsonify({
                'exito': False,
                'error': 'Datos inválidos',
                'mensaje': e.mensaje,
                'campo': e.campo
            }), 400
    return wrapper


print("[Seguridad] Rate limiting y validacion de inputs activados")
print(f"[Seguridad] Limites por minuto: {RATE_LIMITS}")


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
@rate_limit('pesada')
@manejar_error_validacion
def recibir_pesada():
    """Recibe una pesada de la app y la envia a Datadog"""
    data = request.json or {}
    
    # Validar inputs criticos
    dni = validar_dni(data.get('dni', ''))
    kg = validar_numero(data.get('kg'), minimo=1, maximo=800, campo='kg')
    horas = validar_numero(data.get('horas'), minimo=0.5, maximo=12, campo='horas')
    lote = validar_lote(data.get('lote', ''))
    
    # Cuadrilla opcional pero validada si viene
    cuadrilla_input = data.get('cuadrilla', '')
    if cuadrilla_input:
        cuadrilla_input = validar_cuadrilla(cuadrilla_input)
    
    # Sanitizar nombre (XSS prevention)
    nombre_input = limpiar_string(data.get('nombre', ''), max_largo=100)
    
    # Validar que el trabajador existe en la base
    trabajador_db = TRABAJADORES.get(dni)
    if not trabajador_db:
        # Si no esta en la BD, usar los datos que mando la app
        nombre = nombre_input or 'Desconocido'
        cuadrilla = cuadrilla_input or 'N/A'
        historico = validar_numero(data.get('historico', 23), minimo=1, maximo=100, campo='historico')
        sigma = validar_numero(data.get('sigma', 3), minimo=0.1, maximo=20, campo='sigma')
    else:
        nombre = trabajador_db['nombre']
        cuadrilla = trabajador_db['cuadrilla']
        historico = trabajador_db['historico']
        sigma = trabajador_db['sigma']
    
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
@rate_limit('default')
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
@rate_limit('default')
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
@rate_limit('default')
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
@rate_limit('default')
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
@rate_limit('default')
def listar_trabajadores():
    """Devuelve la lista de trabajadores"""
    return jsonify({
        "total": len(TRABAJADORES),
        "trabajadores": [
            {"dni": dni, **datos} for dni, datos in TRABAJADORES.items()
        ]
    })

@app.route('/api/lotes', methods=['GET'])
@rate_limit('default')
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
@rate_limit('analizar_imagen')
@manejar_error_validacion
def analizar_imagen():
    """Analiza una imagen usando IA (Gemini o Claude).
    
    Recibe: { "imagen_base64": "..." (sin prefijo data:image), "contexto": "opcional" }
    Devuelve: { "exito": true, "analisis": {...}, "proveedor": "gemini" }
    """
    try:
        data = request.json or {}
        if not data.get('imagen_base64'):
            raise ValidacionError('Falta imagen_base64', 'imagen_base64')
        
        imagen_b64 = data['imagen_base64']
        
        # Validar tamaño de la imagen (max 10MB en base64)
        if len(imagen_b64) > 14_000_000:  # ~10MB
            raise ValidacionError('Imagen demasiado grande (máximo 10MB)', 'imagen_base64')
        
        if len(imagen_b64) < 100:
            raise ValidacionError('Imagen inválida o vacía', 'imagen_base64')
        
        # Sanitizar contexto (XSS prevention)
        contexto = limpiar_string(data.get('contexto', 'Imagen de cosecha de palta Hass'), max_largo=500)
        
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


def _crear_pdf_base(color_principal_hex, color_oscuro_hex, color_claro_hex,
                    titulo_rol, datos_resumen, secciones):
    """Helper que crea un PDF con el diseno estandar (header + secciones).
    
    Args:
        color_principal_hex: color hex string '#XXXXXX'
        color_oscuro_hex: hex string
        color_claro_hex: hex string  
        titulo_rol: 'JEFE DE CAMPO', 'SUPERVISOR', etc
        datos_resumen: dict con 'kpis' (lista de tuplas) y 'texto'
        secciones: lista de dicts con 'titulo' y 'flowables'
    
    Returns: bytes del PDF
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY, TA_CENTER
    import io
    from datetime import timezone, timedelta
    
    COLOR = colors.HexColor(color_principal_hex)
    COLOR_OSC = colors.HexColor(color_oscuro_hex)
    COLOR_CLA = colors.HexColor(color_claro_hex)
    GRIS_OSC = colors.HexColor('#0F172A')
    GRIS = colors.HexColor('#475569')
    
    PERU_TZ = timezone(timedelta(hours=-5))
    ahora = datetime.now(timezone.utc).astimezone(PERU_TZ)
    fecha_str = ahora.strftime("%d/%m/%Y %H:%M")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm,
                            bottomMargin=2*cm, leftMargin=2*cm, rightMargin=2*cm)
    
    styles = getSampleStyleSheet()
    story = []
    
    # === ENCABEZADO ===
    titulo_style = ParagraphStyle('T', parent=styles['Title'], fontSize=22,
                                  textColor=COLOR, fontName='Helvetica-Bold',
                                  spaceAfter=4, alignment=TA_LEFT)
    story.append(Paragraph('AgroIA', titulo_style))
    
    sub_style = ParagraphStyle('S', parent=styles['Normal'], fontSize=11,
                               textColor=GRIS, spaceAfter=2)
    story.append(Paragraph(f'Reporte - {titulo_rol}', sub_style))
    
    fecha_style = ParagraphStyle('F', parent=styles['Normal'], fontSize=9,
                                 textColor=GRIS, spaceAfter=10)
    story.append(Paragraph(f'Cosecha Palta Hass - Valle de Viru - {fecha_str}', fecha_style))
    
    story.append(HRFlowable(width="100%", thickness=2, color=COLOR, spaceAfter=15))
    
    # === RESUMEN ===
    if datos_resumen.get('titulo_seccion'):
        h_style = ParagraphStyle('H', parent=styles['Normal'], fontSize=14,
                                 textColor=GRIS_OSC, fontName='Helvetica-Bold', spaceAfter=8)
        story.append(Paragraph(datos_resumen['titulo_seccion'], h_style))
    
    if datos_resumen.get('texto'):
        p_style = ParagraphStyle('P', parent=styles['Normal'], fontSize=10,
                                 textColor=GRIS_OSC, alignment=TA_JUSTIFY, leading=15, spaceAfter=15)
        story.append(Paragraph(datos_resumen['texto'], p_style))
    
    # === KPIs ===
    if datos_resumen.get('kpis'):
        kpi_row = [f"{titulo}\n{valor}" for titulo, valor in datos_resumen['kpis']]
        kpi_table = Table([kpi_row], colWidths=[4.2*cm]*len(kpi_row), rowHeights=[2*cm])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), COLOR_CLA),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 11),
            ('TEXTCOLOR', (0,0), (-1,-1), GRIS_OSC),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LINEBEFORE', (0,0), (0,-1), 2, COLOR),
            ('LINEBEFORE', (1,0), (1,-1), 2, COLOR),
            ('LINEBEFORE', (2,0), (2,-1), 2, COLOR),
            ('LINEBEFORE', (3,0), (3,-1), 2, COLOR),
            ('GRID', (0,0), (-1,-1), 3, colors.white),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 0.5*cm))
    
    # === SECCIONES ===
    h_style = ParagraphStyle('H2', parent=styles['Normal'], fontSize=14,
                             textColor=GRIS_OSC, fontName='Helvetica-Bold', spaceAfter=8)
    for seccion in secciones:
        if seccion.get('titulo'):
            story.append(Paragraph(seccion['titulo'], h_style))
        for flow in seccion.get('flowables', []):
            story.append(flow)
        story.append(Spacer(1, 0.5*cm))
    
    # === PIE ===
    story.append(Spacer(1, 0.5*cm))
    pie_style = ParagraphStyle('Pie', parent=styles['Normal'], fontSize=8,
                               textColor=GRIS, alignment=TA_CENTER)
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=8))
    story.append(Paragraph(f'AgroIA - Sistema de Control Operativo - Reporte {titulo_rol}', pie_style))
    story.append(Paragraph('Universidad Cesar Vallejo - Documento confidencial', pie_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


def generar_pdf_jefe_campo():
    """Genera PDF de Jefe de Campo con ranking de cuadrillas."""
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_JUSTIFY
    
    pesadas = _obtener_pesadas_supabase()
    m = _calcular_metricas_base(pesadas)
    
    # Ranking ordenado por productividad
    rankings = []
    for c in ['C3', 'C5', 'C7']:
        mc = _calcular_metricas_cuadrilla(pesadas, c)
        rankings.append(mc)
    rankings.sort(key=lambda x: x['prod_promedio'], reverse=True)
    
    # Datos para tabla de ranking
    medallas = ['#1 ORO', '#2 PLATA', '#3 BRONCE']
    ranking_rows = [['Pos.', 'Cuadrilla', 'Supervisor', 'Pesadas', 'Validadas', 'Kg', 'Productividad', 'Alertas']]
    for i, r in enumerate(rankings):
        ranking_rows.append([
            medallas[i],
            r['cuadrilla'],
            SUPERVISORES.get(r['cuadrilla'], '-'),
            len(r['validadas']) + len(r['bloqueadas']),
            len(r['validadas']),
            f"{round(r['kg_validados']):,}",
            f"{r['prod_promedio']:.1f} kg/h",
            len(r['bloqueadas'])
        ])
    
    VERDE = colors.HexColor('#639922')
    VERDE_CLA = colors.HexColor('#ECF5DC')
    
    ranking_table = Table(ranking_rows, colWidths=[2*cm, 2*cm, 3.5*cm, 1.8*cm, 2*cm, 2*cm, 2.5*cm, 1.5*cm])
    ranking_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), VERDE),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor('#0F172A')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, VERDE_CLA]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    
    # Acciones recomendadas (callout)
    lider = rankings[0]
    ultimo = rankings[-1]
    styles = getSampleStyleSheet()
    callout_style = ParagraphStyle('CO', parent=styles['Normal'], fontSize=9,
                                   textColor=colors.HexColor('#0F172A'), leading=13)
    acciones_text = (f"<b>ACCIONES RECOMENDADAS</b><br/>"
                     f"1. Replicar practicas de cuadrilla {lider['cuadrilla']} "
                     f"({lider['prod_promedio']:.1f} kg/h) en {ultimo['cuadrilla']} "
                     f"({ultimo['prod_promedio']:.1f} kg/h).<br/>"
                     f"2. Coordinar revision de las {len(m['observadas']) + len(m['bloqueadas'])} "
                     f"pesadas con alertas.<br/>"
                     f"3. Validar resultados con sistema de pesaje fisico al cierre.")
    callout_data = [[Paragraph(acciones_text, callout_style)]]
    callout_table = Table(callout_data, colWidths=[17*cm])
    callout_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), VERDE_CLA),
        ('LINEBEFORE', (0,0), (0,-1), 3, VERDE),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    
    # Construir el PDF
    return _crear_pdf_base(
        color_principal_hex='#639922',
        color_oscuro_hex='#3C6414',
        color_claro_hex='#ECF5DC',
        titulo_rol='JEFE DE CAMPO',
        datos_resumen={
            'titulo_seccion': 'Resumen Operativo del Dia',
            'texto': (f"Estado de las 3 cuadrillas activas en la jornada. Se registraron "
                      f"{m['total']} pesadas con tasa de validacion automatica del "
                      f"{m['tasa_validacion']:.1f}%. Productividad promedio del campo: "
                      f"{m['prod_promedio']:.1f} kg/h."),
            'kpis': [
                ('PESADAS', f"{m['total']}"),
                ('PRODUCTIVIDAD', f"{m['prod_promedio']:.1f} kg/h"),
                ('OBSERVADAS', f"{len(m['observadas'])}"),
                ('BLOQUEADAS', f"{len(m['bloqueadas'])}"),
            ]
        },
        secciones=[
            {'titulo': 'Ranking de Cuadrillas', 'flowables': [ranking_table]},
            {'titulo': None, 'flowables': [callout_table]},
        ]
    )


def generar_pdf_supervisor(cuadrilla='C3'):
    """Genera PDF de Supervisor de una cuadrilla especifica."""
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.units import cm
    
    pesadas = _obtener_pesadas_supabase()
    mc = _calcular_metricas_cuadrilla(pesadas, cuadrilla)
    
    # Trabajadores de la cuadrilla
    trabajadores_cuad = {dni: d for dni, d in TRABAJADORES.items() if d['cuadrilla'] == cuadrilla}
    
    # Calcular performers
    performers = []
    for dni, datos in trabajadores_cuad.items():
        sus_pesadas = [p for p in pesadas if p.get('dni') == dni and p.get('estado') in ('green', 'yellow')]
        if not sus_pesadas:
            continue
        kg = sum(float(p.get('kg', 0)) for p in sus_pesadas)
        horas = sum(float(p.get('horas', 0)) for p in sus_pesadas)
        prod = kg/horas if horas > 0 else 0
        performers.append({
            'dni': dni,
            'nombre': datos['nombre'],
            'kg': kg,
            'horas': horas,
            'prod': prod,
            'pesadas': len(sus_pesadas)
        })
    performers.sort(key=lambda x: x['prod'], reverse=True)
    top5 = performers[:5]
    
    AZUL = colors.HexColor('#2563EB')
    AZUL_CLA = colors.HexColor('#DBEAFE')
    
    # Tabla Top 5
    estrellas = ['*** TOP', '** ALTO', '* BUENO', '', '']
    top_rows = [['Pos.', 'DNI', 'Trabajador', 'Kg', 'Horas', 'Productividad', 'Rating']]
    if top5:
        for i, t in enumerate(top5):
            top_rows.append([
                f"#{i+1}",
                t['dni'],
                t['nombre'],
                f"{round(t['kg'])}",
                f"{t['horas']:.1f}",
                f"{t['prod']:.1f} kg/h",
                estrellas[i] if i < 3 else ''
            ])
    else:
        top_rows.append(['', '', 'Sin pesadas validadas aun', '', '', '', ''])
    
    top_table = Table(top_rows, colWidths=[1.5*cm, 2.5*cm, 4.5*cm, 1.8*cm, 1.8*cm, 2.5*cm, 2.4*cm])
    top_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), AZUL),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor('#0F172A')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, AZUL_CLA]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    
    # Tabla de pesadas recientes
    pesadas_cuad = [p for p in pesadas if p.get('cuadrilla') == cuadrilla][:15]
    pes_rows = [['Hora', 'DNI', 'Trabajador', 'Kg', 'Horas', 'Productividad', 'Estado']]
    estado_map = {'green': 'Validado', 'yellow': 'Validado*', 'orange': 'Observado', 'red': 'Bloqueado'}
    for p in pesadas_cuad:
        t = TRABAJADORES.get(p.get('dni'), {})
        prod = (float(p.get('kg', 0)) / float(p.get('horas', 1))) if float(p.get('horas', 0)) > 0 else 0
        pes_rows.append([
            p.get('hora', '-'),
            p.get('dni', '-'),
            t.get('nombre', p.get('nombre', '-')),
            f"{p.get('kg', 0)}",
            f"{p.get('horas', 0)}",
            f"{prod:.1f} kg/h",
            estado_map.get(p.get('estado'), p.get('estado', '-'))
        ])
    
    pes_table = Table(pes_rows, colWidths=[1.8*cm, 2.3*cm, 4*cm, 1.5*cm, 1.5*cm, 2.5*cm, 2.4*cm])
    pes_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1946AF')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.HexColor('#0F172A')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, AZUL_CLA]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
    ]))
    
    secciones = [
        {'titulo': 'Top 5 Performers del Dia', 'flowables': [top_table]},
    ]
    if pesadas_cuad:
        secciones.append({'titulo': 'Pesadas Recientes', 'flowables': [pes_table]})
    
    return _crear_pdf_base(
        color_principal_hex='#2563EB',
        color_oscuro_hex='#1946AF',
        color_claro_hex='#DBEAFE',
        titulo_rol=f'SUPERVISOR - Cuadrilla {cuadrilla}',
        datos_resumen={
            'titulo_seccion': f'Cuadrilla {cuadrilla} - {SUPERVISORES.get(cuadrilla, "-")}',
            'texto': (f"Reporte detallado de la cuadrilla {cuadrilla} bajo supervision de "
                      f"{SUPERVISORES.get(cuadrilla, '-')}. Total de {len(trabajadores_cuad)} "
                      f"trabajadores asignados, {mc['total']} pesadas registradas, "
                      f"{round(mc['kg_validados']):,} kg validados con productividad promedio de "
                      f"{mc['prod_promedio']:.1f} kg/h."),
            'kpis': [
                ('TRABAJADORES', f"{len(trabajadores_cuad)}"),
                ('PESADAS', f"{mc['total']}"),
                ('KG VALIDADOS', f"{round(mc['kg_validados']):,}"),
                ('ALERTAS', f"{len(mc['bloqueadas'])}"),
            ]
        },
        secciones=secciones
    )


def generar_pdf_rrhh():
    """Genera PDF de RR.HH. con planilla y firmas."""
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    
    pesadas = _obtener_pesadas_supabase()
    
    # Calcular planilla
    planilla = []
    for dni, datos in TRABAJADORES.items():
        sus_pesadas = [p for p in pesadas if p.get('dni') == dni and p.get('estado') in ('green', 'yellow')]
        kg_total = sum(float(p.get('kg', 0)) for p in sus_pesadas)
        horas_total = sum(float(p.get('horas', 0)) for p in sus_pesadas)
        monto = horas_total * TARIFA_HORA
        planilla.append({
            'dni': dni,
            'nombre': datos['nombre'],
            'cuadrilla': datos['cuadrilla'],
            'kg': kg_total,
            'horas': horas_total,
            'monto': monto,
            'sin_registro': len(sus_pesadas) == 0
        })
    
    con_registro = [t for t in planilla if not t['sin_registro']]
    sin_registro = [t for t in planilla if t['sin_registro']]
    total_pagar = sum(t['monto'] for t in con_registro)
    total_horas = sum(t['horas'] for t in con_registro)
    total_kg = sum(t['kg'] for t in con_registro)
    
    MORADO = colors.HexColor('#7C3AED')
    MORADO_OSC = colors.HexColor('#581CC3')
    MORADO_CLA = colors.HexColor('#EDE9FE')
    
    # Tabla de planilla
    pla_rows = [['DNI', 'Apellidos y Nombres', 'Cuadrilla', 'Kg validados', 'Horas', 'Monto (S/)']]
    for t in con_registro:
        pla_rows.append([
            t['dni'],
            t['nombre'],
            t['cuadrilla'],
            f"{t['kg']:.1f}",
            f"{t['horas']:.1f}",
            f"{t['monto']:.2f}"
        ])
    # Fila TOTAL
    pla_rows.append(['', '', 'TOTAL', f"{total_kg:.1f}", f"{total_horas:.1f}", f"{total_pagar:.2f}"])
    
    pla_table = Table(pla_rows, colWidths=[2.2*cm, 4.5*cm, 2*cm, 2.5*cm, 2*cm, 3.8*cm])
    pla_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), MORADO),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('FONTNAME', (0,1), (-1,-2), 'Helvetica'),
        ('TEXTCOLOR', (0,1), (-1,-2), colors.HexColor('#0F172A')),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, MORADO_CLA]),
        # Fila TOTAL destacada
        ('BACKGROUND', (0,-1), (-1,-1), MORADO_OSC),
        ('TEXTCOLOR', (0,-1), (-1,-1), colors.white),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,-1), (-1,-1), 10),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    
    secciones = [
        {'titulo': 'Detalle de Planilla', 'flowables': [pla_table]},
    ]
    
    # Callout sin registro
    if sin_registro:
        styles = getSampleStyleSheet()
        callout_style = ParagraphStyle('CO', parent=styles['Normal'], fontSize=9,
                                       textColor=colors.HexColor('#0F172A'), leading=13)
        nombres = ', '.join([t['nombre'].split()[0] + ' ' + t['nombre'].split()[1] 
                             for t in sin_registro[:8]])
        if len(sin_registro) > 8:
            nombres += f' y {len(sin_registro) - 8} mas'
        sin_reg_text = (f"<b>{len(sin_registro)} TRABAJADORES SIN REGISTRO</b><br/>"
                        f"Sin pesadas validadas hoy: {nombres}. Verificar asistencia con "
                        f"sus supervisores antes del cierre de planilla.")
        callout_data = [[Paragraph(sin_reg_text, callout_style)]]
        callout_table = Table(callout_data, colWidths=[17*cm])
        callout_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FFF8DC')),
            ('LINEBEFORE', (0,0), (0,-1), 3, colors.HexColor('#FBBF24')),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        secciones.append({'titulo': None, 'flowables': [callout_table]})
    
    # Firmas
    firmas_data = [
        ['_________________________', '_________________________'],
        ['Elaborado por Sistema AgroIA', 'Aprobado por Jefe de RR.HH.'],
        ['Validacion automatica agente IA', 'Firma y sello requeridos'],
    ]
    firmas_table = Table(firmas_data, colWidths=[8.5*cm, 8.5*cm])
    firmas_table.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('FONTSIZE', (0,1), (-1,1), 9),
        ('FONTSIZE', (0,2), (-1,2), 7),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,1), (-1,1), colors.HexColor('#475569')),
        ('TEXTCOLOR', (0,2), (-1,2), colors.HexColor('#94A3B8')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    secciones.append({'titulo': None, 'flowables': [Spacer(1, 0.3*cm), firmas_table]})
    
    return _crear_pdf_base(
        color_principal_hex='#7C3AED',
        color_oscuro_hex='#581CC3',
        color_claro_hex='#EDE9FE',
        titulo_rol='RECURSOS HUMANOS',
        datos_resumen={
            'titulo_seccion': 'Resumen de Planilla',
            'texto': (f"Planilla del dia con base en pesadas validadas por el agente IA. "
                      f"Tarifa aplicada: S/ {TARIFA_HORA}/hora segun Ley 31110 de Trabajadores "
                      f"Agrarios. Total a pagar: S/ {total_pagar:.2f} entre {len(con_registro)} "
                      f"trabajadores activos."),
            'kpis': [
                ('TRABAJADORES', f"{len(con_registro)}/{len(TRABAJADORES)}"),
                ('TOTAL HORAS', f"{total_horas:.1f}"),
                ('TOTAL KG', f"{round(total_kg):,}"),
                ('TOTAL A PAGAR', f"S/ {round(total_pagar):,}"),
            ]
        },
        secciones=secciones
    )


# ============================================================
# ENDPOINT: ENVIAR EMAIL DE PRUEBA (Resend)
# ============================================================
@app.route('/api/enviar-email-prueba', methods=['POST'])
@rate_limit('enviar_reporte')
@manejar_error_validacion
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
        data = request.json or {}
        destino = validar_email(data.get('destino', ''), 'destino')
        
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
@rate_limit('enviar_reporte')
@manejar_error_validacion
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
        data = request.json or {}
        destino = validar_email(data.get('destino', ''), 'destino')
        tipo = validar_tipo_reporte(data.get('tipo', 'gerencia'))
        
        # Generar el PDF segun el tipo
        if tipo == 'gerencia':
            pdf_bytes = generar_pdf_gerencia()
            nombre_reporte = 'Gerencia'
        elif tipo == 'jefecampo':
            pdf_bytes = generar_pdf_jefe_campo()
            nombre_reporte = 'Jefe de Campo'
        elif tipo == 'supervisor':
            cuadrilla = validar_cuadrilla(data.get('cuadrilla', 'C3'))
            pdf_bytes = generar_pdf_supervisor(cuadrilla)
            nombre_reporte = f'Supervisor {cuadrilla}'
        elif tipo == 'rrhh':
            pdf_bytes = generar_pdf_rrhh()
            nombre_reporte = 'RRHH'
        else:
            return jsonify({"exito": False, "error": f"Tipo de reporte '{tipo}' no valido. Use: gerencia, jefecampo, supervisor, rrhh"}), 400
        
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
# SISTEMA DE ENVIO AUTOMATICO PROGRAMADO
# ============================================================
def _enviar_reporte_automatico(tipo, destinatarios, cuadrilla=None):
    """Envia un reporte automatico a una lista de destinatarios.
    
    Args:
        tipo: 'gerencia', 'jefecampo', 'supervisor', 'rrhh'
        destinatarios: lista de correos
        cuadrilla: solo para 'supervisor' (C3, C5, C7)
    
    Returns:
        dict con resultados de cada envio
    """
    if not RESEND_API_KEY:
        return {"exito": False, "error": "Resend no configurado"}
    
    # Generar el PDF UNA VEZ y reutilizar para todos los destinatarios
    try:
        if tipo == 'gerencia':
            pdf_bytes = generar_pdf_gerencia()
            nombre_reporte = 'Gerencia'
        elif tipo == 'jefecampo':
            pdf_bytes = generar_pdf_jefe_campo()
            nombre_reporte = 'Jefe de Campo'
        elif tipo == 'supervisor':
            pdf_bytes = generar_pdf_supervisor(cuadrilla)
            nombre_reporte = f'Supervisor {cuadrilla}'
        elif tipo == 'rrhh':
            pdf_bytes = generar_pdf_rrhh()
            nombre_reporte = 'RRHH'
        else:
            return {"exito": False, "error": f"Tipo desconocido: {tipo}"}
    except Exception as e:
        return {"exito": False, "error": f"Error generando PDF: {e}"}
    
    import base64
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    from datetime import timezone, timedelta
    PERU_TZ = timezone(timedelta(hours=-5))
    ahora = datetime.now(timezone.utc).astimezone(PERU_TZ)
    fecha_archivo = ahora.strftime("%Y-%m-%d")
    fecha_legible = ahora.strftime("%d/%m/%Y")
    nombre_archivo = f"AgroIA_Reporte_{nombre_reporte.replace(' ', '_')}_{fecha_archivo}.pdf"
    
    # HTML del email
    html_email = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background: linear-gradient(135deg, #EF9F27, #639922); padding: 30px; text-align: center;">
        <h1 style="color: white; margin: 0; font-size: 28px;">AgroIA</h1>
        <p style="color: white; margin: 5px 0 0 0; font-size: 14px;">Reporte Automatico - {nombre_reporte}</p>
      </div>
      <div style="padding: 30px; background: #f9f9f9;">
        <h2 style="color: #243024;">Reporte del {fecha_legible}</h2>
        <p style="color: #555; line-height: 1.6;">
          Estimado equipo de {nombre_reporte},<br><br>
          Adjunto encontrara el reporte automatico generado por el agente IA 
          de AgroIA, con los indicadores de cosecha y validacion estadistica.
        </p>
        <div style="background: white; border-left: 4px solid #EF9F27; padding: 15px; margin: 20px 0;">
          <strong style="color: #243024;">Documento adjunto:</strong><br>
          <span style="color: #555;">{nombre_archivo}</span>
        </div>
        <p style="color: #777; font-size: 13px; line-height: 1.6;">
          Este reporte fue generado y enviado automaticamente. Para ver mas 
          detalles en tiempo real, ingrese a la aplicacion AgroIA.
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
    
    resultados = []
    for destino in destinatarios:
        if not destino or '@' not in destino:
            resultados.append({"destino": destino, "exito": False, "error": "Correo invalido"})
            continue
        
        try:
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
                resultados.append({"destino": destino, "exito": True, "id": response.json().get('id')})
                print(f"[Auto] Enviado {tipo} a {destino}")
            else:
                error_data = response.json() if response.text else {}
                resultados.append({"destino": destino, "exito": False, 
                                   "error": error_data.get('message', f'HTTP {response.status_code}')})
                print(f"[Auto] Error enviando a {destino}: {response.status_code}")
        except Exception as e:
            resultados.append({"destino": destino, "exito": False, "error": str(e)})
            print(f"[Auto] Excepcion enviando a {destino}: {e}")
    
    return {"exito": True, "resultados": resultados}


def _ejecutar_envios_programados(forzar=False):
    """Verifica el horario actual y envia los reportes que correspondan.
    
    Args:
        forzar: si True, envia todos los reportes ignorando horario (modo test)
    
    Returns:
        dict con resumen de lo que se envio
    """
    from datetime import timezone, timedelta
    PERU_TZ = timezone(timedelta(hours=-5))
    ahora = datetime.now(timezone.utc).astimezone(PERU_TZ)
    
    dia_semana = ahora.weekday()  # 0=Lunes, 6=Domingo
    hora_actual = ahora.hour
    minuto_actual = ahora.minute
    fecha_hoy = ahora.strftime("%Y-%m-%d")
    
    resumen = {
        "hora_servidor": ahora.strftime("%Y-%m-%d %H:%M:%S (UTC-5)"),
        "dia_semana": ['Lunes','Martes','Miercoles','Jueves','Viernes','Sabado','Domingo'][dia_semana],
        "envios_ejecutados": [],
        "envios_omitidos": [],
    }
    
    for programa in PROGRAMA_ENVIOS:
        tipo = programa['tipo']
        cuadrilla = programa.get('cuadrilla')
        
        # Crear clave unica para este envio
        if cuadrilla:
            clave = f"{fecha_hoy}_{tipo}_{cuadrilla}"
            tipo_clave = f"supervisor_{cuadrilla}"
        else:
            clave = f"{fecha_hoy}_{tipo}"
            tipo_clave = tipo
        
        # Verificar si ya se envio hoy
        if clave in ENVIOS_REALIZADOS and not forzar:
            continue  # Ya se envio hoy, omitir silenciosamente
        
        # Si no es forzado, verificar dia y hora
        if not forzar:
            if dia_semana not in programa['dias']:
                continue  # No es dia de envio
            
            # Verificar hora con tolerancia (UptimeRobot llama cada 5 min)
            hora_programada = programa['hora']
            minuto_programado = programa['minuto']
            
            # Convertir todo a minutos desde medianoche para comparar
            minutos_actual = hora_actual * 60 + minuto_actual
            minutos_programado = hora_programada * 60 + minuto_programado
            
            diferencia = abs(minutos_actual - minutos_programado)
            if diferencia > TOLERANCIA_MINUTOS:
                continue  # No es la hora aun
        
        # Obtener destinatarios
        destinatarios = DESTINATARIOS.get(tipo_clave, [])
        destinatarios = [d for d in destinatarios if d]  # Filtrar vacios
        
        if not destinatarios:
            resumen["envios_omitidos"].append({
                "tipo": tipo_clave,
                "razon": "Sin destinatarios configurados"
            })
            continue
        
        # Ejecutar el envio
        print(f"[Auto] Ejecutando envio: {tipo_clave} a {len(destinatarios)} destinatarios")
        try:
            resultado = _enviar_reporte_automatico(tipo, destinatarios, cuadrilla)
            
            # Marcar como enviado (para no repetir hoy)
            if resultado.get('exito') and not forzar:
                ENVIOS_REALIZADOS.add(clave)
            
            resumen["envios_ejecutados"].append({
                "tipo": tipo_clave,
                "destinatarios": destinatarios,
                "resultado": resultado
            })
        except Exception as e:
            resumen["envios_ejecutados"].append({
                "tipo": tipo_clave,
                "error": str(e)
            })
    
    return resumen


# ============================================================
# ENDPOINT: REPORTAR PROBLEMA
# ============================================================

@app.route('/api/reportar-problema', methods=['POST'])
@rate_limit('default')
def reportar_problema():
    """
    Recibe reportes de problemas desde la app.
    Envía email al administrador con toda la info recopilada.
    """
    try:
        data = request.json or {}
        
        tipo = data.get('tipo', 'bug')
        descripcion = data.get('descripcion', '').strip()
        email_usuario = data.get('email_usuario', 'no-proporcionado')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        usuario = data.get('usuario', {})
        info_tecnica = data.get('info_tecnica', {})
        ultimas_acciones = data.get('ultimas_acciones', [])
        captura_screenshot = data.get('captura_screenshot')  # Base64
        
        if not descripcion or len(descripcion) < 10:
            return jsonify({"success": False, "error": "Descripción muy corta"}), 400
        
        # Mapeo de tipos a labels amigables
        tipos_labels = {
            'bug': '🐛 Bug o error',
            'lento': '🐢 Algo va lento',
            'duda': '❓ No entiendo cómo usar algo',
            'sugerencia': '💡 Sugerencia'
        }
        tipo_label = tipos_labels.get(tipo, '❓ Otro')
        
        # Construir el HTML del email
        fecha_legible = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        
        usuario_html = "Usuario anónimo (no autenticado)"
        if not usuario.get('anonimo'):
            usuario_html = f"""
                <strong>DNI:</strong> {usuario.get('dni', 'N/D')}<br>
                <strong>Nombre:</strong> {usuario.get('nombre', 'N/D')}<br>
                <strong>Rol:</strong> {usuario.get('rol', 'N/D')}<br>
                <strong>Cuadrilla:</strong> {usuario.get('cuadrilla') or 'N/A'}
            """
        
        info_tec_html = ""
        if info_tecnica:
            info_tec_html = f"""
            <h3 style="color:#243024; margin-top:24px;">💻 Información técnica</h3>
            <table style="width:100%; font-size:13px; border-collapse:collapse;">
                <tr><td style="padding:4px 8px; background:#f5f5dc;"><strong>URL:</strong></td><td style="padding:4px 8px;">{info_tecnica.get('url_actual', 'N/D')}</td></tr>
                <tr><td style="padding:4px 8px;"><strong>Página activa:</strong></td><td style="padding:4px 8px;">{info_tecnica.get('pagina_activa', 'N/D')}</td></tr>
                <tr><td style="padding:4px 8px; background:#f5f5dc;"><strong>Navegador:</strong></td><td style="padding:4px 8px; word-break:break-all;">{info_tecnica.get('user_agent', 'N/D')}</td></tr>
                <tr><td style="padding:4px 8px;"><strong>Plataforma:</strong></td><td style="padding:4px 8px;">{info_tecnica.get('plataforma', 'N/D')}</td></tr>
                <tr><td style="padding:4px 8px; background:#f5f5dc;"><strong>Resolución:</strong></td><td style="padding:4px 8px;">{info_tecnica.get('resolucion', 'N/D')}</td></tr>
                <tr><td style="padding:4px 8px;"><strong>Viewport:</strong></td><td style="padding:4px 8px;">{info_tecnica.get('viewport', 'N/D')}</td></tr>
                <tr><td style="padding:4px 8px; background:#f5f5dc;"><strong>Dispositivo:</strong></td><td style="padding:4px 8px;">{'Móvil' if info_tecnica.get('es_movil') else 'Escritorio'}</td></tr>
                <tr><td style="padding:4px 8px;"><strong>Online:</strong></td><td style="padding:4px 8px;">{'Sí' if info_tecnica.get('online') else 'No'}</td></tr>
                <tr><td style="padding:4px 8px; background:#f5f5dc;"><strong>Timezone:</strong></td><td style="padding:4px 8px;">{info_tecnica.get('timezone', 'N/D')}</td></tr>
            </table>
            """
        
        acciones_html = ""
        if ultimas_acciones:
            acciones_html = """
            <h3 style="color:#243024; margin-top:24px;">📋 Últimas acciones del usuario</h3>
            <table style="width:100%; font-size:12px; border-collapse:collapse; border:1px solid #ddd;">
                <tr style="background:#243024; color:white;">
                    <th style="padding:6px 8px; text-align:left;">Fecha</th>
                    <th style="padding:6px 8px; text-align:left;">Acción</th>
                    <th style="padding:6px 8px; text-align:left;">Descripción</th>
                    <th style="padding:6px 8px; text-align:center;">Estado</th>
                </tr>
            """
            for accion in ultimas_acciones[:10]:
                fecha_a = accion.get('fecha', '')[:19].replace('T', ' ')
                exitoso = '✅' if accion.get('exitoso') else '❌'
                acciones_html += f"""
                <tr>
                    <td style="padding:6px 8px; border-bottom:1px solid #eee;">{fecha_a}</td>
                    <td style="padding:6px 8px; border-bottom:1px solid #eee;"><strong>{accion.get('accion', 'N/D')}</strong></td>
                    <td style="padding:6px 8px; border-bottom:1px solid #eee;">{accion.get('descripcion', '')[:80]}</td>
                    <td style="padding:6px 8px; border-bottom:1px solid #eee; text-align:center;">{exitoso}</td>
                </tr>
                """
            acciones_html += "</table>"
        
        # Email HTML completo
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#f5f5dc; padding:20px; margin:0; color:#243024; }}
                .container {{ max-width:680px; margin:0 auto; background:white; border-radius:12px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.1); }}
                .header {{ background:linear-gradient(135deg, #243024, #639922); color:white; padding:24px; }}
                .badge {{ background:#EF9F27; color:white; padding:6px 14px; border-radius:20px; font-size:13px; font-weight:600; display:inline-block; }}
                .section {{ padding:20px 24px; border-bottom:1px solid #eee; }}
                h2 {{ color:#243024; margin:0 0 12px 0; }}
                h3 {{ color:#639922; margin:16px 0 8px 0; }}
                .descripcion {{ background:#f5f5dc; padding:14px; border-left:4px solid #EF9F27; border-radius:4px; font-size:14px; line-height:1.6; }}
                .footer {{ background:#243024; color:#94a3b8; padding:16px 24px; text-align:center; font-size:12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                        <div>
                            <h2 style="color:white; margin:0;">🆘 Nuevo reporte de problema</h2>
                            <div style="opacity:0.9; font-size:14px; margin-top:4px;">AgroIA - Sistema de validación de cosecha</div>
                        </div>
                        <div class="badge">{tipo_label}</div>
                    </div>
                </div>
                
                <div class="section">
                    <h3>📅 Fecha del reporte</h3>
                    <p style="margin:0;">{fecha_legible}</p>
                </div>
                
                <div class="section">
                    <h3>👤 Usuario que reportó</h3>
                    <p style="margin:0; font-size:13px; line-height:1.7;">{usuario_html}</p>
                    {f'<p style="margin:8px 0 0 0;"><strong>📧 Email de contacto:</strong> <a href="mailto:{email_usuario}">{email_usuario}</a></p>' if email_usuario != 'no-proporcionado' else ''}
                </div>
                
                <div class="section">
                    <h3>📝 Descripción del problema</h3>
                    <div class="descripcion">{descripcion}</div>
                </div>
                
                <div class="section">
                    {info_tec_html}
                    {acciones_html}
                </div>
                
                {('<div class="section"><h3>📸 Captura de pantalla</h3><p style="font-size:12px; color:#666;">Ver archivo adjunto</p></div>') if captura_screenshot else ''}
                
                <div class="footer">
                    AgroIA - Sistema de Reportes Automáticos<br>
                    Universidad César Vallejo · Trujillo, Perú
                </div>
            </div>
        </body>
        </html>
        """
        
        # Enviar email via Resend
        api_key = os.getenv('RESEND_API_KEY')
        if not api_key:
            print('[REPORTAR] RESEND_API_KEY no configurada, solo registrando en logs')
            return jsonify({"success": True, "message": "Reporte registrado (sin email)"})
        
        # Destinatario: tu correo personal (gerencia o el que tengas configurado)
        destinatario = os.getenv('EMAIL_GERENCIA') or os.getenv('EMAIL_JEFECAMPO')
        if not destinatario:
            print('[REPORTAR] No hay email de destino configurado')
            return jsonify({"success": True, "message": "Reporte registrado (sin destinatario)"})
        
        # Preparar adjuntos si hay captura
        attachments = []
        if captura_screenshot:
            try:
                # captura_screenshot viene como "data:image/jpeg;base64,..."
                if ',' in captura_screenshot:
                    base64_data = captura_screenshot.split(',', 1)[1]
                else:
                    base64_data = captura_screenshot
                
                attachments.append({
                    "filename": f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
                    "content": base64_data
                })
            except Exception as e:
                print(f'[REPORTAR] Error procesando screenshot: {e}')
        
        # Enviar email
        email_payload = {
            "from": os.getenv('EMAIL_FROM', 'AgroIA <onboarding@resend.dev>'),
            "to": [destinatario],
            "subject": f"[AgroIA Reporte] {tipo_label} - {fecha_legible}",
            "html": html_body
        }
        if attachments:
            email_payload["attachments"] = attachments
        
        resp = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json=email_payload,
            timeout=15
        )
        
        if resp.status_code in [200, 201]:
            print(f'[REPORTAR] Reporte enviado exitosamente a {destinatario}')
            return jsonify({
                "success": True,
                "message": "Reporte enviado exitosamente",
                "destinatario": destinatario
            })
        else:
            print(f'[REPORTAR] Error de Resend: {resp.status_code} - {resp.text}')
            return jsonify({
                "success": False,
                "error": f"Error al enviar email: {resp.status_code}"
            }), 500
    
    except Exception as e:
        print(f'[REPORTAR] Error: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/cron-automatico', methods=['GET', 'POST'])
@rate_limit('cron')
def cron_automatico():
    """Endpoint que UptimeRobot llama cada 5 minutos.
    Verifica si toca enviar reportes y los envia.
    Es GET para que UptimeRobot pueda llamarlo facil.
    """
    try:
        resumen = _ejecutar_envios_programados(forzar=False)
        return jsonify({"exito": True, **resumen})
    except Exception as e:
        import traceback
        print(f"[Cron] Error: {e}")
        print(traceback.format_exc())
        return jsonify({"exito": False, "error": str(e)}), 500


@app.route('/api/test-envio-automatico', methods=['POST'])
@rate_limit('default')
def test_envio_automatico():
    """Fuerza el envio de TODOS los reportes ignorando horario.
    Util para probar sin esperar a que sea la hora programada.
    """
    try:
        resumen = _ejecutar_envios_programados(forzar=True)
        return jsonify({"exito": True, **resumen})
    except Exception as e:
        import traceback
        print(f"[TestAuto] Error: {e}")
        print(traceback.format_exc())
        return jsonify({"exito": False, "error": str(e)}), 500


@app.route('/api/config-destinatarios', methods=['GET'])
@rate_limit('default')
def config_destinatarios():
    """Muestra la configuracion actual de destinatarios (para debugging)."""
    # Ocultar correos completos por seguridad
    config_visible = {}
    for rol, correos in DESTINATARIOS.items():
        config_visible[rol] = []
        for c in correos:
            if c and '@' in c:
                # Mostrar solo parcialmente: ju***@gmail.com
                user, dom = c.split('@')
                config_visible[rol].append(f"{user[:2]}***@{dom}")
            else:
                config_visible[rol].append("(sin configurar)")
    
    return jsonify({
        "destinatarios": config_visible,
        "programa": [
            {
                "tipo": p['tipo'] + (f" {p['cuadrilla']}" if p.get('cuadrilla') else ''),
                "dias": [['Lun','Mar','Mie','Jue','Vie','Sab','Dom'][d] for d in p['dias']],
                "hora": f"{p['hora']:02d}:{p['minuto']:02d}"
            } for p in PROGRAMA_ENVIOS
        ],
        "envios_realizados_hoy": list(ENVIOS_REALIZADOS),
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
