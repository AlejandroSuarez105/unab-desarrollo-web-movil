"""Servidor estatico del frontend (solo desarrollo). Sirve la carpeta frontend. No tiene logica de negocio.
Variables: HOST (127.0.0.1), PORT (8080), RAIZ_FRONTEND (por defecto ../frontend), API_ORIGEN (https://127.0.0.1:8443).
Envia Content-Security-Policy: las paginas solo pueden hablar con el API Gateway y cargar recursos de los origenes listados."""
import os, http.server, pathlib, functools
RAIZ = pathlib.Path(os.environ.get('RAIZ_FRONTEND') or pathlib.Path(__file__).resolve().parents[1] / 'frontend')
API_ORIGEN = os.environ.get('API_ORIGEN', 'https://127.0.0.1:8443')
# Los scripts y manejadores de eventos de las paginas estan en linea ('unsafe-inline'): la politica no impide ejecutar un script inyectado,
# pero impide que envie el token a otro origen (connect-src, img-src, form-action) y que se carguen plugins, otra base o marcos ajenos.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https://images.unsplash.com https://maps.googleapis.com https://maps.gstatic.com",
    f"connect-src 'self' {API_ORIGEN}",
    "frame-src https://maps.google.com https://www.google.com",
    "object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'",
])

class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', CSP)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        super().end_headers()
srv = http.server.ThreadingHTTPServer((os.environ.get('HOST', '127.0.0.1'), int(os.environ.get('PORT', '8080'))), functools.partial(H, directory=str(RAIZ)))
srv.serve_forever()
