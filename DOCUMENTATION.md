# Weeda Inventory - Complete Documentation

## Overview

**TUI Inventory** (`inventoryV036.py`) is a single-file, terminal-based inventory management system written in Python 3. It uses the `curses` library to render a full text user interface (TUI) in the terminal. It has **zero external dependencies** -- only Python standard library modules are used.

**Run it with:**
```bash
python inventoryV036.py
```
> Must be run in an interactive terminal (TTY). Will not work in piped/non-interactive environments.

---

## Tech Stack

| Component     | Technology                                      |
|---------------|-------------------------------------------------|
| Language      | Python 3 (standard library only)                |
| UI            | `curses` (terminal text user interface)         |
| Data Storage  | CSV flat files (`csv.DictReader` / `DictWriter`)|
| Configuration | JSON file (`json` module)                       |
| File Handling | `pathlib.Path`, `shutil`, `os`                  |
| Timestamps    | `datetime` module                               |

---

## File Structure

The entire application lives in a single Python file. At runtime, it creates and manages these data files in the same directory as the script:

| File                        | Purpose                                                    |
|-----------------------------|------------------------------------------------------------|
| `inventoryV036.py`          | The application (1200 lines)                               |
| `inventory.db`              | Main inventory database (CSV format, auto-created)         |
| `inventory.db.bak`          | Automatic backup of inventory (created before every save)  |
| `inventory_sales.log`       | Append-only sales transaction log (CSV format)             |
| `inventory_config.json`     | Custom field definitions (JSON format)                     |

---

## Constants & Configuration

Defined at the top of the file (lines 23-40):

```
SCRIPT_DIR          → Directory containing the script (all data files stored here)
DB_FILE             → "inventory.db"
BACKUP_FILE         → "inventory.db.bak"
SALES_LOG           → "inventory_sales.log"
CONFIG_FILE         → "inventory_config.json"

NAME_W      = 24    → Column width for item names in the list view
QTY_W       = 6     → Column width for quantity
PRICE_W     = 12    → Column width for price/cost
LOCATION_W  = 10    → Column width for location

LOW_STOCK_THRESHOLD = 5   → Items with qty <= 5 show yellow
CRITICAL_STOCK      = 3   → Items with qty <= 3 show red

CUSTOM_FIELDS = []  → Global list of user-defined custom fields (max 5)
```

---

## Data Model: `Item` Class (lines 66-125)

Each inventory item is represented by an `Item` instance with 8 built-in fields plus up to 5 user-defined custom fields.

### Built-in Fields

| Field         | Type    | Default | Description                                |
|---------------|---------|---------|--------------------------------------------|
| `name`        | `str`   | required| Item name (stripped of whitespace)          |
| `quantity`    | `int`   | `0`     | Current stock count                        |
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
| `stock_status`     | Based on quantity vs thresholds                 | `"critical"`, `"low"`, or `"ok"` |

### Serialization Methods

- **`to_dict()`** -- Converts item to a flat dictionary (built-in fields + custom fields merged). Used when writing to CSV.
- **`from_dict(cls, d)`** -- Class method that creates an `Item` from a dictionary. Separates known fields from custom fields. Custom field values that look numeric are automatically converted to `float`.

---

## Functions Reference

### Configuration (lines 46-60)

| Function        | Description                                                        |
|-----------------|--------------------------------------------------------------------|
| `load_config()` | Reads `inventory_config.json`, populates global `CUSTOM_FIELDS` list (max 5 entries). Silently ignores errors. |
| `save_config()` | Writes current `CUSTOM_FIELDS` to `inventory_config.json` with pretty-print indentation. |

### Persistence (lines 131-171)

| Function                        | Description                                                                                                    |
|---------------------------------|----------------------------------------------------------------------------------------------------------------|
| `get_all_fieldnames(inventory)` | Returns ordered list of all CSV column names: 8 base fields + sorted custom field keys found across all items. |
| `load_inventory()`              | Reads `inventory.db` CSV file, returns list of `Item` objects. Skips malformed rows silently.                  |
| `safe_save_inventory(inventory)`| Creates a `.bak` backup of existing DB, then writes all items to `inventory.db`. Handles empty inventory.      |

