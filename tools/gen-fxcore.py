#!/usr/bin/env python3
"""Generate syntaxes/fxcore.tmLanguage.json.

Instruction set is FXCore_Instruction_Set_2025.pdf v1.2 (September 2025),
72 instructions. The categorised lists below must union to exactly that set;
the assertion at the bottom fails loudly if a future ISA revision adds an
instruction nobody categorised.

Registers, SFRs and constants are ported from fxcore.sublime-syntax, with
these fixes:
  * '.creg' added to the directives rule  (246 uses across 138 files)
  * 'sat65' dropped -- not an instruction; the ISA spells it SAT64
  * hex-float exponent 'p' restored, which the sublime copy had dropped
"""
import json, os

ALU = ['abs', 'clracc64', 'addi', 'add', 'adds', 'addsi', 'sub', 'subs',
       'sl', 'slr', 'sls', 'slsr', 'sr', 'srr', 'sra', 'srar',
       'macrr', 'macri', 'macrd', 'macid',
       'machrr', 'machri', 'machrd', 'machid',
       'multrr', 'multri', 'neg', 'log2', 'exp2', 'sat64']
JUMPS_COND = ['jgez', 'jneg', 'jnz', 'jz', 'jzc']
JUMPS_UNCOND = ['jmp']
COPY = ['cpy_cc', 'cpy_cm', 'cpy_cs', 'cpy_mc', 'cpy_sc', 'cpy_cmx']
MEMORY = ['rdacc64u', 'rdacc64l', 'ldacc64u', 'ldacc64l', 'rddel', 'wrdel',
          'rddelx', 'wrdelx', 'rddirx', 'wrdirx', 'wrdld']
LOGIC = ['inv', 'or', 'ori', 'and', 'andi', 'xor', 'xori']
DSP = ['apa', 'apb', 'apra', 'aprb', 'aprra', 'aprrb', 'apma', 'apmb',
       'chr', 'pitch', 'set', 'interp']

ISA_2025 = set(ALU + JUMPS_COND + JUMPS_UNCOND + COPY + MEMORY + LOGIC + DSP)

DIRECTIVES = ['mreg', 'sreg', 'creg', 'mem', 'equ', 'rn']

REGISTERS = (r'r[0-9]|r1[0-5]|acc32|flags|acc64|in[0-3]|out[0-3]|pin|switch|'
             r'pot[0-5]_k|pot[0-5]_smth|pot[0-5]|'
             r'lfo[0-3]_f|ramp[01]_f|lfo[0-3]_s|lfo[0-3]_c|ramp[01]_r|'
             r'maxtempo|taptempo|samplecnt|noise|bootstat|tapstkrld|'
             r'tapdbrld|swdbrld|prgdbrld|oflrld|'
             r'mr[0-9]|mr[1-9][0-9]|mr1[0-1][0-9]|mr12[0-7]')

CONSTANTS = [
    r'LFO[0-3]|SIN|COS|POS|NEG|RMP[01]|L512|L1024|L2048|L4096|XF[0-3]|USER[01]',
    r'OUT[0-3]OFLO|IN[0-3]OFLO',
    r'TB2NTB1|TAPSTKY|NEWTT|TAPRE|TAPPE|TAPLVL',
    r'SW[0-4](DB|RE|PE)?',
    r'ENABLEDB?|PLLRANGE[01]|MNS|I2CA[0-6]|TAP',
    r'PR(1[0-5]|[0-9])',
]


def alt(names):
    return '|'.join(sorted(set(names), key=lambda s: (-len(s), s)))


def comment_body(scope):
    """#SLOT markers stay highlighted inside every comment form."""
    return [{"match": r"(?i)#SLOT(1[0-5]|[0-9])\b",
             "name": "entity.name.function.fxcore"},
            {"match": r"(?i)#(pot[0-5]|sw[0-4]|tap)\b",
             "name": "entity.name.tag.fxcore"}]


