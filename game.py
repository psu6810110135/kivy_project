from typing import Set, List
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.vector import Vector

from entities import PlayerEntity, BulletEntity

class GameWidget(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player = PlayerEntity(pos=Vector(100, 100))
        self.bullets: List[BulletEntity] = []
        self.bg_texture = CoreImage("game_picture/background/bg2.png").texture
        self._keyboard = Window.request_keyboard(self._on_keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)
        self.pressed_keys: Set[str] = set()
        self.debug_label = Label(text="", pos=(10, 10), halign="left", valign="bottom")
        self.pos_label = Label(text="", halign="right", valign="top")
        self.debug_mode = False
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
            
        if key == 'spacebar' and not self.player.is_shooting:
            # Trigger player shot animation
            self.player.is_shooting = True
            
            # Spawn bullet
            bx = self.player.pos.x + (self.player.size[0] if self.player.facing == 1 else 0)
            by = self.player.pos.y + self.player.size[1] * 0.6 # Adjust height to gun barrel
            self.bullets.append(BulletEntity(Vector(bx, by), self.player.facing))
            return True

        self.pressed_keys.add(key)
        return True

    def _on_key_up(self, keyboard, keycode):
        self.pressed_keys.discard(keycode[1])
        return True

    def update(self, dt: float):
        self.player.update(dt, self.pressed_keys, (self.width, self.height))
        
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
            
            # Draw bullets
            for b in self.bullets:
                b.draw(self.canvas)
                
            if self.debug_mode:
                Color(1, 0, 0, 0.8)
                hx, hy, hw, hh = self.player.get_hitbox()
                Line(rectangle=(hx, hy, hw, hh), width=2)

    def _update_debug(self, dt: float):
        fps = Clock.get_fps() or 0
        info = f"FPS: {fps:.1f}\nBullets: {len(self.bullets)}"
        self.debug_label.text = info
        if self.debug_mode:
            self.pos_label.text = f"Player: ({self.player.x:.1f}, {self.player.y:.1f})"
            self.pos_label.pos = (self.width - 220, self.height - 40)
        else:
            self.pos_label.text = ""

    def on_size(self, *args):
        self.player.update(0, set(), (self.width, self.height))