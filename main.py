import re
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Optional

import typer
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel


class ClubRecord(BaseModel):
    age_class: str
    event: str
    name: str
    result: str
    year: int
    indoor: bool = False


def abbreviate_age_class(raw: str) -> str:
    """Map e.g. 'Gutter 13' -> 'G13', 'Menn Senior' -> 'MS', 'Menn veteran 30-34' -> 'MV30'."""
    raw = raw.strip()
    prefix_map: dict[str, str] = {
        "Gutter": "G",
        "Jenter": "J",
        "Menn Senior": "MS",
        "Kvinner Senior": "KS",
        "Menn Junior": "MJ",
        "Kvinner Junior": "KJ",
        "Menn veteran": "MV",
        "Kvinner veteran": "KV",
    }
    for long, short in prefix_map.items():
        if raw.startswith(long):
            rest = raw[len(long):].strip()
            if not rest:
                return short
            # For veterans "30-34" -> take first number "30"
            age_match = re.match(r"(\d+)", rest)
            if age_match:
                return short + age_match.group(1)
            # For "18/19" -> "18"
            slash_match = re.match(r"(\d+)/", rest)
            if slash_match:
                return short + slash_match.group(1)
            return short + rest
    raise ValueError(f"Unknown age class: {raw}")


def clean_result(raw: str) -> str:
    """Strip wind info and hand-timing marker: '7,94(+1,8)' -> '7,94', '4,30,98+' -> '4,30,98'."""
    return raw.split("(")[0].strip().rstrip("+")


def parse_year(date_str: str) -> int:
    """Parse 'dd.mm.yy' -> 4-digit year. Pivot: >=50 -> 19xx, <50 -> 20xx."""
    yy = int(date_str.split(".")[-1])
    return 1900 + yy if yy >= 50 else 2000 + yy


