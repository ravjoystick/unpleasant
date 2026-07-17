"""God: The Most Unpleasant Character in All Fiction — Search Tool.

A Tkinter desktop app for searching the catalogue by category, book, or
free text, with side-by-side translation and Hebrew columns plus a verse
navigator and bio/chemo annotation panel.

Usage:
    python src/ui.py
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import os, ast, json
from unit import build_bible_tree

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
BIBLES_DIR = os.path.join(BASE_DIR, 'bibles')
CATS_DIR   = os.path.join(BASE_DIR, 'categories')

TITLE = 'God: The Most Unpleasant Character in All Fiction'

# ── palette ──────────────────────────────────────────────────────────────────
BG        = '#0d0d1a'
PANEL     = '#12122a'
PANEL2    = '#1a1a35'
ROW_ODD   = '#1a1a35'
ROW_EVEN  = '#12122a'
ACCENT    = '#c0392b'
ACCENT2   = '#8e44ad'
TEXT      = '#e8e8f0'
DIM       = '#7777aa'
HEADING   = '#ffffff'
INFO_BG   = '#0f0f22'
LABEL_FG  = '#5555aa'
NAV_BG    = '#0a0a18'

# ── data loading ─────────────────────────────────────────────────────────────

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
                    'note': entry.get('notes', ''),
                })
    return idx


CATEGORIES  = _load_categories()
BIBLES      = _load_bibles()

_KJV        = BIBLES.get('en_kjv', next(iter(BIBLES.values())))
NAME_MAP    = _build_name_map(_KJV)
HEB_BIBLE   = BIBLES.get('he_modern', BIBLES.get('he_aleppo', _KJV))
VERSE_INDEX = _build_verse_index(CATEGORIES)
UNIT_TREE   = build_bible_tree(_KJV, CATEGORIES, HEB_BIBLE, NAME_MAP)

# Book list ordered as in KJV (index → name)
ALL_BOOKS    = [b['name'] for b in _KJV]
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
    """Build result table rows for a given search mode and selection.

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
        # selection is "book|chapter|verse"
        parts = selection.split('|')
        if len(parts) == 3:
            book, chapter, verse = parts[0], int(parts[1]), int(parts[2])
            ref   = f'{book} {chapter}:{verse}'
            ltext = _get_text(lang_bible, book, chapter, [verse])
            htext = _get_text(HEB_BIBLE,  book, chapter, [verse])
            hits  = VERSE_INDEX.get((book.lower(), chapter, verse), [])
            cat_name = hits[0]['cat_name'] if hits else '—'
            note     = hits[0]['note']     if hits else '—'
            rows.append((cat_name, ref, note, ltext, htext))

    return rows

