# Copilot Instructions — Kivy 2.5D Shooter

## Architecture Overview

This is a **Kivy-based 2.5D side-scrolling horde-survival shooter** (wave-based, roguelite). The game runs at 60 FPS via `Clock.schedule_interval` in a single `GameWidget` that owns the entire game loop.

### Module Responsibilities

| Module                   | Role                                                                                                 |
| ------------------------ | ---------------------------------------------------------------------------------------------------- |
| `main.py`                | App entry point; sets 1920×1080 window, creates `GameWidget`                                         |
| `game.py`                | **Central game loop** — input, spawning, collision, rendering, debug mode. All game state lives here |
| `entity_base.py`         | `Entity` dataclass — pos (`Vector`), size, color, status hooks                                       |
| `status_system.py`       | `StatusComponent` / `StatusEffect` — timed buff/debuff system with multiplier modifiers              |
| `player_entity.py`       | `PlayerEntity` — sprite animation, WASD movement, shooting state machine                             |
| `enemy_entities.py`      | `EnemyEntity` (zombies) + `SpecialEnemyEntity` (Gorgon/Kitsune/Red_Werewolf) with per-type AI        |
| `projectile_entities.py` | `BulletEntity` (player) + `EnemyProjectileEntity` (Kitsune fire)                                     |
| `entities.py`            | **Re-export facade** — all entity imports should go through this file for compatibility              |

### Data Flow

```
GameWidget.update(dt)
  ├── PlayerEntity.update(dt, keys, bounds) → animation frame
  ├── EnemyEntity.update(dt, player_pos, bounds) → movement toward player
  ├── SpecialEnemyEntity.update(...) → may return EnemyProjectileEntity (Kitsune)
  ├── BulletEntity.update(dt) → linear movement
  ├── Collision check (AABB via _rects_intersect)
  ├── _separate_enemies() → spatial-grid soft repulsion
  └── _draw_scene() → canvas.clear() + Z-sorted render
```

## Key Conventions

### Entity Pattern

- All entities inherit from the `Entity` dataclass in `entity_base.py`.
- Every entity must implement: `draw(canvas)`, `get_hitbox() -> (x, y, w, h)`, and call `self.update_statuses(dt)` in its `update()`.
- Hitboxes use a **shrink_scale** (0.8–0.82) applied to the sprite's pixel-based bounding box for tighter collision.
- Sprite flipping uses Kivy `PushMatrix/Scale(x=-1)/PopMatrix` — `facing` is `1` (right) or `-1` (left).

### Texture & Animation

- Sprites live under `game_picture/` with naming convention `{Action}{FrameNumber}.png` (e.g., `Walk1.png`, `Attack_5.png`).
- Textures are **preloaded at startup** via class-level `_texture_cache` / `_bbox_cache` dicts to avoid runtime allocation.
- Bounding boxes are computed from alpha pixels (`alpha > 10`) and stored as normalized `(x_ratio, y_ratio, w_ratio, h_ratio)`.
- Animation frame counts differ per skin — special enemies define them in `SpecialEnemyEntity.ANIMATION_FRAMES` dict.

### Rendering

- **No Kivy widgets per entity** — everything is drawn directly on the `GameWidget.canvas` using Kivy graphics instructions.
- Z-ordering: entities sorted by danger priority, then by Y position (lower Y = drawn later = in front), with spawn-order tie-breaking.
- The entire canvas is cleared and redrawn every frame in `_draw_scene()`.

### Status System

- Apply buffs/debuffs via `entity.add_status(name, duration, potency, stacks, modifiers={"move_speed": 0.5})`.
- Query multipliers with `entity.get_status_multiplier("move_speed", default=1.0)` — multiplicative stacking.
- Statuses auto-expire via duration countdown in `StatusComponent.update(dt)`.

### Game Mechanics

- 15-minute timed game (`GAME_DURATION = 15 * 60`). Enemy spawn interval decreases linearly from 2.0s to 0.5s.
- Special enemies spawn every 3 minutes; type selection avoids repeating the last 2 types.
- Kitsune has unique ranged AI: approach → ranged_attack → escape states, fires `EnemyProjectileEntity`.
- Player shooting: hold left-click for continuous fire, bullets aim toward cursor clamped to ±80° cone.
- Walkable Y band: `block_unit` to `height - 3*block_unit - player_height` (screen divided into 10 vertical blocks).

## Debug Mode

Press `9` to toggle. Available debug keys:

- `+` / `=` — spawn extra enemy
- `1` / `2` / `3` — spawn Gorgon / Kitsune / Red_Werewolf
- `-` — cycle time speed (1×, 2×, 5×, 10×, 30×, 60×)
- Shows colored hitbox outlines, path lines, and spawn/FPS stats

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
