import requests
import re
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class YouTubeVideoSearchToolInput(BaseModel):
    query: str = Field(..., description="Termo de pesquisa para encontrar vídeos no YouTube")

class YouTubeVideoSearchTool(BaseTool):
    name: str = "YouTube Video Search Scraper"
    description: str = (
        "Busca vídeos no YouTube sem precisar de API paga. "
        "Retorna lista de vídeos com Título e ID. "
        "Útil para encontrar vídeos recentes sobre um tema."
    )
    args_schema: Type[BaseModel] = YouTubeVideoSearchToolInput

    def _run(self, query: str) -> str:
        """
        Realiza scraping leve da página de resultados do YouTube.
        """
        try:
            print(f"🎬 Buscando no YouTube (Scraper): '{query}'")
            
            # Formatar query
            search_query = query.replace(' ', '+')
            url = f"https://www.youtube.com/results?search_query={search_query}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            html = response.text
            
            # Estrategia: Dividir por blocos de videoRenderer para manter contexto ID <-> Título
            results = []
            video_blocks = html.split('"videoRenderer":')
            
            # Pular o primeiro chunk (antes do primeiro video)
            for block in video_blocks[1:]:
                # Limitar tamanho do bloco para performance/evitar falsos positivos distantes
                block_sample = block[:4000] 
                
                # Extrair ID
                id_match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', block_sample)
                # Extrair Titulo
                # Padrao comum: "title":{"runs":[{"text":"TITULO"}]}
                title_match = re.search(r'"title":{"runs":\[{"text":"(.*?)"}\]', block_sample)
                
                if id_match:
                    vid_id = id_match.group(1)
                    title = title_match.group(1) if title_match else "Título não identificado"
                    
                    # Limpar escapes do JSON no titulo (ex: \" -> ")
                    title = title.replace('\\"', '"').replace("\\'", "'")
                    
                    # Evitar duplicatas
                    if not any(r['id'] == vid_id for r in results):
                        results.append({'id': vid_id, 'title': title})
                        
                    if len(results) >= 5:
                        break
            
            if not results:
                return "Nenhum vídeo encontrado. Tente termos diferentes."
                
            output = "VÍDEOS ENCONTRADOS:\n"
            for item in results:
                output += f"- Título: {item['title']} | Link: https://www.youtube.com/watch?v={item['id']} (ID: {item['id']})\n"
            
            return output

        except Exception as e:
            return f"Erro ao buscar vídeos no YouTube: {str(e)}"

# Instância
youtube_video_search_tool = YouTubeVideoSearchTool()
