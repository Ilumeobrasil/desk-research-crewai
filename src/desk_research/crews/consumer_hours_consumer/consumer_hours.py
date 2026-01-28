import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from desk_research.constants import VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.tools.rag_search_tool import rag_search_tool
from desk_research.utils.reporting import export_report

import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_MODEL = "openai/gpt-4o"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 2000

load_dotenv()

@CrewBase
class ConsumerCrew:
    agents: list[Agent]
    tasks: list[Task]

    @agent
    def rag_searcher(self) -> Agent:
        return Agent(
            config=self.agents_config["rag_searcher"],
            tools=[rag_search_tool],
            verbose=VERBOSE_AGENTS,
        )
    
    @agent
    def writer(self) -> Agent:
        return Agent(
            config=self.agents_config["writer"],
            verbose=VERBOSE_AGENTS,
            reasoning=True,
            max_reasoning_attempts=3
        )

    @task
    def search_rag(self) -> Task:
        return Task(
            config=self.tasks_config["search_rag"],
            agent=self.rag_searcher(),
            output_key="rag_search_result"
        )
    
    @task
    def write(self) -> Task:
        return Task(
            config=self.tasks_config["write_report"],
            agent=self.writer(),
            output_key="report_markdown",
            context=[self.search_rag()],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=VERBOSE_CREW,
        )


def _get_task_inputs(topic: str) -> dict[str, Any]:
    return {
        "model": os.getenv("MODEL", DEFAULT_MODEL),
        "temperature": float(os.getenv("TEMPERATURE", str(DEFAULT_TEMPERATURE))),
        "max_tokens": int(os.getenv("MAX_TOKENS", str(DEFAULT_MAX_TOKENS))),
        "topic": topic,
    }


def run_consumer_hours_analysis(topic: str) -> dict[str, Any]:
    crew_instance = ConsumerCrew()
    crew = crew_instance.crew()
    inputs = _get_task_inputs(topic=topic)

    result = crew.kickoff(inputs=inputs)
    
    export_report(result, topic, prefix="consumer_hours", crew_name="consumer_hours_consumer")

    return {
        "topic": topic,
        "report_markdown": result,
    }
