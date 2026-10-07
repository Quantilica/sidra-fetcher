# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Testes de check_agregado (verificação sem download) e do rename sync."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from sidra_fetcher.agregados import Periodo
from sidra_fetcher.check import check_agregado
from sidra_fetcher.download import DownloadChunk
from sidra_fetcher.plugin import app

runner = CliRunner()


def _periodo(pid: str, dia: dt.date) -> Periodo:
    return Periodo(id=pid, literals=[pid], modificacao=dia)


def _agregado(periodos: list[Periodo], nome: str = "Agregado Fake") -> SimpleNamespace:
    return SimpleNamespace(
        id=1705, nome=nome, url="https://fake/1705", periodos=list(periodos)
    )


def _chunk(nivel: str, periodos: list[str]) -> DownloadChunk:
    return DownloadChunk(
        nivel_territorial=nivel,
        parametro=SimpleNamespace(periodos=list(periodos)),
        n_valores=len(periodos) or 1,
    )


class _FakeClient:
    """Dublê de SidraClient com metadados enlatados."""

    def __init__(self, agregado, chunks: list) -> None:
        self._agregado = agregado
        self._chunks = chunks

    def get_agregado(self, agregado_id: int):
        assert agregado_id == self._agregado.id
        return self._agregado

    def plan_dados_agregado(self, agregado_id: int, agregado=None, **filtros):
        assert filtros.get("niveis_territoriais") in (None, ["N1"], ["N3"])
        return list(self._chunks)


def _client_2niveis() -> _FakeClient:
    periodos = [
        _periodo("202301", dt.date(2023, 6, 1)),
        _periodo("202302", dt.date(2024, 2, 1)),
    ]
    agregado = _agregado(periodos)
    chunks = [_chunk("N1", ["202301", "202302"]), _chunk("N3", [])]
    return _FakeClient(agregado, chunks)


def test_check_tudo_ausente_baixa(tmp_path: Path) -> None:
    """Sem arquivos locais, todos os níveis são download/not-present."""
    veredictos, resumo = check_agregado(_client_2niveis(), 1705, tmp_path, {})
    assert resumo["n_niveis"] == 2
    assert [(v["partition"], v["action"], v["reason"]) for v in veredictos] == [
        ("N1", "download", "not-present"),
        ("N3", "download", "not-present"),
    ]
    assert veredictos[0]["remote_last_modified"] == "2024-02-01"
    assert veredictos[0]["entry"]["filtros"] == {}
    assert veredictos[0]["entry"]["nivel"] == "N1"


def test_check_nivel_fresco_pula(tmp_path: Path) -> None:
    """NDJSON mais novo que max(modificacao) gera skip-up-to-date."""
    veredictos, _ = check_agregado(_client_2niveis(), 1705, tmp_path, {})
    (tmp_path / "dados_N1.ndjson").write_text("{}\n", encoding="utf-8")
    veredictos, _ = check_agregado(_client_2niveis(), 1705, tmp_path, {})
    por_nivel = {v["partition"]: (v["action"], v["reason"]) for v in veredictos}
    assert por_nivel["N1"] == ("skip-up-to-date", "local-fresh")
    assert por_nivel["N3"] == ("download", "not-present")


def test_check_nivel_desatualizado_baixa(tmp_path: Path) -> None:
    """NDJSON mais antigo que max(modificacao) gera download/remote-newer."""
    alvo = tmp_path / "dados_N3.ndjson"
    alvo.write_text("{}\n", encoding="utf-8")
    antigo = dt.datetime(2020, 1, 1).timestamp()
    os.utime(alvo, (antigo, antigo))
    veredictos, _ = check_agregado(_client_2niveis(), 1705, tmp_path, {})
    por_nivel = {v["partition"]: (v["action"], v["reason"]) for v in veredictos}
    assert por_nivel["N3"] == ("download", "remote-newer")


