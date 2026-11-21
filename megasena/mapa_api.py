"""Mapa de tudo que a API da Caixa entrega e das correlações entre essas informações.

Lê data/megasena_raw.jsonl.gz (resposta completa de cada concurso) e gera:
  results/mapa_api_campos.csv        dicionário de dados: os 32 campos, tipo, cobertura, distintos
  data/megasena_completo.csv         uma linha por concurso: campos da API + variáveis derivadas
  results/mapa_api_correlacoes.csv   todos os pares de variáveis numéricas (Spearman bruto e sem tempo)
  results/mapa_api_resumo.json       respostas às perguntas (a), (b) e (c) do plano

"Sem tempo" = correlação parcial de Spearman controlando o nº do concurso (polinômio cúbico), porque
preço da aposta, arrecadação e prêmios sobem juntos ao longo dos anos.
"""
import gzip
import json
import re

import numpy as np
import pandas as pd
from scipy import stats

from common import RESULTS, ROOT

RAW = ROOT / "data" / "megasena_raw.jsonl.gz"
NUMS = np.arange(1, 61)
LINHA, COLUNA = (NUMS - 1) // 10, (NUMS - 1) % 10
QUAD = (LINHA >= 3) * 2 + (COLUNA >= 5)
PRIMOS = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59}
GRUPOS = {
    "sorteio": ["listaDezenas", "dezenasSorteadasOrdemSorteio"],
    "calendario": ["numero", "dataApuracao", "dataProximoConcurso", "indicadorConcursoEspecial",
                   "numeroConcursoFinal_0_5", "numeroConcursoAnterior", "numeroConcursoProximo"],
    "ganhadores_e_premios": ["listaRateioPremio"],
    "dinheiro": ["valorArrecadado", "acumulado", "valorAcumuladoProximoConcurso", "valorEstimadoProximoConcurso",
                 "valorAcumuladoConcurso_0_5", "valorAcumuladoConcursoEspecial"],
    "local_do_sorteio": ["localSorteio", "nomeMunicipioUFSorteio"],
    "onde_saiu_a_sena": ["listaMunicipioUFGanhadores"],
    "texto_livre": ["observacao"],
}
GRUPO_DE = {c: g for g, cs in GRUPOS.items() for c in cs}


def vazio(v):
    return v is None or v == "" or v == [] or (isinstance(v, str) and not v.strip("\x00 "))


def dicionario(rows):
    linhas = []
    for campo in rows[-1]:
        vals = [r.get(campo) for r in rows]
        cheios = [v for v in vals if not vazio(v)]
        distintos = len({json.dumps(v, sort_keys=True, ensure_ascii=False) for v in vals})
        ex = json.dumps(cheios[-1], ensure_ascii=False)[:80] if cheios else ""
        linhas.append({"campo": campo, "grupo": GRUPO_DE.get(campo, "constante_ou_vazio"),
                       "tipo": "/".join(sorted({type(v).__name__ for v in vals if v is not None})) or "null",
                       "preenchidos": len(cheios), "cobertura_pct": round(len(cheios) / len(rows) * 100, 1),
                       "valores_distintos": distintos, "varia": distintos > 1, "exemplo": ex})
    return pd.DataFrame(linhas)


def tipo_local(s):
    s = (s or "").upper()
    if "CAMINH" in s:
        return "caminhao"
    if "ESPA" in s:
        return "espaco_da_sorte"
    if "AUDIT" in s:
        return "auditorio"
    return "outro" if s.strip() else "nao_informado"


