# ElevenLabs: dialogi mieszkańców (rozmowy dwóch osób)

Mieszkańcy zamku i przedmieść rozmawiają parami. Kiedy dwie osoby z życia wsi (`village_life.rs::life_social`)
stają do pogawędki, a ich głosy pasują do któregoś dialogu, gra puszcza **całą scenkę**: 7–11 kwestii na zmianę,
każda czeka, aż poprzednia wybrzmi (a kiedy knight odejdzie dalej niż ~27 m albo para się rozejdzie, scenka się urywa).
Dialog odpala się dopiero wtedy, gdy na dysku są **wszystkie** jego pliki. Do tego czasu lecą losowe kwestie `Chat`.

**Wersja 2 (2026-10-15):** wszystkie 18 dialogów napisane od nowa: dłuższe, z puentą, z nawiązaniami do popkultury
(Wiedźmin, KCD, Skyrim, Monty Python, Shrek, Dzień Świstaka, Robin Hood) i z ziarnami fabuły (Ser Godric nie czyta,
nie wchodzi na wieżę i mówi o sobie w 3. osobie; pusty grób giermka; Hamid nuci pieśni orków; kreski na wieży;
pamiętnik mnicha). Żadna scenka nie zdradza, kim jest rycerz. Stare klipy `life_dlg_*` (jeśli jakieś nagrałeś)
**nie pasują** do nowych tekstów, więc nagraj wszystko od zera.

Klucze to `life_dlg_NN_K` (NN to numer dialogu, K numer kwestii). Pliki trafiają do
`assets/audio/vo/life/<klucz>.ogg`. Katalog jest w `src/audio/lines.rs` (`LIFE_DIALOGUES` i wpisy `life_dlg_*`).

## Jak generować

- **Model:** Eleven v3, Stability „Natural”.
- **Ustawienia:** speed 0.89, stability 0.34, similarity 0.75. Tagi w nawiasach kwadratowych to audio tagi v3.
- **Bloki ułożone rolami:** najpierw wszystkie kwestie Chłopa ze wszystkich dialogów, potem Gospodyni, potem Starca.
  Każdy głos jest pocięty na części do ~2600 znaków (limit jednej generacji v3). Jedna część = jedna generacja.
- **Akapit = kwestia**, bez kluczy. Kolejność w bloku = kolejność w tabeli pod nim.
- **Pliki:** jeden mp3 na część, nazwany jak w nagłówku (`dlg_man_1.mp3`, `dlg_man_2.mp3`, …). Potnę je po ciszy
  i przypiszę kluczom w kolejności z tabel.
- Kwestie grają dwie różne osoby jedna po drugiej, więc **nie dodawaj pauz na początku ani na końcu**.
- „...” na początku kwestii to zawahanie (krótka pauza przed słowami), a na końcu to urwane zdanie.
- **Nieudana kwestia:** wygeneruj sam ten akapit jeszcze raz i dopisz klucz do nazwy pliku.

## Głosy — te same co w życiu wsi (NIE ZMIENIAĆ)

| Rola | ID | Głos ElevenLabs |
|---|---|---|
| Chłop (każdy dorosły mężczyzna) | `man_a` | **Darby Skelm** |
| Gospodyni (każda dorosła kobieta) | `woman_a` | **MoanElisa** |
| Starzec | `elder` | **Alder** |

W dialogach „chłop–chłop” obie role czyta Darby Skelm, a w „kobieta–kobieta” obie czyta MoanElisa. W grze mówią dwie
różne postacie z dwóch miejsc, więc przestrzenny dźwięk je rozdziela. W tabelach zaznaczam rolę (A/B).

---

## Blok 1 — CHŁOP (Darby Skelm): 74 kwestii, 2 części

### CHŁOP część 1 → `dlg_man_1.mp3`

```
[low, gossiping] The Reeve was reading the knight his letters again. Out loud. In the square.

[scoffing] His eyes are fine. He spotted a ham on my windowsill from the gate.

[lowering voice] My brother served in the eastern campaign. Says Ser Godric used to write poems. In the margins of the casualty lists.

[uneasy] Bit grim, Edda.

[puzzled] The empty one? There's nobody under it.

[shrugging] The baker's girl, maybe. She was sweet on him on the boat.

[curious] Then who?

[relieved, warm] So the knight was mourning his squire. That's nice. That's a nice thing.

[pleased with himself] You know what orks are like? Onions.

[eager, explaining] Layers. Hide, then mail, then more hide. Then a sort of second hide.

[casually] Only the one. For learning.

[grim, matter-of-fact] Teeth. It's teeth all the way down.

[defensive, then unsure] It's turnip! ...It's mostly turnip.

[interested] And?

[confused] He wished for a goat?

[slowly] ...And the goat?

[hopeful] Did it work, at least? The wish?

[conspiratorial] Brewer's got a new schnapps. Drink it before bed, and if you die, you wake up right where you drank it.

[sceptical] And has anyone tested that?

[proudly] Hob did. Twice.

[interested] Did it work?

[hesitant] Well. The first time he woke up.

[slowly] And the second?

[awkward] We're giving it a few more days.

[nostalgic, puffed up] I was a soldier once, you know. Like him. Proper adventurer.

[polite] What happened?

[gravely] Took an ork spear in the...

[cutting in, exasperated] Don't you dare say knee.

[offended] Arse, Wendel. Took it in the arse.

[taken aback] ...Oh.

[mournful] Can't sit a horse. Can't sit a bench. Can barely sit in judgement.

[trying to be kind] Bet you'll be first up on the wall tonight, then.

[grim] Well, I'm not sitting down, am I.

[thoughtful] How much do you reckon a goose can carry?

[baffled] A goose?

[serious] In flight. Fully laden.

[suspicious] Is this a riddle, or are you trying to send letters home again?

[sad] My mother's not heard from me since the wreck. She thinks I drowned with the squire.

[dry] Then let her. You owe her money.

[wistful] ...A goose could carry a small apology.

[cheerful, like a bookmaker] Pool's open for tonight. Two pennies says the cooper's boy doesn't see harvest.

[appalled] That's monstrous. He's nine.

[reasonable] Odds are good, though.

[tempted] ...What odds?

[brisk] Four to one.

[decisive] Three pennies, then. On him living. Little bugger's quick.

[approving] That's the spirit. Nobody's betting on you, by the way.

[hurt] Nobody?
```

