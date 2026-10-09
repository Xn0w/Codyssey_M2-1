# ugv/config.py — 전부 잠정값, 팀 합의 필요

import os

# 자원 배치 — Gazebo 월드 1개(kangwon)에 PX4 인스턴스 3개 (차량당 PX4 1개, 제어 프로그램은 이 서버 1개)
# px4_instance i → PX4 가 MAVLink 를 14540 + i 로 보낸다. 0 은 UAV 몫이라 UGV 는 1 부터.
# px4_model: PX4 Gazebo 모델 이름. 에어프레임 번호는 ugv/tools/px4-start.sh 가 모델 이름으로 찾는다.
# max_speed_mps: 차량 최고속도(시뮬레이션 초당 m). 도로별 속도 = min(max(도로 제한속도, MIN_ROAD_SPEED_KMH), 이 값) ÷ 혼잡 배율.
#   r1_rover 2.1 (RO_MAX_THR_SPEED), rover_ackermann 3.1, lawnmower 2.7 — PX4 v1.16 기본 파라미터 기준.
#   실제 소방차(수십 km/h)가 아니라 Gazebo 차량 속도에 맞춘 값이다. 실제 시간감은 UGV_TIME_SCALE 로 맞춘다.
# sim_speed_mps: sim 드라이버(PX4 없이)로 달릴 때만 쓰는 속도. 없으면 max_speed_mps. ETA 도 같은 값으로 낸다.
#   세 대 모두 60 km/h (상한, 총괄 브랜치 결정 2026-10-07 과 같은 값). 느린 도로는 하한 50 km/h (MIN_ROAD_SPEED_KMH) —
#   sim 주행은 도로마다 50~60 km/h. PX4 는 r1_rover 라 2.0 그대로 (하한보다 작은 최고속도가 우선이라 영향 없음).
# 스폰 위치는 ugv/data/road_network.json 의 spawn[resource_id] (build_road_network.py 가 계산).
RESOURCES = [
    {"resource_id": "A-ugv1",  "resource_type": "UGV",
     "base": "A", "home_node": "A", "px4_instance": 1, "px4_model": "r1_rover", "max_speed_mps": 2.0,
     "sim_speed_mps": 60 / 3.6},
    # 소방차도 r1_rover 기반 (2026-10-03 WSL): rover_ackermann 은 명령 없이(disarm 상태) 조향된 채 굴러가
    # 도로 밖으로 떨어졌다. 경광등·방수포는 px4-start.sh 가 r1_rover 위에 붙인다 (ugv/gazebo/fire_truck)
    {"resource_id": "A-fire1", "resource_type": "FIRE_ENGINE",
     "base": "A", "home_node": "A", "px4_instance": 3, "px4_model": "r1_rover", "max_speed_mps": 2.0,
     "sim_speed_mps": 60 / 3.6},
    {"resource_id": "B-ugv1",  "resource_type": "UGV",
     "base": "B", "home_node": "B", "px4_instance": 2, "px4_model": "r1_rover", "max_speed_mps": 2.0,
     "sim_speed_mps": 60 / 3.6},
]
for _r in RESOURCES:
    _r["px4_port"] = 14540 + _r["px4_instance"]

# 장비 (ugv/equipment.py) — 잠정값
#   소방차: 물탱크·방수량. [봉인 — UGV_SUPPRESSION=1 일 때만] 도착하면 자동으로 진압(SUPPRESSING) — 물이 바닥나거나 /suppress stop 까지.
#     3,000 L 탱크 + 분당 1,800 L(30 L/s) 방수는 중형 펌프차 수준 → 100 초. 거점 노드에 도착하면 다시 채운다.
#   UGV: 적재 한도. execute 의 cargo(이름, kg) + via_node(싣는 곳) → 싣기(LOADING)·내리기(UNLOADING) 자동.
#   경광등(siren)은 소방차가 출동·진압 중일 때 켠다 (Gazebo 표시: ugv/gz_fx.py).
EQUIPMENT = {
    "FIRE_ENGINE": {"water_capacity_l": 3000.0, "pump_lps": 30.0, "payload_kg": 0.0, "siren": True},
    "UGV":         {"water_capacity_l": 0.0,    "pump_lps": 0.0,  "payload_kg": 100.0, "siren": False},
}
LOAD_S = float(os.getenv("UGV_LOAD_S", "60"))       # 짐 싣기 (시뮬레이션 초)
UNLOAD_S = float(os.getenv("UGV_UNLOAD_S", "60"))   # 짐 내리기
# 진압(방수) 봉인 (2026-10-08 발표 범위 결정): 이번 발표는 진화를 다루지 않는다 — 소방차는 이동·환경 센서 자원으로만 쓴다.
# 코드는 남겨 두고 기본으로 끈다. 켜면(UGV_SUPPRESSION=1) 예전처럼 도착 즉시 진압·/suppress start 가 동작한다.
# 환경에 진화 효과(ENV-07)가 없으므로 켜도 물만 줄 뿐 화재는 바뀌지 않는다.
SUPPRESSION_ENABLED = os.getenv("UGV_SUPPRESSION", "0") == "1"
AUTO_SUPPRESS = SUPPRESSION_ENABLED and os.getenv("UGV_AUTO_SUPPRESS", "1") != "0"   # 소방차 도착 즉시 진압 시작

