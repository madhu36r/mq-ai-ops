"""
Tests for the mock MQ alert generator.

These verify the shape and correctness of generated alerts. They do not
assert on random fields (e.g. put_failure_count_last_min) — only on the
structural guarantees.
"""
import json

import pytest

from mq_ai_ops.alert_generator import (
    Alert,
    AlertGenerator,
    Environment,
    Severity,
)


@pytest.fixture
def gen():
    """A fresh generator bound to a fake prod queue manager."""
    return AlertGenerator(env=Environment.PROD, qmgr="QMPROD01")


class TestChannelDown:
    def test_returns_alert_instance(self, gen):
        alert = gen.channel_down("SYSTEM.DEF.SVRCONN")
        assert isinstance(alert, Alert)

    def test_alert_type_is_channel_down(self, gen):
        alert = gen.channel_down("SYSTEM.DEF.SVRCONN")
        assert alert.alert_type == "CHANNEL_DOWN"

    def test_carries_environment_and_qmgr(self, gen):
        alert = gen.channel_down("SYSTEM.DEF.SVRCONN")
        assert alert.environment == Environment.PROD
        assert alert.queue_manager == "QMPROD01"

    def test_reason_code_is_2059(self, gen):
        alert = gen.channel_down("SYSTEM.DEF.SVRCONN")
        assert alert.details["reason_code"] == 2059

    def test_state_is_retrying_or_stopped(self, gen):
        # Random field — assert only that it's one of the allowed values.
        alert = gen.channel_down("SYSTEM.DEF.SVRCONN")
        assert alert.details["channel_state"] in {"RETRYING", "STOPPED"}


class TestQueueFull:
    def test_alert_type_is_queue_full(self, gen):
        alert = gen.queue_full("APP.ORDERS.IN")
        assert alert.alert_type == "QUEUE_FULL"

    def test_severity_is_critical(self, gen):
        alert = gen.queue_full("APP.ORDERS.IN")
        assert alert.severity == Severity.CRITICAL

    def test_current_depth_equals_max_depth(self, gen):
        alert = gen.queue_full("APP.ORDERS.IN", max_depth=10_000)
        assert alert.details["current_depth"] == alert.details["max_depth"] == 10_000

    def test_reason_code_is_2053(self, gen):
        alert = gen.queue_full("APP.ORDERS.IN")
        assert alert.details["reason_code"] == 2053


class TestMessageBackup:
    def test_alert_type_is_message_backup(self, gen):
        alert = gen.message_backup("APP.PAYMENTS.IN", current_depth=1450)
        assert alert.alert_type == "MESSAGE_BACKUP"

    def test_warning_below_2x_threshold(self, gen):
        alert = gen.message_backup(
            "APP.PAYMENTS.IN", current_depth=1500, threshold=1000
        )
        assert alert.severity == Severity.WARNING

    def test_critical_at_or_above_2x_threshold(self, gen):
        alert = gen.message_backup(
            "APP.PAYMENTS.IN", current_depth=2500, threshold=1000
        )
        assert alert.severity == Severity.CRITICAL


class TestSerialization:
    def test_to_dict_is_json_serializable(self, gen):
        alert = gen.channel_down("SYSTEM.DEF.SVRCONN")
        as_json = json.dumps(alert.to_dict())  # would raise if not serializable
        assert isinstance(as_json, str)

    def test_to_dict_uses_string_enums(self, gen):
        alert = gen.queue_full("APP.ORDERS.IN")
        d = alert.to_dict()
        assert d["environment"] == "prod"
        assert d["severity"] == "CRITICAL"