# Krita Python Scripting Guidelines

Guidelines and reference information for AI agents creating and modifying Krita Python scripts, extensions, and dockers.

---

## 1. Quick Reference & External Documentation

- **Action Dictionary**: [scripting.krita.org/action-dictionary](https://scripting.krita.org/action-dictionary)
- **Official Krita Python Manual**: [docs.krita.org/en/user_manual/python_scripting.html](https://docs.krita.org/en/user_manual/python_scripting.html)
- **Libkis C++/Python Source API Definitions**: [invent.kde.org/graphics/krita/-/tree/master/plugins/extensions/pykrita/libs/libkis](https://invent.kde.org/graphics/krita/-/tree/master/plugins/extensions/pykrita/libs/libkis)

---

## 2. Krita Action Management (`Krita.instance()`)

Actions represent menu items, tools, and UI triggers within Krita.

```python
from krita import Krita

app = Krita.instance()

# 1. Trigger an action by ID
action = app.action('file_save')
if action:
    action.trigger()

# 2. List all registered action IDs (for debugging/inspection)
for act in app.actions():
    print(act.objectName(), "-", act.text())
```

> **Note**: Actions are context-sensitive. If an action is disabled in the UI (e.g., requires active document/selection), `.trigger()` may be a no-op.

---

## 3. Krita Plugin Directory Structure

Krita plugins on Windows live in the `pykrita` directory:
- **PyKrita Directory**: `%APPDATA%\krita\pykrita\` (`C:\Users\<username>\AppData\Roaming\krita\pykrita\`)

> **Windows Dev Tip & New Plugin Deployment (No Admin Required)**: Krita does not have a setting to change the search path. Whenever creating a new plugin in this repository, run the following PowerShell command block to link and register it in Krita:
> ```powershell
> # 1. Create Directory Junction from pykrita to repo folder
> cmd /c mklink /J "$env:APPDATA\krita\pykrita\<plugin_name>" "c:\Users\Leonardo\001\00__DEV\Krita-Scripts\<plugin_name>"
> 
> # 2. Deploy desktop manifest and shortcut action XML
> Copy-Item "<plugin_name>.desktop" "$env:APPDATA\krita\pykrita\" -Force
> if (!(Test-Path "$env:APPDATA\krita\actions")) { New-Item -ItemType Directory -Path "$env:APPDATA\krita\actions" -Force }
> Copy-Item "<plugin_name>\<plugin_name>.action" "$env:APPDATA\krita\actions\" -Force
> ```

### File Layout

```
pykrita/
├── <plugin_name>.desktop
└── <plugin_name>/
    ├── __init__.py
    └── <plugin_logic>.py
```

### Desktop Entry (`<plugin_name>.desktop`)

```ini
[Desktop Entry]
Type=Service
ServiceTypes=Krita/PythonPlugin
X-KDE-Library=<plugin_name>
X-Python-2-Compatible=false
Name=My Plugin Name
Comment=Short description of the plugin.
```

---

## 4. Plugin Types

### A. Extension (`krita.Extension`)

Used for menu items, background utilities, and custom action commands.

```python
from krita import Extension, Krita

class MyExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction("my_custom_action_id", "My Custom Tool", "tools/scripts")
        action.triggered.connect(self.run)

    def run(self):
        doc = Krita.instance().activeDocument()
        # Plugin execution logic

# Registration in __init__.py
Krita.instance().addExtension(MyExtension(Krita.instance()))
```

### B. Docker Panel (`krita.DockWidget`)

Used for persistent side panels / dockable UI elements using PyQt (`PyQt5.QtWidgets` / `PyQt6.QtWidgets`).

```python
from krita import DockWidget, DockWidgetFactory, DockWidgetFactoryBase, Krita

DOCKER_ID = 'my_docker_id'

class MyDocker(DockWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My Docker")

    def canvasChanged(self, canvas):
        pass

# Registration in __init__.py
instance = Krita.instance()
factory = DockWidgetFactory(DOCKER_ID, DockWidgetFactoryBase.DockRight, MyDocker)
instance.addDockWidgetFactory(factory)
```

---

## 5. Shared Library Architecture (`krita_pie_menu`)

All radial Pie Menu extensions (`filters_pie_menu`, `operations_pie_menu`, `conditions_pie_menu`) leverage the shared `krita_pie_menu` widget package:

- **`BasePieMenuExtension` (`krita_pie_menu/base_extension.py`)**: Abstract base class managing configuration persistence, guarded menu display (`show_pie_menu`), and Qt widget destruction lifecycle.
- **`BasePieConfigDialog` (`krita_pie_menu/base_config_dialog.py`)**: Unified PyQt configuration dialog base class for sector key-bindings and options; exports `SECTOR_NAMES`.
- **`utils` (`krita_pie_menu/utils.py`)**: Helper utilities (`load_config`, `save_config`, `get_incremental_layer_name`, `create_incremental_layer`, `resolve_action`, `find_brush_preset`, `set_foreground_black`, `make_doc_active_validator`).
- **`logger` (`krita_pie_menu/logger.py`)**: Thread-safe rotating logger writing to `%APPDATA%/krita/pykrita/krita_scripts.log`.

### Modular Operations Pattern (`operations_pie_menu/operations/`)
Complex operations are decomposed into dedicated single-responsibility modules:
- `refine_sketch.py` (North)
- `sanitize_group.py` (North-East)
- `bw_preview.py` (South-East)
- `init_canvas.py` (South)
- `fit_layer.py` (West)

---

## 6. Development Principles for Agents

1. **Check Active Context**: Always verify `Krita.instance().activeDocument()`, `activeWindow()`, or `activeNode()` before operating on documents/layers.
2. **Batch & Refresh**: Call `document.refreshProjection()` or `document.waitForDone()` after bulk pixel/layer updates.
3. **Succinct & Modular**: Inherit from `BasePieMenuExtension` for new pie menus, and place operation logic in subpackages rather than monolithic files.
4. **Structured Logging**: Use `log_info`, `log_warning`, and `log_error` from `krita_pie_menu` rather than swallowing exceptions.
5. **Ruff Linting & Formatting**: Regularly run `ruff check --fix .` and `ruff format .` after modifying Python code to enforce import hygiene, type consistency, and code style.

---

## 7. Action Shortcuts Registration (`.action` XML Files)

To make custom extension actions searchable and assignable in Krita's **Settings > Configure Krita > Keyboard Shortcuts** menu, Krita requires a `.action` XML file placed in `%APPDATA%\krita\actions\`.

### `.action` File Template

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ActionCollection version="2" name="Scripts">
    <Actions category="Scripts">
        <text>My Extension Group</text>
        <Action name="my_custom_action_id">
            <icon></icon>
            <text>My Custom Tool</text>
            <whatsThis>Description of what this tool does</whatsThis>
            <toolTip>Run My Custom Tool</toolTip>
            <iconText>MyTool</iconText>
            <activationFlags>10000</activationFlags>
            <shortcut></shortcut>
            <isCheckable>false</isCheckable>
            <statusTip></statusTip>
        </Action>
    </Actions>
</ActionCollection>
```

> **Important**: The `<Action name="my_custom_action_id">` attribute **must exactly match** the action ID string used in `window.createAction("my_custom_action_id", ...)`.

---

## 8. Krita Layer Tree API — Hard-Won Lessons (Do Not Repeat)

These mistakes were made repeatedly in `sanitize_group.py` over multiple attempts. Read this before touching any layer-ordering code.

---

### 8.1 `childNodes()` Ordering

`group_layer.childNodes()` returns children in **bottom-to-top UI order**:

| Index | Position in panel |
|-------|-------------------|
| `[0]` | **Bottom-most** layer |
| `[-1]` | **Top-most** layer |

This is the **opposite of what you might intuit** from "index 0 = first". Do not guess, do not assume, do not "fix" it — this is the confirmed, tested order. Code comments that say otherwise are wrong and have caused real bugs.

---

### 8.2 `addChildNode(node, above)` — Detaching & Order Semantics

```python
group_layer.addChildNode(node, reference_node)
```

- If `node` is **already attached** to `group_layer`, calling `addChildNode` is a **no-op** in Krita Libkis! You MUST call `node.remove()` to detach it first before re-inserting it at a new stack position.
- **`reference_node` parameter**: Inserts `node` directly **ABOVE** `reference_node` in the layer panel.
- Passing `None` inserts `node` at the top of drawing layers.

**Correct pattern** to place `B&W` at the absolute top of the group stack and `fresh` directly below it:

```python
# 1. Add fresh empty layer to group
fresh = doc.createNode("_top_", "paintlayer")
group_layer.addChildNode(fresh, None)

# 2. Detach existing B&W layer and re-parent directly ABOVE fresh
if bw_node:
    bw_node.remove()                          # Detach existing node first!
    group_layer.addChildNode(bw_node, fresh)  # Attach B&W directly ABOVE fresh
```

---

### 8.3 Protected Layers — Use a Set, Check Before ANY Mutation

Protected layer names (currently `"WHITE"`, `"B&W"`, and `"LINES"`) must be stored in a module-level set and checked by normalising the name **before** any rename or remove call. Never inline the check as a one-off string comparison scattered through the function — it will be missed.

```python
_PROTECTED_NAMES = {"WHITE", "B&W", "LINES"}

def _is_protected(node) -> bool:
    return node.name().strip().upper() in _PROTECTED_NAMES
```

**The bug:** the name-check code existed and was nominally correct, but the surrounding logic was so confused about ordering that the renumber loop reached the WHITE layer first (it is at index 0 = bottom), named it `"1"`, and then the `is_white_layer` check was vacuous — the layer no longer had the name `"WHITE"`. The fix was not the check itself but ensuring the rest of the function was correct so the check was never bypassed by earlier side effects.

---

### 8.4 Snapshot the Child List Before Mutating the Tree

When removing nodes inside a loop, always snapshot first:

```python
for child in list(group_layer.childNodes()):   # ← list() snapshot
    if should_remove(child):
        child.remove()
```

Iterating the live result of `childNodes()` while removing nodes causes Krita to skip or double-visit nodes within the same loop.
