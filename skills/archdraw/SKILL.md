---
name: archdraw
description: システム構成図・アーキテクチャ図 (AWS、Cloudflare、一般の Web システム、SaaS、技術スタック、オンプレ連携) を、編集できる draw.io ファイル (.drawio) として設計・作図する。図は archdraw ライブラリの Python で書き、配置と線の経路は自動、作図規約と構成の定石 (AWS なら Cloud ⊃ Region ⊃ VPC ⊃ AZ ⊃ Subnet、DB は private、NAT の置き場所など) をスクリプトで検査し、PNG を別モデルに批評させる差し戻しループで仕上げる。AWS 公式アイコンのほか、Lucide / Devicon / Simple Icons / SVGL / Cloudflare 製品アイコンを使える。「構成図を作って」「アーキテクチャ図」「インフラ構成図」「システム構成図」「この構成を図にして」「〜を設計して図にして」「drawio で」「React と Go と PostgreSQL の構成を図に」と言われたら、形式が指定されていなくてもこのスキルを使う。既存の .drawio の構成図の手直し・規約チェック・レビュー (「この構成図おかしくない?」「AWS のお作法に沿ってる?」) や、アイコンが足りない・取り込みたいという相談にも使う。フローチャート、シーケンス図、ER 図、組織図など構成図でないものは drawio スキルに回す。
---

# archdraw — システム構成図

**図の定義は Python で書く** (`<slug>.py`)。.drawio はそこから生成するもの。座標は書かない。
配置と線の経路は archdraw が決め、検査 (lint) も同じ定義で行う。何度作り直しても同じ図が出る。

archdraw はリポジトリの `packages/archdraw` にある Python パッケージ。**呼び出しは常にこの形にする**
(`<PKG>` は `<このスキルのディレクトリ>/../../packages/archdraw`。空白を含むことがあるので引用符で囲む):

```bash
uv run --project "<PKG>" archdraw <サブコマンド> ...
```

素の `python3` は使わない。アイコンの実データは `~/.archdraw` (`$ARCHDRAW_HOME`) にあり、パッケージには入っていない。

## 入口

| 言われたこと | 行き先 |
| --- | --- |
| 「〜の構成図を作って」「こういう構成を設計して」 | 手順0から |
| 既存の `.drawio` を渡されて「直して」「規約に沿ってるか見て」 | 手順0 → `archdraw import` → 手順4から |
| 「アイコンが出ない」「アイコンを取り込みたい」 | 手順0だけ |
| 「この部分だけ変えて」(直前に作った図) | 定義の .py を直す → 手順3から |

## 0. アイコンを確かめる (毎回、最初に1回)

```bash
uv run --project "<PKG>" archdraw doctor
```

使うアイコンのセットが取り込まれているかを見る。足りなければ取り込む (`archdraw icons fetch <ノズル> ...`):

| 使うもの | 取り込み |
| --- | --- |
| AWS 公式アイコン | ユーザーに ZIP を頼む: 「AWS 公式アイコン (Asset Package の ZIP) が必要です。https://aws.amazon.com/architecture/icons/ からダウンロードして、ZIP のパスを教えてください」 → `fetch aws <ZIP>`。**AWS の図で AWS が未取り込みなら作図に進まない** |
| 汎用 (利用者・DB・サーバー)、言語・ミドルウェア、ロゴ | `fetch iconify lucide devicon logos simple-icons` (ネットから取る。取り込む前に1行で了承を得る) |
| Cloudflare 製品 | `fetch cloudflare` (公式ドキュメントのリポジトリから。取れなければ手順が表示される) |
| モダンな SaaS・AI のロゴ | `fetch svgl` |
| 手元の SVG (社内アイコンなど) | `fetch svg <フォルダか ZIP> --prefix <名前>` |

AWS の Asset Package の日付と、使ったセットのライセンスは doctor に出る。報告に書く。
draw.io Desktop が無ければ PNG を書き出せない。そのときは .drawio だけを納品し、そう報告する。

## 1. 要件を固める (確認は1回だけ)

依頼文から次の表を自分で埋める。**埋まらないものだけ** `AskUserQuestion` で**1回にまとめて**聞く (最大4問)。
選択肢は依頼から作った具体的な案にして、推奨を先頭に置く。

