import os
import json
from krita import Extension, Krita
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import QMessageBox
from krita_pie_menu import PieMenuWidget
from .config_dialog import OperationsConfigDialog

class OperationsPieMenuExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        self.pie_widget = None
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.json')

    def setup(self):
        pass

    def createActions(self, window):
        action = window.createAction("trigger_operations_pie_menu", "Operations Pie Menu", "tools/scripts")
        action.triggered.connect(self.show_pie_menu)

        cfg_action = window.createAction("configure_operations_pie_menu", "Configure Operations Pie Menu", "tools/scripts")
        cfg_action.triggered.connect(self.open_config_dialog)

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "N":  { "label": "Refine Sketch",    "action_id": "op_refine_sketch" },
            "NE": { "label": "Stub North East",  "action_id": "op_stub_ne" },
            "E":  { "label": "Stub East",        "action_id": "op_stub_east" },
            "SE": { "label": "B&W Preview",        "action_id": "op_bw_preview" },
            "S":  { "label": "Init Canvas",      "action_id": "op_setup_canvas" },
            "SW": { "label": "Stub South West",  "action_id": "op_stub_sw" },
            "W":  { "label": "Fit Layer to Canvas", "action_id": "op_stub_west" },
            "NW": { "label": "Stub North West",  "action_id": "op_stub_nw" }
        }

    def show_pie_menu(self):
        try:
            if self.pie_widget is not None:
                if self.pie_widget.isVisible() or getattr(self.pie_widget, 'is_interrupted', False):
                    return
        except (RuntimeError, ReferenceError):
            self.pie_widget = None

        self.pie_widget = None

        config = self.load_config()
        callbacks = {}
        items_meta = {}
        validators = {}

        def check_paint_layer_required(action_name):
            def validate():
                app = Krita.instance()
                doc = app.activeDocument()
                if not doc:
                    return False, "No active document."
                node = doc.activeNode()
                if not node:
                    return False, "No active layer selected."
                if node.type() == "grouplayer":
                    return False, f"{action_name} requires a Paint Layer (Group selected)."
                return True, ""
            return validate

        def check_valid_layer_for_fit():
            app = Krita.instance()
            doc = app.activeDocument()
            if not doc:
                return False, "No active document."
            node = doc.activeNode()
            if not node:
                return False, "No active layer selected."
            return True, ""

        validators['N'] = check_paint_layer_required("Refine Sketch")
        validators['W'] = check_valid_layer_for_fit

        def disabled_stub():
            return False, "Stub operation not configured."

        for code in ['NE', 'E', 'SW', 'NW']:
            validators[code] = disabled_stub

        for code, data in config.items():
            act_id = data.get('action_id', '')
            label = data.get('label', '')
            items_meta[code] = (label, act_id)
            if code == 'S' or act_id == 'op_setup_canvas':
                callbacks[code] = self.setup_canvas_operation
            elif code == 'N' or act_id == 'op_refine_sketch' or act_id == 'op_stub_north':
                callbacks[code] = self.execute_north_operation
            elif code == 'W' or act_id == 'op_stub_west':
                callbacks[code] = self.execute_west_operation
            elif code == 'SE' or act_id == 'op_bw_preview':
                callbacks[code] = self.execute_se_operation
            else:
                callbacks[code] = self.make_stub_callback(code, label, act_id)


        self.pie_widget = PieMenuWidget(callbacks, items_meta=items_meta, validators=validators, accent_color="#805AD5", object_name="OperationsPieWidget")
        self.pie_widget.show_at_cursor()

    def make_stub_callback(self, code, label, action_id):
        return lambda: self.execute_stub_action(code, label, action_id)

    def execute_stub_action(self, code, label, action_id):
        app = Krita.instance()
        if action_id:
            act = app.action(action_id)
            if act:
                act.trigger()
                return
        QMessageBox.information(None, "Operations Pie Menu", f"Stub clicked: [{code}] {label}")

    def open_config_dialog(self):
        dlg = OperationsConfigDialog(self.config_path, on_save_callback=None)
        dlg.exec_()

    def execute_north_operation(self):
        """
        Refine Sketch ('N') operation:
        1. Enable alpha lock on active layer.
        2. Fill with random HSL [RANDOM (0-255), 100%, 50%].
        3. Create a new layer above.
        4. Fill it with #808080.
        5. Set it to Luminosity Blend Mode.
        6. Merge it with the one below.
        7. Create a new layer (with +1 protocol matching quick_script_engine).
        8. Set said layer to active, set '0 STD DRW' brush preset, set current color to black.
        """
        import random
        import colorsys
        import re

        app = Krita.instance()
        doc = app.activeDocument()
        if not doc:
            QMessageBox.warning(None, "Operations Pie Menu", "No active document open.")
            return

        active_layer = doc.activeNode()
        if not active_layer:
            QMessageBox.warning(None, "Operations Pie Menu", "No active layer selected.")
            return

        if active_layer.type() == "grouplayer":
            QMessageBox.warning(
                None,
                "Operations Pie Menu",
                "Alpha Lock & Fill operation cannot be run on a Group Layer.\nPlease select a Paint Layer."
            )
            return

        # 0. Check for active selection: if present, cut, paste onto new layer, rename (+1 protocol), and deselect
        sel = doc.selection()
        if sel and sel.width() > 0 and sel.height() > 0:
            from PyQt5.QtWidgets import QApplication
            curr_name = active_layer.name().strip()
            matches = re.findall(r'\d+', curr_name)
            if matches:
                next_num = int(matches[-1]) + 1
            else:
                next_num = 1
            new_layer_name = str(next_num)

            cut_act = app.action("edit_cut")
            if not cut_act:
                cut_act = app.action("cut")
            paste_act = app.action("edit_paste")
            if not paste_act:
                paste_act = app.action("paste")

            if cut_act and paste_act:
                cut_act.trigger()
                QApplication.processEvents()
                doc.waitForDone()

                paste_act.trigger()
                QApplication.processEvents()
                doc.waitForDone()

                pasted_layer = doc.activeNode()
                if pasted_layer and pasted_layer != active_layer:
                    pasted_layer.setName(new_layer_name)
                    active_layer = pasted_layer

                deselect_act = app.action("deselect")
                if deselect_act:
                    deselect_act.trigger()
                else:
                    doc.setSelection(None)
                QApplication.processEvents()
                doc.waitForDone()

        # 1. Enable alpha lock on active layer
        try:
            active_layer.setAlphaLocked(True)
        except Exception:
            pass

        window = app.activeWindow()
        view = window.activeView() if window else None

        # 2. Fill active layer with random HSL: [RANDOM (0-255), 100%, 50%]
        # Use golden-ratio hue stepping to ensure perceptually maximally-distinct
        # colors across successive calls, avoiding green/cyan clustering of uniform random.
        _GOLDEN_RATIO = 0.618033988749895
        hue_norm = (random.random() + _GOLDEN_RATIO) % 1.0
        r, g, b = colorsys.hls_to_rgb(hue_norm, 0.5, 1.0)
        r_byte = int(r * 255)
        g_byte = int(g * 255)
        b_byte = int(b * 255)

        w, h = doc.width(), doc.height()
        try:
            pix_data = bytearray(active_layer.pixelData(0, 0, w, h))
            p_len = len(pix_data) // (w * h) if (w * h) > 0 else 4
            if p_len == 4:
                # Krita pixelData is BGRA order for 8-bit channels
                for i in range(0, len(pix_data), 4):
                    if pix_data[i + 3] > 0:  # alpha channel is index 3
                        pix_data[i]     = b_byte  # B
                        pix_data[i + 1] = g_byte  # G
                        pix_data[i + 2] = r_byte  # R
                active_layer.setPixelData(QByteArray(pix_data), 0, 0, w, h)
        except Exception:
            pass

        # 2b. Conditional step: Duplicate layer and merge immediately if duplicate_reflay flag is enabled
        try:
            cond_cfg_path = os.path.join(os.path.dirname(__file__), '..', 'conditions_pie_menu', 'config.json')
            if os.path.exists(cond_cfg_path):
                with open(cond_cfg_path, 'r', encoding='utf-8') as f:
                    cond_cfg = json.load(f)
                    duplicate_reflay = cond_cfg.get("duplicate_reflay", False)
            else:
                duplicate_reflay = False
        except Exception:
            duplicate_reflay = False

        if duplicate_reflay:
            try:
                dup_node = active_layer.duplicate()
                parent_node = active_layer.parentNode() or doc.rootNode()
                parent_node.addChildNode(dup_node, active_layer)
                doc.setActiveNode(dup_node)
                doc.refreshProjection()
                from PyQt5.QtWidgets import QApplication
                QApplication.processEvents()
                doc.waitForDone()

                merge_act = app.action("layer_merge_down") or app.action("merge_layer_down") or app.action("merge_layer")
                if merge_act:
                    merge_act.trigger()
                    QApplication.processEvents()
                    doc.waitForDone()
                
                active_layer = doc.activeNode()
            except Exception:
                pass

        # 3. Create a new layer above
        parent = active_layer.parentNode()
        if not parent:
            parent = doc.rootNode()

        temp_lum_layer = doc.createNode("Refine_Lum_Temp", "paintlayer")
        parent.addChildNode(temp_lum_layer, active_layer)
        doc.setActiveNode(temp_lum_layer)

        # 4. Fill it with #808080 (R:128, G:128, B:128) directly via pixelData
        w, h = doc.width(), doc.height()
        try:
            sample = temp_lum_layer.pixelData(0, 0, 1, 1)
            p_len = len(sample) if sample else 4
            if p_len == 4:
                gray_pixel = b'\x80\x80\x80\xff'
            else:
                gray_pixel = b'\x80\x80\x80' + b'\xff' * (p_len - 3)
            gray_bytes = gray_pixel * (w * h)
            temp_lum_layer.setPixelData(QByteArray(gray_bytes), 0, 0, w, h)
        except Exception:
            pass

        # 5. Set it to Luminosity Blend Mode
        # Per KoCompositeOpRegistry.h: COMPOSITE_LUMINIZE = "luminize"
        temp_lum_layer.setBlendingMode("luminize")

        # Set inherit alpha to ON
        try:
            temp_lum_layer.setInheritAlpha(True)
        except Exception:
            pass

        # Ensure UI state and projection are updated
        from PyQt5.QtWidgets import QApplication
        doc.setActiveNode(temp_lum_layer)
        if view:
            try:
                view.setActiveNode(temp_lum_layer)
            except Exception:
                pass
        doc.refreshProjection()
        QApplication.processEvents()
        doc.waitForDone()

        # 6. Merge it with the one below
        merge_act = app.action("layer_merge_down")
        if not merge_act:
            merge_act = app.action("merge_layer_down")
        if not merge_act:
            merge_act = app.action("merge_layer")

        if merge_act:
            merge_act.trigger()
            QApplication.processEvents()
            doc.waitForDone()

        # 7. Create a new layer (with the +1 protocol, same as create_incremental_layer logic)
        curr_layer = doc.activeNode()
        if not curr_layer:
            curr_layer = active_layer

        curr_name = curr_layer.name().strip()
        matches = re.findall(r'\d+', curr_name)
        if matches:
            next_num = int(matches[-1]) + 1
        else:
            next_num = 1

        new_layer_name = str(next_num)

        new_layer = doc.createNode(new_layer_name, "paintlayer")
        new_parent = curr_layer.parentNode()
        if not new_parent:
            new_parent = doc.rootNode()
        new_parent.addChildNode(new_layer, curr_layer)

        # 8. Set said layer to active, set '0 STD DRW' to active brush, set current color to black
        doc.setActiveNode(new_layer)
        doc.refreshProjection()

        reset_act = app.action("reset_fg_bg")
        if reset_act:
            reset_act.trigger()

        if view:
            try:
                from krita import ManagedColor
                black = ManagedColor(doc.colorModel(), doc.colorDepth(), doc.colorProfile())
                black.setComponents([0.0, 0.0, 0.0, 1.0])
                view.setForeGroundColor(black)
            except Exception:
                pass

            try:
                resources = app.resources("preset")
                preset_to_activate = None
                for name, res in resources.items():
                    if "0 std drw" in name.lower() or name.lower() == "0 std drw":
                        preset_to_activate = res
                        break
                if not preset_to_activate:
                    for name, res in resources.items():
                        if "std drw" in name.lower():
                            preset_to_activate = res
                            break
                if preset_to_activate:
                    view.activateResource(preset_to_activate)
            except Exception:
                pass

    def execute_west_operation(self):
        """
        West ('W') action:
        Fit/Scale active layer (Paint Layer or Group Layer) content to canvas dimensions
        while preserving aspect ratio.
        Fully undoable (Ctrl+Z compatible).
        """
        app = Krita.instance()
        doc = app.activeDocument()
        if not doc:
            QMessageBox.warning(None, "Operations Pie Menu", "No active document open.")
            return

        active_layer = doc.activeNode()
        if not active_layer:
            QMessageBox.warning(None, "Operations Pie Menu", "No active layer selected.")
            return

        doc_w = doc.width()
        doc_h = doc.height()

        bounds = active_layer.bounds()
        gx, gy, gw, gh = bounds.x(), bounds.y(), bounds.width(), bounds.height()

        if gw <= 0 or gh <= 0:
            QMessageBox.information(None, "Operations Pie Menu", "Active layer is empty.")
            return

        # Compute scaling factor preserving aspect ratio
        scale_w = doc_w / gw
        scale_h = doc_h / gh
        scale = min(scale_w, scale_h)

        target_gw = max(1, int(gw * scale))
        target_gh = max(1, int(gh * scale))

        target_gx = (doc_w - target_gw) // 2
        target_gy = (doc_h - target_gh) // 2

        try:
            from PyQt5.QtGui import QImage
            from PyQt5.QtCore import Qt, QByteArray

            if active_layer.type() == "grouplayer":
                # Collect all child paint layers recursively inside group
                child_paint_layers = active_layer.findChildNodes("", True, False, "paintlayer")
                if not child_paint_layers:
                    QMessageBox.information(None, "Operations Pie Menu", "Group Layer contains no paint layers.")
                    return

                for child in child_paint_layers:
                    cbounds = child.bounds()
                    cx, cy, cw, ch = cbounds.x(), cbounds.y(), cbounds.width(), cbounds.height()
                    if cw <= 0 or ch <= 0:
                        continue

                    # Calculate relative coordinates inside group
                    rel_x = (cx - gx) / gw
                    rel_y = (cy - gy) / gh
                    new_cw = max(1, int(cw * scale))
                    new_ch = max(1, int(ch * scale))
                    new_cx = target_gx + int(rel_x * target_gw)
                    new_cy = target_gy + int(rel_y * target_gh)

                    raw_bytes = bytearray(child.pixelData(cx, cy, cw, ch))
                    img = QImage(raw_bytes, cw, ch, cw * 4, QImage.Format_ARGB32).copy()

                    scaled_img = img.scaled(new_cw, new_ch, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    if scaled_img.format() != QImage.Format_ARGB32:
                        scaled_img = scaled_img.convertToFormat(QImage.Format_ARGB32)

                    ptr = scaled_img.constBits()
                    ptr.setsize(new_cw * new_ch * 4)
                    new_bytes = QByteArray(bytes(ptr))

                    # Clear old bounds and set scaled bytes at new coordinates
                    clear_bytes = b'\x00' * (cw * ch * 4)
                    child.setPixelData(QByteArray(clear_bytes), cx, cy, cw, ch)
                    child.setPixelData(new_bytes, new_cx, new_cy, new_cw, new_ch)

                doc.refreshProjection()

            else:
                # Single Paint Layer scaling (node substitution for Ctrl+Z undo compatibility)
                raw_bytes = bytearray(active_layer.pixelData(gx, gy, gw, gh))
                img = QImage(raw_bytes, gw, gh, gw * 4, QImage.Format_ARGB32).copy()

                scaled_img = img.scaled(target_gw, target_gh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                if scaled_img.format() != QImage.Format_ARGB32:
                    scaled_img = scaled_img.convertToFormat(QImage.Format_ARGB32)

                ptr = scaled_img.constBits()
                ptr.setsize(target_gw * target_gh * 4)
                new_bytes = QByteArray(bytes(ptr))

                parent = active_layer.parentNode() or doc.rootNode()

                scaled_layer = doc.createNode(active_layer.name(), "paintlayer")
                scaled_layer.setPixelData(new_bytes, target_gx, target_gy, target_gw, target_gh)

                try:
                    scaled_layer.setAlphaLocked(active_layer.alphaLocked())
                except Exception:
                    pass

                parent.addChildNode(scaled_layer, active_layer)
                active_layer.remove()

                doc.setActiveNode(scaled_layer)
                doc.refreshProjection()

        except Exception as e:
            QMessageBox.warning(None, "Operations Pie Menu", f"Failed to fit layer to canvas: {e}")

    def execute_se_operation(self):
        """
        South-East ('SE') action:
        - If 'B&W' layer already exists anywhere in document, toggle its visibility.
        - Otherwise, create a paint layer named 'B&W' at the very top of the stack,
          fill it with solid black (#000000), set its blend mode to 'color',
          and keep the initial layer active.
        """
        app = Krita.instance()
        doc = app.activeDocument()
        if not doc:
            QMessageBox.warning(None, "Operations Pie Menu", "No active document open.")
            return

        initial_layer = doc.activeNode()

        # Find existing 'B&W' layer in document
        def find_bw_node(node):
            for child in node.childNodes():
                if child.name() == "B&W":
                    return child
                found = find_bw_node(child)
                if found:
                    return found
            return None

        bw_layer = find_bw_node(doc.rootNode())

        if bw_layer:
            # Toggle visibility if it already exists
            bw_layer.setVisible(not bw_layer.visible())
            doc.refreshProjection()
            return

        # Create new 'B&W' layer at top of root node
        bw_layer = doc.createNode("B&W", "paintlayer")
        doc.rootNode().addChildNode(bw_layer, None)

        # Set blending mode to 'color'
        try:
            bw_layer.setBlendingMode("color")
        except Exception:
            pass

        # Fill layer with solid black (#000000)
        w, h = doc.width(), doc.height()
        try:
            sample = bw_layer.pixelData(0, 0, 1, 1)
            p_len = len(sample) if sample else 4
            # RGBA format where R=0, G=0, B=0, A=255
            # For 8-bit channels: b'\x00\x00\x00\xff' for RGBA or fill black bytes
            if p_len == 4:
                black_pixel = b'\x00\x00\x00\xff'
            else:
                black_pixel = b'\x00' * (p_len - 1) + b'\xff'
            black_bytes = black_pixel * (w * h)
            bw_layer.setPixelData(QByteArray(black_bytes), 0, 0, w, h)
        except Exception:
            pass

        # Maintain initial active layer selection
        if initial_layer:
            doc.setActiveNode(initial_layer)

        doc.refreshProjection()




    def setup_canvas_operation(self):
        """
        Bottom stub ('S') action:
        - Check if document has > 1 layer. If so, prompt 'Nuke Document?'.
        - If approved (or 1 layer), fill base layer with solid white, rename 'WHITE', 75% opacity.
        - Create group layer 'LINES', create paint layer '1' inside 'LINES', activate layer '1'.
        - Set active tool to Freehand Brush ('KritaShape/KritaShapeFreehand').
        """
        app = Krita.instance()
        doc = app.activeDocument()
        if not doc:
            QMessageBox.warning(None, "Operations Pie Menu", "No active document open.")
            return

        def count_all_nodes(node):
            nodes = []
            for child in node.childNodes():
                nodes.append(child)
                nodes.extend(count_all_nodes(child))
            return nodes

        all_nodes = count_all_nodes(doc.rootNode())

        if len(all_nodes) > 1:
            reply = QMessageBox.question(
                None,
                "Nuke Document?",
                "Nuke Document?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            # Nuke existing nodes (unlock first so removal succeeds even if locked)
            for n in all_nodes:
                try:
                    n.setLocked(False)
                    n.setAlphaLocked(False)
                    n.remove()
                except Exception:
                    pass

        # Prepare base layer
        top_nodes = doc.topLevelNodes()
        if top_nodes:
            base_layer = top_nodes[0]
        else:
            base_layer = doc.createNode("WHITE", "paintlayer")
            doc.rootNode().addChildNode(base_layer, None)

        # Unlock base layer, remove alpha lock, and ensure layer is visible
        try:
            base_layer.setLocked(False)
            base_layer.setAlphaLocked(False)
            base_layer.setVisible(True)
        except Exception:
            pass

        # 1. Fill base layer with solid white (#FFFFFF)
        w, h = doc.width(), doc.height()
        try:
            sample = base_layer.pixelData(0, 0, 1, 1)
            p_len = len(sample) if sample else 4
            white_bytes = b'\xff' * (w * h * p_len)
            base_layer.setPixelData(QByteArray(white_bytes), 0, 0, w, h)
        except Exception:
            pass


        # 2. Rename base layer to "WHITE"
        base_layer.setName("WHITE")

        # 3. Set opacity to 75% (191 / 255)
        base_layer.setOpacity(191)

        # 4. Create Group Layer "LINES"
        lines_group = doc.createGroupLayer("LINES")
        doc.rootNode().addChildNode(lines_group, None)

        # 5. Create Paint Layer "1" inside "LINES"
        layer_1 = doc.createNode("1", "paintlayer")
        lines_group.addChildNode(layer_1, None)
        layer_1.setOpacity(255)

        # 6. Set active layer to layer "1"
        doc.setActiveNode(layer_1)
        doc.refreshProjection()

        # 7. Turn off Eraser mode if active
        erase_act = app.action("erase_action")
        if erase_act and erase_act.isChecked():
            erase_act.trigger()

        # 8. Set active tool to Freehand Brush
        brush_act = app.action("KritaShape/KritaShapeFreehand")
        if brush_act:
            brush_act.trigger()

        # 9. Select "0 STD DRW" brush preset and set foreground color to pure opaque black (#000000)
        # First trigger Krita's built-in reset action (Foreground = Black, Background = White)
        reset_act = app.action("reset_fg_bg")
        if reset_act:
            reset_act.trigger()

        window = app.activeWindow()
        if window:
            view = window.activeView()
            if view:
                try:
                    from krita import ManagedColor
                    black = ManagedColor("RGBA", "U8", "")
                    black.setComponents([0.0, 0.0, 0.0, 1.0])
                    view.setForeGroundColor(black)
                except Exception:
                    pass

                try:
                    resources = app.resources("preset")
                    preset_to_activate = None
                    for name, res in resources.items():
                        if "0 std drw" in name.lower() or name.lower() == "0 std drw":
                            preset_to_activate = res
                            break
                    if not preset_to_activate:
                        for name, res in resources.items():
                            if "std drw" in name.lower():
                                preset_to_activate = res
                                break
                    if preset_to_activate:
                        view.activateResource(preset_to_activate)
                except Exception:
                    pass



