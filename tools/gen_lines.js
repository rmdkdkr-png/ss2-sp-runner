#!/usr/bin/env node
/* gen_lines.js — 실행기(index.html)의 SPEAKERS 를 읽어 C 대사표 ss2comm_lines.h 를 만든다.
 *
 *   node tools/gen_lines.js <index.html> <출력 ss2comm_lines.h> [--check <기존 헤더>]
 *
 * 왜 헤드리스로 띄우나:
 *   SPEAKERS 의 값은 문자열이 아니라 **함수**다. pick()·NM()·RO()·NR() 같은 헬퍼와
 *   cfg 를 물고 있어서, 정규식으로 긁거나 스텁을 끼우면 반드시 어긋난다.
 *   그래서 진짜 실행기를 띄우고 window.__ss2 로 원본 함수를 그대로 부른다.
 *   (__ss2 는 ?debug=1 일 때만 열린다. cfg 도 거기 같이 나온다.)
 *
 * 변주를 다 뽑는 법:
 *   pick(a){ return a[(Math.random()*a.length)|0]; } 이므로 Math.random 을 갈아끼우면
 *   난수가 아니라 **전수 열거**가 된다. r=(i+0.5)/STEPS 를 훑으면 길이 STEPS 이하 목록의
 *   모든 칸이 한 번씩 나온다. 그 뒤 무작위로 한 번 더 훑어 빠진 조합이 있으면 알려 준다.
 *
 * 유파:
 *   RSTS()=>cfg.style==="b" 이고 NR(수라문안, 나찰문안) 로 갈린다.
 *   나코루루처럼 인격이 둘인 화자는 양쪽을 다 넣어야 기존 표와 맞는다. 그래서 s·b 를 다 훑는다.
 *
 * 순서:
 *   옛 표는 난수로 만나는 대로 쌓아서 순서가 뒤죽박죽이었다. 여기서는 **정렬해 고정**한다.
 *   그래야 다음부터 diff 가 읽힌다.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const http = require('http');

const EV = [
  'START','ROUND','KO','KOED','DKO','PERFECT',
  'COMEBACK','QUICK','LOW1','LOW2','REVERSAL','WINTALK',
  'LOSETALK','SURV','SURVEND','STAGE','QUOTE','ENDING',
  'CHARSEL','STYLESEL','CARDSEL','TITLE','MUSE_B','MUSE_Q',
  'MUSE_M','IDLE','VSQ','STORYCHAT','CHARSELCHAT','MENUIDLE',
  'FIRSTBLOOD','ROUNDLEAD','ROUNDBEHIND','MATCHPOINT','DOUBLELOW','LONGFIGHT',
  'HIT','TAKEN','DOWN','DOWNED','OPPSP','MOVE',
  'MOVEHIT','MOVEHITL','MOVEDOWN','MOVEDOWNA','MOVEKO','REVENGE','STREAK','RECORD',
  'WINSCR','LOSESCR','REL','LORE','FLOWSAME','FLOWTRADE',
  'FLOWONE','FLOWCHASE','FLOWSP','ARCSWEEP','ARCSWEPT','ARCCOMEBACK',
  'ARCSWEAT','ARCCHOKE','ARCSLIP',
];

/* EV_* ↔ 실행기 키. muse 하나가 ctx 로 세 갈래(MUSE_B/Q/M)로 갈린다.
   실행기에만 있고 C 에 자리가 없는 것 여섯:
     domLead domBehind halfHp2 halfHp1 rush oppInfo
   자리를 만들려면 위 EV 목록과 ss2comm.c 의 emit 을 같이 고쳐야 한다. */
