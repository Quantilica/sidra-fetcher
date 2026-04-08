from sidra_fetcher.reader import read_periodos, load_agregado
import json
from pathlib import Path

path = Path("../ibge-sidra-tabelas/data")

for f in path.glob("**/metadados.json"):
    data = json.loads(f.read_text(encoding="utf-8"))
    periodos = read_periodos(data["periodos"])
    for p in periodos:
        if p.frequencia != "mensal":
            print(p.id, p.frequencia, p.data_inicio, p.data_fim)
