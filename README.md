# unpleasant

A catalogue of Bible verses backing up every chapter of Dan Barker's *God: The Most Unpleasant Character in All Fiction* (2016) — cross-referenced against 18+ translations and the underlying Hebrew text.

## A personal note

This was my first real project when I was learning Python. I've come back and polished bits of it here and there over the years, but never really had the time to finish it properly. If some friends want to jump in, maybe we can finally get it there.

## What it is

Barker's book argues that God, as a literary character, exhibits a consistent set of flaws — jealous, unjust, genocidal, and so on — one per chapter. This project turns each of those chapters into a searchable category: every verse cited gets tagged with its category, notes explaining why it qualifies, and search keywords, then rendered against parallel Bible translations (including the original Hebrew where available).

`unpleasant` is what (g) is.

## Features

- **Explore UI** (`src/web.py`) — browse the Bible as a tree (book → chapter → verse) or flip through the "Catalogue" of flaw categories, with flagged verses highlighted and a bit of biological/chemical trivia annotated onto the text (wine → ethanol, cedar → cedrol, etc.)
- **Reader** (`src/reader.py`) — a calmer, book-like view where each category reads like its own chapter you page through
- **Desktop search tool** (`src/ui.py`) — a Tkinter app for searching by category, book, or free text, with side-by-side translation + Hebrew columns
- **Multi-language** — verses are shown next to translations in a dozen-plus languages, fetched via `src/fetch_bibles.py`

## Project structure

```
src/
  categories/       one file per character-flaw category (genocidal.py, jealous.py, ...)
  bibles/           Bible translations as JSON, one file per language
  web.py            Explore + Catalogue web UI (Flask)
  reader.py         book-like reader web UI (Flask)
  ui.py             desktop search tool (Tkinter)
  unit.py           shared tree model (book/chapter/verse) + bio/chemo annotation
  hebrew.py         Hebrew book names + gematria numerals
  fetch_bibles.py   downloads additional translations from api.getbible.net
```

Each category file (e.g. `src/categories/genocidal.py`) is a Python literal dict: a name, a dictionary-style definition, and a list of verse entries (book, chapter, verse, notes, search keywords).

## Running it

Requires Python 3.10+ and Flask (`pip install flask`) for the web UIs; the desktop tool only needs the standard library.

```
python src/web.py       # Explore / Catalogue UI  → http://localhost:5000
python src/reader.py    # Reader UI                → http://localhost:5050
python src/ui.py        # Desktop search tool
```

Both web tools accept `--port` and `--no-browser`.

## Contributing

This is still a work in progress. All 27 of the book's flaw chapters are catalogued, but plenty of entries could use more translations, better notes, or a second pass. PRs and issues welcome.