# PX4 연결
# PX4 SITL 은 MAVLink 를 자기 호스트의 127.0.0.1 로만 보낸다. Gazebo/PX4 가 원격(WSL)이면
# 그쪽에서 ugv/tools/mavlink_relay.py 가 이 서버 호스트의 같은 포트로 넘겨준다 → 여기서는 0.0.0.0 으로 받는다.
PX4_HOST = "0.0.0.0"
PX4_BASE_PORT = 14540   # 인스턴스 0 = UAV. UGV 는 위 RESOURCES 의 px4_port 를 쓴다.
# 차량별 mavsdk_server gRPC 포트 = 이 값 + px4_instance (50061~). 같은 포트를 쓰면 명령이 다른 차로 간다.
# UAV 쪽 mavsdk 기본 포트(50051)와 겹치지 않게 띄워 둔다.
MAVSDK_GRPC_BASE = int(os.getenv("UGV_MAVSDK_GRPC_BASE", "50060"))
# UGV_DRIVER=px4 일 때 실제로 PX4 에 연결할 자원. 나머지는 sim.
# 띄우지 않은 PX4 를 기다리면 서버가 시작되지 않으므로, 띄운 인스턴스만 적는다.
PX4_RESOURCES = [r for r in os.getenv("UGV_PX4_RESOURCES", "A-ugv1").split(",") if r]

# 시간 — 전부 시뮬레이션 초 기준 (ugv/sim_clock.py)
#   UGV_TIME_SCALE: 시뮬레이션 초 / 벽시계 초. PX4 쪽 PX4_SIM_SPEED_FACTOR 와 반드시 같은 값.
#     sim 드라이버도 이 배율로 움직이므로, PX4 없이 빨리 돌려 보려면 이 값만 키운다 (예: 200).
#   UGV_SECONDS_PER_ENV_STEP: 환경 CA 1 스텝(sim_step)이 몇 시뮬레이션 초인가.
#     환경·총괄 어디에도 정의가 없다(INT-05 미정). 잠정값 — 합의되면 이 값만 바꾼다.
TIME_SCALE = float(os.getenv("UGV_TIME_SCALE", "1"))
SECONDS_PER_ENV_STEP = float(os.getenv("UGV_SECONDS_PER_ENV_STEP", "60"))
# 총괄 보고 (ugv/reporter.py) — 평가·출발·진행·재탐색·도착·실패·중지·자원 상태 변화를 POST {URL}/events 로.
# 기본 꺼짐: 총괄이 1초마다 조회(polling)하므로 필요 없다. 켜려면 UGV_REPORT_URL=http://127.0.0.1:8200
# 꺼져 있어도 GET /reports 에 기록은 남는다.
REPORT_URL = os.getenv("UGV_REPORT_URL", "")
# 환경 시계 따라가기 (ugv/sim_clock.py): 환경 서버(/health 의 simulation_time_s)가 바뀔 때마다 UGV 시계를 그 값으로 맞추고,
# 그 사이는 벽시계 × UGV_TIME_SCALE 로 채운다. 시나리오 시작 시각(scenario_start_kst)도 받아 상황판이 시각으로 보여 준다.
# 비우면 UGV 서버 혼자 시계 (서버 시작 = 0). 환경이 없으면 조용히 혼자 간다.
ENV_URL = os.getenv("UGV_ENV_URL", "http://127.0.0.1:8300")
ENV_CLOCK_POLL_S = float(os.getenv("UGV_ENV_CLOCK_POLL_S", "1.0"))
# 총괄 주소 — 도로 상황판의 노드 클릭 출동 요청을 여기 POST /tasks 로 전달한다 (ugv/server.py /view/dispatch)
ORCH_URL = os.getenv("UGV_ORCH_URL", "http://127.0.0.1:8200")

# 도로 환경 시나리오(차단 도로·경유 불가 노드·혼잡의 시간대, CSV 또는 JSON). 기본은 시나리오 없음(도로 전부 열림)
# — 2026-10-08 발표 범위에서 길막·혼잡 제외. 켜기: UGV_SCENARIO=ugv/scenarios/inje_girin.csv
SCENARIO_FILE = os.getenv("UGV_SCENARIO", "")
# 차량 최고속도가 주어진 주행에서 도로 제한속도가 이보다 낮으면 이 값으로 본다 (50 km/h, 같은 결정). 0 이면 끔
MIN_ROAD_SPEED_KMH = float(os.getenv("UGV_MIN_ROAD_SPEED_KMH", "50"))

