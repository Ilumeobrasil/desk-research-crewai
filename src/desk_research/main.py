import sys
import os
import builtins

from typing import Dict, Any, Literal

from crewai import Crew  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel # pyright: ignore[reportMissingImports]
from crewai.flow.flow import Flow, start, listen, and_, or_, router # pyright: ignore[reportMissingImports]
from datetime import datetime
from typing import List
from desk_research.utils.reporting import export_report

from desk_research.crews.genie.genie import run_genie_analysis
from desk_research.crews.youtube.youtube import run_youtube_analysis
from desk_research.crews.academic.academic import run_academic_research
from desk_research.crews.web.web import run_web_research
from desk_research.crews.x.twitter_x_crew import run_twitter_social_listening
from desk_research.crews.x.twitter_x_crew import run_twitter_social_listening
from desk_research.crews.consumer_hours.consumer_hours import run_consumer_hours_analysis
from desk_research.crews.integrated.integrated_analysis import IntegratedCrew

_original_print = builtins.print
def _safe_print_patch(*args, **kwargs):
    try:
        _original_print(*args, **kwargs)
    except AttributeError:
        pass
builtins.print = _safe_print_patch


ModosPesquisa = Literal["genie", "youtube", "academic", "web", "x", "integrated"]


def safe_print(msg):
    """Prints message safely handling rich/cell errors"""
    try:
        # Tenta usar sys.__stdout__ se disponivel para evitar hooks do rich
        if hasattr(sys, '__stdout__') and sys.__stdout__:
            sys.__stdout__.write(str(msg) + "\\n")
        else:
            print(msg)
    except Exception:
        pass # Silently ignore print errors to prevent crash

# ===== ESTADO & FLOW DO SISTEMA =====

class DeskResearchState(BaseModel):
    topic: str = ""
    selected_crews: List[str] = []
    params: Dict[str, Any] = {}
    results: Dict[str, Any] = {}
    final_report: str = ""
    # Self-Refine Utils
    retry_count: int = 0
    feedback: str = ""

