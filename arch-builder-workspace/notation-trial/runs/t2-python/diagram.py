from archdraw import Diagram

d = Diagram("受発注SaaS")
users = d.node("lucide:users", "利用者\n(ブラウザ)")
with d.group("generic", "Cloudflare", layout="column"):
    waf = d.node("cloudflare:waf", "WAF / CDN")
    with d.row():
        pages = d.node("cloudflare:pages", "Pages\n(React)")
        workers = d.node("cloudflare:workers", "Workers\n(API 入口)")
    with d.row():
        kv = d.node("cloudflare:kv", "KV\n(セッション)")
        r2 = d.node("cloudflare:r2", "R2\n(帳票 PDF)")
auth0 = d.node("logos:auth0-icon", "Auth0")
with d.group("generic", "アプリ"):
    with d.column():
        order = d.node("devicon:go", "注文 API\n(Go)")
        inv = d.node("devicon:go", "在庫 API\n(Go)")
    with d.column():
        pg = d.node("devicon:postgresql", "PostgreSQL")
        redis = d.node("devicon:redis", "Redis")
    with d.column():
        kafka = d.node("devicon:apachekafka", "Kafka")
        worker = d.node("devicon:python", "帳票ワーカー\n(Python)")
with d.column():
    dd = d.node("devicon:datadog", "Datadog")
    acct = d.group("generic", "会計システム")

users >> waf
waf >> [pages, workers]
workers.to(auth0, "認証")
workers.to(kv, "セッション")
workers >> [order, inv]
order >> pg
inv >> pg
inv.to(redis, "キャッシュ")
order.to(kafka, "注文確定")
kafka >> worker
worker.to(r2, "PDF 保存", dashed=True)
worker.to(acct, "CSV (夜間)", dashed=True)
for s in (workers, order, inv, worker):
    s.to(dd, "メトリクス", dashed=True)
