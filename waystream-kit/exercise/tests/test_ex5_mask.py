import pytest
from acex_devkit.normalizer import MASK
from acex_driver_waystream_ibos.codec import IbosCodec
from acex_driver_waystream_ibos.normalizer import IbosNormalizer

from ibos_kit.masking import find_unmasked
from ibos_kit.paths import DEVICE_FIXTURES, GOLDEN, VARIANTS


def test_the_secrets_oxidized_masks_are_masked_with_the_devkit_mask():
    out = IbosNormalizer().mask((VARIANTS / "with-secrets.txt").read_text()).config
    assert out == (GOLDEN / "with-secrets.masked.txt").read_text()
    assert MASK in out
    assert "EXAMPLE-" not in out


def test_masking_twice_changes_nothing():
    masker = IbosNormalizer()
    once = masker.mask((VARIANTS / "with-secrets.txt").read_text()).config
    assert masker.mask(once).config == once


def test_masking_keeps_every_line_in_its_place():
    raw = (VARIANTS / "with-secrets.txt").read_text()
    assert len(IbosNormalizer().mask(raw).config.splitlines()) == len(raw.splitlines())


def test_the_hit_report_names_rules_and_never_values():
    stats = IbosNormalizer().mask((VARIANTS / "with-secrets.txt").read_text()).stats
    assert stats.lines_redacted == 3
    assert all("EXAMPLE" not in name for name in stats.by_rule)


@pytest.mark.parametrize("path", sorted(DEVICE_FIXTURES.glob("*/running-config*.txt")), ids=lambda p: p.parent.name)
def test_configuration_without_secrets_is_left_alone(path):
    text = path.read_text()
    assert IbosNormalizer().mask(text).config == text


def test_the_codec_masks_through_the_normalizer():
    raw = (VARIANTS / "with-secrets.txt").read_text()
    assert IbosCodec().mask(raw) == (GOLDEN / "with-secrets.masked.txt").read_text()
    assert find_unmasked(IbosCodec().mask(raw)) == []


def test_guessed_secret_syntax_is_masked_too_because_unknown_is_not_safe():
    raw = (VARIANTS / "invented-secret-syntax.txt").read_text()
    assert IbosNormalizer().mask(raw).config == (GOLDEN / "invented-secret-syntax.masked.txt").read_text()
