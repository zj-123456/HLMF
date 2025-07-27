"""
Module for collecting and managing feedback for RLHF
"""

import os
import json
import time
import random
import logging
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from datetime import datetime

from src.optimization.feedback_store import FeedbackStore

logger = logging.getLogger(__name__)

class FeedbackCollector:
    """
    Collect and manage user feedback for use in RLHF
    """

    def __init__(self, feedback_store: FeedbackStore, config: Dict[str, Any]):
        """
        Initialize Feedback Collector

        Args:
            feedback_store: Feedback storage
            config: System configuration
        """
        self.store = feedback_store
        self.config = config
        self.feedback_config = config.get("optimization", {}).get("feedback", {})

        # Collection configuration
        self.enabled = self.feedback_config.get("enabled", True)
        self.collection_probability = self.feedback_config.get("collection_probability", 0.3)
        self.collect_comparisons = self.feedback_config.get("collect_comparisons", True)
        self.feedback_cache_size = self.feedback_config.get("feedback_cache_size", 1000)

        # Cache for feedback
        self.feedback_cache = {}

        # List of conversation IDs that have requested feedback
        self.requested_feedback_conversations = set()

        logger.info("Initialized RLHF Feedback Collector")

    def collect_feedback(self, conversation_id: str, query: str,
                        responses: Dict[str, str], selected_response: str,
                        feedback_score: Optional[float] = None,
                        feedback_text: Optional[str] = None) -> Optional[str]:
        """
        Collect feedback on responses

        Args:
            conversation_id: Conversation ID
            query: User query
            responses: Dict of responses with key as model_name
            selected_response: Name of the selected model
            feedback_score: Rating score (0-1, optional)
            feedback_text: Text feedback (optional)

        Returns:
            Feedback ID if successful, None otherwise
        """
        if not self.enabled:
            return None

        try:
            # Create feedback record
            feedback_record = {
                "id": f"fb_{int(time.time())}_{random.randint(1000, 9999)}",
                "timestamp": datetime.now().isoformat(),
                "conversation_id": conversation_id,
                "query": query,
                "responses": responses,
                "selected_response": selected_response,
                "feedback_score": feedback_score,
                "feedback_text": feedback_text
            }

            # Save to database sqlite
            feedback_id = self.store.save_feedback(feedback_record)

            # Save to cache
            self._update_feedback_cache(feedback_id, feedback_record)

            # If collecting comparisons, create pairwise comparison records
            if self.collect_comparisons and len(responses) > 1:
                self._create_pairwise_comparisons(
                    conversation_id, query, responses, selected_response)

            return feedback_id

        except Exception as e:
            logger.error(f"Error collecting feedback: {e}")
            return None

    def should_request_feedback(self, conversation_id: str) -> bool:
        #判断是否应该请求用户反馈，具体来说，它根据一定的概率决定是否对某个对话（conversation_id）请求反馈，同时避免对同一对话重复请求。
        """
        Determine whether to request feedback for this conversation

        Args:
            conversation_id: Conversation ID

        Returns:
            True if feedback should be requested, False otherwise
        """
        if not self.enabled:
            return False

        # Do not request feedback if already requested for this conversation
        if conversation_id in self.requested_feedback_conversations:
            return False

        # Request feedback with configured probability
        should_request = random.random() < self.collection_probability

        if should_request:
            self.requested_feedback_conversations.add(conversation_id)

        return should_request

    def export_feedback_data(self, export_dir: str) -> str:
        """
        Export feedback data to JSON format for RLHF

        Args:
            export_dir: Target directory for exported data

        Returns:
            Path to the exported file
        """
        os.makedirs(export_dir, exist_ok=True)

        try:
            # Get all feedback
            all_feedback = self.store.get_all_feedback()

            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_file = os.path.join(export_dir, f"feedback_export_{timestamp}.json")

            # Convert data format
            export_data = self._convert_to_rlhf_format(all_feedback)

            # Write to file
            with open(export_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Exported {len(all_feedback)} feedback records to {export_file}")
            return export_file

        except Exception as e:
            logger.error(f"Error exporting feedback data: {e}")
            return ""

    def toggle_collection(self, enabled: bool) -> None:
        """
        Enable/disable feedback collection

        Args:
            enabled: True to enable, False to disable
        """
        self.enabled = enabled
        if enabled:
            logger.info("Enabled RLHF feedback collection")
        else:
            logger.info("Disabled RLHF feedback collection")

    def _update_feedback_cache(self, feedback_id: str, feedback_record: Dict[str, Any]) -> None:
        """
        Update feedback cache

        Args:
            feedback_id: Feedback ID
            feedback_record: Feedback record
        """
        # Add to cache
        self.feedback_cache[feedback_id] = feedback_record

        # Limit cache size
        if len(self.feedback_cache) > self.feedback_cache_size:
            # Remove oldest items
            oldest_keys = sorted(self.feedback_cache.keys(),
                                key=lambda k: self.feedback_cache[k].get("timestamp", ""))[:100]
            for key in oldest_keys:
                del self.feedback_cache[key]

    def _create_pairwise_comparisons(self, conversation_id: str, query: str,
                                    responses: Dict[str, str], selected_response: str) -> None:
        """
        Create pairwise comparison records for DPO

        Args:
            conversation_id: Conversation ID
            query: User query
            responses: Dict of responses with key as model_name
            selected_response: Name of the selected model
        """
        # Get the selected response
        chosen_text = responses.get(selected_response, "")
        if not chosen_text:
            return

        # Create comparison records
        for model, response in responses.items():
            if model == selected_response or not response:
                continue

            # Create DPO record with "chosen" and "rejected"
            comparison_record = {
                "id": f"comp_{int(time.time())}_{random.randint(1000, 9999)}",
                "timestamp": datetime.now().isoformat(),
                "conversation_id": conversation_id,
                "query": query,
                "chosen": chosen_text,
                "rejected": response,
                "chosen_model": selected_response,
                "rejected_model": model,
                "type": "pairwise_comparison"
            }

            # Save to database
            self.store.save_comparison(comparison_record)

    def _convert_to_rlhf_format(self, feedback_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert feedback records to RLHF-compatible format

        Args:
            feedback_records: List of feedback records

        Returns:
            Data converted to RLHF format
        """
        rlhf_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0",
                "record_count": len(feedback_records)
            },
            "feedback": [],
            "comparisons": []
        }

        # Convert each record
        for record in feedback_records:
            if record.get("type") == "pairwise_comparison":
                # Comparison record
                rlhf_data["comparisons"].append({
                    "id": record.get("id"),
                    "prompt": record.get("query"),
                    "chosen": record.get("chosen"),
                    "rejected": record.get("rejected"),
                    "chosen_model": record.get("chosen_model"),
                    "rejected_model": record.get("rejected_model")
                })
            else:
                # Feedback record
                rlhf_record = {
                    "id": record.get("id"),
                    "prompt": record.get("query"),
                    "response": record.get("responses", {}).get(record.get("selected_response", "")),
                    "model": record.get("selected_response"),
                    "score": record.get("feedback_score"),
                    "feedback": record.get("feedback_text")
                }
                rlhf_data["feedback"].append(rlhf_record)
                
        return rlhf_data