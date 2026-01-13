"""
UI Module
=========

This module implements the dashboard user interface for the CodeRunner Monitoring System.
It provides instructors with real-time insights into student submission patterns.
"""

from analytics.metrics import calculate_analytics
from dashboard.data_management import *
from analytics.pipeline import run_pedagogical_pipeline
from models.quiz_models import InterventionType, ProgressState

def format_timedelta(td):
    """Formats timedelta into readable strings."""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 24:
        return f"+{hours // 24} days"
    elif hours > 0:
        return f"+{hours}:{minutes:02}:{seconds:02}"
    elif minutes > 0:
        return f"+{minutes}:{seconds:02}"
    else:
        return f"+{seconds}s"

def render_sidebar():
    """
    Handles sidebar settings.
    """
    with st.sidebar:
        st.title("📊 CodeRunner Monitor")
        st.header("Settings")
        user = st.text_input("Moodle User", value=os.getenv("MOODLE_USER", ""))
        pw = st.text_input("Password", type="password", value=os.getenv("MOODLE_PASS", ""))
        qid = st.text_input("Quiz ID", value=os.getenv("MOODLE_QUIZ_ID", ""))

        st.divider()
        st.subheader("Data Management")

        col_load, col_reset = st.columns(2)

        with col_load:
            if st.button("📂 Load Cache", use_container_width=True):
                load_local_cache(qid)

        with col_reset:
            if st.button("🗑️ Reset"):
                st.session_state.confirm_reset = True
            if st.session_state.get('confirm_reset'):
                st.warning("Are you sure?")
                col_yes, col_no = st.columns(2)
                if col_yes.button("YES", width="stretch"):
                    status, message = reset_local_cache(qid)
                    if status:
                        st.info(message)
                    else:
                        st.error(message)
                    st.session_state.confirm_reset = False
                    # st.rerun()
                if col_no.button("No", width="stretch"):
                    st.session_state.confirm_reset = False
                    st.rerun()

        st.divider()
        st.subheader("Updates")
        enable_auto = st.checkbox("Enable Auto-sync", value=True)
        if enable_auto:
            sync_interval = st.slider("Sync interval (min)", min_value=1, max_value=10, value=5)
            st_autorefresh(interval=sync_interval * 60 * 1000, key="moodle_sync_timer")

        if st.button("🚀 Sync Now", width='stretch', type="primary"):
            st.session_state.raw_data = "loading"
            st.rerun()

    return user, pw, qid

def render_pedagogical_alerts(enriched_data):
    """Renders high-priority intervention alerts."""
    st.subheader("🚨 Priority Interventions")
    alert_cols = st.columns(4)
    alert_count = 0

    for student in enriched_data:
        for question in student.questions:
            if question.decision.intervention == InterventionType.INTERVENE_NOW:
                with alert_cols[alert_count % 4]:
                    st.error(f"**{student.username}**\n\n{question.decision.justification}")
                alert_count += 1

    if alert_count == 0:
        st.success("No critical logical interventions detected.")

def run_dashboard():
    """Main dashboard entry point."""
    # Ensure session state initialization
    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = None
    if 'last_sync' not in st.session_state:
        st.session_state.last_sync = "Never"

    username, password, quiz_id = render_sidebar()

    if st.session_state.raw_data == "loading":
        sync_with_moodle(username, password, quiz_id)

    if isinstance(st.session_state.raw_data, list) and st.session_state.raw_data:
        # Layered Analysis
        enriched_data = run_pedagogical_pipeline(st.session_state.raw_data)
        stats_df, _ = calculate_analytics(st.session_state.raw_data)

        # UI Components
        render_pedagogical_alerts(enriched_data)

        st.divider()
        st.subheader("Class Progress")
        matrix_df = stats_df.set_index("Student").filter(like="(%)")
        st.dataframe(matrix_df.style.background_gradient(cmap="RdYlGn"), width='stretch')

    else:
        st.info("Awaiting data. Please check credentials and Sync.")

if __name__ == "__main__":
    run_dashboard()