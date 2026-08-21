#!/usr/bin/env python3
"""
SS2 SP 실행기 — 저속/끊김 A/B 계측 하네스
=========================================
검수 지시서 §2·§3·§5·§6·§7 을 그대로 자동화한다.

측정 항목 (조건마다 동일)
  emu_fps   : gameManager.getFrameNum() 증가량 / 경과초  ← **에뮬레이터가 실제로 돈 프레임**
  disp_fps  : requestAnimationFrame 호출 수 / 경과초      ← 표시 프레임
  p95 / max : rAF 간 간격(ms)의 95퍼센타일 / 최대값        ← 끊김의 체감치
  long      : 33ms(=2프레임) 넘긴 간격 횟수

사용
  python3 perf_ab.py                 # 전부
  python3 perf_ab.py shader          # 쉐이더 A/B만
  python3 perf_ab.py input           # 입력 시나리오만
  python3 perf_ab.py watch first gl  # 여러 개 지정 가능
  (파트: shader / input / watch / first / gl / sim)

옵션 환경변수
  URL=...        기본 http://localhost:8077/runner.html?data=./data/&debug=1
  ROM=...        기본 /home/claude/ejs/webroot/rom.ngc
  SECS=10        조건당 측정 시간(초). 실기 제출용은 30 이상 권장
  THROTTLE=1     CDP CPU 스로틀 배수(4 = 4배 느린 CPU 흉내)

⚠️ 컨테이너의 SwiftShader(소프트웨어 GL)에서 낸 수치는 **기기 수치가 아니다.**
   순위·경향만 참고하고, 합격 판정은 반드시 실기에서 이 스크립트로 다시 낼 것.
"""
import asyncio, os, sys, json, statistics
from playwright.async_api import async_playwright

URL   = os.environ.get("URL", "http://localhost:8077/runner.html?data=./data/&debug=1")
ROM   = os.environ.get("ROM", "/home/claude/ejs/webroot/rom.ngc")
SECS  = float(os.environ.get("SECS", "10"))
THROT = float(os.environ.get("THROTTLE", "1"))

SIMWRAP = """
(() => {
  const gm = EJS_emulator.gameManager;
  if (gm.__wrapped) return; gm.__wrapped = true;
  const o = gm.simulateInput.bind(gm);
  window.__sim = {n:0, ms:0, redundant:0, last:{}};
  gm.simulateInput = (p,id,v) => {
    const S = window.__sim; S.n++;
    if (S.last[id] === v) S.redundant++;
    S.last[id] = v;
    const t = performance.now(); const r = o(p,id,v); S.ms += performance.now()-t; return r;
  };
})()
"""

# WebGL 업로드 경로 관찰용 — 반드시 add_init_script로 페이지보다 먼저 걸어야 한다
GLPROBE = """
(() => {
  const N = v => ({0x1907:'RGB',0x1908:'RGBA',0x8363:'UNSIGNED_SHORT_5_6_5',
    0x1401:'UNSIGNED_BYTE',0x8D62:'RGB565'}[v] || ('0x'+(v>>>0).toString(16)));
  window.__gl = {};
  const hook = proto => {
    if (!proto) return;
    for (const fn of ['texImage2D','texSubImage2D']) {
      const o = proto[fn]; if (!o || o.__h) continue;
      const w = function(){
        const a = arguments;
        if (a.length >= 8) {
          const sig = fn+'  format='+N(a[6])+'  type='+N(a[7]);
          window.__gl[sig] = (window.__gl[sig]||0)+1;
        }
        return o.apply(this,a);
      };
      w.__h = true; proto[fn] = w;
    }
  };
  hook(window.WebGLRenderingContext && WebGLRenderingContext.prototype);
  hook(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype);
})()
"""

PROBE = """
(() => {
  if (window.__probe) return;
  const P = window.__probe = {t:[], last:0, on:false};
  const tick = (t) => {
    if (P.on) { if (P.last) P.t.push(t - P.last); P.last = t; }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  P.start = () => { P.t.length = 0; P.last = 0; P.on = true;
                    P.f0 = EJS_emulator.gameManager.getFrameNum(); P.w0 = performance.now(); };
  P.stop  = () => { P.on = false;
                    const dt = (performance.now() - P.w0) / 1000;
                    const df = EJS_emulator.gameManager.getFrameNum() - P.f0;
                    const a = P.t.slice().sort((x,y)=>x-y);
                    const q = p => a.length ? a[Math.min(a.length-1, Math.floor(a.length*p))] : 0;
                    return {secs:+dt.toFixed(2), emu_fps:+(df/dt).toFixed(1),
                            disp_fps:+(a.length/dt).toFixed(1),
                            p95:+q(.95).toFixed(1), max:+(a.length?a[a.length-1]:0).toFixed(1),
                            long:a.filter(x=>x>33).length};
  };
})()
"""


