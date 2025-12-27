"""Heartbeat management for issue assignments."""

import threading
from dataclasses import dataclass

from structlog import get_logger

from globallm.storage.issue_store import IssueStore

logger = get_logger(__name__)

DEFAULT_HEARTBEAT_INTERVAL = 60  # seconds
DEFAULT_HEARTBEAT_TIMEOUT = 1800  # 30 minutes


@dataclass
class HeartbeatConfig:
    """Configuration for heartbeat manager."""

    interval_seconds: int = DEFAULT_HEARTBEAT_INTERVAL
    timeout_seconds: int = DEFAULT_HEARTBEAT_TIMEOUT


class HeartbeatManager:
    """Manage heartbeats for assigned issues."""

    def __init__(
        self,
        agent_id: str,
        issue_store: IssueStore,
        config: HeartbeatConfig | None = None,
    ) -> None:
        """Initialize heartbeat manager.

        Args:
            agent_id: Agent identifier
            issue_store: Issue store instance
            config: Heartbeat configuration
        """
        self.agent_id = agent_id
        self.issue_store = issue_store
        self.config = config or HeartbeatConfig()
        self._current_issue: tuple[str, int] | None = None  # (repo, number)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start_monitoring(self, repository: str, number: int) -> None:
        """Start sending heartbeats for an issue.

        Args:
            repository: Repository name
            number: Issue number
        """
        self._current_issue = (repository, number)
        self._stop_event.clear()

        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self._thread.start()
            logger.info(
                "heartbeat_monitoring_started",
                repository=repository,
                number=number,
            )

    def stop_monitoring(self) -> None:
        """Stop sending heartbeats."""
        self._stop_event.set()
        self._current_issue = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            logger.info("heartbeat_monitoring_stopped")

    def _heartbeat_loop(self) -> None:
        """Background thread that sends periodic heartbeats."""
        while not self._stop_event.is_set():
            if self._current_issue:
                repository, number = self._current_issue
                success = self.issue_store.send_heartbeat(
                    repository, number, self.agent_id
                )
                if not success:
                    logger.warning(
                        "heartbeat_failed",
                        repository=repository,
                        number=number,
                    )
                    # Issue may have been reassigned - stop monitoring
                    self.stop_monitoring()
                    break

            # Wait for next interval or stop signal
            self._stop_event.wait(self.config.interval_seconds)