| 項目 | 例 | 聞かずに決めてよい既定 |
| --- | --- | --- |
| 何の図か・誰が見るか | 設計レビュー用 / 提案資料用 | 設計レビュー |
| どこまで描くか | サブネットまで / サービス同士の関係だけ | 依頼の粒度に合わせる |
| 必須の要素・制約 | 「ECS on Fargate」「オンプレと VPN」 | 依頼にあるものだけ |
| AWS なら: 環境と可用性、リージョン | 本番 2 AZ / ap-northeast-1 | 本番 = 2 AZ、ap-northeast-1 |
| 利用者の入り方 | インターネット公開 / 社内限定 | **決めない** (下を参照) |
| 仕上げの厳しさ | 標準 / 厳しめ | 標準 |

**依頼に無い前提を黙って確定しない。** 特に利用者の入り方は、セキュリティの形がまるごと変わる。
聞けないときは、もっともらしい方で描いたうえで、**図の注記 (`d.note`) と報告の「前提」に書く**。注記は前提ごとに1行。
設計の判断 (なぜ その構成か) は図ではなく報告に書く。図には構成と流れと前提だけを載せる。

AWS の図なら、不確かなところ (新しいサービス、リージョンでの提供、構成の可否) だけ公式の情報源で確かめる。
やり方と記録の仕方は [references/aws.md](references/aws.md) の最後。**確認した日付と出典 URL を報告に残す。**

## 2. 図を Python で書く

書式は [references/notation.md](references/notation.md)。**書く前に読む。** AWS の図なら [references/aws.md](references/aws.md) も読む。
並べ方の決まりは [references/layout.md](references/layout.md)。出力先は、指定が無ければ `docs/architecture/<slug>/<slug>.py`。

いちばん大事な決まり:

- **並べ方は `layout="auto"` に任せ、何がどこへつながるかを正しい向きで書く。** 枠は意味のまとまりにだけ使う
- **AWS の VPC の中だけは決まった型** (column で [IGW, ALB, AZ を横に並べた row]、各 AZ は column で public → app → data)
- **線を減らす。** 監視・ログなど全体にかかる関係は、囲む枠から 1 本の破線に
- **線種の決まり**: 同期の通信 = 実線、非同期 (キュー・イベント) とレプリケーション = 破線、
  関連 (WAF の関連付け、IAM ロール、オーソライザー、監視) = 破線 + `arrow="none"`。表は [references/layout.md](references/layout.md)
- 同じ構成の繰り返し (AZ、サーバー A/B/C) は for 文で書き、同じ形にそろえる
- 依頼に無い前提・不明点は `d.note(...)` に1つ1行で
- アイコン名が分からなければ `archdraw icons search <語>`

## 3. 生成する

```bash
uv run --project "<PKG>" archdraw build <slug>.py -o <slug>.drawio --png <slug>.png
```

build は定義を実行して図を作り、検査 (lint) し、保存した .drawio を読み直して同じ結果になるかを確かめる。
**error があれば .drawio を書かない** (既存の出力も置き換えない)。

## 4. 決定的検査 (lint) — error を 0 件にする

```bash
uv run --project "<PKG>" archdraw lint <slug>.drawio                      # 納品する .drawio そのものを検査する
uv run --project "<PKG>" archdraw lint <slug>.drawio --strict-geometry    # 交差・接触・重なり・検査不能な線があれば失敗
```

- `error` は**全部直す**。1件でも残っていたら、批評にも納品にも進まない
- `warn` は直すのが基本。直す順番は [references/lint.md](references/lint.md) の最後 (線を減らす → つながる相手を隣に → 枠の分け方 → exit/entry)。
  意図があって残すなら、その理由を報告に書く
- ルールの意味は [references/lint.md](references/lint.md) (core) と [references/aws.md](references/aws.md) (AWS)
- **納品する .drawio 自体を、最後の編集の後に lint する。** build 時の結果を流用しない

## 5. PNG を見て、批評に出す (差し戻しループ)

**まず自分で PNG を Read して見る。** lint が拾えない破綻がある: 線が別の要素につながって見える、流れの逆転、
繰り返しの形の不一致、関連 (破線) と通信 (実線) の混同、詰まりすぎ・空きすぎ。自分で分かるものは先に直す。

そのうえで、**実装と別系列のモデル**に批評させる。既定は Sonnet。同じモデルに採点させると、自分の癖ごと見落とすため。
批評担当はラウンドごとに新しく起動し、返事を待つ (`run_in_background: false`)。前回の経緯は `accepted` で渡す。

