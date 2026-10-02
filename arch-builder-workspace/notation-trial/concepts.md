# archdraw — 図の考え方 (全表記で共通)

archdraw は、図の定義 (要素・枠・線) から、自動で配置と線の経路を決めて、編集できる draw.io の図 (.drawio) を作る。
**座標は書かない。** 読みやすさは「どの枠に入れるか」「並び順」「並べ方 (row / column)」で決まる。

## 要素 (node)

アイコン + ラベル。アイコンの名前は次のどちらか。

- **AWS 公式アイコン**: 公式名か通称 (`Amazon CloudFront`, `ALB`, `NAT Gateway`, `S3`, `AWS Fargate`, `Amazon Aurora`, `Users` …)。
  分からなければ `uv run --project packages/archdraw archdraw icons search <語>` で探す
- **取り込んだセット**: `prefix:name`。`lucide:users` (汎用) / `devicon:go` `devicon:react` `devicon:postgresql` (言語・ミドルウェア) /
  `logos:*` (ロゴ) / `cloudflare:workers` `cloudflare:kv` `cloudflare:r2` `cloudflare:waf` (Cloudflare 製品) / `simple-icons:*` / `svgl:*`。
  同じく `icons search` で探せる

ラベルは必須。1 行 28 字まで、改行で 2 行に分けられる。

## 枠 (group)

| 種類 | 見た目 | 置いてよい親 |
| --- | --- | --- |
| `generic` | 灰・破線の枠 | どこでも。論理的なまとまり (「アプリ」「データ」「管理系」)。**中身が無くラベル付きで線につながる generic は、外部システムを表す小さな実線の箱になる** |
| `layout` | **描かない** | どこでも。並べ方を整えるためだけの箱 |
| `aws-cloud` | AWS Cloud | キャンバス直下 |
| `account` | AWS Account | キャンバス直下 / aws-cloud |
| `region` | Region (ラベルにリージョン名) | aws-cloud / account |
| `vpc` | VPC | region |
| `az` | Availability Zone | vpc |
| `public-subnet` / `private-subnet` | Subnet | az / vpc |
| `security-group` / `auto-scaling` | | subnet / az / vpc |
| `corporate-dc` | オンプレ | キャンバス直下 |

並べ方: `row` (横、既定) / `column` (縦) / `grid` (cols 列)。子は書いた順に並ぶ。

## 線 (edge)

- ラベルは 12〜16 字まで (プロトコルなど)。ラベル無しも可
- `dashed` (破線): 非同期・レプリケーション・関連 (WAF の関連付け、IAM ロールなど、通信ではないもの)
- 矢印: 既定は終点のみ。`both` / `none` も可
- 接続口は自動で決まる。どうしても意図と違うときだけ `exit` / `entry` (top/right/bottom/left) で固定する

## 注記 (notes)

依頼に無く自分で置いた前提・不明点は、図の注記に 1 つ 1 行で書く。図の下に「※」付きで並ぶ。

## 配置の決まり (読みやすさ)

- 流れ: **VPC の中は上 → 下、外は左 → 右**。入口を左、出口を右に置く。線でつながる相手どうしを隣に置く
- AWS の入れ子: AWS Cloud ⊃ Region ⊃ VPC ⊃ AZ ⊃ Subnet ⊃ リソース
- VPC の型: VPC を `column` にし、[入口 (ALB など), AZ を横に並べた layout 箱] の順。各 AZ は `column` で public → app → data
- Internet Gateway / VPN Gateway は **VPC の直下に置くだけで VPC の枠線上に乗る** (IGW は上辺)
- NAT Gateway は各 AZ の public subnet、データベースは private subnet
- グローバルサービス (CloudFront, Route 53, IAM, WAF) は AWS Cloud の中・Region の外。リージョンサービス (S3, DynamoDB, SQS, SNS, Lambda, API Gateway, Cognito) は Region の中・VPC の外
- 利用者・外部システムはキャンバス直下 (AWS Cloud の外) に置く
- 図は横長にする (縦長は error)。要素が多いときは、外の要素を `column` の layout 箱に縦に積む
- 全てのアイコンを 1 本以上の線でつなぐ (つながっていないアイコンは error)
- 同じ構成の繰り返し (AZ ごと、サーバー A/B/C) は、同じ順・同じ形にそろえる

## コマンド (リポジトリのルートで実行)

```bash
uv run --project packages/archdraw archdraw build <定義ファイル> -o <out>.drawio --png <out>.png   # 生成 + 検査 + PNG
uv run --project packages/archdraw archdraw lint <out>.drawio                                     # 検査だけ
uv run --project packages/archdraw archdraw icons search <語>                                     # アイコンを探す
```

build は検査 (lint) の結果を出す。**error が 1 件でもあると .drawio を書かない。** 出力の `→` の行が直し方。
warn は読みにくさの指摘で、直すのが基本。
