# -*- coding: utf-8 -*-
"""132+ scenario desktop verification matrix (ISO 17636 / ASME Sec V Art 2).

Each scenario configures the real MainWindow end-to-end (material x source x
geometry x diameter x wall thickness x detector model x testing class x
standard) and compares the program outputs against the independent oracle in
`tests/matrix_oracle.py`.

Known deviations of the current implementation (2022 wire-IQI table
transcription, film-system-class model, Yb/Tm thin-section SNR) are reported as
`known` and do not fail the build; every other deviation is a hard failure.
Run with `-s` to see the deviation summary.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.matrix_oracle import SCENARIOS, compare  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(scope="module")
def win(qapp):
    from PyQt6.QtCore import QSettings
    QSettings("Radiography", "Radiography").clear()
    from src.ui.main_window import MainWindow
    w = MainWindow()
    yield w
    try:
        w.canvas.figure.clf()
        w.std_canvas.figure.clf()
    except Exception:
        pass
    w.close()
    w.deleteLater()


def configure(win, sc):
    # Scalars first: setting the geometry before the new OD/t could be undone by
    # the DWDI->DWSI forcing applied for the previous scenario's large OD.
    win.txt_custom_od.setText(str(sc["od"]))
    win.txt_custom_t.setText(str(sc["t"]))
    win.txt_cap.setText(str(sc["cap"]))
    win.txt_d.setText(str(sc["d"]))
    win.txt_bed.setText(str(sc["bed"]))
    win.txt_bgap.setText(str(sc["bgap"]))
    win.txt_app_sfd.setText(str(sc["sfd"]))
    win.txt_app_kv.setText(str(sc["kv"]))
    win.rad_digital.setChecked(sc["tech"] == "digital")
    win.rad_analog.setChecked(sc["tech"] == "analog")
    win.rad_detector_flat.setChecked(sc["planar"])
    win.rad_detector_curved.setChecked(not sc["planar"])
    win.cmb_material.setCurrentIndex(win.cmb_material.findData(sc["material"]))
    win.cmb_source.setCurrentIndex(win.cmb_source.findData(sc["source"]))
    win.cmb_class.setCurrentIndex(win.cmb_class.findData(sc["testing_class"]))
    win.cmb_standard.setCurrentIndex(win.cmb_standard.findData(sc["standard"]))
    win.cmb_geometry.setCurrentIndex(
        win.cmb_geometry.findData(sc["requested_geometry"]))
    # The DWDI->DWSI forcing note is emitted on the update triggered by the
    # geometry switch; later updates overwrite the warning box, so capture it.
    transient = win.txt_warnings.text()
    win.update_std_figure_list()
    # Receptor dimensions: square receptor whose diagonal equals sc["dd"]
    side = sc["dd"] / (2.0 ** 0.5)
    if sc["tech"] == "analog":
        win.cmb_film_size.setCurrentIndex(win.cmb_film_size.findData("custom"))
        win.txt_film_width.setText(f"{side:.6f}")
        win.txt_film_height.setText(f"{side:.6f}")
    else:
        win.txt_panel_width.setText(f"{side:.6f}")
        win.txt_panel_height.setText(f"{side:.6f}")
    # Pick a valid standard figure (list depends on technology and panel type)
    want = sc["std_figure"]
    if win.cmb_std_figure.findData(want) < 0:
        for fallback in ("fig8b", "fig8a", "fig6", "fig6a", "fig11",
                         "fig13b", "fig13a", "fig14", "fig13"):
            if win.cmb_std_figure.findData(fallback) >= 0:
                want = fallback
                break
    idx = win.cmb_std_figure.findData(want)
    if idx >= 0:
        win.cmb_std_figure.setCurrentIndex(idx)
    sc["std_figure"] = win.cmb_std_figure.currentData()
    win.chk_source_side_iqi.setChecked(sc["source_side"])
    win.update_calculations()
    # Guard: if a stale forced geometry is still active, re-apply the request
    if win.cmb_geometry.currentData() != sc["requested_geometry"] and sc["od"] <= 100.0:
        win.cmb_geometry.setCurrentIndex(
            win.cmb_geometry.findData(sc["requested_geometry"]))
        win.update_calculations()
        transient = win.txt_warnings.text()
    return transient


def read_program(win):
    lc = win.last_calculated
    return {
        "w_nom": lc.get("w_nom"),
        "w_eff": lc.get("w_eff"),
        "u_max": lc.get("u_max"),
        "b_dist": lc.get("b_dist"),
        "f_min_iso": lc.get("f_min_iso"),
        "f_min_asme": lc.get("f_min_asme"),
        "f_min_gov": lc.get("f_min"),
        "sfd_min": lc.get("sfd_min"),
        "ug": lc.get("ug"),
        "required_wire_no": lc.get("required_wire_no"),
        "required_duplex_no": lc.get("required_duplex_no"),
        "max_srb": lc.get("max_srb"),
        "required_film_class": lc.get("required_film_class"),
        "required_snr": lc.get("required_snr"),
        "exposures_graph": lc.get("exposures_graph"),
        "warnings": win.txt_warnings.text(),
    }


_REPORT = {"known": {}, "info": {}, "hard": {}}


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario_matrix(win, sc):
    transient = configure(win, sc)
    prog = read_program(win)
    prog["warnings"] = transient + "\n" + prog["warnings"]
    hard, known, infos = compare(sc, prog)
    if known:
        _REPORT["known"][sc["id"]] = known
    if infos:
        _REPORT["info"][sc["id"]] = infos
    if hard:
        _REPORT["hard"][sc["id"]] = hard
    assert not hard, f"{sc['id']}: " + " | ".join(hard)


def test_matrix_summary(capsys):
    """Prints the deviation summary (run with -s to see it)."""
    total = len(SCENARIOS)
    hard_ids = sorted(_REPORT["hard"])
    known_ids = sorted(_REPORT["known"])
    info_ids = sorted(_REPORT["info"])
    print(f"\n=== Scenario matrix: {total} scenarios ===")
    print(f"hard mismatches : {len(hard_ids)}")
    print(f"known deviations: {len(known_ids)}")
    print(f"informational   : {len(info_ids)}")
    if known_ids:
        print("\n-- known deviations --")
        for sid in known_ids:
            for line in _REPORT["known"][sid]:
                print(f"  {sid}: {line}")
    if info_ids:
        print("\n-- informational (program conservative / notes) --")
        for sid in info_ids:
            for line in _REPORT["info"][sid]:
                print(f"  {sid}: {line}")
    if hard_ids:
        print("\n-- HARD mismatches --")
        for sid in hard_ids:
            for line in _REPORT["hard"][sid]:
                print(f"  {sid}: {line}")
    assert not hard_ids, "hard mismatches present"
