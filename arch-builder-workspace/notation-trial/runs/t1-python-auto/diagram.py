from archdraw import Diagram

d = Diagram("AgentCore 構成", layout="auto")
user = d.node("Users", "User")

with d.group("aws-cloud", "AWS Cloud", layout="auto"):
    waf = d.node("AWS WAF", "WAF Web ACL")
    with d.group("region", "Region (未確定)", layout="auto"):
        with d.group("vpc", "Frontend VPC", layout="column"):
            igw = d.node("Internet Gateway", "IGW")
            with d.group("public-subnet", "Public Subnet"):
                alb = d.node("ALB", "ALB")
            with d.group("private-subnet", "Private Subnet"):
                fargate = d.node("AWS Fargate", "Fargate")
        with d.group("vpc", "AgentCore Platform VPC", layout="auto"):
            with d.group("private-subnet", "Private Subnet", layout="auto"):
                orch = d.node("Amazon Bedrock AgentCore", "Orchestrator Agent")
                gw = d.node("Amazon Bedrock AgentCore", "AgentCore Gateway")
                subs = [d.node("Amazon Bedrock AgentCore", f"SubAgent {x}") for x in "ABC"]
                icp = d.node("Amazon Bedrock AgentCore", "Interceptor")
        with d.group("vpc", "MCP VPC", layout="auto"):
            with d.group("private-subnet", "Private Subnet", layout="auto"):
                cedar = d.node("Amazon Bedrock AgentCore", "Cedar Policy Engine")
                mgw = d.node("Amazon Bedrock AgentCore", "AgentCore Gateway")
                mcps = [d.node("AWS Fargate", f"MCP Server {x}") for x in "ABC"]
        ddb = d.node("Amazon DynamoDB", "RAG (DynamoDB)")
    with d.group("account", "AWS Account", layout="column"):
        roles = [d.node("AWS Identity Access Management Role", f"Role-MCP-{x}") for x in "ABC"]
env = d.group("generic", "AWS environment")
kb = d.group("generic", "AWS Knowledge Server")

user.to(igw, "HTTPS")
igw >> alb
alb.to(fargate, "HTTPS")
waf.to(alb, "Web ACL association", dashed=True)
fargate.to(orch, "HTTPS")
orch >> gw
gw >> subs
subs >> icp
for s, r in zip(subs, roles):
    s.to(r, dashed=True)
icp.to(cedar, "HTTPS / MCP")
cedar >> mgw
mgw >> mcps
for m in mcps:
    m >> [env, kb, ddb]
d.note("Region は元資料に無いため未確定 (AZ も不明で図に含めない)")
d.note("VPC 間の具体的なネットワーク経路は不明")
d.note("Role の権限内容は不明")
