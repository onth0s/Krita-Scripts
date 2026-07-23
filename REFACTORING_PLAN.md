# Krita-Scripts: Full Audit & Refactoring Implementation Plan

---

## Executive Summary

The Krita-Scripts codebase contains **5 active plugins** and **1 shared library** across ~1,800 lines of Python. The architecture is mature: a shared `krita_pie_menu` library provides a base extension class, pie menu widget, config dialog base, logger, toast notifications, and utility functions — all consumed by 3 pie-menu plugins, a standalone quick-script engine, and a dummy docker template.

Prior refactoring phases (1–6 of the original plan) have already been executed: `utils.py`, `base_extension.py`, `base_config_dialog.py`, `logger.py`, and the `operations/` subpackage all exist and are wired in. What remains is a set of **structural inconsistencies, dead code stubs, cross-plugin coupling, missing type annotations, and documentation drift** that this plan addresses in 5 sequential phases.

---

## Current Codebase Inventory

| Component | Files | Lines | Status |
|-----------|-------|-------|--------|
| `krita_pie_menu/` (shared library) | 7 `.py` | ~580 | Stable, well-structured |
| `filters_pie_menu/` | 4 `.py` + `.desktop` + `.action` | ~230 | Production-ready |
| `operations_pie_menu/` | 3 `.py` + 5 operation modules | ~470 | Production-ready, stubs remain |
| `conditions_pie_menu/` | 3 `.py` + `.desktop` + `.action` | ~190 | Partially implemented (7/8 stubs) |
| `quick_script_engine/` | 2 `.py` + `.desktop` + `.action` | ~50 | Minimal, production-ready |
| `dummy_docker/` | 2 `.py` + `.desktop` | ~50 | Template/demo |

---

## Audit Findings

### Critical

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| C1 | **Cross-plugin filesystem coupling** — `operations_pie_menu.py:50-53` reads `conditions_pie_menu/config.json` via hardcoded relative path `../conditions_pie_menu/config.json` using `os.path.dirname` chain | `operations_pie_menu.py:50-53` | Breaks if plugins are deployed separately or directory layout changes; violates plugin encapsulation |
| C2 | **`bw_preview.py:49` calls undefined `log_warning`** — imports `log_error, log_info` but calls `log_warning` which is not imported. Will raise `NameError` at runtime when blend mode setting fails | `bw_preview.py:49` | Runtime crash on the error path of B&W layer creation |

### High

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| H1 | **Inconsistent `__init__.py` registration patterns** — `filters_pie_menu` and `operations_pie_menu` store `app = Krita.instance()` at module scope; `conditions_pie_menu` and `quick_script_engine` call `Krita.instance()` inline; `dummy_docker` stores `instance` at module scope | All `__init__.py` | Module-level singletons persist after import; inconsistent style |
| H2 | **Condition stubs use modal QMessageBox** — 6 of 8 conditions are stubs using modal `QMessageBox.information`. Should use lightweight non-blocking ToastNotifications while retaining stub slots for future conditions | `conditions_pie_menu.py:57-63` | UX annoyance (modal dialogs block UI for stubs); inconsistent with toast framework |
| H3 | **Stub sectors in operations_pie_menu** — `E/SW/W/NW` are stubs (`disabled_stub` validator always returns `False`). `DEFAULT_OPERATIONS_CONFIG` contains `op_stub_east`, `op_stub_sw`, `op_stub_nw` action IDs that don't exist in Krita | `operations_pie_menu.py:20-25, 65-69` | 4 of 8 sectors are dead; misleading config defaults |
| H4 | **Missing `conditions_pie_menu` from `.action` file for configure action** — `configure_conditions_pie_menu` action is created in `conditions_pie_menu.py:36-37` but the `.action` XML only registers `trigger_conditions_pie_menu`. Compare: `operations_pie_menu.action` and `filters_pie_menu.action` both register their configure actions | `conditions_pie_menu/conditions_pie_menu.action` | Configure action not searchable in Krita shortcut settings |
| H5 | **`fit_layer.py` lacks user toggle for aspect ratio preservation** — Defaults to `Qt.IgnoreAspectRatio`. Requires a condition flag in `conditions_pie_menu` to allow toggling Keep Aspect Ratio behavior on demand | `fit_layer.py`, `conditions_pie_menu.py` | Flexibility for users wanting uniform vs forced-fill layer fitting |

