# 🚀 Como Criar Novos Crews

Guia simples e direto para adicionar novos crews ao sistema de pesquisa integrada.

## 📋 Visão Geral

Quando você cria um novo crew, precisa integrá-lo em 5 lugares principais:

1. **Criar o crew** (a lógica principal)
2. **Criar o executor** (para o Flow)
3. **Criar o coletor de parâmetros** (para a interface interativa)
4. **Registrar nas constantes** (configuração)
5. **Registrar no sistema** (orquestração)

Vamos fazer isso passo a passo! 🎯

---

## 📁 Passo 1: Criar a Estrutura de Pastas

Primeiro, crie a pasta do seu novo crew:

```bash
src/desk_research/crews/seu_novo_crew/
├── __init__.py
├── seu_novo_crew.py
└── config/
    ├── agents.yaml
    └── tasks.yaml
```

**Dica:** Use nomes em minúsculas com underscore (ex: `reddit_analysis`, `news_research`).

---

## 🔧 Passo 2: Criar o Crew Principal

Crie o arquivo `seu_novo_crew.py` seguindo este padrão:

```python
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from desk_research.utils.reporting import export_report

@CrewBase
class SeuNovoCrew:
    '''Descrição do que seu crew faz'''
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def seu_agente(self) -> Agent:
        return Agent(
            config=self.agents_config['seu_agente'],
            verbose=True
        )

    @task
    def sua_tarefa(self) -> Task:
        return Task(
            config=self.tasks_config['sua_tarefa'],
            agent=self.seu_agente()
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.seu_agente()],
            tasks=[self.sua_tarefa()],
            process=Process.sequential,
            verbose=True
        )


def run_seu_novo_crew(topic: str, parametro_extra: int = 10):
    '''
    Função principal que executa o crew.
    
    Args:
        topic: Tópico principal da pesquisa
        parametro_extra: Parâmetro opcional (ajuste conforme necessário)
    '''
    inputs = {
        'topic': topic,
        'parametro_extra': parametro_extra
    }
    
    crew = SeuNovoCrew()
    result = crew.crew().kickoff(inputs=inputs)
    
    export_report(result, topic, prefix="seu_novo_crew_report", crew_name="seu_novo_crew")
    
    return result
```

**Importante:** A função `run_seu_novo_crew` é o ponto de entrada que será chamado pelo sistema.

---

## ⚙️ Passo 3: Criar o Executor

Adicione seu executor em `src/desk_research/flow/crew_executors.py`:

```python
from desk_research.crews.seu_novo_crew.seu_novo_crew import run_seu_novo_crew

class SeuNovoCrewExecutor(CrewExecutor):
    @staticmethod
    def run(topic: str, parametro_extra: int = 5) -> Any:
        safe_print(f"\n🎯 Running Seu Novo Crew...")
        return CrewExecutor.execute_with_error_handling(
            "Seu Novo Crew",
            run_seu_novo_crew,
            topic=topic,
            parametro_extra=parametro_extra
        )
```


## 📝 Passo 4: Adicionar ao Flow

Em `src/desk_research/flow/flow.py`, adicione:

1. **Import do executor:**
```python
from desk_research.flow.crew_executors import (
    # ... outros imports
    SeuNovoCrewExecutor
)
```

2. **Método de execução:**
```python
@listen(initialize_research)
def run_seu_novo_crew(self):
    if "seu_novo_crew" in self.state.selected_crews:
        result = SeuNovoCrewExecutor.run(
            topic=self.state.topic,
            parametro_extra=self.state.params.get('parametro_extra', 5)
        )
        self.state.results["seu_novo_crew"] = result
    else:
        safe_print("⏭️ Skipping Seu Novo Crew")
```

3. **Adicionar ao listener de síntese:**
```python
@listen(or_(and_(run_academic, run_web, run_x, run_genie, run_youtube, run_consumer_hours, run_seu_novo_crew), "retry_synthesis"))
```

---

## 🎛️ Passo 5: Criar o Coletor de Parâmetros

Em `src/desk_research/system/parameter_collectors.py`, adicione:

```python
class SeuNovoCrewParameterCollector(ParameterCollector):
    @staticmethod
    def collect() -> Dict[str, Any] | None:
        print("\n" + "=" * 70)
        print("🎯 CONFIGURAÇÃO - SEU NOVO CREW")
        print("=" * 70)

        topic = ParameterCollector.selecionar_pergunta_padrao()
        if topic is None:
            return None
        
        # Adicione outros parâmetros se necessário
        parametro_extra_input = input(f"\n📊 Parâmetro extra [padrão: 10]: ").strip()
        parametro_extra = int(parametro_extra_input) if parametro_extra_input.isdigit() else 10

        return {
            "topic": topic,
            "parametro_extra": parametro_extra
        }
```

---

## 📌 Passo 6: Registrar nas Constantes

Em `src/desk_research/constants.py`, adicione:

1. **No MODE_CONFIG:**
```python
MODE_CONFIG = {
    # ... outros modos
    "seu_novo_crew": {
        "nome": "Nome Amigável do Seu Crew",
        "emoji": "🎯",
        "descricao": "Descrição do que seu crew faz"
    }
}
```

2. **No MODE_SELECTION_MAP (se for usar no modo integrado):**
```python
MODE_SELECTION_MAP = {
    # ... outros mapeamentos
    '7': 'seu_novo_crew'  # Use o próximo número disponível
}
```

---

## 🔗 Passo 7: Registrar no Sistema

Em `src/desk_research/system/research_system.py`, adicione:

1. **Import do coletor:**
```python
from desk_research.system.parameter_collectors import (
    # ... outros imports
    SeuNovoCrewParameterCollector
)
```

2. **Import da função runner:**
```python
from desk_research.crews.seu_novo_crew.seu_novo_crew import run_seu_novo_crew
```

3. **No `__init__` do DeskResearchSystem:**
```python
self._parameter_collectors = {
    # ... outros coletores
    "seu_novo_crew": SeuNovoCrewParameterCollector
}

self._executors = {
    # ... outros executores
    "seu_novo_crew": self.executar_seu_novo_crew
}
```

4. **Criar o método executor:**
```python
def executar_seu_novo_crew(self, topic: str, parametro_extra: int = 10) -> Dict[str, Any]:
    print(f"\n🎯 Iniciando Seu Novo Crew...")
    print(f"Tópico: {topic}")
    print(f"Parâmetro extra: {parametro_extra}\n")
    
    result = run_seu_novo_crew(topic=topic, parametro_extra=parametro_extra)
    
    return {
        "modo": "seu_novo_crew",
        "resultado": result,
        "metadados": {
            "topic": topic,
            "parametro_extra": parametro_extra
        }
    }
```

---

## ✅ Checklist Final

Antes de considerar seu crew pronto, verifique:

- Crew criado com `@CrewBase` e função `run_*`
- Executor criado em `crew_executors.py`
- Método `run_*` adicionado ao Flow
- Coletor de parâmetros criado
- Registrado em `MODE_CONFIG` nas constantes
- Adicionado ao `MODE_SELECTION_MAP`
- Registrado no `DeskResearchSystem`
- Método `executar_*` criado no sistema
- Arquivos YAML de configuração criados (`agents.yaml` e `tasks.yaml`)

---

## 🎨 Exemplo Completo: Crew de Análise de Reddit

Vamos ver um exemplo prático? Aqui está um crew fictício de análise do Reddit:

### 1. Estrutura:
```
src/desk_research/crews/reddit_analysis/
├── __init__.py
├── reddit_analysis.py
└── config/
    ├── agents.yaml
    └── tasks.yaml
```

### 2. Crew (`reddit_analysis.py`):
```python
@CrewBase
class RedditAnalysisCrew:
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def reddit_researcher(self) -> Agent:
        return Agent(config=self.agents_config['reddit_researcher'], verbose=True)

    @task
    def search_reddit_task(self) -> Task:
        return Task(
            config=self.tasks_config['search_reddit_task'],
            agent=self.reddit_researcher()
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.reddit_researcher()],
            tasks=[self.search_reddit_task()],
            process=Process.sequential,
            verbose=True
        )

def run_reddit_analysis(topic: str, max_posts: int = 20):
    inputs = {'topic': topic, 'max_posts': max_posts}
    crew = RedditAnalysisCrew()
    result = crew.crew().kickoff(inputs=inputs)
    export_report(result, topic, prefix="reddit_report", crew_name="reddit")
    return result
```

### 3. Executor:
```python
class RedditAnalysisCrewExecutor(CrewExecutor):
    @staticmethod
    def run(topic: str, max_posts: int = 20) -> Any:
        safe_print(f"\n🤖 Running Reddit Analysis...")
        return CrewExecutor.execute_with_error_handling(
            "Reddit Analysis Crew",
            run_reddit_analysis,
            topic=topic,
            max_posts=max_posts
        )
```

E assim por diante seguindo os passos acima! 🚀

---

## 💡 Dicas Finais

- **Nomes consistentes:** Use o mesmo nome em todos os lugares (ex: `seu_novo_crew`)
- **Tratamento de erros:** O `CrewExecutor` já cuida disso automaticamente
- **Logging:** Use `safe_print()` para mensagens ao usuário
- **Exportação:** Sempre exporte relatórios para facilitar o debug
- **Testes:** Teste seu crew isoladamente antes de integrar

---

## 🆘 Precisa de Ajuda?

Se ficar em dúvida, olhe os crews existentes como referência:
- `genie` - Crew simples com múltiplos agentes
- `academic` - Crew com parâmetros customizados
- `web` - Crew com ferramentas externas

Boa sorte criando seu novo crew! 🎉

