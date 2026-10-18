# inventory_tracker.py
#
# Terminal-based inventory manager using curses
# Features:
#   - Add, edit, delete items
#   - Record sales (reduces quantity, logs to separate file)
#   - View recent sales history
#   - Search by name/desc/location
#   - Sort by name / quantity / location (toggle asc/desc with repeated key)
#   - Low/critical stock color highlighting
#   - Persistent CSV storage + backup
#   - Up to 5 custom fields (configurable via 'c', edited via "9. All fields")

import curses
import os
import sys
import shutil
import csv
import json
from pathlib import Path
from datetime import datetime

# Paths
# SCRIPT_DIR is the app root (where this script lives). Per-inventory data files
# live in DATA_DIR, which is repointed by set_data_dir() when an inventory is
# selected from the manager.
SCRIPT_DIR  = Path(__file__).parent.resolve()
DATA_DIR    = SCRIPT_DIR
DB_FILE     = DATA_DIR / "inventory.db"
BACKUP_FILE = DATA_DIR / "inventory.db.bak"
SALES_LOG   = DATA_DIR / "inventory_sales.log"
CONFIG_FILE = DATA_DIR / "inventory_config.json"
ABOUT_FILE  = DATA_DIR / "About"
ABOUT_DEFAULT_FILE = DATA_DIR / "AboutDefault"

MANAGER_CONFIG_FILE = SCRIPT_DIR / "manager_config.json"

def set_data_dir(folder):
    """Repoint all inventory data-file paths at a chosen inventory folder."""
    global DATA_DIR, DB_FILE, BACKUP_FILE, SALES_LOG, CONFIG_FILE, ABOUT_FILE, ABOUT_DEFAULT_FILE
    DATA_DIR    = Path(folder).resolve()
    DB_FILE     = DATA_DIR / "inventory.db"
    BACKUP_FILE = DATA_DIR / "inventory.db.bak"
    SALES_LOG   = DATA_DIR / "inventory_sales.log"
    CONFIG_FILE = DATA_DIR / "inventory_config.json"
    ABOUT_FILE  = DATA_DIR / "About"
    ABOUT_DEFAULT_FILE = DATA_DIR / "AboutDefault"

# Display settings
NAME_W     = 24
QTY_W      = 6
PRICE_W    = 12
LOCATION_W = 10

AVAILABLE_COLUMNS = {
    'name': {'label': 'Name', 'width': 24, 'align': 'left'},
    'quantity': {'label': 'Qty', 'width': 6, 'align': 'right'},
    'cost': {'label': 'Cost', 'width': 12, 'align': 'center'},
    'location': {'label': 'Location', 'width': 10, 'align': 'left'},
    'description': {'label': 'Description', 'width': 20, 'align': 'left'},
    'min_value': {'label': 'Min', 'width': 10, 'align': 'right'},
    'max_value': {'label': 'Max', 'width': 10, 'align': 'right'},
    'sale': {'label': 'Sale Price', 'width': 12, 'align': 'center'},
    'timestamp': {'label': 'Time Stamp', 'width': 18, 'align': 'left'},
    'part_number': {'label': 'Part#', 'width': 14, 'align': 'left'},
    'upc': {'label': 'UPC', 'width': 14, 'align': 'left'},
    'po': {'label': 'PO', 'width': 14, 'align': 'left'},
    'date': {'label': 'Date', 'width': 12, 'align': 'left'},
}

FILTERABLE_COLUMNS = ['location', 'po', 'date']

COLUMNS = [
    {'key': 'name', 'width': 24, 'align': 'left'},
    {'key': 'quantity', 'width': 6, 'align': 'right'},
    {'key': 'cost', 'width': 12, 'align': 'center'},
    {'key': 'location', 'width': 10, 'align': 'left'},
    {'key': 'description', 'width': 20, 'align': 'left'},
]

HISTORY_COLUMNS = [
    {'key': 'timestamp', 'width': 10, 'align': 'left'},
    {'key': 'name', 'width': 20, 'align': 'left'},
    {'key': 'quantity', 'width': 4, 'align': 'right'},
    {'key': 'price', 'width': 8, 'align': 'right'},
    {'key': 'total', 'width': 10, 'align': 'right'},
    {'key': 'po', 'width': 12, 'align': 'left'},
]

AVAILABLE_HISTORY_COLUMNS = {
    'timestamp': {'label': 'Date', 'width': 10, 'align': 'left'},
    'name': {'label': 'Name', 'width': 20, 'align': 'left'},
    'quantity': {'label': 'Qty', 'width': 4, 'align': 'right'},
    'price': {'label': 'Price', 'width': 8, 'align': 'right'},
    'total': {'label': 'Total', 'width': 10, 'align': 'right'},
    'po': {'label': 'PO', 'width': 12, 'align': 'left'},
}

PO_ENABLED = True
MONETIZATION_ENABLED = True
COLOR_CRITICAL_ENABLED = True
DELETE_CONFIRM_ENABLED = True
HIDE_ZERO_QTY_ENABLED = True
AUTO_DELETE_ZERO_ENABLED = False
SALE_ENABLED = True
DATE_FORMAT = "%m/%d/%Y"
SPLASH_ENABLED = True

# Global custom fields
CUSTOM_FIELDS = []  # [{'name':str, 'label':str, 'type':'text'|'number'|'decimal'|'money'|'date'|'list', 'decimals':int?}, ...]

# Input customization - which fields to prompt for when adding an item
INPUT_FIELDS = ['name', 'quantity', 'description', 'location', 'cost']

AVAILABLE_INPUT_FIELDS = {
    'name':        {'label': 'Name',        'default': 'NA',  'type': 'text'},
    'quantity':    {'label': 'Quantity',    'default': '0',   'type': 'number'},
    'cost':        {'label': 'Cost',        'default': '0.00','type': 'money'},
    'location':    {'label': 'Location',    'default': 'NA',  'type': 'text'},
    'description': {'label': 'Description', 'default': 'NA',  'type': 'text'},
    'min_value':   {'label': 'Min Value',   'default': '0.00','type': 'money'},
    'max_value':   {'label': 'Max Value',   'default': '0.00','type': 'money'},
    'sale':        {'label': 'Sale Price',  'default': '0.00','type': 'money'},
    'part_number': {'label': 'Part#',       'default': 'NA',  'type': 'text'},
    'upc':         {'label': 'UPC',         'default': '0',   'type': 'number'},
    'po':          {'label': 'PO',          'default': 'NA',  'type': 'text'},
    'date':        {'label': 'Date',        'default': 'NA',  'type': 'date'},
}

# Program display names
PROGRAM_NAME = "TUI Inventory"
SUBTITLE = "Track your inventory with ease"

# Theme color settings
THEME_COLORS = {
    'cyan': curses.COLOR_CYAN,
    'green': curses.COLOR_GREEN,
    'blue': curses.COLOR_BLUE,
    'magenta': curses.COLOR_MAGENTA,
    'red': curses.COLOR_RED,
    'yellow': curses.COLOR_YELLOW,
    'white': curses.COLOR_WHITE,
}
THEME_COLOR_PAIRS = {
    'cyan': 10,
    'green': 11,
    'blue': 12,
    'magenta': 13,
    'red': 14,
    'yellow': 15,
    'white': 16,
}
THEME_COLOR = curses.COLOR_CYAN

# ──────────────────────────────────────────────────────────────────────────────
# Manager (multi-inventory launcher) state
# ──────────────────────────────────────────────────────────────────────────────

MGR_PROGRAM_NAME = "TUI Inventories Manager"
MGR_SUBTITLE     = "Select an inventory to manage"
MGR_THEME_COLOR  = curses.COLOR_CYAN
INVENTORIES      = []
MGR_SELECTED_IDX = 0

# Default configuration written when a new inventory folder is created.
DEFAULT_CONFIG = {
    "custom_fields": [],
    "theme_color": "cyan",
    "program_name": "New Inventory",
    "subtitle": "Track your inventory",
    "po_enabled": True,
    "monetization_enabled": True,
    "color_critical_enabled": True,
    "delete_confirm_enabled": True,
    "hide_zero_qty_enabled": True,
    "auto_delete_zero_enabled": False,
    "sale_enabled": True,
    "date_format": "%m/%d/%Y",
    "splash_enabled": True,
    "columns": [
        {"key": "name", "width": 24, "align": "left"},
        {"key": "quantity", "width": 6, "align": "right"},
        {"key": "cost", "width": 12, "align": "center"},
        {"key": "location", "width": 10, "align": "left"},
        {"key": "description", "width": 20, "align": "left"},
    ],
    "history_columns": [
        {"key": "timestamp", "width": 10, "align": "left"},
        {"key": "name", "width": 20, "align": "left"},
        {"key": "quantity", "width": 4, "align": "right"},
        {"key": "price", "width": 8, "align": "right"},
        {"key": "total", "width": 10, "align": "right"},
        {"key": "po", "width": 12, "align": "left"},
    ],
    "input_fields": ["name", "quantity", "description", "location", "cost"],
}

DEFAULT_ABOUT = (
    "Welcome to your inventory.\n"
    "\n"
    "Edit this About page to describe what you are tracking.\n"
)

def apply_theme(color):
    """Reinitialize the four standard color pairs for the given theme color."""
    curses.init_pair(1, color, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)

def load_manager_config():
    global MGR_PROGRAM_NAME, MGR_SUBTITLE, MGR_THEME_COLOR
    if MANAGER_CONFIG_FILE.exists():
        try:
            with MANAGER_CONFIG_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            MGR_PROGRAM_NAME = data.get('program_name', MGR_PROGRAM_NAME)
            MGR_SUBTITLE = data.get('subtitle', MGR_SUBTITLE)
            MGR_THEME_COLOR = THEME_COLORS.get(data.get('theme_color', 'cyan'), curses.COLOR_CYAN)
        except Exception:
            pass

def save_manager_config():
    color_name = next((k for k, v in THEME_COLORS.items() if v == MGR_THEME_COLOR), 'cyan')
    with MANAGER_CONFIG_FILE.open('w', encoding='utf-8') as f:
        json.dump({
            'program_name': MGR_PROGRAM_NAME,
            'subtitle': MGR_SUBTITLE,
            'theme_color': color_name,
        }, f, indent=2)

def scan_inventories():
    """Return a sorted list of {'folder', 'name'} for each inventory folder."""
    global INVENTORIES
    INVENTORIES = []
    try:
        entries = sorted(SCRIPT_DIR.iterdir())
    except Exception:
        return INVENTORIES

    for entry in entries:
        if entry == SCRIPT_DIR or not entry.is_dir():
            continue
        config_json = entry / "inventory_config.json"
        if not config_json.exists():
            continue
        try:
            with config_json.open('r', encoding='utf-8') as f:
                data = json.load(f)
            name = data.get('program_name') or entry.name
        except Exception:
            name = entry.name
        INVENTORIES.append({'folder': entry, 'name': name})

    INVENTORIES.sort(key=lambda x: x['name'].lower())
    return INVENTORIES

def draw_footer(stdscr, controls):
    h, w = stdscr.getmaxyx()
    try:
        stdscr.addstr(h-2, 0, "·" * min(w, 80))
        stdscr.addnstr(h-1, 0, controls.ljust(w-1), w-1)
    except curses.error:
        pass

def draw_detail_line(stdscr, y, label, value, label_width):
    line = f"{label}:{'':>{label_width - len(label)}}{value}"
    stdscr.addstr(y, 0, line)
    return y + 1

# ──────────────────────────────────────────────────────────────────────────────
# Config load/save
# ──────────────────────────────────────────────────────────────────────────────

def load_config():
    global CUSTOM_FIELDS, THEME_COLOR, PROGRAM_NAME, SUBTITLE, PO_ENABLED, MONETIZATION_ENABLED, COLOR_CRITICAL_ENABLED, DELETE_CONFIRM_ENABLED, HIDE_ZERO_QTY_ENABLED, AUTO_DELETE_ZERO_ENABLED, COLUMNS, HISTORY_COLUMNS, INPUT_FIELDS, SALE_ENABLED, DATE_FORMAT, SPLASH_ENABLED
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
                CUSTOM_FIELDS = data.get('custom_fields', [])[:5]
                color_name = data.get('theme_color', 'cyan')
                THEME_COLOR = THEME_COLORS.get(color_name, curses.COLOR_CYAN)
                PROGRAM_NAME = data.get('program_name', 'TUI Inventory')
                SUBTITLE = data.get('subtitle', 'Track your inventory with ease')
                PO_ENABLED = data.get('po_enabled', True)
                MONETIZATION_ENABLED = data.get('monetization_enabled', True)
                COLOR_CRITICAL_ENABLED = data.get('color_critical_enabled', True)
                DELETE_CONFIRM_ENABLED = data.get('delete_confirm_enabled', True)
                HIDE_ZERO_QTY_ENABLED = data.get('hide_zero_qty_enabled', True)
                AUTO_DELETE_ZERO_ENABLED = data.get('auto_delete_zero_enabled', False)
                SALE_ENABLED = data.get('sale_enabled', True)
                DATE_FORMAT = data.get('date_format', "%m/%d/%Y")
                SPLASH_ENABLED = data.get('splash_enabled', True)
                saved_cols = data.get('columns', None)
                if saved_cols:
                    COLUMNS = saved_cols
                saved_history_cols = data.get('history_columns', None)
                if saved_history_cols:
                    HISTORY_COLUMNS = saved_history_cols
                saved_input_fields = data.get('input_fields', None)
                if saved_input_fields:
                    INPUT_FIELDS = saved_input_fields
        except Exception:
            CUSTOM_FIELDS = []
            THEME_COLOR = curses.COLOR_CYAN
    else:
        CUSTOM_FIELDS = []
        THEME_COLOR = curses.COLOR_CYAN

def save_config(include_theme=True):
    global CUSTOM_FIELDS, PROGRAM_NAME, SUBTITLE, PO_ENABLED, MONETIZATION_ENABLED, COLOR_CRITICAL_ENABLED, DELETE_CONFIRM_ENABLED, HIDE_ZERO_QTY_ENABLED, AUTO_DELETE_ZERO_ENABLED, COLUMNS, HISTORY_COLUMNS, INPUT_FIELDS, SALE_ENABLED, DATE_FORMAT, SPLASH_ENABLED
    with CONFIG_FILE.open('w', encoding='utf-8') as f:
        color_name = next((k for k, v in THEME_COLORS.items() if v == THEME_COLOR), 'cyan')
        if include_theme:
            json.dump({'custom_fields': CUSTOM_FIELDS, 'theme_color': color_name, 'program_name': PROGRAM_NAME, 'subtitle': SUBTITLE, 'po_enabled': PO_ENABLED, 'monetization_enabled': MONETIZATION_ENABLED, 'color_critical_enabled': COLOR_CRITICAL_ENABLED, 'delete_confirm_enabled': DELETE_CONFIRM_ENABLED, 'hide_zero_qty_enabled': HIDE_ZERO_QTY_ENABLED, 'auto_delete_zero_enabled': AUTO_DELETE_ZERO_ENABLED, 'sale_enabled': SALE_ENABLED, 'date_format': DATE_FORMAT, 'splash_enabled': SPLASH_ENABLED, 'columns': COLUMNS, 'history_columns': HISTORY_COLUMNS, 'input_fields': INPUT_FIELDS}, f, indent=2)
        else:
            json.dump({'custom_fields': CUSTOM_FIELDS}, f, indent=2)

def _fmt_custom(value, field):
    """Format a custom-field value by type: money $x.xx, decimal N places, number commas."""
    t = field.get('type')
    if t == 'money' and isinstance(value, (int, float)):
        return f"${value:,.2f}"
    if t == 'decimal' and isinstance(value, (int, float)):
        return f"{value:,.{field.get('decimals', 2)}f}"
    if t == 'number' and isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return f"{int(value):,}"
        return f"{value:,}"
    return str(value)

def _round_custom(value, field):
    """Round a numeric custom-field value to the field's stored precision."""
    if field.get('type') == 'decimal':
        return round(value, field.get('decimals', 2))
    if field.get('type') == 'money':
        return round(value, 2)
    return value

# ──────────────────────────────────────────────────────────────────────────────
# Item model
# ──────────────────────────────────────────────────────────────────────────────

class Item:
    def __init__(self, name, quantity=0, cost=0.0, min_value=0.0, max_value=0.0,
                 sale=0.0, location="", description="", timestamp="",
                 part_number="", upc=0, po="", date="", **custom):
        self.name = name.strip()
        self.quantity = quantity
        self.cost = cost
        self.min_value = min_value
        self.max_value = max_value
        self.sale = sale
        self.location = location.strip()
        self.description = description.strip()
        self.timestamp = timestamp if timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.part_number = part_number.strip()
        self.upc = upc
        self.po = po.strip()
        self.date = date.strip()
        self.custom = custom or {}

    @property
    def total_sale_value(self):
        return self.quantity * self.sale

    @property
    def margin_percent(self):
        if self.sale > self.cost > 0:
            return (self.sale - self.cost) / self.sale * 100
        return None

    @property
    def stock_status(self):
        try:
            critical = int(self.custom.get('critical_stock', 3) or 3)
        except (ValueError, TypeError):
            critical = 3
        try:
            low = int(self.custom.get('low_stock_threshold', 5) or 5)
        except (ValueError, TypeError):
            low = 5
        if self.quantity <= critical: return "critical"
        if self.quantity <= low: return "low"
        return "ok"

    def to_dict(self):
        d = {
            'name': self.name, 'quantity': self.quantity, 'cost': self.cost,
            'min_value': self.min_value, 'max_value': self.max_value,
            'sale': self.sale, 'location': self.location,
            'description': self.description, 'timestamp': self.timestamp,
            'part_number': self.part_number, 'upc': self.upc, 'po': self.po,
            'date': self.date
        }
        d.update(self.custom)
        return d

    @classmethod
    def from_dict(cls, d):
        known = {'name','quantity','cost','min_value','max_value','sale','location','description','timestamp','part_number','upc','po','date'}
        custom = {}
        for k, v in d.items():
            if k not in known:
                try:
                    custom[k] = float(v)
                except (ValueError, TypeError):
                    custom[k] = v
        return cls(
            name=d['name'],
            quantity=int(d.get('quantity', 0)),
            cost=float(d.get('cost', 0.0)),
            min_value=float(d.get('min_value', 0.0)),
            max_value=float(d.get('max_value', 0.0)),
            sale=float(d.get('sale', 0.0)),
            location=d.get('location', '').strip(),
            description=d.get('description', '').strip(),
            timestamp=d.get('timestamp', ''),
            part_number=d.get('part_number', '').strip(),
            upc=int(d.get('upc', 0)) if d.get('upc') else 0,
            po=d.get('po', '').strip(),
            date=d.get('date', '').strip(),
            **custom
        )

# ──────────────────────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────────────────────

def get_all_fieldnames(inventory):
    base = [
        'name', 'quantity', 'cost', 'min_value', 'max_value',
        'sale', 'location', 'description', 'timestamp',
        'part_number', 'upc', 'po', 'date'
    ]
    custom_keys = set()
    for item in inventory:
        custom_keys.update(item.custom.keys())
    custom_sorted = sorted(custom_keys)
    return base + custom_sorted

