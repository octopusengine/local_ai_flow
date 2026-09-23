# Sonic Pi 5 — novinky a doporučení

## Zásadní novinky ve verzi 5.0.0

- **SuperSonic** nahrazuje scsynth; zvukové zařízení, vzorkovací frekvenci a velikost bufferu lze měnit za běhu.
- **Mix a hlasitost:** nový limiter; `set_volume!` má rozsah 0–1. Vybuzení před limiterem řídí `set_drive!` (0.5 = jednotkový zisk).
- **Externí synchronizace:** `use_bpm :midi` sleduje příchozí MIDI hodiny; `link_audio` přijímá živé audio od dalších Ableton Link účastníků.
- **Hudební funkce:** `ring.invert_around` zrcadlí melodii kolem zvoleného tónu; přibyly např. stupnice `:lydian_dominant` a akordy `:minor_major7` a `:maj13`.
- **Výraz a samply:** `play_pattern_timed` podporuje seznamy parametrů pro jednotlivé noty, např. `amp:`; `sample` respektuje `duration:`.
- **Práce v aplikaci:** interaktivní dokumentace, lepší doplňování kódu, náhledy samplů a Sets pro uložení všech deseti bufferů do souboru `.sonicpi`.

Zdroj: [oficiální vydání Sonic Pi 5.0.0](https://github.com/sonic-pi-net/sonic-pi/releases/tag/v5.0.0).

## Zápis tónů

Tóny zapisuj jako Ruby symboly s oktávou, např. `:C4`, `:Es5`. Přípona `s` znamená zvýšení a `b` snížení: `:Es5` je E♯5 (česky Eis5), české Es5 je `:Eb5`. Symbol se v kódu nepíše do uvozovek.

Zdroj: [Sonic Pi — zápis tónů](https://sonic-pi.net/tutorial.html#section-2-1).

## Pět doporučení pro agenta

1. Cíluj na Sonic Pi 5; používej `set_volume!` v rozsahu 0–1 a vybuzení řeš přes `set_drive!`.
2. Stav skladbu z frází po 4–8 taktech, s úvodem, variacemi a zakončením.
3. Melodii a basu odvozuj ze společné tóniny a akordů; rozvíjej krátký motiv místo nezávislých náhodných tónů.
4. Synchronizuj party pomocí `live_loop` a `cue`/`sync`; každé opakování musí posunout hudební čas pomocí `sleep` nebo čekat na synchronizační událost.
5. Tvoř groove pomocí pauz, akcentů a jemného swingu; obálky a hlasitosti nastavuj tak, aby se party nepřekrývaly zbytečně.
