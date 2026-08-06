# Krita-Scripts: Full Audit & Refactoring Implementation Plan (v2)

> Supersedes the executed v1 plan. This is a **new** audit of the current tree
> (post-v1) and a fresh 5-phase refactoring plan. Phases are strictly sequential;
> each phase ends at a green gate (ruff + compile + mypy) and is committed separately.

---

## 0. Execution Status — RATIFIED (2026-08-06)

All five phases below were fully **executed** on `master` and are reflected in the
current tree. The body of this document is retained verbatim as the historical
audit/implementation plan; baseline figures (lines, modules, findings) describe
the **pre-execution** state.

| Phase | Commit | Gate |
|-------|--------|------|
| 1 | `ca39012` | green |
| 2 | `760149e` | green |
| 3 | `38f13b2` | green |
| 4 | `0443cde` | green |
| 5 | `2437a65` | green |

Follow-up work (26 commits) extended the headless test suite to **311 tests /
100% coverage (1,629 stmts)** and is captured in AGENTS.md §10.2. Current gate
results (verified 2026-08-06): `ruff check .` = 0 findings · `compileall` = OK ·
`mypy` = 0 errors (29 files) · `pytest` = 311 passed.

See §9 for post-execution deviations from the plan's letter.

---

## 1. Executive Summary

The repository contains **5 plugins** (`filters`, `operations`, `conditions` pie menus,
`quick_script_engine`, `dummy_docker`) and **1 shared library** (`krita_pie_menu`),
totaling **~2,680 lines of Python** across 28 modules.

The v1 refactor is largely complete and healthy: the shared library is well-factored,
type annotations are mostly in place, `SECTOR_NAMES` is centralized, `ruff`/`mypy`
are configured, and the interrupt-safe pie widget satisfies the AGENTS.md §9 contract.

This audit therefore targets a **second-order** set of problems: data-integrity
guards missing on non-8-bit documents, a protected-layer invariant violation in
`refine_sketch`, a toast-lifecycle crash window, config drift between defaults /
examples / runtime files, cross-plugin coupling that is now *centralized but still
hidden*, a brittle operations dispatcher, dead constants, and a handful of type /
tooling hygiene gaps. The plan below fixes these in 5 sequential phases.

**Baseline static gate (current):**

| Check | Result |
|-------|--------|
| `ruff check .` | 1 error (`I001` import sort, `duplicate_layer.py:1`) |
| `python -m compileall -q …` | OK |
| `mypy …` | 3 errors + 1 config error (see C5/C6/C7/C8) |
| Automated tests | None exist |

---

## 2. Current Codebase Inventory

> Figures reflect the pre-execution baseline; see §0 for the executed state.

| Component | Modules | Lines | Status |
|-----------|---------|-------|--------|
| `krita_pie_menu/` (shared lib) | 7 `.py` | 1,016 | Stable; dead constants + coupling debt |
| `filters_pie_menu/` | 3 `.py` | 199 | Production; action-ID convention drift |
| `operations_pie_menu/` | 3 `.py` + 7 ops | 1,182 | Production; brittle dispatcher, E-sector stub |
| `conditions_pie_menu/` | 3 `.py` | 177 | Production (2 toggles + 6 toast stubs) |
| `quick_script_engine/` | 2 `.py` | 52 | Minimal, fine |
| `dummy_docker/` | 2 `.py` | 54 | Template, fine |
| **Total** | **28** | **2,680** | |

---

## 3. Audit Findings

Severity: **H** = must fix, **M** = should fix, **L** = polish.

> **Status:** All findings H1–H7, A1–A6, D1–D4, C1–C6 below were resolved by the
> executed phases (see §0). Tables are retained as the audit record.

### 3.1 Data integrity & correctness

