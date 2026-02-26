from typing import Dict, List, Tuple
import random

from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.graphics import Color, PopMatrix, PushMatrix, Rectangle, Scale
from kivy.vector import Vector

from entity_base import Entity
from projectile_entities import EnemyProjectileEntity


class EnemyEntity(Entity):
    """Sprite-based enemy with idle/walk/attack/hurt/dead animations."""

    _texture_cache: Dict[str, Dict[str, List]] = {}
    _bbox_cache: Dict[str, Dict[str, List[Tuple[float, float, float, float]]]] = {}
    _base_size_cache: Dict[str, Tuple[float, float]] = {}

    SKINS = [
        "game_picture/enemy/Zombie_1",
        "game_picture/enemy/Zombie_2",
        "game_picture/enemy/Zombie_3",
        "game_picture/enemy/Zombie_4",
    ]

    @classmethod
    def _load_animation_cached(cls, asset_path: str, name: str, prefix: str, count: int):
        if asset_path not in cls._texture_cache:
            cls._texture_cache[asset_path] = {}
            cls._bbox_cache[asset_path] = {}

        if name in cls._texture_cache[asset_path]:
            return

        frames: List = []
        bboxes: List[Tuple[float, float, float, float]] = []
        for idx in range(1, count + 1):
            path = f"{asset_path}/{prefix}{idx}.png"
            try:
                texture = CoreImage(path).texture
                frames.append(texture)
                bboxes.append(cls._compute_bbox_static(texture))
            except Exception as exc:
                print(f"Failed to load {path}: {exc}")

        if frames:
            cls._texture_cache[asset_path][name] = frames
            cls._bbox_cache[asset_path][name] = bboxes
            if name == "idle" and asset_path not in cls._base_size_cache:
                cls._base_size_cache[asset_path] = (frames[0].width, frames[0].height)

    @staticmethod
    def _compute_bbox_static(texture) -> Tuple[float, float, float, float]:
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

    @classmethod
    def preload_all_skins(cls):
        for skin in cls.SKINS:
            cls._load_animation_cached(skin, "idle", "Idle", 6)
            cls._load_animation_cached(skin, "walk", "Walk", 10)
            cls._load_animation_cached(skin, "attack", "Attack", 5)
            cls._load_animation_cached(skin, "hurt", "Hurt", 4)
            cls._load_animation_cached(skin, "dead", "Dead", 5)

    def __init__(self, pos: Vector, player_size: Tuple[float, float] = None, scale_to_player: float = 1.0, asset_path: str = None):
        if asset_path is None:
            self.asset_path = random.choice(self.SKINS)
        else:
            self.asset_path = asset_path

        self._load_animation_cached(self.asset_path, "idle", "Idle", 6)
        self._load_animation_cached(self.asset_path, "walk", "Walk", 10)
        self._load_animation_cached(self.asset_path, "attack", "Attack", 5)
        self._load_animation_cached(self.asset_path, "hurt", "Hurt", 4)
        self._load_animation_cached(self.asset_path, "dead", "Dead", 5)

        self.animations = self._texture_cache[self.asset_path]
        self.anim_bboxes = self._bbox_cache[self.asset_path]

        base_size = self._base_size_cache.get(self.asset_path, (100, 100))

        if player_size:
            target_height = player_size[1] * scale_to_player
        else:
            target_height = Window.height / 3

        scale = target_height / base_size[1]
        width = base_size[0] * scale
        height = base_size[1] * scale

        super().__init__(pos=pos, size=(width, height), color=(1, 1, 1))

        # Health system
        self.max_hp = 50
        self.hp = self.max_hp

        self.current_anim = "walk"
        self.current_frame = 0
        self.frame_timer = 0.0
        self.animation_speed = 0.1
        self.facing = -1
        self.speed = 120
        self.spawn_order = 0
        self.separation_radius = min(self.size[0], self.size[1]) * 0.24

        self.target_pos: Vector = pos

    def get_render_danger_priority(self) -> int:
        priority = 1
        if self.current_anim == "attack":
            priority += 2
        return priority

    def update(self, dt: float, player_pos: Vector, bounds: Tuple[float, float]):
        self.update_statuses(dt)

        self.target_pos = player_pos
        enemy_center = self.pos + Vector(self.size[0] / 2, self.size[1] / 2)
        direction = self.target_pos - enemy_center
        distance = direction.length()

        move_speed = self.speed * self.get_status_multiplier("move_speed", default=1.0)

        if distance > 60:
            move_vec = direction.normalize() * (move_speed * dt)
            self.pos = self.pos + move_vec

            if direction.x < 0:
                self.facing = -1
            else:
                self.facing = 1

        self.pos.x = max(0, min(self.pos.x, bounds[0] - self.size[0]))
        self.pos.y = max(0, min(self.pos.y, bounds[1] - self.size[1]))

        frames = self.animations.get(self.current_anim, [])
        if not frames:
            return

        self.frame_timer += dt
        if self.frame_timer >= self.animation_speed:
            self.frame_timer = 0.0
            self.current_frame = (self.current_frame + 1) % len(frames)

    def get_path_points(self) -> Tuple[float, float, float, float]:
        center_x = self.pos.x + self.size[0] / 2
        center_y = self.pos.y + self.size[1] / 2
        target_x = self.target_pos.x
        target_y = self.target_pos.y
        return (center_x, center_y, target_x, target_y)

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

    def get_attack_hitbox(self) -> Tuple[float, float, float, float]:
        if self.current_anim != "attack":
            return None

        hx, hy, hw, hh = self.get_hitbox()
        hand_w = hw * 0.22
        hand_h = hh * 0.22

        if self.facing == 1:
            hand_x = hx + hw - (hand_w * 0.35)
        else:
            hand_x = hx - (hand_w * 0.65)

        hand_y = hy + hh * 0.42
        return (hand_x, hand_y, hand_w, hand_h)

    def draw(self, canvas):
        texture = self.animations.get(self.current_anim, [None])[self.current_frame]
        if texture is None:
            return
        x, y = self.pos.x, self.pos.y
        # Health bar based on hitbox
        hit_x, hit_y, hit_w, hit_h = self.get_hitbox()
        bar_width = hit_w
        bar_height = 6
        bar_x = hit_x
        bar_y = hit_y + hit_h + 53  # ยกขึ้นอีก 50px
        with canvas:
            # Background
            Color(0.15, 0.15, 0.15, 0.7)
            Rectangle(pos=(bar_x, bar_y), size=(bar_width, bar_height))
            # Foreground (hp) - red
            hp_ratio = max(0.0, min(1.0, self.hp / self.max_hp))
            Color(1, 0.15, 0.15, 1)
            Rectangle(pos=(bar_x, bar_y), size=(bar_width * hp_ratio, bar_height))

            # Draw enemy sprite
            Color(1, 1, 1, 1)
            if self.facing == -1:
                PushMatrix()
                origin = (x + self.size[0] / 2, y + self.size[1] / 2)
                Scale(x=-1, y=1, origin=origin)
                Rectangle(texture=texture, pos=(x, y), size=self.size)
                PopMatrix()
            else:
                Rectangle(texture=texture, pos=(x, y), size=self.size)