**Backup strategy:** Every time inventory is saved, the current `inventory.db` is copied to `inventory.db.bak` first (using `shutil.copy2` which preserves metadata). This provides one level of undo.

### Sales (lines 177-262)

| Function                                          | Description                                                                                                  |
|---------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| `record_sale(inventory, orig_idx, qty_sold, price_each)` | Core sale logic: validates index & quantity, decrements stock, appends CSV row to sales log, saves inventory. Returns `bool`. |
| `record_sale_ui(stdscr, inventory, orig_idx)`     | Interactive UI for recording a sale. Prompts for quantity and price, shows confirmation, calls `record_sale()`. |

**Sales log format** (CSV columns): `timestamp`, `name`, `quantity_sold`, `price_each`, `total`, `remaining_stock`

- Timestamps are ISO 8601 format with seconds precision.
- The log is append-only (opened in `'a'` mode). Header is written only on first creation.
- Confirmation requires pressing `y`, `Y`, or Space.

### Sales History (lines 268-341)

| Function                    | Description                                                                     |
|-----------------------------|---------------------------------------------------------------------------------|
| `view_sales_history(stdscr)`| Reads entire sales log, reverses it (newest first), displays in a scrollable view. Handles resize events. |

### Custom Fields Configuration (lines 347-455)

| Function             | Description                                                                                      |
|----------------------|--------------------------------------------------------------------------------------------------|
| `config_menu(stdscr)`| Interactive menu to manage custom fields. Supports: `a` to add a field, `d#` to delete by index, `q` to quit. |

**Adding a custom field** prompts for:
1. **Label** -- Display name (e.g., "Color")
2. **Key** -- Internal storage key (auto-generated from label, e.g., "color")
3. **Type** -- One of: `text`, `number`, `money` (defaults to `text` if invalid)

Custom fields are saved immediately to `inventory_config.json`.

### Input & Validation (lines 461-519)

| Function                            | Description                                                                                     |
|-------------------------------------|-------------------------------------------------------------------------------------------------|
| `validate_inputs(name, qty_str, cost_str)` | Validates name (non-empty), quantity (non-negative integer), cost (non-negative number). Returns list of error strings. |
| `get_input(stdscr, prompt, y, x, max_len, default)` | General-purpose input helper. Displays prompt, shows default value, enables echo mode for input, returns stripped string. |
| `add_item(stdscr, inventory)`       | Full interactive add-item form: prompts for name, quantity, cost, location, description. Validates, creates `Item`, saves. Leaving name blank cancels. |

### Editing (lines 525-923)

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
C. Custom fields only
0. Cancel

The term "hidden" for fields 6-8 means they are not shown in the main list view -- they are only visible in the detail view and edit screens.

### Delete & View (lines 925-995)

| Function                                   | Description                                                                                  |
|--------------------------------------------|----------------------------------------------------------------------------------------------|
| `delete_item(stdscr, inventory, orig_idx)` | Confirmation prompt (`y/N`). Removes item from list, saves inventory. Returns `bool`.        |
| `view_details(stdscr, inventory, orig_idx)`| Detail view loop. Shows all fields (including custom fields with type-aware formatting). Sub-actions: `e` edit, `d` delete, `c` config fields, any other key returns. |

**Custom field display formatting in detail view:**
- `money` type: formatted as `$1,234.56`
- `number` type: formatted with commas (e.g., `1,234`)
- `text` type: displayed as-is

### Search (lines 997-1001)

| Function             | Description                                                        |
|----------------------|--------------------------------------------------------------------|
| `search_mode(stdscr)`| Prompts for search term. Returns the term (empty string clears search). |

Search filtering happens in `draw_menu()` -- it matches the search term (case-insensitive) against `name`, `description`, and `location` fields.

