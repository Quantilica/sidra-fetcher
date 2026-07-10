# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

import unittest

from sidra_fetcher.sidra import (
    SIDRA_API_VALUES_LIMIT,
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

    def test_parse_periods_monthly_codes(self):
        p, periods = parse_periods("/t/1705/p/202301,202302/v/all")
        self.assertEqual(p, "/p/202301,202302")
        self.assertEqual(periods, ["202301", "202302"])

    def test_parse_periods_annual_codes(self):
        p, periods = parse_periods("/t/1612/p/2010,2011/v/all")
        self.assertEqual(p, "/p/2010,2011")
        self.assertEqual(periods, ["2010", "2011"])

    def test_parse_periods_monthly_range(self):
        p, periods = parse_periods("/t/1705/p/201301-201312/v/all")
        self.assertEqual(p, "/p/201301-201312")
        self.assertEqual(periods, ["201301-201312"])

    def test_parse_periods_annual_range(self):
        p, periods = parse_periods("/t/1612/p/2010-2015/v/all")
        self.assertEqual(p, "/p/2010-2015")
        self.assertEqual(periods, ["2010-2015"])

    def test_parse_periods_mixed_codes_and_ranges(self):
        p, periods = parse_periods("/t/1705/p/201201,201301-201312/v/all")
        self.assertEqual(p, "/p/201201,201301-201312")
        self.assertEqual(periods, ["201201", "201301-201312"])

    def test_parse_periods_last_n(self):
        p, periods = parse_periods("/t/1705/p/last%2012/v/all")
        self.assertEqual(p, "/p/last%2012")
        self.assertEqual(periods, ["last%2012"])

    def test_parse_periods_missing(self):
        p, periods = parse_periods("/t/1705/v/all")
        self.assertEqual(p, "")
        self.assertEqual(periods, [])

    def test_values_limit_constant(self):
        self.assertIsInstance(SIDRA_API_VALUES_LIMIT, int)
        self.assertEqual(SIDRA_API_VALUES_LIMIT, 100_000)

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
