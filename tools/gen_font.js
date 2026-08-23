/* 대사에 실제로 쓰이는 글자만 BDF 에서 떠서 글리프 헤더 두 개를 만든다.
   **자동 생성이다.** 대사표가 바뀌면 gen_lines.js / gen_duo.js 뒤에 이걸 돌려라.

     node tools/gen_font.js <소스디렉터리> [BDF디렉터리]

   Galmuri — SIL Open Font License 1.1 (https://github.com/quiple/galmuri) */
const fs = require('fs');
const path = require('path');
const { parseBDF, pack } = require('/home/claude/tools/bdf.js');

const DIR = process.argv[2];
const BDFDIR = process.argv[3] || '/tmp/package/dist';

/* ── 쓰인 글자 모으기 ──
   대사표만 훑으면 **기술 이름이 빠진다.** 기술명은 "%s" 로 끼워 넣는 것이라
   대사표 안에 그 글자가 없다. 실제로 「리쿠도렛카」의 '렛' 이 빠져 화면에 공백으로 나왔다.
   ss2sp 쪽(기술 이름·유파 이름)까지 반드시 같이 훑는다. */
const SRC = ['ss2comm_lines.h', 'ss2comm_duo.h', 'ss2comm.c', 'ss2comm.h',
             'ss2sp_moves.h', 'ss2sp.c', 'ss2sp.h',
             '../ss2sp/ss2sp_moves.h', '../ss2sp/ss2sp.c', '../ss2sp/ss2sp.h'];
const cps = new Set();
const scanned = [];
for (const f of SRC) {
  const p = path.join(DIR, f);
  if (!fs.existsSync(p)) continue;
  scanned.push(path.basename(f));
  const t = fs.readFileSync(p, 'utf8');
  for (const m of t.matchAll(/"((?:[^"\\]|\\.)*)"/g)) for (const ch of m[1]) cps.add(ch.codePointAt(0));
}
/* 서식·구두점 최소 집합은 늘 넣는다 */
for (const ch of ' 0123456789%sd…·—!?.,()~-:∼') cps.add(ch.codePointAt(0));
const list = [...cps].filter(c => c >= 0x20 && c < 0x10000).sort((a, b) => a - b);
console.log('훑은 파일: ' + scanned.join(', '));

function emit(file, opts) {
  const bdf = parseBDF(path.join(BDFDIR, opts.bdf));
  const ent = [];
  const miss = [];
  for (const cp of list) {
    const g = pack(bdf, cp, opts.H, opts.ascent, opts.xbit);
    if (g) ent.push({ cp, ...g }); else miss.push(cp);
  }
  let o = opts.head;
  o += '#ifndef ' + opts.guard + '\n#define ' + opts.guard + '\n#include <stdint.h>\n\n';
  o += opts.typedef + '\n\n';
  if (opts.H === 13) {
    o += '#define SS2FONT11_H 13\n#define SS2FONT11_N ' + ent.length + '\n';
    o += 'static const ss2glyph11 SS2FONT11[SS2FONT11_N] = {\n';
    for (const e of ent)
      o += '  {0x' + e.cp.toString(16).toUpperCase().padStart(4, '0') + ', ' + e.w + ',{' +
        e.rows.map(v => '0x' + v.toString(16).toUpperCase().padStart(4, '0')).join(',') + '}},\n';
  } else {
    o += 'static const ss2glyph SS2FONT[] = {\n';
    for (const e of ent)
      o += '  {0x' + e.cp.toString(16).toUpperCase().padStart(4, '0') + ',{' +
        e.rows.map(v => '0x' + v.toString(16).toUpperCase().padStart(2, '0')).join(',') + '}},\n';
  }
  o += '};\n';
  if (opts.H === 8) o += '#define SS2FONT_N ' + ent.length + '\n';
  o += '\n#endif\n';
  fs.writeFileSync(path.join(DIR, file), o);
  console.log(file + '  글리프 ' + ent.length + (miss.length ? '  (BDF에 없음 ' + miss.length + '자)' : ''));
}

emit('ss2comm_font11.h', {
  bdf: 'Galmuri11-Condensed.bdf', H: 13, ascent: 11, xbit: 11,
  guard: 'SS2COMM_FONT11_H',
  typedef: 'typedef struct { uint16_t cp; uint8_t w; uint16_t b[13]; } ss2glyph11;',
  head: '/* ss2comm_font11.h — 갈무리11 좁은꼴(Galmuri11-Condensed) 11px 글리프.\n' +
        '   **자동 생성 파일이다. 손으로 고치지 마라.** tools/gen_font.js 가 만든다.\n' +
        '   160픽셀 화면에서 8x8은 읽기 힘들고 보통꼴은 한 줄에 열두 자밖에 안 들어간다.\n' +
        '   좁은꼴은 높이 11px 그대로에 폭이 8px라 같은 자리에 스무 자가 들어간다.\n' +
        '   대사와 **기술 이름**에 실제로 쓰이는 글자만 BDF에서 그대로 떴다.\n' +
        '   Galmuri — SIL Open Font License 1.1 (https://github.com/quiple/galmuri)\n' +
        '   행은 위에서부터 13줄, 비트는 MSB(비트15)가 x=0. w = 다음 글자까지 간격. */\n'
});
emit('ss2comm_font.h', {
  bdf: 'Galmuri7.bdf', H: 8, ascent: 7, xbit: 7,
  guard: 'SS2COMM_FONT_H',
  typedef: 'typedef struct { uint16_t cp; uint8_t b[8]; } ss2glyph;',
  head: '/* ss2comm_font.h — 대사와 기술 이름에 실제로 쓰이는 글자만 담은 8x8 1bpp 글리프.\n' +
        '   **자동 생성 파일이다. 손으로 고치지 마라.** tools/gen_font.js 가 만든다.\n' +
        '   원본: Galmuri7 BDF (SIL Open Font License 1.1, https://github.com/quiple/galmuri).\n' +
        '   OFL은 프로그램에 임베드·재배포를 허용한다. 폰트 파일 자체를 그대로 재배포하지는 않는다. */\n'
});
