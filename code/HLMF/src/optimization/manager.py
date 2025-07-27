"""
Module for managing feedback optimization based on RLHF and DPO
"""

import logging
import os
from typing import Dict, List, Any, Optional, Tuple

from src.optimization.feedback_collector import FeedbackCollector
from src.optimization.feedback_store import FeedbackStore
from src.optimization.preference_optimizer import PreferenceOptimizer
from src.optimization.response_optimizer import ResponseOptimizer

logger = logging.getLogger(__name__)

class FeedbackOptimizationManager:
    """
    Manages the feedback optimization process by coordinating between:
    - Feedback collection (RLHF)
    - Preference-based optimization (DPO)
    - Query/response analysis and optimization
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Feedback Optimization Manager

        Args:
            config: System configuration
        """
        self.config = config
        self.optimization_config = config.get("optimization", {})
        self.enabled = self.optimization_config.get("enabled", True)

        # Initialize components
        feedback_db_path = config.get("system", {}).get("feedback_db", "data/feedback.db")
        os.makedirs(os.path.dirname(feedback_db_path), exist_ok=True)

        # Initialize feedback storage
        self.feedback_store = FeedbackStore(feedback_db_path)

        # Initialize preference optimizer
        self.preference_optimizer = PreferenceOptimizer(config)

        # Initialize feedback collector
        self.feedback_collector = FeedbackCollector(
            self.feedback_store,
            config
        )

        # Initialize response optimizer
        self.response_optimizer = ResponseOptimizer(config)

        logger.info("Initialized Feedback Optimization Manager")

    def optimize_query(self, query: str, user_info: Optional[Dict] = None,
                      conversation_history: Optional[List] = None) -> Dict[str, Any]:
        """
        Optimize user query

        Args:
            query: User query
            user_info: User information (optional)
            conversation_history: Conversation history (optional)

        Returns:
            Dict containing analysis results and optimized prompt
        """
        if not self.enabled:
            return {'analysis': {}, 'optimized_prompt': query}

        try:
            # Use the correct method from ResponseOptimizer
            result = self.response_optimizer.optimize_query(query, user_info, conversation_history)
            return result
        except Exception as e:
            logger.error(f"Error optimizing query: {e}")
            return {'analysis': {}, 'optimized_prompt': query}

    def select_best_model(self, query: str, analysis: Optional[Dict] = None,
                         available_models: Optional[List[Dict]] = None) -> Optional[str]:
        """
        Select the best model based on query analysis

        Args:
            query: User query
            analysis: Query analysis results (optional)
            available_models: List of available models (optional)

        Returns:
            Name of the selected model or None
        """
        if not self.enabled:
            return None

        try:
            # Analyze query if not provided
            if analysis is None:
                analysis = self.response_optimizer.analyze_query(query)

            # Get available models if not provided
            if available_models is None:
                available_models = self.config.get("models", [])#得到的是models.yml的数据

            # Select the best model using PreferenceOptimizer
            best_model = self.preference_optimizer.select_best_model(
                analysis, available_models)

            return best_model
        except Exception as e:
            logger.error(f"Error selecting best model: {e}")
            return None

    def process_feedback(self, conversation_id: str, query: str, responses: Dict[str, str],
                        selected_response: str, feedback_score: Optional[float] = None,
                        feedback_text: Optional[str] = None) -> bool:
        """
        Process user feedback and update optimization models

        Args:
            conversation_id: Conversation ID
            query: User query
            responses: Dict of responses with model_name as key
            selected_response: Name of the selected model
            feedback_score: Feedback score (0-1, optional)
            feedback_text: Text feedback (optional)

        Returns:
            True if processing is successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            # 存储用户反馈数据（通过 self.feedback_collector.collect_feedback()）
            feedback_id = self.feedback_collector.collect_feedback(
                conversation_id=conversation_id,
                query=query,
                responses=responses,
                selected_response=selected_response,
                feedback_score=feedback_score,
                feedback_text=feedback_text
            )

            if feedback_id:
                # 基于用户反馈调整模型权重（通过 self.preference_optimizer.update_weights_from_feedback()）。
                self.preference_optimizer.update_weights_from_feedback(
                    query, responses, selected_response, feedback_score
                )

                # 更新 Prompt 模板的性能数据（通过 self._update_template_performance()）
                self._update_template_performance(query, selected_response, feedback_score)

                return True

            return False
        except Exception as e:
            logger.error(f"Error processing feedback: {e}")
            return False

    def _update_template_performance(self, query: str, selected_model: str,
                                    feedback_score: Optional[float]) -> None:
        """
        Update prompt template performance based on feedback

        Args:
            query: User query
            selected_model: Selected model
            feedback_score: Feedback score
        """
        if feedback_score is None:
            return

        # Get information about the prompt template used
        query_result = self.response_optimizer.query_analysis_cache.get(query, {})
        template_used = query_result.get("template_used", "default")

        # Update template performance
        self.response_optimizer.update_template_performance(template_used, feedback_score)

    def export_feedback_data(self, export_dir: Optional[str] = None) -> str:
        """
        Export feedback data for RLHF training

        Args:
            export_dir: Export directory (optional)

        Returns:
            Path to the exported file
        """
        if export_dir is None:
            export_dir = self.config.get("system", {}).get(
                "rlhf_export_dir", "data/rlhf_exports")

        os.makedirs(export_dir, exist_ok=True)

        try:
            export_path = self.feedback_collector.export_feedback_data(export_dir)
            return export_path
        except Exception as e:
            logger.error(f"Error exporting feedback data: {e}")
            return ""

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about feedback data and optimization

        Returns:
            Dict containing statistics
        """
        stats = {
            "enabled": self.enabled,
            "feedback_collection": {
                "total_samples": self.feedback_store.get_total_count(),
                "positive_samples": self.feedback_store.get_count_by_score(min_score=0.7),
                "negative_samples": self.feedback_store.get_count_by_score(max_score=0.3),
                "neutral_samples": self.feedback_store.get_count_by_score(min_score=0.3, max_score=0.7)
            },
            "model_preferences": self.preference_optimizer.get_model_weights(),
            "template_performance": self.response_optimizer.template_performance_history
        }

        return stats

    def toggle_optimization(self, enabled: bool) -> None:
        """
        Enable/disable optimization

        Args:
            enabled: True to enable, False to disable
        """
        self.enabled = enabled

    def toggle_feedback_collection(self, enabled: bool) -> None:
        """
        Enable/disable feedback collection

        Args:
            enabled: True to enable, False to disable
        """
        self.feedback_collector.toggle_collection(enabled)

    def clear_caches(self) -> None:
        """Clear all caches"""
        self.response_optimizer.clear_cache()
        self.preference_optimizer.clear_cache()