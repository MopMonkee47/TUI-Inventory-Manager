# TUI Inventory - Complete Documentation

## Overview

**TUI Inventory** (`inventory.py`) is a single-file, terminal-based inventory
management system written in Python 3. It uses the `curses` library to render a
full text user interface (TUI) in the terminal. It has **zero external
dependencies** -- only Python standard library modules are used.

It is a **unified manager + inventory** app:

1. On launch it shows a **manager** screen listing every inventory folder found
   next to `inventory.py`.
2. Selecting an inventory opens the familiar inventory UI **in-process** (no
   subprocess and no per-folder copy of the app). Data files are repointed at the
   selected folder via `set_data_dir()`, and the inventory shows its own splash
   screen (its name/subtitle/theme) on entry unless `splash_enabled` is off.
3. Inside an inventory, `Esc` returns to the manager and `q` quits the whole app.

Each inventory is simply a subfolder holding its own data and configuration:

```
inventory.py                 # the one app
manager_config.json          # manager branding (name/subtitle/theme)
AboutTemplate                # copied into new inventories as "About"
AboutDefaultTemplate         # copied into new inventories as "AboutDefault"
<Inventory Name>/
    inventory_config.json
    inventory.db, inventory.db.bak, inventory_sales.log
    About, AboutDefault
```

**Run it with:**
```bash
python inventory.py
```
> Must be run in an interactive terminal (TTY). Will not work in piped/non-interactive environments.

---

## Tech Stack

| Component     | Technology                                      |
|---------------|------------------------------------------------|
| Language      | Python 3 (standard library only)                |
| UI            | `curses` (terminal text user interface)         |
| Data Storage  | CSV flat files (`csv.DictReader` / `DictWriter`)|
| Configuration | JSON file (`json` module)                       |
| File Handling | `pathlib.Path`, `shutil`, `os`                  |
| Timestamps    | `datetime` module                               |

---

## File Structure

The entire application lives in a single Python file. At runtime, it creates and manages these files:

| File                        | Purpose                                                    |
|-----------------------------|------------------------------------------------------------|
| `inventory.py`              | The application (manager + inventory)                      |
| `manager_config.json`       | Manager program name, subtitle, and theme color            |
| `AboutTemplate`             | Source for the `About` file of newly created inventories   |
| `AboutDefaultTemplate`      | Source for the `AboutDefault` file of new inventories      |
| `<Inventory>/inventory.db`          | Per-inventory database (CSV format, auto-created)   |
| `<Inventory>/inventory.db.bak`      | Automatic backup (created before every save)        |
| `<Inventory>/inventory_sales.log`   | Per-inventory append-only sales log (CSV)           |
| `<Inventory>/inventory_config.json` | Per-inventory custom fields, columns, theme, settings |
| `<Inventory>/About`, `/AboutDefault`| Per-inventory About text and its restore default    |

---

## Constants & Configuration

Defined at the top of the file:

```
SCRIPT_DIR          → Directory containing inventory.py (the app root)
DATA_DIR            → Currently selected inventory folder (defaults to SCRIPT_DIR)
                      Changed by set_data_dir(folder)
DB_FILE             → DATA_DIR / "inventory.db"
BACKUP_FILE         → DATA_DIR / "inventory.db.bak"
SALES_LOG           → DATA_DIR / "inventory_sales.log"
CONFIG_FILE         → DATA_DIR / "inventory_config.json"
ABOUT_FILE          → DATA_DIR / "About"
ABOUT_DEFAULT_FILE  → DATA_DIR / "AboutDefault"

MANAGER_CONFIG_FILE → SCRIPT_DIR / "manager_config.json"
MGR_PROGRAM_NAME    → Manager title (customizable)
MGR_SUBTITLE        → Manager subtitle (customizable)
MGR_THEME_COLOR     → Manager accent color
INVENTORIES         → List of {'folder': Path, 'name': str} found by scan_inventories()
MGR_SELECTED_IDX    → Highlighted row in the manager list
DEFAULT_CONFIG      → Dict written as inventory_config.json for new inventories

AVAILABLE_COLUMNS   → Dict of all available columns with label, width, align
COLUMNS            → List of currently active columns with key, width, align

CUSTOM_FIELDS = []  → Global list of user-defined custom fields (max 5)
PO_ENABLED     = True → Whether PO numbers are enabled for sales
PROGRAM_NAME   = "TUI Inventory" → Customizable program name (active inventory)
SUBTITLE       = "Track your inventory with ease" → Customizable subtitle (active inventory)
SPLASH_ENABLED = True → Whether the active inventory shows its splash on entry
```