# ── UI ────────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    """The desktop search window: controls, info panel, verse navigator, and results table."""

    def __init__(self) -> None:
        """Configure the window and build the full widget tree."""
        super().__init__()
        self.title(TITLE)
        self.geometry('1400x860')
        self.minsize(900, 620)
        self.configure(bg=BG)
        self._lang_bible  = _KJV
        self._rows: list[tuple] = []
        self._after_id: str | None = None
        self._nav_updating = False   # guard against cascading nav callbacks
        self._setup_styles()
        self._build()

    # ── styles ────────────────────────────────────────────────────────────────

    def _setup_styles(self) -> None:
        """Configure the ttk theme and all custom widget styles/colours."""
        s = ttk.Style(self)
        s.theme_use('clam')

        s.configure('.',               background=BG, foreground=TEXT,
                                       font=('Segoe UI', 10), borderwidth=0)
        s.configure('TFrame',          background=BG)
        s.configure('Panel.TFrame',    background=PANEL)
        s.configure('Info.TFrame',     background=INFO_BG)
        s.configure('Nav.TFrame',      background=NAV_BG)

        s.configure('TLabel',          background=BG,      foreground=TEXT)
        s.configure('Title.TLabel',    background=BG,      foreground=ACCENT,
                                       font=('Segoe UI', 13, 'bold'))
        s.configure('FieldKey.TLabel', background=INFO_BG, foreground=LABEL_FG,
                                       font=('Segoe UI', 8, 'bold'))
        s.configure('FieldVal.TLabel', background=INFO_BG, foreground=TEXT,
                                       font=('Segoe UI', 10))
        s.configure('FieldNote.TLabel', background=INFO_BG, foreground=DIM,
                                        font=('Segoe UI', 10, 'italic'))
        s.configure('FieldBio.TLabel',  background=INFO_BG, foreground='#8ecfa0',
                                        font=('Segoe UI', 9, 'italic'))
        s.configure('FieldChem.TLabel', background=INFO_BG, foreground='#a0c4ef',
                                        font=('Segoe UI', 9))
        s.configure('NavKey.TLabel',   background=NAV_BG,  foreground=LABEL_FG,
                                       font=('Segoe UI', 8, 'bold'))
        s.configure('Count.TLabel',    background=PANEL,   foreground=DIM,
                                       font=('Segoe UI', 9))

        s.configure('TCombobox',       fieldbackground=PANEL, background=PANEL,
                                       foreground=TEXT, arrowcolor=ACCENT,
                                       selectbackground=ACCENT, selectforeground=HEADING)
        s.map('TCombobox',             fieldbackground=[('readonly', PANEL)])

        s.configure('Nav.TCombobox',   fieldbackground=NAV_BG, background=NAV_BG,
                                       foreground=TEXT, arrowcolor=ACCENT2,
                                       selectbackground=ACCENT2, selectforeground=HEADING)
        s.map('Nav.TCombobox',         fieldbackground=[('readonly', NAV_BG)])

        s.configure('TEntry',          fieldbackground=PANEL, foreground=TEXT,
                                       insertcolor=TEXT, selectbackground=ACCENT)

        s.configure('Treeview',        background=ROW_EVEN, foreground=TEXT,
                                       fieldbackground=ROW_EVEN, rowheight=58,
                                       font=('Segoe UI', 10))
        s.configure('Treeview.Heading',background=PANEL2, foreground=HEADING,
                                       font=('Segoe UI', 10, 'bold'), relief='flat')
        s.map('Treeview',              background=[('selected', ACCENT)],
                                       foreground=[('selected', HEADING)])
        s.map('Treeview.Heading',      background=[('active', ACCENT2)])

        s.configure('TScrollbar',      background=PANEL, troughcolor=BG,
                                       arrowcolor=DIM, borderwidth=0)
        s.map('TScrollbar',            background=[('active', DIM)])

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        """Build the full widget tree: title bar, search controls, info panel,
        verse navigator, and results table."""

        # ── 1. Title bar ─────────────────────────────────────────────────────
        top = ttk.Frame(self)
        top.pack(fill='x', padx=14, pady=(10, 4))

        ttk.Label(top, text=TITLE, style='Title.TLabel').pack(side='left')
        ttk.Label(top, text='Language:').pack(side='right', padx=(0, 4))

        self._lang_var = tk.StringVar(value='en_kjv')
        lang_cb = ttk.Combobox(top, textvariable=self._lang_var,
                               values=LANG_OPTIONS, width=24, state='readonly')
        lang_cb.pack(side='right', padx=(0, 10))
        lang_cb.bind('<<ComboboxSelected>>', self._on_lang_change)

        # ── 2. Search controls ────────────────────────────────────────────────
        ctrl = ttk.Frame(self, style='Panel.TFrame')
        ctrl.pack(fill='x', padx=12, pady=(0, 4))

        pad = dict(padx=(0, 10), pady=8)

        ttk.Label(ctrl, text='Category:', background=PANEL).pack(side='left', padx=(12, 4), pady=8)
        self._cat_var = tk.StringVar()
        cat_cb = ttk.Combobox(ctrl, textvariable=self._cat_var,
                              values=[''] + CAT_OPTIONS, width=22, state='readonly')
        cat_cb.pack(side='left', **pad)
        cat_cb.bind('<<ComboboxSelected>>', lambda _: self._search('category'))

        ttk.Label(ctrl, text='Book:', background=PANEL).pack(side='left', padx=(0, 4))
        self._book_var = tk.StringVar()
        book_cb = ttk.Combobox(ctrl, textvariable=self._book_var,
                               values=[''] + BOOK_OPTIONS, width=22, state='readonly')
        book_cb.pack(side='left', **pad)
        book_cb.bind('<<ComboboxSelected>>', lambda _: self._search('book'))

        ttk.Label(ctrl, text='Search:', background=PANEL).pack(side='left', padx=(0, 4))
        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(ctrl, textvariable=self._search_var, width=28)
        search_entry.pack(side='left', **pad)
        self._search_var.trace_add('write', self._on_search_type)
        search_entry.bind('<Return>', lambda _: self._search('search'))
        search_entry.bind('<Escape>', self._clear_search)

        self._count_var = tk.StringVar(value='')
        ttk.Label(ctrl, textvariable=self._count_var, style='Count.TLabel',
                  background=PANEL).pack(side='right', padx=12)

        # ── 3. Info panel ─────────────────────────────────────────────────────
        info = ttk.Frame(self, style='Info.TFrame')
        info.pack(fill='x', padx=12, pady=(0, 0))

        def _infofield(parent, key: str, var: tk.StringVar,
                       style='FieldVal.TLabel', expand=False):
            """Add one labelled key/value column to the info panel.

            Args:
                parent: The container frame to pack into.
                key: The field's uppercase label, e.g. ``'REFERENCE'``.
                var: The StringVar whose value is displayed.
                style: The ttk style to apply to the value label.
                expand: Whether this column should expand to fill space.
            """
            f = ttk.Frame(parent, style='Info.TFrame')
            f.pack(side='left', fill='x', expand=expand, padx=(10, 12), pady=(4, 6))
            ttk.Label(f, text=key, style='FieldKey.TLabel').pack(anchor='w')
            ttk.Label(f, textvariable=var, style=style,
                      wraplength=380, justify='left').pack(anchor='w')

        self._info_ref   = tk.StringVar(value='—')
        self._info_cat   = tk.StringVar(value='—')
        self._info_note  = tk.StringVar(value='Select a result or navigate to a verse.')
        self._info_bio   = tk.StringVar(value='—')
        self._info_chimo = tk.StringVar(value='—')

        _infofield(info, 'REFERENCE', self._info_ref)
        tk.Frame(info, bg=PANEL2, width=1).pack(side='left', fill='y', pady=4)
        _infofield(info, 'CATEGORY',  self._info_cat)
        tk.Frame(info, bg=PANEL2, width=1).pack(side='left', fill='y', pady=4)
        _infofield(info, 'NOTE', self._info_note,
                   style='FieldNote.TLabel', expand=True)
        tk.Frame(info, bg=PANEL2, width=1).pack(side='left', fill='y', pady=4)
        _infofield(info, 'ORGANISM',  self._info_bio,  style='FieldBio.TLabel')
        tk.Frame(info, bg=PANEL2, width=1).pack(side='left', fill='y', pady=4)
        _infofield(info, 'COMPOUND', self._info_chimo, style='FieldChem.TLabel')

        tk.Frame(self, bg=PANEL2, height=1).pack(fill='x', padx=12)

        # ── 4. Verse navigator ────────────────────────────────────────────────
        nav = ttk.Frame(self, style='Nav.TFrame')
        nav.pack(fill='x', padx=12, pady=(0, 0))

        def _navlabel(text):
            """Add one small uppercase label to the verse-navigator bar."""
            ttk.Label(nav, text=text, style='NavKey.TLabel',
                      background=NAV_BG).pack(side='left', padx=(12, 3), pady=6)

        _navlabel('BOOK')
        self._nav_book_var = tk.StringVar()
        nav_book_cb = ttk.Combobox(nav, textvariable=self._nav_book_var,
                                   values=ALL_BOOKS, width=18,
                                   state='readonly', style='Nav.TCombobox')
        nav_book_cb.pack(side='left', padx=(0, 10), pady=6)
        nav_book_cb.bind('<<ComboboxSelected>>', self._on_nav_book)

        _navlabel('CHAPTER')
        self._nav_ch_var = tk.StringVar()
        self._nav_ch_cb  = ttk.Combobox(nav, textvariable=self._nav_ch_var,
                                         values=[], width=6,
                                         state='readonly', style='Nav.TCombobox')
        self._nav_ch_cb.pack(side='left', padx=(0, 10), pady=6)
        self._nav_ch_cb.bind('<<ComboboxSelected>>', self._on_nav_chapter)

        _navlabel('VERSE')
        self._nav_vs_var = tk.StringVar()
        self._nav_vs_cb  = ttk.Combobox(nav, textvariable=self._nav_vs_var,
                                         values=[], width=6,
                                         state='readonly', style='Nav.TCombobox')
        self._nav_vs_cb.pack(side='left', padx=(0, 10), pady=6)
        self._nav_vs_cb.bind('<<ComboboxSelected>>', self._on_nav_verse)

        # mode indicator + back-to-group button
        self._nav_mode_var = tk.StringVar(value='')
        ttk.Label(nav, textvariable=self._nav_mode_var,
                  background=NAV_BG, foreground=DIM,
                  font=('Segoe UI', 9, 'italic')).pack(side='left', padx=(8, 0))

        self._back_btn = tk.Button(
            nav, text='◀  Show group', relief='flat',
            bg=PANEL2, fg=DIM, activebackground=ACCENT2, activeforeground=HEADING,
            font=('Segoe UI', 9), cursor='hand2', state='disabled',
            command=self._show_group,
        )
        self._back_btn.pack(side='right', padx=12, pady=6)

        tk.Frame(self, bg=PANEL2, height=1).pack(fill='x', padx=12)

        # ── 5. Main table ─────────────────────────────────────────────────────
        table_frame = ttk.Frame(self, style='Panel.TFrame')
        table_frame.pack(fill='both', expand=True, padx=12, pady=(3, 4))

        self._tree = ttk.Treeview(table_frame, columns=('lang', 'hebrew'),
                                  show='headings', selectmode='browse')

        self._tree.heading('lang',   text='en_kjv', anchor='w')
        self._tree.heading('hebrew', text='עברית',  anchor='e')
        self._tree.column('lang',   width=720, minwidth=300, stretch=True,  anchor='w')
        self._tree.column('hebrew', width=420, minwidth=160, stretch=True,  anchor='e')

        self._tree.tag_configure('odd',  background=ROW_ODD)
        self._tree.tag_configure('even', background=ROW_EVEN)
        self._tree.tag_configure('solo', background='#1e0a2e')  # single-verse tint

        vsb = ttk.Scrollbar(table_frame, orient='vertical',   command=self._tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient='horizontal', command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self._tree.bind('<<TreeviewSelect>>', self._on_select)

    # ── nav helpers ───────────────────────────────────────────────────────────

    def _set_nav(self, book: str, chapter: int, verse: int) -> None:
        """Silently update all three nav dropdowns without firing callbacks.

        Args:
            book: Book name to select.
            chapter: Chapter number to select.
            verse: Verse number to select.
        """
        self._nav_updating = True
        try:
            self._nav_book_var.set(book)
            # chapters
            n_ch = _chapter_count(book)
            self._nav_ch_cb.configure(values=list(range(1, n_ch + 1)))
            self._nav_ch_var.set(str(chapter))
            # verses
            n_vs = _verse_count(book, chapter)
            self._nav_vs_cb.configure(values=list(range(1, n_vs + 1)))
            self._nav_vs_var.set(str(verse))
        finally:
            self._nav_updating = False

    def _nav_book_from_ref(self, ref: str) -> tuple[str, int, int]:
        """Parse a reference string into its (book, chapter, verse) parts.

        Args:
            ref: A reference string, e.g. ``'Genesis 1:3'``.

        Returns:
            ``(book, chapter, verse)``, e.g. ``('Genesis', 1, 3)``. Falls
            back to ``(ALL_BOOKS[0], 1, 1)`` if `ref` doesn't parse.
        """
        try:
            parts  = ref.rsplit(' ', 1)
            book   = parts[0]
            cv     = parts[1].split(':')
            ch, vs = int(cv[0]), int(cv[1].split('–')[0])
            return book, ch, vs
        except Exception:
            return ALL_BOOKS[0], 1, 1

    # ── event handlers ────────────────────────────────────────────────────────

    def _on_lang_change(self, _=None) -> None:
        """Re-run whichever search/nav is active in the newly selected language."""
        key = self._lang_var.get()
        self._lang_bible = BIBLES.get(key, _KJV)
        self._tree.heading('lang', text=key)
        if self._cat_var.get():
            self._search('category')
        elif self._book_var.get():
            self._search('book')
        elif self._search_var.get().strip():
            self._search('search')
        elif self._nav_book_var.get():
            self._on_nav_verse()      # re-render current single verse

    def _on_search_type(self, *_) -> None:
        """Debounce free-text search input: reschedule the search 400ms after typing stops."""
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(400, self._trigger_text_search)

    def _trigger_text_search(self) -> None:
        """Run the debounced free-text search, clearing the category/book filters."""
        self._after_id = None
        if self._search_var.get().strip():
            self._cat_var.set('')
            self._book_var.set('')
            self._search('search')

    def _clear_search(self, _=None) -> None:
        """Clear the search box and reset the results table and info panel."""
        self._search_var.set('')
        self._rows = []
        self._populate_table([])
        self._count_var.set('')
        self._reset_info()

    # ── nav callbacks ─────────────────────────────────────────────────────────

    def _on_nav_book(self, _=None) -> None:
        """Reset chapter/verse to 1 for the newly selected book and show that verse."""
        if self._nav_updating:
            return
        book = self._nav_book_var.get()
        if not book:
            return
        n_ch = _chapter_count(book)
        self._nav_ch_cb.configure(values=list(range(1, n_ch + 1)))
        self._nav_ch_var.set('1')
        n_vs = _verse_count(book, 1)
        self._nav_vs_cb.configure(values=list(range(1, n_vs + 1)))
        self._nav_vs_var.set('1')
        self._show_single_verse()

    def _on_nav_chapter(self, _=None) -> None:
        """Reset verse to 1 for the newly selected chapter and show that verse."""
        if self._nav_updating:
            return
        book = self._nav_book_var.get()
        ch   = self._nav_ch_var.get()
        if not book or not ch:
            return
        n_vs = _verse_count(book, int(ch))
        self._nav_vs_cb.configure(values=list(range(1, n_vs + 1)))
        self._nav_vs_var.set('1')
        self._show_single_verse()

    def _on_nav_verse(self, _=None) -> None:
        """Show the newly selected verse."""
        if self._nav_updating:
            return
        self._show_single_verse()

    def _show_single_verse(self) -> None:
        """Look up and display the verse currently selected in the nav bar."""
        book = self._nav_book_var.get()
        ch   = self._nav_ch_var.get()
        vs   = self._nav_vs_var.get()
        if not (book and ch and vs):
            return
        selection = f'{book}|{ch}|{vs}'
        rows = _build_rows('verse', selection, self._lang_bible)
        self._populate_table(rows, solo=True)
        if rows:
            cat_name, ref, note, _, _ = rows[0]
            self._info_ref.set(ref)
            self._info_cat.set(cat_name)
            self._info_note.set(note if note and note != '—' else
                                '(verse not in any category)')
            self._set_bio_chimo(ref)
        self._nav_mode_var.set('single verse')
        self._back_btn.configure(state='normal' if self._rows else 'disabled')
        self._count_var.set('1 verse')

    def _show_group(self) -> None:
        """Restore the last group search results."""
        if not self._rows:
            return
        self._populate_table(self._rows)
        self._nav_mode_var.set('')
        self._back_btn.configure(state='disabled')
        self._count_var.set(f'{len(self._rows)} verse{"s" if len(self._rows) != 1 else ""}')
        children = self._tree.get_children()
        if children:
            self._tree.selection_set(children[0])
            self._tree.focus(children[0])

    # ── search ────────────────────────────────────────────────────────────────

    def _search(self, mode: str) -> None:
        """Run a search for the given mode using its associated control's value.

        Args:
            mode: One of ``'search'``, ``'category'``, ``'book'``. Reads the
                selection from the matching control (search box, category
                dropdown, or book dropdown) and clears the other two.
        """
        if mode == 'search':
            selection = self._search_var.get()
        elif mode == 'category':
            selection = self._cat_var.get()
            self._book_var.set('')
            self._search_var.set('')
        else:
            selection = self._book_var.get()
            self._cat_var.set('')
            self._search_var.set('')

        if not selection.strip():
            return

        self._rows = _build_rows(mode, selection, self._lang_bible)
        self._populate_table(self._rows)
        self._reset_info()
        self._nav_mode_var.set('')
        self._back_btn.configure(state='disabled')

        n = len(self._rows)
        self._count_var.set(f'{n} verse{"s" if n != 1 else ""}')

        children = self._tree.get_children()
        if children:
            self._tree.selection_set(children[0])
            self._tree.focus(children[0])
            self._tree.see(children[0])

    def _populate_table(self, rows: list[tuple], solo: bool = False) -> None:
        """Replace the results table's rows with truncated previews of `rows`.

        Args:
            rows: Row tuples as returned by `_build_rows`.
            solo: If True, tag every row 'solo' (single-verse tint) instead
                of alternating odd/even striping.
        """
        self._tree.delete(*self._tree.get_children())
        for i, (_, _, _, ltext, htext) in enumerate(rows):
            if solo:
                tag = 'solo'
            else:
                tag = 'odd' if i % 2 else 'even'
            lshort = ltext[:160] + '…' if len(ltext) > 160 else ltext
            hshort = htext[:100] + '…' if len(htext) > 100 else htext
            self._tree.insert('', 'end', values=(lshort, hshort), tags=(tag,))

    # ── row selection ─────────────────────────────────────────────────────────

    def _on_select(self, _=None) -> None:
        """Update the info panel and nav bar to match the newly selected table row."""
        sel = self._tree.selection()
        if not sel:
            return
        idx = self._tree.index(sel[0])

        # figure out which row list we're looking at
        children = self._tree.get_children()
        tags = self._tree.item(sel[0], 'tags')
        if 'solo' in tags:
            # single-verse mode — info already set; just keep nav in sync
            return

        if idx >= len(self._rows):
            return
        cat_name, ref, note, _, _ = self._rows[idx]
        self._info_ref.set(ref)
        self._info_cat.set(cat_name)
        self._info_note.set(note or '—')
        self._set_bio_chimo(ref)

        # drive the nav bar to match, suppressing callbacks
        book, ch, vs = self._nav_book_from_ref(ref)
        self._set_nav(book, ch, vs)
        self._nav_mode_var.set('')

    def _set_bio_chimo(self, ref: str) -> None:
        """Populate the organism / compound info-panel labels for a verse.

        Args:
            ref: A reference string, e.g. ``'Genesis 1:1'``. Looked up in
                UNIT_TREE; labels are set to '—' if `ref` doesn't parse or
                has no matching node.
        """
        import re
        m = re.match(r'^(.+?)\s+(\d+):(\d+)', ref)
        if not m:
            self._info_bio.set('—'); self._info_chimo.set('—'); return
        book, ch, vs = m.group(1), int(m.group(2)), int(m.group(3))
        idx = NAME_MAP.get(book.lower())
        if idx is None:
            self._info_bio.set('—'); self._info_chimo.set('—'); return
        abbrev = _KJV[idx]['abbrev'].upper()
        node = UNIT_TREE.find(f'{abbrev}.{ch}.{vs}')
        self._info_bio.set(node.bio_name   if node and node.bio_name   else '—')
        self._info_chimo.set(node.chimo_name if node and node.chimo_name else '—')

    def _reset_info(self) -> None:
        """Reset the info panel fields to their placeholder values."""
        self._info_ref.set('—')
        self._info_cat.set('—')
        self._info_note.set('Click a row to see details.')
        self._info_bio.set('—')
        self._info_chimo.set('—')


if __name__ == '__main__':
    app = App()
    app.mainloop()
