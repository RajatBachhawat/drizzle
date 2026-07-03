#!/usr/bin/env python3
"""
drizzle - Binary Rain Pokémon Edition

A Matrix-style 0/1 rain screensaver that periodically fetches a random
Pokémon sprite from pkmn.li, and lets the falling digits "assemble" into
that sprite (in its real colors), hold for a few seconds, then dissolve
back into rain -- before fetching a new random Pokémon and repeating.

Run:
    python3 drizzle.py
    python3 drizzle.py --spot-disappear   # use old disintegration (fade in place)
    python3 drizzle.py --pokemon bulbasaur,ivysaur,venusaur   # specific cycle

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

import argparse
import curses
import random
import re
import threading
import time
import os
import sys
from collections import Counter
import requests


# ---------------------------------------------------------------------------
# Pokémon mapping
# ---------------------------------------------------------------------------

POKEMON_IDS = {
    "bulbasaur":1,"ivysaur":2,"venusaur":3,"charmander":4,"charmeleon":5,
    "charizard":6,"squirtle":7,"wartortle":8,"blastoise":9,"caterpie":10,
    "metapod":11,"butterfree":12,"weedle":13,"kakuna":14,"beedrill":15,
    "pidgey":16,"pidgeotto":17,"pidgeot":18,"rattata":19,"raticate":20,
    "spearow":21,"fearow":22,"ekans":23,"arbok":24,"pikachu":25,"raichu":26,
    "sandshrew":27,"sandslash":28,"nidoran-f":29,"nidorina":30,"nidoqueen":31,
    "nidoran-m":32,"nidorino":33,"nidoking":34,"clefairy":35,"clefable":36,
    "vulpix":37,"ninetales":38,"jigglypuff":39,"wigglytuff":40,"zubat":41,
    "golbat":42,"oddish":43,"gloom":44,"vileplume":45,"paras":46,"parasect":47,
    "venonat":48,"venomoth":49,"diglett":50,"dugtrio":51,"meowth":52,"persian":53,
    "psyduck":54,"golduck":55,"mankey":56,"primeape":57,"growlithe":58,
    "arcanine":59,"poliwag":60,"poliwhirl":61,"poliwrath":62,"abra":63,
    "kadabra":64,"alakazam":65,"machop":66,"machoke":67,"machamp":68,
    "bellsprout":69,"weepinbell":70,"victreebel":71,"tentacool":72,
    "tentacruel":73,"geodude":74,"graveler":75,"golem":76,"ponyta":77,
    "rapidash":78,"slowpoke":79,"slowbro":80,"magnemite":81,"magneton":82,
    "farfetchd":83,"doduo":84,"dodrio":85,"seel":86,"dewgong":87,"grimer":88,
    "muk":89,"shellder":90,"cloyster":91,"gastly":92,"haunter":93,"gengar":94,
    "onix":95,"drowzee":96,"hypno":97,"krabby":98,"kingler":99,"voltorb":100,
    "electrode":101,"exeggcute":102,"exeggutor":103,"cubone":104,"marowak":105,
    "hitmonlee":106,"hitmonchan":107,"lickitung":108,"koffing":109,"weezing":110,
    "rhyhorn":111,"rhydon":112,"chansey":113,"tangela":114,"kangaskhan":115,
    "horsea":116,"seadra":117,"goldeen":118,"seaking":119,"staryu":120,
    "starmie":121,"mr-mime":122,"scyther":123,"jynx":124,"electabuzz":125,
    "magmar":126,"pinsir":127,"tauros":128,"magikarp":129,"gyarados":130,
    "lapras":131,"ditto":132,"eevee":133,"vaporeon":134,"jolteon":135,
    "flareon":136,"porygon":137,"omanyte":138,"omastar":139,"kabuto":140,
    "kabutops":141,"aerodactyl":142,"snorlax":143,"articuno":144,"zapdos":145,
    "moltres":146,"dratini":147,"dragonair":148,"dragonite":149,"mewtwo":150,
    "mew":151,"chikorita":152,"bayleef":153,"meganium":154,"cyndaquil":155,
    "quilava":156,"typhlosion":157,"totodile":158,"croconaw":159,"feraligatr":160,
    "sentret":161,"furret":162,"hoothoot":163,"noctowl":164,"ledyba":165,
    "ledian":166,"spinarak":167,"ariados":168,"crobat":169,"chinchou":170,
    "lanturn":171,"pichu":172,"cleffa":173,"igglybuff":174,"togepi":175,
    "togetic":176,"natu":177,"xatu":178,"mareep":179,"flaaffy":180,
    "ampharos":181,"bellossom":182,"marill":183,"azumarill":184,"sudowoodo":185,
    "politoed":186,"hoppip":187,"skiploom":188,"jumpluff":189,"aipom":190,
    "sunkern":191,"sunflora":192,"yanma":193,"wooper":194,"quagsire":195,
    "espeon":196,"umbreon":197,"murkrow":198,"slowking":199,"misdreavus":200,
    "unown":201,"wobbuffet":202,"girafarig":203,"pineco":204,"forretress":205,
    "dunsparce":206,"gligar":207,"steelix":208,"snubbull":209,"granbull":210,
    "qwilfish":211,"scizor":212,"shuckle":213,"heracross":214,"sneasel":215,
    "teddiursa":216,"ursaring":217,"slugma":218,"magcargo":219,"swinub":220,
    "piloswine":221,"corsola":222,"remoraid":223,"octillery":224,"delibird":225,
    "mantine":226,"skarmory":227,"houndour":228,"houndoom":229,"kingdra":230,
    "phanpy":231,"donphan":232,"porygon2":233,"stantler":234,"smeargle":235,
    "tyrogue":236,"hitmontop":237,"smoochum":238,"elekid":239,"magby":240,
    "miltank":241,"blissey":242,"raikou":243,"entei":244,"suicune":245,
    "larvitar":246,"pupitar":247,"tyranitar":248,"lugia":249,"ho-oh":250,
    "celebi":251,"treecko":252,"grovyle":253,"sceptile":254,"torchic":255,
    "combusken":256,"blaziken":257,"mudkip":258,"marshtomp":259,"swampert":260,
    "poochyena":261,"mightyena":262,"zigzagoon":263,"linoone":264,"wurmple":265,
    "silcoon":266,"beautifly":267,"cascoon":268,"dustox":269,"lotad":270,
    "lombre":271,"ludicolo":272,"seedot":273,"nuzleaf":274,"shiftry":275,
    "taillow":276,"swellow":277,"wingull":278,"pelipper":279,"ralts":280,
    "kirlia":281,"gardevoir":282,"surskit":283,"masquerain":284,"shroomish":285,
    "breloom":286,"slakoth":287,"vigoroth":288,"slaking":289,"nincada":290,
    "ninjask":291,"shedinja":292,"whismur":293,"loudred":294,"exploud":295,
    "makuhita":296,"hariyama":297,"azurill":298,"nosepass":299,"skitty":300,
    "delcatty":301,"sableye":302,"mawile":303,"aron":304,"lairon":305,
    "aggron":306,"meditite":307,"medicham":308,"electrike":309,"manectric":310,
    "plusle":311,"minun":312,"volbeat":313,"illumise":314,"roselia":315,
    "gulpin":316,"swalot":317,"carvanha":318,"sharpedo":319,"wailmer":320,
    "wailord":321,"numel":322,"camerupt":323,"torkoal":324,"spoink":325,
    "grumpig":326,"spinda":327,"trapinch":328,"vibrava":329,"flygon":330,
    "cacnea":331,"cacturne":332,"swablu":333,"altaria":334,"zangoose":335,
    "seviper":336,"lunatone":337,"solrock":338,"barboach":339,"whiscash":340,
    "corphish":341,"crawdaunt":342,"baltoy":343,"claydol":344,"lileep":345,
    "cradily":346,"anorith":347,"armaldo":348,"feebas":349,"milotic":350,
    "castform":351,"kecleon":352,"shuppet":353,"banette":354,"duskull":355,
    "dusclops":356,"tropius":357,"chimecho":358,"absol":359,"wynaut":360,
    "snorunt":361,"glalie":362,"spheal":363,"sealeo":364,"walrein":365,
    "clamperl":366,"huntail":367,"gorebyss":368,"relicanth":369,"luvdisc":370,
    "bagon":371,"shelgon":372,"salamence":373,"beldum":374,"metang":375,
    "metagross":376,"regirock":377,"regice":378,"registeel":379,"latias":380,
    "latios":381,"kyogre":382,"groudon":383,"rayquaza":384,"jirachi":385,
    "deoxys-normal":386
}

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
FADE_BRIGHTNESS_THRESHOLD = 0.35
INITIAL_DROPS_PER_COLUMN = 4
EXTRA_SPAWN_DISTANCE = (2.0, 4.0)          # vertical gap between drops in a sprite column
RELEASE_DISTANCE_RANGE = (1.5, 4.0)        # vertical distance between released pixels (disintegration)
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

# Global timing variable
_last_fetch_duration_ms = None

# Create a persistent requests session for keep-alive and compression
_session = requests.Session()
_session.headers.update({"User-Agent": "curl/8.0"})  # mimic curl
# requests handles gzip/deflate automatically

def fetch_sprite_text(pokemon_id=None, base_url="https://pkmn.li/gen3/"):
    """
    Fetch a sprite from pkmn.li using requests session.
    If pokemon_id is given, fetch that specific Pokémon; otherwise fetch a random one.
    Records the fetch duration in global _last_fetch_duration_ms.
    """
    global _last_fetch_duration_ms
    if pokemon_id is not None:
        url = f"{base_url}{pokemon_id}/"   # trailing slash avoids redirect
    else:
        url = base_url
    start = time.perf_counter()
    try:
        resp = _session.get(url, timeout=3.0)
        resp.raise_for_status()
        text = resp.text  # automatically decodes using charset from headers
        _last_fetch_duration_ms = int((time.perf_counter() - start) * 1000)
        return text
    except Exception:
        _last_fetch_duration_ms = int((time.perf_counter() - start) * 1000)
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

def is_terminal_background_light():
    """Try to detect if the terminal background is light (e.g., white) or dark."""
    colorfg = os.environ.get('COLORFGBG')
    if colorfg:
        parts = colorfg.split(';')
        if len(parts) >= 2:
            try:
                bg = int(parts[1])
                # If bg is a basic color (0-15), check its brightness
                if bg < 16:
                    rgb = xterm_256_to_rgb(bg)
                    return brightness(rgb) > 128
            except ValueError:
                pass
    # Default assumption: dark background (most common)
    return False

def choose_rain_color(parsed, prefer_bright=True, brightness_threshold=128):
    """
    Return a 256‑color index that is visible on the terminal background.
    If prefer_bright is True, pick colors with brightness >= threshold (for dark bg).
    Otherwise pick colors with brightness < threshold (for light bg).
    """
    if not parsed or not parsed.get("cells"):
        return None
    counts = Counter(
        color256 for (_digit, color256) in parsed["cells"].values()
        if color256 is not None
    )
    for color256, _ in counts.most_common():
        rgb = xterm_256_to_rgb(color256)
        if prefer_bright:
            if brightness(rgb) >= brightness_threshold:
                return color256
        else:
            if brightness(rgb) < brightness_threshold:
                return color256
    return None  # fallback to normal color cycling


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

# Global flags
SPOT_DISINTEGRATION = False
POKEMON_CYCLE = []          # list of IDs (ints) if user provided --pokemon
CYCLE_INDEX = 0

def main(stdscr):
    global SPOT_DISINTEGRATION, POKEMON_CYCLE, CYCLE_INDEX
    global _last_fetch_duration_ms

    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)
    setup_colors()

    # Detect terminal background
    background_light = is_terminal_background_light()
    prefer_bright_rain = not background_light  # dark bg → need bright rain

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

    # Disintegration falling drops (new mode)
    falling_drops = {}     # column -> list of {'pos': float, 'speed': float, 'digit': str}
    release_state = {}     # column -> {'idx': int, 'rows': list, 'accum': float, 'threshold': float, 'speed': float}

    sprite_min_row = 0
    sprite_max_row = 0
    sprite_name = None

    # Pre-loading thread (one fetch at a time)
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
            global CYCLE_INDEX
            while True:
                if POKEMON_CYCLE:
                    idx = CYCLE_INDEX
                    CYCLE_INDEX = (CYCLE_INDEX + 1) % len(POKEMON_CYCLE)
                    pokemon_id = POKEMON_CYCLE[idx]
                    text = fetch_sprite_text(pokemon_id)
                else:
                    text = fetch_sprite_text()
                parsed = parse_sprite(text) if text else None
                if parsed and parsed.get("cells"):
                    with preload_lock:
                        next_parsed = parsed
                    break
                time.sleep(2.0)  # retry after failure
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
        start_preload()   # start fetching the next one immediately
        return parsed

    start_preload()

    def reset_cycle():
        nonlocal phase, phase_start_time, current_target, pinned
        nonlocal pending_lock, pending_unlock, sprite_min_row, sprite_max_row
        nonlocal sprite_name, col_rows, col_heights, col_bottom_row
        nonlocal sprite_drops, sprite_distance, falling_drops, release_state
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
        falling_drops = {}
        release_state = {}

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

    def init_disintegration():
        """Prepare release_state for new disintegration mode."""
        nonlocal release_state, falling_drops
        falling_drops.clear()
        release_state.clear()
        # Build rows per column from pinned keys
        rows_per_col = {}
        for (r, c) in pinned.keys():
            rows_per_col.setdefault(c, []).append(r)
        for c in rows_per_col:
            rows_per_col[c].sort()  # ascending -> bottom to top
        for c, rows in rows_per_col.items():
            if rows:
                release_state[c] = {
                    'idx': len(rows) - 1,               # bottom-most
                    'rows': rows,
                    'accum': 0.0,
                    'threshold': random.uniform(*RELEASE_DISTANCE_RANGE),
                    'speed': random.uniform(0.6, 1.4)
                }

    def move_drop(drop, col, base_step):
        pos = drop['pos']
        speed = drop['speed']
        digit = drop.get('digit', random.choice('01'))  # fallback for assembly drops
        prev_floor = int(pos)
        pos += base_step * speed
        new_floor = int(pos)
        if new_floor > prev_floor:
            start = max(prev_floor + 1, 0)
            end = min(new_floor, rows - 1)
            for r in range(start, end + 1):
                chars[r][col] = digit
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
                        rain_color = choose_rain_color(parsed, prefer_bright=prefer_bright_rain)
                        set_rain_256_color(rain_color)
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
                    for c in col_heights:
                        bottom = col_bottom_row[c]
                        for r in range(bottom + 1, rows):
                            brightness_grid[r][c] = 0.0
                            chars[r][c] = '0'
                        if c in sprite_drops and sprite_drops[c]:
                            top_drop = min(sprite_drops[c], key=lambda d: d['pos'])
                            columns[c].pos = top_drop['pos']
                            columns[c].speed = top_drop['speed']
                        else:
                            columns[c].pos = -random.uniform(0, rows)
                            columns[c].speed = random.uniform(0.6, 1.4)
                    sprite_drops.clear()
                    sprite_distance.clear()
                    col_bottom_row.clear()
                    col_heights.clear()
                    phase = "holding"
                    phase_start_time = now

            elif phase == "holding":
                if elapsed > HOLD_DURATION:
                    if SPOT_DISINTEGRATION:
                        pending_unlock = set(pinned.keys())
                    else:
                        init_disintegration()
                    phase = "disintegrating"
                    phase_start_time = now

            elif phase == "disintegrating":
                if SPOT_DISINTEGRATION:
                    frac = clamp(elapsed / 3.0, 0.0, 1.0)
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
                else:
                    # new disintegration (falling pixels)
                    for c, state in list(release_state.items()):
                        if state['idx'] < 0:
                            continue
                        state['accum'] += base_step * state['speed']
                        if state['accum'] >= state['threshold']:
                            row = state['rows'][state['idx']]
                            coord = (row, c)
                            if coord in pinned:
                                digit, _ = pinned.pop(coord)
                                drop_speed = random.uniform(0.6, 1.4)
                                falling_drops.setdefault(c, []).append({
                                    'pos': float(row),
                                    'speed': drop_speed,
                                    'digit': digit
                                })
                            state['idx'] -= 1
                            state['accum'] = 0.0
                            state['threshold'] = random.uniform(*RELEASE_DISTANCE_RANGE)

                    for c, drops in list(falling_drops.items()):
                        for drop in drops[:]:
                            move_drop(drop, c, base_step)
                        falling_drops[c] = [d for d in drops if d['pos'] < rows + 5]
                        if not falling_drops[c]:
                            del falling_drops[c]

                    all_released = all(state['idx'] < 0 for state in release_state.values())
                    all_drops_gone = not falling_drops
                    if all_released and all_drops_gone:
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
            # Build phase label
            phase_label = {
                "rain": f"rain ({preload_status})",
                "assembling": f"materializing {sprite_name}...",
                "holding": f"{sprite_name}",
                "disintegrating": f"{sprite_name} dissolving...",
            }.get(phase, "")
            # Add fetch time if available
            fetch_time_str = f" {_last_fetch_duration_ms}ms" if _last_fetch_duration_ms is not None else ""
            status = (
                f" [{phase_label}]{fetch_time_str}  speed:{speed_factor:2d} trail:{trail_factor:2d} "
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
    parser = argparse.ArgumentParser(description="drizzle - Binary Rain Pokémon Edition")
    parser.add_argument(
        "--spot-disappear",
        action="store_true",
        help="Use spot‑disappear disintegration (fade in place) instead of falling pixels"
    )
    parser.add_argument(
        "--pokemon",
        type=str,
        default="",
        help="Comma‑separated list of Pokémon names to cycle through (e.g., bulbasaur,ivysaur,venusaur)"
    )
    args = parser.parse_args()
    SPOT_DISINTEGRATION = args.spot_disappear

    if args.pokemon:
        names = [name.strip().lower() for name in args.pokemon.split(",") if name.strip()]
        ids = []
        for name in names:
            if name in POKEMON_IDS:
                ids.append(POKEMON_IDS[name])
            else:
                print(f"Error: Unknown Pokémon name '{name}'. Available: {', '.join(POKEMON_IDS.keys())}")
                sys.exit(1)
        POKEMON_CYCLE = ids

    curses.wrapper(main)