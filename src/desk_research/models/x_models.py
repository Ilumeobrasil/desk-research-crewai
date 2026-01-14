# models.py
"""
Modelos de dados tipados para a crewAI_X, usando Pydantic.
Servem para validar e padronizar o formato dos tweets e, no futuro,
dos insights e análises.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class TweetMetrics(BaseModel):
    """Métricas de engajamento de um tweet."""

    likes: int = Field(0, description="Número de curtidas")
    retweets: int = Field(0, description="Número de retweets")
    replies: int = Field(0, description="Número de respostas")
    quotes: int = Field(0, description="Número de tweets com citação")


class Tweet(BaseModel):
    """
    Representa um tweet relevante para análise de social listening.

    Este modelo é o 'contrato' do que a nossa crew entende como tweet.
    """

    id: str = Field(..., description="ID único do tweet no X/Twitter")
    text: str = Field(..., description="Texto completo do tweet")
    author: str = Field(..., description="Nome de usuário do autor (ex.: @user)")
    created_at: str = Field(..., description="Data/hora em formato ISO 8601 (UTC)")
    language: str = Field("pt", description="Idioma do tweet (código ISO, ex.: 'pt')")
    metrics: TweetMetrics = Field(
        default_factory=TweetMetrics,
        description="Métricas de engajamento do tweet",
    )

    # Campo opcional para guardar info extra (ex.: se tem community notes, verificado, etc.)
    tags: Optional[List[str]] = Field(
        default=None,
        description="Lista opcional de tags (ex.: ['verified', 'community_notes'])",
    )
