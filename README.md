# Sistema de Pesquisa Integrada Desk Research - Ambev

O **Desk Research System** é uma plataforma de inteligência de mercado baseada em Agentes Autônomos (AI Crews). Ele integra múltiplas fontes de dados para gerar relatórios estratégicos profundos e acionáveis, culminando em uma visão 360º do tema pesquisado.

## 🚀 O Ecossistema de Agentes

O sistema é comporto por 6 Crews especializadas que podem atuar em conjunto ou isoladamente:

| Crew | Função | Tecnologia / Diferencial |
|------|--------|--------------------------|
| **🎓 Academic Crew** | rigor e ciência | Consulta bases como Scholar/OpenAlex, **lê PDFs na íntegra** e gera análise crítica com referências ABNT. |
| **📺 YouTube Crew** | mídia e influência | **Sistema Próprio de Scraping** (Sem custo de API de busca). Analisa transcrições (auto/manual) para captar narrativas e sentimentos. |
| **🐦 Social Crew (X)** | pulso social | Conecta via API do X (Twitter) para análise de sentimento real-time e detecção de tendências não-filtradas. |
| **🌐 Web Crew** | notícias de mercado | Varre a surface web em busca de lançamentos, competidores e press releases recentes. |
| **🧞 Genie Crew** | simulação de mercado | **Focus Group Virtual**: Simula um debate entre 3 personas (Cético, Brand Lover, Pragmático) para prever aceitação. |
| **⏳ Consumer Hours** | auditoria de marca | **Auditoria Profunda de Marca**: Análise de documentos e inputs massivos para entender a percepção da marca (Brand Audit). |

## 📊 O Relatório Integrado

O produto final é o **Relatório Master Integrado** (Markdown e PDF), que não apenas cola os resultados, mas realiza um cruzamento inteligente:
- **Convergências**: Onde a Academia e as Redes Sociais concordam?
- **Divergências**: Onde os dados técnicos contradizem a percepção pública?
- **Blind Spots**: O que ninguém está vendo?

## 📦 Instalação Rápida

Pré-requisitos: Python 3.10+ e [Chaves de API](CONFIGURAR_ENV.md).

1.  **Clone o projeto:**
    ```bash
    git clone <repo-url>
    ```

    **Crie o ambiente virtual do projeto:**
    ```bash
    uv venv
    ```

    **Faça a ativação:**
    macOS / Linux:
    ```bash
    source .venv/bin/activate
    ```
    Windows:
    ```bash
    .venv\Scripts\activate
    ```

    **Faça o download das dependências:**
    ```bash
    uv pip install -r requirements.txt
    ```

2.  **Configure o Ambiente:**
    Crie um arquivo `.env` na raiz com suas chaves (veja `.env.example`).

3.  **Execute:**h
    crewai run
        ou

    para executar a interface Streamlit:
  
    streamlit run streamlit_app
        ou utilizando o script:h
    ./run_streamlit.sh
    

## 🛠️ Modos de Uso

Ao iniciar o sistema, você terá um MENU INTERATIVO:

- **[6] Pesquisa Integrada (Recomendado)**: Ativa múltiplos agentes para uma varredura completa. Você escolhe quais participarão.
- **[1-5] Modos Individuais**: Executa apenas um especialista (ex: só YouTube para analisar vídeos específicos).

## 📂 Estrutura do Projeto

- `src/desk_research/crews/`: Cérebro dos agentes (prompts, tarefas, lógica).
- `src/desk_research/tools/`: Ferramentas proprietárias (Scraper YouTube, Leitor PDF, Conector X).
- `outputs/`: Relatórios gerados (organizados por data/tema).
- `data/`: Dados de entrada e saída do Consumer Hours.
  - `data/input_raw/Brand_Audit/`: **Coloque aqui os arquivos .docx/.pdf** para a análise do Consumer Hours.

---

## ℹ️ Notas sobre Consumer Hours

O módulo **Consumer Hours** funciona de forma diferente dos demais:
1.  Ele não pede um "tópico" na hora da execução.
2.  Ele processa **todos os arquivos** que estiverem na pasta `data/input_raw/Brand_Audit`.
3.  Certifique-se de colocar seus documentos lá antes de rodar.

---
**Desenvolvido para Ambev - Tech Innovation**
*Versão 2.0 - Dezembro 2025*
