#!/usr/bin/env python3
"""
Batch Crawler Script for MCP Crawl4AI RAG Server

Este script lê URLs de um arquivo texto e processa cada uma sequencialmente
usando a função crawl_single_page do servidor MCP.

Usage:
    python batch_crawler.py urls.txt
    python batch_crawler.py urls.txt --output results.json --delay 2 --server-url http://localhost:8051
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import re

import httpx
import aiofiles


class BatchCrawler:
    """Cliente para processar URLs sequencialmente via servidor MCP (SSE)."""
    
    def __init__(self, server_url: str = "http://localhost:8051", delay: float = 1.0):
        self.server_url = server_url.rstrip('/')
        self.delay = delay
        self.session: Optional[httpx.AsyncClient] = None
        self.results: List[Dict[str, Any]] = []
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Configura sistema de logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'crawler_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def validate_url(self, url: str) -> bool:
        """Valida formato da URL."""
        if not url or not isinstance(url, str):
            return False
            
        url = url.strip()
        if not url:
            return False
            
        # Regex simples para validar URL
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
        return bool(url_pattern.match(url))
        
    async def read_urls(self, file_path: str) -> List[str]:
        """Lê URLs do arquivo texto."""
        self.logger.info(f"Lendo URLs de: {file_path}")
        
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
            
        urls = []
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            async for line in f:
                url = line.strip()
                if url and not url.startswith('#'):  # Ignora linhas vazias e comentários
                    if self.validate_url(url):
                        urls.append(url)
                    else:
                        self.logger.warning(f"URL inválida ignorada: {url}")
                        
        self.logger.info(f"Total de URLs válidas carregadas: {len(urls)}")
        return urls
        
    async def initialize_session(self):
        """Inicializa sessão HTTP."""
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0),  # 2 minutos timeout
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1)
        )
        
    async def close_session(self):
        """Fecha sessão HTTP."""
        if self.session:
            await self.session.aclose()
            
    async def test_server_connection(self) -> bool:
        """Testa conexão com servidor MCP."""
        try:
            self.logger.info(f"Testando conexão com servidor: {self.server_url}")
            
            # Tentar uma requisição GET simples - 404 é OK (servidor rodando)
            try:
                response = await self.session.get(self.server_url, timeout=5.0)
                if response.status_code in [200, 404, 405]:
                    self.logger.info("Servidor MCP está rodando e acessível")
                    return True
                else:
                    self.logger.warning(f"Servidor respondeu com status inesperado: {response.status_code}")
                    return False
            except httpx.ConnectError:
                self.logger.error("Não foi possível conectar - servidor provavelmente não está rodando")
                return False
            except httpx.TimeoutException:
                self.logger.error("Timeout na conexão - servidor pode estar sobrecarregado")
                return False
            except Exception as e:
                self.logger.error(f"Erro na verificação de conexão: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Erro geral ao testar conexão: {e}")
            self.logger.info("Verifique se o servidor está rodando com: uv run src/crawl4ai_mcp.py")
            return False
            
    async def crawl_single_url(self, url: str) -> Dict[str, Any]:
        """Processa uma única URL usando o servidor MCP."""
        start_time = time.time()
        
        try:
            self.logger.info(f"Iniciando crawl: {url}")
            
            # Preparar payload para FastMCP (JSON-RPC 2.0)
            payload = {
                "jsonrpc": "2.0",
                "id": int(time.time() * 1000),  # ID único baseado em timestamp
                "method": "tools/call",
                "params": {
                    "name": "crawl_single_page",
                    "arguments": {
                        "url": url
                    }
                }
            }
            
            # Fazer requisição para servidor FastMCP via SSE endpoint
            response = await self.session.post(
                f"{self.server_url}/sse",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                timeout=60.0
            )
            
            processing_time = time.time() - start_time
            
            if response.status_code == 200:
                result_data = response.json()
                
                # Parse do resultado do MCP
                if "result" in result_data and "content" in result_data["result"]:
                    content = result_data["result"]["content"]
                    
                    # Tentar fazer parse do JSON retornado pela ferramenta
                    try:
                        if isinstance(content, str):
                            crawl_result = json.loads(content)
                        else:
                            crawl_result = content
                            
                        success = crawl_result.get("success", False)
                        
                        result = {
                            "url": url,
                            "success": success,
                            "processing_time": round(processing_time, 2),
                            "timestamp": datetime.now().isoformat(),
                            "data": crawl_result
                        }
                        
                        if success:
                            chunks_stored = crawl_result.get("chunks_stored", 0)
                            content_length = crawl_result.get("content_length", 0)
                            self.logger.info(
                                f"✓ Sucesso: {url} - {chunks_stored} chunks, "
                                f"{content_length} chars em {processing_time:.1f}s"
                            )
                        else:
                            error_msg = crawl_result.get("error", "Erro desconhecido")
                            self.logger.error(f"✗ Falha: {url} - {error_msg}")
                            
                        return result
                        
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Erro ao fazer parse da resposta para {url}: {e}")
                        return {
                            "url": url,
                            "success": False,
                            "processing_time": round(processing_time, 2),
                            "timestamp": datetime.now().isoformat(),
                            "error": f"Parse error: {str(e)}",
                            "raw_response": str(content)
                        }
                        
                else:
                    self.logger.error(f"Resposta MCP inválida para {url}: {result_data}")
                    return {
                        "url": url,
                        "success": False,
                        "processing_time": round(processing_time, 2),
                        "timestamp": datetime.now().isoformat(),
                        "error": "Invalid MCP response format",
                        "raw_response": str(result_data)
                    }
                    
            else:
                self.logger.error(f"Erro HTTP {response.status_code} para {url}: {response.text}")
                return {
                    "url": url,
                    "success": False,
                    "processing_time": round(processing_time, 2),
                    "timestamp": datetime.now().isoformat(),
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
                
        except asyncio.TimeoutError:
            processing_time = time.time() - start_time
            self.logger.error(f"Timeout ao processar {url} após {processing_time:.1f}s")
            return {
                "url": url,
                "success": False,
                "processing_time": round(processing_time, 2),
                "timestamp": datetime.now().isoformat(),
                "error": "Request timeout"
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Erro inesperado ao processar {url}: {e}")
            return {
                "url": url,
                "success": False,
                "processing_time": round(processing_time, 2),
                "timestamp": datetime.now().isoformat(),
                "error": f"Unexpected error: {str(e)}"
            }
            
    async def process_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Processa lista de URLs sequencialmente."""
        total_urls = len(urls)
        results = []
        
        self.logger.info(f"Iniciando processamento de {total_urls} URLs")
        
        for i, url in enumerate(urls, 1):
            self.logger.info(f"Processando {i}/{total_urls}: {url}")
            
            result = await self.crawl_single_url(url)
            results.append(result)
            
            # Delay entre requisições (exceto na última)
            if i < total_urls:
                self.logger.debug(f"Aguardando {self.delay}s antes da próxima requisição...")
                await asyncio.sleep(self.delay)
                
        return results
        
    async def save_results(self, results: List[Dict[str, Any]], output_file: str):
        """Salva resultados em arquivo JSON."""
        summary = {
            "total_urls": len(results),
            "successful": sum(1 for r in results if r.get("success", False)),
            "failed": sum(1 for r in results if not r.get("success", False)),
            "total_processing_time": sum(r.get("processing_time", 0) for r in results),
            "generated_at": datetime.now().isoformat()
        }
        
        output_data = {
            "summary": summary,
            "results": results
        }
        
        async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(output_data, indent=2, ensure_ascii=False))
            
        self.logger.info(f"Resultados salvos em: {output_file}")
        self.logger.info(
            f"Resumo: {summary['successful']} sucessos, "
            f"{summary['failed']} falhas de {summary['total_urls']} URLs"
        )
        
    async def run(self, urls_file: str, output_file: str):
        """Executa o processo completo de crawling."""
        try:
            # Inicializar sessão
            await self.initialize_session()
            
            # Testar conexão com servidor
            if not await self.test_server_connection():
                self.logger.error("Não foi possível conectar ao servidor MCP. Verifique se está rodando.")
                return False
                
            # Ler URLs
            urls = await self.read_urls(urls_file)
            if not urls:
                self.logger.error("Nenhuma URL válida encontrada no arquivo")
                return False
                
            # Processar URLs
            results = await self.process_urls(urls)
            
            # Salvar resultados
            await self.save_results(results, output_file)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro durante execução: {e}")
            return False
            
        finally:
            await self.close_session()


async def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="Batch crawler para servidor MCP Crawl4AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python batch_crawler.py urls.txt
  python batch_crawler.py urls.txt --output meus_resultados.json
  python batch_crawler.py urls.txt --delay 2 --server-url http://localhost:8051
        """
    )
    
    parser.add_argument("urls_file", help="Arquivo texto com URLs (uma por linha)")
    parser.add_argument(
        "--output", "-o", 
        default="crawl_results.json",
        help="Arquivo de saída para resultados (padrão: crawl_results.json)"
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=1.0,
        help="Delay em segundos entre requisições (padrão: 1.0)"
    )
    parser.add_argument(
        "--server-url", "-s",
        default="http://localhost:8051",
        help="URL do servidor MCP (padrão: http://localhost:8051)"
    )
    
    args = parser.parse_args()
    
    # Validar arquivo de entrada
    if not Path(args.urls_file).exists():
        print(f"Erro: Arquivo '{args.urls_file}' não encontrado.")
        sys.exit(1)
        
    # Criar crawler e executar
    crawler = BatchCrawler(server_url=args.server_url, delay=args.delay)
    
    success = await crawler.run(args.urls_file, args.output)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())