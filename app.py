from desk_research.utils.makelog.makeLog import make_log
import streamlit as st
from datetime import datetime
import os
import sys
import logging
from pathlib import Path
from desk_research.system.research_system import DeskResearchSystem
from desk_research.constants import MODE_CONFIG, PERGUNTAS_PADRAO, DEFAULT_MAX_PAPERS, DEFAULT_MAX_WEB_RESULTS

# Adicionar o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Configurações de logging
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["ANONYMIZED_TELEMETRY"] = "False"

# ----------------------------
# Page config (tamanho e título)
# ----------------------------
st.set_page_config(
    page_title="Ambev.ia",
    page_icon="💬",
    layout="wide",
)

# ----------------------------
# Perguntas pré-definidas (X / Twitter)
# ----------------------------
X_QUESTIONS = PERGUNTAS_PADRAO.get("geral", [])

# ----------------------------
# Variável de ambiente para menu interativo
# ----------------------------
VIEW_INTERACTIVE_MENU = os.getenv("VIEW_INTERACTIVE_MENU", "FALSE").upper() == "TRUE"

# ----------------------------
# Helpers (ordem e nome automático)
# ----------------------------
def _title_from_text(text: str, max_len: int = 28) -> str:
    t = " ".join((text or "").strip().split())
    if not t:
        return "Novo chat"
    t = t[:max_len].strip()
    return t

def _unique_chat_name(base: str) -> str:
    name = base
    i = 2
    while name in st.session_state.chats:
        name = f"{base} ({i})"
        i += 1
    return name

def bump_chat_to_top(chat_name: str):
    if "chat_order" not in st.session_state:
        st.session_state.chat_order = list(st.session_state.chats.keys())
    if chat_name in st.session_state.chat_order:
        st.session_state.chat_order.remove(chat_name)
    st.session_state.chat_order.insert(0, chat_name)

def rename_chat(old, new):
    new = (new or "").strip()
    if not new:
        return
    if new in st.session_state.chats:
        return

    st.session_state.chats[new] = st.session_state.chats.pop(old)

    if "chat_order" in st.session_state and old in st.session_state.chat_order:
        idx = st.session_state.chat_order.index(old)
        st.session_state.chat_order[idx] = new

    st.session_state.active_chat = new

def maybe_autoname_chat(chat_name: str, user_text: str) -> str:
    is_generic = chat_name == "Novo chat" or chat_name.startswith("Chat ")
    if not is_generic:
        return chat_name

    base = _title_from_text(user_text)
    new_name = _unique_chat_name(base)

    if new_name != chat_name:
        rename_chat(chat_name, new_name)
        return new_name

    return chat_name

# ----------------------------
# Helper para extrair texto dos resultados dos crews
# ----------------------------
def extract_result_text(result: any) -> str:
    """Extrai texto formatado dos resultados dos crews"""
    if isinstance(result, dict):
        # Tentar diferentes chaves comuns
        if 'resultado' in result:
            return extract_result_text(result['resultado'])
        if 'result' in result:
            return extract_result_text(result['result'])
        if 'report_markdown' in result:
            return result['report_markdown']
        if 'master_report' in result:
            return extract_result_text(result['master_report'])
        if 'final_report' in result:
            return result['final_report']
        # Se for dict com erro
        if 'erro' in result:
            return f"❌ Erro: {result['erro']}"
    
    # Se for objeto CrewAI
    if hasattr(result, 'raw'):
        return result.raw
    if hasattr(result, 'tasks_output') and result.tasks_output:
        return result.tasks_output[-1].raw if hasattr(result.tasks_output[-1], 'raw') else str(result.tasks_output[-1])
    if hasattr(result, 'pydantic'):
        return str(result.pydantic)
    
    # Fallback para string
    return str(result)

def format_result_for_chat(result: any, modo: str = None) -> str:
    """Formata o resultado para exibição no chat"""
    texto = extract_result_text(result)
    
    # Adicionar header com modo se disponível
    header = ""
    if modo and modo in MODE_CONFIG:
        modo_info = MODE_CONFIG[modo]
        header = f"**{modo_info['emoji']} {modo_info['nome']}**\n\n"
    
    return header + texto 