| # | klucz | dialog | tekst |
|---|---|---|---|
| 1 | `life_dlg_01_1` | 01 listy rycerza | The Reeve was reading the knight his letters again. Out loud. In the square. |
| 2 | `life_dlg_01_3` | 01 listy rycerza | His eyes are fine. He spotted a ham on my windowsill from the gate. |
| 3 | `life_dlg_01_5` | 01 listy rycerza | My brother served in the eastern campaign. Says Ser Godric used to write poems. In the margins of the casualty lists. |
| 4 | `life_dlg_01_7` | 01 listy rycerza | Bit grim, Edda. |
| 5 | `life_dlg_02_2` | 02 grób giermka | The empty one? There's nobody under it. |
| 6 | `life_dlg_02_4` | 02 grób giermka | The baker's girl, maybe. She was sweet on him on the boat. |
| 7 | `life_dlg_02_6` | 02 grób giermka | Then who? |
| 8 | `life_dlg_02_8` | 02 grób giermka | So the knight was mourning his squire. That's nice. That's a nice thing. |
| 9 | `life_dlg_03_1` | 03 orki jak cebula | You know what orks are like? Onions. |
| 10 | `life_dlg_03_3` | 03 orki jak cebula | Layers. Hide, then mail, then more hide. Then a sort of second hide. |
| 11 | `life_dlg_03_5` | 03 orki jak cebula | Only the one. For learning. |
| 12 | `life_dlg_03_7` | 03 orki jak cebula | Teeth. It's teeth all the way down. |
| 13 | `life_dlg_03_9` | 03 orki jak cebula | It's turnip! ...It's mostly turnip. |
| 14 | `life_dlg_04_2` | 04 wiedźma z bagien | And? |
| 15 | `life_dlg_04_4` | 04 wiedźma z bagien | He wished for a goat? |
| 16 | `life_dlg_04_6` | 04 wiedźma z bagien | ...And the goat? |
| 17 | `life_dlg_04_8` | 04 wiedźma z bagien | Did it work, at least? The wish? |
| 18 | `life_dlg_05_1` | 05 gorzałka piwowara (rola A) | Brewer's got a new schnapps. Drink it before bed, and if you die, you wake up right where you drank it. |
| 19 | `life_dlg_05_2` | 05 gorzałka piwowara (rola B) | And has anyone tested that? |
| 20 | `life_dlg_05_3` | 05 gorzałka piwowara (rola A) | Hob did. Twice. |
| 21 | `life_dlg_05_4` | 05 gorzałka piwowara (rola B) | Did it work? |
| 22 | `life_dlg_05_5` | 05 gorzałka piwowara (rola A) | Well. The first time he woke up. |
| 23 | `life_dlg_05_6` | 05 gorzałka piwowara (rola B) | And the second? |
| 24 | `life_dlg_05_7` | 05 gorzałka piwowara (rola A) | We're giving it a few more days. |
| 25 | `life_dlg_06_1` | 06 stara rana (rola A) | I was a soldier once, you know. Like him. Proper adventurer. |
| 26 | `life_dlg_06_2` | 06 stara rana (rola B) | What happened? |
| 27 | `life_dlg_06_3` | 06 stara rana (rola A) | Took an ork spear in the... |
| 28 | `life_dlg_06_4` | 06 stara rana (rola B) | Don't you dare say knee. |
| 29 | `life_dlg_06_5` | 06 stara rana (rola A) | Arse, Wendel. Took it in the arse. |
| 30 | `life_dlg_06_6` | 06 stara rana (rola B) | ...Oh. |
| 31 | `life_dlg_06_7` | 06 stara rana (rola A) | Can't sit a horse. Can't sit a bench. Can barely sit in judgement. |
| 32 | `life_dlg_06_8` | 06 stara rana (rola B) | Bet you'll be first up on the wall tonight, then. |
| 33 | `life_dlg_06_9` | 06 stara rana (rola A) | Well, I'm not sitting down, am I. |
| 34 | `life_dlg_07_1` | 07 obładowana gęś (rola A) | How much do you reckon a goose can carry? |
| 35 | `life_dlg_07_2` | 07 obładowana gęś (rola B) | A goose? |
| 36 | `life_dlg_07_3` | 07 obładowana gęś (rola A) | In flight. Fully laden. |
| 37 | `life_dlg_07_4` | 07 obładowana gęś (rola B) | Is this a riddle, or are you trying to send letters home again? |
| 38 | `life_dlg_07_5` | 07 obładowana gęś (rola A) | My mother's not heard from me since the wreck. She thinks I drowned with the squire. |
| 39 | `life_dlg_07_6` | 07 obładowana gęś (rola B) | Then let her. You owe her money. |
| 40 | `life_dlg_07_7` | 07 obładowana gęś (rola A) | ...A goose could carry a small apology. |
| 41 | `life_dlg_08_1` | 08 zakłady (rola A) | Pool's open for tonight. Two pennies says the cooper's boy doesn't see harvest. |
| 42 | `life_dlg_08_2` | 08 zakłady (rola B) | That's monstrous. He's nine. |
| 43 | `life_dlg_08_3` | 08 zakłady (rola A) | Odds are good, though. |
| 44 | `life_dlg_08_4` | 08 zakłady (rola B) | ...What odds? |
| 45 | `life_dlg_08_5` | 08 zakłady (rola A) | Four to one. |
| 46 | `life_dlg_08_6` | 08 zakłady (rola B) | Three pennies, then. On him living. Little bugger's quick. |
| 47 | `life_dlg_08_7` | 08 zakłady (rola A) | That's the spirit. Nobody's betting on you, by the way. |
| 48 | `life_dlg_08_8` | 08 zakłady (rola B) | Nobody? |

