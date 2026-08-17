# 사무라이 스피리츠! 2 — SP 버튼 실행기

**[▶ 바로 실행하기](https://rmdkdkr-png.github.io/ss2-sp-runner/)**

『사무라이 스피리츠! 2』(네오지오 포켓 컬러)를 브라우저에서 돌리면서,
**필살기를 버튼 하나로** 낼 수 있게 만든 실행기입니다. 파일 하나로 끝나고, 설치가 없습니다.

> 게임 자체의 입력 결함과 플레이어인 저의 손 결함에 대해
> 모던 모드를 만들어보고자 하였던 몸부림입니다.

---

## 쓰는 법

1. 위 **바로 실행하기** 를 누릅니다 (폰·PC 모두 됩니다)
2. **본인이 가지고 있는 롬 파일** 을 고릅니다 — `.ngc` / `.ngp` / `.npc`
3. 화면 아래 **SP 버튼** 하나 + 방향키로 필살기가 나갑니다

**롬은 이 저장소에 들어 있지 않고, 앞으로도 넣지 않습니다.** 본인이 소유한 파일을 쓰십시오.
롬은 브라우저 안에서만 열리며 어디로도 전송되지 않습니다.

### 조작

| 입력 | 나가는 것 |
|---|---|
| SP 만 | 중립 필살기 |
| → + SP | 앞 |
| ← + SP | 뒤 |
| ↓ + SP | 아래 |
| ↓→ / ↓← + SP | 대각 자리 |
| 점프 중 SP | 공중기 |

방향은 **캐릭터가 보는 쪽 기준**입니다. 좌우는 실행기가 알아서 뒤집습니다.
좌우 반전 스위치 같은 건 없습니다 — 있을 필요가 없게 만들었습니다.

버튼은 **길게 눌러 끌면 위치와 크기를 바꿀 수 있습니다.** 손 모양에 맞춰 두시면 됩니다.

---

## 왜 이런 걸 만들었나

삼스2는 커맨드 판정이 인색합니다. `623` 을 십자키로 정확히 넣는 것도 어렵지만,
더 성가신 건 **제대로 넣었는데 엉뚱한 기술이 나가는 경우**입니다.

롬을 뜯어보니 커맨드 판정 루틴(`0x202E8B`)이 입력 기록을 **거꾸로 훑으면서
안 맞는 입력은 건너뜁니다.** 그래서 직전 입력 찌꺼기가 남아 있으면
**짧은 커맨드가 긴 커맨드를 가로챕니다.** 손이 느린 게 아니라 구조가 그렇습니다.

이 실행기는 버튼을 누른 프레임에 두 가지를 합니다.

1. 램 `0x1DCD` 에 **1바이트**를 써서 게임이 스스로 입력 기록을 정리하게 합니다
   (게임 자신의 리셋 경로를 부르는 것이지, 기록을 조작하는 게 아닙니다)
2. 현재 캐릭터·유파에 맞는 커맨드를, 보고 있는 방향에 맞춰 뒤집어 프레임 단위로 넣습니다

**없는 기술을 만들어내거나 게임 데이터를 고치지 않습니다. 입력만 대신 넣습니다.**
히트스톱(맞고 있는 중)이나 공중 판정도 게임 규칙 그대로 지킵니다.
헛손질한 잡기도 실기와 똑같이 헛손질로 나갑니다.

### 검증

| | 결과 |
|---|---|
| 커맨드 하이재킹 (7종 × 6회) | 무보정 0/42 → **41/42** |
| 긴 커맨드 5토큰, 각 20회, 지상·비피격 | 표준 20/20 · 빠름 19/20 · 최속 20/20 |
| 발동까지 걸리는 시간 | 표준 433ms · 빠름 350ms · 최속 267ms |
| 3연참 연속 입력 손상 | 없음 |

---

## 성능에 관한 발견

만들면서 **화면을 만지고 있는 동안 게임이 느려지는** 문제를 오래 쫓았습니다.
원인은 제 코드가 아니라, 에뮬레이터가 그림을 그리는 캔버스가
**"뒤가 비쳐 보이는" 설정**으로 만들어져 있던 것이었습니다.
브라우저가 매 합성마다 쓸데없이 겹쳐 그리면서 에뮬레이터 루프를 굶겼습니다.

속성 두 개를 불투명으로 바꾸자 이렇게 달라졌습니다.

| 상황 | 고치기 전 | 고친 뒤 |
|---|---|---|
| 십자키를 손가락으로 끌 때 | 51.8 fps / 끊김 65회 | **59.6 fps / 3회** |
| 필살기 버튼 연타 | 56.4 / 26 | **59.4 / 4** |
| 셰이더 `2xScaleHQ` | 49.1 / 86 | **59.5 / 1** |

숫자는 브라우저가 그린 프레임이 아니라 **에뮬레이터가 실제로 돌린 프레임 수**입니다.
셰이더가 비싸 보이던 것도 상당 부분 이 합성 비용이 겹친 결과였습니다.

이건 삼스2와 무관하게 EmulatorJS를 쓰는 모든 곳에 해당합니다. 별도로 제보했습니다.

---

## 같은 엔진의 다른 판

| | 저장소 |
|---|---|
| **레트로아크 코어** (안드로이드·PC·휴대기기) | [ss2-sp-core](https://github.com/rmdkdkr-png/ss2-sp-core) |
| **NGP.emu 안드로이드 앱** | [emu-ex-plus-alpha 포크](https://github.com/rmdkdkr-png/emu-ex-plus-alpha) |

브라우저판이 가장 손대기 쉽고, 코어판·앱판은 폰에서 더 매끄럽습니다.

---

## 만든 것 / 안 만든 것

- 기술표는 **16캐릭터 / 30유파 / 185기술** 을 롬에서 뽑아 만들었습니다
- 카드 전용 기술과 초필살기도 일반 기술 목록에 함께 들어 있습니다
- 한글 패치본 기준이며, 일본어 롬을 넣으면 일본어로 뜹니다

---

## 라이선스 · 고지

EmulatorJS 및 Beetle NeoPop(Mednafen) 위에서 동작합니다. 각 프로젝트의 라이선스를 따릅니다.

SAMURAI SPIRITS™ / SAMURAI SHODOWN™ 의 저작권은 SNK CORPORATION 에 있습니다.
본 프로젝트는 **SNK와 무관한 비공식 팬 제작물**이며, 게임 롬을 포함하거나 배포하지 않습니다.

---

## English

A single-file browser front-end for *Samurai Shodown! 2* (Neo Geo Pocket Color) that lets you
perform special moves with **one button plus a direction**, as an accessibility aid.

The game's command matcher scans the input ring **backwards, skipping non-matching samples**,
so leftover inputs let short commands hijack long ones. This front-end writes one byte to
`0x1DCD` to invoke the game's *own* ring-reset routine, then feeds the correct command
frame-by-frame, mirrored according to the facing flag read from RAM. It does not modify game
data or create moves that do not exist — it only supplies inputs, and it respects hitstop and
air-state gating.

No ROM is included or distributed. Bring your own.

While building this I found that the EmulatorJS WebGL canvas is created with `alpha: true`,
which costs roughly 8 fps and 20× more frame hitches while the screen is being touched.
Details and measurements are in the linked issue.
