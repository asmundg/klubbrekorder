from klubbrekorder.parse_website import (
    _clean_website_result,
    _is_relay,
    parse_format_a,
    parse_format_b,
    parse_format_c,
)


class TestCleanWebsiteResult:
    def test_plain_result(self) -> None:
        assert _clean_website_result("10,46") == ("10,46", False)

    def test_indoor_suffix(self) -> None:
        assert _clean_website_result("2,11i") == ("2,11", True)

    def test_hand_timing_suffix(self) -> None:
        assert _clean_website_result("21:17+") == ("21:17", False)

    def test_points_suffix(self) -> None:
        assert _clean_website_result("6507p") == ("6507", False)

    def test_parenthetical_note(self) -> None:
        assert _clean_website_result("4685p (4808p med gammel tabell)") == ("4685", False)

    def test_star_suffix(self) -> None:
        assert _clean_website_result("5386*") == ("5386", False)

    def test_semicolon_fix(self) -> None:
        assert _clean_website_result("3;11,70") == ("3:11,70", False)

    def test_indoor_with_time(self) -> None:
        assert _clean_website_result("11:45,58i") == ("11:45,58", True)


class TestIsRelay:
    def test_relay_with_times(self) -> None:
        assert _is_relay("4×100m") is True

    def test_relay_stafett(self) -> None:
        assert _is_relay("1000m stafett") is True

    def test_normal_event(self) -> None:
        assert _is_relay("100m") is False

    def test_hurdle(self) -> None:
        assert _is_relay("110m HK") is False


class TestParseFormatA:
    """Test Format A parser with minimal HTML snippets."""

    def test_basic_record(self) -> None:
        html = """<table><tr>
            <td>100m</td><td>10,46</td><td>Martin Rypdal</td><td>2006</td>
        </tr></table>"""
        records = parse_format_a(html, age_class="MS")
        assert len(records) == 1
        r = records[0]
        assert r.age_class == "MS"
        assert r.event == "100m"
        assert r.result == "10,46"
        assert r.name == "Martin Rypdal"
        assert r.year == 2006
        assert r.indoor is False

    def test_indoor_record(self) -> None:
        html = """<table><tr>
            <td>Høyde</td><td>2,11i</td><td>Kjetil Theodorsen</td><td>1996</td>
        </tr></table>"""
        records = parse_format_a(html, age_class="MS")
        assert len(records) == 1
        assert records[0].indoor is True
        assert records[0].result == "2,11"

    def test_variant_record(self) -> None:
        html = """<table>
        <tr><td>Høyde</td><td>2,11i</td><td>Kjetil Theodorsen</td><td>1996</td></tr>
        <tr><td> </td><td>2,10</td><td>Geir Vollstad</td><td>1979</td></tr>
        </table>"""
        records = parse_format_a(html, age_class="MS")
        assert len(records) == 2
        assert records[0].event == "Høyde"
        assert records[1].event == "Høyde"
        assert records[1].indoor is False

    def test_skip_relay_section(self) -> None:
        html = """<table>
        <tr><td>100m</td><td>10,46</td><td>Martin Rypdal</td><td>2006</td></tr>
        <tr><td> </td><td> </td><td> </td><td>.</td></tr>
        <tr><td> </td><td> </td><td><strong>Stafetter</strong></td><td> </td></tr>
        <tr><td>4×100m</td><td>41,13</td><td>Team</td><td>2007</td></tr>
        </table>"""
        records = parse_format_a(html, age_class="MS")
        assert len(records) == 1
        assert records[0].event == "100m"

    def test_skip_empty_result(self) -> None:
        html = """<table>
        <tr><td>100m</td><td></td><td></td><td></td></tr>
        </table>"""
        records = parse_format_a(html, age_class="MS")
        assert len(records) == 0


