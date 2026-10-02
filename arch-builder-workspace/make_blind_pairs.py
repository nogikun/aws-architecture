"""盲検の対を作る: arch-builder (2026-09-28 の最終版) と archdraw (iteration-15) の最終 PNG を、eval・run ごとに
ランダムな A/B に並べて blind/eval-N/pair-K-{a,b}.png に置く。対応表は blind/key.json (レビュー担当には見せない)。

    python make_blind_pairs.py <eval番号...> --runs 1 2 3
"""

import argparse
import json
import random
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = Path(r"C:\Users\takah\Documents\git\aws-architecture\arch-builder-workspace\iteration-12")
OLD_PNG = {
    1: "eval-1-fargate-aurora-web/with_skill/run-{r}/outputs/architecture.png",
    2: "eval-2-serverless-orders/with_skill/run-{r}/outputs/orders-r{r}.png",
    3: "eval-3-flawed-diagram-repair/with_skill/run-{r}/outputs/flawed.png",
    4: "eval-4-photo-reconstruction/with_skill/run-{r}/outputs/photo-reconstruction.png",
}
NEW = HERE / "iteration-15-archdraw"
BLIND = NEW / "blind"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("evals", nargs="+", type=int)
    p.add_argument("--runs", nargs="+", type=int, default=[1, 2, 3])
    p.add_argument("--seed", type=int, default=20261002)
    a = p.parse_args()
    rng = random.Random(a.seed)
    keyf = BLIND / "key.json"
    key = json.loads(keyf.read_text(encoding="utf-8")) if keyf.exists() else {}
    for e in a.evals:
        for r in a.runs:
            run = NEW / f"eval-{e}" / f"run-{r}"
            new_png = run / json.loads((run / "result.json").read_text(encoding="utf-8"))["final_png"]
            if (run / "rebuilt" / new_png.name).exists():  # 最終のエンジンで同じ定義から作り直した版 (run-1)
                new_png = run / "rebuilt" / new_png.name
            old_png = OLD / OLD_PNG[e].format(r=r)
            pair = [("old", old_png), ("new", new_png)]
            rng.shuffle(pair)
            out = BLIND / f"eval-{e}"
            out.mkdir(parents=True, exist_ok=True)
            for side, (who, src) in zip("ab", pair):
                shutil.copyfile(src, out / f"pair-{r}-{side}.png")
            key[f"eval-{e}/pair-{r}"] = {"a": pair[0][0], "b": pair[1][0]}
    keyf.write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(json.dumps(key, indent=2))


if __name__ == "__main__":
    main()