### CHŁOP część 2 → `dlg_man_2.mp3`

```
[apologetic] Couldn't find takers. Either way.

[flat, counting] Bell. Orks. Bury someone. Bell.

[patiently] It's a circle, Agnes. That's a circle.

[frowning] Not his. Pip's been here a month.

[trying to joke, unsettled] ...Someone with a lot of free time and no window.

[sceptical] And did it work?

[teasing] Should've hired a monster hunter.

[interested] Any good?

[dry] Sounds like you.

[defensive, slow] I looked at it. Very carefully.

[matter-of-fact] It's definitely broken.

[reasoning] Then they'll be in the larder. And they'll see what you cook. And they'll leave.

[gently] Barn's gone, love.

[excited] Heard there's a fellow in the western woods robbing the Crown's men and giving it all to the poor.

[enthusiastic] The poor.

[deflating] Well, he's mostly giving it to himself. He's very poor too.

[defending him] He's a robber with a lovely hat.

[puzzled, low] Why doesn't the knight ever go up the tower?

[knowing] Bad knee. From the campaign.

[unconvinced] He ran up the wall steps last night. Three at a time. With an ork on his back.

[airily] Wall steps aren't stairs. They're more of a slope with ambitions.

[frowning] And he talks about himself like he's somebody else. 'Ser Godric will see to it.'

[wise] Lords do that. My old lord called himself 'we'. Even on the privy.

[confused] Both of them?

[exasperated] There was only him, Osric. That's the point.

[sighs] Fence is down again by the barley. Third time.
```

| # | klucz | dialog | tekst |
|---|---|---|---|
| 49 | `life_dlg_08_9` | 08 zakłady (rola A) | Couldn't find takers. Either way. |
| 50 | `life_dlg_12_2` | 12 ten sam dzień | Bell. Orks. Bury someone. Bell. |
| 51 | `life_dlg_12_4` | 12 ten sam dzień | It's a circle, Agnes. That's a circle. |
| 52 | `life_dlg_12_6` | 12 ten sam dzień | Not his. Pip's been here a month. |
| 53 | `life_dlg_12_8` | 12 ten sam dzień | ...Someone with a lot of free time and no window. |
| 54 | `life_dlg_13_2` | 13 łowca potworów | And did it work? |
| 55 | `life_dlg_13_4` | 13 łowca potworów | Should've hired a monster hunter. |
| 56 | `life_dlg_13_6` | 13 łowca potworów | Any good? |
| 57 | `life_dlg_13_8` | 13 łowca potworów | Sounds like you. |
| 58 | `life_dlg_16_2` | 16 okiennica | I looked at it. Very carefully. |
| 59 | `life_dlg_16_4` | 16 okiennica | It's definitely broken. |
| 60 | `life_dlg_16_6` | 16 okiennica | Then they'll be in the larder. And they'll see what you cook. And they'll leave. |
| 61 | `life_dlg_16_8` | 16 okiennica | Barn's gone, love. |
| 62 | `life_dlg_17_1` | 17 rozbójnik | Heard there's a fellow in the western woods robbing the Crown's men and giving it all to the poor. |
| 63 | `life_dlg_17_3` | 17 rozbójnik | The poor. |
| 64 | `life_dlg_17_5` | 17 rozbójnik | Well, he's mostly giving it to himself. He's very poor too. |
| 65 | `life_dlg_17_7` | 17 rozbójnik | He's a robber with a lovely hat. |
| 66 | `life_dlg_18_1` | 18 schody (rola A) | Why doesn't the knight ever go up the tower? |
| 67 | `life_dlg_18_2` | 18 schody (rola B) | Bad knee. From the campaign. |
| 68 | `life_dlg_18_3` | 18 schody (rola A) | He ran up the wall steps last night. Three at a time. With an ork on his back. |
| 69 | `life_dlg_18_4` | 18 schody (rola B) | Wall steps aren't stairs. They're more of a slope with ambitions. |
| 70 | `life_dlg_18_5` | 18 schody (rola A) | And he talks about himself like he's somebody else. 'Ser Godric will see to it.' |
| 71 | `life_dlg_18_6` | 18 schody (rola B) | Lords do that. My old lord called himself 'we'. Even on the privy. |
| 72 | `life_dlg_18_7` | 18 schody (rola A) | Both of them? |
| 73 | `life_dlg_18_8` | 18 schody (rola B) | There was only him, Osric. That's the point. |
| 74 | `life_m_chat_2` | (brakująca stara kwestia) | Fence is down again by the barley. Third time. |

