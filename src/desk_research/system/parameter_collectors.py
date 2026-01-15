from typing import Dict, Any
from desk_research.constants import PERGUNTAS_PADRAO, DEFAULT_MAX_PAPERS, DEFAULT_MAX_WEB_RESULTS, MODE_SELECTION_MAP


class ParameterCollector:
    @staticmethod
    def selecionar_pergunta_padrao() -> str | None:
        print("\n" + "-" * 50)
        print("❓ SELEÇÃO DE PERGUNTA")
        print("-" * 50)
        
        perguntas = PERGUNTAS_PADRAO.get("geral", [])
        
        print(f"  [0] ⬅️  Voltar para opção anterior")
        for i, p in enumerate(perguntas, 1):
            print(f"  [{i}] {p}")
        
        print(f"  [{len(perguntas) + 1}] ✍️  Digitar nova pergunta")
        
        while True:
            escolha = input("\n👉 Escolha uma opção: ").strip()
            
            if escolha.isdigit():
                idx = int(escolha)
                if idx == 0:
                    return None
                elif 1 <= idx <= len(perguntas):
                    return perguntas[idx-1]
                elif idx == len(perguntas) + 1:
                    return input("\n✍️  Digite sua pergunta: ").strip()
            
            print("❌ Opção inválida!")


class GenieParameterCollector(ParameterCollector):
    @staticmethod
    def collect() -> Dict[str, Any] | None:
        print("\n" + "=" * 70)
        print("🧞 CONFIGURAÇÃO - ANÁLISE GENIE")
        print("=" * 70)

        pergunta = ParameterCollector.selecionar_pergunta_padrao()
        if pergunta is None:
            return None
        
        print("\n📝 Contexto Adicional (Opcional)")
        print("   Ex: 'Público alvo são jovens de 18-24 anos', 'Focar em concorrentes diretos'")
        contexto = input("   Digite o contexto (ou ENTER para pular): ").strip()

        return {"pergunta": pergunta, "contexto": contexto}


class YouTubeParameterCollector(ParameterCollector):
    @staticmethod
    def collect() -> Dict[str, Any] | None:
        print("\n" + "=" * 70)
        print("📺 CONFIGURAÇÃO - ANÁLISE YOUTUBE")
        print("=" * 70)

        topic = ParameterCollector.selecionar_pergunta_padrao()
        if topic is None:
            return None
        return {"topic": topic}


class AcademicParameterCollector(ParameterCollector):
    @staticmethod
    def collect() -> Dict[str, Any] | None:
        print("\n" + "=" * 70)
        print("🎓 CONFIGURAÇÃO - PESQUISA ACADÊMICA")
        print("=" * 70)

        topic = ParameterCollector.selecionar_pergunta_padrao()
        if topic is None:
            return None
        
        max_papers_input = input(f"\n📊 Número máximo de papers [padrão: {DEFAULT_MAX_PAPERS}]: ").strip()
        max_papers = int(max_papers_input) if max_papers_input.isdigit() else DEFAULT_MAX_PAPERS

        return {"topic": topic, "max_papers": max_papers}


class WebParameterCollector(ParameterCollector):
    @staticmethod
    def collect() -> Dict[str, Any] | None:
        print("\n" + "=" * 70)
        print("🌐 CONFIGURAÇÃO - PESQUISA WEB")
        print("=" * 70)

        query = ParameterCollector.selecionar_pergunta_padrao()
        if query is None:
            return None
        
        max_results_input = input(f"\n📊 Número máximo de resultados [padrão: {DEFAULT_MAX_WEB_RESULTS}]: ").strip()
        max_results = int(max_results_input) if max_results_input.isdigit() else DEFAULT_MAX_WEB_RESULTS

        return {"query": query, "max_results": max_results}


class XParameterCollector(ParameterCollector):
    @staticmethod
    def collect() -> Dict[str, Any] | None:
        print("\n" + "=" * 70)
        print("🐦 CONFIGURAÇÃO - SOCIAL LISTENING (X)")
        print("=" * 70)

        topic = ParameterCollector.selecionar_pergunta_padrao()
        if topic is None:
            return None
        return {"topic": topic}


class ConsumerHoursParameterCollector(ParameterCollector):
    @staticmethod
    def collect() -> Dict[str, Any]:
        print("\n" + "=" * 70)
        print("⏳ CONFIGURAÇÃO - CONSUMER HOURS")
        print("=" * 70)
        print("\nℹ️  Este modo utiliza as configurações do arquivo .env e pastas locais.")
        input("\n👉 Pressione ENTER para iniciar a execução...")
        return {}


class IntegratedParameterCollector(ParameterCollector):
    @staticmethod
    def collect() -> Dict[str, Any] | None:
        print("\n" + "=" * 70)
        print("🧠 CONFIGURAÇÃO - PESQUISA INTEGRADA")
        print("=" * 70)

        topic = ParameterCollector.selecionar_pergunta_padrao()
        if topic is None:
            return None
        
        selected_modos = IntegratedParameterCollector._select_modes()
        if selected_modos is None:
            return None
        
        return {
            "topic": topic,
            "selected_modos": selected_modos,
            "params": {
                "max_papers": DEFAULT_MAX_PAPERS,
                "max_web_results": DEFAULT_MAX_WEB_RESULTS
            }
        }

    @staticmethod
    def _select_modes() -> list | None:
        print("\n🤖 Selecione os agentes para ativar:")
        print("   [0] Todos os agentes")
        print("   [1] Genie (IA)")
        print("   [2] Academic (Papers)")
        print("   [3] YouTube (Vídeo)")
        print("   [4] Web (Busca)")
        print("   [5] X (Twitter)")
        print("   [6] Consumer Hours (Brand Audit)")
        
        selection = input("\n👉 Digite os números separados por vírgula (ex: 1,2,5): ").strip()
        
        if selection == "0":
            return MODE_SELECTION_MAP.values()
        
        selected_modos = []
        for num in selection.split(','):
            num = num.strip()
            if num in MODE_SELECTION_MAP:
                selected_modos.append(MODE_SELECTION_MAP[num])
        
        if not selected_modos:
            print("⚠️ Nenhuma seleção válida. Usando padrão: Genie + Web")
            selected_modos = ['genie', 'web']
        
        print(f"\n✅ Agentes ativados: {', '.join(selected_modos)}")
        return selected_modos