class SpecialEnemyEntity(Entity):
    """Special enemy with enhanced stats: 1.5x speed, 1.2x size. Spawns every 3 minutes."""

    _texture_cache: Dict[str, Dict[str, List]] = {}
    _bbox_cache: Dict[str, Dict[str, List[Tuple[float, float, float, float]]]] = {}
    _base_size_cache: Dict[str, Tuple[float, float]] = {}

    SKINS = [
        "game_picture/special_enemy/Gorgon",
        "game_picture/special_enemy/Kitsune",
        "game_picture/special_enemy/Red_Werewolf",
    ]

    ANIMATION_FRAMES = {
        "game_picture/special_enemy/Gorgon": {
            "attack": 16,
            "dead": 3,
            "hurt": 3,
            "idle": 7,
            "run": 7,
            "walk": 13,
        },
        "game_picture/special_enemy/Kitsune": {
            "attack": 11,
            "dead": 10,
            "hurt": 2,
            "idle": 8,
            "run": 8,
            "walk": 8,
        },
        "game_picture/special_enemy/Red_Werewolf": {
            "attack": 7,
            "dead": 2,
            "hurt": 2,
            "idle": 8,
            "run": 9,
            "walk": 11,
        },
    }

    @classmethod
    def _load_animation_cached(cls, asset_path: str, name: str, prefix: str, count: int):
        if asset_path not in cls._texture_cache:
            cls._texture_cache[asset_path] = {}
            cls._bbox_cache[asset_path] = {}

        if name in cls._texture_cache[asset_path]:
            return

        frames: List = []
        bboxes: List[Tuple[float, float, float, float]] = []
        for idx in range(1, count + 1):
            path = f"{asset_path}/{prefix}{idx}.png"
            try:
                texture = CoreImage(path).texture
                frames.append(texture)
                bboxes.append(cls._compute_bbox_static(texture))
            except Exception as exc:
                print(f"Failed to load {path}: {exc}")

        if frames:
            cls._texture_cache[asset_path][name] = frames
            cls._bbox_cache[asset_path][name] = bboxes
            if name == "idle" and asset_path not in cls._base_size_cache:
                cls._base_size_cache[asset_path] = (frames[0].width, frames[0].height)

    @staticmethod
    def _compute_bbox_static(texture) -> Tuple[float, float, float, float]:
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

    @classmethod
    def preload_all_skins(cls):
        for skin in cls.SKINS:
            frames = cls.ANIMATION_FRAMES[skin]
            cls._load_animation_cached(skin, "idle", "Idle", frames["idle"])
            cls._load_animation_cached(skin, "walk", "Walk", frames["walk"])
            cls._load_animation_cached(skin, "run", "Run", frames["run"])
            cls._load_animation_cached(skin, "attack", "Attack_", frames["attack"])
            cls._load_animation_cached(skin, "hurt", "Hurt", frames["hurt"])
            cls._load_animation_cached(skin, "dead", "Dead", frames["dead"])

    def __init__(self, pos: Vector, player_size: Tuple[float, float] = None, asset_path: str = None, special_index: int = 1):
        if asset_path is None:
            self.asset_path = random.choice(self.SKINS)
        else:
            self.asset_path = asset_path

        frames = self.ANIMATION_FRAMES[self.asset_path]
        self._load_animation_cached(self.asset_path, "idle", "Idle", frames["idle"])
        self._load_animation_cached(self.asset_path, "walk", "Walk", frames["walk"])
        self._load_animation_cached(self.asset_path, "run", "Run", frames["run"])
        self._load_animation_cached(self.asset_path, "attack", "Attack_", frames["attack"])
        self._load_animation_cached(self.asset_path, "hurt", "Hurt", frames["hurt"])
        self._load_animation_cached(self.asset_path, "dead", "Dead", frames["dead"])

        self.animations = self._texture_cache[self.asset_path]
        self.anim_bboxes = self._bbox_cache[self.asset_path]

        base_size = self._base_size_cache.get(self.asset_path, (100, 100))

        if player_size:
            target_height = player_size[1] * 1.2
        else:
            target_height = Window.height / 3

        scale = target_height / base_size[1]
        width = base_size[0] * scale
        height = base_size[1] * scale

        super().__init__(pos=pos, size=(width, height), color=(1, 1, 1))

        if special_index == 2:
            self.max_hp = 200
        elif special_index == 3:
            self.max_hp = 300
        else:
            self.max_hp = 120
        self.hp = self.max_hp

        self.current_anim = "walk"
        self.current_frame = 0
        self.frame_timer = 0.0
        self.animation_speed = 0.1
        self.facing = -1
        self.speed = 180
        self.spawn_order = 0
        self.separation_radius = min(self.size[0], self.size[1]) * 0.28

        self.target_pos: Vector = pos

        self.ai_state = "approach"
        self.escape_distance = 250
        self.attack_range = 550
        self.fire_cooldown = 1.5
        self.fire_timer = 0.0
        self.fire_textures = []

        if "Kitsune" in self.asset_path:
            self._load_fire_animation()

    def get_render_danger_priority(self) -> int:
        priority = 2

        if "Gorgon" in self.asset_path or "Red_Werewolf" in self.asset_path:
            priority += 1
        if self.current_anim == "attack":
            priority += 2
        if "Kitsune" in self.asset_path and self.ai_state == "ranged_attack":
            priority += 1

        return priority

    def _load_fire_animation(self):
        for idx in range(1, 15):
            path = f"{self.asset_path}/Fire_{idx}.png"
            try:
                texture = CoreImage(path).texture
                self.fire_textures.append(texture)
            except Exception as exc:
                print(f"Failed to load fire texture {path}: {exc}")

    def update(self, dt: float, player_pos: Vector, bounds: Tuple[float, float]):
        self.update_statuses(dt)

        self.target_pos = player_pos

        enemy_center = self.pos + Vector(self.size[0] / 2, self.size[1] / 2)
        direction = self.target_pos - enemy_center
        distance = direction.length()

        if "Kitsune" in self.asset_path:
            return self._update_kitsune_ai(dt, enemy_center, direction, distance, bounds)

        move_speed = self.speed * self.get_status_multiplier("move_speed", default=1.0)
        if distance > 10:
            move_vec = direction.normalize() * (move_speed * dt)
            self.pos = self.pos + move_vec

            if direction.x < 0:
                self.facing = -1
            else:
                self.facing = 1

        self.pos.x = max(0, min(self.pos.x, bounds[0] - self.size[0]))
        self.pos.y = max(0, min(self.pos.y, bounds[1] - self.size[1]))

        frames = self.animations.get(self.current_anim, [])
        if not frames:
            return None

        self.frame_timer += dt
        if self.frame_timer >= self.animation_speed:
            self.frame_timer = 0.0
            self.current_frame = (self.current_frame + 1) % len(frames)

        return None

    def _update_kitsune_ai(self, dt: float, enemy_center: Vector, direction: Vector, distance: float, bounds: Tuple[float, float]):
        projectile_to_spawn = None

        self.fire_timer += dt
        move_speed = self.speed * self.get_status_multiplier("move_speed", default=1.0)

        if distance < self.escape_distance:
            self.ai_state = "escape"
            if distance > 0:
                escape_direction = (enemy_center - self.target_pos).normalize()
                self.pos = self.pos + escape_direction * (move_speed * dt)

                if escape_direction.x < 0:
                    self.facing = -1
                else:
                    self.facing = 1

        elif distance < self.attack_range:
            self.ai_state = "ranged_attack"

            if direction.x < 0:
                self.facing = -1
            else:
                self.facing = 1

            if self.fire_timer >= self.fire_cooldown:
                self.fire_timer = 0.0
                fire_spawn_pos = Vector(enemy_center.x - 80, enemy_center.y - 80)
                projectile_to_spawn = EnemyProjectileEntity(
                    pos=fire_spawn_pos,
                    target_pos=self.target_pos,
                    fire_textures=self.fire_textures,
                )

        else:
            self.ai_state = "approach"
            if distance > 60:
                move_vec = direction.normalize() * (move_speed * dt)
                self.pos = self.pos + move_vec

                if direction.x < 0:
                    self.facing = -1
                else:
                    self.facing = 1

        self.pos.x = max(0, min(self.pos.x, bounds[0] - self.size[0]))
        self.pos.y = max(0, min(self.pos.y, bounds[1] - self.size[1]))

        frames = self.animations.get(self.current_anim, [])
        if frames:
            self.frame_timer += dt
            if self.frame_timer >= self.animation_speed:
                self.frame_timer = 0.0
                self.current_frame = (self.current_frame + 1) % len(frames)

        return projectile_to_spawn

    def get_path_points(self) -> Tuple[float, float, float, float]:
        center_x = self.pos.x + self.size[0] / 2
        center_y = self.pos.y + self.size[1] / 2
        target_x = self.target_pos.x
        target_y = self.target_pos.y
        return (center_x, center_y, target_x, target_y)

    def get_hitbox(self) -> Tuple[float, float, float, float]:
        bboxes = self.anim_bboxes.get(self.current_anim)
        if not bboxes:
            return (self.pos.x, self.pos.y, self.size[0], self.size[1])
        bbox = bboxes[self.current_frame % len(bboxes)]
        bx, by, bw, bh = bbox
        offset_x = bx * self.size[0] if self.facing == 1 else (1 - (bx + bw)) * self.size[0]
        offset_y = (1 - (by + bh)) * self.size[1]

        shrink_scale = 0.8
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

    def get_attack_hitbox(self) -> Tuple[float, float, float, float]:
        if self.current_anim != "attack":
            return None

        if "Kitsune" in self.asset_path:
            return None

        hx, hy, hw, hh = self.get_hitbox()

        if "Gorgon" in self.asset_path:
            tail_w = hw * 0.22
            tail_h = hh * 0.28

            if self.facing == 1:
                tail_x = hx - (tail_w * 0.45)
            else:
                tail_x = hx + hw - (tail_w * 0.55)

            tail_y = hy + hh * 0.18
            return (tail_x, tail_y, tail_w, tail_h)

        if "Red_Werewolf" in self.asset_path:
            hand_w = hw * 0.22
            hand_h = hh * 0.22

            if self.facing == 1:
                hand_x = hx + hw - (hand_w * 0.35)
            else:
                hand_x = hx - (hand_w * 0.65)

            hand_y = hy + hh * 0.4
            return (hand_x, hand_y, hand_w, hand_h)

        return None

    def draw(self, canvas):
        texture = self.animations.get(self.current_anim, [None])[self.current_frame]
        if texture is None:
            return
        x, y = self.pos.x, self.pos.y
        # Health bar based on hitbox
        hit_x, hit_y, hit_w, hit_h = self.get_hitbox()
        bar_width = hit_w
        bar_height = 8
        bar_x = hit_x
        bar_y = hit_y + hit_h + 60  # สูงขึ้นอีก 50px
        with canvas:
            # Background
            Color(0.15, 0.15, 0.15, 0.7)
            Rectangle(pos=(bar_x, bar_y), size=(bar_width, bar_height))
            # Foreground (hp) - purple
            hp_ratio = max(0.0, min(1.0, self.hp / self.max_hp))
            Color(0.7, 0.2, 1, 1)
            Rectangle(pos=(bar_x, bar_y), size=(bar_width * hp_ratio, bar_height))

            # Draw special enemy sprite
            Color(1, 1, 1, 1)
            if self.facing == -1:
                PushMatrix()
                origin = (x + self.size[0] / 2, y + self.size[1] / 2)
                Scale(x=-1, y=1, origin=origin)
                Rectangle(texture=texture, pos=(x, y), size=self.size)
                PopMatrix()
            else:
                Rectangle(texture=texture, pos=(x, y), size=self.size)
