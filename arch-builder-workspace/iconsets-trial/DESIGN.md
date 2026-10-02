# 設計案: アイコンセットとリンターのモジュール化

arch-builder を「AWS 構成図ツール」から「システム構成図ツール」にするための分け方。
段階1 (アイコンセットと汎用インポーター) は実装済み。段階2以降は案。

## 全体の分け方

```text
core (配置・経路探索・.drawio 入出力・幾何の lint)   ← どの図でも同じ
 ├─ icons    名前 → SVG。取り込んだセットを読む          ← 段階1で分離済み (icons.py)
 │   └─ importer  ノズルごとに取り込み、IconifyJSON にそろえる (importer.py)
 └─ packs    図の種類ごとの「グループの種類」と「構成ルール」
     ├─ aws        いまの GROUPS・ゲートウェイの置き場所・A-* ルール
     ├─ web        汎用 Web システム (つないではいけない組み合わせなど)
     └─ (cloudflare / gcp / 社内ルール …)
```

core は、アイコンがどのセットから来たか、グループが AWS の何に当たるかを知らない。

## lint の分け方

いまの `rules.py` は3つの節に分かれており、そのまま切り分けられる。

| 行き先 | ルール | 理由 |
| --- | --- | --- |
| core | 幾何 (`N-EDGE-*` `N-OVERLAP` `N-PORT-*` `N-ESCAPE` `N-VISUAL-PARENT` `N-ASPECT*`)、`N-LABEL*`、`N-NODE-UNCONNECTED`、`N-SPARSE`、`E-ICON` `E-REF` | 見た目の破綻は図の種類によらない |
| pack: aws | `N-NESTING` (グループの入れ子)、`N-CATEGORY-ICON` `N-GROUP-ICON`、`N-SUBNET-*` `N-NODE-IN-*`、`A-*` 全部 | AWS の規約 |
| pack: web など | 新しく書く | 図の種類ごとに違う |

`N-NESTING` の中身 (どのグループの中に何を置けるか) は、いまは `GROUPS` の `parents` で決まっている。
これを pack が持つようにすれば、core の入れ子チェックはそのまま使い回せる。

## pack の形

Python のモジュールと、宣言的な YAML の2通りを用意する。AWS のように複雑な判定がある pack は Python、
「これとこれはつながない」程度なら YAML で足りる。

```python
# packs/aws.py
GROUPS = {"aws-cloud": GroupSpec(...), "vpc": GroupSpec(...), ...}   # グループの種類と、置いてよい親
BORDER_DEFAULTS = {"aws:internet-gateway": "top", ...}                 # 枠線の上に乗せるもの
ALIASES = {"alb": "aws:elastic-load-balancing-application-load-balancer", ...}
def check(m, add): ...                                                # A-* ルール
```

```yaml
# packs/web.yaml — 汎用 Web システムの定石
roles:                      # アイコン → 役割。arch.yaml で `role:` を書けば上書きできる
  client:   [lucide:users, lucide:smartphone, lucide:monitor]
  frontend: [devicon:react, devicon:vuejs, devicon:nextjs, svgl:*-frontend]
  backend:  [devicon:go, devicon:python, devicon:nodejs, cloudflare:workers]
  database: [devicon:postgresql, devicon:mysql, lucide:database, aws:amazon-rds]
  cache:    [devicon:redis, cloudflare:kv]
rules:
  - id: W-CLIENT-TO-DB
    severity: error
    forbid: {from: client, to: database}
    message: 利用者から DB へ直接つながない
    fix: backend を間に置く
  - id: W-FRONTEND-TO-DB
    severity: warn
    forbid: {from: frontend, to: database}
    message: フロントエンドから DB を直接読まない
  - id: W-DB-INBOUND
    severity: warn
    require: {role: database, inbound_from: [backend]}
    message: DB には backend からの線が要る
  - id: W-SINGLE-DB
    severity: info
    count: {role: database, max: 1}
    message: DB が複数ある。役割の違いをラベルに書く
```

ルールの種類は、まず次の4つで足りる見込み。

| 種類 | 意味 | 例 |
| --- | --- | --- |
| `forbid` | この役割からこの役割への線を禁止 | client → database |
| `require` | この役割には、この役割からの線が要る | database ← backend |
| `placement` | この役割は、この種類のグループの中に置く | database は private-subnet の中 (aws の A-DB-PUBLIC と同じ形) |
| `count` | この役割の数 | DB が 1 つしかない (冗長化の指摘) |

どの pack を使うかは arch.yaml のトップレベルに書く。書かなければ、使っているグループ・アイコンから決める
(AWS のグループがあれば aws、なければ web)。

```yaml
packs: [web, cloudflare]
```

## AWS を必須から外す

- AWS も importer のノズルの1つにする: `arch icons fetch aws <Icon-package.zip>`。
  ZIP の場所の案内 (doctor に出しているもの) はそのまま使う
- 保存先を `icons/sets/aws.json` にそろえ、`icon: aws:amazon-rds` と書けるようにする。
  `icon: Amazon RDS` のような prefix の無い書き方は、互換のため aws セットとして引く
- doctor は「AWS が無ければ作図できない」から「この図に必要なセットがあるか」に変える。
  AWS のグループやアイコンを使わない図は、AWS のパッケージが無くても作れる
- グループの枠のアイコン (VPC・Subnet の旗など) は aws pack の持ち物にする

## 見た目のそろえ方 (段階1の試作で分かったこと)

AWS のアイコンは、48px いっぱいの色付きタイルで、中の線が細い (約1.5px)。
ほかのセットは形も大きさもまちまちで、そのまま並べると接続線 (2px) との釣り合いが崩れる。

- 線画アイコンの線幅は、48px で 1.5px になるよう細くする (実装済み。Lucide の 4px → 1.5px)
- 形のばらつきは、白い角丸タイルに載せるとそろう (試作: `web-stack-tile.png`)。既定にするか選べるようにするかは未決

## OSS にするときの注意

- アイコンの実データはリポジトリに入れない (`icons/` は git 管理外)。利用者の手元で importer が取り込む
- 取り込んだセットのライセンスは IconifyJSON の `info.license` に残し、`arch doctor` に出す
- Cloudflare の製品アイコンは CC BY 4.0。図を配るときの出典表記 (「アイコン: Cloudflare (CC BY 4.0)」) を
  `notes:` に自動で足すかは要検討。SVGL のロゴは各ブランドの規約に従う

## 段階

1. **アイコンセットと汎用インポーター** (済): `icons.py` / `importer.py`、ノズル iconify / svgl / cloudflare / svg
2. AWS をノズルにして必須から外す。`aws:` prefix、doctor の見直し
3. `rules.py` を core と `packs/aws.py` に分ける。`GROUPS` を pack へ
4. 宣言的な pack (YAML) と役割 (roles)。最初の pack は `web`
5. アイコンの見た目 (タイル) の既定を決める
