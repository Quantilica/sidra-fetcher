# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Round-trip tests for the agregado metadata JSON reader/writer pair."""

import datetime as dt
from pathlib import Path

from sidra_fetcher.agregados import (
    Agregado,
    AgregadoNivelTerritorial,
    Categoria,
    Classificacao,
    ClassificacaoSumarizacao,
    Localidade,
    NivelTerritorial,
    Periodicidade,
    Periodo,
    Pesquisa,
    Variavel,
)
from sidra_fetcher.reader import load_agregado, save_agregado


def _sample_agregado() -> Agregado:
    return Agregado(
        id=188,
        nome="Agregado de exemplo",
        url="https://servicodados.ibge.gov.br/api/v3/agregados/188",
        pesquisa=Pesquisa(id="5741", nome="Pesquisa de exemplo"),
        assunto="Produção agrícola",
        periodicidade=Periodicidade(frequencia="Anual", inicio="p0000", fim="p9999"),
        nivel_territorial=AgregadoNivelTerritorial(
            administrativo=["N1", "N2", "N3"], especial=[], ibge=[]
        ),
        variaveis=[
            Variavel(id="1", nome="Área plantada", unidade="Hectares", sumarizacao=[]),
            Variavel(
                id="4", nome="Quantidade produzida", unidade="Toneladas", sumarizacao=[]
            ),
        ],
        classificacoes=[
            Classificacao(
                id="15704",
                nome="Grão",
                sumarizacao=ClassificacaoSumarizacao(status=True, excecao=[0]),
                categorias=[
                    Categoria(id=0, nome="Total", unidade=None, nivel=0),
                    Categoria(id=1190, nome="Arroz", unidade=None, nivel=1),
                ],
            )
        ],
        periodos=[
            Periodo(
                id="A1974",
                literals=["1974"],
                modificacao=dt.date(2024, 5, 22),
                frequencia="anual",
                data_inicio=dt.date(1974, 1, 1),
                data_fim=dt.date(1974, 12, 31),
                ano=1974,
            )
        ],
        localidades=[
            Localidade(
                id="N1@1",
                nome="Brasil",
                nivel=NivelTerritorial(id="N1", nome="Brasil"),
            )
        ],
    )


def test_save_load_roundtrip(tmp_path: Path):
    """save_agregado -> load_agregado reproduz o mesmo Agregado."""
    agregado = _sample_agregado()
    path = tmp_path / "agregado_188.json"

    save_agregado(agregado, path)
    loaded = load_agregado(path)

    assert loaded == agregado


def test_save_load_roundtrip_writes_manifest(tmp_path: Path):
    """A carga não exige que o manifest esteja presente, mas save o grava."""
    agregado = _sample_agregado()
    path = tmp_path / "agregado.json"

    save_agregado(agregado, path)

    assert path.exists()
    assert path.with_suffix(path.suffix + ".manifest.json").exists()
    assert load_agregado(path) == agregado


def test_load_agregado_empty_collections(tmp_path: Path):
    """Agregados mínimos (sem periodos/localidades/classificacoes) round-tripam."""
    agregado = Agregado(
        id=99,
        nome="Mínimo",
        url="",
        pesquisa=Pesquisa(id="1", nome="P"),
        assunto="A",
        periodicidade=Periodicidade(frequencia="mensal", inicio="p0", fim="p0"),
        nivel_territorial=AgregadoNivelTerritorial(
            administrativo=[], especial=[], ibge=[]
        ),
        variaveis=[],
        classificacoes=[],
        periodos=[],
        localidades=[],
    )
    path = tmp_path / "min.json"

    save_agregado(agregado, path)

    assert load_agregado(path) == agregado
