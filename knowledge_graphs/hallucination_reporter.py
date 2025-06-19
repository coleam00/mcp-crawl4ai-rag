"""
Hallucination Reporter

Generates comprehensive reports about AI coding assistant hallucinations
detected in Python scripts. Supports multiple output formats.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

from knowledge_graph_validator import (
    ScriptValidationResult, ValidationStatus, ValidationResult
)

logger = logging.getLogger(__name__)


class HallucinationReporter:
    """Generates reports about detected hallucinations"""
    
    def __init__(self):
        self.report_timestamp = datetime.now(timezone.utc)
    
    def generate_comprehensive_report(self, validation_result: ScriptValidationResult) -> Dict[str, Any]:
        """Generate a comprehensive report in JSON format"""
        
        # Categorize validations by status (knowledge graph items only)
        valid_items = []
        invalid_items = []
        uncertain_items = []
        not_found_items = []
        
        # Process imports (only knowledge graph ones)
        for val in validation_result.import_validations:
            if not val.validation.details.get('in_knowledge_graph', False):
                continue  # Skip external libraries
            item = {
                'type': 'IMPORT',
                'name': val.import_info.module,
                'line': val.import_info.line_number,
                'status': val.validation.status.value,
                'confidence': val.validation.confidence,
                'message': val.validation.message,
                'details': {
                    'is_from_import': val.import_info.is_from_import,
                    'alias': val.import_info.alias,
                    'available_classes': val.available_classes,
                    'available_functions': val.available_functions
                }
            }
            self._categorize_item(item, val.validation.status, valid_items, invalid_items, uncertain_items, not_found_items)
        
        # Process classes (only knowledge graph ones)
        for val in validation_result.class_validations:
            class_name = val.class_instantiation.full_class_name or val.class_instantiation.class_name
            if not self._is_from_knowledge_graph(class_name, validation_result):
                continue  # Skip external classes
            item = {
                'type': 'CLASS_INSTANTIATION',
                'name': val.class_instantiation.class_name,
                'full_name': val.class_instantiation.full_class_name,
                'variable': val.class_instantiation.variable_name,
                'line': val.class_instantiation.line_number,
                'status': val.validation.status.value,
                'confidence': val.validation.confidence,
                'message': val.validation.message,
                'details': {
                    'args_provided': val.class_instantiation.args,
                    'kwargs_provided': list(val.class_instantiation.kwargs.keys()),
                    'constructor_params': val.constructor_params,
                    'parameter_validation': self._serialize_validation_result(val.parameter_validation) if val.parameter_validation else None
                }
            }
            self._categorize_item(item, val.validation.status, valid_items, invalid_items, uncertain_items, not_found_items)
        
        # Track reported items to avoid duplicates
        reported_items = set()
        
        # Process methods (only knowledge graph ones)
        for val in validation_result.method_validations:
            if not (val.method_call.object_type and self._is_from_knowledge_graph(val.method_call.object_type, validation_result)):
                continue  # Skip external methods
            
            # Create unique key to avoid duplicates
            key = (val.method_call.line_number, val.method_call.method_name, val.method_call.object_type)
            if key not in reported_items:
                reported_items.add(key)
                item = {
                    'type': 'METHOD_CALL',
                    'name': val.method_call.method_name,
                    'object': val.method_call.object_name,
                    'object_type': val.method_call.object_type,
                    'line': val.method_call.line_number,
                    'status': val.validation.status.value,
                    'confidence': val.validation.confidence,
                    'message': val.validation.message,
                    'details': {
                        'args_provided': val.method_call.args,
                        'kwargs_provided': list(val.method_call.kwargs.keys()),
                        'expected_params': val.expected_params,
                        'parameter_validation': self._serialize_validation_result(val.parameter_validation) if val.parameter_validation else None,
                        'suggestions': val.validation.suggestions
                    }
                }
                self._categorize_item(item, val.validation.status, valid_items, invalid_items, uncertain_items, not_found_items)
        
        # Process attributes (only knowledge graph ones) - but skip if already reported as method
        for val in validation_result.attribute_validations:
            if not (val.attribute_access.object_type and self._is_from_knowledge_graph(val.attribute_access.object_type, validation_result)):
                continue  # Skip external attributes
            
            # Create unique key - if this was already reported as a method, skip it
            key = (val.attribute_access.line_number, val.attribute_access.attribute_name, val.attribute_access.object_type)
            if key not in reported_items:
                reported_items.add(key)
                item = {
                    'type': 'ATTRIBUTE_ACCESS',
                    'name': val.attribute_access.attribute_name,
                    'object': val.attribute_access.object_name,
                    'object_type': val.attribute_access.object_type,
                    'line': val.attribute_access.line_number,
                    'status': val.validation.status.value,
                    'confidence': val.validation.confidence,
                    'message': val.validation.message,
                    'details': {
                        'expected_type': val.expected_type
                    }
                }
                self._categorize_item(item, val.validation.status, valid_items, invalid_items, uncertain_items, not_found_items)
        
        # Process functions (only knowledge graph ones)
        for val in validation_result.function_validations:
            if not (val.function_call.full_name and self._is_from_knowledge_graph(val.function_call.full_name, validation_result)):
                continue  # Skip external functions
            item = {
                'type': 'FUNCTION_CALL',
                'name': val.function_call.function_name,
                'full_name': val.function_call.full_name,
                'line': val.function_call.line_number,
                'status': val.validation.status.value,
                'confidence': val.validation.confidence,
                'message': val.validation.message,
                'details': {
                    'args_provided': val.function_call.args,
                    'kwargs_provided': list(val.function_call.kwargs.keys()),
                    'expected_params': val.expected_params,
                    'parameter_validation': self._serialize_validation_result(val.parameter_validation) if val.parameter_validation else None
                }
            }
            self._categorize_item(item, val.validation.status, valid_items, invalid_items, uncertain_items, not_found_items)
        
        # Create library summary
        library_summary = self._create_library_summary(validation_result)
        
        # Generate report
        report = {
            'analysis_metadata': {
                'script_path': validation_result.script_path,
                'analysis_timestamp': self.report_timestamp.isoformat(),
                'total_imports': len(validation_result.import_validations),
                'total_classes': len(validation_result.class_validations),
                'total_methods': len(validation_result.method_validations),
                'total_attributes': len(validation_result.attribute_validations),
                'total_functions': len(validation_result.function_validations)
            },
            'validation_summary': {
                'overall_confidence': validation_result.overall_confidence,
                'total_validations': len(valid_items) + len(invalid_items) + len(uncertain_items) + len(not_found_items),
                'valid_count': len(valid_items),
                'invalid_count': len(invalid_items),
                'uncertain_count': len(uncertain_items),
                'not_found_count': len(not_found_items),
                'hallucination_rate': len(invalid_items + not_found_items) / max(1, len(valid_items) + len(invalid_items) + len(not_found_items))
            },
            'libraries_analyzed': library_summary,
            'validation_details': {
                'valid_items': valid_items,
                'invalid_items': invalid_items,
                'uncertain_items': uncertain_items,
                'not_found_items': not_found_items
            },
            'hallucinations_detected': validation_result.hallucinations_detected,
            'recommendations': self._generate_recommendations(validation_result)
        }
        
        return report
    
    def _is_from_knowledge_graph(self, item_name: str, validation_result) -> bool:
        """Check if an item is from a knowledge graph module"""
        if not item_name:
            return False
        
        # Get knowledge graph modules from import validations
        kg_modules = set()
        for val in validation_result.import_validations:
            if val.validation.details.get('in_knowledge_graph', False):
                kg_modules.add(val.import_info.module)
                if '.' in val.import_info.module:
                    kg_modules.add(val.import_info.module.split('.')[0])
        
        # Check if the item belongs to any knowledge graph module
        if '.' in item_name:
            base_module = item_name.split('.')[0]
            return base_module in kg_modules
        
        return any(item_name in module or module.endswith(item_name) for module in kg_modules)
    
    def _serialize_validation_result(self, validation_result) -> Dict[str, Any]:
        """Convert ValidationResult to JSON-serializable dictionary"""
        if validation_result is None:
            return None
        
        return {
            'status': validation_result.status.value,
            'confidence': validation_result.confidence,
            'message': validation_result.message,
            'details': validation_result.details,
            'suggestions': validation_result.suggestions
        }
    
    def _categorize_item(self, item: Dict[str, Any], status: ValidationStatus, 
                        valid_items: List, invalid_items: List, uncertain_items: List, not_found_items: List):
        """Categorize validation item by status"""
        if status == ValidationStatus.VALID:
            valid_items.append(item)
        elif status == ValidationStatus.INVALID:
            invalid_items.append(item)
        elif status == ValidationStatus.UNCERTAIN:
            uncertain_items.append(item)
        elif status == ValidationStatus.NOT_FOUND:
            not_found_items.append(item)
    
    def _create_library_summary(self, validation_result: ScriptValidationResult) -> List[Dict[str, Any]]:
        """Create summary of libraries analyzed"""
        library_stats = {}
        
        # Aggregate stats by library/module
        for val in validation_result.import_validations:
            module = val.import_info.module
            if module not in library_stats:
                library_stats[module] = {
                    'module_name': module,
                    'import_status': val.validation.status.value,
                    'import_confidence': val.validation.confidence,
                    'classes_used': [],
                    'methods_called': [],
                    'attributes_accessed': [],
                    'functions_called': []
                }
        
        # Add class usage
        for val in validation_result.class_validations:
            class_name = val.class_instantiation.class_name
            full_name = val.class_instantiation.full_class_name
            
            # Try to match to library
            if full_name:
                parts = full_name.split('.')
                if len(parts) > 1:
                    module = '.'.join(parts[:-1])
                    if module in library_stats:
                        library_stats[module]['classes_used'].append({
                            'class_name': class_name,
                            'status': val.validation.status.value,
                            'confidence': val.validation.confidence
                        })
        
        # Add method usage
        for val in validation_result.method_validations:
            method_name = val.method_call.method_name
            object_type = val.method_call.object_type
            
            if object_type:
                parts = object_type.split('.')
                if len(parts) > 1:
                    module = '.'.join(parts[:-1])
                    if module in library_stats:
                        library_stats[module]['methods_called'].append({
                            'method_name': method_name,
                            'class_name': parts[-1],
                            'status': val.validation.status.value,
                            'confidence': val.validation.confidence
                        })
        
        # Add attribute usage
        for val in validation_result.attribute_validations:
            attr_name = val.attribute_access.attribute_name
            object_type = val.attribute_access.object_type
            
            if object_type:
                parts = object_type.split('.')
                if len(parts) > 1:
                    module = '.'.join(parts[:-1])
                    if module in library_stats:
                        library_stats[module]['attributes_accessed'].append({
                            'attribute_name': attr_name,
                            'class_name': parts[-1],
                            'status': val.validation.status.value,
                            'confidence': val.validation.confidence
                        })
        
        # Add function usage
        for val in validation_result.function_validations:
            func_name = val.function_call.function_name
            full_name = val.function_call.full_name
            
            if full_name:
                parts = full_name.split('.')
                if len(parts) > 1:
                    module = '.'.join(parts[:-1])
                    if module in library_stats:
                        library_stats[module]['functions_called'].append({
                            'function_name': func_name,
                            'status': val.validation.status.value,
                            'confidence': val.validation.confidence
                        })
        
        return list(library_stats.values())
    
    def _generate_recommendations(self, validation_result: ScriptValidationResult) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        # Only count actual hallucinations (from knowledge graph libraries)
        kg_hallucinations = [h for h in validation_result.hallucinations_detected]
        
        if kg_hallucinations:
            method_issues = [h for h in kg_hallucinations if h['type'] == 'METHOD_NOT_FOUND']
            attr_issues = [h for h in kg_hallucinations if h['type'] == 'ATTRIBUTE_NOT_FOUND']
            param_issues = [h for h in kg_hallucinations if h['type'] == 'INVALID_PARAMETERS']
            
            if method_issues:
                recommendations.append(
                    f"Found {len(method_issues)} non-existent methods in knowledge graph libraries. "
                    "Consider checking the official documentation for correct method names."
                )
            
            if attr_issues:
                recommendations.append(
                    f"Found {len(attr_issues)} non-existent attributes in knowledge graph libraries. "
                    "Verify attribute names against the class documentation."
                )
            
            if param_issues:
                recommendations.append(
                    f"Found {len(param_issues)} parameter mismatches in knowledge graph libraries. "
                    "Check function signatures for correct parameter names and types."
                )
        else:
            recommendations.append(
                "No hallucinations detected in knowledge graph libraries. "
                "External library usage appears to be working as expected."
            )
        
        if validation_result.overall_confidence < 0.7:
            recommendations.append(
                "Overall confidence is moderate. Most validations were for external libraries not in the knowledge graph."
            )
        
        return recommendations
    
    def save_json_report(self, report: Dict[str, Any], output_path: str):
        """Save report as JSON file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"JSON report saved to: {output_path}")
    
    def save_markdown_report(self, report: Dict[str, Any], output_path: str):
        """Save report as Markdown file"""
        md_content = self._generate_markdown_content(report)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"Markdown report saved to: {output_path}")
    
    def _generate_markdown_content(self, report: Dict[str, Any]) -> str:
        """Generate Markdown content from report"""
        md = []
        
        # Header
        md.append("# AI Hallucination Detection Report")
        md.append("")
        md.append(f"**Script:** `{report['analysis_metadata']['script_path']}`")
        md.append(f"**Analysis Date:** {report['analysis_metadata']['analysis_timestamp']}")
        md.append(f"**Overall Confidence:** {report['validation_summary']['overall_confidence']:.2%}")
        md.append("")
        
        # Summary
        summary = report['validation_summary']
        md.append("## Summary")
        md.append("")
        md.append(f"- **Total Validations:** {summary['total_validations']}")
        md.append(f"- **Valid:** {summary['valid_count']} ({summary['valid_count']/summary['total_validations']:.1%})")
        md.append(f"- **Invalid:** {summary['invalid_count']} ({summary['invalid_count']/summary['total_validations']:.1%})")
        md.append(f"- **Not Found:** {summary['not_found_count']} ({summary['not_found_count']/summary['total_validations']:.1%})")
        md.append(f"- **Uncertain:** {summary['uncertain_count']} ({summary['uncertain_count']/summary['total_validations']:.1%})")
        md.append(f"- **Hallucination Rate:** {summary['hallucination_rate']:.1%}")
        md.append("")
        
        # Hallucinations
        if report['hallucinations_detected']:
            md.append("## 🚨 Hallucinations Detected")
            md.append("")
            for i, hallucination in enumerate(report['hallucinations_detected'], 1):
                md.append(f"### {i}. {hallucination['type'].replace('_', ' ').title()}")
                md.append(f"**Location:** {hallucination['location']}")
                md.append(f"**Description:** {hallucination['description']}")
                if hallucination.get('suggestion'):
                    md.append(f"**Suggestion:** {hallucination['suggestion']}")
                md.append("")
        
        # Libraries
        if report['libraries_analyzed']:
            md.append("## 📚 Libraries Analyzed")
            md.append("")
            for lib in report['libraries_analyzed']:
                md.append(f"### {lib['module_name']}")
                md.append(f"**Import Status:** {lib['import_status']}")
                md.append(f"**Import Confidence:** {lib['import_confidence']:.2%}")
                
                if lib['classes_used']:
                    md.append("**Classes Used:**")
                    for cls in lib['classes_used']:
                        status_emoji = "✅" if cls['status'] == 'VALID' else "❌"
                        md.append(f"  - {status_emoji} `{cls['class_name']}` ({cls['confidence']:.1%})")
                
                if lib['methods_called']:
                    md.append("**Methods Called:**")
                    for method in lib['methods_called']:
                        status_emoji = "✅" if method['status'] == 'VALID' else "❌"
                        md.append(f"  - {status_emoji} `{method['class_name']}.{method['method_name']}()` ({method['confidence']:.1%})")
                
                if lib['attributes_accessed']:
                    md.append("**Attributes Accessed:**")
                    for attr in lib['attributes_accessed']:
                        status_emoji = "✅" if attr['status'] == 'VALID' else "❌"
                        md.append(f"  - {status_emoji} `{attr['class_name']}.{attr['attribute_name']}` ({attr['confidence']:.1%})")
                
                if lib['functions_called']:
                    md.append("**Functions Called:**")
                    for func in lib['functions_called']:
                        status_emoji = "✅" if func['status'] == 'VALID' else "❌"
                        md.append(f"  - {status_emoji} `{func['function_name']}()` ({func['confidence']:.1%})")
                
                md.append("")
        
        # Recommendations
        if report['recommendations']:
            md.append("## 💡 Recommendations")
            md.append("")
            for rec in report['recommendations']:
                md.append(f"- {rec}")
            md.append("")
        
        # Detailed Results
        md.append("## 📋 Detailed Validation Results")
        md.append("")
        
        # Invalid items
        invalid_items = report['validation_details']['invalid_items']
        if invalid_items:
            md.append("### ❌ Invalid Items")
            md.append("")
            for item in invalid_items:
                md.append(f"- **{item['type']}** `{item['name']}` (Line {item['line']}) - {item['message']}")
            md.append("")
        
        # Not found items
        not_found_items = report['validation_details']['not_found_items']
        if not_found_items:
            md.append("### 🔍 Not Found Items")
            md.append("")
            for item in not_found_items:
                md.append(f"- **{item['type']}** `{item['name']}` (Line {item['line']}) - {item['message']}")
            md.append("")
        
        # Valid items (sample)
        valid_items = report['validation_details']['valid_items']
        if valid_items:
            md.append("### ✅ Valid Items (Sample)")
            md.append("")
            for item in valid_items[:10]:  # Show first 10
                md.append(f"- **{item['type']}** `{item['name']}` (Line {item['line']}) - {item['message']}")
            if len(valid_items) > 10:
                md.append(f"- ... and {len(valid_items) - 10} more valid items")
            md.append("")
        
        return "\n".join(md)
    
    def print_summary(self, report: Dict[str, Any]):
        """Print a concise summary to console"""
        print("\n" + "="*80)
        print("🤖 AI HALLUCINATION DETECTION REPORT")
        print("="*80)
        
        print(f"Script: {report['analysis_metadata']['script_path']}")
        print(f"Overall Confidence: {report['validation_summary']['overall_confidence']:.1%}")
        
        summary = report['validation_summary']
        print(f"\nValidation Results:")
        print(f"  ✅ Valid: {summary['valid_count']}")
        print(f"  ❌ Invalid: {summary['invalid_count']}")
        print(f"  🔍 Not Found: {summary['not_found_count']}")
        print(f"  ❓ Uncertain: {summary['uncertain_count']}")
        print(f"  📊 Hallucination Rate: {summary['hallucination_rate']:.1%}")
        
        if report['hallucinations_detected']:
            print(f"\n🚨 {len(report['hallucinations_detected'])} Hallucinations Detected:")
            for hall in report['hallucinations_detected'][:5]:  # Show first 5
                print(f"  - {hall['type'].replace('_', ' ').title()} at {hall['location']}")
                print(f"    {hall['description']}")
        
        if report['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in report['recommendations'][:3]:  # Show first 3
                print(f"  - {rec}")
        
        print("="*80)