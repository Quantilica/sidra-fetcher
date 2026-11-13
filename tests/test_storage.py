# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Testes para DataRepository do ibge-sidra-fetcher."""

import json
from pathlib import Path

from ibge_sidra_fetcher.storage import DataRepository


def test_data_repository_paths(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    assert repo.source_id == "sidra"

    p_agregado = repo.path_agregado(1705)
    assert p_agregado == tmp_path / "agregados" / "agregado_1705.json"

    p_indice = repo.path_indice()
    assert p_indice == tmp_path / "agregados" / "indice_pesquisas.json"

    p_dados = repo.path_dados(1705, "N1")
    assert p_dados == tmp_path / "agregados" / "1705" / "dados_N1.ndjson"


def test_data_repository_write_manifest(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    file_path = repo.path_dados(1705, "N1")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    content = b'{"col": "val"}\n'
    file_path.write_bytes(content)

    manifest_path = repo.write_manifest_for(
        file_path,
        dataset_id="1705:N1",
        url="https://servicodados.ibge.gov.br/api/v3/agregados/1705",
        content=content,
        metadata={"nivel": "N1"},
    )
    assert manifest_path.exists()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["source_id"] == "sidra"
    assert payload["dataset_id"] == "1705:N1"
    assert payload["size_bytes"] == len(content)


def test_path_for_entry_maps_to_existing_layout(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)

    assert repo.path_for_entry({"id": 1705}) == repo.path_agregado(1705)
    assert repo.path_for_entry(
        {"id": 1705, "nivel_territorial": "N1"}
    ) == repo.path_dados(1705, "N1")
