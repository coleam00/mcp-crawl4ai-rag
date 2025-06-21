#!/usr/bin/env python3
"""
Batch Crawler Working Fixed - Usa stdio MCP corretamente

Este script usa o método que REALMENTE funciona: subprocess + stdio + JSON-RPC 2.0
Não tenta usar HTTP REST que não existe no FastMCP.
"""

import asyncio
import json
import logging
import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse


class BatchCrawlerWorkingFixed:
    """Cliente que funciona usando subprocess + stdio + JSON-RPC."""
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.server_script = None
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
        # Encontrar o script do servidor MCP
        self._find_server_script()
    
    def _find_server_script(self):
        """Encontra o script do servidor MCP."""
        current_dir = Path(__file__).parent
        possible_paths = [
            current_dir / ".." / "src" / "crawl4ai_mcp.py",
            current_dir.parent / "src" / "crawl4ai_mcp.py",
            Path("../src/crawl4ai_mcp.py"),
            Path("src/crawl4ai_mcp.py"),
            Path("crawl4ai_mcp.py")
        ]
        
        for path in possible_paths:
            if path.exists():
                self.server_script = str(path.resolve())
                self.logger.info(f"Servidor MCP encontrado: {self.server_script}")
                return
        
        self.logger.error("Script do servidor MCP não encontrado!")
        self.server_script = None
    
    def test_connection(self) -> bool:
        """Testa se podemos executar o servidor MCP."""
        if not self.server_script:
            self.logger.error("Script do servidor não encontrado")
            return False
        
        try:
            # Testar se podemos executar o script
            import subprocess
            result = subprocess.run([
                sys.executable, self.server_script, "--help"
            ], capture_output=True, timeout=10, env={**os.environ, "TRANSPORT": "stdio"})
            
            # Se não der erro de import, é bom sinal
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao testar servidor: {e}")
            return False
    
    async def crawl_single_url_stdio(self, url: str) -> Dict[str, Any]:
        """Crawl uma URL usando subprocess com stdio MCP."""
        start_time = time.time()
        
        try:
            self.logger.info(f"Iniciando crawl via stdio: {url}")
            
            # Preparar mensagem JSON-RPC 2.0 
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
            
            # Ambiente para forçar modo stdio
            env = os.environ.copy()
            env["TRANSPORT"] = "stdio"
            
            # Executar servidor MCP via subprocess com stdio
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
                    timeout=180.0  # 3 minutos timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise Exception("Timeout na comunicação com servidor MCP")
            
            processing_time = time.time() - start_time
            
            if process.returncode == 0:
                # Parse da resposta JSON-RPC
                try:
                    response_text = stdout.decode('utf-8').strip()
                    
                    # Às vezes o FastMCP retorna múltiplas linhas, pegar a última válida
                    lines = response_text.split('\n')
                    response_data = None
                    
                    for line in reversed(lines):
                        if line.strip():
                            try:
                                response_data = json.loads(line.strip())
                                break
                            except json.JSONDecodeError:
                                continue
                    
                    if not response_data:
                        raise Exception("Resposta JSON inválida")
                    
                    # Verificar se é uma resposta de erro JSON-RPC
                    if "error" in response_data:
                        error_msg = response_data["error"].get("message", "Erro desconhecido")
                        raise Exception(f"Erro MCP: {error_msg}")
                    
                    # Extrair resultado da resposta JSON-RPC
                    result_data = response_data.get("result")
                    if not result_data:
                        raise Exception("Resposta MCP sem campo 'result'")
                    
                    self.logger.info(f"Crawl concluído para {url} - {processing_time:.2f}s")
                    
                    return {
                        "success": True,
                        "url": url,
                        "data": result_data,
                        "processing_time": processing_time,
                        "timestamp": datetime.now().isoformat(),
                        "method": "stdio-mcp"
                    }
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Erro ao decodificar JSON para {url}: {e}")
                    self.logger.error(f"Resposta recebida: {stdout.decode('utf-8')[:500]}")
                    raise Exception(f"Resposta JSON inválida: {e}")
                    
            else:
                # Processo falhou
                error_output = stderr.decode('utf-8')
                self.logger.error(f"Processo falhou para {url}: {error_output}")
                raise Exception(f"Processo retornou código {process.returncode}: {error_output}")
                
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
                        self.logger.warning(f"Linha {line_num}: URL inválida: {line}")
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
            
            result = await self.crawl_single_url_stdio(url)
            results.append(result)
            
            # Log resultado
            if result["success"]:
                self.logger.info(f"[OK] {url} - {result['processing_time']:.2f}s")
            else:
                self.logger.error(f"[ERRO] {url} - {result['error']}")
            
            # Delay entre requisições (exceto na última)
            if i < total and self.delay > 0:
                await asyncio.sleep(self.delay)
        
        return results
    
    async def run(self, urls_file: str, output_file: str) -> bool:
        """Executa o crawler batch."""
        # Testar se podemos executar o servidor
        if not self.test_connection():
            self.logger.error("Não é possível executar o servidor MCP")
            return False
        
        # Carregar URLs
        self.logger.info(f"Lendo URLs de: {urls_file}")
        urls = self.load_urls(urls_file)
        
        if not urls:
            self.logger.error("Nenhuma URL válida encontrada")
            return False
        
        # Processar URLs
        self.logger.info(f"Iniciando processamento de {len(urls)} URLs via stdio")
        results = await self.process_urls(urls)
        
        # Salvar resultados
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            # Estatísticas
            successful = sum(1 for r in results if r["success"])
            failed = len(results) - successful
            
            self.logger.info("========================================")
            self.logger.info("Resultado Final:")
            self.logger.info(f"  URLs processadas: {len(results)}")
            self.logger.info(f"  Sucessos: {successful}")
            self.logger.info(f"  Falhas: {failed}")
            self.logger.info(f"  Arquivo de saída: {output_file}")
            self.logger.info("========================================")
            
            return successful > 0
            
        except Exception as e:
            self.logger.error(f"Erro ao salvar resultados: {e}")
            return False