# 도로 AI (ugv/road_ai.py) — [봉인] 기본 꺼짐. 주행 중 앞길이 막히면 우회(1·2순위)·대기를 LLM(Gemini)이 판단한다.
#   sim 드라이버 차량만. 총괄 LLM 과 별개이고 키도 따로 (UGV_AGENT_API_KEY, 저장소 루트 .env 의 UGV_* 도 읽는다)
#   UGV_AGENT_MODE: function_calling (모델이 지식 검색 도구를 부름, 기본) | inline (서버가 자료를 찾아 프롬프트에 넣음)
#   실패하면 항상 1순위 우회 (끈 때와 같다). 시연 시나리오: ugv/scenarios/agent_block.csv + 지식 베이스 ugv/knowledge (가상 기사·지침)
AGENT_ENABLED = os.getenv("UGV_AGENT", "0") == "1"
AGENT_MODE = os.getenv("UGV_AGENT_MODE", "function_calling")
AGENT_MODEL = os.getenv("UGV_AGENT_MODEL", "gemini-3.5-flash-lite").strip().lower().replace(" ", "-")
# ↑ 2026-10-09: gemini-2.5-flash(-lite) 는 새 사용자에게 막혀(404) 교체. 3.8-flash 는 판단은 맞지만 응답 4~64초로 들쭉날쭉,
#   3.5-flash-lite 는 같은 probe 에서 3.5초·호출 2회·같은 판단(ROUTE_1, N1·G1) → 기본값. API 는 소문자 id 만 받아(Gemini-3.5-Flash-Lite → 400) 소문자로 맞춘다
AGENT_EMBED_MODEL = os.getenv("UGV_AGENT_EMBED_MODEL", "gemini-embedding-001")
AGENT_EMBED = os.getenv("UGV_AGENT_EMBED", "1") == "1"       # 0 이면 지식 검색을 BM25 만으로
AGENT_BASE_URL = os.getenv("UGV_AGENT_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
AGENT_TIMEOUT_S = float(os.getenv("UGV_AGENT_TIMEOUT_S", "60"))       # 실제 초 (2026-10-09: 20초는 검색 뒤 판단 호출이 끊겨 60초로)
# 판단 호출의 생각 정도 (Gemini thinkingLevel). 기사 하나 보고 대기·우회를 고르는 일이라 낮게 둔다 —
#   기본값이면 판단 한 번에 수십 초가 걸려 10배속에서 시뮬레이션 수 분이 된다 (2026-10-09 실측 20~64초). 비우면 모델 기본값
AGENT_THINKING = os.getenv("UGV_AGENT_THINKING", "low")
AGENT_MAX_CALLS = int(os.getenv("UGV_AGENT_MAX_CALLS", "30"))          # 서버 1회 실행당 LLM 호출 한도
# WAIT 마감 여유 (시뮬레이션 초): 모델이 준 재개 예정 시각에 이만큼 더 기다린 뒤에야 우회한다 (지침 G1 의 '재개 예정 + 10분').
#   모델이 wait_until 을 재개 예정 시각 그대로 주면 1초 늦게 열려도 우회해 버린다 (2026-10-09 실측: 14:57:00 마감, 14:57:01 해제 → 33분 우회)
AGENT_WAIT_GRACE_S = float(os.getenv("UGV_AGENT_WAIT_GRACE_S", "600"))
AGENT_MAX_WAIT_S = float(os.getenv("UGV_AGENT_MAX_WAIT_S", "2700"))    # WAIT 상한 (시뮬레이션 초, 45분)
AGENT_NEWS = os.getenv("UGV_AGENT_NEWS", "ugv/knowledge")                 # 지식 베이스 폴더 (ugv/road_news.py), 쉼표로 여러 개


def agent_news_paths(root) -> list[str]:
    """도로 AI·뉴스 사이트가 읽는 지식 폴더: UGV_AGENT_NEWS + 시나리오 전용 기사 폴더.
    시나리오 기사는 시나리오 파일 옆 같은 이름 폴더의 news/ 에 둔다 — ugv/scenarios/X.csv ↔ ugv/scenarios/X/news/.
    그래서 시나리오마다 기사 시각이 따로 맞고, 다른 시나리오의 기사가 섞이지 않는다."""
    out = [p if os.path.isabs(p) else os.path.join(root, p) for p in AGENT_NEWS.split(",") if p.strip()]
    if SCENARIO_FILE:
        d = os.path.splitext(SCENARIO_FILE)[0]
        d = d if os.path.isabs(d) else os.path.join(root, d)
        if os.path.isdir(os.path.join(d, "news")) and d not in out:
            out.append(d)
    return out
AGENT_RAG_CACHE = os.getenv("UGV_AGENT_RAG_CACHE", "ugv/.state/rag_cache")   # 조각 임베딩 디스크 캐시 (바뀐 조각만 다시 만든다)
AGENT_RAG_K = int(os.getenv("UGV_AGENT_RAG_K", "3"))                         # 검색 한 번에 돌려줄 문서 수
# 도로 AI 가 지식 베이스를 찾는 웹 API (이 서버의 뉴스 사이트 GET /news/api/search). 서버를 다른 포트로 띄우면 맞춰 준다.
# 비우면 서버 안에서 직접 찾는다. API 가 안 되면 자동으로 서버 안 검색 (기록의 source 에 사유)
AGENT_NEWS_URL = os.getenv("UGV_AGENT_NEWS_URL", "http://127.0.0.1:8100")

# 주행 파라미터 — 실측 보정 필요
CRUISE_SPEED_MPS = 2.0
MISSION_ALT_M = 0.0      # 지상차량. 홈 고도 0 기준 상대 0m
ARM_SETTLE_S = 2.0

# 판단 임계값 — 잠정값
FUEL_RETURN_MARGIN_PCT = 20.0
ROAD_SNAP_M = 50.0          # 이 거리 안이면 해당 도로 위로 간주
NODE_ARRIVE_M = 20.0        # 이 거리 안이면 노드 도착으로 간주
STALE_AFTER_S = 10.0        # 이 시간 넘으면 STALE (주행 중이면 TELEMETRY_LOST 로 task 실패)

# 주행 감시 (server._watch_task) — 잠정값, PX4 rover(2 m/s) 기준
STALL_TIMEOUT_S = float(os.getenv("UGV_STALL_TIMEOUT_S", "60"))   # 이 시뮬레이션 초 동안 (2026-10-03 부터 벽시계 아님 — 4배속이면 벽시계 15초)
STALL_MOVE_M = 10.0          # 이만큼도 못 움직이고 웨이포인트도 안 넘어가면 STALLED
OFF_ROUTE_M = 100.0          # 경로(노드를 이은 선)에서 이보다 벗어나면 OFF_ROUTE
# 추락 판정은 고도 하강 속도로 한다. 강원 지형 월드는 도로를 따라 고도가 수백 m 바뀌므로
# '홈 대비 상대고도 < -5 m' 같은 절대 기준은 정상 주행도 추락으로 잘못 본다.
# 도로 주행 하강은 1 m/s 를 넘기 어렵고(경사 15%, 3 m/s 기준 0.45), 지형을 뚫고 떨어지면 수십 m/s 다.
FALL_RATE_MPS = 8.0          # 시뮬레이션 초당 이보다 빨리 내려가면 추락 (VEHICLE_FAULT)
FAULT_GRACE_S = 5.0          # 출발 직후 이 시간은 차량 이상 판정 안 함 (arm·모드 전환 대기)
FAULT_CONFIRM_S = 3.0        # 차량 이상이 이 시간 이상 계속돼야 확정 (순간 신호 무시)

# 화재 접근 규칙 — 환경변수로 바꿀 수 있다 (코드 수정 없이)
#   기본: 화재에서 가장 가까운 도로 노드 하나만 본다. 거기로 못 가면 거절.
#   UGV_APPROACH_FALLBACK=1: 가장 가까운 노드로 못 가면 APPROACH_MAX_M 안의 다음 노드로 접근
TARGET_SNAP_M = float(os.getenv("UGV_TARGET_SNAP_M", "2000"))      # 가장 가까운 노드가 이보다 멀면 TARGET_UNREACHABLE (루트 config.UGV_TARGET_SNAP_M 과 같은 값)
APPROACH_FALLBACK = os.getenv("UGV_APPROACH_FALLBACK", "0") == "1"
# 목적지 방식 (ugv/road_point.py): node = 목표에서 가장 가까운 도로 노드(기본, 지금까지 동작) /
#   road_point = 목표에서 가장 가까운 도로 위 점에 선다 (교차로 사이 긴 도로 중간 계측용). 요청마다 target_mode 로 바꿀 수 있다
TARGET_MODE = os.getenv("UGV_TARGET_MODE", "node")
APPROACH_MAX_M = float(os.getenv("UGV_APPROACH_MAX_M", "500"))     # fallback 접근 노드의 화재 거리 상한

# 시연용 가속 — 6노드 시연 도로망(graph_data_demo, 총괄 orchestrator_v012 데모)에서만 쓴다.
# 실제 도로망(server.py)은 차량 max_speed_mps × UGV_TIME_SCALE 로 움직인다.
DEMO_SPEED_MPS = 2000.0