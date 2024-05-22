# PG13Nator

A project to remove bad words from movies

## Why

Some people don't like to watch movies where characters curses a lot, so I decided to make a script that remove that

## How to run

```bash
git cloen https://github.com/diegosoriarios/PG13Nator.git
cd ios PG13Nator
pip3 install
python3 script.py --video=VIDEO_PATH
```

## Steps
- [x] Extract audio from video
- [x] Transcribe audio to text
- [x] Filter the text to see if there is any bad words
- [x] Mute/Blip the bad words in the audio
- [x] Remove the original audio from the video
- [x] Add the new audio to the video
- [ ] MAYBE: add subtitles also filtered