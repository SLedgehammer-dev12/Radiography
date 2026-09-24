# -*- coding: utf-8 -*-

import logging
import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

logger = logging.getLogger(__name__)


def _esc(value):
    """Escapes XML markup characters so user-supplied text is safe inside a
    ReportLab Paragraph (which parses XML-like markup). Unescaped '&', '<',
    '>' in report fields crash PDF generation with a Parse error."""
    if value is None:
        return ""
    try:
        from xml.sax.saxutils import escape
        return escape(str(value))
    except Exception:
        return str(value)


def _valid_image(path):
    """Eagerly verifies that an image file can be decoded by reportlab.

    reportlab's Image flowable is lazy for PNG, so a corrupt/missing file would
    only fail later inside doc.build() and abort the whole PDF. This check lets
    the caller fall back to a placeholder text instead.
    """
    if not path:
        return False
    try:
        if not os.path.exists(path) or os.path.getsize(path) <= 0:
            return False
        from reportlab.lib.utils import ImageReader
        ImageReader(path)
        return True
    except Exception:
        return False


class PDFReportGenerator:
    _fonts_registered = False

    def __init__(self):
        if not PDFReportGenerator._fonts_registered:
            self._register_fonts()
            PDFReportGenerator._fonts_registered = True

    _ARIAL_FALLBACK = "Helvetica"
    _FONT_MAP = {
        "Arial": "Helvetica",
        "Arial-Bold": "Helvetica-Bold",
        "Arial-Italic": "Helvetica-Oblique",
        "Arial-BoldItalic": "Helvetica-BoldOblique",
        "Arial-Oblique": "Helvetica-Oblique",
    }

    # Bundled TrueType fonts (full Unicode incl. Turkish) used as a portable
    # fallback when the system Arial faces are unavailable. Embedding a TTF also
    # makes the PDF self-contained (renders correctly on any viewer).
    _BUNDLED_FONTS = [
        ("NotoSans", "NotoSans-Regular.ttf"),
        ("NotoSans-Bold", "NotoSans-Bold.ttf"),
        ("NotoSans-Italic", "NotoSans-Italic.ttf"),
    ]

    @staticmethod
    def _bundled_font_dir():
        """Absolute directory of the bundled Noto Sans fonts (frozen-safe)."""
        try:
            base = sys._MEIPASS
        except AttributeError:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        return os.path.join(base, "src", "mobile", "assets", "fonts")

    @staticmethod
    def _register_fonts():
        import platform

        system = platform.system()
        arial_candidates = []
        if system == "Darwin":
            arial_candidates = [
                ("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf"),
                ("Arial-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
                ("Arial-Italic", "/System/Library/Fonts/Supplemental/Arial Italic.ttf"),
                ("Arial-BoldItalic", "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"),
            ]
        elif system == "Windows":
            win_dir = os.environ.get("WINDIR", "C:\\Windows")
            arial_candidates = [
                ("Arial", os.path.join(win_dir, "Fonts", "arial.ttf")),
                ("Arial-Bold", os.path.join(win_dir, "Fonts", "arialbd.ttf")),
                ("Arial-Italic", os.path.join(win_dir, "Fonts", "ariali.ttf")),
                ("Arial-BoldItalic", os.path.join(win_dir, "Fonts", "arialbi.ttf")),
            ]

        registered_arial = 0
        for name, path in arial_candidates:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    PDFReportGenerator._FONT_MAP[name] = name
                    registered_arial += 1
                except Exception:
                    logger.warning("Could not register system font %s at %s", name, path, exc_info=True)
        if registered_arial == 4:
            try:
                pdfmetrics.registerFontFamily(
                    "Arial", normal="Arial", bold="Arial-Bold",
                    italic="Arial-Italic", boldItalic="Arial-BoldItalic",
                )
            except Exception:
                logger.warning("Could not register Arial font family", exc_info=True)

        # Register the bundled Noto Sans faces (portable fallback).
        noto_dir = PDFReportGenerator._bundled_font_dir()
        registered_noto = 0
        for name, filename in PDFReportGenerator._BUNDLED_FONTS:
            path = os.path.join(noto_dir, filename)
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    registered_noto += 1
                except Exception:
                    logger.warning("Could not register bundled font %s at %s", name, path, exc_info=True)

        # Prefer Arial only when all its faces are present; otherwise use the
        # bundled Noto Sans so Turkish/Unicode text always renders correctly.
        if registered_arial < 4 and registered_noto >= 3:
            PDFReportGenerator._FONT_MAP.update({
                "Arial": "NotoSans",
                "Arial-Bold": "NotoSans-Bold",
                "Arial-Italic": "NotoSans-Italic",
                "Arial-BoldItalic": "NotoSans-Bold",
                "Arial-Oblique": "NotoSans-Italic",
            })
            try:
                pdfmetrics.registerFontFamily(
                    "NotoSans", normal="NotoSans", bold="NotoSans-Bold",
                    italic="NotoSans-Italic", boldItalic="NotoSans-Bold",
                )
            except Exception:
                logger.warning("Could not register NotoSans font family", exc_info=True)

    @staticmethod
    def _resolve_font(name):
        return PDFReportGenerator._FONT_MAP.get(name, PDFReportGenerator._ARIAL_FALLBACK)

    @staticmethod
    def _build_qr_payload(inputs, outputs):
        """Compact verification payload embedded in the QR code (with hash)."""
        import hashlib
        parts = [
            "RT-Report",
            (inputs.get("report_info") or {}).get("report_no", ""),
            inputs.get("material_text", ""),
            f"t={inputs.get('t', 0)}",
            f"OD={inputs.get('od', 0)}",
            inputs.get("source", ""),
            inputs.get("geometry", ""),
            f"N={outputs.get('exposures', '')}",
            inputs.get("class_text", ""),
        ]
        raw = "|".join(str(p) for p in parts)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"{raw}|HASH={digest}"

    @staticmethod
    def _make_qr_image(inputs, outputs):
        """Builds a PNG file-like object of the verification QR code, or None
        if the optional `qrcode` package is unavailable."""
        try:
            import io
            import qrcode
            from qrcode.constants import ERROR_CORRECT_M
            from qrcode.image.pil import PilImage
            payload = PDFReportGenerator._build_qr_payload(inputs, outputs)
            qr = qrcode.QRCode(version=2, error_correction=ERROR_CORRECT_M,
                               box_size=4, border=2)
            qr.add_data(payload)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white", image_factory=PilImage)
            img = img.resize((120, 120))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return buf
        except Exception:
            return None

    def generate_report(self, filepath, inputs, outputs, warnings_list, defect_eval, lvl3_active, sfd_comp_val, lang_obj, dynamic_img_path=None, standard_img_path=None):
        """
        Generates the PDF report. Never raises: returns True on success and
        False on any build/formatting error (the caller shows an error dialog).
        """
        try:
            return self._generate_report_impl(
                filepath, inputs, outputs, warnings_list, defect_eval,
                lvl3_active, sfd_comp_val, lang_obj,
                dynamic_img_path=dynamic_img_path,
                standard_img_path=standard_img_path,
            )
        except Exception:
            logger.exception("PDF report generation failed")
            return False

    def _generate_report_impl(self, filepath, inputs, outputs, warnings_list, defect_eval, lvl3_active, sfd_comp_val, lang_obj, dynamic_img_path=None, standard_img_path=None):
        """
        Generates a professional PDF report of the RT calculation and defect evaluation.
        """
        # Set up document
        doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        story = []
        styles = getSampleStyleSheet()

        # Language code — works with a Translation object (desktop) or a plain
        # dict of translations (mobile pdf_helper).
        if isinstance(lang_obj, dict):
            lang_code = lang_obj.get("language", "tr")
        else:
            lang_code = getattr(lang_obj, "language", "tr")

        # Custom Styles
        title_style = ParagraphStyle(
            name='TitleStyle',
            fontName=self._resolve_font('Arial-Bold'),
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#1b5e20'), # Dark Green / Teal accent
            alignment=1, # Center
        )
        
        section_style = ParagraphStyle(
            name='SectionStyle',
            fontName=self._resolve_font('Arial-Bold'),
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#0d47a1'), # Dark Blue
            spaceBefore=12,
            spaceAfter=6,
        )

        label_style = ParagraphStyle(
            name='LabelStyle',
            fontName=self._resolve_font('Arial-Bold'),
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#212121'),
        )

        value_style = ParagraphStyle(
            name='ValueStyle',
            fontName=self._resolve_font('Arial'),
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#424242'),
        )

        warning_style = ParagraphStyle(
            name='WarningStyle',
            fontName=self._resolve_font('Arial-Oblique'),
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#b71c1c'), # Red warning text
        )

        # Title (with optional verification QR code)
        qr_img = self._make_qr_image(inputs, outputs)
        if qr_img is not None:
            header_table = Table(
                [[Paragraph(lang_obj.get("app_title"), title_style), Image(qr_img, width=92, height=92)]],
                colWidths=[408, 92]
            )
            header_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (1,0), (1,0), 10),
                ('ALIGN', (0,0), (0,0), 'CENTER'),
            ]))
            story.append(header_table)
        else:
            story.append(Paragraph(lang_obj.get("app_title"), title_style))
        story.append(Spacer(1, 15))

        # Metadata Row
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meta_data = [
            [Paragraph(f"<b>Date/Time:</b> {now_str}", value_style), 
             Paragraph("<b>Standards:</b> ISO 17636-1/2, API 1104, ISO 19232-1/5", value_style)]
        ]
        meta_table = Table(meta_data, colWidths=[200, 300])
        meta_table.setStyle(TableStyle([
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor('#e0e0e0')),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 15))

        # Report / procedure header fields (only non-empty ones)
        report_info = inputs.get("report_info") or {}
        info_fields = [
            ("report_no", "report_no"), ("report_rev", "report_rev"),
            ("project", "project"), ("welder_id", "welder_id"),
            ("joint_id", "joint_id"), ("wps_pqr", "wps_pqr"),
            ("procedure_no", "procedure_no"), ("device_serial", "device_serial"),
            ("calibration_date", "calibration_date"), ("personnel", "personnel"),
            ("lvl2_name", "lvl2_name"), ("lvl2_cert", "lvl2_cert"),
            ("lvl3_name", "lvl3_name"), ("lvl3_cert", "lvl3_cert"),
        ]
        filled_info = [(key, report_info.get(key, "")) for key, _ in info_fields if report_info.get(key)]
        if filled_info:
            story.append(Paragraph(lang_obj.get("report_info_section"), section_style))
            info_rows = [[Paragraph(lang_obj.get(key), label_style), Paragraph(_esc(value), value_style)]
                         for key, value in filled_info]
            info_table = Table(info_rows, colWidths=[220, 280])
            info_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cfd8dc')),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f5f5f5')),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(info_table)
            story.append(Spacer(1, 12))

        # Section 1: Inputs
        story.append(Paragraph(lang_obj.get("inputs_section"), section_style))
        inputs_data = [
            [Paragraph(lang_obj.get("material_type"), label_style), Paragraph(inputs.get("material_text", ""), value_style),
             Paragraph(lang_obj.get("testing_class"), label_style), Paragraph(inputs.get("class_text", ""), value_style)],
            [Paragraph(lang_obj.get("pipe_od"), label_style), Paragraph(f"{inputs.get('od', 0.0):.1f} mm", value_style),
             Paragraph(lang_obj.get("rt_tech"), label_style), Paragraph(inputs.get("tech_text", ""), value_style)],
            [Paragraph(lang_obj.get("nominal_t"), label_style), Paragraph(f"{inputs.get('t', 0.0):.1f} mm", value_style),
             Paragraph(lang_obj.get("rad_source"), label_style), Paragraph(inputs.get("source_text", ""), value_style)],
            [Paragraph(lang_obj.get("cap_height"), label_style), Paragraph(f"{inputs.get('cap', 0.0):.1f} mm", value_style),
             Paragraph(lang_obj.get("focal_size"), label_style), Paragraph(f"{inputs.get('d', 0.0):.2f} mm", value_style)],
            [Paragraph(lang_obj.get("geometry"), label_style), Paragraph(inputs.get("geometry_text", ""), value_style),
             Paragraph(lang_obj.get("actual_sfd"), label_style), Paragraph(f"{inputs.get('sfd', 0.0):.1f} mm", value_style)]
        ]

        # Add Tube Voltage (kV) if X-Ray or Activity (Ci) if Isotope
        if inputs.get("source") == "x_ray":
            inputs_data.append([
                Paragraph(lang_obj.get("applied_kv"), label_style), 
                Paragraph(f"{inputs.get('input_kv', 120.0):.1f} kV", value_style),
                Paragraph(lang_obj.get("amperage"), label_style),
                Paragraph(f"{inputs.get('output_val', 5.0):.1f} mA", value_style)
            ])
        else:
            inputs_data.append([
                Paragraph(lang_obj.get("applied_activity"), label_style),
                Paragraph(f"{inputs.get('output_val', 40.0):.1f} Ci", value_style),
                Paragraph("", label_style),
                Paragraph("", value_style)
            ])

        # Film Overlap if Analog Film
        if inputs.get("tech") == "analog":
            inputs_data.append([
                Paragraph(lang_obj.get("film_overlap"), label_style),
                Paragraph(f"{inputs.get('overlap', 10.0):.1f} mm", value_style),
                Paragraph("", label_style),
                Paragraph("", value_style)
            ])
        elif inputs.get("tech") == "digital":
            loc_val = inputs.get("snr_location", "weld")
            loc_text = lang_obj.get("snr_location_weld") if loc_val == "weld" else lang_obj.get("snr_location_adjacent")
            inputs_data.append([
                Paragraph(lang_obj.get("snr_location"), label_style),
                Paragraph(loc_text, value_style),
                Paragraph("", label_style),
                Paragraph("", value_style)
            ])

        # Exposure chart constant (E) — only meaningful for the physics model
        e_unit = "mA·min/m²" if inputs.get("source") == "x_ray" else "Ci·min/m²"
        inputs_data.append([
            Paragraph(lang_obj.get("base_factor"), label_style),
            Paragraph(f"{inputs.get('base_e', 3.0):.4f} {e_unit}", value_style),
            Paragraph("", label_style),
            Paragraph("", value_style)
        ])

        # Weld width (DWDI techniques) — used for the De/4 geometry check
        if inputs.get("geometry") in ("dwdi_elliptic", "dwdi_super"):
            inputs_data.append([
                Paragraph(lang_obj.get("weld_width"), label_style),
                Paragraph(f"{inputs.get('weld_width', 8.0):.1f} mm", value_style),
                Paragraph("", label_style),
                Paragraph("", value_style)
            ])

        # Inspection standard
        std_key = "standard_asme" if inputs.get("standard") == "asme" else "standard_iso"
        inputs_data.append([
            Paragraph(lang_obj.get("standard"), label_style),
            Paragraph(lang_obj.get(std_key), value_style),
            Paragraph("", label_style),
            Paragraph("", value_style)
        ])
        
        inputs_table = Table(inputs_data, colWidths=[140, 110, 140, 110])
        inputs_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cfd8dc')),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f5f5f5')),
            ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#f5f5f5')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(inputs_table)
        story.append(Spacer(1, 15))

        # Section 2: Outputs
        story.append(Paragraph(lang_obj.get("outputs"), section_style))
        
        iqi_label = lang_obj.get("single_step_hole_iqi") if inputs.get("iqi_type") == "step_hole" else lang_obj.get("single_wire_iqi")

        exp_panel = outputs.get("exposures_panel")
        exp_applied = outputs.get("exposures_applied")
        exp_check = outputs.get("exposures_check")
        exp_panel_str = "N/A" if exp_panel is None else str(exp_panel)
        exp_applied_str = "N/A" if exp_applied is None else str(exp_applied)
        if exp_check is None:
            exp_check_str = "N/A"
        elif exp_check:
            exp_check_str = "UYGUN" if lang_code == "tr" else "OK"
        else:
            exp_check_str = "UYGUN DEĞİL" if lang_code == "tr" else "NOT OK"

        outputs_data = [
            [Paragraph(lang_obj.get("w_nom"), label_style), Paragraph(f"{outputs.get('w_nom', 0.0):.2f} mm", value_style),
             Paragraph(lang_obj.get("req_exposures"), label_style), Paragraph(str(outputs.get('exposures', 0)), value_style)],
            [Paragraph(lang_obj.get("exposures_panel"), label_style), Paragraph(exp_panel_str, value_style),
             Paragraph(lang_obj.get("exposures_applied"), label_style), Paragraph(exp_applied_str, value_style)],
            [Paragraph(lang_obj.get("exposures_check"), label_style), Paragraph(exp_check_str, value_style),
             Paragraph("", label_style), Paragraph("", value_style)],
            [Paragraph(lang_obj.get("w_eff"), label_style), Paragraph(f"{outputs.get('w_eff', 0.0):.2f} mm", value_style),
             Paragraph(iqi_label, label_style), Paragraph(_esc(outputs.get('single_wire_iqi', "")), value_style)],
            [Paragraph(lang_obj.get("u_max"), label_style), Paragraph(f"{outputs.get('u_max', 0.0):.1f} kV" if outputs.get('u_max') else "N/A (Isotope)", value_style),
             Paragraph(lang_obj.get("duplex_iqi"), label_style), Paragraph(_esc(outputs.get('duplex_iqi', "N/A (Analog Film)")), value_style)],
            [Paragraph(lang_obj.get("f_min"), label_style), Paragraph(f"{outputs.get('f_min', 0.0):.1f} mm", value_style),
             Paragraph(lang_obj.get("calc_time"), label_style), Paragraph(_esc(outputs.get('calc_time', "")), value_style)],
            [Paragraph(lang_obj.get("sfd_min"), label_style), Paragraph(f"{outputs.get('sfd_min', 0.0):.1f} mm", value_style),
             Paragraph(lang_obj.get("target_snr") if inputs.get("tech") == "digital" else lang_obj.get("optical_density"), label_style),
             Paragraph(_esc(outputs.get('quality_target', "")), value_style)],
            [Paragraph(lang_obj.get("detector_quality"), label_style), Paragraph(_esc(outputs.get('detector_quality', "")), value_style),
             Paragraph(lang_obj.get("filter_recommendation"), label_style), Paragraph(_esc(outputs.get('filter_recommendation', "")), value_style)],
            [Paragraph(lang_obj.get("base_multiplier"), label_style), Paragraph(f"{outputs.get('base_multiplier', 1.0):.2f}", value_style),
             Paragraph("", label_style), Paragraph("", value_style)]
        ]

        # Geometric unsharpness (always) and the ASME-derived f_min (ASME only)
        f_min_asme = outputs.get("f_min_asme")
        if f_min_asme is not None:
            ug_pair = [
                Paragraph(lang_obj.get("f_min_asme"), label_style),
                Paragraph(f"{f_min_asme:.1f} mm", value_style),
            ]
        else:
            ug_pair = [Paragraph("", label_style), Paragraph("", value_style)]
        outputs_data.append([
            Paragraph(lang_obj.get("ug"), label_style),
            Paragraph(f"{outputs.get('ug', 0.0):.3f} mm", value_style),
        ] + ug_pair)

        # ASME/ASTM IQI and radiation barrier distance (when available)
        asme_iqi = outputs.get("asme_iqi")
        if asme_iqi and str(asme_iqi) != "N/A":
            outputs_data.append([
                Paragraph(lang_obj.get("asme_iqi"), label_style),
                Paragraph(_esc(asme_iqi), value_style),
                Paragraph("", label_style), Paragraph("", value_style)
            ])
        barrier = outputs.get("barrier_distance")
        if barrier and str(barrier) != "N/A":
            outputs_data.append([
                Paragraph(lang_obj.get("barrier_distance"), label_style),
                Paragraph(_esc(barrier), value_style),
                Paragraph("", label_style), Paragraph("", value_style)
            ])

        outputs_table = Table(outputs_data, colWidths=[140, 110, 140, 110])
        outputs_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#b0bec5')),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#eceff1')),
            ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#eceff1')),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(outputs_table)
        story.append(Spacer(1, 15))

        # Field Correction Factor (F) context note (only when it deviates from 1.0)
        if outputs.get("base_multiplier", 1.0) != 1.0:
            note_style = ParagraphStyle(
                name='BaseMultiplierNote',
                fontName=self._resolve_font('Arial-Oblique'),
                fontSize=8,
                leading=11,
                textColor=colors.HexColor('#616161'),
            )
            story.append(Paragraph(lang_obj.get("base_multiplier_note"), note_style))
            story.append(Spacer(1, 8))

        # Section 3: Level 3 Overrides (If active)
        if lvl3_active:
            story.append(Paragraph(lang_obj.get("level3_section"), section_style))
            lvl3_data = [
                [Paragraph(f"<b>{lang_obj.get('level3_active')}</b>", label_style), Paragraph(lang_obj.get("success"), value_style)],
                [Paragraph(lang_obj.get("sfd_comp_label"), label_style), Paragraph(f"SNR_N = {sfd_comp_val:.1f}" if sfd_comp_val else "N/A", value_style)]
            ]
            lvl3_table = Table(lvl3_data, colWidths=[250, 250])
            lvl3_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#ffcc80')),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fff8e1')),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(lvl3_table)
            story.append(Spacer(1, 15))

        # Section 4: Defect Evaluation
        if defect_eval and defect_eval.get("active"):
            story.append(Paragraph(lang_obj.get("defect_section"), section_style))
            eval_color = colors.HexColor('#c8e6c9') if defect_eval.get("status") else colors.HexColor('#ffcdd2')
            eval_text_color = colors.HexColor('#1b5e20') if defect_eval.get("status") else colors.HexColor('#b71c1c')
            
            result_lbl = lang_obj.get("result_accept") if defect_eval.get("status") else lang_obj.get("result_reject")

            defect_data = [
                [Paragraph(lang_obj.get("defect_type"), label_style), Paragraph(_esc(defect_eval.get("type_text", "")), value_style)],
                [Paragraph(lang_obj.get("defect_length"), label_style), Paragraph(f"{defect_eval.get('len', 0.0):.1f} mm", value_style)],
                [Paragraph(lang_obj.get("defect_width"), label_style), Paragraph(f"{defect_eval.get('width', 0.0):.1f} mm", value_style)],
                [Paragraph(lang_obj.get("accumulated_12in"), label_style), Paragraph(f"{defect_eval.get('accum', 0.0):.1f} mm", value_style)],
                [Paragraph(f"<b>{lang_obj.get('evaluation_result')}</b>", label_style), 
                 Paragraph(f"<font color='{eval_text_color}'><b>{result_lbl}</b></font>", label_style)],
                [Paragraph("<b>Reason / Details:</b>", label_style), Paragraph(_esc(defect_eval.get("reason", "")), value_style)]
            ]
            
            defect_table = Table(defect_data, colWidths=[180, 320])
            defect_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#b0bec5')),
                ('BACKGROUND', (0,4), (1,4), eval_color),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f5f5f5')),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(defect_table)
            story.append(Spacer(1, 15))

        # Section 5: Warnings & Diagnostic Messages
        warnings_list = [w for w in (warnings_list or []) if str(w).strip()]
        if warnings_list:
            story.append(Paragraph(lang_obj.get("warnings"), section_style))
            warn_table_data = []
            for w in warnings_list:
                warn_table_data.append([Paragraph(f"• {_esc(w)}", warning_style)])
            
            warn_table = Table(warn_table_data, colWidths=[500])
            warn_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ffebee')),
                ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#ffcdd2')),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(warn_table)
            story.append(Spacer(1, 30))

        # Section 6: Shooting Geometry Sketches (if images provided)
        dynamic_img_path = dynamic_img_path if _valid_image(dynamic_img_path) else None
        standard_img_path = standard_img_path if _valid_image(standard_img_path) else None
        if dynamic_img_path or standard_img_path:
            story.append(Paragraph("Shooting Geometry Sketches", section_style))
            img_data = []
            col_widths = []
            if dynamic_img_path:
                try:
                    dyn_img = Image(dynamic_img_path, width=220, height=160)
                    img_data.append(dyn_img)
                    col_widths.append(250)
                except Exception:
                    img_data.append(Paragraph("Dynamic sketch unavailable", value_style))
                    col_widths.append(250)
            else:
                img_data.append(Paragraph("", value_style))
                col_widths.append(250)
            if standard_img_path:
                try:
                    std_img = Image(standard_img_path, width=220, height=160)
                    img_data.append(std_img)
                    col_widths.append(250)
                except Exception:
                    img_data.append(Paragraph("Standard sketch unavailable", value_style))
                    col_widths.append(250)
            else:
                img_data.append(Paragraph("", value_style))
                col_widths.append(250)

            caption_data = []
            if dynamic_img_path:
                caption_data.append(Paragraph("<b>Dynamic Shot Setup</b>", label_style))
            else:
                caption_data.append(Paragraph("", label_style))
            if standard_img_path:
                caption_data.append(Paragraph("<b>ISO 17636 Figure Schematic</b>", label_style))
            else:
                caption_data.append(Paragraph("", label_style))

            img_table = Table([img_data, caption_data], colWidths=col_widths)
            img_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(img_table)
            story.append(Spacer(1, 15))

        # Section 7: Standards & References Appendix
        story.append(Paragraph("<b>" + lang_obj.get("pdf_ref_title", "Standards & Calculation References") + "</b>", section_style))
        ref_style = ParagraphStyle(
            name='RefStyle',
            fontName=self._resolve_font('Arial'),
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor('#616161'),
        )
        ref_header_style = ParagraphStyle(
            name='RefHeaderStyle',
            fontName=self._resolve_font('Arial-Bold'),
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#212121'),
        )
        
        ref_rows = [
            [Paragraph("<b>Parameter</b>", ref_header_style), Paragraph("<b>Standard Reference & Clause</b>", ref_header_style)],
            [Paragraph("Nominal Thickness (w_nom)", ref_style), Paragraph("ISO 17636-1:2022 Clause 3 (t/w definitions), Clause 6.9 &amp; Annex B (SWSI: w_nom = t; DWSI/DWDI: w_nom = 2t)", ref_style)],
            [Paragraph("Min Shooting Distance (f_min)", ref_style), Paragraph("ISO 17636-1:2022 Clause 7.6, Formula (1) Class A / Formula (2) Class B (f_min = C·d·b^(2/3); C=7.5/15); planar detectors: Clause 7.6 Formula (13) f_min*", ref_style)],
            [Paragraph("Minimum Exposures (N)", ref_style), Paragraph("ISO 17636-1:2022 Annex A (number of exposures for circumferential butt welds)", ref_style)],
            [Paragraph("Single Wire IQI Target", ref_style), Paragraph("ISO 19232-1 &amp; ISO 17636-1:2022 Annex B Tables B.1–B.12", ref_style)],
            [Paragraph("Geometric Unsharpness (Ug)", ref_style), Paragraph("Ug = d·b/f with f = SDD − b (ASME Sec V Art 2 T-274.2; ISO 17636-2:2022 Clauses 3.21–3.22)", ref_style)],
        ]

        if inputs.get("standard") == "asme":
            ref_rows.append([Paragraph("ASME Min Distance (f_min, ASME)", ref_style), Paragraph("ASME Sec V Art 2 T-274.2 (Ug ≤ Ug_limit → f_min = d·b/Ug_limit; limits per Table T-274.2)", ref_style)])

        if inputs.get("source") == "x_ray":
            ref_rows.append([Paragraph("Max Tube Voltage (U_max)", ref_style), Paragraph("ISO 17636-1:2022 Annex C Table C.1 (approximation formulae for maximum tube voltage, informative)", ref_style)])
            
        if inputs.get("tech") == "digital":
            ref_rows.append([Paragraph("Duplex Wire IQI Target", ref_style), Paragraph("ISO 19232-5 &amp; ISO 17636-2:2022 Clause 6.7.2; limits in Tables B.13/B.14", ref_style)])
            ref_rows.append([Paragraph("Target SNR_N", ref_style), Paragraph("ISO 17636-2:2022 Clause 7.3.1 &amp; Tables 3/4 (dynamic Class A/B minimum SNR_N)", ref_style)])
            ref_rows.append([Paragraph("SNR_N Measurement Location", ref_style), Paragraph("ISO 17636-2:2022 Clause 7.3.1 (non-flush weld: target SNR_N × 1.4 when measured adjacent)", ref_style)])
            ref_rows.append([Paragraph("Detector Basic Resolution (SRb)", ref_style), Paragraph("ISO 17636-2:2022 Tables B.13 (Class A) &amp; B.14 (Class B) — maximum SRb", ref_style)])
            ref_rows.append([Paragraph("Compensation Principles (CP I/II/III)", ref_style), Paragraph("ISO 17636-2:2022 Clause 5.2 (contrast/sharpness compensation by increased SNR)", ref_style)])
            ref_rows.append([Paragraph("Panel Coverage Exposures", ref_style), Paragraph("ISO 17636-2:2022 Clause 7.8 &amp; Annex A (flat-panel DDA coverage of the circumference)", ref_style)])
        else:
            ref_rows.append([Paragraph("Optical Density Target (D)", ref_style), Paragraph("ISO 17636-1:2022 Clause 7.8 &amp; Table 5 (Class A ≥ 2.0, Class B ≥ 2.3)", ref_style)])
            ref_rows.append([Paragraph("Film System Class", ref_style), Paragraph("ISO 17636-1:2022 Tables 3/4 (film system class per ISO 11699-1)", ref_style)])
            ref_rows.append([Paragraph("Film Overlap", ref_style), Paragraph("ISO 17636-1:2022 Clause 6.6 (overlap of films verified by a high-density marker)", ref_style)])
            
        ref_rows.append([Paragraph("Filter / Screen Recommendation", ref_style), Paragraph("ISO 17636-1:2022 Clause 7.5.1 (metal screens/filters); ASME Sec V Art 2", ref_style)])
            
        ref_table = Table(ref_rows, colWidths=[180, 320])
        ref_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cfd8dc')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#eceff1')),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(ref_table)
        story.append(Spacer(1, 20))

        # Formal approval blocks — Level II (Inspector) / Level III (Approver)
        lvl2_name = _esc((report_info or {}).get("lvl2_name", ""))
        lvl2_cert = _esc((report_info or {}).get("lvl2_cert", ""))
        lvl3_name = _esc((report_info or {}).get("lvl3_name", ""))
        lvl3_cert = _esc((report_info or {}).get("lvl3_cert", ""))
        sig_data = [
            ["", ""],
            ["_________________________", "_________________________"],
            [Paragraph(lang_obj.get("lvl2_name"), label_style), Paragraph(lang_obj.get("lvl3_name"), label_style)],
            [Paragraph(f"{lvl2_name} {('(' + lvl2_cert + ')') if lvl2_cert else ''}", value_style),
             Paragraph(f"{lvl3_name} {('(' + lvl3_cert + ')') if lvl3_cert else ''}", value_style)],
        ]
        sig_table = Table(sig_data, colWidths=[250, 250])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,2), (-1,2), 9),
            ('TOPPADDING', (0,1), (-1,1), 40), # Space for signatures / kaşe
        ]))
        story.append(sig_table)

        # Section 8: Owner, Contact & Disclaimer
        owner_style = ParagraphStyle(
            name='OwnerStyle',
            fontName=self._resolve_font('Arial-Bold'),
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#212121'),
        )
        contact_style = ParagraphStyle(
            name='ContactStyle',
            fontName=self._resolve_font('Arial'),
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor('#0d47a1'),
        )
        small_muted_style = ParagraphStyle(
            name='SmallMutedStyle',
            fontName=self._resolve_font('Arial'),
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#616161'),
        )
        story.append(Spacer(1, 12))
        story.append(Paragraph(lang_obj.get("app_owner"), owner_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(lang_obj.get("contact_title"), owner_style))
        story.append(Paragraph(lang_obj.get("contact_github"), contact_style))
        story.append(Paragraph(lang_obj.get("contact_email"), contact_style))
        story.append(Spacer(1, 6))
        story.append(Paragraph(lang_obj.get("disclaimer"), small_muted_style))

        # Build PDF
        try:
            doc.build(story)
            return True
        except Exception as e:
            logger.error("Error building PDF: %s", e)
            return False
