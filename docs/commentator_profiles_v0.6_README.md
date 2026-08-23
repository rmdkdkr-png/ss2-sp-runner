# commentator_profiles v0.6 — 구현 메모

이 JSON은 기존 설정조사와 동기/이벤트 설계를 코드에 바로 넣기 위한 초기 프로필이다.

## 최소 사용법

1. 게임 이벤트를 감지한다.
2. 각 해설자의 `core_events`에서 관심도를 읽는다.
3. `relation_overrides`가 있으면 일반 이벤트보다 먼저 적용한다.
4. `silence_weight`와 `round_talk_budget`로 과잉 발화를 억제한다.
5. `taboo`와 `global_rules.false_lore_guards`는 생성 후 필터가 아니라 **생성 전 차단 규칙**으로 쓴다.
6. `sample_lines`는 완성 대사집이 아니라 말투/판단의 seed다.

## 권장 런타임 상태

```json
{
  "last_event_type": null,
  "last_semantic_group": null,
  "last_line_id": null,
  "same_move_count": 0,
  "failed_pattern_count": 0,
  "successful_pattern_count": 0,
  "momentum_owner": null,
  "control_owner": null,
  "comeback_stage": 0,
  "round_comment_count": 0,
  "relationship_comment_count": 0,
  "character_core_comment_count": 0
}
```

## 다음 구현 단계

- event detector가 내는 실제 키 이름과 JSON의 `core_events`를 맞춘다.
- 기존 v1.6.x 감시자 이벤트 중 확실하게 잡히는 것부터 연결한다.
- READ_SUCCESS / REPEAT / ADAPT / COMEBACK / LOW_HP / WHIFF_PUNISH를 1차 구현한다.
- 추상 판정(CHOICE, RESTRAINT, VALUE_CHANGE)은 후순위로 둔다.
