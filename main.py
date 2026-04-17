"""
╔══════════════════════════════════════════════════════╗
║          DONKEY KONG  –  Python / PyOpenGL           ║
║  Controles:                                          ║
║    ← → / A D  : mover                               ║
║    SPACE / W  : pular                                ║
║    ↑ ↓        : subir / descer escada                ║
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

# ─── Dimensões & física ──────────────────────────────────────────
W, H      = 800, 600
FPS       = 60
GRAVITY   = -0.38
JUMP_FORCE= 11.0
PLY_SPD   =  3.2
LAD_SPD   =  2.5
BAR_SPD   =  2.7
MAX_FALL  = -15.0

# ─── Paleta de cores (R, G, B  de 0.0 a 1.0) ────────────────────
BG    = (0.02, 0.02, 0.14)
PLT   = (0.48, 0.24, 0.04)
PLT2  = (0.62, 0.35, 0.10)
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

# ─── Plataformas (x_esq, y_esq, x_dir, y_dir, espessura) ────────
#  Inclinações alternadas criam o zigue-zague clássico dos barris:
#    slope < 0  →  plataforma desce para a direita  →  barril rola DIREITA
#    slope > 0  →  plataforma sobe  para a direita  →  barril rola ESQUERDA
PLATS = [
    ( 30,  90, 770,  70, 14),   # Andar 0 – base,    slope ↘
    ( 30, 175, 770, 195, 14),   # Andar 1            slope ↗
    ( 30, 280, 770, 260, 14),   # Andar 2            slope ↘
    ( 30, 365, 770, 385, 14),   # Andar 3            slope ↗
    ( 30, 470, 770, 450, 14),   # Andar 4 – topo, DK slope ↘
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

def draw_plat(p):
    x1, y1, x2, y2, th = p
    # Faixa superior clara
    gl_quad4([(x1, y1), (x2, y2), (x2, y2 - 3), (x1, y1 - 3)], PLT2)
    # Corpo mais escuro
    gl_quad4([(x1, y1 - 3), (x2, y2 - 3), (x2, y2 - th), (x1, y1 - th)], PLT)


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


def draw_barrel(x, y, r, angle):
    cx, cy = x + r, y + r
    gl_circle(cx, cy, r,       BRN)
    gl_circle(cx, cy, r * 0.6, (0.40, 0.18, 0.02))
    # Aros giratórios
    for off in (0.0, math.pi):
        a  = angle + off
        bx = cx + r * 0.55 * math.cos(a) - 2
        by = cy + r * 0.55 * math.sin(a) - 2
        gl_rect(bx, by, 4, 4, (0.20, 0.08, 0.00))


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


# ════════════════════════════════════════════════════════════════
#  ENTIDADES
# ════════════════════════════════════════════════════════════════

class Player:
    PW, PH = 28, 38

    def __init__(self):
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
        up   = keys[K_UP]   or keys[K_w]
        down = keys[K_DOWN] or keys[K_s]
        on_lad = False

        for lad in LADS:
            lx, yb, yt, lw = lad
            near_x = (lx - 6) <= self.cx <= (lx + lw + 6)
            near_y = (yb - 8) <= self.y <= (yt + 8)
            if near_x and near_y:
                if up and self.y + 4 < yt:
                    on_lad = True
                    self.vy  = LAD_SPD
                    self.vx  = 0.0
                    self.x   = lx + lw / 2 - self.PW / 2
                    break
                elif down and self.y > yb + 2:
                    on_lad = True
                    self.vy  = -LAD_SPD
                    self.vx  = 0.0
                    self.x   = lx + lw / 2 - self.PW / 2
                    break
                elif self.on_ladder and not up and not down:
                    on_lad = True
                    self.vy = 0.0
                    self.vx = 0.0
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
        draw_player(self.x, self.y, self.PW, self.PH, self.facing, blink)


# ─────────────────────────────────────────────────────────────────

class Barrel:
    def __init__(self, x, y, vx):
        self.x      = float(x)
        self.y      = float(y)
        self.vx     = float(vx)
        self.vy     = 0.0
        self.r      = 12
        self.angle  = 0.0
        self.dead   = False
        self.scored = False

    @property
    def cx(self):
        return self.x + self.r

    def update(self):
        self.vy = max(self.vy + GRAVITY, MAX_FALL)
        self.x += self.vx
        self.y += self.vy
        self.angle += self.vx * 0.11

        for p in PLATS:
            x1, y1, x2, y2, _ = p
            sy = plat_y(p, self.cx)
            if sy is not None:
                window = max(28, abs(self.vy) + 4)
                if self.vy <= 0.5 and self.y <= sy + 2 and self.y >= sy - window:
                    self.y  = sy
                    self.vy = 0.0
                    # Direção ditada pela inclinação da plataforma
                    slope   = (y2 - y1) / (x2 - x1)
                    self.vx = BAR_SPD if slope < 0 else -BAR_SPD
                    break

        # Morre fora do mundo
        if self.x < -80 or self.x > W + 80 or self.y < -80:
            self.dead = True

    def draw(self):
        draw_barrel(self.x, self.y, self.r, self.angle)


# ─────────────────────────────────────────────────────────────────

class DonkeyKong:
    def __init__(self):
        # Andar 4 surface em x≈80: y≈469
        self.x      = 55.0
        self.y      = 469.0
        self.timer  = 100
        self.frame  = 0
        self.ftimer = 0

    def update(self, barrels):
        self.ftimer += 1
        if self.ftimer >= 28:
            self.ftimer = 0
            self.frame  = 1 - self.frame

        self.timer -= 1
        if self.timer <= 0:
            self.timer = random.randint(80, 170)
            bx = self.x + 82
            by = plat_y(PLATS[4], bx + 12) or 450.0
            barrels.append(Barrel(bx, by, BAR_SPD))

    def draw(self):
        draw_dk(self.x, self.y, self.frame)


# ════════════════════════════════════════════════════════════════
#  JOGO
# ════════════════════════════════════════════════════════════════

MENU, PLAY, OVER, WIN = 0, 1, 2, 3

# Posição da princesa (topo-direita)
PRINCESS_X, PRINCESS_Y = 690, 452


class Game:
    def __init__(self, fonts):
        self.fonts = fonts   # (font_big, font_med, font_small)
        self.state = MENU
        self._new_game()

    def _new_game(self):
        self.player  = Player()
        self.dk      = DonkeyKong()
        self.barrels = []

    # ── Update ─────────────────────────────────────────────────
    def update(self, keys):
        if self.state != PLAY:
            return

        self.player.update(keys, self.barrels)
        self.dk.update(self.barrels)

        for b in self.barrels:
            b.update()
        self.barrels = [b for b in self.barrels if not b.dead]

        if self.player.dead:
            self.state = OVER
            return

        # Vitória: alcançar a princesa
        if (self.player.x > PRINCESS_X - 40 and
                self.player.y > PRINCESS_Y - 20 and
                self.player.y < PRINCESS_Y + 60):
            self.state = WIN

    # ── Draw ───────────────────────────────────────────────────
    def draw(self):
        glClear(GL_COLOR_BUFFER_BIT)
        gl_rect(0, 0, W, H, BG)

        if self.state == MENU:
            self._draw_menu()
            return

        for p in PLATS:
            draw_plat(p)
        for lad in LADS:
            draw_ladder(lad)

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
    def _draw_menu(self):
        fB, fM, fS = self.fonts
        gl_rect(140, 190, 520, 210, (0.10, 0.10, 0.38))
        gl_rect(144, 194, 512, 202, (0.16, 0.16, 0.52))

        t = fB.render("DONKEY  KONG", True, (255, 215, 0))
        s = fM.render("Pressione  ENTER  para jogar", True, (255, 255, 255))
        c = fS.render("A / D  ou  ←→  : mover   |   SPACE / W : pular   |   ↑↓ : escada", True, (190, 190, 200))
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

    game  = Game(fonts)
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