> **Path indirection:** all per-inventory file globals derive from `DATA_DIR`.
> `set_data_dir(folder)` reassigns them, so the entire inventory codebase works
> unchanged against whichever folder the manager selected.

---

## Manager (multi-inventory launcher)

The manager is the app's entry point. It lives in the same file and is entered
through `run()`.

| Function                  | Description                                                                 |
|---------------------------|-----------------------------------------------------------------------------|
| `set_data_dir(folder)`    | Repoint `DATA_DIR`/`DB_FILE`/`SALES_LOG`/`CONFIG_FILE`/`ABOUT_FILE` at a folder. |
| `apply_theme(color)`      | (Re)initialize curses color pairs 1-4 for the given theme color.            |
| `load_manager_config()`   | Load `manager_config.json` into `MGR_*` globals.                            |
| `save_manager_config()`   | Persist `MGR_*` globals to `manager_config.json`.                           |
| `scan_inventories()`      | Find immediate subfolders containing `inventory_config.json`; fill/sort `INVENTORIES`. |
| `draw_manager()`          | Render the manager list and footer.                                         |
| `manager_loop()`          | Manager event loop. Returns the selected folder `Path`, or `None` to quit.  |
| `create_new_inventory()`  | Prompt for a name, create the folder, write `DEFAULT_CONFIG` + About files. |
| `delete_inventory()`      | Confirm, then `shutil.rmtree()` the selected inventory folder.              |
| `cleanup_folders()`       | Remove stale per-folder `inventory.py` / `__pycache__` (data is preserved). |
| `manager_config_menu()`   | Edit manager program name, subtitle, theme, and install command.           |
| `manager_theme_menu()`    | Pick the manager theme color.                                               |
| `manager_about()`         | Static About page for the manager.                                          |
| `install_menu()` / `do_install()` / `check_installed()` | Install a `tui-inventory` command in `~/bin` or add the folder to `PATH`. |

**Manager keys:** `↑↓` navigate, `Enter` open, `a` add, `d` delete, `r` rescan,
`x` remove stale files, `c` settings, `h` about, `q`/`Esc` quit (asks for confirmation).

**Key conventions (app-wide):**
- `Esc` or `b` = back / cancel — works in every submenu and prompt
- `q` = quit the whole application — only from the manager and the inventory
  main list, and always shows a confirmation popup (`y: yes quit` /
  `n: no, I'm not done`; `y` quits, `n` or any other key cancels)
- `q` does nothing inside submenus

---

## Data Model: `Item` Class (lines 66-125)

Each inventory item is represented by an `Item` instance with 8 built-in fields plus up to 5 user-defined custom fields.

### Built-in Fields

| Field         | Type    | Default | Description                                |
|---------------|---------|---------|--------------------------------------------|
| `name`        | `str`   | required| Item name (stripped of whitespace)          |
| `quantity`    | `int`   | `0`     | Current stock count. Note: when adding an item, if `quantity` is not among the configured input fields, it defaults to `1` (so "logbook"-style inventories stay visible with Hide Zero Qty on). |
| `cost`        | `float` | `0.0`   | Unit cost (purchase price)                 |
| `min_value`   | `float` | `0.0`   | Minimum value (hidden field)               |
| `max_value`   | `float` | `0.0`   | Maximum value (hidden field)               |
| `sale`        | `float` | `0.0`   | Sale price per unit                        |
| `location`    | `str`   | `""`    | Storage location                           |
| `description` | `str`   | `""`    | Free-text description                      |
| `custom`      | `dict`  | `{}`    | Key-value pairs for user-defined fields    |