const MAP = {
  START:'start', ROUND:'round', KO:'ko', KOED:'koed', DKO:'dko', PERFECT:'perfect',
  COMEBACK:'comeback', QUICK:'quickKo', LOW1:'low1', LOW2:'low2', REVERSAL:'reversal',
  WINTALK:'winTalk', LOSETALK:'loseTalk', SURV:'survStreak', SURVEND:'survEnd',
  STAGE:'storyStage', QUOTE:'quoteScr', ENDING:'ending', CHARSEL:'charsel',
  STYLESEL:'stylesel', CARDSEL:'cardsel', TITLE:'title',
  MUSE_B:'muse', MUSE_Q:'muse', MUSE_M:'muse',
  IDLE:'idle', VSQ:'vsq', STORYCHAT:'storyChat', CHARSELCHAT:'charselChat',
  MENUIDLE:'menuIdle', FIRSTBLOOD:'firstBlood', ROUNDLEAD:'roundLead',
  ROUNDBEHIND:'roundBehind', MATCHPOINT:'matchPoint', DOUBLELOW:'doubleLow',
  LONGFIGHT:'longFight', HIT:'hit', TAKEN:'taken', DOWN:'down', DOWNED:'downed',
  OPPSP:'oppSp', MOVE:'move',
  MOVEHIT:'moveHit', MOVEHITL:'moveHit',      // 강타 / 약타 — dmg 로 갈린다
  MOVEDOWN:'moveDown', MOVEDOWNA:'moveDown',  // 이름 있음 / 없음
  MOVEKO:'moveKo',
  REVENGE:'revenge', STREAK:'streak', RECORD:'record', WINSCR:'winScr', LOSESCR:'loseScr',
  REL:'rel', LORE:'lore', FLOWSAME:'flowSameMove', FLOWTRADE:'flowTrade',
  FLOWONE:'flowOneSide', FLOWCHASE:'flowChased', FLOWSP:'flowSpHeavy',
  ARCSWEEP:'arcSweep', ARCSWEPT:'arcSwept', ARCCOMEBACK:'arcComeback',
  ARCSWEAT:'arcSweat', ARCCHOKE:'arcChoke', ARCSLIP:'arcSlip',
};

/* 자리표시자.
   이름은 **받침 없는 글자로 끝나야** RO() 가 「로」를 준다 —
   기존 표가 "%s로 계속 당하는군" 이므로 그 쪽에 맞춘다. 앞에 사용자영역 문자를 붙여
   진짜 대사와 절대 겹치지 않게 한다. */
const S_NAME = '\u{E000}가';
const S_TEXT = '\u{E001}본문';
const NUM = { n: 917531, g: 917533, w: 917537, dmg: 917541 };

/* 이벤트별 페이로드. BASE 에 얹는다.
   sup·dmg·ctx·rec 는 함수 안 분기를 고르는 열쇠다. */
const BASE = {
  name: S_NAME, who: S_NAME, text: S_TEXT,
  n: NUM.n, g: NUM.g, w: NUM.w, dmg: NUM.dmg,
  sup: false, rec: false,
};
const OVER = {
  MOVE:      { sup: true },              // sup 아니면 null 을 돌려주는 화자가 있다
  MOVEHIT:   { dmg: NUM.dmg },           // 강타 갈래 (d>=12)
  MOVEHITL:  { dmg: 3 },                 // 약타 갈래
  MOVEDOWN:  { name: S_NAME },           // 기술 이름이 있는 갈래
  MOVEDOWNA: { name: '' },               // 이름 없는 갈래 — %s 가 들어가면 안 된다
  MOVEKO:    { name: S_NAME },
  MUSE_B:  { ctx: 'battle' },
  MUSE_Q:  { ctx: 'quote' },
  MUSE_M:  { ctx: 'menu' },
  SURV:    { rec: false },    // rec 면 신기록 갈래로 새 버린다
};

