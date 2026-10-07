# Music Playground

A collection of small, browser-based music exercises. Plain static HTML: no build step, no dependencies.

## Exercises

| Exercise | File | What it does |
| --- | --- | --- |
| תווים בקצב (Sight-reading in tempo) | `exercises/sight-reading.html` | Read a note, fifth, or triad from the staff and play it on the piano before the beats run out. Pitch is detected through the microphone; an on-screen keyboard works as a fallback. |
| דיאלוג בחשכה (Dialogue in the dark) | `exercises/dialogue-in-the-dark.html` | An English voice (Web Speech API) announces a note, fifth, triad, or one note per hand, and you find it on the piano by touch, with the screen blacked out. Same tempo and microphone engine as תווים בקצב. |

## Structure

```
index.html            # home page that lists all exercises
exercises/            # one self-contained HTML file per exercise
```

## Adding an exercise

1. Create `exercises/<name>.html` (copy the design tokens from an existing exercise so it matches).
2. Add a back link to `../index.html` at the top of the page.
3. Add a card for it in `index.html` (copy an existing `<li>`).

## Running locally

Open `index.html` directly, or serve the folder (the microphone needs `localhost` or HTTPS):

```
npx serve .
# or
python -m http.server
```

## Publishing on GitHub Pages

1. Push this repo to GitHub.
2. In the repo, go to **Settings → Pages**.
3. Under **Build and deployment**, choose **Deploy from a branch**, branch `master`, folder `/ (root)`.
4. The site will be at `https://<your-username>.github.io/<repo-name>/`.
