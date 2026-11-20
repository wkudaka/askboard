"""SQL migrations shipped with Askboard.

Files are named ``<version>_<name>.sql`` (e.g. ``001_metadata.sql``) and applied in
version order by :meth:`askboard.db.database.Database.migrate`.
"""

import re
from dataclasses import dataclass
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent

_FILENAME = re.compile(r"^(?P<version>\d+)_(?P<name>[a-z0-9_]+)\.sql$")


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path

    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations: dict[str, Migration] = {}
    for path in directory.iterdir():
        match = _FILENAME.match(path.name)
        if not match or not path.is_file():
            continue
        version = match["version"]
        if version in migrations:
            raise ValueError(
                f"Duplicate migration version {version}: "
                f"{migrations[version].path.name} and {path.name}"
            )
        migrations[version] = Migration(version=version, name=match["name"], path=path)
    return sorted(migrations.values(), key=lambda m: int(m.version))
