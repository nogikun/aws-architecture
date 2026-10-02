"""AWS の pack: グループの種類 (AWS Cloud ⊃ Region ⊃ VPC ⊃ AZ ⊃ Subnet) と、AWS の構成ルール。

- N-* (AWS の作図規約): グループアイコン・カテゴリアイコンの誤用、AZ / VPC の中の置き場所
- A-* (構成の定石): DB を public に置かない、NAT は public subnet、ゲートウェイは VPC の枠線上 など
検査は AWS のグループ・アイコンにだけ当たる (取り込んだセットの prefix:name は対象外)。根拠は references/aws.md。
"""

from __future__ import annotations

import re

from archdraw.lint import CHECKS, Ctx
from archdraw.model import GROUPS, LAYOUT_ONLY, GroupSpec, Model, on_border

SUBNETS = ("public-subnet", "private-subnet")
# VPC の枠線上に置くゲートウェイ類の既定の辺 (VPC 直下に置いたときだけ当てる)。境界をまたぐものは境界の上に描く
VPC_BORDERS = (
    ("Amazon VPC Internet Gateway", "top"),     # インターネット側
    ("Amazon VPC Carrier Gateway", "top"),
    ("Amazon VPC VPN Gateway", "bottom"),       # 外 (オンプレ) へ出す口はフッター側
    ("AWS Transit Gateway Attachment", "bottom"),
)
GROUPS.update({
    "aws-cloud": GroupSpec("AWS Cloud", "#232F3E", icon="AWS Cloud logo", parents=(None,)),
    "account": GroupSpec("AWS Account", "#E7157B", icon="AWS Account", parents=(None, "aws-cloud")),
    "region": GroupSpec("Region", "#00A4A6", dashed=True, icon="Region", parents=("aws-cloud", "account")),
    # VPC の中は上 -> 下に流す (ヘッダー: IGW / ALB、ボディ: AZ、フッター: 外へ出す口)
    "vpc": GroupSpec("VPC", "#8C4FFF", icon="Virtual private cloud VPC", parents=("region",), flow="down",
                     borders=VPC_BORDERS),
    # 見出しは左寄せ。中央だと、AZ の中央に置いた NAT から IGW へ上る線が見出しを避けて大回りする
    "az": GroupSpec("Availability Zone", "#00A4A6", dashed=True, parents=("vpc",)),
    "public-subnet": GroupSpec("Public subnet", "#7AA116", "#F2F6E8", icon="Public subnet", parents=("az", "vpc")),
    "private-subnet": GroupSpec("Private subnet", "#00A4A6", "#E6F6F7", icon="Private subnet", parents=("az", "vpc")),
    "security-group": GroupSpec("Security group", "#DD3522", parents=SUBNETS + ("az", "vpc")),
    "auto-scaling": GroupSpec("Auto Scaling group", "#ED7100", dashed=True, icon="Auto Scaling group",
                              parents=SUBNETS + ("az", "vpc", "security-group")),
    "ec2-contents": GroupSpec("EC2 instance contents", "#ED7100", icon="EC2 instance contents",
                              parents=SUBNETS + ("security-group", "auto-scaling")),
    "spot-fleet": GroupSpec("Spot Fleet", "#ED7100", icon="Spot Fleet", parents=SUBNETS + ("az", "vpc")),
    "corporate-dc": GroupSpec("Corporate data center", "#7D8998", icon="Corporate data center", parents=(None,)),
    "server-contents": GroupSpec("Server contents", "#7D8998", icon="Server contents", parents=(None, "corporate-dc")),
})
AWS_GROUPS = [k for k in GROUPS if k not in ("generic", LAYOUT_ONLY)]


# アイコン名 (正規化後) の部分一致で役割を判定する
def _has(name: str, *words: str) -> bool:
    if ":" in name:  # 取り込んだセット (lucide:cards など) は AWS の定石の対象外。"cards" が "rds" に当たらないように
        return False
    n = name.lower()
    return any(w in n for w in words)