def test_sync_e_download_produzem_mesmo_plano(monkeypatch, tmp_path: Path) -> None:
    """Alias depreciado delega ao sync (warning + mesmo comportamento)."""
    import sidra_fetcher.plugin as plugin_module

    client = _client_2niveis()
    monkeypatch.setattr(
        plugin_module, "SidraClient", lambda *a, **k: _NoNetClient(client)
    )
    r_sync = runner.invoke(app, ["sync", "1705", "-o", str(tmp_path), "--dry-run"])
    r_down = runner.invoke(app, ["download", "1705", "-o", str(tmp_path), "--dry-run"])
    assert r_sync.exit_code == 0, r_sync.output
    assert r_down.exit_code == 0, r_down.output
    assert "depreciado" in r_down.output
    assert "depreciado" not in r_sync.output


class _NoNetClient:
    """SidraClient fake sem rede para comandos Typer (plan + download vazio)."""

    def __init__(self, base: _FakeClient) -> None:
        self._base = base
        self.download_kwargs: dict = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def get_agregado(self, agregado_id: int):
        return self._base.get_agregado(agregado_id)

    def plan_dados_agregado(self, agregado_id: int, agregado=None, **filtros):
        return self._base.plan_dados_agregado(agregado_id, agregado=agregado, **filtros)

    def download_dados_agregado(self, agregado_id: int, output, **kwargs):
        self.download_kwargs = kwargs
        return []


def test_sync_from_plan_restringe_niveis(monkeypatch, tmp_path: Path) -> None:
    """sync --from-plan baixa só níveis com ação download."""
    import sidra_fetcher.plugin as plugin_module

    base = _client_2niveis()
    net = _NoNetClient(base)
    monkeypatch.setattr(plugin_module, "SidraClient", lambda *a, **k: net)

    veredictos, _ = check_agregado(base, 1705, tmp_path, {})
    plano = {
        "fetcher": "sidra-fetcher",
        "output_dir": str(tmp_path),
        "generated_at": "2026-10-07T00:00:00+00:00",
        "items": [
            {**v, "action": "skip-up-to-date", "reason": "local-fresh"}
            if v["partition"] == "N1"
            else v
            for v in veredictos
        ],
    }
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plano), encoding="utf-8")

    result = runner.invoke(
        app, ["sync", "1705", "-o", str(tmp_path), "--from-plan", str(plan_file)]
    )
    assert result.exit_code == 0, result.output
    assert net.download_kwargs.get("niveis_territoriais") == ["N3"]


def test_sync_from_plan_rejeita_filtros_combinados(monkeypatch, tmp_path: Path) -> None:
    """--from-plan com filtros explícitos aborta com erro claro."""
    import sidra_fetcher.plugin as plugin_module

    net = _NoNetClient(_client_2niveis())
    monkeypatch.setattr(plugin_module, "SidraClient", lambda *a, **k: net)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps({"items": []}), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "sync",
            "1705",
            "-o",
            str(tmp_path),
            "--from-plan",
            str(plan_file),
            "--niveis",
            "N1",
        ],
    )
    assert result.exit_code == 1
    assert "não combina com filtros" in result.output


def test_sync_from_plan_invalido_aborta(tmp_path: Path) -> None:
    """Plano inválido aborta com exit 1."""
    bad = tmp_path / "bad.json"
    bad.write_text('{"nao": "eh-plano"}', encoding="utf-8")
    result = runner.invoke(
        app, ["sync", "1705", "-o", str(tmp_path), "--from-plan", str(bad)]
    )
    assert result.exit_code == 1
    assert "Plano inválido" in result.output


def test_sync_sem_id_e_sem_plano_aborta(tmp_path: Path) -> None:
    """sync sem agregado e sem plano aborta com mensagem clara."""
    result = runner.invoke(app, ["sync", "-o", str(tmp_path)])
    assert result.exit_code == 1
    assert "informe o ID" in result.output


def test_check_json_tem_ids_completos(monkeypatch, tmp_path: Path) -> None:
    """check --json emite plano com ids sem truncamento."""
    import sidra_fetcher.plugin as plugin_module

    net = _NoNetClient(_client_2niveis())
    monkeypatch.setattr(plugin_module, "SidraClient", lambda *a, **k: net)
    result = runner.invoke(app, ["check", "1705", "-o", str(tmp_path), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert [it["id"] for it in data["items"]] == [
        "dados_N1.ndjson",
        "dados_N3.ndjson",
    ]
