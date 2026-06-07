# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QWidget, QVBoxLayout
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
        
        # Style the plot area
        self.axes.set_aspect('equal')
        self.axes.axis('off')
        self.fig.patch.set_facecolor('#1e1e2e') # Sleek dark mode facecolor by default
        self.axes.set_facecolor('#1e1e2e')

    def draw_setup(self, OD, t, cap, geometry, sfd, lang_obj):
        self.axes.clear()
        
        # Detect background color preference based on theme
        # We can dynamically style with dark/light themes
        is_dark = True # default
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
        # Top weld cap
        top_weld_out = patches.Arc((0, R), R*0.2, R*0.1, theta1=0, theta2=180, color=weld_color, linewidth=2)
        top_weld_in = patches.Arc((0, Ri), R*0.2, R*0.1, theta1=180, theta2=360, color=weld_color, linewidth=2)
        self.axes.add_patch(top_weld_out)
        self.axes.add_patch(top_weld_in)
        
        # Bottom weld cap
        bot_weld_out = patches.Arc((0, -R), R*0.2, R*0.1, theta1=180, theta2=360, color=weld_color, linewidth=2)
        bot_weld_in = patches.Arc((0, -Ri), R*0.2, R*0.1, theta1=0, theta2=180, color=weld_color, linewidth=2)
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
            # DWDI Elliptic: Source outside, offset by a small angle (e.g. 15 degrees)
            # Detector on opposite side
            y_s = sfd - R
            # Offset source to create elliptical projection of top weld
            xs_offset = R * 0.4
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

        # Dynamic Zoom & Limits
        padding = R * 1.5 if geometry != "swsi" else R * 0.5
        self.axes.set_xlim(-R - padding, R + padding)
        self.axes.set_ylim(-R - padding, max(R + padding, sfd - R + padding) if geometry != "swsi" else R + padding)
        
        # Legend (neat, modern style)
        self.axes.legend(loc='upper right', framealpha=0.1, facecolor=bg_color, edgecolor=text_color, labelcolor=text_color, fontsize=8)
        self.draw()

    def set_theme(self, is_dark):
        bg_color = '#1e1e2e' if is_dark else '#ffffff'
        self.fig.patch.set_facecolor(bg_color)
        self.axes.set_facecolor(bg_color)
        self.draw()

class StandardSchematicCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        
        self.axes.set_aspect('equal')
        self.axes.axis('off')
        self.fig.patch.set_facecolor('#1e1e2e')
        self.axes.set_facecolor('#1e1e2e')

    def set_theme(self, is_dark):
        bg_color = '#1e1e2e' if is_dark else '#ffffff'
        self.fig.patch.set_facecolor(bg_color)
        self.axes.set_facecolor(bg_color)
        self.draw()

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

        # Uniform Limits
        self.axes.set_xlim(-2.0, 2.0)
        self.axes.set_ylim(-2.0, 2.5)
        self.draw()

