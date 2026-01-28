from typing import Any
from desk_research.constants import DEFAULT_MAX_PAPERS
from desk_research.crews.genie.genie import run_genie_analysis
from desk_research.crews.youtube.youtube import run_youtube_analysis
from desk_research.crews.academic.academic import run_academic_research
from desk_research.crews.web.web import run_web_research
from desk_research.crews.x.twitter_x_crew import run_twitter_social_listening
from desk_research.crews.consumer_hours_consumer.consumer_hours import run_consumer_hours_analysis
from desk_research.utils.logging_utils import safe_print


class CrewExecutor:
    @staticmethod
    def execute_with_error_handling(crew_name: str, executor_func, *args, **kwargs) -> Any:
        try:
            return executor_func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Erro na execucao do {crew_name}: {str(e)}"
            safe_print(f"❌ {error_msg}")
            return error_msg


class AcademicCrewExecutor(CrewExecutor):
    @staticmethod
    def run(topic: str, max_papers: int = DEFAULT_MAX_PAPERS) -> Any:
        return CrewExecutor.execute_with_error_handling(
            "Academic Crew",
            run_academic_research,
            topic=topic,
            max_papers=max_papers
        )


class WebCrewExecutor(CrewExecutor):
    @staticmethod
    def run(topic: str, max_results: int = 5) -> Any:
        return CrewExecutor.execute_with_error_handling(
            "Web Crew",
            run_web_research,
            query=topic,
            max_results=max_results
        )


class XCrewExecutor(CrewExecutor):
    @staticmethod
    def run(topic: str) -> Any:
        return CrewExecutor.execute_with_error_handling(
            "X Crew",
            run_twitter_social_listening,
            topic=topic
        )


class GenieCrewExecutor(CrewExecutor):
    @staticmethod
    def run(topic: str) -> Any:
        return CrewExecutor.execute_with_error_handling(
            "Genie Crew",
            run_genie_analysis,
            pergunta=topic
        )


class YouTubeCrewExecutor(CrewExecutor):
    @staticmethod
    def run(topic: str) -> Any:
        return CrewExecutor.execute_with_error_handling(
            "YouTube Crew",
            run_youtube_analysis,
            topic=topic
        )


class ConsumerHoursCrewExecutor(CrewExecutor):
    @staticmethod
    def run(topic: str) -> Any:
        return CrewExecutor.execute_with_error_handling(
            "Consumer Hours",
            run_consumer_hours_analysis,
            topic=topic
        )