def main():
    grammar = {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "FXCore",
        "scopeName": "source.fxcore",
        "patterns": [{"include": "#" + k} for k in (
            "comments", "directives", "labels", "jumps", "instructions",
            "registers", "constants", "functions", "numbers", "strings")],
        "repository": {
            "comments": {"patterns": [
                {"name": "comment.block.fxcore",
                 "begin": r"/\*", "end": r"\*/",
                 "beginCaptures": {"0": {"name": "punctuation.definition.comment.begin.fxcore"}},
                 "endCaptures": {"0": {"name": "punctuation.definition.comment.end.fxcore"}},
                 "patterns": comment_body("block")},
                {"name": "comment.line.semicolon.fxcore",
                 "begin": ";", "end": "$",
                 "beginCaptures": {"0": {"name": "punctuation.definition.comment.fxcore"}},
                 "patterns": comment_body("line")},
                {"name": "comment.line.double-slash.fxcore",
                 "begin": "//", "end": "$",
                 "beginCaptures": {"0": {"name": "punctuation.definition.comment.fxcore"}},
                 "patterns": comment_body("line")},
            ]},
            "directives": {"patterns": [{
                "match": r"(?i)(\.(?:%s))\b" % alt(DIRECTIVES),
                "captures": {"1": {"name": "keyword.declaration.directive.fxcore"}}}]},
            "labels": {"patterns": [{
                "match": r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:",
                "captures": {"1": {"name": "entity.name.function.fxcore"}}}]},
            "jumps": {"patterns": [
                {"match": r"(?i)\b(%s)\s+([A-Za-z_][A-Za-z0-9_]*)" % alt(JUMPS_UNCOND),
                 "captures": {"1": {"name": "keyword.control.flow.jump.fxcore"},
                              "2": {"name": "entity.name.function.fxcore"}}},
                # Conditional jumps take 'mnemonic reg, target'. A begin/end
                # context is the only way TextMate can scope the trailing
                # target as a label while still colouring the register.
                {"begin": r"(?i)\b(%s)\b" % alt(JUMPS_COND),
                 "beginCaptures": {"1": {"name": "keyword.control.flow.jump.conditional.fxcore"}},
                 "end": "$",
                 "patterns": [
                     {"include": "#comments"},
                     {"include": "#registers"},
                     {"include": "#constants"},
                     {"include": "#numbers"},
                     {"match": ",", "name": "punctuation.separator.fxcore"},
                     {"match": r"[A-Za-z_][A-Za-z0-9_]*",
                      "name": "entity.name.function.fxcore"},
                 ]},
            ]},
            "instructions": {"patterns": [
                {"match": r"(?i)\b(%s)\b" % alt(ALU),
                 "name": "keyword.operator.word.fxcore"},
                {"match": r"(?i)\b(%s)\b" % alt(COPY),
                 "name": "keyword.control.transfer.fxcore"},
                {"match": r"(?i)\b(%s)\b" % alt(MEMORY),
                 "name": "keyword.operator.memory.fxcore"},
                {"match": r"(?i)\b(%s)\b" % alt(LOGIC),
                 "name": "keyword.operator.bitwise.fxcore"},
                {"match": r"(?i)\b(%s)\b" % alt(DSP),
                 "name": "support.function.builtin.fxcore"},
            ]},
            "registers": {"patterns": [{
                "match": r"(?i)\b(%s)\b" % REGISTERS,
                "name": "variable.language.register.fxcore"}]},
            "constants": {"patterns": [
                {"match": r"(?i)\b(%s)\b" % c, "name": "constant.language.fxcore"}
                for c in CONSTANTS]},
            "functions": {"patterns": [
                {"begin": r"(@)([A-Za-z_.][A-Za-z0-9_]*)\s*(\()",
                 "beginCaptures": {"1": {"name": "punctuation.accessor.fxcore"},
                                   "2": {"name": "variable.function.fxcore"},
                                   "3": {"name": "punctuation.section.arguments.begin.fxcore"}},
                 "end": r"\)",
                 "endCaptures": {"0": {"name": "punctuation.section.arguments.end.fxcore"}},
                 "patterns": [{"include": "#numbers"},
                              {"match": r"\w+", "name": "variable.parameter.fxcore"}]},
                {"match": r"(@)([A-Za-z_.][A-Za-z0-9_]*)",
                 "captures": {"1": {"name": "punctuation.accessor.fxcore"},
                              "2": {"name": "variable.function.fxcore"}}}]},
            "numbers": {"patterns": [
                {"match": r"(?i)\b0x[0-9a-f]*(\.[0-9a-f]+p-?\d+)?",
                 "name": "constant.numeric.hex.fxcore"},
                {"match": r"(?i)\b\d+\.\d*(e[-+]?\d+)?|\b\.\d+(e[-+]?\d+)?",
                 "name": "constant.numeric.float.fxcore"},
                {"match": r"\b\d+\b", "name": "constant.numeric.integer.fxcore"}]},
            "strings": {"patterns": [{
                "name": "string.quoted.double.fxcore",
                "begin": "\"", "end": "\"",
                "patterns": [{"match": r"\\.",
                              "name": "constant.character.escape.fxcore"}]}]},
        },
    }

    categorised = set(ALU + JUMPS_COND + JUMPS_UNCOND + COPY + MEMORY + LOGIC + DSP)
    assert categorised == ISA_2025, (
        f"uncategorised: {ISA_2025 - categorised}, unknown: {categorised - ISA_2025}")

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'syntaxes', 'fxcore.tmLanguage.json')
    with open(out, 'w') as f:
        json.dump(grammar, f, indent=2)
        f.write('\n')
    print(f'wrote {out}')
    print(f'  {len(ISA_2025)} instructions, {len(DIRECTIVES)} directives')


if __name__ == '__main__':
    main()
