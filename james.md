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
- `f` — Best-flow menu
- `d` — Database menu
- `x`, `w`, `s` — Reserved sections: chat, cowork, and setup
- `h` — Help
- `q` — Exit from the main menu

## Configuration

`james.json` contains the application version, the visual menu width, and the
project configuration filename. It also contains the main task database path
and the list of best flows. The active project name is read from the `subdir`
field in `project.json`.

The Project menu can display `project.json` and change its `subdir` value.
Every submenu returns with `b` or the Left arrow; `q` remains reserved for the
main menu.

## Database browser

Choose `list` in the Database menu to browse records. Use the Up and Down
arrows to select a row. Enter or `s` shows the complete record. Speak its
answer with `c` for Czech, `a` for English, or `e` for Spanish; each uses that
language's default configured voice. `r` changes its rating, and `d` deletes
it after confirmation.

The Database menu also has `filter`, which offers project, selector, and model.
Choose a value from its numbered, arrow-key navigable list to open the filtered
database browser.
