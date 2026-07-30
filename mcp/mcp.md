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
| [`mcp_config.json`](mcp_config.json) | Local server address, port, MCP path, transport, and default Ollama model. |
| [`wrapp_mcp.py`](wrapp_mcp.py) | Generic FastMCP server wrapper that loads the configuration and registers tools. |
| [`rot13.py`](rot13.py) | Pure `rot13(word)` implementation without server setup. |
| [`current_datetime.py`](current_datetime.py) | Pure parameterless `datetime()` implementation. |
| [`calculate.py`](calculate.py) | Pure `calculate(a, b, operation="+")` implementation. |
| `mcp/memory_server.json` | Project-local stdio configuration for the reference Memory server. |
| `mcp/filesystem_server.json` | Project-local stdio configuration for the reference Filesystem server, restricted to `data_mcp`. |
| `data_mcp/` | Empty dedicated directory that the Filesystem server may access. |
| `cli_mcp.py` | Direct MCP tool test with optional end-to-end Ollama verification; detailed progress requires `"debug": true` in `project.json`. |
| `cli_mcp.json` | Enables or disables project logging for the CLI command. |

### Local endpoint

The current configuration starts the server on this endpoint:

```text
http://127.0.0.1:8000/mcp
```

`cli_mcp.py` starts the generic wrapper in [`wrapp_mcp.py`](wrapp_mcp.py), waits until its port is ready, and always stops it after the test. The address, port, and path are configured in [`mcp_config.json`](mcp_config.json).

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

The implementation is isolated in [`rot13.py`](rot13.py). The generic wrapper imports and publishes it as an MCP tool.

### The `datetime` tool

This parameterless tool returns the server's current local date and time as an ISO 8601 value, including its UTC offset:

```text
2026-07-18T10:46:30+02:00
```

The implementation is isolated in [`current_datetime.py`](current_datetime.py). Because the time is produced by the MCP server, it also verifies that the response came from the external tool rather than from the model itself.

### The `calculate` tool

The calculator accepts two numbers and an optional operation. Addition is used when `operation` is omitted:

```json
{"a": 8, "b": 2, "operation": "+"}
```

Supported operations are `+`, `-`, `*`, and `/`. Division by zero and unsupported operations return a tool error. The implementation is isolated in [`calculate.py`](calculate.py).

## Run the integration test

Use the project's virtual environment if it contains the required packages:

```powershell
python .\cli_mcp.py --list
python .\cli_mcp.py --list --out tools.txt
python .\cli_mcp.py --server-config mcp\memory_server.json --list
python .\cli_mcp.py --server-config mcp\filesystem_server.json --function list_allowed_directories
python .\cli_mcp.py --model qwen3.5:latest --function rot13 --word apple
python .\cli_mcp.py --function datetime --out result.txt
python .\cli_mcp.py --ollama --model qwen3.5:latest --function calculate --a 8 --b 2 --operation "+"
python .\cli_mcp.py --model qwen3.5:latest --function datetime
python .\cli_mcp.py --model qwen3.5:latest --function calculate --a 8 --b 2 --operation "+"
```

All parameters are optional:

- `-h` or `--help` shows command usage and all options.
- `-l` or `--list` starts the MCP server, lists its available tools, and exits without calling Ollama.
- `--out FILE` saves the tool list or direct MCP tool result to a UTF-8 text file directly in the active project directory specified by `project.json`'s `subdir`. For a tool test, the result is written before the final Ollama response arrives.
- `--ollama` additionally verifies the slower end-to-end path where Ollama requests the MCP tool and receives its result. It cannot be combined with `--list`.
- `--server-config FILE` selects a project-local stdio MCP server configuration. It currently cannot be combined with `--ollama`.
- `--args JSON` passes an arbitrary JSON object directly to the selected tool; it is useful for tools whose parameters are not one of the local test schemas.
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

By default the command finishes after the direct MCP tool check. Add `--ollama` for the full Ollama test: it sends the MCP tool schema to Ollama's `/api/chat`, expects the model to request the selected tool, forwards those arguments to the MCP server, and returns the tool result to the model for its final response. With `"debug": false` in `project.json`, it prints only timestamped key milestones, results, and errors; `"debug": true` adds the detailed diagnostic steps. Progress and errors are also written to the active project's `log.txt` when logging is enabled in `project.json`.

After a successful end-to-end test, the direct MCP result is printed on its own green line. When `"db": true` in `project.json`, it is also recorded as the task `answer` in `data/tasks.db` with the active project selector.

## Reference stdio servers

`--server-config` makes the CLI a direct client for a stdio MCP server described by a JSON file inside this project. The current configuration format is deliberately small and portable between Windows and Linux:

```json
{
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-memory"],
  "cwd": "."
}
```

The MCP Python SDK normalizes the executable launch on Windows, so the configurations use `npx` directly rather than a platform-specific shell wrapper. Node.js and `npx` must be installed; the first run downloads the selected reference server package.

### Memory

```powershell
python .\cli_mcp.py --server-config mcp\memory_server.json --list
```

Start with `--list`, then select a displayed tool and provide its exact arguments with `--args JSON`. For example, PowerShell needs single quotes around JSON that itself uses double quotes:

```powershell
python .\cli_mcp.py --server-config mcp\memory_server.json --function create_entities --args '{"entities":[{"name":"test","entityType":"note","observations":["hello MCP"]}]}'
```

### Filesystem

```powershell
python .\cli_mcp.py --server-config mcp\filesystem_server.json --list
python .\cli_mcp.py --server-config mcp\filesystem_server.json --function list_allowed_directories
```

The configuration passes only `data_mcp` as the allowed directory. It must remain a disposable test directory: the reference Filesystem server can read, write, create, move, and delete files inside its allowed paths.

On POSIX shells, use single quotes for JSON as well. The paths in the configuration are relative to the project root, so the same files work on Windows and Linux.

## Extending the server

To add another capability, place its plain Python function in the `mcp` directory, import it in `mcp/wrapp_mcp.py`, and register it with `mcp.tool()`. Then run the CLI with its name, for example `--function new_tool`.

The CLI prepares arguments automatically for parameterless tools, tools with a `word` parameter, and calculator-style tools with `a` and `b` parameters. For any other tool, supply its schema-compatible arguments with `--args JSON`; extending `build_tool_arguments()` remains useful for a frequently used local schema.

## Troubleshooting

- If port `8000` is already occupied, change `port` in `mcp/mcp_config.json` and run the command again.
- If the command reports that `/api/chat` is unavailable, update Ollama and use a model that supports tool calling.
- If the model does not request a tool, choose a tool-capable Ollama model and retry with the explicit `--function` and `--word` arguments.
- The ROT13 tool accepts letters only; values with spaces, numbers, accents, or punctuation are rejected intentionally.
- If a reference stdio server does not start, confirm that `node` and `npx` are on `PATH`, then run its `--list` command to see its diagnostics.

## Further reading

- [Model Context Protocol documentation](https://modelcontextprotocol.io/)
- [MCP Python SDK documentation](https://py.sdk.modelcontextprotocol.io/)
- [Ollama tool calling documentation](https://docs.ollama.com/capabilities/tool-calling)
