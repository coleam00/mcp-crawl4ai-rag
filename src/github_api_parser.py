"""
GitHub API-basierte Repository-Parsing Alternative zu Git.
Viel schneller und benötigt kein Git im Container.
"""
import requests
import tempfile
import zipfile
import os
from pathlib import Path
from typing import Dict, List, Any
import ast
import json

class GitHubAPIParser:
    """
    Parst GitHub Repositories über die API ohne Git zu benötigen.
    """
    
    def __init__(self, github_token: str = None):
        self.github_token = github_token
        self.session = requests.Session()
        if github_token:
            self.session.headers.update({
                'Authorization': f'token {github_token}',
                'Accept': 'application/vnd.github.v3+json'
            })
    
    def parse_repository(self, repo_url: str) -> Dict[str, Any]:
        """
        Parst ein GitHub Repository über die API.
        
        Args:
            repo_url: GitHub Repository URL
            
        Returns:
            Dict mit Repository-Informationen
        """
        # Extrahiere Owner und Repo Name aus URL
        parts = repo_url.rstrip('/').split('/')
        owner = parts[-2]
        repo = parts[-1].replace('.git', '')
        
        # Lade Repository-Metadaten
        repo_info = self._get_repo_info(owner, repo)
        
        # Lade Repository-Inhalt als ZIP
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = self._download_repo_zip(owner, repo, temp_dir)
            extracted_path = self._extract_zip(zip_path, temp_dir)
            
            # Analysiere Python-Dateien
            python_files = self._find_python_files(extracted_path)
            analysis = self._analyze_python_files(python_files)
            
            return {
                'success': True,
                'repository': f"{owner}/{repo}",
                'url': repo_url,
                'statistics': {
                    'files': len(python_files),
                    'classes': len(analysis['classes']),
                    'functions': len(analysis['functions']),
                    'methods': sum(len(cls['methods']) for cls in analysis['classes'])
                },
                'classes': analysis['classes'],
                'functions': analysis['functions'],
                'metadata': {
                    'stars': repo_info.get('stargazers_count', 0),
                    'language': repo_info.get('language', 'Unknown'),
                    'description': repo_info.get('description', ''),
                    'created_at': repo_info.get('created_at', ''),
                    'updated_at': repo_info.get('updated_at', '')
                }
            }
    
    def _get_repo_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Hole Repository-Informationen über GitHub API."""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def _download_repo_zip(self, owner: str, repo: str, temp_dir: str) -> str:
        """Lade Repository als ZIP-Datei herunter."""
        url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
        response = self.session.get(url)
        response.raise_for_status()
        
        zip_path = os.path.join(temp_dir, f"{repo}.zip")
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        return zip_path
    
    def _extract_zip(self, zip_path: str, temp_dir: str) -> str:
        """Extrahiere ZIP-Datei."""
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Finde den extrahierten Ordner
        for item in os.listdir(temp_dir):
            item_path = os.path.join(temp_dir, item)
            if os.path.isdir(item_path) and item != '__pycache__':
                return item_path
        
        return temp_dir
    
    def _find_python_files(self, directory: str) -> List[str]:
        """Finde alle Python-Dateien im Verzeichnis."""
        python_files = []
        for root, dirs, files in os.walk(directory):
            # Ignoriere bestimmte Verzeichnisse
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.pytest_cache', 'node_modules']]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        
        return python_files
    
    def _analyze_python_files(self, python_files: List[str]) -> Dict[str, Any]:
        """Analysiere Python-Dateien und extrahiere Klassen/Funktionen."""
        classes = []
        functions = []
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                file_analysis = self._analyze_ast(tree, file_path)
                
                classes.extend(file_analysis['classes'])
                functions.extend(file_analysis['functions'])
                
            except Exception as e:
                print(f"Fehler beim Analysieren von {file_path}: {e}")
                continue
        
        return {
            'classes': classes,
            'functions': functions
        }
    
    def _analyze_ast(self, tree: ast.AST, file_path: str) -> Dict[str, Any]:
        """Analysiere AST und extrahiere Informationen."""
        classes = []
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = {
                    'name': node.name,
                    'full_name': f"{Path(file_path).stem}.{node.name}",
                    'file_path': file_path,
                    'methods': [],
                    'attributes': []
                }
                
                # Analysiere Methoden
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        method_info = {
                            'name': item.name,
                            'parameters': [arg.arg for arg in item.args.args],
                            'return_type': 'Any'  # Könnte erweitert werden
                        }
                        class_info['methods'].append(method_info)
                
                classes.append(class_info)
            
            elif isinstance(node, ast.FunctionDef) and not self._is_method(node, tree):
                function_info = {
                    'name': node.name,
                    'full_name': f"{Path(file_path).stem}.{node.name}",
                    'file_path': file_path,
                    'parameters': [arg.arg for arg in node.args.args],
                    'return_type': 'Any'
                }
                functions.append(function_info)
        
        return {
            'classes': classes,
            'functions': functions
        }
    
    def _is_method(self, node: ast.FunctionDef, tree: ast.AST) -> bool:
        """Prüfe ob eine Funktion eine Methode ist."""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                if node in parent.body:
                    return True
        return False

# Beispiel-Verwendung
if __name__ == "__main__":
    parser = GitHubAPIParser()
    result = parser.parse_repository("https://github.com/pipecat-ai/pipecat.git")
    print(json.dumps(result, indent=2)) 