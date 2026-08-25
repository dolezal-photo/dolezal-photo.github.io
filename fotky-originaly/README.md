# Kam nahrávat fotografie

Do podsložek v tomto adresáři ukládej původní fotografie podle tématu:

- `kdo-jsem/` — kandidáti na portrét použitý na stránce „Kdo jsem“
- `atelier/`
- `koncerty/`
- `shora/`
- `catering/`
- `svatebni-video/`
- `interiery/`

Originály se na web přímo neposílají a Git je ignoruje. Zůstávají v plné kvalitě jako bezpečný zdroj pro případnou novou exportní verzi.

## Příprava fotografií pro web

V kořenové složce projektu spusť:

```sh
python3 scripts/priprav_fotky.py
```

Nástroj:

- zpracuje pouze nové nebo změněné originály,
- opraví orientaci podle EXIF,
- zmenší delší stranu maximálně na 2400 px,
- uloží progresivní JPEG v kvalitě 82,
- nepřenáší EXIF ani GPS údaje,
- uloží hotové kopie do odpovídajících galerií ve složce `content/portfolio/`,
- portrét ze složky `kdo-jsem/` vždy uloží jako `content/kdo-jsem/kdo-jsem.jpg`.

## Výběr obrázků a pořadí

Ručně upravuj pouze soubor `nastaveni.json` v této složce. Technický soubor `.komprese.json` je automatická cache a není určený k úpravám.

Hodnota `kdo_jsem` obsahuje přesný název vybraného portrétu ze složky `kdo-jsem/`:

```json
"kdo_jsem": "foto11_atelier_profil22 copy.jpg"
```

V části `portfolio` zapisuj názvy fotografií v požadovaném pořadí. První fotografie bude zároveň titulní fotografií kategorie:

```json
"atelier": [
  "hlavni-portret.jpg",
  "portret-02.jpg",
  "portret-03.jpg"
]
```

Fotografie, které v seznamu neuvedeš, se automaticky přidají za nastavené pořadí podle názvu souboru.

Při změně nastavení lze vynutit nový export ze zachovaných originálů:

```sh
python3 scripts/priprav_fotky.py --force
```

Podporované vstupy jsou JPEG, PNG a TIFF. Soubory RAW nebo HEIC nejprve exportuj ve fotografickém editoru jako JPEG v barevném prostoru sRGB.

Ve složce `kdo-jsem/` můžeš ponechat více kandidátů. Aktivní portrét určuje `kdo_jsem` v `nastaveni.json`. Webová kopie dostane vždy stálý název `kdo-jsem.jpg`, takže šablonu není nutné upravovat.
