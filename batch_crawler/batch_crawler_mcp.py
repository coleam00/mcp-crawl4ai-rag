#!/usr/bin/env python3
"""
Batch Crawler Script para MCP Crawl4AI RAG Server (usando cliente MCP oficial)

Este script lê URLs de um arquivo texto e processa cada uma sequencialmente
usando a função crawl_single_page do servidor MCP.

Usage:
    python batch_crawler_mcp.py urls.txt
    python batch_crawler_mcp.py urls.txt --output results.json --delay 2 --server-url http://localhost:8051
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
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class BatchCrawlerMCP:
    """Cliente para processar URLs sequencialmente via servidor MCP usando biblioteca oficial."""
    
    def __init__(self, server_url: str = "http://localhost:8051", delay: float = 1.0):
        self.server_url = server_url.rstrip('/')
        self.delay = delay
        self.session: Optional[ClientSession] = None
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
        
    async def test_server_connection(self) -> bool:
        """Testa conexão com servidor MCP."""
        try:
            self.logger.info(f"Testando conexão com servidor: {self.server_url}")
            
            # Tentar uma requisição GET simples - 404 é OK (servidor rodando)
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    response = await client.get(self.server_url)
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
            self.logger.error(f"Erro geral ao testar conexão: {e}")
            self.logger.info("Verifique se o servidor está rodando com: uv run src/crawl4ai_mcp.py")
            return False
            
    async def initialize_mcp_session(self):
        """Inicializa sessão MCP usando stdio (não SSE por limitações)."""
        try:
            self.logger.info("Inicializando sessão MCP...")
            
            # NOTA: Por limitações da biblioteca MCP atual, não podemos conectar diretamente
            # ao servidor SSE. Esta é uma limitação conhecida que seria resolvida com
            # uma implementação WebSocket/SSE do cliente MCP.
            
            self.logger.warning("Sessão MCP stdio não implementada - usando fallback HTTP")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao inicializar sessão MCP: {e}")
            return False
            
    async def crawl_single_url_fallback(self, url: str) -> Dict[str, Any]:
        """
        Fallback: chama diretamente a função do servidor (apenas para demonstração).
        Em produção, isso exigiria importar o código do servidor ou usar subprocess.
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Iniciando crawl (modo fallback): {url}")
            
            # Simular resultado para demonstração
            # Em uma implementação real, você precisaria:
            # 1. Usar subprocess para chamar o servidor MCP via stdio
            # 2. Implementar cliente WebSocket/SSE para FastMCP
            # 3. Ou importar diretamente as funções do servidor
            
            await asyncio.sleep(self.delay)  # Simular processamento
            
            processing_time = time.time() - start_time
            
            # Resultado simulado
            result = {
                "url": url,
                "success": True,
                "processing_time": round(processing_time, 2),
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "success": True,
                    "chunks_stored": 1,
                    "content_length": 1000,
                    "source_id": urlparse(url).netloc,
                    "note": "Resultado simulado - implementação completa requer cliente WebSocket/SSE"
                }
            }
            
            self.logger.info(f"✓ Simulado: {url} - processado em {processing_time:.1f}s")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Erro ao processar {url}: {e}")
            return {
                "url": url,
                "success": False,
                "processing_time": round(processing_time, 2),
                "timestamp": datetime.now().isoformat(),
                "error": f"Erro: {str(e)}"
            }
            
    async def process_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Processa lista de URLs sequencialmente."""
        total_urls = len(urls)
        results = []
        
        self.logger.info(f"Iniciando processamento de {total_urls} URLs")
        
        for i, url in enumerate(urls, 1):
            self.logger.info(f"Processando {i}/{total_urls}: {url}")
            
            result = await self.crawl_single_url_fallback(url)
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
            "generated_at": datetime.now().isoformat(),
            "note": "Este é um resultado de demonstração usando fallback simulado"
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
            
            # Aviso sobre limitações
            self.logger.warning("AVISO: Esta versão usa simulação de resultados")
            self.logger.info("Para implementação completa, é necessário cliente WebSocket/SSE para FastMCP")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro durante execução: {e}")
            return False


async def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="Batch crawler para servidor MCP Crawl4AI (versão MCP client)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python batch_crawler_mcp.py urls.txt
  python batch_crawler_mcp.py urls.txt --output meus_resultados.json
  python batch_crawler_mcp.py urls.txt --delay 2 --server-url http://localhost:8051

NOTA: Esta versão é uma demonstração. Para funcionalidade completa,
é necessário implementar cliente WebSocket/SSE para FastMCP.
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
    crawler = BatchCrawlerMCP(server_url=args.server_url, delay=args.delay)
    
    success = await crawler.run(args.urls_file, args.output)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())