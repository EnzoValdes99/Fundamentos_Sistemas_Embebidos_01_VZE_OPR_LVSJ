#!/usr/bin/env python3
"""
Daemon de importación automática de ROMs por USB con deduplicación SHA-256
Proyecto Final - Fundamentos de Sistemas Embebidos (FI-UNAM)
Autores: Valdes Zavala Enzo, Ortega de la Paz Rafael, Luna Velazquez Said Josue
Licencia: MIT
"""

import os
import sys
import json
import time
import shutil
import socket
import hashlib
import subprocess
from pathlib import Path

ROMS_DIR = Path("/opt/retroconsole/roms")
MOUNT_POINT = Path("/mnt/usb_import")
UDP_ADDR = ("127.0.0.1", 5050)

EXT_FOLDER = {
    ".nes": "nes",
    ".sfc": "snes",
    ".smc": "snes",
    ".gba": "gba",
    ".gb":  "gba",
    ".gbc": "gba",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def send_udp(payload):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(json.dumps(payload).encode("utf-8"), UDP_ADDR)
    sock.close()


def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    dev = sys.argv[1]
    MOUNT_POINT.mkdir(parents=True, exist_ok=True)

    # Montar en solo lectura
    res = subprocess.run(["mount", "-o", "ro,noexec,nosuid", dev, str(MOUNT_POINT)])
    if res.returncode != 0:
        sys.exit(0)

    try:
        usb_roms = [
            p for p in MOUNT_POINT.rglob("*")
            if p.is_file() and p.suffix.lower() in EXT_FOLDER and not p.name.startswith("._")
        ]
        if not usb_roms:
            return

        # 1. Pausar emulación en el frontend
        send_udp({"cmd": "USB_PAUSE"})
        time.sleep(0.8)

        # 2. Indexar hashes existentes para evitar duplicados
        existing_hashes = set()
        for p in ROMS_DIR.rglob("*"):
            if p.is_file() and p.suffix.lower() in EXT_FOLDER:
                existing_hashes.add(sha256_file(p))

        imported = []
        duplicates = []

        for rom in usb_roms:
            digest = sha256_file(rom)
            if digest in existing_hashes:
                duplicates.append(rom.name)
                continue
            target_dir = ROMS_DIR / EXT_FOLDER[rom.suffix.lower()]
            target_dir.mkdir(parents=True, exist_ok=True)
            dest = target_dir / rom.name
            shutil.copy2(rom, dest)
            subprocess.run(["chown", "pi:pi", str(dest)])
            existing_hashes.add(digest)
            imported.append(rom.name)

        subprocess.run(["sync"])
        # 3. Enviar resultado al menú inteligente
        send_udp({"cmd": "USB_RESULT", "imported": imported, "duplicates": duplicates})
    finally:
        subprocess.run(["umount", str(MOUNT_POINT)])


if __name__ == "__main__":
    main()
