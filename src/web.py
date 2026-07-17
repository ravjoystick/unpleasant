"""
God: The Most Unpleasant Character in All Fiction — Web UI
Run:  python src/web.py
      python src/web.py --port 8080
      python src/web.py --no-browser
"""
from __future__ import annotations
import os, ast, json, argparse, threading, webbrowser
from flask import Flask, jsonify, request, Response
from unit import build_bible_tree

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
BIBLES_DIR = os.path.join(BASE_DIR, 'bibles')
CATS_DIR   = os.path.join(BASE_DIR, 'categories')

# ── data loading ──────────────────────────────────────────────────────────────

def _load_categories() -> dict[str, dict]:
    """Load every category data file from CATS_DIR.

    Each file under src/categories/ is a Python dict literal (not an
    importable module): comment lines are stripped and the remainder is
    parsed with ast.literal_eval(). Files that fail to parse are silently
    skipped.

    Returns:
        A dict mapping each category's `name` field to its full data dict.
    """
    cats: dict[str, dict] = {}
    for fname in sorted(os.listdir(CATS_DIR)):
        if not fname.endswith('.py') or fname == '__init__.py':
            continue
        path = os.path.join(CATS_DIR, fname)
        with open(path, encoding='utf-8') as f:
            src = f.read()
        lines = [l for l in src.splitlines() if not l.strip().startswith('#')]
        try:
            data = ast.literal_eval('\n'.join(lines).strip())
            cats[data['name']] = data
        except Exception:
            pass
    return cats


def _load_bibles() -> dict[str, list]:
    """Load every Bible translation JSON file from BIBLES_DIR.

    Returns:
        A dict mapping translation code (filename without ``.json``) to its
        parsed book list.
    """
    bibles: dict[str, list] = {}
    for fname in sorted(os.listdir(BIBLES_DIR)):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(BIBLES_DIR, fname)
        with open(path, encoding='utf-8-sig') as f:
            bibles[fname[:-5]] = json.load(f)
    return bibles


def _build_name_map(kjv: list) -> dict[str, int]:
    """Build a lookup from book name/abbreviation to its index in `kjv`.

    Args:
        kjv: List of book dicts (as loaded from en_kjv.json).

    Returns:
        A dict mapping lowercased book name and abbreviation (plus the
        ``'psalm'`` -> ``'psalms'`` alias) to the book's index in `kjv`.
    """
    m: dict[str, int] = {}
    for i, book in enumerate(kjv):
        m[book['name'].lower()] = i
        m[book['abbrev'].lower()] = i
    m['psalm'] = m['psalms']
    return m


def _build_verse_index(categories: dict) -> dict[tuple, list[dict]]:
    """Build a lookup from (book, chapter, verse) to the categories citing it.

    Args:
        categories: The dict returned by `_load_categories`.

    Returns:
        A dict mapping ``(book.lower(), chapter, verse)`` to a list of
        ``{'cat_name': str, 'note': str}`` entries, one per category that
        cites that verse.
    """
    idx: dict[tuple, list[dict]] = {}
    for cat in categories.values():
        for entry in cat['verses'].values():
            for v in (entry['verse'] if isinstance(entry['verse'], list) else [entry['verse']]):
                key = (entry['book'].lower(), entry['chapter'], v)
                idx.setdefault(key, []).append({
                    'cat_name': cat['nice_name'],
                    'note':     entry.get('notes', ''),
                })
    return idx


# Every numbered chapter of Dan Barker's "God: The Most Unpleasant Character
# in All Fiction" (2016) that is a character-flaw category (i.e. all of
# Part I/II except ch.28 "What About Jesus?"), mapped to its category slug.
CHAPTER_NUMBERS: dict[str, int] = {
    'jealous': 1, 'petty': 2, 'unjust': 3, 'unforgiving': 4,
    'control_freak': 5, 'vindictive': 6, 'bloodthirsty': 7,
    'ethnic_cleanser': 8, 'misogynistic': 9, 'homophobic': 10, 'racist': 11,
    'infanticidal': 12, 'genocidal': 13, 'filicidal': 14, 'pestilential': 15,
    'megalomaniacal': 16, 'sadomasochistic': 17, 'capriciously_malevolent': 18,
    'bully': 19, 'pyromaniacal': 20, 'angry': 21, 'merciless': 22,
    'curse_hurling': 23, 'vaccicidal': 24, 'aborticidal': 25,
    'cannibalistic': 26, 'slavemonger': 27,
}

CATEGORIES  = _load_categories()
BIBLES      = _load_bibles()
_KJV        = BIBLES.get('en_kjv', next(iter(BIBLES.values())))
NAME_MAP    = _build_name_map(_KJV)
HEB_BIBLE   = BIBLES.get('he_tanakh', BIBLES.get('he_modern', BIBLES.get('he_aleppo', _KJV)))
DEFAULT_LANG = 'he_tanakh' if 'he_tanakh' in BIBLES else 'en_kjv'
VERSE_INDEX = _build_verse_index(CATEGORIES)
UNIT_TREE   = build_bible_tree(_KJV, CATEGORIES, HEB_BIBLE, NAME_MAP)
ALL_BOOKS   = [b['name'] for b in _KJV]
LANG_OPTIONS = sorted(BIBLES.keys())
CAT_OPTIONS  = sorted(CATEGORIES.keys())
BOOK_OPTIONS = sorted({v['book']
                       for cat in CATEGORIES.values()
                       for v in cat['verses'].values()})

# ── helpers ───────────────────────────────────────────────────────────────────

def _normalise_verses(raw) -> list[int]:
    """Wrap a single verse number in a list, or return a list unchanged.

    Args:
        raw: Either a single verse number (int) or a list of verse numbers.

    Returns:
        A list of verse numbers.
    """
    return raw if isinstance(raw, list) else [raw]


