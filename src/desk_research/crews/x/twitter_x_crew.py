from typing import Any, Dict, List
from datetime import datetime

from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew

from desk_research.constants import VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.tools.x_tools import twitter_search_tool
from desk_research.utils.reporting import export_report

import logging

logger = logging.getLogger(__name__)
@CrewBase
class TwitterSocialListeningCrew:
    agents: List[Agent]
    tasks: List[Task]

    @agent
    def planner_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['planner_agent'],
            verbose=VERBOSE_AGENTS,
        )

    @agent
    def researcher_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher_agent'],
            tools=[twitter_search_tool],
            verbose=VERBOSE_AGENTS,
        )

    @agent
    def analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['analyst_agent'],
            verbose=VERBOSE_AGENTS,
        )

    @agent
    def writer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['writer_agent'],
            verbose=VERBOSE_AGENTS,
            allow_delegation=False,
        )

    @task
    def plan_research_task(self) -> Task:
        return Task(
            config=self.tasks_config['plan_research_task'],
            agent=self.planner_agent(),
            output_key="research_plan",
            verbose=True,
        )

    @task
    def collect_tweets_task(self) -> Task:
        return Task(
            config=self.tasks_config['collect_tweets_task'],
            agent=self.researcher_agent(),
            output_key="tweets_raw",
            context=[self.plan_research_task()]
        )

    @task
    def analyze_insights_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_insights_task'],
            agent=self.analyst_agent(),
            output_key="insights_json",
            context=[self.collect_tweets_task()]
        )

    @task
    def write_report_task(self) -> Task:
        return Task(
            config=self.tasks_config['write_report_task'],
            agent=self.writer_agent(),
            output_key="report_markdown",
            context=[self.analyze_insights_task()]
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=VERBOSE_CREW,
        )

def run_twitter_social_listening(topic: str) -> Dict[str, Any]:
    try:
        crew_instance = TwitterSocialListeningCrew()

        crew = crew_instance.crew()

        inputs = {
            "topic": topic,
            "date": datetime.now().strftime("%d/%m/%Y")
        }

        result = crew.kickoff(inputs=inputs)
        
        export_report(result, topic, prefix="x_social_listening", crew_name="x")
        
        return {
            "topic": topic,
            "report_markdown": result,
        }
    except Exception as e:
        logger.error(f"Erro ao executar social listening: {e}", exc_info=True)
        raise