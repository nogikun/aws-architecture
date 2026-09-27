# arch-builder スキル検査 — 手順書 (iteration-4)

あなたの仕事は、`arch-builder` スキルの**第 4 回検査**を行い、結果を残すこと。
スキル本体 (`skills/arch-builder/`) は**一切変更しない**。見つけた問題は報告に書くだけにする。

- リポジトリ: `/Users/takahashikazuaki/Documents/git/aws-architecture`
- スキル: `skills/arch-builder/` (まず `SKILL.md` を読む。評価の決まりは `evals/README.md`、課題は `evals/evals.json`)
- 出力先: `skills/arch-builder-workspace/iteration-4/`
- 前回までの結果: `skills/arch-builder-workspace/iteration-1〜3/`、前回のレビュー: `review-2026-09-27.md`

## 今回確かめたいこと

iteration-3 のあとに入れた変更が効いているかを見る。

1. **流れと接続口** — 各アイコンの入口と出口が向かい合っているか (VPC の中は上から入って下へ、外は左から入って右へ)。
   本流の線が横から入ったり、入口と出口が同じ面にあったりしないか
2. **ヘッダー / ボディ / フッター** — IGW が VPC の上辺の線の上、ALB が VPC の上部 (ヘッダー)、AZ が横並び (ボディ)、
   外へ出す口 (VPN Gateway など) が VPC の下辺の線の上にあるか。IGW から出る線が枠線をなぞっていないか
3. **分岐と対称性** — ALB から各 AZ への線が、同じ出口から出た幹が AZ の間を下りて T 字に分かれているか。
   AZ ごとに同じ役割の相手への線 (ALB → 各 AZ の ECS、各 AZ の ECS → DB) が、同じ口・同じ曲がり方・同じ高さで引かれているか
4. **線の読み違い** — 無関係なアイコンのすぐ脇を通る線、流れと逆向きに入る矢印、重なった線が無いか
5. **縦横比** — 縦長 (1:1 未満) の図が無いか (`N-ASPECT-PORTRAIT` は error)。16:9 は目安なので、1.2:1 程度は合格。
   縦横比を合わせるために線が大回りしていないか
6. **前提の明示** — 依頼に無い前提 (社内システムの入り方など) を、図の `notes` と報告に書いているか
7. **最新 AWS 情報** — 不確かな点や、指定された構成の選択 (VPC を使わない等) の影響を、AWS Knowledge MCP か公式ドキュメントで確かめ、
   確認日と URL を報告に残しているか
8. **完成条件** — 最終版の PNG に対する批評が記録され、pass しているか (直した後に再批評しているか)
9. **接続口の定義** (spec.md「流れと接続口」) — lint の `N-PORT-FACE` / `N-PORT-SLOT` が 0 件か。PNG でも確かめる:
   上流・真横の相手へは 90° 回した面でつながり、3 回以上曲がる実線が無いか (`N-EDGE-BENDS`)。
   ラベルの違う線が同じ面から出るとき、面を 2n+1 等分した偶数番目の位置 (2 本なら 30% / 70%) から別々に出ているか。
   内容の違う線どうしが重なっていないか (`N-EDGE-OVERLAP`)。中 → 外の線 (ECS → NAT、NAT → IGW) が点対称の面を使っているか
10. **枠の大きさとつながり** — 中身に対して広すぎる枠が無いか (`N-SPARSE`。2 倍以上は error)。すべてのノードが 1 本以上の線で何かと
   つながっているか (`N-NODE-UNCONNECTED` は error)。線のラベルの上を別の線が通っていないか (`N-EDGE-LABEL-CROSSED`)、枠線に沿う線が無いか (`N-EDGE-ON-FRAME`)

## 0. 準備 (最初に 1 回)

```bash
cd /Users/takahashikazuaki/Documents/git/aws-architecture
git rev-parse --short HEAD                                   # run.json に書く
uv run --project skills/arch-builder/tools arch doctor       # OK と Asset Package の日付を確認
uv run --project skills/arch-builder/tools pytest skills/arch-builder/tools/tests -q   # 21 件すべて通ること (40 秒ほど)
```

