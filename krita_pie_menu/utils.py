import json
import os
import re
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Union

from krita import Krita, ManagedColor

from .logger import log_warning

PROTECTED_NAMES: Set[str] = {"WHITE", "B&W", "LINES"}

# Strong references to resolved QActions, keyed by id(). See keep_action_alive():
# because the dict holds the only guaranteed reference, the objects it keys on
# can never be collected and their ids can never be recycled.
_ACTION_KEEPALIVE: Dict[int, Any] = {}

# Result contract for pie-menu operation callbacks, consumed by
# PieMenuWidget._execute_sector:
#   True          -> succeeded
#   False         -> failed, generic warning toast
#   (False, str)  -> failed, warning toast carrying the reason
OperationResult = Union[bool, Tuple[bool, str]]

# Name of the operation currently holding the re-entrancy lock, or None.
_ACTIVE_OPERATION: Optional[str] = None


@contextmanager
def single_flight(name: str) -> Iterator[bool]:
    """
    Re-entrancy guard for pie-menu operations.

    Operations pump the Qt event loop (``QApplication.processEvents()``) and
    trigger actions. While that is happening the pie-menu trigger key -- or the
    Tools > Scripts menu item -- can fire again, which would nest a second copy
    of the same operation *inside* the first one. Both copies would then mutate
    the same layer stack: duplicated overlays, cross-contaminated renumbering,
    lost pixels.

    Yields True when the caller acquired the lock and False when another
    operation already holds it, in which case the caller must bail out without
    touching the document. The lock is always released, including on exceptions.
    """
    global _ACTIVE_OPERATION
    if _ACTIVE_OPERATION is not None:
        log_warning(name, f"Rejected: '{_ACTIVE_OPERATION}' is already running.")
        yield False
        return
    _ACTIVE_OPERATION = name
    try:
        yield True
    finally:
        _ACTIVE_OPERATION = None


def is_protected_layer(node: Any) -> bool:
    """
    Checks whether a Krita layer node is protected from purging or renaming.
    """
    if not node or not hasattr(node, "name"):
        return False
    return node.name().strip().upper() in PROTECTED_NAMES


def is_u8_rgba(doc: Any) -> bool:
    """
    Returns True only for 8-bit RGBA documents.

    Pixel-manipulation helpers that build raw byte buffers (e.g. QImage with a
    fixed 4-bytes-per-pixel stride) are only safe for this color model/depth
    combination. Call this guard before touching pixel data.
    """
    if not doc or not hasattr(doc, "colorModel"):
        return False
    return doc.colorModel() == "RGBA" and doc.colorDepth() == "U8"


def is_empty_paint_layer(node: Any) -> bool:
    """
    Returns True when `node` is a paint layer with no painted content
    (zero-width or zero-height bounds).
    """
    if not node or not hasattr(node, "type") or node.type() != "paintlayer":
        return False
    b = node.bounds()
    return b.width() <= 0 or b.height() <= 0


def _resolve_repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CONDITIONS_CONFIG_PATH: str = os.environ.get(
    "KRITA_CONDITIONS_CONFIG",
    os.path.join(_resolve_repo_root(), "conditions_pie_menu", "config.json"),
)


def get_condition_flag(key: str, default: bool = False) -> bool:
    """
    Safely queries a global condition flag from conditions_pie_menu/config.json.

    This is a deliberate cross-plugin coupling: operations read toggles that are
    written by the conditions pie menu. If conditions_pie_menu is renamed or
    uninstalled, or the file is missing, the value silently falls back to
    `default`. Override the resolved path with the KRITA_CONDITIONS_CONFIG
    environment variable (read once at import time), or reassign the
    CONDITIONS_CONFIG_PATH module constant at runtime.
    """
    cond_cfg = load_config(CONDITIONS_CONFIG_PATH, {})
    return bool(cond_cfg.get(key, default))


def read_condition_flag(key: str, default: bool = False) -> bool:
    """Backwards-compatible alias for :func:`get_condition_flag`."""
    return get_condition_flag(key, default)


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merges `overrides` into `base`, returning a new dict.
    Values in `overrides` always win; nested dicts are merged recursively.
    """
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(config_path: str, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Safely load a JSON configuration file, deep-merging any keys missing from
    `defaults` (values present in the file always win). Returns `defaults`
    (or an empty dict) when the file is absent or unreadable.
    """
    if defaults is None:
        defaults = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return _deep_merge(defaults, data)
        except Exception:
            pass
    return dict(defaults)


def save_config(config_path: str, cfg: Dict[str, Any]) -> bool:
    """
    Safely write a JSON configuration file. Returns True if successful.
    """
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception:
        return False


