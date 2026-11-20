"""Native PyVista lesson: an ideal circular current loop, field on its axis only.

No off-axis Biot-Savart solution. Visual tubes, arrows, and disk are schematic.
Physics is prepared in circular_loop_magnetism / circular_loop_presentation.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .circular_loop_magnetism import CircularLoopState, lesson_from_bytes, load_lesson, teaching_case
from .circular_loop_presentation import prepare
from .output_safety import protect_saved_evidence


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n",
                          encoding="utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class CircularLoopLesson:
    """Physical mutations prepare atomically; reveal/orbit reuse physical data."""

    def __init__(self, state: CircularLoopState, *, off_screen=False,
                 window_size=(1200, 760)):
        if not isinstance(state, CircularLoopState):
            raise ValueError("requires validated CircularLoopState")
        import pyvista as pv
        self.pv = pv
        self.initial = self.state = state
        self.prepared = prepare(state, display_reference_radius_m=state.radius_m)
        self.preparation_count = 1
        self.show_values = True
        self.case_label = None
        self.notice = ""
        self.plot = pv.Plotter(shape=(1, 2), col_weights=(.62, .38),
                               border=False, window_size=window_size,
                               off_screen=off_screen)
        self.plot.subplot(0, 0)
        self.plot.set_background("#ffffff", all_renderers=False)
        self.plot.subplot(0, 1)
        self.plot.set_background("#eef4f8", all_renderers=False)
        # Keep both VTK slider widgets in the information pane. Redraw clears
        # the 3D renderer, so attaching controls there silently removes them
        # from real screenshots and makes them unusable after first redraw.
        self._building = True
        self._info_actor = None
        self._warning_actor = None
        self.radius_slider = self.plot.add_slider_widget(
            lambda value: self._event(
                lambda: self.change_radius_ratio(float(value))),
            (.5, 2.0), value=1.0, title="Loop radius / initial R",
            pointa=(.12, .13), pointb=(.88, .13), title_height=.018,
            interaction_event="end", color="#253b54",
            slider_width=.020, tube_width=.005)
        self.radius_slider.GetRepresentation().ShowSliderLabelOff()
        # A model can start at any bounded axial position. Honour the initial
        # z even if it lies beyond the most useful -2R..2R visual window.
        self.z_slider_range = max(2.0, abs(state.probe_z_m/state.radius_m))
        self.z_slider = self.plot.add_slider_widget(
            lambda value: self._event(
                lambda: self.change_probe_ratio(float(value))),
            (-self.z_slider_range, self.z_slider_range),
            value=state.probe_z_m/state.radius_m, title="Probe z / initial R",
            pointa=(.12, .23), pointb=(.88, .23), title_height=.018,
            interaction_event="end", color="#147969",
            slider_width=.020, tube_width=.005)
        self.z_slider.GetRepresentation().ShowSliderLabelOff()
        keys = {"1": lambda: self.preset("1"),
                "2": lambda: self.preset("2"),
                "3": lambda: self.preset("3"),
                "n": self.reverse_current,
                "k": self.zero_current,
                "p": self.positive_current,
                "v": self.toggle_values,
                "0": self.reset}
        for key, callback in keys.items():
            self.plot.add_key_event(key, lambda fn=callback: self._event(fn))
        self._building = False
        self.redraw(reset_camera=True)

    def _event(self, callback):
        if self._building:
            return
        self.notice = ""
        try:
            callback()
        except ValueError as exc:
            self.notice = "Control refused: " + str(exc)
            self.redraw()

    def _apply(self, state, *, case=None, reveal=None):
        if state != self.state:
            prepared = prepare(state, display_reference_radius_m=self.initial.radius_m)
            self.state = state
            self.prepared = prepared
            self.preparation_count += 1
        self.case_label = case
        if reveal is not None:
            self.show_values = reveal
        self.redraw()

    def change_radius_ratio(self, ratio):
        if not math.isfinite(ratio):
            raise ValueError("radius ratio must be finite")
        self._apply(replace(self.state, radius_m=self.initial.radius_m*ratio))

    def change_probe_ratio(self, ratio):
        if not math.isfinite(ratio):
            raise ValueError("probe ratio must be finite")
        self._apply(replace(self.state, probe_z_m=self.initial.radius_m*ratio))

    def reverse_current(self):
        self._apply(replace(self.state, current_A=-self.state.current_A))

    def zero_current(self):
        self._apply(replace(self.state, current_A=0.0))

    def positive_current(self):
        if self.initial.current_A == 0:
            raise ValueError("authored initial current is zero; no magnitude to restore")
        self._apply(replace(self.state, current_A=abs(self.initial.current_A)))

    def preset(self, key):
        self._apply(teaching_case(self.initial, key), case=key, reveal=False)

    def toggle_values(self):
        self.show_values = not self.show_values
        self.redraw()

    def reset(self):
        self._apply(self.initial, case=None, reveal=True)

    def _sync_sliders(self):
        self._building = True
        try:
            self.radius_slider.GetRepresentation().SetValue(
                self.state.radius_m/self.initial.radius_m)
            self.z_slider.GetRepresentation().SetValue(
                self.state.probe_z_m/self.initial.radius_m)
        finally:
            self._building = False

    def redraw(self, *, reset_camera=False):
        pv, plot = self.pv, self.plot
        presentation = self.prepared
        report = presentation.report
        u = np.asarray(self.state.normal_direction)
        plot.subplot(0, 0)
        previous_camera = None if reset_camera else plot.camera_position
        plot.renderer.clear()

        ring = np.asarray(presentation.loop_display_xyz)
        # A thin translucent disk makes the plane apparent in 3D; none of its
        # mesh triangles are used to calculate the magnetic field.
        n = len(ring)
        faces = np.asarray([[3, n, i, (i+1) % n] for i in range(n)],
                           dtype=np.int64).ravel()
        disk = pv.PolyData(np.vstack((ring, np.zeros((1, 3)))), faces)
        plot.add_mesh(disk, color="#c7e4ee", opacity=.20,
                      reset_camera=False, name="schematic_loop_plane")
        plot.add_mesh(pv.lines_from_points(np.vstack((ring, ring[0])), close=False)
                      .tube(radius=.035), color="#b67e32",
                      reset_camera=False, name="schematic_current_filament")
        plot.add_mesh(pv.Line(-2.5*u, 2.5*u), color="#849bb0",
                      line_width=2, reset_camera=False, name="axis_guide")

        # Blue is a fixed positive normal, NOT B. An offset separates it from
        # the green field vector, particularly when current reverses.
        blue_origin = 1.35*ring[0]
        self.positive_normal_arrow_direction = u.copy()
        self.positive_normal_arrow_actor = plot.add_mesh(
            pv.Arrow(start=blue_origin, direction=u, scale=.62,
                     shaft_radius=.045, tip_radius=.115, tip_length=.25),
            color="#276fba", reset_camera=False, name="positive_normal_arrow")

        # Orange is actual signed current circulation on the loop.
        current_vec = np.asarray(presentation.current_arrow_display_xyz)
        self.current_arrow_direction = current_vec.copy()
        self.current_arrow_actor = None
        if np.linalg.norm(current_vec) > 0:
            self.current_arrow_actor = plot.add_mesh(
                pv.Arrow(start=ring[0]-.5*current_vec,
                         direction=current_vec, scale=float(np.linalg.norm(current_vec)),
                         shaft_radius=.048, tip_radius=.125, tip_length=.28),
                color="#e16d30", reset_camera=False, name="signed_current_arrow")

        # Green directions come only from prepared physical SI field data.
        B_arrow = np.asarray(presentation.field_arrow_display_xyz)
        self.field_arrow_direction = B_arrow.copy()
        self.field_arrow_actor = None
        self.probe_field_arrow_actor = None
        self.probe_visible = abs(self.state.probe_z_m/self.initial.radius_m) <= 2.3
        if np.linalg.norm(B_arrow) > 0:
            self.field_arrow_actor = plot.add_mesh(
                pv.Arrow(start=(0., 0., 0.), direction=B_arrow,
                         scale=float(np.linalg.norm(B_arrow)),
                         shaft_radius=.048, tip_radius=.125, tip_length=.29),
                color="#079d84", name="centre_B_arrow", reset_camera=False)
        if self.probe_visible:
            point = np.asarray(presentation.probe_display_xyz)
            if self.state.probe_z_m != 0.0:
                plot.add_mesh(pv.Sphere(radius=.065, center=point),
                              color="#654da6", reset_camera=False,
                              name="axial_probe_marker")
                if np.linalg.norm(B_arrow) > 0:
                    self.probe_field_arrow_actor = plot.add_mesh(
                        pv.Arrow(start=point, direction=B_arrow,
                                 scale=float(np.linalg.norm(B_arrow)),
                                 shaft_radius=.042, tip_radius=.115, tip_length=.28),
                        color="#079d84", reset_camera=False,
                        name="axial_probe_B_arrow")

        plot.add_text("MAGNETIC FIELD  |  CIRCULAR CURRENT LOOP",
                      position="upper_left", font_size=12, color="#15374f")
        plot.add_text(
            "Orange: signed current   |   Green: B direction   |   Blue: fixed +normal\n"
            "Purple: axial probe   |   Display glyphs/thickness schematic, not SI magnitudes",
            position="lower_left", font_size=9, color="#345368")
        plot.add_axes()
        if previous_camera is None:
            plot.camera_position = [(3.6, -4.5, 3.5), (0., 0., 0.), (0., 0., 1.)]
            plot.camera.parallel_projection = True
            plot.camera.parallel_scale = 3.35
        else:
            plot.camera_position = previous_camera

        plot.subplot(0, 1)
        if self._info_actor is not None:
            plot.remove_actor(self._info_actor, reset_camera=False)
        if self._warning_actor is not None:
            plot.remove_actor(self._warning_actor, reset_camera=False)
            self._warning_actor = None
        names = {"1": "POSITIVE CURRENT AT CENTRE",
                 "2": "REVERSED CURRENT AT CENTRE",
                 "3": "DOUBLE RADIUS AT CENTRE"}
        case = names.get(self.case_label, "CUSTOM / AXIAL PROBE")
        lines = [
            "JEE MAGNETOSTATICS 3D  |  LOOP", "",
            "Ideal thin circular filament, vacuum",
            "Exactly on-axis field ONLY",
            f"Case: {case}",
            f"I = {self.state.current_A:.6g} A",
            f"R = {self.state.radius_m:.6g} m",
            f"Axis probe z = {self.state.probe_z_m:.6g} m",
            "", "PREDICT BEFORE REVEAL (V):"
        ]
        if self.show_values:
            lines.extend((
                f"Signed B at centre = {report['centre_signed_B_T']:.6g} T",
                f"Signed B at z = {report['probe_signed_B_T']:.6g} T",
                "Sign is along the fixed positive normal",
            ))
        else:
            lines.extend((
                "Does reversing I reverse B?",
                "At centre, what if R doubles?",
                "Does B reverse when z changes sign?",
                "Numerical answers hidden.",
            ))
        lines.extend((
            "", "1: centre    2: reverse at centre",
            "3: R x 2     N: reverse live I",
            "K: zero I    P: positive live I",
            "V: predict/reveal    0: reset",
            "Sliders: radius and axial position",
            "Mouse: orbit/zoom",
            "",
            "B(z) exact ONLY along the loop axis.",
            "Off-axis B, induction, coils and",
            "magnetic force are not simulated.",
        ))
        if not self.probe_visible:
            lines.append("Probe beyond displayed axis (SI result valid).")
        self._info_actor = plot.add_text("\n".join(lines), position="upper_left",
                                          font_size=10, color="#193f58")
        if self.notice:
            self._warning_actor = plot.add_text(
                self.notice, position="lower_left", font_size=9, color="#af3b28")
        self._sync_sliders()
        plot.subplot(0, 0)
        plot.render()

    def display_state(self):
        self.plot.subplot(0, 0)
        return {
            "show_values": self.show_values, "case": self.case_label,
            "notice": self.notice, "preparation_count": self.preparation_count,
            "camera_position": [list(v) for v in self.plot.camera_position],
            "window_size": list(self.plot.window_size),
            "radius_slider_value": self.radius_slider.GetRepresentation().GetValue(),
            "probe_slider_value": self.z_slider.GetRepresentation().GetValue(),
            "probe_visible": self.probe_visible,
            "display_reference_radius_m": float(
                self.prepared.display_reference_radius_m),
            "rendered_loop_radius_initial_R_units": float(
                self.prepared.loop_radius_display_reference_units),
            "positive_normal_arrow_direction": self.positive_normal_arrow_direction.tolist(),
            "current_arrow_direction": self.current_arrow_direction.tolist(),
            "field_arrow_direction": self.field_arrow_direction.tolist(),
            "current_arrow_present": self.current_arrow_actor is not None,
            "centre_B_arrow_present": self.field_arrow_actor is not None,
            "probe_B_arrow_present": self.probe_field_arrow_actor is not None,
            "schematic_arrow_lengths_not_SI_field_magnitudes": True,
            "original_and_current_states_distinct": self.initial != self.state,
        }


def save_snapshot(authored: CircularLoopState, destination, *, lesson=None,
                  current_state=None, source_bytes=None):
    """Save new source-bound physical data and optional real PyVista screenshot."""
    if not isinstance(authored, CircularLoopState):
        raise ValueError("requires authored CircularLoopState")
    protect_saved_evidence(destination, new_directory=True)
    # Validate the original source BEFORE making even the started.json record.
    # A correct hash of unrelated bytes is not an authentic source/state link.
    raw = source_bytes if source_bytes is not None else (
        json.dumps(authored.to_dict(), sort_keys=True, allow_nan=False).encode("utf-8"))
    parsed_authored = lesson_from_bytes(raw)
    if parsed_authored != authored:
        raise ValueError("source bytes do not match the authored circular-loop state")
    if lesson is not None:
        if not isinstance(lesson, CircularLoopLesson) or lesson.initial != authored:
            raise ValueError("lesson initial state does not match authored circular-loop state")
        if current_state is not None and current_state != lesson.state:
            raise ValueError("explicit current_state conflicts with live lesson state")
        state, data = lesson.state, lesson.prepared
        if data.state != state:
            raise ValueError("prepared lesson data do not match current physical state")
    else:
        state = authored if current_state is None else current_state
        if not isinstance(state, CircularLoopState):
            raise ValueError("requires validated current CircularLoopState")
        data = prepare(state)
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=False)
    _write_json(root/"started.json", {"completed": False, "lesson": "circular_loop_axis_v1"})
    try:
        (root/"authored-input.json").write_bytes(raw)
        _write_json(root/"lesson.json", state.to_dict())
        np.savez_compressed(
            root/"axis_samples.npz", loop_positions_m=data.loop_positions_m,
            positive_current_tangent=data.positive_current_tangent,
            field_centre_T=data.field_centre_T, field_probe_T=data.field_probe_T,
            loop_display_xyz=data.loop_display_xyz,
            current_arrow_display_xyz=data.current_arrow_display_xyz,
            field_arrow_display_xyz=data.field_arrow_display_xyz,
            probe_display_xyz=data.probe_display_xyz)
        files = ("circular_loop_magnetism.py",
                 "circular_loop_presentation.py", "circular_loop_view.py")
        hashes = {f: _sha((Path(__file__).parent/f).read_bytes()) for f in files}
        report = {
            "model": "ideal_circular_current_loop_axis",
            "original_input_sha256": _sha(raw), "source_code_sha256": hashes,
            "authored_state": authored.to_dict(),
            "current_state": state.to_dict(), "physics": dict(data.report),
            "display": lesson.display_state() if lesson is not None else {
                "rendered": False, "schematic": True,
                "display_reference_radius_m": data.display_reference_radius_m,
                "rendered_loop_radius_initial_R_units": data.loop_radius_display_reference_units},
            "renderer": "PyVista real screenshot" if lesson is not None else "none (headless)",
        }
        _write_json(root/"report.json", report)
        if lesson is not None:
            lesson.plot.render()
            lesson.plot.screenshot(str(root/"view.png"))
        _write_json(root/"outcome.json", {"completed": True,
                                         "renderer": report["renderer"]})
    except Exception:
        _write_json(root/"outcome.json", {"completed": False, "error": "snapshot_failed"})
        raise
    finally:
        hashes = {p.name: _sha(p.read_bytes()) for p in root.iterdir()
                  if p.is_file() and p.name != "integrity.json"}
        _write_json(root/"integrity.json", {"files": hashes})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--case", choices=("1", "2", "3"))
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--snapshot", type=Path, metavar="NEW_DIR")
    output.add_argument("--headless", type=Path, metavar="NEW_DIR")
    parser.add_argument("--window-size", nargs=2, type=int, default=[1200, 760])
    args = parser.parse_args(argv)
    raw = args.input.read_bytes()
    original = load_lesson(args.input)
    current = teaching_case(original, args.case) if args.case else original
    if args.headless:
        save_snapshot(original, args.headless, current_state=current, source_bytes=raw)
        print("Headless circular-loop SI report saved to", args.headless)
        return 0
    view = CircularLoopLesson(original, off_screen=bool(args.snapshot),
                              window_size=tuple(args.window_size))
    if args.case:
        view.preset(args.case)
    try:
        if args.snapshot:
            view.plot.show(auto_close=False, interactive=False)
            save_snapshot(original, args.snapshot, lesson=view, source_bytes=raw)
            print("Real circular-loop PyVista screenshot and receipt saved to", args.snapshot)
        else:
            view.plot.show()
    finally:
        view.plot.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
