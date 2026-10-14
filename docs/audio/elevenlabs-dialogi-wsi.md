# ElevenLabs: dialogi mieszkańców (rozmowy dwóch osób)

Mieszkańcy zamku i przedmieść rozmawiają teraz parami. Kiedy dwie osoby z życia wsi
(`village_life.rs::life_social`) stają do pogawędki, a ich głosy pasują do któregoś dialogu, gra puszcza
**skrypt**: pytanie, odpowiedź, puentę. Wcześniej leciały dwie niezwiązane losowe kwestie `Chat`.
Dialog odpala się dopiero wtedy, gdy na dysku są **wszystkie** jego pliki. Do tego czasu zostają losowe kwestie.

Klucze to `life_dlg_NN_K`, gdzie NN to numer dialogu, a K numer kwestii. Pliki trafiają do
`assets/audio/vo/life/<klucz>.ogg`. Katalog jest w `src/audio/lines.rs` (`LIFE_DIALOGUES` i wpisy `life_dlg_*`).

## Jak generować

Tak samo jak przy `elevenlabs-zycie-wsi.md`:

- **Model:** Eleven v3, Stability „Natural”.
- **Ustawienia:** speed 0.89, stability 0.34, similarity 0.75. Tagi w nawiasach kwadratowych to audio tagi v3.
- **Jedna generacja na głos.** Wklej cały blok danego głosu. Każda kwestia idzie w osobnym akapicie, bez kluczy.
- **Kolejność w bloku = kolejność w tabeli.** Bloki ułożone są **rolami**: najpierw wszystkie kwestie Chłopa ze
  wszystkich dialogów, potem wszystkie kwestie Gospodyni, potem Starca.
- **Pliki:** prześlij jeden mp3 na głos: `dlg_man.mp3`, `dlg_woman.mp3`, `dlg_elder.mp3`. Potnę je po ciszy i przypiszę
  kluczom w kolejności z tabel.
- Kwestie są krótkie i sporo z nich to riposty. Grane są jedna po drugiej przez dwie różne osoby, więc **nie
  dodawaj pauz na początku ani na końcu**.
- **Nieudana kwestia:** wygeneruj sam ten akapit jeszcze raz i dopisz klucz do nazwy pliku.

## Głosy — te same co w życiu wsi (NIE ZMIENIAĆ)

| Rola | ID | Głos ElevenLabs |
|---|---|---|
| Chłop (każdy dorosły mężczyzna) | `man_a` | **Darby Skelm** |
| Gospodyni (każda dorosła kobieta) | `woman_a` | **MoanElisa** |
| Starzec | `elder` | **Alder** |

Dialogi bez starca nie mają stałych imion: w dialogach „kobieta–kobieta” obie role czyta MoanElisa, a w „chłop–chłop”
obie czyta Darby Skelm. W grze mówią dwie różne postacie, a przestrzenny dźwięk z dwóch miejsc załatwia resztę.
Jeśli chcesz je wyraźniej rozróżnić, czytaj jedną rolę odrobinę wyżej albo szybciej. Zaznaczam to tagiem.

---

## Blok 1 — CHŁOP (Darby Skelm) → `dlg_man.mp3`

Wklej do ElevenLabs (akapit = kwestia):

```
[puzzled] Have you seen my good hammer?

[indignant] I never lent it to Tam.

[dry, unbothered] It's a yard. It's made of mud.

[excited, gossiping] Bell rang twice last night. Twice!

[concerned] Is he alright?

[defensive, slow] I looked at it. Very carefully.

[matter-of-fact] It's definitely broken.

[weary] Reckon we'll see orks tonight?

[flat, deadpan] Reckon we see orks every night.

[sighs] Aye. Just hoping for a different answer.

[hopeful] Can I borrow your cart tomorrow?

[curt] Wheel's off.

[brightly] Borrow your wheel, then?

[exasperated] That's the cart, Hob. You'd just have the cart.

[grumbling] They want more stone for the wall.

[weary] They always want more stone for the wall.

[sarcastic] Maybe if the orks stopped taking it apart.

[dry] Write to them. See how that goes.

[sceptical] And did it work?

[sighs] Fence is down again by the barley. Third time.
```