def get_incremental_layer_name(layer_name: str) -> str:
    """
    Parses an existing layer name for the last integer sequence and increments it by 1.
    If no number is found, defaults to '1'.
    """
    matches = re.findall(r"\d+", layer_name.strip())
    if matches:
        return str(int(matches[-1]) + 1)
    return "1"


# Sibling-rename rules (see numbered_sibling_name).
#
# Both patterns are strictly ASCII and neither uses re.IGNORECASE. IGNORECASE
# case-folds, so "[a-z]" with it also matches 'Ç', 'Ã', the Kelvin sign and the long
# s -- which would wrongly report an all-caps name like "AÇÃO" as having a lowercase
# letter and collapse it to a bare index.
_AZ_ANY = re.compile(r"[A-Za-z]")
_AZ_LOWER = re.compile(r"[a-z]")
_LEADING_INDEX = re.compile(r"^\d+_")


def keeps_layer_name(name: str) -> bool:
    """
    True when `name` has at least one a-z character (either case) and *none* of them
    is lowercase -- i.e. an all-capitalized name such as "INK", "CANAL A" or "REFLAY 2".

    A name with no a-z character at all ("1", "23") is False: there is nothing to
    preserve, so it collapses to the bare index instead of growing into "1_1".
    """
    return bool(_AZ_ANY.search(name)) and not _AZ_LOWER.search(name)


def numbered_sibling_name(current_name: str, index: int) -> str:
    """
    Target name for the sibling sitting at `index` (1-based, bottom-to-top).

    Preserved names become ``"<index>_<name>"``; every other name becomes the bare
    index. An existing ``"<digits>_"`` prefix from a previous run is stripped before
    re-prefixing, so repeated renumbering is idempotent ("1_INK" at index 2 -> "2_INK",
    never "2_1_INK").
    """
    if not keeps_layer_name(current_name):
        return str(index)
    return f"{index}_{_LEADING_INDEX.sub('', current_name.strip())}"


def renumber_layer_name(node: Any, index: int) -> bool:
    """
    Rename `node` to numbered_sibling_name(node.name(), index).

    Returns True when setName was called, False when the layer already sits at the
    right name -- that no-op is deliberate, so an already-correct stack is left
    completely untouched instead of being rewritten.
    """
    desired = numbered_sibling_name(node.name(), index)
    if node.name() == desired:
        return False
    node.setName(desired)
    return True


def create_incremental_layer(doc, reference_layer=None, view=None):
    """
    Creates a new paint layer directly above `reference_layer` (or activeNode if None).
    Sets the new layer as active on both the document and (when supplied) the view,
    because Krita actions such as merge-down act on the *view's* active node.
    Calls `refreshProjection()`. Returns the new node, or None if it could not be
    created or parented.
    """
    if doc is None:
        return None
    if reference_layer is None:
        reference_layer = doc.activeNode()
    if reference_layer is None:
        return None

    new_name = get_incremental_layer_name(reference_layer.name())
    new_layer = doc.createNode(new_name, "paintlayer")

    parent = reference_layer.parentNode()
    if parent is None:
        parent = doc.rootNode()
    if parent is None:
        return None

    if not parent.addChildNode(new_layer, reference_layer):
        log_warning("create_incremental_layer", f"Could not parent new layer '{new_name}'; aborting.")
        return None

    doc.setActiveNode(new_layer)
    if view is not None:
        try:
            view.setActiveNode(new_layer)
        except Exception:
            pass
    doc.refreshProjection()
    return new_layer


def resolve_action(app, candidate_ids: List[str]):
    """
    Finds and returns the first action matching any ID in candidate_ids.

    The comparison is ``is not None``, never truthiness: a truthiness test
    silently skips a real action that happens to define ``__bool__``/``__len__``
    (a sip wrapper for a destroyed C++ object is falsy) and reports the far more
    misleading "not found". Real PyQt5 QActions are always truthy, so this
    changes nothing in production -- it is a latent-bug fix.
    """
    if app is None:
        app = Krita.instance()
    for act_id in candidate_ids:
        action = app.action(act_id)
        if action is not None:
            return action
    return None


