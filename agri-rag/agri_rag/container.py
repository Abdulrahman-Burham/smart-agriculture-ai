"""Dependency container: builds and wires every component once."""
from __future__ import annotations

from dataclasses import dataclass

from .alerts.agent import AlertAgent
from .alerts.rules import CropProfiles
from .config import Settings, get_settings
from .domain.weather import OpenMeteoProvider, WeatherService
from .generation.llm import LLMClient, get_llm
from .nlp.glossary import Glossary
from .pipeline import RagPipeline
from .retrieval.embeddings import Embedder, get_embedder
from .retrieval.hybrid import HybridRetriever
from .retrieval.vectorstore import ChromaStore
from .sessions import InMemorySessionStore


@dataclass
class Container:
    settings: Settings
    embedder: Embedder
    store: ChromaStore
    retriever: HybridRetriever
    llm: LLMClient
    pipeline: RagPipeline
    alert_agent: AlertAgent
    weather: WeatherService


def build_container(settings: Settings | None = None, llm: LLMClient | None = None,
                    persistent: bool = True) -> Container:
    s = settings or get_settings()
    embedder = get_embedder(s)
    store = ChromaStore(s.chroma_dir if persistent else None, s.collection, embedder)
    glossary = Glossary.load(s.glossary_path)
    retriever = HybridRetriever(store, embedder, glossary, s)
    llm = llm or get_llm(s)
    sessions = InMemorySessionStore(s.session_max_turns, s.session_ttl_s)
    weather = WeatherService(OpenMeteoProvider(s.weather_timeout_s, s.weather_cache_ttl_s), s.weather_enabled)
    pipeline = RagPipeline(retriever, llm, sessions, s, weather)
    agent = AlertAgent(pipeline, CropProfiles.load(s.crop_profiles_path), weather=weather)
    return Container(s, embedder, store, retriever, llm, pipeline, agent, weather)
