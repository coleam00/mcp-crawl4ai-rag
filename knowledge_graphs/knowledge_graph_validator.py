"""
Knowledge Graph Validator

Validates AI-generated code against Neo4j knowledge graph containing
repository information. Checks imports, methods, attributes, and parameters.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from neo4j import AsyncGraphDatabase

from ai_script_analyzer import (
    AnalysisResult, ImportInfo, MethodCall, AttributeAccess, 
    FunctionCall, ClassInstantiation
)

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    VALID = "VALID"
    INVALID = "INVALID" 
    UNCERTAIN = "UNCERTAIN"
    NOT_FOUND = "NOT_FOUND"


@dataclass
class ValidationResult:
    """Result of validating a single element"""
    status: ValidationStatus
    confidence: float  # 0.0 to 1.0
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ImportValidation:
    """Validation result for an import"""
    import_info: ImportInfo
    validation: ValidationResult
    available_classes: List[str] = field(default_factory=list)
    available_functions: List[str] = field(default_factory=list)


@dataclass
class MethodValidation:
    """Validation result for a method call"""
    method_call: MethodCall
    validation: ValidationResult
    expected_params: List[str] = field(default_factory=list)
    actual_params: List[str] = field(default_factory=list)
    parameter_validation: ValidationResult = None


@dataclass
class AttributeValidation:
    """Validation result for attribute access"""
    attribute_access: AttributeAccess
    validation: ValidationResult
    expected_type: Optional[str] = None


@dataclass
class FunctionValidation:
    """Validation result for function call"""
    function_call: FunctionCall
    validation: ValidationResult
    expected_params: List[str] = field(default_factory=list)
    actual_params: List[str] = field(default_factory=list)
    parameter_validation: ValidationResult = None


@dataclass
class ClassValidation:
    """Validation result for class instantiation"""
    class_instantiation: ClassInstantiation
    validation: ValidationResult
    constructor_params: List[str] = field(default_factory=list)
    parameter_validation: ValidationResult = None


@dataclass
class ScriptValidationResult:
    """Complete validation results for a script"""
    script_path: str
    analysis_result: AnalysisResult
    import_validations: List[ImportValidation] = field(default_factory=list)
    class_validations: List[ClassValidation] = field(default_factory=list)
    method_validations: List[MethodValidation] = field(default_factory=list)
    attribute_validations: List[AttributeValidation] = field(default_factory=list)
    function_validations: List[FunctionValidation] = field(default_factory=list)
    overall_confidence: float = 0.0
    hallucinations_detected: List[Dict[str, Any]] = field(default_factory=list)


class KnowledgeGraphValidator:
    """Validates code against Neo4j knowledge graph"""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None
        
        # Cache for performance
        self.module_cache: Dict[str, List[str]] = {}
        self.class_cache: Dict[str, Dict[str, Any]] = {}
        self.method_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.repo_cache: Dict[str, str] = {}  # module_name -> repo_name
        self.knowledge_graph_modules: Set[str] = set()  # Track modules in knowledge graph
    
    async def initialize(self):
        """Initialize Neo4j connection"""
        self.driver = AsyncGraphDatabase.driver(
            self.neo4j_uri, 
            auth=(self.neo4j_user, self.neo4j_password)
        )
        logger.info("Knowledge graph validator initialized")
    
    async def close(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()
    
    async def validate_script(self, analysis_result: AnalysisResult) -> ScriptValidationResult:
        """Validate entire script analysis against knowledge graph"""
        result = ScriptValidationResult(
            script_path=analysis_result.file_path,
            analysis_result=analysis_result
        )
        
        # Validate imports first (builds context for other validations)
        result.import_validations = await self._validate_imports(analysis_result.imports)
        
        # Validate class instantiations
        result.class_validations = await self._validate_class_instantiations(
            analysis_result.class_instantiations
        )
        
        # Validate method calls
        result.method_validations = await self._validate_method_calls(
            analysis_result.method_calls
        )
        
        # Validate attribute accesses
        result.attribute_validations = await self._validate_attribute_accesses(
            analysis_result.attribute_accesses
        )
        
        # Validate function calls
        result.function_validations = await self._validate_function_calls(
            analysis_result.function_calls
        )
        
        # Calculate overall confidence and detect hallucinations
        result.overall_confidence = self._calculate_overall_confidence(result)
        result.hallucinations_detected = self._detect_hallucinations(result)
        
        return result
    
    async def _validate_imports(self, imports: List[ImportInfo]) -> List[ImportValidation]:
        """Validate all imports against knowledge graph"""
        validations = []
        
        for import_info in imports:
            validation = await self._validate_single_import(import_info)
            validations.append(validation)
        
        return validations
    
    async def _validate_single_import(self, import_info: ImportInfo) -> ImportValidation:
        """Validate a single import"""
        # Determine module to search for
        search_module = import_info.module if import_info.is_from_import else import_info.name
        
        # Check cache first
        if search_module in self.module_cache:
            available_files = self.module_cache[search_module]
        else:
            # Query Neo4j for matching modules
            available_files = await self._find_modules(search_module)
            self.module_cache[search_module] = available_files
        
        if available_files:
            # Get available classes and functions from the module
            classes, functions = await self._get_module_contents(search_module)
            
            # Track this module as being in the knowledge graph
            self.knowledge_graph_modules.add(search_module)
            
            # Also track the base module for "from X.Y.Z import ..." patterns
            if '.' in search_module:
                base_module = search_module.split('.')[0]
                self.knowledge_graph_modules.add(base_module)
            
            validation = ValidationResult(
                status=ValidationStatus.VALID,
                confidence=0.9,
                message=f"Module '{search_module}' found in knowledge graph",
                details={"matched_files": available_files, "in_knowledge_graph": True}
            )
            
            return ImportValidation(
                import_info=import_info,
                validation=validation,
                available_classes=classes,
                available_functions=functions
            )
        else:
            # External library - mark as such but don't treat as error
            validation = ValidationResult(
                status=ValidationStatus.UNCERTAIN,
                confidence=0.8,  # High confidence it's external, not an error
                message=f"Module '{search_module}' is external (not in knowledge graph)",
                details={"could_be_external": True, "in_knowledge_graph": False}
            )
            
            return ImportValidation(
                import_info=import_info,
                validation=validation
            )
    
    async def _validate_class_instantiations(self, instantiations: List[ClassInstantiation]) -> List[ClassValidation]:
        """Validate class instantiations"""
        validations = []
        
        for instantiation in instantiations:
            validation = await self._validate_single_class_instantiation(instantiation)
            validations.append(validation)
        
        return validations
    
    async def _validate_single_class_instantiation(self, instantiation: ClassInstantiation) -> ClassValidation:
        """Validate a single class instantiation"""
        class_name = instantiation.full_class_name or instantiation.class_name
        
        # Skip validation for classes not from knowledge graph
        if not self._is_from_knowledge_graph(class_name):
            validation = ValidationResult(
                status=ValidationStatus.UNCERTAIN,
                confidence=0.8,
                message=f"Skipping validation: '{class_name}' is not from knowledge graph"
            )
            return ClassValidation(
                class_instantiation=instantiation,
                validation=validation
            )
        
        # Find class in knowledge graph
        class_info = await self._find_class(class_name)
        
        if not class_info:
            validation = ValidationResult(
                status=ValidationStatus.NOT_FOUND,
                confidence=0.2,
                message=f"Class '{class_name}' not found in knowledge graph"
            )
            return ClassValidation(
                class_instantiation=instantiation,
                validation=validation
            )
        
        # Check constructor parameters (look for __init__ method)
        init_method = await self._find_method(class_name, "__init__")
        
        if init_method:
            param_validation = self._validate_parameters(
                expected_params=init_method.get('params_list', []),
                provided_args=instantiation.args,
                provided_kwargs=instantiation.kwargs
            )
        else:
            param_validation = ValidationResult(
                status=ValidationStatus.UNCERTAIN,
                confidence=0.5,
                message="Constructor parameters not found"
            )
        
        # Use parameter validation result if it failed
        if param_validation.status == ValidationStatus.INVALID:
            validation = ValidationResult(
                status=ValidationStatus.INVALID,
                confidence=param_validation.confidence,
                message=f"Class '{class_name}' found but has invalid constructor parameters: {param_validation.message}",
                suggestions=param_validation.suggestions
            )
        else:
            validation = ValidationResult(
                status=ValidationStatus.VALID,
                confidence=0.8,
                message=f"Class '{class_name}' found in knowledge graph"
            )
        
        return ClassValidation(
            class_instantiation=instantiation,
            validation=validation,
            parameter_validation=param_validation
        )
    
    async def _validate_method_calls(self, method_calls: List[MethodCall]) -> List[MethodValidation]:
        """Validate method calls"""
        validations = []
        
        for method_call in method_calls:
            validation = await self._validate_single_method_call(method_call)
            validations.append(validation)
        
        return validations
    
    async def _validate_single_method_call(self, method_call: MethodCall) -> MethodValidation:
        """Validate a single method call"""
        class_type = method_call.object_type
        
        if not class_type:
            validation = ValidationResult(
                status=ValidationStatus.UNCERTAIN,
                confidence=0.3,
                message=f"Cannot determine object type for '{method_call.object_name}'"
            )
            return MethodValidation(
                method_call=method_call,
                validation=validation
            )
        
        # Skip validation for classes not from knowledge graph
        if not self._is_from_knowledge_graph(class_type):
            validation = ValidationResult(
                status=ValidationStatus.UNCERTAIN,
                confidence=0.8,
                message=f"Skipping validation: '{class_type}' is not from knowledge graph"
            )
            return MethodValidation(
                method_call=method_call,
                validation=validation
            )
        
        # Find method in knowledge graph
        method_info = await self._find_method(class_type, method_call.method_name)
        
        if not method_info:
            # Check for similar method names
            similar_methods = await self._find_similar_methods(class_type, method_call.method_name)
            
            validation = ValidationResult(
                status=ValidationStatus.NOT_FOUND,
                confidence=0.1,
                message=f"Method '{method_call.method_name}' not found on class '{class_type}'",
                suggestions=similar_methods
            )
            return MethodValidation(
                method_call=method_call,
                validation=validation
            )
        
        # Validate parameters
        expected_params = method_info.get('params_list', [])
        param_validation = self._validate_parameters(
            expected_params=expected_params,
            provided_args=method_call.args,
            provided_kwargs=method_call.kwargs
        )
        
        # Use parameter validation result if it failed
        if param_validation.status == ValidationStatus.INVALID:
            validation = ValidationResult(
                status=ValidationStatus.INVALID,
                confidence=param_validation.confidence,
                message=f"Method '{method_call.method_name}' found but has invalid parameters: {param_validation.message}",
                suggestions=param_validation.suggestions
            )
        else:
            validation = ValidationResult(
                status=ValidationStatus.VALID,
                confidence=0.9,
                message=f"Method '{method_call.method_name}' found on class '{class_type}'"
            )
        
        return MethodValidation(
            method_call=method_call,
            validation=validation,
            expected_params=expected_params,
            actual_params=method_call.args + list(method_call.kwargs.keys()),
            parameter_validation=param_validation
        )
    
    async def _validate_attribute_accesses(self, attribute_accesses: List[AttributeAccess]) -> List[AttributeValidation]:
        """Validate attribute accesses"""
        validations = []
        
        for attr_access in attribute_accesses:
            validation = await self._validate_single_attribute_access(attr_access)
            validations.append(validation)
        
        return validations
    
    async def _validate_single_attribute_access(self, attr_access: AttributeAccess) -> AttributeValidation:
        """Validate a single attribute access"""
        class_type = attr_access.object_type
        
        if not class_type:
            validation = ValidationResult(
                status=ValidationStatus.UNCERTAIN,
                confidence=0.3,
                message=f"Cannot determine object type for '{attr_access.object_name}'"
            )
            return AttributeValidation(
                attribute_access=attr_access,
                validation=validation
            )
        
        # Skip validation for classes not from knowledge graph
        if not self._is_from_knowledge_graph(class_type):
            validation = ValidationResult(
                status=ValidationStatus.UNCERTAIN,
                confidence=0.8,
                message=f"Skipping validation: '{class_type}' is not from knowledge graph"
            )
            return AttributeValidation(
                attribute_access=attr_access,
                validation=validation
            )
        
        # Find attribute in knowledge graph
        attr_info = await self._find_attribute(class_type, attr_access.attribute_name)
        
        if not attr_info:
            # If not found as attribute, check if it's a method (for decorators like @agent.tool)
            method_info = await self._find_method(class_type, attr_access.attribute_name)
            
            if method_info:
                validation = ValidationResult(
                    status=ValidationStatus.VALID,
                    confidence=0.8,
                    message=f"'{attr_access.attribute_name}' found as method on class '{class_type}' (likely used as decorator)"
                )
                return AttributeValidation(
                    attribute_access=attr_access,
                    validation=validation,
                    expected_type="method"
                )
            
            validation = ValidationResult(
                status=ValidationStatus.NOT_FOUND,
                confidence=0.2,
                message=f"'{attr_access.attribute_name}' not found on class '{class_type}'"
            )
            return AttributeValidation(
                attribute_access=attr_access,
                validation=validation
            )
        
        validation = ValidationResult(
            status=ValidationStatus.VALID,
            confidence=0.8,
            message=f"Attribute '{attr_access.attribute_name}' found on class '{class_type}'"
        )
        
        return AttributeValidation(
            attribute_access=attr_access,
            validation=validation,
            expected_type=attr_info.get('type')
        )
    
    async def _validate_function_calls(self, function_calls: List[FunctionCall]) -> List[FunctionValidation]:
        """Validate function calls"""
        validations = []
        
        for func_call in function_calls:
            validation = await self._validate_single_function_call(func_call)
            validations.append(validation)
        
        return validations
    
    async def _validate_single_function_call(self, func_call: FunctionCall) -> FunctionValidation:
        """Validate a single function call"""
        func_name = func_call.full_name or func_call.function_name
        
        # Skip validation for functions not from knowledge graph
        if func_call.full_name and not self._is_from_knowledge_graph(func_call.full_name):
            validation = ValidationResult(
                status=ValidationStatus.UNCERTAIN,
                confidence=0.8,
                message=f"Skipping validation: '{func_name}' is not from knowledge graph"
            )
            return FunctionValidation(
                function_call=func_call,
                validation=validation
            )
        
        # Find function in knowledge graph
        func_info = await self._find_function(func_name)
        
        if not func_info:
            validation = ValidationResult(
                status=ValidationStatus.NOT_FOUND,
                confidence=0.2,
                message=f"Function '{func_name}' not found in knowledge graph"
            )
            return FunctionValidation(
                function_call=func_call,
                validation=validation
            )
        
        # Validate parameters
        expected_params = func_info.get('params_list', [])
        param_validation = self._validate_parameters(
            expected_params=expected_params,
            provided_args=func_call.args,
            provided_kwargs=func_call.kwargs
        )
        
        # Use parameter validation result if it failed
        if param_validation.status == ValidationStatus.INVALID:
            validation = ValidationResult(
                status=ValidationStatus.INVALID,
                confidence=param_validation.confidence,
                message=f"Function '{func_name}' found but has invalid parameters: {param_validation.message}",
                suggestions=param_validation.suggestions
            )
        else:
            validation = ValidationResult(
                status=ValidationStatus.VALID,
                confidence=0.8,
                message=f"Function '{func_name}' found in knowledge graph"
            )
        
        return FunctionValidation(
            function_call=func_call,
            validation=validation,
            expected_params=expected_params,
            actual_params=func_call.args + list(func_call.kwargs.keys()),
            parameter_validation=param_validation
        )
    
    def _validate_parameters(self, expected_params: List[str], provided_args: List[str], 
                           provided_kwargs: Dict[str, str]) -> ValidationResult:
        """Validate function/method parameters with comprehensive support"""
        if not expected_params:
            return ValidationResult(
                status=ValidationStatus.UNCERTAIN,
                confidence=0.5,
                message="Parameter information not available"
            )
        
        # Parse expected parameters - handle detailed format
        required_positional = []
        optional_positional = []
        keyword_only_required = []
        keyword_only_optional = []
        has_varargs = False
        has_varkwargs = False
        
        for param in expected_params:
            # Handle detailed format: "[keyword_only] name:type=default" or "name:type"
            param_clean = param.strip()
            
            # Check for parameter kind prefix
            kind = 'positional'
            if param_clean.startswith('['):
                end_bracket = param_clean.find(']')
                if end_bracket > 0:
                    kind = param_clean[1:end_bracket]
                    param_clean = param_clean[end_bracket+1:].strip()
            
            # Check for varargs/varkwargs
            if param_clean.startswith('*') and not param_clean.startswith('**'):
                has_varargs = True
                continue
            elif param_clean.startswith('**'):
                has_varkwargs = True
                continue
            
            # Parse name and check if optional
            if ':' in param_clean:
                param_name = param_clean.split(':')[0]
                is_optional = '=' in param_clean
                
                if kind == 'keyword_only':
                    if is_optional:
                        keyword_only_optional.append(param_name)
                    else:
                        keyword_only_required.append(param_name)
                else:  # positional
                    if is_optional:
                        optional_positional.append(param_name)
                    else:
                        required_positional.append(param_name)
        
        # Count provided parameters
        provided_positional_count = len(provided_args)
        provided_keyword_names = set(provided_kwargs.keys())
        
        # Validate positional arguments
        min_required_positional = len(required_positional)
        max_allowed_positional = len(required_positional) + len(optional_positional)
        
        if not has_varargs and provided_positional_count > max_allowed_positional:
            return ValidationResult(
                status=ValidationStatus.INVALID,
                confidence=0.8,
                message=f"Too many positional arguments: provided {provided_positional_count}, max allowed {max_allowed_positional}"
            )
        
        if provided_positional_count < min_required_positional:
            return ValidationResult(
                status=ValidationStatus.INVALID,
                confidence=0.8,
                message=f"Too few positional arguments: provided {provided_positional_count}, required {min_required_positional}"
            )
        
        # Validate keyword arguments
        all_valid_kwarg_names = set(required_positional + optional_positional + keyword_only_required + keyword_only_optional)
        invalid_kwargs = provided_keyword_names - all_valid_kwarg_names
        
        if invalid_kwargs and not has_varkwargs:
            return ValidationResult(
                status=ValidationStatus.INVALID,
                confidence=0.7,
                message=f"Invalid keyword arguments: {list(invalid_kwargs)}",
                suggestions=[f"Valid parameters: {list(all_valid_kwarg_names)}"]
            )
        
        # Check required keyword-only arguments
        missing_required_kwargs = set(keyword_only_required) - provided_keyword_names
        if missing_required_kwargs:
            return ValidationResult(
                status=ValidationStatus.INVALID,
                confidence=0.8,
                message=f"Missing required keyword arguments: {list(missing_required_kwargs)}"
            )
        
        return ValidationResult(
            status=ValidationStatus.VALID,
            confidence=0.9,
            message="Parameters are valid"
        )
    
    # Neo4j Query Methods
    
    async def _find_modules(self, module_name: str) -> List[str]:
        """Find repository matching the module name, then return its files"""
        async with self.driver.session() as session:
            # First, try to find files with module names that match or start with the search term
            module_query = """
            MATCH (r:Repository)-[:CONTAINS]->(f:File)
            WHERE f.module_name = $module_name 
               OR f.module_name STARTS WITH $module_name + '.'
               OR split(f.module_name, '.')[0] = $module_name
            RETURN DISTINCT r.name as repo_name, count(f) as file_count
            ORDER BY file_count DESC
            LIMIT 5
            """
            
            result = await session.run(module_query, module_name=module_name)
            repos_from_modules = []
            async for record in result:
                repos_from_modules.append(record['repo_name'])
            
            # Also try repository name matching as fallback
            repo_query = """
            MATCH (r:Repository)
            WHERE toLower(r.name) = toLower($module_name)
               OR toLower(replace(r.name, '-', '_')) = toLower($module_name)
               OR toLower(replace(r.name, '_', '-')) = toLower($module_name)
            RETURN r.name as repo_name
            ORDER BY 
                CASE 
                    WHEN toLower(r.name) = toLower($module_name) THEN 1
                    WHEN toLower(replace(r.name, '-', '_')) = toLower($module_name) THEN 2
                    WHEN toLower(replace(r.name, '_', '-')) = toLower($module_name) THEN 3
                END
            LIMIT 5
            """
            
            result = await session.run(repo_query, module_name=module_name)
            repos_from_names = []
            async for record in result:
                repos_from_names.append(record['repo_name'])
            
            # Combine results, prioritizing module-based matches
            all_repos = repos_from_modules + [r for r in repos_from_names if r not in repos_from_modules]
            
            if not all_repos:
                return []
            
            # Get files from the best matching repository
            best_repo = all_repos[0]
            files_query = """
            MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)
            RETURN f.path, f.module_name
            LIMIT 50
            """
            
            result = await session.run(files_query, repo_name=best_repo)
            files = []
            async for record in result:
                files.append(record['f.path'])
            
            return files
    
    async def _get_module_contents(self, module_name: str) -> Tuple[List[str], List[str]]:
        """Get classes and functions available in a repository matching the module name"""
        async with self.driver.session() as session:
            # First, try to find repository by module names in files
            module_query = """
            MATCH (r:Repository)-[:CONTAINS]->(f:File)
            WHERE f.module_name = $module_name 
               OR f.module_name STARTS WITH $module_name + '.'
               OR split(f.module_name, '.')[0] = $module_name
            RETURN DISTINCT r.name as repo_name, count(f) as file_count
            ORDER BY file_count DESC
            LIMIT 1
            """
            
            result = await session.run(module_query, module_name=module_name)
            record = await result.single()
            
            if record:
                repo_name = record['repo_name']
            else:
                # Fallback to repository name matching
                repo_query = """
                MATCH (r:Repository)
                WHERE toLower(r.name) = toLower($module_name)
                   OR toLower(replace(r.name, '-', '_')) = toLower($module_name)
                   OR toLower(replace(r.name, '_', '-')) = toLower($module_name)
                RETURN r.name as repo_name
                ORDER BY 
                    CASE 
                        WHEN toLower(r.name) = toLower($module_name) THEN 1
                        WHEN toLower(replace(r.name, '-', '_')) = toLower($module_name) THEN 2
                        WHEN toLower(replace(r.name, '_', '-')) = toLower($module_name) THEN 3
                    END
                LIMIT 1
                """
                
                result = await session.run(repo_query, module_name=module_name)
                record = await result.single()
                
                if not record:
                    return [], []
                
                repo_name = record['repo_name']
            
            # Get classes from this repository
            class_query = """
            MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)
            RETURN DISTINCT c.name as class_name
            """
            
            result = await session.run(class_query, repo_name=repo_name)
            classes = []
            async for record in result:
                classes.append(record['class_name'])
            
            # Get functions from this repository
            func_query = """
            MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(func:Function)
            RETURN DISTINCT func.name as function_name
            """
            
            result = await session.run(func_query, repo_name=repo_name)
            functions = []
            async for record in result:
                functions.append(record['function_name'])
            
            return classes, functions
    
    async def _find_repository_for_module(self, module_name: str) -> Optional[str]:
        """Find the repository name that matches a module name"""
        if module_name in self.repo_cache:
            return self.repo_cache[module_name]
        
        async with self.driver.session() as session:
            # First, try to find repository by module names in files
            module_query = """
            MATCH (r:Repository)-[:CONTAINS]->(f:File)
            WHERE f.module_name = $module_name 
               OR f.module_name STARTS WITH $module_name + '.'
               OR split(f.module_name, '.')[0] = $module_name
            RETURN DISTINCT r.name as repo_name, count(f) as file_count
            ORDER BY file_count DESC
            LIMIT 1
            """
            
            result = await session.run(module_query, module_name=module_name)
            record = await result.single()
            
            if record:
                repo_name = record['repo_name']
            else:
                # Fallback to repository name matching
                query = """
                MATCH (r:Repository)
                WHERE toLower(r.name) = toLower($module_name)
                   OR toLower(replace(r.name, '-', '_')) = toLower($module_name)
                   OR toLower(replace(r.name, '_', '-')) = toLower($module_name)
                   OR toLower(r.name) CONTAINS toLower($module_name)
                   OR toLower($module_name) CONTAINS toLower(replace(r.name, '-', '_'))
                RETURN r.name as repo_name
                ORDER BY 
                    CASE 
                        WHEN toLower(r.name) = toLower($module_name) THEN 1
                        WHEN toLower(replace(r.name, '-', '_')) = toLower($module_name) THEN 2
                        ELSE 3
                    END
                LIMIT 1
                """
                
                result = await session.run(query, module_name=module_name)
                record = await result.single()
                
                repo_name = record['repo_name'] if record else None
            
            self.repo_cache[module_name] = repo_name
            return repo_name
    
    async def _find_class(self, class_name: str) -> Optional[Dict[str, Any]]:
        """Find class information in knowledge graph"""
        async with self.driver.session() as session:
            # First try exact match
            query = """
            MATCH (c:Class)
            WHERE c.name = $class_name OR c.full_name = $class_name
            RETURN c.name as name, c.full_name as full_name
            LIMIT 1
            """
            
            result = await session.run(query, class_name=class_name)
            record = await result.single()
            
            if record:
                return {
                    'name': record['name'],
                    'full_name': record['full_name']
                }
            
            # If no exact match and class_name has dots, try repository-based search
            if '.' in class_name:
                parts = class_name.split('.')
                module_part = '.'.join(parts[:-1])  # e.g., "pydantic_ai"
                class_part = parts[-1]  # e.g., "Agent"
                
                # Find repository for the module
                repo_name = await self._find_repository_for_module(module_part)
                
                if repo_name:
                    # Search for class within this repository
                    repo_query = """
                    MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)
                    WHERE c.name = $class_name
                    RETURN c.name as name, c.full_name as full_name
                    LIMIT 1
                    """
                    
                    result = await session.run(repo_query, repo_name=repo_name, class_name=class_part)
                    record = await result.single()
                    
                    if record:
                        return {
                            'name': record['name'],
                            'full_name': record['full_name']
                        }
            
            return None
    
    async def _find_method(self, class_name: str, method_name: str) -> Optional[Dict[str, Any]]:
        """Find method information for a class"""
        cache_key = f"{class_name}.{method_name}"
        if cache_key in self.method_cache:
            methods = self.method_cache[cache_key]
            return methods[0] if methods else None
        
        async with self.driver.session() as session:
            # First try exact match
            query = """
            MATCH (c:Class)-[:HAS_METHOD]->(m:Method)
            WHERE (c.name = $class_name OR c.full_name = $class_name)
              AND m.name = $method_name
            RETURN m.name as name, m.params_list as params_list, m.params_detailed as params_detailed, 
                   m.return_type as return_type, m.args as args
            LIMIT 1
            """
            
            result = await session.run(query, class_name=class_name, method_name=method_name)
            record = await result.single()
            
            if record:
                # Use detailed params if available, fall back to simple params
                params_to_use = record['params_detailed'] or record['params_list'] or []
                
                method_info = {
                    'name': record['name'],
                    'params_list': params_to_use,
                    'return_type': record['return_type'],
                    'args': record['args'] or []
                }
                self.method_cache[cache_key] = [method_info]
                return method_info
            
            # If no exact match and class_name has dots, try repository-based search
            if '.' in class_name:
                parts = class_name.split('.')
                module_part = '.'.join(parts[:-1])  # e.g., "pydantic_ai"
                class_part = parts[-1]  # e.g., "Agent"
                
                # Find repository for the module
                repo_name = await self._find_repository_for_module(module_part)
                
                if repo_name:
                    # Search for method within this repository's classes
                    repo_query = """
                    MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)-[:HAS_METHOD]->(m:Method)
                    WHERE c.name = $class_name AND m.name = $method_name
                    RETURN m.name as name, m.params_list as params_list, m.params_detailed as params_detailed,
                           m.return_type as return_type, m.args as args
                    LIMIT 1
                    """
                    
                    result = await session.run(repo_query, repo_name=repo_name, class_name=class_part, method_name=method_name)
                    record = await result.single()
                    
                    if record:
                        # Use detailed params if available, fall back to simple params
                        params_to_use = record['params_detailed'] or record['params_list'] or []
                        
                        method_info = {
                            'name': record['name'],
                            'params_list': params_to_use,
                            'return_type': record['return_type'],
                            'args': record['args'] or []
                        }
                        self.method_cache[cache_key] = [method_info]
                        return method_info
            
            self.method_cache[cache_key] = []
            return None
    
    async def _find_attribute(self, class_name: str, attr_name: str) -> Optional[Dict[str, Any]]:
        """Find attribute information for a class"""
        async with self.driver.session() as session:
            # First try exact match
            query = """
            MATCH (c:Class)-[:HAS_ATTRIBUTE]->(a:Attribute)
            WHERE (c.name = $class_name OR c.full_name = $class_name)
              AND a.name = $attr_name
            RETURN a.name as name, a.type as type
            LIMIT 1
            """
            
            result = await session.run(query, class_name=class_name, attr_name=attr_name)
            record = await result.single()
            
            if record:
                return {
                    'name': record['name'],
                    'type': record['type']
                }
            
            # If no exact match and class_name has dots, try repository-based search
            if '.' in class_name:
                parts = class_name.split('.')
                module_part = '.'.join(parts[:-1])  # e.g., "pydantic_ai"
                class_part = parts[-1]  # e.g., "Agent"
                
                # Find repository for the module
                repo_name = await self._find_repository_for_module(module_part)
                
                if repo_name:
                    # Search for attribute within this repository's classes
                    repo_query = """
                    MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)-[:HAS_ATTRIBUTE]->(a:Attribute)
                    WHERE c.name = $class_name AND a.name = $attr_name
                    RETURN a.name as name, a.type as type
                    LIMIT 1
                    """
                    
                    result = await session.run(repo_query, repo_name=repo_name, class_name=class_part, attr_name=attr_name)
                    record = await result.single()
                    
                    if record:
                        return {
                            'name': record['name'],
                            'type': record['type']
                        }
            
            return None
    
    async def _find_function(self, func_name: str) -> Optional[Dict[str, Any]]:
        """Find function information"""
        async with self.driver.session() as session:
            # First try exact match
            query = """
            MATCH (f:Function)
            WHERE f.name = $func_name OR f.full_name = $func_name
            RETURN f.name as name, f.params_list as params_list, f.params_detailed as params_detailed,
                   f.return_type as return_type, f.args as args
            LIMIT 1
            """
            
            result = await session.run(query, func_name=func_name)
            record = await result.single()
            
            if record:
                # Use detailed params if available, fall back to simple params
                params_to_use = record['params_detailed'] or record['params_list'] or []
                
                return {
                    'name': record['name'],
                    'params_list': params_to_use,
                    'return_type': record['return_type'],
                    'args': record['args'] or []
                }
            
            # If no exact match and func_name has dots, try repository-based search
            if '.' in func_name:
                parts = func_name.split('.')
                module_part = '.'.join(parts[:-1])  # e.g., "pydantic_ai"
                func_part = parts[-1]  # e.g., "some_function"
                
                # Find repository for the module
                repo_name = await self._find_repository_for_module(module_part)
                
                if repo_name:
                    # Search for function within this repository
                    repo_query = """
                    MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(func:Function)
                    WHERE func.name = $func_name
                    RETURN func.name as name, func.params_list as params_list, func.params_detailed as params_detailed,
                           func.return_type as return_type, func.args as args
                    LIMIT 1
                    """
                    
                    result = await session.run(repo_query, repo_name=repo_name, func_name=func_part)
                    record = await result.single()
                    
                    if record:
                        # Use detailed params if available, fall back to simple params
                        params_to_use = record['params_detailed'] or record['params_list'] or []
                        
                        return {
                            'name': record['name'],
                            'params_list': params_to_use,
                            'return_type': record['return_type'],
                            'args': record['args'] or []
                        }
            
            return None
    
    async def _find_pydantic_ai_result_method(self, method_name: str) -> Optional[Dict[str, Any]]:
        """Find method information for pydantic_ai result objects"""
        # Look for methods on pydantic_ai classes that could be result objects
        async with self.driver.session() as session:
            # Search for common result methods in pydantic_ai repository
            query = """
            MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)-[:HAS_METHOD]->(m:Method)
            WHERE m.name = $method_name 
              AND (c.name CONTAINS 'Result' OR c.name CONTAINS 'Stream' OR c.name CONTAINS 'Run')
            RETURN m.name as name, m.params_list as params_list, m.params_detailed as params_detailed,
                   m.return_type as return_type, m.args as args, c.name as class_name
            LIMIT 1
            """
            
            result = await session.run(query, repo_name="pydantic_ai", method_name=method_name)
            record = await result.single()
            
            if record:
                # Use detailed params if available, fall back to simple params
                params_to_use = record['params_detailed'] or record['params_list'] or []
                
                return {
                    'name': record['name'],
                    'params_list': params_to_use,
                    'return_type': record['return_type'],
                    'args': record['args'] or [],
                    'source_class': record['class_name']
                }
            
            return None
    
    async def _find_similar_modules(self, module_name: str) -> List[str]:
        """Find similar repository names for suggestions"""
        async with self.driver.session() as session:
            query = """
            MATCH (r:Repository)
            WHERE toLower(r.name) CONTAINS toLower($partial_name)
               OR toLower(replace(r.name, '-', '_')) CONTAINS toLower($partial_name)
               OR toLower(replace(r.name, '_', '-')) CONTAINS toLower($partial_name)
            RETURN r.name
            LIMIT 5
            """
            
            result = await session.run(query, partial_name=module_name[:3])
            suggestions = []
            async for record in result:
                suggestions.append(record['name'])
            
            return suggestions
    
    async def _find_similar_methods(self, class_name: str, method_name: str) -> List[str]:
        """Find similar method names for suggestions"""
        async with self.driver.session() as session:
            # First try exact class match
            query = """
            MATCH (c:Class)-[:HAS_METHOD]->(m:Method)
            WHERE (c.name = $class_name OR c.full_name = $class_name)
              AND m.name CONTAINS $partial_name
            RETURN m.name as name
            LIMIT 5
            """
            
            result = await session.run(query, class_name=class_name, partial_name=method_name[:3])
            suggestions = []
            async for record in result:
                suggestions.append(record['name'])
            
            # If no suggestions and class_name has dots, try repository-based search
            if not suggestions and '.' in class_name:
                parts = class_name.split('.')
                module_part = '.'.join(parts[:-1])  # e.g., "pydantic_ai"
                class_part = parts[-1]  # e.g., "Agent"
                
                # Find repository for the module
                repo_name = await self._find_repository_for_module(module_part)
                
                if repo_name:
                    repo_query = """
                    MATCH (r:Repository {name: $repo_name})-[:CONTAINS]->(f:File)-[:DEFINES]->(c:Class)-[:HAS_METHOD]->(m:Method)
                    WHERE c.name = $class_name AND m.name CONTAINS $partial_name
                    RETURN m.name as name
                    LIMIT 5
                    """
                    
                    result = await session.run(repo_query, repo_name=repo_name, class_name=class_part, partial_name=method_name[:3])
                    async for record in result:
                        suggestions.append(record['name'])
            
            return suggestions
    
    def _calculate_overall_confidence(self, result: ScriptValidationResult) -> float:
        """Calculate overall confidence score for the validation (knowledge graph items only)"""
        kg_validations = []
        
        # Only count validations from knowledge graph imports
        for val in result.import_validations:
            if val.validation.details.get('in_knowledge_graph', False):
                kg_validations.append(val.validation.confidence)
        
        # Only count validations from knowledge graph classes
        for val in result.class_validations:
            class_name = val.class_instantiation.full_class_name or val.class_instantiation.class_name
            if self._is_from_knowledge_graph(class_name):
                kg_validations.append(val.validation.confidence)
        
        # Only count validations from knowledge graph methods
        for val in result.method_validations:
            if val.method_call.object_type and self._is_from_knowledge_graph(val.method_call.object_type):
                kg_validations.append(val.validation.confidence)
        
        # Only count validations from knowledge graph attributes
        for val in result.attribute_validations:
            if val.attribute_access.object_type and self._is_from_knowledge_graph(val.attribute_access.object_type):
                kg_validations.append(val.validation.confidence)
        
        # Only count validations from knowledge graph functions
        for val in result.function_validations:
            if val.function_call.full_name and self._is_from_knowledge_graph(val.function_call.full_name):
                kg_validations.append(val.validation.confidence)
        
        if not kg_validations:
            return 1.0  # No knowledge graph items to validate = perfect confidence
        
        return sum(kg_validations) / len(kg_validations)
    
    def _is_from_knowledge_graph(self, class_type: str) -> bool:
        """Check if a class type comes from a module in the knowledge graph"""
        if not class_type:
            return False
        
        # For dotted names like "pydantic_ai.Agent" or "pydantic_ai.StreamedRunResult", check the base module
        if '.' in class_type:
            base_module = class_type.split('.')[0]
            # Exact match only - "pydantic" should not match "pydantic_ai"
            return base_module in self.knowledge_graph_modules
        
        # For simple names, check if any knowledge graph module matches exactly
        # Don't use substring matching to avoid "pydantic" matching "pydantic_ai"
        return class_type in self.knowledge_graph_modules
    
    def _detect_hallucinations(self, result: ScriptValidationResult) -> List[Dict[str, Any]]:
        """Detect and categorize hallucinations"""
        hallucinations = []
        reported_items = set()  # Track reported items to avoid duplicates
        
        # Check method calls (only for knowledge graph classes)
        for val in result.method_validations:
            if (val.validation.status == ValidationStatus.NOT_FOUND and 
                val.method_call.object_type and 
                self._is_from_knowledge_graph(val.method_call.object_type)):
                
                # Create unique key to avoid duplicates
                key = (val.method_call.line_number, val.method_call.method_name, val.method_call.object_type)
                if key not in reported_items:
                    reported_items.add(key)
                    hallucinations.append({
                        'type': 'METHOD_NOT_FOUND',
                        'location': f"line {val.method_call.line_number}",
                        'description': f"Method '{val.method_call.method_name}' not found on class '{val.method_call.object_type}'",
                        'suggestion': val.validation.suggestions[0] if val.validation.suggestions else None
                    })
        
        # Check attributes (only for knowledge graph classes) - but skip if already reported as method
        for val in result.attribute_validations:
            if (val.validation.status == ValidationStatus.NOT_FOUND and 
                val.attribute_access.object_type and 
                self._is_from_knowledge_graph(val.attribute_access.object_type)):
                
                # Create unique key - if this was already reported as a method, skip it
                key = (val.attribute_access.line_number, val.attribute_access.attribute_name, val.attribute_access.object_type)
                if key not in reported_items:
                    reported_items.add(key)
                    hallucinations.append({
                        'type': 'ATTRIBUTE_NOT_FOUND',
                        'location': f"line {val.attribute_access.line_number}",
                        'description': f"Attribute '{val.attribute_access.attribute_name}' not found on class '{val.attribute_access.object_type}'"
                    })
        
        # Check parameter issues (only for knowledge graph methods)
        for val in result.method_validations:
            if (val.parameter_validation and 
                val.parameter_validation.status == ValidationStatus.INVALID and
                val.method_call.object_type and 
                self._is_from_knowledge_graph(val.method_call.object_type)):
                hallucinations.append({
                    'type': 'INVALID_PARAMETERS',
                    'location': f"line {val.method_call.line_number}",
                    'description': f"Invalid parameters for method '{val.method_call.method_name}': {val.parameter_validation.message}"
                })
        
        return hallucinations