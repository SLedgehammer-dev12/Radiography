import pytest
import sys
sys.path.insert(0, "src")

from core.asme_b36 import (
    ASME_B36_10_PIPES,
    ASME_B36_19_PIPES,
    get_pipe_od,
    get_pipe_schedules,
    find_nps_by_od,
    get_default_schedule,
)


def test_b36_10_non_empty():
    assert len(ASME_B36_10_PIPES) >= 38


def test_b36_19_non_empty():
    assert len(ASME_B36_19_PIPES) >= 20


def test_all_ods_positive():
    for key, (od, schedules) in ASME_B36_10_PIPES.items():
        assert od > 0, f"{key} has non-positive OD"
        assert od < 2000, f"{key} OD too large"
    for key, (od, schedules) in ASME_B36_19_PIPES.items():
        assert od > 0, f"{key} has non-positive OD"
        assert od < 2000, f"{key} OD too large"


def test_all_walls_positive():
    for key, (od, schedules) in ASME_B36_10_PIPES.items():
        for wall, label in schedules:
            assert wall > 0, f"{key} {label} wall non-positive"
            assert wall < od, f"{key} {label} wall ({wall}) >= OD ({od})"
    for key, (od, schedules) in ASME_B36_19_PIPES.items():
        for wall, label in schedules:
            assert wall > 0, f"{key} {label} wall non-positive"
            assert wall < od, f"{key} {label} wall ({wall}) >= OD ({od})"


def test_no_duplicate_schedules():
    for key, (od, schedules) in ASME_B36_10_PIPES.items():
        labels = [s[1] for s in schedules]
        assert len(labels) == len(set(labels)), f"{key} has duplicate schedule labels"


def test_od_corrections():
    assert ASME_B36_10_PIPES['10" (NPS 10)'][0] == 273.1
    assert ASME_B36_10_PIPES['18" (NPS 18)'][0] == 457.2
    assert ASME_B36_10_PIPES['22" (NPS 22)'][0] == 558.8
    assert ASME_B36_10_PIPES['24" (NPS 24)'][0] == 609.6
    assert ASME_B36_10_PIPES['26" (NPS 26)'][0] == 660.4
    assert ASME_B36_10_PIPES['28" (NPS 28)'][0] == 711.2
    assert ASME_B36_10_PIPES['32" (NPS 32)'][0] == 812.8
    assert ASME_B36_10_PIPES['34" (NPS 34)'][0] == 863.6
    assert ASME_B36_10_PIPES['36" (NPS 36)'][0] == 914.4


def test_ods_match_b36_19():
    shared = set(ASME_B36_10_PIPES.keys()) & set(ASME_B36_19_PIPES.keys())
    for key in shared:
        od10 = ASME_B36_10_PIPES[key][0]
        od19 = ASME_B36_19_PIPES[key][0]
        assert od10 == od19, f"{key} OD mismatch: B36.10={od10} B36.19={od19}"


def _by_label(schedules):
    return {label: wall for wall, label in schedules}

def test_added_schedules():
    nps_1_8 = _by_label(ASME_B36_10_PIPES['1/8" (NPS 1/8)'][1])
    assert nps_1_8["SCH 160"] == 3.15
    assert nps_1_8["XXS"] == 4.83

    nps_1_4 = _by_label(ASME_B36_10_PIPES['1/4" (NPS 1/4)'][1])
    assert nps_1_4["SCH 160"] == 3.68

    nps_3_8 = _by_label(ASME_B36_10_PIPES['3/8" (NPS 3/8)'][1])
    assert nps_3_8["SCH 160"] == 4.01
    assert nps_3_8["XXS"] == 6.40


def test_get_pipe_od():
    assert get_pipe_od('4" (NPS 4)') == 114.3
    assert get_pipe_od('10" (NPS 10)') == 273.1
    assert get_pipe_od("nonexistent") is None


def test_get_pipe_od_b36_19():
    od = get_pipe_od('4" (NPS 4)', standard="B36.19")
    assert od == 114.3


def test_get_pipe_schedules():
    scheds = get_pipe_schedules('4" (NPS 4)')
    assert len(scheds) >= 8
    labels = [l for _, l in scheds]
    assert "SCH 40 / STD" in labels


def test_get_pipe_schedules_empty():
    assert get_pipe_schedules("nonexistent") == []


def test_find_nps_by_od():
    key = find_nps_by_od(114.3)
    assert key == '4" (NPS 4)'


def test_find_nps_by_od_no_match():
    assert find_nps_by_od(9999) is None


def test_get_default_schedule():
    wall, label = get_default_schedule('4" (NPS 4)')
    assert "STD" in label or "SCH 40" in label
    assert wall == 6.02


def test_b36_19_5s_not_in_small_sizes():
    nps_1_8 = dict(ASME_B36_19_PIPES['1/8" (NPS 1/8)'][1])
    assert "SCH 5S" not in nps_1_8


def test_b36_19_5s_in_larger_sizes():
    nps_1_2 = _by_label(ASME_B36_19_PIPES['1/2" (NPS 1/2)'][1])
    assert nps_1_2["SCH 5S"] == 1.65
