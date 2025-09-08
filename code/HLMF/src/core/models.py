"""
Module to manage the AI model and interact with the Ollama API
"""

import os
import time
import json
import logging
import requests
from typing import Dict, List, Any, Optional, Tuple, Union

logger = logging.getLogger(__name__)

class ModelManager:
    """
    Manage the AI model and interact with Ollama API.
    Support:
    - Download and manage the model
    - Consulting Ollama API
    - Buffer management and Retry Logic.
    - tracking performance models
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Model Manager.

        Args:
        Config: Systematic configuration
        """
        self.config = config
        self.ollama_config = config.get("ollama", {})

        # Ollama API configuration
        self.base_url = self.ollama_config.get("base_url", "http://localhost:11434")
        self.timeout = self.ollama_config.get("timeout", 30)
        self.retry_attempts = self.ollama_config.get("retry_attempts", 3)

        # The list of models
        self.models = self._load_models()

        # Buffers for query results
        self.response_cache = {}

        # The performance information
        self.performance_stats = {}

        logger.info(f"started ModelManager with {len(self.models)} model")

    def _load_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Downloading the models from the configuration

        Returns:
        Forbids the information on patterns
        """
        models_dict = {}

        # Load from configuration
        models_config = self.config.get("models", [])
        for model_config in models_config:
            model_name = model_config.get("name")
            if model_name:
                models_dict[model_name] = model_config

        return models_dict

    def list_models(self) -> List[str]:
        """
        Take a list of existing models

        Returns:
        The list of models
        """
        return list(self.models.keys())

    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        To get the model information

        Args:
        Model_name: Model name

        Returns:
        Dict contains the model information or None if not found
        """
        return self.models.get(model_name)

    def get_response(self, model_name: str, prompt: str,
                   system_prompt: Optional[str] = None,
                   params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Take the answers from the model

        Args:
        Model_name: Model name
        Prompt: Query the user
        System_prompt: System prompt (optional)
        Params: Additional parameter (optional)

        Returns:
        Dict contains answers and additional information
        """
        # To test whether the model exists
        if model_name not in self.models:
            return {
                "response": f"Error: The model '{model_name}' doesn't exist.",
                "error": f"Model '{model_name}' not found",
                "success": False
            }

        # Take the System Prompt from the model configuration if not provided
        if system_prompt is None:
            system_prompt = self.models[model_name].get("system_prompt", "")

        # Prepare its parameters.
        model_params = {
            "temperature": self.config.get("assistant", {}).get("default_temperature", 0.7),
            "max_tokens": self.config.get("assistant", {}).get("default_max_tokens", 1024)
        }

        # Overwriting the parameter if supplied
        if params:
            model_params.update(params)

        # Check the buffer
        cache_key = f"{model_name}:{system_prompt}:{prompt}:{json.dumps(model_params)}"
        if cache_key in self.response_cache:
            return self.response_cache[cache_key]

        # Send a query to API.
        start_time = time.time()
        try:
            response = self._query_ollama(model_name, prompt, system_prompt, model_params)

            # Time completed.
            completion_time = time.time() - start_time

            # Return Results
            result = {
                "response": response.get("response", ""),
                "model": model_name,
                "completion_time": completion_time,
                "success": True,
                "tokens": response.get("eval_count", 0)
            }

            # Performance statistics updated#更新模型的性能统计信息，包括执行时间和评估计数。
            self._update_performance_stats(model_name, completion_time,
                                         response.get("eval_count", 0))

            # Stored in the buffer
            self.response_cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Faulty retrieval of the answer from the model {model_name}: {e}")

            # Results of error
            error_result = {
                "response": f"Sorry, there was an error in handling the request. Detail: {str(e)}",
                "error": str(e),
                "model": model_name,
                "completion_time": time.time() - start_time,
                "success": False
            }

            return error_result

    def _query_ollama(self, model_name: str, prompt: str,
                      system_prompt: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends a query to Ollama API

        Args:
        model_name: Model name
        prompt: Query the user
        system_prompt: System prompt
        params: Model parameters

        Returns:
        Dict containing results from API
        """
        # Force JSON format
        # formatted_prompt = f"""Please respond strictly in the following JSON format:
        # {{
        #     "response": "content",
        #     "status": "success"
        # }}
        # User request: {prompt}"""
        #"detail": "additional info"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": True,  # Enable streaming response
            "format": "json",
            "options": {
                "temperature": params.get("temperature", 0.7),
                "num_ctx": 2048
            }
        }

        # Additional System Prompt if available
        if system_prompt:
            payload["system"] = system_prompt

        # Endpoint
        endpoint = f"{self.base_url}/api/generate"

        # Retry logic
        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(
                    endpoint,
                    json=payload,
                    timeout=self.timeout,
                    stream=True  # Ensure streaming
                )

                response.raise_for_status()

                # Collect streamed response content
                full_response = ""
                for chunk in response.iter_lines(decode_unicode=True):
                    if chunk:
                        data = json.loads(chunk)
                        # Add each piece of the response
                        if "response" in data:
                            full_response += data["response"]

                # Return full response after stream
                return {
                    "response": full_response,
                    "status": "success"
                }

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout when it connects to Ollama (time {attempt + 1}/{self.retry_attempts})")
                if attempt == self.retry_attempts - 1:
                    raise
                time.sleep(1)

            except requests.exceptions.RequestException as e:
                logger.error(f"Error on connecting to Ollama: {e}")
                raise

        raise Exception("Not connected to Ollama API after many attempts")

    def _update_performance_stats(self, model_name: str, completion_time: float,
                                token_count: int) -> None:
        """
        Update model performance statistics

        Args:
            model_name: Model name
            completion_time: Completion time (seconds)
            token_count: Number of tokens processed
        """
        if model_name not in self.performance_stats:
            self.performance_stats[model_name] = {
                "count": 0,
                "total_time": 0,
                "total_tokens": 0,
                "avg_time": 0,
                "avg_tokens": 0,
                "tokens_per_second": 0
            }

        stats = self.performance_stats[model_name]
        stats["count"] += 1
        stats["total_time"] += completion_time
        stats["total_tokens"] += token_count

        # Update average values
        stats["avg_time"] = stats["total_time"] / stats["count"]
        stats["avg_tokens"] = stats["total_tokens"] / stats["count"]

        # Token processing speed
        if completion_time > 0:
            stats["tokens_per_second"] = token_count / completion_time

    def get_performance_stats(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get model performance statistics

        Args:
            model_name: Specific model name (optional)

        Returns:
            Dict containing performance statistics
        """
        if model_name:
            return self.performance_stats.get(model_name, {})
        return self.performance_stats

    def clear_cache(self) -> None:
        """Clear response cache"""
        self.response_cache.clear()

    def reset_stats(self) -> None:
        """Reset performance statistics"""
        self.performance_stats.clear()