def _format_ref(book: str, chapter: int, verses) -> str:
    """Format a human-readable Bible reference.

    Args:
        book: Book name, e.g. ``'Genesis'``.
        chapter: Chapter number.
        verses: A single verse number or a list of verse numbers.

    Returns:
        e.g. ``'Genesis 1:1'`` for a single verse, or ``'Genesis 1:1–3'``
        for a range (using the first and last of `verses`).
    """
    vv = _normalise_verses(verses)
    if len(vv) == 1:
        return f'{book} {chapter}:{vv[0]}'
    return f'{book} {chapter}:{vv[0]}–{vv[-1]}'


def _get_text(bible: list, book: str, chapter: int, verses) -> str:
    """Look up and concatenate the text of one or more verses.

    Args:
        bible: A book list in the loaded-translation format (see `_load_bibles`).
        book: Book name to look up.
        chapter: Chapter number (1-indexed).
        verses: A single verse number or a list of verse numbers.

    Returns:
        The verse text(s) joined with a space, or ``''`` if the book,
        chapter, or all verses are out of range.
    """
    idx = NAME_MAP.get(book.lower())
    if idx is None or idx >= len(bible):
        return ''
    chs = bible[idx].get('chapters', [])
    if chapter < 1 or chapter > len(chs):
        return ''
    ch = chs[chapter - 1]
    parts = []
    for v in _normalise_verses(verses):
        if 1 <= v <= len(ch):
            parts.append(ch[v - 1])
    return ' '.join(parts)


def _chapter_count(book: str) -> int:
    """Return the number of chapters in `book` (per the KJV), or 0 if unknown."""
    idx = NAME_MAP.get(book.lower())
    if idx is None or idx >= len(_KJV):
        return 0
    return len(_KJV[idx].get('chapters', []))


def _verse_count(book: str, chapter: int) -> int:
    """Return the number of verses in `book` `chapter` (per the KJV), or 0 if unknown."""
    idx = NAME_MAP.get(book.lower())
    if idx is None or idx >= len(_KJV):
        return 0
    chs = _KJV[idx].get('chapters', [])
    if chapter < 1 or chapter > len(chs):
        return 0
    return len(chs[chapter - 1])


def _build_rows(mode: str, selection: str, lang_bible: list) -> list[tuple]:
    """Build catalogue table rows for a given search mode and selection.

    Args:
        mode: One of ``'category'``, ``'book'``, ``'search'``, ``'verse'``.
        selection: The category name, book name, free-text query, or
            ``'book|chapter|verse'`` string, depending on `mode`.
        lang_bible: The book list to pull verse text from, in the currently
            selected UI language.

    Returns:
        A list of ``(category_nice_name, reference, note, lang_text,
        heb_text)`` tuples.
    """
    rows: list[tuple] = []

    def _add(cat: dict, entry: dict) -> None:
        """Append one (category, ref, note, lang_text, heb_text) row for `entry`."""
        ref   = _format_ref(entry['book'], entry['chapter'], entry['verse'])
        ltext = _get_text(lang_bible, entry['book'], entry['chapter'], entry['verse'])
        htext = _get_text(HEB_BIBLE,  entry['book'], entry['chapter'], entry['verse'])
        rows.append((cat['nice_name'], ref, entry.get('notes', ''), ltext, htext))

    if mode == 'category':
        cat = CATEGORIES.get(selection)
        if cat:
            for entry in cat['verses'].values():
                _add(cat, entry)

    elif mode == 'book':
        sel_lower = selection.lower()
        for cat in CATEGORIES.values():
            for entry in cat['verses'].values():
                if entry['book'].lower() == sel_lower:
                    _add(cat, entry)

    elif mode == 'search':
        query = selection.strip().lower()
        if query:
            for cat in CATEGORIES.values():
                for entry in cat['verses'].values():
                    haystack = ' '.join([
                        entry.get('notes', '').lower(),
                        entry['book'].lower(),
                        cat['name'].lower(),
                        cat['nice_name'].lower(),
                        ' '.join(entry.get('search', [])).lower(),
                        _get_text(lang_bible, entry['book'],
                                  entry['chapter'], entry['verse']).lower(),
                    ])
                    if query in haystack:
                        _add(cat, entry)

    elif mode == 'verse':
        parts = selection.split('|')
        if len(parts) == 3:
            book, chapter, verse = parts[0], int(parts[1]), int(parts[2])
            ref   = f'{book} {chapter}:{verse}'
            ltext = _get_text(lang_bible, book, chapter, [verse])
            htext = _get_text(HEB_BIBLE,  book, chapter, [verse])
            hits  = VERSE_INDEX.get((book.lower(), chapter, verse), [])
            rows.append((
                hits[0]['cat_name'] if hits else '—',
                ref,
                hits[0]['note']     if hits else '(not in any category)',
                ltext,
                htext,
            ))

    return rows


# ── Flask ─────────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=None)


@app.route('/')
def index():
    """Serve the single-page Explore/Catalogue frontend."""
    return Response(_HTML, mimetype='text/html; charset=utf-8')


@app.route('/api/meta')
def api_meta():
    """Return catalogue metadata: categories, languages, and book options.

    Returns:
        A Flask JSON response consumed by the frontend's `init()` to
        populate the language selector, book filter, and category tab bar.
    """
    cats = sorted(
        CATEGORIES.values(),
        key=lambda c: (CHAPTER_NUMBERS.get(c['name'], 999), c['name']),
    )
    return jsonify({
        'categories': [{
            'name':      c['name'],
            'nice_name': c['nice_name'],
            'chapter':   CHAPTER_NUMBERS.get(c['name']),
            'count':     len(c['verses']),
        } for c in cats],
        'total_book_chapters': 28,
        'languages':    LANG_OPTIONS,
        'default_lang': DEFAULT_LANG,
        'kjv_books':    ALL_BOOKS,
        'book_options': BOOK_OPTIONS,
    })


