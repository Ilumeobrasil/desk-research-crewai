#!/bin/bash
# Script para deploy via SSH: para serviço, atualiza código e reinicia

# Configurações - Ajuste conforme necessário
SSH_HOST="31.97.31.110"
SSH_USER="root"
REMOTE_PATH="/home/ubuntu/crewai/desk-research-crewai"
STREAMLIT_PORT="8501"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Iniciando deploy via SSH...${NC}"
echo -e "${YELLOW}Host: ${SSH_USER}@${SSH_HOST}${NC}"
echo -e "${YELLOW}Pasta remota: ${REMOTE_PATH}${NC}"
echo ""

# Comando SSH que executa todos os passos
ssh ${SSH_USER}@${SSH_HOST} << EOF
    set -e  # Para em caso de erro
    
    echo -e "${YELLOW}📂 Navegando para ${REMOTE_PATH}...${NC}"
    cd ${REMOTE_PATH} || { echo -e "${RED}❌ Erro: Pasta não encontrada!${NC}"; exit 1; }
    
    echo -e "${YELLOW}🛑 Parando serviço Streamlit...${NC}"
    # Tenta parar processos do Streamlit na porta especificada
    pkill -f "streamlit.*streamlit_app.py" || echo "Nenhum processo Streamlit encontrado"
    # Alternativa: kill na porta específica
    lsof -ti:${STREAMLIT_PORT} | xargs kill -9 2>/dev/null || echo "Porta ${STREAMLIT_PORT} já está livre"
    sleep 2
    
    echo -e "${YELLOW}📥 Fazendo git pull...${NC}"
    git pull || { echo -e "${RED}❌ Erro ao fazer git pull!${NC}"; exit 1; }
    
    echo -e "${YELLOW}🔄 Ativando ambiente virtual (se existir)...${NC}"
    if [ -d ".venv" ]; then
        source .venv/bin/activate
        echo "Ambiente virtual ativado"
    fi
    
    echo -e "${YELLOW}📦 Verificando dependências...${NC}"
    # Opcional: atualizar dependências se necessário
    # pip install -r requirements.txt --quiet
    
    echo -e "${YELLOW}▶️  Iniciando serviço Streamlit...${NC}"
    # Inicia Streamlit em background e salva o PID
    nohup streamlit run streamlit_app.py --server.port=${STREAMLIT_PORT} > streamlit.log 2>&1 &
    STREAMLIT_PID=\$!
    echo \$STREAMLIT_PID > streamlit.pid
    echo -e "${GREEN}✅ Streamlit iniciado com PID: \$STREAMLIT_PID${NC}"
    
    sleep 3
    echo -e "${GREEN}✅ Deploy concluído com sucesso!${NC}"
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Deploy realizado com sucesso!${NC}"
else
    echo ""
    echo -e "${RED}❌ Erro durante o deploy!${NC}"
    exit 1
fi

