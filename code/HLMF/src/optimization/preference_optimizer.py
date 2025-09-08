"""
Module optimizes model preferences based on analysis of strengths and feedback

"""

import logging
import json
import random
import time
from typing import Dict, List, Any, Optional, Tuple, Union, Set

logger = logging.getLogger(__name__)

class PreferenceOptimizer:
    """
    Optimize model preferences based on:
    - Model strengths
    - User feedback (RLHF/DPO)
    - Query and requirements analysis
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Preference Optimizer

        Args:
        config: System configuration
        """
        self.config = config
        self.preference_config = config.get("optimization", {}).get("preference", {})
        self.models_config = config.get("models", [])

        #Declare default strengths
        self.strength_categories = [
            "programming", "analysis", "creative", "reasoning",
            "math", "language", "technical_explanation", "evaluation",
            "critical_thinking", "problem_solving", "algorithms",
            "conciseness", "clarity", "summarization", "general_knowledge",
            "communication", "balanced", "comprehensive", "thorough"
        ]

        # Load model strengths
        self.model_strengths = self._load_model_strengths()
        logger.info(f"Initialized strengths for {len(self.model_strengths)} model")
        
        # Configure weights
        self.weight_update_factor = self.preference_config.get("weight_update_factor", 0.1)
        self.win_rate_weight = self.preference_config.get("win_rate_weight", 0.7)
        self.score_weight = self.preference_config.get("score_weight", 0.3)
        self.default_weight = self.preference_config.get("default_weight", 1.0)
        self.min_weight = self.preference_config.get("min_weight", 0.5)
        self.max_weight = self.preference_config.get("max_weight", 2.0)
        
        # Track picks and scores
        self.model_selection_count = {}
        self.model_win_rate = {}
        self.model_avg_score = {}
        self.model_weights = {}
        
        # Cache for model performance by query type
        self.model_performance_cache = {}
        
        # Initialize default weights
        self._initialize_weights()
        
    def _load_model_strengths(self) -> Dict[str, Dict[str, float]]:
        """
        Load model strengths from configuration

        Returns:
        Dict containing strengths of each model
        """
        model_strengths = {}
        
        # Take advantage of configuration
        for model_config in self.models_config:
            model_name = model_config.get("name")
            if not model_name:
                continue
                
            strengths = model_config.get("strengths", {})
            
            # Ensure standardized strength lists
            normalized_strengths = {}
            for category in self.strength_categories:
                normalized_strengths[category] = strengths.get(category, 0.5)
                
            model_strengths[model_name] = normalized_strengths
            
        # Add group discussion if any
        group_discussion = self.config.get("group_discussion", {})
        if group_discussion and "name" in group_discussion:
            group_name = group_discussion.get("name", "group_discussion")
            group_strengths = group_discussion.get("strengths", {})
            
            normalized_strengths = {}
            for category in self.strength_categories:
                normalized_strengths[category] = group_strengths.get(category, 0.7)
                
            model_strengths[group_name] = normalized_strengths
            
        return model_strengths
    
    def _initialize_weights(self) -> None:
        """Initialize default weights for each model"""
        for model_name in self.model_strengths.keys():
            self.model_weights[model_name] = self.default_weight
            self.model_selection_count[model_name] = 0
            self.model_win_rate[model_name] = 0.5  # Default win rate is 50%
            self.model_avg_score[model_name] = 0.5  # The default average score is 0.5
    
    def select_best_model(self, query_analysis: Dict[str, Any], 
                         available_models: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
        """
        Select the best model based on query analysis and strengths

        Args:
        query_analysis: Query analysis results
        available_models: List of available models (optional)

        Returns:
        Name of selected model or None
        """
        # Check if no models available
        if not available_models and not self.model_strengths:
            return None
            
        # Get model list from parameter or configuration
        model_list = []
        if available_models:
            model_list = available_models
        else:
            model_list = self.models_config
            
        # List of model names
        model_names = [model.get("name") for model in model_list if model.get("name")]
        model_names = [name for name in model_names if name in self.model_strengths]
        
        if not model_names:
            return None
            
        # Identify the required strengths from query analysis
        required_strengths = self._determine_required_strengths(query_analysis)
        
        # Score each model
        model_scores = {}
        for model_name in model_names:
            strengths = self.model_strengths.get(model_name, {})
            score = self._calculate_model_score(strengths, required_strengths)
            
            # Adjust score based on weight
            weight = self.model_weights.get(model_name, self.default_weight)
            adjusted_score = score * weight
            
            model_scores[model_name] = adjusted_score
            
        # Select the model with the highest score
        if model_scores:
            best_model = max(model_scores.items(), key=lambda x: x[1])[0]
            
            # Update number of selections
            self.model_selection_count[best_model] = self.model_selection_count.get(best_model, 0) + 1
            
            return best_model
            
        # Default select first model if score not calculated
        return model_names[0] if model_names else None
    
    def update_weights_from_feedback(self, query: str, responses: Dict[str, str],
                                    selected_response: str, feedback_score: Optional[float] = None) -> None:
        """
        Update weights based on user feedback
        #用于 基于用户反馈动态调整模型的权重，以优化模型选择。

        Args:
        query: User query
        responses: Dict of responses with key as model_name
        selected_response: Selected model name
        feedback_score: Evaluation score (0-1, optional)
        """
        if not selected_response or selected_response not in self.model_weights:
            return
            
        # Update win rate
        participating_models = list(responses.keys())
        if len(participating_models) > 1 and selected_response in participating_models:
            for model in participating_models:#记录在某次对比中，哪个模型被用户选择。
                if model == selected_response:
                    self._update_win_rate(model, True)
                else:
                    self._update_win_rate(model, False)
                    
        # Update average score
        if feedback_score is not None:#结合历史评分，调整模型的质量评分。
            current_avg = self.model_avg_score.get(selected_response, 0.5)
            count = self.model_selection_count.get(selected_response, 1)
            # Weighted average, preferring newer values
            new_avg = (current_avg * 0.9 * count + feedback_score * 0.1 * count) / count
            self.model_avg_score[selected_response] = new_avg
            
        # Update weights#结合胜率和平均评分，动态调整模型权重，使得更受用户认可的模型获得更高的权重。
        win_rate = self.model_win_rate.get(selected_response, 0.5)
        avg_score = self.model_avg_score.get(selected_response, 0.5)
        
        # Calculate new weights based on win rate and average score
        performance_score = (
            win_rate * self.win_rate_weight +
            avg_score * self.score_weight
        )
        
        # Adjust weights
        current_weight = self.model_weights.get(selected_response, self.default_weight)
        adjustment = (performance_score - 0.5) * self.weight_update_factor
        
        new_weight = current_weight + adjustment
        new_weight = max(self.min_weight, min(self.max_weight, new_weight))
        
        self.model_weights[selected_response] = new_weight
        
        # Update performance cache#记录该 query 的选中模型和反馈分数。
        self._update_performance_cache(query, selected_response, feedback_score)
    
    def _update_win_rate(self, model_name: str, is_win: bool) -> None:
        """
        Update model win rate

        Args:
        model_name: Model name
        is_win: True if model is selected, False otherwise
        """
        if model_name not in self.model_win_rate:
            self.model_win_rate[model_name] = 0.5
            self.model_selection_count[model_name] = 0
            
        current_rate = self.model_win_rate[model_name]
        count = self.model_selection_count[model_name]
        new_count = count + 1
        
        # New win rate with decreasing weight over time
        decay_factor = min(100, new_count) / (min(100, new_count) + 10)
        win_value = 1.0 if is_win else 0.0
        
        new_rate = current_rate * decay_factor + win_value * (1 - decay_factor)
        
        self.model_win_rate[model_name] = new_rate
        self.model_selection_count[model_name] = new_count
    
    def _determine_required_strengths(self, query_analysis: Dict[str, Any]) -> Dict[str, float]:
        """
        Determine required strengths based on query analysis

        Args:
        query_analysis: Query analysis results

        Returns:
        Dict containing required strengths and priorities
        """
        required_strengths = {}
        
        # By default each strength has low priority
        for category in self.strength_categories:
            required_strengths[category] = 0.1
            
        # Based on analysis, adjust priorities
        if query_analysis.get("requires_code", False):
            required_strengths["programming"] = 0.9
            required_strengths["algorithms"] = 0.7
            required_strengths["technical_explanation"] = 0.6
            
        if query_analysis.get("requires_reasoning", False):
            required_strengths["reasoning"] = 0.8
            required_strengths["critical_thinking"] = 0.7
            required_strengths["analysis"] = 0.7
            required_strengths["evaluation"] = 0.6
            
        if query_analysis.get("requires_creativity", False):
            required_strengths["creative"] = 0.9
            
        # Based on complexity
        complexity = query_analysis.get("complexity", 0)
        if complexity > 7:
            required_strengths["comprehensive"] = 0.8
            required_strengths["thorough"] = 0.7
            required_strengths["balanced"] = 0.6
        elif complexity < 3:
            required_strengths["conciseness"] = 0.8
            required_strengths["clarity"] = 0.7
            
        # Based on query type
        query_type = query_analysis.get("query_type", "")
        if query_type == "how_to":
            required_strengths["technical_explanation"] = 0.7
            required_strengths["clarity"] = 0.7
        elif query_type == "comparison":
            required_strengths["balanced"] = 0.8
            required_strengths["analysis"] = 0.7
        elif query_type == "what_is":
            required_strengths["general_knowledge"] = 0.7
            required_strengths["clarity"] = 0.6
        elif query_type == "opinion":
            required_strengths["critical_thinking"] = 0.8
            required_strengths["evaluation"] = 0.7
        elif query_type == "list":
            required_strengths["comprehensive"] = 0.7
            required_strengths["clarity"] = 0.6
            
        # Based on format requirements
        format_reqs = query_analysis.get("format_requirements", {})
        if format_reqs.get("requires_step_by_step", False):
            required_strengths["clarity"] = 0.8
        if format_reqs.get("requires_examples", False):
            required_strengths["technical_explanation"] = 0.7
        if format_reqs.get("requires_comparison", False):
            required_strengths["balanced"] = 0.8
            required_strengths["analysis"] = 0.7
            
        # Consider the field
        domain = query_analysis.get("domain", "")
        if domain == "technology":
            required_strengths["technical_explanation"] = 0.8
            required_strengths["programming"] = 0.7
        elif domain == "science":
            required_strengths["analysis"] = 0.8
            required_strengths["reasoning"] = 0.7
        elif domain == "business":
            required_strengths["analysis"] = 0.7
            required_strengths["balanced"] = 0.7
        elif domain == "arts":
            required_strengths["creative"] = 0.8
            
        return required_strengths
    
    def _calculate_model_score(self, model_strengths: Dict[str, float],
                              required_strengths: Dict[str, float]) -> float:
        """
        Score the model based on strengths and requirements

        Args:
        model_strengths: Model strengths
        required_strengths: Required strengths

        Returns:
        Summary score
        """
        score = 0.0
        total_weight = 0.0
        
        for category, importance in required_strengths.items():
            if importance > 0.1:  # Consider only prioritized strengths
                strength = model_strengths.get(category, 0.5)
                score += strength * importance
                total_weight += importance
                
        # If no strong point is preferred, use average
        if total_weight == 0:
            return sum(model_strengths.values()) / len(model_strengths) if model_strengths else 0.5
            
        return score / total_weight
    
    def _update_performance_cache(self, query: str, model_name: str, 
                                feedback_score: Optional[float]) -> None:
        """
        Update model performance cache

        Args:
        query: User query
        model_name: Model name
        feedback_score: Evaluation score
        """
        if feedback_score is None:
            return
            
        # Keyword Extraction
        keywords = self._extract_keywords(query)
        query_type = self._infer_query_type(query)
        
        # Update cache for each keyword
        for keyword in keywords:
            if keyword not in self.model_performance_cache:
                self.model_performance_cache[keyword] = {}
                
            if model_name not in self.model_performance_cache[keyword]:
                self.model_performance_cache[keyword][model_name] = {
                    "score": 0.5,
                    "count": 0
                }
                
            current = self.model_performance_cache[keyword][model_name]
            new_score = (current["score"] * current["count"] + feedback_score) / (current["count"] + 1)
            
            self.model_performance_cache[keyword][model_name] = {
                "score": new_score,
                "count": current["count"] + 1
            }
            
        # Update cache for query type
        query_key = f"type:{query_type}"
        if query_key not in self.model_performance_cache:
            self.model_performance_cache[query_key] = {}
            
        if model_name not in self.model_performance_cache[query_key]:
            self.model_performance_cache[query_key][model_name] = {
                "score": 0.5,
                "count": 0
            }
            
        current = self.model_performance_cache[query_key][model_name]
        new_score = (current["score"] * current["count"] + feedback_score) / (current["count"] + 1)
        
        self.model_performance_cache[query_key][model_name] = {
            "score": new_score,
            "count": current["count"] + 1
        }
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract keywords from query

        Args:
        query: User query

        Returns:
        List of keywords
        """
        # Simple method: split words and remove stop words
        stop_words= {
            "是", "和", "的", "为", "在", "一个", "一些", "那些",
            "关于", "与", "有", "被", "不", "像", "从", "到",
            "我", "你", "我们", "他们", "自己", "这个", "当", "做", "为了"
        }

        # Convert to lowercase and split words
        words = query.lower().split()

        # Filter out stop words and short words
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords
    
    def _infer_query_type(self, query: str) -> str:
        """
        Query Type Inference

        Args:
        query: User query

        Returns:
        Query Type
        """
        query_lower = query.lower()

        if any(q in query_lower for q in ["how", "how", "way"]):
            return "how_to"
        elif any(q in query_lower for q in ["why", "why", "reason"]):
            return "why"
        elif any(q in query_lower for q in ["what", "definition", "explanation"]):
            return "what_is"
        elif any(q in query_lower for q in ["compare", "different", "same"]):
            return "comparison"
        elif any(q in query_lower for q in ["example", "illustration"]):
            return "example"
        elif any(q in query_lower for q in ["list", "list", "types"]):
            return "list"
        elif any(q in query_lower for q in ["review", "comment", "opinion"]):
            return "opinion"
        elif "?" in query:
            return "question"
        else:
            return "statement"
    
    def get_model_weights(self) -> Dict[str, float]:
        """
        Get the current weights of the models

        Returns:
        Dict containing the weights of each model
        """
        return self.model_weights.copy()
    
    def get_model_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get model performance statistics

        Returns:
        Dict containing statistics about each model
        """
        stats = {}
        
        for model_name in self.model_weights.keys():
            stats[model_name] = {
                "weight": self.model_weights.get(model_name, self.default_weight),
                "win_rate": self.model_win_rate.get(model_name, 0.5),
                "avg_score": self.model_avg_score.get(model_name, 0.5),
                "selection_count": self.model_selection_count.get(model_name, 0),
                "strengths": self.model_strengths.get(model_name, {})
            }
            
        return stats
    
    def clear_cache(self) -> None:
        """Clear performance cache"""
        self.model_performance_cache.clear()
        
    def reset_weights(self) -> None:
        """Reset weights to default"""
        for model_name in self.model_weights.keys():
            self.model_weights[model_name] = self.default_weight