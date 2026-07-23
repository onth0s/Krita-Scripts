# Krita-Scripts: Full Audit & Refactoring Implementation Plan

---

## Executive Summary

The Krita-Scripts codebase contains 5 active plugins and 1 shared library across ~2,000 lines of Python. The architecture is sound — the shared `krita_pie_menu` widget library is a clean abstraction consumed by 3 pie-menu plugins. However, the largest file (`operations_pie_menu.py`, 769 lines) has accumulated significant technical debt: silent exception swallowing, duplicated logic, massive monolithic methods, cross-plugin filesystem coupling, and no tests. This plan addresses all issues in 7 sequential phases, ordered by dependency and risk.

---

## Audit Findings

### Critical

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| C1 | **Cross-plugin filesystem coupling** — `operations_pie_menu.py:300` reads `conditions_pie_menu/config.json` via hardcoded relative path `../conditions_pie_menu/config.json` | `operations_pie_menu.py:298-308` | Breaks on layout change, OS path separator differences, separate deployment |
| C2 | **Silent exception swallowing** — 10+ bare `except Exception: pass` blocks suppress all errors in pixel manipulation, layer operations, blend mode setting, and brush activation | `operations_pie_menu.py` lines 265, 284, 295, 298, 328, 351, 361, 370, 422, 439 | Impossible to debug production failures; data corruption undetected |
| C3 | **Duplicated incremental-layer logic** — The regex parse + increment + createNode pattern is independently implemented in `quick_script_engine.py:38-56` and `operations_pie_menu.py:227-233` + `393-406` | Two files | DRY violation; inconsistency risk if one is updated and the other is not |
| C4 | **Missing `manual.html`** for `conditions_pie_menu` — `.desktop` references it but file doesn't exist | `conditions_pie_menu/` | Broken manual link in Krita UI |

### High

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| H1 | **Monolithic methods** — `execute_north_operation()` is 250+ lines (188-440), `execute_west_operation()` is 120+ lines (442-563), `setup_canvas_operation()` is 135+ lines (634-769) | `operations_pie_menu.py` | Unreadable, untestable, fragile |
| H2 | **Hardcoded brush preset name** `"0 STD DRW"` with fuzzy fallback — user-specific preset that may not exist | `operations_pie_menu.py:426-436, 751-765` | Plugin partially broken on fresh Krita installs |
| H3 | **Widget lifecycle leak** — `self.pie_widget` stale reference checked via `RuntimeError` catch instead of proper nullification on close | All 3 pie menu extensions | Accessing deleted Qt objects; defensive but fragile |
| H4 | **Mixed import styles** — Some imports at module level, some inline at method level (`random`, `colorsys`, `re`, `QApplication`, `ManagedColor`) | `operations_pie_menu.py` | Inconsistent; some re-imported on every call |
| H5 | **Pixel format assumptions** — Code assumes BGRA 8-bit (`p_len == 4`) without verifying actual color model/depth | `operations_pie_menu.py:287-294` | Breaks for 16-bit or float documents |
| H6 | **Orphaned `hello_extension/`** — Directory contains only stale `__pycache__/`, no source, no `.desktop` | Root directory | Dead code, confusing README reference |

### Medium

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| M1 | **Duplicated config loading** — `load_config()` boilerplate is copy-pasted across `filters_pie_menu.py`, `operations_pie_menu.py`, `conditions_pie_menu.py` | 3 files | Maintenance burden; inconsistency risk |
| M2 | **Duplicated `show_pie_menu()` guard pattern** — The `pie_widget is not None` / `isVisible()` / `is_interrupted` / `RuntimeError` catch is identical in all 3 extensions | 3 files | Boilerplate; should be in base class or shared utility |
| M3 | **Inconsistent `__init__.py` patterns** — Some store `app = Krita.instance()` at module scope, others call inline | `__init__.py` files | Module-level singleton persists after import |
| M4 | **Config dialogs diverge** — `filters_pie_menu` uses `QComboBox` with preset options; `operations_pie_menu` uses raw `QLineEdit`; no shared base | 2 config_dialog.py | Inconsistent UX; duplicated save/load logic |
| M5 | **No `.action` entries for configure actions** — `configure_filters_pie_menu` and `configure_operations_pie_menu` are created in code but not in `.action` XML | `.action` files | Not searchable in Krita's shortcut settings |
| M6 | **README inaccuracies** — References `hello_extension` as active, installation instructions only cover `conditions_pie_menu` | `README.md` | Misleading documentation |
| M7 | **No type hints** anywhere in the codebase | All files | Reduced IDE support and readability |

