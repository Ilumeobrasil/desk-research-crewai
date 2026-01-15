# 🔑 CONFIGURAR .env - API Keys

## ❌ O Erro

```
ImportError: Error importing native provider: OPENAI_API_KEY is required
```

O CrewAI precisa de uma chave de API da OpenAI (ou outra LLM) para funcionar.

---

## ✅ SOLUÇÃO RÁPIDA

### **Opção 1: Criar arquivo .env (RECOMENDADO)**

Crie um arquivo `.env` no diretório raiz do projeto:

```bash
cd D:\Ilumeo\AMBEV\AGENTEIA_V1\ai-augmented-desk-research-flow
```

Crie o arquivo `.env` com este conteúdo:

```env
# OpenAI (padrão do CrewAI)
OPENAI_API_KEY=sk-sua-chave-aqui
OPENAI_MODEL_NAME=gpt-4o-mini

# Ou use Groq (gratuito e rápido)
# GROQ_API_KEY=sua-chave-groq-aqui
# GROQ_MODEL_NAME=llama-3.3-70b-versatile

# Ou use Anthropic Claude
# ANTHROPIC_API_KEY=sua-chave-anthropic-aqui
# ANTHROPIC_MODEL_NAME=claude-3-5-sonnet-20241022
```

---

### **Opção 2: Usar Groq (GRATUITO)** ⭐ RECOMENDADO

Groq é **gratuito** e muito rápido!

#### Passo 1: Obter chave Groq
1. Acesse: https://console.groq.com/
2. Crie conta (gratuita)
3. Vá em "API Keys"
4. Clique "Create API Key"
5. Copie a chave

#### Passo 2: Criar .env
```env
GROQ_API_KEY=gsk_sua_chave_groq_aqui
GROQ_MODEL_NAME=llama-3.3-70b-versatile
```

#### Passo 3: Instalar groq
```bash
pip install groq
```

---

### **Opção 3: Usar OpenAI (PAGO)**

#### Passo 1: Obter chave OpenAI
1. Acesse: https://platform.openai.com/api-keys
2. Faça login
3. Clique "Create new secret key"
4. Copie a chave (começa com `sk-`)

#### Passo 2: Criar .env
```env
OPENAI_API_KEY=sk-sua_chave_openai_aqui
OPENAI_MODEL_NAME=gpt-4o-mini
```

---

### **Opção 4: Usar Anthropic Claude (PAGO)**

#### Passo 1: Obter chave Anthropic
1. Acesse: https://console.anthropic.com/
2. Crie conta
3. Vá em "API Keys"
4. Crie nova chave

#### Passo 2: Criar .env
```env
ANTHROPIC_API_KEY=sk-ant-sua_chave_aqui
ANTHROPIC_MODEL_NAME=claude-3-5-sonnet-20241022
```

---

## 📝 CRIAR ARQUIVO .env NO WINDOWS

### Método 1: Notepad
```powershell
notepad .env
```

Cole o conteúdo:
```env
GROQ_API_KEY=sua_chave_aqui
GROQ_MODEL_NAME=llama-3.3-70b-versatile
```

Salve e feche.

### Método 2: PowerShell
```powershell
@"
GROQ_API_KEY=sua_chave_aqui
GROQ_MODEL_NAME=llama-3.3-70b-versatile
"@ | Out-File -FilePath .env -Encoding UTF8
```

### Método 3: VS Code
```bash
code .env
```

Cole o conteúdo e salve (Ctrl+S).

---

## 🔍 VERIFICAR SE FUNCIONOU

Depois de criar o `.env`, teste:

```bash
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('GROQ_API_KEY:', os.getenv('GROQ_API_KEY')[:10] + '...' if os.getenv('GROQ_API_KEY') else 'NÃO ENCONTRADA')"
```

Se aparecer `GROQ_API_KEY: gsk_...`, está funcionando!

---

## 📦 INSTALAR python-dotenv

Se não tiver instalado:

```bash
pip install python-dotenv
```

---

## 🎯 EXEMPLO COMPLETO - GROQ (GRATUITO)