## Blok 2 — GOSPODYNI (MoanElisa): 66 kwestii, 2 części

### GOSPODYNI część 1 → `dlg_woman_1.mp3`

```
[shrugs it off] It's his eyes. Since the axe.

[dry] Ham's different. Ham is a calling.

[flat] Lovely.

[dry] Well, he doesn't write anything now. So that's an improvement for everyone.

[hushed, uneasy] Somebody leaves flowers on the squire's grave. Every morning. Fresh ones.

[quietly] Doesn't stop the flowers.

[dismissive] She was sweet on everyone on that boat. And she's never up before noon.

[whispering, creeped out] I couldn't sleep last night. Saw a big shape by the gate. In armour. Just standing there.

[whispering, unsettled] He kept saying sorry. Over and over. In a different voice.

[deadpan] They make you cry?

[suspicious] You've been peeling orks, Jory?

[curious despite herself] And what's in the middle?

[firmly] I'm not eating your stew tonight.

[gossiping] Marek walked out to the swamp witch. For a wish.

[matter-of-fact] Came back with nine fingers and a goat.

[patiently] He wished for a wife.

[firmly, lowering voice] We don't ask about the goat, Will.

[uneasy] He's very happy. That's the worrying part.

[curious, gossiping] Is that knight ever going to take his helmet off?

[dreamy] My sister says he's very handsome under there.

[dry] Your sister's never seen under there.

[smug] That's why she's so sure.

[lowering voice] Old Bram says the axe took half his face. Says he eats through the visor. Soup only.

[scoffing] Bram also says he once fought a bear for a wife. And lost.

[deadpan] He did lose. You've met her.

[conceding] ...Fair.

[softening] Still. Soup only. Poor lamb.

[sighs, wistful] My sister says she'd make him soup.

[complaining] Margit's bread's gone up a penny again.

[dry] And down a size. I could post it through the keyhole.

[lowering voice, disturbed] Found a tooth in mine yesterday.

[surprised] Margit's?

[uneasy] Not Margit's. Not anybody's I know. Long. Pointy.

[thinking aloud] Well, the orks did get into her mill last month...

[warning] Don't.

[relishing it] Grinds very fine, that mill.

[loud, disgusted] I said don't!

[suddenly sweet and loud] Shh, here she comes. Lovely loaves, Margit!

[hushed] That southerner they pulled out of the cage. Hamid. He hums at sundown.

[unbothered] Everybody hums.

[uneasy] Not their songs. The orks'. The drum one.

[sympathetic] Four months in a cage, I'd hum anything too.

[suspicious] He stops when you look at him. Then he smiles and tries to sell you a carpet.

[curious] Did you buy one?

[pleased despite herself] Half price. It's lovely.

[weary, thoughtful] Do you ever feel like we live the same day, over and over?
```

