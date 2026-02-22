from dataclasses import dataclass
from typing import Dict, List, Tuple

from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
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

        # Scale sprite so its height is 1/3 of the current window height
        base_texture = self.animations["idle"][0]
        target_height = Window.height / 3
        scale = target_height / base_texture.height
        width = base_texture.width * scale
        height = base_texture.height * scale

        super().__init__(pos=pos, size=(width, height), color=(1, 1, 1))

        self.current_anim = "idle"
        self.current_frame = 0
        self.frame_timer = 0.0
        self.animation_speed = 0.1  # seconds per frame
        self.facing = 1
        self.speed = 240  # units per second
        
        # Tighter hitbox for actual sprite content (excludes transparent padding)
        self.hitbox_scale = 0.5  # sprite content is roughly 50% of texture width
        self.hitbox_offset_x = width * 0.25  # center the hitbox
        self.hitbox_offset_y = 0  # bottom aligned
        self.hitbox_width = width * self.hitbox_scale
        self.hitbox_height = height * 0.85  # sprite content height

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

        # Vertical bounds: split height into 10 parts; block top 3 and bottom 1
        height = bounds[1]
        block_unit = height / 10.0
        min_y = block_unit  # bottom 1/10 blocked
        max_y_allowed = height - (3 * block_unit) - self.size[1]  # top 3/10 blocked

        self.pos.x = max(0, min(self.pos.x, max_x))
        self.pos.y = max(min_y, min(self.pos.y, max_y_allowed))

        # Advance animation frames
        frames = self.animations.get(self.current_anim, [])
        if not frames:
            return None

        self.frame_timer += dt
        if self.frame_timer >= self.animation_speed:
            self.frame_timer = 0.0
            self.current_frame = (self.current_frame + 1) % len(frames)

        return frames[self.current_frame]

    def get_hitbox(self) -> Tuple[float, float, float, float]:
        """Return actual sprite hitbox (x, y, width, height) for collision/debug."""
        return (
            self.pos.x + self.hitbox_offset_x,
            self.pos.y + self.hitbox_offset_y,
            self.hitbox_width,
            self.hitbox_height,
        )

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