@app.route('/api/gematria')
def api_gematria():
    """Return the Hebrew gematria numeral and book-name reference tables.

    Returns:
        A Flask JSON response with `numerals` (1-100) and `books` lists,
        sourced from hebrew.NUMERALS / hebrew.BOOKS.
    """
    import hebrew
    return jsonify({
        'numerals': [{
            'value': n.number, 'hebrew': n.hebrew, 'say': n.say,
            'unicode': list(n.unicode),
        } for n in hebrew.NUMERALS.values()],
        'books': [{
            'name': b.english, 'hebrew': b.hebrew, 'say': b.say,
        } for b in hebrew.BOOKS.values()],
    })


@app.route('/api/book_counts')
def api_book_counts():
    """Return, per KJV book, the verse count of each chapter.

    Returns:
        A Flask JSON response: a list of ``{'name': str, 'chapters':
        [int, ...]}`` dicts, one per book.
    """
    return jsonify([
        {'name': b['name'], 'chapters': [len(ch) for ch in b['chapters']]}
        for b in _KJV
    ])


def _bio_for_ref(ref: str) -> dict:
    """Look up a verse's bio/chemo annotation from UNIT_TREE by its reference string.

    Args:
        ref: A reference string, e.g. ``'Genesis 1:1'``.

    Returns:
        ``{'bio_name': str | None, 'chimo_name': str | None}``, both None
        if `ref` doesn't parse or has no matching node.
    """
    import re as _re
    m = _re.match(r'^(.+?)\s+(\d+):(\d+)', ref)
    if not m:
        return {'bio_name': None, 'chimo_name': None}
    book, ch, vs = m.group(1), int(m.group(2)), int(m.group(3))
    idx = NAME_MAP.get(book.lower())
    if idx is None:
        return {'bio_name': None, 'chimo_name': None}
    abbrev = _KJV[idx]['abbrev'].upper()
    node   = UNIT_TREE.find(f'{abbrev}.{ch}.{vs}')
    return {
        'bio_name':   node.bio_name   if node else None,
        'chimo_name': node.chimo_name if node else None,
    }


@app.route('/api/search')
def api_search():
    """Run a catalogue search and return matching rows with annotations.

    Query args:
        mode: One of ``'category'``, ``'book'``, ``'search'``, ``'verse'``
            (default ``'search'``).
        q: The category name, book name, free-text query, or
            ``'book|chapter|verse'`` string, depending on `mode`.
        lang: Translation code to render verse text in (default ``'en_kjv'``).

    Returns:
        A Flask JSON response: a list of row dicts with cat/ref/note/
        lang_text/heb_text plus bio_name/chimo_name annotations.
    """
    mode  = request.args.get('mode',  'search')
    q     = request.args.get('q',     '')
    lang  = request.args.get('lang',  'en_kjv')
    bible = BIBLES.get(lang, _KJV)
    rows  = _build_rows(mode, q, bible)
    return jsonify([{
        'cat':       r[0],
        'ref':       r[1],
        'note':      r[2],
        'lang_text': r[3],
        'heb_text':  r[4],
        **_bio_for_ref(r[1]),
    } for r in rows])


@app.route('/api/verse')
def api_verse():
    """Return a single verse's full detail, including catalogue and bio/chemo data.

    Query args:
        book: Book name (default ``'Genesis'``).
        ch: Chapter number (default ``1``).
        vs: Verse number (default ``1``).
        lang: Translation code to render verse text in (default ``'en_kjv'``).

    Returns:
        A Flask JSON response with the verse's category/note, translated
        and Hebrew text, dominant bio_name/chimo_name, and top_bio/top_chimo
        lists.
    """
    book  = request.args.get('book', 'Genesis')
    ch    = int(request.args.get('ch',  '1'))
    vs    = int(request.args.get('vs',  '1'))
    lang  = request.args.get('lang', 'en_kjv')
    bible = BIBLES.get(lang, _KJV)
    rows  = _build_rows('verse', f'{book}|{ch}|{vs}', bible)
    r     = rows[0] if rows else ('—', f'{book} {ch}:{vs}', '(not in any category)', '', '')
    idx   = NAME_MAP.get(book.lower())
    abbrev = _KJV[idx]['abbrev'].upper() if idx is not None else ''
    node  = UNIT_TREE.find(f'{abbrev}.{ch}.{vs}') if abbrev else None
    return jsonify({
        'cat':        r[0],
        'ref':        r[1],
        'note':       r[2],
        'lang_text':  r[3],
        'heb_text':   r[4],
        'bio_name':   node.bio_name   if node else None,
        'chimo_name': node.chimo_name if node else None,
        'top_bio':    node.top_bio(3)   if node else [],
        'top_chimo':  node.top_chimo(3) if node else [],
    })


@app.route('/api/node/<path:uid>')
def api_node(uid: str):
    """Return one Unit tree node's detail (and a summary of its children).

    Args:
        uid: The node's uid, e.g. ``'GEN'``, ``'GEN.1'``, ``'GEN.1.1'``
            (case-insensitive).

    Query args:
        lang: If given and `uid` resolves to a verse node, render that
            verse's text in this translation code as `lang_text`.

    Returns:
        A Flask JSON response (see Unit.to_dict), or a 404 JSON error if
        `uid` doesn't match any node.
    """
    node = UNIT_TREE.find(uid.upper())
    if node is None:
        return jsonify({'error': f'node {uid!r} not found'}), 404
    d = node.to_dict()
    lang = request.args.get('lang')
    if lang and node.level == 'verse' and node.book and node.chapter and node.verse_num:
        bible = BIBLES.get(lang, _KJV)
        d['lang_text'] = _get_text(bible, node.book, node.chapter, [node.verse_num])
    return jsonify(d)


