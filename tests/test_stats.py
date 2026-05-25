# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

import unittest
from unittest.mock import Mock

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
from sidra_fetcher.stats import (
    calculate_aggregate,
    get_n_dimensoes,
    get_stat_localidades,
)


class TestStats(unittest.TestCase):
    def create_dummy_agregado(self):
        # Helper to create a populated Agregado object
        return Agregado(
            id=123,
            nome="Agregado Teste",
            url="http://url",
            pesquisa=Pesquisa(id="P1", nome="Pesquisa 1"),
            assunto="Assunto",
            periodicidade=Periodicidade(
                frequencia="mensal", inicio="202001", fim="202012"
            ),
            nivel_territorial=AgregadoNivelTerritorial(
                administrativo=["N1"], especial=[], ibge=[]
            ),
            variaveis=[
                Variavel(id=1, nome="V1", unidade="u", sumarizacao=[]),
                Variavel(id=2, nome="V2", unidade="u", sumarizacao=[]),
            ],
            classificacoes=[
                Classificacao(
                    id=1,
                    nome="C1",
                    sumarizacao=ClassificacaoSumarizacao(status=True, excecao=[]),
                    categorias=[
                        Categoria(id=10, nome="Cat1", unidade=None, nivel=1),
                        Categoria(id=11, nome="Cat2", unidade=None, nivel=1),
                    ],
                ),
                Classificacao(
                    id=2,
                    nome="C2",
                    sumarizacao=ClassificacaoSumarizacao(status=True, excecao=[]),
                    categorias=[
                        Categoria(id=20, nome="Cat3", unidade=None, nivel=1),
                        Categoria(id=21, nome="Cat4", unidade=None, nivel=1),
                        Categoria(id=22, nome="Cat5", unidade=None, nivel=1),
                    ],
                ),
            ],
            periodos=[
                Periodo(id="202001", literals=[], modificacao=Mock()),
                Periodo(id="202002", literals=[], modificacao=Mock()),
            ],
            localidades=[
                Localidade(
                    id="1",
                    nome="Loc1",
                    nivel=NivelTerritorial(id="N1", nome="Nivel 1"),
                ),
                Localidade(
                    id="2",
                    nome="Loc2",
                    nivel=NivelTerritorial(id="N1", nome="Nivel 1"),
                ),
                Localidade(
                    id="3",
                    nome="Loc3",
                    nivel=NivelTerritorial(id="N2", nome="Nivel 2"),
                ),
            ],
        )

    def test_get_stat_localidades(self):
        agregado = self.create_dummy_agregado()
        stats = get_stat_localidades(agregado)
        # We have 2 localities in N1 and 1 in N2
        self.assertEqual(stats, {"N1": 2, "N2": 1})

    def test_get_n_dimensoes(self):
        agregado = self.create_dummy_agregado()
        # C1 has 2 categories, C2 has 3. Total dimensions = 2 * 3 = 6
        n_dim = get_n_dimensoes(agregado)
        self.assertEqual(n_dim, 6)

    def test_calculate_aggregate(self):
        agregado = self.create_dummy_agregado()
        result = calculate_aggregate(agregado)

        self.assertEqual(result["pesquisa_id"], "P1")
        self.assertEqual(result["agregado_id"], 123)
        self.assertEqual(result["stat_localidades"], {"N1": 2, "N2": 1})
        self.assertEqual(result["n_niveis_territoriais"], 2)
        self.assertEqual(result["n_localidades"], 3)
        self.assertEqual(result["n_variaveis"], 2)
        self.assertEqual(result["n_classificacoes"], 2)
        self.assertEqual(result["n_dimensoes"], 6)
        self.assertEqual(result["n_periodos"], 2)

        # Calculations:
        # period_size = n_localidades * n_variaveis * max(n_dimensoes, 1)
        # period_size = 3 * 2 * 6 = 36
        self.assertEqual(result["period_size"], 36)

        # total_size = period_size * n_periodos
        # total_size = 36 * 2 = 72
        self.assertEqual(result["total_size"], 72)

        # localidade_size = max(n_variaveis, 1) * max(n_dimensoes, 1)
        # localidade_size = 2 * 6 = 12
        self.assertEqual(result["localidade_size"], 12)

        # variavel_size = max(n_dimensoes, 1)
        # variavel_size = 6
        self.assertEqual(result["variavel_size"], 6)


if __name__ == "__main__":
    unittest.main()
