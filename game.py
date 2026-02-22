from typing import Set

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.vector import Vector

from entities import PlayerEntity


class GameWidget(Widget):
    """Phase 0 skeleton: basic loop, input, player movement, debug overlay."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player = PlayerEntity(pos=Vector(100, 100))
        self.entities = [self.player]
        self._keyboard = Window.request_keyboard(self._on_keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)
        self.pressed_keys: Set[str] = set()
        self.debug_label = Label(text="", pos=(10, 10), halign="left", valign="bottom")
        self.add_widget(self.debug_label)

        Clock.schedule_interval(self.update, 1 / 60)

    def _on_keyboard_closed(self):
        if self._keyboard:
            self._keyboard.unbind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)
            self._keyboard = None

    def _on_key_down(self, keyboard, keycode, text, modifiers):
        self.pressed_keys.add(keycode[1])
        return True

    def _on_key_up(self, keyboard, keycode):
        self.pressed_keys.discard(keycode[1])
        return True

    def update(self, dt: float):
        self._update_player(dt)
        self._draw_scene()
        self._update_debug(dt)

    def _update_player(self, dt: float):
        # Update sprite movement/animation using current pressed keys and widget bounds
        self.player.update(dt, self.pressed_keys, (self.width, self.height))

    def _draw_scene(self):
        self.canvas.clear()
        with self.canvas:
            Color(0.12, 0.12, 0.16)
            Rectangle(pos=(0, 0), size=self.size)
            for entity in self.entities:
                entity.draw(self.canvas)

    def _update_debug(self, dt: float):
        fps = Clock.get_fps() or 0
        info = f"FPS: {fps:.1f}\nEntities: {len(self.entities)}"
        self.debug_label.text = info

    def on_size(self, *args):
        # Ensure player remains in bounds when window resizes
        self._update_player(0)