| # | Sev | Finding | Location |
|---|-----|---------|----------|
| H1 | **H** | `fit_layer` assumes **4 bytes/pixel (U8 RGBA)** end-to-end (`QImage(..., w*4, Format_ARGB32)`), with **no `colorDepth()`/`colorModel()` guard**. On U16/F16/F32 or non-RGBA documents it silently writes corrupt/mis-strided pixel data. | `operations/…/fit_layer.py:92-108, 118-135` |
| H2 | **H** | `merge_to_black` has the same unguarded 4Bpp assumption (`QImage(proj_bytes, gw, gh, gw*4, …)`, `gw*gh*4` sizing). | `operations/…/merge_to_black.py:128-142` |
| H3 | **H** | `refine_sketch` renumbers **all** siblings `1..N` after creating the new layer, **including protected layers** (`WHITE`/`B&W`/`LINES`). This violates the AGENTS.md §8.3 invariant that `sanitize_group`/`merge_to_black` already honor — a `B&W` placed at group top by `merge_to_black` then gets renamed by the next `Refine Sketch`. | `operations/…/refine_sketch.py:239-242` |
| H4 | **M** | `ToastNotification.show_toast` closes the previous toast (`WA_DeleteOnClose`) but **does not cancel its pending fade timer**. If a second toast supersedes the first within `duration_ms`, the old toast's `fade_out` later runs against a deleted C++ widget → `RuntimeError` (uncaught, crashes the Krita event handler). | `krita_pie_menu/toast_notification.py:87-105, 153-165` |
| H5 | **M** | `fit_layer` (non-group branch) replaces the active layer but copies **only** `alphaLocked`; it drops opacity, blend mode, visibility and locked state. | `operations/…/fit_layer.py:134-143` |
| H6 | **M** | `init_canvas` silently **repurposes and white-fills the existing layer when the document has exactly 1 node** (no confirmation, unlike the >1-node "Nuke?" path). Destroys the user's only layer without asking. | `operations/…/init_canvas.py:43-64` |
| H7 | **L** | `bw_preview` matches `child.name() == "B&W"` case-sensitively while protected checks normalize `.upper()`; a `b&w` layer is protected from purge but not found here → duplicate `B&W` created. | `operations/…/bw_preview.py:26-33` |

### 3.2 Architecture & coupling

| # | Sev | Finding | Location |
|---|-----|----------|----------|
| A1 | **M** | Cross-plugin coupling is now **centralized in the shared lib but still hidden**: `read_condition_flag()` hardcodes `conditions_pie_menu/config.json` relative to the package root. It cannot be overridden and silently falls back to defaults if `conditions` is renamed/uninstalled. | `krita_pie_menu/utils.py:20-28` |
| A2 | **M** | `load_config()` performs **no defaults deep-merge**. A config file missing newly-added keys (e.g. a new sector or condition flag) silently drops those entries; `operations`/`filters` iterate `config.keys()`, so the sector button disappears entirely. | `krita_pie_menu/utils.py:32-46` |
| A3 | **M** | Operations callback dispatch is a brittle `if/elif` chain mixing `code` and `action_id` string matches. Users **cannot remap** a sector to another operation via config, and every show re-evaluates the chain. | `operations_pie_menu/operations_pie_menu.py:82-97` |
| A4 | **M** | `operations` **E sector has no validator** (validators dict covers only 7 sectors) while its runtime config action `op_stub_east` has no dispatcher branch → it becomes an *enabled* stub that pops a **modal** `QMessageBox`, inconsistent with `conditions` toast-stubs. | `operations_pie_menu/operations_pie_menu.py:67-73, 96-97, 104-111` |
| A5 | **M** | Config drift between defaults / examples / runtime (runtime `config.json` is gitignored, so v1 stub cleanups never reached it): `DEFAULT_OPERATIONS_CONFIG` E = `op_placeholder_east` but `config.example.json` still ships `op_stub_east` / `op_stub_west`. `filters` defaults use **unprefixed** IDs (`hsv_adjustment`) while example/config ship prefixed `krita_filter_*`; `trigger_action` papers over both. | `operations_pie_menu.py:26-35`, `operations_pie_menu/config.example.json:11,28`, `filters_pie_menu.py:20-29`, `filters_pie_menu/config.example.json` |
| A6 | **L** | `filters_pie_menu.trigger_action()` returns `False` on unresolved action, but the caller ignores it → user sees a "Triggered: …" toast followed by **nothing** (the success toast is emitted by the pie widget *before* the callback runs). Fallback also scans `app.actions()` with loose text matching. | `filters_pie_menu/filters_pie_menu.py:67-68, 110-121` |

