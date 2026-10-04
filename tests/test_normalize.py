from klubbrekorder.normalize import normalize_event


class TestNormalizeDistances:
    def test_meter_suffix(self) -> None:
        assert normalize_event("100 meter") == "100m"

    def test_m_suffix(self) -> None:
        assert normalize_event("100m") == "100m"

    def test_long_distance_with_space(self) -> None:
        assert normalize_event("10 000m") == "10000m"

    def test_long_distance_no_space(self) -> None:
        assert normalize_event("10000 meter") == "10000m"


class TestNormalizeHurdles:
    def test_federation_format(self) -> None:
        assert normalize_event("110 meter hekk (106,7cm)") == "110m HK 106,7"

    def test_website_format_cm(self) -> None:
        assert normalize_event("60m HK (100 cm)") == "60m HK 100"

    def test_website_format_meters(self) -> None:
        assert normalize_event("80m HK 0,76") == "80m HK 76,2"

    def test_bare_hurdle(self) -> None:
        assert normalize_event("60m HK") == "60m HK"
        assert normalize_event("60 meter hekk") == "60m HK"

    def test_steeplechase_federation(self) -> None:
        assert normalize_event("3000 meter hinder (91,4cm)") == "3000m hinder 91,4"

    def test_steeplechase_website_abbrev(self) -> None:
        assert normalize_event("3000m hin") == "3000m hinder"

    def test_steeplechase_website_with_height(self) -> None:
        assert normalize_event("2000m hin (0,91)") == "2000m hinder 91,4"


class TestNormalizeThrows:
    def test_kule_kg(self) -> None:
        assert normalize_event("Kule 7,26kg") == "Kule 7,26kg"

    def test_kule_parenthesized(self) -> None:
        assert normalize_event("Kule (7,26kg)") == "Kule 7,26kg"

    def test_diskos_gram(self) -> None:
        assert normalize_event("Diskos 600gram") == "Diskos 0,6kg"
        assert normalize_event("Diskos 750gram") == "Diskos 0,75kg"

    def test_slegge_with_wire(self) -> None:
        assert normalize_event("Slegge 7,26kg/121,5cm") == "Slegge 7,26kg"
        assert normalize_event("Slegge 3,0Kg (119,5cm)") == "Slegge 3,0kg"

    def test_spyd_gram(self) -> None:
        assert normalize_event("Spyd 800gram") == "Spyd 0,8kg"

    def test_spyd_g_suffix(self) -> None:
        assert normalize_event("Spyd 600g") == "Spyd 0,6kg"

    def test_vektkast_formats(self) -> None:
        assert normalize_event("VektKast 15,88Kg") == "Vektkast 15,88kg"
        assert normalize_event("VektKast4,0kg") == "Vektkast 4,0kg"
        assert normalize_event("Vektkast (15,88kg)") == "Vektkast 15,88kg"

    def test_bare_throw(self) -> None:
        assert normalize_event("Kule") == "Kule"
        assert normalize_event("Diskos") == "Diskos"


class TestNormalizeKappgang:
    def test_meter_format(self) -> None:
        assert normalize_event("Kappgang 3000 meter") == "Kappgang 3000m"

    def test_m_format(self) -> None:
        assert normalize_event("Kappgang 3000m") == "Kappgang 3000m"

    def test_km_landevei(self) -> None:
        assert normalize_event("Kappgang 10 km landevei") == "Kappgang 10km"
        assert normalize_event("Kappgang 10km Landevei") == "Kappgang 10km"
        assert normalize_event("Kappgang 10km vei") == "Kappgang 10km"

    def test_reversed_format(self) -> None:
        assert normalize_event("3000m kappgang") == "Kappgang 3000m"

    def test_typo(self) -> None:
        assert normalize_event("3000m kappang") == "Kappgang 3000m"


