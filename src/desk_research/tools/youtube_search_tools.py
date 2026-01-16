import requests
import re
from typing import Type, List, Dict
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from urllib.parse import urlencode

class YouTubeVideoSearchToolInput(BaseModel):
    query: str = Field(..., description="Termo de pesquisa para encontrar vídeos no YouTube")

class YouTubeVideoSearchTool(BaseTool):
    name: str = "YouTube Video Search Scraper"
    description: str = (
        "Busca vídeos no YouTube utilizando Scraping. "
        "Retorna lista de vídeos com Título e ID. "
        "Útil para encontrar vídeos recentes sobre um tema."
    )
    args_schema: Type[BaseModel] = YouTubeVideoSearchToolInput

    _BASE_YOUTUBE_SEARCH_URL = "https://www.youtube.com/results"
    _REQUEST_TIMEOUT = 10
    _MAX_RESULTS = 5
    _VIDEO_ID_LENGTH = 11
    _BLOCK_SAMPLE_SIZE = 4000
    _VIDEO_RENDERER_MARKER = '"videoRenderer":'
    
    _USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/91.0.4472.124 Safari/537.36'
    )
    
    _VIDEO_ID_PATTERN = re.compile(r'"videoId":"([a-zA-Z0-9_-]{11})"')
    _TITLE_PATTERN = re.compile(r'"title":{"runs":\[{"text":"(.*?)"}\]')
    
    _DEFAULT_HEADERS = {
        'User-Agent': _USER_AGENT,
        'Accept-Language': 'en-US,en;q=0.9',
    }

    def _run(self, query: str) -> str:
        try:
            print(f"🎬 Buscando no YouTube (Scraper): '{query}'")
            
            html = self._fetch_search_results(query)
            videos = self._parse_videos_from_html(html)
            
            if not videos:
                return "Nenhum vídeo encontrado. Tente termos diferentes."
            
            return self._format_results(videos)
            
        except Exception as e:
            return f"Erro ao buscar vídeos no YouTube: {str(e)}"

    def _fetch_search_results(self, query: str) -> str:
        params = {"search_query": query}
        url = f"{self._BASE_YOUTUBE_SEARCH_URL}?{urlencode(params)}"
        
        response = requests.get(url, headers=self._DEFAULT_HEADERS, timeout=self._REQUEST_TIMEOUT)
        response.raise_for_status()
        
        return response.text

    def _parse_videos_from_html(self, html: str) -> List[Dict[str, str]]:
        videos = []
        video_blocks = html.split(self._VIDEO_RENDERER_MARKER)
        
        for block in video_blocks[1:]:
            video = self._extract_video_from_block(block)
            
            if video and not self._is_duplicate(video['id'], videos):
                videos.append(video)
                
                if len(videos) >= self._MAX_RESULTS:
                    break
        
        return videos

    def _extract_video_from_block(self, block: str) -> Dict[str, str] | None:
        block_sample = block[:self._BLOCK_SAMPLE_SIZE]
        
        id_match = self._VIDEO_ID_PATTERN.search(block_sample)
        if not id_match:
            return None
        
        video_id = id_match.group(1)
        title_match = self._TITLE_PATTERN.search(block_sample)
        title = title_match.group(1) if title_match else "Título não identificado"
        title = self._clean_title(title)
        
        return {'id': video_id, 'title': title}

    def _clean_title(self, title: str) -> str:
        return title.replace('\\"', '"').replace("\\'", "'")

    def _is_duplicate(self, video_id: str, existing_videos: List[Dict[str, str]]) -> bool:
        return any(video['id'] == video_id for video in existing_videos)

    def _format_results(self, videos: List[Dict[str, str]]) -> str:
        output = "VÍDEOS ENCONTRADOS:\n"
        for video in videos:
            video_url = f"https://www.youtube.com/watch?v={video['id']}"
            output += f"- Título: {video['title']} | Link: {video_url} (ID: {video['id']})\n"
        return output

youtube_video_search_tool = YouTubeVideoSearchTool()