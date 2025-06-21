#!/usr/bin/env python3
"""
Batch Crawler Simple - Versão simplificada que funciona com FastMCP

Usa a estratégia mais simples: requisições HTTP diretas para invocar as ferramentas MCP.
"""

import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse


class BatchCrawlerSimple:
    def __init__(self, server_url: str = "http://localhost:8051", delay: float = 1.0):
        self.server_url = server_url.rstrip('/')
        self.delay = delay
    
    def test_connection(self) -> bool:
        """Testa se o servidor MCP está rodando."""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=10)
            if response.status_code == 200:
                print(f"✅ Servidor MCP conectado: {self.server_url}")
                return True
            else:
                print(f"❌ Servidor retornou status {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erro ao conectar: {e}")
            return False
    
    def crawl_url_via_sse(self, url: str) -> Dict[str, Any]:
        """
        Tenta crawl via Server-Sent Events endpoint do FastMCP.
        
        FastMCP geralmente expõe um endpoint SSE para comunicação em tempo real.
        """
        try:
            # Payload no formato esperado pelo FastMCP
            payload = {
                "tool": "crawl_single_page",
                "arguments": {
                    "url": url
                }
            }
            
            # Tentar diferentes formatos de endpoint
            endpoints = [
                "/tools/crawl_single_page",
                "/api/tools/crawl_single_page", 
                "/mcp/tools/crawl_single_page",
                "/crawl_single_page"
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.post(
                        f"{self.server_url}{endpoint}",
                        json=payload,
                        headers={'Content-Type': 'application/json'},
                        timeout=120
                    )
                    
                    if response.status_code == 200:
                        return {
                            "success": True,
                            "url": url,
                            "data": response.json(),
                            "method": f"mcp{endpoint}"
                        }
                    elif response.status_code == 404:
                        continue  # Tentar próximo endpoint
                    else:
                        print(f"Endpoint {endpoint} retornou {response.status_code}")
                        continue
                        
                except requests.exceptions.RequestException:
                    continue  # Tentar próximo endpoint
            
            # Se nenhum endpoint funcionou
            return {
                "success": False,
                "url": url,
                "error": "Nenhum endpoint MCP válido encontrado"
            }
            
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": f"Erro na requisição MCP: {str(e)}"
            }
    
    def crawl_url_direct_post(self, url: str) -> Dict[str, Any]:
        """
        Método alternativo: POST direto no root do servidor.
        Alguns servidores FastMCP aceitam POSTs na raiz.
        """
        try:
            # Formato JSON-RPC 2.0 
            rpc_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "crawl_single_page",
                    "arguments": {
                        "url": url
                    }
                }
            }
            
            response = requests.post(
                self.server_url,
                json=rpc_request,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                timeout=120
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "url": url,
                    "data": response.json(),
                    "method": "json-rpc"
                }
            else:
                return {
                    "success": False,
                    "url": url,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": f"Erro JSON-RPC: {str(e)}"
            }
    
    def crawl_url_fallback(self, url: str) -> Dict[str, Any]:
        """Fallback: crawl básico sem MCP."""
        try:
            response = requests.get(url, timeout=30)
            return {
                "success": True,
                "url": url,
                "data": {
                    "url": url,
                    "status_code": response.status_code,
                    "content_preview": response.text[:500] + "...",
                    "headers": dict(response.headers)
                },
                "method": "fallback"
            }
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": f"Fallback failed: {str(e)}"
            }
    
    def crawl_single_url(self, url: str) -> Dict[str, Any]:
        """Crawl uma URL tentando diferentes métodos."""
        print(f"🔄 Processando: {url}")
        start_time = time.time()
        
        # Método 1: Tentar via SSE/tools endpoint
        result = self.crawl_url_via_sse(url)
        if result["success"]:
            processing_time = time.time() - start_time
            result["processing_time"] = processing_time
            print(f"✅ Sucesso via {result['method']} - {processing_time:.2f}s")
            return result
        
        # Método 2: Tentar JSON-RPC direto
        print(f"⚠️  SSE falhou, tentando JSON-RPC...")
        result = self.crawl_url_direct_post(url)
        if result["success"]:
            processing_time = time.time() - start_time
            result["processing_time"] = processing_time
            print(f"✅ Sucesso via {result['method']} - {processing_time:.2f}s")
            return result
        
        # Método 3: Fallback básico
        print(f"⚠️  JSON-RPC falhou, usando fallback...")
        result = self.crawl_url_fallback(url)
        processing_time = time.time() - start_time
        result["processing_time"] = processing_time
        
        if result["success"]:
            print(f"✅ Sucesso via {result['method']} - {processing_time:.2f}s")
        else:
            print(f"❌ Falha total - {processing_time:.2f}s")
        
        return result
    
    def load_urls(self, file_path: str) -> List[str]:
        """Carrega URLs de um arquivo."""
        urls = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and line.startswith(('http://', 'https://')):
                        urls.append(line)
            print(f"📂 Carregadas {len(urls)} URLs de {file_path}")
            return urls
        except Exception as e:
            print(f"❌ Erro ao carregar {file_path}: {e}")
            return []
    
    def process_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Processa lista de URLs."""
        results = []
        total = len(urls)
        
        print(f"\n🚀 Iniciando processamento de {total} URLs...")
        print("=" * 50)
        
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{total}] {url}")
            
            result = self.crawl_single_url(url)
            results.append(result)
            
            # Delay entre requisições (exceto na última)
            if i < total and self.delay > 0:
                print(f"⏳ Aguardando {self.delay}s...")
                time.sleep(self.delay)
        
        return results
    
    def save_results(self, results: List[Dict[str, Any]], output_file: str):
        """Salva resultados em arquivo JSON."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            # Estatísticas
            successful = sum(1 for r in results if r["success"])
            failed = len(results) - successful
            
            methods = {}
            for r in results:
                if r["success"]:
                    method = r.get("method", "unknown")
                    methods[method] = methods.get(method, 0) + 1
            
            print("\n" + "=" * 50)
            print("📊 RESULTADO FINAL")
            print("=" * 50)
            print(f"Total processadas: {len(results)}")
            print(f"✅ Sucessos: {successful}")
            print(f"❌ Falhas: {failed}")
            print("\nMétodos utilizados:")
            for method, count in methods.items():
                print(f"  {method}: {count}")
            print(f"\n💾 Resultados salvos em: {output_file}")
            print("=" * 50)
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao salvar resultados: {e}")
            return False
    
    def run(self, urls_file: str, output_file: str = "results.json") -> bool:
        """Executa o crawler completo."""
        print("🎯 Batch Crawler Simple - FastMCP")
        print("=" * 50)
        
        # Testar conexão
        if not self.test_connection():
            print("⚠️  Servidor MCP inacessível, usando apenas fallback")
        
        # Carregar URLs
        urls = self.load_urls(urls_file)
        if not urls:
            print("❌ Nenhuma URL válida encontrada")
            return False
        
        # Processar URLs
        results = self.process_urls(urls)
        
        # Salvar resultados
        return self.save_results(results, output_file)