| # | klucz | dialog | tekst |
|---|---|---|---|
| 1 | `life_dlg_01_2` | 01 listy rycerza | It's his eyes. Since the axe. |
| 2 | `life_dlg_01_4` | 01 listy rycerza | Ham's different. Ham is a calling. |
| 3 | `life_dlg_01_6` | 01 listy rycerza | Lovely. |
| 4 | `life_dlg_01_8` | 01 listy rycerza | Well, he doesn't write anything now. So that's an improvement for everyone. |
| 5 | `life_dlg_02_1` | 02 grób giermka | Somebody leaves flowers on the squire's grave. Every morning. Fresh ones. |
| 6 | `life_dlg_02_3` | 02 grób giermka | Doesn't stop the flowers. |
| 7 | `life_dlg_02_5` | 02 grób giermka | She was sweet on everyone on that boat. And she's never up before noon. |
| 8 | `life_dlg_02_7` | 02 grób giermka | I couldn't sleep last night. Saw a big shape by the gate. In armour. Just standing there. |
| 9 | `life_dlg_02_9` | 02 grób giermka | He kept saying sorry. Over and over. In a different voice. |
| 10 | `life_dlg_03_2` | 03 orki jak cebula | They make you cry? |
| 11 | `life_dlg_03_4` | 03 orki jak cebula | You've been peeling orks, Jory? |
| 12 | `life_dlg_03_6` | 03 orki jak cebula | And what's in the middle? |
| 13 | `life_dlg_03_8` | 03 orki jak cebula | I'm not eating your stew tonight. |
| 14 | `life_dlg_04_1` | 04 wiedźma z bagien | Marek walked out to the swamp witch. For a wish. |
| 15 | `life_dlg_04_3` | 04 wiedźma z bagien | Came back with nine fingers and a goat. |
| 16 | `life_dlg_04_5` | 04 wiedźma z bagien | He wished for a wife. |
| 17 | `life_dlg_04_7` | 04 wiedźma z bagien | We don't ask about the goat, Will. |
| 18 | `life_dlg_04_9` | 04 wiedźma z bagien | He's very happy. That's the worrying part. |
| 19 | `life_dlg_09_1` | 09 pod hełmem (rola A) | Is that knight ever going to take his helmet off? |
| 20 | `life_dlg_09_2` | 09 pod hełmem (rola B) | My sister says he's very handsome under there. |
| 21 | `life_dlg_09_3` | 09 pod hełmem (rola A) | Your sister's never seen under there. |
| 22 | `life_dlg_09_4` | 09 pod hełmem (rola B) | That's why she's so sure. |
| 23 | `life_dlg_09_5` | 09 pod hełmem (rola A) | Old Bram says the axe took half his face. Says he eats through the visor. Soup only. |
| 24 | `life_dlg_09_6` | 09 pod hełmem (rola B) | Bram also says he once fought a bear for a wife. And lost. |
| 25 | `life_dlg_09_7` | 09 pod hełmem (rola A) | He did lose. You've met her. |
| 26 | `life_dlg_09_8` | 09 pod hełmem (rola B) | ...Fair. |
| 27 | `life_dlg_09_9` | 09 pod hełmem (rola A) | Still. Soup only. Poor lamb. |
| 28 | `life_dlg_09_10` | 09 pod hełmem (rola B) | My sister says she'd make him soup. |
| 29 | `life_dlg_10_1` | 10 chleb Margit (rola A) | Margit's bread's gone up a penny again. |
| 30 | `life_dlg_10_2` | 10 chleb Margit (rola B) | And down a size. I could post it through the keyhole. |
| 31 | `life_dlg_10_3` | 10 chleb Margit (rola A) | Found a tooth in mine yesterday. |
| 32 | `life_dlg_10_4` | 10 chleb Margit (rola B) | Margit's? |
| 33 | `life_dlg_10_5` | 10 chleb Margit (rola A) | Not Margit's. Not anybody's I know. Long. Pointy. |
| 34 | `life_dlg_10_6` | 10 chleb Margit (rola B) | Well, the orks did get into her mill last month... |
| 35 | `life_dlg_10_7` | 10 chleb Margit (rola A) | Don't. |
| 36 | `life_dlg_10_8` | 10 chleb Margit (rola B) | Grinds very fine, that mill. |
| 37 | `life_dlg_10_9` | 10 chleb Margit (rola A) | I said don't! |
| 38 | `life_dlg_10_10` | 10 chleb Margit (rola B) | Shh, here she comes. Lovely loaves, Margit! |
| 39 | `life_dlg_11_1` | 11 Hamid nuci (rola A) | That southerner they pulled out of the cage. Hamid. He hums at sundown. |
| 40 | `life_dlg_11_2` | 11 Hamid nuci (rola B) | Everybody hums. |
| 41 | `life_dlg_11_3` | 11 Hamid nuci (rola A) | Not their songs. The orks'. The drum one. |
| 42 | `life_dlg_11_4` | 11 Hamid nuci (rola B) | Four months in a cage, I'd hum anything too. |
| 43 | `life_dlg_11_5` | 11 Hamid nuci (rola A) | He stops when you look at him. Then he smiles and tries to sell you a carpet. |
| 44 | `life_dlg_11_6` | 11 Hamid nuci (rola B) | Did you buy one? |
| 45 | `life_dlg_11_7` | 11 Hamid nuci (rola A) | Half price. It's lovely. |
| 46 | `life_dlg_12_1` | 12 ten sam dzień | Do you ever feel like we live the same day, over and over? |

### GOSPODYNI część 2 → `dlg_woman_2.mp3`

```
[continuing the list] Bury someone, bell, orks...

[uneasy] Pip's found scratches up the tower. Little tally marks. Hundreds of them.

[quietly] Then whose?

[patient] It's summer, Grandad.

[curious] What happened to them?

[quietly] And then?

[eager] What did it say?

[scandalised] Grandad!

[flat] You never met my mother.

[dry] She had one leg.

[warming, proud] She was, actually. Hopped the whole harvest reel. Won a pig.

[stern] Did you fix the shutter like I asked?

[expectant] And?

[exasperated] The orks will come right through it, Piet.

[icy] ...Sleep in the barn tonight.

[icy] Then sleep where the barn was.

[sharp] Giving it to who?

[flat] We're the poor. Nobody's given us anything.

[dry] Then he's just a robber.

[worried] Need rain for the beans. And none of us need orks.
```

