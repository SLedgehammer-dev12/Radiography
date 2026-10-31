# -*- coding: utf-8 -*-
"""
ISO 10893-7:2019 / ISO 10893-6:2011 Clause 10 Acceptance limits for weld seam imperfections.
Applies to automated fusion arc-welded steel tubes (longitudinal and helical seams).
"""


class ISO10893Evaluator:
    """Evaluates weld imperfections against ISO 10893 Clause 10 acceptance criteria."""

    IS_APPROXIMATION = False

    def _msg(self, lang, key, *args):
        table = {
            "crack": (
                "ISO 10893-7 Madde 10.2: Çatlaklar kabul edilmez (RED).",
                "ISO 10893-7 Clause 10.2: Cracks are not acceptable (REJECT)."
            ),
            "ip": (
                "ISO 10893-7 Madde 10.2: Yetersiz nüfuziyet (incomplete penetration) kabul edilmez (RED).",
                "ISO 10893-7 Clause 10.2: Incomplete penetration is not acceptable (REJECT)."
            ),
            "if": (
                "ISO 10893-7 Madde 10.2: Erime noksanlığı (lack of fusion) kabul edilmez (RED).",
                "ISO 10893-7 Clause 10.2: Lack of fusion is not acceptable (REJECT)."
            ),
            "burn": (
                "ISO 10893-7: Kök yanması / yanma (burn-through) kabul edilmez (RED).",
                "ISO 10893-7: Burn-through is not acceptable (REJECT)."
            ),
            "por_size": (
                "ISO 10893-7 Madde 10.3: Dairesel cüruf/gözenek çapı ({:.1f} mm) azami limiti ({:.1f} mm) aşıyor (RED).",
                "ISO 10893-7 Clause 10.3: Circular slag/pore diameter ({:.1f} mm) exceeds limit ({:.1f} mm) (REJECT)."
            ),
            "por_accum": (
                "ISO 10893-7 Madde 10.3: Gözenek toplam yığılma çapı ({:.1f} mm) izin verilen sınırı ({:.1f} mm) aşıyor (RED).",
                "ISO 10893-7 Clause 10.3: Accumulated porosity diameter ({:.1f} mm) exceeds limit ({:.1f} mm) (REJECT)."
            ),
            "slag_len": (
                "ISO 10893-7 Madde 10.4: Uzamış cüruf boyu ({:.1f} mm) azami limiti ({:.1f} mm) aşıyor (RED).",
                "ISO 10893-7 Clause 10.4: Elongated slag length ({:.1f} mm) exceeds limit ({:.1f} mm) (REJECT)."
            ),
            "slag_width": (
                "ISO 10893-7 Madde 10.4: Uzamış cüruf genişliği ({:.1f} mm) azami 1.5 mm limitini aşıyor (RED).",
                "ISO 10893-7 Clause 10.4: Elongated slag width ({:.1f} mm) exceeds 1.5 mm limit (REJECT)."
            ),
            "slag_accum": (
                "ISO 10893-7 Madde 10.4: Uzamış cüruf toplam yığılma boyu ({:.1f} mm) azami 12.0 mm limitini aşıyor (RED).",
                "ISO 10893-7 Clause 10.4: Accumulated slag length ({:.1f} mm) exceeds 12.0 mm limit (REJECT)."
            ),
            "undercut_depth": (
                "ISO 10893-7 Madde 10.5: Yanma çentiği (undercut) derinliği ({:.2f} mm) izin verilen azami limiti ({:.2f} mm) aşıyor (RED).",
                "ISO 10893-7 Clause 10.5: Undercut depth ({:.2f} mm) exceeds permitted limit ({:.2f} mm) (REJECT)."
            ),
            "undercut_len": (
                "ISO 10893-7 Madde 10.5: Yanma çentiği uzunluğu ({:.1f} mm) T/2 limitini ({:.1f} mm) aşıyor (RED).",
                "ISO 10893-7 Clause 10.5: Undercut length ({:.1f} mm) exceeds T/2 limit ({:.1f} mm) (REJECT)."
            ),
            "accept": (
                "Kusur boyutları ISO 10893-7 Madde 10 sınırları dahilindedir (KABUL EDİLEBİLİR).",
                "Imperfection dimensions are within ISO 10893-7 Clause 10 acceptance limits (ACCEPTABLE)."
            ),
        }
        text = table.get(key, ("", ""))[0 if lang == "tr" else 1]
        return text.format(*args) if args else text

    def evaluate(self, defect_type, t, length, width, accumulated, level="E3", lang="tr"):
        """Evaluates defect parameters against ISO 10893 Clause 10 (E3: Standard, E2: Enhanced)."""
        t = max(0.1, float(t))
        length = float(length)
        width = float(width)
        accumulated = float(accumulated)

        # Clause 10.2: Cracks, incomplete penetration, lack of fusion not acceptable
        if defect_type in ("crack", "defect_crack"):
            return False, self._msg(lang, "crack")
        if defect_type in ("ip", "defect_ip", "incomplete_penetration"):
            return False, self._msg(lang, "ip")
        if defect_type in ("if", "defect_if", "lack_of_fusion"):
            return False, self._msg(lang, "if")
        if defect_type in ("burn", "defect_burn_through"):
            return False, self._msg(lang, "burn")

        # Clause 10.3: Circular slag and gas pockets (porosities)
        if defect_type in ("porosity", "defect_porosity", "gas_pocket"):
            dia = max(length, width)
            max_dia = min(2.0, t / 4.0) if level == "E2" else min(3.0, t / 3.0)
            if dia > max_dia:
                return False, self._msg(lang, "por_size", dia, max_dia)
            max_accum = min(4.0, 0.35 * t) if level == "E2" else min(6.0, 0.5 * t)
            if accumulated > max_accum:
                return False, self._msg(lang, "por_accum", accumulated, max_accum)
            return True, self._msg(lang, "accept")

        # Clause 10.4: Elongated slag inclusions
        if defect_type in ("slag", "defect_slag"):
            max_len = min(6.0, t / 2.0) if level == "E2" else min(12.0, t)
            if length > max_len:
                return False, self._msg(lang, "slag_len", length, max_len)
            max_w = 1.0 if level == "E2" else 1.5
            if width > max_w:
                return False, self._msg(lang, "slag_width", width)
            max_acc = 6.0 if level == "E2" else 12.0
            if accumulated > max_acc:
                return False, self._msg(lang, "slag_accum", accumulated)
            return True, self._msg(lang, "accept")

        # Clause 10.5: Undercut
        if defect_type in ("undercut", "defect_undercut"):
            # depth is passed in width or explicit depth
            depth = width
            if depth > 0.5 or depth > (0.10 * t):
                return False, self._msg(lang, "undercut_depth", depth, min(0.5, 0.10 * t))
            if depth > 0.4:
                # Can only be accepted if length <= T/2
                if length > (t / 2.0):
                    return False, self._msg(lang, "undercut_len", length, t / 2.0)
            return True, self._msg(lang, "accept")

        # Unknown / other defaults to acceptable if dimensions non-zero
        return True, self._msg(lang, "accept")
