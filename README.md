# AWS Architecture Skills

AWS構成図を、編集可能なdraw.ioファイルとして作成・検証するエージェントSkillを開発するリポジトリです。中心となるSkillは [`skills/arch-builder/`](skills/arch-builder/SKILL.md) です。

`arch-builder` は `arch.yaml` を正本にしてAWS構成図を生成し、AWS公式アイコン、構成ルールのlint、PNGでの目視・独立批評を通して仕上げます。draw.ioで直接編集した場合は、YAMLへ戻してから再生成・再検査します。

## 使い始める

CLIにはPython 3.13以上とuvが必要です。リポジトリの開発環境はNix flakeで用意しています。Nixを使う場合は `nix develop`、direnvを使う場合は `direnv allow` で環境に入れます。

```bash
# アイコン・draw.io環境を確認
uv run --project skills/arch-builder/tools arch doctor

# arch.yamlからdraw.ioを作成し、lintする
uv run --project skills/arch-builder/tools arch build path/to/architecture.arch.yaml -o architecture.drawio
uv run --project skills/arch-builder/tools arch lint architecture.drawio

# テスト
uv run --project skills/arch-builder/tools pytest skills/arch-builder/tools/tests -q
```

作図Skillの手順、入力仕様、AWS構成ルールは[arch-builderのSKILL.md](skills/arch-builder/SKILL.md)と`references/`を参照してください。

## ディレクトリ

```text
skills/
└── arch-builder/              # このリポジトリのSkill本体
    ├── SKILL.md
    ├── agents/                 # 図の独立批評用指示
    ├── evals/                  # 評価課題と採点コード
    ├── references/             # YAML仕様・AWS構成ルール
    ├── tools/                  # arch CLIとテスト
    └── vendor/                 # 取り込んだdraw.io関連Skill
arch-builder-workspace/         # 評価手順、レビュー、実行結果
└── png-comparison-iteration-4/ # with-skill / without-skill PNG比較
```

`skills/`直下には配布対象のSkillだけを置きます。評価作業用の資料と結果は、Skillと区別してリポジトリ直下の`arch-builder-workspace/`にまとめています。評価runの生成物は`.gitignore`対象です。

## 評価資料

- [iteration-4 PNG左右比較](arch-builder-workspace/png-comparison-iteration-4/compare.md) — 同じ課題・run番号でwith-skillとwithout-skillの最終PNGを比較できます。
- [iteration-4 全体レビュー](arch-builder-workspace/review-2026-09-27-iteration-4.md) — 評価方法、各assertionの集計、制約、修正後の検証結果。
- [評価手順](arch-builder-workspace/test.md)
- [評価資料の索引](arch-builder-workspace/README.md)

## iteration-4で観測した差

同じ3課題を各条件3回実行した評価では、設計assertionはwith-skillが高く、PNGの可読性assertionはwithout-skillが高い結果でした。

| 採点 | with-skill | without-skill | 観測 |
|---|---:|---:|---|
| 設計 | 95.2% (40/42) | 42.9% (18/42) | AWS構成、サービス配置、前提の記録でwith-skillが高い |
| PNG可読性 | 16.7% (2/12) | 50.0% (6/12) | 線ラベルや配線の混雑が残り、without-skillが高い |
| machine | 40.7% (11/27) | 3.7% (1/27) | without-skillに`.arch.yaml`と公式アイコンを求める判定が含まれ、比較はwith-skillに有利 |

各条件9 run、3課題の範囲での観測であり、広い用途への一般化はできません。machineの差は採点条件の影響を受けます。詳しい根拠と制約は[全体レビュー](arch-builder-workspace/review-2026-09-27-iteration-4.md)、画像の個別比較は[PNG比較ページ](arch-builder-workspace/png-comparison-iteration-4/compare.md)にまとめています。
