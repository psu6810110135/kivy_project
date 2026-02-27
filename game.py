from typing import Set, List
import random
import math
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.vector import Vector
from kivy.core.text import Label as CoreLabel

from entities import PlayerEntity, BulletEntity, EnemyEntity, SpecialEnemyEntity, EnemyProjectileEntity

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
        self.base_spawn_interval = 2.0  # Starting spawn interval
        self.spawn_interval = self.base_spawn_interval
        self.bullets: List[BulletEntity] = []
        
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
        self.debug_mode = False
        self.god_mode = False  # Player invincibility (debug key 8)
        self.bullet_damage = 10  # Damage per bullet
        self.fire_rate = 0.15  # seconds between shots while holding
        self.fire_timer = 0.0
        self.firing = False

        # Game timer
        self.game_time = 0.0
        self.time_speed_multiplier = 1.0  # Normal speed, can be increased in debug mode
        self.timer_label = Label(text="15:00", font_size=48, halign="center", valign="middle")
        self.timer_label.color = (1, 1, 1, 1)  # White
        self.timer_label.bold = True
        self.add_widget(self.timer_label)

        self.add_widget(self.debug_label)
        self.add_widget(self.pos_label)

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
            if self.player.is_dead:
                return True
            self.player.start_shooting()
            self.firing = True
            self.fire_timer = 0.0  # require hold; first shot after fire_rate
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.button == 'left':
            self.player.stop_shooting()
            self.firing = False
            return True
        return super().on_touch_up(touch)

    def update(self, dt: float):
        # Update game time (stop at max duration)
        if self.game_time < self.GAME_DURATION:
            self.game_time += dt * self.time_speed_multiplier
            if self.game_time > self.GAME_DURATION:
                self.game_time = self.GAME_DURATION

            # Update spawn interval based on elapsed time (faster spawning over time)
            # At 0:00 -> 2.0s interval, at 15:00 -> 0.5s interval
            progress = self.game_time / self.GAME_DURATION  # 0.0 to 1.0
            self.spawn_interval = self.base_spawn_interval - (progress * 1.5)  # 2.0 -> 0.5

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
            self._spawn_enemy()

        # Spawn special enemies every 3 minutes (affected by time speed multiplier)
        self.special_spawn_timer += dt * self.time_speed_multiplier
        if self.special_spawn_timer >= self.special_spawn_interval:
            self.special_spawn_timer -= self.special_spawn_interval
            self._spawn_special_enemy()

        # Update all enemies (target player's hitbox center for accurate pathing/aim)
        pbox = self.player.get_hitbox()
        player_center = Vector(pbox[0] + pbox[2] / 2, pbox[1] + pbox[3] / 2)
        for enemy in self.enemies[:]:
            enemy.update(dt, player_center, (self.width, self.height))
            if not enemy.is_dying:
                self._update_enemy_state(enemy)

        # Update all special enemies (Kitsune may spawn projectiles)
        for special_enemy in self.special_enemies[:]:
            if not special_enemy.is_dying:
                projectile = special_enemy.update(dt, player_center, (self.width, self.height))
                if projectile:  # Kitsune spawned a fire projectile
                    self.enemy_projectiles.append(projectile)
                self._update_enemy_state(special_enemy)
            else:
                special_enemy.update(dt, player_center, (self.width, self.height))

        # Light separation so enemies don't stack
        self._separate_enemies()

        # Re-clamp all enemies to walkable Y band after separation push
        height = self.height if self.height > 0 else Window.height
        block_unit = height / 10.0
        walk_min_y = block_unit
        for e in self.enemies + self.special_enemies:
            walk_max_y = height - (3 * block_unit) - e.size[1]
            e.pos.y = max(walk_min_y, min(e.pos.y, max(walk_min_y, walk_max_y)))

        # Handle continuous fire when holding left click
        if self.firing and not self.player.is_dead:
            self.fire_timer += dt
            if self.fire_timer >= self.fire_rate:
                self.fire_timer -= self.fire_rate
                self._spawn_bullet()
        
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
                    enemy.take_damage(self.bullet_damage)
                    hit = True
                    break
            if not hit:
                # Check collision with special enemies
                for se in self.special_enemies[:]:
                    if se.is_dying:
                        continue
                    if self._rects_intersect(bullet_box, se.get_hitbox()):
                        se.take_damage(self.bullet_damage)
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

            # Draw player with red flash if hit
            if hasattr(self, 'player_hit_flash') and self.player_hit_flash > 0:
                # Flash red when hit
                Color(1, 0.3, 0.3, 1)
            else:
                Color(1, 1, 1, 1)
            self.player.draw(self.canvas)
            Color(1, 1, 1, 1)  # Reset color

            # Draw enemies using danger-aware Y-sort ordering.
            for enemy in self._get_enemy_render_order():
                enemy.draw(self.canvas)

            # Draw bullets
            for b in self.bullets:
                b.draw(self.canvas)

            # Draw enemy projectiles
            for proj in self.enemy_projectiles:
                proj.draw(self.canvas)

            # Draw timer at top center
            self._draw_timer()

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

    def _update_debug(self, dt: float):
        fps = Clock.get_fps() or 0
        god_str = "  [GODMODE ON]" if self.god_mode else ""
        info = f"FPS: {fps:.1f}{god_str}\nBullets: {len(self.bullets)}\nEnemies: {len(self.enemies)}\nSpecial Enemies: {len(self.special_enemies)}\nEnemy Projectiles: {len(self.enemy_projectiles)}"
        if self.debug_mode:
            info += f"\nTime Speed: {self.time_speed_multiplier}x\nSpawn Interval: {self.spawn_interval:.2f}s"
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
        self.bullets.append(BulletEntity(spawn_pos, shot_direction))

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
        self.special_enemies.append(SpecialEnemyEntity(
            pos=Vector(x_pos, y_pos),
            player_size=self.player.size,
            asset_path=selected
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

        self.special_enemies.append(SpecialEnemyEntity(
            pos=Vector(x_pos, y_pos),
            player_size=self.player.size,
            asset_path=enemy_type
        ))
        self.enemy_spawn_counter += 1
        self.special_enemies[-1].spawn_order = self.enemy_spawn_counter

    def on_size(self, *args):
        if not self._did_initial_player_center and self.width > 0 and self.height > 0:
            self._spawn_player_at_screen_center()
            self._did_initial_player_center = True
        self.player.update(0, set(), (self.width, self.height))