DATA_STORE = ("rds", "aurora", "elasticache", "redshift", "documentdb", "neptune", "memorydb", "opensearch")
COMPUTE = ("ec2", "instance", "elastic container service", "ecs", "fargate", "eks", "elastic kubernetes")
OUTSIDE_VPC = ("simple storage service", "s3", "dynamodb", "simple queue service", "sqs", "simple notification",
               "sns", "api gateway", "cognito", "eventbridge", "step functions", "kinesis", "secrets manager",
               "key management", "cloudwatch", "cloudtrail", "elastic container registry", "simple email",
               "athena", "glue", "bedrock", "codepipeline", "codebuild", "systems manager")
GLOBAL = ("cloudfront", "route 53", "identity and access management", "iam", "global accelerator", "organizations")
VPC_EDGE = ("internet gateway", "load balanc", "vpn gateway", "virtual private gateway", "endpoint",
            "transit gateway", "network firewall", "privatelink", "customer gateway")
GATEWAYS = ("internet gateway", "nat gateway", "vpn gateway", "carrier gateway", "customer gateway", "transit gateway",
            "direct connect", "endpoint")
BASTION = re.compile(r"bastion|踏み台|jump", re.I)


def _word(name: str, words) -> bool:
    if ":" in name:
        return False
    n = " " + re.sub(r"[^a-z0-9]+", " ", name.lower()) + " "
    return any(f" {w} " in n for w in words)



