# Jam3$-01

Jam3$-01 is a small cross-platform terminal menu for the local Ollama tools.
It runs on Windows and Linux without a shell-specific launcher.

## Run

```text
python james.py
```

Press a highlighted key directly; Enter is not required.

## Main menu

- `p` — Project settings
- `c` — Camera capture
- `v` — Voice recording
- `x`, `f`, `w`, `d`, `s` — Reserved sections: chat, flow, cowork, database, and setup
- `h` — Help
- `q` or Escape — Exit

## Configuration

`james.json` contains the application version, the visual menu width, and the
project configuration filename. It also contains the main task database path
and the list of best flows. The active project name is read from the `subdir`
field in `project.json`.

The Project menu can display `project.json` and change its `subdir` value.
