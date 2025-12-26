"""Agent identification and metadata."""

import os
import socket
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


@dataclass
class AgentIdentity:
    """Unique identifier for an agent instance."""

    agent_id: str  # Unique ID (hostname-pid-uuid)
    hostname: str
    pid: int
    started_at: str

    @classmethod
    def create(cls) -> "AgentIdentity":
        """Create a new agent identity."""
        return cls(
            agent_id=f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:8]}",
            hostname=socket.gethostname(),
            pid=os.getpid(),
            started_at=datetime.now().isoformat(),
        )
