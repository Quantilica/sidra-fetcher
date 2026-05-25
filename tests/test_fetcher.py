# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

import datetime as dt
import unittest
from unittest.mock import MagicMock, patch

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


def _make_mock_response(data: object) -> MagicMock:
    """Return a mock httpx.Response that yields *data* as JSON."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.url = "http://mock"
    mock_response.json.return_value = data
    return mock_response


def _make_client(mock_response: object) -> SidraClient:
    """Patch httpx.Client so that any request returns *mock_response*."""
    mock_resp = _make_mock_response(mock_response)
    with patch("quantilica_core.http.httpx.Client") as mock_client_cls:
        ctx = mock_client_cls.return_value.__enter__.return_value
        ctx.request.return_value = mock_resp
        # The SidraClient is created inside the patch so the
        # HttpClient captures the patched httpx.Client class.
        client = SidraClient()
    # Re-apply the patch on the already-created client's internal
    # HttpClient so subsequent calls also use our mock.
    client._mock_resp = mock_resp
    client._mock_client_cls_patcher = patch("quantilica_core.http.httpx.Client")
    mock_client_cls2 = client._mock_client_cls_patcher.start()
    mock_inst2 = mock_client_cls2.return_value.__enter__.return_value
    mock_inst2.request.return_value = mock_resp
    return client


class TestFetcher(unittest.TestCase):
    def setUp(self):
        self._patchers = []

    def tearDown(self):
        for p in self._patchers:
            p.stop()

    def _patch_http(self, data: object) -> tuple[SidraClient, MagicMock]:
        """
        Patch httpx.Client used inside quantilica_core.http so that
        every request returns a response whose .json() is *data*.
        Returns (client, mock_response).
        """
        mock_resp = _make_mock_response(data)
        patcher = patch("quantilica_core.http.httpx.Client")
        self._patchers.append(patcher)
        mock_cls = patcher.start()
        mock_instance = mock_cls.return_value.__enter__.return_value
        mock_instance.request.return_value = mock_resp
        return SidraClient(), mock_resp

    def test_get_indice_pesquisas_agregados(self):
        mock_response = [
            {
                "id": "P1",
                "nome": "Pesquisa 1",
                "agregados": [{"id": 1, "nome": "Agregado 1"}],
            }
        ]

        client, _ = self._patch_http(mock_response)
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
            "variaveis": [{"id": 1, "nome": "V1", "unidade": "u", "sumarizacao": []}],
            "classificacoes": [
                {
                    "id": 1,
                    "nome": "C1",
                    "sumarizacao": {"status": True, "excecao": []},
                    "categorias": [
                        {
                            "id": 10,
                            "nome": "Cat1",
                            "unidade": None,
                            "nivel": 1,
                        }
                    ],
                }
            ],
        }

        client, _ = self._patch_http(mock_response)
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
        client, _ = self._patch_http(mock_response)
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
        client, _ = self._patch_http(mock_response)
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
        client, _ = self._patch_http(mock_response)
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
        client, _ = self._patch_http(mock_response)
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
        client, _ = self._patch_http(mock_response)
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
        client, _ = self._patch_http(mock_response)
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
        client, _ = self._patch_http(mock_response)
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
        client, _ = self._patch_http(mock_response)
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

        client, _ = self._patch_http(mock_response)
        localidades = client.get_agregado_localidades(123, "N1")

        self.assertEqual(len(localidades), 1)
        self.assertEqual(localidades[0].id, "1")
        self.assertEqual(localidades[0].nivel.id, "N1")

    def test_get_acervo(self):
        mock_response = {"some": "data"}

        client, _ = self._patch_http(mock_response)
        data = client.get_acervo(AcervoEnum.ASSUNTO)

        self.assertEqual(data, mock_response)

    # ------------------------------------------------------------------
    # JSON serialisation round-trip for sys.modules mock is no longer
    # needed since we patch at the httpx.Client level.
    # The json / sys.modules imports were only used by the old approach.
    # ------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main()
