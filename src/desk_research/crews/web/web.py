import sys
from pathlib import Path
import datetime

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from desk_research.tools.research_tools import google_search_tool, web_scraper_tool, url_validator_tool

from desk_research.utils.reporting import export_report

@CrewBase
class WebCrew:
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'


    def web_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['web_researcher'],
            tools=[
                google_search_tool,
                web_scraper_tool,
                url_validator_tool
            ],

            verbose=True
        )

    @agent
    def content_analyzer(self) -> Agent:
        return Agent(
            config=self.agents_config['content_analyzer'],

            verbose=True
        )

    @agent
    def web_report_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['web_report_writer'],

            verbose=True
        )

    @task
    def search_web(self) -> Task:
        return Task(
            config=self.tasks_config['search_web'],
            agent=self.web_researcher()
        )

    @task
    def analyze_content(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_content'],
            agent=self.content_analyzer()
        )

    @task
    def create_web_report(self) -> Task:
        return Task(
            config=self.tasks_config['create_web_report'],
            agent=self.web_report_writer()
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )

def run_web_research(query: str, max_results: int = 10):
    inputs = {
        'query': query,
        'max_results': max_results,
        'current_date': datetime.datetime.now().strftime('%d/%m/%Y')
    }
    
    crew = WebCrew()
    result = crew.crew().kickoff(inputs=inputs)
    
    export_report(result, query, prefix="web_report")
    
    return result
