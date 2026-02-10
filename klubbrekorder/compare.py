import sqlite3

from .main import (
    ClubRecord,
    _LOWER_IS_BETTER_CATEGORIES,
    classify_event,
    load_records,
    parse_result_value,
)
from .db import get_best_per_event
from .normalize import normalize_event


def find_new_records(
    conn: sqlite3.Connection,
    *,
    outdoor: bool = False,
    indoor: bool = False,
) -> list[tuple[ClubRecord, ClubRecord]]:
    """Find federation records that beat the website baseline.

    Returns list of (federation_record, baseline_record) tuples.
    """
    # Get website baseline: best per (age_class, event)
    baseline = get_best_per_event(conn, "website")

    # Build normalized lookup: (age_class, normalized_event) -> ClubRecord
    baseline_norm: dict[tuple[str, str], ClubRecord] = {}
    for (ac, event), rec in baseline.items():
        norm = normalize_event(event)
        key = (ac, norm)
        if key not in baseline_norm:
            baseline_norm[key] = rec
        else:
            # Keep the better of duplicates (can happen with website event name variants)
            try:
                cat = classify_event(norm)
                lower_better = cat in _LOWER_IS_BETTER_CATEGORIES
                existing = parse_result_value(baseline_norm[key].result, event_category=cat)
                new = parse_result_value(rec.result, event_category=cat)
                if lower_better and new < existing:
                    baseline_norm[key] = rec
                elif not lower_better and new > existing:
                    baseline_norm[key] = rec
            except ValueError:
                pass

    # Load federation records (live from HTML files)
    fed_records = load_records(outdoor=outdoor, indoor=indoor)

    # Group federation by (age_class, normalized_event) and pick best
    fed_grouped: dict[tuple[str, str], list[ClubRecord]] = {}
    for r in fed_records:
        norm = normalize_event(r.event)
        key = (r.age_class, norm)
        fed_grouped.setdefault(key, []).append(r)

    new_records: list[tuple[ClubRecord, ClubRecord]] = []

    for key, group in fed_grouped.items():
        ac, norm_event = key
        try:
            cat = classify_event(norm_event)
        except ValueError:
            continue

        lower_better = cat in _LOWER_IS_BETTER_CATEGORIES

        # Pick best federation record for this combo
        best_fed = min(
            group,
            key=lambda r: parse_result_value(r.result, event_category=cat) * (1 if lower_better else -1),
        )

        baseline_rec = baseline_norm.get(key)
        if baseline_rec is None:
            # New event not in baseline — skip, too noisy
            continue

        try:
            fed_val = parse_result_value(best_fed.result, event_category=cat)
            base_val = parse_result_value(baseline_rec.result, event_category=cat)
        except (ValueError, IndexError):
            continue

        is_better = (fed_val < base_val) if lower_better else (fed_val > base_val)
        if is_better:
            new_records.append((best_fed, baseline_rec))

    new_records.sort(key=lambda x: (x[0].age_class, normalize_event(x[0].event)))
    return new_records


def current_best_records(
    conn: sqlite3.Connection,
    *,
    outdoor: bool = False,
    indoor: bool = False,
) -> list[ClubRecord]:
    """Return the current best record per (age_class, event), merging baseline with federation."""
    baseline = get_best_per_event(conn, "website")

    # Start with baseline as the current bests (keyed by normalized event)
    bests: dict[tuple[str, str], ClubRecord] = {}
    for (ac, event), rec in baseline.items():
        norm = normalize_event(event)
        key = (ac, norm)
        if key not in bests:
            bests[key] = rec
        else:
            try:
                cat = classify_event(norm)
                lower_better = cat in _LOWER_IS_BETTER_CATEGORIES
                if _is_better(rec, bests[key], cat, lower_better):
                    bests[key] = rec
            except ValueError:
                pass

    # Override with federation where it's better
    fed_records = load_records(outdoor=outdoor, indoor=indoor)
    fed_grouped: dict[tuple[str, str], list[ClubRecord]] = {}
    for r in fed_records:
        norm = normalize_event(r.event)
        key = (r.age_class, norm)
        fed_grouped.setdefault(key, []).append(r)

    for key, group in fed_grouped.items():
        try:
            cat = classify_event(key[1])
        except ValueError:
            continue
        lower_better = cat in _LOWER_IS_BETTER_CATEGORIES
        best_fed = min(
            group,
            key=lambda r: parse_result_value(r.result, event_category=cat) * (1 if lower_better else -1),
        )
        existing = bests.get(key)
        if existing is None:
            continue
        try:
            if _is_better(best_fed, existing, cat, lower_better):
                bests[key] = best_fed
        except (ValueError, IndexError):
            continue

    return list(bests.values())


def _is_better(a: ClubRecord, b: ClubRecord, category: str, lower_better: bool) -> bool:
    a_val = parse_result_value(a.result, event_category=category)
    b_val = parse_result_value(b.result, event_category=category)
    return (a_val < b_val) if lower_better else (a_val > b_val)


def print_new_records(new_records: list[tuple[ClubRecord, ClubRecord]]) -> None:
    """Print new records in a formatted table."""
    if not new_records:
        print("No new records found.")
        return

    print(f"Found {len(new_records)} potential new record(s):\n")
    print(f"{'':1s} {'AC':6s} {'Event':30s} {'New':>10s} {'Name':30s} {'Year':>6s} {'Old':>10s}")
    print("-" * 99)
    for fed, base in new_records:
        suffix = "i" if fed.indoor else ""
        old_result = base.result
        # Flag suspiciously small improvements (likely format artifacts)
        cat = classify_event(normalize_event(fed.event))
        fed_val = parse_result_value(fed.result, event_category=cat)
        base_val = parse_result_value(base.result, event_category=cat)
        diff = abs(fed_val - base_val)
        flag = "?" if diff < 1.0 and fed_val > 10 else " "
        print(
            f"{flag} {fed.age_class:6s} {normalize_event(fed.event):30s} "
            f"{fed.result + suffix:>10s} "
            f"{fed.name:30s} {fed.year:>6d} {old_result:>10s}"
        )
