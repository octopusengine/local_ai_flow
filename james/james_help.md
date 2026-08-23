# James help

The main menu reacts to the highlighted key; Enter is not required there.

## Chat

`/bye` exits chat, `/clr` clears its context, and `/mod MODEL` changes the
model for the rest of the session. A command from `assistant/commands/sc.json`
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
Ollama displays `lib/ollama.json`. Setup options use arrow selection and Enter.

In every submenu, `b` or Space returns to the previous menu.
