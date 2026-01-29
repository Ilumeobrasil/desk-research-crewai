import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from desk_research.constants import VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.tools.ingestion_clean_tool import ingest_clean_folder_tool
from desk_research.tools.extract_insights_tool import extract_insights_tool

import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[4]

DATA_DIR = PROJECT_ROOT / "data"
INPUT_RAW_DIR = DATA_DIR / "input_raw"
OUTPUT_INGESTOR_DIR = DATA_DIR / "output_ingestor"
OUTPUT_EXTRACTOR_DIR = DATA_DIR / "output_extractor"

load_dotenv()

@dataclass(frozen=True)
class Paths:
    input_dir: str
    ingestor_output_dir: str
    extractor_output_dir: str


@dataclass(frozen=True)
class Settings:
    paths: Paths


def get_settings() -> Settings:
    input_dir = os.getenv("INGESTOR_INPUT_DIR") or str(INPUT_RAW_DIR)
    ingestor_output_dir = os.getenv("INGESTOR_OUTPUT_DIR") or str(OUTPUT_INGESTOR_DIR)
    extractor_output_dir = os.getenv("EXTRACTOR_OUTPUT_DIR") or str(OUTPUT_EXTRACTOR_DIR)

    return Settings(
        paths=Paths(
            input_dir=input_dir,
            ingestor_output_dir=ingestor_output_dir,
            extractor_output_dir=extractor_output_dir
        ),
    )


def _ensure_directory(path: str | Path) -> Path | str:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@CrewBase
class IngestorCrew:
    agents: list[Agent]
    tasks: list[Task]

    @agent
    def ingestor(self) -> Agent:
        return Agent(
            config=self.agents_config["ingestor"],
            tools=[ingest_clean_folder_tool],
            verbose=VERBOSE_AGENTS,
        )

    @agent
    def extractor(self) -> Agent:
        return Agent(
            config=self.agents_config["extractor"],
            tools=[extract_insights_tool],
            verbose=VERBOSE_AGENTS,
        )

    @task
    def ingest(self) -> Task:
        return Task(
            config=self.tasks_config["ingest"],
            agent=self.ingestor(),
            output_key="ingestion_result"
        )

    @task
    def extract_insights(self) -> Task:
        return Task(
            config=self.tasks_config["extract_insights"],
            agent=self.extractor(),
            output_key="extraction_result",
            context=[self.ingest()],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=VERBOSE_CREW,
        )


def _get_task_inputs(settings: Settings) -> dict[str, Any]:
    return {
        "ingest_input_dir": settings.paths.input_dir,
        "ingest_output_dir": settings.paths.ingestor_output_dir,
        "ingestor_output_dir": settings.paths.ingestor_output_dir,
        "extractor_output_dir": settings.paths.extractor_output_dir,
    }


def run_consumer_hours_ingestion() -> dict[str, Any]:
    settings = get_settings()

    _ensure_directory(settings.paths.input_dir)
    _ensure_directory(settings.paths.ingestor_output_dir)
    _ensure_directory(settings.paths.extractor_output_dir)

    crew_instance = IngestorCrew()
    crew = crew_instance.crew()
    inputs = _get_task_inputs(settings)

    result = crew.kickoff(inputs=inputs)

    return {
        "ok": True,
        "result": str(result),
        "input_dir": settings.paths.input_dir,
        "ingestor_output_dir": settings.paths.ingestor_output_dir,
        "extractor_output_dir": settings.paths.extractor_output_dir,
    }
