# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

import datetime as dt
import json
import sys
import unittest
from unittest.mock import MagicMock

# Mock external dependencies that might be missing
sys.modules["httpx"] = MagicMock()
sys.modules["tenacity"] = MagicMock()
sys.modules["tenacity.retry"] = MagicMock()
sys.modules["tenacity.stop"] = MagicMock()
sys.modules["tenacity.wait"] = MagicMock()


# Mock the decorators from tenacity to just return the function
def mock_retry(*args, **kwargs):
    def decorator(f):
        return f

    return decorator


sys.modules["tenacity"].retry = mock_retry

from sidra_fetcher.agregados import AcervoEnum
from sidra_fetcher.fetcher import SidraClient
from sidra_fetcher.periodos import (
    FREQUENCIA_ANUAL,
    FREQUENCIA_MENSAL,
    FREQUENCIA_NAO_RECONHECIDA,
    FREQUENCIA_PLURIANUAL,
    FREQUENCIA_SEMESTRAL,
    FREQUENCIA_TRIMESTRAL,
    FREQUENCIA_TRIMESTRE_MOVEL,
)


class TestFetcher(unittest.TestCase):
    def _setup_mock_periodos(self, mock_response):
        mock_httpx = sys.modules["httpx"]
        mock_client_instance = mock_httpx.Client.return_value
        mock_client_instance.stream.return_value.__enter__.return_value.iter_bytes.return_value = [
            json.dumps(mock_response).encode("utf-8")
        ]
        return SidraClient()

    def test_get_indice_pesquisas_agregados(self):
        mock_response = [
            {
                "id": "P1",
                "nome": "Pesquisa 1",
                "agregados": [{"id": 1, "nome": "Agregado 1"}],
            }
        ]

        mock_httpx = sys.modules["httpx"]
        mock_client_instance = mock_httpx.Client.return_value
        mock_client_instance.stream.return_value.__enter__.return_value.iter_bytes.return_value = [
            json.dumps(mock_response).encode("utf-8")
        ]

        client = SidraClient()
        result = client.get_indice_pesquisas_agregados()

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "P1")
        self.assertEqual(result[0].agregados[0].id, 1)

    def test_get_agregado_metadados(self):
        mock_response = {
            "id": 123,
            "nome": "Agregado Teste",
            "URL": "http://url",
            "pesquisa": "Pesquisa Teste",
            "assunto": "Assunto Teste",
            "periodicidade": {
                "frequencia": "mensal",
                "inicio": "202001",
                "fim": "202012",
            },
            "nivelTerritorial": {
                "Administrativo": ["N1"],
                "Especial": [],
                "IBGE": [],
            },
            "variaveis": [
                {"id": 1, "nome": "V1", "unidade": "u", "sumarizacao": []}
            ],
            "classificacoes": [
                {
                    "id": 1,
                    "nome": "C1",
                    "sumarizacao": {"status": True, "excecao": []},
                    "categorias": [
                        {"id": 10, "nome": "Cat1", "unidade": None, "nivel": 1}
                    ],
                }
            ],
        }

        mock_httpx = sys.modules["httpx"]
        mock_client_instance = mock_httpx.Client.return_value
        mock_client_instance.stream.return_value.__enter__.return_value.iter_bytes.return_value = [
            json.dumps(mock_response).encode("utf-8")
        ]

        client = SidraClient()
        agregado = client.get_agregado_metadados(123)

        self.assertEqual(agregado.id, 123)
        self.assertEqual(agregado.nome, "Agregado Teste")
        self.assertEqual(len(agregado.variaveis), 1)
        self.assertEqual(len(agregado.classificacoes), 1)

    def test_get_agregado_periodos_mensal(self):
        mock_response = [
            {
                "id": "202001",
                "literals": ["janeiro de 2020", "1/2020"],
                "modificacao": "15/02/2020",
            }
        ]
        client = self._setup_mock_periodos(mock_response)
        periodos = client.get_agregado_periodos(123)

        self.assertEqual(len(periodos), 1)
        p = periodos[0]
        self.assertEqual(p.id, "202001")
        self.assertEqual(p.literals, ["janeiro de 2020", "1/2020"])
        self.assertEqual(p.modificacao, dt.date(2020, 2, 15))
        self.assertEqual(p.frequencia, FREQUENCIA_MENSAL)
        self.assertEqual(p.data_inicio, dt.date(2020, 1, 1))
        self.assertEqual(p.data_fim, dt.date(2020, 1, 31))
        self.assertEqual(p.ano, 2020)
        self.assertEqual(p.mes, 1)
        self.assertIsNone(p.trimestre)
        self.assertIsNone(p.semestre)
        self.assertIsNone(p.ano_fim)

    def test_get_agregado_periodos_trimestral(self):
        mock_response = [
            {
                "id": "20201",
                "literals": ["1º trimestre de 2020"],
                "modificacao": "15/04/2020",
            }
        ]
        client = self._setup_mock_periodos(mock_response)
        periodos = client.get_agregado_periodos(123)

        self.assertEqual(len(periodos), 1)
        p = periodos[0]
        self.assertEqual(p.id, "20201")
        self.assertEqual(p.modificacao, dt.date(2020, 4, 15))
        self.assertEqual(p.frequencia, FREQUENCIA_TRIMESTRAL)
        self.assertEqual(p.data_inicio, dt.date(2020, 1, 1))
        self.assertEqual(p.data_fim, dt.date(2020, 3, 31))
        self.assertEqual(p.ano, 2020)
        self.assertEqual(p.trimestre, 1)
        self.assertIsNone(p.mes)
        self.assertIsNone(p.semestre)
        self.assertIsNone(p.ano_fim)

    def test_get_agregado_periodos_trimestre_movel(self):
        mock_response = [
            {
                "id": "202001",
                "literals": ["jan-fev-mar 2020"],
                "modificacao": "15/04/2020",
            }
        ]
        client = self._setup_mock_periodos(mock_response)
        periodos = client.get_agregado_periodos(123)

        self.assertEqual(len(periodos), 1)
        p = periodos[0]
        self.assertEqual(p.frequencia, FREQUENCIA_TRIMESTRE_MOVEL)
        self.assertEqual(p.data_inicio, dt.date(2020, 1, 1))
        self.assertEqual(p.data_fim, dt.date(2020, 3, 31))
        self.assertEqual(p.ano, 2020)
        self.assertEqual(p.mes, 3)
        self.assertIsNone(p.trimestre)
        self.assertIsNone(p.semestre)
        self.assertIsNone(p.ano_fim)

    def test_get_agregado_periodos_semestral(self):
        mock_response = [
            {
                "id": "20201",
                "literals": ["1º semestre de 2020"],
                "modificacao": "15/07/2020",
            }
        ]
        client = self._setup_mock_periodos(mock_response)
        periodos = client.get_agregado_periodos(123)

        self.assertEqual(len(periodos), 1)
        p = periodos[0]
        self.assertEqual(p.frequencia, FREQUENCIA_SEMESTRAL)
        self.assertEqual(p.data_inicio, dt.date(2020, 1, 1))
        self.assertEqual(p.data_fim, dt.date(2020, 6, 30))
        self.assertEqual(p.ano, 2020)
        self.assertEqual(p.semestre, 1)
        self.assertIsNone(p.trimestre)
        self.assertIsNone(p.mes)
        self.assertIsNone(p.ano_fim)

    def test_get_agregado_periodos_anual(self):
        mock_response = [
            {
                "id": "2020",
                "literals": ["2020"],
                "modificacao": "15/01/2021",
            }
        ]
        client = self._setup_mock_periodos(mock_response)
        periodos = client.get_agregado_periodos(123)

        self.assertEqual(len(periodos), 1)
        p = periodos[0]
        self.assertEqual(p.frequencia, FREQUENCIA_ANUAL)
        self.assertEqual(p.data_inicio, dt.date(2020, 1, 1))
        self.assertEqual(p.data_fim, dt.date(2020, 12, 31))
        self.assertEqual(p.ano, 2020)
        self.assertIsNone(p.ano_fim)
        self.assertIsNone(p.mes)
        self.assertIsNone(p.trimestre)
        self.assertIsNone(p.semestre)

    def test_get_agregado_periodos_plurianual(self):
        mock_response = [
            {
                "id": "2020/2022",
                "literals": ["2020/2022"],
                "modificacao": "15/01/2023",
            }
        ]
        client = self._setup_mock_periodos(mock_response)
        periodos = client.get_agregado_periodos(123)

        self.assertEqual(len(periodos), 1)
        p = periodos[0]
        self.assertEqual(p.frequencia, FREQUENCIA_PLURIANUAL)
        self.assertEqual(p.data_inicio, dt.date(2020, 1, 1))
        self.assertEqual(p.data_fim, dt.date(2022, 12, 31))
        self.assertEqual(p.ano, 2020)
        self.assertEqual(p.ano_fim, 2022)
        self.assertIsNone(p.mes)
        self.assertIsNone(p.trimestre)
        self.assertIsNone(p.semestre)

    def test_get_agregado_periodos_nao_reconhecido(self):
        mock_response = [
            {
                "id": "unknown",
                "literals": ["período desconhecido"],
                "modificacao": "01/01/2020",
            }
        ]
        client = self._setup_mock_periodos(mock_response)
        periodos = client.get_agregado_periodos(123)

        self.assertEqual(len(periodos), 1)
        p = periodos[0]
        self.assertEqual(p.id, "unknown")
        self.assertEqual(p.frequencia, FREQUENCIA_NAO_RECONHECIDA)
        self.assertIsNone(p.data_inicio)
        self.assertIsNone(p.data_fim)
        self.assertIsNone(p.ano)
        self.assertIsNone(p.mes)
        self.assertIsNone(p.trimestre)
        self.assertIsNone(p.semestre)
        self.assertIsNone(p.ano_fim)

    def test_get_agregado_periodos_multiplos(self):
        mock_response = [
            {
                "id": "202001",
                "literals": ["janeiro de 2020"],
                "modificacao": "15/02/2020",
            },
            {
                "id": "20201",
                "literals": ["1º trimestre de 2020"],
                "modificacao": "15/04/2020",
            },
            {
                "id": "2020",
                "literals": ["2020"],
                "modificacao": "15/01/2021",
            },
        ]
        client = self._setup_mock_periodos(mock_response)
        periodos = client.get_agregado_periodos(123)

        self.assertEqual(len(periodos), 3)
        self.assertEqual(periodos[0].frequencia, FREQUENCIA_MENSAL)
        self.assertEqual(periodos[1].frequencia, FREQUENCIA_TRIMESTRAL)
        self.assertEqual(periodos[2].frequencia, FREQUENCIA_ANUAL)

    def test_get_agregado_localidades(self):
        mock_response = [
            {
                "id": "1",
                "nome": "Loc1",
                "nivel": {"id": "N1", "nome": "Nivel 1"},
            }
        ]

        mock_httpx = sys.modules["httpx"]
        mock_client_instance = mock_httpx.Client.return_value
        mock_client_instance.stream.return_value.__enter__.return_value.iter_bytes.return_value = [
            json.dumps(mock_response).encode("utf-8")
        ]

        client = SidraClient()
        localidades = client.get_agregado_localidades(123, "N1")

        self.assertEqual(len(localidades), 1)
        self.assertEqual(localidades[0].id, "1")
        self.assertEqual(localidades[0].nivel.id, "N1")

    def test_get_acervo(self):
        mock_response = {"some": "data"}

        mock_httpx = sys.modules["httpx"]
        mock_client_instance = mock_httpx.Client.return_value
        mock_client_instance.stream.return_value.__enter__.return_value.iter_bytes.return_value = [
            json.dumps(mock_response).encode("utf-8")
        ]

        client = SidraClient()
        data = client.get_acervo(AcervoEnum.ASSUNTO)

        self.assertEqual(data, mock_response)


if __name__ == "__main__":
    unittest.main()
