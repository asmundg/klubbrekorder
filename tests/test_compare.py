from main import ClubRecord
from db import init_db, insert_records, get_best_per_event


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