def tabela(rows):
    out = []
    seguidos = 0
    for r in rows:
        dez = np.array(sorted(int(x) for x in r["listaDezenas"]))
        ordem = [int(x) for x in r["dezenasSorteadasOrdemSorteio"]]
        fx = {f["faixa"]: f for f in r["listaRateioPremio"]}
        i = dez - 1
        muni = r.get("nomeMunicipioUFSorteio") or ""
        uf = muni.split(",")[-1].strip().upper() if "," in muni else ""
        gan = r.get("listaMunicipioUFGanhadores") or []
        zero_nan = lambda v: np.nan if not v else v
        linha = {
            # --- campos diretos da API
            "concurso": r["numero"], "data": r["dataApuracao"], "data_proximo": r.get("dataProximoConcurso"),
            "concurso_especial": int(r["indicadorConcursoEspecial"] == 2),
            "concurso_final_0_5": r.get("numeroConcursoFinal_0_5"),
            "acumulou": int(bool(r.get("acumulado"))),
            "arrecadacao": zero_nan(r.get("valorArrecadado")),
            "acumulado_proximo": r.get("valorAcumuladoProximoConcurso"),
            "estimativa_proximo": zero_nan(r.get("valorEstimadoProximoConcurso")),
            "acumulado_final_0_5": r.get("valorAcumuladoConcurso_0_5"),
            "acumulado_especial": r.get("valorAcumuladoConcursoEspecial"),
            "ganhadores_sena": fx[1]["numeroDeGanhadores"], "premio_sena": zero_nan(fx[1]["valorPremio"]),
            "ganhadores_quina": fx[2]["numeroDeGanhadores"], "premio_quina": zero_nan(fx[2]["valorPremio"]),
            "ganhadores_quadra": fx[3]["numeroDeGanhadores"], "premio_quadra": zero_nan(fx[3]["valorPremio"]),
            "local_sorteio": r.get("localSorteio") or "", "municipio_sorteio": muni,
            "cidades_com_sena": len(gan), "ufs_com_sena": " ".join(sorted({g.get("uf", "") for g in gan})),
            "tem_observacao": int(not vazio(r.get("observacao"))),
            "time_coracao_preenchido": int(r.get("nomeTimeCoracaoMesSorte") not in (None, "")),
            # --- campos constantes ou vazios (mantidos a pedido)
            **{f"api_{c}": json.dumps(r.get(c), ensure_ascii=False) for c in
               ("id", "tipoJogo", "numeroJogo", "tipoPublicacao", "ultimoConcurso", "listaDezenasSegundoSorteio",
                "listaResultadoEquipeEsportiva", "premiacaoContingencia", "valorSaldoReservaGarantidora",
                "valorTotalPremioFaixaUm", "exibirDetalhamentoPorCidade")},
            # --- dezenas
            **{f"d{k + 1}": int(v) for k, v in enumerate(dez)}, **{f"o{k + 1}": v for k, v in enumerate(ordem)},
            "soma": int(dez.sum()), "pares": int((dez % 2 == 0).sum()), "primos": int(sum(d in PRIMOS for d in dez)),
            "ate_31": int((dez <= 31).sum()), "consecutivas": int((np.diff(dez) == 1).sum()),
            "amplitude": int(dez[-1] - dez[0]), "menor": int(dez[0]), "maior": int(dez[-1]),
            "max_mesma_linha": int(np.bincount(LINHA[i], minlength=6).max()),
            "max_mesma_coluna": int(np.bincount(COLUNA[i], minlength=10).max()),
            "linhas_distintas": int(len(set(LINHA[i]))), "multiplos_de_5": int((dez % 5 == 0).sum()),
            **{f"quadrante_{q + 1}": int((QUAD[i] == q).sum()) for q in range(4)},
            # --- local
            "tipo_local": tipo_local(r.get("localSorteio")), "uf_sorteio": uf,
            "concursos_acumulados_seguidos": seguidos,
        }
        seguidos = seguidos + 1 if r.get("acumulado") else 0
        out.append(linha)
    df = pd.DataFrame(out)
    dt = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["ano"], df["mes"], df["dia_semana"] = dt.dt.year, dt.dt.month, dt.dt.dayofweek
    df["dias_desde_anterior"] = dt.diff().dt.days
    df["mega_da_virada"] = ((dt.dt.month == 12) & (dt.dt.day == 31) | (dt.dt.month == 1) & (dt.dt.day == 1)).astype(int) \
        * df["concurso_especial"]
    df["final_0_ou_5"] = (df["concurso"] % 5 == 0).astype(int)
    df["bolo_quadra"] = df["ganhadores_quadra"] * df["premio_quadra"]       # total pago à faixa (∝ arrecadação)
    df["bolo_quina"] = df["ganhadores_quina"] * df["premio_quina"]
    df["quadras_por_milhao_arrecadado"] = df["ganhadores_quadra"] / df["arrecadacao"] * 1e6
    df["quinas_por_milhao_arrecadado"] = df["ganhadores_quina"] / df["arrecadacao"] * 1e6
    df["estimativa_recebida"] = df["estimativa_proximo"].shift(1)            # estimativa divulgada para ESTE concurso
    df["acumulado_recebido"] = df["acumulado_proximo"].shift(1)              # valor que veio acumulado para este
    return df


