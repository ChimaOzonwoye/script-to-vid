# script to vid

Write a script. Get back a narrated video with visuals, subtitles, your logo
and music. Characters blink and their mouths move in time with the narration.
Eleven templates decide how it looks, from a plain page to a dark room with a
spotlight. Finished videos can be joined into one. Runs on your own computer,
free, no editing software.

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

A long video is encoded in parts of a couple of minutes each, and finished
parts are kept. If a render is interrupted, or the computer gives up, starting
it again picks up where it stopped rather than going back to the beginning.

## Templates

A template is three things: a ground, a light and a palette. Colours alone
were not enough. Four palettes on the same pale page gave four videos that
were the same video in different colours, and a look is not a set of colours.

The ground is the flat pattern under every scene: a solid floor, a panel
behind the speaker, a halftone field, a sunburst, wide bands. The light is the
wash over it: even, a warm pool, a vignette, light from above, a spotlight.
The same palette under a spotlight is a different film, so the light is a
choice of its own and can be moved onto any template. So can the lettering,
which sets the words plain, haloed, with a drop shadow, or in a solid slab.

A template can also stand one thing beside the speaker: a board or a chart on
the wall behind them, a plant, flowers, an animal. It goes in the corner on
their side, because the headline runs most of the way to the other edge and
anything tall enough to be worth drawing over there lands on the sentence.
Rooms are a separate thing and still exist: a room is furniture across the
whole frame that you pick per beat with `> scene:`, this is one object a
template carries everywhere.

Eleven ship. Cream, Paper white, Sky and Mint are the quiet family: pale
ground, even light, nothing beside the speaker. Mustard, Riso print, Coral,
Slate, Deep forest, Ledger and Studio each commit to a ground and a light too,
and three of them are dark. Ledger is built for money: a lit desk and a chart
on the wall behind. Studio has a board on the wall, for teaching something.

The picker shows a real still of each one. A name and three colour dots cannot
tell anyone that Coral has a sunburst behind the speaker, and a template is the
one setting nobody can judge without seeing it. The stills are drawn the first
time you open that step and kept, so it happens once.

Picking a dark template does not take the app dark with it. The page borrows
the template's hue and not its lightness, because a dark app was never the
design.

Nothing in any template uses a trademarked character, logo or brand mark, so a
video made with one is safe to monetise.

## What a beat looks like

A paragraph with no direction on it is drawn as a presenter: one figure held
in the same place, with a line from your script beside them. The words beside
them change and the side swaps at a chapter, which reads as a cut to the other
camera.

It used to rotate through four layouts and move the figure every beat. That is
what made a run of ordinary paragraphs read as a slideshow rather than as
somebody talking to you. All the other layouts are still there and are reached
by naming them in a direction.

## Joining videos

**Join videos** on the front page puts finished videos together into one, in
whatever order you tick them.

It is there for two reasons. A long script can be made as two or three
projects and joined at the end, which is useful if you would rather work in
sittings than wait for one long render. And a joiner is useful on its own, so
it takes video files from anywhere, not just ones made here.

Videos made by this app are never re-encoded, because they already share one
shape, so joining them takes seconds however long they are. A video from
somewhere else is converted to that shape first, which takes minutes, and the
page says which of the two is about to happen before you start. Anything of a
different size is letterboxed rather than stretched, and a clip with no sound
has silence put in, because otherwise the audio would stop at that point and
never come back.

## The script format

**No special formatting is required.** Paste your script, exactly the words
you want spoken, and press Generate. Blank lines separate it into beats.

```
Boiling an egg sounds like the simplest thing in the world, and most people
still get it slightly wrong.

Start with eggs straight from the fridge, and a pan deep enough to cover them
by about an inch of water.
```

Scripts written elsewhere usually carry things nobody wants read aloud:
`[Scene 1 - man at a desk]`, a bare `0:00 - 0:15`, `Narration:` down the left
margin. Those are left out, labels like `Narration:` and `Visual:` are used
for what they describe, and every line that was left out is listed above the
Generate button with a button to put it back. Nothing is dropped silently.

### Optional formatting

If you want more control, two characters do it. `#` starts a chapter card and
`>` is a visual direction.

```
# How to boil an egg

> character: happy, cheer
> caption: Cover them by an inch

Start with eggs straight from the fridge.

> bubbles: soft?, medium?, hard?

Six minutes gives you a runny yolk.
```

Directions include `character`, `duo`, `bubbles`, `split`, `chart`, `gauge`,
`timeline`, `growth`, `jars`, `terms`, `callout`, `quiet`, `recap`, `title`,
`sweep`, `outro`, and the modifiers `caption`, `sub`, `prop` and `scene`.
Anything the parser does not recognise becomes narration, never an error.

`> scene: kitchen` puts a character in a room. The settings are `classroom`,
`office`, `kitchen`, `living room`, `street` and `plain`, and `plain` is what
you get if you never ask.

The example a new project opens with is in `example-script.txt`.

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
