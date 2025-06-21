
## Testing the Tools

To test the text detection tool, follow these steps:

1. **Navigate to the Project Directory:**

   Change your current directory to where the tools are located. Replace `your_path` with the actual path to your project directory.

   ```sh
   cd your_path/coordinatoragent
   ```

2. **Run the Text Detection Tool:**

   ```sh
   cd toolbox-agent
   export PYTHONPATH=$(pwd)
   ```


   Execute the tool using the following command:

   ```sh
   python tools/text_detector/tool.py

   python tools/object_detector/tool.py

   ```

## File Structure

The project is organized as follows:

```sh
├── __init__.py              # Initializes the tools package and possibly exposes submodules
├── base.py                  # Base class for tools, providing common functionality
├── text_detector/           # Directory for the text detection tool
│   ├── readme.md            # Documentation for the text detection tool
│   └── tool.py              # Implementation of the text detection tool
├── object_detector/         # Directory for the object detection tool
│   ├── readme.md            # Documentation for the object detection tool
│   └── tool.py              # Implementation of the object detection tool
```
