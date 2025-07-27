"""
CLI interactive mode.
Provides a command-line interface for the system.
"""

import logging
import os
import sys
import time
from typing import Dict, Any, Optional, List, Tuple
import argparse

from src.integration.enhanced_assistant import EnhancedPersonalAssistant

logger = logging.getLogger(__name__)

class InteractiveShell:
    """Command-line interface for the assistant system."""

    def __init__(self, assistant: EnhancedPersonalAssistant, args: argparse.Namespace):
        """
        Initialize the interactive interface.

        Args:
            assistant: Enhanced assistant object
            args: Command-line arguments
        """
        self.assistant = assistant
        self.args = args
        self.running = False
        self.command_history = []
        self.special_commands = {
            'help': self.show_help,
            'exit': self.exit_shell,
            'quit': self.exit_shell,
            'thoát': self.exit_shell,
            'toggle-opt': self.toggle_optimization,
            'toggle-feedback': self.toggle_feedback,
            'toggle-auto-model': self.toggle_auto_model,
            'report': self.show_performance_report,
            'export-rlhf': self.export_rlhf_data,
            'save': self.save_conversation,
            'clear': self.clear_screen,
            'reset': self.reset_optimization,
            'status': self.show_status,
        }

        logger.info("Initialized Interactive Shell")

    def run(self):
        """Run the main interactive loop."""
        self.running = True
        self._print_welcome_message()

        try:
            while self.running:
                user_input = input("\nYou: ").strip()

                if not user_input:
                    continue

                # Save to history
                self.command_history.append(user_input)

                # Handle special commands
                if user_input.lower() in self.special_commands:
                    self.special_commands[user_input.lower()]()
                    continue

                # Handle commands with arguments
                if ' ' in user_input and user_input.split()[0].lower() in self.special_commands:
                    command, *args = user_input.split(maxsplit=1)
                    if command.lower() in self.special_commands:
                        self.special_commands[command.lower()](*args)
                        continue

                # Handle regular queries
                self._process_query(user_input)

        except KeyboardInterrupt:
            print("\nReceived exit signal...")
        except EOFError:
            print("\nEnd of input...")
        finally:
            self._handle_exit()

    def _process_query(self, query: str):
        """
        Process user queries.

        Args:
            query: User query
        """
        try:
            start_time = time.time()

            # Process query with the enhanced assistant
            result = self.assistant.process_query(
                query=query,
                role=self.args.role if not self.args.auto_model else None,
                temperature=self.args.temperature,
                max_tokens=self.args.max_tokens,
                group_discussion=self.args.group_discussion,
                rounds=self.args.rounds,
                collect_feedback=self.args.feedback
            )

            # Display results
            self._display_result(result)

            # Display optimization info if available
            if "optimization_info" in result and not self.args.no_optimization:
                self._display_optimization_info(result["optimization_info"])

            processing_time = time.time() - start_time
            print(f"\n(Total processing time: {processing_time:.2f}s)")

        except Exception as e:
            logger.error(f"Error processing query: {e}")
            print(f"\nAn error occurred: {str(e)}")

    def _display_result(self, result: Dict[str, Any]):
        """
        Display response results.

        Args:
            result: Result from the assistant
        """
        if "error" in result:
            print(f"\nError: {result['error']}")
            return

        # Display group discussion results
        if self.args.group_discussion and "final_response" in result:
            print("\n" + "="*50)
            print(f"GROUP DISCUSSION RESULT")
            if "confidence_score" in result:
                print(f"(Confidence score: {result['confidence_score']:.2f})")
            print("="*50)

            if "summary" in result and result["summary"]:
                print("\nMAIN SUMMARY:")
                print(result['summary'])

            print("\nFULL RESPONSE:")
            print(result['final_response'])

            if self.args.verbose and "discussion_log" in result:
                self._display_discussion_details(result["discussion_log"])

        # Display single model results
        elif "response" in result:
            print(f"\n[{result['role']} - {result['model']}]")
            print(f"Assistant: {result['response']}")

        # Display multiple results from different models
        elif "responses" in result:
            for role, data in result["responses"].items():
                print(f"\n[{role} - {data['model']}]")
                print(f"Assistant: {data['response']}")
                print("-" * 40)

    def _display_discussion_details(self, discussion_log: List[Dict[str, Any]]):
        """
        Display discussion process details.

        Args:
            discussion_log: Discussion process log
        """
        print("\n" + "="*50)
        print("DISCUSSION PROCESS DETAILS:")

        for round_data in discussion_log:
            round_num = round_data.get('round', 0)
            print(f"\n--- ROUND {round_num} ---")

            for role, response_data in round_data.get('responses', {}).items():
                model = response_data.get('model', 'unknown')
                response = response_data.get('response', '')

                print(f"\n[{role} - {model}]")
                # Truncate long responses
                preview = response[:300] + "..." if len(response) > 300 else response
                print(preview)

    def _display_optimization_info(self, optimization_info: Dict[str, Any]):
        """
        Display optimization information.

        Args:
            optimization_info: Optimization information from the process
        """
        if not optimization_info.get("optimization_applied", False):
            return

        print("\n[Optimization Information]")

        if "suggested_model" in optimization_info:
            print(f"* Suggested model: {optimization_info['suggested_model']}")

        if "should_use_group_discussion" in optimization_info:
            use_group = "Yes" if optimization_info["should_use_group_discussion"] else "No"
            print(f"* Should use group discussion: {use_group}")

        if "top_models" in optimization_info:
            top_models = optimization_info["top_models"]
            if top_models:
                print("* Best matching models:")
                for model, score in top_models:
                    print(f"  - {model}: {score:.2f}")

    def _print_welcome_message(self):
        """Display welcome message."""
        print("\n" + "="*70)
        print("  ENHANCED PERSONAL ASSISTANT SYSTEM WITH RLHF AND DPO")
        print("="*70)

        # Display status
        states = []
        states.append(f"Optimization: {'ON' if not self.args.no_optimization else 'OFF'}")
        states.append(f"Feedback collection: {'ON' if self.args.feedback else 'OFF'}")
        states.append(f"Auto model selection: {'ON' if self.args.auto_model else 'OFF'}")
        states.append(f"Group discussion: {'ON' if self.args.group_discussion else 'OFF'}")

        print(f"\nStatus: {' | '.join(states)}")
        print("\nType 'help' to see command list, 'exit' to quit")

    def show_help(self):
        """Display help for special commands."""
        print("\n" + "="*50)
        print("SPECIAL COMMANDS:")
        print("="*50)

        commands = [
            ("help", "Display this help"),
            ("exit/quit/thoát", "Exit the program"),
            ("toggle-opt", "Toggle automatic optimization"),
            ("toggle-feedback", "Toggle feedback collection"),
            ("toggle-auto-model", "Toggle auto model selection"),
            ("report", "Display model performance report"),
            ("export-rlhf [directory]", "Export RLHF data"),
            ("save [filename]", "Save conversation history"),
            ("clear", "Clear the screen"),
            ("reset", "Reset optimization weights"),
            ("status", "Display system status"),
        ]

        col_width = max(len(cmd[0]) for cmd in commands) + 2
        for cmd, desc in commands:
            print(f"  {cmd:<{col_width}} - {desc}")

    def exit_shell(self):
        """Exit the interactive shell."""
        self.running = False

    def _handle_exit(self):
        """Handle program exit."""
        # Automatically save conversation if configured
        if self.args.save:
            self.save_conversation(self.args.save)
        else:
            # Save with default filename
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_{timestamp}.json"
            self.save_conversation(filename)

        print("\nThank you for using the personal assistant system. Goodbye!")

    def toggle_optimization(self):
        """Toggle automatic optimization."""
        self.args.no_optimization = not self.args.no_optimization
        self.assistant.toggle_optimization(not self.args.no_optimization)
        state = "OFF" if self.args.no_optimization else "ON"
        print(f"Automatic optimization: {state}")

    def toggle_feedback(self):
        """Toggle feedback collection."""
        self.args.feedback = not self.args.feedback
        self.assistant.toggle_feedback_collection(self.args.feedback)
        state = "ON" if self.args.feedback else "OFF"
        print(f"Feedback collection: {state}")

    def toggle_auto_model(self):
        """Toggle auto model selection."""
        self.args.auto_model = not self.args.auto_model
        self.assistant.toggle_auto_select_model(self.args.auto_model)
        if self.args.auto_model:
            # When enabling auto model selection, disable manual model selection
            self.args.role = None
        state = "ON" if self.args.auto_model else "OFF"
        print(f"Auto model selection: {state}")

    def show_performance_report(self):
        """Display model performance report."""
        from src.cli.reporting import display_performance_report

        try:
            report = self.assistant.get_performance_report()
            display_performance_report(report)
        except Exception as e:
            logger.error(f"Error displaying performance report: {e}")
            print(f"Failed to display report: {str(e)}")

    def export_rlhf_data(self, export_dir: Optional[str] = None):
        """
        Export collected RLHF data.

        Args:
            export_dir: Target directory (optional)
        """
        try:
            output_file = self.assistant.export_rlhf_dataset()
            print(f"Successfully exported RLHF data to: {output_file}")
        except Exception as e:
            logger.error(f"Error exporting RLHF data: {e}")
            print(f"Failed to export RLHF data: {str(e)}")

    def save_conversation(self, filename: Optional[str] = None):
        """
        Save conversation history.

        Args:
            filename: Filename (optional)
        """
        try:
            saved_path = self.assistant.save_conversation(filename)
            print(f"Saved conversation history to: {saved_path}")
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            print(f"Failed to save conversation history: {str(e)}")

    def clear_screen(self):
        """Clear the console screen."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def reset_optimization(self):
        """Reset optimization process."""
        try:
            confirm = input("Are you sure you want to reset optimization weights to default? (y/n): ")
            if confirm.lower() in ['y', 'yes']:
                self.assistant.feedback_manager.reset_optimization(reset_feedback_db=False)
                print("Reset optimization weights to default.")
        except Exception as e:
            logger.error(f"Error resetting optimization: {e}")
            print(f"Failed to reset optimization: {str(e)}")

    def show_status(self):
        """Display current system status."""
        try:
            status = self.assistant.get_optimization_status()

            print("\n" + "="*50)
            print("SYSTEM STATUS")
            print("="*50)

            print(f"\nGeneral configuration:")
            print(f"  Auto optimization: {'ON' if status['auto_optimization'] else 'OFF'}")
            print(f"  Auto model selection: {'ON' if status['auto_select_model'] else 'OFF'}")
            print(f"  Feedback collection: {'ON' if status['feedback_enabled'] else 'OFF'}")

            # Display statistics
            if "optimization_stats" in status:
                stats = status["optimization_stats"]

                print(f"\nStatistics:")
                print(f"  Total feedback count: {stats.get('total_feedback_count', 0)}")
                print(f"  Model count: {stats.get('model_count', 0)}")

                # Display current weights
                if "current_weights" in stats:
                    print("\nCurrent weights:")
                    for model, weight in stats["current_weights"].items():
                        print(f"  {model}: {weight:.3f}")

                # Display feedback counts by model
                if "feedback_counts_by_model" in stats:
                    print("\nFeedback counts by model:")
                    for model, count in stats["feedback_counts_by_model"].items():
                        print(f"  {model}: {count}")

            print("\nUse 'report' to view detailed performance report")

        except Exception as e:
            logger.error(f"Error displaying status: {e}")
            print(f"Failed to display status: {str(e)}")


def run_interactive_mode(assistant: EnhancedPersonalAssistant, args: argparse.Namespace):
    """
    Run the assistant in interactive mode.

    Args:
        assistant: Enhanced assistant object
        args: Command-line arguments
    """
    shell = InteractiveShell(assistant, args)
    shell.run()