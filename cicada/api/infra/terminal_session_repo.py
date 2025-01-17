from cicada.api.infra.db_connection import DbConnection
from cicada.domain.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.domain.session import SessionId
from cicada.domain.terminal_session import TerminalSession

# TODO: move to class (as singleton)
LIVE_TERMINAL_SESSIONS = dict[tuple[SessionId, int], TerminalSession]()


class TerminalSessionRepo(ITerminalSessionRepo, DbConnection):
    def append_to_session(
        self, session_id: SessionId, data: bytes, run: int = -1
    ) -> None:
        if run == -1:
            run = self._get_run_count_for_session(session_id)

        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT INTO terminal_sessions (session_id, lines)
            VALUES (?, ?)
            ON CONFLICT(session_id)
            DO UPDATE SET lines=lines || excluded.lines;
            """,
            [f"{session_id}#{run}", data],
        )

        self.conn.commit()

    def get_by_session_id(
        self, session_id: SessionId, run: int = -1
    ) -> TerminalSession | None:
        if run == -1:
            run = self._get_run_count_for_session(session_id)

        if terminal := LIVE_TERMINAL_SESSIONS.get((session_id, run)):
            return terminal

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT lines FROM terminal_sessions WHERE session_id=?;
            """,
            [f"{session_id}#{run}"],
        )

        if rows := cursor.fetchone():
            terminal = TerminalSession()
            terminal.chunks = [rows[0].encode()]
            terminal.finish()

            return terminal

        return None

    def create(self, session_id: SessionId, run: int = -1) -> TerminalSession:
        terminal = TerminalSession()

        if run == -1:
            run = self._get_run_count_for_session(session_id) + 1

        LIVE_TERMINAL_SESSIONS[(session_id, run)] = terminal

        self.conn.execute(
            "INSERT INTO terminal_sessions (session_id, lines) VALUES (?, '')",
            [f"{session_id}#{run}"],
        )
        self.conn.commit()

        return terminal

    # TODO: make this function less hacky
    def _get_run_count_for_session(self, session_id: SessionId) -> int:
        rows = self.conn.execute(
            """
            SELECT session_id
            FROM terminal_sessions
            WHERE session_id LIKE ?||'%';
            """,
            [session_id],
        ).fetchall()

        return max(
            (int(row["session_id"].split("#")[-1]) for row in rows),
            default=0,
        )
