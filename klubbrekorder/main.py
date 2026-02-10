import re
from pathlib import Path
from typing import Annotated

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


def abbreviate_age_class(raw: str, *, birth_year: int | None = None, competition_year: int | None = None) -> str:
    """Map e.g. 'Gutter 13' -> 'G13', 'Menn Senior' -> 'MS', 'Menn veteran 30-34' -> 'MV30'.

    For combined classes like 'Gutter 18/19', uses birth_year and competition_year
    to determine actual age (you compete as 18 the year you turn 18).
    """
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
            # For "18/19" -> resolve using birth year
            slash_match = re.match(r"(\d+)/(\d+)", rest)
            if slash_match:
                if birth_year is not None and competition_year is not None:
                    age = competition_year - birth_year
                    return short + str(age)
                return short + slash_match.group(1)
            # For veterans "30-34" -> take first number "30"
            age_match = re.match(r"(\d+)", rest)
            if age_match:
                return short + age_match.group(1)
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
                birth_date_str = cells[2].get_text(strip=True)
                date_str = cells[5].get_text(strip=True)
                competition_year = parse_year(date_str)

                records.append(
                    ClubRecord(
                        age_class=abbreviate_age_class(
                            current_age_class,
                            birth_year=parse_year(birth_date_str),
                            competition_year=competition_year,
                        ),
                        event=current_event,
                        name=name,
                        result=clean_result(result_raw),
                        year=competition_year,
                        indoor=indoor,
                    )
                )
                event_captured = True
                break

    return records


_SPRINT_DISTANCES = {"60", "100", "150", "200", "300", "400"}
_MIDDLE_DISTANCES = {"600", "800", "1000", "1500"}
_LONG_DISTANCES = {"2000", "3000", "5000", "10000"}


def classify_event(event: str) -> str:
    """Classify an event name into a category."""
    lower = event.lower()

    # Check specific keywords first (order matters)
    if "hekk" in lower or "hinder" in lower or " hk" in lower or lower.endswith("hk"):
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
    if "halvmaraton" in lower or "maraton" in lower:
        return "Langdistanse"
    if "mile" in lower:
        return "Mellomdistanse"
    if lower.endswith("km"):
        return "Langdistanse"

    # Distance-based classification: "100 meter" or "100m"
    m = re.match(r"(\d+)\s*(?:meter|m)\b", lower)
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


def parse_result_value(result: str, *, event_category: str = "") -> float:
    """Parse a result string like '7,94', '1:23,45', '1,05,40' into a comparable float.

    For Langdistanse/Kappgang, 2-part comma results (e.g. '56,11') are min:sec.
    For other events, 2-part comma results (e.g. '10,50') are decimal seconds/meters.
    """
    normalized = result.replace(",", ".")
    if ":" in normalized:
        parts = normalized.split(":")
        return round(float(parts[0]) * 60 + float(parts[1]), 2)
    # 3-part dot format: m.ss.f (e.g. "1.05.40" = 1min 05.40s, "10.44.1" = 10min 44.1s)
    dot_parts = normalized.split(".")
    if len(dot_parts) == 3:
        frac = float(f"0.{dot_parts[2]}")
        return round(int(dot_parts[0]) * 60 + int(dot_parts[1]) + frac, 2)
    # 2-part: for road/walking events, interpret as min:sec (e.g. "56,11" = 56:11)
    if len(dot_parts) == 2 and event_category in ("Langdistanse", "Kappgang"):
        return round(int(dot_parts[0]) * 60 + int(dot_parts[1]), 2)
    return float(normalized)


def pick_best_record(records: list[ClubRecord], category: str) -> ClubRecord:
    """Pick the best record from a list — lowest time or highest distance/points."""
    lower_better = category in _LOWER_IS_BETTER_CATEGORIES
    return min(records, key=lambda r: parse_result_value(r.result, event_category=category) * (1 if lower_better else -1))


_FEDERATION_URL = "https://www.minfriidrettsstatistikk.info/php/KlubbStatistikk.php"
_CLUB_ID = "176"  # IL i BUL Tromsø


def _fetch_federation_html(*, outdoor: bool) -> str:
    """Fetch club statistics HTML from the federation site."""
    import httpx

    resp = httpx.get(
        _FEDERATION_URL,
        params={
            "showclub": _CLUB_ID,
            "showclass": "0",
            "showevent": "0",
            "outdoor": "Y" if outdoor else "N",
            "showseason": "0",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text


def load_records(*, outdoor: bool, indoor: bool) -> list[ClubRecord]:
    do_outdoor = not indoor or outdoor
    do_indoor = not outdoor or indoor

    all_records: list[ClubRecord] = []
    if do_outdoor:
        all_records.extend(parse_records(_fetch_federation_html(outdoor=True), indoor=False))
    if do_indoor:
        all_records.extend(parse_records(_fetch_federation_html(outdoor=False), indoor=True))
    return all_records


app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def default_command(
    ctx: typer.Context,
    outdoor: Annotated[bool, typer.Option(help="Compare outdoor records only")] = False,
    indoor: Annotated[bool, typer.Option(help="Compare indoor records only")] = False,
) -> None:
    """Compare federation stats against website baseline to find new records."""
    if ctx.invoked_subcommand is not None:
        return
    from .db import init_db, DEFAULT_DB_PATH
    from .compare import compare_federation_vs_baseline

    if not DEFAULT_DB_PATH.exists():
        print("No database found. Run 'scrape' then 'import-website' first.")
        raise typer.Exit(1)

    conn = init_db()
    compare_federation_vs_baseline(conn, outdoor=outdoor, indoor=indoor)
    conn.close()


@app.command()
def scrape() -> None:
    """Download club record pages from bul-tromso.no."""
    from .scrape import scrape_all

    scrape_all(Path("data/website"))


@app.command("import-website")
def import_website() -> None:
    """Parse downloaded website HTML and import into SQLite baseline."""
    from .parse_website import parse_all_website_pages
    from .db import init_db, insert_records

    data_dir = Path("data/website")
    if not data_dir.exists():
        print("No data/website/ directory. Run 'scrape' first.")
        raise typer.Exit(1)

    records = parse_all_website_pages(data_dir)
    conn = init_db()
    count = insert_records(conn, records, "website")
    conn.close()
    print(f"\nImported {count} records into database.")