### Medium

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| M1 | **Duplicated validator functions** — `validate_refine_sketch()` in `refine_sketch.py` repeats the same doc/node/type/empty checks that `execute_refine_sketch()` does at lines 179-204. Similarly `validate_sanitize_group()` overlaps with `execute_sanitize_group()` lines 46-64 | `refine_sketch.py`, `sanitize_group.py` | DRY violation; validators and executors can drift |
| M2 | **No type hints anywhere** — Zero type annotations across the entire codebase. All function signatures are untyped | All `.py` files | No IDE autocompletion, no static analysis, reduced readability |
| M3 | **No docstrings on shared library public API** — `utils.py`, `base_extension.py`, `base_config_dialog.py`, `pie_widget.py` lack docstrings on most public methods | `krita_pie_menu/*.py` | Poor discoverability for plugin authors |
| M4 | **`quick_script_engine` does not use `BasePieMenuExtension`** — It extends raw `Extension` instead of the shared base class, despite being a simple single-action extension | `quick_script_engine.py:4` | Inconsistent inheritance; misses base class guard patterns |
| M5 | **Missing `__init__.py` docstrings** — All 6 `__init__.py` files are bare imports with no module docstring | All `__init__.py` | No IDE module-level documentation |
| M6 | **README references emojis** that may not render in all terminals/docs | `README.md` | Minor cosmetic |
| M7 | **`pyproject.toml` has no `[tool.ruff]` or `[tool.flake8]` section** — Only mypy is configured; no linter config exists | `pyproject.toml` | No automated style enforcement |

### Low

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| L1 | **Inconsistent toast vs QMessageBox usage** — `filters_pie_menu` never uses toasts; `conditions_pie_menu` uses toasts for toggle feedback; `operations_pie_menu` uses QMessageBox for errors but toasts are available | Multiple | UX inconsistency across plugins |
| L2 | **`SECTOR_NAMES` duplicated in 3 files** — Defined in `base_config_dialog.py`, `filters_pie_menu/config_dialog.py`, and `operations_pie_menu/config_dialog.py` identically | 3 files | DRY violation; should import from base |
| L3 | **`dummy_docker` has no logging or error handling** — Raw `Krita.instance()` calls with no null checks | `dummy_docker.py` | Fragile if document state is unexpected |
| L4 | **Hardcoded magic numbers** — Widget size `520`, center `260`, button size `150x36`, deadzone `45` in `pie_widget.py` are not named constants | `pie_widget.py` | Readability; magic numbers scattered across methods |

---

## Refactoring Phases

### Phase 1: Bug Fixes & Dead Code Cleanup & Conditions Enhancement

**Goal:** Fix critical bugs, refine condition stubs to non-blocking ToastNotifications, add `keep_aspect_ratio` toggle to `conditions_pie_menu`, and clean up dead stubs.

**Steps:**

1. **Fix C2: Add missing `log_warning` import to `bw_preview.py`**
   - File: `operations_pie_menu/operations/bw_preview.py:4`
   - Change: `from krita_pie_menu import log_error, log_info` → `from krita_pie_menu import log_error, log_info, log_warning`

2. **Refine `conditions_pie_menu` stubs & add `keep_aspect_ratio` condition toggle**
   - File: `conditions_pie_menu/conditions_pie_menu.py`
   - Add `"keep_aspect_ratio": False` to `DEFAULT_CONDITIONS_CONFIG` and assign sector `W` to `"Keep Aspect Ratio (Fit)"`.
   - Implement `toggle_keep_aspect_ratio()` with ToastNotification feedback ("Keep Aspect Ratio: ON/OFF").
   - Update stub callbacks to use `ToastNotification.show_toast(f"Condition [{code}] stub", toast_type="info")` instead of modal `QMessageBox`.

