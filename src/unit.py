"""
unit.py — recursive tree node with biological / chemical annotation.

A Unit represents any level of a hierarchical text corpus:
    root → book → chapter → verse   (main Bible tree)
    category                          (cross-cutting thematic group)

All levels share the same type so callers can traverse, annotate and
aggregate uniformly.  The class carries no Bible-specific logic; the
build_bible_tree() factory at the bottom of this file does that.

Usage
-----
    from unit import Unit, build_bible_tree, lookup, BIO_MAP
    tree = build_bible_tree(kjv_list, categories_dict, heb_list, name_map)
    genesis = tree.find('GEN')
    print(genesis.top_bio(3))   # → [('Bos taurus', 42), ...]
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

# ── BioEntity ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BioEntity:
    """One biological organism or organic compound identifiable in text.

    Attributes:
        key: Canonical slug used as the key into BIO_MAP.
        bio_name: Linnaean binomial, e.g. ``'Vitis vinifera'``, or None.
        chimo_name: Common chemical / compound name, e.g. ``'ethanol'``, or None.
        formula: Molecular formula, e.g. ``'C₂H₅OH'``, or None.
        entity_type: One of ``'organism'``, ``'compound'``, ``'element'``, ``'mixture'``.
        is_organic: True if carbon-based; False if inorganic (e.g. water).
    """
    key:         str
    bio_name:    str | None
    chimo_name:  str | None
    formula:     str | None
    entity_type: str
    is_organic:  bool

# ── Bio / chemo keyword table ──────────────────────────────────────────────────
# Each row: ([trigger words], key, bio_name, chimo_name, formula, entity_type, is_organic)
# Trigger words are matched case-insensitively at word boundaries.

_ENTRIES: list[tuple] = [

    # ── cereals / bread ────────────────────────────────────────────────────────
    (['wheat', 'flour', 'bread', 'loaf', 'loaves', 'grain', 'meal', 'corn'],
     'wheat', 'Triticum aestivum', 'starch', '(C₆H₁₀O₅)ₙ', 'organism', True),

    (['barley', 'barleycorn'],
     'barley', 'Hordeum vulgare', 'starch', '(C₆H₁₀O₅)ₙ', 'organism', True),

    (['rye', 'spelt'],
     'rye', 'Secale cereale', 'starch', '(C₆H₁₀O₅)ₙ', 'organism', True),

    # ── fruits / fermentation ──────────────────────────────────────────────────
    (['wine', 'grape', 'grapes', 'vineyard', 'vineyards', 'vintage',
      'winepress', 'winebiber', 'grapevine', 'raisin', 'raisins', 'vine', 'vines'],
     'wine', 'Vitis vinifera', 'ethanol', 'C₂H₅OH', 'compound', True),

    (['vinegar'],
     'vinegar', None, 'acetic acid', 'C₂H₄O₂', 'compound', True),

    (['fig', 'figs', 'sycamore', 'sycomore'],
     'fig', 'Ficus carica', 'glucose', 'C₆H₁₂O₆', 'organism', True),

    (['pomegranate', 'pomegranates'],
     'pomegranate', 'Punica granatum', 'ellagic acid', 'C₁₄H₆O₈', 'organism', True),

    (['date', 'dates', 'palm'],
     'date_palm', 'Phoenix dactylifera', 'fructose', 'C₆H₁₂O₆', 'organism', True),

    # ── oils / fats ────────────────────────────────────────────────────────────
    (['olive', 'olives', 'oil', 'anointed', 'anoint', 'anointing'],
     'olive', 'Olea europaea', 'oleic acid', 'C₁₈H₃₄O₂', 'organism', True),

    (['fat', 'fatness', 'suet', 'lard', 'fatted'],
     'fat', None, 'palmitic acid', 'C₁₆H₃₂O₂', 'compound', True),

    (['butter', 'curds', 'cream'],
     'butter', 'Bos taurus', 'butyric acid', 'C₄H₈O₂', 'mixture', True),

    # ── sweeteners ─────────────────────────────────────────────────────────────
    (['honey', 'honeycomb', 'honeybee'],
     'honey', 'Apis mellifera', 'glucose', 'C₆H₁₂O₆', 'mixture', True),

    # ── dairy / animal products ────────────────────────────────────────────────
    (['milk', 'cheese', 'whey'],
     'milk', 'Bos taurus', 'lactose', 'C₁₂H₂₂O₁₁', 'mixture', True),

    (['blood'],
     'blood', None, 'hemoglobin', 'C₃₄H₃₂FeN₄O₄', 'compound', True),

    (['flesh', 'meat', 'carcass', 'carcases', 'carcase'],
     'meat', None, 'protein', 'C/H/N/O/S', 'mixture', True),

    # ── herd / flock animals ───────────────────────────────────────────────────
    (['lamb', 'lambs', 'sheep', 'ram', 'rams', 'ewe', 'ewes', 'flock', 'shearing'],
     'sheep', 'Ovis aries', None, None, 'organism', True),

    (['goat', 'goats', 'kid', 'kids'],
     'goat', 'Capra aegagrus hircus', None, None, 'organism', True),

    (['ox', 'oxen', 'bull', 'bulls', 'bullock', 'bullocks', 'cattle',
      'cow', 'cows', 'heifer', 'heifers', 'calf', 'calves'],
     'cattle', 'Bos taurus', None, None, 'organism', True),

    (['donkey', 'donkeys', 'ass', 'asses', 'mule', 'mules'],
     'donkey', 'Equus africanus asinus', None, None, 'organism', True),

    (['horse', 'horses', 'horseman', 'horsemen', 'mare', 'chariot'],
     'horse', 'Equus caballus', None, None, 'organism', True),

    (['camel', 'camels'],
     'camel', 'Camelus dromedarius', None, None, 'organism', True),

    (['swine', 'pig', 'pigs', 'sow', 'boar'],
     'swine', 'Sus scrofa', None, None, 'organism', True),

    # ── wild animals ───────────────────────────────────────────────────────────
    (['lion', 'lions', 'lioness', 'whelp', 'whelps', 'young lion'],
     'lion', 'Panthera leo', None, None, 'organism', True),

    (['bear', 'bears'],
     'bear', 'Ursus arctos syriacus', None, None, 'organism', True),

    (['wolf', 'wolves'],
     'wolf', 'Canis lupus', None, None, 'organism', True),

    (['leopard', 'leopards'],
     'leopard', 'Panthera pardus', None, None, 'organism', True),

    (['fox', 'foxes', 'jackal', 'jackals'],
     'fox', 'Vulpes vulpes', None, None, 'organism', True),

    # ── birds ──────────────────────────────────────────────────────────────────
    (['eagle', 'eagles', 'vulture', 'vultures'],
     'eagle', 'Aquila chrysaetos', None, None, 'organism', True),

    (['dove', 'doves', 'pigeon', 'pigeons', 'turtledove', 'turtledoves'],
     'dove', 'Columba livia', None, None, 'organism', True),

    (['raven', 'ravens', 'crow', 'crows'],
     'raven', 'Corvus corax', None, None, 'organism', True),

    (['sparrow', 'sparrows'],
     'sparrow', 'Passer domesticus', None, None, 'organism', True),

    (['quail', 'quails'],
     'quail', 'Coturnix coturnix', None, None, 'organism', True),

    # ── aquatic ────────────────────────────────────────────────────────────────
    (['fish', 'fishes', 'fishing', 'fisherman', 'fishermen', 'whale', 'leviathan'],
     'fish', 'Pisces', None, None, 'organism', True),

    # ── insects / invertebrates ────────────────────────────────────────────────
    (['locust', 'locusts', 'grasshopper', 'grasshoppers', 'cricket'],
     'locust', 'Schistocerca gregaria', None, None, 'organism', True),

    (['bee', 'bees', 'hornet', 'hornets'],
     'bee', 'Apis mellifera', None, None, 'organism', True),

    (['worm', 'worms', 'maggot', 'maggots'],
     'worm', 'Lumbricus terrestris', None, None, 'organism', True),

    (['moth', 'moths'],
     'moth', 'Tineola bisselliella', None, None, 'organism', True),

    (['scorpion', 'scorpions'],
     'scorpion', 'Leiurus quinquestriatus', None, None, 'organism', True),

    # ── reptiles ───────────────────────────────────────────────────────────────
    (['serpent', 'serpents', 'snake', 'snakes', 'viper', 'vipers',
      'adder', 'adders', 'asp', 'asps', 'basilisk'],
     'serpent', 'Serpentes', None, None, 'organism', True),

    # ── trees / timber ─────────────────────────────────────────────────────────
    (['cedar', 'cedars'],
     'cedar', 'Cedrus libani', 'cedrol', 'C₁₅H₂₆O', 'organism', True),

    (['oak', 'oaks', 'terebinth', 'teil'],
     'oak', 'Quercus', 'quercitrin', 'C₂₁H₂₀O₁₁', 'organism', True),

    (['acacia', 'shittim', 'shittah'],
     'acacia', 'Vachellia nilotica', 'catechin', 'C₁₅H₁₄O₆', 'organism', True),

    (['hyssop'],
     'hyssop', 'Origanum syriacum', 'thymol', 'C₁₀H₁₄O', 'organism', True),

    (['flax', 'linen'],
     'flax', 'Linum usitatissimum', 'cellulose', '(C₆H₁₀O₅)ₙ', 'organism', True),

    # ── spices / resins / aromatics ────────────────────────────────────────────
    (['frankincense', 'incense'],
     'frankincense', 'Boswellia sacra', 'boswellic acid', 'C₃₀H₄₈O₃', 'organism', True),

    (['myrrh'],
     'myrrh', 'Commiphora myrrha', 'myrrhol', 'C₁₅H₂₆O', 'organism', True),

    (['cinnamon'],
     'cinnamon', 'Cinnamomum verum', 'cinnamaldehyde', 'C₉H₈O', 'organism', True),

    (['spikenard', 'nard'],
     'spikenard', 'Nardostachys jatamansi', 'nardol', 'C₁₅H₂₆O', 'organism', True),

    (['aloe', 'aloes'],
     'aloe', 'Aloe vera', 'aloin', 'C₂₁H₂₂O₉', 'organism', True),

    (['wormwood'],
     'wormwood', 'Artemisia absinthium', 'absinthin', 'C₃₂H₄₄O₆', 'organism', True),

    (['calamus', 'cane'],
     'calamus', 'Acorus calamus', 'beta-asarone', 'C₁₂H₁₆O₃', 'organism', True),

    (['balm', 'balsam'],
     'balm', 'Commiphora gileadensis', 'alpha-pinene', 'C₁₀H₁₆', 'organism', True),

    (['camphor', 'henna'],
     'henna', 'Lawsonia inermis', 'lawsone', 'C₁₀H₆O₃', 'organism', True),

    # ── water (inorganic — tracked separately, is_organic=False) ──────────────
    (['water', 'waters', 'river', 'rivers', 'flood', 'floods',
      'sea', 'seas', 'rain', 'dew', 'fountain', 'fountains',
      'well', 'wells', 'spring', 'springs', 'stream', 'streams',
      'brook', 'brooks', 'pool', 'pools', 'lake'],
     'water', None, 'water', 'H₂O', 'element', False),
]

# Build the lookup structures
BIO_MAP: dict[str, BioEntity] = {}         # key → BioEntity
_KEYWORD_TO_KEY: dict[str, str] = {}       # any trigger word → canonical key

for _kws, _key, _bio, _chimo, _formula, _etype, _organic in _ENTRIES:
    _entity = BioEntity(_key, _bio, _chimo, _formula, _etype, _organic)
    BIO_MAP[_key] = _entity
    for _kw in _kws:
        _KEYWORD_TO_KEY[_kw.lower()] = _key


def lookup(word: str) -> BioEntity | None:
    """Look up the BioEntity for a trigger word or two-word phrase.

    Args:
        word: A single word or bigram to match, case-insensitive.

    Returns:
        The matching BioEntity, or None if `word` is not a known trigger.
    """
    return BIO_MAP.get(_KEYWORD_TO_KEY.get(word.lower(), ''))


# ── Unit ───────────────────────────────────────────────────────────────────────

@dataclass
class Unit:
    """
    A node in a hierarchical text tree.

    Typical Bible levels (coarsest → finest):
        'root'     — the entire corpus
        'book'     — e.g. Genesis
        'chapter'  — e.g. Genesis 1
        'verse'    — e.g. Genesis 1:1  (leaf node)
        'category' — cross-cutting thematic group (virtual / orthogonal)

    All levels are the same type.  Leaves carry raw text; inner nodes
    accumulate counts via aggregate().

    Attributes:
        uid: Unique identifier within the tree, e.g. ``'GEN'``, ``'GEN.1'``, ``'GEN.1.1'``.
        ui_name: Human-readable label shown in the UI.
        level: One of ``'root'``, ``'book'``, ``'chapter'``, ``'verse'``, ``'category'``.
        parent: The containing Unit, or None for the root.
        children: Child Units, in document order.
        bio_hits: Cumulative organism-mention counts, keyed by Linnaean name.
        chimo_hits: Cumulative compound-mention counts, keyed by formula.
        keyword_hits: Cumulative trigger-word mention counts.
        bio_name: Linnaean name of the most-mentioned organism in this subtree.
        chimo_name: Formula of the most-mentioned compound in this subtree.
        text: Raw verse text (verse-level nodes only).
        heb_text: Raw Hebrew verse text (verse-level nodes only).
        reference: Human-readable reference, e.g. ``'Hosea 13:16'`` (verse-level only).
        book: Containing book name.
        chapter: Containing chapter number.
        verse_num: Verse number (verse-level nodes only).
        category_tags: Names of flaw categories this verse is tagged with.
        notes: Catalogue note explaining why this verse qualifies, if any.
        meta: Open metadata bag for anything a parser needs to attach.
    """

    # ── identity ───────────────────────────────────────────────────────────────
    uid:     str   # unique within the tree; e.g. 'GEN', 'GEN.1', 'GEN.1.1'
    ui_name: str   # human-readable label shown in the UI
    level:   str   # 'root' | 'book' | 'chapter' | 'verse' | 'category'

    # ── tree links (excluded from eq / repr to avoid recursion) ───────────────
    parent:   Unit | None = field(default=None,         compare=False, repr=False)
    children: list[Unit]  = field(default_factory=list, compare=False, repr=False)

    # ── accumulated bio / chemo hit counts ─────────────────────────────────────
    # At leaves these are set by annotate_text(); at inner nodes by aggregate().
    bio_hits:     dict[str, int] = field(default_factory=dict)
    chimo_hits:   dict[str, int] = field(default_factory=dict)
    keyword_hits: dict[str, int] = field(default_factory=dict)

    # ── dominant labels (set by aggregate) ─────────────────────────────────────
    bio_name:   str | None = None   # Linnaean name of most-mentioned organism
    chimo_name: str | None = None   # formula of most-mentioned compound

    # ── verse-level payload (None for inner nodes) ─────────────────────────────
    text:          str | None  = None
    heb_text:      str | None  = None
    reference:     str | None  = None   # e.g. 'Hosea 13:16'
    book:          str | None  = None
    chapter:       int | None  = None
    verse_num:     int | None  = None
    category_tags: list[str]   = field(default_factory=list)
    notes:         str | None  = None

    # ── open metadata bag — attach anything a parser needs ─────────────────────
    meta: dict = field(default_factory=dict)

    def __hash__(self) -> int:
        """Hash by uid, so Units can be used in sets/dicts."""
        return hash(self.uid)

    def __repr__(self) -> str:
        """Return a short debug string with uid, level, and top annotations."""
        nc = len(self.children)
        return (f'Unit(uid={self.uid!r}, level={self.level!r}, '
                f'children={nc}, bio={self.bio_name!r}, chimo={self.chimo_name!r})')

    # ── tree operations ────────────────────────────────────────────────────────

    def add_child(self, child: Unit) -> Unit:
        """Attach a child node to this node, setting the child's parent link.

        Args:
            child: The Unit to attach.

        Returns:
            The same `child`, for chaining.
        """
        child.parent = self
        self.children.append(child)
        return child

    def is_leaf(self) -> bool:
        """Return True if this node has no children."""
        return not self.children

    def walk(self) -> Iterator[Unit]:
        """Traverse this subtree in pre-order (this node, then each child).

        Yields:
            Each Unit in the subtree, starting with self.
        """
        yield self
        for child in self.children:
            yield from child.walk()

    def leaves(self) -> Iterator[Unit]:
        """Traverse only the leaf nodes of this subtree.

        Yields:
            Each leaf Unit (a node with no children) in document order.
        """
        if self.is_leaf():
            yield self
        else:
            for child in self.children:
                yield from child.leaves()

    def path(self) -> list[Unit]:
        """Return the chain of ancestors from the root down to this node.

        Returns:
            A list of Units starting at the root and ending with self.
        """
        chain: list[Unit] = []
        node: Unit | None = self
        while node:
            chain.append(node)
            node = node.parent
        return list(reversed(chain))

    def breadcrumb(self) -> str:
        """Return a human-readable breadcrumb, e.g. ``'Bible / Genesis / Genesis 1'``."""
        return ' / '.join(n.ui_name for n in self.path())

    def depth(self) -> int:
        """Return this node's depth in the tree (0 = root, 1 = book, 2 = chapter, 3 = verse)."""
        return len(self.path()) - 1

    def find(self, uid: str) -> Unit | None:
        """Search this subtree for a node with the given uid.

        Args:
            uid: The uid to search for, e.g. ``'GEN.1.1'``.

        Returns:
            The matching Unit, or None if no node in the subtree has that uid.
        """
        for node in self.walk():
            if node.uid == uid:
                return node
        return None

    def siblings(self) -> list[Unit]:
        """Return all other nodes under the same parent as this node.

        Returns:
            A list of sibling Units (excluding self), or an empty list at the root.
        """
        if self.parent is None:
            return []
        return [c for c in self.parent.children if c is not self]

    def next_sibling(self) -> Unit | None:
        """Return the sibling immediately after this node, or None if last/root."""
        if self.parent is None:
            return None
        kids = self.parent.children
        idx = kids.index(self)
        return kids[idx + 1] if idx + 1 < len(kids) else None

    def prev_sibling(self) -> Unit | None:
        """Return the sibling immediately before this node, or None if first/root."""
        if self.parent is None:
            return None
        kids = self.parent.children
        idx = kids.index(self)
        return kids[idx - 1] if idx > 0 else None

    # ── bio / chemo queries ────────────────────────────────────────────────────

    def top_bio(self, n: int = 5) -> list[tuple[str, int]]:
        """Return the most-mentioned organisms in this subtree.

        Args:
            n: Maximum number of entries to return.

        Returns:
            (Linnaean name, hit count) pairs, sorted by count descending.
        """
        return sorted(self.bio_hits.items(), key=lambda x: x[1], reverse=True)[:n]

    def top_chimo(self, n: int = 5) -> list[tuple[str, int]]:
        """Return the most-mentioned compounds/formulas in this subtree.

        Args:
            n: Maximum number of entries to return.

        Returns:
            (formula, hit count) pairs, sorted by count descending.
        """
        return sorted(self.chimo_hits.items(), key=lambda x: x[1], reverse=True)[:n]

    def top_keywords(self, n: int = 10) -> list[tuple[str, int]]:
        """Return the most-frequent trigger words matched in this subtree.

        Args:
            n: Maximum number of entries to return.

        Returns:
            (keyword, hit count) pairs, sorted by count descending.
        """
        return sorted(self.keyword_hits.items(), key=lambda x: x[1], reverse=True)[:n]

    def organic_ratio(self) -> float:
        """Return the fraction of keyword hits that are organic compounds.

        Returns:
            A value in [0.0, 1.0]; 0.0 if this subtree has no keyword hits.
        """
        total = sum(self.keyword_hits.values())
        if total == 0:
            return 0.0
        organic = sum(
            cnt for kw, cnt in self.keyword_hits.items()
            if (e := lookup(kw)) and e.is_organic
        )
        return organic / total

    # ── annotation ────────────────────────────────────────────────────────────

    def annotate_text(self, text: str) -> None:
        """Scan text for bio/chemo keywords and update this node's hit counts.

        Checks bigrams first (more specific), then unigrams. Safe to call
        multiple times — counts accumulate rather than reset.

        Args:
            text: The raw verse text to scan.
        """
        words = re.findall(r'[a-z]+(?:[-\'][a-z]+)*', text.lower())
        matched: set[int] = set()

        # bigrams
        for i in range(len(words) - 1):
            phrase = f'{words[i]} {words[i + 1]}'
            entity = lookup(phrase)
            if entity:
                matched.update((i, i + 1))
                self._record(phrase, entity)

        # unigrams (skip indices consumed by a bigram)
        for i, word in enumerate(words):
            if i in matched:
                continue
            entity = lookup(word)
            if entity:
                self._record(word, entity)

    def _record(self, keyword: str, entity: BioEntity) -> None:
        """Increment this node's hit counts for one matched keyword/entity pair.

        Args:
            keyword: The matched word or bigram, as found in the text.
            entity: The BioEntity the keyword resolved to.
        """
        self.keyword_hits[keyword] = self.keyword_hits.get(keyword, 0) + 1
        if entity.bio_name and entity.entity_type == 'organism':
            self.bio_hits[entity.bio_name] = self.bio_hits.get(entity.bio_name, 0) + 1
        if entity.formula:
            self.chimo_hits[entity.formula] = self.chimo_hits.get(entity.formula, 0) + 1

    # ── aggregation ───────────────────────────────────────────────────────────

    def aggregate(self) -> None:
        """Roll up hit counts from children into this node, bottom-up.

        Recurses into children first, merges their bio/chimo/keyword hit
        counts into this node, then recomputes this node's dominant
        `bio_name` / `chimo_name`. Call once after the tree is fully built
        and all leaves have been annotated.
        """
        for child in self.children:
            child.aggregate()
            for k, v in child.bio_hits.items():
                self.bio_hits[k] = self.bio_hits.get(k, 0) + v
            for k, v in child.chimo_hits.items():
                self.chimo_hits[k] = self.chimo_hits.get(k, 0) + v
            for k, v in child.keyword_hits.items():
                self.keyword_hits[k] = self.keyword_hits.get(k, 0) + v
        if self.bio_hits:
            self.bio_name = max(self.bio_hits, key=self.bio_hits.__getitem__)
        if self.chimo_hits:
            self.chimo_name = max(self.chimo_hits, key=self.chimo_hits.__getitem__)

    # ── serialisation ─────────────────────────────────────────────────────────

    def to_dict(self, shallow: bool = False) -> dict:
        """Serialise this node (and a summary of its children) to a JSON-safe dict.

        Args:
            shallow: Unused summary flag reserved for future use; children
                are currently always rendered as summary dicts (no
                grandchildren), which keeps payloads small by construction.

        Returns:
            A dict suitable for ``flask.jsonify``, including this node's
            identity, aggregated bio/chemo annotations, verse payload
            (if any), and a summary of each direct child.
        """
        def child_summary(c: Unit) -> dict:
            """Build the compact summary dict used for each entry in 'children'."""
            return {
                'uid':        c.uid,
                'ui_name':    c.ui_name,
                'level':      c.level,
                'bio_name':   c.bio_name,
                'chimo_name': c.chimo_name,
                'n_children': len(c.children),
                'top_bio':    c.top_bio(3),
                'top_chimo':  c.top_chimo(3),
            }

        return {
            'uid':           self.uid,
            'ui_name':       self.ui_name,
            'level':         self.level,
            'bio_name':      self.bio_name,
            'chimo_name':    self.chimo_name,
            'top_bio':       self.top_bio(5),
            'top_chimo':     self.top_chimo(5),
            'top_keywords':  self.top_keywords(10),
            'organic_ratio': round(self.organic_ratio(), 3),
            'breadcrumb':    self.breadcrumb(),
            'children':      [child_summary(c) for c in self.children],
            # verse payload
            'text':          self.text,
            'heb_text':      self.heb_text,
            'reference':     self.reference,
            'book':          self.book,
            'chapter':       self.chapter,
            'verse_num':     self.verse_num,
            'category_tags': self.category_tags,
            'notes':         self.notes,
            'meta':          self.meta,
        }


