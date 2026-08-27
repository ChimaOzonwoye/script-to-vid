# script to vid

Turns a written narration script into a finished, narrated explainer video —
no editing software, no cost per video.

![The page](docs/the-page.png)

![A still from a finished video](docs/a-still.png)

## Install

1. Download this repository (green **Code** button → **Download ZIP**) and unzip it.
2. Windows: right-click `install-windows.ps1` and choose **Run with PowerShell**.
   Mac: open Terminal in the folder and run `./install-mac.sh`.
3. When it says it's done, use the **script to vid** shortcut on your Desktop.

A browser tab opens at a local address. Everything runs on your machine; only
the voice generation talks to the internet.

## Use

Write a script, pick a look, add a logo and music if you want them, press
**Generate**. Download the MP4 and the subtitles when it finishes. Each video
is a project, and duplicating one starts the next video with the same look.

Re-running is cheap: editing one line only regenerates that line, and changing
the theme reuses the whole voiceover.

## The script format

Blank lines separate beats. `#` starts a chapter. `>` is a visual direction.
Everything else is narration.

```
# Your credit score starts early

> gauge

No credit is not the same as good credit.

> character: worried, think, triangle
> caption: It's a new vocabulary, not a flaw

Terms like APR and escrow get thrown at you like you already know them.
```

Directions include `character`, `duo`, `bubbles`, `split`, `chart`, `gauge`,
`timeline`, `growth`, `jars`, `terms`, `callout`, `quiet`, `recap`, `title`,
`sweep`, `outro`, and the modifiers `caption`, `sub` and `prop` (piggy, coin,
coins, jar). Anything the parser doesn't recognise becomes a plain caption
slide and a note above the Generate button — never an error.

## Licence

MIT. Everything here is original, including the character art and the bundled
music, which is generated from code in this repository and is safe to use in
monetised videos.
