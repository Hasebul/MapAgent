
# find all tool.py files in the tools folder
tools=$(find . -type f -name "tool.py")

echo "Testing all tools"

# print the tools
echo "Tools:"
for tool in $tools; do
    echo "  - $(basename $(dirname $tool))"
done

# Track if any tests fail
failed=0

# run the test script in each tool
for tool in $tools; do
    tool_dir=$(dirname $tool)
    tool_name=$(basename $tool_dir)

    echo ""
    echo "Testing $tool_name..."
    
    # Save current directory
    pushd $tool_dir > /dev/null
    
    # Run test and capture exit code
    python tool.py > test.log 2>&1
    if [ $? -ne 0 ]; then
        echo "❌ $tool_name failed! Check $tool_dir/test.log for details"
        failed=1
    else
        echo "✅ $tool_name passed"
    fi
    
    # Return to original directory
    popd > /dev/null
done

echo ""
echo "Done testing all tools"
echo "Failed: $failed"