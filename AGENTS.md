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

> **Windows Dev Tip (No Admin Required)**: Krita does not have a setting to change the search path, but you can create a Directory Junction from Krita's `pykrita` folder directly to your dev repo without administrator privileges:
> ```powershell
> cmd /c mklink /J "$env:APPDATA\krita\pykrita\<plugin_name>" "c:\Users\Leonardo\001\00__DEV\Krita-Scripts\<plugin_name>"
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

## 5. Development Principles for Agents

1. **Check Active Context**: Always verify `Krita.instance().activeDocument()`, `activeWindow()`, or `activeNode()` before operating on documents/layers.
2. **Batch & Refresh**: Call `document.refreshProjection()` or `document.waitForDone()` after bulk pixel/layer updates.
3. **Succinct & Modular**: Keep extensions and dockers clean, separated into single-responsibility modules when growing beyond small scripts.

---

## 6. Action Shortcuts Registration (`.action` XML Files)

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

