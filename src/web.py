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

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
BIBLES_DIR   = os.path.join(BASE_DIR, 'bibles')
CATS_DIR     = os.path.join(BASE_DIR, 'categories')
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

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

    he_tanakh.json embeds raw Sefaria HTML markup in its verse text (see
    hebrew.clean_verse_text); it's cleaned here, once, at load time.

    Returns:
        A dict mapping translation code (filename without ``.json``) to its
        parsed book list.
    """
    import hebrew
    bibles: dict[str, list] = {}
    for fname in sorted(os.listdir(BIBLES_DIR)):
        if not fname.endswith('.json'):
            continue
        path = os.path.join(BIBLES_DIR, fname)
        with open(path, encoding='utf-8-sig') as f:
            data = json.load(f)
        if fname == 'he_tanakh.json':
            for book in data:
                book['chapters'] = [
                    [hebrew.clean_verse_text(v) for v in ch]
                    for ch in book['chapters']
                ]
        bibles[fname[:-5]] = data
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


def _format_heb_ref(book: str, chapter: int, verses) -> str:
    """Format a Bible reference using Hebrew book name and gematria numerals.

    Same shape as `_format_ref` (book chapter:verse[–verse]), but with the
    book name looked up in hebrew.BOOKS and the numbers converted via
    hebrew.to_hebrew_number() instead of left as Arabic digits. Falls back
    to the English book name for NT epistles/Revelation, which hebrew.BOOKS
    doesn't cover.

    Args:
        book: English book name, e.g. ``'Genesis'``.
        chapter: Chapter number.
        verses: A single verse number or a list of verse numbers.

    Returns:
        e.g. ``'בראשית א:א'`` for Genesis 1:1.
    """
    import hebrew
    heb_book = hebrew.BOOKS.get(book)
    name = heb_book.hebrew if heb_book else book
    vv = _normalise_verses(verses)
    ch = hebrew.to_hebrew_number(chapter)
    if len(vv) == 1:
        return f'{name} {ch}:{hebrew.to_hebrew_number(vv[0])}'
    return f'{name} {ch}:{hebrew.to_hebrew_number(vv[0])}–{hebrew.to_hebrew_number(vv[-1])}'


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
        heb_text, heb_reference)`` tuples.
    """
    rows: list[tuple] = []

    def _add(cat: dict, entry: dict) -> None:
        """Append one (category, ref, note, lang_text, heb_text, heb_ref) row for `entry`."""
        ref    = _format_ref(entry['book'], entry['chapter'], entry['verse'])
        href   = _format_heb_ref(entry['book'], entry['chapter'], entry['verse'])
        ltext  = _get_text(lang_bible, entry['book'], entry['chapter'], entry['verse'])
        htext  = _get_text(HEB_BIBLE,  entry['book'], entry['chapter'], entry['verse'])
        rows.append((cat['nice_name'], ref, entry.get('notes', ''), ltext, htext, href))

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
            href  = _format_heb_ref(book, chapter, verse)
            ltext = _get_text(lang_bible, book, chapter, [verse])
            htext = _get_text(HEB_BIBLE,  book, chapter, [verse])
            hits  = VERSE_INDEX.get((book.lower(), chapter, verse), [])
            rows.append((
                hits[0]['cat_name'] if hits else '—',
                ref,
                hits[0]['note']     if hits else '(not in any category)',
                ltext,
                htext,
                href,
            ))

    return rows


# ── Flask ─────────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=None)


@app.route('/')
def index():
    """Serve the single-page Explore/Catalogue frontend.

    Read from templates/index.html on every request (rather than caching
    it at import time) so frontend edits show up on a browser refresh
    without needing to restart the server.
    """
    with open(os.path.join(TEMPLATE_DIR, 'index.html'), encoding='utf-8-sig') as f:
        html = f.read()
    return Response(html, mimetype='text/html; charset=utf-8')


@app.route('/api/meta')
def api_meta():
    """Return catalogue metadata: categories, languages, and book options.

    Returns:
        A Flask JSON response consumed by the frontend's `init()` to
        populate the language selector, book filter, and category tab bar.
    """
    import hebrew
    cats = sorted(
        CATEGORIES.values(),
        key=lambda c: (CHAPTER_NUMBERS.get(c['name'], 999), c['name']),
    )
    return jsonify({
        'categories': [{
            'name':      c['name'],
            'nice_name': c['nice_name'],
            'heb_name':  hebrew.category_hebrew(c['name']),
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


@app.route('/api/timeline')
def api_timeline():
    """Return per-book category breakdowns for the Timeline view.

    Aggregates every catalogued verse by its KJV book (resolved through
    NAME_MAP so book-name aliases like 'Psalm'/'Psalms' collapse together),
    in canonical Genesis-to-Revelation order.

    Returns:
        A Flask JSON response: 'books' is a list of ``{name, heb_name,
        abbrev, index, testament, total, categories: [{name, nice_name,
        count}, ...]}`` entries, one per KJV book (heb_name is '' for the
        NT epistles/Revelation, which hebrew.BOOKS doesn't cover);
        'categories' echoes the api_meta() category list (name/nice_name/
        chapter) for consistent colour assignment on the frontend.
    """
    import hebrew
    per_book: dict[int, dict[str, int]] = {}
    for cat in CATEGORIES.values():
        for entry in cat['verses'].values():
            idx = NAME_MAP.get(entry['book'].lower())
            if idx is None:
                continue
            counts = per_book.setdefault(idx, {})
            counts[cat['name']] = counts.get(cat['name'], 0) + 1

    cat_chapter = {n: CHAPTER_NUMBERS.get(n, 999) for n in CATEGORIES}

    books = []
    for i, book in enumerate(_KJV):
        counts = per_book.get(i, {})
        cats = sorted(
            ({'name': n, 'nice_name': CATEGORIES[n]['nice_name'], 'count': c}
             for n, c in counts.items()),
            key=lambda x: cat_chapter[x['name']],
        )
        heb_book = hebrew.BOOKS.get(book['name'])
        books.append({
            'name':       book['name'],
            'heb_name':   heb_book.hebrew if heb_book else '',
            'abbrev':     book['abbrev'],
            'index':      i,
            'testament':  'OT' if i < 39 else 'NT',
            'total':      sum(counts.values()),
            'categories': cats,
        })

    return jsonify({
        'books': books,
        'categories': sorted(
            [{'name': n, 'nice_name': CATEGORIES[n]['nice_name'],
              'chapter': CHAPTER_NUMBERS.get(n)} for n in CATEGORIES],
            key=lambda c: (c['chapter'] or 999, c['name']),
        ),
    })


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
        A Flask JSON response: a list of row dicts with cat/ref/heb_ref/
        note/lang_text/heb_text plus bio_name/chimo_name annotations.
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
        'heb_ref':   r[5],
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
    r     = rows[0] if rows else ('—', f'{book} {ch}:{vs}', '(not in any category)', '', '',
                                   _format_heb_ref(book, ch, vs))
    idx   = NAME_MAP.get(book.lower())
    abbrev = _KJV[idx]['abbrev'].upper() if idx is not None else ''
    node  = UNIT_TREE.find(f'{abbrev}.{ch}.{vs}') if abbrev else None
    return jsonify({
        'cat':        r[0],
        'ref':        r[1],
        'note':       r[2],
        'lang_text':  r[3],
        'heb_text':   r[4],
        'heb_ref':    r[5],
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