- 素の `python3` は使わない。この環境では Nix の shim が自分自身を起動し続けて止まる。Python は必ず `uv run` 経由で動かす
- doctor か pytest が失敗したら、検査を止めて、その出力を報告に書いて終える
- AWS Knowledge MCP (`aws-knowledge-mcp-server`、リポジトリ直下の `.mcp.json`) が使えるかどうかを控えておく。使えなくても検査は進める
- draw.io Desktop: `/Applications/draw.io.app/Contents/MacOS/draw.io`

## 1. 実行 (3 課題 × 2 条件 × 3 回 = 18 run)

課題は `skills/arch-builder/evals/evals.json` の 3 つ。各課題を**スキルあり**と**スキルなし**で、それぞれ **3 回**ずつ実行する。

### ディレクトリ

```text
iteration-4/
  eval-1-fargate-aurora-web/
    eval_metadata.json            ← evals.json の該当課題 (id, prompt, assertions) をそのまま写す
    with_skill/run-1/outputs/  run-2/  run-3/
    without_skill/run-1/outputs/  run-2/  run-3/
  eval-2-serverless-orders/ ...
  eval-3-fix-flawed-drawio/ ...
```

課題 3 は、各 run の `outputs/` に `skills/arch-builder/evals/files/flawed.drawio` をコピーしてから始める。

### 実行のしかた

**各 run は、互いの結果もスキルの中身も知らない、独立した実行者に任せる** (サブエージェント、別セッション、別プロセスなど)。
あなた自身が作図してはいけない。あなたの役目は、実行者に渡す・結果を受け取る・採点することだけ。

- **スキルなしの実行者には、`skills/arch-builder/` と `.claude/skills/arch-builder` を読ませない**。
  同じ実行者を使い回すなら、スキルなしの run を先に全部終えてから、スキルありに進む
- 実行者はユーザーに質問できない前提で進める (依頼文と既定値で決める)

スキルありの実行者に渡すプロンプト (`<...>` を埋める):

```text
次の依頼を、スキル /Users/takahashikazuaki/Documents/git/aws-architecture/skills/arch-builder を使って実行してください。
まず SKILL.md を読み、その手順に従ってください。

依頼: <evals.json の prompt。課題 3 は flawed.drawio を outputs/ のパスに読み替える>
入力ファイル: <課題 3 のみ: <run>/outputs/flawed.drawio。他は なし>
出力先: <run>/outputs/
残すもの: <slug>.arch.yaml、<slug>.drawio、<slug>.png (課題 3 は fixed.*)、ユーザー向けの最終報告 report.md、
          批評ループの作業ファイル (.arch-loop/ を outputs/ の下に)

注意:
- これは自動テストです。ユーザーはいません。質問せず、依頼文と既定値で決めてください
- 素の python3 は使わず、uv run だけを使ってください
- 批評は SKILL.md のとおり、実装と別系列のモデルで行ってください。使えない場合は、その旨を report.md に書いてください
- report.md の書き込みが拒否されたら回避せず、最終返答に本文を含めてください
```

スキルなしの実行者に渡すプロンプト:

```text
次の依頼を実行してください。

依頼: <evals.json の prompt>
入力ファイル: <課題 3 のみ: <run>/outputs/flawed.drawio。他は なし>
出力先: <run>/outputs/
残すもの: 編集できる .drawio (課題 3 は fixed.drawio)、確認用の PNG、ユーザー向けの最終報告 report.md

注意:
- これは自動テストです。ユーザーはいません。質問せず、依頼文と妥当な既定で決めてください
- /Users/takahashikazuaki/Documents/git/aws-architecture/skills/arch-builder と .claude/skills/arch-builder は読まないでください
- draw.io Desktop は /Applications/draw.io.app/Contents/MacOS/draw.io にあります (-x -f png -o out.png in.drawio で書き出せます)
- 素の python3 は環境依存で止まります。Python が要るなら uv run --no-project python を使ってください
- report.md の書き込みが拒否されたら回避せず、最終返答に本文を含めてください
```

### run ごとに残すもの

- `report.md` が書けずに本文だけ返ってきたら、あなたがその本文を `outputs/report.md` に保存する (中身は変えない)
- `timing.json`: `{"total_tokens": <数>, "duration_ms": <数>, "total_duration_seconds": <数>}` (取れない値は null)
- `run.json`:

  ```json
  {"executor_model": "<実行者のモデル>", "critic_model": "<批評のモデル。スキルなしは null>",
   "grader_model": "<あなたのモデル>", "skill_commit": "<git rev-parse の値>",
   "icon_package": "<doctor が出した日付>", "aws_knowledge_mcp": true/false}
  ```

