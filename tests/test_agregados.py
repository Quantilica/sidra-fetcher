import unittest

from sidra_fetcher.agregados import (
    AcervoEnum,
    build_url_acervos,
    build_url_agregados,
    build_url_localidades,
    build_url_metadados,
    build_url_periodos,
)

BASE_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"


class TestAgregados(unittest.TestCase):
    def test_build_url_agregados(self):
        self.assertEqual(build_url_agregados(), BASE_URL)

    def test_build_url_metadados(self):
        agregado_id = 1705
        expected = f"{BASE_URL}/{agregado_id}/metadados"
        self.assertEqual(build_url_metadados(agregado_id), expected)

    def test_build_url_periodos(self):
        agregado_id = 1705
        expected = f"{BASE_URL}/{agregado_id}/periodos"
        self.assertEqual(build_url_periodos(agregado_id), expected)

    def test_build_url_localidades(self):
        agregado_id = 1705
        localidades_nivel = "N1"
        expected = f"{BASE_URL}/{agregado_id}/localidades/{localidades_nivel}"
        self.assertEqual(
            build_url_localidades(agregado_id, localidades_nivel), expected
        )

    def test_build_url_acervos(self):
        # Test for each enum value
        for acervo in AcervoEnum:
            url = build_url_acervos(acervo)
            self.assertIn("acervo=" + acervo.value, url)
            self.assertTrue(url.startswith(BASE_URL))


if __name__ == "__main__":
    unittest.main()
