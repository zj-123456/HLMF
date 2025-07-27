"""
Performance report and data analysis.
Display reports and statistics from collected data.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

def display_performance_report(report: Dict[str, Any]):
    """
    Display the performance report of the models.

    Args:
        report: Dict containing performance report data
    """
    if "error" in report:
        print(f"\nError generating report: {report['error']}")
        return

    print("\n" + "="*70)
    print("  MODEL PERFORMANCE REPORT BASED ON USER FEEDBACK")
    print("="*70)

    # Display model metrics
    print("\nMODEL PERFORMANCE:")
    print("-" * 80)
    print(f"{'Model':<20} {'Avg Score':<10} {'Win Rate':<15} {'Sample Count':<10} {'Last Updated':<20}")
    print("-" * 80)

    for model, metrics in report.get("model_metrics", {}).items():
        avg_score = metrics.get("avg_score", 0)
        win_rate = metrics.get("win_rate", 0)
        samples = metrics.get("sample_count", 0)
        last_updated = metrics.get("last_updated", "N/A")

        if isinstance(last_updated, str) and len(last_updated) > 19:
            last_updated = last_updated[:19]  # Trim milliseconds

        print(f"{model:<20} {avg_score:<10.2f} {win_rate:<15.2f} {samples:<10} {last_updated:<20}")

    # Display preference statistics
    print("\nSELECTION COUNT:")
    preference_stats = report.get("preference_stats", {})
    if preference_stats:
        for model, count in preference_stats.items():
            print(f"  {model}: {count} times")
    else:
        print("  No preference comparison data available.")

    # Display current preference weights
    print("\nCURRENT PREFERENCE WEIGHTS:")
    preference_weights = report.get("preference_weights", {})
    if preference_weights:
        for model, weight in preference_weights.items():
            print(f"  {model}: {weight:.2f}")
    else:
        print("  No preference weights available.")

    # Display performance trends
    if "performance_trends" in report and report["performance_trends"]:
        print("\nPERFORMANCE TRENDS (LAST 30 DAYS):")
        for model, trend in report["performance_trends"].items():
            if trend:
                print(f"\n  {model}:")
                print(f"    {'Date':<12} {'Avg Score':<10} {'Sample Count':<8}")
                print(f"    {'-'*30}")
                for entry in trend[-7:]:  # Show only last 7 entries
                    date = entry.get("date", "N/A")
                    score = entry.get("avg_score", 0)
                    count = entry.get("sample_count", 0)
                    print(f"    {date:<12} {score:<10.2f} {count:<8}")

    # Display recent feedback
    print("\nRECENT FEEDBACK:")
    recent_feedback = report.get("recent_feedback", [])
    if recent_feedback:
        for idx, feedback in enumerate(recent_feedback[:5]):  # Show only last 5 feedback
            query = feedback.get('query', '')
            if len(query) > 50:
                query = query[:47] + "..."

            print(f"\n  [{idx+1}] Query: {query}")
            print(f"      Model: {feedback.get('model', '')}")
            print(f"      Score: {feedback.get('score', 'N/A')}")
            if feedback.get('feedback_text'):
                feedback_text = feedback.get('feedback_text', '')
                if len(feedback_text) > 70:
                    feedback_text = feedback_text[:67] + "..."
                print(f"      Comment: {feedback_text}")

            timestamp = feedback.get('timestamp', '')
            if timestamp and len(timestamp) > 19:
                timestamp = timestamp[:19]
            print(f"      Timestamp: {timestamp}")
    else:
        print("  No recorded feedback available.")

    # Display optimization status
    print("\nOPTIMIZATION STATUS:")
    print(f"  Optimization: {'ENABLED' if report.get('optimization_enabled', False) else 'DISABLED'}")
    print(f"  Feedback Collection: {'ENABLED' if report.get('feedback_enabled', False) else 'DISABLED'}")

    # Report generation timestamp
    generated_at = report.get("generated_at", "N/A")
    if isinstance(generated_at, str) and len(generated_at) > 19:
        generated_at = generated_at[:19]
    print(f"\nReport generated at: {generated_at}")
    print("="*70)


def generate_optimization_summary(stats: Dict[str, Any]) -> str:
    """
    Generate a summary of the optimization process.

    Args:
        stats: Optimization statistics

    Returns:
        Summary string
    """
    lines = []
    lines.append("OPTIMIZATION SUMMARY:")

    # Basic information
    total_feedback = stats.get("total_feedback_count", 0)
    model_count = stats.get("model_count", 0)
    lines.append(f"- Total feedback collected: {total_feedback}")
    lines.append(f"- Number of models evaluated: {model_count}")

    # Weight analysis
    if "current_weights" in stats:
        weights = stats["current_weights"]
        if weights:
            max_model = max(weights.items(), key=lambda x: x[1])[0]
            min_model = min(weights.items(), key=lambda x: x[1])[0]
            lines.append(f"- Most preferred model: {max_model} (weight: {weights[max_model]:.2f})")
            lines.append(f"- Least preferred model: {min_model} (weight: {weights[min_model]:.2f})")

    # Feedback statistics
    if "feedback_counts_by_model" in stats:
        feedback_counts = stats["feedback_counts_by_model"]
        if feedback_counts:
            most_feedback_model = max(feedback_counts.items(), key=lambda x: x[1])[0]
            lines.append(
                f"- Model with the most feedback: {most_feedback_model} ({feedback_counts[most_feedback_model]} feedback entries)")

    # Add timestamp
    timestamp = stats.get("timestamp", "")
    if timestamp and len(timestamp) > 19:
        timestamp = timestamp[:19]
    lines.append(f"- Last updated: {timestamp}")

    return "\n".join(lines)


def export_report_to_file(report: Dict[str, Any], output_path: str) -> bool:
    """
    Export the performance report to a file.

    Args:
        report: Report data
        output_path: Output file path

    Returns:
        True if export is successful, False otherwise
    """
    try:
        import json

        # Add metadata
        report["export_metadata"] = {
            "exported_at": datetime.now().isoformat(),
            "format_version": "1.0"
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"Performance report exported to {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error exporting performance report: {e}")
        return False