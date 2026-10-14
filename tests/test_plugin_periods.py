# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Regressão do comando ``periods`` do plugin Typer."""

from __future__ import annotations

import datetime as dt

from typer.testing import CliRunner

from sidra_fetcher import plugin
from sidra_fetcher.agregados import Periodo


class _FakeClient:
    """Cliente sem rede: devolve períodos fixos."""

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get_agregado_periodos(self, agregado_id: int) -> list[Periodo]:
        return [
            Periodo(
                id="202401",
                literals=["janeiro 2024"],
                modificacao=dt.date(2024, 2, 9),
                frequencia="monthly",
            ),
            Periodo(
                id="2023",
                literals=["2023"],
                modificacao=dt.date(2024, 1, 5),
            ),
        ]


def test_periods_lista_literais_e_frequencia(monkeypatch) -> None:
    """``periods`` usa só atributos que ``Periodo`` expõe (não ``nome``)."""
    monkeypatch.setattr(plugin, "SidraClient", _FakeClient)
    result = CliRunner().invoke(plugin.app, ["periods", "1737"])
    assert result.exit_code == 0, result.output
    assert "202401" in result.output
    assert "janeiro 2024" in result.output
    assert "monthly" in result.output
    assert "2024-02-09" in result.output