def interactive_mode():
    """Modo interativo."""
    print("=" * 50)
    print(" Batch Crawler Working Fixed - MCP stdio")
    print("=" * 50)
    
    # Listar arquivos de URL disponíveis
    current_dir = Path(__file__).parent
    url_files = list(current_dir.glob("*.txt"))
    
    if url_files:
        print("\nArquivos de URL disponíveis:\n")
        for i, file_path in enumerate(url_files, 1):
            print(f"  {i}. {file_path.name}")
        
        print(f"\nOpções:")
        print(f"  1-{len(url_files)}. Selecionar arquivo listado")
        print(f"  m. Digitar caminho manualmente")
        print(f"  q. Sair")
        
        while True:
            choice = input("\nEscolha uma opção: ").strip().lower()
            
            if choice == 'q':
                return None
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
    
    # Configurações
    output = input("Arquivo de saída [results.json]: ").strip() or "results.json"
    delay_str = input("Delay entre requisições [1.0]: ").strip()
    delay = float(delay_str) if delay_str else 1.0
    
    return {
        'urls_file': urls_file,
        'output': output,
        'delay': delay
    }


async def main():
    """Função principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch Crawler Working Fixed")
    parser.add_argument("urls_file", nargs="?", help="Arquivo com URLs")
    parser.add_argument("-o", "--output", default="results.json", help="Arquivo de saída")
    parser.add_argument("-d", "--delay", type=float, default=1.0, help="Delay entre requests")
    parser.add_argument("-i", "--interactive", action="store_true", help="Modo interativo")
    
    args = parser.parse_args()
    
    # Modo interativo se necessário
    if args.interactive or not args.urls_file:
        config = interactive_mode()
        if not config:
            return
        
        args.urls_file = config['urls_file']
        args.output = config['output']
        args.delay = config['delay']
    
    if not args.urls_file:
        print("Erro: arquivo de URLs não especificado")
        return
    
    print(f"\n🚀 Iniciando crawling...")
    print("=" * 50)
    
    # Executar crawler
    crawler = BatchCrawlerWorkingFixed(args.delay)
    success = await crawler.run(args.urls_file, args.output)
    
    if success:
        print("\n✅ Crawling concluído com sucesso!")
    else:
        print("\n❌ Crawling falhou")
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