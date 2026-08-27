# James help

The main menu reacts to the highlighted key; Enter is not required there.

## Chat

`/bye` exits chat, `/clr` clears its context, and `/mod MODEL` changes the
model for the rest of the session. `/url URL` downloads an HTTP(S) page,
removes its HTML markup, and adds its readable text to the current chat context;
the downloaded text is limited to 20,000 characters. A command from `assistant/commands/sc.json`
can begin a message, for example `/eli5 Explain gravity` or `/plan Prepare a
migration`.

## Flow

Flow opens the Test, Single, Code, Batch, Media, and MCP categories. Choose a
category and its flow with the Up/Down arrows; Enter runs the selected flow.

## Database

Choose List, Show ID, Delete ID, Rating 3, or Filter with the Up/Down arrows;
Enter performs the selected action. Filter values display their record count
first, aligned in a fixed-width column. Monthly filters by calendar month and
Last week lists the current day plus the preceding six days, newest first.

## Setup

James displays the basic `james.json` settings without flow lists. Project
opens active-project settings, Language changes the response language, and
Ollama displays `lib/ollama.json`. Slash commands displays `sc_cz.md` for
Czech, or the command `README.md` for the other languages. Setup options use
arrow selection and Enter.

## Libraries used by James

`james.py` uses the Python standard library, the `requests` package, and three
project-internal modules. Standard-library and external-library links point to
official documentation; internal-module links point to source files with docstrings.

### Python standard library

| Library | Purpose in James | Examples |
| --- | --- | --- |
| [`json`](https://docs.python.org/3/library/json.html) | Reads and writes the James, project, MCP, and command-catalog settings. | `json.loads(...)`, `json.dumps(...)` |
| [`os`](https://docs.python.org/3/library/os.html) | Detects Windows or Unix and reads terminal key presses. | `os.name`, `os.read(...)` |
| [`socket`](https://docs.python.org/3/library/socket.html) | Checks whether a local MCP server is already listening on its port. | `socket.create_connection(...)` |
| [`datetime`](https://docs.python.org/3/library/datetime.html) | Calculates date ranges for database filters. | `date.today()`, `timedelta(days=6)` |
| [`html.parser`](https://docs.python.org/3/library/html.parser.html) | Converts HTML pages to readable text for `/url`. | `HTMLParser`, `handle_data(...)` |
| [`pathlib`](https://docs.python.org/3/library/pathlib.html) | Safely builds and validates project file and directory paths. | `Path(...)`, `path.read_text(...)` |
| [`re`](https://docs.python.org/3/library/re.html) | Recognizes internal chat commands and validates their parameters. | `re.match(...)`, `re.fullmatch(...)` |
| [`subprocess`](https://docs.python.org/3/library/subprocess.html) | Starts `runner.py` plus database, speech, and MCP tools. | `subprocess.run(...)`, `subprocess.Popen(...)` |
| [`sys`](https://docs.python.org/3/library/sys.html) | Uses the active Python interpreter and standard input/output. | `sys.executable`, `sys.stdin.isatty()` |
| [`typing`](https://docs.python.org/3/library/typing.html) | Adds type annotations for clearer, safer code. | `Any`, `dict[str, Any]` |
| [`urllib.parse`](https://docs.python.org/3/library/urllib.parse.html) | Validates the scheme and host of a `/url` address. | `urlparse(url)`, `parsed.netloc` |

### External library

| Library | Purpose in James | Examples |
| --- | --- | --- |
| [`requests`](https://requests.readthedocs.io/en/latest/) | Downloads the HTTP(S) page for `/url`, handling HTTP errors and the timeout. It is listed in `requirements.txt`. | `requests.get(...)`, `response.raise_for_status()` |

### Project-internal modules

| Module | Purpose in James | Examples |
| --- | --- | --- |
| [`lib.wrapp_db`](../lib/wrapp_db.py) | Works with the completed-task database and formats record listings. | `list_task_rows(...)`, `set_task_stars(...)`, `delete_task(...)` |
| [`lib.wrapp_terminal`](../lib/wrapp_terminal.py) | Provides coloured terminal output, ANSI support, and cursor control. | `Terminal().g(...)`, `hide_cursor()`, `ansi_enabled(...)` |
| [`lib.wrapp_vector`](../lib/wrapp_vector.py) | Loads and manages profiles for local RAG databases. | `load_vector_config(...)`, `new_database_profile(...)`, `VectorError` |

In every submenu, `b` or Space returns to the previous menu.
