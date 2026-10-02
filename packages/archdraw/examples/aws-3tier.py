"""aws-3tier.yaml と同じ図を Python で書いたもの。AZ ごとの同じ構成はループで書ける。"""

from archdraw import Diagram

d = Diagram("3層Webアプリ (東京)")
users = d.node("Users", "利用者", id="users")
with d.group("aws-cloud", layout="column", id="cloud"):
    with d.row(id="edge"):
        cf = d.node("Amazon CloudFront", "CloudFront", id="cf")
    with d.group("region", "ap-northeast-1 (東京)", id="tokyo"):
        with d.group("vpc", "VPC 10.0.0.0/16", layout="column", id="vpc"):
            igw = d.node("Internet Gateway", "Internet Gateway", id="igw")
            alb = d.node("ALB", "ALB", id="alb")
            ecs, nat, rds = {}, {}, {}
            with d.row(id="azs"):
                for i, az in enumerate("ac"):
                    with d.group("az", f"AZ ap-northeast-1{az}", layout="column", id=f"az-{az}"):
                        with d.group("public-subnet", f"Public 10.0.{i}.0/24", id=f"pub-{az}"):
                            nat[az] = d.node("NAT Gateway", "NAT Gateway", id=f"nat-{az}")
                        with d.group("private-subnet", f"App 10.0.{10 + i}.0/24", id=f"app-{az}"):
                            ecs[az] = d.node("AWS Fargate", "Fargate\nAPI", id=f"ecs-{az}")
                        with d.group("private-subnet", f"DB 10.0.{20 + i}.0/24", id=f"db-{az}"):
                            rds[az] = d.node("Amazon Aurora", "Aurora\n" + ("Writer" if az == "a" else "Reader"),
                                             id=f"rds-{az}")
        s3 = d.node("S3", "S3\n静的アセット", id="s3")

users.to(cf, "HTTPS")
cf >> igw
cf.to(s3, "OAC")
igw >> alb >> [ecs["a"], ecs["c"]]
for az in "ac":
    ecs[az] >> nat[az]
for az in "ac":
    nat[az] >> igw
for az in "ac":
    ecs[az] >> rds["a"]
rds["a"].to(rds["c"], "レプリケーション", dashed=True)