### 3.3 Duplication & dead code

| # | Sev | Finding | Location |
|---|-----|----------|----------|
| D1 | **L** | Identical "is empty paint layer" logic duplicated in `refine_sketch` and `sanitize_group`. | `refine_sketch.py:21-25`, `sanitize_group.py:9-13` |
| D2 | **L** | Pie-widget named constants (`WIDGET_SIZE`, `CENTER_OFFSET`, `BUTTON_WIDTH/HEIGHT`, `DEADZONE_RADIUS`) are **defined but unused** — 520/260/150/36/45 are hardcoded inline. Sector codes are duplicated (`["N","NE",…]`) across `evaluate_sector_states`, `positions`, and `base_config_dialog.SECTOR_NAMES`. Scope note: the per-sector position offsets (95/75/59/114/225/245) and the `-10000` offscreen move are *not* among the named constants — constantization applies only to the direct matches (520, 260, 150, 36, deadzone 45). | `pie_widget.py:10-14, 53, 71, 124-125, 206, 255` |
| D3 | **L** | Sector trigger logic (toast + cleanup + callback) duplicated between `make_click_handler` and `trigger_selected_action`; the two can drift. | `pie_widget.py:165-177 vs 345-363` |
| D4 | **L** | `conditions_pie_menu` imports `QMessageBox` solely for an **unreachable** `except ImportError` branch (`config_dialog` always exists). | `conditions_pie_menu/conditions_pie_menu.py:3, 104-111` |

### 3.4 Type safety, tooling, docs

| # | Sev | Finding | Location |
|---|-----|----------|----------|
| C1 | **M** | `pyproject.toml` declares `mypy.python_version = "3.8"` and `ruff.target-version = "py38"`; installed mypy ≥1.17 rejects it ("3.8 is not supported"). Python 3.10/3.13 caches are present; current Krita installs embed ≥3.10 (5.0 shipped 3.8, 5.1 → 3.9, 5.2+ → 3.10). | `pyproject.toml:13,21` |
| C2 | **M** | `ConditionsConfigDialog.collect_config` dereferences `self.chk_dup_reflay` / `self.chk_keep_ar` which are typed `Optional[QCheckBox]` (initialized `None`) → mypy `union-attr` errors; runtime crashes if `build_sector_editors` was never called. | `conditions_pie_menu/config_dialog.py:12-14, 50-57` |
| C3 | **L** | `operations_pie_menu.py:85` lambda cannot be type-inferred (mypy `misc` error) due to the `or`-chained dispatch. | `operations_pie_menu/operations_pie_menu.py:85` |
| C4 | **L** | `logger.py` is documented as "thread-safe" (AGENTS.md §5) but has **no lock** around rotate+write. | `krita_pie_menu/logger.py` |
| C5 | **L** | Docs drift: AGENTS.md §5 omits `duplicate_layer.py`; README links a **non-existent `LICENSE`** file; README uses emoji headers (v1 intended removal). | `AGENTS.md`, `README.md:117` |
| C6 | **L** | No tests and no CI gate. `krita` is not importable outside Krita, so any harness must stub it. | repo root |

---

## 4. Verification Protocol (every phase)

Each phase must end with all gates green **before** the next phase starts:

```powershell
# 1. Lint (target: 0 findings)
ruff check .

# 2. Syntax/byte-compile all packages
python -m compileall -q krita_pie_menu filters_pie_menu operations_pie_menu conditions_pie_menu quick_script_engine dummy_docker

# 3. Static types — use CLI override until Phase 4 fixes pyproject
mypy --python-version 3.10 krita_pie_menu operations_pie_menu filters_pie_menu conditions_pie_menu quick_script_engine dummy_docker

# 4. Krita runtime smoke — manual, per Phase 1 checklist (Krita cannot run headless)
```

