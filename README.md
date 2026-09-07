# script to vid

Write a script. Get back a narrated video with visuals, subtitles, your logo
and music. Runs on your own computer, free, no editing software.

## Install

**Windows.** Press the Windows key, type `powershell`, open it, then paste
this and press Enter:

```
irm https://raw.githubusercontent.com/ChimaOzonwoye/script-to-vid/main/install.ps1 | iex
```

**Mac.** Press Command and Space, type `terminal`, open it, then paste this
and press Enter:

```
curl -fsSL https://raw.githubusercontent.com/ChimaOzonwoye/script-to-vid/main/install.sh | bash
```

That is the whole install. It checks for Python and tells you where to get it
if you need it, downloads everything including the video engine, and opens the
app in your browser when it is finished. The first run takes a few minutes.
After that there is a **script to vid** shortcut on your Desktop.

If you would rather not paste something you have not read, open the link in
your browser first and read it. Or paste it into an AI chatbot and ask what it
does before you run it. Piping a script from the internet into your shell is a
fair thing to be careful about.

<details>
<summary>Prefer to download it yourself?</summary>

Click the green **Code** button above, then **Download ZIP**, and unzip it.
Then on Windows double-click `install-windows.bat`, or on a Mac open Terminal
in that folder and run `./install.sh`. Same result, more steps.

</details>

![The page](docs/the-page.png)

![A still from a finished video](docs/a-still.png)

## Why this exists

Explaining something well is not just a video. It is narration, visuals,
captions, branding and an edit. Paying people for that costs money. AI video
tools charge per render. If you have something worth explaining and no budget,
that is usually where it ends.

This does the whole production on your own computer for free, so money is not
the reason it never gets made.

This is a first step, not a finish line. It gets you making and publishing
now, with what you already have. When you can afford better tools, use them.
Not having the resources should not be the reason you never start.

## Why there is no AI video in this

Generating video or images with a model needs a graphics card most computers
do not have. Paying a service to do it instead costs money per video. Either
way, the requirement is the thing that stops people.

So this draws everything from code. It runs on an ordinary laptop, it costs
nothing, and it never gets slower or more expensive the more you make.

## Use

Your first project opens with a short example script already in it. Press
**Generate** and watch a real video come out before you write anything of your
own.

After that: write your script, choose a voice, pick a look, add a logo and
music if you want them, then Generate. Download the MP4 and the subtitle file
when it finishes. Each video is a project, and duplicating one starts the next
week's video with the same settings.

Twelve narration voices are included across American, British, Australian,
Indian and Nigerian accents, and you can hear each one before you choose. The
speed has three settings.

Re-running is cheap. Editing one line only remakes that line. Changing the
look reuses the whole voiceover. Changing the voice remakes the narration and
nothing else.

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
`sweep`, `outro`, and the modifiers `caption`, `sub`, `prop` and `scene`.
Anything the parser does not recognise becomes a plain caption slide and a
note above the Generate button, never an error.

`> scene: kitchen` puts a character in a room. The settings are `classroom`,
`office`, `kitchen`, `living room`, `street` and `plain`, and `plain` is what
you get if you never ask, so every script you have already written looks the
same as it did.

The full example is in `example-script.txt`.

## Licence

You can use this for anything, including commercially. The videos you make are
yours, and nobody has a claim on them.

The bundled music and the character drawings are original work that ships with
this project, with no rights held by anyone else, so a video using them is safe
to put on a monetised channel. No attribution is required.

The code is MIT licensed. See [LICENSE](LICENSE).

## Contributing

Contributions are welcome. Bugs, new scene layouts, new props, more voices,
better installers, anything. Open an issue or send a pull request.

The one rule: this has to stay usable by someone who has never opened a
terminal. A change that adds a setup step, a config file to edit, or an error
message only a developer can read is not an improvement here, however good the
code is.
