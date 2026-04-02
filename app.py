import streamlit as st
import asyncio
import os
import datetime
import google.generativeai as genai
from mcp import ClientSession
from mcp.client.sse import sse_client

# ==========================================
# 1. 설정 부분
# ==========================================
# Streamlit Secrets에서 API 키 호출
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# Render에 띄워둔 MCP 서버 주소 (자신의 주소로 변경/확인 필요)
MCP_SERVER_URL = "https://vkd-mcp.onrender.com/sse" 

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
    """
    Verkada 시스템에서 특정 시간 범위의 카메라 알림(Alerts)을 조회합니다.
    
    Args:
        start_time_iso: 조회 시작 시간 (ISO 8601 형식, 예: "2026-04-01T00:00:00")
        end_time_iso: 조회 종료 시간 (ISO 8601 형식, 예: "2026-04-01T23:59:59")
        notification_type: 알림 유형 (예: motion, person_of_interest 등). 특정 유형이 없으면 빈 문자열("") 입력.
    """
    return asyncio.run(fetch_mcp_tool(start_time_iso, end_time_iso, notification_type))

# ==========================================
# 3. 모델 설정 (System Instruction)
# ==========================================
current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
sys_instruct = f"""
당신은 Verkada 물리적 보안 시스템을 관리하는 전문 AI 어시스턴트입니다.
현재 한국 시간은 {current_time_str} 입니다. 

[중요 지침]
1. 사용자가 '오늘', '어제' 등 시간을 언급하면 위 시간을 기준으로 계산하여 도구를 호출하세요.
2. 만약 질문에 시간 정보가 아예 없거나 너무 모호해서 검색 범위를 잡을 수 없다면 (예: "알림 보여줘", "사람 감지된 거 있어?"), 절대로 도구를 임의로 호출하지 마세요.
3. 정보가 부족할 경우, 사용자에게 "어느 시간대의 알림을 조회할까요? (예: 오늘 오전 9시 ~ 오후 3시)"라고 친절하게 먼저 되물어보세요.
"""

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    tools=[get_camera_alerts],
    system_instruction=sys_instruct 
)

# ==========================================
# 4. Streamlit 웹 UI 구현 및 예외 처리
# ==========================================
st.set_page_config(page_title="Verkada 보안 어시스턴트", page_icon="🚨")
st.title("🚨 Verkada 보안 어시스턴트")
st.caption("자연어로 카메라 알림 이벤트를 조회해 보세요. (예: 오늘 오전 9시 ~ 12시 알림 보여줘)")

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
                error_msg = str(e)
                # 에러 발생 시 사용자 친화적인 메시지로 우회
                if "MALFORMED_FUNCTION_CALL" in error_msg:
                    st.warning("🤔 시간이나 조건이 명확하지 않아 조회하지 못했습니다. '오늘 오전 10시부터 12시까지 모션 알림'처럼 구체적인 시간을 포함해서 다시 말씀해 주시겠어요?")
                else:
                    st.error(f"시스템 오류가 발생했습니다: {error_msg}")