/* ── 자리 뜻이 정해진 이벤트 ────────────────────────────────────────
   ss2comm.c 의 emit_ex(ev, vsel, …) 가 vsel 을 0 이상으로 주는 자리들이다.
   그런 이벤트는 **번호마다 뜻이 있어서 정렬하면 안 된다.**

     emit_ex(EV_SURV,    rec?0:(surv>=10?1:(surv>=7?2:(surv>=3?3:-1))), …)
     emit_ex(EV_RECORD,  sess_wins*2>=sess_games?0:1, …)
     emit_ex(EV_STAGE,   (stage+1)>=8?0:((stage+1)>=5?1:-1), …)
     emit_ex(EV_STREAK,  sess_streak>=5?0:-1, …)
     emit_ex(EV_MOVEHIT, d>=12?0:2, …)
     emit_ex(EV_MOVEDOWN, 0 …) / emit_ex(EV_MOVEDOWN, 1 …)   ← 1 은 who=0 (이름 없음)
     emit_ex(EV_MOVEKO,  0 …)

   그런데 emit_ex 는 `cand[vsel < n ? vsel : n-1]` 로 **넘치는 번호를 마지막 것으로 자른다.**
   그래서 자리를 안 채우면 조용히 엉뚱한 말이 나온다 (져도 "술맛 나는 날이군" 같은 것).
   여기서는 번호마다 알맞은 갈래를 골라 **그 자리에 그대로 박는다.**
   자리를 채우고 남은 변주는 뒤에 붙인다 — 나중에 vsel 을 -1 로 바꾸면 바로 쓰인다.

   slots: 그 번호에 와야 하는 페이로드. null 이면 「그 갈래에서 아무거나」가 아니라
   「이 번호는 C 가 안 읽는다」는 뜻이고, 앞뒤 자리를 맞추려고 자리만 잡아 둔다. */
const SLOTS = {
  /* 조건이 「이상」으로 열려 있는 자리는 큰 자리표시자를 쓴다 (그래야 %d 로 깨끗이 지워진다).
     7~9 처럼 구간이 좁은 자리만 어쩔 수 없이 실제 수를 넣는다. */
  SURV:     [{ rec: true, n: NUM.n }, { rec: false, n: NUM.n }, { rec: false, n: 9 }, { rec: false, n: 6 }],
  RECORD:   [{ g: NUM.g, w: NUM.w }, { g: NUM.g, w: 400001 }],   // 0 이김(w*2>=g) · 1 짐
  STAGE:    [{ n: NUM.n }, { n: 6 }],
  STREAK:   [{ n: NUM.n }],
};

/* EVMAXV — 한 칸에 들어가는 변주의 최대 개수.
   기본은 **필요한 만큼 자동으로 맞춘다.** 10 으로 굳혀 두면 대사가 조용히 잘려 나간다
   (실제로 charselChat 이 12·14 개라 옛 표에서 넉 줄이 사라져 있었다).
   ss2comm.c 는 cand[EVMAXV] 와 i<EVMAXV 만 쓰므로 올려도 안전하다.
   굳이 고정하려면 --evmaxv 10 을 준다 — 그때는 잘린 것을 하나하나 알려 준다. */
const EVMAXV_MIN = 10;
const STEPS = 120;

function serve(root) {
  const types = {
    '.html': 'text/html;charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
    '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml',
    '.wasm': 'application/wasm', '.woff2': 'font/woff2',
  };
  const srv = http.createServer((req, res) => {
    const rel = decodeURIComponent(req.url.split('?')[0]);
    const p = path.join(root, rel);
    if (!p.startsWith(root)) { res.writeHead(403); res.end(); return; }
    fs.readFile(p, (e, buf) => {
      if (e) { res.writeHead(404); res.end(); return; }
      res.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' });
      res.end(buf);
    });
  });
  return new Promise(r => srv.listen(0, '127.0.0.1', () => r({ srv, port: srv.address().port })));
}

function cstr(s) {
  return '"' + s.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n') + '"';
}

/* 실행기의 **순수 데이터 리터럴**(CHARS / CHAR_BY_IDX / CHAR_LORE / FACE_ROM)을 꺼낸다.
   이 넷은 __ss2 로 안 나오는데, 함수가 아니라 숫자·문자열뿐인 표라
   리터럴 원문을 그대로 평가하면 정확하다. (스텁을 짜는 것과는 다르다 —
   짜깁기가 아니라 원문 그 자체다.) 실행기가 나중에 이 넷을 __ss2 로 내보내면
   그때는 페이지에서 바로 읽는 편이 낫다. */
