# unpleasant

A catalogue of Bible verses backing up every chapter of Dan Barker's *God: The Most Unpleasant Character in All Fiction* (2016) cross-referenced against 42 translations and the underlying Hebrew text.

## A personal note

Actually I see now that all the original code is... gone, this is pretty much AI.
I'm taking my original vision of this tool and putting it together now cuase once again I am testing a new thing I'm learning, AI.
I'm finishing/starting new/ this project with it, its fun and frustrating at the same time.

## What it is

Barker's book argues that God, as a literary character, exhibits a consistent set of flaws jealous, unjust, genocidal, and so on one per chapter. This project turns each of those chapters into a searchable category: every verse cited gets tagged with its category, notes explaining why it qualifies, and search keywords, then rendered against parallel Bible translations (including the original Hebrew where available).

`unpleasant` is what (g) is.

## Features

- **Catalogue** (`src/web.py`) flip through the 27 flaw categories (Jealous, Genocidal, Misogynistic, ...), with every verse cross-referenced against 42 translations, a Hebrew column with proper chapter:verse references in Hebrew gematria, an Overview panel, and Gematria / Hebrew-book-name reference tables
- **Timeline** a zoomable, color-coded stacked-bar chart of catalogued verses across all 66 books, with full English and Hebrew book names, per-category color legends, and verse counts
- **4 color themes** (Crimson, Inferno, Abyss, Void), plus adjustable text/UI sizing, all remembered across visits
- **Reader** (`src/reader.py`) a calmer, book-like view where each category reads like its own chapter you page through
- **Desktop search tool** (`src/ui.py`) a Tkinter app for searching by category, book, or free text, with side-by-side translation + Hebrew columns
- **Multi-language** verses are shown next to translations in 42 languages, fetched via `src/fetch_bibles.py`

## Project structure

```
src/
  categories/       one file per character-flaw category (genocidal.py, jealous.py, ...)
  bibles/           Bible translations as JSON, one file per language (42 total)
  templates/
    index.html      Catalogue + Timeline frontend (HTML/CSS/JS), served fresh on every request
  web.py            Catalogue + Timeline web UI (Flask)
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
python src/web.py       # Catalogue / Timeline UI  → http://localhost:5000
python src/reader.py    # Reader UI                → http://localhost:5050
python src/ui.py        # Desktop search tool
```

Both web tools accept `--port` and `--no-browser`.

`web.py` reads `src/templates/index.html` from disk on every request, so frontend edits (HTML/CSS/JS) show up on a browser refresh no server restart needed. Changes to `web.py` itself (or any other `.py` file) do require a restart.

## Contributing

This is still a work in progress. All 27 of the book's flaw chapters are catalogued (506 verses so far) chapter 28, "What About Jesus?", isn't a flaw category and is intentionally left out but plenty of entries could use more translations, better notes, or a second pass. PRs and issues welcome.
