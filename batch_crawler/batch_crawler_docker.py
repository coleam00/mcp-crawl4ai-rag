#!/usr/bin/env python3
"""
Batch Crawler Docker - Usa o servidor MCP que já está rodando no Docker

Este script se conecta ao servidor MCP via HTTP requests para fazer crawling batch.
Não precisa instalar dependências localmente - usa o servidor Docker.
"""

import json
import time
import requests
import sys
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse


class BatchCrawlerDocker:
    """Cliente que usa o servidor MCP rodando no Docker container."""
    
    def __init__(self, server_url: str = "http://localhost:8051", delay: float = 1.0):
        self.server_url = server_url.rstrip('/')
        self.delay = delay
        self.session = requests.Session()
        self.session.timeout = 120
    
    def test_connection(self) -> bool:
        """Testa conexão com servidor MCP no Docker."""
        try:
            response = self.session.get(f"{self.server_url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Servidor MCP conectado: {self.server_url}")
                print(f"   Status: {health_data.get('status', 'unknown')}")
                
                services = health_data.get('services', {})
                for service, status in services.items():
                    if isinstance(status, dict):
                        service_status = status.get('status', 'unknown')
                        print(f"   {service}: {service_status}")
                
                return True
            else:
                print(f"❌ Servidor retornou status {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Erro ao conectar: {e}")
            return False
    
    def invoke_mcp_tool_via_docker(self, tool_name: str, arguments: dict) -> Dict[str, Any]:
        """
        Invoca uma ferramenta MCP usando exec no container Docker.
        
        Esta é a estratégia mais direta: executar comandos dentro do container
        onde todas as dependências estão disponíveis.
        """
        try:
            import subprocess
            
            # Comando para executar dentro do container Docker
            docker_cmd = [
                "docker", "exec", "-i", "mcp-crawl4ai-rag-mcp-server-1",
                "python3", "-c", f"""
import json
import sys
import os
sys.path.append('/app/src')

# Import das ferramentas MCP
from crawl4ai_mcp import mcp

# Preparar argumentos
tool_name = '{tool_name}'
arguments = {json.dumps(arguments)}

try:
    # Simular uma chamada de ferramenta
    if tool_name == 'crawl_single_page':
        from crawl4ai_mcp import crawl_single_page
        
        # Criar um contexto mock (normalmente seria fornecido pelo FastMCP)
        class MockContext:
            def __init__(self):
                # Não precisamos do contexto completo para teste
                pass
        
        context = MockContext()
        
        # Chamar a função diretamente
        result = crawl_single_page(url=arguments['url'])
        
        # Retornar resultado como JSON
        print(json.dumps({{"success": True, "result": result}}))
    else:
        print(json.dumps({{"success": False, "error": f"Tool {{tool_name}} not supported"}}))
        
except Exception as e:
    import traceback
    print(json.dumps({{"success": False, "error": str(e), "traceback": traceback.format_exc()}}))
"""
            ]
            
            # Executar comando
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                # Parse da resposta JSON
                try:
                    response_data = json.loads(result.stdout.strip())
                    return response_data
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": f"Resposta JSON inválida: {result.stdout[:200]}"
                    }
            else:
                return {
                    "success": False,
                    "error": f"Docker exec falhou: {result.stderr}"
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout na execução Docker"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro na execução Docker: {str(e)}"
            }
    
    def crawl_single_url(self, url: str) -> Dict[str, Any]:
        """Crawl uma URL usando o container Docker."""
        print(f"🔄 Processando: {url}")
        start_time = time.time()
        
        try:
            # Método 1: Tentar via Docker exec
            result = self.invoke_mcp_tool_via_docker("crawl_single_page", {"url": url})
            
            processing_time = time.time() - start_time
            
            if result.get("success"):
                print(f"✅ Sucesso via Docker MCP - {processing_time:.2f}s")
                return {
                    "success": True,
                    "url": url,
                    "data": result.get("result"),
                    "processing_time": processing_time,
                    "method": "docker-mcp",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                print(f"⚠️  Docker MCP falhou: {result.get('error', 'Unknown error')}")
                # Fallback para HTTP simples
                return self.crawl_url_fallback(url, start_time)
                
        except Exception as e:
            print(f"⚠️  Erro Docker: {e}")
            return self.crawl_url_fallback(url, start_time)
    
    def crawl_url_fallback(self, url: str, start_time: float) -> Dict[str, Any]:
        """Fallback: crawl HTTP básico."""
        try:
            print(f"🔄 Usando fallback HTTP para: {url}")
            
            response = self.session.get(url, timeout=30)
            processing_time = time.time() - start_time
            
            if response.status_code == 200:
                print(f"✅ Sucesso via fallback HTTP - {processing_time:.2f}s")
                return {
                    "success": True,
                    "url": url,
                    "data": {
                        "url": url,
                        "status_code": response.status_code,
                        "title": self._extract_title(response.text),
                        "content_preview": response.text[:1000] + "...",
                        "content_type": response.headers.get("content-type", ""),
                        "content_length": len(response.text)
                    },
                    "processing_time": processing_time,
                    "method": "fallback-http",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                processing_time = time.time() - start_time
                print(f"❌ Fallback falhou: HTTP {response.status_code}")
                return {
                    "success": False,
                    "url": url,
                    "error": f"HTTP {response.status_code}",
                    "processing_time": processing_time,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
        except Exception as e:
            processing_time = time.time() - start_time
            print(f"❌ Fallback falhou: {str(e)}")
            return {
                "success": False,
                "url": url,
                "error": f"Fallback failed: {str(e)}",
                "processing_time": processing_time,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
    
    def _extract_title(self, html: str) -> str:
        """Extrai título simples do HTML."""
        try:
            import re
            match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            return match.group(1).strip() if match else "No title"
        except:
            return "No title"
    
    def load_urls(self, file_path: str) -> List[str]:
        """Carrega URLs de um arquivo."""
        urls = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and line.startswith(('http://', 'https://')):
                        try:
                            parsed = urlparse(line)
                            if parsed.netloc:
                                urls.append(line)
                        except:
                            continue
            
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
        print("=" * 60)
        
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{total}] {url}")
            
            result = self.crawl_single_url(url)
            results.append(result)
            
            # Delay entre requisições (exceto na última)
            if i < total and self.delay > 0:
                print(f"⏳ Aguardando {self.delay}s...")
                time.sleep(self.delay)
        
        return results
    
    def save_results(self, results: List[Dict[str, Any]], output_file: str) -> bool:
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
            
            print("\n" + "=" * 60)
            print("📊 RESULTADO FINAL")
            print("=" * 60)
            print(f"Total processadas: {len(results)}")
            print(f"✅ Sucessos: {successful}")
            print(f"❌ Falhas: {failed}")
            print(f"Taxa de sucesso: {successful/len(results)*100:.1f}%")
            print("\nMétodos utilizados:")
            for method, count in methods.items():
                print(f"  {method}: {count} URLs")
            print(f"\n💾 Resultados salvos em: {output_file}")
            print("=" * 60)
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao salvar resultados: {e}")
            return False
    
    def run(self, urls_file: str, output_file: str = "results.json") -> bool:
        """Executa o crawler completo."""
        print("🎯 Batch Crawler Docker - MCP Container")
        print("=" * 60)
        
        # Testar conexão
        if not self.test_connection():
            print("⚠️  Continuando sem verificação de saúde...")
        
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
    if len(sys.argv) < 2:
        print("Uso: python batch_crawler_docker.py <arquivo_urls> [arquivo_saida] [delay]")
        print("Exemplo: python batch_crawler_docker.py sitemap_urls.txt results.json 1.5")
        
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
                        
                        crawler = BatchCrawlerDocker(delay=delay)
                        success = crawler.run(urls_file, output_file)
                        
                        if not success:
                            sys.exit(1)
            except (ValueError, KeyboardInterrupt):
                print("❌ Operação cancelada")
        
        return
    
    urls_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "results.json"
    delay = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    
    crawler = BatchCrawlerDocker(delay=delay)
    success = crawler.run(urls_file, output_file)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()