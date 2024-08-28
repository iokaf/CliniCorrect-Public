import os
import ollama

from pathlib import Path
import json

import openai 

import warnings
import datetime

import google
import google.generativeai as genai

class Evaluator:
    """Class to combine text passage, prompt and model"""

    def __init__(self, config: dict, provider: str, model_name: str, api_key: str = ""):

        self.source = provider
        self.model_name = model_name

        if self.source == "OpenAI":
            self.client = openai.OpenAI(api_key=api_key)

        elif self.source == "Google":
            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(model_name)

        elif self.source == "Ollama":
            self.client = ollama
        
        self.task_config = config["tasks"]

        self.save_path = config["general"].get("save_path", None)
        self.verbose = config["general"].get("verbose", False)
        
        if not self.save_path is None:
            os.makedirs(Path(self.save_path).parent, exist_ok=True)
            if not os.path.exists(self.save_path):
                with open(self.save_path, "w") as f:
                    json.dump([], f)


    def generate(self, system_prompt: str, user_prompt:str, passage: str):
        if self.source == "OpenAI":
            return self.generate_openai(system_prompt, user_prompt, passage)
        
        if self.source == "Google":
            return self.generate_google(system_prompt, user_prompt, passage)
        
        elif self.source == "Ollama":
            return self.generate_ollama(system_prompt, user_prompt, passage)
        
        else:
            raise ValueError("Model not supported")

    def generate_ollama(self, system_prompt: str, user_prompt:str, passage: str):

        response = self.client.chat(
            model=self.model_name,

            messages=[
                {"role": "system", "content": f"{system_prompt}"},
                {"role": "user", "content": f"{user_prompt}: {passage}"}
            ],
            stream=False,
            options={
                "temperature": 0.0,
            }
            )
        
        response = response.get("message", dict()).get("content", "")
        # response = response['message']['content']
        return response

    def generate_openai(self, system_prompt: str, user_prompt:str, passage: str):
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": f"{system_prompt}"},
                    {"role": "user", "content": f"{user_prompt}: {passage}"}
                ]
                )
        except openai.APIConnectionError:
            raise ValueError("OpenAI API key missing.")    
        except openai.AuthenticationError as e:
            raise ValueError("OpenAI API key is wrong.")
        
        return completion.choices[0].message.content
    
    def generate_google(self, system_prompt: str, user_prompt:str, passage: str):
        try:
            history=[
                {"role": "user", "parts": [system_prompt]},
            ]

            chat = self.client.start_chat(history=history)

            response = chat.send_message(f"{user_prompt}: {passage}", stream=False)
            response = response.candidates
            
            if len(response) == 0:
                raise ValueError("No response from the model")
            response = response[0]

            response = response.content.parts
            
            if len(response) == 0:
                raise ValueError("No response content parts from the model")
            
            response = response[0].text

        except google.api_core.exceptions.InvalidArgument as e:
            raise ValueError("Google API key is wrong.")
        
        # except google.api_core.exceptions.DefaultCredentialsError as e:
        #     raise ValueError("Google API key missing.")
        return response


    def configure_base_prompt(self, base_prompt, passage):
        return base_prompt + passage

    def create_passage(self, document_json: dict, section_names: list[str]):
        passage = ""

        for name in section_names:
            section_text = document_json.get(name, "")
            if section_text == "":
                warnings.warn(f"Section {name} not found in document")
                continue

            passage += name + "\n"
            passage += document_json[name]
            passage += "\n\n"

        if passage == "":
            warnings.warn("No passage found for the given section names")
            return None
        
        return passage

    def generate_typos_response(self, document_json: dict):  
        """Evaluates a document for typos.
        
        Args:
            document_json (dict): A dictionary containing the text of the document

        Returns:
            dict[str, str]: A dictionary containing the typos in the document. Keys
            are the different section names of the evaluated document. Values are the
            typos found in the respective section.
        """

        task_data = self.task_config.get("typos", "")

        system_prompt = task_data["system_prompt"]
        user_prompt = task_data["user_prompt"]

        typos_output = dict()

        for sec_name, sec_content in document_json.items():
            if sec_content == "":
                continue

            resp = self.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                passage=sec_content
            )

            typos_output[sec_name] = resp

        return typos_output


    def evaluate_task(
            self, 
            task, 
            document_json: dict, 
            output_section: str, 
            case_name: str):
        
        task_data = self.task_config.get(task, "")
        section_names = task_data["sections"]
        
        system_prompt = task_data["system_prompt"]
        user_prompt = task_data["user_prompt"]

        if self.verbose:
            print(f"Generating response for task: {task}")

        if task == "typos":
            passage = ""
            response = self.generate_typos_response(document_json)
        else:
            passage = self.create_passage(document_json, section_names)

            if passage is None:
                raise ValueError("No text entry found for any of the given section names")

            response = self.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                passage=passage
            )

            response = {output_section: response}


        output = dict(
                task=task, 
                system_prompt=system_prompt, 
                user_prompt=user_prompt, 
                passage=passage, 
                response=response,
                case_name=case_name
                )
        
        if self.save_path is not None:
            self.save(
                **output
                )

        return output
    
    def save(self, **kwargs):
        task = kwargs.get("task", "na")
        system_prompt = kwargs.get("system_prompt", "na")
        user_prompt = kwargs.get("user_prompt", "na")
        passage = kwargs.get("passage", "na")
        response = kwargs.get("response", "na")
        case_name = kwargs.get("case_name", "na")

        entry = {
            "case": case_name,
            "task": str(task),
            "system_prompt": str(system_prompt),
            "user_prompt": str(user_prompt),
            "passage": str(passage),
            "response": str(response),
            "timestamp": f"{datetime.datetime.now()}"
        }

        if not os.path.exists(self.save_path):
            # Write the [entry] to the file
            with open(self.save_path, "w") as f:
                json.dump([entry], f, indent=2)

        else:
            with open(self.save_path, "r") as f:
                data = json.load(f)
            
            data.append(entry)

            with open(self.save_path, "w") as f:
                json.dump(data, f, indent=2)

