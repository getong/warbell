# Campaign VO voices (ElevenLabs, 2026-10-14)

Re-takes and new lines MUST use the same voice per character prefix (`a1_<character>_NN.ogg`):

| prefix | character | ElevenLabs voice |
|---|---|---|
| `a1_harrow_*` | Ser Godric Harrow (prologue) | Julian — Deep, Rich and Mature |
| `a1_wat_*` | Wat ("Ser Godric") | Sully — Mature, Deep and Intriguing |
| `a1_maud_*` | Maud, the Reeve | MoanElisa — Sultry, Dark, Velvet |
| `a1_pip_*` | Pip (12) | Omar J — Very Young Storyteller |
| `a1_settler_*` | settler | Wilf — Cheerful, Quirky & Northern |
| `a1_farmer_*` | farmer | Darby Skelm — Witty and Sarcastic |
| `a1_hamid_*` | Hamid | Sal — calm, Confidential |
| `a1_ork_*`, `a1_shaman_*` | orks (broken common) | Dante — Growly and Menacing Monster |

Script + key → transcript table: `docs/audio/elevenlabs-akt-1.md`.
Processing (same as `vo/life`): cut per line, per-voice gain to -16 LUFS, quiet lines lifted to >= -24 LUFS,
limiter -1 dBFS, mono 44.1 kHz Vorbis q5.
