#!/usr/bin/env python3
"""
Script de teste para verificar comunicação com servidor MCP.
"""

import asyncio
import httpx
import json


async def test_mcp_connection():
    """Testa diferentes formas de conectar com o servidor MCP."""
    
    server_url = "http://localhost:8051"
    
    print("=== Teste de Conexão MCP ===")
    print(f"Servidor: {server_url}")
    print()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        
        # Teste 1: GET simples (deve retornar 404 - normal)
        print("1. Testando GET simples...")
        try:
            response = await client.get(server_url)
            print(f"   Status: {response.status_code}")
            if response.status_code == 404:
                print("   ✓ Servidor está rodando (404 é esperado)")
            elif response.status_code == 200:
                print("   ✓ Servidor respondeu com sucesso")
            else:
                print(f"   ? Status inesperado: {response.status_code}")
        except Exception as e:
            print(f"   ✗ Erro: {e}")
            return
        
        print()
        
        # Teste 2: Tentar diferentes endpoints e métodos
        print("2. Testando endpoints FastMCP...")
        
        endpoints_to_test = [
            ("GET", "/sse"),
            ("POST", "/message"),
            ("POST", "/rpc"), 
            ("POST", "/"),
            ("POST", "/mcp"),
            ("GET", "/health"),
            ("GET", "/docs"),
            ("GET", "/openapi.json")
        ]
        
        for method, endpoint in endpoints_to_test:
            try:
                print(f"   Testando {method} {endpoint}...")
                if method == "GET":
                    response = await client.get(f"{server_url}{endpoint}")
                else:
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/list",
                        "params": {}
                    }
                    response = await client.post(
                        f"{server_url}{endpoint}",
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )
                
                print(f"     Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"     ✓ Sucesso! Endpoint funcional: {method} {endpoint}")
                    try:
                        result = response.json()
                        print(f"     Resposta: {result}")
                        return  # Parar no primeiro sucesso
                    except:
                        print(f"     Resposta texto: {response.text[:100]}...")
                elif response.status_code in [404, 405]:
                    print(f"     - Não disponível")
                else:
                    print(f"     ? Status: {response.status_code}")
                    
            except Exception as e:
                print(f"     ✗ Erro: {e}")
        
        print("   Nenhum endpoint MCP funcional encontrado")
        
        print()
        print("=== Conclusão ===")
        print("O servidor FastMCP está rodando mas não encontrou endpoint HTTP funcional.")
        print("Isso pode ser normal se o servidor usar apenas WebSocket/SSE nativo.")
        print("Você pode precisar usar a biblioteca MCP oficial para comunicação.")


if __name__ == "__main__":
    asyncio.run(test_mcp_connection())