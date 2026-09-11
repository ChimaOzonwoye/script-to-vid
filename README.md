# script to vid

Write a script. Get back a finished narrated video: voiceover, drawn visuals,
subtitles, your logo and music. Eleven templates decide how it looks, from a
plain page to a dark room with a spotlight.

Runs on your own computer. Free, no account, no editing software, no limit on
how much you make.

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

![Picking a template](docs/the-page.png)

*The Look step. Every template shows a real still, and the light, the lettering
and what stands beside the speaker can each be changed on any of them.*

![A still from a finished video](docs/a-still.png)

*A frame from a finished video in the Ledger template.*

## Why this exists

Explaining something well takes narration, visuals, captions, branding and an
edit. Paying people for that costs money and AI video tools charge per render.
If you have something worth explaining and no budget, that is usually where it
ends.

This does the whole production on your own computer for free.

It is a first step, not a finish line. When you can afford better tools, use
them. Not having the resources should not be the reason you never start.

## Why there is no AI video in this

Generating video or images with a model needs a graphics card most computers
do not have, and paying a service to do it costs money per video. Either way
the requirement is the thing that stops people.

So everything is drawn from code with matplotlib. It runs on an ordinary
laptop, costs nothing, and never gets slower or more expensive the more you
make. It also means every frame is reproducible: the same script and the same
settings give the same video, which is what makes the cache safe.

## How it works

Six stages, each cached separately, so a change only redoes what it touched.

1. **Parse.** The script becomes a list of beats. A blank line ends a beat.
   `#` starts a chapter, `>` is a visual direction, everything else is
   narration. Beats carry content only and never line numbers, so editing
   higher up the script does not invalidate anything below it.
2. **Voice.** Each beat's line is sent to edge-tts and cached under a hash of
   the text, the voice and the speed. Changing the look never touches this.
3. **Slides.** Each beat is drawn to a PNG at 1920x1080. A beat with a
   speaking figure is drawn several times, once per mouth and eye position.
4. **Segments.** One MP4 per beat: the slide, a slow zoom, fades to the page
   colour, the narration, and the mouth positions cut to the audio. Cached
   under a hash of the beat, the template and the audio.
5. **Parts.** Segments are concatenated into chunks of about two and a half
   minutes and each chunk gets one encode with the logo and the music. Parts
   are cached too, so an interrupted render resumes.
6. **Final.** The parts are stream copied together and the subtitle file is
   written.

Nothing leaves your machine except the edge-tts requests. The web app binds to
127.0.0.1 and there is no account, no database and no server to run.

## Use

Your first project opens with an example script already in it. Press
**Generate** and watch a real video come out before you write anything of your
own.

After that: write your script, choose a voice, pick a template, add a logo and
music if you want them, then Generate. Download the MP4 and the subtitle file
when it finishes. Each video is a project, and duplicating one starts the next
video with the same settings.

Twelve voices are included, across American, British, Australian, Indian and
Nigerian accents, and you can hear each one before you choose. Three speeds.

Re-running is cheap. Editing one line only remakes that line. Changing the
look reuses the whole voiceover. Changing the voice remakes the narration and
nothing else.

A long video is encoded in parts of a couple of minutes each, and finished
parts are kept. If a render is interrupted, or the computer gives up, starting
it again picks up where it stopped rather than going back to the beginning.

## Templates

A template is three things: a ground, a light and a palette. Colours alone
were not enough. Four palettes on the same pale page gave four videos that
were the same video in four colours.

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
in the same place, with a headline from your script beside them. The headline
changes and the side swaps at a chapter, which reads as a cut to the other
camera.

It used to rotate four layouts and move the figure every beat, which made a
run of ordinary paragraphs read as a slideshow. The other layouts are still
there and are reached by naming them in a direction.

The headline is the first sentence of the beat when it is short enough,
otherwise the first comma clause, otherwise a word count with trailing
function words dropped. A fixed cut alone lands on "TAKE THE MONEY OUT
BEFORE" and leaves the reader waiting out the beat for an object that never
arrives.

## Joining videos

**Join videos** on the front page puts finished videos together into one, in
whatever order you tick them.

Two reasons. A long script can be made as two or three projects and joined at
the end, if you would rather work in sittings than wait for one render. And a
joiner is useful on its own, so it takes video files from anywhere.

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

## Decisions worth knowing about

**Everything is cached on content, never on position.** A beat carries what it
says and how it looks, not where it sits in the script. Insert a paragraph at
the top and nothing below it rebuilds. This is also why the same script always
gives the same video.

**One music bed for the whole video, sliced across the parts.** A bed built
per part fades down at the end of one and up at the start of the next, which
measures as a hole about a second and a half wide at every join: the mix drops
to 18 where the unsplit render sits at 224. There is one bed and each part
reads its own stretch of it.

**Parts are cut between beats and nowhere else.** A beat is a paragraph, so a
part can only end where the script had a blank line and the video already cut.
A part cannot end part-way through a sentence and rejoining is a stream copy.

**The app page does not follow a dark template.** It borrows the template's
hue and not its lightness. A dark app was never designed, and a template that
took the whole app dark with it would have been a worse surprise than a page
that stays pale.

**The interface is not a form.** One column of equal cards down the middle of
a wide screen is the shape of a form whatever the cards are made of, so the
work column has an index of the steps beside it and the script step gets more
room than the settings. Three passes at the card edges and surfaces did not
fix it, because the problem was never the edges.

**No trademarked characters, logos or brand marks in any template.** Reference
material for this kind of video is full of them. Copying one would hand a
claim over somebody's video to a company that had nothing to do with it.

**No YouTube downloader.** It would breach the terms of service and put
Content ID claims on videos people are trying to monetise, which is the
opposite of the point.

## Where this is

Working and tested: the parser, the voiceover and its cache, all the scene
layouts, the eleven templates with their grounds, lights, lettering and side
objects, the logo and music, subtitles, the part renderer and its resume, the
joiner, the installers for Windows and Mac, and the web app. 476 tests across
unit, integration and end to end, with a real render in the integration ones.

Known gaps:

- The joiner re-encodes a video that did not come from here, which takes
  minutes rather than seconds. It says so before it starts.
- There is no way to preview a single beat. The template picker draws a still,
  but your own script does not appear until you render it.
- Audio drifts against picture by about four milliseconds per part join,
  because an aac frame is 1024 samples and the stream has to end on one. A
  frame of video is thirty-three milliseconds, so this is well under one
  frame, but it does accumulate with the number of parts.
- Side objects sit in shadow under a spotlight, which is coherent but means
  Slate hides anything you put beside the speaker.

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
