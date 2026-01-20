import datetime
from typing import List, Dict, Any
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from desk_research.constants import VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.utils.reporting import export_report
from desk_research.tools.knowledge_bar_stravito_tools import knowledge_bar_stravito_tool

@CrewBase
class KnowledgeBarStravitoCrew:
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def knowledge_bar_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['knowledge_bar_researcher'],
            tools=[knowledge_bar_stravito_tool],
            verbose=VERBOSE_AGENTS,
        )

    @agent
    def follow_up_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['follow_up_researcher'],
            tools=[knowledge_bar_stravito_tool],
            verbose=VERBOSE_AGENTS,
        )

    @agent
    def content_analyzer(self) -> Agent:
        return Agent(
            config=self.agents_config['content_analyzer'],
            verbose=VERBOSE_AGENTS,
        )

    @agent
    def report_consolidator(self) -> Agent:
        return Agent(
            config=self.agents_config['report_consolidator'],
            verbose=VERBOSE_AGENTS,
        )

    @task
    def initial_research_task(self) -> Task:
        return Task(
            config=self.tasks_config['initial_research_task'],
            agent=self.knowledge_bar_researcher(),
        )

    @task
    def follow_up_research_task(self) -> Task:
        return Task(
            config=self.tasks_config['follow_up_research_task'],
            agent=self.follow_up_researcher(),
            context=[self.initial_research_task()],
        )

    @task
    def analyze_content_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_content_task'],
            agent=self.content_analyzer(),
            context=[self.initial_research_task(), self.follow_up_research_task()],
        )

    @task
    def create_consolidated_report_task(self) -> Task:
        return Task(
            config=self.tasks_config['create_consolidated_report_task'],
            agent=self.report_consolidator(),
            context=[
                self.initial_research_task(),
                self.follow_up_research_task(),
                self.analyze_content_task()
            ],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[
                self.knowledge_bar_researcher(),
                self.follow_up_researcher(),
                self.content_analyzer(),
                self.report_consolidator()
            ],
            tasks=[
                self.initial_research_task(),
                self.follow_up_research_task(),
                self.analyze_content_task(),
                self.create_consolidated_report_task()
            ],
            process=Process.sequential,
            verbose=VERBOSE_CREW,
        )

def run_knowledge_bar_stravito_research(query: str):
    """
    Executa pesquisa completa na Knowledge Bar Stravito, incluindo:
    - Pesquisa inicial sobre o tema
    - Pesquisas adicionais para cada follow-up sugerido
    - Análise e consolidação em relatório único
    
    Args:
        query: A query de pesquisa (tema ou keywords)
    
    Returns:
        Resultado da crew com relatório consolidado
    """
    inputs = {
        'query': query,
        'current_date': datetime.datetime.now().strftime('%d/%m/%Y')
    }
    
    crew = KnowledgeBarStravitoCrew()
    result = crew.crew().kickoff(inputs=inputs)
    
    export_report(
        result, 
        query, 
        prefix="knowledge_bar_stravito_report", 
        crew_name="knowledge_bar_stravito"
    )
    
    return result
