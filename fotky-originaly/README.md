# Jediné místo pro fotografie a obsah webu

V této složce jsou původní fotografie a soubor `nastaveni.json`. Právě tento JSON je jediný soubor, ve kterém se ručně řídí obsah webu.

Neupravuj komprimované obrázky ve složkách `content/` ani `assets/images/`. Jsou to automatické webové kopie a přípravný nástroj je může kdykoli nahradit.

## Jak je JSON uspořádaný

- `media` — katalog úplně všech obrazových souborů ve `fotky-originaly`
- `spolecne` — název webu, logo, menu, Instagram, patička a společná kontaktní výzva
- `uvod` — všechny texty a fotografie úvodní stránky
- `portfolio` — úvod portfolia, pořadí kategorií, texty kategorií, titulní fotografie, galerie a svatební video
- `kdo_jsem` — všechny texty a vybraný portrét stránky „Kdo jsem“
- `kontakt` — všechny texty stránky Kontakt

Každá fotografie má v `media` stabilní ID, například:

```json
"atelier-p1140078": {
  "typ": "fotografie",
  "soubor": "atelier/P1140078.jpg",
  "alt": "Portrét ženy v černém roláku opřené o židli",
  "stav": "aktivni"
}
```

Ostatní části JSON používají už jen toto ID. Popis `alt` slouží lidem se čtečkou obrazovky a také vyhledávačům.

## Nejčastější změny

### Fotografie nahoře na úvodní stránce

Uprav hodnotu:

```text
uvod → hero → fotografie
```

Je v ní výslovně uvedené ID `atelier-p1140078`. Úvodní snímek už se nevybírá skrytě jako první fotografie galerie.

### Portrét na stránce „Kdo jsem“

Uprav hodnotu:

```text
kdo_jsem → fotografie
```

Stejné nebo jiné ID lze nastavit také pro upoutávku na úvodu v `uvod → o_mne → fotografie`.

### Pořadí kategorií portfolia

Přesuň celé objekty v poli:

```text
portfolio → kategorie
```

### Titulní snímek kategorie

V dané kategorii změň `titulni_fotografie`. Použité ID musí zároveň zůstat v jejím poli `fotografie`.

### Pořadí snímků v galerii

Přesuň ID v poli `fotografie` dané kategorie. Názvy webových kopií jsou stabilní, takže pouhá změna pořadí už fotografie znovu nekomprimuje.

### Texty

Texty uprav přímo v odpovídající sekci `spolecne`, `uvod`, `portfolio`, `kdo_jsem` nebo `kontakt`. Po změně samotného textu není nutné spouštět přípravu obrázků; běžící Hugo náhled změnu automaticky načte.

## Přidání nové fotografie

1. Vlož originál do správné podsložky: `atelier`, `koncerty`, `svatebni-video`, `interiery`, `shora`, `catering` nebo `kdo-jsem`.
2. Přidej mu jedinečné ID do katalogu `media`.
3. Chceš-li ho zobrazit, vlož jeho ID do příslušné stránky nebo galerie a ponech `"stav": "aktivni"`.
4. Spusť kontrolu a přípravu:

```sh
python3 scripts/priprav_fotky.py --check
python3 scripts/priprav_fotky.py
```

Kontrola záměrně ohlásí chybu, pokud ve složce leží obrázek, který v katalogu `media` chybí. JSON tak nemůže být nepozorovaně neúplný.

## Rezervní fotografie

Obrázek s hodnotou `"stav": "rezerva"` je v JSON evidovaný, ale nástroj pro něj nevytváří webovou kopii. Chceš-li ho použít, změň stav na `aktivni` a vlož jeho ID do požadované sekce.

Aktuálně jsou jako rezerva vedené:

- `kdo-jsem-alternativa`
- `atelier-p1180272-rezerva`

## Co dělá příprava fotografií

Nástroj:

- nejprve zkontroluje úplnost JSON a existenci všech souborů,
- zpracuje pouze nové nebo změněné originály,
- opraví orientaci podle EXIF,
- převede vložený barevný profil do sRGB,
- zmenší delší stranu maximálně na 2400 px,
- uloží progresivní JPEG v kvalitě 82 bez EXIF a GPS,
- pro logo zachová PNG a odstraní prázdné okraje,
- bezpečně odstraní jen staré automaticky spravované kopie.

Samotnou kontrolu bez zápisu spustíš:

```sh
python3 scripts/priprav_fotky.py --check
```

Náhled plánovaných změn bez zápisu:

```sh
python3 scripts/priprav_fotky.py --dry-run
```

Podporované vstupy jsou JPEG, PNG a TIFF. RAW nebo HEIC nejprve exportuj ve fotografickém editoru jako JPEG v barevném prostoru sRGB.