def fmt(name, r):
    return (f"  {name:<22} emu {r['emu_fps']:>5.1f}fps   disp {r['disp_fps']:>5.1f}fps   "
            f"p95 {r['p95']:>5.1f}ms   max {r['max']:>6.1f}ms   끊김 {r['long']:>3d}")


class Rig:
    def __init__(self, page, cdp=None): self.page = page; self._cdp = cdp

    async def measure(self, secs=None, during=None):
        secs = secs or SECS
        await self.page.evaluate("window.__probe.start()")
        if during:
            await during(secs)
        else:
            await self.page.wait_for_timeout(int(secs * 1000))
        return await self.page.evaluate("window.__probe.stop()")

    async def set_shader(self, v):
        await self.page.evaluate(f"(()=>{{window.__ss2.cfg.shader={json.dumps(v)};"
                                 "document.querySelector('#shaderSeg button[data-shader=\"'+"
                                 f"{json.dumps(v)}+'\"]')?.click();}})()")
        await self.page.wait_for_timeout(1200)

    async def tap_loop(self, sel, secs, period=0.12):
        end = asyncio.get_event_loop().time() + secs
        el = await self.page.query_selector(sel)
        box = await el.bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        while asyncio.get_event_loop().time() < end:
            await self.page.mouse.move(cx, cy)
            await self.page.mouse.down()
            await self.page.wait_for_timeout(int(period * 1000 * .4))
            await self.page.mouse.up()
            await self.page.wait_for_timeout(int(period * 1000 * .6))

    async def both_loop(self, secs):
        """E 시나리오: SP 연타 + D-pad 드래그 동시"""
        await asyncio.gather(self.tap_loop("#spBig", secs, .25), self.dpad_loop(secs, hold=True))

    async def dpad_loop(self, secs, hold=False):
        el = await self.page.query_selector("#dpad")
        b = await el.bounding_box()
        cx, cy = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        r = b["width"] * 0.36
        end = asyncio.get_event_loop().time() + secs
        import math
        # 동시 시나리오에서는 마우스 버튼을 공유할 수 없으므로 터치 이벤트로 넣는다
        cdp = self._cdp
        async def touch(kind, x, y):
            await cdp.send("Input.dispatchTouchEvent", {
                "type": kind,
                "touchPoints": [] if kind == "touchEnd" else [{"x": x, "y": y, "id": 1}]})
        await touch("touchStart", cx, cy)
        i = 0
        while asyncio.get_event_loop().time() < end:
            a = i * 0.5
            await touch("touchMove", cx + r * math.cos(a), cy + r * math.sin(a))
            await self.page.wait_for_timeout(16)
            i += 1
        await touch("touchEnd", cx, cy)


