#!/usr/bin/env python3
"""
SUPER MICHITO 256 - Frontend Temático DOOM (KMS/DRM sin escritorio)
Incluye menú inteligente USB (pausa/reanudación), control remoto (apuntador + teclado)
y controles de reinicio/apagado.
Proyecto Final - Fundamentos de Sistemas Embebidos (FI-UNAM)
Autores: Valdes Zavala Enzo, Ortega de la Paz Rafael, Luna Velazquez Said Josue
Licencia: MIT
"""

import os
import json
import time
import socket
import struct
import select
import subprocess
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame

ROMS_DIR = Path("/opt/retroconsole/roms")
ASSETS_DIR = Path("/opt/retroconsole/assets")
EXT_MAP = {
    ".nes": "NES · 8-BIT",
    ".sfc": "SNES · 16-BIT",
    ".smc": "SNES · 16-BIT",
    ".gba": "GBA · 32-BIT",
    ".gb":  "GB · 8-BIT",
    ".gbc": "GBC · 8-BIT",
}

# Paleta DOOM (tonos rojizos, fuego y hueso con alto contraste)
BG_TOP = (38, 6, 10)
BG_BOT = (10, 4, 6)
PANEL_BG = (24, 8, 12)
HEADER_LINE = (185, 28, 28)
ROW_SEL = (92, 16, 22)
FIRE_ORANGE = (249, 115, 22)
BLOOD_RED = (220, 38, 38)
GOLD = (250, 204, 21)
TEXT_MAIN = (254, 242, 242)
TEXT_MUTE = (196, 148, 148)
KEY_BG = (42, 14, 18)
KEY_HL = (185, 28, 28)

EXIT_COMBOS = [{8, 9}, {6, 7}]
UDP_PORT = 5050

KB_ROWS = [
    list("1234567890"),
    list("QWERTYUIOP"),
    list("ASDFGHJKL"),
    ["ZXCVBNM"[i] for i in range(7)] + ["ESP", "BOR", "OK"],
]

# Matriz pixel-art 11x11 de calavera estilo retro DOOM
SKULL_BITMAP = [
    "  #######  ",
    " ######### ",
    "###########",
    "##EE###EE##",
    "##EE###EE##",
    "#####N#####",
    " ####N#### ",
    "  #######  ",
    "  # # # #  ",
    "  #######  ",
    "   #####   ",
]


def load_doom_font(size):
    """Carga AmazDOOM (.ttf) si existe en assets/, o usa una serif pesada como respaldo."""
    for fname in ("amazdoom.ttf", "AmazDooMLeft.ttf", "AmazDooMRight.ttf", "doom.ttf"):
        fpath = ASSETS_DIR / fname
        if fpath.exists():
            try:
                return pygame.font.Font(str(fpath), size)
            except Exception:
                pass
    return pygame.font.SysFont("dejavuserif", size, bold=True)


def render_doom_title(screen, text, size, x, y):
    """Renderiza texto con sombra y efecto fuego/sangre estilo logotipo DOOM."""
    font = load_doom_font(size)
    shadow = font.render(text, True, (0, 0, 0))
    crimson = font.render(text, True, BLOOD_RED)
    fire = font.render(text, True, FIRE_ORANGE)
    screen.blit(shadow, (x + 4, y + 4))
    screen.blit(crimson, (x + 2, y + 2))
    screen.blit(fire, (x, y))
    return fire.get_size()


def draw_pixel_skull(screen, x, y, scale=3, bone=TEXT_MAIN, eye=BLOOD_RED):
    """Dibuja una calavera pixel-art nítida sin depender de archivos externos."""
    for r, row in enumerate(SKULL_BITMAP):
        for c, ch in enumerate(row):
            if ch == "#":
                pygame.draw.rect(screen, bone, (x + c * scale, y + r * scale, scale, scale))
            elif ch == "E":
                pygame.draw.rect(screen, eye, (x + c * scale, y + r * scale, scale, scale))
            elif ch == "N":
                pygame.draw.rect(screen, BG_BOT, (x + c * scale, y + r * scale, scale, scale))


