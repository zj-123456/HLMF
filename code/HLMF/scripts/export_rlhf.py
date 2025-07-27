#!/usr/bin/env python
"""
Script to output feedback data for RLHF training
"""

import os
import sys
import argparse
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.optimization.feedback_store import FeedbackStore
from src.cli.setup import setup_logging

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Export feedback data for RLHF training")
    parser.add_argument("--db", type=str, default="data/feedback.db",
                        help="Path to response database file")
    parser.add_argument("--output-dir", type=str, default="data/rlhf_exports",
                        help="Data export directory")
    parser.add_argument("--format", type=str, choices=["jsonl", "json", "csv"], default="jsonl",
                        help="Export format (default: jsonl)")
    parser.add_argument("--min-score", type=float, help="Only output responses with higher scores")
    parser.add_argument("--max-feedback", type=int, help="Limit the number of responses")
    parser.add_argument("--split", action="store_true", help="Split into train/eval sets")
    parser.add_argument("--eval-ratio", type=float, default=0.1, 
                        help="Eval set ratio when dividing (default: 0.1)")
    parser.add_argument("--backup", action="store_true", help="Backup database before exporting")
    parser.add_argument("--log-level", type=str, default="INFO", 
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging level")
    
    return parser.parse_args()

def export_feedback_to_jsonl(feedback_data: List[Dict], output_file: str) -> int:
    """
    Export response data to JSONL format
    
    Args:
        feedback_data: Feedback list
        output_file: Output file path
        
    Returns:
        Number of records exported
    """
    count = 0
    with open(output_file, 'w', encoding='utf-8') as f:
        for item in feedback_data:
            # Convert to RLHF format
            if item.get("type") == "pairwise_comparison":
                # Comparison record
                rlhf_item = {
                    "prompt": item.get("query", ""),
                    "chosen": item.get("chosen", ""),
                    "rejected": item.get("rejected", ""),
                    "chosen_model": item.get("chosen_model", ""),
                    "rejected_model": item.get("rejected_model", ""),
                    "conversation_id": item.get("conversation_id", ""),
                    "timestamp": item.get("timestamp", "")
                }
            else:
                # Feedback Record
                selected_response = item.get("selected_response", "")
                responses = item.get("responses", {})
                response_text = responses.get(selected_response, "")
                
                rlhf_item = {
                    "prompt": item.get("query", ""),
                    "response": response_text,
                    "score": item.get("feedback_score"),
                    "model": selected_response,
                    "feedback": item.get("feedback_text"),
                    "conversation_id": item.get("conversation_id", ""),
                    "timestamp": item.get("timestamp", "")
                }
                
            f.write(json.dumps(rlhf_item, ensure_ascii=False) + '\n')
            count += 1
            
    return count

def export_feedback_to_json(feedback_data: List[Dict], output_file: str, 
                           split: bool = False, eval_ratio: float = 0.1) -> Dict:
    """
    Export response data to JSON format
    
    Args:
        feedback_data: Feedback list
        output_file: Output file path
        split: Split into train/eval sets
        eval_ratio: Ratio of eval sets
        
    Returns:
        Dict statistics of the number of records exported
    """
    # Data Classification
    comparisons = []
    feedback = []
    
    for item in feedback_data:
        if item.get("type") == "pairwise_comparison":
            comparisons.append({
                "prompt": item.get("query", ""),
                "chosen": item.get("chosen", ""),
                "rejected": item.get("rejected", ""),
                "chosen_model": item.get("chosen_model", ""),
                "rejected_model": item.get("rejected_model", ""),
                "conversation_id": item.get("conversation_id", ""),
                "timestamp": item.get("timestamp", "")
            })
        else:
            selected_response = item.get("selected_response", "")
            responses = item.get("responses", {})
            response_text = responses.get(selected_response, "")
            
            feedback.append({
                "prompt": item.get("query", ""),
                "response": response_text,
                "score": item.get("feedback_score"),
                "model": selected_response,
                "feedback": item.get("feedback_text"),
                "conversation_id": item.get("conversation_id", ""),
                "timestamp": item.get("timestamp", "")
            })
    
    # Split into train/eval sets if needed
    if split and feedback:
        import random
        random.shuffle(feedback)
        split_idx = max(1, int(len(feedback) * (1 - eval_ratio)))
        train_feedback = feedback[:split_idx]
        eval_feedback = feedback[split_idx:]
    else:
        train_feedback = feedback
        eval_feedback = []
        
    if split and comparisons:
        import random
        random.shuffle(comparisons)
        split_idx = max(1, int(len(comparisons) * (1 - eval_ratio)))
        train_comparisons = comparisons[:split_idx]
        eval_comparisons = comparisons[split_idx:]
    else:
        train_comparisons = comparisons
        eval_comparisons = []
    
    # Create export data structure
    export_data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "split": split
        },
        "train": {
            "feedback": train_feedback,
            "comparisons": train_comparisons
        }
    }
    
    if split:
        export_data["eval"] = {
            "feedback": eval_feedback,
            "comparisons": eval_comparisons
        }
    
    # The file is empty.
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
        
    return {
        "total": len(feedback) + len(comparisons),
        "feedback": len(feedback),
        "comparisons": len(comparisons),
        "train_feedback": len(train_feedback),
        "train_comparisons": len(train_comparisons),
        "eval_feedback": len(eval_feedback) if split else 0,
        "eval_comparisons": len(eval_comparisons) if split else 0
    }

