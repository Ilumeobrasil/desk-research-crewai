import os
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

class YouTubeTranscriptToolInput(BaseModel):
    video_id: str = Field(..., description="O ID do vídeo do YouTube (não a URL completa). Ex: 'dQw4w9WgXcQ'")

class YouTubeTranscriptTool(BaseTool):
    name: str = "Ferramenta de Transcrição do YouTube"
    description: str = (
        "Busca e retorna a transcrição completa (legendas) de um vídeo do YouTube em português ou inglês. "
        "Essencial para analisar o conteúdo falado do vídeo."
    )
    args_schema: Type[BaseModel] = YouTubeTranscriptToolInput

    def _run(self, video_id: str) -> str:
        try:
            print(f"🎬 Iniciando extração de transcrição para: {video_id} (API v1.2.3 Custom)")
            
            api = YouTubeTranscriptApi()
            
            try:
                # 1. Listar (Pode falhar se vídeo for restrito)
                # NOTA: Nesta versão customizada da lib, o método é .list(), não .list_transcripts()
                transcript_list = api.list(video_id)
                # print(f"   - Opções encontradas: {transcript_list}")
                
                # 2. Seleção Inteligente
                transcript = None
                
                # Tentar Manual (PT > EN)
                try: transcript = transcript_list.find_manually_created_transcript(['pt', 'pt-BR'])
                except: pass
                
                if not transcript:
                    try: transcript = transcript_list.find_manually_created_transcript(['en', 'en-US'])
                    except: pass
                
                # Tentar Auto (PT > EN)
                if not transcript:
                    try: transcript = transcript_list.find_generated_transcript(['pt', 'pt-BR'])
                    except: pass
                    
                if not transcript:
                    try: transcript = transcript_list.find_generated_transcript(['en', 'en-US'])
                    except: pass
                
                # Fallback: Qualquer um
                if not transcript:
                    try: transcript = next(iter(transcript_list))
                    except: pass
                
                if not transcript:
                    return f"ERRO: Nenhuma transcrição encontrada para {video_id}."
                
                print(f"   - Selecionado: {transcript.language_code} (Auto: {transcript.is_generated})")
                
                # 3. Fetch (Baixar dados)
                transcript_data = transcript.fetch()
                
                # 4. Formatar Texto
                full_text = []
                for item in transcript_data:
                    # item pode ser dict ou objeto, dependendo da versão interna
                    text_val = item.get('text') if isinstance(item, dict) else getattr(item, 'text', str(item))
                    full_text.append(str(text_val))
                
                text_formatted = " ".join(full_text)
                header = f"--- TRANSCRICAO VIDEO ID: {video_id} ({transcript.language_code}) ---\n"
                return header + text_formatted[:15000]

            except Exception as e_api:
                # Tratar erros conhecidos da API
                err_msg = str(e_api)
                if "VideoUnavailable" in err_msg:
                    return f"ERRO: Vídeo restrito/indisponível para análise automática (Bloqueio do YouTube). ID: {video_id}"
                if "NoTranscriptFound" in err_msg:
                    return f"ERRO: Vídeo não possui legendas (nem automáticas). ID: {video_id}"
                
                # Tentar fetch direto como última esperança se API mudou
                try:
                    raw_fetch = api.fetch(video_id)
                    text_formatted = " ".join([str(x) for x in raw_fetch])
                    return f"--- TRANSCRICAO (FALLBACK FETCH) ---\n{text_formatted[:15000]}"
                except:
                    return f"ERRO: Falha na transcrição: {err_msg}"
            
        except Exception as e:
            return f"ERRO GERAL na transcrição: {str(e)}"

# Instanciação
youtube_transcript_tool = YouTubeTranscriptTool()
