# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

import unittest

from sidra_fetcher.sidra import (
    Parametro,
    Precisao,
    parameter_from_url,
    parse_aggregate,
    parse_classifications,
    parse_decimal,
    parse_periods,
    parse_territories,
    parse_url,
    parse_variables,
)

url = "https://apisidra.ibge.gov.br/values/t/6723/n1/all/v/all/p/all/c844/all/d/v1394%202,v1395%202,v1396%202,v10008%205"


class TestSidra(unittest.TestCase):
    def test_parse_aggregate(self):
        t, aggregate = parse_aggregate(url)
        self.assertEqual(t, "/t/6723")
        self.assertEqual(aggregate, "6723")

    def test_parse_territories(self):
        n, territories = parse_territories(url)
        self.assertEqual(n, ["/n1/all"])
        self.assertEqual(territories, {"1": ["all"]})

    def test_parse_classifications(self):
        c, classifications = parse_classifications(url)
        self.assertEqual(c, ["/c844/all"])
        self.assertEqual(classifications, {"844": ["all"]})

    def test_parse_variables(self):
        v, variables = parse_variables(url)
        self.assertEqual(v, "/v/all")
        self.assertEqual(variables, ["all"])

    def test_parse_decimal(self):
        d, decimal = parse_decimal(url)
        self.assertEqual(d, "/d/v1394%202,v1395%202,v1396%202,v10008%205")
        self.assertEqual(
            decimal,
            {
                "1394": Precisao("2"),
                "1395": Precisao("2"),
                "1396": Precisao("2"),
                "10008": Precisao("5"),
            },
        )

    def test_parse_periods(self):
        p, periods = parse_periods(url)
        self.assertEqual(p, "/p/all")
        self.assertEqual(periods, ["all"])

    def test_parse_url(self):
        parsed = parse_url(url)
        self.assertEqual(
            parsed["url"],
            "/t/6723/n1/all/v/all/p/all/c844/all/d/v1394%202,v1395%202,v1396%202,v10008%205",
        )
        self.assertEqual(parsed["t"], "/t/6723")
        self.assertEqual(parsed["aggregate"], "6723")
        self.assertEqual(parsed["n"], ["/n1/all"])
        self.assertEqual(parsed["territories"], {"1": ["all"]})
        self.assertEqual(parsed["c"], ["/c844/all"])
        self.assertEqual(parsed["classifications"], {"844": ["all"]})
        self.assertEqual(parsed["v"], "/v/all")
        self.assertEqual(parsed["variables"], ["all"])
        self.assertEqual(parsed["d"], "/d/v1394%202,v1395%202,v1396%202,v10008%205")
        self.assertEqual(
            parsed["decimal"],
            {
                "1394": Precisao("2"),
                "1395": Precisao("2"),
                "1396": Precisao("2"),
                "10008": Precisao("5"),
            },
        )
        self.assertEqual(parsed["p"], "/p/all")
        self.assertEqual(parsed["periods"], ["all"])

    def test_parameter_from_url(self):
        parameter = parameter_from_url(url)
        self.assertIsInstance(parameter, Parametro)
        self.assertEqual(parameter.agregado, "6723")
        self.assertEqual(parameter.territorios, {"1": ["all"]})
        self.assertEqual(parameter.variaveis, ["all"])
        self.assertEqual(parameter.periodos, ["all"])
        self.assertEqual(parameter.classificacoes, {"844": ["all"]})
        self.assertEqual(
            parameter.decimais,
            {
                "1394": Precisao("2"),
                "1395": Precisao("2"),
                "1396": Precisao("2"),
                "10008": Precisao("5"),
            },
        )


if __name__ == "__main__":
    unittest.main()
