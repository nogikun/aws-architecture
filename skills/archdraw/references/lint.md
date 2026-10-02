# 検査 (lint) のルール

出力は `[重大度] コード id: 説明` と、直し方を示す `→` の行でできている。

- **error**: 図として誤っている。納品前に 0 件にする (build は error があると .drawio を書かない)
- **warn**: 読みにくさ・定石からの外れ。直すのが基本。意図があるなら理由を報告に書いて残してよい
- **info**: 書き足すと親切なもの

AWS の構成ルール (`A-*` と AWS の `N-*`) は [aws.md](aws.md)。ここはどの図にも当たる core のルール。

## 読み込み

| コード | 重大度 | 何を見るか |
| --- | --- | --- |
| `E-ICON` | error | アイコンが見つからない (名前違い、セット未取り込み)。`→` に候補と取り込み方が出る |
| `E-ID` / `E-REF` | error | id の重複・欠落、線の端が存在しない |
| `E-PAGE-ASPECT` / `E-ICON-STYLE` / `E-LAYOUT` | error | 図全体の設定値が不正 |
| `N-UNMANAGED` | error | draw.io で足された、ライブラリに無い画像や図形 |

## 作図規約

| コード | 重大度 | 何を見るか |
| --- | --- | --- |
| `N-LABEL` / `N-LABEL-LONG` | error / warn | アイコンにラベルが無い / 1 行が長い (改行で 2 行に) |
| `N-ICON-DISTORT` / `N-ICON-SIZE` | error / warn | アイコンの縦横比が崩れている / 48px 以外 |
| `N-GROUP-TYPE` | error | 未知の枠の種類 |
| `N-NESTING` | error | 置いてよい親が決まっている種類 (AWS の region / vpc / az …) の親が違う |
| `N-EMPTY-GROUP` | warn | 中身の無い枠 (ラベル付きで線につながる generic は外部システムの箱なので対象外) |
| `N-NODE-UNCONNECTED` | error | どの線ともつながっていないアイコン |
| `N-BORDER-ON-LAYOUT` | warn | 描かれない layout 箱の枠線上に置いている |
| `N-EDGE-SELF` / `N-EDGE-DUP` / `N-EDGE-LABEL-LONG` | warn | 自分への線 / 重複した線 / 線のラベルが長い |

## 見た目の破綻 (幾何)

| コード | 重大度 | 何を見るか |
| --- | --- | --- |
| `N-ESCAPE` / `N-OVERLAP` / `N-VISUAL-PARENT` | error | 子が枠からはみ出す / 兄弟が重なる / 見た目の所属と定義上の所属が違う |
| `N-EDGE-THROUGH-NODE` | error | 線がアイコンかラベルを横切る。並び順を変えるか、exit / entry で直す |
| `N-PORT-FACE` / `N-PORT-SLOT` | error | 線の出入りの面・位置が決まりと違う (build し直せば直る) |
| `N-ASPECT-PORTRAIT` | error | 図全体が縦長 |
| `N-SPARSE` | warn / error | 枠が中身に対して広すぎる (1.5 倍超で warn、2 倍以上で error) |
| `N-EDGE-NEAR-NODE` | warn | 線が無関係なアイコンのすぐ脇を通り、そこへつながっているように見える |
| `N-EDGE-CROSS` / `N-EDGE-TOUCH` | warn | 線どうしが交差する / 端で接する |
| `N-EDGE-OVERLAP` | warn | 内容の違う線が重なって走る |
| `N-EDGE-BENDS` | warn | 実線が 3 回以上曲がる (並びが流れの向きと合っていない) |
| `N-EDGE-LABEL-OVERLAP` / `N-EDGE-LABEL-CROSSED` | warn | 線のラベルが何かに重なる / ラベルの上を別の線が通る |
| `N-EDGE-THROUGH-HEADER` / `N-EDGE-ON-FRAME` | warn | 線が枠の見出しを横切る / 枠線に沿って走る |
| `N-EDGE-LABEL-ON-FRAME` | warn | 線のラベル (線の中点に置かれる) が枠線の上にあり、枠線が文字を貫く。枠をまたぐ短い線で起きやすい。ラベルを短くするか、外す (関係の役割は要素のラベルに書いてもよい)。読めるなら理由を書いて残してよい |
| `N-ASPECT` | info | 横長だが 16:9 の目安から外れている |
| `N-EDGE-UNCHECKED` | info | draw.io 任せの経路で検査できない線がある |

`--strict-geometry` を付けると、交差・接触・重なり・検査できない線が 1 本でもあれば失敗する (納品前の確認)。

## warn を減らすときの順番

1. 線を減らす (全体にかかる関係は枠から 1 本に、同じ線は代表 1 本に)
2. つながる相手を隣に置く (`layout="auto"` なら線の向きをそろえる。手で並べるなら並び順)
3. 枠の分け方を変える (意味のまとまりで分ける。大きすぎる枠を割る)
4. 最後に exit / entry で 1〜2 本だけ固定する
