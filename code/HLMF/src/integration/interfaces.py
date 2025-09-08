"""
A common interface to the system.
Offers Factory methods and utilities to create and configuration components.
"""

import os
import logging
import yaml
from typing import Dict, Optional, Any

from src.core.models import ModelManager
from src.core.assistant import PersonalAssistant
from src.core.group_discussion import GroupDiscussionManager
from src.optimization.manager import FeedbackOptimizationManager
from src.integration.enhanced_assistant import EnhancedPersonalAssistant

logger = logging.getLogger(__name__)

class AssistantFactory:
    """Factory to create and configure assistant objects."""
    
    @staticmethod
    def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from the YAML file.

        Args:
            config_path: Path to configuration file (None for default)

        Returns:
            Dict containing system configuration
        """
        if config_path is None:
            config_dir = os.environ.get("CONFIG_DIR", "config")
            config_path = os.path.join(config_dir, "default.yml")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # Load additional configuration files
            config_dir = os.path.dirname(config_path)

            # Load models configuration
            models_path = os.path.join(config_dir, "models.yml")
            if os.path.exists(models_path):
                with open(models_path, 'r', encoding='utf-8') as f:
                    models_config = yaml.safe_load(f)
                if models_config:
                    config["models"] = models_config.get("models", [])
                    if "group_discussion" in models_config:
                        config["group_discussion"] = models_config["group_discussion"]

            # Load optimization configuration
            optimization_path = os.path.join(config_dir, "optimization.yml")
            if os.path.exists(optimization_path):
                with open(optimization_path, 'r', encoding='utf-8') as f:
                    optimization_config = yaml.safe_load(f)
                if optimization_config:
                    config["optimization"] = optimization_config

            # Set paths to the configuration directory
            if "system" not in config:
                config["system"] = {}
            config["system"]["config_dir"] = config_dir

            logger.info(f"Loaded configuration from {config_path}")
            return config

        except Exception as e:
            logger.error(f"Failed to load configuration from {config_path}: {e}")
            # Return minimal configuration
            return {
                "system": {
                    "version": "1.0.0",
                    "config_dir": config_dir if 'config_dir' in locals() else "config"
                }
            }

    @staticmethod
    def create_model_manager(config: Dict[str, Any]) -> ModelManager:
        """
        Create a model manager object.

        Args:
            config: System configuration

        Returns:
            Configured ModelManager object
        """
        try:
            model_manager = ModelManager(config)
            return model_manager
        except Exception as e:
            logger.error(f"Error creating ModelManager: {e}")
            raise

    @staticmethod
    def create_base_assistant(config: Dict[str, Any], model_manager: ModelManager) -> PersonalAssistant:
        """
        Create a base assistant object.

        Args:
            config: System configuration
            model_manager: Model manager object

        Returns:
            Configured PersonalAssistant object
        """
        try:
            assistant = PersonalAssistant(model_manager, config)
            return assistant
        except Exception as e:
            logger.error(f"Error creating PersonalAssistant: {e}")
            raise

    @staticmethod
    def create_group_discussion_manager(config: Dict[str, Any], model_manager: ModelManager) -> GroupDiscussionManager:
        """
        Create a group discussion manager object.

        Args:
            config: System configuration
            model_manager: Model manager object

        Returns:
            Configured GroupDiscussionManager object
        """
        try:
            group_manager = GroupDiscussionManager(model_manager, config)
            return group_manager
        except Exception as e:
            logger.error(f"Error creating GroupDiscussionManager: {e}")
            raise

    @staticmethod
    def create_feedback_optimization_manager(config: Dict[str, Any]) -> FeedbackOptimizationManager:
        """
        Create a feedback optimization manager object.

        Args:
            config: System configuration

        Returns:
            Configured FeedbackOptimizationManager object
        """
        try:
            feedback_manager = FeedbackOptimizationManager(config)
            return feedback_manager
        except Exception as e:
            logger.error(f"Error creating FeedbackOptimizationManager: {e}")
            raise

    @staticmethod
    def create_enhanced_assistant(config: Dict[str, Any]) -> EnhancedPersonalAssistant:
        """
        Create an enhanced assistant object integrating all components.

        Args:
            config: System configuration

        Returns:
            Configured EnhancedPersonalAssistant object
        """
        try:
            # Create necessary components
            model_manager = AssistantFactory.create_model_manager(config)
            base_assistant = AssistantFactory.create_base_assistant(config, model_manager)
            group_manager = AssistantFactory.create_group_discussion_manager(config, model_manager)
            feedback_manager = AssistantFactory.create_feedback_optimization_manager(config)

            # Create enhanced assistant
            enhanced_assistant = EnhancedPersonalAssistant(
                base_assistant=base_assistant,
                group_discussion_manager=group_manager,
                feedback_manager=feedback_manager,
                config=config
            )

            # Configure optimization
            optimization_config = config.get("optimization", {})
            if not optimization_config.get("enabled", True):
                enhanced_assistant.toggle_optimization(False)

            if not optimization_config.get("auto_select_model", True):
                enhanced_assistant.toggle_auto_select_model(False)

            feedback_config = optimization_config.get("feedback", {})
            if not feedback_config.get("enabled", True):
                enhanced_assistant.toggle_feedback_collection(False)

            logger.info("Successfully created EnhancedPersonalAssistant")
            return enhanced_assistant

        except Exception as e:
            logger.error(f"Error creating EnhancedPersonalAssistant: {e}")
            raise


def setup_assistant(config_path: Optional[str] = None) -> EnhancedPersonalAssistant:
    """
    Utility function to create and configure an enhanced assistant.

    Args:
        config_path: Path to configuration file (None for default)

    Returns:
        Configured EnhancedPersonalAssistant object
    """
    try:
        # Load configuration
        config = AssistantFactory.load_config(config_path)

        # Create enhanced assistant
        assistant = AssistantFactory.create_enhanced_assistant(config)

        return assistant

    except Exception as e:
        logger.error(f"Error setting up assistant: {e}")
        raise