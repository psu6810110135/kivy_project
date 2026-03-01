from typing import Set, List
import random
import math
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line, PushMatrix, PopMatrix, Rotate, Ellipse
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.vector import Vector
from kivy.core.text import Label as CoreLabel

from entities import PlayerEntity, BulletEntity, EnemyEntity, SpecialEnemyEntity, EnemyProjectileEntity


class ExpOrb:
    """Collectible EXP orb rendered as a green diamond and pulled by player magnet radius."""

    def __init__(self, pos: Vector, exp_value: int):
        self.pos = Vector(pos.x, pos.y)
        self.exp_value = exp_value
        self.size = 18
        self.base_pull_speed = 240
        self.max_pull_speed = 820

    def get_hitbox(self):
        half = self.size / 2
        return (self.pos.x - half, self.pos.y - half, self.size, self.size)

    def update(self, dt: float, player_center: Vector, pull_radius: float):
        direction = player_center - self.pos
        distance = direction.length()
        if distance <= 0.001 or distance > pull_radius:
            return

        strength = 1.0 - (distance / pull_radius)
        pull_speed = self.base_pull_speed + (self.max_pull_speed - self.base_pull_speed) * strength
        self.pos += direction.normalize() * (pull_speed * dt)

    def draw(self, canvas):
        half = self.size / 2
        with canvas:
            Color(0.25, 1.0, 0.3, 0.95)
            PushMatrix()
            Rotate(angle=45, origin=(self.pos.x, self.pos.y))
            Rectangle(pos=(self.pos.x - half, self.pos.y - half), size=(self.size, self.size))
            PopMatrix()

            Color(0.85, 1.0, 0.88, 0.95)
            PushMatrix()
            Rotate(angle=45, origin=(self.pos.x, self.pos.y))
            Rectangle(pos=(self.pos.x - half * 0.35, self.pos.y - half * 0.35), size=(self.size * 0.35, self.size * 0.35))
            PopMatrix()

