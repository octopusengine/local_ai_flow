# Vizuální kontrola Pygame v Cowork / code

Profil `code` (schéma `extended`, také `hw_extended`) má dva nové nástroje:

```text
run_pygame({"path":"platformer.py","frame":60,"timeout_seconds":30})
inspect_image({"path":"pygame.png","question":"Popiš rozmístění hráče, platforem a předmětů. Jsou vidět překryvy nebo oříznuté objekty?"})
```

`run_pygame` používá projektové `.venv` nebo `venv`, jinak Python Jamesu.
Spustí existující hru přes pomocný skript bez změn zdrojáku, s neviditelným
SDL displejem a vypnutým zvukovým výstupem. Po požadovaném počtu volání
`pygame.display.flip()` nebo `pygame.display.update()` uloží displej a
ukončí běh. Výchozí limit je 30 sekund, nejvýše 120 sekund. `frame` může
být 1–3600; volitelné `args` předá argumenty hry. Nic se neinstaluje.

Úspěšný výsledek přepíše `pygame.png` v kořeni aktivního projektu a přidá ho
mezi artefakty. Chyba, timeout nebo konec hry před zachycením ponechá předchozí
obrázek a výslovně oznámí, že nový nevznikl. Nástroj respektuje pravidla
potvrzování běhu; politika `observe` ho nepovoluje.

`inspect_image` přijímá projektový PNG/JPEG do 8 MiB. Obraz předá samostatnému
vision dotazu na stejný Ollama server. Hlavní agent dostane pouze textový
popis se jménem použitého modelu; obrazová data se nepřidávají do jeho historie
ani záznamu nástrojů. Model hlavní relace a jeho nastavení se nemění.

Výběr vision modelu: pokud je před spuštěním Jamesu nastavena proměnná
`JAMES_VISION_MODEL`, použije se tento model. Jinak má přednost `vision_model`
z kořenového `cli_agent.json` (nyní `"qwen3.5:latest"`), načtený při novém zadání.
Explicitní volba nepřechází automaticky na jiný model při chybě nebo chybějící
podpoře vision. Pokud klíč chybí nebo je `null`, prověří se hlavní model
a poté ostatní modely nainstalované na serveru. První model, jehož `/api/show`
hlásí schopnost `vision`, se použije a zapamatuje pro daný engine. Pokud
žádný nevyhovuje, agent dostane informaci, že obrázek nebyl prohlédnut.
Žádný model se automaticky nestahuje. Explicitní volba například v PowerShellu:

```powershell
$env:JAMES_VISION_MODEL = "nazev-vaseho-nainstalovaneho-vision-modelu"
python james.py
```

Zadání vision inspekce je v `agent/vision_inspection.txt` a načítá se při každé
inspekci. Vyžaduje podrobný popis celého snímku: oken, panelů, ovládacích prvků,
čitelných textů, objektů, poloh a viditelných problémů. Platí i pro obecnou otázku
„describe the image“. Samostatný vision dotaz má limit výstupu 4096 tokenů;
vyčerpání limitu nebo zkrácení popisu se hlásí v reportu. Tento prompt se
nepřidává do hlavního systémového promptu; vrácený podrobný popis ale zabírá
místo v historii kódovacího agenta.

Jde o snímek softwarového displeje, nikoli test hratelnosti. Nástroj
nesimuluje klávesnici, nepodporuje OpenGL a menu čekající na stisk klávesy
se samo nepřeskočí. Počet aktualizací displeje nemusí být shodný s počtem
herních kroků. Doskoky, pohyb a kolize vyžadují další běhový test.

Po aktualizaci restartujte James. Příklad zadání: „Spusť vizuální kontrolu
platformer.py, ulož pygame.png a popiš, co je na snímku vidět.“

Rozhraní: [Ollama vision](https://docs.ollama.com/capabilities/vision),
[Pygame display](https://www.pygame.org/docs/ref/display.html).
