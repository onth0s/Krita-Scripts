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
            "N":  { "label": "Stub North",       "action_id": "op_stub_north" },
            "NE": { "label": "Stub North East",  "action_id": "op_stub_ne" },
            "E":  { "label": "Stub East",        "action_id": "op_stub_east" },
            "SE": { "label": "Stub South East",  "action_id": "op_stub_se" },
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

        config = self.load_config()
        callbacks = {}
        items_meta = {}

        for code, data in config.items():
            act_id = data.get('action_id', '')
            label = data.get('label', '')
            items_meta[code] = (label, act_id)
            if code == 'S' or act_id == 'op_setup_canvas':
                callbacks[code] = self.setup_canvas_operation
            elif code == 'N' or act_id == 'op_stub_north':
                callbacks[code] = self.execute_north_operation
            elif code == 'W' or act_id == 'op_stub_west':
                callbacks[code] = self.execute_west_operation
            else:
                callbacks[code] = self.make_stub_callback(code, label, act_id)


        self.pie_widget = PieMenuWidget(callbacks, items_meta=items_meta, object_name="OperationsPieWidget")
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
        North ('N') stub action:
        1. Set current layer to Alpha Locked.
        2. Fill current layer with purple (#6c37bb).
        3. Parse current layer name integer, increment by +1 for new layer name.
        4. Create new paint layer directly above current layer.
        5. Set active layer to new layer.
        6. Reset foreground color to Black.
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

        # 1. Set current layer to Alpha Locked
        try:
            active_layer.setAlphaLocked(True)
        except Exception:
            pass

        # 2. Set foreground color to #6c37bb (R:108, G:55, B:187) and fill
        window = app.activeWindow()
        if window:
            view = window.activeView()
            if view:
                try:
                    from krita import ManagedColor
                    purple = ManagedColor(doc.colorModel(), doc.colorDepth(), doc.colorProfile())
                    purple.setComponents([108/255.0, 55/255.0, 187/255.0, 1.0])
                    view.setForeGroundColor(purple)
                except Exception:
                    pass

        fill_act = app.action("fill_selection_foreground_color")
        if not fill_act:
            fill_act = app.action("edit_fill_selection_foreground_color")
        if fill_act:
            fill_act.trigger()

        # 3. Parse current layer name as integer and increment
        curr_name = active_layer.name().strip()
        import re
        matches = re.findall(r'\d+', curr_name)
        if matches:
            next_num = int(matches[-1]) + 1
        else:
            next_num = 2

        new_layer_name = str(next_num)

        # 4. Create new paint layer directly above active_layer
        new_layer = doc.createNode(new_layer_name, "paintlayer")
        parent = active_layer.parentNode()
        if not parent:
            parent = doc.rootNode()
        parent.addChildNode(new_layer, active_layer)

        # 5. Set active layer to new layer
        doc.setActiveNode(new_layer)
        doc.refreshProjection()

        # 6. Reset color back to Black (#000000)
        reset_act = app.action("reset_fg_bg")
        if reset_act:
            reset_act.trigger()

        if window:
            view = window.activeView()
            if view:
                try:
                    from krita import ManagedColor
                    black = ManagedColor(doc.colorModel(), doc.colorDepth(), doc.colorProfile())
                    black.setComponents([0.0, 0.0, 0.0, 1.0])
                    view.setForeGroundColor(black)
                except Exception:
                    pass

    def execute_west_operation(self):
        """
        West ('W') stub action:
        Resize/scale active layer to fit the document size.
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

        from PyQt5.QtCore import QPointF
        doc_w = doc.width()
        doc_h = doc.height()

        try:
            active_layer.scaleNode(QPointF(0, 0), doc_w, doc_h, "Bilinear")
            active_layer.move(0, 0)
            doc.refreshProjection()
        except Exception as e:
            QMessageBox.warning(None, "Operations Pie Menu", f"Failed to resize layer: {e}")



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



