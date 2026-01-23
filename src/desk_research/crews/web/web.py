import datetime
import json
import time

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from desk_research.constants import VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.tools.research_tools import google_search_tool, web_scraper_tool, url_validator_tool
from desk_research.utils.makelog.makeLog import make_log
from desk_research.utils.reporting import export_report

@CrewBase
class WebCrew:
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def web_researcher_url(self) -> Agent:
        return Agent(
            config=self.agents_config['web_researcher_url'],
            tools=[
                google_search_tool,
                url_validator_tool
            ],
            verbose=True
        )

    @agent
    def web_researcher_content(self) -> Agent:
        return Agent(
            config=self.agents_config['web_researcher_content'],
            tools=[
                web_scraper_tool,
            ],
            verbose=True
        )

    """ @agent
    def content_analyzer(self) -> Agent:
        return Agent(
            config=self.agents_config['content_analyzer'],
            verbose=VERBOSE_AGENTS,
            tools=[
                web_scraper_tool,
            ]
        ) """

    @agent
    def web_report_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['web_report_writer'],
            verbose=VERBOSE_AGENTS
        )

    @task
    def search_web_urls(self) -> Task:
        return Task(
            config=self.tasks_config['search_web_urls'],
            agent=self.web_researcher_url()
        )

    @task
    def extract_web_content(self) -> Task:
        return Task(
            config=self.tasks_config['extract_web_content'],
            agent=self.web_researcher_content()
        )

    """ @task
    def classify_organize_content(self) -> Task:
        return Task(
            config=self.tasks_config['classify_organize_content'],
            context=[self.search_web()],
            agent=self.content_analyzer()
        ) """

    @task
    def evidence_consolidation_task(self) -> Task:
        return Task(
            config=self.tasks_config['evidence_consolidation_task'],
            context=[self.extract_web_content()],
            agent=self.web_report_writer()
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=VERBOSE_CREW
        )

def run_web_research(query: str, max_results: int = 10):
    try:    
        inputs = {
            'query': query,
            'max_results': max_results,
            'max_results_extractions': max_results + 5,
            'current_date': datetime.datetime.now().strftime('%d/%m/%Y')
        }
        
        crew = WebCrew()
        
        #remover
        print("RODANDO WEB")
        start_time = time.time()

        result = crew.crew().kickoff(inputs=inputs)
        
        #remover
        end_time = time.time()
        execution_time = end_time - start_time
        minutes = int(execution_time // 60)
        seconds = int(execution_time % 60)
        if minutes > 0:
            print(f"TERMINOU WEB - Tempo de execução: {minutes}m {seconds}s")
        else:
            print(f"TERMINOU WEB - Tempo de execução: {seconds}s")
   # Este documento NÃO contém respostas, análises ou conclusões.
        make_log({
            "logName": f"web_research",
            "content": {
                "result": result,
                "query": query,
                "max_results": max_results,
                "current_date": datetime.datetime.now().strftime('%d/%m/%Y')
            }
        })
        
        export_report(result, query, prefix="web_report", crew_name="web")
        
        return result
    except Exception as e:
        print(f"Error running web research: {e}")
        return None
