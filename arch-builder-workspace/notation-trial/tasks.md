# 表記トライアルの課題

## T1: AgentCore 構成 (AWS・要素が多く繰り返しがある)

設計レビュー用の AWS 構成図を作ってください。AWS Cloud の外に User を置き、HTTPS を Internet Gateway 経由でフロントエンド VPC の Public Subnet にある ALB へつなぐ。ALB から Private Subnet の Fargate へ HTTPS で接続し、WAF の Web ACL association は通信線と区別して破線で示す。下段に AgentCore Platform VPC を置き、Private Subnet 内で Orchestrator Agent → AgentCore Gateway → SubAgent A/B/C の順に分岐させ、3つの SubAgent は縦に並べて Interceptor に集約する。Fargate から Orchestrator へ HTTPS、各 SubAgent から AWS Account 内の Role-MCP-A/B/C へ破線の関連を示す。Interceptor から HTTPS / MCP で別の MCP VPC に接続し、その Private Subnet に Cedar Policy Engine と AgentCore Gateway、MCP Server A/B/C を置く。各 MCP Server から AWS environment、AWS Knowledge Server、RAG (DynamoDB) へそれぞれ接続する。元資料で分からない Region、AZ、VPC 間の具体的なネットワーク経路、Role の権限内容は決めつけず、図に不明点として残す。

## T2: SaaS の Web システム (AWS 以外)

社内向け受発注 SaaS のシステム構成図を作ってください。利用者 (ブラウザ) は Cloudflare の WAF/CDN を通り、静的なフロントエンド (React、Cloudflare Pages) と、API の入口になる Cloudflare Workers に入る。Workers は認証を Auth0 に問い合わせ、セッションを Cloudflare KV に置く。Workers の先に Go の API が 2 つ (注文 API と在庫 API) あり、どちらも PostgreSQL を使い、在庫 API は Redis をキャッシュに使う。注文が確定したら注文 API が Kafka にイベントを積み、Python のワーカーが非同期に処理して帳票 PDF を Cloudflare R2 に置く。全サービスのメトリクスは Datadog に送る (監視の線は通信と区別する)。社内の会計システム (外部) へは、Python ワーカーから夜間に CSV を送る。
