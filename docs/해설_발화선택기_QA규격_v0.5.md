# SS2 해설 엔진 — 발화 선택기·상태기계·QA 규격 v0.5

## 1. 목적
앞 단계의 설정조사 → 동기 축 → 이벤트 반응 매트릭스를 실제 발화 선택 규칙으로 연결한다.

## 2. 최종 파이프라인
RAW GAME STATE → EVENT DETECTOR → DERIVED EVENT → RELATION OVERRIDE → COMMENTATOR INTEREST → MEMORY → CANDIDATE SCORING → ANTI-REPEAT → SILENCE GATE → LINE FAMILY → FINAL LINE

기술 감지 자체보다 관계, 희귀 상태, 캐릭터 핵심 사건을 우선한다.

## 3. 후보 점수
score = EVENT_PRIORITY + INTEREST + RELATION_BONUS + RARITY_BONUS + NARRATIVE_BONUS + CHARACTER_CORE_BONUS - REPETITION_PENALTY - RECENCY_PENALTY

핵심 사건:
- 하오마루: RISK / COMEBACK
- 겐주로: KILL_CHANCE / PUNISH
- 나코루루: DANGER / OVERKILL
- 리무루루: LOW_HP / COMEBACK
- 한조: READ_SUCCESS
- 갈포드: SPECTACLE / COMEBACK
- 쥬베이: CLEAN_FUNDAMENTAL / ADAPT
- 우쿄: ONE_CHANCE / PRECISION
- 샬롯: PRECISION / RANGE_CONTROL
- 카즈키: MOMENTUM
- 소게츠: CONTROL / ADAPT
- 아수라: RESIST
- 시키: CHOICE
- 타이잔: RESTRAINT / LOSS_OF_CONTROL
- 유가: VALUE_CHANGE

## 4. Narrative / Callback
단기 기억(5~10초), 라운드 기억, 매치 기억을 둔다.
관찰 → 반복 → 적응/실패 → 결과가 이어지면 일반 감탄보다 콜백 대사를 우선한다.

예:
한조: “저 점프가 잦군.” → 세 번째 점프를 대공 → “이번에는 읽었군.”
쥬베이: “같은 수에 두 번 당했군.” → 다음 라운드 방어 → “이번에는 배웠어.”
타이잔: “마음이 앞서는군.” → 이후 절제 → “이제야 자신을 다스리는군.”

## 5. Event Collapse
700~1200ms 안의 사건은 한 묶음으로 합친다.
WHIFF + ANTI_AIR + HEAVY_HIT + LOW_HP + COMEBACK_SEED가 동시에 생겨도 한 문장만 선택한다.
한조는 READ/PUNISH, 리무루루는 COMEBACK, 우쿄는 PRECISION을 우선할 수 있다.

## 6. Silence Gate
중요도가 낮거나 반복되는 사건은 말하지 않는다.
우쿄·타이잔·시키·소게츠·한조는 침묵 자체를 캐릭터성으로 사용한다.
관계 감정이 커질수록 타이잔/우쿄/시키는 오히려 문장이 짧아지거나 침묵할 수 있다.

## 7. 발화 예산
초기 목표(라운드당):
- 갈포드/리무루루/카즈키 5~8
- 하오마루/나코루루 4~7
- 샬롯/쥬베이/겐주로/유가 3~6
- 한조/소게츠/아수라 3~5
- 우쿄/시키/타이잔 2~5

희귀 관계 사건은 예산 초과 허용.

## 8. Line Family
REACTION / ANALYSIS / WARNING / PRAISE / DISAPPROVAL / CALLBACK / RELATION / RARE_LORE / ROUND_RESULT / MATCH_RESULT

문장을 독립 랜덤으로 뽑지 말고 family 단위로 관리한다.

## 9. RARE_LORE
설정은 설명하지 않고 가끔 새어 나오게 한다.
타이잔 LOSS_OF_CONTROL:
일반 “분노가 눈을 가리는군.”
희귀 “……나도 그랬지.”
한 매치 최대 1회 권장.

## 10. 관계 레벨
REL1 암시 → REL2 이름 호출 → REL3 감정 노출 → REL4 희귀 과거 암시.
대부분 REL1~2에 둔다. 관계 대사가 전술 해설을 매번 덮지 않게 한다.

## 11. 감정 상태
CALM / ENGAGED / EXCITED / TENSE / ANGRY / DISTURBED.
하오마루는 흥분할수록 발화가 커지고, 겐주로는 공격성이 증가한다.
타이잔·시키는 DISTURBED에서 단편화/침묵이 증가한다.
감정은 사건 종료 후 점진적으로 CALM으로 복귀한다.

## 12. SELF_OVERRIDE
해설자 본인이 경기 중이면 3인칭 평가를 피한다.
- 하오마루: 자기 성공을 즐김
- 겐주로: 성공을 당연시
- 한조/우쿄: 자기평가 최소
- 카즈키: 자기 성공에 즉각 반응
- 소게츠: 당연한 결과처럼 처리
- 타이잔: 자기 과잉공격/분노에는 특히 비판적
- 유가: 자기 우위를 당연시

## 13. QA
### Character Identification Test
이름을 지운 대사만 보고 화자를 좁힐 수 있어야 한다.

### Swap Test
타이잔과 카즈키 등 서로의 대사를 바꿔도 자연스러우면 실패.

### Lore Leakage Test
위키 설명처럼 과거사를 직접 말하면 실패.

### False Lore Test
자동 경고:
- 쥬베이 + 딸
- 갈포드 + 한조 + 스승
- 타이잔 + 화가
- 아수라 + 그림자 아수라 + 동일인
- 시키 + 유가 + 자발적 충성
- 카즈키 + 소게츠 + 증오/원수
- 미코토/유다의 NGPC !2 시점 등장
- 검증 전 갈포드-나코루루 연애 확정
- 검증 전 한조 아내 이름

### Overcharacterization Test
갈포드=Yeah, 유가=그릇, 우쿄=말줄임표처럼 대표 표식을 남발하지 않는다.
캐릭터성은 어휘보다 사건 선택과 가치판단에서 나온다.

### Silence Test
일반 HIT까지 계속 말하면 실패. 중요한 사건과 캐릭터 핵심 사건 중심이어야 한다.

### Narrative Test
한 라운드에서 관찰 → 반복 → 적응/실패 → 결과의 연결이 최소 한 번 자연스럽게 형성되는지 본다.

## 14. 구현 우선순위
1. 기존 이벤트에 priority/interest 부여
2. 5~10초 단기 기억
3. REPEAT / READ / ADAPT
4. COMEBACK 단계
5. 캐릭터 Core Event
6. 관계 Override
7. Silence Gate
8. Line Family + cooldown
9. 라운드/매치 기억
10. QA 자동검사

처음부터 모든 추상 이벤트를 완벽히 판정하려 하지 않는다. READ_SUCCESS, REPEAT, COMEBACK, LOW_HP, WHIFF_PUNISH처럼 RAM에서 비교적 확실히 검출 가능한 사건부터 구현한다.

## 15. 다음 단계
다음 문서는 실제 코드에 옮길 수 있는 `commentator_profiles` 데이터 스키마와 15인 초기값을 정의한다. 설정 확정도가 낮은 관계는 LOCKED 상태로 유지한다.
