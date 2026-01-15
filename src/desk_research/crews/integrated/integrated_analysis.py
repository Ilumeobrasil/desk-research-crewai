from __future__ import annotations

import sys
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

from crewai import Agent, Task, Crew, Process, LLM
from crewai.project import CrewBase, agent, task, crew

# Imports dos crews individuais
from desk_research.crews.genie.genie import run_genie_analysis
from desk_research.crews.youtube.youtube import run_youtube_analysis
from desk_research.crews.academic.academic import run_academic_research
from desk_research.crews.web.web import run_web_research
from desk_research.crews.x.twitter_x_crew import run_twitter_social_listening

from pydantic import BaseModel, Field

class QualityReview(BaseModel):
    """Modelo de saída da avaliação de qualidade."""
    score: int = Field(default=0, description="Nota de 0 a 100 para a qualidade do relatório.")
    feedback: str = Field(default="Sem feedback fornecido.", description="Críticas construtivas e pontos específicos de melhoria.")
    approved: bool = Field(default=False, description="Se a nota for >= 80, aprovado. Caso contrário, reprovado.")

@CrewBase
class IntegratedCrew:
    """
    Crew 'Editor-Chefe' responsável por sintetizar relatórios de múltiplas fontes.
    """
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def chief_editor_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['chief_editor_agent'],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def evaluator_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['evaluator_agent'],
            verbose=True,
            allow_delegation=False
        )

    @task
    def synthesis_task(self) -> Task:
        return Task(
            config=self.tasks_config['synthesis_task'],
            agent=self.chief_editor_agent()
        )

    @task
    def evaluation_task(self) -> Task:
        return Task(
            config=self.tasks_config['evaluation_task'],
            agent=self.evaluator_agent(),
            output_pydantic=QualityReview
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.chief_editor_agent()],
            tasks=[self.synthesis_task()], # Initial task, others can be added dynamically if needed
            process=Process.sequential,
            verbose=True
        )

def run_integrated_research(topic: str, selected_modos: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orquestrador que roda os crews selecionados e depois a síntese.
    
    Args:
        topic: Tema da pesquisa.
        selected_modos: Lista de IDs dos modos (ex: ['academic', 'x', 'genie']).
        params: Parâmetros globais (ex: max_results).
    """
    sys.stderr.write(f"\n🚀 INICIANDO PESQUISA INTEGRADA: {topic}\n")
    sys.stderr.write(f"📋 Modos selecionados: {selected_modos}\n")

    results_buffer = []
    
    # 1. Execução Sequencial dos Crews Selecionados
    # (Poderia ser paralela no futuro com ThreadPoolExecutor)

    if 'genie' in selected_modos:
        sys.stderr.write("\n>>> Executando Genie...\n")
        try:
            res = run_genie_analysis(pergunta=topic)
            results_buffer.append(f"=== RELATÓRIO GENIE ===\n{res}\n======================\n")
        except Exception as e:
            sys.stderr.write(f"❌ Erro no Genie: {e}\n")
            results_buffer.append(f"=== ERRO GENIE ===\n{e}\n")

    if 'academic' in selected_modos:
        sys.stderr.write("\n>>> Executando Academic...\n")
        try:
            # Adaptando retorno que pode ser dict ou obj
            res_dict = run_academic_research(topic=topic, max_papers=params.get('max_papers', 5))
            # Extrair texto do resultado
            content = res_dict.get('result', str(res_dict))
            results_buffer.append(f"=== RELATÓRIO ACADÊMICO ===\n{content}\n======================\n")
        except Exception as e:
            sys.stderr.write(f"❌ Erro no Academic: {e}\n")
            results_buffer.append(f"=== RELATÓRIO ACADÊMICO ===\n(Erro: {e})\n")

    if 'youtube' in selected_modos:
        sys.stderr.write("\n>>> Executando YouTube...\n")
        try:
            res = run_youtube_analysis(topic=topic)
            results_buffer.append(f"=== RELATÓRIO YOUTUBE ===\n{res}\n======================\n")
        except Exception as e:
            sys.stderr.write(f"❌ Erro no YouTube: {e}\n")
            results_buffer.append(f"=== RELATÓRIO YOUTUBE ===\n(Erro: {e})\n")

    if 'web' in selected_modos:
        sys.stderr.write("\n>>> Executando Web...\n")
        try:
            res = run_web_research(query=topic, max_results=params.get('max_web_results', 5))
            results_buffer.append(f"=== RELATÓRIO WEB ===\n{res}\n======================\n")
        except Exception as e:
            sys.stderr.write(f"❌ Erro no Web: {e}\n")

    if 'x' in selected_modos:
        sys.stderr.write("\n>>> Executando Social Listening (X)...\n")
        try:
            res_dict = run_twitter_social_listening(topic=topic)
            content = res_dict.get('report_markdown', str(res_dict))
            results_buffer.append(f"=== RELATÓRIO X (TWITTER) ===\n{content}\n======================\n")
        except Exception as e:
             sys.stderr.write(f"❌ Erro no X: {e}\n")

    # 2. Síntese Final (Editor-Chefe)
    sys.stderr.write("\n✍️ INICIANDO SÍNTESE FINAL (EDITOR-CHEFE)...\n")
    
    all_reports_text = "\n".join(results_buffer)
    
    if not all_reports_text.strip():
        return {"error": "Nenhum relatório foi gerado pelos crews selecionados."}

    # 2. Síntese Final (Editor-Chefe)
    sys.stderr.write("\n✍️ INICIANDO SÍNTESE FINAL (EDITOR-CHEFE)...\n")
    
    all_reports_text = "\n".join(results_buffer)
    
    if not all_reports_text.strip():
        return {"error": "Nenhum relatório foi gerado pelos crews selecionados."}

    inputs = {
        'topic': topic,
        'reports_context': all_reports_text,
        'date': datetime.now().strftime('%d/%m/%Y'),
        'instruction': "" # Instrução de feedback/retry vazia por padrão
    }

    # Instanciar e rodar o crew integrado
    integrated_crew = IntegratedCrew()
    master_result = integrated_crew.crew().kickoff(inputs=inputs)
    
    # --- CONSOLIDAÇÃO DO DOSSIÊ (MASTER + INDIVIDUAIS) ---
    # Extrair texto do Master
    master_text = ""
    if hasattr(master_result, 'raw'):
        master_text = master_result.raw
    elif hasattr(master_result, 'tasks_output') and master_result.tasks_output:
        master_text = master_result.tasks_output[-1].raw
    else:
        master_text = str(master_result)

    # Preparar Anexos (Convertendo marcadores para Markdown melhorado se possível)
    anexos_text = "\n\n<div style='page-break-before: always;'></div>\n\n# 📚 ANEXOS: RELATÓRIOS INDIVIDUAIS\n\n"
    anexos_text += "Abaixo seguem os relatórios completos gerados por cada frente de pesquisa.\n\n"
    
    for res in results_buffer:
        # Tenta melhorar a formatação removendo as linhas de === se existirem
        clean_res = res.replace("======================", "---")
        anexos_text += f"\n{clean_res}\n"

    full_dossier = master_text + anexos_text

    # Exportar Relatório Master Completo (PDF + MD)
    from desk_research.utils.reporting import export_report
    export_report(full_dossier, topic, prefix="integrated_master", crew_name="integrated_analysis")
    
    return {
        "topic": topic,
        "master_report": master_result,
        "individual_results": results_buffer
    }
