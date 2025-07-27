"""
Interactive CLI for personal assistant system
"""

import os
import sys
import cmd
import time
import logging
import json
from typing import Dict, List, Any, Optional, Tuple

from src.integration.enhanced_assistant import EnhancedPersonalAssistant

logger = logging.getLogger(__name__)

class InteractiveShell(cmd.Cmd):
    """
    Interactive shell for personal assistant system
    """

    intro = """
======================================================================
  ENHANCED PERSONAL ASSISTANT SYSTEM WITH RLHF AND DPO
======================================================================

Type 'help' to see command list, 'exit' to quit
"""
    prompt = "\nYou: "

    def __init__(self, assistant: EnhancedPersonalAssistant, model_name: Optional[str] = None):
        """
        Initialize Interactive Shell

        Args:
            assistant: EnhancedPersonalAssistant instance
            model_name: Default model (optional)
        """
        super().__init__()
        self.assistant = assistant
        self.model_name = model_name
        self.conversation_id = None
        self.user_info = None
        self.system_prompt = None
        self.last_query = None

        # Update status display
        self._update_status_display()

        logger.info("Initialized Interactive Shell")

    def _update_status_display(self) -> None:
        """Update display status"""
        optimization = "ON" if self.assistant.optimization_enabled else "OFF"
        feedback = "ON" if self.assistant.feedback_collection_enabled else "OFF"
        auto_model = "ON" if self.assistant.auto_select_model else "OFF"
        group_discussion = "ON" if self.assistant.use_group_discussion else "OFF"

        status_info = f"Optimization: {optimization} | Feedback collection: {feedback} | Auto model select: {auto_model} | Group discussion: {group_discussion}"

        if self.model_name:
            status_info += f" | Model: {self.model_name}"

        self.status = status_info

    def preloop(self) -> None:
        """Setup before entering main loop"""
        # Initialize new conversation
        self.conversation_id = f"conv_{int(time.time())}"

    def default(self, line: str) -> bool:
        """
        Handle input that doesn't match any command

        Args:
            line: Input line

        Returns:
            False to continue loop
        """
        if line.strip():
            self._process_query(line.strip())
        return False

    def emptyline(self) -> bool:
        """
        Handle empty line input

        Returns:
            False to continue loop
        """
        return False

    def _process_query(self, query: str) -> None:
        """
        Process user query

        Args:
            query: User query
        """
        self.last_query = query
        start_time = time.time()

        try:
            result = self.assistant.get_response(
                query=query,
                conversation_id=self.conversation_id,
                user_info=self.user_info,
                model_name=self.model_name,
                system_prompt=self.system_prompt
            )

            response_text = result.get("response", "")
            model_used = result.get("model_used", "")
            completion_time = result.get("completion_time", 0)

            # Display response
            print(f"\nAssistant ({model_used}, {completion_time:.2f}s): {response_text}")

            # Check if feedback should be requested
            self._maybe_ask_for_feedback()

        except KeyboardInterrupt:
            print("\nRequest canceled.")
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            print(f"\nError occurred: {e}")

        # Display total time
        total_time = time.time() - start_time
        if total_time > 0.5:  # Only show if significant
            print(f"(Completed in {total_time:.2f}s)")

    def _maybe_ask_for_feedback(self) -> None:
        """Request user feedback if conditions are met"""
        if not self.assistant.feedback_collection_enabled:
            return

        # Determine if feedback should be requested (logic from FeedbackCollector)
        should_ask = self.assistant.feedback_manager.feedback_collector.should_request_feedback(
            self.conversation_id)

        if should_ask:
            try:
                print("\n--- Feedback ---")
                print("How would you rate this response? (1-5, or skip)")
                rating = input("Rating: ").strip()

                if rating and rating in "12345":
                    score = float(rating) / 5.0

                    print("Any additional comments? (press Enter to skip)")
                    feedback_text = input("Comment: ").strip()

                    # Get last response
                    history = self.assistant.get_conversation_history()
                    if history and len(history) >= 2:
                        last_response = history[-1].get("content", "")

                        # Save feedback
                        self.assistant.provide_feedback(
                            query=self.last_query,
                            selected_response=last_response,
                            feedback_score=score,
                            feedback_text=feedback_text if feedback_text else None
                        )

                        print("Thank you for your feedback!")

            except KeyboardInterrupt:
                print("\nFeedback skipped.")
            except Exception as e:
                logger.error(f"Error collecting feedback: {e}")

    def do_exit(self, arg: str) -> bool:
        """
        Exit interactive shell

        Args:
            arg: Parameter (unused)

        Returns:
            True to terminate loop
        """
        print("Goodbye!")
        return True

    def do_quit(self, arg: str) -> bool:
        """Alias for exit"""
        return self.do_exit(arg)

    def do_bye(self, arg: str) -> bool:
        """Alias for exit"""
        return self.do_exit(arg)

    def do_clear(self, arg: str) -> None:
        """
        Clear screen and start new conversation

        Args:
            arg: Parameter (unused)
        """
        # Clear screen
        os.system('cls' if os.name == 'nt' else 'clear')

        # Initialize new conversation
        self.assistant.clear_conversation()
        self.conversation_id = f"conv_{int(time.time())}"

        # Redisplay intro
        print(self.intro)
        self._update_status_display()
        print(f"Status: {self.status}")

        print("Cleared conversation and started new session.")

    def do_status(self, arg: str) -> None:
        """
        Show current status

        Args:
            arg: Parameter (unused)
        """
        self._update_status_display()
        print(f"Status: {self.status}")

        # Show detailed info
        stats = self.assistant.get_stats()
        optimization = stats.get("optimization", {})

        print("\nDetailed information:")
        print(f"- Current conversation: {self.conversation_id}")
        print(f"- Collected responses: {optimization.get('feedback_collection', {}).get('total_samples', 0)}")

        if self.model_name:
            print(f"- Current model: {self.model_name}")

        # Show model weights if available
        model_weights = optimization.get("model_weights", {})
        if model_weights:
            print("\nModel weights:")
            for model, weight in model_weights.items():
                print(f"- {model}: {weight:.2f}")

    def do_model(self, arg: str) -> None:
        """
        Set or show current model

        Args:
            arg: Model name to set
        """
        if not arg:
            available_models = self.assistant.model_manager.list_models()
            print(f"Current model: {self.model_name or 'auto'}")
            print(f"Available models: {', '.join(available_models)}")
            return

        arg = arg.strip()
        if arg == "auto":
            self.model_name = None
            self.assistant.toggle_auto_select_model(True)
            print("Switched to auto model selection mode.")
        else:
            available_models = self.assistant.model_manager.list_models()
            if arg in available_models:
                self.model_name = arg
                print(f"Switched to model: {arg}")
            else:
                print(f"Error: Model '{arg}' not found.")
                print(f"Available models: {', '.join(available_models)}")

        self._update_status_display()

    def do_toggle(self, arg: str) -> None:
        """
        Toggle features on/off

        Args:
            arg: Feature name (optimization, feedback, auto-model, group-discussion)
        """
        valid_features = ["optimization", "feedback", "auto-model", "group-discussion"]

        if not arg or arg.strip() not in valid_features:
            print(f"Syntax: toggle <feature>")
            print(f"Features: {', '.join(valid_features)}")
            return

        feature = arg.strip()

        if feature == "optimization":
            new_state = not self.assistant.optimization_enabled
            self.assistant.toggle_optimization(new_state)
            print(f"Optimization: {'ON' if new_state else 'OFF'}")

        elif feature == "feedback":
            new_state = not self.assistant.feedback_collection_enabled
            self.assistant.toggle_feedback_collection(new_state)
            print(f"Feedback collection: {'ON' if new_state else 'OFF'}")

        elif feature == "auto-model":
            new_state = not self.assistant.auto_select_model
            self.assistant.toggle_auto_select_model(new_state)
            print(f"Auto model select: {'ON' if new_state else 'OFF'}")

        elif feature == "group-discussion":
            new_state = not self.assistant.use_group_discussion
            self.assistant.toggle_group_discussion(new_state)
            print(f"Group discussion: {'ON' if new_state else 'OFF'}")

        self._update_status_display()

    def do_system(self, arg: str) -> None:
        """
        Set or show system prompt

        Args:
            arg: New system prompt
        """
        if not arg:
            print(f"Current system prompt: {self.system_prompt or 'Default'}")
            return

        self.system_prompt = arg.strip()
        print(f"Set new system prompt.")

    def do_user(self, arg: str) -> None:
        """
        Set user information

        Args:
            arg: User info in JSON format
        """
        if not arg:
            print(f"Current user info: {json.dumps(self.user_info, ensure_ascii=False) if self.user_info else 'None'}")
            return

        try:
            self.user_info = json.loads(arg.strip())
            print(f"Set new user information.")
        except json.JSONDecodeError:
            print("Error: Invalid JSON format.")

    def do_export(self, arg: str) -> None:
        """
        Export feedback data

        Args:
            arg: Export directory (optional)
        """
        export_dir = arg.strip() if arg else None

        try:
            export_path = self.assistant.export_feedback_data(export_dir)
            if export_path:
                print(f"Exported feedback data to: {export_path}")
            else:
                print("Failed to export feedback data.")
        except Exception as e:
            print(f"Export error: {e}")

    def do_help(self, arg: str) -> None:
        """
        Show help

        Args:
            arg: Command name to get help for
        """
        if not arg:
            print("\nAvailable commands:")
            print("  status        - Show current status")
            print("  model [name]  - Set or show model ('auto' for auto)")
            print("  toggle <opt>  - Toggle feature (optimization, feedback, auto-model, group-discussion)")
            print("  system [text] - Set or show system prompt")
            print("  user [json]   - Set or show user info")
            print("  export [dir]  - Export feedback data")
            print("  clear         - Clear screen and start new session")
            print("  exit/quit     - Exit program")
            print("\nType directly to interact with assistant.")
            return

        super().do_help(arg)

    def run(self) -> None:
        """Run interactive shell"""
        self._update_status_display()
        print(f"Status: {self.status}")

        try:
            self.cmdloop()
        except KeyboardInterrupt:
            print("\nReceived interrupt signal, exiting...")
        except Exception as e:
            logger.error(f"Unexpected shell error: {e}")
            print(f"\nError occurred: {e}")
        finally:
            print("Goodbye!")