"""통합 실행 기록 판정 → analysis.json (UAV: 지형 여유·순항·착륙, UGV: 차체 이탈·화재 칸 경계 거리·지나간 도로).
  python integration/px4_live/judge_run.py logs/integ/run_<시각>
UAV 목표 = 화재 칸 중심 (프로파일 ENV_IGNITION), 거점 = 인제119안전센터 좌표 (UNVERIFIED)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

HOME_LL = (38.0613774, 128.1684755)


def main(run: Path):
    import os
    prof = json.loads((run / "profile.json").read_text(encoding="utf-8"))
    os.environ["UGV_ROAD_SUBSET"] = str(ROOT / prof["ugv"]["UGV_ROAD_SUBSET"])
    import gz_bridge as gb
    import run_integ
    import uav_pretest
    col, row = (int(v) for v in prof["env"]["ENV_IGNITION"].split(","))
    fla, flo = gb.grid_cell_to_latlon(col, row)
    out = {"ugv": run_integ.analyze_ugv(run / "track_adair_ugv_1.csv", fla, flo),
           "uav": uav_pretest.analyze(run / "track_x500_0.csv", [], HOME_LL, (fla, flo))}
    (run / "analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    u, g = out["uav"], out["ugv"]
    print("UGV", g.get("status"), "이탈", g.get("offroad_samples"), g.get("offroad_max_m"), "전복", g.get("rollover_samples"),
          "화재 경계", g.get("min_dist_to_fire_cell_m_conservative"))
    print("UAV", u.get("status"), "지형 여유", u.get("min_clearance_surface_m"), "순항", u.get("cruise_hspeed_p50_mps"),
          "감시", u.get("time_within_10m_of_target_s"), "거점", u.get("final_dist_to_home_m"), "지면 위", u.get("final_height_above_surface_m"))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
