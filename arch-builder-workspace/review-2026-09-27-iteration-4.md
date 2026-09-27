# arch-builder スキル評価 — 2026-09-27 (iteration-4)

## 評価

| 観点 | 評価 | コメント |
|---|---:|---|
| 設計 | 4/5 | with-skill は設計アサーション 40/42 (95.2%)。VPC の階層、サービス配置、前提の記録は、without-skill の18/42 (42.9%)を上回った。 |
| 図の品質 | 2/5 | with-skill のPNG可読性は2/12 (16.7%)で、without-skill の6/12 (50.0%)を下回った。線ラベルの重なりと配線の密集が残った。 |
| 評価基盤 | 3/5 | 18 runを独立実行し、machine / design / legibility を分けて採点した。3 runの所要時間欠落、Desktop共有画面の分離不十分、集計スクリプトの互換調整が残る。 |

全アサーションのrun単位合格率は with-skill 65.0% ± 11.4%、without-skill 30.7% ± 6.1%。machine 比較は、without-skillにも `.arch.yaml` を要求する条件と、公式Asset Package以外をlintが unmanaged とする条件が含まれるため、with-skillに有利である。図の品質判断には design と legibility を重視する。

## 数値

各値は評価ケース内で3 runの合格率を平均し、標本標準偏差を付けた。単位は `%`。

| 課題 | 条件 | machine | design | legibility |
|---|---|---:|---:|---:|
| Eval 1 Webアプリ | with-skill | 33.3 ± 0.0 | 86.7 ± 23.1 | 0.0 ± 0.0 |
| Eval 1 Webアプリ | without-skill | 11.1 ± 19.2 | 40.0 ± 0.0 | 100.0 ± 0.0 |
| Eval 2 Serverless | with-skill | 44.4 ± 19.2 | 100.0 ± 0.0 | 33.3 ± 28.9 |
| Eval 2 Serverless | without-skill | 0.0 ± 0.0 | 33.3 ± 0.0 | 50.0 ± 0.0 |
| Eval 3 Flawed図の修正 | with-skill | 44.4 ± 19.2 | 100.0 ± 0.0 | 0.0 ± 0.0 |
| Eval 3 Flawed図の修正 | without-skill | 0.0 ± 0.0 | 50.0 ± 0.0 | 0.0 ± 0.0 |
| **全課題・assertion単位** | **with-skill** | **40.7 (11/27)** | **95.2 (40/42)** | **16.7 (2/12)** |
| **全課題・assertion単位** | **without-skill** | **3.7 (1/27)** | **42.9 (18/42)** | **50.0 (6/12)** |

with-skill は設計面で優位だった一方、図の読みやすさは下回った。スキル指示とcriticの合格だけでは、PNG上の線ラベルや混雑を十分に抑えられていない。

## 今回確かめたいこと

