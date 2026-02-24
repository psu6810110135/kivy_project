from dataclasses import dataclass
from typing import Dict, List, Tuple
import random

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

class BulletEntity(Entity):
    """Simple projectile that moves in the direction the player was facing."""
    def __init__(self, pos: Vector, direction: int):
        super().__init__(pos=pos, size=(20, 5), color=(1, 1, 0))
        self.direction = direction
        self.speed = 800

    def update(self, dt: float):
        self.move(Vector(self.direction * self.speed * dt, 0))

    def get_hitbox(self) -> Tuple[float, float, float, float]:
        """Returns the bullet's hitbox as (x, y, width, height)"""
        return (self.pos.x, self.pos.y, self.size[0], self.size[1])

    def draw(self, canvas):
        with canvas:
            Color(*self.color)
            Rectangle(pos=self.pos, size=self.size)

class EnemyProjectileEntity(Entity):
    """Projectile fired by enemies (e.g., Kitsune's fire)."""
    def __init__(self, pos, target_pos, fire_textures: List = None):
        # Ensure pos is a Vector
        if not isinstance(pos, Vector):
            pos = Vector(pos[0], pos[1]) if hasattr(pos, '__len__') else Vector(pos.x, pos.y)
        if not isinstance(target_pos, Vector):
            target_pos = Vector(target_pos[0], target_pos[1]) if hasattr(target_pos, '__len__') else Vector(target_pos.x, target_pos.y)

        super().__init__(pos=pos, size=(160, 160), color=(1, 0.5, 0))

        direction = target_pos - pos
        self.velocity = direction.normalize() * 450 if direction.length() > 0 else Vector(0, 0)
        
        # Calculate rotation angle for proper orientation
        import math
        self.angle = math.degrees(math.atan2(self.velocity.y, self.velocity.x))

        self.fire_textures = fire_textures or []
        self.current_frame = 3  # Start at frame 4 (0-indexed: 3)
        self.frame_timer = 0.0
        self.animation_speed = 0.05
        self.hit = False  # Track if projectile has hit

    def update(self, dt: float):
        # Ensure velocity * dt returns a Vector
        delta = Vector(self.velocity.x * dt, self.velocity.y * dt)
        self.pos = self.pos + delta

        if self.fire_textures:
            self.frame_timer += dt
            if self.frame_timer >= self.animation_speed:
                self.frame_timer = 0.0
                # Loop frames 4-6 (indices 3-5)
                self.current_frame = 3 + (self.current_frame - 3 + 1) % 3

    def get_hitbox(self) -> Tuple[float, float, float, float]:
        # Hitbox centered on the fireball (95% of sprite size to fit visual)
        hitbox_size = self.size[0] * 0.95
        offset = (self.size[0] - hitbox_size) / 2
        return (self.pos.x + offset, self.pos.y + offset, hitbox_size, hitbox_size)

    def draw(self, canvas):
        with canvas:
            if self.fire_textures and len(self.fire_textures) > 0:
                texture = self.fire_textures[self.current_frame]
                Color(1, 1, 1, 1)
                
                # Rotate fireball based on direction
                PushMatrix()
                from kivy.graphics import Rotate
                center_x = self.pos.x + self.size[0] / 2
                center_y = self.pos.y + self.size[1] / 2
                Rotate(angle=self.angle, origin=(center_x, center_y))
                Rectangle(texture=texture, pos=self.pos, size=self.size)
                PopMatrix()
            else:
                Color(*self.color)
                Rectangle(pos=self.pos, size=self.size)

