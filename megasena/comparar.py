"""Prevê com dados até um concurso de corte e compara com os resultados reais que vieram depois.

Uso:
    python3 comparar.py --ate 3082 --alvos 3083 3084 3085
"""
import argparse
import json

from common import RESULTS, load
from prever import gerar_palpites


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ate", type=int, required=True, help="último concurso que os modelos podem ver")
    ap.add_argument("--alvos", type=int, nargs="+", required=True, help="concursos reais para comparar")
    args = ap.parse_args()
    assert min(args.alvos) > args.ate, "os concursos-alvo precisam ser posteriores ao corte"

    df = load()
    treino = df[df.concurso <= args.ate].reset_index(drop=True)
    palpites, _ = gerar_palpites(treino)

    reais = {}
    for c in args.alvos:
        r = df[df.concurso == c].iloc[0]
        reais[c] = {"data": r.data.strftime("%d/%m/%Y"), "dezenas": [int(r[f"d{i}"]) for i in range(1, 7)]}

    linhas = []
    for nome, jogo in palpites.items():
        por_concurso = {c: sorted(set(jogo) & set(v["dezenas"])) for c, v in reais.items()}
        linhas.append({"modelo": nome, "palpite": jogo,
                       "acertos": {str(c): {"qtd": len(a), "dezenas": a} for c, a in por_concurso.items()},
                       "media_acertos": round(sum(len(a) for a in por_concurso.values()) / len(reais), 3)})

    out = {"treino": f"concursos 1–{args.ate} (até {treino.data.iloc[-1].strftime('%d/%m/%Y')})",
           "n_concursos_treino": len(treino),
           "resultados_reais": {str(c): v for c, v in reais.items()},
           "acaso_esperado_por_concurso": 0.6,
           "comparacao": linhas}
    (RESULTS / f"comparacao_ate_{args.ate}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))

    print(out["treino"])
    for c, v in reais.items():
        print(f"  real {c} ({v['data']}): {' '.join(f'{d:02d}' for d in v['dezenas'])}")
    print()
    for l in linhas:
        ac = "  ".join(f"{c}: {a['qtd']} {a['dezenas'] or ''}" for c, a in l["acertos"].items())
        print(f"{l['modelo']:38s} {' '.join(f'{d:02d}' for d in l['palpite'])} | {ac} | média {l['media_acertos']}")


if __name__ == "__main__":
    main()
