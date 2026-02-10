import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from .main import ClubRecord


def _clean_website_result(raw: str) -> tuple[str, bool]:
    """Clean a result string from the website. Returns (cleaned, is_indoor).

    Strips 'i' suffix (indoor marker), '+' suffix (hand-timing),
    parenthetical notes, trailing '*' and 'p' (points marker).
    """
    # Strip parenthetical notes: "4685p (4808p med gammel tabell)" -> "4685p"
    s = raw.split("(")[0].strip()
    # Fix common typo: semicolon instead of colon in times
    s = s.replace(";", ":")
    indoor = s.endswith("i")
    if indoor:
        s = s[:-1]
    s = s.rstrip("+").rstrip("*")
    # Strip trailing 'p' only if preceded by a digit (points marker)
    if s.endswith("p") and len(s) > 1 and s[-2].isdigit():
        s = s[:-1]
    return s, indoor


def _is_relay(event: str) -> bool:
    """Check if an event name indicates a relay."""
    lower = event.lower()
    return "×" in lower or "x" in lower and ("stafett" in lower or "×" in lower) or "stafett" in lower


def _is_separator_row(texts: list[str]) -> bool:
    """Check if a row is a separator (all empty or just a dot)."""
    return all(t in ("", ".") for t in texts)


def parse_format_a(html: str, age_class: str) -> list[ClubRecord]:
    """Parse Format A pages: senior/U20/U23.

    Single table, 4 cols: [event, result, name, year].
    Blank event col = variant of previous event.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not isinstance(table, Tag):
        raise ValueError("No table found in HTML")

    records: list[ClubRecord] = []
    current_event: str | None = None
    in_relay_section = False

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue

        texts = [c.get_text(strip=True) for c in cells]

        # Detect relay section header
        if tr.find("strong"):
            strong_text = tr.find("strong").get_text(strip=True).lower()  # type: ignore[union-attr]
            if "stafett" in strong_text:
                in_relay_section = True
            continue

        if in_relay_section:
            continue

        if _is_separator_row(texts):
            continue

        event_text, result_text, name_text, year_text = texts[0], texts[1], texts[2], texts[3]

        if event_text:
            current_event = event_text

        if not current_event or not result_text or not name_text or not year_text:
            continue

        if _is_relay(current_event):
            continue

        result_clean, is_indoor = _clean_website_result(result_text)
        if not result_clean:
            continue

        # Parse year - may contain extra text like "1982 (internasjonal tikamp)"
        year_match = re.match(r"(\d{4})", year_text)
        if not year_match:
            continue

        records.append(
            ClubRecord(
                age_class=age_class,
                event=current_event,
                name=name_text,
                result=result_clean,
                year=int(year_match.group(1)),
                indoor=is_indoor,
            )
        )

    return records


def parse_format_b(html: str, gender_prefix: str) -> list[ClubRecord]:
    """Parse Format B pages: gutter/jenter.

    Single table. Event headers in <strong> tags.
    Data rows: [age, result, name, year]. Blank age = variant.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not isinstance(table, Tag):
        raise ValueError("No table found in HTML")

    records: list[ClubRecord] = []
    current_event: str | None = None
    current_age: str | None = None

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue

        texts = [c.get_text(strip=True) for c in cells]

        # Event header row: has <strong> tag
        strong = tr.find("strong")
        if strong:
            # Build event name from all strong-tagged cells or the strong text itself
            strong_texts = [s.get_text(strip=True) for s in tr.find_all("strong")]
            event_name = " ".join(t for t in strong_texts if t)
            if event_name:
                current_event = event_name
                current_age = None
            continue

        if _is_separator_row(texts):
            continue

        if not current_event or len(cells) < 4:
            continue

        age_text, result_text, name_text, year_text = texts[0], texts[1], texts[2], texts[3]

        # Update current age if provided
        if age_text:
            current_age = age_text

        if not current_age or not result_text or not name_text or not year_text:
            continue

        # Skip relay-style entries (age like G13-14, G15-16)
        if "-" in current_age and not current_age.isdigit():
            # Could be age range for relays like "G13-14"
            if re.match(r"[GJ]\d+-\d+", current_age):
                continue

        if _is_relay(current_event):
            continue

        result_clean, is_indoor = _clean_website_result(result_text)
        if not result_clean:
            continue

        # Build age class: for pure numbers (13-19), prefix with gender
        # For already-prefixed values like "G14 (7,26)", extract the age
        if re.match(r"^\d{1,2}$", current_age):
            age_class = f"{gender_prefix}{current_age}"
        elif re.match(r"^[GJ]\d+", current_age):
            # Already has prefix, like "G14 (7,26)" - just use the prefix+number
            m = re.match(r"([GJ]\d+)", current_age)
            age_class = m.group(1) if m else f"{gender_prefix}{current_age}"
        else:
            continue

        # Parse year - may contain extra text
        year_match = re.match(r"(\d{4})", year_text)
        if not year_match:
            continue

        records.append(
            ClubRecord(
                age_class=age_class,
                event=current_event,
                name=name_text,
                result=result_clean,
                year=int(year_match.group(1)),
                indoor=is_indoor,
            )
        )

    return records


