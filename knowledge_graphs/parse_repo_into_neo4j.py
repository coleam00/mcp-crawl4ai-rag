"""
Direct Neo4j GitHub Code Repository Extractor

Creates nodes and relationships directly in Neo4j without Graphiti:
- File nodes
- Class nodes  
- Method nodes
- Function nodes
- Import relationships

Bypasses all LLM processing for maximum speed.
"""

import asyncio
import logging
import os
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
import ast

from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


class Neo4jCodeAnalyzer:
    """Analyzes code for direct Neo4j insertion"""
    
    def __init__(self):
        # External modules to ignore
        self.external_modules = {
            # Python standard library
            'os', 'sys', 'json', 'logging', 'datetime', 'pathlib', 'typing', 'collections',
            'asyncio', 'subprocess', 'ast', 're', 'string', 'urllib', 'http', 'email',
            'time', 'uuid', 'hashlib', 'base64', 'itertools', 'functools', 'operator',
            'contextlib', 'copy', 'pickle', 'tempfile', 'shutil', 'glob', 'fnmatch',
            'io', 'codecs', 'locale', 'platform', 'socket', 'ssl', 'threading', 'queue',
            'multiprocessing', 'concurrent', 'warnings', 'traceback', 'inspect',
            'importlib', 'pkgutil', 'types', 'weakref', 'gc', 'dataclasses', 'enum',
            'abc', 'numbers', 'decimal', 'fractions', 'math', 'cmath', 'random', 'statistics',
            
            # Common third-party libraries
            'requests', 'urllib3', 'httpx', 'aiohttp', 'flask', 'django', 'fastapi',
            'pydantic', 'sqlalchemy', 'alembic', 'psycopg2', 'pymongo', 'redis',
            'celery', 'pytest', 'unittest', 'mock', 'faker', 'factory', 'hypothesis',
            'numpy', 'pandas', 'matplotlib', 'seaborn', 'scipy', 'sklearn', 'torch',
            'tensorflow', 'keras', 'opencv', 'pillow', 'boto3', 'botocore', 'azure',
            'google', 'openai', 'anthropic', 'langchain', 'transformers', 'huggingface_hub',
            'click', 'typer', 'rich', 'colorama', 'tqdm', 'python-dotenv', 'pyyaml',
            'toml', 'configargparse', 'marshmallow', 'attrs', 'dataclasses-json',
            'jsonschema', 'cerberus', 'voluptuous', 'schema', 'jinja2', 'mako',
            'cryptography', 'bcrypt', 'passlib', 'jwt', 'authlib', 'oauthlib'
        }
    
    def analyze_python_file(self, file_path: Path, repo_root: Path, project_modules: Set[str]) -> Dict[str, Any]:
        """Extract structure for direct Neo4j insertion"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            relative_path = str(file_path.relative_to(repo_root))
            module_name = self._get_importable_module_name(file_path, repo_root, relative_path)
            
            # Extract structure
            classes = []
            functions = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Extract class with its methods and attributes
                    methods = []
                    attributes = []
                    
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if not item.name.startswith('_'):  # Public methods only
                                # Extract comprehensive parameter info
                                params = self._extract_function_parameters(item)
                                
                                # Get return type annotation
                                return_type = self._get_name(item.returns) if item.returns else 'Any'
                                
                                # Create detailed parameter list for Neo4j storage
                                params_detailed = []
                                for p in params:
                                    param_str = f"{p['name']}:{p['type']}"
                                    if p['optional'] and p['default'] is not None:
                                        param_str += f"={p['default']}"
                                    elif p['optional']:
                                        param_str += "=None"
                                    if p['kind'] != 'positional':
                                        param_str = f"[{p['kind']}] {param_str}"
                                    params_detailed.append(param_str)
                                
                                methods.append({
                                    'name': item.name,
                                    'params': params,  # Full parameter objects
                                    'params_detailed': params_detailed,  # Detailed string format
                                    'return_type': return_type,
                                    'args': [arg.arg for arg in item.args.args if arg.arg != 'self']  # Keep for backwards compatibility
                                })
                        elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                            # Type annotated attributes
                            if not item.target.id.startswith('_'):
                                attributes.append({
                                    'name': item.target.id,
                                    'type': self._get_name(item.annotation) if item.annotation else 'Any'
                                })
                    
                    classes.append({
                        'name': node.name,
                        'full_name': f"{module_name}.{node.name}",
                        'methods': methods,
                        'attributes': attributes
                    })
                
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Only top-level functions
                    if not any(node in cls_node.body for cls_node in ast.walk(tree) if isinstance(cls_node, ast.ClassDef)):
                        if not node.name.startswith('_'):
                            # Extract comprehensive parameter info
                            params = self._extract_function_parameters(node)
                            
                            # Get return type annotation
                            return_type = self._get_name(node.returns) if node.returns else 'Any'
                            
                            # Create detailed parameter list for Neo4j storage
                            params_detailed = []
                            for p in params:
                                param_str = f"{p['name']}:{p['type']}"
                                if p['optional'] and p['default'] is not None:
                                    param_str += f"={p['default']}"
                                elif p['optional']:
                                    param_str += "=None"
                                if p['kind'] != 'positional':
                                    param_str = f"[{p['kind']}] {param_str}"
                                params_detailed.append(param_str)
                            
                            # Simple format for backwards compatibility
                            params_list = [f"{p['name']}:{p['type']}" for p in params]
                            
                            functions.append({
                                'name': node.name,
                                'full_name': f"{module_name}.{node.name}",
                                'params': params,  # Full parameter objects
                                'params_detailed': params_detailed,  # Detailed string format
                                'params_list': params_list,  # Simple string format for backwards compatibility
                                'return_type': return_type,
                                'args': [arg.arg for arg in node.args.args]  # Keep for backwards compatibility
                            })
                
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    # Track internal imports only
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if self._is_likely_internal(alias.name, project_modules):
                                imports.append(alias.name)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        if (node.module.startswith('.') or self._is_likely_internal(node.module, project_modules)):
                            imports.append(node.module)
            
            return {
                'module_name': module_name,
                'file_path': relative_path,
                'classes': classes,
                'functions': functions,
                'imports': list(set(imports)),  # Remove duplicates
                'line_count': len(content.splitlines())
            }
            
        except Exception as e:
            logger.warning(f"Could not analyze {file_path}: {e}")
            return None
    
    def _is_likely_internal(self, import_name: str, project_modules: Set[str]) -> bool:
        """Check if an import is likely internal to the project"""
        if not import_name:
            return False
        
        # Relative imports are definitely internal
        if import_name.startswith('.'):
            return True
        
        # Check if it's a known external module
        base_module = import_name.split('.')[0]
        if base_module in self.external_modules:
            return False
        
        # Check if it matches any project module
        for project_module in project_modules:
            if import_name.startswith(project_module):
                return True
        
        # If it's not obviously external, consider it internal
        if (not any(ext in base_module.lower() for ext in ['test', 'mock', 'fake']) and
            not base_module.startswith('_') and
            len(base_module) > 2):
            return True
        
        return False
    
    def _get_importable_module_name(self, file_path: Path, repo_root: Path, relative_path: str) -> str:
        """Determine the actual importable module name for a Python file"""
        # Start with the default: convert file path to module path
        default_module = relative_path.replace('/', '.').replace('\\', '.').replace('.py', '')
        
        # Common patterns to detect the actual package root
        path_parts = Path(relative_path).parts
        
        # Look for common package indicators
        package_roots = []
        
        # Check each directory level for __init__.py to find package boundaries
        current_path = repo_root
        for i, part in enumerate(path_parts[:-1]):  # Exclude the .py file itself
            current_path = current_path / part
            if (current_path / '__init__.py').exists():
                # This is a package directory, mark it as a potential root
                package_roots.append(i)
        
        if package_roots:
            # Use the first (outermost) package as the root
            package_start = package_roots[0]
            module_parts = path_parts[package_start:]
            module_name = '.'.join(module_parts).replace('.py', '')
            return module_name
        
        # Fallback: look for common Python project structures
        # Skip common non-package directories
        skip_dirs = {'src', 'lib', 'source', 'python', 'pkg', 'packages'}
        
        # Find the first directory that's not in skip_dirs
        filtered_parts = []
        for part in path_parts:
            if part.lower() not in skip_dirs or filtered_parts:  # Once we start including, include everything
                filtered_parts.append(part)
        
        if filtered_parts:
            module_name = '.'.join(filtered_parts).replace('.py', '')
            return module_name
        
        # Final fallback: use the default
        return default_module
    
    def _extract_function_parameters(self, func_node):
        """Comprehensive parameter extraction from function definition"""
        params = []
        
        # Regular positional arguments
        for i, arg in enumerate(func_node.args.args):
            if arg.arg == 'self':
                continue
                
            param_info = {
                'name': arg.arg,
                'type': self._get_name(arg.annotation) if arg.annotation else 'Any',
                'kind': 'positional',
                'optional': False,
                'default': None
            }
            
            # Check if this argument has a default value
            defaults_start = len(func_node.args.args) - len(func_node.args.defaults)
            if i >= defaults_start:
                default_idx = i - defaults_start
                if default_idx < len(func_node.args.defaults):
                    param_info['optional'] = True
                    param_info['default'] = self._get_default_value(func_node.args.defaults[default_idx])
            
            params.append(param_info)
        
        # *args parameter
        if func_node.args.vararg:
            params.append({
                'name': f"*{func_node.args.vararg.arg}",
                'type': self._get_name(func_node.args.vararg.annotation) if func_node.args.vararg.annotation else 'Any',
                'kind': 'var_positional',
                'optional': True,
                'default': None
            })
        
        # Keyword-only arguments (after *)
        for i, arg in enumerate(func_node.args.kwonlyargs):
            param_info = {
                'name': arg.arg,
                'type': self._get_name(arg.annotation) if arg.annotation else 'Any',
                'kind': 'keyword_only',
                'optional': True,  # All kwonly args are optional unless explicitly required
                'default': None
            }
            
            # Check for default value
            if i < len(func_node.args.kw_defaults) and func_node.args.kw_defaults[i] is not None:
                param_info['default'] = self._get_default_value(func_node.args.kw_defaults[i])
            else:
                param_info['optional'] = False  # No default = required kwonly arg
            
            params.append(param_info)
        
        # **kwargs parameter
        if func_node.args.kwarg:
            params.append({
                'name': f"**{func_node.args.kwarg.arg}",
                'type': self._get_name(func_node.args.kwarg.annotation) if func_node.args.kwarg.annotation else 'Dict[str, Any]',
                'kind': 'var_keyword',
                'optional': True,
                'default': None
            })
        
        return params
    
    def _get_default_value(self, default_node):
        """Extract default value from AST node"""
        try:
            if isinstance(default_node, ast.Constant):
                return repr(default_node.value)
            elif isinstance(default_node, ast.Name):
                return default_node.id
            elif isinstance(default_node, ast.Attribute):
                return self._get_name(default_node)
            elif isinstance(default_node, ast.List):
                return "[]"
            elif isinstance(default_node, ast.Dict):
                return "{}"
            else:
                return "..."
        except Exception:
            return "..."
    
    def _get_name(self, node):
        """Extract name from AST node, handling complex types safely"""
        if node is None:
            return "Any"
        
        try:
            if isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Attribute):
                if hasattr(node, 'value'):
                    return f"{self._get_name(node.value)}.{node.attr}"
                else:
                    return node.attr
            elif isinstance(node, ast.Subscript):
                # Handle List[Type], Dict[K,V], etc.
                base = self._get_name(node.value)
                if hasattr(node, 'slice'):
                    if isinstance(node.slice, ast.Name):
                        return f"{base}[{node.slice.id}]"
                    elif isinstance(node.slice, ast.Tuple):
                        elts = [self._get_name(elt) for elt in node.slice.elts]
                        return f"{base}[{', '.join(elts)}]"
                    elif isinstance(node.slice, ast.Constant):
                        return f"{base}[{repr(node.slice.value)}]"
                    elif isinstance(node.slice, ast.Attribute):
                        return f"{base}[{self._get_name(node.slice)}]"
                    elif isinstance(node.slice, ast.Subscript):
                        return f"{base}[{self._get_name(node.slice)}]"
                    else:
                        # Try to get the name of the slice, fallback to Any if it fails
                        try:
                            slice_name = self._get_name(node.slice)
                            return f"{base}[{slice_name}]"
                        except:
                            return f"{base}[Any]"
                return base
            elif isinstance(node, ast.Constant):
                return str(node.value)
            elif isinstance(node, ast.Str):  # Python < 3.8
                return f'"{node.s}"'
            elif isinstance(node, ast.Tuple):
                elts = [self._get_name(elt) for elt in node.elts]
                return f"({', '.join(elts)})"
            elif isinstance(node, ast.List):
                elts = [self._get_name(elt) for elt in node.elts]
                return f"[{', '.join(elts)}]"
            else:
                # Fallback for complex types - return a simple string representation
                return "Any"
        except Exception:
            # If anything goes wrong, return a safe default
            return "Any"


class DirectNeo4jExtractor:
    """Creates nodes and relationships directly in Neo4j"""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None
        self.analyzer = Neo4jCodeAnalyzer()
    
    async def initialize(self):
        """Initialize Neo4j connection"""
        logger.info("Initializing Neo4j connection...")
        self.driver = AsyncGraphDatabase.driver(
            self.neo4j_uri, 
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        # Clear existing data
        # logger.info("Clearing existing data...")
        # async with self.driver.session() as session:
        #     await session.run("MATCH (n) DETACH DELETE n")
        
        # Create constraints and indexes
        logger.info("Creating constraints and indexes...")
        async with self.driver.session() as session:
            # Create constraints - using MERGE-friendly approach
            await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE")
            await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Class) REQUIRE c.full_name IS UNIQUE")
            # Remove unique constraints for methods/attributes since they can be duplicated across classes
            # await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (m:Method) REQUIRE m.full_name IS UNIQUE")
            # await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:Function) REQUIRE f.full_name IS UNIQUE")
            # await session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Attribute) REQUIRE a.full_name IS UNIQUE")
            
            # Create indexes for performance
            await session.run("CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.name)")
            await session.run("CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.name)")
            await session.run("CREATE INDEX IF NOT EXISTS FOR (m:Method) ON (m.name)")
        
        logger.info("Neo4j initialized successfully")
    
    async def clear_repository_data(self, repo_name: str):
        """Clear all data for a specific repository"""
        logger.info(f"Clearing existing data for repository: {repo_name}")
        async with self.driver.session() as session:
            # Delete in specific order to avoid constraint issues
            
            # 1. Delete methods and attributes (they depend on classes)
            await session.run("""
                MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)-[:HAS_METHOD]->(m:Method)
                DETACH DELETE m
            """, repo_name=repo_name)
            
            await session.run("""
                MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)-[:HAS_ATTRIBUTE]->(a:Attribute)
                DETACH DELETE a
            """, repo_name=repo_name)
            
            # 2. Delete functions (they depend on files)
            await session.run("""
                MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(func:Function)
                DETACH DELETE func
            """, repo_name=repo_name)
            
            # 3. Delete classes (they depend on files)
            await session.run("""
                MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)
                DETACH DELETE c
            """, repo_name=repo_name)
            
            # 4. Delete files (they depend on repository)
            await session.run("""
                MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)
                DETACH DELETE f
            """, repo_name=repo_name)
            
            # 5. Finally delete the repository
            await session.run("""
                MATCH (r:Repository {name: $repo_name})
                DETACH DELETE r
            """, repo_name=repo_name)
            
        logger.info(f"Cleared data for repository: {repo_name}")
    
    async def close(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()
    
    def clone_repo(self, repo_url: str, target_dir: str) -> str:
        """Clone repository with shallow clone"""
        logger.info(f"Cloning repository to: {target_dir}")
        if os.path.exists(target_dir):
            logger.info(f"Removing existing directory: {target_dir}")
            try:
                def handle_remove_readonly(func, path, exc):
                    try:
                        if os.path.exists(path):
                            os.chmod(path, 0o777)
                            func(path)
                    except PermissionError:
                        logger.warning(f"Could not remove {path} - file in use, skipping")
                        pass
                shutil.rmtree(target_dir, onerror=handle_remove_readonly)
            except Exception as e:
                logger.warning(f"Could not fully remove {target_dir}: {e}. Proceeding anyway...")
        
        logger.info(f"Running git clone from {repo_url}")
        subprocess.run(['git', 'clone', '--depth', '1', repo_url, target_dir], check=True)
        logger.info("Repository cloned successfully")
        return target_dir
    
    def get_python_files(self, repo_path: str) -> List[Path]:
        """Get Python files, focusing on main source directories"""
        python_files = []
        exclude_dirs = {
            'tests', 'test', '__pycache__', '.git', 'venv', 'env',
            'node_modules', 'build', 'dist', '.pytest_cache', 'docs',
            'examples', 'example', 'demo', 'benchmark'
        }
        
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
            
            for file in files:
                if file.endswith('.py') and not file.startswith('test_'):
                    file_path = Path(root) / file
                    if (file_path.stat().st_size < 500_000 and 
                        file not in ['setup.py', 'conftest.py']):
                        python_files.append(file_path)
        
        return python_files
    
    async def analyze_repository(self, repo_url: str, temp_dir: str = None):
        """Analyze repository and create nodes/relationships in Neo4j"""
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        logger.info(f"Analyzing repository: {repo_name}")
        
        # Clear existing data for this repository before re-processing
        await self.clear_repository_data(repo_name)
        
        # Set default temp_dir to repos folder at script level
        if temp_dir is None:
            script_dir = Path(__file__).parent
            temp_dir = str(script_dir / "repos" / repo_name)
        
        # Clone and analyze
        repo_path = Path(self.clone_repo(repo_url, temp_dir))
        
        try:
            logger.info("Getting Python files...")
            python_files = self.get_python_files(str(repo_path))
            logger.info(f"Found {len(python_files)} Python files to analyze")
            
            # First pass: identify project modules
            logger.info("Identifying project modules...")
            project_modules = set()
            for file_path in python_files:
                relative_path = str(file_path.relative_to(repo_path))
                module_parts = relative_path.replace('/', '.').replace('.py', '').split('.')
                if len(module_parts) > 0 and not module_parts[0].startswith('.'):
                    project_modules.add(module_parts[0])
            
            logger.info(f"Identified project modules: {sorted(project_modules)}")
            
            # Second pass: analyze files and collect data
            logger.info("Analyzing Python files...")
            modules_data = []
            for i, file_path in enumerate(python_files):
                if i % 20 == 0:
                    logger.info(f"Analyzing file {i+1}/{len(python_files)}: {file_path.name}")
                
                analysis = self.analyzer.analyze_python_file(file_path, repo_path, project_modules)
                if analysis:
                    modules_data.append(analysis)
            
            logger.info(f"Found {len(modules_data)} files with content")
            
            # Create nodes and relationships in Neo4j
            logger.info("Creating nodes and relationships in Neo4j...")
            await self._create_graph(repo_name, modules_data)
            
            # Print summary
            total_classes = sum(len(mod['classes']) for mod in modules_data)
            total_methods = sum(len(cls['methods']) for mod in modules_data for cls in mod['classes'])
            total_functions = sum(len(mod['functions']) for mod in modules_data)
            total_imports = sum(len(mod['imports']) for mod in modules_data)
            
            print(f"\\n=== Direct Neo4j Repository Analysis for {repo_name} ===")
            print(f"Files processed: {len(modules_data)}")
            print(f"Classes created: {total_classes}")
            print(f"Methods created: {total_methods}")
            print(f"Functions created: {total_functions}")
            print(f"Import relationships: {total_imports}")
            
            logger.info(f"Successfully created Neo4j graph for {repo_name}")
            
        finally:
            if os.path.exists(temp_dir):
                logger.info(f"Cleaning up temporary directory: {temp_dir}")
                try:
                    def handle_remove_readonly(func, path, exc):
                        try:
                            if os.path.exists(path):
                                os.chmod(path, 0o777)
                                func(path)
                        except PermissionError:
                            logger.warning(f"Could not remove {path} - file in use, skipping")
                            pass
                    
                    shutil.rmtree(temp_dir, onerror=handle_remove_readonly)
                    logger.info("Cleanup completed")
                except Exception as e:
                    logger.warning(f"Cleanup failed: {e}. Directory may remain at {temp_dir}")
                    # Don't fail the whole process due to cleanup issues
    
    async def _create_graph(self, repo_name: str, modules_data: List[Dict]):
        """Create all nodes and relationships in Neo4j"""
        
        async with self.driver.session() as session:
            # Create Repository node
            await session.run(
                "CREATE (r:Repository {name: $repo_name, created_at: datetime()})",
                repo_name=repo_name
            )
            
            nodes_created = 0
            relationships_created = 0
            
            for i, mod in enumerate(modules_data):
                # 1. Create File node
                await session.run("""
                    CREATE (f:File {
                        name: $name,
                        path: $path,
                        module_name: $module_name,
                        line_count: $line_count,
                        created_at: datetime()
                    })
                """, 
                    name=mod['file_path'].split('/')[-1],
                    path=mod['file_path'],
                    module_name=mod['module_name'],
                    line_count=mod['line_count']
                )
                nodes_created += 1
                
                # 2. Connect File to Repository
                await session.run("""
                    MATCH (r:Repository {name: $repo_name})
                    MATCH (f:File {path: $file_path})
                    CREATE (r)-[:CONTAINS]->(f)
                """, repo_name=repo_name, file_path=mod['file_path'])
                relationships_created += 1
                
                # 3. Create Class nodes and relationships
                for cls in mod['classes']:
                    # Create Class node using MERGE to avoid duplicates
                    await session.run("""
                        MERGE (c:Class {full_name: $full_name})
                        ON CREATE SET c.name = $name, c.created_at = datetime()
                    """, name=cls['name'], full_name=cls['full_name'])
                    nodes_created += 1
                    
                    # Connect File to Class
                    await session.run("""
                        MATCH (f:File {path: $file_path})
                        MATCH (c:Class {full_name: $class_full_name})
                        MERGE (f)-[:DEFINES]->(c)
                    """, file_path=mod['file_path'], class_full_name=cls['full_name'])
                    relationships_created += 1
                    
                    # 4. Create Method nodes - use MERGE to avoid duplicates
                    for method in cls['methods']:
                        method_full_name = f"{cls['full_name']}.{method['name']}"
                        # Create method with unique ID to avoid conflicts
                        method_id = f"{cls['full_name']}::{method['name']}"
                        
                        await session.run("""
                            MERGE (m:Method {method_id: $method_id})
                            ON CREATE SET m.name = $name, 
                                         m.full_name = $full_name,
                                         m.args = $args,
                                         m.params_list = $params_list,
                                         m.params_detailed = $params_detailed,
                                         m.return_type = $return_type,
                                         m.created_at = datetime()
                        """, 
                            name=method['name'], 
                            full_name=method_full_name,
                            method_id=method_id,
                            args=method['args'],
                            params_list=[f"{p['name']}:{p['type']}" for p in method['params']],  # Simple format
                            params_detailed=method.get('params_detailed', []),  # Detailed format
                            return_type=method['return_type']
                        )
                        nodes_created += 1
                        
                        # Connect Class to Method
                        await session.run("""
                            MATCH (c:Class {full_name: $class_full_name})
                            MATCH (m:Method {method_id: $method_id})
                            MERGE (c)-[:HAS_METHOD]->(m)
                        """, 
                            class_full_name=cls['full_name'], 
                            method_id=method_id
                        )
                        relationships_created += 1
                    
                    # 5. Create Attribute nodes - use MERGE to avoid duplicates
                    for attr in cls['attributes']:
                        attr_full_name = f"{cls['full_name']}.{attr['name']}"
                        # Create attribute with unique ID to avoid conflicts
                        attr_id = f"{cls['full_name']}::{attr['name']}"
                        await session.run("""
                            MERGE (a:Attribute {attr_id: $attr_id})
                            ON CREATE SET a.name = $name,
                                         a.full_name = $full_name,
                                         a.type = $type,
                                         a.created_at = datetime()
                        """, 
                            name=attr['name'], 
                            full_name=attr_full_name,
                            attr_id=attr_id,
                            type=attr['type']
                        )
                        nodes_created += 1
                        
                        # Connect Class to Attribute
                        await session.run("""
                            MATCH (c:Class {full_name: $class_full_name})
                            MATCH (a:Attribute {attr_id: $attr_id})
                            MERGE (c)-[:HAS_ATTRIBUTE]->(a)
                        """, 
                            class_full_name=cls['full_name'], 
                            attr_id=attr_id
                        )
                        relationships_created += 1
                
                # 6. Create Function nodes (top-level) - use MERGE to avoid duplicates
                for func in mod['functions']:
                    func_id = f"{mod['file_path']}::{func['name']}"
                    await session.run("""
                        MERGE (f:Function {func_id: $func_id})
                        ON CREATE SET f.name = $name,
                                     f.full_name = $full_name,
                                     f.args = $args,
                                     f.params_list = $params_list,
                                     f.params_detailed = $params_detailed,
                                     f.return_type = $return_type,
                                     f.created_at = datetime()
                    """, 
                        name=func['name'], 
                        full_name=func['full_name'],
                        func_id=func_id,
                        args=func['args'],
                        params_list=func.get('params_list', []),  # Simple format for backwards compatibility
                        params_detailed=func.get('params_detailed', []),  # Detailed format
                        return_type=func['return_type']
                    )
                    nodes_created += 1
                    
                    # Connect File to Function
                    await session.run("""
                        MATCH (file:File {path: $file_path})
                        MATCH (func:Function {func_id: $func_id})
                        MERGE (file)-[:DEFINES]->(func)
                    """, file_path=mod['file_path'], func_id=func_id)
                    relationships_created += 1
                
                # 7. Create Import relationships
                for import_name in mod['imports']:
                    # Try to find the target file
                    await session.run("""
                        MATCH (source:File {path: $source_path})
                        OPTIONAL MATCH (target:File) 
                        WHERE target.module_name = $import_name OR target.module_name STARTS WITH $import_name
                        WITH source, target
                        WHERE target IS NOT NULL
                        MERGE (source)-[:IMPORTS]->(target)
                    """, source_path=mod['file_path'], import_name=import_name)
                    relationships_created += 1
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(modules_data)} files...")
            
            logger.info(f"Created {nodes_created} nodes and {relationships_created} relationships")
    
    async def search_graph(self, query_type: str, **kwargs):
        """Search the Neo4j graph directly"""
        async with self.driver.session() as session:
            if query_type == "files_importing":
                target = kwargs.get('target')
                result = await session.run("""
                    MATCH (source:File)-[:IMPORTS]->(target:File)
                    WHERE target.module_name CONTAINS $target
                    RETURN source.path as file, target.module_name as imports
                """, target=target)
                return [{"file": record["file"], "imports": record["imports"]} async for record in result]
            
            elif query_type == "classes_in_file":
                file_path = kwargs.get('file_path')
                result = await session.run("""
                    MATCH (f:File {path: $file_path})-[:DEFINES]->(c:Class)
                    RETURN c.name as class_name, c.full_name as full_name
                """, file_path=file_path)
                return [{"class_name": record["class_name"], "full_name": record["full_name"]} async for record in result]
            
            elif query_type == "methods_of_class":
                class_name = kwargs.get('class_name')
                result = await session.run("""
                    MATCH (c:Class)-[:HAS_METHOD]->(m:Method)
                    WHERE c.name CONTAINS $class_name OR c.full_name CONTAINS $class_name
                    RETURN m.name as method_name, m.args as args
                """, class_name=class_name)
                return [{"method_name": record["method_name"], "args": record["args"]} async for record in result]


async def main():
    """Example usage"""
    load_dotenv()
    
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = os.environ.get('NEO4J_PASSWORD', 'password')
    
    extractor = DirectNeo4jExtractor(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        await extractor.initialize()
        
        # Analyze repository - direct Neo4j, no LLM processing!
        # repo_url = "https://github.com/pydantic/pydantic-ai.git"
        repo_url = "https://github.com/getzep/graphiti.git"
        await extractor.analyze_repository(repo_url)
        
        # Direct graph queries
        print("\\n=== Direct Neo4j Queries ===")
        
        # Which files import from models?
        results = await extractor.search_graph("files_importing", target="models")
        print(f"\\nFiles importing from 'models': {len(results)}")
        for result in results[:3]:
            print(f"- {result['file']} imports {result['imports']}")
        
        # What classes are in a specific file?
        results = await extractor.search_graph("classes_in_file", file_path="pydantic_ai/models/openai.py")
        print(f"\\nClasses in openai.py: {len(results)}")
        for result in results:
            print(f"- {result['class_name']}")
        
        # What methods does OpenAIModel have?
        results = await extractor.search_graph("methods_of_class", class_name="OpenAIModel")
        print(f"\\nMethods of OpenAIModel: {len(results)}")
        for result in results[:5]:
            print(f"- {result['method_name']}({', '.join(result['args'])})")
    
    finally:
        await extractor.close()


if __name__ == "__main__":
    asyncio.run(main())