### Main List View: `draw_menu()` (lines 1003-1075)

This is the core rendering function that draws the main inventory list screen. It:

1. **Filters** items by search term (matches against name, description, location -- case-insensitive)
2. **Sorts** filtered items by the current sort key and direction
3. **Maps** filtered items back to original inventory indices (needed for edit/delete operations)
4. **Renders** the table with columns: Name, Qty, Cost, Location, Description
5. **Color-codes** rows by stock status:
   - Color pair 3 (red) = critical stock (qty <= 3)
   - Color pair 2 (yellow) = low stock (qty <= 5)
   - Color pair 4 (green) + reverse video = currently selected row
6. **Shows footer** with item count, low-stock count, and keyboard shortcuts

**Returns:** `(filtered_list, original_indices_list)` -- used by the main loop to map selection to actual inventory positions.

### Terminal Size Check (lines 1080-1098)

| Function              | Description                                                  |
|-----------------------|--------------------------------------------------------------|
| `check_size(stdscr)`  | Enforces minimum terminal size of 70x20. Displays resize message if too small. Returns `bool`. |

Many sub-screens also have their own minimum size checks (e.g., config menu needs 50x12, edit needs 60x18).

### Main Loop: `main()` (lines 1104-1194)

The application entry point (wrapped by `curses.wrapper()`). Sets up:

**Color pairs:**
| Pair | Foreground | Usage                          |
|------|------------|--------------------------------|
| 1    | Cyan       | Headers, titles                |
| 2    | Yellow     | Low stock items (qty <= 5)     |
| 3    | Red        | Critical stock items (qty <= 3)|
| 4    | Green      | Selected row highlight         |

**State variables:**
- `selected_row_idx` -- Currently highlighted row in the list
- `search_term` -- Active search filter (empty = show all)
- `sort_key` -- Current sort column (`'name'`, `'quantity'`, or `'location'`)
- `sort_directions` -- Dict tracking asc/desc for each sort key (`1` = ascending, `-1` = descending)

**Main event loop** (runs until `q` is pressed):
1. Check terminal size (show resize message if too small)
2. Call `draw_menu()` to render the list
3. Wait for keypress
4. Handle key:

| Key            | Action                                              |
|----------------|-----------------------------------------------------|
| Up Arrow       | Move selection up                                   |
| Down Arrow     | Move selection down                                 |
| `q`            | Quit the application                                |
| `a`            | Add a new item                                      |
| `s`            | Enter search mode                                   |
| `n`            | Sort by name (toggle asc/desc if already sorting by name) |
| `t`            | Sort by quantity (toggle asc/desc)                  |
| `l`            | Sort by location (toggle asc/desc)                  |
| `r`            | Record a sale for selected item                     |
| `h`            | View sales history                                  |
| `c`            | Open custom fields configuration                    |
| Enter          | View details of selected item                       |
| Resize event   | Clears and redraws the screen                       |

### Entry Point (lines 1196-1200)

```python
if __name__ == "__main__":
    if not sys.stdin.isatty():
        print("This program must be run in a terminal.")
        sys.exit(1)
    curses.wrapper(main)
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

1. **No scrolling in the main list** -- Items that don't fit on screen are simply not shown (the list is truncated at `h - 3` rows).
2. **No pagination in sales history** -- Only shows as many sales as fit on screen.
3. **Linear search for original indices** -- `draw_menu()` uses `inventory.index(item)` which is O(n) per item, making it O(n^2) overall. Fine for small inventories but would be slow with thousands of items.
4. **Single-level backup** -- Only the most recent backup is kept (`.bak` file is overwritten each save).
5. **No concurrent access protection** -- No file locking; not safe if multiple instances run simultaneously.
6. **The `Zone.Identifier` file** alongside the script is a Windows NTFS metadata artifact indicating the file was downloaded from the internet.
7. **Version `V036`** in the filename suggests this is the 36th iteration of active development.
