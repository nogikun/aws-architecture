# AWS の図を描くとき

AWS の構成図は、AWS 公式アイコン (Asset Package) とグループの規約 (AWS Cloud ⊃ Region ⊃ VPC ⊃ AZ ⊃ Subnet) で描く。
draw.io 標準の `mxgraph.aws4` は使わない (更新が遅れて古い意匠が混ざり、検査で公式かどうか判定できないため)。

## アイコン

- 公式名か通称で書く: `Amazon CloudFront` / `ALB` / `NAT Gateway` / `S3` / `AWS Fargate` / `Amazon Aurora` / `Users`。
  `aws:` を付けてもよい (`aws:Amazon RDS`)。分からなければ `archdraw icons search <語>`
- AWS アイコンが未取り込みなら、作図に入る前にユーザーに頼む:
  「AWS 公式アイコン (Asset Package の ZIP) が必要です。https://aws.amazon.com/architecture/icons/ から
  ダウンロードして、ZIP のパスを教えてください」 → `archdraw icons fetch aws <ZIP>`
- `archdraw doctor` が Asset Package の日付を出す。報告に書く。四半期ごとに更新されるので、古い注意が出たら1行伝える
- AWS 以外の要素 (利用者の端末、SaaS、OSS) が混ざるなら、取り込んだセット (`lucide:` / `devicon:` / `logos:` など) を使ってよい

## グループの種類

| 種類 | 置いてよい親 |
| --- | --- |
| `aws-cloud` | キャンバス直下 |
| `account` | キャンバス直下 / aws-cloud |
| `region` | aws-cloud / account。**ラベルにリージョン名** (`ap-northeast-1 (東京)`) |
| `vpc` | region。**中の流れは上 → 下** (ヘッダー → ボディ → フッター) |
| `az` | vpc。見出しは中央 |
| `public-subnet` / `private-subnet` | az / vpc (AZ を描いたら必ず AZ の中) |
| `security-group` / `auto-scaling` / `ec2-contents` / `spot-fleet` | subnet / az / vpc |
| `corporate-dc` / `server-contents` | キャンバス直下 (オンプレ側) |

## 置き場所

| 置くもの | 置き場所 |
| --- | --- |
| 利用者・外部システム・オンプレ | キャンバス直下 (AWS Cloud の外) |
| グローバルサービス (CloudFront, Route 53, IAM, Global Accelerator, WAF on CloudFront) | AWS Cloud の中、Region の外 |
| リージョンサービス (S3, DynamoDB, SQS, SNS, API Gateway, Cognito, CloudWatch, Lambda※, EventBridge) | Region の中、VPC の外 |
| VPC の境界 (Internet Gateway, ELB, VPC エンドポイント, VPN/Transit Gateway Attachment) | VPC の直下 |
| NAT Gateway | **各 AZ の public subnet** |
| アプリ (EC2, ECS/Fargate, EKS) | private subnet (踏み台だけは public 可) |
| データ (RDS, Aurora, ElastiCache, OpenSearch) | private subnet (データ用に subnet を分けるとなお良い) |

※ Lambda を VPC に接続する構成なら private subnet に置く。

### ゲートウェイ類は境界の上

| もの | 置き場所 | 書き方 |
| --- | --- | --- |
| Internet Gateway | VPC の**上辺の線の上** | VPC の直下に置くだけで乗る |
| VPN Gateway / Transit Gateway Attachment | VPC の**下辺 (フッター) の線の上** | VPC の直下に置くだけで乗る |
| Gateway 型 VPC エンドポイント (S3 / DynamoDB) | **既定: アイコンを置かず、VPC の枠から S3 へ 1 本の線** (ラベル `Gateway Endpoint`)。エンドポイント自体を強調したいときだけ VPC の**サービス側の辺の上** | `vpc.to(s3, "Gateway Endpoint")` / `Endpoints` アイコン + `border="right"` |
| Interface 型 VPC エンドポイント | private subnet の中 | subnet の子 |
| Transit Gateway 本体 | VPC の外、Region の中 | region の子 |
| Customer Gateway | オンプレ側 (`corporate-dc` の中) | |

## VPC の型 (Web ページのヘッダー / ボディ / フッター)

| 部分 | 置くもの |
| --- | --- |
| ヘッダーの上 (VPC 上辺の線) | Internet Gateway |
| ヘッダー (VPC の上部) | ALB など AZ をまたぐ入口。VPC を column にして先頭に置く |
| ボディ | AZ を横に並べた layout 箱。各 AZ は column で public → app → data。**各 AZ の subnet は同じ順・同じ数** |
| フッター (VPC 下辺の線) | 外へ出す口 (VPN Gateway, Transit Gateway Attachment) |

- region は row にして、入口 (CloudFront など) を左、VPC を中央、リージョンサービスを右に置く。
  入口のグローバルサービスは、region の上の段 (aws-cloud を column にして先頭の layout 箱) に置くと、IGW へ素直に下りる
- ALB からの線は AZ の間を下りて T 字に分かれる (自動)
- 外向き通信 (ECS → NAT → IGW) は中 → 外の逆方向の線。自動で点対称の面を使う。AZ ごとの線は同じ形になる

## 読み違いを防ぐ描き方 (過去のレビューで指摘されたもの)

- **WAF は CloudFront / ALB のラベルに書き込まず、独立したアイコンにして、関連付けを破線で示す**
  (`waf.to(cf, "Web ACL", dashed=True, arrow="none")`)。通信線と区別できないと、関係を読み手が推測することになる