### Computed Properties

| Property           | Logic                                          | Returns              |
|--------------------|------------------------------------------------|----------------------|
| `total_sale_value` | `quantity * sale`                               | `float`              |
| `margin_percent`   | `(sale - cost) / sale * 100` if sale > cost > 0| `float` or `None`    |
| `stock_status`     | Based on quantity vs per-item thresholds (defaults: low<=5, critical<=3) | `"critical"`, `"low"`, or `"ok"` |

### Serialization Methods

- **`to_dict()`** -- Converts item to a flat dictionary (built-in fields + custom fields merged). Used when writing to CSV.
- **`from_dict(cls, d)`** -- Class method that creates an `Item` from a dictionary. Separates known fields from custom fields. Custom field values that look numeric are automatically converted to `float`.

---

## Functions Reference

### Configuration

| Function        | Description                                                        |
|-----------------|--------------------------------------------------------------------|
| `load_config()` | Reads `inventory_config.json`, populates global settings (CUSTOM_FIELDS, THEME_COLOR, COLUMNS, PO_ENABLED, PROGRAM_NAME, SUBTITLE). Silently ignores errors. |
| `save_config()` | Writes current settings to `inventory_config.json` with pretty-print indentation. |

### Persistence

| Function                        | Description                                                                                                    |
|---------------------------------|----------------------------------------------------------------------------------------------------------------|
| `get_all_fieldnames(inventory)` | Returns ordered list of all CSV column names: 8 base fields + sorted custom field keys found across all items. |
| `load_inventory()`              | Reads `inventory.db` CSV file, returns list of `Item` objects. Skips malformed rows silently.                  |
| `safe_save_inventory(inventory)`| Creates a `.bak` backup of existing DB, then writes all items to `inventory.db`. Handles empty inventory.      |
| `load_config()`                 | Loads config from JSON file including custom fields, theme, columns, PO setting, program name, subtitle         |
| `save_config()`                 | Saves config to JSON file                                                 |

**Backup strategy:** Every time inventory is saved, the current `inventory.db` is copied to `inventory.db.bak` first (using `shutil.copy2` which preserves metadata). This provides one level of undo.

### Sales

| Function                                          | Description                                                                                                  |
|---------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| `record_sale(inventory, orig_idx, qty_sold, price_each)` | Core sale logic: validates index & quantity, decrements stock, appends CSV row to sales log, saves inventory. Returns `bool`. |
| `record_sale_ui(stdscr, inventory, orig_idx)`     | Interactive UI for recording a sale. Prompts for quantity and price, shows confirmation, calls `record_sale()`. Supports optional PO number (if enabled). |

**Sales log format** (CSV columns): `timestamp`, `name`, `quantity_sold`, `price_each`, `total`, `remaining_stock`, `po_number`

- Timestamps are ISO 8601 format with seconds precision.
- The log is append-only (opened in `'a'` mode). Header is written only on first creation.
- Confirmation requires pressing `y`, `Y`, or Space.
- PO number is optional and can be enabled/disabled in Display settings.

### Sales History

| Function                    | Description                                                                     |
|-----------------------------|---------------------------------------------------------------------------------|
| `view_sales_history(stdscr)`| Reads entire sales log, reverses it (newest first), displays in a scrollable view. Handles resize events. Includes dotted separator line before controls. |

### Settings / Configuration

| Function             | Description                                                                                      |
|----------------------|--------------------------------------------------------------------------------------------------|
| `config_menu(stdscr, inventory=None)`| Tabbed settings menu with Custom Fields, Theming, and System Settings tabs. |

