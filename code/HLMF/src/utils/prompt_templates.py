"""
Manage prompt templates for the system.
Provide utilities to load, customize, and use prompt templates.
"""

import os
import yaml
import logging
import re
from typing import Dict, Any, Optional, List, Union
from string import Template

logger = logging.getLogger(__name__)

class PromptTemplate:
    """Class to manage and customize prompt templates."""

    def __init__(self, template_str: str):
        """
        Initialize prompt template.

        Args:
            template_str: Template string
        """
        self.template_str = template_str
        self.template = Template(template_str)

    def format(self, **kwargs) -> str:
        """
        Format the template with parameters.

        Args:
            **kwargs: Parameters to replace in the template

        Returns:
            Formatted string
        """
        try:
            return self.template.substitute(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing parameter {e} when formatting prompt template")
            # Use safe_substitute to avoid errors when a parameter is missing
            return self.template.safe_substitute(**kwargs)

    def __str__(self) -> str:
        """Get the template string."""
        return self.template_str


class PromptLibrary:
    """Library to manage prompt templates."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the prompt template library.

        Args:
            config: System configuration
        """
        self.config = config
        self.templates = {}
        self.load_templates()

    def load_templates(self) -> None:
        """Load prompt templates from configuration file."""
        config_dir = self.config.get("system", {}).get("config_dir", "config")
        template_path = os.path.join(config_dir, "prompt_templates.yml")

        if os.path.exists(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    templates_config = yaml.safe_load(f)

                if templates_config and isinstance(templates_config, dict):
                    for role, role_templates in templates_config.items():
                        if isinstance(role_templates, dict):
                            self.templates[role] = {}
                            for template_name, template_str in role_templates.items():
                                if isinstance(template_str, str):
                                    self.templates[role][template_name] = PromptTemplate(template_str)

                    logger.info(f"Loaded {self._count_templates()} prompt templates from {template_path}")
                else:
                    logger.warning(f"Prompt template file is not in the correct format: {template_path}")
                    self._load_default_templates()
            except Exception as e:
                logger.error(f"Error loading prompt templates from {template_path}: {e}")
                self._load_default_templates()
        else:
            logger.warning(f"Prompt template file not found: {template_path}")
            self._load_default_templates()

    def _count_templates(self) -> int:
        """
        Count the total number of loaded prompt templates.

        Returns:
            Number of templates
        """
        count = 0
        for role, templates in self.templates.items():
            count += len(templates)
        return count

    def _load_default_templates(self) -> None:
        """Load default prompt templates."""
        self.templates = {
            "qwq_32b_nothink": {
                "default": PromptTemplate(
                    "Please reflect deeply on the following question, evaluate it from multiple aspects, and provide "
                    "a balanced, comprehensive, and thoughtful response:\n${query}\n\n"
                    "In your answer, please:\n"
                    "1. Provide a multi-faceted analysis\n"
                    "2. Consider contradictions and paradoxes\n"
                    "3. Connect to a broader context\n"
                    "4. Consider both short-term and long-term consequences\n"
                    "5. Provide a well-thought-out and balanced conclusion"
                )
            },
            "gemma3_27b": {
                "default": PromptTemplate(
                    "Please reflect deeply on the following question, evaluate it from multiple aspects, and provide "
                    "a balanced, comprehensive, and thoughtful response:\n${query}\n\n"
                    "In your answer, please:\n"
                    "1. Provide a multi-faceted analysis\n"
                    "2. Consider contradictions and paradoxes\n"
                    "3. Connect to a broader context\n"
                    "4. Consider both short-term and long-term consequences\n"
                    "5. Provide a well-thought-out and balanced conclusion"
                )
            },
            "deepseek_r1_32b_nothink": {
                "default": PromptTemplate(
                    "Please reflect deeply on the following question, evaluate it from multiple aspects, and provide "
                    "a balanced, comprehensive, and thoughtful response:\n${query}\n\n"
                    "In your answer, please:\n"
                    "1. Provide a multi-faceted analysis\n"
                    "2. Consider contradictions and paradoxes\n"
                    "3. Connect to a broader context\n"
                    "4. Consider both short-term and long-term consequences\n"
                    "5. Provide a well-thought-out and balanced conclusion"
                )
            },
            "group_discussion": {
                "default": PromptTemplate(
                    "Please think carefully about the following issue from multiple perspectives, consider technical aspects, "
                    "analyze in-depth, and present clearly:\n${query}\n\n"
                    "In your answer, please:\n"
                    "1. Provide both technical information and in-depth analysis\n"
                    "2. Consider different viewpoints\n"
                    "3. Propose practical and evidence-based solutions\n"
                    "4. Balance technical detail with accessibility\n"
                    "5. Summarize into a comprehensive and coherent response"
                )
            }
        }
        logger.info(f"Loaded {self._count_templates()} default prompt templates")

    def get_template(self, role: str, template_name: str = "default") -> Optional[PromptTemplate]:
        """
        Get a prompt template by role and name.

        Args:
            role: The model's role
            template_name: Template name

        Returns:
            PromptTemplate object or None if not found
        """
        if role in self.templates and template_name in self.templates[role]:
            return self.templates[role][template_name]

        # Fallback to the default template if specific template is not found
        if role in self.templates and "default" in self.templates[role]:
            logger.debug(f"Template '{template_name}' not found for role '{role}', using the default template")
            return self.templates[role]["default"]

        logger.warning(f"No template found for role '{role}'")
        return None

    def format_prompt(self, role: str, template_name: str = "default", **kwargs) -> str:
        """
        Format the prompt with the given parameters.

        Args:
            role: The model's role
            template_name: Template name
            **kwargs: Parameters to replace

        Returns:
            Formatted string or returns the original query if no template found
        """
        template = self.get_template(role, template_name)

        if template:
            return template.format(**kwargs)

        # If no template is found, return the original query
        if "query" in kwargs:
            logger.warning(f"No matching template found, returning the original query")
            return kwargs["query"]

        # Nothing to return
        logger.error("Cannot format prompt: no template found and no query")
        return ""

    def get_system_prompt(self, role: str) -> str:
        """
        Get the system prompt for the specified role.

        Args:
            role: The model's role

        Returns:
            System prompt
        """
        models_config = self.config.get("models", [])

        for model_config in models_config:
            if model_config.get("role") == role:
                return model_config.get("system_prompt", "")

        # Fallback to the default system prompt if not found
        if role == "qwq_32b_nothink":
            return "You are an AI specializing in critical thinking and deep analysis."
        elif role == "gemma3_27b":
            return "You are an AI specializing in critical thinking and deep analysis."
        elif role == "deepseek_r1_32b_nothink":
            return "You are an AI specializing in critical thinking and deep analysis."
        elif role == "group_discussion":
            return "You are an information synthesizer assistant, tasked with providing the final response based on group discussion."

        return ""

def load_prompt_library(config: Dict[str, Any]) -> PromptLibrary:
    """
    Load the prompt library.

    Args:
        config: System configuration

    Returns:
        PromptLibrary object
    """
    return PromptLibrary(config)
