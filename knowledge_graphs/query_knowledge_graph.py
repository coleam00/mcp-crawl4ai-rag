#!/usr/bin/env python3
"""
Knowledge Graph Query Tool

Interactive script to explore what's actually stored in your Neo4j knowledge graph.
Useful for debugging hallucination detection and understanding graph contents.
"""

import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any
import argparse


class KnowledgeGraphQuerier:
    """Interactive tool to query the knowledge graph"""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None
    
    async def initialize(self):
        """Initialize Neo4j connection"""
        self.driver = AsyncGraphDatabase.driver(
            self.neo4j_uri, 
            auth=(self.neo4j_user, self.neo4j_password)
        )
        print("🔗 Connected to Neo4j knowledge graph")
    
    async def close(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()
    
    async def list_repositories(self):
        """List all repositories in the knowledge graph"""
        print("\n📚 Repositories in Knowledge Graph:")
        print("=" * 50)
        
        async with self.driver.session() as session:
            query = "MATCH (r:Repository) RETURN r.name as name ORDER BY r.name"
            result = await session.run(query)
            
            repos = []
            async for record in result:
                repos.append(record['name'])
            
            if repos:
                for i, repo in enumerate(repos, 1):
                    print(f"{i}. {repo}")
            else:
                print("No repositories found in knowledge graph.")
        
        return repos
    
    async def explore_repository(self, repo_name: str):
        """Get overview of a specific repository"""
        print(f"\n🔍 Exploring Repository: {repo_name}")
        print("=" * 60)
        
        async with self.driver.session() as session:
            # Get file count
            files_query = """
            MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)
            RETURN count(f) as file_count
            """
            result = await session.run(files_query, repo_name=repo_name)
            file_count = (await result.single())['file_count']
            
            # Get class count
            classes_query = """
            MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)
            RETURN count(DISTINCT c) as class_count
            """
            result = await session.run(classes_query, repo_name=repo_name)
            class_count = (await result.single())['class_count']
            
            # Get function count
            functions_query = """
            MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(func:Function)
            RETURN count(DISTINCT func) as function_count
            """
            result = await session.run(functions_query, repo_name=repo_name)
            function_count = (await result.single())['function_count']
            
            print(f"📄 Files: {file_count}")
            print(f"🏗️  Classes: {class_count}")
            print(f"⚙️  Functions: {function_count}")
    
    async def list_classes(self, repo_name: str = None, limit: int = 20):
        """List classes in the knowledge graph"""
        title = f"Classes in {repo_name}" if repo_name else "All Classes"
        print(f"\n🏗️  {title} (limit {limit}):")
        print("=" * 50)
        
        async with self.driver.session() as session:
            if repo_name:
                query = """
                MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)
                RETURN c.name as name, c.full_name as full_name
                ORDER BY c.name
                LIMIT $limit
                """
                result = await session.run(query, repo_name=repo_name, limit=limit)
            else:
                query = """
                MATCH (c:Class)
                RETURN c.name as name, c.full_name as full_name
                ORDER BY c.name
                LIMIT $limit
                """
                result = await session.run(query, limit=limit)
            
            classes = []
            async for record in result:
                classes.append({
                    'name': record['name'],
                    'full_name': record['full_name']
                })
            
            if classes:
                for i, cls in enumerate(classes, 1):
                    print(f"{i:2d}. {cls['name']} ({cls['full_name']})")
            else:
                print("No classes found.")
        
        return classes
    
    async def explore_class(self, class_name: str):
        """Get detailed information about a specific class"""
        print(f"\n🔍 Exploring Class: {class_name}")
        print("=" * 60)
        
        async with self.driver.session() as session:
            # Find the class
            class_query = """
            MATCH (c:Class)
            WHERE c.name = $class_name OR c.full_name = $class_name
            RETURN c.name as name, c.full_name as full_name
            LIMIT 1
            """
            result = await session.run(class_query, class_name=class_name)
            class_record = await result.single()
            
            if not class_record:
                print(f"❌ Class '{class_name}' not found in knowledge graph.")
                return None
            
            actual_name = class_record['name']
            full_name = class_record['full_name']
            
            print(f"📋 Name: {actual_name}")
            print(f"📋 Full Name: {full_name}")
            
            # Get methods
            methods_query = """
            MATCH (c:Class)-[:HAS_METHOD]->(m:Method)
            WHERE c.name = $class_name OR c.full_name = $class_name
            RETURN m.name as name, m.params_list as params_list, m.params_detailed as params_detailed, m.return_type as return_type
            ORDER BY m.name
            """
            result = await session.run(methods_query, class_name=class_name)
            
            methods = []
            async for record in result:
                methods.append({
                    'name': record['name'],
                    'params_list': record['params_list'] or [],
                    'params_detailed': record['params_detailed'] or [],
                    'return_type': record['return_type'] or 'Any'
                })
            
            if methods:
                print(f"\n⚙️  Methods ({len(methods)}):")
                for i, method in enumerate(methods, 1):
                    # Use detailed params if available, fall back to simple params
                    params_to_show = method['params_detailed'] or method['params_list']
                    params = ', '.join(params_to_show) if params_to_show else ''
                    print(f"{i:2d}. {method['name']}({params}) -> {method['return_type']}")
            else:
                print("\n⚙️  No methods found.")
            
            # Get attributes
            attributes_query = """
            MATCH (c:Class)-[:HAS_ATTRIBUTE]->(a:Attribute)
            WHERE c.name = $class_name OR c.full_name = $class_name
            RETURN a.name as name, a.type as type
            ORDER BY a.name
            """
            result = await session.run(attributes_query, class_name=class_name)
            
            attributes = []
            async for record in result:
                attributes.append({
                    'name': record['name'],
                    'type': record['type'] or 'Any'
                })
            
            if attributes:
                print(f"\n📋 Attributes ({len(attributes)}):")
                for i, attr in enumerate(attributes, 1):
                    print(f"{i:2d}. {attr['name']}: {attr['type']}")
            else:
                print("\n📋 No attributes found.")
        
        return {'methods': methods, 'attributes': attributes}
    
    async def search_method(self, method_name: str, class_name: str = None):
        """Search for methods by name"""
        title = f"Method '{method_name}'"
        if class_name:
            title += f" in class '{class_name}'"
        
        print(f"\n🔍 Searching for {title}:")
        print("=" * 60)
        
        async with self.driver.session() as session:
            if class_name:
                query = """
                MATCH (c:Class)-[:HAS_METHOD]->(m:Method)
                WHERE (c.name = $class_name OR c.full_name = $class_name)
                  AND m.name = $method_name
                RETURN c.name as class_name, c.full_name as class_full_name,
                       m.name as method_name, m.params_list as params_list, 
                       m.return_type as return_type, m.args as args
                """
                result = await session.run(query, class_name=class_name, method_name=method_name)
            else:
                query = """
                MATCH (c:Class)-[:HAS_METHOD]->(m:Method)
                WHERE m.name = $method_name
                RETURN c.name as class_name, c.full_name as class_full_name,
                       m.name as method_name, m.params_list as params_list, 
                       m.return_type as return_type, m.args as args
                ORDER BY c.name
                """
                result = await session.run(query, method_name=method_name)
            
            methods = []
            async for record in result:
                methods.append({
                    'class_name': record['class_name'],
                    'class_full_name': record['class_full_name'],
                    'method_name': record['method_name'],
                    'params_list': record['params_list'] or [],
                    'return_type': record['return_type'] or 'Any',
                    'args': record['args'] or []
                })
            
            if methods:
                for i, method in enumerate(methods, 1):
                    params = ', '.join(method['params_list']) if method['params_list'] else ''
                    print(f"{i}. {method['class_full_name']}.{method['method_name']}({params}) -> {method['return_type']}")
                    if method['args']:
                        print(f"   Legacy args: {method['args']}")
            else:
                print(f"❌ Method '{method_name}' not found.")
        
        return methods
    
    async def run_custom_query(self, query: str):
        """Run a custom Cypher query"""
        print(f"\n🔍 Running Custom Query:")
        print("=" * 60)
        print(f"Query: {query}")
        print("-" * 60)
        
        async with self.driver.session() as session:
            try:
                result = await session.run(query)
                
                records = []
                async for record in result:
                    records.append(dict(record))
                
                if records:
                    for i, record in enumerate(records, 1):
                        print(f"{i:2d}. {record}")
                        if i >= 20:  # Limit output
                            print(f"... and {len(records) - 20} more records")
                            break
                else:
                    print("No results found.")
                
                return records
                
            except Exception as e:
                print(f"❌ Query error: {str(e)}")
                return None


async def interactive_mode(querier: KnowledgeGraphQuerier):
    """Interactive exploration mode"""
    print("\n🚀 Welcome to Knowledge Graph Explorer!")
    print("Available commands:")
    print("  repos          - List all repositories")
    print("  explore <repo> - Explore a specific repository") 
    print("  classes [repo] - List classes (optionally in specific repo)")
    print("  class <name>   - Explore a specific class")
    print("  method <name> [class] - Search for method")
    print("  query <cypher> - Run custom Cypher query")
    print("  quit           - Exit")
    print()
    
    while True:
        try:
            command = input("🔍 > ").strip()
            
            if not command:
                continue
            elif command == "quit":
                break
            elif command == "repos":
                await querier.list_repositories()
            elif command.startswith("explore "):
                repo_name = command[8:].strip()
                await querier.explore_repository(repo_name)
            elif command == "classes":
                await querier.list_classes()
            elif command.startswith("classes "):
                repo_name = command[8:].strip()
                await querier.list_classes(repo_name)
            elif command.startswith("class "):
                class_name = command[6:].strip()
                await querier.explore_class(class_name)
            elif command.startswith("method "):
                parts = command[7:].strip().split()
                if len(parts) >= 2:
                    await querier.search_method(parts[0], parts[1])
                else:
                    await querier.search_method(parts[0])
            elif command.startswith("query "):
                query = command[6:].strip()
                await querier.run_custom_query(query)
            else:
                print("❌ Unknown command. Type 'quit' to exit.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {str(e)}")


async def main():
    """Main function with CLI argument support"""
    parser = argparse.ArgumentParser(description="Query the knowledge graph")
    parser.add_argument('--repos', action='store_true', help='List repositories')
    parser.add_argument('--classes', metavar='REPO', nargs='?', const='', help='List classes')
    parser.add_argument('--explore', metavar='REPO', help='Explore repository')
    parser.add_argument('--class', dest='class_name', metavar='NAME', help='Explore class')
    parser.add_argument('--method', nargs='+', metavar=('NAME', 'CLASS'), help='Search method')
    parser.add_argument('--query', metavar='CYPHER', help='Run custom query')
    parser.add_argument('--interactive', action='store_true', help='Interactive mode')
    
    args = parser.parse_args()
    
    # Load environment
    load_dotenv()
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    
    querier = KnowledgeGraphQuerier(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        await querier.initialize()
        
        # Execute commands based on arguments
        if args.repos:
            await querier.list_repositories()
        elif args.classes is not None:
            await querier.list_classes(args.classes if args.classes else None)
        elif args.explore:
            await querier.explore_repository(args.explore)
        elif args.class_name:
            await querier.explore_class(args.class_name)
        elif args.method:
            if len(args.method) >= 2:
                await querier.search_method(args.method[0], args.method[1])
            else:
                await querier.search_method(args.method[0])
        elif args.query:
            await querier.run_custom_query(args.query)
        elif args.interactive or len(sys.argv) == 1:
            await interactive_mode(querier)
        else:
            parser.print_help()
    
    finally:
        await querier.close()


if __name__ == "__main__":
    import sys
    asyncio.run(main())