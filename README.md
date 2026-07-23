# Krita Python Scripts & Extensions

A collection of Krita Python scripts, extensions, dockable UI panels, and Blender-style radial pie menu tools designed for digital artists.

---

## 🎨 Included Plugins & Tools

### 1. 🥧 Filters Pie Menu (`filters_pie_menu`)
A Blender-style 8-sector radial Pie Menu mapped to the **`Space`** key for instant access to Krita adjustment filters.

#### Features
- **Hold & Gesture Release:** Hold <kbd>Space</kbd>, flick/drag in an 8-sector direction, and release <kbd>Space</kbd> to trigger the filter immediately.
- **Circular Neutral Deadzone:** Releasing <kbd>Space</kbd> within the center circle closes the menu cleanly without executing anything.
- **Instant Interrupt:** Press <kbd>F11</kbd>, <kbd>Esc</kbd>, or **Right-Click** to cancel the pie call. Hides visually and blocks re-triggers until <kbd>Space</kbd> is released.
- **Interactive Sector Configurator:** Open **Tools → Scripts → Configure Filters Pie Menu** to reassign or move filters across sectors via GUI.

#### Supported Filter Actions
- HSV Adjustment...
- Color Curves... (*Per-Channel Curves*)
- Color Balance...
- Slope, Offset, Power...
- Desaturate...
- Auto Contrast
- Levels...
- Invert
- Gradient Map...
- Sharpen...
- Gaussian High Pass...
- Color to Alpha...
- Gaussian Blur...
- Threshold / Dodge / Burn...

---

### 2. 🥧 Operations Pie Menu (`operations_pie_menu`)
An 8-sector radial Pie Menu providing canvas and layer workflow operations:
- **Refine Sketch (North / `N`):**
  1. Enables Alpha Lock on the active layer.
  2. Fills sketch lines with a perceptually distributed random HSL color (`[0-255], 100%, 50%`) using golden-ratio hue stepping.
  3. *(Conditional)* If `Duplicate RefLay` flag is enabled, duplicates the layer and merges it down immediately.
  4. Creates a temporary layer above and fills it with neutral gray (`#808080`).
  5. Sets the temporary layer to `Luminosity` blend mode (`luminize`) and enables `Inherit Alpha`.
  6. Merges the layer down into the sketch layer.
  7. Creates a new paint layer directly above using `+1` incremental naming protocol.
  8. Activates the new layer, switches brush preset to `'0 STD DRW'`, and resets foreground color to black (`#000000`).
- **Init Canvas (South / `S`):** Sets up standard canvas layout.
- **B&W Preview (South East / `SE`):** Toggles or creates a top-level color override layer for value checking.
- **Fit Layer to Canvas (West / `W`):** Scales/fits active layer bounds to canvas size.

---

### 3. 🥧 Conditions Pie Menu (`conditions_pie_menu`)
An 8-sector radial Pie Menu mapped to **`Ctrl+Tab`** for toggling global workflow condition flags:
- **Duplicate RefLay (North East / `NE`):** Toggles layer duplication step in Refine Sketch OP. Displays visual toggle underscore/sidescore indicator and toast notification.
- **Stub Sectors (`N`, `E`, `SE`, `S`, `SW`, `W`, `NW`):** Prepared slots for future workflow flags.

---

### 4. ⚡ Quick Script Engine (`quick_script_engine`)
Workflow automation extension providing utility commands:
- **Create Incremental Layer:** Parses integer suffix on the active layer name and creates a new paint layer with incremented `+1` name.

---

### 4. 🔌 Hello World Extension (`hello_extension`)
Minimalist script extension template registered under **Tools → Scripts → Hello World Script**. Demonstrates action registration and active document state inspection.

### 5. 🖼️ Dummy Docker Panel (`dummy_docker`)
Dockable side panel UI template registered under **Settings → Dockers → Dummy Docker Panel**. Demonstrates PyQt widget layout, button signals, and canvas change tracking.

---

## 🛠️ Windows Installation (Directory Junctions)

Krita expects Python plugins to reside in `%APPDATA%\krita\pykrita\`. On Windows, you can create a **Directory Junction (`mklink /J`)** to link this development repository directly into Krita without requiring administrator privileges:

```powershell
# Create junction links for plugins
cmd /c mklink /J "$env:APPDATA\krita\pykrita\filters_pie_menu" "c:\Users\Leonardo\001\00__DEV\Krita-Scripts\filters_pie_menu"
cmd /c mklink /J "$env:APPDATA\krita\pykrita\operations_pie_menu" "c:\Users\Leonardo\001\00__DEV\Krita-Scripts\operations_pie_menu"
cmd /c mklink /J "$env:APPDATA\krita\pykrita\conditions_pie_menu" "c:\Users\Leonardo\001\00__DEV\Krita-Scripts\conditions_pie_menu"

# Deploy desktop manifests and action XML files
Copy-Item "conditions_pie_menu.desktop" "$env:APPDATA\krita\pykrita\" -Force
if (!(Test-Path "$env:APPDATA\krita\actions")) { New-Item -ItemType Directory -Path "$env:APPDATA\krita\actions" -Force }
Copy-Item "conditions_pie_menu\conditions_pie_menu.action" "$env:APPDATA\krita\actions\" -Force
```

> **Note:** Edits made in this workspace sync live to Krita instantly!

---

## 🚀 How to Enable in Krita

1. Open Krita.
2. Go to **Settings** → **Configure Krita...** → **Python Plugin Manager**.
3. Check the box next to **Filters Pie Menu** (or any desired plugin).
4. Click **OK** and **Restart Krita**.

---

## 📖 Developer Documentation

For detailed PyKrita API reference, action management, directory layouts, and agent development guidelines, see [AGENTS.md](AGENTS.md).

---

## 📜 License

[MIT License](LICENSE)