class GameWidget(Widget):
    MAX_ENEMIES = 100  # Limit to prevent lag
    GAME_DURATION = 15 * 60  # 15 minutes in seconds

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Preload all enemy textures at startup to avoid runtime lag
        EnemyEntity.preload_all_skins()
        SpecialEnemyEntity.preload_all_skins()

        self.player = PlayerEntity(pos=Vector(0, 0))
        self._did_initial_player_center = False
        # Enemies spawn at left/right edges
        self.enemies: List[EnemyEntity] = []
        self.enemy_spawn_counter = 0
        self.spawn_timer = 0.0
        self.base_spawn_interval = 1.5  # Harder base spawn rate
        self.spawn_interval = self.base_spawn_interval
        self.min_spawn_interval = 0.22
        self.enemy_speed_multiplier = 1.0
        self.bullets: List[BulletEntity] = []
        self.exp_orbs: List[ExpOrb] = []
        self.exp_pickup_radius = 52.0
        
        # Special enemy spawning (every 3 minutes, no max limit)
        self.special_enemies: List[SpecialEnemyEntity] = []
        self.special_spawn_timer = 0.0
        self.special_spawn_interval = 180.0  # 3 minutes in seconds
        self.last_special_types: List[str] = []  # Track last 2 types spawned
        
        # Enemy projectiles (Kitsune's fire)
        self.enemy_projectiles: List[EnemyProjectileEntity] = []
        
        self.bg_texture = CoreImage("game_picture/background/bg2.png").texture
        self._keyboard = Window.request_keyboard(self._on_keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)
        self.pressed_keys: Set[str] = set()
        self.debug_label = Label(text="", pos=(10, 10), halign="left", valign="bottom")
        self.pos_label = Label(text="", halign="right", valign="top")
        self.progression_label = Label(text="", halign="left", valign="top")
        self.debug_mode = False
        self.god_mode = False  # Player invincibility (debug key 8)
        self.bullet_damage = self.player.bullet_damage
        self.fire_rate = self.player.fire_rate
        
        self.fire_timer = 0.0
        self.firing = False
        self.burst_shots_remaining = 0  # Support for semi/burst fire modes

        # Level-up selection overlay
        self.levelup_active = False
        self.pending_levelups = 0
        self.levelup_choices = []
        self.levelup_choice_labels = {
            "str": "STR +1  (Damage +)",
            "dex": "DEX +1  (Fire Rate +)",
            "agi": "AGI +1  (Move Speed +)",
            "int": "INT +1  (Skill Cooldown -)",
            "vit": "VIT +1  (Max HP +)",
            "luck": "LUCK +1 (Crit / Drop +)",
        }

        # Game timer
        self.game_time = 0.0
        self.time_speed_multiplier = 1.0  # Normal speed, can be increased in debug mode
        self.timer_label = Label(text="15:00", font_size=48, halign="center", valign="middle")
        self.timer_label.color = (1, 1, 1, 1)  # White
        self.timer_label.bold = True
        self.timer_label.opacity = 0  # Timer drawn on canvas
        self.add_widget(self.timer_label)

        self.add_widget(self.debug_label)
        self.add_widget(self.pos_label)
        self.progression_label.opacity = 0  # HUD drawn on canvas
        self.add_widget(self.progression_label)

        self.kill_count = 0

        self._sync_combat_from_player()

        self._spawn_player_at_screen_center()

        Clock.schedule_interval(self.update, 1 / 60)

    def _get_player_walkable_y_range(self):
        """Return the Y range the player can actually walk to."""
        height = self.height if self.height > 0 else Window.height
        block_unit = height / 10.0
        min_y = block_unit
        max_y_allowed = height - (3 * block_unit) - self.player.size[1]
        return (min_y, max(min_y, max_y_allowed))

    def _spawn_player_at_screen_center(self):
        """Spawn player at screen center (clamped to walkable Y band)."""
        width = self.width if self.width > 0 else Window.width
        height = self.height if self.height > 0 else Window.height

        spawn_x = (width - self.player.size[0]) / 2
        spawn_y = (height - self.player.size[1]) / 2

        min_y, max_y = self._get_player_walkable_y_range()
        spawn_y = max(min_y, min(spawn_y, max_y))

        self.player.pos = Vector(spawn_x, spawn_y)

    def _get_enemy_offscreen_x(self, enemy_width: float, spawn_left: bool) -> float:
        """Spawn enemy from outside the screen on left or right."""
        width = self.width if self.width > 0 else Window.width
        margin = max(40.0, enemy_width * 0.35)
        if spawn_left:
            return -enemy_width - margin
        return width + margin

    def _on_keyboard_closed(self):
        if self._keyboard:
            self._keyboard.unbind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)
            self._keyboard = None

    def _on_key_down(self, keyboard, keycode, text, modifiers):
        key = keycode[1]

        if key == 'r':
            if hasattr(self.player, 'start_reload'):
                self.player.start_reload()
            return True

        if key == 'v':
            if hasattr(self.player, 'toggle_firing_mode'):
                self.player.toggle_firing_mode()
            return True

        if self.levelup_active:
            if key in ('1', '2', '3'):
                self._apply_levelup_choice(int(key) - 1)
            return True

        if key == '9':
            self.debug_mode = not self.debug_mode
            if not self.debug_mode:
                self.time_speed_multiplier = 1.0  # Reset speed when exiting debug mode
            return True

        if key == '8':
            self.god_mode = not self.god_mode
            return True

        if self.debug_mode and key in ('+', '='):
            # Spawn an extra enemy for testing
            self._spawn_enemy()
            return True

        if self.debug_mode and key == '1':
            # Spawn Gorgon (special enemy)
            self._spawn_special_enemy_by_type("game_picture/special_enemy/Gorgon")
            return True

        if self.debug_mode and key == '2':
            # Spawn Kitsune (special enemy)
            self._spawn_special_enemy_by_type("game_picture/special_enemy/Kitsune")
            return True

        if self.debug_mode and key == '3':
            # Spawn Red_Werewolf (special enemy)
            self._spawn_special_enemy_by_type("game_picture/special_enemy/Red_Werewolf")
            return True

        if self.debug_mode and key == '-':
            # Speed up time in debug mode (cycle through speeds)
            speeds = [1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
            current_idx = speeds.index(self.time_speed_multiplier) if self.time_speed_multiplier in speeds else 0
            self.time_speed_multiplier = speeds[(current_idx + 1) % len(speeds)]
            return True

        self.pressed_keys.add(key)
        return True

    def _on_key_up(self, keyboard, keycode):
        self.pressed_keys.discard(keycode[1])
        return True

    def on_touch_down(self, touch):
        if touch.button == 'left':
            # Process clicking on upgrade cards if level up screen is active
            if self.levelup_active:
                s = self.height / 1080.0 if self.height > 0 else 1.0
                panel_w = self.width * 0.55
                panel_h = self.height * 0.52
                panel_x = (self.width - panel_w) / 2
                panel_y = (self.height - panel_h) / 2
                
                card_count = len(self.levelup_choices)
                card_spacing = 24 * s
                total_card_width = panel_w - 80 * s
                card_w = (total_card_width - card_spacing * (card_count - 1)) / max(1, card_count)
                card_h = panel_h * 0.48
                card_start_x = panel_x + 40 * s
                card_y = panel_y + 30 * s
                
                # Check if click falls within any card's bounding box
                for idx in range(card_count):
                    cx = card_start_x + idx * (card_w + card_spacing)
                    if cx <= touch.x <= cx + card_w and card_y <= touch.y <= card_y + card_h:
                        self._apply_levelup_choice(idx)
                        break
                return True

            if self.player.is_dead:
                return True
            
            # Weapon firing / reloading logic
            if not getattr(self.player, 'is_reloading', False) and getattr(self.player, 'ammo', 1) > 0:
                mode = getattr(self.player, 'firing_mode', 'AUTO')
                if mode == 'AUTO':
                    self.firing = True
                    self.player.start_shooting()
                elif mode == 'SEMI':
                    if not self.firing:
                        self.burst_shots_remaining = 3
                        self.firing = True
                        self.player.start_shooting()
                elif mode == 'SINGLE':
                    if not self.firing:
                        self.burst_shots_remaining = 1
                        self.firing = True
                        self.player.start_shooting()
            elif getattr(self.player, 'ammo', 0) <= 0:
                if hasattr(self.player, 'start_reload'):
                    self.player.start_reload()
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.button == 'left':
            mode = getattr(self.player, 'firing_mode', 'AUTO')
            if mode == 'AUTO':
                self.player.stop_shooting()
                self.firing = False
            # For SEMI and SINGLE, we let the ongoing burst finish gracefully
            return True
        return super().on_touch_up(touch)

    def update(self, dt: float):
        if self.levelup_active:
            self._update_progression_hud()
            self._draw_scene()
            self._update_debug(0.0)
            return

        # Update game time (stop at max duration)
        if self.game_time < self.GAME_DURATION:
            self.game_time += dt * self.time_speed_multiplier
            if self.game_time > self.GAME_DURATION:
                self.game_time = self.GAME_DURATION

            # Update spawn interval based on elapsed time (faster spawning over time)
            # At 0:00 -> 1.5s interval, at 15:00 -> 0.22s interval
            progress = self.game_time / self.GAME_DURATION  # 0.0 to 1.0
            target_interval = self.base_spawn_interval - (progress * 1.45)
            self.spawn_interval = max(self.min_spawn_interval, target_interval)
            self.enemy_speed_multiplier = 1.0 + (progress * 0.85)

        self._update_progression_hud()

        self.player.update(dt, self.pressed_keys, (self.width, self.height))

        # If player is dead, skip gameplay updates but still draw
        if self.player.is_dead:
            # Still update death anims for enemies in progress
            for enemy in self.enemies[:]:
                if enemy.is_dying:
                    enemy.update(dt, Vector(0, 0), (self.width, self.height))
                    if enemy.death_anim_done:
                        self.enemies.remove(enemy)
            for se in self.special_enemies[:]:
                if se.is_dying:
                    se.update(dt, Vector(0, 0), (self.width, self.height))
                    if se.death_anim_done:
                        self.special_enemies.remove(se)
            self._draw_scene()
            self._update_debug(dt)
            return

        # Keep player facing aligned with cursor while shooting
        if self.firing:
            mx, my = Window.mouse_pos
            local_mouse = Vector(*self.to_widget(mx, my))
            player_center = self.player.pos + Vector(self.player.size[0] / 2, self.player.size[1] / 2)
            self.player.facing = 1 if local_mouse.x >= player_center.x else -1

        # Spawn enemies at left/right edges
        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer -= self.spawn_interval
            progress = self.game_time / self.GAME_DURATION if self.GAME_DURATION > 0 else 0.0
            spawn_count = 1 + int(progress * 2.5)
            spawn_count = max(1, min(4, spawn_count))
            for _ in range(spawn_count):
                self._spawn_enemy()

        # Spawn special enemies every 3 minutes (affected by time speed multiplier)
        self.special_spawn_timer += dt * self.time_speed_multiplier
        if self.special_spawn_timer >= self.special_spawn_interval:
            self.special_spawn_timer -= self.special_spawn_interval
            self._spawn_special_enemy()

        # Update all enemies (target player's hitbox center for accurate pathing/aim)
        pbox = self.player.get_hitbox()
        player_center = Vector(pbox[0] + pbox[2] / 2, pbox[1] + pbox[3] / 2)
        enemy_dt = dt * self.enemy_speed_multiplier
        for enemy in self.enemies[:]:
            enemy.update(enemy_dt, player_center, (self.width, self.height))
            if not enemy.is_dying:
                self._update_enemy_state(enemy)

        # Update all special enemies (Kitsune may spawn projectiles)
        for special_enemy in self.special_enemies[:]:
            if not special_enemy.is_dying:
                projectile = special_enemy.update(enemy_dt, player_center, (self.width, self.height), bullets=self.bullets)
                if projectile:  # Kitsune spawned a fire projectile
                    self.enemy_projectiles.append(projectile)
                self._update_enemy_state(special_enemy)
            else:
                special_enemy.update(enemy_dt, player_center, (self.width, self.height))

        # Light separation so enemies don't stack
        self._separate_enemies()

        # Re-clamp all enemies to walkable Y band after separation push
        height = self.height if self.height > 0 else Window.height
        block_unit = height / 10.0
        walk_min_y = block_unit
        for e in self.enemies + self.special_enemies:
            walk_max_y = height - (3 * block_unit) - e.size[1]
            e.pos.y = max(walk_min_y, min(e.pos.y, max(walk_min_y, walk_max_y)))

        # Handle weapon fire cooldown tracking
        self.fire_timer += dt

        # Handle shooting execution
        if self.firing and not self.player.is_dead:
            if getattr(self.player, 'is_reloading', False):
                self.player.stop_shooting()
                self.firing = False
                self.burst_shots_remaining = 0
            elif getattr(self.player, 'ammo', 1) > 0:
                if self.fire_timer >= self.fire_rate:
                    self.fire_timer = 0.0  # Reset cooldown explicitly to avoid rapid stack bursts
                    self._spawn_bullet()
                    if hasattr(self.player, 'consume_ammo'):
                        self.player.consume_ammo()

                    mode = getattr(self.player, 'firing_mode', 'AUTO')
                    if mode in ('SEMI', 'SINGLE'):
                        self.burst_shots_remaining -= 1
                        if self.burst_shots_remaining <= 0:
                            self.firing = False
                            self.player.stop_shooting()
            else:
                if hasattr(self.player, 'start_reload'):
                    self.player.start_reload()
                self.firing = False
                self.burst_shots_remaining = 0
        
        # Update and clean up bullets + bullet-enemy collision
        for b in self.bullets[:]:
            b.update(dt)
            # Off-screen removal
            if b.pos.x < -50 or b.pos.x > self.width + 50 or b.pos.y < -50 or b.pos.y > self.height + 50:
                self.bullets.remove(b)
                continue
            # Check collision with regular enemies
            bullet_box = b.get_hitbox()
            hit = False
            for enemy in self.enemies[:]:
                if enemy.is_dying:
                    continue
                if self._rects_intersect(bullet_box, enemy.get_hitbox()):
                    bullet_damage = getattr(b, "damage", self.bullet_damage)
                    enemy_died = enemy.take_damage(bullet_damage)
                    if enemy_died:
                        self.kill_count += 1
                        self._drop_exp_orbs(enemy, self._get_enemy_exp_reward(enemy))
                    hit = True
                    break
            if not hit:
                # Check collision with special enemies
                for se in self.special_enemies[:]:
                    if se.is_dying:
                        continue
                    if self._rects_intersect(bullet_box, se.get_hitbox()):
                        bullet_damage = getattr(b, "damage", self.bullet_damage)
                        enemy_died = se.take_damage(bullet_damage)
                        if enemy_died:
                            self.kill_count += 1
                            self._drop_exp_orbs(se, self._get_enemy_exp_reward(se))
                        hit = True
                        break
            if hit:
                if b in self.bullets:
                    self.bullets.remove(b)
        
        # Update and clean up enemy projectiles
        for proj in self.enemy_projectiles[:]:
            proj.update(dt)
            # Check collision with player
            pbox = self.player.get_hitbox()
            proj_box = proj.get_hitbox()
            if self._rects_intersect(pbox, proj_box):
                # Hit player! Apply damage (unless godmode)
                if not self.god_mode:
                    # Kitsune fire damage
                    fire_damage = 25
                    for se in self.special_enemies:
                        if "Kitsune" in se.asset_path:
                            fire_damage = se.damage
                            break
                    self.player.take_damage(fire_damage)
                if not hasattr(self, 'player_hit_flash'):
                    self.player_hit_flash = 0.0
                self.player_hit_flash = 0.3  # Flash for 0.3 seconds
                self.enemy_projectiles.remove(proj)
                continue
            # Remove if off-screen
            if proj.pos.x < 0 or proj.pos.x > self.width or proj.pos.y < 0 or proj.pos.y > self.height:
                self.enemy_projectiles.remove(proj)

        # Update exp orbs: pull toward player and collect on touch
        pull_radius = self._get_exp_pull_radius()
        pickup_box = self._inflate_rect(self.player.get_hitbox(), self.exp_pickup_radius)
        for orb in self.exp_orbs[:]:
            orb.update(dt, player_center, pull_radius)
            if self._rects_intersect(orb.get_hitbox(), pickup_box):
                self._grant_player_exp(orb.exp_value)
                self.exp_orbs.remove(orb)
                continue

            # Cleanup only if somehow far outside the world
            margin = 300
            if orb.pos.x < -margin or orb.pos.x > self.width + margin or orb.pos.y < -margin or orb.pos.y > self.height + margin:
                self.exp_orbs.remove(orb)
        
        # Update hit flash timer
        if hasattr(self, 'player_hit_flash') and self.player_hit_flash > 0:
            self.player_hit_flash -= dt

        # Enemy melee attack damages player
        if not self.player.is_dead:
            for enemy in self.enemies + self.special_enemies:
                if enemy.is_dying:
                    continue
                if not getattr(enemy, 'is_attacking', False):
                    continue
                if enemy.damage_cooldown > 0:
                    continue
                # Check attack hitbox vs player
                attack_box = enemy.get_attack_hitbox()
                if attack_box is None:
                    continue
                pbox = self.player.get_hitbox()
                if self._rects_intersect(attack_box, pbox):
                    if not self.god_mode:
                        self.player.take_damage(enemy.damage)
                    enemy.damage_cooldown = getattr(enemy, 'attack_anim_speed', 0.1) * 3
                    if not hasattr(self, 'player_hit_flash'):
                        self.player_hit_flash = 0.0
                    self.player_hit_flash = 0.3

        # Remove enemies whose death animation is done
        self.enemies = [e for e in self.enemies if not e.death_anim_done]
        self.special_enemies = [e for e in self.special_enemies if not e.death_anim_done]

        self._draw_scene()
        self._update_debug(dt)

    def _update_enemy_state(self, enemy):
        """Trigger attack animation when enemy's attack hitbox (hand/tail) touches player."""
        if enemy.is_dying:
            return
        # Add hysteresis to prevent stuttering: use different thresholds for entering/exiting attack
        if not hasattr(enemy, 'is_attacking'):
            enemy.is_attacking = False
        
        pbox = self.player.get_hitbox()
        enemy_center = Vector(enemy.pos.x + enemy.size[0] / 2, enemy.pos.y + enemy.size[1] / 2)
        player_center = Vector(pbox[0] + pbox[2] / 2, pbox[1] + pbox[3] / 2)
        distance = (player_center - enemy_center).length()
        
        # Per-enemy hysteresis thresholds from stats
        attack_enter_distance = getattr(enemy, 'attack_enter_dist', 150)
        attack_exit_distance = getattr(enemy, 'attack_exit_dist', 200)
        
        if enemy.is_attacking:
            # Currently attacking - only stop if player moves far enough away
            if distance > attack_exit_distance:
                enemy.is_attacking = False
                self._set_enemy_anim(enemy, "walk")
            else:
                self._set_enemy_anim(enemy, "attack")
        else:
            # Currently walking - only start attacking if player is close enough
            if distance < attack_enter_distance:
                enemy.is_attacking = True
                self._set_enemy_anim(enemy, "attack")
            else:
                self._set_enemy_anim(enemy, "walk")

    def _separate_enemies(self):
        """Separate enemies using soft repulsion and per-enemy separation radii."""
        all_enemies = self.enemies + self.special_enemies
        if len(all_enemies) < 2:
            return

        max_sep_radius = max(getattr(enemy, "separation_radius", 40.0) for enemy in all_enemies)
        cell_size = max_sep_radius * 2

        # Build spatial grid
        grid = {}
        for enemy in all_enemies:
            cx = int((enemy.pos.x + enemy.size[0] / 2) / cell_size)
            cy = int((enemy.pos.y + enemy.size[1] / 2) / cell_size)
            key = (cx, cy)
            if key not in grid:
                grid[key] = []
            grid[key].append(enemy)

        # Only check enemies in same or adjacent cells
        for (cx, cy), cell_enemies in grid.items():
            # Check within same cell
            for i in range(len(cell_enemies)):
                for j in range(i + 1, len(cell_enemies)):
                    self._push_apart(cell_enemies[i], cell_enemies[j])

            # Check adjacent cells (only right, down, and diagonals to avoid duplicate checks)
            adjacent = [(cx + 1, cy), (cx, cy + 1), (cx + 1, cy + 1), (cx + 1, cy - 1)]
            for adj_key in adjacent:
                if adj_key in grid:
                    for e1 in cell_enemies:
                        for e2 in grid[adj_key]:
                            self._push_apart(e1, e2)

    def _push_apart(self, e1, e2):
        """Push two enemies apart if they're too close."""
        c1 = e1.pos + Vector(e1.size[0] / 2, e1.size[1] / 2)
        c2 = e2.pos + Vector(e2.size[0] / 2, e2.size[1] / 2)
        delta = c2 - c1
        dist = delta.length()

        r1 = getattr(e1, "separation_radius", min(e1.size[0], e1.size[1]) * 0.24)
        r2 = getattr(e2, "separation_radius", min(e2.size[0], e2.size[1]) * 0.24)
        min_dist = r1 + r2

        if dist >= min_dist:
            return

        if dist < 0.001:
            delta = Vector(1, 0)
            dist = 1.0

        # Soft collision: only resolve part of the overlap for smoother crowd motion.
        overlap = min_dist - dist
        soft_factor = 0.50
        push = overlap * 0.5 * soft_factor
        move = delta.normalize() * push
        e1.pos -= move
        e2.pos += move

    def _get_enemy_render_order(self):
        """Render order: danger first to front, then Y-sort, then stable spawn tie-break."""
        all_enemies = self.enemies + self.special_enemies

        def sort_key(enemy):
            danger = enemy.get_render_danger_priority() if hasattr(enemy, "get_render_danger_priority") else 0
            center_y = enemy.pos.y + enemy.size[1] / 2
            spawn_order = getattr(enemy, "spawn_order", 0)
            # Lower center_y (closer to camera in 2.5D) should render in front (later draw).
            # Newer spawns go slightly behind to reduce flip-flop overlap artifacts.
            return (danger, -center_y, -spawn_order)

        return sorted(all_enemies, key=sort_key)

    @staticmethod
    def _rects_intersect(a, b) -> bool:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        return not (ax + aw < bx or bx + bw < ax or ay + ah < by or by + bh < ay)

    @staticmethod
    def _inflate_rect(rect, pad: float):
        x, y, w, h = rect
        return (x - pad, y - pad, w + pad * 2, h + pad * 2)

    @staticmethod
    def _set_enemy_anim(enemy: EnemyEntity, anim: str):
        if enemy.current_anim != anim:
            enemy.current_anim = anim
            enemy.current_frame = 0
            enemy.frame_timer = 0.0

    def _draw_scene(self):
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=self.bg_texture, pos=(0, 0), size=self.size)

            # Draw player (hit flash handled inside draw())
            self.player.draw(self.canvas)
            Color(1, 1, 1, 1)  # Reset color

            # Draw enemies using danger-aware Y-sort ordering.
            for enemy in self._get_enemy_render_order():
                enemy.draw(self.canvas)

            # Draw bullets
            for b in self.bullets:
                b.draw(self.canvas)

            # Draw exp orbs
            for orb in self.exp_orbs:
                orb.draw(self.canvas)

            # Draw enemy projectiles
            for proj in self.enemy_projectiles:
                proj.draw(self.canvas)

            # Draw game UI (HP bar, EXP bar, timer, kills, etc.)
            self._draw_game_ui()

            if self.levelup_active:
                self._draw_levelup_overlay()

            # Debug hitboxes
            if self.debug_mode:
                # Player Hitbox
                Color(1, 0, 0, 0.8) # Red for player
                hx, hy, hw, hh = self.player.get_hitbox()
                Line(rectangle=(hx, hy, hw, hh), width=2)

                # Bullet Hitboxes
                Color(0, 1, 0, 0.8) # Green for bullets
                for b in self.bullets:
                    bx, by, bw, bh = b.get_hitbox()
                    Line(rectangle=(bx, by, bw, bh), width=1)

                # Enemy Projectile Hitboxes
                Color(1, 0.5, 0, 0.8) # Orange for enemy projectiles
                for proj in self.enemy_projectiles:
                    px, py, pw, ph = proj.get_hitbox()
                    Line(rectangle=(px, py, pw, ph), width=1)

                # EXP Orb hitboxes and pull radius
                Color(0.2, 1, 0.3, 0.85)
                for orb in self.exp_orbs:
                    ox, oy, ow, oh = orb.get_hitbox()
                    Line(rectangle=(ox, oy, ow, oh), width=1)
                Color(0.2, 1, 0.3, 0.25)
                pbox = self.player.get_hitbox()
                center_x = pbox[0] + pbox[2] / 2
                center_y = pbox[1] + pbox[3] / 2
                Line(circle=(center_x, center_y, self._get_exp_pull_radius()), width=1)

                # Enemy Hitbox
                Color(0, 0, 1, 0.8) # Blue for enemy
                for enemy in self.enemies:
                    ex, ey, ew, eh = enemy.get_hitbox()
                    Line(rectangle=(ex, ey, ew, eh), width=2)
                    
                    # Enemy Attack Hitbox (hand)
                    attack_box = enemy.get_attack_hitbox()
                    if attack_box:
                        Color(1, 1, 0, 0.8) # Yellow for attack hitbox
                        ax, ay, aw, ah = attack_box
                        Line(rectangle=(ax, ay, aw, ah), width=2)

                # Special Enemy Hitbox
                Color(1, 0, 1, 0.8) # Magenta for special enemy
                for special_enemy in self.special_enemies:
                    ex, ey, ew, eh = special_enemy.get_hitbox()
                    Line(rectangle=(ex, ey, ew, eh), width=2)
                    
                    # Special Enemy Attack Hitbox (tail/hand)
                    attack_box = special_enemy.get_attack_hitbox()
                    if attack_box:
                        Color(1, 0.5, 0, 0.8) # Orange for special attack hitbox
                        ax, ay, aw, ah = attack_box
                        Line(rectangle=(ax, ay, aw, ah), width=2)

                # Enemy Path to Player
                Color(1, 1, 0, 0.8) # Yellow for path
                for enemy in self.enemies:
                    px1, py1, px2, py2 = enemy.get_path_points()
                    Line(points=[px1, py1, px2, py2], width=2)

                # Special Enemy Path to Player
                Color(0, 1, 1, 0.8) # Cyan for special enemy path
                for special_enemy in self.special_enemies:
                    px1, py1, px2, py2 = special_enemy.get_path_points()
                    Line(points=[px1, py1, px2, py2], width=2)

                # --- Debug stat labels on entities ---
                self._draw_debug_entity_stats()

    def _draw_debug_entity_stats(self):
        """Draw HP / DMG / SPD / Cooldown text above each entity in debug mode."""
        # Player stats
        phx, phy, phw, phh = self.player.get_hitbox()
        p_info = (
            f"HP:{self.player.hp}/{self.player.max_hp}  "
            f"FireRate:{self.fire_rate:.2f}s  "
            f"SPD:{self.player.speed}"
        )
        self._draw_label_at(p_info, phx + phw / 2, phy + phh + 80, (0, 1, 0.5, 1))

        # Regular enemies
        for enemy in self.enemies:
            ehx, ehy, ehw, ehh = enemy.get_hitbox()
            is_atk = getattr(enemy, 'is_attacking', False)
            e_info = (
                f"HP:{enemy.hp}/{enemy.max_hp}  "
                f"DMG:{enemy.damage}  "
                f"SPD:{enemy.speed}  "
                f"AtkSpd:{enemy.attack_anim_speed:.2f}  "
                f"{'ATK' if is_atk else 'walk'}"
            )
            self._draw_label_at(e_info, ehx + ehw / 2, ehy + ehh + 75, (1, 0.7, 0.3, 1))

        # Special enemies
        for se in self.special_enemies:
            shx, shy, shw, shh = se.get_hitbox()
            is_atk = getattr(se, 'is_attacking', False)
            se_name = se.asset_path.split('/')[-1]
            se_info = (
                f"{se_name}  HP:{se.hp}/{se.max_hp}  "
                f"DMG:{se.damage}  SPD:{se.speed}  "
                f"AtkSpd:{se.attack_anim_speed:.2f}  "
            )
            if "Kitsune" in se.asset_path:
                remaining_cd = max(0.0, se.fire_cooldown - se.fire_timer)
                se_info += f"FireCD:{remaining_cd:.1f}/{se.fire_cooldown:.1f}s  AI:{se.ai_state}"
            else:
                se_info += f"{'ATK' if is_atk else 'walk'}"
            self._draw_label_at(se_info, shx + shw / 2, shy + shh + 85, (0.8, 0.3, 1, 1))

    def _draw_label_at(self, text: str, cx: float, y: float, color_tuple=(1, 1, 1, 1)):
        """Render a small debug label centered at (cx, y) on the canvas with outline."""
        # Draw dark outline by rendering the text offset in 4 directions
        outline_color = (0, 0, 0, 1)
        outline_lbl = CoreLabel(text=text, font_size=30, color=outline_color)
        outline_lbl.refresh()
        outline_tex = outline_lbl.texture

        lbl = CoreLabel(text=text, font_size=30, color=color_tuple)
        lbl.refresh()
        tex = lbl.texture
        if tex:
            w, h = tex.size
            x = cx - w / 2
            with self.canvas:
                # Outline (offset in 4 directions)
                if outline_tex:
                    Color(*outline_color)
                    for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                        Rectangle(texture=outline_tex, pos=(x + dx, y + dy), size=(w, h))
                # Foreground text
                Color(*color_tuple)
                Rectangle(texture=tex, pos=(x, y), size=(w, h))

    def _draw_timer(self):
        """Draw the timer text on the canvas at the top center."""
        remaining = self.GAME_DURATION - self.game_time
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        self.timer_label.text = f"{minutes:02d}:{seconds:02d}"
        self.timer_label.texture_update()
        texture = self.timer_label.texture
        if texture:
            label_w, label_h = texture.size
            x = (self.width - label_w) / 2
            y = self.height - label_h - 20
            Color(1, 1, 1, 1)
            Rectangle(texture=texture, pos=(x, y), size=(label_w, label_h))

    # ─── Enhanced UI Drawing Methods ────────────────────────────────────

    def _draw_outlined_text(self, text, x, y, font_size=24, color=(1, 1, 1, 1),
                            anchor_x='left', anchor_y='bottom', bold=False):
        """Draw text with dark outline at the specified position. Returns (w, h)."""
        lbl = CoreLabel(text=text, font_size=font_size, color=color, bold=bold)
        lbl.refresh()
        tex = lbl.texture
        if not tex:
            return (0, 0)
        w, h = tex.size
        draw_x, draw_y = x, y
        if anchor_x == 'center':
            draw_x = x - w / 2
        elif anchor_x == 'right':
            draw_x = x - w
        if anchor_y == 'center':
            draw_y = y - h / 2
        elif anchor_y == 'top':
            draw_y = y - h
        shadow = CoreLabel(text=text, font_size=font_size, color=(0, 0, 0, 1), bold=bold)
        shadow.refresh()
        stex = shadow.texture
        if stex:
            Color(0, 0, 0, 0.9)
            for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                Rectangle(texture=stex, pos=(draw_x + dx, draw_y + dy), size=(w, h))
        Color(*color)
        Rectangle(texture=tex, pos=(draw_x, draw_y), size=(w, h))
        return (w, h)

    def _draw_game_ui(self):
        """Main UI orchestrator — draws all HUD elements on canvas."""
        s = self.height / 1080.0 if self.height > 0 else 1.0
        # Low HP warning vignette
        if not self.player.is_dead and self.player.max_hp > 0:
            hp_ratio = self.player.hp / self.player.max_hp
            if hp_ratio < 0.3:
                pulse = 0.08 + 0.06 * math.sin(self.game_time * 5)
                Color(0.7, 0, 0, pulse)
                Rectangle(pos=(0, 0), size=self.size)
        self._draw_hud_panel(s)
        self._draw_timer_panel(s)
        self._draw_combat_info_panel(s)
        self._draw_ammo_panel(s)
        
        # Death overlay
        if self.player.is_dead:
            Color(0.03, 0, 0, 0.55)
            Rectangle(pos=(0, 0), size=self.size)
            self._draw_outlined_text(
                "DEFEATED", self.width / 2, self.height / 2,
                font_size=int(64 * s), color=(0.85, 0.12, 0.1, 1),
                anchor_x='center', anchor_y='center', bold=True
            )

    def _draw_ammo_panel(self, s):
        """Draw the ammo counter prominently at the bottom right of the screen."""
        ammo = getattr(self.player, 'ammo', 30)
        max_ammo = getattr(self.player, 'max_ammo', 30)
        is_reloading = getattr(self.player, 'is_reloading', False)
        reload_timer = getattr(self.player, 'reload_timer', 0.0)

        if is_reloading:
            ammo_text = f"RELOADING... {reload_timer:.1f}s"
            ammo_color = (0.9, 0.8, 0.2, 1)
        else:
            ammo_text = f"Ammo: {ammo}/{max_ammo}"
            ammo_color = (0.95, 0.95, 0.95, 1) if ammo > 0 else (0.9, 0.2, 0.2, 1)

        self._draw_outlined_text(
            ammo_text, self.width - 40 * s, 40 * s,
            font_size=int(32 * s), color=ammo_color,
            anchor_x='right', anchor_y='bottom', bold=True
        )

        # Draw Firing Mode
        mode = getattr(self.player, 'firing_mode', 'AUTO')
        mode_text = f"Mode: {mode}"
        self._draw_outlined_text(
            mode_text, self.width - 40 * s, 40 * s + 36 * s,
            font_size=int(22 * s), color=(0.8, 0.9, 1.0, 0.9),
            anchor_x='right', anchor_y='bottom', bold=True
        )

    def _draw_hud_panel(self, s):
        """Draw the player status HUD panel in the top-left corner."""
        pad = 16 * s
        panel_x = 16 * s
        panel_w = 400 * s
        panel_h = 150 * s
        panel_y = self.height - panel_h - 16 * s

        # Panel background
        Color(0.05, 0.05, 0.12, 0.75)
        RoundedRectangle(pos=(panel_x, panel_y), size=(panel_w, panel_h), radius=[12 * s])
        Color(0.45, 0.42, 0.55, 0.5)
        Line(rounded_rectangle=(panel_x, panel_y, panel_w, panel_h, 12 * s), width=1.5)

        # ── Level badge ──
        badge_x = panel_x + pad
        badge_y = panel_y + panel_h - 36 * s
        badge_r = 16 * s
        Color(0.85, 0.7, 0.15, 0.9)
        Ellipse(pos=(badge_x, badge_y), size=(badge_r * 2, badge_r * 2))
        self._draw_outlined_text(
            f"{self.player.level}", badge_x + badge_r, badge_y + badge_r,
            font_size=int(16 * s), color=(0.1, 0.05, 0, 1),
            anchor_x='center', anchor_y='center', bold=True
        )
        self._draw_outlined_text(
            f"LV {self.player.level}", badge_x + badge_r * 2 + 8 * s, badge_y + 6 * s,
            font_size=int(20 * s), color=(1, 0.92, 0.5, 1), bold=True
        )
        # Stat points indicator
        if self.player.stat_points > 0:
            self._draw_outlined_text(
                f"+{self.player.stat_points} SP", panel_x + panel_w - pad, badge_y + 6 * s,
                font_size=int(16 * s), color=(0.3, 1, 0.5, 1),
                anchor_x='right', bold=True
            )

        # ── HP Bar ──
        bar_x = panel_x + pad
        bar_w = panel_w - pad * 2
        bar_h = 22 * s
        hp_bar_y = panel_y + panel_h - 68 * s

        # HP heart icon (red circle)
        heart_size = 18 * s
        Color(0.9, 0.15, 0.15, 1)
        Ellipse(pos=(bar_x, hp_bar_y + (bar_h - heart_size) / 2), size=(heart_size, heart_size))
        hp_bar_x = bar_x + heart_size + 6 * s
        hp_bar_w = bar_w - heart_size - 6 * s

        # Bar background
        Color(0.2, 0.08, 0.08, 0.9)
        RoundedRectangle(pos=(hp_bar_x, hp_bar_y), size=(hp_bar_w, bar_h), radius=[4 * s])
        # Bar fill
        hp_ratio = max(0, min(1, self.player.hp / self.player.max_hp)) if self.player.max_hp > 0 else 0
        fill_w = hp_bar_w * hp_ratio
        if fill_w > 1:
            if hp_ratio > 0.5:
                Color(0.15, 0.78, 0.25, 0.95)
            elif hp_ratio > 0.25:
                Color(0.95, 0.75, 0.1, 0.95)
            else:
                Color(0.88, 0.12, 0.12, 0.95)
            RoundedRectangle(pos=(hp_bar_x, hp_bar_y), size=(fill_w, bar_h), radius=[4 * s])
        # HP text overlay
        self._draw_outlined_text(
            f"{int(self.player.hp)}/{int(self.player.max_hp)}",
            hp_bar_x + hp_bar_w / 2, hp_bar_y + bar_h / 2,
            font_size=int(14 * s), color=(1, 1, 1, 1),
            anchor_x='center', anchor_y='center', bold=True
        )

        # ── EXP Bar ──
        exp_bar_y = hp_bar_y - 18 * s
        exp_bar_h = 12 * s
        Color(0.08, 0.08, 0.18, 0.9)
        RoundedRectangle(pos=(bar_x, exp_bar_y), size=(bar_w, exp_bar_h), radius=[3 * s])
        exp_ratio = (self.player.exp / self.player.next_exp) if self.player.next_exp > 0 else 0
        exp_fill_w = bar_w * max(0, min(1, exp_ratio))
        if exp_fill_w > 1:
            Color(0.95, 0.8, 0.15, 0.9)
            RoundedRectangle(pos=(bar_x, exp_bar_y), size=(exp_fill_w, exp_bar_h), radius=[3 * s])
        self._draw_outlined_text(
            f"EXP {int(self.player.exp)}/{int(self.player.next_exp)}",
            bar_x + bar_w / 2, exp_bar_y + exp_bar_h / 2,
            font_size=int(11 * s), color=(1, 0.95, 0.7, 1),
            anchor_x='center', anchor_y='center'
        )

        # ── Stats line ──
        stats_y = exp_bar_y - 20 * s
        stats_text = (
            f"STR {self.player.str}  DEX {self.player.dex}  AGI {self.player.agi}  "
            f"INT {self.player.int}  VIT {self.player.vit}  LCK {self.player.luck}"
        )
        self._draw_outlined_text(
            stats_text, bar_x, stats_y,
            font_size=int(12 * s), color=(0.72, 0.72, 0.82, 0.85)
        )

        # ── Combat info line ──
        combat_y = stats_y - 18 * s
        combat_text = (
            f"DMG {self.player.bullet_damage:.1f}   "
            f"Rate {self.player.fire_rate:.2f}s   "
            f"Crit {self.player.crit_chance * 100:.0f}%"
        )
        self._draw_outlined_text(
            combat_text, bar_x, combat_y,
            font_size=int(11 * s), color=(0.6, 0.65, 0.72, 0.75)
        )

    def _draw_timer_panel(self, s):
        """Draw the styled timer panel at top center."""
        remaining = max(0, self.GAME_DURATION - self.game_time)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        timer_text = f"{minutes:02d}:{seconds:02d}"

        panel_w = 180 * s
        panel_h = 72 * s
        panel_x = (self.width - panel_w) / 2
        panel_y = self.height - panel_h - 12 * s

        # Panel background
        Color(0.05, 0.05, 0.12, 0.78)
        RoundedRectangle(pos=(panel_x, panel_y), size=(panel_w, panel_h), radius=[10 * s])
        # Border — color shifts with time
        if remaining > 300:
            Color(0.4, 0.4, 0.55, 0.6)
        elif remaining > 60:
            Color(0.9, 0.75, 0.15, 0.7)
        else:
            Color(0.9, 0.2, 0.15, 0.8)
        Line(rounded_rectangle=(panel_x, panel_y, panel_w, panel_h, 10 * s), width=1.5)

        # Timer text
        timer_color = (1, 1, 1, 1) if remaining > 60 else (1, 0.4, 0.3, 1)
        self._draw_outlined_text(
            timer_text, self.width / 2, panel_y + panel_h / 2 + 8 * s,
            font_size=int(34 * s), color=timer_color,
            anchor_x='center', anchor_y='center', bold=True
        )

        # Difficulty indicator
        progress = min(1.0, self.game_time / self.GAME_DURATION) if self.GAME_DURATION > 0 else 0
        diff_level = int(progress * 10) + 1
        diff_color = (
            min(1.0, 0.4 + progress * 0.6),
            max(0.3, 0.9 - progress * 0.6),
            0.2, 0.9
        )
        self._draw_outlined_text(
            f"Danger Lv.{diff_level}", self.width / 2, panel_y + 8 * s,
            font_size=int(12 * s), color=diff_color,
            anchor_x='center', anchor_y='bottom'
        )

    def _draw_combat_info_panel(self, s):
        """Draw kill counter and enemy count in the top-right corner."""
        panel_w = 190 * s
        panel_h = 85 * s
        panel_x = self.width - panel_w - 16 * s
        panel_y = self.height - panel_h - 16 * s
        pad = 14 * s

        Color(0.05, 0.05, 0.12, 0.75)
        RoundedRectangle(pos=(panel_x, panel_y), size=(panel_w, panel_h), radius=[10 * s])
        Color(0.5, 0.35, 0.35, 0.45)
        Line(rounded_rectangle=(panel_x, panel_y, panel_w, panel_h, 10 * s), width=1.2)

        # Kill count
        self._draw_outlined_text(
            f"Kills: {self.kill_count}", panel_x + pad, panel_y + panel_h - 28 * s,
            font_size=int(18 * s), color=(1, 0.85, 0.3, 1), bold=True
        )
        # Enemy count
        total_enemies = len(self.enemies) + len(self.special_enemies)
        self._draw_outlined_text(
            f"Enemies: {total_enemies}", panel_x + pad, panel_y + panel_h - 52 * s,
            font_size=int(14 * s), color=(0.9, 0.5, 0.4, 0.9)
        )
        # Orb count
        self._draw_outlined_text(
            f"Orbs: {len(self.exp_orbs)}", panel_x + pad, panel_y + panel_h - 72 * s,
            font_size=int(12 * s), color=(0.4, 0.95, 0.5, 0.8)
        )

    def _update_debug(self, dt: float):
        fps = Clock.get_fps() or 0
        god_str = "  [GODMODE ON]" if self.god_mode else ""
        info = (
            f"FPS: {fps:.1f}{god_str}\n"
            f"Bullets: {len(self.bullets)}\n"
            f"Enemies: {len(self.enemies)}\n"
            f"Special Enemies: {len(self.special_enemies)}\n"
            f"Enemy Projectiles: {len(self.enemy_projectiles)}\n"
            f"EXP Orbs: {len(self.exp_orbs)}"
        )
        if self.debug_mode:
            active_statuses = getattr(self.player, 'status', None)
            status_text = "none"
            if active_statuses:
                status_dict = active_statuses.to_dict()
                if status_dict:
                    status_parts = []
                    for name, payload in status_dict.items():
                        status_parts.append(f"{name}({payload['duration']:.1f}s x{payload['stacks']})")
                    status_text = ", ".join(status_parts)

            info += (
                f"\nTime Speed: {self.time_speed_multiplier}x"
                f"\nSpawn Interval: {self.spawn_interval:.2f}s"
                f"\nEnemy Speed x: {self.enemy_speed_multiplier:.2f}"
                f"\nEXP Pull Radius: {self._get_exp_pull_radius():.0f}"
                f"\nPlayer LV:{self.player.level} EXP:{int(self.player.exp)}/{int(self.player.next_exp)} SP:{self.player.stat_points}"
                f"\nPlayer HP:{self.player.hp:.0f}/{self.player.max_hp:.0f} Ammo:{getattr(self.player, 'ammo', 0)}/{getattr(self.player, 'max_ammo', 30)} DMG:{self.player.bullet_damage:.1f}"
                f"\nStats STR:{self.player.str} DEX:{self.player.dex} AGI:{self.player.agi} INT:{self.player.int} VIT:{self.player.vit} LUCK:{self.player.luck}"
                f"\nStatus Effects: {status_text}"
            )
        self.debug_label.text = info
        if self.debug_mode:
            self.pos_label.text = f"Player: ({self.player.x:.1f}, {self.player.y:.1f})"
            self.pos_label.pos = (self.width - 220, self.height - 40)
        else:
            self.pos_label.text = ""

    def _spawn_bullet(self):
        mx, my = Window.mouse_pos
        cursor = Vector(*self.to_widget(mx, my))

        pbox = self.player.get_hitbox()
        shooter_origin = Vector(pbox[0] + pbox[2] / 2, pbox[1] + pbox[3] / 2)
        raw_direction = cursor - shooter_origin

        if raw_direction.length() == 0:
            raw_direction = Vector(self.player.facing, 0)

        # Face left/right based on cursor
        self.player.facing = 1 if raw_direction.x >= 0 else -1

        # Clamp aim to a 160-degree cone around facing direction (±80°)
        aim_angle = math.degrees(math.atan2(raw_direction.y, raw_direction.x))
        if self.player.facing == 1:
            clamped_angle = max(-80.0, min(80.0, aim_angle))
        else:
            relative_angle = ((aim_angle - 180.0 + 180.0) % 360.0) - 180.0
            relative_angle = max(-80.0, min(80.0, relative_angle))
            clamped_angle = 180.0 + relative_angle

        rad = math.radians(clamped_angle)
        shot_direction = Vector(math.cos(rad), math.sin(rad))

        muzzle_pos = self.player.get_muzzle_position(shot_direction)
        bullet_w, bullet_h = BulletEntity.SIZE
        bullet_center = muzzle_pos + shot_direction * (bullet_w / 2)
        spawn_pos = bullet_center - Vector(bullet_w / 2, bullet_h / 2)
        bullet = BulletEntity(spawn_pos, shot_direction)
        is_crit = random.random() < self.player.crit_chance
        bullet.damage = self.player.bullet_damage * (1.75 if is_crit else 1.0)
        bullet.is_crit = is_crit
        self.bullets.append(bullet)

    def _grant_player_exp(self, amount: int):
        levels_gained = self.player.add_experience(amount)
        if levels_gained <= 0:
            return

        self.pending_levelups += levels_gained
        self._sync_combat_from_player()
        if not self.levelup_active:
            self._open_next_levelup()

    def _open_next_levelup(self):
        if self.pending_levelups <= 0:
            self.levelup_active = False
            self.levelup_choices = []
            return

        self.pending_levelups -= 1
        self.levelup_active = True
        choice_pool = ["str", "dex", "agi", "int", "vit", "luck"]
        self.levelup_choices = random.sample(choice_pool, 3)

        self.player.stop_shooting()
        self.firing = False

    def _drop_exp_orbs(self, enemy, total_exp: int):
        if total_exp <= 0:
            return

        hitbox = enemy.get_hitbox()
        center = Vector(hitbox[0] + hitbox[2] / 2, hitbox[1] + hitbox[3] / 2)

        chunk_size = 12
        orb_count = max(1, min(8, math.ceil(total_exp / chunk_size)))
        remaining = total_exp
        for idx in range(orb_count):
            orb_value = chunk_size if idx < orb_count - 1 else max(1, remaining)
            remaining -= orb_value

            offset = Vector(random.uniform(-24, 24), random.uniform(-18, 18))
            self.exp_orbs.append(ExpOrb(center + offset, orb_value))

    def _get_exp_pull_radius(self) -> float:
        return 150.0 + (self.player.luck * 14.0) + (self.player.int * 8.0)

    def _apply_levelup_choice(self, choice_index: int):
        if not self.levelup_active:
            return
        if choice_index < 0 or choice_index >= len(self.levelup_choices):
            return

        chosen_stat = self.levelup_choices[choice_index]
        if self.player.allocate_stat(chosen_stat):
            self._sync_combat_from_player()

        if self.pending_levelups > 0:
            self._open_next_levelup()
        else:
            self.levelup_active = False
            self.levelup_choices = []

    def _draw_levelup_overlay(self):
        """Draw an enhanced level-up selection overlay with card UI."""
        s = self.height / 1080.0 if self.height > 0 else 1.0

        # Full-screen dark overlay
        Color(0, 0, 0, 0.6)
        Rectangle(pos=(0, 0), size=self.size)

        # Central panel
        panel_w = self.width * 0.55
        panel_h = self.height * 0.52
        panel_x = (self.width - panel_w) / 2
        panel_y = (self.height - panel_h) / 2

        # Panel background layers
        Color(0.08, 0.07, 0.14, 0.95)
        RoundedRectangle(pos=(panel_x, panel_y), size=(panel_w, panel_h), radius=[20 * s])
        inner_pad = 4 * s
        Color(0.12, 0.11, 0.2, 0.9)
        RoundedRectangle(
            pos=(panel_x + inner_pad, panel_y + inner_pad),
            size=(panel_w - inner_pad * 2, panel_h - inner_pad * 2),
            radius=[16 * s]
        )
        # Golden border
        Color(0.85, 0.7, 0.2, 0.8)
        Line(rounded_rectangle=(panel_x, panel_y, panel_w, panel_h, 20 * s), width=2.5)

        # Title
        title_y = panel_y + panel_h - 55 * s
        self._draw_outlined_text(
            "LEVEL UP!", self.width / 2, title_y,
            font_size=int(42 * s), color=(1, 0.9, 0.3, 1),
            anchor_x='center', anchor_y='center', bold=True
        )

        # Subtitle
        subtitle_y = title_y - 35 * s
        remaining_text = f"({self.pending_levelups} more)" if self.pending_levelups > 0 else ""
        self._draw_outlined_text(
            f"Choose your upgrade  {remaining_text}", self.width / 2, subtitle_y,
            font_size=int(20 * s), color=(0.85, 0.85, 0.9, 0.9),
            anchor_x='center', anchor_y='center'
        )

        # Separator line
        sep_y = subtitle_y - 20 * s
        Color(0.5, 0.45, 0.6, 0.4)
        Line(points=[panel_x + 40 * s, sep_y, panel_x + panel_w - 40 * s, sep_y], width=1)

        # Option cards
        stat_descriptions = {
            "str": ("STR", "+1", "Bullet Damage +", (0.95, 0.35, 0.3, 1)),
            "dex": ("DEX", "+1", "Fire Rate +", (0.3, 0.85, 0.95, 1)),
            "agi": ("AGI", "+1", "Move Speed +", (0.3, 0.95, 0.45, 1)),
            "int": ("INT", "+1", "Skill Cooldown -", (0.6, 0.4, 0.95, 1)),
            "vit": ("VIT", "+1", "Max HP +", (0.95, 0.55, 0.7, 1)),
            "luck": ("LUCK", "+1", "Crit & Drop +", (0.95, 0.85, 0.2, 1)),
        }

        card_count = len(self.levelup_choices)
        card_spacing = 24 * s
        total_card_width = panel_w - 80 * s
        card_w = (total_card_width - card_spacing * (card_count - 1)) / max(1, card_count)
        card_h = panel_h * 0.48
        card_start_x = panel_x + 40 * s
        card_y = panel_y + 30 * s

        for idx, stat_key in enumerate(self.levelup_choices):
            cx = card_start_x + idx * (card_w + card_spacing)
            stat_name, bonus, desc, accent = stat_descriptions.get(
                stat_key, (stat_key.upper(), "+1", "", (1, 1, 1, 1))
            )

            # Card background
            Color(0.1, 0.1, 0.18, 0.92)
            RoundedRectangle(pos=(cx, card_y), size=(card_w, card_h), radius=[12 * s])
            # Card border
            Color(*accent[:3], 0.6)
            Line(rounded_rectangle=(cx, card_y, card_w, card_h, 12 * s), width=1.8)

            # Key number hint
            key_y = card_y + card_h - 35 * s
            Color(*accent[:3], 0.15)
            Ellipse(pos=(cx + card_w / 2 - 18 * s, key_y - 4 * s), size=(36 * s, 36 * s))
            self._draw_outlined_text(
                f"{idx + 1}", cx + card_w / 2, key_y + 14 * s,
                font_size=int(22 * s), color=accent,
                anchor_x='center', anchor_y='center', bold=True
            )

            # Stat name
            self._draw_outlined_text(
                stat_name, cx + card_w / 2, key_y - 40 * s,
                font_size=int(28 * s), color=accent,
                anchor_x='center', anchor_y='center', bold=True
            )

            # Bonus text
            self._draw_outlined_text(
                bonus, cx + card_w / 2, key_y - 72 * s,
                font_size=int(20 * s), color=(0.9, 0.9, 0.9, 0.9),
                anchor_x='center', anchor_y='center'
            )

            # Description
            self._draw_outlined_text(
                desc, cx + card_w / 2, key_y - 102 * s,
                font_size=int(14 * s), color=(0.7, 0.7, 0.75, 0.8),
                anchor_x='center', anchor_y='center'
            )

            # Current value
            current_val = getattr(self.player, stat_key, 0)
            self._draw_outlined_text(
                f"Current: {current_val}", cx + card_w / 2, card_y + 20 * s,
                font_size=int(13 * s), color=(0.6, 0.6, 0.65, 0.7),
                anchor_x='center', anchor_y='bottom'
            )

        # Bottom hint
        self._draw_outlined_text(
            "Click or Press  1  /  2  /  3  to select", self.width / 2, panel_y + 8 * s,
            font_size=int(16 * s), color=(0.7, 0.7, 0.75, 0.7),
            anchor_x='center', anchor_y='bottom'
        )

    def _get_enemy_exp_reward(self, enemy) -> int:
        if isinstance(enemy, SpecialEnemyEntity):
            return 80

        asset_path = getattr(enemy, "asset_path", "")
        if "Zombie_1" in asset_path:
            return 18
        if "Zombie_2" in asset_path:
            return 28
        if "Zombie_3" in asset_path:
            return 16
        if "Zombie_4" in asset_path:
            return 24
        return 20

    def _sync_combat_from_player(self):
        self.bullet_damage = self.player.bullet_damage
        self.fire_rate = self.player.fire_rate

    def _update_progression_hud(self):
        """Progression HUD is now drawn on canvas in _draw_hud_panel. Keep label cleared."""
        self.progression_label.text = ""

    def _spawn_enemy(self):
        """Spawn enemy at random edge (left or right) within the player's walkable band."""
        # Don't spawn if at max capacity
        if len(self.enemies) >= self.MAX_ENEMIES:
            return

        spawn_left = random.choice([True, False])

        # Spawn only in the same Y band that player can reach.
        min_y, max_y = self._get_player_walkable_y_range()
        y_pos = random.uniform(min_y, max_y)

        enemy_width = self.player.size[0]
        x_pos = self._get_enemy_offscreen_x(enemy_width, spawn_left)

        # Spawn enemy with size relative to player (scale_to_player=1.0 = same size)
        self.enemies.append(EnemyEntity(
            pos=Vector(x_pos, y_pos),
            player_size=self.player.size,
            scale_to_player=1.0
        ))
        self.enemy_spawn_counter += 1
        self.enemies[-1].spawn_order = self.enemy_spawn_counter

    def _spawn_special_enemy(self):
        """Spawn special enemy at random edge. Must not repeat last 2 types spawned. No max limit."""
        # Get available types (exclude last 2 spawned)
        available = [s for s in SpecialEnemyEntity.SKINS if s not in self.last_special_types]
        if not available:
            # Fallback if all excluded (shouldn't happen with 3 types and tracking 2)
            available = SpecialEnemyEntity.SKINS

        selected = random.choice(available)

        # Update last 2 tracking
        self.last_special_types.append(selected)
        if len(self.last_special_types) > 2:
            self.last_special_types.pop(0)

        # Spawn at random edge (same logic as basic enemy)
        spawn_left = random.choice([True, False])

        min_y, max_y = self._get_player_walkable_y_range()
        y_pos = random.uniform(min_y, max_y)

        special_enemy_width = self.player.size[0] * 1.2
        x_pos = self._get_enemy_offscreen_x(special_enemy_width, spawn_left)

        # Spawn special enemy with selected type
        special_index = len(self.special_enemies) + 1
        if special_index > 3:
            special_index = 3
        self.special_enemies.append(SpecialEnemyEntity(
            pos=Vector(x_pos, y_pos),
            player_size=self.player.size,
            asset_path=selected,
            special_index=special_index
        ))
        self.enemy_spawn_counter += 1
        self.special_enemies[-1].spawn_order = self.enemy_spawn_counter

    def _spawn_special_enemy_by_type(self, enemy_type: str):
        """Spawn a specific special enemy type at random edge (for debug mode)."""
        spawn_left = random.choice([True, False])

        min_y, max_y = self._get_player_walkable_y_range()
        y_pos = random.uniform(min_y, max_y)

        special_enemy_width = self.player.size[0] * 1.2
        x_pos = self._get_enemy_offscreen_x(special_enemy_width, spawn_left)

        special_index = len(self.special_enemies) + 1
        if special_index > 3:
            special_index = 3
        self.special_enemies.append(SpecialEnemyEntity(
            pos=Vector(x_pos, y_pos),
            player_size=self.player.size,
            asset_path=enemy_type,
            special_index=special_index
        ))
        self.enemy_spawn_counter += 1
        self.special_enemies[-1].spawn_order = self.enemy_spawn_counter

    def on_size(self, *args):
        if not self._did_initial_player_center and self.width > 0 and self.height > 0:
            self._spawn_player_at_screen_center()
            self._did_initial_player_center = True
        self.player.update(0, set(), (self.width, self.height))