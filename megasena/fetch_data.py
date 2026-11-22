"""Baixa todos os resultados da Mega-Sena da API oficial da Caixa.

Guarda a resposta COMPLETA de cada concurso em data/megasena_raw.jsonl.gz (uma linha JSON por concurso)
e gera dois CSVs derivados dela:
  data/megasena.csv          dezenas (ordenadas e na ordem do sorteio)
  data/megasena_premios.csv  arrecadação, ganhadores e prêmio por faixa, local do sorteio
O download é incremental: só busca os concursos que ainda não estão no arquivo bruto.
"""
import csv, gzip, json, ssl, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/"
DATA = Path(__file__).parent / "data"
RAW, OUT, PREMIOS = DATA / "megasena_raw.jsonl.gz", DATA / "megasena.csv", DATA / "megasena_premios.csv"
CTX = ssl.create_default_context()


def get(n=""):
    for attempt in range(6):
        try:
            req = urllib.request.Request(f"{BASE}{n}", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                return json.load(r)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"falhou concurso {n}")


def linha_dezenas(d):
    dez = sorted(int(x) for x in d["listaDezenas"])
    ordem = [int(x) for x in (d.get("dezenasSorteadasOrdemSorteio") or d["listaDezenas"])]
    return {"concurso": d["numero"], "data": d["dataApuracao"],
            **{f"d{i+1}": v for i, v in enumerate(dez)},
            **{f"o{i+1}": v for i, v in enumerate(ordem)},
            "acumulado": d.get("acumulado")}


def linha_premios(d):
    faixas = {f["faixa"]: f for f in (d.get("listaRateioPremio") or [])}
    g = lambda fx, campo: faixas.get(fx, {}).get(campo)
    return {"concurso": d["numero"], "data": d["dataApuracao"],
            "arrecadacao": d.get("valorArrecadado"),
            "ganhadores_sena": g(1, "numeroDeGanhadores"), "premio_sena": g(1, "valorPremio"),
            "ganhadores_quina": g(2, "numeroDeGanhadores"), "premio_quina": g(2, "valorPremio"),
            "ganhadores_quadra": g(3, "numeroDeGanhadores"), "premio_quadra": g(3, "valorPremio"),
            "acumulado": d.get("acumulado"), "acumulado_proximo": d.get("valorAcumuladoProximoConcurso"),
            "concurso_especial": d.get("indicadorConcursoEspecial"),
            "local_sorteio": d.get("localSorteio"), "municipio_uf": d.get("nomeMunicipioUFSorteio")}


def escreve_csv(caminho, linhas):
    with caminho.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[-1].keys()))
        w.writeheader(); w.writerows(linhas)


def main():
    brutos = {}
    if RAW.exists():
        with gzip.open(RAW, "rt", encoding="utf-8") as f:
            brutos = {d["numero"]: d for d in map(json.loads, f)}
    ultimo = get()["numero"]
    faltam = [n for n in range(1, ultimo + 1) if n not in brutos]
    print(f"último concurso: {ultimo}; baixando {len(faltam)}", file=sys.stderr)
    with ThreadPoolExecutor(8) as ex:
        for d in ex.map(get, faltam):
            brutos[d["numero"]] = d
    todos = [brutos[k] for k in sorted(brutos)]
    with gzip.open(RAW, "wt", encoding="utf-8") as f:
        for d in todos:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    escreve_csv(OUT, [linha_dezenas(d) for d in todos])
    escreve_csv(PREMIOS, [linha_premios(d) for d in todos])
    print(f"salvo {len(todos)} concursos em {RAW.name}, {OUT.name} e {PREMIOS.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
