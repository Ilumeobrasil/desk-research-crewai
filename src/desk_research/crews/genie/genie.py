import sys
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from desk_research.utils.reporting import export_report


@CrewBase
class GenieCrew:
    '''Crew Genie - Análise Estratégica com Simulação de Focus Group'''
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'



    @agent
    def question_generator(self) -> Agent:
        return Agent(
            config=self.agents_config['question_generator'],

            verbose=True
        )

    @agent
    def focus_group_simulator(self) -> Agent:
        return Agent(
            config=self.agents_config['focus_group_simulator'],

            verbose=True
        )

    @agent
    def insight_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['insight_analyst'],

            verbose=True
        )

    # --- TASKS ---

    @task
    def generate_questions_task(self) -> Task:
        return Task(
            config=self.tasks_config['generate_questions_task'],
            agent=self.question_generator()
        )

    @task
    def focus_group_task(self) -> Task:
        return Task(
            config=self.tasks_config['focus_group_task'],
            agent=self.focus_group_simulator(),
            context=[self.generate_questions_task()]
        )

    @task
    def analyze_insights_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_insights_task'],
            agent=self.insight_analyst(),
            context=[self.focus_group_task()]
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.question_generator(), self.focus_group_simulator(), self.insight_analyst()],
            tasks=[self.generate_questions_task(), self.focus_group_task(), self.analyze_insights_task()],
            process=Process.sequential,
            verbose=True
        )


def run_genie_analysis(pergunta: str, contexto: str = ""):
    '''
    Executa análise Genie Híbrida (Perguntas -> Focus Group -> Insights)
    '''
    inputs = {
        'pergunta': pergunta,
        'contexto': contexto
    }
    
    crew = GenieCrew()
    result = crew.crew().kickoff(inputs=inputs)
    
    # Exportar relatório
    report_path = export_report(result, pergunta, prefix="genie_hybrid_report")
    
    return result

