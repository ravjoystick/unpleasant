"""Hebrew gematria numerals and biblical book names.

Provides structured lookup tables (NUMERALS, BOOKS) plus conversion
helpers, built at import time from the raw data below. Consumed by
web.py's ``/api/gematria`` route to render the reference tables in the
Explore UI.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class HebrewNumeral:
    """A single Hebrew gematria numeral (1-100).

    Attributes:
        number: The integer value this numeral represents.
        hebrew: The Hebrew numeral string, e.g. ``'יא'``.
        unicode: Unicode codepoints of each Hebrew letter, e.g. ``('U+05D9',)``.
        html: HTML numeric character references for each letter.
        say: Romanised pronunciation, e.g. ``'Yod Alef'``.
    """
    number: int
    hebrew: str
    unicode: tuple[str, ...]
    html: tuple[str, ...]
    say: str

    def __str__(self) -> str:
        """Return the Hebrew numeral string (same as `self.hebrew`)."""
        return self.hebrew


@dataclass(frozen=True)
class HebrewBook:
    """The Hebrew name of a book of the Bible.

    Attributes:
        english: The canonical English book name, e.g. ``'Genesis'``.
        hebrew: The Hebrew book name, e.g. ``'בראשית'``.
        say: Romanised pronunciation, e.g. ``'Bereshit'``.
    """
    english: str
    hebrew: str
    say: str


# ---------------------------------------------------------------------------
# Raw numeral data  (Gematria, 1–100)
# 15 and 16 intentionally use Tet as the tens digit to avoid spelling יה / יו
# ---------------------------------------------------------------------------
_NUMERAL_DATA: list[tuple[int, str, list[str], list[str], str]] = [
    (1,   'א',       ['U+05D0'],              ['&#1488;'],              'Alef'),
    (2,   'ב',       ['U+05D1'],              ['&#1489;'],              'Bet'),
    (3,   'ג',       ['U+05D2'],              ['&#1490;'],              'Gimel'),
    (4,   'ד',       ['U+05D3'],              ['&#1491;'],              'Dalet'),
    (5,   'ה',       ['U+05D4'],              ['&#1492;'],              'He'),
    (6,   'ו',       ['U+05D5'],              ['&#1493;'],              'Vav'),
    (7,   'ז',       ['U+05D6'],              ['&#1494;'],              'Zayin'),
    (8,   'ח',       ['U+05D7'],              ['&#1495;'],              'Het'),
    (9,   'ט',       ['U+05D8'],              ['&#1496;'],              'Tet'),
    (10,  'י',       ['U+05D9'],              ['&#1497;'],              'Yod'),
    (11,  'יא',      ['U+05D9', 'U+05D0'],    ['&#1497;', '&#1488;'],   'Yod Alef'),
    (12,  'יב',      ['U+05D9', 'U+05D1'],    ['&#1497;', '&#1489;'],   'Yod Bet'),
    (13,  'יג',      ['U+05D9', 'U+05D2'],    ['&#1497;', '&#1490;'],   'Yod Gimel'),
    (14,  'יד',      ['U+05D9', 'U+05D3'],    ['&#1497;', '&#1491;'],   'Yod Dalet'),
    (15,  'טו',      ['U+05D8', 'U+05D5'],    ['&#1496;', '&#1493;'],   'Tet Vav'),
    (16,  'טז',      ['U+05D8', 'U+05D6'],    ['&#1496;', '&#1494;'],   'Tet Zayin'),
    (17,  'יז',      ['U+05D9', 'U+05D6'],    ['&#1497;', '&#1494;'],   'Yod Zayin'),
    (18,  'יח',      ['U+05D9', 'U+05D7'],    ['&#1497;', '&#1495;'],   'Yod Het'),
    (19,  'יט',      ['U+05D9', 'U+05D8'],    ['&#1497;', '&#1496;'],   'Yod Tet'),
    (20,  'כ',       ['U+05DB'],              ['&#1499;'],              'Kaf'),
    (21,  'כא',      ['U+05DB', 'U+05D0'],    ['&#1499;', '&#1488;'],   'Kaf Alef'),
    (22,  'כב',      ['U+05DB', 'U+05D1'],    ['&#1499;', '&#1489;'],   'Kaf Bet'),
    (23,  'כג',      ['U+05DB', 'U+05D2'],    ['&#1499;', '&#1490;'],   'Kaf Gimel'),
    (24,  'כד',      ['U+05DB', 'U+05D3'],    ['&#1499;', '&#1491;'],   'Kaf Dalet'),
    (25,  'כה',      ['U+05DB', 'U+05D4'],    ['&#1499;', '&#1492;'],   'Kaf He'),
    (26,  'כו',      ['U+05DB', 'U+05D5'],    ['&#1499;', '&#1493;'],   'Kaf Vav'),
    (27,  'כז',      ['U+05DB', 'U+05D6'],    ['&#1499;', '&#1494;'],   'Kaf Zayin'),
    (28,  'כח',      ['U+05DB', 'U+05D7'],    ['&#1499;', '&#1495;'],   'Kaf Het'),
    (29,  'כט',      ['U+05DB', 'U+05D8'],    ['&#1499;', '&#1496;'],   'Kaf Tet'),
    (30,  'ל',       ['U+05DC'],              ['&#1500;'],              'Lamed'),
    (31,  'לא',      ['U+05DC', 'U+05D0'],    ['&#1500;', '&#1488;'],   'Lamed Alef'),
    (32,  'לב',      ['U+05DC', 'U+05D1'],    ['&#1500;', '&#1489;'],   'Lamed Bet'),
    (33,  'לג',      ['U+05DC', 'U+05D2'],    ['&#1500;', '&#1490;'],   'Lamed Gimel'),
    (34,  'לד',      ['U+05DC', 'U+05D3'],    ['&#1500;', '&#1491;'],   'Lamed Dalet'),
    (35,  'לה',      ['U+05DC', 'U+05D4'],    ['&#1500;', '&#1492;'],   'Lamed He'),
    (36,  'לו',      ['U+05DC', 'U+05D5'],    ['&#1500;', '&#1493;'],   'Lamed Vav'),
    (37,  'לז',      ['U+05DC', 'U+05D6'],    ['&#1500;', '&#1494;'],   'Lamed Zayin'),
    (38,  'לח',      ['U+05DC', 'U+05D7'],    ['&#1500;', '&#1495;'],   'Lamed Het'),
    (39,  'לט',      ['U+05DC', 'U+05D8'],    ['&#1500;', '&#1496;'],   'Lamed Tet'),
    (40,  'מ',       ['U+05DE'],              ['&#1502;'],              'Mem'),
    (41,  'מא',      ['U+05DE', 'U+05D0'],    ['&#1502;', '&#1488;'],   'Mem Alef'),
    (42,  'מב',      ['U+05DE', 'U+05D1'],    ['&#1502;', '&#1489;'],   'Mem Bet'),
    (43,  'מג',      ['U+05DE', 'U+05D2'],    ['&#1502;', '&#1490;'],   'Mem Gimel'),
    (44,  'מד',      ['U+05DE', 'U+05D3'],    ['&#1502;', '&#1491;'],   'Mem Dalet'),
    (45,  'מה',      ['U+05DE', 'U+05D4'],    ['&#1502;', '&#1492;'],   'Mem He'),
    (46,  'מו',      ['U+05DE', 'U+05D5'],    ['&#1502;', '&#1493;'],   'Mem Vav'),
    (47,  'מז',      ['U+05DE', 'U+05D6'],    ['&#1502;', '&#1494;'],   'Mem Zayin'),
    (48,  'מח',      ['U+05DE', 'U+05D7'],    ['&#1502;', '&#1495;'],   'Mem Het'),
    (49,  'מט',      ['U+05DE', 'U+05D8'],    ['&#1502;', '&#1496;'],   'Mem Tet'),
    (50,  'נ',       ['U+05E0'],              ['&#1504;'],              'Nun'),
    (51,  'נא',      ['U+05E0', 'U+05D0'],    ['&#1504;', '&#1488;'],   'Nun Alef'),
    (52,  'נב',      ['U+05E0', 'U+05D1'],    ['&#1504;', '&#1489;'],   'Nun Bet'),
    (53,  'נג',      ['U+05E0', 'U+05D2'],    ['&#1504;', '&#1490;'],   'Nun Gimel'),
    (54,  'נד',      ['U+05E0', 'U+05D3'],    ['&#1504;', '&#1491;'],   'Nun Dalet'),
    (55,  'נה',      ['U+05E0', 'U+05D4'],    ['&#1504;', '&#1492;'],   'Nun He'),
    (56,  'נו',      ['U+05E0', 'U+05D5'],    ['&#1504;', '&#1493;'],   'Nun Vav'),
    (57,  'נז',      ['U+05E0', 'U+05D6'],    ['&#1504;', '&#1494;'],   'Nun Zayin'),
    (58,  'נח',      ['U+05E0', 'U+05D7'],    ['&#1504;', '&#1495;'],   'Nun Het'),
    (59,  'נט',      ['U+05E0', 'U+05D8'],    ['&#1504;', '&#1496;'],   'Nun Tet'),
    (60,  'ס',       ['U+05E1'],              ['&#1505;'],              'Samech'),
    (61,  'סא',      ['U+05E1', 'U+05D0'],    ['&#1505;', '&#1488;'],   'Samech Alef'),
    (62,  'סב',      ['U+05E1', 'U+05D1'],    ['&#1505;', '&#1489;'],   'Samech Bet'),
    (63,  'סג',      ['U+05E1', 'U+05D2'],    ['&#1505;', '&#1490;'],   'Samech Gimel'),
    (64,  'סד',      ['U+05E1', 'U+05D3'],    ['&#1505;', '&#1491;'],   'Samech Dalet'),
    (65,  'סה',      ['U+05E1', 'U+05D4'],    ['&#1505;', '&#1492;'],   'Samech He'),
    (66,  'סו',      ['U+05E1', 'U+05D5'],    ['&#1505;', '&#1493;'],   'Samech Vav'),
    (67,  'סז',      ['U+05E1', 'U+05D6'],    ['&#1505;', '&#1494;'],   'Samech Zayin'),
    (68,  'סח',      ['U+05E1', 'U+05D7'],    ['&#1505;', '&#1495;'],   'Samech Het'),
    (69,  'סט',      ['U+05E1', 'U+05D8'],    ['&#1505;', '&#1496;'],   'Samech Tet'),
    (70,  'ע',       ['U+05E2'],              ['&#1506;'],              'Ayin'),
    (71,  'עא',      ['U+05E2', 'U+05D0'],    ['&#1506;', '&#1488;'],   'Ayin Alef'),
    (72,  'עב',      ['U+05E2', 'U+05D1'],    ['&#1506;', '&#1489;'],   'Ayin Bet'),
    (73,  'עג',      ['U+05E2', 'U+05D2'],    ['&#1506;', '&#1490;'],   'Ayin Gimel'),
    (74,  'עד',      ['U+05E2', 'U+05D3'],    ['&#1506;', '&#1491;'],   'Ayin Dalet'),
    (75,  'עה',      ['U+05E2', 'U+05D4'],    ['&#1506;', '&#1492;'],   'Ayin He'),
    (76,  'עו',      ['U+05E2', 'U+05D5'],    ['&#1506;', '&#1493;'],   'Ayin Vav'),
    (77,  'עז',      ['U+05E2', 'U+05D6'],    ['&#1506;', '&#1494;'],   'Ayin Zayin'),
    (78,  'עח',      ['U+05E2', 'U+05D7'],    ['&#1506;', '&#1495;'],   'Ayin Het'),
    (79,  'עט',      ['U+05E2', 'U+05D8'],    ['&#1506;', '&#1496;'],   'Ayin Tet'),
    (80,  'פ',       ['U+05E4'],              ['&#1508;'],              'Pe'),
    (81,  'פא',      ['U+05E4', 'U+05D0'],    ['&#1508;', '&#1488;'],   'Pe Alef'),
    (82,  'פב',      ['U+05E4', 'U+05D1'],    ['&#1508;', '&#1489;'],   'Pe Bet'),
    (83,  'פג',      ['U+05E4', 'U+05D2'],    ['&#1508;', '&#1490;'],   'Pe Gimel'),
    (84,  'פד',      ['U+05E4', 'U+05D3'],    ['&#1508;', '&#1491;'],   'Pe Dalet'),
    (85,  'פה',      ['U+05E4', 'U+05D4'],    ['&#1508;', '&#1492;'],   'Pe He'),
    (86,  'פו',      ['U+05E4', 'U+05D5'],    ['&#1508;', '&#1493;'],   'Pe Vav'),
    (87,  'פז',      ['U+05E4', 'U+05D6'],    ['&#1508;', '&#1494;'],   'Pe Zayin'),
    (88,  'פח',      ['U+05E4', 'U+05D7'],    ['&#1508;', '&#1495;'],   'Pe Het'),
    (89,  'פט',      ['U+05E4', 'U+05D8'],    ['&#1508;', '&#1496;'],   'Pe Tet'),
    (90,  'צ',       ['U+05E6'],              ['&#1510;'],              'Tsadi'),
    (91,  'צא',      ['U+05E6', 'U+05D0'],    ['&#1510;', '&#1488;'],   'Tsadi Alef'),
    (92,  'צב',      ['U+05E6', 'U+05D1'],    ['&#1510;', '&#1489;'],   'Tsadi Bet'),
    (93,  'צג',      ['U+05E6', 'U+05D2'],    ['&#1510;', '&#1490;'],   'Tsadi Gimel'),
    (94,  'צד',      ['U+05E6', 'U+05D3'],    ['&#1510;', '&#1491;'],   'Tsadi Dalet'),
    (95,  'צה',      ['U+05E6', 'U+05D4'],    ['&#1510;', '&#1492;'],   'Tsadi He'),
    (96,  'צו',      ['U+05E6', 'U+05D5'],    ['&#1510;', '&#1493;'],   'Tsadi Vav'),
    (97,  'צז',      ['U+05E6', 'U+05D6'],    ['&#1510;', '&#1494;'],   'Tsadi Zayin'),
    (98,  'צח',      ['U+05E6', 'U+05D7'],    ['&#1510;', '&#1495;'],   'Tsadi Het'),
    (99,  'צט',      ['U+05E6', 'U+05D8'],    ['&#1510;', '&#1496;'],   'Tsadi Tet'),
    (100, 'ק',       ['U+05E7'],              ['&#1511;'],              'Qof'),
]

# ---------------------------------------------------------------------------
# Raw book data (OT books only; NT Hebrew names are transliterations)
# ---------------------------------------------------------------------------
_BOOK_DATA: list[tuple[str, str, str]] = [
    ('Genesis',          'בראשית',          'Bereshit'),
    ('Exodus',           'שמות',             'Shmot'),
    ('Leviticus',        'ויקרא',            'Vayikra'),
    ('Numbers',          'במדבר',            'Bamidbar'),
    ('Deuteronomy',      'דברים',            'Dvarim'),
    ('Joshua',           'יהושע',            'Yhoshuaa'),
    ('Judges',           'שופטים',           'Shuftim'),
    ('1 Samuel',         'שמואל א',          'Shamoeel Alef'),
    ('2 Samuel',         'שמואל ב',          'Shmoeel Bet'),
    ('1 Kings',          'מלכים א',          'Melachim Alef'),
    ('2 Kings',          'מלכים ב',          'Melachim Bet'),
    ('Isaiah',           'ישעיהו',           'Yshiaayahu'),
    ('Jeremiah',         'ירמיהו',           'Yirmiyaaho'),
    ('Ezekiel',          'יחזקאל',           'Yehezkeel'),
    ('Hosea',            'הושע',             'Hushea'),
    ('Joel',             'יואל',             'Yuel'),
    ('Amos',             'עמוס',             'Amos'),
    ('Obadiah',          'עבדיה',            'Auvadya'),
    ('Jonah',            'יונה',             'Yuna'),
    ('Micah',            'מיכה',             'Micha'),
    ('Nahum',            'נחום',             'Nahum'),
    ('Habakkuk',         'חבקוק',            'Havakok'),
    ('Zephaniah',        'צפניה',            'Tzfaniya'),
    ('Haggai',           'חגי',              'Hagi'),
    ('Zechariah',        'זכריה',            'Zehaariya'),
    ('Malachi',          'מלאכי',            'Malaachi'),
    ('Psalms',           'תהלים',            'Tehilim'),
    ('Proverbs',         'משלי',             'Meshliy'),
    ('Job',              'איוב',             'Eyuv'),
    ('Song of Solomon',  'שיר השירים',       'Shir HaShirim'),
    ('Ruth',             'רות',              'Root'),
    ('Lamentations',     'איכה',             'Icha'),
    ('Ecclesiastes',     'קהלת',             'Kuhelet'),
    ('Esther',           'אסתר',             'Ester'),
    ('Daniel',           'דניאל',            'Daniel'),
    ('Ezra',             'עזרא',             'Ezra'),
    ('Nehemiah',         'נחמיה',            'Nehaamiya'),
    ('1 Chronicles',     'דברי הימים א',     'Devri HaYamim Alef'),
    ('2 Chronicles',     'דברי הימים ב',     'Devri HaYamim Bet'),
    ('Matthew',          'הבשורה על-פי מתי',     ''),
    ('Mark',             'הבשורה על-פי מרקוס',   ''),
    ('Luke',             'הבשורה על-פי לוקס',    ''),
    ('John',             'הבשורה על-פי יוחנן',   ''),
]

# ---------------------------------------------------------------------------
# Build lookup tables at import time.
#
# NUMERALS maps 1-100 -> HebrewNumeral, BOOKS maps English book name ->
# HebrewBook. The private _BY_HEBREW / _BOOKS_BY_HEBREW tables invert those
# for the from_hebrew() / book_from_hebrew() lookups below.
# ---------------------------------------------------------------------------
NUMERALS: dict[int, HebrewNumeral] = {
    n: HebrewNumeral(n, h, tuple(u), tuple(html), say)
    for n, h, u, html, say in _NUMERAL_DATA
}

_BY_HEBREW: dict[str, int] = {v.hebrew: k for k, v in NUMERALS.items()}

BOOKS: dict[str, HebrewBook] = {
    eng: HebrewBook(eng, heb, say)
    for eng, heb, say in _BOOK_DATA
}

_BOOKS_BY_HEBREW: dict[str, str] = {v.hebrew: k for k, v in BOOKS.items()}


# ---------------------------------------------------------------------------
# Conversion API
# ---------------------------------------------------------------------------

def to_hebrew(n: int) -> str:
    """Convert an integer to its Hebrew numeral string.

    Args:
        n: Integer value in the range 1-100.

    Returns:
        The Hebrew numeral string, e.g. ``'יא'`` for 11.

    Raises:
        KeyError: If `n` is outside the 1-100 range covered by NUMERALS.
    """
    return NUMERALS[n].hebrew


def from_hebrew(s: str) -> int:
    """Convert a Hebrew numeral string back to its integer value.

    Args:
        s: A Hebrew numeral string, e.g. ``'יא'``.

    Returns:
        The integer value the numeral represents.

    Raises:
        KeyError: If `s` does not match any known numeral.
    """
    return _BY_HEBREW[s]


def to_say(n: int) -> str:
    """Return the romanised pronunciation for a numeral.

    Args:
        n: Integer value in the range 1-100.

    Returns:
        Romanised pronunciation, e.g. ``'Yod Alef'`` for 11.
    """
    return NUMERALS[n].say


def to_html(n: int) -> list[str]:
    """Return the HTML numeric character references for a numeral.

    Args:
        n: Integer value in the range 1-100.

    Returns:
        One HTML entity string per Hebrew letter, e.g. ``['&#1497;', '&#1488;']``.
    """
    return list(NUMERALS[n].html)


def to_unicode(n: int) -> list[str]:
    """Return the Unicode codepoints for a numeral.

    Args:
        n: Integer value in the range 1-100.

    Returns:
        One codepoint string per Hebrew letter, e.g. ``['U+05D9', 'U+05D0']``.
    """
    return list(NUMERALS[n].unicode)


def book_hebrew(english_name: str) -> str:
    """Look up the Hebrew name for an English book name.

    Args:
        english_name: Canonical English book name, e.g. ``'Genesis'``.

    Returns:
        The Hebrew book name, e.g. ``'בראשית'``.

    Raises:
        KeyError: If `english_name` is not a recognised book.
    """
    return BOOKS[english_name].hebrew


def book_from_hebrew(hebrew_name: str) -> str:
    """Look up the English name for a Hebrew book name.

    Args:
        hebrew_name: A Hebrew book name, e.g. ``'בראשית'``.

    Returns:
        The canonical English book name, e.g. ``'Genesis'``.

    Raises:
        KeyError: If `hebrew_name` is not a recognised book.
    """
    return _BOOKS_BY_HEBREW[hebrew_name]