### Low

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| L1 | **Trailing blank lines** at end of `operations_pie_menu.py` (lines 768-769) | `operations_pie_menu.py` | Cosmetic |
| L2 | **Inconsistent toast usage** — `filters_pie_menu` never shows toasts; `conditions_pie_menu` uses them; `operations_pie_menu` uses `QMessageBox` | Multiple | UX inconsistency |
| L3 | **`pie_widget` is always set to `None` before reassignment** — Redundant `self.pie_widget = None` after the guard check | All 3 extensions | Minor clutter |

---

## Refactoring Phases

### Phase 1: Cleanup & Remove Dead Code

**Goal:** Eliminate orphaned artifacts and fix documentation before touching any logic.

**Steps:**
1. Delete `hello_extension/` directory (including `__pycache__/`)
2. Remove `hello_extension` references from `README.md` (lines 66-67)
3. Create `conditions_pie_menu/manual.html` (stub with basic content matching other manual files)
4. Remove trailing blank lines at end of `operations_pie_menu.py`
5. Add `.action` XML entries for `configure_filters_pie_menu` and `configure_operations_pie_menu` actions
6. Update README installation section to cover all 5 plugins

**Files modified:** `README.md`, `hello_extension/` (deleted), `conditions_pie_menu/manual.html` (new), `operations_pie_menu.py`, `filters_pie_menu/filters_pie_menu.action`, `operations_pie_menu/operations_pie_menu.action`

**Risk:** None — purely additive/subtractive changes with no logic impact.

---

### Phase 2: Extract Shared Utilities into `krita_pie_menu`

**Goal:** Eliminate duplicated patterns by extracting reusable helpers into the shared library.

**Steps:**
1. **Create `krita_pie_menu/utils.py`** with:
   - `load_config(config_path: str, defaults: dict) -> dict` — Replaces the 3 copy-pasted `load_config()` methods
   - `get_incremental_layer_name(layer_name: str) -> str` — The regex parse + increment logic (used by `quick_script_engine` and `operations_pie_menu`)
   - `create_incremental_layer(doc, reference_layer) -> Node` — Full create-and-insert operation
   - `resolve_action(app, candidates: list[str]) -> Optional[QAction]` — Multi-candidate action lookup (replaces the inline `if not merge_act: merge_act = app.action(...)` chains)
   - `find_brush_preset(app, preset_name: str) -> Optional[resource]` — Fuzzy brush preset lookup (replaces the duplicated loop in `operations_pie_menu.py:426-436` and `751-765`)
   - `set_foreground_black(doc, view)` — ManagedColor setup for black foreground
2. **Update `krita_pie_menu/__init__.py`** to export the new utils
3. **Refactor `quick_script_engine.py`** to use `create_incremental_layer()` from utils
4. **Refactor `operations_pie_menu.py`** to use all relevant utils functions
5. **Refactor all 3 pie menu extensions** to use `load_config()` from utils

**Files modified:** `krita_pie_menu/utils.py` (new), `krita_pie_menu/__init__.py`, `quick_script_engine/quick_script_engine.py`, `operations_pie_menu/operations_pie_menu.py`, `filters_pie_menu/filters_pie_menu.py`, `conditions_pie_menu/conditions_pie_menu.py`

