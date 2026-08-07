# MCP „2.0“: co je nového, jak se nasazuje a kam směřuje

*Stav k 7. 8. 2026*

## Krátké shrnutí

Model Context Protocol (MCP) je otevřený protokol pro připojování aplikací s AI k nástrojům, datům a předpřipraveným pracovním postupům. Dává klientovi (např. chatovací aplikaci nebo agentovi) jednotný způsob, jak zjistit, co vzdálená služba nabízí, číst kontext a bezpečně vyvolat akci.

V běžné řeči se nyní mluví o „MCP 2.0“, ale je dobré rozlišovat tři odlišné věci:

| Označení | Co skutečně znamená |
| --- | --- |
| **MCP `2026-07-28`** | Aktuální vydání samotné specifikace protokolu; nahradilo revizi `2025-11-25`. |
| **SDK 2.0** | Verze některých klientských knihoven, například oficiálního C# SDK. Není to univerzální číslování protokolu. |
| **JSON-RPC 2.0** | Formát zpráv, na němž MCP stojí; nejde o novou verzi MCP. |

Nejdůležitější změna je posun od dlouho žijícího, stavového spojení ke **stateless HTTP**: jednotlivý požadavek nese potřebnou identitu a metainformace sám. MCP se tím mnohem lépe hodí pro kontejnery, load balancery, serverless i edge nasazení.

## O co jde

MCP lze chápat jako „standardní konektor“ mezi AI a okolním softwarem. Místo toho, aby každá aplikace s modelem měla vlastní integraci pro databázi, úložiště, CRM nebo interní API, vystaví služba MCP server a klient se s ní domluví stejnými pravidly.

Základní role jsou:

- **Host** – aplikace, v níž uživatel pracuje (desktopový klient, IDE, agentní platforma).
- **MCP client** – komponenta hosta, která komunikuje s jedním MCP serverem.
- **MCP server** – adaptér k datům, API nebo firemní službě.

Server obvykle vystavuje tři druhy funkcí:

| Prvek | K čemu je | Typický příklad |
| --- | --- | --- |
| **Prompts** | Uživatelem volené šablony/instrukce. | `/analyzuj-projekt` |
| **Resources** | Kontextová data, která klient připojí modelu. | soubor, dokumentace, Git historie |
| **Tools** | Akce či dotazy, které může model vyvolat. | vyhledat objednávku, založit issue, zapsat záznam |

MCP tedy není model, agentní framework ani univerzální bezpečnostní hranice. Je to komunikační vrstva. Kvalitu plánování obstarává host/model; autorizaci, validaci vstupů, oprávnění a ochranu dat musí správně implementovat celá integrace.

## Co přináší aktuální generace MCP

### 1. Bezstavové jádro protokolu

Zmizel povinný handshake `initialize`/`initialized` i hlavička `Mcp-Session-Id`. Každý požadavek nyní nese verzi protokolu, informaci o klientovi a jeho schopnostech. Volání proto může obsloužit libovolná instance za obyčejným round-robin load balancerem – bez sticky sessions a bez sdíleného session storage na úrovni protokolu.

„Bezstavový protokol“ neznamená, že aplikace nesmí mít stav. Pokud nástroj založí například pracovní košík nebo běh analýzy, vrátí klientovi explicitní identifikátor (`basketId`, `jobId`) a další volání jej předávají jako běžný parametr. Stav je tím viditelný, auditovatelný a přenositelný mezi kroky agenta.

### 2. HTTP, které rozumí běžná infrastruktura

Pro Streamable HTTP jsou standardizovány hlavičky `Mcp-Method` a `Mcp-Name`. Proxy, API gateway, WAF, rate limiter nebo observability nástroj díky nim pozná volání typu `tools/call` a konkrétní nástroj, aniž by musel analyzovat JSON tělo požadavku.

Praktický přínos:

- pravidla typu „nástroj `payments/refund` pouze přes schválenou síť“;
- oddělené limity, metriky a audit pro citlivé nástroje;
- standardní provoz přes reverse proxy, Kubernetes Ingress, CDN/edge či serverless.

### 3. Interakce bez trvale otevřeného kanálu (MRTR)

Multi Round-Trip Requests (MRTR) řeší situaci, kdy nástroj potřebuje během práce doplnit údaj nebo potvrzení uživatele. Server místo zpětného volání po otevřeném spojení vrátí `input_required`; klient získá vstup a původní požadavek zopakuje s `inputResponses`.

Je to důležité například pro potvrzení finanční operace, výběr ze dvou variant nebo doplnění chybějícího parametru. Tato interakce zůstává možná i ve stateless architektuře.

