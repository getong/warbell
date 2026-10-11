# Zamek v2: architektura, która opowiada fabułę

> Po polsku dla autora; wszystko w grze po angielsku. Nadpisuje §2, §3 i §5 dokumentu
> `2026-10-11-centrum-mapy-design.md` (podłoże i rynek z faz 1–2 zostają). Źródło fabuły:
> `2026-10-10-kampania-fabula-design.md` (v2). **Kolonia nie ma kościoła.**

Zamek mówi bez słów: na starcie **obóz rozbitków w ruinach starego fortu**, pod koniec
**twierdza, w której coraz więcej barw Korony**.

## 1. Skala (przeliczona na bohatera, nie na metry)

Bohater ma w grze **1.49 u** (rig 2.35 × `HERO_SCALE 0.6345`, potwierdzone screenem), czyli
**1 u ≈ 1.3 m**. Dzisiejszy mur (1.35 u ≈ 2 m) jest tylko trochę wyższy od bohatera, keep (~1.5 u
× skala) jak szopa. Cele:

| Element | Dziś | Cel (u) | ≈ m |
|---|---|---|---|
| Palisada (na wale) | — | 2.2–2.6 + wał 0.4, rów ~0.6 głęb. | 3.5–4 |
| Kamienny mur | 1.35 | 3.6–4.0 do blanek, chodnik ~3.0, grubość 1.2–1.5 | 5.5–6 |
| Wieże | 2.5 | 5.5–6.5 | 8–10 |
| Keep (donżon, tier 2) | ~1.5 | 8–10 | 12–15 |
| Brama (przejazd) | 2.0 | 2.6–2.8 wys. × 2.6–3.0 szer. (wóz przejedzie) | 4 × 4 |
| Wieża dzwonu (stara kolonia) | rama z belek | ~8, otwarta dzwonnica | 12 |
| Domy | okap ~1.3 | okap ~2.0, kalenica ~3.5, drzwi ~1.4 | — |

**Warunek:** wysokie mury zasłonią kamerę zza pleców → kamera musi się przybliżać przy
przeszkodzie (spring-arm jak w Wiedźminie / KCD2), inaczej nie podnosimy murów.

## 2. Przestrzeń: zamek w murach, miasteczko pod murami (v3, uwaga autora 2026-10-11)

> Autor: „domki są mega nierealistycznie poustawiane”, „część budynków może być poza murami”,
> „zamek ma być modelowany w Blenderze, realistyczny, a nie przeskalowane byle co”.
> Prymitywy z `castle.rs` były tylko szkicem układu. Docelowo **każda bryła to model z kitu**.

**Zasada (jak w prawdziwych zamkach i w KCD2):** w murach stoi tylko to, co należy do zamku;
miasteczko (**podgrodzie**) rośnie **za bramą, wzdłuż drogi**. Rząd identycznych domków plecami
do muru wygląda jak gra, nie jak miejsce.

**Obrys murów: nieregularny wielokąt, nie prostokąt** (autor: „fort nie musi być kwadratowy”). Stały,
ręcznie zaprojektowany (ten sam w każdym seedzie): 7–9 narożników, boki 10–30 u, kąty wypukłe
105–170°, wieża w każdym narożniku (okrągła lub D-kształtna ukrywa każdy kąt), keep od północy
(może stać w linii kurtyny jak bergfried), brama S z wieżą dzwonu na południu, brama W, furta N.
Powierzchnia jak dotąd (mieści się w ok. x −31…31, z −26…24).

**W murach (podzamcze):**
- keep, wieża dzwonu przy bramie S, **otwarty dziedziniec ≥ 24×16** z ogniskiem i studnią;
- zabudowa gospodarcza **przyklejona do kurtyny** (przybudówki pod murem, dachy pulpitowe):
  koszary, stajnia, kuźnia zamkowa (Armoury), spichlerz (płonie w Rozdz. 8 — musi być w środku),
  izba chorych z ogrodem ziół (cicha strona wschodnia), składy, drewutnia, wozownia;
