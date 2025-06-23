#!/usr/bin/env python3
"""
Cliente de exemplo para Qwen3-Embedding API
Demonstra como usar a API compatível com OpenAI
"""

import openai
import numpy as np
import time
import json
from typing import List, Optional
import argparse
import sys


class Qwen3EmbeddingClient:
    """Cliente para API Qwen3-Embedding"""
    
    def __init__(self, base_url: str = "http://localhost:8000/v1", api_key: str = "EMPTY"):
        """
        Inicializar cliente
        
        Args:
            base_url: URL base da API
            api_key: Chave da API (EMPTY para vLLM)
        """
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.base_url = base_url
        
    def get_models(self) -> List[str]:
        """Listar modelos disponíveis"""
        try:
            models = self.client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            print(f"Erro ao listar modelos: {e}")
            return []
    
    def embed_text(
        self, 
        text: str, 
        model: str = "Qwen/Qwen3-Embedding-0.6B",
        dimensions: Optional[int] = None
    ) -> List[float]:
        """
        Gerar embedding para um texto
        
        Args:
            text: Texto para embedding
            model: Nome do modelo
            dimensions: Dimensões customizadas (opcional)
            
        Returns:
            Lista de floats representando o embedding
        """
        try:
            kwargs = {
                "model": model,
                "input": [text],
                "encoding_format": "float"
            }
            
            if dimensions:
                kwargs["dimensions"] = dimensions
                
            response = self.client.embeddings.create(**kwargs)
            return response.data[0].embedding
            
        except Exception as e:
            print(f"Erro ao gerar embedding: {e}")
            return []
    
    def embed_batch(
        self, 
        texts: List[str], 
        model: str = "Qwen/Qwen3-Embedding-0.6B",
        dimensions: Optional[int] = None
    ) -> List[List[float]]:
        """
        Gerar embeddings para múltiplos textos
        
        Args:
            texts: Lista de textos
            model: Nome do modelo
            dimensions: Dimensões customizadas (opcional)
            
        Returns:
            Lista de embeddings
        """
        try:
            kwargs = {
                "model": model,
                "input": texts,
                "encoding_format": "float"
            }
            
            if dimensions:
                kwargs["dimensions"] = dimensions
                
            response = self.client.embeddings.create(**kwargs)
            return [item.embedding for item in response.data]
            
        except Exception as e:
            print(f"Erro ao gerar embeddings em lote: {e}")
            return []
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calcular similaridade coseno entre dois embeddings
        
        Args:
            embedding1: Primeiro embedding
            embedding2: Segundo embedding
            
        Returns:
            Similaridade coseno (-1 a 1)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Normalizar vetores
        vec1_norm = vec1 / np.linalg.norm(vec1)
        vec2_norm = vec2 / np.linalg.norm(vec2)
        
        # Calcular similaridade coseno
        similarity = np.dot(vec1_norm, vec2_norm)
        return float(similarity)
    
    def benchmark_dimensions(self, text: str = "Teste de benchmark", model: str = "Qwen/Qwen3-Embedding-0.6B"):
        """Fazer benchmark de diferentes dimensões"""
        dimensions = [128, 256, 512, 768, 1024]
        
        print(f"🔬 Benchmark de dimensões para: '{text}'")
        print("-" * 60)
        
        for dim in dimensions:
            start_time = time.time()
            embedding = self.embed_text(text, model, dimensions=dim)
            end_time = time.time()
            
            if embedding:
                duration = end_time - start_time
                print(f"Dimensão {dim:4d}: {duration:.3f}s - Tamanho: {len(embedding)}")
            else:
                print(f"Dimensão {dim:4d}: ERRO")
    
    def semantic_search_demo(self):
        """Demonstração de busca semântica"""
        # Documentos de exemplo
        documents = [
            "O gato subiu no telhado da casa",
            "Python é uma linguagem de programação",
            "Machine learning é uma área da inteligência artificial",
            "O cachorro correu pelo jardim",
            "Deep learning usa redes neurais artificiais",
            "JavaScript é usado para desenvolvimento web"
        ]
        
        # Query de busca
        query = "inteligência artificial e programação"
        
        print(f"🔍 Busca semântica para: '{query}'")
        print("-" * 60)
        
        # Gerar embeddings
        print("Gerando embeddings...")
        query_embedding = self.embed_text(query)
        doc_embeddings = self.embed_batch(documents)
        
        if not query_embedding or not doc_embeddings:
            print("Erro ao gerar embeddings!")
            return
        
        # Calcular similaridades
        similarities = []
        for i, doc_embedding in enumerate(doc_embeddings):
            similarity = self.calculate_similarity(query_embedding, doc_embedding)
            similarities.append((i, similarity, documents[i]))
        
        # Ordenar por similaridade
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Mostrar resultados
        print("\nResultados (ordenados por relevância):")
        for rank, (doc_idx, similarity, document) in enumerate(similarities, 1):
            print(f"{rank}. [{similarity:.3f}] {document}")


