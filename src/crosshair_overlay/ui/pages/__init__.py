"""UI pages package."""

from .creator_page import CreatorPage
from .beta_page import BetaPage
from .crosshair_detail_page import CrosshairDetailPage
from .crosshairs_page import CrosshairsPage
from .export_page import ExportPage
from .games_page import GamesPage
from .home_page import HomePage
from .settings_page import SettingsPage
from .about_page import AboutPage

__all__ = [
    "HomePage",
    "CrosshairsPage",
    "CrosshairDetailPage",
    "ExportPage",
    "AboutPage",
    "CreatorPage",
    "BetaPage",
    "GamesPage",
    "SettingsPage",
]
