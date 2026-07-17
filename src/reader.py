"""
God: The Most Unpleasant Character in All Fiction — Reader
A calm, book-like viewer: categories are the table of contents,
each category reads like its own little book you page through.

Run:  python src/reader.py
      python src/reader.py --port 8080
      python src/reader.py --no-browser
"""
from __future__ import annotations
import os, ast, json, re, argparse, threading, webbrowser
from flask import Flask, jsonify, Response

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
BIBLES_DIR = os.path.join(BASE_DIR, 'bibles')
CATS_DIR   = os.path.join(BASE_DIR, 'categories')

# ── data loading ────────────────────────────────────────────────────────────

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


def _load_bible(fname: str) -> list:
    """Load a single Bible translation JSON file.

    Args:
        fname: Filename within BIBLES_DIR, e.g. ``'en_kjv.json'``.

    Returns:
        The parsed book list for that translation.
    """
    with open(os.path.join(BIBLES_DIR, fname), encoding='utf-8-sig') as f:
        return json.load(f)


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


CATEGORIES = _load_categories()
CAT_ORDER  = sorted(CATEGORIES, key=lambda k: CATEGORIES[k]['nice_name'])
KJV        = _load_bible('en_kjv.json')
HEB_BIBLE  = _load_bible('he_modern.json')
NAME_MAP   = _build_name_map(KJV)

# ── helpers ─────────────────────────────────────────────────────────────────

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


def _strip_translator_notes(text: str) -> str:
    """Clean the {curly-brace} annotations embedded in KJV source text.

    KJV text embeds two kinds of annotations: plain supplied words like
    ``{was}`` (needed for the sentence to read — unwrapped in place) and
    marginal notes like ``{continually: Heb. every day}`` (asides — dropped
    entirely).

    Args:
        text: Raw KJV verse text, possibly containing {...} annotations.

    Returns:
        The text with supplied words unwrapped and marginal notes removed.
    """
    cleaned = re.sub(r'\s*\{[^{}]*:[^{}]*\}', '', text)
    cleaned = re.sub(r'\{([^{}]*)\}', r'\1', cleaned)
    return re.sub(r'\s{2,}', ' ', cleaned).strip()


