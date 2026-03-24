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

LOW_STOCK_THRESHOLD = 5
CRITICAL_STOCK      = 3

# Global custom fields
CUSTOM_FIELDS = []  # [{'name':str, 'label':str, 'type':'text'|'number'|'money'}, ...]

# ──────────────────────────────────────────────────────────────────────────────
# Config load/save
# ──────────────────────────────────────────────────────────────────────────────

def load_config():
    global CUSTOM_FIELDS
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
                CUSTOM_FIELDS = data.get('custom_fields', [])[:5]
        except Exception:
            CUSTOM_FIELDS = []
    else:
        CUSTOM_FIELDS = []

def save_config():
    with CONFIG_FILE.open('w', encoding='utf-8') as f:
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

def record_sale(inventory, orig_idx, qty_sold, price_each):
    if not (0 <= orig_idx < len(inventory)):
        return False
    item = inventory[orig_idx]
    if qty_sold <= 0 or qty_sold > item.quantity:
        return False

    item.quantity -= qty_sold
    total = qty_sold * price_each

    timestamp = datetime.now().isoformat(timespec='seconds')
    row = {
        'timestamp': timestamp,
        'name': item.name,
        'quantity_sold': qty_sold,
        'price_each': f"{price_each:.2f}",
        'total': f"{total:.2f}",
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
    if not (0 <= orig_idx < len(inventory)):
        return False
    item = inventory[orig_idx]

    stdscr.clear()
    stdscr.addstr(0, 0, f"Record Sale: {item.name}")
    stdscr.addstr(2, 0, f"Current stock: {item.quantity:,}")
    if item.sale > 0:
        stdscr.addstr(3, 0, f"Suggested price: ${item.sale:,.2f}")

    qty_str = get_input(stdscr, "How many sold? ", 5, 0, 10, "1")
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

    default_price = f"{item.sale:.2f}" if item.sale > 0 else "0.00"
    price_str = get_input(stdscr, "Price each ($) ", 6, 0, 12, default_price)
    try:
        price_each = float(price_str or "0.00")
        if price_each <= 0:
            raise ValueError
    except ValueError:
        stdscr.addstr(8, 0, "Price must be > 0")
        stdscr.addstr(10, 0, "Press any key...")
        stdscr.getch()
        return False

    total = qty_sold * price_each
    confirm = f"Sell {qty_sold:,} × {item.name} @ ${price_each:,.2f} = ${total:,.2f} ? (y/N)"
    stdscr.addstr(8, 0, confirm[:curses.COLS-1])
    stdscr.refresh()

    ch = stdscr.getch()
    if ch not in (ord('y'), ord('Y'), ord(' ')):
        stdscr.addstr(10, 0, "Cancelled. Press any key...")
        stdscr.getch()
        return False

    success = record_sale(inventory, orig_idx, qty_sold, price_each)
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

        y = 0
        try:
            stdscr.addstr(y, 0, "Recent Sales (newest first)".center(min(w, 80))); y += 2
        except curses.error:
            pass

        try:
            with SALES_LOG.open('r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
                rows.reverse()

                max_lines = h - y - 4
                for row in rows[:max_lines]:
                    if y >= h - 3:
                        break
                    ts = row.get('timestamp', '?').replace('T', ' ')
                    qty = row.get('quantity_sold', '0')
                    name = row.get('name', '?')[:45]
                    price = row.get('price_each', '0.00')
                    total = row.get('total', '0.00')
                    
                    line = f"{ts}  {qty:>4} × {name:<45} @ ${price} = ${total}"
                    try:
                        stdscr.addnstr(y, 0, line, w-1)
                    except curses.error:
                        pass
                    y += 1

            try:
                stdscr.addstr(y+1, 0, "Press any key to return...")
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
        else:
            break

# ──────────────────────────────────────────────────────────────────────────────
# Custom Fields Configuration Menu
# ──────────────────────────────────────────────────────────────────────────────

def config_menu(stdscr, inventory=None):
    global CUSTOM_FIELDS
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
            stdscr.addstr(0, 0, "Custom Fields (max 5)")
            stdscr.addstr(1, 0, "-" * min(50, w-1))
        except curses.error:
            pass

        y = 3
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
                line = f"{i+1}. {f['label']} ({f['type']}) key:{f['name']}"
                try:
                    stdscr.addnstr(y, 2, line, w-3)
                except curses.error:
                    pass
                y += 1

        y += 1
        try:
            stdscr.addstr(y, 2, f"[{len(CUSTOM_FIELDS)}/5]  a:add  #:del  q:quit")
            stdscr.addstr(y+2, 2, "> ")
        except curses.error:
            pass

        stdscr.refresh()

        curses.echo()
        try:
            cmd = stdscr.getstr(y+2, 4, 15).decode('utf-8').strip().lower()
        except:
            cmd = ""
        curses.noecho()

        if cmd == 'q':
            break
        if cmd == 'a':
            if len(CUSTOM_FIELDS) >= 5:
                try:
                    stdscr.addstr(y+4, 2, "Max 5 fields reached. Press any key...")
                    stdscr.getch()
                except:
                    pass
                continue

            stdscr.clear()
            try:
                stdscr.addstr(2, 2, "Add Field")
                label = get_input(stdscr, "Label: ", 4, 2, 30, "")
                if not label.strip():
                    continue
                defkey = label.lower().replace(" ", "_")[:15]
                key = get_input(stdscr, f"Key [{defkey}]: ", 5, 2, 15, defkey).strip() or defkey
                typ = get_input(stdscr, "Type [text/number/money]: ", 6, 2, 10, "text").lower()
                if typ not in ('text','number','money'):
                    typ = 'text'
                CUSTOM_FIELDS.append({'name':key, 'label':label, 'type':typ})
                save_config()
                stdscr.addstr(8, 2, "Added. Press any key...")
                stdscr.getch()
            except curses.error:
                pass

        elif cmd.isdigit() and 1 <= int(cmd) <= len(CUSTOM_FIELDS):
            try:
                idx = int(cmd) - 1
                removed_key = CUSTOM_FIELDS[idx]['name']
                CUSTOM_FIELDS.pop(idx)
                save_config()
                # Remove the deleted field's data from all inventory items
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

        if cmd == 'q':
            break

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

        stdscr.addstr(y, 0, "e = edit   d = delete   c = config fields   other = back")
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
        else:
            return False

def search_mode(stdscr):
    stdscr.clear()
    stdscr.addstr(0, 0, "Search term (empty to clear):")
    term = get_input(stdscr, "> ", 1, 0, 60)
    return term.strip()

def draw_menu(stdscr, selected_row_idx, inventory, search_term="", sort_key='name', sort_directions=None):
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
        filtered.sort(key=lambda x: x.quantity, reverse=(direction < 0))  # ← fixed direction logic
    elif sort_key == 'location':
        filtered.sort(key=lambda x: x.location.lower(), reverse=(direction < 0))

    original_indices = [inventory.index(item) for item in filtered]

    stdscr.attron(curses.color_pair(1))
    stdscr.addstr(0, 0, "Inventory Tracker".center(min(w, 100)))
    stdscr.attroff(curses.color_pair(1))

    dir_symbol = "↓" if direction > 0 else "↑"
    stdscr.addstr(1, 0, f"Search: {search_term or '(none)'}   Sort: {sort_key} {dir_symbol}   (n:name t:qty l:loc)")

    stdscr.addstr(2, 0, "-" * min(w, 100))

    headers = "Name".ljust(NAME_W) + "Qty".rjust(QTY_W) + "Cost".center(PRICE_W) + "Location".ljust(LOCATION_W) + " Description"
    stdscr.attron(curses.color_pair(1))
    stdscr.addstr(3, 0, headers[:w])
    stdscr.attroff(curses.color_pair(1))

    for idx, item in enumerate(filtered):
        y = idx + 4
        if y >= h - 3: break

        name_disp = (item.name[:NAME_W-2] + '…') if len(item.name) >= NAME_W-1 else item.name
        qty_part  = f"{item.quantity:,}".rjust(QTY_W)
        cost_part = f"${item.cost:,.2f}".center(PRICE_W)
        loc_disp  = (item.location[:LOCATION_W-2] + '…') if len(item.location) >= LOCATION_W-1 else item.location
        desc_avail = max(10, w - (NAME_W + QTY_W + PRICE_W + LOCATION_W + 9))
        desc_text = item.description.replace("\n", " ").replace("\r", " ")
        desc_part = (desc_text[:desc_avail-1] + '…') if len(desc_text) > desc_avail else desc_text

        line = name_disp.ljust(NAME_W) + qty_part + cost_part + loc_disp.ljust(LOCATION_W) + " " + desc_part

        color_pair = 0
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
    low_stock   = sum(1 for item in filtered if item.stock_status in ("low", "critical"))

    stats = f"Items:{total_items} Low:{low_stock}"
    controls = "q:quit a:add s:search r:sale h:history c:cfg ENTER:details"
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
    curses.init_pair(1, curses.COLOR_CYAN,   -1)
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
            stdscr.addstr(box_y + 2, box_x,     "│" + "TUI Inventory".center(inner_w) + "│")
            stdscr.addstr(box_y + 3, box_x,     "│" + "─" * 36 + "─".rjust(inner_w - 36) + "│")
            stdscr.addstr(box_y + 4, box_x,     "│" + " " * inner_w + "│")
            stdscr.addstr(box_y + 5, box_x,     "│" + "Track your inventory with ease".center(inner_w) + "│")
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
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_CYAN,   -1)
    curses.init_pair(2, curses.COLOR_YELLOW, -1)
    curses.init_pair(3, curses.COLOR_RED,    -1)
    curses.init_pair(4, curses.COLOR_GREEN,  -1)

    show_splash(stdscr)

    inventory = load_inventory()
    load_config()

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