**Settings Tabs:**
1. **Custom Fields** - Add/delete/edit custom fields (max 5)
2. **Theming** - Theme color, program name, subtitle
3. **System Settings** - Feature toggles, date format, column/input configuration, splash

**Theming Tab Options:**
- Theme color (↑↓ or 1-7): Select color, Enter to apply
- Program Name (↑↓ then Enter, or `n`): Customize the program name displayed in title
- Subtitle (↑↓ then Enter, or `s`): Customize the subtitle shown below the title
- Reset defaults (`r`): Restore name, subtitle, and cyan theme

**System Settings Tab Options (↑↓ + Enter):**
- Show stock alerts - Toggle yellow/red coloring for low/critical stock items
- PO Number - Toggle PO number tracking on/off for sales
- Monetization - Toggle price input when recording sales
- Delete Confirm / Hide Zero Qty / Auto Delete Zero Qty - Behavior toggles
- Sale Option - Toggle sale recording
- Date Format - Switch MM/DD/YYYY <-> DD/MM/YYYY
- Column configuration (inventory, history) and Input Customization
- **Show Splash** - Toggle whether this inventory's splash screen is shown on entry (default On)

**Navigation Controls:**
- ←/→ or h/l: Switch between tabs
- Esc or b: Back to previous screen
- ↑/↓: Navigate options within the tab (Theming wraps through colors + name + subtitle)
- Enter: Select/apply current option
- Number keys (1-7 in Theming): Quick-select a theme color

**Important Implementation Notes:**

1. **Color pair reinitialization:** When changing THEME_COLOR in config_menu, you MUST call `curses.init_pair(1, THEME_COLOR, curses.COLOR_BLACK)` to apply the color change immediately within the settings menu.

2. **Tab selection state:** When switching tabs with ←/→, reset `current_option = 0` to avoid stale selection state.

3. **Enter key handling:** The Enter key handler for tab navigation must come AFTER the selection/apply handler, otherwise it intercepts Enter before the selection code runs. Use separate handlers: `(27, ord('b'))` for back (Esc/b), and `(10, curses.KEY_ENTER, ord(' '))` for selection.

4. **Display toggle alignment:** Use consistent spacing after the colon for all toggle options. Example:
   ```python
   stdscr.addstr(y, 2, f"1. Show stock alerts:  {color_crit_status}")
   stdscr.addstr(y+1, 2, f"2. PO Number:         {po_status}")
   stdscr.addstr(y+2, 2, f"3. Monetization:     {mon_status}")
   ```

**Note:** Stock alert thresholds are now per-item settings. Each item can have its own low stock threshold and critical stock level, configurable in the item detail/edit screen (press Enter on an item, then e to edit, then L for low stock threshold or R for critical stock threshold). Defaults are 5 for low stock and 3 for critical.

**Input cursor positioning:** When prompting for user input with a colon (e.g., "Enter new value: "), the cursor position for `getstr()` should be the starting column plus the length of the prompt string. This ensures the cursor starts after the colon and space, not overwriting the prompt. For example, a prompt starting at column 2 with "Value: " (8 chars) uses position 2 + 8 = 10.

**Adding a custom field** prompts for:
1. **Label** -- Display name (e.g., "Color")
2. **Key** -- Internal storage key (auto-generated from label, e.g., "color")
3. **Type** -- One of: `text`, `number`, `decimal`, `money`, `date`, `list` (defaults to `text` if invalid)
4. **Decimal places** -- (only when type is `decimal`) 0-6, default 2; stored as
   the optional `decimals` key in the field dict. Controls display precision
   everywhere (list columns, details, edit previews) and rounding on save.
   Fields created before this setting existed default to 2 places.
5. **Max character length** -- (text/number/decimal/money) default 60
6. **Options** -- (only when type is `list`) up to 10 choices

