#!/usr/bin/env python3
"""Generate syntaxes/spinasm.tmLanguage.json from asfv1.py.

The assembler is the authority, not the Spin knowledge-base page: that page
omits LDAX, JMP and RAW, which asfv1 assembles. Regenerate after pulling
asfv1-extended so the grammar cannot drift from what actually builds.

Usage: python3 tools/gen-spinasm.py [path/to/asfv1.py]
"""
import json, os, re, sys

DEFAULT_ASFV1 = os.path.expanduser(
    '~/Library/CloudStorage/Dropbox/Arduino/asfv1-extended/asfv1.py')


def tables(src):
    def dict_keys(name):
        # Non-greedy to the first '}': none of these tables nest braces, and
        # this handles both the multi-line dicts and the single-line EXT_LFO.
        m = re.search(name + r'\s*=\s*\{(.*?)\}', src, re.S | re.M)
        return re.findall(r"'([A-Z0-9_]+)'\s*:", m.group(1)) if m else []

    ops = dict_keys(r'^op_tbl')
    ext_ops = dict_keys(r'^ext_op_tbl')
    ext_lfo = dict_keys(r'^EXT_LFO')
    ext_lfo_regs = dict_keys(r'^EXT_LFO_REGS')

    m = re.search(r'self\.symtbl\s*=\s*\{(.*?)\n\s*\}', src, re.S)
    sym = re.findall(r"'([A-Z0-9_]+)'\s*:", m.group(1))

    m = re.search(r'EXT_ONLY_OPS\s*=\s*frozenset\(\[(.*?)\]\)', src, re.S)
    ext_only_ops = re.findall(r"'([A-Z0-9_]+)'", m.group(1)) if m else []

    # POT3-5 are added to symtbl imperatively under #extended
    ext_pots = re.findall(r"self\.symtbl\['(POT[345])'\]", src)
    return ops, ext_ops, ext_lfo, ext_lfo_regs, sym, ext_only_ops, ext_pots


