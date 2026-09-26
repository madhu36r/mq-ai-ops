"""
Mock IBM MQ alert generator.

Simulates realistic alerts from queue managers across five environments,
so downstream AI components can be developed without a real MQ instance.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import random
import uuid


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class Environment(str, Enum):
    DEV = "dev"
    SIT = "sit"
    UAT = "uat"
    PROD_LIKE = "prod-like"
    PROD = "prod"


@dataclass
class Alert:
    """A single MQ alert event."""
    alert_id: str
    timestamp: str
    environment: Environment
    queue_manager: str
    severity: Severity
    alert_type: str
    resource: str          # queue name or channel name
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp,
            "environment": self.environment.value,
            "queue_manager": self.queue_manager,
            "severity": self.severity.value,
            "alert_type": self.alert_type,
            "resource": self.resource,
            "message": self.message,
            "details": self.details,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_alert_id() -> str:
    return f"alert-{uuid.uuid4().hex[:8]}"

# --------------------------------------------------------------------------
# Scenario generators
#
# Each scenario models a common IBM MQ failure mode. Real MQ produces
# hundreds of event message types (see the "IBM MQ Event Messages" doc);
# we're picking three that:
#   1. Occur frequently in production
#   2. Have clear cascading effects (good for the correlation logic later)
#   3. Have well-known remediation steps (good for the RAG + agent phases)
# --------------------------------------------------------------------------


class AlertGenerator:
    """
    Generates realistic mock IBM MQ alerts for a given environment
    and queue manager.

    Usage:
        gen = AlertGenerator(env=Environment.PROD, qmgr="QMPROD01")
        alert = gen.channel_down("SYSTEM.DEF.SVRCONN")
        print(alert.to_dict())
    """

    def __init__(self, env: Environment, qmgr: str):
        self.env = env
        self.qmgr = qmgr

    # ---- scenario 1: channel down --------------------------------------
    def channel_down(self, channel_name: str) -> Alert:
        """
        Simulates a sender/receiver channel entering RETRYING or STOPPED state.
        Corresponds to MQ event: Channel Stopped (MQRC 2059 on connect attempt).
        """
        state = random.choice(["RETRYING", "STOPPED"])
        reason_code = 2059  # MQRC_Q_MGR_NOT_AVAILABLE (typical for down channels)
        return Alert(
            alert_id=_new_alert_id(),
            timestamp=_now_iso(),
            environment=self.env,
            queue_manager=self.qmgr,
            severity=Severity.CRITICAL if state == "STOPPED" else Severity.WARNING,
            alert_type="CHANNEL_DOWN",
            resource=channel_name,
            message=f"Channel {channel_name} on {self.qmgr} is {state}",
            details={
                "channel_type": "SVRCONN",
                "channel_state": state,
                "reason_code": reason_code,
                "reason_text": "MQRC_Q_MGR_NOT_AVAILABLE",
                "last_msg_time": _now_iso(),
                "connection_name": "10.42.17.9(1414)",
            },
        )

    # ---- scenario 2: queue full ----------------------------------------
    def queue_full(self, queue_name: str, max_depth: int = 5000) -> Alert:
        """
        Simulates a queue reaching MAXDEPTH — PUT operations start failing
        with MQRC 2053 (MQRC_Q_FULL).
        """
        current_depth = max_depth  # by definition, full
        return Alert(
            alert_id=_new_alert_id(),
            timestamp=_now_iso(),
            environment=self.env,
            queue_manager=self.qmgr,
            severity=Severity.CRITICAL,
            alert_type="QUEUE_FULL",
            resource=queue_name,
            message=(
                f"Queue {queue_name} on {self.qmgr} is FULL "
                f"({current_depth}/{max_depth}). PUT operations failing with MQRC 2053."
            ),
            details={
                "current_depth": current_depth,
                "max_depth": max_depth,
                "reason_code": 2053,
                "reason_text": "MQRC_Q_FULL",
                "put_failure_count_last_min": random.randint(50, 500),
            },
        )

    # ---- scenario 3: message backup ------------------------------------
    def message_backup(
        self,
        queue_name: str,
        current_depth: int,
        threshold: int = 1000,
    ) -> Alert:
        """
        Simulates a queue whose depth is climbing steadily because consumers
        aren't keeping up. Not yet full — early warning.
        """
        severity = Severity.WARNING if current_depth < threshold * 2 else Severity.CRITICAL
        return Alert(
            alert_id=_new_alert_id(),
            timestamp=_now_iso(),
            environment=self.env,
            queue_manager=self.qmgr,
            severity=severity,
            alert_type="MESSAGE_BACKUP",
            resource=queue_name,
            message=(
                f"Queue {queue_name} on {self.qmgr} depth is {current_depth}, "
                f"above threshold {threshold}. Consumers may be lagging."
            ),
            details={
                "current_depth": current_depth,
                "threshold": threshold,
                "oldest_msg_age_seconds": random.randint(60, 900),
                "input_open_count": random.randint(0, 3),  # 0 = no consumers!
            },
        )