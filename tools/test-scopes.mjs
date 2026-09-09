import fs from 'fs';
import path from 'path';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const oniguruma = require('vscode-oniguruma');
const vsctm = require('vscode-textmate');

const REPO = path.dirname(path.dirname(new URL(import.meta.url).pathname));
const wasm = fs.readFileSync(require.resolve('vscode-oniguruma/release/onig.wasm'));
await oniguruma.loadWASM(wasm.buffer);

const GRAMMARS = {
  'source.spinasm': path.join(REPO, 'syntaxes/spinasm.tmLanguage.json'),
  'source.fxcore':  path.join(REPO, 'syntaxes/fxcore.tmLanguage.json'),
};

const registry = new vsctm.Registry({
  onigLib: Promise.resolve({
    createOnigScanner: p => new oniguruma.OnigScanner(p),
    createOnigString: s => new oniguruma.OnigString(s),
  }),
  loadGrammar: async scope => GRAMMARS[scope]
    ? vsctm.parseRawGrammar(fs.readFileSync(GRAMMARS[scope], 'utf8'), GRAMMARS[scope])
    : null,
});

// [scope, line, [ [text, expected-scope-substring], ... ]]
const CASES = [
  ['source.spinasm', 'start:\tskp\trun, skip1', [
    ['start', 'entity.name.function'], ['skp', 'keyword.control.flow.skip'],
    ['run', 'constant.language'], ['skip1', 'entity.name'] ]],
  ['source.spinasm', '\tldax\tadcl', [
    ['ldax', 'keyword.operator.word'], ['adcl', 'variable.language.register'] ]],
  ['source.spinasm', '\tor\t$007FFF00', [['$007FFF00', 'constant.numeric.hex']]],
  ['source.spinasm', '\tand\t%01100000_00000000_00000000', [
    ['%01100000_00000000_00000000', 'constant.numeric.binary'] ]],
  ['source.spinasm', '\trdax\tpot0, 0x7fffff', [['0x7fffff', 'constant.numeric.hex']]],
  ['source.spinasm', '#extended', [['#extended', 'keyword.control.directive.pragma']]],
  ['source.spinasm', '\trmpax\treg0', [['rmpax', 'keyword.operator.word']]],
  ['source.spinasm', '\tcho\trda, sin0, REG|COMPC, delay^', [
    ['cho', 'keyword.operator.word'], ['sin0', 'constant.language.lfo'],
    ['REG', 'constant.language'], ['delay', 'variable.other.delay'],
    ['^', 'keyword.operator.delay'] ]],
  ['source.spinasm', '\twrax\tdacl, 1.0\t; comment here', [
    ['; comment here', 'comment'], ['1.0', 'constant.numeric.float'] ]],

  ['source.fxcore', '.creg\tr0\t0.5', [['.creg', 'keyword.declaration.directive']]],
  ['source.fxcore', '.rn\tmyreg\tr3', [['.rn', 'keyword.declaration.directive']]],
  ['source.fxcore', 'loop:\tcpy_cc\tacc32, r0', [
    ['loop', 'entity.name.function'], ['cpy_cc', 'keyword.control.transfer'],
    ['acc32', 'variable.language.register'] ]],
  ['source.fxcore', '\tjgez\tr0, done', [
    ['jgez', 'keyword.control.flow.jump.conditional'],
    ['r0', 'variable.language.register'], ['done', 'entity.name.function'] ]],
  ['source.fxcore', '\tjmp\tloop', [
    ['jmp', 'keyword.control.flow.jump'], ['loop', 'entity.name.function'] ]],
  ['source.fxcore', '\tsat64\tacc64', [['sat64', 'keyword.operator.word']]],
  ['source.fxcore', '\tchr\tr0, LFO0|SIN', [
    ['chr', 'support.function.builtin'], ['LFO0', 'constant.language'] ]],
  ['source.fxcore', '\t.equ\tx 0x1.8p-1', [['0x1.8p-1', 'constant.numeric.hex']]],
  ['source.fxcore', '; #SLOT3 preset name', [['#SLOT3', 'entity.name.function']]],
  ['source.fxcore', '/* block #SLOT0 */', [
    ['/*', 'comment.block'], ['#SLOT0', 'entity.name.function'] ]],
  ['source.fxcore', '\t.mem\tdelay 1000', [['.mem', 'keyword.declaration.directive']]],
  ['source.fxcore', '\twrdld\tacc64, @lfo(1)', [
    ['wrdld', 'keyword.operator.memory'], ['lfo', 'variable.function'] ]],
];

let fail = 0, checks = 0;
const cache = {};
for (const [scope, line, expects] of CASES) {
  const g = cache[scope] ??= await registry.loadGrammar(scope);
  const r = g.tokenizeLine(line, vsctm.INITIAL);
  for (const [text, want] of expects) {
    checks++;
    const at = line.indexOf(text);
    const tok = r.tokens.find(t => t.startIndex <= at && t.endIndex > at);
    const got = tok ? tok.scopes.join(' ') : '(no token)';
    if (!got.includes(want)) {
      fail++;
      console.log(`FAIL  [${scope}] ${JSON.stringify(line)}`);
      console.log(`        ${JSON.stringify(text)} wanted ${want}`);
      console.log(`        got    ${got}`);
    }
  }
}
console.log(`\n${checks - fail}/${checks} scope assertions passed`);
process.exit(fail ? 1 : 0);
