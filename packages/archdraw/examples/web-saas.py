"""AWS 以外の見本: Cloudflare + Go + PostgreSQL の SaaS。並べ方は書かず (layout="auto")、つながりだけを書く。"""

from archdraw import Diagram

d = Diagram("受発注SaaS", layout="auto", icon_style="tile")
users = d.node("lucide:users", "利用者\n(ブラウザ)")
with d.group("generic", "Cloudflare", layout="auto"):
    waf = d.node("cloudflare:waf", "WAF / CDN")
    pages = d.node("cloudflare:pages", "Pages\n(React)")
    workers = d.node("cloudflare:workers", "Workers\n(API 入口)")
    kv = d.node("cloudflare:kv", "KV\n(セッション)")
auth0 = d.node("logos:auth0-icon", "Auth0")
with d.group("generic", "アプリ", layout="auto") as app:
    order = d.node("devicon:go", "注文 API\n(Go)")
    inv = d.node("devicon:go", "在庫 API\n(Go)")
    pg = d.node("devicon:postgresql", "PostgreSQL")
    redis = d.node("devicon:redis", "Redis")
    kafka = d.node("devicon:apachekafka", "Kafka")
    worker = d.node("devicon:python", "帳票ワーカー\n(Python)")
r2 = d.node("cloudflare:r2", "R2\n(帳票 PDF)")
dd = d.node("devicon:datadog", "Datadog")
acct = d.group("generic", "会計システム")    # 中身の無い generic = 外部システムの箱

users >> waf >> [pages, workers]
workers.to(auth0, "認証")
workers.to(kv, "セッション")
workers >> [order, inv]
[order, inv] >> pg
inv.to(redis, "キャッシュ")
order.to(kafka, "注文確定")
kafka >> worker
worker.to(r2, "PDF 保存", dashed=True)
worker.to(acct, "CSV (夜間)", dashed=True)
app.to(dd, "メトリクス", dashed=True)      # 監視は要素ごとに引かず、枠から 1 本
d.note("前提: 社内利用者もインターネット経由で Cloudflare に入る")
