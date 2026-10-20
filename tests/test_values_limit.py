# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Regressão: limite de 50.000 valores por requisição da API SIDRA.

Em 2026-10-20 a API passou a responder HTTP 400 ("Quantidade de valores
solicitados: 55710 excedeu o limite: 50000") para consultas acima de 50.000
valores, enquanto o planejador ainda usava 100.000. Reprodução original:
``quantilica sidra sync 6579 --niveis N6 --periodos <10 anos>`` (5.571
municípios x 10 períodos = 55.710 valores num único request).
"""

from __future__ import annotations

import pytest
from quantilica.core.exceptions import FetchError
from quantilica.core.http import HttpStatusError
from test_download import _expand_chunk, _make_agregado
from typer.testing import CliRunner

from sidra_fetcher import plugin
from sidra_fetcher.download import plan_agregado_download
from sidra_fetcher.fetcher import SidraClient, SidraLimitError
from sidra_fetcher.sidra import SIDRA_API_VALUES_LIMIT

_MSG_LIMITE = "Quantidade de valores solicitados: 55710 excedeu o limite: 50000"


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeHttpxError(Exception):
    def __init__(self, text: str) -> None:
        super().__init__("400 Bad Request")
        self.response = _FakeResponse(text)


def _http_400(url: str, corpo: str) -> HttpStatusError:
    """Reproduz o encadeamento de ``HttpClient``: HttpStatusError from httpx."""
    try:
        try:
            raise _FakeHttpxError(corpo)
        except _FakeHttpxError as cause:
            raise HttpStatusError(url, 400) from cause
    except HttpStatusError as exc:
        return exc


def test_limite_e_50_mil() -> None:
    assert SIDRA_API_VALUES_LIMIT == 50_000


def test_caso_6579_n6_dez_periodos_divide_por_periodo() -> None:
    """5.571 localidades x 10 períodos = 55.710 > 50.000: divide por período."""
    agregado = _make_agregado(n_periodos=10, n_localidades=5571, nivel="N6")
    periodos = [p.id for p in agregado.periodos]
    chunks = plan_agregado_download(
        agregado, niveis_territoriais=["N6"], periodos=periodos
    )
    assert len(chunks) == 10
    assert all(c.n_valores == 5571 for c in chunks)
    assert all(c.n_valores <= SIDRA_API_VALUES_LIMIT for c in chunks)
    assert sorted(p for c in chunks for p in c.parametro.periodos) == periodos


def test_chunks_nunca_excedem_50_mil_e_cobrem_tudo() -> None:
    """Um único período grande cai no fatiamento por lote de localidades."""
    agregado = _make_agregado(
        n_periodos=1, n_localidades=600, n_variaveis=1, categoria_counts=[100]
    )  # 60.000 valores
    chunks = plan_agregado_download(agregado)
    assert len(chunks) > 1
    cobertos = set()
    for chunk in chunks:
        combos = _expand_chunk(chunk.parametro, agregado)
        assert len(combos) <= SIDRA_API_VALUES_LIMIT
        assert not (cobertos & combos)
        cobertos |= combos
    assert len(cobertos) == 60_000


def test_get_traduz_400_de_limite_em_sidra_limit_error(monkeypatch) -> None:
    url = "https://apisidra.ibge.gov.br/values/t/6579/n6/all/v/all/p/all"
    client = SidraClient()

    def _raise(_url: str):
        raise _http_400(url, _MSG_LIMITE)

    monkeypatch.setattr(client.client, "get_json", _raise)
    with pytest.raises(SidraLimitError) as info:
        client.get(url)
    msg = str(info.value)
    assert "excedeu o limite: 50000" in msg
    assert "--periodos" in msg
    assert isinstance(info.value, FetchError)


def test_get_outro_400_vira_fetch_error_com_corpo(monkeypatch) -> None:
    url = "https://apisidra.ibge.gov.br/values/t/1/n1/all"
    client = SidraClient()

    def _raise(_url: str):
        raise _http_400(url, "Tabela inexistente")

    monkeypatch.setattr(client.client, "get_json", _raise)
    with pytest.raises(FetchError) as info:
        client.get(url)
    assert not isinstance(info.value, SidraLimitError)
    assert "Tabela inexistente" in str(info.value)


class _FakeSyncClient:
    """Cliente sem rede para ``sync``: planeja de verdade, falha no download."""

    def __init__(self) -> None:
        self.agregado = _make_agregado(n_periodos=2, n_localidades=3, nivel="N6")

    def __enter__(self) -> _FakeSyncClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get_agregado(self, agregado_id: int):
        return self.agregado

    def plan_dados_agregado(self, agregado_id, *, agregado, **filtros):
        return plan_agregado_download(agregado, **filtros)

    def download_dados_agregado(self, *args, **kwargs):
        raise SidraLimitError(f"A API SIDRA recusou a consulta ({_MSG_LIMITE}).")


def test_sync_mostra_erro_de_limite_sem_traceback(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(plugin, "SidraClient", _FakeSyncClient)
    result = CliRunner().invoke(
        plugin.app, ["sync", "6579", "--niveis", "N6", "-o", str(tmp_path)]
    )
    assert result.exit_code == 1
    assert "Erro no download" in result.output
    assert "excedeu o limite: 50000" in result.output
    assert "Traceback" not in result.output
    assert not isinstance(result.exception, SidraLimitError)
