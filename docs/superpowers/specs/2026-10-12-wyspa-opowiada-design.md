# Wyspa opowiada: narracja środowiskowa per biom (design)

> Uzupełnienie `2026-10-10-kampania-fabula-design.md` (tamten dokument jest nadrzędny i go nie
> edytujemy). Tu jest tylko to, **co mówi sama wyspa**: bez tekstu, bez interakcji, przez miejsca do
> odkrycia. Napisy w grze zostają po angielsku.

## 1. Zasady

1. **Każdy biom to inny rozdział historii wyspy i inny punkt widzenia.** Biomy nie dzielą się
   typami miejsc: ruina z lasu nie wraca na pustyni w innym kolorze.
2. **Mało powtórzeń.** Miejsca fabularne występują raz, a drobne i ogólne (ognisko myśliwych, wrak
   wozu) najwyżej dwa razy. Lepiej 5 unikalnych miejsc w biomie niż 15 kopii trzech.
3. **Każdy biom ma własną paletę materiałów i własne modele.** Wspólne są tylko techniki
   (pipeline Blendera, planner, `attach_story`).
4. **Trzy warstwy czasu**, które gracz rozróżnia po materiale:
   - **Starzy** (przodkowie orków, prastare): menhiry, żelazne gongi, runy, prawo żelaznego głosu.
     Kamień porośnięty porostem, żelazo czarne od wieków.
   - **Pierwsza kolonia** (sto lat temu, Brother Anselm): zbutwiałe drewno, zielony brąz,
     zapadnięte dachy.
   - **Teraźniejszość** (lud Pashy, Korona, nasz wrak, obecna wojna): świeże ślady, popiół,
     tkanina, która jeszcze nie spłowiała.
5. **Ziarna, nie wykład.** Linijka lore zasiewa zwrot (dzwon wzywa orki, Korona wiedziała, orki to
   lud), ale nigdy go nie mówi wprost.
6. **Obozy orków zostają w liczbie pięciu, ale każdy jest inny** formą i funkcją, związaną z
   rozdziałem fabuły. Żaden nie jest kopią szablonu „namioty + ognisko + klatka”.

## 2. Łuk Anselma (strony dziennika, kolejność czytania ≠ kolejność odkrywania)

Gracz zbiera strony w dowolnej kolejności, a układają się w historię w pięciu etapach:

| Etap | Biom | Co mówi strona (ziarno) |
|---|---|---|
| 1. Przybycie | **Las** | lądowanie, karczowanie, odlewanie dzwonu według królewskiego wzoru, czyli inskrypcja; zielony lud przychodzi popatrzeć, ciekawy, bez broni |
| 2. Ekspansja | **Pustynia** | wyprawa gubernatora na południe, żeby **mierzyć zasypaną piramidę** (Korona chciała jej już wtedy); handel z orkami: sól za żelazo, nikt nie dobył ostrza |
| 3. Dzwon | **Skały** | dzwon zawieszony, statut odczytany, dzwonimy co zmierzch; pierwsze nocne ataki; „żelazo odpowiada żelazu w górach” (gongi klanów); niepokój Anselma |
| 4. Wojna | **Śnieg** (już jest) | Pustelnia Anselma (pusta dzwonnica, dwa groby, pulpit): lata wojny, odwrót, zaginiona partia drwali, ostatni apel |
| 5. Koniec | **Bagno** | zatopiona **kaplica misyjna** na skraju bagna. Anselm poszedł tam szukać rozmowy z orkami, wbrew gubernatorowi (lustro rozejmu Wata i Garroka). Ostatnia strona jest zalana, a ze szkicem dzwonu z inskrypcją zostały czytelne tylko dwa fragmenty: *„…came only after we rang…”* / *„…the Governor will not let us stop…”* |

Uwaga do chronologii: lud Pashy osiadł 30 lat przed Koroną, czyli **70 lat po upadku pierwszej
kolonii**. Anselm nie mógł go znać, więc pustynne strony mówią o orkach i piramidzie, nie o Pashy.

## 3. Biomy

### LAS (W/SW): „Początek”
- **Perspektywa:** nadzieja i trud. Obie kolonie zaczynały tutaj, a natura odebrała to, co
  zbudowano.
- **Paleta:** dąb, mech, paproć, porost, mokry kamień, grzyby, korzenie.
- **Jest:** obóz myśliwych, wyrąb (`stories_warm`).
- **Nowe:**
  - **Dół odlewniczy dzwonu.** Zawalony piec, skorupy glinianej formy, a na jednej skorupie
    fragment tej samej inskrypcji co na dzwonie w forcie (ziarno B). **Dzwonu tu nie ma.**
  - mielerz węglarzy;
  - **traczny dół** z pniem przepiłowanym do połowy;
  - **słup Starych wrośnięty w korzenie dębu**;
  - **pierwsze groby kolonii**.
- **Anselm:** etap 1 (1–2 strony, np. w dziupli dębu przy grobach).
- **Obóz orków:** **obóz szamanów** (Rozdz. 3 „The Ritual”) z totemami, kręgami z kości, amuletami
  na gałęziach i bębnem. Bez klatek.

