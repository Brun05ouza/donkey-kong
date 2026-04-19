"""
╔══════════════════════════════════════════════════════╗
║          DONKEY KONG  –  Python / PyOpenGL           ║
║  Controles:                                          ║
║    ← → / A D  : mover                               ║
║    SPACE / W  : pular                                ║
║    ↑ ↓        : escada (↑ na base / ↓ no topo)       ║
║    ENTER      : confirmar menu                       ║
║    ESC        : sair                                 ║
╚══════════════════════════════════════════════════════╝
"""

import pygame
from pygame.locals import *
from OpenGL.GL import *
import random
import math
import sys
import re
import base64
from io import BytesIO
from collections import deque
from pathlib import Path

# ─── Dimensões & física ──────────────────────────────────────────
W, H      = 800, 600
FPS       = 60
GRAVITY   = -0.38
# Pulo só o necessário para saltar barril (r≈12); calibrado com GRAVITY actual
JUMP_FORCE= 5.08
PLY_SPD   =  2.38
LAD_SPD   =  1.92
BAR_SPD   =  2.55
BAR_ROLL_SMOOTH = 0.42
MAX_FALL  = -15.0
# Barril marrom: queda mais lenta (mais tempo para desviar)
BARREL_GRAVITY   = -0.27
BARREL_MAX_FALL  = -9.2
DROP_VY_END      = -1.46
# Margem nas pontas onde o barril cai sempre; no meio pode cair ao acaso (estilo DK).
GIRDER_END_MARGIN = 14
BARREL_RANDOM_DROP_FR = 0.00165  # probabilidade / frame (~6% por s em 60 FPS) no tramo central
BARREL_RANDOM_DROP_INSET = 38   # recuo extra em relação à ponta para a queda aleatória
# Barril azul: lanço em arco para o jogador (como o original, ligeiramente mais lento).
# Ao apoiar na mesma viga que o jogador, o rolamento segue em direção a ele (cx), não à inclinação.
BLUE_LAUNCH_SPD = 2.65
BLUE_LAUNCH_VERTICAL = 0.76
BLUE_AIR_DRAG = 0.987
BLUE_BAR_ROLL_SPD = 1.55
BLUE_BAR_HOME_ALIGN = 10.0  # px: se já estiver junto ao Mario, não força vx
_BASE_DIR = Path(__file__).resolve().parent

# ─── Paleta de cores (R, G, B  de 0.0 a 1.0) ────────────────────
BG    = (1.00, 1.00, 1.00)
BG2   = (1.00, 1.00, 1.00)
PLT   = (0.42, 0.22, 0.06)
PLT2  = (0.58, 0.36, 0.12)
PLT_RAIL = (0.35, 0.35, 0.38)
SKN   = (0.92, 0.72, 0.50)
RED   = (0.90, 0.12, 0.12)
BLUE  = (0.20, 0.45, 1.00)
NAV   = (0.10, 0.12, 0.80)
BRN   = (0.55, 0.25, 0.03)
YEL   = (0.82, 0.68, 0.10)
WHT   = (1.00, 1.00, 1.00)
BLK   = (0.00, 0.00, 0.00)
DKC   = (0.45, 0.22, 0.00)
PNK   = (1.00, 0.45, 0.80)
# Vigas segmentadas (efeito arcade)
PLT_STEP_A = (0.56, 0.33, 0.10)
PLT_STEP_B = (0.46, 0.26, 0.07)
PLT_GAP_CRK = (0.05, 0.04, 0.08)
PLT_CAP_BL = (0.38, 0.22, 0.06)
PLT_LIP_HI = (0.72, 0.46, 0.16)

# ─── Plataformas (x_esq, y_esq, x_dir, y_dir, espessura) ────────
#  Inclinações alternadas criam o zigue-zague clássico dos barris:
#    slope < 0  →  plataforma desce para a direita  →  barril rola DIREITA
#    slope > 0  →  plataforma sobe  para a direita  →  barril rola ESQUERDA
#  Extremidades alternadas (em relação ao topo): nível abaixo do topo desloca
#  para a direita, o seguinte para a esquerda, etc., para haver “vazio” sob
#  a quina da viga onde o barril cai e continua a rolar.
PLATS = [
    ( 12,  90, 730,  70, 14),   # Andar 0 – base,    slope ↘  (mais à esquerda)
    ( 52, 175, 798, 195, 14),   # Andar 1            slope ↗  (à direita)
    ( 12, 280, 730, 260, 14),   # Andar 2            slope ↘  (à esquerda)
    ( 70, 365, 798, 385, 14),   # Andar 3            slope ↗  (à direita)
    ( 30, 470, 770, 450, 14),   # Andar 4 – topo DK (referência; igual ao DK clássico)
]

# ─── Escadas (x_centro, y_baixo, y_cima, largura) ────────────────
LADS = [
    (680,  72, 193, 26),   # andar 0 → 1  direita
    (150,  87, 178, 26),   # andar 0 → 1  esquerda
    (380, 185, 271, 26),   # andar 1 → 2  meio-direita
    (570, 190, 265, 26),   # andar 1 → 2  direita
    (150, 277, 368, 26),   # andar 2 → 3  esquerda
    (520, 267, 378, 26),   # andar 2 → 3  direita
    (380, 375, 461, 26),   # andar 3 → 4  meio
    (600, 380, 455, 26),   # andar 3 → 4  direita
]

# ════════════════════════════════════════════════════════════════
#  FUNÇÕES AUXILIARES
# ════════════════════════════════════════════════════════════════

