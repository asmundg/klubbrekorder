import re


# Standard hurdle heights: meters -> cm mapping
# These are the official IAAF hurdle heights
_HURDLE_M_TO_CM: dict[str, str] = {
    "0,68": "68,0",
    "0,76": "76,2",
    "0,84": "84,0",
    "0,91": "91,4",
}


def _weight_to_kg(value: str, unit: str) -> str:
    """Convert a weight value to kg with consistent formatting.

    >>> _weight_to_kg("600", "gram")
    '0,6'
    >>> _weight_to_kg("7,26", "kg")
    '7,26'
    """
    if unit in ("gram", "g"):
        grams = float(value.replace(",", "."))
        kg = grams / 1000
    else:
        kg = float(value.replace(",", "."))

    # Format with comma separator, minimal decimals but at least one
    if kg == int(kg):
        return f"{int(kg)},0"
    formatted = f"{kg:.2f}".rstrip("0")
    if formatted.endswith("."):
        formatted += "0"
    return formatted.replace(".", ",")


def normalize_event(raw: str) -> str:
    """Normalize an event name to a canonical form for comparison.

    Both website and federation event names should normalize to the same string.
    """
    s = raw.strip()

    # Multi-event (check early, before distance parsing eats "4 Kamp")
    lower = s.lower()
    if "kast 5 kamp" in lower:
        return "Kast 5-kamp"
    if "firekamp" in lower or "4 kamp" in lower or "4kamp" in lower or "4-kamp" in lower:
        return "4-kamp"
    if "5 kamp" in lower or "5kamp" in lower or "5-kamp" in lower or "femkamp" in lower:
        return "5-kamp"
    if "7 kamp" in lower or "7kamp" in lower or "7-kamp" in lower or "syvkamp" in lower:
        return "7-kamp"
    if "10 kamp" in lower or "10kamp" in lower or "10-kamp" in lower or "tikamp" in lower:
        return "10-kamp"

    # Halvmaraton/Marathon
    if lower in ("halvmaraton", "halvmarathon"):
        return "Halvmaraton"
    if lower in ("maraton", "marathon"):
        return "Maraton"

    # Mile
    if lower == "1 mile":
        return "1 mile"

    # Kappgang events (must come before generic distance matching)
    # "Kappgang 3000 meter" / "Kappgang 3000m" / "3000m kappgang" / "Kappg. 10000m"
    m = re.match(r"^(?:Kappg\.\s+|Kappgang\s+)(\d[\d\s]*)(?:meter|m)$", s, re.IGNORECASE)
    if m:
        return f"Kappgang {m.group(1).replace(' ', '')}m"
    m = re.match(r"^(\d+)m?\s+kappg?ang$", s, re.IGNORECASE)
    if m:
        return f"Kappgang {m.group(1)}m"
    m = re.match(r"^(?:Kappg\.\s+|Kappgang\s+)(\d+)\s*km\s*(?:landevei|vei)?$", s, re.IGNORECASE)
    if m:
        return f"Kappgang {m.group(1)}km"

    # Steeplechase: "3000 meter hinder (91,4cm)" / "3000m hinder" / "3000m hin" / "3000mH 0,91" / "2000m hin (0,91)"
    m = re.match(
        r"^(\d+)\s*(?:meter\s+hinder|m\s*(?:hinder|hin|H))\s*(?:\(?(\d+(?:,\d+)?)\s*(?:cm)?\)?)?$", s
    )
    if m:
        dist = m.group(1)
        height = m.group(2)
        if height:
            # Normalize height: if < 10, it's meters -> convert to cm
            height_f = float(height.replace(",", "."))
            if height_f < 10:
                height = _HURDLE_M_TO_CM.get(height, height)
            return f"{dist}m hinder {height}"
        return f"{dist}m hinder"

    # "1500m H 0,76" format
    m = re.match(r"^(\d+)m?\s*H\s+(\d+,\d+)$", s)
    if m:
        height = m.group(2)
        height_f = float(height.replace(",", "."))
        if height_f < 10:
            height = _HURDLE_M_TO_CM.get(height, height)
        return f"{m.group(1)}m hinder {height}"

    # Hurdles: "110 meter hekk (106,7cm)" / "60m HK (100 cm)" / "80m HK 0,76" / "60 meter hekk"
    m = re.match(
        r"^(\d+)\s*(?:meter\s+hekk|m\s*HK)\s*(?:\(?\s*(\d+(?:,\d+)?)\s*(?:cm)?\s*\)?)?$", s
    )
    if m:
        dist = m.group(1)
        height = m.group(2)
        if height:
            height_f = float(height.replace(",", "."))
            if height_f < 10:
                height = _HURDLE_M_TO_CM.get(height, height)
            # Strip trailing ,0 for whole numbers: "100,0" -> "100"
            height = re.sub(r",0$", "", height)
            return f"{dist}m HK {height}"
        return f"{dist}m HK"

    # Distance events: "100 meter" / "100m" / "10 000m" / "10000 meter"
    m = re.match(r"^(\d[\d\s]*)\s*(?:meter|m)$", s)
    if m:
        return f"{m.group(1).replace(' ', '')}m"

    # Road distance: "10 km"
    m = re.match(r"^(\d+)\s*km$", s)
    if m:
        return f"{m.group(1)}km"

    # Høyde / Lengde / Stav / Tresteg
    if lower in ("høyde",):
        return "Høyde"
    if lower in ("høyde u/t", "høyde uten tilløp"):
        return "Høyde u/t"
    if lower in ("lengde",):
        return "Lengde"
    if lower in ("lengde u/t", "lengde uten tilløp"):
        return "Lengde u/t"
    if lower in ("lengde (sone 0,5m)",):
        return "Lengde"
    if lower in ("stav",):
        return "Stav"
    if lower in ("tresteg",):
        return "Tresteg"
    if lower in ("tresteg (sone 0,5m)",):
        return "Tresteg"

    # Throws with weight
    # Patterns: "Kule 7,26kg" / "Kule (7,26kg)" / "Kule 7,0kg" / "Spyd 600gram" / "Slegge 3,0kg/110cm"
    # Also: "VektKast 15,88Kg" / "VektKast4,0kg" (no space)
    for throw in ("Kule", "Diskos", "Slegge", "Spyd", "VektKast", "Vektkast"):
        pattern = rf"^{throw}\s*\(?(\d+(?:,\d+)?)\s*(kg|gram)(?:/[\d,]+cm)?\)?(?:\s+\(.*\))?$"
        m = re.match(pattern, s, re.IGNORECASE)
        if m:
            weight = _weight_to_kg(m.group(1), m.group(2).lower())
            name = "Vektkast" if throw.lower() == "vektkast" else throw.capitalize()
            return f"{name} {weight}kg"
        # Bare name without weight
        if lower == throw.lower():
            name = "Vektkast" if throw.lower() == "vektkast" else throw.capitalize()
            return name

    # Spyd with parenthetical notes but weight in "g" not "gram": "Spyd 800g"
    m = re.match(r"^(Spyd|Diskos)\s+(\d+)g(?:\s+\(.*\))?$", s, re.IGNORECASE)
    if m:
        weight = _weight_to_kg(m.group(2), "gram")
        return f"{m.group(1).capitalize()} {weight}kg"

    # Spyd/Diskos with "X kg" (space before kg)
    m = re.match(r"^(Kule|Diskos|Slegge|Spyd)\s+(\d+(?:,\d+)?)\s+kg$", s, re.IGNORECASE)
    if m:
        weight = _weight_to_kg(m.group(2), "kg")
        return f"{m.group(1).capitalize()} {weight}kg"

    # Slegge/Spyd with extra format: "Slegge 3,0Kg (119,5cm)" / "Slegge 7,26kg/121,5cm"
    m = re.match(r"^(Slegge|Spyd)\s+(\d+(?:,\d+)?)\s*[Kk]g(?:/[\d,]+cm)?(?:\s+\([\d,]+cm\))?$", s)
    if m:
        weight = _weight_to_kg(m.group(2), "kg")
        return f"{m.group(1).capitalize()} {weight}kg"

    # "Spyd (800g)" / "Diskos (2,0kg)" - parenthesized weight
    m = re.match(r"^(Kule|Diskos|Slegge|Spyd)\s+\((\d+(?:,\d+)?)\s*(kg|gram|g)\)$", s, re.IGNORECASE)
    if m:
        weight = _weight_to_kg(m.group(2), m.group(3).lower())
        return f"{m.group(1).capitalize()} {weight}kg"

    # Spyd with special suffix: "Spyd <1999" / "Spyd >1999"
    m = re.match(r"^Spyd\s*[<>]\d+$", s)
    if m:
        return "Spyd"

    # "60 meter" that didn't match earlier (e.g. in "60 meter" from jenter website)
    m = re.match(r"^(\d+)\s+meter$", s)
    if m:
        return f"{m.group(1)}m"

    # If nothing matched, return as-is
    return s