def alt(names):
    """Longest-first alternation; \\b alone already stops prefix matches, but
    ordering keeps the intent obvious to anyone reading the generated file."""
    return '|'.join(sorted(set(names), key=lambda s: (-len(s), s)))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ASFV1
    src = open(path).read()
    ops, ext_ops, ext_lfo, ext_lfo_regs, sym, ext_only_ops, ext_pots = tables(src)

    registers = [s for s in sym if re.fullmatch(r'REG\d+', s)] + [
        s for s in sym if s in
        ('POT0', 'POT1', 'POT2', 'ADCL', 'ADCR', 'DACL', 'DACR', 'ADDR_PTR')
        or s.endswith(('_RATE', '_RANGE'))] + ext_pots + ext_lfo_regs
    lfos = [s for s in sym if re.fullmatch(r'(SIN|RMP)\d', s)] + ext_lfo
    cho_flags = [s for s in sym if s in
                 ('SIN', 'COS', 'REG', 'COMPC', 'COMPA', 'RPTR2', 'NA')]
    cho_variants = [s for s in sym if s in ('RDA', 'SOF', 'RDAL')]
    conditions = [s for s in sym if s in ('RUN', 'ZRC', 'ZRO', 'GEZ', 'NEG')]

    # Instructions, minus the ones only reachable under #extended.
    base_ops = [o for o in ops if o not in ext_only_ops]
    only_ext = sorted(set(ext_only_ops) | (set(ext_ops) - set(ops)))

    comment = {
        "name": "comment.line.semicolon.spinasm",
        "begin": ";", "end": "$",
        "beginCaptures": {"0": {"name": "punctuation.definition.comment.spinasm"}},
        "patterns": [{"match": r"(?i)#SLOT(1[0-5]|[0-9])\b",
                      "name": "entity.name.function.spinasm"}],
    }

    grammar = {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "SpinASM",
        "scopeName": "source.spinasm",
        "patterns": [{"include": "#" + k} for k in (
            "comments", "pragmas", "labels", "directives", "skp", "instructions",
            "extended-instructions", "conditions", "registers", "lfos",
            "cho-flags", "delay-refs", "numbers", "strings")],
        "repository": {
            "comments": {"patterns": [comment]},
            "pragmas": {"patterns": [{
                "match": r"(?i)^\s*(#extended)\b",
                "captures": {"1": {"name": "keyword.control.directive.pragma.spinasm"}}}]},
            "labels": {"patterns": [{
                "match": r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:",
                "captures": {"1": {"name": "entity.name.function.spinasm"}}}]},
            "directives": {"patterns": [{
                "match": r"(?i)\b(EQU|MEM)\b",
                "name": "keyword.declaration.directive.spinasm"}]},
            # SKP takes 'condition, target', where target is a label or a
            # skip count. A begin/end context is the only way TextMate can
            # scope the trailing label while still colouring the condition,
            # so this has to precede the generic instruction rule.
            "skp": {"patterns": [{
                "begin": r"(?i)\b(SKP)\b",
                "beginCaptures": {"1": {"name": "keyword.control.flow.skip.spinasm"}},
                "end": "$",
                "patterns": [
                    {"include": "#comments"},
                    {"include": "#conditions"},
                    {"include": "#numbers"},
                    {"match": r"[|,]", "name": "punctuation.separator.spinasm"},
                    {"match": r"[A-Za-z_][A-Za-z0-9_]*",
                     "name": "entity.name.function.spinasm"},
                ]}]},
            "instructions": {"patterns": [{
                "match": r"(?i)\b(%s)\b" % alt(base_ops),
                "name": "keyword.operator.word.spinasm"}]},
            "extended-instructions": {"patterns": [{
                "match": r"(?i)\b(%s)\b" % alt(only_ext),
                "name": "keyword.operator.word.extended.spinasm"}]},
            "conditions": {"patterns": [{
                "match": r"(?i)\b(%s)\b" % alt(conditions),
                "name": "constant.language.condition.spinasm"}]},
            "registers": {"patterns": [{
                "match": r"(?i)\b(%s)\b" % alt(registers),
                "name": "variable.language.register.spinasm"}]},
            "lfos": {"patterns": [{
                "match": r"(?i)\b(%s)\b" % alt(lfos),
                "name": "constant.language.lfo.spinasm"}]},
            "cho-flags": {"patterns": [{
                "match": r"(?i)\b(%s)\b" % alt(cho_flags + cho_variants),
                "name": "constant.language.spinasm"}]},
            # asfv1 spells the delay midpoint '^'; Spin's page documents '$',
            # which this codebase has never used. Both are accepted so an
            # imported program still colours, with '#' for the end address.
            "delay-refs": {"patterns": [{
                "match": r"\b([A-Za-z_][A-Za-z0-9_]*)([#^$])",
                "captures": {"1": {"name": "variable.other.delay.spinasm"},
                             "2": {"name": "keyword.operator.delay.spinasm"}}}]},
            # asfv1's scanner (__next__) accepts four integer forms: the
            # SpinASM '$' hex and '%' binary prefixes, which strip '_', plus
            # C-style 0x and 0b. Floats are intpart '.' frac with an optional
            # exponent. 0x/0b must precede the plain-decimal rule or the
            # leading '0' is eaten as an integer.
            "numbers": {"patterns": [
                {"match": r"\$[0-9a-fA-F_]+", "name": "constant.numeric.hex.spinasm"},
                {"match": r"%[01_]+", "name": "constant.numeric.binary.spinasm"},
                {"match": r"(?i)\b0x[0-9a-f_]+\b", "name": "constant.numeric.hex.spinasm"},
                {"match": r"(?i)\b0b[01_]+\b", "name": "constant.numeric.binary.spinasm"},
                {"match": r"(?i)\b\d+\.\d*(e[-+]?\d+)?|\b\.\d+(e[-+]?\d+)?",
                 "name": "constant.numeric.float.spinasm"},
                {"match": r"\b\d+\b", "name": "constant.numeric.integer.spinasm"}]},
            "strings": {"patterns": [{
                "name": "string.quoted.double.spinasm",
                "begin": "\"", "end": "\"",
                "patterns": [{"match": r"\\.",
                              "name": "constant.character.escape.spinasm"}]}]},
        },
    }

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'syntaxes', 'spinasm.tmLanguage.json')
    with open(out, 'w') as f:
        json.dump(grammar, f, indent=2)
        f.write('\n')
    print(f'wrote {out}')
    print(f'  {len(base_ops)} instructions, {len(only_ext)} extended-only, '
          f'{len(registers)} registers, {len(lfos)} LFO selectors')


if __name__ == '__main__':
    main()
