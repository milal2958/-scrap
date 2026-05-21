import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os
import plotly.express as px
import plotly.graph_objects as go
import hashlib
import time

# --- 1. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="정련Sub팀 스크랩 관리 시스템 v3.5", page_icon="⚙️", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
    
    /* 📱 모바일 환경 최적화 레이아웃 */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.5rem !important; 
            padding-right: 0.5rem !important;
            padding-top: 3.5rem !important; 
            padding-bottom: 1.5rem !important;
        }
        header[data-testid="stHeader"] {
            height: 3.0rem !important;
            background: transparent !important;
        }
        div[data-testid="stHorizontalBlock"] {
            padding-top: 0px !important;
        }
        h1, h2, h3 {
            font-size: 1.4rem !important;
            margin-top: 0rem !important; 
            margin-bottom: 1.0rem !important;
            line-height: 1.3 !important;
        }
        .metric-card {
            background-color: #ffffff !important;
            color: #333333 !important;
            border: 1.5px solid #e1e4e8 !important;
            box-shadow: 0 2px 5px rgba(0,0,0,0.15) !important;
            padding: 12px !important;
            border-radius: 6px !important;
            margin-bottom: 8px !important;
        }
    }
    
    .metric-card {
        background-color: #ffffff;
        color: #333333;
        padding: 12px;
        border-radius: 6px;
        border: 1px solid #e1e4e8;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

MAC_LIST = [f"A{i}" for i in range(1002, 1014)]


# --- 단방향 비밀번호 암호화 함수 ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# --- 2. 구글 시트 클라이언트 기본 연결 ---
@st.cache_resource
def connect_google_sheet_client():
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
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"구글 인증 서버 연결 오류: {e}")
        return None


# --- 3. 구글 시트 동적 연동 로그인 로직 ---
def login():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if not st.session_state["logged_in"]:
        st.subheader("⚙️ 정련Sub팀 시스템 로그인")
        
        login_container = st.container()
        with login_container.form("login_form"):
            user_id = st.text_input("아이디(ID)").strip()
            user_pw = st.text_input("비밀번호(PW)", type="password")
            
            btn_col, dev_col = st.columns([1, 1])
            with btn_col:
                submit_btn = st.form_submit_button("로그인")
            with dev_col:
                st.markdown(
                    "<div style='text-align: right; margin-top: 15px; color: #888888; font-size: 0.85rem; font-family: Pretendard, sans-serif;'>By In02</div>", 
                    unsafe_allow_html=True
                )
                
            if submit_btn:
                sheet_client = connect_google_sheet_client()
                if sheet_client:
                    try:
                        user_sheet = sheet_client.open("현장스크랩데이터").worksheet("사용자정보")
                        user_records = user_sheet.get_all_records()
                        
                        USER_CREDENTIALS = {}
                        for row in user_records:
                            k = str(row.get('사번', '')).split('.')[0].strip()
                            v = str(row.get('비밀번호', '')).strip()
                            if k:
                                USER_CREDENTIALS[k] = v
                        
                        if user_id in USER_CREDENTIALS and USER_CREDENTIALS[user_id] == hash_password(user_pw):
                            st.session_state["logged_in"], st.session_state["user_id"] = True, user_id
                            st.rerun()
                        else: 
                            st.error("❌ 아이디 또는 비밀번호가 틀렸습니다.")
                    except Exception as e:
                        st.error(f"⚠️ 사용자 정보 탭을 읽어오지 못했습니다. 시트명을 확인하세요: {e}")
                else:
                    st.error("❌ 구글 시트 데이터베이스 서버 연결 실패")
        return False
    return True


