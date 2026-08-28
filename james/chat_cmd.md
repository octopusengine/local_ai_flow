**/hlp** show this help
**/bye** quit chat and return to the main menu
**/clr** clear the context buffer and start a new conversation
**/mod** NEW switch the chat model
**/url** URL add cleaned web-page text to the context
**/add** FILE add a UTF-8 text file from the active project directory to the context
**/cam** [FILE] capture an image from the camera as `camera.png`, or as FILE, in the active project directory
**/ocr** [FILE] run OCR on `camera.png`, or on FILE; save `ocr.txt` and add it to the chat context as `[OCR]`
**/img** [FILE] describe `camera.png`, or FILE; save `describe.txt` and add it to the chat context as `[IMAGE]`
**/ctx** show the number of context sources, conversation turns, and characters
**/src** list the attached context sources only
**/drop** ocr remove all `[OCR]` sources from the chat context
**/save** [FILE] export the current chat context as `chat_export.md`, or as FILE, in the active project directory
**/load** FILE replace the current chat context with a UTF-8 project file; the previous context is discarded
**/find** TEXT find matching text in project text files; use `/add FILE` to attach a result
**/clip** add text from the desktop clipboard to the chat context as `[CLIPBOARD]`
**/last** show the latest saved chat reply
**/tool** --PARAM run `cli_tool.py` with its CLI parameters, for example `/tool --date-time` or `/tool --ping`
**/sum** summarize the current context with the active model and save it to `chat_summary.txt`
**/COMMAND** [message] use any command from sc.json; without message, apply it to the current chat context
