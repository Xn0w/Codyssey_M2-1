"""관측 범위 화면 요약 (api._one_observation): 모양마다 표시에 필요한 키가 빠지지 않는가.
2026-10-18 팀 보고: UGV 지상 열화상 관측(RADIUS_TERRAIN_LOS)이 화면에 '0m × 0m (높이 0m)' 로 보였다 —
요약이 드론 한 프레임 키(width_m·height_m·agl_m)만 넘겨 UGV 는 셋 다 null 이었다."""
from orchestrator import api


def _obs(fp):
    return {"result": "NOT_DETECTED", "resource_id": "B-ugv1", "detail": {"footprint": fp, "source": "SIMULATED"}}


def test_ugv_line_of_sight_footprint_keeps_radius_and_mast():
    fp = {"shape": "RADIUS_TERRAIN_LOS", "min_m": 600.0, "max_m": 2000.0, "mast_m": 3.0, "eye_amsl_m": 512.3,
          "visible_cells": 140, "hidden_cells": 12, "agl_m": None, "method": "GRID_LINE_OF_SIGHT_HALF_CELL_STEP"}
    s = api._one_observation(_obs(fp), None)["footprint"]
    assert s["shape"] == "RADIUS_TERRAIN_LOS"
    assert (s["min_m"], s["max_m"], s["mast_m"]) == (600.0, 2000.0, 3.0)
    assert (s["visible_cells"], s["hidden_cells"]) == (140, 12)
    assert s["width_m"] is None and s["agl_m"] is None          # 사각형 키는 없다 → 화면은 모양으로 갈라 그린다


def test_swath_and_frame_footprints_keep_their_keys():
    sw = api._one_observation(_obs({"shape": "SWATH_ALONG_PATH", "swath_m": 40.0, "length_m": 180.0, "width_m": 40.0,
                                    "height_m": 180.0, "agl_m": None}), None)["footprint"]
    assert (sw["shape"], sw["swath_m"], sw["length_m"]) == ("SWATH_ALONG_PATH", 40.0, 180.0)
    fr = api._one_observation(_obs({"shape": "RECT", "width_m": 52.0, "height_m": 42.0, "agl_m": 90.0}), None)["footprint"]
    assert (fr["width_m"], fr["height_m"], fr["agl_m"]) == (52.0, 42.0, 90.0)


def test_no_footprint_stays_none():
    assert api._one_observation(_obs(None), None)["footprint"] is None
