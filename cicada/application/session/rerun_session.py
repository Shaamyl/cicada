from pathlib import Path
from tempfile import TemporaryDirectory

from cicada.application.session.common import (
    IWorkflowGatherer,
    IWorkflowRunner,
)
from cicada.ast.nodes import FileNode, RunOnStatement, RunType
from cicada.domain.repo.environment_repo import IEnvironmentRepo
from cicada.domain.repo.repository_repo import IRepositoryRepo
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.domain.services.repository import get_env_vars_for_repo
from cicada.domain.session import Session, SessionStatus


class RerunSession:
    """
    This service is very similar to the MakeSessionFromTrigger service, except
    that this service simply re-runs the most recent run for a session instead
    of creating a new session from a trigger.

    All arguments to this service are the same as the MakeSessionFromTrigger
    service. The only difference between these services is that the handle()
    method takes a session object, and a new session with the same ID is
    created, except the `run` number is incremented by 1.

    One edge case with this service is that if no workflow files are found when
    running the gather step, the session will not re-run. Since we know the SHA
    that the session was ran at, we might not need even run the gather stage,
    but for now this is how it is executing.
    """

    def __init__(
        self,
        session_repo: ISessionRepo,
        terminal_session_repo: ITerminalSessionRepo,
        workflow_runner: IWorkflowRunner,
        gather_workflows: IWorkflowGatherer,
        env_repo: IEnvironmentRepo | None = None,
        repository_repo: IRepositoryRepo | None = None,
    ) -> None:
        self.session_repo = session_repo
        self.terminal_session_repo = terminal_session_repo
        self.workflow_runner = workflow_runner
        self.gather_workflows = gather_workflows
        self.env_repo = env_repo
        self.repository_repo = repository_repo

    async def handle(self, session: Session) -> Session | None:
        with TemporaryDirectory() as cloned_repo:
            return await self._handle(Path(cloned_repo), session)

    async def _handle(
        self, cloned_repo: Path, session: Session
    ) -> Session | None:
        # TODO: make these required
        if self.env_repo and self.repository_repo:
            session.trigger.env = get_env_vars_for_repo(
                self.env_repo, self.repository_repo, session.trigger
            )

        # TODO: assert previous session(s) arent pending

        files = await self.gather_workflows(session.trigger, cloned_repo)

        if not files:
            return None

        filenode = files[0]

        # TODO: isolate this logic (shared with MakeSessionFromTrigger service)
        match filenode:
            case FileNode(run_on=RunOnStatement(type=RunType.SELF_HOSTED)):
                status = SessionStatus.BOOTING
                run_on_self_hosted = True

            case _:
                status = SessionStatus.PENDING
                run_on_self_hosted = False

        session = Session(
            id=session.id,
            status=status,
            trigger=session.trigger,
            run=session.run + 1,
            run_on_self_hosted=run_on_self_hosted,
        )

        def callback(data: bytes) -> None:
            self.terminal_session_repo.append_to_session(
                session.id, data, run=session.run
            )

        terminal = self.terminal_session_repo.create(
            session.id, run=session.run
        )
        terminal.callback = callback

        self.session_repo.create(session)

        await self.workflow_runner(session, terminal, cloned_repo, filenode)
        assert session.status != SessionStatus.PENDING
        assert session.finished_at is not None

        self.session_repo.update(session)

        return session
