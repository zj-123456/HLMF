"""
Command-line parameter processing.
Provides CLI configuration and parameter parsing for the system.
"""

import argparse
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def setup_argparser() -> argparse.ArgumentParser:
    """
    Set up command-line argument parser.

    Returns:
        Configured ArgumentParser object
    """
    parser = argparse.ArgumentParser(
        description="Advanced personal assistant system with RLHF and DPO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python main.py -i                                # Run in interactive mode
  python main.py -q "Write a sorting algorithm"    # Single query
  python main.py -q "Analyze a poem" -g           # Group discussion
  python main.py -i -f --auto-model                # Interactive with feedback collection
  python main.py --report                          # Display performance report
  python main.py --export-rlhf rlhf_data           # Export RLHF data
"""
    )

    # General parameters
    parser.add_argument('--config', '-c', type=str,
                        help='Path to configuration file')
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Run in interactive mode')
    parser.add_argument('--query', '-q', type=str,
                        help='Query to process (for non-interactive mode)')
    parser.add_argument('--role', '-r', type=str,
                        help='Specific model role to use')
    parser.add_argument('--temperature', '-t', type=float, default=0.7,
                        help='Model temperature (0.0-1.0)')
    parser.add_argument('--max-tokens', '-m', type=int, default=1024,
                        help='Maximum number of tokens in response')
    parser.add_argument('--save', '-s', type=str,
                        help='File name to save conversation history')

    # Group discussion parameters
    group_discussion = parser.add_argument_group('Group Discussion')
    group_discussion.add_argument('--group-discussion', '-g', action='store_true',
                        help='Enable group discussion mode between models')
    group_discussion.add_argument('--rounds', type=int, default=2,
                        help='Number of discussion rounds in group mode (default: 2)')
    group_discussion.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed discussion process (for group mode)')

    # RLHF/DPO parameters
    optimization = parser.add_argument_group('RLHF/DPO Optimization')
    optimization.add_argument('--feedback', '-f', action='store_true',
                        help='Enable user feedback collection')
    optimization.add_argument('--no-optimization', action='store_true',
                        help='Disable automatic optimization based on RLHF/DPO')
    optimization.add_argument('--feedback-db', type=str,
                        help='Path to feedback database')
    optimization.add_argument('--export-rlhf', type=str, metavar='DIR',
                        help='Export collected RLHF data to specified directory')
    optimization.add_argument('--report', action='store_true',
                        help='Generate model performance report based on feedback')
    optimization.add_argument('--auto-model', action='store_true',
                        help='Automatically select the best model based on query analysis')
    optimization.add_argument('--reset-optimization', action='store_true',
                        help='Reset optimization process (weights to default)')
    optimization.add_argument('--reset-feedback-db', action='store_true',
                        help='Reset feedback database (backup before proceeding)')

    # Logging parameters
    logging_group = parser.add_argument_group('Logging')
    logging_group.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='INFO', help='Log level')
    logging_group.add_argument('--log-file', type=str,
                        help='Path to log file (if not provided, logs to console)')

    return parser

def parse_args() -> argparse.Namespace:
    """
    Parse command-line parameters.

    Returns:
        Namespace object containing parsed parameters
    """
    parser = setup_argparser()
    args = parser.parse_args()

    # Check for conflicting parameters
    if args.query is None and not args.interactive and not args.report and not args.export_rlhf and not args.reset_optimization:
        parser.error("Must provide a query (--query) or use interactive mode (--interactive) "
                    "or one of the following functions: --report, --export-rlhf, --reset-optimization")

    if args.reset_feedback_db and not args.reset_optimization:
        parser.error("--reset-feedback-db can only be used with --reset-optimization")

    return args

def args_to_config(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Convert command-line parameters into system configuration.

    Args:
        args: Namespace object containing parsed parameters

    Returns:
        Dictionary containing configuration generated from parameters
    """
    config_updates = {
        "system": {}
    }

    # Update system configuration
    if args.feedback_db:
        config_updates["system"]["feedback_db"] = args.feedback_db

    if args.log_file:
        config_updates["system"]["log_file"] = args.log_file

    config_updates["system"]["log_level"] = args.log_level

    # Update RLHF/DPO configuration
    config_updates["optimization"] = {
        "enabled": not args.no_optimization,
        "auto_select_model": args.auto_model,
        "feedback": {
            "enabled": args.feedback
        }
    }

    # Update group discussion configuration
    config_updates["group_discussion"] = {
        "default_rounds": args.rounds
    }

    return config_updates

def update_config_from_args(config: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    """
    Update existing configuration with command-line parameters.

    Args:
        config: Existing configuration
        args: Namespace object containing parsed parameters

    Returns:
        Updated configuration
    """
    updates = args_to_config(args)

    # Update nested dictionary
    def update_nested_dict(d, u):
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                d[k] = update_nested_dict(d[k], v)
            else:
                d[k] = v
        return d

    updated_config = update_nested_dict(config, updates)
    return updated_config
