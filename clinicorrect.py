import json
import streamlit as st
import toml

from src import Evaluator
from src.parser import get_pdf_sections

import regex as re


# Make the page wide by default

################################################################################
# Initializations
################################################################################
# Create a regex for identifying the following pattern: ++word++
pattern = r"\+\+(.*?)\+\+"

def color_text(text, color="red"):
    return f'<span style="color:{color}">{text}</span>'

config = toml.load("config.toml")

st.set_page_config(
    page_title=config["page"]["title"], 
    page_icon=config["page"]["logo"], 
    layout="wide"
    )


################################################################################
# Document Selector 
################################################################################

# Add a page where the user can upload a PDF file
st.markdown("# CliniCorrect")
data_file = st.file_uploader("Bitte wählen Sie einen Entlassungsbrief", type=["pdf"])

if not data_file:
    # Clear the session state
    st.session_state.clear()
    st.stop()


data = data_file.read()

extracted_sections = get_pdf_sections(data)
extracted_sections = {k: v for k, v in extracted_sections.items() if v.strip()}

for section, text in extracted_sections.items():
    if not f"{section}_text" in st.session_state:
        st.session_state[f"{section}_text"] = text

################################################################################
# Sidebar Setup
################################################################################

with st.sidebar:
    st.image(config["page"]["logo"], width=150)

with st.sidebar:
    st.markdown("# Konfiguration")

    providers = config["models"]["providers"]
    st.selectbox("API Provider", providers, key="api_provider")

    models = config["models"][st.session_state.get("api_provider")]["names"]

    st.selectbox("Model", models, key="model_name")
    st.text_input("API Key", type="password", key="api_key")

section_names = config["sections"]["names"]
section_names.sort()

with st.sidebar:
    st.markdown("# Aufgaben auswählen")
    all_tasks = list(config["tasks"].keys())

    available_tasks = []

    selected_sections = [
        name for name in section_names 
        if st.session_state.get(f"include_{name}")
        ]

    for task in all_tasks:
        required_sections = config["tasks"][task]["sections"]

        diff = set(required_sections).difference(set(selected_sections))

        if not diff:
            available_tasks.append(task)


    for task in all_tasks:
        st.checkbox(
            config["tasks"][task]["tab_display"],
            value=task in available_tasks,
            key=f"task_{task}",
            disabled=task not in available_tasks
        )

        if task not in available_tasks:
            required_sections = config["tasks"][task]["sections"]
            diff = set(required_sections).difference(set(selected_sections))
            st.info(f'Diese Abschnitte fehlen: {" ,".join(diff)}', icon="ℹ️")

    st.session_state.selected_tasks = [
        task for task in all_tasks
        if st.session_state.get(f"task_{task}")
        ]
    
with st.sidebar:
    st.markdown("# Abschnittsauswahl")
    sect_cols = st.columns(2)

    for i, name in enumerate(section_names):
        col_idx = i % len(sect_cols)

        value = False
        if name in extracted_sections:
            value = True

        sect_cols[col_idx].checkbox(name, value=value, key=f"include_{name}")

################################################################################
# Initializations
################################################################################
evaluator = Evaluator(
    config=config,
    provider=st.session_state.get("api_provider"),
    model_name=st.session_state.get("model_name"),
    api_key=st.session_state.get("api_key")
)

################################################################################
# App main display
################################################################################

disp_cols = st.columns(2)

####################################
# Input Text Areas
####################################
disp_cols[0].markdown("# Originaltexte")
for section in section_names:
    if st.session_state.get(f"include_{section}"):
        disp_cols[0].markdown(f"### {section}")

        disp_cols[0].text_area(
            label=f"{section}", 
            key=f"{section}_text",
            height=300,
            label_visibility="hidden"
        )


####################################
# CliniCorrect Output
####################################
disp_cols[1].markdown("# CliniCorrect Ausgabe")

if disp_cols[1].button("CliniCorrect me!"):
    selected_tasks = st.session_state.get("selected_tasks")
    selected_sections = [
        name for name in section_names 
        if st.session_state.get(f"include_{name}")
        ]

    for task in selected_tasks:
        task_display_name = config["tasks"][task]["tab_display"]
        disp_cols[1].markdown(f"## {task_display_name}")

        if task == "typos":
            
            user_prompt = config["tasks"][task]["user_prompt"]

            case_data = {
                section: st.session_state.get(f"{section}_text")
                for section in selected_sections
            }
             
            output = evaluator.evaluate_task(
                task=task,
                document_json=case_data,
                case_name="case_name",
                output_section="output_section"
                )
            
            sections_response = output.get("response", dict())
            
            for sect_name, sect_resp in sections_response.items():
                disp_cols[1].markdown(f"## {sect_name}")
                response = sect_resp
                response = response.replace(user_prompt, "")
                
                matches = re.finditer(pattern, response)
                response = re.sub(pattern, lambda x: color_text(x.group(1)), response)
                disp_cols[1].markdown(response, unsafe_allow_html=True)
                

        else:
            user_prompt = config["tasks"][task]["user_prompt"]
            output_section = config["tasks"][task]["output-section"]

            case_data = {
                section: st.session_state.get(f"{section}_text")
                for section in selected_sections
            }

            
            output = evaluator.evaluate_task(
                task=task,
                document_json=case_data,
                case_name="case_name",
                output_section=output_section
                )

            sections_response = output.get("response", dict())
            reply = sections_response.get(output_section, dict())
            disp_cols[1].write(reply)
        
            

