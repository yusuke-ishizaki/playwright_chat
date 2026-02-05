import streamlit as st
import os
import json
import asyncio
import nest_asyncio
from dotenv import load_dotenv
from typing import List
import traceback

# Install Playwright browsers (important for Streamlit Cloud deployment)
os.system("playwright install")

from models.scenario import BrowserScenario
from agents.browser_agent import BrowserAgent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

# Apply nest_asyncio to allow async execution in Streamlit
nest_asyncio.apply()

# Load environment variables
# Try st.secrets first (for Streamlit Cloud), then fall back to .env (for local development)
def get_api_key():
    """Get API key from st.secrets or environment variables."""
    try:
        # Try Streamlit secrets first
        return st.secrets["GOOGLE_API_KEY"]
    except (KeyError, FileNotFoundError):
        # Fall back to .env file for local development
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            st.error("GOOGLE_API_KEY not found. Please set it in .streamlit/secrets.toml or .env file.")
        return api_key

# Set the API key as an environment variable for langchain
os.environ["GOOGLE_API_KEY"] = get_api_key() or ""

# Page Config
st.set_page_config(
    page_title="Playwright ブラウザエージェント",
    page_icon="🤖",
    layout="wide"
)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_scenario" not in st.session_state:
    st.session_state.current_scenario = None
if "agent_state" not in st.session_state:
    st.session_state.agent_state = "planning" # planning, executing, finished
if "execution_results" not in st.session_state:
    st.session_state.execution_results = {}

def normalize_step(step: dict) -> dict:
    """Convert recorded step to BrowserAction format if needed."""
    # If it already has the required fields, return as is
    if "action_type" in step and "description" in step:
        return step
        
    # Initialize fields
    action_type = "click" # Default
    selector = None
    value = step.get("value")
    description = "Unknown step"
    
    # Extract selector information
    tag_name = step.get("tagName", "").lower()
    step_id = step.get("id")
    class_name = step.get("className")
    xpath = step.get("xpath")
    name = step.get("name")
    href = step.get("href")
    text_content = step.get("textContent")
    
    # Construct selector
    if step_id:
        selector = f"#{step_id}"
    elif class_name:
        # Use the first class or all classes joined by dots
        # Cleaning up class string
        classes = [c for c in class_name.split() if c]
        if classes:
            selector = "." + ".".join(classes)
    elif name:
        selector = f"[name='{name}']"
    elif href and tag_name == "a":
        selector = f"a[href='{href}']"
    elif xpath:
        selector = xpath
    elif tag_name:
        selector = tag_name
        
    # Determine action type and description
    recorded_type = step.get("type", "").lower()
    url = step.get("url", "")
    domain = ""
    if url:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = f"[{parsed.netloc}] "
    
    if recorded_type == "input" or recorded_type == "change" or (tag_name == "input" and value is not None):
        action_type = "fill"
        
        # Simplify element name for description
        element_name = "入力欄"
        if tag_name == "textarea":
            element_name = "テキストエリア"
            
        description = f"{domain}{element_name}に '{value}' を入力"
    elif recorded_type == "goto":
        action_type = "goto"
        value = step.get("url") or value
        selector = None
        description = f"'{value}' に移動"
    else:
        # Default to click
        action_type = "click"
        if text_content:
            description = f"'{text_content}' をクリック"
        elif selector:
            description = f"'{selector}' をクリック"
        else:
            description = "要素をクリック"
        
    return {
        "action_type": action_type,
        "selector": selector,
        "value": value,
        "description": description
    }

def load_scenario(data, filename: str):
    """Load scenario from JSON data."""
    try:
        # If data is a list, assume it's a list of steps
        if isinstance(data, list):
            data = {
                "title": os.path.splitext(filename)[0],
                "steps": data
            }

        # Normalize steps if they exist
        if "steps" in data:
            data["steps"] = [normalize_step(s) for s in data["steps"]]

        # Validate with Pydantic
        scenario = BrowserScenario(**data)
        st.session_state.current_scenario = scenario
        
        # Add initial system message
        initial_msg = f"シナリオ '{filename}' を読み込みました。\n\n**現在のプラン:**\n"
        for i, step in enumerate(scenario.steps, 1):
            initial_msg += f"{i}. {step.description}\n"
        initial_msg += "\n変更は必要ですか？"
        
        st.session_state.messages = [AIMessage(content=initial_msg)]
        st.session_state.agent_state = "planning"
        
    except Exception as e:
        st.error(f"ファイルの読み込みエラー: {e}")

