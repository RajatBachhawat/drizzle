#!/usr/bin/env python3
"""
drizzle - Binary Rain Pokémon Edition

A Matrix-style 0/1 rain screensaver that periodically fetches a random
Pokémon sprite from pkmn.li, and lets the falling digits "assemble" into
that sprite (in its real colors), hold for a few seconds, then dissolve
back into rain -- before fetching a new random Pokémon and repeating.

This is a merge of two pieces:
  1. The original binary_rain.py Matrix-rain screensaver (curses animation).
  2. The ANSI-block-art -> colored-digit conversion logic from
     ansi_blocks_to_binary.py (adapted here to build a positioned grid
     instead of printing text), used to turn the fetched sprite into a
     set of "target cells" (row, col) -> (digit, color) that the rain
     animation can lock onto.

Run:
    python3 drizzle.py

Controls (while running):
    q           quit
    + / -       speed up / slow down the rain
    ] / [       longer / shorter rain trail
    . / ,       more / less rain density
    c           cycle rain color (used for cells with no sprite color info)
    n           skip ahead to the next phase early (impatience button)
    space       pause / resume
    h           hide / show the status bar

Requires only the Python standard library (curses, urllib).
On Windows, install the 'windows-curses' package first:
    pip install windows-curses
"""

import curses
import random
import re
import threading
import time
import urllib.request
from collections import Counter


# ---------------------------------------------------------------------------
# Rain color palette (used for plain rain and as a fallback when a sprite
# cell has no color info, or the terminal doesn't support 256 colors).
# ---------------------------------------------------------------------------

COLOR_CHOICES = [
    ("green", curses.COLOR_GREEN),
    ("cyan", curses.COLOR_CYAN),
    ("red", curses.COLOR_RED),
    ("yellow", curses.COLOR_YELLOW),
    ("magenta", curses.COLOR_MAGENTA),
    ("white", curses.COLOR_WHITE),
]
RAIN_PAIR_COUNT = len(COLOR_CHOICES) * 3  # pairs 1..RAIN_PAIR_COUNT reserved for rain

# We'll reuse the next 3 pairs for the dynamic rain 256‑color (option 7)
RAIN_256_BASE = RAIN_PAIR_COUNT + 1

# Reference RGB for each rain color choice, used to find the closest match
# to a sprite color (bright/saturated variants, since that's what reads
# well as falling rain digits).
RAIN_COLOR_REFERENCE_RGB = {
    "green": (0, 255, 0),
    "cyan": (0, 255, 255),
    "red": (255, 0, 0),
    "yellow": (255, 255, 0),
    "magenta": (255, 0, 255),
    "white": (255, 255, 255),
}


# ---------------------------------------------------------------------------
# ANSI-art parsing helpers (adapted from ansi_blocks_to_binary.py)
# ---------------------------------------------------------------------------

BLOCK_CHARS = "▄▀█▌▐░▒▓"
SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")


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
    """Fetch a random Pokémon sprite dump. pkmn.li returns ANSI art for a
    curl-like client, so we send a curl-ish User-Agent to make sure we get
    the colored terminal version rather than an HTML page."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        return data.decode("utf-8", errors="replace")
    except Exception:
        return None


def parse_sprite(text):
    """Parse a pkmn.li ANSI dump into a name + a grid of (digit, color256)
    cells, dropping all background color info (foreground only), matching
    ansi_blocks_to_binary.py's approach."""
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
                        j += 2  # background dropped entirely
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
                col += 1  # space or stray char: transparent gap, no cell
            i += 1
        width = max(width, col)

    return {"name": name or "???", "width": width, "height": len(image_lines), "cells": cells}


def build_target(parsed, rows, cols):
    """Center the parsed sprite within the terminal grid (leaving row 0 for
    the status bar) and clip anything that doesn't fit."""
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
    """Return the xterm-256 color index that is the most frequent
    (by cell count) foreground color in the parsed sprite, or None if the
    sprite has fewer than one distinct color."""
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
    # Pre‑init the three pairs for 256‑color rain (they will be re‑used)
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


# Holds the xterm-256 color index to use for rain (None = use COLOR_CHOICES fallback)
_rain_256_color = None
_rain_256_initialized = False  # whether the fixed pairs have been set

def set_rain_256_color(color256):
    """Set the xterm-256 color that plain rain digits should use.
       This re‑uses the fixed three pairs, so it never consumes new pairs."""
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
    """Like attr_for() but uses the true xterm-256 secondary color when available."""
    global _rain_256_color, _rain_256_initialized
    if has_256 and _rain_256_color is not None and _rain_256_initialized:
        # Use the fixed pairs
        if level >= 3:
            return curses.color_pair(RAIN_256_BASE + 2) | curses.A_BOLD   # bold
        elif level == 2:
            return curses.color_pair(RAIN_256_BASE + 2) | curses.A_BOLD   # bold also
        elif level == 1:
            return curses.color_pair(RAIN_256_BASE + 1)                   # normal
        else:
            return curses.color_pair(RAIN_256_BASE) | curses.A_DIM        # dim
    # fallback to the legacy 6-color path
    return attr_for(level, color_index)