async def main(parts):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium",
            args=["--autoplay-policy=no-user-gesture-required", "--enable-unsafe-swiftshader",
                  "--use-gl=angle", "--use-angle=swiftshader", "--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 412, "height": 915}, has_touch=True)
        if "gl" in parts:
            await ctx.add_init_script(GLPROBE)
        pg = await ctx.new_page()
        if THROT > 1:
            cdp = await ctx.new_cdp_session(pg)
            await cdp.send("Emulation.setCPUThrottlingRate", {"rate": THROT})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
        await pg.goto(URL)
        await pg.set_input_files("#fileInput", ROM)
        await pg.wait_for_function("window.EJS_emulator && window.EJS_emulator.started", timeout=90000)
        await pg.wait_for_timeout(4000)
        await pg.evaluate(PROBE)
        cdp2 = await ctx.new_cdp_session(pg)
        rig = Rig(pg, cdp2)
        print(f"== SS2 SP 실행기 성능 A/B ==  조건당 {SECS:.0f}초, CPU 스로틀 ×{THROT:g}")
        print("   (컨테이너 SwiftShader — 경향만 참고. 합격 판정은 실기에서.)\n")

        if "shader" in parts:
            print("§3 화면 필터 A/B")
            for v, nm in [("off", "없음"), ("crt-zfast", "스캔라인"),
                          ("2xScaleHQ.glslp", "부드럽게"), ("4xScaleHQ.glslp", "강하게")]:
                await rig.set_shader(v)
                print(fmt(nm, await rig.measure()))
            await rig.set_shader("off")
            print()

        if "input" in parts:
            print("§5 입력 시나리오 (필터 없음)")
            await rig.set_shader("off")
            print(fmt("A 아무것도 안 누름", await rig.measure()))
            print(fmt("B 디패드 연속", await rig.measure(during=lambda s: rig.dpad_loop(s))))
            print(fmt("C A 연타", await rig.measure(during=lambda s: rig.tap_loop("#btnA", s))))
            print(fmt("D SP 연타", await rig.measure(during=lambda s: rig.tap_loop("#spBig", s, .25))))
            print(fmt("E SP+디패드 동시", await rig.measure(during=lambda s: rig.both_loop(s))))
            print(fmt("F 콤보 연속", await rig.measure(during=lambda s: rig.tap_loop("#btnCombo", s, .5))))
            print()

        if "watch" in parts:
            print("§6 발동 결과 표시(watch) A/B — SP 연타 중")
            for w, nm in [(1, "watch ON"), (0, "watch OFF")]:
                await pg.evaluate(f"(()=>{{window.__ss2.cfg.watch={w};}})()")
                await pg.wait_for_timeout(300)
                print(fmt(nm, await rig.measure(during=lambda s: rig.tap_loop("#spBig", s, .25))))
            await pg.evaluate("(()=>{window.__ss2.cfg.watch=1;})()")
            print()

        if "sim" in parts:
            print("§5-b simulateInput 비용 (applyDir이 방향마다 U/D/L/R 4회를 보낸다)")
            await pg.evaluate(SIMWRAP)
            for nm, sel, per in [("SP 연타", "#spBig", .25), ("콤보 연타", "#btnCombo", .5)]:
                await pg.evaluate("(()=>{const S=window.__sim;S.n=0;S.ms=0;S.redundant=0;})()")
                r = await rig.measure(during=lambda s: rig.tap_loop(sel, s, per))
                S = await pg.evaluate("({n:window.__sim.n,ms:+window.__sim.ms.toFixed(1),r:window.__sim.redundant})")
                print(fmt(nm, r))
                print(f"      simulateInput {S['n']:>5}회 / {S['ms']:>6.1f}ms 누적 "
                      f"= 벽시계의 {100*S['ms']/(r['secs']*1000):.3f}%   "
                      f"중복 {S['r']} ({100*S['r']//max(S['n'],1)}%)")
            print()

        if "gl" in parts:
            print("§2 픽셀 포맷 — 실제 GL 업로드 경로")
            g = await pg.evaluate("window.__gl || null")
            if not g:
                print("  (GLPROBE가 안 걸렸다 — add_init_script로 페이지보다 먼저 주입해야 한다)")
            else:
                for k, v in sorted(g.items(), key=lambda x: -x[1]):
                    print(f"  {v:>6}회  {k}")
            a = await pg.evaluate("""(()=>{const c=document.querySelector('#game canvas');
                const x=c&&(c.getContext('webgl2')||c.getContext('webgl'));
                return x?x.getContextAttributes():null;})()""")
            print(f"  canvas attrs: alpha={a and a['alpha']}  premultiplied={a and a['premultipliedAlpha']}"
                  f"  depth={a and a['depth']}  stencil={a and a['stencil']}")
            print()

        if "first" in parts:
            print("§7 첫 SP vs 안정 후 SP (초기화·힙 탐색 비용)")
            async def sp_latency():
                """SP를 누른 순간부터 ACT가 필살기(>=0x180)로 바뀔 때까지의 실제 지연(ms)"""
                await pg.evaluate("window.__t0=performance.now(); window.__hit=null;"
                                  "window.__iv=setInterval(()=>{const g=window.__ss2.readGame();"
                                  "if(g.ok&&g.act>=0x180&&window.__hit===null){"
                                  "window.__hit=performance.now()-window.__t0;clearInterval(window.__iv);}},4);")
                await pg.tap("#spBig")
                await pg.wait_for_timeout(1500)
                return await pg.evaluate("(clearInterval(window.__iv), window.__hit)")
            ok = await pg.evaluate("(()=>{const g=window.__ss2.readGame();return !!(g&&g.ok);})()")
            if not ok:
                print("  ⚠️ 전투 중이 아니라 측정할 수 없다 — 이 항목은 **전투 화면에서** 돌려야 한다.")
                print("     (타이틀/데모에서는 ACT가 필살기 값으로 바뀌지 않는다)")
                print("     세이브 슬롯을 전투 장면으로 잡아 두고 SLOT=1 로 로드한 뒤 재실행할 것.")
                first, later = None, []
            else:
                first = await sp_latency()
                await pg.wait_for_timeout(10000)
                later = [await sp_latency() for _ in range(3)]
            if first is not None:
                print(f"  첫 SP 발동 지연  : {first} ms")
                print(f"  10초 후 SP 지연  : {later}")
            h = await pg.evaluate("""(()=>{const t0=performance.now();window.__ss2.findHeap();
                const t1=performance.now();window.__ss2.findHeap();
                return {first:+(t1-t0).toFixed(1),cached:+(performance.now()-t1).toFixed(1),
                        heap:window.__ss2.heapBase};})()""")
            print(f"  힙 탐색 최초 {h['first']}ms / 재탐색 {h['cached']}ms  (heapBase={h['heap']})")
            print("  → 첫 SP만 유의미하게 느리면 초기화 문제다. 해결은 **게임 시작 시 1회 선행 확보**이지,")
            print("     전투 중 polling을 늘리는 것이 아니다.\n")

        print("page errors:", errs or "none")
        await b.close()


if __name__ == "__main__":
    parts = sys.argv[1:] or ["gl", "shader", "input", "sim", "watch", "first"]
    asyncio.run(main(parts))
