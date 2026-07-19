# Model Context Protocol (MCP)

The Model Context Protocol (MCP) is an open protocol for connecting AI applications to external capabilities in a consistent way. An MCP client can discover and invoke tools exposed by an MCP server, instead of requiring a custom integration for every application and service.

MCP separates the AI application from the implementation of a capability. The server owns the capability and its validation; the client connects to the server, discovers what is available, and invokes it when needed. MCP servers can expose three main kinds of features:

- **Tools** are callable actions, such as searching files or calling an API.
- **Resources** provide readable data, such as a document or database record.
- **Prompts** provide reusable prompt templates.

The protocol can run over local standard input/output or an HTTP transport. This project uses a local Streamable HTTP server. The language model does not connect to the MCP server directly: `cli_mcp.py` acts as the client, passes the tool definition to Ollama, executes the model's requested tool call through MCP, and returns the result to Ollama.

## MCP tools in this project

This repository includes a small, real MCP server with three test tools: a ROT13 Caesar cipher, the server's current local date and time, and a calculator. They are intentionally simple so that each part of the integration is easy to verify: server startup, MCP handshake, tool discovery, parameter passing, direct tool calls, and Ollama tool calling.

### Project layout

| File | Purpose |
| --- | --- |
| `mcp/mcp_config.json` | Local server address, port, MCP path, transport, and default Ollama model. |
| `mcp/wrapp_mpc.py` | Generic FastMCP server wrapper that loads the configuration and registers tools. |
| `mcp/rot13.py` | Pure `rot13(word)` implementation without server setup. |
| `mcp/current_datetime.py` | Pure parameterless `datetime()` implementation. |
| `mcp/calculate.py` | Pure `calculate(a, b, operation="+")` implementation. |
| `cli_mcp.py` | Verbose client and end-to-end Ollama integration test. |
| `cli_mcp.json` | Enables or disables project logging for the CLI command. |

### Local endpoint

The current configuration starts the server on this endpoint:

```text
http://127.0.0.1:8000/mcp
```

`cli_mcp.py` starts the generic wrapper in [`mcp/wrapp_mpc.py`](mcp/wrapp_mpc.py), waits until its port is ready, and always stops it after the test. The address, port, and path are configured in [`mcp/mcp_config.json`](mcp/mcp_config.json).

### The `rot13` tool

The tool accepts one parameter:

```json
{"word": "apple"}
```

It converts the input to uppercase, validates that it contains only ASCII letters `A` through `Z`, then shifts every letter by 13 positions with wraparound. For example:

```text
APPLE -> NCCYR
A -> N
N -> A
```

The implementation is isolated in [`mcp/rot13.py`](mcp/rot13.py). The generic wrapper imports and publishes it as an MCP tool.

### The `datetime` tool

This parameterless tool returns the server's current local date and time as an ISO 8601 value, including its UTC offset:

```text
2026-07-18T10:46:30+02:00
```

The implementation is isolated in [`mcp/current_datetime.py`](mcp/current_datetime.py). Because the time is produced by the MCP server, it also verifies that the response came from the external tool rather than from the model itself.

### The `calculate` tool

The calculator accepts two numbers and an optional operation. Addition is used when `operation` is omitted:

```json
{"a": 8, "b": 2, "operation": "+"}
```

Supported operations are `+`, `-`, `*`, and `/`. Division by zero and unsupported operations return a tool error. The implementation is isolated in [`mcp/calculate.py`](mcp/calculate.py).

## Run the integration test

Use the project's virtual environment if it contains the required packages:

```powershell
python .\cli_mcp.py --model qwen3.5:latest --function rot13 --word apple
python .\cli_mcp.py --model qwen3.5:latest --function datetime
python .\cli_mcp.py --model qwen3.5:latest --function calculate --a 8 --b 2 --operation "+"
```

All parameters are optional:

- `--model` selects an Ollama model. Its default comes from `mcp/mcp_config.json`.
- `--function` selects the MCP tool to test. Its current default is `rot13`.
- `--word` supplies the value for tools with a `word` parameter. Its default is `apple` and it is ignored by parameterless tools.
- `--a` and `--b` supply calculator numbers. Their defaults are `2` and `3`.
- `--operation` selects `+`, `-`, `*`, or `/`. Its default is `+`.

A successful direct MCP check includes output similar to:

```text
MCP handshake: OK
MCP endpoint: http://127.0.0.1:8000/mcp
MCP tools: rot13, datetime, calculate
MCP parameter test result: APPLE -> NCCYR
```

The command then performs the full Ollama test: it sends the MCP tool schema to Ollama's `/api/chat` endpoint, expects the model to request the selected tool, forwards those arguments to the MCP server, and returns the tool result to the model for its final response. Progress and errors are also written to the active project's `log.txt` when logging is enabled in `cli_mcp.json`.

## Extending the server

To add another capability, place its plain Python function in the `mcp` directory, import it in `mcp/wrapp_mpc.py`, and register it with `mcp.tool()`. Then run the CLI with its name, for example `--function new_tool`.

The CLI currently prepares arguments automatically for parameterless tools, tools with a `word` parameter, and calculator-style tools with `a` and `b` parameters. Extend `build_tool_arguments()` in `cli_mcp.py` when a new tool requires a different input schema.

## Troubleshooting

- If port `8000` is already occupied, change `port` in `mcp/mcp_config.json` and run the command again.
- If the command reports that `/api/chat` is unavailable, update Ollama and use a model that supports tool calling.
- If the model does not request a tool, choose a tool-capable Ollama model and retry with the explicit `--function` and `--word` arguments.
- The ROT13 tool accepts letters only; values with spaces, numbers, accents, or punctuation are rejected intentionally.

## Further reading

- [Model Context Protocol documentation](https://modelcontextprotocol.io/)
- [MCP Python SDK documentation](https://py.sdk.modelcontextprotocol.io/)
- [Ollama tool calling documentation](https://docs.ollama.com/capabilities/tool-calling)
