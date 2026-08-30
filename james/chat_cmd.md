**/hlp** show this help
**/cmd** show the localized slash-command catalog from `assistant/commands`
**/bye** quit chat and return to the main menu
**/clr** clear the context buffer and start a new conversation
**/task** list available task JSON files from `assistant/tasks`; **/task** TASK.json changes the Chat flow task and resets the model to that task's model for the rest of this Chat session; a new Chat session starts with `default_task` from `chat_cmd.json` (`task_base.json` by default)
**/db** ID print the `answer` of record ID from the main task database and immediately send it to Chat as the user's message; equivalent to reading the answer with `cli_db.py -E ID`
**/mod** list locally available Ollama models and highlight the active one; **/mod** NEW switches the model for following Chat requests and overrides the model from the selected `/task`
**/lng** list available Chat languages; **/lng** LANGUAGE (`cz`, `en`, or `es`) switch the language for this Chat session
**/proj** show parsed, color-rendered `project.json`; **/proj** SUBDIR temporarily switches the active project subdirectory for this Chat session without changing `project.json`
**/rag** DATA select an existing `rag_wiki/data/wiki_DATA.db` for this Chat session; **/rag** off disconnect it and removes its transient context
**/chunk** FILTER[, FILTER ...] retrieve local FTS5 chunks from the selected wiki. Their count is always `defaults.rag_chunk_count` from `chat_cmd.json` (5 by default). Comma-separated phrases use `AND`, while `(phrase) and/or (phrase)` (or `#(phrase)`) lets you choose the operator; show the attached chunks, then wait for the next chat question
**/ask** FILTER :: QUESTION perform semantic vector retrieval for the filters, attach the configured number of chunks, then submit QUESTION immediately; for example `/ask (bitcoin mining) or (hardware wallet) :: Explain their roles in Bitcoin security.`
**/url** URL add cleaned web-page text to the context
**/add** FILE add a UTF-8 text file from the active project directory to the context
**/cat** show the main `chat_context.txt` with Markdown rendering; **/cat** FILE show a UTF-8 text file from the active project directory without adding it to the context; render `.md` with Markdown colors
**/rec** [FILE.mp3] record the default microphone with `cli_record_mp3.py`; save `record.mp3`, or FILE, directly in the active project directory; press any key, Escape, or Ctrl+C to stop
**/voice** or **/voi** [FILE.mp3] record `record.mp3`, or FILE, conservatively correct likely Czech speech-recognition errors with `/speechfix`, then submit the corrected voice prompt to Chat automatically
**/whisper** [FILE.mp3] transcribe `record.mp3`, or FILE, with `cli_whisper_mp3.py`; save the transcript beside it as `record.txt` or FILE.txt
**/play** [FILE.mp3] play `record.mp3`, or an MP3 anywhere below the active project directory, synchronously
**/say** "TEXT" speak the quoted text with the voice for the current Chat language; **/say** FILE speaks a UTF-8 project file; **/say** without a parameter speaks the latest Chat reply after Markdown cleanup
**/cam** [FILE] capture an image from the camera as `camera.png`, or as FILE, in the active project directory
**/ocr** [FILE] run OCR on `camera.png`, or on FILE; save `ocr.txt` and add it to the chat context as `[OCR]`
**/img** [FILE] describe `camera.png`, or FILE; save `describe.txt`, add it as `[IMAGE]`, and keep the image active for follow-up vision chat
**/ctx** show the number of context sources, conversation turns, and characters
**/src** list the attached context sources only
**/drop** ocr remove all `[OCR]` sources from the chat context
**/save** [FILE] export the current chat context as `chat_export.md`, or as FILE, in the active project directory
**/load** FILE replace the current chat context with a UTF-8 project file; the previous context is discarded
**/find** TEXT find matching text in project text files; use `/add FILE` to attach a result
**/files** or **/ls** list files in the active project directory and its subdirectories
**/clip** add text from the desktop clipboard to the chat context as `[CLIPBOARD]`
**/last** show the latest saved chat reply with James Markdown colors
**/debug** [on|off|true|false] show or set chat diagnostics; defaults to on; when on, preserve live runner output, timings, and executed commands; when off, show the chat reply and one muted status message
**/tldr** [FILE] condense the latest saved chat reply, or a UTF-8 project FILE, into one short paragraph
**/wtf** [FILE] explain the latest saved chat reply, or a UTF-8 project FILE, in plain language
**/tool** --PARAM run `cli_tool.py` with its CLI parameters, for example `/tool --date-time` or `/tool --ping`
**/sum** summarize the current context with the active model and save it to `chat_summary.txt`
**/COMMAND** [/MODIFIER ...] [message] use one catalog command and optional compatible modifiers from sc.json; without message, apply it to the current chat context; for example `/tldr /list /md`