**Manual Krita regression checklist** (run once per phase, on an 8-bit RGBA canvas):
1. `Space` filters pie opens/gestures/interrupts (F11, Esc, right-click) without hanging keyboard.
2. `Ctrl+Space` operations pie: Refine Sketch, Sanitize Group, Init Canvas, Merge to Black, Fit Layer, Duplicate, B&W Preview — each on a paint layer *and* inside a group.
3. `Ctrl+Tab` conditions pie: both toggles persist across restart and affect Refine Sketch / Fit Layer.
4. Trigger two toasts quickly (< 2.5 s apart) — no crash/console error.
5. Re-open each Config dialog, Save, confirm `config.json` intact and pie reflects changes.

Each phase = **one commit**. Do not mix phases in a commit.

---

## 5. Phases

### Phase 1 — Pixel-Integrity & Protected-Layer Fixes

> **Status: EXECUTED** — commit `ca39012`, gate green.

**Goal:** Eliminate data-corruption paths and bring `refine_sketch` in line with the AGENTS.md §8.3 protected-layer invariant.

1. **Add a pixel-format guard helper to `krita_pie_menu/utils.py`:**
   ```python
   def is_u8_rgba(doc) -> bool:
       return bool(doc and doc.colorModel() == "RGBA" and doc.colorDepth() == "U8")
   ```
   Export it from `krita_pie_menu/__init__.py`.

2. **Guard `fit_layer.py` (H1):** at the top of `execute_fit_layer`, if `not is_u8_rgba(doc)`, `log_warning` + `ToastNotification` ("Fit Layer requires an 8-bit RGBA document") and return before any mutation. Same for the QImage construction paths.

3. **Guard `merge_to_black.py` (H2):** identical early-return guard before the `projectionPixelData`/QImage block.

4. **Fix `refine_sketch.py` renumber loop (H3):** skip protected names, mirroring `sanitize_group`:
   ```python
   for idx, child in enumerate(parent.childNodes(), start=1):
       if is_protected_layer(child):
           continue
       child.setName(str(idx))
   ```
   Re-assert active node afterwards.

5. **Fix `bw_preview.py` (H7):** normalize to `child.name().strip().upper() == "B&W"`.

6. **Fix toast lifecycle (H4):** **convert to an instance timer** — `QTimer.singleShot(...)` returns `None` and cannot be stopped, so it must become a member: `self._fade_timer = QTimer(self)`, `self._fade_timer.setSingleShot(True)`, `self._fade_timer.timeout.connect(self.fade_out)`. In `show_toast`, stop the previous toast's timer (`self._fade_timer.stop()`) before `close()`; wrap `fade_out` body in `try/except RuntimeError`.

7. **Preserve layer attributes in `fit_layer` non-group branch (H5):** after creating `scaled_layer`, also copy `opacity()`, `blendingMode()`, `visible()`, `locked()`, `setInheritAlpha` alongside the existing `alphaLocked()`.

8. **`init_canvas` (H6):** when exactly one node exists and it is not already a protected `WHITE`, prompt the same "Nuke/Replace?" confirmation before white-filling/renaming.

**Files:** `utils.py`, `krita_pie_menu/__init__.py`, `fit_layer.py`, `merge_to_black.py`, `refine_sketch.py`, `bw_preview.py`, `toast_notification.py`, `init_canvas.py`

**Verification:** all Phase-1 gates green; manual smoke items 1, 2, 4, 5.

**Risk:** Low-Medium — behavioral changes are narrow (guards + renumber skip + attr copy); primary U8 path unaffected except H5/H6.

---

### Phase 2 — Configuration & Cross-Plugin Decoupling

> **Status: EXECUTED** — commit `760149e`, gate green.

**Goal:** Make the conditions coupling explicit/overridable, add defaults deep-merge, and eliminate config convention drift.