# ── embedded frontend ─────────────────────────────────────────────────────────

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>God: The Most Unpleasant Character in All Fiction</title>
<style>
:root {
  --bg:      #0d0d1a;
  --panel:   #12122a;
  --panel2:  #1a1a35;
  --accent:  #c0392b;
  --accent2: #8e44ad;
  --text:    #e8e8f0;
  --dim:     #7777aa;
  --head:    #ffffff;
  --nav-bg:  #0a0a18;
  --bio-col: #4caf72;
  --chm-col: #5b9bd5;
  --row-odd: #1a1a35;
  --row-evn: #12122a;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;font-size:14px;display:flex;flex-direction:column}

/* top bar */
.top-bar{display:flex;align-items:center;gap:8px;padding:9px 16px;border-bottom:1px solid var(--panel2);flex-shrink:0}
.app-title{flex:1;font-size:14px;font-weight:700;color:var(--accent);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mode-btn{background:var(--panel);color:var(--dim);border:1px solid var(--panel2);border-radius:4px;padding:4px 14px;font-size:12px;cursor:pointer;font-family:inherit;transition:.15s all}
.mode-btn.active,.mode-btn:hover{background:var(--accent2);color:#fff;border-color:var(--accent2)}

/* views */
.view{display:flex;flex-direction:column;flex:1;overflow:hidden;min-height:0}
.view[hidden]{display:none!important}

/* breadcrumb */
.bc-bar{display:flex;align-items:center;gap:6px;padding:6px 14px;background:var(--panel);flex-shrink:0;min-height:36px}
#btn-back{background:none;border:none;color:var(--accent2);font-size:22px;line-height:1;cursor:pointer;padding:0 2px;transition:color .15s;flex-shrink:0}
#btn-back:hover{color:#fff}
#btn-back:disabled{color:var(--panel2);cursor:default}
.bc-crumb{font-size:12px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bc-sep{color:var(--panel2);margin:0 2px;flex-shrink:0}
.bc-item{color:var(--dim);cursor:pointer;transition:color .15s}
.bc-item:hover{color:var(--text)}
.bc-item.cur{color:var(--text);cursor:default}

/* category strip */
.cat-strip{display:flex;align-items:center;gap:6px;padding:5px 14px;background:var(--nav-bg);flex-shrink:0;min-height:32px;flex-wrap:wrap}
.cat-pill{font-size:11px;padding:2px 9px;border-radius:10px;white-space:nowrap;background:rgba(192,57,43,.18);color:var(--accent);border:1px solid rgba(192,57,43,.25)}
.strip-inf{font-size:11px;color:var(--dim)}
.strip-bio{font-size:10px;color:var(--bio-col);font-style:italic;margin-left:auto;white-space:nowrap}

/* card area */
.card-area{flex:1;overflow-y:auto;padding:14px;transition:opacity .18s;min-height:0}
.card-area.fading{opacity:0;pointer-events:none}

/* card grid */
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}

.ucard{background:var(--panel);border:1px solid var(--panel2);border-radius:7px;padding:13px 14px;cursor:pointer;transition:.15s transform,.15s border-color,.15s background;display:flex;flex-direction:column;gap:3px;min-height:108px}
.ucard:hover{transform:translateY(-3px);border-color:var(--accent2);background:var(--panel2)}
.ucard.flagged{border-left:3px solid var(--accent)}

.uc-level{font-size:9px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--dim)}
.uc-name{font-size:14px;font-weight:600;color:var(--head);line-height:1.3;margin-top:1px}
.uc-cats{display:flex;flex-wrap:wrap;gap:3px;margin-top:6px}
.uc-cat{font-size:9px;background:rgba(192,57,43,.18);color:var(--accent);border-radius:3px;padding:2px 6px;border:1px solid rgba(192,57,43,.2)}
.uc-foot{font-size:10px;color:var(--dim);margin-top:auto;padding-top:7px;display:flex;justify-content:space-between;align-items:flex-end;gap:6px}
.uc-bio-note{font-size:9px;color:#3a6b45;font-style:italic;text-align:right;line-height:1.3}

/* verse detail */
.vd-wrap{display:flex;flex-direction:column;gap:14px;max-width:860px;margin:0 auto;padding:22px 14px}
.vd-ref{font-size:24px;font-weight:700;color:var(--head)}
.vd-tags{display:flex;flex-wrap:wrap;gap:6px}
.vd-tag{font-size:12px;background:rgba(192,57,43,.2);color:var(--accent);border-radius:4px;padding:4px 11px;border:1px solid rgba(192,57,43,.3)}
.vd-text{font-size:16px;line-height:1.75;color:var(--text);padding:14px 18px;background:var(--panel);border-radius:6px;border-left:3px solid var(--accent2)}
.vd-heb{font-size:19px;line-height:1.8;color:#d4c5e8;direction:rtl;text-align:right;font-family:'Noto Serif Hebrew','David','Times New Roman',serif;padding:12px 18px;background:var(--panel);border-radius:6px}
.vd-note{font-size:13px;color:var(--dim);font-style:italic;padding:9px 13px;background:var(--panel2);border-radius:4px}
.vd-bio-row{display:flex;gap:8px;flex-wrap:wrap;padding-top:2px;border-top:1px solid var(--panel2);margin-top:4px}
.vd-bio-label{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);align-self:center}
.vd-chip{font-size:11px;padding:3px 9px;border-radius:10px}
.vd-chip.org{background:#152a1a;color:var(--bio-col);font-style:italic}
.vd-chip.chm{background:#101d2e;color:var(--chm-col);font-family:monospace}
.vd-nav{display:flex;gap:10px;padding-top:4px}
.vd-btn{background:var(--panel);color:var(--dim);border:1px solid var(--panel2);border-radius:4px;padding:6px 16px;cursor:pointer;font-family:inherit;font-size:13px;transition:.15s all}
.vd-btn:hover:not(:disabled){background:var(--accent2);color:#fff;border-color:var(--accent2)}
.vd-btn:disabled{opacity:.3;cursor:default}

/* search view */
.srch-ctrl{display:flex;align-items:center;gap:6px;padding:7px 14px;background:var(--panel);flex-shrink:0;flex-wrap:wrap}
.srch-table-wrap{flex:1;overflow-y:auto;min-height:0}
table{width:100%;table-layout:fixed;border-collapse:collapse}
thead th{position:sticky;top:0;z-index:2;background:var(--panel2);color:var(--head);font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:7px 13px;border-bottom:1px solid var(--bg)}
th.c-heb,td.c-heb{text-align:right}
th.c-cat{text-align:left}
.c-lang{width:45%}.c-heb{width:30%}.c-cat{width:25%}
tbody td{padding:10px 13px;vertical-align:top;line-height:1.55;font-size:13px}
tbody td.c-heb{direction:rtl;font-size:15px;color:#d4c5e8;font-family:'Noto Serif Hebrew','David',serif}
tbody td.c-cat{font-size:11px}
.td-cat-chip{display:inline-block;background:rgba(192,57,43,.18);color:var(--accent);border-radius:3px;padding:1px 6px;margin:1px 2px 1px 0;font-size:10px}
tbody tr.even{background:var(--row-evn)}
tbody tr.odd{background:var(--row-odd)}
tbody tr.sel{background:var(--accent)!important}
tbody tr.sel td{color:#fff!important}
tbody tr:not(.sel):hover{background:var(--panel2)}
tbody tr{cursor:pointer}
.placeholder{text-align:center;color:var(--dim);padding:40px;font-style:italic}
#lbl-count{margin-left:auto;font-size:11px;color:var(--dim);white-space:nowrap}

/* category tab bar — small pill buttons, replaces the old category <select> */
.cat-tabbar{display:flex;align-items:center;gap:5px;padding:7px 14px;background:var(--nav-bg);flex-shrink:0;flex-wrap:wrap;border-bottom:1px solid var(--panel2)}
.cat-tab{font-size:11px;padding:4px 10px;border-radius:999px;white-space:nowrap;background:var(--panel);color:var(--dim);border:1px solid var(--panel2);cursor:pointer;font-family:inherit;transition:.15s all}
.cat-tab:hover{border-color:var(--accent2);color:var(--text)}
.cat-tab.active{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
.cat-tab .ct-n{font-family:monospace;font-size:9px;opacity:.65;margin-right:3px}
.cat-tab .ct-c{font-size:9px;opacity:.75;margin-left:4px}
.cat-tab-sep{width:1px;height:15px;background:var(--panel2);margin:0 3px;flex-shrink:0}

/* overview panel */
.ov-wrap{padding:20px 24px}
.ov-lede{font-size:13px;color:var(--dim);line-height:1.6;margin-bottom:18px;max-width:640px}
.ov-stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:22px}
.ov-stat{background:var(--panel);border:1px solid var(--panel2);border-radius:8px;padding:12px 16px;min-width:110px}
.ov-stat-n{font-size:22px;font-weight:700;color:var(--accent)}
.ov-stat-l{font-size:11px;color:var(--dim);margin-top:2px}
.ov-list{border:1px solid var(--panel2);border-radius:8px;overflow:hidden}
.ov-row{display:flex;align-items:center;gap:10px;padding:8px 14px;border-bottom:1px solid var(--panel2);font-size:12.5px;cursor:pointer}
.ov-row:last-child{border-bottom:none}
.ov-row:hover{background:var(--panel2)}
.ov-row.pending{opacity:.45;cursor:default}
.ov-row.pending:hover{background:none}
.ov-num{font-family:monospace;font-size:11px;color:var(--dim);width:20px;text-align:right;flex-shrink:0}
.ov-title{flex:1}
.ov-badge{font-size:10px;padding:2px 8px;border-radius:20px;background:rgba(192,57,43,.18);color:var(--accent);font-weight:600}
.ov-badge.muted{background:var(--panel2);color:var(--dim)}

/* gematria / book-name reference tables */
.ref-wrap{padding:0}
td.c-heb-ref{direction:rtl;font-size:15px;color:#d4c5e8;font-family:'Noto Serif Hebrew','David',serif;width:20%}

/* shared controls */
.fk{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);white-space:nowrap}
select,input[type=text]{background:var(--panel);color:var(--text);border:1px solid #2a2a4a;border-radius:3px;padding:4px 8px;font-size:13px;font-family:inherit;outline:none;transition:border-color .15s}
select:focus,input:focus{border-color:var(--accent2)}
select option{background:var(--panel2);color:var(--text)}

/* scrollbar */
::-webkit-scrollbar{width:7px;height:7px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:#3a3a5a;border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:var(--accent2)}
</style>
</head>
<body>

<!-- top bar -->
<div class="top-bar">
  <span class="app-title">God: The Most Unpleasant Character in All Fiction</span>
  <span class="fk">Language</span>
  <select id="sel-lang" style="width:150px"></select>
  <button class="mode-btn"        onclick="setMode('explore')">Explore</button>
  <button class="mode-btn active" onclick="setMode('search')">Catalogue</button>
</div>

<!-- EXPLORE VIEW -->
<div id="view-explore" class="view" hidden>

  <div class="bc-bar">
    <button id="btn-back" disabled onclick="zoomBack()">&#8249;</button>
    <div id="bc" class="bc-crumb"></div>
  </div>

  <div class="cat-strip">
    <span id="strip-cats"></span>
    <span id="strip-inf" class="strip-inf"></span>
    <span id="strip-bio" class="strip-bio" hidden></span>
  </div>

  <div id="card-area" class="card-area">
    <div id="card-grid" class="card-grid"></div>
    <div id="vd" class="vd-wrap" hidden></div>
  </div>
</div>

<!-- SEARCH VIEW -->
<div id="view-search" class="view">
  <div id="cat-tabbar" class="cat-tabbar"></div>

  <div class="srch-ctrl">
    <span class="fk">Book</span>
    <select id="sel-book" style="width:152px"></select>
    <span class="fk" style="margin-left:6px">Search</span>
    <input id="inp-search" type="text" style="flex:1;max-width:260px" placeholder="notes, text, tags…" autocomplete="off">
    <span id="lbl-count"></span>
  </div>

  <div id="panel-overview" class="srch-table-wrap" hidden></div>
  <div id="panel-reference" class="srch-table-wrap" hidden></div>

  <div id="panel-results" class="srch-table-wrap">
    <table>
      <thead><tr>
        <th id="th-lang" class="c-lang">en_kjv</th>
        <th class="c-heb">&#x5E2;&#x5D1;&#x5E8;&#x5D9;&#x5EA;</th>
        <th class="c-cat">Categories</th>
      </tr></thead>
      <tbody id="tbl-body">
        <tr><td colspan="3" class="placeholder">Pick a category above, or search / filter by book.</td></tr>
      </tbody>
    </table>
  </div>
</div>

<script>
'use strict';

// ── shared ───────────────────────────────────────────────────────────────────
let LANG = 'he_tanakh';
let mode = 'search';

function $(id){ return document.getElementById(id); }
function delay(ms){ return new Promise(r => setTimeout(r,ms)); }
function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function debounce(fn,ms){ let t; return function(...a){ clearTimeout(t); t=setTimeout(()=>fn(...a),ms); }; }

async function api(path, params){
  const u = new URL(path, location.origin);
  if(params) Object.entries(params).forEach(([k,v])=>u.searchParams.set(k,String(v)));
  const r = await fetch(u);
  if(!r.ok) throw new Error(r.statusText);
  return r.json();
}

let exploreLoaded = false;

function setMode(m){
  mode = m;
  $('view-explore').hidden = m!=='explore';
  $('view-search').hidden  = m!=='search';
  document.querySelectorAll('.mode-btn').forEach((b,i)=>
    b.classList.toggle('active', (i===0&&m==='explore')||(i===1&&m==='search'))
  );
  if(m==='explore' && !exploreLoaded){
    exploreLoaded = true;
    navHist = ['ROOT'];
    zoom('ROOT', false);
  }
}

// ── explore ───────────────────────────────────────────────────────────────────
let navHist = [];
let curNode = null;

async function zoom(uid, push=true){
  const area = $('card-area');
  area.classList.add('fading');
  await delay(180);

  const node = await api('/api/node/'+uid, {lang:LANG});
  curNode = node;
  if(push) navHist.push(uid);

  renderBreadcrumb(node);
  renderCatStrip(node);

  if(node.level==='verse'){
    $('card-grid').hidden = true;
    $('vd').hidden = false;
    renderVerseDetail(node);
  } else {
    $('card-grid').hidden = false;
    $('vd').hidden = true;
    renderCards(node.children || []);
  }

  area.classList.remove('fading');
  area.scrollTop = 0;
}

async function zoomBack(){
  if(navHist.length<=1) return;
  navHist.pop();
  await zoom(navHist[navHist.length-1], false);
}

async function jumpTo(idx){
  navHist = navHist.slice(0, idx+1);
  await zoom(navHist[navHist.length-1], false);
}

// breadcrumb
function renderBreadcrumb(node){
  const parts = (node.breadcrumb||node.ui_name).split(' / ');
  $('bc').innerHTML = parts.map((p,i)=>{
    const last = i===parts.length-1;
    if(last) return '<span class="bc-item cur">'+esc(p)+'</span>';
    return '<span class="bc-item" onclick="jumpTo('+i+')">'+esc(p)+'</span>';
  }).join('<span class="bc-sep"> › </span>');
  $('btn-back').disabled = navHist.length<=1;
}

// category strip — categories are primary; bio/chemo are a small aside
function renderCatStrip(node){
  // collect top categories from children
  const freq={};
  (node.children||[]).forEach(c=>{
    [...new Set(c.category_tags||[])].forEach(t=>{ freq[t]=(freq[t]||0)+1; });
  });
  const topCats = Object.entries(freq).sort((a,b)=>b[1]-a[1]).slice(0,5).map(e=>e[0]);

  const cEl = $('strip-cats');
  cEl.innerHTML = topCats.map(t=>'<span class="cat-pill">'+esc(t)+'</span>').join('');

  const kids = (node.children||[]).length;
  const flagged = (node.children||[]).filter(c=>c.category_tags&&c.category_tags.length).length;
  const parts=[];
  if(kids>0){
    const w = node.level==='book'?'chapters':node.level==='chapter'?'verses':'items';
    parts.push(kids+' '+w);
  }
  if(flagged>0) parts.push(flagged+' flagged');
  $('strip-inf').textContent = parts.join('  •  ');

  // bio/chemo: small, right-aligned, only if present
  const sBio = $('strip-bio');
  const bioStr = [node.bio_name, node.chimo_name].filter(Boolean).join('  /  ');
  if(bioStr){ sBio.textContent=bioStr; sBio.hidden=false; } else sBio.hidden=true;
}

// cards — categories are the visual focus; bio/chemo is a small footnote
function renderCards(children){
  const grid=$('card-grid');
  grid.innerHTML='';
  if(!children.length){
    grid.innerHTML='<p style="color:var(--dim);padding:20px">No children.</p>';
    return;
  }
  const frag=document.createDocumentFragment();
  children.forEach(c=>{
    const tags = [...new Set(c.category_tags||[])];
    const div=document.createElement('div');
    div.className='ucard'+(tags.length?' flagged':'');
    div.onclick=()=>zoom(c.uid);

    const w = c.level==='book'?'ch':c.level==='chapter'?'vs':'';
    const childCount = c.n_children>0 ? c.n_children+' '+w : (c.level==='verse'?'verse':'—');
    const bioNote = [c.bio_name, c.chimo_name].filter(Boolean).join(' / ');

    const catsHtml = tags.length
      ? '<div class="uc-cats">'+tags.slice(0,4).map(t=>'<span class="uc-cat">'+esc(t)+'</span>').join('')+'</div>'
      : '';

    div.innerHTML=
      '<div class="uc-level">'+esc(c.level||'')+'</div>'+
      '<div class="uc-name">'+esc(c.ui_name)+'</div>'+
      catsHtml+
      '<div class="uc-foot">'+
        '<span>'+esc(childCount)+'</span>'+
        (bioNote?'<span class="uc-bio-note">'+esc(bioNote)+'</span>':'')+
      '</div>';
    frag.appendChild(div);
  });
  grid.appendChild(frag);
}

// verse detail — categories first, text second, bio/chemo at the bottom as annotations
function renderVerseDetail(node){
  const d=$('vd');
  const tags=[...new Set(node.category_tags||[])];
  const tagHtml=tags.map(t=>'<span class="vd-tag">'+esc(t)+'</span>').join('');
  const txt=node.lang_text||node.text||'';
  const heb=node.heb_text||'';
  const note=(node.notes&&node.notes!=='—'&&node.notes)?node.notes:'';

  let bioSection='';
  const bioChips=[];
  if(node.bio_name)   bioChips.push('<span class="vd-chip org">'+esc(node.bio_name)+'</span>');
  if(node.chimo_name) bioChips.push('<span class="vd-chip chm">'+esc(node.chimo_name)+'</span>');
  if(bioChips.length){
    bioSection='<div class="vd-bio-row"><span class="vd-bio-label">Annotations</span>'+bioChips.join('')+'</div>';
  }

  d.innerHTML=
    '<div class="vd-ref">'+esc(node.reference||node.ui_name)+'</div>'+
    (tagHtml?'<div class="vd-tags">'+tagHtml+'</div>':'')+
    (txt?'<div class="vd-text">'+esc(txt)+'</div>':'')+
    (heb?'<div class="vd-heb">'+esc(heb)+'</div>':'')+
    (note?'<div class="vd-note">'+esc(note)+'</div>':'')+
    bioSection+
    '<div class="vd-nav">'+
      '<button class="vd-btn" onclick="verseStep(-1)">&#8592; Prev</button>'+
      '<button class="vd-btn" onclick="verseStep(1)">Next &#8594;</button>'+
    '</div>';
}

async function verseStep(dir){
  if(!curNode || navHist.length<2) return;
  const parentUid = navHist[navHist.length-2];
  const parent = await api('/api/node/'+parentUid);
  const kids = parent.children||[];
  const idx = kids.findIndex(c=>c.uid===curNode.uid);
  const next = kids[idx+dir];
  if(next) await zoom(next.uid);
}

// lang change
$('sel-lang').addEventListener('change', async ()=>{
  LANG = $('sel-lang').value;
  $('th-lang').textContent = LANG;
  if(mode==='explore' && curNode && curNode.level==='verse'){
    await zoom(curNode.uid, false);
  } else if(mode==='search' && srchState.mode){
    await doSearch(srchState.mode, srchState.q);
  }
});

// ── search ────────────────────────────────────────────────────────────────────
const srchState = {mode:null, q:'', rows:[]};

async function doSearch(smode, q){
  if(!q.trim()) return;
  srchState.mode=smode; srchState.q=q;
  const rows = await api('/api/search',{mode:smode,q,lang:LANG});
  srchState.rows = rows;
  renderSrchRows(rows);
  $('lbl-count').textContent = rows.length+' verse'+(rows.length!==1?'s':'');
  if(rows.length) selSrchRow(0);
}

function renderSrchRows(rows){
  const tbody=$('tbl-body');
  tbody.innerHTML='';
  if(!rows.length){
    tbody.innerHTML='<tr><td colspan="3" class="placeholder">No results.</td></tr>';
    return;
  }
  const frag=document.createDocumentFragment();
  rows.forEach((row,i)=>{
    const tr=document.createElement('tr');
    tr.className=i%2?'odd':'even';
    tr.dataset.idx=i;
    const tdL=document.createElement('td'); tdL.className='c-lang';
    tdL.innerHTML='<strong style="font-size:11px;color:var(--dim)">'+esc(row.ref||'')+'</strong><br>'+esc(row.lang_text||'');
    const tdH=document.createElement('td'); tdH.className='c-heb';  tdH.textContent=row.heb_text||'';
    const tdC=document.createElement('td'); tdC.className='c-cat';
    tdC.innerHTML=[row.cat].filter(Boolean).map(t=>'<span class="td-cat-chip">'+esc(t)+'</span>').join('');
    tr.append(tdL,tdH,tdC);
    tr.addEventListener('click',()=>selSrchRow(i));
    frag.appendChild(tr);
  });
  tbody.appendChild(frag);
}

function selSrchRow(idx){
  $('tbl-body').querySelectorAll('tr.sel').forEach(r=>r.classList.remove('sel'));
  const tr=$('tbl-body').querySelector('tr[data-idx="'+idx+'"]');
  if(tr){ tr.classList.add('sel'); tr.scrollIntoView({block:'nearest'}); }
}

$('sel-book').addEventListener('change', async()=>{
  const v=$('sel-book').value; if(!v) return;
  setActiveTab(null); showPanel('results'); $('inp-search').value='';
  await doSearch('book',v);
});
$('inp-search').addEventListener('input', debounce(async()=>{
  const q=$('inp-search').value.trim();
  if(!q){ $('lbl-count').textContent=''; return; }
  setActiveTab(null); showPanel('results'); $('sel-book').value='';
  await doSearch('search',q);
},400));

// ── category tab bar / overview / reference panels ─────────────────────────────
let META = null;
let GEMATRIA = null;

function showPanel(which){
  $('panel-overview').hidden = which!=='overview';
  $('panel-reference').hidden = which!=='reference';
  $('panel-results').hidden  = which!=='results';
}

function setActiveTab(key){
  document.querySelectorAll('.cat-tab').forEach(b=>b.classList.toggle('active', b.dataset.key===key));
}

async function selectOverview(){
  setActiveTab('overview');
  $('sel-book').value=''; $('inp-search').value=''; $('lbl-count').textContent='';
  showPanel('overview');
  renderOverview();
}

async function selectReference(kind){
  setActiveTab(kind);
  $('sel-book').value=''; $('inp-search').value=''; $('lbl-count').textContent='';
  showPanel('reference');
  if(!GEMATRIA) GEMATRIA = await api('/api/gematria');
  renderReference(kind);
}

async function selectCategory(name){
  setActiveTab(name);
  $('sel-book').value=''; $('inp-search').value='';
  showPanel('results');
  await doSearch('category', name);
}

function renderOverview(){
  const cats = META.categories;
  const total = cats.reduce((s,c)=>s+c.count,0);
  const rows = [];
  for(let n=1; n<=META.total_book_chapters; n++){
    const cat = cats.find(c=>c.chapter===n);
    if(cat){
      rows.push('<div class="ov-row" data-key="'+esc(cat.name)+'"><span class="ov-num">'+n+'.</span>'+
        '<span class="ov-title">'+esc(cat.nice_name)+'</span>'+
        '<span class="ov-badge">'+cat.count+' verses</span></div>');
    } else {
      const title = n===28 ? 'What About Jesus?' : '—';
      const label = n===28 ? 'not a flaw category' : 'not catalogued';
      rows.push('<div class="ov-row pending"><span class="ov-num">'+n+'.</span>'+
        '<span class="ov-title">'+esc(title)+'</span>'+
        '<span class="ov-badge muted">'+label+'</span></div>');
    }
  }
  $('panel-overview').innerHTML =
    '<div class="ov-wrap">'+
      '<div class="ov-lede">A catalogue of Bible verses supporting each chapter of '+
      '<em>God: The Most Unpleasant Character in All Fiction</em> by Dan Barker (2016), '+
      'cross-referenced against '+META.languages.length+' translations and the Hebrew text behind them.</div>'+
      '<div class="ov-stats">'+
        '<div class="ov-stat"><div class="ov-stat-n">'+cats.length+'/'+META.total_book_chapters+'</div><div class="ov-stat-l">chapters catalogued</div></div>'+
        '<div class="ov-stat"><div class="ov-stat-n">'+total+'</div><div class="ov-stat-l">verses collected</div></div>'+
        '<div class="ov-stat"><div class="ov-stat-n">'+META.languages.length+'</div><div class="ov-stat-l">translations on hand</div></div>'+
      '</div>'+
      '<div class="ov-list">'+rows.join('')+'</div>'+
    '</div>';
  $('panel-overview').querySelectorAll('.ov-row[data-key]').forEach(el=>{
    el.addEventListener('click', ()=>selectCategory(el.dataset.key));
  });
}

function renderReference(kind){
  if(kind==='gematria'){
    $('panel-reference').innerHTML =
      '<div class="ref-wrap"><table><thead><tr><th>Value</th><th>Hebrew</th><th>Say</th><th>Unicode</th></tr></thead><tbody>'+
      GEMATRIA.numerals.map(n=>'<tr><td>'+n.value+'</td><td class="c-heb-ref">'+esc(n.hebrew)+'</td><td>'+esc(n.say)+
        '</td><td style="font-size:10px;color:var(--dim)">'+n.unicode.join(' ')+'</td></tr>').join('')+
      '</tbody></table></div>';
  } else {
    $('panel-reference').innerHTML =
      '<div class="ref-wrap"><table><thead><tr><th>Book</th><th>Hebrew</th><th>Say</th></tr></thead><tbody>'+
      GEMATRIA.books.map(b=>'<tr><td>'+esc(b.name)+'</td><td class="c-heb-ref">'+esc(b.hebrew)+'</td><td>'+esc(b.say)+'</td></tr>').join('')+
      '</tbody></table></div>';
  }
}

function renderCatTabbar(){
  let html = '<button class="cat-tab" data-key="overview">Overview</button>';
  META.categories.forEach(c=>{
    html += '<button class="cat-tab" data-key="'+esc(c.name)+'">'+
      '<span class="ct-n">'+(c.chapter??'')+'</span>'+esc(c.nice_name)+
      '<span class="ct-c">'+c.count+'</span></button>';
  });
  html += '<span class="cat-tab-sep"></span>';
  html += '<button class="cat-tab" data-key="gematria">Gematria</button>';
  html += '<button class="cat-tab" data-key="books">Book names</button>';
  const bar = $('cat-tabbar');
  bar.innerHTML = html;
  bar.querySelectorAll('.cat-tab').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const key = btn.dataset.key;
      if(key==='overview') selectOverview();
      else if(key==='gematria' || key==='books') selectReference(key);
      else selectCategory(key);
    });
  });
}

// ── init ──────────────────────────────────────────────────────────────────────
async function init(){
  META = await api('/api/meta');

  META.languages.forEach(l=>{
    const o=new Option(l,l);
    if(l===META.default_lang) o.selected=true;
    $('sel-lang').appendChild(o);
  });
  LANG = META.default_lang;
  $('th-lang').textContent = LANG;

  $('sel-book').appendChild(new Option('— Book —',''));
  META.book_options.forEach(b=>$('sel-book').appendChild(new Option(b,b)));

  renderCatTabbar();
  await selectOverview();
}

init().catch(err=>{
  $('panel-overview').hidden = false;
  $('panel-overview').innerHTML='<p style="color:var(--dim);padding:20px;font-style:italic">Error loading: '+esc(err.message)+'</p>';
  console.error(err);
});
</script>
</body>
</html>
"""

# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """Parse CLI args and run the Flask development server.

    Supports ``--port`` (default 5000) and ``--no-browser`` to skip
    auto-opening the default browser.
    """
    parser = argparse.ArgumentParser(
        description='God: The Most Unpleasant Character — web UI')
    parser.add_argument('--port', type=int, default=5000,
                        help='Port to listen on (default 5000)')
    parser.add_argument('--no-browser', action='store_true',
                        help='Do not open browser automatically')
    args = parser.parse_args()

    url = f'http://localhost:{args.port}'
    print(f'  Serving at {url}')
    print(f'  Categories: {len(CATEGORIES)}')
    print(f'  Bibles: {len(BIBLES)}')
    print(f'  Unit tree: {sum(1 for _ in UNIT_TREE.walk())} nodes')
    print(f'  Press Ctrl+C to stop.')

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
