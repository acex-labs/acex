"""The migrations form one line. Two heads make the upgrade at startup fail, and the backend does not start."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS = Path(__file__).parent.parent / "src/acex/migrations"


def should_have_a_single_head():
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))

    heads = ScriptDirectory.from_config(config).get_heads()

    assert len(heads) == 1, (
        f"Several migration heads: {sorted(heads)}. Point the newer one's down_revision at the other."
    )
