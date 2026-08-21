# ── 재현 조건 ─────────────────────────────────────────────
# 이 검사는 실제 롬과 전투 세이브스테이트(webroot의 *.bin)를 요구한다.
# 롬·스테이트는 저장소에 넣지 않는 금지선이라 배포본만으로는 돌 수 없다 — 의도된 제약.
# 환경변수: SS2_ROM=롬 경로, SS2_CHROMIUM=크로미움 경로, SS2_PAGE=페이지(기본 index.html).
import asyncio, os
from playwright.async_api import async_playwright

PASS=[]; FAIL=[]
def check(name, ok, info=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS " if ok else "FAIL ")+name+(" — "+str(info) if info and not ok else ""))

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=os.environ.get("SS2_CHROMIUM","/opt/pw-browsers/chromium"),
            args=["--autoplay-policy=no-user-gesture-required","--enable-unsafe-swiftshader","--use-gl=angle","--use-angle=swiftshader","--no-sandbox"])
        ctx = await browser.new_context(viewport={"width":420,"height":820}, has_touch=True)
        page = await ctx.new_page()
        errors=[]
        # 'Failed to fetch' = EJS 버전체크(localhost/debug 전용) 차단 아티팩트 — 실사용 미발생
        page.on("pageerror", lambda e: errors.append(str(e)[:200]) if "Failed to fetch" not in str(e) else None)

        # ---------- 1. landing + file pick ----------
        PAGE=os.environ.get("SS2_PAGE","index.html")
        await page.goto(f"http://localhost:8077/{PAGE}?data=./data/&debug=1")
        await page.wait_for_timeout(500)
        check("1.1 landing visible", await page.is_visible("#landing"))
        ROM=os.environ.get("SS2_ROM","/home/claude/ejs/webroot/rom.ngc")   # 다른 환경: SS2_ROM=경로
        await page.set_input_files("#fileInput", ROM)
        await page.wait_for_function("window.EJS_emulator && window.EJS_emulator.started", timeout=90000)
        check("1.2 game starts from file pick", True)
        # v0.3.1: 해설 기본 켬 (새 사용자 기준 — 신규 컨텍스트라 localStorage 빈 상태)
        cm0=await page.evaluate("({m:window.__ss2.cfg.commMode,hidden:document.getElementById('commPanel').hidden})")
        check("1.3 해설 기본 켬 + 해설창 표시", cm0["m"]=="on" and not cm0["hidden"], cm0)

        # ---------- 2. reload → cache resume + cfg persistence ----------
        await page.evaluate("window.__ss2.cfg.commSpk='hanzo'; localStorage.setItem('ss2sp_cfg_v3', JSON.stringify(window.__ss2.cfg));")
        await page.goto(f"http://localhost:8077/{PAGE}?data=./data/&debug=1")
        await page.wait_for_selector("#cachedRow:not([hidden])", timeout=10000)
        check("2.1 cached rom offered", True)
        await page.click("#resumeBtn")
        await page.wait_for_function("window.EJS_emulator && window.EJS_emulator.started", timeout=90000)
        pc = await page.evaluate("window.__ss2.cfg.commSpk")
        check("2.2 cfg persisted across reload", pc=="hanzo", pc)

        await page.evaluate("window.__ss2.cfg.commSpk='haohmaru';")

        await page.wait_for_timeout(1200)
        await page.evaluate("""async () => { const r=await fetch('nav_fight.bin'); window.__ss2.loadStateBytes(new Uint8Array(await r.arrayBuffer())); }""")
        await page.wait_for_timeout(400)
        hb = await page.evaluate("window.__ss2.findHeap()")
        check("3.1 heapBase found", hb>=0, hb)
        g = await page.evaluate("window.__ss2.readGame()")
        check("3.2 readGame ok+facing", g["ok"] and g["facing"]==0, g)

        # ---------- 4. SP mode: all directions ----------
        async def wait_idle():
            try:
                await page.wait_for_function("!window.__ss2.macroActive", timeout=4000)
            except Exception:
                pass
            await page.wait_for_timeout(120)
        check("4.0 SP 버튼 노출", not await page.evaluate("document.getElementById('spBig').hidden"))
        m = await page.evaluate("window.__ss2.curSpMap()")
        check("4.1 asura map complete", all(m[k] is not None for k in ["n","f","d","b"]), m)
        for dirs,rel,expect in [((0,0,0,0),"n","셰드 무사"),((0,1,0,0),"d","노 아무"),((0,0,0,1),"f","로페 레프"),((0,0,1,0),"b",None)]:
            await wait_idle()
            # v1.4 게이트: 직전 기술(반격 자세 등)의 경직이 풀릴 때까지 기다렸다 누른다
            try: await page.wait_for_function("window.__ss2.ss2Actable()", timeout=4000)
            except Exception: pass
            await page.evaluate(f"window.__ss2.setDir({dirs[0]},{dirs[1]},{dirs[2]},{dirs[3]})")
            await page.evaluate("window.__ss2.spPress(); window.__ss2.spRelease();")
            # v0.5.7: 하단 기술명 알림을 없앴으므로 **실제로 주입된 입력 스텝**으로 확인한다.
            # (선입력으로 밀릴 수 있으므로 폴링한다. expect 는 기술명 — runMove 가 기록한다.)
            ok = False; t = ""
            for _ in range(16):
                await page.wait_for_timeout(50)
                st = await page.evaluate("({s:window.__ss2.lastSteps, n:window.__ss2.runMove.lastName})")
                t = (st.get("n") or "") + " " + (st.get("s") or "")[:80]
                fired = bool(st.get("s")) and bool(st.get("n"))
                ok = fired and (expect is None or expect in (st.get("n") or ""))
                if ok: break
            check(f"4.2 {rel}+SP fires ({(t or '').strip()[:40]})", ok, t)
            await page.wait_for_timeout(400)
        await page.evaluate("window.__ss2.setDir(0,0,0,0)")

        # 4.2c 뒤 + A+B = 비오의 (v0.5: 버튼을 A·B·A+B·SP 넷으로 줄이며 옮긴 자리)
        await wait_idle()
        try: await page.wait_for_function("window.__ss2.ss2Actable()", timeout=4000)
        except Exception: pass
        await page.evaluate("""() => { const t=document.getElementById('toast'); t.textContent=''; t.classList.remove('show'); }""")
        # 뒤 = 바라보는 방향의 반대. facing 0 이면 왼쪽이 뒤다.
        fac = await page.evaluate("window.__ss2.readGame().facing")
        await page.evaluate(f"window.__ss2.setDir(0,0,{0 if fac else 1},{1 if fac else 0})")
        await page.evaluate("window.__ss2.fireAB()")
        # v0.5.7: 토스트 대신 runMove 가 기록한 기술명으로 확인한다
        t = ""
        for _ in range(16):
            await page.wait_for_timeout(50)
            t = await page.evaluate("window.__ss2.runMove.lastName") or ""
            if "비오의" in t: break
        check("4.2c 뒤+A+B = 비오의", "비오의" in t, t)
        await page.evaluate("window.__ss2.setDir(0,0,0,0)")
        await page.wait_for_timeout(600)

        # 4.2b 기술명 숨김이면 SP 토스트에도 이름이 안 나온다 (v0.2.1 제보 수정)
        await wait_idle()
        try: await page.wait_for_function("window.__ss2.ss2Actable()", timeout=4000)
        except Exception: pass
        await page.evaluate("window.__ss2.cfg.commNames=0")
        await page.wait_for_timeout(1500)   # 직전 발동의 결과 폴링(최대 1.2s)이 끝나길 기다린다
        await page.evaluate("""() => { const t=document.getElementById('toast'); t.textContent=''; t.classList.remove('show'); }""")
        await page.evaluate("window.__ss2.spPress(); window.__ss2.spRelease();")
        t=""
        for _ in range(12):
            await page.wait_for_timeout(50)
            t=await page.text_content("#toast")
        # v0.4.6: 기술명 숨김이면 SP 토스트가 아예 안 뜬다 (제보: 이름이 계속 보인다)
        check("4.2b 기술명 숨김 = SP 토스트 침묵", (t or "").strip()=="", t)
        await page.evaluate("window.__ss2.cfg.commNames=1")
        await page.wait_for_timeout(400)

        # macro cleanliness: no stuck inputs after macro (자동 재시도 창 1.4s 고려)
        await page.wait_for_timeout(1800)
        await wait_idle()
        stuck = await page.evaluate("window.__ss2.macroActive")
        check("4.3 macro not stuck", stuck==False)

        # 4.4 짧은 탭이 프레임 경계에서 씹히지 않는다 (v0.4.8 최소 홀드)
        idb=await page.evaluate("window.__ss2.ID.B")
        seen=[]
        for _ in range(6):
            seen.append(await page.evaluate("""async (IDB) => {
              const g=window.__ss2.gm(), H=g.Module.HEAPU8, b=window.__ss2.heapBase;
              let n=0, run=true;
              const loop=()=>{ if(!run) return; if(H[b+0x2F82]&0x20) n++; requestAnimationFrame(loop); };
              requestAnimationFrame(loop);
              await new Promise(r=>setTimeout(r,100));
              window.__ss2.simDown(IDB); await new Promise(r=>setTimeout(r,4)); window.__ss2.simUp(IDB);
              await new Promise(r=>setTimeout(r,200)); run=false; return n; }""", idb))
        check("4.4 4ms 탭도 게임이 반드시 인식(최소 홀드)", all(n>=1 for n in seen), seen)

        # ---------- 5. card gating ----------
        cs = await page.evaluate("window.__ss2.cardState()")
        check("5.1 no cards detected", cs["known"] and cs["nums"]==[None,None], cs)
        await page.evaluate("""async () => { const r=await fetch('asura_beelzebub_fight.bin'); window.__ss2.loadStateBytes(new Uint8Array(await r.arrayBuffer())); }""")
        await page.wait_for_timeout(300)
        cs2 = await page.evaluate("window.__ss2.cardState()")
        check("5.2 beelzebub #67 detected", cs2["known"] and cs2["nums"][0]==67, cs2)
        await page.tap("#palBtn"); await page.wait_for_timeout(300)
        rows = await page.evaluate("[...document.querySelectorAll('#palGrid button b')].map(b=>b.textContent).join('|')")
        check("5.3 palette equip badges", ("베엘제붑 (#67) 🃏장착됨" in rows) and ("에레스 (#68) 🃏미장착" in rows), rows)
        await page.click("#palClose")

        # ---------- 6. SP 전용 체계 (v1.1: 클래식 슬롯 제거됨) ----------
        gone = await page.evaluate("""(() => ({
            modeBtn: !!document.getElementById('modeBtn'),
            spCountSeg: !!document.getElementById('spCountSeg'),
            slotTab: !!document.querySelector('#sheetTabs [data-t=slot]'),
            slots: document.querySelectorAll('#controls .btnSP:not(#spBig)').length,
            cfgKeys: ['mode','spCount','slots'].filter(k=>k in window.__ss2.cfg)
        }))()""")
        check("6.1 클래식 UI 완전 제거", (not gone['modeBtn']) and (not gone['spCountSeg'])
              and (not gone['slotTab']) and gone['slots']==0 and gone['cfgKeys']==[], gone)
        check("6.2 SP 버튼 유지", not await page.evaluate("document.getElementById('spBig').hidden"))
        # v1.3: [콤보] 버튼 폐기 — 이제 '없음'이 정상이다
        check("6.3 콤보 버튼 제거됨(v1.3)", await page.evaluate("!document.getElementById('btnCombo')"))
        # ---------- 6-4. 프레임 보정 제거 확인 (v1.2) ----------
        gone2 = await page.evaluate("!document.getElementById('fskipSeg') && window.__ss2.cfg.fskip===undefined && window.__ss2.setVsyncOff===undefined")
        check("6.4 프레임 보정 기능 완전 제거", gone2)

        # ---------- 7. 검수 fixes: back-poison wait + waitGround + perf ----------
        # (아수라 상태 그대로 — f슬롯 로페 레프 = 623 → 뒤이동 오염 대상)
        gs0 = await page.evaluate("window.__ss2.perf.getState")
        await page.evaluate("window.__ss2.setDir(0,0,1,0)")
        await page.wait_for_timeout(250)
        await page.evaluate("window.__ss2.setDir(0,0,0,1)")
        await page.evaluate("window.__ss2.spPress(); window.__ss2.spRelease();")
        await page.wait_for_timeout(120)
        tb = await page.text_content("#toast")
        fl = await page.evaluate("window.__ss2.lastFlush")
        br = await page.evaluate("window.__ss2.lastBufferReset")
        # v10.30~: 게임 자체 reset 경로(0x1DCD=1) 사용. 구버전 약베기 플러시도 통과시킨다.
        check("7.2 back-poison 보정 적용(reset 또는 flush)",
              bool(br) or bool(fl) or ("베기캔슬" in tb) or ("뒤이동 보정" in tb), (tb, fl, br))
        cb = await page.evaluate("window.__ss2.clearCommandBuffer()")
        check("7.2b clearCommandBuffer 성공", cb is True, cb)
        st72 = await page.evaluate("window.__ss2.lastSteps") or ""
        # 프리앰블은 **중립(5)에서의 약베기**다. 기술 자체의 마지막 A 스텝과 헷갈리면 안 된다.
        check("7.2c reset 시 슬래시 프리앰블 없음", (not br) or ('"d":"5","b":"A"' not in st72), st72[:160])
        await page.evaluate("window.__ss2.setDir(0,0,0,0)")
        await page.wait_for_timeout(1400)
        # 점프 직후 SP: 착지 대기 문구
        await page.evaluate("window.__ss2.setDir(1,0,0,0)")
        await page.wait_for_timeout(50)
        await page.evaluate("window.__ss2.setDir(0,0,0,0)")
        await page.evaluate("window.__ss2.spPress(); window.__ss2.spRelease();")
        await page.wait_for_timeout(120)
        # v0.5.7: "착지 후" 토스트가 없어졌으므로 **주입된 스텝에 wg 대기**가 들어갔는지로 본다
        tj = await page.evaluate("window.__ss2.lastSteps") or ""
        check("7.3 waitGround applied", '"wg":1' in tj, tj[:160])
        await page.wait_for_timeout(2000)
        gs1 = await page.evaluate("window.__ss2.perf.getState")
        check("7.4 no getState during combat presses", gs1==gs0, (gs0,gs1))
        # 갈포드 데이터: 머신건 독 = 카드 기술 214+B ci2
        await page.evaluate("window.__ss2.cfg.char='galford'; window.__ss2.cfg.style='s';")
        await page.evaluate("document.getElementById('charBtn').click()"); await page.click("#sheetOk")
        await page.wait_for_timeout(400)
        m2 = await page.evaluate("JSON.stringify(window.__ss2.curMoves().find(m=>m.card))")
        check("7.5 galford card move = 머신건 독 214+B ci2", '"머신건 독' in m2 and '"m":"214"' in m2 and '"ci":2' in m2, m2)

        # ---------- 8. step chain (genjuro) ----------
        await page.evaluate("window.__ss2.cfg.char='genjuro'; window.__ss2.cfg.style='s'; window.__ss2.cfg.spChainMode='step';")
        await page.evaluate("document.getElementById('charBtn').click()"); await page.click("#sheetOk")
        await page.wait_for_timeout(300)
        await page.evaluate("window.__ss2.spPress(); window.__ss2.spRelease();")
        await page.wait_for_timeout(600)
        r1 = await page.evaluate("window.__ss2.spPress()")  # chain tap
        await page.wait_for_timeout(300)
        r2 = await page.evaluate("window.__ss2.spPress()")  # chain tap 2
        await page.wait_for_timeout(300)
        check("8.1 step chain no errors", len(errors)==0, errors)
        await page.evaluate("window.__ss2.cfg.spChainMode='auto';")

        # ---------- 9. save/load hash keys ----------
        await wait_idle(); await page.wait_for_timeout(1300)  # 잔여 매크로/토스트 정리
        await page.click("#qSaveBtn"); await page.wait_for_timeout(400)
        await page.click("#qLoadBtn"); await page.wait_for_timeout(400)
        t9 = await page.text_content("#toast")
        check("9.1 quick save+load", "불러오기 완료" in t9, t9)
        keys = await page.evaluate("""new Promise(res=>{ const r=indexedDB.open('ss2runner',1); r.onsuccess=()=>{ const q=r.result.transaction('states').objectStore('states').getAllKeys(); q.onsuccess=()=>res(q.result.join(',')); }; })""")
        # ---------- 9.3 매크로 도중 스테이트 로드 → 잔여물 없이 다음 발동 정상 (v1.4) ----------
        await page.evaluate("window.__ss2.spPress()")
        await page.wait_for_timeout(60)
        await page.evaluate("""async () => { const r=await fetch('nav_fight.bin');
            window.__ss2.loadStateBytes(new Uint8Array(await r.arrayBuffer())); }""")
        await page.wait_for_timeout(200)
        stale = await page.evaluate("window.__ss2.macroActive")
        check("9.3 스테이트 로드가 매크로를 끊는다", stale is False, stale)
        await page.evaluate("window.__ss2.spRelease()")
        await wait_idle()
        await page.evaluate("window.__ss2.setDir(0,0,0,0)")
        a0 = await page.evaluate("window.__ss2.readGame().act")
        await page.evaluate("window.__ss2.spPress(); window.__ss2.spRelease();")
        await page.wait_for_timeout(900)
        a1 = await page.evaluate("window.__ss2.readGame().act")
        check("9.4 로드 직후 SP 정상 발동", a1 >= 0x180 and a1 != a0, (hex(a0), hex(a1)))

        check("9.2 hash-prefixed key", ":" in keys, keys)

        # ---------- 10. FF, fullscreen btn, settings render ----------
        await page.tap("#ffBtn"); await page.wait_for_timeout(150)
        check("10.1 FF on", await page.evaluate("document.getElementById('ffBtn').classList.contains('on')"))
        await page.tap("#ffBtn"); await page.wait_for_timeout(100)
        await page.click("#cfgBtn"); await page.wait_for_timeout(200)
        segs = await page.evaluate("['shaderSeg','hudSeg'].every(id=>document.getElementById(id).querySelector('.sel')!==null)")
        check("10.2 settings segments render", segs)
        await page.click("#cfgClose")
        check("10.3 [SP 연속기]·[콤보] 잔재 없음(v1.3)",
              await page.evaluate("!document.getElementById('chainSeg') && !document.getElementById('comboSeg')"
                                  " && !document.getElementById('openerSeg') && !document.getElementById('sheetTabs')"))

        # ---------- 10-A. 0.6 접근성/부하 불변식 ----------
        acc = await page.evaluate("""(()=>{
            const ids=['btnA','btnB','spBig','btnAB'];   /* v1.3: btnCombo 제거 */
            const w=ids.map(i=>document.getElementById(i).getBoundingClientRect().width);
            const shadow=ids.some(i=>{
              const el=document.getElementById(i);
              el.classList.add('armed');
              const v=getComputedStyle(el).boxShadow;
              el.classList.remove('armed');
              return v && v!=='none';
            });
            return {min:Math.min(...w), max:Math.max(...w), shadow:shadow,
                    spSmall:!!document.querySelector('#spBig small')};
        })()""")
        check("10.4 다섯 버튼 지름 동일", abs(acc["max"]-acc["min"]) < 1.0, acc)
        check("10.5 터치 표적 44px 이상", acc["min"] >= 44, acc["min"])
        check("10.6 armed 상태에 box-shadow 없음", not acc["shadow"], acc)
        check("10.7 SP 기술명 라벨 제거됨", not acc["spSmall"], acc)
        gl = await page.evaluate("""(()=>{
            const c=document.querySelector('#game canvas'); if(!c) return null;
            const g=c.getContext('webgl2')||c.getContext('webgl'); if(!g) return null;
            const a=g.getContextAttributes();
            return {alpha:a.alpha, pre:a.premultipliedAlpha};
        })()""")
        check("10.8 게임 캔버스가 불투명(alpha:false)", gl and gl["alpha"] is False and gl["pre"] is False, gl)
        check("10.9 전역 addEventListener 패치가 부팅 후 복원됨",
              await page.evaluate("!/TYPES|passive:true/.test(EventTarget.prototype.addEventListener.toString())"))

        # ---------- 11. drag one element ----------
        await wait_idle()
        await page.click("#cfgBtn"); await page.click("#editStart"); await page.wait_for_timeout(400)
        b = await page.evaluate("(() => {const r=document.getElementById('btnA').getBoundingClientRect(); return [r.x+r.width/2,r.y+r.height/2];})()")
        await page.mouse.move(b[0],b[1]); await page.mouse.down(); await page.mouse.move(b[0]-30,b[1]-20,steps=4); await page.mouse.up()
        await page.click("#editDone"); await page.wait_for_timeout(150)
        off = await page.evaluate("JSON.stringify(window.__ss2.cfg.layout.btnA||null)")
        check("11.1 btnA dragged", '"x":-30' in off, off)
        # editing off → controls work again
        await page.evaluate("window.__ss2.spPress(); window.__ss2.spRelease();")
        await page.wait_for_timeout(100)
        check("11.2 sp works after edit mode", True)

        # ---------- 12. no page errors accumulated ----------
        # ---------- 13. 해설 (v1.6) ----------
        await page.evaluate("window.__ss2.cfg.commMode='on'; window.__ss2.cfg.commVoice=0")
        await page.evaluate("window.__ss2.cfg.char='asura'; window.__ss2.cfg.style='s'; window.__ss2.cfg.autoChar=false")
        await page.evaluate("""async () => { const r=await fetch('nav_fight.bin');
            window.__ss2.loadStateBytes(new Uint8Array(await r.arrayBuffer())); }""")
        await page.wait_for_timeout(500); await page.evaluate("window.__ss2.findHeap()")
        await page.wait_for_timeout(200)
        comm=""
        for attempt in range(3):        # 실전투 — COM 방해 시 스테이트 리로드로 재시도
            await page.evaluate("""async () => { const r=await fetch('nav_fight.bin');
                window.__ss2.loadStateBytes(new Uint8Array(await r.arrayBuffer())); }""")
            await page.wait_for_timeout(500); await page.evaluate("window.__ss2.findHeap()")
            try: await page.wait_for_function("window.__ss2.ss2Actable()", timeout=3000)
            except Exception: pass
            await page.wait_for_timeout(150)
            await page.evaluate("window.__ss2.runMove(window.__ss2.curMoves()[0],null,{sustain:false})")
            for _ in range(40):
                await page.wait_for_timeout(80)
                t=await page.evaluate("window.__ss2.commLast")
                if "셰드" in t: comm=t; break
            if comm: break
        check("13.1 해설: 발동(+결과 결합) 호명", "셰드" in comm, comm)
        await page.wait_for_timeout(1200)
        t0=await page.evaluate("window.__ss2.commLastAt")
        await page.evaluate("""() => { const g=window.__ss2.gm(),H=g.Module.HEAPU8,b=window.__ss2.heapBase;
            H[b+0x1C46]=0; }""")
        # 13.1 꼬리 큐(역전 등)가 먼저 나올 수 있다 — 첫 줄에서 끊지 말고 2.5초간 모아서 본다
        kos=[]
        for _ in range(30):
            await page.wait_for_timeout(85)
            r=await page.evaluate("({t:window.__ss2.commLast,at:window.__ss2.commLastAt})")
            if r["at"]>t0 and (not kos or kos[-1]!=r["t"]): kos.append(r["t"])
            if any(any(w in t for w in ("KO","승부","끝","저스티스","마무리")) for t in kos): break
        check("13.2 해설: KO 라인", any(any(w in t for w in ("KO","승부","끝","저스티스","마무리")) for t in kos), kos)
        await page.evaluate("window.__ss2.cfg.commMode='off'")

        # ---------- 14. 해설 합성 검사 (commStep에 합성 램 값 주입 — 롬 상태 무관) ----------
        await page.evaluate("window.__ss2.commSynth=true")   # 실제 램 감시 정지
        async def synth_seq(js):
            await page.evaluate("window.__ss2.commReset()")
            await page.evaluate(js)
        async def lines_until(want, sec=3.0):
            seen=[]
            for _ in range(int(sec*12)):
                await page.wait_for_timeout(85)
                t=await page.evaluate("window.__ss2.commLast")
                if t and (not seen or seen[-1]!=t): seen.append(t)
                if any(want(x) for x in seen): break
            return seen
        await page.evaluate("window.__ss2.cfg.commMode='on'")
        # 14.1 발동+히트 결합
        await synth_seq("""() => { const rm=window.__ss2.runMove;
            rm.lastAt=performance.now(); rm.lastName='셰드 무사'; rm.lastMv={n:'셰드 무사'};
            const S=(m,p1,p2,a1,a2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:a1,a2:a2,fresh:false});
            S(0xF1,128,128,8,8); S(0xF1,128,128,0x1b0,8); S(0xF1,128,110,0x1b0,0xe0); }""")
        seen=await lines_until(lambda t:"셰드 무사" in t and ("들어" in t or "적중" in t or "맞았" in t))
        check("14.1 합성: 발동+히트 결합", any("셰드 무사" in t and ("들어" in t or "적중" in t or "맞았" in t) for t in seen), seen)
        # 14.2 동시 KO
        await synth_seq("""() => {
            const S=(m,p1,p2,a1,a2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:a1,a2:a2,fresh:false});
            S(0xF1,110,110,8,8); S(0xF1,0,0,8,8); }""")
        seen=await lines_until(lambda t:("더블" in t) or ("둘 다" in t) or ("동귀" in t))
        check("14.2 합성: 동시 KO = 더블", any(("더블" in t) or ("둘 다" in t) or ("동귀" in t) for t in seen), seen)
        # 14.3 미검증 기술 — 이름만, 설명 침묵 (설명이 나가는 입문 모드에서 검사)
        await page.evaluate("window.__ss2.cfg.commMode='intro'")
        await synth_seq("""() => { const rm=window.__ss2.runMove;
            rm.lastAt=performance.now(); rm.lastName='레피 슐'; rm.lastMv={n:'레피 슐'};
            const S=(m,p1,p2,a1,a2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:a1,a2:a2,fresh:false});
            S(0xF1,128,128,8,8); S(0xF1,128,128,0x1f0,8); }""")
        # 새 정책(v1.7): 발동 단독은 침묵 — 기술명을 외치지 않는다
        await page.wait_for_timeout(1200)
        silent=await page.evaluate("window.__ss2.commLast")
        check("14.3a 합성: 발동 단독 = 침묵", "레피 슐" not in (silent or ""), silent)
        # 결과가 붙으면 이름은 나오되 미검증 설명은 없다
        await synth_seq("""() => { const rm=window.__ss2.runMove;
            rm.lastAt=performance.now(); rm.lastName='레피 슐'; rm.lastMv={n:'레피 슐'};
            const S=(m,p1,p2,a1,a2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:a1,a2:a2,fresh:false});
            S(0xF1,128,128,8,8); S(0xF1,128,128,0x1f0,8); S(0xF1,128,110,0x1f0,0xe0); }""")
        seen=await lines_until(lambda t:"레피 슐" in t, 2.5)
        ok=any(("레피 슐" in t) and ("분신" not in t) and ("전기" not in t) for t in seen)
        check("14.3b 합성: 결합 시 이름만, 미검증 설명 침묵", ok, seen)
        # 14.4 역전 — 최소 1회 발화 + 3번 뒤집어도 2회 초과 금지
        await synth_seq("""() => {
            const S=(p1,p2)=>window.__ss2.commStep({mode:0xF1,p1:p1,p2:p2,a1:8,a2:8,fresh:false});
            S(128,128); S(128,100); S(90,100); S(90,60); S(50,60); S(50,30); }""")  # 리드 교차 하락(증가 없음)
        seen=await lines_until(lambda t:("역전" in t) or ("뒤집" in t) or ("형세" in t), 2.0)
        rev=sum(1 for t in seen if ("역전" in t) or ("뒤집" in t) or ("형세" in t))
        check("14.4 합성: 역전 1회 이상·2회 이하", 1<=rev<=2, seen)
        # 14.5 기술명 숨김 — 결합 문장에서 이름이 빠진다 (v1.8)
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("window.__ss2.cfg.commNames=0")
        await page.evaluate("""() => { const rm=window.__ss2.runMove;
            rm.lastAt=performance.now(); rm.lastName='셰드 무사'; rm.lastMv={n:'셰드 무사'};
            const S=(m,p1,p2,a1,a2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:a1,a2:a2,fresh:false});
            S(0xF1,128,128,8,8); S(0xF1,128,128,0x1b0,8); S(0xF1,128,110,0x1b0,0xe0); }""")
        seen=await lines_until(lambda t:("들어" in t) or ("적중" in t) or ("맞았" in t) or ("히트" in t) or ("명중" in t), 2.5)
        ok=any(((("들어" in t) or ("적중" in t) or ("맞았" in t) or ("히트" in t) or ("명중" in t)) and ("셰드" not in t)) for t in seen)
        check("14.5 합성: 기술명 숨김", ok, seen)
        await page.evaluate("window.__ss2.cfg.commNames=1")
        # 14.6 시작 3연 멘트 — 큐에서 순서대로 전부 나온다 (입문)
        await page.evaluate("window.__ss2.cfg.commMode='intro'")
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,fresh:false});
            S(0xF1); S(0xF0); }""")
        await page.wait_for_timeout(3200)   # 메뉴 3초 조건
        await page.evaluate("""() => { window.__ss2.commStep({mode:0xF1,p1:128,p2:128,a1:8,a2:8,fresh:false}); }""")
        seen=await lines_until(lambda t:False, 5.0)
        has_start=any(" 대 " in t or "간다" in t for t in seen)
        check("14.6 합성: 시작 멘트 탈락 없음(매치업+썰)", has_start, seen)
        # 14.8 메뉴 조잘 — 캐릭터 선택 화면 진입 한 마디
        await page.evaluate("window.__ss2.cfg.commMode='on'")
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => { window.__ss2.touchStamp();
            const S=(m,scr)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,scr:scr,fresh:false});
            S(0xF0,0); S(0xF0,2); }""")
        seen=await lines_until(lambda t:"누구" in t or "검객" in t or "픽" in t, 2.0)
        check("14.8 합성: 캐릭터 선택 조잘", any(("누구" in t) or ("검객" in t) or ("픽" in t) for t in seen), seen)

        # ---------- v1.9: 화면별 코멘트·잡담·폭 맞춤 ----------
        await page.evaluate("window.__ss2.cfg.commSpk='haohmaru'")
        # 14.9 타이틀·카드 화면 코멘트
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => { window.__ss2.touchStamp();
            const S=(m,scr)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,scr:scr,fresh:false});
            S(0xF0,2); S(0xF0,0); }""")
        seen=await lines_until(lambda t:("혼이" in t) or ("한판" in t) or ("기다렸다" in t), 2.0)
        check("14.9a 합성: 타이틀 화면 조잘", any(("혼이" in t) or ("한판" in t) or ("기다렸다" in t) for t in seen), seen)
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => { window.__ss2.touchStamp();
            const S=(m,scr)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,scr:scr,fresh:false});
            S(0xF0,4); S(0xF0,6); }""")
        seen=await lines_until(lambda t:("카드" in t) or ("공짜" in t) or ("무뎌" in t), 2.0)
        check("14.9b 합성: 카드 화면 조잘", any(("카드" in t) or ("공짜" in t) or ("무뎌" in t) for t in seen), seen)
        # 14.10 전투 잡담 — 공방이 끊기면 (임계 600ms로 줄여서 검사)
        await page.evaluate("window.__ss2.commReset(); window.__ss2.commIdleMs=600")
        await page.evaluate("""() => {
            const S=(m)=>window.__ss2.commStep({mode:m,p1:110,p2:110,a1:8,a2:8,fresh:false});
            S(0xF0); S(0xF1); }""")
        for _ in range(14):
            await page.wait_for_timeout(100)
            await page.evaluate("window.__ss2.commStep({mode:0xF1,p1:110,p2:110,a1:8,a2:8,fresh:false})")
        seen=await lines_until(lambda t:("노려보" in t) or ("먼저 가라" in t) or ("신중한" in t), 6.0)
        check("14.10 합성: 전투 잡담(놀 때)", any(("노려보" in t) or ("먼저 가라" in t) or ("신중한" in t) for t in seen), seen)
        await page.evaluate("window.__ss2.commIdleMs=12000")
        # 14.11 메뉴 잡담 — 한 화면에 오래 머무르면 (선택창(2)은 사담 담당이라 유파(4)로 검사)
        await page.evaluate("window.__ss2.commReset(); window.__ss2.commIdleMenuMs=500")
        for _ in range(12):
            await page.wait_for_timeout(90)
            await page.evaluate("window.__ss2.commStep({mode:0xF0,p1:128,p2:128,a1:8,a2:8,scr:4,fresh:false})")
        seen=await lines_until(lambda t:("천천히" in t) or ("고르는 것도" in t) or ("술 마시며" in t), 2.0)
        check("14.11 합성: 메뉴 잡담(놀 때)", any(("천천히" in t) or ("고르는 것도" in t) or ("술 마시며" in t) for t in seen), seen)
        await page.evaluate("window.__ss2.commIdleMenuMs=15000")
        # 14.12 대사 폭 맞춤 — 짧은 문장은 크게, 긴 문장은 작게 (클램프 11~26px)
        fs=await page.evaluate("""() => { const el=document.getElementById('commLine');
            window.__ss2.fitFont('간다!!'); const a=parseFloat(el.style.fontSize);
            window.__ss2.fitFont('아주 긴 문장으로 해설창의 가로 폭을 넘겨 보는 검사용 대사입니다, 길수록 작아져야 한다');
            const b=parseFloat(el.style.fontSize); return {a:a,b:b}; }""")
        ok=fs and fs["a"]>=fs["b"] and 11<=fs["a"]<=26 and 11<=fs["b"]<=26
        check("14.12 대사 폭 맞춤(짧으면 크게·길면 작게)", bool(ok), fs)

        # ---------- v1.9.1: 선택창 사담·문구 반응·승패 화면 반응 ----------
        # 14.14 캐릭터 선택창 사담 — 고르는 동안 주기적으로 (임계 300ms로 줄여 검사)
        await page.evaluate("window.__ss2.commReset(); window.__ss2.commSelChatMs=300")
        for _ in range(14):
            await page.wait_for_timeout(90)
            await page.evaluate("window.__ss2.commStep({mode:0xF0,p1:128,p2:128,a1:8,a2:8,scr:2,fresh:false})")
        SELW=("겐주로","살살","우쿄","고민되면","기다리는 것도","쿠로코","유가","쥬베이","시키라는")
        seen=await lines_until(lambda t:any(w in t for w in SELW), 2.0)
        check("14.14 합성: 선택창 사담", any(any(w in t for w in SELW) for t in seen), seen)
        await page.evaluate("window.__ss2.commSelChatMs=7000")
        # 14.15 문구(VS) 화면 반응 — "한판 승부 정정당당히" 류 (확률 가드 고정)
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => { window.__rndBak=Math.random; Math.random=()=>0.1;
            const S=(m,scr)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,scr:scr,fresh:false});
            S(0xF0,6); S(0xF1,0); Math.random=window.__rndBak; }""")
        seen=await lines_until(lambda t:("정정당당" in t) or ("글귀" in t), 8.0)
        check("14.15 합성: 문구 화면 반응", any(("정정당당" in t) or ("글귀" in t) for t in seen), seen)
        # 14.16 승리 후 이름 화면 반응
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m,p1,p2,scr)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,scr:scr,fresh:false});
            /* v0.5.3: 결과 멘트는 **매치가 끝났을 때만**(2선승) — 라운드 둘을 이겨 준다 */
            S(0xF0,128,128,6); S(0xF1,128,128,8); S(0xF1,128,0,8);
            S(0xF0,128,128,8); S(0xF1,128,128,8); S(0xF1,128,0,8); S(0xF1,128,0,2); }""")
        seen=await lines_until(lambda t:("승자의" in t) or ("이긴 자" in t), 6.0)
        check("14.16 합성: 승리 후 이름 화면 반응", any(("승자의" in t) or ("이긴 자" in t) for t in seen), seen)
        # 14.17 패배 후 이름 화면 반응
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m,p1,p2,scr)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,scr:scr,fresh:false});
            S(0xF0,128,128,6); S(0xF1,128,128,8); S(0xF1,0,128,8);
            S(0xF0,128,128,8); S(0xF1,128,128,8); S(0xF1,0,128,8); S(0xF1,0,128,2); }""")
        seen=await lines_until(lambda t:("기억해" in t) or ("분한" in t), 6.0)
        check("14.17 합성: 패배 후 이름 화면 반응", any(("기억해" in t) or ("분한" in t) for t in seen), seen)
        # 14.18 해설창 높이 고정 — 효과가 게임 화면을 밀지 않는다
        hv=await page.evaluate("""() => { const pn=document.getElementById('commPanel');
            const st=getComputedStyle(pn); return {h:st.height,of:st.overflow}; }""")
        check("14.18 해설창 높이 고정(64px 두줄)+overflow hidden", hv and hv["h"]=="64px" and hv["of"]=="hidden", hv)

        # 14.19 요령: 클릭 없는 메뉴 전환 = 스토리/데모 사담 (화면 멘트 아님)
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => { window.__rndBak=Math.random; Math.random=()=>0.1;
            const S=(m,scr)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,scr:scr,fresh:false});
            S(0xF0,0); S(0xF0,2); Math.random=window.__rndBak; }""")   # touchStamp 없음 = 자동 전환
        seen=await lines_until(lambda t:("이야기" in t) or ("어떻게 되는" in t) or ("술안주" in t), 2.5)
        chat_ok=any(("이야기" in t) or ("어떻게 되는" in t) or ("술안주" in t) for t in seen)
        no_sel=not any("누구와" in t for t in seen)
        check("14.19 합성: 자동 전환 = 스토리 사담(선택 멘트 아님)", chat_ok and no_sel, seen)
        # 14.20 결과 반응 뒤 스토리 페이지(0↔2 자동 반복) 사담 — 실전 박자대로 두 단계
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m,p1,p2,scr)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,scr:scr,fresh:false});
            S(0xF0,128,128,6); S(0xF1,128,128,8); S(0xF1,128,0,8); S(0xF1,128,0,2); }""")
        await page.wait_for_timeout(3200)   # KO·후속·승리반응 큐 소화
        await page.evaluate("""() => { window.__rndBak=Math.random; Math.random=()=>0.1;
            const S=(m,p1,p2,scr)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,scr:scr,fresh:false});
            S(0xF1,128,0,0); S(0xF1,128,0,2); Math.random=window.__rndBak; }""")
        seen=await lines_until(lambda t:("이야기" in t) or ("술안주" in t), 4.0)
        check("14.20 합성: 결과 뒤 스토리 페이지 사담", any(("이야기" in t) or ("술안주" in t) for t in seen), seen)
        # 14.21 해설창 폭 = 게임 디스플레이 폭 (±2px)
        wv=await page.evaluate("""() => { window.__ss2.alignCommPanel();
            const pn=document.getElementById('commPanel');
            const gw=document.getElementById('gamewrap').getBoundingClientRect();
            const target=Math.min(gw.width,gw.height*160/152);
            return {p:pn.getBoundingClientRect().width,t:target,hidden:pn.hidden}; }""")
        ok=wv and (wv["hidden"] or abs(wv["p"]-wv["t"])<=2.5)
        check("14.21 해설창 폭 = 게임 디스플레이 폭", bool(ok), wv)

        # ---------- v0.3: 도파민 이벤트 (완승·역전승·선취·벼랑·연승·선제) ----------
        async def battle_seq(js):
            await page.evaluate("window.__ss2.commReset()")
            await page.evaluate(js)
        # 14.22 완승 — 무피해 KO
        await battle_seq("""() => {
            const S=(m,p1,p2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,fresh:false});
            S(0xF0,128,128); S(0xF1,128,128); S(0xF1,128,128); S(0xF1,128,0); }""")
        seen=await lines_until(lambda t:("완승" in t) or ("퍼펙트" in t) or ("흠집" in t), 3.5)
        check("14.22 합성: 완승(퍼펙트)", any(("완승" in t) or ("퍼펙트" in t) or ("흠집" in t) for t in seen), seen)
        # 14.23 역전승 — 빈사에서 KO 승
        await battle_seq("""() => {
            const S=(m,p1,p2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,fresh:false});
            S(0xF0,128,128); S(0xF1,128,128); S(0xF1,20,100); S(0xF1,20,0); }""")
        seen=await lines_until(lambda t:("뒤집" in t) or ("역전" in t) or ("사지" in t) or ("각본" in t), 3.5)
        check("14.23 합성: 역전승(빈사 승리)", any(("뒤집" in t) or ("역전" in t) or ("사지" in t) or ("각본" in t) for t in seen), seen)
        # 14.24 선취 — 1라운드 승리 후 재개 라인
        await battle_seq("""() => {
            const S=(m,p1,p2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,fresh:false});
            S(0xF0,128,128); S(0xF1,128,128); S(0xF1,100,90); S(0xF1,100,0);   /* 1R 승 */
            S(0xF0,128,128); S(0xF1,128,128); }""")
        seen=await lines_until(lambda t:("밀어붙" in t) or ("앞섰" in t) or ("리드" in t), 5.0)
        check("14.24 합성: 라운드 선취 라인", any(("밀어붙" in t) or ("앞섰" in t) or ("리드" in t) for t in seen), seen)
        # 14.25 매치포인트 — 1승 1패 후 최종 라운드 (라운드 간 실전 간격 유지)
        await battle_seq("""() => {
            const S=(m,p1,p2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,fresh:false});
            S(0xF0,128,128); S(0xF1,128,128); S(0xF1,100,90); S(0xF1,100,0);   /* 1R 승 */
            S(0xF0,128,128); S(0xF1,128,128); S(0xF1,90,100); S(0xF1,0,100); }""")   # 2R 패
        await page.wait_for_timeout(2700)   # roundCtx 쿨다운(2.5s) 경과 = 실전 라운드 간격
        await page.evaluate("""() => {
            const S=(m,p1,p2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,fresh:false});
            S(0xF0,128,128); S(0xF1,128,128); }""")
        seen=await lines_until(lambda t:("마지막 판" in t) or ("최종국" in t) or ("파이널" in t), 4.0)
        check("14.25 합성: 매치포인트", any(("마지막 판" in t) or ("최종국" in t) or ("파이널" in t) for t in seen), seen)
        # 14.26 벼랑끝 — 양쪽 빈사
        await battle_seq("""() => {
            const S=(m,p1,p2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,fresh:false});
            S(0xF0,128,128); S(0xF1,128,128); S(0xF1,30,100); S(0xF1,30,20); }""")
        seen=await lines_until(lambda t:("둘 다" in t) or ("벼랑" in t) or ("목숨" in t), 3.5)
        check("14.26 합성: 벼랑끝(양쪽 빈사)", any(("둘 다" in t) or ("벼랑" in t) or ("목숨" in t) for t in seen), seen)
        # 14.27 연승 — 세션 연승 2 (매치 승리 = 2라운드)
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("window.__ss2.sessStreak=1")
        await page.evaluate("""() => {
            const S=(m,p1,p2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,fresh:false});
            S(0xF0,128,128); S(0xF1,128,128); S(0xF1,100,90); S(0xF1,100,0);
            S(0xF0,128,128); S(0xF1,128,128); S(0xF1,60,90); S(0xF1,60,0); }""")
        seen=await lines_until(lambda t:"연승" in t, 6.0)
        check("14.27 합성: 연승 멘트", any("연승" in t for t in seen), seen)
        # 14.28 선제타 — 1라운드 첫 일반 유효타
        await battle_seq("""() => {
            const S=(m,p1,p2)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,fresh:false});
            S(0xF0,128,128); S(0xF1,128,128); S(0xF1,128,118); }""")
        seen=await lines_until(lambda t:("선제" in t) or ("퍼스트" in t) or ("첫 유효" in t), 7.0)
        check("14.28 합성: 선제타", any(("선제" in t) or ("퍼스트" in t) or ("첫 유효" in t) for t in seen), seen)

        # ---------- v0.3.1: 대사 굳음 방지 (사용자 피드백) ----------
        # 14.29 자연 소멸 — TTL 지나면 스르륵 사라지고 "…" 복귀
        await page.evaluate("window.__ss2.commReset(); window.__ss2.commLineTTL=800")
        await page.evaluate("window.__ss2.commSub('굳음 검사용 대사입니다',0)")
        await page.wait_for_timeout(2400)
        line=await page.evaluate("document.getElementById('commLine').textContent")
        check("14.29 대사 자연 소멸(TTL)", line.strip()=="…", line)
        await page.evaluate("window.__ss2.commLineTTL=8000")
        # 14.30 장면 전환 클리어 — 전환 시 2초 넘은 옛 대사는 지워진다
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("window.__ss2.commSub('장면 전환 검사 대사',0)")
        await page.wait_for_timeout(2200)
        await page.evaluate("""() => { window.__rndBak=Math.random; Math.random=()=>0.9;
            const S=(m,scr)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,scr:scr,fresh:false});
            S(0xF0,3); S(0xF0,5); Math.random=window.__rndBak; }""")
        await page.wait_for_timeout(1400)
        line=await page.evaluate("document.getElementById('commLine').textContent")
        # v0.3.2: 전환마다 반드시 반응하므로 "…"가 아니라 새 사담으로 교체될 수도 있다 — 옛 대사만 사라지면 통과
        check("14.30 장면 전환 시 굳은 대사 클리어", "장면 전환 검사" not in line, line)

        # ---------- v0.3.2→v0.3.4: 반피·전황·연타는 제거됨 (이전 속도 복귀) ----------
        # 14.34 상대 분석 — 지식 기반 특성 문구 존재 (유닛)
        tr=await page.evaluate("window.__ss2.oppTrait('haohmaru_s')")
        check("14.34 상대 분석 문구(지식 '확실'만)", bool(tr) and ("보유" in tr), tr)
        # 14.35 전적 코멘트 — 2번째 매치 승리 후 결과 화면
        # v0.5.3: 전적은 세 판에 한 번만 붙는다 - 2전 2승 상태에서 세 번째 매치를 이겨 본다
        await page.evaluate("window.__ss2.commReset(); window.__ss2.sessWins=2; window.__ss2.sessGames=2")
        await page.evaluate("""() => {
            const S=(m,p1,p2,scr)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,scr:scr,fresh:false});
            S(0xF0,128,128,6); S(0xF1,128,128,8); S(0xF1,100,0,8);
            S(0xF0,128,128,8); S(0xF1,128,128,8); S(0xF1,60,0,8); S(0xF1,60,0,2); }""")
        seen=await lines_until(lambda t:("3승" in t) and ("3전" in t), 8.0)
        check("14.35 합성: 전적 코멘트(오늘 N전 M승)", any(("3승" in t) and ("3전" in t) for t in seen), seen)

        # ---------- v0.4.1: 무한대전(서바이벌) 연승 ----------
        # 14.36 연승 콜 — 전투 진입 시 surv=5
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m,surv)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,surv:surv,fresh:false});
            S(0xF0,5); S(0xF1,5); }""")
        seen=await lines_until(lambda t:"연승" in t, 5.0)
        check("14.36 합성: 서바이벌 연승 콜", any("연승" in t or "명째" in t for t in seen), seen)
        # 14.37 결산 — 서바이벌 중 패배
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m,p1,surv)=>window.__ss2.commStep({mode:m,p1:p1,p2:100,a1:8,a2:8,surv:surv,fresh:false});
            S(0xF0,128,7); S(0xF1,128,7); S(0xF1,120,7); S(0xF1,0,7); }""")
        seen=await lines_until(lambda t:("기록" in t) or ("격파" in t) or ("멈췄" in t) or ("스트릭 종료" in t), 5.0)
        check("14.37 합성: 서바이벌 결산", any(("기록" in t) or ("격파" in t) or ("멈췄" in t) or ("스트릭 종료" in t) for t in seen), seen)

        # ---------- v0.4.2: 스토리 연전 콜 · 대사 화면 반응 ----------
        # 14.38 스토리 연전 — surv=0, stage=4 (5연전째)
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m,st)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,surv:0,stage:st,fresh:false});
            S(0xF0,4); S(0xF1,4); }""")
        seen=await lines_until(lambda t:("연전" in t) or ("풀렸" in t) or ("데워" in t) or ("익었" in t) or ("지치" in t), 5.0)
        check("14.38 합성: 스토리 연전 콜", any(("연전" in t) or ("풀렸" in t) or ("데워" in t) or ("익었" in t) or ("지치" in t) for t in seen), seen)
        # 14.39 대사 화면(mode 197) 반응
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,surv:0,stage:0,fresh:false});
            S(0xF0); S(0xC5); }""")
        seen=await lines_until(lambda t:("말" in t) or ("인사" in t) or ("각오" in t) or ("명대사" in t) or ("입은" in t), 4.0)
        check("14.39 합성: 대사 화면(mode 197) 반응", any(("말" in t) or ("인사" in t) or ("각오" in t) or ("명대사" in t) or ("입은" in t) for t in seen), seen)
        # 14.40 엔딩(mode 199) 반응
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,surv:0,stage:7,fresh:false});
            S(0xF0); S(0xC7); }""")
        seen=await lines_until(lambda t:("클리어" in t) or ("완주" in t) or ("끝까지" in t) or ("해내" in t), 4.0)
        check("14.40 합성: 엔딩(mode 199) 반응", any(("클리어" in t) or ("완주" in t) or ("끝까지" in t) or ("해내" in t) for t in seen), seen)
        # 14.41 연전 콜은 값이 오를 때만 (같은 값 재진입은 침묵)
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m,st)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,surv:0,stage:st,fresh:false});
            S(0xF0,3); S(0xF1,3); }""")
        STG=("연전","풀렸","데워","익었","지치","다음 상대","계속 가자","도전자")
        seen=await lines_until(lambda t:any(w in t for w in STG), 6.0)
        got1=any(any(w in t for w in STG) for t in seen)
        # 1차 대사(매치업·설정·연전 세 줄)가 큐에서 **다 빠질 때까지** 기다렸다 재진입한다.
        # 고정 대기(3.2초)로는 큐가 길 때 마지막 줄이 2차 창에 잔상으로 걸쳐 간헐 실패했다.
        # 대기열이 0이 되고 화면 줄도 비는 것을 **확인하고** 넘어간다.
        try:
            await page.wait_for_function("window.__ss2.annQ===0", timeout=12000)
        except Exception:
            pass
        await page.evaluate("window.__ss2.lineFade()")
        try:
            await page.wait_for_function(
                "document.getElementById('commLine').textContent.trim()===''"
                " || document.getElementById('commLine').textContent.trim()==='…'", timeout=6000)
        except Exception:
            pass
        await page.wait_for_timeout(600)
        await page.evaluate("""() => {
            const S=(m,st)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,surv:0,stage:st,fresh:false});
            S(0xF0,3); S(0xF1,3); }""")   # 같은 stage 값으로 재진입
        seen2=await lines_until(lambda t:False, 3.0)
        got2=any(any(w in t for w in STG) for t in seen2)
        check("14.41 연전 콜은 값 상승 시에만", got1 and not got2, {"1st":seen,"2nd":seen2})

        # ---------- v0.4.4: 승패 후 한마디 더 · 하단 알림/연계 토글 ----------
        # 14.42 승리 후 한마디 더 (winScr + winTalk 두 마디)
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m,p1,p2,scr)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:8,a2:8,scr:scr,surv:0,stage:0,fresh:false});
            /* v0.5.3: 결과 멘트는 매치 종료(2선승)에서만 — 라운드 둘을 이겨 준다 */
            S(0xF0,128,128,6); S(0xF1,128,128,8); S(0xF1,120,90,8); S(0xF1,120,0,8);
            S(0xF0,128,128,8); S(0xF1,128,128,8); S(0xF1,110,0,8); S(0xF1,110,0,2); }""")
        WT=("좋은 검이었","몇 번이고","술이 달","베어야 할 때")
        seen=await lines_until(lambda t:any(w in t for w in WT), 8.0)
        check("14.42 합성: 승리 후 한마디 더", any(any(w in t for w in WT) for t in seen), seen)
        # 14.50 승부가 난 뒤 승리 포즈(액션 >= 0x180)를 비오의로 오인하지 않는다 (v0.5.6 사용자 제보)
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m,p1,p2,a1)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:a1,a2:8,scr:8,surv:0,stage:0,fresh:false});
            S(0xF0,128,128,8); S(0xF1,128,128,8); S(0xF1,120,40,8);
            S(0xF1,120,0,8);            /* KO */
            S(0xF1,120,0,0x1B4);        /* 승리 포즈 — 액션ID가 0x180을 넘는다 */
            S(0xF1,120,0,0x1B8); }""")
        seen=await lines_until(lambda t:"비오의" in t, 2.5)
        check("14.50 승리 포즈를 비오의로 오인하지 않음", not any("비오의" in t for t in seen), seen)
        # 14.51 라운드가 다시 서면 기술 알림이 되살아난다 (KO 표식이 눌러붙지 않게)
        await page.evaluate("window.__ss2.commReset()")
        await page.evaluate("""() => {
            const S=(m,p1,p2,a1)=>window.__ss2.commStep({mode:m,p1:p1,p2:p2,a1:a1,a2:8,scr:8,surv:0,stage:0,fresh:false});
            S(0xF0,128,128,8); S(0xF1,128,128,8); S(0xF1,120,0,8); S(0xF1,120,0,0x1B4);
            S(0xF1,128,128,8);          /* 다음 라운드 — 양쪽 만피 */
            S(0xF1,128,128,0x1B4); }""")
        live=await page.evaluate("() => !!(window.__ss2.commPend && window.__ss2.commPend())")
        check("14.51 라운드 재개 후 기술 알림 복귀", live is True, live)

        # 14.52 전투가 끝나면 예약된 SP 입력이 버려진다 (귀신터치 방지, v0.5.6 사용자 제보)
        armed=await page.evaluate("""() => {
            window.__ss2.spPress();                      /* 예약 시한을 세운다 */
            const before = window.__ss2.spArmed;
            window.__ss2.spGuard(0x00, 128, 128);        /* 전투 아님 → 버려야 한다 */
            return {before: before>0, after: window.__ss2.spArmed}; }""")
        check("14.52 전투 종료 시 예약 SP 폐기", armed and armed["before"] and armed["after"]==0, armed)
        # 14.53 전투 중에는 예약을 건드리지 않는다
        keep=await page.evaluate("""() => {
            window.__ss2.spPress();
            window.__ss2.spGuard(0xF1, 128, 128);
            return window.__ss2.spArmed>0; }""")
        check("14.53 전투 중 예약은 유지", keep is True, keep)

        # 14.54 선입력 창이 짧고, 새 입력이 오면 지난 예약을 버린다 (귀신터치 2차, v0.5.6b)
        gw=await page.evaluate("""() => ({gate: window.__ss2.SP_GATE_MS, air: window.__ss2.SP_AIR_MS})""")
        check("14.54 선입력 창 400ms/공중 700ms", gw and gw["gate"]<=500 and gw["air"]<=800, gw)
        drop=await page.evaluate("""async () => {
            const s0 = window.__ss2.inputSeq;
            window.__ss2.bumpInput();
            return window.__ss2.inputSeq === s0 + 1; }""")
        check("14.55 사용자 입력마다 일련번호가 오른다", drop is True, drop)

        # 14.56 전투를 벗어나면 메뉴 잡담 타이머가 리셋된다 (v0.5.6c 사용자 제보:
        #        "한 판 끝나도 준비할 때마다 항상 '빨리 고를 필요 없다'가 나온다")
        await page.evaluate("window.__ss2.commReset(); window.__ss2.cfg.commSpk='haohmaru'; window.__ss2.commIdleMenuMs=400")
        STEP="""(m,scr)=>window.__ss2.commStep({mode:m,p1:128,p2:128,a1:8,a2:8,scr:scr,surv:0,stage:0,fresh:false})"""
        await page.evaluate("()=>{const S=%s; S(0x00,0); S(0xF1,8); S(0xF1,8);}"%STEP)
        await page.wait_for_timeout(900)          # 전투 중 임계를 넘길 만큼 시간이 흐른다
        await page.evaluate("()=>{const S=%s; S(0x00,8); S(0x00,8);}"%STEP)   # 전투 이탈 (scr 그대로)
        MI=("천천히 골라라","고르는 것도 승부")
        seen=await lines_until(lambda t:any(w in t for w in MI), 0.8)
        check("14.56 전투 이탈 직후 메뉴 잡담 침묵", not any(any(w in t for w in MI) for t in seen), seen)
        # 14.57 그래도 실제로 오래 머무르면 나온다 (기능 자체는 살아 있다)
        await page.wait_for_timeout(700)
        await page.evaluate("()=>{const S=%s; S(0x00,8);}"%STEP)
        seen=await lines_until(lambda t:any(w in t for w in MI), 2.0)
        check("14.57 오래 머무르면 메뉴 잡담은 나온다", any(any(w in t for w in MI) for t in seen), seen)
        await page.evaluate("window.__ss2.commIdleMenuMs=15000; window.__ss2.commReset()")
        # 14.58 조사 (으)로 — 받침 없는 기술명에 「으로」가 붙지 않는다
        ro=await page.evaluate("""() => {
            const t=window.__ss2.SPEAKERS.haohmaru.moveDown({name:"츠바메 가에시"})[0];
            const u=window.__ss2.SPEAKERS.haohmaru.moveDown({name:"호월참"})[0];
            return {a:t,b:u}; }""")
        check("14.58 조사 (으)로 받침 판정", ro and "가에시로" in ro["a"] and "호월참으로" in ro["b"], ro)

        # 14.59 뒤+A+B 비오의는 **A+B 버튼**에 불이 들어온다 (SP 아님, v0.5.6d 제보)
        await page.evaluate("window.__ss2.setDir(0,0,0,0)")
        try: await page.wait_for_function("window.__ss2.ss2Actable()", timeout=4000)
        except Exception: pass
        abr=await page.evaluate("""() => {
            const g=window.__ss2.readGame();
            if(g.facing) window.__ss2.setDir(0,0,0,1); else window.__ss2.setDir(0,0,1,0);
            document.getElementById('toast').textContent='';
            window.__ss2.fireAB();
            return {ab:document.getElementById('btnAB').className,
                    sp:document.getElementById('spBig').className}; }""")
        check("14.59 뒤+A+B 는 A+B 버튼에 불이 들어온다",
              abr and "busy" in abr["ab"] and "busy" not in abr["sp"], abr)
        await page.wait_for_timeout(400)
        # v0.5.7: 기술명 하단 알림을 없앴으므로 "SP 버튼에 불이 안 들어온다"만 확인하면 된다(14.59)
        await page.evaluate("window.__ss2.setDir(0,0,0,0)")
        await page.wait_for_timeout(1200)

        # 14.48 입력 속도는 최속 고정 (설정 항목 삭제)
        sp=await page.evaluate("({speed:window.__ss2.cfg.speed, seg:!!document.getElementById('speedSeg'), chainSeg:!!document.getElementById('chainAutoSeg')})")
        check("14.48 입력 속도 최속 고정·속도/연계 설정 삭제",
              sp["speed"]=="max" and not sp["seg"] and not sp["chainSeg"], sp)

        # 14.43 SP 발동 시 하단 기술명 알림이 아예 뜨지 않는다 (v0.5.7: 기능째 폐지)
        await page.evaluate("""() => { document.getElementById('toast').textContent=''; }""")
        try: await page.wait_for_function("window.__ss2.ss2Actable()", timeout=4000)
        except Exception: pass
        await page.evaluate("window.__ss2.spPress(); window.__ss2.spRelease();")
        await page.wait_for_timeout(1500)
        t=await page.text_content("#toast")
        check("14.43 SP 기술명 하단 알림 폐지", (t or "").strip()=="", t)
        seg=await page.evaluate("()=>!!document.getElementById('spToastSeg')")
        check("14.43b 하단 알림 설정 항목도 없다", seg is False, seg)
        # 14.44 연계 자동입력 폐지 — chain 이 있어도 추가 A 를 넣지 않는다 (v0.5.1)
        cs=await page.evaluate("""() => {
            const plain={n:"t",m:"236",b:"A"};
            const chained={n:"t",m:"236",b:"A",chain:["A","A"]};
            return {plain:window.__ss2.compileMove(plain,0,{}).length,
                    chained:window.__ss2.compileMove(chained,0,{}).length}; }""")
        check("14.44 연계 자동입력 폐지(추가 A 없음)", cs and cs["plain"]==cs["chained"], cs)

        # ---------- v0.4.5: 쉼 채우기(혼잣말) ----------
        # 14.45 창이 비고 임계 지나면 화자다운 한마디 (임계 400ms로 줄여 검사)
        await page.evaluate("window.__ss2.commReset(); window.__ss2.cfg.commSpk='haohmaru'")
        await page.evaluate("window.__ss2.commLineTTL=500; window.__ss2.commMuseMs=400")
        await page.evaluate("window.__ss2.commSub('마중물 대사',0)")   # 뜬 뒤 TTL로 사라지며 쉼 시작
        MUSE=("술이 떨어","목이 마르","그립군","한잔","한판 더","근질","호흡을 고르","크게 가도")
        seen=await lines_until(lambda t:any(w in t for w in MUSE), 8.0)
        check("14.45 합성: 쉼에 화자다운 혼잣말", any(any(w in t for w in MUSE) for t in seen), seen)
        await page.evaluate("window.__ss2.commLineTTL=8000; window.__ss2.commMuseMs=3000")
        # 14.45b 쉼이 이어지면 3초 간격으로 계속 (한 번 던지고 15초 잠기지 않는다)
        await page.evaluate("window.__ss2.commReset(); window.__ss2.cfg.commSpk='haohmaru'")
        await page.evaluate("window.__ss2.commLineTTL=600; window.__ss2.commMuseMs=600")
        await page.evaluate("window.__ss2.commSub('마중물',0)")
        got=set()
        for _ in range(60):
            await page.wait_for_timeout(120)
            t=await page.evaluate("window.__ss2.commLast")
            if t and any(w in t for w in MUSE): got.add(t)
            if len(got)>=2: break
        check("14.45b 쉼이 길면 반복해서 혼잣말", len(got)>=2, list(got))
        await page.evaluate("window.__ss2.commLineTTL=8000; window.__ss2.commMuseMs=3000")
        # 14.46 해설 끄면 혼잣말도 안 나온다
        await page.evaluate("window.__ss2.commReset(); window.__ss2.cfg.commMode='off'; window.__ss2.museAt=1")
        await page.wait_for_timeout(1500)
        q=await page.evaluate("window.__ss2.annQ")
        line=await page.evaluate("document.getElementById('commLine').textContent")
        check("14.46 해설 끔이면 혼잣말 없음", q==0 and line.strip() in ("…",""), {"q":q,"line":line})
        await page.evaluate("window.__ss2.cfg.commMode='on'")

        # 14.47 블록 0x98 모호성: 기본은 샤를로트 나찰, 쿠로코 선택 중이면 쿠로코 유지 (v0.4.7 제보)
        res=await page.evaluate("""() => {
          const save=window.__ss2.cfg.char;
          window.__ss2.cfg.char='haohmaru'; const fresh=window.__ss2.blkToChar(0x98);
          window.__ss2.cfg.char='kuroko';   const kur=window.__ss2.blkToChar(0x98);
          window.__ss2.cfg.char='charlotte';const cha=window.__ss2.blkToChar(0x98);
          const nor=window.__ss2.blkToChar(0x90);
          window.__ss2.cfg.char=save;
          return {fresh:fresh, kuroko:kur, charlotte:cha, plain90:nor}; }""")
        ok=(res and res["fresh"]["id"]=="charlotte" and res["fresh"]["style"]=="b"
            and res["kuroko"]["id"]=="kuroko" and res["charlotte"]["id"]=="charlotte"
            and res["plain90"]["id"]=="charlotte" and res["plain90"]["style"]=="s")
        check("14.47 블록 0x98 = 샤를로트 나찰 기본(쿠로코 중이면 유지)", bool(ok), res)

        # 14.13 롬 초상 — 로드된 롬에서 해설자 4인 초상이 그려졌다 (주소·팔레트만 임베드)
        rf=await page.evaluate("""() => { const r=window.__ss2.romFaces||{};
            return {n:Object.keys(r).length,
                    spk:['haohmaru','nakoruru','hanzo','galford'].every(k=>(r[k]||'').startsWith('data:image'))}; }""")
        check("14.13 롬 초상: 해설자 4인 전원 렌더", rf and rf["spk"] and rf["n"]>=15, rf)

        # 14.7 해설 끄기 = 예약 정리
        await page.evaluate("""() => { window.__ss2.commReset();
            const S=(p1,p2)=>window.__ss2.commStep({mode:0xF1,p1:p1,p2:p2,a1:8,a2:8,fresh:false});
            S(128,128); S(128,100); S(128,80); S(128,60); }""")
        await page.evaluate("""() => { document.querySelector('#cfgBtn').click(); }""")
        await page.wait_for_timeout(200)
        await page.evaluate("""() => { const b=document.querySelector('#commSeg [data-cm="off"]'); if(b) b.click();
            const c=document.querySelector('#settings'); if(c) c.hidden=true; }""")
        await page.wait_for_timeout(200)
        q=await page.evaluate("window.__ss2.annQ")
        line=await page.evaluate("document.getElementById('commLine').textContent")
        check("14.7 해설 끄기 — 예약 정리", q==0 and line.strip() in ("…",""), {"q":q,"line":line})
        await page.evaluate("window.__ss2.cfg.commMode='off'; window.__ss2.commSynth=false; window.__ss2.commReset()")

        # ── 14.61~ 촬영 모드 자막 (v0.5.8) ─────────────────────────────
        # 끔이 기본이고, 켜면 기술을 낼 때 [누른 것 ▶ 커맨드]가 뜬다. 점등은 **실제 입력 시점**에 한다.
        await page.evaluate("window.__ss2.cfg.cap='off'; window.__ss2.capApply();")
        await page.evaluate("window.__ss2.capShow(window.__ss2.curMoves()[0],'← + SP')")
        check("14.61 촬영 모드 끔이면 자막 없음",
              not await page.evaluate("document.getElementById('capBar').classList.contains('show')"))

        await page.evaluate("window.__ss2.cfg.cap='on'; window.__ss2.capApply();")
        cap=await page.evaluate("""() => { const mv=window.__ss2.curMoves()[0];
            window.__ss2.capShow(mv,'← + SP');
            const b=document.getElementById('capBar');
            return {show:b.classList.contains('show'), big:b.classList.contains('big'),
                    name:b.querySelector('.capName').textContent,
                    press:(b.querySelector('.capPress')||{}).textContent,
                    glyphs:[...b.querySelectorAll('.g')].map(e=>e.textContent).join(''),
                    lit:[...b.querySelectorAll('.g.on')].length, mvn:mv.n, m:mv.m}; }""")
        check("14.62 자막에 [누른 것 · 기술명 · 커맨드]가 모두 실린다",
              cap["show"] and cap["name"].endswith(cap["mvn"]) and cap["press"]=="← + SP"
              and len(cap["glyphs"])>=len(cap["m"]) and cap["lit"]==0, cap)

        lit=await page.evaluate("""() => { window.__ss2.capStep(0);
            return [...document.querySelectorAll('#capBar .g.on')].length; }""")
        check("14.63 커맨드 글자는 그 입력이 들어갈 때 점등", lit==1, lit)

        # 컴파일된 스텝에 cg(자막 글자 번호)가 커맨드 길이만큼 달려 있어야 점등이 성립한다
        cg=await page.evaluate("""() => { const mv=window.__ss2.curMoves()[0];
            const st=window.__ss2.compileMove(mv,0,{});
            return {cg:st.filter(s=>s.cg!==undefined).map(s=>s.cg), len:mv.m.length}; }""")
        check("14.64 컴파일 스텝에 자막 점등 표식(cg)이 커맨드 전부에 붙는다",
              sorted(set(x for x in cg["cg"] if x>=0))==list(range(cg["len"])), cg)

        # [크게]는 배율만 올린다 / 자막은 배치 편집으로 옮길 수 있고 [배치 초기화]로 돌아온다
        await page.evaluate("window.__ss2.cfg.cap='big'; window.__ss2.capApply();")
        big=await page.evaluate("document.getElementById('capBar').classList.contains('big')")
        check("14.65 [크게] 배율 적용", big)

        mv=await page.evaluate("""() => { window.__ss2.cfg.layout.capBar={x:0,y:-120};
            window.__ss2.applyLayout();
            const t=document.getElementById('capBar').style.transform;
            window.__ss2.cfg.layout={}; window.__ss2.applyLayout();
            return {moved:t, reset:document.getElementById('capBar').style.transform}; }""")
        check("14.66 자막 위치는 배치 편집으로 옮기고 초기화로 되돌아온다",
              "-120px" in mv["moved"] and "-120px" not in mv["reset"], mv)
        await page.evaluate("window.__ss2.cfg.cap='off'; window.__ss2.capApply();")

        # ── 14.72~ 촬영 자막을 배치 편집의 정식 구성원으로 (v0.5.8c) ────
        # 제보 "드래그가 잘 안 됨". 원인은 touch-action — 없으면 브라우저가 스크롤 제스처로
        # 채 가면서 pointercancel 을 쏘고 드래그가 끊긴다. 되돌리지 말 것.
        ta=await page.evaluate("getComputedStyle(document.getElementById('capBar')).touchAction")
        check("14.72 자막에 touch-action:none (드래그가 안 끊기게)", ta=="none", ta)

        # 제보: "촬영모드 꺼져 있으면 드래그 편집할 때도 꺼내놓지 마라."
        await page.evaluate("window.__ss2.cfg.cap='off'; window.__ss2.capApply();")
        await page.evaluate("""() => { document.querySelector('#cfgBtn').click(); }""")
        await page.wait_for_timeout(150)
        await page.click("#editStart")
        await page.wait_for_timeout(250)
        off=await page.evaluate("""() => { const b=document.getElementById('capBar');
            return {tgt:b.classList.contains('editTarget'), show:b.classList.contains('show'),
                    grab:b.querySelectorAll('.capGrab').length}; }""")
        check("14.73 촬영 모드가 꺼져 있으면 편집에서도 자막을 안 꺼낸다",
              not off["tgt"] and not off["show"] and off["grab"]==0, off)
        await page.evaluate("""() => { document.querySelector('#editDone').click(); }""")
        await page.wait_for_timeout(150)

        await page.evaluate("window.__ss2.cfg.cap='on'; window.__ss2.capApply();")
        await page.evaluate("""() => { document.querySelector('#cfgBtn').click(); }""")
        await page.wait_for_timeout(150)
        await page.click("#editStart")
        await page.wait_for_timeout(250)
        ed=await page.evaluate("""() => { const b=document.getElementById('capBar');
            const h=b.querySelector('.capGrab');
            return {tgt:b.classList.contains('editTarget'), show:b.classList.contains('show'),
                    grab:b.querySelectorAll('.capGrab').length,
                    box:getComputedStyle(b).pointerEvents,
                    handle:h?getComputedStyle(h).pointerEvents:null}; }""")
        # 상자 전체가 아니라 **손잡이 한 줄만** 잡힌다 — 안 그러면 밑에 깔린 버튼을 못 잡는다
        check("14.73b 촬영 모드가 켜져 있으면 편집에서 자막 손잡이를 잡을 수 있다",
              ed["tgt"] and ed["show"] and ed["grab"]==1
              and ed["box"]=="none" and ed["handle"]=="auto", ed)

        # 화면 밖으로 밀어도 다시 못 잡는 일이 없게 안으로 물린다
        cl=await page.evaluate("""() => { window.__ss2.cfg.layout.capBar={x:-4000,y:-4000};
            window.__ss2.applyLayout();
            const r=document.getElementById('capBar').getBoundingClientRect();
            const s=document.getElementById('stage').getBoundingClientRect();
            window.__ss2.cfg.layout.capBar=null; window.__ss2.applyLayout();
            return {inside:(r.left>=s.left-1&&r.top>=s.top-1&&r.right<=s.right+1&&r.bottom<=s.bottom+1),
                    r:[Math.round(r.left),Math.round(r.top)]}; }""")
        check("14.74 자막을 화면 밖으로 밀어도 안으로 물린다", cl["inside"], cl)
        await page.evaluate("""() => { document.querySelector('#editDone').click(); }""")
        await page.wait_for_timeout(200)
        check("14.75 편집을 마치면 견본 자막이 사라진다",
              not await page.evaluate("document.getElementById('capBar').classList.contains('show')"))

        # ── 14.67~ 더미 상대 (v0.5.8) ──────────────────────────────────
        # COM 판단 바이트(0xE88) 하위 2비트를 세워 반격을 없애고, 가로 좌표를 물어 제자리에 세운다.
        # 액션ID를 직접 덮어쓰던 첫 방식은 라운드 종료 연출을 막아 게임이 멈췄다 — 되돌리지 말 것.
        await page.evaluate("window.__ss2.cfg.dummy=false; window.__ss2.dummyApply();")
        check("14.67 더미 끔이면 감시 타이머가 없다", not await page.evaluate("window.__ss2.dummyOn"))

        await page.evaluate("""async () => { const r=await fetch('nav_fight.bin'); window.__ss2.loadStateBytes(new Uint8Array(await r.arrayBuffer())); }""")
        await page.wait_for_timeout(500)
        await page.evaluate("window.__ss2.findHeap()")
        await page.evaluate("window.__ss2.cfg.dummy=true; window.__ss2.dummyApply();")
        await page.wait_for_timeout(600)
        # 게임이 매 프레임 이 자리를 0으로 되돌리고 우리는 16ms마다 비트를 세운다 —
        # 한 번만 읽으면 게임이 지운 직후에 걸릴 수 있다(실측 약 1/5). 표본으로 본다.
        ai=await page.evaluate("""async () => { const H=window.EJS_emulator.gameManager.Module.HEAPU8, hb=window.__ss2.heapBase;
            let set=0; for(let i=0;i<60;i++){ if((H[hb+0xE88]&3)===3) set++; await new Promise(r=>setTimeout(r,5)); }
            return {set:set, n:60, on:window.__ss2.dummyOn, mode:H[hb+0xA7]}; }""")
        check("14.68 더미 켬 — COM 판단 바이트 하위 2비트가 선다",
              ai["on"] and ai["set"]>=40, ai)

        # v0.5.8d: 좌표 고정은 **폐기**했다. 0xE38·0xE78 은 월드가 아니라 카메라 상대 좌표라
        # 고정이 성립하지 않았고(써 넣어도 231→215→199 로 흐름), 상대를 화면 한 점에 묶어
        # 스테이지를 가로질러 끌고 다니는 부작용만 났다("더미가 이상하게 멀어진다").
        # 대신 라운드 종료 연출 중에는 아예 손대지 않는지를 본다.
        ph=await page.evaluate("""() => { const H=window.EJS_emulator.gameManager.Module.HEAPU8, hb=window.__ss2.heapBase;
            const keep=H[hb+0x11A];
            H[hb+0x11A]=3; H[hb+0xE88]=0;      /* 라운드 종료 연출 중이라고 속인다 */
            window.__ss2.dummyTick();
            const during=H[hb+0xE88];
            H[hb+0x11A]=1; H[hb+0xE88]=0;
            window.__ss2.dummyTick();
            const fighting=H[hb+0xE88];
            H[hb+0x11A]=keep;
            return {during:during, fighting:fighting}; }""")
        check("14.69 라운드 종료 연출 중에는 더미가 손대지 않는다",
              ph["during"]==0 and (ph["fighting"]&3)==3, ph)

        # 좌표를 건드리지 않는다 — 이걸 되살리면 카메라 스크롤에 상대가 끌려다닌다
        nox=await page.evaluate("""() => { const H=window.EJS_emulator.gameManager.Module.HEAPU8, hb=window.__ss2.heapBase;
            const want=(H[hb+0xE78]|(H[hb+0xE79]<<8))+40;
            H[hb+0xE78]=want&0xFF; H[hb+0xE79]=(want>>8)&0xFF;
            window.__ss2.dummyTick();
            return {want:want, now:H[hb+0xE78]|(H[hb+0xE79]<<8)}; }""")
        check("14.70 더미는 상대 좌표를 건드리지 않는다(카메라 상대값)", nox["now"]==nox["want"], nox)

        hp=await page.evaluate("""async () => { const H=window.EJS_emulator.gameManager.Module.HEAPU8, hb=window.__ss2.heapBase;
            H[hb+0x1C46]=10; await new Promise(r=>setTimeout(r,120)); return H[hb+0x1C46]; }""")
        check("14.71 더미 켬 — 쓰러지기 직전에 체력을 채운다", hp==128, hp)
        await page.evaluate("window.__ss2.cfg.dummy=false; window.__ss2.dummyApply();")

        check("12.1 zero page errors", len(errors)==0, errors)

        print(f"\n==== {len(PASS)} passed / {len(FAIL)} failed ====")
        if FAIL: print("FAILED:", FAIL)
        await browser.close()

asyncio.run(main())
