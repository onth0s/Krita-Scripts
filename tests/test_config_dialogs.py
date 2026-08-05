import json

import pytest

from conditions_pie_menu.config_dialog import ConditionsConfigDialog
from filters_pie_menu.config_dialog import SectorConfigDialog
from krita_pie_menu.base_config_dialog import SECTOR_CODES, BasePieConfigDialog
from krita_pie_menu.utils import save_config
from operations_pie_menu.config_dialog import OperationsConfigDialog


@pytest.fixture
def qmessage(monkeypatch):
    from krita_pie_menu import base_config_dialog

    calls = {"info": [], "critical": []}
    monkeypatch.setattr(
        base_config_dialog.QMessageBox,
        "information",
        staticmethod(lambda *a, **k: calls["info"].append(a)),
    )
    monkeypatch.setattr(
        base_config_dialog.QMessageBox,
        "critical",
        staticmethod(lambda *a, **k: calls["critical"].append(a)),
    )
    return calls


def _stub_sector_combos(dlg):
    for code in dlg.combos:
        combo = dlg.combos[code]
        combo.currentText = (lambda c=code: f"Label {c}")
        combo.currentData = (lambda c=code: f"krita_filter_{c.lower()}")


def test_base_dialog_build_sector_editors_is_abstract(tmp_path):
    with pytest.raises(NotImplementedError):
        BasePieConfigDialog(str(tmp_path / "c.json"), title="x")


def test_sector_config_dialog_loads_existing_config(tmp_path):
    cfg = tmp_path / "config.json"
    save_config(str(cfg), {"N": {"label": "HSV", "action_id": "krita_filter_hsvadjustment"}})
    dlg = SectorConfigDialog(str(cfg))
    assert dlg.current_config["N"]["label"] == "HSV"
    assert dlg.current_config["N"]["action_id"] == "krita_filter_hsvadjustment"


def test_sector_config_dialog_collect_and_save(tmp_path, qmessage, monkeypatch):
    cfg = tmp_path / "config.json"
    save_config(str(cfg), {"duplicate_reflay": True, "N": {"label": "HSV", "action_id": "krita_filter_hsvadjustment"}})

    saved = []
    dlg = SectorConfigDialog(str(cfg), on_save_callback=lambda c: saved.append(c))
    accepted = []
    monkeypatch.setattr(dlg, "accept", lambda: accepted.append(1))

    _stub_sector_combos(dlg)
    dlg.handle_save()

    assert saved, "on_save_callback must be invoked"
    merged = saved[0]
    assert merged["duplicate_reflay"] is True  # root-level key preserved
    assert set(merged) == set(SECTOR_CODES) | {"duplicate_reflay"}
    assert qmessage["info"], "success info box expected"
    assert not qmessage["critical"]
    assert accepted == [1]

    on_disk = json.loads(cfg.read_text(encoding="utf-8"))
    assert on_disk["N"]["action_id"] == "krita_filter_n"


def test_sector_config_dialog_save_failure(tmp_path, qmessage, monkeypatch):
    from krita_pie_menu import base_config_dialog

    monkeypatch.setattr(base_config_dialog, "save_config", lambda *a, **k: False)
    dlg = SectorConfigDialog(str(tmp_path / "c.json"))
    accepted = []
    monkeypatch.setattr(dlg, "accept", lambda: accepted.append(1))

    _stub_sector_combos(dlg)
    dlg.handle_save()

    assert qmessage["critical"]
    assert accepted == []


def test_sector_config_dialog_collect_exception(tmp_path, qmessage, monkeypatch):
    dlg = SectorConfigDialog(str(tmp_path / "c.json"))

    def boom():
        raise RuntimeError("collect failed")

    monkeypatch.setattr(dlg, "collect_config", boom)
    dlg.handle_save()

    assert qmessage["critical"]
    assert "collect failed" in str(qmessage["critical"][0])


def test_operations_config_dialog_collect(tmp_path):
    dlg = OperationsConfigDialog(str(tmp_path / "c.json"))
    for code in dlg.inputs:
        lbl, act = dlg.inputs[code]
        lbl.text = (lambda c=code: f"Label {c}")
        act.text = (lambda c=code: f"op_{c.lower()}")

    cfg = dlg.collect_config()
    assert set(cfg) == set(SECTOR_CODES)
    assert cfg["N"] == {"label": "Label N", "action_id": "op_n"}


def test_conditions_config_dialog_collect(tmp_path):
    dlg = ConditionsConfigDialog(str(tmp_path / "c.json"))
    dlg.chk_dup_reflay.isChecked = lambda: True
    dlg.chk_keep_ar.isChecked = lambda: False
    for code in dlg.inputs:
        lbl, act = dlg.inputs[code]
        lbl.text = (lambda c=code: f"Label {c}")
        act.text = (lambda c=code: f"cond_{c.lower()}")

    cfg = dlg.collect_config()
    assert cfg["duplicate_reflay"] is True
    assert cfg["keep_aspect_ratio"] is False
    assert set(cfg) == set(SECTOR_CODES) | {"duplicate_reflay", "keep_aspect_ratio"}