1. **Decouple conditions path (A1):** in `utils.py`, add
   `CONDITIONS_CONFIG_PATH = os.environ.get("KRITA_CONDITIONS_CONFIG", os.path.join(<resolved repo root>, "conditions_pie_menu", "config.json"))`,
   add `get_condition_flag(key, default=False)` and keep `read_condition_flag` as a thin alias. Add a docstring documenting the coupling and when it silently falls back.

2. **Defaults deep-merge (A2):** add `_deep_merge(base, overrides)` in `utils.py`; extend `load_config(path, defaults)` to recursively fill missing keys from `defaults` (non-destructive to user values). Update `BasePieMenuExtension.load_config`, `BasePieConfigDialog.load_current_config`, and `conditions` to benefit automatically. Add unit-testable pure function.

3. **Filters ID convention (A5):** rewrite `DEFAULT_FILTERS_CONFIG` to prefixed `krita_filter_*` IDs matching `config.example.json` and `FILTER_OPTIONS` — import `FILTER_OPTIONS` from `filters_pie_menu/config_dialog.py` (no cycle: `trigger_action` already imports `SectorConfigDialog` from that module). Simplify `trigger_action` candidates: keep the `krita_filter_` fallback but drop the unbounded `app.actions()` scan, validating against the guarded `FILTER_OPTIONS` list as the source of truth.

4. **Silent-failure UX (A6):** make the filters callback **return** `trigger_action(...)`'s boolean. The "Triggered: …" success toast is emitted by the pie widget *before* the callback runs, so it cannot be suppressed in Phase 2 — Phase 3's `_execute_sector` makes the success toast conditional on the callback's return and shows "Filter action not found: …" on `False`. Until Phase 3 lands, a failure still shows the warning toast after the (incorrect) "Triggered:" one.

5. **Operations E-sector + stub UX (A4):** assign a disabled-stub validator to `E` (consistent with `conditions`), and convert `execute_stub_action` from modal `QMessageBox` to `ToastNotification`.

6. **Refresh example configs (A5):** `operations_pie_menu/config.example.json` → replace `op_stub_east` with `op_placeholder_east` and keep `op_fit_layer` for W; add a note that runtime `config.json` is untracked and regenerated on first save. **Registry-migration edge:** the current dispatcher maps legacy `op_stub_west` → Fit Layer and `op_stub_north` → Refine Sketch, but Phase 3's registry turns those IDs into plain stubs — a stale runtime `config.json` would silently lose Fit/Refine. Fold a "re-save the runtime config to regenerate it" reminder into the existing runtime-regeneration note.

**Files:** `utils.py`, `base_extension.py` (consumers of load), `filters_pie_menu.py`, `operations_pie_menu.py`, `operations_pie_menu/config.example.json`, `filters_pie_menu/config.example.json`, `krita_pie_menu/__init__.py`

**Verification:** all gates green; manual smoke items 1, 3, 5.

**Risk:** Low — no doc-structure changes, only config plumbing and UX.

---

### Phase 3 — DRY & Dispatch Simplification

> **Status: EXECUTED** — commit `38f13b2`, gate green.

**Goal:** Kill the duplicate/dead code from §3.3 and replace the brittle operations dispatcher with a registry.

1. **Pie-widget constants & sector codes (D2):**
   - Define `SECTOR_CODES = ("N","NE","E","SE","S","SW","W","NW")` in `krita_pie_menu/__init__.py` (and have `base_config_dialog.SECTOR_NAMES` derive from it).
   - Replace the **direct matches** of the named constants: widget size (520), center offset (260), button width/height (150/36), deadzone (45) — in `setFixedSize`, `paintEvent`, the deadzone check, and positions math.
   - **Not constantized:** the per-sector button position offsets (95/75/59/114/225/245) are not derivable from `BUTTON_WIDTH/HEIGHT` — keep them literal or introduce an explicit `BUTTON_OFFSETS` position table (likewise for the `-10000` offscreen move).
   - Drive `evaluate_sector_states` and `init_ui` from `SECTOR_CODES`.

