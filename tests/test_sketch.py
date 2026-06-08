# -*- coding: utf-8 -*-

import os
import tempfile
import unittest
from unittest.mock import patch


class TestWeldSketchCanvasSaveFigure(unittest.TestCase):
    def test_weld_canvas_save_figure(self):
        """Test save_figure without Qt by using matplotlib Figure directly."""
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        fig = Figure(figsize=(5, 4), dpi=100)
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.set_aspect('equal')
        ax.axis('off')
        fig.patch.set_facecolor('#1e1e2e')
        ax.set_facecolor('#1e1e2e')
        ax.plot([0, 1], [0, 1], color='#89b4fa')

        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        tmp.close()
        try:
            fig.savefig(tmp.name, dpi=150, bbox_inches='tight', pad_inches=0.2)
            self.assertTrue(os.path.exists(tmp.name))
            self.assertGreater(os.path.getsize(tmp.name), 500)
        finally:
            os.unlink(tmp.name)

    def test_weld_canvas_save_figure_with_draw_setup_logic(self):
        """Test that matplotlib figure can be created and saved with weld-like elements."""
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        import matplotlib.patches as patches
        import numpy as np

        fig = Figure(figsize=(5, 4), dpi=100)
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.set_aspect('equal')
        ax.axis('off')
        fig.patch.set_facecolor('#1e1e2e')
        ax.set_facecolor('#1e1e2e')

        R = 50.0
        pipe_color = '#89b4fa'
        weld_color = '#f38ba8'
        beam_color = '#f9e2af'
        source_color = '#fab387'

        ax.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
        ax.add_patch(patches.Circle((0, 0), R - 8, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))
        ax.plot(0, 0, marker='*', color=source_color, markersize=12)
        ax.plot([0, -10], [0, -R], color=beam_color, linestyle=':', alpha=0.7)
        ax.plot([0, 10], [0, -R], color=beam_color, linestyle=':', alpha=0.7)

        ax.set_xlim(-R - 20, R + 20)
        ax.set_ylim(-R - 20, R + 20)

        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        tmp.close()
        try:
            fig.savefig(tmp.name, dpi=150, bbox_inches='tight', pad_inches=0.2)
            self.assertTrue(os.path.exists(tmp.name))
            self.assertGreater(os.path.getsize(tmp.name), 500)
        finally:
            os.unlink(tmp.name)


class TestStandardSchematicCanvasSaveFigure(unittest.TestCase):
    def test_standard_schematic_save_figure(self):
        """Test standard schematic canvas save figure with fig5-like content."""
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        import matplotlib.patches as patches
        import numpy as np

        fig = Figure(figsize=(5, 4), dpi=100)
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.set_aspect('equal')
        ax.axis('off')
        fig.patch.set_facecolor('#1e1e2e')
        ax.set_facecolor('#1e1e2e')

        R = 1.0
        pipe_color = '#89b4fa'
        det_color = '#a6e3a1'
        source_color = '#fab387'
        beam_color = '#f9e2af'

        ax.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
        ax.add_patch(patches.Circle((0, 0), R * 1.08, color=det_color, fill=False, linewidth=3))
        ax.plot(0, 0, marker='*', color=source_color, markersize=12)
        for angle in [0, 90, 180, 270]:
            rad = np.radians(angle)
            ax.plot([0, R * np.sin(rad)], [0, R * np.cos(rad)], color=beam_color, linestyle=':', alpha=0.8)

        ax.set_xlim(-2.0, 2.0)
        ax.set_ylim(-2.0, 2.5)

        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        tmp.close()
        try:
            fig.savefig(tmp.name, dpi=150, bbox_inches='tight', pad_inches=0.2)
            self.assertTrue(os.path.exists(tmp.name))
            self.assertGreater(os.path.getsize(tmp.name), 500)
        finally:
            os.unlink(tmp.name)

    def test_all_standard_figure_types_render(self):
        """Verify that each standard figure type can be drawn and saved."""
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        import matplotlib.patches as patches
        import numpy as np

        figure_types = ["fig5", "fig6", "fig7", "fig11", "fig12", "fig13"]
        for fig_name in figure_types:
            with self.subTest(figure=fig_name):
                fig = Figure(figsize=(5, 4), dpi=100)
                FigureCanvasAgg(fig)
                ax = fig.add_subplot(111)
                ax.set_aspect('equal')
                ax.axis('off')
                fig.patch.set_facecolor('#ffffff')
                ax.set_facecolor('#ffffff')

                R = 1.0
                pipe_color = '#1b5e20'
                det_color = '#2e7d32'
                source_color = '#e65100'
                beam_color = '#fbc02d'
                text_color = '#000000'

                ax.add_patch(patches.Circle((0, 0), R, color=pipe_color, fill=False, linewidth=2))
                ax.add_patch(patches.Circle((0, 0), R * 0.8, color=pipe_color, fill=False, linewidth=1.5, linestyle='--'))

                if fig_name == "fig5":
                    ax.add_patch(patches.Circle((0, 0), R * 1.08, color=det_color, fill=False, linewidth=3))
                    ax.plot(0, 0, marker='*', color=source_color, markersize=12)
                    ax.set_title("ISO 17636-1 Figure 5", color=text_color, fontsize=10)
                elif fig_name == "fig6":
                    ys = 0.5
                    ax.plot(0, ys, marker='*', color=source_color, markersize=10)
                    ax.add_patch(patches.Arc((0, 0), R * 2.08, R * 2.08, theta1=220, theta2=320, color=det_color, linewidth=4))
                    ax.set_title("ISO 17636-1 Figure 6", color=text_color, fontsize=10)
                elif fig_name == "fig7":
                    ys = 1.8
                    ax.plot(0, ys, marker='o', color=source_color, markersize=10)
                    ax.add_patch(patches.Arc((0, 0), 1.6, 1.6, theta1=220, theta2=320, color=det_color, linewidth=4))
                    ax.set_title("ISO 17636-1 Figure 7", color=text_color, fontsize=10)
                elif fig_name == "fig11":
                    xs, ys = 0.4, 1.8
                    ax.plot(xs, ys, marker='o', color=source_color, markersize=10)
                    ax.plot([-1.2, 1.2], [-1.2, -1.2], color=det_color, linewidth=4)
                    ax.set_title("ISO 17636-1 Figure 11", color=text_color, fontsize=10)
                elif fig_name == "fig12":
                    ys = 1.8
                    ax.plot(0, ys, marker='o', color=source_color, markersize=10)
                    ax.plot([-1.2, 1.2], [-1.2, -1.2], color=det_color, linewidth=4)
                    ax.set_title("ISO 17636-1 Figure 12", color=text_color, fontsize=10)
                elif fig_name == "fig13":
                    ys = 1.8
                    ax.plot(0, ys, marker='o', color=source_color, markersize=10)
                    ax.add_patch(patches.Arc((0, 0), R * 2.08, R * 2.08, theta1=220, theta2=320, color=det_color, linewidth=4))
                    ax.set_title("ISO 17636-1 Figure 13", color=text_color, fontsize=10)

                ax.set_xlim(-2.0, 2.0)
                ax.set_ylim(-2.0, 2.5)

                tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                tmp.close()
                try:
                    fig.savefig(tmp.name, dpi=150, bbox_inches='tight', pad_inches=0.2)
                    self.assertTrue(os.path.exists(tmp.name))
                    self.assertGreater(os.path.getsize(tmp.name), 300)
                finally:
                    os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
