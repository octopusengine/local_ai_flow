# Přímé Python nástroje vs. MCP pro práci se soubory

Kontext: lokální běh malého LLM modelu, nástroje volané přímo v Pythonu v testovacím prostředí.

## Shrnutí

MCP (Model Context Protocol) nedává modelu nic, co by nešlo udělat obyčejnou Python funkcí zavolanou z tool-calling smyčky. Rozdíl je v tom, že MCP tuto funkčnost **standardizuje, izoluje do samostatného procesu a dělá znovupoužitelnou napříč klienty**. Pro solo experiment v jednom skriptu je to obvykle zbytečná režie navíc.

## Kdy si vystačíš s přímými Python nástroji

- **Jeden proces, jeden model, jedno prostředí** — žádná mezivrstva, nižší latence, míň věcí, co se můžou rozbít.
- **Rychlá iterace** — měníš schéma nástrojů často; v Pythonu je to jedna funkce a jeden JSON schema blok.
- **Ladění a testování** — plná kontrola nad tím, co se přesně děje, žádný serializační overhead ani meziproces.

### Příklad: přímý Python nástroj

```python
import json

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

TOOLS = [
    {
        "name": "read_file",
        "description": "Přečte obsah souboru na daném path.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }
]

# ve smyčce modelu:
def dispatch(tool_name, args):
    if tool_name == "read_file":
        return read_file(**args)
    raise ValueError(f"Neznámý nástroj: {tool_name}")

# model vrátí tool_call -> zavoláš dispatch() -> výsledek pošleš zpět jako tool result
result = dispatch("read_file", {"path": "notes.txt"})
```

Žádný meziproces, žádný protokol — funkce se prostě zavolá.

## Kdy začne dávat smysl MCP

- **Sdílení napříč klienty** — stejný souborový nástroj chceš použít v Claude Desktopu, nějakém IDE i vlastním agentovi, aniž bys psal glue kód pro každého zvlášť. MCP server napíšeš jednou.
- **Oddělení exekuce od modelu** — MCP server běží jako samostatný proces (stdio nebo SSE). Pád nebo bug v souborovém nástroji nesestřelí inferenční smyčku. Snazší sandboxing na úrovni procesu/OS.
- **Hotová řešení** — existuje řada hotových MCP serverů (filesystem, git, sqlite...), takže je jen připojíš místo psaní vlastních `read_file`/`write_file` wrapperů.
- **Permission model** — MCP má vestavěnou představu o discovery nástrojů a schvalování přístupu; hodí se, když nechceš, aby měl model bianco přístup k celému disku.
- **Škálování mimo jeden skript** — víc agentů, víc uživatelů, remote nasazení, kde tool a model neběží na stejném stroji.

### Příklad: minimální MCP filesystem server (koncept)

```python
# server.py — samostatný proces, komunikuje přes stdio
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

app = Server("filesystem-tools")

@app.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="read_file",
            description="Přečte obsah souboru na daném path.",
            inputSchema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "read_file":
        with open(arguments["path"], "r", encoding="utf-8") as f:
            return [types.TextContent(type="text", text=f.read())]
    raise ValueError(f"Neznámý nástroj: {name}")

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())
```

Klient (model/agent) se k tomuto serveru připojí přes MCP protokol a nemusí vůbec vědět, že jde o Python — server by mohl být klidně v jiném jazyce.

## Rozhodovací tabulka

| Kritérium | Přímý Python nástroj | MCP |
|---|---|---|
| Latence | Nižší | Vyšší (meziproces, serializace) |
| Izolace / sandboxing | Žádná (sdílí proces s modelem) | Samostatný proces |
| Znovupoužitelnost napříč klienty | Nízká | Vysoká |
| Rychlost iterace | Velmi vysoká | Nižší (nutný restart serveru atd.) |
| Hotová řešení k dispozici | Musíš psát sám | Existují hotové servery |
| Vhodné pro | Solo experiment, jeden skript | Sdílené nástroje, víc agentů/klientů, produkční nasazení |

## Závěr

Pro tvůj současný setup — lokální malý model, testovací prostředí, nástroje přímo v Pythonu — dává smysl zůstat u přímých funkcí. MCP se vyplatí ve chvíli, kdy budeš chtít stejný souborový nástroj používat opakovaně napříč různými kontexty (jiný klient, jiný agent, produkční nasazení), nebo když budeš chtít mezi modelem a souborovým systémem jasnou procesní/bezpečnostní hranici.
