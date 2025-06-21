#!/usr/bin/env python3
"""
Batch Crawler Fixed - Funciona com o servidor MCP via HTTP

Este script usa requests HTTP diretos para o servidor FastMCP rodando no Docker.
Não modifica o servidor, apenas usa os endpoints existentes.

Usage:
    python batch_crawler_fixed.py urls.txt
"""

import asyncio
import argparse
import json
import logging
import sys
import time
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import re

try:
    import aiofiles
    import aiohttp
except ImportError:
    print("Dependências necessárias: pip install aiohttp aiofiles")
    sys.exit(1)


class BatchCrawlerFixed:
    """Cliente que funciona com FastMCP via HTTP direto."""
    
    def __init__(self, server_url: str = "http://localhost:8051", delay: float = 1.0):
        self.server_url = server_url.rstrip('/')
        self.delay = delay
        self.session = None
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    async def __aenter__(self):
        """Context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.session:
            await self.session.close()
    
    def test_connection_sync(self) -> bool:
        """Testa conexão com servidor MCP (versão síncrona)."""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=10)
            if response.status_code == 200:
                self.logger.info(f"[OK] Servidor MCP está respondendo em {self.server_url}")
                return True
            else:
                self.logger.error(f"[ERRO] Servidor retornou status {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"[ERRO] Não foi possível conectar ao servidor: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """Testa conexão com servidor MCP."""
        try:
            async with self.session.get(f"{self.server_url}/health") as response:
                if response.status == 200:
                    self.logger.info(f"[OK] Servidor MCP está respondendo em {self.server_url}")
                    return True
                else:
                    self.logger.error(f"[ERRO] Servidor retornou status {response.status}")
                    return False
        except Exception as e:
            self.logger.error(f"[ERRO] Não foi possível conectar ao servidor: {e}")
            return False
    
    async def crawl_single_url_mcp(self, url: str) -> Dict[str, Any]:
        """
        Crawl uma URL usando o protocolo MCP via HTTP.
        
        O FastMCP usa Server-Sent Events (SSE) para comunicação.
        Vamos fazer uma requisição HTTP POST direta.
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Iniciando crawl via MCP HTTP: {url}")
            
            # Preparar payload MCP para crawl_single_page
            mcp_request = {
                "method": "tools/call",
                "params": {
                    "name": "crawl_single_page",
                    "arguments": {
                        "url": url
                    }
                }
            }
            
            # Tentar diferentes endpoints que FastMCP pode usar
            endpoints_to_try = [
                "/mcp/tools/call",
                "/tools/call", 
                "/call",
                "/mcp",
                "/sse"
            ]
            
            last_error = None
            
            for endpoint in endpoints_to_try:
                try:
                    async with self.session.post(
                        f"{self.server_url}{endpoint}",
                        json=mcp_request,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json"
                        },
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as response:
                        
                        if response.status == 200:
                            result = await response.json()
                            processing_time = time.time() - start_time
                            
                            self.logger.info(f"[OK] Crawl concluído para {url} - {processing_time:.2f}s")
                            
                            return {
                                "success": True,
                                "url": url,
                                "data": result,
                                "processing_time": processing_time,
                                "timestamp": datetime.now().isoformat(),
                                "endpoint_used": endpoint
                            }
                        elif response.status == 404:
                            # Endpoint não existe, tentar próximo
                            continue
                        else:
                            error_text = await response.text()
                            last_error = f"HTTP {response.status}: {error_text}"
                            continue
                            
                except aiohttp.ClientError:
                    # Endpoint não funciona, tentar próximo
                    continue
            
            # Se chegou aqui, nenhum endpoint funcionou
            processing_time = time.time() - start_time
            error_msg = last_error or "Nenhum endpoint MCP válido encontrado"
            
            self.logger.error(f"Falha ao crawl {url}: {error_msg}")
            
            return {
                "success": False,
                "url": url,
                "error": error_msg,
                "processing_time": processing_time,
                "timestamp": datetime.now().isoformat()
            }
                    
        except asyncio.TimeoutError:
            processing_time = time.time() - start_time
            self.logger.error(f"Timeout ao processar {url}")
            return {
                "success": False,
                "url": url,
                "error": "Timeout na requisição",
                "processing_time": processing_time,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Erro ao processar {url}: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "processing_time": processing_time,
                "timestamp": datetime.now().isoformat()
            }
    
    async def crawl_single_url_direct(self, url: str) -> Dict[str, Any]:
        """
        Método alternativo: fazer crawl direto usando requests simples.
        Se o MCP não funcionar, pelo menos tenta fazer um crawl básico.
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Tentando crawl direto (fallback): {url}")
            
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                content = await response.text()
                processing_time = time.time() - start_time
                
                return {
                    "success": True,
                    "url": url,
                    "data": {
                        "url": url,
                        "content": content[:1000] + "..." if len(content) > 1000 else content,
                        "status_code": response.status,
                        "content_type": response.headers.get("content-type", ""),
                        "method": "direct_fallback"
                    },
                    "processing_time": processing_time,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            processing_time = time.time() - start_time
            return {
                "success": False,
                "url": url,
                "error": f"Fallback direto falhou: {str(e)}",
                "processing_time": processing_time,
                "timestamp": datetime.now().isoformat()
            }
    
    def load_urls(self, file_path: str) -> List[str]:
        """Carrega URLs de um arquivo."""
        urls = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Pular linhas vazias e comentários
                    if not line or line.startswith('#'):
                        continue
                    
                    # Validar URL básica
                    if not line.startswith(('http://', 'https://')):
                        self.logger.warning(f"Linha {line_num}: URL inválida (sem protocolo): {line}")
                        continue
                    
                    try:
                        parsed = urlparse(line)
                        if not parsed.netloc:
                            self.logger.warning(f"Linha {line_num}: URL malformada: {line}")
                            continue
                        urls.append(line)
                    except Exception as e:
                        self.logger.warning(f"Linha {line_num}: Erro ao analisar URL {line}: {e}")
                        continue
                        
            self.logger.info(f"Total de URLs válidas carregadas: {len(urls)}")
            return urls
            
        except FileNotFoundError:
            self.logger.error(f"Arquivo não encontrado: {file_path}")
            return []
        except Exception as e:
            self.logger.error(f"Erro ao carregar arquivo {file_path}: {e}")
            return []
    
    async def process_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Processa lista de URLs sequencialmente."""
        results = []
        total = len(urls)
        
        for i, url in enumerate(urls, 1):
            self.logger.info(f"Processando {i}/{total}: {url}")
            
            # Tentar primeiro via MCP
            result = await self.crawl_single_url_mcp(url)
            
            # Se falhou, tentar método direto como fallback
            if not result["success"] and "endpoint" in result.get("error", ""):
                self.logger.warning(f"MCP falhou para {url}, tentando método direto...")
                result = await self.crawl_single_url_direct(url)
            
            results.append(result)
            
            # Log resultado
            if result["success"]:
                method = result.get("data", {}).get("method", "mcp")
                self.logger.info(f"[OK] {url} ({method}) - {result['processing_time']:.2f}s")
            else:
                self.logger.error(f"[ERRO] {url} - {result['error']}")
            
            # Delay entre requisições (exceto na última)
            if i < total:
                await asyncio.sleep(self.delay)
        
        return results
    
    async def run(self, urls_file: str, output_file: str) -> bool:
        """Executa o crawler batch."""
        # Carregar URLs
        self.logger.info(f"Lendo URLs de: {urls_file}")
        urls = self.load_urls(urls_file)
        
        if not urls:
            self.logger.error("Nenhuma URL válida encontrada")
            return False
        
        # Testar conexão
        if not await self.test_connection():
            self.logger.warning("Servidor MCP não acessível, usando apenas método direto")
        
        # Processar URLs
        self.logger.info(f"Iniciando processamento de {len(urls)} URLs")
        results = await self.process_urls(urls)
        
        # Salvar resultados
        try:
            async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(results, indent=2, ensure_ascii=False))
            
            # Estatísticas
            successful = sum(1 for r in results if r["success"])
            failed = len(results) - successful
            mcp_success = sum(1 for r in results if r["success"] and r.get("endpoint_used"))
            direct_success = successful - mcp_success
            
            self.logger.info("========================================")
            self.logger.info("Resultado Final:")
            self.logger.info(f"  URLs processadas: {len(results)}")
            self.logger.info(f"  Sucessos: {successful}")
            self.logger.info(f"    - Via MCP: {mcp_success}")
            self.logger.info(f"    - Direto: {direct_success}")
            self.logger.info(f"  Falhas: {failed}")
            self.logger.info(f"  Arquivo de saída: {output_file}")
            self.logger.info("========================================")
            
            return successful > 0
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar resultados: {e}")
            return False


