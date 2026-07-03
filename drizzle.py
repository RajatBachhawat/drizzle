#!/usr/bin/env python3
"""
drizzle - Binary Rain Pokémon Edition

A Matrix-style 0/1 rain screensaver that periodically fetches a random
Pokémon sprite from pkmn.li, and lets the falling digits "assemble" into
that sprite (in its real colors), hold for a few seconds, then dissolve
back into rain -- before fetching a new random Pokémon and repeating.

Run:
    python3 drizzle.py

Controls:
    q           quit
    + / -       speed up / slow down the rain
    ] / [       longer / shorter rain trail
    . / ,       more / less rain density
    c           cycle rain color
    n           skip to next phase
    space       pause / resume
    h           hide / show status bar
"""

import curses
import random
import re
import threading
import time
import urllib.request
from collections import Counter


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COLOR_CHOICES = [
    ("green", curses.COLOR_GREEN),
    ("cyan", curses.COLOR_CYAN),
    ("red", curses.COLOR_RED),
    ("yellow", curses.COLOR_YELLOW),
    ("magenta", curses.COLOR_MAGENTA),
    ("white", curses.COLOR_WHITE),
]
RAIN_PAIR_COUNT = len(COLOR_CHOICES) * 3
RAIN_256_BASE = RAIN_PAIR_COUNT + 1

BLOCK_CHARS = "▄▀█▌▐░▒▓"
SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")

RAIN_MIN_DURATION = 3.0
ASSEMBLE_DURATION = 10.0
HOLD_DURATION = 5.0
DISINTEGRATE_DURATION = 3.0
FADE_BRIGHTNESS_THRESHOLD = 0.35
INITIAL_DROPS_PER_COLUMN = 4
EXTRA_SPAWN_DISTANCE = (2.0, 4.0)          # vertical gap between drops in a sprite column
FRAME_DELAY = 0.03

# ---------------------------------------------------------------------------
# ANSI-art parsing
# ---------------------------------------------------------------------------