class TestNormalizeMultiEvent:
    def test_mangekamp_variants(self) -> None:
        assert normalize_event("10-kamp") == "10-kamp"
        assert normalize_event("Tikamp") == "10-kamp"
        assert normalize_event("7-kamp") == "7-kamp"
        assert normalize_event("Syvkamp") == "7-kamp"
        assert normalize_event("Firekamp") == "4-kamp"
        assert normalize_event("5-kamp") == "5-kamp"

    def test_federation_kamp_formats(self) -> None:
        assert normalize_event("4 Kamp (60m-Lengde-Kule-600m)") == "4-kamp"
        assert normalize_event("7 Kamp (60m-Lengde-Kule-Høyde-60mhekk-Stav-1000m)") == "7-kamp"

    def test_kast_5kamp(self) -> None:
        assert normalize_event("Kast 5 Kamp (Slegge-Kule-Diskos-Spyd-Vektkast)") == "Kast 5-kamp"


class TestNormalizeMisc:
    def test_halvmaraton(self) -> None:
        assert normalize_event("Halvmaraton") == "Halvmaraton"
        assert normalize_event("Halvmarathon") == "Halvmaraton"

    def test_maraton(self) -> None:
        assert normalize_event("Maraton") == "Maraton"
        assert normalize_event("Marathon") == "Maraton"

    def test_mile(self) -> None:
        assert normalize_event("1 mile") == "1 mile"

    def test_field_events(self) -> None:
        assert normalize_event("Høyde") == "Høyde"
        assert normalize_event("Høyde u/t") == "Høyde u/t"
        assert normalize_event("Høyde uten tilløp") == "Høyde u/t"
        assert normalize_event("Lengde") == "Lengde"
        assert normalize_event("Lengde uten tilløp") == "Lengde u/t"
        assert normalize_event("Stav") == "Stav"
        assert normalize_event("Tresteg") == "Tresteg"
        assert normalize_event("Tresteg (Sone 0,5m)") == "Tresteg"


from klubbrekorder.main import ClubRecord
from klubbrekorder.normalize import record_event


def _rec(age_class: str, event: str, year: int = 2020) -> ClubRecord:
    return ClubRecord(age_class=age_class, event=event, name="X", result="1", year=year)


class TestRecordEvent:
    def test_bare_senior_events_get_class_spec(self) -> None:
        assert record_event(_rec("KS", "Slegge")) == "Slegge 4,0kg"
        assert record_event(_rec("MS", "110m HK")) == "110m HK 106,7"
        assert record_event(_rec("KJ20", "100m HK")) == "100m HK 84"
        assert record_event(_rec("MJ23", "3000m hin")) == "3000m hinder 91,4"
        assert record_event(_rec("MJ20", "110m HK")) == "110m HK 106,7"

    def test_matches_federation_name(self) -> None:
        assert record_event(_rec("KS", "Slegge")) == record_event(_rec("KS", "Slegge 4,0kg"))
        assert record_event(_rec("MS", "400m HK")) == record_event(_rec("MS", "400 meter hekk (91,4cm)"))

    def test_explicit_spec_kept(self) -> None:
        assert record_event(_rec("MJ20", "Kule 6kg")) == "Kule 6,0kg"

    def test_no_default_leaves_bare(self) -> None:
        assert record_event(_rec("MJ20", "Kule")) == "Kule"
        assert record_event(_rec("G15", "Vektkast")) == "Vektkast"

    def test_old_javelin_by_year(self) -> None:
        assert record_event(_rec("MS", "Spyd 800g", 1985)) == "Spyd 0,8kg gammel"
        assert record_event(_rec("MS", "Spyd 800g", 1986)) == "Spyd 0,8kg"
        assert record_event(_rec("KJ20", "Spyd <1999", 1991)) == "Spyd 0,6kg gammel"
        assert record_event(_rec("KJ20", "Spyd >1999", 2021)) == "Spyd 0,6kg"
        assert record_event(_rec("G13", "Spyd 600g (gammel type)", 1990)) == "Spyd 0,6kg gammel"
        assert record_event(_rec("J13", "Spyd 400g", 1990)) == "Spyd 0,4kg"