def plat_y(p, px):
    """Retorna o y da superfície da plataforma na posição px."""
    x1, y1, x2, y2, _ = p
    if x1 <= px <= x2:
        t = (px - x1) / (x2 - x1)
        return y1 + t * (y2 - y1)
    return None


def plat_max_y_under_span(p, x_left, x_right):
    """Maior y da superfície ao longo de um intervalo em X (apoio conservador num barril)."""
    x1, _, x2, _, _ = p
    lo = max(x_left, x1)
    hi = min(x_right, x2)
    if lo > hi:
        return None
    sy_lo = plat_y(p, lo)
    sy_hi = plat_y(p, hi)
    sy_mid = plat_y(p, (lo + hi) * 0.5)
    ys = [v for v in (sy_lo, sy_mid, sy_hi) if v is not None]
    return max(ys) if ys else None


def plat_index_underfoot(cx, foot_y, tol=14):
    """Índice da plataforma em que o pé (foot_y) está apoiado, ou None."""
    best_i, best_sy = None, -1e9
    for i, p in enumerate(PLATS):
        sy = plat_y(p, cx)
        if sy is None:
            continue
        if foot_y <= sy + tol and foot_y >= sy - tol * 2 and sy > best_sy:
            best_sy = sy
            best_i = i
    return best_i


def gl_rect(x, y, w, h, c):
    glColor3f(*c)
    glBegin(GL_QUADS)
    glVertex2f(x,     y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x,     y + h)
    glEnd()


def gl_quad4(pts, c):
    """Quadrilátero com 4 vértices (x,y) em sentido horário."""
    glColor3f(*c)
    glBegin(GL_QUADS)
    for v in pts:
        glVertex2f(*v)
    glEnd()


def gl_circle(cx, cy, r, c, seg=20):
    glColor3f(*c)
    glBegin(GL_TRIANGLE_FAN)
    glVertex2f(cx, cy)
    for i in range(seg + 1):
        a = 2 * math.pi * i / seg
        glVertex2f(cx + r * math.cos(a), cy + r * math.sin(a))
    glEnd()


# ════════════════════════════════════════════════════════════════
#  DESENHO DOS ELEMENTOS
# ════════════════════════════════════════════════════════════════