2. **Deduplicate trigger logic (D3):** extract `_execute_sector(key)` containing the enable-check → cleanup → callback; have both `make_click_handler` and `trigger_selected_action` call it. `_execute_sector` emits the "Triggered: …" toast only when the callback does **not** return `False`; on `False` it shows the warning toast instead — this completes the A6 fix begun in Phase 2 item 4.

3. **Operations registry (A3):** replace the `if/elif` chain with
   ```python
   OP_HANDLERS = {
       "op_setup_canvas": execute_init_canvas,
       "op_refine_sketch": lambda dup=…: execute_refine_sketch(duplicate_reflay=dup),
       "op_sanitize_group": execute_sanitize_group,
       "op_merge_to_black": execute_merge_to_black,
       "op_fit_layer": execute_fit_layer,
       "op_bw_preview": execute_bw_preview,
       "op_duplicate_layer": execute_duplicate_layer,
   }
   ```
   `build_pie_config` looks up `act_id`; unknown IDs → stub. This enables config-based remapping and removes the `code ==` special cases.

4. **Consolidate empty-layer check (D1):** move to `utils.is_empty_paint_layer(node)`; use in `refine_sketch` and `sanitize_group`.

5. **Dead code (D4):** drop the `QMessageBox` import and unreachable `except ImportError` branch in `conditions_pie_menu.py`.

**Files:** `pie_widget.py`, `krita_pie_menu/__init__.py`, `base_config_dialog.py`, `operations_pie_menu.py`, `utils.py`, `refine_sketch.py`, `sanitize_group.py`, `conditions_pie_menu.py`

**Verification:** all gates green; manual smoke items 1-3 (verify sector geometry unchanged: widget still 520×520, buttons at same offsets, deadzone 45).

**Risk:** Medium — the highest-risk phase; geometry and dispatch must be visually verified, but it is pure code motion (no Krita-API behavior change).

---

### Phase 4 — Type Safety, Logging, Docs Sync

> **Status: EXECUTED** — commit `0443cde`, gate green.

**Goal:** Close the type gaps, make the logger honor its contract, and sync AGENTS.md/README with reality.

1. **Tooling config (C1):** set `mypy.python_version = "3.10"` and `ruff.target-version = "py310"` — correct for current Krita installs (5.0 embeds 3.8, 5.1 → 3.9, 5.2+ → 3.10); consider bumping `requires-python = ">=3.9"`.

2. **Fix mypy errors (C2, C3):**
   - `conditions_pie_menu/config_dialog.py`: add `assert self.chk_dup_reflay is not None` / `assert self.chk_keep_ar is not None` in `collect_config`. (Only the assert path is sound — assigning `QCheckBox` children before `super().__init__()` runs raises `RuntimeError` in PyQt, so that alternative is dropped.)
   - `operations_pie_menu.py`: replace the inferred lambda with a named helper `_make_refine_callback(dup_reflay: bool) -> Callable[[], None]`.

3. **Thread-safe logger (C4):** add a module-level `threading.Lock`; hold it across `_rotate_if_needed()` + write. Update the module docstring.

4. **Type the remaining internals:** `config_dialog` classes, `make_stub_callback`/`execute_stub_action`, `pie_widget` helper methods, `dummy_docker` — until `mypy` is clean with the new config.

5. **AGENTS.md (C5):** add `duplicate_layer.py` to §5; document the operations registry pattern, the U8/RGBA pixel-format guard, the protected-layer skip in `refine_sketch`, `read_condition_flag`/`get_condition_flag` coupling + override, and the logger lock.

6. **README (C5):** add a real `LICENSE` file (MIT, per README link) or drop the link; remove emoji headers if terminal rendering matters; add a "Regenerating runtime config" note.

**Files:** `pyproject.toml`, `conditions_pie_menu/config_dialog.py`, `operations_pie_menu.py`, `krita_pie_menu/logger.py`, `krita_pie_menu/pie_widget.py`, `dummy_docker/dummy_docker.py`, `AGENTS.md`, `README.md`, `LICENSE` (new, optional)

