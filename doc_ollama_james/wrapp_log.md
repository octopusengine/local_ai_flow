# Tagy v log.txt

`console_log(...)` a `log_event(...)` zapisují pouze stávající `log.txt`.
Obsah zpráv, formát diagnostických hodnot, průběžný zápis a barevný výstup
terminálu zůstávají zachované. Úpravy tagů se provádějí jen v souboru.

Hlavičky diagnostických událostí a začátku/konce běhu mají jednotný tvar:

```text
2026-09-07T14:32:01.123+02:00 [INFO] [program="agent"] [event="model"] | event: model | model: test
2026-09-07T14:32:02.123+02:00 [ERROR] [program="agent"] [event="summary"] | event: summary | status: failed
```

Čas je ISO 8601 s časovým pásmem. Hodnoty `program` a `event` jsou JSON
řetězce v hranatých závorkách. Původní diagnostická data následují beze změny
v kompaktním nebo víceřádkovém formátu. Explicitní `level` se normalizuje;
bez platné úrovně znamená událost `error`, `status=failed` nebo neprázdné
`error` úroveň `ERROR`, jinak `INFO`.

Konzolové tagy na začátku řádku se rozšíří takto:

| Původní tag | Tagy v souboru |
| --- | --- |
| `[agent]` | `[INFO] [status] [role=assistant]` |
| `[thinking]` | `[DEBUG] [thinking] [role=assistant]` |
| `[answer]` | `[INFO] [answer] [role=assistant]` |
| `[tool]` | `[INFO] [tool_call] [role=assistant]` |
| `[result]` | `[INFO] [tool_result] [role=tool]` |

Úrovně na začátku řádku se zapisují v hranatých závorkách: `DEBUG` jako
`[DEBUG]`, `WARNING`/`[WARNING]` jako `[WARN]`, `CRITICAL` jako `[FATAL]`.
Podporované úrovně jsou TRACE, DEBUG, INFO, WARN, ERROR a FATAL.
Obsah za tagem se nemění. Běžné řádky ani jednotlivé tokeny odpovědi
nedostávají opakované hlavičky. Samotný stderr automaticky neznamená chybu.

Tagy jsou pomocné značky konzole, nikoli autoritativní hranice zpráv modelu.
Rozpoznávají se úplné tagy na začátku řádku v jednom zápisu do streamu;
rozdělený tag se ponechá původní, aby nebylo nutné zdržovat stream bufferem.
Text uprostřed řádku se nepřeznačuje.

Začátek běhu označuje `[event="session_start"]`, konec
`[event="session_end"] [status=completed]`, při výjimce `[status=failed]`
s úrovní ERROR. Zůstává i oddělovač `---`.

Stávající přepínače logování a UTF-8 s BOM se nemění. Historické záznamy
se zpětně nepřepisují; nový formát platí pro další zápisy. Samostatný
`log.jsonl` se nevytváří.
