"""Baixa o clima de cada sorteio (cidade e data do concurso) da Open-Meteo e salva data/megasena_clima.csv.

Para cada concurso com cidade informada: geocodifica a cidade e busca, no arquivo histórico, o clima das
20h locais (hora aproximada do sorteio): temperatura, umidade, pressão, chuva na hora, além de chuva do
dia, máxima, mínima e o código da condição do tempo (WMO). O download é incremental (cache em JSON).
"""
import json
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from common import ROOT

CACHE = ROOT / "data" / "clima_cache.json"
OUT = ROOT / "data" / "megasena_clima.csv"
HORA = 20
UFS = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
       "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
       "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
       "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
       "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
       "SE": "Sergipe", "TO": "Tocantins"}


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower().strip()


def get(url):
    for tent in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "python"}), timeout=40) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(4 * (tent + 1) if "429" in str(e) else 1.5)
    return None


def condicao(c):
    if c is None:
        return ""
    if c <= 1:
        return "ensolarado"
    if c <= 3:
        return "nublado"
    if c in (45, 48):
        return "neblina"
    if c >= 95:
        return "tempestade"
    return "chuva"


def main():
    comp = pd.read_csv(ROOT / "data" / "megasena_completo.csv", usecols=["concurso", "data", "municipio_sorteio", "uf_sorteio"])
    comp["dia"] = pd.to_datetime(comp["data"], format="%d/%m/%Y").dt.strftime("%Y-%m-%d")
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {"geo": {}, "clima": {}}
    geo, clima = cache["geo"], cache["clima"]
    comp = comp[comp.municipio_sorteio.notna() & (comp.municipio_sorteio.str.strip() != "")]

    # 1) coordenadas de cada cidade
    for muni in sorted(comp.municipio_sorteio.unique()):
        if muni in geo:
            continue
        nome, _, uf = muni.rpartition(",")
        nome, uf = nome.strip() or muni, uf.strip().upper()
        r = get("https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
            {"name": nome.title(), "count": 10, "country": "BR", "language": "pt"}))
        achou = None
        for x in (r or {}).get("results", []) or []:
            if sem_acento(x.get("admin1", "")) == sem_acento(UFS.get(uf, "")):
                achou = x
                break
        geo[muni] = [achou["latitude"], achou["longitude"]] if achou else None
        time.sleep(0.25)
    CACHE.write_text(json.dumps(cache))
    print("cidades:", len(geo), "sem coordenada:", sum(v is None for v in geo.values()), file=sys.stderr, flush=True)

    # 2) clima por cidade: uma chamada por cidade e por ano
    comp["ano"] = comp.dia.str[:4]
    feitos = 0
    for (muni, ano), g in comp.groupby(["municipio_sorteio", "ano"]):
        if geo.get(muni) is None or all(f"{c}" in clima for c in g.concurso):
            continue
        lat, lon = geo[muni]
        r = get("https://archive-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode({
            "latitude": lat, "longitude": lon, "start_date": g.dia.min(), "end_date": g.dia.max(),
            "hourly": "temperature_2m,relative_humidity_2m,surface_pressure,precipitation,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
            "timezone": "America/Sao_Paulo"}))
        if r is None or "hourly" not in r:
            continue
        hi = {t: i for i, t in enumerate(r["hourly"]["time"])}
        di = {t: i for i, t in enumerate(r["daily"]["time"])}
        for c, dia in zip(g.concurso, g.dia):
            i, j = hi.get(f"{dia}T{HORA:02d}:00"), di.get(dia)
            if i is None or j is None:
                continue
            h, d = r["hourly"], r["daily"]
            clima[f"{c}"] = {"temperatura_c": h["temperature_2m"][i], "umidade_pct": h["relative_humidity_2m"][i],
                             "pressao_hpa": h["surface_pressure"][i], "chuva_hora_mm": h["precipitation"][i],
                             "vento_kmh": h["wind_speed_10m"][i], "temp_max_c": d["temperature_2m_max"][j],
                             "temp_min_c": d["temperature_2m_min"][j], "chuva_dia_mm": d["precipitation_sum"][j],
                             "codigo_wmo": d["weather_code"][j], "condicao": condicao(d["weather_code"][j]),
                             "lat": lat, "lon": lon}
        feitos += 1
        if feitos % 50 == 0:
            CACHE.write_text(json.dumps(cache))
            print("chamadas:", feitos, "concursos com clima:", len(clima), file=sys.stderr, flush=True)
        time.sleep(0.8)
    CACHE.write_text(json.dumps(cache))
    tab = pd.DataFrame([{"concurso": int(c), **v} for c, v in clima.items()]).sort_values("concurso")
    tab.to_csv(OUT, index=False)
    print(f"salvo {len(tab)} concursos com clima em {OUT}")
    print(tab.condicao.value_counts().to_dict())


if __name__ == "__main__":
    main()