def _get_text(bible: list, book: str, chapter: int, verses) -> str:
    """Look up, clean, and concatenate the text of one or more verses.

    Args:
        bible: A book list in the loaded-translation format (see `_load_bible`).
        book: Book name to look up.
        chapter: Chapter number (1-indexed).
        verses: A single verse number or a list of verse numbers.

    Returns:
        The verse text(s) (with translator notes stripped) joined with a
        space, or ``''`` if the book, chapter, or all verses are out of range.
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
            parts.append(_strip_translator_notes(ch[v - 1]))
    return ' '.join(parts)


def _clean_dictionary(text: str) -> list[str]:
    """Reflow a hand-formatted dictionary block into one line per sense.

    Category `dictionary` fields are free-form text with inconsistent line
    wraps and numbered senses (``'1. ... 2. ...'``); this splits them apart.

    Args:
        text: The raw `dictionary` field text.

    Returns:
        One string per numbered sense, in order, with numbering stripped.
    """
    joined = ' '.join(line.strip() for line in text.strip().splitlines() if line.strip())
    parts = re.split(r'\s*\d+\.\s*', joined)
    return [p.strip() for p in parts if p.strip()]


def _cat_summary(name: str) -> dict:
    """Build the compact summary dict shown for one category on the home grid.

    Args:
        name: The category's slug (its `name` field).

    Returns:
        ``{'name', 'nice_name', 'definition' (first sense only), 'count'}``.
    """
    cat = CATEGORIES[name]
    return {
        'name':       cat['name'],
        'nice_name':  cat['nice_name'],
        'definition': _clean_dictionary(cat['dictionary'])[0] if cat['dictionary'].strip() else '',
        'count':      len(cat['verses']),
    }


def _entry_payload(cat_name: str, idx: int) -> dict:
    """Build the full reading-pane payload for one verse entry in a category.

    Args:
        cat_name: The category's slug (its `name` field).
        idx: The entry's key within the category's `verses` dict. Falls
            back to the first entry if `idx` isn't a valid key.

    Returns:
        A dict with position/navigation info (pos, total, prev, next) plus
        the verse's reference, notes, KJV text, and Hebrew text.
    """
    cat     = CATEGORIES[cat_name]
    verses  = cat['verses']
    keys    = sorted(verses.keys())
    if idx not in verses:
        idx = keys[0]
    entry   = verses[idx]
    pos     = keys.index(idx)

    return {
        'cat_name':  cat['name'],
        'nice_name': cat['nice_name'],
        'idx':       idx,
        'pos':       pos + 1,
        'total':     len(keys),
        'prev':      keys[pos - 1] if pos > 0 else None,
        'next':      keys[pos + 1] if pos < len(keys) - 1 else None,
        'ref':       _format_ref(entry['book'], entry['chapter'], entry['verse']),
        'notes':     entry.get('notes', ''),
        'text':      _get_text(KJV, entry['book'], entry['chapter'], entry['verse']),
        'heb_text':  _get_text(HEB_BIBLE, entry['book'], entry['chapter'], entry['verse']),
    }


# ── Flask ───────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=None)


@app.route('/')
def index():
    """Serve the single-page book-like reader frontend."""
    return Response(_HTML, mimetype='text/html; charset=utf-8')


@app.route('/api/categories')
def api_categories():
    """Return the summary list of all categories, for the home grid.

    Returns:
        A Flask JSON response: a list of `_cat_summary` dicts, alphabetical
        by nice_name.
    """
    return jsonify([_cat_summary(n) for n in CAT_ORDER])


@app.route('/api/category/<name>')
def api_category(name: str):
    """Return one category's table of contents.

    Args:
        name: The category's slug (its `name` field).

    Returns:
        A Flask JSON response with the category's name/definition and an
        `entries` list (idx, ref, notes) for its table-of-contents view,
        or a 404 JSON error if `name` is unknown.
    """
    if name not in CATEGORIES:
        return jsonify({'error': 'not found'}), 404
    cat = CATEGORIES[name]
    keys = sorted(cat['verses'].keys())
    entries = []
    for k in keys:
        e = cat['verses'][k]
        entries.append({
            'idx':   k,
            'ref':   _format_ref(e['book'], e['chapter'], e['verse']),
            'notes': e.get('notes', ''),
        })
    return jsonify({
        'name':       cat['name'],
        'nice_name':  cat['nice_name'],
        'definition': _clean_dictionary(cat['dictionary']),
        'entries':    entries,
    })


@app.route('/api/entry/<name>/<int:idx>')
def api_entry(name: str, idx: int):
    """Return one verse entry's full reading-pane payload.

    Args:
        name: The category's slug (its `name` field).
        idx: The entry's key within the category's `verses` dict.

    Returns:
        A Flask JSON response (see `_entry_payload`), or a 404 JSON error
        if `name`/`idx` don't resolve to a known entry.
    """
    if name not in CATEGORIES or idx not in CATEGORIES[name]['verses']:
        return jsonify({'error': 'not found'}), 404
    return jsonify(_entry_payload(name, idx))


# ── embedded frontend ───────────────────────────────────────────────────────

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>God: The Most Unpleasant Character in All Fiction — Reader</title>
<style>
:root{
  --bg:      #faf6ee;
  --paper:   #fffdf8;
  --ink:     #2b2620;
  --dim:     #8a8073;
  --line:    #e8ddc9;
  --accent:  #a8471f;
  --accent2: #6b5b95;
  --chip-bg: #f1e6cf;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:      #1c1a16;
    --paper:   #24211b;
    --ink:     #ece5d6;
    --dim:     #9a9182;
    --line:    #3a352b;
    --accent:  #e2793f;
    --accent2: #b3a0e0;
    --chip-bg: #332c1e;
  }
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  background:var(--bg);color:var(--ink);
  font-family:Georgia,'Iowan Old Style','Palatino Linotype',serif;
  display:flex;flex-direction:column;min-height:100%;
}
.wrap{max-width:760px;margin:0 auto;padding:36px 20px 80px;width:100%;flex:1}
a{color:inherit}

/* header */
.masthead{text-align:center;margin-bottom:34px}
.masthead h1{
  font-size:26px;font-weight:400;letter-spacing:.01em;
  font-style:italic;color:var(--ink);
}
.masthead .rule{width:64px;height:2px;background:var(--accent);margin:14px auto 0;border-radius:2px}

/* breadcrumb / back link */
.crumbs{display:flex;align-items:center;gap:8px;margin-bottom:22px;font-family:system-ui,sans-serif;font-size:13px;color:var(--dim)}
.crumbs a{text-decoration:none;color:var(--accent2);cursor:pointer}
.crumbs a:hover{text-decoration:underline}
.crumbs .sep{color:var(--line)}
.crumbs .cur{color:var(--ink)}

/* category grid */
.cat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:16px}
.cat-card{
  background:var(--paper);border:1px solid var(--line);border-radius:8px;
  padding:18px 18px 16px;cursor:pointer;transition:.15s transform,.15s box-shadow;
  display:flex;flex-direction:column;gap:8px;
}
.cat-card:hover{transform:translateY(-2px);box-shadow:0 6px 18px rgba(0,0,0,.08)}
.cat-title{font-size:19px;font-style:italic;color:var(--accent)}
.cat-def{font-family:system-ui,sans-serif;font-size:12.5px;line-height:1.5;color:var(--dim);flex:1}
.cat-count{
  font-family:system-ui,sans-serif;font-size:11px;color:var(--dim);
  border-top:1px solid var(--line);padding-top:8px;letter-spacing:.03em;
}

/* category (table of contents) view */
.cat-header{margin-bottom:22px}
.cat-header h2{font-size:28px;font-style:italic;color:var(--accent);margin-bottom:8px}
.cat-header .def-list{font-family:system-ui,sans-serif;font-size:13px;color:var(--dim);line-height:1.7}

.toc{border-top:1px solid var(--line)}
.toc-row{
  display:flex;align-items:baseline;gap:14px;padding:13px 4px;
  border-bottom:1px solid var(--line);cursor:pointer;transition:.12s background;
}
.toc-row:hover{background:var(--paper)}
.toc-n{font-family:system-ui,sans-serif;font-size:11px;color:var(--dim);width:20px;flex-shrink:0}
.toc-ref{font-weight:700;color:var(--accent2);white-space:nowrap;flex-shrink:0;font-size:14.5px}
.toc-note{font-size:14.5px;color:var(--ink);line-height:1.4}

/* reading pane */
.page{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:30px 34px;box-shadow:0 2px 10px rgba(0,0,0,.04)}
.page-pos{font-family:system-ui,sans-serif;font-size:11px;color:var(--dim);letter-spacing:.05em;text-transform:uppercase;margin-bottom:10px}
.page-ref{font-size:24px;color:var(--accent);margin-bottom:16px}
.page-note{font-size:14px;font-style:italic;color:var(--dim);margin-bottom:20px;line-height:1.6}
.page-text{font-size:19px;line-height:1.85;color:var(--ink);margin-bottom:20px}
.page-heb{
  font-size:20px;line-height:1.9;color:var(--accent2);direction:rtl;text-align:right;
  font-family:'Noto Serif Hebrew','David','Times New Roman',serif;
  padding-top:18px;border-top:1px solid var(--line);
}
.heb-toggle{
  font-family:system-ui,sans-serif;font-size:12px;color:var(--accent2);
  background:none;border:1px solid var(--line);border-radius:14px;
  padding:4px 12px;cursor:pointer;margin-bottom:4px;
}
.heb-toggle:hover{background:var(--chip-bg)}

/* pager */
.pager{display:flex;align-items:center;justify-content:space-between;margin-top:20px;font-family:system-ui,sans-serif}
.pg-btn{
  background:var(--paper);border:1px solid var(--line);border-radius:6px;
  padding:9px 18px;cursor:pointer;font-size:13px;color:var(--ink);font-family:inherit;
  transition:.15s all;
}
.pg-btn:hover:not(:disabled){border-color:var(--accent);color:var(--accent)}
.pg-btn:disabled{opacity:.35;cursor:default}
.pg-mid{font-size:12px;color:var(--dim)}

.placeholder{text-align:center;color:var(--dim);padding:60px 0;font-style:italic}
</style>
</head>
<body>
<div class="wrap">
  <div class="masthead">
    <h1>God: The Most Unpleasant Character in All Fiction</h1>
    <div class="rule"></div>
  </div>

  <div id="crumbs" class="crumbs"></div>
  <div id="content"></div>
</div>

<script>
'use strict';
function $(id){ return document.getElementById(id); }
function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
async function api(path){
  const r = await fetch(path);
  if(!r.ok) throw new Error(r.statusText);
  return r.json();
}

let showHeb = false;

function renderCrumbs(parts){
  $('crumbs').innerHTML = parts.map((p,i)=>{
    const last = i===parts.length-1;
    if(last) return '<span class="cur">'+esc(p.label)+'</span>';
    return '<a onclick="'+p.action+'">'+esc(p.label)+'</a><span class="sep">/</span>';
  }).join('');
}

async function showHome(){
  renderCrumbs([{label:'Categories'}]);
  const cats = await api('/api/categories');
  const grid = document.createElement('div');
  grid.className = 'cat-grid';
  cats.forEach(c=>{
    const div = document.createElement('div');
    div.className = 'cat-card';
    div.onclick = ()=>showCategory(c.name);
    div.innerHTML =
      '<div class="cat-title">'+esc(c.nice_name)+'</div>'+
      '<div class="cat-def">'+esc(c.definition)+'</div>'+
      '<div class="cat-count">'+c.count+' entr'+(c.count===1?'y':'ies')+'</div>';
    grid.appendChild(div);
  });
  $('content').innerHTML='';
  $('content').appendChild(grid);
}

async function showCategory(name){
  const cat = await api('/api/category/'+encodeURIComponent(name));
  renderCrumbs([
    {label:'Categories', action:'showHome()'},
    {label:cat.nice_name},
  ]);

  const wrap = document.createElement('div');

  const header = document.createElement('div');
  header.className = 'cat-header';
  header.innerHTML =
    '<h2>'+esc(cat.nice_name)+'</h2>'+
    '<div class="def-list">'+cat.definition.map(d=>esc(d)).join('<br>')+'</div>';
  wrap.appendChild(header);

  const toc = document.createElement('div');
  toc.className = 'toc';
  cat.entries.forEach((e,i)=>{
    const row = document.createElement('div');
    row.className = 'toc-row';
    row.onclick = ()=>showEntry(name, e.idx);
    row.innerHTML =
      '<span class="toc-n">'+(i+1)+'</span>'+
      '<span class="toc-ref">'+esc(e.ref)+'</span>'+
      '<span class="toc-note">'+esc(e.notes)+'</span>';
    toc.appendChild(row);
  });
  wrap.appendChild(toc);

  $('content').innerHTML='';
  $('content').appendChild(wrap);
}

async function showEntry(name, idx){
  const e = await api('/api/entry/'+encodeURIComponent(name)+'/'+idx);
  renderCrumbs([
    {label:'Categories', action:'showHome()'},
    {label:e.nice_name,  action:'showCategory("'+name+'")'},
    {label:e.ref},
  ]);

  const page = document.createElement('div');
  page.className = 'page';
  page.innerHTML =
    '<div class="page-pos">'+e.pos+' of '+e.total+'</div>'+
    '<div class="page-ref">'+esc(e.ref)+'</div>'+
    (e.notes?'<div class="page-note">'+esc(e.notes)+'</div>':'')+
    '<div class="page-text">'+esc(e.text||'(text unavailable)')+'</div>'+
    (e.heb_text?'<button class="heb-toggle" id="heb-btn">'+(showHeb?'Hide':'Show')+' Hebrew</button><div class="page-heb" id="heb-block" '+(showHeb?'':'hidden')+'>'+esc(e.heb_text)+'</div>':'');

  const pager = document.createElement('div');
  pager.className = 'pager';
  pager.innerHTML =
    '<button class="pg-btn" id="pg-prev" '+(e.prev===null?'disabled':'')+'>&#8592; Previous</button>'+
    '<span class="pg-mid">'+esc(e.nice_name)+'</span>'+
    '<button class="pg-btn" id="pg-next" '+(e.next===null?'disabled':'')+'>Next &#8594;</button>';

  $('content').innerHTML='';
  $('content').appendChild(page);
  $('content').appendChild(pager);

  if(e.heb_text){
    $('heb-btn').onclick = ()=>{
      showHeb = !showHeb;
      $('heb-block').hidden = !showHeb;
      $('heb-btn').textContent = (showHeb?'Hide':'Show')+' Hebrew';
    };
  }
  if(e.prev!==null) $('pg-prev').onclick = ()=>showEntry(name, e.prev);
  if(e.next!==null) $('pg-next').onclick = ()=>showEntry(name, e.next);

  window.onkeydown = (ev)=>{
    if(ev.key==='ArrowLeft'  && e.prev!==null) showEntry(name, e.prev);
    if(ev.key==='ArrowRight' && e.next!==null) showEntry(name, e.next);
  };
}

showHome().catch(err=>{
  $('content').innerHTML='<p class="placeholder">Error loading: '+esc(err.message)+'</p>';
  console.error(err);
});
</script>
</body>
</html>
"""

# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """Parse CLI args and run the Flask development server.

    Supports ``--port`` (default 5050) and ``--no-browser`` to skip
    auto-opening the default browser.
    """
    parser = argparse.ArgumentParser(description='God: The Most Unpleasant Character — Reader')
    parser.add_argument('--port', type=int, default=5050, help='Port to listen on (default 5050)')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    args = parser.parse_args()

    url = f'http://localhost:{args.port}'
    print(f'  Serving at {url}')
    print(f'  Categories: {len(CATEGORIES)}')

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
