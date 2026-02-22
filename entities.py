from dataclasses import dataclass
from typing import Dict, List, Tuple

from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, PopMatrix, PushMatrix, Rectangle, Scale
from kivy.vector import Vector


@dataclass
class Entity:
    pos: Vector
    size: Tuple[float, float]
    color: Tuple[float, float, float]

    def draw(self, canvas):
        Color(*self.color)
        Rectangle(pos=self.pos, size=self.size)

    @property
    def x(self) -> float:
        return self.pos.x

    @property
    def y(self) -> float:
        return self.pos.y

    def move(self, delta: Vector):
        self.pos = self.pos + delta


class PlayerEntity(Entity):
    """Sprite-based player that supports idle/walk with facing flip."""

    def __init__(self, pos: Vector, asset_path: str = "game_picture/player/Soldier_1"):
        self.asset_path = asset_path
        self.animations: Dict[str, List] = {}
        self._load_animation("idle", "Idle", 7)
        self._load_animation("walk", "Walk", 7)

        # Use idle frame size as base display size, scaled up a bit for visibility
        base_texture = self.animations["idle"][0]
        scale = 1.8
        width = base_texture.width * scale
        height = base_texture.height * scale

        super().__init__(pos=pos, size=(width, height), color=(1, 1, 1))

        self.current_anim = "idle"
        self.current_frame = 0
        self.frame_timer = 0.0
        self.animation_speed = 0.1  # seconds per frame
        self.facing = 1
        self.speed = 240  # units per second

    def _load_animation(self, name: str, prefix: str, count: int):
        frames: List = []
        for idx in range(1, count + 1):
            path = f"{self.asset_path}/{prefix}{idx}.png"
            try:
                frames.append(CoreImage(path).texture)
            except Exception as exc:  # pragma: no cover - runtime asset load
                print(f"Failed to load {path}: {exc}")
        if frames:
            self.animations[name] = frames

    def update(self, dt: float, pressed_keys: set, bounds: Tuple[float, float]):
        """Update movement and animation based on input and keep within bounds."""
        move_vec = Vector(0, 0)
        if "w" in pressed_keys:
            move_vec += Vector(0, self.speed * dt)
        if "s" in pressed_keys:
            move_vec += Vector(0, -self.speed * dt)
        if "a" in pressed_keys:
            move_vec += Vector(-self.speed * dt, 0)
        if "d" in pressed_keys:
            move_vec += Vector(self.speed * dt, 0)

        if move_vec.length() > 0:
            self.facing = 1 if move_vec.x >= 0 else -1
            self.current_anim = "walk"
        else:
            self.current_anim = "idle"

        # Apply movement and clamp to widget bounds
        self.pos = self.pos + move_vec
        max_x = max(0, bounds[0] - self.size[0])
        max_y = max(0, bounds[1] - self.size[1])
        self.pos.x = max(0, min(self.pos.x, max_x))
        self.pos.y = max(0, min(self.pos.y, max_y))

        # Advance animation frames
        frames = self.animations.get(self.current_anim, [])
        if not frames:
            return None

        self.frame_timer += dt
        if self.frame_timer >= self.animation_speed:
            self.frame_timer = 0.0
            self.current_frame = (self.current_frame + 1) % len(frames)

        return frames[self.current_frame]

    def draw(self, canvas):
        texture = self.animations.get(self.current_anim, [None])[self.current_frame]
        if texture is None:
            return

        x, y = self.pos.x, self.pos.y
        if self.facing == -1:
            with canvas:
                Color(1, 1, 1, 1)
                PushMatrix()
                # Flip horizontally around sprite center
                origin = (x + self.size[0] / 2, y + self.size[1] / 2)
                Scale(x=-1, y=1, origin=origin)
                Rectangle(texture=texture, pos=(x, y), size=self.size)
                PopMatrix()
        else:
            with canvas:
                Color(1, 1, 1, 1)
                Rectangle(texture=texture, pos=(x, y), size=self.size)