class PlayerEntity(Entity):
    """Sprite-based player that supports idle/walk/run and a specific shot sequence."""

    def __init__(self, pos: Vector, asset_path: str = "game_picture/player/Soldier_1"):
        self.asset_path = asset_path
        self.animations: Dict[str, List] = {}
        self.anim_bboxes: Dict[str, List[Tuple[float, float, float, float]]] = {}
        
        # Load standard animations
        self._load_animation("idle", "Idle", 7)
        self._load_animation("walk", "Walk", 7)
        self._load_animation("run", "Run", 8)
        self._load_animation("shot", "Shot_", 5)

        base_texture = self.animations["idle"][0]
        target_height = Window.height / 3
        scale = target_height / base_texture.height
        width = base_texture.width * scale
        height = base_texture.height * scale

        super().__init__(pos=pos, size=(width, height), color=(1, 1, 1))

        self.current_anim = "idle"
        self.current_frame = 0
        self.frame_timer = 0.0
        self.animation_speed = 0.1 
        self.facing = 1
        self.speed = 240  # units per second
        self.run_speed = 420  # faster when holding shift
        self.is_shooting = False

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
                    if x < min_x: min_x = x
                    if y < min_y: min_y = y
                    if x > max_x: max_x = x
                    if y > max_y: max_y = y
        if max_x == -1: return (0.0, 0.0, 1.0, 1.0)
        return (min_x / w, min_y / h, (max_x - min_x + 1) / w, (max_y - min_y + 1) / h)

    def update(self, dt: float, pressed_keys: set, bounds: Tuple[float, float]):
        move_vec = Vector(0, 0)
        if "w" in pressed_keys: move_vec += Vector(0, 1)
        if "s" in pressed_keys: move_vec += Vector(0, -1)
        if "a" in pressed_keys: move_vec += Vector(-1, 0)
        if "d" in pressed_keys: move_vec += Vector(1, 0)

        prev_anim = self.current_anim
        
        # Logic to lock animation during shooting sequence
        if self.is_shooting:
            self.current_anim = "shot"
        elif move_vec.length() > 0:
            self.facing = 1 if move_vec.x >= 0 else -1
            self.current_anim = "run" if "shift" in pressed_keys else "walk"
        else:
            self.current_anim = "idle"

        if self.current_anim != prev_anim:
            self.current_frame = 0
            self.frame_timer = 0.0

        speed = self.speed if self.is_shooting else (self.run_speed if "shift" in pressed_keys else self.speed)
        if move_vec.length() > 0:
            self.pos = self.pos + move_vec.normalize() * (speed * dt)
        
        # Boundary Clamping
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
                # Loop frames 3-5 (index 2-4)
                if self.current_frame < 2 or self.current_frame > 4:
                    self.current_frame = 2
                else:
                    self.current_frame += 1
                    if self.current_frame > 4:
                        self.current_frame = 2
            else:
                self.current_frame = (self.current_frame + 1) % len(frames)

        return frames[self.current_frame]

    def start_shooting(self):
        # Loop frames 3-5 (index 2-4) of Shot animation
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
        if not bboxes: return (self.pos.x, self.pos.y, self.size[0], self.size[1])
        bbox = bboxes[self.current_frame % len(bboxes)]
        bx, by, bw, bh = bbox
        offset_x = bx * self.size[0] if self.facing == 1 else (1 - (bx + bw)) * self.size[0]
        offset_y = (1 - (by + bh)) * self.size[1]
        return (self.pos.x + offset_x, self.pos.y + offset_y, bw * self.size[0], bh * self.size[1])

    def draw(self, canvas):
        texture = self.animations.get(self.current_anim, [None])[self.current_frame]
        if texture is None: return
        x, y = self.pos.x, self.pos.y
        with canvas:
            Color(1, 1, 1, 1)
            if self.facing == -1:
                PushMatrix()
                origin = (x + self.size[0] / 2, y + self.size[1] / 2)
                Scale(x=-1, y=1, origin=origin)
                Rectangle(texture=texture, pos=(x, y), size=self.size)
                PopMatrix()
            else:
                Rectangle(texture=texture, pos=(x, y), size=self.size)

