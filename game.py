from typing import Set, List
import random
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.vector import Vector

from entities import PlayerEntity, BulletEntity, EnemyEntity

class GameWidget(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player = PlayerEntity(pos=Vector(100, 100))
        # Enemies spawn at left/right edges
        self.enemies: List[EnemyEntity] = []
        self.spawn_timer = 0.0
        self.spawn_interval = 2.0  # seconds between spawns
        self.bullets: List[BulletEntity] = []
        self.bg_texture = CoreImage("game_picture/background/bg2.png").texture
        self._keyboard = Window.request_keyboard(self._on_keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)
        self.pressed_keys: Set[str] = set()
        self.debug_label = Label(text="", pos=(10, 10), halign="left", valign="bottom")
        self.pos_label = Label(text="", halign="right", valign="top")
        self.debug_mode = False
        self.fire_rate = 0.15  # seconds between shots while holding
        self.fire_timer = 0.0
        self.firing = False
        self.add_widget(self.debug_label)
        self.add_widget(self.pos_label)

        Clock.schedule_interval(self.update, 1 / 60)

    def _on_keyboard_closed(self):
        if self._keyboard:
            self._keyboard.unbind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)
            self._keyboard = None

    def _on_key_down(self, keyboard, keycode, text, modifiers):
        key = keycode[1]

        if key == '9':
            self.debug_mode = not self.debug_mode
            return True

        self.pressed_keys.add(key)
        return True

    def _on_key_up(self, keyboard, keycode):
        self.pressed_keys.discard(keycode[1])
        return True

    def on_touch_down(self, touch):
        if touch.button == 'left':
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
        self.player.update(dt, self.pressed_keys, (self.width, self.height))

        # Spawn enemies at left/right edges
        self.spawn_timer += dt
        if self.spawn_timer >= self.spawn_interval:
            self.spawn_timer -= self.spawn_interval
            self._spawn_enemy()

        # Update all enemies
        for enemy in self.enemies[:]:
            enemy.update(dt, self.player.pos, (self.width, self.height))

        # Handle continuous fire when holding left click
        if self.firing:
            self.fire_timer += dt
            if self.fire_timer >= self.fire_rate:
                self.fire_timer -= self.fire_rate
                self._spawn_bullet()
        
        # Update and clean up bullets
        for b in self.bullets[:]:
            b.update(dt)
            if b.pos.x < 0 or b.pos.x > self.width:
                self.bullets.remove(b)
                
        self._draw_scene()
        self._update_debug(dt)

    def _draw_scene(self):
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=self.bg_texture, pos=(0, 0), size=self.size)
            
            # Draw player
            self.player.draw(self.canvas)

            # Draw all enemies
            for enemy in self.enemies:
                enemy.draw(self.canvas)
            
            # Draw bullets
            for b in self.bullets:
                b.draw(self.canvas)
                
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

                # Enemy Hitbox
                Color(0, 0, 1, 0.8) # Blue for enemy
                for enemy in self.enemies:
                    ex, ey, ew, eh = enemy.get_hitbox()
                    Line(rectangle=(ex, ey, ew, eh), width=2)

                # Enemy Path to Player
                Color(1, 1, 0, 0.8) # Yellow for path
                for enemy in self.enemies:
                    px1, py1, px2, py2 = enemy.get_path_points()
                    Line(points=[px1, py1, px2, py2], width=2)

    def _update_debug(self, dt: float):
        fps = Clock.get_fps() or 0
        info = f"FPS: {fps:.1f}\nBullets: {len(self.bullets)}"
        self.debug_label.text = info
        if self.debug_mode:
            self.pos_label.text = f"Player: ({self.player.x:.1f}, {self.player.y:.1f})"
            self.pos_label.pos = (self.width - 220, self.height - 40)
        else:
            self.pos_label.text = ""

    def _spawn_bullet(self):
        bx = self.player.pos.x + (self.player.size[0] if self.player.facing == 1 else 0)
        offset_x = -60
        if self.player.facing == 1:
            bx = self.player.pos.x + self.player.size[0] + offset_x
        else:
            bx = self.player.pos.x - offset_x
        by = self.player.pos.y + self.player.size[1] * 0.45
        self.bullets.append(BulletEntity(Vector(bx, by), self.player.facing))

    def _spawn_enemy(self):
        """Spawn enemy at random edge (left or right) within the player's walkable band."""
        spawn_left = random.choice([True, False])

        # Keep spawn area aligned with player's allowed Y band to avoid unreachable spawns
        block_unit = self.height / 10.0
        enemy_height = self.player.size[1]  # Enemy is scaled to player size below
        min_y = block_unit
        max_y = self.height - (3 * block_unit) - enemy_height
        max_y = max(min_y, max_y)  # Guard against small window sizes
        y_pos = random.uniform(min_y, max_y)

        x_pos = 50 if spawn_left else self.width - 50

        # Spawn enemy with size relative to player (scale_to_player=1.0 = same size)
        self.enemies.append(EnemyEntity(
            pos=Vector(x_pos, y_pos),
            player_size=self.player.size,
            scale_to_player=1.0
        ))

    def on_size(self, *args):
        self.player.update(0, set(), (self.width, self.height))