def bh(p):
    """q-valores de Benjamini-Hochberg."""
    p = np.asarray(p, float)
    ok = ~np.isnan(p)
    q = np.full(len(p), np.nan)
    o = np.argsort(p[ok])
    r = p[ok][o] * ok.sum() / (np.arange(ok.sum()) + 1)
    r = np.minimum.accumulate(r[::-1])[::-1]
    q[np.flatnonzero(ok)[o]] = np.minimum(r, 1)
    return q


def residuo_tempo(v, t):
    """Postos de v sem a tendência de tempo (polinômio cúbico do nº do concurso)."""
    ok = ~np.isnan(v)
    r = np.full(len(v), np.nan)
    if ok.sum() < 30:
        return r
    rk = stats.rankdata(v[ok])
    tt = (t[ok] - t.mean()) / t.std()
    X = np.c_[np.ones(ok.sum()), tt, tt ** 2, tt ** 3]
    r[ok] = rk - X @ np.linalg.lstsq(X, rk, rcond=None)[0]
    return r


def correlacoes(df, cols):
    t = df["concurso"].values.astype(float)
    res = {c: residuo_tempo(df[c].values.astype(float), t) for c in cols}
    linhas = []
    for a in range(len(cols)):
        for b in range(a + 1, len(cols)):
            x, y = df[cols[a]].values.astype(float), df[cols[b]].values.astype(float)
            ok = ~np.isnan(x) & ~np.isnan(y)
            n = int(ok.sum())
            lin = {"var_a": cols[a], "var_b": cols[b], "n": n, "spearman": np.nan, "spearman_sem_tempo": np.nan,
                   "p_sem_tempo": np.nan, "obs": ""}
            if n < 30 or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
                lin["obs"] = "sem variação" if n >= 30 else "poucos dados"
            else:
                lin["spearman"] = stats.spearmanr(x[ok], y[ok])[0]
                ra, rb = res[cols[a]][ok], res[cols[b]][ok]
                if np.ptp(ra) > 0 and np.ptp(rb) > 0:
                    lin["spearman_sem_tempo"], lin["p_sem_tempo"] = stats.pearsonr(ra, rb)
            linhas.append(lin)
    c = pd.DataFrame(linhas)
    c["q_sem_tempo"] = bh(c["p_sem_tempo"].values)
    return c


