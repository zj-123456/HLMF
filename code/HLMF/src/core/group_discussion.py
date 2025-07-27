"""
Module for managing group discussions between LLM models
"""

import os
import time
import json
import logging
import random
from typing import Dict, List, Any, Optional, Tuple, Union

from src.core.models import ModelManager

logger = logging.getLogger(__name__)

class GroupDiscussionManager:
    """
    Manages group discussions between multiple LLM models.
    Implements:
    - Discussion flow coordination
    - Response integration
    - Final result synthesis
    """

    def __init__(self, model_manager: ModelManager, config: Dict[str, Any]):
        """
        Initialize Group Discussion Manager

        Args:
            model_manager: Model management object
            config: System configuration
        """
        self.model_manager = model_manager
        self.config = config
        self.group_config = config.get("group_discussion", {})

        # Get configurations
        self.name = self.group_config.get("name", "group_discussion")
        self.system_prompt = self.group_config.get("system_prompt",
            "This is the result of a group discussion between different AI experts. "
            "Each expert has contributed from their specialized field, and "
            "the results have been synthesized into a comprehensive answer.")
        self.default_rounds = self.group_config.get("default_rounds", 2)

        # Discussion storage
        self.discussions = {}

        logger.info("Initialized Group Discussion Manager")

    def conduct_discussion(self, query: str, discussion_id: Optional[str] = None,
                          user_info: Optional[Dict] = None, models: Optional[List[str]] = None,
                          params: Optional[Dict[str, Any]] = None,
                          rounds: Optional[int] = None) -> Dict[str, Any]:
        """
        Conduct a group discussion

        Args:
            query: User query
            discussion_id: Discussion ID (optional)
            user_info: User information (optional)
            models: List of participating models (optional)
            params: Additional parameters (optional)
            rounds: Number of discussion rounds (optional)

        Returns:
            Dictionary containing discussion results and additional info
        """
        start_time = time.time()

        # Generate discussion ID if not provided
        if not discussion_id:
            discussion_id = f"disc_{int(time.time())}"

        # Number of rounds
        rounds = rounds or self.default_rounds

        # Select participating models
        participating_models = self._select_participating_models(models)
        if not participating_models:
            return {
                "error": "No suitable models found for discussion",
                "success": False
            }

        # Prepare parameters
        discussion_params = {
            "temperature": 0.7,
            "max_tokens": 1024
        }
        if params:
            discussion_params.update(params)

        # Conduct discussion rounds
        discussion_log = []
        current_context = query
        models_used = set()

        for round_num in range(rounds):
            round_responses = {}

            # Get responses from each model
            for model_name in participating_models:
                try:
                    response = self.model_manager.get_response(
                        model_name,
                        current_context,
                        self._create_expert_system_prompt(model_name, round_num),
                        discussion_params
                    )

                    round_responses[model_name] = response.get("response", "")
                    models_used.add(model_name)

                except Exception as e:
                    logger.error(f"Error getting response from {model_name}: {e}")

            # Add to discussion log
            discussion_log.append({
                "round": round_num + 1,
                "responses": round_responses
            })

            # Update context for next round
            if round_num < rounds - 1:
                current_context = self._create_next_round_context(
                    query, round_responses, round_num)

        # Synthesize final response
        final_response = self._synthesize_final_response(query, discussion_log)

        # Save discussion
        self._save_discussion(discussion_id, query, discussion_log, final_response)

        # Completion time
        completion_time = time.time() - start_time

        # Result
        result = {
            "response": final_response,
            "discussion_id": discussion_id,
            "models_used": list(models_used),
            "rounds": rounds,
            "completion_time": completion_time,
            "success": True
        }

        return result

    def _select_participating_models(self, specified_models: Optional[List[str]] = None) -> List[str]:
        """
        Select models to participate in discussion

        Args:
            specified_models: List of specified models (optional)

        Returns:
            List of selected model names
        """
        if specified_models:
            # Filter existing models
            available_models = self.model_manager.list_models()
            return [model for model in specified_models if model in available_models]

        # Default to all models
        return self.model_manager.list_models()

    def _create_expert_system_prompt(self, model_name: str, round_num: int) -> str:
        """
        Create system prompt for expert model

        Args:
            model_name: Model name
            round_num: Round number

        Returns:
            Model system prompt
        """
        # Get model info
        model_info = self.model_manager.get_model_info(model_name)
        if not model_info:
            return ""

        # Get role and system prompt
        role = model_info.get("role", "assistant")
        base_prompt = model_info.get("system_prompt", "")

        # Create round-based prompt
        if round_num == 0:
            # Initial round: first response
            return (f"{base_prompt}\n\nYou are participating in a group discussion as a {role} expert. "
                   f"Please answer the question based on your expertise. "
                   f"Focus on your strengths as a {role} expert.")
        else:
            # Subsequent rounds: response synthesis
            return (f"{base_prompt}\n\nYou are participating in a group discussion as a {role} expert. "
                   f"Please consider opinions from other experts and provide additional insights from your professional perspective. "
                   f"Focus on improving the answer based on your {role} expertise.")

    def _create_next_round_context(self, query: str, round_responses: Dict[str, str],
                                 round_num: int) -> str:
        """
        Create context for next discussion round

        Args:
            query: Original query
            round_responses: Current round responses
            round_num: Current round number

        Returns:
            Context for next round
        """
        context_parts = [
            f"Original question: {query}",
            f"\nDiscussion round {round_num + 1} has completed. Here are expert opinions:"
        ]

        # Add responses from each model
        for model, response in round_responses.items():
            model_info = self.model_manager.get_model_info(model)
            role = model_info.get("role", "assistant") if model_info else "assistant"

            context_parts.append(f"\n--- Opinion from {role} expert ---")
            context_parts.append(response)

        # Instructions for next round
        context_parts.append(f"\n\nDiscussion round {round_num + 2}:")
        context_parts.append("Please consider the above opinions and provide additional insights from your professional perspective.")
        context_parts.append("Focus on improving and clarifying points that need further elaboration.")

        return "\n".join(context_parts)

    def _synthesize_final_response(self, query: str, discussion_log: List[Dict[str, Any]]) -> str:
        """
        Synthesize final response from discussion

        Args:
            query: Original query
            discussion_log: Discussion log

        Returns:
            Synthesized answer
        """
        # No discussion data
        if not discussion_log:
            return "Insufficient discussion data to synthesize response."

        # Get last round
        last_round = discussion_log[-1]
        last_responses = last_round.get("responses", {})

        if not last_responses:
            return "No responses in final discussion round."

        # Create synthesis prompt
        synthesis_prompt = [
            f"Question: {query}",
            "\nA group discussion has taken place between experts. Here are their final opinions:"
        ]

        for model, response in last_responses.items():
            model_info = self.model_manager.get_model_info(model)
            role = model_info.get("role", "assistant") if model_info else "assistant"

            synthesis_prompt.append(f"\n--- {role} expert ---")
            synthesis_prompt.append(response)

        synthesis_prompt.append("\nPlease synthesize the above opinions into a comprehensive and balanced answer.")

        # Use a model for synthesis
        synthesis_model = self._select_synthesis_model(last_responses.keys())

        try:
            result = self.model_manager.get_response(
                synthesis_model,
                "\n".join(synthesis_prompt),
                self.system_prompt,
                {"temperature": 0.5, "max_tokens": 1536}
            )

            return result.get("response", "Failed to synthesize response.")

        except Exception as e:
            logger.error(f"Error synthesizing response: {e}")

            # Fallback: combine responses
            combined_response = "\n\n".join([
                f"From {self.model_manager.get_model_info(model).get('role', 'expert') if self.model_manager.get_model_info(model) else 'expert'} perspective:\n{response}"
                for model, response in last_responses.items()
            ])

            return combined_response

    def _select_synthesis_model(self, participating_models: List[str]) -> str:
        """
        Select model for final response synthesis

        Args:
            participating_models: List of participating models

        Returns:
            Selected model name
        """
        # Prefer models with deep_thinking role
        all_models = self.model_manager.list_models()

        for model in all_models:
            model_info = self.model_manager.get_model_info(model)
            if model_info and model_info.get("role") == "deep_thinking":
                return model

        # Fallback: random selection from participants
        if participating_models:
            return random.choice(list(participating_models))

        # Default: first available model
        return all_models[0] if all_models else "deepseek-r1:8b"

    def _save_discussion(self, discussion_id: str, query: str,
                       discussion_log: List[Dict[str, Any]], final_response: str) -> None:
        """
        Save discussion

        Args:
            discussion_id: Discussion ID
            query: Original query
            discussion_log: Discussion log
            final_response: Final response
        """
        # Save to memory
        self.discussions[discussion_id] = {
            "id": discussion_id,
            "query": query,
            "log": discussion_log,
            "final_response": final_response,
            "timestamp": time.time()
        }

    def get_discussion(self, discussion_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve discussion information

        Args:
            discussion_id: Discussion ID

        Returns:
            Discussion information dictionary or None if not found
        """
        return self.discussions.get(discussion_id)

    def list_discussions(self) -> List[str]:
        """
        List all discussion IDs

        Returns:
            List of discussion IDs
        """
        return list(self.discussions.keys())

    def clear_discussions(self) -> None:
        """Clear all discussion data"""
        self.discussions.clear()