"""
AI Hallucination Detector

Main orchestrator for detecting AI coding assistant hallucinations in Python scripts.
Combines AST analysis, knowledge graph validation, and comprehensive reporting.
"""

import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv

from ai_script_analyzer import AIScriptAnalyzer, analyze_ai_script
from knowledge_graph_validator import KnowledgeGraphValidator
from hallucination_reporter import HallucinationReporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class AIHallucinationDetector:
    """Main detector class that orchestrates the entire process"""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.validator = KnowledgeGraphValidator(neo4j_uri, neo4j_user, neo4j_password)
        self.reporter = HallucinationReporter()
        self.analyzer = AIScriptAnalyzer()
    
    async def initialize(self):
        """Initialize connections and components"""
        await self.validator.initialize()
        logger.info("AI Hallucination Detector initialized successfully")
    
    async def close(self):
        """Close connections"""
        await self.validator.close()
    
    async def detect_hallucinations(self, script_path: str, 
                                  output_dir: Optional[str] = None,
                                  save_json: bool = True,
                                  save_markdown: bool = True,
                                  print_summary: bool = True) -> dict:
        """
        Main detection function that analyzes a script and generates reports
        
        Args:
            script_path: Path to the AI-generated Python script
            output_dir: Directory to save reports (defaults to script directory)
            save_json: Whether to save JSON report
            save_markdown: Whether to save Markdown report
            print_summary: Whether to print summary to console
        
        Returns:
            Complete validation report as dictionary
        """
        logger.info(f"Starting hallucination detection for: {script_path}")
        
        # Validate input
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Script not found: {script_path}")
        
        if not script_path.endswith('.py'):
            raise ValueError("Only Python (.py) files are supported")
        
        # Set output directory
        if output_dir is None:
            output_dir = str(Path(script_path).parent)
        
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # Step 1: Analyze the script using AST
            logger.info("Step 1: Analyzing script structure...")
            analysis_result = self.analyzer.analyze_script(script_path)
            
            if analysis_result.errors:
                logger.warning(f"Analysis warnings: {analysis_result.errors}")
            
            logger.info(f"Found: {len(analysis_result.imports)} imports, "
                       f"{len(analysis_result.class_instantiations)} class instantiations, "
                       f"{len(analysis_result.method_calls)} method calls, "
                       f"{len(analysis_result.function_calls)} function calls, "
                       f"{len(analysis_result.attribute_accesses)} attribute accesses")
            
            # Step 2: Validate against knowledge graph
            logger.info("Step 2: Validating against knowledge graph...")
            validation_result = await self.validator.validate_script(analysis_result)
            
            logger.info(f"Validation complete. Overall confidence: {validation_result.overall_confidence:.1%}")
            
            # Step 3: Generate comprehensive report
            logger.info("Step 3: Generating reports...")
            report = self.reporter.generate_comprehensive_report(validation_result)
            
            # Step 4: Save reports
            script_name = Path(script_path).stem
            
            if save_json:
                json_path = os.path.join(output_dir, f"{script_name}_hallucination_report.json")
                self.reporter.save_json_report(report, json_path)
            
            if save_markdown:
                md_path = os.path.join(output_dir, f"{script_name}_hallucination_report.md")
                self.reporter.save_markdown_report(report, md_path)
            
            # Step 5: Print summary
            if print_summary:
                self.reporter.print_summary(report)
            
            logger.info("Hallucination detection completed successfully")
            return report
            
        except Exception as e:
            logger.error(f"Error during hallucination detection: {str(e)}")
            raise
    
    async def batch_detect(self, script_paths: List[str], 
                          output_dir: Optional[str] = None) -> List[dict]:
        """
        Detect hallucinations in multiple scripts
        
        Args:
            script_paths: List of paths to Python scripts
            output_dir: Directory to save all reports
        
        Returns:
            List of validation reports
        """
        logger.info(f"Starting batch detection for {len(script_paths)} scripts")
        
        results = []
        for i, script_path in enumerate(script_paths, 1):
            logger.info(f"Processing script {i}/{len(script_paths)}: {script_path}")
            
            try:
                result = await self.detect_hallucinations(
                    script_path=script_path,
                    output_dir=output_dir,
                    print_summary=False  # Don't print individual summaries in batch mode
                )
                results.append(result)
                
            except Exception as e:
                logger.error(f"Failed to process {script_path}: {str(e)}")
                # Continue with other scripts
                continue
        
        # Print batch summary
        self._print_batch_summary(results)
        
        return results
    
    def _print_batch_summary(self, results: List[dict]):
        """Print summary of batch processing results"""
        if not results:
            print("No scripts were successfully processed.")
            return
        
        print("\n" + "="*80)
        print("🚀 BATCH HALLUCINATION DETECTION SUMMARY")
        print("="*80)
        
        total_scripts = len(results)
        total_validations = sum(r['validation_summary']['total_validations'] for r in results)
        total_valid = sum(r['validation_summary']['valid_count'] for r in results)
        total_invalid = sum(r['validation_summary']['invalid_count'] for r in results)
        total_not_found = sum(r['validation_summary']['not_found_count'] for r in results)
        total_hallucinations = sum(len(r['hallucinations_detected']) for r in results)
        
        avg_confidence = sum(r['validation_summary']['overall_confidence'] for r in results) / total_scripts
        
        print(f"Scripts Processed: {total_scripts}")
        print(f"Total Validations: {total_validations}")
        print(f"Average Confidence: {avg_confidence:.1%}")
        print(f"Total Hallucinations: {total_hallucinations}")
        
        print(f"\nAggregated Results:")
        print(f"  ✅ Valid: {total_valid} ({total_valid/total_validations:.1%})")
        print(f"  ❌ Invalid: {total_invalid} ({total_invalid/total_validations:.1%})")
        print(f"  🔍 Not Found: {total_not_found} ({total_not_found/total_validations:.1%})")
        
        # Show worst performing scripts
        print(f"\n🚨 Scripts with Most Hallucinations:")
        sorted_results = sorted(results, key=lambda x: len(x['hallucinations_detected']), reverse=True)
        for result in sorted_results[:5]:
            script_name = Path(result['analysis_metadata']['script_path']).name
            hall_count = len(result['hallucinations_detected'])
            confidence = result['validation_summary']['overall_confidence']
            print(f"  - {script_name}: {hall_count} hallucinations ({confidence:.1%} confidence)")
        
        print("="*80)


