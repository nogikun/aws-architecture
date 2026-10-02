from archdraw import Diagram

d = Diagram("受発注SaaS", layout="auto", icon_style="tile")
users = d.node("lucide:users", "利用者 (ブラウザ)")
with d.group("generic", "Cloudflare", layout="auto") as cf:
    waf = d.node("cloudflare:waf", "WAF / CDN")
    pages = d.node("cloudflare:pages", "Pages (React)")
    workers = d.node("cloudflare:workers", "Workers (API入口)")
    kv = d.node("cloudflare:kv", "KV (セッション)")
auth0 = d.node("logos:auth0", "Auth0")
r2 = d.node("cloudflare:r2", "Cloudflare R2 (帳票PDF)")
with d.group("generic", "バックエンド", layout="auto") as be:
    order = d.node("devicon:go", "注文 API")
    stock = d.node("devicon:go", "在庫 API")
    pg = d.node("devicon:postgresql", "PostgreSQL")
    redis = d.node("devicon:redis", "Redis (キャッシュ)")
    kafka = d.node("devicon:apachekafka", "Kafka")
    worker = d.node("devicon:python", "帳票ワーカー")
dd = d.node("devicon:datadog", "Datadog")
acct = d.group("generic", "会計システム")

users.to(waf, "HTTPS")
waf >> [pages, workers]
workers.to(auth0, "認証")
workers.to(kv, "セッション")
workers >> [order, stock]
[order, stock] >> pg
stock >> redis
order.to(kafka, "注文イベント")
kafka >> worker
worker.to(r2, "帳票PDF")
worker.to(acct, "CSV (夜間)")
be.to(dd, "メトリクス", dashed=True)
cf.to(dd, "メトリクス", dashed=True)
d.note("Cloudflare Pages/Workers/KV は 1 つの枠にまとめた。R2 は帳票の出力先として枠外に置いた")
