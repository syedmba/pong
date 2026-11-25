from __future__ import annotations

import array
import math
import random
import sys
import pygame

# --- Configuration ---
WIDTH, HEIGHT = 900, 560
FPS = 60

PADDLE_W, PADDLE_H = 14, 96
WIDE_PADDLE_H = 152
PADDLE_SPEED = 7.5
PADDLE_MARGIN = 36
WIDE_DURATION_SEC = 7.5

BALL_RADIUS = 10
BASE_BALL_SPEED = 6.2
MAX_BALL_SPEED = 14.5
SPEED_INCREMENT = 0.35

SLOW_DURATION_SEC = 7.0
SLOW_SPEED_FACTOR = 0.65
MIN_SLOW_SPEED = 4.2

POWERUP_RADIUS = 15
POWERUP_SPAWN_MIN_SEC = 5.0
POWERUP_SPAWN_MAX_SEC = 9.5

WIN_SCORE = 7

# Colors (RGB)
BG_COLOR = (12, 14, 26)
GRID_COLOR = (22, 27, 48)
NEON_CYAN = (0, 240, 255)
NEON_PINK = (255, 56, 130)
NEON_GOLD = (255, 210, 63)
NEON_GREEN = (56, 255, 160)
NEON_ICE = (130, 225, 255)
TEXT_DIM = (140, 152, 185)
WHITE = (245, 248, 255)


def make_tone(freq: float, duration: float = 0.07, volume: float = 0.25) -> pygame.mixer.Sound:
    """Generate a clean retro square wave beep in memory."""
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    buf = array.array("h")
    period = sample_rate / freq
    for i in range(n_samples):
        env = min(1.0, i / 120.0, (n_samples - i) / 240.0)
        wave = 1.0 if (i % period) < (period / 2) else -1.0
        sample = int(32767 * volume * env * wave)
        buf.append(sample)
    return pygame.mixer.Sound(buffer=buf)


class Paddle:
    def __init__(self, x: float, y: float, color: tuple[int, int, int]):
        self.base_h = PADDLE_H
        self.rect = pygame.Rect(x, y, PADDLE_W, PADDLE_H)
        self.color = color
        self.score = 0
        self.wide_timer = 0.0

    def reset_size(self):
        center_y = self.rect.centery
        self.rect.height = self.base_h
        self.rect.centery = center_y
        self.rect.clamp_ip(pygame.Rect(0, 16, WIDTH, HEIGHT - 32))
        self.wide_timer = 0.0

    def grant_wide(self, duration: float = WIDE_DURATION_SEC):
        center_y = self.rect.centery
        self.rect.height = WIDE_PADDLE_H
        self.rect.centery = center_y
        self.rect.clamp_ip(pygame.Rect(0, 16, WIDTH, HEIGHT - 32))
        self.wide_timer = duration

    def update(self, dt: float):
        if self.wide_timer > 0.0:
            self.wide_timer = max(0.0, self.wide_timer - dt)
            if self.wide_timer == 0.0:
                self.reset_size()

    def move(self, dy: float):
        self.rect.y += int(dy)
        self.rect.clamp_ip(pygame.Rect(0, 16, WIDTH, HEIGHT - 32))

    def draw(self, surface: pygame.Surface):
        h = self.rect.height
        glow = pygame.Surface((PADDLE_W + 16, h + 16), pygame.SRCALPHA)
        pygame.draw.rect(
            glow, (*self.color, 45), glow.get_rect(), border_radius=12
        )
        surface.blit(glow, (self.rect.x - 8, self.rect.y - 8))

        pygame.draw.rect(surface, self.color, self.rect, border_radius=6)
        inner = self.rect.inflate(-6, -12)
        if inner.height > 4:
            pygame.draw.rect(surface, WHITE, inner, border_radius=4)


