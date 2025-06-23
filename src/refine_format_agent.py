import os
import time
import autogen
import sys
sys.path.append(os.path.abspath('../../'))
from utils import simple_parse, config_list

def get_task_prompt(oldformat, rfc, parserlog):
    task_prompt = f"""
    Your task is to find and fix any **errors in the 3D code** for the  protocol according to the provided RFC specifications. Do not change struct names. The error could be **missing constraints**, **incorrect field lengths**, or **incorrect struct**, fix them.
    !!!The 3D code generated packet got: {parserlog}, please fix this error in the 3d format.!!!
    
    **Below is the incorrect 3D code:** 
    {oldformat}

    **RFC reference:**
    {rfc}

    Follow these steps carefully:
    1. **DO NOT infer or interpret the 3D code directly**.
    2. Execute only the `simple_parse` function to check correctness.
    3. **Identify missing constraints** (like length or version constraints) or incorrect details in the 3D code.
  
    Remember, you are working with **3D code** (not C code). Any change should follow 3D syntax. Ensure the generated code complies with both the RFC and the 3D language rules.
    """
    return task_prompt

def get_developer_prompt(manual, example):
    developer_prompt = f""" You need to fix the 3D code by addressing **any structural, constraint, or length-related issues**. Follow these steps carefully:
    1. **Incorrect or missing constraints**:
        - Check for missing or incorrect constraints, especially for fields like the version (`Ver`), length, or any other field that must adhere to a specific value.
        - For example, the incorrent 3d code defines: ```UINT8BE Vers : 3;```, while the RFC states `This document defines protocol version 1.` Correct this by adding a constraint like:
          ```
          UINT8BE Vers : 3 {{ Vers == 1 }};
          ```
    2. **Incorrect length expressions**:
        - Ensure all fields that are variable-length (or have length requirements) are clearly defined. If needed, add a length parameter at the entrypoint.

    You make sure that any 3d code follows syntax rules in the manual: \
    ********* \
    {manual} \
    ********* \

    Call the provided function only, make sure you pass syntactically correct code to the funtion only, do not wrap your code. Listen to the feedback from the parsing function and fix any syntax mistakes you make. Explain why you chose to add an action when you do. You MUST retain all fields in the code to translate.
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

def agent_loop(manual, old_format, rfc, example, parserlog):
    agent_list = agent_config(manual, example)

    agent_list[1].initiate_chat(
    agent_list[0],
    message=get_task_prompt(old_format, rfc, parserlog)
    )

def refine_format(old_format, rfc, parserlog):
    request_success = False
    with open("DSL/3d_syntax_check.txt", "r") as f:
        manual = f.read()
    with open("example/example.txt", "r") as f:
        example = f.read()
    while not request_success:
        try:
            agent_loop(manual, old_format, rfc, example, parserlog)
            request_success = True
        except Exception as e:
            print(f"Error: {e}")
            print("Retrying......")
            time.sleep(10)
            continue