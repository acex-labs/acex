from collections.abc import Generator
from urllib.parse import quote_plus

from sqlmodel import Session, create_engine


class Connection:
    def __init__(
        self,
        backend: str = "sqlite",  # 'sqlite', 'postgresql', 'mysql'
        dbname: str | None = None,
        user: str | None = None,
        password: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ):
        self.backend = backend.lower()
        self.url = self._build_url(
            backend=self.backend,
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port,
        )
        self.engine = self._create_engine()

    def _build_url(
        self,
        backend: str,
        dbname: str | None,
        user: str | None,
        password: str | None,
        host: str | None,
        port: int | None,
    ) -> str:
        if backend == "sqlite":
            return f"sqlite:///./{dbname or 'app.db'}"

        if backend in {"postgresql", "mysql"}:
            if not all([dbname, user, host]):
                raise ValueError(f"{backend}: dbname, user och host krävs")

            pw = quote_plus(password or "")
            default_port = 5432 if backend == "postgresql" else 3306
            port = port or default_port
            driver = backend
            if backend == "mysql":
                driver = "mysql+pymysql"

            return f"{driver}://{user}:{pw}@{host}:{port}/{dbname}"

        raise ValueError(f"Okänt backend: {backend}")

    def _create_engine(self):
        connect_args = {"check_same_thread": False} if self.backend == "sqlite" else {}
        return create_engine(self.url, echo=False, connect_args=connect_args)

    def get_session(self) -> Generator[Session]:
        with Session(self.engine) as session:
            yield session
