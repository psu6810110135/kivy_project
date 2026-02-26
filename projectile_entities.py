from typing import List, Tuple
import math

from kivy.graphics import Color, PopMatrix, PushMatrix, Rectangle, Rotate
from kivy.vector import Vector

from entity_base import Entity


class BulletEntity(Entity):
    """Projectile fired by player that travels toward cursor direction."""
    SIZE = (24, 6)

    def __init__(self, pos: Vector, direction: Vector):
        super().__init__(pos=pos, size=self.SIZE, color=(1, 1, 0))
        self.speed = 800
        if direction.length() == 0:
            direction = Vector(1, 0)
        self.velocity = direction.normalize() * self.speed
        self.angle = math.degrees(math.atan2(self.velocity.y, self.velocity.x))

    def update(self, dt: float):
        self.update_statuses(dt)
        self.move(Vector(self.velocity.x * dt, self.velocity.y * dt))

    def get_hitbox(self) -> Tuple[float, float, float, float]:
        """Returns the bullet's hitbox as (x, y, width, height)."""
        scale_x = 1.2
        scale_y = 1.6
        hit_w = self.size[0] * scale_x
        hit_h = self.size[1] * scale_y
        offset_x = (hit_w - self.size[0]) / 2
        offset_y = (hit_h - self.size[1]) / 2
        return (self.pos.x - offset_x, self.pos.y - offset_y, hit_w, hit_h)

    def draw(self, canvas):
        with canvas:
            Color(*self.color)
            PushMatrix()
            center_x = self.pos.x + self.size[0] / 2
            center_y = self.pos.y + self.size[1] / 2
            Rotate(angle=self.angle, origin=(center_x, center_y))
            Rectangle(pos=self.pos, size=self.size)
            PopMatrix()


class EnemyProjectileEntity(Entity):
    """Projectile fired by enemies (e.g., Kitsune's fire)."""

    def __init__(self, pos, target_pos, fire_textures: List = None):
        if not isinstance(pos, Vector):
            pos = Vector(pos[0], pos[1]) if hasattr(pos, '__len__') else Vector(pos.x, pos.y)
        if not isinstance(target_pos, Vector):
            target_pos = Vector(target_pos[0], target_pos[1]) if hasattr(target_pos, '__len__') else Vector(target_pos.x, target_pos.y)

        super().__init__(pos=pos, size=(160, 160), color=(1, 0.5, 0))

        projectile_center = self.pos + Vector(self.size[0] / 2, self.size[1] / 2)
        direction = target_pos - projectile_center
        self.velocity = direction.normalize() * 450 if direction.length() > 0 else Vector(0, 0)
        self.angle = math.degrees(math.atan2(self.velocity.y, self.velocity.x))

        self.fire_textures = fire_textures or []
        self.current_frame = 3
        self.frame_timer = 0.0
        self.animation_speed = 0.05
        self.hit = False

    def update(self, dt: float):
        self.update_statuses(dt)
        delta = Vector(self.velocity.x * dt, self.velocity.y * dt)
        self.pos = self.pos + delta

        if self.fire_textures:
            self.frame_timer += dt
            if self.frame_timer >= self.animation_speed:
                self.frame_timer = 0.0
                self.current_frame = 3 + (self.current_frame - 3 + 1) % 3

    def get_hitbox(self) -> Tuple[float, float, float, float]:
        hitbox_size = self.size[0] * 0.75
        offset = (self.size[0] - hitbox_size) / 2
        return (self.pos.x + offset, self.pos.y + offset, hitbox_size, hitbox_size)

    def draw(self, canvas):
        with canvas:
            if self.fire_textures and len(self.fire_textures) > 0:
                texture = self.fire_textures[self.current_frame]
                Color(1, 1, 1, 1)
                PushMatrix()
                center_x = self.pos.x + self.size[0] / 2
                center_y = self.pos.y + self.size[1] / 2
                Rotate(angle=self.angle, origin=(center_x, center_y))
                Rectangle(texture=texture, pos=self.pos, size=self.size)
                PopMatrix()
            else:
                Color(*self.color)
                Rectangle(pos=self.pos, size=self.size)