- **複数のアプリから同じ DB へ行くなら、どこへ書くかを示す**。各 AZ のアプリの線を Writer に集め、
  **Writer のラベルに「(クラスターエンドポイント)」と書く** (線のラベルにすると、中点が AZ の隙間に来て枠線に乗る)。
  Writer → Reader はレプリケーションの破線。ラベルは付けないか短く (AZ の隙間に来る)
- **SQS を通る非同期の区間は破線** (積む側も、起動される側も)。同期の API 呼び出しと線種で区別する
- **外向き通信 (アプリ → NAT → IGW) は線で描く**。AZ ごとに外側の面を通るので、ALB からの線と混ざらない。
  **exit / entry で面を固定しない** (アプリ → NAT は外側の面、NAT → IGW は NAT の上の面から、が自動で選ばれる。
  NAT → IGW を横の面に固定すると、アプリ → NAT と一直線に並んで 1 本の線に見える)。
  ラベルは 1 本目にだけ「外向き」などと付ける (全部に付けると重なる)
- **複数 AZ のアプリから S3 などリージョンサービスへ行く線は、VPC の枠から 1 本にまとめる** (`vpc.to(s3, "Gateway Endpoint", ...)`)。
  AZ ごとに引くと ALB の幹と重なる
- CloudFront から S3 (静的) と IGW / ALB (動的) の両方へ行く定番の形: CloudFront を aws-cloud の上の段 (row の箱) に置き、
  **WAF はその右**、**S3 は Region の中で VPC の右**。CloudFront → S3 は `exit="bottom", entry="top"` にすると VPC の上を横切らない
- 利用者を AWS Cloud の上に置くなら、利用者 → IGW は `exit="bottom"` などで向きを固定する (最上位の layout は row / auto だけ。
  column にはできない)
- IAM ロールなどの論理的な関連 (破線) は、関連元の近くに置く。遠くの枠へ長い破線を引くと、実線を横切り、境界の外に見える
- 依頼で決まっていない前提 (インターネット公開か社内限定か、リージョン、AZ) は図の注記に書く

## 構成のルール (archdraw の AWS pack が検査する)

| コード | 重大度 | 何を見るか | 根拠 |
| --- | --- | --- | --- |
| `N-CATEGORY-ICON` | error | カテゴリアイコンをサービスとして使っている | アイコン規約。カテゴリはサービスを表さない |
| `N-GROUP-ICON` | error | グループアイコンを単体の要素として置いている | グループは枠で表す |
| `N-NESTING` | error | 入れ子の順序が誤っている | VPC はリージョンに、subnet は AZ に属する |
| `N-SUBNET-OUTSIDE-AZ` | warn | AZ を描いた VPC で、AZ の外に subnet がある | subnet は必ず1つの AZ に属する |
| `N-NODE-IN-AZ` / `N-NODE-IN-VPC` | warn | リソースが AZ / VPC の直下にある | リソースは subnet に属する (VPC 直下は境界要素だけ) |
| `N-REGION-LABEL` | info | Region のラベルにリージョン名が無い | |
| `A-NAT-PLACEMENT` | error | NAT Gateway が public subnet の外 | public NAT は public subnet に作る |
| `A-DB-PUBLIC` | warn | データストアが public subnet | Well-Architected SEC05 |
| `A-COMPUTE-PUBLIC` | warn | 踏み台以外の計算資源が public subnet | 入口は ALB / NAT に絞る |
| `A-LAMBDA-PUBLIC` | warn | VPC Lambda が public subnet | パブリック IP は付かない |
| `A-GATEWAY-BORDER` | warn | IGW / VPN Gateway が VPC の枠線上に無い | VPC の出入口なので境界をまたいで描く |
| `A-REGIONAL-IN-VPC` | warn | S3 / DynamoDB / SQS などが VPC の中 | VPC の外のサービス。私設経路はエンドポイントで描く |
| `A-GLOBAL-IN-REGION` | warn | CloudFront / Route 53 / IAM が Region の中 | グローバルサービス |
| `A-ELB-IN-AZ` | warn | ELB が1つの AZ の中 | ELB は複数 AZ にまたがる (REL10) |
| `A-SINGLE-AZ` | warn | VPC のワークロードが 2 AZ 未満 | REL10。意図的なら報告に理由 |
| `A-NO-IGW` | warn | public subnet があるのに IGW が無い | |
| `A-DB-SINGLE` | info | 2 AZ なのに DB が1つの AZ だけ | Multi-AZ ならスタンバイを描くかラベルに書く |

## 最新の AWS 情報を確かめる (不確かなところだけ)

手元の知識と検査ルールはある時点のもの。次のどれかに当たるときだけ、公式の情報源で確かめてから設計する。

- 新しいサービス・機能、最近変わった仕様 (名前の変更、統合の可否)
- 指定リージョンで使えるか
- 構成の成否を左右する仕様 (その組み合わせで VPC 接続できるか、Multi-AZ に対応するか)
- 依頼で指定された構成の選択 (「VPC は使わない」「1 AZ でよい」) の影響と、見直すべき条件。図は指定どおりに描き、影響は報告に書く

道具: AWS Knowledge MCP (`search_documentation` / `read_documentation` / `get_regional_availability`) が使えればそれを、
無ければ docs.aws.amazon.com / aws.amazon.com に絞った Web 検索。どちらも使えなければ「未確認」と書く (確かめたふりをしない)。
**確認した日付と出典 URL を報告に残す。** 定番の配置 (NAT は public subnet など) は確かめない。
