# archdraw スキル (新) と arch-builder (旧) の盲検比較 — 2026-10-03

## 結論

同じ課題の最終 PNG を、作り方を伏せて 1 対 1 で比べた。9 組のうち 8 組で新スキルの図が「より明確」とされた。
可読性の平均は 新 6.7 / 旧 5.4 (10 点満点)、設計レビューに使えるか (Pass) は 新 8/9 / 旧 5/9。

| Eval | 組 | 新 | 旧 | より明確 |
| --- | --- | --- | --- | --- |
| 1 Fargate/Aurora | run-1 | 7 Pass | 6 Pass | 新 |
| 1 | run-2 | 7 Pass | 7 Pass | 旧 (差は小さい) |
| 2 サーバーレス | run-1 | 8 Pass | 6 Pass | 新 |
| 2 | run-2 | 7 Pass | 6 Pass | 新 |
| 2 | run-3 | 7 Pass | 6 Pass | 新 |
| 3 修正課題 | run-1 | 7 Pass | 5 Fail | 新 |
| 3 | run-2 | 6 Pass | 5 Fail | 新 |
| 4 AgentCore | run-1 | 6 Pass | 4 Fail | 新 |
| 4 | run-2 | 5 Fail | 4 Fail | 新 |

## 方法

- 旧: `arch-builder-workspace/iteration-12/` の 2026-09-28 の最終 PNG (各 run の outputs/)。旧の評価で盲検 Pass したもの
- 新: `iteration-15-archdraw/eval-N/run-K/` の最終 PNG。executor は Opus、批評は Sonnet (スキルの手順どおり)。
  run-1 はエンジンを直す前に作った定義を、最終のエンジンで build し直した PNG (`rebuilt/`。lint の件数は変わらない)
- 盲検レビュー: Sonnet 1 体。依頼文と PNG の組だけを見せ、A/B はランダム (`blind/key.json`)。指示は `blind-review-instructions.md`

## 制約

- 費用を抑えるため、run は各 2 回 (Eval 2 は 3 回)。Eval 1・3・4 の 3 回目は途中で止めた
- レビュー担当は 1 体。9/28 の旧評価のレビュー担当とは別なので、点数の絶対値は 9/28 の値 (Eval 2 で 9/10 など) と比べられない。比べられるのは同じレビュー担当がつけた新旧の差だけ
- 新スキルの自己批評 (Sonnet) では、Eval 3 run-2 と Eval 4 の 2 回が不合格のまま納品された。Eval 4 は新旧とも読みにくさが残る (Role への長い破線)

## 新スキルの lint (納品した .drawio)

| Eval | run-1 | run-2 | run-3 |
| --- | --- | --- | --- |
| 1 | warn 2 | warn 0 | (中止) |
| 2 | warn 2 | warn 0 | warn 0 |
| 3 | warn 0 | warn 7 | (中止) |
| 4 | warn 10 | warn 5 | (中止) |

すべて error 0。旧 (9/28) は Eval 1 warn 2、Eval 2 warn 0、Eval 3 warn 6〜10、Eval 4 warn 10。
