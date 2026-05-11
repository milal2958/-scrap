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

# 가독성을 위한 CSS 추가
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
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

    # 👇 [수정 1] 타이틀 크기 축소 (st.title -> st.header)
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
            # 👇 [수정 2] 필터링 로직 복구
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
            
            # 👇 [수정 3] 처리 예정일, 처리 완료 맨 앞으로(index 0) 이동
            current_cols = list(filtered_df.columns)
            target_cols = ["처리 예정일", "처리 완료"]
            for col in target_cols:
                if col in current_cols: current_cols.remove(col)
            
            insert_idx = 0 # 가장 맨 앞으로 지정
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
        # 👇 [수정 4] 스크랩 발생 데이터 시각화 문구 삭제 (st.subheader 제거)
        df_analysis = get_data()
        
        if not df_analysis.empty:
            # 1. 데이터 전처리 (환산)
            df_analysis['발생량_kg'] = df_analysis.apply(
                lambda x: x['발생량'] * 200 if 'batch' in str(x['단위']).lower() else x['발생량'], axis=1
            )
            df_analysis['년월'] = pd.to_datetime(df_analysis['날짜']).dt.strftime('%Y-%m')

            # --- [그래프 1: 조별/월별 발생 추이] ---
            st.markdown("#### 📅 조별 및 월별 발생 트렌드")
            monthly_summary = df_analysis.groupby(['년월', '생산 조'])['발생량_kg'].sum().reset_index()
            
            fig_monthly = px.bar(
                monthly_summary, x='생산 조', y='발생량_kg', color='년월',
                barmode='group', text_auto='.1f',
                labels={'발생량_kg': '발생량 (kg)', '년월': '월별'},
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            
            fig_monthly.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=10, b=10, l=10, r=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                font=dict(family="Pretendard, sans-serif", size=13),
                hovermode="x unified"
            )
            fig_monthly.update_traces(marker_line_width=0, opacity=0.85)
            st.plotly_chart(fig_monthly, use_container_width=True)

            # 👇 [수정 5] 미완료 조별 건수를 그래프 바로 밑으로 이동
            st.markdown("#### ⚠️ 생산 조별 미완료(잔여) 항목 집계 (전체 기간)")
            uncompleted_df = df_analysis[df_analysis['처리 완료'] == False].copy()
            
            if not uncompleted_df.empty:
                uncomp_summary = uncompleted_df.groupby('생산 조').agg(
                    미완료건수=('생산 조', 'size'),
                    미완료중량_kg=('발생량_kg', 'sum')
                ).reset_index()
                
                uncomp_cols = st.columns(len(uncomp_summary))
                for idx, row in uncomp_summary.iterrows():
                    with uncomp_cols[idx]:
                        st.metric(label=f"[{row['생산 조']}] 미완료", 
                                  value=f"{row['미완료건수']} 건", 
                                  delta=f"{row['미완료중량_kg']:,.1f} kg",
                                  delta_color="inverse")
            else:
                st.success("✅ 모든 처리가 완료되었습니다!")

            st.markdown("---")

            # --- [섹션: 상세 분석 및 지표] ---
            col_a, col_b = st.columns([1, 2])
            
            with col_a:
                st.markdown("#### 🔍 특정 분석 기간 설정")
                start_date = st.date_input("시작일", datetime.now().replace(day=1))
                end_date = st.date_input("종료일", datetime.now())
                
                mask = (df_analysis['날짜'] >= start_date) & (df_analysis['날짜'] <= end_date)
                df_filtered = df_analysis.loc[mask].copy()

            with col_b:
                if not df_filtered.empty:
                    st.markdown(f"#### 🏆 {start_date} ~ {end_date} 요약")
                    total_kg = df_filtered['발생량_kg'].sum()
                    m_col1, m_col2 = st.columns(2)
                    m_col1.metric("선택 기간 총 발생량", f"{total_kg:,.1f} kg", delta="핵심 지표")
                    
                    # 선택 기간 내의 미완료 건수
                    uncomp_filtered = df_filtered[df_filtered['처리 완료'] == False]
                    m_col2.metric("선택 기간 내 미완료 건수", f"{len(uncomp_filtered)} 건", delta=f"{uncomp_filtered['발생량_kg'].sum():,.1f} kg", delta_color="inverse")

            if not df_filtered.empty:
                # --- [그래프 2: 원인별 분석] ---
                st.markdown("#### ⚠️ 선택 기간 원인별 스크랩 발생 비중")
                cause_summary = df_filtered.groupby('추정 원인')['발생량_kg'].sum().reset_index()
                
                fig_pie = px.pie(
                    cause_summary, values='발생량_kg', names='추정 원인',
                    hole=0.5,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(margin=dict(t=30, b=10, l=10, r=10))
                st.plotly_chart(fig_pie, use_container_width=True)

        else:
            st.info("데이터를 먼저 등록해 주세요.")