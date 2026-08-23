/* 아주 작은 BDF 파서 — 필요한 것만 읽는다. */
const fs = require('fs');
function parseBDF(path) {
  const lines = fs.readFileSync(path, 'latin1').split('\n');
  const out = new Map();
  let cur = null, inBitmap = false;
  for (const raw of lines) {
    const s = raw.trim();
    if (s.startsWith('STARTCHAR')) { cur = { rows: [], cp: -1 }; inBitmap = false; continue; }
    if (!cur) continue;
    if (s.startsWith('ENCODING')) { cur.cp = parseInt(s.split(/\s+/)[1], 10); continue; }
    if (s.startsWith('DWIDTH')) { cur.dw = parseInt(s.split(/\s+/)[1], 10); continue; }
    if (s.startsWith('BBX')) {
      const p = s.split(/\s+/).map(Number);
      cur.bw = p[1]; cur.bh = p[2]; cur.bx = p[3]; cur.by = p[4]; continue;
    }
    if (s === 'BITMAP') { inBitmap = true; continue; }
    if (s === 'ENDCHAR') { if (cur.cp >= 0) out.set(cur.cp, cur); cur = null; inBitmap = false; continue; }
    if (inBitmap && /^[0-9A-Fa-f]+$/.test(s)) cur.rows.push(s);
  }
  return out;
}
/* 글리프를 H줄 격자에 얹고, x=0 이 비트 `xbit` 가 되도록 한 워드씩 싼다.
   포장 규칙은 기존 헤더와 **비트 단위로 대조해서** 정한 것이다(486/486 일치):
     font11 = Galmuri11-Condensed · ascent 11 · x=0 이 비트11 · 13줄
     font8  = Galmuri7            · ascent 7  · x=0 이 비트7  · 8줄 */
function pack(bdf, cp, H, ascent, xbit) {
  const g = bdf.get(cp);
  if (!g || g.bw === undefined) return null;
  const rows = new Array(H).fill(0);
  const bpr = Math.ceil(g.bw / 8), bits = bpr * 8;
  for (let r = 0; r < g.bh; r++) {
    const v = BigInt('0x' + (g.rows[r] || '0'));
    const y = ascent - g.by - g.bh + r;
    if (y < 0 || y >= H) continue;
    let w = 0;
    for (let c = 0; c < g.bw; c++) {
      if ((v >> BigInt(bits - 1 - c)) & 1n) {
        const x = g.bx + c;
        if (x >= 0 && x <= xbit) w |= 1 << (xbit - x);
      }
    }
    rows[y] = w;
  }
  return { w: g.dw, rows };
}
module.exports = { parseBDF, pack };
