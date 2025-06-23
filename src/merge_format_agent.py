import os
import time
import autogen
import sys
sys.path.append(os.path.abspath('../../'))
from utils import simple_parse, config_list

def get_task_prompt(formats):
    task_prompt = f"""You are tasked with merging multiple 3D formats into a single comprehensive format. Your task is to:
    - **Merge the casetypes** for the same field (`Type`) into a single casetype while including all structs from the original formats.
    - DONOT obmit any constraint. if there is field constraint conflict while merging casetypes, consider move those field into each case struct.
    - **Do NOT infer** or add new cases. Keep the original cases as is.
    - **Avoid redefining the control variable** (`Type`) inside the `casetype` switch statement.
    Here are the formats to merge:
    {formats}
    Execute code with the supplied function simple_parse only
    """
    return task_prompt

def get_developer_prompt(manual, example):
    developer_prompt = f"""You are an expert in the 3D Dependent Data Description DSL. Your goal is to:
    - Make sure the merged format adheres strictly to the 3D syntax.
    ********* \
    {manual} \
    ********* \
    - Do **NOT add new fields** unless explicitly mentioned.
    - Follow these rules closely:
      - **No nested structs** inside other structs.
      - **No empty structs**—use `unit` for empty cases.
      - Use `message_type` instead of `type` to avoid reserved keywords.
      - `casetype` syntax: casetype _NAME (Type variable_name) {{ switch(variable_name) {{ ... }} }} NAME; Don' format 'Name;' in the end
    Here is an example format:;
    {example}
    """
    return developer_prompt

def agent_config(manual, example):
    engineer = autogen.AssistantAgent(
        name="Developer",
        llm_config={"config_list": config_list},
        is_termination_msg=lambda x: x.get("content", "") and "EverParse succeeded!" in x.get("content", "").rstrip(),
        max_consecutive_auto_reply = 15,
        system_message=get_developer_prompt(manual, example),
    )
    executor = autogen.UserProxyAgent(
        name="Executor",
        system_message="Executor. Execute the 3d code written by the Developer using the custom function simple_parse. You can only execute code using the provided function!! Please ***donot infer and execute the 3D code directly***!",    
        human_input_mode="NEVER",
        code_execution_config={"last_n_messages": 1, "work_dir": "coding", "use_docker": False},
    )

    engineer.register_for_llm(name="simple_parse", description="Parse the 3D code and return the result. If the code is syntactically correct, return 'EverParse succeeded!'. If there are syntax errors, return the error message.")(simple_parse)
    executor.register_for_execution(name="simple_parse")(simple_parse)
    return [engineer, executor]

def agent_loop(manual, rfc, example):
    agent_list = agent_config(manual, example)

    agent_list[1].initiate_chat(
    agent_list[0],
    message=get_task_prompt(rfc)
    )

def merge_format(rfc):
    request_success = False
    with open("DSL/3d_syntax_check.txt", "r") as f:
        manual = f.read()
    with open("example/example_merge.txt", "r") as f:
        example = f.read()
    while not request_success:
        try:
            agent_loop(manual, rfc, example)
            request_success = True
        except Exception as e:
            print(f"Error: {e}")
            print("Retrying......")
            time.sleep(10)
            continue