class DeskResearchFlow(Flow[DeskResearchState]):

    @start()
    def initialize_research(self):
        safe_print(f"🚀 INICIANDO DESK RESEARCH FLOW...")
        
        # Hydrate state manually if not auto-populated
        if hasattr(self, 'inputs') and self.inputs:
             # print(f"📥 Recebido Inputs: {self.inputs.keys()}")
             self.state.topic = self.inputs.get('topic', self.state.topic)
             self.state.selected_crews = self.inputs.get('selected_crews', self.state.selected_crews)
             self.state.params = self.inputs.get('params', self.state.params)

        safe_print(f"📌 Tópico no State: {self.state.topic}")
        # print(f"📋 Crews Selecionadas: {self.state.selected_crews}")
        
        if not self.state.topic:
             safe_print("⚠️  AVISO: Tópico vazio! Verifique os inputs.")
             self.state.topic = "Pesquisa Genérica"

        self.state.results = {}
        return "initialized"

    @listen(initialize_research)
    def run_academic(self):
        if "academic" in self.state.selected_crews:
            print(f"\n🎓 Running Academic Crew...")
            try:
                res = run_academic_research(
                    topic=self.state.topic, 
                    max_papers=self.state.params.get('max_papers', 5)
                )
                self.state.results["academic"] = res
            except Exception as e:
                # print(f"❌ Erro no Academic: {e}")
                self.state.results["academic"] = f"Erro na execucao do Academic Crew: {str(e)}"
        else:
            safe_print("⏭️ Skipping Academic")

    @listen(initialize_research)
    def run_web(self):
        if "web" in self.state.selected_crews:
            print(f"\n🌐 Running Web Crew...")
            try:
                res = run_web_research(
                    query=self.state.topic, 
                    max_results=self.state.params.get('max_web_results', 5)
                )
                self.state.results["web"] = res
            except Exception as e:
                # print(f"❌ Erro no Web: {e}")
                self.state.results["web"] = f"Erro na execucao do Web Crew: {str(e)}"
        else:
            safe_print("⏭️ Skipping Web")

    @listen(initialize_research)
    def run_x(self):
        if "x" in self.state.selected_crews:
            print(f"\n🐦 Running X Crew...")
            try:
                res = run_twitter_social_listening(topic=self.state.topic)
                self.state.results["x"] = res
            except Exception as e:
                # print(f"❌ Erro no X: {e}")
                self.state.results["x"] = f"Erro na execucao do X Crew: {str(e)}"
        else:
            safe_print("⏭️ Skipping X")

    @listen(initialize_research)
    def run_genie(self):
        if "genie" in self.state.selected_crews:
            print(f"\n🧞 Running Genie...")
            try:
                res = run_genie_analysis(pergunta=self.state.topic)
                self.state.results["genie"] = res
            except Exception as e:
                # print(f"❌ Erro no Genie: {e}")
                self.state.results["genie"] = f"Erro na execucao do Genie Crew: {str(e)}"
        else:
            safe_print("⏭️ Skipping Genie")
            
    # YouTube
    @listen(initialize_research)
    def run_youtube(self):
        if "youtube" in self.state.selected_crews:
             print(f"\n📺 Running YouTube Crew...")
             try:
                # from desk_research.crews.youtube.youtube import run_youtube_analysis # Already imported at top level
                res = run_youtube_analysis(topic=self.state.topic)
                self.state.results["youtube"] = res
             except Exception as e:
                # print(f"❌ Erro no YouTube: {e}")
                self.state.results["youtube"] = f"Erro na execucao do YouTube Crew: {str(e)}"
        else:
             safe_print("⏭️ Skipping YouTube")

    # Consumer Hours
    @listen(initialize_research)
    def run_consumer_hours(self):
        if "consumer_hours" in self.state.selected_crews:
             print(f"\n⏳ Running Consumer Hours Crew...")
             try:
                res = run_consumer_hours_analysis()
                # O wrapper retorna string.
                self.state.results["consumer_hours"] = res
             except Exception as e:
                # print(f"❌ Erro no Consumer Hours: {e}")
                self.state.results["consumer_hours"] = f"Erro na execucao do Consumer Hours: {str(e)}"
        else:
             safe_print("⏭️ Skipping Consumer Hours")


    @listen(or_(and_(run_academic, run_web, run_x, run_genie, run_youtube, run_consumer_hours), "retry_synthesis"))
    def synthesize_report(self):
        print(f"\n✍️ SÍNTESE FINAL (Tentativa {self.state.retry_count + 1})")
        
        results_buffer = []
        for crew_id, res in self.state.results.items():
            content = str(res)
            if isinstance(res, dict):
                 content = res.get('report_markdown') or res.get('result') or str(res)
            results_buffer.append(f"=== RELATÓRIO {crew_id.upper()} ===\n{content}\n======================\n")

        all_reports_text = "\n".join(results_buffer)

        if not all_reports_text.strip():
            safe_print("⚠️ Nenhum relatório gerado para síntese.")
            return

        integ_crew = IntegratedCrew()
        task = integ_crew.synthesis_task()
        
        crew_runner = Crew(agents=[integ_crew.chief_editor_agent()], tasks=[task], verbose=True)
        
        inputs = {
            'topic': self.state.topic,
            'reports_context': all_reports_text,
            'feedback': self.state.feedback,
            'instruction': self.state.feedback,
            'date': datetime.now().strftime('%d/%m/%Y')
        }

        master_result = crew_runner.kickoff(inputs=inputs)
        self.state.final_report = str(master_result)
        
        return "report_generated"

    @listen(synthesize_report)
    def evaluate_report(self):
        print("\n⚖️ AVALIANDO QUALIDADE (Self-Refine)...")
        
        integ_crew = IntegratedCrew()
        task = integ_crew.evaluation_task()
        
        qa_crew = Crew(agents=[integ_crew.evaluator_agent()], tasks=[task], verbose=True)
        
        inputs = {
            "report_content": self.state.final_report
        }
        
        qa_result = qa_crew.kickoff(inputs=inputs)
        
        review = qa_result.pydantic or qa_result
        
        if hasattr(review, 'score'):
            score = review.score
            feedback = review.feedback
        else:
            score = 100
            feedback = "Approved (Fallback)"

        safe_print(f"📊 Nota: {score}/100")
        safe_print(f"📝 Feedback: {feedback}")
        
        if score >= 80:
            safe_print("✅ Relatório APROVADO!")
            self.state.feedback = "" 
            return "approved"
        else:
            safe_print("❌ Relatório REPROVADO. Solicitando melhorias...")
            self.state.feedback = feedback
            self.state.retry_count += 1
            return "rejected"

    @router(evaluate_report)
    def flow_control(self):
        if self.state.retry_count > 2:
            safe_print("⚠️ Limite de retries atingido.")
            return "max_retries"
        
        if self.state.feedback:
             return "retry_synthesis"
        
        return "approved"

    @listen("approved")
    def finalize_approved(self):
        self._export_final()

    @listen("max_retries")
    def finalize_forced(self):
        safe_print("⚠️ Finalizando com versão 'Best Effort'.")
        self._export_final()

    @listen("rejected")
    def retry_synthesis(self):
        pass

    def _export_final(self):
        print("\n📚 MONTANDO DOSSIÊ COMPLETO (MASTER + ANEXOS)...")
        
        try:
            # 1. Recuperar Relatório Master
            master_report = self.state.final_report
            if not master_report:
                print("⚠️  AVISO: Relatório Master vazio. Nada a exportar.")
                return ""

            # 2. Recuperar Relatórios Individuais
            results_buffer = []
            if self.state.results:
                for crew_id, res in self.state.results.items():
                    try:
                        content = ""
                        # Tratamento seguro de diferentes tipos de retorno
                        if isinstance(res, dict):
                             content = res.get('report_markdown') or res.get('result') or str(res)
                        elif hasattr(res, 'raw'):
                             content = getattr(res, 'raw', str(res))
                        elif isinstance(res, str):
                             content = res
                        else:
                             content = str(res)
                        
                        # Limpeza visual simples
                        content = content.replace("======================", "---")
                        
                        # Adicionar ao buffer
                        results_buffer.append(f"\n\n<div style='page-break-before: always;'></div>\n\n# 📚 ANEXO: RELATÓRIO {crew_id.upper()}\n\n{content}")
                    except Exception as e_inner:
                        print(f"⚠️  Erro ao processar anexo {crew_id}: {e_inner}")
                        results_buffer.append(f"\n\n# ERRO ANEXO {crew_id}\n(Falha ao processar conteúdo: {e_inner})")

            # 3. Concatenar tudo
            anexos_text = ""
            if results_buffer:
                anexos_text = "\n\n<div style='page-break-before: always;'></div>\n\n# 🗂️ ANEXOS: RELATÓRIOS INDIVIDUAIS\n\n"
                anexos_text += "Abaixo seguem os relatórios completos gerados por cada frente de pesquisa.\n"
                anexos_text += "".join(results_buffer)
            
            full_dossier = master_report + anexos_text

            # 4. Exportar Dossiê Completo
            export_report(full_dossier, self.state.topic, prefix="integrated_master")
            print("\n✅ FLOW FINALIZADO COM SUCESSO! (Dossiê Exportado)")
            return full_dossier

        except Exception as e:
            print(f"❌ ERRO CRÍTICO AO MONTAR DOSSIÊ: {e}")
            print("🔄 Tentando exportar apenas o Relatório Master (sem anexos)...")
            try:
                export_report(self.state.final_report, self.state.topic, prefix="integrated_master_FALLBACK")
                print("✅ Relatório Master (Fallback) exportado com sucesso.")
            except Exception as e2:
                print(f"❌ Falha total na exportação: {e2}")
            return self.state.final_report