def interactive_mode():
    """Modo interativo para configurar e executar o crawler."""
    print("=" * 40)
    print(" Batch Crawler Fixed - Modo Interativo")
    print("=" * 40)
    
    # Listar arquivos de URL disponíveis
    current_dir = Path(__file__).parent
    url_files = []
    
    for ext in ['*.txt']:
        url_files.extend(current_dir.glob(ext))
    
    if url_files:
        print("\nArquivos de URL disponíveis:\n")
        for i, file_path in enumerate(url_files, 1):
            print(f"  {i}. {file_path.name}")
        
        print(f"\nOpções:")
        print(f"  1-{len(url_files)}. Selecionar arquivo listado acima")
        print(f"  m. Digitar caminho manualmente")
        print(f"  e. Usar example_urls.txt")
        print(f"  q. Sair")
        
        while True:
            choice = input("\nEscolha uma opção: ").strip().lower()
            
            if choice == 'q':
                print("Saindo...")
                return None
            elif choice == 'e':
                urls_file = 'example_urls.txt'
                break
            elif choice == 'm':
                urls_file = input("Digite o caminho do arquivo: ").strip()
                break
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(url_files):
                    urls_file = str(url_files[idx])
                    break
                else:
                    print("Opção inválida!")
            else:
                print("Opção inválida!")
    else:
        urls_file = input("Digite o caminho do arquivo de URLs: ").strip()
    
    if urls_file:
        print(f"\n[OK] Arquivo selecionado: {Path(urls_file).name}")
    
    # Configurações opcionais
    print(f"\nConfigurações opcionais (pressione Enter para usar padrão):")
    
    output = input("Arquivo de saída [crawl_results.json]: ").strip()
    if not output:
        output = "crawl_results.json"
    
    delay_str = input("Delay entre requisições em segundos [1]: ").strip()
    delay = float(delay_str) if delay_str else 1.0
    
    server_url = input("URL do servidor MCP [http://localhost:8051]: ").strip()
    if not server_url:
        server_url = "http://localhost:8051"
    
    # Confirmação
    print("\n" + "=" * 40)
    print(" Configuração Final")
    print("=" * 40)
    print(f"\n  Arquivo URLs: {Path(urls_file).name}")
    print(f"  Arquivo saída: {output}")
    print(f"  Delay: {delay} segundos")
    print(f"  Servidor: {server_url}")
    
    confirm = input(f"\nConfirmar e iniciar? [S/n]: ").strip().lower()
    if confirm in ['', 's', 'sim', 'y', 'yes']:
        return {
            'urls_file': urls_file,
            'output': output,
            'delay': delay,
            'server_url': server_url
        }
    else:
        print("Operação cancelada.")
        return None


