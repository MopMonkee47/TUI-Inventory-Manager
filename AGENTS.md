# TUI Inventory

## Project Context

CRITICAL: At the start of every conversation, immediately read the file `DOCUMENTATION.md` in this project root. It contains the complete project documentation including architecture, data model, function reference, and data flow diagrams. Treat its contents as essential context for all tasks.

## Quick Reference

- **Single-file Python 3 TUI app** using `curses` (zero external dependencies)
- **Main file**: `inventory.py`
- **Data files**: `inventory.db` (CSV), `inventory.db.bak`, `inventory_sales.log`, `inventory_config.json`
- **Run**: `python inventory.py` (requires interactive TTY)

## Git Guidelines

- **Do NOT commit** database, config, or log files: `inventory.db`, `inventory.db.bak`, `inventory_sales.log`, `inventory_config.json`
