# 🖥️ drizzle - Terminal Binary Rain Pokémon Edition

<img width="800" height="450" alt="multi-pkmn-rain-smol" src="https://github.com/user-attachments/assets/479f47ce-ddb1-47fa-92d6-0d8a2070fb2a" />

Turn your command line into a **Matrix‑style** rain of `0`s and `1`s — which periodically assembles into a random Pokémon sprite (colours and all), holds for a few seconds, then dissolves back into the downpour.

Just a fun piece of **terminal eye‑candy** to run in a spare window.

---

## ✨ What it does

- Fetches a random Pokémon sprite from [pkmn.li](https://pkmn.li/gen3/) via ANSI art. Currently fetches Gen 3 National Dex only and also for the forseeable future :\) Nothing beats Gen 3 and you cannot change my mind!
- Parses the coloured blocks into `1`s (bright) and `0`s (dim), using the exact 256‑color codes.
- Displays the sprite as falling digits that “assemble” into it.
- Holds the completed sprite for a few seconds, then dissolves it back into rain.
- Repeats with a new Pokémon — and the **next one is pre‑loaded** in the background, so you never wait.

---

## 🧰 Use cases

- **Ambient background** for a tmux pane, a terminal tab, or a Raspberry Pi on a spare monitor.
- **Focus break** — glance at it for a mental reset during long coding sessions.
- **Just for fun** — because why not?

---

## 🚀 How to Run

```bash
# On Linux/macOS/WSL – Python’s curses is built‑in
python3 drizzle.py

# On Windows – install windows-curses first
pip install windows-curses
python drizzle.py
```

## 🎮 Controls

| Key          | Action |
|--------------|--------|
| `q` / `Q`    | Quit |
| `+` / `=`    | Speed up rain |
| `-` / `_`    | Slow down rain |
| `]`          | Longer trail |
| `[`          | Shorter trail |
| `.`          | More density |
| `,`          | Less density |
| `c`          | Cycle rain colour (fallback) |
| `n` / `N`    | Skip to next phase (impatience button) |
| `Space`      | Pause / resume |
| `h` / `H`    | Toggle status bar |

---

## 🧠 How it works

- A background thread continuously fetches sprites.
- The main loop runs the rain physics and a state machine: `rain → assembling → holding → disintegrating → rain ...`
- Rain takes on the dominant colour of the current sprite (using a fixed set of 3 pairs, so no pair‑leak).

---

## 🛠️ Technical details

- Written in pure Python, using only the standard library (`curses`, `urllib`, `threading`).
- Requires a terminal that supports at least 256 colours (falls back to a 6‑colour palette if not).
- Resizes gracefully when you change the window size.

---

## 🙏 Credits

- Pokémon sprites from **[pkmn.li](https://pkmn.li)** – an awesome ANSI‑art API.
- Inspired by the classic *Matrix* digital rain effect.
- Vibe-coded in ~2 hours for the joy of it.

---

## 📜 License

MIT — use it, break it, improve it.

Enjoy the rain! 🌧️✨