_FORMAT_C_AGE_CLASS_MAP: dict[str, str] = {
    "MENN SENIOR": "MS",
    "MENN JUNIOR (U20)": "MJ20",
    "MENN JUNIOR (U23)": "MJ23",
    "KVINNER SENIOR": "KS",
    "KVINNER JUNIOR (U20)": "KJ20",
    "KVINNER JUNIOR (U23)": "KJ23",
}


def parse_format_c(html: str) -> list[ClubRecord]:
    """Parse Format C pages: short track / indoor.

    Single table with section headers (bold rows like "MENN SENIOR").
    Data rows: [event, result, name, year, (notes)].
    All records are indoor.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not isinstance(table, Tag):
        raise ValueError("No table found in HTML")

    records: list[ClubRecord] = []
    current_age_class: str | None = None
    current_event: str | None = None

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue

        texts = [c.get_text(strip=True) for c in cells]

        # Section header: row with age class name
        first_text = texts[0].strip()
        if first_text.upper() in _FORMAT_C_AGE_CLASS_MAP:
            current_age_class = _FORMAT_C_AGE_CLASS_MAP[first_text.upper()]
            current_event = None
            continue

        if _is_separator_row(texts):
            continue

        if not current_age_class or len(cells) < 4:
            continue

        event_text = texts[0]
        result_text = texts[1]
        name_text = texts[2]
        year_text = texts[3]

        if event_text:
            current_event = event_text

        if not current_event or not result_text or not name_text or not year_text:
            continue

        if _is_relay(current_event):
            continue

        result_clean, _indoor_from_suffix = _clean_website_result(result_text)
        if not result_clean:
            continue

        year_match = re.match(r"(\d{4})", year_text)
        if not year_match:
            continue

        records.append(
            ClubRecord(
                age_class=current_age_class,
                event=current_event,
                name=name_text,
                result=result_clean,
                year=int(year_match.group(1)),
                indoor=True,  # all short track records are indoor
            )
        )

    return records


# Mapping of slug -> (parser_function, parser_args)
_PAGE_CONFIG: list[tuple[str, str, dict[str, str]]] = [
    # Format A pages: (slug, format, {kwarg: value})
    ("klubbrekorder-menn-senior", "a", {"age_class": "MS"}),
    ("klubbrekorder-kvinner-senior", "a", {"age_class": "KS"}),
    ("klubbrekorder-menn-junior-u23", "a", {"age_class": "MJ23"}),
    ("klubbrekorder-kvinner-junior-u23", "a", {"age_class": "KJ23"}),
    ("klubbrekorder-menn-junior-u20", "a", {"age_class": "MJ20"}),
    ("klubbrekorder-kvinner-junior-u20", "a", {"age_class": "KJ20"}),
    # Format B pages
    ("klubbrekorder-gutter", "b", {"gender_prefix": "G"}),
    ("klubbrekorder-jenter", "b", {"gender_prefix": "J"}),
    # Format C pages
    ("klubbrekorder-menn-short-track-innendørs", "c", {}),
    ("klubbrekorder-kvinner-short-track-innendørs", "c", {}),
]


def parse_all_website_pages(data_dir: Path) -> list[ClubRecord]:
    """Parse all downloaded website HTML files and return combined records."""
    all_records: list[ClubRecord] = []
    for slug, fmt, kwargs in _PAGE_CONFIG:
        path = data_dir / f"{slug}.html"
        html = path.read_text(encoding="utf-8")
        if fmt == "a":
            records = parse_format_a(html, **kwargs)
        elif fmt == "b":
            records = parse_format_b(html, **kwargs)
        elif fmt == "c":
            records = parse_format_c(html)
        else:
            raise ValueError(f"Unknown format: {fmt}")
        print(f"  {slug}: {len(records)} records")
        all_records.extend(records)
    return all_records
