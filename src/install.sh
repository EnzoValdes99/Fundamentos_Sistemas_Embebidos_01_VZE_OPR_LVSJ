#!/usr/bin/env bash
# ==============================================================================
# SUPER MICHITO 256 - Script de instalación y configuración automatizada
# Proyecto Final - Fundamentos de Sistemas Embebidos (FI-UNAM)
# Autores:
#   - Valdes Zavala Enzo
#   - Ortega de la Paz Rafael
#   - Luna Velazquez Said Josue
# Licencia: MIT
# Uso: sudo bash install.sh
# ==============================================================================

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Error: ejecuta este script con permisos de administrador (sudo bash install.sh)."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_USER="${SUDO_USER:-pi}"
TARGET_HOME="$(eval echo "~$TARGET_USER")"
INSTALL_DIR="/opt/retroconsole"

echo "[1/7] Actualizando repositorios e instalando dependencias base (sin entorno de escritorio)..."
apt-get update
apt-get install -y \
  mpv alsa-utils libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 \
  libsdl2-mixer-2.0-0 python3-pygame mednafen joystick git

echo "[2/7] Configurando permisos de usuario y salida de audio HDMI0 (ALSA)..."
usermod -aG video,render,audio,input "$TARGET_USER"
cat << 'ASND' > /etc/asound.conf
defaults.pcm.card 1
defaults.ctl.card 1
ASND

echo "[3/7] Copiando código fuente, recursos y configuración de Mednafen..."
mkdir -p "$INSTALL_DIR"/{assets,bin,config,roms/{nes,snes,gba}}
cp -f "$SCRIPT_DIR/bin/"*.py "$INSTALL_DIR/bin/"
chmod +x "$INSTALL_DIR/bin/"*.py
cp -f "$SCRIPT_DIR/assets/"* "$INSTALL_DIR/assets/" 2>/dev/null || true
cp -f "$SCRIPT_DIR/config/mednafen.cfg" "$INSTALL_DIR/config/mednafen.cfg"

mkdir -p "$TARGET_HOME/.mednafen"
cp -f "$SCRIPT_DIR/config/mednafen.cfg" "$TARGET_HOME/.mednafen/mednafen.cfg"
chown -R "$TARGET_USER:$TARGET_USER" "$INSTALL_DIR" "$TARGET_HOME/.mednafen"

echo "[4/7] Autorizando apagado y reinicio desde la interfaz de consola..."
echo "$TARGET_USER ALL=(ALL) NOPASSWD: /sbin/reboot, /sbin/poweroff" > /etc/sudoers.d/retroconsole-power
chmod 440 /etc/sudoers.d/retroconsole-power

echo "[5/7] Silenciando mensajes de arranque de Raspberry Pi OS..."
BOOT_DIR="/boot/firmware"
[[ -f "$BOOT_DIR/cmdline.txt" ]] || BOOT_DIR="/boot"

cp -n "$BOOT_DIR/config.txt" "$BOOT_DIR/config.txt.bak" || true
cp -n "$BOOT_DIR/cmdline.txt" "$BOOT_DIR/cmdline.txt.bak" || true

grep -q "^disable_splash=1" "$BOOT_DIR/config.txt" || echo -e "\ndisable_splash=1\nboot_delay=0" >> "$BOOT_DIR/config.txt"

sed -i 's/console=tty1/console=tty3/g' "$BOOT_DIR/cmdline.txt"
for param in quiet splash loglevel=0 logo.nologo vt.global_cursor_default=0 systemd.show_status=false udev.log_level=3 fbcon=map:2; do
  grep -q "$param" "$BOOT_DIR/cmdline.txt" || sed -i "s/$/ $param/" "$BOOT_DIR/cmdline.txt"
done

mkdir -p /etc/systemd/system.conf.d
cat << 'QCONF' > /etc/systemd/system.conf.d/quiet.conf
[Manager]
ShowStatus=no
LogLevel=err
QCONF

echo "kernel.printk = 0 0 0 0" > /etc/sysctl.d/99-quiet.conf
systemctl disable getty@tty1.service || true

echo "[6/7] Instalando servicios systemd y regla udev para importación USB..."
cp -f "$SCRIPT_DIR/systemd/"retro-*.service /etc/systemd/system/
sed -i "s/^User=.*/User=$TARGET_USER/" /etc/systemd/system/retro-frontend.service
sed -i "s/^User=.*/User=$TARGET_USER/" /etc/systemd/system/retro-remote.service
cp -f "$SCRIPT_DIR/udev/99-retro-usb.rules" /etc/udev/rules.d/

udevadm control --reload-rules
systemctl daemon-reload
systemctl enable retro-splash.service retro-frontend.service retro-remote.service

echo "[7/7] Instalación completa."
echo "Copia tus ROMs (.nes, .sfc, .gba) en $INSTALL_DIR/roms/ y reinicia con: sudo reboot"