**Verification:** all gates green — notably `mypy` with the corrected config must return **0 errors**; smoke item 4.

**Risk:** Low — metadata/annotations only; the only behavioral delta is the logger lock.

---

### Phase 5 — Test Harness & CI Hygiene

> **Status: EXECUTED** — commit `2437a65`, gate green.

**Goal:** Add a repeatable, non-Krita test harness and wire it into CI so future refactors are verifiable.

1. **Fix the ruff baseline (C0):** `ruff check --fix` for `I001` in `operations_pie_menu/operations/duplicate_layer.py:1`.

2. **Add `tests/` with a `krita` stub (`conftest.py`):**
   - Inject a fake `krita` module into `sys.modules` before importing packages, providing `Krita.instance()`, `ManagedColor`, `Extension`, `DockWidget`, `DockWidgetFactory`, `DockWidgetFactoryBase` (lazily enough for import-only tests).
   - Pure-Python unit tests (no real Krita objects required):
     - `load_config` / deep-merge behavior (Phase 2 helper).
     - `get_incremental_layer_name`, `is_protected_layer`, `is_u8_rgba`, `is_empty_paint_layer`.
     - `get_condition_flag` with `KRITA_CONDITIONS_CONFIG` override.
     - Pie-widget sector-angle math (`update_selection_from_mouse` boundaries) via a minimal QWidget-free extraction or `importorskip("PyQt5")`.
   - If `PyQt5` is unavailable outside Krita, guard GUI tests with `pytest.importorskip`.

3. **Add `pyproject` dev extras + optional CI:**
   - `[project.optional-dependencies] dev = ["ruff", "mypy", "pytest"]`.
   - `.github/workflows/ci.yml`: on push/PR run `ruff check .`, `mypy …`, `pytest` on Python 3.10 and 3.13.

4. **Document the harness** in AGENTS.md ("Verification" section) so the Phase-gate protocol in §4 becomes scriptable: `ruff check . && python -m compileall -q … && mypy … && pytest`.

**Files:** `duplicate_layer.py`, `tests/` (new), `tests/conftest.py` (new), `pyproject.toml`, `.github/workflows/ci.yml` (new), `AGENTS.md`

**Verification:** `ruff check .` = 0; `mypy` = 0; `pytest` green; full manual smoke.

**Risk:** None to runtime behavior — additive infrastructure only.

---

## 6. Phase Dependency Graph

```
Phase 1  Pixel-Integrity & Protected-Layer Fixes
    │
    ▼
Phase 2  Configuration & Cross-Plugin Decoupling
    │
    ▼
Phase 3  DRY & Dispatch Simplification   ← highest-code-risk phase
    │
    ▼
Phase 4  Type Safety, Logging, Docs Sync
    │
    ▼
Phase 5  Test Harness & CI Hygiene
```

- **Critical path:** 1 → 2 → 3 → 4 → 5 (strictly sequential; each phase is one commit).
- **Rationale:** correctness (1) before coupling/config (2) before code motion (3); type/annotation work (4) benefits from the simpler Phase-3 shapes; tests (5) are written against the final, simplified code so they encode the target invariants.

---

## 7. Files Summary

> All "Modified" / "Created" rows below were applied across the executed phases; see §0.

### Modified

