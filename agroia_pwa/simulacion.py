"""
============================================================
AgroIA - Simulacion de operacion completa
Universidad Cesar Vallejo - Proyecto academico
Autor: Jhonny Huipama
============================================================

Este script simula un dia completo de operacion de AgroIA en el fundo.
Genera 40 pesadas con datos realistas:
- ~75% validadas (banda verde)
- ~12% con observacion leve (banda amarilla)
- ~8% observadas (banda naranja)  
- ~5% bloqueadas por anomalia (banda roja)

ARQUITECTURA:
[simulacion.py]  ->  [agroia_servidor.py]  ->  [Datadog]
                            |
                            v
                       [AgroIA_Demo.html]
                       (ve las pesadas en tiempo real)

IMPORTANTE: Este script requiere que el servidor (agroia_servidor.py)
este corriendo en otra ventana CMD, porque envia los datos a:
http://localhost:5000/api/pesada

Si el servidor no esta corriendo, las pesadas NO llegaran ni a Datadog
ni a la app HTML.

INSTALACION (una sola vez):
    pip install requests

USO:
    1. Asegurate de que agroia_servidor.py este corriendo en otra ventana CMD
    2. Ejecuta: python agroia_simulacion.py
    3. Veras pesadas llegar en la app HTML y en Datadog en tiempo real
============================================================
"""

import time
import random
import json
import urllib.request
import urllib.error
from datetime import datetime

# ============================================================
# CONFIGURACION
# ============================================================
SERVIDOR_URL = "http://localhost:5000"

# Cuantas pesadas simular y cuanto esperar entre cada una
TOTAL_PESADAS = 40
SEGUNDOS_ENTRE_PESADAS = 6  # 40 pesadas x 6 seg = ~4 minutos

# ============================================================
# DATOS BASE (sincronizados con la app HTML y el servidor)
# ============================================================
TRABAJADORES = [
    # Cuadrilla C3 - 14 trabajadores - Marco Saldana - Lote L-23
    {"dni": "47234122", "nombre": "Juan Perez", "cuadrilla": "C3", "lote": "L-23", "historico": 24, "sigma": 4},
    {"dni": "71234567", "nombre": "Maria Quispe", "cuadrilla": "C3", "lote": "L-23", "historico": 22, "sigma": 3},
    {"dni": "73456789", "nombre": "Carlos Sanchez", "cuadrilla": "C3", "lote": "L-23", "historico": 21, "sigma": 3.5},
    {"dni": "40123456", "nombre": "Rosa Gutierrez", "cuadrilla": "C3", "lote": "L-23", "historico": 23, "sigma": 3},
    {"dni": "41234567", "nombre": "Manuel Vargas", "cuadrilla": "C3", "lote": "L-23", "historico": 25, "sigma": 4},
    {"dni": "42345678", "nombre": "Carmen Loayza", "cuadrilla": "C3", "lote": "L-23", "historico": 22, "sigma": 3},
    {"dni": "43456789", "nombre": "Luis Cabrera", "cuadrilla": "C3", "lote": "L-23", "historico": 26, "sigma": 4},
    {"dni": "44567890", "nombre": "Sandra Mejia", "cuadrilla": "C3", "lote": "L-23", "historico": 23, "sigma": 3},
    {"dni": "45678901", "nombre": "Jorge Castillo", "cuadrilla": "C3", "lote": "L-23", "historico": 24, "sigma": 3.5},
    {"dni": "46789012", "nombre": "Pilar Rodriguez", "cuadrilla": "C3", "lote": "L-23", "historico": 21, "sigma": 3},
    {"dni": "47890123", "nombre": "Andres Salinas", "cuadrilla": "C3", "lote": "L-23", "historico": 25, "sigma": 4},
    {"dni": "48901234", "nombre": "Teresa Olivos", "cuadrilla": "C3", "lote": "L-23", "historico": 23, "sigma": 3},
    {"dni": "49012345", "nombre": "Ricardo Paredes", "cuadrilla": "C3", "lote": "L-23", "historico": 22, "sigma": 3},
    {"dni": "50123456", "nombre": "Monica Rios", "cuadrilla": "C3", "lote": "L-23", "historico": 24, "sigma": 3.5},
    # Cuadrilla C5 - 12 trabajadores - Patricia Chavez - Lote L-08
    {"dni": "44556677", "nombre": "Pedro Rojas", "cuadrilla": "C5", "lote": "L-08", "historico": 19, "sigma": 3},
    {"dni": "78912345", "nombre": "Lucia Mendoza", "cuadrilla": "C5", "lote": "L-08", "historico": 25, "sigma": 3.5},
    {"dni": "65432198", "nombre": "Ana Torres", "cuadrilla": "C5", "lote": "L-08", "historico": 23, "sigma": 3},
    {"dni": "51234567", "nombre": "Hugo Velarde", "cuadrilla": "C5", "lote": "L-08", "historico": 20, "sigma": 3},
    {"dni": "52345678", "nombre": "Beatriz Nunez", "cuadrilla": "C5", "lote": "L-08", "historico": 22, "sigma": 3},
    {"dni": "53456789", "nombre": "Felipe Morales", "cuadrilla": "C5", "lote": "L-08", "historico": 24, "sigma": 3.5},
    {"dni": "54567890", "nombre": "Karina Espinoza", "cuadrilla": "C5", "lote": "L-08", "historico": 21, "sigma": 3},
    {"dni": "55678901", "nombre": "Daniel Pacheco", "cuadrilla": "C5", "lote": "L-08", "historico": 23, "sigma": 3.5},
    {"dni": "56789012", "nombre": "Liliana Bazan", "cuadrilla": "C5", "lote": "L-08", "historico": 22, "sigma": 3},
    {"dni": "57890123", "nombre": "Eduardo Romero", "cuadrilla": "C5", "lote": "L-08", "historico": 20, "sigma": 3},
    {"dni": "58901234", "nombre": "Veronica Quiroz", "cuadrilla": "C5", "lote": "L-08", "historico": 24, "sigma": 3.5},
    {"dni": "59012345", "nombre": "Miguel Sandoval", "cuadrilla": "C5", "lote": "L-08", "historico": 21, "sigma": 3},
    # Cuadrilla C7 - 9 trabajadores - Luis Mendoza - Lote L-17
    {"dni": "12345678", "nombre": "Roberto Diaz", "cuadrilla": "C7", "lote": "L-17", "historico": 28, "sigma": 4},
    {"dni": "98765432", "nombre": "Patricia Vargas", "cuadrilla": "C7", "lote": "L-17", "historico": 26, "sigma": 3.5},
    {"dni": "60123456", "nombre": "Ivan Cardenas", "cuadrilla": "C7", "lote": "L-17", "historico": 27, "sigma": 4},
    {"dni": "61234567", "nombre": "Norma Aguirre", "cuadrilla": "C7", "lote": "L-17", "historico": 25, "sigma": 3},
    {"dni": "62345678", "nombre": "Oscar Leon", "cuadrilla": "C7", "lote": "L-17", "historico": 28, "sigma": 4},
    {"dni": "63456789", "nombre": "Diana Flores", "cuadrilla": "C7", "lote": "L-17", "historico": 26, "sigma": 3.5},
    {"dni": "64567890", "nombre": "Walter Luna", "cuadrilla": "C7", "lote": "L-17", "historico": 27, "sigma": 4},
    {"dni": "65678901", "nombre": "Estela Vidal", "cuadrilla": "C7", "lote": "L-17", "historico": 25, "sigma": 3},
    {"dni": "66789012", "nombre": "Fernando Avila", "cuadrilla": "C7", "lote": "L-17", "historico": 26, "sigma": 3.5},
]

