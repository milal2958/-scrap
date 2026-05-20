import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os
import plotly.express as px
import plotly.graph_objects as go

# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="정련Sub팀 스크랩 관리 시스템 v3.4", page_icon="⚙️", layout="wide")

# 📱 모바일 상단 잘림 현상 방지 및 가독성 최적화 CSS 패치
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
    
    /* [모바일 전용 최적화] 스마트폰 화면에서 윗부분 잘림 방지 및 여백 극대화 */
    @media (max-width: 768px) {
        /* 시스템 기본 상단 여백 최소화 */
        .block-container {
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
            padding-top: 0.2rem !important; /* 상단 여백을 극단적으로 줄여 짤림 현상 완벽 해결 */
            padding-bottom: 1rem !important;
        }
        /* 상단 빈 공간을 만드는 Streamlit 내부 헤더 영역 강제 축소 및 패딩 제거 */
        header[data-testid="stHeader"] {
            height: 1.5rem !important;
            background: transparent !important;
        }
        /* 공통 탭 바 내부 여백 조절하여 첫 화면 진입 시 컨텐츠가 위로 바짝 붙도록 설정 */
        div[data-testid="stHorizontalBlock"] {
            padding-top: 0px !important;
        }
        /* 메인 제목 크기를 스마트폰 규격에 맞춰 축소하여 시원하게 노출 */
        h1, h2, h3 {
            font-size: 1.5rem !important;
            margin-top: -0.8rem !important;
            margin-bottom: 0.8rem !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

USER_CREDENTIALS = {"21200364": "enslfkd11@", "21601281": "skakstkfkdgowpqkf", "user2": "9999"}
MAC_LIST = [f"A{i}" for i in range(1002, 1014)]

# --- 2. 로그인 로직 ---
def login():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if not st.session_state["logged_in"]:
        st.subheader("⚙️ 정련Sub팀 시스템 로그인")
        with st.form("login_form"):
            user_id = st.text_input("아이디(ID)")
            user_pw = st.text_input("비밀번호(PW)", type="password")
            if st.form_submit_button("로그인"):
                if user_id in USER_CREDENTIALS and USER_CREDENTIALS[user_id] == user_pw:
                    st.session_state["logged_in"], st.session_state["user_id"] = True, user_id
                    st.rerun()
                else: 
                    st.error("❌ 아이디 또는 비밀번호가 틀렸습니다.")
        return False
    return True

# --- 3. 구글 시트 연결 ---
@st.cache_resource
def connect_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            creds_info = st.secrets["gcp_service_account"]
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        else:
            json_file = "secrets.json"
            if os.path.exists(json_file):
                creds = Credentials.from_service_account_file(json_file, scopes=scopes)
            else:
                return None
        client = gspread.authorize(creds)
        return client.open("현장스크랩데이터").sheet1
    except Exception as e:
        return None

# --- 4. 데이터 로드 및 정제 ---
def get_data():
    sheet = connect_google_sheet()
    if sheet:
        try:
            all_values = sheet.get_all_values()
            if len(all_values) > 1:
                df = pd.DataFrame(all_values[1:], columns=all_values[0])
                df.columns = df.columns.str.strip() 
                if '날짜' in df.columns:
                    df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce').dt.date
                if '발생량' in df.columns:
                    df['발생량'] = pd.to_numeric(df['발생량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                if '처리 예정일' in df.columns:
                    df['처리 예정일'] = pd.to_datetime(df['처리 예정일'], errors='coerce')
                if '처리 완료' in df.columns:
                    df['처리 완료'] = df['처리 완료'].apply(lambda x: True if str(x).upper() == 'TRUE' else False)
                return df
        except: pass
    return pd.DataFrame()

# --- 메인 실행 로직 ---
if login():
    st.sidebar.info(f"👷 접속자: **{st.session_state['user_id']}**님")
    if st.sidebar.button("🔒 로그아웃"):
        st.session_state["logged_in"] = False
        st.rerun()

    st.header("⚙️ 정련Sub팀 스크랩 관리 시스템")
    
    if st.sidebar.button("🔄 데이터 최신화"):
        st.cache_resource.clear()
        st.rerun()

    tab1, tab2, tab3 = st.tabs(["📥 발생 등록", "📋 실시간 조회", "📊 데이터 정밀분석"])

    # --- [TAB 1] 데이터 등록 ---
    with tab1:
        st.subheader("📍 발생 정보 입력")
        with st.container():
            row1_col1, row1_col2, row1_col3 = st.columns(3)
            with row1_col1: reg_date = st.date_input("생산 일자", datetime.now())
            with row1_col2: reg_shift = st.selectbox("생산 조", ["A조", "B조", "C조", "D조"])
            with row1_col3: reg_mac = st.selectbox("발생 설비", MAC_LIST)
            
            st.markdown("---")
            st.write("**Comp'd명 입력**")
            comp_col1, comp_col2, comp_col3 = st.columns([1, 2, 4])
            with comp_col1: st.text_input("고정", value="C", disabled=True)
            with comp_col2: comp_choice = st.selectbox("구분", ["1", "2", "3", "4", "Q"])
            with comp_col3: comp_text = st.text_input("나머지 3글자 입력", max_chars=3, placeholder="예: R24").upper()
            final_comp_name = f"C{comp_choice}{comp_text}"

            cause_col, status_col = st.columns(2)
            with cause_col: reg_cause = st.selectbox("추정 원인", ["리쿱영향", "롤러다이 영향", "혼합온도 상승", "설비이상", "트러블로 인한 설비정지", "기타"])
            with status_col: reg_status = st.selectbox("처리 판단", ["선별대기", "스크랩장 이동", "유관부서 판단 필요", "자체처리"])

            unit_col, amt_col = st.columns(2)
            with unit_col:
                u_type = st.radio("단위 선택", ["중량 (kg)", "수량 (batch)"], horizontal=True)
                u_str = "kg" if "중량" in u_type else "batch"
            with amt_col: reg_amt = st.number_input(f"발생량 ({u_str})", min_value=0.0, step=0.1)

            reg_loc = st.text_input("현재 보관 위치")
            reg_detail = st.text_area("발생상황 상세 설명")

            if st.button("🚀 데이터 등록하기"):
                if len(comp_text) < 1 or reg_amt <= 0:
                    st.warning("⚠️ Comp'd명과 발생량을 확인해주세요.")
                else:
                    sheet = connect_google_sheet()
                    if sheet:
                        new_data = [str(reg_date), "", reg_shift, reg_mac, final_comp_name, reg_amt, u_str, reg_status, reg_cause, reg_loc, reg_detail, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state["user_id"], "", "FALSE"]
                        sheet.append_row(new_data)
                        st.success(f"✅ 등록 완료!")

    # --- [TAB 2] 실시간 조회 ---
    with tab2:
        st.subheader("📋 실시간 현황 및 처리 내역")
        df = get_data()
        if not df.empty:
            st.write("🔍 **데이터 필터링**")
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                shift_options = ["전체", "A조", "B조", "C조", "D조"]
                selected_shifts = st.multiselect("생산 조 필터", options=shift_options, default=["전체"])
            with f_col2:
                mac_options = ["전체"] + MAC_LIST
                selected_macs = st.multiselect("발생 호기 필터", options=mac_options, default=mac_options)

            filtered_df = df.copy()
            if "전체" not in selected_shifts and selected_shifts:
                filtered_df = filtered_df[filtered_df['생산 조'].isin(selected_shifts)]
            if "전체" not in selected_macs and selected_macs:
                filtered_df = filtered_df[filtered_df['발생 호기'].isin(selected_macs)]

            if '요일' in filtered_df.columns:
                filtered_df = filtered_df.drop(columns=['요일'])
            
            current_cols = list(filtered_df.columns)
            target_cols = ["처리 예정일", "처리 완료"]
            for col in target_cols:
                if col in current_cols: current_cols.remove(col)
            
            insert_idx = 0 
            for col in reversed(target_cols):
                if col in filtered_df.columns: current_cols.insert(insert_idx, col)
            
            try:
                edited_df = st.data_editor(
                    filtered_df,
                    column_order=current_cols,
                    column_config={
                        "처리 예정일": st.column_config.DateColumn("📅 처리 예정일", format="YYYY-MM-DD"),
                        "처리 완료": st.column_config.CheckboxColumn("✅ 완료"),
                        "날짜": st.column_config.DateColumn("생산 일자", disabled=True),
                        "발생량": st.column_config.NumberColumn("발생량", disabled=True),
                        "추정 원인": st.column_config.SelectboxColumn("추정 원인", options=["리쿱영향", "롤러다이 영향", "혼합온도 상승", "설비이상", "트러블로 인한 설비정지", "기타"]),
                        "처리 판단": st.column_config.SelectboxColumn("처리 판단", options=["선별대기", "스크랩장 이동", "유관부서 판단 필요", "자체처리"])
                    },
                    hide_index=True,
                    use_container_width=True
                )

                if st.button("💾 변경사항 구글 시트에 저장하기"):
                    sheet = connect_google_sheet()
                    if sheet:
                        with st.spinner("구글 시트 업데이트 중..."):
                            save_df = edited_df.copy()
                            save_df['처리 완료'] = save_df['처리 완료'].apply(lambda x: "TRUE" if x else "FALSE")
                            if '처리 예정일' in save_df.columns:
                                save_df['처리 예정일'] = pd.to_datetime(save_df['처리 예정일']).dt.strftime('%Y-%m-%d').fillna("")
                            if '요일' not in save_df.columns:
                                save_df.insert(1, '요일', "")
                            update_vals = save_df.astype(str).values.tolist()
                            sheet.update(f'A2:O{len(update_vals)+1}', update_vals)
                            st.success("✅ 업데이트 완료!")
            except Exception as e:
                st.error(f"데이터 에디터 로드 실패: {e}")
        else:
            st.info("데이터가 없습니다.")

    # --- [TAB 3] 발생 정밀분석 ---
    with tab3:
        df_analysis = get_data()
        
        if not df_analysis.empty:
            # 데이터 전처리 (단위 환산)
            df_analysis['발생량_kg'] = df_analysis.apply(
                lambda x: x['발생량'] * 200 if 'batch' in str(x['단위']).lower() else x['발생량'], axis=1
            )
            df_analysis['날짜_dt'] = pd.to_datetime(df_analysis['날짜'])
            df_analysis['년월'] = df_analysis['날짜_dt'].dt.strftime('%Y-%m')

            # --- [섹션: 트렌드 조회 기간 설정] ---
            st.markdown("#### 📅 조별 및 월별 발생 트렌드 기간 설정")
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                start_date = st.date_input("시작일", datetime.now().replace(day=1))
            with date_col2:
                end_date = st.date_input("종료일", datetime.now())

            # 설정한 기간으로 트렌드 데이터 필터링
            mask = (df_analysis['날짜'] >= start_date) & (df_analysis['날짜'] <= end_date)
            df_trend_filtered = df_analysis.loc[mask].copy()

            # --- [그래프 1: 조별/월별 발생 추이] ---
            if not df_trend_filtered.empty:
                monthly_summary = df_trend_filtered.groupby(['년월', '생산 조'])['발생량_kg'].sum().reset_index()
                monthly_summary = monthly_summary.sort_values(by=['년월', '생산 조'])

                # 데이터 구조에 따른 모바일 반응형 뷰포트 트리거
                is_mobile_view = len(monthly_summary['년월'].unique()) >= 3 or len(monthly_summary) >= 8

                if is_mobile_view:
                    # 📱 모바일 버전: 가로형(Horizontal) 바 차트
                    fig_monthly = px.bar(
                        monthly_summary, 
                        x='발생량_kg', 
                        y='생산 조', 
                        color='년월',
                        barmode='group', 
                        text_auto='.1f',
                        orientation='h',
                        labels={'발생량_kg': '발생량 (kg)', '년월': '월별', '생산 조': '생산 조'},
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                    fig_monthly.update_traces(textposition='outside')
                else:
                    # 💻 PC 버전: 세로형(Vertical) 바 차트
                    fig_monthly = px.bar(
                        monthly_summary, 
                        x='생산 조', 
                        y='발생량_kg', 
                        color='년월',
                        barmode='group', 
                        text_auto='.1f',
                        labels={'발생량_kg': '발생량 (kg)', '년월': '월별'},
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                    fig_monthly.update_traces(textposition='outside')
                
                # 디자인 레이아웃 설정 (오류 차단 완료)
                fig_monthly.update_layout(
                    plot_bgcolor='rgba(250,250,250,0.8)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=20, b=30, l=20, r=20),
                    legend=dict(
                        orientation="h", 
                        yanchor="top", 
                        y=-0.15, 
                        xanchor="center", 
                        x=0.5,
                        title_text=""
                    ),
                    font=dict(family="Pretendard, sans-serif", size=12),
                    hovermode="closest"
                )
                
                fig_monthly.update_xaxes(showgrid=True, gridcolor='#E5E5E5', zeroline=False)
                fig_monthly.update_yaxes(showgrid=True, gridcolor='#E5E5E5', zeroline=False)
                
                st.plotly_chart(fig_monthly, use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("⚠️ 선택한 기간에 해당하는 트렌드 데이터가 없습니다.")

        else:
            st.info("데이터를 먼저 등록해 주세요.")