Musíme propojit herní smysly se vstupy konektomu a jeho aktivitu převést na pohyb. Samotný konektom nemá příkazy „jdi doleva“ ani informaci, co znamená oranžové políčko.



Vznikla by smyčka:

svět → smyslové vstupy → simulace konektomu → řízení pohybu → změněný svět



Nejdůležitější je rozhodnout, co bude biologický model a co naše zjednodušení.



1\. Jak moucha zjistí cukr

Dnešní agent dostává přímo směr k nejbližšímu cukru. Pro propojení bych navrhl dva umělé senzory — levý a pravý:

\- Cukr vytváří ve světě pole intenzity, které se vzdáleností slábne.

\- Moucha změří intenzitu na levé a pravé straně.

\- Naměřené hodnoty převedeme na frekvence stimulace vybraných neuronů.

Tohle by byl umělý smyslový model. Naše současné „cukrové“ vstupy bych používal hlavně jako informaci o kontaktu s potravou; jejich stimulaci podle vzdálenosti bychom neměli vydávat za ověřený biologický čich.



2\. Jak aktivita mozku způsobí pohyb

Potřebujeme výstupní rozhraní, které například ze tří skupin neuronů odvodí:

Aktivita	Akce ve světě

Skupina L	Natočit doleva

Skupina P	Natočit doprava

Skupina V	Posunout se vpřed





Konkrétní skupiny bychom museli vybrat podle anotací a podkladů k jejich funkci. MN9, který teď sledujeme, nemáme ověřený jako vhodný výstup pro navigaci.

Moucha by tedy nově měla i orientaci. Je to přirozenější propojení než přímé povely sever/jih/východ/západ.



3\. Kde by probíhalo učení

Tady jsou dvě různé možnosti:

A. Konektom zůstane pevný, učí se převod jeho aktivity na pohyb.

Malý učící se řadič dostává aktivitu vybraných neuronů a vybírá akce podle odměny za cukr. To je pro nás nejpraktičtější první experiment. Učí se ale připojený řadič, nikoli synapse mozku.

B. Učí se přímo spoje konektomu.

Přidali bychom pravidlo změn vah, například závislé na aktivitě a odměně. To je podstatně náročnější: samotná mapa spojů nám neříká, které váhy a jak měnit. Výsledek by obsahoval další výrazné modelové předpoklady.

Co bych navrhl jako první

Začít pevným konektomem a jednoduchým výstupním řadičem, nejprve dokonce bez učení. Ověřit, že změna senzorického vstupu mění aktivitu a následně pohyb. Potom přidat učení výstupního řadiče.

Zásadní by bylo porovnání:

\- řadič se skutečným konektomem,

\- stejný řadič s promíchanými spoji,

\- řadič dostávající přímo senzory, bez konektomu.





Pokud by všechny varianty fungovaly stejně, neměli bychom důkaz, že zapojení konektomu přináší něco užitečného.

Ještě potřebujeme upravit simulátor: dnes každý pokus začíná z klidu. Pro pohyb ve světě musí stav mozku přetrvávat mezi kroky. Rychlost propojené simulace bychom teprve změřili.

