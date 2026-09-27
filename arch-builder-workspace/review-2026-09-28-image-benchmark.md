# 画像由来ベンチマークの評価

## 結果

Eval 4 の最終候補は、自動 lint error 0、Desktop PNG の独立批評 pass、テスト 27 件通過。別モデルの採点は legibility 4/5、flow 4/5、AWS notation 5/5、requirements 5/5、architecture 5/5。必須・改善指摘は残らなかった。

- 編集用 YAML: [iteration-10/agentcore-clear-roles.arch.yaml](iteration-10/agentcore-clear-roles.arch.yaml)
- 生成・保存後 lint 済み draw.io: [iteration-10/agentcore-clear-roles.drawio](iteration-10/agentcore-clear-roles.drawio)
- 同じ draw.io から Desktop 出力した PNG (4936 × 2858): [iteration-10/agentcore-clear-roles.png](iteration-10/agentcore-clear-roles.png)
- ベンチマーク入力: [Eval 4](../skills/arch-builder/evals/evals.json)

図の画面比率は約1.73:1。MCP Server A/B/C と各接続先の垂直中心差はすべて 0 px、対応する3本の線は折れ曲がり 0。IAM Role は横並びにし、見出しの下へずらして、SubAgent と対応 Role の破線を個別に辿れる形にした。SubAgent 間隔も広げ、Role 線の近接警告と見出し横断警告を解消した。

「完璧」は主観的で保証できないため、完了条件を保存後 lint error 0、PNG の独立批評 pass、テスト全通過として測定した。批評者の legibility / flow は 5 点満点ではなく、残る lint 警告も下に明記する。

## ベンチマークの境界

元資料は依頼者提供の写真1枚。写真をリポジトリや作業ディレクトリへコピーせず、Gitにも含めていない。再実行用 Eval 4 は写真から要件を文章化し、files を空にした。写真はこの会話での評価だけに使用した。

評価した図は、User → Internet Gateway → ALB → Fargate、別の AgentCore Platform VPC 内の Orchestrator / Gateway / 縦並び3 SubAgent / Interceptor、別の MCP VPC 内の Gateway / MCP Server A・B・C と各接続先を含む。WAF association と SubAgent から AWS Account 内の Role A/B/C への関連も含めた。画像にない Region、AZ、VPC 間の物理経路、IAM 権限は補っていない。

## PDCA の記録

| 試行 | 仮説・変更 | 検証結果 |
|---|---|---|
| 基準 | 元の自動配置を保存後 lint | error 0 / warning 22 / info 1。曲がりの多い線、見出し横断、generic endpoint の扱いなどを検出。 |
| 1–2 | SubAgent 縦配置と YAML → draw.io → lint の往復を調べ、flow と exit / entry を draw.io metadata に保持。build は一時ファイルを再読込・lint し、差があれば既存出力を置き換えないよう変更。BOM付きUTF-8と Windows ESM path も修正。 | 保存前後で出入口の lint が異なる不具合を再現・解消。 |
| 3–4 | IAM 出口を比較し、線でつながった generic leaf を外部端点として描く。 | 未接続の空 generic group は警告を保ちつつ、接続済み端点をコンパクトな実線箱にした。テストで両条件を固定。 |
| 5–6 | VPC を横配置して Fargate → Orchestrator の経路を短くする。 | error 0 / warning 9 / info 2。PNG ではRole線の迂回と全体幅が課題として残った。 |
| 7 | 2段レイアウトにして全体幅を縮める。 | PNG の批評は legibility 3 / flow 4 / AWS notation 4 / requirements 5 / architecture 4、fail。線の迂回が増えたため不採用。 |
| 8 | Fargate と Orchestrator、AgentCore VPC と MCP VPC の位置を揃え、汎用接続先を小さくする。 | error 0 / warning 17 / info 1。批評は 3 / 3 / 5 / 4 / 5、fail。接続先の高さ、Role対応線、注記サイズが must / should。 |
| 9 | MCP接続先を各MCP Serverと同じ高さに固定し、MCP線を右→左の水平線にする。Roleを横並びに戻し、注記をページ幅まで広げ14ptにする。 | error 0 / warning 15 / info 1。PNG批評は 4 / 4 / 5 / 5 / 5、pass、findingsなし。PNGで接続先・Role対応を確認した。 |
| 10 | Role行をAccount見出しの下へ移し、SubAgent間隔を広げる。 | error 0 / warning 12 / info 1。批評は 4 / 4 / 5 / 5 / 5、pass、findingsなし。Role線の near-node 2件と through-header 1件を解消。 |

### V10に残るlint警告

| code | 数 | 理由・扱い |
|---|---:|---|
| A-REGIONAL-IN-VPC | 6 | 参照図のVPC枠内にAgentCoreを描いた論理表現による警告。実配置として採用する場合は Runtime ENI と Gateway のリージョンサービス / VPC egress を分けて再設計する。 |
| A-SINGLE-AZ | 1 | 元画像からAZ数を判断できないため補っていない。本番冗長化図へ転用するときは実AZを確認する。 |
| N-EDGE-BENDS | 4 | Fargate→Orchestrator と Interceptor→Gateway、GatewayからMCPへの分岐に残る迂回。最終PNGでは主要な流れを追えることを独立批評で確認した。 |
| N-EDGE-LABEL-CROSSED | 1 | HTTPS ラベル付近を Outbound 線が横切る。PNGの批評で読み違い指摘はなかったが、自動 lint 上は残る。 |
| N-REGION-LABEL | 1 info | Region 名が分からないため「未指定」と表示。 |

図の読みやすさ評価は通過したが、全警告ゼロではない。図を設計の確定版として使う場合は、VPC経路・AZ・IAM権限を確定し、残る線警告を設計条件に沿って再調整する。

## Skill とツールの変更

- YAML BOM / UTF-8 出力、group flow と edge exit / entry の保存・復元、Windows の draw.io / Node 検出を修正。
- arch build に保存後 lint の比較と原子的な出力置換を追加し、保存後に error や差異があれば既存ファイルを維持。
- 接続済み generic leaf はコンパクトな実線端点、子を持つ generic group は従来の破線枠として描画。
- notes をページ幅、fontSize 14 に合わせ、図全体表示での可読性を改善。Skill / spec に運用条件を記載。
- Eval 4 は配置・前提・MCP対応線・Role対応線・PNG批評条件を明示。

## 検査と制約

- arch build と保存済み draw.io の lint: error 0 / warning 12 / info 1。
- uv run --project skills/arch-builder/tools pytest skills/arch-builder/tools/tests -q: 27 passed。
- evals.json の JSON parse、git diff --check: pass。
- arch doctor: Asset Package 2026-07-31、service 1,220 / resource 513 / category 104 / group 15。
- Desktop PNG はローカル renderer で出力し、最終ファイルを自分で目視した後、別系列の画像批評に提出した。
- diagrams.net の外部URLを使う表示は自動審査で拒否された (構成データを信頼できない外部サービスへ渡すため)。ローカル Desktop 出力に切り替え、構成データや写真を外部へ送っていない。
- 写真のコピー・追跡、Git commit は行っていない。反映前の差分は作業ツリーにある。

## AWS公式資料

- [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/): 2026-07-31版の公式パッケージを使用。
- [AgentCore Runtime の VPC 接続](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-vpc.html): Runtime の VPC 接続では指定サブネットにサービス管理 ENI を作る。
- [AgentCore VPC interface endpoint](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/vpc-interface-endpoints.html) と [Gateway VPC egress](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-vpc-egress.html): Gateway API の PrivateLink 接続と、Gateway からVPC内ターゲットへの egress は異なる関係として扱う。
