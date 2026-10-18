# TUI Inventory (unified manager + inventory)

## Project Context

CRITICAL: At the start of every conversation, immediately read the file `DOCUMENTATION.md` in this project root. It contains the complete project documentation including architecture, data model, function reference, and data flow diagrams. Treat its contents as essential context for all tasks.

## Quick Reference

- **Single-file Python 3 TUI app** using `curses` (zero external dependencies)
- **Main file**: `inventory.py` — now a unified **manager + inventory** app
- **Manager**: opens first, lists inventory folders, launches a selected
  inventory **in-process** (no subprocess, no per-folder app copies)
- **Inventories**: each is a subfolder containing `inventory_config.json`,
  `inventory.db`, `inventory_sales.log`, `About`, `AboutDefault`
- **Splash**: the manager shows one at startup; each inventory shows its own on
  entry unless its `splash_enabled` setting (System Settings tab) is Off
- **Config**: `manager_config.json` (manager branding) + one
  `inventory_config.json` per inventory folder
- **Run**: `python inventory.py` (requires interactive TTY)

## Git Guidelines

- **Do NOT commit** database, config, or log files: `inventory.db`,
  `inventory.db.bak`, `inventory_sales.log`, `inventory_config.json`,
  `manager_config.json`