def main():
    """Interface de linha de comando."""
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python batch_crawler_simple.py <arquivo_urls> [arquivo_saida] [delay]")
        print("Exemplo: python batch_crawler_simple.py sitemap_urls.txt results.json 1.5")
        
        # Listar arquivos .txt disponíveis
        txt_files = list(Path(".").glob("*.txt"))
        if txt_files:
            print(f"\nArquivos .txt encontrados:")
            for i, f in enumerate(txt_files, 1):
                print(f"  {i}. {f.name}")
            
            try:
                choice = input(f"\nEscolha um arquivo (1-{len(txt_files)}) ou Enter para sair: ")
                if choice.strip():
                    idx = int(choice) - 1
                    if 0 <= idx < len(txt_files):
                        urls_file = str(txt_files[idx])
                        output_file = input("Arquivo de saída [results.json]: ").strip() or "results.json"
                        delay = float(input("Delay entre requests [1.0]: ").strip() or "1.0")
                        
                        crawler = BatchCrawlerSimple(delay=delay)
                        crawler.run(urls_file, output_file)
            except (ValueError, KeyboardInterrupt):
                print("❌ Operação cancelada")
        
        return
    
    urls_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "results.json"
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    
    crawler = BatchCrawlerSimple(delay=delay)
    success = crawler.run(urls_file, output_file)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()