```bash
# 1. Obter chave em https://console.groq.com/

# 2. Criar .env
cd D:\Ilumeo\AMBEV\AGENTEIA_V1\ai-augmented-desk-research-flow
notepad .env

# 3. Cole no arquivo:
# GROQ_API_KEY=gsk_sua_chave_aqui
# GROQ_MODEL_NAME=llama-3.3-70b-versatile

# 4. Instalar groq
pip install groq python-dotenv

# 5. Testar
python src/desk_research/main.py
```

---

## 💰 COMPARAÇÃO DE OPÇÕES

| Provider | Preço | Velocidade | Qualidade | Link |
|----------|-------|------------|-----------|------|
| **Groq** | ✅ Gratuito | ⚡ Muito rápida | 🟡 Boa | https://console.groq.com/ |
| **OpenAI** | 💰 Pago (~$0.01/1K tokens) | 🟢 Rápida | 🟢 Excelente | https://platform.openai.com/ |
| **Anthropic** | 💰 Pago (~$0.015/1K tokens) | 🟢 Rápida | 🟢 Excelente | https://console.anthropic.com/ |

**Recomendação**: Use **Groq** (gratuito) para testes! ⭐

---

## 🚀 MODELO RECOMENDADO POR PROVIDER

### Groq (Gratuito)
```env
GROQ_API_KEY=gsk_sua_chave
GROQ_MODEL_NAME=llama-3.3-70b-versatile
```

### OpenAI (Barato)
```env
OPENAI_API_KEY=sk-sua_chave
OPENAI_MODEL_NAME=gpt-4o-mini
```

### OpenAI (Melhor qualidade)
```env
OPENAI_API_KEY=sk-sua_chave
OPENAI_MODEL_NAME=gpt-4o
```

### Anthropic (Melhor qualidade)
```env
ANTHROPIC_API_KEY=sk-ant-sua_chave
ANTHROPIC_MODEL_NAME=claude-3-5-sonnet-20241022
```

---

## 🔧 CONFIGURAÇÃO AVANÇADA

### Múltiplos providers (fallback)
```env
# Primário
GROQ_API_KEY=sua_chave_groq
GROQ_MODEL_NAME=llama-3.3-70b-versatile

# Fallback
OPENAI_API_KEY=sua_chave_openai
OPENAI_MODEL_NAME=gpt-4o-mini
```

### Com temperatura customizada
```env
GROQ_API_KEY=sua_chave
GROQ_MODEL_NAME=llama-3.3-70b-versatile
GROQ_TEMPERATURE=0.7
GROQ_MAX_TOKENS=4096
```

---

## ⚠️ SEGURANÇA

**NUNCA commit o arquivo .env no git!**

Adicione no `.gitignore`:
```
.env
*.env
.env.*
```

---

## 📞 TROUBLESHOOTING

### Erro: "No module named 'dotenv'"
```bash
pip install python-dotenv
```

### Erro: "GROQ_API_KEY is required"
- Verifique se o arquivo `.env` está no diretório correto
- Verifique se o nome da variável está correto (maiúsculas)
- Reinicie o terminal

### Erro: "Invalid API key"
- Verifique se copiou a chave completa
- Verifique se não tem espaços extras
- Gere uma nova chave

---

## ✅ CHECKLIST

- [ ] Obtive chave da API (Groq/OpenAI/Anthropic)
- [ ] Criei arquivo `.env` no diretório raiz
- [ ] Colei a chave corretamente
- [ ] Instalei `python-dotenv`
- [ ] Instalei provider (groq/openai/anthropic)
- [ ] Testei com script de verificação
- [ ] Executei `python src/desk_research/main.py`

---

**🎉 Depois de configurar, execute novamente e vai funcionar!** 🚀

---

## 🔮 CONFIGURAR ASIMOV (Opcional - Consumer Hours)

Se você for usar o modo **Consumer Hours**, precisará configurar o acesso ao Asimov.

1.  Crie um arquivo `.env.asimov` na raiz do projeto.
2.  Adicione as seguintes variáveis:

```env
ASIMOV_API_BASE=https://abi-apim-internal.ab-inbev.com/asimov_stg_saz/api
ASIMOV_API_KEY=sua_chave_asimov
ASIMOV_DATASET=consumer-hours-flow-dev
ASIMOV_ENABLED=true
ASIMOV_DATASET_MODEL=openai/text-embedding-ada-002
```