class EnemyEntity(Entity):
    """Sprite-based enemy with idle/walk/attack/hurt/dead animations."""

    # Class-level cache for textures and bounding boxes (shared across all instances)
    _texture_cache: Dict[str, Dict[str, List]] = {}  # asset_path -> {anim_name: [textures]}
    _bbox_cache: Dict[str, Dict[str, List[Tuple[float, float, float, float]]]] = {}  # asset_path -> {anim_name: [bboxes]}
    _base_size_cache: Dict[str, Tuple[float, float]] = {}  # asset_path -> (width, height)

    SKINS = [
        "game_picture/enemy/Zombie_1",
        "game_picture/enemy/Zombie_2",
        "game_picture/enemy/Zombie_3",
        "game_picture/enemy/Zombie_4",
    ]

    @classmethod
    def _load_animation_cached(cls, asset_path: str, name: str, prefix: str, count: int):
        """Load animation textures once per asset_path and cache them."""
        if asset_path not in cls._texture_cache:
            cls._texture_cache[asset_path] = {}
            cls._bbox_cache[asset_path] = {}

        if name in cls._texture_cache[asset_path]:
            return  # Already cached

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
            # Cache base size from first idle frame
            if name == "idle" and asset_path not in cls._base_size_cache:
                cls._base_size_cache[asset_path] = (frames[0].width, frames[0].height)

    @staticmethod
    def _compute_bbox_static(texture) -> Tuple[float, float, float, float]:
        """Static version of bbox computation for caching."""
        w, h = texture.size
        pixels = texture.pixels
        min_x, min_y = w, h
        max_x, max_y = -1, -1
        for y in range(h):
            row_start = y * w * 4
            for x in range(w):
                alpha = pixels[row_start + x * 4 + 3]
                if alpha > 10:
                    if x < min_x: min_x = x
                    if y < min_y: min_y = y
                    if x > max_x: max_x = x
                    if y > max_y: max_y = y
        if max_x == -1: return (0.0, 0.0, 1.0, 1.0)
        return (min_x / w, min_y / h, (max_x - min_x + 1) / w, (max_y - min_y + 1) / h)

    @classmethod
    def preload_all_skins(cls):
        """Preload all enemy skins at startup to avoid runtime lag."""
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

        # Load animations (uses cache if already loaded)
        self._load_animation_cached(self.asset_path, "idle", "Idle", 6)
        self._load_animation_cached(self.asset_path, "walk", "Walk", 10)
        self._load_animation_cached(self.asset_path, "attack", "Attack", 5)
        self._load_animation_cached(self.asset_path, "hurt", "Hurt", 4)
        self._load_animation_cached(self.asset_path, "dead", "Dead", 5)

        # Reference cached textures and bboxes
        self.animations = self._texture_cache[self.asset_path]
        self.anim_bboxes = self._bbox_cache[self.asset_path]

        base_size = self._base_size_cache.get(self.asset_path, (100, 100))

        # Size relative to player if provided, otherwise fallback to window-based sizing
        if player_size:
            target_height = player_size[1] * scale_to_player
        else:
            target_height = Window.height / 3

        scale = target_height / base_size[1]
        width = base_size[0] * scale
        height = base_size[1] * scale

        super().__init__(pos=pos, size=(width, height), color=(1, 1, 1))

        self.current_anim = "walk"  # Start with walk animation
        self.current_frame = 0
        self.frame_timer = 0.0
        self.animation_speed = 0.1
        self.facing = -1  # Face left (toward player) by default
        self.speed = 120  # Movement speed

        # Path to player
        self.target_pos: Vector = pos  # Will be updated to player position

    def update(self, dt: float, player_pos: Vector, bounds: Tuple[float, float]):
        """Move toward player and advance animation frame."""
        # Update target to player position
        self.target_pos = player_pos

        # Calculate direction to player from enemy center
        enemy_center = self.pos + Vector(self.size[0] / 2, self.size[1] / 2)
        direction = self.target_pos - enemy_center
        distance = direction.length()

        # Move toward player if not too close
        if distance > 60:  # Get closer before stopping (like special enemies)
            move_vec = direction.normalize() * (self.speed * dt)
            self.pos = self.pos + move_vec

            # Update facing direction based on movement
            if direction.x < 0:
                self.facing = -1
            else:
                self.facing = 1

        # Boundary clamping
        self.pos.x = max(0, min(self.pos.x, bounds[0] - self.size[0]))
        self.pos.y = max(0, min(self.pos.y, bounds[1] - self.size[1]))

        # Advance animation frame
        frames = self.animations.get(self.current_anim, [])
        if not frames:
            return

        self.frame_timer += dt
        if self.frame_timer >= self.animation_speed:
            self.frame_timer = 0.0
            self.current_frame = (self.current_frame + 1) % len(frames)

    def get_path_points(self) -> Tuple[float, float, float, float]:
        """Return start and end points for path visualization: (x1, y1, x2, y2)"""
        center_x = self.pos.x + self.size[0] / 2
        center_y = self.pos.y + self.size[1] / 2
        target_x = self.target_pos.x
        target_y = self.target_pos.y
        return (center_x, center_y, target_x, target_y)

    def get_hitbox(self) -> Tuple[float, float, float, float]:
        bboxes = self.anim_bboxes.get(self.current_anim)
        if not bboxes: return (self.pos.x, self.pos.y, self.size[0], self.size[1])
        bbox = bboxes[self.current_frame % len(bboxes)]
        bx, by, bw, bh = bbox
        offset_x = bx * self.size[0] if self.facing == 1 else (1 - (bx + bw)) * self.size[0]
        offset_y = (1 - (by + bh)) * self.size[1]
        return (self.pos.x + offset_x, self.pos.y + offset_y, bw * self.size[0], bh * self.size[1])

    def get_attack_hitbox(self) -> Tuple[float, float, float, float]:
        """Returns the attack hitbox (hand area) for collision detection."""
        if self.current_anim != "attack":
            return None
        
        # Hand hitbox at front of sprite (normalized coordinates)
        hand_width = 0.3
        hand_height = 0.3
        
        if self.facing == 1:  # Facing right
            hand_x = self.pos.x + self.size[0] * 0.7
        else:  # Facing left
            hand_x = self.pos.x
        
        hand_y = self.pos.y + self.size[1] * 0.4
        return (hand_x, hand_y, self.size[0] * hand_width, self.size[1] * hand_height)

    def draw(self, canvas):
        texture = self.animations.get(self.current_anim, [None])[self.current_frame]
        if texture is None: return
        x, y = self.pos.x, self.pos.y
        with canvas:
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

    # Separate class-level caches to avoid conflict with basic enemies
    _texture_cache: Dict[str, Dict[str, List]] = {}
    _bbox_cache: Dict[str, Dict[str, List[Tuple[float, float, float, float]]]] = {}
    _base_size_cache: Dict[str, Tuple[float, float]] = {}

    SKINS = [
        "game_picture/special_enemy/Gorgon",
        "game_picture/special_enemy/Kitsune",
        "game_picture/special_enemy/Red_Werewolf",
    ]

    # Animation frame counts per skin type
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
        """Load animation textures once per asset_path and cache them."""
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
        """Static version of bbox computation for caching."""
        w, h = texture.size
        pixels = texture.pixels
        min_x, min_y = w, h
        max_x, max_y = -1, -1
        for y in range(h):
            row_start = y * w * 4
            for x in range(w):
                alpha = pixels[row_start + x * 4 + 3]
                if alpha > 10:
                    if x < min_x: min_x = x
                    if y < min_y: min_y = y
                    if x > max_x: max_x = x
                    if y > max_y: max_y = y
        if max_x == -1: return (0.0, 0.0, 1.0, 1.0)
        return (min_x / w, min_y / h, (max_x - min_x + 1) / w, (max_y - min_y + 1) / h)

    @classmethod
    def preload_all_skins(cls):
        """Preload all special enemy skins at startup to avoid runtime lag."""
        for skin in cls.SKINS:
            frames = cls.ANIMATION_FRAMES[skin]
            cls._load_animation_cached(skin, "idle", "Idle", frames["idle"])
            cls._load_animation_cached(skin, "walk", "Walk", frames["walk"])
            cls._load_animation_cached(skin, "run", "Run", frames["run"])
            cls._load_animation_cached(skin, "attack", "Attack_", frames["attack"])
            cls._load_animation_cached(skin, "hurt", "Hurt", frames["hurt"])
            cls._load_animation_cached(skin, "dead", "Dead", frames["dead"])

    def __init__(self, pos: Vector, player_size: Tuple[float, float] = None, asset_path: str = None):
        if asset_path is None:
            self.asset_path = random.choice(self.SKINS)
        else:
            self.asset_path = asset_path

        # Load animations (uses cache if already loaded)
        frames = self.ANIMATION_FRAMES[self.asset_path]
        self._load_animation_cached(self.asset_path, "idle", "Idle", frames["idle"])
        self._load_animation_cached(self.asset_path, "walk", "Walk", frames["walk"])
        self._load_animation_cached(self.asset_path, "run", "Run", frames["run"])
        self._load_animation_cached(self.asset_path, "attack", "Attack_", frames["attack"])
        self._load_animation_cached(self.asset_path, "hurt", "Hurt", frames["hurt"])
        self._load_animation_cached(self.asset_path, "dead", "Dead", frames["dead"])

        # Reference cached textures and bboxes
        self.animations = self._texture_cache[self.asset_path]
        self.anim_bboxes = self._bbox_cache[self.asset_path]

        base_size = self._base_size_cache.get(self.asset_path, (100, 100))

        # Size: 1.2x player size (enhanced)
        if player_size:
            target_height = player_size[1] * 1.2
        else:
            target_height = Window.height / 3

        scale = target_height / base_size[1]
        width = base_size[0] * scale
        height = base_size[1] * scale

        super().__init__(pos=pos, size=(width, height), color=(1, 1, 1))

        self.current_anim = "walk"
        self.current_frame = 0
        self.frame_timer = 0.0
        self.animation_speed = 0.1
        self.facing = -1
        self.speed = 180  # 1.5x basic enemy speed (120 * 1.5 = 180)

        self.target_pos: Vector = pos
        
        # Kitsune AI state machine
        self.ai_state = "approach"  # States: approach, ranged_attack, escape
        self.escape_distance = 250  # Start escaping when player within 250px
        self.attack_range = 550  # Shoot fire when player within 550px
        self.fire_cooldown = 1.5  # Seconds between fire shots (faster for more action)
        self.fire_timer = 0.0
        self.fire_textures = []  # Will be loaded for Kitsune
        
        # Load fire animation for Kitsune
        if "Kitsune" in self.asset_path:
            self._load_fire_animation()

    def _load_fire_animation(self):
        """Load Kitsune's fire projectile animation frames."""
        for idx in range(1, 15):  # Fire_1.png to Fire_14.png
            path = f"{self.asset_path}/Fire_{idx}.png"
            try:
                texture = CoreImage(path).texture
                self.fire_textures.append(texture)
            except Exception as exc:
                print(f"Failed to load fire texture {path}: {exc}")

    def update(self, dt: float, player_pos: Vector, bounds: Tuple[float, float]):
        """Move toward player and advance animation frame. Kitsune has special AI behavior."""
        self.target_pos = player_pos

        enemy_center = self.pos + Vector(self.size[0] / 2, self.size[1] / 2)
        direction = self.target_pos - enemy_center
        distance = direction.length()

        # Kitsune AI state machine
        if "Kitsune" in self.asset_path:
            return self._update_kitsune_ai(dt, enemy_center, direction, distance, bounds)
        
        # Normal enemy behavior (Gorgon, Red_Werewolf)
        if distance > 10:
            move_vec = direction.normalize() * (self.speed * dt)
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
        """Kitsune AI: Ranged attack from distance, escape when player gets too close."""
        projectile_to_spawn = None
        
        # Update fire cooldown
        self.fire_timer += dt
        
        # State machine
        if distance < self.escape_distance:
            # ESCAPE: Run away from player
            self.ai_state = "escape"
            if distance > 0:
                escape_direction = (enemy_center - self.target_pos).normalize()
                self.pos = self.pos + escape_direction * (self.speed * dt)
                
                # Face away from player while escaping
                if escape_direction.x < 0:
                    self.facing = -1
                else:
                    self.facing = 1
        
        elif distance < self.attack_range:
            # RANGED_ATTACK: Shoot fire at player
            self.ai_state = "ranged_attack"
            
            # Face player
            if direction.x < 0:
                self.facing = -1
            else:
                self.facing = 1
            
            # Shoot fire projectile
            if self.fire_timer >= self.fire_cooldown:
                self.fire_timer = 0.0
                # Spawn fireball centered on Kitsune (fireball is 160x160, so offset by 80)
                fire_spawn_pos = Vector(enemy_center.x - 80, enemy_center.y - 80)
                projectile_to_spawn = EnemyProjectileEntity(
                    pos=fire_spawn_pos,
                    target_pos=self.target_pos,
                    fire_textures=self.fire_textures
                )
        
        else:
            # APPROACH: Move toward player to get into attack range
            self.ai_state = "approach"
            if distance > 60:  # Get closer before stopping
                move_vec = direction.normalize() * (self.speed * dt)
                self.pos = self.pos + move_vec

                if direction.x < 0:
                    self.facing = -1
                else:
                    self.facing = 1
        
        # Boundary clamping
        self.pos.x = max(0, min(self.pos.x, bounds[0] - self.size[0]))
        self.pos.y = max(0, min(self.pos.y, bounds[1] - self.size[1]))
        
        # Advance animation frame
        frames = self.animations.get(self.current_anim, [])
        if frames:
            self.frame_timer += dt
            if self.frame_timer >= self.animation_speed:
                self.frame_timer = 0.0
                self.current_frame = (self.current_frame + 1) % len(frames)
        
        return projectile_to_spawn

    def get_path_points(self) -> Tuple[float, float, float, float]:
        """Return start and end points for path visualization: (x1, y1, x2, y2)"""
        center_x = self.pos.x + self.size[0] / 2
        center_y = self.pos.y + self.size[1] / 2
        target_x = self.target_pos.x
        target_y = self.target_pos.y
        return (center_x, center_y, target_x, target_y)

    def get_hitbox(self) -> Tuple[float, float, float, float]:
        bboxes = self.anim_bboxes.get(self.current_anim)
        if not bboxes: return (self.pos.x, self.pos.y, self.size[0], self.size[1])
        bbox = bboxes[self.current_frame % len(bboxes)]
        bx, by, bw, bh = bbox
        offset_x = bx * self.size[0] if self.facing == 1 else (1 - (bx + bw)) * self.size[0]
        offset_y = (1 - (by + bh)) * self.size[1]
        return (self.pos.x + offset_x, self.pos.y + offset_y, bw * self.size[0], bh * self.size[1])

    def get_attack_hitbox(self) -> Tuple[float, float, float, float]:
        """Returns attack hitbox based on enemy type: Gorgon (tail), Red_Werewolf (hand), Kitsune (None - ranged)."""
        if self.current_anim != "attack":
            return None
        
        # Kitsune is ranged - no melee attack hitbox
        if "Kitsune" in self.asset_path:
            return None
        
        # Gorgon attacks with tail (back of sprite)
        if "Gorgon" in self.asset_path:
            tail_width = 0.3
            tail_height = 0.35
            
            if self.facing == 1:  # Facing right, tail on left
                tail_x = self.pos.x
            else:  # Facing left, tail on right
                tail_x = self.pos.x + self.size[0] * 0.7
            
            tail_y = self.pos.y + self.size[1] * 0.1
            return (tail_x, tail_y, self.size[0] * tail_width, self.size[1] * tail_height)

        # Red_Werewolf attacks with hand (front of sprite)
        if "Red_Werewolf" in self.asset_path:
            hand_width = 0.3
            hand_height = 0.3

            if self.facing == 1:  # Facing right
                hand_x = self.pos.x + self.size[0] * 0.7
            else:  # Facing left
                hand_x = self.pos.x

            hand_y = self.pos.y + self.size[1] * 0.4
            return (hand_x, hand_y, self.size[0] * hand_width, self.size[1] * hand_height)
        
        return None

    def draw(self, canvas):
        texture = self.animations.get(self.current_anim, [None])[self.current_frame]
        if texture is None: return
        x, y = self.pos.x, self.pos.y
        with canvas:
            Color(1, 1, 1, 1)
            if self.facing == -1:
                PushMatrix()
                origin = (x + self.size[0] / 2, y + self.size[1] / 2)
                Scale(x=-1, y=1, origin=origin)
                Rectangle(texture=texture, pos=(x, y), size=self.size)
                PopMatrix()
            else:
                Rectangle(texture=texture, pos=(x, y), size=self.size)