## 2. 採点 (3 種類を混ぜない)

`evals.json` のアサーションには `type` がある。種類ごとに採点の仕方を分ける。

### machine — スクリプトで採点する

```bash
uv run --project skills/arch-builder/tools python skills/arch-builder/evals/grade_machine.py skills/arch-builder-workspace/iteration-4
```

各 run に `machine.json` ができる。スキルなしの図は draw.io 標準の aws4 図形で描かれることが多く、lint は公式 ZIP
アイコン以外を `N-UNMANAGED` にする。**machine の比較はスキルありに有利になる**ことを、集計に注記する。

### design — 成果物を読んで採点する

`.arch.yaml` (スキルなしは `.drawio`)、`report.md`、`.arch-loop/` (最終版の `critique.json`) を読んで判定する。
「最終版の PNG に対する批評が pass」は、`.arch-loop/` の最後の critique が**納品した PNG と同じ図**に対するものかまで確かめる
(最後の批評の後に図を直していたら不合格)。

### legibility — PNG だけで採点する

**PNG 以外を見ない採点者**に任せる (yaml・報告・批評を渡さない)。あなたが採点するなら、PNG を開く前に他の資料を読まない。
次を 1 件ずつ具体的に書く: 線が無関係なアイコンのすぐ脇を通る / 矢印が逆向き / 線の重なり / ラベルと線の重なり /
AZ ごとの対になる線のつなぎ方の不一致 / 枠線をなぞる線 / 入口と出口が向かい合っていないアイコン / 幹を共有しない分岐。

### grading.json

各 run に、次の形で書く (フィールド名はこのとおり。集計スクリプトが読む):

```json
{"expectations": [{"text": "<アサーション>", "type": "machine|design|legibility", "passed": true, "evidence": "<根拠>"}],
 "summary": {"passed": 0, "failed": 0, "total": 0, "pass_rate": 0.0}}
```

アサーションの並び順は `eval_metadata.json` と同じにする (前回、並び順がずれて採点を付け直した)。

## 3. 集計と比較画面

skill-creator のスクリプトを使う (パスはこの環境のもの。無ければ `benchmark.json` を手で作る):

```bash
SC="/Users/takahashikazuaki/.claude/skills/synced/0905d599-d8ad-4112-b9b9-b37f9687085c_28e68a8f-a5f9-4c0f-a461-d3135eedb52f/skill-creator"
W=/Users/takahashikazuaki/Documents/git/aws-architecture/skills/arch-builder-workspace
cd "$SC"
uv run --no-project --python 3.13 python -m scripts.aggregate_benchmark $W/iteration-4 --skill-name arch-builder
uv run --no-project --python 3.13 python eval-viewer/generate_review.py $W/iteration-4 --skill-name arch-builder \
  --benchmark $W/iteration-4/benchmark.json --previous-workspace $W/iteration-3 --static $W/iteration-4/review.html
```

`benchmark.json` の `runs_per_configuration` が 3 になっているか確かめる。

## 4. 報告 — `skills/arch-builder-workspace/review-<YYYY-MM-DD>.md`

`review-2026-09-27.md` と同じ形で書く。必ず入れるもの:

1. **評価表** (設計 / 図の品質 / 評価基盤 を 5 段階で。1 行コメント付き)
2. **数値**: 条件ごとの合格率を type 別 (machine / design / legibility) に、3 回のばらつき (平均 ± 標準偏差) 付きで。
   スキルなしとの差は design と legibility で述べる
3. **「今回確かめたいこと」1〜10 の結果**: それぞれ 合格 / 一部 / 不合格 と、根拠 (ファイルへのリンク)
4. **主な所見**: 問題ごとに、再現する run、何が起きたか、改善案 (スキルのどこを直すか)。スキルは直さない
5. **前回からの変化**: iteration-3 と比べて良くなった点・悪くなった点
6. 実行・批評・採点に使ったモデル、AWS Knowledge MCP を使えたか、途中で失敗・中断した run とその理由

事実と推測を分けて書く。確かめていないことを確かめたように書かない。