def export_feedback_to_csv(feedback_data: List[Dict], output_dir: str) -> Dict:
    """
    Export response data to CSV format
    
    Args:
        feedback_data: Feedback list
        output_dir: Output directory
        
    Returns:
        Dict statistics of the number of records exported
    """
    import csv
    
    # Data Classification
    comparisons = []
    feedback = []
    
    for item in feedback_data:
        if item.get("type") == "pairwise_comparison":
            comparisons.append({
                "prompt": item.get("query", ""),
                "chosen": item.get("chosen", ""),
                "rejected": item.get("rejected", ""),
                "chosen_model": item.get("chosen_model", ""),
                "rejected_model": item.get("rejected_model", ""),
                "conversation_id": item.get("conversation_id", ""),
                "timestamp": item.get("timestamp", "")
            })
        else:
            selected_response = item.get("selected_response", "")
            responses = item.get("responses", {})
            response_text = responses.get(selected_response, "")
            
            feedback.append({
                "prompt": item.get("query", ""),
                "response": response_text,
                "score": item.get("feedback_score"),
                "model": selected_response,
                "feedback": item.get("feedback_text"),
                "conversation_id": item.get("conversation_id", ""),
                "timestamp": item.get("timestamp", "")
            })
    
    # Export feedback
    feedback_file = os.path.join(output_dir, "feedback.csv")
    feedback_count = 0
    if feedback:
        with open(feedback_file, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ["prompt", "response", "score", "model", "feedback", 
                        "conversation_id", "timestamp"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for item in feedback:
                writer.writerow(item)
                feedback_count += 1
    
    # Export comparison
    comparison_file = os.path.join(output_dir, "comparisons.csv")
    comparison_count = 0
    if comparisons:
        with open(comparison_file, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ["prompt", "chosen", "rejected", "chosen_model", 
                        "rejected_model", "conversation_id", "timestamp"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for item in comparisons:
                writer.writerow(item)
                comparison_count += 1
                
    return {
        "total": feedback_count + comparison_count,
        "feedback": feedback_count,
        "comparisons": comparison_count,
        "feedback_file": feedback_file if feedback_count > 0 else None,
        "comparison_file": comparison_file if comparison_count > 0 else None
    }

def filter_feedback_data(feedback_data: List[Dict], min_score: Optional[float] = None,
                        max_count: Optional[int] = None) -> List[Dict]:
    """
    Filter feedback data by score and quantity
    
    Args:
        feedback_data: Feedback list
        min_score: Minimum score
        max_count: Maximum count

    Returns:
        Filtered response list
    """
    # Filter by score
    if min_score is not None:
        feedback_data = [
            item for item in feedback_data
            if (item.get("type") == "pairwise_comparison") or 
               (item.get("feedback_score") is not None and 
                item.get("feedback_score") >= min_score)
        ]
    
    # Quantity limit
    if max_count is not None and max_count > 0:
        feedback_data = feedback_data[:max_count]
        
    return feedback_data

def main():
    """Main function"""
    args = parse_args()
    
    # Set up logging
    log_level = getattr(logging, args.log_level)
    setup_logging(log_level)#2025-03-15 06:14:48 - setup - INFO - Logging initialized with level INFO
    logger = logging.getLogger("export_rlhf")
    
    # Create output folder
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize FeedbackStore
    store = FeedbackStore(args.db)#2025-03-15 06:17:45 - src.optimization.feedback_store - INFO - Initialized feedback database at data/feedback.db
    
    # Backup database if needed
    if args.backup:
        logger.info("Backing up database...")
        backup_success = store.backup_database()
        if backup_success:
            logger.info("Database backed up successfully")
        else:
            logger.warning("Unable to backup database")
    
    # Get all responses
    logger.info("Fetching response data...")
    feedback_data = store.get_all_feedback()
    logger.info(f"Taken {len(feedback_data)} feedback record")
    
    # Filter data
    feedback_data = filter_feedback_data(
        feedback_data, 
        min_score=args.min_score,
        max_count=args.max_feedback
    )
    logger.info(f"Remaining {len(feedback_data)} filtered records")
    
    if not feedback_data:
        logger.warning("No data to export")
        return
    
    # Create file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Export data in format
    if args.format == "jsonl":
        output_file = os.path.join(args.output_dir, f"rlhf_export_{timestamp}.jsonl")
        count = export_feedback_to_jsonl(feedback_data, output_file)
        logger.info(f"Exported {count} record to {output_file}")
        
    elif args.format == "json":
        output_file = os.path.join(args.output_dir, f"rlhf_export_{timestamp}.json")
        stats = export_feedback_to_json(
            feedback_data, output_file, 
            split=args.split, eval_ratio=args.eval_ratio
        )
        logger.info(f"Exported {stats['total']} record to {output_file}")
        if args.split:
            logger.info(f"  - Train: {stats['train_feedback']} feedback, {stats['train_comparisons']} compare")
            logger.info(f"  - Eval: {stats['eval_feedback']} feedback, {stats['eval_comparisons']} compare")
            
    elif args.format == "csv":
        output_subdir = os.path.join(args.output_dir, f"rlhf_export_{timestamp}")
        os.makedirs(output_subdir, exist_ok=True)
        stats = export_feedback_to_csv(feedback_data, output_subdir)
        logger.info(f"Exported {stats['total']} record to {output_subdir}")
        logger.info(f"  - {stats['feedback']} feedback: {os.path.basename(stats['feedback_file']) if stats['feedback_file'] else 'None'}")
        logger.info(f"  - {stats['comparisons']} compare: {os.path.basename(stats['comparison_file']) if stats['comparison_file'] else 'None'}")

if __name__ == "__main__":
    main()