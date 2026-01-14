import sys
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from desk_research.utils.reporting import export_report
from desk_research.tools.youtube_tools import youtube_transcript_tool
from desk_research.tools.youtube_search_tools import youtube_video_search_tool

@CrewBase
class YouTubeCrew:
    '''Crew YouTube - Pesquisa e Análise de Conteúdo em Vídeo'''
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'


    def video_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['video_researcher'],

            verbose=True,
            tools=[youtube_video_search_tool]
        )

    @agent
    def youtube_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['youtube_analyst'],

            verbose=True,
            tools=[youtube_transcript_tool]
        )

    @task
    def search_videos_task(self) -> Task:
        return Task(
            config=self.tasks_config['search_videos_task'],
            agent=self.video_researcher()
        )

    @task
    def analyze_videos_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_videos_task'],
            agent=self.youtube_analyst(),
            context=[self.search_videos_task()]
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.video_researcher(), self.youtube_analyst()],
            tasks=[self.search_videos_task(), self.analyze_videos_task()],
            process=Process.sequential,
            verbose=True
        )

def run_youtube_analysis(topic: str):
    '''
    Executa análise YouTube de um tema
    '''
    inputs = {
        'topic': topic
    }
    
    crew = YouTubeCrew()
    # Metodo correto de chamada no CrewAI moderno
    result = crew.crew().kickoff(inputs=inputs)
    
    # Injetar Cabeçalho (Título e Data) conforme solicitado
    from datetime import datetime
    date_str = datetime.now().strftime("%d/%m/%Y")
    
    header = f"# Relatório de Análise YouTube: {topic}\n**Data da Pesquisa:** {date_str}\n\n"
    
    # Se result for objeto com .raw, atualizar .raw. Se for string, concatenar.
    if hasattr(result, 'raw'):
        result.raw = header + result.raw
    else:
        result = header + str(result)
    
    # Exportar relatório em PDF e MD
    export_report(result, topic, prefix="youtube_report")
    
    return result
