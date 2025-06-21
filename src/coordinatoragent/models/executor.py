import os
import importlib
import re
from typing import Dict, Any, List
from datetime import datetime

from octotools.engine.openai import ChatOpenAI 
from octotools.models.formatters import ToolCommand

import signal
from typing import Dict, Any, List, Optional

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Function execution timed out")

class Executor:
    def __init__(self, llm_engine_name: str, root_cache_dir: str = "solver_cache",  num_threads: int = 1, max_time: int = 120, max_output_length: int = 100000):
        self.llm_engine_name = llm_engine_name
        self.root_cache_dir = root_cache_dir
        self.num_threads = num_threads
        self.max_time = max_time
        self.max_output_length = max_output_length

    def set_query_cache_dir(self, query_cache_dir):
        if query_cache_dir:
            self.query_cache_dir = query_cache_dir
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.query_cache_dir = os.path.join(self.root_cache_dir, timestamp)
        os.makedirs(self.query_cache_dir, exist_ok=True)
    
    def generate_tool_command(self, question: str, image: str, context: str, sub_goal: str, tool_name: str, tool_metadata: Dict[str, Any]) -> ToolCommand:
        prompt_generate_tool_command = f"""
Task: Generate a precise command to execute the selected tool based on the given information.

Query: {question}
Image: {image}
Context: {context}
Sub-Goal: {sub_goal}
Selected Tool: {tool_name}
Tool Metadata: {tool_metadata}

Instructions:
1. Carefully review all provided information: the query, image path, context, sub-goal, selected tool, and tool metadata.
2. Analyze the tool's input_types from the metadata to understand required and optional parameters.
3. Construct a command or series of commands that aligns with the tool's usage pattern and addresses the sub-goal.
4. Ensure all required parameters are included and properly formatted.
5. Use appropriate values for parameters based on the given context, particularly the `Context` field which may contain relevant information from previous steps.
6. If multiple steps are needed to prepare data for the tool, include them in the command construction.

Output Format:
<analysis>: a step-by-step analysis of the context, sub-goal, and selected tool to guide the command construction.
<explanation>: a detailed explanation of the constructed command(s) and their parameters.
<command>: the Python code to execute the tool, which can be one of the following types:
    a. A single line command with `execution = tool.execute()`.
    b. A multi-line command with complex data preparation, ending with `execution = tool.execute()`.
    c. Multiple lines of `execution = tool.execute()` calls for processing multiple items.
```python
<your command here>
```

Rules:
1. The command MUST be valid Python code and include at least one call to `tool.execute()`.
2. Each `tool.execute()` call MUST be assigned to the 'execution' variable in the format `execution = tool.execute(...)`.
3. For multiple executions, use separate `execution = tool.execute()` calls for each execution.
4. The final output MUST be assigned to the 'execution' variable, either directly from `tool.execute()` or as a processed form of multiple executions.
5. Use the exact parameter names as specified in the tool's input_types.
6. Enclose string values in quotes, use appropriate data types for other values (e.g., lists, numbers).
7. Do not include any code or text that is not part of the actual command.
8. Ensure the command directly addresses the sub-goal and query.
9. Include ALL required parameters, data, and paths to execute the tool in the command itself.
10. If preparation steps are needed, include them as separate Python statements before the `tool.execute()` calls.

Examples (Not to use directly unless relevant):

Example 1 (Single line command):
<analysis>: The tool requires an image path and a list of labels for object detection.
<explanation>: We pass the image path and a list containing "baseball" as the label to detect.
<command>:
```python
execution = tool.execute(image="path/to/image", labels=["baseball"])
```

Example 2 (Multi-line command with data preparation):
<analysis>: The tool requires an image path, multiple labels, and a threshold for object detection.
<explanation>: We prepare the data by defining variables for the image path, labels, and threshold, then pass these to the tool.execute() function.
<command>:
```python
image = "path/to/image"
labels = ["baseball", "football", "basketball"]
threshold = 0.5
execution = tool.execute(image=image, labels=labels, threshold=threshold)
```

Example 3 (Multiple executions):
<analysis>: We need to process multiple images for baseball detection.
<explanation>: We call the tool for each image path, using the same label and threshold for all.
<command>:
```python
execution = tool.execute(image="path/to/image1", labels=["baseball"], threshold=0.5)
execution = tool.execute(image="path/to/image2", labels=["baseball"], threshold=0.5)
execution = tool.execute(image="path/to/image3", labels=["baseball"], threshold=0.5)
```

Some Wrong Examples:
<command>:
```python
execution1 = tool.execute(query="...")
execution2 = tool.execute(query="...")
```
Reason: only `execution = tool.execute` is allowed, not `execution1` or `execution2`.

<command>:
```python
urls = [
    "https://example.com/article1",
    "https://example.com/article2"
]

execution = tool.execute(url=urls[0])
execution = tool.execute(url=urls[1])
```
Reason: The command should process multiple items in a single execution, not separate executions for each item.

Remember: Your <command> field MUST be valid Python code including any necessary data preparation steps and one or more `execution = tool.execute(` calls, without any additional explanatory text. The format `execution = tool.execute` must be strictly followed, and the last line must begin with `execution = tool.execute` to capture the final output.
"""

        llm_generate_tool_command = ChatOpenAI(model_string=self.llm_engine_name, is_multimodal=False)
        tool_command = llm_generate_tool_command(prompt_generate_tool_command, response_format=ToolCommand)

        return tool_command

    def extract_explanation_and_command(self, response: ToolCommand) -> tuple:
        def normarlize_code(code: str) -> str:
            # Remove leading and trailing whitespace and triple backticks
            return re.sub(r'^```python\s*', '', code).rstrip('```').strip()
        
        explanation = response.explanation.strip()
        command = normarlize_code(response.command.strip())
        return explanation, command

    def execute_tool_command(self, tool_name: str, command: str) -> Any:
        """
        Execute a tool command with timeout protection. If execution exceeds max_time seconds,
        the function will be interrupted and return a timeout message.
        
        Args:
            tool_name (str): Name of the tool to execute
            command (str): Command string containing tool.execute() calls
            
        Returns:
            Any: List of execution results or error message
        """
        
        def split_commands(command: str) -> List[str]:
            # Use regex to find all tool.execute() commands and their surrounding code
            pattern = r'.*?execution\s*=\s*tool\.execute\([^\n]*\)\s*(?:\n|$)'
            blocks = re.findall(pattern, command, re.DOTALL)
            return [block.strip() for block in blocks if block.strip()]
        
        def execute_with_timeout(block: str, local_context: dict) -> Optional[str]:
            # Set up the timeout handler
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.max_time)
            
            try:
                # Execute the block in the local context
                exec(block, globals(), local_context)
                result = local_context.get('execution')
                signal.alarm(0)  # Disable the alarm
                return result
            except TimeoutError:
                return f"Execution timed out after {self.max_time} seconds"
            finally:
                signal.alarm(0)  # Ensure alarm is disabled even if other exceptions occur

        # Import the tool module and instantiate it
        module_name = f"tools.{tool_name.lower().replace('_tool', '')}.tool"
        
        # print(f"Attempting to import module: {module_name}")
        # print(f"Current sys.path: {sys.path}")

        try:
            # Dynamically import the module
            module = importlib.import_module(module_name)

            # Get the tool class
            tool_class = getattr(module, tool_name)

            # Check if the tool requires an LLM engine
            # NOTE may need to refine base.py and tool.py to handle this better
            if getattr(tool_class, 'require_llm_engine', False):
                # Instantiate the tool with the model_string
                tool = tool_class(model_string=self.llm_engine_name)
            else:
                # Instantiate the tool without model_string for tools that don't require it
                tool = tool_class()
            
            # Set the custom output directory
            # NOTE: May have a better way to handle this
            tool.set_custom_output_dir(self.query_cache_dir)

            # Split the command into blocks, execute each one and store execution results
            command_blocks = split_commands(command)
            executions = []

            for block in command_blocks:
                # Create a local context to safely execute the block
                local_context = {'tool': tool}

                # Execute the block with timeout protection
                result = execute_with_timeout(block, local_context)
                
                if result is not None:
                    executions.append(result)
                else:
                    executions.append(f"No execution captured from block: {block}")

            # Return all the execution results
            return executions
        except Exception as e:
            return f"Error in execute_tool_command: {str(e)}"