def parse_records(html: str, *, indoor: bool = False) -> list[ClubRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[ClubRecord] = []

    current_age_class: str | None = None
    current_event: str | None = None
    # Track whether we've already captured the record for the current event
    event_captured = False
    # Track if last heading was h5/h6 (sub-section to skip)
    in_skip_section = False

    for tag in soup.descendants:
        if not isinstance(tag, Tag):
            continue

        if tag.name == "h2":
            text = tag.get_text(strip=True)
            if text:
                current_age_class = text
                current_event = None
                event_captured = False
                in_skip_section = False

        elif tag.name == "h4":
            text = tag.get_text(strip=True)
            if text:
                current_event = text
                event_captured = False
                in_skip_section = False

        elif tag.name in ("h5", "h6"):
            in_skip_section = True

        elif tag.name == "table" and not in_skip_section and not event_captured:
            if current_age_class is None or current_event is None:
                continue

            # Find first data row (with <td> cells)
            for tr in tag.find_all("tr"):
                cells = tr.find_all("td")
                if not cells or len(cells) < 6:
                    continue

                result_raw = cells[0].get_text(strip=True)
                if result_raw == "-----":
                    break

                a_tag = cells[1].find("a")
                if a_tag is None:
                    break

                name = a_tag.get_text(strip=True)
                date_str = cells[5].get_text(strip=True)

                records.append(
                    ClubRecord(
                        age_class=abbreviate_age_class(current_age_class),
                        event=current_event,
                        name=name,
                        result=clean_result(result_raw),
                        year=parse_year(date_str),
                        indoor=indoor,
                    )
                )
                event_captured = True
                break

    return records


EVENT_TYPE_ORDER: list[str] = [
    "Sprint",
    "Mellomdistanse",
    "Langdistanse",
    "Hekk & hinder",
    "Kappgang",
    "Høyde",
    "Stav",
    "Lengde",
    "Tresteg",
    "Kule",
    "Diskos",
    "Slegge",
    "Spyd",
    "Vektkast",
    "Mangekamp",
]

_SPRINT_DISTANCES = {"60", "100", "200", "300", "400"}
_MIDDLE_DISTANCES = {"600", "800", "1000", "1500"}
_LONG_DISTANCES = {"2000", "3000", "5000", "10000"}


def classify_event(event: str) -> str:
    """Classify an event name into a category."""
    lower = event.lower()

    # Check specific keywords first (order matters)
    if "hekk" in lower or "hinder" in lower:
        return "Hekk & hinder"
    if "kappgang" in lower:
        return "Kappgang"
    if "kamp" in lower:
        return "Mangekamp"
    if "høyde" in lower:
        return "Høyde"
    if "stav" in lower:
        return "Stav"
    if "lengde" in lower:
        return "Lengde"
    if "tresteg" in lower:
        return "Tresteg"
    if "kule" in lower:
        return "Kule"
    if "diskos" in lower:
        return "Diskos"
    if "slegge" in lower:
        return "Slegge"
    if "spyd" in lower:
        return "Spyd"
    if "vektkast" in lower:
        return "Vektkast"
    if "halvmaraton" in lower:
        return "Langdistanse"
    if "mile" in lower:
        return "Mellomdistanse"

    # Distance-based classification
    m = re.match(r"(\d+)\s*meter", lower)
    if m:
        dist = m.group(1)
        if dist in _SPRINT_DISTANCES:
            return "Sprint"
        if dist in _MIDDLE_DISTANCES:
            return "Mellomdistanse"
        if dist in _LONG_DISTANCES:
            return "Langdistanse"

    raise ValueError(f"Cannot classify event: {event}")


_LOWER_IS_BETTER_CATEGORIES = {
    "Sprint", "Mellomdistanse", "Langdistanse", "Hekk & hinder", "Kappgang",
}


def parse_result_value(result: str) -> float:
    """Parse a result string like '7,94', '1:23,45', '1,05,40' into a comparable float."""
    # Normalize: colon or comma-separated minutes (e.g. "1:23,45" or "1,05,40")
    normalized = result.replace(",", ".")
    if ":" in normalized:
        parts = normalized.split(":")
        return float(parts[0]) * 60 + float(parts[1])
    # 3-part dot format: m.ss.hh (e.g. "1.05.40" = 1min 05.40s)
    dot_parts = normalized.split(".")
    if len(dot_parts) == 3:
        return int(dot_parts[0]) * 60 + int(dot_parts[1]) + int(dot_parts[2]) / 100
    return float(normalized)


def pick_best_record(records: list[ClubRecord], category: str) -> ClubRecord:
    """Pick the best record from a list — lowest time or highest distance/points."""
    lower_better = category in _LOWER_IS_BETTER_CATEGORIES
    return min(records, key=lambda r: parse_result_value(r.result) * (1 if lower_better else -1))


def age_class_sort_key(abbrev: str) -> tuple[int, int]:
    """Return a sortable tuple so age classes print in logical order.

    Order: G (boys) by age, J (girls) by age, MJ, MS, KJ, KS, MV by age, KV by age.
    """
    order_map: dict[str, int] = {
        "G": 0,
        "J": 1,
        "MJ": 2,
        "MS": 3,
        "KJ": 4,
        "KS": 5,
        "MV": 6,
        "KV": 7,
    }

    # Extract prefix and optional number
    m = re.match(r"([A-Z]+)(\d*)", abbrev)
    if not m:
        return (99, 0)

    prefix = m.group(1)
    num = int(m.group(2)) if m.group(2) else 0
    group = order_map.get(prefix, 99)
    return (group, num)


def load_records(*, outdoor: bool, indoor: bool) -> list[ClubRecord]:
    do_outdoor = not indoor or outdoor
    do_indoor = not outdoor or indoor

    all_records: list[ClubRecord] = []
    if do_outdoor:
        all_records.extend(parse_records(Path("outdoor.html").read_text(), indoor=False))
    if do_indoor:
        all_records.extend(parse_records(Path("indoor.html").read_text(), indoor=True))
    return all_records


def best_records(records: list[ClubRecord]) -> list[ClubRecord]:
    """Deduplicate to one best record per (event, age_class)."""
    grouped: dict[str, dict[str, dict[str, list[ClubRecord]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for r in records:
        cat = classify_event(r.event)
        grouped[cat][r.event][r.age_class].append(r)

    result: list[ClubRecord] = []
    for cat in EVENT_TYPE_ORDER:
        for event_name in sorted(grouped.get(cat, {})):
            for ac in sorted(grouped[cat][event_name], key=age_class_sort_key):
                result.append(pick_best_record(grouped[cat][event_name][ac], cat))
    return result


def print_grouped(records: list[ClubRecord]) -> None:
    current_cat: str | None = None
    current_event: str | None = None
    for r in records:
        cat = classify_event(r.event)
        if cat != current_cat:
            current_cat = cat
            current_event = None
            print(f"\n=== {cat} ===\n")
        if r.event != current_event:
            current_event = r.event
            print(r.event)
        suffix = "i" if r.indoor else ""
        print(f"  {r.age_class:6s} {r.name:30s} {r.result:>10s}{suffix}  {r.year}")
    print()


app = typer.Typer()


@app.command()
def main(
    outdoor: Annotated[bool, typer.Option(help="Parse outdoor records only")] = False,
    indoor: Annotated[bool, typer.Option(help="Parse indoor records only")] = False,
    year: Annotated[Optional[int], typer.Option(help="Show only records from this year")] = None,
) -> None:
    records = best_records(load_records(outdoor=outdoor, indoor=indoor))
    if year is not None:
        records = [r for r in records if r.year == year]
    print_grouped(records)


if __name__ == "__main__":
    app()