# Sidebar
with st.sidebar:
    st.title("シナリオファイル")
    
    uploaded_file = st.file_uploader("シナリオファイル (.json) をアップロード", type=["json"])
    
    if st.button("シナリオを読み込む"):
        if uploaded_file is not None:
            try:
                data = json.load(uploaded_file)
                load_scenario(data, uploaded_file.name)
            except Exception as e:
                st.error(f"JSONパースエラー: {e}")
        else:
            st.warning("ファイルをアップロードしてください。")

# Main Area
st.title("🤖 ブラウザAIエージェント")

# Chat Interface
for msg in st.session_state.messages:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.markdown(msg.content)
    elif isinstance(msg, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(msg.content)

# Chat Input (Only active in planning mode)
if st.session_state.agent_state == "planning":
    if prompt := st.chat_input("プランを修正するか、'run' と入力して実行してください"):
        # Add user message
        st.session_state.messages.append(HumanMessage(content=prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        if prompt.lower() == "run" or prompt.lower() == "execute":
             st.session_state.agent_state = "ready_to_execute"
             st.rerun()
        else:
            # Call LLM to modify scenario
            with st.spinner("プランを更新中..."):
                try:
                    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite-preview", temperature=0)
                    parser = PydanticOutputParser(pydantic_object=BrowserScenario)
                    
                    template = """
                    あなたはブラウザ自動化アシスタントです。
                    現在のシナリオJSON:
                    {current_json}
                    
                    ユーザーの指示: {user_input}
                    
                    ユーザーの指示に基づいてJSONを更新してください。
                    構造は変更せず、値の変更やステップの追加/削除のみを行ってください。
                    {format_instructions}
                    """
                    
                    prompt_template = ChatPromptTemplate.from_template(template)
                    chain = prompt_template | llm | parser
                    
                    current_json = st.session_state.current_scenario.model_dump_json()
                    new_scenario = chain.invoke({
                        "current_json": current_json,
                        "user_input": prompt,
                        "format_instructions": parser.get_format_instructions()
                    })
                    
                    st.session_state.current_scenario = new_scenario
                    
                    # Response
                    response_msg = f"リクエストに基づいてプランを更新しました。\n\n**新しいプラン:**\n"
                    for i, step in enumerate(new_scenario.steps, 1):
                        response_msg += f"{i}. {step.description}\n"
                    response_msg += "\nよろしければ 'run' と入力して実行してください。"
                    
                    st.session_state.messages.append(AIMessage(content=response_msg))
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"プラン更新エラー: {e}")

# Execution Phase
if st.session_state.agent_state == "ready_to_execute":
    st.info("実行準備完了。ブラウザエージェントを起動します...")
    
    async def run_agent():
        agent = BrowserAgent(headless=True)
        status_container = st.status("シナリオを実行中...", expanded=True)
        
        try:
            # We can't easily stream updates from the agent in this simple setup without callbacks,
            # so we'll just run it and show results. 
            # For a better UX, we could pass a callback to the agent.
            status_container.write("ブラウザを初期化中...")
            
            results = await agent.execute_scenario(st.session_state.current_scenario)
            
            st.session_state.execution_results = results
            st.session_state.agent_state = "finished"
            status_container.update(label="実行完了！", state="complete", expanded=False)
            st.rerun()
            
        except Exception as e:
            st.error(f"実行失敗: {e}")
            traceback.print_exc() # Print the full traceback to the logs
            status_container.update(label="実行失敗", state="error")
            await agent.stop()

    asyncio.run(run_agent())

# Results Display
if st.session_state.agent_state == "finished":
    st.success("シナリオが正常に実行されました！")
    
    results = st.session_state.execution_results
    
    st.subheader("実行ビデオ")
    if "video_path" in results and results["video_path"]:
        st.video(results["video_path"])
    
    st.subheader("ステップ結果")
    for res in results.get("results", []):
        st.text(res)
        
    st.subheader("スクリーンショット")
    # List screenshots in media/screenshots
    screenshots_dir = "media/screenshots"
    if os.path.exists(screenshots_dir):
        images = sorted([os.path.join(screenshots_dir, f) for f in os.listdir(screenshots_dir) if f.endswith(".png")])
        if images:
            st.image(images, caption=[os.path.basename(img) for img in images], width=600)