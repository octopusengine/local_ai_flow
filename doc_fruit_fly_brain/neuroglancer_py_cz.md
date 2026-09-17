# Neuroglancer v Pythonu — české shrnutí

Zdroj: [oficiální README](https://github.com/google/neuroglancer/blob/master/python/README.md).
Jde o shrnutí, nikoli úplný překlad.

## Účel a možnosti

Neuroglancer je webový prohlížeč trojrozměrných objemových dat. Pythonové rozhraní umožňuje:

- zobrazovat NumPy pole a obdobné datové struktury, například HDF5 přes `h5py`;
- číst a měnit stav prohlížeče;
- upravovat ovládání klávesnicí a myší;
- spouštět Pythonové funkce uživatelskými akcemi.

Lokální server poskytuje webového klienta, synchronizaci stavu a lokální data.

## Instalace

Doporučuje se virtuální prostředí:

```powershell
pip install neuroglancer
```

Předkompilovaný balíček obvykle nevyžaduje Node.js ani C++ kompilátor.
Instalace ze zdrojového balíčku potřebuje C++ kompilátor; webový klient je přibalený.
Instalace přímo z GitHubu vyžaduje také Node.js:

```powershell
pip install git+https://github.com/google/neuroglancer
```

Z lokálního klonu použij `pip install .`. Pro vývoj slouží `uv sync`;
změny webového klienta vyžadují sestavení pomocí `npm run build-python`.

## Spouštění příkladů

Příklady jsou v adresáři `python/examples`. Spouštějí se interaktivně:

```powershell
uv run python -i example.py
```

Bez interaktivního režimu může skript okamžitě skončit a zastavit server.

## Segmentace, zabezpečení a testy

Ze segmentačních objemů v paměti lze na vyžádání vytvářet povrchové 3D modely objektů.

Server standardně naslouchá pouze na `127.0.0.1`; požadavky chrání náhodný 160bitový tajný klíč.

Testy používají `nox`; prohlížečové testy potřebují WebGL2. Testy bez prohlížeče:

```powershell
uvx nox -s test -- --skip-browser-tests
```

README popisuje omezení bezobslužného testování a linuxovou variantu s `xvfb-run`.