class TestParseFormatB:
    """Test Format B parser with minimal HTML snippets."""

    def test_basic_event_with_ages(self) -> None:
        html = """<table>
        <tr><td><strong>60m</strong></td><td></td><td></td><td></td></tr>
        <tr><td>13</td><td>7,94</td><td>Magnus Somying Olsen</td><td>2022</td></tr>
        <tr><td>14</td><td>7,7</td><td>Ken Kvalsvik</td><td>1974</td></tr>
        </table>"""
        records = parse_format_b(html, gender_prefix="G")
        assert len(records) == 2
        assert records[0].age_class == "G13"
        assert records[0].event == "60m"
        assert records[1].age_class == "G14"

    def test_variant_record(self) -> None:
        html = """<table>
        <tr><td><strong>100m</strong></td><td></td><td></td><td></td></tr>
        <tr><td>14</td><td>12,3</td><td>Ken Kvalsvik</td><td>1975</td></tr>
        <tr><td> </td><td>12,37</td><td>Magnus Somying Olsen</td><td>2023</td></tr>
        </table>"""
        records = parse_format_b(html, gender_prefix="G")
        assert len(records) == 2
        assert records[0].age_class == "G14"
        assert records[1].age_class == "G14"

    def test_indoor_result(self) -> None:
        html = """<table>
        <tr><td><strong>60m</strong></td><td></td><td></td><td></td></tr>
        <tr><td>15</td><td>7,49i</td><td>Tomas Bjerknesli</td><td>2010</td></tr>
        </table>"""
        records = parse_format_b(html, gender_prefix="G")
        assert len(records) == 1
        assert records[0].indoor is True
        assert records[0].result == "7,49"

    def test_multi_word_event(self) -> None:
        html = """<table>
        <tr><td><strong>Kappgang</strong><strong>1000m</strong></td><td></td><td></td><td></td></tr>
        <tr><td>13</td><td>5:05,0</td><td>Jesper Lundin</td><td>2015</td></tr>
        </table>"""
        records = parse_format_b(html, gender_prefix="G")
        assert len(records) == 1
        assert records[0].event == "Kappgang 1000m"

    def test_prefixed_age_class(self) -> None:
        html = """<table>
        <tr><td><strong>Vektkast</strong></td><td></td><td></td><td></td></tr>
        <tr><td>G14 (7,26)</td><td>8,82</td><td>Elias Lynum Ringkjøb</td><td>2014</td></tr>
        </table>"""
        records = parse_format_b(html, gender_prefix="G")
        assert len(records) == 1
        assert records[0].age_class == "G14"


class TestParseFormatC:
    """Test Format C parser with minimal HTML snippets."""

    def test_basic_section(self) -> None:
        html = """<table>
        <tr><td colspan="2"><strong>MENN SENIOR</strong></td><td></td><td></td></tr>
        <tr><td>60m</td><td>6,73</td><td>Martin Rypdal</td><td>2007</td></tr>
        </table>"""
        records = parse_format_c(html)
        assert len(records) == 1
        assert records[0].age_class == "MS"
        assert records[0].indoor is True

    def test_multiple_sections(self) -> None:
        html = """<table>
        <tr><td colspan="2"><strong>MENN SENIOR</strong></td><td></td><td></td></tr>
        <tr><td>60m</td><td>6,73</td><td>Martin Rypdal</td><td>2007</td></tr>
        <tr><td></td><td></td><td></td><td>.</td></tr>
        <tr><td colspan="2"><strong>MENN JUNIOR (U20)</strong></td><td></td></tr>
        <tr><td>60m</td><td>6,97</td><td>Nikolai Bjerkan</td><td>2011</td></tr>
        </table>"""
        records = parse_format_c(html)
        assert len(records) == 2
        assert records[0].age_class == "MS"
        assert records[1].age_class == "MJ20"

    def test_variant_record(self) -> None:
        html = """<table>
        <tr><td colspan="2"><strong>MENN SENIOR</strong></td><td></td><td></td></tr>
        <tr><td>60m HK</td><td>8,5</td><td>Kjetil Theodorsen</td><td>1996</td></tr>
        <tr><td></td><td>8,78</td><td>Kjetil Theodorsen</td><td>1996</td></tr>
        </table>"""
        records = parse_format_c(html)
        assert len(records) == 2
        assert records[0].event == "60m HK"
        assert records[1].event == "60m HK"

    def test_skip_relay(self) -> None:
        html = """<table>
        <tr><td colspan="2"><strong>MENN SENIOR</strong></td><td></td><td></td></tr>
        <tr><td>60m</td><td>6,73</td><td>Martin Rypdal</td><td>2007</td></tr>
        <tr><td>4×200m</td><td>1:28,76</td><td>BUL Tromsø MS</td><td>2007</td></tr>
        </table>"""
        records = parse_format_c(html)
        assert len(records) == 1

    def test_kvinner_section(self) -> None:
        html = """<table>
        <tr><td colspan="4">KVINNER SENIOR</td><td></td></tr>
        <tr><td>60m</td><td>7,7</td><td>Katrine Eliassen</td><td>1993</td><td></td></tr>
        </table>"""
        records = parse_format_c(html)
        assert len(records) == 1
        assert records[0].age_class == "KS"
