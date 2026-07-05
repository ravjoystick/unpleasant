"""
Downloads Bible translations from api.getbible.net/v2 and saves them
in the same format as the existing files in src/bibles/:
  [ { 'abbrev': 'gn', 'name': 'Genesis', 'chapters': [['v1','v2',...], ...] }, ... ]

Usage:
  python src/fetch_bibles.py
"""

import urllib.request, json, os, time

BIBLES_DIR = os.path.join(os.path.dirname(__file__), 'bibles')
API_BASE   = 'https://api.getbible.net/v2'

# Build abbrev map from existing en_kjv.json (book_nr -> abbrev)
KJV_FILE = os.path.join(BIBLES_DIR, 'en_kjv.json')
_abbrev_map = {}
with open(KJV_FILE, encoding='utf-8-sig') as f:
    _kjv = json.load(f)
for i, book in enumerate(_kjv, start=1):
    _abbrev_map[i] = book['abbrev']


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': 'unpleasant-bible-fetcher/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def convert(api_data):
    """Convert getbible API response to our flat list format."""
    out = []
    for book in api_data['books']:
        nr      = book['nr']
        abbrev  = _abbrev_map.get(nr, book['name'][:3].lower())
        chapters = []
        for ch in sorted(book['chapters'], key=lambda c: c['chapter']):
            verses = [v['text'] for v in sorted(ch['verses'], key=lambda v: v['verse'])]
            chapters.append(verses)
        out.append({'abbrev': abbrev, 'name': book['name'], 'chapters': chapters})
    return out


def download(translation_key, out_filename):
    dest = os.path.join(BIBLES_DIR, out_filename)
    if os.path.exists(dest):
        print(f'  SKIP  {out_filename} (already exists)')
        return True
    url = f'{API_BASE}/{translation_key}.json'
    print(f'  GET   {url}', end=' ... ', flush=True)
    try:
        api_data = fetch(url)
        converted = convert(api_data)
        with open(dest, 'w', encoding='utf-8') as f:
            json.dump(converted, f, ensure_ascii=False)
        size_kb = os.path.getsize(dest) // 1024
        books   = len(converted)
        print(f'OK ({books} books, {size_kb} KB)')
        return True
    except Exception as e:
        print(f'FAILED: {e}')
        return False


# Languages to download: (api_key, output_filename)
# Hebrew is first and mandatory; rest fill language gaps
DOWNLOADS = [
    # Hebrew
    ('aleppo',       'he_aleppo.json'),       # Aleppo Codex (ancient pointed Hebrew, OT only)
    ('codex',        'he_wlc.json'),           # Westminster Leningrad Codex (OT only)
    ('modernhebrew', 'he_modern.json'),        # Modern Hebrew (full Bible)
    # Latin
    ('vulgate',      'la_vulgate.json'),       # Latin Vulgate
    # Italian
    ('giovanni',     'it_giovanni.json'),      # Italian Giovanni Diodati
    # Dutch
    ('statenvertaling', 'nl_statenvertaling.json'),
    # Swedish
    ('swedish',      'sv_swedish.json'),
    # Danish
    ('danish',       'da_danish.json'),
    # Polish
    ('polgdanska',   'pl_gdanska.json'),
    # Hungarian
    ('karoli',       'hu_karoli.json'),
    # Czech
    ('bkr',          'cs_bkr.json'),
    # Turkish
    ('turkish',      'tr_turkish.json'),
    # Ukrainian
    ('ukrogienko',   'uk_ogienko.json'),
    # Swahili
    ('swahili',      'sw_swahili.json'),
    # Japanese
    ('japkougo',     'ja_kougo.json'),
    # Thai
    ('thai',         'th_thai.json'),
    # Tagalog
    ('tagalog',      'tl_tagalog.json'),
    # ASV (another English for completeness)
    ('asv',          'en_asv.json'),
    # Wycliffe (Middle English historical)
    ('wycliffe',     'enm_wycliffe.json'),
    # Ancient Greek NT (Westcott-Hort)
    ('westcotthort', 'grc_wh.json'),
    # Coptic
    ('coptic',       'cop_coptic.json'),
    # Gothic
    ('gothic',       'got_gothic.json'),
]


def main():
    print(f'Bible downloader — saving to: {BIBLES_DIR}')
    print(f'Using abbrev map from en_kjv.json ({len(_abbrev_map)} books)')
    print()

    ok = fail = skip = 0
    for api_key, filename in DOWNLOADS:
        result = download(api_key, filename)
        if os.path.exists(os.path.join(BIBLES_DIR, filename)):
            if 'SKIP' in str(result) or result is True:
                skip_check = not result  # result True = downloaded, was already skipped above
        if result:
            ok += 1
        else:
            fail += 1
        time.sleep(0.4)

    print()
    print(f'Results: {ok} succeeded, {fail} failed')
    print()
    print('All bibles in bibles/:')
    for f in sorted(os.listdir(BIBLES_DIR)):
        if f.endswith('.json'):
            size_kb = os.path.getsize(os.path.join(BIBLES_DIR, f)) // 1024
            print(f'  {f:<35}  {size_kb:>6} KB')


if __name__ == '__main__':
    main()