class Ball:
    def __init__(self):
        self.trail: list[tuple[float, float]] = []
        self.last_hit_by: str | None = None  # "left" or "right"
        self.slow_owner: str | None = None
        self.slow_timer: float = 0.0
        self.normal_speed: float = BASE_BALL_SPEED
        self.reset(direction=random.choice([-1, 1]))

    def reset(self, direction: int = 1):
        self.x = WIDTH / 2
        self.y = HEIGHT / 2
        self.normal_speed = BASE_BALL_SPEED
        self.slow_owner = None
        self.slow_timer = 0.0
        angle = random.uniform(-0.42, 0.42)
        self.vx = math.cos(angle) * self.normal_speed * direction
        self.vy = math.sin(angle) * self.normal_speed
        self.trail.clear()
        self.last_hit_by = None

    def activate_directional_slow(self, owner: str, duration: float = SLOW_DURATION_SEC):
        self.slow_owner = owner
        self.slow_timer = duration

    def bump_normal_speed(self, delta: float = SPEED_INCREMENT):
        self.normal_speed = min(MAX_BALL_SPEED, self.normal_speed + delta)

    def is_moving_toward_slow_owner(self) -> bool:
        if self.slow_owner is None or self.slow_timer <= 0.0:
            return False
        if self.slow_owner == "left":
            return self.vx < 0
        if self.slow_owner == "right":
            return self.vx > 0
        return False

    def current_speed(self) -> float:
        if self.is_moving_toward_slow_owner():
            return max(MIN_SLOW_SPEED, self.normal_speed * SLOW_SPEED_FACTOR)
        return self.normal_speed

    def apply_velocity(self, angle: float, dir_x: int):
        """Set vx/vy from angle and horizontal direction (-1 left, +1 right) using active directional speed."""
        spd = self.current_speed()
        self.vx = math.cos(angle) * spd * dir_x
        self.vy = math.sin(angle) * spd

    def sync_speed_to_direction(self):
        """Keep travel angle while switching between slow and normal speed as direction changes."""
        spd = self.current_speed()
        mag = math.hypot(self.vx, self.vy)
        if mag > 1e-6:
            ux, uy = self.vx / mag, self.vy / mag
            self.vx = ux * spd
            self.vy = uy * spd

    def step(self, dt: float):
        if self.slow_timer > 0.0:
            self.slow_timer = max(0.0, self.slow_timer - dt)
            if self.slow_timer == 0.0:
                self.slow_owner = None

        self.sync_speed_to_direction()

        self.trail.append((self.x, self.y))
        if len(self.trail) > 10:
            self.trail.pop(0)
        self.x += self.vx
        self.y += self.vy

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.x - BALL_RADIUS),
            int(self.y - BALL_RADIUS),
            BALL_RADIUS * 2,
            BALL_RADIUS * 2,
        )

    def draw(self, surface: pygame.Surface):
        ball_color = NEON_ICE if self.is_moving_toward_slow_owner() else NEON_GOLD

        for idx, (tx, ty) in enumerate(self.trail):
            alpha = int(18 * (idx + 1))
            radius = max(3, int(BALL_RADIUS * (idx + 1) / len(self.trail)))
            dot = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(
                dot, (*ball_color, alpha), (radius + 2, radius + 2), radius
            )
            surface.blit(dot, (int(tx) - radius - 2, int(ty) - radius - 2))

        pygame.draw.circle(surface, ball_color, (int(self.x), int(self.y)), BALL_RADIUS)
        pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), BALL_RADIUS // 2)