1. **流れと接続口 — 一部。** YAML上の設計採点は高いが、最終draw.ioの独立lintで `N-PORT-FACE` / `N-PORT-SLOT` が残るrunがあった。[Eval 1 with-skill run 1](iteration-4/eval-1-fargate-aurora-web/with_skill/run-1/machine.json)、[Eval 1 run 2](iteration-4/eval-1-fargate-aurora-web/with_skill/run-2/machine.json)。
2. **ヘッダー / ボディ / フッター — 一部。** Eval 3 with-skill は2 AZ、ALB、IGWの配置を3/3で満たした。Eval 1では全run一律ではない。[Eval 3 run 1](iteration-4/eval-3-fix-flawed-drawio/with_skill/run-1/grading.json)。
3. **分岐と対称性 — 一部。** Criticを通過した図にも `should` が残り、AZ間の線の高さ・曲がり方が視認性を損ねる指摘があった。[Eval 1 run 2の批評](iteration-4/eval-1-fargate-aurora-web/with_skill/run-2/outputs/.arch-loop/)、[Eval 3 run 3の報告](iteration-4/eval-3-fix-flawed-drawio/with_skill/run-3/outputs/report.md)。
4. **線の読み違い — 不合格。** Eval 1 with-skillはPNG legibilityが0/3、Eval 3も0/3。線ラベル、共有幹、中央の交差が繰り返し問題になった。[Eval 1 run 1の採点](iteration-4/eval-1-fargate-aurora-web/with_skill/run-1/grading.json)、[Eval 3 run 3の採点](iteration-4/eval-3-fix-flawed-drawio/with_skill/run-3/grading.json)。
5. **縦横比 — 一部。** portrait error は最終成果物の主な失敗として現れなかったが、いくつかの図は16:9目安を外れる `N-ASPECT` info が残った。目安を満たすための大回りは、個別PNGを見て判断する必要がある。[Eval 3 run 3 machine結果](iteration-4/eval-3-fix-flawed-drawio/with_skill/run-3/machine.json)。
6. **前提の明示 — 合格 (Eval 3)。** 社内向けの入口を図のnotesと報告に記した。Eval 3 with-skillの該当設計assertionは3/3合格。[Eval 3 run 1](iteration-4/eval-3-fix-flawed-drawio/with_skill/run-1/grading.json)。
7. **最新AWS情報 — 一部。** Asset Package の日付とAWS公式資料は記録された。AWS Knowledge MCPは利用できず、各runが必要な公式情報を漏れなく確認したかは報告ごとに異なる。実行metadataの `aws_knowledge_mcp` は全run false。
8. **完成条件 — 一部。** 大半の最終criticはpassしたが、Eval 1 with-skill run 2は最終批評がfail。別runではPNG legibility graderがラベル重なりを指摘してもcriticはpassしており、critic passだけでは完成の根拠として弱い。[Eval 1 run 2 grading](iteration-4/eval-1-fargate-aurora-web/with_skill/run-2/grading.json)。
9. **接続口の定義 — 不合格。** with-skill全体でmachineのlint assertionは11/27。最終図に `N-PORT-FACE`、`N-PORT-SLOT`、`N-EDGE-BENDS`、`N-EDGE-OVERLAP` 等が残った。[Eval 1 run 1](iteration-4/eval-1-fargate-aurora-web/with_skill/run-1/machine.json)、[Eval 3 run 2](iteration-4/eval-3-fix-flawed-drawio/with_skill/run-2/machine.json)。
10. **枠・接続・ラベル — 不合格。** Eval 3 with-skill run 3の最終図を再lintすると、`web-a` / `web-c` の `N-NODE-UNCONNECTED` が2件。別runでは `N-SPARSE` やラベル警告も残る。[Eval 3 run 3 machine結果](iteration-4/eval-3-fix-flawed-drawio/with_skill/run-3/machine.json)。

## 主な所見

### 1. PNGの可読性がcritiqueのpassに反映されない

- **再現:** Eval 1 with-skill run 1〜3、Eval 3 with-skill run 1〜3。
- **事実:** Eval 1のlegibilityは0/3。Eval 3も0/3。PNGのみの採点では線ラベルと配線の混雑が挙がった。Eval 3 run 3は最終critic passだが、最終lintに未接続ノードが2件あった。
- **改善案:** 最終保存後に同一 `.drawio` をlintし、同じファイルから書き出したPNGを読む。線ラベル同士・他の線との重なり、無関係なノード脇の経路、未接続ノードを完了前に解消する。critic passとlintの古い出力を流用しない。

### 2. 共有幹を許すルールが、個別ラベルの重なりを見逃す

- **再現:** 同一ラベル・同一線種で端点を共有する線。`route.py` と `rules.py` が共有幹ならラベル矩形の重なりも無視していた。
- **事実:** 同じ端点クラスの線もdraw.ioでは各edgeのラベルを別々に描画する。
- **改善:** 修正版では、幹の重なりは許してもラベル重なりを警告し、経路探索でも減点する。回帰テストを追加した。

### 3. Desktopで最終編集した後に、lint結果と納品物がずれる

- **再現:** Eval 1 with-skill run 1、Eval 3 with-skill run 3。
- **事実:** 報告やbuild時のlintがerror 0でも、納品 `.drawio` の再lintではport/sparse/未接続ノード等が増えた。Eval 3 run 3は `N-NODE-UNCONNECTED` が2件。
- **改善:** 修正版SKILL.mdに、Desktop編集後はimportでYAMLへ戻してbuildし直し、最終 `.drawio` 自体をlintし、そのファイルからPNGを作る手順を明記した。

### 4. 評価基盤と集計上の制限

