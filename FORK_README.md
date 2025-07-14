# 🍴 MCP Crawl4AI-RAG Fork

## 📋 **Fork-Informationen**

- **Original Repository:** [coleam00/mcp-crawl4ai-rag](https://github.com/coleam00/mcp-crawl4ai-rag)
- **Fork Repository:** [Silverstar187/mcp-crawl4ai-rag](https://github.com/Silverstar187/mcp-crawl4ai-rag)
- **Fork erstellt:** 14. Juli 2025
- **Zweck:** Verbesserungen und umfassende Tests der MCP Tools

## 🎯 **Ziele dieses Forks**

1. **Umfassende Tool-Tests** - Alle MCP Tools auf Funktionalität prüfen
2. **Performance-Optimierungen** - Lazy Loading und Startup-Verbesserungen
3. **Dokumentation** - Ausführliche Dokumentation aller Features
4. **Bug-Fixes** - Behebung identifizierter Probleme
5. **Erweiterungen** - Neue Features und Verbesserungen

## ✅ **Durchgeführte Tests & Verbesserungen**

### **Erfolgreich getestete Tools:**
- ✅ `smart_crawl_url` - 11+ Seiten gecrawlt, 39+ Chunks gespeichert
- ✅ `crawl_single_page` - Einzelseiten-Crawling funktioniert
- ✅ `perform_rag_query` - Hybrid-Suche mit Reranking
- ✅ `search_code_examples` - Code-Extraktion und Kategorisierung
- ✅ `get_available_sources` - 4 Quellen verfügbar
- ✅ `query_knowledge_graph` - Neo4j-Integration aktiv
- ✅ Lazy Loading - CrossEncoder und Knowledge Graph nur bei Bedarf geladen

### **Identifizierte Probleme:**
- ⚠️ `parse_github_repository` - Git-Installation im Docker Container erforderlich
- ⚠️ `check_ai_script_hallucinations` - Pfad-Handling-Problem
- ⚠️ Reranking sehr streng kalibriert (funktioniert, aber konservativ)

## 🔧 **Implementierte Verbesserungen**

### **1. Lazy Loading Optimierung**
```python
# Schwere Komponenten werden nur bei Bedarf geladen
@asynccontextmanager
async def get_reranking_model(ctx: Crawl4AIContext) -> Optional[CrossEncoder]:
    if ctx.reranking_model is None:
        ctx.reranking_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    return ctx.reranking_model
```

### **2. Supabase-Integration**
- Vollständige Datenbankstruktur implementiert
- Vector-Similarity-Suche mit IVFFlat-Indizes
- Automatisches Chunking mit Kontext-Erhaltung
- Code-Beispiel-Extraktion und Zusammenfassung

### **3. Knowledge Graph**
- Neo4j-Integration für Hallucination-Detection
- Repository-Parsing für Python-Code
- Klassen-, Methoden- und Funktions-Analyse
- Cypher-Query-Interface

## 📊 **Test-Ergebnisse**

### **Pipecat Dokumentation Crawl:**
- **Seiten gecrawlt:** 11+
- **Content-Chunks:** 39+
- **Code-Beispiele:** 4+
- **Quellen:** 4 (docs.pipecat.ai, flows.pipecat.ai, etc.)

### **RAG-Suche Performance:**
- **Hybrid-Suche:** Funktioniert
- **Reranking:** Aktiv, aber streng kalibriert
- **Similarity-Scores:** 0.5-0.7 für relevante Ergebnisse
- **Rerank-Scores:** +2.3 für sehr relevant, -11.3 für irrelevant

### **Knowledge Graph Statistiken:**
- **Repositories:** 2 (crawl4ai, pipecat)
- **Pipecat:** 305 Dateien, 693 Klassen, 1236 Methoden
- **Crawl4AI:** Vollständig analysiert

## 🚀 **Nächste Schritte**

### **Geplante Verbesserungen:**
1. **Git-Installation** im Docker-Image für Repository-Parsing
2. **Reranking-Kalibrierung** weniger streng einstellen
3. **Pfad-Handling** für Hallucination-Detection reparieren
4. **Performance-Monitoring** für alle Tools
5. **Zusätzliche Tests** für Edge-Cases

### **Neue Features:**
1. **Batch-Processing** für große Crawling-Jobs
2. **Caching-Mechanismen** für häufige Anfragen
3. **Monitoring-Dashboard** für Tool-Performance
4. **API-Rate-Limiting** für externe Services

## 📚 **Dokumentation**

### **Supabase-Schema:**
```sql
-- Haupttabellen
CREATE TABLE sources (source_id, summary, total_word_count, timestamps);
CREATE TABLE crawled_pages (id, url, content, embedding, metadata);
CREATE TABLE code_examples (id, url, code, summary, embedding);

-- Vector-Suche
CREATE INDEX ON crawled_pages USING ivfflat (embedding vector_cosine_ops);
```

### **MCP Tools Übersicht:**
- `smart_crawl_url` - Intelligentes Website-Crawling
- `crawl_single_page` - Einzelseiten-Crawling
- `perform_rag_query` - RAG-Suche mit Reranking
- `search_code_examples` - Code-Beispiel-Suche
- `get_available_sources` - Verfügbare Quellen auflisten
- `query_knowledge_graph` - Neo4j-Abfragen
- `parse_github_repository` - Repository-Analyse
- `check_ai_script_hallucinations` - AI-Hallucination-Detection

## 🤝 **Beitrag zum Original-Projekt**

Alle Verbesserungen in diesem Fork sind darauf ausgelegt, zurück zum Original-Repository beigetragen zu werden:

1. **Pull Request** mit umfassenden Tests
2. **Dokumentation** aller Änderungen
3. **Rückwärtskompatibilität** gewährleistet
4. **Performance-Verbesserungen** ohne Breaking Changes

## 📞 **Kontakt**

Bei Fragen oder Anregungen zu diesem Fork:
- GitHub: [@Silverstar187](https://github.com/Silverstar187)
- Issues: [Fork Issues](https://github.com/Silverstar187/mcp-crawl4ai-rag/issues)

---

**Hinweis:** Dieser Fork dient der Verbesserung und Erweiterung der MCP Crawl4AI-RAG Tools. Alle Änderungen sind dokumentiert und getestet. 