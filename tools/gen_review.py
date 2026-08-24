#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""검수 페이지 생성기 — 대사표·픽셀 폰트·초상 주소를 C 헤더에서 뽑아
   브라우저에서 열리는 review.html 한 장을 만든다.

     python3 tools/gen_review.py <ss2-sp-core/src 경로> <출력 review.html>

   왜 있나: 검수를 사람이 게임을 다 돌려 보며 할 수는 없다. 이 페이지는
   APK 와 **같은 폰트·같은 줄바꿈·같은 띠 규격**으로 대사를 전부 그려 보여 준다.
   롬 파일을 넣으면 초상도 실물로 뜬다(파일은 브라우저 안에서만 읽는다 — 어디로도
   전송되지 않고, 페이지에는 그림이 아니라 주소 숫자만 들어 있다)."""
import io, json, os, re, sys

D   = sys.argv[1] if len(sys.argv) > 1 else "."
OUT = sys.argv[2] if len(sys.argv) > 2 else "review.html"
def rd(fn): return io.open(os.path.join(D, fn), encoding="utf-8").read()
lines_h = rd("ss2comm_lines.h"); comm_c = rd("ss2comm.c")
f11_h = rd("ss2comm_font11.h"); f8_h = rd("ss2comm_font.h")
icon_h = rd("ss2comm_icon.h")
STR = r'"((?:[^"\\]|\\.)*)"'

# ── 폰트 ──
F11 = [[int(m[0],16), int(m[1])] + [int(x,16) for x in m[2].split(",")]
       for m in re.findall(r"\{0x([0-9A-Fa-f]{4}),\s*(\d+),\{([^}]*)\}\}", f11_h)]
F8  = [[int(m[0],16)] + [int(x,16) for x in m[1].split(",")]
       for m in re.findall(r"\{0x([0-9A-Fa-f]{4}),\{([^}]*)\}\}", f8_h)]

# ── 화자·이벤트·대사표 ──
ev_blk = re.search(r"enum \{(.*?)EV_N", lines_h, re.S).group(1)
EV = [x.strip()[3:] for x in re.sub(r"/\*.*?\*/","",ev_blk,flags=re.S).replace("\n"," ").split(",") if x.strip()]
SPK_KO = re.findall(STR, re.search(r"SPK_NAME\[SS2COMM_SPK_N\] = \{(.*?)\};", lines_h, re.S).group(1))
m = re.search(r"LINES\[SS2COMM_SPK_N\]\[EV_N\]\[EVMAXV\] = \{(.*?)\n\};", lines_h, re.S)
SPK_ID = re.findall(r"\n \{ /\* (\w+) \*/", m.group(1))
LINES = []
for blk in re.split(r"\n \{ /\* \w+ \*/", m.group(1))[1:]:
    d = {}
    for name, body in re.findall(r"/\* ([A-Z0-9_]+)\s*\*/ \{(.*?)\},\n", blk):
        d[name] = re.findall(STR, body)
    LINES.append(d)
CHARNAME = re.findall(STR, re.search(r"CHARNAME\[15\] = \{(.*?)\};", comm_c, re.S).group(1))
EVHIT = dict(re.findall(r"\[EV_(\w+)\s*\]\s*=\s*(\d+)", re.search(r"EVHIT\[EV_N\] = \{(.*?)\n\};", comm_c, re.S).group(1)))

def table2(name, src):
    mm = re.search(r"static const char \*%s\[SS2COMM_SPK_N\]\[\d+\] = \{(.*?)\n\};" % name, src, re.S)
    out = []
    for row in re.findall(r"\{(.*?)\},\s*/\* \w+ \*/", mm.group(1), re.S):
        cells, cur, inq, esc = [], "", False, False
        for ch in row:
            if esc: cur += ch; esc = False; continue
            if ch == "\\": cur += ch; esc = True; continue
            if ch == '"': inq = not inq; cur += ch; continue
            if ch == "," and not inq: cells.append(cur.strip()); cur = ""; continue
            cur += ch
        cells.append(cur.strip())
        out.append([re.match(STR, c).group(1) if c.startswith('"') else None for c in cells])
    return out
def table1(name, src):
    mm = re.search(r"static const char \*%s\[SS2COMM_SPK_N\] = \{(.*?)\n\};" % name, src, re.S)
    return [ (re.match(STR, c.strip()).group(1) if c.strip().startswith('"') else None)
             for c in re.findall(r"\n\s*(.+?),\s*/\* \w+ \*/", mm.group(1)) ]
RELOPP = table2("RELOPP", lines_h); RELME = table2("RELME", lines_h)
WEAPV  = table2("WEAPV",  lines_h); RELYOU = table2("RELYOU", lines_h)
RELSELF = table1("RELSELF", lines_h); RELGAND = table1("RELGAND", lines_h)
def tblN(name):
    mm = re.search(r"static const char \*%s\[\d+\]\[\d+\] = \{(.*?)\n\};" % name, lines_h, re.S)
    return [re.findall(STR, row) for row in re.findall(r"\{(.*?)\},", mm.group(1), re.S)]
ANEC = tblN("ANEC"); WEAPF = tblN("WEAP")
HELLO = re.findall(STR, re.search(r"HELLO\[SS2COMM_SPK_N\] = \{(.*?)\};", lines_h, re.S).group(1))
REF_ROUND = re.findall(STR, re.search(r"REF_ROUND\[3\] = \{(.*?)\};", comm_c, re.S).group(1))
CHARFULL  = re.findall(STR, re.search(r"CHARFULL\[15\] = \{(.*?)\};", comm_c, re.S).group(1))

# ── 초상 주소 ──
flat = icon_h.replace("\\\n", " ")
ICON = []
for mm in re.finditer(r"\{\s*(\d+),\s*\{([\d,\s]+)\},\s*\{([^}]*)\},\s*\{([^}]*)\}\s*\},?\s*/\* (\w+) \*/", flat):
    ICON.append(dict(bg=int(mm.group(1)),
                     fg=[int(x) for x in mm.group(2).split(",")],
                     palF=[int(x,16) for x in mm.group(3).split(",")],
                     palB=[int(x,16) for x in mm.group(4).split(",")]))
def nums(name):
    t = re.search(name + r"\[16\] = \{(.*?)\}", comm_c, re.S).group(1)
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    return [int(x) for x in t.replace("\n", " ").split(",") if x.strip()]
KBG = nums("KUROKO_BG"); KFG = nums("KUROKO_FG")
KPF = [int(x,16) for x in re.search(r"KUROKO_PAL_FG\[4\] = \{(.*?)\}", comm_c).group(1).split(",")]
KPB = [int(x,16) for x in re.search(r"KUROKO_PAL_BG\[4\] = \{(.*?)\}", comm_c).group(1).split(",")]
FACE = [[int(a), int(b)] for a, b in
        re.findall(r"\{\s*(\d+),\s*\{[^}]*\},\s*(\d+)\s*\}", re.search(r"SS2COMM_FACE_ROM_INIT \{(.*?)\n\n", lines_h, re.S).group(1))]

DATA = dict(F11=F11, F8=F8, EV=EV, EVHIT=EVHIT, SPK_ID=SPK_ID, SPK_KO=SPK_KO,
            LINES=LINES, CHARNAME=CHARNAME, RELOPP=RELOPP, RELME=RELME, WEAPV=WEAPV,
            RELYOU=RELYOU, RELSELF=RELSELF, RELGAND=RELGAND, ANEC=ANEC, WEAPF=WEAPF,
            HELLO=HELLO, REF_ROUND=REF_ROUND, CHARFULL=CHARFULL,
            ICON=ICON, KBG=KBG, KFG=KFG, KPF=KPF, KPB=KPB, FACE=FACE)

HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SS2 해설 검수</title>
<style>
 body{background:#14161c;color:#dde;font:15px/1.5 system-ui,sans-serif;margin:0;padding:12px}
 h1{font-size:17px;margin:4px 0 10px} .mut{color:#89a}
 .tabs{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}
 .tabs button{background:#232735;color:#dde;border:1px solid #39405a;border-radius:8px;padding:8px 14px;font-size:15px}
 .tabs button.on{background:#3450a0;border-color:#5878d8}
 select,input[type=text]{background:#1b1f2b;color:#dde;border:1px solid #39405a;border-radius:6px;padding:6px 8px;font-size:15px;max-width:46vw}
 button.sm{background:#2a3042;color:#dde;border:1px solid #39405a;border-radius:6px;padding:6px 10px;font-size:14px}
 canvas{image-rendering:pixelated;display:block;margin:6px 0;border:1px solid #2a3042;max-width:100%}
 .list{max-height:44vh;overflow:auto;border:1px solid #2a3042;border-radius:8px;margin-top:8px}
 .list div{padding:6px 10px;border-bottom:1px solid #20242f;cursor:pointer}
 .list div:active,.list div.on{background:#2c3a5e}
 .cell{padding:6px 8px;border-bottom:1px solid #20242f;cursor:pointer}
 .k{color:#8fb0ff;margin-right:6px}
 .grid{max-height:52vh;overflow:auto;border:1px solid #2a3042;border-radius:8px}
 .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}
 .ok{color:#7fd88f}.bad{color:#ff8f8f}
 #icons{display:flex;flex-wrap:wrap;gap:8px}
 #icons figure{margin:0;text-align:center;font-size:12px;color:#9ab}
 .note{font-size:13px;color:#89a;margin:6px 0}
 mark{background:#c9921b;color:#000;border-radius:2px}
 .list div.cur{outline:2px solid #e8b64a;outline-offset:-2px}
</style></head><body>
<h1>SS2 해설 검수 <span class="mut">— APK와 같은 폰트·줄바꿈·띠 규격으로 그립니다</span></h1>
<div class="row"><label>롬 파일(선택): <input type="file" id="rom"></label> <span id="romst" class="mut">없으면 초상 자리만 표시</span></div>
<div class="note">롬은 이 브라우저 안에서만 읽습니다 — 어디로도 전송되지 않습니다. 페이지에는 그림이 아니라 주소 숫자만 들어 있습니다.</div>
<div class="tabs">
 <button data-t="t1" class="on">대사표</button><button data-t="t2">관계·썰</button>
 <button data-t="t3">한 판 재생</button><button data-t="t4">초상</button><button data-t="t5">전체 목록</button>
</div>

<div id="t1">
 <div class="row">
  <select id="s1"></select><select id="e1"></select>
  <input type="text" id="q1" placeholder="검색 (전체 화자·이벤트)">
  <button class="sm" id="auto1">▶ 전부 훑기</button>
 </div>
 <canvas id="c1" width="480" height="96"></canvas>
 <div class="list" id="l1"></div>
</div>

<div id="t2" hidden>
 <div class="row"><select id="s2"></select> <span class="mut">화자를 고르면 상대 15명에 대한 관계·내편·무기·썰이 전부 나옵니다. 줄을 누르면 위 띠에 그립니다.</span></div>
 <canvas id="c2" width="480" height="96"></canvas>
 <div class="grid" id="g2"></div>
</div>

<div id="t3" hidden>
 <div class="row">
  <label>해설 <select id="s3"></select></label>
  <label>내 캐릭 <select id="m3"></select></label>
  <label>상대 <select id="o3"></select></label>
  <button class="sm" id="play3">▶ 재생</button>
  <button class="sm" data-sp="1">×1</button><button class="sm" data-sp="2">×2</button><button class="sm" data-sp="4">×4</button>
 </div>
 <div class="mut">위 = 해설창 · 아래 = 심판 칸. 유가·간다라전에는 심판이 서지 않습니다. 간격은 실기 규칙 그대로 — 전투 밖 1.6초, 전투 중 4.5초.</div>
 <canvas id="c3" width="480" height="192"></canvas>
 <div id="log3" class="list" style="max-height:30vh"></div>
</div>

<div id="t5" hidden>
 <div class="row">
  <select id="mode5">
   <option value="all">전체 (화자순)</option>
   <option value="char">캐릭터별 (그 사람에 대한 말)</option>
   <option value="ev">상황별</option>
  </select>
  <input type="text" id="q5" placeholder="거르기 (화자·칸·대사)">
  <span id="n5" class="mut"></span>
  <button class="sm" id="txt5">TXT 저장</button>
 </div>
 <div class="row">
  <input type="text" id="find5" placeholder="검색 — 목록은 그대로, 자리로 점프">
  <button class="sm" id="prev5">◀ 이전</button>
  <button class="sm" id="next5">다음 ▶</button>
  <span id="fn5" class="mut"></span>
 </div>
 <div style="position:sticky;top:0;background:#14161c;z-index:2"><canvas id="c5" width="480" height="96"></canvas></div>
 <div class="list" id="l5" style="max-height:62vh"></div>
</div>

<div id="t4" hidden>
 <div class="note">롬을 넣으면 15명 + 쿠로코 초상이 실물로 뜹니다. 체크섬이 안 맞으면 그 캐릭터는 건너뜁니다.</div>
 <div id="icons"></div>
</div>

<script>
const D = __DATA__;
/* ── 폰트 ── */
const F11={},F8={};
for(const g of D.F11) F11[g[0]]=[g[1],g.slice(2)];
for(const g of D.F8)  F8[g[0]]=g.slice(1);
const adv11=cp=>F11[cp]?F11[cp][0]:(cp<128?6:11);
const adv8 =cp=>cp<128?4:8;
const cps=s=>[...s].map(c=>c.codePointAt(0));
function wrap(s,maxw,adv){
  const seg=[]; let cur="",w=0,sp=-1,spw=0;
  for(const ch of s){
    const a=adv(ch.codePointAt(0));
    if(w+a>maxw && cur){
      if(sp>0){ seg.push(cur.slice(0,sp)); cur=cur.slice(sp).replace(/^ /,""); w=0; for(const c2 of cur) w+=adv(c2.codePointAt(0)); }
      else { seg.push(cur); cur=""; w=0; }
      sp=-1;
      if(seg.length>=3) break;
    }
    cur+=ch; w+=a; if(ch===" "){sp=cur.length; spw=w;}
  }
  if(cur && seg.length<3) seg.push(cur);
  return seg;
}
const c565=v=>[((v>>11)&31)*255/31|0,((v>>5)&63)*255/63|0,(v&31)*255/31|0];
const WHITE=[255,255,255],GOLD=c565(0xFEA0),REF=c565(0x9E7F);
function drawGlyph(img,W,x,y,cp,col,small,shadow){
  if(small){ const g=F8[cp]; if(!g)return;
    for(let j=0;j<8;j++)for(let i=0;i<8;i++) if(g[j]&(0x80>>i)) px(img,W,x+i,y+j,col);
  }else{ const g=F11[cp]; if(!g)return;
    for(let j=0;j<13;j++)for(let i=0;i<12;i++) if(g[1][j]&(0x8000>>i)){
      if(shadow) px(img,W,x+i+1,y+j+1,[0,0,0]); else px(img,W,x+i,y+j,col); }
  }
}
function px(img,W,x,y,c){ if(x<0||x>=W||y<0||y>=img.h)return; const o=(y*W+x)*4;
  img.d[o]=c[0];img.d[o+1]=c[1];img.d[o+2]=c[2];img.d[o+3]=255; }
/* 띠 한 장(160x32) 그리기 — C 의 draw 경로 그대로 */
function renderStrip(text,{icon=null,color=WHITE}={}){
  const W=160,H=32,img={d:new Uint8ClampedArray(W*H*4),h:H};
  for(let i=3;i<W*H*4;i+=4) img.d[i]=255;
  if(icon){ for(let j=0;j<32;j++)for(let i=0;i<32;i++){ const c=icon[j*32+i]; if(c) px(img,W,2+i,j,c);} }
  else { for(let j=0;j<32;j+=2){px(img,W,2,j,[70,80,110]);px(img,W,33,j,[70,80,110]);}
         for(let i=2;i<34;i+=2){px(img,W,i,0,[70,80,110]);px(img,W,i,31,[70,80,110]);} }
  const tx0=37,x1=W-3,maxw=x1-tx0-4;
  let segs=wrap(text,maxw,adv11),small=false;
  if(segs.length>2){ segs=wrap(text,maxw,adv8); small=true; }
  const lh=small?9:13, ty=(H-segs.length*lh)/2|0;
  segs.forEach((sg,i)=>{
    const adv=small?adv8:adv11;
    let lw=0; for(const cp of cps(sg)) lw+=adv(cp);
    let x=tx0+(((x1-tx0)-lw)/2|0); if(x<tx0)x=tx0;
    if(!small) { let xx=x; for(const cp of cps(sg)){ drawGlyph(img,W,xx,ty+i*lh,cp,color,false,true); xx+=adv11(cp);} }
    let xx=x;
    for(const cp of cps(sg)){ drawGlyph(img,W,xx,ty+i*lh+(small?1:0),cp,color,small,false); xx+=adv(cp); if(xx>x1-4)break; }
  });
  return img;
}
function blit(cv,imgs){ const W=160,S=3,H=imgs.reduce((a,b)=>a+b.h,0);
  cv.width=W*S; cv.height=H*S; const g=cv.getContext("2d"); g.imageSmoothingEnabled=false;
  const off=document.createElement("canvas"); off.width=W; off.height=H;
  const og=off.getContext("2d"); let y=0;
  for(const im of imgs){ og.putImageData(new ImageData(im.d,W,im.h),0,y); y+=im.h; }
  g.drawImage(off,0,0,W*S,H*S); }
/* ── 조사 보정(미리보기용) + 서식 채움 ── */
function batchim(s){ const c=s.charCodeAt(s.length-1); if(c<0xAC00||c>0xD7A3)return -1; return (c-0xAC00)%28; }
const JOSA=[["로","으로"],["가","이"],["를","을"],["는","은"],["와","과"],["야","아"]];
function fill(fmt,ev){
  let out=fmt;
  if(out.includes("%s")){ const nm=(ev==="START")?"하오마루 대 겐주로":"츠바메가에시", i=out.indexOf("%s");
    let rest=out.slice(i+2); const b=batchim(nm);
    if(b>=0) for(const [a,bb] of JOSA){
      if(rest.startsWith(a)||rest.startsWith(bb)){
        const noB=(b===0)||(a==="로"&&b===8);
        rest=(noB?a:bb)+rest.slice(rest.startsWith(a)?a.length:bb.length); break; } }
    out=out.slice(0,i)+nm+rest; }
  out=out.replace("%d","3").replace("%d","1");
  return out;
}
/* ── 롬 → 초상 ── */
let ROM=null, ICONS=null, KICON=null;
function tile(off){ const t=[]; for(let j=0;j<8;j++){ const w=ROM[off+j*2]|(ROM[off+j*2+1]<<8);
  const r=[]; for(let i=0;i<8;i++) r.push((w>>((7-i)*2))&3); t.push(r);} return t; }
const p444=v=>[ (v&15)*17, ((v>>4)&15)*17, ((v>>8)&15)*17 ];
function buildIcons(){
  ICONS=[];
  for(const ic of D.ICON){
    const im=new Array(32*32).fill(null);
    if(ic.bg && ic.bg+256<=ROM.length){
      for(let k=0;k<16;k++){ const t=tile(ic.bg+k*16),ox=(k&3)*8,oy=(k>>2)*8;
        for(let j=0;j<8;j++)for(let i=0;i<8;i++){ const c=t[j][i]; if(c) im[(oy+j)*32+ox+i]=p444(ic.palB[c]); } }
      for(let k=0;k<16;k++){ const of=ic.fg[k]; if(!of)continue; const t=tile(of),ox=(k&3)*8,oy=(k>>2)*8;
        for(let j=0;j<8;j++)for(let i=0;i<8;i++){ const c=t[j][i]; if(c) im[(oy+j)*32+ox+i]=p444(ic.palF[c]); } } }
    ICONS.push(im);
  }
  KICON=new Array(32*32).fill(null);
  for(let k=0;k<16;k++){ const tb=tile(D.KBG[k]),ox=(k&3)*8,oy=(k>>2)*8;
    const tf=D.KFG[k]?tile(D.KFG[k]):null;
    for(let j=0;j<8;j++)for(let i=0;i<8;i++){
      const cf=tf?tf[j][i]:0, cb=tb[j][i], p=(oy+j)*32+ox+i;
      if(cf) KICON[p]=p444(D.KPF[cf]);
      else if(cb&&cb!==3) KICON[p]=p444(D.KPB[cb]); } }
}
document.getElementById("rom").onchange=async e=>{
  const f=e.target.files[0]; if(!f)return;
  ROM=new Uint8Array(await f.arrayBuffer());
  let ok=0; for(const [off,sum] of D.FACE){ let s=0; for(let i=0;i<64;i++)s=(s+ROM[off+i])&0xFFFF; if(s===sum)ok++; }
  const st=document.getElementById("romst");
  if(ok===15){ st.textContent="롬 확인 15/15 — 초상 실물로 그립니다"; st.className="ok"; buildIcons(); drawIconsTab(); redraw(); }
  else { st.textContent=`이 롬이 아닙니다 (초상 체크섬 ${ok}/15) — 초상 없이 계속`; st.className="bad"; ROM=null; }
};
/* ── UI ── */
const $=id=>document.getElementById(id);
for(const b of document.querySelectorAll(".tabs button"))
  b.onclick=()=>{ for(const x of document.querySelectorAll(".tabs button"))x.classList.remove("on");
    b.classList.add("on"); for(const t of ["t1","t2","t3","t4","t5"]) $(t).hidden=(t!==b.dataset.t); };
function opts(sel,arr){ sel.innerHTML=arr.map((n,i)=>`<option value="${i}">${n}</option>`).join(""); }
opts($("s1"),D.SPK_KO); opts($("s2"),D.SPK_KO);
/* REL·LORE 는 문장이 통째로 들어오는 통과용 칸(표에는 "%s" 뿐)이라 목록에서 뺀다 — 내용은 「관계·썰」 탭에 있다 */
$("e1").innerHTML=D.EV.map((n,i)=>({n,i})).filter(o=>o.n!=="REL"&&o.n!=="LORE").map(o=>`<option value="${o.i}">${o.n}</option>`).join("");
opts($("s3"),D.SPK_KO); opts($("m3"),D.CHARNAME);
$("o3").innerHTML=D.CHARNAME.map((n,i)=>`<option value="${i}">${n}</option>`).join("")+`<option value="-1">간다라(표 밖)</option>`;
$("s3").value=0; $("m3").value=2; $("o3").value=3;
let cur1=null;
function show1(text,ev,spk){ cur1=[text,ev,spk];
  const gold=D.EVHIT[ev]==="1"||D.EVHIT[ev]===1;
  blit($("c1"),[renderStrip(fill(text,ev),{icon:ICONS?ICONS[spk]:null,color:gold?GOLD:WHITE})]); }
function list1(){
  const s=+$("s1").value, ev=D.EV[+$("e1").value], q=$("q1").value.trim();
  const l=$("l1"); l.innerHTML="";
  const add=(t,e2,sp)=>{ const d=document.createElement("div");
    d.textContent=(q? D.SPK_KO[sp]+" · "+e2+" — " : "")+t;
    d.onclick=()=>{show1(t,e2,sp); for(const x of l.children)x.classList.remove("on"); d.classList.add("on");};
    l.appendChild(d); };
  if(q){ D.LINES.forEach((tbl,sp)=>{ for(const e2 in tbl) for(const t of tbl[e2]) if(t.includes(q)) add(t,e2,sp); }); }
  else for(const t of (D.LINES[s][ev]||[])) add(t,ev,s);
  if(l.firstChild) l.firstChild.click(); else blit($("c1"),[renderStrip("(이 이벤트에는 대사가 없습니다)",{})]);
}
$("s1").onchange=$("e1").onchange=list1; $("q1").oninput=list1;
let auto=null;
$("auto1").onclick=()=>{ if(auto){clearInterval(auto);auto=null;$("auto1").textContent="▶ 전부 훑기";return;}
  $("auto1").textContent="⏸ 멈춤"; const l=$("l1");
  auto=setInterval(()=>{ const on=l.querySelector(".on"); let nx=on&&on.nextSibling;
    if(!nx){ const e=$("e1"); if(+e.value+1<D.EV.length){e.value=+e.value+1;}
      else { e.value=0; $("s1").value=(+$("s1").value+1)%15; } list1(); return; }
    nx.click(); nx.scrollIntoView({block:"center"}); },1300); };
function grid2(){
  const s=+$("s2").value, g=$("g2"); g.innerHTML="";
  const add=(k,t)=>{ if(!t)return; const d=document.createElement("div"); d.className="cell";
    d.innerHTML=`<span class="k">${k}</span>${t}`;
    d.onclick=()=>blit($("c2"),[renderStrip(fill(t),{icon:ICONS?ICONS[s]:null})]); g.appendChild(d); };
  D.CHARNAME.forEach((nm,c)=>{
    add(nm+" · 맞은편",D.RELOPP[s][c]); add(nm+" · 내 편",D.RELME[s][c]); add(nm+" · 무기",D.WEAPV[s][c]);
    (D.ANEC[c]||[]).forEach((t,i)=>add(nm+" · 썰"+(i+1),t)); });
  add("미러전",D.RELSELF[s]); add("간다라",D.RELGAND[s]);
  (D.RELYOU[s]||[]).forEach((t,i)=>add("당신에게 "+(i+1),t));
}
$("s2").onchange=grid2;
/* ── 한 판 재생 ── */
let SPEED=1,playT=null;
for(const b of document.querySelectorAll('[data-sp]')) b.onclick=()=>SPEED=+b.dataset.sp;
const pick=a=>a&&a.length?a[Math.random()*a.length|0]:null;
$("play3").onclick=()=>{
  const s=+$("s3").value,m=+$("m3").value,o=+$("o3").value,L=D.LINES[s];
  const boss=(o===14||o===-1);
  const rel=o===-1?D.RELGAND[s]:(o===m?D.RELSELF[s]:D.RELOPP[s][o]);
  const who=D.CHARNAME[m]+" 대 "+(o>=0?D.CHARNAME[o]:"간다라");
  const seq=[]; const B=(t,txt,ev)=>txt&&seq.push({t,lane:0,
    txt:(txt.includes("%s")?txt.replace("%s",who):fill(txt,ev)),gold:ev&&(D.EVHIT[ev]==1)});
  const R=(t,txt)=>!boss&&txt&&seq.push({t,lane:1,txt});
  /* 박자는 실기 규칙 그대로 — 전투 밖 최소 1.6초, 전투 중 4.5초, 심판끼리 2.5초.
     0초의 썰은 뺐다(제보: 「대부분 TMI」). 그 자리는 심판의 **풀네임 대진 호명**이다 —
     심판이 안 서는 판(유가·간다라)에는 호명도 없다.
     문구(VS) 화면이 3초 서고, 판이 서는 순간(3.0s)에 구호가 0초로 바로,
     관계 대사가 그 3초 뒤에 붙는다 — 실기와 같은 배치다. */
  const FIGHT=3.0;
  R(0.0,(o>=0?D.CHARFULL[m]+" 대 "+D.CHARFULL[o]+"!":null));
  B(1.0,pick(L.START),"START");
  R(FIGHT+0.0,D.REF_ROUND[0]); B(FIGHT+3.0,rel);
  B(FIGHT+7.5,Math.random()<.5&&o>=0?D.WEAPV[s][o]:pick(L.FIRSTBLOOD),"FIRSTBLOOD");
  B(FIGHT+12.0,pick(L.FLOWTRADE),"FLOWTRADE"); B(FIGHT+16.5,pick(L.HIT),"HIT");
  B(FIGHT+21.0,pick(L.KO),"KO"); B(FIGHT+23.5,pick(L.PERFECT),"PERFECT");
  R(FIGHT+25.5,D.CHARFULL[m]+" — 훌륭하오!"); B(FIGHT+26.5,pick(L.WINSCR),"WINSCR"); B(FIGHT+29.0,pick(L.ARCSWEEP),"ARCSWEEP");
  $("log3").innerHTML=seq.map(e=>`<div>${e.t.toFixed(1)}s ${e.lane?"〔심판〕":""} ${e.txt}</div>`)
    .join("").replace(/(<div>3\.0s)/,'<div style="opacity:.6">— 3.0s 판 시작 —</div>$1');
  if(playT)cancelAnimationFrame(playT);
  const t0=performance.now();
  const step=()=>{
    const now=(performance.now()-t0)/1000*SPEED;
    let band=null,ref=null;
    for(const e of seq){ if(now>=e.t){ if(e.lane===0&&now-e.t<2.5)band=e; if(e.lane===1&&now-e.t<3.0)ref=e; } }
    const a=band?renderStrip(band.txt,{icon:ICONS?ICONS[s]:null,color:band.gold?GOLD:WHITE})
               :renderStrip("",{icon:ICONS?ICONS[s]:null});
    /* 실기 배치 그대로: 심판은 제 칸이 없고, 게임 화면 맨 위 32줄(해설창 바로 아래)에 오버레이로 뜬다 */
    const gm={d:new Uint8ClampedArray(160*152*4),h:152};
    for(let j=0;j<152;j++)for(let i=0;i<160;i++){const k=(j*160+i)*4,v=(((j>>3)&1)^((i>>3)&1))?26:16;
      gm.d[k]=v;gm.d[k+1]=v+4;gm.d[k+2]=v+12;gm.d[k+3]=255;}
    if(ref){const rs=renderStrip(ref.txt,{icon:KICON,color:REF});
      for(let j=0;j<32;j++) gm.d.set(rs.d.subarray(j*160*4,(j+1)*160*4),j*160*4);}
    blit($("c3"),[a,gm]);
    if(now<FIGHT+30) playT=requestAnimationFrame(step);
  }; step();
};
/* ── 초상 탭 ── */
function drawIconsTab(){
  const box=$("icons"); box.innerHTML="";
  const mk=(im,label)=>{ const f=document.createElement("figure");
    const cv=document.createElement("canvas"); cv.width=128; cv.height=128;
    const g=cv.getContext("2d"); g.imageSmoothingEnabled=false;
    const off=document.createElement("canvas"); off.width=32;off.height=32;
    const og=off.getContext("2d"), id=og.createImageData(32,32);
    for(let p=0;p<32*32;p++){ const c=im&&im[p]; if(c){id.data[p*4]=c[0];id.data[p*4+1]=c[1];id.data[p*4+2]=c[2];id.data[p*4+3]=255;} }
    og.putImageData(id,0,0); g.drawImage(off,0,0,128,128);
    f.appendChild(cv); f.appendChild(document.createTextNode(label)); box.appendChild(f); };
  if(!ICONS){ box.innerHTML='<div class="mut">롬을 넣으면 여기에 초상이 뜹니다.</div>'; return; }
  D.SPK_KO.forEach((n,i)=>mk(ICONS[i],n)); mk(KICON,"쿠로코(심판)");
}
/* ── 전체 목록 — 한 줄도 안 빼고 쫙. 전체 / 캐릭터별 / 상황별로 묶어 볼 수 있다 ── */
let ALL=null;
function buildAll(){
  if(ALL) return; ALL=[];
  const A=(spk,slot,txt,ev,tgt)=>txt&&ALL.push({spk,slot,txt,ev:ev||"",tgt:(tgt===undefined?-1:tgt)});
  D.REF_ROUND.forEach((t,i)=>ALL.push({spk:-1,slot:(i+1)+"판째 구호",txt:t,ev:"REF",tgt:-1}));
  D.CHARFULL.forEach((n,c)=>ALL.push({spk:-1,slot:"승자 호명",txt:n+" — 훌륭하오!",ev:"REF",tgt:c}));
  D.SPK_ID.forEach((id,sp)=>{
    A(sp,"소개",D.HELLO[sp],"HELLO");
    for(const ev of D.EV){ if(ev==="REL"||ev==="LORE")continue;
      for(const t of (D.LINES[sp][ev]||[])) A(sp,ev,t,ev); }
    D.CHARNAME.forEach((nm,c)=>{
      A(sp,nm+" 맞은편",D.RELOPP[sp][c],"맞은편",c);
      A(sp,nm+" 내 편",D.RELME[sp][c],"내 편",c);
      A(sp,nm+" 무기",D.WEAPV[sp][c],"무기 소회",c); });
    /* 미러전은 「같은 캐릭터끼리」라 특정 상대가 없다 — 화자 번호를 캐릭터 번호로
       잘못 달면 캐릭터별 묶기에서 엉뚱한 사람 밑에 낀다(실제로 그랬다) */
    A(sp,"미러전",D.RELSELF[sp],"미러전"); A(sp,"간다라",D.RELGAND[sp],"간다라");
    (D.RELYOU[sp]||[]).forEach((t,i)=>A(sp,"당신에게 "+(i+1),t,"당신에게"));
  });
  D.CHARNAME.forEach((nm,c)=>{
    (D.ANEC[c]||[]).forEach((t,i)=>A(-2,nm+" 썰"+(i+1),t,"썰",c));
    (D.WEAPF[c]||[]).forEach((t,i)=>A(-2,nm+" 무기(예비)"+(i+1),t,"무기(예비)",c)); });
}
function who5(r){ return r.spk===-1?"쿠로코":(r.spk===-2?"공용":D.SPK_KO[r.spk]); }
function list5(){
  buildAll();
  const q=$("q5").value.trim(), mode=$("mode5").value, l=$("l5"); l.innerHTML="";
  ROWS5=[]; HITS5=[]; CUR5=-1;
  const frag=document.createDocumentFragment(); let n=0, lastHead=null;
  const head=t=>{ if(t===lastHead)return; lastHead=t;
    const h=document.createElement("div");
    h.textContent="── "+t+" ──";
    h.style.cssText="background:#1d2333;color:#8fb0ff;font-weight:600;position:sticky;top:0";
    frag.appendChild(h); };
  let rows;
  if(mode==="char"){
    /* 캐릭터별: 그 사람에 대한 말 전부 — 열다섯 해설자의 관계·무기 + 공용 썰 */
    rows=[];
    D.CHARNAME.forEach((nm,c)=>{ for(const r of ALL) if(r.tgt===c) rows.push({h:nm,...r}); });
    for(const r of ALL) if(r.ev==="미러전") rows.push({h:"미러전(같은 캐릭터끼리)",...r});
    for(const r of ALL) if(r.ev==="간다라") rows.push({h:"간다라(표 밖)",...r});
  }else if(mode==="ev"){
    rows=[];
    for(const ev of D.EV){ if(ev==="REL"||ev==="LORE")continue;
      for(const r of ALL) if(r.ev===ev) rows.push({h:"상황 · "+ev,...r}); }
    for(const g of ["HELLO","맞은편","내 편","무기 소회","미러전","간다라","당신에게","썰","무기(예비)","REF"])
      for(const r of ALL) if(r.ev===g) rows.push({h:g==="REF"?"심판":g,...r});
  }else{
    rows=ALL.map(r=>({h:who5(r),...r}));
  }
  for(const r of rows){
    const line="["+who5(r)+"] "+r.slot+" — "+r.txt;
    if(q && !line.includes(q)) continue;
    n++; head(r.h);
    const d=document.createElement("div");
    d.innerHTML='<span class="k">['+who5(r)+"] "+r.slot+"</span>"+r.txt;
    d.onclick=()=>{ for(const x of l.children)x.classList.remove("on"); d.classList.add("on");
      const gold=D.EVHIT[r.ev]==1;
      blit($("c5"),[renderStrip(fill(r.txt,r.ev),{icon:r.spk>=0&&ICONS?ICONS[r.spk]:(r.spk===-1?KICON:null),
        color:r.ev==="REF"?REF:(gold?GOLD:WHITE)})]); };
    frag.appendChild(d);
    ROWS5.push({el:d, line:line, html:d.innerHTML, marked:false});
  }
  l.appendChild(frag);
  $("n5").textContent=n+"줄"+(q?" (걸러짐)":"");
  if($("find5").value.trim()) find5();          /* 목록을 다시 지으면 검색도 다시 건다 */
  const first=l.querySelector("div:not([style])"); if(first) first.click();
}
$("q5").oninput=list5; $("mode5").onchange=list5;
/* ── 검색 — 거르기와 달리 목록을 줄이지 않는다. 자리로 점프하고 노랗게 칠한다 ── */
let ROWS5=[], HITS5=[], CUR5=-1;
function esc5(t){ return t.replace(/[&<>]/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }
function find5(){
  const q=$("find5").value.trim();
  for(const r of ROWS5){ if(r.marked){ r.el.innerHTML=r.html; r.el.classList.remove("cur"); r.marked=false; } }
  HITS5=[]; CUR5=-1;
  if(!q){ $("fn5").textContent=""; return; }
  for(const r of ROWS5){
    if(!r.line.includes(q)) continue;
    HITS5.push(r); r.marked=true;
    r.el.innerHTML=r.html.split(esc5(q)).join("<mark>"+esc5(q)+"</mark>");
  }
  $("fn5").textContent=HITS5.length?("1 / "+HITS5.length):"없음";
  if(HITS5.length){ CUR5=0; goto5(); }
}
function goto5(){
  if(CUR5<0||!HITS5.length) return;
  for(const r of HITS5) r.el.classList.remove("cur");
  const r=HITS5[CUR5];
  r.el.classList.add("cur");
  r.el.scrollIntoView({block:"center"});
  r.el.click();
  $("fn5").textContent=(CUR5+1)+" / "+HITS5.length;
}
$("find5").oninput=find5;
$("find5").onkeydown=e=>{ if(e.key==="Enter"){ e.preventDefault(); $("next5").click(); } };
$("next5").onclick=()=>{ if(HITS5.length){ CUR5=(CUR5+1)%HITS5.length; goto5(); } };
$("prev5").onclick=()=>{ if(HITS5.length){ CUR5=(CUR5-1+HITS5.length)%HITS5.length; goto5(); } };
$("txt5").onclick=()=>{ buildAll();
  const t=ALL.map(r=>"["+who5(r)+"] "+r.slot+"\t"+r.txt).join("\n");
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([t],{type:"text/plain"})); a.download="ss2_대사_전체.txt"; a.click(); };
function redraw(){ list1(); grid2(); drawIconsTab(); list5(); }
redraw();
</script></body></html>'''

html = HTML.replace("__DATA__", json.dumps(DATA, ensure_ascii=False, separators=(",",":")))
io.open(OUT, "w", encoding="utf-8").write(html)
print("썼다:", OUT, "(%.0fKB)" % (len(html.encode())/1024))
