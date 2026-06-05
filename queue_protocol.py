"""Message protocol for inter-thread communication."""

import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
from enum import Enum


class MessageType(Enum):
    """Message type enumeration."""
    STATUS_UPDATE = "status_update"
    PROFILE_PAYLOAD = "profile_payload"
    OPERATION_WARNING = "operation_warning"
    EXECUTION_COMPLETE = "execution_complete"


@dataclass(frozen=True)
class Message:
    """Base message class with timestamp and worker ID."""
    timestamp: float = field(default_factory=time.time)
    worker_id: str = field(default="default")
    message_type: MessageType = None

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            **asdict(self),
            "message_type": self.message_type.value if self.message_type else None,
        }


@dataclass(frozen=True)
class StatusUpdate(Message):
    """Status update during profile traversal."""
    profile_url: str = ""
    status: str = ""  # "loading", "parsing", "stored"
    elapsed_sec: float = 0.0
    message_type: MessageType = field(default=MessageType.STATUS_UPDATE, init=False)


@dataclass(frozen=True)
class ProfilePayload(Message):
    """Collected profile data payload."""
    profile_data: Dict[str, Any] = field(default_factory=dict)
    url: str = ""
    message_type: MessageType = field(default=MessageType.PROFILE_PAYLOAD, init=False)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        result = {
            "timestamp": self.timestamp,
            "worker_id": self.worker_id,
            "message_type": self.message_type.value,
            "profile_data": self.profile_data,
            "url": self.url,
        }
        return result


@dataclass(frozen=True)
class OperationWarning(Message):
    """Operational warning (rate limit, CAPTCHA, etc)."""
    severity: str = ""  # "info", "warning", "critical"
    message: str = ""
    action: Optional[str] = None  # "continue", "pause", "shutdown"
    message_type: MessageType = field(default=MessageType.OPERATION_WARNING, init=False)


@dataclass(frozen=True)
class ExecutionComplete(Message):
    """Execution complete or error halt."""
    success: bool = False
    profiles_collected: int = 0
    total_queued: int = 0
    error_type: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    message_type: MessageType = field(default=MessageType.EXECUTION_COMPLETE, init=False)


class MessageFactory:
    """Factory for message creation and deserialization."""

    @staticmethod
    def from_dict(data: dict) -> Message:
        """Deserialize message from dictionary."""
        message_type = data.get("message_type")
        common_args = {
            "timestamp": data.get("timestamp", time.time()),
            "worker_id": data.get("worker_id", "default"),
        }

        if message_type == MessageType.STATUS_UPDATE.value:
            return StatusUpdate(
                **common_args,
                profile_url=data.get("profile_url", ""),
                status=data.get("status", ""),
                elapsed_sec=data.get("elapsed_sec", 0.0),
            )
        elif message_type == MessageType.PROFILE_PAYLOAD.value:
            return ProfilePayload(
                **common_args,
                profile_data=data.get("profile_data", {}),
                url=data.get("url", ""),
            )
        elif message_type == MessageType.OPERATION_WARNING.value:
            return OperationWarning(
                **common_args,
                severity=data.get("severity", ""),
                message=data.get("message", ""),
                action=data.get("action"),
            )
        elif message_type == MessageType.EXECUTION_COMPLETE.value:
            return ExecutionComplete(
                **common_args,
                success=data.get("success", False),
                profiles_collected=data.get("profiles_collected", 0),
                total_queued=data.get("total_queued", 0),
                error_type=data.get("error_type"),
                details=data.get("details", {}),
            )
        else:
            raise ValueError(f"Unknown message type: {message_type}")