3. **Integrate `keep_aspect_ratio` condition flag in `fit_layer.py`**
   - File: `operations_pie_menu/operations/fit_layer.py`
   - Maintain default `Qt.IgnoreAspectRatio` behavior.
   - Query `keep_aspect_ratio` condition from `conditions_pie_menu/config.json`. If enabled, apply proportional scaling calculations (`Qt.KeepAspectRatio`), otherwise default to standard integer scaling with `Qt.IgnoreAspectRatio`.

4. **Fix H4: Add `configure_conditions_pie_menu` entry to conditions `.action` file**
   - File: `conditions_pie_menu/conditions_pie_menu.action`
   - Add an `<Action name="configure_conditions_pie_menu">` block matching the pattern in `operations_pie_menu.action`

5. **Fix H1: Normalize all `__init__.py` to use inline `Krita.instance()` pattern**
   - Files: `filters_pie_menu/__init__.py`, `operations_pie_menu/__init__.py`, `dummy_docker/__init__.py`
   - Change module-level `app = Krita.instance()` / `instance = Krita.instance()` to direct inline calls like `conditions_pie_menu/__init__.py`

6. **Remove dead stub action IDs from `DEFAULT_OPERATIONS_CONFIG`**
   - File: `operations_pie_menu/operations_pie_menu.py:20-25`
   - Replace `op_stub_east`, `op_stub_sw`, `op_stub_nw` with descriptive placeholder IDs like `op_placeholder_east` or remove the stub entries entirely and document them as "Unassigned"

7. **Remove dead stub validators from `build_pie_config()`**
   - File: `operations_pie_menu/operations_pie_menu.py:65-69`
   - Remove the `disabled_stub` closure and the loop that assigns it to `['E', 'SW', 'NW']`

**Files modified:** `bw_preview.py`, `conditions_pie_menu.py`, `fit_layer.py`, `conditions_pie_menu.action`, `filters_pie_menu/__init__.py`, `operations_pie_menu/__init__.py`, `dummy_docker/__init__.py`, `operations_pie_menu.py`

**Risk:** Low — surgical bug fixes, UX improvement (toasts instead of modals), and clean toggle feature integration.

---

### Phase 2: Eliminate Cross-Plugin Coupling

**Goal:** Remove the filesystem dependency between `operations_pie_menu` and `conditions_pie_menu`.

**Steps:**

1. **Remove `_get_duplicate_reflay_condition()` from `operations_pie_menu.py`**
   - File: `operations_pie_menu/operations_pie_menu.py:46-53`
   - Delete the method entirely (it reads `../conditions_pie_menu/config.json` via hardcoded path)

2. **Move `duplicate_reflay` condition read into `build_pie_config()` at callback construction time**
   - File: `operations_pie_menu/operations_pie_menu.py:71`
   - Replace `dup_reflay = self._get_duplicate_reflay_condition()` with a direct call: `dup_reflay = self._read_conditions_config("duplicate_reflay")`

3. **Add `_read_conditions_config()` helper that uses the same `load_config` utility but with a clean path resolution**
   - File: `operations_pie_menu/operations_pie_menu.py`
   - New method that resolves the conditions config path relative to `__file__` with clear documentation of the coupling

4. **Add a comment block documenting the cross-plugin dependency**
   - Explain why operations_pie_menu needs to read conditions_pie_menu config and under what conditions this coupling would break

**Files modified:** `operations_pie_menu/operations_pie_menu.py`

**Risk:** Low — the coupling is real and necessary (operations reads a condition flag set by conditions). The fix is to make the coupling explicit and robust rather than removing it.

---

