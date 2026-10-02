"""archdraw: システム構成図を Python / YAML / タグ表記で書き、編集できる draw.io の図にする。

    from archdraw import Diagram
    d = Diagram("Web サービス")
    users = d.node("lucide:users", "利用者")
    api = d.node("devicon:go", "API")
    users.to(api, "HTTPS")
    d.save("web.drawio")
"""

from archdraw.api import Diagram, Group, Ref
from archdraw.icons import Library
from archdraw.lint import Finding, lint, report
from archdraw.model import GROUPS, Model, from_dict, load_yaml
from archdraw.packs import aws as _aws  # noqa: F401  AWS のグループ種類と構成ルールを登録する

__all__ = ["Diagram", "Group", "Ref", "Library", "Finding", "lint", "report", "GROUPS", "Model", "from_dict",
           "load_yaml"]