def probe_action_ids(app, candidate_ids: List[str]) -> List[Tuple[str, str]]:
    """
    Per-candidate diagnosis for a lookup that came up empty.

    A bare "not found; tried [...]" cannot distinguish the two ways a candidate
    can fail:

    * ``app.action()`` returned ``None`` -- the ID is genuinely absent from
      Krita's action registry.
    * ``app.action()`` returned a non-``None`` but *falsy* object -- an
      unexpected binding state, e.g. a sip wrapper whose C++ object was
      destroyed. This is the case worth knowing about, because the same ID can
      resolve fine one run and come back "not found" the next.
    * the lookup raised.

    Repeats the lookups, so only call this on the failure path.
    """
    if app is None:
        app = Krita.instance()
    report: List[Tuple[str, str]] = []
    for act_id in candidate_ids:
        try:
            action = app.action(act_id)
        except Exception as exc:  # noqa: BLE001 - diagnosis must not raise
            report.append((act_id, f"lookup raised {type(exc).__name__}: {exc}"))
            continue
        if action is None:
            report.append((act_id, "returned None (ID absent from the registry)"))
        elif not action:
            report.append((act_id, f"returned a falsy non-None object: {action!r}"))
        else:
            report.append((act_id, f"resolved -> {describe_action(action)}"))
    return report


def describe_action(action: Any) -> str:
    """Best-effort human identity for a resolved QAction; never raises."""
    bits: List[str] = []
    for attr in ("objectName", "text"):
        getter = getattr(action, attr, None)
        if getter is None:
            continue
        try:
            value = getter()
        except Exception:  # noqa: BLE001 - a destroyed C++ object raises here
            bits.append(f"{attr}=<unavailable>")
            continue
        if isinstance(value, str) and value:
            bits.append(f"{attr}={value!r}")
    return " ".join(bits) if bits else repr(action)


def keep_action_alive(action: Any) -> None:
    """
    Hold a strong reference to a resolved QAction for the process lifetime.

    PyQt5 deletes the underlying C++ object when the last Python wrapper for an
    **unparented** QObject is garbage collected (verified empirically: unparented
    -> deleted on GC, parented -> survives). Krita's registry actions are added
    via ``addAction()`` and are therefore parented, so this is *not* a
    demonstrated fix for the observed "not found" alternation -- it is
    defence-in-depth that bounds the "action present, then gone" failure class
    and removes a well-known PyQt5 crash source at zero cost.
    """
    if action is None:
        return
    _ACTION_KEEPALIVE[id(action)] = action


def find_brush_preset(app, preset_name: str = "0 STD DRW"):
    """
    Fuzzy search for a brush preset resource in Krita by name.
    """
    if app is None:
        app = Krita.instance()
    resources = app.resources("preset")
    if not resources:
        return None

    target = preset_name.lower()
    # 1. Exact match
    for name, res in resources.items():
        if name.lower() == target:
            return res

    # 2. Substring match
    for name, res in resources.items():
        if target in name.lower():
            return res

    # 3. Fallback match for "std drw" if target was "0 std drw"
    if "std drw" in target:
        for name, res in resources.items():
            if "std drw" in name.lower():
                return res

    return None


def set_foreground_black(doc, view):
    """
    Sets the active view's foreground color to solid black.
    """
    if doc is None or view is None:
        return
    try:
        col = ManagedColor(doc.colorModel(), doc.colorDepth(), doc.colorProfileName())
        col.setComponents([0.0, 0.0, 0.0, 1.0])
        view.setForeGroundColor(col)
    except Exception:
        pass


def make_doc_active_validator(extra_checks=None):
    """
    Returns a validator function ensuring an active document and active layer exist.
    Optional `extra_checks(doc, node)` callback can perform operation-specific validation.
    """

    def validator():
        app = Krita.instance()
        doc = app.activeDocument()
        if not doc:
            return False, "No active document."
        node = doc.activeNode()
        if not node:
            return False, "No active layer selected."
        if extra_checks:
            return extra_checks(doc, node)
        return True, ""

    return validator


def reset_drawing_tool(
    app: Any = None,
    doc: Any = None,
    view: Any = None,
    preset_name: str = "0 STD DRW",
    action_resolver: Any = resolve_action,
    brush_finder: Any = find_brush_preset,
    color_setter: Any = set_foreground_black,
    warning_logger: Any = log_warning,
) -> None:
    """
    Resets tools and brush state after layer drawing operations:
    1. Disables eraser mode if active.
    2. Sets active tool to Freehand Brush.
    3. Resets FG/BG color.
    4. Sets active view foreground color to solid black.
    5. Activates the given brush preset.
    """
    if app is None:
        app = Krita.instance()

    erase_act = app.action("erase_action")
    if erase_act and erase_act.isChecked():
        erase_act.trigger()

    brush_act = action_resolver(app, ["KritaShape/KritaShapeFreehand", "KritaShapeFreehand"])
    if brush_act:
        brush_act.trigger()

    reset_act = app.action("reset_fg_bg")
    if reset_act:
        reset_act.trigger()

    if doc is not None and view is not None:
        color_setter(doc, view)
        preset = brush_finder(app, preset_name)
        if preset:
            try:
                view.activateResource(preset)
            except Exception as e:
                warning_logger("reset_drawing_tool", f"Failed activating brush preset: {e}")
