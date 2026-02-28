# Kivy 2.5D Shooter — Implementation Status & Detailed Plan

อัปเดตล่าสุด: 2026-02-28  
เอกสารนี้อ้างอิงจากโค้ดปัจจุบันจริงในโปรเจ็กต์ เพื่อสรุปว่าอะไร **ทำแล้ว** / **ยังไม่ทำ** และวางแผนต่อแบบละเอียด โดยใช้ asset ที่มีอยู่ใน `game_picture/` ให้มากที่สุด

## 1) Current Scope (จากโค้ดปัจจุบัน)

- เกมเป็น 2.5D side-scrolling shooter แบบ survival timer 15 นาที
- มีผู้เล่น 1 ตัว, ศัตรูปกติ 4 แบบ, ศัตรูพิเศษ 3 แบบ
- ใช้ `GameWidget` เป็น game loop หลัก (`Clock.schedule_interval` 60 FPS)
- วาดด้วย Kivy canvas โดยตรง (ไม่สร้าง widget ต่อ entity)

## 2) Implemented vs Not Implemented

### ✅ Implemented แล้ว

#### Core Loop / Input / Render

- [x] Game loop 60 FPS ใน `game.py`
- [x] Input keyboard (`WASD`, `Shift`, debug keys)
- [x] Mouse hold ยิงต่อเนื่อง (left click)
- [x] พื้นหลัง + redraw scene ทุกเฟรม
- [x] Render order แบบ danger + Y-sort + spawn order

#### Player

- [x] Player sprite animation (`idle/walk/run/shot/hurt/dead`)
- [x] Clamp พื้นที่เดินให้อยู่ใน walkable Y band
- [x] HP และ death state
- [x] ยิงจาก muzzle + aim clamp (cone)

#### Enemies & Combat

- [x] Spawn ศัตรูจากซ้าย/ขวานอกจอ
- [x] Spawn rate เร็วขึ้นตามเวลา (2.0s → 0.5s)
- [x] ศัตรูปกติ 4 archetype พร้อม stat ต่างกัน
- [x] ศัตรูพิเศษ 3 แบบ + stat เฉพาะ
- [x] Kitsune ranged projectile + dodge behavior
- [x] Bullet ↔ enemy collision
- [x] Enemy melee ↔ player collision
- [x] Enemy projectile ↔ player collision
- [x] Enemy separation (spatial grid + soft repulsion)

#### Status Infrastructure

- [x] `StatusComponent` / `StatusEffect` ใช้งานได้แล้ว
- [x] `update_statuses(dt)` ถูกเรียกใน player/enemy/projectile
- [x] multiplier modifiers พร้อมต่อยอด status effect

#### Debug / Testing Helpers

- [x] Debug mode (`9`) + hitbox/path/FPS
- [x] Spawn ศัตรู debug (`+`, `1`, `2`, `3`)
- [x] Time speed debug cycle (`-`)
- [x] God mode (`8`)

### ❌ ยังไม่ Implement (สำคัญ)

#### Progression / RPG

- [ ] ระบบ EXP และ Level-up
- [ ] ระบบค่าสเตตัส RPG (STR/DEX/AGI/INT/VIT/LUCK) แบบมีผลจริง
- [ ] ระบบเลือกอัปเกรดตอนเลเวลอัป (pause + choose)

#### Skill-based System

- [ ] Active skills (กดใช้ + cooldown)
- [ ] Passive skills (ติดตัวตลอดรอบ)
- [ ] Skill tree / card pool / rarity

#### Loot / Economy

- [ ] ดรอปไอเท็มจากศัตรู/บอส
- [ ] เงิน/แต้ม + pickup magnet radius
- [ ] rarity & affix system
- [ ] ใช้หน้าจอ upgrade/shop จริงในเกม

#### UI Flow (ใช้รูปที่มี)

- [ ] Main menu flow จริง
- [ ] Pause menu flow จริง
- [ ] Victory / Mission Failed screens
- [ ] HUD เต็มรูปแบบ (weapon icon, money panel, xp bar)
- [ ] Inventory & Stats screen

#### Content/Polish

- [ ] สลับตัวละคร `Soldier_1` / `Soldier_2`
- [ ] ระบบอาวุธหลายชนิด
- [ ] Sound/SFX/BGM
- [ ] Save meta progression

## 3) Asset-Aware Plan (ยึดของที่มีใน `game_picture`)

ใช้ทรัพยากรเดิมโดยตรง:

- `game_picture/ui/Main menu` → หน้าเริ่มเกม/ปุ่ม Start/Settings/Exit
- `game_picture/ui/Pause menu` → pause overlay + resume/restart
- `game_picture/ui/Mission Failed` → game over screen
- `game_picture/ui/Victory` → clear screen
- `game_picture/ui/HUD/CHARACTER HUD` → HP/EXP/level panel
- `game_picture/ui/HUD/MONEY PANEL` → เงิน/score
- `game_picture/ui/HUD/WEAPON ICONS` → icon weapon + skill slot
- `game_picture/ui/Inventory and Stats` → stats detail + loadout
- `game_picture/ui/Upgrade` → level-up choice / shop / reroll
- `game_picture/ui/Bonus` → item/skill card visual
- `game_picture/background/bg1.png`, `bg2.png`, `bg3.png` → map tier/phase

## 4) Detailed Development Plan (Skill + Loot first)

## Phase A — Progression Backbone (2-3 วัน)

เป้าหมาย: ทำระบบเลเวลและค่าสเตตัสให้ครบก่อน เพื่อรองรับ skill/loot

### งาน

