# -*- coding: utf-8 -*-


class API1104Evaluator:
    def __init__(self):
        pass

    def evaluate(self, defect_type, t, length, width, accumulated, lang="tr"):
        """
        Evaluates a weld defect based on API 1104 Section 9 criteria.
        Returns: (is_accepted, reason_str)
        """
        is_accepted = True
        reasons = []

        messages = {
            "tr": {
                "crack_reject": "Çatlaklar (Cracks) ebatlarına bakılmaksızın API 1104 Madde 9.3.10 gereği REDDEDİLİR.",
                "ip_len_reject": "Yetersiz Nüfuziyet (IP) tekil uzunluğu 25.4 mm (1 inç) limitini aşıyor ({:.1f} mm > 25.4 mm).",
                "ip_accum_reject": "Yetersiz Nüfuziyet (IP) 300 mm'deki toplam yığılma uzunluğu 25.4 mm limitini aşıyor ({:.1f} mm > 25.4 mm).",
                "if_len_reject": "Yetersiz Ergime (IF) tekil uzunluğu 25.4 mm (1 inç) limitini aşıyor ({:.1f} mm > 25.4 mm).",
                "if_accum_reject": "Yetersiz Ergime (IF) 300 mm'deki toplam yığılma uzunluğu 25.4 mm limitini aşıyor ({:.1f} mm > 25.4 mm).",
                "ic_len_reject": "Yetersiz İç Kep (IC) tekil uzunluğu 50.8 mm (2 inç) limitini aşıyor ({:.1f} mm > 50.8 mm).",
                "ic_accum_reject": "Yetersiz İç Kep (IC) 300 mm'deki toplam yığılma uzunluğu 50.8 mm limitini aşıyor ({:.1f} mm > 50.8 mm).",
                "por_size_reject": "Tekil gözenek (Porosity) boyutu limitini aşıyor ({:.1f} mm > {:.2f} mm - 3.2 mm veya %25 t).",
                "por_accum_reject": "Gözenek (Porosity) 300 mm'deki toplam yığılma uzunluğu 12.7 mm (0.5 inç) limitini aşıyor ({:.1f} mm > 12.7 mm).",
                "por_scattered_reject": "Yayılmış gözeneklilik (Scattered Porosity) alan oranı limitini aşıyor (%{:.1f} > %{:.1f}).",
                "slag_len_reject": "Cüruf Kalıntısı (Slag) tekil uzunluğu 25.4 mm (1 inç) limitini aşıyor ({:.1f} mm > 25.4 mm).",
                "slag_width_reject": "Cüruf Kalıntısı (Slag) genişliği limitini aşıyor ({:.1f} mm > {:.2f} mm).",
                "slag_accum_reject": "Cüruf Kalıntısı (Slag) 300 mm'deki toplam yığılma uzunluğu 12.7 mm (0.5 inç) limitini aşıyor ({:.1f} mm > 12.7 mm).",
                "undercut_depth_reject": "Yanma Oluğu (Undercut) derinliği limitini aşıyor ({:.2f} mm > {:.2f} mm).",
                "undercut_len_reject": "Yanma Oluğu (Undercut) tekil uzunluğu 25.4 mm (1 inç) limitini aşıyor ({:.1f} mm > 25.4 mm).",
                "undercut_accum_reject": "Yanma Oluğu (Undercut) 300 mm'deki toplam yığılma uzunluğu 50.8 mm (2 inç) limitini aşıyor ({:.1f} mm > 50.8 mm).",
                "burn_width_reject": "Kök Yanması (Burn-Through) genişliği 6.4 mm (0.25 inç) limitini aşıyor ({:.1f} mm > 6.4 mm).",
                "burn_len_reject": "Kök Yanması (Burn-Through) tekil uzunluğu 25.4 mm (1 inç) limitini aşıyor ({:.1f} mm > 25.4 mm).",
                "burn_accum_reject": "Kök Yanması (Burn-Through) 300 mm'deki toplam yığılma uzunluğu 25.4 mm (1 inç) limitini aşıyor ({:.1f} mm > 25.4 mm).",
                "accept_msg": "Hata ebatları API 1104 limitleri dahilindedir. KABUL EDİLEBİLİR.",
            },
            "en": {
                "crack_reject": "Cracks are unacceptable regardless of size according to API 1104 Clause 9.3.10.",
                "ip_len_reject": "Incomplete Penetration (IP) individual length exceeds the 25.4 mm (1 inch) limit ({:.1f} mm > 25.4 mm).",
                "ip_accum_reject": "Incomplete Penetration (IP) accumulated length in 300 mm exceeds the 25.4 mm limit ({:.1f} mm > 25.4 mm).",
                "if_len_reject": "Incomplete Fusion (IF) individual length exceeds the 25.4 mm (1 inch) limit ({:.1f} mm > 25.4 mm).",
                "if_accum_reject": "Incomplete Fusion (IF) accumulated length in 300 mm exceeds the 25.4 mm limit ({:.1f} mm > 25.4 mm).",
                "ic_len_reject": "Incomplete Penetration of Weld Root (IC) individual length exceeds the 50.8 mm (2 inches) limit ({:.1f} mm > 50.8 mm).",
                "ic_accum_reject": "Incomplete Penetration of Weld Root (IC) accumulated length in 300 mm exceeds the 50.8 mm limit ({:.1f} mm > 50.8 mm).",
                "por_size_reject": "Individual pore size exceeds the limit ({:.1f} mm > {:.2f} mm - 3.2 mm or 25% of t).",
                "por_accum_reject": "Porosity accumulated length in 300 mm exceeds the 12.7 mm (0.5 inch) limit ({:.1f} mm > 12.7 mm).",
                "por_scattered_reject": "Scattered porosity area ratio exceeds the limit (%{:.1f} > %{:.1f}).",
                "slag_len_reject": "Slag Inclusion (Slag) individual length exceeds the 25.4 mm (1 inch) limit ({:.1f} mm > 25.4 mm).",
                "slag_width_reject": "Slag Inclusion (Slag) width exceeds the limit ({:.1f} mm > {:.2f} mm).",
                "slag_accum_reject": "Slag Inclusion (Slag) accumulated length in 300 mm exceeds the 12.7 mm (0.5 inch) limit ({:.1f} mm > 12.7 mm).",
                "undercut_depth_reject": "Undercut depth exceeds the limit ({:.2f} mm > {:.2f} mm).",
                "undercut_len_reject": "Undercut individual length exceeds the 25.4 mm (1 inch) limit ({:.1f} mm > 25.4 mm).",
                "undercut_accum_reject": "Undercut accumulated length in 300 mm exceeds the 50.8 mm (2 inches) limit ({:.1f} mm > 50.8 mm).",
                "burn_width_reject": "Burn-Through width exceeds the 6.4 mm (0.25 inch) limit ({:.1f} mm > 6.4 mm).",
                "burn_len_reject": "Burn-Through individual length exceeds the 25.4 mm (1 inch) limit ({:.1f} mm > 25.4 mm).",
                "burn_accum_reject": "Burn-Through accumulated length in 300 mm exceeds the 25.4 mm (1 inch) limit ({:.1f} mm > 25.4 mm).",
                "accept_msg": "Defect dimensions are within API 1104 limits. ACCEPTABLE.",
            }
        }

        lang_msgs = messages.get(lang, messages["tr"])

        if defect_type == "defect_crack":
            is_accepted = False
            reasons.append(lang_msgs["crack_reject"])

        elif defect_type == "defect_ip":
            if length > 25.4:
                is_accepted = False
                reasons.append(lang_msgs["ip_len_reject"].format(length))
            if accumulated > 25.4:
                is_accepted = False
                reasons.append(lang_msgs["ip_accum_reject"].format(accumulated))

        elif defect_type == "defect_if":
            if length > 25.4:
                is_accepted = False
                reasons.append(lang_msgs["if_len_reject"].format(length))
            if accumulated > 25.4:
                is_accepted = False
                reasons.append(lang_msgs["if_accum_reject"].format(accumulated))

        elif defect_type == "defect_ic":
            if length > 50.8:
                is_accepted = False
                reasons.append(lang_msgs["ic_len_reject"].format(length))
            if accumulated > 50.8:
                is_accepted = False
                reasons.append(lang_msgs["ic_accum_reject"].format(accumulated))

        elif defect_type == "defect_porosity":
            porosity_limit = min(3.2, 0.25 * t)
            max_dim = max(length, width)
            if max_dim > porosity_limit:
                is_accepted = False
                reasons.append(lang_msgs["por_size_reject"].format(max_dim, porosity_limit))
            if accumulated > 12.7:
                is_accepted = False
                reasons.append(lang_msgs["por_accum_reject"].format(accumulated))
            if max_dim < 0.5 * porosity_limit and accumulated > 6.0:
                scattered_ratio = accumulated / (300.0 / 0.3)
                if scattered_ratio > 0.15:
                    is_accepted = False
                    reasons.append(lang_msgs["por_scattered_reject"].format(scattered_ratio * 100, 15.0))

        elif defect_type == "defect_slag":
            slag_width_limit = 1.6 if t <= 12.7 else 3.2
            if width > slag_width_limit:
                is_accepted = False
                reasons.append(lang_msgs["slag_width_reject"].format(width, slag_width_limit))
            if length > 25.4:
                is_accepted = False
                reasons.append(lang_msgs["slag_len_reject"].format(length))
            if accumulated > 12.7:
                is_accepted = False
                reasons.append(lang_msgs["slag_accum_reject"].format(accumulated))

        elif defect_type == "defect_undercut":
            undercut_depth_limit = 0.4 if t <= 12.7 else 0.8
            if width > undercut_depth_limit:
                is_accepted = False
                reasons.append(lang_msgs["undercut_depth_reject"].format(width, undercut_depth_limit))
            if length > 25.4:
                is_accepted = False
                reasons.append(lang_msgs["undercut_len_reject"].format(length))
            if accumulated > 50.8:
                is_accepted = False
                reasons.append(lang_msgs["undercut_accum_reject"].format(accumulated))

        elif defect_type == "defect_burn_through":
            if width > 6.4:
                is_accepted = False
                reasons.append(lang_msgs["burn_width_reject"].format(width))
            if length > 25.4:
                is_accepted = False
                reasons.append(lang_msgs["burn_len_reject"].format(length))
            if accumulated > 25.4:
                is_accepted = False
                reasons.append(lang_msgs["burn_accum_reject"].format(accumulated))

        if is_accepted:
            reason_str = lang_msgs["accept_msg"]
        else:
            reason_str = " | ".join(reasons)

        return is_accepted, reason_str

    def evaluate_accumulation(self, defects, weld_length=300.0, lang="tr"):
        """
        API 1104 §9.3.12: Cross-defect accumulation check.
        Sum of all defect lengths in any 300 mm weld length must not exceed 8% of weld length.
        
        defects: list of (defect_type, length) tuples
        weld_length: reference length in mm (default 300 mm = 12 inches)
        Returns: (is_accepted, reason_str)
        """
        total_length = sum(length for _, length in defects)
        limit = 0.08 * weld_length

        if total_length > limit:
            messages = {
                "tr": "API 1104 Madde 9.3.12: Toplam hata yığılma uzunluğu ({:.1f} mm) kaynak boyunun %8'ini ({:.1f} mm) aşıyor.",
                "en": "API 1104 Clause 9.3.12: Total accumulated defect length ({:.1f} mm) exceeds 8% of weld length ({:.1f} mm).",
            }
            msg = messages.get(lang, messages["en"])
            return False, msg.format(total_length, limit)

        return True, ""
