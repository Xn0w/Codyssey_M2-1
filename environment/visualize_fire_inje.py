"""동적 2D 산불 시뮬레이션 GIS 시각화 도구. 과거 화제 재현 전용 (전체 지역 & 화재 지역 상세).

2D 공간 지도 상에서 산불 확산, 지형 기복(terrain relief), 식생(vegetation),
도로망(road networks), 119 안전센터를 애니메이션으로 보여주는 로컬 도구.
로컬 환경에서의 시뮬레이션 시각화, 분석 및 테스트 전용.

사용법:
1. 대화형 GUI 창 실행 (화면에 그래프/애니메이션 표시):

    cd environment
    python visualize_fire_inje.py

2. 애니메이션을 GIF 파일로 저장:

    python visualize_fire_inje.py --save images/fire_spread.gif

3. 사용자 정의 시뮬레이션 파라미터 적용:

    python visualize_fire_inje.py --x 14 --y 101 --steps 65 --seed 42

"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Optional

import matplotlib.animation as animation
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import rasterio.warp

# Enable font fallback for Windows
import os
font_path = "C:/Windows/Fonts/malgun.ttf"
if os.path.exists(font_path):
    try:
        import matplotlib.font_manager as fm
        fm.fontManager.addfont(font_path)
        plt.rcParams["font.family"] = "Malgun Gothic"
    except Exception:
        pass
plt.rcParams["font.sans-serif"] = ["Malgun Gothic", "NanumGothic", "DejaVu Sans", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

from src.api import EnvironmentModelAPI
from src.cell import FireState
from src.fire_model import WildfireCAEngine
from src.grid import EnvironmentGrid

# Consistent color constants matching environment/fire-area.png
COLOR_SIMULATION = [87 / 255.0, 148 / 255.0, 238 / 255.0, 0.95]   # #5794EE Blue (시뮬레이션 BURNING)
COLOR_OVERLAP = [134 / 255.0, 71 / 255.0, 169 / 255.0, 0.95]      # #8647A9 Purple: simulation ∩ satellite reference
COLOR_REF = [235 / 255.0, 57 / 255.0, 70 / 255.0, 0.95]           # #EB3946 Red (위성 피해지)
COLOR_WATER = [178 / 255.0, 216 / 255.0, 246 / 255.0, 0.85]       # #B2D8F6 Light Blue (호수)


def create_visualization(
    config_path: str = "config/environment_config.yaml",
    seed: int = 42,
    ignition_x: Optional[int] = None,
    ignition_y: Optional[int] = None,
    steps: int = 30,
    interval: int = 200,
    save_path: Optional[str] = None,
    fps: int = 5,
    show_perimeter: bool = False,
    zoom_window: Optional[tuple[int, int, int, int]] = (0, 65, 75, 122),
) -> None:
    """Run and animate wildfire cellular automaton simulation with synchronized dual panels.

    Left Panel: Full Inje map with updated colors.
    Right Panel: Zoomed-in wildfire spread area synchronized frame-by-frame,
                 matching the visual representation in fire-area.png.

    Parameters
    ----------
    config_path : str
        Path to YAML configuration file.
    seed : int
        Simulation seed for bitwise reproducible execution.
    ignition_x : int, optional
        Initial ignition column index (default: grid center).
    ignition_y : int, optional
        Initial ignition row index (default: grid center).
    steps : int
        Total simulation steps to advance.
    interval : int
        Animation frame delay in milliseconds.
    save_path : str, optional
        File path to save output animation (.gif or .mp4).
    fps : int
        Frame rate for saved animation output.
    show_perimeter : bool
        Whether to display active fire perimeter boundary overlay markers.
    zoom_window : tuple[int, int, int, int], optional
        (xmin, xmax, ymin, ymax) grid coordinates for the right zoomed-in panel.
    """
    cfg_p = Path(config_path)
    if not cfg_p.exists():
        alt_p = Path(__file__).parent / "config" / "environment_config.yaml"
        if alt_p.exists():
            config_path = str(alt_p)
        elif (Path("environment") / config_path).exists():
            config_path = str(Path("environment") / config_path)

    # 1. Instantiate grid, cellular automaton engine, and API wrapper
    grid = EnvironmentGrid(config_path=config_path, seed=seed)
    ca_engine = WildfireCAEngine(grid=grid, config_path=config_path, seed=seed)
    api = EnvironmentModelAPI(grid=grid, ca_engine=ca_engine)

    rows, cols = grid.rows, grid.cols

    # Ignition point resolution priority:
    #   1. Explicit --x / --y grid indices (if provided).
    #   2. Config ignition point in lat/lon (ignition.lat / ignition.lon),
    #      reprojected to grid row/col.
    #   3. Fallback to grid center.
    if ignition_x is None and ignition_y is None:
        try:
            ignited_cell = ca_engine.ignite_from_config()
            ignition_x, ignition_y = ignited_cell.x, ignited_cell.y
            ign_cfg = grid._config.get("ignition", {})
            print(
                f"Ignition from config lat/lon "
                f"({ign_cfg.get('lat')}, {ign_cfg.get('lon')}) "
                f"-> grid (col={ignition_x}, row={ignition_y})"
            )
        except (KeyError, IndexError) as exc:
            ignition_x, ignition_y = cols // 2, rows // 2
            print(
                f"Config ignition point unavailable ({exc}); "
                f"falling back to grid center (col={ignition_x}, row={ignition_y})"
            )
            ca_engine.ignite_at(ignition_x, ignition_y)
    else:
        if ignition_x is None:
            ignition_x = cols // 2
        if ignition_y is None:
            ignition_y = rows // 2
        ca_engine.ignite_at(ignition_x, ignition_y)

    # -------------------------------------------------------------------------
    # Shared GIS Raster Layers Pre-computation
    # -------------------------------------------------------------------------
    # 1. DEM Elevation matrix
    elevation_matrix = np.zeros((rows, cols), dtype=np.float64)
    for cell in grid.cells:
        elevation_matrix[cell.y, cell.x] = cell.elevation

    # 2. Hillshade relief
    hillshade_norm = None
    for hs_candidate in [
        Path("data/processed/hillshade.tif"),
        Path("environment/data/processed/hillshade.tif"),
        Path(__file__).parent / "data/processed/hillshade.tif",
    ]:
        if hs_candidate.exists():
            with rasterio.open(hs_candidate) as ds:
                h_data = ds.read(1).astype(np.float32)
                h_min, h_max = np.nanmin(h_data), np.nanmax(h_data)
                if h_max > h_min:
                    hillshade_norm = (h_data - h_min) / (h_max - h_min)
                else:
                    hillshade_norm = h_data
            break

    # 3. Vegetation / Fuel type overlay
    veg_rgba = np.zeros((rows, cols, 4), dtype=np.float32)
    for cell in grid.cells:
        ft = cell.fuel_type
        if ft == 1:
            veg_rgba[cell.y, cell.x] = [0.45, 0.75, 0.25, 0.22]
        elif ft == 2:
            veg_rgba[cell.y, cell.x] = [0.20, 0.55, 0.15, 0.32]
        elif ft == 3:
            veg_rgba[cell.y, cell.x] = [0.05, 0.35, 0.05, 0.42]

    # 4. Roads overlay
    roads_rgba = np.zeros((rows, cols, 4), dtype=np.float32)
    for roads_candidate in [
        Path("data/processed/roads_raster.tif"),
        Path("environment/data/processed/roads_raster.tif"),
        Path(__file__).parent / "data/processed/roads_raster.tif",
        Path("../data/inje2019/roads/roads_raster_2019.tif"),
    ]:
        if roads_candidate.exists():
            with rasterio.open(roads_candidate) as ds:
                r_data = ds.read(1)
            roads_mask = (r_data == 1)
            roads_rgba[roads_mask] = [0.15, 0.15, 0.18, 0.85]
            break

    # 5. Water mask overlay (consistent light blue matching fire-area.png)
    water_rgba = np.zeros((rows, cols, 4), dtype=np.float32)
    for water_candidate in [
        Path("../data/inje2019/water/inje_2019_water_mask_5186.tif"),
        Path("data/inje2019/water/inje_2019_water_mask_5186.tif"),
        Path(__file__).parent.parent / "data/inje2019/water/inje_2019_water_mask_5186.tif",
    ]:
        if water_candidate.exists():
            with rasterio.open(water_candidate) as ds:
                w_data = ds.read(1)
            water_mask = (w_data == 1)
            water_rgba[water_mask] = COLOR_WATER
            break

    # 6. Satellite reference burn overlay for right panel (matching fire-area.png red)
    ref_rgba = np.zeros((rows, cols, 4), dtype=np.float32)
    reference_mask = np.zeros((rows, cols), dtype=bool)
    for ref_candidate in [
        Path("../data/inje2019/burned_area/inje_2019_burn_reference_binary.tif"),
        Path("data/inje2019/burned_area/inje_2019_burn_reference_binary.tif"),
        Path(__file__).parent.parent / "data/inje2019/burned_area/inje_2019_burn_reference_binary.tif",
    ]:
        if ref_candidate.exists():
            with rasterio.open(ref_candidate) as ds:
                ref_data = ds.read(1)
            reference_mask = (ref_data == 1)
            ref_rgba[reference_mask] = COLOR_REF
            break

    # 7. 119 Safety Centers
    stations = [
        {"name": "Inje 119", "lat": 38.0614106, "lon": 128.1685080},
        {"name": "Girin 119", "lat": 37.9648437, "lon": 128.3184546},
    ]
    station_cols, station_rows, station_names = [], [], []
    for st in stations:
        try:
            xs, ys = rasterio.warp.transform(
                "EPSG:4326", grid.crs, [st["lon"]], [st["lat"]]
            )
            r, c = grid.xy_to_rowcol(xs[0], ys[0])
            station_cols.append(c)
            station_rows.append(r)
            station_names.append(st["name"])
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Initialize Dual Subplots (Side by Side)
    # -------------------------------------------------------------------------
    fig, (ax_full, ax_zoom) = plt.subplots(1, 2, figsize=(12, 6), dpi=100)
    fig.subplots_adjust(left=0.05, right=0.97, top=0.91, bottom=0.08, wspace=0.3)

    # -------------------------
    # LEFT PANEL: Full Inje Map
    # -------------------------
    im_elevation = ax_full.imshow(
        elevation_matrix,
        cmap="gray",
        origin="upper",
        aspect="equal",
        zorder=1,
    )
    cbar = fig.colorbar(im_elevation, ax=ax_full, fraction=0.038, pad=0.03)
    cbar.set_label("Elevation (m)", fontsize=10, fontweight="bold")

    if hillshade_norm is not None:
        ax_full.imshow(
            hillshade_norm,
            cmap="gray",
            alpha=0.35,
            origin="upper",
            aspect="equal",
            zorder=2,
        )

    ax_full.imshow(
        veg_rgba,
        origin="upper",
        aspect="equal",
        interpolation="nearest",
        zorder=3,
    )

    ax_full.imshow(
        roads_rgba,
        origin="upper",
        aspect="equal",
        interpolation="nearest",
        zorder=4,
    )

    if station_cols:
        ax_full.scatter(
            station_cols,
            station_rows,
            marker="^",
            s=95,
            facecolor="#00E5FF",
            edgecolor="white",
            linewidths=1.5,
            zorder=12,
            label="119 Safety Center",
        )
        for c, r, name in zip(station_cols, station_rows, station_names):
            # Place Girin 119 to the left so it doesn't collide with the legend
            offset_x = -3 if "Girin" in name else 3
            ha = "right" if "Girin" in name else "left"
            ax_full.text(
                c + offset_x,
                r - 2,
                name,
                color="white",
                fontsize=8,
                fontweight="bold",
                ha=ha,
                zorder=13,
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    facecolor="#003366",
                    alpha=0.75,
                    edgecolor="#00E5FF",
                ),
            )

    # ------------------------------------
    # RIGHT PANEL: Zoomed-in Wildfire View
    # ------------------------------------
    # Light, low-contrast grayscale relief like the reference image.
    if hillshade_norm is not None:
        ax_zoom.imshow(
            hillshade_norm,
            cmap="gray",
            vmin=-0.35, vmax=1.45,
            origin="upper",
            aspect="equal",
            zorder=1,
        )
    else:
        ax_zoom.imshow(
            elevation_matrix,
            cmap="gray",
            alpha=0.45,
            origin="upper",
            aspect="equal",
            zorder=1,
        )

    # Water body layer on zoom panel
    ax_zoom.imshow(
        water_rgba,
        origin="upper",
        aspect="equal",
        interpolation="nearest",
        zorder=2,
    )

    # Reference burn footprint is combined with simulation in comparison_rgba below.

    # Do not draw the thick road overlay in the zoom view: it obscures
    # the burn-footprint comparison and is absent from the reference image.

    # Set zoom extent focused on wildfire spread area
    if zoom_window:
        zx_min, zx_max, zy_min, zy_max = zoom_window
    else:
        zx_min, zx_max, zy_min, zy_max = 0, 65, 75, 122
    ax_zoom.set_xlim(zx_min - 0.5, zx_max + 0.5)
    ax_zoom.set_ylim(zy_max + 0.5, zy_min - 0.5)  # Inverted Y for upper origin

    # Ignition point marker on zoom panel
    ax_zoom.scatter(
        [ignition_x],
        [ignition_y],
        color="#111122",
        edgecolor="white",
        linewidths=1.5,
        s=75,
        zorder=10,
    )
    ax_zoom.text(
        ignition_x - 1.5,
        ignition_y,
        "발화점",
        fontsize=9.5,
        fontweight="bold",
        color="#111122",
        ha="right",
        va="center",
        zorder=11,
    )

    # -------------------------------------------------------------------------
    # Shared Fire State Matrices & Imshow Artists
    # Full panel: simulation state only (preserve the original full-map layers).
    # Zoom panel: BLUE=simulated footprint only, RED=reference only,
    # PURPLE=intersection. Burned cells remain part of the simulated footprint.
    # The reference is a static FINAL footprint, not a time-resolved observation.
    # -------------------------------------------------------------------------
    fire_rgba = np.zeros((rows, cols, 4), dtype=np.float32)
    comparison_rgba = np.zeros((rows, cols, 4), dtype=np.float32)

    def update_rgba_matrix() -> None:
        simulated_mask = np.zeros((rows, cols), dtype=bool)
        fire_rgba.fill(0.0)
        comparison_rgba.fill(0.0)
        for cell in grid.cells:
            if cell.fire_state in (FireState.BURNING, FireState.BURNED):
                simulated_mask[cell.y, cell.x] = True
                fire_rgba[cell.y, cell.x] = COLOR_SIMULATION
        comparison_rgba[reference_mask & ~simulated_mask] = COLOR_REF
        comparison_rgba[simulated_mask & ~reference_mask] = COLOR_SIMULATION
        comparison_rgba[simulated_mask & reference_mask] = COLOR_OVERLAP

    update_rgba_matrix()

    im_fire_full = ax_full.imshow(
        fire_rgba, origin="upper", aspect="equal", interpolation="nearest", zorder=5,
    )
    im_fire_zoom = ax_zoom.imshow(
        comparison_rgba, origin="upper", aspect="equal", interpolation="nearest", zorder=5,
    )

    # Active Fire Perimeter Overlays
    perimeter_cells = api.get_fire_perimeter() if show_perimeter else []
    px = [p["x"] for p in perimeter_cells]
    py = [p["y"] for p in perimeter_cells]

    scat_perim_full = ax_full.scatter(px, py, s=1, facecolors="none", edgecolors="#FFE066", linewidths=0.1, alpha=0.7, zorder=6) #label="Fire Perimeter"

    # Keep the reference-style zoom free of yellow perimeter markers.
    scat_perim_zoom = None

    # Wind Vector Indicator Arrow on Full Map
    spread_info = api.get_spread_direction()
    wind_dx = spread_info["dx"]
    wind_dy = spread_info["dy"]

    wind_x = cols * 0.92
    wind_y = rows * 0.08
    quiver_wind = ax_full.quiver(
        [wind_x],
        [wind_y],
        [wind_dx],
        [-wind_dy],
        color="#00FFFF",
        scale=12,
        width=0.008,
        headwidth=4,
        headlength=5,
        zorder=14,
    )

    # -------------------------------------------------------------------------
    # Legends
    # -------------------------------------------------------------------------
    # Left Panel Legend (Full view)
    patch_burning = mpatches.Patch(color="#5794EE", label="시뮬레이션 (BURNING #5794EE)")
    patch_burned = mpatches.Patch(color="#8647A9", label="겹침 (시뮬레이션 ∩ 위성 피해지)")
    marker_station = plt.Line2D(
        [0],
        [0],
        marker="^",
        color="w",
        markerfacecolor="#00E5FF",
        markeredgecolor="w",
        markersize=8,
        label="119 Safety Center",
    )
    patch_road = mpatches.Patch(color="#26262E", label="Road Network")
    patch_forest = mpatches.Patch(color="#0D590D", label="Dense Forest (Fuel 3)")
    patch_hillshade = mpatches.Patch(color="#888888", label="Hillshade Relief")

    legend_handles_full = [
        patch_burning,
        marker_station,
        patch_road,
        patch_forest,
        patch_hillshade,
    ]
    if show_perimeter:
        line_perim = plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markeredgecolor="#FFE066",
            markersize=1,
            label="Fire Perimeter",
        )
        legend_handles_full.append(line_perim)

    ax_full.legend(
        handles=legend_handles_full,
        loc="lower right",
        framealpha=0.85,
        fontsize=5,
    )

    # Right Panel Legend (Zoomed view matching fire-area.png)
    legend_handles_zoom = [
        mpatches.Patch(color="#5794EE", label="시뮬레이션"),
        mpatches.Patch(color="#EB3946", label="위성 피해지"),
        mpatches.Patch(color="#8647A9", label="겹침 (시뮬레이션 ∩ 위성 피해지)"),
        mpatches.Patch(color="#B2D8F6", label="호수"),
    ]
    ax_zoom.legend(
        handles=legend_handles_zoom,
        loc="upper left",
        framealpha=0.90,
        fontsize=6,
    )

    ax_full.set_xlabel("Grid Column (X)", fontsize=10)
    ax_full.set_ylabel("Grid Row (Y)", fontsize=10)
    ax_zoom.set_xlabel("Grid Column (X) [Zoomed]", fontsize=10)
    ax_zoom.set_ylabel("Grid Row (Y) [Zoomed]", fontsize=10)

    # Real-Time HUD Update
    def update_hud(step_num: int, current_spread: dict) -> None:
        env_state = api.get_environment_state()
        b_cnt = env_state["burning_cell_count"]
        bd_cnt = env_state["burned_cell_count"]
        ver = env_state["state_version"]
        w_spd = current_spread["wind_speed_ms"]
        w_deg = current_spread["wind_direction_deg"]
        cardinal = current_spread["primary_cardinal"]

        time_str = ""
        if hasattr(ca_engine, "current_simulation_time"):
            time_str = f" | {ca_engine.current_simulation_time.strftime('%Y-%m-%d %H:%M')}"

        title_full = (
            f"전체 인제군 영역 | Step {step_num}/{steps}{time_str} (v{ver})\n"
            f"Burning: {b_cnt} | Burned: {bd_cnt} | Wind: {w_spd:.1f} m/s ({w_deg:.1f}°, {cardinal})"
        )
        ax_full.set_title(title_full, fontsize=10.5, fontweight="bold", pad=8)

        title_zoom = (
            f"산불 확산 영역 상세\n"
            f"발화점: ({ignition_x}, {ignition_y}) | 활성 화선 둘레: {len(api.get_fire_perimeter())} cells"
        )
        ax_zoom.set_title(title_zoom, fontsize=10.5, fontweight="bold", pad=8)

    update_hud(0, spread_info)

    # Synchronized Animation Frame Update
    def animate(frame: int) -> None:
        if frame > 0:
            api.step()
            update_rgba_matrix()

        # Update fire RGBA on both panels synchronously
        im_fire_full.set_data(fire_rgba)
        im_fire_zoom.set_data(comparison_rgba)

        if show_perimeter:
            perim = api.get_fire_perimeter()
            if perim:
                pts = np.column_stack([[p["x"] for p in perim], [p["y"] for p in perim]])
                scat_perim_full.set_offsets(pts)
                if scat_perim_zoom is not None:
                    scat_perim_zoom.set_offsets(pts)
            else:
                scat_perim_full.set_offsets(np.empty((0, 2)))
                if scat_perim_zoom is not None:
                    scat_perim_zoom.set_offsets(np.empty((0, 2)))

        curr_spread = api.get_spread_direction()
        quiver_wind.set_UVC([curr_spread["dx"]], [-curr_spread["dy"]])
        update_hud(frame, curr_spread)

    anim = animation.FuncAnimation(
        fig,
        animate,
        frames=steps + 1,
        interval=interval,
        repeat=False,
    )

    class KeyColorPreservingPillowWriter(animation.PillowWriter):
        """Pillow GIF writer that preserves key domain colors in the palette."""

        def finish(self):
            from PIL import Image

            key_colors = [
                [87, 148, 238],    # #5794EE Blue (시뮬레이션 BURNING)
                [134, 71, 169],   # #8647A9 Purple (연소 완료 BURNED)
                [235, 57, 70],    # #EB3946 Red (위성 피해지)
                [178, 216, 246],  # #B2D8F6 Light Blue (호수)
                [0, 229, 255],    # #00E5FF Cyan (119 안전센터)
                [255, 224, 102],  # #FFE066 Yellow (화선 경계)
                [0, 0, 0],        # Black
                [255, 255, 255],  # White
            ]

            processed_frames = []
            for im in self._frames:
                rgb_im = im.convert("RGB") if im.mode != "RGB" else im
                # Base quantize with mediancut leaving space for domain key colors
                q_base = rgb_im.quantize(colors=248, method=Image.Quantize.MEDIANCUT)
                pal = q_base.getpalette()[: 248 * 3]
                for kc in key_colors:
                    pal.extend(kc)
                pal_img = Image.new("P", (1, 1))
                pal_img.putpalette(pal + [0] * (768 - len(pal)))
                q_frame = rgb_im.quantize(palette=pal_img, dither=Image.Dither.NONE)
                processed_frames.append(q_frame)

            processed_frames[0].save(
                self.outfile,
                save_all=True,
                append_images=processed_frames[1:],
                duration=int(1000 / self.fps),
                loop=0,
            )

    if save_path:
        out_path = Path(save_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Saving synchronized dual animation to {out_path} (fps={fps})...")
        if out_path.suffix.lower() == ".gif":
            writer = KeyColorPreservingPillowWriter(fps=fps)
            anim.save(str(out_path), writer=writer)
        else:
            anim.save(str(out_path), fps=fps)
        print(f"Saved integrated dual-panel visualization successfully to {out_path}")
        plt.close(fig)
    else:
        plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dynamic 2D Wildfire Simulation Integrated GIS Visualization Tool"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/environment_config.yaml",
        help="Path to YAML configuration file (default: config/environment_config.yaml)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Simulation seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--x",
        type=int,
        default=None,
        help="Initial ignition column index (default: grid center)",
    )
    parser.add_argument(
        "--y",
        type=int,
        default=None,
        help="Initial ignition row index (default: grid center)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=30,
        help="Total simulation steps to run (default: 30)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=200,
        help="Animation frame delay in milliseconds (default: 200)",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Output file path to save animation (e.g. fire_expansion.gif)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=5,
        help="Frame rate for saved animation (default: 5)",
    )
    parser.add_argument(
        "--hide-perimeter",
        action="store_true",
        help="Hide active fire perimeter boundary overlay markers for unobstructed cell color visibility",
    )

    args = parser.parse_args()

    create_visualization(
        config_path=args.config,
        seed=args.seed,
        ignition_x=args.x,
        ignition_y=args.y,
        steps=args.steps,
        interval=args.interval,
        save_path=args.save,
        fps=args.fps,
        show_perimeter=not args.hide_perimeter,
    )


if __name__ == "__main__":
    main()
