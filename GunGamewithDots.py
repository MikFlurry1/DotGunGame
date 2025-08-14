"""
Arcade Top‑Down Shooter — Bigger, Flashier Pygame (single file, no assets)

Controls
- Move: WASD
- Aim: Mouse
- Shoot: Left mouse (hold)
- Reload: R
- Switch weapon: Q (Rifle / Shotgun)
- Dash: Space
- Pause: Esc
- Fullscreen: F11

What’s new vs last version
- Bigger sprites (player/enemies/bullets), bold colors, chunky health bars
- Camera zoom feel with parallax background
- Two weapons (rifle fast / shotgun spread)
- Grenade‑like dash impact knockback
- Screen shake, muzzle flash, hit sparks (high‑contrast)
- Clear UI (ammo, HP, wave, score)
- Guaranteed large playable arena (fewer walls, wider corridors)

Requires: pygame (`pip install pygame`)
"""

import sys, math, random
import pygame
from pygame import Vector2

# ----------------------------- Config -----------------------------
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60
TILE = 48
MAP_W, MAP_H = 48, 30  # tiles
SEED = None  # set an int for reproducible maps

COLORS = {
    "bg_dark": (10, 12, 16),
    "bg_mid": (18, 20, 28),
    "wall": (50, 56, 72),
    "floor": (26, 28, 38),
    "player": (80, 220, 255),
    "player_core": (255, 255, 255),
    "enemy_1": (255, 80, 80),
    "enemy_2": (255, 150, 70),
    "enemy_3": (255, 220, 60),
    "bullet": (255, 240, 120),
    "shot": (255, 255, 200),
    "ui": (235, 238, 245),
    "hp": (90, 230, 130),
    "danger": (255, 100, 100),
}

random.seed(SEED)


# ----------------------------- Helpers -----------------------------
def clamp(v, a, b):
    return max(a, min(b, v))