# ----------------------------
# Função para executar pesquisa real
# ----------------------------
def execute_research(user_text: str, modo_selecionado: str = None) -> str:
    """Executa a pesquisa usando o DeskResearchSystem"""
    try:
        system = DeskResearchSystem()
        
        # Se modo não foi selecionado e VIEW_INTERACTIVE_MENU está desabilitado, usar modo integrado
        if not modo_selecionado and not VIEW_INTERACTIVE_MENU:
            modo_selecionado = "integrated"
        
        # Se ainda não tem modo, retornar erro
        if not modo_selecionado:
            return "❌ Erro: Nenhum modo selecionado."
        
        # Preparar parâmetros baseado no modo
        params = {}
        
        if modo_selecionado == "genie":
            params = {"pergunta": user_text, "contexto": ""}
        elif modo_selecionado == "youtube":
            params = {"topic": user_text}
        elif modo_selecionado == "academic":
            params = {"topic": user_text, "max_papers": DEFAULT_MAX_PAPERS}
        elif modo_selecionado == "web":
            params = {"query": user_text, "max_results": DEFAULT_MAX_WEB_RESULTS}
        elif modo_selecionado == "x":
            params = {"topic": user_text}
        elif modo_selecionado == "consumer_hours":
            params = {}
        elif modo_selecionado == "integrated":
            # Modo integrado usa todos os modos disponíveis por padrão
            selected_modos = ['web']
            params = {
                "topic": user_text,
                "selected_modos": selected_modos,
                "params": {
                    "max_papers": DEFAULT_MAX_PAPERS,
                    "max_web_results": DEFAULT_MAX_WEB_RESULTS
                }
            }
        else:
            return f"❌ Modo '{modo_selecionado}' não suportado."
        
        # Executar pesquisa
        executor = system._executors.get(modo_selecionado)
        if not executor:
            return f"❌ Executor para modo '{modo_selecionado}' não encontrado."
        
        resultado = executor(**params)

        make_log({
            "content": resultado,
            "logName": "resultado_integrado"
        })
        
        # Formatar resultado para chat
        return format_result_for_chat(resultado, modo_selecionado)
        
    except Exception as e:
        import traceback
        error_msg = f"❌ Erro na execução: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
        return error_msg