class Column:
    __slots__ = ("pos", "speed")

    def __init__(self, rows):
        self.pos = -random.uniform(0, rows)
        self.speed = random.uniform(0.6, 1.4)


# ---------------------------------------------------------------------------
# Phase durations
# ---------------------------------------------------------------------------

RAIN_MIN_DURATION = 3.0        # plain rain shown at least this long between sprites
ASSEMBLE_DURATION = 12.0       # max seconds allotted for the sprite to fully materialize
HOLD_DURATION = 4.0            # seconds the completed sprite is held on screen
DISINTEGRATE_DURATION = 3.0    # max seconds allotted for the sprite to dissolve back into rain

# A pinned cell releases once the natural rain brightness has faded
# past this threshold (used during disintegration).
FADE_BRIGHTNESS_THRESHOLD = 0.35


def decay_for_trail(trail_val):
    trail_val = clamp(trail_val, 1, 10)
    return 0.80 + ((trail_val - 1) / 9) * (0.95 - 0.80)


def spawn_chance_for_density(density_val):
    density_val = clamp(density_val, 1, 10)
    return (density_val / 10) * 0.5 + 0.02


def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)
    setup_colors()

    has_256 = curses.COLORS >= 256
    max_sprite_pairs = max(0, min(200, curses.COLOR_PAIRS - RAIN_PAIR_COUNT - 5 - 3))
    sprite_pair_cache = {}
    next_pair_id = [RAIN_PAIR_COUNT + 4]  # start after the 3 rain‑256 pairs

    # When cache grows too large, clear it to prevent pair exhaustion.
    MAX_SPRITE_CACHE_ENTRIES = max(20, max_sprite_pairs // 2)

    def get_pair_attr(color256):
        """Map an xterm 256-color index to a ready-to-use curses attr,
        falling back to the current rain color if we're out of pairs or
        the terminal can't do 256 colors."""
        if color256 is None or not has_256:
            return curses.color_pair(1) | curses.A_BOLD
        if color256 in sprite_pair_cache:
            return sprite_pair_cache[color256]
        # If cache is too big, clear it and reset the pair counter.
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

    # --- Pokémon cycle state ---
    phase = "rain"          # rain -> assembling -> holding -> disintegrating -> rain
    phase_start_time = time.time()
    current_target = {}     # (r, c) -> (digit, color256)
    pinned = {}             # (r, c) -> (digit, attr) currently locked/displayed
    pending_lock = set()    # target cells not yet locked in (assembling)
    pending_unlock = set()  # pinned cells not yet released (disintegrating)
    extra_drops = {}        # col -> [pos, ...] extra simultaneous drops for pending columns
    sprite_min_row = 0
    sprite_max_row = 0
    sprite_name = None

    # --- Double‑buffered pre‑loading ---
    next_parsed = None          # holds the pre‑loaded parsed sprite (or None)
    preload_thread = None       # the background thread that fills next_parsed
    preload_lock = threading.Lock()   # to safely swap the buffer

    def start_preload():
        """Start a background fetch if none is currently running."""
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
        """Return the pre‑loaded parsed sprite, and start a new background fetch."""
        nonlocal next_parsed, preload_thread
        with preload_lock:
            parsed = next_parsed
            next_parsed = None
            preload_thread = None
        start_preload()
        return parsed

    # Kick off the very first pre‑load immediately
    start_preload()

    def reset_cycle():
        nonlocal phase, phase_start_time, current_target, pinned
        nonlocal pending_lock, pending_unlock, sprite_min_row, sprite_max_row
        nonlocal sprite_name
        phase = "rain"
        phase_start_time = time.time()
        current_target = {}
        pinned = {}
        pending_lock = set()
        pending_unlock = set()
        sprite_min_row = 0
        sprite_max_row = 0
        sprite_name = None
        extra_drops.clear()

    def resize(new_rows, new_cols):
        nonlocal rows, cols, brightness_grid, chars, columns
        rows, cols = max(1, new_rows), max(1, new_cols)
        brightness_grid = [[0.0] * cols for _ in range(rows)]
        chars = [["0"] * cols for _ in range(rows)]
        columns = [Column(rows) for _ in range(cols)]

    last_size = (rows, cols)
    frame_delay = 0.03

    while True:
        # --- input ---
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
            # impatience button: force the current phase to end on the next tick
            phase_start_time = time.time() - 10_000

        # --- handle terminal resize ---
        new_size = stdscr.getmaxyx()
        if new_size != last_size:
            resize(*new_size)
            last_size = new_size
            reset_cycle()
            # Reset pre‑load buffer and sprite cache
            with preload_lock:
                next_parsed = None
                preload_thread = None
            sprite_pair_cache.clear()
            next_pair_id[0] = RAIN_PAIR_COUNT + 4
            start_preload()

        now = time.time()
        elapsed = now - phase_start_time

        if not paused:
            # ---- background rain physics (always running, no per-column boosts) ----
            decay = decay_for_trail(trail_factor)
            for r in range(rows):
                row_b = brightness_grid[r]
                for c in range(cols):
                    if row_b[c] > 0:
                        row_b[c] *= decay
                        if row_b[c] < 0.05:
                            row_b[c] = 0.0

            base_step = 0.06 + (speed_factor / 10) * 0.5
            spawn_chance = spawn_chance_for_density(density_factor)

            for c, col in enumerate(columns):
                prev_floor = int(col.pos // 1)
                col.pos += base_step * col.speed
                new_floor = int(col.pos // 1)

                if new_floor > prev_floor:
                    start = max(prev_floor + 1, 0)
                    end = min(new_floor, rows - 1)
                    for r in range(start, end + 1):
                        chars[r][c] = random.choice("01")
                        brightness_grid[r][c] = 1.0

                if col.pos > rows + 5:
                    if random.random() < spawn_chance:
                        columns[c] = Column(rows)
                    else:
                        col.pos = rows + 5

            # ---- dense absorbing rain for pending columns (assembling only) ----
            if phase == "assembling" and pending_lock:
                pending_cols_set = {c for (_r, c) in pending_lock}
                EXTRA = 4
                # band sweeps bottom-up: eligible rows are >= sprite_min_row and <= allowed_max_row
                # allowed_max_row starts at sprite_max_row and rises to sprite_min_row over time
                _frac = clamp(elapsed / ASSEMBLE_DURATION, 0.0, 1.0)
                _span = max(1, sprite_max_row - sprite_min_row)
                allowed_max_row = sprite_max_row - _frac * _span

                for c in pending_cols_set:
                    if c not in extra_drops:
                        extra_drops[c] = [-random.uniform(0, rows * 0.4) for _ in range(EXTRA)]
                for c in list(extra_drops):
                    if c not in pending_cols_set:
                        del extra_drops[c]

                for c, drops in extra_drops.items():
                    for i, pos in enumerate(drops):
                        prev = int(pos)
                        pos += base_step * random.uniform(0.8, 1.2)
                        new_f = int(pos)
                        absorbed = False
                        if new_f > prev:
                            for r in range(max(prev + 1, 0), min(new_f + 1, rows)):
                                if (r, c) in pending_lock and r >= allowed_max_row:
                                    digit, color256 = current_target[(r, c)]
                                    pinned[(r, c)] = (digit, get_pair_attr(color256))
                                    pending_lock.discard((r, c))
                                    drops[i] = -random.uniform(0, 2)
                                    absorbed = True
                                    break
                                chars[r][c] = random.choice("01")
                                brightness_grid[r][c] = 1.0
                        if not absorbed:
                            drops[i] = pos
                        if pos > rows + 2:
                            drops[i] = -random.uniform(0, 2)
            else:
                extra_drops.clear()

            # ---- Pokémon cycle state machine ----
            if phase == "rain":
                # If we have a pre‑loaded sprite and we've rained for the minimum time,
                # consume it and start assembling.
                if next_parsed is not None and elapsed > RAIN_MIN_DURATION:
                    parsed = consume_preloaded()
                    target = build_target(parsed, rows, cols) if parsed else {}
                    if target:
                        current_target = target
                        rows_present = [r for (r, _c) in current_target.keys()]
                        sprite_min_row = min(rows_present)
                        sprite_max_row = max(rows_present)
                        pending_lock = set(current_target.keys())
                        pinned = {}
                        sprite_name = parsed["name"]
                        # Also set the true xterm-256 secondary color for the rain (reuses fixed pairs)
                        most256 = most_common_sprite_color(parsed)
                        set_rain_256_color(most256)
                        phase = "assembling"
                        phase_start_time = now
                    else:
                        # Sprite didn't fit – discard and wait for the next pre‑load
                        phase_start_time = now

            elif phase == "assembling":
                frac = clamp(elapsed / ASSEMBLE_DURATION, 0.0, 1.0)
                # force-lock anything remaining at timeout
                if frac >= 1.0 and pending_lock:
                    for coord in list(pending_lock):
                        digit, color256 = current_target[coord]
                        pinned[coord] = (digit, get_pair_attr(color256))
                    pending_lock.clear()
                if not pending_lock:
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
                                # hand the freed cell back to normal rain: relight it and
                                # let that column's existing falling physics carry it
                                # further down the screen on the following frames, so it
                                # visibly continues falling instead of just fading in place
                                chars[r][c] = random.choice("01")
                                brightness_grid[r][c] = 1.0
                                columns[c].pos = float(r)
                if not pending_unlock:
                    pinned = {}
                    current_target = {}
                    sprite_name = None
                    phase = "rain"
                    phase_start_time = now

        # --- draw ---
        stdscr.erase()
        for r in range(rows):
            row_b = brightness_grid[r]
            row_c = chars[r]
            for c in range(cols):
                coord = (r, c)
                if coord in pinned:
                    digit, attr = pinned[coord]
                    try:
                        stdscr.addstr(r, c, digit, attr)
                    except curses.error:
                        pass
                    continue
                v = row_b[c]
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
                    stdscr.addstr(r, c, row_c[c], attr_for_rain(level, color_index, has_256))
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
        time.sleep(frame_delay)


if __name__ == "__main__":
    curses.wrapper(main)