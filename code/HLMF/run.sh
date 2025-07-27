#!/bin/bash

# Script to run the enhanced personal assistant system

# Check Ollama connection
echo "Checking connection with Ollama..."
curl -s http://localhost:11434/api/version > /dev/null
if [ $? -ne 0 ]; then
    echo "WARNING: Unable to connect to Ollama. Please ensure Ollama is running."
    echo "Do you want to continue? (y/n)"
    read response
    if [ "$response" != "y" ]; then
        echo "Exiting."
        exit 1
    fi
fi

# Create necessary directories
mkdir -p data/conversations data/rlhf_exports logs

# Check and initialize virtual environment if needed
if [ ! -d "venv" ]; then
    echo "Initializing virtual environment..."
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Display menu
show_menu() {
    clear
    echo "====================================================="
    echo "  ENHANCED PERSONAL ASSISTANT SYSTEM WITH RLHF AND DPO  "
    echo "====================================================="
    echo "1. Interactive mode (with feedback collection)"
    echo "2. Interactive mode (without feedback collection)"
    echo "3. Interactive mode + Group discussion"
    echo "4. Enter a specific question"
    echo "5. Model performance report"
    echo "6. Export RLHF data"
    echo "7. Reset optimization"
    echo "8. Exit"
    echo "====================================================="
    echo "Your choice: "
}

run_interactive() {
    python main.py --interactive --feedback --auto-model
}

run_interactive_no_feedback() {
    python main.py --interactive --no-optimization
}

run_interactive_group() {
    python main.py --interactive --feedback --auto-model --group-discussion
}

run_single_query() {
    echo "Enter your question:"
    read -e query
    echo "Use group discussion? (y/n) [n]:"
    read use_group

    if [ "$use_group" = "y" ]; then
        python main.py --query "$query" --auto-model --group-discussion --feedback
    else
        python main.py --query "$query" --auto-model --feedback
    fi

    echo "Press Enter to continue..."
    read
}

show_report() {
    python main.py --report
    echo "Press Enter to continue..."
    read
}

export_rlhf() {
    echo "Exporting RLHF data to data/rlhf_exports"
    python main.py --export-rlhf data/rlhf_exports
    echo "Press Enter to continue..."
    read
}

reset_optimization() {
    echo "WARNING: This will reset all optimization weights to default values."
    echo "Are you sure you want to continue? (y/n)"
    read confirm

    if [ "$confirm" = "y" ]; then
        python main.py --reset-optimization --confirmed
        echo "Optimization has been reset."
    else
        echo "Operation canceled."
    fi

    echo "Press Enter to continue..."
    read
}

# Main loop
while true; do
    show_menu
    read choice

    case $choice in
        1) run_interactive ;;
        2) run_interactive_no_feedback ;;
        3) run_interactive_group ;;
        4) run_single_query ;;
        5) show_report ;;
        6) export_rlhf ;;
        7) reset_optimization ;;
        8) echo "Goodbye!"; break ;;
        *) echo "Invalid choice"; sleep 1 ;;
    esac
done

# Deactivate virtual environment
deactivate
