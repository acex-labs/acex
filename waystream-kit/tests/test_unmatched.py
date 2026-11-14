import io
from types import SimpleNamespace

import pytest

from ibos_kit.unmatched import build, kind, main, render

RAW = "hostname h\ninterface a\n vlan member 2\n vlan untagged 2\n description x\nrouter ospf\n router-id 1\n"


def line(text: str, *parents: str):
    return SimpleNamespace(line=text, parents=list(parents))


class Codec:
    def __init__(self, unmatched):
        self.unmatched = unmatched

    def normalize(self, raw):
        return raw

    def parse(self, raw, node):
        return SimpleNamespace(metadata=SimpleNamespace(unmatched=self.unmatched))


UNMATCHED = [
    line(" vlan member 2", "interface a"),
    line(" vlan untagged 2", "interface a"),
    line("router ospf"),
    line(" router-id 1", "router ospf"),
]


def test_the_share_counts_lines_that_were_translated():
    report = build(Codec(UNMATCHED), RAW)
    assert report.significant == 7
    assert round(report.translated_share, 2) == 0.43


def test_nothing_unmatched_is_everything_translated_and_an_empty_file_is_not_a_division_by_zero():
    assert build(Codec([]), RAW).translated_share == 1.0
    assert build(Codec([]), "").translated_share == 1.0


def test_a_kind_is_the_header_word_and_the_first_two_words_of_the_line():
    assert kind(line(" vlan member 2", "interface a")) == "interface > vlan member"
    assert kind(line("router ospf")) == "router ospf"


def test_the_lines_are_grouped_under_the_header_they_sat_under():
    out = render(build(Codec(UNMATCHED), RAW)).splitlines()
    assert out[0] == "4 of 7 lines not translated (43% translated)"
    assert out[2:6] == ["interface a", "   vlan member 2", "   vlan untagged 2", ""]
    assert "(top level)" in out and "router ospf" in out


def test_the_most_common_kinds_come_last_with_their_counts():
    unmatched = [*UNMATCHED, line(" vlan member 3", "interface b")]
    report = build(Codec(unmatched), RAW)
    assert report.kinds()[0] == ("interface > vlan member", 2)
    out = render(report)
    assert out.index("Most common:") > out.index("router ospf")
    assert "     2  interface > vlan member" in out


def test_a_stub_that_is_not_there_yet_gives_a_message_instead_of_a_traceback(tmp_path):
    class Stub:
        def normalize(self, raw):
            raise NotImplementedError("Exercise 4: normalize, with the normalizer")

    path = tmp_path / "config.txt"
    path.write_text(RAW)
    with pytest.raises(SystemExit) as stopped:
        main(Stub(), [str(path)])
    assert str(stopped.value) == "Not there yet: Exercise 4: normalize, with the normalizer"


def test_a_dash_reads_standard_input(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(RAW))
    main(Codec(UNMATCHED), ["-"])
    assert "4 of 7 lines not translated" in capsys.readouterr().out


def test_no_argument_prints_the_usage():
    with pytest.raises(SystemExit, match="usage"):
        main(Codec([]), [])