### 4. Cache a stabilnější katalog nástrojů

Odpovědi z `tools/list`, `prompts/list`, `resources/list` a `resources/read` mohou uvést `ttlMs` a `cacheScope`; pořadí položek je určeno deterministicky. Klient tak nemusí katalog načítat při každém spojení, sníží provoz a stabilnější kontext pomáhá i cache na straně modelu.

### 5. Rozšíření místo nafukování jádra

Specifikace zavádí formální rámec pro rozšíření. Mezi významná patří:

- **Tasks** pro dlouhotrvající práci: klient může vytvořený úkol zjišťovat přes `tasks/get`, dostávat změny a server může stav ukládat do trvalého úložiště;
- **MCP Apps** pro interaktivní rozhraní poskytované nástrojem přímo uvnitř podporujícího hosta;
- **Enterprise Managed Authorization (EMA)** pro řízené podnikové autorizační scénáře.

Ne každé rozšíření podporuje každý klient nebo SDK. Server proto musí schopnosti vyjednat a nabídnout rozumné chování i bez nepovinného rozšíření.

### 6. Tvrdší autorizace a řízené zastarávání

Nová revize vyžaduje validaci `iss` podle RFC 9207, váže klientské přihlašovací údaje k issuerovi a posouvá registraci klientů od Dynamic Client Registration (DCR) ke Client ID Metadata Documents (CIMD). DCR zůstává kvůli kompatibilitě, ale je deprecováno.

Deprecated jsou také Roots, Sampling, Logging a starší transport HTTP+SSE. Budou fungovat nejméně 12 měsíců; nový vývoj je však nemá přidávat. Tato přechodová lhůta je součástí nově zavedené deprekační politiky.

## Jak se to ujímá a nasazuje

### Kde má MCP největší smysl

MCP se dobře uplatní tam, kde agent nebo AI asistent musí pracovat s několika existujícími systémy:

- vývoj: repozitáře, issue tracker, CI/CD, dokumentace, lokální soubory;
- zákaznická a provozní práce: CRM, helpdesk, objednávky, sklad;
- analytika: řízený přístup k databázi, datovému katalogu a reportům;
- interní knowledge workflow: vyhledávání v dokumentech a následné akce pod dohledem člověka.

V prvním kroku bývá nejrozumnější **read-only server** s malým počtem úzce vymezených nástrojů. Teprve po ověření auditních stop, oprávnění a chování modelu je vhodné přidat zápisové operace.

### Doporučený postup zavedení

1. **Vyberte jeden konkrétní workflow.** Například „najdi stav objednávky a navrhni odpověď“, ne obecný přístup ke všemu CRM.
2. **Návrh nástrojů zjednodušte.** Každý tool a jeho parametry popište přesně, schématem validujte vstupy a oddělte čtení od změn.
3. **Zaveďte identitu a minimální oprávnění.** Přístup musí být svázán s uživatelem nebo pracovní zátěží; server nesmí spoléhat jen na text v promptu.
4. **Přidejte potvrzení pro důsledkové akce.** Mazání, platby, odeslání e-mailu či publikace mají vyžadovat zřetelné schválení mimo model.
5. **Nasazujte stateless přes HTTPS.** Použijte Streamable HTTP, TLS, standardní gateway/WAF a horizontální škálování. Aplikační stav ukládejte explicitně do databáze nebo vracejte jako handle.
6. **Měřte a auditujte.** Logujte identitu, volaný nástroj, parametry v bezpečně redigované podobě, rozhodnutí politik a výsledek.
7. **Otestujte neideální cesty.** Zamítnutá oprávnění, timeouty, duplicity, retry, vypršení tasků, prompt injection v datech a rollback zápisů.

### Referenční architektura

```text
Uživatel
   │ schválení citlivých kroků
   ▼
Host / AI agent ── MCP client ── HTTPS ── API gateway / WAF
                                            │
                                ┌───────────┴───────────┐
                                ▼                       ▼
                       MCP server (stateless)   MCP server (stateless)
                                │                       │
                          business API / DB      dokumenty / vyhledávání
                                │
                       identity, policy, audit
```

Gateway rozhoduje o síťových a transportních pravidlech; MCP server vynucuje doménová oprávnění a validuje každý požadavek; zdrojový systém zůstává konečnou autoritou pro citlivá data a změny. Model nesmí být jediným místem, které rozhodne o přístupu.

### Migrace ze staršího MCP

Pro existující server je praktická strategie dvojkolejná:

