#!/usr/bin/env python3
"""Drift check: scan a corpus of real .spn/.fxc files and report every run of
source the grammar leaves unscoped.

This is a left-to-right scanner, not a word splitter: at each position it tries
every regex in the grammar, and on a match skips past it. That way '0x7f8000'
is consumed whole by the number rule instead of being mis-reported as an
unknown identifier 'x7f8000'.

Symbols the file declares for itself -- labels, FXCore .rn/.equ/.mreg/.sreg/
.creg/.mem, and FV-1 'name EQU val' / 'EQU name val' in either order -- are
expected to be unscoped, so they are subtracted. What is left should be empty.
Anything that survives is a hardware name the grammar is missing, or a new ISA
mnemonic that needs categorising in the generator.

Usage: check-coverage.py [corpus-root ...]
"""
import collections, json, os, re, sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROOTS = [os.path.expanduser('~/Documents/GitHub'),
                 os.path.expanduser('~/Library/CloudStorage/Dropbox')]

LANGS = {
    'fxcore':  {'exts': ('.fxc', '.fxo', '.fxl'),
                'grammar': 'syntaxes/fxcore.tmLanguage.json'},
    'spinasm': {'exts': ('.spn',),
                'grammar': 'syntaxes/spinasm.tmLanguage.json'},
}

# Whitespace and punctuation carry no scope of their own and are not a gap.
# Punctuation is skipped ONE character at a time: '$', '%' and '#' are literal
# prefixes here, so a greedy run would swallow the '$' of ' $007FFF00' together
# with the space before it and the hex rule would never see the position.
SPACE = re.compile(r'\s+')
PUNCT = re.compile(r'[,()\[\]+\-*/|&^~<>=!:.%$#@\'"\\{}?]')
WORD = re.compile(r'[A-Za-z_][A-Za-z0-9_]*|\d[A-Za-z0-9_.]*')

DECL = re.compile(
    r'^\s*\.(?:rn|equ|mreg|sreg|creg|mem)\s+([A-Za-z_][\w]*)'      # FXCore
    r'|^\s*([A-Za-z_][\w]*)\s*:'                                   # label
    r'|^\s*([A-Za-z_][\w]*)\s+(?i:equ|mem)\b'                      # FV-1 name-first
    r'|^\s*(?i:equ|mem)\s+([A-Za-z_][\w]*)',                       # FV-1 keyword-first
    re.M)


def rules(grammar):
    out = []
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ('match', 'begin') and isinstance(v, str):
                    try: out.append(re.compile(v))
                    except re.error: pass
                else: walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(grammar)
    return out


def read(path):
    """A sizeable minority of shipped .spn files are UTF-16LE with no BOM."""
    with open(path, 'rb') as f:
        data = f.read()
    if b'\x00' in data[:512]:
        enc = 'utf-16' if data[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-16-le'
    else:
        enc = 'utf-8'
    return data.decode(enc, errors='replace')


def strip(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'(;|//).*', ' ', text)
    return re.sub(r'"(?:[^"\\]|\\.)*"', ' ', text)


def scan(text, pats):
    """Yield each run of source no rule in the grammar matches."""
    i, n = 0, len(text)
    while i < n:
        # Grammar rules get first look, before punctuation is skipped:
        # '$', '%' and '#' are literal prefixes in these languages, so
        # skipping them first would hide '$007FFF00' behind a bogus '007FFF00'.
        best = 0
        for p in pats:
            m = p.match(text, i)
            if m and m.end() > i:
                best = max(best, m.end() - i)
        if best:
            i += best; continue
        m = SPACE.match(text, i)
        if m and m.end() > i:
            i = m.end(); continue
        if PUNCT.match(text, i):
            i += 1; continue
        m = WORD.match(text, i)
        if m:
            yield m.group(0); i = m.end()
        else:
            i += 1


def check(lang, roots, verbose):
    cfg = LANGS[lang]
    pats = rules(json.load(open(os.path.join(R, cfg['grammar']))))
    unknown, where, files, decls = collections.Counter(), {}, 0, set()
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != 'node_modules']
            for fn in filenames:
                if not fn.lower().endswith(cfg['exts']):
                    continue
                path = os.path.join(dirpath, fn)
                try: raw = read(path)
                except OSError: continue
                files += 1
                decls |= {m.lower() for g in DECL.findall(raw) for m in g if m}
                for w in set(scan(strip(raw), pats)):
                    unknown[w] += 1
                    where.setdefault(w, path)
    # Both languages are case-insensitive: a symbol declared 'tapCPos' and
    # used as 'tapCpos' is the same symbol.
    for w in [w for w in unknown if w.lower() in decls]:
        unknown.pop(w)
    print(f'\n{lang}: {files} files, {len(decls)} declared symbols subtracted')
    if not unknown:
        print('  full coverage')
        return 0
    for w, n in unknown.most_common(None if verbose else 30):
        print(f'  {n:5d}  {w:<24} e.g. {where[w]}')
    if not verbose and len(unknown) > 30:
        print(f'  ... and {len(unknown) - 30} more (-v for all)')
    return len(unknown)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '-v']
    verbose = '-v' in sys.argv
    roots = args or DEFAULT_ROOTS
    sys.exit(min(1, sum(check(l, roots, verbose) for l in LANGS)))