| # | klucz | dialog | tekst |
|---|---|---|---|
| 47 | `life_dlg_12_3` | 12 ten sam dzień | Bury someone, bell, orks... |
| 48 | `life_dlg_12_5` | 12 ten sam dzień | Pip's found scratches up the tower. Little tally marks. Hundreds of them. |
| 49 | `life_dlg_12_7` | 12 ten sam dzień | Then whose? |
| 50 | `life_dlg_14_2` | 14 pamiętnik mnicha | It's summer, Grandad. |
| 51 | `life_dlg_14_4` | 14 pamiętnik mnicha | What happened to them? |
| 52 | `life_dlg_14_6` | 14 pamiętnik mnicha | And then? |
| 53 | `life_dlg_14_8` | 14 pamiętnik mnicha | What did it say? |
| 54 | `life_dlg_14_10` | 14 pamiętnik mnicha | Grandad! |
| 55 | `life_dlg_15_2` | 15 tancerka | You never met my mother. |
| 56 | `life_dlg_15_4` | 15 tancerka | She had one leg. |
| 57 | `life_dlg_15_6` | 15 tancerka | She was, actually. Hopped the whole harvest reel. Won a pig. |
| 58 | `life_dlg_16_1` | 16 okiennica | Did you fix the shutter like I asked? |
| 59 | `life_dlg_16_3` | 16 okiennica | And? |
| 60 | `life_dlg_16_5` | 16 okiennica | The orks will come right through it, Piet. |
| 61 | `life_dlg_16_7` | 16 okiennica | ...Sleep in the barn tonight. |
| 62 | `life_dlg_16_9` | 16 okiennica | Then sleep where the barn was. |
| 63 | `life_dlg_17_2` | 17 rozbójnik | Giving it to who? |
| 64 | `life_dlg_17_4` | 17 rozbójnik | We're the poor. Nobody's given us anything. |
| 65 | `life_dlg_17_6` | 17 rozbójnik | Then he's just a robber. |
| 66 | `life_w_chat_2` | (brakująca stara kwestia) | Need rain for the beans. And none of us need orks. |

## Blok 3 — STARZEC (Alder): 15 kwestii, 1 części

### STARZEC część 1 → `dlg_elder_1.mp3`

```
[proud, wagging a finger] When I was your age, we fought orks with a rake.

[grumpy] No. That's why I'm still angry about it.

[remembering] Had one once. Cat's eyes, white hair, two swords.

[grumbling] Charged forty crowns for a drowner and moaned about the weather the whole time.

[fond, grudging] His horse was nicer than me. Smarter, too. Kept changing its name.

[wistful] This fort's seen worse winters than this.

[stubborn] Then it's seen worse summers. There was a colony here before us, you know. Hundred years back.

[matter-of-fact] Same as us. Bell, orks, bury someone.

[slow] Then there was nobody left to ring it. Found a page of their monk's diary in the old chapel.

[indignant] Can't read, can I? Used it to light the stove.

[satisfied] Lovely flame. Very holy.

[gallant, flirtatious] Your mother was the finest dancer on the whole east coast.

[unbothered] I'm being polite. Was she a good dancer?

[pause, recovering] ...Then she must've been tremendous at it.

[triumphant] There you are. Finest dancer on the east coast.
```

| # | klucz | dialog | tekst |
|---|---|---|---|
| 1 | `life_dlg_13_1` | 13 łowca potworów | When I was your age, we fought orks with a rake. |
| 2 | `life_dlg_13_3` | 13 łowca potworów | No. That's why I'm still angry about it. |
| 3 | `life_dlg_13_5` | 13 łowca potworów | Had one once. Cat's eyes, white hair, two swords. |
| 4 | `life_dlg_13_7` | 13 łowca potworów | Charged forty crowns for a drowner and moaned about the weather the whole time. |
| 5 | `life_dlg_13_9` | 13 łowca potworów | His horse was nicer than me. Smarter, too. Kept changing its name. |
| 6 | `life_dlg_14_1` | 14 pamiętnik mnicha | This fort's seen worse winters than this. |
| 7 | `life_dlg_14_3` | 14 pamiętnik mnicha | Then it's seen worse summers. There was a colony here before us, you know. Hundred years back. |
| 8 | `life_dlg_14_5` | 14 pamiętnik mnicha | Same as us. Bell, orks, bury someone. |
| 9 | `life_dlg_14_7` | 14 pamiętnik mnicha | Then there was nobody left to ring it. Found a page of their monk's diary in the old chapel. |
| 10 | `life_dlg_14_9` | 14 pamiętnik mnicha | Can't read, can I? Used it to light the stove. |
| 11 | `life_dlg_14_11` | 14 pamiętnik mnicha | Lovely flame. Very holy. |
| 12 | `life_dlg_15_1` | 15 tancerka | Your mother was the finest dancer on the whole east coast. |
| 13 | `life_dlg_15_3` | 15 tancerka | I'm being polite. Was she a good dancer? |
| 14 | `life_dlg_15_5` | 15 tancerka | ...Then she must've been tremendous at it. |
| 15 | `life_dlg_15_7` | 15 tancerka | There you are. Finest dancer on the east coast. |

---

## Dialogi w całości (do odsłuchu / kontroli)

### 01 listy rycerza (Chłop → Gospodyni)

