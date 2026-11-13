import pytest
from acex_driver_waystream_ibos.codec import IbosCodec
from acex_driver_waystream_ibos.normalizer import IbosNormalizer

from ibos_kit.paths import DEVICE_FIXTURES, GOLDEN, VARIANTS

PAIRS = [
    ("ms4000-6.3.5/running-config.txt", "ms4000-6.3.5.normalized.txt"),
    ("ms4000-6.3.5/running-config.with-client.txt", "ms4000-6.3.5.with-client.normalized.txt"),
    ("asr6000-6.3.5/running-config.txt", "asr6000-6.3.5.normalized.txt"),
    ("asr6000-6.3.5/running-config.with-client.txt", "asr6000-6.3.5.with-client.normalized.txt"),
]


@pytest.mark.parametrize(("raw", "golden"), PAIRS)
def test_normalizing_gives_the_golden_form(raw, golden):
    assert IbosNormalizer().normalize((DEVICE_FIXTURES / raw).read_text()).config == (GOLDEN / golden).read_text()


def test_a_configuration_with_a_client_normalizes_to_the_one_without():
    normalizer = IbosNormalizer()
    for name in ("ms4000-6.3.5", "asr6000-6.3.5"):
        with_client = (DEVICE_FIXTURES / name / "running-config.with-client.txt").read_text()
        without = (DEVICE_FIXTURES / name / "running-config.txt").read_text()
        assert normalizer.normalize(with_client).config == normalizer.normalize(without).config


def test_volatile_lines_go_wherever_they_sit_and_other_comments_stay():
    raw = "interface x\n !volatile foo\n description a\n! a plain comment\n   !volatile bar\nhostname h\n"
    assert IbosNormalizer().normalize(raw).config == "interface x\n description a\n! a plain comment\nhostname h\n"


def test_the_version_comment_and_the_end_marker_are_not_configuration():
    assert IbosNormalizer().normalize("! version ibos-x (ibos-x.bz2)\nhostname h\n!end\n").config == "hostname h\n"


def test_lone_bang_separators_are_dropped_so_both_separator_styles_read_alike():
    bang = (VARIANTS / "bang-separators.txt").read_text()
    blank = (DEVICE_FIXTURES / "ms4000-6.3.5/running-config.txt").read_text()
    stripped = IbosNormalizer().normalize(bang).config.replace("\n\n", "\n")
    assert stripped == IbosNormalizer().normalize(blank).config.replace("\n\n", "\n")


def test_windows_line_endings_read_like_unix_ones():
    raw = (DEVICE_FIXTURES / "ms4000-6.3.5/running-config.with-client.txt").read_text()
    normalizer = IbosNormalizer()
    assert normalizer.normalize(raw.replace("\n", "\r\n")).config == normalizer.normalize(raw).config


def test_normalizing_twice_changes_nothing():
    normalizer = IbosNormalizer()
    once = normalizer.normalize((DEVICE_FIXTURES / "asr6000-6.3.5/running-config.with-client.txt").read_text()).config
    assert normalizer.normalize(once).config == once


def test_the_codec_normalizes_through_the_normalizer():
    raw = (DEVICE_FIXTURES / "ms4000-6.3.5/running-config.with-client.txt").read_text()
    assert IbosCodec().normalize(raw) == (GOLDEN / "ms4000-6.3.5.normalized.txt").read_text()