| # | klucz | dialog | tekst |
|---|---|---|---|
| 1 | `life_dlg_01_1` | 01 młotek | Have you seen my good hammer? |
| 2 | `life_dlg_01_3` | 01 młotek | I never lent it to Tam. |
| 3 | `life_dlg_02_2` | 02 błoto | It's a yard. It's made of mud. |
| 4 | `life_dlg_03_1` | 03 dzwon | Bell rang twice last night. Twice! |
| 5 | `life_dlg_03_3` | 03 dzwon | Is he alright? |
| 6 | `life_dlg_04_2` | 04 okiennica | I looked at it. Very carefully. |
| 7 | `life_dlg_04_4` | 04 okiennica | It's definitely broken. |
| 8 | `life_dlg_08_1` | 08 orki dziś? (rola A) | Reckon we'll see orks tonight? |
| 9 | `life_dlg_08_2` | 08 orki dziś? (rola B) | Reckon we see orks every night. |
| 10 | `life_dlg_08_3` | 08 orki dziś? (rola A) | Aye. Just hoping for a different answer. |
| 11 | `life_dlg_09_1` | 09 wóz (rola A) | Can I borrow your cart tomorrow? |
| 12 | `life_dlg_09_2` | 09 wóz (rola B) | Wheel's off. |
| 13 | `life_dlg_09_3` | 09 wóz (rola A) | Borrow your wheel, then? |
| 14 | `life_dlg_09_4` | 09 wóz (rola B) | That's the cart, Hob. You'd just have the cart. |
| 15 | `life_dlg_10_1` | 10 kamień (rola A) | They want more stone for the wall. |
| 16 | `life_dlg_10_2` | 10 kamień (rola B) | They always want more stone for the wall. |
| 17 | `life_dlg_10_3` | 10 kamień (rola A) | Maybe if the orks stopped taking it apart. |
| 18 | `life_dlg_10_4` | 10 kamień (rola B) | Write to them. See how that goes. |
| 19 | `life_dlg_11_2` | 11 grabie | And did it work? |
| 20 | `life_m_chat_2` | (brakująca stara kwestia) | Fence is down again by the barley. Third time. |

## Blok 2 — GOSPODYNI (MoanElisa) → `dlg_woman.mp3`

```
[helpful, innocent] The one you lent to Tam?

[smug] Well. Tam's got a very nice hammer now.

[irritated] You're tracking mud through the whole yard.

[firm] Not my bit of it.

[gossiping, amused] Once for the orks. Once for old Bram falling off the wall.

[deadpan] Landed on the pigs. The pigs are not alright.

[suspicious] Did you fix the shutter like I asked?

[expectant] And?

[conspiratorial] Margit's bread's gone up a penny again.

[snorts] And down a size. I could post it through the keyhole.

[whispers, then loudly sweet] Shh, here she comes. Lovely loaves, Margit!

[curious, gossiping] Is that knight ever going to take his helmet off?

[dreamy] My sister says he's very handsome under there.

[flat] Your sister's never seen under there.

[knowing] That's why she's so sure.

[wrinkling nose] The well water tastes of iron today.

[casual] That's the new bucket. Or the sword somebody dropped down there last week.

[resigned] I'll boil it.

[patient, a little loud] It's summer, Grandad.

[worried] Need rain for the beans. And none of us need orks.
```