# ── Bible tree builder ────────────────────────────────────────────────────────

def build_bible_tree(
    kjv:        list[dict],
    categories: dict | None            = None,
    heb_bible:  list[dict] | None      = None,
    name_map:   dict[str, int] | None  = None,
) -> Unit:
    """Build a full Unit tree (root -> book -> chapter -> verse) from KJV data.

    Each verse leaf is tagged with matching category names/notes (if
    `categories` is given), paired with its Hebrew text (if `heb_bible` is
    given), and annotated for bio/chemo keyword hits. `aggregate()` is
    called on the root before returning, so every node's `bio_name` /
    `chimo_name` / hit counts are already rolled up.

    Args:
        kjv: List of book dicts as loaded from en_kjv.json. Each book is
            ``{'abbrev': str, 'name': str, 'chapters': [[str, ...], ...]}``.
        categories: Dict loaded from src/categories/*.py, used to tag verses
            with category names and notes. Optional.
        heb_bible: List of book dicts (same shape as `kjv`) providing Hebrew
            verse text. Optional.
        name_map: Maps ``book_name.lower()`` to its index in `kjv`, used to
            align `heb_bible` books to `kjv` books. Built from `kjv` if not
            given.

    Returns:
        The root Unit, with the full tree built and aggregated beneath it.
    """

    # Pre-build category tag index: (book.lower(), ch, vs) → [nice_name, ...]
    cat_index: dict[tuple, list[str]] = {}
    cat_notes: dict[tuple, str] = {}
    if categories:
        for cat in categories.values():
            for entry in cat['verses'].values():
                b = entry['book'].lower()
                c = entry['chapter']
                vv = entry['verse'] if isinstance(entry['verse'], list) else [entry['verse']]
                for v in vv:
                    key = (b, c, v)
                    cat_index.setdefault(key, []).append(cat['nice_name'])
                    if entry.get('notes'):
                        cat_notes.setdefault(key, entry['notes'])

    # Build name_map if not provided
    if name_map is None:
        name_map = {b['name'].lower(): i for i, b in enumerate(kjv)}

    root = Unit(uid='ROOT', ui_name='The Bible', level='root')

    for book_data in kjv:
        abbrev     = book_data['abbrev'].upper()
        book_name  = book_data['name']
        book_unit  = Unit(uid=abbrev, ui_name=book_name, level='book', book=book_name)
        root.add_child(book_unit)

        # Hebrew chapter list for this book (may be absent for NT-only bibles)
        heb_chapters: list | None = None
        if heb_bible:
            heb_idx = name_map.get(book_name.lower())
            if heb_idx is not None and heb_idx < len(heb_bible):
                heb_chapters = heb_bible[heb_idx].get('chapters', [])

        for ch_idx, ch_verses in enumerate(book_data['chapters']):
            ch_num  = ch_idx + 1
            ch_uid  = f'{abbrev}.{ch_num}'
            ch_unit = Unit(
                uid=ch_uid,
                ui_name=f'{book_name} {ch_num}',
                level='chapter',
                book=book_name,
                chapter=ch_num,
            )
            book_unit.add_child(ch_unit)

            heb_ch: list | None = None
            if heb_chapters and ch_num <= len(heb_chapters):
                heb_ch = heb_chapters[ch_num - 1]

            for vs_idx, vs_text in enumerate(ch_verses):
                vs_num  = vs_idx + 1
                vs_uid  = f'{abbrev}.{ch_num}.{vs_num}'
                heb_txt = heb_ch[vs_idx] if (heb_ch and vs_idx < len(heb_ch)) else None
                key     = (book_name.lower(), ch_num, vs_num)

                vs_unit = Unit(
                    uid=vs_uid,
                    ui_name=f'{book_name} {ch_num}:{vs_num}',
                    level='verse',
                    text=vs_text,
                    heb_text=heb_txt,
                    reference=f'{book_name} {ch_num}:{vs_num}',
                    book=book_name,
                    chapter=ch_num,
                    verse_num=vs_num,
                    category_tags=list(cat_index.get(key, [])),
                    notes=cat_notes.get(key),
                )
                vs_unit.annotate_text(vs_text)
                ch_unit.add_child(vs_unit)

    root.aggregate()
    return root
