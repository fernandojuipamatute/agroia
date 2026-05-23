# AgroIA — Agente IA de Validación de Cosecha

Sistema de validación estadística de cosecha para agroindustrias peruanas.

## Arquitectura

```
                 USUARIOS (profesor, supervisores, RR.HH.)
                            │
                            │
        ┌───────────────────▼───────────────────┐
        │  Frontend (PWA instalable en celular)  │
        │  https://agroia-app.onrender.com        │
        └───────────────────┬───────────────────┘
                            │
                            │ API REST
                            ▼
        ┌───────────────────────────────────────┐
        │  Backend Python Flask                   │
        │  https://agroia-api.onrender.com        │
        └───────────────────┬───────────────────┘
                            │
                            ▼
                       ┌─────────┐
                       │ Datadog │
                       └─────────┘
```

## Estructura del proyecto

```
agroia_pwa/
├── server.py              # Backend Python Flask
├── simulacion.py          # Script de simulación
├── requirements.txt       # Dependencias Python
├── render.yaml           # Configuración de despliegue
│
└── public/               # Frontend estático
    ├── index.html        # App PWA
    ├── manifest.json     # Manifiesto PWA
    ├── service-worker.js # Service Worker offline
    └── icons/            # Íconos en varios tamaños
```

## Tecnología

- **Frontend**: HTML5 + CSS3 + JavaScript vanilla (PWA)
- **Backend**: Python 3.11 + Flask + Gunicorn
- **Monitoreo**: Datadog API
- **Hosting**: Render.com (plan gratuito)

## Despliegue

Ver `INSTRUCCIONES_DESPLIEGUE.md` para guía paso a paso.

## Configuración local

### Servidor
```bash
pip install -r requirements.txt
export DATADOG_API_KEY=tu_clave_aqui
python server.py
```

### Frontend
Abrir `public/index.html` en cualquier navegador.

## Autor

Jhonny Huipama — Universidad César Vallejo, Trujillo

Curso de Inteligencia Artificial · 2026