def load_inventory():
    inventory = []
    if DB_FILE.exists():
        with DB_FILE.open('r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    inventory.append(Item.from_dict(row))
                except (ValueError, KeyError):
                    continue
    return inventory

def safe_save_inventory(inventory):
    if DB_FILE.exists():
        shutil.copy2(DB_FILE, BACKUP_FILE)

    if not inventory:
        fieldnames = get_all_fieldnames([])
        with DB_FILE.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        return

    fieldnames = get_all_fieldnames(inventory)

    with DB_FILE.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for item in inventory:
            writer.writerow(item.to_dict())

# ──────────────────────────────────────────────────────────────────────────────
# Sales Recording
# ──────────────────────────────────────────────────────────────────────────────

def record_sale(inventory, orig_idx, qty_sold, price_each, po_number=None):
    global PO_ENABLED
    if not (0 <= orig_idx < len(inventory)):
        return False
    item = inventory[orig_idx]
    if qty_sold <= 0 or qty_sold > item.quantity:
        return False

    item.quantity -= qty_sold
    total = qty_sold * price_each

    timestamp = datetime.now().isoformat(timespec='seconds')
    po_value = "N/A" if not PO_ENABLED else (po_number or '')
    row = {
        'timestamp': timestamp,
        'name': item.name,
        'quantity_sold': qty_sold,
        'price_each': f"{price_each:.2f}",
        'total': f"{total:.2f}",
        'po_number': po_value,
        'remaining_stock': item.quantity
    }

    header = list(row.keys())
    mode = 'a' if SALES_LOG.exists() else 'w'

    with SALES_LOG.open(mode, encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if mode == 'w':
            writer.writeheader()
        writer.writerow(row)

    if item.quantity == 0 and AUTO_DELETE_ZERO_ENABLED:
        inventory.pop(orig_idx)

    safe_save_inventory(inventory)
    return True

def record_sale_ui(stdscr, inventory, orig_idx):
    global PO_ENABLED, MONETIZATION_ENABLED
    load_config()
    if not (0 <= orig_idx < len(inventory)):
        return False
    item = inventory[orig_idx]

    stdscr.clear()
    stdscr.addstr(0, 0, f"Record Sale: {item.name}")
    stdscr.addstr(2, 0, f"Current stock: {item.quantity:,}")
    if item.sale > 0 and MONETIZATION_ENABLED:
        stdscr.addstr(3, 0, f"Suggested price: ${item.sale:,.2f}")

    if MONETIZATION_ENABLED:
        qty_str = get_input(stdscr, "How many sold? ", 5, 0, 10, "1")
    else:
        qty_str = get_input(stdscr, "Remove how many units? ", 5, 0, 10, "1")
    try:
        qty_sold = int(qty_str or "1")
        if qty_sold <= 0 or qty_sold > item.quantity:
            stdscr.addstr(8, 0, f"Error: 1–{item.quantity}")
            stdscr.addstr(10, 0, "Press any key...")
            stdscr.getch()
            return False
    except ValueError:
        stdscr.addstr(8, 0, "Invalid quantity")
        stdscr.addstr(10, 0, "Press any key...")
        stdscr.getch()
        return False

    if MONETIZATION_ENABLED:
        default_price = f"{item.sale:.2f}" if item.sale > 0 else "0.00"
        price_str = get_input(stdscr, "Price each ($): ", 6, 0, 12, "")
        try:
            price_each = float(price_str or "0.00")
            if price_each <= 0:
                raise ValueError
        except ValueError:
            stdscr.addstr(8, 0, "Price must be > 0")
            stdscr.addstr(10, 0, "Press any key...")
            stdscr.getch()
            return False
    else:
        price_each = 0.0

    po_number = ""
    if PO_ENABLED and MONETIZATION_ENABLED:
        while True:
            stdscr.addstr(10, 0, " " * (curses.COLS - 1))
            stdscr.addstr(9, 0, " " * (curses.COLS - 1))
            po_str = get_input(stdscr, "PO Number (optional, 20 max): ", 9, 0, 20, "")
            po_number = po_str.strip() if po_str else ""

            total = qty_sold * price_each
            po_display = f"PO: {po_number}" if po_number else "PO: -"
            confirm = f"Sell {qty_sold:,} × {item.name} @ ${price_each:,.2f} = ${total:,.2f} ? (y/n/r)"
            stdscr.addstr(7, 0, po_display)
            stdscr.addstr(10, 0, confirm[:curses.COLS-1])
            stdscr.refresh()

            ch = stdscr.getch()
            if ch in (ord('r'), ord('R')):
                continue
            elif ch not in (ord('y'), ord('Y'), ord(' ')):
                stdscr.addstr(12, 0, "Cancelled. Press any key...")
                stdscr.getch()
                return False
            else:
                break
    elif MONETIZATION_ENABLED:
        total = qty_sold * price_each
        po_display = "PO: N/A (disabled)"
        confirm = f"Sell {qty_sold:,} × {item.name} @ ${price_each:,.2f} = ${total:,.2f} ? (y/n)"
        stdscr.addstr(7, 0, po_display)
        stdscr.addstr(9, 0, confirm[:curses.COLS-1])
        stdscr.refresh()
        ch = stdscr.getch()
        if ch not in (ord('y'), ord('Y'), ord(' ')):
            stdscr.addstr(11, 0, "Cancelled. Press any key...")
            stdscr.getch()
            return False
    else:
        confirm = f"Remove {qty_sold:,} × {item.name} from inventory ? (y/n)"
        stdscr.addstr(7, 0, "Monetization: disabled")
        stdscr.addstr(9, 0, confirm[:curses.COLS-1])
        stdscr.refresh()
        ch = stdscr.getch()
        if ch not in (ord('y'), ord('Y'), ord(' ')):
            stdscr.addstr(11, 0, "Cancelled. Press any key...")
            stdscr.getch()
            return False

    success = record_sale(inventory, orig_idx, qty_sold, price_each, po_number)
    stdscr.addstr(9, 0, " " * (curses.COLS - 1))
    stdscr.addstr(10, 0, " " * (curses.COLS - 1))
    msg = f"Sale recorded. New stock: {inventory[orig_idx].quantity:,}" if success else "Error recording sale."
    stdscr.addstr(10, 0, msg)
    stdscr.addstr(12, 0, "Press any key...")
    stdscr.getch()
    return success

# ──────────────────────────────────────────────────────────────────────────────
# Sales History
# ──────────────────────────────────────────────────────────────────────────────

def view_sales_history(stdscr):
    global HISTORY_COLUMNS, AVAILABLE_HISTORY_COLUMNS
    load_config()
    
    if not SALES_LOG.exists():
        stdscr.clear()
        try:
            stdscr.addstr(2, 0, "No sales recorded yet.")
            stdscr.addstr(4, 0, "Press any key...")
        except curses.error:
            pass
        stdscr.refresh()
        stdscr.getch()
        return

    search_term = ""
    sort_key = 'timestamp'
    sort_directions = {'timestamp': -1, 'name': 1, 'quantity': 1, 'total': 1, 'price': 1, 'po': 1}

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        
        if h < 10 or w < 50:
            try:
                stdscr.addstr(h//2 - 1, 2, "Window too small to show sales history")
                stdscr.addstr(h//2 + 1, 2, f"Need ~50×10 – current: {w}×{h}")
                stdscr.addstr(h//2 + 3, 2, "Resize and press any key...")
            except curses.error:
                pass
            stdscr.refresh()
            ch = stdscr.getch()
            if ch == curses.KEY_RESIZE:
                continue
            return

        try:
            with SALES_LOG.open('r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))

                term = search_term.lower()
                if term:
                    rows = [r for r in rows if term in r.get('name', '').lower()]

                direction = sort_directions.get(sort_key, 1)
                rev = direction < 0

                if sort_key == 'timestamp':
                    rows.sort(key=lambda x: x.get('timestamp', ''), reverse=rev)
                elif sort_key == 'name':
                    rows.sort(key=lambda x: x.get('name', '').lower(), reverse=rev)
                elif sort_key == 'quantity':
                    rows.sort(key=lambda x: int(x.get('quantity_sold', 0)), reverse=rev)
                elif sort_key == 'total':
                    rows.sort(key=lambda x: float(x.get('total', 0)), reverse=rev)
                elif sort_key == 'price':
                    rows.sort(key=lambda x: float(x.get('price_each', 0)), reverse=rev)
                elif sort_key == 'po':
                    rows.sort(key=lambda x: x.get('po_number', '').lower(), reverse=rev)

                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(0, 0, "Sales History".center(min(w, 100)))
                stdscr.attroff(curses.color_pair(1))
                stdscr.addstr(1, 0, "")

                dir_symbol = "↓" if direction < 0 else "↑"
                status = f"Search: {search_term or '(none)'}   Sort: {sort_key} {dir_symbol}   (s:search #:sort ESC:clear)"
                try:
                    stdscr.addstr(2, 0, status[:w-1])
                except curses.error:
                    pass

                try:
                    stdscr.addstr(3, 0, "─" * min(w, 80))
                except curses.error:
                    pass

                col_positions = []
                x = 0
                for idx, col in enumerate(HISTORY_COLUMNS):
                    key = col['key']
                    label = AVAILABLE_HISTORY_COLUMNS[key]['label']
                    width = col['width']
                    align = col.get('align', 'left')
                    col_positions.append((key, x, width, align, label))
                    x += width + 1

                header_y = 6
                try:
                    stdscr.addstr(header_y, 0, "# ")
                    x = 2
                    for key, pos_x, width, align, label in col_positions:
                        col_label = f"{label}({col_positions.index((key, pos_x, width, align, label)) + 1})"
                        if align == 'right':
                            header_text = col_label[:width].rjust(width)
                        elif align == 'center':
                            header_text = col_label[:width].center(width)
                        else:
                            header_text = col_label[:width].ljust(width)
                        stdscr.addstr(header_y, x, header_text)
                        x += width + 1
                    stdscr.addstr(header_y, x, "more ->")
                    header_y += 1
                    stdscr.addstr(header_y, 0, "- " + "-" * min(w - 2, 80))
                except curses.error:
                    pass

                y = header_y + 1

                max_lines = h - y - 4
                for idx, row in enumerate(rows[:max_lines]):
                    if y >= h - 3:
                        break
                    row_str = f"{idx+1:<2} "
                    x = 2
                    for key, pos_x, width, align, label in col_positions:
                        if key == 'timestamp':
                            val = row.get('timestamp', '?')[:10]
                        elif key == 'name':
                            val = row.get('name', '?')
                        elif key == 'quantity':
                            val = int(row.get('quantity_sold', '0'))
                        elif key == 'price':
                            val = f"${float(row.get('price_each', '0')):,.2f}"
                        elif key == 'total':
                            val = f"${float(row.get('total', '0')):,.2f}"
                        elif key == 'po':
                            val = row.get('po_number', '-')
                        else:
                            val = str(row.get(key, ''))
                        
                        val = str(val)[:width]
                        if align == 'right':
                            formatted = val.rjust(width)
                        elif align == 'center':
                            formatted = val.center(width)
                        else:
                            formatted = val.ljust(width)
                        row_str += formatted + " "
                    try:
                        stdscr.addnstr(y, 0, row_str, w-1)
                    except curses.error:
                        pass
                    y += 1

            if len(rows) > max_lines:
                try:
                    stdscr.addstr(y, 0, f"... {len(rows) - max_lines} more rows (resize to see more)")
                except curses.error:
                    pass
                y += 1

            if search_term:
                draw_footer(stdscr, "ESC/b: clear search")
            else:
                draw_footer(stdscr, "ESC/b: back")
        except Exception as e:
            try:
                stdscr.addstr(2, 0, f"Error reading sales log: {str(e)[:60]}")
            except:
                pass
        else:
            stdscr.refresh()
        key = stdscr.getch()
        
        if key == curses.KEY_RESIZE:
            continue
        elif key == 27:
            if search_term:
                search_term = ""
            else:
                break
        elif key == ord('s'):
            search_term = search_mode(stdscr)
        elif key == ord('b') and search_term:
            search_term = ""
        elif key in (10, curses.KEY_ENTER, ord('b')):
            break
        elif key in (ord('n'), ord('t'), ord('$')):
            new_key = {ord('n'): 'name', ord('t'): 'timestamp', ord('$'): 'total'}[key]
            if new_key == sort_key:
                sort_directions[new_key] *= -1
            else:
                sort_key = new_key
                sort_directions[new_key] = 1
        elif ord('1') <= key <= ord('6'):
            col_idx = key - ord('1')
            if col_idx < len(HISTORY_COLUMNS):
                new_key = HISTORY_COLUMNS[col_idx]['key']
                if new_key == sort_key:
                    sort_directions[new_key] *= -1
                else:
                    sort_key = new_key
                    sort_directions[new_key] = 1
        elif not search_term:
            break

# ──────────────────────────────────────────────────────────────────────────────
# Column Configuration Menu
# ──────────────────────────────────────────────────────────────────────────────

def column_config_menu(stdscr):
    global COLUMNS, AVAILABLE_COLUMNS
    load_config()
    stdscr.keypad(1)
    
    for color_name, pair_id in THEME_COLOR_PAIRS.items():
        curses.init_pair(pair_id, THEME_COLORS[color_name], -1)
    
    selected_idx = 0
    
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        
        if h < 15 or w < 50:
            try:
                stdscr.addstr(h//2 - 2, 2, "Window too small")
                stdscr.addstr(h//2, 2, f"Need ~50×15 – current: {w}×{h}")
            except curses.error:
                pass
            stdscr.refresh()
            stdscr.getch()
            break
        
        try:
            stdscr.attron(curses.color_pair(1))
            stdscr.addstr(0, 0, "Inventory Column Configuration".center(min(w, 100)))
            stdscr.attroff(curses.color_pair(1))
        except curses.error:
            pass
        
        all_columns = []
        for key in AVAILABLE_COLUMNS.keys():
            is_active = any(c['key'] == key for c in COLUMNS)
            width = None
            align = None
            for c in COLUMNS:
                if c['key'] == key:
                    width = c['width']
                    align = c.get('align')
                    break
            if width is None:
                width = AVAILABLE_COLUMNS[key]['width']
            if align is None:
                align = AVAILABLE_COLUMNS[key]['align']
            all_columns.append({'key': key, 'width': width, 'align': align, 'active': is_active, 'is_custom': False})
        
        for field in CUSTOM_FIELDS:
            key = 'custom_' + field['name']
            is_active = any(c['key'] == key for c in COLUMNS)
            width = None
            align = None
            for c in COLUMNS:
                if c['key'] == key:
                    width = c['width']
                    align = c.get('align', 'left')
                    break
            if width is None:
                width = 12
            if align is None:
                align = 'left'
            all_columns.append({'key': key, 'width': width, 'align': align, 'active': is_active, 'is_custom': True, 'label': field['label'], 'type': field.get('type', 'text')})
        
        all_columns.sort(key=lambda c: c.get('label') or AVAILABLE_COLUMNS[c['key']]['label'])
        
        try:
            stdscr.addstr(2, 2, "Columns (↑↓: navigate, Enter: toggle, +/-: width, a: align L/C/R):")
            stdscr.addstr(3, 0, "─" * min(w, 80))
        except curses.error:
            pass
        
        y = 4
        for i, col in enumerate(all_columns):
            key = col['key']
            label = col.get('label') or AVAILABLE_COLUMNS[key]['label']
            width = col['width']
            align = col['align']
            marker = '[x]' if col['active'] else '[ ]'
            if i == selected_idx:
                prefix = '>'
            else:
                prefix = ' '
            if col['active']:
                try:
                    if i == selected_idx:
                        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                        stdscr.addstr(y + i, 2, f"{prefix} {marker} {label:<12}  w:{width:>3}  a:{align[0]}")
                        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                    else:
                        stdscr.addstr(y + i, 2, f"{prefix} {marker} {label:<12}  w:{width:>3}  a:{align[0]}")
                except curses.error:
                    pass
            else:
                try:
                    if i == selected_idx:
                        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                        stdscr.addstr(y + i, 2, f"{prefix} {marker} {label}")
                        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                    else:
                        stdscr.addstr(y + i, 2, f"{prefix} {marker} {label}")
                except curses.error:
                    pass
        
        preview_y = y + len(all_columns) + 2
        if preview_y > h - 10:
            preview_y = h - 10
        
        try:
            stdscr.addstr(preview_y, 2, "Sample Preview:")
        except curses.error:
            pass
        
        header_y = preview_y + 3
        sample_data = [
            {'name': 'Widget A', 'quantity': '25', 'cost': '$9.99', 'location': 'A1', 'description': 'Blue widget', 'min_value': '50.00', 'max_value': '100.00', 'sale': '$19.99'},
            {'name': 'Gadget B', 'quantity': '3', 'cost': '$24.50', 'location': 'B2', 'description': 'Red gadget', 'min_value': '75.00', 'max_value': '150.00', 'sale': '$49.00'},
            {'name': 'Thingamajig C', 'quantity': '150', 'cost': '$5.00', 'location': 'C3', 'description': 'Green thing', 'min_value': '25.00', 'max_value': '50.00', 'sale': '$12.00'},
        ]
        
        col_positions = []
        x = 2
        for col in COLUMNS:
            key = col['key']
            if key.startswith('custom_'):
                label = col.get('label', key)
            else:
                label = AVAILABLE_COLUMNS[key]['label']
            width = col['width']
            align = col.get('align', 'left')
            col_positions.append((key, x, width, align))
            x += width + 1
        
        x = 2
        for idx, col in enumerate(COLUMNS):
            key = col['key']
            if key.startswith('custom_'):
                label = col.get('label', key)
            else:
                label = AVAILABLE_COLUMNS[key]['label']
            width = col['width']
            align = col.get('align', 'left')
            label_with_num = f"{label}({idx + 1})"
            try:
                if align == 'right':
                    header_text = label_with_num[:width].rjust(width)
                elif align == 'center':
                    header_text = label_with_num[:width].center(width)
                else:
                    header_text = label_with_num[:width].ljust(width)
                stdscr.addstr(header_y, x, header_text)
            except curses.error:
                pass
            x += width + 1
        
        separator_y = header_y + 1
        for key, x, width, align in col_positions:
            try:
                stdscr.addstr(separator_y, x, '-' * width)
            except curses.error:
                pass
        
        for row_idx, row in enumerate(sample_data):
            row_y = header_y + 2 + row_idx
            if row_y >= h - 3:
                break
            for key, x, width, align in col_positions:
                val = str(row.get(key, ''))[:width]
                if align == 'right':
                    formatted = val.rjust(width)
                elif align == 'center':
                    formatted = val.center(width)
                else:
                    formatted = val.ljust(width)
                try:
                    stdscr.addstr(row_y, x, formatted)
                except curses.error:
                    pass
        
        try:
            stdscr.addstr(h-4, 0, "·" * min(w, 80))
            stdscr.addstr(h-3, 2, "↑↓: navigate  Enter: toggle  +/-: width  a: align  d: default  Esc/b: back")
            stdscr.addstr(h-2, 2, "(width 1-60)")
        except curses.error:
            pass
        
        stdscr.refresh()
        key = stdscr.getch()
        
        if key in (27, ord('b')):
            break
        elif key == ord('d'):
            COLUMNS[:] = [
                {'key': 'name', 'width': 24, 'align': 'left'},
                {'key': 'quantity', 'width': 6, 'align': 'right'},
                {'key': 'cost', 'width': 12, 'align': 'center'},
                {'key': 'location', 'width': 10, 'align': 'left'},
                {'key': 'description', 'width': 20, 'align': 'left'},
            ]
        elif key == curses.KEY_UP:
            selected_idx = max(0, selected_idx - 1)
        elif key == curses.KEY_DOWN:
            selected_idx = min(len(all_columns) - 1, selected_idx + 1)
        elif key in (curses.KEY_ENTER, 10, 13, ord(' ')):
            col = all_columns[selected_idx]
            if col['active']:
                COLUMNS[:] = [c for c in COLUMNS if c['key'] != col['key']]
            else:
                entry = {'key': col['key'], 'width': col['width'], 'align': col['align']}
                if col.get('label'):
                    entry['label'] = col['label']
                COLUMNS.append(entry)
        elif key in (ord('+'), ord('=')):
            col = all_columns[selected_idx]
            if col['active']:
                for c in COLUMNS:
                    if c['key'] == col['key']:
                        c['width'] = min(60, c['width'] + 1)
                        break
        elif key == ord('-'):
            col = all_columns[selected_idx]
            if col['active']:
                for c in COLUMNS:
                    if c['key'] == col['key']:
                        c['width'] = max(1, c['width'] - 1)
                        break
        elif key == ord('a'):
            col = all_columns[selected_idx]
            if col['active']:
                for c in COLUMNS:
                    if c['key'] == col['key']:
                        current_align = c.get('align', 'left')
                        if current_align == 'left':
                            c['align'] = 'center'
                        elif current_align == 'center':
                            c['align'] = 'right'
                        else:
                            c['align'] = 'left'
                        break
    
    save_config()

# ──────────────────────────────────────────────────────────────────────────────
# History Column Configuration Menu
# ──────────────────────────────────────────────────────────────────────────────

def history_column_config_menu(stdscr):
    global HISTORY_COLUMNS, AVAILABLE_HISTORY_COLUMNS
    load_config()
    stdscr.keypad(1)
    
    for color_name, pair_id in THEME_COLOR_PAIRS.items():
        curses.init_pair(pair_id, THEME_COLORS[color_name], -1)
    
    selected_idx = 0
    
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        
        if h < 15 or w < 50:
            try:
                stdscr.addstr(h//2 - 2, 2, "Window too small")
                stdscr.addstr(h//2, 2, f"Need ~50×15 – current: {w}×{h}")
            except curses.error:
                pass
            stdscr.refresh()
            stdscr.getch()
            break
        
        try:
            stdscr.attron(curses.color_pair(1))
            stdscr.addstr(0, 0, "History Column Configuration".center(min(w, 100)))
            stdscr.attroff(curses.color_pair(1))
        except curses.error:
            pass
        
        all_columns = []
        for key in AVAILABLE_HISTORY_COLUMNS.keys():
            is_active = any(c['key'] == key for c in HISTORY_COLUMNS)
            width = None
            align = None
            for c in HISTORY_COLUMNS:
                if c['key'] == key:
                    width = c['width']
                    align = c.get('align')
                    break
            if width is None:
                width = AVAILABLE_HISTORY_COLUMNS[key]['width']
            if align is None:
                align = AVAILABLE_HISTORY_COLUMNS[key]['align']
            all_columns.append({'key': key, 'width': width, 'align': align, 'active': is_active, 'is_custom': False})
        
        all_columns.sort(key=lambda c: c.get('label') or AVAILABLE_HISTORY_COLUMNS[c['key']]['label'])
        
        try:
            stdscr.addstr(2, 2, "Columns (↑↓: navigate, Enter: toggle, +/-: width, a: align L/C/R):")
            stdscr.addstr(3, 0, "─" * min(w, 80))
        except curses.error:
            pass
        
        y = 4
        for i, col in enumerate(all_columns):
            key = col['key']
            label = col.get('label') or AVAILABLE_HISTORY_COLUMNS[key]['label']
            width = col['width']
            align = col['align']
            marker = '[x]' if col['active'] else '[ ]'
            if i == selected_idx:
                prefix = '>'
            else:
                prefix = ' '
            if col['active']:
                try:
                    if i == selected_idx:
                        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                        stdscr.addstr(y + i, 2, f"{prefix} {marker} {label:<12}  w:{width:>3}  a:{align[0]}")
                        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                    else:
                        stdscr.addstr(y + i, 2, f"{prefix} {marker} {label:<12}  w:{width:>3}  a:{align[0]}")
                except curses.error:
                    pass
            else:
                try:
                    if i == selected_idx:
                        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                        stdscr.addstr(y + i, 2, f"{prefix} {marker} {label:<12}")
                        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                    else:
                        stdscr.addstr(y + i, 2, f"{prefix} {marker} {label:<12}")
                except curses.error:
                    pass
        
        header_y = 4 + len(all_columns) + 1
        try:
            stdscr.addstr(header_y, 2, "Preview:")
        except curses.error:
            pass
        
        sample_data = [
            {'timestamp': '2024-01-15', 'name': 'Widget A', 'quantity': '5', 'price': '$19.99', 'total': '$99.95', 'po': 'PO-12345'},
            {'timestamp': '2024-01-14', 'name': 'Gadget B', 'quantity': '2', 'price': '$49.00', 'total': '$98.00', 'po': ''},
        ]
        
        col_positions = []
        x = 2
        for col in HISTORY_COLUMNS:
            key = col['key']
            label = AVAILABLE_HISTORY_COLUMNS[key]['label']
            width = col['width']
            align = col.get('align', 'left')
            col_positions.append((key, x, width, align))
            x += width + 1
        
        x = 2
        for idx, col in enumerate(HISTORY_COLUMNS):
            key = col['key']
            label = AVAILABLE_HISTORY_COLUMNS[key]['label']
            width = col['width']
            align = col.get('align', 'left')
            label_with_num = f"{label}({idx + 1})"
            try:
                if align == 'right':
                    header_text = label_with_num[:width].rjust(width)
                elif align == 'center':
                    header_text = label_with_num[:width].center(width)
                else:
                    header_text = label_with_num[:width].ljust(width)
                stdscr.addstr(header_y + 2, x, header_text)
            except curses.error:
                pass
            x += width + 1
        
        separator_y = header_y + 3
        for key, x, width, align in col_positions:
            try:
                stdscr.addstr(separator_y, x, '-' * width)
            except curses.error:
                pass
        
        for row_idx, row in enumerate(sample_data):
            row_y = header_y + 4 + row_idx
            if row_y >= h - 3:
                break
            for key, x, width, align in col_positions:
                val = str(row.get(key, ''))[:width]
                if align == 'right':
                    formatted = val.rjust(width)
                elif align == 'center':
                    formatted = val.center(width)
                else:
                    formatted = val.ljust(width)
                try:
                    stdscr.addstr(row_y, x, formatted)
                except curses.error:
                    pass
        
        try:
            stdscr.addstr(h-4, 0, "·" * min(w, 80))
            stdscr.addstr(h-3, 2, "↑↓: navigate  Enter: toggle  +/-: width  a: align  d: default  Esc/b: back")
            stdscr.addstr(h-2, 2, "(width 1-60)")
        except curses.error:
            pass
        
        stdscr.refresh()
        key = stdscr.getch()
        
        if key in (27, ord('b')):
            break
        elif key == ord('d'):
            HISTORY_COLUMNS[:] = [
                {'key': 'timestamp', 'width': 10, 'align': 'left'},
                {'key': 'name', 'width': 20, 'align': 'left'},
                {'key': 'quantity', 'width': 4, 'align': 'right'},
                {'key': 'price', 'width': 8, 'align': 'right'},
                {'key': 'total', 'width': 10, 'align': 'right'},
                {'key': 'po', 'width': 12, 'align': 'left'},
            ]
        elif key == curses.KEY_UP:
            selected_idx = max(0, selected_idx - 1)
        elif key == curses.KEY_DOWN:
            selected_idx = min(len(all_columns) - 1, selected_idx + 1)
        elif key in (curses.KEY_ENTER, 10, 13, ord(' ')):
            col = all_columns[selected_idx]
            if col['active']:
                HISTORY_COLUMNS[:] = [c for c in HISTORY_COLUMNS if c['key'] != col['key']]
            else:
                HISTORY_COLUMNS.append({'key': col['key'], 'width': col['width'], 'align': col['align']})
        elif key in (ord('+'), ord('=')):
            col = all_columns[selected_idx]
            if col['active']:
                for c in HISTORY_COLUMNS:
                    if c['key'] == col['key']:
                        c['width'] = min(60, c['width'] + 1)
                        break
        elif key == ord('-'):
            col = all_columns[selected_idx]
            if col['active']:
                for c in HISTORY_COLUMNS:
                    if c['key'] == col['key']:
                        c['width'] = max(3, c['width'] - 1)
                        break
        elif key == ord('a'):
            col = all_columns[selected_idx]
            if col['active']:
                for c in HISTORY_COLUMNS:
                    if c['key'] == col['key']:
                        current_align = c.get('align', 'left')
                        if current_align == 'left':
                            c['align'] = 'center'
                        elif current_align == 'center':
                            c['align'] = 'right'
                        else:
                            c['align'] = 'left'
                        break
    
    save_config()

# ──────────────────────────────────────────────────────────────────────────────
# Inventory Input Customization Menu
# ──────────────────────────────────────────────────────────────────────────────

def input_customization_menu(stdscr):
    global INPUT_FIELDS, CUSTOM_FIELDS
    load_config()
    stdscr.keypad(1)

    for color_name, pair_id in THEME_COLOR_PAIRS.items():
        curses.init_pair(pair_id, THEME_COLORS[color_name], -1)

    selected_idx = 0

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        if h < 15 or w < 50:
            try:
                stdscr.addstr(0, 0, "Window too small. Resize and press any key...")
                stdscr.refresh()
                stdscr.getch()
            except curses.error:
                pass
            break

        try:
            stdscr.attron(curses.color_pair(1))
            stdscr.addstr(0, 0, "Inventory Input Customization".center(min(w, 100)))
            stdscr.attroff(curses.color_pair(1))
        except curses.error:
            pass

        # Build list of all available input fields (built-in + custom)
        all_fields = []
        for key in AVAILABLE_INPUT_FIELDS:
            info = AVAILABLE_INPUT_FIELDS[key]
            is_active = key in INPUT_FIELDS
            all_fields.append({'key': key, 'label': info['label'], 'default': info['default'], 'type': info['type'], 'active': is_active, 'is_custom': False})
        for field in CUSTOM_FIELDS:
            key = 'custom_' + field['name']
            is_active = key in INPUT_FIELDS
            if field.get('type') == 'money':
                default = '0.00'
            elif field.get('type') == 'decimal':
                d = field.get('decimals', 2)
                default = '0' if d == 0 else '0.' + '0' * d
            elif field.get('type') == 'number':
                default = '0'
            else:
                default = 'NA'
            all_fields.append({'key': key, 'label': field['label'], 'default': default, 'type': field.get('type', 'text'), 'active': is_active, 'is_custom': True})

        try:
            stdscr.addstr(2, 2, "Fields (Enter: toggle on/off):")
            stdscr.addstr(3, 0, "─" * min(w, 80))
        except curses.error:
            pass

        y = 4
        for i, field in enumerate(all_fields):
            if field['active']:
                order = INPUT_FIELDS.index(field['key']) + 1
                marker = f'[{order:>2}]'
            else:
                marker = '[  ]'
            if i == selected_idx:
                prefix = '>'
            else:
                prefix = ' '
            label = field['label']
            default_val = field['default']
            try:
                if i == selected_idx:
                    stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                    stdscr.addstr(y + i, 2, f"{prefix} {marker} {label:<18} default: {default_val}")
                    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                else:
                    stdscr.addstr(y + i, 2, f"{prefix} {marker} {label:<18} default: {default_val}")
            except curses.error:
                pass

        try:
            stdscr.addstr(h-2, 2, "(↑↓: scroll, Enter: toggle, d: reset defaults)")
        except curses.error:
            pass

        draw_footer(stdscr, "↑↓: navigate  Enter: toggle  d: defaults  Esc/b: back")

        stdscr.refresh()
        key = stdscr.getch()

        if key == curses.KEY_RESIZE:
            continue
        elif key == curses.KEY_UP:
            selected_idx = max(0, selected_idx - 1)
        elif key == curses.KEY_DOWN:
            selected_idx = min(len(all_fields) - 1, selected_idx + 1)
        elif key in (curses.KEY_ENTER, 10, 13, ord(' ')):
            field = all_fields[selected_idx]
            if field['active']:
                INPUT_FIELDS = [f for f in INPUT_FIELDS if f != field['key']]
            else:
                INPUT_FIELDS.append(field['key'])
            save_config()
        elif key == ord('d'):
            INPUT_FIELDS = ['name', 'quantity', 'description', 'location', 'cost']
            save_config()
        elif key in (27, ord('b')):
            break

# ──────────────────────────────────────────────────────────────────────────────
# About Menu
# ──────────────────────────────────────────────────────────────────────────────

def about_menu(stdscr):
    global PROGRAM_NAME
    load_config()
    stdscr.keypad(1)

    for color_name, pair_id in THEME_COLOR_PAIRS.items():
        curses.init_pair(pair_id, THEME_COLORS[color_name], -1)

    scroll_offset = 0

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        if h < 10 or w < 40:
            try:
                stdscr.addstr(0, 0, "Window too small. Resize and press any key...")
                stdscr.refresh()
                stdscr.getch()
            except curses.error:
                pass
            break

        try:
            stdscr.attron(curses.color_pair(1))
            stdscr.addstr(0, 0, f"About {PROGRAM_NAME}".center(min(w, 100)))
            stdscr.attroff(curses.color_pair(1))
        except curses.error:
            pass

        try:
            stdscr.addstr(1, 0, "─" * min(w, 100))
        except curses.error:
            pass

        lines = []
        try:
            if ABOUT_FILE.exists():
                with ABOUT_FILE.open('r', encoding='utf-8') as f:
                    lines = [line.rstrip('\n') for line in f.readlines()]
        except Exception:
            lines = ["Unable to read About file."]

        max_width = w - 5
        wrapped_lines = []
        for line in lines:
            words = line.split()
            current_line = ""
            for word in words:
                if not current_line:
                    current_line = word
                elif len(current_line) + 1 + len(word) <= max_width:
                    current_line += " " + word
                else:
                    wrapped_lines.append(current_line)
                    current_line = word
            if current_line:
                wrapped_lines.append(current_line)

        content_top = 2
        content_bottom = h - 3
        visible_lines = content_bottom - content_top

        for i in range(visible_lines):
            line_idx = scroll_offset + i
            if line_idx >= len(wrapped_lines):
                break
            try:
                stdscr.addstr(content_top + i, 2, wrapped_lines[line_idx])
            except curses.error:
                pass

        max_scroll = max(0, len(wrapped_lines) - visible_lines)

        draw_footer(stdscr, "↑↓: scroll  r: reset to default  Esc/b: back")

        stdscr.refresh()
        key = stdscr.getch()

        if key == curses.KEY_RESIZE:
            continue
        elif key in (curses.KEY_UP, ord('k')):
            scroll_offset = max(0, scroll_offset - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            scroll_offset = min(max_scroll, scroll_offset + 1)
        elif key == ord('r'):
            try:
                if ABOUT_DEFAULT_FILE.exists():
                    shutil.copy2(ABOUT_DEFAULT_FILE, ABOUT_FILE)
                    scroll_offset = 0
            except Exception:
                pass
        elif key in (27, ord('b')):
            break

# ──────────────────────────────────────────────────────────────────────────────
# Custom Fields Configuration Menu
# ──────────────────────────────────────────────────────────────────────────────

def _config_safe_row(stdscr):
    h, w = stdscr.getmaxyx()
    return max(0, min(22, h - 3)), w

def _edit_config_text(stdscr, label, current, max_len=40):
    """Prompt for a text value on a guaranteed on-screen row. Returns the new
    value or None if blank/cancelled."""
    row, w = _config_safe_row(stdscr)
    try:
        stdscr.move(row, 0)
        stdscr.clrtoeol()
    except curses.error:
        pass
    val = get_input(stdscr, label, row, 2, max_len, current)
    if val in ("__CANCEL__", "__GOBACK__"):
        return None
    val = val.strip()
    return val or None

def _config_status(stdscr, msg):
    row, w = _config_safe_row(stdscr)
    try:
        stdscr.move(row, 0)
        stdscr.clrtoeol()
        stdscr.addstr(row, 2, msg[:max(0, w - 3)])
    except curses.error:
        pass
    stdscr.refresh()
    stdscr.getch()

def config_menu(stdscr, inventory=None):
    global CUSTOM_FIELDS, THEME_COLOR, THEME_COLORS, THEME_COLOR_PAIRS, PROGRAM_NAME, SUBTITLE, PO_ENABLED, MONETIZATION_ENABLED, COLOR_CRITICAL_ENABLED, DELETE_CONFIRM_ENABLED, HIDE_ZERO_QTY_ENABLED, AUTO_DELETE_ZERO_ENABLED, SALE_ENABLED, DATE_FORMAT, INPUT_FIELDS, COLUMNS, SPLASH_ENABLED

    load_config()
    stdscr.keypad(1)

    for color_name, pair_id in THEME_COLOR_PAIRS.items():
        curses.init_pair(pair_id, THEME_COLORS[color_name], -1)

    TABS = ["Custom Fields", "Theming", "System Settings"]
    current_tab = 0
    current_option = 0

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        if h < 12 or w < 50:
            try:
                stdscr.addstr(h//2 - 2, 2, "Window too small for config menu")
                stdscr.addstr(h//2, 2, f"Need ~50×12 – current: {w}×{h}")
                stdscr.addstr(h//2 + 2, 2, "Resize and press any key to try again")
            except curses.error:
                pass
            stdscr.refresh()
            ch = stdscr.getch()
            if ch == curses.KEY_RESIZE:
                continue
            else:
                break

        try:
            stdscr.attron(curses.color_pair(1))
            stdscr.addstr(0, 0, "Inventory Settings".center(min(w, 100)))
            stdscr.attroff(curses.color_pair(1))
            stdscr.addstr(1, 0, "")
        except curses.error:
            pass

        tab_width = min(20, w // len(TABS))
        try:
            for i, tab in enumerate(TABS):
                x = i * tab_width
                if i == current_tab:
                    stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                    stdscr.addstr(2, x, f" {tab} ")
                    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                else:
                    stdscr.addstr(2, x, f" {tab} ")
            stdscr.addstr(3, 0, "─" * min(w, 80))
        except curses.error:
            pass

        content_top = 4

        if current_tab == 0:
            y = content_top
            try:
                stdscr.addstr(y, 2, "Custom Fields")
            except curses.error:
                pass
            y += 2
            if not CUSTOM_FIELDS:
                try:
                    stdscr.addstr(y, 2, "(none yet)")
                except:
                    pass
                y += 2
            else:
                for i, f in enumerate(CUSTOM_FIELDS):
                    if y >= h - 6:
                        try:
                            stdscr.addstr(y, 2, "[more fields hidden – resize taller]")
                        except:
                            pass
                        break
                    line = f"{i+1}. {f['label']} ({f['type']})"
                    try:
                        if i == current_option:
                            stdscr.attron(curses.color_pair(1))
                            stdscr.addnstr(y, 2, ">" + line, w-3)
                            stdscr.attroff(curses.color_pair(1))
                        else:
                            stdscr.addnstr(y, 2, " " + line, w-3)
                    except curses.error:
                        pass
                    y += 1

            y += 1
            try:
                stdscr.addstr(y, 2, f"[{len(CUSTOM_FIELDS)}/5]  a:add  d:del  e:edit")
            except curses.error:
                pass

        if current_tab == 1:
            y = content_top
            try:
                stdscr.addstr(y, 2, "Theme Color (titles & splash):")
                y += 1
                color_options = list(THEME_COLORS.keys())
                for i, color_name in enumerate(color_options):
                    prefix = ">" if i == current_option else " "
                    try:
                        stdscr.addstr(y + i, 2, f"{i+1}. {prefix} ")
                        stdscr.attron(curses.color_pair(THEME_COLOR_PAIRS[color_name]))
                        stdscr.addstr("  " + color_name.capitalize())
                        stdscr.attroff(curses.color_pair(THEME_COLOR_PAIRS[color_name]))
                    except curses.error:
                        pass
                y += len(color_options) + 1
                stdscr.addstr(y, 2, "(↑↓: select, 1-7: color, Enter: edit/change)")
                y += 2

                # Program Name
                if current_option == 7:
                    stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, 2, "> Program Name (max 40 chars):" if current_option == 7
                              else "  Program Name (max 40 chars):")
                stdscr.addstr(y + 1, 4, f"{PROGRAM_NAME}")
                if current_option == 7:
                    stdscr.attroff(curses.color_pair(1))
                y += 2

                # Subtitle
                if current_option == 8:
                    stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, 2, "> Subtitle (max 40 chars):" if current_option == 8
                              else "  Subtitle (max 40 chars):")
                stdscr.addstr(y + 1, 4, f"{SUBTITLE}")
                if current_option == 8:
                    stdscr.attroff(curses.color_pair(1))
                y += 3
                stdscr.addstr(y, 2, "n: edit name  s: edit subtitle  r: reset defaults")
            except curses.error:
                pass

        if current_tab == 2:
            y = content_top
            try:
                lines = [
                    f" 1. {'Show stock alerts':<20}: {'On' if COLOR_CRITICAL_ENABLED else 'Off'}",
                    f" 2. {'PO Number':<20}: {'On' if PO_ENABLED else 'Off'}",
                    f" 3. {'Monetization':<20}: {'On' if MONETIZATION_ENABLED else 'Off'}",
                    f" 4. {'Delete Confirm':<20}: {'On' if DELETE_CONFIRM_ENABLED else 'Off'}",
                    f" 5. {'Hide Zero Qty':<20}: {'On' if HIDE_ZERO_QTY_ENABLED else 'Off'}",
                    f" 6. {'Auto Delete Zero Qty':<20}: {'On' if AUTO_DELETE_ZERO_ENABLED else 'Off'}",
                    f" 7. {'Sale Option':<20}: {'On' if SALE_ENABLED else 'Off'}",
                    f" 8. {'Date Format':<20}: {'MM/DD/YYYY' if DATE_FORMAT == '%m/%d/%Y' else 'DD/MM/YYYY'}",
                    f" 9. Inventory Column Configuration",
                    f"10. History Column Configuration",
                    f"11. Inventory Input Customization",
                    f"12. {'Show Splash':<20}: {'On' if SPLASH_ENABLED else 'Off'}",
                ]
                for i, line in enumerate(lines):
                    if i == current_option:
                        stdscr.attron(curses.color_pair(1))
                        stdscr.addstr(y + i, 2, ">" + line)
                        stdscr.attroff(curses.color_pair(1))
                    else:
                        stdscr.addstr(y + i, 2, " " + line)
                stdscr.addstr(y + len(lines) + 1, 2, "(↑↓: navigate, Enter: toggle)")
            except curses.error:
                pass

        draw_footer(stdscr, "←/→: tabs  ↑↓: navigate  Enter: select  ?: about  Esc/b: back")

        stdscr.refresh()
        key = stdscr.getch()

        if key == curses.KEY_RESIZE:
            continue
        elif key in (curses.KEY_LEFT, ord('h')):
            current_tab = (current_tab - 1) % len(TABS)
            current_option = 0
        elif key in (curses.KEY_RIGHT, ord('l')):
            current_tab = (current_tab + 1) % len(TABS)
            current_option = 0
        elif current_tab == 1 and key == curses.KEY_UP:
            current_option = (current_option - 1) % 9
        elif current_tab == 1 and key == curses.KEY_DOWN:
            current_option = (current_option + 1) % 9
        elif current_tab == 0 and key == curses.KEY_UP:
            current_option = max(0, current_option - 1)
        elif current_tab == 0 and key == curses.KEY_DOWN:
            current_option = min(max(0, len(CUSTOM_FIELDS) - 1), current_option + 1)
        elif current_tab == 2 and key == curses.KEY_UP:
            current_option = (current_option - 1) % 12
        elif current_tab == 2 and key == curses.KEY_DOWN:
            current_option = (current_option + 1) % 12
        elif key in (10, curses.KEY_ENTER, ord(' ')):
            if current_tab == 1:
                color_names = list(THEME_COLORS.keys())
                if 0 <= current_option < len(color_names):
                    THEME_COLOR = THEME_COLORS[color_names[current_option]]
                    curses.init_pair(1, THEME_COLOR, -1)
                    save_config()
                elif current_option == 7:
                    new_name = _edit_config_text(stdscr, "Enter new program name: ", PROGRAM_NAME, 40)
                    if new_name:
                        PROGRAM_NAME = new_name
                        save_config()
                elif current_option == 8:
                    new_subtitle = _edit_config_text(stdscr, "Enter new subtitle: ", SUBTITLE, 40)
                    if new_subtitle:
                        SUBTITLE = new_subtitle
                        save_config()
            elif current_tab == 2:
                if current_option == 0:
                    COLOR_CRITICAL_ENABLED = not COLOR_CRITICAL_ENABLED
                    save_config()
                elif current_option == 1:
                    PO_ENABLED = not PO_ENABLED
                    save_config()
                elif current_option == 2:
                    MONETIZATION_ENABLED = not MONETIZATION_ENABLED
                    save_config()
                elif current_option == 3:
                    DELETE_CONFIRM_ENABLED = not DELETE_CONFIRM_ENABLED
                    save_config()
                elif current_option == 4:
                    HIDE_ZERO_QTY_ENABLED = not HIDE_ZERO_QTY_ENABLED
                    save_config()
                elif current_option == 5:
                    AUTO_DELETE_ZERO_ENABLED = not AUTO_DELETE_ZERO_ENABLED
                    save_config()
                elif current_option == 6:
                    SALE_ENABLED = not SALE_ENABLED
                    save_config()
                elif current_option == 7:
                    DATE_FORMAT = "%d/%m/%Y" if DATE_FORMAT == "%m/%d/%Y" else "%m/%d/%Y"
                    save_config()
                elif current_option == 8:
                    column_config_menu(stdscr)
                elif current_option == 9:
                    history_column_config_menu(stdscr)
                elif current_option == 10:
                    input_customization_menu(stdscr)
                elif current_option == 11:
                    SPLASH_ENABLED = not SPLASH_ENABLED
                    save_config()
        elif key == ord('?'):
            about_menu(stdscr)
        elif key in (27, ord('b')):
            break
        elif current_tab == 1 and 49 <= key <= 55:
            try:
                idx = key - 49
                current_option = idx
                color_names = list(THEME_COLORS.keys())
                if 0 <= idx < len(color_names):
                    THEME_COLOR = THEME_COLORS[color_names[idx]]
                    curses.init_pair(1, THEME_COLOR, -1)
                    save_config()
            except Exception as e:
                pass
        elif current_tab == 1 and key == ord('r'):
            PROGRAM_NAME = "TUI Inventory"
            SUBTITLE = "Track your inventory with ease"
            THEME_COLOR = THEME_COLORS['cyan']
            curses.init_pair(1, THEME_COLOR, -1)
            save_config()
            _config_status(stdscr, "Defaults restored. Press any key...")
        elif current_tab == 1 and key == ord('n'):
            new_name = _edit_config_text(stdscr, "Enter new program name: ", PROGRAM_NAME, 40)
            if new_name:
                PROGRAM_NAME = new_name
                save_config()
        elif current_tab == 1 and key == ord('s'):
            new_subtitle = _edit_config_text(stdscr, "Enter new subtitle: ", SUBTITLE, 40)
            if new_subtitle:
                SUBTITLE = new_subtitle
                save_config()
        elif current_tab == 0 and key == ord('a'):
            if len(CUSTOM_FIELDS) >= 5:
                try:
                    stdscr.addstr(y+4, 2, "Max 5 fields reached. Press any key...")
                    stdscr.getch()
                except:
                    pass
            else:
                stdscr.clear()
                try:
                    stdscr.addstr(2, 2, "Add Field")
                    label = get_input(stdscr, "Label: ", 4, 2, 30, "")
                    if not label.strip():
                        pass
                    else:
                        key = label.lower().replace(" ", "_")[:15]
                        while True:
                            typ = get_input(stdscr, "Type [t:text n:number d:decimal m:money x:date l:list]: ", 5, 2, 20, "").lower()
                            if typ in ('t', 'text'):
                                typ = 'text'
                                break
                            elif typ in ('n', 'number'):
                                typ = 'number'
                                break
                            elif typ in ('d', 'decimal'):
                                typ = 'decimal'
                                break
                            elif typ in ('m', 'money'):
                                typ = 'money'
                                break
                            elif typ in ('x', 'date'):
                                typ = 'date'
                                break
                            elif typ in ('l', 'list'):
                                typ = 'list'
                                break
                        decimals = None
                        if typ == 'decimal':
                            dec_str = get_input(stdscr, "Decimal places [0-6, default 2]: ", 6, 2, 1, "2", field_type="number")
                            try:
                                decimals = max(0, min(6, int(dec_str))) if dec_str.strip() else 2
                            except ValueError:
                                decimals = 2
                        if typ == 'date':
                            max_len = 30
                        elif typ == 'list':
                            max_len = 30
                            options = []
                            stdscr.clear()
                            stdscr.addstr(2, 2, "Add List Options (up to 10, empty line to finish)")
                            for i in range(10):
                                opt = get_input(stdscr, f"Option {i+1}: ", 4 + i, 2, 30, "")
                                if not opt.strip():
                                    break
                                options.append(opt.strip())
                            CUSTOM_FIELDS.append({'name':key, 'label':label, 'type':typ, 'max_len': max_len, 'options': options})
                        else:
                            max_row = 7 if typ == 'decimal' else 6
                            max_len_str = get_input(stdscr, "Max character length [default 60]: ", max_row, 2, 10, "60", field_type="number")
                            try:
                                max_len = int(max_len_str) if max_len_str.strip() else 60
                            except ValueError:
                                max_len = 60
                            field_entry = {'name':key, 'label':label, 'type':typ, 'max_len': max_len}
                            if decimals is not None:
                                field_entry['decimals'] = decimals
                            CUSTOM_FIELDS.append(field_entry)
                        save_config()
                        if typ == 'list':
                            msg_y = 16
                        elif typ == 'decimal':
                            msg_y = 9
                        else:
                            msg_y = 8
                        stdscr.addstr(msg_y, 2, "Added. Press any key...")
                        stdscr.getch()
                except curses.error:
                    pass
        elif current_tab == 0 and key == ord('e'):
            if current_tab == 0 and 0 <= current_option < len(CUSTOM_FIELDS):
                idx = current_option
                field = CUSTOM_FIELDS[idx]
                old_label = field['label']
                field_type = field.get('type', 'text')
                
                while True:
                    stdscr.clear()
                    h, w = stdscr.getmaxyx()
                    if h < 15 or w < 50:
                        break
                    try:
                        stdscr.addstr(2, 2, "Edit Field")
                        stdscr.addstr(3, 2, f"Label: {field['label']}")
                        if field_type == 'list':
                            stdscr.addstr(4, 2, "Type: List")
                            options = field.get('options', [])
                            stdscr.addstr(5, 2, "Options:")
                            for i, opt in enumerate(options):
                                stdscr.addstr(6 + i, 2, f"  {i+1}. {opt}")
                            instr_y = 6 + len(options) + 2
                            stdscr.addstr(instr_y, 2, "n: edit label  a: add option  d: delete option  Esc/b: save & back")
                            prompt_base = 6 + len(options) + 4
                        else:
                            instr_y = 6
                            if field_type == 'decimal':
                                stdscr.addstr(4, 2, f"Type: decimal ({field.get('decimals', 2)} places)")
                                stdscr.addstr(instr_y, 2, "n: edit label  p: decimal places  Esc/b: save & back")
                            else:
                                stdscr.addstr(4, 2, f"Type: {field_type}")
                                stdscr.addstr(instr_y, 2, "n: edit label  Esc/b: save & back")
                            prompt_base = 8
                    except curses.error:
                        pass
                    stdscr.refresh()
                    key = stdscr.getch()
                    
                    if key in (27, ord('b')):
                        save_config()
                        break
                    elif key == ord('n'):
                        prompt_y = prompt_base
                        stdscr.addstr(prompt_y, 2, "New label: ".ljust(w-3))
                        curses.echo()
                        try:
                            new_label = stdscr.getstr(prompt_y, 12, 30).decode('utf-8').strip()
                        except:
                            new_label = ""
                        curses.noecho()
                        if new_label:
                            field['label'] = new_label.strip()
                            new_key = new_label.lower().replace(" ", "_")[:15]
                            old_key = field['name']
                            field['name'] = new_key
                            if inventory is not None:
                                for item in inventory:
                                    if old_key in item.custom:
                                        item.custom[new_key] = item.custom.pop(old_key)
                            save_config()
                            if inventory:
                                safe_save_inventory(inventory)
                    elif key == ord('p') and field_type == 'decimal':
                        prompt_y = prompt_base
                        stdscr.addstr(prompt_y, 2, "Decimal places (0-6): ".ljust(w-3))
                        curses.echo()
                        try:
                            dec_str = stdscr.getstr(prompt_y, 25, 1).decode('utf-8').strip()
                        except:
                            dec_str = ""
                        curses.noecho()
                        if dec_str.strip():
                            try:
                                field['decimals'] = max(0, min(6, int(dec_str)))
                                save_config()
                            except ValueError:
                                pass
                    elif key == ord('a') and field_type == 'list':
                        options = field.get('options', [])
                        if len(options) >= 10:
                            try:
                                prompt_y = prompt_base
                                stdscr.addstr(prompt_y, 2, "Max 10 options. Press any key...")
                                stdscr.getch()
                            except:
                                pass
                        else:
                            prompt_y = prompt_base
                            stdscr.addstr(prompt_y, 2, "New option: ".ljust(w-3))
                            curses.echo()
                            try:
                                new_opt = stdscr.getstr(prompt_y, 13, 30).decode('utf-8').strip()
                            except:
                                new_opt = ""
                            curses.noecho()
                            if new_opt:
                                options.append(new_opt.strip())
                                field['options'] = options
                                save_config()
                    elif key == ord('d') and field_type == 'list':
                        options = field.get('options', [])
                        if not options:
                            try:
                                prompt_y = prompt_base
                                stdscr.addstr(prompt_y, 2, "No options to delete. Press any key...")
                                stdscr.getch()
                            except:
                                pass
                        else:
                            prompt_y = prompt_base
                            stdscr.addstr(prompt_y, 2, "Delete which (1-" + str(len(options)) + "): ".ljust(w-3))
                            curses.echo()
                            try:
                                del_cmd = stdscr.getstr(prompt_y, 23, 3).decode('utf-8').strip()
                            except:
                                del_cmd = ""
                            curses.noecho()
                            if del_cmd.isdigit() and 1 <= int(del_cmd) <= len(options):
                                deleted_opt = options.pop(int(del_cmd) - 1)
                                field['options'] = options
                                save_config()
        elif current_tab == 0 and key == ord('d'):
            if 0 <= current_option < len(CUSTOM_FIELDS):
                idx = current_option
                try:
                    removed_key = CUSTOM_FIELDS[idx]['name']
                    removed_label = CUSTOM_FIELDS[idx]['label']
                    prompt_text = f"Delete '{removed_label}'? This will delete all data collected for this field. (y/n): "
                    stdscr.addstr(y+4, 2, prompt_text)
                    stdscr.refresh()
                    curses.echo()
                    try:
                        confirm = stdscr.getstr(y+4, 2 + len(prompt_text), 3).decode('utf-8').strip().lower()
                    except:
                        confirm = ""
                    curses.noecho()
                    if confirm == 'y':
                        CUSTOM_FIELDS.pop(idx)
                        INPUT_FIELDS = [f for f in INPUT_FIELDS if f != f"custom_{removed_key}"]
                        COLUMNS = [c for c in COLUMNS if c['key'] != f"custom_{removed_key}"]
                        save_config()
                        current_option = max(0, min(current_option, len(CUSTOM_FIELDS) - 1)) if CUSTOM_FIELDS else 0
                        if inventory is not None:
                            for item in inventory:
                                item.custom.pop(removed_key, None)
                            safe_save_inventory(inventory)
                        try:
                            stdscr.addstr(y+6, 2, "Removed. Press any key...")
                            stdscr.getch()
                        except:
                            pass
                except:
                    pass

    return

# ──────────────────────────────────────────────────────────────────────────────
# Input / Validation Helpers
# ──────────────────────────────────────────────────────────────────────────────

def validate_inputs(name, qty_str, cost_str):
    errors = []
    if not name.strip():
        errors.append("Name cannot be empty")
    try:
        qty = int(qty_str or "0")
        if qty < 0:
            errors.append("Quantity cannot be negative")
    except ValueError:
        errors.append("Quantity must be integer")
    try:
        cost = float(cost_str or "0")
        if cost < 0:
            errors.append("Cost cannot be negative")
    except ValueError:
        errors.append("Cost must be number")
    return errors

def get_input(stdscr, prompt, y, x, max_len=60, default="", field_type="text", allow_cancel=False):
    stdscr.addstr(y, x, prompt)
    prompt_x = x + len(prompt)
    stdscr.move(y, prompt_x)
    stdscr.refresh()
    curses.curs_set(1)

    val = ""
    while True:
        ch = stdscr.getch()
        if ch in (10, 13, curses.KEY_ENTER):
            break
        elif ch == 27:
            if allow_cancel:
                curses.curs_set(0)
                return "__CANCEL__"
        elif ch == curses.KEY_UP:
            if allow_cancel:
                curses.curs_set(0)
                return "__GOBACK__"
        elif ch in (8, 127, curses.KEY_BACKSPACE, curses.KEY_DC):
            if val:
                val = val[:-1]
                try:
                    stdscr.addstr(y, prompt_x + len(val), " ")
                    stdscr.move(y, prompt_x + len(val))
                except curses.error:
                    pass
                stdscr.refresh()
        elif 32 <= ch <= 126 and len(val) < max_len:
            c = chr(ch)
            if field_type == "number" and c.isdigit():
                val += c
                stdscr.addch(y, prompt_x + len(val) - 1, ch)
                stdscr.refresh()
            elif field_type in ("money", "decimal") and (c.isdigit() or (c == '.' and '.' not in val)):
                val += c
                stdscr.addch(y, prompt_x + len(val) - 1, ch)
                stdscr.refresh()
            elif field_type == "text":
                val += c
                stdscr.addch(y, prompt_x + len(val) - 1, ch)
                stdscr.refresh()

    curses.curs_set(0)
    val = val.strip()
    if not val and default:
        return default
    return val

def _get_bounded_number(stdscr, prompt, y, x, max_digits, min_val, max_val, allow_cancel=False):
    label = prompt.ljust(15)
    stdscr.addstr(y, x, label)
    prompt_x = x + len(label)
    stdscr.move(y, prompt_x)
    stdscr.refresh()

    val = ""
    while True:
        ch = stdscr.getch()
        if ch in (10, 13, curses.KEY_ENTER):
            break
        elif ch == 27:
            if allow_cancel:
                return "__CANCEL__"
        elif ch == curses.KEY_UP:
            if allow_cancel:
                return "__GOBACK__"
        elif ch in (8, 127, curses.KEY_BACKSPACE, curses.KEY_DC):
            if val:
                val = val[:-1]
                try:
                    stdscr.addstr(y, prompt_x + len(val), " ")
                    stdscr.move(y, prompt_x + len(val))
                except curses.error:
                    pass
                stdscr.refresh()
        elif 32 <= ch <= 126 and len(val) < max_digits:
            c = chr(ch)
            if c.isdigit():
                test_val = val + c
                try:
                    num = int(test_val)
                    if num <= max_val:
                        val = test_val
                        stdscr.addch(y, prompt_x + len(val) - 1, ch)
                        stdscr.refresh()
                except ValueError:
                    pass

    if not val.strip():
        return str(min_val)
    num = int(val)
    if num < min_val:
        num = min_val
    return str(num)

def get_date_input(stdscr, prompt, y, x, allow_cancel=False):
    global DATE_FORMAT
    if prompt:
        stdscr.addstr(y, x, prompt)
        stdscr.refresh()

    is_mdy = DATE_FORMAT == "%m/%d/%Y"

    if is_mdy:
        month_str = _get_bounded_number(stdscr, "Month (1-12):", y, x, 2, 1, 12, allow_cancel)
        if month_str in ("__CANCEL__", "__GOBACK__"):
            return month_str
        day_str = _get_bounded_number(stdscr, "Day (1-31):", y + 1, x, 2, 1, 31, allow_cancel)
        if day_str in ("__CANCEL__", "__GOBACK__"):
            return day_str
        year_str = get_input(stdscr, "Year (YYYY):   ", y + 2, x, 4, "", "number", allow_cancel)
    else:
        day_str = _get_bounded_number(stdscr, "Day (1-31):", y, x, 2, 1, 31, allow_cancel)
        if day_str in ("__CANCEL__", "__GOBACK__"):
            return day_str
        month_str = _get_bounded_number(stdscr, "Month (1-12):", y + 1, x, 2, 1, 12, allow_cancel)
        if month_str in ("__CANCEL__", "__GOBACK__"):
            return month_str
        year_str = get_input(stdscr, "Year (YYYY):   ", y + 2, x, 4, "", "number", allow_cancel)

    if year_str in ("__CANCEL__", "__GOBACK__"):
        return year_str

    try:
        month = int(month_str) if month_str.strip() else 1
        day = int(day_str) if day_str.strip() else 1
        year = int(year_str) if year_str.strip() else 2026
        month = max(1, min(12, month))
        day = max(1, min(31, day))
        year = max(1900, min(2100, year))
        return f"{month:02d}/{day:02d}/{year:04d}"
    except ValueError:
        return "NA"

def add_item(stdscr, inventory):
    global INPUT_FIELDS, CUSTOM_FIELDS
    load_config()
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    stdscr.addstr(0, 0, "Add New Item (Esc: cancel, Up: go back)")

    defaults = {
        'name': 'NA', 'quantity': '0', 'cost': '0.00',
        'location': 'NA', 'description': 'NA',
        'min_value': '0.00', 'max_value': '0.00', 'sale': '0.00'
    }
    if 'quantity' not in INPUT_FIELDS:
        defaults['quantity'] = '1'

    field_values = {}
    for key in defaults:
        if key not in INPUT_FIELDS:
            field_values[key] = defaults[key]

    def get_label(key):
        if key in AVAILABLE_INPUT_FIELDS:
            return AVAILABLE_INPUT_FIELDS[key]['label']
        elif key.startswith('custom_'):
            for cf in CUSTOM_FIELDS:
                if cf['name'] == key[7:]:
                    return cf['label']
        return None

    def get_max_len(key):
        if key in AVAILABLE_INPUT_FIELDS:
            return 60
        for cf in CUSTOM_FIELDS:
            if cf['name'] == key[7:]:
                return cf.get('max_len', 60)
        return 60

    def get_field_type(key):
        if key in AVAILABLE_INPUT_FIELDS:
            return AVAILABLE_INPUT_FIELDS[key]['type']
        for cf in CUSTOM_FIELDS:
            if cf['name'] == key[7:]:
                return cf.get('type', 'text')
        return None

    def calc_y(index):
        cy = 2
        for i in range(index):
            k = INPUT_FIELDS[i]
            if get_label(k) is None:
                continue
            if k.startswith('custom_'):
                for field in CUSTOM_FIELDS:
                    if field['name'] == k[7:] and field.get('type') == 'date':
                        cy += 1
                        break
            cy += 1
        return cy

    def redraw_screen(up_to_idx):
        h, w = stdscr.getmaxyx()
        for row in range(h):
            try:
                stdscr.addstr(row, 0, " " * (w - 1))
            except curses.error:
                pass
        stdscr.addstr(0, 0, "Add New Item (Esc: cancel, Up: go back)")
        fy = 1
        for i in range(up_to_idx):
            fk = INPUT_FIELDS[i]
            label = get_label(fk)
            if label is None:
                continue
            fv = field_values.get(fk, '')
            ftype = get_field_type(fk)
            if fk.startswith('custom_'):
                cf = next((f for f in CUSTOM_FIELDS if f['name'] == fk[7:]), None)
                if cf is not None and isinstance(fv, (int, float)):
                    fv = _fmt_custom(fv, cf)
                else:
                    fv = str(fv) if fv != '' else ''
            elif ftype == 'money' and isinstance(fv, (int, float)):
                fv = f"${fv:,.2f}"
            elif ftype == 'number' and isinstance(fv, (int, float)):
                fv = f"{fv:,}"
            else:
                fv = str(fv) if fv != '' else ''
            stdscr.addstr(fy, 0, f"  {label + ':':<16}{fv}")
            fy += 1
        stdscr.refresh()

    y = 2
    idx = 0
    while idx < len(INPUT_FIELDS):
        key = INPUT_FIELDS[idx]
        label = get_label(key)
        if label is None:
            idx += 1
            continue
        y = calc_y(idx)
        ftype = get_field_type(key)

        if ftype == 'date':
            stdscr.addstr(y, 0, f"  {label + ':':<16}Enter date:")
            result = get_date_input(stdscr, "", y + 1, 0, allow_cancel=True)
            if result == "__CANCEL__":
                stdscr.addstr(min(y + 5, h - 2), 0, "Cancelled. Press any key...")
                stdscr.getch()
                return
            if result == "__GOBACK__":
                if idx > 0:
                    idx -= 1
                    redraw_screen(idx)
                    continue
                else:
                    continue
            field_values[key] = result if result else 'NA'
            redraw_screen(idx + 1)
        elif ftype == 'list':
            stdscr.addstr(y, 0, f"  {label + ':':<16}Select option:")
            options = []
            for cf in CUSTOM_FIELDS:
                if cf['name'] == key[7:]:
                    options = cf.get('options', [])
                    break
            for i, opt in enumerate(options):
                stdscr.addstr(y + 1 + i, 2, f"{i+1}. {opt}")
            stdscr.addstr(y + 1 + len(options), 0, "Enter number: ")
            stdscr.refresh()
            choice_str = ""
            while True:
                ch = stdscr.getch()
                if ch in (10, 13, curses.KEY_ENTER):
                    break
                elif ch == 27:
                    stdscr.addstr(min(y + len(options) + 3, h - 2), 0, "Cancelled. Press any key...")
                    stdscr.getch()
                    return
                elif ch == curses.KEY_UP:
                    if idx > 0:
                        idx -= 1
                        redraw_screen(idx)
                        choice_str = "__GOBACK__"
                        break
                    else:
                        continue
                elif ch in (8, 127, curses.KEY_BACKSPACE, curses.KEY_DC):
                    if choice_str:
                        choice_str = choice_str[:-1]
                        try:
                            prompt_x = 15
                            stdscr.addstr(y + 1 + len(options), prompt_x, "   ")
                            stdscr.addstr(y + 1 + len(options), prompt_x, choice_str)
                            stdscr.move(y + 1 + len(options), prompt_x + len(choice_str))
                        except curses.error:
                            pass
                        stdscr.refresh()
                elif 32 <= ch <= 126 and len(choice_str) < 3:
                    choice_str += chr(ch)
                    try:
                        stdscr.addch(y + 1 + len(options), 15 + len(choice_str) - 1, ch)
                        stdscr.move(y + 1 + len(options), 15 + len(choice_str))
                    except curses.error:
                        pass
                    stdscr.refresh()
            if choice_str == "__GOBACK__":
                continue
            try:
                choice_num = int(choice_str)
                if 1 <= choice_num <= len(options):
                    field_values[key] = options[choice_num - 1]
                else:
                    field_values[key] = 'NA'
            except ValueError:
                field_values[key] = choice_str if choice_str else 'NA'
            redraw_screen(idx + 1)
        else:
            prompt = f"  {label + ':':<16}"
            max_len = get_max_len(key)
            default_val = defaults.get(key, "")
            result = get_input(stdscr, prompt, y, 0, max_len, default_val, ftype, allow_cancel=True)
            if result == "__CANCEL__":
                stdscr.addstr(min(y + 1, h - 2), 0, "Cancelled. Press any key...")
                stdscr.getch()
                return
            if result == "__GOBACK__":
                if idx > 0:
                    idx -= 1
                    redraw_screen(idx)
                    continue
                else:
                    continue
            field_values[key] = result
            if key == 'name' and not field_values[key].strip():
                stdscr.addstr(min(y + 2, h - 2), 0, "Cancelled. Press any key...")
                stdscr.getch()
                return
            redraw_screen(idx + 1)
        idx += 1

    name = field_values['name']
    quantity = field_values['quantity']
    cost = field_values['cost']

    errors = validate_inputs(name, quantity, cost)
    if errors:
        stdscr.clear()
        stdscr.addstr(2, 0, "Cannot add item:")
        for i, err in enumerate(errors, 4):
            stdscr.addstr(i, 2, f"* {err}")
        stdscr.addstr(len(errors)+6, 0, "Press any key...")
        stdscr.getch()
        return

    try:
        new_item = Item(
            name, int(quantity or "0"), float(cost or "0"),
            float(field_values['min_value'] or "0"),
            float(field_values['max_value'] or "0"),
            float(field_values['sale'] or "0"),
            field_values['location'], field_values['description'],
            date=field_values.get('date', ''),
            part_number=field_values.get('part_number', ''),
            upc=int(field_values['upc']) if field_values.get('upc', '').strip() else 0,
            po=field_values.get('po', '')
        )
    except (ValueError, TypeError) as e:
        stdscr.clear()
        stdscr.addstr(2, 0, f"Cannot add item: {e}")
        stdscr.addstr(4, 0, "Press any key...")
        stdscr.getch()
        return

    new_item.custom['low_stock_threshold'] = 5
    new_item.custom['critical_stock'] = 3

    for field in CUSTOM_FIELDS:
        ckey = 'custom_' + field['name']
        if ckey in field_values:
            val = field_values[ckey]
            if field.get('type') in ('money', 'decimal') and isinstance(val, str) and val.strip():
                try:
                    val = _round_custom(float(val), field)
                except ValueError:
                    pass
            new_item.custom[field['name']] = val
        else:
            if field.get('type') in ('money', 'decimal'):
                new_item.custom[field['name']] = 0.0
            elif field.get('type') == 'number':
                new_item.custom[field['name']] = 0
            else:
                new_item.custom[field['name']] = 'NA'

    stdscr.clear()
    stdscr.addstr(0, 0, "Add New Item (leave name blank to cancel)")
    stdscr.addstr(2, 0, "Confirm add:")
    cy = 4
    try:
        for key in INPUT_FIELDS:
            # Get field value and type info
            if key.startswith('custom_'):
                cf_name = key[7:]
                for cf in CUSTOM_FIELDS:
                    if cf['name'] == cf_name:
                        label = cf['label']
                        value = new_item.custom.get(cf_name, '')
                        ftype = cf.get('type', 'text')
                        break
                else:
                    # Custom field not found, skip it
                    continue
            else:
                # Standard field
                label = AVAILABLE_INPUT_FIELDS[key]['label']
                value = getattr(new_item, key)
                ftype = AVAILABLE_INPUT_FIELDS[key]['type']
            
            # Format value based on type
            if key.startswith('custom_') and isinstance(value, (int, float)):
                formatted_value = _fmt_custom(value, cf)
            elif ftype == 'money' and isinstance(value, (int, float)):
                formatted_value = f"${value:,.2f}"
            elif ftype == 'number' and isinstance(value, (int, float)):
                formatted_value = f"{value:,}"
            elif ftype == 'date':
                formatted_value = str(value) if value else '(empty)'
            else:
                formatted_value = str(value) if value != '' else '(empty)'
            
            stdscr.addstr(cy, 0, f"  {label+':':<16}{formatted_value}"); cy += 1
    except curses.error:
        pass
    cy += 1
    try:
        stdscr.addstr(cy, 0, "Add this item? (y/n)")
    except curses.error:
        pass
    stdscr.refresh()
    while True:
        ch = stdscr.getch()
        if ch in (ord('y'), ord('Y')):
            inventory.append(new_item)
            safe_save_inventory(inventory)
            return
        elif ch in (ord('n'), ord('N')):
            return

# ──────────────────────────────────────────────────────────────────────────────
# Hardened select_field_to_edit
# ──────────────────────────────────────────────────────────────────────────────

def select_field_to_edit(stdscr, item):
    options = [
        "1.  Name",
        "2.  Quantity",
        "3.  Cost",
        "4.  Location",
        "5.  Description",
        "6.  Min Value",
        "7.  Max Value",
        "8.  All fields",
    ]
    custom_start = 8
    for i, field in enumerate(CUSTOM_FIELDS):
        num = custom_start + 1 + i
        sep = "  " if num < 10 else " "
        options.append(f"{num}.{sep}{field['label']} (custom)")
    all_fields_num = custom_start + len(CUSTOM_FIELDS)
    for j in range(1, 8):
        num = all_fields_num + j
        sep = "  " if num < 10 else " "
        label = f"{num}.{sep}Part#" if j == 1 else f"{num}.{sep}UPC" if j == 2 else f"{num}.{sep}PO" if j == 3 else f"{num}.{sep}Date" if j == 4 else f"{num}.{sep}Sale Price" if j == 5 else f"{num}.{sep}Low stock threshold" if j == 6 else f"{num}.{sep}Critical stock threshold"
        options.append(label)
    options.append("0.  Cancel")

    option_values = list(range(1, custom_start + 1)) + list(range(custom_start + 1, custom_start + 1 + len(CUSTOM_FIELDS))) + [custom_start + len(CUSTOM_FIELDS) + 1, custom_start + len(CUSTOM_FIELDS) + 2, custom_start + len(CUSTOM_FIELDS) + 3, custom_start + len(CUSTOM_FIELDS) + 4, custom_start + len(CUSTOM_FIELDS) + 5, custom_start + len(CUSTOM_FIELDS) + 6, custom_start + len(CUSTOM_FIELDS) + 7, None]
    
    selected_idx = 0
    typed_input = ""

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        if h < 18 or w < 60:
            try:
                stdscr.addstr(h//2 - 2, 2, "Window too small to edit item")
                stdscr.addstr(h//2, 2, f"Need ≈60×18 – current: {w}×{h}")
                stdscr.addstr(h//2 + 2, 2, "Resize larger then press any key...")
                stdscr.refresh()
                stdscr.getch()
            except curses.error:
                pass
            return None

        try:
            stdscr.addstr(0, 0, f"Edit which field?  (Item: {item.name[:w-30]})")
        except:
            pass

        y = 2
        try:
            stdscr.attron(curses.color_pair(1))
            stdscr.addstr(y, 2, "Current values:")
            stdscr.attroff(curses.color_pair(1))
            y += 1
        except:
            y += 1

        try: stdscr.addnstr(y, 4, f"Name:          {item.name[:w-20]}", w-5); y += 1
        except: y += 1
        try: stdscr.addnstr(y, 4, f"Quantity:      {item.quantity:,}", w-5); y += 1
        except: y += 1
        try: stdscr.addnstr(y, 4, f"Cost:          ${item.cost:,.2f}", w-5); y += 1
        except: y += 1
        try: stdscr.addnstr(y, 4, f"Location:      {item.location[:w-20]}", w-5); y += 1
        except: y += 1

        desc_line = item.description.replace('\n',' ').replace('\r',' ')[:w-20]
        if len(item.description) > w-20: desc_line += "..."
        try: stdscr.addnstr(y, 4, f"Description:   {desc_line}", w-5); y += 1
        except: y += 1

        try:
            stdscr.addnstr(y, 4, f"Min Value:     ${item.min_value:,.2f}", w-5); y += 1
            stdscr.addnstr(y, 4, f"Max Value:     ${item.max_value:,.2f}", w-5); y += 1
            stdscr.addnstr(y, 4, f"Sale:          ${item.sale:,.2f}", w-5); y += 1
            stdscr.addnstr(y, 4, f"Time Stamp:    {item.timestamp}", w-5); y += 1
        except:
            pass

        if CUSTOM_FIELDS:
            for field in CUSTOM_FIELDS:
                if y >= h - len(options) - 4:
                    break
                value = item.custom.get(field['name'], "")
                if value == "":
                    disp = "(empty)"
                else:
                    disp = _fmt_custom(value, field)
                label_padded = (field['label'] + ":").ljust(15)
                try:
                    stdscr.addnstr(y, 4, f"{label_padded}{disp[:w-20]}", w-5)
                    y += 1
                except:
                    y += 1

        low_thresh = item.custom.get('low_stock_threshold', 5)
        crit_thresh = item.custom.get('critical_stock', 3)
        try:
            stdscr.addnstr(y, 4, f"Low threshold: {low_thresh}", w-5); y += 1
            stdscr.addnstr(y, 4, f"Critical:      {crit_thresh}", w-5); y += 1
        except:
            y += 2

        y += 1

        max_opt_y = h - 4
        visible_options = min(len(options), max(0, max_opt_y - y))

        for i in range(visible_options):
            try:
                if i == selected_idx and not typed_input:
                    stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                    stdscr.addnstr(y + i, 2, options[i], w-3)
                    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                else:
                    stdscr.addnstr(y + i, 2, options[i], w-3)
            except:
                pass

        if visible_options < len(options):
            try:
                stdscr.addstr(y + visible_options, 2, "[some options hidden – resize taller]")
            except:
                pass

        if typed_input:
            draw_footer(stdscr, f"Enter → {typed_input}")
        else:
            draw_footer(stdscr, "↑↓:select  Enter: confirm  Esc/b: back")

        stdscr.refresh()
        key = stdscr.getch()

        if key == curses.KEY_UP:
            if selected_idx > 0:
                selected_idx -= 1
            typed_input = ""
        elif key == curses.KEY_DOWN:
            if selected_idx < len(options) - 1:
                selected_idx += 1
            typed_input = ""
        elif key == curses.KEY_ENTER or key in (10, 13):
            if not typed_input:
                return option_values[selected_idx]
            if typed_input:
                choice_str = typed_input.upper()
                if choice_str in ('0', ''):
                    return None
                if choice_str == 'C':
                    return 'C'
                if choice_str == 'L':
                    return 'L'
                if choice_str == 'R':
                    return 'R'
                try:
                    ch = int(choice_str)
                    if 1 <= ch <= 15 + len(CUSTOM_FIELDS):
                        return ch
                except ValueError:
                    pass
        elif key in (27, ord('b')):
            return None
        elif key in (curses.KEY_BACKSPACE, 127):
            if typed_input:
                typed_input = typed_input[:-1]
        elif 48 <= key <= 57:
            typed_input += chr(key)

# ──────────────────────────────────────────────────────────────────────────────
# Hardened edit_item
# ──────────────────────────────────────────────────────────────────────────────
def edit_item(stdscr, inventory, orig_idx):
    if not (0 <= orig_idx < len(inventory)):
        return
    item = inventory[orig_idx]

    part_choice = 9 + len(CUSTOM_FIELDS)  # 9 with 0 custom fields, 10 with 1, etc.
    upc_choice = part_choice + 1
    po_choice = upc_choice + 1
    date_choice = po_choice + 1
    sale_choice = date_choice + 1
    low_choice = sale_choice + 1
    crit_choice = low_choice + 1

    choice = select_field_to_edit(stdscr, item)
    if choice is None:
        return

    if choice == part_choice:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        try:
            stdscr.addstr(0, 0, f"Edit Part# – {item.name[:w-30]}")
        except:
            pass
        try:
            val = get_input(stdscr, f"Part# [{item.part_number}]: ", 2, 0, 40, "")
        except curses.error:
            val = item.part_number
        if val.strip():
            item.part_number = val.strip()
            inventory[orig_idx] = Item(
                name=item.name, quantity=item.quantity, cost=item.cost,
                min_value=item.min_value, max_value=item.max_value, sale=item.sale,
                location=item.location, description=item.description,
                timestamp=item.timestamp, part_number=item.part_number, upc=item.upc,
                **item.custom
            )
            safe_save_inventory(inventory)
        try:
            stdscr.addstr(4, 0, "Part# updated. Press any key...")
            stdscr.refresh()
            stdscr.getch()
        except:
            pass
        return

    if choice == upc_choice:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        try:
            stdscr.addstr(0, 0, f"Edit UPC – {item.name[:w-30]}")
        except:
            pass
        try:
            val = get_input(stdscr, f"UPC [{item.upc}]: ", 2, 0, 20, "", field_type="number")
        except curses.error:
            val = str(item.upc)
        try:
            item.upc = int(val) if val.strip() else 0
        except ValueError:
            item.upc = 0
        inventory[orig_idx] = Item(
            name=item.name, quantity=item.quantity, cost=item.cost,
            min_value=item.min_value, max_value=item.max_value, sale=item.sale,
            location=item.location, description=item.description,
            timestamp=item.timestamp, part_number=item.part_number, upc=item.upc,
            **item.custom
        )
        safe_save_inventory(inventory)
        try:
            stdscr.addstr(4, 0, "UPC updated. Press any key...")
            stdscr.refresh()
            stdscr.getch()
        except:
            pass
        return

    if choice == po_choice:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        try:
            stdscr.addstr(0, 0, f"Edit PO – {item.name[:w-30]}")
        except:
            pass
        try:
            val = get_input(stdscr, f"PO [{item.po}]: ", 2, 0, 40, "")
        except curses.error:
            val = item.po
        if val.strip():
            item.po = val.strip()
            inventory[orig_idx] = Item(
                name=item.name, quantity=item.quantity, cost=item.cost,
                min_value=item.min_value, max_value=item.max_value, sale=item.sale,
                location=item.location, description=item.description,
                timestamp=item.timestamp, part_number=item.part_number, upc=item.upc,
                po=item.po,
                **item.custom
            )
            safe_save_inventory(inventory)
        try:
            stdscr.addstr(4, 0, "PO updated. Press any key...")
            stdscr.refresh()
            stdscr.getch()
        except:
            pass
        return

    if choice == date_choice:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        try:
            stdscr.addstr(0, 0, f"Edit Date – {item.name[:w-30]}")
        except:
            pass
        try:
            stdscr.addstr(2, 0, f"Current: {item.date}")
        except:
            pass
        val = get_date_input(stdscr, "", 4, 0)
        if val and val not in ("__CANCEL__", "__GOBACK__"):
            item.date = val
            inventory[orig_idx] = Item(
                name=item.name, quantity=item.quantity, cost=item.cost,
                min_value=item.min_value, max_value=item.max_value, sale=item.sale,
                location=item.location, description=item.description,
                timestamp=item.timestamp, part_number=item.part_number, upc=item.upc,
                po=item.po, date=item.date,
                **item.custom
            )
            safe_save_inventory(inventory)
        try:
            stdscr.addstr(8, 0, "Date updated. Press any key...")
            stdscr.refresh()
            stdscr.getch()
        except:
            pass
        return

    # Individual custom field edit (choices 9, 10, 11, ... based on count)
    if isinstance(choice, int) and 9 <= choice < 9 + len(CUSTOM_FIELDS):
        field_idx = choice - 9
        field = CUSTOM_FIELDS[field_idx]
        new_custom = item.custom.copy()

        stdscr.clear()
        h, w = stdscr.getmaxyx()
        max_prompt_w = w - 15

        try:
            stdscr.addstr(0, 0, f"Edit Custom Field – {item.name[:w-30]}")
            stdscr.addstr(1, 0, "-" * min(60, w-1))
        except:
            pass

        curr = new_custom.get(field['name'], "")
        curr_str = f"{curr:.2f}" if isinstance(curr, (int, float)) else str(curr)
        prompt = f"{field['label']} [{curr_str[:max_prompt_w - len(field['label'])-5]}]: "

        if field['type'] == 'date':
            stdscr.addstr(3, 0, f"Edit {field['label']}")
            stdscr.addstr(4, 0, f"Current: {curr_str}")
            val = get_date_input(stdscr, "", 5, 0)
        elif field['type'] == 'list':
            options = field.get('options', [])
            stdscr.addstr(3, 0, f"Edit {field['label']}")
            stdscr.addstr(4, 0, f"Current: {curr_str}")
            for i, opt in enumerate(options):
                stdscr.addstr(5 + i, 2, f"{i+1}. {opt}")
            stdscr.addstr(5 + len(options), 0, "Enter number: ")
            stdscr.refresh()
            curses.echo()
            try:
                choice_str = stdscr.getstr(5 + len(options), 15, 3).decode('utf-8').strip()
            except:
                choice_str = ""
            curses.noecho()
            try:
                choice_num = int(choice_str)
                if 1 <= choice_num <= len(options):
                    val = options[choice_num - 1]
                else:
                    val = curr_str
            except ValueError:
                val = curr_str
        else:
            try:
                val = get_input(stdscr, prompt, 3, 0,
                                min(40, max_prompt_w - len(prompt) + 5),
                                curr_str)
            except curses.error:
                val = curr_str

        if val != curr_str:
            if field['type'] in ('number', 'money', 'decimal'):
                if not val.strip():
                    new_custom[field['name']] = 0.0
                else:
                    try:
                        new_custom[field['name']] = _round_custom(float(val), field)
                    except ValueError:
                        try:
                            stdscr.addstr(5, 2, f"Invalid {field['type']} – kept original")
                            stdscr.refresh()
                            stdscr.getch()
                        except:
                            pass
                        return
            else:
                new_custom[field['name']] = val

        inventory[orig_idx] = Item(
            name=item.name, quantity=item.quantity, cost=item.cost,
            min_value=item.min_value, max_value=item.max_value, sale=item.sale,
            location=item.location, description=item.description,
            timestamp=item.timestamp, part_number=item.part_number, upc=item.upc,
            po=item.po,
            **new_custom
        )
        safe_save_inventory(inventory)

        if field['type'] == 'list':
            msg_y = 6 + len(field.get('options', []))
        elif field['type'] == 'date':
            msg_y = 6
        else:
            msg_y = 5
        try:
            stdscr.addstr(msg_y, 0, "Custom field updated. Press any key...")
            stdscr.refresh()
            stdscr.getch()
        except:
            pass
        return

    low_choice = 14 + len(CUSTOM_FIELDS)
    if choice == low_choice:
        new_custom = item.custom.copy()
        stdscr.clear()
        try:
            stdscr.addstr(0, 0, "Edit Low Stock Threshold")
        except:
            pass
        curr = new_custom.get('low_stock_threshold', 5)
        try:
            val = get_input(stdscr, f"Low stock threshold [{curr}]: ", 2, 0, 5, str(curr))
            if val.strip():
                new_custom['low_stock_threshold'] = int(val)
        except:
            pass
        inventory[orig_idx] = Item(
            name=item.name, quantity=item.quantity, cost=item.cost,
            min_value=item.min_value, max_value=item.max_value, sale=item.sale,
            location=item.location, description=item.description,
            timestamp=item.timestamp,
            **new_custom
        )
        safe_save_inventory(inventory)
        try:
            stdscr.addstr(4, 0, "Threshold updated. Press any key...")
            stdscr.refresh()
            stdscr.getch()
        except:
            pass
        return

    crit_choice = 15 + len(CUSTOM_FIELDS)
    if choice == crit_choice:
        new_custom = item.custom.copy()
        stdscr.clear()
        try:
            stdscr.addstr(0, 0, "Edit Critical Stock Threshold")
        except:
            pass
        curr = new_custom.get('critical_stock', 3)
        try:
            val = get_input(stdscr, f"Critical stock threshold [{curr}]: ", 2, 0, 5, str(curr))
            if val.strip():
                new_custom['critical_stock'] = int(val)
        except:
            pass
        inventory[orig_idx] = Item(
            name=item.name, quantity=item.quantity, cost=item.cost,
            min_value=item.min_value, max_value=item.max_value, sale=item.sale,
            location=item.location, description=item.description,
            timestamp=item.timestamp,
            **new_custom
        )
        safe_save_inventory(inventory)
        try:
            stdscr.addstr(4, 0, "Threshold updated. Press any key...")
            stdscr.refresh()
            stdscr.getch()
        except:
            pass
        return

    h, w = stdscr.getmaxyx()
    if h < 20 or w < 60:
        try:
            stdscr.clear()
            stdscr.addstr(h//2 - 2, 2, "Window too small for editing")
            stdscr.addstr(h//2, 2, "Please enlarge terminal")
            stdscr.refresh()
            stdscr.getch()
        except:
            pass
        return

    stdscr.clear()
    try:
        stdscr.addstr(0, 0, "Edit Item (leave blank to keep current value)")
    except:
        pass

    new_name      = item.name
    new_qty       = item.quantity
    new_cost      = item.cost
    new_location  = item.location
    new_desc      = item.description
    new_min       = item.min_value
    new_max       = item.max_value
    new_sale      = item.sale
    new_timestamp = item.timestamp
    new_part_number = item.part_number
    new_upc       = item.upc
    new_po        = item.po
    new_date      = item.date

    y = 2
    max_prompt_w = w - 20

    def safe_input(label, default_val, y_pos, max_len):
        try:
            prompt = f"{label} [{str(default_val)[:max_prompt_w - len(label) - 5]}]: "
            val = get_input(stdscr, prompt, y_pos, 0, min(max_len, max_prompt_w), "")
            return val if val.strip() else default_val
        except curses.error:
            return default_val

    if choice in (1, 8):
        new_name = safe_input("Name", new_name, y, 60)
        y += 1

    if choice in (2, 8):
        new_qty_str = safe_input("Quantity", new_qty, y, 10)
        try: new_qty = int(new_qty_str)
        except: pass
        y += 1

    if choice in (3, 8):
        new_cost_str = safe_input("Cost ($)", f"{new_cost:.2f}", y, 12)
        try: new_cost = float(new_cost_str)
        except: pass
        y += 1

    if choice in (4, 8):
        new_location = safe_input("Location", new_location, y, 60)
        y += 1

    if choice in (5, 8):
        new_desc = safe_input("Description", new_desc, y, 60)
        y += 1

    if choice in (6, 8):
        new_min_str = safe_input("Min value ($)", f"{new_min:.2f}", y, 12)
        try: new_min = float(new_min_str)
        except: pass
        y += 1

    if choice in (7, 8):
        new_max_str = safe_input("Max value ($)", f"{new_max:.2f}", y, 12)
        try: new_max = float(new_max_str)
        except: pass
        y += 1

    sale_choice = 13 + len(CUSTOM_FIELDS)
    if choice in (sale_choice, 8):
        new_sale_str = safe_input("Sale ($)", f"{new_sale:.2f}", y, 12)
        try: new_sale = float(new_sale_str)
        except: pass
        y += 1

    part_choice = 9 + len(CUSTOM_FIELDS)
    if choice in (part_choice, 8):
        new_part_number = safe_input("Part#", item.part_number, y, 60)
        y += 1

    upc_choice = 10 + len(CUSTOM_FIELDS)
    if choice in (upc_choice, 8):
        new_upc_str = safe_input("UPC", str(item.upc), y, 20)
        try: new_upc = int(new_upc_str)
        except: pass
        y += 1

    po_choice = 11 + len(CUSTOM_FIELDS)
    if choice in (po_choice, 8):
        new_po = safe_input("PO", item.po, y, 40)
        y += 1

    date_choice = 12 + len(CUSTOM_FIELDS)
    if choice in (date_choice, 8):
        stdscr.addstr(y, 0, f"Edit Date")
        stdscr.addstr(y + 1, 0, f"Current: {new_date}")
        val = get_date_input(stdscr, "", y + 2, 0)
        if val and val not in ("__CANCEL__", "__GOBACK__"):
            new_date = val
        y += 5

    # Custom fields section
    new_custom = item.custom.copy()
    all_fields_choice = 8 + len(CUSTOM_FIELDS)
    if choice == 8 or choice == all_fields_choice:
        y += 2
        try:
            stdscr.addnstr(y-1, 0, "-" * min(40, w-1), w-1)
            y += 1
        except:
            pass

        avail_lines = h - y - 5
        fields_per_screen = max(1, avail_lines // 2)

        for i, field in enumerate(CUSTOM_FIELDS):
            if i >= fields_per_screen:
                try:
                    stdscr.addstr(y, 0, "[more fields hidden – resize taller]")
                except:
                    pass
                break

            if y >= h - 4:
                break

            curr = new_custom.get(field['name'], "")
            curr_str = f"{curr:.2f}" if isinstance(curr, (int,float)) else str(curr)
            prompt = f"{field['label']} [{curr_str[:max_prompt_w - len(field['label']) - 5]}]: "

            if field['type'] == 'date':
                stdscr.addstr(y, 0, f"Edit {field['label']}")
                val = get_date_input(stdscr, "", y + 1, 0)
                y += 4
            elif field['type'] == 'list':
                options = field.get('options', [])
                stdscr.addstr(y, 0, f"Edit {field['label']}")
                stdscr.addstr(y + 1, 0, f"Current: {curr_str}")
                for i, opt in enumerate(options):
                    stdscr.addstr(y + 2 + i, 2, f"{i+1}. {opt}")
                stdscr.addstr(y + 2 + len(options), 0, "Enter number: ")
                stdscr.refresh()
                curses.echo()
                try:
                    choice_str = stdscr.getstr(y + 2 + len(options), 15, 3).decode('utf-8').strip()
                except:
                    choice_str = ""
                curses.noecho()
                try:
                    choice_num = int(choice_str)
                    if 1 <= choice_num <= len(options):
                        val = options[choice_num - 1]
                    else:
                        val = curr_str
                except ValueError:
                    val = curr_str
                y += 4 + len(options)
            else:
                val = ""
                try:
                    val = get_input(stdscr, prompt, y, 0,
                                    min(40, max_prompt_w - len(prompt) + 5),
                                    curr_str)
                except curses.error:
                    pass

            if val != curr_str:
                if field['type'] in ('number', 'money', 'decimal'):
                    if not val.strip():
                        new_custom[field['name']] = 0.0
                    else:
                        try:
                            new_custom[field['name']] = _round_custom(float(val), field)
                        except ValueError:
                            try:
                                stdscr.addstr(y + 1, 2, f"Invalid {field['type']} – kept original")
                                stdscr.refresh()
                                stdscr.getch()
                            except:
                                pass
                else:
                    new_custom[field['name']] = val

            if field['type'] != 'date':
                y += 2

    # Final validation & save
    errors = validate_inputs(new_name, str(new_qty), str(new_cost))
    if errors:
        stdscr.clear()
        try:
            stdscr.addstr(2, 0, "Cannot update:")
            for i, err in enumerate(errors, 4):
                stdscr.addnstr(i, 2, f"* {err}", w-4)
            stdscr.addstr(len(errors)+6, 0, "Press any key...")
            stdscr.getch()
        except:
            pass
        return

    inventory[orig_idx] = Item(
        name=new_name, quantity=new_qty, cost=new_cost,
        min_value=new_min, max_value=new_max, sale=new_sale,
        location=new_location, description=new_desc,
        timestamp=new_timestamp,
        part_number=new_part_number, upc=new_upc, po=new_po, date=new_date,
        **new_custom
    )

    try:
        safe_save_inventory(inventory)
        stdscr.addstr(min(y + 2, h-4), 0, "Item updated successfully. Press any key...")
    except Exception as e:
        try:
            stdscr.addstr(min(y + 2, h-4), 0, f"Save failed: {str(e)[:w-20]}")
        except:
            pass
    try:
        stdscr.refresh()
        stdscr.getch()
    except:
        pass
        
def edit_custom_fields_only(stdscr, inventory, orig_idx):
    if not (0 <= orig_idx < len(inventory)):
        return
    item = inventory[orig_idx]
    new_custom = item.custom.copy()

    stdscr.clear()
    h, w = stdscr.getmaxyx()

    if h < 12 or w < 50 or not CUSTOM_FIELDS:
        try:
            stdscr.addstr(2, 2, "No custom fields defined or window too small.")
            stdscr.addstr(4, 2, "Press any key...")
            stdscr.refresh()
            stdscr.getch()
        except:
            pass
        return

    y = 2
    try:
        stdscr.addstr(0, 0, f"Edit Custom Fields – {item.name[:w-30]}")
        stdscr.addstr(1, 0, "-" * min(60, w-1))
    except:
        pass

    max_prompt_w = w - 15

    for field in CUSTOM_FIELDS:
        if y >= h - 5:
            try:
                stdscr.addstr(y, 2, "[Not enough space – resize taller]")
            except:
                pass
            break

        curr = new_custom.get(field['name'], "")
        curr_str = f"{curr:.2f}" if isinstance(curr, (int,float)) else str(curr)
        prompt = f"{field['label']} [{curr_str[:max_prompt_w - len(field['label'])-5]}]: "

        if field['type'] == 'date':
            stdscr.addstr(y, 0, f"Edit {field['label']}")
            val = get_date_input(stdscr, "", y + 1, 0)
            y += 4
        elif field['type'] == 'list':
            options = field.get('options', [])
            stdscr.addstr(y, 0, f"Edit {field['label']}")
            stdscr.addstr(y + 1, 0, f"Current: {curr_str}")
            for i, opt in enumerate(options):
                stdscr.addstr(y + 2 + i, 2, f"{i+1}. {opt}")
            stdscr.addstr(y + 2 + len(options), 0, "Enter number: ")
            stdscr.refresh()
            curses.echo()
            try:
                choice_str = stdscr.getstr(y + 2 + len(options), 15, 3).decode('utf-8').strip()
            except:
                choice_str = ""
            curses.noecho()
            try:
                choice_num = int(choice_str)
                if 1 <= choice_num <= len(options):
                    val = options[choice_num - 1]
                else:
                    val = curr_str
            except ValueError:
                val = curr_str
            y += 4 + len(options)
        else:
            try:
                val = get_input(stdscr, prompt, y, 0,
                                min(40, max_prompt_w - len(prompt) + 5),
                                curr_str)
            except curses.error:
                val = curr_str

        if val != curr_str:
            if field['type'] in ('number', 'money', 'decimal'):
                if not val.strip():
                    new_custom[field['name']] = 0.0
                else:
                    try:
                        new_custom[field['name']] = _round_custom(float(val), field)
                    except ValueError:
                        try:
                            stdscr.addstr(y + 1, 2, f"Invalid {field['type']} – kept original")
                            stdscr.refresh()
                            stdscr.getch()
                        except:
                            pass
            else:
                new_custom[field['name']] = val

        y += 2

    # Save updated item
    inventory[orig_idx] = Item(
        name=item.name, quantity=item.quantity, cost=item.cost,
        min_value=item.min_value, max_value=item.max_value, sale=item.sale,
        location=item.location, description=item.description,
        timestamp=item.timestamp,
        **new_custom
    )

    safe_save_inventory(inventory)

    try:
        stdscr.addstr(min(y + 1, h-4), 2, "Custom fields updated. Press any key...")
        stdscr.refresh()
        stdscr.getch()
    except:
        pass

def delete_item(stdscr, inventory, orig_idx):
    global DELETE_CONFIRM_ENABLED
    if not (0 <= orig_idx < len(inventory)):
        return False
    item = inventory[orig_idx]

    if DELETE_CONFIRM_ENABLED:
        h, w = stdscr.getmaxyx()
        prompt = f"Delete '{item.name}'? (y/n)"
        try:
            stdscr.addnstr(h-1, 0, " " * (w - 1), w - 1)
            stdscr.addnstr(h-1, 0, prompt, w - 1)
        except curses.error:
            pass
        stdscr.refresh()
        while True:
            ch = stdscr.getch()
            if ch in (ord('y'), ord('Y')):
                del inventory[orig_idx]
                safe_save_inventory(inventory)
                return True
            elif ch in (ord('n'), ord('N')):
                return False
    else:
        del inventory[orig_idx]
        safe_save_inventory(inventory)
        return True

def view_details(stdscr, inventory, orig_idx):
    if not (0 <= orig_idx < len(inventory)):
        return False
    item = inventory[orig_idx]

    while True:
        stdscr.clear()
        y = 0

        standard_labels = ["Name", "Quantity", "Cost", "Location", "Part#", "UPC", "PO", "Date", "Low threshold", "Critical", "Min Value", "Max Value", "Sale", "Margin", "Time Stamp", "Description"]
        all_labels = standard_labels + [f['label'] for f in CUSTOM_FIELDS]
        label_width = max(len(l) for l in all_labels) + 2

        stdscr.addstr(y, 0, "Item Details"); y += 2

        y = draw_detail_line(stdscr, y, "Name", item.name, label_width)
        y = draw_detail_line(stdscr, y, "Quantity", str(item.quantity), label_width)
        y = draw_detail_line(stdscr, y, "Cost", f"${item.cost:,.2f}", label_width)
        y = draw_detail_line(stdscr, y, "Location", item.location, label_width)
        y = draw_detail_line(stdscr, y, "Part#", item.part_number, label_width)
        y = draw_detail_line(stdscr, y, "UPC", str(item.upc), label_width)
        y = draw_detail_line(stdscr, y, "PO", item.po, label_width)
        y = draw_detail_line(stdscr, y, "Date", item.date, label_width)

        for field in CUSTOM_FIELDS:
            value = item.custom.get(field['name'], "")
            disp = _fmt_custom(value, field)
            y = draw_detail_line(stdscr, y, field['label'], disp, label_width)

        low_thresh = item.custom.get('low_stock_threshold', 5)
        crit_thresh = item.custom.get('critical_stock', 3)
        y = draw_detail_line(stdscr, y, "Low threshold", str(low_thresh), label_width)
        y = draw_detail_line(stdscr, y, "Critical", str(crit_thresh), label_width)

        y = draw_detail_line(stdscr, y, "Min Value", f"${item.min_value:,.2f}", label_width)
        y = draw_detail_line(stdscr, y, "Max Value", f"${item.max_value:,.2f}", label_width)
        y = draw_detail_line(stdscr, y, "Sale", f"${item.sale:,.2f}", label_width)

        margin = item.margin_percent
        margin_str = f"{margin:.1f}%" if margin is not None else "N/A"
        y = draw_detail_line(stdscr, y, "Margin", margin_str, label_width)
        y = draw_detail_line(stdscr, y, "Time Stamp", item.timestamp, label_width)
        y += 1

        y = draw_detail_line(stdscr, y, "Description", item.description, label_width)
        y += 2

        draw_footer(stdscr, "e: edit   d: delete   c: configuration   other keys: back")

        key = stdscr.getch()

        if key == ord('e'):
            edit_item(stdscr, inventory, orig_idx)
            item = inventory[orig_idx]  # refresh
        elif key == ord('d'):
            deleted = delete_item(stdscr, inventory, orig_idx)
            if deleted:
                return True
        elif key == ord('c'):
            config_menu(stdscr, inventory)
            curses.init_pair(1, THEME_COLOR, -1)
            curses.init_pair(2, curses.COLOR_YELLOW, -1)
            curses.init_pair(3, curses.COLOR_RED,    -1)
            curses.init_pair(4, curses.COLOR_GREEN,  -1)
        else:
            return False

def search_mode(stdscr):
    stdscr.clear()
    stdscr.addstr(0, 0, "Search term (empty to clear):")
    term = get_input(stdscr, "> ", 1, 0, 60)
    return term.strip()

FILTERABLE_COLUMNS = ['location', 'po', 'date']

def get_filterable_columns():
    global CUSTOM_FIELDS
    load_config()
    cols = FILTERABLE_COLUMNS.copy()
    for field in CUSTOM_FIELDS:
        if field.get('type') == 'list':
            cols.append('custom_' + field['name'])
    return cols

def get_unique_values(inventory, column_key):
    global CUSTOM_FIELDS
    load_config()
    
    if column_key.startswith('custom_'):
        field_name = column_key[7:]
        for field in CUSTOM_FIELDS:
            if field['name'] == field_name and field.get('type') == 'list':
                return sorted(field.get('options', []))
        return []
    
    if column_key == 'location':
        values = set()
        for item in inventory:
            if item.location:
                values.add(item.location)
        return sorted(values)
    
    if column_key == 'po':
        values = set()
        for item in inventory:
            if item.po:
                values.add(item.po)
        return sorted(values)
    
    if column_key == 'date':
        values = set()
        for item in inventory:
            if item.date:
                values.add(item.date)
        return sorted(values)
    
    return []

def filter_select_menu(stdscr, inventory, column_key):
    global CUSTOM_FIELDS
    load_config()
    
    h, w = stdscr.getmaxyx()
    
    if column_key.startswith('custom_'):
        field_name = column_key[7:]
        for field in CUSTOM_FIELDS:
            if field['name'] == field_name:
                label = field.get('label', field_name)
                options = sorted(field.get('options', []))
                break
        else:
            return None
    else:
        label = AVAILABLE_COLUMNS.get(column_key, {}).get('label', column_key)
        options = get_unique_values(inventory, column_key)
    
    if not options:
        return None
    
    if len(options) > 15:
        return None
    
    current_option = 0
    while True:
        stdscr.clear()
        stdscr.attron(curses.color_pair(1))
        stdscr.addstr(0, 0, f"Filter by {label}".center(min(w, 60)))
        stdscr.attroff(curses.color_pair(1))
        stdscr.addstr(1, 0, "")
        stdscr.addstr(2, 0, "↑↓ navigate  Enter select  Esc/b cancel")
        stdscr.addstr(3, 0, "─" * min(w, 60))
        
        visible_options = min(h - 6, len(options))
        start_idx = max(0, current_option - visible_options + 1)
        
        for i in range(start_idx, min(start_idx + visible_options, len(options))):
            y = i - start_idx + 4
            if i == current_option:
                stdscr.attron(curses.color_pair(4))
                stdscr.addstr(y, 0, f"> {i+1}. {options[i]}")
                stdscr.attroff(curses.color_pair(4))
            else:
                try:
                    stdscr.addstr(y, 0, f"  {i+1}. {options[i]}")
                except curses.error:
                    pass
        
        stdscr.refresh()
        key = stdscr.getch()
        
        if key in (27, ord('b')):
            return None
        
        if key == curses.KEY_UP and current_option > 0:
            current_option -= 1
        elif key == curses.KEY_DOWN and current_option < len(options) - 1:
            current_option += 1
        elif key in (10, curses.KEY_ENTER, ord(' ')):
            return options[current_option]
        elif key == curses.KEY_RESIZE:
            continue

def draw_menu(stdscr, selected_row_idx, inventory, search_term="", sort_key='name', sort_directions=None, scroll_offset=0, column_filter=None):
    global COLUMNS, AVAILABLE_COLUMNS, CUSTOM_FIELDS
    load_config()
    if sort_directions is None:
        sort_directions = {'name': 1, 'quantity': 1, 'location': 1}
    if column_filter is None:
        column_filter = {}

    stdscr.clear()
    h, w = stdscr.getmaxyx()

    term = search_term.lower()
    filtered = [item for item in inventory if (not HIDE_ZERO_QTY_ENABLED or item.quantity > 0) and (term in item.name.lower() or term in item.description.lower() or term in item.location.lower() or term in item.part_number.lower())]

    for col_key, filter_val in column_filter.items():
        if col_key.startswith('custom_'):
            field_name = col_key[7:]
            filtered = [item for item in filtered if item.custom.get(field_name, '') == filter_val]
        elif col_key == 'location':
            filtered = [item for item in filtered if item.location == filter_val]
        elif col_key == 'po':
            filtered = [item for item in filtered if item.po == filter_val]
        elif col_key == 'date':
            filtered = [item for item in filtered if item.date == filter_val]

    direction = sort_directions.get(sort_key, 1)

    def get_sort_value(item):
        if sort_key == 'name':
            return item.name.lower()
        elif sort_key == 'quantity':
            return item.quantity
        elif sort_key == 'location':
            return item.location.lower()
        elif sort_key == 'cost':
            return item.cost
        elif sort_key == 'description':
            return item.description.lower()
        elif sort_key == 'min_value':
            return item.min_value
        elif sort_key == 'max_value':
            return item.max_value
        elif sort_key == 'sale':
            return item.sale
        elif sort_key == 'timestamp':
            return item.timestamp
        elif sort_key == 'part_number':
            return item.part_number.lower()
        elif sort_key == 'upc':
            return item.upc
        elif sort_key == 'po':
            return item.po.lower()
        elif sort_key == 'date':
            return item.date
        elif sort_key.startswith('custom_'):
            val = item.custom.get(sort_key[7:], '')
            if isinstance(val, (int, float)):
                return val
            return str(val).lower()
        return ''

    filtered.sort(key=get_sort_value, reverse=(direction < 0))

    original_indices = [inventory.index(item) for item in filtered]

    stdscr.attron(curses.color_pair(1))
    stdscr.addstr(0, 0, PROGRAM_NAME.center(min(w, 100)))
    stdscr.attroff(curses.color_pair(1))
    stdscr.addstr(1, 0, "")

    dir_symbol = "↓" if direction > 0 else "↑"
    
    filter_str = ""
    if column_filter:
        for col_key, val in column_filter.items():
            if col_key.startswith('custom_'):
                field_name = col_key[7:]
                for field in CUSTOM_FIELDS:
                    if field['name'] == field_name:
                        label = field.get('label', field_name)
                        break
                else:
                    label = col_key
            else:
                label = AVAILABLE_COLUMNS.get(col_key, {}).get('label', col_key)
            filter_str = f"{label}={val}"
            break
    
    stdscr.addstr(2, 0, f"Search: {search_term or '(none)'}   Filter: {filter_str or '(none)'}   Sort: {sort_key} {dir_symbol}   (s:search f:filter #:sort ESC:clear)")

    stdscr.addstr(3, 0, "─" * min(w, 100))
    stdscr.addstr(4, 0, "")

    header_parts = []
    for idx, col in enumerate(COLUMNS):
        key = col['key']
        if key.startswith('custom_'):
            label = col.get('label')
            if not label:
                for field in CUSTOM_FIELDS:
                    if 'custom_' + field['name'] == key:
                        label = field['label']
                        break
            if not label:
                label = key
        else:
            label = AVAILABLE_COLUMNS[key]['label']
        label = f"{label}({idx + 1})"
        width = col['width']
        align = col.get('align', 'left')
        if align == 'right':
            header_parts.append(label.rjust(width))
        elif align == 'center':
            header_parts.append(label.center(width))
        else:
            header_parts.append(label.ljust(width))
    headers = "  ".join(header_parts)
    stdscr.addstr(5, 0, headers[:w])
    header_dashes = "  ".join([col['width'] * '-' for col in COLUMNS])
    stdscr.addstr(6, 0, header_dashes[:w])
    
    for idx, item in enumerate(filtered):
        if idx < scroll_offset:
            continue
        y = idx - scroll_offset + 7
        if y >= h - 3: break

        row_parts = []
        for col in COLUMNS:
            key = col['key']
            width = col['width']
            align = col.get('align', 'left')
            if key.startswith('custom_'):
                value = item.custom.get(key[7:], '')
                cfield = next((f for f in CUSTOM_FIELDS if f['name'] == key[7:]), None)
            else:
                value = getattr(item, key, '')
                cfield = None
            if value is None:
                value = ''
            
            if key == 'quantity':
                disp = f"{value:,}"
            elif key in ('cost', 'min_value', 'max_value', 'sale'):
                disp = f"${value:,.2f}"
            elif cfield is not None and isinstance(value, (int, float)):
                disp = _fmt_custom(value, cfield)
            else:
                disp = str(value)
            
            if len(disp) >= width - 1:
                disp = disp[:width-2] + '…'
            
            if align == 'right':
                row_parts.append(disp.rjust(width))
            elif align == 'center':
                row_parts.append(disp.center(width))
            else:
                row_parts.append(disp.ljust(width))
        
        line = "  ".join(row_parts)

        color_pair = 0
        if COLOR_CRITICAL_ENABLED:
            if item.stock_status == "critical": color_pair = 3
            elif item.stock_status == "low":    color_pair = 2

        if color_pair: stdscr.attron(curses.color_pair(color_pair))
        if idx == selected_row_idx: stdscr.attron(curses.A_REVERSE | curses.color_pair(1))

        try:
            stdscr.addnstr(y, 0, line, w-1)
        except curses.error:
            pass

        if idx == selected_row_idx: stdscr.attroff(curses.A_REVERSE | curses.color_pair(1))
        if color_pair: stdscr.attroff(curses.color_pair(color_pair))

    total_items = len(filtered)

    stats = f"Items:{total_items}"
    sale_control = "r:sale " if SALE_ENABLED else ""
    controls = f"q:quit ESC:back a:add e:edit d:delete {sale_control}h:history c:configure ↑↓:navigate ENTER:details"
    footer = f"{stats} | {controls}"
    draw_footer(stdscr, footer)

    return filtered, original_indices, scroll_offset

# ──────────────────────────────────────────────────────────────────────────────
# Size checking helper
# ──────────────────────────────────────────────────────────────────────────────

MIN_HEIGHT = 20
MIN_WIDTH  = 70

def check_size(stdscr):
    h, w = stdscr.getmaxyx()
    if h < MIN_HEIGHT or w < MIN_WIDTH:
        stdscr.clear()
        msg1 = f"Terminal too small ({w}x{h}). Need at least {MIN_WIDTH}x{MIN_HEIGHT}"
        msg2 = "Resize window and press any key..."
        try:
            stdscr.addstr(h//2 - 1, max(0, (w - len(msg1))//2), msg1)
            stdscr.addstr(h//2 + 1, max(0, (w - len(msg2))//2), msg2)
        except curses.error:
            pass
        stdscr.refresh()
        stdscr.getch()
        return False
    return True



# ──────────────────────────────────────────────────────────────────────────────
# Split-screen view
# ──────────────────────────────────────────────────────────────────────────────
def draw_split_screen(stdscr, selected_row_idx, inventory, search_term="", sort_key="name", sort_directions=None, scroll_offset=0, column_filter=None):
    """Draw split-screen view: item list on left (60%), item details on right (40%)"""
    global COLUMNS, AVAILABLE_COLUMNS, CUSTOM_FIELDS
    load_config()
    if sort_directions is None:
        sort_directions = {"name": 1, "quantity": 1, "location": 1}
    if column_filter is None:
        column_filter = {}

    stdscr.clear()
    h, w = stdscr.getmaxyx()

    # If terminal too narrow for split-screen, fall back to normal view
    if w < 50:
        return draw_menu(stdscr, selected_row_idx, inventory, search_term, sort_key, sort_directions, scroll_offset, column_filter)

    # Calculate split: 60% list, 40% details
    list_width = int(w * 0.6)
    details_width = w - list_width - 1  # -1 for separator

    # Ensure minimum widths
    if list_width < 30:
        list_width = 30
        details_width = w - list_width - 1
    if details_width < 20:
        details_width = 20
        list_width = w - details_width - 1

    term = search_term.lower()
    filtered = [item for item in inventory if (not HIDE_ZERO_QTY_ENABLED or item.quantity > 0) and (term in item.name.lower() or term in item.description.lower() or term in item.location.lower() or term in item.part_number.lower())]

    for col_key, filter_val in column_filter.items():
        if col_key.startswith("custom_"):
            field_name = col_key[7:]
            filtered = [item for item in filtered if item.custom.get(field_name, "") == filter_val]
        elif col_key == "location":
            filtered = [item for item in filtered if item.location == filter_val]
        elif col_key == "po":
            filtered = [item for item in filtered if item.po == filter_val]
        elif col_key == "date":
            filtered = [item for item in filtered if item.date == filter_val]

    direction = sort_directions.get(sort_key, 1)

    def get_sort_value(item):
        if sort_key == "name":
            return item.name.lower()
        elif sort_key == "quantity":
            return item.quantity
        elif sort_key == "location":
            return item.location.lower()
        elif sort_key == "cost":
            return item.cost
        elif sort_key == "description":
            return item.description.lower()
        elif sort_key == "min_value":
            return item.min_value
        elif sort_key == "max_value":
            return item.max_value
        elif sort_key == "sale":
            return item.sale
        elif sort_key == "timestamp":
            return item.timestamp
        elif sort_key == "part_number":
            return item.part_number.lower()
        elif sort_key == "upc":
            return item.upc
        elif sort_key == "po":
            return item.po.lower()
        elif sort_key == "date":
            return item.date
        elif sort_key.startswith("custom_"):
            val = item.custom.get(sort_key[7:], "")
            if isinstance(val, (int, float)):
                return val
            return str(val).lower()
        return ''

    filtered.sort(key=get_sort_value, reverse=(direction < 0))

    original_indices = [inventory.index(item) for item in filtered]

    # Draw LEFT PANE (Item List)
    stdscr.attron(curses.color_pair(1))
    stdscr.addstr(0, 0, PROGRAM_NAME.center(min(list_width, 100)))
    stdscr.attroff(curses.color_pair(1))
    stdscr.addstr(1, 0, "")

    dir_symbol = "↓" if direction > 0 else "↑"

    filter_str = ""
    if column_filter:
        for col_key, val in column_filter.items():
            if col_key.startswith("custom_"):
                field_name = col_key[7:]
                for field in CUSTOM_FIELDS:
                    if field["name"] == field_name:
                        label = field.get("label", field_name)
                        break
                else:
                    label = col_key
            else:
                label = AVAILABLE_COLUMNS.get(col_key, {}).get("label", col_key)
            filter_str = f"{label}={val}"
            break

    stdscr.addstr(2, 0, f"Search: {search_term or '(none)'}   Filter: {filter_str or '(none)'}   Sort: {sort_key} {dir_symbol}   (s:search f:filter #:sort ESC:clear)")

    stdscr.addstr(3, 0, "─" * min(w, 100))
    stdscr.addstr(4, 0, "")

    # Header for list pane
    header_parts = []
    for idx, col in enumerate(COLUMNS):
        key = col["key"]
        if key.startswith("custom_"):
            label = col.get("label")
            if not label:
                for field in CUSTOM_FIELDS:
                    if "custom_" + field["name"] == key:
                        label = field["label"]
                        break
            if not label:
                label = key
        else:
            label = AVAILABLE_COLUMNS[key]["label"]
        label = f"{label}({idx + 1})"
        width = col["width"]
        align = col.get("align", "left")
        if align == "right":
            header_parts.append(label.rjust(width))
        elif align == "center":
            header_parts.append(label.center(width))
        else:
            header_parts.append(label.ljust(width))
    headers = "  ".join(header_parts)
    stdscr.addstr(5, 0, headers[:list_width])
    header_dashes = "  ".join([col["width"] * "-" for col in COLUMNS])
    stdscr.addstr(6, 0, header_dashes[:list_width])

    # Draw list items
    for idx, item in enumerate(filtered):
        if idx < scroll_offset:
            continue
        y = idx - scroll_offset + 7
        if y >= h - 3:
            break

        row_parts = []
        for col in COLUMNS:
            key = col["key"]
            width = col["width"]
            align = col.get("align", "left")
            if key.startswith("custom_"):
                value = item.custom.get(key[7:], "")
                cfield = next((f for f in CUSTOM_FIELDS if f["name"] == key[7:]), None)
            else:
                value = getattr(item, key, "")
                cfield = None
            if value is None:
                value = ""

            if key == "quantity":
                disp = f"{value:,}"
            elif key in ("cost", "min_value", "max_value", "sale"):
                disp = f"${value:,.2f}"
            elif cfield is not None and isinstance(value, (int, float)):
                disp = _fmt_custom(value, cfield)
            else:
                disp = str(value)

            if len(disp) >= width - 1:
                disp = disp[:width - 2] + "…"

            if align == "right":
                row_parts.append(disp.rjust(width))
            elif align == "center":
                row_parts.append(disp.center(width))
            else:
                row_parts.append(disp.ljust(width))

        line = "  ".join(row_parts)

        color_pair = 0
        if COLOR_CRITICAL_ENABLED:
            if item.stock_status == "critical":
                color_pair = 3
            elif item.stock_status == "low":
                color_pair = 2

        if color_pair:
            stdscr.attron(curses.color_pair(color_pair))
        if idx == selected_row_idx:
            stdscr.attron(curses.A_REVERSE | curses.color_pair(1))

        try:
            stdscr.addnstr(y, 0, line, list_width - 1)
        except curses.error:
            pass

        if idx == selected_row_idx:
            stdscr.attroff(curses.A_REVERSE | curses.color_pair(1))
        if color_pair:
            stdscr.attroff(curses.color_pair(color_pair))

    # Draw separator line (skip top header rows 0-4)
    for row in range(5, h):
        try:
            stdscr.addch(row, list_width, "│")
        except curses.error:
            pass

    # Draw RIGHT PANE (Item Details)
    if filtered and 0 <= selected_row_idx < len(filtered):
        item = filtered[selected_row_idx]
        orig_idx = original_indices[selected_row_idx]

        # Details header
        try:
            stdscr.addstr(5, list_width + 1, "Item Details".center(details_width))
        except curses.error:
            pass

        detail_y = 7
        # Basic info
        try:
            stdscr.addstr(detail_y, list_width + 2, f"Name: {item.name}")
        except curses.error:
            pass
        detail_y += 1
        try:
            stdscr.addstr(detail_y, list_width + 2, f"Part #: {item.part_number or '(none)'}")
        except curses.error:
            pass
        detail_y += 1
        try:
            stdscr.addstr(detail_y, list_width + 2, f"UPC: {item.upc or '(none)'}")
        except curses.error:
            pass
        detail_y += 1
        try:
            stdscr.addstr(detail_y, list_width + 2, f"Description: {item.description or '(none)'}")
        except curses.error:
            pass
        detail_y += 1
        try:
            stdscr.addstr(detail_y, list_width + 2, f"Location: {item.location}")
        except curses.error:
            pass
        detail_y += 1
        try:
            stdscr.addstr(detail_y, list_width + 2, f"Quantity: {item.quantity:,}")
        except curses.error:
            pass
        detail_y += 1

        if MONETIZATION_ENABLED:
            try:
                stdscr.addstr(detail_y, list_width + 2, f"Cost: ${item.cost:,.2f}")
            except curses.error:
                pass
            detail_y += 1
            try:
                stdscr.addstr(detail_y, list_width + 2, f"Price: ${item.sale:,.2f}")
            except curses.error:
                pass
            detail_y += 1
            try:
                stdscr.addstr(detail_y, list_width + 2, f"Min Value: ${item.min_value:,.2f}")
            except curses.error:
                pass
            detail_y += 1
            try:
                stdscr.addstr(detail_y, list_width + 2, f"Max Value: ${item.max_value:,.2f}")
            except curses.error:
                pass
            detail_y += 1

        if PO_ENABLED:
            try:
                stdscr.addstr(detail_y, list_width + 2, f"PO #: {item.po or '(none)'}")
            except curses.error:
                pass
            detail_y += 1

        try:
            stdscr.addstr(detail_y, list_width + 2, f"Date Added: {item.date}")
        except curses.error:
            pass
        detail_y += 1

        # Custom fields
        if item.custom:
            detail_y += 1
            try:
                stdscr.addstr(detail_y, list_width + 2, "Custom Fields:")
            except curses.error:
                pass
            detail_y += 1
            for field in CUSTOM_FIELDS:
                key = field["name"]
                value = item.custom.get(key, "")
                if value:
                    label = field.get("label", key)
                    try:
                        stdscr.addstr(detail_y, list_width + 4, f"{label}: {value}")
                    except curses.error:
                        pass
                    detail_y += 1

        # Status indicators
        detail_y += 1
        if COLOR_CRITICAL_ENABLED:
            status = item.stock_status.upper()
            if status == "CRITICAL":
                stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
                try:
                    stdscr.addstr(detail_y, list_width + 2, f"STOCK STATUS: {status}")
                except curses.error:
                    pass
                stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)
            elif status == "LOW":
                stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                try:
                    stdscr.addstr(detail_y, list_width + 2, f"STOCK STATUS: {status}")
                except curses.error:
                    pass
                stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
            else:
                try:
                    stdscr.addstr(detail_y, list_width + 2, f"STOCK STATUS: OK")
                except curses.error:
                    pass

    else:
        # No items or no selection
        try:
            stdscr.addstr(5, list_width + 2, "No items to display")
        except curses.error:
            pass

    # Full-width footer (same format as draw_menu)
    total_items = len(filtered)
    stats = f"Items:{total_items}"
    sale_control = "r:sale " if SALE_ENABLED else ""
    controls = f"q:quit ESC:back a:add e:edit d:delete {sale_control}h:history c:configure ↑↓:navigate ENTER:details"
    footer = f"{stats} | {controls}"
    draw_footer(stdscr, footer)

    return filtered, original_indices, scroll_offset
# ──────────────────────────────────────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────────────────────────────────────

def show_splash(stdscr, program_name=None, subtitle=None):
    program_name = program_name if program_name is not None else PROGRAM_NAME
    subtitle = subtitle if subtitle is not None else SUBTITLE
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, THEME_COLOR, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_RED,    -1)
    curses.init_pair(4, curses.COLOR_GREEN,  -1)

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        if h < 15 or w < 50:
            try:
                stdscr.addstr(h//2, 0, "Terminal too small for splash. Enlarge and press any key...")
            except curses.error:
                pass
            stdscr.refresh()
            stdscr.getch()
            continue

        box_h = 11
        box_w = 43
        box_y = (h - box_h) // 2
        box_x = max(0, (w - box_w) // 2)

        inner_w = box_w - 2
        cy = curses.color_pair(1) | curses.A_BOLD

        try:
            stdscr.attron(cy)
            stdscr.addstr(box_y,     box_x,     "┌" + "─" * inner_w + "┐")
            stdscr.addstr(box_y + 1, box_x,     "│" + " " * inner_w + "│")
            stdscr.addstr(box_y + 2, box_x,     "│" + program_name.center(inner_w) + "│")
            stdscr.addstr(box_y + 3, box_x,     "│" + "─" * inner_w + "│")
            stdscr.addstr(box_y + 4, box_x,     "│" + " " * inner_w + "│")
            stdscr.addstr(box_y + 5, box_x,     "│" + subtitle.center(inner_w) + "│")
            stdscr.addstr(box_y + 6, box_x,     "│" + " " * inner_w + "│")
            stdscr.addstr(box_y + 7, box_x,     "│" + "[ Add • Edit • Sell • Search ]".center(inner_w) + "│")
            stdscr.addstr(box_y + 8, box_x,     "│" + " " * inner_w + "│")
            stdscr.addstr(box_y + 9, box_x,     "│" + " " * inner_w + "│")
            stdscr.addstr(box_y + 10, box_x,    "└" + "─" * inner_w + "┘")
            stdscr.attroff(cy)
        except curses.error:
            pass

        prompt = "         Press ENTER to continue...          "
        prompt_y = box_y + box_h + 1
        stdscr.attron(curses.A_BLINK)
        try:
            stdscr.addnstr(prompt_y, max(0, (w - len(prompt)) // 2), prompt, w - 1)
        except curses.error:
            pass
        stdscr.attroff(curses.A_BLINK)

        stdscr.refresh()
        key = stdscr.getch()
        if key in (10, curses.KEY_ENTER):
            break
        elif key == curses.KEY_RESIZE:
            continue

def inline_search(stdscr, current_term):
    global COLUMNS, AVAILABLE_COLUMNS
    load_config()
    h, w = stdscr.getmaxyx()
    search_term = current_term
    cursor_pos = len(search_term) if search_term else 0
    while True:
        stdscr.clear()
        stdscr.attron(curses.color_pair(1))
        stdscr.addstr(0, 0, PROGRAM_NAME.center(min(w, 100)))
        stdscr.attroff(curses.color_pair(1))
        stdscr.addstr(1, 0, "")
        
        prompt = f"Search: {search_term}_"
        stdscr.addstr(2, 0, prompt[:w-1])
        stdscr.addstr(3, 0, "Press Enter to search, Esc to cancel, Backspace to delete")
        stdscr.addstr(4, 0, "─" * min(w, 100))
        
        stdscr.attron(curses.color_pair(1))
        header_parts = []
        for idx, col in enumerate(COLUMNS):
            key = col['key']
            if key.startswith('custom_'):
                label = col.get('label', key)
            else:
                label = AVAILABLE_COLUMNS[key]['label']
            label = f"{label}({idx + 1})"
            width = col['width']
            align = col.get('align', 'left')
            if align == 'right':
                header_parts.append(label.rjust(width))
            elif align == 'center':
                header_parts.append(label.center(width))
            else:
                header_parts.append(label.ljust(width))
        headers = "  ".join(header_parts)
        stdscr.addstr(5, 0, headers[:w])
        header_dashes = "  ".join([col['width'] * '-' for col in COLUMNS])
        stdscr.addstr(6, 0, header_dashes[:w])
        stdscr.attroff(curses.color_pair(1))
        
        stdscr.move(2, 8 + cursor_pos)
        stdscr.refresh()
        curses.doupdate()
        
        key = stdscr.getch()
        
        if key == 27:
            return ""
        
        if key == -1:
            continue
        
        if key in (10, curses.KEY_ENTER):
            return search_term
        elif key == 27:
            return ""
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if cursor_pos > 0:
                search_term = search_term[:cursor_pos-1] + search_term[cursor_pos:]
                cursor_pos -= 1
        elif 32 <= key <= 126:
            if cursor_pos < 30:
                char = chr(key)
                search_term = search_term[:cursor_pos] + char + search_term[cursor_pos:]
                cursor_pos += 1
        elif key == curses.KEY_RESIZE:
            continue
        elif key == curses.KEY_LEFT and cursor_pos > 0:
            cursor_pos -= 1
        elif key == curses.KEY_RIGHT and cursor_pos < len(search_term):
            cursor_pos += 1
        elif key == curses.KEY_HOME:
            cursor_pos = 0
        elif key == curses.KEY_END:
            cursor_pos = len(search_term)

# ──────────────────────────────────────────────────────────────────────────────
# Manager: unified entry point for selecting and managing inventories
# ──────────────────────────────────────────────────────────────────────────────

def _plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"

def draw_manager(stdscr, selected_idx):
    stdscr.clear()
    h, w = stdscr.getmaxyx()

    try:
        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(0, 0, MGR_PROGRAM_NAME.center(min(w, 80)))
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
    except curses.error:
        pass

    try:
        stdscr.addstr(1, 0, MGR_SUBTITLE.center(min(w, 80)))
        stdscr.addstr(2, 0, "─" * min(w, 80))
    except curses.error:
        pass

    if not INVENTORIES:
        try:
            stdscr.addstr(h//2 - 1, 0, "No inventories found".center(min(w, 80)))
            stdscr.addstr(h//2 + 1, 0, "Press 'a' to create one".center(min(w, 80)))
        except curses.error:
            pass
    else:
        visible_lines = max(1, h - 6)
        start_y = 4
        for i in range(min(len(INVENTORIES), visible_lines)):
            name = INVENTORIES[i]['name']
            prefix = "> " if i == selected_idx else "  "
            line = f"{prefix}[{i+1}] {name}"
            try:
                if i == selected_idx:
                    stdscr.attron(curses.color_pair(4))
                stdscr.addstr(start_y + i, 0, line)
                if i == selected_idx:
                    stdscr.attroff(curses.color_pair(4))
            except curses.error:
                pass

    try:
        stdscr.addstr(h-2, 0, "·" * min(w, 80))
    except curses.error:
        pass

    footer = "↑↓: Navigate  Enter: Open  a: Add  d: Delete  r: Rescan  x: Remove stale files  c: Settings  h: About  q/Esc: Quit"
    try:
        stdscr.addnstr(h-1, 0, footer.ljust(w-1), w-1)
    except curses.error:
        pass

def confirm_quit(stdscr):
    """Ask the user to confirm quitting the whole app. Returns True to quit."""
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    try:
        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(0, 0, "Quit?".center(min(w, 60)))
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(2, 0, "─" * min(w, 40))
        stdscr.addstr(4, 2, "Are you sure you want to quit?")
        stdscr.addstr(6, 2, "y: yes quit")
        stdscr.addstr(7, 2, "n: no, I'm not done")
    except curses.error:
        pass
    stdscr.refresh()
    ch = stdscr.getch()
    return ch in (ord('y'), ord('Y'), ord(' '))

def manager_loop(stdscr):
    """Run the manager screen. Returns a folder Path to open, or None to quit."""
    global MGR_SELECTED_IDX
    stdscr.keypad(1)
    curses.curs_set(0)
    load_manager_config()
    apply_theme(MGR_THEME_COLOR)
    scan_inventories()
    if INVENTORIES:
        MGR_SELECTED_IDX = min(MGR_SELECTED_IDX, len(INVENTORIES) - 1)
    else:
        MGR_SELECTED_IDX = 0

    while True:
        if not check_size(stdscr):
            stdscr.clear()
            stdscr.refresh()
            continue

        draw_manager(stdscr, MGR_SELECTED_IDX)
        stdscr.refresh()
        key = stdscr.getch()

        if key == curses.KEY_RESIZE:
            stdscr.clear()
            stdscr.refresh()
            continue

        if key in (ord('q'), 27):
            if confirm_quit(stdscr):
                return None
        elif key == curses.KEY_UP and INVENTORIES and MGR_SELECTED_IDX > 0:
            MGR_SELECTED_IDX -= 1
        elif key == curses.KEY_DOWN and INVENTORIES and MGR_SELECTED_IDX < len(INVENTORIES) - 1:
            MGR_SELECTED_IDX += 1
        elif key in (10, curses.KEY_ENTER, ord(' ')) and INVENTORIES:
            return INVENTORIES[MGR_SELECTED_IDX]['folder']
        elif key == ord('a'):
            create_new_inventory(stdscr)
            MGR_SELECTED_IDX = min(MGR_SELECTED_IDX, max(0, len(INVENTORIES) - 1))
        elif key == ord('d'):
            delete_inventory(stdscr)
            MGR_SELECTED_IDX = min(MGR_SELECTED_IDX, max(0, len(INVENTORIES) - 1))
        elif key == ord('r'):
            scan_inventories()
            MGR_SELECTED_IDX = min(MGR_SELECTED_IDX, max(0, len(INVENTORIES) - 1))
        elif key == ord('x'):
            cleanup_folders(stdscr)
            scan_inventories()
            MGR_SELECTED_IDX = min(MGR_SELECTED_IDX, max(0, len(INVENTORIES) - 1))
        elif key == ord('c'):
            manager_config_menu(stdscr)
            apply_theme(MGR_THEME_COLOR)
        elif key in (ord('h'), ord('?')):
            manager_about(stdscr)

def _manager_message(stdscr, lines):
    stdscr.clear()
    for i, line in enumerate(lines):
        try:
            stdscr.addstr(4 + i, 2, line)
        except curses.error:
            pass
    try:
        stdscr.addstr(len(lines) + 6, 2, "Press any key...")
    except curses.error:
        pass
    stdscr.refresh()
    stdscr.getch()

def create_new_inventory(stdscr):
    global MGR_SELECTED_IDX
    h, w = stdscr.getmaxyx()
    if h < 15 or w < 50:
        return

    stdscr.clear()
    try:
        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(0, 0, "Create New Inventory".center(min(w, 60)))
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(2, 0, "─" * min(w, 40))
    except curses.error:
        pass

    name = get_input(stdscr, "Enter name for new inventory: ", 4, 2, max_len=40, allow_cancel=True)
    if name in ("__CANCEL__", "__GOBACK__") or not name.strip():
        return

    folder = SCRIPT_DIR / name.strip()
    if folder.exists():
        _manager_message(stdscr, ["Folder already exists!"])
        return

    try:
        folder.mkdir()
        config = json.loads(json.dumps(DEFAULT_CONFIG))
        config['program_name'] = name.strip()
        with (folder / "inventory_config.json").open('w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

        tpl_about = SCRIPT_DIR / "AboutTemplate"
        tpl_default = SCRIPT_DIR / "AboutDefaultTemplate"
        if tpl_about.exists():
            shutil.copy2(tpl_about, folder / "About")
        else:
            (folder / "About").write_text(DEFAULT_ABOUT, encoding='utf-8')
        if tpl_default.exists():
            shutil.copy2(tpl_default, folder / "AboutDefault")
        else:
            (folder / "AboutDefault").write_text(DEFAULT_ABOUT, encoding='utf-8')
    except Exception as e:
        _manager_message(stdscr, [f"Error creating inventory: {e}"])
        return

    scan_inventories()
    for i, inv in enumerate(INVENTORIES):
        if inv['folder'] == folder:
            MGR_SELECTED_IDX = i
            break

def delete_inventory(stdscr):
    if not INVENTORIES or MGR_SELECTED_IDX >= len(INVENTORIES):
        return

    inv = INVENTORIES[MGR_SELECTED_IDX]
    name = inv['name']
    folder = inv['folder']
    h, w = stdscr.getmaxyx()

    stdscr.clear()
    try:
        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(0, 0, "Delete Inventory".center(min(w, 60)))
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(2, 0, "─" * min(w, 40))
        stdscr.addstr(4, 2, f"Delete '{name}'?")
        stdscr.addstr(5, 2, "This will permanently delete the folder and all data.")
    except curses.error:
        pass

    confirm = get_input(stdscr, "Type 'yes' to confirm: ", 7, 2, max_len=10, allow_cancel=True)
    if confirm != "yes":
        return

    try:
        shutil.rmtree(folder)
    except Exception as e:
        _manager_message(stdscr, [f"Error: {e}"])
        return

    _manager_message(stdscr, ["Deleted!"])

def cleanup_folders(stdscr):
    """Remove redundant per-folder app copies and caches from each inventory."""
    targets = []
    for inv in INVENTORIES:
        folder = inv['folder']
        stale_py = folder / "inventory.py"
        stale_cache = folder / "__pycache__"
        if stale_py.exists() or stale_cache.is_dir():
            targets.append(inv)

    h, w = stdscr.getmaxyx()
    stdscr.clear()
    try:
        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(0, 0, "Clean Up Inventory Folders".center(min(w, 60)))
        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(2, 0, "─" * min(w, 40))
    except curses.error:
        pass

    if not targets:
        _manager_message(stdscr, ["Nothing to clean up.", "Inventory folders hold data only."])
        return

    for i, inv in enumerate(targets):
        try:
            stdscr.addstr(4 + i, 2, f"- {inv['name']}")
        except curses.error:
            pass
    try:
        stdscr.addstr(6 + len(targets), 2, "Remove stale inventory.py / __pycache__ from these?")
    except curses.error:
        pass

    confirm = get_input(stdscr, "Type 'yes' to confirm: ", 8 + len(targets), 2, max_len=10, allow_cancel=True)
    if confirm != "yes":
        return

    removed = 0
    for inv in targets:
        folder = inv['folder']
        for path in (folder / "inventory.py", folder / "__pycache__"):
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                    removed += 1
                elif path.exists():
                    path.unlink()
                    removed += 1
            except Exception:
                pass

    _manager_message(stdscr, [f"Cleaned up {_plural(removed, 'item')}."])

def manager_about(stdscr):
    stdscr.keypad(1)
    lines = [
        MGR_PROGRAM_NAME,
        "Version 2.0",
        "",
        "A single-file TUI inventory manager.",
        "Create, delete, and open separate inventories.",
        "Each inventory keeps its own data, config, and About page.",
        "",
        "Inventory folders live alongside this script.",
        "",
        "Press q to return",
    ]
    while True:
        h, w = stdscr.getmaxyx()
        if h < 10 or w < 40:
            stdscr.clear()
            try:
                stdscr.addstr(0, 0, "Window too small. Resize and press any key...")
            except curses.error:
                pass
            stdscr.refresh()
            stdscr.getch()
            return

        stdscr.clear()
        try:
            stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addstr(0, 0, f"About {MGR_PROGRAM_NAME}".center(min(w, 60)))
            stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addstr(2, 0, "─" * min(w, 60))
        except curses.error:
            pass

        for i, line in enumerate(lines):
            try:
                stdscr.addstr(4 + i, 0, line.center(min(w, 60)))
            except curses.error:
                pass

        stdscr.refresh()
        key = stdscr.getch()
        if key in (27, ord('b')):
            return

def manager_theme_menu(stdscr):
    global MGR_THEME_COLOR
    stdscr.keypad(1)
    color_names = list(THEME_COLORS.keys())
    selected = color_names.index(next((k for k, v in THEME_COLORS.items() if v == MGR_THEME_COLOR), 'cyan'))

    while True:
        h, w = stdscr.getmaxyx()
        if h < 15 or w < 50:
            return

        stdscr.clear()
        try:
            stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addstr(0, 0, "Manager Theme Color".center(min(w, 50)))
            stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addstr(2, 0, "─" * min(w, 40))
        except curses.error:
            pass

        for i, color_name in enumerate(color_names):
            try:
                marker = "> " if i == selected else "  "
                curses.init_pair(10, THEME_COLORS[color_name], -1)
                if i == selected:
                    stdscr.attron(curses.color_pair(4))
                stdscr.addstr(4 + i, 2, f"{marker}{i + 1}. ")
                if i == selected:
                    stdscr.attroff(curses.color_pair(4))
                stdscr.attron(curses.color_pair(10))
                stdscr.addstr(color_name.capitalize())
                stdscr.attroff(curses.color_pair(10))
            except curses.error:
                pass

        try:
            stdscr.addstr(4 + len(color_names), 0, "─" * min(w, 40))
            stdscr.addstr(5 + len(color_names), 2, "↑↓: Navigate  Enter: Apply  Esc/b: Back")
        except curses.error:
            pass
        stdscr.refresh()
        key = stdscr.getch()

        if key in (27, ord('b')):
            return
        elif key == curses.KEY_UP and selected > 0:
            selected -= 1
        elif key == curses.KEY_DOWN and selected < len(color_names) - 1:
            selected += 1
        elif key in (10, curses.KEY_ENTER, ord(' ')):
            MGR_THEME_COLOR = THEME_COLORS[color_names[selected]]
            save_manager_config()
            return
        elif ord('1') <= key <= ord('7'):
            selected = key - ord('1')
            MGR_THEME_COLOR = THEME_COLORS[color_names[selected]]
            save_manager_config()
            return

def manager_config_menu(stdscr):
    global MGR_PROGRAM_NAME, MGR_SUBTITLE
    stdscr.keypad(1)
    selected = 0
    options = ["Program name", "Subtitle", "Theme color", "Install command"]

    while True:
        h, w = stdscr.getmaxyx()
        if h < 15 or w < 50:
            return

        stdscr.clear()
        try:
            stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addstr(0, 0, "Manager Settings".center(min(w, 50)))
            stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addstr(2, 0, "─" * min(w, 40))
        except curses.error:
            pass

        color_name = next((k for k, v in THEME_COLORS.items() if v == MGR_THEME_COLOR), 'cyan')
        values = [MGR_PROGRAM_NAME, MGR_SUBTITLE, color_name, "Configure"]
        for i, opt in enumerate(options):
            try:
                if i == selected:
                    stdscr.attron(curses.color_pair(4))
                stdscr.addstr(4 + i, 2, f"{i+1}. {opt}: {values[i]}")
                if i == selected:
                    stdscr.attroff(curses.color_pair(4))
            except curses.error:
                pass

        try:
            stdscr.addstr(4 + len(options), 0, "─" * min(w, 40))
            stdscr.addstr(5 + len(options), 2, "Enter: Edit  Esc/b: Back")
        except curses.error:
            pass
        stdscr.refresh()
        key = stdscr.getch()

        if key in (27, ord('b')):
            return
        elif key == curses.KEY_UP and selected > 0:
            selected -= 1
        elif key == curses.KEY_DOWN and selected < len(options) - 1:
            selected += 1
        elif key in (10, curses.KEY_ENTER, ord(' ')):
            if selected == 0:
                new = get_input(stdscr, "New name: ", 7, 2, max_len=40, default=MGR_PROGRAM_NAME, allow_cancel=True)
                if new not in ("__CANCEL__", "__GOBACK__") and new.strip():
                    MGR_PROGRAM_NAME = new.strip()
                    save_manager_config()
            elif selected == 1:
                new = get_input(stdscr, "New subtitle: ", 7, 2, max_len=60, default=MGR_SUBTITLE, allow_cancel=True)
                if new not in ("__CANCEL__", "__GOBACK__") and new.strip():
                    MGR_SUBTITLE = new.strip()
                    save_manager_config()
            elif selected == 2:
                manager_theme_menu(stdscr)
            elif selected == 3:
                install_menu(stdscr)
        elif ord('1') <= key <= ord('9'):
            idx = key - ord('1')
            if idx < len(options):
                selected = idx

def _install_target():
    return SCRIPT_DIR / "inventory.py"

def check_installed():
    cmd = Path.home() / "bin" / "tui-inventory"
    if cmd.exists():
        if cmd.is_symlink():
            if cmd.resolve() == _install_target():
                return "symlink"
        try:
            if str(_install_target()) in cmd.read_text():
                return "wrapper"
        except Exception:
            pass
    bashrc = Path.home() / ".bashrc"
    if bashrc.exists():
        try:
            content = bashrc.read_text()
            if str(SCRIPT_DIR) in content and "inventory" in content.lower():
                return "path"
        except Exception:
            pass
    return None

def do_install(option):
    bin_dir = Path.home() / "bin"
    bashrc_path = Path.home() / ".bashrc"
    wrapper_path = bin_dir / "tui-inventory"

    if option == 1:
        try:
            bin_dir.mkdir(exist_ok=True)
        except PermissionError:
            return "mkdir_failed"

        try:
            content = f'''#!/bin/sh
exec python3 "{_install_target()}" "$@"
'''
            with wrapper_path.open('w') as f:
                f.write(content)
            os.chmod(str(wrapper_path), 0o755)
        except (PermissionError, OSError):
            return "write_failed"

        path_line = 'export PATH="$HOME/bin:$PATH"'
        try:
            if bashrc_path.exists():
                if path_line not in bashrc_path.read_text():
                    with bashrc_path.open('a') as f:
                        f.write(f"\n{path_line}\n")
            else:
                with bashrc_path.open('w') as f:
                    f.write(f"{path_line}\n")
        except PermissionError:
            return "bashrc_failed"
        return "success"

    elif option == 2:
        path_line = f'export PATH="$PATH:{SCRIPT_DIR}"'
        try:
            if bashrc_path.exists():
                if path_line not in bashrc_path.read_text():
                    with bashrc_path.open('a') as f:
                        f.write(f"\n{path_line}\n")
            else:
                with bashrc_path.open('w') as f:
                    f.write(f"{path_line}\n")
        except PermissionError:
            return "bashrc_failed"
        return "success"

    elif option == 3:
        if wrapper_path.exists():
            try:
                wrapper_path.unlink()
            except (PermissionError, OSError):
                return "unlink_failed"
        return "success"

    return "error"

def install_menu(stdscr):
    stdscr.keypad(1)
    selected = 0
    options = ["Install 'tui-inventory' command (Recommended)", "Add folder to PATH", "Uninstall"]

    while True:
        h, w = stdscr.getmaxyx()
        if h < 15 or w < 50:
            return

        stdscr.clear()
        try:
            stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addstr(0, 0, "Install Command".center(min(w, 50)))
            stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
            stdscr.addstr(2, 0, "─" * min(w, 40))
        except curses.error:
            pass

        status = check_installed()
        if status:
            text = "Status: command installed" if status in ("symlink", "wrapper") else "Status: folder in PATH"
            try:
                stdscr.addstr(3, 2, text)
            except curses.error:
                pass

        for i, opt in enumerate(options):
            try:
                if i == selected:
                    stdscr.attron(curses.color_pair(4))
                stdscr.addstr(4 + i, 2, f"{i+1}. {opt}")
                if i == selected:
                    stdscr.attroff(curses.color_pair(4))
            except curses.error:
                pass

        try:
            stdscr.addstr(4 + len(options), 0, "─" * min(w, 40))
            stdscr.addstr(5 + len(options), 2, "Enter: Install  Esc/b: Back")
        except curses.error:
            pass
        stdscr.refresh()
        key = stdscr.getch()

        if key in (27, ord('b')):
            return
        elif key == curses.KEY_UP and selected > 0:
            selected -= 1
        elif key == curses.KEY_DOWN and selected < len(options) - 1:
            selected += 1
        elif key in (10, curses.KEY_ENTER, ord(' ')):
            result = do_install(selected + 1)
            if result == "success":
                _manager_message(stdscr, ["Installation complete!", "Restart terminal or run: source ~/.bashrc"])
            elif result == "mkdir_failed":
                _manager_message(stdscr, ["Error: Cannot create ~/bin directory.", "Try manually: mkdir ~/bin"])
            elif result == "write_failed":
                _manager_message(stdscr, ["Error: Cannot write wrapper file."])
            elif result == "bashrc_failed":
                _manager_message(stdscr, ["Warning: Could not update ~/.bashrc",
                                          'Manually add: export PATH="$HOME/bin:$PATH"'])
            elif result == "unlink_failed":
                _manager_message(stdscr, ["Error: Cannot remove command."])
            else:
                _manager_message(stdscr, ["Installation failed."])
        elif ord('1') <= key <= ord('9'):
            idx = key - ord('1')
            if idx < len(options):
                selected = idx

def run(stdscr):
    """Top-level dispatcher: manager <-> selected inventory, all in-process."""
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.set_escdelay(25)
    load_manager_config()
    apply_theme(MGR_THEME_COLOR)

    show_splash(stdscr, MGR_PROGRAM_NAME, MGR_SUBTITLE)

    while True:
        folder = manager_loop(stdscr)
        if folder is None:
            break

        set_data_dir(folder)
        result = inventory_main(stdscr)
        if result == "quit":
            break

        apply_theme(MGR_THEME_COLOR)
        stdscr.clear()
        stdscr.refresh()

def inventory_main(stdscr):
    load_config()
    curses.curs_set(0)
    apply_theme(THEME_COLOR)
    curses.set_escdelay(25)

    if SPLASH_ENABLED:
        show_splash(stdscr, PROGRAM_NAME, SUBTITLE)

    inventory = load_inventory()

    selected_row_idx = 0
    search_term = ""
    column_filter = {}
    sort_key = 'name'
    split_screen_mode = False  # Track split-screen state

    sort_directions = {'name': 1, 'quantity': 1, 'location': 1}
    scroll_offset = 0

    while True:
        stdscr.timeout(-1)
        # ── Always check size first ───────────────────────────────────────
        if not check_size(stdscr):
            # If too small → wait for resize or any key press
            try:
                stdscr.getch()
            except KeyboardInterrupt:
                return
            stdscr.clear()
            stdscr.refresh()
            continue
        # ── Draw the current state (this is what the user sees right now) ──
        h, w = stdscr.getmaxyx()
        if split_screen_mode:
            filtered, original_indices, scroll_offset = draw_split_screen(
                stdscr, selected_row_idx, inventory,
                search_term, sort_key, sort_directions, scroll_offset, column_filter
            )
        else:
            filtered, original_indices, scroll_offset = draw_menu(
                stdscr, selected_row_idx, inventory,
                search_term, sort_key, sort_directions, scroll_offset, column_filter
            )
        filtered_len = len(filtered)
        visible_lines = h - 10
        max_scroll = max(0, filtered_len - visible_lines)

        filtered_len = len(filtered)
        visible_lines = h - 10
        max_scroll = max(0, filtered_len - visible_lines)

        # ── Wait for user input ────────────────────────────────────────────
        try:
            key = stdscr.getch()
        except KeyboardInterrupt:
            continue

        # ── Handle special resize event first ──────────────────────────────
        if key == curses.KEY_RESIZE:
            stdscr.clear()
            stdscr.refresh()
            continue

        # ── Normal key handling ────────────────────────────────────────────
        if key == curses.KEY_UP and selected_row_idx > 0:
            selected_row_idx -= 1
            if selected_row_idx < scroll_offset:
                scroll_offset = selected_row_idx

        elif key == curses.KEY_DOWN and selected_row_idx < filtered_len - 1:
            selected_row_idx += 1
            if selected_row_idx >= scroll_offset + visible_lines:
                scroll_offset = selected_row_idx - visible_lines + 1
                if scroll_offset > max_scroll:
                    scroll_offset = max_scroll

        elif key in (curses.KEY_PPAGE, ord('K')):
            if scroll_offset > 0:
                scroll_offset = max(0, scroll_offset - visible_lines)
                selected_row_idx = max(0, selected_row_idx - visible_lines)

        elif key in (curses.KEY_NPAGE, ord('J')):
            if scroll_offset < max_scroll:
                scroll_offset = min(max_scroll, scroll_offset + visible_lines)
                selected_row_idx = min(filtered_len - 1, selected_row_idx + visible_lines)
        elif key == 22:  # CTRL+v
            split_screen_mode = not split_screen_mode
            scroll_offset = 0  # Reset scroll when toggling


        elif key == ord('q'):
            if confirm_quit(stdscr):
                return "quit"

        elif key == ord('a'):
            add_item(stdscr, inventory)
            selected_row_idx = 0
            scroll_offset = 0

        elif key == ord('s'):
            search_term = inline_search(stdscr, search_term)
            selected_row_idx = 0
            scroll_offset = 0

        elif key == ord('f'):
            filterable = get_filterable_columns()
            visible_filterable = []
            for col in COLUMNS:
                if col['key'] in filterable:
                    visible_filterable.append(col['key'])
            
            if not visible_filterable:
                pass
            else:
                h, w = stdscr.getmaxyx()
                stdscr.clear()
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(0, 0, "Select column to filter".center(min(w, 60)))
                stdscr.attroff(curses.color_pair(1))
                stdscr.addstr(2, 0, "Enter column number:")
                stdscr.addstr(3, 0, "─" * min(w, 40))
                
                for i, col_key in enumerate(visible_filterable):
                    if col_key.startswith('custom_'):
                        field_name = col_key[7:]
                        for field in CUSTOM_FIELDS:
                            if field['name'] == field_name:
                                label = field.get('label', field_name)
                                break
                        else:
                            label = col_key
                    else:
                        label = AVAILABLE_COLUMNS.get(col_key, {}).get('label', col_key)
                    stdscr.addstr(4 + i, 2, f"{i+1}. {label}")
                
                stdscr.addstr(4 + len(visible_filterable), 2, "q. Cancel")
                stdscr.refresh()
                
                ch = stdscr.getch()
                
                if ord('1') <= ch <= ord('1') + len(visible_filterable) - 1:
                    col_idx = ch - ord('1')
                    col_key = visible_filterable[col_idx]
                    
                    unique_vals = get_unique_values(inventory, col_key)
                    
                    if not unique_vals:
                        stdscr.clear()
                        stdscr.addstr(0, 0, "No values to filter")
                        stdscr.addstr(2, 0, "Press any key...")
                        stdscr.refresh()
                        stdscr.getch()
                    elif len(unique_vals) > 15:
                        stdscr.clear()
                        stdscr.addstr(0, 0, f"Too many unique values ({len(unique_vals)})")
                        stdscr.addstr(2, 0, "Use text search instead (s)")
                        stdscr.addstr(4, 0, "Press any key...")
                        stdscr.refresh()
                        stdscr.getch()
                    else:
                        selected = filter_select_menu(stdscr, inventory, col_key)
                        if selected:
                            column_filter = {col_key: selected}
                            search_term = ""
                            selected_row_idx = 0
                            scroll_offset = 0

        elif key == ord('e') and filtered_len > 0:
            orig_idx = original_indices[selected_row_idx]
            edit_item(stdscr, inventory, orig_idx)

        elif key == 27:
            if search_term or column_filter:
                search_term = ""
                column_filter = {}
                selected_row_idx = 0
                scroll_offset = 0
            else:
                return "back"

        elif key in (ord('n'), ord('t'), ord('l')):
            key_map = {ord('n'):'name', ord('t'):'quantity', ord('l'):'location'}
            new_key = key_map.get(key)
            if new_key == sort_key:
                sort_directions[sort_key] *= -1
            else:
                sort_key = new_key
                sort_directions[sort_key] = 1
            selected_row_idx = 0
            scroll_offset = 0

        elif ord('1') <= key <= ord('9'):
            col_idx = key - ord('1')
            if col_idx < len(COLUMNS):
                new_key = COLUMNS[col_idx]['key']
                if new_key == sort_key:
                    sort_directions[sort_key] *= -1
                else:
                    sort_key = new_key
                    sort_directions[sort_key] = 1
                selected_row_idx = 0
                scroll_offset = 0

        elif key == ord('r') and filtered_len > 0 and SALE_ENABLED:
            orig_idx = original_indices[selected_row_idx]
            record_sale_ui(stdscr, inventory, orig_idx)
            # After sale we continue → next loop iteration will redraw automatically

        elif key == ord('d') and filtered_len > 0:
            orig_idx = original_indices[selected_row_idx]
            deleted = delete_item(stdscr, inventory, orig_idx)
            if deleted:
                selected_row_idx = max(0, min(selected_row_idx, len(inventory) - 1))
                if selected_row_idx < scroll_offset:
                    scroll_offset = selected_row_idx

        elif key == ord('h'):
            view_sales_history(stdscr)

        elif key == ord('c'):
            config_menu(stdscr, inventory)
            curses.init_pair(1, THEME_COLOR, -1)
            curses.init_pair(2, curses.COLOR_YELLOW, -1)
            curses.init_pair(3, curses.COLOR_RED,    -1)
            curses.init_pair(4, curses.COLOR_GREEN,  -1)

        elif key in (10, curses.KEY_ENTER) and filtered_len > 0:
            orig_idx = original_indices[selected_row_idx]
            was_deleted = view_details(stdscr, inventory, orig_idx)

            if was_deleted:
                selected_row_idx = max(0, min(selected_row_idx, len(inventory) - 1))
                if selected_row_idx < scroll_offset:
                    scroll_offset = selected_row_idx

            # No need to redraw here — next loop iteration will do it

        # After most actions we just continue → the loop will redraw automatically

if __name__ == "__main__":
    if not sys.stdin.isatty():
        print("This program must be run in a terminal.")
        sys.exit(1)
    curses.wrapper(run)