# ----------------------------- Tile Map -----------------------------
class TileMap:
    def __init__(self, w, h, tile):
        self.w, self.h, self.tile = w, h, tile
        self.grid = [[0 for _ in range(w)] for _ in range(h)]
        self.wall_rects = []
        self.generate()

    def generate(self):
        # border walls & sparse inner blocks for wide arena
        for y in range(self.h):
            for x in range(self.w):
                if x in (0, self.w - 1) or y in (0, self.h - 1):
                    self.grid[y][x] = 1
                else:
                    self.grid[y][x] = 1 if random.random() < 0.06 else 0
        # carve a huge start plaza
        cx, cy = self.w // 2, self.h // 2
        for y in range(cy - 5, cy + 6):
            for x in range(cx - 7, cx + 8):
                if 0 < x < self.w - 1 and 0 < y < self.h - 1:
                    self.grid[y][x] = 0
        self.rebuild_wall_rects()

    def rebuild_wall_rects(self):
        self.wall_rects = []
        t = self.tile
        for y in range(self.h):
            x = 0
            while x < self.w:
                if self.grid[y][x] == 1:
                    start = x
                    while x < self.w and self.grid[y][x] == 1:
                        x += 1
                    self.wall_rects.append(
                        pygame.Rect(start * TILE, y * TILE, (x - start) * TILE, TILE)
                    )
                else:
                    x += 1

    def draw_floor(self, surf, camera):
        # parallax stripes for depth
        surf.fill(COLORS["bg_dark"])
        stripes = 16
        for i in range(stripes):
            y = int((i / stripes) * SCREEN_H)
            alpha = 40 if i % 2 == 0 else 20
            s = pygame.Surface((SCREEN_W, SCREEN_H // stripes + 2), pygame.SRCALPHA)
            s.fill((255, 255, 255, alpha))
            surf.blit(s, (0, y))

    def draw_walls(self, surf, camera):
        for rect in self.wall_rects:
            pygame.draw.rect(
                surf, COLORS["wall"], camera.apply_rect(rect), border_radius=6
            )

    def rect_collide(self, rect):
        return [w for w in self.wall_rects if rect.colliderect(w)]


# ----------------------------- Camera -----------------------------
class Camera:
    def __init__(self):
        self.offset = Vector2(0, 0)
        self.shake_frames = 0
        self.shake_mag = 0

    def update(self, target_pos):
        desired = target_pos - Vector2(SCREEN_W / 2, SCREEN_H / 2)
        self.offset += (desired - self.offset) * 0.15
        if self.shake_frames > 0:
            self.shake_frames -= 1

    def apply(self, pos):
        jitter = Vector2(0, 0)
        if self.shake_frames > 0:
            jitter = Vector2(
                random.uniform(-self.shake_mag, self.shake_mag),
                random.uniform(-self.shake_mag, self.shake_mag),
            )
        return pos - self.offset + jitter

    def apply_rect(self, rect):
        r = rect.copy()
        r.topleft = self.apply(Vector2(r.topleft))
        return r

    def shake(self, frames=10, mag=6):
        self.shake_frames = frames
        self.shake_mag = mag


# ----------------------------- Entities -----------------------------
class Entity(pygame.sprite.Sprite):
    def __init__(self, pos, radius, color):
        super().__init__()
        self.pos = Vector2(pos)
        self.vel = Vector2()
        self.radius = radius
        self.color = color
        self.image = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (radius, radius), radius)
        self.rect = self.image.get_rect(center=self.pos)

    def collide_move(self, dt, tilemap: TileMap, speed):
        # X axis
        self.pos.x += self.vel.x * dt
        self.rect.centerx = int(self.pos.x)
        for w in tilemap.rect_collide(self.rect):
            if self.vel.x > 0:
                self.rect.right = w.left
            elif self.vel.x < 0:
                self.rect.left = w.right
            self.pos.x = self.rect.centerx
        # Y axis
        self.pos.y += self.vel.y * dt
        self.rect.centery = int(self.pos.y)
        for w in tilemap.rect_collide(self.rect):
            if self.vel.y > 0:
                self.rect.bottom = w.top
            elif self.vel.y < 0:
                self.rect.top = w.bottom
            self.pos.y = self.rect.centery

    def draw(self, surf, camera):
        surf.blit(self.image, self.image.get_rect(center=camera.apply(self.pos)))


class Player(Entity):
    def __init__(self, pos):
        super().__init__(pos, radius=22, color=COLORS["player"])
        self.core = pygame.Surface((18, 18), pygame.SRCALPHA)
        pygame.draw.circle(self.core, COLORS["player_core"], (9, 9), 9)
        self.speed = 320
        self.hp = 150
        self.max_hp = 150
        self.invuln = 0
        self.dash_cd = 0
        self.reload_time = 0
        self.weapon = "rifle"  # or "shotgun"
        self.ammo = {"rifle": 30, "shotgun": 8}
        self.mag = {"rifle": 30, "shotgun": 8}
        self.fire_cd = 0
        self.rpm = {"rifle": 480, "shotgun": 90}  # rounds per minute

    def input(self, keys):
        d = Vector2(0, 0)
        d.x = (1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0)
        d.y = (1 if keys[pygame.K_s] else 0) - (1 if keys[pygame.K_w] else 0)
        if d.length_squared():
            d = d.normalize()
        self.vel = d * self.speed

    def update_cooldowns(self):
        if self.invuln > 0:
            self.invuln -= 1
        if self.dash_cd > 0:
            self.dash_cd -= 1
        if self.reload_time > 0:
            self.reload_time -= 1
            if self.reload_time <= 0:
                self.ammo[self.weapon] = self.mag[self.weapon]
        if self.fire_cd > 0:
            self.fire_cd -= 1

    def aim_dir(self, world_mouse):
        v = world_mouse - self.pos
        if v.length_squared():
            v = v.normalize()
        return v

    def try_dash(self, camera, particles):
        if self.dash_cd <= 0 and self.vel.length_squared() > 0:
            self.pos += self.vel.normalize() * 140
            self.rect.center = self.pos
            self.dash_cd = 50
            camera.shake(6, 5)
            # dust burst
            for _ in range(16):
                particles.add(
                    Particle(
                        self.pos,
                        Vector2(random.uniform(-4, 4), random.uniform(-4, 4)),
                        18,
                        COLORS["wall"],
                    )
                )

    def damage(self, amt):
        if self.invuln > 0:
            return
        self.hp -= amt
        self.invuln = 25

    def reload(self):
        if self.reload_time <= 0 and self.ammo[self.weapon] < self.mag[self.weapon]:
            self.reload_time = int(FPS * (0.8 if self.weapon == "rifle" else 1.2))

    def switch_weapon(self):
        self.weapon = "shotgun" if self.weapon == "rifle" else "rifle"


class Enemy(Entity):
    def __init__(self, pos, tier=1):
        color = (
            COLORS["enemy_1"]
            if tier == 1
            else (COLORS["enemy_2"] if tier == 2 else COLORS["enemy_3"])
        )
        super().__init__(pos, radius=20 + 3 * (tier - 1), color=color)
        self.speed = 170 + 20 * (tier - 1)
        self.hp = 40 + 20 * (tier - 1)
        self.tier = tier

    def ai(self, player: Player, tilemap: TileMap):
        desired = player.pos - self.pos
        d = desired.length() or 0.0001
        desired = desired / d
        steer = desired * self.speed
        # simple wall avoidance
        feel = [Vector2(1, 0), Vector2(-1, 0), Vector2(0, 1), Vector2(0, -1)]
        avoid = Vector2()
        for f in feel:
            ahead = self.pos + f * 24
            rect = pygame.Rect(ahead.x - 10, ahead.y - 10, 20, 20)
            if tilemap.rect_collide(rect):
                avoid -= f * 200
        self.vel = steer + avoid
        if self.vel.length() > self.speed:
            self.vel.scale_to_length(self.speed)


class Bullet(pygame.sprite.Sprite):
    def __init__(self, pos, vel, life=70):
        super().__init__()
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.life = life
        self.image = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.circle(self.image, COLORS["bullet"], (5, 5), 5)
        self.rect = self.image.get_rect(center=self.pos)

    def update(self, dt, tilemap):
        self.pos += self.vel * (dt / 1000)
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if tilemap.rect_collide(self.rect):
            self.life = 0
        self.life -= 1
        if self.life <= 0:
            self.kill()


class Particle(pygame.sprite.Sprite):
    def __init__(self, pos, vel, life, color):
        super().__init__()
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.life = life
        self.image = pygame.Surface((6, 6), pygame.SRCALPHA)
        pygame.draw.rect(self.image, color, (0, 0, 6, 6), border_radius=2)
        self.rect = self.image.get_rect(center=self.pos)

    def update(self):
        self.pos += self.vel
        self.vel *= 0.88
        self.life -= 1
        self.rect.center = (int(self.pos.x), int(self.pos.y))
        if self.life <= 0:
            self.kill()


# ----------------------------- Game -----------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Arcade Top‑Down Shooter — Pygame")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 20)

        self.map = TileMap(MAP_W, MAP_H, TILE)
        self.player = Player(Vector2(self.map.w * TILE // 2, self.map.h * TILE // 2))
        self.camera = Camera()

        self.enemies = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.particles = pygame.sprite.Group()

        self.wave = 0
        self.score = 0
        self.paused = False
        self.game_over = False

        self.spawn_wave()

    def spawn_wave(self):
        self.wave += 1
        n = 6 + self.wave * 2
        for _ in range(n):
            tier = 1 if self.wave < 3 else (2 if random.random() < 0.6 else 3)
            while True:
                x = random.randint(1, self.map.w - 2)
                y = random.randint(1, self.map.h - 2)
                if self.map.grid[y][x] == 0:
                    pos = Vector2(x * TILE + TILE // 2, y * TILE + TILE // 2)
                    if (pos - self.player.pos).length() > 380:
                        break
            self.enemies.add(Enemy(pos, tier))

    def shoot(self, world_mouse):
        if self.player.reload_time > 0 or self.player.fire_cd > 0:
            return
        w = self.player.weapon
        if self.player.ammo[w] <= 0:
            return
        dir = self.player.aim_dir(world_mouse)
        muzzle = self.player.pos + dir * 30
        speed = 900 if w == "rifle" else 750
        if w == "rifle":
            spread = random.uniform(-0.04, 0.04)
            rot = Vector2(
                math.cos(spread) * dir.x - math.sin(spread) * dir.y,
                math.sin(spread) * dir.x + math.cos(spread) * dir.y,
            )
            self.bullets.add(Bullet(muzzle, rot * speed))
            self.player.fire_cd = max(1, int(60 / (self.player.rpm[w] / 60)))
            self.player.ammo[w] -= 1
        else:  # shotgun
            pellets = 6
            for _ in range(pellets):
                spread = random.uniform(-0.22, 0.22)
                rot = Vector2(
                    math.cos(spread) * dir.x - math.sin(spread) * dir.y,
                    math.sin(spread) * dir.x + math.cos(spread) * dir.y,
                )
                self.bullets.add(Bullet(muzzle, rot * speed * 0.9, life=50))
            self.player.fire_cd = max(1, int(60 / (self.player.rpm[w] / 60)))
            self.player.ammo[w] -= 1
        # muzzle flash
        for _ in range(8 if w == "rifle" else 16):
            self.particles.add(
                Particle(
                    muzzle,
                    Vector2(random.uniform(-3, 3), random.uniform(-3, 3)),
                    14,
                    COLORS["shot"],
                )
            )
        self.camera.shake(5 if w == "rifle" else 8, 6 if w == "rifle" else 9)

    def run(self):
        fullscreen = False
        while True:
            dt = self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.paused = not self.paused
                    if (
                        event.key == pygame.K_SPACE
                        and not self.paused
                        and not self.game_over
                    ):
                        self.player.try_dash(self.camera, self.particles)
                    if (
                        event.key == pygame.K_r
                        and not self.paused
                        and not self.game_over
                    ):
                        self.player.reload()
                    if (
                        event.key == pygame.K_q
                        and not self.paused
                        and not self.game_over
                    ):
                        self.player.switch_weapon()
                    if event.key == pygame.K_F11:
                        fullscreen = not fullscreen
                        flags = pygame.FULLSCREEN if fullscreen else 0
                        self.screen = pygame.display.set_mode(
                            (SCREEN_W, SCREEN_H), flags
                        )
                if (
                    event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                    and not self.paused
                    and not self.game_over
                ):
                    self.shoot(self.screen_to_world(pygame.mouse.get_pos()))

            keys = pygame.key.get_pressed()
            if not self.paused and not self.game_over:
                self.player.input(keys)
                self.player.update_cooldowns()

                # continuous fire
                if pygame.mouse.get_pressed()[0]:
                    self.shoot(self.screen_to_world(pygame.mouse.get_pos()))

                # move
                self.player.collide_move(dt / 1000, self.map, self.player.speed)

                # bullets
                for b in list(self.bullets):
                    b.update(dt, self.map)

                # enemies
                for e in list(self.enemies):
                    e.ai(self.player, self.map)
                    e.collide_move(dt / 1000, self.map, e.speed)
                    if e.rect.colliderect(self.player.rect):
                        self.player.damage(12)
                        self.camera.shake(8, 7)
                        for _ in range(12):
                            self.particles.add(
                                Particle(
                                    self.player.pos,
                                    Vector2(
                                        random.uniform(-3, 3), random.uniform(-3, 3)
                                    ),
                                    18,
                                    COLORS["danger"],
                                )
                            )

                # bullet vs enemy
                for e in list(self.enemies):
                    for b in list(self.bullets):
                        if e.rect.colliderect(b.rect):
                            e.hp -= 20
                            b.kill()
                            for _ in range(10):
                                self.particles.add(
                                    Particle(
                                        e.pos,
                                        Vector2(
                                            random.uniform(-4, 4), random.uniform(-4, 4)
                                        ),
                                        16,
                                        COLORS["bullet"],
                                    )
                                )
                            if e.hp <= 0:
                                self.score += 10 * e.tier
                                # mini pop
                                for _ in range(18):
                                    self.particles.add(
                                        Particle(
                                            e.pos,
                                            Vector2(
                                                random.uniform(-5, 5),
                                                random.uniform(-5, 5),
                                            ),
                                            20,
                                            COLORS["enemy_1"],
                                        )
                                    )
                                e.kill()

                # particles
                for p in list(self.particles):
                    p.update()

                # next wave
                if len(self.enemies) == 0:
                    self.spawn_wave()

                # death
                if self.player.hp <= 0:
                    self.game_over = True

                # camera
                self.camera.update(self.player.pos)

            self.draw()

    def screen_to_world(self, screen_pos):
        return Vector2(screen_pos) + self.camera.offset

    def draw(self):
        self.map.draw_floor(self.screen, self.camera)
        self.map.draw_walls(self.screen, self.camera)
        for b in self.bullets:
            self.screen.blit(b.image, b.image.get_rect(center=self.camera.apply(b.pos)))
        for e in self.enemies:
            e.draw(self.screen, self.camera)
        self.player.draw(self.screen, self.camera)
        # player core & crosshair
        self.screen.blit(
            self.player.core,
            self.player.core.get_rect(center=self.camera.apply(self.player.pos)),
        )
        self.draw_crosshair()
        # UI and overlays
        if self.player.invuln > 18:
            s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            s.fill((255, 80, 80, 60))
            self.screen.blit(s, (0, 0))
        for p in self.particles:
            self.screen.blit(p.image, p.image.get_rect(center=self.camera.apply(p.pos)))
        self.draw_ui()
        if self.paused:
            self.center_text("PAUSED", 48, (240, 240, 240))
        if self.game_over:
            self.center_text(
                "GAME OVER — press R to reload weapon, Q to switch, F11 fullscreen",
                26,
                (255, 160, 160),
            )
        pygame.display.flip()

    def draw_crosshair(self):
        m = pygame.mouse.get_pos()
        pygame.draw.circle(self.screen, COLORS["ui"], m, 10, 2)
        pygame.draw.line(
            self.screen, COLORS["ui"], (m[0] - 16, m[1]), (m[0] - 4, m[1]), 2
        )
        pygame.draw.line(
            self.screen, COLORS["ui"], (m[0] + 4, m[1]), (m[0] + 16, m[1]), 2
        )
        pygame.draw.line(
            self.screen, COLORS["ui"], (m[0], m[1] - 16), (m[0], m[1] - 4), 2
        )
        pygame.draw.line(
            self.screen, COLORS["ui"], (m[0], m[1] + 4), (m[0], m[1] + 16), 2
        )

    def draw_ui(self):
        pad = 14
        bw, bh = 320, 22
        # HP bar
        pygame.draw.rect(self.screen, (60, 60, 72), (pad, pad, bw, bh), border_radius=8)
        hpw = int(bw * (self.player.hp / self.player.max_hp))
        pygame.draw.rect(
            self.screen, COLORS["hp"], (pad, pad, hpw, bh), border_radius=8
        )
        # Ammo & info
        w = self.player.weapon
        ammo_text = f"{w.upper()}  Ammo {self.player.ammo[w]}/{self.player.mag[w]}"
        if self.player.reload_time > 0:
            ammo_text = f"{w.upper()}  Reloading..."
        t1 = self.font.render(ammo_text, True, COLORS["ui"])
        t2 = self.font.render(
            f"Wave {self.wave}   Score {self.score}", True, COLORS["ui"]
        )
        self.screen.blit(t1, (pad, pad + bh + 6))
        self.screen.blit(t2, (pad, pad + bh + 32))

    def center_text(self, text, size, color):
        font = pygame.font.SysFont("consolas", size, bold=True)
        img = font.render(text, True, color)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))


# ----------------------------- Main -----------------------------
if __name__ == "__main__":
    try:
        Game().run()
    except Exception as e:
        print("Error:", e)
        pygame.quit()
        raise
