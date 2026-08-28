**/hlp** show this help
**/cmd** show the localized slash-command catalog from `assistant/commands`
**/bye** quit chat and return to the main menu
**/clr** clear the context buffer and start a new conversation
**/mod** list locally available Ollama models and highlight the active one; **/mod** NEW switch the chat model
**/rag** DATA select an existing `rag_wiki/data/wiki_DATA.db` for this Chat session; **/rag** off disconnect it and removes its transient context
**/chunk** N FILTER[, FILTER ...] retrieve up to N local FTS5 chunks from the selected wiki; use one to three comma-separated phrases (plain, `(phrase)`, or `#(phrase)`) as retrieval filters; parenthesized filters may be followed by QUESTION to answer immediately
**/url** URL add cleaned web-page text to the context
**/add** FILE add a UTF-8 text file from the active project directory to the context
**/cat** FILE show a UTF-8 text file from the active project directory without adding it to the context; render `.md` with James Markdown colors
**/cam** [FILE] capture an image from the camera as `camera.png`, or as FILE, in the active project directory
**/ocr** [FILE] run OCR on `camera.png`, or on FILE; save `ocr.txt` and add it to the chat context as `[OCR]`
**/img** [FILE] describe `camera.png`, or FILE; save `describe.txt`, add it as `[IMAGE]`, and keep the image active for follow-up vision chat
**/ctx** show the number of context sources, conversation turns, and characters
**/src** list the attached context sources only
**/drop** ocr remove all `[OCR]` sources from the chat context
**/save** [FILE] export the current chat context as `chat_export.md`, or as FILE, in the active project directory
**/load** FILE replace the current chat context with a UTF-8 project file; the previous context is discarded
**/find** TEXT find matching text in project text files; use `/add FILE` to attach a result
**/files** list files in the active project directory and its subdirectories
**/clip** add text from the desktop clipboard to the chat context as `[CLIPBOARD]`
**/last** show the latest saved chat reply
**/debug** [on|off] show or set chat diagnostics; defaults to off; when on, preserve live runner output, timings, and executed commands
**/tldr** [FILE] condense the latest saved chat reply, or a UTF-8 project FILE, into one short paragraph
**/wtf** [FILE] explain the latest saved chat reply, or a UTF-8 project FILE, in plain language
**/tool** --PARAM run `cli_tool.py` with its CLI parameters, for example `/tool --date-time` or `/tool --ping`
**/sum** summarize the current context with the active model and save it to `chat_summary.txt`
**/COMMAND** [/MODIFIER ...] [message] use one catalog command and optional compatible modifiers from sc.json; without message, apply it to the current chat context; for example `/tldr /list /md`