def xterm_256_to_rgb(n: int):
    if n < 16:
        basic = [
            (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
            (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
            (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
            (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
        ]
        return basic[n]
    elif n < 232:
        n -= 16
        r = n // 36
        g = (n % 36) // 6
        b = n % 6
        scale = lambda v: 0 if v == 0 else 55 + v * 40
        return (scale(r), scale(g), scale(b))
    else:
        gray = 8 + (n - 232) * 10
        return (gray, gray, gray)

def brightness(rgb):
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def fetch_sprite_text(url="https://pkmn.li/gen3/"):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        return data.decode("utf-8", errors="replace")
    except Exception:
        return None

def parse_sprite(text):
    if not text:
        return None

    name = None
    image_lines = []
    for line in text.splitlines():
        if name is None:
            m = re.search(r"Name:\s*(.+)", line)
            if m:
                name = m.group(1).strip()
        if "\x1b[" in line and any(ch in line for ch in BLOCK_CHARS):
            image_lines.append(line)

    if not image_lines:
        return None

    cells = {}
    width = 0
    for r, line in enumerate(image_lines):
        col = 0
        fg = None
        i = 0
        n = len(line)
        while i < n:
            m = SGR_RE.match(line, i)
            if m:
                params = m.group(1).split(";") if m.group(1) else ["0"]
                j = 0
                while j < len(params):
                    p = params[j]
                    if p == "0" or p == "":
                        fg = None
                    elif p == "38" and j + 2 < len(params) and params[j + 1] == "5":
                        fg = int(params[j + 2])
                        j += 2
                    elif p == "48" and j + 2 < len(params) and params[j + 1] == "5":
                        j += 2
                    j += 1
                i = m.end()
                continue

            ch = line[i]
            if ch in BLOCK_CHARS:
                if fg is not None:
                    b = brightness(xterm_256_to_rgb(fg))
                    digit = "1" if b > 128 else "0"
                    cells[(r, col)] = (digit, fg)
                else:
                    cells[(r, col)] = (random.choice("01"), None)
                col += 1
            else:
                col += 1
            i += 1
        width = max(width, col)

    return {"name": name or "???", "width": width, "height": len(image_lines), "cells": cells}

def build_target(parsed, rows, cols):
    width, height = parsed["width"], parsed["height"]
    usable_rows = max(1, rows - 1)
    offset_r = 1 + max(0, (usable_rows - height) // 2)
    offset_c = max(0, (cols - width) // 2)

    target = {}
    for (r, c), (digit, color256) in parsed["cells"].items():
        tr, tc = offset_r + r, offset_c + c
        if 0 <= tr < rows and 0 <= tc < cols:
            target[(tr, tc)] = (digit, color256)
    return target

def most_common_sprite_color(parsed):
    if not parsed or not parsed.get("cells"):
        return None
    counts = Counter(
        color256 for (_digit, color256) in parsed["cells"].values() if color256 is not None
    )
    ranked = counts.most_common()
    if ranked:
        return ranked[0][0]
    return None


# ---------------------------------------------------------------------------
# curses helpers
# ---------------------------------------------------------------------------

def clamp(value, low, high):
    return max(low, min(high, value))

def setup_colors():
    curses.start_color()
    curses.use_default_colors()
    for color_index, (_, color) in enumerate(COLOR_CHOICES):
        base = color_index * 3
        curses.init_pair(base + 1, color, -1)
        curses.init_pair(base + 2, color, -1)
        curses.init_pair(base + 3, color, -1)
    for i in range(3):
        try:
            curses.init_pair(RAIN_256_BASE + i, curses.COLOR_WHITE, -1)
        except curses.error:
            pass

def attr_for(level, color_index):
    base = color_index * 3
    if level >= 3:
        return curses.color_pair(base + 3) | curses.A_BOLD
    elif level == 2:
        return curses.color_pair(base + 2) | curses.A_BOLD
    elif level == 1:
        return curses.color_pair(base + 1)
    else:
        return curses.color_pair(base + 1) | curses.A_DIM

_rain_256_color = None
_rain_256_initialized = False

def set_rain_256_color(color256):
    global _rain_256_color, _rain_256_initialized
    _rain_256_color = color256
    if color256 is None:
        return
    try:
        for i in range(3):
            curses.init_pair(RAIN_256_BASE + i, color256, -1)
        _rain_256_initialized = True
    except curses.error:
        _rain_256_initialized = False

def attr_for_rain(level, color_index, has_256):
    global _rain_256_color, _rain_256_initialized
    if has_256 and _rain_256_color is not None and _rain_256_initialized:
        if level >= 3:
            return curses.color_pair(RAIN_256_BASE + 2) | curses.A_BOLD
        elif level == 2:
            return curses.color_pair(RAIN_256_BASE + 2) | curses.A_BOLD
        elif level == 1:
            return curses.color_pair(RAIN_256_BASE + 1)
        else:
            return curses.color_pair(RAIN_256_BASE) | curses.A_DIM
    return attr_for(level, color_index)

class Column:
    __slots__ = ("pos", "speed")
    def __init__(self, rows):
        self.pos = -random.uniform(0, rows)
        self.speed = random.uniform(0.6, 1.4)

def decay_for_trail(trail_val):
    trail_val = clamp(trail_val, 1, 10)
    return 0.80 + ((trail_val - 1) / 9) * (0.95 - 0.80)

def spawn_chance_for_density(density_val):
    density_val = clamp(density_val, 1, 10)
    return (density_val / 10) * 0.5 + 0.02


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)
    setup_colors()

    has_256 = curses.COLORS >= 256
    max_sprite_pairs = max(0, min(200, curses.COLOR_PAIRS - RAIN_PAIR_COUNT - 5 - 3))
    sprite_pair_cache = {}
    next_pair_id = [RAIN_PAIR_COUNT + 4]
    MAX_SPRITE_CACHE_ENTRIES = max(20, max_sprite_pairs // 2)

    def get_pair_attr(color256):
        if color256 is None or not has_256:
            return curses.color_pair(1) | curses.A_BOLD
        if color256 in sprite_pair_cache:
            return sprite_pair_cache[color256]
        if len(sprite_pair_cache) >= MAX_SPRITE_CACHE_ENTRIES:
            sprite_pair_cache.clear()
            next_pair_id[0] = RAIN_PAIR_COUNT + 4
        if next_pair_id[0] - RAIN_PAIR_COUNT > max_sprite_pairs:
            return curses.color_pair(1) | curses.A_BOLD
        try:
            curses.init_pair(next_pair_id[0], color256, -1)
            attr = curses.color_pair(next_pair_id[0]) | curses.A_BOLD
            sprite_pair_cache[color256] = attr
            next_pair_id[0] += 1
            return attr
        except curses.error:
            return curses.color_pair(1) | curses.A_BOLD

    speed_factor = 10
    trail_factor = 5
    density_factor = 6
    color_index = 0
    paused = False
    show_status = True

    rows, cols = stdscr.getmaxyx()
    cols = max(1, cols)
    rows = max(1, rows)

    brightness_grid = [[0.0] * cols for _ in range(rows)]
    chars = [["0"] * cols for _ in range(rows)]
    columns = [Column(rows) for _ in range(cols)]

    # State variables
    phase = "rain"
    phase_start_time = time.time()
    current_target = {}
    pinned = {}
    pending_lock = set()
    pending_unlock = set()

    col_rows = {}          # column -> list of rows still pending (bottom to top)
    col_heights = {}       # column -> total rows in sprite
    col_bottom_row = {}    # column -> bottommost row for rain cutoff

    # Sprite column drop lists (only active during assembling)
    sprite_drops = {}      # column -> list of {'pos': float, 'speed': float}
    sprite_distance = {}   # column -> distance traveled by topmost drop

    sprite_min_row = 0
    sprite_max_row = 0
    sprite_name = None

    # Pre-loading thread
    next_parsed = None
    preload_thread = None
    preload_lock = threading.Lock()

    def start_preload():
        nonlocal preload_thread, next_parsed
        with preload_lock:
            if preload_thread is not None and preload_thread.is_alive():
                return
        def worker():
            nonlocal next_parsed
            while True:
                text = fetch_sprite_text()
                parsed = parse_sprite(text) if text else None
                if parsed and parsed.get("cells"):
                    with preload_lock:
                        next_parsed = parsed
                    break
                time.sleep(2.0)
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        with preload_lock:
            preload_thread = t

    def consume_preloaded():
        nonlocal next_parsed, preload_thread
        with preload_lock:
            parsed = next_parsed
            next_parsed = None
            preload_thread = None
        start_preload()
        return parsed

    start_preload()

    def reset_cycle():
        nonlocal phase, phase_start_time, current_target, pinned
        nonlocal pending_lock, pending_unlock, sprite_min_row, sprite_max_row
        nonlocal sprite_name, col_rows, col_heights, col_bottom_row
        nonlocal sprite_drops, sprite_distance
        phase = "rain"
        phase_start_time = time.time()
        current_target = {}
        pinned = {}
        pending_lock = set()
        pending_unlock = set()
        sprite_min_row = 0
        sprite_max_row = 0
        sprite_name = None
        col_rows = {}
        col_heights = {}
        col_bottom_row = {}
        sprite_drops = {}
        sprite_distance = {}

    def resize(new_rows, new_cols):
        nonlocal rows, cols, brightness_grid, chars, columns
        rows, cols = max(1, new_rows), max(1, new_cols)
        brightness_grid = [[0.0] * cols for _ in range(rows)]
        chars = [["0"] * cols for _ in range(rows)]
        columns = [Column(rows) for _ in range(cols)]

    last_size = (rows, cols)

    def init_assembling(target):
        nonlocal col_rows, col_heights, col_bottom_row, sprite_drops, sprite_distance
        heights = {}
        rows_per_col = {}
        for (r, c) in target.keys():
            heights[c] = heights.get(c, 0) + 1
            rows_per_col.setdefault(c, []).append(r)
        for c in rows_per_col:
            rows_per_col[c].sort()
        col_heights = heights
        col_rows = rows_per_col
        col_bottom_row = {c: max(rows) for c, rows in rows_per_col.items()}

        sprite_drops = {}
        sprite_distance = {}
        for c in col_rows:
            sprite_drops[c] = []
            sprite_distance[c] = 0.0
            for i in range(INITIAL_DROPS_PER_COLUMN):
                pos = -random.uniform(0.2, 2.5) * (i + 1)
                speed = random.uniform(0.6, 1.4)
                sprite_drops[c].append({'pos': pos, 'speed': speed})

    def move_drop(drop, col, base_step):
        pos = drop['pos']
        speed = drop['speed']
        prev_floor = int(pos)
        pos += base_step * speed
        new_floor = int(pos)
        if new_floor > prev_floor:
            start = max(prev_floor + 1, 0)
            end = min(new_floor, rows - 1)
            for r in range(start, end + 1):
                chars[r][col] = random.choice("01")
                brightness_grid[r][col] = 1.0
                if (r, col) in pending_lock and col_rows.get(col) and r == col_rows[col][-1]:
                    digit, color256 = current_target[(r, col)]
                    pinned[(r, col)] = (digit, get_pair_attr(color256))
                    pending_lock.discard((r, col))
                    col_rows[col].pop()
        drop['pos'] = pos
        return pos

    def spawn_sprite_drop(col):
        if col not in sprite_drops:
            return
        speed = random.uniform(0.6, 1.4)
        pos = -random.uniform(0, 2.0)
        sprite_drops[col].append({'pos': pos, 'speed': speed})

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    while True:
        # -- input --
        try:
            key = stdscr.getch()
        except curses.error:
            key = -1

        if key in (ord("q"), ord("Q"), 27):
            break
        elif key in (ord("+"), ord("=")):
            speed_factor = clamp(speed_factor + 1, 1, 10)
        elif key in (ord("-"), ord("_")):
            speed_factor = clamp(speed_factor - 1, 1, 10)
        elif key == ord("]"):
            trail_factor = clamp(trail_factor + 1, 1, 10)
        elif key == ord("["):
            trail_factor = clamp(trail_factor - 1, 1, 10)
        elif key == ord("."):
            density_factor = clamp(density_factor + 1, 1, 10)
        elif key == ord(","):
            density_factor = clamp(density_factor - 1, 1, 10)
        elif key == ord(" "):
            paused = not paused
        elif key in (ord("h"), ord("H")):
            show_status = not show_status
        elif key in (ord("n"), ord("N")):
            phase_start_time = time.time() - 10_000

        # -- resize --
        new_size = stdscr.getmaxyx()
        if new_size != last_size:
            resize(*new_size)
            last_size = new_size
            reset_cycle()
            with preload_lock:
                next_parsed = None
                preload_thread = None
            sprite_pair_cache.clear()
            next_pair_id[0] = RAIN_PAIR_COUNT + 4
            start_preload()

        now = time.time()
        elapsed = now - phase_start_time

        if not paused:
            # -- rain physics --
            decay = decay_for_trail(trail_factor)
            for r in range(rows):
                for c in range(cols):
                    if brightness_grid[r][c] > 0:
                        brightness_grid[r][c] *= decay
                        if brightness_grid[r][c] < 0.05:
                            brightness_grid[r][c] = 0.0

            base_step = 0.06 + (speed_factor / 10) * 0.5
            spawn_chance = spawn_chance_for_density(density_factor)

            # -- process columns --
            sprite_active = (phase == "assembling")
            for c, col in enumerate(columns):
                if sprite_active and c in col_heights:
                    # Sprite column: distance‑based multiple drops
                    if c not in sprite_drops:
                        continue
                    drops = sprite_drops[c]
                    for drop in drops[:]:
                        move_drop(drop, c, base_step)
                    sprite_drops[c] = [d for d in drops if d['pos'] < rows + 5]

                    if col_rows.get(c):  # still have pending cells
                        if sprite_drops[c]:
                            top_drop = min(sprite_drops[c], key=lambda d: d['pos'])
                            delta = base_step * top_drop['speed']
                            sprite_distance[c] += delta
                            threshold = random.uniform(*EXTRA_SPAWN_DISTANCE)
                            if sprite_distance[c] >= threshold:
                                spawn_sprite_drop(c)
                                sprite_distance[c] = 0.0
                        else:
                            spawn_sprite_drop(c)
                            sprite_distance[c] = 0.0
                else:
                    # Normal column: single drop, probabilistic reset
                    prev_floor = int(col.pos)
                    col.pos += base_step * col.speed
                    new_floor = int(col.pos)
                    if new_floor > prev_floor:
                        start = max(prev_floor + 1, 0)
                        end = min(new_floor, rows - 1)
                        for r in range(start, end + 1):
                            chars[r][c] = random.choice("01")
                            brightness_grid[r][c] = 1.0
                            if (r, c) in pending_lock and col_rows.get(c) and r == col_rows[c][-1]:
                                digit, color256 = current_target[(r, c)]
                                pinned[(r, c)] = (digit, get_pair_attr(color256))
                                pending_lock.discard((r, c))
                                col_rows[c].pop()
                    if col.pos > rows + 5:
                        if random.random() < spawn_chance:
                            col.pos = -random.uniform(0, rows)
                            col.speed = random.uniform(0.6, 1.4)
                        else:
                            col.pos = rows + 5

            # -- state transitions --
            if phase == "rain":
                if next_parsed is not None and elapsed > RAIN_MIN_DURATION:
                    parsed = consume_preloaded()
                    target = build_target(parsed, rows, cols) if parsed else {}
                    if target:
                        current_target = target
                        rows_present = [r for (r, _c) in target.keys()]
                        sprite_min_row = min(rows_present)
                        sprite_max_row = max(rows_present)
                        pending_lock = set(target.keys())
                        pinned = {}
                        sprite_name = parsed["name"]
                        init_assembling(target)
                        most256 = most_common_sprite_color(parsed)
                        set_rain_256_color(most256)
                        phase = "assembling"
                        phase_start_time = now
                    else:
                        phase_start_time = now

            elif phase == "assembling":
                if elapsed > ASSEMBLE_DURATION and pending_lock:
                    for coord in list(pending_lock):
                        digit, color256 = current_target[coord]
                        pinned[coord] = (digit, get_pair_attr(color256))
                    pending_lock.clear()
                    col_rows.clear()

                if not pending_lock:
                    # All cells locked – prepare to switch to holding
                    # 1) Clear hidden rain below each sprite column's bottom
                    for c in col_heights:
                        bottom = col_bottom_row[c]
                        for r in range(bottom + 1, rows):
                            brightness_grid[r][c] = 0.0
                            chars[r][c] = '0'
                        # 2) Transfer column to normal rain (use topmost drop pos)
                        if c in sprite_drops and sprite_drops[c]:
                            top_drop = min(sprite_drops[c], key=lambda d: d['pos'])
                            columns[c].pos = top_drop['pos']
                            columns[c].speed = top_drop['speed']
                        else:
                            columns[c].pos = -random.uniform(0, rows)
                            columns[c].speed = random.uniform(0.6, 1.4)
                    # 3) Clear sprite data and remove rain cutoff
                    sprite_drops.clear()
                    sprite_distance.clear()
                    col_bottom_row.clear()
                    col_heights.clear()
                    phase = "holding"
                    phase_start_time = now

            elif phase == "holding":
                if elapsed > HOLD_DURATION:
                    pending_unlock = set(pinned.keys())
                    phase = "disintegrating"
                    phase_start_time = now

            elif phase == "disintegrating":
                frac = clamp(elapsed / DISINTEGRATE_DURATION, 0.0, 1.0)
                span = max(1, sprite_max_row - sprite_min_row)
                allowed_min_row = sprite_max_row - frac * span
                if pending_unlock:
                    for coord in list(pending_unlock):
                        r, c = coord
                        naturally_faded = brightness_grid[r][c] < FADE_BRIGHTNESS_THRESHOLD
                        if frac >= 1.0 or (r >= allowed_min_row and naturally_faded):
                            pinned.pop(coord, None)
                            pending_unlock.discard(coord)
                            if 0 <= r < rows and 0 <= c < cols:
                                chars[r][c] = random.choice("01")
                                brightness_grid[r][c] = 1.0
                                columns[c].pos = float(r)
                if not pending_unlock:
                    pinned = {}
                    current_target = {}
                    sprite_name = None
                    phase = "rain"
                    phase_start_time = now

        # -- draw --
        stdscr.erase()
        for r in range(rows):
            for c in range(cols):
                coord = (r, c)
                if coord in pinned:
                    digit, attr = pinned[coord]
                    try:
                        stdscr.addstr(r, c, digit, attr)
                    except curses.error:
                        pass
                    continue

                # During assembling, hide rain below each column's bottom row
                if phase == "assembling" and c in col_bottom_row and r > col_bottom_row[c]:
                    continue

                v = brightness_grid[r][c]
                if v <= 0:
                    continue
                if v > 0.92:
                    level = 3
                elif v > 0.6:
                    level = 2
                elif v > 0.3:
                    level = 1
                else:
                    level = 0
                try:
                    stdscr.addstr(r, c, chars[r][c], attr_for_rain(level, color_index, has_256))
                except curses.error:
                    pass

        if show_status:
            preload_status = "preloaded" if next_parsed is not None else "fetching..."
            phase_label = {
                "rain": f"rain ({preload_status})",
                "assembling": f"materializing {sprite_name}...",
                "holding": f"{sprite_name}",
                "disintegrating": f"{sprite_name} dissolving...",
            }.get(phase, "")
            status = (
                f" [{phase_label}]  speed:{speed_factor:2d} trail:{trail_factor:2d} "
                f"density:{density_factor:2d} "
                f"{'PAUSED' if paused else ''}  "
                f"[q]uit [+/-]speed [\\[/\\]]trail [,/.]density [n]ext [space]pause [h]ide"
            )
            try:
                stdscr.addstr(0, 0, status[:cols], curses.A_REVERSE)
            except curses.error:
                pass

        stdscr.refresh()
        time.sleep(FRAME_DELAY)


if __name__ == "__main__":
    curses.wrapper(main)