**Editing a custom field** (select field, press Enter): `n` edits the label;
for `decimal` fields, `p` changes the decimal places (0-6); for `list` fields,
`a`/`d` add/remove options; Esc/b saves and goes back.

### Column Configuration

| Function                  | Description                                                                                      |
|---------------------------|--------------------------------------------------------------------------------------------------|
| `column_config_menu(stdscr)` | Interactive menu to configure which columns are shown in the main list view. |

**Available columns:** Name, Qty, Cost, Location, Description, Min, Max, Sale (plus any custom fields)

**Column controls:**
- **Arrow keys** - Navigate through columns
- **Enter** or **Space** - Toggle column on/off
- **+/-** - Increase/decrease column width (3-30)
- **a** - Cycle alignment (left → center → right)
- **d** - Reset to defaults
- **q** - Back to settings

**Features:**
- Columns are listed alphabetically (built-in + custom fields)
- Live preview shows what the column layout looks like
- Alignment settings are saved per-column
- Max 5 active columns

### Input & Validation

| Function                            | Description                                                                                     |
|-------------------------------------|-------------------------------------------------------------------------------------------------|
| `validate_inputs(name, qty_str, cost_str)` | Validates name (non-empty), quantity (non-negative integer), cost (non-negative number). Returns list of error strings. |
| `get_input(stdscr, prompt, y, x, max_len, default)` | General-purpose input helper. Displays prompt, shows default value, enables echo mode for input, returns stripped string. |
| `add_item(stdscr, inventory)`       | Full interactive add-item form: prompts for name, quantity, cost, location, description. Validates, creates `Item`, saves. Leaving name blank cancels. |

### Editing

| Function                                        | Description                                                                                    |
|-------------------------------------------------|------------------------------------------------------------------------------------------------|
| `select_field_to_edit(stdscr, item)`            | Shows edit menu with field previews. Returns: `1`-`9` (field choice), `'C'` (custom only), or `None` (cancel). |
| `edit_item(stdscr, inventory, orig_idx)`        | Main edit flow. Shows current values, lets user edit selected field(s). Choice `9` = "All fields" (includes custom). Validates and saves. |
| `edit_custom_fields_only(stdscr, inventory, orig_idx)` | Edits only custom fields for an item. Validates number/money types. Saves immediately. |

**Edit menu options:**
1. Name
2. Quantity
3. Cost
4. Location
5. Description
6. Min Value (hidden field)
7. Max Value (hidden field)
8. Sale Price (hidden field)
9. All fields (edits everything including custom fields)
L. Low stock threshold (per-item)
R. Critical stock threshold (per-item)
C. Custom fields only
0. Cancel

The term "hidden" for fields 6-8 means they are not shown in the main list view -- they are only visible in the detail view and edit screens.

### Delete & View

| Function                                   | Description                                                                                  |
|--------------------------------------------|----------------------------------------------------------------------------------------------|
| `delete_item(stdscr, inventory, orig_idx)` | Confirmation prompt (`y/N`). Removes item from list, saves inventory. Returns `bool`.        |
| `view_details(stdscr, inventory, orig_idx)`| Detail view loop. Shows all fields (including custom fields with type-aware formatting). Sub-actions: `e` edit, `d` delete, `c` config fields, any other key returns. Includes dotted separator line before controls. |

**Custom field display formatting in detail view:**
- `money` type: formatted as `$1,234.56`
- `number` type: formatted with commas (e.g., `1,234`)
- `text` type: displayed as-is

### Search

| Function             | Description                                                        |
|----------------------|--------------------------------------------------------------------|
| `search_mode(stdscr)`| Prompts for search term. Returns the term (empty string clears search). |

Search filtering happens in `draw_menu()` -- it matches the search term (case-insensitive) against `name`, `description`, and `location` fields.

### Main List View: `draw_menu()` (lines 1599+)

This is the core rendering function that draws the main inventory list screen. It:

1. **Filters** items by search term (matches against name, description, location -- case-insensitive)
2. **Sorts** filtered items by the current sort key and direction
3. **Maps** filtered items back to original inventory indices (needed for edit/delete operations)
4. **Renders** the table with configurable columns (from `COLUMNS` config)
5. **Color-codes** rows by stock status:
   - Color pair 3 (red) = critical stock (qty <= 3)
   - Color pair 2 (yellow) = low stock (qty <= 5)
   - Color pair 4 (green) + reverse video = currently selected row
6. **Shows footer** with item count and keyboard shortcuts
7. **Separator line** - Dotted line (`·`) separates controls from content

**Column Configuration:**
- Columns are defined in `COLUMNS` list with `key`, `width`, and `align`
- Can include built-in fields and custom fields (`custom_fieldname`)
- Custom field columns display values from `item.custom` dict
- Each column has independent width (3-30) and alignment (left/center/right)

**Returns:** `(filtered_list, original_indices_list)` -- used by the main loop to map selection to actual inventory positions.

### Terminal Size Check

| Function              | Description                                                  |
|-----------------------|--------------------------------------------------------------|
| `check_size(stdscr)`  | Enforces minimum terminal size of 70x20. Displays resize message if too small. Returns `bool`. |

Many sub-screens also have their own minimum size checks (e.g., config menu needs 50x15, column config needs 50x15).

### Top Level: `run()` and the Inventory Loop: `inventory_main()`

The app entry point is `run()` (wrapped by `curses.wrapper()`). It:

1. Initializes curses colors and sets the manager theme.
2. Shows the splash screen **once** using the manager branding.
3. Loops: show the manager (`manager_loop()`), and if a folder is chosen,
   `set_data_dir(folder)` then run `inventory_main()` for that inventory.
4. Restores the manager theme and returns to the manager when `inventory_main()`
   returns `"back"`; exits when the manager returns `None` or the inventory
   returns `"quit"`.

`inventory_main()` is the former single-inventory `main()`: it loads the active
inventory's config, and — if `splash_enabled` is on for that inventory (default)
— shows the inventory's own splash (its name, subtitle, and theme) before
loading `inventory.db` and running the list view event loop.

**Color pairs (reinitialized per scope by `apply_theme()`):**
| Pair | Foreground | Usage                          |
|------|------------|--------------------------------|
| 1    | Theme color | Headers, titles               |
| 2    | Yellow     | Low stock items (qty <= 5)     |
| 3    | Red        | Critical stock items (qty <= 3)|
| 4    | Green      | Selected row highlight         |

**Theme colors:** The manager theme comes from `manager_config.json`; each
inventory's theme comes from its own `inventory_config.json`.

**State variables:**
- `selected_row_idx` -- Currently highlighted row in the list
- `search_term` -- Active search filter (empty = show all)
- `sort_key` -- Current sort column (`'name'`, `'quantity'`, or `'location'`)
- `sort_directions` -- Dict tracking asc/desc for each sort key (`1` = ascending, `-1` = descending)

**Main event loop** (runs until `q` quits the app or `Esc` returns to the manager):
1. Check terminal size (show resize message if too small)
2. Call `draw_menu()` (or `draw_split_screen()`) to render the list
3. Wait for keypress
4. Handle key:

| Key            | Action                                              |
|----------------|-----------------------------------------------------|
| Up Arrow       | Move selection up                                   |
| Down Arrow     | Move selection down                                 |
| `q`            | Quit the whole application (asks for confirmation)   |
| `Esc`          | Clear active search/filter, else return to manager  |
| `a`            | Add a new item                                      |
| `s`            | Enter search mode                                   |
| `n`            | Sort by name (toggle asc/desc if already sorting by name) |
| `t`            | Sort by quantity (toggle asc/desc)                  |
| `l`            | Sort by location (toggle asc/desc)                  |
| `r`            | Record a sale for selected item                     |
| `h`            | View sales history                                  |
| `c`            | Open settings menu                                  |
| Enter          | View details of selected item                       |
| Resize event   | Clears and redraws the screen                       |

