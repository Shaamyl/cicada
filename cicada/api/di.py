from cicada.api.infra.environment_repo import EnvironmentRepo
from cicada.api.infra.github.stop_session import github_session_terminator
from cicada.api.infra.installation_repo import InstallationRepo
from cicada.api.infra.repository_repo import RepositoryRepo
from cicada.api.infra.runner_repo import RunnerRepo
from cicada.api.infra.session_repo import SessionRepo
from cicada.api.infra.terminal_session_repo import TerminalSessionRepo
from cicada.api.infra.user_repo import UserRepo
from cicada.api.infra.waitlist_repo import WaitlistRepo
from cicada.application.session.stop_session import SessionTerminator
from cicada.domain.repo.environment_repo import IEnvironmentRepo
from cicada.domain.repo.installation_repo import IInstallationRepo
from cicada.domain.repo.repository_repo import IRepositoryRepo
from cicada.domain.repo.runner_repo import IRunnerRepo
from cicada.domain.repo.session_repo import ISessionRepo
from cicada.domain.repo.terminal_session_repo import ITerminalSessionRepo
from cicada.domain.repo.user_repo import IUserRepo
from cicada.domain.repo.waitlist_repo import IWaitlistRepo


class DiContainer:  # pragma: no cover
    # TODO: move settings classes here so they can be injected without patching

    @classmethod
    def user_repo(cls) -> IUserRepo:
        return UserRepo()

    @classmethod
    def session_repo(cls) -> ISessionRepo:
        return SessionRepo()

    @classmethod
    def terminal_session_repo(cls) -> ITerminalSessionRepo:
        return TerminalSessionRepo()

    @classmethod
    def waitlist_repo(cls) -> IWaitlistRepo:
        return WaitlistRepo()

    @classmethod
    def repository_repo(cls) -> IRepositoryRepo:
        return RepositoryRepo()

    @classmethod
    def environment_repo(cls) -> IEnvironmentRepo:
        return EnvironmentRepo()

    @classmethod
    def installation_repo(cls) -> IInstallationRepo:
        return InstallationRepo()

    @classmethod
    def runner_repo(cls) -> IRunnerRepo:
        return RunnerRepo()

    @classmethod
    def session_terminators(cls) -> dict[str, SessionTerminator]:
        return {"github": github_session_terminator}
