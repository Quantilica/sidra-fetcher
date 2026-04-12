# Copyright (C) 2022-2026 Daniel Kiyoyudi Komesu
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.

import datetime as dt
import unittest

from sidra_fetcher.agregados import Periodo
from sidra_fetcher.periodos import (
    FREQUENCIA_MENSAL,
    parse_date,
    parse_period,
)
from sidra_fetcher.reader import read_periodos


class TestPeriodoParsing(unittest.TestCase):
    """Test suite for period parsing functions."""

    def test_parse_monthly_period(self):
        """Test parsing a monthly period."""
        periodo = {
            "id": "202301",
            "literals": ["janeiro de 2023", "1/2023"],
        }
        result = parse_period(periodo)

        self.assertEqual(result["id"], "202301")
        self.assertEqual(result["frequencia"], "mensal")
        self.assertEqual(result["ano"], 2023)
        self.assertEqual(result["mes"], 1)
        self.assertEqual(result["data_inicio"], dt.date(2023, 1, 1))
        self.assertEqual(result["data_fim"], dt.date(2023, 1, 31))

    def test_parse_quarterly_period(self):
        """Test parsing a quarterly period."""
        periodo = {
            "id": "202302",
            "literals": ["2º trimestre de 2023"],
        }
        result = parse_period(periodo)

        self.assertEqual(result["frequencia"], "trimestral")
        self.assertEqual(result["trimestre"], 2)
        self.assertEqual(result["ano"], 2023)
        self.assertEqual(result["data_inicio"], dt.date(2023, 4, 1))
        self.assertEqual(result["data_fim"], dt.date(2023, 6, 30))

    def test_parse_rolling_quarter_period(self):
        """Test parsing a rolling quarter period."""
        periodo = {
            "id": "202212",
            "literals": ["jan-fev-mar 2023"],
        }
        result = parse_period(periodo)

        self.assertEqual(result["frequencia"], "trimestre_movel")
        self.assertEqual(result["ano"], 2023)
        self.assertEqual(result["data_inicio"], dt.date(2023, 1, 1))
        self.assertEqual(result["data_fim"], dt.date(2023, 3, 31))

    def test_parse_semiannual_period(self):
        """Test parsing a semiannual period."""
        periodo = {
            "id": "202301",
            "literals": ["1º semestre de 2023"],
        }
        result = parse_period(periodo)

        self.assertEqual(result["frequencia"], "semestral")
        self.assertEqual(result["semestre"], 1)
        self.assertEqual(result["ano"], 2023)
        self.assertEqual(result["data_inicio"], dt.date(2023, 1, 1))
        self.assertEqual(result["data_fim"], dt.date(2023, 6, 30))

    def test_parse_annual_period(self):
        """Test parsing an annual period."""
        periodo = {
            "id": "2023",
            "literals": ["2023"],
        }
        result = parse_period(periodo)

        self.assertEqual(result["frequencia"], "anual")
        self.assertEqual(result["ano"], 2023)
        self.assertIsNone(result["ano_fim"])
        self.assertEqual(result["data_inicio"], dt.date(2023, 1, 1))
        self.assertEqual(result["data_fim"], dt.date(2023, 12, 31))

    def test_parse_multi_annual_period(self):
        """Test parsing a multi-annual period."""
        periodo = {
            "id": "20202023",
            "literals": ["2020/2023"],
        }
        result = parse_period(periodo)

        self.assertEqual(result["frequencia"], "plurianual")
        self.assertEqual(result["ano"], 2020)
        self.assertEqual(result["ano_fim"], 2023)
        self.assertEqual(result["data_inicio"], dt.date(2020, 1, 1))
        self.assertEqual(result["data_fim"], dt.date(2023, 12, 31))

    def test_parse_unrecognized_period(self):
        """Test parsing an unrecognized period format."""
        periodo = {
            "id": "unknown",
            "literals": ["unknown format"],
        }
        result = parse_period(periodo)

        self.assertEqual(result["frequencia"], "nao_reconhecida")
        self.assertIsNone(result["data_inicio"])
        self.assertIsNone(result["data_fim"])

    def test_parse_period_case_insensitive(self):
        """Test that period parsing is case-insensitive."""
        periodo = {
            "id": "202301",
            "literals": ["JANEIRO DE 2023"],
        }
        result = parse_period(periodo)

        self.assertEqual(result["frequencia"], "mensal")
        self.assertEqual(result["mes"], 1)

    def test_parse_period_with_space_variant(self):
        """Test parsing period with space variant separator."""
        periodo = {
            "id": "202301",
            "literals": ["janeiro 2023"],
        }
        result = parse_period(periodo)

        self.assertEqual(result["frequencia"], "mensal")
        self.assertEqual(result["mes"], 1)


class TestDateParsing(unittest.TestCase):
    """Test suite for date parsing utilities."""

    def test_parse_date(self):
        """Test parsing date strings."""
        result = parse_date("15/01/2023")
        expected = dt.date(2023, 1, 15)
        self.assertEqual(result, expected)

        result = parse_date("2023-01-15")
        expected = dt.date(2023, 1, 15)
        self.assertEqual(result, expected)


class TestReaderPeriodos(unittest.TestCase):
    """Test suite for reader.py period functions."""

    def test_read_periodos_basic(self):
        """Test basic period reading with enrichment."""
        raw_data = [
            {
                "id": "202301",
                "literals": ["janeiro de 2023", "1/2023"],
                "modificacao": "15/01/2023",
            }
        ]
        result = read_periodos(raw_data)

        self.assertEqual(len(result), 1)
        p = result[0]
        self.assertEqual(p.id, "202301")
        self.assertEqual(p.literals, ["janeiro de 2023", "1/2023"])
        self.assertEqual(p.modificacao, dt.date(2023, 1, 15))
        # Enriched fields should be populated
        self.assertEqual(p.frequencia, "mensal")
        self.assertEqual(p.ano, 2023)
        self.assertEqual(p.mes, 1)
        self.assertEqual(p.data_inicio, dt.date(2023, 1, 1))
        self.assertEqual(p.data_fim, dt.date(2023, 1, 31))

    def test_read_periodos_multiple(self):
        """Test reading multiple periods."""
        raw_data = [
            {
                "id": "202301",
                "literals": ["janeiro de 2023"],
                "modificacao": "15/01/2023",
            },
            {
                "id": "202302",
                "literals": ["fevereiro de 2023"],
                "modificacao": "15/02/2023",
            },
        ]
        result = read_periodos(raw_data)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, "202301")
        self.assertEqual(result[1].id, "202302")

    def test_periodo_dataclass_enriched_fields(self):
        """Test that Periodo dataclass supports enriched fields."""
        p = Periodo(
            id="202301",
            literals=["janeiro de 2023"],
            modificacao=dt.date(2023, 1, 15),
            frequencia=FREQUENCIA_MENSAL,
            data_inicio=dt.datetime(2023, 1, 1),
            data_fim=dt.datetime(2023, 1, 31),
            ano=2023,
            mes=1,
        )
        self.assertEqual(p.frequencia, FREQUENCIA_MENSAL)
        self.assertEqual(p.ano, 2023)
        self.assertEqual(p.mes, 1)
        self.assertEqual(p.data_inicio, dt.datetime(2023, 1, 1))


if __name__ == "__main__":
    unittest.main()
