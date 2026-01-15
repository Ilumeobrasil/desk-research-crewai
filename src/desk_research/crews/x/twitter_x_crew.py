# twitter_x_crew.py
from __future__ import annotations

from typing import Any, Dict
from datetime import datetime

from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew


from desk_research.tools.x_tools import twitter_search_tool
from desk_research.utils.reporting import export_report


@CrewBase
class TwitterSocialListeningCrew:
    """
    Crew de social listening em X (Twitter) para temas/marcas da Ambev.
    """
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'


    # AGENTES
    # =========================

    @agent
    def planner_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['planner_agent'],

            verbose=True,
        )

    @agent
    def researcher_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher_agent'],
            tools=[twitter_search_tool],

            verbose=True,
        )

    @agent
    def analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['analyst_agent'],

            verbose=True,
        )

    @agent
    def writer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['writer_agent'],

            verbose=True,
        )

    # =========================
    # TASKS
    # =========================

    @task
    def plan_research_task(self) -> Task:
        return Task(
            config=self.tasks_config['plan_research_task'],
            agent=self.planner_agent(),
            output_key="research_plan",
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

    # =========================
    # CREW
    # =========================

    @crew
    def crew(self) -> Crew:
        """
        Monta e devolve a Crew configurada para um tema.
        """
        return Crew(
            agents=[
                self.planner_agent(),
                self.researcher_agent(),
                self.analyst_agent(),
                self.writer_agent(),
            ],
            tasks=[
                self.plan_research_task(),
                self.collect_tweets_task(),
                self.analyze_insights_task(),
                self.write_report_task()
            ],
            process=Process.sequential,
            verbose=True,
        )


# =========================
# Função de alto nível
# =========================

def run_twitter_social_listening(topic: str) -> Dict[str, Any]:
    """
    Função de entrada única para usar essa crew via main_interativo
    ou via outros módulos (ex.: main_interativo do Desk Research).

    Retorna um dicionário com:
      - "topic"
      - "report_markdown"
    """
    crew_instance = TwitterSocialListeningCrew()
    # Crew agora é instanciada sem argumentos de tarefa, inputs vão no kickoff
    crew = crew_instance.crew()

    inputs = {
        "topic": topic,
        "date": datetime.now().strftime("%d/%m/%Y")
    }

    result = crew.kickoff(inputs=inputs)
    
    # Exportar relatório
    export_report(result, topic, prefix="x_social_listening", crew_name="x")
    
    return {
        "topic": topic,
        "report_markdown": result,
    }
