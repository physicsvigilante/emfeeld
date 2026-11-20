"""JEE 3D: rectangular current-loop torque in a prescribed uniform B.

Renderer adapter only. Exact SI physics belongs to rectangular_loop_torque;
immutable drawing data belongs to rectangular_loop_presentation. Every arrow
length and drawn wire thickness is schematic. There is no rotation in time.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .rectangular_loop_torque import (
    RectangularLoopState, lesson_from_bytes, load_lesson, teaching_case,
)
from .rectangular_loop_presentation import prepare
from .output_safety import protect_saved_evidence


def _json(path, obj):
    Path(path).write_text(
        json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8"
    )


def _sha(data):
    return hashlib.sha256(data).hexdigest()


class TorqueLesson:
    """Native 3D static hypotheses; presentation never supplies SI forces."""

    def __init__(self, state: RectangularLoopState, *, off_screen=False,
                 window_size=(1200, 760)):
        if not isinstance(state, RectangularLoopState):
            raise ValueError("requires validated RectangularLoopState")
        if (type(window_size) not in (list, tuple) or len(window_size) != 2
                or any(type(x) is not int for x in window_size)
                or not 840 <= window_size[0] <= 3840
                or not 560 <= window_size[1] <= 2160):
            raise ValueError("window_size must be 840..3840 by 560..2160 pixels")
        import pyvista as pv

        self.pv = pv
        self.initial = self.state = state
        self.reference_length_m = max(state.width_m, state.height_m)
        self.prepared = prepare(state, reference_length_m=self.reference_length_m)
        self.preparation_count = 1
        self.case_label = None
        self.show_values = True
        self.show_forces = True
        self.notice = ""
        self.plot = pv.Plotter(shape=(1, 2), col_weights=(.61, .39), border=False,
                               window_size=window_size, off_screen=off_screen)
        self.plot.subplot(0, 0)
        self.plot.set_background("#ffffff", all_renderers=False)
        self.plot.subplot(0, 1)
        self.plot.set_background("#edf3f8", all_renderers=False)
        # Widgets belong to the right panel: redraw() clears the left mesh
        # renderer and otherwise silently removes interactive sliders.
        self._building = True
        self._info_actor = None
        self._warning_actor = None
        self.angle_slider = self.plot.add_slider_widget(
            lambda value: self._event(lambda: self.set_angle(float(value))),
            (0., 180.), value=state.tilt_deg, title="Positive normal angle (degrees)",
            pointa=(.12, .16), pointb=(.88, .16), title_height=.018,
            interaction_event="end", color="#233f5e",
            slider_width=.020, tube_width=.005)
        self.angle_slider.GetRepresentation().ShowSliderLabelOff()
        self.field_slider = self.plot.add_slider_widget(
            lambda value: self._event(lambda: self.set_field_ratio(float(value))),
            (0., 2.), value=1., title="Signed field / initial strength",
            pointa=(.12, .26), pointb=(.88, .26), title_height=.018,
            interaction_event="end", color="#148e78",
            slider_width=.020, tube_width=.005)
        self.field_slider.GetRepresentation().ShowSliderLabelOff()
        self.plot.subplot(0, 0)
        callbacks = {
            "1": lambda: self.preset("1"), "2": lambda: self.preset("2"),
            "3": lambda: self.preset("3"), "4": lambda: self.preset("4"),
            "5": lambda: self.preset("5"), "6": lambda: self.preset("6"),
            "n": self.reverse_current, "b": self.reverse_field,
            "f": self.toggle_forces, "v": self.toggle_values,
            "0": self.reset
        }
        for key, fn in callbacks.items():
            self.plot.add_key_event(key, lambda callback=fn: self._event(callback))
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

    def _apply(self, new_state, *, case=None, reveal=None):
        if new_state != self.state:
            data = prepare(new_state, reference_length_m=self.reference_length_m)
            self.state = new_state
            self.prepared = data
            self.preparation_count += 1
        self.case_label = case
        if reveal is not None:
            self.show_values = reveal
        self.redraw()

    def set_angle(self, degrees):
        if not math.isfinite(degrees):
            raise ValueError("angle must be finite")
        self._apply(replace(self.state, tilt_deg=degrees))

    def set_field_ratio(self, ratio):
        if not math.isfinite(ratio):
            raise ValueError("field ratio must be finite")
        self._apply(replace(self.state,
                            field_strength_T=self.initial.field_strength_T*ratio))

    def reverse_current(self):
        self._apply(replace(self.state, current_A=-self.state.current_A))

    def reverse_field(self):
        self._apply(replace(self.state,
                            field_strength_T=-self.state.field_strength_T))

    def preset(self, key):
        self._apply(teaching_case(self.initial, key), case=key, reveal=False)

    def toggle_values(self):
        self.show_values = not self.show_values
        self.redraw()

    def toggle_forces(self):
        self.show_forces = not self.show_forces
        self.redraw()

    def reset(self):
        self.show_forces = True
        self._apply(self.initial, case=None, reveal=True)

    def _sync_widgets(self):
        self._building = True
        try:
            self.angle_slider.GetRepresentation().SetValue(self.state.tilt_deg)
            ratio = (self.state.field_strength_T/self.initial.field_strength_T
                     if self.initial.field_strength_T != 0 else 0.)
            # Widget is 0..2; reversed live signed field is explicitly reported
            # numerically, while the slider retains the magnitude within range.
            self.field_slider.GetRepresentation().SetValue(abs(ratio))
        finally:
            self._building = False

    def redraw(self, *, reset_camera=False):
        pv, plot = self.pv, self.plot
        data = self.prepared
        m = data.report
        plot.subplot(0, 0)
        old_camera = None if reset_camera else plot.camera_position
        plot.renderer.clear()
        corners = np.asarray(data.loop_display_xyz)
        plane = pv.PolyData(corners, faces=[4, 0, 1, 2, 3])
        plot.add_mesh(plane, color="#f2cfa0", opacity=.15,
                      reset_camera=False, name="schematic_loop_plane")
        ring = np.vstack((corners, corners[0]))
        plot.add_mesh(pv.lines_from_points(ring, close=False).tube(radius=.032),
                      color="#965f2e", reset_camera=False,
                      name="representative_current_filament")

        def arrow(name, origin, vector, color, shaft=.04, tip=.11):
            magnitude = float(np.linalg.norm(vector))
            if not magnitude:
                return None
            return plot.add_mesh(
                pv.Arrow(start=origin, direction=vector, scale=magnitude,
                         shaft_radius=shaft, tip_radius=tip, tip_length=.26),
                color=color, name=name, reset_camera=False)

        current = np.asarray(data.current_direction_display_xyz)
        self.current_arrow_actor = arrow(
            "signed_loop_current_arrow", (corners[0]+corners[1])/2 - .5*current,
            current, "#dd7336")
        normal = np.asarray(data.positive_normal_display_xyz)
        self.positive_normal_arrow_actor = arrow(
            "fixed_positive_normal_arrow", corners[2]+.1*normal,
            normal, "#316cb3", shaft=.035, tip=.092)
        self.field_arrow_actor = arrow(
            "uniform_external_B_arrow", np.array((1.2, -.35, 0.)),
            data.field_B_direction_display_xyz, "#129c83")
        self.moment_arrow_actor = arrow(
            "signed_magnetic_moment_arrow", (0., 0., 0.),
            data.magnetic_moment_display_xyz, "#ba4b9b")
        self.torque_arrow_actor = arrow(
            "physical_torque_direction_arrow", (0., 0., 0.),
            data.torque_direction_display_xyz, "#7752b2")
        self.force_actors = []
        if self.show_forces:
            for i, (origin, vector) in enumerate(
                    zip(data.side_force_origins_display_xyz,
                        data.side_force_vectors_display_xyz)):
                actor = arrow("segment_force_"+str(i), origin, vector,
                              "#0790af", shaft=.032, tip=.080)
                if actor is not None:
                    self.force_actors.append(actor)
        self.torque_glyph = np.asarray(data.torque_direction_display_xyz).copy()
        self.field_glyph = np.asarray(data.field_B_direction_display_xyz).copy()
        self.moment_glyph = np.asarray(data.magnetic_moment_display_xyz).copy()
        self.normal_glyph = np.asarray(data.positive_normal_display_xyz).copy()
        self.current_glyph = np.asarray(data.current_direction_display_xyz).copy()
        plot.add_text("CURRENT LOOP  |  UNIFORM MAGNETIC FIELD",
                      position="upper_left", font_size=12, color="#19374f")
        plot.add_text(
            "Green: external B    Pink: moment    Purple: torque\n"
            "Cyan: segment forces    Orange: signed current    Blue: fixed +normal\n"
            "All glyph sizes and wire thickness are SCHEMATIC",
            position="lower_left", font_size=9, color="#345368")
        plot.add_axes()
        if old_camera is None:
            plot.camera_position = [(2.8, -3.8, 2.7), (0., 0., 0.), (0., 0., 1.)]
            plot.camera.parallel_projection = True
            plot.camera.parallel_scale = 2.5
        else:
            plot.camera_position = old_camera

        plot.subplot(0, 1)
        if self._info_actor is not None:
            plot.remove_actor(self._info_actor, reset_camera=False)
        if self._warning_actor is not None:
            plot.remove_actor(self._warning_actor, reset_camera=False)
            self._warning_actor = None
        case_names = {
            "1": "NORMAL PARALLEL TO REFERENCE +B",
            "2": "NORMAL PERPENDICULAR TO +B",
            "3": "NORMAL ANTIPARALLEL TO +B",
            "4": "REVERSED CURRENT AT 90 DEG",
            "5": "ZERO CURRENT", "6": "ZERO EXTERNAL FIELD"
        }
        lines = [
            "JEE MAGNETISM 3D | TORQUE",
            "", "One rigid, ideal rectangular loop",
            "Uniform EXTERNAL B, one turn",
            f"Case: {case_names.get(self.case_label, 'CUSTOM')}",
            f"I = {self.state.current_A:.5g} A",
            f"B signed = {self.state.field_strength_T:.5g} T",
            f"Width x height = {self.state.width_m:.4g} x {self.state.height_m:.4g} m",
            f"Positive-normal tilt = {self.state.tilt_deg:.4g} degrees",
            "", "PREDICT BEFORE V REVEAL:"
        ]
        if self.show_values:
            lines.extend((
                f"|magnetic moment| = {float(np.linalg.norm(data.magnetic_moment_A_m2)):.6g} A m^2",
                f"|torque| = {m['torque_magnitude_N_m']:.6g} N m",
                f"U orientation = {m['orientation_potential_J']:.6g} J",
                "Forces add to zero; couple yields torque."
            ))
        else:
            lines.extend((
                "Torque zero at 0 and 180 degrees?",
                "Which alignment is lower energy?",
                "Where is |torque| largest?",
                "Numerical answers are hidden."
            ))
        lines.extend((
            "", "1 aligned   2 perpendicular   3 opposite",
            "4 reverse I   5 I=0   6 B=0",
            "N reverse I   B reverse field",
            "F show/hide forces   V predict/reveal",
            "0 reset   mouse orbit/zoom",
            "Sliders: tilt and signed field magnitude",
            "", "STATIC configurations; no spin in time,",
            "induction, self-field, or material effects."
        ))
        self._info_actor = plot.add_text(
            "\n".join(lines), position="upper_left", font_size=10,
            color="#193f58")
        if self.notice:
            self._warning_actor = plot.add_text(
                self.notice, position="lower_left",
                font_size=9, color="#a94229")
        self._sync_widgets()
        plot.subplot(0, 0)
        plot.render()

    def display_state(self):
        self.plot.subplot(0, 0)
        return {
            "show_values": self.show_values, "show_forces": self.show_forces,
            "case": self.case_label, "notice": self.notice,
            "preparation_count": self.preparation_count,
            "camera_position": [list(x) for x in self.plot.camera_position],
            "window_size": list(self.plot.window_size),
            "angle_slider_deg": self.angle_slider.GetRepresentation().GetValue(),
            "field_slider_magnitude_ratio": self.field_slider.GetRepresentation().GetValue(),
            "current_arrow_present": self.current_arrow_actor is not None,
            "field_arrow_present": self.field_arrow_actor is not None,
            "moment_arrow_present": self.moment_arrow_actor is not None,
            "torque_arrow_present": self.torque_arrow_actor is not None,
            "segment_force_arrow_count": len(self.force_actors),
            "normal_glyph": self.normal_glyph.tolist(),
            "current_glyph": self.current_glyph.tolist(),
            "field_glyph": self.field_glyph.tolist(),
            "moment_glyph": self.moment_glyph.tolist(),
            "torque_glyph": self.torque_glyph.tolist(),
            "reference_length_m": self.reference_length_m,
            "display_glyphs_not_SI_values": True,
            "authored_and_current_states_distinct": self.initial != self.state,
        }


def save_snapshot(authored: RectangularLoopState, destination, *,
                  lesson=None, current_state=None, source_bytes=None):
    """Write new source-bound evidence; reject inconsistent bytes before writes."""
    if not isinstance(authored, RectangularLoopState):
        raise ValueError("requires validated RectangularLoopState")
    protect_saved_evidence(destination, new_directory=True)
    raw = source_bytes if source_bytes is not None else json.dumps(
        authored.to_dict(), sort_keys=True, allow_nan=False).encode("utf-8")
    if lesson_from_bytes(raw) != authored:
        raise ValueError("original JSON source does not match authored physical state")
    if lesson is not None:
        if not isinstance(lesson, TorqueLesson) or lesson.initial != authored:
            raise ValueError("live lesson initial state does not match authored state")
        if current_state is not None and current_state != lesson.state:
            raise ValueError("conflicting current state and live lesson")
        state, data = lesson.state, lesson.prepared
        if data.state != state:
            raise ValueError("prepared physical data do not match live state")
    else:
        state = authored if current_state is None else current_state
        if not isinstance(state, RectangularLoopState):
            raise ValueError("requires validated current RectangularLoopState")
        data = prepare(state)
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=False)
    _json(dest/"started.json", {"completed": False, "lesson": "rectangular_loop_torque_v1"})
    try:
        (dest/"authored-input.json").write_bytes(raw)
        _json(dest/"lesson.json", state.to_dict())
        np.savez_compressed(
            dest/"physical_samples.npz",
            corners_m=data.loop_corners_m,
            side_midpoints_m=data.side_midpoints_m,
            edge_vectors_m=data.edge_vectors_m,
            positive_normal_unit=data.normal_unit,
            external_field_B_T=data.field_B_T,
            magnetic_moment_A_m2=data.magnetic_moment_A_m2,
            physical_torque_N_m=data.torque_N_m,
            segment_forces_N=data.segment_forces_N,
            display_corners=data.loop_display_xyz,
            display_force_vectors=data.side_force_vectors_display_xyz)
        file_names = ("rectangular_loop_torque.py",
                      "rectangular_loop_presentation.py",
                      "rectangular_loop_view.py")
        code = {f: _sha((Path(__file__).parent/f).read_bytes()) for f in file_names}
        report = {
            "model": "ideal_rectangular_current_loop_uniform_B",
            "original_input_sha256": _sha(raw),
            "source_code_sha256": code,
            "authored_state": authored.to_dict(),
            "current_state": state.to_dict(),
            "physics": dict(data.report),
            "display": lesson.display_state() if lesson else {
                "rendered": False, "reference_length_m": data.reference_length_m,
                "display_glyphs_not_SI_values": True},
            "renderer": "PyVista real screenshot" if lesson else "none (headless)"
        }
        _json(dest/"report.json", report)
        if lesson is not None:
            lesson.plot.render()
            lesson.plot.screenshot(str(dest/"view.png"))
        _json(dest/"outcome.json", {"completed": True, "renderer": report["renderer"]})
    except Exception:
        _json(dest/"outcome.json", {"completed": False, "error": "snapshot_failed"})
        raise
    finally:
        hashes = {p.name: _sha(p.read_bytes()) for p in dest.iterdir()
                  if p.is_file() and p.name != "integrity.json"}
        _json(dest/"integrity.json", {"files": hashes})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--case", choices=tuple("123456"))
    dest = parser.add_mutually_exclusive_group()
    dest.add_argument("--headless", type=Path, metavar="NEW_DIR")
    dest.add_argument("--snapshot", type=Path, metavar="NEW_DIR")
    parser.add_argument("--window-size", nargs=2, type=int, default=(1200,760))
    args = parser.parse_args(argv)
    raw = args.input.read_bytes()
    initial = load_lesson(args.input)
    selected = teaching_case(initial, args.case) if args.case else initial
    if args.headless:
        save_snapshot(initial, args.headless, current_state=selected, source_bytes=raw)
        print("Headless SI torque and force report saved to", args.headless)
        return 0
    obj = TorqueLesson(initial, off_screen=bool(args.snapshot),
                       window_size=tuple(args.window_size))
    try:
        if args.case:
            obj.preset(args.case)
        if args.snapshot:
            obj.plot.show(auto_close=False, interactive=False)
            save_snapshot(initial, args.snapshot, lesson=obj, source_bytes=raw)
            print("Real PyVista torque and force screenshot saved to", args.snapshot)
        else:
            obj.plot.show()
    finally:
        obj.plot.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