- żadnych domów mieszkalnych w rzędach.

**Za bramą W, wzdłuż King's Road (podgrodzie):**
- **plac targowy przy bramie** (stragany z fazy 2 przenoszą się tutaj), studnia, **karczma „The
  Drowned Squire”** przy placu, **dom Maud z tablicą edyktów** przy placu;
- domy na **działkach siedliskowych**: wąski front szczytem do drogi, za domem podwórko, ogród,
  szopa, płot z wikliny/sztachet, kurnik, stos drewna; **nieregularnie** — linia zabudowy idzie za
  łukiem drogi, różne odstępy, lekkie skręty, różne warianty domów, uliczka w bok;
- cieśla przy drodze (kozły, wióry), stodoły i pola dalej od murów;
- **skład Korony** przy rozwidleniu na zatokę, **szubienica na wzniesieniu przy drodze poza
  zabudową** (tak je stawiano), **pusty grób** przy trakcie dalej na zachód.
- Teren: płaska strefa dostaje **płat wzdłuż drogi W** (lub drogi, gdzie jest miejsce — NW to
  urwiska mesy), z wyciętym lasem; nadal ≥ 15 u wolnego pierścienia wokół reszty murów.

**Fabuła i mechanika:** podgrodzie jest **bez osłony** — o zmierzchu ludzie schodzą za mury, brama
się zamyka (§5). Tor **Podgrodzie** (§6) dokłada mu z czasem **palisadę z własną bramą**. Orki na
razie nie palą domów podgrodzia (później: podpalenia jako stawka nocy).

```
                              N furta
        [koszary][stajnia]  ┌────────┐  [spichlerz][skład]
        [kuźnia zamkowa]    │  KEEP  │       [izba chorych + zioła]
  ══ W brama                └────────┘                               ściana E pełna
  ║        ognisko · studnia   DZIEDZINIEC (otwarty)
  ║                     [WIEŻA DZWONU]══ S brama (orki)
  ╚═ PLAC TARGOWY (stragany, studnia, karczma, dom Maud + edykty)
       ╲ King's Road: domy szczytem do drogi, ogrody, płoty, szopy (nieregularnie)
         ╲ skład Korony przy rozwidleniu · szubienica na wzgórku · pusty grób dalej
```

## 3. Trzy warstwy, czytane bez słów

1. **Stary kamień pierwszej kolonii:** szary, omszały, zrujnowany. Nietknięta stoi tylko **wieża
   dzwonu** (orki nie ruszają „żelaznego głosu”) — ciche ziarno zwrotu.
2. **Nasze świeże drewno:** bale, strzechy, bielone domy szachulcowe, błoto, słoma.
3. **Barwy Korony** od Rozdz. 7: karmazynowe chorągwie, malowane skrzynie, namioty żołnierzy,
   szubienica. Każdy akt dokłada ich więcej.

## 4. Elementy obowiązkowe

| Element | Po co |
|---|---|
| **Keep** | War Table, kwatera Wata, budzi się tu po „Ser Godric padł”, kwatera Maud w Akcie IV. **Keep zostaje nasz** (Crane w Akcie IV wycofuje się do zatoki). |
| **Wieża dzwonu** | Kamienna, stara kolonia, stoi od początku. Platforma Pipa, sznur, wyjęte serce dzwonu, finał. Przy bramie S (brama „pod wieżą dzwonu”). |
| **Spichlerz** | Budynek, bo w Rozdz. 8 płonie pod fałszywą flagą. Zapas jedzenia. |
| **Ognisko na dziedzińcu** | Rozmowy po każdym świcie. |
| **Dom Maud** | Tablica edyktów, podatki, scenki. |
| **Pusty grób „utopionego giermka Wata”** | Przy trakcie za bramą W (droga z zatoki). Ziarno zwrotu tożsamości, rekwizyt epilogu. |
| **Studnia** | Oblężenie, rynek, scenki. |
| **Kuźnia** | Fizyczna gałąź Armoury: tiery broni; w epilogu lemiesz z brązu dzwonu. |
| **Karczma „The Drowned Squire”** | Centrum barków. Żart Maud, po zwrocie mroczny. (Nie „The Cracked Bell” — w v2 dzwon nie pęka.) Szyld: hełm giermka nad falami. |
| **Izba chorych + ogród ziół** | Zamiast kapliczki leczącej (`shrine`). |
| **Skład Korony + szubienica** | Od Rozdz. 7, **za bramą zachodnią** (droga do zatoki). „Korona wiesza za mniej”. |

