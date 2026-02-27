from typing import Dict, List, Optional, Tuple

from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.graphics import Color, PopMatrix, PushMatrix, Rectangle, Scale
from kivy.vector import Vector

from entity_base import Entity


class PlayerEntity(Entity):
    """Sprite-based player that supports idle/walk/run and a specific shot sequence."""

    def __init__(self, pos: Vector, asset_path: str = "game_picture/player/Soldier_1"):
        self.asset_path = asset_path
        self.animations: Dict[str, List] = {}
        self.anim_bboxes: Dict[str, List[Tuple[float, float, float, float]]] = {}

        self._load_animation("idle", "Idle", 7)
        self._load_animation("walk", "Walk", 7)
        self._load_animation("run", "Run", 8)
        self._load_animation("shot", "Shot_", 5)
        self._load_animation("hurt", "Hurt", 3)
        self._load_animation("dead", "Dead", 4)

        base_texture = self.animations["idle"][0]
        target_height = Window.height / 3
        scale = target_height / base_texture.height
        width = base_texture.width * scale
        height = base_texture.height * scale

        super().__init__(pos=pos, size=(width, height), color=(1, 1, 1))

        # Health system
        self.max_hp = 100
        self.hp = self.max_hp

        self.current_anim = "idle"
        self.current_frame = 0
        self.frame_timer = 0.0
        self.animation_speed = 0.1
        self.facing = 1
        self.speed = 240
        self.run_speed = 420
        self.is_shooting = False
        self.is_dead = False
        self.is_hurt = False
        self.hurt_timer = 0.0
        self.hurt_duration = 0.3  # seconds of hurt flash/anim
        self.death_anim_done = False
        self.hit_flash_timer = 0.0  # red flash on hit

    def _load_animation(self, name: str, prefix: str, count: int):
        frames: List = []
        bboxes: List[Tuple[float, float, float, float]] = []
        for idx in range(1, count + 1):
            path = f"{self.asset_path}/{prefix}{idx}.png"
            try:
                texture = CoreImage(path).texture
                frames.append(texture)
                bboxes.append(self._compute_bbox(texture))
            except Exception as exc:
                print(f"Failed to load {path}: {exc}")
        if frames:
            self.animations[name] = frames
            self.anim_bboxes[name] = bboxes

    def _compute_bbox(self, texture) -> Tuple[float, float, float, float]:
        w, h = texture.size
        pixels = texture.pixels
        min_x, min_y = w, h
        max_x, max_y = -1, -1
        for y in range(h):
            row_start = y * w * 4
            for x in range(w):
                alpha = pixels[row_start + x * 4 + 3]
                if alpha > 10:
                    if x < min_x:
                        min_x = x
                    if y < min_y:
                        min_y = y
                    if x > max_x:
                        max_x = x
                    if y > max_y:
                        max_y = y
        if max_x == -1:
            return (0.0, 0.0, 1.0, 1.0)
        return (min_x / w, min_y / h, (max_x - min_x + 1) / w, (max_y - min_y + 1) / h)

    def update(self, dt: float, pressed_keys: set, bounds: Tuple[float, float]):
        self.update_statuses(dt)

        # Dead — play death anim once then freeze on last frame
        if self.is_dead:
            if self.current_anim != "dead":
                self.current_anim = "dead"
                self.current_frame = 0
                self.frame_timer = 0.0
            frames = self.animations.get("dead", [])
            if frames and not self.death_anim_done:
                self.frame_timer += dt
                if self.frame_timer >= self.animation_speed:
                    self.frame_timer = 0.0
                    if self.current_frame < len(frames) - 1:
                        self.current_frame += 1
                    else:
                        self.death_anim_done = True
            return frames[self.current_frame] if frames else None

        # Hit flash countdown
        if self.hit_flash_timer > 0:
            self.hit_flash_timer -= dt

        # Hurt timer countdown
        if self.is_hurt:
            self.hurt_timer -= dt
            if self.hurt_timer <= 0:
                self.is_hurt = False

        move_vec = Vector(0, 0)
        if "w" in pressed_keys:
            move_vec += Vector(0, 1)
        if "s" in pressed_keys:
            move_vec += Vector(0, -1)
        if "a" in pressed_keys:
            move_vec += Vector(-1, 0)
        if "d" in pressed_keys:
            move_vec += Vector(1, 0)

        prev_anim = self.current_anim

        if self.is_shooting:
            self.current_anim = "shot"
        elif self.is_hurt:
            self.current_anim = "hurt"
        elif move_vec.length() > 0:
            self.facing = 1 if move_vec.x >= 0 else -1
            self.current_anim = "run" if "shift" in pressed_keys else "walk"
        else:
            self.current_anim = "idle"

        if self.current_anim != prev_anim:
            self.current_frame = 0
            self.frame_timer = 0.0

        speed = self.speed if self.is_shooting else (self.run_speed if "shift" in pressed_keys else self.speed)
        speed *= self.get_status_multiplier("move_speed", default=1.0)

        if move_vec.length() > 0:
            self.pos = self.pos + move_vec.normalize() * (speed * dt)

        max_x = max(0, bounds[0] - self.size[0])
        height = bounds[1]
        block_unit = height / 10.0
        min_y, max_y_allowed = block_unit, height - (3 * block_unit) - self.size[1]
        self.pos.x = max(0, min(self.pos.x, max_x))
        self.pos.y = max(min_y, min(self.pos.y, max_y_allowed))

        frames = self.animations.get(self.current_anim, [])
        if not frames:
            return None

        self.frame_timer += dt
        if self.frame_timer >= self.animation_speed:
            self.frame_timer = 0.0
            if self.current_anim == "shot" and self.is_shooting and len(frames) >= 5:
                if self.current_frame < 2 or self.current_frame > 4:
                    self.current_frame = 2
                else:
                    self.current_frame += 1
                    if self.current_frame > 4:
                        self.current_frame = 2
            else:
                self.current_frame = (self.current_frame + 1) % len(frames)

        return frames[self.current_frame]

    def take_damage(self, amount: float):
        """Apply damage to player. Returns True if player died."""
        self.hp -= amount
        self.is_hurt = True
        self.hurt_timer = self.hurt_duration
        self.hit_flash_timer = 0.15  # brief red flash
        if self.hp <= 0:
            self.hp = 0
            self.is_dead = True
            self.is_shooting = False
            return True
        return False

    def start_shooting(self):
        if self.is_dead:
            return
        if "shot" in self.animations:
            self.is_shooting = True
            self.current_anim = "shot"
            self.current_frame = 2
            self.frame_timer = 0.0

    def stop_shooting(self):
        if self.is_shooting:
            self.is_shooting = False
            self.current_anim = "idle"
            self.current_frame = 0

    def get_hitbox(self) -> Tuple[float, float, float, float]:
        bboxes = self.anim_bboxes.get(self.current_anim)
        if not bboxes:
            return (self.pos.x, self.pos.y, self.size[0], self.size[1])
        bbox = bboxes[self.current_frame % len(bboxes)]
        bx, by, bw, bh = bbox
        offset_x = bx * self.size[0] if self.facing == 1 else (1 - (bx + bw)) * self.size[0]
        offset_y = (1 - (by + bh)) * self.size[1]

        shrink_scale = 0.82
        raw_w = bw * self.size[0]
        raw_h = bh * self.size[1]
        hit_w = raw_w * shrink_scale
        hit_h = raw_h * shrink_scale
        inset_x = (raw_w - hit_w) / 2
        inset_y = (raw_h - hit_h) / 2

        return (
            self.pos.x + offset_x + inset_x,
            self.pos.y + offset_y + inset_y,
            hit_w,
            hit_h,
        )

    def get_muzzle_position(self, shot_direction: Optional[Vector] = None) -> Vector:
        muzzle_x_ratio = 0.79 if self.facing == 1 else 0.21
        muzzle_y_ratio = 0.45

        muzzle = Vector(
            self.pos.x + self.size[0] * muzzle_x_ratio,
            self.pos.y + self.size[1] * muzzle_y_ratio,
        )

        if shot_direction is not None and shot_direction.length() > 0:
            muzzle = muzzle + shot_direction.normalize() * (self.size[0] * 0.06)

        return muzzle

    def draw(self, canvas):
        texture = self.animations.get(self.current_anim, [None])[self.current_frame]
        if texture is None:
            return
        x, y = self.pos.x, self.pos.y
        with canvas:
            if self.hit_flash_timer > 0:
                Color(1, 0.3, 0.3, 1)  # red tint on hit
            else:
                Color(1, 1, 1, 1)
            if self.facing == -1:
                PushMatrix()
                origin = (x + self.size[0] / 2, y + self.size[1] / 2)
                Scale(x=-1, y=1, origin=origin)
                Rectangle(texture=texture, pos=(x, y), size=self.size)
                PopMatrix()
            else:
                Rectangle(texture=texture, pos=(x, y), size=self.size)
