from archdraw import Diagram

d = Diagram("AgentCore 構成")
user = d.node("Users", "User")
with d.group("aws-cloud", layout="row"):
    waf = d.node("AWS WAF", "WAF\nWeb ACL")
    with d.group("region", "Region (未確定)", layout="row"):
        with d.group("vpc", "フロントエンド VPC", layout="column"):
            igw = d.node("Internet Gateway", "Internet Gateway")
            with d.group("public-subnet", "Public Subnet"):
                alb = d.node("ALB", "ALB")
            with d.group("private-subnet", "Private Subnet"):
                fargate = d.node("AWS Fargate", "Fargate")
        with d.group("vpc", "AgentCore Platform VPC"):
            with d.group("private-subnet", "Private Subnet"):
                orch = d.node("lucide:bot", "Orchestrator\nAgent")
                gw1 = d.node("lucide:bot", "AgentCore\nGateway")
                with d.column():
                    subs = [d.node("lucide:bot", f"SubAgent {x}") for x in "ABC"]
                icp = d.node("lucide:bot", "Interceptor")
        with d.group("vpc", "MCP VPC"):
            with d.group("private-subnet", "Private Subnet"):
                cedar = d.node("lucide:bot", "Cedar Policy\nEngine")
                gw2 = d.node("lucide:bot", "AgentCore\nGateway")
                with d.column():
                    mcps = [d.node("lucide:server", f"MCP Server {x}") for x in "ABC"]
    with d.column():
        with d.group("account", "AWS Account"):
            with d.column():
                roles = [d.node("AWS Identity Access Management Role", f"Role-MCP-{x}") for x in "ABC"]
        with d.group("generic", "AWS environment") as env:
            pass
        ks = d.node("Document", "AWS Knowledge\nServer")
        ddb = d.node("Amazon DynamoDB", "RAG\n(DynamoDB)")

user.to(igw, "HTTPS")
igw >> alb
alb.to(fargate, "HTTPS")
waf.to(alb, "Web ACL association", dashed=True)
fargate.to(orch, "HTTPS")
orch >> gw1
gw1 >> subs
subs >> icp
for s, r in zip(subs, roles):
    s.to(r, dashed=True)
icp.to(cedar, "HTTPS / MCP")
cedar >> gw2
gw2 >> mcps
for m in mcps:
    m >> [env, ks, ddb]
d.note("Region・AZ は元資料から不明のため未確定")
d.note("VPC 間の具体的なネットワーク経路は不明")
d.note("Role の権限内容は不明")
