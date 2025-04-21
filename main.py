MODEL_TO_USE = "google/gemini-2.0-flash-001"

#!/usr/bin/env python3
import argparse
import json
import os
import requests
import subprocess
import re
from dotenv import load_dotenv
import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from colorama import init, Fore, Style
import pygame  # Added for sound playback
init(autoreset=True)

# Load .env file
load_dotenv()
"""
def run_git_commands(message):
    #Run git add . and git commit with the provided message.
    try:
        subprocess.run(["git", "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        return f"Git error: {e.stderr.decode()}"
    except FileNotFoundError:
        return "Error: Git not installed or not found."
"""

def is_path_within_base(path, base_dir):
    """Check if path is within base_dir, resolving symlinks and absolute paths."""
    abs_path = os.path.abspath(path)
    abs_base = os.path.abspath(base_dir)
    return abs_path.startswith(abs_base + os.sep) or abs_path == abs_base

def ls_tool(directory, base_dir):
    """List contents of a directory, restricted to base_dir."""
    if not is_path_within_base(directory, base_dir):
        return f"Error: Directory {directory} is outside allowed base directory {base_dir}."
    try:
        result = subprocess.run(["ls", directory], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error listing directory: {e.stderr}"
    except FileNotFoundError:
        return "Error: 'ls' command not found. Try 'dir' on Windows."

def cat_tool(file_path, base_dir):
    """Read contents of a file, restricted to base_dir."""
    if not is_path_within_base(file_path, base_dir):
        return f"Error: File {file_path} is outside allowed base directory {base_dir}."
    if not os.path.isfile(file_path):
        return f"Error: File {file_path} does not exist or is not a file."
    try:
        # Try UTF-8 first, fall back to binary read if it fails
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Handle non-text files or unknown encoding
            with open(file_path, 'rb') as f:
                return f"Binary file content (hex): {f.read().hex()[:1000]}"  # Limit output
    except FileNotFoundError:
        return f"Error: File {file_path} not found."
    except IOError as e:
        return f"Error reading file: {e}"

# Note: LLMs don't usually use these tools properly, so commented out
'''
def edit_file_tool(file_path, content, base_dir):
    """Edit or overwrite a file with new content, restricted to base_dir."""
    if not is_path_within_base(file_path, base_dir):
        return f"Error: File {file_path} is outside allowed base directory {base_dir}."
    try:
        with open(file_path, 'w') as f:
            f.write(content)
        result = f"File {file_path} edited successfully."
        git_result = run_git_commands(f"Edited file: {file_path}")
        if git_result is not True:
            result += f"\n{git_result}"
        return result
    except IOError as e:
        return f"Error editing file: {e}"

def make_dir_tool(directory, base_dir):
    """Create a directory, restricted to base_dir."""
    if not is_path_within_base(directory, base_dir):
        return f"Error: Directory {directory} is outside allowed base directory {base_dir}."
    try:
        os.makedirs(directory, exist_ok=True)
        result = f"Directory {directory} created successfully."
        git_result = run_git_commands(f"Created directory: {directory}")
        if git_result is not True:
            result += f"\n{git_result}"
        return result
    except OSError as e:
        return f"Error creating directory: {e}"

def create_file_tool(file_path, content, base_dir):
    """Create a new file with optional content, restricted to base_dir."""
    if not is_path_within_base(file_path, base_dir):
        return f"Error: File {file_path} is outside allowed base directory {base_dir}."
    try:
        if os.path.exists(file_path):
            return f"Error: File {file_path} already exists."
        with open(file_path, 'w') as f:
            f.write(content)
        result = f"File {file_path} created successfully."
        git_result = run_git_commands(f"Created file: {file_path}")
        if git_result is not True:
            result += f"\n{git_result}"
        return result
    except IOError as e:
        return f"Error creating file: {e}"
'''
def call_tool(tool_call, base_dir):
    """Execute a tool based on JSON tool call, passing base_dir for restriction."""
    tool = tool_call.get("tool")
    args = tool_call.get("args", {})
    if tool == "ls":
        return ls_tool(args.get("directory", "."), base_dir)
    elif tool == "cat":
        return cat_tool(args.get("file_path"), base_dir)
    else:
        return f"Error: Unknown tool {tool}"

def extract_json(response):
    """Extract all JSON tool calls from mixed text, return (tool_calls, remaining_text)."""
    tool_calls = []
    remaining_text = response

    json_pattern = r'\{(?:[^{}]|\{[^{}]*\})*\}'
    matches = re.findall(json_pattern, remaining_text)

    for match in matches:
        try:
            parsed = json.loads(match)
            if isinstance(parsed, dict) and "tool" in parsed and "args" in parsed:
                tool_calls.append(parsed)
                remaining_text = re.sub(re.escape(match), '', remaining_text, count=1)
        except json.JSONDecodeError:
            continue

    return tool_calls, remaining_text.strip()

def process_response(assistant_response, history, base_dir):
    """Process assistant response, execute tool calls, and return updated history."""
    tool_calls, remaining_text = extract_json(assistant_response)
    history.append({"role": "assistant", "content": assistant_response})

    # Execute all tool calls immediately
    for tool_call in tool_calls:
        tool_result = call_tool(tool_call, base_dir)
        print(f"Tool Result: {tool_result}")
        history.append({"role": "system", "content": f"Tool result for {tool_call['tool']} with args {json.dumps(tool_call['args'])}: {tool_result}"})

    return tool_calls, remaining_text

def analyze_codebase(directory, user_input, history=None):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "Error: OPENROUTER_API_KEY not found in .env file.", history

    base_dir = os.path.abspath(directory)

    if history is None:
        history = []
        initial_ls = ls_tool(base_dir, base_dir)
        system_prompt = f"""You are an interactive code assistant for a codebase in {base_dir}. Engage in a multi-step conversation, using tools to analyze, modify, and create files or directories. All operations are restricted to {base_dir} and its subdirectories.

Available tools:
- ls: Lists directory contents. Call with {{"tool": "ls", "args": {{"directory": "<directory>"}}}}.
- cat: Reads file contents. Call with {{"tool": "cat", "args": {{"file_path": "<file_path>"}}}}.

Mix text responses with JSON tool calls. Execute tool calls immediately (e.g., ls, cat) and use their results in the same conversation turn. Tool results are provided in the conversation history. Respond concisely unless more detail is requested. Do not attempt to access paths outside {base_dir} (e.g., '..').

Initial directory listing:
{initial_ls}"""
        history.append({"role": "system", "content": system_prompt})

    # Append user input
    history.append({"role": "user", "content": user_input})

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": MODEL_TO_USE,
                "messages": history
            })
        )
        response.raise_for_status()
        assistant_response = response.json()['choices'][0]['message']['content'].strip()

        # Process response and execute tool calls
        tool_calls, remaining_text = process_response(assistant_response, history, base_dir)

        # If there were tool calls, continue the conversation automatically
        if tool_calls:
            return analyze_codebase(directory, "", history)
        else:
            # No tool calls, print response in green and return
            if remaining_text:
                print(f"{Fore.GREEN}{remaining_text}{Style.RESET_ALL}")
            return None, history

    except requests.RequestException as e:
        error_msg = f"Error calling API: {e}"
        history.append({"role": "system", "content": error_msg})
        print(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
        return error_msg, history
    except KeyError:
        error_msg = "Error: Unexpected API response format."
        history.append({"role": "system", "content": error_msg})
        print(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
        return error_msg, history

def main():
    parser = argparse.ArgumentParser(description="Interactive codebase analysis and modification tool.")
    parser.add_argument("directory", help="Directory containing the codebase.")

    args = parser.parse_args()

    directory = os.path.abspath(args.directory)
    if not os.path.isdir(directory):
        print(f"{Fore.RED}Error: {directory} is not a valid directory.{Style.RESET_ALL}")
        sys.exit(1)

    # Initialize pygame mixer for sound playback
    try:
        pygame.mixer.init()
    except pygame.error as e:
        print(f"{Fore.RED}Warning: Could not initialize audio: {e}. Sound will not play.{Style.RESET_ALL}")

    # Construct sound file path relative to script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sound_path = os.path.join(script_dir, "sound", "1.mp3")
    if not os.path.exists(sound_path):
        print(f"{Fore.RED}Warning: Sound file {sound_path} not found. Sound will not play.{Style.RESET_ALL}")
        sound_path = None

    # Interactive prompt session with plain prompt
    session = PromptSession(
        ">> ",
        history=FileHistory(os.path.join(directory, ".codebase_chat_history")),
        multiline=False
    )

    history = None
    while True:
        try:
            user_input = session.prompt()
            if user_input.lower() in ['exit', 'quit']:
                break

            error, history = analyze_codebase(directory, user_input, history)
            if error:
                continue

            # Play sound after response, before new prompt
            if sound_path:
                try:
                    pygame.mixer.music.load(sound_path)
                    pygame.mixer.music.play()
                    # Wait briefly to ensure sound starts (non-blocking)
                    pygame.time.wait(100)
                except pygame.error as e:
                    print(f"{Fore.RED}Warning: Could not play sound: {e}.{Style.RESET_ALL}")

        except KeyboardInterrupt:
            break
        except EOFError:
            break
    # Clean up pygame mixer
    pygame.mixer.quit()

if __name__ == "__main__":
    main()
