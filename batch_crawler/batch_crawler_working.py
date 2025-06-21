#!/usr/bin/env python3
"""
Batch Crawler Script que REALMENTE funciona com MCP Crawl4AI RAG Server

Este script usa subprocess para comunicar com o servidor MCP via stdio,
contornando as limitações do FastMCP SSE.

Usage:
    python batch_crawler_working.py urls.txt
"""

import asyncio
import argparse
import json
import logging
import sys
import time
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import re

import aiofiles


class BatchCrawlerWorking:
    """Cliente que funciona de verdade usando subprocess + stdio."""
    
    def __init__(self, delay: float = 1.0, server_script: str = None):
        self.delay = delay
        self.server_script = server_script or "../src/crawl4ai_mcp.py"
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
            
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
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
                if url and not url.startswith('#'):
                    if self.validate_url(url):
                        urls.append(url)
                    else:
                        self.logger.warning(f"URL inválida ignorada: {url}")
                        
        self.logger.info(f"Total de URLs válidas carregadas: {len(urls)}")
        return urls
        
    def check_server_script(self) -> bool:
        """Verifica se o script do servidor existe."""
        script_path = Path(self.server_script)
        if script_path.exists():
            self.logger.info(f"Script do servidor encontrado: {script_path.absolute()}")
            return True
        else:
            self.logger.error(f"Script do servidor não encontrado: {script_path.absolute()}")
            return False
            
    async def crawl_single_url_stdio(self, url: str) -> Dict[str, Any]:
        """Crawl uma URL usando subprocess com stdio MCP."""
        start_time = time.time()
        
        try:
            self.logger.info(f"Iniciando crawl via stdio: {url}")
            
            # Preparar mensagem MCP JSON-RPC 2.0
            request = {
                "jsonrpc": "2.0",
                "id": int(time.time() * 1000),
                "method": "tools/call",
                "params": {
                    "name": "crawl_single_page", 
                    "arguments": {
                        "url": url
                    }
                }
            }
            
            # Executar servidor MCP via subprocess com stdio
            env = os.environ.copy()
            env["TRANSPORT"] = "stdio"  # Forçar modo stdio
            
            process = await asyncio.create_subprocess_exec(
                sys.executable, self.server_script,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Enviar requisição JSON-RPC
            request_json = json.dumps(request) + "\n"
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=request_json.encode('utf-8')),
                    timeout=120.0  # 2 minutos timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise Exception("Timeout na comunicação com servidor MCP")
            
            processing_time = time.time() - start_time
            
            if process.returncode == 0:
                # Parse da resposta
                try:
                    response_text = stdout.decode('utf-8').strip()
                    if response_text:
                        # Pode haver múltiplas linhas JSON, pegar a última válida
                        lines = response_text.split('\n')
                        response = None
                        for line in reversed(lines):
                            line = line.strip()
                            if line and line.startswith('{'):
                                try:
                                    response = json.loads(line)
                                    break
                                except json.JSONDecodeError:
                                    continue
                        
                        if response and "result" in response:
                            # Extrair resultado da ferramenta
                            tool_result = response["result"].get("content", "")
                            if isinstance(tool_result, str):
                                try:
                                    crawl_result = json.loads(tool_result)
                                    success = crawl_result.get("success", False)
                                    
                                    result = {
                                        "url": url,
                                        "success": success,
                                        "processing_time": round(processing_time, 2),
                                        "timestamp": datetime.now().isoformat(),
                                        "data": crawl_result
                                    }
                                    
                                    if success:
                                        chunks = crawl_result.get("chunks_stored", 0)
                                        content_len = crawl_result.get("content_length", 0)
                                        self.logger.info(f"✓ Sucesso: {url} - {chunks} chunks, {content_len} chars")
                                    else:
                                        error_msg = crawl_result.get("error", "Erro desconhecido")
                                        self.logger.error(f"✗ Falha: {url} - {error_msg}")
                                        
                                    return result
                                    
                                except json.JSONDecodeError as e:
                                    self.logger.error(f"Erro ao parse resultado para {url}: {e}")
                            else:
                                self.logger.error(f"Resultado não é string para {url}")
                        else:
                            self.logger.error(f"Resposta MCP inválida para {url}: {response}")
                    else:
                        self.logger.error(f"Resposta vazia do servidor para {url}")
                        
                except Exception as e:
                    self.logger.error(f"Erro ao processar resposta para {url}: {e}")
                    
            else:
                stderr_text = stderr.decode('utf-8')
                self.logger.error(f"Servidor retornou erro para {url}: {stderr_text}")
                
            # Se chegou até aqui, houve erro
            return {
                "url": url,
                "success": False,
                "processing_time": round(processing_time, 2),
                "timestamp": datetime.now().isoformat(),
                "error": "Erro na comunicação com servidor MCP"
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Erro geral ao processar {url}: {e}")
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
        
        self.logger.info(f"Iniciando processamento de {total_urls} URLs via stdio")
        
        for i, url in enumerate(urls, 1):
            self.logger.info(f"Processando {i}/{total_urls}: {url}")
            
            result = await self.crawl_single_url_stdio(url)
            results.append(result)
            
            # Delay entre requisições (exceto na última)
            if i < total_urls:
                self.logger.debug(f"Aguardando {self.delay}s...")
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
        """Executa o processo completo."""
        try:
            # Verificar se script do servidor existe
            if not self.check_server_script():
                return False
                
            # Ler URLs
            urls = await self.read_urls(urls_file)
            if not urls:
                self.logger.error("Nenhuma URL válida encontrada")
                return False
                
            # Processar URLs
            results = await self.process_urls(urls)
            
            # Salvar resultados
            await self.save_results(results, output_file)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro durante execução: {e}")
            return False


async def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description="Batch crawler MCP que FUNCIONA via stdio")
    parser.add_argument("urls_file", help="Arquivo com URLs")
    parser.add_argument("--output", "-o", default="crawl_results.json", help="Arquivo de saída")
    parser.add_argument("--delay", "-d", type=float, default=2.0, help="Delay entre URLs")
    parser.add_argument("--server-script", "-s", help="Caminho para crawl4ai_mcp.py")
    
    args = parser.parse_args()
    
    if not Path(args.urls_file).exists():
        print(f"Erro: Arquivo '{args.urls_file}' não encontrado.")
        sys.exit(1)
        
    crawler = BatchCrawlerWorking(delay=args.delay, server_script=args.server_script)
    success = await crawler.run(args.urls_file, args.output)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    import os
    asyncio.run(main())