"""
Singletons compartilhados entre todos os módulos do Alexandria-AI.

Importe a partir daqui em vez de reinstanciar em cada módulo:

    from src.container import loader, graph, search_engine, gutenberg
"""

from src.ingestion.document_loader import DocumentLoader
from src.knowledge.graph import KnowledgeGraph
from src.search.semantic_search import SemanticSearch
from src.prospectors.gutenberg import GutenbergProspector

loader: DocumentLoader = DocumentLoader()
graph: KnowledgeGraph = KnowledgeGraph()
search_engine: SemanticSearch = SemanticSearch()
gutenberg: GutenbergProspector = GutenbergProspector(
    search_engine=search_engine, graph=graph
)