- เพิ่ม `PlayerProgression` (exp, level, next_exp, stat_points)
- เพิ่มฟิลด์ stat จริง: `str`, `dex`, `agi`, `int`, `vit`, `luck`
- สร้างฟังก์ชัน recalc derived stats:
  - `bullet_damage`
  - `fire_rate`
  - `move_speed`
  - `max_hp`
  - `crit_chance`
- ให้ศัตรูตายแล้วให้ EXP

### เกณฑ์จบ

- ฆ่าศัตรูแล้ว EXP เพิ่มได้
- EXP เต็มแล้วเลเวลขึ้นและมีแต้มอัป
- ค่าสเตตัสมีผลกับการยิง/เคลื่อนที่/เลือดจริง

## Phase B — Skill System (3-4 วัน)

เป้าหมาย: เพิ่มระบบ skill-based gameplay แบบชัดเจน

### โครงระบบ

- สร้าง `skill_system.py`:
  - `SkillDefinition`
  - `ActiveSkillRuntime`
  - `PassiveSkillRuntime`
- เพิ่ม skill slots (เช่น 2 active + 3 passive)
- เพิ่ม cooldown manager per skill

### Skill MVP ที่ควรเริ่ม

- Active 1: Dash (หลบเร็วระยะสั้น)
- Active 2: Grenade / Shockwave (AoE)
- Passive 1: Attack Speed Up
- Passive 2: Lifesteal เล็กน้อย
- Passive 3: Pickup Radius Up

### UI ที่ใช้

- ใช้ `game_picture/ui/HUD/WEAPON ICONS` เป็น skill icon slot
- ใช้ `game_picture/ui/Upgrade` + `game_picture/ui/Bonus` เป็นหน้าจอเลือก skill

### เกณฑ์จบ

- กดใช้ active skill ได้และมี cooldown แสดง
- passive skill มีผลทันทีเมื่อเลือก
- มีระบบสุ่มตัวเลือก skill 3 ใบตอน level up

## Phase C — Loot & Economy (3-4 วัน)

เป้าหมาย: ให้ลูปการเล่น “ฆ่า → ดรอป → เก็บ → เก่งขึ้น” สมบูรณ์

### โครงระบบ

- สร้าง `loot_system.py`:
  - `LootDropDefinition`
  - `LootInstance`
  - `DropTable`
- item type MVP:
  - Gold
  - HP Orb
  - Skill Essence (ใช้ reroll/upgrade)
  - Temporary Buff pickup

### Logic สำคัญ

- โอกาสดรอปขึ้นกับ `luck`
- rarity tiers: common/rare/epic/legendary
- auto-pick เมื่อเข้า radius (radius โตจาก passive)
- loot magnet effect (วิ่งเข้าผู้เล่น)

### UI ที่ใช้

- เงิน: `game_picture/ui/HUD/MONEY PANEL`
- แจ้ง item pickup: `game_picture/ui/Bonus`
- หน้าอัปเกรด/ซื้อ: `game_picture/ui/Upgrade`

### เกณฑ์จบ

- ศัตรูตายแล้วมีโอกาสดรอปของ
- ผู้เล่นเก็บได้และเห็นผลทันที
- เงิน/essence นำไปใช้ในระบบ upgrade ได้

## Phase D — Menu Flow Integration (2-3 วัน)

เป้าหมาย: เชื่อม UX ให้ครบก่อน polish

### งาน

- Main menu scene (`Main menu` assets)
- Pause scene (`Pause menu` assets)
- Mission failed scene (`Mission Failed` assets)
- Victory scene (`Victory` assets)
- Loading/transition (`Loading Screen` assets)

### เกณฑ์จบ

- เข้าเกม/หยุดเกม/จบเกมครบ flow
- ไม่มี dead-end screen

## Phase E — Balance & Content Expansion (ต่อเนื่อง)

### งาน

- เพิ่มอาวุธหลายแบบ (SMG/Shotgun/Rifle)
- ใช้ `Soldier_2` เป็น alternative character
- ปรับ balance enemy wave + boss timing
- เพิ่ม minimap/level menu เมื่อพร้อม

### เกณฑ์จบ

- รอบ 15 นาทีเล่นได้ลื่น + มีเป้าหมายชัด
- skill + loot ทำให้ build ต่างกันจริง

## 5) Implementation Order (แนะนำให้ทำตามนี้)

1. `player_entity.py` + `game.py` → ใส่ progression stats/exp/level
2. เพิ่ม `skill_system.py` และต่อเข้ากับ game loop
3. เพิ่ม `loot_system.py` และ entity pickup
4. ค่อยเชื่อม UI assets (`HUD`, `Upgrade`, `Bonus`)
5. ปิดท้ายด้วย menu/result flow (`Main menu`, `Pause`, `Victory`, `Mission Failed`)

## 6) Risks / Notes

- โค้ดตอนนี้รวม logic ใน `GameWidget` ค่อนข้างมาก ควรแยกเป็นระบบย่อยทีละส่วน (skill/loot/progression) ไม่ต้อง rewrite ทั้งหมดทันที
- ก่อนเพิ่มฟีเจอร์หนัก ควรกำหนด data-driven config (dict/json) สำหรับ skill และ loot เพื่อบาลานซ์ง่าย
- รักษา pattern เดิม: วาด canvas ตรง + ใช้ hitbox + clamp เดียวกันทุก entity

## 7) Immediate Next Sprint (ทำได้เลย)

- [ ] เพิ่ม EXP/Level และ stat points
- [ ] ทำ level-up popup (3 choices)
- [ ] สร้าง active skill 1 ตัว + passive skill 2 ตัว
- [ ] ทำ loot drop 2 ชนิด (Gold + HP Orb)
- [ ] ผูก HUD money/xp ด้วย asset ที่มี
