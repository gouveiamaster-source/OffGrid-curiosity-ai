#!/usr/bin/env python3
"""
prospect_gutenberg.py — CLI para prospecção em lote do Project Gutenberg.

Uso:
    python scripts/prospect_gutenberg.py --query "Machado de Assis" --lang pt --limit 5
    python scripts/prospect_gutenberg.py --ids 55752 67526 12345
    python scripts/prospect_gutenberg.py --topic "Science fiction" --lang en --limit 10
    python scripts/prospect_gutenberg.py --catalog          # lista catálogo local
    python scripts/prospect_gutenberg.py --stats            # estatísticas

O script inicializa os motores Alexandria-AI e indexa os livros diretamente
(sem necessidade de o servidor estar rodando).
"""

import argparse
import sys
import os

# Garante que o root do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from src.knowledge.graph import KnowledgeGraph
from src.search.semantic_search import SemanticSearch
from src.prospectors.gutenberg import GutenbergProspector


def build_engines():
    logger.info("Inicializando motores Alexandria-AI…")
    os.makedirs("data/index", exist_ok=True)
    se = SemanticSearch()
    se.load_index()
    g = KnowledgeGraph()
    return se, g


def fmt_book(b) -> str:
    authors = ", ".join(b.authors) if b.authors else "Autor desconhecido"
    langs = "/".join(b.languages)
    return f"  [{b.id:>7}] {b.title[:60]:<60}  {authors[:30]:<30}  [{langs}]"


def cmd_prospect(args):
    se, g = build_engines()
    prospector = GutenbergProspector(search_engine=se, graph=g)

    book_ids = args.ids if args.ids else None
    langs = args.lang.split(",") if args.lang else None

    print(f"\n🔍 Prospectando Project Gutenberg…")
    if args.query:
        print(f"   Busca: '{args.query}'")
    if book_ids:
        print(f"   IDs: {book_ids}")
    if langs:
        print(f"   Idiomas: {langs}")
    if args.topic:
        print(f"   Tópico: {args.topic}")
    print()

    results = prospector.prospect(
        query=args.query or "",
        book_ids=book_ids,
        languages=langs,
        topic=args.topic or "",
        limit=args.limit,
        skip_already_ingested=not args.force,
    )

    ok = failed = skipped = 0
    for r in results:
        icon = {"ok": "✅", "already_indexed": "⏭", "download_failed": "❌",
                "ingest_failed": "⚠️", "downloaded_only": "📥"}.get(r.status, "?")
        authors = ", ".join(r.authors[:2])
        print(f"  {icon}  [{r.book_id}] {r.title[:55]:<55}  {authors[:25]}")
        if r.status == "ok":
            print(f"       → {r.chunks} chunks · {r.entities} entidades · doc_id={r.document_id}")
            ok += 1
        elif r.status == "already_indexed":
            print(f"       → já indexado, pulando.")
            skipped += 1
        elif r.error:
            print(f"       → {r.error}")
            failed += 1

    print(f"\n  Resultado: {ok} indexados · {skipped} pulados · {failed} falhas")
    se.save_index()


def cmd_catalog(args):
    prospector = GutenbergProspector()
    books = prospector.get_cached_books()
    if not books:
        print("Catálogo local vazio. Execute uma prospecção primeiro.")
        return
    print(f"\n📚 Catálogo local ({len(books)} livros):\n")
    for b in sorted(books, key=lambda x: x["id"]):
        ingested = "✅" if b["ingested"] else ("📥" if b["local_path"] else "📋")
        authors = ", ".join(b["authors"][:2]) if b["authors"] else "—"
        langs = "/".join(b["languages"])
        print(f"  {ingested} [{b['id']:>7}] {b['title'][:55]:<55}  {authors[:25]:<25}  [{langs}]")


def cmd_stats(args):
    prospector = GutenbergProspector()
    s = prospector.catalog_stats()
    print(f"\n📊 Estatísticas do catálogo Gutenberg:")
    print(f"   Total catalogado : {s['total_catalogued']}")
    print(f"   Baixados         : {s['downloaded']}")
    print(f"   Indexados        : {s['ingested']}")


def cmd_search(args):
    """Apenas busca no catálogo remoto e lista — sem baixar."""
    prospector = GutenbergProspector()
    langs = args.lang.split(",") if args.lang else None
    books = prospector.search_catalog(
        query=args.query or "",
        languages=langs,
        topic=args.topic or "",
        limit=args.limit,
    )
    if not books:
        print("Nenhum resultado encontrado.")
        return
    print(f"\n🔎 Resultados da busca ({len(books)}):\n")
    for b in books:
        ingested = "✅" if b.ingested else ("📥" if b.local_path else "  ")
        authors = ", ".join(b.authors[:2]) if b.authors else "—"
        langs_s = "/".join(b.languages)
        print(f"  {ingested} [{b.id:>7}] {b.title[:55]:<55}  {authors[:25]:<25}  [{langs_s}]  ⬇{b.download_count}")
    print()


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Alexandria-AI — Prospector Project Gutenberg"
    )
    sub = parser.add_subparsers(dest="cmd")

    # prospect
    p = sub.add_parser("prospect", help="Baixa e indexa livros")
    p.add_argument("--query", "-q", default="", help="Busca textual")
    p.add_argument("--ids", "-i", type=int, nargs="+", help="IDs específicos de livros")
    p.add_argument("--lang", "-l", default="", help="Idiomas separados por vírgula (ex: pt,en)")
    p.add_argument("--topic", "-t", default="", help="Filtro de tópico")
    p.add_argument("--limit", "-n", type=int, default=5, help="Máximo de livros")
    p.add_argument("--force", action="store_true", help="Re-indexa mesmo se já indexado")

    # search
    s = sub.add_parser("search", help="Busca no catálogo remoto sem baixar")
    s.add_argument("--query", "-q", default="")
    s.add_argument("--lang", "-l", default="")
    s.add_argument("--topic", "-t", default="")
    s.add_argument("--limit", "-n", type=int, default=20)

    # catalog
    sub.add_parser("catalog", help="Lista o catálogo local")

    # stats
    sub.add_parser("stats", help="Exibe estatísticas do catálogo")

    args = parser.parse_args()

    # Atalhos: args sem subcomando com --query tratados como prospect
    if args.cmd is None:
        parser.print_help()
        return

    dispatch = {
        "prospect": cmd_prospect,
        "search": cmd_search,
        "catalog": cmd_catalog,
        "stats": cmd_stats,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