class PowerUp:
    """Kind is 'wide' or 'slow'."""

    def __init__(self, kind: str, x: float, y: float):
        self.kind = kind
        self.x = x
        self.y = y
        self.pulse = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            int(self.x - POWERUP_RADIUS),
            int(self.y - POWERUP_RADIUS),
            POWERUP_RADIUS * 2,
            POWERUP_RADIUS * 2,
        )

    def update(self, dt: float):
        self.pulse += dt * 5.0

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        color = NEON_CYAN if self.kind == "wide" else NEON_GOLD
        letter = "W" if self.kind == "wide" else "S"
        ring_r = POWERUP_RADIUS + int(3 * math.sin(self.pulse))

        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), POWERUP_RADIUS)
        pygame.draw.circle(surface, BG_COLOR, (int(self.x), int(self.y)), POWERUP_RADIUS - 3)
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), ring_r, 1)

        glyph = font.render(letter, True, WHITE)
        surface.blit(glyph, (int(self.x) - glyph.get_width() // 2, int(self.y) - glyph.get_height() // 2))


def draw_background(surface: pygame.Surface):
    surface.fill(BG_COLOR)
    for x in range(0, WIDTH, 40):
        pygame.draw.line(surface, GRID_COLOR, (x, 0), (x, HEIGHT), 1)
    for y in range(0, HEIGHT, 40):
        pygame.draw.line(surface, GRID_COLOR, (0, y), (WIDTH, y), 1)

    for y in range(24, HEIGHT - 20, 28):
        pygame.draw.rect(surface, (42, 50, 82), (WIDTH // 2 - 2, y, 4, 14), border_radius=2)


def reset_match(
    left_paddle: Paddle,
    right_paddle: Paddle,
    ball: Ball,
) -> tuple[PowerUp | None, float]:
    left_paddle.score = 0
    right_paddle.score = 0
    left_paddle.rect.centery = HEIGHT // 2
    right_paddle.rect.centery = HEIGHT // 2
    left_paddle.reset_size()
    right_paddle.reset_size()
    ball.reset(direction=random.choice([-1, 1]))
    next_spawn = random.uniform(POWERUP_SPAWN_MIN_SEC, POWERUP_SPAWN_MAX_SEC)
    return None, next_spawn


def main():
    pygame.init()
    mixer_ready = False
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=1)
        mixer_ready = True
    except pygame.error:
        pass

    snd_paddle = make_tone(520, 0.055, 0.22) if mixer_ready else None
    snd_wall = make_tone(310, 0.05, 0.18) if mixer_ready else None
    snd_score = make_tone(190, 0.18, 0.25) if mixer_ready else None
    snd_powerup = make_tone(780, 0.09, 0.22) if mixer_ready else None

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Neon Pong")
    clock = pygame.time.Clock()

    font_score = pygame.font.SysFont("consolas", 54, bold=True)
    font_title = pygame.font.SysFont("consolas", 36, bold=True)
    font_badge = pygame.font.SysFont("consolas", 15, bold=True)
    font_hud = pygame.font.SysFont("consolas", 15)

    left_paddle = Paddle(PADDLE_MARGIN, HEIGHT // 2 - PADDLE_H // 2, NEON_CYAN)
    right_paddle = Paddle(WIDTH - PADDLE_MARGIN - PADDLE_W, HEIGHT // 2 - PADDLE_H // 2, NEON_PINK)
    ball = Ball()

    two_player = False
    paused = False
    winner: str | None = None
    ai_speed = 5.4

    powerup: PowerUp | None = None
    spawn_timer = random.uniform(POWERUP_SPAWN_MIN_SEC, POWERUP_SPAWN_MAX_SEC)
    status_banner = ""
    status_timer = 0.0

    while True:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_TAB:
                    two_player = not two_player
                    powerup, spawn_timer = reset_match(left_paddle, right_paddle, ball)
                    winner = None
                    paused = False
                    mode_name = "2P LOCAL" if two_player else "1P VS AI"
                    status_banner = f"SWITCHED TO {mode_name}"
                    status_timer = 1.6
                if event.key == pygame.K_p and winner is None:
                    paused = not paused
                if event.key == pygame.K_r and winner is not None:
                    powerup, spawn_timer = reset_match(left_paddle, right_paddle, ball)
                    winner = None
                    paused = False

        keys = pygame.key.get_pressed()

        if status_timer > 0.0:
            status_timer = max(0.0, status_timer - dt)

        if not paused and winner is None:
            left_paddle.update(dt)
            right_paddle.update(dt)

            

            # Right paddle: Up / Down in 2P mode, AI in 1P mode
            if two_player:
                # Left paddle: W / S
                dy_left = 0.0
                if keys[pygame.K_w]:
                    dy_left -= PADDLE_SPEED
                if keys[pygame.K_s]:
                    dy_left += PADDLE_SPEED
                left_paddle.move(dy_left)

                dy_right = 0.0
                if keys[pygame.K_UP]:
                    dy_right -= PADDLE_SPEED
                if keys[pygame.K_DOWN]:
                    dy_right += PADDLE_SPEED
                right_paddle.move(dy_right)
            else:
                # Left paddle: W / S
                dy_left = 0.0
                if keys[pygame.K_w] or keys[pygame.K_UP]:
                    dy_left -= PADDLE_SPEED
                if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                    dy_left += PADDLE_SPEED
                left_paddle.move(dy_left)


                target_y = ball.y if ball.vx > 0 else HEIGHT / 2
                diff = target_y - right_paddle.rect.centery
                if abs(diff) > 4:
                    right_paddle.move(max(-ai_speed, min(ai_speed, diff)))

            # Power-up spawning
            if powerup is None:
                spawn_timer -= dt
                if spawn_timer <= 0.0:
                    kind = random.choice(["wide", "slow"])
                    px = random.uniform(WIDTH * 0.28, WIDTH * 0.72)
                    py = random.uniform(90, HEIGHT - 90)
                    powerup = PowerUp(kind, px, py)
            else:
                powerup.update(dt)

            # Ball movement
            ball.step(dt)

            # Power-up pickup
            if powerup is not None and ball.rect.colliderect(powerup.rect):
                collector_side = (
                    ball.last_hit_by
                    if ball.last_hit_by in ("left", "right")
                    else ("left" if ball.vx > 0 else "right")
                )
                if powerup.kind == "wide":
                    target_paddle = left_paddle if collector_side == "left" else right_paddle
                    target_paddle.grant_wide()
                    side_label = "LEFT" if collector_side == "left" else "RIGHT"
                    status_banner = f"WIDE PADDLE ({side_label})"
                elif powerup.kind == "slow":
                    ball.activate_directional_slow(collector_side)
                    side_label = "LEFT" if collector_side == "left" else "RIGHT"
                    status_banner = f"SLOW ON {side_label} APPROACH"

                status_timer = 1.6
                powerup = None
                spawn_timer = random.uniform(POWERUP_SPAWN_MIN_SEC, POWERUP_SPAWN_MAX_SEC)
                if snd_powerup:
                    snd_powerup.play()

            # Top / Bottom wall bounce
            if ball.y - BALL_RADIUS <= 12:
                ball.y = 12 + BALL_RADIUS
                ball.vy = abs(ball.vy)
                if snd_wall:
                    snd_wall.play()
            elif ball.y + BALL_RADIUS >= HEIGHT - 12:
                ball.y = HEIGHT - 12 - BALL_RADIUS
                ball.vy = -abs(ball.vy)
                if snd_wall:
                    snd_wall.play()

            # Paddle collisions
            b_rect = ball.rect
            if b_rect.colliderect(left_paddle.rect) and ball.vx < 0:
                offset = (ball.y - left_paddle.rect.centery) / (left_paddle.rect.height / 2)
                offset = max(-1.0, min(1.0, offset))
                angle = offset * 0.72
                ball.bump_normal_speed()
                ball.last_hit_by = "left"
                ball.apply_velocity(angle, dir_x=1)
                ball.x = left_paddle.rect.right + BALL_RADIUS + 1
                if snd_paddle:
                    snd_paddle.play()

            elif b_rect.colliderect(right_paddle.rect) and ball.vx > 0:
                offset = (ball.y - right_paddle.rect.centery) / (right_paddle.rect.height / 2)
                offset = max(-1.0, min(1.0, offset))
                angle = offset * 0.72
                ball.bump_normal_speed()
                ball.last_hit_by = "right"
                ball.apply_velocity(angle, dir_x=-1)
                ball.x = right_paddle.rect.left - BALL_RADIUS - 1
                if snd_paddle:
                    snd_paddle.play()

            # Scoring
            if ball.x + BALL_RADIUS < 0:
                right_paddle.score += 1
                if snd_score:
                    snd_score.play()
                if right_paddle.score >= WIN_SCORE:
                    winner = "PLAYER 2 WINS!" if two_player else "AI WINS"
                else:
                    ball.reset(direction=-1)
            elif ball.x - BALL_RADIUS > WIDTH:
                left_paddle.score += 1
                if snd_score:
                    snd_score.play()
                if left_paddle.score >= WIN_SCORE:
                    winner = "PLAYER 1 WINS!" if two_player else "YOU WIN!"
                else:
                    ball.reset(direction=1)

        # --- Render ---
        draw_background(screen)

        p_txt = font_score.render(str(left_paddle.score), True, NEON_CYAN)
        a_txt = font_score.render(str(right_paddle.score), True, NEON_PINK)
        screen.blit(p_txt, (WIDTH // 2 - 90 - p_txt.get_width() // 2, 24))
        screen.blit(a_txt, (WIDTH // 2 + 90 - a_txt.get_width() // 2, 24))

        mode_badge = font_badge.render(
            "MODE: 2P LOCAL" if two_player else "MODE: 1P VS AI",
            True,
            NEON_GREEN if two_player else NEON_CYAN,
        )
        screen.blit(mode_badge, (20, 18))

        # Active left-side buff timers
        left_y = 40
        if left_paddle.wide_timer > 0:
            w_txt = font_badge.render(f"WIDE {left_paddle.wide_timer:.1f}s", True, NEON_CYAN)
            screen.blit(w_txt, (20, left_y))
            left_y += 20
        if ball.slow_owner == "left" and ball.slow_timer > 0:
            s_txt = font_badge.render(f"SLOW SHIELD {ball.slow_timer:.1f}s", True, NEON_ICE)
            screen.blit(s_txt, (20, left_y))

        # Active right-side buff timers
        right_y = 18
        if right_paddle.wide_timer > 0:
            r_txt = font_badge.render(f"WIDE {right_paddle.wide_timer:.1f}s", True, NEON_PINK)
            screen.blit(r_txt, (WIDTH - r_txt.get_width() - 20, right_y))
            right_y += 20
        if ball.slow_owner == "right" and ball.slow_timer > 0:
            rs_txt = font_badge.render(f"SLOW SHIELD {ball.slow_timer:.1f}s", True, NEON_ICE)
            screen.blit(rs_txt, (WIDTH - rs_txt.get_width() - 20, right_y))

        if status_timer > 0 and status_banner:
            b_txt = font_badge.render(status_banner, True, NEON_GOLD)
            screen.blit(b_txt, (WIDTH // 2 - b_txt.get_width() // 2, 86))

        controls_hint = (
            "P1: W/S  |  P2: Up/Down  |  TAB: Mode  |  P: Pause"
            if two_player
            else "Move: W/S or Up/Down  |  TAB: 2P Mode  |  P: Pause"
        )
        hud_txt = font_hud.render(f"{controls_hint}  |  First to {WIN_SCORE}", True, TEXT_DIM)
        screen.blit(hud_txt, (WIDTH // 2 - hud_txt.get_width() // 2, HEIGHT - 28))

        if powerup is not None:
            powerup.draw(screen, font_badge)

        left_paddle.draw(screen)
        right_paddle.draw(screen)
        ball.draw(screen)

        if paused and winner is None:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((8, 10, 20, 150))
            screen.blit(overlay, (0, 0))
            p_label = font_title.render("PAUSED", True, WHITE)
            screen.blit(p_label, (WIDTH // 2 - p_label.get_width() // 2, HEIGHT // 2 - 20))

        if winner is not None:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((8, 10, 20, 175))
            screen.blit(overlay, (0, 0))
            color = NEON_CYAN if ("YOU" in winner or "1" in winner) else NEON_PINK
            w_label = font_title.render(winner, True, color)
            r_label = font_hud.render("Press R to play again  |  TAB to switch mode  |  ESC to quit", True, WHITE)
            screen.blit(w_label, (WIDTH // 2 - w_label.get_width() // 2, HEIGHT // 2 - 36))
            screen.blit(r_label, (WIDTH // 2 - r_label.get_width() // 2, HEIGHT // 2 + 14))

        pygame.display.flip()


if __name__ == "__main__":
    main()