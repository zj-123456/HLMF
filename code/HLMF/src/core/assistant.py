"""
Module for Personal Assistant basic Class
"""

import os
import time
import json
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

from src.core.models import ModelManager

logger = logging.getLogger(__name__)

class PersonalAssistant:
    """
    Personal Assistant System:
    - Managing conversation.
    - Query routing to the right model
    - Keeping conversational history
    - Managing the context
    """

    def __init__(self, model_manager: ModelManager, config: Dict[str, Any]):
        """
        Personal Assistant Initializes

        Args:
        model_manager: Model management subjects
        config: Systematic configuration

        """
        self.model_manager = model_manager
        self.config = config
        self.assistant_config = config.get("assistant", {})

        # Take the configuration
        self.default_max_tokens = self.assistant_config.get("default_max_tokens", 1024)
        self.default_temperature = self.assistant_config.get("default_temperature", 0.7)
        self.conversation_history_limit = self.assistant_config.get("conversation_history_limit", 100)

        # The conversational pathways
        self.conversation_dir = config.get("system", {}).get(
            "conversation_dir", "data/conversations")
        os.makedirs(self.conversation_dir, exist_ok=True)

        # The History of ID Conversation
        self.conversations = {}

        logger.info("Started the Personal Assistant")

    def get_response(self, query: str, conversation_id: Optional[str] = None,
                    user_info: Optional[Dict] = None, model_name: Optional[str] = None,
                    system_prompt: Optional[str] = None,
                    params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get response to query

        Args:
            query: User query
            conversation_id: ID of the conversation (optional)
            user_info: Information about the user (optional)
            model_name: Name of the model to use (optional)
            system_prompt: Override system prompt (optional)
            params: Additional parameters for the model (optional)

        Returns:
            Dict containing the response and additional information
        """
        start_time = time.time()

        # Create conversation ID if not provided
        if not conversation_id:
            conversation_id = f"conv_{int(time.time())}"

        # Initialize conversation history if not existing
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        # Prepare model parameters
        model_params = {
            "temperature": self.default_temperature,
            "max_tokens": self.default_max_tokens
        }

        # Override parameters if provided
        if params:
            model_params.update(params)

        # Select default model if not specified
        #模型自动选择是根据问题类型评估出来的
        if not model_name:
            model_name = self._select_default_model()#

        # Create prompt with conversation history#帮助 AI 进行上下文连续对话。
        prompt_with_history = self._create_prompt_with_history(
            query, conversation_id, user_info)#需要

        # Get response from model
        response = self.model_manager.get_response(
            model_name, prompt_with_history, system_prompt, model_params)

        # Update conversation history
        self._update_conversation_history(
            conversation_id, query, response.get("response", ""))

        # Save conversation#保存json文件
        self._save_conversation(conversation_id)

        # Add additional information to the result
        response["conversation_id"] = conversation_id
        response["query"] = query
        response["total_time"] = time.time() - start_time

        return response

    def _select_default_model(self) -> str:
        """
        Select default model

        Returns:
            Name of the default model
        """
        # Get list of models
        models = self.model_manager.list_models()

        # Use the first model if available
        if models:
            return models[0]

        # Default
        return "deepseek-r1:1.5b"#"deepseek-r1:1.5b"

    def _create_prompt_with_history(self, query: str, conversation_id: str,
                                  user_info: Optional[Dict] = None) -> str:
        """
        Create prompt including conversation history

        Args:
            query: User query
            conversation_id: ID of the conversation
            user_info: Information about the user (optional)

        Returns:
            Complete prompt
        """
        # Get conversation history
        history = self.conversations.get(conversation_id, [])

        # Limit history length
        limited_history = history[-self.conversation_history_limit:] if history else []

        # Create prompt with history
        prompt_parts = []

        # Add user info if available
        if user_info:
            user_context = f"User Information: {json.dumps(user_info, ensure_ascii=False)}"
            prompt_parts.append(user_context)

        # Add conversation history
        for entry in limited_history:
            if entry["role"] == "user":
                prompt_parts.append(f"User: {entry['content']}")
            else:
                prompt_parts.append(f"Assistant: {entry['content']}")

        # Add current query
        prompt_parts.append(f"User: {query}")
        prompt_parts.append("Assistant:")

        return "\n\n".join(prompt_parts)

    def _update_conversation_history(self, conversation_id: str,
                                     query: str, response: str) -> None:
        """
        Update conversation history

        Args:
            conversation_id: ID of the conversation
            query: User query
            response: Assistant's response
        """
        # Ensure conversation_id exists
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        # Add query and response
        self.conversations[conversation_id].append({
            "role": "user",
            "content": query,
            "timestamp": time.time()
        })

        self.conversations[conversation_id].append({
            "role": "assistant",
            "content": response,
            "timestamp": time.time()
        })

    def _save_conversation(self, conversation_id: str) -> None:
        """
        Save conversation to file

        Args:
            conversation_id: ID of the conversation
        """
        try:
            conversation = self.conversations.get(conversation_id, [])
            if not conversation:
                return

            file_path = os.path.join(self.conversation_dir, f"{conversation_id}.json")

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "id": conversation_id,
                    "updated_at": time.time(),
                    "messages": conversation
                }, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Error saving conversation {conversation_id}: {e}")

    def load_conversation(self, conversation_id: str) -> bool:
        """
        Load conversation from file

        Args:
            conversation_id: ID of the conversation

        Returns:
            True if successfully loaded, False otherwise
        """
        try:
            file_path = os.path.join(self.conversation_dir, f"{conversation_id}.json")

            if not os.path.exists(file_path):
                return False

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.conversations[conversation_id] = data.get("messages", [])
            return True

        except Exception as e:
            logger.error(f"Error loading conversation {conversation_id}: {e}")
            return False

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history

        Args:
            conversation_id: ID of the conversation

        Returns:
            List of conversation exchanges
        """
        # Load conversation if not in memory
        if conversation_id not in self.conversations:
            self.load_conversation(conversation_id)

        return self.conversations.get(conversation_id, []).copy()

    def list_conversations(self) -> List[str]:
        """
        Retrieve a list of saved conversation IDs

        Returns:
            List of conversation IDs
        """
        try:
            files = os.listdir(self.conversation_dir)
            conversation_ids = [f.replace(".json", "") for f in files if f.endswith(".json")]
            return conversation_ids

        except Exception as e:
            logger.error(f"Error retrieving conversation list: {e}")
            return []

    def clear_conversation(self, conversation_id: str) -> bool:
        """
        Delete conversation history

        Args:
            conversation_id: ID of the conversation

        Returns:
            True if successfully deleted, False otherwise
        """
        try:
            # Remove from memory
            if conversation_id in self.conversations:
                del self.conversations[conversation_id]

            # Delete file
            file_path = os.path.join(self.conversation_dir, f"{conversation_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)

            return True

        except Exception as e:
            logger.error(f"Error deleting conversation {conversation_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Retrieve assistant statistics

        Returns:
            Dict containing statistics
        """
        try:
            # Count total conversations
            conversation_files = self.list_conversations()

            # Count total exchanges
            total_exchanges = 0
            for conv_id in self.conversations.keys():
                total_exchanges += len(self.conversations[conv_id]) // 2

            # Get statistics from model manager
            model_stats = self.model_manager.get_performance_stats()

            return {
                "total_conversations": len(conversation_files),
                "active_conversations": len(self.conversations),
                "total_exchanges": total_exchanges,
                "model_stats": model_stats
            }

        except Exception as e:
            logger.error(f"Error retrieving statistics: {e}")
            return {}