# ----------------------------
# CSS (estilo ChatGPT-like)
# ----------------------------
st.markdown(
    """
    <style>
    /* ===== Fundo geral ===== */
    .stApp {
        background-color: #ffffff;
        color: #0f172a;
    }

    /* ===== Sidebar ===== */
    section[data-testid="stSidebar"] {
        background-color: #f9f9f9;
        border-right: 1px solid #e5e7eb;
    }

    /* ===== Títulos ===== */
    h1, h2, h3, h4 {
        color: #0f172a !important;
    }

    /* ===== Container do chat ===== */
    .chat-wrap {
        max-width: 900px;
        margin: 0 auto;
        padding: 16px 12px 96px 12px;
    }

    /* ===== Bolhas ===== */
    .bubble {
        padding: 12px 14px;
        border-radius: 14px;
        margin: 10px 0;
        line-height: 1.5;
        font-size: 15px;
        max-width: 85%;
        border: 1px solid #e5e7eb;
        white-space: pre-wrap;
        word-wrap: break-word;
        background-color: #ffffff;
    }

    .user {
        background-color: #f4f4f5;
        margin-left: auto;
    }

    .assistant {
        background-color: #ffffff;
        margin-right: auto;
    }

    /* ===== Label (Você / Assistente) ===== */
    .meta {
        font-size: 12px;
        color: #6b7280;
        margin-bottom: 4px;
    }

    /* ===== Input fixo ===== */
    .input-bar {
        position: fixed;
        bottom: 16px;
        left: 0;
        right: 0;
        z-index: 9999;
        display: flex;
        justify-content: center;
        pointer-events: none;
    }

    .input-inner {
        width: min(900px, 92vw);
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 10px 12px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        pointer-events: auto;
    }

    textarea {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border-radius: 10px !important;
        border: 1px solid #e5e7eb !important;
    }

    textarea::placeholder {
        color: #9ca3af !important;
    }

    /* ===== Botões ===== */
    .stButton>button {
        background-color: #f3f4f6 !important;
        color: #0f172a !important;
        border: 1px solid #e5e7eb !important;
        border-radius: 10px !important;
    }

    .stButton>button:hover {
        background-color: #e5e7eb !important;
    }

    /* ===== Ajustes gerais ===== */
    .block-container {
        padding-top: 12px;
        padding-bottom: 0px;
    }

    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* ===== Ocultar toolbar/header do Streamlit (Share etc.) ===== */
    div[data-testid="stToolbar"] { display: none !important; }
    div[data-testid="stToolbarActions"] { display: none !important; }
    .stAppToolbar { display: none !important; }
    header[data-testid="stHeader"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True
)

# ----------------------------
# Estado (chats / menu / envio pendente)
# ----------------------------
if "chats" not in st.session_state:
    st.session_state.chats = {
        "Novo chat": [
            {"role": "assistant", "content": "Oi! Esse é a IA da Ambev. 😊\n\nMe manda uma mensagem aí embaixo."}
        ]
    }
    st.session_state.active_chat = "Novo chat"
    st.session_state.chat_order = ["Novo chat"]

if "chat_order" not in st.session_state:
    st.session_state.chat_order = list(st.session_state.chats.keys())

if "sidebar_section" not in st.session_state:
    st.session_state.sidebar_section = "chats" 

if "pending_user_message" not in st.session_state:
    st.session_state.pending_user_message = ""

if "pending_mode" not in st.session_state:
    st.session_state.pending_mode = None

if "system" not in st.session_state:
    st.session_state.system = DeskResearchSystem()
    
def new_chat():
    name = _unique_chat_name(f"Chat {len(st.session_state.chats)+1}")
    st.session_state.chats[name] = [
        {"role": "assistant", "content": "Começamos uma novo chat. Como posso ajudar?"}
    ]
    st.session_state.active_chat = name
    bump_chat_to_top(name)

# ----------------------------
# Sidebar (menu fixo + chats / X)
# ----------------------------
with st.sidebar:
    # Menu fixo
    colA, colB = st.columns(2)
    if st.session_state.sidebar_section == "chats":
        st.markdown("### Chats")
        st.button("➕ Novo chat", use_container_width=True, on_click=new_chat)

        st.markdown("---")
        for chat_name in st.session_state.chat_order:
            is_active = (chat_name == st.session_state.active_chat)
            label = f"{chat_name}" if is_active else chat_name

            if st.button(label, key=f"chat_{chat_name}", use_container_width=True):
                st.session_state.active_chat = chat_name

    else:
        st.markdown("### X (Twitter)")
        st.caption("Clique em uma pergunta pronta para enviar ao chat, ou crie uma nova.")

        st.markdown("**Perguntas pré-definidas**")
        for i, q in enumerate(X_QUESTIONS, start=1):
            if st.button(f"{i}. {q}", key=f"xq_{i}", use_container_width=True):
                st.session_state.pending_user_message = q
                st.rerun()

        st.markdown("---")
        st.markdown("**Criar nova**")
        custom = st.text_area(
            "Nova pergunta",
            placeholder="Digite sua pergunta...",
            label_visibility="collapsed",
            height=100,
            key="x_custom_question"
        )
        if st.button("Enviar para o chat", use_container_width=True, key="x_send_custom"):
            if custom.strip():
                st.session_state.pending_user_message = custom.strip()
                st.session_state["x_custom_question"] = ""  # limpa a caixa
                st.rerun()

# ----------------------------
# Área principal
# ----------------------------
active = st.session_state.active_chat
messages = st.session_state.chats[active]

st.markdown(f"## {active}")

# ----------------------------
# Seleção de modo (se VIEW_INTERACTIVE_MENU estiver ativo)
# ----------------------------
modo_selecionado = None
if VIEW_INTERACTIVE_MENU:
    st.markdown("---")
    modo_selecionado = st.selectbox(
        "🔧 Escolha o modo de pesquisa:",
        options=["integrated"] + [k for k in MODE_CONFIG.keys() if k != "integrated"],
        format_func=lambda x: f"{MODE_CONFIG[x]['emoji']} {MODE_CONFIG[x]['nome']}",
        key=f"mode_select_{active}",
        help="Selecione qual tipo de pesquisa deseja executar"
    )
    st.markdown("---")

# ----------------------------
# Render das mensagens (bolhas)
# ----------------------------
st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)

for m in messages:
    role = m["role"]
    content = m["content"]

    who = "Você" if role == "user" else "Assistente"
    css_class = "user" if role == "user" else "assistant"
    meta = f'<div class="meta">{who} • {datetime.now().strftime("%H:%M")}</div>'

    st.markdown(
        f"""
        <div>
            {meta}
            <div class="bubble {css_class}">{content}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Input (form)
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    user_text = st.text_area("Mensagem", placeholder="Digite sua mensagem...", label_visibility="collapsed", height=70)
    col1, col2 = st.columns([6, 1])
    with col2:
        send = st.form_submit_button("Enviar")


# ----------------------------
# Processamento de mensagens
# ----------------------------

# 1) Se veio algo do menu lateral (X/Twitter), injeta no chat
if st.session_state.pending_user_message.strip():
    injected = st.session_state.pending_user_message.strip()
    st.session_state.pending_user_message = ""
    
    # Determinar modo
    modo_para_execucao = modo_selecionado if VIEW_INTERACTIVE_MENU else None
    
    active_before = st.session_state.active_chat
    st.session_state.chats[active_before].append({"role": "user", "content": injected})
    
    # Executar pesquisa real
    with st.spinner("🔄 Processando pesquisa... Isso pode levar alguns minutos."):
        resposta = execute_research(injected, modo_para_execucao)
    
    active_after = maybe_autoname_chat(active_before, injected)
    st.session_state.chats[active_after].append({"role": "assistant", "content": resposta})
    
    bump_chat_to_top(active_after)
    st.rerun()

# 2) Envio normal pelo input
if send and user_text.strip():
    txt = user_text.strip()
    active_before = st.session_state.active_chat
    
    # Determinar modo
    modo_para_execucao = modo_selecionado if VIEW_INTERACTIVE_MENU else None
    
    st.session_state.chats[active_before].append({"role": "user", "content": txt})
    
    # Executar pesquisa real
    with st.spinner("🔄 Processando pesquisa... Isso pode levar alguns minutos."):
        resposta = execute_research(txt, modo_para_execucao)
    
    active_after = maybe_autoname_chat(active_before, txt)
    st.session_state.chats[active_after].append({"role": "assistant", "content": resposta})
    
    bump_chat_to_top(active_after)
    st.rerun()