### PUSTYNIA (NE): „Ci drudzy”
- **Perspektywa:** ludzie, którzy żyli z orkami w pokoju, i chciwość Korony starsza o sto lat.
- **Paleta:**
  - ochra i piaskowiec, spękane turkusowe kafle, sól;
  - płowa barwiona tkanina, mosiądz, kość;
  - wyszorowane wiatrem drewno.
- **Jest:** przewrócona karawana, żebra bestii, martwa oaza.
- **Nowe:**
  - **Kamienie targowe.** Neutralne miejsce wymiany orków z karawanami: płaska płyta, odważniki,
    znaki obu ludów, a dziś porzucone (ziarno: orki to lud).
  - **Paliki mierników i kopiec ze znakiem Korony na skraju piramidy.** Stare, pierwszej kolonii.
  - zasypana przez wydmę placówka kolonii (łuki, cysterna);
  - **ściana petroglifów Starych**;
  - **świeżo złupiona karawana na orkowym szlaku wojennym** (teraźniejszość: odkąd dzwon znów bije,
    orki atakują i Pashę).
- **Anselm:** etap 2.
- **Obóz orków:** **obóz łupieżców** w ruinie karawanseraju albo pod skalnym nawisem w wadi,
  z łupem z karawan Pashy (dywany, bele, dzbany).

### SKAŁY (E): „Żelazny głos”
- **Perspektywa:** prawo starsze od ludzi i orkowa kultura wojny.
- **Paleta:** granit, łupek, czarne żelazo, czerwona ochra, porost, liny.
- **Jest:** szyb kopalni, wóz pod obrywem, kamieniołom z niedokończonym monolitem.
- **Nowe:**
  - **Gong klanów.** Prastary żelazny gong między dwoma menhirami na wysokiej przełęczy. Nietknięty,
    ofiary u stóp, nikt tu nie obozuje (tabu, ziarno prawa).
  - **kamienna wieża sygnałowa kolonii** na grzbiecie;
  - **zerwany most linowy** nad żlebem (droga kolonii na wschód przecięta w wojnie);
  - **drzwi Starych w skale** z płytami runicznymi (rune trial);
  - **pole bitwy pierwszej wojny** w żlebie: hełmy kolonii i orkowe tasaki pod piargiem.
- **Anselm:** etap 3.
- **Obóz orków:** **obóz w jaskini.** Wojownicy w wylocie groty, a na ścianie **rzędy kresek**:
  stara kolumna setek kresek urwana sto lat temu i **nowa, świeża kolumna węglem** (ziarno B:
  „they're counting”).

### BAGNO (S): „Koniec i drugi brzeg”
- **Perspektywa:**
  - koszt wojny;
  - koniec pierwszej kolonii;
  - orki jako lud: groby, połowy, codzienność. Gnashfang jest tuż obok.
- **Paleta:** czarna woda, zbutwiałe belki, rdza, porost, torf, kość, trzcinowa strzecha.
- **Jest:** półzatopiona łódź z chatą na palach, utopiona kapliczka.
- **Nowe:**
  - **Zatopiona kaplica misyjna (landmark).** Przechylona w torf, z pustą dzwonnicą (jedyny dzwon
    jest w forcie) i pulpitem z zalaną księgą.
  - **Orkowe cmentarzysko** z ofiarami i świeżymi grobami tych, którzy „odpowiedzieli” (ziarno do
    Rozdz. 10: *„My brother answered last winter”*).
  - **jazy węgorzowe orków**;
  - grobla kolonii kończąca się w otwartej wodzie;
  - torfowisko z narzędziami.
- **Anselm:** etap 5 (ostatnia strona).
- **Obóz orków:** **obóz z klatkami na palach nad wodą** (Rozdz. 4 „The Muster”, Hamid). Przy
  klatkach miski z jedzeniem: jeńców się karmi, bo to okup za ciszę.

### ŚNIEG (NW): „Odwrót i świadkowie”
- **Jest:**
  - obóz drwali;
  - zasypana chata;
  - ostatni apel;
  - spalone gospodarstwo;
  - Konwój Korony;
  - Pustelnia Anselma (etap 4);
  - Krąg Starych.
- **Nowe:** **schron rozbitków ze śniegu (igloo).** Szalupa z naszego statku dryfowała w sztormie
  na północ. Na brzegu są wyciągnięta łódź, latarnia okrętowa, koce, a na wiośle wydrapane dni. Los
  ludzi jest niejasny: ślady prowadzą w głąb lądu. Dziennik bosmana: *„Rang the ship's bell till
  dawn. They came out of the fog at the second hour.”* (ziarno B, echo prologu).
- **Obóz orków:** **zimowy obóz łowców.** Jurty ze skór, suszarnie, przeręble na zamarzniętym
  jeziorze, tusza. Orki jako lud, nie horda.
- **Do decyzji:** **Konwój Korony wiezie brązowy dzwon wojenny**, co kłóci się z §11 p.3 speca
  fabuły („jeden dzwon”). Propozycja: zamienić ładunek na **skrzynię depesz gubernatora z pieczęcią
  Korony, pustą** (raporty dotarły do stolicy, czyli Korona wiedziała, §2).

## 4. Poza zakresem tego dokumentu
Wreck Cove, King's Road, miasto w Hold i krąg z zasadzką należą do kamieni milowych M1–M3 speca
fabuły. Tutaj tylko ich nie blokujemy: miejsca nie zajmują tych stref.
