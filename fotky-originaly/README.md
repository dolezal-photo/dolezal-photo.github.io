# Kam nahrávat fotografie

Do podsložek v tomto adresáři ukládej původní fotografie podle tématu:

- `kdo-jsem/` — právě jeden portrét použitý na stránce „Kdo jsem“
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
- uloží hotové kopie do odpovídajících galerií ve složce `content/`,
- portrét ze složky `kdo-jsem/` vždy uloží jako `content/kdo-jsem/kdo-jsem.jpg`.

Při změně nastavení lze vynutit nový export ze zachovaných originálů:

```sh
python3 scripts/priprav_fotky.py --force
```

Podporované vstupy jsou JPEG, PNG a TIFF. Soubory RAW nebo HEIC nejprve exportuj ve fotografickém editoru jako JPEG v barevném prostoru sRGB.

Chceš-li určit titulní obrázek galerie, pojmenuj jej například `00-titulni.jpg`, aby byl v abecedním pořadí první.

Ve složce `kdo-jsem/` ponechávej pouze jeden obrázek. Jeho původní název není důležitý; webová kopie dostane vždy stálý název `kdo-jsem.jpg`, takže při výměně portrétu není nutné upravovat šablonu.