1. Aktualizovat Tier 1 SDK a ověřit podporu `2026-07-28` na testovacím prostředí.
2. Odstranit závislost na `Mcp-Session-Id`, sticky sessions a skrytém transportním stavu.
3. Přesunout nutný stav do explicitních argumentů/handles nebo do trvalého datového úložiště.
4. Přidat hlavičky pro routing a pravidla gateway; ověřit cache katalogů.
5. Nahradit staré serverem iniciované toky MRTR a dát uživateli jasné UI pro potvrzení.
6. Zachovat kompatibilní cestu pro starší klienty po dobu přechodu, ale nové funkce navrhovat pro stateless variantu.

SDK 2.0 nemusí automaticky znamenat okamžitý nekompatibilní přepis. Například oficiální C# SDK 2.0 uvádí zachování běhu existujícího kódu; přesto je nutné otestovat konkrétní kombinaci hosta, klienta, serveru a SDK.

## Bezpečnost: co MCP samo nevyřeší

MCP zjednodušuje propojení a jeho nová revize zlepšuje některé autorizace, ale nechrání automaticky před všemi riziky agentního systému. Zvláštní pozornost patří:

- **prompt injection v externích datech** – dokument či ticket může obsahovat instrukce určené modelu;
- **příliš širokým nástrojům** – jeden „admin tool“ je hůře kontrolovatelný než několik úzkých operací;
- **záměně identity** – credentials, token audience a issuer musí být kontrolovány serverem;
- **nečekané kombinaci oprávnění** – bezpečné nástroje samostatně mohou dohromady umožnit únik dat;
- **supply-chain rizikům** – server, SDK i závislosti aktualizujte, podepisujte/verifikujte a nasazujte s minimálními právy.

Pravidlo pro produkci: nástroje musí provádět vlastní autorizaci podle identity a účelu operace; na „model to určitě neudělá“ nelze spoléhat.

## Výhledy použití

Následující body jsou směr vývoje, ne garance termínu ani součást hotové specifikace.

### Krátkodobě: MCP jako produkční konektor pro agenty

Stateless HTTP, routování podle hlaviček, cache a Tasks posouvají MCP z lokálních experimentů k běžnému provozu ve více instancích. Pravděpodobné je rozšíření v interních AI asistentech, kde podnik nechce vytvářet proprietární integraci pro každý model a každý nástroj.

### Střednědobě: lepší objevování a podniková správa

Roadmapa uvádí MCP Server Cards – strukturovaná metadata zveřejněná na `.well-known` URL pro vyhledání schopností serveru bez připojení. Další prioritou je jemnější least-privilege autorizace, DPoP, Workload Identity Federation, konformní testy a rozvoj registru rozšíření. To může výrazně zlepšit provoz ve větších organizacích, kde jsou objevování, evidence a audit stejně důležité jako samotné volání nástroje.

### Dlouhodobě: interoperabilní ekosystém, ne všemocný agent

MCP má šanci zůstat společnou vrstvou pro agent–nástroj a agent–data komunikaci. Pro agent–agent spolupráci ale bude nutné sladit MCP s dalšími vzory/protokoly a dopracovat životní cyklus Tasks (retry, expirace, odpovědnost za opakování). Nejspíš nevznikne jeden univerzální „agentní internet“ přes noc; reálnější je ekosystém specializovaných protokolů, kde MCP obstarává přístup ke schopnostem a kontextu.

## Doporučení pro rozhodnutí dnes

MCP `2026-07-28` je vhodné brát vážně pro nové vzdálené integrace, zejména pokud očekáváte více instancí, cloudové nasazení nebo více klientů. Začněte malým, read-only a dobře auditovaným serverem; pro zápisové akce přidejte explicitní workflow schvalování.

Pro stávající projekty není nutné vše přepsat ihned. Vyplatí se ale už nyní navrhovat nástroje bez závislosti na transportní session, sledovat připravovaná rozšíření a mít testovací matici klient × server × SDK. Tím bude přechod ze staršího MCP na aktuální revizi podstatně méně rizikový.

## Zdroje

- [MCP: specifikace `2026-07-28` – oznámení a změny](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
- [Oficiální roadmapa MCP pro rok 2026](https://modelcontextprotocol.io/development/roadmap)
- [Přehled serverových primitives MCP](https://modelcontextprotocol.io/specification/2025-11-25/server/index)
- [Oznámení MCP C# SDK 2.0 a praktické migrační souvislosti](https://devblogs.microsoft.com/dotnet/announcing-v20-of-the-official-mcp-csharp-sdk/)
- [RFC 9207: Authorization Server Issuer Identification](https://www.rfc-editor.org/rfc/rfc9207)