```text
Agent: subagent_type "general-purpose", model "sonnet", run_in_background false
prompt:
  よく考えてから採点してほしい。まず <このスキルのディレクトリ>/agents/critic.md を読み、その指示に完全に従うこと。
  - png: <.archdraw-loop/<slug>/round-N/<slug>.png>   ← 必ず Read で画像を見る
  - source: <slug>.py のパス
  - requirements: <手順1で固めた要件を箇条書きで>
  - strictness: <標準 / 厳しめ>
  - lint: <archdraw lint の出力をそのまま>
  - accepted: <.archdraw-loop/<slug>/accepted.md の中身。無ければ「なし」>
  返答は指定の JSON のみ。
```

- 返答は `.archdraw-loop/<slug>/round-N/critique.json` に加工せずに保存する
- 直すのは findings の分だけ。直したら build → lint → render を回す
- 確定した判断は `.archdraw-loop/<slug>/accepted.md` に1行ずつ足す (次のラウンドで逆向きの指摘を防ぐ)
- `user_conflict` が空でなければ、直さずにユーザーに判断を仰ぐ

**終了条件**: lint の error が 0 件、かつ**納品する PNG そのもの**に対する批評が `pass`。

- 批評のあとに直したら、その図はまだ誰にも見られていない。**直した最終版は必ずもう一度批評に通す**
- 「厳しめ」なら `should` も 0 件で pass。残ったものは直さない理由を添えて報告の「未解決」に並べる
- **直すのは 2 ラウンドまで。** 批評 → 直す → 批評 → 直す、のあとに、**直さない前提の確認の批評を 1 回だけ**回し、
  その結果をそのまま報告する (確認の批評のあとは直さない)。pass しなくても、現物と残りの指摘を持ってユーザーに返す

## 6. 納品と報告

納品物は `<slug>.py` (定義)、`<slug>.drawio` (編集用)、`<slug>.png` (確認用)。`.archdraw-loop/` は作業用なのでパスだけ書く。
報告には次を短く書く:

- 3つの成果物のパス
- 構成の要点と設計判断 (なぜその構成か) を3〜6行
- **前提** (図の注記と同じもの)
- AWS なら **確認した AWS 情報** (確認日と出典 URL。確かめなかったなら「なし」) と Asset Package の日付
- 使ったアイコンセットとライセンス (Cloudflare 製品アイコンは CC BY 4.0。資料に載せるなら出典を書く)
- lint の結果 (error 0 / 残した warn とその理由)
- 批評のラウンド数、**最終版に対する批評の結果**、**未解決**の指摘
- draw.io で手直ししたときの戻し方: 「保存したら `archdraw import <slug>.drawio -o <slug>.yaml` で定義に戻す (以後は YAML が正本)」

## draw.io で手直しされた図を受け取ったとき

```bash
uv run --project "<PKG>" archdraw import <slug>.drawio -o <slug>.yaml
```

- import は draw.io 上の座標を `pos` / `size` として YAML に書き戻す。以後は YAML が正本 (`archdraw build <slug>.yaml`)。
  正本を上書きする前に、git の管理下にあるか確かめるか、コピーを取る
- ライブラリのアイコンは画像の中身から名前を逆引きする。逆引きできない画像や図形は `N-UNMANAGED` (error)
- 見た目の位置と所属がずれている (枠の上に載っているだけ) と `N-VISUAL-PARENT`。draw.io で枠の中へ入れ直す
- YAML の正本は `archdraw edit` でも直せる (id の整合をスクリプトが保証する。`archdraw edit -h`)

## 同梱物

| パス | 中身 | 読むタイミング |
| --- | --- | --- |
| `references/notation.md` | Python の書き方・API・YAML | 図を書く前 |
| `references/layout.md` | 配置と線の決まり (流れ、並び順、線を減らす、枠、キャンバス) | 図を書く前・warn を直すとき |
| `references/aws.md` | AWS のグループ・置き場所・VPC の型・構成ルール・最新情報の確かめ方 | AWS の図のとき |
| `references/lint.md` | core の検査ルールと warn の直し方 | lint の結果を読むとき |
| `agents/critic.md` | 批評担当への指示 | 批評担当が読む |
| `<PKG>/examples/` | 見本 (`aws-3tier.py` など) | 最初に書くとき |