- **Chłop:** The Reeve was reading the knight his letters again. Out loud. In the square.
- **Gospodyni:** It's his eyes. Since the axe.
- **Chłop:** His eyes are fine. He spotted a ham on my windowsill from the gate.
- **Gospodyni:** Ham's different. Ham is a calling.
- **Chłop:** My brother served in the eastern campaign. Says Ser Godric used to write poems. In the margins of the casualty lists.
- **Gospodyni:** Lovely.
- **Chłop:** Bit grim, Edda.
- **Gospodyni:** Well, he doesn't write anything now. So that's an improvement for everyone.

### 02 grób giermka (Gospodyni → Chłop)

- **Gospodyni:** Somebody leaves flowers on the squire's grave. Every morning. Fresh ones.
- **Chłop:** The empty one? There's nobody under it.
- **Gospodyni:** Doesn't stop the flowers.
- **Chłop:** The baker's girl, maybe. She was sweet on him on the boat.
- **Gospodyni:** She was sweet on everyone on that boat. And she's never up before noon.
- **Chłop:** Then who?
- **Gospodyni:** I couldn't sleep last night. Saw a big shape by the gate. In armour. Just standing there.
- **Chłop:** So the knight was mourning his squire. That's nice. That's a nice thing.
- **Gospodyni:** He kept saying sorry. Over and over. In a different voice.

### 03 orki jak cebula (Chłop → Gospodyni)

- **Chłop:** You know what orks are like? Onions.
- **Gospodyni:** They make you cry?
- **Chłop:** Layers. Hide, then mail, then more hide. Then a sort of second hide.
- **Gospodyni:** You've been peeling orks, Jory?
- **Chłop:** Only the one. For learning.
- **Gospodyni:** And what's in the middle?
- **Chłop:** Teeth. It's teeth all the way down.
- **Gospodyni:** I'm not eating your stew tonight.
- **Chłop:** It's turnip! ...It's mostly turnip.

### 04 wiedźma z bagien (Gospodyni → Chłop)

- **Gospodyni:** Marek walked out to the swamp witch. For a wish.
- **Chłop:** And?
- **Gospodyni:** Came back with nine fingers and a goat.
- **Chłop:** He wished for a goat?
- **Gospodyni:** He wished for a wife.
- **Chłop:** ...And the goat?
- **Gospodyni:** We don't ask about the goat, Will.
- **Chłop:** Did it work, at least? The wish?
- **Gospodyni:** He's very happy. That's the worrying part.

### 05 gorzałka piwowara (Chłop A → Chłop B)

- **Chłop A:** Brewer's got a new schnapps. Drink it before bed, and if you die, you wake up right where you drank it.
- **Chłop B:** And has anyone tested that?
- **Chłop A:** Hob did. Twice.
- **Chłop B:** Did it work?
- **Chłop A:** Well. The first time he woke up.
- **Chłop B:** And the second?
- **Chłop A:** We're giving it a few more days.

### 06 stara rana (Chłop A → Chłop B)

- **Chłop A:** I was a soldier once, you know. Like him. Proper adventurer.
- **Chłop B:** What happened?
- **Chłop A:** Took an ork spear in the...
- **Chłop B:** Don't you dare say knee.
- **Chłop A:** Arse, Wendel. Took it in the arse.
- **Chłop B:** ...Oh.
- **Chłop A:** Can't sit a horse. Can't sit a bench. Can barely sit in judgement.
- **Chłop B:** Bet you'll be first up on the wall tonight, then.
- **Chłop A:** Well, I'm not sitting down, am I.

### 07 obładowana gęś (Chłop A → Chłop B)

- **Chłop A:** How much do you reckon a goose can carry?
- **Chłop B:** A goose?
- **Chłop A:** In flight. Fully laden.
- **Chłop B:** Is this a riddle, or are you trying to send letters home again?
- **Chłop A:** My mother's not heard from me since the wreck. She thinks I drowned with the squire.
- **Chłop B:** Then let her. You owe her money.
- **Chłop A:** ...A goose could carry a small apology.

### 08 zakłady (Chłop A → Chłop B)

- **Chłop A:** Pool's open for tonight. Two pennies says the cooper's boy doesn't see harvest.
- **Chłop B:** That's monstrous. He's nine.
- **Chłop A:** Odds are good, though.
- **Chłop B:** ...What odds?
- **Chłop A:** Four to one.
- **Chłop B:** Three pennies, then. On him living. Little bugger's quick.
- **Chłop A:** That's the spirit. Nobody's betting on you, by the way.
- **Chłop B:** Nobody?
- **Chłop A:** Couldn't find takers. Either way.

### 09 pod hełmem (Gospodyni A → Gospodyni B)

- **Gospodyni A:** Is that knight ever going to take his helmet off?
- **Gospodyni B:** My sister says he's very handsome under there.
- **Gospodyni A:** Your sister's never seen under there.
- **Gospodyni B:** That's why she's so sure.
- **Gospodyni A:** Old Bram says the axe took half his face. Says he eats through the visor. Soup only.
- **Gospodyni B:** Bram also says he once fought a bear for a wife. And lost.
- **Gospodyni A:** He did lose. You've met her.
- **Gospodyni B:** ...Fair.
- **Gospodyni A:** Still. Soup only. Poor lamb.
- **Gospodyni B:** My sister says she'd make him soup.

### 10 chleb Margit (Gospodyni A → Gospodyni B)

