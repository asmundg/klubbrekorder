import re
import sqlite3

from .main import (
    ClubRecord,
    _LOWER_IS_BETTER_CATEGORIES,
    classify_event,
    load_records,
    parse_result_value,
)
from .db import get_records
from .normalize import record_event


def competing_classes(age_class: str) -> list[str]:
    """Record classes a result in age_class competes for: 'G17' -> ['G17', 'MJ20', 'MJ23', 'MS'].

    From 15, a youth result also counts for the junior classes the athlete is young enough for, and for senior.
    """
    m = re.fullmatch(r"([GJ])(\d+)", age_class)
    if not m or int(m.group(2)) < 15:
        return [age_class]
    adult = {"G": "M", "J": "K"}[m.group(1)]
    age = int(m.group(2))
    return [age_class] + [f"{adult}J{limit}" for limit in (20, 23) if age < limit] + [f"{adult}S"]

def _group_by_class_and_event(records: list[ClubRecord]) -> dict[tuple[str, str], list[ClubRecord]]:
    """Group federation records by (record class, normalized event), counting youth results toward junior classes."""
    grouped: dict[tuple[str, str], list[ClubRecord]] = {}
    for r in records:
        for ac in competing_classes(r.age_class):
            rec = r.model_copy(update={"age_class": ac})
            grouped.setdefault((ac, record_event(rec)), []).append(rec)
    return grouped


# Website record pages: the main pages, and the short-track pages for indoor tracks shorter than 400m.
SOURCES = ("website", "short-track")


def has_bends(event: str) -> bool:
    """Whether a normalized event is a running event over 110m, which a short track changes."""
    try:
        if classify_event(event) not in _LOWER_IS_BETTER_CATEGORIES:
            return False
    except ValueError:
        return False
    m = re.search(r"(\d+)m\b", event)
    return not (m and int(m.group(1)) <= 110)


def _counts_for(source: str, r: ClubRecord) -> bool:
    """Short-track pages take indoor results; main pages take everything but short-track running round bends."""
    if source == "short-track":
        return r.indoor
    return not (r.indoor and has_bends(record_event(r)))


def _best(records: list[ClubRecord], category: str) -> ClubRecord:
    lower_better = category in _LOWER_IS_BETTER_CATEGORIES
    return min(records, key=lambda r: parse_result_value(r.result, event_category=category) * (1 if lower_better else -1))


def _bests(grouped: dict[tuple[str, str], list[ClubRecord]]) -> dict[tuple[str, str], ClubRecord]:
    bests: dict[tuple[str, str], ClubRecord] = {}
    for key, group in grouped.items():
        try:
            bests[key] = _best(group, classify_event(key[1]))
        except (ValueError, IndexError):
            continue
    return bests


def _baseline(conn: sqlite3.Connection, source: str) -> dict[tuple[str, str], ClubRecord]:
    """Best website record per (age_class, event key) on one source's pages."""
    grouped: dict[tuple[str, str], list[ClubRecord]] = {}
    for r in get_records(conn, source):
        if _counts_for(source, r):
            grouped.setdefault((r.age_class, record_event(r)), []).append(r)
    return _bests(grouped)


def _federation_bests(fed_records: list[ClubRecord], source: str) -> dict[tuple[str, str], ClubRecord]:
    return _bests(_group_by_class_and_event([r for r in fed_records if _counts_for(source, r)]))


def find_new_records(
    conn: sqlite3.Connection,
    *,
    outdoor: bool = False,
    indoor: bool = False,
) -> list[tuple[ClubRecord, ClubRecord, str]]:
    """Find federation records that beat the website baseline.

    Returns (federation_record, baseline_record, source) tuples. Events missing from the baseline are skipped.
    """
    fed_records = load_records(outdoor=outdoor, indoor=indoor)
    new_records: list[tuple[ClubRecord, ClubRecord, str]] = []
    for source in SOURCES:
        baseline = _baseline(conn, source)
        for key, best_fed in _federation_bests(fed_records, source).items():
            base = baseline.get(key)
            if base is None:
                continue
            cat = classify_event(key[1])
            try:
                if _is_better(best_fed, base, cat, cat in _LOWER_IS_BETTER_CATEGORIES):
                    new_records.append((best_fed, base, source))
            except (ValueError, IndexError):
                continue
    new_records.sort(key=lambda x: (x[2], x[0].age_class, record_event(x[0])))
    return new_records


def current_best_records(
    conn: sqlite3.Connection,
    *,
    outdoor: bool = False,
    indoor: bool = False,
) -> list[ClubRecord]:
    """Return the current best record per (age_class, event) on each source's pages, merging baseline with federation."""
    fed_records = load_records(outdoor=outdoor, indoor=indoor)
    result: list[ClubRecord] = []
    for source in SOURCES:
        bests = _baseline(conn, source)
        for key, best_fed in _federation_bests(fed_records, source).items():
            existing = bests.get(key)
            if existing is None:
                continue
            cat = classify_event(key[1])
            try:
                if _is_better(best_fed, existing, cat, cat in _LOWER_IS_BETTER_CATEGORIES):
                    bests[key] = best_fed
            except (ValueError, IndexError):
                continue
        result.extend(bests.values())
    return result


def _is_better(a: ClubRecord, b: ClubRecord, category: str, lower_better: bool) -> bool:
    a_val = parse_result_value(a.result, event_category=category)
    b_val = parse_result_value(b.result, event_category=category)
    return (a_val < b_val) if lower_better else (a_val > b_val)


def print_new_records(new_records: list[tuple[ClubRecord, ClubRecord, str]]) -> None:
    """Print new records in a formatted table."""
    if not new_records:
        print("No new records found.")
        return

    print(f"Found {len(new_records)} potential new record(s):\n")
    print(f"{'':1s} {'Page':11s} {'AC':6s} {'Event':30s} {'New':>10s} {'Name':30s} {'Year':>6s} {'Old':>10s}")
    print("-" * 111)
    for fed, base, source in new_records:
        suffix = "i" if fed.indoor else ""
        old_result = base.result
        # Flag suspiciously small improvements (likely format artifacts)
        cat = classify_event(record_event(fed))
        fed_val = parse_result_value(fed.result, event_category=cat)
        base_val = parse_result_value(base.result, event_category=cat)
        diff = abs(fed_val - base_val)
        flag = "?" if diff < 1.0 and fed_val > 10 else " "
        print(
            f"{flag} {source:11s} {fed.age_class:6s} {record_event(fed):30s} "
            f"{fed.result + suffix:>10s} "
            f"{fed.name:30s} {fed.year:>6d} {old_result:>10s}"
        )