function litFrom(src, name) {
  const m = new RegExp('const\\s+' + name + '\\s*=\\s*').exec(src);
  if (!m) throw new Error(`실행기에서 ${name} 를 못 찾았다`);
  const i = m.index + m[0].length;
  let d = 0, instr = null, esc = false, k = i;
  for (; k < src.length; k++) {
    const c = src[k];
    if (instr) {
      if (esc) esc = false;
      else if (c === '\\') esc = true;
      else if (c === instr) instr = null;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') { instr = c; continue; }
    if (c === '[' || c === '{') d++;
    else if (c === ']' || c === '}') { d--; if (d === 0) break; }
  }
  return new Function('return ' + src.slice(i, k + 1))();
}

/* 기존 헤더에서 화자별 EV 행을 읽어 온다 (--check 대조용). */
function parseHeader(txt) {
  const rows = [];
  let cur = null;
  for (const line of txt.split('\n')) {
    if (/^ \{ \/\* \w+ \*\//.test(line)) { cur = {}; rows.push(cur); continue; }
    const r = line.match(/^\s*\/\* ([A-Z0-9_]+)\s*\*\/ \{(.*)\},\s*$/);
    if (r && cur) {
      const vals = [];
      const rx = /"((?:[^"\\]|\\.)*)"/g;
      let mm;
      while ((mm = rx.exec(r[2]))) vals.push(mm[1].replace(/\\"/g, '"').replace(/\\\\/g, '\\'));
      cur[r[1]] = vals;
    }
  }
  return rows;
}

(async () => {
  const args = process.argv.slice(2);
  const srcArg = args[0], outArg = args[1];
  if (!srcArg || !outArg) {
    console.error('usage: node tools/gen_lines.js <index.html> <out ss2comm_lines.h> [--check <기존 헤더>]');
    process.exit(2);
  }
  const ci = args.indexOf('--check');
  const checkPath = ci >= 0 ? args[ci + 1] : null;
  const ei = args.indexOf('--evmaxv');
  const pinned = ei >= 0 ? parseInt(args[ei + 1], 10) : null;

  const srcAbs = path.resolve(srcArg);
  const root = path.dirname(srcAbs);
  const { srv, port } = await serve(root);

  const { chromium } = require('playwright');
  const browser = await chromium.launch({ executablePath: process.env.SS2_CHROMIUM || undefined });
  const page = await browser.newPage();
  await page.goto(`http://127.0.0.1:${port}/${path.basename(srcAbs)}?debug=1`, { waitUntil: 'domcontentloaded' });

  let ready = false;
  for (let i = 0; i < 60; i++) {
    ready = await page.evaluate(() => !!(window.__ss2 && window.__ss2.SPEAKERS && window.__ss2.cfg));
    if (ready) break;
    await page.waitForTimeout(500);
  }
  if (!ready) {
    console.error('실행기에서 window.__ss2.SPEAKERS 를 못 찾았다. ?debug=1 로 열리는지 확인해라.');
    await browser.close(); srv.close(); process.exit(1);
  }
  await page.evaluate(() => { window.__ss2.cfg.commNames = 1; });

  const order = await page.evaluate(() => window.__ss2.SPK_ORDER);
  const koNames = await page.evaluate(() => window.__ss2.SPK_ORDER.map(k => window.__ss2.SPK_KO[k]));
  const hellos = await page.evaluate(() => window.__ss2.SPK_ORDER.map(k => window.__ss2.SPEAKERS[k].hello));
  const relObjs = await page.evaluate(() => window.__ss2.SPK_ORDER.map(k => window.__ss2.SPEAKERS[k].REL || {}));

  /* 게임 캐릭터 순서 · 소개문 · 얼굴 오프셋 — 실행기 리터럴에서 그대로 꺼낸다.
     RELLINE 과 LORE 의 두 번째 첨자는 **화자 순서가 아니라 이 순서**다. */
  const srcText = fs.readFileSync(srcAbs, 'utf8');
  const CHAR_BY_IDX = litFrom(srcText, 'CHAR_BY_IDX');
  const CHAR_LORE = litFrom(srcText, 'CHAR_LORE');
  const CHAR_ANEC = litFrom(srcText, 'CHAR_ANEC');   /* 썰 — 짧은 일화·행적 */
  const REL_SELF  = litFrom(srcText, 'REL_SELF');    /* 미러전 */
  const REL_OPPX  = litFrom(srcText, 'REL_OPP');     /* 화자 → 맞은편 (빈칸 메움) */
  const REL_MEX   = litFrom(srcText, 'REL_ME');      /* 화자 → 내 편 */
  const REL_YOUX  = litFrom(srcText, 'REL_YOU');     /* 화자 → 사람 */
  const WEAP_V    = litFrom(srcText, 'WEAP_VOICE');  /* 무기 소회 — 화자 목소리 */
  const REL_GAND  = litFrom(srcText, 'REL_GANDHARA'); /* 표 밖 개체 */
  const CHAR_WEAP = litFrom(srcText, 'CHAR_WEAP');   /* 무기 소회 */
  const FACE_ROM = litFrom(srcText, 'FACE_ROM');
  const roster = [];
  for (let i = 0; ; i++) { if (!(i in CHAR_BY_IDX)) break; roster.push(CHAR_BY_IDX[i]); }

  const warn = [];
  const table = {};

  /* 페이로드 하나로 그 갈래의 변주를 전부 뽑아 온다. */
  async function collect(spk, ev, extraPayload) {
    const key = MAP[ev];
    const payload = Object.assign({}, BASE, OVER[ev] || {}, extraPayload || {});
    const res = await page.evaluate(({ spk, key, payload, steps }) => {
        const S = window.__ss2.SPEAKERS[spk];
        const fn = S && S[key];
        if (typeof fn !== 'function') return { missing: true, out: [], extra: false };
        const seen = new Set(), out = [];
        const real = Math.random;
        const push = v => {
          if (v == null) return;
          const s = Array.isArray(v) ? v[0] : v;
          if (typeof s !== 'string' || !s.length) return;
          if (!seen.has(s)) { seen.add(s); out.push(s); }
        };
        let extra = false;
        for (const st of ['s', 'b']) {
          window.__ss2.cfg.style = st;
          for (let i = 0; i < steps; i++) {
            Math.random = () => (i + 0.5) / steps;
            try { push(fn(payload)); } catch (e) { /* 안 쓰이는 갈래 */ }
          }
          Math.random = real;
          const before = out.length;
          for (let i = 0; i < 3000; i++) { try { push(fn(payload)); } catch (e) {} }
          if (out.length > before) extra = true;   // 훑기가 놓친 조합이 있다
        }
        Math.random = real;
        return { missing: false, out, extra };
      }, { spk, key, payload, steps: STEPS });

    if (res.missing) { warn.push(`${spk}.${key} 없음 (EV_${ev})`); return null; }
    if (res.extra) warn.push(`${spk}.EV_${ev}: 훑기가 놓친 조합이 있다 (pick 이 둘 이상 겹친 자리)`);
    /* 숫자는 **이번 호출에 실제로 넣은 값**을 지운다.
       분기를 고르려고 작은 수를 넣어야 하는 자리가 있어서(예: 7연승 갈래는 7~9 뿐),
       고정 자리표시자만으로는 부족하다. 큰 값부터 지워야 부분 일치로 깨지지 않는다. */
    const nums = Object.values(payload).filter(v => typeof v === 'number')
      .sort((a, b) => String(b).length - String(a).length || b - a);
    const vals = [];
    for (const raw of res.out) {
      let t = raw.split(S_NAME).join('%s');
      if (S_TEXT) t = t.split(S_TEXT).join('%s');
      for (const v of nums) t = t.split(String(v)).join('%d');
      if (!vals.includes(t)) vals.push(t);
    }
    vals.sort();                                     // 순서 고정 — diff 가 읽히게
    return vals;
  }

  for (const spk of order) {
    table[spk] = {};
    for (const ev of EV) {
      const slots = SLOTS[ev];
      if (!slots) {                                  // C 가 무작위로 고르는 칸 — 정렬해서 넣는다
        table[spk][ev] = (await collect(spk, ev, null)) || [];
        continue;
      }
      /* 자리 뜻이 정해진 칸 — 번호마다 알맞은 갈래를 박는다. 정렬하지 않는다.
         emit_ex 가 빈 칸을 건너뛰며 압축하므로 **중간을 비워 두면 뒤 번호가 밀린다.**
         그래서 C 가 안 읽는 자리도 같은 갈래의 다른 변주로 반드시 채운다. */
      const perSlot = [];
      for (const s of slots) perSlot.push(s ? ((await collect(spk, ev, s)) || []) : null);
      const row = [], used = new Set();
      for (let i = 0; i < perSlot.length; i++) {
        const pool = perSlot[i] || perSlot.find(p => p && p.length) || [];
        let pickOne = pool.find(x => !used.has(x));
        if (pickOne === undefined) pickOne = pool[0];
        if (pickOne === undefined) {
          warn.push(`${spk}.EV_${ev}: ${i}번 자리를 채울 대사가 없다 — 앞 자리로 메웠다`);
          pickOne = row[row.length - 1] || '';
        }
        row.push(pickOne); used.add(pickOne);
      }
      const rest = [];
      for (const p of perSlot) for (const x of (p || [])) if (!used.has(x) && !rest.includes(x)) rest.push(x);
      rest.sort();
      table[spk][ev] = row.concat(rest);
    }
  }

  await browser.close();
  srv.close();

  /* 상한을 정한다. 기본은 필요한 만큼 — 대사가 조용히 사라지는 것을 막는다. */
  let need = 0, needAt = '';
  for (const spk of order) for (const ev of EV) {
    if (table[spk][ev].length > need) { need = table[spk][ev].length; needAt = `${spk}.EV_${ev}`; }
  }
  const EVMAXV = pinned || Math.max(EVMAXV_MIN, need);
  if (pinned && need > pinned) {
    for (const spk of order) for (const ev of EV) {
      const v = table[spk][ev];
      if (v.length > pinned) {
        warn.push(`${spk}.EV_${ev}: 변주 ${v.length}개인데 --evmaxv ${pinned} 라 ${v.length - pinned}줄 버렸다 → ${v.slice(pinned).join(' / ')}`);
        table[spk][ev] = v.slice(0, pinned);
      }
    }
  }
  console.log(`EVMAXV = ${EVMAXV} (제일 많은 칸: ${needAt} ${need}개)`);

  /* 화자끼리 똑같은 대사를 쓰고 있으면 알려 준다.
     「열다섯 목소리가 서로 다르다」가 이 프로젝트의 약속이고 test_flow.sh 도 그걸 본다.
     정렬해서 넣기 때문에, 겹친 대사가 하필 맨 앞이면 여러 화자가 같은 말로 시작하게 된다. */
  let dupAll = 0;
  const dupLines = [];
  for (const ev of EV) {
    const who = new Map(), lead = new Map();
    for (const spk of order) {
      const v = table[spk][ev];
      if (v.length === 1 && /^%[sd]$/.test(v[0])) continue;   // REL·LORE 처럼 통째로 넘겨받는 칸은 겹쳐도 정상
      v.forEach((s, i) => {
        if (!who.has(s)) who.set(s, []);
        who.get(s).push(spk);
        if (i === 0) { if (!lead.has(s)) lead.set(s, []); lead.get(s).push(spk); }
      });
    }
    for (const [s, list] of who) if (list.length > 1) { dupAll++; dupLines.push(`  EV_${ev} ×${list.length} [${list.join(' ')}] ${s}`); }
    for (const [s, list] of lead) {
      if (list.length > 1) warn.push(`EV_${ev}: ${list.join(', ')} 가 **똑같은 말로 시작한다** — "${s}" (정렬하면 맨 앞에 온다. 실행기에서 이 줄을 갈라 줘라)`);
    }
  }
  console.log(`화자끼리 겹치는 대사 ${dupAll}건 (그중 맨 앞에 오는 것은 위 주의로 따로 뽑았다). 전부 보려면 --dups`);
  if (args.includes('--dups')) console.log(dupLines.join('\n'));

  const L = [];
  L.push('/* ss2comm_lines.h — 해설 대사표. **자동 생성 파일이다. 손으로 고치지 마라.**');
  L.push('   tools/gen_lines.js 가 실행기(index.html)의 SPEAKERS 를 그대로 읽어 뽑는다.');
  L.push('   원본(브라우저판)이 바뀌면 다시 돌린다:');
  L.push('     node tools/gen_lines.js index.html <이 파일>');
  L.push('   변주는 정렬해서 넣는다 — 순서가 흔들리면 diff 를 읽을 수 없다.');
  L.push('   %s = 이름·상대·본문, %d = 숫자. */');
  L.push('#ifndef SS2COMM_LINES_H');
  L.push('#define SS2COMM_LINES_H');
  L.push('');
  L.push(`#define SS2COMM_SPK_N ${order.length}`);
  L.push('');
  L.push('enum {');
  for (let i = 0; i < EV.length; i += 6) L.push('  ' + EV.slice(i, i + 6).map(e => 'EV_' + e).join(', ') + ',');
  L.push('  EV_N');
  L.push('};');
  L.push('');
  L.push(`#define EVMAXV ${EVMAXV}`);
  L.push('');
  L.push('static const char *const SPK_NAME[SS2COMM_SPK_N] = {');
  L.push('  ' + koNames.map(cstr).join(', '));
  L.push('};');
  L.push('');
  L.push('static const char *const HELLO[SS2COMM_SPK_N] = {');
  for (const h of hellos) L.push('  ' + cstr(h) + ',');
  L.push('};');
  L.push('');
  L.push('static const char *LINES[SS2COMM_SPK_N][EV_N][EVMAXV] = {');
  for (const spk of order) {
    L.push(` { /* ${spk} */`);
    for (const ev of EV) {
      const v = table[spk][ev];
      const cells = v.map(cstr).concat(Array(EVMAXV - v.length).fill('0'));
      L.push(`  /* ${ev.padEnd(11)} */ {${cells.join(',')}},`);
    }
    L.push(' },');
  }
  L.push('};');
  L.push('');

  /* 상대별 한마디 — [화자][게임 캐릭터 번호]. 없으면 0. */
  L.push(`static const char *RELLINE[SS2COMM_SPK_N][${roster.length}] = {`);
  for (const [si, spk] of order.entries()) {
    const cells = roster.map(cid => {
      const v = relObjs[si][cid];
      return v ? cstr(v) : '0';
    });
    L.push(` { /* ${spk.padEnd(9)} */ ${cells.join(', ')} },`);
  }
  L.push('};');
  L.push('');

  L.push('/* 초상(얼굴) 타일의 롬 파일 오프셋 — 화자 순서. 그림은 배포물에 없고 사용자 롬에서 그린다. */');
  L.push('#define SS2COMM_FACE_ROM_INIT { \\');
  order.forEach((spk, i) => {
    const f = FACE_ROM[spk];
    if (!f) throw new Error(`FACE_ROM 에 ${spk} 가 없다`);
    const pal = f[1].map(v => '0x' + v.toString(16).toUpperCase().padStart(4, '0')).join(',');
    const tail = i === order.length - 1 ? ' }' : ', \\';
    L.push(`  { ${f[0]}, {${pal}}, ${f[2]} }  /* ${spk} */${tail}`);
  });
  L.push('');

  /* 캐릭터 한 줄 소개 — 게임 캐릭터 순서. */
  L.push(`static const char *LORE[${roster.length}] = {`);
  for (const cid of roster) {
    const v = CHAR_LORE[cid];
    L.push('  ' + (v && v[0] ? cstr(v[0]) : '0') + ',');
  }
  L.push('};');
  L.push('');

  /* 썰과 무기 소회 — 캐릭터 순서. 빈칸은 0 으로 채워 자리를 맞춘다.
     대사표(LINES)와 달리 **화자별이 아니라 캐릭터별**이다 —
     누가 해설하든 「그 사람에 대한 이야기」는 같다. */
  const tbl = (name, src, wide) => {
    L.push(`static const char *${name}[${roster.length}][${wide}] = {`);
    for (const cid of roster) {
      const v = (src && src[cid]) || [];
      const cells = [];
      for (let i = 0; i < wide; i++) cells.push(v[i] ? cstr(v[i]) : '0');
      L.push('  {' + cells.join(',') + '},   /* ' + cid + ' */');
    }
    L.push('};');
    L.push('');
  };
  const anecW = Math.max(1, ...roster.map(c => ((CHAR_ANEC && CHAR_ANEC[c]) || []).length));
  const weapW = Math.max(1, ...roster.map(c => ((CHAR_WEAP && CHAR_WEAP[c]) || []).length));
  L.push(`#define SS2COMM_ANEC_N ${anecW}`);
  L.push(`#define SS2COMM_WEAP_N ${weapW}`);
  /* 화자별 한 줄짜리 표 — 미러전 / 표 밖 개체 */
  const one = (name, src) => {
    L.push(`static const char *${name}[SS2COMM_SPK_N] = {`);
    for (const sp of order) L.push('  ' + ((src && src[sp]) ? cstr(src[sp]) : '0') + ',   /* ' + sp + ' */');
    L.push('};');
    L.push('');
  };
  /* 관계 표 셋 — 화자 × 캐릭터. RELLINE(기존 SPEAKERS[*].REL)에 REL_OPP 를 덮어
     빈칸을 메우고, REL_ME 는 따로 낸다. */
  const rel2 = (name, primary, fallback) => {
    L.push(`static const char *${name}[SS2COMM_SPK_N][${roster.length}] = {`);
    for (const sp of order) {
      const row = roster.map(cid => {
        const v = (primary && primary[sp] && primary[sp][cid])
               || (fallback && fallback[sp] && fallback[sp][cid]);
        return v ? cstr(v) : '0';
      });
      L.push('  {' + row.join(',') + '},   /* ' + sp + ' */');
    }
    L.push('};');
    L.push('');
  };
  const relSrc = {};
  order.forEach((sp, i) => { relSrc[sp] = relObjs[i] || {}; });   /* 페이지에서 이미 떠 온 것 */
  rel2('RELOPP', REL_OPPX, relSrc);
  rel2('RELME',  REL_MEX,  null);
  rel2('WEAPV',  WEAP_V,   null);   /* 무기 소회: 화자 15 × 상대 15 */
  {
    const w = Math.max(1, ...order.map(sp => ((REL_YOUX && REL_YOUX[sp]) || []).length));
    L.push(`#define SS2COMM_RELYOU_N ${w}`);
    L.push(`static const char *RELYOU[SS2COMM_SPK_N][${w}] = {`);
    for (const sp of order) {
      const v = (REL_YOUX && REL_YOUX[sp]) || [];
      const cells = []; for (let i = 0; i < w; i++) cells.push(v[i] ? cstr(v[i]) : '0');
      L.push('  {' + cells.join(',') + '},   /* ' + sp + ' */');
    }
    L.push('};');
    L.push('');
  }
  one('RELSELF', REL_SELF);
  one('RELGAND', REL_GAND);
  tbl('ANEC', CHAR_ANEC, anecW);
  tbl('WEAP', CHAR_WEAP, weapW);

  L.push('#endif');
  fs.writeFileSync(path.resolve(outArg), L.join('\n') + '\n', 'utf8');
  console.log(`썼다: ${outArg}  (화자 ${order.length} × 이벤트 ${EV.length})`);
  for (const w of warn) console.log('  주의: ' + w);

  if (checkPath) {
    const oldTab = parseHeader(fs.readFileSync(checkPath, 'utf8'));
    let same = 0, diff = 0;
    const report = [];
    for (const [si, spk] of order.entries()) {
      for (const ev of EV) {
        const a = new Set(table[spk][ev]);
        const b = new Set((oldTab[si] && oldTab[si][ev]) || []);
        const onlyNew = [...a].filter(x => !b.has(x));
        const onlyOld = [...b].filter(x => !a.has(x));
        if (!onlyNew.length && !onlyOld.length) { same++; continue; }
        diff++;
        report.push(`  다름 ${spk}.EV_${ev}`);
        for (const x of onlyOld) report.push(`    옛것에만: ${x}`);
        for (const x of onlyNew) report.push(`    새것에만: ${x}`);
      }
    }
    console.log(report.join('\n'));
    console.log(`\n집합 일치 ${same} / 다름 ${diff} (전체 ${order.length * EV.length})`);
  }
})();
