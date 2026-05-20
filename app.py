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

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
    
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.5rem !important; 
            padding-right: 0.5rem !important;
            padding-top: 0.2rem !important;
            padding-bottom: 1rem !important;
        }
        header[data-testid="stHeader"] {
            height: 1.5rem !important;
            background: transparent !important;
        }
        div[data-testid="stHorizontalBlock"] {
            padding-top: 0px !important;
        }
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
                
                # 원본 유실 방지용 인덱스 생성
                df['__original_idx'] = df.index 
                
                if '날짜' in df.columns:
                    df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce').dt.date
                if '발생량' in df.columns:
                    df['발생량'] = pd.to_numeric(df['발생량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                
                # 데이터 에디터 호환용 datetime 날짜 형식 정제
                if '처리 예정일' in df.columns:
                    df['처리 예정일'] = pd.to_datetime(df['처리 예정일'], errors='coerce')
                    df['처리 예정일'] = df['처리 예정일'].where(df['처리 예정일'].notna(), None)
                    
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
        if "raw_df" in st.session_state:
            del st.session_state["raw_df"]
        st.rerun()

    st.header("⚙️ 정련Sub팀 스크랩 관리 시스템")
    
    if st.sidebar.button("🔄 데이터 최신화"):
        st.cache_resource.clear()
        if "raw_df" in st.session_state:
            del st.session_state["raw_df"]
        st.rerun()

    # 로그인이 성공한 시점에서만 안전하게 데이터베이스 세션을 할당
    if "raw_df" not in st.session_state:
        st.session_state["raw_df"] = get_data()

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

            msg_container = st.container()

            if st.button("🚀 데이터 등록하기"):
                if len(comp_text) < 1 or reg_amt <= 0:
                    msg_container.warning("⚠️ Comp'd명과 발생량을 확인해주세요.")
                else:
                    sheet = connect_google_sheet()
                    if sheet:
                        new_data = [str(reg_date), "", reg_shift, reg_mac, final_comp_name, reg_amt, u_str, reg_status, reg_cause, reg_loc, reg_detail, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state["user_id"], "", "FALSE"]
                        sheet.append_row(new_data)
                        
                        msg_container.success(f"✅ 스크랩 발생 정보가 정상 등록되었습니다!")
                        st.toast(f"✅ 등록 완료!", icon="🚀")
                        
                        st.cache_resource.clear()
                        if "raw_df" in st.session_state: del st.session_state["raw_df"]

    # --- [TAB 2] 실시간 조회 ---
    with tab2:
        st.subheader("📋 실시간 현황 및 처리 내역")
        
        if "raw_df" in st.session_state:
            df = st.session_state["raw_df"]
        else:
            df = pd.DataFrame()
        
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
            
            current_cols = [c for c in filtered_df.columns if c != '__original_idx']
            target_cols = ["처리 예정일", "처리 완료"]
            for col in target_cols:
                if col in current_cols: current_cols.remove(col)
            
            idx_pos = 0 
            for col in reversed(target_cols):
                if col in filtered_df.columns: current_cols.insert(idx_pos, col)
            
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
                        with st.spinner("데이터 업데이트 중..."):
                            for _, row in edited_df.iterrows():
                                orig_idx = row['__original_idx']
                                df.loc[orig_idx, '처리 예정일'] = row['처리 예정일']
                                df.loc[orig_idx, '처리 완료'] = row['처리 완료']
                                df.loc[orig_idx, '추정 원인'] = row['추정 원인']
                                df.loc[orig_idx, '처리 판단'] = row['처리 판단']
                            
                            save_df = df.drop(columns=['__original_idx']).copy()
                            save_df['처리 완료'] = save_df['처리 완료'].apply(lambda x: "TRUE" if x else "FALSE")
                            
                            if '처리 예정일' in save_df.columns:
                                save_df['처리 예정일'] = pd.to_datetime(save_df['처리 예정일'], errors='coerce').dt.strftime('%Y-%m-%d').fillna("")
                            if '요일' not in save_df.columns:
                                save_df.insert(1, '요일', "")
                                
                            update_vals = save_df.astype(str).values.tolist()
                            sheet.update(f'A2:O{len(update_vals)+1}', update_vals)
                            
                            st.toast("✅ 변경 내역이 안전하게 반영되었습니다!", icon="💾")
                            st.cache_resource.clear()
                            st.session_state["raw_df"] = get_data()
                            st.rerun()
            except Exception as e:
                st.error(f"데이터 에디터 로드 실패: {e}")
        else:
            st.info("데이터가 없습니다.")

    # --- [TAB 3] 발생 정밀분석 ---
    with tab3:
        if "raw_df" in st.session_state:
            df_analysis = st.session_state["raw_df"].copy()
        else:
            df_analysis = get_data()
        
        if not df_analysis.empty:
            # 🛠️ [패치] 모든 원본 kg 데이터를 1000으로 나누어 'ton' 단위 변수 기반으로 전면 전환
            df_analysis['발생량_ton'] = df_analysis.apply(
                lambda x: (x['발생량'] * 200) / 1000 if 'batch' in str(x['단위']).lower() else x['발생량'] / 1000, axis=1
            )
            df_analysis['날짜_dt'] = pd.to_datetime(df_analysis['날짜'])
            df_analysis['년월'] = df_analysis['날짜_dt'].dt.strftime('%Y-%m')

            # ==========================================
            # 1️⃣ [조별 및 월별 발생 트렌드]
            # ==========================================
            st.markdown("### 📅 1. 조별 및 월별 발생 트렌드 분석")
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                start_date_trend = st.date_input("트렌드 시작일", datetime.now().replace(day=1), key="trend_start")
            with date_col2:
                end_date_trend = st.date_input("트렌드 종료일", datetime.now(), key="trend_end")

            mask_trend = (df_analysis['날짜'] >= start_date_trend) & (df_analysis['날짜'] <= end_date_trend)
            df_trend_filtered = df_analysis.loc[mask_trend].copy()

            if not df_trend_filtered.empty:
                # 🛠️ 수치 변수를 발생량_ton으로 연산
                monthly_summary = df_trend_filtered.groupby(['년월', '생산 조'])['발생량_ton'].sum().reset_index()
                monthly_summary = monthly_summary.sort_values(by=['년월', '생산 조'])

                is_mobile_view = len(monthly_summary['년월'].unique()) >= 3 or len(monthly_summary) >= 8

                if is_mobile_view:
                    fig_monthly = px.bar(
                        monthly_summary, 
                        x='발생량_ton', 
                        y='생산 조', 
                        color='년월',
                        barmode='group', 
                        text_auto='.1f', # 소수점 첫째 자리 포맷
                        orientation='h',
                        labels={'발생량_ton': '발생량 (ton)', '년월': '월별', '생산 조': '생산 조'},
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                else:
                    fig_monthly = px.bar(
                        monthly_summary, 
                        x='생산 조', 
                        y='발생량_ton', 
                        color='년월',
                        barmode='group', 
                        text_auto='.1f',
                        labels={'발생량_ton': '발생량 (ton)', '년월': '월별'},
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                
                # 🛠️ 뒤에 ' ton' 텍스트 강제 추가 결합 및 글씨 세팅
                fig_monthly.update_traces(
                    texttemplate='%{text} ton',
                    textposition='outside',
                    textfont=dict(color='#0052CC', size=18, family='Pretendard, Malgun Gothic, sans-serif', weight='bold')
                )
                
                max_val_trend = monthly_summary['발생량_ton'].max()
                fig_monthly.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=30, b=30, l=10, r=120), 
                    legend=dict(
                        orientation="h", 
                        yanchor="top", 
                        y=-0.18, 
                        xanchor="center", 
                        x=0.5,
                        title_text="",
                        font=dict(size=14, family='Pretendard, Malgun Gothic, sans-serif')
                    ),
                    font=dict(family="Pretendard, sans-serif", size=14),
                    hovermode="closest"
                )
                
                if is_mobile_view:
                    fig_monthly.update_xaxes(title_text="", showgrid=False, showticklabels=False, ticks="", zeroline=False, range=[0, max_val_trend * 1.3])
                    fig_monthly.update_yaxes(showgrid=False, zeroline=False, tickfont=dict(size=18, family='Pretendard, Malgun Gothic, sans-serif', weight='bold'))
                else:
                    fig_monthly.update_xaxes(showgrid=False, zeroline=False, tickfont=dict(size=18, family='Pretendard, Malgun Gothic, sans-serif', weight='bold'))
                    fig_monthly.update_yaxes(title_text="", showgrid=False, showticklabels=False, ticks="", zeroline=False, range=[0, max_val_trend * 1.3])
                
                st.plotly_chart(fig_monthly, use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("⚠️ 선택한 기간에 해당하는 트렌드 데이터가 없습니다.")

            st.markdown("---")

            # ==========================================
            # 2️⃣ [추정 원인별 발생량 분석]
            # ==========================================
            st.markdown("### 🔍 2. 추정 원인별 스크랩 발생량 현황")
            
            date_col3, date_col4 = st.columns(2)
            with date_col3:
                start_date_cause = st.date_input("원인분석 시작일", datetime.now().replace(day=1), key="cause_start")
            with date_col4:
                end_date_cause = st.date_input("원인분석 종료일", datetime.now(), key="cause_end")

            mask_cause = (df_analysis['날짜'] >= start_date_cause) & (df_analysis['날짜'] <= end_date_cause)
            df_cause_filtered = df_analysis.loc[mask_cause].copy()

            if not df_cause_filtered.empty:
                # 🛠️ 수치 변수를 발생량_ton으로 연산
                cause_summary = df_cause_filtered.groupby('추정 원인')['발생량_ton'].sum().reset_index()
                cause_summary = cause_summary.sort_values(by='발생량_ton', ascending=True)

                fig_cause = px.bar(
                    cause_summary,
                    x='발생량_ton',
                    y='추정 원인',
                    orientation='h',
                    text_auto='.1f',
                    labels={'발생량_ton': '발생량 (ton)', '추정 원인': '추정 원인'}
                )

                # 🛠️ 뒤에 ' ton' 결합 패치
                fig_cause.update_traces(
                    marker_color='#4A90E2', 
                    texttemplate='%{text} ton',
                    textposition='outside',
                    textfont=dict(color='#0052CC', size=18, family='Pretendard, Malgun Gothic, sans-serif', weight='bold')
                )

                max_val_cause = cause_summary['발생량_ton'].max()
                fig_cause.update_layout(
                    height=380, 
                    bargap=0.15, 
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=20, b=20, l=10, r=130), 
                    font=dict(family="Pretendard, Malgun Gothic, sans-serif", size=14),
                    hovermode="closest"
                )

                fig_cause.update_xaxes(
                    title_text="", 
                    showgrid=False, 
                    showticklabels=False, 
                    ticks="", 
                    zeroline=False,
                    range=[0, max_val_cause * 1.25]
                )
                fig_cause.update_yaxes(
                    showgrid=False, 
                    zeroline=False,
                    tickfont=dict(size=18, family='Pretendard, Malgun Gothic, sans-serif', weight='bold')
                )

                st.plotly_chart(fig_cause, use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("⚠️ 선택한 기간에 해당하는 원인 데이터가 없습니다.")

            st.markdown("---")

            # ==========================================
            # 3️⃣ [신규 추가: 설비별 발생 실적 분석]
            # ==========================================
            st.markdown("### ⚙️ 3. 설비(호기)별 스크랩 발생 실적 현황")
            
            date_col5, date_col6 = st.columns(2)
            with date_col5:
                start_date_mac = st.date_input("설비분석 시작일", datetime.now().replace(day=1), key="mac_start")
            with date_col6:
                end_date_mac = st.date_input("설비분석 종료일", datetime.now(), key="mac_end")

            mask_mac = (df_analysis['날짜'] >= start_date_mac) & (df_analysis['날짜'] <= end_date_mac)
            df_mac_filtered = df_analysis.loc[mask_mac].copy()

            if not df_mac_filtered.empty:
                # 설비(발생 호기)별 발생 실적 집계 및 정렬
                mac_summary = df_mac_filtered.groupby('발생 호기')['발생량_ton'].sum().reset_index()
                mac_summary = mac_summary.sort_values(by='발생량_ton', ascending=True)

                fig_mac = px.bar(
                    mac_summary,
                    x='발생량_ton',
                    y='발생 호기',
                    orientation='h',
                    text_auto='.1f',
                    labels={'발생량_ton': '발생량 (ton)', '발생 호기': '설비 호기'}
                )

                # 파란색 수치 및 뒤에 ' ton' 결합 패치
                fig_mac.update_traces(
                    marker_color='#7ED321', # 설비 차트 구분용 깔끔한 그린/연두 계열
                    texttemplate='%{text} ton',
                    textposition='outside',
                    textfont=dict(color='#0052CC', size=18, family='Pretendard, Malgun Gothic, sans-serif', weight='bold')
                )

                max_val_mac = mac_summary['발생량_ton'].max()
                fig_mac.update_layout(
                    height=450, # 설비 항목수가 많으므로(12개 호기) 높이를 조금 더 확보
                    bargap=0.15, 
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=20, b=20, l=10, r=130), 
                    font=dict(family="Pretendard, Malgun Gothic, sans-serif", size=14),
                    hovermode="closest"
                )

                fig_mac.update_xaxes(
                    title_text="", 
                    showgrid=False, 
                    showticklabels=False, 
                    ticks="", 
                    zeroline=False,
                    range=[0, max_val_mac * 1.25]
                )
                fig_mac.update_yaxes(
                    showgrid=False, 
                    zeroline=False,
                    tickfont=dict(size=18, family='Pretendard, Malgun Gothic, sans-serif', weight='bold')
                )

                st.plotly_chart(fig_mac, use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("⚠️ 선택한 기간에 해당하는 설비 실적 데이터가 없습니다.")

        else:
            st.info("데이터를 먼저 등록해 주세요.")