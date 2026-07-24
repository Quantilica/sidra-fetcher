# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

import itertools
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from quantilica.core.exceptions import FetchError

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
from sidra_fetcher.download import (
    _RateLimiter,
    describe_download_plan,
    plan_agregado_download,
)
from sidra_fetcher.fetcher import SidraClient
from sidra_fetcher.stats import calculate_aggregate


def _make_agregado(
    *,
    n_periodos=1,
    n_localidades=1,
    n_variaveis=1,
    categoria_counts=(),
    nivel="N1",
    outros_niveis=None,
):
    """Constrói um Agregado sintético com contagens controladas, para testar
    o chunking sem depender de dados reais do IBGE.
    """
    periodos = [
        Periodo(id=f"p{i:04d}", literals=[], modificacao=Mock())
        for i in range(n_periodos)
    ]
    localidades = [
        Localidade(
            id=f"loc{i}", nome=f"Loc{i}", nivel=NivelTerritorial(id=nivel, nome=nivel)
        )
        for i in range(n_localidades)
    ]
    niveis = [nivel]
    if outros_niveis:
        for outro_nivel, n in outros_niveis.items():
            niveis.append(outro_nivel)
            localidades += [
                Localidade(
                    id=f"{outro_nivel}_{i}",
                    nome=f"{outro_nivel}{i}",
                    nivel=NivelTerritorial(id=outro_nivel, nome=outro_nivel),
                )
                for i in range(n)
            ]
    variaveis = [
        Variavel(id=i, nome=f"V{i}", unidade="u", sumarizacao=[])
        for i in range(n_variaveis)
    ]
    classificacoes = [
        Classificacao(
            id=ci,
            nome=f"C{ci}",
            sumarizacao=ClassificacaoSumarizacao(status=True, excecao=[]),
            categorias=[
                Categoria(id=ci * 100 + k, nome=f"Cat{ci}_{k}", unidade=None, nivel=1)
                for k in range(count)
            ],
        )
        for ci, count in enumerate(categoria_counts, start=1)
    ]
    return Agregado(
        id=1,
        nome="Agregado Teste",
        url="http://url",
        pesquisa=Pesquisa(id="P1", nome="Pesquisa 1"),
        assunto="Assunto",
        periodicidade=Periodicidade(frequencia="mensal", inicio="p0000", fim="p9999"),
        nivel_territorial=AgregadoNivelTerritorial(
            administrativo=niveis, especial=[], ibge=[]
        ),
        variaveis=variaveis,
        classificacoes=classificacoes,
        periodos=periodos,
        localidades=localidades,
    )


def _localidades_do_nivel(agregado, nivel):
    return [loc.id for loc in agregado.localidades if loc.nivel.id == nivel]


def _expand_chunk(parametro, agregado):
    """Reconstrói o conjunto explícito de (periodo, localidade, variavel,
    combinacao_de_categorias) coberto por um chunk, resolvendo `all`/`[]`
    contra os metadados completos do agregado — independente da lógica
    interna de planejamento, para verificar cobertura/sobreposição.
    """
    nivel_numero, codigos_loc = next(iter(parametro.territorios.items()))
    nivel = f"N{nivel_numero}"
    localidades = codigos_loc if codigos_loc else _localidades_do_nivel(agregado, nivel)

    periodos = (
        parametro.periodos if parametro.periodos else [p.id for p in agregado.periodos]
    )
    variaveis = (
        parametro.variaveis
        if parametro.variaveis
        else [str(v.id) for v in agregado.variaveis]
    )

    opcoes_por_classificacao = []
    for c in agregado.classificacoes:
        cid = str(c.id)
        cats = parametro.classificacoes.get(cid, [])
        opcoes_por_classificacao.append(
            cats if cats else [str(cat.id) for cat in c.categorias]
        )

    combos = set()
    for periodo in periodos:
        for localidade in localidades:
            for variavel in variaveis:
                for combo in itertools.product(*opcoes_por_classificacao):
                    combos.add((periodo, localidade, variavel, combo))
    return combos