# ===== PERGUNTAS PADRÃO =====
PERGUNTAS_PADRAO = {
    "geral": [
        "O jovem esta bebendo menos alcool? E cerveja?",
        "O consumidor associa luta a alguma marca de cerveja? Qual? Quais perfis demograficos e de interesse associam mais/menos?",
        "Scan no QR Code da tampinha de Brahma aumenta fidelidade/volume/frequencia?",
        "E verdade que as pessoas gostam mais de colocar limao na Coronita porque o sabor do limao fica mais concentrado?",
        "Quero entender melhor Eisenbahn. A marca esta em evolucao ou nao?"
    ]
}


class DeskResearchSystem:
    """Sistema principal que integra todos os modos de pesquisa"""

    def __init__(self):
        self.modos_disponiveis = {
            "genie": {
                "nome": "Análise de perguntas com IA",
                "emoji": "🧞",
                "descricao": "Análise inteligente de perguntas usando IA"
            },
            "youtube": {
                "nome": "Análise de vídeos do YouTube",
                "emoji": "📺",
                "descricao": "Análise profunda de conteúdo de vídeos"
            },
            "academic": {
                "nome": "Pesquisa Acadêmica",
                "emoji": "🎓",
                "descricao": "Busca em Semantic Scholar, arXiv e Google Scholar"
            },
            "web": {
                "nome": "Pesquisa Web",
                "emoji": "🌐",
                "descricao": "Busca geral na web com Google Search"
            },
            "x": {
                "nome": "Social Listening (X)",
                "emoji": "🐦",
                "descricao": "Monitoramento e análise de tendências no X (Twitter)"
            },
            "integrated": {
                "nome": "PESQUISA INTEGRADA (Multi-Agente)",
                "emoji": "🧠",
                "descricao": "Executa múltiplos agentes e gera relatório master consolidado"
            },
            "consumer_hours": {
                "nome": "Consumer Hours (Brand Audit)",
                "emoji": "⏳",
                "descricao": "Análise profunda de auditoria de marca (Consumer Hours Flow)"
            }
        }

    def listar_modos(self):
        """Lista todos os modos disponíveis"""
        print("\n" + "=" * 70)
        print("📋 MODOS DE PESQUISA DISPONÍVEIS")
        print("=" * 70)

        for i, (modo_id, info) in enumerate(self.modos_disponiveis.items(), 1):
            print(f"\n  [{i}] {info['emoji']} {info['nome']}")
            print(f"      ID: {modo_id}")
            print(f"      {info['descricao']}")

        print("\n" + "=" * 70)

    def selecionar_modo_interativo(self) -> str:
        """Permite ao usuário selecionar o modo interativamente"""
        self.listar_modos()

        modos_lista = list(self.modos_disponiveis.keys())

        while True:
            print("\n🔹 Escolha o modo de pesquisa:")
            escolha = input("   Digite o número [1-5] ou o ID do modo: ").strip().lower()

            # Verificar se é número
            if escolha.isdigit():
                idx = int(escolha) - 1
                if 0 <= idx < len(modos_lista):
                    modo_selecionado = modos_lista[idx]
                    break
            # Verificar se é ID direto
            elif escolha in self.modos_disponiveis:
                modo_selecionado = escolha
                break

            print("   ❌ Opção inválida! Tente novamente.")

        info = self.modos_disponiveis[modo_selecionado]
        print(f"\n✅ Modo selecionado: {info['emoji']} {info['nome']}")

        return modo_selecionado

    def selecionar_pergunta_padrao(self, modo: str) -> str:
        """Permite selecionar uma pergunta padrão ou digitar uma nova"""
        print("\n" + "-" * 50)
        print("❓ SELEÇÃO DE PERGUNTA")
        print("-" * 50)
        
        perguntas = PERGUNTAS_PADRAO.get("geral", [])
        
        for i, p in enumerate(perguntas, 1):
            print(f"  [{i}] {p}")
        
        print(f"  [{len(perguntas) + 1}] ✍️  Digitar nova pergunta")
        
        while True:
            escolha = input("\n👉 Escolha uma opção: ").strip()
            
            if escolha.isdigit():
                idx = int(escolha)
                if 1 <= idx <= len(perguntas):
                    return perguntas[idx-1]
                elif idx == len(perguntas) + 1:
                    return input("\n✍️  Digite sua pergunta: ").strip()
            
            print("❌ Opção inválida!")

    def coletar_parametros_genie(self) -> Dict[str, Any]:
        """Coleta parâmetros para análise Genie"""
        print("\n" + "=" * 70)
        print("🧞 CONFIGURAÇÃO - ANÁLISE GENIE")
        print("=" * 70)

        pergunta = self.selecionar_pergunta_padrao("genie")
        
        print("\n📝 Contexto Adicional (Opcional)")
        print("   Ex: 'Público alvo são jovens de 18-24 anos', 'Focar em concorrentes diretos'")
        contexto = input("   Digite o contexto (ou ENTER para pular): ").strip()

        return {
            "pergunta": pergunta,
            "contexto": contexto
        }

    def coletar_parametros_youtube(self) -> Dict[str, Any]:
        """Coleta parâmetros para análise YouTube"""
        print("\n" + "=" * 70)
        print("📺 CONFIGURAÇÃO - ANÁLISE YOUTUBE")
        print("=" * 70)

        topic = self.selecionar_pergunta_padrao("youtube")

        return {
            "topic": topic
        }

    def coletar_parametros_academic(self) -> Dict[str, Any]:
        """Coleta parâmetros para pesquisa acadêmica"""
        print("\n" + "=" * 70)
        print("🎓 CONFIGURAÇÃO - PESQUISA ACADÊMICA")
        print("=" * 70)

        topic = self.selecionar_pergunta_padrao("academic")
        
        max_papers_input = input("\n📊 Número máximo de papers [padrão: 10]: ").strip()
        max_papers = int(max_papers_input) if max_papers_input.isdigit() else 10

        return {
            "topic": topic,
            "max_papers": max_papers
        }

    def coletar_parametros_web(self) -> Dict[str, Any]:
        """Coleta parâmetros para pesquisa web"""
        print("\n" + "=" * 70)
        print("🌐 CONFIGURAÇÃO - PESQUISA WEB")
        print("=" * 70)

        query = self.selecionar_pergunta_padrao("web")
        
        max_results_input = input("\n📊 Número máximo de resultados [padrão: 10]: ").strip()
        max_results = int(max_results_input) if max_results_input.isdigit() else 10

        return {
            "query": query,
            "max_results": max_results
        }

    def coletar_parametros_x(self) -> Dict[str, Any]:
        """Coleta parâmetros para Social Listening no X"""
        print("\n" + "=" * 70)
        print("🐦 CONFIGURAÇÃO - SOCIAL LISTENING (X)")
        print("=" * 70)

        topic = self.selecionar_pergunta_padrao("x")

        return {
            "topic": topic
        }

    def coletar_parametros_consumer_hours(self) -> Dict[str, Any]:
        """Coleta parâmetros para Consumer Hours (sem params extras por enquanto)"""
        print("\n" + "=" * 70)
        print("⏳ CONFIGURAÇÃO - CONSUMER HOURS")
        print("=" * 70)
        print("\nℹ️  Este modo utiliza as configurações do arquivo .env e pastas locais.")
        input("\n👉 Pressione ENTER para iniciar a execução...")
        return {}

    def coletar_parametros_integrated(self) -> Dict[str, Any]:
        """Coleta parâmetros para Pesquisa Integrada"""
        print("\n" + "=" * 70)
        print("🧠 CONFIGURAÇÃO - PESQUISA INTEGRADA")
        print("=" * 70)

        # Seleção de Tema (Padronizado + Outro)
        print("\n📚 Tópicos Sugeridos:")
        for idx, pergunta in enumerate(PERGUNTAS_PADRAO["geral"], 1):
             print(f"  [{idx}] {pergunta}")
        print(f"  [{len(PERGUNTAS_PADRAO['geral']) + 1}] Outro (Digitar novo tema)")

        while True:
            choice = input("\n👉 Escolha uma opção: ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(PERGUNTAS_PADRAO["geral"]):
                    topic = PERGUNTAS_PADRAO["geral"][idx]
                    break
                elif idx == len(PERGUNTAS_PADRAO["geral"]):
                    topic = input("\n🎯 Digite o tema da pesquisa: ").strip()
                    break
            print("❌ Opção inválida. Tente novamente.")

        print(f"\n✅ Tema selecionado: {topic}")
        
        print("\n🤖 Selecione os agentes para ativar:")
        print("   [1] Genie (IA)")
        print("   [2] Academic (Papers)")
        print("   [3] YouTube (Vídeo)")
        print("   [4] Web (Busca)")
        print("   [5] X (Twitter)")
        print("   [6] Consumer Hours (Brand Audit)")
        
        selection = input("\n👉 Digite os números separados por vírgula (ex: 1,2,5): ").strip()
        
        # Mapeamento
        map_id = {
            '1': 'genie', 
            '2': 'academic', 
            '3': 'youtube', 
            '4': 'web', 
            '5': 'x',
            '6': 'consumer_hours'
        }
        selected_modos = []
        
        for num in selection.split(','):
            num = num.strip()
            if num in map_id:
                selected_modos.append(map_id[num])
        
        if not selected_modos:
            print("⚠️ Nenhuma seleção válida. Usando padrão: Genie + Web")
            selected_modos = ['genie', 'web']
        
        print(f"\n✅ Agentes ativados: {', '.join(selected_modos)}")
        
        return {
            "topic": topic,
            "selected_modos": selected_modos,
            "params": {
                "max_papers": 5, 
                "max_web_results": 5
            }
        }

    def executar_interativo(self) -> Any:
        """Executa o sistema de forma interativa"""
        # Selecionar modo
        modo = self.selecionar_modo_interativo()

        # Coletar parâmetros
        if modo == "genie":
            params = self.coletar_parametros_genie()
            result = self.executar_genie(**params)
        elif modo == "youtube":
            params = self.coletar_parametros_youtube()
            result = self.executar_youtube(**params)
        elif modo == "academic":
            params = self.coletar_parametros_academic()
            result = self.executar_academic(**params)
        elif modo == "web":
            params = self.coletar_parametros_web()
            result = self.executar_web(**params)
        elif modo == "x":
            params = self.coletar_parametros_x()
            result = self.executar_x(**params)
        elif modo == "integrated":
            params = self.coletar_parametros_integrated()
            result = self.executar_integrated(**params)
        elif modo == "consumer_hours":
            params = self.coletar_parametros_consumer_hours()
            result = self.executar_consumer_hours(**params)

        # Mensagem de sucesso
        print("\n" + "=" * 70)
        print("✅ PESQUISA CONCLUÍDA COM SUCESSO!")
        print("=" * 70)
        print(f"\n📋 Modo: {modo}")
        print(f"📊 Parâmetros: {params}")
        print(f"\n💾 Resultado disponível na variável 'result'")
        
        if isinstance(result, dict) and "resultado" in result:
             print("\n📝 RESUMO DO RESULTADO:")
             print(result["resultado"])

        return result

    # ===== MÉTODOS DE EXECUÇÃO =====

    def executar_genie(self, pergunta: str, contexto: str = "") -> Dict[str, Any]:
        """Executa análise Genie"""
        print(f"\n🧞 Iniciando análise Genie...")
        print(f"Pergunta: {pergunta}")
        if contexto:
            print(f"Contexto: {contexto}")
        print("")

        result = run_genie_analysis(pergunta=pergunta, contexto=contexto)

        return {
            "modo": "genie",
            "resultado": result,
            "metadados": {
                "pergunta": pergunta,
                "contexto": contexto
            }
        }

    def executar_youtube(self, topic: str) -> Dict[str, Any]:
        """Executa análise YouTube"""
        print(f"\n📺 Iniciando análise YouTube...")
        print(f"Tópico: {topic}\n")

        result = run_youtube_analysis(topic=topic)

        return {
            "modo": "youtube",
            "resultado": result,
            "metadados": {
                "topic": topic
            }
        }

    def executar_academic(self, topic: str, max_papers: int = 10) -> Dict[str, Any]:
        """Executa pesquisa acadêmica"""
        print(f"\n🎓 Iniciando pesquisa acadêmica...")
        print(f"Tópico: {topic}")
        print(f"Máximo de papers: {max_papers}\n")

        result = run_academic_research(topic=topic, max_papers=max_papers)

        return {
            "modo": "academic",
            "resultado": result,
            "metadados": {
                "topic": topic,
                "max_papers": max_papers
            }
        }

    def executar_web(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Executa pesquisa web"""
        print(f"\n🌐 Iniciando pesquisa web...")
        print(f"Query: {query}")
        print(f"Máximo de resultados: {max_results}\n")

        result = run_web_research(query=query, max_results=max_results)

        return {
            "modo": "web",
            "resultado": result,
            "metadados": {
                "query": query,
                "max_results": max_results
            }
        }

    def executar_x(self, topic: str) -> Dict[str, Any]:
        """Executa Social Listening no X"""
        print(f"\n🐦 Iniciando Social Listening no X...")
        print(f"Tema: {topic}\n")

        result = run_twitter_social_listening(topic=topic)

        return {
            "modo": "x",
            "resultado": result,
            "metadados": {
                "topic": topic
            }
        }

    def executar_consumer_hours(self) -> Dict[str, Any]:
        """Executa Consumer Hours"""
        print(f"\n⏳ Iniciando Consumer Hours...")
        
        try:
            result = run_consumer_hours_analysis()
            return {
                "modo": "consumer_hours",
                "resultado": result,
                "metadados": {}
            }
        except Exception as e:
            print(f"❌ Erro na execução: {e}")
            return {"erro": str(e)}

    def executar_integrated(self, topic: str, selected_modos: list, params: dict) -> Dict[str, Any]:
        """Executa Pesquisa Integrada via CrewAI FLOW"""
        print(f"\n🧠 Iniciando Pesquisa Integrada (FLOW)...")
        print(f"Tema: {topic}")
        print(f"Modos: {selected_modos}\n")
        
        try:
             # from desk_research.flow.flow import DeskResearchFlow # REMOVED: Now local
             
             # Instanciar Flow
             flow = DeskResearchFlow()
             
             inputs = {
                 "topic": topic,
                 "selected_crews": selected_modos,
                 "params": params
             }
             
             final_result = flow.kickoff(inputs=inputs)
             
             return {
                 "modo": "integrated",
                 "resultado": final_result,
                 "outputs_parciais": flow.state.results,
                 "metadados": inputs
             }
             
        except Exception as e:
            print(f"❌ Erro crítico no Flow: {e}")
            import traceback
            traceback.print_exc()
            return {"erro": str(e)}


def main():
    """Função principal - modo interativo"""
    print("\n" + "=" * 70)
    print("🚀 SISTEMA DESK RESEARCH - PESQUISA INTEGRADA AMBEV")
    print("=" * 70)

    system = DeskResearchSystem()
    result = system.executar_interativo()

    return result



# DISABLE TELEMETRY (Network fix)
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# ===== CLI ENTRY POINTS (CREWAI COMPATIBILITY) =====

def kickoff():
    """
    Entry point padrão para 'crewai run'.
    Redireciona para o modo interativo.
    """
    try:
        main()
    except Exception as e:
        print(f"Erro na execução: {e}")
        sys.exit(1)

def plot():
    """
    Entry point para 'crewai plot'.
    """
    print("⚠️  Plotting not yet implemented for integrated system.")

def train():
    """
    Entry point para 'crewai train'.
    """
    print("⚠️  Training not available for integrated system yet.")

def replay():
    """
    Entry point para 'crewai replay'.
    """
    print("⚠️  Replay not available for integrated system yet.")

def test():
    """
    Entry point para 'crewai test'.
    """
    print("⚠️  Testing not available for integrated system yet.")


if __name__ == "__main__":
    main()