- **Gospodyni A:** Margit's bread's gone up a penny again.
- **Gospodyni B:** And down a size. I could post it through the keyhole.
- **Gospodyni A:** Found a tooth in mine yesterday.
- **Gospodyni B:** Margit's?
- **Gospodyni A:** Not Margit's. Not anybody's I know. Long. Pointy.
- **Gospodyni B:** Well, the orks did get into her mill last month...
- **Gospodyni A:** Don't.
- **Gospodyni B:** Grinds very fine, that mill.
- **Gospodyni A:** I said don't!
- **Gospodyni B:** Shh, here she comes. Lovely loaves, Margit!

### 11 Hamid nuci (Gospodyni A → Gospodyni B)

- **Gospodyni A:** That southerner they pulled out of the cage. Hamid. He hums at sundown.
- **Gospodyni B:** Everybody hums.
- **Gospodyni A:** Not their songs. The orks'. The drum one.
- **Gospodyni B:** Four months in a cage, I'd hum anything too.
- **Gospodyni A:** He stops when you look at him. Then he smiles and tries to sell you a carpet.
- **Gospodyni B:** Did you buy one?
- **Gospodyni A:** Half price. It's lovely.

### 12 ten sam dzień (Gospodyni → Chłop)

- **Gospodyni:** Do you ever feel like we live the same day, over and over?
- **Chłop:** Bell. Orks. Bury someone. Bell.
- **Gospodyni:** Bury someone, bell, orks...
- **Chłop:** It's a circle, Agnes. That's a circle.
- **Gospodyni:** Pip's found scratches up the tower. Little tally marks. Hundreds of them.
- **Chłop:** Not his. Pip's been here a month.
- **Gospodyni:** Then whose?
- **Chłop:** ...Someone with a lot of free time and no window.

### 13 łowca potworów (Starzec → Chłop)

- **Starzec:** When I was your age, we fought orks with a rake.
- **Chłop:** And did it work?
- **Starzec:** No. That's why I'm still angry about it.
- **Chłop:** Should've hired a monster hunter.
- **Starzec:** Had one once. Cat's eyes, white hair, two swords.
- **Chłop:** Any good?
- **Starzec:** Charged forty crowns for a drowner and moaned about the weather the whole time.
- **Chłop:** Sounds like you.
- **Starzec:** His horse was nicer than me. Smarter, too. Kept changing its name.

### 14 pamiętnik mnicha (Starzec → Gospodyni)

- **Starzec:** This fort's seen worse winters than this.
- **Gospodyni:** It's summer, Grandad.
- **Starzec:** Then it's seen worse summers. There was a colony here before us, you know. Hundred years back.
- **Gospodyni:** What happened to them?
- **Starzec:** Same as us. Bell, orks, bury someone.
- **Gospodyni:** And then?
- **Starzec:** Then there was nobody left to ring it. Found a page of their monk's diary in the old chapel.
- **Gospodyni:** What did it say?
- **Starzec:** Can't read, can I? Used it to light the stove.
- **Gospodyni:** Grandad!
- **Starzec:** Lovely flame. Very holy.

### 15 tancerka (Starzec → Gospodyni)

- **Starzec:** Your mother was the finest dancer on the whole east coast.
- **Gospodyni:** You never met my mother.
- **Starzec:** I'm being polite. Was she a good dancer?
- **Gospodyni:** She had one leg.
- **Starzec:** ...Then she must've been tremendous at it.
- **Gospodyni:** She was, actually. Hopped the whole harvest reel. Won a pig.
- **Starzec:** There you are. Finest dancer on the east coast.

### 16 okiennica (Gospodyni → Chłop)

- **Gospodyni:** Did you fix the shutter like I asked?
- **Chłop:** I looked at it. Very carefully.
- **Gospodyni:** And?
- **Chłop:** It's definitely broken.
- **Gospodyni:** The orks will come right through it, Piet.
- **Chłop:** Then they'll be in the larder. And they'll see what you cook. And they'll leave.
- **Gospodyni:** ...Sleep in the barn tonight.
- **Chłop:** Barn's gone, love.
- **Gospodyni:** Then sleep where the barn was.

### 17 rozbójnik (Chłop → Gospodyni)

- **Chłop:** Heard there's a fellow in the western woods robbing the Crown's men and giving it all to the poor.
- **Gospodyni:** Giving it to who?
- **Chłop:** The poor.
- **Gospodyni:** We're the poor. Nobody's given us anything.
- **Chłop:** Well, he's mostly giving it to himself. He's very poor too.
- **Gospodyni:** Then he's just a robber.
- **Chłop:** He's a robber with a lovely hat.

### 18 schody (Chłop A → Chłop B)

- **Chłop A:** Why doesn't the knight ever go up the tower?
- **Chłop B:** Bad knee. From the campaign.
- **Chłop A:** He ran up the wall steps last night. Three at a time. With an ork on his back.
- **Chłop B:** Wall steps aren't stairs. They're more of a slope with ambitions.
- **Chłop A:** And he talks about himself like he's somebody else. 'Ser Godric will see to it.'
- **Chłop B:** Lords do that. My old lord called himself 'we'. Even on the privy.
- **Chłop A:** Both of them?
- **Chłop B:** There was only him, Osric. That's the point.