- **事実:** 18 runのうち3つのwith-skill durationは未取得、tokensは全run未記録。skill-creator集計スクリプトは `eval_metadata.id` とnull timingを処理できず、一時コピーだけ補正して実行した。`benchmark.json` では未取得値をnullに戻し、時間統計は記録済み分のみとした。
- **事実:** draw.io DesktopのCLI exportがexit 134で終了したため、Eval 3のPNGはDesktop UIから書き出した。共有UIのsaveダイアログで、別runのファイル名・metadataが一時的に他producerに見える分離上の不備があった。成果物の書き換えは確認されていない。
- **改善案:** runごとに独立したheadless export環境を使い、最後の図・PNG・criticのハッシュをrun metadataに記録する。集計器はnull値を扱えるようにする。

## 前回からの変化

iteration-3のbenchmarkは with-skill 100% ± 0%、without-skill 77% ± 17% と記載するが、保存されたrunはケース差を反復差として扱っており、今回の「同一課題を各条件3回」と直接比較できない。今回の改善点は18回を揃え、3種類の採点を分離したこと。新しい設計指示は設計合格率で優位 (95.2%対42.9%) だった一方、PNG legibilityは低かった (16.7%対50.0%)。iteration-3からの品質向上を統計的に結論づけることはできない。

## 実行条件と制限

- **実行者:** GPT-6 Codex (variantの記録なし)。**design / PNG grader / critic:** `gpt-5.6-terra`。**machine:** `grade_machine.py`。
- **git commit:** `c233eb2`。**Asset Package:** `2026-01-30`。**AWS Knowledge MCP:** 利用不可。必要な確認はAWS公式資料を参照したと各producer reportに記録されている。
- runの中断はなし。初回のuv cacheアクセスは `UV_CACHE_DIR=/private/tmp/arch-builder-uv-cache` に切り替えてdoctor / pytestを通した。修正で回帰テストを1件追加したため、手順書の期待件数を21件から22件へ更新した。
- 全runのmetadata、machine grading、design/legibility grading、集計は [iteration-4](iteration-4/) と [benchmark](iteration-4/benchmark.md) を参照。

## ユーザー依頼による修正版の検証

test.mdは基準評価中にスキル本体を変更しないよう定めている。基準の18 runとその成果物は変更せず、評価完了後にユーザーが総修正を依頼したため、修正後のスキルは別の `iteration-4-remediation/` に保存して検証する。基準集計へ修正後runは混ぜない。

- 修正内容: 共有する幹と個別ラベルの重なりを別判定にする (`route.py`, `rules.py`)。最終のdraw.io編集後にimport/build/lint/renderすること、孤立ノードとラベル重なりを確認することを `SKILL.md` に追記。
- 確認: skill-creator `quick_validate.py` は `Skill is valid!`。pytestは22件通過。
- 3課題の独立したスキル使用スモークrunを実施し、各成果物を別系列 critic で確認した。基準評価の18 runとその統計は変更していない。

| 修正版スモーク | 最終 lint | 独立 critic | 対応した指摘 |
|---|---|---|---|
| [Eval 1: Fargate / Aurora Web](iteration-4-remediation/eval-1-fargate-aurora-web/with_skill/run-1/outputs/report.md) | error 0 / warn 0 / info 0 | Round 2 pass、5/4/5/5/4 | ALB が2 AZのpublic subnetにまたがることをラベルで明示 |
| [Eval 2: Serverless Orders](iteration-4-remediation/eval-2-serverless-orders/with_skill/run-1/outputs/report.md) | error 0 / warn 0 / info 1 (`N-ASPECT`, 2.21:1) | pass、全5軸5、findings 0 | 比率を3.99:1から2.21:1へ改善。配線を大回りさせずinfoを記録 |
| [Eval 3: Flawed図の修正](iteration-4-remediation/eval-3-fix-flawed-drawio/with_skill/run-1/outputs/report.md) | error 0 / warn 0 / info 0 | Round 2 pass、4/5/5/5/5 | 各VPN線ラベルに2本のIPsecトンネルを明記 |

- いずれも最終 `.drawio` を再lintし、その同一ファイルを Desktop UI からPNGへexportした。draw.io Desktop CLI render は exit 134 で失敗する環境のためUI exportを用いた。納品 PNG と批評用 PNG のハッシュ一致、画像確認、独立 critic の結果は各レポートに記録した。
- ソース修正後の `quick_validate.py` は `Skill is valid!`、pytestは22件すべて通過した。