def draw_plat(p, plat_idx=0):
    """
    Viga estilo DK: degraus horizontais ao longo da rampa, segmentos alternados,
    extremidades diferentes — entrada (chapa) vs. lado da quebra (fenda + lábio).
    """
    x1, y1, x2, y2, th = p
    slope = (y2 - y1) / max(x2 - x1, 1e-6)
    roll_right = slope < 0
    dx = x2 - x1
    n_seg = 26
    rail_h = max(4, th // 5)

    # --- Corpo em degraus (topo horizontal por segmento, efeito “serra”) ---
    for i in range(n_seg):
        t0 = i / n_seg
        t1 = (i + 1) / n_seg
        xa = x1 + t0 * dx
        xb = x1 + t1 * dx
        ya = y1 + t0 * (y2 - y1)
        yb = y1 + t1 * (y2 - y1)
        y_tread = yb if roll_right else ya
        col = PLT_STEP_A if (i + plat_idx) % 2 == 0 else PLT_STEP_B
        gl_quad4([(xa, y_tread), (xb, y_tread), (xb, y_tread - 3), (xa, y_tread - 3)], PLT2)
        gl_quad4(
            [(xa, y_tread - 3), (xb, y_tread - 3), (xb, y_tread - th), (xa, y_tread - th)],
            col,
        )
        if i > 0:
            ris = abs(ya - yb)
            if ris > 0.8:
                gl_rect(xa - 1.8, min(ya, yb) - th * 0.15, 3.6, ris + th * 0.25, PLT_GAP_CRK)
        if i % 4 == 2:
            mx = (xa + xb) * 0.5
            my = y_tread - 1.5
            gl_circle(mx, my, 1.6, PLT_CAP_BL)

    # Trilho metálico ao longo da rampa (só contorno superior)
    gl_quad4(
        [(x1 - 2, y1), (x2 + 2, y2), (x2 + 2, y2 - rail_h), (x1 - 2, y1 - rail_h)],
        PLT_RAIL,
    )

    # --- Extremidades assimétricas (onde o barril cai vs. onde “entra” na viga) ---
    if roll_right:
        # Quebra à DIREITA (x₂): fenda escura + lábio claro (o barril cai aqui)
        sy2 = y2
        gl_rect(x2 - 5, sy2 - th - 3, 6, th + 8, PLT_GAP_CRK)
        gl_quad4(
            [
                (x2 - 18, sy2),
                (x2 + 2, sy2),
                (x2 + 2, sy2 - 4),
                (x2 - 18, sy2 - 4),
            ],
            PLT_LIP_HI,
        )
        gl_rect(x2 - 14, sy2 - th - 1, 10, 3, (0.12, 0.06, 0.02))
        # Entrada à ESQUERDA (x₁): chapa de apoio mais maciça
        sy1 = y1
        gl_quad4(
            [(x1 - 8, sy1), (x1 + 6, sy1), (x1 + 6, sy1 - th - 1), (x1 - 8, sy1 - th - 1)],
            PLT_CAP_BL,
        )
        gl_circle(x1 + 2, sy1 - th * 0.35, 2.0, PLT_LIP_HI)
        gl_circle(x1 + 5, sy1 - th * 0.65, 1.6, PLT_CAP_BL)
    else:
        # Rampa para a esquerda: quebra à ESQUERDA, entrada à DIREITA
        sy1 = y1
        sy2 = y2
        gl_rect(x1 - 3, sy1 - th - 3, 6, th + 8, PLT_GAP_CRK)
        gl_quad4(
            [
                (x1 - 4, sy1),
                (x1 + 16, sy1),
                (x1 + 16, sy1 - 4),
                (x1 - 4, sy1 - 4),
            ],
            PLT_LIP_HI,
        )
        gl_rect(x1 + 6, sy1 - th - 1, 10, 3, (0.12, 0.06, 0.02))
        gl_quad4(
            [(x2 - 6, sy2), (x2 + 8, sy2), (x2 + 8, sy2 - th - 1), (x2 - 6, sy2 - th - 1)],
            PLT_CAP_BL,
        )
        gl_circle(x2 - 2, sy2 - th * 0.35, 2.0, PLT_LIP_HI)
        gl_circle(x2 - 5, sy2 - th * 0.65, 1.6, PLT_CAP_BL)


def draw_ladder(lad):
    lx, yb, yt, lw = lad
    # Trilhos
    gl_rect(lx,         yb, 4, yt - yb, YEL)
    gl_rect(lx + lw - 4, yb, 4, yt - yb, YEL)
    # Degraus
    steps = max(2, int((yt - yb) / 18))
    for i in range(steps + 1):
        ry = yb + i * (yt - yb) / steps
        gl_rect(lx, ry - 2, lw, 4, YEL)


def draw_player(x, y, w, h, facing, blink):
    if blink:
        return
    hw = w // 2
    # Pernas
    gl_rect(x + 2,       y,       hw - 3, h // 4, NAV)
    gl_rect(x + hw + 1,  y,       hw - 3, h // 4, NAV)
    # Corpo
    gl_rect(x,           y + h // 4, w, h // 2, RED)
    # Cabeça
    gl_circle(x + w / 2, y + h * 0.82, w / 2 - 2, SKN)
    # Chapéu
    gl_rect(x + 3, int(y + h - w / 4), w - 6, int(w / 4), BLUE)
    # Braço
    ax = (x + w - 2) if facing > 0 else (x - 7)
    gl_rect(ax, y + h // 3, 8, 5, SKN)


def draw_barrel(x, y, r, angle, blue=False):
    cx, cy = x + r, y + r
    if blue:
        outer = (0.12, 0.35, 0.95)
        inner = (0.25, 0.55, 1.00)
        rivet = (0.85, 0.90, 1.00)
    else:
        outer = BRN
        inner = (0.40, 0.18, 0.02)
        rivet = (0.20, 0.08, 0.00)
    gl_circle(cx, cy, r,       outer)
    gl_circle(cx, cy, r * 0.6, inner)
    # Aros / rebites
    for off in (0.0, math.pi):
        a  = angle + off
        bx = cx + r * 0.55 * math.cos(a) - 2
        by = cy + r * 0.55 * math.sin(a) - 2
        gl_rect(bx, by, 4, 4, rivet)


def draw_dk(x, y, frame):
    bw, bh = 72, 82
    # Corpo
    gl_rect(x,      y,      bw,      bh,      DKC)
    gl_rect(x + 14, y + 20, bw - 28, bh - 30, (0.60, 0.35, 0.05))
    # Cabeça
    gl_circle(x + bw / 2, y + bh + 22, 27, (0.38, 0.18, 0.00))
    # Olhos
    for ex, dx in ((-10, -10), (10, 10)):
        gl_circle(x + bw / 2 + ex, y + bh + 25, 7, WHT)
        gl_circle(x + bw / 2 + ex, y + bh + 25, 3, BLK)
    # Narinas
    gl_circle(x + bw / 2 - 5, y + bh + 10, 4, (0.20, 0.08, 0.00))
    gl_circle(x + bw / 2 + 5, y + bh + 10, 4, (0.20, 0.08, 0.00))
    # Braços animados
    if frame == 0:
        gl_rect(x - 22,      y + bh - 8,  26, 16, DKC)
        gl_rect(x + bw - 4,  y + bh - 22, 26, 16, DKC)
    else:
        gl_rect(x - 22,      y + bh - 22, 26, 16, DKC)
        gl_rect(x + bw - 4,  y + bh - 8,  26, 16, DKC)


def draw_princess(x, y):
    gl_rect(x,     y,      32, 44, PNK)
    gl_rect(x + 4, y + 44, 24, 16, (0.85, 0.55, 0.85))
    gl_circle(x + 16, y + 70, 14, SKN)
    gl_rect(x + 3,  y + 60, 26, 18, (0.85, 0.55, 0.10))
    gl_rect(x + 6,  y + 78, 20,  8, (1.00, 0.85, 0.00))


# ════════════════════════════════════════════════════════════════
#  TEXTO (Pygame Surface → Textura OpenGL)
# ════════════════════════════════════════════════════════════════

def render_text(surf, x, y):
    data = pygame.image.tostring(surf, "RGBA", True)
    tw, th = surf.get_width(), surf.get_height()
    tid = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tid)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, data)
    glEnable(GL_TEXTURE_2D)
    glColor4f(1, 1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(x,      y)
    glTexCoord2f(1, 0); glVertex2f(x + tw, y)
    glTexCoord2f(1, 1); glVertex2f(x + tw, y + th)
    glTexCoord2f(0, 1); glVertex2f(x,      y + th)
    glEnd()
    glDisable(GL_TEXTURE_2D)
    glDeleteTextures([tid])


def find_asset(filename):
    for folder in (_BASE_DIR, _BASE_DIR / "assets"):
        p = folder / filename
        if p.is_file():
            return p
    return None


def texture_from_surface(surf):
    """Cria textura OpenGL reutilizável a partir de Surface RGBA."""
    data = pygame.image.tostring(surf, "RGBA", True)
    tw, th = surf.get_width(), surf.get_height()
    tid = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tid)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, data)
    return tid, tw, th


def mask_sprite_outer_background(surf, dark_rgb_sum=95, white_min=248):
    """
    Deixa transparente o fundo que encosta à borda da imagem (caixa preta/branca).
    Usa propagação a partir das margens para não apagar preto no interior do boneco.
    """
    s = surf.convert_alpha()
    w, h = s.get_width(), s.get_height()
    if w < 2 or h < 2:
        return s

    def treat_as_background(r, g, b, a):
        if a < 12:
            return True
        if r >= white_min and g >= white_min and b >= white_min:
            return True
        return (r + g + b) <= dark_rgb_sum

    visited = [[False] * w for _ in range(h)]
    q = deque()
    for x in range(w):
        q.append((x, 0))
        q.append((x, h - 1))
    for y in range(h):
        q.append((0, y))
        q.append((w - 1, y))

    while q:
        x, y = q.popleft()
        if visited[y][x]:
            continue
        r, g, b, a = s.get_at((x, y))
        if not treat_as_background(r, g, b, a):
            visited[y][x] = True
            continue
        visited[y][x] = True
        s.set_at((x, y), (0, 0, 0, 0))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                q.append((nx, ny))

    return s


def silhouette_to_white(surf, alpha_floor=12):
    """Sprite escuro no PNG/SVG → silhueta branca (mantém alpha)."""
    s = surf.convert_alpha()
    w, h = s.get_width(), s.get_height()
    for y in range(h):
        for x in range(w):
            r, g, b, a = s.get_at((x, y))
            if a > alpha_floor:
                s.set_at((x, y), (255, 255, 255, a))
    return s


def pygame_surface_from_svg_file(svg_path):
    """Rasteriza SVG: 1) PNG embutido em base64 no ficheiro; 2) opcionalmente cairosvg."""
    try:
        txt = Path(svg_path).read_text(encoding="utf-8")
    except OSError:
        return None
    blobs = re.findall(r"data:image/png;base64,([A-Za-z0-9+/=]+)", txt)
    best = None
    best_n = 0
    for b in blobs:
        if len(b) > best_n:
            best_n = len(b)
            best = b
    if best:
        try:
            raw = base64.b64decode(best)
            return pygame.image.load(BytesIO(raw)).convert_alpha()
        except Exception:
            pass
    try:
        import cairosvg
        png_bytes = cairosvg.svg2png(url=str(svg_path))
        return pygame.image.load(BytesIO(png_bytes)).convert_alpha()
    except Exception:
        return None


def draw_texture(tid, x, y, dw, dh, flip_x=False):
    """Desenha textura completa no rect (x,y)-(x+dw,y+dh); origem OpenGL em baixo-esquerdo."""
    glEnable(GL_TEXTURE_2D)
    glBindTexture(GL_TEXTURE_2D, tid)
    glColor4f(1, 1, 1, 1)
    u0, u1 = (1, 0) if flip_x else (0, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(u0, 0); glVertex2f(x,      y)
    glTexCoord2f(u1, 0); glVertex2f(x + dw, y)
    glTexCoord2f(u1, 1); glVertex2f(x + dw, y + dh)
    glTexCoord2f(u0, 1); glVertex2f(x,      y + dh)
    glEnd()
    glDisable(GL_TEXTURE_2D)


def load_masked_scaled_sprite(svg_name, png_name, target_h, silhouette_white=False):
    """Carrega SVG/PNG, remove fundo na borda e escala para altura target_h. Retorna (tid, dw, dh) ou None."""
    surf = None
    ps = find_asset(svg_name)
    if ps:
        surf = pygame_surface_from_svg_file(ps)
    if surf is None:
        pp = find_asset(png_name)
        if pp:
            surf = pygame.image.load(str(pp)).convert_alpha()
    if surf is None:
        return None
    surf.set_colorkey(None)
    surf = mask_sprite_outer_background(surf)
    sc = target_h / max(surf.get_height(), 1)
    nw = max(12, int(surf.get_width() * sc))
    nh = target_h
    surf = pygame.transform.scale(surf, (nw, nh))
    surf = mask_sprite_outer_background(surf, dark_rgb_sum=110, white_min=252)
    if silhouette_white:
        surf = silhouette_to_white(surf)
    tid, tw, th = texture_from_surface(surf)
    return tid, nw, nh


def load_game_assets():
    """Carrega tela-inicial, Mario, Donkey Kong (kong.svg) e princesa (princess.svg)."""
    out = {}
    pm = find_asset("tela-inicial.png")
    if pm:
        s = pygame.image.load(str(pm)).convert_alpha()
        s = pygame.transform.smoothscale(s, (W, H))
        tid, tw, th = texture_from_surface(s)
        out["menu"] = (tid, tw, th)

    m = None
    p_svg = find_asset("mario.svg")
    p_png = find_asset("mario.png")
    if p_svg:
        m = pygame_surface_from_svg_file(p_svg)
    if m is None and p_png:
        m = pygame.image.load(str(p_png)).convert_alpha()
    if m is not None:
        m.set_colorkey(None)
        m = mask_sprite_outer_background(m)
        target_h = 42
        sc = target_h / max(m.get_height(), 1)
        nw = max(18, int(m.get_width() * sc))
        nh = target_h
        right = pygame.transform.scale(m, (nw, nh))
        right = mask_sprite_outer_background(right, dark_rgb_sum=110, white_min=252)
        left = pygame.transform.flip(right, True, False)
        tr, _, _ = texture_from_surface(right)
        tl, _, _ = texture_from_surface(left)
        out["mario_r"] = tr
        out["mario_l"] = tl
        out["mario_dw"] = nw
        out["mario_dh"] = nh

    kong = load_masked_scaled_sprite("kong.svg", "kong.png", target_h=94)
    if kong:
        out["kong"] = kong

    princess = load_masked_scaled_sprite(
        "princess.svg", "princess.png", target_h=56, silhouette_white=False
    )
    if princess:
        out["princess"] = princess

    return out


# ════════════════════════════════════════════════════════════════
#  ENTIDADES
# ════════════════════════════════════════════════════════════════

class Player:
    PW, PH = 28, 38

    def __init__(self, assets=None):
        self._assets = assets or {}
        self.reset()

    def reset(self):
        self.x        = 60.0
        self.y        = 89.0    # sobre o andar 0
        self.vx       = 0.0
        self.vy       = 0.0
        self.facing   = 1
        self.on_ground= False
        self.on_ladder= False
        self.jump_held= False
        self.invince  = 0       # frames de invencibilidade
        self.dead     = False
        self.score    = 0
        self.lives    = 3

    @property
    def cx(self):
        return self.x + self.PW / 2

    def update(self, keys, barrels):
        if self.dead:
            return
        if self.invince > 0:
            self.invince -= 1

        # ── Movimento horizontal ──────────────────────────────
        self.vx = 0.0
        if keys[K_LEFT]  or keys[K_a]:
            self.vx = -PLY_SPD
            self.facing = -1
        if keys[K_RIGHT] or keys[K_d]:
            self.vx =  PLY_SPD
            self.facing =  1

        # ── Escada ───────────────────────────────────────────
        # Só entra na escada alinhado em X em cima do patamar da base (↑) ou
        # do topo (↓), não ao aproximar com uma caixa larga à volta da escada.
        up   = keys[K_UP]   or keys[K_w]
        down = keys[K_DOWN] or keys[K_s]
        on_lad = False
        foot_y = self.y

        def ladder_aligned(cx, lx, lw, pad=5.0):
            return (lx + pad) <= cx <= (lx + lw - pad)

        for lad in LADS:
            lx, yb, yt, lw = lad
            if not ladder_aligned(self.cx, lx, lw):
                continue

            on_span = (yb - 12) <= foot_y <= (yt + 18)

            if self.on_ladder and on_span:
                if up:
                    if foot_y + 6 < yt:
                        on_lad = True
                        self.vy = LAD_SPD
                        self.vx = 0.0
                        self.x = lx + lw / 2 - self.PW / 2
                    else:
                        # Topo da escada — larga para a plataforma assumir no próximo frame
                        on_lad = False
                elif down and foot_y > yb + 3:
                    on_lad = True
                    self.vy = -LAD_SPD
                    self.vx = 0.0
                    self.x = lx + lw / 2 - self.PW / 2
                else:
                    on_lad = True
                    self.vy = 0.0
                    self.vx = 0.0
                    self.x = lx + lw / 2 - self.PW / 2
                break

            if not self.on_ladder and self.on_ground:
                at_bottom = (yb - 18) <= foot_y <= (yb + 28) and foot_y + 6 < yt
                at_top = (yt - 38) <= foot_y <= (yt + 22)
                if at_bottom and up:
                    on_lad = True
                    self.vy = LAD_SPD
                    self.vx = 0.0
                    self.x = lx + lw / 2 - self.PW / 2
                    break
                if at_top and down:
                    on_lad = True
                    self.vy = -LAD_SPD
                    self.vx = 0.0
                    self.x = lx + lw / 2 - self.PW / 2
                    break

        self.on_ladder = on_lad

        # ── Gravidade ────────────────────────────────────────
        if not self.on_ladder:
            self.vy = max(self.vy + GRAVITY, MAX_FALL)

        # ── Pulo ─────────────────────────────────────────────
        jump_key = keys[K_SPACE] or (keys[K_UP] or keys[K_w])
        if jump_key and self.on_ground and not self.on_ladder and not self.jump_held:
            self.vy = JUMP_FORCE
            self.jump_held = True
        if not jump_key:
            self.jump_held = False

        # ── Aplicar velocidade ────────────────────────────────
        self.x += self.vx
        self.y += self.vy

        # ── Colisão com plataformas ───────────────────────────
        self.on_ground = False
        for p in PLATS:
            sy = plat_y(p, self.cx)
            if sy is not None:
                window = max(22, abs(self.vy) + 4)
                if self.vy <= 0.5 and self.y <= sy + 2 and self.y >= sy - window:
                    self.y        = sy
                    self.vy       = 0.0
                    self.on_ground= True
                    break

        # ── Limites da tela ───────────────────────────────────
        self.x = max(0.0, min(W - self.PW, self.x))
        if self.y < 0:
            self.y  = 0.0
            self.vy = 0.0

        # ── Colisão com barris ────────────────────────────────
        if self.invince == 0:
            for b in barrels:
                dx = abs(self.cx - b.cx)
                dy = abs((self.y + self.PH / 2) - (b.y + b.r))
                if dx < (self.PW / 2 + b.r) and dy < (self.PH / 2 + b.r):
                    self.lives -= 1
                    self.invince = 150
                    if self.lives <= 0:
                        self.dead = True
                    return

        # ── Pontos por pular barril ───────────────────────────
        if self.vy > 4:
            for b in barrels:
                if not b.scored and abs(self.cx - b.cx) < 48 and self.y > b.y + b.r:
                    self.score += 100
                    b.scored = True

    def draw(self):
        blink = self.invince > 0 and (self.invince // 5) % 2 == 0
        if blink:
            return
        tr = self._assets.get("mario_r")
        tl = self._assets.get("mario_l")
        if tr is not None and tl is not None:
            dw = self._assets.get("mario_dw", self.PW)
            dh = self._assets.get("mario_dh", self.PH)
            tid = tr if self.facing >= 0 else tl
            dx = self.x + (self.PW - dw) / 2
            dy = self.y + self.PH - dh
            draw_texture(tid, dx, dy, dw, dh, False)
            return
        draw_player(self.x, self.y, self.PW, self.PH, self.facing, False)


# ─────────────────────────────────────────────────────────────────

class Barrel:
    """Barril normal: rola nas vigas e pode cair aleatoriamente nas bordas."""

    def __init__(self, x, y, vx):
        self.x             = float(x)
        self.y             = float(y)
        self.vx            = float(vx)
        self.vy            = 0.0
        self.r             = 12
        self.angle         = 0.0
        self.dead          = False
        self.scored        = False
        self.exiting_plat  = None   # índice da viga que está a atravessar para baixo
        self._grounded     = False

    @property
    def cx(self):
        return self.x + self.r

    def _best_platform_land(self, prev_y, prev_x):
        """Melhor candidato de apoio após integrar posição (mesma lógica para ar e solo)."""
        foot_lo = self.x + self.r * 0.25
        foot_hi = self.x + self.r * 1.75
        best_sy = None
        best_j = None
        prev_cx = prev_x + self.r

        for j, p in enumerate(PLATS):
            x1, y1, x2, y2, th = p
            sy = plat_y(p, self.cx)
            if sy is None:
                sy = plat_max_y_under_span(p, foot_lo, foot_hi)
            if sy is None:
                continue
            underside = sy - th

            if self.exiting_plat is not None and j == self.exiting_plat:
                if self.y > underside - 12:
                    continue
                self.exiting_plat = None

            prev_sy = plat_y(p, prev_cx)
            if prev_sy is None:
                prev_sy = plat_max_y_under_span(
                    p,
                    prev_x + self.r * 0.25,
                    prev_x + self.r * 1.75,
                )
            if prev_sy is None:
                prev_sy = sy

            crossed = prev_y >= prev_sy - 2.0 and self.y <= sy + 10.0
            frame_move = abs(self.y - prev_y) + 1.0
            window = max(42.0, abs(self.vy) * 1.35 + frame_move + 18.0)

            if not crossed and self.y < underside - 6:
                continue

            if crossed or (
                self.vy <= 0.55 and self.y <= sy + 3.5 and self.y >= sy - window
            ):
                if best_sy is None or sy > best_sy:
                    best_sy = sy
                    best_j = j

        return best_j, best_sy

    def update(self):
        self.vy = max(self.vy + BARREL_GRAVITY, BARREL_MAX_FALL)
        prev_y = self.y
        prev_x = self.x
        self.x += self.vx
        self.y += self.vy
        self.angle += self.vx * 0.095

        best_j, best_sy = self._best_platform_land(prev_y, prev_x)

        landed = False
        if best_j is not None:
            p = PLATS[best_j]
            snap_y = plat_y(p, self.cx)
            self.y = snap_y if snap_y is not None else best_sy
            self.vy = 0.0
            x1, y1, x2, y2, _ = p
            slope = (y2 - y1) / (x2 - x1)

            gp = getattr(self, "_blue_player", None)
            if gp is not None:
                pi = best_j
                pp = plat_index_underfoot(gp.cx, gp.y, tol=18)
                if pp is not None and pi == pp:
                    dxp = gp.cx - self.cx
                    if abs(dxp) <= BLUE_BAR_HOME_ALIGN:
                        target_vx = 0.0
                    else:
                        target_vx = BLUE_BAR_ROLL_SPD * (1 if dxp > 0 else -1)
                else:
                    target_vx = BAR_SPD if slope < 0 else -BAR_SPD
            else:
                target_vx = BAR_SPD if slope < 0 else -BAR_SPD
            self.vx += (target_vx - self.vx) * BAR_ROLL_SMOOTH
            landed = True

        self._grounded = landed and abs(self.vy) < 0.06

        # Queda nas pontas obrigatória; no tramo central, às vezes cai para o nível abaixo.
        if landed and abs(self.vy) < 0.05:
            pi = plat_index_underfoot(self.cx, self.y, tol=18)
            if pi is not None:
                x1, y1, x2, y2, _ = PLATS[pi]
                slope = (y2 - y1) / (x2 - x1)
                at_right_end = slope < 0 and self.cx >= x2 - GIRDER_END_MARGIN
                at_left_end = slope >= 0 and self.cx <= x1 + GIRDER_END_MARGIN
                inset = GIRDER_END_MARGIN + BARREL_RANDOM_DROP_INSET
                inner_lo = x1 + inset
                inner_hi = x2 - inset
                span = x2 - x1
                inner_ok = span > inset * 2 + 24 and inner_lo <= self.cx <= inner_hi
                random_drop = inner_ok and random.random() < BARREL_RANDOM_DROP_FR
                if at_right_end or at_left_end or random_drop:
                    self.exiting_plat = pi
                    self.vy = DROP_VY_END

        if self.x < -80 or self.x > W + 80 or self.y < -80:
            self.dead = True

    def draw(self):
        bob = math.sin(self.angle * 1.15) * (1.35 if self._grounded else 0.45)
        draw_barrel(self.x, self.y + bob, self.r, self.angle, blue=False)


class BlueBarrel(Barrel):
    """Barril azul: arco para o jogador; na mesma viga, rola até junto do Mario (cx)."""

    def __init__(self, x, y, player):
        super().__init__(x, y, 0.0)
        self._blue_player = player
        self._blue_airborne = True
        bx = self.cx
        by = self.y + self.r
        tx = player.cx
        ty = player.y + player.PH * 0.5
        dx = tx - bx
        dy = ty - by
        dist = math.hypot(dx, dy) + 1e-6
        self.vx = (dx / dist) * BLUE_LAUNCH_SPD
        self.vy = (dy / dist) * BLUE_LAUNCH_SPD * BLUE_LAUNCH_VERTICAL

    def update(self):
        if self._blue_airborne:
            self.vx *= BLUE_AIR_DRAG
            self.vy = max(self.vy + GRAVITY, MAX_FALL)
            prev_y = self.y
            prev_x = self.x
            self.x += self.vx
            self.y += self.vy
            self.angle += self.vx * 0.072 + self.vy * 0.055
            best_j, best_sy = self._best_platform_land(prev_y, prev_x)
            if best_j is not None:
                p = PLATS[best_j]
                snap_y = plat_y(p, self.cx)
                self.y = snap_y if snap_y is not None else best_sy
                self.vy = 0.0
                self._blue_airborne = False
            if self.x < -100 or self.x > W + 100 or self.y < -120 or self.y > H + 120:
                self.dead = True
            return

        super().update()

    def draw(self):
        wobble = math.sin(self.angle * 0.9) * 0.9
        draw_barrel(self.x, self.y + wobble, self.r, self.angle, blue=True)


# ─────────────────────────────────────────────────────────────────

class DonkeyKong:
    def __init__(self, assets=None):
        self._assets = assets or {}
        # Andar 4 — alinhar base do sprite ao tabuleiro
        self.x          = 55.0
        self.y          = 469.0
        self.timer      = 68
        self.blue_timer = 220
        self.frame      = 0
        self.ftimer     = 0

    def update(self, barrels, player):
        self.ftimer += 1
        if self.ftimer >= 28:
            self.ftimer = 0
            self.frame  = 1 - self.frame

        self.timer -= 1
        if self.timer <= 0:
            self.timer = random.randint(58, 108)
            bx = self.x + 82
            by = plat_y(PLATS[4], bx + 12) or 450.0
            barrels.append(Barrel(bx, by, BAR_SPD))
            if random.random() < 0.12 and len(barrels) < 10:
                br = 12
                bx2 = bx + random.uniform(-34, 34)
                bx2 = max(45.0, min(W - 55.0, bx2))
                by2 = plat_y(PLATS[4], bx2 + br) or by
                barrels.append(Barrel(bx2, by2, BAR_SPD))

        self.blue_timer -= 1
        if self.blue_timer <= 0:
            self.blue_timer = random.randint(300, 520)
            bx = self.x + 84
            by = plat_y(PLATS[4], bx + 12) or 450.0
            barrels.append(BlueBarrel(bx, by, player))

    def draw(self):
        k = self._assets.get("kong")
        if k:
            tid, dw, dh = k
            draw_texture(tid, self.x, self.y, dw, dh, False)
            return
        draw_dk(self.x, self.y, self.frame)


# ════════════════════════════════════════════════════════════════
#  JOGO
# ════════════════════════════════════════════════════════════════

MENU, PLAY, OVER, WIN = 0, 1, 2, 3

# Posição da princesa (topo-direita)
PRINCESS_X, PRINCESS_Y = 690, 452


class Game:
    def __init__(self, fonts, assets=None):
        self.fonts = fonts   # (font_big, font_med, font_small)
        self.assets = assets or {}
        self.state = MENU
        self._new_game()

    def _new_game(self):
        self.player  = Player(self.assets)
        self.dk      = DonkeyKong(self.assets)
        self.barrels = []

    # ── Update ─────────────────────────────────────────────────
    def update(self, keys):
        if self.state != PLAY:
            return

        self.player.update(keys, self.barrels)
        self.dk.update(self.barrels, self.player)

        for b in self.barrels:
            b.update()
        self.barrels = [b for b in self.barrels if not b.dead]

        if self.player.dead:
            self.state = OVER
            return

        # Vitória: alcançar a princesa (zona um pouco maior se sprite raster)
        pr = self.assets.get("princess")
        px_margin = 52 if pr else 40
        py_top = 68 if pr else 60
        if (self.player.x > PRINCESS_X - px_margin and
                self.player.y > PRINCESS_Y - 22 and
                self.player.y < PRINCESS_Y + py_top):
            self.state = WIN

    # ── Draw ───────────────────────────────────────────────────
    def draw(self):
        glClear(GL_COLOR_BUFFER_BIT)

        if self.state == MENU:
            menu = self.assets.get("menu")
            if menu:
                tid, _, _ = menu
                draw_texture(tid, 0, 0, W, H)
                return
            strips = 10
            for s in range(strips):
                t = s / (strips - 1) if strips > 1 else 0
                c = (
                    BG[0] + (BG2[0] - BG[0]) * t,
                    BG[1] + (BG2[1] - BG[1]) * t,
                    BG[2] + (BG2[2] - BG[2]) * t,
                )
                hh = H / strips
                gl_rect(0, s * hh, W, hh + 1, c)
            self._draw_menu_fallback()
            return

        # Partida: fundo em faixas
        strips = 10
        for s in range(strips):
            t = s / (strips - 1) if strips > 1 else 0
            c = (
                BG[0] + (BG2[0] - BG[0]) * t,
                BG[1] + (BG2[1] - BG[1]) * t,
                BG[2] + (BG2[2] - BG[2]) * t,
            )
            hh = H / strips
            gl_rect(0, s * hh, W, hh + 1, c)

        for ip, p in enumerate(PLATS):
            draw_plat(p, ip)
        for lad in LADS:
            draw_ladder(lad)

        pr = self.assets.get("princess")
        if pr:
            ptid, pdw, pdh = pr
            draw_texture(ptid, PRINCESS_X, PRINCESS_Y, pdw, pdh, flip_x=True)
        else:
            draw_princess(PRINCESS_X, PRINCESS_Y)
        self.dk.draw()

        for b in self.barrels:
            b.draw()

        self.player.draw()
        self._draw_hud()

        if self.state == OVER:
            self._draw_overlay(is_win=False)
        elif self.state == WIN:
            self._draw_overlay(is_win=True)

    # ── Menus ──────────────────────────────────────────────────
    def _draw_menu_fallback(self):
        fB, fM, fS = self.fonts
        gl_rect(140, 190, 520, 210, (0.10, 0.10, 0.38))
        gl_rect(144, 194, 512, 202, (0.16, 0.16, 0.52))

        t = fB.render("DONKEY  KONG", True, (255, 215, 0))
        s = fM.render("Pressione  ENTER  para jogar", True, (255, 255, 255))
        c = fS.render(
            "A/D ou ←→ : mover  |  SPACE/W : pular  |  escada: em cima da escada, ↑ ou ↓",
            True,
            (190, 190, 200),
        )
        render_text(t, W // 2 - t.get_width() // 2, 338)
        render_text(s, W // 2 - s.get_width() // 2, 286)
        render_text(c, W // 2 - c.get_width() // 2, 234)

        # Prévia miniatura do nível
        for p in PLATS:
            x1, y1, x2, y2, th = p
            # Escala: /3 + offset para centralizar no menu
            sx1, sy1 = x1 // 4 + 250, y1 // 4 + 30
            sx2, sy2 = x2 // 4 + 250, y2 // 4 + 30
            gl_quad4([(sx1, sy1), (sx2, sy2),
                      (sx2, sy2 - th // 2), (sx1, sy1 - th // 2)], PLT2)

    def _draw_hud(self):
        fB, fM, fS = self.fonts
        gl_rect(0, H - 28, W, 28, (0, 0, 0))
        sc = fM.render(f"SCORE  {self.player.score:06d}", True, (255, 215, 0))
        hearts = "♥ " * self.player.lives
        lv = fM.render(f"VIDAS  {hearts}", True, (255, 80, 80))
        render_text(sc, 8, H - 26)
        render_text(lv, W - lv.get_width() - 8, H - 26)

    def _draw_overlay(self, is_win):
        fB, fM, _ = self.fonts
        c1 = (0.00, 0.38, 0.00) if is_win else (0.45, 0.00, 0.00)
        c2 = (0.08, 0.65, 0.08) if is_win else (0.72, 0.08, 0.08)
        gl_rect(140, 210, 520, 175, c1)
        gl_rect(144, 214, 512, 167, c2)

        if is_win:
            t = fB.render("VOCÊ  GANHOU!", True, (80, 255, 100))
            r = fM.render("ENTER → jogar novamente", True, (255, 255, 255))
        else:
            t = fB.render("GAME  OVER", True, (255, 60, 60))
            r = fM.render("ENTER → tentar novamente", True, (255, 255, 255))

        sc = fM.render(f"Pontuação:  {self.player.score}", True, (255, 215, 0))
        render_text(t,  W // 2 - t.get_width()  // 2, 344)
        render_text(sc, W // 2 - sc.get_width() // 2, 296)
        render_text(r,  W // 2 - r.get_width()  // 2, 248)


# ════════════════════════════════════════════════════════════════
#  PONTO DE ENTRADA
# ════════════════════════════════════════════════════════════════

def main():
    pygame.init()
    pygame.display.set_mode((W, H), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Donkey Kong  –  Python / OpenGL")

    # Projeção 2D ortográfica: (0,0) = canto inferior esquerdo
    glViewport(0, 0, W, H)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, W, 0, H, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    fonts = (
        pygame.font.SysFont("Arial", 38, bold=True),
        pygame.font.SysFont("Arial", 24, bold=True),
        pygame.font.SysFont("Arial", 17),
    )

    assets = load_game_assets()
    game  = Game(fonts, assets)
    clock = pygame.time.Clock()

    while True:
        for ev in pygame.event.get():
            if ev.type == QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == KEYDOWN:
                if ev.key == K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if ev.key == K_RETURN:
                    if game.state == MENU:
                        game.state = PLAY
                    elif game.state in (OVER, WIN):
                        game._new_game()
                        game.state = PLAY

        game.update(pygame.key.get_pressed())
        game.draw()
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
