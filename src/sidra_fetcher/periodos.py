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

"""Period parsing utilities for IBGE time-series data.

This module provides functions to parse period strings from the IBGE API and
extract temporal information (frequency, start date, end date, etc.). It supports
multiple Brazilian temporal formats including:

- Monthly periods (e.g., "janeiro de 2023")
- Quarterly periods (e.g., "1º trimestre de 2023")
- Rolling quarters (e.g., "jan-fev-mar 2023")
- Semiannual periods (e.g., "1º semestre de 2023")
- Annual periods (e.g., "2023")
- Multi-annual ranges (e.g., "2020/2023")

Typical usage:

    >>> from sidra_fetcher.periodos import parse_period
    >>> raw_period = {"id": "202301", "literals": ["janeiro de 2023", "1/2023"]}
    >>> parsed = parse_period(raw_period)
    >>> print(parsed["frequency"])  # "monthly"
    >>> print(parsed["start_date"])  # datetime.datetime(2023, 1, 1)
"""

import calendar
import datetime as dt
import re


def _last_day_of_month(year: int, month: int) -> int:
    """Get the last day number of a given month."""
    return calendar.monthrange(year, month)[1]


def _add_months(date: dt.datetime, months: int) -> dt.datetime:
    """Add months to a datetime, handling year/month overflow."""
    month = date.month + months
    year = date.year
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1
    day = min(date.day, _last_day_of_month(year, month))
    return date.replace(year=year, month=month, day=day)


# Frequency type constants (in Portuguese)
FREQUENCIA_TRIMESTRE_MOVEL = "trimestre_movel"
FREQUENCIA_MENSAL = "mensal"
FREQUENCIA_TRIMESTRAL = "trimestral"
FREQUENCIA_SEMESTRAL = "semestral"
FREQUENCIA_ANUAL = "anual"
FREQUENCIA_PLURIANUAL = "plurianual"
FREQUENCIA_NAO_RECONHECIDA = "nao_reconhecida"


# Define patterns for different period types

# Rolling Quarters
ROLLING_QUARTERS = "|".join(
    [
        "jan-fev-mar",
        "fev-mar-abr",
        "mar-abr-mai",
        "abr-mai-jun",
        "mai-jun-jul",
        "jun-jul-ago",
        "jul-ago-set",
        "ago-set-out",
        "set-out-nov",
        "out-nov-dez",
        "nov-dez-jan",
        "dez-jan-fev",
    ]
)
ROLLING_QUARTERS_PATTERN = f"^({ROLLING_QUARTERS})" + r"( de | )(\d{4})$"
ROLLING_QUARTERS_RE = re.compile(ROLLING_QUARTERS_PATTERN, re.IGNORECASE)

# Months
MONTHS_DICT = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}
MONTHS = "|".join(MONTHS_DICT.keys())
MONTHS_PATTERN = f"^({MONTHS})" + r"( de | )(\d{4})$"
MONTHS_RE = re.compile(MONTHS_PATTERN, re.IGNORECASE)

# Quarters
QUARTERS_PATTERN = r"^(\d{1})º trimestre( de | )(\d{4})$"
QUARTERS_RE = re.compile(QUARTERS_PATTERN, re.IGNORECASE)

# Semesters
SEMESTERS_PATTERN = r"^(\d{1})º semestre( de | )(\d{4})$"
SEMESTERS_RE = re.compile(SEMESTERS_PATTERN, re.IGNORECASE)

# Years (including year ranges)
YEARS_PATTERN = r"^(\d{4})(?:/(\d{4}))?$"
YEARS_RE = re.compile(YEARS_PATTERN)


def parse_period(periodo: dict[str, str]):
    period_id = periodo["id"]
    literals = periodo["literals"]

    # Try to match rolling quarters
    m = ROLLING_QUARTERS_RE.match(literals[0])
    if m:
        quarter_name = m.group(1).lower()
        year = int(m.group(3))

        # Map rolling quarters to start month
        quarter_start_months = {
            "jan-fev-mar": 1,
            "fev-mar-abr": 2,
            "mar-abr-mai": 3,
            "abr-mai-jun": 4,
            "mai-jun-jul": 5,
            "jun-jul-ago": 6,
            "jul-ago-set": 7,
            "ago-set-out": 8,
            "set-out-nov": 9,
            "out-nov-dez": 10,
            "nov-dez-jan": 11,
            "dez-jan-fev": 12,
        }

        start_month = quarter_start_months[quarter_name]
        start_date = dt.datetime(year, start_month, 1)
        end_date = _add_months(start_date, 3) - dt.timedelta(days=1)
        end_month = end_date.month

        return {
            "id": period_id,
            "literals": literals,
            "frequencia": FREQUENCIA_TRIMESTRE_MOVEL,
            "data_inicio": start_date,
            "data_fim": end_date,
            "ano": year,
            "mes": end_month,
        }

    # Try to match months
    m = MONTHS_RE.match(literals[0])
    if m:
        month_name = m.group(1).lower()
        year = int(m.group(3))
        month = MONTHS_DICT[month_name]

        start_date = dt.datetime(year, month, 1)
        end_date = _add_months(start_date, 1) - dt.timedelta(days=1)

        return {
            "id": period_id,
            "literals": literals,
            "frequencia": FREQUENCIA_MENSAL,
            "data_inicio": start_date,
            "data_fim": end_date,
            "ano": year,
            "mes":month,
        }

    # Try to match quarters
    m = QUARTERS_RE.match(literals[0])
    if m:
        quarter = int(m.group(1))
        year = int(m.group(3))

        start_month = (quarter - 1) * 3 + 1
        start_date = dt.datetime(year, start_month, 1)
        end_date = _add_months(start_date, 3) - dt.timedelta(days=1)

        return {
            "id": period_id,
            "literals": literals,
            "frequencia": FREQUENCIA_TRIMESTRAL,
            "data_inicio": start_date,
            "data_fim": end_date,
            "ano": year,
            "trimestre":quarter,
        }

    # Try to match semesters
    m = SEMESTERS_RE.match(literals[0])
    if m:
        semester = int(m.group(1))
        year = int(m.group(3))

        start_month = (semester - 1) * 6 + 1
        start_date = dt.datetime(year, start_month, 1)
        end_date = _add_months(start_date, 6) - dt.timedelta(days=1)

        return {
            "id": period_id,
            "literals": literals,
            "frequencia": FREQUENCIA_SEMESTRAL,
            "data_inicio": start_date,
            "data_fim": end_date,
            "ano": year,
            "semestre":semester,
        }

    # Try to match years
    m = YEARS_RE.match(literals[0])
    if m:
        year = int(m.group(1))
        end_year = int(m.group(2)) if m.group(2) else year

        start_date = dt.datetime(year, 1, 1)
        end_date = dt.datetime(end_year, 12, 31)

        frequency = (
            FREQUENCIA_ANUAL if year == end_year else FREQUENCIA_PLURIANUAL
        )

        return {
            "id": period_id,
            "literals": literals,
            "frequencia": frequency,
            "data_inicio": start_date,
            "data_fim": end_date,
            "ano": year,
            "ano_fim":end_year if year != end_year else None,
        }

    # If no pattern matches, mark as unrecognized
    return {
        "id": period_id,
        "literals": literals,
        "frequencia": FREQUENCIA_NAO_RECONHECIDA,
        "data_inicio": None,
        "data_fim": None,
    }


def parse_ddmmyyyy(date_str: str) -> dt.date:
    """Parse 'DD/MM/YYYY' date strings to date."""
    return dt.datetime.strptime(date_str, "%d/%m/%Y").date()
