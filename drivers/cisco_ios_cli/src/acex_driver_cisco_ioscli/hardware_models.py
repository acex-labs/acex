
"""Cisco hardware model helpers.

The values represent the highest fixed front-panel index that should be
treated as onboard ports before the renderer falls back to module indexing.
"""


CISCO_HARDWARE_MAX_INDEX = {
    "C9200-24T": 24,
    "C9200-24P": 24,
    "C9200-48T": 48,
    "C9200-48P": 48,
    "C9200L-24T-4G": 28,
    "C9200L-24P-4G": 28,
    "C9200L-24T-4X": 28,
    "C9200L-24P-4X": 28,
    "C9200L-48T-4G": 52,
    "C9200L-48P-4G": 52,
    "C9200L-48T-4X": 52,
    "C9200L-48P-4X": 52,
    "C9300-24T": 28,
    "C9300-24P": 28,
    "C9300-48": 48,
    "C9300-48T": 52,
    "C9300-48P": 52,
    "C9300-48U": 52,
    "C9300L-24T-4G": 28,
    "C9300L-24P-4G": 28,
    "C9300L-24T-4X": 28,
    "C9300L-24P-4X": 28,
    "C9300L-48T-4G": 52,
    "C9300L-48P-4G": 52,
    "C9300L-48T-4X": 52,
    "C9300L-48P-4X": 52,
    "C9500-16X": 16,
    "C9500-24Y4C": 28,
    "C9500-32C": 32,
    "C9500-40X": 40,
    "C9500-48Y4C": 52,
    "WS-C2960X-24TS-L": 28,
    "WS-C2960X-48TS-L": 52,
    "WS-C3850-24T": 28,
    "WS-C3850-24P": 28,
    "WS-C3850-48T": 52,
    "WS-C3850-48P": 52,
}


def match_hardware_model(hardware_model):
    return CISCO_HARDWARE_MAX_INDEX.get(hardware_model, 0)