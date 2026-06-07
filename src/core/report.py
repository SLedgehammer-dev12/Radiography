# -*- coding: utf-8 -*-

import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

class PDFReportGenerator:
    _fonts_registered = False

    def __init__(self):
        if not PDFReportGenerator._fonts_registered:
            self._register_fonts()
            PDFReportGenerator._fonts_registered = True

    @staticmethod
    def _register_fonts():
        font_paths = [
            ("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf"),
            ("Arial-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
            ("Arial-Italic", "/System/Library/Fonts/Supplemental/Arial Italic.ttf"),
            ("Arial-BoldItalic", "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"),
            ("Arial-Oblique", "/System/Library/Fonts/Supplemental/Arial Italic.ttf"),
        ]
        for name, path in font_paths:
            if os.path.exists(path):
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                except Exception:
                    pass

    def generate_report(self, filepath, inputs, outputs, warnings_list, defect_eval, lvl3_active, sfd_comp_val, lang_obj):
        """
        Generates a professional PDF report of the RT calculation and defect evaluation.
        """
        # Set up document
        doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        story = []
        styles = getSampleStyleSheet()

        # Custom Styles
        title_style = ParagraphStyle(
            name='TitleStyle',
            fontName='Arial-Bold',
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#1b5e20'), # Dark Green / Teal accent
            alignment=1, # Center
        )
        
        section_style = ParagraphStyle(
            name='SectionStyle',
            fontName='Arial-Bold',
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#0d47a1'), # Dark Blue
            spaceBefore=12,
            spaceAfter=6,
        )

        label_style = ParagraphStyle(
            name='LabelStyle',
            fontName='Arial-Bold',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#212121'),
        )

        value_style = ParagraphStyle(
            name='ValueStyle',
            fontName='Arial',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#424242'),
        )

        warning_style = ParagraphStyle(
            name='WarningStyle',
            fontName='Arial-Oblique',
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#b71c1c'), # Red warning text
        )

        # Title
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
        
        outputs_data = [
            [Paragraph(lang_obj.get("w_nom"), label_style), Paragraph(f"{outputs.get('w_nom', 0.0):.2f} mm", value_style),
             Paragraph(lang_obj.get("req_exposures"), label_style), Paragraph(str(outputs.get('exposures', 0)), value_style)],
            [Paragraph(lang_obj.get("w_eff"), label_style), Paragraph(f"{outputs.get('w_eff', 0.0):.2f} mm", value_style),
             Paragraph(iqi_label, label_style), Paragraph(outputs.get('single_wire_iqi', ""), value_style)],
            [Paragraph(lang_obj.get("u_max"), label_style), Paragraph(f"{outputs.get('u_max', 0.0):.1f} kV" if outputs.get('u_max') else "N/A (Isotope)", value_style),
             Paragraph(lang_obj.get("duplex_iqi"), label_style), Paragraph(outputs.get('duplex_iqi', "N/A (Analog Film)"), value_style)],
            [Paragraph(lang_obj.get("f_min"), label_style), Paragraph(f"{outputs.get('f_min', 0.0):.1f} mm", value_style),
             Paragraph(lang_obj.get("calc_time"), label_style), Paragraph(outputs.get('calc_time', ""), value_style)],
            [Paragraph(lang_obj.get("sfd_min"), label_style), Paragraph(f"{outputs.get('sfd_min', 0.0):.1f} mm", value_style),
             Paragraph(lang_obj.get("target_snr") if inputs.get("tech") == "digital" else lang_obj.get("optical_density"), label_style),
             Paragraph(str(outputs.get('quality_target', "")), value_style)],
            [Paragraph(lang_obj.get("detector_quality"), label_style), Paragraph(outputs.get('detector_quality', ""), value_style),
             Paragraph(lang_obj.get("filter_recommendation"), label_style), Paragraph(outputs.get('filter_recommendation', ""), value_style)]
        ]
        
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
                [Paragraph(lang_obj.get("defect_type"), label_style), Paragraph(defect_eval.get("type_text", ""), value_style)],
                [Paragraph(lang_obj.get("defect_length"), label_style), Paragraph(f"{defect_eval.get('len', 0.0):.1f} mm", value_style)],
                [Paragraph(lang_obj.get("defect_width"), label_style), Paragraph(f"{defect_eval.get('width', 0.0):.1f} mm", value_style)],
                [Paragraph(lang_obj.get("accumulated_12in"), label_style), Paragraph(f"{defect_eval.get('accum', 0.0):.1f} mm", value_style)],
                [Paragraph(f"<b>{lang_obj.get('evaluation_result')}</b>", label_style), 
                 Paragraph(f"<font color='{eval_text_color}'><b>{result_lbl}</b></font>", label_style)],
                [Paragraph("<b>Reason / Details:</b>", label_style), Paragraph(defect_eval.get("reason", ""), value_style)]
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
        if warnings_list:
            story.append(Paragraph(lang_obj.get("warnings"), section_style))
            warn_table_data = []
            for w in warnings_list:
                warn_table_data.append([Paragraph(f"• {w}", warning_style)])
            
            warn_table = Table(warn_table_data, colWidths=[500])
            warn_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ffebee')),
                ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#ffcdd2')),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(warn_table)
            story.append(Spacer(1, 30))

        # Section 5.5: Standards & References Appendix (Option 4)
        story.append(Paragraph("<b>" + lang_obj.get("pdf_ref_title", "Standards & Calculation References") + "</b>", section_style))
        ref_style = ParagraphStyle(
            name='RefStyle',
            fontName='Arial',
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor('#616161'),
        )
        ref_header_style = ParagraphStyle(
            name='RefHeaderStyle',
            fontName='Arial-Bold',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor('#212121'),
        )
        
        ref_rows = [
            [Paragraph("<b>Parameter</b>", ref_header_style), Paragraph("<b>Standard Reference & Clause</b>", ref_header_style)],
            [Paragraph("Nominal Thickness (w_nom)", ref_style), Paragraph("ISO 17636-1 Clause 4.3 (SWSI: w_nom = t; DWSI/DWDI: w_nom = 2t)", ref_style)],
            [Paragraph("Min Shooting Distance (f_min)", ref_style), Paragraph("ISO 17636-1 Clause 6.3, Equation (2) (f_min = C * d * b^(2/3); C=7.5 Class A, C=15 Class B)", ref_style)],
            [Paragraph("Minimum Exposures (N)", ref_style), Paragraph("ISO 17636-1 Clause 6.4 (circumferential weld minimum number of exposures)", ref_style)],
            [Paragraph("Single Wire IQI Target", ref_style), Paragraph("ISO 19232-1 & ISO 17636-1 Annex B Tables B.1 - B.3", ref_style)],
        ]
        
        if inputs.get("source") == "x_ray":
            ref_rows.append([Paragraph("Max Tube Voltage (U_max)", ref_style), Paragraph("ISO 17636-1 Annex C Table C.1 (Maximum X-Ray voltage caps)", ref_style)])
            
        if inputs.get("tech") == "digital":
            ref_rows.append([Paragraph("Duplex Wire IQI Target", ref_style), Paragraph("ISO 19232-5 & ISO 17636-2 Clause 6.6 Table 3 (basic unsharpness / duplex)", ref_style)])
            ref_rows.append([Paragraph("Target SNR_N", ref_style), Paragraph("ISO 17636-2 Clause 6.8 (Class A SNR_N >= 70, Class B SNR_N >= 130)", ref_style)])
            ref_rows.append([Paragraph("Detector Basic Resolution (SRb)", ref_style), Paragraph("ISO 17636-2 Tables B.1 & B.2 (Maximum allowed basic spatial resolution)", ref_style)])
        else:
            ref_rows.append([Paragraph("Optical Density Target (D)", ref_style), Paragraph("ISO 17636-1 Clause 5.3 (Class A density >= 2.0, Class B >= 2.3)", ref_style)])
            ref_rows.append([Paragraph("Film System Class", ref_style), Paragraph("ISO 17636-1 Table 2 (Required minimum film system class)", ref_style)])
            ref_rows.append([Paragraph("Film Overlap", ref_style), Paragraph("ISO 17636-1 Clause 6.4 (Welded joints overlap must be >= 10 mm)", ref_style)])
            
        ref_rows.append([Paragraph("Filter / Screen Recommendation", ref_style), Paragraph("ISO 17636-1 Table 1 & Annex D, ASME Sec V Art 2 (Pb screens / filters)", ref_style)])
            
        ref_table = Table(ref_rows, colWidths=[180, 320])
        ref_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cfd8dc')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#eceff1')),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        story.append(ref_table)
        story.append(Spacer(1, 20))

        # Signature Line
        sig_data = [
            ["", ""],
            ["_________________________", "_________________________"],
            ["Prepared By (Inspector)", "Approved By (Client / QA)"]
        ]
        sig_table = Table(sig_data, colWidths=[250, 250])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,2), (-1,2), 'Arial-Bold'),
            ('FONTSIZE', (0,2), (-1,2), 9),
            ('TOPPADDING', (0,1), (-1,1), 40), # Space for signatures
        ]))
        story.append(sig_table)

        # Build PDF
        try:
            doc.build(story)
            return True
        except Exception as e:
            print(f"Error building PDF: {e}")
            return False
