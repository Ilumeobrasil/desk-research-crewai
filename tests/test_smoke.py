import pytest
import sys
import os

# Ensure src is in path for testing if not installed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from desk_research.main import DeskResearchSystem
from desk_research.crews.academic.academic import AcademicCrew
from desk_research.crews.web.web import WebCrew

from desk_research.crews.genie.genie import GenieCrew
from desk_research.crews.youtube.youtube import YouTubeCrew

def test_system_initialization():
    """Test if the main system class initializes correctly."""
    system = DeskResearchSystem()
    assert system is not None
    assert "integrated" in system.modos_disponiveis
    assert "academic" in system.modos_disponiveis

def test_academic_crew_import():
    """Test if AcademicCrew class is importable."""
    assert AcademicCrew is not None

def test_web_crew_import():
    """Test if WebCrew class is importable."""
    assert WebCrew is not None

def test_genie_crew_instantiation():
    """Test if GenieCrew can be instantiated (verifies config loading)."""
    crew = GenieCrew()
    assert crew is not None

def test_youtube_crew_instantiation():
    """Test if YouTubeCrew can be instantiated (verifies config loading)."""
    crew = YouTubeCrew()
    assert crew is not None

def test_twitter_crew_instantiation():
    """Test if TwitterSocialListeningCrew can be instantiated (verifies config loading)."""
    from desk_research.crews.x.twitter_x_crew import TwitterSocialListeningCrew
    crew = TwitterSocialListeningCrew()
    assert crew is not None
