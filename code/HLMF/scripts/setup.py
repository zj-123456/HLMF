#!/usr/bin/env python
"""
Script to set up the environment for the personal assistant system
Execution:
1. Install dependent libraries
2. Create necessary directories
3. Create default configuration file
4. Set up development environment
"""

import os
import sys
import subprocess
import argparse
import logging
import shutil
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Setting up the environment for the personal assistant system")
    parser.add_argument("--config-dir", type=str, default="config",
                        help="Configuration directory")
    parser.add_argument("--data-dir", type=str, default="data",
                        help="Data directory")
    parser.add_argument("--logs-dir", type=str, default="logs",
                        help="Log directory")
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434",
                        help="URL of Ollama API")
    parser.add_argument("--dev", action="store_true",
                        help="Setting up the development environment")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing configuration files")
    parser.add_argument("--no-deps", action="store_true",
                        help="Do not install dependent libraries")
    parser.add_argument("--log-level", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging level")
    
    return parser.parse_args()

def setup_logging(log_level: str) -> logging.Logger:
    """
    Logging settings

    Args:
    log_level: Logging level

    Returns:
    Logger object
    """
    # Convert level name to value
    numeric_level = getattr(logging, log_level)

    # Log format
    numeric_level = getattr(logging, log_level)

    # Định dạng log
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Set up logging
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler()]
    )
    
    return logging.getLogger("setup")

def create_directories(dirs: List[str], logger: logging.Logger) -> None:
    """
    Create the required directories

    Args:
    dirs: List of directories to create
    logger: Logger object
    """
    for dir_path in dirs:
        try:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                logger.info(f"Created directory: {dir_path}")
            else:
                logger.debug(f"Directory already exists: {dir_path}")
        except Exception as e:
            logger.error(f"Error creating directory {dir_path}: {e}")

def install_dependencies(dev_mode: bool, logger: logging.Logger) -> bool:
    """
    Install dependent libraries

    Args:
    dev_mode: True if setting up a development environment
    logger: Logger object

    Returns:
    True if installation was successful, False otherwise
    """
    requirements_file = "requirements.txt"
    dev_requirements_file = "requirements-dev.txt"
    
    try:
        # Check pip
        try:
            subprocess.run([sys.executable, "-m", "pip", "--version"], 
                        check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("pip not found or pip not working")
            return False

        # Installing core libraries
        if os.path.exists(requirements_file):
            logger.info(f"Installing libraries from {requirements_file}...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", requirements_file],
                    check=True, text=True
                )
                logger.info("Installing core libraries")
            except subprocess.CalledProcessError as e:
                logger.error(f"Error installing from {requirements_file}: {e}")
                return False
        else:
            logger.warning(f"File {requirements_file} not found")

            # Install essential libraries
            essential_packages = [
                "requests", "pyyaml", "tqdm", "matplotlib", "pandas", 
                "numpy", "colorama", "rich"
            ]
            logger.info(f"Installing essential libraries...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install"] + essential_packages,
                    check=True, text=True
                )
                logger.info("Essential libraries installed")
            except subprocess.CalledProcessError as e:
                logger.error(f"Error installing essential libraries: {e}")
                return False

        # Install development libraries (if required)
        if dev_mode:
            if os.path.exists(dev_requirements_file):
                logger.info(f"Installing development libraries from {dev_requirements_file}...")
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "-r", dev_requirements_file],
                        check=True, text=True
                    )
                    logger.info("Development libraries installed")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Error installing from {dev_requirements_file}: {e}")
                    return False
            else:
                logger.warning(f"File {dev_requirements_file} not found")

                # Install essential development libraries
                dev_packages = [
                    "pytest", "flake8", "black"
                ]
                logger.info(f"Installing essential development libraries...")
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install"] + dev_packages,
                        check=True, text=True
                    )
                    logger.info("Installing essential development libraries")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Error installing development libraries: {e}")
                    return False

        logger.info("Installing dependent libraries successfully")
        return True

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

