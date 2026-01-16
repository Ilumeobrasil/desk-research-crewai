from typing import Type, List, Optional
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from youtube_transcript_api import YouTubeTranscriptApi

class YouTubeTranscriptToolInput(BaseModel):
    video_id: str = Field(..., description="O ID do vídeo do YouTube (não a URL completa). Ex: 'dQw4w9WgXcQ'")

class YouTubeTranscriptTool(BaseTool):
    name: str = "Ferramenta de Transcrição do YouTube"
    description: str = (
        "Busca e retorna a transcrição completa (legendas) de um vídeo do YouTube em português ou inglês. "
        "Essencial para analisar o conteúdo falado do vídeo."
    )
    args_schema: Type[BaseModel] = YouTubeTranscriptToolInput

    _MAX_TEXT_LENGTH = 15000
    _PREFERRED_LANGUAGES_PT = ['pt', 'pt-BR']
    _PREFERRED_LANGUAGES_EN = ['en', 'en-US']
    
    _ERROR_VIDEO_UNAVAILABLE = "VideoUnavailable"
    _ERROR_NO_TRANSCRIPT = "NoTranscriptFound"

    def _run(self, video_id: str) -> str:
        try:
            print(f"🎬 Iniciando extração de transcrição para: {video_id}")
            
            api = YouTubeTranscriptApi()
            
            try:
                transcript_list = api.list(video_id)
                transcript = self._select_best_transcript(transcript_list)
                
                if not transcript:
                    return f"ERRO: Nenhuma transcrição encontrada para {video_id}."
                
                print(f"   - Selecionado: {transcript.language_code} (Auto: {transcript.is_generated})")
                
                transcript_data = transcript.fetch()
                formatted_text = self._format_transcript(transcript_data, video_id, transcript.language_code)
                
                return formatted_text

            except Exception as e_api:
                return self._handle_api_errors(e_api, api, video_id)
            
        except Exception as e:
            return f"ERRO GERAL na transcrição: {str(e)}"

    def _select_best_transcript(self, transcript_list) -> Optional:
        transcript = self._find_manual_transcript(transcript_list, self._PREFERRED_LANGUAGES_PT)
        
        if not transcript:
            transcript = self._find_manual_transcript(transcript_list, self._PREFERRED_LANGUAGES_EN)
        
        if not transcript:
            transcript = self._find_generated_transcript(transcript_list, self._PREFERRED_LANGUAGES_PT)
        
        if not transcript:
            transcript = self._find_generated_transcript(transcript_list, self._PREFERRED_LANGUAGES_EN)
        
        if not transcript:
            transcript = self._get_any_transcript(transcript_list)
        
        return transcript

    def _find_manual_transcript(self, transcript_list, languages: List[str]) -> Optional:
        try:
            return transcript_list.find_manually_created_transcript(languages)
        except Exception:
            return None

    def _find_generated_transcript(self, transcript_list, languages: List[str]) -> Optional:
        try:
            return transcript_list.find_generated_transcript(languages)
        except Exception:
            return None

    def _get_any_transcript(self, transcript_list) -> Optional:
        try:
            return next(iter(transcript_list))
        except Exception:
            return None

    def _format_transcript(self, transcript_data: List, video_id: str, language_code: str) -> str:
        full_text = [self._extract_text_from_item(item) for item in transcript_data]
        text_formatted = " ".join(full_text)
        truncated_text = text_formatted[:self._MAX_TEXT_LENGTH]
        header = f"--- TRANSCRICAO VIDEO ID: {video_id} ({language_code}) ---\n"
        
        return header + truncated_text

    def _extract_text_from_item(self, item) -> str:
        if isinstance(item, dict):
            return str(item.get('text', ''))
        return str(getattr(item, 'text', item))

    def _handle_api_errors(self, error: Exception, api: YouTubeTranscriptApi, video_id: str) -> str:
        error_msg = str(error)
        
        if self._ERROR_VIDEO_UNAVAILABLE in error_msg:
            return f"ERRO: Vídeo restrito/indisponível para análise automática (Bloqueio do YouTube). ID: {video_id}"
        
        if self._ERROR_NO_TRANSCRIPT in error_msg:
            return f"ERRO: Vídeo não possui legendas (nem automáticas). ID: {video_id}"
        
        return self._try_fallback_fetch(api, video_id, error_msg)

    def _try_fallback_fetch(self, api: YouTubeTranscriptApi, video_id: str, error_msg: str) -> str:
        try:
            raw_fetch = api.fetch(video_id)
            text_formatted = " ".join([str(x) for x in raw_fetch])
            truncated_text = text_formatted[:self._MAX_TEXT_LENGTH]
            return f"--- TRANSCRICAO (FALLBACK FETCH) ---\n{truncated_text}"
        except Exception:
            return f"ERRO: Falha na transcrição: {error_msg}"

youtube_transcript_tool = YouTubeTranscriptTool()