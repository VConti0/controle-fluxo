"""Baixa todos os resultados da Mega-Sena da API oficial da Caixa e salva em data/megasena.csv."""
import csv, json, ssl, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/"
OUT = Path(__file__).parent / "data" / "megasena.csv"
CTX = ssl.create_default_context()

def get(n=""):
    for attempt in range(6):
        try:
            req = urllib.request.Request(f"{BASE}{n}", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"falhou concurso {n}")

def row(d):
    dez = sorted(int(x) for x in d["listaDezenas"])
    ordem = [int(x) for x in (d.get("dezenasSorteadasOrdemSorteio") or d["listaDezenas"])]
    return {"concurso": d["numero"], "data": d["dataApuracao"],
            **{f"d{i+1}": v for i, v in enumerate(dez)},
            **{f"o{i+1}": v for i, v in enumerate(ordem)},
            "acumulado": d.get("acumulado")}

def main():
    last = get()["numero"]
    existing = {}
    if OUT.exists():
        with OUT.open() as f:
            existing = {int(r["concurso"]): r for r in csv.DictReader(f)}
    todo = [n for n in range(1, last + 1) if n not in existing]
    print(f"último concurso: {last}; baixando {len(todo)}", file=sys.stderr)
    with ThreadPoolExecutor(8) as ex:
        for r in ex.map(lambda n: row(get(n)), todo):
            existing[r["concurso"]] = r
    rows = [existing[k] for k in sorted(existing)]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[-1].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"salvo {len(rows)} concursos em {OUT}", file=sys.stderr)

if __name__ == "__main__":
    main()