def main():
    rows = [json.loads(l) for l in gzip.open(RAW, "rt", encoding="utf-8")]
    campos = dicionario(rows)
    campos.to_csv(RESULTS / "mapa_api_campos.csv", index=False)
    df = tabela(rows)
    df.to_csv(ROOT / "data" / "megasena_completo.csv", index=False)
    n = len(df)
    resumo = {"concursos": n, "campos_api": len(campos), "campos_que_variam": int(campos.varia.sum()),
              "colunas_tabela_completa": df.shape[1]}

    # ---------------- matriz geral
    constantes = [c for c in df.columns if c.startswith("api_")]
    numericas = [c for c in df.columns if c not in constantes and pd.api.types.is_numeric_dtype(df[c])
                 and not re.fullmatch(r"[do]\d", c) and c not in ("concurso", "concurso_final_0_5")]
    for c in constantes:                      # entram na matriz, mas não têm variação
        df[c + "_cod"] = pd.factorize(df[c])[0].astype(float)
    cols = numericas + [c + "_cod" for c in constantes]
    corr = correlacoes(df, cols)
    corr.round(4).to_csv(RESULTS / "mapa_api_correlacoes.csv", index=False)
    val = corr.dropna(subset=["spearman_sem_tempo"])
    resumo["pares_testados"] = len(val)
    resumo["pares_sem_variacao"] = int((corr.obs == "sem variação").sum())
    resumo["pares_significativos_q<0.01"] = int((val.q_sem_tempo < 0.01).sum())
    forte = val.reindex(val.spearman_sem_tempo.abs().sort_values(ascending=False).index)
    resumo["mais_fortes_sem_tempo"] = forte.head(40)[["var_a", "var_b", "n", "spearman", "spearman_sem_tempo"]] \
        .round(3).to_dict("records")

    # ---------------- (a) algo se correlaciona com QUAIS dezenas saem?
    M = np.zeros((n, 60))
    M[np.arange(n)[:, None], df[[f"d{k}" for k in range(1, 7)]].values - 1] = 1
    t = df["concurso"].values.astype(float)
    contexto = ["arrecadacao", "estimativa_recebida", "acumulado_recebido", "concursos_acumulados_seguidos",
                "dias_desde_anterior", "dia_semana", "mes", "ano", "concurso_especial", "final_0_ou_5",
                "tem_observacao", "time_coracao_preenchido"]
    pa = []
    for c in contexto:
        v = df[c].values.astype(float)
        ok = ~np.isnan(v)
        for j in range(60):
            r, p = stats.spearmanr(v[ok], M[ok, j])
            pa.append({"contexto": c, "numero": j + 1, "r": r, "p": p})
    for c in ("tipo_local", "uf_sorteio", "dia_semana"):
        g = df[c].astype(str)
        g = g.where(g.map(g.value_counts()) >= 40, "outros")
        for j in range(60):
            tab = pd.crosstab(g, M[:, j])
            pa.append({"contexto": c + " (qui²)", "numero": j + 1, "r": np.nan, "p": stats.chi2_contingency(tab)[1]})
    pa = pd.DataFrame(pa)
    pa["q"] = bh(pa.p.values)
    resumo["a_contexto_x_dezenas"] = {
        "testes": len(pa), "p<0.05": int((pa.p < 0.05).sum()), "esperado_por_acaso": round(len(pa) * 0.05, 1),
        "significativos_apos_correcao_q<0.05": int((pa.q < 0.05).sum()),
        "maior_|r|": round(float(pa.r.abs().max()), 4),
        "menores_p": pa.nsmallest(5, "p").round(4).to_dict("records")}

    # ---------------- (b) as dezenas sorteadas se correlacionam com quantos ganham / valor do prêmio?
    # log do prêmio da quadra, tirando a média de cada bloco de 25 concursos (absorve preço e regras)
    comuns = df["concurso_especial"].values == 0
    bloco = (np.arange(n) // 25)
    def dentro(v):
        s = pd.Series(v)
        return (s - s.groupby(bloco).transform("mean")).values
    pb = {}
    for faixa in ("quadra", "quina"):
        y = dentro(np.log(df[f"premio_{faixa}"].values))
        ok = comuns & ~np.isnan(y)
        X = np.column_stack([dentro(M[:, j]) for j in range(60)])[ok]
        beta = np.linalg.lstsq(X[:, :59], y[ok], rcond=None)[0]           # 60ª é combinação das outras
        pred = X[:, :59] @ beta
        r2 = 1 - ((y[ok] - pred) ** 2).sum() / ((y[ok] - y[ok].mean()) ** 2).sum()
        ef = np.array([stats.pearsonr(X[:, j], y[ok])[0] for j in range(60)])
        # fora da amostra: ajusta nos primeiros 80% e prevê os últimos 20%
        k = int(ok.sum() * 0.8)
        b2 = np.linalg.lstsq(X[:k, :59], y[ok][:k], rcond=None)[0]
        r_fora = stats.pearsonr(X[k:, :59] @ b2, y[ok][k:])[0]
        deriv = {c: round(float(stats.pearsonr(dentro(df[c].values.astype(float))[ok], y[ok])[0]), 3)
                 for c in ("ate_31", "soma", "menor", "maior", "consecutivas", "pares", "primos", "multiplos_de_5",
                           "max_mesma_linha", "max_mesma_coluna", "amplitude")}
        pb[faixa] = {"r2_dentro_da_amostra": round(float(r2), 3), "correlacao_fora_da_amostra": round(float(r_fora), 3),
                     "numeros_que_mais_baixam_o_premio": [(int(j + 1), round(float(ef[j]), 3)) for j in np.argsort(ef)[:10]],
                     "numeros_que_mais_sobem_o_premio": [(int(j + 1), round(float(ef[j]), 3)) for j in np.argsort(-ef)[:10]],
                     "correlacao_media_numeros_ate_31": round(float(ef[:31].mean()), 3),
                     "correlacao_media_numeros_acima_31": round(float(ef[31:].mean()), 3),
                     "derivadas_x_log_premio": deriv}
        if faixa == "quadra":
            df["efeito_popularidade"] = np.nan
            df.loc[ok, "efeito_popularidade"] = -pred
    # ganhadores da sena: mais ganhadores quando saem dezenas populares?
    ok = comuns & df["efeito_popularidade"].notna().values
    tercil = pd.qcut(df.loc[ok, "efeito_popularidade"], 3, labels=["impopulares", "medianas", "populares"])
    pb["sena_por_popularidade_das_dezenas"] = {
        k: {"concursos": int(v.size), "com_ganhador_pct": round(float((v > 0).mean() * 100), 1),
            "ganhadores_por_concurso": round(float(v.mean()), 3)}
        for k, v in df.loc[ok, "ganhadores_sena"].groupby(tercil, observed=True)}
    resumo["b_dezenas_x_premios"] = pb

    # ---------------- (c) o que explica arrecadação e nº de ganhadores?
    alvo = ["arrecadacao", "ganhadores_quadra", "ganhadores_quina", "ganhadores_sena", "premio_quadra", "premio_quina"]
    pc = {}
    for a in alvo:
        s = val[(val.var_a == a) | (val.var_b == a)].copy()
        s["outra"] = np.where(s.var_a == a, s.var_b, s.var_a)
        s = s.reindex(s.spearman_sem_tempo.abs().sort_values(ascending=False).index).head(8)
        pc[a] = [(o, round(float(r), 3)) for o, r in zip(s.outra, s.spearman_sem_tempo)]
    eta = {}
    for cat in ("tipo_local", "dia_semana", "uf_sorteio"):
        g = df[cat].astype(str)
        g = g.where(g.map(g.value_counts()) >= 40, "outros")
        for a in ("arrecadacao", "ganhadores_quadra", "soma"):
            r = residuo_tempo(df[a].values.astype(float), t)
            ok = ~np.isnan(r)
            grupos = [r[ok & (g == k).values] for k in g.unique()]
            grupos = [x for x in grupos if len(x) > 5]
            tot = np.concatenate(grupos)
            e2 = sum(len(x) * (x.mean() - tot.mean()) ** 2 for x in grupos) / ((tot - tot.mean()) ** 2).sum()
            eta[f"{cat} -> {a}"] = {"eta2": round(float(e2), 4), "p": round(float(stats.kruskal(*grupos)[1]), 4)}
    resumo["c_o_que_explica"] = {"correlacoes_sem_tempo": pc, "categoricas_eta2": eta}

    (RESULTS / "mapa_api_resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False, default=str))
    pd.set_option("display.width", 220)
    print(campos.drop(columns="exemplo").to_string(index=False))
    print(json.dumps(resumo, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