def draw_doom_background(screen):
    """Dibuja degradado rojizo oscuro + bordes metálicos sutiles."""
    w, h = screen.get_size()
    steps = 28
    strip_h = (h // steps) + 1
    for i in range(steps):
        t = i / max(1, steps - 1)
        r = int(BG_TOP[0] * (1 - t) + BG_BOT[0] * t)
        g = int(BG_TOP[1] * (1 - t) + BG_BOT[1] * t)
        b = int(BG_TOP[2] * (1 - t) + BG_BOT[2] * t)
        pygame.draw.rect(screen, (r, g, b), (0, i * strip_h, w, strip_h))
    # Marco exterior rojo sangre sutil
    pygame.draw.rect(screen, (100, 18, 22), (10, 10, w - 20, h - 20), 2)


def create_udp_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", UDP_PORT))
    sock.setblocking(False)
    return sock


def poll_udp(sock):
    msgs = []
    while True:
        try:
            data, _ = sock.recvfrom(4096)
            msgs.append(json.loads(data.decode("utf-8")))
        except BlockingIOError:
            break
        except Exception:
            break
    return msgs


def scan_roms(search_filter=""):
    roms = []
    if not ROMS_DIR.exists():
        return roms
    q = search_filter.strip().lower()
    for p in sorted(ROMS_DIR.rglob("*")):
        if p.is_file() and p.suffix.lower() in EXT_MAP:
            if not q or q in p.stem.lower() or q in EXT_MAP[p.suffix.lower()].lower():
                roms.append((p.stem, EXT_MAP[p.suffix.lower()], str(p)))
    return roms


def init_display():
    pygame.display.init()
    pygame.font.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.mouse.set_visible(False)
    return screen


def init_joysticks():
    pygame.joystick.quit()
    pygame.joystick.init()
    joys = []
    for i in range(pygame.joystick.get_count()):
        j = pygame.joystick.Joystick(i)
        j.init()
        joys.append(j)
    return joys


def launch_rom(rom_path, udp_sock):
    pygame.display.quit()
    env = os.environ.copy()
    env["SDL_VIDEODRIVER"] = "kmsdrm"
    cmd = [
        "/usr/games/mednafen",
        "-autosave", "1",
        "-video.driver", "softfb",
        "-video.fs", "1",
        "-sound.driver", "alsa",
        "-sound.device", "plughw:1,0",
        rom_path,
    ]
    proc = subprocess.Popen(cmd, env=env)
    pressed = set()
    js_fd = None
    reason = "USER_EXIT"
    pending_usb = None

    try:
        if os.path.exists("/dev/input/js0"):
            js_fd = os.open("/dev/input/js0", os.O_RDONLY | os.O_NONBLOCK)
        while proc.poll() is None:
            for msg in poll_udp(udp_sock):
                c = msg.get("cmd")
                if c == "USB_PAUSE":
                    reason = "USB_PAUSED"
                    proc.terminate()
                    break
                elif c == "USB_RESULT":
                    reason = "USB_PAUSED"
                    pending_usb = msg
                    proc.terminate()
                    break
                elif c == "EXIT_GAME":
                    reason = "USER_EXIT"
                    proc.terminate()
                    break
            if proc.poll() is not None or reason != "USER_EXIT":
                break
            if js_fd is not None:
                r, _, _ = select.select([js_fd], [], [], 0.08)
                if r:
                    data = os.read(js_fd, 8)
                    if len(data) == 8:
                        _, value, ev_type, number = struct.unpack("IhBB", data)
                        if ev_type & 0x01:
                            if value:
                                pressed.add(number)
                            else:
                                pressed.discard(number)
                            if any(combo.issubset(pressed) for combo in EXIT_COMBOS):
                                proc.terminate()
                                break
            else:
                time.sleep(0.08)
    finally:
        if js_fd is not None:
            os.close(js_fd)
    proc.wait()
    return reason, pending_usb


def draw_pointer(screen, px, py, visible):
    if not visible:
        return
    pts = [(px, py), (px + 18, py + 12), (px + 8, py + 13), (px + 4, py + 22)]
    pygame.draw.polygon(screen, FIRE_ORANGE, pts)
    pygame.draw.polygon(screen, TEXT_MAIN, pts, 2)


def show_usb_modal(screen, udp_sock, was_playing, initial_result=None):
    w, h = screen.get_size()
    font_b = pygame.font.SysFont("dejavusans", max(19, h // 30), bold=True)
    font_s = pygame.font.SysFont("dejavusans", max(15, h // 38))

    result = initial_result
    wait_start = time.time()
    choice = 0
    options = ["Continuar emulación", "Regresar al menú de títulos"] if was_playing else ["Regresar al menú de títulos"]
    clock = pygame.time.Clock()
    px, py, pvis = w // 2, h // 2, False

    while True:
        for msg in poll_udp(udp_sock):
            c = msg.get("cmd")
            if c == "USB_RESULT":
                result = msg
            elif result is not None:
                if c == "MOVE":
                    px = max(0, min(w - 1, px + int(msg.get("dx", 0))))
                    py = max(0, min(h - 1, py + int(msg.get("dy", 0))))
                    pvis = True
                elif c == "KEY":
                    k = msg.get("key")
                    if k in ("LEFT", "UP"):
                        choice = (choice - 1) % len(options)
                    elif k in ("RIGHT", "DOWN"):
                        choice = (choice + 1) % len(options)
                    elif k == "ENTER":
                        return options[choice]
                elif c == "CLICK":
                    return options[choice]

        if result is None and (time.time() - wait_start > 20):
            result = {"imported": [], "duplicates": [], "error": "Tiempo de espera agotado"}

        draw_doom_background(screen)
        draw_pixel_skull(screen, 64, 48, scale=3, eye=FIRE_ORANGE)
        title = "IMPORTANDO ROMS DESDE USB..." if result is None else "IMPORTACION USB COMPLETADA"
        render_doom_title(screen, title, max(28, h // 18), 112, 46)
        pygame.draw.line(screen, HEADER_LINE, (64, 114), (w - 64, 114), 2)

        if result is None:
            screen.blit(font_b.render("Analizando memoria USB y verificando duplicados (SHA-256)...", True, TEXT_MAIN), (64, 152))
            screen.blit(font_s.render("No retires la memoria USB todavía.", True, TEXT_MUTE), (64, 202))
        else:
            imp = result.get("imported", [])
            dups = result.get("duplicates", [])
            y = 144
            summary = f"ROMs nuevas importadas: {len(imp)}    |    Duplicadas omitidas: {len(dups)}"
            screen.blit(font_b.render(summary, True, GOLD if imp else TEXT_MAIN), (64, y))
            y += 58
            if imp:
                for name in imp[:6]:
                    screen.blit(font_s.render(f"+  {name[:52]}", True, TEXT_MAIN), (84, y))
                    y += 38
                if len(imp) > 6:
                    screen.blit(font_s.render(f"... y {len(imp) - 6} más", True, TEXT_MUTE), (84, y))
            else:
                screen.blit(font_s.render("Todas las ROMs encontradas en la USB ya existían en la consola.", True, TEXT_MUTE), (84, y))

            gap = 36
            btn_w = min(460, (w - 128 - gap) // max(1, len(options)))
            btn_h = 68
            btn_y = h - 172
            for i, label in enumerate(options):
                bx = 64 + i * (btn_w + gap)
                rect = pygame.Rect(bx, btn_y, btn_w, btn_h)
                if pvis and rect.collidepoint(px, py):
                    choice = i
                pygame.draw.rect(screen, ROW_SEL if i == choice else KEY_BG, rect)
                pygame.draw.rect(screen, FIRE_ORANGE if i == choice else HEADER_LINE, rect, 2)
                lbl = font_b.render(label, True, TEXT_MAIN)
                screen.blit(lbl, (bx + (btn_w - lbl.get_width()) // 2, btn_y + (btn_h - lbl.get_height()) // 2))

            pygame.draw.line(screen, HEADER_LINE, (64, h - 76), (w - 64, h - 76), 1)
            screen.blit(font_s.render("Usa la cruceta o apuntador para elegir y presiona A / Clic", True, TEXT_MUTE), (64, h - 54))
            draw_pointer(screen, px, py, pvis)

        pygame.display.flip()

        for event in pygame.event.get():
            if result is None:
                continue
            if event.type == pygame.JOYHATMOTION and (event.value[0] != 0 or event.value[1] != 0):
                choice = (choice + (1 if event.value[0] > 0 or event.value[1] < 0 else -1)) % len(options)
            elif event.type == pygame.JOYBUTTONDOWN and event.button in (0, 1, 2):
                return options[choice]
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                    choice = (choice + 1) % len(options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return options[choice]
        clock.tick(30)


def confirm_power_action(screen, udp_sock, action):
    w, h = screen.get_size()
    font_b = pygame.font.SysFont("dejavusans", max(19, h // 30), bold=True)
    font_s = pygame.font.SysFont("dejavusans", max(15, h // 38))
    label_act = "APAGAR" if action == "poweroff" else "REINICIAR"
    options = [f"Sí, {label_act}", "Cancelar"]
    choice = 1
    clock = pygame.time.Clock()
    px, py, pvis = w // 2, h // 2, False

    while True:
        for msg in poll_udp(udp_sock):
            c = msg.get("cmd")
            if c == "MOVE":
                px = max(0, min(w - 1, px + int(msg.get("dx", 0))))
                py = max(0, min(h - 1, py + int(msg.get("dy", 0))))
                pvis = True
            elif c == "KEY":
                k = msg.get("key")
                if k in ("LEFT", "RIGHT", "UP", "DOWN"):
                    choice = (choice + 1) % 2
                elif k == "ENTER":
                    return choice == 0
            elif c == "CLICK":
                return choice == 0

        draw_doom_background(screen)
        draw_pixel_skull(screen, 64, 54, scale=4, eye=BLOOD_RED)
        render_doom_title(screen, f"DESEAS {label_act} LA CONSOLA?", max(28, h // 18), 124, 58)
        pygame.draw.line(screen, HEADER_LINE, (64, 128), (w - 64, 128), 2)
        screen.blit(font_b.render("Selecciona una opción con el gamepad o el apuntador:", True, TEXT_MAIN), (64, 168))

        gap = 36
        btn_w = min(360, (w - 128 - gap) // 2)
        btn_h = 68
        btn_y = h // 2
        for i, lbl_txt in enumerate(options):
            bx = 64 + i * (btn_w + gap)
            rect = pygame.Rect(bx, btn_y, btn_w, btn_h)
            if pvis and rect.collidepoint(px, py):
                choice = i
            fill = (153, 27, 27) if (i == 0 and choice == 0) else (ROW_SEL if i == choice else KEY_BG)
            border = FIRE_ORANGE if i == choice else HEADER_LINE
            pygame.draw.rect(screen, fill, rect)
            pygame.draw.rect(screen, border, rect, 2)
            lbl = font_b.render(lbl_txt, True, TEXT_MAIN)
            screen.blit(lbl, (bx + (btn_w - lbl.get_width()) // 2, btn_y + (btn_h - lbl.get_height()) // 2))

        screen.blit(font_s.render("[Cruceta] Cambiar   |   [A] Confirmar   |   [B] Cancelar", True, TEXT_MUTE), (64, h - 54))
        draw_pointer(screen, px, py, pvis)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.JOYHATMOTION and (event.value[0] != 0 or event.value[1] != 0):
                choice = (choice + 1) % 2
            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button in (0, 2):
                    return choice == 0
                elif event.button == 1:
                    return False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    choice = (choice + 1) % 2
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return choice == 0
                elif event.key == pygame.K_ESCAPE:
                    return False
        clock.tick(30)


def draw_keyboard(screen, search_text, kb_r, kb_c, px, py, pvis):
    w, h = screen.get_size()
    font_k = pygame.font.SysFont("dejavusans", max(18, h // 32), bold=True)
    font_s = pygame.font.SysFont("dejavusans", max(18, h // 30), bold=True)

    panel_y = h - 310
    pygame.draw.rect(screen, PANEL_BG, (40, panel_y, w - 80, 250))
    pygame.draw.rect(screen, FIRE_ORANGE, (40, panel_y, w - 80, 250), 2)
    screen.blit(font_s.render(f"BUSCAR TITULO: {search_text}_", True, GOLD), (60, panel_y + 14))

    key_rects = []
    start_y = panel_y + 58
    for r_i, row in enumerate(KB_ROWS):
        kw = (w - 140) // len(row) - 6
        kh = 40
        for c_i, key in enumerate(row):
            kx = 60 + c_i * (kw + 6)
            ky = start_y + r_i * (kh + 8)
            rect = pygame.Rect(kx, ky, kw, kh)
            hovered = pvis and rect.collidepoint(px, py)
            selected = (r_i == kb_r and c_i == kb_c) or hovered
            pygame.draw.rect(screen, KEY_HL if selected else KEY_BG, rect)
            pygame.draw.rect(screen, FIRE_ORANGE if selected else HEADER_LINE, rect, 1)
            lbl = font_k.render(key, True, TEXT_MAIN)
            screen.blit(lbl, (kx + (kw - lbl.get_width()) // 2, ky + (kh - lbl.get_height()) // 2))
            key_rects.append((rect, key))
    return key_rects


def draw_ui(screen, roms, selected, scroll_offset, search_text, show_kb, kb_r, kb_c, px, py, pvis):
    w, h = screen.get_size()
    draw_doom_background(screen)

    font_item = pygame.font.SysFont("dejavusans", max(20, h // 27), bold=True)
    font_sub = pygame.font.SysFont("dejavusans", max(15, h // 38))
    eye_pulse = GOLD if int(time.time() * 2.5) % 2 == 0 else BLOOD_RED

    # Encabezado DOOM con calaveras flanqueando SUPER MICHITO 256
    draw_pixel_skull(screen, 48, 30, scale=3, eye=eye_pulse)
    tw, _ = render_doom_title(screen, "SUPER MICHITO 256", max(32, h // 16), 96, 24)
    draw_pixel_skull(screen, 96 + tw + 16, 30, scale=3, eye=eye_pulse)

    badge = f"{len(roms)} JUEGOS" + (f" · FILTRO: '{search_text}'" if search_text else "")
    count_surf = font_sub.render(badge, True, GOLD)
    screen.blit(count_surf, (96 + tw + 68, 40))

    # Botones de Reiniciar [L] y Apagar [R] arriba a la derecha
    btn_h = 38
    btn_w = 152
    power_rect = pygame.Rect(w - 48 - btn_w, 28, btn_w, btn_h)
    reboot_rect = pygame.Rect(w - 48 - btn_w * 2 - 14, 28, btn_w, btn_h)
    for rect, txt, bg_c, bd_c in [
        (reboot_rect, "[L] Reiniciar", KEY_BG, FIRE_ORANGE),
        (power_rect,  "[R] Apagar",    (110, 14, 18), BLOOD_RED),
    ]:
        hov = pvis and rect.collidepoint(px, py)
        pygame.draw.rect(screen, bd_c if hov else bg_c, rect)
        pygame.draw.rect(screen, bd_c, rect, 2)
        t = font_sub.render(txt, True, BG_BOT if hov else TEXT_MAIN)
        screen.blit(t, (rect.x + (rect.w - t.get_width()) // 2, rect.y + (rect.h - t.get_height()) // 2))

    pygame.draw.line(screen, HEADER_LINE, (48, 86), (w - 48, 86), 2)
    pygame.draw.line(screen, FIRE_ORANGE, (48, 89), (w - 48, 89), 1)

    # Lista de juegos con calavera selectora estilo DOOM 1993
    list_top = 110
    row_h = max(48, h // 13)
    bottom_reserve = 330 if show_kb else 86
    visible_rows = max(1, (h - list_top - bottom_reserve) // row_h)

    row_rects = []
    if not roms:
        screen.blit(font_item.render("No se encontraron ROMs — Inserta una USB o limpia el filtro", True, TEXT_MUTE), (48, list_top + 20))
    else:
        for idx in range(scroll_offset, min(len(roms), scroll_offset + visible_rows)):
            name, system, _ = roms[idx]
            y = list_top + (idx - scroll_offset) * row_h
            rect = pygame.Rect(44, y, w - 88, row_h - 6)
            row_rects.append((rect, idx))
            if idx == selected:
                pygame.draw.rect(screen, ROW_SEL, rect)
                pygame.draw.rect(screen, FIRE_ORANGE, rect, 2)
                draw_pixel_skull(screen, 58, y + (row_h - 34) // 2, scale=3, bone=TEXT_MAIN, eye=eye_pulse)
            name_surf = font_item.render(name[:44], True, TEXT_MAIN if idx == selected else TEXT_MUTE)
            sys_surf = font_sub.render(system, True, GOLD if idx == selected else TEXT_MUTE)
            screen.blit(name_surf, (108, y + (row_h - name_surf.get_height()) // 2 - 3))
            screen.blit(sys_surf, (w - sys_surf.get_width() - 68, y + (row_h - sys_surf.get_height()) // 2 - 3))

    key_rects = draw_keyboard(screen, search_text, kb_r, kb_c, px, py, pvis) if show_kb else []

    pygame.draw.line(screen, HEADER_LINE, (48, h - 56), (w - 48, h - 56), 2)
    help_text = "[Cruceta] Navegar | [A/B] Jugar | [Y] Desde cero | [-/+] Menú | [X] Teclado | [L] Reiniciar | [R] Apagar"
    screen.blit(font_sub.render(help_text, True, TEXT_MUTE), (48, h - 40))

    draw_pointer(screen, px, py, pvis)
    pygame.display.flip()
    return visible_rows, row_rects, key_rects, reboot_rect, power_rect


def main():
    pygame.init()
    pygame.mixer.quit()
    screen = init_display()
    joys = init_joysticks()
    udp_sock = create_udp_socket()

    search_text = ""
    roms = scan_roms(search_text)
    selected = 0
    scroll_offset = 0
    show_kb = False
    kb_r, kb_c = 0, 0
    w, h = screen.get_size()
    px, py, pvis = w // 2, h // 2, False
    clock = pygame.time.Clock()
    last_axis_move = 0.0

    def apply_key(key_str):
        nonlocal search_text, show_kb, roms, selected, scroll_offset
        if key_str == "OK":
            show_kb = False
        elif key_str == "BOR":
            search_text = search_text[:-1]
        elif key_str == "ESP":
            search_text += " "
        else:
            search_text += key_str
        roms = scan_roms(search_text)
        selected, scroll_offset = 0, 0

    running = True
    while running:
        visible_rows, row_rects, key_rects, reboot_rect, power_rect = draw_ui(
            screen, roms, selected, scroll_offset, search_text, show_kb, kb_r, kb_c, px, py, pvis
        )

        move_v = 0
        move_h = 0
        activate = False

        for msg in poll_udp(udp_sock):
            cmd = msg.get("cmd")
            if cmd in ("USB_PAUSE", "USB_RESULT"):
                show_usb_modal(screen, udp_sock, was_playing=False, initial_result=msg if cmd == "USB_RESULT" else None)
                roms = scan_roms(search_text)
                selected = min(selected, max(0, len(roms) - 1))
                pygame.event.clear()
            elif cmd == "MOVE":
                w, h = screen.get_size()
                px = max(0, min(w - 1, px + int(msg.get("dx", 0))))
                py = max(0, min(h - 1, py + int(msg.get("dy", 0))))
                pvis = True
            elif cmd == "CLICK":
                pvis = True
                if reboot_rect.collidepoint(px, py):
                    if confirm_power_action(screen, udp_sock, "reboot"):
                        subprocess.run(["sudo", "/sbin/reboot"])
                    continue
                if power_rect.collidepoint(px, py):
                    if confirm_power_action(screen, udp_sock, "poweroff"):
                        subprocess.run(["sudo", "/sbin/poweroff"])
                    continue
                hit_kb = False
                for rect, k in key_rects:
                    if rect.collidepoint(px, py):
                        apply_key(k)
                        hit_kb = True
                        break
                if not hit_kb:
                    for rect, idx in row_rects:
                        if rect.collidepoint(px, py):
                            selected = idx
                            activate = True
                            break
            elif cmd == "TOGGLE_KB":
                show_kb = not show_kb
            elif cmd == "KEY":
                k = msg.get("key")
                if k == "UP": move_v = -1
                elif k == "DOWN": move_v = 1
                elif k == "LEFT": move_h = -1
                elif k == "RIGHT": move_h = 1
                elif k == "ENTER": activate = True
            elif cmd == "TYPE":
                apply_key(msg.get("char", ""))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.JOYHATMOTION:
                hx, hy = event.value
                if hy == 1: move_v = -1
                elif hy == -1: move_v = 1
                if hx == -1: move_h = -1
                elif hx == 1: move_h = 1
            elif event.type == pygame.JOYAXISMOTION and event.axis in (0, 1):
                now = time.time()
                if now - last_axis_move > 0.22:
                    if event.axis == 1 and event.value < -0.6:
                        move_v, last_axis_move = -1, now
                    elif event.axis == 1 and event.value > 0.6:
                        move_v, last_axis_move = 1, now
                    elif event.axis == 0 and event.value < -0.6:
                        move_h, last_axis_move = -1, now
                    elif event.axis == 0 and event.value > 0.6:
                        move_h, last_axis_move = 1, now
            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button in (1, 2):
                    activate = True
                elif event.button == 0 and not show_kb and roms:
                    # Y -> borrar save state del juego seleccionado y arrancar desde cero
                    stem = Path(roms[selected][2]).stem
                    mcs_dir = Path.home() / ".mednafen" / "mcs"
                    if mcs_dir.exists():
                        for f in mcs_dir.glob(f"{stem}.*"):
                            f.unlink(missing_ok=True)
                    activate = True
                elif event.button == 3:
                    show_kb = not show_kb
                elif event.button == 4:
                    if confirm_power_action(screen, udp_sock, "reboot"):
                        subprocess.run(["sudo", "/sbin/reboot"])
                elif event.button == 5:
                    if confirm_power_action(screen, udp_sock, "poweroff"):
                        subprocess.run(["sudo", "/sbin/poweroff"])
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP: move_v = -1
                elif event.key == pygame.K_DOWN: move_v = 1
                elif event.key == pygame.K_LEFT: move_h = -1
                elif event.key == pygame.K_RIGHT: move_h = 1
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE): activate = True
                elif event.key == pygame.K_ESCAPE: running = False

        if show_kb:
            if move_v != 0:
                kb_r = (kb_r + move_v) % len(KB_ROWS)
                kb_c = min(kb_c, len(KB_ROWS[kb_r]) - 1)
            if move_h != 0:
                kb_c = (kb_c + move_h) % len(KB_ROWS[kb_r])
            if activate:
                apply_key(KB_ROWS[kb_r][kb_c])
        else:
            if move_v != 0 and roms:
                selected = (selected + move_v) % len(roms)
                if selected < scroll_offset:
                    scroll_offset = selected
                elif selected >= scroll_offset + visible_rows:
                    scroll_offset = selected - visible_rows + 1
            if activate and roms:
                _, _, rom_path = roms[selected]
                while True:
                    reason, pending_usb = launch_rom(rom_path, udp_sock)
                    screen = init_display()
                    joys = init_joysticks()
                    time.sleep(0.35)
                    pygame.event.clear()
                    if reason == "USB_PAUSED":
                        decision = show_usb_modal(screen, udp_sock, was_playing=True, initial_result=pending_usb)
                        roms = scan_roms(search_text)
                        time.sleep(0.3)
                        pygame.event.clear()
                        if decision == "Continuar emulación":
                            continue
                    break
                roms = scan_roms(search_text)
                selected = min(selected, max(0, len(roms) - 1))

        clock.tick(30)

    pygame.quit()


if __name__ == "__main__":
    main()
