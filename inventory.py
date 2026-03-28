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
SCRIPT_DIR  = Path(__file__).parent.resolve()
DB_FILE     = SCRIPT_DIR / "inventory.db"
BACKUP_FILE = SCRIPT_DIR / "inventory.db.bak"
SALES_LOG   = SCRIPT_DIR / "inventory_sales.log"
CONFIG_FILE = SCRIPT_DIR / "inventory_config.json"

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
    'sale': {'label': 'Sale', 'width': 12, 'align': 'center'},
}

COLUMNS = [
    {'key': 'name', 'width': 24, 'align': 'left'},
    {'key': 'quantity', 'width': 6, 'align': 'right'},
    {'key': 'cost', 'width': 12, 'align': 'center'},
    {'key': 'location', 'width': 10, 'align': 'left'},
    {'key': 'description', 'width': 20, 'align': 'left'},
]

LOW_STOCK_THRESHOLD = 5
CRITICAL_STOCK      = 3
PO_ENABLED = True
MONETIZATION_ENABLED = True
COLOR_CRITICAL_ENABLED = True

# Global custom fields
CUSTOM_FIELDS = []  # [{'name':str, 'label':str, 'type':'text'|'number'|'money'}, ...]

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
# Config load/save
# ──────────────────────────────────────────────────────────────────────────────

def load_config():
    global CUSTOM_FIELDS, THEME_COLOR, PROGRAM_NAME, SUBTITLE, PO_ENABLED, MONETIZATION_ENABLED, COLOR_CRITICAL_ENABLED, COLUMNS
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
                saved_cols = data.get('columns', None)
                if saved_cols:
                    COLUMNS = saved_cols
        except Exception:
            CUSTOM_FIELDS = []
            THEME_COLOR = curses.COLOR_CYAN
    else:
        CUSTOM_FIELDS = []
        THEME_COLOR = curses.COLOR_CYAN

def save_config(include_theme=True):
    global PROGRAM_NAME, SUBTITLE, PO_ENABLED, MONETIZATION_ENABLED, COLOR_CRITICAL_ENABLED, COLUMNS
    with CONFIG_FILE.open('w', encoding='utf-8') as f:
        color_name = next((k for k, v in THEME_COLORS.items() if v == THEME_COLOR), 'cyan')
        if include_theme:
            json.dump({'custom_fields': CUSTOM_FIELDS, 'theme_color': color_name, 'program_name': PROGRAM_NAME, 'subtitle': SUBTITLE, 'po_enabled': PO_ENABLED, 'monetization_enabled': MONETIZATION_ENABLED, 'color_critical_enabled': COLOR_CRITICAL_ENABLED, 'columns': COLUMNS}, f, indent=2)
        else:
            json.dump({'custom_fields': CUSTOM_FIELDS}, f, indent=2)

# ──────────────────────────────────────────────────────────────────────────────
# Item model
# ──────────────────────────────────────────────────────────────────────────────

class Item:
    def __init__(self, name, quantity=0, cost=0.0, min_value=0.0, max_value=0.0,
                 sale=0.0, location="", description="", **custom):
        self.name = name.strip()
        self.quantity = quantity
        self.cost = cost
        self.min_value = min_value
        self.max_value = max_value
        self.sale = sale
        self.location = location.strip()
        self.description = description.strip()
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
        if self.quantity <= CRITICAL_STOCK: return "critical"
        if self.quantity <= LOW_STOCK_THRESHOLD: return "low"
        return "ok"

    def to_dict(self):
        d = {
            'name': self.name, 'quantity': self.quantity, 'cost': self.cost,
            'min_value': self.min_value, 'max_value': self.max_value,
            'sale': self.sale, 'location': self.location,
            'description': self.description
        }
        d.update(self.custom)
        return d

    @classmethod
    def from_dict(cls, d):
        known = {'name','quantity','cost','min_value','max_value','sale','location','description'}
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
            **custom
        )

# ──────────────────────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────────────────────