# --- 4. 데이터 로드 및 정제 ---
def get_data():
    client = connect_google_sheet_client()
    if client:
        try:
            sheet = client.open("현장스크랩데이터").sheet1
            all_values = sheet.get_all_values()
            if len(all_values) > 1:
                df = pd.DataFrame(all_values[1:], columns=all_values[0])
                df.columns = df.columns.str.strip() 
                
                df['__sheet_row_idx'] = df.index + 2
                
                if '날짜' in df.columns:
                    df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce').dt.date
                if '발생량' in df.columns:
                    df['발생량'] = pd.to_numeric(df['발생량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                if '처리 예정일' in df.columns:
                    df['처리 예정일'] = pd.to_datetime(df['처리 예정일'], errors='coerce').dt.date
                if '처리 완료' in df.columns:
                    df['처리 완료'] = df['처리 완료'].apply(lambda x: True if str(x).upper().strip() == 'TRUE' else False)
                return df
        except Exception as e:
            st.error(f"데이터 로드 중 오류 발생: {e}")
    return pd.DataFrame()


# --- 메인 실행 로직 ---
if login():
    st.sidebar.info(f"👷 접속자: **{st.session_state['user_id']}**님")
    
    with st.sidebar.expander("🔐 비밀번호 변경", expanded=False):
        with st.form("change_pw_form", clear_on_submit=True):
            current_pw = st.text_input("현재 비밀번호", type="password")
            new_pw = st.text_input("새 새로운 비밀번호", type="password")
            confirm_pw = st.text_input("새 비밀번호 확인", type="password")
            
            if st.form_submit_button("🔄 비밀번호 변경 확정"):
                if not current_pw or not new_pw or not confirm_pw:
                    st.error("⚠️ 모든 칸을 입력해주세요.")
                elif new_pw != confirm_pw:
                    st.error("❌ 새 비밀번호가 서로 일치하지 않습니다.")
                else:
                    client = connect_google_sheet_client()
                    if client:
                        try:
                            user_sheet = client.open("현장스크랩데이터").worksheet("사용자정보")
                            user_records = user_sheet.get_all_records()
                            
                            found_row_idx = None
                            is_current_pw_correct = False
                            
                            for idx, row in enumerate(user_records, start=2): 
                                clean_sheet_id = str(row.get('사번', '')).split('.')[0].strip()
                                if clean_sheet_id == str(st.session_state['user_id']):
                                    found_row_idx = idx
                                    if str(row.get('비밀번호', '')).strip() == hash_password(current_pw):
                                        is_current_pw_correct = True
                                    break
                            
                            if not is_current_pw_correct:
                                st.error("❌ 현재 비밀번호가 틀렸습니다.")
                            elif found_row_idx:
                                hashed_new = hash_password(new_pw)
                                user_sheet.update_cell(found_row_idx, 2, hashed_new)
                                st.success("🎉 비밀번호가 변경되었습니다!")
                                st.toast("🔐 비밀번호 변경 완료!", icon="✅")
                        except Exception as e:
                            st.error(f"⚠️ 시트 수정 중 오류 발생: {e}")
    
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
            with comp_col1: st.text_input("고정", value="C", disabled=True, key="fixed_c_input")
            with comp_col2: comp_choice = st.selectbox("구분", ["1", "2", "3", "4", "Q"])
            with comp_col3: comp_text = st.text_input("나머지 3글자 입력", max_chars=3, placeholder="예: R24").upper()
            final_comp_name = f"C{comp_choice}{comp_text}"

            cause_col, status_col = st.columns(2)
            with cause_col: 
                reg_cause = st.selectbox("추정 원인", ["리쿱영향", "롤러다이 영향", "혼합온도 상승", "설비이상", "트러블로 인한 설비정지", "원부재 영향", "기타"])
            with status_col: reg_status = st.selectbox("처리 판단", ["선별대기", "스크랩장 이동", "유관부서 판단 필요", "자체처리"])

            unit_col, amt_col = st.columns(2)
            with unit_col:
                u_type = st.radio("단위 선택", ["중량 (kg)", "수량 (batch)"], horizontal=True)
                u_str = "kg" if "중량" in u_type else "batch"
            with amt_col: reg_amt = st.number_input(f"발생량 ({u_str})", min_value=0.0, step=0.1)

            reg_loc = st.text_input("현재 보관 위치")
            reg_detail = st.text_area("발생상황 상세 설명")

            alert_container = st.container()

            if "reg_success_msg" in st.session_state:
                alert_container.success(st.session_state["reg_success_msg"])
            elif "reg_warning_msg" in st.session_state:
                alert_container.warning(st.session_state["reg_warning_msg"])

            if st.button("🚀 데이터 등록하기"):
                if len(comp_text) < 1 or reg_amt <= 0:
                    st.session_state["reg_warning_msg"] = "⚠️ Comp'd명과 발생량을 정확히 입력해주세요."
                    if "reg_success_msg" in st.session_state: del st.session_state["reg_success_msg"]
                    st.rerun()
                else:
                    current_submission = {
                        "date": str(reg_date),
                        "shift": reg_shift,
                        "mac": reg_mac,
                        "comp": final_comp_name,
                        "amt": reg_amt,
                        "unit": u_str
                    }
                    
                    if "last_submitted" in st.session_state and st.session_state["last_submitted"] == current_submission:
                        st.session_state["reg_warning_msg"] = "⚠️ 이미 등록된 데이터입니다. (실수로 두 번 클릭함 방지)"
                        st.rerun()
                    
                    client = connect_google_sheet_client()
                    if client:
                        sheet = client.open("현장스크랩데이터").sheet1
                        new_data = [str(reg_date), "", reg_shift, reg_mac, final_comp_name, reg_amt, u_str, reg_status, reg_cause, reg_loc, reg_detail, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state["user_id"], "", "FALSE"]
                        sheet.append_row(new_data)
                        
                        st.session_state["last_submitted"] = current_submission
                        st.session_state["reg_success_msg"] = f"✅ [{datetime.now().strftime('%H:%M:%S')}] 스크랩 발생 정보({final_comp_name}, {reg_amt}{u_str})가 정상 등록되었습니다!"
                        if "reg_warning_msg" in st.session_state: del st.session_state["reg_warning_msg"]
                        
                        st.cache_resource.clear()
                        if "raw_df" in st.session_state: del st.session_state["raw_df"]
                        st.rerun()

    # --- [TAB 2] 실시간 조회 ---
    with tab2:
        st.subheader("📋 실시간 현황 및 처리 내역")
        df = st.session_state["raw_df"] if "raw_df" in st.session_state else pd.DataFrame()
        
        if not df.empty:
            st.markdown("#### 📊 조별 처리 현황")
            
            df_stat = df.copy()
            df_stat['__wt_ton'] = df_stat.apply(
                lambda x: (float(x['발생량']) * 200) / 1000 if 'batch' in str(x['단위']).lower() else float(x['발생량']) / 1000, axis=1
            )
            
            stat_cols = st.columns(4)
            shifts_list = ["A조", "B조", "C조", "D조"]
            
            for i, shift_name in enumerate(shifts_list):
                with stat_cols[i]:
                    df_shift_stat = df_stat[df_stat['생산 조'] == shift_name]
                    
                    df_done = df_shift_stat[df_shift_stat['처리 완료'] == True]
                    done_count, done_weight = len(df_done), df_done['__wt_ton'].sum()
                    
                    df_plan = df_shift_stat[(df_shift_stat['처리 완료'] == False) & (df_shift_stat['처리 예정일'].notna())]
                    plan_count, plan_weight = len(df_plan), df_plan['__wt_ton'].sum()
                    
                    df_missing = df_shift_stat[(df_shift_stat['처리 완료'] == False) & (df_shift_stat['처리 예정일'].isna())]
                    missing_count, missing_weight = len(df_missing), df_missing['__wt_ton'].sum()
                    
                    with st.expander(f"**👷 {shift_name} 실적 현황**", expanded=True):
                        st.markdown(f"""
                        <div class="metric-card">
                            <span style='color:#0052CC; font-weight:bold;'>📅 처리대기:</span> {plan_count}건 / <b>{plan_weight:.1f} ton</b><br>
                            <span style='color:#7ED321; font-weight:bold;'>✅ 처리완료:</span> {done_count}건 / <b>{done_weight:.1f} ton</b><br>
                            <span style='color:#F5A623; font-weight:bold;'>⚠️ 미입력건:</span> {missing_count}건 / <b>{missing_weight:.1f} ton</b>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("---")
            st.write("🔍 **데이터 테이블 필터링**")
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                selected_shifts = st.multiselect("생산 조 필터", options=["전체", "A조", "B조", "C조", "D조"], default=["전체"])
            with f_col2:
                selected_macs = st.multiselect("발생 호기 필터", options=["전체"] + MAC_LIST, default=["전체"] + MAC_LIST)

            filtered_df = df.copy()
            if "전체" not in selected_shifts and selected_shifts:
                filtered_df = filtered_df[filtered_df['생산 조'].isin(selected_shifts)]
            if "전체" not in selected_macs and selected_macs:
                filtered_df = filtered_df[filtered_df['발생 호기'].isin(selected_macs)]

            all_cols = list(filtered_df.columns)
            display_order = ["처리 예정일", "처리 완료"] + [c for c in all_cols if c not in ["처리 예정일", "처리 완료", "__sheet_row_idx"]]
            
            try:
                edited_df = st.data_editor(
                    filtered_df,
                    column_order=display_order,
                    column_config={
                        "처리 예정일": st.column_config.DateColumn("📅 처리 예정일", format="YYYY-MM-DD"),
                        "처리 완료": st.column_config.CheckboxColumn("✅ 완료"),
                        "날짜": st.column_config.DateColumn("생산 일자", disabled=True),
                        "발생량": st.column_config.NumberColumn("발생량", disabled=True),
                        "추정 원인": st.column_config.SelectboxColumn("추정 원인", options=["리쿱영향", "롤러다이 영향", "혼합온도 상승", "설비이상", "트러블로 인한 설비정지", "원부재 영향", "기타"]),
                        "처리 판단": st.column_config.SelectboxColumn("처리 판단", options=["선별대기", "스크랩장 이동", "유관부서 판단 필요", "자체처리"])
                    },
                    hide_index=True,
                    use_container_width=True
                )

                if st.button("💾 변경사항 구글 시트에 저장하기"):
                    client = connect_google_sheet_client()
                    if client:
                        sheet = client.open("현장스크랩데이터").sheet1
                        with st.spinner("데이터 업데이트 중..."):
                            # 💡 버그 수정: row[0] 대신 데이터프레임 컬럼 목록에서 컬럼 맵을 안전하게 확보합니다.
                            headers = [str(c) for c in df.columns if c != '__sheet_row_idx']
                            col_map = {name: i+1 for i, name in enumerate(headers)}
                            
                            batch_cells = []
                            for _, row in edited_df.iterrows():
                                r_idx = int(row['__sheet_row_idx'])
                                p_date = row['처리 예정일']
                                p_date_str = p_date.strftime('%Y-%m-%d') if pd.notna(p_date) else ""
                                is_done_str = "TRUE" if row['처리 완료'] else "FALSE"
                                
                                if "처리 예정일" in col_map:
                                    batch_cells.append({'range': gspread.utils.rowcol_to_a1(r_idx, col_map['처리 예정일']), 'values': [[p_date_str]]})
                                if "처리 완료" in col_map:
                                    batch_cells.append({'range': gspread.utils.rowcol_to_a1(r_idx, col_map['처리 완료']), 'values': [[is_done_str]]})
                                if "추정 원인" in col_map:
                                    batch_cells.append({'range': gspread.utils.rowcol_to_a1(r_idx, col_map['추정 원인']), 'values': [[str(row['추정 원인'])]]})
                                if "처리 판단" in col_map:
                                    batch_cells.append({'range': gspread.utils.rowcol_to_a1(r_idx, col_map['처리 판단']), 'values': [[str(row['처리 판단'])]]})
                            
                            if batch_cells:
                                sheet.batch_update(batch_cells)
                            
                            st.toast("✅ 변경 내역이 안전하게 반영되었습니다!", icon="💾")
                            st.cache_resource.clear()
                            st.session_state["raw_df"] = get_data()
                            st.rerun()
            except Exception as e:
                st.error(f"데이터 에디터 로드 또는 저장 실패: {e}")
        else:
            st.info("데이터가 없습니다.")

    # --- [TAB 3] 발생 정밀분석 ---
    with tab3:
        df_analysis = st.session_state["raw_df"].copy() if "raw_df" in st.session_state else get_data()
        
        if not df_analysis.empty:
            df_analysis['발생량_ton'] = df_analysis.apply(
                lambda x: (x['발생량'] * 200) / 1000 if 'batch' in str(x['단위']).lower() else x['발생량'] / 1000, axis=1
            )
            df_analysis = df_analysis.dropna(subset=['날짜'])
            df_analysis['날짜_dt'] = pd.to_datetime(df_analysis['날짜'])
            df_analysis['년월'] = df_analysis['날짜_dt'].dt.strftime('%Y-%m')

            st.markdown("### 📅 분석 대상 기간 설정")
            ana_col1, ana_col2 = st.columns(2)
            with ana_col1:
                start_date = st.date_input("분석 시작일", df_analysis['날짜'].min() if len(df_analysis)>0 else datetime.now().replace(day=1), key="ana_start")
            with ana_col2:
                end_date = st.date_input("분석 종료일", datetime.now(), key="ana_end")

            mask = (df_analysis['날짜'] >= start_date) & (df_analysis['날짜'] <= end_date)
            df_filtered = df_analysis.loc[mask].copy()

            if not df_filtered.empty:
                st.markdown("---")
                st.markdown("### 📅 1. 조별 및 월별 발생 트렌드 분석")
                
                monthly_summary = df_filtered.groupby(['년월', '생산 조'])['발생량_ton'].sum().reset_index()
                monthly_summary = monthly_summary.sort_values(by=['년월', '생산 조'])
                monthly_summary['레이블'] = monthly_summary['발생량_ton'].round(1).astype(str) + " ton"

                is_mobile_view = len(monthly_summary['년월'].unique()) >= 3 or len(monthly_summary) >= 8

                if is_mobile_view:
                    fig_monthly = px.bar(monthly_summary, x='발생량_ton', y='생산 조', color='년월', barmode='group', text='레이블', orientation='h', labels={'발생량_ton': '발생량 (ton)'}, color_discrete_sequence=px.colors.qualitative.Set2)
                else:
                    fig_monthly = px.bar(monthly_summary, x='생산 조', y='발생량_ton', color='년월', barmode='group', text='레이블', labels={'발생량_ton': '발생량 (ton)'}, color_discrete_sequence=px.colors.qualitative.Set2)
                
                fig_monthly.update_traces(textposition='outside', textfont=dict(color='#0052CC', size=18, family='Pretendard, sans-serif', weight='bold'))
                max_val_trend = monthly_summary['발생량_ton'].max() if len(monthly_summary)>0 else 1
                
                margin_left_trend = 0 if is_mobile_view else 10
                fig_monthly.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=30, b=30, l=margin_left_trend, r=140), font=dict(family="Pretendard, sans-serif", size=14), hovermode="closest", legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5, title_text=""))
                
                if is_mobile_view:
                    fig_monthly.update_xaxes(title_text="", showgrid=False, showticklabels=False, ticks="", zeroline=False, range=[0, max_val_trend * 1.35])
                    fig_monthly.update_yaxes(showgrid=False, zeroline=False, tickfont=dict(size=18, family='Pretendard, sans-serif', weight='bold'))
                else:
                    fig_monthly.update_xaxes(showgrid=False, zeroline=False, tickfont=dict(size=18, family='Pretendard, sans-serif', weight='bold'))
                    fig_monthly.update_yaxes(title_text="", showgrid=False, showticklabels=False, ticks="", zeroline=False, range=[0, max_val_trend * 1.35])
                st.plotly_chart(fig_monthly, use_container_width=True, config={'displayModeBar': False})

                st.markdown("---")
                st.markdown("### 🔍 2. 추정 원인별 스크랩 발생량 현황")
                
                cause_summary = df_filtered.groupby('추정 원인')['발생량_ton'].sum().reset_index()
                cause_summary = cause_summary.sort_values(by='발생량_ton', ascending=True)
                cause_summary['레이블'] = cause_summary['발생량_ton'].round(1).astype(str) + " ton"

                fig_cause = px.bar(cause_summary, x='발생량_ton', y='추정 원인', orientation='h', text='레이블')
                fig_cause.update_traces(marker_color='#4A90E2', textposition='outside', textfont=dict(color='#0052CC', size=18, family='Pretendard, sans-serif', weight='bold'))
                max_val_cause = cause_summary['발생량_ton'].max() if len(cause_summary)>0 else 1
                
                fig_cause.update_layout(height=380, bargap=0.15, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=20, b=20, l=0, r=140), font=dict(family="Pretendard, sans-serif", size=14))
                fig_cause.update_xaxes(showgrid=False, showticklabels=False, ticks="", zeroline=False, range=[0, max_val_cause * 1.35])
                fig_cause.update_yaxes(showgrid=False, zeroline=False, tickfont=dict(size=18, family='Pretendard, sans-serif', weight='bold'))
                st.plotly_chart(fig_cause, use_container_width=True, config={'displayModeBar': False})

                st.markdown("---")
                st.markdown("### ⚙️ 3. 설비(호기)별 스크랩 발생 실적 현황")
                
                mac_summary = df_filtered.groupby('발생 호기')['발생량_ton'].sum().reset_index()
                mac_summary = mac_summary.sort_values(by='발생량_ton', ascending=False)
                mac_summary['레이블'] = mac_summary['발생량_ton'].round(1).astype(str) + " ton"

                fig_mac = px.bar(mac_summary, x='발생 호기', y='발생량_ton', text='레이블')
                fig_mac.update_traces(marker_color='#7ED321', textposition='outside', textfont=dict(color='#0052CC', size=16, family='Pretendard, sans-serif', weight='bold'))
                max_val_mac = mac_summary['발생량_ton'].max() if len(mac_summary)>0 else 1
                fig_mac.update_layout(height=450, bargap=0.2, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=40, b=30, l=10, r=10), font=dict(family="Pretendard, sans-serif", size=14))
                fig_mac.update_xaxes(showgrid=False, zeroline=False, tickfont=dict(size=16, family='Pretendard, sans-serif', weight='bold'))
                fig_mac.update_yaxes(showgrid=False, showticklabels=False, ticks="", zeroline=False, range=[0, max_val_mac * 1.3])
                st.plotly_chart(fig_mac, use_container_width=True, config={'displayModeBar': False})

                st.markdown("---")
                st.markdown("### 📋 4. 처리 판단별 스크랩 현황 분석")
                
                status_summary = df_filtered.groupby('처리 판단')['발생량_ton'].sum().reset_index()
                status_summary = status_summary.sort_values(by='발생량_ton', ascending=True)
                status_summary['레이블'] = status_summary['발생량_ton'].round(1).astype(str) + " ton"

                fig_status = px.bar(status_summary, x='발생량_ton', y='처리 판단', orientation='h', text='레이블')
                fig_status.update_traces(marker_color='#F5A623', textposition='outside', textfont=dict(color='#0052CC', size=18, family='Pretendard, sans-serif', weight='bold'))
                max_val_status = status_summary['발생량_ton'].max() if len(status_summary)>0 else 1
                
                fig_status.update_layout(height=350, bargap=0.15, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=20, b=20, l=0, r=140), font=dict(family="Pretendard, sans-serif", size=14))
                fig_status.update_xaxes(showgrid=False, showticklabels=False, ticks="", zeroline=False, range=[0, max_val_status * 1.35])
                fig_status.update_yaxes(showgrid=False, zeroline=False, tickfont=dict(size=18, family='Pretendard, sans-serif', weight='bold'))
                st.plotly_chart(fig_status, use_container_width=True, config={'displayModeBar': False})
            else:
                st.warning("⚠️ 선택한 기간에 해당하는 분석 데이터가 존재하지 않습니다.")
        else:
            st.info("데이터를 먼저 등록해 주세요.")