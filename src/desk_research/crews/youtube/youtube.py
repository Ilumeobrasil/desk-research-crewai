import logging

from typing import List
from datetime import datetime
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from desk_research.constants import VERBOSE_AGENTS, VERBOSE_CREW
from desk_research.utils.reporting import export_report
from desk_research.tools.youtube_tools import youtube_transcript_tool
from desk_research.tools.youtube_search_tools import youtube_video_search_tool

logger = logging.getLogger(__name__)

@CrewBase
class YouTubeCrew:
    agents: List[Agent]
    tasks: List[Task]

    @agent
    def video_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['video_researcher'],
            tools=[youtube_video_search_tool],
            verbose=VERBOSE_AGENTS,
        )

    @agent
    def youtube_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['youtube_analyst'],
            tools=[youtube_transcript_tool],
            verbose=VERBOSE_AGENTS,
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
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=VERBOSE_CREW
        )

def run_youtube_analysis(topic: str):
    try:
        crew_instance = YouTubeCrew()
        crew = crew_instance.crew()

        inputs = {
            "topic": topic,
            "date": datetime.now().strftime("%d/%m/%Y")
        }

        result = crew.kickoff(inputs=inputs)
            
        export_report(result, topic, prefix="youtube_report", crew_name="youtube")
        
        return {
            "topic": topic,
            "report_markdown": result,
        }
    except Exception as e:
        logger.error(f"Erro ao executar análise YouTube: {e}", exc_info=True)
        raise