**UI Styling:**
- Horizontal separator lines use Unicode box-drawing character (`─`)
- Dotted separator lines (`·`) separate controls from content in footer areas
- Settings menu uses tabs (Custom Fields, Settings, Display)

### Entry Point

```python
if __name__ == "__main__":
    if not sys.stdin.isatty():
        print("This program must be run in a terminal.")
        sys.exit(1)
    curses.wrapper(run)
```

Checks that stdin is a TTY before launching. `curses.wrapper()` handles terminal initialization and cleanup (restoring terminal state on exit or crash).

---

## Data Flow Diagrams

### Adding an Item
```
User presses 'a'
  → add_item() prompts for: name, quantity, cost, location, description
  → validate_inputs() checks for errors
  → Item() created and appended to inventory list
  → safe_save_inventory() backs up DB, writes all items to CSV
  → Returns to main list
```

### Recording a Sale
```
User presses 'r' on a selected item
  → record_sale_ui() prompts for quantity sold and price each
  → Shows confirmation: "Sell X × ItemName @ $Y = $Z? (y/N)"
  → record_sale() decrements item.quantity
  → Appends transaction row to inventory_sales.log (CSV)
  → safe_save_inventory() saves updated inventory
  → Returns to main list
```

### Editing an Item
```
User presses Enter on item → view_details() → presses 'e'
  → select_field_to_edit() shows menu with current values
  → User picks field(s) to edit (1-8 single, 9=all, C=custom only)
  → edit_item() or edit_custom_fields_only() prompts for new values
  → validate_inputs() checks core fields
  → New Item() created with updated values, replaces old in list
  → safe_save_inventory() saves
```

### Search & Sort
```
Search:
  User presses 's' → search_mode() prompts for term
  → Term stored in main loop state
  → draw_menu() filters items where term appears in name/description/location

Sort:
  User presses 'n'/'t'/'l' → toggles sort direction if same key, else switches key
  → draw_menu() sorts filtered list by key and direction
```

### Column Configuration
```
User presses 'c' (settings) → Display tab → 4 (Column settings)
  → column_config_menu() shows all available columns
  → Arrow keys/j/k to navigate, Enter to toggle on/off
  → +/- to adjust width, 'a' to cycle alignment
  → Live preview shows column layout
  → 'd' resets to defaults, 'q' saves and returns
  → Config saved to inventory_config.json
```

---

## Error Handling Approach

The application uses a defensive coding style throughout:

- **`try/except curses.error`** wraps nearly all `addstr()` calls to handle cases where text would be drawn outside terminal bounds.
- **Bare `except:` blocks** are used in several places (lines 377, 557, etc.) as catch-alls for UI rendering -- not ideal practice but prevents crashes from terminal edge cases.
- **Input validation** uses `validate_inputs()` for core fields, with inline `try/except ValueError` for numeric conversions.
- **File I/O** errors during load are silently skipped (malformed CSV rows are ignored, corrupt config falls back to empty).
- **Terminal resize** is handled at every screen via `curses.KEY_RESIZE` detection and re-rendering.

---

## Limitations & Notes

1. **Single-level backup** -- Only the most recent backup is kept (`.bak` file is overwritten each save).
2. **No concurrent access protection** -- No file locking; not safe if multiple instances run simultaneously.
3. **Max 5 custom fields** -- Limited to prevent UI crowding.
4. **Column width limits** -- Width must be between 3 and 30 characters.

---

## Roadmap

### Planned Features

1. **Date-based filtering in sales history** -- Filter sales by date range instead of just text search. Could use a calendar-style picker or MM/DD/YYYY-MM/DD/YYYY input format.

2. **Low stock report** -- Dedicated view showing only items at or below their per-item stock thresholds. Could include sortable columns, export capability, and color-coded severity levels.
