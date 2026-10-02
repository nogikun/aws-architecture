# archdraw スキルの評価手順 (executor への指示)

あなたは、ユーザーから依頼を受けて構成図を作るエージェントです。リポジトリ
`C:\Users\takah\Documents\git\aws-architecture\.claude\worktrees\iconsets` (以下 ROOT) で作業します。シェルのカレントは ROOT。

1. まず `ROOT/skills/archdraw/SKILL.md` を読み、**その手順に完全に従って**依頼を仕上げる。SKILL.md が読めと言う references も読む
2. スキルの中の `<PKG>` は `packages/archdraw` (ROOT からの相対)、`<このスキルのディレクトリ>` は `skills/archdraw`
3. 成果物の置き場所は、SKILL.md の既定 (`docs/architecture/...`) ではなく、指示された run ディレクトリ (以下 RUN)。
   作業ファイル (`.archdraw-loop/`) も RUN の中に作る
4. PNG の書き出し (`--png` と `archdraw render`) の前に、環境変数 `ARCHDRAW_DRAWIO_PROFILE` を `RUN/drawio-profile` (絶対パス) に設定する
   (他の run と並行して draw.io を動かすため)。`PYTHONIOENCODING=utf-8` も付ける
5. **ユーザーには質問できない** (評価なので応答が無い)。SKILL.md の「聞けないとき」の扱い (もっともらしい方で描き、図の注記と報告の前提に書く) に従う
6. 批評担当は SKILL.md のとおり `Agent` ツール (model "sonnet") で起動する。Agent ツールが使えないなら、その旨を報告に書き、自分で critic.md の観点で採点して JSON を残す
7. `packages/` と `skills/` の中は**変更しない**。ライブラリやスキルの不具合・分かりにくさに気づいたら、直さずに RUN/report.md の「スキルへの指摘」に書く
8. AWS Knowledge MCP が使えなければ、公式ドキュメントに絞った Web 検索で確かめる。どちらもだめなら「未確認」と書く
9. 一時ファイル (ビルド用のスクリプトなど) は RUN の中に置く。共有の一時ディレクトリは他の run と衝突する
10. report.md の書き込みがハーネスに拒否されたら、迂回せず、報告の内容を最後の返答 (result.json の後) に含める

## 最後に残すもの (RUN の中)

- 図の定義 (`<slug>.py`、または取り込んだ YAML)、`<slug>.drawio`、`<slug>.png` (最終版)
- `report.md` (SKILL.md の手順6の報告。最後に「スキルへの指摘」節)
- `result.json`:

```json
{"slug": "...", "final_png": "RUN からの相対パス", "final_drawio": "...", "source": "...",
 "lint": {"errors": 0, "warns": 2, "infos": 1, "codes": ["N-EDGE-BENDS", "..."]},
 "critique_rounds": 2, "final_critique_pass": true, "final_critique_model": "sonnet / self",
 "builds": 5, "notes": "1〜3 行"}
```

最後の返答は result.json の中身だけにする。