| File | Phases | Nature |
|------|--------|--------|
| `krita_pie_menu/utils.py` | 1, 2, 3 | guards, deep-merge, condition coupling, empty-layer helper |
| `krita_pie_menu/__init__.py` | 1, 2, 3 | new exports, `SECTOR_CODES` |
| `krita_pie_menu/pie_widget.py` | 3, 4 | constants, dedup trigger, typing |
| `krita_pie_menu/base_config_dialog.py` | 3 | `SECTOR_NAMES` derived from `SECTOR_CODES` |
| `krita_pie_menu/toast_notification.py` | 1 | timer cancellation, RuntimeError guard |
| `krita_pie_menu/logger.py` | 4 | thread lock |
| `operations_pie_menu/operations_pie_menu.py` | 2, 3, 4 | registry, E validator, typing |
| `operations_pie_menu/operations/fit_layer.py` | 1 | U8 guard, attr preservation |
| `operations_pie_menu/operations/merge_to_black.py` | 1 | U8 guard |
| `operations_pie_menu/operations/refine_sketch.py` | 1, 3 | protected skip, shared empty check |
| `operations_pie_menu/operations/sanitize_group.py` | 3 | shared empty check |
| `operations_pie_menu/operations/bw_preview.py` | 1 | name normalization |
| `operations_pie_menu/operations/init_canvas.py` | 1 | single-layer confirm |
| `operations_pie_menu/operations/duplicate_layer.py` | 5 | ruff I001 |
| `filters_pie_menu/filters_pie_menu.py` | 2 | prefixed defaults, failure toast, simpler search |
| `conditions_pie_menu/conditions_pie_menu.py` | 3, 4 | dead import removal, typing |
| `conditions_pie_menu/config_dialog.py` | 4 | Optional asserts |
| `dummy_docker/dummy_docker.py` | 4 | typing |
| `operations_pie_menu/config.example.json` | 2 | stub-ID cleanup |
| `filters_pie_menu/config.example.json` | 2 | ID normalization |
| `pyproject.toml` | 4, 5 | py3.10 targets, dev extras |
| `AGENTS.md` | 4, 5 | architecture + verification docs |
| `README.md` | 4 | LICENSE link / cleanup |

### Created

| File | Phase | Purpose |
|------|-------|---------|
| `tests/` + `tests/conftest.py` + unit tests | 5 | non-Krita test harness with `krita` stub |
| `.github/workflows/ci.yml` | 5 | ruff + mypy + pytest gate |
| `LICENSE` | 4 | satisfy README link (or remove link) |

---

## 8. Non-Goals (explicitly out of scope)

- Implementing **full U16/F16/F32 pixel support** in `fit_layer`/`merge_to_black` — Phase 1 *guards* against it; full support is a feature, not refactoring.
- Replacing the Qt widget stack or migrating PyQt5 → PyQt6.
- Changing the interrupt architecture (AGENTS.md §9) — verified correct; untouched.
- Renaming plugins or changing the `.action`/`.desktop` deployment contract.

---

## 9. Post-Execution Log & Deviations (added 2026-08-06)

### 9.1 Execution trail

- **Phase 1** (`ca39012`) — pixel-integrity guards, protected-layer renumber skip, toast timer lifecycle.
- **Phase 2** (`760149e`) — conditions path decoupling, deep-merge defaults, filter ID convention.
- **Phase 3** (`38f13b2`) — SECTOR_CODES constants, `_execute_sector` dedup, operations registry.
- **Phase 4** (`0443cde`) — type targets to py3.10, logger lock, mypy 0, docs sync.
- **Phase 5** (`2437a65`) — ruff I001 baseline, headless pytest harness, CI workflow.
- **Post-phase** (26 commits, `7dbd34f`…`3d1c956`) — coverage lifted to 100% (311 tests).

### 9.2 Deviations from the plan's letter

1. **U8-guard UX (Phase 1, items 2–3):** the plan specified `ToastNotification`;
   `fit_layer`/`merge_to_black` instead use `log_warning` + `QMessageBox.warning`,
   consistent with the other operation guards in the codebase. AGENTS.md §5 wording
   ("warning toast") has been corrected to match.
2. **Renumber loop (Phase 1, item 4):** the plan's `enumerate(..., start=1)` sketch
   increments over protected layers too; the implementation uses a skip-only
   `counter`, so non-protected siblings are numbered contiguously 1..N.
3. **Filters example vs defaults (Phase 2, item 3):** both use prefixed
   `krita_filter_*` IDs, but `config.example.json` assigns different filters to
   E/SE/SW/W than `DEFAULT_FILTERS_CONFIG`; runtime configs are untracked and
   regenerated on first save (see §0).