### Phase 3: Extract Duplicated Constants & DRY Validators

**Goal:** Remove the 3× duplicated `SECTOR_NAMES` and reduce validator/executor duplication.

**Steps:**

1. **Remove `SECTOR_NAMES` from `filters_pie_menu/config_dialog.py:23-32`**
   - Import from `krita_pie_menu.base_config_dialog` instead

2. **Remove `SECTOR_NAMES` from `operations_pie_menu/config_dialog.py:4-13`**
   - Import from `krita_pie_menu.base_config_dialog` instead

3. **Remove `SECTOR_NAMES` from `conditions_pie_menu/config_dialog.py:4-13`**
   - Import from `krita_pie_menu.base_config_dialog` instead

4. **Refactor validators to use a shared factory function in `utils.py`**
   - Add `make_doc_active_validator(extra_checks=None)` to `krita_pie_menu/utils.py`
   - This returns a validator function that checks for active document, active node, and optional custom checks
   - Replaces the duplicated doc/node/type checks in `validate_refine_sketch`, `validate_sanitize_group`, `validate_fit_layer`, and the inline `validate_filter_context` in `filters_pie_menu.py`

**Files modified:** `krita_pie_menu/utils.py`, `krita_pie_menu/__init__.py`, `filters_pie_menu/config_dialog.py`, `operations_pie_menu/config_dialog.py`, `conditions_pie_menu/config_dialog.py`, `refine_sketch.py`, `sanitize_group.py`, `fit_layer.py`, `filters_pie_menu.py`

**Risk:** Low — mechanical extraction of identical code into shared location.

---

### Phase 4: Type Hints & Docstrings

**Goal:** Add comprehensive type annotations and docstrings to all public API surfaces.

**Steps:**

1. **`krita_pie_menu/utils.py`** — Add type hints to all 7 public functions. Add module docstring.

2. **`krita_pie_menu/base_extension.py`** — Add type hints to all public methods. Add class docstring and method docstrings.

3. **`krita_pie_menu/base_config_dialog.py`** — Add type hints. Add class/method docstrings.

4. **`krita_pie_menu/pie_widget.py`** — Add type hints to all public methods. Add named constants for magic numbers (WIDGET_SIZE=520, CENTER=260, BTN_SIZE=(150,36), DEADZONE_RADIUS=45).

5. **`krita_pie_menu/logger.py`** — Add type hints to `log_info`, `log_warning`, `log_error`.

6. **`krita_pie_menu/toast_notification.py`** — Add type hints to `show_toast`, `get_left_dockers_offset`.

7. **`krita_pie_menu/__init__.py`** — Add module docstring.

8. **All plugin files** — Add type hints to all public methods (`createActions`, `build_pie_config`, `open_config_dialog`, all `execute_*` and `validate_*` functions).

9. **All `__init__.py` files** — Add module-level docstrings.

10. **Operation modules** — Add docstrings to `refine_sketch.py`, `sanitize_group.py`, `bw_preview.py`, `init_canvas.py`, `fit_layer.py` functions.

**Files modified:** All `.py` files

**Risk:** None — purely additive metadata with no behavioral changes.

---

### Phase 5: Documentation & Project Config

**Goal:** Bring README, AGENTS.md, and pyproject.toml in sync with the current codebase state.

**Steps:**

1. **Update `README.md`**
   - Remove emoji prefixes from section headers (cleaner for terminal rendering)
   - Add "Architecture" section documenting the shared library pattern
   - Add "Development" section with testing/linting instructions
   - Ensure installation instructions cover all 5 plugins (currently correct)
   - Add note about the `operations/` subpackage structure

2. **Update `AGENTS.md`**
   - Add reference to `utils.py` public API
   - Add reference to `base_extension.py` and `base_config_dialog.py`
   - Document the `operations/` subpackage and each operation module
   - Update the "Quick Reference" section to reflect current file structure
   - Add a "Common Patterns" section for new operation authors

