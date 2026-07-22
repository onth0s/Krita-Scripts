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

### 2. 🔌 Hello World Extension (`hello_extension`)
Minimalist script extension template registered under **Tools → Scripts → Hello World Script**. Demonstrates action registration and active document state inspection.

### 3. 🖼️ Dummy Docker Panel (`dummy_docker`)
Dockable side panel UI template registered under **Settings → Dockers → Dummy Docker Panel**. Demonstrates PyQt widget layout, button signals, and canvas change tracking.

---

## 🛠️ Windows Installation (Directory Junctions)

Krita expects Python plugins to reside in `%APPDATA%\krita\pykrita\`. On Windows, you can create a **Directory Junction (`mklink /J`)** to link this development repository directly into Krita without requiring administrator privileges:

```powershell
# 1. Create junction link for the plugin
cmd /c mklink /J "$env:APPDATA\krita\pykrita\filters_pie_menu" "c:\Users\Leonardo\001\00__DEV\Krita-Scripts\filters_pie_menu"

# 2. Deploy desktop manifest and shortcut action XML
Copy-Item "filters_pie_menu.desktop" "$env:APPDATA\krita\pykrita\" -Force
if (!(Test-Path "$env:APPDATA\krita\actions")) { New-Item -ItemType Directory -Path "$env:APPDATA\krita\actions" -Force }
Copy-Item "filters_pie_menu\filters_pie_menu.action" "$env:APPDATA\krita\actions\" -Force
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