## 5. Bramy: trzy zamiast czterech

- **Zachodnia (główna):** King's Road do zatoki → z czasem krata.
- **Południowa (atakowana):** pod wieżą dzwonu → z czasem barbakan.
- **Północna furta:** las i kamieniołom.
- **Wschód: pełny mur.** Drogi, które dziś wchodzą od wschodu, obchodzą mur do N lub S.

Mechanika (faza 3, po układzie): bramy **zamykają się o zmierzchu na dzwon Pipa**; brama ma HP,
orki ją rąbią, w Rozdz. 9 tarany; zamknięta brama blokuje nawigację orków i staje się celem.
Bohater i nasi przechodzą (straż otwiera).

## 6. Pięć torów rozwoju (faza 3+; dziś mapowane na `economy::Defenses`)

| Tor | Etapy | Dzisiejsza flaga |
|---|---|---|
| **Mury** | wozy w krąg + ruiny → palisada na wale z rowem → kamienna kurtyna z kamienia ruin → fosa i zwodzony most („I said dig a moat”) | `!walls` → `walls` → `reinforced` → (nowa) |
| **Bramy** | przerwa z wozem → drewniane wrota → krata → barbakan (S) | `!gate` → `gate` → (nowe) |
| **Wieże** | drewniane strażnice → kamienne → galerie (hurdycje) → platformy balist | `towers` → `tower_mastery` → … → `ballista` |
| **Keep** | ruina bez dachu → hala z nowym dachem + War Table → kamienny donżon z wieżą schodową → wielka sala (Akt III) | tier 0/1/2 (+ nowy) |
| **Podgrodzie** | domy, spichlerz, kuźnia, karczma, izba chorych, cieśla, koszary z tarczami | `town.rs` + `villager_arms_tier`, `shrine` |

**Miasto vs twierdza:** budżet ciągnie w stronę miasta (ludzie, morale, złoto) albo twierdzy
(mury, wieże, machiny). Edykty Crane'a pchają w twierdzę (pobór → koszary Korony i balisty, ale
rynek pustoszeje). „Twierdza wygrywa z miastem” wynika z decyzji gracza.

## 7. Fazy

- **3a — układ i skala** (kod): obwód 28×21, `SAFE_R`, 3 bramy, strefy, pozycje jako funkcje
  `HALF_X/HALF_Z`, tymczasowe realistyczne wysokości prymitywów, przeniesiony rynek i dzwon,
  podłoże/trakty za nowym układem, oblężenie/drogi/testy.
- **3b — kamera** (kod): spring-arm przy wysokich bryłach.
- **3c — kit fortyfikacji** (Blender `castle_kit.glb`): wieża dzwonu, ruiny, palisada, kurtyna,
  wieże, brama, keep tier 0–2.
- **3d — kit miasta** (Blender `town_kit.glb`): spichlerz, kuźnia, karczma, dom Maud, izba chorych,
  ognisko, grób, domy szachulcowe, skład Korony, szubienica, namioty.
- **4 — integracja**: kity zamiast prymitywów, tiery według flag.
- **5 — mechanika**: bramy (zmierzch, HP, nawigacja orków), pięć torów, miasto vs twierdza.
- **6 — warianty aktowe + VO** (barwy Korony per akt, puste stragany Aktu III, epilogi).
