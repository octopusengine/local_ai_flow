# MCP – Model Context Protocol

## Úvod

**MCP (Model Context Protocol)** je otevřený standard vyvinutý firmou Anthropic, který definuje **obecné rozhraní mezi AI modelem (LLM) a externími nástroji, daty a službami**.

Problém, který řeší: bez standardu musí každá integrace (Gmail, GitHub, databáze, Slack...) mít svůj vlastní, "ušitý na míru" konektor. Pro *N* modelů a *M* nástrojů by vznikalo *N×M* různých integrací. MCP zavádí jednotné rozhraní, takže stačí napsat **jeden MCP server** pro daný nástroj a **jakýkoli** MCP-kompatibilní klient (Claude, jiné LLM aplikace) ho může použít.

### Základní architektura

```
┌───────────────┐       MCP protokol         ┌───────────────┐
│  MCP Client   │ ◄─────────────────────────►│  MCP Server   │
│ (např. Claude)│      (JSON-RPC over        │ (nástroj/data)│
└───────────────┘   stdio / HTTP / SSE)      └───────────────┘
```

- **MCP Server** – zpřístupňuje modelu konkrétní schopnosti (např. čtení souborů, dotazy do databáze, volání API).
- **MCP Client** – aplikace s LLM, která se k serveru připojuje a využívá jeho nabízené funkce.
- Komunikace probíhá přes **JSON-RPC**, typicky po `stdio` (lokální proces) nebo přes `HTTP/SSE` (vzdálený server).

### Tři hlavní stavební bloky

1. **Tools (nástroje)** – funkce, které model může zavolat (např. `search_files`, `create_issue`).
2. **Resources (zdroje)** – data, ke kterým může model přistupovat "pasivně" (např. obsah souboru, záznam v databázi).
3. **Prompts (šablony)** – předpřipravené šablony promptů, které server nabízí klientovi.

---

## Jednoduché příklady

### 1. Minimální MCP server v Pythonu (nástroj "sečti dvě čísla")

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-server")

@mcp.tool()
def add(a: int, b: int) -> int:
    """Sečte dvě čísla."""
    return a + b

if __name__ == "__main__":
    mcp.run()
```

Tento server po spuštění nabídne klientovi jediný nástroj `add`, který může LLM zavolat, když potřebuje sečíst dvě čísla.

### 2. Nástroj, který čte soubor (resource)

```python
@mcp.resource("file://poznamky.txt")
def get_notes() -> str:
    """Vrátí obsah poznámek."""
    with open("poznamky.txt", "r", encoding="utf-8") as f:
        return f.read()
```

### 3. Konfigurace MCP serveru v klientovi (např. Claude Desktop)

```json
{
  "mcpServers": {
    "demo-server": {
      "command": "python",
      "args": ["cesta/k/serveru.py"]
    }
  }
}
```

Po přidání této konfigurace klient při startu spustí server jako subproces a automaticky mu nabídne přístup k jeho nástrojům.

### 4. Vzdálený MCP server přes HTTP/SSE

```json
{
  "mcpServers": {
    "vzdaleny-nastroj": {
      "url": "https://priklad.cz/mcp/sse"
    }
  }
}
```

Tady se model připojuje ke vzdálené službě (např. firemnímu API), místo aby server běžel lokálně.

---

## Shrnutí

| Pojem | Význam |
|---|---|
| MCP | Protokol/standard pro propojení LLM s nástroji |
| MCP Server | Poskytuje nástroje/data/prompty |
| MCP Client | Aplikace s LLM, která server využívá |
| Tool | Funkce volatelná modelem |
| Resource | Data čitelná modelem |

MCP tak funguje trochu jako "USB-C pro AI" – jednotný konektor, díky kterému nemusí každá kombinace model↔nástroj vznikat zvlášť.


---


