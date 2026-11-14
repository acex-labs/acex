import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "exercise" / "src"))

from acex_driver_waystream_ibos.codec import IbosCodec  # noqa: E402

from ibos_kit.unmatched import main  # noqa: E402

if __name__ == "__main__":
    main(IbosCodec(), sys.argv[1:])