async def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="Batch Crawler Fixed para MCP Crawl4AI RAG Server"
    )
    parser.add_argument("urls_file", nargs="?", help="Arquivo contendo URLs para crawl")
    parser.add_argument("-o", "--output", default="crawl_results.json", 
                       help="Arquivo de saída JSON")
    parser.add_argument("-d", "--delay", type=float, default=1.0,
                       help="Delay entre requisições em segundos")
    parser.add_argument("-s", "--server", default="http://localhost:8051",
                       help="URL do servidor MCP")
    parser.add_argument("-i", "--interactive", action="store_true",
                       help="Modo interativo")
    
    args = parser.parse_args()
    
    # Modo interativo se não há argumentos ou flag -i
    if args.interactive or not args.urls_file:
        config = interactive_mode()
        if not config:
            return
        
        args.urls_file = config['urls_file']
        args.output = config['output']
        args.delay = config['delay']
        args.server = config['server_url']
    
    if not args.urls_file:
        print("Erro: arquivo de URLs não especificado")
        return
    
    print(f"\nIniciando crawling...")
    print("=" * 40)
    
    # Executar crawler
    async with BatchCrawlerFixed(args.server, args.delay) as crawler:
        success = await crawler.run(args.urls_file, args.output)
        
        if success:
            print("\n✅ Crawling concluído com sucesso!")
        else:
            print("\n❌ Crawling falhou ou foi cancelado")
            sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        sys.exit(1)