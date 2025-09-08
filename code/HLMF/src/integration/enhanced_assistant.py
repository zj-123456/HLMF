"""
Integration of components into an enhanced assistant with RLHF and DPO
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple, Union

from src.core.assistant import PersonalAssistant
from src.core.group_discussion import GroupDiscussionManager
from src.optimization.manager import FeedbackOptimizationManager

logger = logging.getLogger(__name__)

class EnhancedPersonalAssistant:
    """
    Personal assistant for Improving Integration:
    -Basic assistant.
    -Group discussions.
    - Feedback optimization (RLHF/DPO)
    -To automatically choose the model
    """
    
    def __init__(self, base_assistant: PersonalAssistant,
                group_discussion_manager: GroupDiscussionManager,
                feedback_manager: FeedbackOptimizationManager,
                config: Dict[str, Any]):
        """
        Launch of Enhanced Personal Assistant

        Args:
        Base_assistant: Personali-Resistant object
        Group_discussion_manager: Subject of Groupdiscussion_Manager
        Feedback_manager: Profile for FeedbackOptimizationManager
        Config: Systematic configuration
        """
        self.assistant = base_assistant
        self.group_manager = group_discussion_manager
        self.feedback_manager = feedback_manager
        self.config = config
        
        # Orthorization
        #从 config 字典中获取 "optimization" 相关的 "enabled" 配置，并赋值给 self.optimization_enabled，如果相关的值不存在，则默认设置为 True。
        self.optimization_enabled = config.get("optimization", {}).get("enabled", False)#True)
        self.auto_select_model = config.get("optimization", {}).get("auto_select_model", False), #True)
        self.use_group_discussion = config.get("optimization", {}).get("check_group_discussion_suitability", False)
        
        # Configuration collected feedback
        self.feedback_collection_enabled = config.get("optimization", {}).get(
            "feedback", {}).get("enabled", True)
        
        # Current conversation information
        self.current_conversation_id = None
        self.conversation_history = []
        
        # Caches for answers
        self.response_cache = {}
        
        logger.info("Started the Enhanced Personal Assistant with RLHF and DPO")
        
    def get_response(self, query: str, conversation_id: Optional[str] = None,
                    user_info: Optional[Dict] = None, model_name: Optional[str] = None,
                    use_group_discussion: Optional[bool] = None,
                    system_prompt: Optional[str] = None,
                    params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Receive answers to queries with automated optimization

        Args:
        Query: User query
        Conversation_id: ID of (optional) conversations
        User_info: User information (optional)
        Model_name: Model name for Use (option)
        Use_group_discussion: Overwriting configuration use group Discussion (option)
        System_prompt: Prompt system prompt (optional).
        Params: Additional parameter to the model (option)

        Returns:
        Dict contains answers and additional information
        """
        start_time = time.time()
        
        # To establish that conversation
        conversation_id = conversation_id or self.current_conversation_id or f"conv_{int(time.time())}"
        self.current_conversation_id = conversation_id
        
        # Optimization if enabled
        optimized_query = query
        query_analysis = {}
        
        if self.optimization_enabled:#self.optimization_enabled = config.get("optimization", {}).get("enabled", False)
            try:
                optimization_result = self.feedback_manager.optimize_query(
                    query, user_info, self.conversation_history)
                
                if optimization_result:
                    optimized_query = optimization_result.get("optimized_prompt", query)
                    #optimized_query的内容'Can you introduce Nezha 2\nProvide concise, clear, and easy-to-understand answers.'
                    query_analysis = optimization_result.get("analysis", {})
            except Exception as e:
                logger.error(f"Mistakes in query optimization: {e}")
        
        # Automatically choose one if turned on and no specific model is available.
        selected_model = model_name
        model_selection_info = {}
        
        if self.auto_select_model and not selected_model:#False
            try:
                selected_model = self.feedback_manager.select_best_model(
                    query, query_analysis)#根据问题的难易程度自动选择模型
                
                if selected_model:
                    logger.info(f"To automatically choose the model {selected_model} based on the analysis of questions")
                    model_selection_info = {
                        "auto_selected": True,
                        "model": selected_model,
                        "reason": "Based on analyzing the strengths of the model and the requirements of the question"
                    }
            except Exception as e:
                logger.error(f"Mistakes to automatically choose the model: {e}")
        
        # Whether or not they should use group discussions.
        should_use_group = use_group_discussion if use_group_discussion is not None else self.use_group_discussion
        group_discussion_used = False
        group_discussion_info = {}
        
        if should_use_group and self._is_suitable_for_group_discussion(query, query_analysis):#False
            try:
                group_result = self.group_manager.conduct_discussion(
                    optimized_query, conversation_id, user_info, None, params)
                
                response_text = group_result.get("response", "")
                group_discussion_used = True
                group_discussion_info = {
                    "rounds": group_result.get("rounds", 0),
                    "models_used": group_result.get("models_used", []),
                    "completion_time": group_result.get("completion_time", 0)
                }
            except Exception as e:
                logger.error(f"Mistakes of conducting group discussions: {e}")
                # To come back with a single model when discussing the failed group
                group_discussion_used = False
        
        # Without using group discussion, using the answer from a single model
        if not group_discussion_used:
            try:
                response = self.assistant.get_response(
                    optimized_query, conversation_id, user_info,
                    selected_model, system_prompt, params)
                
                response_text = response.get("response", "")
            except Exception as e:
                logger.error(f"To get an answer from the Assistant,: {e}")
                response_text = f"Sorry, there has been an error in handling your request. Faulty details: {str(e)}"
        
        # Update the conversation history
        #self._update_conversation_history(query, response_text)
        
        # Prepare the return results
        completion_time = time.time() - start_time
        
        result = {
            "response": response_text,
            "conversation_id": conversation_id,
            "completion_time": completion_time,
            "model_used": selected_model or "default",
            "optimized": self.optimization_enabled,
            "auto_model_selection": model_selection_info if self.auto_select_model else {},
            "group_discussion": group_discussion_info if group_discussion_used else {},
            "query_analysis": query_analysis if self.optimization_enabled else {}
        }
        
        # Put your results in a cache#或者如果答案正确，就缓存。
        #self._cache_response(query, result)#只在此处调用了_cache_response
        
        return result
    
    def provide_feedback(self, query: str, selected_response: str, 
                        feedback_score: Optional[float] = None,
                        feedback_text: Optional[str] = None) -> bool:
        """
        Provide feedback on the answers

        Args:
        Query: Original query
        Selected_response: The answer we take
        Feedback_score (0-1)
        Feedback_text: Text feedback (option)

        Returns:
        True if feedback is handled successfully, False or not
        """
        if not self.feedback_collection_enabled or not self.current_conversation_id:
            return False
            
        # Take the answers from the Cache
        cached_responses = self._get_cached_responses(query)
        if not cached_responses:
            return False
            
        # Monitoring feedback through FeedbackOptimizationManager
        #将反馈提交给 feedback_manager 进行处理（用以模型优化）
        success = self.feedback_manager.process_feedback(
            conversation_id=self.current_conversation_id,
            query=query,
            responses=cached_responses,
            selected_response=selected_response,
            feedback_score=feedback_score,
            feedback_text=feedback_text
        )
        
        return success
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """
        Takes the history of existing conversation

        Returns:
        List of restrictions on information on each exchange
        """
        return self.conversation_history.copy()
    
    def clear_conversation(self) -> None:
        """Erase the history of dialogue and create new dialogue"""
        self.current_conversation_id = f"conv_{int(time.time())}"
        self.conversation_history = []
        self.response_cache = {}
        
    def toggle_optimization(self, enabled: bool) -> None:
        """
        Optimizing on/off

        Args:
        Enabled: True to enable, False to turn off
        """
        self.optimization_enabled = enabled
        self.feedback_manager.toggle_optimization(enabled)
        
    def toggle_auto_select_model(self, enabled: bool) -> None:
        """
        On/off and pick the model.

        Args:
        Enabled: True to enable, False to turn off
        """
        self.auto_select_model = enabled
        
    def toggle_feedback_collection(self, enabled: bool) -> None:
        """
        On/off collect feedback

        Args:
        Enabled: True to enable, False to turn off
        """
        self.feedback_collection_enabled = enabled
        self.feedback_manager.toggle_feedback_collection(enabled)
        
    def toggle_group_discussion(self, enabled: bool) -> None:
        """
        On/off using group discussion

        Args:
        Enabled: True to enable, False to turn off
        """
        self.use_group_discussion = enabled
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Taking statistics on the system

        Returns:
        Dict contains statistics
        """
        # Extract statistics from the components.
        optimization_stats = self.feedback_manager.get_stats()
        
        stats = {
            "optimization": {
                "enabled": self.optimization_enabled,
                "auto_select_model": self.auto_select_model,
                "feedback_collection": self.feedback_collection_enabled,
                "use_group_discussion": self.use_group_discussion,
                **optimization_stats
            },
            "conversation": {
                "current_id": self.current_conversation_id,
                "history_length": len(self.conversation_history),
                "cached_responses": len(self.response_cache)
            }
        }
        
        return stats
    
    def export_feedback_data(self, export_dir: Optional[str] = None) -> str:
        """
        Exporting feedback data to train RLHF

        Args:
        Export_dir: optional, export_Dir

        Returns:
        The way to the export file
        """
        return self.feedback_manager.export_feedback_data(export_dir)
    
    def _update_conversation_history(self, query: str, response: str) -> None:
        """
        Update the conversation history

        Args:
        Query: User query
        Response: The assistant's answer
        """
        # Limit the number of historical items
        max_history = self.config.get("assistant", {}).get("conversation_history_limit", 5)#100
        
        # Adding new turns of exchange
        self.conversation_history.append({
            "role": "user",
            "content": query,
            "timestamp": time.time()
        })
        
        self.conversation_history.append({
            "role": "assistant", 
            "content": response,
            "timestamp": time.time()
        })
        
        # Cutting if it's too long
        if len(self.conversation_history) > max_history:
            self.conversation_history = self.conversation_history[-max_history:]
    
    def _cache_response(self, query: str, result: Dict[str, Any]) -> None:
        """
        Caches the answers

        Args:
        Query: User query
        Result: the assistant's result
        """
        model_used = result.get("model_used", "default")
        response = result.get("response", "")
        
        if query not in self.response_cache:
            self.response_cache[query] = {}
            
        self.response_cache[query][model_used] = response
    
    def _get_cached_responses(self, query: str) -> Dict[str, str]:
        """
        Take your answers stored in the cache.

        Args:
        Query: User query

        Returns:
        Dict Answers to key are model_name
        """
        return self.response_cache.get(query, {})
    
    def _is_suitable_for_group_discussion(self, query: str, 
                                         analysis: Optional[Dict] = None) -> bool:
        """
        Checking if queries are suitable for group discussions

        Args:
        Query: User query
        Analysis: Query analysis (option)

        Returns:
        True if it's appropriate, False or not
        """
        # No analyses, using simple analysis
        if not analysis:
            # Longer and more complex queries are often appropriate for group discussions
            is_complex = len(query) > 100 and ('?' in query or 'tại sao' in query.lower())
            return is_complex
            
        # Using existing analysis
        complexity = analysis.get("complexity", 0)
        requires_reasoning = analysis.get("requires_reasoning", False)
        requires_creativity = analysis.get("requires_creativity", False)
        
        # Complex queries, requires reasoning or creativity appropriate for group discussion
        return complexity > 6 or requires_reasoning or requires_creativity