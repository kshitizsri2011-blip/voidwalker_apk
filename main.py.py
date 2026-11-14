"""
VOIDWALKER: 100K PROOF EDITION
==============================
A complete first-person 3D raycasting survival-horror & paranormal investigation game
written in pure Python + Pygame + NumPy.
A KS_5G1 Production.

No external art or sound assets are required - every texture, sprite, blood decal,
critter swarm, weapon/hand animation, camera snapshot, icon, and sound effect is
procedurally generated at startup.

    pip install pygame numpy
    python voidwalker.py

    python voidwalker.py --unlock-all     (testing: opens every sector, doesn't touch your save)

CONTROLS
    W A S D             - Move / strafe
    Mouse               - Look around (click window to capture mouse)
    Right Click / C / F - Snap a picture with your Camera (Core Proof + Blog/Book B-Roll)
    G                   - Toggle Camcorder IR Night-Vision mode
    V                   - Toggle Camera Viewfinder overlay
    Left Click / Space  - Shoot weapon (hold to charge the Railgun)
    Left / Right        - Turn (keyboard fallback)
    Shift               - Sprint
    R                   - Reload weapon (with full multi-stage hand reload animation)
    1-4                 - Switch weapon (Pistol / Shotgun / Plasma Cannon / Railgun)
    N / L               - Open Creator Notebook (Stream, Blog, Book, Polaroids)
    H / F1              - Toggle Controls & Features Field Manual
    T                   - Toggle On-Screen Mobile Touch Controls
    Tab                 - Toggle hand-drawn expedition map
    Esc                 - Pause / Back
    Enter               - Confirm / Select
    S                   - Open Settings
    F11                 - Toggle fullscreen (Alt+Enter also works)
"""

import math
import sys
import os
import json
import tempfile
import random
import array
import numpy as np

import pygame
from pygame.locals import *

# ----------------------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------------------
DISPLAY_W, DISPLAY_H = 1024, 640      # actual OS window size
RENDER_W, RENDER_H = 320, 200         # upgraded high-res default internal buffer (vectorized, fast!)
RES_PRESETS = [
    ("RETRO (200x125)", 200, 125),
    ("CLASSIC (240x150)", 240, 150),
    ("HD SMOOTH (320x200)", 320, 200),
    ("ULTRA HD (400x250)", 400, 250),
]
FOV_DEG_DEFAULT = 60
FOV_DEG_MIN = 50
FOV_DEG_MAX = 85
FOV_DEG_STEP = 5
FOV = math.radians(FOV_DEG_DEFAULT)
HALF_FOV = FOV / 2.0
MAX_DEPTH = 14.5
TEX_SIZE = 64

MOVE_SPEED = 3.2
SPRINT_MULT = 1.7
ROT_SPEED = 2.6
MOUSE_SENS_DEFAULT = 0.0026
MOUSE_SENS_MIN = 0.0008
MOUSE_SENS_MAX = 0.0060
MOUSE_SENS_STEP = 0.0004
VOLUME_STEP = 0.1

PLAYER_MAX_HP = 100
PLAYER_RADIUS = 0.22
SPAWN_GRACE_SECONDS = 3.0
SECTOR_CLEAR_HEAL = 25
ENEMY_HIT_RADIUS = 0.42
STALK_WATCHED = 0.45
STALK_UNWATCHED = 1.30
STALK_FOV = math.radians(38)
SHAKE_DEFAULT = 1.0

BRIGHTNESS_DEFAULT = 1.0
BRIGHTNESS_MIN = 0.6
BRIGHTNESS_MAX = 1.6
BRIGHTNESS_STEP = 0.1
AMBIENT_LIGHT = 0.09
LIGHT_FALLOFF = 0.85

GAME_MODES = [
    ('STANDARD URBEX', True, 1.0, 'Unsettling darkness • IR Night Vision [G] active'),
    ('BLACKOUT HORROR', False, 1.0, 'Pitch-black corridors • IR Night Vision DISABLED'),
    ('NIGHTMARE (EMF)', False, 1.5, 'Deadlier entities • IR Jammed • 1.5x Reach'),
]
EMF_JAMMED_SECTORS = {3, 11}  # Pripyat radiation & Hoia Baciu EMF dead-zone

PHOTOS_REQUIRED = 10                  # player only knows they must take AT LEAST 10 unique pics
TOTAL_UNIQUE_TARGETS = 15             # internal count of unique targets (hidden from player UI!)
CAMERA_MAX_RANGE = 8.5
CAMERA_AIM_SPREAD = 0.24

FPS_CAP = 60
MIXER_RATE = 22050
IS_ANDROID = ("ANDROID_ARGUMENT" in os.environ or "ANDROID_ROOT" in os.environ)


def _settings_dir():
    """Persistent folder for settings.json and save files."""
    base = os.environ.get("APPDATA")
    if not base:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base, "VoidWalker")
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        path = tempfile.gettempdir()
    return path


SETTINGS_FILE = os.path.join(_settings_dir(), "settings.json")


def load_settings():
    defaults = {
        "mouse_sens": MOUSE_SENS_DEFAULT,
        "master_volume": 1.0,
        "horror_volume": 0.9,
        "brightness": BRIGHTNESS_DEFAULT,
        "fov_deg": FOV_DEG_DEFAULT,
        "res_index": 2,               # HD SMOOTH (320x200) default
        "shake": SHAKE_DEFAULT,
        "vhs_effect": True,
        "head_bob": True,
        "touch_controls": IS_ANDROID,
        "fullscreen": False,
    }
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        defaults["mouse_sens"] = max(MOUSE_SENS_MIN, min(MOUSE_SENS_MAX, float(data.get("mouse_sens", MOUSE_SENS_DEFAULT))))
        defaults["master_volume"] = max(0.0, min(1.0, float(data.get("master_volume", 1.0))))
        defaults["horror_volume"] = max(0.0, min(1.0, float(data.get("horror_volume", 0.9))))
        defaults["brightness"] = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, float(data.get("brightness", BRIGHTNESS_DEFAULT))))
        defaults["fov_deg"] = max(FOV_DEG_MIN, min(FOV_DEG_MAX, int(data.get("fov_deg", FOV_DEG_DEFAULT))))
        defaults["res_index"] = max(0, min(len(RES_PRESETS) - 1, int(data.get("res_index", 2))))
        defaults["shake"] = max(0.0, min(1.0, float(data.get("shake", SHAKE_DEFAULT))))
        defaults["vhs_effect"] = bool(data.get("vhs_effect", True))
        defaults["head_bob"] = bool(data.get("head_bob", True))
        defaults["touch_controls"] = bool(data.get("touch_controls", IS_ANDROID))
        defaults["fullscreen"] = bool(data.get("fullscreen", False))
        return defaults
    except Exception:
        return defaults


def save_settings(cfg):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


LORE_FILE = os.path.join(_settings_dir(), "lore_progress.json")


def load_lore_progress():
    try:
        with open(LORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        found = data.get("found", [])
        return set(int(i) for i in found if isinstance(i, (int, float)))
    except Exception:
        return set()


def save_lore_progress(found_set):
    try:
        with open(LORE_FILE, "w", encoding="utf-8") as f:
            json.dump({"found": sorted(found_set)}, f)
    except Exception:
        pass


PROGRESS_FILE = os.path.join(_settings_dir(), "progress.json")


def load_progress(num_levels):
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        highest = max(0, min(num_levels - 1, int(data.get("highest_unlocked", 0))))
        known = {w['id'] for w in WEAPON_DEFS}
        found = {w for w in data.get("weapons_found", []) if w in known}
        return highest, found
    except Exception:
        return 0, set()


def save_progress(highest_unlocked, weapons_found=()):
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump({"highest_unlocked": int(highest_unlocked),
                       "weapons_found": sorted(weapons_found)}, f)
    except Exception:
        pass


WALL_EMPTY = 0
WALL_BRICK = 1
WALL_STONE = 2
WALL_METAL = 3
WALL_WOOD = 4
WALL_HULL = 5
WALL_DOOR = 6
WALL_BLOOD_BRICK = 7
WALL_BLOOD_STONE = 8
EXIT_TILE = 9
WALL_BLOOD_METAL = 10
WALL_GRAFFITI = 11

HORROR_WALL_NAMES = {
    WALL_BLOOD_BRICK: ("Blood-Written Brick Wall ('RUN')",
                       "Someone dragged their bleeding fingers across the brickwork to spell 'RUN'. Fresh drops are still forming."),
    WALL_BLOOD_STONE: ("Occult Blood Sigil & Tally Marks",
                       "A ritual circle painted in clotting blood beside prisoner tally marks. My subscribers need to see this wall."),
    WALL_BLOOD_METAL: ("Bloody Handprint Bulkhead",
                       "A frantic palm print slammed against the rusted steel bulkhead, with five long finger streaks dragging down."),
    WALL_GRAFFITI:    ("Blood Warning ('100K LIES')",
                       "Written in blood across the stone: '100K LIES'. How did whoever died down here know my exact follower milestone?!"),
}

# ----------------------------------------------------------------------------------
# PROCEDURAL TEXTURE GENERATION (ENHANCED WITH SPECULAR & RELIEF DETAILS)
# ----------------------------------------------------------------------------------

def _clamp(a):
    return np.clip(a, 0, 255).astype(np.uint8)


_GLYPHS_5X5 = {
    'R': ["1110", "1001", "1110", "1010", "1001"],
    'U': ["1001", "1001", "1001", "1001", "0110"],
    'N': ["1001", "1101", "1011", "1001", "1001"],
    'L': ["1000", "1000", "1000", "1000", "1111"],
    'I': ["111", "010", "010", "010", "111"],
    'E': ["1111", "1000", "1110", "1000", "1111"],
    'S': ["0111", "1000", "0110", "0001", "1110"],
    'D': ["1110", "1001", "1001", "1001", "1110"],
    'A': ["0110", "1001", "1111", "1001", "1001"],
    '1': ["010", "110", "010", "010", "111"],
    '0': ["0110", "1001", "1001", "1001", "0110"],
    'K': ["1001", "1010", "1100", "1010", "1001"],
    'O': ["0110", "1001", "1001", "1001", "0110"],
    'T': ["11111", "00100", "00100", "00100", "00100"],
    'G': ["0111", "1000", "1011", "1001", "0111"],
}


def _stamp_blood_word(tex, word, x0, y0, scale=2, rng=None):
    blood_dark = np.array([115, 10, 12], dtype=np.float32)
    blood_bright = np.array([175, 18, 18], dtype=np.float32)
    cx = x0
    for ch in word:
        rows = _GLYPHS_5X5.get(ch)
        if not rows:
            cx += 3 * scale
            continue
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit == '1':
                    px0 = cx + rx * scale
                    py0 = y0 + ry * scale
                    px1 = min(TEX_SIZE, px0 + scale)
                    py1 = min(TEX_SIZE, py0 + scale)
                    if 0 <= px0 < TEX_SIZE and 0 <= py0 < TEX_SIZE:
                        tex[py0:py1, px0:px1] = blood_bright
                        if rng is not None and rng.random() < 0.48:
                            drip_len = int(rng.integers(3, 14))
                            for dy in range(scale, scale + drip_len):
                                yy = py0 + dy
                                if 0 <= yy < TEX_SIZE:
                                    tex[yy, px0:min(TEX_SIZE, px0 + 1)] = (
                                        blood_dark * max(0.35, 1.0 - dy / 15.0)
                                    )
        cx += (len(rows[0]) + 1) * scale


def _stamp_blood_splatter_and_sigil(tex, rng, mode='handprint'):
    tex = tex.astype(np.float32).copy()
    blood = np.array([140, 14, 14], dtype=np.float32)
    if mode == 'handprint':
        cx, cy = 32, 24
        for y in range(cy - 5, cy + 6):
            for x in range(cx - 6, cx + 6):
                if (x - cx) ** 2 + (y - cy) ** 2 <= 32:
                    tex[y, x] = blood
        for fx, fy in ((-6, -11), (-3, -13), (0, -14), (3, -13), (6, -9)):
            for step in range(8):
                yy = int(cy + fy * step / 7)
                xx = int(cx + fx * step / 7)
                if 0 <= yy < TEX_SIZE and 0 <= xx < TEX_SIZE:
                    tex[yy:min(TEX_SIZE, yy + 2), xx:min(TEX_SIZE, xx + 2)] = blood
        for x in range(cx - 5, cx + 6, 2):
            drip = int(rng.integers(10, 28))
            for y in range(cy + 4, min(TEX_SIZE, cy + 4 + drip)):
                tex[y, x] = blood * 0.78
    elif mode == 'sigil':
        cx, cy, r = 32, 32, 16
        for ang in np.linspace(0, 2 * math.pi, 120):
            x = int(cx + r * math.cos(ang))
            y = int(cy + r * math.sin(ang))
            if 0 <= x < TEX_SIZE and 0 <= y < TEX_SIZE:
                tex[y, x] = blood
                if y + 1 < TEX_SIZE:
                    tex[y + 1, x] = blood * 0.8
        for i in range(-r, r + 1):
            if 0 <= cy + i < TEX_SIZE:
                tex[cy + i, cx] = blood
            if 0 <= cx + i < TEX_SIZE:
                tex[cy, cx + i] = blood
        for tx in range(8, 20, 3):
            tex[8:18, tx] = blood
        for s in range(14):
            tex[17 - s // 2, 6 + s] = blood
    return _clamp(tex)


def make_brick_texture(rng):
    tex = np.zeros((TEX_SIZE, TEX_SIZE, 3), dtype=np.float32)
    mortar = np.array([62, 58, 54])
    brick_base = np.array([154, 62, 46])
    tex[:, :] = mortar
    brick_h, brick_w = 8, 16
    for row in range(0, TEX_SIZE, brick_h):
        offset = (brick_w // 2) if (row // brick_h) % 2 else 0
        for col in range(-offset, TEX_SIZE, brick_w):
            shade = rng.uniform(-18, 18)
            color = brick_base + shade
            y0, y1 = row + 1, min(row + brick_h - 1, TEX_SIZE)
            x0, x1 = max(col, 0), min(col + brick_w - 1, TEX_SIZE)
            if x1 > x0 and y1 > y0:
                tex[y0:y1, x0:x1] = color
                # Top bevel highlight & bottom shadow for 3D brick depth
                tex[y0:min(y0 + 1, y1), x0:x1] = color * 1.18
                tex[max(y0, y1 - 1):y1, x0:x1] = color * 0.72
    noise = rng.normal(0, 6, size=(TEX_SIZE, TEX_SIZE, 1))
    tex += noise
    return _clamp(tex)


def make_stone_texture(rng):
    base = rng.normal(122, 1, size=(TEX_SIZE, TEX_SIZE))
    for scale in (2, 4, 8, 16):
        small = rng.uniform(-20, 20, size=(scale, scale))
        big = np.kron(small, np.ones((TEX_SIZE // scale, TEX_SIZE // scale)))
        base += big
    grey = np.stack([base * 0.85, base * 0.87, base * 0.9], axis=-1)
    grey[::16, :] *= 0.50
    grey[1::16, :] *= 1.14
    grey[:, ::16] *= 0.50
    grey[:, 1::16] *= 1.12
    return _clamp(grey)


def make_metal_texture(rng):
    tex = np.full((TEX_SIZE, TEX_SIZE, 3), (92, 97, 104), dtype=np.float32)
    for x in range(0, TEX_SIZE, 16):
        tex[:, x:x + 2] = (38, 40, 44)
        if x + 2 < TEX_SIZE:
            tex[:, x + 2:x + 3] = (125, 130, 138)
    for y in range(0, TEX_SIZE, 16):
        tex[y:y + 2, :] = (38, 40, 44)
        if y + 2 < TEX_SIZE:
            tex[y + 2:y + 3, :] = (125, 130, 138)
    for gx in range(8, TEX_SIZE, 16):
        for gy in range(8, TEX_SIZE, 16):
            tex[gy - 1:gy + 2, gx - 1:gx + 2] = (175, 180, 186)
    tex += rng.normal(0, 4, size=(TEX_SIZE, TEX_SIZE, 1))
    return _clamp(tex)


def make_wood_texture(rng):
    x = np.linspace(0, 6 * math.pi, TEX_SIZE)
    grain = 12 * np.sin(x)[None, :] + rng.normal(0, 6, size=(TEX_SIZE, TEX_SIZE))
    base = 112 + grain
    tex = np.stack([base * 0.95, base * 0.6, base * 0.32], axis=-1)
    for y in range(0, TEX_SIZE, 16):
        tex[y:y + 1, :] *= 0.45
        if y + 1 < TEX_SIZE:
            tex[y + 1:y + 2, :] *= 1.15
    return _clamp(tex)


def make_hull_texture(rng):
    tex = np.full((TEX_SIZE, TEX_SIZE, 3), (58, 68, 78), dtype=np.float32)
    stripe = (np.arange(TEX_SIZE) // 4) % 2 == 0
    tex[stripe, :] *= 1.16
    tex[:, ::32] = (230, 190, 40)
    tex += rng.normal(0, 3, size=(TEX_SIZE, TEX_SIZE, 1))
    return _clamp(tex)


def make_door_texture(rng):
    tex = np.full((TEX_SIZE, TEX_SIZE, 3), (60, 110, 130), dtype=np.float32)
    tex[24:40, 8:56] = (30, 60, 75)
    tex[28:36, 12:52] = (255, 200, 40)
    for y in range(0, TEX_SIZE, 6):
        tex[y, :] *= 0.85
    return _clamp(tex)


def make_floor_texture(rng):
    base = np.full((TEX_SIZE, TEX_SIZE), 86.0)
    checker = ((np.arange(TEX_SIZE)[:, None] // 8) + (np.arange(TEX_SIZE)[None, :] // 8)) % 2
    base += checker * 22
    base += rng.normal(0, 3, size=(TEX_SIZE, TEX_SIZE))
    # Grout lines for crisp tile perspective
    base[::8, :] *= 0.68
    base[:, ::8] *= 0.68
    tex = np.stack([base * 0.8, base * 0.82, base * 0.86], axis=-1)
    for _ in range(3):
        cx, cy = int(rng.integers(10, 54)), int(rng.integers(10, 54))
        r = int(rng.integers(4, 10))
        yy, xx = np.ogrid[:TEX_SIZE, :TEX_SIZE]
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
        tex[mask] *= np.array([0.75, 0.55, 0.55])
    return _clamp(tex)


def make_ceiling_texture(rng):
    base = np.full((TEX_SIZE, TEX_SIZE), 56.0)
    base += rng.normal(0, 2, size=(TEX_SIZE, TEX_SIZE))
    for y in range(0, TEX_SIZE, 16):
        base[y, :] *= 1.4
    for x in range(0, TEX_SIZE, 16):
        base[:, x] *= 0.75
    tex = np.stack([base * 0.6, base * 0.65, base * 0.8], axis=-1)
    return _clamp(tex)


def _horror_grade(tex):
    tex = tex.astype(np.float32)
    gray = tex.mean(axis=-1, keepdims=True)
    desat = tex * 0.52 + gray * 0.48
    tint = np.array([0.90, 0.97, 0.95], dtype=np.float32)
    graded = desat * tint * 1.00
    return _clamp(graded)


def build_textures(seed=1337):
    rng = np.random.default_rng(seed)
    brick = _horror_grade(make_brick_texture(rng))
    stone = _horror_grade(make_stone_texture(rng))
    metal = _horror_grade(make_metal_texture(rng))
    wood = _horror_grade(make_wood_texture(rng))
    hull = _horror_grade(make_hull_texture(rng))

    blood_brick = brick.astype(np.float32).copy()
    _stamp_blood_word(blood_brick, "RUN", 14, 18, scale=3, rng=rng)
    blood_brick = _clamp(blood_brick)

    blood_stone = _stamp_blood_splatter_and_sigil(stone, rng, mode='sigil')
    blood_metal = _stamp_blood_splatter_and_sigil(metal, rng, mode='handprint')

    graffiti = stone.astype(np.float32).copy()
    _stamp_blood_word(graffiti, "100K", 8, 12, scale=2, rng=rng)
    _stamp_blood_word(graffiti, "LIES", 8, 34, scale=2, rng=rng)
    graffiti = _clamp(graffiti)

    return {
        WALL_BRICK: brick,
        WALL_STONE: stone,
        WALL_METAL: metal,
        WALL_WOOD: wood,
        WALL_HULL: hull,
        WALL_DOOR: _horror_grade(make_door_texture(rng)),
        WALL_BLOOD_BRICK: blood_brick,
        WALL_BLOOD_STONE: blood_stone,
        WALL_BLOOD_METAL: blood_metal,
        WALL_GRAFFITI: graffiti,
        'floor': _horror_grade(make_floor_texture(rng)),
        'ceiling': _horror_grade(make_ceiling_texture(rng)),
    }


def make_window_icon_surface():
    """Generate the runtime 64x64 window icon (Floating Skull in Red Camcorder Viewfinder)."""
    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    pygame.draw.rect(surf, (12, 12, 18), (2, 2, 60, 60), border_radius=10)
    pygame.draw.rect(surf, (215, 35, 40), (2, 2, 60, 60), width=2, border_radius=10)
    skull = make_floating_skull_surface(2)
    surf.blit(skull, (0, 2))
    # Viewfinder brackets & REC dot
    for x0, y0, sx, sy in ((7, 7, 1, 1), (56, 7, -1, 1), (7, 56, 1, -1), (56, 56, -1, -1)):
        pygame.draw.line(surf, (250, 55, 55), (x0, y0), (x0 + sx * 8, y0), 2)
        pygame.draw.line(surf, (250, 55, 55), (x0, y0), (x0, y0 + sy * 8), 2)
    pygame.draw.circle(surf, (255, 40, 40), (12, 12), 3)
    return surf


# ----------------------------------------------------------------------------------
# PROCEDURAL SPRITE GENERATION:
# - Floating Animated Skull ('grunt')
# - Detailed Headless Skeleton ('shooter')
# - Evaporating Black Shadow Figure ('charger')
# - Reanimated Mangled Dead Body ('brute' - replaces the big purple guy!)
# ----------------------------------------------------------------------------------

def make_floating_skull_surface(frame=0):
    size = 64
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2

    if frame == 3:
        pygame.draw.ellipse(surf, (45, 18, 25, 160), (10, 44, 44, 14))
        pygame.draw.arc(surf, (195, 185, 165), (16, 38, 26, 18), 0, math.pi, 4)
        pygame.draw.polygon(surf, (180, 170, 150), [(20, 48), (38, 46), (44, 54), (16, 54)])
        pygame.draw.rect(surf, (160, 150, 130), (34, 50, 14, 5), border_radius=2)
        for tx in range(35, 47, 3):
            pygame.draw.rect(surf, (220, 215, 200), (tx, 48, 2, 3))
        pygame.draw.circle(surf, (90, 20, 20), (25, 46), 3)
        return surf

    bob_y = {0: 0, 1: -3, 2: -2, 4: 2, 5: -1}.get(frame, 0)
    tilt_x = {0: -1, 1: 0, 2: 0, 4: 1, 5: 0}.get(frame, 0)
    jaw_gap = {0: 1, 1: 4, 2: 9, 4: 6, 5: 2}.get(frame, 2)

    aura_col = (140, 25, 40, 85) if frame == 2 else (75, 20, 55, 70)
    pygame.draw.circle(surf, aura_col, (cx + tilt_x, 26 + bob_y), 24)
    for wisp_i, wx in enumerate((-10, -4, 3, 9)):
        wy0 = 38 + bob_y + ((frame + wisp_i) % 3) * 2
        pts = [
            (cx + wx - 3, wy0),
            (cx + wx + 3, wy0),
            (cx + wx + (2 if (frame + wisp_i) % 2 == 0 else -2), wy0 + 16),
        ]
        pygame.draw.polygon(surf, (60, 18, 45, 130), pts)

    for v_i in range(3):
        vy = 43 + bob_y + jaw_gap // 2 + v_i * 5
        vx = cx + tilt_x + int(math.sin(frame * 1.4 + v_i) * 2)
        pygame.draw.ellipse(surf, (155, 145, 128), (vx - 4, vy, 8, 4))
        pygame.draw.circle(surf, (90, 80, 70), (vx, vy + 2), 1)

    bone_hi = (225, 216, 195)
    bone_mid = (195, 184, 162)
    bone_shd = (140, 130, 112)
    hy = 20 + bob_y
    hx = cx + tilt_x

    pygame.draw.ellipse(surf, bone_shd, (hx - 17, hy - 14, 34, 28))
    pygame.draw.ellipse(surf, bone_mid, (hx - 16, hy - 14, 32, 26))
    pygame.draw.ellipse(surf, bone_hi, (hx - 12, hy - 12, 24, 16))

    pygame.draw.polygon(surf, bone_mid, [
        (hx - 15, hy + 4), (hx + 15, hy + 4),
        (hx + 11, hy + 13), (hx - 11, hy + 13)
    ])
    pygame.draw.circle(surf, bone_shd, (hx - 13, hy + 8), 3)
    pygame.draw.circle(surf, bone_shd, (hx + 13, hy + 8), 3)

    pygame.draw.line(surf, (70, 60, 50), (hx - 6, hy - 12), (hx - 1, hy - 5), 1)
    pygame.draw.line(surf, (70, 60, 50), (hx - 1, hy - 5), (hx + 5, hy - 8), 1)
    pygame.draw.line(surf, (70, 60, 50), (hx - 1, hy - 5), (hx - 3, hy - 1), 1)

    upper_teeth_y = hy + 12
    for tx in range(hx - 8, hx + 8, 3):
        pygame.draw.rect(surf, (235, 230, 210), (tx, upper_teeth_y, 2, 4))
        pygame.draw.rect(surf, (90, 80, 70), (tx, upper_teeth_y, 2, 4), 1)

    jy = upper_teeth_y + 3 + jaw_gap
    if jaw_gap > 1:
        pygame.draw.rect(surf, (25, 8, 12), (hx - 8, upper_teeth_y + 3, 16, jaw_gap + 2))
        if frame == 2:
            pygame.draw.ellipse(surf, (220, 50, 30, 180), (hx - 6, upper_teeth_y + 4, 12, jaw_gap))
    pygame.draw.polygon(surf, bone_shd, [
        (hx - 11, jy - 2), (hx + 11, jy - 2),
        (hx + 8, jy + 7), (hx - 8, jy + 7)
    ])
    pygame.draw.polygon(surf, bone_mid, [
        (hx - 9, jy - 1), (hx + 9, jy - 1),
        (hx + 7, jy + 6), (hx - 7, jy + 6)
    ])
    for tx in range(hx - 7, hx + 7, 3):
        pygame.draw.rect(surf, (230, 224, 204), (tx, jy - 3, 2, 3))

    for ex in (hx - 7, hx + 7):
        pygame.draw.ellipse(surf, (20, 15, 18), (ex - 5, hy - 2, 10, 9))
        eye_glow = (255, 50, 30) if frame == 2 else (255, 190, 40) if frame % 2 == 0 else (255, 110, 30)
        pygame.draw.circle(surf, eye_glow, (ex, hy + 2), 3 if frame == 2 else 2)
        pygame.draw.circle(surf, (255, 255, 220), (ex, hy + 2), 1)

    pygame.draw.polygon(surf, (22, 16, 18), [
        (hx, hy + 4), (hx - 3, hy + 10), (hx + 3, hy + 10)
    ])
    return surf


def make_headless_skeleton_surface(frame=0):
    size = 64
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2
    bone_hi = (225, 218, 200)
    bone_mid = (188, 178, 158)
    bone_dark = (128, 118, 102)
    joint_col = (150, 140, 122)

    if frame == 3:
        pygame.draw.ellipse(surf, (35, 45, 55, 130), (10, 44, 44, 14))
        for bx1, by1, bx2, by2 in ((14, 52, 34, 44), (24, 46, 48, 53), (18, 48, 42, 49)):
            pygame.draw.line(surf, bone_mid, (bx1, by1), (bx2, by2), 3)
            pygame.draw.circle(surf, bone_hi, (bx1, by1), 2)
            pygame.draw.circle(surf, bone_hi, (bx2, by2), 2)
        for rx in range(22, 38, 4):
            pygame.draw.arc(surf, bone_hi, (rx, 42, 8, 12), 0, math.pi, 2)
        return surf

    bob = 2 if frame == 1 else 0
    stride = 2 if frame == 1 else -2 if frame == 0 else 0

    core_alpha = 135 if frame == 2 else 75
    pygame.draw.ellipse(surf, (60, 180, 220, core_alpha), (cx - 8, 20 - bob, 16, 18))

    neck_y = 14 - bob
    pygame.draw.line(surf, (35, 15, 25, 180), (cx - 2, neck_y - 5), (cx + 1, neck_y), 3)
    pygame.draw.circle(surf, (120, 20, 28, 190), (cx, neck_y - 2), 3)
    for vy in range(neck_y, 41 - bob, 3):
        pygame.draw.rect(surf, bone_dark, (cx - 3, vy, 6, 2))
        pygame.draw.rect(surf, bone_hi, (cx - 2, vy, 4, 2))

    sh_y = 18 - bob
    pygame.draw.line(surf, bone_hi, (cx - 14, sh_y + 1), (cx, sh_y - 1), 2)
    pygame.draw.line(surf, bone_hi, (cx, sh_y - 1), (cx + 14, sh_y + 1), 2)
    pygame.draw.circle(surf, joint_col, (cx - 14, sh_y + 1), 3)
    pygame.draw.circle(surf, joint_col, (cx + 14, sh_y + 1), 3)

    pygame.draw.line(surf, bone_mid, (cx, sh_y), (cx, 32 - bob), 2)
    for r_idx in range(5):
        ry = sh_y + 2 + r_idx * 3
        rw = 12 - (1 if r_idx >= 3 else 0)
        pygame.draw.arc(surf, bone_hi if r_idx % 2 == 0 else bone_mid,
                        (cx - rw - 1, ry - 1, rw + 2, 5), 0.2, math.pi - 0.1, 2)
        pygame.draw.arc(surf, bone_hi if r_idx % 2 == 0 else bone_mid,
                        (cx - 1, ry - 1, rw + 2, 5), 0.1, math.pi - 0.2, 2)

    pelvis_y = 39 - bob
    pygame.draw.polygon(surf, bone_mid, [
        (cx - 11, pelvis_y - 2), (cx + 11, pelvis_y - 2),
        (cx + 8, pelvis_y + 5), (cx - 8, pelvis_y + 5)
    ], 2)
    pygame.draw.circle(surf, (20, 20, 24), (cx - 5, pelvis_y + 2), 2)
    pygame.draw.circle(surf, (20, 20, 24), (cx + 5, pelvis_y + 2), 2)

    for side, hip_x, leg_off in ((-1, cx - 7, stride), (1, cx + 7, -stride)):
        knee_x = hip_x + side * 1
        knee_y = 50 - bob + leg_off // 2
        ankle_x = hip_x + side * 2
        ankle_y = 60 + leg_off // 2
        pygame.draw.line(surf, bone_hi, (hip_x, pelvis_y + 4), (knee_x, knee_y), 3)
        pygame.draw.circle(surf, joint_col, (knee_x, knee_y), 2)
        pygame.draw.line(surf, bone_mid, (knee_x - 1, knee_y), (ankle_x - 1, ankle_y), 2)
        pygame.draw.line(surf, bone_dark, (knee_x + 1, knee_y), (ankle_x + 1, ankle_y), 1)
        pygame.draw.line(surf, bone_hi, (ankle_x - 2, ankle_y), (ankle_x + side * 4, ankle_y + 1), 2)

    pygame.draw.line(surf, bone_hi, (cx - 14, sh_y + 2), (cx - 17, 27 - bob), 2)
    pygame.draw.circle(surf, joint_col, (cx - 17, 27 - bob), 2)
    pygame.draw.line(surf, bone_mid, (cx - 17, 27 - bob), (cx - 4, 25 - bob), 2)

    pygame.draw.line(surf, bone_hi, (cx + 14, sh_y + 2), (cx + 16, 26 - bob), 2)
    pygame.draw.circle(surf, joint_col, (cx + 16, 26 - bob), 2)
    pygame.draw.line(surf, bone_mid, (cx + 16, 26 - bob), (cx + 8, 23 - bob), 2)

    pygame.draw.rect(surf, (45, 36, 28), (cx - 8, 22 - bob, 28, 4))
    pygame.draw.rect(surf, (28, 30, 34), (cx + 14, 21 - bob, 10, 4))
    if frame == 2:
        pygame.draw.circle(surf, (130, 230, 255), (cx + 25, 23 - bob), 6)
        pygame.draw.circle(surf, (240, 255, 255), (cx + 25, 23 - bob), 3)
    return surf


def make_evaporating_shadow_surface(frame=0):
    size = 64
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2

    if frame == 3:
        pygame.draw.ellipse(surf, (8, 6, 12, 210), (12, 46, 40, 12))
        pygame.draw.ellipse(surf, (22, 14, 32, 140), (8, 44, 48, 16))
        for wx in (18, 26, 34, 42):
            pygame.draw.line(surf, (15, 10, 24, 150), (wx, 48), (wx + (wx % 3 - 1) * 2, 34), 2)
        return surf

    rng = random.Random(303 + frame * 71)
    pygame.draw.ellipse(surf, (14, 8, 24, 95), (cx - 22, 8, 44, 52))

    bob = -1 if frame % 2 == 1 else 1
    pygame.draw.polygon(surf, (10, 8, 15, 230), [
        (cx - 13, 22 + bob), (cx + 13, 22 + bob),
        (cx + 10, 46), (cx + 4, 58),
        (cx, 50), (cx - 5, 58), (cx - 10, 46)
    ])
    pygame.draw.ellipse(surf, (6, 5, 10, 250), (cx - 14, 18 + bob, 28, 26))
    pygame.draw.circle(surf, (5, 4, 8, 252), (cx, 15 + bob), 10)

    reach = 6 if frame == 2 else 0
    pygame.draw.polygon(surf, (8, 6, 14, 240), [
        (cx - 13, 21 + bob), (cx - 24 - reach, 30 + bob),
        (cx - 20 - reach, 35 + bob), (cx - 11, 27 + bob)
    ])
    pygame.draw.polygon(surf, (8, 6, 14, 240), [
        (cx + 13, 21 + bob), (cx + 24 + reach, 30 + bob),
        (cx + 20 + reach, 35 + bob), (cx + 11, 27 + bob)
    ])

    for p_idx in range(14):
        px = cx + int((p_idx - 6.5) * 3.2)
        phase = (frame * 5 + p_idx * 3) % 16
        py_base = 24 - (8 if abs(px - cx) < 9 else 0) + bob
        py_top = max(1, py_base - 8 - phase)
        sway = int(math.sin(frame * 1.3 + p_idx) * 2.5)
        pygame.draw.line(surf, (38, 18, 58, 155), (px, py_base), (px + sway, py_top), 4)
        pygame.draw.line(surf, (6, 4, 10, 235), (px, py_base), (px + sway, py_top + 2), 2)

    for _ in range(22):
        ax = cx + rng.randint(-20, 20)
        ay = rng.randint(1, 34)
        r = rng.randint(1, 3)
        pygame.draw.circle(surf, (28, 12, 42, 160), (ax, ay), r + 1)
        pygame.draw.circle(surf, (5, 4, 8, 245), (ax, ay), r)

    eye_col = (255, 240, 255) if frame == 2 else (200, 175, 245)
    pygame.draw.circle(surf, eye_col, (cx - 4, 15 + bob), 2 if frame == 2 else 1)
    pygame.draw.circle(surf, eye_col, (cx + 4, 15 + bob), 2 if frame == 2 else 1)
    return surf


def make_dead_body_surface(frame=0):
    """Replacement for the big purple 'brute' guy: a Reanimated Mangled Dead Body / Corpse!
    Features pallid necrotic grey-green skin, torn blood-soaked expedition rags, a gaping
    chest/abdominal cavity with exposed white ribs and dark viscera, a snapped neck with the
    corpse's head lolling sideways, milky cataract eyes, and a dragging/shambling gait across
    6 animation frames."""
    size = 64
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2

    flesh_pale = (142, 148, 134)
    flesh_bruise = (96, 88, 98)
    rag_dark = (48, 52, 46)
    rag_torn = (68, 70, 62)
    blood_dark = (115, 12, 16)
    blood_bright = (168, 20, 22)
    bone_rib = (215, 205, 185)

    if frame == 3:
        # Motionless dead body lying in a spreading pool of dark blood on the floor
        pygame.draw.ellipse(surf, (95, 10, 14, 215), (6, 44, 52, 16))
        pygame.draw.ellipse(surf, rag_dark, (12, 42, 36, 14))
        pygame.draw.ellipse(surf, flesh_pale, (40, 44, 14, 11))
        pygame.draw.line(surf, blood_bright, (20, 46), (36, 50), 3)
        for rx in (22, 26, 30):
            pygame.draw.line(surf, bone_rib, (rx, 44), (rx + 1, 50), 2)
        return surf

    # Shambling / dragging body lurch based on frame (0, 1, 2, 4, 5)
    lurch_x = {0: -2, 1: 2, 2: 0, 4: -1, 5: 1}.get(frame, 0)
    bob_y = {0: 1, 1: -1, 2: -2, 4: 2, 5: 0}.get(frame, 0)
    drag_leg = 3 if frame in (1, 4) else -2

    # Blood trail smeared on the floor beneath the dragging feet
    pygame.draw.ellipse(surf, (95, 12, 15, 145), (cx - 16, 55, 32, 7))

    # Asymmetrical dragging legs (left leg bent & dragging, right leg shambling)
    pygame.draw.polygon(surf, rag_dark, [
        (cx - 12 + lurch_x, 42 + bob_y),
        (cx - 4 + lurch_x, 42 + bob_y),
        (cx - 8, 59 + drag_leg),
        (cx - 17, 58 + drag_leg),
    ])
    pygame.draw.polygon(surf, rag_torn, [
        (cx + 3 + lurch_x, 42 + bob_y),
        (cx + 12 + lurch_x, 42 + bob_y),
        (cx + 14, 59 - drag_leg),
        (cx + 5, 59 - drag_leg),
    ])
    # Exposed shin bone & bloody ankle on torn trouser leg
    pygame.draw.rect(surf, flesh_pale, (cx - 13, 50, 5, 6))
    pygame.draw.rect(surf, blood_dark, (cx - 13, 52, 5, 3))

    # Hunched, mangled torso in shredded expedition jacket
    tx = cx + lurch_x
    ty = 20 + bob_y
    pygame.draw.polygon(surf, rag_torn, [
        (tx - 16, ty + 24), (tx + 16, ty + 24),
        (tx + 14, ty), (tx - 15, ty + 2)
    ])
    pygame.draw.polygon(surf, rag_dark, [
        (tx - 15, ty + 2), (tx - 2, ty + 2),
        (tx - 4, ty + 24), (tx - 16, ty + 24)
    ])

    # Gaping torn chest / abdominal cavity with exposed white ribs & dark viscera
    pygame.draw.ellipse(surf, (55, 8, 12), (tx - 7, ty + 5, 16, 16))
    pygame.draw.ellipse(surf, blood_dark, (tx - 5, ty + 7, 12, 12))
    for r_y in range(ty + 7, ty + 19, 3):
        pygame.draw.line(surf, bone_rib, (tx - 6, r_y), (tx + 6, r_y + 1), 2)
        pygame.draw.circle(surf, blood_bright, (tx, r_y + 1), 1)
    # Blood dripping down from the open chest wound
    pygame.draw.line(surf, blood_bright, (tx - 2, ty + 18), (tx - 3, ty + 27), 2)
    pygame.draw.line(surf, blood_dark, (tx + 3, ty + 17), (tx + 2, ty + 25), 2)

    # Dead body's arms: one dangling limp & dislocated, the other clawing forward
    reach_y = -6 if frame == 2 else 0
    # Left arm (limp/Wait, lunging on attack frame 2)
    pygame.draw.line(surf, rag_dark, (tx - 14, ty + 4), (tx - 21, ty + 16 + reach_y), 6)
    pygame.draw.line(surf, flesh_pale, (tx - 21, ty + 16 + reach_y), (tx - 24, ty + 24 + reach_y), 4)
    pygame.draw.circle(surf, blood_bright, (tx - 24, ty + 24 + reach_y), 3)

    # Right arm (outstretched bloody hand)
    pygame.draw.line(surf, rag_torn, (tx + 13, ty + 3), (tx + 21, ty + 14 + reach_y), 6)
    pygame.draw.line(surf, flesh_pale, (tx + 21, ty + 14 + reach_y), (tx + 25, ty + 21 + reach_y), 4)
    pygame.draw.circle(surf, blood_bright, (tx + 25, ty + 21 + reach_y), 3)

    # Snapped neck — corpse head lolling sharply to the left at an unnatural 40-degree angle!
    hx = tx - 5
    hy = ty - 5
    # Neck wound
    pygame.draw.line(surf, blood_dark, (tx, ty + 1), (hx + 2, hy + 5), 5)
    #Tilted decaying head
    pygame.draw.ellipse(surf, flesh_bruise, (hx - 11, hy - 9, 22, 19))
    pygame.draw.ellipse(surf, flesh_pale, (hx - 10, hy - 8, 20, 17))
    # Livor mortis bruising & scalp wound
    pygame.draw.ellipse(surf, blood_dark, (hx - 8, hy - 7, 8, 5))
    # Milky white dead cataract eyes (asymmetric because head is tilted)
    pygame.draw.circle(surf, (25, 20, 24), (hx - 4, hy - 1), 3)
    pygame.draw.circle(surf, (215, 225, 220), (hx - 4, hy - 1), 2)
    pygame.draw.circle(surf, (25, 20, 24), (hx + 4, hy + 1), 3)
    pygame.draw.circle(surf, (215, 225, 220), (hx + 4, hy + 1), 2)
    # Unhinged slack jaw dripping dark blood
    jaw_open = 6 if frame == 2 else 4
    pygame.draw.ellipse(surf, (35, 8, 12), (hx - 4, hy + 4, 9, jaw_open + 2))
    pygame.draw.line(surf, blood_bright, (hx, hy + 5 + jaw_open), (hx - 1, hy + 12 + jaw_open), 2)
    return surf


def make_enemy_surface(kind, frame=0):
    if kind == 'grunt':
        return make_floating_skull_surface(frame)
    if kind == 'shooter':
        return make_headless_skeleton_surface(frame)
    if kind == 'charger':
        return make_evaporating_shadow_surface(frame)
    if kind == 'brute':
        return make_dead_body_surface(frame)

    size = 64
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2

    # 'turret'
    base_col = (45, 45, 50)
    metal_col = (80, 80, 88)
    eye_col = (255, 90, 40)
    if frame == 3:
        pygame.draw.ellipse(surf, base_col, (14, 40, 36, 16))
        pygame.draw.rect(surf, metal_col, (20, 44, 24, 8))
        pygame.draw.circle(surf, (40, 40, 40), (32, 44), 3)
        return surf
    pygame.draw.rect(surf, base_col, (18, 40, 28, 16), border_radius=4)
    pygame.draw.circle(surf, metal_col, (cx, 32), 14)
    pygame.draw.circle(surf, eye_col, (cx, 30), 4 if frame != 2 else 6)
    barrel_len = 22 if frame == 2 else 18
    pygame.draw.rect(surf, (25, 25, 28), (cx - 3, 32 - barrel_len, 6, barrel_len))
    if frame == 2:
        pygame.draw.circle(surf, (255, 200, 120), (cx, 32 - barrel_len - 4), 6)
    return surf


def make_pickup_surface(kind):
    size = 48
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    if kind == 'health':
        pygame.draw.rect(surf, (200, 30, 30), (10, 10, 28, 28), border_radius=6)
        pygame.draw.rect(surf, (255, 255, 255), (20, 14, 8, 20))
        pygame.draw.rect(surf, (255, 255, 255), (14, 20, 20, 8))
    elif kind == 'ammo':
        for i in range(3):
            pygame.draw.rect(surf, (220, 190, 60), (14 + i * 7, 12, 4, 20))
            pygame.draw.rect(surf, (120, 90, 20), (14 + i * 7, 28, 4, 4))
    elif kind == 'key':
        pygame.draw.circle(surf, (255, 210, 40), (18, 24), 8, 3)
        pygame.draw.rect(surf, (255, 210, 40), (24, 22, 16, 4))
        pygame.draw.rect(surf, (255, 210, 40), (34, 22, 4, 8))
    elif kind == 'blue_key':
        pygame.draw.circle(surf, (40, 140, 255, 90), (24, 24), 21)
        pygame.draw.circle(surf, (70, 190, 255), (16, 24), 9, 3)
        pygame.draw.circle(surf, (200, 245, 255), (16, 24), 4, 1)
        pygame.draw.rect(surf, (70, 190, 255), (24, 22, 18, 4))
        pygame.draw.rect(surf, (70, 190, 255), (33, 22, 3, 9))
        pygame.draw.rect(surf, (70, 190, 255), (38, 22, 3, 7))
    elif kind == 'pistol':
        pygame.draw.rect(surf, (55, 55, 60), (8, 20, 28, 8), border_radius=2)
        pygame.draw.rect(surf, (30, 30, 33), (32, 21, 8, 5))
        pygame.draw.rect(surf, (70, 50, 30), (10, 27, 9, 14), border_radius=2)
        pygame.draw.rect(surf, (25, 25, 28), (19, 28, 6, 5))
    elif kind == 'shotgun':
        pygame.draw.rect(surf, (90, 60, 35), (6, 22, 30, 6))
        pygame.draw.rect(surf, (40, 40, 44), (30, 20, 14, 4))
        pygame.draw.rect(surf, (40, 40, 44), (30, 26, 14, 4))
        pygame.draw.rect(surf, (60, 40, 25), (4, 28, 10, 8))
    elif kind == 'plasma':
        pygame.draw.rect(surf, (40, 40, 55), (6, 20, 32, 10), border_radius=4)
        pygame.draw.circle(surf, (120, 220, 255), (36, 25), 7)
        pygame.draw.circle(surf, (220, 250, 255), (36, 25), 3)
        pygame.draw.rect(surf, (90, 60, 140), (10, 30, 10, 8))
    elif kind == 'railgun':
        pygame.draw.rect(surf, (60, 60, 65), (4, 22, 40, 6))
        for cx_ in (14, 22, 30):
            pygame.draw.circle(surf, (255, 140, 40), (cx_, 25), 4, 2)
        pygame.draw.rect(surf, (30, 30, 33), (40, 20, 6, 10))
        pygame.draw.rect(surf, (80, 50, 25), (8, 29, 8, 10))
    elif kind == 'log':
        pygame.draw.rect(surf, (35, 38, 45), (10, 8, 28, 34), border_radius=3)
        pygame.draw.rect(surf, (90, 220, 200), (13, 12, 22, 14))
        for ly in (30, 34, 38):
            pygame.draw.rect(surf, (150, 230, 220), (13, ly, 22, 2))
    return surf


PHOTO_TARGET_DEFS = [
    {
        'id': 0, 'kind': 'cursed_suitcase', 'name': 'Pile of 1940s Evacuation Suitcases',
        'cluster_count': 3,
        'note': "A whole heap of abandoned leather suitcases stacked together like a panicked evacuation. Inside are photographs with scratched-out eyes.",
    },
    {
        'id': 1, 'kind': 'blood_altar', 'name': 'Occult Sacrificial Slab & Candelabra',
        'cluster_count': 2,
        'note': "Stone altars slick with fresh crimson surrounded by clusters of ritual candles still burning in a sealed room.",
    },
    {
        'id': 2, 'kind': 'weeping_statue', 'name': 'Row of Weeping Stone Effigies',
        'cluster_count': 2,
        'note': "Cracked marble busts arranged in a shrine, each crying thick dark blood. My camera's face-detection just locked onto all of them.",
    },
    {
        'id': 3, 'kind': 'gas_mask_pile', 'name': 'Stockpile of Soviet GP-5 Gas Masks',
        'cluster_count': 4,
        'note': "Crates overflowing with dozens of rubber GP-5 gas masks. Every filter canister is clogged with black ash from the inside.",
    },
    {
        'id': 4, 'kind': 'cipher_machine', 'name': 'Bank of Self-Typing Cipher Terminals',
        'cluster_count': 2,
        'note': "A desk of rusted rotor cipher machines clattering in unison with no operator, stamping '100,000 WITNESSES' onto paper tape.",
    },
    {
        'id': 5, 'kind': 'bone_ossuary', 'name': 'Catacomb Ossuary Bone Stacks',
        'cluster_count': 3,
        'note': "Thousands of femurs and grinning skulls stacked into dense ossuary walls and bound with copper telegraph wire.",
    },
    {
        'id': 6, 'kind': 'specimen_jar', 'name': 'Row of Bio-Containment Specimen Vats',
        'cluster_count': 3,
        'note': "Multiple cracked glass cylinders filled with glowing formalin. The preserved specimens inside turned to face my camera flash.",
    },
    {
        'id': 7, 'kind': 'floating_chair', 'name': 'Ward of Levitating Restraint Chairs',
        'cluster_count': 3,
        'note': "A whole group of iron interrogation chairs hovering above the floor at impossible angles, straps buckled around unseen figures.",
    },
    {
        'id': 8, 'kind': 'tv_static', 'name': 'Wall of Unplugged Broadcast Monitors',
        'cluster_count': 3,
        'note': "A stack of dead CRT monitors with cut power cords, all flickering to life at once to display my live subscriber count.",
    },
    {
        'id': 9, 'kind': 'ritual_circle', 'name': 'Interlocking Blood Transmutation Sigils',
        'cluster_count': 2,
        'note': "Concentric occult seals burned into the concrete floor. My compass needle spins wildly whenever I step between them.",
    },
    {
        'id': 10, 'kind': 'corpse_recorder', 'name': 'Lost Press Crew & Reel-to-Reel Decks',
        'cluster_count': 2,
        'note': "Remains of an entire previous camera crew clutching press cameras and spinning tape decks. We weren't the first creators baited here.",
    },
    {
        'id': 11, 'kind': 'ghost_skull', 'name': 'Floating Cursed Skull Entity',
        'cluster_count': 2,
        'note': "Captured a crystal-clear shot of the floating skull mid-chatter! Glowing sockets, cervical spine dangling—undeniable proof.",
    },
    {
        'id': 12, 'kind': 'ghost_brute', 'name': 'Reanimated Mangled Corpse',
        'cluster_count': 1,
        'note': "Photographed a reanimated dead body dragging itself down the corridor—torn chest cavity, snapped neck, still moving toward me!",
    },
    {
        'id': 13, 'kind': 'ghost_phantom', 'name': 'Headless Skeletal Sentry',
        'cluster_count': 2,
        'note': "Got a shot of the headless skeleton patrolling with a rifle! Exposed ribcage, severed neck vertebra dripping mist—my chat is losing its mind.",
    },
    {
        'id': 14, 'kind': 'ghost_remnant', 'name': 'Evaporating Black Shadow Figure',
        'cluster_count': 2,
        'note': "Photographed the pitch-black shadow figure as dark energy evaporated upward off its shoulders like boiling smoke!",
    },
]

ENEMY_KIND_TO_PHOTO_ID = {
    'grunt': 11,
    'brute': 12,
    'shooter': 13,
    'charger': 14,
    'turret': 13,
}

ENV_PROP_DEFS = [
    {
        'kind': 'env_stretcher', 'name': 'Cluster of Rusted Medical Gurneys',
        'note': "Rows of rusted hospital stretchers with leather restraints still stained dark brown. Great atmospheric B-roll for the blog.",
    },
    {
        'kind': 'env_barrels', 'name': 'Stockpile of Corroded Biohazard Drums',
        'note': "Leaking steel drums stamped with faded Soviet and German chemical codes. The sludge on the floor is eating through my boot soles.",
    },
    {
        'kind': 'env_boots', 'name': 'Pile of Abandoned Miners\' & Soldiers\' Boots',
        'note': "Dozens of empty leather boots stacked neatly against the wall—as if a whole platoon vanished out of their clothes at once.",
    },
    {
        'kind': 'env_tripods', 'name': 'Broken Film Cameras & Rusted Tripods',
        'note': "Smashed 16mm film cameras and tripods from expeditions in the 1960s and 1980s. Every lens was shattered from the inside.",
    },
]


def make_anomaly_surface(kind):
    size = 64
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size // 2

    if kind == 'cursed_suitcase':
        pygame.draw.rect(surf, (58, 32, 18), (4, 18, 24, 32), border_radius=3)
        pygame.draw.rect(surf, (170, 140, 50), (10, 18, 2, 32))
        pygame.draw.rect(surf, (68, 38, 22), (34, 22, 26, 28), border_radius=3)
        pygame.draw.rect(surf, (185, 150, 55), (42, 22, 2, 28))
        pygame.draw.rect(surf, (88, 48, 26), (12, 30, 38, 26), border_radius=4)
        pygame.draw.rect(surf, (108, 62, 35), (14, 32, 34, 22), border_radius=3)
        pygame.draw.rect(surf, (45, 25, 14), (20, 30, 4, 26))
        pygame.draw.rect(surf, (45, 25, 14), (38, 30, 4, 26))
        pygame.draw.rect(surf, (215, 180, 65), (19, 39, 6, 4))
        pygame.draw.rect(surf, (215, 180, 65), (37, 39, 6, 4))
        pygame.draw.rect(surf, (50, 28, 16), (26, 25, 10, 5), border_radius=2)
        pygame.draw.polygon(surf, (155, 15, 18), [(22, 42), (35, 42), (32, 56), (25, 54)])
        pygame.draw.rect(surf, (225, 215, 190), (44, 32, 8, 5))
    elif kind == 'blood_altar':
        pygame.draw.rect(surf, (85, 85, 92), (6, 36, 52, 20))
        pygame.draw.rect(surf, (115, 115, 122), (4, 32, 56, 6))
        pygame.draw.polygon(surf, (155, 16, 20), [(14, 32), (50, 32), (44, 54), (20, 50)])
        for candle_x, ch_h in ((10, 10), (16, 8), (32, 11), (46, 9), (52, 11)):
            pygame.draw.rect(surf, (230, 220, 195), (candle_x - 2, 32 - ch_h, 4, ch_h))
            pygame.draw.circle(surf, (255, 190, 60), (candle_x, 29 - ch_h), 4)
            pygame.draw.circle(surf, (255, 250, 180), (candle_x, 29 - ch_h), 2)
    elif kind == 'weeping_statue':
        for ox, scale_h in ((20, 0), (44, 4)):
            pygame.draw.rect(surf, (95, 98, 104), (ox - 10, 44, 20, 14))
            pygame.draw.polygon(surf, (150, 154, 160), [(ox - 9, 44), (ox + 9, 44), (ox + 6, 24 + scale_h), (ox - 6, 24 + scale_h)])
            pygame.draw.circle(surf, (175, 180, 186), (ox, 18 + scale_h), 8)
            for ex in (ox - 3, ox + 3):
                pygame.draw.circle(surf, (30, 20, 25), (ex, 17 + scale_h), 2)
                pygame.draw.rect(surf, (165, 15, 20), (ex - 1, 19 + scale_h, 2, 15))
    elif kind == 'gas_mask_pile':
        pygame.draw.rect(surf, (65, 44, 26), (6, 38, 52, 20))
        pygame.draw.rect(surf, (45, 30, 16), (6, 38, 52, 20), 2)
        for ox, oy in ((15, 38), (27, 40), (39, 39), (50, 38), (21, 28), (35, 27)):
            pygame.draw.circle(surf, (135, 140, 130), (ox, oy), 8)
            pygame.draw.circle(surf, (20, 24, 28), (ox - 3, oy - 2), 2)
            pygame.draw.circle(surf, (20, 24, 28), (ox + 3, oy - 2), 2)
            pygame.draw.rect(surf, (58, 74, 58), (ox - 2, oy + 4, 5, 6), border_radius=2)
    elif kind == 'cipher_machine':
        pygame.draw.rect(surf, (55, 42, 30), (4, 34, 56, 22), border_radius=3)
        for ox in (8, 34):
            pygame.draw.rect(surf, (35, 38, 42), (ox, 22, 22, 14))
            for rx in (ox + 4, ox + 10, ox + 16):
                pygame.draw.rect(surf, (180, 185, 190), (rx, 18, 3, 6))
            for lx in range(ox + 3, ox + 20, 5):
                pygame.draw.circle(surf, (255, 210, 70), (lx, 32), 2)
            pygame.draw.polygon(surf, (235, 230, 215), [(ox + 18, 26), (ox + 26, 20), (ox + 27, 23), (ox + 19, 30)])
    elif kind == 'bone_ossuary':
        for fy in (46, 51, 55):
            pygame.draw.rect(surf, (165, 155, 135), (8, fy, 48, 3))
        for sx, sy in ((14, 40), (26, 40), (38, 40), (50, 40), (20, 29), (32, 29), (44, 29)):
            pygame.draw.circle(surf, (215, 205, 185), (sx, sy), 6)
            pygame.draw.circle(surf, (28, 18, 18), (sx - 2, sy), 2)
            pygame.draw.circle(surf, (28, 18, 18), (sx + 2, sy), 2)
    elif kind == 'specimen_jar':
        for ox, h_top in ((8, 16), (23, 10), (39, 14)):
            pygame.draw.rect(surf, (65, 70, 78), (ox, 48, 16, 8), border_radius=2)
            pygame.draw.rect(surf, (50, 195, 140, 160), (ox + 1, h_top, 14, 48 - h_top))
            pygame.draw.rect(surf, (180, 240, 220), (ox + 1, h_top, 14, 48 - h_top), 1)
            pygame.draw.rect(surf, (65, 70, 78), (ox, h_top - 3, 16, 4), border_radius=1)
            pygame.draw.circle(surf, (25, 70, 55), (ox + 8, h_top + 12), 4)
            pygame.draw.circle(surf, (255, 80, 80), (ox + 7, h_top + 11), 1)
            pygame.draw.circle(surf, (255, 80, 80), (ox + 9, h_top + 11), 1)
    elif kind == 'floating_chair':
        for ox, oy in ((10, 14), (34, 8)):
            pygame.draw.ellipse(surf, (50, 20, 60, 100), (ox, 52, 20, 5))
            pygame.draw.line(surf, (110, 70, 38), (ox + 2, oy), (ox + 5, oy + 16), 3)
            pygame.draw.line(surf, (110, 70, 38), (ox + 14, oy - 2), (ox + 17, oy + 14), 3)
            pygame.draw.rect(surf, (130, 82, 44), (ox + 2, oy + 14, 18, 4))
            pygame.draw.line(surf, (95, 58, 30), (ox + 4, oy + 18), (ox + 1, oy + 28), 2)
            pygame.draw.line(surf, (95, 58, 30), (ox + 18, oy + 18), (ox + 21, oy + 28), 2)
    elif kind == 'tv_static':
        for ox, oy, w, h in ((6, 32, 26, 22), (32, 32, 26, 22), (18, 12, 28, 22)):
            pygame.draw.rect(surf, (50, 52, 58), (ox, oy, w, h), border_radius=3)
            pygame.draw.rect(surf, (185, 215, 235), (ox + 3, oy + 3, w - 8, h - 6), border_radius=2)
            pygame.draw.ellipse(surf, (245, 245, 250), (ox + 6, oy + 6, w - 14, h - 12))
            pygame.draw.circle(surf, (180, 30, 40), (ox + w // 2 - 1, oy + h // 2), 3)
            pygame.draw.circle(surf, (15, 15, 20), (ox + w // 2 - 1, oy + h // 2), 1)
    elif kind == 'ritual_circle':
        pygame.draw.ellipse(surf, (180, 20, 30, 180), (4, 34, 56, 24), 3)
        pygame.draw.ellipse(surf, (255, 70, 50, 210), (12, 38, 40, 16), 2)
        pygame.draw.polygon(surf, (255, 90, 60, 190), [(cx, 34), (12, 54), (52, 54)], 2)
        pygame.draw.polygon(surf, (255, 90, 60, 190), [(cx, 58), (12, 38), (52, 38)], 2)
    elif kind == 'corpse_recorder':
        pygame.draw.circle(surf, (210, 200, 180), (20, 28), 8)
        pygame.draw.circle(surf, (25, 20, 20), (18, 27), 2)
        pygame.draw.circle(surf, (25, 20, 20), (22, 27), 2)
        pygame.draw.polygon(surf, (70, 80, 75), [(10, 54), (32, 54), (28, 36), (14, 36)])
        pygame.draw.rect(surf, (45, 48, 54), (32, 36, 22, 18), border_radius=2)
        pygame.draw.circle(surf, (190, 195, 200), (38, 42), 4, 1)
        pygame.draw.circle(surf, (190, 195, 200), (48, 42), 4, 1)
        pygame.draw.circle(surf, (255, 50, 50), (43, 50), 2)
    elif kind == 'ghost_skull':
        return make_floating_skull_surface(1)
    elif kind == 'ghost_brute':
        return make_dead_body_surface(0)
    elif kind == 'ghost_phantom':
        return make_headless_skeleton_surface(0)
    elif kind == 'ghost_remnant':
        return make_evaporating_shadow_surface(1)
    elif kind == 'env_stretcher':
        pygame.draw.rect(surf, (165, 155, 140), (8, 30, 48, 8), border_radius=2)
        pygame.draw.ellipse(surf, (130, 25, 25), (18, 31, 22, 6))
        pygame.draw.line(surf, (90, 95, 100), (12, 38), (12, 54), 2)
        pygame.draw.line(surf, (90, 95, 100), (52, 38), (52, 54), 2)
        pygame.draw.line(surf, (90, 95, 100), (12, 46), (52, 46), 2)
        pygame.draw.circle(surf, (40, 40, 45), (12, 55), 3)
        pygame.draw.circle(surf, (40, 40, 45), (52, 55), 3)
    elif kind == 'env_barrels':
        for ox, oy, col in ((8, 26, (95, 75, 35)), (32, 28, (80, 65, 30)), (20, 30, (115, 90, 40))):
            pygame.draw.rect(surf, col, (ox, oy, 20, 26), border_radius=3)
            pygame.draw.line(surf, (40, 30, 15), (ox, oy + 8), (ox + 19, oy + 8), 2)
            pygame.draw.line(surf, (40, 30, 15), (ox, oy + 17), (ox + 19, oy + 17), 2)
        pygame.draw.ellipse(surf, (60, 210, 90, 190), (14, 52, 36, 8))
    elif kind == 'env_boots':
        for ox, oy in ((10, 42), (20, 44), (30, 41), (40, 44), (24, 34), (34, 35)):
            pygame.draw.rect(surf, (48, 34, 24), (ox, oy, 7, 11), border_radius=2)
            pygame.draw.rect(surf, (38, 26, 18), (ox - 2, oy + 8, 12, 5), border_radius=2)
    elif kind == 'env_tripods':
        for ox in (20, 42):
            pygame.draw.line(surf, (70, 72, 78), (ox, 28), (ox - 10, 56), 2)
            pygame.draw.line(surf, (70, 72, 78), (ox, 28), (ox + 10, 56), 2)
            pygame.draw.line(surf, (70, 72, 78), (ox, 28), (ox, 56), 2)
            pygame.draw.rect(surf, (35, 38, 44), (ox - 7, 20, 14, 9), border_radius=2)
            pygame.draw.circle(surf, (120, 180, 210), (ox + 6, 24), 3)
    return surf


def make_insect_swarm_surfaces():
    frames = []
    size = 64
    for f in range(4):
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for i in range(45):
            base_rng = random.Random(900 + i)
            bx = base_rng.randint(8, 56) + int(math.sin(f * 1.6 + i) * 4)
            by = base_rng.randint(30, 60) + int(math.cos(f * 1.6 + i * 0.7) * 3)
            bx = max(4, min(60, bx))
            by = max(24, min(61, by))
            col = (28, 20, 16, 230) if i % 3 else (48, 32, 22, 240)
            pygame.draw.ellipse(surf, col, (bx - 2, by - 1, 4, 3))
            pygame.draw.line(surf, (18, 12, 10, 200), (bx - 3, by - 2), (bx + 3, by + 2), 1)
            pygame.draw.line(surf, (18, 12, 10, 200), (bx - 3, by + 2), (bx + 3, by - 2), 1)
        frames.append(surf)
    return frames


def make_mouse_surfaces():
    frames = []
    size = 56
    for f in range(2):
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        for rx_off, ry_off, sc in ((0, 0, 1.0), (14, 6, 0.85)):
            bob = 1 if (f + rx_off) % 2 == 1 else 0
            bx = 10 + rx_off
            by = 34 + ry_off - bob
            pygame.draw.ellipse(surf, (62, 58, 56), (bx, by, int(16 * sc), int(8 * sc)))
            pygame.draw.polygon(surf, (70, 65, 62), [
                (bx + int(14 * sc), by + 1),
                (bx + int(22 * sc), by + int(4 * sc)),
                (bx + int(14 * sc), by + int(7 * sc))
            ])
            pygame.draw.circle(surf, (95, 75, 75), (bx + int(13 * sc), by), 2)
            pygame.draw.circle(surf, (240, 40, 40), (bx + int(18 * sc), by + 2), 1)
            tail_y = by + 4 + (2 if f == 1 else -1)
            pygame.draw.line(surf, (130, 95, 95), (bx, by + 4), (max(1, bx - 9), tail_y), 2)
        frames.append(surf)
    return frames


WEAPON_DEFS = [
    {
        'id': 'pistol', 'name': 'PISTOL', 'mode': 'hitscan', 'sfx': 'shot_pistol',
        'mag_size': 8, 'max_reserve': 16, 'pickup_ammo': 6, 'start_reserve': 4,
        'cooldown': 0.32, 'reload_time': 1.1,
        'dmg_min': 17, 'dmg_max': 25,
        'pellets': 1, 'spread': 0.14,
        'recoil': 0.45, 'shake': 1.2, 'flash': (255, 215, 140), 'flash_amt': 0.35,
    },
    {
        'id': 'shotgun', 'name': 'SHOTGUN', 'mode': 'hitscan', 'sfx': 'shot_shotgun',
        'mag_size': 4, 'max_reserve': 8, 'pickup_ammo': 2, 'start_reserve': 2,
        'cooldown': 0.85, 'reload_time': 1.9,
        'dmg_min': 8, 'dmg_max': 13,
        'pellets': 6, 'spread': 0.30,
        'falloff': (4.0, 9.0, 0.35),
        'knockback': 1.1, 'pump_delay': 0.42,
        'recoil': 1.0, 'shake': 5.5, 'flash': (255, 190, 100), 'flash_amt': 0.6,
    },
    {
        'id': 'plasma', 'name': 'PLASMA CANNON', 'mode': 'projectile', 'sfx': 'shot_plasma',
        'mag_size': 3, 'max_reserve': 6, 'pickup_ammo': 2, 'start_reserve': 1,
        'cooldown': 0.60, 'reload_time': 2.1,
        'dmg_min': 55, 'dmg_max': 70,
        'pellets': 1, 'spread': 0.12,
        'proj_speed': 12.0, 'blast_radius': 1.5, 'blast_scale': 0.5, 'slow': (2.4, 0.40),
        'recoil': 0.6, 'shake': 2.0, 'flash': (110, 210, 255), 'flash_amt': 0.55,
    },
    {
        'id': 'railgun', 'name': 'RAILGUN', 'mode': 'beam', 'sfx': 'shot_railgun',
        'mag_size': 2, 'max_reserve': 4, 'pickup_ammo': 1, 'start_reserve': 1,
        'cooldown': 0.70, 'reload_time': 2.2,
        'dmg_min': 120, 'dmg_max': 140,
        'pellets': 1, 'spread': 0.06,
        'charge': 0.50, 'pierce_falloff': 0.85, 'charge_move': 0.55,
        'recoil': 1.2, 'shake': 11.0, 'flash': (190, 215, 255), 'flash_amt': 0.8,
    },
]

WEAPON_FOUND_IN_SECTOR = {'pistol': 0, 'shotgun': 2, 'plasma': 6, 'railgun': 11}
WEAPON_BY_ID = {w['id']: w for w in WEAPON_DEFS}


def weapon_index(weapon_id):
    return next(i for i, w in enumerate(WEAPON_DEFS) if w['id'] == weapon_id)


def _alpha(a):
    return max(0, min(255, int(a)))


def make_fx_surfaces():
    fx = {}
    S = 64
    c = S // 2

    def blank():
        return pygame.Surface((S, S), pygame.SRCALPHA)

    s = blank()
    pygame.draw.circle(s, (60, 170, 255, 70), (c, c), 28)
    pygame.draw.circle(surf := s, (100, 210, 255, 150), (c, c), 20)
    pygame.draw.circle(s, (170, 240, 255, 230), (c, c), 12)
    pygame.draw.circle(s, (255, 255, 255, 255), (c, c), 6)
    fx['plasma_orb'] = [s]

    fx['plasma_trail'] = []
    for r, a in ((16, 150), (12, 95), (8, 45)):
        s = blank()
        pygame.draw.circle(s, (90, 200, 255, _alpha(a * 0.5)), (c, c), r + 6)
        pygame.draw.circle(s, (170, 235, 255, _alpha(a)), (c, c), r)
        fx['plasma_trail'].append(s)

    fx['plasma_hit'] = []
    for i in range(5):
        u = i / 4.0
        s = blank()
        pygame.draw.circle(s, (80, 190, 255, _alpha(90 * (1 - u))), (c, c), int(14 + 16 * u))
        pygame.draw.circle(s, (170, 235, 255, _alpha(230 * (1 - u))), (c, c), int(10 + 14 * u), max(2, int(6 - 4 * u)))
        pygame.draw.circle(s, (255, 255, 255, _alpha(255 * (1 - u * 1.1))), (c, c), max(2, int(12 * (1 - u))))
        fx['plasma_hit'].append(s)

    return fx


# ----------------------------------------------------------------------------------
# DETAILED WEAPON VIEWMODELS & ANIMATED HANDS / FINGERS (8 FRAMES PER WEAPON!)
# ----------------------------------------------------------------------------------
# Frame indices for each weapon:
#   0: Idle frame A (hands wrapped on grip, subtle finger posture)
#   1: Shoot frame 1 (Muzzle blast, slide/bolt blown back, brass shell ejecting, wrist kick)
#   2: Shoot frame 2 (Secondary flash, slide halfway back, smoke curl)
#   3: Shoot frame 3 (Slide locks forward, hand re-centers)
#   4: Reload Stage 1 (Gun tilts; left hand reaches in & ejects old magazine / opens breech)
#   5: Reload Stage 2 (Left hand brings fresh magazine / shells / plasma core up into receiver!)
#   6: Reload Stage 3 (Left hand grips slide / pump / bolt and racks it back with thumb/fingers!)
#   7: Weapon Switch / Ready Hand Pose (Left hand steadies barrel as gun is raised/lowered)

def make_gun_surfaces(kind='pistol'):
    """Return 8 detailed, shaded weapon + animated hand frames per gun:
    0: idle_0, 1: fire_0, 2: fire_1, 3: fire_2,
    4: reload_eject, 5: reload_insert, 6: reload_rack, 7: switch_pose"""
    frames = []
    w, h = 260, 260
    for i in range(8):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        is_fire = i in (1, 2, 3)
        recoil_y = {1: 18, 2: 10, 3: 4}.get(i, 0)
        slide_back = {1: 16, 2: 9, 6: 14}.get(i, 0)
        tilt_x = {4: -18, 5: -14, 6: -6, 7: 12}.get(i, 0)
        base_y = h - 142 + recoil_y + ({4: 10, 5: 6, 7: 16}.get(i, 0))
        cx = w // 2 + tilt_x
        f_shift = -2 if i in (1, 2) else (1 if i == 7 else 0)

        if kind == 'pistol':
            # Muzzle flash on fire frames (drawn behind barrel tip)
            if is_fire:
                fr = {1: 44, 2: 28, 3: 14}[i]
                fx_c, fy_c = cx, base_y - 54
                pygame.draw.circle(surf, (255, 140, 30, 150), (fx_c, fy_c), fr)
                pygame.draw.polygon(surf, (255, 220, 110, 230), [
                    (fx_c, fy_c - fr), (fx_c + 12, fy_c - 10), (fx_c + fr, fy_c),
                    (fx_c + 12, fy_c + 10), (fx_c, fy_c + fr // 2),
                    (fx_c - 12, fy_c + 10), (fx_c - fr, fy_c), (fx_c - 12, fy_c - 10)
                ])
                pygame.draw.circle(surf, (255, 255, 240), (fx_c, fy_c), max(4, fr // 3))

            # Lower polymer frame & Picatinny accessory rail
            pygame.draw.rect(surf, (36, 38, 44), (cx - 18, base_y - 34, 36, 56), border_radius=4)
            # Grip frame extending down into the right hand
            pygame.draw.polygon(surf, (28, 30, 35), [
                (cx - 16, base_y + 10), (cx + 16, base_y + 10),
                (cx + 22, base_y + 78), (cx - 12, base_y + 78)
            ])
            # Stippled grip panels
            pygame.draw.polygon(surf, (44, 46, 52), [
                (cx - 12, base_y + 16), (cx + 12, base_y + 16),
                (cx + 16, base_y + 68), (cx - 8, base_y + 68)
            ])

            # Reload Stage 1 (frame 4): Ejecting spent magazine dropping down!
            if i == 4:
                pygame.draw.rect(surf, (60, 62, 68), (cx - 8, base_y + 62, 18, 42), border_radius=2)
                pygame.draw.circle(surf, (215, 175, 55), (cx + 1, base_y + 64), 4)

            # Reload Stage 2 (frame 5): Left hand inserting fresh brass-loaded magazine!
            if i == 5:
                pygame.draw.rect(surf, (70, 74, 82), (cx - 10, base_y + 34, 18, 40), border_radius=2)
                pygame.draw.ellipse(surf, (230, 190, 65), (cx - 8, base_y + 31, 14, 7))

            # Exposed steel barrel (visible when slide blows back on fire or rack!)
            pygame.draw.rect(surf, (95, 100, 108), (cx - 9, base_y - 52, 18, 28), border_radius=2)
            pygame.draw.ellipse(surf, (15, 16, 20), (cx - 6, base_y - 54, 12, 6))

            # Reciprocating Machined Steel Slide (moves down by `slide_back` when firing or racking!)
            sy = base_y - 44 + slide_back
            pygame.draw.rect(surf, (68, 73, 82), (cx - 19, sy, 38, 62), border_radius=5)
            pygame.draw.rect(surf, (96, 102, 114), (cx - 15, sy + 2, 12, 58), border_radius=3)
            pygame.draw.rect(surf, (45, 48, 55), (cx + 5, sy + 2, 11, 58), border_radius=3)
            # Slide serrations
            for ser_y in range(sy + 32, sy + 54, 4):
                pygame.draw.line(surf, (35, 38, 44), (cx - 17, ser_y), (cx - 11, ser_y), 2)
                pygame.draw.line(surf, (35, 38, 44), (cx + 11, ser_y), (cx + 17, ser_y), 2)
            # Ejection port & glowing green tritium rear/front night sights
            pygame.draw.rect(surf, (25, 26, 30), (cx - 8, sy + 10, 16, 14), border_radius=2)
            pygame.draw.circle(surf, (90, 255, 120), (cx, sy + 3), 2)
            pygame.draw.circle(surf, (90, 255, 120), (cx - 8, sy + 56), 2)
            pygame.draw.circle(surf, (90, 255, 120), (cx + 8, sy + 56), 2)

            # Flying brass shell casing on fire frames 1 & 2!
            if i in (1, 2):
                sx_c = cx + (26 if i == 1 else 44)
                sy_c = sy - (6 if i == 1 else 18)
                pygame.draw.rect(surf, (235, 195, 70), (sx_c, sy_c, 10, 5), border_radius=1)
                pygame.draw.rect(surf, (255, 235, 150), (sx_c + 2, sy_c + 1, 6, 2))



        elif kind == 'shotgun':
            if is_fire:
                fr = {1: 54, 2: 34, 3: 16}[i]
                for ox in (cx - 10, cx + 10):
                    pygame.draw.circle(surf, (255, 130, 25, 160), (ox, base_y - 72), fr // 2 + 8)
                    pygame.draw.circle(surf, (255, 225, 130), (ox, base_y - 72), fr // 3 + 4)

            # Heavy twin steel barrels with ventilated rib & brass bead sight
            barrel_drop = 14 if i in (4, 5) else 0
            by0 = base_y - 68 + barrel_drop
            pygame.draw.rect(surf, (38, 41, 46), (cx - 20, by0, 19, 96), border_radius=3)
            pygame.draw.rect(surf, (38, 41, 46), (cx + 1, by0, 19, 96), border_radius=3)
            # Metallic cylindrical highlights down both barrels
            pygame.draw.line(surf, (105, 112, 122), (cx - 13, by0 + 2), (cx - 13, by0 + 92), 3)
            pygame.draw.line(surf, (105, 112, 122), (cx + 8, by0 + 2), (cx + 8, by0 + 92), 3)
            # Muzzle bores
            pygame.draw.circle(surf, (14, 15, 18), (cx - 10, by0 + 4), 6)
            pygame.draw.circle(surf, (14, 15, 18), (cx + 10, by0 + 4), 6)
            pygame.draw.circle(surf, (235, 195, 70), (cx, by0 + 3), 2)

            # Ribbed walnut/polymer pump forend (slides back on frame 2 & frame 6!)
            pump_off = 18 if i in (2, 6) else 0
            py_pump = by0 + 44 + pump_off
            pygame.draw.rect(surf, (88, 52, 28), (cx - 23, py_pump, 46, 36), border_radius=5)
            for gy in range(py_pump + 5, py_pump + 32, 5):
                pygame.draw.line(surf, (52, 30, 15), (cx - 21, gy), (cx + 21, gy), 2)

            # Steel receiver & walnut stock
            pygame.draw.rect(surf, (62, 66, 74), (cx - 22, base_y + 18, 44, 38), border_radius=4)
            pygame.draw.polygon(surf, (96, 56, 30), [
                (cx - 20, base_y + 48), (cx + 20, base_y + 48),
                (cx + 28, h), (cx - 16, h)
            ])

            # Reload Stage 1 & 2 (frames 4 & 5): Visible red 12-gauge brass shotgun shells!
            if i == 4:
                # Spent red shells ejecting upward
                for sx_s, sy_s in ((cx - 26, base_y - 6), (cx + 18, base_y - 12)):
                    pygame.draw.rect(surf, (205, 30, 35), (sx_s, sy_s, 9, 18), border_radius=1)
                    pygame.draw.rect(surf, (230, 190, 65), (sx_s, sy_s + 13, 9, 6))
            elif i == 5:
                # Left hand thumbing two fresh red 12-gauge shells into the open breech!
                for sx_s in (cx - 12, cx + 4):
                    pygame.draw.rect(surf, (215, 32, 36), (sx_s, base_y + 4, 9, 20), border_radius=1)
                    pygame.draw.rect(surf, (235, 195, 70), (sx_s, base_y + 18, 9, 6))


        elif kind == 'plasma':
            if is_fire:
                fr = {1: 52, 2: 34, 3: 18}[i]
                pygame.draw.circle(surf, (70, 195, 255, 165), (cx, base_y - 76), fr)
                pygame.draw.circle(surf, (200, 248, 255), (cx, base_y - 76), fr // 2)

            # Experimental electromagnetic plasma chassis
            pygame.draw.rect(surf, (42, 46, 58), (cx - 24, base_y - 64, 48, 96), border_radius=7)
            pygame.draw.rect(surf, (68, 74, 92), (cx - 18, base_y - 60, 14, 88), border_radius=4)
            # Vented magnetic containment prongs at muzzle
            pygame.draw.rect(surf, (85, 92, 110), (cx - 20, base_y - 78, 10, 18), border_radius=2)
            pygame.draw.rect(surf, (85, 92, 110), (cx + 10, base_y - 78, 10, 18), border_radius=2)
            pygame.draw.circle(surf, (95, 225, 255), (cx, base_y - 68), 11)
            pygame.draw.circle(surf, (230, 255, 255), (cx, base_y - 68), 5)

            # Glowing cyan plasma core chamber (ejects in frame 4, inserted by hand in frame 5!)
            core_off_x = -26 if i == 4 else (-12 if i == 5 else 0)
            core_off_y = 14 if i == 4 else (6 if i == 5 else 0)
            pygame.draw.rect(surf, (25, 40, 52), (cx - 12, base_y - 36, 24, 38), border_radius=4)
            pygame.draw.rect(surf, (70, 215, 255),
                             (cx - 9 + core_off_x, base_y - 33 + core_off_y, 18, 32), border_radius=4)
            for rib_y in range(base_y - 30, base_y - 4, 7):
                pygame.draw.line(surf, (30, 34, 44), (cx - 14, rib_y), (cx + 14, rib_y), 2)

            # Rear digital charge readout & grip
            pygame.draw.rect(surf, (22, 32, 38), (cx - 14, base_y + 10, 28, 14), border_radius=2)
            bar_col = (255, 95, 95) if i == 4 else (90, 245, 220)
            pygame.draw.rect(surf, bar_col, (cx - 11, base_y + 13, 22 if i != 4 else 6, 8), border_radius=1)



        else:  # 'railgun'
            if is_fire:
                fr = {1: 60, 2: 38, 3: 20}[i]
                pygame.draw.circle(surf, (130, 190, 255, 180), (cx, base_y - 92), fr)
                pygame.draw.circle(surf, (255, 255, 255), (cx, base_y - 92), fr // 2)

            # Dual parallel magnetic accelerator rails with central plasma gap
            pygame.draw.rect(surf, (34, 36, 42), (cx - 22, base_y - 92, 16, 118), border_radius=2)
            pygame.draw.rect(surf, (34, 36, 42), (cx + 6, base_y - 92, 16, 118), border_radius=2)
            pygame.draw.line(surf, (105, 112, 124), (cx - 16, base_y - 88), (cx - 16, base_y + 20), 2)
            pygame.draw.line(surf, (105, 112, 124), (cx + 12, base_y - 88), (cx + 12, base_y + 20), 2)

            # Glowing copper-orange induction coils & electric arcs between rails
            for cy_coil in (base_y - 76, base_y - 48, base_y - 20):
                pygame.draw.rect(surf, (235, 125, 35), (cx - 25, cy_coil, 50, 9), border_radius=3)
                pygame.draw.rect(surf, (255, 195, 90), (cx - 22, cy_coil + 2, 44, 3), border_radius=1)
                pygame.draw.line(surf, (150, 225, 255), (cx - 6, cy_coil + 4), (cx + 6, cy_coil + 4), 2)

            # Heavy receiver housing & breech block
            pygame.draw.rect(surf, (52, 56, 64), (cx - 26, base_y + 8, 52, 46), border_radius=5)
            if i == 5:
                # Heavy tungsten-core rail slug slotting into the breech
                pygame.draw.rect(surf, (210, 175, 80), (cx - 8, base_y - 6, 16, 28), border_radius=3)

        frames.append(surf)
    return frames


# ----------------------------------------------------------------------------------
# PROCEDURAL SOUND SYNTHESIS
# ----------------------------------------------------------------------------------

def _mixer_rate():
    init = pygame.mixer.get_init()
    return init[0] if init else MIXER_RATE


def _mixer_channels():
    init = pygame.mixer.get_init()
    return init[2] if init else 2


def _to_sound(mono, peak=0.9, fade=True):
    mono = np.array(mono, dtype=np.float64)
    top = float(np.max(np.abs(mono))) if mono.size else 0.0
    if top > 1e-9:
        mono = mono / top * peak
    if fade and mono.size > 8:
        sr = _mixer_rate()
        a = min(mono.size // 4, max(1, int(0.002 * sr)))
        b = min(mono.size // 4, max(1, int(0.030 * sr)))
        mono[:a] *= np.linspace(0.0, 1.0, a)
        mono[-b:] *= np.linspace(1.0, 0.0, b)
    mono = np.clip(mono, -1.0, 1.0)
    data = np.stack([mono, mono], axis=-1) if _mixer_channels() >= 2 else mono
    audio = np.ascontiguousarray((data * 32767).astype(np.int16))
    return pygame.sndarray.make_sound(audio)


def synth_sound(freq_env, duration, sample_rate=None, noise_amt=0.0, decay=6.0, volume=0.5):
    if sample_rate is None:
        sample_rate = _mixer_rate()
    n = int(sample_rate * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    if callable(freq_env):
        freq = freq_env(t)
    else:
        freq = freq_env
    phase = 2 * np.pi * np.cumsum(freq) / sample_rate
    wave = np.sin(phase)
    if noise_amt > 0:
        wave = wave * (1 - noise_amt) + (np.random.uniform(-1, 1, n) * noise_amt)
    env = np.exp(-decay * t)
    wave *= env * volume
    stereo = np.stack([wave, wave], axis=-1)
    audio = (stereo * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(audio))


def _phase(freq, sr):
    return 2 * np.pi * np.cumsum(freq) / sr


def _smooth(x, width):
    return np.convolve(x, np.ones(width) / width, mode='same')


def _fft_noise(n, sr, rng, shape):
    spec = rng.normal(size=n // 2 + 1) + 1j * rng.normal(size=n // 2 + 1)
    spec *= shape(np.fft.rfftfreq(n, 1.0 / sr))
    out = np.fft.irfft(spec, n)
    return out / (np.max(np.abs(out)) + 1e-9)


def _echo(wave, sr, taps, tail=0.9):
    longest = max([d for d, _ in taps] + [tail])
    out = np.zeros(len(wave) + int(longest * sr))
    out[:len(wave)] += wave
    for delay, gain in taps:
        d = int(delay * sr)
        out[d:d + len(wave)] += gain * wave
    return out


def make_drone(variant=0, dur=8.0):
    sr = _mixer_rate()
    n = int(sr * dur)
    t = np.arange(n) / sr
    rng = np.random.default_rng(900 + variant)
    base = (55.0, 49.0)[variant % 2]
    two_pi = 2 * np.pi

    def loopf(hz):
        return max(1, round(hz * dur)) / dur

    tone = (0.90 * np.sin(two_pi * loopf(base) * t)
            + 0.50 * np.sin(two_pi * loopf(base * 2.0) * t + 0.7)
            + 0.28 * np.sin(two_pi * loopf(base * 3.0) * t + 1.9))
    pad = (0.16 * np.sin(two_pi * loopf(base * 5.66) * t)
           + 0.14 * np.sin(two_pi * loopf(base * 5.66 + 1.5) * t + 0.5))
    swell = 0.75 + 0.25 * np.sin(two_pi * t / dur + 0.4)
    wind = _fft_noise(n, sr, rng,
                      lambda f: (1.0 / (1.0 + (f / 180.0) ** 2)) * (0.3 + np.exp(-((f - 420.0) / 160.0) ** 2)))
    wind *= 0.6 + 0.4 * np.sin(two_pi * 2 * t / dur + 1.3)
    return _to_sound((tone * 0.55 + pad * 0.50 + wind * 0.55) * swell, peak=0.55, fade=False)


def make_heartbeat(kind):
    sr = _mixer_rate()
    dur = 0.35 if kind == 'lub' else 0.30
    n = int(sr * dur)
    t = np.arange(n) / sr
    f0, f1 = (62.0, 38.0) if kind == 'lub' else (80.0, 52.0)
    freq = f1 + (f0 - f1) * np.exp(-t * 28)
    ph = _phase(freq, sr)
    wave = np.sin(ph) + 0.45 * np.sin(2 * ph) + 0.30 * np.sin(3 * ph)
    wave *= np.exp(-t * (16 if kind == 'lub' else 20)) * np.minimum(1.0, t / 0.004)
    return _to_sound(wave, peak=0.9 if kind == 'lub' else 0.7)


def make_jumpscare():
    sr = _mixer_rate()
    n = int(sr * 1.5)
    t = np.arange(n) / sr
    rng = np.random.default_rng(666)
    glide = 1.0 + 0.55 * np.minimum(t / 0.35, 1.0)
    vib = 1.0 + 0.04 * np.sin(2 * np.pi * 38 * t)
    shriek = np.zeros(n)
    for ratio, amp in ((1.0, 1.0), (1.41, 0.8), (1.89, 0.65), (2.52, 0.5), (3.17, 0.4)):
        shriek += amp * np.sin(_phase(780.0 * ratio * glide * vib, sr))
    shriek /= 3.4
    hiss = np.diff(rng.normal(size=n + 1))
    hiss /= np.max(np.abs(hiss))
    shriek += 0.45 * hiss
    env_s = np.minimum(1.0, t / 0.004) * np.exp(-2.6 * np.maximum(t - 0.25, 0.0))
    boom = np.sin(_phase(28.0 + 55.0 * np.exp(-t * 9), sr)) * np.exp(-3.2 * t)
    thump = _smooth(rng.normal(size=n), 40)
    boom += 6.0 * thump * np.exp(-14 * t)
    mix = shriek * env_s * 0.8 + boom
    return _to_sound(np.tanh(2.0 * mix), peak=0.88)


def make_sting():
    sr = _mixer_rate()
    n = int(sr * 1.1)
    t = np.arange(n) / sr
    wave = np.zeros(n)
    for f, a in ((311.1, 1.0), (329.6, 0.9), (466.2, 0.6), (622.3, 0.35)):
        wave += a * np.sin(_phase(f * (1.0 - 0.03 * t), sr))
    wave *= 0.65 + 0.35 * np.sin(2 * np.pi * 7.0 * t)
    wave *= np.minimum(1.0, t / 0.02) * np.exp(-2.8 * t)
    rng = np.random.default_rng(31)
    wave += 0.25 * _smooth(rng.normal(size=n), 6) * np.exp(-9 * t)
    return _to_sound(wave, peak=0.6)


def make_dvloper_splash_sound():
    sr = _mixer_rate()
    dur = 2.6
    n = int(sr * dur)
    t = np.arange(n) / sr
    rng = np.random.default_rng(501)
    sub = np.sin(2 * np.pi * 46.0 * t) * np.sin(np.pi * t / dur) ** 0.7
    chime = (0.6 * np.sin(2 * np.pi * 233.1 * t) * np.exp(-t * 1.4)
             + 0.5 * np.sin(2 * np.pi * 246.9 * t) * np.exp(-t * 1.5)
             + 0.35 * np.sin(2 * np.pi * 554.4 * t) * np.exp(-t * 2.1))
    creak = _smooth(rng.normal(size=n), 12) * np.exp(-((t - 0.8) / 0.45) ** 2) * 0.8
    out = _echo(sub * 0.8 + chime * 0.7 + creak, sr, ((0.28, 0.4), (0.62, 0.22)), tail=0.5)
    return _to_sound(out, peak=0.78)


def make_type_key():
    sr = _mixer_rate()
    n = int(sr * 0.038)
    t = np.arange(n) / sr
    rng = np.random.default_rng(712)
    click = np.diff(rng.normal(size=n + 1)) * np.exp(-t * 170)
    tone = 0.45 * np.sin(2 * np.pi * 1650.0 * t) * np.exp(-t * 140)
    return _to_sound(click + tone, peak=0.36)


def make_whisper():
    sr = _mixer_rate()
    dur = 2.0
    n = int(sr * dur)
    t = np.arange(n) / sr
    rng = np.random.default_rng(77)
    spec = np.fft.rfft(rng.normal(size=n))
    f = np.fft.rfftfreq(n, 1.0 / sr)
    band = (np.exp(-((f - 1800) / 700.0) ** 2) + 0.7 * np.exp(-((f - 3600) / 900.0) ** 2)
            + 0.4 * np.exp(-((f - 700) / 300.0) ** 2))
    sig = np.fft.irfft(spec * band, n)
    env = np.zeros(n)
    for c, w, a in ((0.25, .09, .8), (0.55, .07, 1.0), (0.90, .10, .7), (1.25, .08, .9), (1.55, .12, .6)):
        env += a * np.exp(-((t - c) / w) ** 2)
    env *= np.minimum(1.0, t / 0.1) * np.minimum(1.0, (dur - t) / 0.2)
    return _to_sound(sig * env, peak=0.5)


def make_distant_scream():
    sr = _mixer_rate()
    dur = 1.8
    n = int(sr * dur)
    t = np.arange(n) / sr
    rng = np.random.default_rng(12)
    f = 520.0 + 730.0 * np.sin(np.pi * np.clip(t / 1.2, 0, 1)) ** 1.3
    f *= 1.0 + 0.03 * np.sin(2 * np.pi * 6.5 * t)
    ph = _phase(f, sr)
    voice = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.3 * np.sin(3 * ph)
    voice += 0.15 * np.diff(rng.normal(size=n + 1))
    voice *= np.sin(np.pi * t / dur) ** 1.5
    out = _echo(voice, sr, ((0.22, 0.45), (0.47, 0.25), (0.75, 0.12)), tail=0.9)
    return _to_sound(_smooth(out, 5), peak=0.45)


def make_creak():
    sr = _mixer_rate()
    dur = 1.8
    n = int(sr * dur)
    t = np.arange(n) / sr
    rng = np.random.default_rng(55)
    f = 90.0 + 50.0 * np.sin(np.pi * t / dur)
    saw = 2.0 * ((np.cumsum(f) / sr) % 1.0) - 1.0
    soft = _smooth(saw, 10)
    stick = 0.55 + 0.45 * np.sign(np.sin(2 * np.pi * (9 + 6 * t) * t))
    env = np.sin(np.pi * t / dur) ** 0.8
    wave = soft * stick * env + 0.10 * rng.normal(size=n) * env
    return _to_sound(wave, peak=0.5)


def make_thud():
    sr = _mixer_rate()
    n = int(sr * 1.2)
    t = np.arange(n) / sr
    rng = np.random.default_rng(8)
    boom = np.sin(_phase(48.0 + 40.0 * np.exp(-t * 14), sr)) * np.exp(-5 * t)
    boom += 4.0 * _smooth(rng.normal(size=n), 30) * np.exp(-18 * t)
    out = _echo(boom, sr, ((0.18, 0.35), (0.40, 0.18)), tail=0.6)
    return _to_sound(out, peak=0.8)


def make_roar():
    sr = _mixer_rate()
    dur = 0.9
    n = int(sr * dur)
    t = np.arange(n) / sr
    rng = np.random.default_rng(404)
    f = 85.0 - 25.0 * t / dur + 6.0 * np.sin(2 * np.pi * 11 * t)
    ph = _phase(f, sr)
    wave = sum(np.sin(k * ph) / k for k in range(1, 11))
    wave *= 1.0 + 0.5 * np.sin(2 * np.pi * 28 * t)
    wave += 0.6 * _smooth(rng.normal(size=n), 6)
    wave *= np.minimum(1.0, t / 0.03) * np.exp(-2.2 * t)
    return _to_sound(np.tanh(1.6 * wave), peak=0.7)


def make_enemy_die():
    sr = _mixer_rate()
    n = int(sr * 0.8)
    t = np.arange(n) / sr
    rng = np.random.default_rng(909)
    ph = _phase(45.0 + 320.0 * np.exp(-t * 3.2), sr)
    wave = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.35 * _smooth(rng.normal(size=n), 4)
    wave *= np.exp(-3.5 * t) * np.minimum(1.0, t / 0.005)
    return _to_sound(wave, peak=0.6)


def make_log_chime():
    sr = _mixer_rate()
    n = int(sr * 2.2)
    t = np.arange(n) / sr
    wave = np.zeros(n)
    for k, (ratio, amp) in enumerate(((1.0, 1.0), (2.76, 0.6), (5.4, 0.35), (8.93, 0.2))):
        wave += amp * np.sin(2 * np.pi * 392.0 * ratio * t) * np.exp(-(1.6 + 0.8 * k) * t)
    out = _echo(wave, sr, ((0.25, 0.4), (0.5, 0.2)), tail=0.6)
    return _to_sound(out, peak=0.5)


def make_camera_shutter():
    sr = _mixer_rate()
    n = int(sr * 0.42)
    t = np.arange(n) / sr
    rng = np.random.default_rng(707)
    c1 = _smooth(rng.normal(size=n), 3) * np.exp(-t * 95)
    c2 = np.zeros(n)
    i2 = int(0.065 * sr)
    c2[i2:] = _smooth(rng.normal(size=n - i2), 3) * np.exp(-np.arange(n - i2) / sr * 85)
    whine = 0.25 * np.sin(_phase(1400.0 + 2600.0 * (t / 0.42), sr)) * np.exp(-t * 4.5)
    return _to_sound(c1 + 0.85 * c2 + whine, peak=0.75)


def make_pencil_scribble():
    sr = _mixer_rate()
    n = int(sr * 0.36)
    t = np.arange(n) / sr
    rng = np.random.default_rng(808)
    noise = _smooth(np.diff(rng.normal(size=n + 1)), 4)
    env = (np.exp(-((t - 0.08) / 0.04) ** 2)
           + 0.8 * np.exp(-((t - 0.19) / 0.05) ** 2)
           + 0.7 * np.exp(-((t - 0.29) / 0.04) ** 2))
    return _to_sound(noise * env, peak=0.42)


def make_skitter():
    sr = _mixer_rate()
    n = int(sr * 0.30)
    t = np.arange(n) / sr
    rng = np.random.default_rng(515)
    squeak = np.sin(_phase(2600.0 + 600.0 * np.sin(2 * np.pi * 18 * t), sr)) * np.exp(-((t - 0.07) / 0.03) ** 2)
    patter = rng.normal(size=n) * (0.5 + 0.5 * np.sin(2 * np.pi * 35 * t)) * np.exp(-t * 10)
    return _to_sound(0.45 * squeak + 0.55 * patter, peak=0.35)


def _crack(n, sr, rng, decay):
    c = np.diff(rng.normal(size=n + 1))
    c /= (np.max(np.abs(c)) + 1e-9)
    return c * np.exp(-np.arange(n) / sr * decay)


def make_shot_pistol():
    sr = _mixer_rate(); n = int(sr * 0.22); t = np.arange(n) / sr
    rng = np.random.default_rng(101)
    body = np.sin(_phase(260.0 + 900.0 * np.exp(-t * 18), sr)) * np.exp(-t * 22)
    wave = 0.95 * _crack(n, sr, rng, 60) + 0.8 * body
    return _to_sound(np.tanh(1.5 * wave), peak=0.8)


def make_shot_shotgun():
    sr = _mixer_rate(); n = int(sr * 0.55); t = np.arange(n) / sr
    rng = np.random.default_rng(102)
    boom = np.sin(_phase(55.0 + 110.0 * np.exp(-t * 14), sr)) * np.exp(-t * 7)
    blast = _smooth(rng.normal(size=n), 8) * np.exp(-t * 16) * 2.2
    wave = 1.1 * boom + blast + 0.8 * _crack(n, sr, rng, 40)
    out = _echo(wave, sr, ((0.07, 0.30), (0.16, 0.15)), tail=0.25)
    return _to_sound(np.tanh(1.4 * out), peak=0.95)


def make_pump():
    sr = _mixer_rate(); n = int(sr * 0.32); t = np.arange(n) / sr
    rng = np.random.default_rng(103)
    wave = np.zeros(n)
    for t0, amp in ((0.0, 1.0), (0.15, 0.85)):
        i0 = int(t0 * sr)
        m = n - i0
        tt = np.arange(m) / sr
        wave[i0:] += amp * (_smooth(rng.normal(size=m), 4) * np.exp(-tt * 90)
                            + 0.5 * np.sin(2 * np.pi * 1900 * tt) * np.exp(-tt * 70))
    return _to_sound(wave, peak=0.55)


def make_shot_plasma():
    sr = _mixer_rate(); n = int(sr * 0.45); t = np.arange(n) / sr
    rng = np.random.default_rng(105)
    f = (300.0 + 2200.0 * np.exp(-t * 5)) * (1.0 + 0.15 * np.sin(2 * np.pi * 38 * t))
    ph = _phase(f, sr)
    wave = np.sin(ph) + 0.5 * np.sin(2 * ph) * np.exp(-t * 3)
    wave += 0.25 * _crack(n, sr, rng, 12) * 4
    wave *= np.minimum(1.0, t / 0.003) * np.exp(-t * 5)
    return _to_sound(wave, peak=0.65)


def make_plasma_hit():
    sr = _mixer_rate(); n = int(sr * 0.40); t = np.arange(n) / sr
    rng = np.random.default_rng(106)
    fizz = _smooth(np.diff(rng.normal(size=n + 1)), 3) * np.exp(-t * 9)
    zap = np.sin(_phase(200.0 + 900.0 * np.exp(-t * 8), sr)) * np.exp(-t * 10)
    return _to_sound(fizz / (np.max(np.abs(fizz)) + 1e-9) * 0.9 + zap, peak=0.6)


def make_rail_charge():
    sr = _mixer_rate(); n = int(sr * 0.55); t = np.arange(n) / sr
    x = np.clip(t / 0.5, 0, 1)
    ph = _phase(180.0 + 2300.0 * x ** 2, sr)
    wave = (np.sin(ph) * (0.2 + 0.8 * x) + 0.3 * np.sin(2 * ph) * x) * (1.0 + 0.25 * np.sin(2 * np.pi * 22 * t))
    return _to_sound(wave, peak=0.5)


def make_rail_fire():
    sr = _mixer_rate(); n = int(sr * 1.2); t = np.arange(n) / sr
    rng = np.random.default_rng(107)
    sweep = np.sin(_phase(120.0 + 3500.0 * np.exp(-t * 9), sr)) * np.exp(-t * 6)
    ring = np.sin(2 * np.pi * 900 * t) * np.exp(-t * 3.5) * 0.4
    thump = np.sin(_phase(40.0 + 70.0 * np.exp(-t * 6), sr)) * np.exp(-t * 5) * 1.2
    wave = _crack(n, sr, rng, 35) + sweep + ring + thump
    out = _echo(wave, sr, ((0.12, 0.3), (0.3, 0.15)), tail=0.4)
    return _to_sound(np.tanh(1.3 * out), peak=0.9)


def make_groan():
    sr = _mixer_rate(); n = int(sr * 1.7); t = np.arange(n) / sr
    rng = np.random.default_rng(130)
    f = (88.0 - 28.0 * (t / 1.7)) * (1.0 + 0.04 * np.sin(2 * np.pi * 4.2 * t))
    ph = _phase(f, sr)
    voice = sum(np.sin(k * ph + 0.3 * k) / (k ** 1.1) for k in range(1, 9))
    breath = _smooth(rng.normal(size=n), 14) * 1.4
    env = np.sin(np.pi * np.clip(t / 1.7, 0, 1)) ** 1.4
    wobble = 0.75 + 0.25 * np.sin(2 * np.pi * 6.5 * t + 1.0)
    return _to_sound((voice * 0.8 + breath * 0.45) * env * wobble, peak=0.6)


def make_empty_click():
    sr = _mixer_rate(); n = int(sr * 0.07); t = np.arange(n) / sr
    rng = np.random.default_rng(110)
    wave = _crack(n, sr, rng, 400) + 0.4 * np.sin(2 * np.pi * 1500 * t) * np.exp(-t * 120)
    return _to_sound(wave, peak=0.4)


def make_switch():
    sr = _mixer_rate(); n = int(sr * 0.22); t = np.arange(n) / sr
    rng = np.random.default_rng(111)
    slide = _smooth(rng.normal(size=n), 3) * np.exp(-((t - 0.05) / 0.04) ** 2)
    i0 = int(0.16 * sr); m = n - i0; tt = np.arange(m) / sr
    click = np.zeros(n); click[i0:] = _smooth(rng.normal(size=m), 3) * np.exp(-tt * 100)
    return _to_sound(slide * 0.6 + click, peak=0.45)


def make_step(variant):
    sr = _mixer_rate(); n = int(sr * 0.14); t = np.arange(n) / sr
    rng = np.random.default_rng(120 + variant)
    base = (95.0, 82.0)[variant % 2]
    thump = np.sin(_phase(55.0 + base * np.exp(-t * 20), sr)) * np.exp(-t * 28)
    scuff = _smooth(rng.normal(size=n), 10) * np.exp(-t * 45) * 0.6
    return _to_sound(thump + scuff, peak=0.35)


def make_ui_tick():
    sr = _mixer_rate(); n = int(sr * 0.05); t = np.arange(n) / sr
    return _to_sound(np.sin(2 * np.pi * 1100 * t) * np.exp(-t * 60), peak=0.3)


def make_ui_ok():
    sr = _mixer_rate(); n = int(sr * 0.16); t = np.arange(n) / sr
    return _to_sound(np.sin(_phase(500.0 + 600.0 * t / 0.16, sr)) * np.exp(-t * 14), peak=0.35)


HORROR_SOUND_KEYS = {
    'drone_0', 'drone_1', 'heart_lub', 'heart_dub', 'jumpscare', 'sting',
    'whisper', 'scream_far', 'creak', 'thud', 'roar', 'groan', 'skitter', 'splash'
}


def build_sounds():
    sounds = {}
    sounds['shoot'] = synth_sound(lambda t: 900 - 4000 * t, 0.12, noise_amt=0.5, decay=18, volume=0.55)
    sounds['hit'] = synth_sound(lambda t: 220 - 300 * t, 0.15, noise_amt=0.7, decay=10, volume=0.5)
    sounds['hurt'] = synth_sound(lambda t: 180 - 100 * t, 0.25, noise_amt=0.35, decay=6, volume=0.55)
    sounds['pickup'] = synth_sound(lambda t: 500 + 900 * t, 0.18, noise_amt=0.02, decay=6, volume=0.5)
    sounds['door'] = synth_sound(lambda t: 140 + 40 * t, 0.4, noise_amt=0.15, decay=3, volume=0.45)
    sounds['enemy_growl'] = synth_sound(lambda t: 90 + 20 * np.sin(t * 20), 0.35, noise_amt=0.5, decay=4, volume=0.4)
    sounds['enemy_shoot'] = synth_sound(lambda t: 1400 - 900 * t, 0.10, noise_amt=0.35, decay=16, volume=0.4)
    sounds['reload'] = synth_sound(lambda t: 400 - 100 * t, 0.2, noise_amt=0.1, decay=8, volume=0.35)
    sounds['win'] = synth_sound(lambda t: 400 + 400 * t, 0.6, noise_amt=0.0, decay=1.5, volume=0.5)
    sounds['dead'] = synth_sound(lambda t: 300 - 280 * t, 0.9, noise_amt=0.2, decay=2, volume=0.5)
    sounds['deny'] = synth_sound(lambda t: 110 + 0 * t, 0.18, noise_amt=0.25, decay=10, volume=0.45)
    sounds['drone_0'] = make_drone(0)
    sounds['drone_1'] = make_drone(1)
    sounds['heart_lub'] = make_heartbeat('lub')
    sounds['heart_dub'] = make_heartbeat('dub')
    sounds['jumpscare'] = make_jumpscare()
    sounds['sting'] = make_sting()
    sounds['splash'] = make_dvloper_splash_sound()
    sounds['type_key'] = make_type_key()
    sounds['whisper'] = make_whisper()
    sounds['scream_far'] = make_distant_scream()
    sounds['creak'] = make_creak()
    sounds['thud'] = make_thud()
    sounds['roar'] = make_roar()
    sounds['enemy_die'] = make_enemy_die()
    sounds['log'] = make_log_chime()
    sounds['shutter'] = make_camera_shutter()
    sounds['scribble'] = make_pencil_scribble()
    sounds['skitter'] = make_skitter()
    sounds['shot_pistol'] = make_shot_pistol()
    sounds['shot_shotgun'] = make_shot_shotgun()
    sounds['pump'] = make_pump()
    sounds['shot_plasma'] = make_shot_plasma()
    sounds['plasma_hit'] = make_plasma_hit()
    sounds['rail_charge'] = make_rail_charge()
    sounds['shot_railgun'] = make_rail_fire()
    sounds['groan'] = make_groan()
    sounds['empty'] = make_empty_click()
    sounds['switch'] = make_switch()
    sounds['step_0'] = make_step(0)
    sounds['step_1'] = make_step(1)
    sounds['ui_tick'] = make_ui_tick()
    sounds['ui_ok'] = make_ui_ok()
    return sounds


# ----------------------------------------------------------------------------------
# LEVEL DATA
# ----------------------------------------------------------------------------------

LEVEL_1 = [
"11111111111111111111",
"10000000000000000001",
"10111011111110111101",
"10100000000000100001",
"10100111111110111001",
"10100100000010000001",
"10100100333310111101",
"10100100300010100001",
"10111100300010100111",
"10000000300010000001",
"10111111311110111101",
"10000000300000100001",
"14444440300444100001",
"14000000300000100001",
"14006004300000144441",
"14000000000000100001",
"14444444444440144441",
"10000000000000000001",
"10111111111111111101",
"10000000000000000091",
"11111111111111111111",
]

LEVEL_2 = [
"555555555555555555555555",
"500000000000000000000005",
"503333333333333333333305",
"503000000000000000000305",
"503022222222222222220305",
"503020000000000000020305",
"503020666600006666020305",
"503020600000000006020305",
"503020600222220006020305",
"503020600200020006020305",
"503020600200020006020305",
"503020600202020006020305",
"503020006202020006020305",
"503020000000000006020305",
"503022222200222222020305",
"503000000000000000020305",
"503333333311133333330305",
"500000000010000000000005",
"555555555510555555555555",
"000000000010000000000000",
"000000000090000000000000",
]

LEVEL_3 = [
"222222222222222222222222222",
"200000000000000000000000002",
"204444444444440444444444402",
"200000000000000000000000002",
"202222222222220222222222202",
"202000000000000000000000202",
"202033333333330333333330202",
"202030000000000000000030202",
"202030066666666666666030202",
"202030060000000000000030202",
"202030060555550555550060202",
"202030060500000000050060202",
"202030060505999905050060202",
"202030060500000000050060202",
"202030060555550555550060202",
"202030060000000000000030202",
"202030066666660666666030202",
"202030000000000000000030202",
"202033333333330333333330202",
"202000000000000000000000202",
"202222222222220222222222202",
"200000000000000000000000002",
"222222222222222222222222222",
]

LEVEL_4 = [
"55555555555555555555555555",
"50000000000001000000000005",
"50000000000001000000000905",
"50000000000001000000000005",
"50003000030001300003000005",
"50000000000001000000000005",
"50000000000001000000000005",
"50000000000001000000000005",
"50003000030001300003000005",
"50000000000001000000000005",
"50000000000000000000000005",
"50000000000000000000000005",
"50003000030001300003000005",
"50000000000001000000000005",
"50000000000001000000000005",
"50000000000001000005555555",
"50003000030001300005000055",
"50000000000001000006000055",
"50000000000001000005000055",
"50000000000001000005000055",
"50000000000001000005555555",
"55555555555555555555555555",
]

LEVEL_5 = [
"2222222222222222222222",
"2000000000020000000092",
"2000000000020000000002",
"2000000000020000000002",
"2000400040024000400002",
"2000000000020000000002",
"2000000000020000000002",
"2000000000020000000002",
"2000400040004000400002",
"2000000000000000000002",
"2000000000020000000002",
"2000000000020000222222",
"2000400040024000200022",
"2000000000020000600022",
"2000000000020000200022",
"2000000000020000222222",
"2000000000020000000002",
"2222222222222222222222",
]

LEVEL_6 = [
"444444444444444444444444",
"400000004000000040000004",
"400000004000000040000004",
"400000004000000000000004",
"400010004000100010001004",
"400000004000000040000004",
"400000004000000040000004",
"400000004000000040000004",
"400010004000100040001004",
"400000000000000040000004",
"400000000000000040000004",
"400000004000000040000004",
"400010004000100040001004",
"400000004000000040000004",
"400000004000000040444444",
"400000004000000040400044",
"400010004000100040600044",
"400000004000000040400044",
"490000004000000040444444",
"444444444444444444444444",
]

LEVEL_7 = [
"33333333333333333333333333",
"30000000030000000030000093",
"30000000030000000030000003",
"30000000030000000000000003",
"30002000230020002000200003",
"30000000030000000030000003",
"30000000030000000030000003",
"30000000030000000030000003",
"30002000230020002030200003",
"30000000000000000030000003",
"30000000000000000030000003",
"30000000030000000030000003",
"30002000230020002030200003",
"30000000030000000030333333",
"30000000030000000030300033",
"30000000030000000030600033",
"30002000230020002030300033",
"30000000030000000030333333",
"30000000030000000030000003",
"33333333333333333333333333",
]

LEVEL_8 = [
"1111111111111111111111111111",
"1000000001000000001000000001",
"1000000001000000001000000001",
"1000000000000000001000000001",
"1000300030003000301030003001",
"1000000001000000001000000001",
"1000000001000000001000000001",
"1000000001000000001000000001",
"1000300031003000301030003001",
"1000000001000000001000000001",
"1000000001000000001000000001",
"1000000001000000001000000001",
"1000300031003000301030003001",
"1000000001000000001000000001",
"1000000001000000001000111111",
"1000000001000000001000100011",
"1000300031003000301030600011",
"1000000001000000000000100011",
"1000000001000000000000100011",
"1000000001000000001000111111",
"1000000001000000001000000091",
"1111111111111111111111111111",
]

LEVEL_9 = [
"555555555555555555555555555555",
"500000000050000000005000000095",
"500000000050000000005000000005",
"500000000000000000005000000005",
"500040000400004000045000400005",
"500000000050000000005000000005",
"500000000050000000005000000005",
"500000000050000000005000000005",
"500000000050000000005000000005",
"500040000450004000040000400005",
"500000000050000000000000000005",
"500000000050000000005000000005",
"500000000050000000005000000005",
"500000000050000000005005555555",
"500040000450004000045005000055",
"500000000050000000005006000055",
"500000000050000000005005000055",
"500000000000000000005005000055",
"500000000000000000005005555555",
"500040000450004000045000400005",
"500000000050000000005000000005",
"555555555555555555555555555555",
]

LEVEL_10 = [
"22222222222222222222222222222222",
"20000000002000000000020000000092",
"20000000002000000000020000000002",
"20000000000000000000020000000002",
"20005000050000500005020050000502",
"20000000002000000000020000000002",
"20000000002000000000020000000002",
"20000000002000000000020000000002",
"20000000002000000000020000000002",
"20005000052000500005020050000502",
"20000000002000000000000000000002",
"22222200222222222222222220022222",
"20000000002000000000020000000002",
"20000000002000000000020000000002",
"20022222052000500005020022222202",
"20020002002000000000020020000202",
"20020006002000000000020060000202",
"20020002002000000000020020000202",
"20022222000000000000020020000202",
"20005000050000500005020022222202",
"20000000002000000000020000000002",
"20000000002000000000020000000002",
"20000000002000000000020000000002",
"22222222222222222222222222222222",
]

LEVEL_11 = [
"44444444444444444444444444",
"40000000040000000040000094",
"40000000040000000040000004",
"40000000040000000000000004",
"40002000240020002000200004",
"40000000040000000040000004",
"40000000040000000040000004",
"40000000040000000040000004",
"40002000240020002040200004",
"40000000000000000040000004",
"40000000000000000040000004",
"40000000040000000040000004",
"40002000240020002040200004",
"40000000040000000040444444",
"40000000040000000040400044",
"40000000040000000040600044",
"40002000240020002040400044",
"40000000040000000040444444",
"40000000040000000040000004",
"44444444444444444444444444",
]

LEVEL_12 = [
"1111111111111111111111111111",
"1000000001000000001000000001",
"1000000001000000001000000001",
"1000000000000000001000000001",
"1000500050005000501050005001",
"1000000001000000001000000001",
"1000000001000000001000000001",
"1000000001000000001000000001",
"1000500051005000501050005001",
"1000000001000000001000000001",
"1000000001000000001000000001",
"1000000001000000001000000001",
"1000500051005000501050005001",
"1000000001000000001000000001",
"1000000001000000001000111111",
"1000000001000000001000100011",
"1000500051005000501050600011",
"1000000001000000000000100011",
"1000000001000000000000100011",
"1000000001000000001000111111",
"1000000001000000001000000091",
"1111111111111111111111111111",
]

LEVEL_13 = [
"555555555555555555555555555555",
"500000000050000000005000000095",
"500000000050000000005000000005",
"500000000000000000005000000005",
"500030000300003000035000300005",
"500000000050000000005000000005",
"500000000050000000005000000005",
"500000000050000000005000000005",
"500000000050000000005000000005",
"500030000350003000030000300005",
"500000000050000000000000000005",
"500000000050000000005000000005",
"500000000050000000005000000005",
"500000000050000000005005555555",
"500030000350003000035005000055",
"500000000050000000005006000055",
"500000000050000000005005000055",
"500000000000000000005005000055",
"500000000000000000005005555555",
"500030000350003000035000300005",
"500000000050000000005000000005",
"555555555555555555555555555555",
]

LEVEL_14 = [
"222222222222222222222222222222",
"200000000020000000000200000092",
"200000000020000000000200000002",
"200000000000000000000200000002",
"200010000100001000010200100002",
"200000000020000000000200000002",
"200000000020000000000200000002",
"200000000020000000000200000002",
"200000000020000000000200000002",
"200010000120001000010200100002",
"2000000000200000000000000000002",
"2000000000200000000000000000002",
"200000000020000000000200000002",
"200000000020000000000200000002",
"200222220120001000010200222222",
"200200020020000000000200200002",
"200200060020000000000200600002",
"200200020020000000000200200002",
"200222220000000000000200200002",
"200010000100001000010200222222",
"200000000020000000000200000002",
"200000000020000000000200000002",
"200000000020000000000200000002",
"222222222222222222222222222222",
]

LEVEL_15 = [
"3333333333333333333333333333333333",
"3000000000030000000000030000000093",
"3000000000030000000000030000000003",
"3000000000000000000000030000000003",
"3000400004000040000400034000040003",
"3000000000030000000000030000000003",
"3000000000030000000000030000000003",
"3000000000030000000000030000000003",
"3000000000030000000000030000000003",
"3000400004030040000400034000040003",
"3000000000030000000000030000000003",
"3000000000030000000000000000000003",
"3000000000030000000000000000000003",
"3000000000030000000000030000000003",
"3000400004030040000400034000040003",
"3003333330030000000000030033333303",
"3003000030030000000000030030000303",
"3003000060030000000000030060000303",
"3003000030030000000000030030000303",
"3003333334000040000400034030000303",
"3000000000000000000000030033333303",
"3000000000030000000000030000000003",
"3000000000030000000000030000000003",
"3000000000030000000000030000000003",
"3000000000030000000000030000000003",
"3333333333333333333333333333333333",
]

LEVEL_16 = [
"2222222222222222222222222222222222",
"2000000000000000222200000000000092",
"2000000000000000222200000000000002",
"2000000000000000222200000000000002",
"2000100010001000222200030003000302",
"2000000000000000222200000000000002",
"2000000000000000222200000000000002",
"2000000000000000222200000000000002",
"2000100010001000444400030003000302",
"2000000000000000000000000000000002",
"2000000000000000000000000000000002",
"2000000000000000444400000000000002",
"2000100010001000222200030003000302",
"2000000000000000222200000000000002",
"2000000000000000222200000000000002",
"2000000000000000222200000000000002",
"2000100010001000222200030003000302",
"2000000000000000222200000000000002",
"2000000000000000222200000000000002",
"2222222222222222222222222222222222",
]

LEVELS = [LEVEL_1, LEVEL_2, LEVEL_3, LEVEL_4, LEVEL_5, LEVEL_6, LEVEL_7, LEVEL_8, LEVEL_9, LEVEL_10,
          LEVEL_11, LEVEL_12, LEVEL_13, LEVEL_14, LEVEL_15, LEVEL_16]

SECTOR_NAMES = [
    "Nazi Bunker 'Walküre' (1945)",
    "USSR Kola Superdeep Caves",
    "Unit 731 Bio-Containment Wing",
    "Pripyat Hospital Basement",
    "Paris Catacombs: Gate IX",
    "Poveglia Plague Asylum",
    "Derinkuyu 18th Sub-Level",
    "MKUltra Sub-Project 68 Ward",
    "Aralsk-7 Kantubek Bio-Vault",
    "Hashima Coal Shaft No. 9",
    "Dyatlov Weather Station",
    "Hoia Baciu Radar Bunker",
    "Area 51 S-4 Sub-Hangar",
    "Aokigahara Shrine Lava Tubes",
    "Tunguska 1908 Crater Vault",
    "The 100K Broadcast Convergence",
]


SECTOR_WALL_WRITINGS = [
    ("APRIL 1945", "WALKURE", "DO NOT OPEN"),
    ("12262M", "VOICES", "WELD SHUT"),
    ("UNIT 731", "NO EXIT", "STERILIZE"),
    ("3.6 ROENTGEN", "1986", "DO NOT TOUCH"),
    ("EMPIRE OF", "DEATH", "1786"),
    ("PLAGUE BELL", "BURN IT", "THE DOCTOR"),
    ("LEVEL 18", "NOT STONE", "GO BACK"),
    ("TAPE LOOP", "OBEY", "1959"),
    ("BREACH", "NO CURE", "ARALSK 7"),
    ("-1000M", "TRAPPED", "SEA WALL"),
    ("9 MISSING", "RUN", "1959"),
    ("DEAD ZONE", "NO SIGNAL", "LOOK UP"),
    ("HANGAR S4", "EYES ONLY", "GRAVITY OFF"),
    ("NO COMPASS", "LOST", "REWIND"),
    ("NOT METEOR", "1908", "HULL"),
    ("100K WATCH", "LIES", "OPEN DOOR"),
]

SECTOR_STREAM_COMMENTS = [
    ["@hist_buff: Wait... those stencils on the wall are authentic 1945 Wehrmacht font!",
     "@bunker_rat: Did you hear that metal door slam behind you?!",
     "@skeptic_dan: Okay I thought this was a movie set until I saw the dust fall..."],
    ["@geo_nerd: 12,262 meters down—that's the actual Kola Superdeep Borehole depth!",
     "@audio_tech: Turn up your mic gain, I swear I hear screaming from the floor!",
     "@nightowl_99: Why is the rock down here warm?!"],
    ["@dark_history: Pingfan Wing 4... Kaelen, you should NOT be breathing that air.",
     "@medic_lee: Those specimen jars still have intact labels from 1945...",
     "@urbex_maya: Something just moved behind the containment glass!"],
    ["@dosimeter_tv: Bro your Geiger counter is clicking nonstop, get out!!",
     "@stalker_86: That's the Pripyat basement where they dumped the firemen's boots.",
     "@vhs_ghost: My screen flickered green right when you walked past that wall!"],
    ["@paris_under: You crossed Gate IX—there are no official maps past this point.",
     "@bone_keeper: 'Arrête! C'est ici l'empire de la mort'... chills.",
     "@cryptid_jay: Did that skull on the shelf just turn toward your lens?!"],
    ["@venice_lore: 100,000 plague bodies burned on Poveglia... just like your sub count.",
     "@asylum_watch: Listen—can you hear the tower bell ringing underground?",
     "@paranoia_hq: Don't turn around, there's a figure in the doorway!"],
    ["@ancient_arc: Cappadocia tuff stone shouldn't have riveted steel bolted into it!",
     "@spelunker_k: How deep is Level 18?! No survey ever went past Level 8!",
     "@lens_flare: That writing on the stone wasn't there 5 seconds ago!!"],
    ["@mk_files: Sub-Project 68... those reel-to-reel tapes are still spinning!",
     "@tape_loop: Wait, why does the whisper on the tape know your username?!",
     "@mod_sarah: Chat is lagging—everybody's audio just echoed 'OBEY'."],
    ["@bio_watch: Aralsk-7 Kantubek! Those containment cages are bent OUTWARD!",
     "@hazmat_01: Don't touch the black dust on the floor, Kaelen!",
     "@urbex_maya: Why are all the lab benches still set up in clusters?!"],
    ["@nagasaki_urbex: Hashima Shaft 9 flooded in 1974... why is this tunnel dry?",
     "@miner_son: You're a thousand meters under the ocean floor right now.",
     "@superchat_50: 0 DONO — PLEASE USE YOUR FLASHLIGHT MORE, IT'S SO DARK!"],
    ["@ural_mystery: Nine torn tent fragments... Dyatlov Pass 1959.",
     "@cold_front: Why is there frost on the camera lens inside a bunker?!",
     "@skeptic_dan: Okay I'm not calling it fake anymore. Just find the key."],
    ["@cluj_local: Nobody goes into Hoia Baciu's dead zone after midnight.",
     "@emf_hunter: My phone compass just spun 360 degrees watching your stream!",
     "@vhs_ghost: Your IR night vision won't survive this interference!"],
    ["@groom_lake: S-4 Sub-Hangar... why is that chair floating off the concrete?!",
     "@black_budget: If this stream stays up, the feds are gonna nuke your channel!",
     "@cryptid_jay: Look at the wall markings—that's not human handwriting."],
    ["@fuji_trails: Thousands of dead compasses pointing straight down...",
     "@cassette_99: Someone left a tape with YOUR channel name on it!!",
     "@urbex_maya: Don't follow the red cords in the dark, Kaelen."],
    ["@siberia_1908: That's not meteor rock... those are hull plates from Tunguska!",
     "@physicist_r: The airburst happened 5km up—how is the hull buried HERE?!",
     "@USER_100000: Almost 100,000 witnesses. One more descent."],
    ["@USER_100000: All sixteen doors were the same door, Kaelen.",
     "@WALKURE_45: 100,000 followers watching live. Click the shutter.",
     "@MOD_BOT: STREAM LOCKED — CANNOT END BROADCAST UNTIL CONVERGENCE."],
]

GENERAL_STREAM_COMMENTS = [
    ("@superchat_king", "0 DONO: Bro my heart is pounding just watching this!"),
    ("@dark_lens", "It's pitch black down there—use [G] Night Vision if it works!"),
    ("@urbex_maya", "Check the blood writing on the walls, every site has different clues!"),
    ("@skeptic_dan", "Wait... pause at 0:14, was that a shadow evaporating?!"),
    ("@clip_master", "CLIPPING THIS! Viewers just jumped again!"),
    ("@audio_freak", "Anyone else wearing headphones? Hear the footsteps behind him?!"),
    ("@night_shift", "Watching from work at 2 AM, terrible decision lol"),
    ("@cryptid_jay", "Keep snapping unique photos—10+ unlocks the Blue Exit Key!"),
    ("@void_theorist", "Notice how all the props are left in clusters like people vanished mid-task?"),
    ("@vhs_ghost", "The lighting in this corridor is unsettling as hell..."),
    ("@mod_sarah", "Remember to post your photos to the Blog [N] between fights!"),
    ("@book_worm99", "Pre-ordered Beneath the Sealed Earth—need those chapter plates!"),
]


SUPERCHAT_CHALLENGES = [
    ('no_ir',     '@dark_donor',    25,  'NO IR NIGHT VISION for 18s!',       18.0, 650),
    ('close_pic', '@lens_dare',     50,  'Snap a photo from < 2.8m away!',    32.0, 900),
    ('no_shoot',  '@stealth_vip',   35,  'HOLD FIRE! No shooting for 16s!',    16.0, 750),
    ('kills_2',   '@bunker_brawler',45,  'Eliminate 2 entities in 35s!',      35.0, 850),
    ('photos_2',  '@clip_king',     75,  'Take 2 photos in the next 30s!',    30.0, 1100),
    ('stand_still','@ice_nerves',   100, 'Freeze still 4s with threat near!', 28.0, 1400),
]

SECTOR_HINTS = [
    "Bavarian Alps, Germany. Sealed April 1945 by SS Ahnenerbe occult researchers. Capture at least 10 unique photos to materialize the Blue Exit Key.",
    "Murmansk Oblast, USSR. In 1989 Soviet geologists drilled 12,262m down, heard voices on the borehole mic, and welded the shaft shut.",
    "Pingfan District, Harbin. Buried biological testing chambers dynamited in 1945—yet the specimen vats down here still have power.",
    "Chernobyl Exclusion Zone, 1986. The flooded basement where liquidators' radioactive gear was dumped. Your Geiger counter beats like a heart.",
    "Beneath Paris, France. Past the 'Arrête! C'est ici l'empire de la mort' lintel into an unmapped 1786 bone quarry.",
    "Venetian Lagoon, Italy. 100,000 plague victims burned in the soil, followed by a 1922 psychiatric hospital whose doctor jumped from the tower.",
    "Cappadocia, Turkey. Carved 85 meters below volcanic rock—except the lowest stone tunnel opens into cold, riveted steel.",
    "Decommissioned 1959 sensory-deprivation basement. Reel-to-reel tape loops are still whispering psychic driving phrases to empty beds.",
    "Vozrozhdeniye Island, Aral Sea. Abandoned Soviet anthrax & plague laboratory where containment cages were bent outward from inside.",
    "Battleship Island, Nagasaki. Undersea coal tunnels 1,000 meters below the seabed, flooded the night miners broke into an older chamber.",
    "Kholat Syakhl (Dead Mountain), Urals. A classified 1959 meteorological bunker containing nine torn tent fragments and paradoxical radiation logs.",
    "Cluj-Napoca, Romania. Cold War listening post built dead-center in the Hoia Baciu clearing where compasses and clocks fail.",
    "Papoose Lake, Nevada. Subterranean hangar S-4 where gravity tests left interrogation chairs floating six inches above the floor.",
    "Base of Mount Fuji, Japan. Volcanic lava tubes lined with thousands of rusted compasses and cassette tapes left behind in the dark.",
    "Podkamennaya Tunguska, Siberia. Imperial-to-Soviet excavation beneath the 1908 airburst epicenter. They didn't find a meteor—they found a hull.",
    "Your GPS hasn't moved since Bavaria. Every bunker, cave, and catacomb led down the same staircase—waiting for your 100,000 followers.",
]

TYPING_HORROR_INTRO_TEXT = (
    "CREATOR: KAELEN VANCE  (@VoidVlogs - 100,000 FOLLOWERS)\n"
    "EQUIPPED: CAMCORDER, LIVESTREAM RIG & FIELD NOTEBOOK\n\n"
    "They called my last urban exploration videos fake.\n"
    "Three nights ago, an anonymous follower sent me coordinates\n"
    "to a sealed 1945 bunker - promising undeniable proof.\n\n"
    "I stepped inside with my camera rolling.\n"
    "The heavy steel door just locked behind me.\n\n"
    "I need at least 10 unique pictures of whatever is down here\n"
    "to make the Blue Exit Key appear... and prove I am not lying."
)

SECTOR_INTRO_MONOLOGUES = [
    "What's up guys, Kaelen here—we just hit 100K followers! Tonight I'm inside a sealed 1945 Nazi bunker in Bavaria. I need at least 10 unique photos of real anomalies so no one can call my channel fake.",
    "Okay chat, hold on—the exit from that 1945 German bunker just opened straight into the USSR Kola Superdeep caves! How do Bavaria and Russia connect underground?! Keep watching the stream.",
    "Level 3: Unit 731 sub-basement. After what we learned in the Nazi bunker and Kola caves, these floating skulls aren't random—every regime in the 1940s was studying the exact same subterranean vein.",
    "Pripyat Hospital Basement, Chernobyl. Notice the pattern from the first three sites? Whenever I take 10 unique photos, a Blue Key materializes out of thin air. The room is reacting to my camera.",
    "Paris Catacombs Gate IX. Back in Chernobyl and Harbin the bones were wired like antennas; down here six million skeletons are arranged into a giant resonator. I'm logging all of this for my book.",
    "Poveglia Plague Asylum, Italy. I've survived five impossible transitions now. The headless skeletons, dragging corpses, and black evaporating figures aren't ghosts—they're antibodies guarding a lock.",
    "Derinkuyu 18th Sub-Level. Having seen the masonry in Paris and Poveglia, look how the ancient carved stone fuses into modern steel. Every civilization dug into the same buried organism.",
    "MKUltra Sub-Project 68 Ward. Remember the self-typing cipher machines we photographed back in the Nazi bunker? The CIA had the exact same terminals here—tracking 'optical transmission' through cameras.",
    "Aralsk-7 Bio-Vault. The Soviet GP-5 gas masks here match the crates from Pripyat and Kola. I've learned its trick now: the black evaporating shadow figures rush the second I look away.",
    "Hashima Undersea Coal Shaft. Ten sectors deep and my GPS still shows my starting coordinates from Sector 1. The dead journalists I keep finding all carried cameras just like mine.",
    "Dyatlov Weather Vault, 1959. Look at the blood writing on the stone—'100K LIES'. Back in Sector 1 I thought it was old graffiti, but it's addressing MY channel directly!",
    "Hoia Baciu Radar Bunker. All my previous blog posts and book chapters point to one conclusion: the entity can't cross sealed concrete, it rides photographic images into human minds.",
    "Area 51 S-4 Sub-Hangar. The levitating chairs here are identical to the ones in the MKUltra ward. The military didn't hide aliens—they quarantined the same memetic lens we've been photographing since Sector 1.",
    "Aokigahara Shrine Lava Tubes. Fourteen sites in, I finally understand why the Blue Key only spawns after 10 unique photos: ten distinct visual anchors are required to open each containment seal!",
    "Tunguska 1908 Crater Vault. Every clue from Bavaria, Kola, Chernobyl, and Area 51 converges right here at the 1908 impact hull. One more seal and the broadcast package is complete.",
    "The 100K Convergence. I learned the hard way across all 15 previous sites: I wasn't investigating a haunting—I was the courier. My livestream, my blog, and my book are the three vessels it needed!",
]

PROGRESSIVE_AMBIENT_LINES = [
    [
        "Look at the walls—someone wrote 'RUN' in blood right before they died. Snapping a shot of the wall for the blog!",
        "Clusters of 1940s suitcases piled together... people tried to evacuate in a hurry. Adding this to Chapter 1 of my book.",
        "Thousands of roaches and packs of rats scurrying across the floor. Chat, tell me you're seeing this on the livestream.",
        "People in my comments swore my last video was CGI. Let's see the debunkers explain a floating chattering skull.",
    ],
    [
        "Wait—those headless skeletons carry the exact same rifles we saw two sectors ago, even though we're in a different country!",
        "Just like in the earlier bunkers, the items are stacked in clusters—gas masks, specimen jars, suitcases—like a museum of human panic.",
        "Watch those black shadow figures: I learned in the last sector that their black energy evaporates faster right before they lunge!",
        "Even the dead bodies on the floor are dragging themselves after me—their necks are snapped just like the corpses from the last site.",
    ],
    [
        "Think about what we learned in the earlier levels: the Blue Key never exists until my camera clicks its tenth unique photo.",
        "The blood writing says '100K LIES'—left-to-right, clear as day. It knows how many followers are watching my stream right now.",
        "Every previous explorer corpse we've photographed since Sector 1 had a camera and a notebook. None of them had 100,000 viewers—until me.",
        "Open my notebook with N—weird accounts in the livestream chat are quoting my own book chapters back to me.",
    ],
    [
        "From the Nazi Walküre bunker to Kola, Pripyat, and Area 51—it's all one subterranean body, and my camera lens is unlocking its cells.",
        "I used to wonder why I needed at least 10 unique photos per sector. Ten visual proofs is the threshold to imprint the entity on my audience.",
        "My livestream, my blog, and my book—three platforms, three ways to make sure 100,000 minds never forget what we photographed down here.",
    ],
]

LORE_LOGS = [
    "FIELD NOTEBOOK #1 — 1945 NAZI BUNKER 'PROJEKT WALKÜRE' (BAVARIA)\n"
    "Subscriber Milestone Special (100,000 Followers). I pried open the rusted Kriegsmarine bulkhead "
    "at 02:14 AM. German stenciling reads 'NICHT FOTOGRAFIEREN' (DO NOT PHOTOGRAPH). Why would SS "
    "occult researchers in 1945 ban cameras in a bunker? Even stranger: the heavy exit door has a blue "
    "electromagnetic seal that only reacts after I capture at least 10 unique anomalies.",

    "FIELD NOTEBOOK #2 — USSR KOLA SUPERDEEP RESEARCH CAVES (MURMANSK)\n"
    "I walked through the Bavarian bunker exit and stepped straight into a 1989 Soviet geological "
    "cavern. Impossible—that's 2,800 kilometers away. A clipboard signed by Dr. Azakov states: "
    "'At 12,262 meters we did not hit mantle rock. We hit a gallery of rooms that already had cameras "
    "waiting for us.'",

    "FIELD NOTEBOOK #3 — UNIT 731 SUB-BASEMENT (PINGFAN, HARBIN)\n"
    "Rows of glass specimen vats line the corridors in clusters. Inside the broken cylinders are human "
    "skulls that hover and gnash their teeth, guarded by headless skeletons, dragging corpses, and black "
    "evaporating shadows. My livestream, blog, and book draft are blowing up.",

    "FIELD NOTEBOOK #4 — PRIPYAT HOSPITAL NO. 126 BASEMENT (CHERNOBYL)\n"
    "The flooded floor is crawling with irradiated beetles and packs of rats. Piles of suitcases from "
    "1986 sit beside crates of GP-5 gas masks. Written across the wall in blood: 'RUN' and '100K LIES'. "
    "One pair of eyes keeps it awake; a hundred thousand sets it free.",

    "FIELD NOTEBOOK #5 — PARIS CATACOMBS: FORBIDDEN OSSUARY GATE IX\n"
    "The limestone walls are packed with stacked femurs and grinning craniums from 1786. Yet wired into "
    "the bone piles are Cold War vacuum tubes from Kola and Bavaria. Whoever curated these historical "
    "horrors across centuries wasn't hiding them—they were staging an exhibition for a broadcaster.",

    "FIELD NOTEBOOK #6 — POVEGLIA ISLAND PLAGUE ASYLUM (VENICE LAGOON)\n"
    "Found the asylum director's 1922 ledger beside a pair of weeping stone statues. He wrote: 'The "
    "patients are not hallucinating the headless skeletons or reanimated corpses. They are tuning "
    "into them like receivers. God help us if an author or broadcaster ever publishes their image.'",

    "FIELD NOTEBOOK #7 — DERINKUYU 18TH SUB-LEVEL (CAPPADOCIA)\n"
    "Eighteen levels below the Turkish desert. The ancient Phrygian tufa rock abruptly stops at a "
    "riveted hull wall smeared with bloody handprints. Every civilization that dug too deep broke into "
    "the exact same subterranean labyrinth—and sealed it from the outside.",

    "FIELD NOTEBOOK #8 — MKULTRA SUB-PROJECT 68 WARD (1959 ARCHIVE)\n"
    "Sensory-deprivation tanks and banks of self-typing cipher machines. A declassified memo on the desk "
    "describes 'Project LENS': an experiment proving that a paranormal entity trapped in deep rock "
    "can relocate through photographic sensors, livestreams, and printed books.",

    "FIELD NOTEBOOK #9 — ARALSK-7 'KANTUBEK' BIO-TESTING BUNKER\n"
    "Crates of Soviet GP-5 gas masks stare at me from the dark. None of the pathogens here were viral. "
    "The lab notes call the contagion 'MEMETIC-OPTICAL CLASS': if at least ten distinct manifestations "
    "are captured in sequence, the chamber unlocks and lets the carrier ascend to the next threshold.",

    "FIELD NOTEBOOK #10 — HASHIMA 'BATTLESHIP ISLAND' SHAFT NO. 9\n"
    "Coal dust, seawater, and packs of scurrying rats. I found a dead journalist crew from 1974 clutching "
    "press cameras. They didn't have a 100K livestream, a blog, and a book manuscript to broadcast the "
    "signal wide enough, so the vault kept them down here.",

    "FIELD NOTEBOOK #11 — DYATLOV PASS WEATHER VAULT (KHOLAT SYAKHL)\n"
    "Inside this Ural bunker is the tenth camera from the 1959 Dyatlov expedition—the one the Soviet "
    "prosecutor never released. Its final frame shows the exact same Blue Key that silently materializes "
    "every time I take my tenth unique photograph.",

    "FIELD NOTEBOOK #12 — HOIA BACIU MILITARY LISTENING POST (ROMANIA)\n"
    "The stack of unplugged CRT televisions in the corner just flickered on and showed my '@VoidVlogs' "
    "livestream, my blog, and my book manuscript. The anonymous email that leaked me these coordinates "
    "was sent from an IP address inside this bunker.",

    "FIELD NOTEBOOK #13 — AREA 51 S-4 REVERSE-ENGINEERING HANGAR\n"
    "Clusters of interrogation chairs float upside down in the dark. The military didn't recover a "
    "spacecraft here—they dug up a lens-node of the same subterranean entity found in Bavaria and Kola. "
    "Their containment protocol had one rule: NEVER LET AN INFLUENCER OR AUTHOR INSIDE.",

    "FIELD NOTEBOOK #14 — AOKIGAHARA FORBIDDEN SHRINE LAVA TUBES\n"
    "Compasses spin wildly around the blood altars. I finally pieced my notes together: every "
    "photo I click, every blog I post, and every book chapter I draft is acting as a three-part "
    "waveguide—encoding the entity into live video, web articles, and print.",

    "FIELD NOTEBOOK #15 — TUNGUSKA 1908 IMPACT VAULT (SIBERIA)\n"
    "The 1908 Siberian blast wasn't a meteor—it was the entity arriving and burrowing through time "
    "and bedrock. For a century it was trapped because only lone soldiers and scientists saw it. "
    "It needed a creator obsessed with proving it was real across every media platform at once.",

    "FIELD NOTEBOOK #16 — THE FINAL REALIZATION: 100K BROADCAST CONVERGENCE\n"
    "I UNDERSTAND THE STORY NOW. I came here as a content creator with 100,000 followers, desperate "
    "to photograph at least 10 undeniable anomalies per site so nobody would call me a liar. Every "
    "Blue Key that spawned after 10 photos wasn't helping me escape—it was unlocking a 16-stage "
    "containment seal across my Livestream, my Blog, and my Book!",
]


def parse_level(rows):
    grid = [[int(ch) for ch in row] for row in rows]
    return grid


def find_open_tiles(grid, exclude=(EXIT_TILE, WALL_DOOR)):
    tiles = []
    for y, row in enumerate(grid):
        for x, v in enumerate(row):
            if v == WALL_EMPTY:
                tiles.append((x, y))
    return tiles


# ----------------------------------------------------------------------------------
# ENTITIES
# ----------------------------------------------------------------------------------

class Player:
    def __init__(self, x, y, angle=0.0):
        self.x = x
        self.y = y
        self.angle = angle
        self.hp = PLAYER_MAX_HP
        self.max_hp = PLAYER_MAX_HP

        self.weapons_owned = [False] * len(WEAPON_DEFS)
        self.weapon_index = 0
        self.ammo = {i: 0 for i in range(len(WEAPON_DEFS))}
        self.reserve = {i: 0 for i in range(len(WEAPON_DEFS))}

        self.keys = set()
        self.bob_phase = 0.0
        self.moving = False
        self.reloading = False
        self.reload_timer = 0.0
        self.shoot_cooldown = 0.0
        self.camera_cooldown = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.charge = 0.0
        self.damage_flash = 0.0
        self.pickup_flash = 0.0
        self.kills = 0
        self.spawn_grace = SPAWN_GRACE_SECONDS

    @property
    def weapon(self):
        return WEAPON_DEFS[self.weapon_index]

    @property
    def armed(self):
        return self.weapons_owned[self.weapon_index]

    def ensure_valid_weapon(self):
        if not self.armed:
            for i, owned in enumerate(self.weapons_owned):
                if owned:
                    self.weapon_index = i
                    break

    def switch_weapon(self, index):
        if 0 <= index < len(WEAPON_DEFS) and self.weapons_owned[index] and index != self.weapon_index:
            self.weapon_index = index
            self.reloading = False
            self.charge = 0.0
            self.shoot_cooldown = max(self.shoot_cooldown, 0.22)
            return True
        return False

    @property
    def dir_vec(self):
        return math.cos(self.angle), math.sin(self.angle)

    def try_move(self, dx, dy, grid):
        r = PLAYER_RADIUS
        nx = self.x + dx
        if not is_wall(grid, nx + math.copysign(r, dx), self.y) and \
           not is_wall(grid, nx - math.copysign(r, dx), self.y) and \
           not is_wall(grid, nx + math.copysign(r, dx), self.y - r) and \
           not is_wall(grid, nx + math.copysign(r, dx), self.y + r):
            self.x = nx
        ny = self.y + dy
        if not is_wall(grid, self.x, ny + math.copysign(r, dy)) and \
           not is_wall(grid, self.x, ny - math.copysign(r, dy)) and \
           not is_wall(grid, self.x - r, ny + math.copysign(r, dy)) and \
           not is_wall(grid, self.x + r, ny + math.copysign(r, dy)):
            self.y = ny

    def take_damage(self, amount):
        if self.spawn_grace > 0:
            return
        self.hp = max(0, self.hp - amount)
        self.damage_flash = 1.0

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)
        self.pickup_flash = 1.0


def is_wall(grid, x, y):
    ix, iy = int(x), int(y)
    if iy < 0 or iy >= len(grid) or ix < 0 or ix >= len(grid[0]):
        return True
    v = grid[iy][ix]
    return v not in (WALL_EMPTY, EXIT_TILE)


def is_blocking_for_door(grid, x, y, opened_doors):
    ix, iy = int(x), int(y)
    if iy < 0 or iy >= len(grid) or ix < 0 or ix >= len(grid[0]):
        return True
    v = grid[iy][ix]
    if v == WALL_DOOR and (ix, iy) in opened_doors:
        return False
    return v not in (WALL_EMPTY, EXIT_TILE)


class Enemy:
    __slots__ = ('x', 'y', 'kind', 'hp', 'max_hp', 'state', 'anim_t', 'attack_cd',
                 'alerted', 'speed', 'damage', 'dead_timer', 'growl_cd', 'ranged',
                 'preferred_range', 'fire_flash', 'slow_t', 'hit_flash', 'kx', 'ky',
                 'step_cd', 'photo_id', 'photographed')

    def __init__(self, x, y, kind='grunt', photo_id=None):
        self.x = x
        self.y = y
        self.kind = kind
        stats = {
            'grunt':   dict(hp=55, speed=1.5, damage=9),
            'brute':   dict(hp=120, speed=1.0, damage=18),
            'shooter': dict(hp=45, speed=1.2, damage=9),
            'charger': dict(hp=35, speed=2.3, damage=12),
            'turret':  dict(hp=60, speed=0.0, damage=10),
        }[kind]
        self.max_hp = stats['hp']
        self.hp = self.max_hp
        self.state = 'idle'
        self.anim_t = random.uniform(0, 10)
        self.attack_cd = 0.0
        self.alerted = False
        self.speed = stats['speed']
        self.damage = stats['damage']
        self.dead_timer = 0.0
        self.growl_cd = random.uniform(2, 6)
        self.ranged = kind in ('shooter', 'turret')
        self.preferred_range = 5.5 if kind == 'shooter' else 6.5
        self.fire_flash = 0.0
        self.slow_t = 0.0
        self.hit_flash = 0.0
        self.kx = 0.0
        self.ky = 0.0
        self.step_cd = 0.0
        self.photo_id = ENEMY_KIND_TO_PHOTO_ID.get(kind, 11) if photo_id is None else photo_id
        self.photographed = False

    def take_damage(self, amount):
        if self.state == 'dead':
            return False
        self.hp -= amount
        if self.hp <= 0:
            self.state = 'dead'
            self.dead_timer = 0.0
            return True
        self.alerted = True
        self.state = 'chase'
        return False


class Anomaly:
    __slots__ = ('x', 'y', 'photo_id', 'kind', 'name', 'note', 'photographed',
                 'is_core', 'companions')

    def __init__(self, x, y, target_def, is_core=True, companions=()):
        self.x = x
        self.y = y
        self.photo_id = target_def['id']
        self.kind = target_def['kind']
        self.name = target_def['name']
        self.note = target_def['note']
        self.photographed = False
        self.is_core = is_core
        self.companions = list(companions)


class Critter:
    __slots__ = ('x', 'y', 'kind', 'vx', 'vy', 'anim_t', 'turn_t', 'squeak_cd',
                 'photo_id', 'photographed')

    def __init__(self, x, y, kind='mouse', photo_id=200):
        self.x = x
        self.y = y
        self.kind = kind
        ang = random.uniform(0, 2 * math.pi)
        spd = 2.6 if kind == 'mouse' else 0.35
        self.vx = math.cos(ang) * spd
        self.vy = math.sin(ang) * spd
        self.anim_t = random.uniform(0, 10.0)
        self.turn_t = random.uniform(0.6, 2.2)
        self.squeak_cd = random.uniform(4.0, 14.0)
        self.photo_id = photo_id
        self.photographed = False


class Projectile:
    __slots__ = ('x', 'y', 'dx', 'dy', 'speed', 'wid', 'life', 'trail_t')

    def __init__(self, x, y, dx, dy, wdef):
        self.x, self.y, self.dx, self.dy = x, y, dx, dy
        self.speed = wdef['proj_speed']
        self.wid = wdef['id']
        self.life = 3.0
        self.trail_t = 0.0


class Effect:
    __slots__ = ('x', 'y', 'kind', 't', 'dur')

    def __init__(self, x, y, kind, dur):
        self.x, self.y, self.kind, self.t, self.dur = x, y, kind, 0.0, dur


class Pickup:
    __slots__ = ('x', 'y', 'kind', 'alive')

    def __init__(self, x, y, kind):
        self.x = x
        self.y = y
        self.kind = kind
        self.alive = True


# ----------------------------------------------------------------------------------
# LEVEL STATE / SPAWNING
# ----------------------------------------------------------------------------------

class LevelState:
    def __init__(self, grid, spawn, exit_pos, enemies, pickups, anomalies, critters,
                 blue_key_pos, name):
        self.grid = grid
        self.spawn = spawn
        self.exit_pos = exit_pos
        self.enemies = enemies
        self.pickups = pickups
        self.anomalies = anomalies
        self.critters = critters
        self.blue_key_pos = blue_key_pos
        self.blue_key_spawned = False
        self.opened_doors = set()
        self.explored = set()
        self.name = name
        self.width = len(grid[0])
        self.height = len(grid)


def _far_enough(tile, points, min_dist=3.0):
    for p in points:
        if math.hypot(tile[0] - p[0], tile[1] - p[1]) < min_dist:
            return False
    return True


def _decorate_horror_walls(grid, rng):
    h, w = len(grid), len(grid[0])
    horror_variants = (WALL_BLOOD_BRICK, WALL_BLOOD_STONE, WALL_BLOOD_METAL, WALL_GRAFFITI)
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            v = grid[y][x]
            if v in (WALL_BRICK, WALL_STONE, WALL_METAL, WALL_WOOD, WALL_HULL):
                touches_open = any(
                    grid[y + dy][x + dx] == WALL_EMPTY
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                )
                if touches_open and rng.random() < 0.25:
                    grid[y][x] = rng.choice(horror_variants)


def _make_cluster_companions(grid, cx, cy, count, rng):
    companions = []
    for i in range(max(0, count - 1)):
        for _ in range(10):
            ang = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(0.28, 0.55)
            nx = cx + math.cos(ang) * dist
            ny = cy + math.sin(ang) * dist
            if not is_wall(grid, nx, ny) and not is_wall(grid, nx + 0.15, ny) and not is_wall(grid, nx - 0.15, ny):
                companions.append((nx, ny, rng.uniform(0.78, 0.96)))
                break
    return companions


def build_level(index):
    rows = LEVELS[index]
    grid = parse_level(rows)
    rng = random.Random(4242 + index * 97)
    _decorate_horror_walls(grid, rng)

    open_tiles = find_open_tiles(grid)
    exit_pos = None
    for y, row in enumerate(grid):
        for x, v in enumerate(row):
            if v == EXIT_TILE:
                exit_pos = (x + 0.5, y + 0.5)

    if index == 0:
        spawn_tile = (1, 1)
        spawn = (1.5, 1.5)
        enemies = [
            Enemy(10.5, 1.5, 'grunt', photo_id=11),
            Enemy(5.5, 9.5, 'shooter', photo_id=13),
            Enemy(15.5, 11.5, 'charger', photo_id=14),
            Enemy(10.5, 19.5, 'brute', photo_id=12),
        ]
        pickups = [
            Pickup(1.5, 6.5, 'pistol'),
            Pickup(10.5, 5.5, 'key'),
            Pickup(16.5, 7.5, 'ammo'),
            Pickup(3.5, 13.5, 'health'),
            Pickup(17.5, 3.5, 'health'),
            Pickup(5.5, 13.5, 'log'),
        ]
        used = [
            (1, 1), (10, 1), (5, 9), (15, 11), (10, 19),
            (1, 6), (10, 5), (16, 7), (3, 13), (17, 3), (5, 13),
        ]
        name = f"SECTOR 1 - {SECTOR_NAMES[0]}"
    else:
        spawn_tile = open_tiles[0]
        spawn = (spawn_tile[0] + 0.5, spawn_tile[1] + 0.5)

        reachable = _bfs_open(grid, spawn_tile)
        has_doors = any(WALL_DOOR in row for row in grid)
        locked_off = has_doors and len(reachable) < len(open_tiles) + 1

        avoid = [spawn, exit_pos]
        candidates = [t for t in open_tiles if _far_enough(t, avoid, 2.5)]
        rng.shuffle(candidates)

        enemy_pool = [t for t in candidates if _far_enough(t, [spawn], 5.5)]

        enemies = []
        pickups = []
        used = [spawn_tile]

        if locked_off:
            key_candidates = [t for t in candidates if t in reachable]
            if key_candidates:
                key_tile = max(key_candidates,
                               key=lambda t: math.hypot(t[0] - spawn[0], t[1] - spawn[1]))
                pickups.append(Pickup(key_tile[0] + 0.5, key_tile[1] + 0.5, 'key'))
                used.append(key_tile)
                candidates = [t for t in candidates if t != key_tile]

        vault_tiles = []
        if locked_off:
            full_reachable = _bfs_with_doors(grid, spawn_tile)
            vault_tiles = [t for t in candidates if t not in used and t in full_reachable and t not in reachable]
        if vault_tiles:
            log_tile = _pick_hiding_spot(grid, vault_tiles, spawn)
        else:
            far_candidates = [t for t in candidates if t not in used]
            log_tile = _pick_hiding_spot(grid, far_candidates, exit_pos)
        if log_tile:
            pickups.append(Pickup(log_tile[0] + 0.5, log_tile[1] + 0.5, 'log'))
            used.append(log_tile)
            candidates = [t for t in candidates if t != log_tile]

        def _place_guaranteed_weapon(weapon_id):
            avail = [t for t in candidates if t not in used]
            if avail:
                tile = max(avail, key=lambda t: math.hypot(t[0] - spawn[0], t[1] - spawn[1]))
                pickups.append(Pickup(tile[0] + 0.5, tile[1] + 0.5, weapon_id))
                used.append(tile)

        for weapon_id, found_in in WEAPON_FOUND_IN_SECTOR.items():
            if found_in == index:
                _place_guaranteed_weapon(weapon_id)

        n_enemies = 4 + (index - 1) // 4
        n_pickups = 4 + index // 6
        schedule = ['grunt', 'shooter', 'charger', 'brute', 'grunt', 'turret', 'shooter']
        kind_from_sector = {'grunt': 0, 'shooter': 0, 'charger': 0, 'brute': 0, 'turret': 5}
        available_kinds = [k for k in schedule if kind_from_sector[k] <= index]
        enemy_candidates = [t for t in enemy_pool if t not in used]
        for i in range(len(enemy_candidates)):
            if len(enemies) >= n_enemies:
                break
            t = enemy_candidates[i]
            if not _far_enough(t, used, 3.0):
                continue
            used.append(t)
            slot = len(enemies)
            kind = available_kinds[slot % len(available_kinds)]
            far_from_spawn = math.hypot(t[0] - spawn[0], t[1] - spawn[1]) >= 6.5
            if kind in ('shooter', 'turret') and not far_from_spawn:
                kind = 'charger'
            enemies.append(Enemy(t[0] + 0.5, t[1] + 0.5, kind))

        kinds_cycle = ['health', 'ammo', 'ammo', 'health', 'ammo', 'health']
        remaining = [t for t in candidates if t not in used]
        for i in range(min(n_pickups, len(remaining))):
            t = remaining[i]
            used.append(t)
            pickups.append(Pickup(t[0] + 0.5, t[1] + 0.5, kinds_cycle[i % len(kinds_cycle)]))

        name = f"SECTOR {index + 1} - {SECTOR_NAMES[index]}"

    reachable_open = list(_bfs_open(grid, spawn_tile))
    full_open = list(_bfs_with_doors(grid, spawn_tile))
    avail_reach = [t for t in reachable_open if t not in used and grid[t[1]][t[0]] == WALL_EMPTY]
    avail_other = [t for t in full_open if t not in avail_reach and t not in used and grid[t[1]][t[0]] == WALL_EMPTY]
    rng.shuffle(avail_reach)
    rng.shuffle(avail_other)
    photo_pool = avail_reach + avail_other

    anomalies = []
    chosen_tiles = []
    for tdef in PHOTO_TARGET_DEFS:
        best_tile = None
        for min_spacing in (2.6, 1.8, 1.1, 0.0):
            for t in photo_pool:
                if t not in chosen_tiles and _far_enough(t, chosen_tiles, min_spacing):
                    best_tile = t
                    break
            if best_tile is not None:
                break
        if best_tile is None and open_tiles:
            best_tile = open_tiles[tdef['id'] % len(open_tiles)]
        chosen_tiles.append(best_tile)
        cx, cy = best_tile[0] + 0.5, best_tile[1] + 0.5
        comps = _make_cluster_companions(grid, cx, cy, tdef.get('cluster_count', 2), rng)
        anomalies.append(Anomaly(cx, cy, tdef, is_core=True, companions=comps))

    extra_pool = [t for t in photo_pool if t not in chosen_tiles]
    for i in range(min(6, len(extra_pool))):
        t = extra_pool[i]
        edef = ENV_PROP_DEFS[i % len(ENV_PROP_DEFS)]
        cx, cy = t[0] + 0.5, t[1] + 0.5
        comps = _make_cluster_companions(grid, cx, cy, 3, rng)
        prop_def = {
            'id': 100 + i,
            'kind': edef['kind'],
            'name': edef['name'],
            'note': edef['note'],
        }
        anomalies.append(Anomaly(cx, cy, prop_def, is_core=False, companions=comps))

    bkey_candidates = [
        t for t in reachable_open
        if grid[t[1]][t[0]] == WALL_EMPTY
        and t not in chosen_tiles
        and math.hypot(t[0] + 0.5 - spawn[0], t[1] + 0.5 - spawn[1]) >= 3.5
    ]
    if bkey_candidates:
        bkey_tile = bkey_candidates[len(bkey_candidates) // 2]
    else:
        bkey_tile = (int(spawn[0]), int(spawn[1]))
    blue_key_pos = (bkey_tile[0] + 0.5, bkey_tile[1] + 0.5)

    critters = []
    critter_tiles = [t for t in full_open if grid[t[1]][t[0]] == WALL_EMPTY]
    rng.shuffle(critter_tiles)
    n_swarms = min(14, max(8, len(critter_tiles) // 10))
    n_mice = min(14, max(8, len(critter_tiles) // 10))
    for i in range(min(n_swarms, len(critter_tiles))):
        tx, ty = critter_tiles[i]
        critters.append(Critter(tx + 0.5, ty + 0.5, 'swarm', photo_id=200 + i))
    for i in range(n_swarms, min(n_swarms + n_mice, len(critter_tiles))):
        tx, ty = critter_tiles[i]
        critters.append(Critter(tx + 0.5, ty + 0.5, 'mouse', photo_id=200 + i))

    return LevelState(grid, spawn, exit_pos, enemies, pickups, anomalies, critters,
                      blue_key_pos, name)


def _bfs_open(grid, start):
    from collections import deque
    h, w = len(grid), len(grid[0])
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen:
                v = grid[ny][nx]
                if v in (WALL_EMPTY, EXIT_TILE):
                    seen.add((nx, ny))
                    q.append((nx, ny))
    return seen


def _bfs_with_doors(grid, start):
    from collections import deque
    h, w = len(grid), len(grid[0])
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen:
                v = grid[ny][nx]
                if v in (WALL_EMPTY, EXIT_TILE, WALL_DOOR):
                    seen.add((nx, ny))
                    q.append((nx, ny))
    return seen


def _open_neighbor_count(grid, t):
    x, y = t
    h, w = len(grid), len(grid[0])
    c = 0
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] in (WALL_EMPTY, EXIT_TILE, WALL_DOOR):
            c += 1
    return c


def _pick_hiding_spot(grid, pool, anchor):
    if not pool:
        return None
    dead_ends = [t for t in pool if _open_neighbor_count(grid, t) <= 1]
    search_pool = dead_ends if dead_ends else pool
    return max(search_pool, key=lambda t: math.hypot(t[0] - anchor[0], t[1] - anchor[1]))


# ----------------------------------------------------------------------------------
# FULLY VECTORIZED HIGH-SPEED RENDERER (CRISP GRAPHICS & SMOOTH 60 FPS)
# ----------------------------------------------------------------------------------

class Renderer:
    def __init__(self, screen, textures, rw=RENDER_W, rh=RENDER_H):
        self.screen = screen
        self.rw = rw
        self.rh = rh
        self.render_surf = pygame.Surface((rw, rh))
        self.zbuffer = [MAX_DEPTH] * rw
        self.wall_hit_types = [WALL_STONE] * rw
        self.textures = textures
        self.flicker = 1.0
        self._flicker_target = 1.0
        self._flicker_hold = 0.0
        self.brightness = BRIGHTNESS_DEFAULT
        self.dread = 0.0
        self._base_textures = textures
        self.wall_surfs = {}
        for wid, arr in textures.items():
            if isinstance(wid, int):
                surf = pygame.surfarray.make_surface(np.transpose(arr, (1, 0, 2)))
                self.wall_surfs[wid] = surf
        self.nv_active = False
        self.floor_tex = textures['floor'].astype(np.float32)
        self.ceil_tex = textures['ceiling'].astype(np.float32)
        self._init_lut()

    def _init_lut(self):
        """Pre-allocate 2D NumPy broadcasting tables for zero-loop floor & ceiling casting."""
        W, H = self.rw, self.rh
        half = H // 2
        ps = np.arange(1, half + 1, dtype=np.float32)[:, None]      # shape (half, 1)
        self._row_dists = (0.5 * H) / ps                            # shape (half, 1)
        self._xs_norm = (np.arange(W, dtype=np.float32) / W)[None, :]  # shape (1, W)
        self._fogs = np.clip(1.0 - self._row_dists / MAX_DEPTH, 0.0, 1.0)[:, :, None]

    def update_sector_writings(self, sector_idx):
        """Stamp place-specific wall writings onto blood & graffiti walls for the current sector."""
        w1, w2, w3 = SECTOR_WALL_WRITINGS[sector_idx % len(SECTOR_WALL_WRITINGS)]
        rng = np.random.default_rng(7000 + sector_idx * 131)

        # Blood brick: primary warning phrase
        b_brick = self._base_textures[WALL_BRICK].astype(np.float32).copy()
        _stamp_blood_word(b_brick, w1, 6, 16, scale=2 if len(w1) > 6 else 3, rng=rng)
        if len(w3) <= 8:
            _stamp_blood_word(b_brick, w3, 8, 40, scale=1, rng=rng)
        self.wall_surfs[WALL_BLOOD_BRICK] = pygame.surfarray.make_surface(
            np.transpose(_clamp(b_brick), (1, 0, 2))
        )

        # Graffiti stone: two stacked place-specific phrases
        graf = self._base_textures[WALL_STONE].astype(np.float32).copy()
        _stamp_blood_word(graf, w2, 6, 12, scale=2 if len(w2) <= 7 else 1, rng=rng)
        _stamp_blood_word(graf, w3, 6, 36, scale=2 if len(w3) <= 7 else 1, rng=rng)
        self.wall_surfs[WALL_GRAFFITI] = pygame.surfarray.make_surface(
            np.transpose(_clamp(graf), (1, 0, 2))
        )

        # Blood stone & blood metal: sigil/handprint + short etched word
        b_stone = _stamp_blood_splatter_and_sigil(self._base_textures[WALL_STONE], rng, mode='sigil').astype(np.float32)
        _stamp_blood_word(b_stone, w2[:8], 8, 42, scale=1, rng=rng)
        self.wall_surfs[WALL_BLOOD_STONE] = pygame.surfarray.make_surface(
            np.transpose(_clamp(b_stone), (1, 0, 2))
        )
        b_metal = _stamp_blood_splatter_and_sigil(self._base_textures[WALL_METAL], rng, mode='handprint').astype(np.float32)
        _stamp_blood_word(b_metal, w1[:8], 8, 44, scale=1, rng=rng)
        self.wall_surfs[WALL_BLOOD_METAL] = pygame.surfarray.make_surface(
            np.transpose(_clamp(b_metal), (1, 0, 2))
        )

    def set_resolution(self, rw, rh):
        global RENDER_W, RENDER_H
        RENDER_W, RENDER_H = rw, rh
        self.rw, self.rh = rw, rh
        self.render_surf = pygame.Surface((rw, rh))
        self.zbuffer = [MAX_DEPTH] * rw
        self.wall_hit_types = [WALL_STONE] * rw
        self._init_lut()

    def light_level(self, fog, dist=None, beam_factor=1.0):
        # Unsettling dark ambient with readable close-range camcorder flashlight cone
        if self.nv_active:
            base = 0.40 + 0.72 * (fog ** 1.1)
        else:
            close_cone = 0.0
            if dist is not None and dist < 4.8:
                close_cone = (1.0 - dist / 4.8) ** 1.45 * 0.62 * beam_factor
            base = AMBIENT_LIGHT + LIGHT_FALLOFF * (fog ** 2.35) * 0.72 + close_cone
        return min(1.35, base * self.brightness)

    def draw_floor_ceiling(self, player):
        """100% Vectorized 2D NumPy Floor & Ceiling Caster (zero Python row loop!)."""
        W, H = self.rw, self.rh
        half = H // 2
        dirX, dirY = math.cos(player.angle), math.sin(player.angle)
        plane_len = math.tan(HALF_FOV)
        planeX, planeY = -dirY * plane_len, dirX * plane_len

        rayDirX0, rayDirY0 = dirX - planeX, dirY - planeY
        rayDirX1, rayDirY1 = dirX + planeX, dirY + planeY

        row_dists = self._row_dists
        xs = self._xs_norm

        fx = player.x + row_dists * (rayDirX0 + (rayDirX1 - rayDirX0) * xs)
        fy = player.y + row_dists * (rayDirY0 + (rayDirY1 - rayDirY0) * xs)

        TS = TEX_SIZE
        tx = (np.mod(fx, 1.0) * TS).astype(np.int32) & (TS - 1)
        ty = (np.mod(fy, 1.0) * TS).astype(np.int32) & (TS - 1)

        if self.nv_active:
            shades = (0.40 + 0.72 * (self._fogs ** 1.1)) * self.brightness
        else:
            d = self._row_dists[:, :, None]
            close_c = np.clip(1.0 - d / 4.8, 0.0, 1.0) ** 1.45 * 0.56
            # Subtle center flashlight beam cone across screen X
            beam_x = (1.0 - np.abs(self._xs_norm * 2.0 - 1.0) * 0.45)[:, :, None]
            shades = (AMBIENT_LIGHT + LIGHT_FALLOFF * (self._fogs ** 2.35) * 0.68 + close_c * beam_x) * self.brightness
        # Subtle wet-floor specular sheen near player
        spec = np.where((tx % 8 == 0) | (ty % 8 == 0), 0.88, 1.04)[:, :, None]

        floor_half = np.clip(self.floor_tex[ty, tx] * shades * spec, 0, 255).astype(np.uint8)
        ceil_half = np.clip(self.ceil_tex[ty, tx] * shades, 0, 255).astype(np.uint8)

        buf = np.empty((H, W, 3), dtype=np.uint8)
        buf[:half] = ceil_half[::-1]
        if H % 2 == 1:
            buf[half] = (14, 15, 20)
        buf[H - half:] = floor_half

        pygame.surfarray.blit_array(self.render_surf, np.transpose(buf, (1, 0, 2)))

    def draw_walls(self, player, grid, opened_doors):
        W, H = self.rw, self.rh
        dirX, dirY = math.cos(player.angle), math.sin(player.angle)
        plane_len = math.tan(HALF_FOV)
        planeX, planeY = -dirY * plane_len, dirX * plane_len
        posX, posY = player.x, player.y

        for x in range(W):
            cameraX = 2 * x / W - 1
            rayDirX = dirX + planeX * cameraX
            rayDirY = dirY + planeY * cameraX

            mapX, mapY = int(posX), int(posY)

            deltaDistX = abs(1 / rayDirX) if rayDirX != 0 else 1e30
            deltaDistY = abs(1 / rayDirY) if rayDirY != 0 else 1e30

            if rayDirX < 0:
                stepX = -1
                sideDistX = (posX - mapX) * deltaDistX
            else:
                stepX = 1
                sideDistX = (mapX + 1.0 - posX) * deltaDistX
            if rayDirY < 0:
                stepY = -1
                sideDistY = (posY - mapY) * deltaDistY
            else:
                stepY = 1
                sideDistY = (mapY + 1.0 - posY) * deltaDistY

            side = 0
            wall_type = 1
            for _ in range(48):
                if sideDistX < sideDistY:
                    sideDistX += deltaDistX
                    mapX += stepX
                    side = 0
                else:
                    sideDistY += deltaDistY
                    mapY += stepY
                    side = 1
                if mapY < 0 or mapY >= len(grid) or mapX < 0 or mapX >= len(grid[0]):
                    wall_type = WALL_STONE
                    break
                v = grid[mapY][mapX]
                if v == WALL_DOOR and (mapX, mapY) in opened_doors:
                    continue
                if v not in (WALL_EMPTY, EXIT_TILE):
                    wall_type = v
                    break

            if side == 0:
                perp_dist = max(0.0001, (mapX - posX + (1 - stepX) / 2) / rayDirX)
            else:
                perp_dist = max(0.0001, (mapY - posY + (1 - stepY) / 2) / rayDirY)

            self.zbuffer[x] = perp_dist
            self.wall_hit_types[x] = wall_type
            line_h = int(H / perp_dist) if perp_dist > 0 else H
            draw_start = max(0, -line_h // 2 + H // 2)
            draw_end = min(H - 1, line_h // 2 + H // 2)

            if side == 0:
                wallX = posY + perp_dist * rayDirY
            else:
                wallX = posX + perp_dist * rayDirX
            wallX -= math.floor(wallX)
            texX = int(wallX * TEX_SIZE)
            if (side == 0 and rayDirX < 0) or (side == 1 and rayDirY > 0):
                texX = TEX_SIZE - texX - 1
            texX = min(TEX_SIZE - 1, max(0, texX))

            tex_surf = self.wall_surfs.get(wall_type, self.wall_surfs[WALL_STONE])
            strip = tex_surf.subsurface((texX, 0, 1, TEX_SIZE))
            seg_h = max(1, draw_end - draw_start)
            scaled = pygame.transform.scale(strip, (1, seg_h))

            fog = max(0.0, 1.0 - perp_dist / MAX_DEPTH)
            # Subtle ambient occlusion near wall edges (wallX near 0 or 1)
            edge_ao = 0.88 + 0.12 * min(1.0, min(wallX, 1.0 - wallX) * 10.0)
            beam_f = 1.0 - abs(cameraX) * 0.35
            lit = self.light_level(fog, perp_dist, beam_f) * (0.76 if side == 1 else 1.0) * edge_ao
            shade_val = int(255 * min(1.0, lit))
            if shade_val < 255:
                scaled = scaled.copy()
                scaled.fill((shade_val, shade_val, shade_val), special_flags=pygame.BLEND_RGB_MULT)

            self.render_surf.blit(scaled, (x, draw_start))

    def draw_sprites(self, player, grid, sprite_list):
        W, H = self.rw, self.rh
        dirX, dirY = math.cos(player.angle), math.sin(player.angle)
        plane_len = math.tan(HALF_FOV)
        planeX, planeY = -dirY * plane_len, dirX * plane_len

        items = []
        for item in sprite_list:
            sx, sy, surf, scale, voffset = item[:5]
            add = item[5] if len(item) > 5 else None
            emissive = item[6] if len(item) > 6 else False
            dx, dy = sx - player.x, sy - player.y
            dist2 = dx * dx + dy * dy
            items.append((dist2, sx, sy, dx, dy, surf, scale, voffset, add, emissive))
        items.sort(key=lambda i: -i[0])

        invDet = 1.0 / (planeX * dirY - dirX * planeY + 1e-9)
        zbuf = self.zbuffer

        for dist2, sx, sy, dx, dy, surf, scale, voffset, add, emissive in items:
            transformX = invDet * (dirY * dx - dirX * dy)
            transformY = invDet * (-planeY * dx + planeX * dy)
            if transformY <= 0.15 or transformY > MAX_DEPTH * 0.85:
                continue

            if not has_visibility_cone(grid, player.x, player.y, sx, sy):
                continue

            sprite_screen_x = int((W / 2) * (1 + transformX / transformY))

            sprite_h = abs(int((H / transformY) * scale))
            sprite_w = sprite_h
            if sprite_h <= 0 or sprite_h > 4000:
                continue

            v_move = int((H / transformY) * voffset)
            draw_start_y = -sprite_h // 2 + H // 2 + v_move
            draw_start_x = -sprite_w // 2 + sprite_screen_x
            draw_end_x = sprite_w // 2 + sprite_screen_x

            col0 = max(0, draw_start_x)
            col1 = min(W - 1, draw_end_x)
            if col1 < col0:
                continue

            spans = []
            span_start = None
            for x in range(col0, col1 + 1):
                if transformY < zbuf[x] - 0.02:
                    if span_start is None:
                        span_start = x
                else:
                    if span_start is not None:
                        spans.append((span_start, x - 1))
                        span_start = None
            if span_start is not None:
                spans.append((span_start, col1))

            if not spans:
                continue

            fog = max(0.0, 1.0 - transformY / MAX_DEPTH)
            shade_val = 255 if emissive else int(255 * min(1.0, self.light_level(fog, transformY, 0.95) * 1.12))

            scaled = pygame.transform.scale(surf, (max(1, sprite_w), max(1, sprite_h)))
            if shade_val < 255:
                scaled.fill((shade_val, shade_val, shade_val, 255), special_flags=pygame.BLEND_RGBA_MULT)
            if add:
                scaled.fill((max(0, min(255, int(add[0]))), max(0, min(255, int(add[1]))),
                             max(0, min(255, int(add[2])))), special_flags=pygame.BLEND_RGB_ADD)

            sw, sh = scaled.get_width(), scaled.get_height()
            for x0, x1 in spans:
                src_x0 = max(0, min(sw, x0 - draw_start_x))
                src_x1 = max(0, min(sw, x1 - draw_start_x + 1))
                if src_x1 > src_x0:
                    chunk = scaled.subsurface((src_x0, 0, src_x1 - src_x0, sh))
                    self.render_surf.blit(chunk, (x0, draw_start_y))

    def update_flicker(self, dt):
        self._flicker_hold -= dt
        if self._flicker_hold <= 0:
            self._flicker_hold = max(0.35, random.uniform(0.5, 1.6) * (1.0 - 0.55 * self.dread))
            self._flicker_target = random.uniform(0.88 - 0.38 * self.dread, 1.0)
        self.flicker += (self._flicker_target - self.flicker) * min(1.0, dt * 3.0)

    def apply_flicker_overlay(self):
        if self.flicker >= 0.995:
            return
        level = int(255 * self.flicker)
        self.render_surf.fill((level, level, level), special_flags=pygame.BLEND_RGB_MULT)

    def present(self):
        pygame.transform.scale(self.render_surf, (DISPLAY_W, DISPLAY_H), self.screen)


# ----------------------------------------------------------------------------------
# GAME LOGIC & STRICT OCCLUSION HELPERS
# ----------------------------------------------------------------------------------

def has_line_of_sight(grid, x0, y0, x1, y1):
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist < 1e-4:
        return True
    steps = max(2, int(dist / 0.06))
    prev_ix, prev_iy = int(x0), int(y0)
    for i in range(1, steps):
        t = i / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        ix, iy = int(x), int(y)
        if is_wall(grid, x, y):
            return False
        if ix != prev_ix and iy != prev_iy:
            if is_wall(grid, prev_ix + 0.5, iy + 0.5) and is_wall(grid, ix + 0.5, prev_iy + 0.5):
                return False
        prev_ix, prev_iy = ix, iy
    return True


def has_visibility_cone(grid, x0, y0, x1, y1, radius=0.18):
    if has_line_of_sight(grid, x0, y0, x1, y1):
        return True
    dx, dy = x1 - x0, y1 - y0
    d = math.hypot(dx, dy)
    if d < 0.25:
        return True
    px, py = -dy / d * radius, dx / d * radius
    return (has_line_of_sight(grid, x0, y0, x1 + px, y1 + py)
            or has_line_of_sight(grid, x0, y0, x1 - px, y1 - py))


def move_enemy_toward(grid, enemy, tx, ty, dist):
    dx, dy = tx - enemy.x, ty - enemy.y
    d = math.hypot(dx, dy)
    if d < 1e-5:
        return
    dx, dy = dx / d * dist, dy / d * dist
    r = 0.25
    if not is_wall(grid, enemy.x + dx + math.copysign(r, dx), enemy.y):
        enemy.x += dx
    if not is_wall(grid, enemy.x, enemy.y + dy + math.copysign(r, dy)):
        enemy.y += dy


# ----------------------------------------------------------------------------------
# MAIN GAME CLASS
# ----------------------------------------------------------------------------------

STATE_SPLASH = 'splash'
STATE_MENU = 'menu'
STATE_STORY_INTRO = 'story_intro'
STATE_LEVEL_SELECT = 'level_select'
STATE_SETTINGS = 'settings'
STATE_PLAYING = 'playing'
STATE_PAUSED = 'paused'
STATE_GAMEOVER = 'gameover'
STATE_WIN = 'win'
STATE_LEVEL_INTRO = 'level_intro'
STATE_READING = 'reading'
STATE_ARCHIVE = 'archive'

_SOFT_STATES = (STATE_PAUSED, STATE_READING)


class Game:
    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        old = getattr(self, '_state', None)
        self._state = value
        if old is not None and old != value and old not in _SOFT_STATES and value not in _SOFT_STATES:
            self.fade = 0.85

    def __init__(self, unlock_all=False):
        self.fade = 0.0
        pygame.mixer.pre_init(MIXER_RATE, -16, 2, 512)
        pygame.init()
        pygame.mixer.init(MIXER_RATE, -16, 2, 512)
        pygame.mixer.set_num_channels(24)
        pygame.mixer.set_reserved(2)
        self.ambient_ch = pygame.mixer.Channel(0)
        self.heart_ch = pygame.mixer.Channel(1)
        pygame.display.set_caption("VOIDWALKER — A KS_5G1 Production")
        try:
            pygame.display.set_icon(make_window_icon_surface())
        except Exception:
            pass

        cfg = load_settings()
        self.mouse_sens = cfg["mouse_sens"]
        self.master_volume = cfg["master_volume"]
        self.horror_volume = cfg["horror_volume"]
        self.brightness = cfg["brightness"]
        self.fov_deg = cfg["fov_deg"]
        self.res_index = cfg["res_index"]
        self.shake_scale = cfg["shake"]
        self.vhs_effect = cfg["vhs_effect"]
        self.head_bob = cfg["head_bob"]
        self.touch_controls = cfg["touch_controls"]
        self.fullscreen = cfg["fullscreen"]
        self._apply_fov()

        self.window = None
        self._present_rect = pygame.Rect(0, 0, DISPLAY_W, DISPLAY_H)
        self._apply_display_mode()
        self.screen = pygame.Surface((DISPLAY_W, DISPLAY_H))
        self.clock = pygame.time.Clock()

        self.textures = build_textures()
        _, rw, rh = RES_PRESETS[self.res_index]
        self.renderer = Renderer(self.screen, self.textures, rw=rw, rh=rh)
        self.renderer.brightness = self.brightness
        self.sounds = build_sounds()
        self._vignette_surf = self._build_vignette_surf()
        self._scanline_surf = self._build_scanline_surf()

        self._apply_volume()
        self.lore_found = load_lore_progress()

        self.reading_text = ""
        self.reading_index = 0
        self.reading_is_new = False
        self.reading_t = 0.0

        self.archive_sel = 0
        self.archive_tab = 0
        self.archive_return_state = STATE_MENU

        self.heart_t = 0.0
        self.heart_period = 1.15
        self.scare_cd = 0.0
        self.dread = 0.0
        self.scare_flash = 0.0
        self.ambient_event_t = 25.0
        self._ambient_paused = False

        self.font_big = pygame.font.SysFont("georgia", 50, bold=True)
        self.font_med = pygame.font.SysFont("georgia", 25, bold=True)
        self.font_small = pygame.font.SysFont("consolas", 17)
        self.font_tiny = pygame.font.SysFont("consolas", 13)

        # Build enemy surfaces: 6 frames for Floating Skull ('grunt'), Evaporating Shadow ('charger'),
        # and Reanimated Dead Body ('brute' - replaces the big purple guy!)
        self.enemy_surfs = {}
        for kind in ('grunt', 'brute', 'shooter', 'charger', 'turret'):
            max_f = 6 if kind in ('grunt', 'charger', 'brute') else 4
            for f in range(max_f):
                self.enemy_surfs[(kind, f)] = make_enemy_surface(kind, f)

        self.pickup_surfs = {
            k: make_pickup_surface(k) for k in
            ['health', 'ammo', 'key', 'blue_key', 'log'] + [w['id'] for w in WEAPON_DEFS]
        }
        all_prop_kinds = [tdef['kind'] for tdef in PHOTO_TARGET_DEFS] + [edef['kind'] for edef in ENV_PROP_DEFS]
        self.anomaly_surfs = {k: make_anomaly_surface(k) for k in all_prop_kinds}
        self.insect_surfs = make_insect_swarm_surfaces()
        self.mouse_surfs = make_mouse_surfaces()

        # 8 detailed frames per gun (including multi-stage hand reload & switch animations!)
        self.gun_frames_by_weapon = [make_gun_surfaces(w['id']) for w in WEAPON_DEFS]
        self.gun_frames_scaled = [
            [pygame.transform.smoothscale(f, (int(f.get_width() * 1.6), int(f.get_height() * 1.6)))
             for f in frames]
            for frames in self.gun_frames_by_weapon
        ]
        self._overlay_surfs = {}
        self._beam_surf = pygame.Surface((DISPLAY_W, DISPLAY_H), pygame.SRCALPHA)
        self._hb_surf = self._build_heartbeat_surf()
        self.cross_gap = 5.0
        self.on_target = False
        self._menu_fog = self._build_fog_surf()

        self.sector_photos = {}
        self.sector_blog_photos = {}
        self.all_captured_photos = []
        self.unposted_blog_photos = []
        self.uncompiled_book_photos = []
        self.notebook_entries = []
        self.visited_sectors = []

        self.followers = 100000
        self.live_viewers = 4200
        self.stream_likes = 18500
        self.stream_comments = [
            ("@urbex_maya", "Congrats on 100K Kaelen!! Stay safe in there!"),
            ("@skeptic_dan", "Let's see if he actually finds anything real tonight..."),
            ("@night_crawler", "Audio on the shotgun mic sounds super eerie already."),
        ]
        self.live_chat_fade = 4.0

        self.blog_posts = []
        self.blog_total_views = 84000
        self.blog_total_likes = 9200
        self.blog_subscribers = 24500

        self.book_chapters = []
        self.book_preorders = 3100
        self.book_word_count = 12400

        self.camera_flash = 0.0
        self.photo_preview_surf = None
        self.photo_preview_label = ""
        self.photo_preview_sub = ""
        self.photo_preview_t = 0.0
        self.viewfinder_on = True
        self.game_mode = 0
        self.night_vision = False
        self.nv_battery = 1.0
        self.ambient_chat_t = 6.0
        self.superchat_queue = []
        self.active_superchat = None
        self.sc_photos_taken = 0
        self.sc_kills = 0
        self.sc_still_t = 0.0
        self.sc_fired = False
        self.sc_used_ir = False
        self._hud_touch_rect = None
        self._menu_touch_rect = None
        self._pause_rects = []
        self._settings_rects = []
        self._settings_back_rect = None
        self._archive_tab_rects = []
        self._archive_back_rect = None
        self._lvl_mode_rect = None
        self._lvl_back_rect = None
        self.current_photo_candidate = None
        self.monologue_text = ""
        self.monologue_t = 0.0
        self.monologue_total = 0.0
        self.ambient_talk_cd = 18.0
        self.social_tick_t = 4.0
        self.story_unlocked = False

        # In-Game Controls & Features Field Manual overlay (toggled with H or F1)
        self.show_controls_help = False
        self.sector_play_t = 0.0          # drives gentle contextual control hints in first moments

        # On-Screen Mobile Touch Controls state
        self.touch_joy_center = (128, DISPLAY_H - 128)
        self.touch_joy_radius = 68
        self.touch_move_vec = [0.0, 0.0]  # [strafe, forward] in -1..1
        self.touch_fire_held = False
        self._touch_buttons = {}

        self.splash_t = 0.0
        self.splash_sound_played = False
        self.menu_selected = 0
        self._menu_rects = []
        self.story_intro_t = 0.0
        self.story_intro_chars = 0
        self.story_intro_target_sector = 0
        self.story_intro_seen = False

        self.state = STATE_SPLASH
        self.level_index = 0
        self.level = None
        self.player = None
        self.time = 0.0
        self.level_intro_t = 0.0
        self.gun_frame = 0
        self.gun_timer = 0.0
        self.bob_t = 0.0
        self.fx_surfs = make_fx_surfaces()
        self.projectiles = []
        self.effects = []
        self.timed_sounds = []
        self.shake = 0.0
        self.recoil = 0.0
        self.sway_x = 0.0
        self.muzzle_light = 0.0
        self.muzzle_col = (255, 220, 150)
        self.hit_t = 0.0
        self.beam_t = 0.0
        self.vm_index = 0
        self.vm_drop = 0.0
        self.step_dist = 0.0
        self.step_i = 0
        self.hp_shown = self.hp_ghost = self.hp_last = float(PLAYER_MAX_HP)
        self.ghost_delay = 0.0
        self.dmg_marks = []
        self.messages = []
        self.show_big_map = False
        self._last_tile = None
        self.notice_text = ""
        self.notice_t = 0.0

        self.selected_level = 0
        if unlock_all:
            self.highest_unlocked, self.weapons_found = len(LEVELS) - 1, set()
        else:
            self.highest_unlocked, self.weapons_found = load_progress(len(LEVELS))
        self.unlock_all = unlock_all
        self._level_select_rects = []

        self.settings_return_state = STATE_MENU
        self.settings_selected = 0

        self._loadout_snapshot = None

    def _apply_fov(self):
        global FOV, HALF_FOV
        FOV = math.radians(self.fov_deg)
        HALF_FOV = FOV / 2.0

    def _apply_volume(self):
        for k, s in self.sounds.items():
            mult = self.horror_volume if k in HORROR_SOUND_KEYS else 1.0
            s.set_volume(self.master_volume * mult)

    def _save_settings(self):
        save_settings({
            "mouse_sens": self.mouse_sens,
            "master_volume": self.master_volume,
            "horror_volume": self.horror_volume,
            "brightness": self.brightness,
            "fov_deg": self.fov_deg,
            "res_index": self.res_index,
            "shake": self.shake_scale,
            "vhs_effect": self.vhs_effect,
            "head_bob": self.head_bob,
            "touch_controls": self.touch_controls,
            "fullscreen": self.fullscreen,
        })

    def _apply_display_mode(self):
        try:
            if self.fullscreen:
                self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)
            else:
                self.window = pygame.display.set_mode((DISPLAY_W, DISPLAY_H), pygame.DOUBLEBUF)
        except pygame.error:
            self.fullscreen = False
            self.window = pygame.display.set_mode((DISPLAY_W, DISPLAY_H), pygame.DOUBLEBUF)
        ww, wh = self.window.get_size()
        scale = min(ww / DISPLAY_W, wh / DISPLAY_H)
        dw, dh = max(1, int(DISPLAY_W * scale)), max(1, int(DISPLAY_H * scale))
        self._present_rect = pygame.Rect((ww - dw) // 2, (wh - dh) // 2, dw, dh)
        self.window.fill((0, 0, 0))

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self._apply_display_mode()
        in_world = self.state in (STATE_PLAYING, STATE_LEVEL_INTRO, STATE_READING) and not self.touch_controls
        pygame.event.set_grab(in_world)
        pygame.mouse.set_visible(not in_world)
        pygame.mouse.get_rel()
        self._save_settings()

    def _present(self):
        if self.vhs_effect:
            self.screen.blit(self._scanline_surf, (0, 0))
        r = self._present_rect
        if r.size == (DISPLAY_W, DISPLAY_H) and r.topleft == (0, 0):
            self.window.blit(self.screen, (0, 0))
            return
        self.window.fill((0, 0, 0))
        try:
            pygame.transform.scale(self.screen, r.size, self.window.subsurface(r))
        except (ValueError, pygame.error):
            self.window.blit(pygame.transform.scale(self.screen, r.size), r.topleft)

    def _to_canvas(self, pos):
        r = self._present_rect
        if r.w <= 0 or r.h <= 0:
            return pos
        return ((pos[0] - r.x) * DISPLAY_W / r.w, (pos[1] - r.y) * DISPLAY_H / r.h)

    def _snapshot_loadout(self):
        p = self.player
        self._loadout_snapshot = {
            'hp': p.hp,
            'weapons_owned': list(p.weapons_owned),
            'ammo': dict(p.ammo),
            'reserve': dict(p.reserve),
            'weapon_index': p.weapon_index,
            'kills': p.kills,
        }

    def _restart_level(self, after_death=False):
        snap = self._loadout_snapshot
        self.load_level(self.level_index)
        if snap:
            p = self.player
            p.hp = max(snap['hp'], 50) if after_death else snap['hp']
            p.weapons_owned = list(snap['weapons_owned'])
            p.ammo = dict(snap['ammo'])
            p.reserve = dict(snap['reserve'])
            p.weapon_index = snap['weapon_index']
            p.kills = snap['kills']
        self._enter_intro()

    def _enter_intro(self):
        self.state = STATE_LEVEL_INTRO
        self.level_intro_t = 0.0
        self._sync_feel()

    def _begin_level(self):
        if self.state == STATE_LEVEL_INTRO and self.level_intro_t >= 0.6:
            self.state = STATE_PLAYING
            pygame.event.set_grab(not self.touch_controls)
            pygame.mouse.set_visible(self.touch_controls)
            pygame.mouse.get_rel()
            sname = SECTOR_NAMES[self.level_index]
            if sname not in self.visited_sectors:
                self.visited_sectors.append(sname)
            if 0 <= self.level_index < len(SECTOR_INTRO_MONOLOGUES):
                self._speak_and_write_note(
                    f"SITE ARRIVAL: {sname}",
                    SECTOR_INTRO_MONOLOGUES[self.level_index],
                    dur=6.5,
                )

    def _launch_sector_with_typing_intro(self, level_index=0):
        self.story_intro_target_sector = level_index
        self.story_intro_t = 0.0
        self.story_intro_chars = 0
        self.state = STATE_STORY_INTRO

    def start_new_game(self, level_index=0):
        self.level_index = level_index
        self.load_level(level_index)
        for weapon_id, found_in in WEAPON_FOUND_IN_SECTOR.items():
            if level_index > found_in and (weapon_id in self.weapons_found or self.unlock_all):
                self._grant_weapon(weapon_index(weapon_id))
        self.player.ensure_valid_weapon()
        self._snapshot_loadout()
        self._enter_intro()

    def _grant_weapon(self, widx):
        wdef = WEAPON_DEFS[widx]
        self.player.weapons_owned[widx] = True
        self.player.ammo[widx] = wdef['mag_size']
        self.player.reserve[widx] = wdef['start_reserve']

    def load_level(self, index):
        self.level = build_level(index)
        self.renderer.update_sector_writings(index)
        self.nv_battery = 1.0
        self.night_vision = False
        self.renderer.nv_active = False
        sx, sy = self.level.spawn
        self.player = Player(sx, sy, angle=0.0)
        pygame.event.set_grab(not self.touch_controls)
        pygame.mouse.set_visible(self.touch_controls)
        pygame.mouse.get_rel()
        self.messages = []
        self.show_big_map = False
        self.show_controls_help = False
        self.sector_play_t = 0.0
        self.touch_move_vec = [0.0, 0.0]
        self.touch_fire_held = False
        self._last_tile = None
        self.heart_t = 0.0
        self.heart_period = 1.15
        self.scare_cd = 0.0
        self.scare_flash = 0.0
        self.ambient_event_t = random.uniform(12.0, 22.0)
        n_sc = random.randint(1, 4)
        self.superchat_queue = [10.0 + i * random.uniform(22.0, 30.0) for i in range(n_sc)]
        self.active_superchat = None
        self.sc_photos_taken = 0
        self.sc_kills = 0
        self.sc_still_t = 0.0
        self.sc_fired = False
        self.sc_used_ir = False
        self.dread = 0.0
        self.ambient_ch.stop()
        self._ambient_paused = False
        self.projectiles = []
        self.effects = []
        self.timed_sounds = []
        self.shake = self.recoil = self.sway_x = self.muzzle_light = 0.0
        self.hit_t = self.beam_t = 0.0
        self.dmg_marks = []
        self.sector_photos = {}
        self.sector_blog_photos = {}
        self.camera_flash = 0.0
        self.photo_preview_t = 0.0
        self.current_photo_candidate = None
        self.ambient_talk_cd = 16.0
        self._sync_feel()

    # ------------------------------------------------------------------ Creator Monologue & Social Handles
    def _speak_and_write_note(self, title, text, dur=5.2):
        self.monologue_text = text
        self.monologue_total = max(dur, 3.5 + 0.035 * len(text))
        self.monologue_t = self.monologue_total
        self.sounds['scribble'].play()
        stamp = f"S{self.level_index + 1} | {len(self.sector_photos)} PROOF"
        if not self.notebook_entries or self.notebook_entries[-1][1] != title:
            self.notebook_entries.append((stamp, title, text))

    def _toggle_touch_controls(self):
        self.touch_controls = not self.touch_controls
        if self.state == STATE_PLAYING:
            pygame.event.set_grab(not self.touch_controls)
            pygame.mouse.set_visible(self.touch_controls)
            pygame.mouse.get_rel()
        self._save_settings()
        self.sounds['ui_tick'].play()
        self.show_message("CONTROLS: MOBILE TOUCH" if self.touch_controls else "CONTROLS: PC KEYBOARD & MOUSE", 1.6)

    def _spawn_superchat_challenge(self):
        pool = [c for c in SUPERCHAT_CHALLENGES if (c[0] != 'no_ir' or self._is_nv_allowed())]
        cid, donor, amt, desc, dur, reward = random.choice(pool)
        self.active_superchat = {
            'id': cid, 'donor': donor, 'amt': amt, 'desc': desc,
            'dur': dur, 'left': dur, 'reward': reward,
        }
        self.sc_photos_taken = 0
        self.sc_kills = 0
        self.sc_still_t = 0.0
        self.sc_fired = False
        self.sc_used_ir = self.night_vision
        self.stream_comments.append((donor, f"${amt} SUPERCHAT CHALLENGE: {desc}"))
        if len(self.stream_comments) > 18:
            self.stream_comments.pop(0)
        self.live_chat_fade = 6.0
        self.sounds['log'].play()

    def _complete_superchat(self):
        sc = self.active_superchat
        if not sc:
            return
        mult = GAME_MODES[self.game_mode][2]
        f_gain = int(sc['reward'] * mult)
        v_gain = int(sc['amt'] * 12 * mult)
        self.followers += f_gain
        self.live_viewers += v_gain
        self.stream_likes += sc['amt'] * 30
        self.stream_comments.append(('@MOD_BOT', f"SUPERCHAT CLEARED! +{f_gain:,} followers from {sc['donor']}!"))
        if len(self.stream_comments) > 18:
            self.stream_comments.pop(0)
        self.live_chat_fade = 6.0
        self.sounds['ui_ok'].play()
        self.show_message(f"${sc['amt']} SUPERCHAT CLEARED! +{f_gain:,} Followers", 2.4)
        self.active_superchat = None

    def _fail_superchat(self, reason="TIME UP"):
        sc = self.active_superchat
        if not sc:
            return
        self.stream_comments.append((sc['donor'], f"Challenge failed ({reason})! Better luck next time!"))
        if len(self.stream_comments) > 18:
            self.stream_comments.pop(0)
        self.live_chat_fade = 4.5
        self.sounds['deny'].play()
        self.show_message(f"SUPERCHAT FAILED: {reason}", 1.8)
        self.active_superchat = None

    def _is_nv_allowed(self):
        return GAME_MODES[self.game_mode][1] and (self.level_index not in EMF_JAMMED_SECTORS)

    def _toggle_night_vision(self):
        if not self._is_nv_allowed():
            self.night_vision = False
            self.sounds['deny'].play()
            if not GAME_MODES[self.game_mode][1]:
                self.show_message(f"IR NIGHT VISION DISABLED IN {GAME_MODES[self.game_mode][0]}", 2.0)
            else:
                self.show_message("IR OPTICS JAMMED BY SITE RADIATION / EMF", 2.0)
            return
        if self.nv_battery <= 0.0:
            self.night_vision = False
            self.sounds['deny'].play()
            self.show_message("IR BATTERY DEAD — FRESH CELL NEXT SECTOR", 1.8)
            return
        self.night_vision = not self.night_vision
        self.sounds['ui_tick'].play()

    def _push_ambient_chat(self):
        site_pool = SECTOR_STREAM_COMMENTS[self.level_index % len(SECTOR_STREAM_COMMENTS)]
        if random.random() < 0.55 and site_pool:
            raw = random.choice(site_pool)
            if ':' in raw:
                handle, cmt = raw.split(':', 1)
                handle, cmt = handle.strip(), cmt.strip()
            else:
                handle, cmt = '@urbex_maya', raw
        else:
            handle, cmt = random.choice(GENERAL_STREAM_COMMENTS)
        self.stream_comments.append((handle, cmt))
        if len(self.stream_comments) > 18:
            self.stream_comments.pop(0)
        self.live_chat_fade = 5.5

    def _push_social_reaction(self, subject_name, is_core=True):
        mult = GAME_MODES[self.game_mode][2]
        gain_followers = int((random.randint(380, 950) if is_core else random.randint(140, 420)) * mult)
        gain_viewers = int((random.randint(220, 680) if is_core else random.randint(90, 260)) * mult)
        gain_likes = int(random.randint(600, 1800) * mult)
        self.followers += gain_followers
        self.live_viewers += gain_viewers
        self.stream_likes += gain_likes
        self.live_chat_fade = 5.0

        if self.level_index >= 8 and random.random() < 0.38:
            handle = random.choice(("@USER_100000", "@WALKURE_45", "@KOLA_12262M", "@ANTIBODY_04"))
            cmt = random.choice((
                f"Yes Kaelen. Show {subject_name} to all {self.followers:,} of us.",
                "We can see your room through the screen now.",
                f"{len(self.sector_photos)} seals opened. Keep clicking the shutter.",
                "Your book will be our scripture.",
            ))
        else:
            handle = random.choice(("@cryptid_jay", "@urbex_maya", "@skeptic_dan", "@vhs_ghost", "@history_buff", "@lens_flare"))
            cmt = random.choice((
                f"NO WAY! That {subject_name} is 100% real, not CGI!!",
                f"+{gain_followers} new followers from that shot alone! Clip it!",
                f"Did anyone else see the shadow move behind the {subject_name}?!",
                f"Waiting for the blog post breakdown on urbexproof.net!",
                f"Pre-ordered your book right after seeing that {subject_name}!",
            ))
        self.stream_comments.append((handle, cmt))
        if len(self.stream_comments) > 12:
            self.stream_comments.pop(0)

    def _publish_blog_post(self):
        count = len(self.unposted_blog_photos)
        if count == 0:
            self.sounds['deny'].play()
            return
        sname = SECTOR_NAMES[self.level_index]
        views_gain = count * random.randint(4200, 7800) + self.level_index * 2500
        likes_gain = int(views_gain * random.uniform(0.14, 0.24))
        foll_gain = count * random.randint(310, 640)
        self.blog_total_views += views_gain
        self.blog_total_likes += likes_gain
        self.blog_subscribers += int(foll_gain * 0.7)
        self.followers += foll_gain
        self.live_viewers += random.randint(250, 600)

        sample_subject = self.unposted_blog_photos[-1]['name']
        if self.level_index == 0:
            headline = f"PHOTO PROOF: Inside the Sealed 1945 '{sname}' ({count} Photos)"
            reader_cmt = "@dr_klein_hist: 'The German stencils and cipher rotors match classified 1945 archives!'"
        elif self.level_index < 6:
            prev = SECTOR_NAMES[self.level_index - 1]
            headline = f"Why Does {prev} Connect Directly to {sname}? ({count} Photos)"
            reader_cmt = f"@geology_prof: 'Wait—the rock strata in your {sample_subject} photo shouldn't exist there!'"
        else:
            headline = f"THE 100K PATTERN: {sample_subject} & The Subterranean Link ({count} Photos)"
            reader_cmt = "@SIGNAL_WATCHER: 'Every reader who opened this blog post heard the low hum in their room.'"

        self.blog_posts.append({
            'title': headline,
            'views': views_gain,
            'likes': likes_gain,
            'foll': foll_gain,
            'comment': reader_cmt,
            'sector': self.level_index + 1,
            'photo_count': count,
        })
        self.unposted_blog_photos.clear()
        self.sounds['ui_ok'].play()
        self.show_message(f"BLOG POSTED  +{views_gain:,} Views  +{foll_gain:,} Followers", 2.4)

    def _compile_book_chapter(self):
        count = len(self.uncompiled_book_photos)
        if count == 0:
            self.sounds['deny'].play()
            return
        ch_num = len(self.book_chapters) + 1
        sname = SECTOR_NAMES[self.level_index]
        words_added = count * random.randint(650, 1150) + 1400
        preorders_gain = count * random.randint(180, 420) + self.level_index * 150
        foll_gain = count * random.randint(240, 520)

        self.book_word_count += words_added
        self.book_preorders += preorders_gain
        self.followers += foll_gain

        if ch_num <= 3:
            summary = (f"Documents the descent into {sname} with {count} photographic plates. "
                       f"Establishes that items left behind in clusters were abandoned mid-ritual.")
            review = "Publisher Note: 'The headless skeletal sentry plates are chilling. Pre-orders spiked!'"
        elif ch_num <= 8:
            prev_sites = ", ".join(self.visited_sectors[-3:]) if self.visited_sectors else sname
            summary = (f"Cross-references {prev_sites}. Proves that all sealed sites share the same "
                       f"subterranean architecture and react specifically to camera flashes.")
            review = "Critic Review: 'Vance connects 1945 Bavaria, Soviet Kola, and Chernobyl into one map.'"
        else:
            summary = (f"Reveals the memetic trap: taking at least 10 unique photos materializes the Blue Key "
                       f"because 10 visual anchors are required to transmit the entity into 100,000 readers.")
            review = "Reader #100,000: 'I finished reading Chapter " + str(ch_num) + " and the Blue Key was on my desk.'"

        self.book_chapters.append({
            'num': ch_num,
            'title': f"Chapter {ch_num}: {sname}",
            'words': words_added,
            'preorders': preorders_gain,
            'summary': summary,
            'review': review,
        })
        self.uncompiled_book_photos.clear()
        self.sounds['log'].play()
        self.show_message(f"CHAPTER {ch_num} WRITTEN  +{words_added:,} Words  +{preorders_gain:,} Pre-Orders", 2.4)

    def _boost_livestream(self):
        if not self.all_captured_photos:
            self.sounds['deny'].play()
            return
        last = self.all_captured_photos[-1]['name']
        v_gain = random.randint(450, 1100)
        l_gain = random.randint(1200, 3200)
        f_gain = random.randint(280, 740)
        self.live_viewers += v_gain
        self.stream_likes += l_gain
        self.followers += f_gain
        self.live_chat_fade = 5.0
        self.stream_comments.append(("@MOD_BOT", f"PINNED SHOT: {last} (+{f_gain:,} followers)"))
        if len(self.stream_comments) > 12:
            self.stream_comments.pop(0)
        self.sounds['ui_ok'].play()
        self.show_message(f"SHOT SHARED ON STREAM  +{v_gain:,} Viewers  +{f_gain:,} Followers", 2.2)

    # ------------------------------------------------------------------ Camera & Photo System
    def _find_best_photo_candidate(self):
        if not self.level or not self.player:
            return None
        p = self.player
        grid = self.level.grid
        W = self.renderer.rw
        dirX, dirY = math.cos(p.angle), math.sin(p.angle)
        plane_len = math.tan(HALF_FOV)
        planeX, planeY = -dirY * plane_len, dirX * plane_len
        invDet = 1.0 / (planeX * dirY - dirX * planeY + 1e-9)

        candidates = []
        for e in self.level.enemies:
            pid = e.photo_id
            tdef = PHOTO_TARGET_DEFS[pid]
            dx, dy = e.x - p.x, e.y - p.y
            dist = math.hypot(dx, dy)
            if dist > CAMERA_MAX_RANGE:
                continue
            tY = invDet * (-planeY * dx + planeX * dy)
            tX = invDet * (dirY * dx - dirX * dy)
            if tY <= 0.2:
                continue
            aim = abs(tX / tY)
            if aim <= CAMERA_AIM_SPREAD:
                col = max(0, min(W - 1, int((W / 2) * (1 + tX / tY))))
                if tY < self.renderer.zbuffer[col] + 0.05 and has_line_of_sight(grid, p.x, p.y, e.x, e.y):
                    is_new = pid not in self.sector_photos
                    candidates.append((0 if is_new else 2, aim, dist, pid, tdef['name'], tdef['note'], e, is_new, True))

        for an in self.level.anomalies:
            pid = an.photo_id
            dx, dy = an.x - p.x, an.y - p.y
            dist = math.hypot(dx, dy)
            if dist > CAMERA_MAX_RANGE:
                continue
            tY = invDet * (-planeY * dx + planeX * dy)
            tX = invDet * (dirY * dx - dirX * dy)
            if tY <= 0.2:
                continue
            aim = abs(tX / tY)
            if aim <= CAMERA_AIM_SPREAD:
                col = max(0, min(W - 1, int((W / 2) * (1 + tX / tY))))
                if tY < self.renderer.zbuffer[col] + 0.05 and has_line_of_sight(grid, p.x, p.y, an.x, an.y):
                    if an.is_core:
                        is_new = pid not in self.sector_photos
                        prio = 0 if is_new else 2
                    else:
                        is_new = pid not in self.sector_blog_photos
                        prio = 1 if is_new else 3
                    candidates.append((prio, aim, dist, pid, an.name, an.note, an, is_new, an.is_core))

        for cr in self.level.critters:
            pid = cr.photo_id
            dx, dy = cr.x - p.x, cr.y - p.y
            dist = math.hypot(dx, dy)
            if dist > 6.0:
                continue
            tY = invDet * (-planeY * dx + planeX * dy)
            tX = invDet * (dirY * dx - dirX * dy)
            if tY <= 0.2:
                continue
            aim = abs(tX / tY)
            if aim <= CAMERA_AIM_SPREAD:
                col = max(0, min(W - 1, int((W / 2) * (1 + tX / tY))))
                if tY < self.renderer.zbuffer[col] + 0.05 and has_line_of_sight(grid, p.x, p.y, cr.x, cr.y):
                    is_new = pid not in self.sector_blog_photos
                    cname = "Swarm of Thousands of Beetles" if cr.kind == 'swarm' else "Pack of Red-Eyed Tunnel Rats"
                    cnote = ("Hundreds of insects boiling out of the floor cracks—perfect B-roll for my next blog post."
                             if cr.kind == 'swarm' else
                             "A pack of huge rats scurrying past the bones. Adding this shot to the blog and book.")
                    candidates.append((1 if is_new else 3, aim, dist, pid, cname, cnote, cr, is_new, False))

        if candidates:
            candidates.sort(key=lambda c: (c[0], c[1], c[2]))
            _, _, dist, pid, name, note, obj_ref, is_new, is_core = candidates[0]
            return (pid, name, note, obj_ref, is_new, dist, is_core)

        mid_col = W // 2
        wall_dist = self.renderer.zbuffer[mid_col]
        wtype = self.renderer.wall_hit_types[mid_col]
        if wall_dist <= 5.5 and wtype in HORROR_WALL_NAMES:
            wname, wnote = HORROR_WALL_NAMES[wtype]
            pid = 300 + wtype
            is_new = pid not in self.sector_blog_photos
            return (pid, wname, wnote, None, is_new, wall_dist, False)

        return None

    def _build_progressive_photo_commentary(self, name, base_note, is_core):
        if self.level_index == 0 or len(self.visited_sectors) <= 1:
            return base_note
        prev_site = self.visited_sectors[max(0, len(self.visited_sectors) - 2)]
        if self.level_index >= 8:
            prefix = f"Just like we discovered back in {prev_site}—this {name} is another optical anchor. "
        elif self.level_index >= 3:
            prefix = f"Compare this to our footage from {prev_site}: "
        else:
            prefix = f"Wait, this matches the markings from {prev_site}! "
        return prefix + base_note

    def _click_picture(self):
        p = self.player
        if p.camera_cooldown > 0:
            return
        p.camera_cooldown = 0.55
        self.camera_flash = 1.0
        self.sounds['shutter'].play()
        self._add_shake(1.8)

        rw, rh = self.renderer.rw, self.renderer.rh
        cw, ch = max(40, rw // 2), max(28, int(rh * 0.56))
        rx0 = (rw - cw) // 2
        ry0 = (rh - ch) // 2
        raw_crop = self.renderer.render_surf.subsurface((rx0, ry0, cw, ch)).copy()
        thumb = pygame.transform.scale(raw_crop, (180, 126))

        cand = self._find_best_photo_candidate()
        if cand is None:
            broll_id = 500 + len(self.sector_blog_photos)
            photo_record = {
                'id': broll_id,
                'name': f"Corridor Atmosphere ({SECTOR_NAMES[self.level_index][:16]})",
                'note': "Eerie wide shot of the corridor architecture for the blog & book.",
                'thumb': thumb,
                'sector': self.level_index + 1,
                'is_core': False,
            }
            if len(self.unposted_blog_photos) < 12:
                self.unposted_blog_photos.append(photo_record)
            self.photo_preview_surf = thumb
            self.photo_preview_label = "ATMOS B-ROLL SAVED"
            self.photo_preview_sub = "Added to Blog Roll"
            self.photo_preview_t = 2.2
            self.show_message("B-ROLL SAVED FOR BLOG", 1.6)
            return

        pid, name, note, obj_ref, is_new, dist, is_core = cand
        if obj_ref is not None:
            obj_ref.photographed = True

        if not is_new:
            self.photo_preview_surf = thumb
            self.photo_preview_label = f"DUPLICATE: {name.upper()}"
            self.photo_preview_sub = f"Proof Logged: {len(self.sector_photos)} (Need {PHOTOS_REQUIRED}+)"
            self.photo_preview_t = 2.4
            self.show_message(f"ALREADY PHOTOGRAPHED: {name}", 1.8)
            return

        spoken_note = self._build_progressive_photo_commentary(name, note, is_core)
        photo_record = {
            'id': pid,
            'name': name,
            'note': spoken_note,
            'thumb': thumb,
            'sector': self.level_index + 1,
            'is_core': is_core,
        }
        self.all_captured_photos.append(photo_record)
        self.unposted_blog_photos.append(photo_record)
        self.uncompiled_book_photos.append(photo_record)
        self._push_social_reaction(name, is_core=is_core)

        if not is_core:
            self.sector_blog_photos[pid] = photo_record
            self.photo_preview_surf = thumb
            self.photo_preview_label = f"BLOG SHOT: {name.upper()}"
            self.photo_preview_sub = "+Followers! Open Notebook (N)"
            self.photo_preview_t = 3.0
        if self.active_superchat is not None:
            self.sc_photos_taken += 1
            if self.active_superchat['id'] == 'close_pic' and cand[5] <= 2.8:
                self._complete_superchat()
            self._speak_and_write_note(f"BLOG EVIDENCE: {name}", spoken_note, dur=5.0)
            return

        self.sector_photos[pid] = photo_record
        count = len(self.sector_photos)

        self.photo_preview_surf = thumb
        self.photo_preview_label = f"UNIQUE PROOF #{count}: {name.upper()}"
        if count < PHOTOS_REQUIRED:
            self.photo_preview_sub = f"Unique Proof: {count} (At least {PHOTOS_REQUIRED} needed)"
        else:
            self.photo_preview_sub = f"Unique Proof: {count} (10+ Goal Met!)"
        self.photo_preview_t = 3.2

        self._speak_and_write_note(f"PROOF #{count}: {name}", spoken_note, dur=5.5)

        if count >= PHOTOS_REQUIRED and not self.level.blue_key_spawned:
            bx, by = self.level.blue_key_pos
            self.level.pickups.append(Pickup(bx, by, 'blue_key'))
            self.level.blue_key_spawned = True
            self.story_unlocked = True
            if self.level_index not in self.lore_found:
                self.lore_found.add(self.level_index)
                save_lore_progress(self.lore_found)

    # ------------------------------------------------------------------ messages
    def show_message(self, text, dur=2.5):
        dur = max(dur, 2.6 + 0.05 * len(text))
        for m in self.messages:
            if m[0] == text:
                m[1] = dur
                return
        self.messages.append([text, dur])
        if len(self.messages) > 4:
            self.messages.pop(0)

    # ------------------------------------------------------------------ horror audio
    def _play_at(self, name, x, y, boost=1.0):
        p = self.player
        dx, dy = x - p.x, y - p.y
        dist = math.hypot(dx, dy)
        pan = math.sin(math.atan2(dy, dx) - p.angle)
        vol = min(1.0, boost / (1.0 + 0.22 * dist)) * self.horror_volume
        ch = self.sounds[name].play()
        if ch:
            ch.set_volume(vol * (1.0 - 0.85 * max(0.0, pan)), vol * (1.0 + 0.85 * min(0.0, pan)))

    def _play_random_pan(self, name, vol=1.0):
        pan = random.uniform(-1.0, 1.0)
        v = vol * self.horror_volume
        ch = self.sounds[name].play()
        if ch:
            ch.set_volume(v * (1.0 - 0.8 * max(0.0, pan)), v * (1.0 + 0.8 * min(0.0, pan)))

    def _jumpscare(self):
        self.sounds['jumpscare'].play()
        self.scare_flash = 1.0
        self.scare_cd = 28.0
        self.ambient_event_t = max(self.ambient_event_t, 12.0)

    def _on_enemy_alert(self, e, dist):
        if dist < 4.5 and self.scare_cd <= 0 and random.random() < 0.7:
            self._jumpscare()
        else:
            self._play_at('roar', e.x, e.y, boost=1.6)

    def _play_ambient_event(self):
        roll = random.random()
        if roll < 0.10 and self.scare_cd <= 0:
            self._jumpscare()
        elif roll < 0.20:
            self.sounds['sting'].play()
            self.scare_flash = 0.5
        elif roll < 0.42:
            self._phantom_steps()
        else:
            name = random.choice(('whisper', 'scream_far', 'creak', 'thud', 'groan'))
            self._play_random_pan(name, vol=random.uniform(0.55, 1.0))

    def _phantom_steps(self):
        side = random.choice((-1.0, 1.0))
        for i in range(7):
            vol = (0.20 + 0.11 * i) * self.horror_volume
            left = vol * (1.0 - 0.8 * max(0.0, side))
            right = vol * (1.0 + 0.8 * min(0.0, side))
            self.timed_sounds.append([0.45 * (i + 1), 'step_%d' % (i % 2), left, right])

    def _update_audio(self):
        ch = self.ambient_ch
        in_world = self.state in (STATE_PLAYING, STATE_LEVEL_INTRO, STATE_PAUSED, STATE_READING)
        if in_world:
            if not ch.get_busy():
                ch.play(self.sounds['drone_%d' % (self.level_index % 2)], loops=-1)
                self._ambient_paused = False
            ch.set_volume((0.85 if self.state == STATE_PLAYING else 0.45) * self.horror_volume)
            if self.state == STATE_PAUSED:
                if not self._ambient_paused:
                    ch.pause()
                    self._ambient_paused = True
            elif self._ambient_paused:
                ch.unpause()
                self._ambient_paused = False
        else:
            if self._ambient_paused:
                ch.unpause()
                self._ambient_paused = False
            if ch.get_busy():
                ch.fadeout(500)

    def _update_horror(self, dt):
        p = self.player
        self.scare_cd = max(0.0, self.scare_cd - dt)
        self.scare_flash = max(0.0, self.scare_flash - dt * 1.2)
        self.live_chat_fade = max(0.0, self.live_chat_fade - dt)

        nearest = 99.0
        dread_target = 0.0
        for e in self.level.enemies:
            if e.state == 'dead':
                continue
            d = math.hypot(e.x - p.x, e.y - p.y)
            nearest = min(nearest, d if e.alerted else d / 0.7)
            near = max(0.0, 1.0 - d / 8.0)
            if near > 0:
                seen = d < 3.0 or has_line_of_sight(self.level.grid, p.x, p.y, e.x, e.y)
                dread_target = max(dread_target, near if seen else near * 0.4)
        self.dread += (dread_target - self.dread) * min(1.0, dt * 2.5)
        self.renderer.dread = self.dread
        prox = max(0.0, 1.0 - nearest / 9.0)
        hp_frac = p.hp / float(p.max_hp)
        low = max(0.0, (0.65 - hp_frac) / 0.65)
        danger = max(prox, low)
        self.heart_period = 1.15 - 0.5 * danger

        prev = self.heart_t
        self.heart_t += dt
        wrapped = False
        if self.heart_t >= self.heart_period:
            self.heart_t -= self.heart_period
            wrapped = True

        def crossed(mark):
            if wrapped:
                return mark > prev or mark <= self.heart_t
            return prev < mark <= self.heart_t

        if danger > 0.08:
            vol = (0.25 + 0.75 * danger) * self.horror_volume
            if crossed(0.05):
                self.heart_ch.play(self.sounds['heart_lub'])
                self.heart_ch.set_volume(vol)
            elif crossed(0.22):
                self.heart_ch.play(self.sounds['heart_dub'])
                self.heart_ch.set_volume(vol * 0.8)

        if p.spawn_grace <= 0:
            self.ambient_event_t -= dt
            if self.ambient_event_t <= 0:
                self.ambient_event_t = random.uniform(10.0, 24.0)
                self._play_ambient_event()

            self.ambient_talk_cd -= dt
            if self.ambient_talk_cd <= 0 and self.monologue_t <= 0:
                self.ambient_talk_cd = random.uniform(22.0, 34.0)
                tier = min(3, self.level_index // 4)
                line = random.choice(PROGRESSIVE_AMBIENT_LINES[tier])
                self._speak_and_write_note("FIELD OBSERVATION", line, dur=4.8)

            self.social_tick_t -= dt
            if self.social_tick_t <= 0:
                self.social_tick_t = random.uniform(4.5, 8.0)
                self.live_viewers = max(1200, self.live_viewers + random.randint(-35, 95))
                self.stream_likes += random.randint(15, 85)

    def _update_critters(self, dt):
        p = self.player
        grid = self.level.grid
        for cr in self.level.critters:
            cr.anim_t += dt * (8.0 if cr.kind == 'mouse' else 5.5)
            cr.turn_t -= dt
            dist_p = math.hypot(cr.x - p.x, cr.y - p.y)
            if cr.kind == 'mouse' and dist_p < 2.4:
                away_ang = math.atan2(cr.y - p.y, cr.x - p.x) + random.uniform(-0.35, 0.35)
                cr.vx = math.cos(away_ang) * 3.8
                cr.vy = math.sin(away_ang) * 3.8
            elif cr.turn_t <= 0:
                cr.turn_t = random.uniform(0.8, 2.5)
                ang = random.uniform(0, 2 * math.pi)
                spd = 2.4 if cr.kind == 'mouse' else 0.30
                cr.vx = math.cos(ang) * spd
                cr.vy = math.sin(ang) * spd

            nx = cr.x + cr.vx * dt
            ny = cr.y + cr.vy * dt
            if not is_wall(grid, nx + math.copysign(0.18, cr.vx), cr.y):
                cr.x = nx
            else:
                cr.vx = -cr.vx
            if not is_wall(grid, cr.x, ny + math.copysign(0.18, cr.vy)):
                cr.y = ny
            else:
                cr.vy = -cr.vy

            cr.squeak_cd -= dt
            if cr.squeak_cd <= 0:
                cr.squeak_cd = random.uniform(7.0, 18.0)
                if dist_p < 7.0:
                    self._play_at('skitter', cr.x, cr.y, boost=0.9)

    # ------------------------------------------------------------------ fog-of-war map
    def _reveal_map(self):
        p = self.player
        grid = self.level.grid
        explored = self.level.explored
        tx, ty = int(p.x), int(p.y)
        h, w = len(grid), len(grid[0])
        ring = []
        for dy in range(-5, 6):
            for dx in range(-5, 6):
                if dx * dx + dy * dy > 30:
                    continue
                x, y = tx + dx, ty + dy
                if 0 <= x < w and 0 <= y < h:
                    ring.append((x, y))
        open_tiles = (WALL_EMPTY, EXIT_TILE)
        for x, y in ring:
            if grid[y][x] in open_tiles and (x, y) not in explored:
                if has_line_of_sight(grid, p.x, p.y, x + 0.5, y + 0.5):
                    explored.add((x, y))
        for x, y in ring:
            if grid[y][x] not in open_tiles and (x, y) not in explored:
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if (nx, ny) in explored and 0 <= nx < w and 0 <= ny < h and grid[ny][nx] in open_tiles:
                        explored.add((x, y))
                        break

    # ------------------------------------------------------------------ update
    def update(self, dt):
        self.time += dt
        if self.fade > 0:
            self.fade = max(0.0, self.fade - dt * 3.0)
        if self.notice_t > 0:
            self.notice_t -= dt
        self._update_audio()

        if self.state == STATE_SPLASH:
            if not self.splash_sound_played:
                self.splash_sound_played = True
                self.sounds['splash'].play()
            self.splash_t += dt
            if self.splash_t >= 3.8:
                self.state = STATE_MENU
            return

        if self.state == STATE_STORY_INTRO:
            self.story_intro_t += dt
            target_chars = int(self.story_intro_t * 36.0)
            total_len = len(TYPING_HORROR_INTRO_TEXT)
            if target_chars > self.story_intro_chars and self.story_intro_chars < total_len:
                prev_c = self.story_intro_chars
                self.story_intro_chars = min(total_len, target_chars)
                ch = TYPING_HORROR_INTRO_TEXT[self.story_intro_chars - 1]
                if ch not in (' ', '\n') and (self.story_intro_chars // 2 != prev_c // 2):
                    self.sounds['type_key'].play()
            return

        if self.state == STATE_LEVEL_INTRO:
            self.level_intro_t += dt
            return
        if self.state == STATE_READING:
            self.reading_t += dt
            return

        if self.state != STATE_PLAYING or self.show_controls_help:
            return

        self.sector_play_t += dt
        for m in self.messages:
            m[1] -= dt
        self.messages = [m for m in self.messages if m[1] > 0]

        if self.monologue_t > 0:
            self.monologue_t = max(0.0, self.monologue_t - dt)
        if self.camera_flash > 0:
            self.camera_flash = max(0.0, self.camera_flash - dt * 3.0)
        if self.photo_preview_t > 0:
            self.photo_preview_t = max(0.0, self.photo_preview_t - dt)

        if not self._is_nv_allowed():
            self.night_vision = False
        if self.night_vision:
            self.nv_battery = max(0.0, self.nv_battery - dt * 0.005)
            if self.nv_battery <= 0.0:
                self.nv_battery = 0.0
                self.night_vision = False
                self.sounds['deny'].play()
                self.show_message("CAMCORDER IR BATTERY DEAD FOR THIS SECTOR", 2.2)
        self.renderer.nv_active = self.night_vision
        self.renderer.brightness = self.brightness

        self.ambient_chat_t -= dt
        if self.ambient_chat_t <= 0:
            self.ambient_chat_t = random.uniform(8.5, 14.5)
            self._push_ambient_chat()

        if self.active_superchat is None and self.superchat_queue:
            if self.sector_play_t >= self.superchat_queue[0]:
                self.superchat_queue.pop(0)
                self._spawn_superchat_challenge()
        elif self.active_superchat is not None:
            sc = self.active_superchat
            sc['left'] -= dt
            cid = sc['id']
            if cid == 'no_ir':
                if self.night_vision:
                    self._fail_superchat("TURNED ON IR")
                elif sc['left'] <= 0:
                    self._complete_superchat()
            elif cid == 'no_shoot':
                if self.sc_fired:
                    self._fail_superchat("FIRED WEAPON")
                elif sc['left'] <= 0:
                    self._complete_superchat()
            elif cid == 'kills_2':
                if self.sc_kills >= 2:
                    self._complete_superchat()
                elif sc['left'] <= 0:
                    self._fail_superchat("NEEDED 2 KILLS")
            elif cid == 'photos_2':
                if self.sc_photos_taken >= 2:
                    self._complete_superchat()
                elif sc['left'] <= 0:
                    self._fail_superchat("NEEDED 2 PHOTOS")
            elif cid == 'stand_still':
                near_threat = any(
                    e.alive and math.hypot(e.x - self.player.x, e.y - self.player.y) < 7.5
                    for e in self.level.enemies
                )
                moving = (abs(self.touch_move_vec[0]) > 0.1 or abs(self.touch_move_vec[1]) > 0.1 or
                          pygame.key.get_pressed()[K_w] or pygame.key.get_pressed()[K_s] or
                          pygame.key.get_pressed()[K_a] or pygame.key.get_pressed()[K_d])
                if near_threat and not moving:
                    self.sc_still_t += dt
                else:
                    self.sc_still_t = max(0.0, self.sc_still_t - dt * 0.5)
                if self.sc_still_t >= 4.0:
                    self._complete_superchat()
                elif sc['left'] <= 0:
                    self._fail_superchat("KEPT MOVING")
            elif sc['left'] <= 0:
                self._fail_superchat("TIME UP")

        p = self.player
        grid = self.level.grid
        keys = pygame.key.get_pressed()

        self.renderer.update_flicker(dt)

        if p.spawn_grace > 0:
            p.spawn_grace = max(0.0, p.spawn_grace - dt)
        p.camera_cooldown = max(0.0, p.camera_cooldown - dt)

        mdx, _ = pygame.mouse.get_rel()
        if not self.touch_controls:
            p.angle += mdx * self.mouse_sens
        elif pygame.mouse.get_pressed()[0]:
            mpos = self._to_canvas(pygame.mouse.get_pos())
            if mpos[0] > DISPLAY_W * 0.38 and mpos[0] < DISPLAY_W * 0.78:
                p.angle += mdx * self.mouse_sens * 1.4

        if keys[K_LEFT]:
            p.angle -= ROT_SPEED * dt
        if keys[K_RIGHT]:
            p.angle += ROT_SPEED * dt

        wdef_now = p.weapon
        sprinting = bool(keys[K_LSHIFT] or keys[K_RSHIFT])
        speed = MOVE_SPEED * (SPRINT_MULT if sprinting else 1.0)
        if p.charge > 0:
            speed *= wdef_now.get('charge_move', 1.0)
        dirX, dirY = math.cos(p.angle), math.sin(p.angle)
        strafeX, strafeY = -dirY, dirX
        mvx = mvy = 0.0
        wants_move = False
        if keys[K_w]:
            mvx += dirX; mvy += dirY; wants_move = True
        if keys[K_s]:
            mvx -= dirX; mvy -= dirY; wants_move = True
        if keys[K_d]:
            mvx += strafeX; mvy += strafeY; wants_move = True
        if keys[K_a]:
            mvx -= strafeX; mvy -= strafeY; wants_move = True
        if self.touch_controls and (abs(self.touch_move_vec[0]) > 0.08 or abs(self.touch_move_vec[1]) > 0.08):
            tx_m, ty_m = self.touch_move_vec
            mvx += dirX * ty_m + strafeX * tx_m
            mvy += dirY * ty_m + strafeY * tx_m
            wants_move = True

        if wants_move:
            norm = math.hypot(mvx, mvy) or 1.0
            tvx, tvy = mvx / norm * speed, mvy / norm * speed
        else:
            tvx = tvy = 0.0
        k = min(1.0, dt * (14.0 if wants_move else 11.0))
        p.vx += (tvx - p.vx) * k
        p.vy += (tvy - p.vy) * k
        cur_speed = math.hypot(p.vx, p.vy)
        if cur_speed < 0.05:
            p.vx = p.vy = 0.0
            cur_speed = 0.0
        else:
            p.try_move(p.vx * dt, p.vy * dt, grid)
        moving = cur_speed > 0.35
        if moving:
            if self.head_bob:
                self.bob_t += dt * (10.0 if sprinting else 7.0) * min(1.4, cur_speed / MOVE_SPEED)
            self.step_dist += cur_speed * dt
            if self.step_dist >= 1.5:
                self.step_dist -= 1.5
                self.step_i ^= 1
                ch = self.sounds['step_%d' % self.step_i].play()
                if ch:
                    ch.set_volume(0.55 + (0.3 if sprinting else 0.0))
        p.moving = moving

        tile = (int(p.x), int(p.y))
        if tile != self._last_tile:
            self._last_tile = tile
            self._reveal_map()

        for key_const, widx in ((K_1, 0), (K_2, 1), (K_3, 2), (K_4, 3)):
            if keys[key_const]:
                self._switch_weapon(widx)
                break

        px, py = int(p.x), int(p.y)
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                cx, cy = px + ox, py + oy
                if 0 <= cy < len(grid) and 0 <= cx < len(grid[0]):
                    if grid[cy][cx] == WALL_DOOR and (cx, cy) not in self.level.opened_doors:
                        if 'key' in p.keys and math.hypot(cx + 0.5 - p.x, cy + 0.5 - p.y) < 1.6:
                            self.level.opened_doors.add((cx, cy))
                            grid[cy][cx] = WALL_EMPTY
                            self.sounds['door'].play()
                            self._play_random_pan('creak', 0.5)
                            self.show_message("VAULT DOOR UNLOCKED", 1.5)

        for pick in self.level.pickups:
            if not pick.alive:
                continue
            if math.hypot(pick.x - p.x, pick.y - p.y) < 0.5:
                if pick.kind == 'ammo':
                    if not any(p.weapons_owned):
                        self.show_message("AMMO - but you have nothing to load it into", 2.0)
                        continue
                    if not any(p.weapons_owned[i] and p.reserve[i] < wd['max_reserve']
                               for i, wd in enumerate(WEAPON_DEFS)):
                        self.show_message("AMMO FULL - leave it for later", 1.8)
                        continue
                pick.alive = False
                self.sounds['pickup'].play()
                if pick.kind == 'health':
                    p.heal(40)
                    self.show_message("+40 HEALTH", 1.2)
                elif pick.kind == 'ammo':
                    wdef = p.weapon
                    mine = others = 0
                    for i, wd in enumerate(WEAPON_DEFS):
                        if not p.weapons_owned[i]:
                            continue
                        want = wd['pickup_ammo'] if i == p.weapon_index else max(1, wd['pickup_ammo'] // 2)
                        gain = min(want, wd['max_reserve'] - p.reserve[i])
                        p.reserve[i] += gain
                        if i == p.weapon_index:
                            mine = gain
                        else:
                            others += gain
                    if mine:
                        msg = f"+{mine} {wdef['name']} ROUND{'' if mine == 1 else 'S'}"
                        if others:
                            msg += "  (and a few for your other guns)"
                    else:
                        msg = "+ROUNDS FOR YOUR OTHER GUNS"
                    self.show_message(msg, 1.4)
                elif pick.kind == 'key':
                    p.keys.add('key')
                    self.sounds['sting'].play()
                    self.show_message("VAULT KEYCARD ACQUIRED", 1.8)
                elif pick.kind == 'blue_key':
                    p.keys.add('blue_key')
                    self.sounds['log'].play()
                    self.show_message("BLUE EXIT KEY ACQUIRED — EXIT SEAL UNLOCKED", 2.8)
                    self._speak_and_write_note(
                        "BLUE EXIT KEY FOUND",
                        "Wait—this glowing Blue Key wasn't on the floor earlier! It materialized silently after my 10th unique photo. This unlocks the exit seal!",
                        dur=5.8,
                    )
                elif pick.kind == 'log':
                    self._open_log(self.level_index)
                elif pick.kind in WEAPON_BY_ID:
                    self._pick_up_weapon(pick.kind)

        wdef = p.weapon
        p.shoot_cooldown = max(0.0, p.shoot_cooldown - dt)
        if p.reloading:
            p.reload_timer -= dt
            if p.reload_timer <= 0:
                need = wdef['mag_size'] - p.ammo[p.weapon_index]
                take = min(need, p.reserve[p.weapon_index])
                p.ammo[p.weapon_index] += take
                p.reserve[p.weapon_index] -= take
                p.reloading = False

        if p.armed:
            self._update_firing(dt, keys)
        self._update_projectiles(dt)
        self._update_effects(dt)
        self._update_feel(dt, mdx)

        self.current_photo_candidate = self._find_best_photo_candidate()

        # Select which of the 8 weapon+hand animation frames to display!
        if self.vm_drop > 0.15:
            # Weapon switching: show hand steadying pose (frame 7)
            self.gun_frame = 7
        elif p.reloading:
            # Multi-stage hand reload animation (frames 4 -> 5 -> 6)
            total_rt = max(0.01, wdef['reload_time'])
            frac = 1.0 - (p.reload_timer / total_rt)
            if frac < 0.34:
                self.gun_frame = 4   # Stage 1: Hand ejects old magazine / opens breech
            elif frac < 0.72:
                self.gun_frame = 5   # Stage 2: Left hand inserts fresh magazine / shells / cell
            else:
                self.gun_frame = 6   # Stage 3: Left hand racks slide / pump / bolt
        elif self.gun_timer > 0:
            self.gun_timer -= dt
            # Smooth 3-stage firing & shell-ejection sequence (1 -> 2 -> 3)
            if self.gun_timer > 0.18:
                self.gun_frame = 1
            elif self.gun_timer > 0.09:
                self.gun_frame = 2
            else:
                self.gun_frame = 3
        else:
            self.gun_frame = 0

        p.damage_flash = max(0.0, p.damage_flash - dt * 2.5)
        p.pickup_flash = max(0.0, p.pickup_flash - dt * 2.5)

        for e in self.level.enemies:
            self._update_enemy(e, dt)

        self._update_critters(dt)
        self._update_horror(dt)

        ex, ey = self.level.exit_pos
        if math.hypot(ex - p.x, ey - p.y) < 0.65:
            if 'blue_key' in p.keys:
                self._advance_level()
            else:
                if len(self.sector_photos) < PHOTOS_REQUIRED:
                    self.show_message(
                        f"EXIT LOCKED (BLUE SEAL) — Take at least {PHOTOS_REQUIRED} unique proof pics ({len(self.sector_photos)} taken) & find the Blue Key",
                        2.2,
                    )
                else:
                    self.show_message(
                        "EXIT LOCKED — You have 10+ unique pics! Search the sector for the Blue Exit Key",
                        2.2,
                    )

        if p.hp <= 0:
            self.state = STATE_GAMEOVER
            self.sounds['dead'].play()
            pygame.event.set_grab(False)
            pygame.mouse.set_visible(True)

    def _pick_up_weapon(self, weapon_id):
        p = self.player
        widx = weapon_index(weapon_id)
        wdef = WEAPON_DEFS[widx]
        if p.weapons_owned[widx]:
            p.reserve[widx] = min(wdef['max_reserve'], p.reserve[widx] + wdef['pickup_ammo'])
            self.show_message(f"+{wdef['name']} AMMO", 1.2)
            return
        was_armed = p.armed
        p.weapons_owned[widx] = True
        p.ammo[widx] = wdef['mag_size']
        p.reserve[widx] = wdef['start_reserve']
        p.weapon_index = widx
        p.reloading = False
        p.charge = 0.0
        p.shoot_cooldown = 0.45
        if not was_armed:
            self.vm_index = widx
            self.vm_drop = 1.0
        self.sounds['switch'].play()
        self.sounds['sting'].play()
        self.show_message(f"{wdef['name']} FOUND", 2.5)
        if weapon_id not in self.weapons_found:
            self.weapons_found.add(weapon_id)
            if not self.unlock_all:
                save_progress(self.highest_unlocked, self.weapons_found)

    def _open_log(self, level_index):
        first_time = level_index not in self.lore_found
        if first_time:
            self.lore_found.add(level_index)
            save_lore_progress(self.lore_found)
        self.reading_text = LORE_LOGS[level_index]
        self.reading_index = level_index
        self.reading_is_new = first_time
        self.reading_t = 0.0
        self.state = STATE_READING
        self.show_big_map = False
        self.sounds['log'].play()
        self._play_random_pan('whisper', 0.6)

    def _close_reading(self):
        if self.state == STATE_READING and self.reading_t >= 0.6:
            self.state = STATE_PLAYING
            pygame.mouse.get_rel()

    def _advance_level(self):
        self.level_index += 1
        self.highest_unlocked = min(len(LEVELS) - 1, max(self.highest_unlocked, self.level_index))
        if not self.unlock_all:
            save_progress(self.highest_unlocked, self.weapons_found)
        if self.level_index >= len(LEVELS):
            self.state = STATE_WIN
            self.sounds['win'].play()
            pygame.event.set_grab(False)
            pygame.mouse.set_visible(True)
        else:
            carried_hp = min(self.player.max_hp, self.player.hp + SECTOR_CLEAR_HEAL)
            carried_weapons_owned = self.player.weapons_owned
            carried_ammo = self.player.ammo
            carried_reserve = self.player.reserve
            carried_weapon_index = self.player.weapon_index
            carried_kills = self.player.kills
            self.load_level(self.level_index)
            self.player.hp = carried_hp
            self.player.weapons_owned = carried_weapons_owned
            self.player.ammo = carried_ammo
            self.player.reserve = carried_reserve
            self.player.weapon_index = carried_weapon_index
            self.player.kills = carried_kills
            self._snapshot_loadout()
            self._enter_intro()
            self.show_message(f"SECTOR CLEARED  +{SECTOR_CLEAR_HEAL} HP", 3.0)

    def _update_enemy(self, e, dt):
        if e.state == 'dead':
            e.dead_timer += dt
            return
        p = self.player
        e.hit_flash = max(0.0, e.hit_flash - dt)
        e.slow_t = max(0.0, e.slow_t - dt)
        if e.kx or e.ky:
            gridk = self.level.grid
            nx, ny = e.x + e.kx * dt, e.y + e.ky * dt
            if not is_wall(gridk, nx + math.copysign(0.25, e.kx), e.y):
                e.x = nx
            if not is_wall(gridk, e.x, ny + math.copysign(0.25, e.ky)):
                e.y = ny
            damp = math.exp(-dt * 9.0)
            e.kx *= damp
            e.ky *= damp
            if abs(e.kx) + abs(e.ky) < 0.05:
                e.kx = e.ky = 0.0
        if p.spawn_grace > 0:
            return
        grid = self.level.grid
        dist = math.hypot(p.x - e.x, p.y - e.y)
        e.anim_t += dt
        move_speed = e.speed * (WEAPON_BY_ID['plasma']['slow'][1] if e.slow_t > 0 else 1.0)

        if e.alerted and not e.ranged and dist > 2.2:
            ang = math.atan2(e.y - p.y, e.x - p.x)
            off = abs((ang - p.angle + math.pi) % (2 * math.pi) - math.pi)
            if off < STALK_FOV and has_line_of_sight(grid, p.x, p.y, e.x, e.y):
                move_speed *= STALK_WATCHED
            else:
                move_speed *= 1.15 if e.kind == 'charger' else STALK_UNWATCHED
                e.step_cd -= dt
                if e.step_cd <= 0 and dist < 9:
                    e.step_cd = 0.38
                    self._play_at('step_%d' % random.randint(0, 1), e.x, e.y, boost=2.6)

        detect_range = 6.5 if e.ranged else 6.0
        if not e.alerted:
            if dist < detect_range and has_line_of_sight(grid, e.x, e.y, p.x, p.y):
                e.alerted = True
                e.state = 'chase'
                self._on_enemy_alert(e, dist)
            else:
                e.growl_cd -= dt
                if e.growl_cd <= 0:
                    e.growl_cd = random.uniform(5.0, 10.0)
                    if dist < 13:
                        self._play_at('groan', e.x, e.y, boost=2.2)
        else:
            e.growl_cd -= dt
            if e.growl_cd <= 0:
                e.growl_cd = random.uniform(3, 7)
                if dist < 10:
                    self._play_at('enemy_growl', e.x, e.y)

        if e.state in ('chase', 'attack'):
            if e.ranged:
                if dist > e.preferred_range + 1.5:
                    move_enemy_toward(grid, e, p.x, p.y, move_speed * dt)
                elif dist < e.preferred_range - 1.5 and dist > 0.3:
                    move_enemy_toward(grid, e, e.x + (e.x - p.x), e.y + (e.y - p.y), move_speed * dt)
                e.attack_cd -= dt
                if e.attack_cd <= 0 and has_line_of_sight(grid, e.x, e.y, p.x, p.y):
                    e.attack_cd = 2.2
                    e.fire_flash = 0.2
                    self._play_at('enemy_shoot', e.x, e.y)
                    hit_chance = max(0.15, min(0.60, 0.9 - dist / 10.0))
                    if random.random() <= hit_chance:
                        self._hurt_player(e.damage, e.x, e.y)
                        self.sounds['hurt'].play()
            else:
                if dist > 1.1:
                    e.state = 'chase'
                    move_enemy_toward(grid, e, p.x, p.y, move_speed * dt)
                else:
                    e.state = 'attack'
                    e.attack_cd -= dt
                    if e.attack_cd <= 0:
                        e.attack_cd = 1.4
                        self._hurt_player(e.damage, e.x, e.y)
                        self.sounds['hurt'].play()

        if e.fire_flash > 0:
            e.fire_flash = max(0.0, e.fire_flash - dt)

    # ------------------------------------------------------------------ feel helpers
    def _add_shake(self, amount):
        amount *= self.shake_scale
        if amount <= 0:
            return
        self.shake = min(18.0, max(self.shake, amount) + amount * 0.25)

    def _switch_weapon(self, idx):
        p = self.player
        if p.switch_weapon(idx):
            self.timed_sounds = [t for t in self.timed_sounds if t[1] != 'pump']
            self.sounds['rail_charge'].stop()
            self.sounds['switch'].play()

    def _hurt_player(self, amount, src_x, src_y):
        p = self.player
        before = p.hp
        p.take_damage(amount)
        if p.hp < before:
            self._add_shake(min(8.0, 2.5 + amount * 0.3))
            ang = math.atan2(src_y - p.y, src_x - p.x)
            if len(self.dmg_marks) < 6:
                self.dmg_marks.append([ang, 1.3])

    def _damage_enemy(self, e, dmg, src_x, src_y, knock=0.0, slow=None, flash=0.12):
        dmg = max(1, int(round(dmg)))
        killed = e.take_damage(dmg)
        e.hit_flash = flash
        if slow and e.state != 'dead':
            e.slow_t = max(e.slow_t, slow[0])
        if knock > 0:
            ang = math.atan2(e.y - src_y, e.x - src_x)
            e.kx += math.cos(ang) * knock * 6.0
            e.ky += math.sin(ang) * knock * 6.0
            if not killed:
                e.attack_cd = max(e.attack_cd, 0.4)
        if killed:
            self.player.kills += 1
            self.hit_kill = True
            self.sc_kills += 1
            self.hit_t = 0.32
            self.sounds['enemy_die'].play()
            self.show_message("ENTITY BANISHED", 1.0)
        else:
            if self.hit_t <= 0:
                self.hit_kill = False
            self.hit_t = max(self.hit_t, 0.15)
        return killed

    def _add_effect(self, x, y, kind, dur):
        if len(self.effects) >= 80:
            self.effects.pop(0)
        self.effects.append(Effect(x, y, kind, dur))

    # ------------------------------------------------------------------ firing
    def _start_reload(self, wdef):
        p = self.player
        p.reloading = True
        p.reload_timer = wdef['reload_time']
        p.charge = 0.0
        self.sounds['rail_charge'].stop()
        self.sounds['reload'].play()

    def _update_firing(self, dt, keys):
        p = self.player
        wdef = p.weapon
        wi = p.weapon_index
        mouse_fire = bool(pygame.mouse.get_pressed()[0]) and not self.touch_controls
        fire_held = bool(mouse_fire or keys[K_SPACE] or self.touch_fire_held)

        if keys[K_r] and not p.reloading and p.ammo[wi] < wdef['mag_size'] and p.reserve[wi] > 0:
            self._start_reload(wdef)

        if 'charge' in wdef:
            self._update_railgun(wdef, fire_held, dt)
        elif fire_held and p.shoot_cooldown <= 0 and not p.reloading:
            if p.ammo[wi] > 0:
                self._fire_weapon(wdef)
            elif p.reserve[wi] > 0:
                self._start_reload(wdef)
            else:
                p.shoot_cooldown = 0.35
                self.sounds['empty'].play()

    def _update_railgun(self, wdef, fire_held, dt):
        p = self.player
        wi = p.weapon_index
        if p.reloading:
            p.charge = 0.0
            return
        if fire_held and p.shoot_cooldown <= 0:
            if p.ammo[wi] <= 0:
                if p.reserve[wi] > 0:
                    self._start_reload(wdef)
                else:
                    p.shoot_cooldown = 0.35
                    self.sounds['empty'].play()
                return
            if p.charge <= 0:
                self.sounds['rail_charge'].play()
            p.charge += dt
            if p.charge >= wdef['charge']:
                p.charge = 0.0
                self.sounds['rail_charge'].stop()
                self._fire_weapon(wdef)
        elif p.charge > 0:
            p.charge = 0.0
            self.sounds['rail_charge'].stop()

    def _fire_weapon(self, wdef):
        self.sc_fired = True
        p = self.player
        wi = p.weapon_index
        p.ammo[wi] -= 1
        p.shoot_cooldown = wdef['cooldown']
        self.gun_frame = 1
        self.gun_timer = 0.28
        self.sounds[wdef['sfx']].play()
        mode = wdef['mode']
        if mode == 'hitscan':
            self._hitscan(wdef)
        elif mode == 'projectile':
            self._spawn_projectile(wdef)
        else:
            self._fire_beam(wdef)
        self.recoil = max(self.recoil, wdef['recoil'])
        self._add_shake(wdef['shake'])
        self.muzzle_light = max(self.muzzle_light, wdef['flash_amt'])
        self.muzzle_col = wdef['flash']
        if 'pump_delay' in wdef:
            self.timed_sounds.append([wdef['pump_delay'], 'pump'])

    def _aim_targets(self, spread):
        p = self.player
        grid = self.level.grid
        W = self.renderer.rw
        dirX, dirY = math.cos(p.angle), math.sin(p.angle)
        plane_len = math.tan(HALF_FOV)
        planeX, planeY = -dirY * plane_len, dirX * plane_len
        invDet = 1.0 / (planeX * dirY - dirX * planeY + 1e-9)
        out = []
        for e in self.level.enemies:
            if e.state == 'dead':
                continue
            dx, dy = e.x - p.x, e.y - p.y
            tY = invDet * (-planeY * dx + planeX * dy)
            tX = invDet * (dirY * dx - dirX * dy)
            if tY <= 0.1:
                continue
            aim = abs(tX / tY)
            if aim < spread:
                col = int((W / 2) * (1 + tX / tY))
                col = max(0, min(W - 1, col))
                if tY <= self.renderer.zbuffer[col] + 0.15 and has_line_of_sight(grid, p.x, p.y, e.x, e.y):
                    out.append((tY, aim, e))
        out.sort(key=lambda a: a[0])
        return out

    def _hitscan(self, wdef):
        p = self.player
        targets = self._aim_targets(wdef['spread'])
        if not targets:
            return
        depth, aim, e = targets[0]
        hit_chance = max(0.2, 1.0 - aim / wdef['spread'])
        hits = 0
        total = 0.0
        for _ in range(wdef['pellets']):
            if random.random() <= hit_chance:
                dmg = random.randint(wdef['dmg_min'], wdef['dmg_max'])
                falloff = wdef.get('falloff')
                if falloff:
                    full_range, far_range, min_scale = falloff
                    if depth > full_range:
                        t = min(1.0, (depth - full_range) / (far_range - full_range))
                        dmg = max(1, int(round(dmg * (1.0 - t * (1.0 - min_scale)))))
                total += dmg
                hits += 1
        if not hits:
            return
        knock = 0.0
        if 'knockback' in wdef:
            rangef = 1.0 if depth <= 3.5 else max(0.25, 1.0 - (depth - 3.5) / 6.0)
            knock = wdef['knockback'] * (hits / float(wdef['pellets'])) * rangef
        self._damage_enemy(e, total, p.x, p.y, knock=knock)
        self.sounds['hit'].play()

    def _fire_beam(self, wdef):
        p = self.player
        scale = 1.0
        hit_any = False
        for depth, aim, e in self._aim_targets(wdef['spread']):
            chance = max(0.2, 1.0 - aim / wdef['spread'])
            if random.random() <= chance:
                dmg = random.randint(wdef['dmg_min'], wdef['dmg_max']) * scale
                self._damage_enemy(e, dmg, p.x, p.y, flash=0.22)
                scale *= wdef['pierce_falloff']
                hit_any = True
        self.beam_t = 0.40
        if hit_any:
            self.sounds['hit'].play()

    def _spawn_projectile(self, wdef):
        p = self.player
        dx, dy = math.cos(p.angle), math.sin(p.angle)
        sx, sy = p.x + dx * 0.35, p.y + dy * 0.35
        pr = Projectile(sx, sy, dx, dy, wdef)
        if is_wall(self.level.grid, sx, sy):
            self._projectile_impact(pr, wdef, p.x, p.y, None)
        else:
            self.projectiles.append(pr)

    def _update_projectiles(self, dt):
        grid = self.level.grid
        keep = []
        for pr in self.projectiles:
            wdef = WEAPON_BY_ID[pr.wid]
            pr.life -= dt
            dist = pr.speed * dt
            steps = max(1, int(dist / 0.2) + 1)
            sd = dist / steps
            impact = None
            for _ in range(steps):
                nx, ny = pr.x + pr.dx * sd, pr.y + pr.dy * sd
                if is_wall(grid, nx, ny):
                    impact = (pr.x, pr.y, None)
                    break
                pr.x, pr.y = nx, ny
                for e in self.level.enemies:
                    if e.state != 'dead' and math.hypot(e.x - pr.x, e.y - pr.y) < ENEMY_HIT_RADIUS:
                        impact = (pr.x, pr.y, e)
                        break
                if impact:
                    break
            if impact is None and pr.life <= 0:
                impact = (pr.x, pr.y, None)
            if impact:
                self._projectile_impact(pr, wdef, impact[0], impact[1], impact[2])
                continue
            pr.trail_t -= dt
            if pr.trail_t <= 0:
                pr.trail_t = 0.04
                self._add_effect(pr.x, pr.y, 'plasma_trail', 0.25)
            keep.append(pr)
        self.projectiles = keep

    def _projectile_impact(self, pr, wdef, x, y, target):
        p = self.player
        grid = self.level.grid
        dmg = random.randint(wdef['dmg_min'], wdef['dmg_max'])
        slow = wdef['slow']
        hit_any = False
        if target is not None:
            self._damage_enemy(target, dmg, x - pr.dx, y - pr.dy, slow=slow, flash=0.18)
            hit_any = True
        radius = wdef['blast_radius']
        for e in self.level.enemies:
            if e is target or e.state == 'dead':
                continue
            d = math.hypot(e.x - x, e.y - y)
            if d <= radius and has_line_of_sight(grid, x, y, e.x, e.y):
                fall = 1.0 - 0.5 * d / radius
                self._damage_enemy(e, dmg * wdef['blast_scale'] * fall, x, y, slow=slow, flash=0.15)
                hit_any = True
        self._add_effect(x, y, 'plasma_hit', 0.35)
        self._play_at('plasma_hit', x, y, boost=2.2)
        if hit_any:
            self.sounds['hit'].play()
        self._add_shake(max(0.0, 3.0 - math.hypot(p.x - x, p.y - y) * 0.4))

    def _update_effects(self, dt):
        for fx in self.effects:
            fx.t += dt
        self.effects = [fx for fx in self.effects if fx.t < fx.dur]

    def _update_feel(self, dt, mdx):
        p = self.player
        self.shake *= math.exp(-dt * 10.0)
        if self.shake < 0.15:
            self.shake = 0.0
        self.recoil *= math.exp(-dt * 11.0)
        if self.recoil < 0.01:
            self.recoil = 0.0
        self.muzzle_light = max(0.0, self.muzzle_light - dt * 5.0)
        self.hit_t = max(0.0, self.hit_t - dt)
        self.beam_t = max(0.0, self.beam_t - dt)
        self.sway_x = max(-60.0, min(60.0, self.sway_x - mdx * 0.9)) * math.exp(-dt * 7.0)
        for m in self.dmg_marks:
            m[1] -= dt
        self.dmg_marks = [m for m in self.dmg_marks if m[1] > 0]
        if self.vm_index != p.weapon_index:
            self.vm_drop = min(1.0, self.vm_drop + dt / 0.11)
            if self.vm_drop >= 1.0:
                self.vm_index = p.weapon_index
        elif self.vm_drop > 0:
            self.vm_drop = max(0.0, self.vm_drop - dt / 0.14)
        for ts in self.timed_sounds:
            ts[0] -= dt
            if ts[0] <= 0:
                ch = self.sounds[ts[1]].play()
                if ch and len(ts) >= 4:
                    ch.set_volume(ts[2], ts[3])
        self.timed_sounds = [ts for ts in self.timed_sounds if ts[0] > 0]
        speed_f = min(1.0, math.hypot(p.vx, p.vy) / MOVE_SPEED)
        target_gap = 4.0 + 6.0 * speed_f + 11.0 * self.recoil + (7.0 if p.weapon['id'] == 'shotgun' else 0.0)
        self.cross_gap += (target_gap - self.cross_gap) * min(1.0, dt * 16.0)
        self.on_target = bool(p.armed and self._aim_targets(0.07))
        if p.hp < self.hp_last:
            self.ghost_delay = 0.45
        self.hp_last = p.hp
        self.hp_shown += (p.hp - self.hp_shown) * min(1.0, dt * 9.0)
        if self.ghost_delay > 0:
            self.ghost_delay -= dt
        else:
            self.hp_ghost = max(float(p.hp), self.hp_ghost - 45.0 * dt)
        self.hp_ghost = max(self.hp_ghost, float(p.hp))

    def _sync_feel(self):
        p = self.player
        self.vm_index = p.weapon_index
        self.vm_drop = 0.0
        self.hp_shown = self.hp_ghost = self.hp_last = float(p.hp)
        self.ghost_delay = 0.0

    # ------------------------------------------------------------------ drawing
    def draw(self):
        if self.state == STATE_SPLASH:
            self._draw_splash()
        elif self.state == STATE_MENU:
            self._draw_menu()
        elif self.state == STATE_STORY_INTRO:
            self._draw_story_intro()
        elif self.state == STATE_LEVEL_SELECT:
            self._draw_level_select()
        elif self.state == STATE_SETTINGS:
            self._draw_settings()
        elif self.state == STATE_ARCHIVE:
            self._draw_archive()
        elif self.state in (STATE_PLAYING, STATE_PAUSED, STATE_LEVEL_INTRO, STATE_READING):
            self._draw_world()
            if self.state == STATE_LEVEL_INTRO:
                self._draw_level_intro()
            if self.state == STATE_PAUSED:
                self._draw_pause()
            if self.state == STATE_READING:
                self._draw_reading()
        elif self.state == STATE_GAMEOVER:
            self._draw_world()
            self._draw_gameover()
        elif self.state == STATE_WIN:
            self._draw_win()
        if self.fade > 0:
            self._overlay((0, 0, 0), 255 * self.fade)
        self._present()
        pygame.display.flip()

    def _draw_splash(self):
        self.screen.fill((3, 3, 5))
        t = self.splash_t
        cx, cy = DISPLAY_W // 2, DISPLAY_H // 2

        if t < 1.1:
            alpha = t / 1.1
        elif t < 2.8:
            alpha = 1.0
        else:
            alpha = max(0.0, 1.0 - (t - 2.8) / 1.0)

        flick = 0.88 + 0.12 * math.sin(t * 23.0) * math.cos(t * 11.0)
        a_val = _alpha(255 * alpha * flick)

        spot = pygame.Surface((420, 260), pygame.SRCALPHA)
        for r in range(120, 20, -12):
            pygame.draw.ellipse(spot, (34, 12, 14, int(14 * alpha * flick)),
                                (210 - r * 1.5, 130 - r, r * 3, r * 2))
        self.screen.blit(spot, (cx - 210, cy - 130))

        skull = pygame.transform.scale(self.enemy_surfs[('grunt', 1 if (int(t * 6) % 2) else 0)], (110, 110))
        skull.set_alpha(_alpha(65 * alpha * flick))
        jx = int(math.sin(t * 50) * 3) if (1.6 < t < 1.85) else 0
        self.screen.blit(skull, (cx - 55 + jx, cy - 115))

        prod_txt = self.font_big.render("a  KS_5G1  production", True, (215, 205, 195))
        prod_glow = self.font_big.render("a  KS_5G1  production", True, (130, 18, 22))
        prod_txt.set_alpha(a_val)
        prod_glow.set_alpha(_alpha(150 * alpha))
        self.screen.blit(prod_glow, prod_glow.get_rect(center=(cx + 2 + jx, cy + 18)))
        self.screen.blit(prod_txt, prod_txt.get_rect(center=(cx + jx, cy + 16)))

        sub = self.font_tiny.render("P R E S E N T S", True, (135, 125, 120))
        sub.set_alpha(_alpha(190 * alpha))
        self.screen.blit(sub, sub.get_rect(center=(cx, cy + 68)))

        self.screen.blit(self._vignette_surf, (0, 0))

    def _draw_story_intro(self):
        self.screen.fill((5, 6, 8))
        cx = DISPLAY_W // 2

        shown = TYPING_HORROR_INTRO_TEXT[:self.story_intro_chars]
        lines = shown.split('\n')
        y0 = 135
        for i, line in enumerate(lines):
            is_last = (i == len(lines) - 1)
            cursor = "█" if (is_last and int(self.time * 4) % 2 == 0) else ""
            col = (210, 75, 75) if i < 2 else (215, 220, 215)
            surf = self.font_small.render(line + cursor, True, col)
            self.screen.blit(surf, (140, y0 + i * 30))

        done = self.story_intro_chars >= len(TYPING_HORROR_INTRO_TEXT)
        prompt = "Press ENTER / SPACE to step into the dark" if done else "Press ENTER / SPACE to skip typing"
        if int(self.time * 2) % 2 == 0 or not done:
            p_surf = self.font_tiny.render(prompt, True, (150, 145, 135))
            self.screen.blit(p_surf, p_surf.get_rect(center=(cx, DISPLAY_H - 48)))

        self.screen.blit(self._vignette_surf, (0, 0))

    def _overlay(self, rgb, alpha):
        alpha = max(0, min(255, int(alpha)))
        if alpha <= 0:
            return
        surf = self._overlay_surfs.get(rgb)
        if surf is None:
            surf = pygame.Surface((DISPLAY_W, DISPLAY_H))
            surf.fill(rgb)
            self._overlay_surfs[rgb] = surf
        surf.set_alpha(alpha)
        self.screen.blit(surf, (0, 0))

    def _world_sprites(self):
        sprites = []

        for e in self.level.enemies:
            base_scale = 0.95 if e.kind == 'brute' else 0.78 if e.kind == 'grunt' else 0.84
            tint = None
            if e.hit_flash > 0:
                f = int(220 * min(1.0, e.hit_flash / 0.12))
                tint = (f, f, f)
            if e.slow_t > 0 and e.state != 'dead':
                pulse = 0.6 + 0.4 * math.sin(self.time * 9.0 + e.x)
                blue = (int(10 * pulse), int(35 * pulse), int(75 * pulse))
                tint = blue if tint is None else tuple(min(255, tint[i] + blue[i]) for i in range(3))
            if e.state == 'dead':
                u = min(1.0, e.dead_timer / 0.35)
                ease = 1.0 - (1.0 - u) ** 2
                frame = 2 if u < 0.35 else 3
                sprites.append((e.x, e.y, self.enemy_surfs[(e.kind, frame)],
                                base_scale + (0.55 - base_scale) * ease, 0.28 * ease, tint))
            else:
                if e.kind == 'grunt':
                    walk_frames = (0, 1, 4, 5)
                    frame = 2 if (e.state == 'attack' or e.fire_flash > 0) else walk_frames[int(e.anim_t * 6.0) % 4]
                    hover = -0.08 + 0.08 * math.sin(self.time * 4.2 + e.x * 3.1)
                    sprites.append((e.x, e.y, self.enemy_surfs[('grunt', frame)],
                                    base_scale, hover, tint))
                elif e.kind in ('charger', 'brute'):
                    # Both Evaporating Shadow ('charger') and Reanimated Dead Body ('brute')
                    # animate across 5 active frames (0, 1, 4, 5 + attack 2)
                    anim_frames = (0, 1, 4, 5)
                    spd = 8.0 if e.kind == 'charger' else 4.5
                    frame = 2 if e.state == 'attack' else anim_frames[int(e.anim_t * spd) % 4]
                    sprites.append((e.x, e.y, self.enemy_surfs[(e.kind, frame)],
                                    base_scale, 0.06 if e.kind == 'brute' else 0.0, tint))
                else:
                    phase = int(e.anim_t * 4) % 2
                    frame = 2 if (e.state == 'attack' or e.fire_flash > 0) else phase
                    sprites.append((e.x, e.y, self.enemy_surfs[(e.kind, frame)], base_scale, 0.0, tint))

        for an in self.level.anomalies:
            surf = self.anomaly_surfs[an.kind]
            if an.kind in ('floating_chair', 'ghost_skull', 'ghost_remnant'):
                float_bob = -0.05 + 0.06 * math.sin(self.time * 3.2 + an.x * 5.0)
            else:
                float_bob = 0.14
            tint = None
            if an.is_core and an.photo_id not in self.sector_photos:
                glint = int(18 * (0.5 + 0.5 * math.sin(self.time * 4.0 + an.photo_id)))
                tint = (glint, glint + 8, glint)
            sprites.append((an.x, an.y, surf, 0.58, float_bob, tint))
            for cx, cy, sc_mult in an.companions:
                sprites.append((cx, cy, surf, 0.52 * sc_mult, float_bob, tint))

        for cr in self.level.critters:
            if cr.kind == 'swarm':
                f = int(cr.anim_t) % len(self.insect_surfs)
                sprites.append((cr.x, cr.y, self.insect_surfs[f], 0.52, 0.26))
            else:
                f = int(cr.anim_t) % len(self.mouse_surfs)
                sprites.append((cr.x, cr.y, self.mouse_surfs[f], 0.36, 0.34))

        for pick in self.level.pickups:
            if pick.alive:
                surf = self.pickup_surfs[pick.kind]
                bob = 0.06 * math.sin(self.time * 3 + pick.x * 7)
                emissive = (pick.kind == 'blue_key')
                sprites.append((pick.x, pick.y, surf, 0.42 if emissive else 0.4, 0.25 + bob, None, emissive))

        orb = self.fx_surfs['plasma_orb'][0]
        for pr in self.projectiles:
            sprites.append((pr.x, pr.y, orb, 0.30 + 0.03 * math.sin(self.time * 40.0), 0.10, None, True))
        for fx in self.effects:
            frames = self.fx_surfs[fx.kind]
            u = max(0.0, min(0.999, fx.t / fx.dur))
            frame = frames[int(u * len(frames))]
            scale = (0.35 + 0.7 * u) if fx.kind == 'plasma_hit' else 0.16 * (1.0 - 0.5 * u)
            sprites.append((fx.x, fx.y, frame, scale, 0.10, None, True))
        return sprites

    def _draw_world(self):
        p = self.player
        grid = self.level.grid
        self.renderer.draw_floor_ceiling(p)
        self.renderer.draw_walls(p, grid, self.level.opened_doors)
        self.renderer.draw_sprites(p, grid, self._world_sprites())
        self.renderer.apply_flicker_overlay()
        self.renderer.present()

        if self.night_vision:
            self.screen.fill((15, 55, 22), special_flags=pygame.BLEND_RGB_ADD)

        if self.shake > 0.3:
            t = self.time
            self.screen.scroll(int(round(math.sin(t * 61.0) * self.shake)),
                               int(round(math.cos(t * 53.0) * self.shake * 0.8)))
        if self.muzzle_light > 0.02:
            m = self.muzzle_light * 0.18
            r, g, b = self.muzzle_col
            self.screen.fill((int(r * m), int(g * m), int(b * m)), special_flags=pygame.BLEND_RGB_ADD)
        if self.beam_t > 0:
            self._draw_beam()

        self._draw_weapon()
        self._draw_flashes()
        if self.viewfinder_on:
            self._draw_camera_viewfinder()
        self._draw_hud()
        self._draw_contextual_prompts()
        self._draw_live_social_ticker()
        self._draw_photo_preview()
        self._draw_creator_monologue()
        if self.touch_controls and self.state == STATE_PLAYING:
            self._draw_touch_controls()
        if self.show_big_map and self.state == STATE_PLAYING:
            self._draw_big_map()
        if self.show_controls_help and self.state == STATE_PLAYING:
            self._draw_controls_guide()
        self._draw_message()

    def _draw_contextual_prompts(self):
        """Interactive, non-intrusive contextual tips that help the player understand all
        controls and features naturally while playing."""
        p = self.player
        cx = DISPLAY_W // 2
        hint = None
        if self.sector_play_t < 6.0 and self.level_index == 0:
            hint = "TIP: Move with WASD • Aim with Mouse • Press [H] anytime for Full Controls & Features Guide"
        elif self.current_photo_candidate is not None and len(self.sector_photos) == 0:
            hint = "TIP: Anomaly in frame! Press [Right Click] or [C] to snap your first Proof Photo"
        elif p.armed and p.ammo[p.weapon_index] == 0 and p.reserve[p.weapon_index] > 0 and not p.reloading:
            hint = "TIP: Magazine empty — Press [R] to reload your weapon"
        elif len(self.unposted_blog_photos) >= 3 and len(self.blog_posts) == 0:
            hint = "TIP: You have unposted photos! Press [N] to publish on your Blog, Book & Livestream"
        elif len(self.sector_photos) >= PHOTOS_REQUIRED and 'blue_key' not in p.keys and int(self.time) % 8 < 4:
            hint = "OBJECTIVE UPDATE: 10+ unique photos captured — the Blue Exit Key has materialized somewhere in this sector!"

        if hint:
            t_surf = self.font_tiny.render(hint, True, (220, 210, 165))
            self.screen.blit(t_surf, t_surf.get_rect(center=(cx, 62)))

    def _draw_controls_guide(self):
        """Full in-game Controls & Features Field Manual overlay (toggled with H or F1)."""
        dim = pygame.Surface((DISPLAY_W, DISPLAY_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 205))
        self.screen.blit(dim, (0, 0))
        cx = DISPLAY_W // 2

        title = self.font_med.render("URBEX FIELD MANUAL — CONTROLS & FEATURES", True, (235, 215, 155))
        self.screen.blit(title, title.get_rect(center=(cx, 62)))

        sections = [
            ("MOVEMENT & SURVIVAL", [
                "W A S D : Move & Strafe       Shift : Sprint",
                "Mouse / Arrows : Look         Tab : Hand-Drawn Expedition Map",
                "Stalker Rule : Melee entities creep while watched, but rush when you look away!",
            ]),
            ("CAMERA, PHOTO PROOF & SILENT BLUE KEY", [
                "Right Click / C / F : Snap Picture (Captures Core Proof + Blog/Book B-Roll)",
                "G : Toggle Camcorder IR Night-Vision       V : Toggle Viewfinder",
                "Exit Rule : Capture at least 10 unique anomalies to silently spawn the Blue Exit Key!",
            ]),
            ("WEAPONS & COMBAT", [
                "Left Click / Space : Fire Weapon (Hold to charge the Railgun)",
                "R : Reload Weapon       1 - 4 : Switch Found Weapons (Pistol/Shotgun/Plasma/Railgun)",
            ]),
            ("CREATOR NOTEBOOK & MOBILE MODE", [
                "N / L : Open 3-Page Notebook (Manage Livestream, Publish Blogs & Write Book Chapters)",
                "T : Toggle On-Screen Mobile Touch Controls       F11 : Fullscreen",
            ]),
        ]

        y = 108
        for header, lines in sections:
            h_s = self.font_small.render(header, True, (225, 85, 85))
            self.screen.blit(h_s, (150, y))
            y += 26
            for ln in lines:
                l_s = self.font_tiny.render("•  " + ln, True, (215, 215, 210))
                self.screen.blit(l_s, (170, y))
                y += 21
            y += 12

        foot = self.font_tiny.render("Press [H / F1 / ESC] to close Field Manual", True, (170, 215, 165))
        self.screen.blit(foot, foot.get_rect(center=(cx, DISPLAY_H - 36)))

    def _draw_touch_controls(self):
        """On-screen Mobile Touch Controls overlay (virtual thumbstick + tap buttons)."""
        jx, jy = self.touch_joy_center
        jr = self.touch_joy_radius
        overlay = pygame.Surface((DISPLAY_W, DISPLAY_H), pygame.SRCALPHA)
        # Left virtual joystick ring + thumb knob
        pygame.draw.circle(overlay, (255, 255, 255, 45), (jx, jy), jr, 2)
        kx = int(jx + self.touch_move_vec[0] * (jr - 18))
        ky = int(jy - self.touch_move_vec[1] * (jr - 18))
        pygame.draw.circle(overlay, (220, 230, 240, 110), (kx, ky), 24)

        # Right-side action buttons
        btns = {
            'fire':     (pygame.Rect(DISPLAY_W - 145, DISPLAY_H - 165, 110, 52), "FIRE"),
            'snap':     (pygame.Rect(DISPLAY_W - 265, DISPLAY_H - 165, 108, 52), "SNAP PIC"),
            'reload':   (pygame.Rect(DISPLAY_W - 145, DISPLAY_H - 228, 110, 44), "RELOAD"),
            'ir':       (pygame.Rect(DISPLAY_W - 265, DISPLAY_H - 228, 108, 44), "IR NIGHT"),
            'notebook': (pygame.Rect(DISPLAY_W - 145, 70, 110, 38), "NOTEBOOK"),
            'map':      (pygame.Rect(DISPLAY_W - 265, 70, 108, 38), "MAP"),
            'help':     (pygame.Rect(24, 68, 92, 34), "GUIDE"),
        }
        self._touch_buttons = btns
        for key_id, (rect, label) in btns.items():
            col = (210, 55, 55, 115) if key_id == 'fire' else (55, 165, 195, 110) if key_id == 'snap' else (40, 45, 55, 110)
            pygame.draw.rect(overlay, col, rect, border_radius=8)
            pygame.draw.rect(overlay, (215, 220, 225, 140), rect, 1, border_radius=8)
            t = self.font_tiny.render(label, True, (240, 240, 245))
            overlay.blit(t, t.get_rect(center=rect.center))
        self.screen.blit(overlay, (0, 0))

    def _draw_live_social_ticker(self):
        ox = DISPLAY_W - 24
        if int(self.time * 2.2) % 2 == 0:
            pygame.draw.circle(self.screen, (235, 45, 45), (DISPLAY_W - 230, 20), 4)
        top_line = self.font_tiny.render(
            f"LIVE  {self.live_viewers:,} watching  •  {self.followers // 1000}K", True, (220, 220, 225)
        )
        self.screen.blit(top_line, top_line.get_rect(topright=(ox, 13)))

        if self.stream_comments and self.live_chat_fade > 0:
            alpha = _alpha(255 * min(1.0, self.live_chat_fade / 1.2))
            recent = self.stream_comments[-2:]
            for idx_c, (user, cmt) in enumerate(recent):
                short_cmt = cmt if len(cmt) <= 44 else cmt[:41] + "..."
                col_c = (225, 215, 165) if idx_c == len(recent) - 1 else (165, 165, 175)
                c_surf = self.font_tiny.render(f"{user}: {short_cmt}", True, col_c)
                c_surf.set_alpha(alpha if idx_c == len(recent) - 1 else int(alpha * 0.72))
                self.screen.blit(c_surf, c_surf.get_rect(topright=(ox, 33 + idx_c * 17)))

        # Clickable/tappable [TOUCH / PC] control-mode pill in top-center HUD
        ctrl_lbl = "TOUCH: ON" if self.touch_controls else "PC KEYS"
        pill = pygame.Rect(DISPLAY_W // 2 - 48, 10, 96, 22)
        self._hud_touch_rect = pill
        pygame.draw.rect(self.screen, (28, 32, 38), pill, border_radius=5)
        pygame.draw.rect(self.screen, (110, 210, 150) if self.touch_controls else (120, 125, 135), pill, 1, border_radius=5)
        pt = self.font_tiny.render(ctrl_lbl, True, (220, 230, 225))
        self.screen.blit(pt, pt.get_rect(center=pill.center))

        # Active Superchat Challenge Banner
        if self.active_superchat is not None:
            sc = self.active_superchat
            bw, bh = 310, 56
            bx, by = DISPLAY_W - bw - 20, 74
            panel = pygame.Surface((bw, bh), pygame.SRCALPHA)
            panel.fill((34, 24, 8, 205))
            pygame.draw.rect(panel, (240, 190, 60, 230), (0, 0, bw, bh), 2, border_radius=6)
            t1 = self.font_tiny.render(f"${sc['amt']} SUPERCHAT • {sc['donor']}", True, (255, 220, 95))
            t2 = self.font_tiny.render(sc['desc'][:40], True, (245, 240, 225))
            panel.blit(t1, (10, 6))
            panel.blit(t2, (10, 24))
            frac = max(0.0, min(1.0, sc['left'] / max(0.1, sc['dur'])))
            pygame.draw.rect(panel, (65, 50, 20), (10, bh - 10, bw - 20, 4))
            pygame.draw.rect(panel, (245, 195, 65), (10, bh - 10, int((bw - 20) * frac), 4))
            self.screen.blit(panel, (bx, by))

    def _draw_camera_viewfinder(self):
        cx, cy = DISPLAY_W // 2, DISPLAY_H // 2
        vw, vh = 500, 320
        x0, y0 = cx - vw // 2, cy - vh // 2
        x1, y1 = cx + vw // 2, cy + vh // 2
        c_len = 22

        cand = self.current_photo_candidate
        if cand is not None:
            _, name, _, _, is_new, dist, is_core = cand
            if is_new and is_core:
                frame_col = (70, 255, 130)
            elif is_new and not is_core:
                frame_col = (95, 215, 255)
            else:
                frame_col = (255, 200, 70)
        else:
            frame_col = (120, 240, 150) if self.night_vision else (160, 170, 180)

        for bx, by, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            pygame.draw.line(self.screen, frame_col, (bx, by), (bx + sx * c_len, by), 2)
            pygame.draw.line(self.screen, frame_col, (bx, by), (bx, by + sy * c_len), 2)

        if cand is not None:
            _, name, _, _, is_new, dist, is_core = cand
            tag = f"{name}  [R-Click / C]" if is_new else f"{name} (Taken)"
            t_surf = self.font_tiny.render(tag, True, frame_col)
            self.screen.blit(t_surf, t_surf.get_rect(center=(cx, y1 + 16)))

    def _draw_photo_preview(self):
        if self.photo_preview_t <= 0 or self.photo_preview_surf is None:
            return
        alpha = max(0, min(255, int(255 * min(1.0, self.photo_preview_t / 0.45))))
        pw, ph = 204, 178
        px, py = 24, 54
        card = pygame.Surface((pw, ph), pygame.SRCALPHA)
        card.fill((242, 238, 226, alpha))
        pygame.draw.rect(card, (40, 40, 45, alpha), (0, 0, pw, ph), 2)
        thumb = self.photo_preview_surf.copy()
        thumb.set_alpha(alpha)
        card.blit(thumb, (12, 10))
        lbl = self.font_tiny.render(self.photo_preview_label[:26], True, (20, 20, 25))
        sub = self.font_tiny.render(self.photo_preview_sub[:28], True, (80, 30, 30))
        card.blit(lbl, (10, 140))
        card.blit(sub, (10, 156))
        self.screen.blit(card, (px, py))

    def _draw_creator_monologue(self):
        if self.monologue_t <= 0 or not self.monologue_text:
            return
        alpha = max(0, min(255, int(255 * min(1.0, self.monologue_t / 0.5))))
        lines = self._wrap_text(f'"{self.monologue_text}"', self.font_small, 720)
        by = DISPLAY_H - 82 - len(lines) * 24
        for i, ln in enumerate(lines):
            shd = self.font_small.render(ln, True, (0, 0, 0))
            txt = self.font_small.render(ln, True, (235, 232, 215))
            shd.set_alpha(alpha)
            txt.set_alpha(alpha)
            cx = DISPLAY_W // 2
            self.screen.blit(shd, shd.get_rect(center=(cx + 2, by + i * 24 + 2)))
            self.screen.blit(txt, txt.get_rect(center=(cx, by + i * 24)))

    def _draw_beam(self):
        u = max(0.0, min(1.0, self.beam_t / 0.40))
        s = self._beam_surf
        s.fill((0, 0, 0, 0))
        cx, cy = DISPLAY_W // 2, DISPLAY_H // 2
        mx, my = DISPLAY_W // 2 + 34, DISPLAY_H - 150
        pygame.draw.line(s, (90, 150, 255, _alpha(70 * u)), (mx, my), (cx, cy), int(26 * u) + 4)
        pygame.draw.line(s, (150, 200, 255, _alpha(150 * u)), (mx, my), (cx, cy), int(12 * u) + 2)
        pygame.draw.line(s, (255, 255, 255, _alpha(255 * u)), (mx, my), (cx, cy), max(1, int(5 * u)))
        pygame.draw.circle(s, (190, 225, 255, _alpha(200 * u)), (cx, cy), int(10 + 60 * (1.0 - u)),
                           max(1, int(5 * u)))
        self.screen.blit(s, (0, 0))

    def _draw_weapon(self):
        p = self.player
        if not p.weapons_owned[self.vm_index]:
            return
        frame = self.gun_frames_scaled[self.vm_index][self.gun_frame]
        sw, sh = frame.get_size()
        speed_f = min(1.0, math.hypot(p.vx, p.vy) / MOVE_SPEED) if self.head_bob else 0.0
        bob_x = math.sin(self.bob_t) * 14 * speed_f
        bob_y = abs(math.sin(self.bob_t)) * 10 * speed_f
        breathe = math.sin(self.time * 1.8) * 2.0
        kick = self.recoil * 30
        dip = 0.0
        if p.reloading:
            frac = 1.0 - p.reload_timer / max(0.01, p.weapon['reload_time'])
            dip = math.sin(math.pi * max(0.0, min(1.0, frac))) * 28
        drop = self.vm_drop * 220
        tremble = 0.0
        if p.charge > 0 and 'charge' in p.weapon:
            tremble = math.sin(self.time * 85.0) * 3.0 * (p.charge / p.weapon['charge'])
        x = DISPLAY_W // 2 - sw // 2 + int(bob_x + self.sway_x + tremble)
        y = DISPLAY_H - sh + 56 + int(bob_y + breathe + kick + dip + drop)
        self.screen.blit(frame, (x, y))

    def _build_vignette_surf(self):
        vig = pygame.Surface((DISPLAY_W, DISPLAY_H), pygame.SRCALPHA)
        band = 40
        for i in range(band):
            a = int(85 * (1 - i / band))
            if a <= 0:
                continue
            pygame.draw.rect(vig, (0, 0, 0, a), (0, i, DISPLAY_W, 1))
            pygame.draw.rect(vig, (0, 0, 0, a), (0, DISPLAY_H - 1 - i, DISPLAY_W, 1))
            pygame.draw.rect(vig, (0, 0, 0, a), (i, 0, 1, DISPLAY_H))
            pygame.draw.rect(vig, (0, 0, 0, a), (DISPLAY_W - 1 - i, 0, 1, DISPLAY_H))
        return vig

    def _build_scanline_surf(self):
        s = pygame.Surface((DISPLAY_W, DISPLAY_H), pygame.SRCALPHA)
        for y in range(0, DISPLAY_H, 3):
            pygame.draw.line(s, (0, 0, 0, 26), (0, y), (DISPLAY_W, y), 1)
        return s

    def _build_heartbeat_surf(self):
        s = pygame.Surface((DISPLAY_W, DISPLAY_H), pygame.SRCALPHA)
        edge = 90
        for i in range(edge):
            a = _alpha(255 * (1.0 - i / edge) ** 1.6)
            if a <= 0:
                continue
            col = (90, 0, 0, a)
            pygame.draw.rect(s, col, (0, i, DISPLAY_W, 1))
            pygame.draw.rect(s, col, (0, DISPLAY_H - 1 - i, DISPLAY_W, 1))
            pygame.draw.rect(s, col, (i, 0, 1, DISPLAY_H))
            pygame.draw.rect(s, col, (DISPLAY_W - 1 - i, 0, 1, DISPLAY_H))
        return s

    def _build_fog_surf(self):
        w, h = DISPLAY_W * 2, 240
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        rng = random.Random(77)
        for _ in range(26):
            ew, eh = rng.randint(260, 560), rng.randint(60, 150)
            ex, ey = rng.randint(0, w - ew), rng.randint(0, h - eh)
            pygame.draw.ellipse(s, (70, 70, 96, rng.randint(10, 22)), (ex, ey, ew, eh))
        return s

    def _heartbeat_intensity(self):
        period = self.heart_period
        t = self.heart_t % period

        def pulse(center, width):
            return math.exp(-((t - center) / width) ** 2)
        return 0.55 * pulse(0.05, 0.06) + 0.40 * pulse(0.22, 0.05)

    def _draw_flashes(self):
        p = self.player
        self._overlay((200, 0, 0), 120 * p.damage_flash)
        self._overlay((255, 255, 255), 60 * p.pickup_flash)
        self._overlay((255, 252, 240), 210 * self.camera_flash)
        self._overlay((110, 0, 0), 75 * self.scare_flash)

        beat = self._heartbeat_intensity()
        if beat > 0.02:
            self._hb_surf.set_alpha(_alpha(150 * beat))
            self.screen.blit(self._hb_surf, (0, 0))

        self._draw_dmg_markers()
        self.screen.blit(self._vignette_surf, (0, 0))

    def _draw_dmg_markers(self):
        p = self.player
        cx, cy = DISPLAY_W // 2, DISPLAY_H // 2
        for ang, left in self.dmg_marks:
            a = max(0.0, min(1.0, left / 0.5))
            rel = ang - p.angle
            dx, dy = math.sin(rel), -math.cos(rel)
            px = cx + dx * DISPLAY_W * 0.36
            py = cy + dy * DISPLAY_H * 0.36
            nx, ny = -dy, dx
            half = 12 + 14 * a
            tip = 10 + 26 * a
            pts = [(int(px + nx * half - dx * 6), int(py + ny * half - dy * 6)),
                   (int(px - nx * half - dx * 6), int(py - ny * half - dy * 6)),
                   (int(px + dx * tip), int(py + dy * tip))]
            pygame.draw.polygon(self.screen, (215, 25, 25), pts)

    def _draw_crosshair(self):
        p = self.player
        cx, cy = DISPLAY_W // 2, DISPLAY_H // 2
        if not p.armed:
            pygame.draw.circle(self.screen, (170, 170, 170), (cx, cy), 2)
            return
        col = (255, 70, 70) if self.on_target else (255, 255, 255)
        gap = int(self.cross_gap)
        ln = 8
        pygame.draw.line(self.screen, col, (cx - gap - ln, cy), (cx - gap, cy), 2)
        pygame.draw.line(self.screen, col, (cx + gap, cy), (cx + gap + ln, cy), 2)
        pygame.draw.line(self.screen, col, (cx, cy - gap - ln), (cx, cy - gap), 2)
        pygame.draw.line(self.screen, col, (cx, cy + gap), (cx, cy + gap + ln), 2)
        if p.charge > 0 and 'charge' in p.weapon:
            f = min(1.0, p.charge / p.weapon['charge'])
            pygame.draw.circle(self.screen, (int(120 + 135 * f), int(170 + 85 * f), 255),
                               (cx, cy), int(46 - 34 * f), 2)
        if self.hit_t > 0:
            kill = self.hit_kill
            u = self.hit_t / (0.32 if kill else 0.15)
            d = int(9 + (1.0 - u) * 5)
            length = 10 if kill else 6
            c = (255, 50, 50) if kill else (255, 255, 255)
            for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                pygame.draw.line(self.screen, c, (cx + sx * d, cy + sy * d),
                                 (cx + sx * (d + length), cy + sy * (d + length)), 3 if kill else 2)

    def _draw_hud(self):
        p = self.player
        bar_w, bar_h = 200, 18

        if p.spawn_grace > 0:
            alpha = min(255, int(255 * min(1.0, p.spawn_grace)))
            txt = self.font_tiny.render("SPAWN PROTECTED", True, (120, 220, 255))
            txt.set_alpha(alpha)
            self.screen.blit(txt, txt.get_rect(center=(DISPLAY_W // 2, 42)))

        x0, y0 = 24, DISPLAY_H - 36
        pygame.draw.rect(self.screen, (25, 25, 28), (x0, y0, bar_w, bar_h), border_radius=3)
        real = max(0.0, p.hp / p.max_hp)
        shown = max(0.0, min(1.0, self.hp_shown / p.max_hp))
        ghost = max(0.0, min(1.0, self.hp_ghost / p.max_hp))
        if ghost > shown:
            pygame.draw.rect(self.screen, (130, 35, 35), (x0, y0, int(bar_w * ghost), bar_h), border_radius=3)
        col = (60, 190, 65) if real > 0.5 else (210, 165, 30) if real > 0.25 else (210, 40, 40)
        if int(bar_w * shown) > 0:
            pygame.draw.rect(self.screen, col, (x0, y0, int(bar_w * shown), bar_h), border_radius=3)
        txt = self.font_tiny.render(f"HP {int(p.hp)}", True, (240, 240, 240))
        self.screen.blit(txt, (x0 + 6, y0 + 2))

        cam_col = (110, 235, 150) if len(self.sector_photos) >= PHOTOS_REQUIRED else (215, 210, 180)
        if not self._is_nv_allowed():
            ir_lbl = "IR: JAMMED"
        elif self.nv_battery <= 0.0:
            ir_lbl = "IR: DEAD (0%)"
        elif self.night_vision:
            ir_lbl = f"IR: ON {int(self.nv_battery * 100)}%"
        else:
            ir_lbl = f"IR [G]: {int(self.nv_battery * 100)}%"
        cam_txt = self.font_tiny.render(
            f"Pics: {len(self.sector_photos)} (10+ needed)  •  {ir_lbl}  •  [N] Notebook  •  [H] Guide",
            True, cam_col,
        )
        self.screen.blit(cam_txt, (x0, y0 - 20))

        if p.armed:
            wi = p.weapon_index
            label = "RELOADING..." if p.reloading else f"{p.weapon['name']}  {p.ammo[wi]}/{p.reserve[wi]}"
            txt2 = self.font_tiny.render(label, True, (230, 230, 230))
            self.screen.blit(txt2, txt2.get_rect(bottomright=(DISPLAY_W - 24, DISPLAY_H - 20)))

        bkey_str = "  •  BLUE KEY FOUND" if 'blue_key' in p.keys else ""
        vkey_str = "  •  VAULT KEY" if 'key' in p.keys else ""
        top = self.font_tiny.render(
            f"{self.level.name}{vkey_str}{bkey_str}",
            True, (195, 195, 200),
        )
        self.screen.blit(top, (20, 14))

        self._draw_crosshair()

    def _draw_message(self):
        base_y = DISPLAY_H - 165
        for i, (text, left) in enumerate(reversed(self.messages)):
            alpha = max(0, min(255, int(255 * min(1.0, left / 0.6))))
            txt = self.font_small.render(text, True, (245, 225, 130) if i == 0 else (215, 195, 120))
            rect = txt.get_rect(center=(DISPLAY_W // 2, base_y - i * 28))
            txt.set_alpha(alpha)
            self.screen.blit(txt, rect)

    def _wrap_text(self, text, font, max_width):
        lines = []
        for raw_line in text.split('\n'):
            words = raw_line.split(' ')
            cur = ""
            for word in words:
                trial = (cur + " " + word).strip()
                if font.size(trial)[0] <= max_width:
                    cur = trial
                else:
                    if cur:
                        lines.append(cur)
                    cur = word
            lines.append(cur)
        return lines

    def _draw_log_panel(self, header, sub_header, body, footer=None, header_col=(210, 195, 155)):
        max_text_w = 640
        lines = self._wrap_text(body, self.font_small, max_text_w)
        line_h = 24
        box_w = max_text_w + 90
        box_h = 115 + len(lines) * line_h + (36 if footer else 0)
        box_x = DISPLAY_W // 2 - box_w // 2
        box_y = max(110, (DISPLAY_H - box_h) // 2)
        panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        panel.fill((14, 14, 18, 245))
        pygame.draw.rect(panel, (95, 85, 75), (0, 0, box_w, box_h), width=1)
        panel.blit(self.font_small.render(header, True, header_col), (45, 18))
        panel.blit(self.font_tiny.render(sub_header, True, (145, 140, 135)), (45, 42))
        for i, line in enumerate(lines):
            panel.blit(self.font_small.render(line, True, (220, 215, 205)), (45, 74 + i * line_h))
        self.screen.blit(panel, (box_x, box_y))
        if footer:
            ft = self.font_small.render(footer, True, (225, 200, 130))
            self.screen.blit(ft, ft.get_rect(center=(DISPLAY_W // 2, box_y + box_h - 24)))

    def _draw_reading(self):
        dim = pygame.Surface((DISPLAY_W, DISPLAY_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 185))
        self.screen.blit(dim, (0, 0))
        idx = self.reading_index
        header = "FIELD NOTE RECOVERED" if self.reading_is_new else "FIELD NOTE"
        sub = f"SECTOR {idx + 1} - {SECTOR_NAMES[idx]}"
        ready = self.reading_t >= 0.6
        blink = (int(self.time * 2) % 2 == 0)
        footer = "Press E / ENTER / SPACE to close" if (ready and blink) else " "
        self._draw_log_panel(header, sub, self.reading_text, footer)

    def _draw_archive(self):
        self.screen.fill((11, 11, 14))
        cx = DISPLAY_W // 2

        pages = ["1. LIVE STREAM", "2. BLOG & BOOK", "3. POLAROIDS & NOTES"]
        self.archive_tab = self.archive_tab % 3
        self._archive_tab_rects = []
        for i, pname in enumerate(pages):
            active = (self.archive_tab == i)
            col = (235, 215, 150) if active else (115, 115, 120)
            t = self.font_small.render(pname, True, col)
            px = cx + (i - 1) * 250
            tr = t.get_rect(center=(px, 48))
            self._archive_tab_rects.append((tr.inflate(24, 14), i))
            self.screen.blit(t, tr)
            if active:
                pygame.draw.line(self.screen, (200, 60, 60), (px - 70, 64), (px + 70, 64), 2)
        ab_rect = pygame.Rect(24, 24, 96, 30)
        self._archive_back_rect = ab_rect
        pygame.draw.rect(self.screen, (26, 26, 32), ab_rect, border_radius=6)
        pygame.draw.rect(self.screen, (130, 130, 140), ab_rect, 1, border_radius=6)
        abt = self.font_tiny.render("< CLOSE", True, (220, 220, 220))
        self.screen.blit(abt, abt.get_rect(center=ab_rect.center))

        if self.archive_tab == 0:
            head = self.font_med.render(f"@VoidVlogs  •  {self.followers:,} Followers", True, (235, 230, 220))
            self.screen.blit(head, head.get_rect(center=(cx, 108)))
            sub = self.font_tiny.render(
                f"{self.live_viewers:,} watching live   •   {self.stream_likes:,} likes", True, (165, 160, 155)
            )
            self.screen.blit(sub, sub.get_rect(center=(cx, 138)))

            if self.all_captured_photos:
                last_p = self.all_captured_photos[-1]
                scaled_t = pygame.transform.scale(last_p['thumb'], (240, 168))
                self.screen.blit(scaled_t, (cx - 120, 166))
                cap = self.font_tiny.render(last_p['name'], True, (200, 195, 185))
                self.screen.blit(cap, cap.get_rect(center=(cx, 348)))

            y_chat = 382
            for u_handle, u_msg in self.stream_comments[-5:]:
                col_u = (215, 95, 95) if u_handle.startswith("@USER") or u_handle.startswith("@ANTIBODY") else (195, 190, 180)
                line = self.font_small.render(f"{u_handle}: {u_msg[:64]}", True, col_u)
                self.screen.blit(line, line.get_rect(center=(cx, y_chat)))
                y_chat += 28

            act = self.font_tiny.render("Press [SPACE / ENTER] to share latest shot on stream", True, (145, 205, 155))
            self.screen.blit(act, act.get_rect(center=(cx, DISPLAY_H - 58)))

        elif self.archive_tab == 1:
            head = self.font_med.render("Blog & Book Manuscript", True, (235, 230, 220))
            self.screen.blit(head, head.get_rect(center=(cx, 108)))
            sub = self.font_tiny.render(
                f"Blog Views: {self.blog_total_views:,} ({len(self.blog_posts)} posts)   •   "
                f"Book: {len(self.book_chapters)} Chapters ({self.book_preorders:,} pre-orders)",
                True, (165, 160, 155),
            )
            self.screen.blit(sub, sub.get_rect(center=(cx, 138)))

            y = 185
            if self.blog_posts:
                latest_b = self.blog_posts[-1]
                self.screen.blit(self.font_small.render(f"Latest Blog: {latest_b['title']}", True, (225, 205, 140)), (140, y))
                self.screen.blit(self.font_tiny.render(latest_b['comment'], True, (175, 180, 185)), (140, y + 26))
            else:
                self.screen.blit(self.font_small.render("Blog: No posts published yet.", True, (160, 160, 165)), (140, y))

            y = 285
            if self.book_chapters:
                latest_c = self.book_chapters[-1]
                self.screen.blit(self.font_small.render(f"Book Draft — {latest_c['title']}", True, (225, 205, 140)), (140, y))
                for i, ln in enumerate(self._wrap_text(latest_c['summary'], self.font_small, 740)[:3]):
                    self.screen.blit(self.font_small.render(ln, True, (205, 200, 190)), (140, y + 30 + i * 24))
                self.screen.blit(self.font_tiny.render(latest_c['review'], True, (150, 200, 160)), (140, y + 110))
            else:
                self.screen.blit(self.font_small.render("Book: Take photos in-game to draft Chapter 1.", True, (160, 160, 165)), (140, y))

            act = self.font_tiny.render(
                f"Press [SPACE / ENTER] to publish Blog & Book update ({len(self.unposted_blog_photos)} new photos ready)",
                True, (145, 205, 155),
            )
            self.screen.blit(act, act.get_rect(center=(cx, DISPLAY_H - 58)))

        else:
            photos = self.all_captured_photos
            if photos:
                self.archive_sel = max(0, min(len(photos) - 1, self.archive_sel))
                item = photos[self.archive_sel]
                card = pygame.Surface((240, 195), pygame.SRCALPHA)
                card.fill((238, 232, 220))
                scaled_thumb = pygame.transform.scale(item['thumb'], (216, 148))
                card.blit(scaled_thumb, (12, 12))
                lbl = self.font_tiny.render(f"Photo {self.archive_sel + 1} of {len(photos)}", True, (25, 25, 30))
                card.blit(lbl, (12, 168))
                self.screen.blit(card, (cx - 120, 105))

                h1 = self.font_med.render(item['name'], True, (235, 215, 150))
                self.screen.blit(h1, h1.get_rect(center=(cx, 326)))
                for i, ln in enumerate(self._wrap_text(item['note'], self.font_small, 680)[:3]):
                    s = self.font_small.render(ln, True, (210, 205, 195))
                    self.screen.blit(s, s.get_rect(center=(cx, 362 + i * 24)))
            else:
                t = self.font_small.render("No Polaroids taken yet (Right Click / C in-game).", True, (180, 180, 185))
                self.screen.blit(t, t.get_rect(center=(cx, 220)))

            d_idx = min(len(LORE_LOGS) - 1, self.level_index)
            for i, ln in enumerate(self._wrap_text(LORE_LOGS[d_idx], self.font_tiny, 740)[:4]):
                s = self.font_tiny.render(ln, True, (150, 155, 150))
                self.screen.blit(s, s.get_rect(center=(cx, 455 + i * 20)))

        hint = self.font_tiny.render("1/2/3 or Up/Down: Page    Left/Right: Photo    Esc/N: Close", True, (130, 130, 135))
        self.screen.blit(hint, hint.get_rect(center=(cx, DISPLAY_H - 26)))
        self.screen.blit(self._vignette_surf, (0, 0))

    def _draw_big_map(self):
        grid = self.level.grid
        gh, gw = len(grid), len(grid[0])
        cell = max(6, min((DISPLAY_W - 140) // gw, (DISPLAY_H - 170) // gh))
        mw, mh = gw * cell, gh * cell
        panel_w, panel_h = mw + 40, mh + 84
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((6, 10, 10, 228))
        pygame.draw.rect(panel, (90, 220, 200), (0, 0, panel_w, panel_h), width=2)
        panel.blit(self.font_small.render("HAND-DRAWN EXPEDITION MAP", True, (120, 240, 220)), (20, 10))
        hint = self.font_tiny.render("Tab - close      blue = Exit (needs Blue Key)   green dot = Unphotographed Anomaly", True, (150, 175, 170))
        panel.blit(hint, (panel_w - hint.get_width() - 20, 14))
        mx0, my0 = 20, 50
        for (x, y) in self.level.explored:
            v = grid[y][x]
            r = (mx0 + x * cell, my0 + y * cell, cell, cell)
            if v == EXIT_TILE:
                col = (60, 170, 255)
            elif v == WALL_DOOR and (x, y) not in self.level.opened_doors:
                col = (230, 190, 40)
            elif v == WALL_EMPTY:
                col = (30, 38, 40)
            else:
                col = (112, 118, 130)
            pygame.draw.rect(panel, col, r)
        for an in self.level.anomalies:
            ax, ay = int(an.x), int(an.y)
            if an.is_core and (ax, ay) in self.level.explored and an.photo_id not in self.sector_photos:
                pygame.draw.circle(panel, (80, 230, 130),
                                   (int(mx0 + an.x * cell), int(my0 + an.y * cell)), max(2, cell // 4))
        p = self.player
        pcx, pcy = mx0 + p.x * cell, my0 + p.y * cell
        pygame.draw.circle(panel, (60, 160, 255), (int(pcx), int(pcy)), max(3, cell // 3))
        pygame.draw.line(panel, (60, 160, 255), (int(pcx), int(pcy)),
                         (int(pcx + math.cos(p.angle) * cell * 1.2), int(pcy + math.sin(p.angle) * cell * 1.2)), 2)
        self.screen.blit(panel, ((DISPLAY_W - panel_w) // 2, (DISPLAY_H - panel_h) // 2))

    def _draw_level_intro(self):
        t = self.level_intro_t
        fade = min(1.0, t / 0.5)
        s = pygame.Surface((DISPLAY_W, DISPLAY_H), pygame.SRCALPHA)
        s.fill((0, 0, 0, int(215 * fade) if t < 0.5 else 195))
        self.screen.blit(s, (0, 0))
        txt = self.font_big.render(self.level.name, True, (235, 225, 200))
        txt.set_alpha(int(255 * fade))
        self.screen.blit(txt, txt.get_rect(center=(DISPLAY_W // 2, DISPLAY_H // 2 - 35)))
        hint = SECTOR_HINTS[self.level_index] if self.level_index < len(SECTOR_HINTS) else "Find the exit. Survive."
        for i, line in enumerate(self._wrap_text(hint, self.font_small, 740)):
            sub = self.font_small.render(line, True, (195, 195, 195))
            sub.set_alpha(int(255 * fade))
            self.screen.blit(sub, sub.get_rect(center=(DISPLAY_W // 2, DISPLAY_H // 2 + 25 + i * 26)))
        if t >= 0.6 and int(self.time * 2) % 2 == 0:
            go = self.font_tiny.render("Press ENTER / SPACE to begin", True, (220, 195, 130))
            self.screen.blit(go, go.get_rect(center=(DISPLAY_W // 2, DISPLAY_H // 2 + 135)))

    def _draw_pause(self):
        s = pygame.Surface((DISPLAY_W, DISPLAY_H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 175))
        self.screen.blit(s, (0, 0))
        txt = self.font_big.render("PAUSED", True, (235, 230, 220))
        self.screen.blit(txt, txt.get_rect(center=(DISPLAY_W // 2, DISPLAY_H // 2 - 105)))
        lines = [
            ("resume", "Resume Game [Esc]"),
            ("touch", f"Switch Controls: {'MOBILE TOUCH' if self.touch_controls else 'PC KEYBOARD'} [T]"),
            ("guide", "Controls & Features Guide [H]"),
            ("notebook", "Creator Notebook [N]"),
            ("restart", "Restart Sector [R]"),
            ("settings", "Settings [S]"),
            ("menu", "Main Menu [Q]"),
        ]
        self._pause_rects = []
        for i, (act_id, line) in enumerate(lines):
            sub = self.font_small.render(line, True, (140, 225, 165) if act_id == 'touch' else (205, 205, 205))
            r = sub.get_rect(center=(DISPLAY_W // 2, DISPLAY_H // 2 - 45 + i * 32))
            self._pause_rects.append((r.inflate(28, 8), act_id))
            self.screen.blit(sub, r)

    def _draw_settings(self):
        self.screen.fill((7, 7, 10))
        cx = DISPLAY_W // 2
        title = self.font_big.render("SETTINGS", True, (225, 210, 180))
        self.screen.blit(title, title.get_rect(center=(cx, 44)))

        res_name, _, _ = RES_PRESETS[self.res_index]
        rows = [
            ("Mouse Sensitivity", f"{self.mouse_sens:.4f}"),
            ("Master Volume", f"{int(round(self.master_volume * 100))}%"),
            ("Horror & Ambient Volume", f"{int(round(self.horror_volume * 100))}%"),
            ("Brightness / Gamma", f"{int(round(self.brightness * 100))}%"),
            ("Field of View (FOV)", f"{self.fov_deg}°"),
            ("Graphics Resolution", res_name),
            ("Camera Shake", "OFF" if self.shake_scale <= 0 else f"{int(round(self.shake_scale * 100))}%"),
            ("VHS Scanlines", "ON" if self.vhs_effect else "OFF"),
            ("Viewbob / Hand Bobbing", "ON" if self.head_bob else "OFF"),
            ("Mobile Touch Controls", "ON" if self.touch_controls else "OFF"),
            ("Display Mode", "FULLSCREEN" if self.fullscreen else "WINDOWED"),
        ]

        start_y = 98
        row_h = 42
        self._settings_rects = []
        for i, (label, val_str) in enumerate(rows):
            y = start_y + i * row_h
            self._settings_rects.append((pygame.Rect(170, y - 4, DISPLAY_W - 340, row_h - 4), i))
            active = (i == self.settings_selected)
            l_col = (235, 75, 75) if active else (185, 180, 175)
            v_col = (255, 235, 170) if active else (145, 145, 150)
            prefix = "> " if active else "  "
            lt = self.font_small.render(prefix + label, True, l_col)
            vt = self.font_small.render(f"<  {val_str}  >" if active else val_str, True, v_col)
            self.screen.blit(lt, (190, y))
            self.screen.blit(vt, vt.get_rect(topright=(DISPLAY_W - 190, y)))

        sb_rect = pygame.Rect(24, 20, 96, 30)
        self._settings_back_rect = sb_rect
        pygame.draw.rect(self.screen, (26, 26, 32), sb_rect, border_radius=6)
        pygame.draw.rect(self.screen, (130, 130, 140), sb_rect, 1, border_radius=6)
        sbt = self.font_tiny.render("< BACK", True, (220, 220, 220))
        self.screen.blit(sbt, sbt.get_rect(center=sb_rect.center))
        sub = self.font_tiny.render("Up/Down or Tap Row: Change    Esc: Save & Back", True, (135, 135, 140))
        self.screen.blit(sub, sub.get_rect(center=(cx, DISPLAY_H - 28)))
        self.screen.blit(self._vignette_surf, (0, 0))

    def _draw_menu(self):
        t = self.time
        self.screen.fill((5, 5, 8))
        fw = self._menu_fog.get_width()
        for speed, y, alpha in ((11.0, 130, 130), (-7.0, 340, 95)):
            x = int((t * speed) % fw)
            self._menu_fog.set_alpha(alpha)
            self.screen.blit(self._menu_fog, (-x, y))
            self.screen.blit(self._menu_fog, (fw - x, y))

        cx = DISPLAY_W // 2
        title_y = 165
        name = "V O I D W A L K E R"
        glow = self.font_big.render(name, True, (110, 15, 18))
        glow.set_alpha(_alpha(130 + 60 * math.sin(t * 1.5)))
        self.screen.blit(glow, glow.get_rect(center=(cx + 3, title_y + 3)))
        title = self.font_big.render(name, True, (220, 50, 50))
        self.screen.blit(title, title.get_rect(center=(cx, title_y)))

        sub = self.font_tiny.render("a  K S _ 5 G 1  p r o d u c t i o n", True, (135, 125, 120))
        self.screen.blit(sub, sub.get_rect(center=(cx, title_y + 48)))

        t_rect = pygame.Rect(DISPLAY_W - 210, 18, 190, 30)
        self._menu_touch_rect = t_rect
        pygame.draw.rect(self.screen, (22, 26, 30), t_rect, border_radius=6)
        pygame.draw.rect(self.screen, (110, 220, 150) if self.touch_controls else (110, 115, 125), t_rect, 1, border_radius=6)
        t_lbl = self.font_tiny.render("CONTROLS: MOBILE TOUCH" if self.touch_controls else "CONTROLS: PC KEYBOARD", True, (225, 230, 225))
        self.screen.blit(t_lbl, t_lbl.get_rect(center=t_rect.center))

        items = ["PLAY", "NOTEBOOK", "SETTINGS", "QUIT"]
        self._menu_rects = []
        for i, label in enumerate(items):
            y = 310 + i * 54
            active = (i == self.menu_selected)
            col = (235, 220, 175) if active else (140, 135, 130)
            txt = self.font_med.render(f"—  {label}  —" if active else label, True, col)
            r = txt.get_rect(center=(cx, y))
            self._menu_rects.append((r.inflate(40, 16), i))
            self.screen.blit(txt, r)

        self.screen.blit(self._vignette_surf, (0, 0))

    def _draw_level_select(self):
        self.screen.fill((7, 7, 10))
        title = self.font_big.render("SELECT SITE", True, (225, 210, 180))
        self.screen.blit(title, title.get_rect(center=(DISPLAY_W // 2, 56)))

        cols, rows = 8, 2
        card_w, card_h = 112, 112
        gap = 12
        grid_w = cols * card_w + (cols - 1) * gap
        grid_h = rows * card_h + (rows - 1) * gap
        ox = DISPLAY_W // 2 - grid_w // 2
        oy = 130

        self._level_select_rects = []
        for idx in range(len(LEVELS)):
            col = idx % cols
            row = idx // cols
            x = ox + col * (card_w + gap)
            y = oy + row * (card_h + gap)
            rect = pygame.Rect(x, y, card_w, card_h)
            self._level_select_rects.append((rect, idx))

            active = idx == self.selected_level
            unlocked = idx <= self.highest_unlocked
            base_col = (38, 24, 24) if active else (18, 18, 22)
            border_col = (210, 70, 70) if active else (65, 65, 72) if unlocked else (35, 35, 40)
            pygame.draw.rect(self.screen, base_col, rect, border_radius=6)
            pygame.draw.rect(self.screen, border_col, rect, width=2 if active else 1, border_radius=6)

            num_col = (235, 230, 220) if unlocked else (80, 80, 88)
            num_txt = self.font_med.render(str(idx + 1), True, num_col)
            self.screen.blit(num_txt, num_txt.get_rect(center=(rect.centerx, rect.y + 28)))

            if not unlocked:
                q = self.font_tiny.render("LOCKED", True, (95, 65, 65))
                self.screen.blit(q, q.get_rect(center=(rect.centerx, rect.y + 76)))
                continue

            lines = self._wrap_text(SECTOR_NAMES[idx], self.font_tiny, card_w - 10)
            for li, ln in enumerate(lines[:3]):
                t_ln = self.font_tiny.render(ln, True, (195, 195, 195))
                self.screen.blit(t_ln, t_ln.get_rect(center=(rect.centerx, rect.y + 56 + li * 16)))

        if self.selected_level <= self.highest_unlocked:
            hint_text = f"{SECTOR_NAMES[self.selected_level]}   —   Press ENTER"
            hint_col = (220, 210, 185)
        else:
            hint_text = f"Locked — Clear Site {self.highest_unlocked + 1} first"
            hint_col = (195, 100, 100)
        sub = self.font_small.render(hint_text, True, hint_col)
        self.screen.blit(sub, sub.get_rect(center=(DISPLAY_W // 2, oy + grid_h + 44)))
        m_name, m_nv, _, m_desc = GAME_MODES[self.game_mode]
        nv_note = " (EMF-Jammed Here)" if (m_nv and self.selected_level in EMF_JAMMED_SECTORS) else ""
        m_col = (140, 225, 165) if (m_nv and self.selected_level not in EMF_JAMMED_SECTORS) else (225, 145, 115)
        m_txt = self.font_tiny.render(f"MODE [M]: {m_name} — {m_desc}{nv_note}", True, m_col)
        mr = m_txt.get_rect(center=(DISPLAY_W // 2, oy + grid_h + 74))
        self._lvl_mode_rect = mr.inflate(24, 10)
        pygame.draw.rect(self.screen, (24, 24, 30), self._lvl_mode_rect, border_radius=6)
        pygame.draw.rect(self.screen, m_col, self._lvl_mode_rect, 1, border_radius=6)
        self.screen.blit(m_txt, mr)
        b_rect = pygame.Rect(24, 20, 96, 30)
        self._lvl_back_rect = b_rect
        pygame.draw.rect(self.screen, (26, 26, 32), b_rect, border_radius=6)
        pygame.draw.rect(self.screen, (130, 130, 140), b_rect, 1, border_radius=6)
        bt = self.font_tiny.render("< BACK", True, (220, 220, 220))
        self.screen.blit(bt, bt.get_rect(center=b_rect.center))
        self.screen.blit(self._vignette_surf, (0, 0))

    def _draw_gameover(self):
        s = pygame.Surface((DISPLAY_W, DISPLAY_H), pygame.SRCALPHA)
        s.fill((50, 0, 0, 185))
        self.screen.blit(s, (0, 0))
        txt = self.font_big.render("FOOTAGE LOST", True, (225, 55, 55))
        self.screen.blit(txt, txt.get_rect(center=(DISPLAY_W // 2, DISPLAY_H // 2 - 25)))
        sub = self.font_small.render("ENTER - Retry      ESC - Menu", True, (215, 215, 215))
        self.screen.blit(sub, sub.get_rect(center=(DISPLAY_W // 2, DISPLAY_H // 2 + 35)))

    def _draw_win(self):
        self.screen.fill((6, 10, 8))
        txt = self.font_big.render("THE BROADCAST IS COMPLETE", True, (180, 225, 175))
        self.screen.blit(txt, txt.get_rect(center=(DISPLAY_W // 2, 120)))
        epilogue = [
            f"Followers: {self.followers:,}   •   Blog Views: {self.blog_total_views:,}   •   Book Pre-Orders: {self.book_preorders:,}",
            "",
            "You escaped the final convergence with your camera, blog, and book manuscript intact.",
            "Through your stream, your articles, and your book, 100,000+ minds have witnessed the entity.",
            "Nobody calls you a liar anymore.",
            "",
            "ENTER - Select Site      N - Notebook      ESC - Menu",
        ]
        for i, ln in enumerate(epilogue):
            col = (230, 210, 150) if i == 0 else (200, 205, 200)
            s = self.font_small.render(ln, True, col)
            self.screen.blit(s, s.get_rect(center=(DISPLAY_W // 2, 210 + i * 36)))

    # ------------------------------------------------------------------ input
    def _release_mouse(self):
        pygame.event.set_grab(False)
        pygame.mouse.set_visible(True)

    def _to_menu(self):
        self.state = STATE_MENU
        self._release_mouse()

    def _try_start_sector(self, idx):
        if idx <= self.highest_unlocked:
            self.sounds['ui_ok'].play()
            self.selected_level = idx
            self._launch_sector_with_typing_intro(idx)
        else:
            self.selected_level = idx
            self.sounds['deny'].play()
            self.notice_text = f"Site {idx + 1} is locked."
            self.notice_t = 3.0

    def _activate_menu_item(self, idx):
        self.sounds['ui_ok'].play()
        if idx == 0:
            self.state = STATE_LEVEL_SELECT
            self.selected_level = min(self.selected_level, self.highest_unlocked)
        elif idx == 1:
            self.archive_return_state = STATE_MENU
            self.state = STATE_ARCHIVE
        elif idx == 2:
            self.settings_return_state = STATE_MENU
            self.state = STATE_SETTINGS
        elif idx == 3:
            return False
        return True

    def _adjust_setting(self, direction):
        row = self.settings_selected
        if row == 0:
            self.mouse_sens = max(MOUSE_SENS_MIN, min(MOUSE_SENS_MAX,
                                                      self.mouse_sens + direction * MOUSE_SENS_STEP))
        elif row == 1:
            self.master_volume = max(0.0, min(1.0, round(self.master_volume + direction * VOLUME_STEP, 2)))
            self._apply_volume()
        elif row == 2:
            self.horror_volume = max(0.0, min(1.0, round(self.horror_volume + direction * VOLUME_STEP, 2)))
            self._apply_volume()
        elif row == 3:
            self.brightness = round(max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX,
                                                            self.brightness + direction * BRIGHTNESS_STEP)), 2)
            self.renderer.brightness = self.brightness
        elif row == 4:
            self.fov_deg = max(FOV_DEG_MIN, min(FOV_DEG_MAX, self.fov_deg + direction * FOV_DEG_STEP))
            self._apply_fov()
        elif row == 5:
            self.res_index = (self.res_index + direction) % len(RES_PRESETS)
            _, rw, rh = RES_PRESETS[self.res_index]
            self.renderer.set_resolution(rw, rh)
        elif row == 6:
            self.shake_scale = round(max(0.0, min(1.0, self.shake_scale + direction * 0.1)), 2)
        elif row == 7:
            self.vhs_effect = not self.vhs_effect
        elif row == 8:
            self.head_bob = not self.head_bob
        elif row == 9:
            self.touch_controls = not self.touch_controls
        elif row == 10:
            self.toggle_fullscreen()
            return
        self._save_settings()

    def _handle_keydown(self, event):
        key, st = event.key, self.state
        before_sel = (self.menu_selected, self.selected_level, self.settings_selected, self.archive_sel, self.archive_tab)

        if key == K_F11 or (key in (K_RETURN, K_KP_ENTER) and (event.mod & KMOD_ALT)):
            self.toggle_fullscreen()
            return True

        if st == STATE_SPLASH:
            if key in (K_RETURN, K_KP_ENTER, K_SPACE, K_ESCAPE):
                self.state = STATE_MENU
            return True

        if st == STATE_STORY_INTRO:
            if key in (K_RETURN, K_KP_ENTER, K_SPACE, K_ESCAPE):
                if self.story_intro_chars < len(TYPING_HORROR_INTRO_TEXT):
                    self.story_intro_chars = len(TYPING_HORROR_INTRO_TEXT)
                else:
                    self.story_intro_seen = True
                    self.start_new_game(self.story_intro_target_sector)
            return True

        if st == STATE_PLAYING and self.show_controls_help:
            if key in (K_h, K_F1, K_ESCAPE, K_RETURN, K_SPACE):
                self.show_controls_help = False
                pygame.mouse.get_rel()
            return True

        if key == K_ESCAPE:
            if st == STATE_PLAYING:
                self.state = STATE_PAUSED
                self._release_mouse()
            elif st == STATE_PAUSED:
                self.state = STATE_PLAYING
                pygame.event.set_grab(not self.touch_controls)
                pygame.mouse.set_visible(self.touch_controls)
                pygame.mouse.get_rel()
            elif st == STATE_MENU:
                return False
            elif st == STATE_SETTINGS:
                self.state = self.settings_return_state
            elif st == STATE_ARCHIVE:
                self.state = self.archive_return_state
                if self.state == STATE_PLAYING:
                    pygame.event.set_grab(not self.touch_controls)
                    pygame.mouse.set_visible(self.touch_controls)
                    pygame.mouse.get_rel()
            elif st == STATE_READING:
                self._close_reading()
            else:
                self._to_menu()
            return True

        if st == STATE_LEVEL_INTRO:
            if key in (K_RETURN, K_KP_ENTER, K_SPACE):
                self._begin_level()
        elif st == STATE_READING:
            if key in (K_e, K_RETURN, K_KP_ENTER, K_SPACE):
                self._close_reading()
        elif st == STATE_PLAYING:
            if key == K_TAB:
                self.show_big_map = not self.show_big_map
            elif key in (K_h, K_F1):
                self.show_controls_help = not self.show_controls_help
            elif key == K_t:
                self._toggle_touch_controls()
            elif key in (K_c, K_f):
                self._click_picture()
            elif key == K_v:
                self.viewfinder_on = not self.viewfinder_on
            elif key == K_g:
                self._toggle_night_vision()
            elif key in (K_n, K_l):
                self.archive_return_state = STATE_PLAYING
                self.state = STATE_ARCHIVE
                self._release_mouse()
        elif st == STATE_PAUSED:
            if key == K_q:
                self._to_menu()
            elif key in (K_h, K_F1):
                self.state = STATE_PLAYING
                self.show_controls_help = True
            elif key == K_r:
                self._restart_level()
            elif key == K_s:
                self.settings_return_state = STATE_PAUSED
                self.state = STATE_SETTINGS
            elif key in (K_l, K_n):
                self.archive_return_state = STATE_PAUSED
                self.state = STATE_ARCHIVE
        elif st == STATE_MENU:
            if key in (K_UP, K_w):
                self.menu_selected = (self.menu_selected - 1) % 4
            elif key in (K_DOWN, K_s):
                self.menu_selected = (self.menu_selected + 1) % 4
            elif key in (K_RETURN, K_KP_ENTER, K_SPACE):
                if self._activate_menu_item(self.menu_selected) is False:
                    return False
            elif key in (K_l, K_n):
                self.archive_return_state = STATE_MENU
                self.state = STATE_ARCHIVE
        elif st == STATE_GAMEOVER:
            if key in (K_RETURN, K_KP_ENTER):
                self._restart_level(after_death=True)
        elif st == STATE_WIN:
            if key in (K_RETURN, K_KP_ENTER):
                self.state = STATE_LEVEL_SELECT
            elif key in (K_n, K_l):
                self.archive_return_state = STATE_WIN
                self.state = STATE_ARCHIVE
        elif st == STATE_LEVEL_SELECT:
            cols = 8
            if key in (K_RETURN, K_KP_ENTER):
                self._try_start_sector(self.selected_level)
            elif key in (K_LEFT, K_a):
                self.selected_level = (self.selected_level - 1) % len(LEVELS)
            elif key in (K_RIGHT, K_d):
                self.selected_level = (self.selected_level + 1) % len(LEVELS)
            elif key in (K_UP, K_w):
                nxt = self.selected_level - cols
                self.selected_level = nxt if nxt >= 0 else nxt + len(LEVELS)
            elif key in (K_DOWN, K_s):
                nxt = self.selected_level + cols
                self.selected_level = nxt if nxt < len(LEVELS) else nxt - len(LEVELS)
            elif key == K_m:
                self.game_mode = (self.game_mode + 1) % len(GAME_MODES)
                self.sounds['ui_tick'].play()
        elif st == STATE_SETTINGS:
            n_rows = 11
            if key in (K_UP, K_w):
                self.settings_selected = (self.settings_selected - 1) % n_rows
            elif key in (K_DOWN, K_s):
                self.settings_selected = (self.settings_selected + 1) % n_rows
            elif key in (K_LEFT, K_RIGHT, K_a, K_d):
                self._adjust_setting(-1 if key in (K_LEFT, K_a) else 1)
            elif key in (K_RETURN, K_KP_ENTER, K_SPACE) and self.settings_selected in (7, 8, 9, 10):
                self._adjust_setting(1)
        elif st == STATE_ARCHIVE:
            if key in (K_n, K_l):
                self.state = self.archive_return_state
                if self.state == STATE_PLAYING:
                    pygame.event.set_grab(not self.touch_controls)
                    pygame.mouse.set_visible(self.touch_controls)
                    pygame.mouse.get_rel()
            elif key == K_1:
                self.archive_tab = 0; self.archive_sel = 0
            elif key == K_2:
                self.archive_tab = 1; self.archive_sel = 0
            elif key == K_3:
                self.archive_tab = 2; self.archive_sel = 0
            elif key in (K_UP, K_w):
                self.archive_tab = (self.archive_tab - 1) % 3; self.archive_sel = 0
            elif key in (K_DOWN, K_s):
                self.archive_tab = (self.archive_tab + 1) % 3; self.archive_sel = 0
            elif key in (K_LEFT, K_a):
                self.archive_sel = max(0, self.archive_sel - 1)
            elif key in (K_RIGHT, K_d):
                max_len = len(self.all_captured_photos)
                self.archive_sel = min(max(0, max_len - 1), self.archive_sel + 1)
            elif key in (K_RETURN, K_KP_ENTER, K_SPACE):
                if self.archive_tab == 0:
                    self._boost_livestream()
                elif self.archive_tab == 1:
                    if self.unposted_blog_photos:
                        self._publish_blog_post()
                    if self.uncompiled_book_photos:
                        self._compile_book_chapter()
        if st in (STATE_MENU, STATE_LEVEL_SELECT, STATE_SETTINGS, STATE_ARCHIVE) and \
                before_sel != (self.menu_selected, self.selected_level, self.settings_selected, self.archive_sel, self.archive_tab):
            self.sounds['ui_tick'].play()
        return True

    def _handle_touch_or_click(self, pos, button=1, is_down=True):
        st = self.state
        if not is_down:
            self.touch_move_vec = [0.0, 0.0]
            self.touch_fire_held = False
            return

        if st == STATE_SPLASH:
            self.state = STATE_MENU
            return
        if st == STATE_STORY_INTRO:
            if self.story_intro_chars < len(TYPING_HORROR_INTRO_TEXT):
                self.story_intro_chars = len(TYPING_HORROR_INTRO_TEXT)
            else:
                self.start_new_game(self.story_intro_target_sector)
            return

        if st == STATE_PLAYING and self.show_controls_help:
            self.show_controls_help = False
            return

        if st == STATE_PLAYING and button == 3:
            self._click_picture()
            return

        if st == STATE_PLAYING and button == 1 and self._hud_touch_rect and self._hud_touch_rect.collidepoint(pos):
            self._toggle_touch_controls()
            return

        if st == STATE_PLAYING and self.touch_controls and button == 1:
            # Check virtual joystick
            jx, jy = self.touch_joy_center
            jr = self.touch_joy_radius
            dx, dy = pos[0] - jx, pos[1] - jy
            if math.hypot(dx, dy) <= jr * 1.35:
                self.touch_move_vec = [
                    max(-1.0, min(1.0, dx / float(jr))),
                    max(-1.0, min(1.0, -dy / float(jr))),
                ]
                return
            # Check on-screen touch buttons
            for key_id, (rect, _) in self._touch_buttons.items():
                if rect.collidepoint(pos):
                    if key_id == 'fire':
                        self.touch_fire_held = True
                    elif key_id == 'snap':
                        self._click_picture()
                    elif key_id == 'reload':
                        p = self.player
                        wi = p.weapon_index
                        wdef = p.weapon
                        if p.armed and not p.reloading and p.ammo[wi] < wdef['mag_size'] and p.reserve[wi] > 0:
                            self._start_reload(wdef)
                    elif key_id == 'ir':
                        self._toggle_night_vision()
                    elif key_id == 'notebook':
                        self.archive_return_state = STATE_PLAYING
                        self.state = STATE_ARCHIVE
                    elif key_id == 'map':
                        self.show_big_map = not self.show_big_map
                    elif key_id == 'help':
                        self.show_controls_help = not self.show_controls_help
                    return

        if button != 1:
            return
        if st == STATE_MENU:
            if self._menu_touch_rect and self._menu_touch_rect.collidepoint(pos):
                self._toggle_touch_controls()
                return
            for rect, idx in self._menu_rects:
                if rect.collidepoint(pos):
                    self.menu_selected = idx
                    if self._activate_menu_item(idx) is False:
                        pygame.quit()
                        sys.exit()
                    break
        elif st == STATE_LEVEL_SELECT:
            if self._lvl_back_rect and self._lvl_back_rect.collidepoint(pos):
                self._to_menu()
                return
            if self._lvl_mode_rect and self._lvl_mode_rect.collidepoint(pos):
                self.game_mode = (self.game_mode + 1) % len(GAME_MODES)
                self.sounds['ui_tick'].play()
                return
            for rect, idx in self._level_select_rects:
                if rect.collidepoint(pos):
                    self._try_start_sector(idx)
                    break
        elif st == STATE_LEVEL_INTRO:
            self._begin_level()
        elif st == STATE_READING:
            self._close_reading()
        elif st == STATE_PAUSED:
            for rect, act_id in self._pause_rects:
                if rect.collidepoint(pos):
                    if act_id == 'resume':
                        self.state = STATE_PLAYING
                        pygame.event.set_grab(not self.touch_controls)
                        pygame.mouse.set_visible(self.touch_controls)
                        pygame.mouse.get_rel()
                    elif act_id == 'touch':
                        self._toggle_touch_controls()
                    elif act_id == 'guide':
                        self.state = STATE_PLAYING
                        self.show_controls_help = True
                    elif act_id == 'notebook':
                        self.archive_return_state = STATE_PAUSED
                        self.state = STATE_ARCHIVE
                    elif act_id == 'restart':
                        self._restart_level()
                    elif act_id == 'settings':
                        self.settings_return_state = STATE_PAUSED
                        self.state = STATE_SETTINGS
                    elif act_id == 'menu':
                        self._to_menu()
                    return
        elif st == STATE_SETTINGS:
            if self._settings_back_rect and self._settings_back_rect.collidepoint(pos):
                self.state = self.settings_return_state
                return
            for rect, row_idx in self._settings_rects:
                if rect.collidepoint(pos):
                    self.settings_selected = row_idx
                    direction = -1 if pos[0] < DISPLAY_W // 2 else 1
                    self._adjust_setting(direction)
                    return
        elif st == STATE_ARCHIVE:
            if self._archive_back_rect and self._archive_back_rect.collidepoint(pos):
                self.state = self.archive_return_state
                if self.state == STATE_PLAYING:
                    pygame.event.set_grab(not self.touch_controls)
                    pygame.mouse.set_visible(self.touch_controls)
                    pygame.mouse.get_rel()
                return
            for rect, tab_idx in self._archive_tab_rects:
                if rect.collidepoint(pos):
                    self.archive_tab = tab_idx
                    self.archive_sel = 0
                    self.sounds['ui_tick'].play()
                    return
            if pos[1] > DISPLAY_H - 95:
                if self.archive_tab == 0:
                    self._boost_livestream()
                elif self.archive_tab == 1:
                    if self.unposted_blog_photos:
                        self._publish_blog_post()
                    if self.uncompiled_book_photos:
                        self._compile_book_chapter()
        elif st == STATE_GAMEOVER:
            self._restart_level(after_death=True)
        elif st == STATE_WIN:
            self.state = STATE_LEVEL_SELECT

    # ------------------------------------------------------------------ main loop
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS_CAP) / 1000.0
            dt = min(dt, 0.05)

            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                elif event.type == KEYDOWN:
                    if self._handle_keydown(event) is False:
                        running = False
                elif event.type == MOUSEBUTTONDOWN and event.button in (1, 3):
                    self._handle_touch_or_click(self._to_canvas(event.pos), event.button, is_down=True)
                elif event.type == MOUSEBUTTONUP and event.button == 1:
                    self._handle_touch_or_click(self._to_canvas(event.pos), event.button, is_down=False)
                elif event.type == MOUSEMOTION and self.touch_controls and pygame.mouse.get_pressed()[0]:
                    pos = self._to_canvas(event.pos)
                    jx, jy = self.touch_joy_center
                    jr = self.touch_joy_radius
                    if math.hypot(pos[0] - jx, pos[1] - jy) <= jr * 1.6:
                        self.touch_move_vec = [
                            max(-1.0, min(1.0, (pos[0] - jx) / float(jr))),
                            max(-1.0, min(1.0, -(pos[1] - jy) / float(jr))),
                        ]

            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit()


def main():
    Game(unlock_all=("--unlock-all" in sys.argv)).run()


if __name__ == "__main__":
    main()