def create_default_config(config_dir: str, data_dir: str, logs_dir: str,
                         ollama_url: str, force: bool, logger: logging.Logger) -> bool:
    """
    Create default configuration files

    Args:
    config_dir: Configuration directory
    data_dir: Data directory
    logs_dir: Log directory
    ollama_url: Ollama API URL
    force: True if overwrite existing files
    logger: Logger object

    Returns:
    True if creation was successful, False otherwise
    """
    try:
        # 1. Create default.yml
        default_config = {
            "system": {
                "version": "1.0.0",
                "log_level": "INFO",
                "log_file": os.path.join(logs_dir, "assistant.log"),
                "data_dir": data_dir,
                "feedback_db": os.path.join(data_dir, "feedback.db"),
                "conversation_dir": os.path.join(data_dir, "conversations"),
                "rlhf_export_dir": os.path.join(data_dir, "rlhf_exports"),
                "config_dir": config_dir
            },
            "ollama": {
                "base_url": ollama_url,
                "timeout": 30,
                "retry_attempts": 3
            },
            "assistant": {
                "default_max_tokens": 1024,
                "default_temperature": 0.7,
                "conversation_history_limit": 100
            },
            "group_discussion": {
                "name": "group_discussion",
                "system_prompt": "This is the result of a group discussion between different AI experts. Each expert contributed from their own area of ​​expertise, and the results were compiled into a comprehensive answer.\n",
                "strengths": {
                    "comprehensive": 0.9,
                    "balanced": 0.88,
                    "thorough": 0.85,
                    "creative": 0.8,
                    "problem_solving": 0.88,
                    "language": 0.85
                },
                "default_rounds": 2
            },
            "optimization": {
                "enabled": True,
                "auto_select_model": True,
                "check_group_discussion_suitability": True,
                "improve_system_prompt": True,
                "improve_user_prompt": True,
                "feedback": {
                    "enabled": True,
                    "collection_probability": 0.3,
                    "collect_comparisons": True,
                    "min_samples_for_update": 5,
                    "feedback_cache_size": 1000,
                    "feedback_collection_methods": ["cli_prompt", "api"],
                    "initial_feedback_boost": True
                },
                "preference": {
                    "weight_update_factor": 0.1,
                    "win_rate_weight": 0.7,
                    "score_weight": 0.3,
                    "default_weight": 1.0,
                    "min_weight": 0.5,
                    "max_weight": 2.0,
                    "periodic_update": True,
                    "update_interval": 10,
                    "smooth_updates": True
                },
                "query_analysis": {
                    "use_cached_categories": True,
                    "category_similarity_threshold": 0.85,
                    "keyword_weighting": True,
                    "complex_query_threshold": 1.8
                },
                "prompt_optimization": {
                    "template_selection_strategy": "best_match",
                    "max_prompt_token_count": 2048,
                    "dynamic_instruction_tuning": True,
                    "instruction_history_window": 20
                },
                "system_prompt_optimization": {
                    "append_only": True,
                    "max_additions": 3,
                    "max_tokens": 512,
                    "instruction_categories": [
                        "performance", "quality", "tone", "format", "domain_specific"
                    ]
                }
            },
            "api": {
                "enabled": False,
                "port": 8000,
                "host": "127.0.0.1",
                "auth_required": True
            }
        }
        
        default_config_path = os.path.join(config_dir, "default.yml")
        if not os.path.exists(default_config_path) or force:
            with open(default_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            logger.info(f"Default configuration file created: {default_config_path}")
        else:
            logger.debug(f"Configuration file already exists: {default_config_path}")
        
        # 2. Create models.yml
        models_config = {
            "models": [
                {
                    "name": "qwen2.5-coder:7b",
                    "role": "code",
                    "system_prompt": "You are a professional programmer assistant. Your tasks are to write high-quality source code, provide technical solutions, debug and optimize code. Focus on clean code, performance, and security principles. Always provide detailed explanations with the source code.\n",
                    "strengths": {
                        "programming": 0.95,
                        "algorithms": 0.9,
                        "technical_explanation": 0.85,
                        "math": 0.8,
                        "problem_solving": 0.85,
                        "language": 0.75
                    }
                },
                {
                    "name": "deepseek-r1:8b",
                    "role": "deep_thinking",
                    "system_prompt": "You are an AI who specializes in critical thinking and deep analysis. Look at problems from multiple perspectives, evaluate arguments, analyze logic, find potential contradictions, and draw well-founded conclusions. Apply systems thinking and multidimensional thinking to solve complex problems.\n",
                    "strengths": {
                        "analysis": 0.95,
                        "critical_thinking": 0.9,
                        "reasoning": 0.92,
                        "evaluation": 0.88,
                        "problem_solving": 0.85,
                        "language": 0.8
                    }
                },
                {
                    "name": "deepseek-r1:1.5b",
                    "role": "llm",
                    "system_prompt": "You are a concise, linguistic AI assistant focused on responding quickly and efficiently. Provide information that is short, concise, and to the point. Prioritize accuracy and speed. You are good at summarizing complex information into easy-to-understand key points.\n",
                    "strengths": {
                        "language": 0.9,
                        "conciseness": 0.95,
                        "clarity": 0.85,
                        "summarization": 0.92,
                        "general_knowledge": 0.75,
                        "communication": 0.88
                    }
                }
            ]
        }
        
        models_config_path = os.path.join(config_dir, "models.yml")
        if not os.path.exists(models_config_path) or force:
            with open(models_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(models_config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            logger.info(f"Model configuration file created: {models_config_path}")
        else:
            logger.debug(f"Model configuration file already exists: {models_config_path}")
        
        # 3. Tạo prompt_templates.yml
        prompt_templates = {
            "templates": [
                {
                    "name": "general",
                    "description": "A general prompt template suitable for most questions",
                    "domains": ["general"],
                    "complexity": "medium",
                    "use_cases": ["general", "question", "statement"],
                    "template": "{query}"
                },
                {
                    "name": "programming",
                    "description": "Template prompt for programming and coding questions",
                    "domains": ["technology", "programming"],
                    "complexity": "high",
                    "use_cases": ["how_to", "code", "technical_explanation"],
                    "template": "Please solve the following programming problem. Provide complete, clear code with detailed comments:\n\n{query}\n\nMake sure your code is:\n- Readable and follows clean code principles\n- Algorithmically and resource-efficient\n- Handles exceptions and invalid input\n- Uses best practices for {languages}"
                },
                {
                    "name": "step_by_step",
                    "description": "Template prompt asking for step-by-step explanation",
                    "domains": ["general"],
                    "complexity": "medium",
                    "use_cases": ["how_to", "explanation", "reasoning"],
                    "template": "Please explain step-by-step in detail:\n\n{query}\n\nProvide clear, sequential instructions so I can fully understand the process and logic. If appropriate, explain the reasoning for each step."
                },
                {
                    "name": "creative",
                    "description": "Prompt template for creative content",
                    "domains": ["creative", "writing", "arts"],
                    "complexity": "high",
                    "use_cases": ["creative", "writing"],
                    "template": "Create the following content in a unique and engaging style:\n\n{query}\n\nUse rich language, create vivid images, and explore fresh ideas. Don't be afraid to break conventions when necessary to create work that truly stands out."
                }
            ]
        }
        
        templates_path = os.path.join(config_dir, "prompt_templates.yml")
        if not os.path.exists(templates_path) or force:
            with open(templates_path, 'w', encoding='utf-8') as f:
                yaml.dump(prompt_templates, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
            logger.info(f"Prompt template file created: {templates_path}")
        else:
            logger.debug(f"The prompt template file already exists.: {templates_path}")
        
        return True
    except Exception as e:
        logger.error(f"Error creating configuration file: {e}")
        return False

def setup_dev_environment(logger: logging.Logger) -> bool:
    """
    Set up development environment

    Args:
    logger: Logger object

    Returns:
    True if setup is successful, False otherwise
    """
    try:
        # 1. Tạo file .gitignore nếu chưa có
        gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# PyCharm
.idea/

# VS Code
.vscode/

# Logs
logs/
*.log

# Data
data/
*.db
*.sqlite3

# Reports
reports/

# Cache
.cache/
.pytest_cache/
.coverage
htmlcov/

# Jupyter
.ipynb_checkpoints
"""
        
        if not os.path.exists(".gitignore"):
            with open(".gitignore", "w", encoding="utf-8") as f:
                f.write(gitignore_content.strip())
            logger.info("Đã tạo file .gitignore")
        else:
            logger.debug("File .gitignore đã tồn tại")
            
        # 2. Create setup.cfg files for flake8, mypy, and pytest
        setup_cfg_content = """
[flake8]
max-line-length = 100
exclude = .git,__pycache__,docs/conf.py,old,build,dist,venv,.venv

[tool:pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
python_classes = Test*
addopts = --verbose
"""
        
        if not os.path.exists("setup.cfg"):
            with open("setup.cfg", "w", encoding="utf-8") as f:
                f.write(setup_cfg_content.strip())
            logger.info("Đã tạo file setup.cfg")
        else:
            logger.debug("File setup.cfg đã tồn tại")
            
        # 3. Create pyproject.toml file for black
        pyproject_content = """
[tool.black]
line-length = 100
target-version = ['py38']
include = '\.pyi?$'
exclude = '''
/(
    \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | _build
  | buck-out
  | build
  | dist
)/
'''
"""
        
        if not os.path.exists("pyproject.toml"):
            with open("pyproject.toml", "w", encoding="utf-8") as f:
                f.write(pyproject_content.strip())
            logger.info("Created pyproject.toml file")
        else:
            logger.debug("The file pyproject.toml already exists.")
        
        # 4. Create tests folder if it doesn't exist
        if not os.path.exists("tests"):
            os.makedirs("tests")
            
            # Create __init__.py file in tests directory
            with open(os.path.join("tests", "__init__.py"), "w") as f:
                f.write("# Tests package\n")
                
            # Create sample test file
            test_sample_content = """
import unittest
import sys
import os

# Add root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestAssistant(unittest.TestCase):
    def setUp(self):
        pass
        
    def tearDown(self):
        pass
        
    def test_sample(self):
        self.assertEqual(1 + 1, 2)
        
if __name__ == '__main__':
    unittest.main()
"""
            
            with open(os.path.join("tests", "test_assistant.py"), "w", encoding="utf-8") as f:
                f.write(test_sample_content.strip())

            logger.info("Created tests directory with sample test file")
        else:
            logger.debug("The tests directory already exists")

        return True
    except Exception as e:
        logger.error(f"Error setting up development environment: {e}")
        return False

def main():
    """Main function"""
    # Parse command line arguments
    args = parse_args()

    # Setup logging
    logger = setup_logging(args.log_level)
    logger.info("Starting setup of personal assistant system...")

    # Create necessary directories
    dirs_to_create = [
        args.config_dir,
        args.data_dir,
        args.logs_dir,
        os.path.join(args.data_dir, "conversations"),
        os.path.join(args.data_dir, "rlhf_exports"),
        os.path.join(args.data_dir, "backups")
    ]

    logger.info("Creating necessary directories...")
    create_directories(dirs_to_create, logger)

    # Install dependent libraries
    if not args.no_deps:
        logger.info("Installing dependencies...")
        if not install_dependencies(args.dev, logger):
            logger.warning("Error installing libraries, continue setup...")
    else:
        logger.info("Skipping installation of dependencies (--no-deps)")

    # Create default configuration files
    logger.info("Creating default configuration files...")
    if not create_default_config(
            args.config_dir, args.data_dir, args.logs_dir,
            args.ollama_url, args.force, logger
    ):
        logger.warning("Error creating configuration file, continue setting...")

    # Set up development environment if required
    if args.dev:
        logger.info("Setting up development environment...")
        if not setup_dev_environment(logger):
            logger.warning("Error setting up development environment")

    logger.info("Setup complete!")
    logger.info(f"- Configuration directory: {os.path.abspath(args.config_dir)}")
    logger.info(f"- Data directory: {os.path.abspath(args.data_dir)}")
    logger.info(f"- Log directory: {os.path.abspath(args.logs_dir)}")
    logger.info(f"- Ollama URL: {args.ollama_url}")

    if not args.no_deps:
        logger.info("You can start the system with the command: python main.py --interactive")
    else:
        logger.info("Please install dependencies before running the system")
        logger.info("pip install -r requirements.txt")

if __name__ == "__main__":
    main()