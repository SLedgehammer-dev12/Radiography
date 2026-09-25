# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as patches
import numpy as np

class WeldSketchCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        # We set up a modern aesthetic for matplotlib
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Style the plot area
        self.axes.set_aspect('equal')
        self.axes.axis('off')
        self.fig.patch.set_facecolor('#1e1e2e') # Sleek dark mode facecolor by default
        self.axes.set_facecolor('#1e1e2e')

    def draw_setup(self, OD, t, cap, geometry, sfd, lang_obj, is_dark=True,
                   panel_width=None, panel_height=None, overlap_pct=10.0, n_panel=None,
                   safety_radius_m=None):
        self.axes.clear()
        # Remove any previously added metre-scale inset axes
        for ax in list(self.fig.axes):
            if ax is not self.axes:
                self.fig.delaxes(ax)
        
        # Detect background color preference based on theme
        bg_color = '#1e1e2e' if is_dark else '#ffffff'
        text_color = '#ffffff' if is_dark else '#000000'
        pipe_color = '#89b4fa' if is_dark else '#1b5e20'
        weld_color = '#f38ba8' if is_dark else '#d32f2f'
        beam_color = '#f9e2af' if is_dark else '#fbc02d'
        source_color = '#fab387' if is_dark else '#e65100'
        det_color = '#a6e3a1' if is_dark else '#2e7d32'

        self.fig.patch.set_facecolor(bg_color)
        self.axes.set_facecolor(bg_color)

        R = OD / 2.0
        Ri = R - t
        
        # Let's draw the pipe cross-section
        # Outer wall
        outer_circle = patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2, label=lang_obj.get("pipe_wall"))
        self.axes.add_patch(outer_circle)
        # Inner wall
        inner_circle = patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--')
        self.axes.add_patch(inner_circle)

        # Draw Welds (Top and Bottom)
        # Weld cap geometry follows the user-entered cap height (mm), clamped
        # to stay legible within the pipe cross-section drawing.
        try:
            cap_mm = float(cap) if cap is not None else 0.0
        except (TypeError, ValueError):
            cap_mm = 0.0
        if cap_mm > 0.0:
            weld_h = min(cap_mm, R * 0.30)
            weld_w = min(2.5 * cap_mm, R * 0.45)
        else:
            weld_h = R * 0.08
            weld_w = R * 0.18

        # Top weld cap
        top_weld_out = patches.Arc((0, R), weld_w, weld_h, theta1=0, theta2=180, color=weld_color, linewidth=2)
        top_weld_in = patches.Arc((0, Ri), weld_w, weld_h, theta1=180, theta2=360, color=weld_color, linewidth=2)
        self.axes.add_patch(top_weld_out)
        self.axes.add_patch(top_weld_in)
        
        # Bottom weld cap
        bot_weld_out = patches.Arc((0, -R), weld_w, weld_h, theta1=180, theta2=360, color=weld_color, linewidth=2)
        bot_weld_in = patches.Arc((0, -Ri), weld_w, weld_h, theta1=0, theta2=180, color=weld_color, linewidth=2)
        self.axes.add_patch(bot_weld_out)
        self.axes.add_patch(bot_weld_in)

        # Draw Setup details based on Geometry
        if geometry == "swsi":
            # SWSI: Source at center (0,0), detector wrapped around the outside
            # Source
            self.axes.plot(0, 0, marker='*', color=source_color, markersize=12, label=lang_obj.get("source"))
            
            # Detector (full outer circle or bottom arc)
            detector_arc = patches.Arc((0, 0), R*2.08, R*2.08, theta1=180, theta2=360, color=det_color, linewidth=4, label=lang_obj.get("detector"))
            self.axes.add_patch(detector_arc)
            
            # Radiation beam divergence (covers the bottom weld)
            self.axes.plot([0, -R*0.2], [0, -R], color=beam_color, linestyle=':', alpha=0.7)
            self.axes.plot([0, R*0.2], [0, -R], color=beam_color, linestyle=':', alpha=0.7)
            beam_poly = patches.Polygon([[0,0], [-R*0.2, -R], [R*0.2, -R]], facecolor=beam_color, alpha=0.15)
            self.axes.add_patch(beam_poly)
            
        elif geometry == "dwsi":
            # DWSI: Source is outside at (0, sfd - R), detector at bottom (0, -R)
            y_s = sfd - R
            self.axes.plot(0, y_s, marker='o', color=source_color, markersize=10, label=lang_obj.get("source"))
            
            # Detector arc at bottom
            detector_arc = patches.Arc((0, 0), R*2.08, R*2.08, theta1=220, theta2=320, color=det_color, linewidth=4, label=lang_obj.get("detector"))
            self.axes.add_patch(detector_arc)

            # Beam divergence lines from source to detector edges
            det_x1 = R * np.sin(np.radians(-40))
            det_y1 = -R * np.cos(np.radians(-40))
            det_x2 = R * np.sin(np.radians(40))
            det_y2 = -R * np.cos(np.radians(40))

            self.axes.plot([0, det_x1], [y_s, det_y1], color=beam_color, linestyle=':', alpha=0.7)
            self.axes.plot([0, det_x2], [y_s, det_y2], color=beam_color, linestyle=':', alpha=0.7)
            
            beam_poly = patches.Polygon([[0, y_s], [det_x1, det_y1], [det_x2, det_y2]], facecolor=beam_color, alpha=0.15)
            self.axes.add_patch(beam_poly)
            
        elif geometry == "dwdi_elliptic":
            # DWDI Elliptic: Source outside, offset so the weld is projected as
            # an ellipse. Beam angle 10-15 deg -> offset x = SFD * tan(alpha).
            y_s = sfd - R
            angle_deg = 15.0  # typical elliptical projection beam angle
            xs_offset = sfd * np.tan(np.radians(angle_deg))
            # Keep the offset within the drawn pipe region for legibility
            xs_offset = min(xs_offset, R * 0.9)
            self.axes.plot(xs_offset, y_s, marker='o', color=source_color, markersize=10, label=lang_obj.get("source"))

            # Detector at bottom (centered around -xs_offset)
            detector_arc = patches.Arc((-xs_offset*0.5, 0), R*2.08, R*2.08, theta1=200, theta2=340, color=det_color, linewidth=4, label=lang_obj.get("detector"))
            self.axes.add_patch(detector_arc)

            # Show the double wall penetration beam
            det_x1 = R * np.sin(np.radians(-50)) - xs_offset*0.5
            det_y1 = -R * np.cos(np.radians(-50))
            det_x2 = R * np.sin(np.radians(30)) - xs_offset*0.5
            det_y2 = -R * np.cos(np.radians(30))

            self.axes.plot([xs_offset, det_x1], [y_s, det_y1], color=beam_color, linestyle=':', alpha=0.7)
            self.axes.plot([xs_offset, det_x2], [y_s, det_y2], color=beam_color, linestyle=':', alpha=0.7)

            beam_poly = patches.Polygon([[xs_offset, y_s], [det_x1, det_y1], [det_x2, det_y2]], facecolor=beam_color, alpha=0.1)
            self.axes.add_patch(beam_poly)

            # Dimension annotations: source offset and elliptical beam angle
            self.axes.annotate('', xy=(0, y_s), xytext=(xs_offset, y_s),
                               arrowprops=dict(arrowstyle='<->', color=text_color, lw=1))
            self.axes.text(xs_offset / 2.0, y_s + R * 0.18,
                           f"{lang_obj.get('source_offset')}: {xs_offset:.0f} mm",
                           color=text_color, fontsize=8, ha='center')
            self.axes.text(xs_offset + R * 0.08, y_s - R * 0.12,
                           f"{lang_obj.get('beam_angle')} α ≈ {angle_deg:.0f}°",
                           color=text_color, fontsize=8)
            
        elif geometry == "dwdi_super":
            # DWDI Superimposed: Source straight outside, detector straight opposite
            y_s = sfd - R
            self.axes.plot(0, y_s, marker='o', color=source_color, markersize=10, label=lang_obj.get("source"))
            
            # Detector at bottom
            detector_arc = patches.Arc((0, 0), R*2.08, R*2.08, theta1=210, theta2=330, color=det_color, linewidth=4, label=lang_obj.get("detector"))
            self.axes.add_patch(detector_arc)

            # Beam
            det_x1 = R * np.sin(np.radians(-40))
            det_y1 = -R * np.cos(np.radians(-40))
            det_x2 = R * np.sin(np.radians(40))
            det_y2 = -R * np.cos(np.radians(40))

            self.axes.plot([0, det_x1], [y_s, det_y1], color=beam_color, linestyle=':', alpha=0.7)
            self.axes.plot([0, det_x2], [y_s, det_y2], color=beam_color, linestyle=':', alpha=0.7)

            beam_poly = patches.Polygon([[0, y_s], [det_x1, det_y1], [det_x2, det_y2]], facecolor=beam_color, alpha=0.1)
            self.axes.add_patch(beam_poly)

        # Radiation safety perimeter (metre-scale value, drawn scaled to fit)
        ring_r = 0.0
        if safety_radius_m is not None and safety_radius_m > 0.0:
            ring_r = max(R * 1.8, min(safety_radius_m * 0.05, R * 4.0))
            ring = patches.Circle((0, 0), ring_r, color=weld_color, fill=False,
                                  linewidth=1.5, linestyle='--', alpha=0.7)
            self.axes.add_patch(ring)
            self.axes.text(ring_r * 0.7, ring_r * 0.7,
                           f"{lang_obj.get('safety_ring')}: R≈{safety_radius_m:.0f} m",
                           color=text_color, fontsize=7, alpha=0.85)
            # True metre-scale plan view: pipe drawn to real scale (tiny dot)
            # inside the actual safety circle radius.
            ax_m = self.fig.add_axes([0.70, 0.62, 0.27, 0.27])
            ax_m.set_aspect('equal')
            ax_m.set_facecolor(bg_color)
            ax_m.add_patch(patches.Circle((0, 0), safety_radius_m, color=weld_color,
                                          fill=False, linewidth=1.2, linestyle='--'))
            pipe_r_m = max((OD / 2.0) / 1000.0, 0.0005)
            ax_m.add_patch(patches.Circle((0, 0), pipe_r_m, color=pipe_color, fill=False, linewidth=1.2))
            ax_m.plot(0, 0, marker='*', color=source_color, markersize=6)
            ax_m.set_xlim(-safety_radius_m * 1.15, safety_radius_m * 1.15)
            ax_m.set_ylim(-safety_radius_m * 1.15, safety_radius_m * 1.15)
            ax_m.axis('off')
            ax_m.set_title(f"{lang_obj.get('safety_ring')} (m)",
                           color=text_color, fontsize=7)

        # Flat-panel DDA coverage overlay (digital mode, when panel width is provided)
        if panel_width is not None:
            pw = max(10.0, float(panel_width))
            panel_half = pw / 2.0
            y_panel = -R - R * 0.15
            self.axes.plot([-panel_half, panel_half], [y_panel, y_panel],
                           color=det_color, linewidth=6, solid_capstyle='butt',
                           label=lang_obj.get("dda_label"))
            ov = max(10.0, (overlap_pct or 10.0) / 100.0 * pw)
            self.axes.plot([panel_half - ov, panel_half], [y_panel, y_panel],
                           color=weld_color, linewidth=6, solid_capstyle='butt')
            self.axes.text(panel_half - ov / 2.0, y_panel + R * 0.12,
                           f"{lang_obj.get('overlap_short')} {ov:.0f} mm",
                           color=text_color, fontsize=7, ha='center')
            self.axes.text(0, y_panel - R * 0.18,
                           f"DDA {pw:.0f} mm", color=text_color, fontsize=7, ha='center')
            # Extend limits so the panel remains visible
            self.axes.set_xlim(min(-R * 1.5, -panel_half * 1.1),
                               max(R * 1.5, panel_half * 1.1))
            self.axes.set_ylim(-R - R * 0.45, max(R * 1.5, y_s + R * 0.5) if geometry != "swsi" else R * 1.5)

        # Dynamic Zoom & Limits
        padding = R * 1.5 if geometry != "swsi" else R * 0.5
        if panel_width is None:
            self.axes.set_xlim(-R - padding, R + padding)
            self.axes.set_ylim(-R - padding, max(R + padding, sfd - R + padding) if geometry != "swsi" else R + padding)
        if ring_r > 0.0:
            self.axes.set_xlim(min(self.axes.get_xlim()[0], -ring_r * 1.05),
                               max(self.axes.get_xlim()[1], ring_r * 1.05))
            self.axes.set_ylim(min(self.axes.get_ylim()[0], -ring_r * 1.05),
                               max(self.axes.get_ylim()[1], ring_r * 1.05))
        
        # Legend (neat, modern style)
        self.axes.legend(loc='upper right', framealpha=0.1, facecolor=bg_color, edgecolor=text_color, labelcolor=text_color, fontsize=8)
        self.draw()

    def set_theme(self, is_dark):
        bg_color = '#1e1e2e' if is_dark else '#ffffff'
        self.fig.patch.set_facecolor(bg_color)
        self.axes.set_facecolor(bg_color)
        self.draw()

    def save_figure(self, filepath, dpi=150):
        self.fig.savefig(filepath, dpi=dpi, bbox_inches='tight', pad_inches=0.2)

class StandardSchematicCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.axes.set_aspect('equal')
        self.axes.axis('off')
        self.fig.patch.set_facecolor('#1e1e2e')
        self.axes.set_facecolor('#1e1e2e')

    def set_theme(self, is_dark):
        bg_color = '#1e1e2e' if is_dark else '#ffffff'
        self.fig.patch.set_facecolor(bg_color)
        self.axes.set_facecolor(bg_color)
        self.draw()

    def save_figure(self, filepath, dpi=150):
        self.fig.savefig(filepath, dpi=dpi, bbox_inches='tight', pad_inches=0.2)

    def draw_figure(self, fig_name, lang_obj, is_dark=True):
        self.axes.clear()

        bg_color = '#1e1e2e' if is_dark else '#ffffff'
        text_color = '#ffffff' if is_dark else '#000000'
        pipe_color = '#89b4fa' if is_dark else '#1b5e20'
        weld_color = '#f38ba8' if is_dark else '#d32f2f'
        beam_color = '#f9e2af' if is_dark else '#fbc02d'
        source_color = '#fab387' if is_dark else '#e65100'
        det_color = '#a6e3a1' if is_dark else '#2e7d32'

        self.fig.patch.set_facecolor(bg_color)
        self.axes.set_facecolor(bg_color)

        # ISO 17636-2 flexible-detector (a) variants reuse the existing film
        # drawings; only the title is overridden below.
        orig_name = fig_name
        alias = {"fig2": "fig2b", "fig2a": "fig2b", "fig8": "fig8a", "fig5a": "fig5",
                 "fig6a": "fig6", "fig7a": "fig7", "fig13a": "fig13",
                 "fig14a": "fig14"}
        fig_name = alias.get(fig_name, fig_name)

        R = 1.0
        Ri = 0.8
        
        if fig_name == "fig5": # Fig 5: Panoramic
            # Pipe
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            # Panoramic Film all around
            self.axes.add_patch(patches.Circle((0, 0), R*1.08, color=det_color, fill=False, linewidth=3))
            
            # Central Source
            self.axes.plot(0, 0, marker='*', color=source_color, markersize=12)
            self.axes.text(0.1, 0.1, "S (Panoramic)", color=text_color, fontsize=9, fontweight='bold')
            
            # Diverging rays in 4 directions
            for angle in [0, 90, 180, 270]:
                rad = np.radians(angle)
                self.axes.plot([0, R*np.sin(rad)], [0, R*np.cos(rad)], color=beam_color, linestyle=':', alpha=0.8)
            
            # Labels
            self.axes.text(0.2, -0.5, "f = R\nb = t", color=text_color, fontsize=10, bbox=dict(facecolor=bg_color, alpha=0.5))
            self.axes.set_title(lang_obj.get("fig5_title"), color=text_color, fontsize=10)

        elif fig_name == "fig6": # Fig 6: Eccentric Source Inside
            # Pipe
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            
            # Eccentric Source near top
            ys = 0.5
            self.axes.plot(0, ys, marker='*', color=source_color, markersize=10)
            self.axes.text(0.1, ys+0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            
            # Film at bottom
            detector_arc = patches.Arc((0, 0), R*2.08, R*2.08, theta1=220, theta2=320, color=det_color, linewidth=4)
            self.axes.add_patch(detector_arc)
            
            # Beam to bottom
            self.axes.plot([0, R*np.sin(np.radians(-40))], [ys, -R*np.cos(np.radians(-40))], color=beam_color, linestyle=':')
            self.axes.plot([0, R*np.sin(np.radians(40))], [ys, -R*np.cos(np.radians(40))], color=beam_color, linestyle=':')
            
            # Dimension arrows
            # f (source to bottom weld inner)
            self.axes.annotate('', xy=(0, -Ri), xytext=(0, ys), arrowprops=dict(arrowstyle='<->', color=text_color))
            self.axes.text(-0.2, (ys - Ri)/2, "f", color=text_color, fontsize=10, fontweight='bold')
            
            self.axes.set_title(lang_obj.get("fig6_title"), color=text_color, fontsize=10)

        elif fig_name == "fig7": # Fig 7: Source Outside, Film Inside
            # Pipe
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            
            # Source Outside at top
            ys = 1.8
            self.axes.plot(0, ys, marker='o', color=source_color, markersize=10)
            self.axes.text(0.1, ys+0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            
            # Film Inside at bottom
            detector_arc = patches.Arc((0, 0), Ri*2.0, Ri*2.0, theta1=220, theta2=320, color=det_color, linewidth=4)
            self.axes.add_patch(detector_arc)
            
            # Beam
            self.axes.plot([0, R*np.sin(np.radians(-35))], [ys, -Ri*np.cos(np.radians(-35))], color=beam_color, linestyle=':')
            self.axes.plot([0, R*np.sin(np.radians(35))], [ys, -Ri*np.cos(np.radians(35))], color=beam_color, linestyle=':')
            
            # Dimension f & b
            self.axes.annotate('', xy=(0, -Ri), xytext=(0, ys), arrowprops=dict(arrowstyle='<->', color=text_color))
            self.axes.text(-0.2, 0.2, "f", color=text_color, fontsize=10)
            self.axes.text(-0.2, -0.9, "b = t", color=text_color, fontsize=10)
            
            self.axes.set_title(lang_obj.get("fig7_title"), color=text_color, fontsize=10)

        elif fig_name == "fig11": # Fig 11: DWDI Elliptical
            # Pipe
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            
            # Source Outside offset
            xs = 0.4
            ys = 1.8
            self.axes.plot(xs, ys, marker='o', color=source_color, markersize=10)
            self.axes.text(xs+0.1, ys+0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            
            # Flat film below pipe
            self.axes.plot([-1.2, 1.2], [-1.2, -1.2], color=det_color, linewidth=4)
            self.axes.text(0, -1.4, "Film / Detector", color=text_color, fontsize=8, ha='center')
            
            # Beam covering both walls
            self.axes.plot([xs, -1.0], [ys, -1.2], color=beam_color, linestyle=':')
            self.axes.plot([xs, 1.0], [ys, -1.2], color=beam_color, linestyle=':')
            
            # Welds offset
            self.axes.plot(0.2, R, marker='s', color=weld_color, markersize=6)
            self.axes.plot(-0.2, -R, marker='s', color=weld_color, markersize=6)
            
            # Dimension arrows
            self.axes.text(-0.5, 0, "b = OD", color=text_color, fontsize=10)
            self.axes.text(0.6, 0.8, "f", color=text_color, fontsize=10)
            
            self.axes.set_title(lang_obj.get("fig11_title"), color=text_color, fontsize=10)

        elif fig_name == "fig12": # Fig 12: DWDI Superimposed
            # Pipe
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            
            # Source Outside centered
            ys = 1.8
            self.axes.plot(0, ys, marker='o', color=source_color, markersize=10)
            self.axes.text(0.1, ys+0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            
            # Flat film below pipe
            self.axes.plot([-1.2, 1.2], [-1.2, -1.2], color=det_color, linewidth=4)
            
            # Beam
            self.axes.plot([0, -0.9], [ys, -1.2], color=beam_color, linestyle=':')
            self.axes.plot([0, 0.9], [ys, -1.2], color=beam_color, linestyle=':')
            
            # Welds superimposed (both on y-axis)
            self.axes.plot(0, R, marker='s', color=weld_color, markersize=6)
            self.axes.plot(0, -R, marker='s', color=weld_color, markersize=6)
            
            self.axes.set_title(lang_obj.get("fig12_title"), color=text_color, fontsize=10)

        elif fig_name == "fig13": # Fig 13: DWSI
            # Pipe
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            
            # Source Outside centered
            ys = 1.8
            self.axes.plot(0, ys, marker='o', color=source_color, markersize=10)
            self.axes.text(0.1, ys+0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            
            # Detector arc at bottom outside
            detector_arc = patches.Arc((0, 0), R*2.08, R*2.08, theta1=220, theta2=320, color=det_color, linewidth=4)
            self.axes.add_patch(detector_arc)
            
            # Beam evaluating bottom weld
            self.axes.plot([0, R*np.sin(np.radians(-40))], [ys, -R*np.cos(np.radians(-40))], color=beam_color, linestyle=':')
            self.axes.plot([0, R*np.sin(np.radians(40))], [ys, -R*np.cos(np.radians(40))], color=beam_color, linestyle=':')
            
            # Dimension labels
            self.axes.text(-0.6, 0.3, "f = SFD - t", color=text_color, fontsize=9)
            self.axes.text(-0.5, -0.9, "b = t", color=text_color, fontsize=9)
            
            self.axes.set_title(lang_obj.get("fig13_title"), color=text_color, fontsize=10)

        elif fig_name == "fig8b": # Fig 8b: ISO 17636-2 - panoramic central source, curved DDA
            # Pipe
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            # Curved detector wrapped around outer wall
            self.axes.add_patch(patches.Circle((0, 0), R*1.08, color=det_color, fill=False, linewidth=3))
            # Central source
            self.axes.plot(0, 0, marker='*', color=source_color, markersize=12)
            self.axes.text(0.1, 0.1, "S (Panoramic)", color=text_color, fontsize=9, fontweight='bold')
            # Diverging rays
            for angle in [0, 90, 180, 270]:
                rad = np.radians(angle)
                self.axes.plot([0, R*np.sin(rad)], [0, R*np.cos(rad)], color=beam_color, linestyle=':', alpha=0.8)
            self.axes.text(0.2, -0.5, "f = R\nb = t", color=text_color, fontsize=10,
                           bbox=dict(facecolor=bg_color, alpha=0.5))
            self.axes.set_title(lang_obj.get("fig8b_title"), color=text_color, fontsize=10)

        elif fig_name == "fig9b": # Fig 9b: ISO 17636-2 - eccentric source inside, curved DDA
            # Pipe
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            # Eccentric source near top
            ys = 0.5
            self.axes.plot(0, ys, marker='*', color=source_color, markersize=10)
            self.axes.text(0.1, ys+0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            # Curved detector arc at bottom (inside the pipe)
            detector_arc = patches.Arc((0, 0), Ri*2.0, Ri*2.0, theta1=220, theta2=320, color=det_color, linewidth=4)
            self.axes.add_patch(detector_arc)
            # Beam to bottom
            self.axes.plot([0, R*np.sin(np.radians(-40))], [ys, -R*np.cos(np.radians(-40))], color=beam_color, linestyle=':')
            self.axes.plot([0, R*np.sin(np.radians(40))], [ys, -R*np.cos(np.radians(40))], color=beam_color, linestyle=':')
            self.axes.annotate('', xy=(0, -Ri), xytext=(0, ys), arrowprops=dict(arrowstyle='<->', color=text_color))
            self.axes.text(-0.2, (ys - Ri)/2, "f", color=text_color, fontsize=10, fontweight='bold')
            self.axes.set_title(lang_obj.get("fig9b_title"), color=text_color, fontsize=10)

        elif fig_name == "fig10b": # Fig 10b: ISO 17636-2 - DWSI, source outside, curved DDA
            # Pipe
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            # Source outside at top
            ys = 1.8
            self.axes.plot(0, ys, marker='o', color=source_color, markersize=10)
            self.axes.text(0.1, ys+0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            # Curved DDA outside at bottom
            detector_arc = patches.Arc((0, 0), R*2.08, R*2.08, theta1=220, theta2=320, color=det_color, linewidth=4)
            self.axes.add_patch(detector_arc)
            # Beam
            self.axes.plot([0, R*np.sin(np.radians(-40))], [ys, -R*np.cos(np.radians(-40))], color=beam_color, linestyle=':')
            self.axes.plot([0, R*np.sin(np.radians(40))], [ys, -R*np.cos(np.radians(40))], color=beam_color, linestyle=':')
            self.axes.text(-0.6, 0.3, "f = SFD - t", color=text_color, fontsize=9)
            self.axes.text(-0.5, -0.9, "b = t", color=text_color, fontsize=9)
            self.axes.set_title(lang_obj.get("fig10b_title"), color=text_color, fontsize=10)

        elif fig_name == "fig14b": # Fig 14b: ISO 17636-2 - DWDI, curved DDA
            # Pipe
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            # Source outside offset for elliptical projection
            xs = 0.4
            ys = 1.8
            self.axes.plot(xs, ys, marker='o', color=source_color, markersize=10)
            self.axes.text(xs+0.1, ys+0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            # Curved DDA at bottom outside
            detector_arc = patches.Arc((0, 0), R*2.08, R*2.08, theta1=200, theta2=340, color=det_color, linewidth=4)
            self.axes.add_patch(detector_arc)
            # Beam covering both walls
            self.axes.plot([xs, -1.0], [ys, -1.2], color=beam_color, linestyle=':')
            self.axes.plot([xs, 1.0], [ys, -1.2], color=beam_color, linestyle=':')
            # Welds offset
            self.axes.plot(0.2, R, marker='s', color=weld_color, markersize=6)
            self.axes.plot(-0.2, -R, marker='s', color=weld_color, markersize=6)
            self.axes.text(-0.5, 0, "b = OD", color=text_color, fontsize=10)
            self.axes.text(0.6, 0.8, "f", color=text_color, fontsize=10)
            self.axes.set_title(lang_obj.get("fig14b_title"), color=text_color, fontsize=10)

        elif fig_name == "fig2b":  # Fig 2b: SWSI, source outside, planar detector
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            ys = 1.8
            self.axes.plot(0, ys, marker='o', color=source_color, markersize=10)
            self.axes.text(0.1, ys + 0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            # Planar detector tangent below the pipe
            self.axes.plot([-0.9, 0.9], [-1.15, -1.15], color=det_color, linewidth=4)
            self.axes.plot([0, 0], [-R, -1.15], color=det_color, linewidth=1, linestyle='--')
            self.axes.plot([0, -0.9], [ys, -1.15], color=beam_color, linestyle=':')
            self.axes.plot([0, 0.9], [ys, -1.15], color=beam_color, linestyle=':')
            self.axes.plot(0, R, marker='s', color=weld_color, markersize=6)
            self.axes.text(-0.6, 0.4, "f", color=text_color, fontsize=9)
            self.axes.text(-0.7, -1.0, "b = b_ed + b_gap + k·t", color=text_color, fontsize=8)
            self.axes.set_title(lang_obj.get("fig2b_title"), color=text_color, fontsize=10)

        elif fig_name == "fig5b":  # Fig 5b: panoramic central source, planar detector
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            self.axes.plot(0, 0, marker='*', color=source_color, markersize=12)
            self.axes.text(0.1, 0.1, "S (Panoramic)", color=text_color, fontsize=9, fontweight='bold')
            # Planar detector outside, tangent at the bottom
            self.axes.plot([-0.9, 0.9], [-1.25, -1.25], color=det_color, linewidth=4)
            for x in (-0.9, 0.9):
                self.axes.plot([0, x], [0, -1.25], color=beam_color, linestyle=':', alpha=0.8)
            self.axes.text(0.15, -0.55, "f = R\nb = b_ed + b_gap + t", color=text_color, fontsize=9,
                           bbox=dict(facecolor=bg_color, alpha=0.5))
            self.axes.set_title(lang_obj.get("fig5b_title"), color=text_color, fontsize=10)

        elif fig_name == "fig8a":  # Fig 8a: eccentric source inside, flexible detector
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            ys = 0.5
            self.axes.plot(0, ys, marker='*', color=source_color, markersize=10)
            self.axes.text(0.1, ys + 0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            det = patches.Arc((0, 0), R * 2.08, R * 2.08, theta1=220, theta2=320,
                              color=det_color, linewidth=4)
            self.axes.add_patch(det)
            self.axes.plot([0, R * np.sin(np.radians(-40))], [ys, -R * np.cos(np.radians(-40))],
                           color=beam_color, linestyle=':')
            self.axes.plot([0, R * np.sin(np.radians(40))], [ys, -R * np.cos(np.radians(40))],
                           color=beam_color, linestyle=':')
            self.axes.text(-0.6, -0.2, "f", color=text_color, fontsize=9)
            self.axes.text(-0.5, -1.0, "b = t", color=text_color, fontsize=9)
            self.axes.set_title(lang_obj.get("fig8a_title"), color=text_color, fontsize=10)

        elif fig_name == "fig9a":  # Fig 9a: eccentric source near wall, flexible detector
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            ys = 0.75
            self.axes.plot(0, ys, marker='*', color=source_color, markersize=10)
            self.axes.text(0.1, ys + 0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            det = patches.Arc((0, 0), Ri * 2.0, Ri * 2.0, theta1=220, theta2=320,
                              color=det_color, linewidth=4)
            self.axes.add_patch(det)
            self.axes.plot([0, Ri * np.sin(np.radians(-40))], [ys, -Ri * np.cos(np.radians(-40))],
                           color=beam_color, linestyle=':')
            self.axes.plot([0, Ri * np.sin(np.radians(40))], [ys, -Ri * np.cos(np.radians(40))],
                           color=beam_color, linestyle=':')
            self.axes.text(-0.5, -0.1, "f", color=text_color, fontsize=9)
            self.axes.text(-0.4, -0.8, "b = t", color=text_color, fontsize=9)
            self.axes.set_title(lang_obj.get("fig9a_title"), color=text_color, fontsize=10)

        elif fig_name == "fig10a":  # Fig 10a: eccentric source lower, flexible detector
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            ys = 0.2
            self.axes.plot(0, ys, marker='*', color=source_color, markersize=10)
            self.axes.text(0.1, ys + 0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            det = patches.Arc((0, 0), R * 2.08, R * 2.08, theta1=230, theta2=310,
                              color=det_color, linewidth=4)
            self.axes.add_patch(det)
            self.axes.plot([0, R * np.sin(np.radians(-35))], [ys, -R * np.cos(np.radians(-35))],
                           color=beam_color, linestyle=':')
            self.axes.plot([0, R * np.sin(np.radians(35))], [ys, -R * np.cos(np.radians(35))],
                           color=beam_color, linestyle=':')
            self.axes.text(-0.5, -0.3, "f", color=text_color, fontsize=9)
            self.axes.text(-0.4, -1.0, "b = t", color=text_color, fontsize=9)
            self.axes.set_title(lang_obj.get("fig10a_title"), color=text_color, fontsize=10)

        elif fig_name == "fig13b":  # Fig 13b: DWSI, source outside, planar detector
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            ys = 1.8
            self.axes.plot(0, ys, marker='o', color=source_color, markersize=10)
            self.axes.text(0.1, ys + 0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            self.axes.plot([-0.9, 0.9], [-1.15, -1.15], color=det_color, linewidth=4)
            self.axes.plot([0, -0.9], [ys, -1.15], color=beam_color, linestyle=':')
            self.axes.plot([0, 0.9], [ys, -1.15], color=beam_color, linestyle=':')
            self.axes.plot(-0.2, -R, marker='s', color=weld_color, markersize=6)
            self.axes.text(-0.7, 0.3, "f'", color=text_color, fontsize=9)
            self.axes.text(-0.8, -1.0, "b = b_ed + b_gap + k·t", color=text_color, fontsize=8)
            self.axes.set_title(lang_obj.get("fig13b_title"), color=text_color, fontsize=10)

        elif fig_name == "fig14":  # Fig 14 (ISO 17636-1): DWSI, source on the surface
            self.axes.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
            self.axes.add_patch(patches.Circle((0, 0), Ri, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
            self.axes.plot(0, R, marker='o', color=source_color, markersize=10)
            self.axes.text(0.1, R + 0.1, "S", color=text_color, fontsize=9, fontweight='bold')
            det = patches.Arc((0, 0), R * 2.08, R * 2.08, theta1=220, theta2=320,
                              color=det_color, linewidth=4)
            self.axes.add_patch(det)
            self.axes.plot([0, R * np.sin(np.radians(-40))], [R, -R * np.cos(np.radians(-40))],
                           color=beam_color, linestyle=':')
            self.axes.plot([0, R * np.sin(np.radians(40))], [R, -R * np.cos(np.radians(40))],
                           color=beam_color, linestyle=':')
            self.axes.text(-0.6, 0.35, "f'", color=text_color, fontsize=9)
            self.axes.text(-0.5, -0.95, "b = t", color=text_color, fontsize=9)
            self.axes.set_title(lang_obj.get("fig14_title"), color=text_color, fontsize=10)

        # a-variant title override (drawing reused from the film figures)
        if orig_name in ("fig2", "fig2a", "fig8", "fig5a", "fig6a", "fig7a",
                         "fig13a", "fig14a"):
            self.axes.set_title(lang_obj.get(f"{orig_name}_title"), color=text_color, fontsize=10)

        # Uniform Limits
        self.axes.set_xlim(-2.0, 2.0)
        self.axes.set_ylim(-2.0, 2.5)
        self.draw()

