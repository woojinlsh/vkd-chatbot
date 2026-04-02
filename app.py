import streamlit as st
import asyncio
import os
import google.generativeai as genai
from mcp import ClientSession
from mcp.client.sse import sse_client

# ==========================================
# 1. 설정 부분 (Streamlit Secrets에서 API 키 호출)
# ==========================================
# 🚨 절대 여기에 API 키를 직접 적지 마세요!
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# Render에서 배포 성공한 MCP 서버 주소 (끝에 /sse 필수)
MCP_SERVER_URL = "https://vkd-mcp.onrender.com/sse" 

# Gemini 초기화
genai.configure(api_key=GEMINI_API_KEY)

# ==========================================
# 2. MCP 통신 및 Gemini 도구(Tool) 정의
# ==========================================
async def fetch_mcp_tool(start_time_iso, end_time_iso, notification_type):
    async with sse_client(MCP_SERVER_URL) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            result = await session.call_tool(
                "get_camera_alerts", 
                arguments={
                    "start_time_iso": start_time_iso,
                    "end_time_iso": end_time_iso,
                    "notification_type": notification_type
                }
            )
            return result.content[0].text

def get_camera_alerts(start_time_iso: str, end_time_iso: str, notification_type: str = "") -> str:
    """특정 시간 범위 내의 Verkada 카메라 알림 이벤트를 조회합니다."""
    return asyncio.run(fetch_mcp_tool(start_time_iso, end_time_iso, notification_type))

# Gemini 모델 설정
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    tools=[get_camera_alerts]
)

# ==========================================
# 3. Streamlit 웹 UI 구현
# ==========================================
st.set_page_config(page_title="Verkada 보안 어시스턴트", page_icon="🚨")
st.title("🚨 Verkada 보안 어시스턴트")
st.caption("자연어로 카메라 알림 이벤트를 조회해 보세요.")

if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(enable_automatic_function_calling=True)

for message in st.session_state.chat_session.history:
    if hasattr(message, 'parts') and message.parts and getattr(message.parts[0], 'text', None):
        role = "assistant" if message.role == "model" else "user"
        with st.chat_message(role):
            st.markdown(message.parts[0].text)

if user_input := st.chat_input("메시지를 입력하세요..."):
    with st.chat_message("user"):
        st.markdown(user_input)
    
    with st.chat_message("assistant"):
        with st.spinner("Verkada 시스템을 확인하는 중입니다..."):
            try:
                response = st.session_state.chat_session.send_message(user_input)
                st.markdown(response.text)
            except Exception as e:
                st.error(f"오류가 발생했습니다: {str(e)}")
