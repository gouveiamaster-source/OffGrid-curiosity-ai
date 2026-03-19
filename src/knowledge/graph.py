"""
Grafo de conhecimento com NetworkX.

Nós:
  - tipo "document"  → cada documento ingerido
  - tipo "entity"    → entidades nomeadas extraídas

Arestas:
  - "contains"  → documento → entidade
  - "co_occurs" → entidade ↔ entidade (quando aparecem no mesmo documento)
"""

from __future__ import annotations

import json
import os
from typing import Any

import networkx as nx
from loguru import logger

from src.ingestion.document_loader import AlexDocument
from src.models.schemas import GraphStats

GRAPH_PATH = "data/index/knowledge_graph.json"


class KnowledgeGraph:
    def __init__(self):
        self.G: nx.Graph = nx.Graph()
        self._load()

    # ------------------------------------------------------------------
    # Operações principais
    # ------------------------------------------------------------------

    def add_document(self, doc: AlexDocument) -> None:
        """Adiciona um documento e suas entidades ao grafo."""
        # Nó do documento
        self.G.add_node(
            f"doc:{doc.id}",
            type="document",
            label=doc.filename,
            doc_id=doc.id,
        )

        # Nós de entidades + arestas documento→entidade
        for entity in doc.entities:
            ent_key = f"ent:{entity.lower()}"
            if not self.G.has_node(ent_key):
                self.G.add_node(ent_key, type="entity", label=entity)
            self.G.add_edge(f"doc:{doc.id}", ent_key, relation="contains")

        # Arestas de co-ocorrência entre entidades do mesmo documento
        ents = [f"ent:{e.lower()}" for e in doc.entities]
        for i in range(len(ents)):
            for j in range(i + 1, len(ents)):
                if self.G.has_edge(ents[i], ents[j]):
                    self.G[ents[i]][ents[j]]["weight"] = (
                        self.G[ents[i]][ents[j]].get("weight", 1) + 1
                    )
                else:
                    self.G.add_edge(ents[i], ents[j], relation="co_occurs", weight=1)

        self._save()
        logger.info(
            f"Grafo atualizado: {self.G.number_of_nodes()} nós, "
            f"{self.G.number_of_edges()} arestas"
        )

    def remove_document(self, doc_id: str) -> None:
        doc_key = f"doc:{doc_id}"
        if self.G.has_node(doc_key):
            # Remove arestas "contains" e nós entidade que ficaram isolados
            neighbors = list(self.G.neighbors(doc_key))
            self.G.remove_node(doc_key)
            for n in neighbors:
                if self.G.degree(n) == 0:
                    self.G.remove_node(n)
            self._save()

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def stats(self) -> GraphStats:
        docs = sum(1 for _, d in self.G.nodes(data=True) if d.get("type") == "document")
        ents = sum(1 for _, d in self.G.nodes(data=True) if d.get("type") == "entity")
        return GraphStats(
            nodes=self.G.number_of_nodes(),
            edges=self.G.number_of_edges(),
            documents=docs,
            entities=ents,
        )

    def get_nodes(self, limit: int = 100) -> list[dict[str, Any]]:
        nodes = []
        for node_id, data in list(self.G.nodes(data=True))[:limit]:
            nodes.append({"id": node_id, **data})
        return nodes

    def get_edges(self, limit: int = 200) -> list[dict[str, Any]]:
        edges = []
        for u, v, data in list(self.G.edges(data=True))[:limit]:
            edges.append({"source": u, "target": v, **data})
        return edges

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------

    def _save(self) -> None:
        os.makedirs(os.path.dirname(GRAPH_PATH), exist_ok=True)
        data = nx.node_link_data(self.G)
        with open(GRAPH_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _load(self) -> None:
        if os.path.exists(GRAPH_PATH):
            try:
                with open(GRAPH_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                self.G = nx.node_link_graph(data)
                logger.info(
                    f"Grafo carregado: {self.G.number_of_nodes()} nós, "
                    f"{self.G.number_of_edges()} arestas"
                )
            except Exception as e:
                logger.warning(f"Falha ao carregar grafo, iniciando vazio: {e}")
                self.G = nx.Graph()