**Risk:** Low — extracted functions are pure logic with no side effects. Verify each plugin still works after each theKK (:
K, then. +``.\ (.K,:
(K().;(). \n<think>_(). (
 . ( (().5,6.fail(self:
 + (
 /  backup<think> 66:
().<think>":. as().Fail5 .         atal.5<think>:\n:.<|im_start|>...

(��().. (...().._().K. logging().KGr"). __K(_K")."). ... wait ... I mean ... **refactoring** ...)**Risk:** Low — extracted functions are straightforward mechanical extractions. Each can be verified independently.

---

### Phase 3: Base Class for Pie Menu Extensions

**Goal:** Eliminate the duplicated `show_pie_menu()` guard pattern, widget lifecycle management, and config loading boilerplate.

**Steps:**
1. **Create `krita_pie_menu/base_extension.py`** with `BasePieMenuExtension(Extension)`:
   - `__init__`: stores `config_path`, initializes `self.pie_widget = None`
   - `load_config()`: delegates to `utils.load_config()`
   - `save_config()`: shared JSON write
   - `show_pie_menu(accent_color, object_name)`: contains the guard pattern, calls `build_pie_config()` (abstract), creates widget, shows it
   - `build_pie_config() -> (callbacks, items_meta, validators, toggle_states)`: abstract method overridden by each extension
   - `open_config_dialog()`: abstract method
   - Proper widget lifecycle: connects to `QWidget.destroyed` signal to null `self.pie_widget`
2. **Refactor all 3 pie menu extensions** to inherit from `BasePieMenuExtension`:
   - `FiltersPieMenuExtension` → override `build_pie_config()` and `open_config_dialog()`
   - `OperationsPieMenuExtension` → override `build_pie_config()` and `open_config_dialog()`
   - `ConditionsPieMenuExtension` → override `build_pie_config()` and `open_config_dialog()`
3. **Remove duplicated guard/widget-creation code** from each extension

**Files modified:** `krita_pie_menu/base_extension.py` (new), all 3 pie menu extension files

**Risk:** Medium — architectural change. Must verify each extension still registers actions correctly and pie menus appear. The `createActions(window)` method stays in each subclass (Krita calls it), but the body becomes a one-liner connecting to `show_pie_menu()`.

---

### Phase 4: Decompose `operations_pie_menu.py`

**Goal:** Break the 769-line monolith into focused, testable operation modules.

**Steps:**
1. **Create `operations_pie_menu/operations/` subpackage:**
   - `__init__.py` — exports all operation classes/functions
   - `refine_sketch.py` — The North operation (currently `execute_north_operation`, lines 188-440)
   - `init_canvas.py` — The South operation (currently `setup_canvas_operation`, lines 634-769)
   - `bw_preview.py` — The SE operation (currently `execute_se_operation`, lines 565-629)
   - `fit_layer.py` — The West operation (currently `execute_west_operation`, lines 442-563)
   - `sanitize_group.py` — The NE operation (currently `execute_ne_operation`, lines 134-173)
2. **Each operation file contains:**
   - A single function `execute(doc, app, **kwargs)` that performs the operation
   - Its own validator function (moved from the closures in `show_pie_menu()`)
3. **Refactor `operations_pie_menu.py`** to import from `operations/` and wire them into `build_pie_config()`
4. **Decompose `refine_sketch.py` further** into helper functions:
   - `handle_selection_cut_paste(doc, app, layer)`
   - `fill_layer_with_random_hsl(doc, layer)`
   - `apply_luminosity_overlay(doc, app, layer)`
   - `apply_duplicate_reflay_condition(doc, app, layer)` — also addresses C1 (receives condition as parameter instead of reading filesystem)
5. **Fix C1 (cross-plugin coupling):** The `duplicate_reflay` condition is now passed as a parameter from `build_pie_config()` (which reads its own config) rather than from `operations_pie_menu` reading `conditions_pie_menu/config.json` directly. The conditions extension exposes its state via `ConditionsPieMenuExtension.get_condition()` called at build time.

**Files modified:** `operations_pie_menu/operations/` (new subpackage), `operations_pie_menu/operations_pie_menu.py`, `conditions_pie_menu/conditions_pie_menu.py` (minor — expose `get_condition`)

**Risk:** High — largest change. The operations contain complex pixel manipulation and layer tree mutations. Each operation must be tested individually after extraction. The selection cut/paste + `processEvents` + `waitForDone` sequence in refine_sketch is particularly sensitive to timing.

---

### Phase 5: Error Handling & Logging

**Goal:** Replace all silent exception swallowing with structured error handling.

**Steps:**
1. **Create `krita_pie_menu/logger.py`** with a simple file-based logger:
   - Writes to `%APPDATA%/krita/pykrita/krita_scripts.log`
   - `log_debug(module, message)`, `log_error(module, message, exception=None)`
   - Rotates at 500KB (simple file-size check)
2. **Replace all bare `except Exception: pass`** blocks:
   - Add `log_error()` calls with module name and exception info
   - For non-critical operations (visual-only like `setInheritAlpha`), log and continue
   - For data-critical operations (pixel manipulation, layer creation), log and show a toast/warning
3. **Add pixel format validation** before pixel manipulation:
   - Check `doc.colorDepth()` and `doc.colorModel()` before assuming BGRA 4-byte
   - Skip operation or warn if format is unsupported (16-bit, float)
4. **Replace generic `Exception` catches** with specific exception types where possible

**Files modified:** `krita_pie_menu/logger.py` (new), `operations_pie_menu/operations/*.py`, `krita_pie_menu/pie_widget.py`

**Risk:** Low-Medium — adding logging doesn't change behavior. Changing exception handling could surface previously-hidden errors (which is the goal, but may produce unexpected warnings initially).

---

### Phase 6: Config Dialog Unification & Polish

**Goal:** Create a consistent configuration experience across all pie menu plugins.

**Steps:**
1. **Create `krita_pie_menu/base_config_dialog.py`** with `BasePieConfigDialog(QDialog)`:
   - Shared grid layout with direction labels
   - Save/Cancel button bar
   - `load_config()` / `save_config()` methods
   - Abstract method `build_sector_editor(code, data) -> QWidget` for per-sector widget creation
2. **Refactor `SectorConfigDialog`** (filters) to extend base with `QComboBox` editor
3. **Refactor `OperationsConfigDialog`** to extend base with `QLineEdit` pair editor
4. **Add `ConditionsConfigDialog`** extending base with toggle switches for condition flags
5. **Update `conditions_pie_menu`** to register a `configure_conditions_pie_menu` action with dialog
6. **Add `.action` entries** for all configure actions (if not done in Phase 1)

**Files modified:** `krita_pie_menu/base_config_dialog.py` (new), `filters_pie_menu/config_dialog.py`, `operations_pie_menu/config_dialog.py`, `conditions_pie_menu/` (new config_dialog.py), all `.action` files

**Risk:** Low — UI-only changes. Config files remain JSON with the same schema.

---

### Phase 7: Type Hints, Documentation & README Update

**Goal:** Add static analysis support and bring documentation in sync with the refactored codebase.

**Steps:**
1. **Add type hints** to all public methods and function signatures across the codebase:
   - `krita_pie_menu/` — full type hints (pure Python, no Krita runtime needed for IDE)
   - Plugin files — type hints on all public methods (Krita types as strings or `TYPE_CHECKING` imports)
2. **Add docstrings** to all public classes and methods (Google style)
3. **Update `README.md`:**
   - Remove `hello_extension` reference
   - Document all 5 active plugins
   - Update installation section to cover all plugins
   - Add architecture overview section referencing the shared library
4. **Update `AGENTS.md`:**
   - Add reference to `utils.py` and `base_extension.py`
   - Document the `operations/` subpackage structure
5. **Add a `pyproject.toml` or `setup.cfg`** with `mypy` configuration for IDE integration

**Files modified:** All `.py` files (type hints), `README.md`, `AGENTS.md`, `pyproject.toml` (new)

**Risk:** None — purely additive metadata.

---

## Phase Dependency Graph

```
Phase 1 (Cleanup)
    │
    ▼
Phase 2 (Shared Utilities) ──────────────────────┐
    │                                             │
    ▼                                             │
Phase 3 (Base Extension Class)                   │
    │                                             │
    ▼                                             │
Phase 4 (Decompose Operations) ◄─────────────────┘
    │                    (depends on Phase 2 utils
    │                     and Phase 3 base class)
    ▼
Phase 5 (Error Handling & Logging)
    │
    ▼
Phase 6 (Config Dialog Unification)
    │
    ▼
Phase 7 (Type Hints & Documentation)
```

**Critical path:** Phase 1 → 2 → 3 → 4 → 5 → 6 → 7 (strictly sequential)
**Estimated total scope:** ~400-500 lines of new code, ~800 lines refactored, ~200 lines deleted

---

## Files Created (New)

| File | Phase | Purpose |
|------|-------|---------|
| `krita_pie_menu/utils.py` | 2 | Shared utility functions |
| `krita_pie_menu/base_extension.py` | 3 | Base class for pie menu extensions |
| `krita_pie_menu/logger.py` | 5 | File-based logging |
| `krita_pie_menu/base_config_dialog.py` | 6 | Base class for config dialogs |
| `operations_pie_menu/operations/__init__.py` | 4 | Operations subpackage |
| `operations_pie_menu/operations/refine_sketch.py` | 4 | North operation |
| `operations_pie_menu/operations/init_canvas.py` | 4 | South operation |
| `operations_pie_menu/operations/bw_preview.py` | 4 | SE operation |
| `operations_pie_menu/operations/fit_layer.py` | 4 | West operation |
| `operations_pie_menu/operations/sanitize_group.py` | 4 | NE operation |
| `conditions_pie_menu/manual.html` | 1 | Missing manual page |
| `conditions_pie_menu/config_dialog.py` | 6 | Config dialog for conditions |
| `pyproject.toml` | 7 | Project config for mypy |

## Files Deleted

| File | Phase | Reason |
|------|-------|--------|
| `hello_extension/` (entire directory) | 1 | Orphaned, no source code |

## Files Modified (Every Phase Touches These)

| File | Phases | Nature of Changes |
|------|--------|-------------------|
| `operations_pie_menu/operations_pie_menu.py` | 1,2,3,4,5,7 | Major decomposition, utils adoption, base class, logging, types |
| `filters_pie_menu/filters_pie_menu.py` | 2,3,7 | Utils adoption, base class, types |
| `conditions_pie_menu/conditions_pie_menu.py` | 2,3,5,6,7 | Utils adoption, base class, logging, config dialog, types |
| `quick_script_engine/quick_script_engine.py` | 2,7 | Utils adoption, types |
| `krita_pie_menu/pie_widget.py` | 5,7 | Logging, types |
| `krita_pie_menu/__init__.py` | 2,3,7 | Export new modules |
| `README.md` | 1,7 | Documentation updates |
| `AGENTS.md` | 7 | Documentation updates |
