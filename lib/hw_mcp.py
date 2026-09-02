"""SDK-free, allowlisted hardware operations for the local MCP server.

Only named entries in ``devices.json`` can be listed or executed.  This module
does not expose raw BLE UUIDs, payloads, device addresses, or environment
values, and can therefore be tested without importing the MCP SDK.
"""

from __future__ import annotations

from collections.abc import Mapping

import cli_ble
from lib import device_runner


DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 60.0


def load_hardware_config() -> dict[str, object]:
    """Load the already validated local device catalog."""

    return cli_ble.load_devices_config()


def load_hardware_aliases() -> dict[str, str]:
    """Load GATT aliases used internally by configured transport profiles."""

    return cli_ble.load_gatt_aliases()


def _mapping(value: object) -> Mapping[str, object]:
    """Return a mapping from data already validated by ``cli_ble``."""

    if not isinstance(value, dict):
        raise ValueError("The configured hardware catalog is invalid.")
    return value


def _description(action: Mapping[str, object]) -> str | None:
    """Return an optional public action description."""

    description = action.get("description")
    return description if isinstance(description, str) else None


def _side_effect(action: Mapping[str, object]) -> str:
    """Return a public classification, defaulting conservatively for old entries."""

    value = action.get("side_effect")
    return value if isinstance(value, str) and value else "not_classified"


def _agent_allowed(action: Mapping[str, object]) -> bool:
    """Allow agent execution only when the configuration says so explicitly."""

    return action.get("agent_allowed") is True


def list_hardware_devices(config: Mapping[str, object] | None = None) -> dict[str, object]:
    """List the public device/action catalog without accessing any hardware.

    The response intentionally excludes addresses, profiles, raw payloads, and
    authentication configuration.  Those details remain local implementation
    data rather than agent capabilities.
    """

    active_config = load_hardware_config() if config is None else config
    devices = _mapping(active_config.get("devices"))
    public_devices: list[dict[str, object]] = []
    for device_id in sorted(devices):
        device = _mapping(devices[device_id])
        tools = _mapping(device.get("tools", {}))
        actions: list[dict[str, object]] = []
        for action_id in sorted(tools):
            action = _mapping(tools[action_id])
            item: dict[str, object] = {"action_id": action_id}
            description = _description(action)
            if description is not None:
                item["description"] = description
            item["side_effect"] = _side_effect(action)
            item["agent_allowed"] = _agent_allowed(action)
            actions.append(item)
        public_device: dict[str, object] = {
            "device_id": device_id,
            "actions": actions,
        }
        name = device.get("name")
        if isinstance(name, str):
            public_device["name"] = name
        public_devices.append(public_device)
    return {"devices": public_devices}


def _validation_failure(device_id: object, action_id: object, message: str) -> dict[str, object]:
    """Return a stable failure without echoing untrusted tool arguments."""

    return {
        "ok": False,
        "device_id": device_id if isinstance(device_id, str) else None,
        "action_id": action_id if isinstance(action_id, str) else None,
        "error": {"kind": "validation", "message": message},
    }


def _validate_action_request(
    config: Mapping[str, object], device_id: object, action_id: object, timeout_seconds: object
) -> str | None:
    """Check that a request is limited to one configured named action."""

    if not isinstance(device_id, str) or not device_id:
        return "device_id must be a non-empty configured device ID."
    if not isinstance(action_id, str) or not action_id:
        return "action_id must be a non-empty configured action ID."
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        return "timeout_seconds must be a number."
    if not 1 <= float(timeout_seconds) <= MAX_TIMEOUT_SECONDS:
        return f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS:g}."
    devices = _mapping(config.get("devices"))
    device = devices.get(device_id)
    if not isinstance(device, dict):
        return "device_id is not configured for hardware MCP access."
    tools = device.get("tools")
    if not isinstance(tools, dict) or action_id not in tools:
        return "action_id is not configured for this device."
    action = tools[action_id]
    if not isinstance(action, dict) or not _agent_allowed(action):
        return "action_id is not enabled for agent hardware access."
    return None


def _value_as_json(value: bytes) -> dict[str, object]:
    """Represent arbitrary BLE bytes as safe JSON-compatible text and hex."""

    try:
        text: str | None = value.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    return {"text": text, "hex": value.hex(" ")}


def serialize_device_tool_result(result: device_runner.DeviceToolResult) -> dict[str, object]:
    """Convert the runner result into a stable JSON-safe MCP result."""

    serialized: dict[str, object] = {
        "ok": result.ok,
        "device_id": result.device_id,
        "action_id": result.tool_id,
        "description": result.description,
        "connected": result.connected,
        "authentication_sent": result.authentication_sent,
        "sent": [
            {"characteristic": item.characteristic, **_value_as_json(item.value)}
            for item in result.sent
        ],
        "notifications": [
            {
                "characteristic": item.characteristic,
                "sender": item.sender,
                **_value_as_json(item.value),
            }
            for item in result.notifications
        ],
        "duration_ms": result.duration_ms,
        "diagnostics": list(result.diagnostics),
        "error": None,
    }
    if result.error is not None:
        serialized["error"] = {"kind": result.error.kind, "message": result.error.message}
    return serialized


async def run_hardware_action(
    device_id: object,
    action_id: object,
    timeout_seconds: object = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    """Run one configured hardware action and return a redacted structured result."""

    try:
        config = load_hardware_config()
        validation_error = _validate_action_request(config, device_id, action_id, timeout_seconds)
        if validation_error is not None:
            return _validation_failure(device_id, action_id, validation_error)
        assert isinstance(device_id, str)
        assert isinstance(action_id, str)
        result = await device_runner.run_device_tool(
            config,
            load_hardware_aliases(),
            device_id,
            action_id,
            timeout=float(timeout_seconds),
        )
    except (OSError, RuntimeError, ValueError) as error:
        return _validation_failure(device_id, action_id, f"Hardware configuration error: {error}")
    return serialize_device_tool_result(result)
