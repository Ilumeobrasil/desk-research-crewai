from typing import Literal

MIN_APPROVAL_SCORE = 80
MAX_RETRY_COUNT = 2
DEFAULT_MAX_PAPERS = 5
DEFAULT_MAX_WEB_RESULTS = 5
DEFAULT_TOPIC = "Pesquisa Genérica"

MODE_CONFIG = {
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
    "consumer_hours": {
        "nome": "Consumer Hours (Brand Audit)",
        "emoji": "⏳",
        "descricao": "Análise profunda de auditoria de marca (Consumer Hours Flow)"
    },
    "integrated": {
        "nome": "Pesquisa Integrada (Multi-Agente)",
        "emoji": "🧠",
        "descricao": "Executa múltiplos agentes e gera relatório master consolidado"
    }
}

PERGUNTAS_PADRAO = {
    "geral": [
        "O jovem esta bebendo menos alcool? E cerveja?",
        "O consumidor associa luta a alguma marca de cerveja? Qual? Quais perfis demograficos e de interesse associam mais/menos?",
        "Scan no QR Code da tampinha de Brahma aumenta fidelidade/volume/frequencia?",
        "E verdade que as pessoas gostam mais de colocar limao na Coronita porque o sabor do limao fica mais concentrado?",
        "Quero entender melhor Eisenbahn. A marca esta em evolucao ou nao?"
    ]
}

# USADO PARA SELECIONAR OS MODOS PARA PESQUISA INTEGRADA
MODE_SELECTION_MAP = {
    '1': 'genie',
    '2': 'academic',
    '3': 'youtube',
    '4': 'web',
    '5': 'x',
    '6': 'consumer_hours'
}


