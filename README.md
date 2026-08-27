# script to vid

Turns a written narration script into a finished, narrated explainer video.
No editing software, no cost per video.

![The page](docs/the-page.png)

![A still from a finished video](docs/a-still.png)

## Why this exists

Making a video usually means paying an editor, or paying per render for an AI
video tool. If you have something worth explaining but not the budget to
produce it, that cost is where you stop.

This turns a written script into a finished video on your own machine, for
nothing. It runs locally, there is no account and no per-video charge, so
running out of money is not the thing that stops you starting.

## Before you install

You need **Python 3.10 or newer**. If you do not have it, download it from
[python.org/downloads](https://www.python.org/downloads/) and install it
first. On Windows, tick **Add python.exe to PATH** on the first screen of the
Python installer.

The installer will tell you plainly if Python is missing, so if you are not
sure, just carry on and it will check for you.

## Install

1. Download this repository: the green **Code** button, then **Download ZIP**.
   Unzip it somewhere you can find again, like your Documents folder.

2. **Windows:** double-click `install-windows.bat`.
   **Mac:** open Terminal in the folder and run `./install-mac.sh`.

   Windows may warn that the file came from the internet. Choose **More info**,
   then **Run anyway**. The installer sets up Python packages and downloads
   ffmpeg, which takes a few minutes the first time.

3. When it says it is done, start the app:
   - Use the **script to vid** shortcut on your Desktop, or
   - if the shortcut is not there, open the folder you unzipped and
     double-click **`run.bat`** on Windows or **`run.sh`** on a Mac.

A browser tab opens showing the app. Everything runs on your machine. The only
thing that leaves it is the text of your script, sent to Microsoft's free
voice service to be read aloud.

## Use

Your first project starts with a short example script already loaded, so you
can press **Generate** straight away and watch a real video come out. After
that, replace the script with your own.

Write a script, pick a look, add a logo and music if you want them, then press
Generate. Download the MP4 and the subtitle file when it finishes. Each video
is a project, and duplicating one starts the next video with the same look.

Re-running is cheap: editing one line only remakes that line, and changing the
theme reuses the whole voiceover.

## The script format

Blank lines separate beats. `#` starts a chapter. `>` is a visual direction.
Everything else is narration.

```
# How to boil an egg

> character: happy, cheer
> caption: Cover them by an inch

Start with eggs straight from the fridge, and a pan deep enough to cover them
by about an inch of water.

> bubbles: soft?, medium?, hard?
> caption: One pan, three results

Six minutes gives you a runny yolk. Eight is soft but set. Ten and it is firm
all the way through.
```

Directions include `character`, `duo`, `bubbles`, `split`, `chart`, `gauge`,
`timeline`, `growth`, `jars`, `terms`, `callout`, `quiet`, `recap`, `title`,
`sweep`, `outro`, and the modifiers `caption`, `sub` and `prop`. Anything the
parser does not recognise becomes a plain caption slide and a note above the
Generate button, never an error.

The full example is in `example-script.txt`.

## Licence

You can use this for anything, including commercially. The videos you make are
yours, and nobody has a claim on them.

The bundled music and the character drawings are original work that ships with
this project, with no rights held by anyone else, so a video using them is safe
to monetise. No attribution is required.

The code is MIT licensed. See [LICENSE](LICENSE).
