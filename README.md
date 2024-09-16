# Running the Application Locally

This guide will help you set up and run the application on your local machine. Use the Jupyter Notebook to Run the project.

> This Guide suppose you have Python, Pip and MongoDB installed.
> It also suppose you can run jupyter notebook locally. 
>
> Important: Open Terminal at Current Folder

## Using Conda

1. Create Environment and Activate
```
conda create -n caipo_env python=3.12.4 pip
conda activate caipo_env
```

2. Install Dependencies (on current folder)
```
pip install -r requirements.txt
```

3. Load env as jupyter kernel
```
python -m ipykernel install --user --name caipo_env --display-name "Caipo Env"
```

## Using Virtual Environment

1. Create Environment
```
python -m venv caipo_env
```

2. Activate Environment
    - on macOS/Linux:
    ```
    source caipo_env/bin/activate
    ```
    - on Windows:
    ```
    caipo_env\Scripts\activate
    ```

3. Install Dependencies
```
pip install -r requirements.txt
```

4. Load env as jupyter kernel
```
python -m ipykernel install --user --name caipo_env --display-name "Caipo Env"
```

5. Deactivate Environment (Optional)
```
deactivate
```

# Future Path

1. Create an intent Extractor to grab clear intent from user input. (https://demo.deeppavlov.ai/#/examples/text_intent)

2. Create a super-supervisor to decide which workflow to go to. (https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/)

3. Enables Each Workflow to handle Loops and if-else-conditions by optimizing: (https://langchain-ai.github.io/langgraph/tutorials/self-discover/self-discover/)
    - create_new_workflow() or
    - create_graph() or 
    - create_team_supervisor()

4. Expand the ability of Workflows by adding more tools in: (https://python.langchain.com/v0.1/docs/modules/tools/custom_tools/)
    - custom_tools.py (or create new files in tools folder)
    - prebuilt_tools.py for built-in functions.
    - make sure to add a tool to get user's input dynamically.

5. Improve Response and Speed by improving prompts in: 
    - prompts.yaml

6. Using multi-thread or other methods to speed up workflows.

7. (Optional) Isolate Agent from Step (You can see steps in mongodb) for future reuse. Related Functions and Classes:
    - MetaStep (class)
    - MetaStepList (class)
    - generate_steps_and_supervisor_prompt (function)
    - prompts