def _espaco_completo(agregado, nivel="N1"):
    return set(
        itertools.product(
            [p.id for p in agregado.periodos],
            _localidades_do_nivel(agregado, nivel),
            [str(v.id) for v in agregado.variaveis],
            list(
                itertools.product(
                    *[
                        [str(cat.id) for cat in c.categorias]
                        for c in agregado.classificacoes
                    ]
                )
            ),
        )
    )


class TestPlanAgregadoDownload(unittest.TestCase):
    def test_plan_happy_path_single_chunk(self):
        agregado = _make_agregado(
            n_periodos=2, n_localidades=3, n_variaveis=2, categoria_counts=[2, 3]
        )
        chunks = plan_agregado_download(agregado)
        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        self.assertEqual(chunk.nivel_territorial, "N1")
        self.assertEqual(chunk.parametro.territorios, {"1": []})
        self.assertEqual(chunk.parametro.variaveis, [])
        self.assertEqual(chunk.parametro.periodos, [])
        self.assertEqual(chunk.parametro.classificacoes, {"1": [], "2": []})
        esperado = calculate_aggregate(agregado)["total_size"]
        self.assertEqual(chunk.n_valores, esperado)

    def test_no_chunk_exceeds_limit(self):
        agregado = _make_agregado(n_periodos=50, n_localidades=30, n_variaveis=2)
        limit = 1000
        chunks = plan_agregado_download(agregado, limit=limit)
        for chunk in chunks:
            combos = _expand_chunk(chunk.parametro, agregado)
            self.assertLessEqual(len(combos), limit)
            self.assertEqual(len(combos), chunk.n_valores)

    def test_chunks_cover_full_selection_without_overlap(self):
        agregado = _make_agregado(n_periodos=6, n_localidades=10, n_variaveis=2)
        limit = 8
        chunks = plan_agregado_download(agregado, limit=limit)

        todas = set()
        soma = 0
        for chunk in chunks:
            combos = _expand_chunk(chunk.parametro, agregado)
            self.assertLessEqual(len(combos), limit)
            self.assertTrue(todas.isdisjoint(combos), "chunks não devem se sobrepor")
            todas |= combos
            soma += len(combos)

        esperado = _espaco_completo(agregado)
        self.assertEqual(todas, esperado)
        self.assertEqual(soma, len(esperado))

    def test_period_first_priority(self):
        # period_size (3*1=3) cabe no limite, mas o total (5*3=15) não —
        # deve dividir só por período, mantendo o resto intacto ("all").
        agregado = _make_agregado(n_periodos=5, n_localidades=3, n_variaveis=1)
        chunks = plan_agregado_download(agregado, limit=10)
        self.assertEqual(len(chunks), 5)
        periodos_vistos = set()
        for chunk in chunks:
            self.assertEqual(len(chunk.parametro.periodos), 1)
            self.assertEqual(chunk.parametro.territorios, {"1": []})
            self.assertEqual(chunk.parametro.variaveis, [])
            periodos_vistos.add(chunk.parametro.periodos[0])
        self.assertEqual(periodos_vistos, {p.id for p in agregado.periodos})

    def test_locality_batch_fallback(self):
        # Um único período já excede o limite; localidades divididas em
        # lotes, variáveis permanecem intactas ("all").
        agregado = _make_agregado(n_periodos=1, n_localidades=10, n_variaveis=1)
        chunks = plan_agregado_download(agregado, limit=4)
        self.assertGreater(len(chunks), 1)
        vistos: set[str] = set()
        for chunk in chunks:
            codigos = chunk.parametro.territorios["1"]
            self.assertTrue(codigos)  # lote explícito, não "all"
            self.assertLessEqual(len(codigos), 4)
            self.assertTrue(vistos.isdisjoint(codigos))
            vistos.update(codigos)
            self.assertEqual(chunk.parametro.variaveis, [])
        self.assertEqual(vistos, set(_localidades_do_nivel(agregado, "N1")))

    def test_variable_and_classificacao_fallback(self):
        # localidade=1, período=1: só variável e classificação sobram para
        # dividir. C2 inclui a categoria "0" — que TEM que ser baixada (ao
        # contrário do unnest_classificacoes do sidra-sql, aqui o objetivo é
        # completude, não excluir a categoria "Total").
        agregado = Agregado(
            id=99,
            nome="X",
            url="",
            pesquisa=Pesquisa(id="P", nome="P"),
            assunto="A",
            periodicidade=Periodicidade(frequencia="mensal", inicio="p0", fim="p0"),
            nivel_territorial=AgregadoNivelTerritorial(
                administrativo=["N1"], especial=[], ibge=[]
            ),
            variaveis=[
                Variavel(id=i, nome=f"V{i}", unidade="u", sumarizacao=[])
                for i in range(4)
            ],
            classificacoes=[
                Classificacao(
                    id=1,
                    nome="C1",
                    sumarizacao=ClassificacaoSumarizacao(status=True, excecao=[]),
                    categorias=[
                        Categoria(id=10, nome="Cat10", unidade=None, nivel=1),
                        Categoria(id=11, nome="Cat11", unidade=None, nivel=1),
                    ],
                ),
                Classificacao(
                    id=2,
                    nome="C2",
                    sumarizacao=ClassificacaoSumarizacao(status=True, excecao=[]),
                    categorias=[
                        Categoria(id=0, nome="Total", unidade=None, nivel=1),
                        Categoria(id=20, nome="Cat20", unidade=None, nivel=1),
                        Categoria(id=21, nome="Cat21", unidade=None, nivel=1),
                    ],
                ),
            ],
            periodos=[Periodo(id="p0", literals=[], modificacao=Mock())],
            localidades=[
                Localidade(
                    id="loc0", nome="Loc0", nivel=NivelTerritorial(id="N1", nome="N1")
                )
            ],
        )
        chunks = plan_agregado_download(agregado, limit=2)

        todas = set()
        for chunk in chunks:
            self.assertLessEqual(chunk.n_valores, 2)
            combos = _expand_chunk(chunk.parametro, agregado)
            self.assertTrue(todas.isdisjoint(combos))
            todas |= combos

        esperado = _espaco_completo(agregado)
        self.assertEqual(todas, esperado)
        # A categoria "0" precisa aparecer em algum chunk — não pode ter sido
        # descartada.
        categorias_baixadas = {combo[3][1] for combo in todas}
        self.assertIn("0", categorias_baixadas)

    def test_skip_nivel_sem_localidades(self):
        # Nível declarado nos metadados (nivel_territorial.administrativo)
        # mas sem nenhuma localidade correspondente — não deve gerar chunk
        # (request vazio), como acontece na prática com alguns agregados do
        # IBGE (ex.: N7 sem localidades em algumas tabelas).
        agregado = _make_agregado(n_periodos=1, n_localidades=2, n_variaveis=1)
        agregado.nivel_territorial.administrativo.append("N7")
        chunks = plan_agregado_download(agregado)
        self.assertEqual({c.nivel_territorial for c in chunks}, {"N1"})

    def test_niveis_territoriais_never_mixed(self):
        agregado = _make_agregado(
            n_periodos=1,
            n_localidades=2,
            n_variaveis=1,
            outros_niveis={"N3": 2},
        )
        chunks = plan_agregado_download(agregado)
        self.assertEqual({c.nivel_territorial for c in chunks}, {"N1", "N3"})
        for chunk in chunks:
            self.assertEqual(len(chunk.parametro.territorios), 1)

    def test_describe_download_plan_totals(self):
        agregado = _make_agregado(
            n_periodos=2, n_localidades=3, n_variaveis=2, categoria_counts=[2, 3]
        )
        chunks = plan_agregado_download(agregado)
        resumo = describe_download_plan(chunks)
        self.assertEqual(
            resumo["n_valores"], calculate_aggregate(agregado)["total_size"]
        )
        self.assertEqual(resumo["n_requests"], len(chunks))
        self.assertEqual(resumo["por_nivel"]["N1"]["n_requests"], len(chunks))

    def test_restrict_variaveis_and_periodos(self):
        agregado = _make_agregado(
            n_periodos=5, n_localidades=3, n_variaveis=4, categoria_counts=[3]
        )
        periodos_restritos = [p.id for p in agregado.periodos[:2]]
        variaveis_restritas = [str(v.id) for v in agregado.variaveis[:1]]
        cid = str(agregado.classificacoes[0].id)
        categorias_restritas = [
            str(cat.id) for cat in agregado.classificacoes[0].categorias[:2]
        ]
        chunks = plan_agregado_download(
            agregado,
            periodos=periodos_restritos,
            variaveis=variaveis_restritas,
            classificacoes={cid: categorias_restritas},
        )
        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        # Sem restrição, o total seria 5*3*4*3=180; restrito deve ser 2*3*1*2=12.
        self.assertEqual(chunk.n_valores, 12)
        # A restrição precisa aparecer explicitamente no Parametro renderizado
        # — não pode "cair" para "all" só porque coube num único chunk.
        self.assertEqual(chunk.parametro.periodos, periodos_restritos)
        self.assertEqual(chunk.parametro.variaveis, variaveis_restritas)
        self.assertEqual(chunk.parametro.classificacoes[cid], categorias_restritas)

    def test_unknown_variavel_raises(self):
        agregado = _make_agregado(n_periodos=1, n_localidades=1, n_variaveis=2)
        with self.assertRaises(ValueError):
            plan_agregado_download(agregado, variaveis=["999"])

    def test_unknown_periodo_raises(self):
        agregado = _make_agregado(n_periodos=2, n_localidades=1, n_variaveis=1)
        with self.assertRaises(ValueError):
            plan_agregado_download(agregado, periodos=["209912"])

    def test_unknown_nivel_raises(self):
        agregado = _make_agregado(n_periodos=1, n_localidades=1, n_variaveis=1)
        with self.assertRaises(ValueError):
            plan_agregado_download(agregado, niveis_territoriais=["N99"])

    def test_unknown_classificacao_raises(self):
        agregado = _make_agregado(
            n_periodos=1, n_localidades=1, n_variaveis=1, categoria_counts=[2]
        )
        with self.assertRaises(ValueError):
            plan_agregado_download(agregado, classificacoes={"999": ["1"]})

    def test_empty_filter_raises(self):
        agregado = _make_agregado(n_periodos=2, n_localidades=1, n_variaveis=1)
        with self.assertRaises(ValueError):
            plan_agregado_download(agregado, periodos=[])