def check(m: Model, c: Ctx):
    add, nodes, groups = c.add, c.nodes, c.groups
    real_parent, real_children, gtypes = c.real_parent, c.real_children, c.gtypes

    # ---------------- AWS の作図規約 ----------------
    for it in nodes:
        if it.unmanaged or not it.raw_icon:
            continue
        if it.raw_icon.kind == "category":
            add("error", "N-CATEGORY-ICON", it.id,
                f"カテゴリアイコン '{it.icon}' をサービスとして使っている (カテゴリアイコンはサービスを表さない)",
                "具体的なサービスアイコンにする")
        elif it.raw_icon.kind == "group":
            add("error", "N-GROUP-ICON", it.id, f"グループアイコン '{it.icon}' を単体で置いている",
                "group として表現する (group: vpc など)")

    for it in groups:
        if it.group not in GROUPS or it.group == LAYOUT_ONLY:
            continue
        if it.group == "region" and not re.search(r"[a-z]{2}-[a-z]+-\d|東京|大阪|バージニア|オレゴン", it.label or ""):
            add("info", "N-REGION-LABEL", it.id, "Region のラベルにリージョン名が無い", "例: 'ap-northeast-1 (東京)'")
        if it.group == "vpc":
            azs = [c.id for c in real_children(it) if c.group == "az"]
            loose = [c.id for c in real_children(it) if c.group in SUBNETS]
            if azs and loose:
                add("warn", "N-SUBNET-OUTSIDE-AZ", it.id, f"AZ を描いた VPC で、AZ の外に subnet がある: {loose}",
                    "subnet は必ずどれか1つの AZ に属する。該当 AZ の中へ移す")
        if it.group == "az":
            bare = [c.id for c in real_children(it) if c.kind == "node"]
            if bare:
                add("warn", "N-NODE-IN-AZ", it.id, f"AZ の直下にリソースがある: {bare}", "リソースは subnet の中に置く")

    for it in nodes:
        rp = real_parent(it)
        if rp and rp.group == "vpc" and it.raw_icon and not _has(it.raw_icon.name, *VPC_EDGE):
            add("warn", "N-NODE-IN-VPC", it.id, f"'{it.raw_icon.name}' が VPC 直下にある",
                "VPC 内のリソースは subnet に置く (VPC 直下に置いてよいのは IGW / ELB / エンドポイント等の境界要素)")

    # ---------------- 構成の妥当性 ----------------
    vpcs = [g for g in groups if g.group == "vpc"]
    for it in nodes:
        if not it.raw_icon:
            continue
        name, anc = it.raw_icon.name, gtypes(it)
        in_public = "public-subnet" in anc
        in_vpc = "vpc" in anc
        bastion = bool(BASTION.search(it.label))
        if in_public and _has(name, *DATA_STORE):
            add("warn", "A-DB-PUBLIC", it.id, f"データストア '{name}' が public subnet にある", "private subnet に置く")
        if in_public and _word(name, COMPUTE) and not bastion:
            add("warn", "A-COMPUTE-PUBLIC", it.id, f"'{name}' が public subnet にある (踏み台以外)",
                "アプリ層は private subnet に置き、入口は ALB / NAT を通す")
        if in_public and _has(name, "lambda"):
            add("warn", "A-LAMBDA-PUBLIC", it.id, "VPC Lambda を public subnet に置いてもパブリック IP は付かない",
                "private subnet + NAT Gateway (または VPC エンドポイント) にする")
        if _has(name, "nat gateway") and not in_public:
            add("error", "A-NAT-PLACEMENT", it.id, "NAT Gateway は public subnet に置く", "public subnet の中へ移す")
        if _has(name, "internet gateway", "vpn gateway", "carrier gateway") and not (
                it.parent and m.items[it.parent].group == "vpc" and on_border(it)):
            add("warn", "A-GATEWAY-BORDER", it.id, f"'{name}' は VPC の枠線の上に置く (VPC の出入口なので境界をまたいで描く)",
                "VPC の直下に置けば自動で枠線上に乗る (IGW は上辺、VPN Gateway は左辺)。辺は border: で変えられる")
        if in_vpc and _word(name, OUTSIDE_VPC) and not _has(name, "endpoint", "agentcore"):
            add("warn", "A-REGIONAL-IN-VPC", it.id, f"'{name}' は VPC の外のリージョンサービス",
                "Region 直下 (VPC の外) に置く。VPC から私設経路で使うなら VPC エンドポイントを描く")
        if "region" in anc and _word(name, GLOBAL):
            add("warn", "A-GLOBAL-IN-REGION", it.id, f"'{name}' はグローバルサービス", "Region の外 (AWS Cloud 直下) に置く")
        if _has(name, "load balanc") and "az" in anc:
            add("warn", "A-ELB-IN-AZ", it.id, "ELB は複数の AZ にまたがる。1つの AZ の中に描くと単一 AZ に見える",
                "VPC 直下 (AZ をまたぐ位置) に置く")

    for v in vpcs:
        sub = [m.items[i] for i in {x.id for x in m.walk(v.children)}]
        azs = [g for g in sub if g.group == "az"]
        has_workload = any(n.kind == "node" and n.raw_icon and (_word(n.raw_icon.name, COMPUTE) or _has(n.raw_icon.name, *DATA_STORE))
                           for n in sub)
        if has_workload and len(azs) < 2:
            add("warn", "A-SINGLE-AZ", v.id, f"VPC {v.id} のワークロードが {len(azs)} AZ にしか無い",
                "本番想定なら 2 AZ 以上に分散して描く。検証環境など意図的なら報告で理由を言う")
        if len(azs) >= 2:
            for n in sub:
                if n.kind == "node" and n.raw_icon and _has(n.raw_icon.name, "rds", "aurora"):
                    others = [x for x in sub if x.kind == "node" and x.raw_icon and x.raw_icon.name == n.raw_icon.name]
                    if len(others) == 1:
                        add("info", "A-DB-SINGLE", n.id, "DB が1つの AZ にしか描かれていない",
                            "Multi-AZ ならスタンバイ (もう一方の AZ) も描くか、ラベルに Multi-AZ と書く")
                    break
        has_public = any(g.group == "public-subnet" for g in sub)
        has_igw = any(n.kind == "node" and n.raw_icon and _has(n.raw_icon.name, "internet gateway") for n in sub)
        if has_public and not has_igw:
            add("warn", "A-NO-IGW", v.id, "public subnet があるのに Internet Gateway が描かれていない")


CHECKS.append(check)
