# arch-builder 評価資料

`arch-builder` Skillの評価手順、各iterationの結果、PNG比較をまとめる作業領域です。配布するSkill本体は [`../skills/arch-builder/`](../skills/arch-builder/SKILL.md) にあります。

## まず見る資料

- [PNG左右比較](png-comparison-iteration-4/compare.md) — iteration-4の最終PNGをwith-skill / without-skillで並べています。
- [iteration-4レビュー](review-2026-09-27-iteration-4.md) — 評価結果、図の品質、修正後のスモーク検証。
- [過去レビュー](review-2026-09-27.md) — iteration-1 / 2のレビューと改善提案。
- [iteration-4検査手順](test.md) — 18 runの実施、採点、集計の手順。
- 修正版スモーク結果 — 基準評価を変更せずに実施した3ケース:
  - [Eval 1: Fargate / Aurora Web](iteration-4-remediation/eval-1-fargate-aurora-web/with_skill/run-1/outputs/report.md)
  - [Eval 2: Serverless Orders](iteration-4-remediation/eval-2-serverless-orders/with_skill/run-1/outputs/report.md)
  - [Eval 3: Flawed diagram repair](iteration-4-remediation/eval-3-fix-flawed-drawio/with_skill/run-1/outputs/report.md)

## 評価履歴

| ディレクトリ | 内容 |
|---|---|
| `iteration-1/`〜`iteration-3/` | 過去の評価runと集計 |
| `iteration-4/` | 3課題 × 2条件 × 3 runの基準評価 |
| `iteration-4-remediation/` | 基準評価を変更せずに実施した、修正版Skillのスモーク検証 |

iterationごとのrun出力は`.gitignore`対象です。手順書、レビュー、比較用Markdownは追跡対象としてこのディレクトリ直下に置いています。