# Parametros de validacion (igual que la app y el servidor)
UMBRAL_VERDE = 1.5
UMBRAL_AMARILLO = 2.0
UMBRAL_NARANJA = 2.5

# Estadisticas locales
stats = {
    "total": 0,
    "validadas": 0,
    "observadas_leve": 0,
    "observadas": 0,
    "bloqueadas": 0,
    "kg_totales": 0.0,
    "errores": 0,
}

# ============================================================
# COMUNICACION CON EL SERVIDOR
# ============================================================
def verificar_servidor():
    """Verifica que el servidor este corriendo antes de empezar"""
    try:
        req = urllib.request.Request(SERVIDOR_URL + "/api/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False

def enviar_pesada_al_servidor(trabajador, kg, horas):
    """Envia la pesada al servidor, que se encarga de procesar
    el z-score, enviar a Datadog y guardar en memoria para la app HTML."""
    payload = {
        "nombre": trabajador["nombre"],
        "dni": trabajador["dni"],
        "cuadrilla": trabajador["cuadrilla"],
        "lote": trabajador["lote"],
        "kg": kg,
        "horas": horas,
        "historico": trabajador["historico"],
        "sigma": trabajador["sigma"],
        "tiempo_validacion_ms": random.randint(200, 1000),
        "origen": "simulacion"
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            SERVIDOR_URL + "/api/pesada",
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                respuesta = json.loads(resp.read().decode('utf-8'))
                return respuesta
            return None
    except Exception as e:
        stats["errores"] += 1
        return None

# ============================================================
# GENERAR PESADA SIMULADA REALISTA
# ============================================================
def generar_pesada():
    """Genera una pesada simulada con distribucion realista"""
    trabajador = random.choice(TRABAJADORES)
    
    # Decidir el escenario segun probabilidades
    rand = random.random()
    
    if rand < 0.75:
        # Banda VERDE: productividad normal (z entre -1.5 y +1.5)
        z_objetivo = random.uniform(-1.4, 1.4)
    elif rand < 0.87:
        # Banda AMARILLA: ligeramente fuera (z entre 1.5 y 2.0)
        z_objetivo = random.choice([-1, 1]) * random.uniform(1.5, 2.0)
    elif rand < 0.95:
        # Banda NARANJA: significativamente fuera (z entre 2.0 y 2.5)
        z_objetivo = random.choice([-1, 1]) * random.uniform(2.0, 2.5)
    else:
        # Banda ROJA: anomalia (z mayor a 2.5)
        z_objetivo = random.choice([-1, 1]) * random.uniform(2.5, 5.0)
    
    # Calcular kg que producirian ese z-score
    horas = random.choice([4, 4, 4, 4, 6, 6, 8])
    productividad = trabajador["historico"] + (z_objetivo * trabajador["sigma"])
    productividad = max(2, productividad)
    kg = round(productividad * horas, 1)
    
    return trabajador, kg, horas

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 65)
    print("AgroIA - Simulacion de operacion completa")
    print("Universidad Cesar Vallejo - Proyecto academico")
    print("=" * 65)
    print()
    print(f"Inicio: {datetime.now().strftime('%H:%M:%S')}")
    print(f"Servidor destino: {SERVIDOR_URL}")
    print(f"Trabajadores cargados: {len(TRABAJADORES)}")
    print(f"Pesadas a simular: {TOTAL_PESADAS}")
    print(f"Duracion estimada: ~{TOTAL_PESADAS * SEGUNDOS_ENTRE_PESADAS // 60} minutos")
    print()
    
    # Verificar que el servidor este corriendo
    print("Verificando conexion con el servidor...")
    if not verificar_servidor():
        print()
        print("  >>> ERROR: No se puede conectar con el servidor <<<")
        print()
        print(f"  El servidor debe estar corriendo en {SERVIDOR_URL}")
        print(f"  Abre otra ventana CMD y ejecuta:")
        print(f"      python agroia_servidor.py")
        print(f"  Despues vuelve a ejecutar esta simulacion.")
        print()
        input("Presiona Enter para salir...")
        return
    
    print("  Servidor conectado correctamente")
    print()
    print("Iniciando simulacion...")
    print("-" * 65)
    
    for i in range(1, TOTAL_PESADAS + 1):
        # Generar pesada simulada
        trabajador, kg, horas = generar_pesada()
        
        # Enviar al servidor (que la procesa, envia a Datadog y la guarda
        # en memoria para que la app HTML la vea)
        respuesta = enviar_pesada_al_servidor(trabajador, kg, horas)
        
        if respuesta:
            estado = respuesta.get("estado", "?")
            color = respuesta.get("color", "?")
            z_score = respuesta.get("z_score", 0)
            productividad = respuesta.get("productividad", 0)
            motivo = respuesta.get("motivo", "")
            
            stats["total"] += 1
            stats["kg_totales"] += kg
            if color == "green" or color == "yellow":
                stats["validadas"] += 1
            elif color == "orange":
                stats["observadas"] += 1
            elif color == "red":
                stats["bloqueadas"] += 1
            
            simbolo = {"green": "[OK]", "yellow": "[!] ", "orange": "[!!]", "red": "[X] "}.get(color, "[?]")
            
            print(f"{simbolo} [{i:>2}/{TOTAL_PESADAS}] {trabajador['nombre']:<20} "
                  f"({trabajador['cuadrilla']}) {trabajador['lote']} -> "
                  f"{kg:>6.1f} kg/{horas}h = {productividad:>5.1f} kg/h "
                  f"| z={z_score:+5.2f} | {estado}")
            
            if color != "green":
                print(f"           motivo: {motivo}")
        else:
            print(f"[ERROR] [{i:>2}/{TOTAL_PESADAS}] Error enviando pesada al servidor")
        
        # Pausa entre pesadas (excepto la ultima)
        if i < TOTAL_PESADAS:
            time.sleep(SEGUNDOS_ENTRE_PESADAS)
    
    print("-" * 65)
    print()
    print("RESUMEN DE LA SIMULACION:")
    print("-" * 65)
    print(f"  Total pesadas procesadas:     {stats['total']}")
    print(f"  Validadas (verde/amarilla):   {stats['validadas']}")
    print(f"  Observadas (banda naranja):   {stats['observadas']}")
    print(f"  Bloqueadas (banda roja):      {stats['bloqueadas']}")
    print(f"  Kg totales cosechados:        {stats['kg_totales']:.1f} kg")
    print(f"  Errores de envio:             {stats['errores']}")
    print()
    print(f"Fin: {datetime.now().strftime('%H:%M:%S')}")
    print()
    print("Las pesadas estan visibles en:")
    print("  - La app AgroIA_Demo.html (KPIs, tabla, reporte ejecutivo)")
    print("  - Dashboard de Datadog (metricas y logs)")
    print()
    print("=" * 65)
    input("Presiona Enter para cerrar...")

if __name__ == "__main__":
    main()
