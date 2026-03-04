from typing import Set, List, Dict
import random
import math
from kivy.clock import Clock
from kivy.app import App
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line, PushMatrix, PopMatrix, Rotate, Ellipse
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.vector import Vector
from kivy.core.text import Label as CoreLabel

from entities import PlayerEntity, BulletEntity, EnemyEntity, SpecialEnemyEntity, EnemyProjectileEntity


class ExpOrb:
    """Collectible EXP orb rendered as a green diamond and pulled by player magnet radius."""

    def __init__(self, pos: Vector, exp_value: int):
        self.pos = Vector(pos.x, pos.y)
        self.exp_value = exp_value
        self.size = 18
        self.base_pull_speed = 240
        self.max_pull_speed = 820

    def get_hitbox(self):
        half = self.size / 2
        return (self.pos.x - half, self.pos.y - half, self.size, self.size)

    def update(self, dt: float, player_center: Vector, pull_radius: float):
        direction = player_center - self.pos
        distance = direction.length()
        if distance <= 0.001 or distance > pull_radius:
            return

        strength = 1.0 - (distance / pull_radius)
        pull_speed = self.base_pull_speed + (self.max_pull_speed - self.base_pull_speed) * strength
        self.pos += direction.normalize() * (pull_speed * dt)

    def draw(self, canvas):
        half = self.size / 2
        with canvas:
            Color(0.25, 1.0, 0.3, 0.95)
            PushMatrix()
            Rotate(angle=45, origin=(self.pos.x, self.pos.y))
            Rectangle(pos=(self.pos.x - half, self.pos.y - half), size=(self.size, self.size))
            PopMatrix()

            Color(0.85, 1.0, 0.88, 0.95)
            PushMatrix()
            Rotate(angle=45, origin=(self.pos.x, self.pos.y))
            Rectangle(pos=(self.pos.x - half * 0.35, self.pos.y - half * 0.35), size=(self.size * 0.35, self.size * 0.35))
            PopMatrix()


class BossOrb:
    """Boss reward orb: larger purple collectible that grants a powerful upgrade choice."""

    def __init__(self, pos: Vector):
        self.pos = Vector(pos.x, pos.y)
        self.size = 34
        self.base_pull_speed = 210
        self.max_pull_speed = 720

    def get_hitbox(self):
        half = self.size / 2
        return (self.pos.x - half, self.pos.y - half, self.size, self.size)

    def update(self, dt: float, player_center: Vector, pull_radius: float):
        direction = player_center - self.pos
        distance = direction.length()
        if distance <= 0.001 or distance > pull_radius:
            return

        strength = 1.0 - (distance / pull_radius)
        pull_speed = self.base_pull_speed + (self.max_pull_speed - self.base_pull_speed) * strength
        self.pos += direction.normalize() * (pull_speed * dt)

    def draw(self, canvas):
        half = self.size / 2
        with canvas:
            Color(0.58, 0.22, 0.92, 0.95)
            Ellipse(pos=(self.pos.x - half, self.pos.y - half), size=(self.size, self.size))
            Color(0.9, 0.75, 1.0, 0.95)
            inner = self.size * 0.42
            Ellipse(pos=(self.pos.x - inner / 2, self.pos.y - inner / 2), size=(inner, inner))


class HealthOrb:
    """Collectible health orb that restores a portion of max HP."""

    def __init__(self, pos: Vector, heal_ratio: float = 0.15, lifetime: float = 10.0):
        self.pos = Vector(pos.x, pos.y)
        self.heal_ratio = max(0.01, heal_ratio)
        self.lifetime = max(0.1, lifetime)
        self.age = 0.0
        self.size = 24
        self.base_pull_speed = 190
        self.max_pull_speed = 700

    def get_hitbox(self):
        half = self.size / 2
        return (self.pos.x - half, self.pos.y - half, self.size, self.size)

    def update(self, dt: float, player_center: Vector, pull_radius: float):
        self.age += dt

        direction = player_center - self.pos
        distance = direction.length()
        if distance <= 0.001 or distance > pull_radius:
            return

        strength = 1.0 - (distance / pull_radius)
        pull_speed = self.base_pull_speed + (self.max_pull_speed - self.base_pull_speed) * strength
        self.pos += direction.normalize() * (pull_speed * dt)

    def is_expired(self) -> bool:
        return self.age >= self.lifetime

    def draw(self, canvas):
        half = self.size / 2
        with canvas:
            Color(0.95, 0.22, 0.28, 0.95)
            Ellipse(pos=(self.pos.x - half, self.pos.y - half), size=(self.size, self.size))
            Color(1.0, 0.78, 0.82, 0.95)
            inner = self.size * 0.42
            Ellipse(pos=(self.pos.x - inner / 2, self.pos.y - inner / 2), size=(inner, inner))


class GrenadeEntity:
    """Thrown grenade that travels toward target then explodes after fuse timer."""

    def __init__(
        self,
        start_pos: Vector,
        target_pos: Vector,
        damage: float,
        blast_radius: float,
        textures: List = None,
        visual_scale: float = 1.0,
        min_contact_time: float = 0.20,
        fuse_min_time: float = 0.35,
        fuse_max_time: float = 1.15,
        fuse_offset: float = 0.06,
    ):
        self.base_size = 56.0
        self.size = self.base_size * max(0.5, visual_scale)
        self.hitbox_size = self.base_size * 0.56
        self.pos = Vector(start_pos.x, start_pos.y)
        self.target_pos = Vector(target_pos.x, target_pos.y)
        self.damage = damage
        self.blast_radius = blast_radius
        self.travel_speed = 780.0

        travel_distance = (self.target_pos - self.pos).length()
        travel_time = travel_distance / self.travel_speed if self.travel_speed > 0 else 0.0
        fuse_min = min(fuse_min_time, fuse_max_time)
        fuse_max = max(fuse_min_time, fuse_max_time)
        self.fuse_time = max(fuse_min, min(fuse_max, travel_time + fuse_offset))
        self.time_left = self.fuse_time
        self.age = 0.0
        self.min_contact_time = max(0.0, min_contact_time)
        self.textures = textures or []
        self.current_frame = 0
        self.frame_timer = 0.0
        self.animation_speed = 0.07

        direction = self.target_pos - self.pos
        if direction.length() <= 0.001:
            direction = Vector(1, 0)
        self.velocity = direction.normalize() * self.travel_speed
        self.angle = math.degrees(math.atan2(self.velocity.y, self.velocity.x))

    def update(self, dt: float):
        self.age += dt
        self.time_left -= dt
        if self.textures:
            self.frame_timer += dt
            if self.frame_timer >= self.animation_speed:
                self.frame_timer = 0.0
                self.current_frame = (self.current_frame + 1) % len(self.textures)
        if self.time_left > 0:
            to_target = self.target_pos - self.pos
            if to_target.length() > 8:
                self.pos += self.velocity * dt

    def get_hitbox(self):
        half = self.hitbox_size / 2
        return (self.pos.x - half, self.pos.y - half, self.hitbox_size, self.hitbox_size)

    def is_exploded(self) -> bool:
        return self.time_left <= 0

    def draw(self, canvas):
        with canvas:
            if self.textures:
                tex = self.textures[self.current_frame]
                Color(1, 1, 1, 1)
                PushMatrix()
                Rotate(angle=self.angle, origin=(self.pos.x, self.pos.y))
                Rectangle(
                    texture=tex,
                    pos=(self.pos.x - self.size / 2, self.pos.y - self.size / 2),
                    size=(self.size, self.size),
                )
                PopMatrix()
            else:
                Color(0.22, 0.28, 0.32, 0.95)
                Ellipse(pos=(self.pos.x - self.size / 2, self.pos.y - self.size / 2), size=(self.size, self.size))
                Color(0.95, 0.4, 0.2, 0.95)
                fuse_size = self.size * 0.35
                Ellipse(
                    pos=(self.pos.x - fuse_size / 2, self.pos.y + self.size * 0.22 - fuse_size / 2),
                    size=(fuse_size, fuse_size),
                )


class ExplosionEffect:
    """Visual explosion animation effect spawned when grenade detonates."""

    def __init__(self, pos: Vector, textures: List = None, size: float = 180.0, y_lift_ratio: float = 0.0):
        self.pos = Vector(pos.x, pos.y)
        self.textures = textures or []
        self.size = size
        self.y_lift_ratio = y_lift_ratio
        self.current_frame = 0
        self.frame_timer = 0.0
        self.animation_speed = 0.05
        self.done = False

    def update(self, dt: float):
        if self.done:
            return

        if not self.textures:
            self.frame_timer += dt
            if self.frame_timer >= 0.18:
                self.done = True
            return

        self.frame_timer += dt
        if self.frame_timer >= self.animation_speed:
            self.frame_timer = 0.0
            self.current_frame += 1
            if self.current_frame >= len(self.textures):
                self.done = True

    def draw(self, canvas):
        if self.done:
            return
        draw_center = Vector(self.pos.x, self.pos.y + self.size * self.y_lift_ratio)
        with canvas:
            if self.textures:
                tex = self.textures[min(self.current_frame, len(self.textures) - 1)]
                Color(1, 1, 1, 0.95)
                Rectangle(
                    texture=tex,
                    pos=(draw_center.x - self.size / 2, draw_center.y - self.size / 2),
                    size=(self.size, self.size),
                )
            else:
                Color(1, 0.45, 0.2, 0.55)
                Ellipse(pos=(draw_center.x - self.size / 2, draw_center.y - self.size / 2), size=(self.size, self.size))

