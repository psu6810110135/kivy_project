# Copilot Instructions — Kivy 2.5D Shooter

## Architecture Overview

Kivy-based 2.5D side-scrolling horde-survival shooter (wave-based, roguelite). Runs at 60 FPS via `Clock.schedule_interval` in a single `GameWidget` that owns the entire game loop.

### Module Responsibilities

| Module                   | Role                                                                                     |
| ------------------------ | ---------------------------------------------------------------------------------------- |
| `main.py`                | App entry point; sets 1920×1080 window, creates `GameWidget`                             |
| `game.py`                | **Central game loop** — input, spawning, collision, rendering, debug mode                |
| `entity_base.py`         | `Entity` dataclass — pos (`Vector`), size, color, status hooks                           |
| `status_system.py`       | `StatusComponent` / `StatusEffect` — timed buff/debuff with multiplier modifiers         |
| `player_entity.py`       | `PlayerEntity` — sprite animation, WASD movement, shooting state machine                 |
| `enemy_entities.py`      | `EnemyEntity` (4 zombie variants) + `SpecialEnemyEntity` (3 boss types) with per-type AI |
| `projectile_entities.py` | `BulletEntity` (player) + `EnemyProjectileEntity` (Kitsune fire)                         |
| `entities.py`            | **Re-export facade** — all entity imports go through this file                           |

## Entity Pattern

- All entities inherit `Entity` dataclass from `entity_base.py`.
- Required interface: `draw(canvas)`, `get_hitbox() -> (x, y, w, h)`, call `self.update_statuses(dt)` in `update()`.
- Hitboxes use a **shrink_scale** (0.8–0.82) on pixel-based bounding boxes.
- Sprite flipping: `PushMatrix/Scale(x=-1)/PopMatrix`. `facing` is `1` (right) or `-1` (left).
- Textures **preloaded at startup** via class-level `_texture_cache` / `_bbox_cache`.

## Enemy Stat System (`SKIN_STATS`)

Each enemy type has unique combat stats defined in `SKIN_STATS` class dict mapped by asset path.

### Regular Enemies (`EnemyEntity`)

| Zombie   | Role          | HP  | Speed | Damage | Atk Anim Speed |
| -------- | ------------- | --- | ----- | ------ | -------------- |
| Zombie_1 | Normal        | 50  | 120   | 10     | 0.10           |
| Zombie_2 | Tank          | 100 | 80    | 8      | 0.12           |
| Zombie_3 | Fast Attacker | 35  | 150   | 6      | 0.06           |
| Zombie_4 | Heavy Hitter  | 60  | 90    | 18     | 0.15           |

### Special Enemies / Bosses (`SpecialEnemyEntity`)

| Boss         | Role          | HP  | Speed | Damage | Atk Anim | Special                                                                     |
| ------------ | ------------- | --- | ----- | ------ | -------- | --------------------------------------------------------------------------- |
| Kitsune      | Ranged mage   | 300 | 140   | 25     | 0.12     | Fire projectiles, keeps distance (escape 300px, range 600px, cooldown 2.5s) |
| Red_Werewolf | Berserker     | 400 | 200   | 12     | 0.06     | Fast melee strikes, lighter damage per hit                                  |
| Gorgon       | Heavy charger | 500 | 120   | 35     | 0.18     | Massive damage but slow charge animation                                    |

To add/tune: edit `SKIN_STATS` dicts in `enemy_entities.py`. Keys: `max_hp`, `speed`, `damage`, `attack_anim_speed`, `attack_enter_dist`, `attack_exit_dist`.

## Walkable Y Band

All entities (player + enemies) are clamped to the same vertical band:

```python
block_unit = height / 10.0
min_y = block_unit
max_y = height - (3 * block_unit) - entity.size[1]
```

Enemies are clamped in their `update()` AND again after separation in `GameWidget.update()`.

## Rendering

- **No Kivy widgets per entity** — direct `canvas` drawing with Kivy graphics instructions.
- Z-order: sorted by danger priority → Y position (lower Y = in front) → spawn order.
- Canvas cleared and redrawn every frame in `_draw_scene()`.

## Enemy Separation

Spatial-grid soft repulsion in `_separate_enemies()`. Per-enemy `separation_radius`:

- Regular enemies: `min(size) * 0.45`
- Special enemies: `min(size) * 0.50`
- `soft_factor = 0.85` controls push strength

## Debug Mode (press `9`)

- `+`/`=` — spawn enemy | `1`/`2`/`3` — spawn Gorgon/Kitsune/Wolf
- `-` — cycle time speed (1×→60×)
- Shows hitbox outlines, path lines, FPS

## Running

```bash
pip install kivy
python main.py
```

## Adding New Content

### New Enemy Type

1. Add sprite folder under `game_picture/enemy/` or `game_picture/special_enemy/`.
2. For basic enemies: add path to `EnemyEntity.SKINS` list and call `preload_all_skins()`.
3. For special enemies: add to `SpecialEnemyEntity.SKINS` + `ANIMATION_FRAMES` dict with per-animation frame counts, then add AI logic in the `update()` method.

### New Status Effect

1. Define modifiers dict: `{"move_speed": 0.5, "damage": 1.5}`.
2. Apply: `entity.add_status("slow", duration=3.0, modifiers={"move_speed": 0.5})`.
3. Consume in update: `speed *= self.get_status_multiplier("move_speed")`.
