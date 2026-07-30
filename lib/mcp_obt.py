"""Read-only MCP tools for the educational One Byte Toy (OBT) BBR API.

The API accepts a four-character hexadecimal public-key address.  The public
tools in this module take an OBT private scalar where applicable, derive that
address locally, and never transmit the private key.

OBT and the BBR API are an educational toy protocol.  Do not use this module
with real keys or real funds.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_API_BASE_URL = "https://www.agamapoint.com/bbr/index.php"
API_BASE_URL_ENVIRONMENT_VARIABLE = "OBT_API_BASE_URL"
DEFAULT_API_KEY = "123"
API_KEY_ENVIRONMENT_VARIABLE = "OBT_API_KEY"
PRIVATE_KEY_ENVIRONMENT_VARIABLE = "obt_key"
API_TIMEOUT_SECONDS = 10.0

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"

P_MOD = 251
ORDER_N = 252
G_POINT: tuple[int, int] = (10, 76)


def _mod(value: int, modulus: int) -> int:
    """Return the non-negative remainder used by the JavaScript OBT client."""

    return value % modulus


def _inverse_mod(value: int, modulus: int) -> int | None:
    """Return a modular inverse for the small educational field."""

    value = _mod(value, modulus)
    for candidate in range(1, modulus):
        if (value * candidate) % modulus == 1:
            return candidate
    return None


def _point_double(point: tuple[int, int] | None) -> tuple[int, int] | None:
    if point is None:
        return None
    x, y = point
    if y == 0:
        return None
    denominator = _inverse_mod(2 * y, P_MOD)
    if denominator is None:
        return None
    slope = _mod((3 * x * x) * denominator, P_MOD)
    x3 = _mod(slope * slope - 2 * x, P_MOD)
    # Keep the ``- y`` from the reference implementation in ess251.js.
    y3 = _mod(slope * (x - x3) - y, P_MOD)
    return x3, y3


def _point_add(
    point1: tuple[int, int] | None, point2: tuple[int, int] | None
) -> tuple[int, int] | None:
    if point1 is None:
        return point2
    if point2 is None:
        return point1
    x1, y1 = point1
    x2, y2 = point2
    if x1 == x2 and y1 != y2:
        return None
    if x1 == x2:
        return _point_double(point1)
    denominator = _inverse_mod(x2 - x1, P_MOD)
    if denominator is None:
        return None
    slope = _mod((y2 - y1) * denominator, P_MOD)
    x3 = _mod(slope * slope - x1 - x2, P_MOD)
    # Keep the ``- y1`` from the reference implementation in ess251.js.
    y3 = _mod(slope * (x1 - x3) - y1, P_MOD)
    return x3, y3


def _scalar_multiply(private_key: int) -> tuple[int, int] | None:
    """Port ``scalar_mult`` from ``obt_cip/ess251.js`` without dependencies."""

    result: tuple[int, int] | None = None
    addend: tuple[int, int] | None = G_POINT
    scalar = _mod(private_key, ORDER_N)
    while scalar > 0:
        if scalar & 1:
            result = _point_add(result, addend)
        addend = _point_double(addend)
        scalar >>= 1
    return result


def _validate_private_key(private_key: int) -> int:
    if isinstance(private_key, bool) or not isinstance(private_key, int):
        raise ValueError("private_key must be an integer from 1 to 251.")
    if not 1 <= private_key < ORDER_N:
        raise ValueError("private_key must be an integer from 1 to 251.")
    return private_key


def _dotenv_value(name: str) -> str | None:
    """Read one simple ``KEY=value`` from the project-local .env file."""

    try:
        lines = DOTENV_PATH.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise RuntimeError(f"Could not read OBT environment file {DOTENV_PATH}: {error}") from error
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value
    return None


def _private_key_from_source(private_key: int | None) -> int:
    """Prefer an explicit scalar, then load the private scalar from .env."""

    if private_key is not None:
        return _validate_private_key(private_key)
    value = os.environ.get(PRIVATE_KEY_ENVIRONMENT_VARIABLE)
    source = f"environment variable {PRIVATE_KEY_ENVIRONMENT_VARIABLE}"
    if value is None:
        value = _dotenv_value(PRIVATE_KEY_ENVIRONMENT_VARIABLE)
        source = f"{DOTENV_PATH.name} variable {PRIVATE_KEY_ENVIRONMENT_VARIABLE}"
    if value is None or not value.strip():
        raise ValueError(
            f"Provide private_key or set {PRIVATE_KEY_ENVIRONMENT_VARIABLE}=<1..251> in {DOTENV_PATH.name}."
        )
    try:
        parsed_private_key = int(value.strip(), 10)
    except ValueError as error:
        raise ValueError(f"{source} must be an integer from 1 to 251.") from error
    return _validate_private_key(parsed_private_key)


def obt_get_address(private_key: int | None = None) -> str:
    """Derive the four-hex-character BBR API address for an OBT private key."""

    point = _scalar_multiply(_private_key_from_source(private_key))
    if point is None:
        raise ValueError("private_key derives the point at infinity and has no API address.")
    x, y = point
    return f"{x:02x}{y:02x}"


def _api_base_url() -> str:
    """Return the configurable API base URL without a query string."""

    base_url = os.environ.get(API_BASE_URL_ENVIRONMENT_VARIABLE, DEFAULT_API_BASE_URL).strip()
    if not base_url:
        raise RuntimeError(f"{API_BASE_URL_ENVIRONMENT_VARIABLE} must not be empty.")
    return base_url.rstrip("?")


def _api_key() -> str:
    """Return the temporary API key required by the current BBR endpoint."""

    api_key = os.environ.get(API_KEY_ENVIRONMENT_VARIABLE, DEFAULT_API_KEY).strip()
    if not api_key:
        raise RuntimeError(f"{API_KEY_ENVIRONMENT_VARIABLE} must not be empty.")
    return api_key


def _get_route(route: str) -> dict[str, Any]:
    """Fetch one read-only BBR route and validate that it returns a JSON object."""

    url = (
        f"{_api_base_url()}?route={quote(route, safe='/')}"
        f"&api_key={quote(_api_key(), safe='')}"
    )
    request = Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    try:
        with urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as error:
        raise RuntimeError(f"OBT API request failed with HTTP {error.code} for route {route!r}.") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach the OBT API for route {route!r}: {error.reason}.") from error
    except OSError as error:
        raise RuntimeError(f"Could not read the OBT API response for route {route!r}: {error}.") from error
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"OBT API returned invalid JSON for route {route!r}.") from error
    if not isinstance(document, dict):
        raise RuntimeError(f"OBT API returned a JSON value other than an object for route {route!r}.")
    if document.get("status") not in (None, "ok"):
        message = document.get("message", document.get("msg", "unknown API error"))
        raise RuntimeError(f"OBT API rejected route {route!r}: {message}")
    return document


def _json_result(document: dict[str, Any]) -> str:
    """Provide stable, readable text content for an MCP tool response."""

    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)


def obt_get_utxo(private_key: int | None = None) -> str:
    """Get UTXO and balance; read the private key from ``.env`` when omitted."""

    address = obt_get_address(private_key)
    document = _get_route(f"get_balance/{address}")
    document.setdefault("address", address)
    unspent_outputs = document.get("unspent_outputs")
    if not isinstance(unspent_outputs, list):
        raise RuntimeError("OBT API balance response does not contain an unspent_outputs list.")
    if "balance" not in document:
        try:
            document["balance"] = sum(item["value"] for item in unspent_outputs if isinstance(item, dict))
        except (KeyError, TypeError) as error:
            raise RuntimeError("OBT API balance response has an invalid UTXO value.") from error
    document.setdefault("utxo_count", len(unspent_outputs))
    return _json_result(document)


def obt_get_balance(private_key: int | None = None) -> str:
    """Return only the current OBT API balance; read the key from ``.env`` when omitted."""

    document = json.loads(obt_get_utxo(private_key))
    balance = document["balance"]
    if isinstance(balance, bool) or not isinstance(balance, (int, float)):
        raise RuntimeError("OBT API balance response has a non-numeric balance.")
    return str(balance)


def obt_get_last_block() -> str:
    """Get the most recent block reported by the OBT BBR API."""

    return _json_result(_get_route("get_last_block"))


def obt_get_block(block_id: int) -> str:
    """Get one OBT BBR block by its positive numeric ID."""

    if isinstance(block_id, bool) or not isinstance(block_id, int) or block_id <= 0:
        raise ValueError("block_id must be a positive integer.")
    return _json_result(_get_route(f"get_block/{block_id}"))


def obt_get_blocks() -> str:
    """Get up to 20 most recent OBT BBR blocks."""

    return _json_result(_get_route("get_blocks"))


def obt_get_tx_raw(txid: int) -> str:
    """Get the raw educational representation of one OBT transaction."""

    if isinstance(txid, bool) or not isinstance(txid, int) or txid <= 0:
        raise ValueError("txid must be a positive integer.")
    return _json_result(_get_route(f"get_tx_raw/{txid}"))


def obt_get_tx(txid: int) -> str:
    """Get the decoded educational representation of one OBT transaction."""

    if isinstance(txid, bool) or not isinstance(txid, int) or txid <= 0:
        raise ValueError("txid must be a positive integer.")
    return _json_result(_get_route(f"get_tx/{txid}"))