class TestRateLimiter(unittest.TestCase):
    def test_spaces_calls(self):
        limiter = _RateLimiter(0.02)
        inicio = time.monotonic()
        for _ in range(3):
            limiter.wait()
        elapsed = time.monotonic() - inicio
        # 3 chamadas com intervalo mínimo de 0.02 s: a 1ª é imediata, a 2ª e a
        # 3ª esperam ~0.02 s cada → total >= ~0.04 s.
        self.assertGreaterEqual(elapsed, 0.035)

    def test_zero_interval_is_noop(self):
        limiter = _RateLimiter(0.0)
        inicio = time.monotonic()
        for _ in range(100):
            limiter.wait()
        self.assertLess(time.monotonic() - inicio, 0.05)


def _make_mock_response(data: object) -> MagicMock:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.url = "http://mock"
    mock_response.json.return_value = data
    return mock_response


class TestClientDownload(unittest.TestCase):
    def setUp(self):
        self._patchers = []

    def tearDown(self):
        for p in self._patchers:
            p.stop()

    def _make_client_with_responses(self, payloads: list[object]) -> SidraClient:
        responses = [_make_mock_response(p) for p in payloads]
        patcher = patch("quantilica.core.http.httpx.Client")
        self._patchers.append(patcher)
        mock_cls = patcher.start()
        mock_instance = mock_cls.return_value.__enter__.return_value
        mock_instance.request.side_effect = responses
        return SidraClient()

    def _make_agregado_2_periodos(self):
        return _make_agregado(n_periodos=2, n_localidades=1, n_variaveis=1)

    def test_iter_dados_agregado_merges_sequential_requests(self):
        payload_p0 = [{"NC": "cab"}, {"NC": "1", "V": "10"}]
        payload_p1 = [{"NC": "cab"}, {"NC": "1", "V": "20"}]
        client = self._make_client_with_responses([payload_p0, payload_p1])
        agregado = self._make_agregado_2_periodos()

        resultados = list(
            client.iter_dados_agregado(agregado.id, agregado=agregado, limit=1)
        )

        self.assertEqual(len(resultados), 2)
        self.assertEqual(resultados[0][1], payload_p0)
        self.assertEqual(resultados[1][1], payload_p1)

    def test_get_dados_agregado_strips_repeated_headers(self):
        payload_p0 = [{"NC": "cab"}, {"NC": "1", "V": "10"}]
        payload_p1 = [{"NC": "cab"}, {"NC": "1", "V": "20"}]
        client = self._make_client_with_responses([payload_p0, payload_p1])
        agregado = self._make_agregado_2_periodos()

        linhas = client.get_dados_agregado(agregado.id, agregado=agregado, limit=1)

        self.assertEqual(
            linhas,
            [payload_p0[0], payload_p0[1], payload_p1[1]],
        )

    def test_non_list_response_raises_fetcherror(self):
        # A API pode responder HTTP 200 com um corpo de erro em dict; deve
        # levantar FetchError claro em vez de TypeError obscuro.
        erro = {"status": 400, "message": "Parâmetro inválido"}
        client = self._make_client_with_responses([erro])
        agregado = self._make_agregado_2_periodos()
        with self.assertRaises(FetchError):
            list(client.iter_dados_agregado(agregado.id, agregado=agregado, limit=1))

    def test_non_list_response_raises_in_download(self):
        erro = {"status": 500, "message": "Erro interno"}
        client = self._make_client_with_responses([erro, erro])
        agregado = self._make_agregado_2_periodos()
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(FetchError):
                client.download_dados_agregado(
                    agregado.id, tmp_dir, agregado=agregado, limit=1, max_workers=1
                )

    def test_download_agregado_dados_writes_ndjson_and_manifest(self):
        payload_p0 = [{"NC": "cab"}, {"NC": "1", "V": "10"}]
        payload_p1 = [{"NC": "cab"}, {"NC": "1", "V": "20"}]
        client = self._make_client_with_responses([payload_p0, payload_p1])
        agregado = self._make_agregado_2_periodos()

        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = client.download_dados_agregado(
                agregado.id,
                tmp_dir,
                agregado=agregado,
                limit=1,
                max_workers=1,
            )

            self.assertEqual(len(paths), 1)
            data_path = paths[0]
            self.assertEqual(data_path.name, "dados_N1.ndjson")

            linhas = [json.loads(linha) for linha in data_path.read_text().splitlines()]
            self.assertEqual(linhas, [payload_p0[0], payload_p0[1], payload_p1[1]])

            manifest_path = Path(str(data_path) + ".manifest.json")
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["source_id"], "ibge")
            self.assertEqual(manifest["dataset_id"], f"{agregado.id}:N1")
            self.assertEqual(manifest["size_bytes"], len(data_path.read_bytes()))

            import hashlib

            self.assertEqual(
                manifest["sha256"], hashlib.sha256(data_path.read_bytes()).hexdigest()
            )


if __name__ == "__main__":
    unittest.main()