def main():
    parser = argparse.ArgumentParser(description="Cliente Qwen3-Embedding")
    parser.add_argument("--url", default="http://localhost:8000/v1", help="URL da API")
    parser.add_argument("--model", default="Qwen/Qwen3-Embedding-0.6B", help="Nome do modelo")
    parser.add_argument("--text", help="Texto para embedding")
    parser.add_argument("--dimensions", type=int, help="Dimensões customizadas")
    parser.add_argument("--benchmark", action="store_true", help="Executar benchmark")
    parser.add_argument("--demo", action="store_true", help="Executar demo de busca semântica")
    parser.add_argument("--models", action="store_true", help="Listar modelos disponíveis")
    
    args = parser.parse_args()
    
    # Criar cliente
    client = Qwen3EmbeddingClient(base_url=args.url)
    
    try:
        # Listar modelos
        if args.models:
            print("📋 Modelos disponíveis:")
            models = client.get_models()
            for model in models:
                print(f"  - {model}")
            return
        
        # Benchmark
        if args.benchmark:
            client.benchmark_dimensions(model=args.model)
            return
        
        # Demo de busca semântica
        if args.demo:
            client.semantic_search_demo()
            return
        
        # Embedding de texto específico
        if args.text:
            print(f"📝 Gerando embedding para: '{args.text}'")
            
            start_time = time.time()
            embedding = client.embed_text(args.text, args.model, args.dimensions)
            end_time = time.time()
            
            if embedding:
                print(f"✅ Embedding gerado em {end_time - start_time:.3f}s")
                print(f"   Dimensões: {len(embedding)}")
                print(f"   Primeiros 10 valores: {embedding[:10]}")
                
                # Salvar em arquivo se solicitado
                output_file = f"embedding_{int(time.time())}.json"
                with open(output_file, 'w') as f:
                    json.dump({
                        "text": args.text,
                        "model": args.model,
                        "dimensions": len(embedding),
                        "embedding": embedding,
                        "timestamp": time.time()
                    }, f, indent=2)
                print(f"   Salvo em: {output_file}")
            else:
                print("❌ Erro ao gerar embedding")
                sys.exit(1)
            return
        
        # Se nenhuma ação específica, mostrar menu interativo
        print("🤖 Cliente Qwen3-Embedding Interativo")
        print("=" * 50)
        
        while True:
            print("\nOpções:")
            print("1. Gerar embedding de texto")
            print("2. Busca semântica (demo)")
            print("3. Benchmark de dimensões")
            print("4. Listar modelos")
            print("5. Sair")
            
            choice = input("\nEscolha uma opção (1-5): ").strip()
            
            if choice == "1":
                text = input("Digite o texto: ").strip()
                if text:
                    dims = input("Dimensões (Enter para padrão): ").strip()
                    dimensions = int(dims) if dims.isdigit() else None
                    
                    embedding = client.embed_text(text, args.model, dimensions)
                    if embedding:
                        print(f"✅ Embedding: {len(embedding)} dimensões")
                        print(f"   Amostra: {embedding[:5]}...")
                    else:
                        print("❌ Erro ao gerar embedding")
            
            elif choice == "2":
                client.semantic_search_demo()
            
            elif choice == "3":
                text = input("Texto para benchmark (Enter para padrão): ").strip()
                if not text:
                    text = "Teste de benchmark"
                client.benchmark_dimensions(text, args.model)
            
            elif choice == "4":
                models = client.get_models()
                print("📋 Modelos:")
                for model in models:
                    print(f"  - {model}")
            
            elif choice == "5":
                print("👋 Até logo!")
                break
            
            else:
                print("❌ Opção inválida!")
                
    except KeyboardInterrupt:
        print("\n👋 Interrompido pelo usuário")
    except Exception as e:
        print(f"❌ Erro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 