# Krita Python Scripts & Extensions

A collection of Krita Python scripts, extensions, dockable UI panels, and Blender-style radial pie menu tools designed for digital artists.

---

## Included Plugins & Tools

### 1. Filters Pie Menu (`filters_pie_menu`)
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

### 2. Operations Pie Menu (`operations_pie_menu`)
An 8-sector radial Pie Menu providing canvas and layer workflow operations:
- **Refine Sketch (North / `N`):**
  1. Enables Alpha Lock on the active layer.
  2. Fills sketch lines with a perceptually distributed random HSL color (`[0-255], 100%, 50%`) using golden-ratio hue stepping.
  3. *(Conditional)* If `Duplicate RefLay` flag is enabled, duplicates the layer and merges it down immediately.
  4. Creates a temporary layer above and fills it with neutral gray (`#808080`).
  5. Sets the temporary layer to `Luminosity` blend mode (`luminize`) and enables `Inherit Alpha`.
  6. Merges the layer down into the sketch layer.
  7. Creates a new paint layer directly above using `+1` incremental naming protocol.
- **Sanitize Group (North East / `NE`):** Purges non-protected empty layers, adds fresh top drawing layer, preserves `B&W` at absolute top (`[-1]`), and renumbers non-protected layers 1..N.
- **Init Canvas (South / `S`):** Sets up standard canvas layout (`WHITE` base layer at 75% opacity and `LINES` group with paint layer `1`).
- **Merge to Black (South West / `SW`):** Merges non-protected paint layers inside target group into a solid black silhouette layer, preserving target group hierarchy, `WHITE` at bottom (`[0]`), silhouette layer `"1"` in middle, and `B&W` at top (`[-1]`). Activates `'0 STD DRW'` brush preset and black foreground color.
- **B&W Preview (South East / `SE`):** Toggles or creates a top-level color override layer for value checking.
- **Fit Layer to Canvas (West / `W`):** Scales/fits active layer bounds to canvas size (respecting Keep Aspect Ratio condition).

---

### 3. Conditions Pie Menu (`conditions_pie_menu`)
An 8-sector radial Pie Menu mapped to **`Ctrl+Tab`** for toggling global workflow condition flags:
- **Duplicate RefLay (North East / `NE`):** Toggles layer duplication step in Refine Sketch OP.
- **Keep Aspect Ratio (West / `W`):** Toggles uniform aspect ratio preservation vs default scaling in Fit Layer to Canvas OP.
- **Stub Sectors (`N`, `E`, `SE`, `S`, `SW`, `NW`):** Prepared slots for future workflow flags with non-blocking ToastNotifications.

---

### 4. Quick Script Engine (`quick_script_engine`)
Workflow automation extension providing utility commands:
- **Create Incremental Layer:** Parses integer suffix on the active layer name and creates a new paint layer with incremented `+1` name.

---

### 5. Dummy Docker Panel (`dummy_docker`)
Dockable side panel UI template registered under **Settings → Dockers → Dummy Docker Panel**. Demonstrates PyQt widget layout, button signals, and canvas change tracking.

---

## Windows Installation (Directory Junctions)

Krita expects Python plugins to reside in `%APPDATA%\krita\pykrita\`. On Windows, you can create **Directory Junctions (`mklink /J`)** to link this development repository directly into Krita without requiring administrator privileges:

```powershell
$pykrita = "$env:APPDATA\krita\pykrita"
$actions = "$env:APPDATA\krita\actions"
$repo = "c:\Users\Leonardo\001\00__DEV\Krita-Scripts"

if (!(Test-Path $actions)) { New-Item -ItemType Directory -Path $actions -Force }

# 1. Shared library
cmd /c mklink /J "$pykrita\krita_pie_menu" "$repo\krita_pie_menu"

# 2. Plugins
$plugins = @("filters_pie_menu", "operations_pie_menu", "conditions_pie_menu", "quick_script_engine", "dummy_docker")
foreach ($p in $plugins) {
    cmd /c mklink /J "$pykrita\$p" "$repo\$p"
    if (Test-Path "$repo\$p.desktop") { Copy-Item "$repo\$p.desktop" "$pykrita\" -Force }
    if (Test-Path "$repo\$p\$p.action") { Copy-Item "$repo\$p\$p.action" "$actions\" -Force }
}
```

> **Note:** Edits made in this workspace sync live to Krita instantly!

> **Runtime configs (`config.json`) are untracked and generated locally.** The
> tracked `config.example.json` files are the templates; when sector action IDs
> change in a release, re-open each pie's **Configure** dialog and save once to
> regenerate your runtime `config.json` (otherwise stale IDs silently fall back
> to stub sectors).

---

## How to Enable in Krita

1. Open Krita.
2. Go to **Settings** → **Configure Krita...** → **Python Plugin Manager**.
3. Check the box next to **Filters Pie Menu** (or any desired plugin).
4. Click **OK** and **Restart Krita**.

---

## Developer Documentation

For detailed PyKrita API reference, action management, directory layouts, and agent development guidelines, see [AGENTS.md](AGENTS.md).

---

## License

[MIT License](LICENSE)
