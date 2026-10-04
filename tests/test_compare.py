from klubbrekorder.main import ClubRecord
from klubbrekorder.db import init_db, insert_records, get_best_per_event


class TestDbOperations:
    def test_insert_and_retrieve(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        records = [
            ClubRecord(age_class="MS", event="100m", name="Test", result="10,50", year=2020),
            ClubRecord(age_class="MS", event="100m", name="Test2", result="10,80", year=2019),
        ]
        count = insert_records(conn, records, "website")
        assert count == 2

        # Idempotent
        count2 = insert_records(conn, records, "website")
        assert count2 == 0

        conn.close()

    def test_best_per_event(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        records = [
            ClubRecord(age_class="MS", event="100m", name="Fast", result="10,50", year=2020),
            ClubRecord(age_class="MS", event="100m", name="Slow", result="11,00", year=2019),
            ClubRecord(age_class="MS", event="Høyde", name="High", result="2,10", year=2020),
            ClubRecord(age_class="MS", event="Høyde", name="Low", result="1,90", year=2019),
        ]
        insert_records(conn, records, "website")

        best = get_best_per_event(conn, "website")

        # Sprint: lower is better
        assert ("MS", "100m") in best
        assert best[("MS", "100m")].name == "Fast"

        # Høyde: higher is better
        assert ("MS", "Høyde") in best
        assert best[("MS", "Høyde")].name == "High"

        conn.close()

    def test_indoor_outdoor_combined(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Indoor and outdoor records are combined — best overall result wins."""
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        records = [
            ClubRecord(age_class="MS", event="60m", name="Outdoor", result="7,00", year=2020, indoor=False),
            ClubRecord(age_class="MS", event="60m", name="Indoor", result="6,80", year=2020, indoor=True),
        ]
        insert_records(conn, records, "website")

        best = get_best_per_event(conn, "website")
        # Only one entry per (age_class, event) — the faster time wins
        assert ("MS", "60m") in best
        assert best[("MS", "60m")].name == "Indoor"
        assert best[("MS", "60m")].result == "6,80"

        conn.close()


from klubbrekorder import compare
from klubbrekorder.compare import competing_classes, find_new_records, has_bends


class TestCompetingClasses:
    def test_from_15_counts_for_junior_and_senior(self) -> None:
        assert competing_classes("G15") == ["G15", "MJ20", "MJ23", "MS"]
        assert competing_classes("J19") == ["J19", "KJ20", "KJ23", "KS"]

    def test_over_19_skips_u20(self) -> None:
        assert competing_classes("G20") == ["G20", "MJ23", "MS"]
        assert competing_classes("J22") == ["J22", "KJ23", "KS"]

    def test_under_15_counts_for_own_class_only(self) -> None:
        assert competing_classes("G14") == ["G14"]
        assert competing_classes("J13") == ["J13"]

    def test_other_classes_unchanged(self) -> None:
        assert competing_classes("MS") == ["MS"]
        assert competing_classes("KV40") == ["KV40"]


class TestHasBends:
    def test_running_over_110m(self) -> None:
        assert has_bends("200m")
        assert has_bends("400m HK 76,2")
        assert has_bends("Kappgang 3000m")
        assert has_bends("1 mile")

    def test_straights_and_field(self) -> None:
        assert not has_bends("60m")
        assert not has_bends("60m HK 84")
        assert not has_bends("110m HK 106,7")
        assert not has_bends("Høyde")


class TestFindNewRecords:
    def _found(self, tmp_path, monkeypatch, fed: list[ClubRecord]) -> list[tuple[str, str, str, str]]:  # type: ignore[no-untyped-def]
        conn = init_db(tmp_path / "test.db")
        insert_records(
            conn,
            [
                ClubRecord(age_class="G17", event="400m", name="Old Youth", result="50,00", year=2003),
                ClubRecord(age_class="MJ20", event="400m", name="Old Junior", result="52,02", year=2016),
                ClubRecord(age_class="MJ20", event="Høyde", name="Old High", result="1,90", year=2000),
            ],
            "website",
        )
        insert_records(
            conn,
            [ClubRecord(age_class="MJ20", event="400m", name="Old Indoor", result="53,00", year=2010, indoor=True)],
            "short-track",
        )
        monkeypatch.setattr(compare, "load_records", lambda **_: fed)
        return [(src, f.age_class, f.name, b.name) for f, b, src in find_new_records(conn)]

    def test_youth_result_beats_junior_record(self, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        fed = [ClubRecord(age_class="G17", event="400m", name="New", result="51,52", year=2026)]
        assert self._found(tmp_path, monkeypatch, fed) == [("website", "MJ20", "New", "Old Junior")]

    def test_short_track_run_only_beats_short_track_record(self, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        fed = [ClubRecord(age_class="G17", event="400m", name="New", result="51,52", year=2026, indoor=True)]
        assert self._found(tmp_path, monkeypatch, fed) == [("short-track", "MJ20", "New", "Old Indoor")]

    def test_indoor_field_result_counts_on_main_page(self, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        fed = [ClubRecord(age_class="G17", event="Høyde", name="New", result="1,95", year=2026, indoor=True)]
        assert self._found(tmp_path, monkeypatch, fed) == [("website", "MJ20", "New", "Old High")]

from klubbrekorder.main import parse_result_value


class TestParseResultValue:
    def test_three_part_track_time_is_minutes(self) -> None:
        assert parse_result_value("1,05,40", event_category="Sprint") == 65.4
        assert parse_result_value("5,43,94", event_category="Langdistanse") == 343.94
        assert parse_result_value("4,33,4", event_category="Kappgang") == 273.4

    def test_three_part_road_time_is_hours(self) -> None:
        assert parse_result_value("1,02,04", event_category="Kappgang") == 3724
        assert parse_result_value("1,04,59", event_category="Langdistanse") == 3899

    def test_colon_hours(self) -> None:
        assert parse_result_value("1:26:22", event_category="Kappgang") == 5182
        assert parse_result_value("3:48,9", event_category="Mellomdistanse") == 228.9