| # | klucz | dialog | tekst |
|---|---|---|---|
| 1 | `life_dlg_01_2` | 01 młotek | The one you lent to Tam? |
| 2 | `life_dlg_01_4` | 01 młotek | Well. Tam's got a very nice hammer now. |
| 3 | `life_dlg_02_1` | 02 błoto | You're tracking mud through the whole yard. |
| 4 | `life_dlg_02_3` | 02 błoto | Not my bit of it. |
| 5 | `life_dlg_03_2` | 03 dzwon | Once for the orks. Once for old Bram falling off the wall. |
| 6 | `life_dlg_03_4` | 03 dzwon | Landed on the pigs. The pigs are not alright. |
| 7 | `life_dlg_04_1` | 04 okiennica | Did you fix the shutter like I asked? |
| 8 | `life_dlg_04_3` | 04 okiennica | And? |
| 9 | `life_dlg_05_1` | 05 chleb Margit (rola A) | Margit's bread's gone up a penny again. |
| 10 | `life_dlg_05_2` | 05 chleb Margit (rola B) | And down a size. I could post it through the keyhole. |
| 11 | `life_dlg_05_3` | 05 chleb Margit (rola A) | Shh, here she comes. Lovely loaves, Margit! |
| 12 | `life_dlg_06_1` | 06 hełm (rola A) | Is that knight ever going to take his helmet off? |
| 13 | `life_dlg_06_2` | 06 hełm (rola B) | My sister says he's very handsome under there. |
| 14 | `life_dlg_06_3` | 06 hełm (rola A) | Your sister's never seen under there. |
| 15 | `life_dlg_06_4` | 06 hełm (rola B) | That's why she's so sure. |
| 16 | `life_dlg_07_1` | 07 studnia (rola A) | The well water tastes of iron today. |
| 17 | `life_dlg_07_2` | 07 studnia (rola B) | That's the new bucket. Or the sword somebody dropped down there last week. |
| 18 | `life_dlg_07_3` | 07 studnia (rola A) | I'll boil it. |
| 19 | `life_dlg_12_2` | 12 zimy | It's summer, Grandad. |
| 20 | `life_w_chat_2` | (brakująca stara kwestia) | Need rain for the beans. And none of us need orks. |

## Blok 3 — STARZEC (Alder) → `dlg_elder.mp3`

```
[proud, wagging a finger] When I was your age, we fought orks with a rake.

[grumpy] No. That's why I'm still angry about it.

[wistful] This fort's seen worse winters than this.

[stubborn] Then it's seen worse summers too.
```

| # | klucz | dialog | tekst |
|---|---|---|---|
| 1 | `life_dlg_11_1` | 11 grabie | When I was your age, we fought orks with a rake. |
| 2 | `life_dlg_11_3` | 11 grabie | No. That's why I'm still angry about it. |
| 3 | `life_dlg_12_1` | 12 zimy | This fort's seen worse winters than this. |
| 4 | `life_dlg_12_3` | 12 zimy | Then it's seen worse summers too. |

---

## Dialogi w całości (do odsłuchu / kontroli)

| # | kto | przebieg |
|---|---|---|
| 01 młotek | Chłop → Gospodyni | „Have you seen my good hammer?” / „The one you lent to Tam?” / „I never lent it to Tam.” / „Well. Tam's got a very nice hammer now.” |
| 02 błoto | Gospodyni → Chłop | „You're tracking mud through the whole yard.” / „It's a yard. It's made of mud.” / „Not my bit of it.” |
| 03 dzwon | Chłop → Gospodyni | „Bell rang twice last night. Twice!” / „Once for the orks. Once for old Bram falling off the wall.” / „Is he alright?” / „Landed on the pigs. The pigs are not alright.” |
| 04 okiennica | Gospodyni → Chłop | „Did you fix the shutter like I asked?” / „I looked at it. Very carefully.” / „And?” / „It's definitely broken.” |
| 05 chleb Margit | Gospodyni → Gospodyni | „Margit's bread's gone up a penny again.” / „And down a size…” / „Shh, here she comes. Lovely loaves, Margit!” |
| 06 hełm | Gospodyni → Gospodyni | „Is that knight ever going to take his helmet off?” / „My sister says he's very handsome under there.” / „Your sister's never seen under there.” / „That's why she's so sure.” |
| 07 studnia | Gospodyni → Gospodyni | „The well water tastes of iron today.” / „That's the new bucket. Or the sword…” / „I'll boil it.” |
| 08 orki dziś? | Chłop → Chłop | „Reckon we'll see orks tonight?” / „Reckon we see orks every night.” / „Aye. Just hoping for a different answer.” |
| 09 wóz | Chłop → Chłop | „Can I borrow your cart tomorrow?” / „Wheel's off.” / „Borrow your wheel, then?” / „That's the cart, Hob…” |
| 10 kamień | Chłop → Chłop | „They want more stone for the wall.” / „They always want more stone…” / „Maybe if the orks stopped taking it apart.” / „Write to them. See how that goes.” |
| 11 grabie | Starzec → Chłop | „When I was your age, we fought orks with a rake.” / „And did it work?” / „No. That's why I'm still angry about it.” |
| 12 zimy | Starzec → Gospodyni | „This fort's seen worse winters than this.” / „It's summer, Grandad.” / „Then it's seen worse summers too.” |
