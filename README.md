# TUI Inventory Manager

Terminal-based inventory management with multi-inventory support.
Written in Python 3 using `curses` — zero external dependencies.

## Features

- **Manager screen** — create, open, and delete multiple inventories in one app.
  Each inventory is simply a folder with its own data and settings (e.g. Gas
  Receipts, a game collection, a workshop stock list).
- **Per-inventory customization** — theme color, program name/subtitle, splash
  screen, which fields are asked when adding an item, up to 5 custom fields
  (text, number, decimal with 0-6 places, money, date, list), and up to 5
  display columns with adjustable width and alignment.
- **Items** — name, quantity, cost, location, description, plus part#, UPC, PO,
  date, min/max/sale price, and per-item low/critical stock thresholds with
  color-coded alerts.
- **Find things fast** — search, column filters, and sorting.
- **Optional sales tracking** — record sales with optional PO numbers, browse a
  scrollable sales history, and configure which columns it shows.
- **Behavior toggles** — hide zero-qty items, auto-delete zero-qty items, delete
  confirmations, MM/DD/YYYY vs DD/MM/YYYY dates, and more.
- **All data stays local** — plain CSV and JSON files you can open in any
  spreadsheet. Automatic `.bak` backup on every save.

## Requirements

- Python 3 (uses only the standard library, including `curses`)
- An interactive terminal (TTY) — it will not run in a piped/non-interactive
  environment

## Quick Start

```bash
git clone https://github.com/MopMonkee47/TUI-Inventory-Manager.git
cd TUI-Inventory-Manager
python3 inventory.py
```

Optional: in the manager, press `c` (Settings) → Install command to create a
`tui-inventory` launcher in `~/bin`.

## How It Works

On launch, the manager lists every inventory folder found next to
`inventory.py`. Selecting one opens that inventory in-process — no separate app
copies, no subprocesses:

```
inventory.py                 # the one app
manager_config.json          # manager branding (created on first run)
AboutTemplate                # copied into new inventories as "About"
AboutDefaultTemplate         # copied into new inventories as "AboutDefault"
<Inventory Name>/
    inventory_config.json    # fields, columns, theme, settings
    inventory.db             # your items (CSV)
    inventory.db.bak         # automatic backup
    inventory_sales.log      # sales history (CSV)
    About, AboutDefault      # editable About text + its default
```

One folder = one inventory. Back up or copy a folder to back up or move an
entire inventory.

## Controls

**Key conventions**

- `Esc` or `b` — back / cancel, works in every submenu
- `q` — quit the whole app, only from the manager or the inventory list, and
  always asks for confirmation first

**Manager**

| Key | Action |
|-----|--------|
| `↑` `↓` | Navigate |
| `Enter` | Open selected inventory |
| `a` | Add a new inventory |
| `d` | Delete selected inventory |
| `r` | Rescan folders |
| `x` | Remove stale files from inventory folders |
| `c` | Manager settings |
| `h` | About |
| `q` / `Esc` | Quit (with confirmation) |

**Inventory list**

| Key | Action |
|-----|--------|
| `↑` `↓` | Navigate |
| `Enter` | Item details |
| `a` | Add item |
| `e` | Edit item |
| `d` | Delete item |
| `s` | Search |
| `f` | Filter by column |
| `n` / `t` / `l` | Sort by name / quantity / location |
| `r` | Record a sale |
| `h` | Sales history |
| `c` | Settings |
| `J` / `K`, PgUp/PgDn | Page down / up |
| `Ctrl+V` | Toggle split-screen view |
| `Esc` | Clear search/filter, else back to manager |
| `q` | Quit (with confirmation) |

## Customization

Settings (`c`) has tabs for **Custom Fields** (labels, types, decimal places),
**Theming** (color, program name, subtitle), and **System Settings** (feature
toggles, date format, column configuration, input customization, splash
screen). Changes save per-inventory.

## Data Files

| File | Purpose |
|------|---------|
| `inventory.db` | Items (CSV, auto-created) |
| `inventory.db.bak` | Backup, written before every save |
| `inventory_sales.log` | Append-only sales log (CSV) |
| `inventory_config.json` | Custom fields, columns, theme, settings |
| `manager_config.json` | Manager name, subtitle, theme |

All files are local to your machine and are gitignored by this repository.

## Documentation

See [DOCUMENTATION.md](DOCUMENTATION.md) for the full reference — data model,
every function, settings, and data-flow diagrams.

## License

Free to use, modify, and share. No formal license is applied.
