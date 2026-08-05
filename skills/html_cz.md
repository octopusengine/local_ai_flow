---
name: html_cz.md / skill-html-prezentace
description: Vytvoří moderní jednosouborovou HTML prezentaci na zadané téma — scrollovací stránka plná karet, čísel a animací (nebo klasické slidy na mezerník), s přepínačem tmavého režimu. Aktivuj na "udělej prezentaci", "html prezentace", "prezentace o", "slidy na téma".
---

# Skill Prezentace

Vytvoř KOMPLETNÍ prezentaci v HTML + CSS + JS,
žádné knihovny, žádné CDN - na téma z hlavního zadání.
Na výssẗupu pouze html - začínáme  <!DOCTYPE html> ... a tak dále.

## Výchozí podoba: scrollovací stránka

1. **5–7 sekcí** pod sebou, stránka se scrolluje shora dolů. (Když si uživatel
   řekne o „slidy" / „na mezerník", udělej místo toho celoobrazovkové slidy
   s ovládáním šipkami + mezerníkem.)
2. **Hero nahoře:** velký titulek, podtitulek jednou větou, výzva „scrolluj ↓".
3. **Namíchej typy sekcí** (každá jiná): úvod ve 2–3 odstavcích · mřížka 4 karet ·
   číslované kroky nebo časová osa · velká čísla/statistiky (4 dlaždice) ·
   srovnávací tabulka (min. 4 řádky) · výrazný citát na kontrastním pruhu ·
   štítky / rychlé tipy · závěr se shrnutím a výzvou.
4. **Obsah je král:** VŠECHNY sekce naplň konkrétními fakty, čísly a příklady
   k tématu — žádné výplňové fráze, žádné „lorem ipsum". Prezentace musí být
   zajímavá ke čtení sama o sobě, i bez řečníka.
5. **Animace:** prvky se objevují při scrollování (IntersectionObserver + CSS
   transition, jemný posun nahoru). Nahoře tenký progress bar podle scrollu.
6. **Tmavý režim:** tlačítko vpravo nahoře přepíná světlý/tmavý vzhled (obojí
   kontrastní a čitelné), volba se pamatuje v localStorage.
7. **Klávesa `F`** přepne fullscreen.

## Design

- Všechny barvy jako CSS proměnné v `:root` (pozadí, text, akcent…) — ať se dají
  měnit na jednom místě. Vyber JEDNU akcentovou barvu podle tématu.
- Velké čitelné písmo z Google Fonts (jediná povolená externí věc): výrazný font
  na nadpisy + jednoduchý na text. Základní velikost textu ať je pohodlně čitelná.
- Zaoblené karty s jemným okrajem, hodně vzduchu, max 3 odrážky na blok.
- Česky s diakritikou. Profesionální a moderní — ne šablona z PowerPointu.

## Po vygenerování VŽDY zkontroluj

- nic nepřetéká do stran (žádný vodorovný scrollbar),
- tmavý i světlý režim jsou čitelné (žádný tmavý text na tmavém pozadí),
- progress bar dojede na konci stránky na 100 %,
- řekni uživateli, jak si soubor otevřít (dvojklik — otevře se v prohlížeči).

Na závěr jednou větou připomeň: o změnu barev, textů nebo počtu sekcí stačí
požádat další zprávou — iterace je normální součást postupu.

---

hlavní zadání:
