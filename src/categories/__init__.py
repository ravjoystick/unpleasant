"""Character-flaw category data, one file per chapter of Barker's book.

Each sibling module in this package (e.g. genocidal.py, jealous.py) is a
plain Python dict literal not an importable module — parsed at load time
via ast.literal_eval() by web.py / reader.py / ui.py. This __init__.py is
explicitly skipped by that loader and exists only to make the directory a
package for tooling purposes.
"""
