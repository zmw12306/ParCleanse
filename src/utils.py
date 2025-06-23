import os
import subprocess
import shutil
import random
import json
from botocore.config import Config

import boto3
from botocore.exceptions import BotoCoreError, ClientError
import asyncio

# Create a session to access credentials
session = boto3.Session()
credentials = session.get_credentials()
config_list = [ { ..., "temperature": 0.0} ] # todo: replace with actual config list


# Access the credentials
current_credentials = credentials.get_frozen_credentials()
class BedrockClient:
    def __init__(self, region_name, config):
        self.client = boto3.client(
            "bedrock-runtime", region_name=region_name, config=config
        )

    def invoke_model(self, model_id, input_data, content_type="application/json"):
        try:
            response = self.client.invoke_model(
                modelId=model_id, contentType=content_type, body=input_data
            )
            return response["body"].read().decode("utf-8")
        except (BotoCoreError, ClientError) as error:
            print("Error happened calling bedrock")
            return {"error": str(error)}


async def query(prompt):
    config = Config(read_timeout=20)
    # Need to request access to foundation models https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html
    model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    br_client = BedrockClient("us-west-2", config)
    body = json.dumps(
        {
            "messages": prompt,
            "max_tokens": 1600,
            "anthropic_version": "bedrock-2023-05-31",
            "temperature": 0,
            "top_k": 50,
        }
    )
    
    br_response = br_client.invoke_model(model_id=model_id, input_data=body)
    response = json.loads(br_response)  # Parse if it's a string
    return response["content"][0]["text"]

def askLLM(prompt):
    test_prompt = [
        {"role": "user", "content": prompt},
    ]
    response = asyncio.run(query(test_prompt))
    return response

def simple_parse(code:str, module_name:str):
    module_name = module_name.upper()
    base_path = "everparse/everparse_files"
    while True:
        dir_path = os.path.join(base_path, module_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)  # Create the full directory path
            print(f"Directory {dir_path} created.")
            break
        else:
            print(f"Directory {dir_path} already exists.")
            module_name = module_name + str(random.randint(0, 10))  # Append a random number to avoid conflicts
            
    filename = f"{module_name}.3d"
    filepath = os.path.join(dir_path, filename)
    with open(filepath, "w") as f:
        f.write(code)
        print(f"Finish writing 3d code under {filepath}")
    print(dir_path)
    print(os.getcwd())
    os.chdir(dir_path)
    print(os.getcwd())
    call = f"bash ../../everparse.sh --no_clang_format {filename}"
    print("Calling everparse.....")
    print(call)
    process = subprocess.Popen(
        call, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()
    if stdout:
        output_dump = stdout.decode("utf-8")
    else:
        output_dump = ""
    if stderr:
        output_err = stderr.decode("utf-8")
    else:
        output_err = ""
    print("EverParse output:")
    print(output_dump)
    print("EverParse error:")
    print(output_err)
    os.chdir("../../..")  # Change back to the grandparent directory

    if "EverParse succeeded" not in output_dump:  
        print("Everparse unsuccess")
        if  "Cannot verify u" in output_err and "subtraction" in output_err:
            output_dump = "\nThe old format has Uint substraction, e.g., use x-y without guarantee x>=y before use of x-y"
        elif "Cannot verify u" in output_err and "addition" in output_err:
            output_dump = "\nThe old format has Uint addition, e.g., use x + y wihout guarantee x + y < type bound, e.g., UINT8BE Plen, should have Plen <= 255 - 7 before use (Plen + 7)"
        elif "unknown language unknown" in output_err:
            output_dump = "\nPlease regenerate and Execute code with the supplied function simple_parse only!"
        elif "Error 168" in output_dump:
            output_dump = "Syntax error, type is a reserved keyword"
        # else:         
        #     output_dump = "ERROR, try again and Execute code with the supplied function simple_parse only: " + output_dump 
            # output_dump += "\nPlease regenerate!DO NOT use 'type' as an identifier! Do NOT use 'struct.field' , consider expand the struct fields with the current struct! casetype syntax should be as follows: casetype _NAME (Type variable_name) {{ switch(variable_name){{ ...}} }} NAME; Type variable_name should not be defined inside the casetype, e.g., {{..Type variable_name; _NAME(variable_name);...}}, Do not add default type in casetype!!"
        shutil.rmtree(dir_path)

    else:
        output_dump +="\nEverParse succeeded!\n"
    
    return output_err, output_dump
