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

        # Translation of messages
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
            # Max individual size is smaller of 3.2 mm or 25% of t
            porosity_limit = min(3.2, 0.25 * t)
            max_dim = max(length, width)
            if max_dim > porosity_limit:
                is_accepted = False
                reasons.append(lang_msgs["por_size_reject"].format(max_dim, porosity_limit))
            if accumulated > 12.7:
                is_accepted = False
                reasons.append(lang_msgs["por_accum_reject"].format(accumulated))

        if is_accepted:
            reason_str = lang_msgs["accept_msg"]
        else:
            reason_str = " | ".join(reasons)

        return is_accepted, reason_str