3. **Update `pyproject.toml`**
   - Add `[tool.ruff]` section with line-length and select rules
   - Add `[tool.ruff.lint]` with appropriate ignore rules for Krita/PyQt patterns
   - Update `requires-python` to `>=3.9` if Krita 5.2+ is the target

4. **Add `.editorconfig`** (new file)
   - Standardize indent_style = space, indent_size = 4 for Python
   - Set charset = utf-8, end_of_line = lf

**Files modified:** `README.md`, `AGENTS.md`, `pyproject.toml`, `.editorconfig` (new)

**Risk:** None — documentation and config only.

---

## Phase Dependency Graph

```
Phase 1 (Bug Fixes & Cleanup)
    │
    ▼
Phase 2 (Cross-Plugin Coupling)
    │
    ▼
Phase 3 (DRY Constants & Validators)
    │
    ▼
Phase 4 (Type Hints & Docstrings)
    │
    ▼
Phase 5 (Documentation & Config)
```

**Critical path:** 1 → 2 → 3 → 4 → 5 (strictly sequential)

**Estimated scope:** ~50 lines fixed, ~80 lines extracted/DRY'd, ~300 lines of type hints added, ~100 lines of documentation updated.

---

## Files Summary

### Files Modified

| File | Phases | Nature of Changes |
|------|--------|-------------------|
| `operations_pie_menu/operations/bw_preview.py` | 1 | Add missing import |
| `operations_pie_menu/operations/fit_layer.py` | 1 | Fix aspect ratio enum |
| `conditions_pie_menu/conditions_pie_menu.action` | 1 | Add configure action entry |
| `filters_pie_menu/__init__.py` | 1 | Normalize init pattern |
| `operations_pie_menu/__init__.py` | 1 | Normalize init pattern |
| `dummy_docker/__init__.py` | 1 | Normalize init pattern |
| `operations_pie_menu/operations_pie_menu.py` | 1, 2 | Stub cleanup, coupling fix |
| `krita_pie_menu/utils.py` | 3, 4 | Extract validator factory, add types |
| `krita_pie_menu/__init__.py` | 3, 4 | Export new utils, add docstring |
| `filters_pie_menu/config_dialog.py` | 3 | Import SECTOR_NAMES from base |
| `operations_pie_menu/config_dialog.py` | 3 | Import SECTOR_NAMES from base |
| `conditions_pie_menu/config_dialog.py` | 3 | Import SECTOR_NAMES from base |
| `filters_pie_menu/filters_pie_menu.py` | 3, 4 | Use validator factory, add types |
| `operations_pie_menu/operations/refine_sketch.py` | 3, 4 | Use validator factory, add types |
| `operations_pie_menu/operations/sanitize_group.py` | 3, 4 | Use validator factory, add types |
| `operations_pie_menu/operations/fit_layer.py` | 3, 4 | Use validator factory, add types |
| `operations_pie_menu/operations/bw_preview.py` | 4 | Add types |
| `operations_pie_menu/operations/init_canvas.py` | 4 | Add types |
| `krita_pie_menu/base_extension.py` | 4 | Add types and docstrings |
| `krita_pie_menu/base_config_dialog.py` | 4 | Add types and docstrings |
| `krita_pie_menu/pie_widget.py` | 4 | Add types, named constants |
| `krita_pie_menu/logger.py` | 4 | Add types |
| `krita_pie_menu/toast_notification.py` | 4 | Add types |
| `conditions_pie_menu/conditions_pie_menu.py` | 4 | Add types |
| `quick_script_engine/quick_script_engine.py` | 4 | Add types |
| `dummy_docker/dummy_docker.py` | 4 | Add types |
| `README.md` | 5 | Documentation update |
| `AGENTS.md` | 5 | Documentation update |
| `pyproject.toml` | 5 | Add ruff config |

### Files Created

| File | Phase | Purpose |
|------|-------|---------|
| `.editorconfig` | 5 | Editor configuration standardization |
