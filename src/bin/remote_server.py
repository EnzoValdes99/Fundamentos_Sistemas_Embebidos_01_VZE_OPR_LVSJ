#!/usr/bin/env python3
"""
Servidor Web de Control Remoto (Apuntador + Teclado en Pantalla + Cruceta)
Proyecto Final - Fundamentos de Sistemas Embebidos (FI-UNAM)
Autores: Valdes Zavala Enzo, Ortega de la Paz Rafael, Luna Velazquez Said Josue
Licencia: MIT
"""

import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UDP_ADDR = ("127.0.0.1", 5050)
HTTP_PORT = 8080

HTML_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Control Remoto — SUPER MICHITO 256</title>
<style>
  * { box-sizing: border-box; user-select: none; -webkit-user-select: none; }
  body { margin: 0; padding: 16px; background: #0B1020; color: #F8FAFC; font-family: system-ui, sans-serif; display: flex; flex-direction: column; gap: 14px; height: 100dvh; }
  h1 { margin: 0; font-size: 18px; color: #38BDF8; text-align: center; }
  #pad { flex: 1; min-height: 200px; background: #1E293B; border: 2px solid #2563EB; border-radius: 14px; display: flex; align-items: center; justify-content: center; color: #94A3B8; font-size: 15px; touch-action: none; text-align: center; padding: 12px; }
  .row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  button { background: #1E293B; color: #F8FAFC; border: 1px solid #334155; border-radius: 10px; padding: 14px 8px; font-size: 16px; font-weight: 600; active: opacity 0.8; }
  button:active { background: #2563EB; }
  .primary { background: #1D4ED8; border-color: #38BDF8; }
  .teal { background: #0F766E; border-color: #2DD4BF; }
  .danger { background: #991B1B; border-color: #F87171; }
</style>
</head>
<body>
  <h1>Control Remoto — SUPER MICHITO 256</h1>
  <div id="pad">Desliza para mover el apuntador<br>Toca para hacer clic</div>

  <div class="row2">
    <button class="primary" onclick="send({cmd:'CLICK'})">Clic / Seleccionar</button>
    <button class="teal" onclick="send({cmd:'TOGGLE_KB'})">Teclado en pantalla</button>
  </div>

  <div class="row">
    <div></div>
    <button onclick="send({cmd:'KEY',key:'UP'})">▲</button>
    <div></div>
    <button onclick="send({cmd:'KEY',key:'LEFT'})">◀</button>
    <button class="primary" onclick="send({cmd:'KEY',key:'ENTER'})">OK</button>
    <button onclick="send({cmd:'KEY',key:'RIGHT'})">▶</button>
    <div></div>
    <button onclick="send({cmd:'KEY',key:'DOWN'})">▼</button>
    <button class="danger" onclick="send({cmd:'EXIT_GAME'})">Menú</button>
  </div>

<script>
function send(obj) {
  fetch('/cmd', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(obj)
  }).catch(() => {});
}

const pad = document.getElementById('pad');
let lastX = null, lastY = null, moved = false;

pad.addEventListener('touchstart', e => {
  const t = e.touches[0];
  lastX = t.clientX; lastY = t.clientY; moved = false;
}, {passive: false});

pad.addEventListener('touchmove', e => {
  e.preventDefault();
  const t = e.touches[0];
  const dx = Math.round((t.clientX - lastX) * 2.4);
  const dy = Math.round((t.clientY - lastY) * 2.4);
  if (Math.abs(dx) > 1 || Math.abs(dy) > 1) {
    moved = true;
    send({cmd: 'MOVE', dx, dy});
    lastX = t.clientX; lastY = t.clientY;
  }
}, {passive: false});

pad.addEventListener('touchend', () => {
  if (!moved) send({cmd: 'CLICK'});
  lastX = null; lastY = null;
});
</script>
</body>
</html>
"""


def send_udp(payload):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(json.dumps(payload).encode("utf-8"), UDP_ADDR)
    sock.close()


class RemoteHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE.encode("utf-8"))

    def do_POST(self):
        if self.path == "/cmd":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                send_udp(json.loads(body.decode("utf-8")))
            except Exception:
                pass
            self.send_response(204)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), RemoteHandler)
    server.serve_forever()
