import json
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path
from typing import Tuple, Union

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from plugins.reports.graphs.bp.graphs import BrasilParticipativoGraphs
from plugins.reports.graphs.matomo.graphs import MatomoGraphs
from plugins.reports.tables.bp.tables import BrasilParticipativoTables


class Report:
    """
    Represents a report generator.

    Args:
    ----
        report_name (str): The name of the report.
        template_path (Union[str, Path]): The path to the template file or a `Path` object.
        start_date (datetime): The start date for the report.
        end_date (datetime): The end date for the report.

    Attributes:
    ----------
        css_file (Path): The path to the CSS file for styling.
        template (Template): The Jinja2 template used for rendering the report.
        report_name (str): The name of the report.
        start_date (str): The formatted start date for the report (dd/mm/YYYY).
        end_date (str): The formatted end date for the report (dd/mm/YYYY).
        bp_graphs (BrasilParticipativoGraphs): Instance of BrasilParticipativoGraphs class.
        matomo_graphs (MatomoGraphs): Instance of MatomoGraphs class.

    Methods:
    -------
        create_report_pdf(**kwargs):
            Generates a PDF report and returns the byte data.

        render_template(**kwargs):
            Raises NotImplementedError.

    Args:
    ----
        **kwargs: Additional keyword arguments to be passed to the template rendering.

    Returns:
    -------
        bytes: The byte data of the generated PDF.

    """

    def __init__(
        self,
        report_name: str,
        template_path: Union[str, Path],
        start_date: datetime,
        end_date: datetime,
    ) -> None:
        template_path = Path(template_path)
        self.css_file = template_path.parent.joinpath("./css/styles.css")
        self.template = Environment(loader=FileSystemLoader(template_path.parent)).get_template(
            template_path.name
        )

        self.report_name = report_name
        self.start_date = start_date.strftime("%d/%m/%Y")
        self.end_date = end_date.strftime("%d/%m/%Y")

        self.bp_tables = BrasilParticipativoTables()
        self.bp_graphs = BrasilParticipativoGraphs()
        self.matomo_graphs = MatomoGraphs()
        self.bp_tables = BrasilParticipativoTables()

    def create_report_pdf(self, **kwargs):
        """
        Generates a PDF report and returns the byte data.

        Args:
        ----
            **kwargs: Additional keyword arguments to be passed to the template rendering.

        Returns:
        -------
            bytes: The byte data of the generated PDF.
        """
        rendered_html = self.render_template(**kwargs)

        pdf_bytes = BytesIO()
        HTML(string=rendered_html).write_pdf(target=pdf_bytes, stylesheets=[self.css_file.as_posix()])
        pdf_bytes.seek(0)

        return pdf_bytes.getvalue()

    def render_template(self, **kwargs):
        """Raises NotImplementedError."""
        raise NotImplementedError

    def get_population_data(self) -> dict:
        current_script_path = Path(__file__).parent.parent
        population_json_path = current_script_path / "graphs/matomo/geo/population_uf.json"
        with population_json_path.open("r") as f:
            population_data = json.load(f)
        return population_data["population_estado"]

    def get_state_proportion_data(
        self, matomo_user_country_csv: str, matomo_user_region_csv: str
    ) -> Tuple[str, str, str]:
        region_visits = pd.read_csv(StringIO(matomo_user_region_csv))
        region_visits = region_visits[region_visits["metadata_country"] == "br"].rename(
            columns={"metadata_region_name": "UF"}
        )

        country_visits = pd.read_csv(StringIO(matomo_user_country_csv))
        total_brazil_visits = country_visits.loc[
            country_visits["metadata_code"] == "br", "sum_daily_nb_uniq_visitors"
        ].iloc[0]

        population_data = self.get_population_data()
        region_visits["access_ratio"] = region_visits.apply(
            lambda x: (x["sum_daily_nb_uniq_visitors"] / total_brazil_visits)
            * 100
            / population_data[x["UF"]],
            axis=1,
        )

        max_state = region_visits.loc[region_visits["access_ratio"].idxmax()]["UF"]
        min_state = region_visits.loc[region_visits["access_ratio"].idxmin()]["UF"]
        one_state = region_visits.iloc[(region_visits["access_ratio"] - 1).abs().argsort()[:1]]["UF"].values[
            0
        ]

        return max_state, min_state, one_state
