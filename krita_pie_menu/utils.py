import json
import os
import re
from typing import Any, Dict, List, Optional, Set

from krita import Krita, ManagedColor

PROTECTED_NAMES: Set[str] = {"WHITE", "B&W", "LINES"}


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


def create_incremental_layer(doc, reference_layer=None):
    """
    Creates a new paint layer directly above `reference_layer` (or activeNode if None).
    Sets the new layer as active and calls `refreshProjection()`. Returns the new node.
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

    parent.addChildNode(new_layer, reference_layer)
    doc.setActiveNode(new_layer)
    doc.refreshProjection()
    return new_layer


def resolve_action(app, candidate_ids: List[str]):
    """
    Finds and returns the first valid Krita action matching any ID in candidate_ids.
    """
    if app is None:
        app = Krita.instance()
    for act_id in candidate_ids:
        action = app.action(act_id)
        if action:
            return action
    return None


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