async def main():
    """Command-line interface for the AI Hallucination Detector"""
    parser = argparse.ArgumentParser(
        description="Detect AI coding assistant hallucinations in Python scripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze single script
  python ai_hallucination_detector.py script.py
  
  # Analyze multiple scripts
  python ai_hallucination_detector.py script1.py script2.py script3.py
  
  # Specify output directory
  python ai_hallucination_detector.py script.py --output-dir reports/
  
  # Skip markdown report
  python ai_hallucination_detector.py script.py --no-markdown
        """
    )
    
    parser.add_argument(
        'scripts',
        nargs='+',
        help='Python script(s) to analyze for hallucinations'
    )
    
    parser.add_argument(
        '--output-dir',
        help='Directory to save reports (defaults to script directory)'
    )
    
    parser.add_argument(
        '--no-json',
        action='store_true',
        help='Skip JSON report generation'
    )
    
    parser.add_argument(
        '--no-markdown',
        action='store_true',
        help='Skip Markdown report generation'
    )
    
    parser.add_argument(
        '--no-summary',
        action='store_true',
        help='Skip printing summary to console'
    )
    
    parser.add_argument(
        '--neo4j-uri',
        default=None,
        help='Neo4j URI (default: from environment NEO4J_URI)'
    )
    
    parser.add_argument(
        '--neo4j-user',
        default=None,
        help='Neo4j username (default: from environment NEO4J_USER)'
    )
    
    parser.add_argument(
        '--neo4j-password',
        default=None,
        help='Neo4j password (default: from environment NEO4J_PASSWORD)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)
        # Only enable debug for our modules, not neo4j
        logging.getLogger('neo4j').setLevel(logging.WARNING)
        logging.getLogger('neo4j.pool').setLevel(logging.WARNING)
        logging.getLogger('neo4j.io').setLevel(logging.WARNING)
    
    # Load environment variables
    load_dotenv()
    
    # Get Neo4j credentials
    neo4j_uri = args.neo4j_uri or os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    neo4j_user = args.neo4j_user or os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_password = args.neo4j_password or os.environ.get('NEO4J_PASSWORD', 'password')
    
    if not neo4j_password or neo4j_password == 'password':
        logger.error("Please set NEO4J_PASSWORD environment variable or use --neo4j-password")
        sys.exit(1)
    
    # Initialize detector
    detector = AIHallucinationDetector(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        await detector.initialize()
        
        # Process scripts
        if len(args.scripts) == 1:
            # Single script mode
            await detector.detect_hallucinations(
                script_path=args.scripts[0],
                output_dir=args.output_dir,
                save_json=not args.no_json,
                save_markdown=not args.no_markdown,
                print_summary=not args.no_summary
            )
        else:
            # Batch mode
            await detector.batch_detect(
                script_paths=args.scripts,
                output_dir=args.output_dir
            )
    
    except KeyboardInterrupt:
        logger.info("Detection interrupted by user")
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"Detection failed: {str(e)}")
        sys.exit(1)
    
    finally:
        await detector.close()


if __name__ == "__main__":
    asyncio.run(main())