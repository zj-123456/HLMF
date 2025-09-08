"""
Module for optimizing responses based on query analysis
"""

import logging
import os
import yaml
import re
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class ResponseOptimizer:
    """
    Optimizes responses based on user query analysis,
    selects appropriate prompt templates, and adjusts instructions.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes Response Optimizer

        Args:
            config: System configuration
        """
        self.config = config
        self.optimization_config = config.get("optimization", {}).get("prompt_optimization", {})

        # Load prompt templates
        self.prompt_templates = self._load_prompt_templates()
        logger.info(f"Loaded {len(self.prompt_templates)} prompt templates from {self._get_template_path()}")

        # Optimization configuration
        self.template_selection_strategy = self.optimization_config.get(
            "template_selection_strategy", "best_match")
        self.max_prompt_token_count = self.optimization_config.get(
            "max_prompt_token_count", 2048)
        self.dynamic_instruction_tuning = self.optimization_config.get(
            "dynamic_instruction_tuning", True)
        self.instruction_history_window = self.optimization_config.get(
            "instruction_history_window", 20)

        # Temporary memory for previous analyses
        self.query_analysis_cache = {}
        self.template_performance_history = {}

    def _get_template_path(self) -> str:
        """Get the path to the prompt template file"""
        config_dir = self.config.get("system", {}).get("config_dir", "config")
        return os.path.join(config_dir, "prompt_templates.yml")

    def _load_prompt_templates(self) -> List[Dict[str, Any]]:
        """Load prompt templates from the configuration file"""
        try:
            template_path = self._get_template_path()
            with open(template_path, 'r', encoding='utf-8') as f:
                templates_data = yaml.safe_load(f)
            return templates_data.get("templates", [])
        except Exception as e:
            logger.error(f"Error loading prompt templates: {e}")
            return []

    def analyze_query(self, query: str, user_info: Optional[Dict] = None,
                     conversation_history: Optional[List] = None) -> Dict[str, Any]:
        """
        Analyze user queries to determine characteristics and requirements

        Args:
            query: User's question
            user_info: User information (optional)
            conversation_history: Conversation history (optional)

        Returns:
            Dictionary containing analysis results
        """
        # Check cache
        if query in self.query_analysis_cache:
            return self.query_analysis_cache[query].copy()

        # Calculate query complexity
        complexity_score = self._calculate_complexity(query)

        # Identify domain and topics
        domain, topics = self._identify_domain_and_topics(query)

        # Determine query type
        query_type = self._determine_query_type(query)

        # Identify format requirements
        format_requirements = self._detect_format_requirements(query)

        # Aggregate analysis results
        analysis_result = {
            "complexity": complexity_score,
            "domain": domain,
            "topics": topics,
            "query_type": query_type,
            "format_requirements": format_requirements,
            "requires_code": self._requires_code(query),
            "requires_reasoning": self._requires_reasoning(query),
            "requires_creativity": self._requires_creativity(query),
            "languages": self._detect_languages(query),
            "sentiment": self._analyze_sentiment(query),
            "urgency": self._detect_urgency(query)
        }#只检测汉语和英语

        # Save to cache
        self.query_analysis_cache[query] = analysis_result.copy()

        return analysis_result

    def optimize_query(self, query: str, user_info: Optional[Dict] = None,
                      conversation_history: Optional[List] = None) -> Dict[str, Any]:
        """
        Optimize queries based on analysis

        Args:
            query: User's question
            user_info: User information (optional)
            conversation_history: Conversation history (optional)

        Returns:
            Dictionary containing analysis results and optimized prompt
        """
        try:
            # Analyze query
            analysis = self.analyze_query(query, user_info, conversation_history)

            # Select appropriate prompt template
            selected_template = self._select_best_template(analysis)
            #selected_template{'name': 'default', 'description': 'Default template', 'template': '{query}', 'use_cases': ['general']}
            # Optimize prompt based on analysis
            optimized_prompt = self._optimize_prompt_from_template(
                query, analysis, selected_template)

            return {
                "analysis": analysis,
                "template_used": selected_template.get("name", "default"),
                "optimized_prompt": optimized_prompt
            }
        except Exception as e:
            logger.error(f"Error optimizing query: {e}")
            return {
                "analysis": {},
                "template_used": "default",
                "optimized_prompt": query
            }

    # Add alias method for compatibility with existing calling code
    def optimize_query_result(self, query: str, user_info: Optional[Dict] = None,
                            conversation_history: Optional[List] = None) -> Dict[str, Any]:
        """
        Alias for the optimize_query method to ensure compatibility
        with existing code calling this method
        """
        return self.optimize_query(query, user_info, conversation_history)

    def _calculate_complexity(self, query: str) -> float:
        """Calculate query complexity"""
        # Consider factors such as length, sentence structure, complex keywords
        complexity = min(5.0, (len(query) / 100) +
                        (query.count(',') * 0.1) +
                        (query.count('?') * 0.3))

        # Check for complexity-indicating keywords
        complex_indicators = [
            "why", "explain", "analyze", "compare", "evaluate",
            "cause", "consequence", "impact", "strategy", "comprehensive solution"
        ]

        for indicator in complex_indicators:
            if indicator in query.lower():
                complexity += 0.5

        return min(10.0, complexity)

    def _identify_domain_and_topics(self, query: str) -> Tuple[str, List[str]]:
        """Identify domain and topics of the query"""
        # Classify domain based on keywords
        domains = {
            "technology": ["computer", "software", "technology", "programming", "code", "AI", "application"],
            "business": ["business", "marketing", "finance", "management", "strategy", "investment"],
            "science": ["science", "physics", "chemistry", "biology", "mathematics", "research"],
            "health": ["health", "medical", "disease", "medicine", "treatment", "nutrition"],
            "education": ["education", "learning", "school", "university", "knowledge", "teaching"],
            "arts": ["art", "music", "film", "literature", "design", "creativity"],
            "lifestyle": ["lifestyle", "travel", "cuisine", "fashion", "sports"]
        }

        # Count matching keywords for each domain
        domain_scores = {domain: 0 for domain in domains}
        detected_topics = []

        query_lower = query.lower()
        for domain, keywords in domains.items():
            for keyword in keywords:
                if keyword in query_lower:
                    domain_scores[domain] += 1
                    if keyword not in detected_topics:
                        detected_topics.append(keyword)

        # Select domain with the highest score
        main_domain = max(domain_scores, key=domain_scores.get)
        if domain_scores[main_domain] == 0:
            main_domain = "general"

        return main_domain, detected_topics

    def _determine_query_type(self, query: str) -> str:
        """Determine query type"""
        query_lower = query.lower()

        if any(q in query_lower for q in ["how to", "how do", "way to"]):
            return "how_to"
        elif any(q in query_lower for q in ["why", "reason"]):
            return "why"
        elif any(q in query_lower for q in ["what is", "definition", "explain"]):
            return "what_is"
        elif any(q in query_lower for q in ["compare", "difference", "similarity"]):
            return "comparison"
        elif any(q in query_lower for q in ["example", "illustrate"]):
            return "example"
        elif any(q in query_lower for q in ["list", "enumeration", "types"]):
            return "list"
        elif any(q in query_lower for q in ["evaluate", "opinion", "comment"]):
            return "opinion"
        elif any(q in query_lower for q in ["predict", "future", "will"]):
            return "prediction"
        elif "?" in query:
            return "question"
        else:
            return "statement"

    def _detect_format_requirements(self, query: str) -> Dict[str, bool]:
        """Detect format requirements from the query"""
        query_lower = query.lower()

        return {
            "requires_list": any(kw in query_lower for kw in ["list", "enumeration", "points"]),
            "requires_step_by_step": any(kw in query_lower for kw in ["step by step", "detailed", "guide"]),
            "requires_examples": any(kw in query_lower for kw in ["example", "illustrate", "sample"]),
            "requires_summary": any(kw in query_lower for kw in ["summary", "overview", "brief"]),
            "requires_comparison": any(kw in query_lower for kw in ["compare", "contrast", "difference"]),
            "requires_pros_cons": any(kw in query_lower for kw in ["advantage", "disadvantage", "benefit", "limitation"]),
            "requires_table": any(kw in query_lower for kw in ["table", "chart"]),
            "requires_diagram": any(kw in query_lower for kw in ["diagram", "chart", "figure"])
        }

    def _requires_code(self, query: str) -> bool:
        """Check if the query requires code"""
        code_indicators = [
            "code", "programming", "function", "class", "implement",
            "algorithm", "script", "module", "debug", "fix", "error"
        ]
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in code_indicators)

    def _requires_reasoning(self, query: str) -> bool:
        """Check if the query requires reasoning"""
        reasoning_indicators = [
            "why", "reason", "explain", "analyze",
            "evaluate", "opinion", "conclusion", "inference"
        ]
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in reasoning_indicators)

    def _requires_creativity(self, query: str) -> bool:
        """Check if the query requires creativity"""
        creativity_indicators = [
            "creative", "idea", "design", "imagine", "write",
            "compose", "story", "fiction", "art", "unique"
        ]
        query_lower = query.lower()
        return any(indicator in query_lower for indicator in creativity_indicators)

    def _detect_languages(self, query: str) -> List[str]:
        """Detect languages used in the query"""
        """
            Return a list containing "chinese" if the input contains any CJK Unified Ideographs,
            and/or "english" if it contains any ASCII letters A–Z or a–z.
            """
        langs = []
        # Detect Chinese characters
        if re.search(r'[\u4e00-\u9fff]', query):
            langs.append("chinese")
        # Detect English letters
        if re.search(r'[A-Za-z]', query):
            langs.append("english")
        return langs or ["unknown"]

    def _analyze_sentiment(self, query: str) -> str:
        """Analyze sentiment in the query"""
        positive_words = ["good", "great", "excellent", "like", "happy", "satisfied"]
        negative_words = ["bad", "poor", "sad", "disappointed", "uncomfortable", "dislike"]
        query_lower = query.lower()

        positive_count = sum(1 for word in positive_words if word in query_lower)
        negative_count = sum(1 for word in negative_words if word in query_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

    def _detect_urgency(self, query: str) -> str:
        """Detect urgency level in the query"""
        urgent_indicators = ["urgent", "immediate", "quick", "soon", "as soon as possible"]
        query_lower = query.lower()

        if any(indicator in query_lower for indicator in urgent_indicators):
            return "high"
        else:
            return "normal"

    def _select_best_template(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Select the most suitable prompt template based on analysis results

        Args:
            analysis: Query analysis results

        Returns:
            Selected prompt template
        """
        if not self.prompt_templates:
            # Return default template if no templates are available
            return {
                "name": "default",
                "description": "Default template",
                "template": "{query}",
                "use_cases": ["general"]
            }

        # Selection strategy
        if self.template_selection_strategy == "best_match":
            return self._select_best_match_template(analysis)
        elif self.template_selection_strategy == "performance_based":
            return self._select_performance_based_template(analysis)
        else:
            # Default to best_match
            return self._select_best_match_template(analysis)

    def _select_best_match_template(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Select the best matching template based on analysis"""
        scores = []

        for template in self.prompt_templates:
            score = 0

            # Score for matching domain
            if analysis.get("domain") in template.get("domains", []):
                score += 3
            elif "general" in template.get("domains", []):
                score += 1

            # Score for use cases
            for use_case in template.get("use_cases", []):
                if use_case == analysis.get("query_type"):
                    score += 2
                if use_case == "code" and analysis.get("requires_code"):
                    score += 2
                if use_case == "reasoning" and analysis.get("requires_reasoning"):
                    score += 2
                if use_case == "creative" and analysis.get("requires_creativity"):
                    score += 2

            # Score for complexity
            template_complexity = template.get("complexity", "medium")
            if (template_complexity == "high" and analysis.get("complexity", 0) > 7) or \
                    (template_complexity == "medium" and 3 <= analysis.get("complexity", 0) <= 7) or \
                    (template_complexity == "low" and analysis.get("complexity", 0) < 3):
                score += 2

            scores.append((template, score))

        # Select template with the highest score
        if scores:
            best_template = max(scores, key=lambda x: x[1])[0]
            return best_template

        # Return default template if no scores are available


        return self.prompt_templates[0] if self.prompt_templates else {
            "name": "default",
            "template": "{query}"
        }

    def _select_performance_based_template(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Select template based on past performance"""
        # Filter templates matching the analysis
        matching_templates = []
        for template in self.prompt_templates:
            if (analysis.get("domain") in template.get("domains", []) or
                "general" in template.get("domains", [])):
                matching_templates.append(template)

        if not matching_templates:
            matching_templates = self.prompt_templates

        # Sort by past performance
        templates_with_scores = []
        for template in matching_templates:
            template_name = template.get("name")
            performance_score = self.template_performance_history.get(template_name, {}).get("score", 0.5)
            templates_with_scores.append((template, performance_score))

        # Select template with the highest performance score
        if templates_with_scores:
            best_template = max(templates_with_scores, key=lambda x: x[1])[0]
            return best_template

        # Return default template if no scores are available
        return matching_templates[0] if matching_templates else {
            "name": "default",
            "template": "{query}"
        }

    def _optimize_prompt_from_template(self, query: str, analysis: Dict[str, Any],
                                     template: Dict[str, Any]) -> str:
        """
        Optimize prompt based on the selected template and analysis results

        Args:
            query: Original query
            analysis: Analysis results
            template: Selected prompt template

        Returns:
            Optimized prompt
        """
        # Get prompt template
        prompt_template = template.get("template", "{query}")

        # Basic replacements
        replacements = {
            "{query}": query,
            "{domain}": analysis.get("domain", "general"),
            "{complexity}": str(analysis.get("complexity", 0)),
            "{query_type}": analysis.get("query_type", "general"),
            "{topics}": ", ".join(analysis.get("topics", [])),
            "{requires_code}": "true" if analysis.get("requires_code") else "false",
            "{requires_reasoning}": "true" if analysis.get("requires_reasoning") else "false",
            "{requires_creativity}": "true" if analysis.get("requires_creativity") else "false",
            "{format_requirements}": self._format_requirements_to_string(analysis.get("format_requirements", {})),
            "{sentiment}": analysis.get("sentiment", "neutral"),
            "{urgency}": analysis.get("urgency", "normal"),
            "{languages}": ", ".join(analysis.get("languages", ["vietnamese"])),
        }

        # Perform replacements
        optimized_prompt = prompt_template
        for key, value in replacements.items():
            optimized_prompt = optimized_prompt.replace(key, value)

        # Add additional instructions if needed
        if self.dynamic_instruction_tuning:
            additional_instructions = self._generate_additional_instructions(analysis)
            if additional_instructions:
                optimized_prompt += f"\n\n{additional_instructions}"

        return optimized_prompt

    def _format_requirements_to_string(self, format_reqs: Dict[str, bool]) -> str:
        """Convert format requirements into instruction strings"""
        instructions = []

        for req, value in format_reqs.items():
            if value:
                if req == "requires_list":
                    instructions.append("Present the results in a structured list format.")
                elif req == "requires_step_by_step":
                    instructions.append("Provide detailed step-by-step instructions.")
                elif req == "requires_examples":
                    instructions.append("Include specific examples to illustrate.")
                elif req == "requires_summary":
                    instructions.append("Include a brief summary of key points.")
                elif req == "requires_comparison":
                    instructions.append("Clearly compare different aspects.")
                elif req == "requires_pros_cons":
                    instructions.append("List pros and cons.")
                elif req == "requires_table":
                    instructions.append("Present data in a table format if applicable.")
                elif req == "requires_diagram":
                    instructions.append("Describe using diagrams or charts if possible.")

        return " ".join(instructions)

    def _generate_additional_instructions(self, analysis: Dict[str, Any]) -> str:
        """Generate additional instructions based on analysis"""
        instructions = []

        # Add instructions based on complexity
        if analysis.get("complexity", 0) > 7:
            instructions.append("Analyze the issue comprehensively, considering multiple aspects and providing in-depth analysis.")
        elif analysis.get("complexity", 0) < 3:
            instructions.append("Provide concise, clear, and easy-to-understand answers.")

        # Add instructions based on requirements
        if analysis.get("requires_code"):
            instructions.append("Provide clear, commented code adhering to clean code principles.")

        if analysis.get("requires_reasoning"):
            instructions.append("Explain the logic and reasoning in detail, providing well-founded arguments.")

        if analysis.get("requires_creativity"):
            instructions.append("Demonstrate creativity, originality, and out-of-the-box thinking.")

        # Add instructions based on language
        if "vietnamese" in analysis.get("languages", []):
            instructions.append("Respond in Vietnamese, using appropriate terminology and natural language style.")

        # Add instructions based on urgency
        if analysis.get("urgency") == "high":
            instructions.append("Prioritize providing essential information and quick solutions.")

        return " ".join(instructions)

    def update_template_performance(self, template_name: str, feedback_score: float) -> None:
        """
        Update template performance based on feedback

        Args:
            template_name: Template name
            feedback_score: Feedback score (0-1)
        """
        if template_name not in self.template_performance_history:
            self.template_performance_history[template_name] = {
                "score": 0.5,
                "count": 0
            }

        current = self.template_performance_history[template_name]
        current_count = current["count"]
        current_score = current["score"]

        # Update score with decreasing weight
        updated_score = (current_score * current_count + feedback_score) / (current_count + 1)

        self.template_performance_history[template_name] = {
            "score": updated_score,
            "count": current_count + 1
        }

    def clear_cache(self) -> None:
        """Clear cache"""
        self.query_analysis_cache.clear()