def get_all_fieldnames(inventory):
    base = [
        'name', 'quantity', 'cost', 'min_value', 'max_value',
        'sale', 'location', 'description'
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
    sort_directions = {'timestamp': -1, 'name': 1, 'quantity': 1, 'total': 1}

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

                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(0, 0, "Sales History".center(min(w, 100)))
                stdscr.attroff(curses.color_pair(1))

                dir_symbol = "↓" if direction < 0 else "↑"
                status = f"Search: {search_term or '(none)'}   Sort: {sort_key} {dir_symbol}   (s:search n:name t:time q:qty $:total)"
                try:
                    stdscr.addstr(1, 0, status[:w-1])
                except curses.error:
                    pass

                try:
                    stdscr.addstr(3, 0, "DATE       NAME                 QTY  PRICE     TOTAL    PO")
                    stdscr.addstr(4, 0, "---------- -------------------- --- -------- -------- ----------")
                    stdscr.addstr(4, 75, "more ->")
                except curses.error:
                    pass

                y = 5

                max_lines = h - y - 4
                for row in rows[:max_lines]:
                    if y >= h - 3:
                        break
                    ts = row.get('timestamp', '?')[:10]
                    qty = int(row.get('quantity_sold', '0'))
                    price = float(row.get('price_each', '0'))
                    total = float(row.get('total', '0'))
                    po = row.get('po_number', '')
                    
                    name = row.get('name', '?')[:20]
                    
                    po_str = f"{po}" if po else "-"
                    line = f"{ts:<10} {name:<20} {qty:>3}  ${price:>7,.2f}  ${total:>7,.2f}  {po_str:<10}"
                    try:
                        stdscr.addnstr(y, 0, line, w-1)
                    except curses.error:
                        pass
                    y += 1

            if len(rows) > max_lines:
                try:
                    stdscr.addstr(y, 0, f"... {len(rows) - max_lines} more rows (resize to see more)")
                except curses.error:
                    pass
                y += 1

            try:
                stdscr.addstr(y+1, 0, "·" * min(w, 80))
                if search_term:
                    stdscr.addstr(y+2, 0, "b:back (clear search)  ENTER:return to main")
                else:
                    stdscr.addstr(y+2, 0, "ENTER:return to main")
            except curses.error:
                pass
        except Exception as e:
            try:
                stdscr.addstr(2, 0, f"Error reading sales log: {str(e)[:60]}")
            except:
                pass

        stdscr.refresh()
        key = stdscr.getch()
        
        if key == curses.KEY_RESIZE:
            continue
        elif key == ord('s'):
            search_term = search_mode(stdscr)
        elif key == ord('b') and search_term:
            search_term = ""
        elif key in (10, curses.KEY_ENTER, ord('b')):
            break
        elif key in (ord('n'), ord('t'), ord('q'), ord('$')):
            new_key = {ord('n'): 'name', ord('t'): 'timestamp', ord('q'): 'quantity', ord('$'): 'total'}[key]
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
        curses.init_pair(pair_id, THEME_COLORS[color_name], curses.COLOR_BLACK)
    
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
            stdscr.addstr(0, 0, "Column Configuration".center(min(w, 100)))
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
            stdscr.addstr(2, 2, "Columns (Arrows: scroll, Enter: toggle, +/-: width, a: align L/C/R):")
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
                        stdscr.addstr(y + i, 2, f"{prefix} {marker} {label:<12}  w:{width}  a:{align[0]}")
                        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                    else:
                        stdscr.addstr(y + i, 2, f"{prefix} {marker} {label:<12}  w:{width}  a:{align[0]}")
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
        for col in COLUMNS:
            key = col['key']
            if key.startswith('custom_'):
                label = col.get('label', key)
            else:
                label = AVAILABLE_COLUMNS[key]['label']
            width = col['width']
            align = col.get('align', 'left')
            try:
                if align == 'right':
                    header_text = label[:width].rjust(width)
                elif align == 'center':
                    header_text = label[:width].center(width)
                else:
                    header_text = label[:width].ljust(width)
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
            stdscr.addstr(h-3, 2, "Enter/Arrows: toggle  +/-: width  a: align  d: default  q: back")
            stdscr.addstr(h-2, 2, "(max 5 columns, width 3-30)")
        except curses.error:
            pass
        
        stdscr.refresh()
        key = stdscr.getch()
        
        if key == ord('q'):
            break
        elif key == ord('d'):
            COLUMNS[:] = [
                {'key': 'name', 'width': 24, 'align': 'left'},
                {'key': 'quantity', 'width': 6, 'align': 'right'},
                {'key': 'cost', 'width': 12, 'align': 'center'},
                {'key': 'location', 'width': 10, 'align': 'left'},
                {'key': 'description', 'width': 20, 'align': 'left'},
            ]
        elif key in (curses.KEY_UP, ord('k')):
            selected_idx = max(0, selected_idx - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            selected_idx = min(len(all_columns) - 1, selected_idx + 1)
        elif key in (curses.KEY_ENTER, 10, 13, ord(' ')):
            col = all_columns[selected_idx]
            if col['active']:
                COLUMNS[:] = [c for c in COLUMNS if c['key'] != col['key']]
            else:
                if len(COLUMNS) < 5:
                    COLUMNS.append({'key': col['key'], 'width': col['width'], 'align': col['align']})
        elif key in (ord('+'), ord('=')):
            col = all_columns[selected_idx]
            if col['active']:
                for c in COLUMNS:
                    if c['key'] == col['key']:
                        c['width'] = min(30, c['width'] + 1)
                        break
        elif key == ord('-'):
            col = all_columns[selected_idx]
            if col['active']:
                for c in COLUMNS:
                    if c['key'] == col['key']:
                        c['width'] = max(3, c['width'] - 1)
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
# Custom Fields Configuration Menu
# ──────────────────────────────────────────────────────────────────────────────

def config_menu(stdscr, inventory=None):
    global CUSTOM_FIELDS, LOW_STOCK_THRESHOLD, CRITICAL_STOCK, THEME_COLOR, THEME_COLORS, THEME_COLOR_PAIRS, PROGRAM_NAME, SUBTITLE, PO_ENABLED, MONETIZATION_ENABLED, COLOR_CRITICAL_ENABLED

    load_config()
    stdscr.keypad(1)

    for color_name, pair_id in THEME_COLOR_PAIRS.items():
        curses.init_pair(pair_id, THEME_COLORS[color_name], curses.COLOR_BLACK)

    TABS = ["Custom Fields", "Settings", "Display"]
    current_tab = 0

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
            stdscr.addstr(0, 0, (PROGRAM_NAME + " Settings").center(min(w, 100)))
            stdscr.attroff(curses.color_pair(1))
        except curses.error:
            pass

        tab_width = min(20, w // len(TABS))
        try:
            for i, tab in enumerate(TABS):
                x = i * tab_width
                if i == current_tab:
                    stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                    stdscr.addstr(1, x, f" {tab} ")
                    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                else:
                    stdscr.addstr(1, x, f" {tab} ")
            stdscr.addstr(2, 0, "─" * min(w, 80))
        except curses.error:
            pass

        content_top = 3

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
                        stdscr.addnstr(y, 2, line, w-3)
                    except curses.error:
                        pass
                    y += 1

            y += 1
            try:
                stdscr.addstr(y, 2, f"[{len(CUSTOM_FIELDS)}/5]  a:add  #:del")
            except curses.error:
                pass

        if current_tab == 1:
            y = content_top
            current_color_name = next((k for k, v in THEME_COLORS.items() if v == THEME_COLOR), 'cyan')
            try:
                stdscr.addstr(y, 2, "Settings")
                stdscr.addstr(y+2, 2, "Theme Color (titles & splash):")
                y += 3
                color_options = list(THEME_COLORS.keys())
                for i, color_name in enumerate(color_options):
                    prefix = ">" if color_name == current_color_name else " "
                    try:
                        stdscr.addstr(y + i, 2, f"{i+1}. {prefix} ")
                        stdscr.attron(curses.color_pair(THEME_COLOR_PAIRS[color_name]))
                        stdscr.addstr("  " + color_name.capitalize())
                        stdscr.attroff(curses.color_pair(THEME_COLOR_PAIRS[color_name]))
                    except curses.error:
                        pass
                y += len(color_options) + 1
                stdscr.addstr(y, 2, "(press 1-7 to change)")
                y += 2
                stdscr.addstr(y, 2, "Program Name (max 40 chars):")
                stdscr.addstr(y+1, 2, f"  {PROGRAM_NAME}")
                y += 2
                stdscr.addstr(y, 2, "Subtitle (max 40 chars):")
                stdscr.addstr(y+1, 2, f"  {SUBTITLE}")
                y += 3
                stdscr.addstr(y, 2, "n: edit name  s: edit subtitle  r: reset defaults")
            except curses.error:
                pass

        if current_tab == 2:
            y = content_top
            try:
                stdscr.addstr(y, 2, "Display Settings")
                color_crit_status = "On" if COLOR_CRITICAL_ENABLED else "Off"
                stdscr.addstr(y+2, 2, f"1. Stock alerts:         {color_crit_status}")
                stdscr.addstr(y+3, 2, f"2. Low stock threshold:  {LOW_STOCK_THRESHOLD}")
                stdscr.addstr(y+4, 2, f"3. Critical stock:       {CRITICAL_STOCK}")
                po_status = "On" if PO_ENABLED else "Off"
                stdscr.addstr(y+5, 2, f"4. PO Number:            {po_status}")
                mon_status = "On" if MONETIZATION_ENABLED else "Off"
                stdscr.addstr(y+6, 2, f"5. Monetization:         {mon_status}")
                stdscr.addstr(y+7, 2, "6. Column settings")
                stdscr.addstr(y+9, 2, "(press 1-6 to edit)")
            except curses.error:
                pass

        try:
            stdscr.addstr(h-2, 0, "·" * min(w, 80))
            stdscr.addstr(h-1, 0, f"←/→: tabs  Enter: Return".ljust(w-1))
        except curses.error:
            pass

        stdscr.refresh()
        key = stdscr.getch()

        if key == curses.KEY_RESIZE:
            continue
        elif key in (curses.KEY_LEFT, ord('h')):
            current_tab = (current_tab - 1) % len(TABS)
        elif key in (curses.KEY_RIGHT, ord('l')):
            current_tab = (current_tab + 1) % len(TABS)
        elif key in (10, curses.KEY_ENTER, ord('q'), ord('b')):
            break
        elif current_tab == 1 and 49 <= key <= 55:
            try:
                idx = key - 49
                color_names = list(THEME_COLORS.keys())
                if 0 <= idx < len(color_names):
                    THEME_COLOR = THEME_COLORS[color_names[idx]]
                    save_config()
            except Exception as e:
                pass
        elif current_tab == 1 and key == ord('n'):
            try:
                stdscr.addstr(y+12, 2, "Enter new program name: ".ljust(w-3))
                stdscr.refresh()
                curses.echo()
                new_name = stdscr.getstr(y+12, 25, 40).decode('utf-8').strip()
                curses.noecho()
                if new_name:
                    PROGRAM_NAME = new_name
                    save_config()
            except:
                curses.noecho()
        elif current_tab == 2 and key == ord('1'):
            COLOR_CRITICAL_ENABLED = not COLOR_CRITICAL_ENABLED
            save_config()
        elif current_tab == 2 and key == ord('2'):
            try:
                stdscr.addstr(y+11, 2, "New low stock threshold: ")
                stdscr.refresh()
                curses.echo()
                val = stdscr.getstr(y+11, 26, 5).decode('utf-8').strip()
                curses.noecho()
                if val.isdigit():
                    LOW_STOCK_THRESHOLD = int(val)
            except:
                curses.noecho()
        elif current_tab == 2 and key == ord('3'):
            try:
                stdscr.addstr(y+11, 2, "New critical stock level: ")
                stdscr.refresh()
                curses.echo()
                val = stdscr.getstr(y+11, 27, 5).decode('utf-8').strip()
                curses.noecho()
                if val.isdigit():
                    CRITICAL_STOCK = int(val)
            except:
                curses.noecho()
        elif current_tab == 2 and key == ord('4'):
            PO_ENABLED = not PO_ENABLED
            save_config()
        elif current_tab == 2 and key == ord('5'):
            MONETIZATION_ENABLED = not MONETIZATION_ENABLED
            save_config()
        elif current_tab == 2 and key == ord('6'):
            column_config_menu(stdscr)
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
                                typ = get_input(stdscr, "Type [text:t/number:n/money:m]: ", 5, 2, 20, "").lower()
                                if typ in ('t', 'text'):
                                    typ = 'text'
                                    break
                                elif typ in ('n', 'number'):
                                    typ = 'number'
                                    break
                                elif typ in ('m', 'money'):
                                    typ = 'money'
                                    break
                            CUSTOM_FIELDS.append({'name':key, 'label':label, 'type':typ})
                            save_config()
                            stdscr.addstr(8, 2, "Added. Press any key...")
                            stdscr.getch()
                    except curses.error:
                        pass
        elif current_tab == 0 and 48 <= key <= 57:
            cmd = chr(key)
            if cmd.isdigit() and 1 <= int(cmd) <= len(CUSTOM_FIELDS):
                try:
                    idx = int(cmd) - 1
                    removed_key = CUSTOM_FIELDS[idx]['name']
                    removed_label = CUSTOM_FIELDS[idx]['label']
                    stdscr.addstr(y+4, 2, f"Delete '{removed_label}'? (y/n): ")
                    stdscr.refresh()
                    curses.echo()
                    try:
                        confirm = stdscr.getstr(y+4, 28, 3).decode('utf-8').strip().lower()
                    except:
                        confirm = ""
                    curses.noecho()
                    if confirm == 'y':
                        CUSTOM_FIELDS.pop(idx)
                        save_config()
                        if inventory is not None:
                            for item in inventory:
                                item.custom.pop(removed_key, None)
                            safe_save_inventory(inventory)
                        try:
                            stdscr.addstr(y+4, 2, "Removed. Press any key...")
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

def get_input(stdscr, prompt, y, x, max_len=40, default=""):
    stdscr.addstr(y, x, prompt)
    if default:
        stdscr.addstr(y, x + len(prompt), default)
        stdscr.move(y, x + len(prompt) + len(default))
    else:
        stdscr.move(y, x + len(prompt))
    curses.echo()
    val = stdscr.getstr(y, x + len(prompt), max_len).decode('utf-8').strip()
    curses.noecho()
    return val

def add_item(stdscr, inventory):
    stdscr.clear()
    stdscr.addstr(0, 0, "Add New Item (leave name blank to cancel)")

    name = get_input(stdscr, "Name:          ", 2, 0, 40)
    if not name.strip():
        stdscr.addstr(12, 0, "Cancelled. Press any key...")
        stdscr.getch()
        return

    quantity    = get_input(stdscr, "Quantity:      ", 3, 0, 10, "0")
    cost        = get_input(stdscr, "Cost ($):      ", 4, 0, 12, "0.00")
    location    = get_input(stdscr, "Location:      ", 5, 0, 30, "")
    description = get_input(stdscr, "Description:   ", 6, 0, 60, "")

    errors = validate_inputs(name, quantity, cost)
    if errors:
        stdscr.clear()
        stdscr.addstr(2, 0, "Cannot add item:")
        for i, err in enumerate(errors, 4):
            stdscr.addstr(i, 2, f"* {err}")
        stdscr.addstr(len(errors)+6, 0, "Press any key...")
        stdscr.getch()
        return

    inventory.append(Item(name, int(quantity), float(cost), 0.0, 0.0, 0.0, location, description))
    safe_save_inventory(inventory)
    stdscr.addstr(10, 0, "Item added. Press any key...")
    stdscr.getch()

# ──────────────────────────────────────────────────────────────────────────────
# Hardened select_field_to_edit
# ──────────────────────────────────────────────────────────────────────────────

def select_field_to_edit(stdscr, item):
    # Build options list dynamically to include custom fields
    options = [
        "1. Name",
        "2. Quantity",
        "3. Cost",
        "4. Location",
        "5. Description",
        "6. Min Value (hidden)",
        "7. Max Value (hidden)",
        "8. Sale Price (hidden)",
        "9. All fields",
    ]
    # Add individual custom field options numbered 10, 11, ...
    for i, field in enumerate(CUSTOM_FIELDS):
        options.append(f"{10 + i}. {field['label']} (custom)")
    options.append("0. Cancel")

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

        # Regular fields
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

        # Hidden fields
        try:
            stdscr.addnstr(y, 4, f"Min Value:     ${item.min_value:,.2f} (hidden)", w-5); y += 1
            stdscr.addnstr(y, 4, f"Max Value:     ${item.max_value:,.2f} (hidden)", w-5); y += 1
            stdscr.addnstr(y, 4, f"Sale:          ${item.sale:,.2f} (hidden)", w-5); y += 1
        except:
            pass

        # Custom field values with type-aware formatting
        if CUSTOM_FIELDS:
            for field in CUSTOM_FIELDS:
                if y >= h - len(options) - 4:
                    break
                value = item.custom.get(field['name'], "")
                if field['type'] == 'money' and isinstance(value, (int, float)):
                    disp = f"${value:,.2f}"
                elif field['type'] == 'number' and isinstance(value, (int, float)):
                    disp = f"{value:,}"
                else:
                    disp = str(value) if value != "" else "(empty)"
                label_padded = (field['label'] + ":").ljust(15)
                try:
                    stdscr.addnstr(y, 4, f"{label_padded}{disp[:w-20]}", w-5)
                    y += 1
                except:
                    y += 1

        y += 1  # blank line before options

        # Options list
        max_opt_y = h - 4
        visible_options = min(len(options), max(0, max_opt_y - y))

        for i in range(visible_options):
            try:
                stdscr.addnstr(y + i, 2, options[i], w-3)
            except:
                pass

        if visible_options < len(options):
            try:
                stdscr.addstr(y + visible_options, 2, "[some options hidden – resize taller]")
            except:
                pass

        prompt_y = min(y + visible_options + 1, h - 2)
        try:
            stdscr.addstr(prompt_y, 0, "Enter Number → ")
        except:
            pass

        stdscr.refresh()

        try:
            curses.echo()
            choice_str = stdscr.getstr(prompt_y, 20, 5).decode('utf-8').strip().upper()
            curses.noecho()
        except:
            choice_str = ""

        if choice_str in ('0', ''):
            return None

        if choice_str == 'C':
            return 'C'   # special code for custom fields only

        try:
            ch = int(choice_str)
            if 1 <= ch <= 9:
                return ch
            # Custom field individual edit: 10, 11, 12, ...
            if 10 <= ch < 10 + len(CUSTOM_FIELDS):
                return ch
        except ValueError:
            continue

# ──────────────────────────────────────────────────────────────────────────────
# Hardened edit_item
# ──────────────────────────────────────────────────────────────────────────────
def edit_item(stdscr, inventory, orig_idx):
    if not (0 <= orig_idx < len(inventory)):
        return
    item = inventory[orig_idx]

    choice = select_field_to_edit(stdscr, item)
    if choice is None:
        return

    # Individual custom field edit (choices 10, 11, 12, ...)
    if isinstance(choice, int) and 10 <= choice < 10 + len(CUSTOM_FIELDS):
        field_idx = choice - 10
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

        try:
            val = get_input(stdscr, prompt, 3, 0,
                            min(40, max_prompt_w - len(prompt) + 5),
                            curr_str)
        except curses.error:
            val = curr_str

        if val != curr_str:
            if field['type'] in ('number', 'money'):
                if not val.strip():
                    new_custom[field['name']] = 0.0
                else:
                    try:
                        new_custom[field['name']] = float(val)
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
            **new_custom
        )
        safe_save_inventory(inventory)

        try:
            stdscr.addstr(5, 0, "Custom field updated. Press any key...")
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

    y = 2
    max_prompt_w = w - 20

    def safe_input(label, default_val, y_pos, max_len):
        try:
            prompt = f"{label} [{str(default_val)[:max_prompt_w - len(label) - 5]}]: "
            val = get_input(stdscr, prompt, y_pos, 0, min(max_len, max_prompt_w), "")
            return val if val.strip() else default_val
        except curses.error:
            return default_val

    if choice in (1, 9):
        new_name = safe_input("Name", new_name, y, 40)
        y += 1

    if choice in (2, 9):
        new_qty_str = safe_input("Quantity", new_qty, y, 10)
        try: new_qty = int(new_qty_str)
        except: pass
        y += 1

    if choice in (3, 9):
        new_cost_str = safe_input("Cost ($)", f"{new_cost:.2f}", y, 12)
        try: new_cost = float(new_cost_str)
        except: pass
        y += 1

    if choice in (4, 9):
        new_location = safe_input("Location", new_location, y, 30)
        y += 1

    if choice in (5, 9):
        new_desc = safe_input("Description", new_desc, y, 60)
        y += 1

    if choice in (6, 9):
        new_min_str = safe_input("Min value ($)", f"{new_min:.2f}", y, 12)
        try: new_min = float(new_min_str)
        except: pass
        y += 1

    if choice in (7, 9):
        new_max_str = safe_input("Max value ($)", f"{new_max:.2f}", y, 12)
        try: new_max = float(new_max_str)
        except: pass
        y += 1

    if choice in (8, 9):
        new_sale_str = safe_input("Sale ($)", f"{new_sale:.2f}", y, 12)
        try: new_sale = float(new_sale_str)
        except: pass
        y += 1

    # Custom fields section
    new_custom = item.custom.copy()
    if choice == 9 and CUSTOM_FIELDS:
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

            val = ""
            try:
                val = get_input(stdscr, prompt, y, 0,
                                min(40, max_prompt_w - len(prompt) + 5),
                                curr_str)
            except curses.error:
                pass

            if val != curr_str:
                if field['type'] in ('number', 'money'):
                    if not val.strip():
                        new_custom[field['name']] = 0.0
                    else:
                        try:
                            new_custom[field['name']] = float(val)
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
        stdscr.addstr(min(y + 3, h-3), 0, "Press any key...")
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

        try:
            val = get_input(stdscr, prompt, y, 0,
                            min(40, max_prompt_w - len(prompt) + 5),
                            curr_str)
        except curses.error:
            val = curr_str

        if val != curr_str:
            if field['type'] in ('number', 'money'):
                if not val.strip():
                    new_custom[field['name']] = 0.0
                else:
                    try:
                        new_custom[field['name']] = float(val)
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
    if not (0 <= orig_idx < len(inventory)):
        return False
    item = inventory[orig_idx]

    stdscr.clear()
    stdscr.addstr(2, 0, f"Really delete '{item.name}' ? (y/N)")
    stdscr.refresh()
    ch = stdscr.getch()
    if ch in (ord('y'), ord('Y')):
        del inventory[orig_idx]
        safe_save_inventory(inventory)
        stdscr.addstr(4, 0, "Deleted. Press any key...")
        stdscr.getch()
        return True
    else:
        stdscr.addstr(4, 0, "Cancelled. Press any key...")
        stdscr.getch()
        return False

def view_details(stdscr, inventory, orig_idx):
    if not (0 <= orig_idx < len(inventory)):
        return False
    item = inventory[orig_idx]

    while True:
        stdscr.clear()
        y = 0
        stdscr.addstr(y, 0, "Item Details"); y += 2

        stdscr.addstr(y, 0, f"Name:         {item.name}"); y += 1
        stdscr.addstr(y, 0, f"Quantity:     {item.quantity:,}"); y += 1
        stdscr.addstr(y, 0, f"Cost:         ${item.cost:,.2f}"); y += 1
        stdscr.addstr(y, 0, f"Location:     {item.location}"); y += 1

        for field in CUSTOM_FIELDS:
            value = item.custom.get(field['name'], "")
            disp = str(value)
            if field['type'] == 'money' and isinstance(value, (int, float)):
                disp = f"${value:,.2f}"
            elif field['type'] == 'number' and isinstance(value, (int, float)):
                disp = f"{value:,}"
            stdscr.addstr(y, 0, f"{field['label']:13} {disp}"); y += 1

        stdscr.addstr(y, 0, f"Min Value:    ${item.min_value:,.2f}"); y += 1
        stdscr.addstr(y, 0, f"Max Value:    ${item.max_value:,.2f}"); y += 1
        stdscr.addstr(y, 0, f"Sale:         ${item.sale:,.2f}"); y += 1

        margin = item.margin_percent
        margin_str = f"{margin:.1f}%" if margin is not None else "N/A"
        stdscr.addstr(y, 0, f"Margin:       {margin_str}"); y += 2

        stdscr.addstr(y, 0, f"Description:  {item.description}")
        y += 2

        h, w = stdscr.getmaxyx()
        stdscr.addstr(h-2, 0, "·" * min(w, 80))

        stdscr.addstr(h-1, 0, "e = edit   d = delete   c = config fields   Enter = back")
        stdscr.refresh()

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

def draw_menu(stdscr, selected_row_idx, inventory, search_term="", sort_key='name', sort_directions=None):
    global COLUMNS, AVAILABLE_COLUMNS
    load_config()
    if sort_directions is None:
        sort_directions = {'name': 1, 'quantity': 1, 'location': 1}

    stdscr.clear()
    h, w = stdscr.getmaxyx()

    term = search_term.lower()
    filtered = [item for item in inventory if term in item.name.lower() or term in item.description.lower() or term in item.location.lower()]

    direction = sort_directions.get(sort_key, 1)

    if sort_key == 'name':
        filtered.sort(key=lambda x: x.name.lower(), reverse=(direction < 0))
    elif sort_key == 'quantity':
        filtered.sort(key=lambda x: x.quantity, reverse=(direction < 0))
    elif sort_key == 'location':
        filtered.sort(key=lambda x: x.location.lower(), reverse=(direction < 0))

    original_indices = [inventory.index(item) for item in filtered]

    stdscr.attron(curses.color_pair(1))
    stdscr.addstr(0, 0, PROGRAM_NAME.center(min(w, 100)))
    stdscr.attroff(curses.color_pair(1))

    dir_symbol = "↓" if direction > 0 else "↑"
    stdscr.addstr(1, 0, f"Search: {search_term or '(none)'}   Sort: {sort_key} {dir_symbol}   (s:search n:name t:qty l:loc)")

    stdscr.addstr(2, 0, "─" * min(w, 100))

    header_parts = []
    for col in COLUMNS:
        key = col['key']
        if key.startswith('custom_'):
            label = col.get('label', key)
        else:
            label = AVAILABLE_COLUMNS[key]['label']
        width = col['width']
        align = col.get('align', 'left')
        if align == 'right':
            header_parts.append(label.rjust(width))
        elif align == 'center':
            header_parts.append(label.center(width))
        else:
            header_parts.append(label.ljust(width))
    headers = "  ".join(header_parts)
    stdscr.attron(curses.color_pair(1))
    stdscr.addstr(3, 0, headers[:w])
    stdscr.attroff(curses.color_pair(1))
    
    for idx, item in enumerate(filtered):
        y = idx + 4
        if y >= h - 3: break

        row_parts = []
        for col in COLUMNS:
            key = col['key']
            width = col['width']
            align = col.get('align', 'left')
            if key.startswith('custom_'):
                value = item.custom.get(key[7:], '')
            else:
                value = getattr(item, key, '')
            if value is None:
                value = ''
            
            if key == 'quantity':
                disp = f"{value:,}"
            elif key in ('cost', 'min_value', 'max_value', 'sale'):
                disp = f"${value:,.2f}"
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
        if idx == selected_row_idx: stdscr.attron(curses.A_REVERSE | curses.color_pair(4))

        try:
            stdscr.addnstr(y, 0, line, w-1)
        except curses.error:
            pass

        if idx == selected_row_idx: stdscr.attroff(curses.A_REVERSE | curses.color_pair(4))
        if color_pair: stdscr.attroff(curses.color_pair(color_pair))

    total_items = len(filtered)

    stdscr.addstr(h-2, 0, "·" * min(w, 80))

    stats = f"Items:{total_items}"
    controls = "q:quit a:add s:search r:sale h:history c:configure ENTER:details"
    footer = f"{stats} | {controls}"
    stdscr.addnstr(h-1, 0, footer, w-1)

    return filtered, original_indices

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
# Main loop
# ──────────────────────────────────────────────────────────────────────────────

def show_splash(stdscr):
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
            stdscr.addstr(box_y + 2, box_x,     "│" + PROGRAM_NAME.center(inner_w) + "│")
            stdscr.addstr(box_y + 3, box_x,     "│" + "─" * 36 + "─".rjust(inner_w - 36) + "│")
            stdscr.addstr(box_y + 4, box_x,     "│" + " " * inner_w + "│")
            stdscr.addstr(box_y + 5, box_x,     "│" + SUBTITLE.center(inner_w) + "│")
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

def main(stdscr):
    load_config()
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, THEME_COLOR, -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_RED,    -1)
    curses.init_pair(4, curses.COLOR_GREEN,  -1)

    show_splash(stdscr)

    inventory = load_inventory()

    selected_row_idx = 0
    search_term = ""
    sort_key = 'name'
    sort_directions = {'name': 1, 'quantity': 1, 'location': 1}

    while True:
        # ── Always check size first ───────────────────────────────────────
        if not check_size(stdscr):
            # If too small → wait for resize or any key press
            stdscr.getch()
            stdscr.clear()
            stdscr.refresh()
            continue

        # ── Draw the current state (this is what the user sees right now) ──
        filtered, original_indices = draw_menu(
            stdscr, selected_row_idx, inventory,
            search_term, sort_key, sort_directions
        )
        filtered_len = len(filtered)

        # ── Wait for user input ────────────────────────────────────────────
        key = stdscr.getch()

        # ── Handle special resize event first ──────────────────────────────
        if key == curses.KEY_RESIZE:
            stdscr.clear()
            stdscr.refresh()
            continue

        # ── Normal key handling ────────────────────────────────────────────
        if key == curses.KEY_UP and selected_row_idx > 0:
            selected_row_idx -= 1

        elif key == curses.KEY_DOWN and selected_row_idx < filtered_len - 1:
            selected_row_idx += 1

        elif key == ord('q'):
            break

        elif key == ord('a'):
            add_item(stdscr, inventory)
            selected_row_idx = 0

        elif key == ord('s'):
            search_term = search_mode(stdscr)
            selected_row_idx = 0

        elif key in (ord('n'), ord('t'), ord('l')):
            key_map = {ord('n'):'name', ord('t'):'quantity', ord('l'):'location'}
            new_key = key_map.get(key)
            if new_key == sort_key:
                sort_directions[sort_key] *= -1
            else:
                sort_key = new_key
                sort_directions[sort_key] = 1
            selected_row_idx = 0

        elif key == ord('r') and filtered_len > 0:
            orig_idx = original_indices[selected_row_idx]
            record_sale_ui(stdscr, inventory, orig_idx)
            # After sale we continue → next loop iteration will redraw automatically

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

            # No need to redraw here — next loop iteration will do it

        # After most actions we just continue → the loop will redraw automatically

if __name__ == "__main__":
    if not sys.stdin.isatty():
        print("This program must be run in a terminal.")
        sys.exit(1)
    curses.wrapper(main)