class GameWidget(Widget):
    MAX_ENEMIES = 100  # Limit to prevent lag
    GAME_DURATION = 15 * 60  # 15 minutes in seconds
    STATE_LOADING = "LOADING"
    STATE_MAIN_MENU = "MAIN_MENU"
    STATE_PLAYING = "PLAYING"
    STATE_PAUSED = "PAUSED"
    STATE_SETTINGS = "SETTINGS"
    STATE_DEFEATED = "DEFEATED"
    STATE_VICTORY = "VICTORY"

    def __init__(self, **kwargs):
        initial_state = kwargs.pop("initial_state", self.STATE_LOADING)
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
        self.base_spawn_interval = 1.5  # Harder base spawn rate
        self.spawn_interval = self.base_spawn_interval
        self.min_spawn_interval = 0.22
        self.enemy_speed_multiplier = 1.0
        self.bullets: List[BulletEntity] = []
        self.grenades: List[GrenadeEntity] = []
        self.explosion_effects: List[ExplosionEffect] = []
        self.exp_orbs: List[ExpOrb] = []
        self.boss_orbs: List[BossOrb] = []
        self.health_orbs: List[HealthOrb] = []
        self.exp_pickup_radius = 52.0
        self.health_orb_drop_chance = 0.12
        self.health_orb_special_drop_chance = 0.35
        self.health_orb_heal_ratio = 0.15
        self.health_orb_lifetime = 10.0
        self.grenade_contact_arm_time = 0.20
        self.grenade_damage_base = 70.0
        self.grenade_damage_str_scale = 5.0
        self.grenade_radius_base = 220.0
        self.grenade_radius_int_scale = 6.0
        self.grenade_visual_scale = 1.4
        self.grenade_explosion_visual_scale = 1.4
        self.grenade_fuse_min_time = 0.35
        self.grenade_fuse_max_time = 1.15
        self.grenade_fuse_offset = 0.06

        # Passive skills (always active for now)
        self.passive_attack_speed_mult = 0.82  # lower fire interval -> faster attacks
        self.passive_lifesteal = 0.04          # 4% of dealt damage returned as HP
        self.passive_pickup_radius_mult = 1.5

        # Boss upgrade multipliers (stack with each boss reward choice)
        self.boss_move_speed_mult = 1.0
        self.boss_hp_mult = 1.0
        self.boss_skill_cdr_mult = 1.0
        self.boss_grenade_radius_mult = 1.0
        
        # Special enemy spawning (every 3 minutes, no max limit)
        self.special_enemies: List[SpecialEnemyEntity] = []
        self.special_spawn_timer = 0.0
        self.special_spawn_interval = 180.0  # 3 minutes in seconds
        self.last_special_types: List[str] = []  # Track last 2 types spawned
        
        # Enemy projectiles (Kitsune's fire)
        self.enemy_projectiles: List[EnemyProjectileEntity] = []

        # Front-end flow states (Phase D)
        self.game_state = initial_state
        self.settings_return_state = self.STATE_MAIN_MENU
        self.loading_progress = 0.0
        self.loading_duration = 1.6
        self.death_screen_timer = 0.0
        self.death_screen_delay = 1.1
        self._scheduled_update = None
        self._is_cleaned = False
        self.main_menu_buttons = []
        self.pause_buttons = []
        self.settings_buttons = []
        self.settings_sliders = {}
        self.defeated_buttons = []
        self.victory_buttons = []
        self.settings = {
            "music_volume": 0.7,
            "sfx_volume": 0.7,
            "fullscreen": False,
        }

        self.ui_textures = self._load_ui_textures()
        
        self.bg_texture = CoreImage("game_picture/background/bg2.png").texture
        self.menu_bg_texture = self._load_texture("game_picture/background/bg1.png") or self.bg_texture
        self._keyboard = Window.request_keyboard(self._on_keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_key_down, on_key_up=self._on_key_up)
        self.pressed_keys: Set[str] = set()
        self.debug_label = Label(text="", pos=(10, 10), halign="left", valign="bottom")
        self.pos_label = Label(text="", halign="right", valign="top")
        self.progression_label = Label(text="", halign="left", valign="top")
        self.debug_mode = False
        self.god_mode = False  # Player invincibility (debug key 8)
        self.bullet_damage = self.player.bullet_damage
        self.fire_rate = self.player.fire_rate
        
        self.fire_timer = 0.0
        self.firing = False
        self.left_mouse_held = False
        self.burst_shots_remaining = 0  # Support for semi/burst fire modes

        self.dodge_duration = 0.18
        self.dodge_distance = 180.0
        self.dodge_timer = 0.0
        self.dodge_iframe_timer = 0.0
        self.dodge_direction = Vector(1, 0)

        self.grenade_throw_textures = self._load_sequential_textures(self.player.asset_path, "Grenade", max_frames=20)
        self.grenade_explosion_textures = self._load_sequential_textures(self.player.asset_path, "Explosion", max_frames=20)
        if not self.grenade_explosion_textures:
            self.grenade_explosion_textures = self._load_sequential_textures("game_picture/player/Soldier_1", "Explosion", max_frames=20)

        # Skill runtime state (active skills + hotkey slots)
        self.skill_cooldowns: Dict[str, Dict[str, float]] = {
            "dodge": {"base": 2.2, "remaining": 0.0},
            "grenade": {"base": 6.5, "remaining": 0.0},
            "shockwave": {"base": 8.0, "remaining": 0.0},
        }
        self.ultimate_kills_required = 20
        self.ultimate_kill_progress = 0
        self.ultimate_infinite_ammo_duration = 15.0
        self.ultimate_infinite_ammo_timer = 0.0
        self.balance_preset_order = ["conservative", "balanced", "generous"]
        self.balance_presets = self._build_balance_presets()
        self.auto_balance_progression = True
        self.balance_start_preset = "balanced"
        self.balance_end_preset = "conservative"
        self.balance_preset_name = "balanced"
        self.balance_status_text = "Balanced"
        self._apply_balance_preset(self.balance_preset_name)

        self.skill_slots = [
            {"key": "Q", "bind": "Q", "skill_id": "dodge", "label": "Dash"},
            {"key": "E", "bind": "E", "skill_id": "grenade", "label": "Grenade"},
            {"key": "1", "bind": "1", "skill_id": "shockwave", "label": "Ultimate"},
        ]
        self.skill_key_to_skill = {
            "q": "dodge",
            "e": "grenade",
            "1": "shockwave",
        }

        # Level-up selection overlay
        self.levelup_active = False
        self.pending_levelups = 0
        self.levelup_choices = []
        self.levelup_choice_labels = {
            "str": "STR +1  (Damage +)",
            "dex": "DEX +1  (Fire Rate +)",
            "agi": "AGI +1  (Move Speed +)",
            "int": "INT +1  (Skill Cooldown -)",
            "vit": "VIT +1  (Max HP +)",
            "luck": "LUCK +1 (Crit / Drop +)",
        }

        # Boss upgrade overlay
        self.boss_upgrade_active = False
        self.pending_boss_upgrades = 0
        self.boss_upgrade_choices = []
        self.boss_upgrade_labels = {
            "speed": "Move Speed x1.5",
            "hp": "Max HP x1.5",
            "skill_cooldown": "Skill Cooldown x1.5",
            "radius": "Grenade Radius x1.5",
        }

        # Game timer
        self.game_time = 0.0
        self.time_speed_multiplier = 1.0  # Normal speed, can be increased in debug mode
        self.timer_label = Label(text="15:00", font_size=48, halign="center", valign="middle")
        self.timer_label.color = (1, 1, 1, 1)  # White
        self.timer_label.bold = True
        self.timer_label.opacity = 0  # Timer drawn on canvas
        self.add_widget(self.timer_label)

        self.add_widget(self.debug_label)
        self.add_widget(self.pos_label)
        self.progression_label.opacity = 0  # HUD drawn on canvas
        self.add_widget(self.progression_label)

        self.kill_count = 0
        self.coins = 0

        self._sync_combat_from_player()

        self._spawn_player_at_screen_center()

        self._scheduled_update = Clock.schedule_interval(self.update, 1 / 60)

    def cleanup(self):
        if self._is_cleaned:
            return
        if self._scheduled_update is not None:
            self._scheduled_update.cancel()
            self._scheduled_update = None
        self._on_keyboard_closed()
        self._is_cleaned = True

    def _load_texture(self, path: str):
        try:
            return CoreImage(path).texture
        except Exception:
            return None

    def _load_ui_textures(self) -> Dict[str, object]:
        texture_paths = {
            "loading_bg": "game_picture/ui/Loading Screen/Background.png",
            "loading_logo": "game_picture/ui/Loading Screen/Test Logo.png",
            "loading_bar_bg": "game_picture/ui/Loading Screen/Loading Bar BG.png",
            "loading_bar_fill": "game_picture/ui/Loading Screen/Loading Bar.png",
            "loading_icon": "game_picture/ui/Loading Screen/Loading icon.png",
            "main_btn_play": "game_picture/ui/Main menu/BTN PLAY.png",
            "main_btn_settings": "game_picture/ui/Main menu/BTN SETTINGS.png",
            "main_btn_exit": "game_picture/ui/Main menu/BTN Exit.png",
            "main_btn_bg": "game_picture/ui/Main menu/Button BG.png",
            "main_btn_shadow": "game_picture/ui/Main menu/Button BG shadow.png",
            "pause_bg": "game_picture/ui/Pause menu/BG.png",
            "pause_preset": "game_picture/ui/Pause menu/PAUSE PRESET.png",
            "pause_title": "game_picture/ui/Pause menu/Pause.png",
            "pause_btn_back": "game_picture/ui/Pause menu/BTN BACK.png",
            "pause_btn_menu": "game_picture/ui/Pause menu/BTN MENU.png",
            "pause_btn_settings": "game_picture/ui/Pause menu/BTN SETTINGS.png",
            "pause_line": "game_picture/ui/Pause menu/Line.png",
            "pause_star": "game_picture/ui/Pause menu/Star.png",
            "defeat_bg": "game_picture/ui/Mission Failed/BG.png",
            "defeat_preset": "game_picture/ui/Mission Failed/BG Preset.png",
            "defeat_btn_retry": "game_picture/ui/Mission Failed/BTN Retry.png",
            "victory_preset": "game_picture/ui/Victory/Victory panel Preset.png",
            "victory_btn_menu": "game_picture/ui/Victory/BTN MENU.png",
            "victory_btn_ok": "game_picture/ui/Victory/BTN OK.png",
            "victory_star": "game_picture/ui/Victory/Star.png",
            "settings_bg": "game_picture/ui/Settings/Settings BG.png",
            "settings_btn_ok": "game_picture/ui/Settings/BTN OK.png",
            "settings_bar_bg": "game_picture/ui/Settings/Bar BG.png",
            "settings_bar_fill": "game_picture/ui/Settings/Bar.png",
            "settings_desc": "game_picture/ui/Settings/Description Area.png",
            "settings_checkbox_1": "game_picture/ui/Settings/Checkbox 01.png",
            "settings_checkbox_2": "game_picture/ui/Settings/Chebox 02.png",
            "settings_checkbox_3": "game_picture/ui/Settings/Checkbox 03.png",
            "settings_mark": "game_picture/ui/Settings/Mark.png",
            "money_icon": "game_picture/ui/HUD/MONEY PANEL/Money Icon.png",
            "money_panel_empty": "game_picture/ui/HUD/MONEY PANEL/Money Panel EMPTY HUD.png",
            "money_panel": "game_picture/ui/HUD/MONEY PANEL/Money Panel HUD.png",
        }
        return {key: self._load_texture(path) for key, path in texture_paths.items()}

    def _build_balance_presets(self) -> Dict[str, Dict[str, float]]:
        return {
            "conservative": {
                "orb_drop_chance": 0.09,
                "orb_special_drop_chance": 0.25,
                "orb_heal_ratio": 0.10,
                "orb_lifetime": 8.0,
                "exp_pickup_radius": 46.0,
                "lifesteal": 0.03,
                "pickup_radius_mult": 1.35,
                "grenade_contact_arm_time": 0.24,
                "grenade_cooldown": 7.2,
                "grenade_damage_base": 62.0,
                "grenade_damage_str_scale": 4.0,
                "grenade_radius_base": 200.0,
                "grenade_radius_int_scale": 5.0,
                "grenade_fuse_min": 0.32,
                "grenade_fuse_max": 1.00,
                "grenade_fuse_offset": 0.05,
            },
            "balanced": {
                "orb_drop_chance": 0.12,
                "orb_special_drop_chance": 0.35,
                "orb_heal_ratio": 0.15,
                "orb_lifetime": 10.0,
                "exp_pickup_radius": 52.0,
                "lifesteal": 0.04,
                "pickup_radius_mult": 1.50,
                "grenade_contact_arm_time": 0.20,
                "grenade_cooldown": 6.5,
                "grenade_damage_base": 70.0,
                "grenade_damage_str_scale": 5.0,
                "grenade_radius_base": 220.0,
                "grenade_radius_int_scale": 6.0,
                "grenade_fuse_min": 0.35,
                "grenade_fuse_max": 1.15,
                "grenade_fuse_offset": 0.06,
            },
            "generous": {
                "orb_drop_chance": 0.16,
                "orb_special_drop_chance": 0.45,
                "orb_heal_ratio": 0.20,
                "orb_lifetime": 12.0,
                "exp_pickup_radius": 62.0,
                "lifesteal": 0.05,
                "pickup_radius_mult": 1.65,
                "grenade_contact_arm_time": 0.14,
                "grenade_cooldown": 5.8,
                "grenade_damage_base": 80.0,
                "grenade_damage_str_scale": 6.0,
                "grenade_radius_base": 250.0,
                "grenade_radius_int_scale": 7.0,
                "grenade_fuse_min": 0.30,
                "grenade_fuse_max": 1.25,
                "grenade_fuse_offset": 0.08,
            },
        }

    def _apply_balance_values(self, values: Dict[str, float], reset_grenade_cooldown: bool = False):
        self.health_orb_drop_chance = values["orb_drop_chance"]
        self.health_orb_special_drop_chance = values["orb_special_drop_chance"]
        self.health_orb_heal_ratio = values["orb_heal_ratio"]
        self.health_orb_lifetime = values["orb_lifetime"]
        self.exp_pickup_radius = values["exp_pickup_radius"]
        self.passive_lifesteal = values["lifesteal"]
        self.passive_pickup_radius_mult = values["pickup_radius_mult"]

        self.grenade_contact_arm_time = values["grenade_contact_arm_time"]
        self.grenade_damage_base = values["grenade_damage_base"]
        self.grenade_damage_str_scale = values["grenade_damage_str_scale"]
        self.grenade_radius_base = values["grenade_radius_base"]
        self.grenade_radius_int_scale = values["grenade_radius_int_scale"]
        self.grenade_fuse_min_time = values["grenade_fuse_min"]
        self.grenade_fuse_max_time = values["grenade_fuse_max"]
        self.grenade_fuse_offset = values["grenade_fuse_offset"]

        grenade_payload = self.skill_cooldowns.get("grenade") if hasattr(self, "skill_cooldowns") else None
        if grenade_payload is not None:
            grenade_payload["base"] = values["grenade_cooldown"]
            if reset_grenade_cooldown:
                grenade_payload["remaining"] = 0.0
            else:
                grenade_payload["remaining"] = min(grenade_payload["remaining"], grenade_payload["base"])

    def _apply_balance_preset(self, preset_name: str, reset_grenade_cooldown: bool = False):
        preset = self.balance_presets.get(preset_name)
        if preset is None:
            return

        self.balance_preset_name = preset_name
        self.balance_status_text = preset_name.title()
        self._apply_balance_values(preset, reset_grenade_cooldown=reset_grenade_cooldown)

    def _apply_time_scaled_balance(self):
        if not self.auto_balance_progression:
            return

        start_values = self.balance_presets.get(self.balance_start_preset)
        end_values = self.balance_presets.get(self.balance_end_preset)
        if start_values is None or end_values is None:
            return

        if self.GAME_DURATION <= 0:
            t = 1.0
        else:
            t = max(0.0, min(1.0, self.game_time / self.GAME_DURATION))

        blended = {}
        for key, start_value in start_values.items():
            end_value = end_values.get(key, start_value)
            blended[key] = start_value + (end_value - start_value) * t

        self.balance_status_text = f"Adaptive {self.balance_start_preset.title()}→{self.balance_end_preset.title()} {int(t * 100)}%"
        self._apply_balance_values(blended, reset_grenade_cooldown=False)

    def _cycle_balance_preset(self):
        self.auto_balance_progression = False
        if not self.balance_preset_order:
            return

        try:
            current_idx = self.balance_preset_order.index(self.balance_preset_name)
        except ValueError:
            current_idx = 0
        next_name = self.balance_preset_order[(current_idx + 1) % len(self.balance_preset_order)]
        self._apply_balance_preset(next_name, reset_grenade_cooldown=True)

    def _set_state(self, new_state: str):
        if self.game_state == new_state:
            return
        self.game_state = new_state
        if new_state != self.STATE_PLAYING:
            self.firing = False
            self.left_mouse_held = False
            self.burst_shots_remaining = 0
            self.pressed_keys.clear()
            self.player.stop_shooting()

    def _return_to_main_menu(self):
        app = App.get_running_app()
        if app and hasattr(app, "return_to_main_menu"):
            app.return_to_main_menu()

    def _retry_run(self):
        app = App.get_running_app()
        if app and hasattr(app, "retry_run"):
            app.retry_run()

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

        if key == 'escape':
            if self.game_state == self.STATE_PLAYING and not self.levelup_active and not self.boss_upgrade_active:
                self._set_state(self.STATE_PAUSED)
                return True
            if self.game_state == self.STATE_PAUSED:
                self._set_state(self.STATE_PLAYING)
                return True
            if self.game_state == self.STATE_SETTINGS:
                self._set_state(self.settings_return_state)
                return True

        if self.game_state in (self.STATE_LOADING, self.STATE_MAIN_MENU, self.STATE_DEFEATED, self.STATE_VICTORY):
            return True

        if self.game_state == self.STATE_SETTINGS:
            return True

        if self.game_state == self.STATE_PAUSED:
            return True

        if key == 'r':
            if hasattr(self.player, 'start_reload'):
                self.player.start_reload()
            return True

        if key == 'v':
            if hasattr(self.player, 'toggle_firing_mode'):
                self.player.toggle_firing_mode()
            return True

        if self.levelup_active:
            if key in ('1', '2', '3'):
                self._apply_levelup_choice(int(key) - 1)
            return True

        if self.boss_upgrade_active:
            if key in ('1', '2', '3'):
                self._apply_boss_upgrade_choice(int(key) - 1)
            return True

        if key in self.skill_key_to_skill and not self.player.is_dead:
            self._use_skill_from_key(key)
            return True

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

        if self.debug_mode and key == '4':
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

        if self.debug_mode and key == '0':
            # Cycle balance presets for fast playtest comparisons (manual override)
            self._cycle_balance_preset()
            return True

        self.pressed_keys.add(key)
        return True

    def _on_key_up(self, keyboard, keycode):
        if self.game_state != self.STATE_PLAYING:
            return True
        self.pressed_keys.discard(keycode[1])
        return True

    def on_touch_down(self, touch):
        if self.game_state == self.STATE_LOADING:
            return True

        if self.game_state == self.STATE_MAIN_MENU:
            if touch.button == 'left':
                action = self._hit_test_buttons(self.main_menu_buttons, touch.x, touch.y)
                if action == "play":
                    self._set_state(self.STATE_PLAYING)
                elif action == "settings":
                    self.settings_return_state = self.STATE_MAIN_MENU
                    self._set_state(self.STATE_SETTINGS)
                elif action == "exit":
                    app = App.get_running_app()
                    if app:
                        app.stop()
                return True

        if self.game_state == self.STATE_PAUSED:
            if touch.button == 'left':
                action = self._hit_test_buttons(self.pause_buttons, touch.x, touch.y)
                if action == "resume":
                    self._set_state(self.STATE_PLAYING)
                elif action == "settings":
                    self.settings_return_state = self.STATE_PAUSED
                    self._set_state(self.STATE_SETTINGS)
                elif action == "menu":
                    self._return_to_main_menu()
                return True

        if self.game_state == self.STATE_SETTINGS:
            if touch.button == 'left':
                if self._handle_settings_touch(touch.x, touch.y):
                    return True
                action = self._hit_test_buttons(self.settings_buttons, touch.x, touch.y)
                if action == "ok":
                    self._set_state(self.settings_return_state)
                return True

        if self.game_state == self.STATE_DEFEATED:
            if touch.button == 'left':
                action = self._hit_test_buttons(self.defeated_buttons, touch.x, touch.y)
                if action == "retry":
                    self._retry_run()
                elif action == "menu":
                    self._return_to_main_menu()
                return True

        if self.game_state == self.STATE_VICTORY:
            if touch.button == 'left':
                action = self._hit_test_buttons(self.victory_buttons, touch.x, touch.y)
                if action == "retry":
                    self._retry_run()
                elif action == "menu":
                    self._return_to_main_menu()
                return True

        if self.game_state != self.STATE_PLAYING:
            return True

        if touch.button == 'left':
            # Process clicking on upgrade cards if level up screen is active
            if self.levelup_active:
                s = self.height / 1080.0 if self.height > 0 else 1.0
                panel_w = self.width * 0.55
                panel_h = self.height * 1
                panel_x = (self.width - panel_w) / 2
                panel_y = (self.height - panel_h) / 2
                
                card_count = len(self.levelup_choices)
                card_spacing = 24 * s
                total_card_width = panel_w - 80 * s
                card_w = (total_card_width - card_spacing * (card_count - 1)) / max(1, card_count)
                card_h = panel_h * 0.48
                card_start_x = panel_x + 40 * s
                card_y = panel_y + 30 * s
                
                # Check if click falls within any card's bounding box
                for idx in range(card_count):
                    cx = card_start_x + idx * (card_w + card_spacing)
                    if cx <= touch.x <= cx + card_w and card_y <= touch.y <= card_y + card_h:
                        self._apply_levelup_choice(idx)
                        break
                return True

            # Process boss upgrade cards
            if self.boss_upgrade_active:
                s = self.height / 1080.0 if self.height > 0 else 1.0
                panel_w = self.width * 0.55
                panel_h = self.height * 0.52
                panel_x = (self.width - panel_w) / 2
                panel_y = (self.height - panel_h) / 2

                card_count = len(self.boss_upgrade_choices)
                card_spacing = 24 * s
                total_card_width = panel_w - 80 * s
                card_w = (total_card_width - card_spacing * (card_count - 1)) / max(1, card_count)
                card_h = panel_h * 0.48
                card_start_x = panel_x + 40 * s
                card_y = panel_y + 30 * s

                for idx in range(card_count):
                    cx = card_start_x + idx * (card_w + card_spacing)
                    if cx <= touch.x <= cx + card_w and card_y <= touch.y <= card_y + card_h:
                        self._apply_boss_upgrade_choice(idx)
                        break
                return True

            if self.player.is_dead:
                return True

            self.left_mouse_held = True
            
            # Weapon firing / reloading logic
            has_infinite_ammo = self._has_ultimate_infinite_ammo()
            can_fire_now = (not getattr(self.player, 'is_reloading', False)) or has_infinite_ammo
            has_ammo_now = getattr(self.player, 'ammo', 1) > 0

            if can_fire_now and (has_ammo_now or has_infinite_ammo):
                mode = getattr(self.player, 'firing_mode', 'AUTO')
                if mode == 'AUTO':
                    self.firing = True
                    self.player.start_shooting()
                elif mode == 'SEMI':
                    if not self.firing:
                        self.burst_shots_remaining = 3
                        self.firing = True
                        self.player.start_shooting()
                elif mode == 'SINGLE':
                    if not self.firing:
                        self.burst_shots_remaining = 1
                        self.firing = True
                        self.player.start_shooting()
            elif not has_infinite_ammo and getattr(self.player, 'ammo', 0) <= 0:
                if hasattr(self.player, 'start_reload'):
                    self.player.start_reload()
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.game_state != self.STATE_PLAYING:
            return True
        if touch.button == 'left':
            self.left_mouse_held = False
            mode = getattr(self.player, 'firing_mode', 'AUTO')
            if mode == 'AUTO':
                self.player.stop_shooting()
                self.firing = False
            # For SEMI and SINGLE, we let the ongoing burst finish gracefully
            return True
        return super().on_touch_up(touch)

    def update(self, dt: float):
        if self.game_state == self.STATE_LOADING:
            self.loading_progress = min(1.0, self.loading_progress + (dt / max(0.1, self.loading_duration)))
            self._draw_loading_screen()
            self._update_debug(0.0)
            if self.loading_progress >= 1.0:
                self._set_state(self.STATE_MAIN_MENU)
            return

        if self.game_state == self.STATE_MAIN_MENU:
            self._draw_main_menu()
            self._update_debug(0.0)
            return

        if self.game_state == self.STATE_PAUSED:
            self._draw_scene()
            self._draw_pause_overlay()
            self._update_debug(0.0)
            return

        if self.game_state == self.STATE_SETTINGS:
            if self.settings_return_state == self.STATE_PAUSED:
                self._draw_scene()
                self._draw_pause_overlay(draw_buttons=False)
            else:
                self._draw_main_menu(draw_settings=False)
            self._draw_settings_overlay()
            self._update_debug(0.0)
            return

        if self.game_state == self.STATE_DEFEATED:
            self._draw_scene()
            self._draw_defeated_overlay()
            self._update_debug(0.0)
            return

        if self.game_state == self.STATE_VICTORY:
            self._draw_scene()
            self._draw_victory_overlay()
            self._update_debug(0.0)
            return

        if self.levelup_active or self.boss_upgrade_active:
            self._update_progression_hud()
            self._draw_scene()
            self._update_debug(0.0)
            return

        self._update_skill_cooldowns(dt)
        self._update_dodge_timers(dt)
        if self.ultimate_infinite_ammo_timer > 0:
            self.ultimate_infinite_ammo_timer = max(0.0, self.ultimate_infinite_ammo_timer - dt)

        # Update game time (stop at max duration)
        if self.game_time < self.GAME_DURATION:
            self.game_time += dt * self.time_speed_multiplier
            if self.game_time > self.GAME_DURATION:
                self.game_time = self.GAME_DURATION

            # Update spawn interval based on elapsed time (faster spawning over time)
            # At 0:00 -> 1.5s interval, at 15:00 -> 0.22s interval
            progress = self.game_time / self.GAME_DURATION  # 0.0 to 1.0
            target_interval = self.base_spawn_interval - (progress * 1.45)
            self.spawn_interval = max(self.min_spawn_interval, target_interval)
            self.enemy_speed_multiplier = 1.0 + (progress * 0.85)
        elif self.game_state == self.STATE_PLAYING:
            self._set_state(self.STATE_VICTORY)
            self._draw_scene()
            self._draw_victory_overlay()
            self._update_debug(0.0)
            return

        self._apply_time_scaled_balance()

        self._update_progression_hud()

        self.player.update(dt, self.pressed_keys, (self.width, self.height))
        self._update_dodge_state(dt)

        # If player is dead, skip gameplay updates but still draw
        if self.player.is_dead:
            self.death_screen_timer += dt
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
            if self.death_screen_timer >= self.death_screen_delay:
                self._set_state(self.STATE_DEFEATED)
            self._draw_scene()
            if self.game_state == self.STATE_DEFEATED:
                self._draw_defeated_overlay()
            self._update_debug(dt)
            return

        self._resume_auto_fire_if_holding()

        # Keep player facing aligned with cursor while shooting
        if self.firing:
            mx, my = Window.mouse_pos
            local_mouse = Vector(*self.to_widget(mx, my))
            player_center = self.player.pos + Vector(self.player.size[0] / 2, self.player.size[1] / 2)
            self.player.facing = 1 if local_mouse.x >= player_center.x else -1

        # Spawn enemies at left/right edges
        if self.game_time < self.GAME_DURATION:
            self.spawn_timer += dt
            if self.spawn_timer >= self.spawn_interval:
                self.spawn_timer -= self.spawn_interval
                progress = self.game_time / self.GAME_DURATION if self.GAME_DURATION > 0 else 0.0
                spawn_count = 1 + int(progress * 2.5)
                spawn_count = max(1, min(4, spawn_count))
                for _ in range(spawn_count):
                    self._spawn_enemy()

            # Spawn special enemies every 3 minutes (affected by time speed multiplier)
            self.special_spawn_timer += dt * self.time_speed_multiplier
            if self.special_spawn_timer >= self.special_spawn_interval:
                self.special_spawn_timer -= self.special_spawn_interval
                self._spawn_special_enemy()

        # Update all enemies (target player's hitbox center for accurate pathing/aim)
        pbox = self.player.get_hitbox()
        player_center = Vector(pbox[0] + pbox[2] / 2, pbox[1] + pbox[3] / 2)
        enemy_dt = dt * self.enemy_speed_multiplier
        for enemy in self.enemies[:]:
            enemy.update(enemy_dt, player_center, (self.width, self.height))
            if not enemy.is_dying:
                self._update_enemy_state(enemy)

        # Update all special enemies (Kitsune may spawn projectiles)
        for special_enemy in self.special_enemies[:]:
            if not special_enemy.is_dying:
                projectile = special_enemy.update(enemy_dt, player_center, (self.width, self.height), bullets=self.bullets)
                if projectile:  # Kitsune spawned a fire projectile
                    self.enemy_projectiles.append(projectile)
                self._update_enemy_state(special_enemy)
            else:
                special_enemy.update(enemy_dt, player_center, (self.width, self.height))

        # Light separation so enemies don't stack
        self._separate_enemies()

        # Re-clamp all enemies to walkable Y band after separation push
        height = self.height if self.height > 0 else Window.height
        block_unit = height / 10.0
        walk_min_y = block_unit
        for e in self.enemies + self.special_enemies:
            walk_max_y = height - (3 * block_unit) - e.size[1]
            e.pos.y = max(walk_min_y, min(e.pos.y, max(walk_min_y, walk_max_y)))

        # Handle weapon fire cooldown tracking
        self.fire_timer += dt

        # Handle shooting execution
        if self.firing and not self.player.is_dead:
            has_infinite_ammo = self._has_ultimate_infinite_ammo()
            if getattr(self.player, 'is_reloading', False) and not has_infinite_ammo:
                self.player.stop_shooting()
                self.firing = False
                self.burst_shots_remaining = 0
            elif has_infinite_ammo or getattr(self.player, 'ammo', 1) > 0:
                if self.fire_timer >= self._get_effective_fire_rate():
                    self.fire_timer = 0.0  # Reset cooldown explicitly to avoid rapid stack bursts
                    self._spawn_bullet()
                    if not has_infinite_ammo and hasattr(self.player, 'consume_ammo'):
                        self.player.consume_ammo()

                    mode = getattr(self.player, 'firing_mode', 'AUTO')
                    if mode in ('SEMI', 'SINGLE'):
                        self.burst_shots_remaining -= 1
                        if self.burst_shots_remaining <= 0:
                            self.firing = False
                            self.player.stop_shooting()
            else:
                if hasattr(self.player, 'start_reload'):
                    self.player.start_reload()
                self.firing = False
                self.burst_shots_remaining = 0
        
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
                    bullet_damage = getattr(b, "damage", self.bullet_damage)
                    enemy_died = enemy.take_damage(bullet_damage)
                    self._apply_lifesteal(bullet_damage)
                    if enemy_died:
                        self._handle_enemy_kill(enemy)
                    hit = True
                    break
            if not hit:
                # Check collision with special enemies
                for se in self.special_enemies[:]:
                    if se.is_dying:
                        continue
                    if self._rects_intersect(bullet_box, se.get_hitbox()):
                        bullet_damage = getattr(b, "damage", self.bullet_damage)
                        enemy_died = se.take_damage(bullet_damage)
                        self._apply_lifesteal(bullet_damage)
                        if enemy_died:
                            self._handle_enemy_kill(se)
                        hit = True
                        break
            if hit:
                if b in self.bullets:
                    self.bullets.remove(b)

        # Update grenades and explode when timer completes
        for grenade in self.grenades[:]:
            grenade.update(dt)
            if grenade.is_exploded() or self._grenade_hits_enemy(grenade):
                self._explode_grenade(grenade)
                self.grenades.remove(grenade)

        for effect in self.explosion_effects[:]:
            effect.update(dt)
            if effect.done:
                self.explosion_effects.remove(effect)
        
        # Update and clean up enemy projectiles
        for proj in self.enemy_projectiles[:]:
            proj.update(dt)
            # Check collision with player
            pbox = self.player.get_hitbox()
            proj_box = proj.get_hitbox()
            if self._rects_intersect(pbox, proj_box):
                # Hit player! Apply damage (unless godmode)
                if self._can_player_take_damage():
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

        # Update exp orbs: pull toward player and collect on touch
        pull_radius = self._get_exp_pull_radius()
        pickup_box = self._inflate_rect(self.player.get_hitbox(), self.exp_pickup_radius * self.passive_pickup_radius_mult)
        for orb in self.exp_orbs[:]:
            orb.update(dt, player_center, pull_radius)
            if self._rects_intersect(orb.get_hitbox(), pickup_box):
                self._grant_player_exp(orb.exp_value)
                self.exp_orbs.remove(orb)
                continue

            # Cleanup only if somehow far outside the world
            margin = 300
            if orb.pos.x < -margin or orb.pos.x > self.width + margin or orb.pos.y < -margin or orb.pos.y > self.height + margin:
                self.exp_orbs.remove(orb)

        # Update boss reward orbs
        for boss_orb in self.boss_orbs[:]:
            boss_orb.update(dt, player_center, pull_radius * 0.95)
            if self._rects_intersect(boss_orb.get_hitbox(), pickup_box):
                self.boss_orbs.remove(boss_orb)
                self.pending_boss_upgrades += 1
                if not self.boss_upgrade_active:
                    self._open_next_boss_upgrade()
                continue

            margin = 300
            if boss_orb.pos.x < -margin or boss_orb.pos.x > self.width + margin or boss_orb.pos.y < -margin or boss_orb.pos.y > self.height + margin:
                self.boss_orbs.remove(boss_orb)

        # Update health orbs
        for health_orb in self.health_orbs[:]:
            health_orb.update(dt, player_center, pull_radius * 0.9)
            if self._rects_intersect(health_orb.get_hitbox(), pickup_box):
                heal_amount = self.player.max_hp * health_orb.heal_ratio
                self.player.hp = min(self.player.max_hp, self.player.hp + heal_amount)
                self.health_orbs.remove(health_orb)
                continue

            margin = 300
            if health_orb.is_expired() or health_orb.pos.x < -margin or health_orb.pos.x > self.width + margin or health_orb.pos.y < -margin or health_orb.pos.y > self.height + margin:
                self.health_orbs.remove(health_orb)
        
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
                    if self._can_player_take_damage():
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

            # Draw player (hit flash handled inside draw())
            self.player.draw(self.canvas)
            Color(1, 1, 1, 1)  # Reset color

            # Draw enemies using danger-aware Y-sort ordering.
            for enemy in self._get_enemy_render_order():
                enemy.draw(self.canvas)

            # Draw bullets
            for b in self.bullets:
                b.draw(self.canvas)

            # Draw grenades
            for grenade in self.grenades:
                grenade.draw(self.canvas)

            for effect in self.explosion_effects:
                effect.draw(self.canvas)

            # Draw exp orbs
            for orb in self.exp_orbs:
                orb.draw(self.canvas)

            for boss_orb in self.boss_orbs:
                boss_orb.draw(self.canvas)

            for health_orb in self.health_orbs:
                health_orb.draw(self.canvas)

            # Draw enemy projectiles
            for proj in self.enemy_projectiles:
                proj.draw(self.canvas)

            # Draw game UI (HP bar, EXP bar, timer, kills, etc.)
            self._draw_game_ui()

            if self.levelup_active:
                self._draw_levelup_overlay()

            if self.boss_upgrade_active:
                self._draw_boss_upgrade_overlay()

            # Debug hitboxes
            if self.debug_mode and self.game_state == self.STATE_PLAYING:
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

                # EXP Orb hitboxes and pull radius
                Color(0.2, 1, 0.3, 0.85)
                for orb in self.exp_orbs:
                    ox, oy, ow, oh = orb.get_hitbox()
                    Line(rectangle=(ox, oy, ow, oh), width=1)
                Color(0.2, 1, 0.3, 0.25)
                pbox = self.player.get_hitbox()
                center_x = pbox[0] + pbox[2] / 2
                center_y = pbox[1] + pbox[3] / 2
                Line(circle=(center_x, center_y, self._get_exp_pull_radius()), width=1)

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

    # ─── Enhanced UI Drawing Methods ────────────────────────────────────

    def _draw_outlined_text(self, text, x, y, font_size=24, color=(1, 1, 1, 1),
                            anchor_x='left', anchor_y='bottom', bold=False):
        """Draw text with dark outline at the specified position. Returns (w, h)."""
        lbl = CoreLabel(text=text, font_size=font_size, color=color, bold=bold)
        lbl.refresh()
        tex = lbl.texture
        if not tex:
            return (0, 0)
        w, h = tex.size
        draw_x, draw_y = x, y
        if anchor_x == 'center':
            draw_x = x - w / 2
        elif anchor_x == 'right':
            draw_x = x - w
        if anchor_y == 'center':
            draw_y = y - h / 2
        elif anchor_y == 'top':
            draw_y = y - h
        shadow = CoreLabel(text=text, font_size=font_size, color=(0, 0, 0, 1), bold=bold)
        shadow.refresh()
        stex = shadow.texture
        if stex:
            Color(0, 0, 0, 0.9)
            for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                Rectangle(texture=stex, pos=(draw_x + dx, draw_y + dy), size=(w, h))
        Color(*color)
        Rectangle(texture=tex, pos=(draw_x, draw_y), size=(w, h))
        return (w, h)

    def _draw_texture_centered(self, texture, center_x: float, center_y: float, scale: float = 1.0, alpha: float = 1.0):
        if texture is None:
            return None
        width = texture.width * scale
        height = texture.height * scale
        x = center_x - width / 2
        y = center_y - height / 2
        Color(1, 1, 1, alpha)
        Rectangle(texture=texture, pos=(x, y), size=(width, height))
        return (x, y, width, height)

    def _draw_texture_fill_width(self, texture, x: float, y: float, width: float, height: float, alpha: float = 1.0):
        if texture is None or width <= 0 or height <= 0:
            return
        Color(1, 1, 1, alpha)
        Rectangle(texture=texture, pos=(x, y), size=(width, height))

    @staticmethod
    def _hit_test_buttons(buttons: List[dict], x: float, y: float):
        for button in buttons:
            bx, by, bw, bh = button["rect"]
            if bx <= x <= bx + bw and by <= y <= by + bh:
                return button["action"]
        return None

    @staticmethod
    def _format_time(total_seconds: float) -> str:
        seconds = max(0, int(total_seconds))
        minutes = seconds // 60
        rem = seconds % 60
        return f"{minutes:02}:{rem:02}"

    def _draw_loading_screen(self):
        self.canvas.clear()
        s = self.height / 1080.0 if self.height > 0 else 1.0
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=self.ui_textures.get("loading_bg") or self.menu_bg_texture, pos=(0, 0), size=self.size)
            self._draw_texture_centered(self.ui_textures.get("loading_logo"), self.width * 0.5, self.height * 0.65, 0.75 * s)

            bar_bg_rect = self._draw_texture_centered(self.ui_textures.get("loading_bar_bg"), self.width * 0.5, self.height * 0.2, 0.9 * s)
            if bar_bg_rect is not None:
                bx, by, bw, bh = bar_bg_rect
                margin = 8 * s
                self._draw_texture_fill_width(self.ui_textures.get("loading_bar_fill"), bx + margin, by + margin, (bw - margin * 2) * self.loading_progress, bh - margin * 2)

            self._draw_texture_centered(
                self.ui_textures.get("loading_icon"),
                self.width * 0.5,
                self.height * 0.3,
                (0.42 + 0.08 * math.sin(self.loading_progress * math.pi * 8)) * s,
            )
            self._draw_outlined_text(
                f"Loading... {int(self.loading_progress * 100)}%",
                self.width * 0.5,
                self.height * 0.12,
                font_size=int(30 * s),
                color=(0.95, 0.95, 0.95, 1),
                anchor_x='center',
                anchor_y='center',
                bold=True,
            )

    def _draw_main_menu(self, draw_settings: bool = True):
        self.canvas.clear()
        self.main_menu_buttons = []
        s = self.height / 1080.0 if self.height > 0 else 1.0
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=self.menu_bg_texture, pos=(0, 0), size=self.size)
            Color(0, 0, 0, 0.4)
            Rectangle(pos=(0, 0), size=self.size)

            self._draw_outlined_text("KIVY 2.5D SHOOTER", self.width * 0.5, self.height * 0.8, font_size=int(68 * s), color=(0.95, 0.9, 0.3, 1), anchor_x='center', anchor_y='center', bold=True)
            self._draw_outlined_text("Survive 15:00 • Build your soldier", self.width * 0.5, self.height * 0.73, font_size=int(24 * s), color=(0.92, 0.92, 0.96, 0.95), anchor_x='center', anchor_y='center')

            start_y = self.height * 0.56
            gap = 165 * s
            button_defs = [
                ("play", self.ui_textures.get("main_btn_play")),
                ("settings", self.ui_textures.get("main_btn_settings")),
                ("exit", self.ui_textures.get("main_btn_exit")),
            ]
            for idx, (action, texture) in enumerate(button_defs):
                by = start_y - idx * gap
                fallback = (self.width * 0.5 - 330 * s, by - 64 * s, 660 * s, 128 * s)
                self._draw_texture_centered(self.ui_textures.get("main_btn_shadow"), self.width * 0.5, by - 7 * s, 1.02 * s, 0.95)
                self._draw_texture_centered(self.ui_textures.get("main_btn_bg"), self.width * 0.5, by, 1.02 * s)
                rect = self._draw_texture_centered(texture, self.width * 0.5, by, 1.02 * s) or fallback
                self.main_menu_buttons.append({"action": action, "rect": rect})

        if draw_settings and self.game_state == self.STATE_SETTINGS:
            self._draw_settings_overlay()

    def _draw_pause_overlay(self, draw_buttons: bool = True):
        if draw_buttons:
            self.pause_buttons = []
        s = self.height / 1080.0 if self.height > 0 else 1.0
        with self.canvas:
            Color(0, 0, 0, 0.52)
            Rectangle(pos=(0, 0), size=self.size)
            self._draw_texture_centered(self.ui_textures.get("pause_bg"), self.width * 0.5, self.height * 0.5, 1.12 * s, 0.94)
            panel_rect = self._draw_texture_centered(self.ui_textures.get("pause_preset"), self.width * 0.5, self.height * 0.5, 1.28 * s)
            if panel_rect is None:
                panel_rect = (self.width * 0.2, self.height * 0.14, self.width * 0.6, self.height * 0.72)

            title_y = panel_rect[1] + panel_rect[3] * 0.84
            self._draw_texture_centered(self.ui_textures.get("pause_line"), self.width * 0.5, title_y - 48 * s, 1.25 * s, 0.7)

            if draw_buttons:
                for action, texture, y in [
                    ("resume", self.ui_textures.get("pause_btn_back"), panel_rect[1] + panel_rect[3] * 0.60),
                    ("settings", self.ui_textures.get("pause_btn_settings"), panel_rect[1] + panel_rect[3] * 0.42),
                    ("menu", self.ui_textures.get("pause_btn_menu"), panel_rect[1] + panel_rect[3] * 0.24),
                ]:
                    fallback = (self.width * 0.5 - 210 * s, y - 54 * s, 420 * s, 108 * s)
                    rect = self._draw_texture_centered(texture, self.width * 0.5, y, 1.36 * s) or fallback
                    self.pause_buttons.append({"action": action, "rect": rect})

            self._draw_texture_centered(self.ui_textures.get("pause_star"), panel_rect[0] + panel_rect[2] * 0.2, panel_rect[1] + panel_rect[3] * 0.14, 0.62 * s, 0.78)
            self._draw_texture_centered(self.ui_textures.get("pause_star"), panel_rect[0] + panel_rect[2] * 0.8, panel_rect[1] + panel_rect[3] * 0.14, 0.62 * s, 0.78)

    def _draw_defeated_overlay(self):
        self.defeated_buttons = []
        s = self.height / 1080.0 if self.height > 0 else 1.0
        with self.canvas:
            Color(0, 0, 0, 0.72)
            Rectangle(pos=(0, 0), size=self.size)
            self._draw_texture_centered(self.ui_textures.get("defeat_bg"), self.width * 0.5, self.height * 0.5, 1.25 * s)

            panel_w = self.width * 0.62
            panel_h = self.height * 0.62
            panel_x = (self.width - panel_w) / 2
            panel_y = self.height * 0.12
            Color(1, 1, 1, 1)
            Rectangle(texture=self.ui_textures.get("defeat_preset"), pos=(panel_x, panel_y), size=(panel_w, panel_h))

            # Title
            self._draw_outlined_text("MISSION FAILED", self.width * 0.5, panel_y + panel_h - 92 * s, font_size=int(62 * s), color=(1, 0.2, 0.2, 1), anchor_x='center', anchor_y='center', bold=True)

            # Stats
            self._draw_outlined_text(
                f"Kills: {self.kill_count}   Level: {self.player.level}   Time: {self._format_time(self.game_time)}",
                self.width * 0.5,
                panel_y + panel_h - 150 * s,
                font_size=int(42 * s),
                color=(0.95, 0.95, 0.96, 0.98),
                anchor_x='center',
                anchor_y='center'
            )

            # Coin display — use defeat preset's built-in coin bar and draw only the number
            coin_y = panel_y + panel_h * 0.48
            self._draw_outlined_text(
                f"{int(self.coins)}",
                self.width * 0.5,
                coin_y,
                font_size=int(44 * s),
                color=(1, 0.88, 0.2, 1),
                anchor_x='center',
                anchor_y='center',
                bold=True,
            )

            # Buttons — large and centered
            btn_scale = 2.25 * s
            retry_fallback = (self.width * 0.5 - 190 * s, panel_y + 130 * s, 380 * s, 106 * s)
            menu_fallback = (self.width * 0.5 - 190 * s, panel_y + 18 * s, 380 * s, 106 * s)
            retry_rect = self._draw_texture_centered(self.ui_textures.get("defeat_btn_retry"), self.width * 0.5, panel_y + 188 * s, btn_scale) or retry_fallback
            menu_rect = self._draw_texture_centered(self.ui_textures.get("victory_btn_menu") or self.ui_textures.get("pause_btn_menu"), self.width * 0.5, panel_y + 72 * s, btn_scale) or menu_fallback
            self.defeated_buttons.append({"action": "retry", "rect": retry_rect})
            self.defeated_buttons.append({"action": "menu", "rect": menu_rect})

    def _draw_victory_overlay(self):
        self.victory_buttons = []
        s = self.height / 1080.0 if self.height > 0 else 1.0
        hp_ratio = self.player.hp / self.player.max_hp if self.player.max_hp > 0 else 0.0
        stars = 3 if hp_ratio >= 0.66 else (2 if hp_ratio >= 0.33 else 1)
        with self.canvas:
            Color(0, 0, 0, 0.65)
            Rectangle(pos=(0, 0), size=self.size)

            # Panel — sized to fill nicely
            panel_w = self.width * 0.62
            panel_h = self.height * 0.68
            panel_x = (self.width - panel_w) / 2
            panel_y = self.height * 0.10
            Color(1, 1, 1, 1)
            Rectangle(texture=self.ui_textures.get("victory_preset"), pos=(panel_x, panel_y), size=(panel_w, panel_h))

            # Stars below the panel's built-in "VICTORY" header
            star_y = panel_y + panel_h - 160 * s
            for idx in range(stars):
                self._draw_texture_centered(self.ui_textures.get("victory_star"), self.width * 0.5 + (idx - (stars - 1) / 2) * 110 * s, star_y, 0.7 * s)

            # Stats text
            self._draw_outlined_text(
                f"Survived: {self._format_time(self.game_time)}   Kills: {self.kill_count}   Level: {self.player.level}",
                self.width * 0.5,
                star_y - 100 * s,
                font_size=int(42 * s),
                color=(0.95, 0.95, 1, 0.98),
                anchor_x='center',
                anchor_y='center'
            )

            # Separator line
            line_y = star_y - 160 * s
            Color(0.6, 0.58, 0.5, 0.4)
            Rectangle(pos=(panel_x + 40 * s, line_y), size=(panel_w - 80 * s, 2 * s))

            # Coin display — use preset's built-in coin bar/icon, draw only the number
            coin_y = panel_y + panel_h * 0.335
            self._draw_outlined_text(
                f"{int(self.coins)}",
                self.width * 0.5,
                coin_y,
                font_size=int(52 * s),
                color=(1, 0.88, 0.2, 1),
                anchor_x='center',
                anchor_y='center',
                bold=True,
            )

            # Buttons — side by side, large
            btn_scale = 2.1 * s
            btn_y = panel_y + 70 * s
            retry_fallback = (self.width * 0.5 - 260 * s, btn_y - 50 * s, 220 * s, 100 * s)
            menu_fallback = (self.width * 0.5 + 40 * s, btn_y - 50 * s, 220 * s, 100 * s)
            retry_rect = self._draw_texture_centered(self.ui_textures.get("victory_btn_ok"), self.width * 0.38, btn_y, btn_scale) or retry_fallback
            menu_rect = self._draw_texture_centered(self.ui_textures.get("victory_btn_menu"), self.width * 0.62, btn_y, btn_scale) or menu_fallback
            self.victory_buttons.append({"action": "retry", "rect": retry_rect})
            self.victory_buttons.append({"action": "menu", "rect": menu_rect})

    def _draw_settings_overlay(self):
        self.settings_buttons = []
        self.settings_sliders = {}
        s = self.height / 1080.0 if self.height > 0 else 1.0
        with self.canvas:
            Color(0, 0, 0, 0.5)
            Rectangle(pos=(0, 0), size=self.size)

            panel_w = self.width * 0.78
            panel_h = self.height * 0.76
            px = (self.width - panel_w) / 2
            py = (self.height - panel_h) / 2
            Color(1, 1, 1, 1)
            Rectangle(texture=self.ui_textures.get("settings_bg"), pos=(px, py), size=(panel_w, panel_h))
            pw, ph = panel_w, panel_h

            self._draw_outlined_text("SETTINGS", px + pw * 0.5, py + ph * 0.88, font_size=int(68 * s), color=(0.95, 0.95, 0.98, 1), anchor_x='center', anchor_y='center', bold=True)

            bar_bg_texture = self.ui_textures.get("settings_bar_bg")
            bar_fill_texture = self.ui_textures.get("settings_bar_fill")
            for key, label, y in [
                ("music_volume", "Music Volume", py + ph * 0.64),
                ("sfx_volume", "SFX Volume", py + ph * 0.48),
            ]:
                self._draw_texture_centered(self.ui_textures.get("settings_desc"), px + pw * 0.25, y, 0.95 * s, 0.95)
                self._draw_outlined_text(label, px + pw * 0.25, y, font_size=int(50 * s), color=(0.94, 0.94, 0.97, 1), anchor_x='center', anchor_y='center', bold=True)

                bw = pw * 0.44
                bh = max(26 * s, ph * 0.058)
                bx = px + pw * 0.47
                by = y - bh * 0.5

                if bar_bg_texture is not None:
                    self._draw_texture_fill_width(bar_bg_texture, bx, by, bw, bh)
                else:
                    Color(0.2, 0.2, 0.25, 0.9)
                    RoundedRectangle(pos=(bx, by), size=(bw, bh), radius=[8 * s])

                self._draw_texture_fill_width(bar_fill_texture, bx, by, bw * max(0.0, min(1.0, self.settings[key])), bh)
                self.settings_sliders[key] = (bx, by, bw, bh)

            # Fullscreen toggle (custom square for consistent size and visibility)
            toggle_size = 52 * s
            toggle_cx = px + pw * 0.50
            toggle_cy = py + ph * 0.30
            checkbox = (toggle_cx - toggle_size * 0.5, toggle_cy - toggle_size * 0.5, toggle_size, toggle_size)

            Color(0.12, 0.1, 0.06, 0.95)
            RoundedRectangle(pos=(checkbox[0], checkbox[1]), size=(checkbox[2], checkbox[3]), radius=[6 * s])
            Color(0.78, 0.62, 0.2, 0.95)
            Line(rounded_rectangle=(checkbox[0], checkbox[1], checkbox[2], checkbox[3], 6 * s), width=max(1.5, 2 * s))

            if self.settings["fullscreen"]:
                mark_tex = self.ui_textures.get("settings_mark")
                if mark_tex is not None:
                    self._draw_texture_centered(mark_tex, toggle_cx, toggle_cy, 0.82 * s)
                else:
                    Color(0.2, 0.9, 0.2, 1)
                    Line(points=[checkbox[0] + 12 * s, checkbox[1] + 25 * s, checkbox[0] + 22 * s, checkbox[1] + 13 * s, checkbox[0] + 40 * s, checkbox[1] + 37 * s], width=max(1.5, 2 * s))

            self._draw_outlined_text("Fullscreen", px + pw * 0.58, toggle_cy, font_size=int(46 * s), color=(0.94, 0.94, 0.97, 1), anchor_x='left', anchor_y='center', bold=True)
            self.settings_sliders["fullscreen_toggle"] = checkbox

            ok_fallback = (px + pw * 0.5 - 170 * s, py + ph * 0.12 - 45 * s, 340 * s, 90 * s)
            ok_rect = self._draw_texture_centered(self.ui_textures.get("settings_btn_ok"), px + pw * 0.5, py + ph * 0.12, 1.26 * s) or ok_fallback
            self.settings_buttons.append({"action": "ok", "rect": ok_rect})

    def _handle_settings_touch(self, x: float, y: float) -> bool:
        for key in ("music_volume", "sfx_volume"):
            if key not in self.settings_sliders:
                continue
            bx, by, bw, bh = self.settings_sliders[key]
            if bx <= x <= bx + bw and by <= y <= by + bh:
                self.settings[key] = max(0.0, min(1.0, (x - bx) / max(1.0, bw)))
                return True

        checkbox = self.settings_sliders.get("fullscreen_toggle")
        if checkbox is not None:
            bx, by, bw, bh = checkbox
            if bx <= x <= bx + bw and by <= y <= by + bh:
                self.settings["fullscreen"] = not self.settings["fullscreen"]
                return True
        return False

    def _draw_game_ui(self):
        """Main UI orchestrator — draws all HUD elements on canvas."""
        s = self.height / 1080.0 if self.height > 0 else 1.0
        # Low HP warning vignette
        if not self.player.is_dead and self.player.max_hp > 0:
            hp_ratio = self.player.hp / self.player.max_hp
            if hp_ratio < 0.3:
                pulse = 0.08 + 0.06 * math.sin(self.game_time * 5)
                Color(0.7, 0, 0, pulse)
                Rectangle(pos=(0, 0), size=self.size)
        self._draw_hud_panel(s)
        self._draw_timer_panel(s)
        self._draw_combat_info_panel(s)
        self._draw_ammo_panel(s)
        self._draw_skill_slots(s)

    def _draw_ammo_panel(self, s):
        """Draw the ammo counter prominently at the bottom right of the screen."""
        ammo = getattr(self.player, 'ammo', 30)
        max_ammo = getattr(self.player, 'max_ammo', 30)
        is_reloading = getattr(self.player, 'is_reloading', False)
        reload_timer = getattr(self.player, 'reload_timer', 0.0)
        has_infinite_ammo = self._has_ultimate_infinite_ammo()

        if has_infinite_ammo:
            ammo_text = f"Ammo: ∞  ({self.ultimate_infinite_ammo_timer:.1f}s)"
            ammo_color = (0.45, 0.95, 1.0, 1)
        elif is_reloading:
            ammo_text = f"RELOADING... {reload_timer:.1f}s"
            ammo_color = (0.9, 0.8, 0.2, 1)
        else:
            ammo_text = f"Ammo: {ammo}/{max_ammo}"
            ammo_color = (0.95, 0.95, 0.95, 1) if ammo > 0 else (0.9, 0.2, 0.2, 1)

        self._draw_outlined_text(
            ammo_text, self.width - 40 * s, 40 * s,
            font_size=int(32 * s), color=ammo_color,
            anchor_x='right', anchor_y='bottom', bold=True
        )

        # Draw Firing Mode
        mode = getattr(self.player, 'firing_mode', 'AUTO')
        mode_text = f"Mode: {mode}"
        self._draw_outlined_text(
            mode_text, self.width - 40 * s, 40 * s + 36 * s,
            font_size=int(22 * s), color=(0.8, 0.9, 1.0, 0.9),
            anchor_x='right', anchor_y='bottom', bold=True
        )

    def _draw_hud_panel(self, s):
        """Draw the player status HUD panel in the top-left corner."""
        pad = 16 * s
        panel_x = 16 * s
        panel_w = 400 * s
        panel_h = 150 * s
        panel_y = self.height - panel_h - 16 * s

        # Panel background
        Color(0.05, 0.05, 0.12, 0.75)
        RoundedRectangle(pos=(panel_x, panel_y), size=(panel_w, panel_h), radius=[12 * s])
        Color(0.45, 0.42, 0.55, 0.5)
        Line(rounded_rectangle=(panel_x, panel_y, panel_w, panel_h, 12 * s), width=1.5)

        # ── Level badge ──
        badge_x = panel_x + pad
        badge_y = panel_y + panel_h - 36 * s
        badge_r = 16 * s
        Color(0.85, 0.7, 0.15, 0.9)
        Ellipse(pos=(badge_x, badge_y), size=(badge_r * 2, badge_r * 2))
        self._draw_outlined_text(
            f"{self.player.level}", badge_x + badge_r, badge_y + badge_r,
            font_size=int(16 * s), color=(0.1, 0.05, 0, 1),
            anchor_x='center', anchor_y='center', bold=True
        )
        self._draw_outlined_text(
            f"LV {self.player.level}", badge_x + badge_r * 2 + 8 * s, badge_y + 6 * s,
            font_size=int(20 * s), color=(1, 0.92, 0.5, 1), bold=True
        )
        # Stat points indicator
        if self.player.stat_points > 0:
            self._draw_outlined_text(
                f"+{self.player.stat_points} SP", panel_x + panel_w - pad, badge_y + 6 * s,
                font_size=int(16 * s), color=(0.3, 1, 0.5, 1),
                anchor_x='right', bold=True
            )

        # ── HP Bar ──
        bar_x = panel_x + pad
        bar_w = panel_w - pad * 2
        bar_h = 22 * s
        hp_bar_y = panel_y + panel_h - 68 * s

        # HP heart icon (red circle)
        heart_size = 18 * s
        Color(0.9, 0.15, 0.15, 1)
        Ellipse(pos=(bar_x, hp_bar_y + (bar_h - heart_size) / 2), size=(heart_size, heart_size))
        hp_bar_x = bar_x + heart_size + 6 * s
        hp_bar_w = bar_w - heart_size - 6 * s

        # Bar background
        Color(0.2, 0.08, 0.08, 0.9)
        RoundedRectangle(pos=(hp_bar_x, hp_bar_y), size=(hp_bar_w, bar_h), radius=[4 * s])
        # Bar fill
        hp_ratio = max(0, min(1, self.player.hp / self.player.max_hp)) if self.player.max_hp > 0 else 0
        fill_w = hp_bar_w * hp_ratio
        if fill_w > 1:
            if hp_ratio > 0.5:
                Color(0.15, 0.78, 0.25, 0.95)
            elif hp_ratio > 0.25:
                Color(0.95, 0.75, 0.1, 0.95)
            else:
                Color(0.88, 0.12, 0.12, 0.95)
            RoundedRectangle(pos=(hp_bar_x, hp_bar_y), size=(fill_w, bar_h), radius=[4 * s])
        # HP text overlay
        self._draw_outlined_text(
            f"{int(self.player.hp)}/{int(self.player.max_hp)}",
            hp_bar_x + hp_bar_w / 2, hp_bar_y + bar_h / 2,
            font_size=int(14 * s), color=(1, 1, 1, 1),
            anchor_x='center', anchor_y='center', bold=True
        )

        # ── EXP Bar ──
        exp_bar_y = hp_bar_y - 18 * s
        exp_bar_h = 12 * s
        Color(0.08, 0.08, 0.18, 0.9)
        RoundedRectangle(pos=(bar_x, exp_bar_y), size=(bar_w, exp_bar_h), radius=[3 * s])
        exp_ratio = (self.player.exp / self.player.next_exp) if self.player.next_exp > 0 else 0
        exp_fill_w = bar_w * max(0, min(1, exp_ratio))
        if exp_fill_w > 1:
            Color(0.95, 0.8, 0.15, 0.9)
            RoundedRectangle(pos=(bar_x, exp_bar_y), size=(exp_fill_w, exp_bar_h), radius=[3 * s])
        self._draw_outlined_text(
            f"EXP {int(self.player.exp)}/{int(self.player.next_exp)}",
            bar_x + bar_w / 2, exp_bar_y + exp_bar_h / 2,
            font_size=int(11 * s), color=(1, 0.95, 0.7, 1),
            anchor_x='center', anchor_y='center'
        )

        # ── Stats line ──
        stats_y = exp_bar_y - 20 * s
        stats_text = (
            f"STR {self.player.str}  DEX {self.player.dex}  AGI {self.player.agi}  "
            f"INT {self.player.int}  VIT {self.player.vit}  LCK {self.player.luck}"
        )
        self._draw_outlined_text(
            stats_text, bar_x, stats_y,
            font_size=int(12 * s), color=(0.72, 0.72, 0.82, 0.85)
        )

        # ── Coin counter (below HUD panel) ──
        coin_y = panel_y - 12 * s
        money_icon_tex = self.ui_textures.get("money_icon")
        if money_icon_tex:
            icon_sz = 28 * s
            Color(1, 1, 1, 1)
            Rectangle(texture=money_icon_tex, pos=(panel_x + pad, coin_y - icon_sz), size=(icon_sz, icon_sz))
            self._draw_outlined_text(
                f"{self.coins}", panel_x + pad + icon_sz + 6 * s, coin_y - icon_sz * 0.5,
                font_size=int(18 * s), color=(1, 0.88, 0.2, 1),
                anchor_y='center', bold=True
            )
        else:
            self._draw_outlined_text(
                f"Coins: {self.coins}", panel_x + pad, coin_y - 14 * s,
                font_size=int(14 * s), color=(1, 0.88, 0.2, 1), bold=True
            )

        # ── Combat info line ──
        combat_y = stats_y - 18 * s
        combat_text = (
            f"DMG {self.player.bullet_damage:.1f}   "
            f"Rate {self.player.fire_rate:.2f}s   "
            f"Crit {self.player.crit_chance * 100:.0f}%"
        )
        self._draw_outlined_text(
            combat_text, bar_x, combat_y,
            font_size=int(11 * s), color=(0.6, 0.65, 0.72, 0.75)
        )

    def _draw_timer_panel(self, s):
        """Draw the styled timer panel at top center."""
        remaining = max(0, self.GAME_DURATION - self.game_time)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        timer_text = f"{minutes:02d}:{seconds:02d}"

        panel_w = 180 * s
        panel_h = 72 * s
        panel_x = (self.width - panel_w) / 2
        panel_y = self.height - panel_h - 12 * s

        # Panel background
        Color(0.05, 0.05, 0.12, 0.78)
        RoundedRectangle(pos=(panel_x, panel_y), size=(panel_w, panel_h), radius=[10 * s])
        # Border — color shifts with time
        if remaining > 300:
            Color(0.4, 0.4, 0.55, 0.6)
        elif remaining > 60:
            Color(0.9, 0.75, 0.15, 0.7)
        else:
            Color(0.9, 0.2, 0.15, 0.8)
        Line(rounded_rectangle=(panel_x, panel_y, panel_w, panel_h, 10 * s), width=1.5)

        # Timer text
        timer_color = (1, 1, 1, 1) if remaining > 60 else (1, 0.4, 0.3, 1)
        self._draw_outlined_text(
            timer_text, self.width / 2, panel_y + panel_h / 2 + 8 * s,
            font_size=int(34 * s), color=timer_color,
            anchor_x='center', anchor_y='center', bold=True
        )

        # Difficulty indicator
        progress = min(1.0, self.game_time / self.GAME_DURATION) if self.GAME_DURATION > 0 else 0
        diff_level = int(progress * 10) + 1
        diff_color = (
            min(1.0, 0.4 + progress * 0.6),
            max(0.3, 0.9 - progress * 0.6),
            0.2, 0.9
        )
        self._draw_outlined_text(
            f"Danger Lv.{diff_level}", self.width / 2, panel_y + 8 * s,
            font_size=int(12 * s), color=diff_color,
            anchor_x='center', anchor_y='bottom'
        )

    def _draw_combat_info_panel(self, s):
        """Draw kill counter and enemy count in the top-right corner."""
        panel_w = 190 * s
        panel_h = 85 * s
        panel_x = self.width - panel_w - 16 * s
        panel_y = self.height - panel_h - 16 * s
        pad = 14 * s

        Color(0.05, 0.05, 0.12, 0.75)
        RoundedRectangle(pos=(panel_x, panel_y), size=(panel_w, panel_h), radius=[10 * s])
        Color(0.5, 0.35, 0.35, 0.45)
        Line(rounded_rectangle=(panel_x, panel_y, panel_w, panel_h, 10 * s), width=1.2)

        # Kill count
        self._draw_outlined_text(
            f"Kills: {self.kill_count}", panel_x + pad, panel_y + panel_h - 28 * s,
            font_size=int(18 * s), color=(1, 0.85, 0.3, 1), bold=True
        )
        # Enemy count
        total_enemies = len(self.enemies) + len(self.special_enemies)
        self._draw_outlined_text(
            f"Enemies: {total_enemies}", panel_x + pad, panel_y + panel_h - 52 * s,
            font_size=int(14 * s), color=(0.9, 0.5, 0.4, 0.9)
        )
        # Orb count
        self._draw_outlined_text(
            f"Orbs: {len(self.exp_orbs)}", panel_x + pad, panel_y + panel_h - 72 * s,
            font_size=int(12 * s), color=(0.4, 0.95, 0.5, 0.8)
        )

        self._draw_outlined_text(
            f"Boss Orbs: {len(self.boss_orbs)}", panel_x + pad, panel_y + panel_h - 88 * s,
            font_size=int(11 * s), color=(0.78, 0.45, 1.0, 0.85)
        )

        self._draw_outlined_text(
            f"Passives: AS+ LS+ PR+", panel_x + pad, panel_y + panel_h - 90 * s,
            font_size=int(10 * s), color=(0.75, 0.85, 0.95, 0.75)
        )

    def _draw_skill_slots(self, s):
        """Draw centered bottom skill slots with cooldown overlay and countdown numbers."""
        slot_count = len(self.skill_slots)
        slot_w = 88 * s
        slot_h = 88 * s
        gap = 12 * s
        total_w = slot_count * slot_w + (slot_count - 1) * gap
        start_x = (self.width - total_w) / 2
        y = 18 * s

        for idx, slot in enumerate(self.skill_slots):
            x = start_x + idx * (slot_w + gap)
            skill_id = slot["skill_id"]

            Color(0.05, 0.06, 0.1, 0.86)
            RoundedRectangle(pos=(x, y), size=(slot_w, slot_h), radius=[10 * s])

            is_ready = self._is_skill_ready(skill_id)
            if is_ready:
                Color(0.35, 0.75, 0.45, 0.75)
            else:
                Color(0.75, 0.35, 0.35, 0.75)
            Line(rounded_rectangle=(x, y, slot_w, slot_h, 10 * s), width=1.8)

            self._draw_outlined_text(
                slot["bind"], x + 8 * s, y + slot_h - 22 * s,
                font_size=int(14 * s), color=(0.95, 0.95, 1, 0.95), bold=True
            )
            self._draw_outlined_text(
                slot["label"], x + slot_w / 2, y + 14 * s,
                font_size=int(11 * s), color=(0.8, 0.86, 0.95, 0.9),
                anchor_x='center', anchor_y='bottom'
            )

            remaining = self._get_skill_remaining(skill_id)
            if remaining > 0:
                cooldown = self._get_skill_cooldown(skill_id)
                ratio = max(0.0, min(1.0, remaining / cooldown)) if cooldown > 0 else 0.0
                overlay_h = slot_h * ratio
                Color(0.02, 0.03, 0.05, 0.72)
                Rectangle(pos=(x, y), size=(slot_w, overlay_h))
                if skill_id == "shockwave":
                    display_text = f"{int(math.ceil(remaining))}K"
                else:
                    display_text = f"{remaining:.1f}"
                self._draw_outlined_text(
                    display_text, x + slot_w / 2, y + slot_h / 2,
                    font_size=int(22 * s), color=(1, 0.95, 0.95, 0.95),
                    anchor_x='center', anchor_y='center', bold=True
                )

    def _update_debug(self, dt: float):
        fps = Clock.get_fps() or 0
        god_str = "  [GODMODE ON]" if self.god_mode else ""
        info = (
            f"FPS: {fps:.1f}{god_str}\n"
            f"Bullets: {len(self.bullets)}\n"
            f"Enemies: {len(self.enemies)}\n"
            f"Special Enemies: {len(self.special_enemies)}\n"
            f"Enemy Projectiles: {len(self.enemy_projectiles)}\n"
            f"EXP Orbs: {len(self.exp_orbs)}"
        )
        if self.debug_mode:
            active_statuses = getattr(self.player, 'status', None)
            status_text = "none"
            if active_statuses:
                status_dict = active_statuses.to_dict()
                if status_dict:
                    status_parts = []
                    for name, payload in status_dict.items():
                        status_parts.append(f"{name}({payload['duration']:.1f}s x{payload['stacks']})")
                    status_text = ", ".join(status_parts)

            info += (
                f"\nTime Speed: {self.time_speed_multiplier}x"
                f"\nBalance Preset: {self.balance_status_text}"
                f"\nSpawn Interval: {self.spawn_interval:.2f}s"
                f"\nEnemy Speed x: {self.enemy_speed_multiplier:.2f}"
                f"\nEXP Pull Radius: {self._get_exp_pull_radius():.0f}"
                f"\nPlayer LV:{self.player.level} EXP:{int(self.player.exp)}/{int(self.player.next_exp)} SP:{self.player.stat_points}"
                f"\nPlayer HP:{self.player.hp:.0f}/{self.player.max_hp:.0f} Ammo:{getattr(self.player, 'ammo', 0)}/{getattr(self.player, 'max_ammo', 30)} DMG:{self.player.bullet_damage:.1f}"
                f"\nULT Infinite Ammo: {self.ultimate_infinite_ammo_timer:.1f}s"
                f"\nUltimate Charge: {self.ultimate_kill_progress}/{self.ultimate_kills_required} kills"
                f"\nStats STR:{self.player.str} DEX:{self.player.dex} AGI:{self.player.agi} INT:{self.player.int} VIT:{self.player.vit} LUCK:{self.player.luck}"
                f"\nStatus Effects: {status_text}"
            )
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
        bullet = BulletEntity(spawn_pos, shot_direction)
        is_crit = random.random() < self.player.crit_chance
        bullet.damage = self.player.bullet_damage * (1.75 if is_crit else 1.0)
        bullet.is_crit = is_crit
        self.bullets.append(bullet)

    def _grant_player_exp(self, amount: int):
        levels_gained = self.player.add_experience(amount)
        if levels_gained <= 0:
            return

        self.pending_levelups += levels_gained
        self._sync_combat_from_player()
        if not self.levelup_active:
            self._open_next_levelup()

    def _open_next_levelup(self):
        if self.pending_levelups <= 0:
            self.levelup_active = False
            self.levelup_choices = []
            return

        self.pending_levelups -= 1
        self.levelup_active = True
        choice_pool = ["str", "dex", "agi", "int", "vit", "luck"]
        self.levelup_choices = random.sample(choice_pool, 3)

        self.player.stop_shooting()
        self.firing = False

    def _drop_exp_orbs(self, enemy, total_exp: int):
        if total_exp <= 0:
            return

        hitbox = enemy.get_hitbox()
        center = Vector(hitbox[0] + hitbox[2] / 2, hitbox[1] + hitbox[3] / 2)

        chunk_size = 12
        orb_count = max(1, min(8, math.ceil(total_exp / chunk_size)))
        remaining = total_exp
        for idx in range(orb_count):
            orb_value = chunk_size if idx < orb_count - 1 else max(1, remaining)
            remaining -= orb_value

            offset = Vector(random.uniform(-24, 24), random.uniform(-18, 18))
            self.exp_orbs.append(ExpOrb(center + offset, orb_value))

    def _handle_enemy_kill(self, enemy):
        self.kill_count += 1
        self._add_ultimate_kill_progress(1)

        if isinstance(enemy, SpecialEnemyEntity):
            self.coins += 10
        else:
            self.coins += 1

        self._drop_exp_orbs(enemy, self._get_enemy_exp_reward(enemy))
        if isinstance(enemy, SpecialEnemyEntity):
            self._drop_boss_orb(enemy)
        self._maybe_drop_health_orb(enemy)

    def _maybe_drop_health_orb(self, enemy):
        base_chance = self.health_orb_special_drop_chance if isinstance(enemy, SpecialEnemyEntity) else self.health_orb_drop_chance
        luck_multiplier = max(0.0, getattr(self.player, "loot_drop_multiplier", 1.0))
        final_chance = min(0.60, base_chance * luck_multiplier)
        if random.random() > final_chance:
            return

        hitbox = enemy.get_hitbox()
        center = Vector(hitbox[0] + hitbox[2] / 2, hitbox[1] + hitbox[3] / 2)
        offset = Vector(random.uniform(-20, 20), random.uniform(-14, 14))
        self.health_orbs.append(
            HealthOrb(
                center + offset,
                heal_ratio=self.health_orb_heal_ratio,
                lifetime=self.health_orb_lifetime,
            )
        )

    def _apply_levelup_choice(self, choice_index: int):
        if not self.levelup_active:
            return
        if choice_index < 0 or choice_index >= len(self.levelup_choices):
            return

        chosen_stat = self.levelup_choices[choice_index]
        if self.player.allocate_stat(chosen_stat):
            self._sync_combat_from_player()

        if self.pending_levelups > 0:
            self._open_next_levelup()
        else:
            self.levelup_active = False
            self.levelup_choices = []

    def _draw_levelup_overlay(self):
        """Draw an enhanced level-up selection overlay with card UI."""
        s = self.height / 1080.0 if self.height > 0 else 1.0

        # Full-screen dark overlay
        Color(0, 0, 0, 0.6)
        Rectangle(pos=(0, 0), size=self.size)

        # Central panel
        panel_w = self.width * 0.55
        panel_h = self.height * 0.52
        panel_x = (self.width - panel_w) / 2
        panel_y = (self.height - panel_h) / 2

        # Panel background layers
        Color(0.08, 0.07, 0.14, 0.95)
        RoundedRectangle(pos=(panel_x, panel_y), size=(panel_w, panel_h), radius=[20 * s])
        inner_pad = 4 * s
        Color(0.12, 0.11, 0.2, 0.9)
        RoundedRectangle(
            pos=(panel_x + inner_pad, panel_y + inner_pad),
            size=(panel_w - inner_pad * 2, panel_h - inner_pad * 2),
            radius=[16 * s]
        )
        # Golden border
        Color(0.85, 0.7, 0.2, 0.8)
        Line(rounded_rectangle=(panel_x, panel_y, panel_w, panel_h, 20 * s), width=2.5)

        # Title
        title_y = panel_y + panel_h - 55 * s
        self._draw_outlined_text(
            "LEVEL UP!", self.width / 2, title_y,
            font_size=int(42 * s), color=(1, 0.9, 0.3, 1),
            anchor_x='center', anchor_y='center', bold=True
        )

        # Subtitle
        subtitle_y = title_y - 35 * s
        remaining_text = f"({self.pending_levelups} more)" if self.pending_levelups > 0 else ""
        self._draw_outlined_text(
            f"Choose your upgrade  {remaining_text}", self.width / 2, subtitle_y,
            font_size=int(20 * s), color=(0.85, 0.85, 0.9, 0.9),
            anchor_x='center', anchor_y='center'
        )

        # Separator line
        sep_y = subtitle_y - 20 * s
        Color(0.5, 0.45, 0.6, 0.4)
        Line(points=[panel_x + 40 * s, sep_y, panel_x + panel_w - 40 * s, sep_y], width=1)

        # Option cards
        stat_descriptions = {
            "str": ("STR", "+1", "Bullet Damage +", (0.95, 0.35, 0.3, 1)),
            "dex": ("DEX", "+1", "Fire Rate +", (0.3, 0.85, 0.95, 1)),
            "agi": ("AGI", "+1", "Move Speed +", (0.3, 0.95, 0.45, 1)),
            "int": ("INT", "+1", "Skill Cooldown -", (0.6, 0.4, 0.95, 1)),
            "vit": ("VIT", "+1", "Max HP +", (0.95, 0.55, 0.7, 1)),
            "luck": ("LUCK", "+1", "Crit & Drop +", (0.95, 0.85, 0.2, 1)),
        }

        card_count = len(self.levelup_choices)
        card_spacing = 24 * s
        total_card_width = panel_w - 80 * s
        card_w = (total_card_width - card_spacing * (card_count - 1)) / max(1, card_count)
        card_h = panel_h * 0.48
        card_start_x = panel_x + 40 * s
        card_y = panel_y + 30 * s

        for idx, stat_key in enumerate(self.levelup_choices):
            cx = card_start_x + idx * (card_w + card_spacing)
            stat_name, bonus, desc, accent = stat_descriptions.get(
                stat_key, (stat_key.upper(), "+1", "", (1, 1, 1, 1))
            )

            # Card background
            Color(0.1, 0.1, 0.18, 0.92)
            RoundedRectangle(pos=(cx, card_y), size=(card_w, card_h), radius=[12 * s])
            # Card border
            Color(*accent[:3], 0.6)
            Line(rounded_rectangle=(cx, card_y, card_w, card_h, 12 * s), width=1.8)

            # Key number hint
            key_y = card_y + card_h - 35 * s
            Color(*accent[:3], 0.15)
            Ellipse(pos=(cx + card_w / 2 - 18 * s, key_y - 4 * s), size=(36 * s, 36 * s))
            self._draw_outlined_text(
                f"{idx + 1}", cx + card_w / 2, key_y + 14 * s,
                font_size=int(22 * s), color=accent,
                anchor_x='center', anchor_y='center', bold=True
            )

            # Stat name
            self._draw_outlined_text(
                stat_name, cx + card_w / 2, key_y - 40 * s,
                font_size=int(28 * s), color=accent,
                anchor_x='center', anchor_y='center', bold=True
            )

            # Bonus text
            self._draw_outlined_text(
                bonus, cx + card_w / 2, key_y - 72 * s,
                font_size=int(20 * s), color=(0.9, 0.9, 0.9, 0.9),
                anchor_x='center', anchor_y='center'
            )

            # Description
            self._draw_outlined_text(
                desc, cx + card_w / 2, key_y - 102 * s,
                font_size=int(14 * s), color=(0.7, 0.7, 0.75, 0.8),
                anchor_x='center', anchor_y='center'
            )

            # Current value
            current_val = getattr(self.player, stat_key, 0)
            self._draw_outlined_text(
                f"Current: {current_val}", cx + card_w / 2, card_y + 20 * s,
                font_size=int(13 * s), color=(0.6, 0.6, 0.65, 0.7),
                anchor_x='center', anchor_y='bottom'
            )

        # Bottom hint
        self._draw_outlined_text(
            "Click or Press  1  /  2  /  3  to select", self.width / 2, panel_y + 8 * s,
            font_size=int(16 * s), color=(0.7, 0.7, 0.75, 0.7),
            anchor_x='center', anchor_y='bottom'
        )

    def _draw_boss_upgrade_overlay(self):
        """Boss reward selection overlay (powerful x1.5 upgrade choice)."""
        s = self.height / 1080.0 if self.height > 0 else 1.0

        Color(0, 0, 0, 0.68)
        Rectangle(pos=(0, 0), size=self.size)

        panel_w = self.width * 0.55
        panel_h = self.height * 0.52
        panel_x = (self.width - panel_w) / 2
        panel_y = (self.height - panel_h) / 2

        Color(0.11, 0.06, 0.18, 0.96)
        RoundedRectangle(pos=(panel_x, panel_y), size=(panel_w, panel_h), radius=[20 * s])
        Color(0.72, 0.4, 1.0, 0.8)
        Line(rounded_rectangle=(panel_x, panel_y, panel_w, panel_h, 20 * s), width=2.5)

        title_y = panel_y + panel_h - 55 * s
        self._draw_outlined_text(
            "BOSS REWARD", self.width / 2, title_y,
            font_size=int(40 * s), color=(0.92, 0.74, 1, 1),
            anchor_x='center', anchor_y='center', bold=True
        )
        self._draw_outlined_text(
            "Choose one upgrade (x1.5)", self.width / 2, title_y - 34 * s,
            font_size=int(18 * s), color=(0.86, 0.86, 0.95, 0.95),
            anchor_x='center', anchor_y='center'
        )

        card_count = len(self.boss_upgrade_choices)
        card_spacing = 24 * s
        total_card_width = panel_w - 80 * s
        card_w = (total_card_width - card_spacing * (card_count - 1)) / max(1, card_count)
        card_h = panel_h * 0.48
        card_start_x = panel_x + 40 * s
        card_y = panel_y + 30 * s

        accent_map = {
            "speed": (0.35, 0.95, 0.45, 1),
            "hp": (0.95, 0.35, 0.42, 1),
            "skill_cooldown": (0.42, 0.75, 1.0, 1),
            "radius": (0.85, 0.55, 1.0, 1),
        }

        for idx, key in enumerate(self.boss_upgrade_choices):
            cx = card_start_x + idx * (card_w + card_spacing)
            accent = accent_map.get(key, (1, 1, 1, 1))
            label = self.boss_upgrade_labels.get(key, key)

            Color(0.12, 0.1, 0.2, 0.95)
            RoundedRectangle(pos=(cx, card_y), size=(card_w, card_h), radius=[12 * s])
            Color(*accent[:3], 0.75)
            Line(rounded_rectangle=(cx, card_y, card_w, card_h, 12 * s), width=1.8)

            self._draw_outlined_text(
                f"{idx + 1}", cx + card_w / 2, card_y + card_h - 26 * s,
                font_size=int(22 * s), color=accent,
                anchor_x='center', anchor_y='center', bold=True
            )
            self._draw_outlined_text(
                label, cx + card_w / 2, card_y + card_h / 2,
                font_size=int(22 * s), color=accent,
                anchor_x='center', anchor_y='center', bold=True
            )

        self._draw_outlined_text(
            "Click card or press 1 / 2 / 3", self.width / 2, panel_y + 10 * s,
            font_size=int(16 * s), color=(0.82, 0.82, 0.9, 0.75),
            anchor_x='center', anchor_y='bottom'
        )

    def _get_enemy_exp_reward(self, enemy) -> int:
        if isinstance(enemy, SpecialEnemyEntity):
            return 80

        asset_path = getattr(enemy, "asset_path", "")
        if "Zombie_1" in asset_path:
            return 18
        if "Zombie_2" in asset_path:
            return 28
        if "Zombie_3" in asset_path:
            return 16
        if "Zombie_4" in asset_path:
            return 24
        return 20

    def _sync_combat_from_player(self):
        self.bullet_damage = self.player.bullet_damage
        self.fire_rate = self.player.fire_rate

        # Re-apply persistent boss multipliers on top of recalculated base stats
        base_walk_speed = self.player.base_walk_speed + (self.player.agi - 1) * 8
        base_run_speed = self.player.base_run_speed + (self.player.agi - 1) * 10
        self.player.speed = base_walk_speed * self.boss_move_speed_mult
        self.player.run_speed = base_run_speed * self.boss_move_speed_mult

        base_max_hp = self.player.base_max_hp + (self.player.vit - 1) * 18
        hp_ratio = self.player.hp / self.player.max_hp if self.player.max_hp > 0 else 1.0
        self.player.max_hp = base_max_hp * self.boss_hp_mult
        self.player.hp = max(1.0, min(self.player.max_hp, self.player.max_hp * hp_ratio))

    def _resume_auto_fire_if_holding(self):
        """Resume AUTO fire when reload finishes while left mouse is still held."""
        if not self.left_mouse_held or self.levelup_active or self.player.is_dead:
            return

        mode = getattr(self.player, 'firing_mode', 'AUTO')
        if mode != 'AUTO':
            return

        if self.firing:
            return

        has_infinite_ammo = self._has_ultimate_infinite_ammo()

        if getattr(self.player, 'is_reloading', False) and not has_infinite_ammo:
            return

        if getattr(self.player, 'ammo', 0) <= 0 and not has_infinite_ammo:
            if hasattr(self.player, 'start_reload'):
                self.player.start_reload()
            return

        self.firing = True
        self.player.start_shooting()

    def _get_effective_fire_rate(self) -> float:
        return max(0.045, self.fire_rate * self.passive_attack_speed_mult)

    def _apply_lifesteal(self, damage_dealt: float):
        if damage_dealt <= 0 or self.player.is_dead:
            return
        heal_amount = damage_dealt * self.passive_lifesteal
        self.player.hp = min(self.player.max_hp, self.player.hp + heal_amount)

    def _load_sequential_textures(self, base_path: str, prefix: str, max_frames: int = 20) -> List:
        textures = []
        for idx in range(1, max_frames + 1):
            path = f"{base_path}/{prefix}{idx}.png"
            try:
                tex = CoreImage(path).texture
                textures.append(tex)
            except Exception:
                if idx > 1:
                    break
        return textures

    def _can_player_take_damage(self) -> bool:
        return (not self.god_mode) and self.dodge_iframe_timer <= 0

    def _update_dodge_timers(self, dt: float):
        if self.dodge_timer > 0:
            self.dodge_timer = max(0.0, self.dodge_timer - dt)
        if self.dodge_iframe_timer > 0:
            self.dodge_iframe_timer = max(0.0, self.dodge_iframe_timer - dt)

    def _update_dodge_state(self, dt: float):
        if self.dodge_timer <= 0:
            return

        dash_speed = self.dodge_distance / max(0.001, self.dodge_duration)
        self.player.pos += self.dodge_direction * (dash_speed * dt)
        self._clamp_player_to_bounds()

        if self.dodge_direction.x != 0:
            self.player.facing = 1 if self.dodge_direction.x > 0 else -1
        if "run" in self.player.animations:
            self.player.current_anim = "run"
            run_frames = self.player.animations.get("run", [])
            if run_frames:
                self.player.current_frame = self.player.current_frame % len(run_frames)
                self.player.frame_timer += dt
                if self.player.frame_timer >= self.player.animation_speed:
                    self.player.frame_timer = 0.0
                    self.player.current_frame = (self.player.current_frame + 1) % len(run_frames)

    def _clamp_player_to_bounds(self):
        max_x = max(0, self.width - self.player.size[0])
        block_unit = self.height / 10.0
        min_y = block_unit
        max_y = self.height - (3 * block_unit) - self.player.size[1]
        self.player.pos.x = max(0, min(self.player.pos.x, max_x))
        self.player.pos.y = max(min_y, min(self.player.pos.y, max(min_y, max_y)))

    def _update_skill_cooldowns(self, dt: float):
        for skill_id, payload in self.skill_cooldowns.items():
            if skill_id == "shockwave":
                continue
            if payload["remaining"] > 0:
                payload["remaining"] = max(0.0, payload["remaining"] - dt)

    def _add_ultimate_kill_progress(self, amount: int = 1):
        if amount <= 0:
            return
        self.ultimate_kill_progress = min(
            self.ultimate_kills_required,
            self.ultimate_kill_progress + amount,
        )

    def _get_ultimate_kills_remaining(self) -> int:
        return max(0, self.ultimate_kills_required - self.ultimate_kill_progress)

    def _is_ultimate_ready(self) -> bool:
        return self._get_ultimate_kills_remaining() <= 0

    def _has_ultimate_infinite_ammo(self) -> bool:
        return self.ultimate_infinite_ammo_timer > 0.0

    def _get_skill_cooldown(self, skill_id: str) -> float:
        if skill_id == "shockwave":
            return float(max(1, self.ultimate_kills_required))
        payload = self.skill_cooldowns.get(skill_id)
        if payload is None:
            return 0.0
        return payload["base"] * self.player.skill_cooldown_multiplier * self.boss_skill_cdr_mult

    def _get_skill_remaining(self, skill_id: str) -> float:
        if skill_id == "shockwave":
            return float(self._get_ultimate_kills_remaining())
        payload = self.skill_cooldowns.get(skill_id)
        if payload is None:
            return 0.0
        return payload["remaining"]

    def _is_skill_ready(self, skill_id: str) -> bool:
        if skill_id == "shockwave":
            return self._is_ultimate_ready()
        return self._get_skill_remaining(skill_id) <= 0.0

    def _start_skill_cooldown(self, skill_id: str):
        if skill_id == "shockwave":
            self.ultimate_kill_progress = 0
            return
        payload = self.skill_cooldowns.get(skill_id)
        if payload is None:
            return
        payload["remaining"] = self._get_skill_cooldown(skill_id)

    def _use_skill_from_key(self, key: str):
        skill_id = self.skill_key_to_skill.get(key)
        if skill_id is None:
            return

        if not self._is_skill_ready(skill_id):
            return

        used = False
        if skill_id == "dodge":
            used = self._cast_dodge()
        elif skill_id == "grenade":
            used = self._cast_grenade()
        elif skill_id == "shockwave":
            used = self._cast_shockwave()

        if used:
            self._start_skill_cooldown(skill_id)

    def _cast_dodge(self) -> bool:
        move_vec = Vector(0, 0)
        if "w" in self.pressed_keys:
            move_vec += Vector(0, 1)
        if "s" in self.pressed_keys:
            move_vec += Vector(0, -1)
        if "a" in self.pressed_keys:
            move_vec += Vector(-1, 0)
        if "d" in self.pressed_keys:
            move_vec += Vector(1, 0)

        if move_vec.length() <= 0:
            move_vec = Vector(self.player.facing, 0)

        self.dodge_direction = move_vec.normalize()
        self.dodge_distance = 180.0 + (self.player.agi * 5.0)
        self.dodge_timer = self.dodge_duration
        self.dodge_iframe_timer = self.dodge_duration + 0.08

        self.player.stop_shooting()
        if "run" in self.player.animations:
            self.player.current_anim = "run"
            run_frames = self.player.animations.get("run", [])
            if run_frames:
                self.player.current_frame = self.player.current_frame % len(run_frames)
            self.player.frame_timer = 0.0
        return True

    def _cast_grenade(self) -> bool:
        mx, my = Window.mouse_pos
        target = Vector(*self.to_widget(mx, my))
        pbox = self.player.get_hitbox()
        start = Vector(pbox[0] + pbox[2] / 2, pbox[1] + pbox[3] / 2)

        damage = self.grenade_damage_base + (self.player.str * self.grenade_damage_str_scale)
        blast_radius = (self.grenade_radius_base + (self.player.int * self.grenade_radius_int_scale)) * self.boss_grenade_radius_mult
        self.grenades.append(
            GrenadeEntity(
                start,
                target,
                damage=damage,
                blast_radius=blast_radius,
                textures=self.grenade_throw_textures,
                visual_scale=self.grenade_visual_scale,
                min_contact_time=self.grenade_contact_arm_time,
                fuse_min_time=self.grenade_fuse_min_time,
                fuse_max_time=self.grenade_fuse_max_time,
                fuse_offset=self.grenade_fuse_offset,
            )
        )
        return True

    def _open_next_boss_upgrade(self):
        if self.pending_boss_upgrades <= 0:
            self.boss_upgrade_active = False
            self.boss_upgrade_choices = []
            return

        self.pending_boss_upgrades -= 1
        self.boss_upgrade_active = True
        pool = ["speed", "hp", "skill_cooldown", "radius"]
        self.boss_upgrade_choices = random.sample(pool, 3)

        self.player.stop_shooting()
        self.firing = False
        self.left_mouse_held = False

    def _apply_boss_upgrade_choice(self, choice_index: int):
        if not self.boss_upgrade_active:
            return
        if choice_index < 0 or choice_index >= len(self.boss_upgrade_choices):
            return

        selected = self.boss_upgrade_choices[choice_index]
        if selected == "speed":
            self.boss_move_speed_mult *= 1.5
        elif selected == "hp":
            self.boss_hp_mult *= 1.5
        elif selected == "skill_cooldown":
            self.boss_skill_cdr_mult = max(0.05, self.boss_skill_cdr_mult / 1.5)
        elif selected == "radius":
            self.boss_grenade_radius_mult *= 1.5

        self._sync_combat_from_player()

        if self.pending_boss_upgrades > 0:
            self._open_next_boss_upgrade()
        else:
            self.boss_upgrade_active = False
            self.boss_upgrade_choices = []

    def _cast_shockwave(self) -> bool:
        center = Vector(self.player.pos.x + self.player.size[0] / 2, self.player.pos.y + self.player.size[1] / 2)
        visual_radius = 185.0 + (self.player.int * 6.0)

        self.ultimate_infinite_ammo_timer = self.ultimate_infinite_ammo_duration
        self.player.is_reloading = False
        self.player.reload_timer = 0.0
        self.player.ammo = self.player.max_ammo

        self.explosion_effects.append(
            ExplosionEffect(
                center,
                textures=self.grenade_explosion_textures,
                size=max(170.0, visual_radius * 1.8),
                y_lift_ratio=0.45,
            )
        )

        return True

    def _grenade_hits_enemy(self, grenade: GrenadeEntity) -> bool:
        if grenade.age < grenade.min_contact_time:
            return False

        grenade_box = grenade.get_hitbox()
        for enemy in self.enemies:
            if enemy.is_dying:
                continue
            if self._rects_intersect(grenade_box, self._inflate_rect(enemy.get_hitbox(), 4.0)):
                return True

        for enemy in self.special_enemies:
            if enemy.is_dying:
                continue
            if self._rects_intersect(grenade_box, self._inflate_rect(enemy.get_hitbox(), 4.0)):
                return True

        return False

    def _explode_grenade(self, grenade: GrenadeEntity):
        blast_center = grenade.pos

        effect_size = max(120.0, grenade.blast_radius * 1.9) * self.grenade_explosion_visual_scale
        self.explosion_effects.append(
            ExplosionEffect(
                blast_center,
                textures=self.grenade_explosion_textures,
                size=effect_size,
                y_lift_ratio=0.45,
            )
        )

        for enemy in self.enemies[:]:
            if enemy.is_dying:
                continue
            ebox = enemy.get_hitbox()
            center = Vector(ebox[0] + ebox[2] / 2, ebox[1] + ebox[3] / 2)
            if (center - blast_center).length() <= grenade.blast_radius:
                enemy_died = enemy.take_damage(grenade.damage)
                self._apply_lifesteal(grenade.damage)
                if enemy_died:
                    self._handle_enemy_kill(enemy)

        for enemy in self.special_enemies[:]:
            if enemy.is_dying:
                continue
            ebox = enemy.get_hitbox()
            center = Vector(ebox[0] + ebox[2] / 2, ebox[1] + ebox[3] / 2)
            if (center - blast_center).length() <= grenade.blast_radius:
                enemy_died = enemy.take_damage(grenade.damage)
                self._apply_lifesteal(grenade.damage)
                if enemy_died:
                    self._handle_enemy_kill(enemy)

    def _drop_boss_orb(self, enemy):
        hitbox = enemy.get_hitbox()
        center = Vector(hitbox[0] + hitbox[2] / 2, hitbox[1] + hitbox[3] / 2)
        offset = Vector(random.uniform(-18, 18), random.uniform(-12, 12))
        self.boss_orbs.append(BossOrb(center + offset))

    def _update_progression_hud(self):
        """Progression HUD is now drawn on canvas in _draw_hud_panel. Keep label cleared."""
        self.progression_label.text = ""

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
        special_index = len(self.special_enemies) + 1
        if special_index > 3:
            special_index = 3
        self.special_enemies.append(SpecialEnemyEntity(
            pos=Vector(x_pos, y_pos),
            player_size=self.player.size,
            asset_path=selected,
            special_index=special_index
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

        special_index = len(self.special_enemies) + 1
        if special_index > 3:
            special_index = 3
        self.special_enemies.append(SpecialEnemyEntity(
            pos=Vector(x_pos, y_pos),
            player_size=self.player.size,
            asset_path=enemy_type,
            special_index=special_index
        ))
        self.enemy_spawn_counter += 1
        self.special_enemies[-1].spawn_order = self.enemy_spawn_counter

    def _get_exp_pull_radius(self) -> float:
        base = 150.0 + (self.player.luck * 14.0) + (self.player.int * 8.0)
        return base

    def on_size(self, *args):
        if not self._did_initial_player_center and self.width > 0 and self.height > 0:
            self._spawn_player_at_screen_center()
            self._did_initial_player_center = True
        self.player.update(0, set(), (self.width, self.height))