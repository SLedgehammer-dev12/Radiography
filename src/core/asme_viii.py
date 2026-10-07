# -*- coding: utf-8 -*-
"""
ASME Section VIII Div. 1 — UW-51 (full radiography) / UW-52 (spot radiography)
acceptance criteria for pressure-vessel welds.

Starter evaluator; limits are engineering approximations of UW-51/UW-52.
Verify against the current edition of ASME BPVC Section VIII Div. 1.
"""


class ASMEVIIIEvaluator:
    MODES = ("UW-51", "UW-52")
    # Limits below are engineering approximations of UW-51/UW-52; not a
    # substitute for the current edition of ASME BPVC Sec VIII Div. 1.
    IS_APPROXIMATION = True

    def _msg(self, lang, key, *args):
        table = {
            # {0} is the mode designator ("UW-51"/"UW-52"), already prefixed.
            "reject": ("{} {} modunda kabul edilmez.", "{} is not permitted in {} mode."),
            "por_size": ("Gözenek çapı ({:.1f} mm) {} limitini ({:.1f} mm) aşıyor.",
                         "Pore size ({:.1f} mm) exceeds the {} limit ({:.1f} mm)."),
            "por_accum": ("Gözenek yığılma ({:.1f} mm) {} limitini ({:.1f} mm) aşıyor.",
                          "Porosity accumulation ({:.1f} mm) exceeds the {} limit ({:.1f} mm)."),
            "slag_w": ("Cüruf genişliği ({:.1f} mm) {} limitini ({:.1f} mm) aşıyor.",
                       "Slag width ({:.1f} mm) exceeds the {} limit ({:.1f} mm)."),
            "undercut_d": ("Yanma oluğu derinliği ({:.2f} mm) {} limitini ({:.2f} mm) aşıyor.",
                           "Undercut depth ({:.2f} mm) exceeds the {} limit ({:.2f} mm)."),
            "accept": ("Kusur ebatları ASME VIII {} kriterleri dahilindedir. KABUL EDİLEBİLİR.",
                       "Defect dimensions are within ASME VIII {} criteria. ACCEPTABLE."),
            "label_reject_common": ("Çatlak / yetersiz ergime / yetersiz nüfuziyet",
                                    "Crack / incomplete fusion / incomplete penetration"),
            "label_burn": ("Kök yanması (Burn-through)", "Burn-through"),
        }
        text = table.get(key, ("", ""))[0 if lang == "tr" else 1]
        return text.format(*args) if args else text

    def evaluate(self, defect_type, t, length, width, accumulated, mode="UW-51", lang="tr"):
        is_accepted = True
        reasons = []
        mode = (mode or "UW-51").upper()
        if mode not in self.MODES:
            mode = "UW-51"

        # Full RT (UW-51): essentially no unacceptable indications.
        if mode == "UW-51":
            if defect_type in ("defect_crack", "defect_if", "defect_ic", "defect_ip"):
                return False, self._msg(lang, "reject", self._msg(lang, "label_reject_common"), mode)
            max_pore = 1.0
            max_slag = 1.0
            max_under = 0.4
        else:  # UW-52 spot RT: limited indications allowed
            max_pore = 3.0
            max_slag = 1.6
            max_under = 0.8

        if defect_type == "defect_porosity":
            max_dim = max(length, width)
            if max_dim > max_pore:
                is_accepted = False
                reasons.append(self._msg(lang, "por_size", max_dim, mode, max_pore))
            if accumulated > 0.02 * 300.0:
                is_accepted = False
                reasons.append(self._msg(lang, "por_accum", accumulated, mode, 0.02 * 300.0))
        elif defect_type in ("defect_slag",):
            if width > max_slag:
                is_accepted = False
                reasons.append(self._msg(lang, "slag_w", width, mode, max_slag))
        elif defect_type == "defect_undercut":
            if width > max_under:
                is_accepted = False
                reasons.append(self._msg(lang, "undercut_d", width, mode, max_under))
        elif defect_type == "defect_burn_through":
            if mode == "UW-51":
                return False, self._msg(lang, "reject", self._msg(lang, "label_burn"), mode)
            if width > 2.0:
                is_accepted = False
                reasons.append(self._msg(lang, "undercut_d", width, mode, 2.0))

        if is_accepted:
            return True, self._msg(lang, "accept", mode)
        return False, " | ".join(reasons)