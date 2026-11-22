# SUPER MICHITO 256 — Consola de Videojuegos Retro Embebida

Proyecto Final de **Fundamentos de Sistemas Embebidos** (Facultad de Ingeniería, UNAM).

## Integrantes
- Valdes Zavala Enzo
- Ortega de la Paz Rafael
- Luna Velazquez Said Josue

## Enlaces del proyecto
- **Repositorio público:** [https://github.com/EnzoValdes99/Fundamentos_Sistemas_Embebidos_01_VZE_OPR_LVSJ](https://github.com/EnzoValdes99/Fundamentos_Sistemas_Embebidos_01_VZE_OPR_LVSJ)
- **Video-evidencia (YouTube):** PENDIENTE_AGREGAR_URL_YOUTUBE

## Características implementadas
- Sistema operativo base sobre Raspberry Pi OS Lite (64-bit) sin entorno de escritorio ni manejador de ventanas.
- Arranque silencioso directo a animación personalizada con audio (`systemd` + `mpv --vo=drm`).
- Frontend propio a pantalla completa en Python + Pygame/SDL2 (`kmsdrm`) con temática DOOM, botones de reinicio/apagado y opción de iniciar juego desde cero.
- Emulación de consolas de 8, 16 y 32 bits (NES, SNES y GBA) mediante Mednafen operada 100 % con gamepad USB (HORIPAD S).
- Importación automática de ROMs vía memoria USB (`udev` + `SHA-256` para evitar duplicados + pausa/reanudación inteligente con `-autosave 1`).
- Control remoto web local (`[http://consolaretro.local:8080](http://consolaretro.local:8080)`) con apuntador en pantalla y teclado en pantalla.

## Descarga e instalación en una Raspberry Pi OS Lite limpia

    git clone [https://github.com/EnzoValdes99/Fundamentos_Sistemas_Embebidos_01_VZE_OPR_LVSJ.git](https://github.com/EnzoValdes99/Fundamentos_Sistemas_Embebidos_01_VZE_OPR_LVSJ.git)
    cd Fundamentos_Sistemas_Embebidos_01_VZE_OPR_LVSJ/src
    sudo bash install.sh

Copia tus ROMs (`.nes`, `.sfc`, `.smc`, `.gba`) en `/opt/retroconsole/roms/{nes,snes,gba}` y reinicia con `sudo reboot`.
