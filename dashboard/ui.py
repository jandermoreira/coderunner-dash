"""
UI Module
=========

This module implements the dashboard user interface for the CodeRunner Monitoring System.
It provides instructors with real-time insights into student submission patterns.
"""
from pprint import pprint

from analytics.metrics import calculate_analytics
from dashboard.data_management import *
from analytics.pipeline import run_pedagogical_pipeline
from models.quiz_models import InterventionType
from streamlit_extras.stylable_container import stylable_container
from streamlit_autorefresh import st_autorefresh


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
            st.session_state.sync_requested = True
            st.rerun()

        st.divider()
        st.subheader("Data Management")

        if not has_local_cache(qid):
            st.text("No local cache.")
        else:
            col_load, col_reset = st.columns(2)

            with col_load:
                if st.button("📂 Load Cache", use_container_width=True):
                    load_local_cache(qid)

            with col_reset:
                if has_local_cache(qid):
                    if st.button("🗑️ Reset"):
                        st.session_state.confirm_reset = True
                    if st.session_state.get('confirm_reset'):
                        st.warning("Are you sure?")
                        col_yes, col_no = st.columns(2)
                        if col_yes.button("YES", width="stretch"):
                            reset_local_cache(qid)
                            st.session_state.confirm_reset = False
                            st.rerun()
                        if col_no.button("No", width="stretch"):
                            st.session_state.confirm_reset = False
                            st.rerun()

    return user, pw, qid


INTERVENTION_STYLES = {
    InterventionType.INTERVENE_NOW: {
        "color": "#FF4B4B",
        "icon": "🚨",
        "title": "Need intervention",
        "bg_opacity": "40"
    },
    InterventionType.MONITOR: {
        "color": "#FFAA00",
        "icon": "⚠️",
        "title": "Under Observation",
        "bg_opacity": "40"
    },
    InterventionType.TECHNICAL: {
        "color": "#007BFF",
        "icon": "🔧",
        "title": "Technical Issues",
        "bg_opacity": "40"
    },
    InterventionType.NONE: {
        "color": "#28A745",
        "icon": "✅",
        "title": "Consistent Progress",
        "bg_opacity": "40"
    }
}


def render_intervention_section(enriched_data, intervention_type, title, st_method, empty_msg=None):
    """
    Generic renderer for different types of pedagogical interventions.
    """
    st.markdown(f"##### {title}")
    number_columns = 5
    cols = st.columns(number_columns)
    count = 0

    for student in sorted(enriched_data, key=lambda u: u.username.lower()):
        for question in student.questions:
            # Filtra pelo tipo de intervenção passado no parâmetro
            if question.decision.intervention == intervention_type:
                with cols[count % number_columns]:
                    style = INTERVENTION_STYLES.get(intervention_type)
                    with stylable_container(
                            key=f"container_{intervention_type}_{student.username}_{count}",
                            css_styles=f"""
                                {{
                                    border: 2px solid {style['color']};
                                    border-radius: 8px;
                                    padding: 15px;
                                    background-color: {style['color']}{style['bg_opacity']};
                                    margin-bottom: 10px;
                                }}
                            """,
                    ):
                        st.markdown(f"**{student.username}**")
                        st.text(question.decision.justification)
                count += 1

    if count == 0 and empty_msg:
        st.write(empty_msg)

    return count


def render_intervene_alerts(enriched_data):
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
    st.set_page_config(
        page_title="Coderunner dashboard",
        menu_items={
            'Get help': 'https://exemplo.com/ajuda',
            'Report a bug': 'https://exemplo.com/bug',
            'About': "# Sobre meu app\nAlgum texto aqui."
        },
        layout="wide"
    )

    # Ensure session state initialization
    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = None
    if 'last_sync' not in st.session_state:
        st.session_state.last_sync = "Never"
    if 'sync_requested' not in st.session_state:
        st.session_state.sync_requested = False

    username, password, quiz_id = render_sidebar()

    if st.session_state.get('sync_requested'):
        st.session_state.sync_requested = False
        sync_with_moodle(username, password, quiz_id)
        st.rerun()

    if isinstance(st.session_state.raw_data, list) and st.session_state.raw_data:
        # Layered Analysis
        enriched_data = run_pedagogical_pipeline(st.session_state.raw_data)
        stats_df, _ = calculate_analytics(st.session_state.raw_data)

        # UI Components
        intervention_items = [
            {
                "type": InterventionType.INTERVENE_NOW,
                "title": "🚨 Priority Interventions",
                "st_element": st.error,
                "empty_message": "No critical logical interventions detected."
            },
            {
                "type": InterventionType.TECHNICAL,
                "title": "🔧 Technical Issues",
                "st_element": st.info,
                "empty_message": "No techical issues"
            },
            {
                "type": InterventionType.MONITOR,
                "title": "⚠️ Students to Monitor",
                "st_element": st.warning,
                "empty_message": "No one currently require monitoring."
            },
            {
                "type": InterventionType.NONE,
                "title": "✅ Consistent Progress",
                "st_element": st.success,
                "empty_message": "No one is in consistent progress!"
            }
        ]
        for item in intervention_items:
            render_intervention_section(
                enriched_data,
                item["type"],
                item["title"],
                item["st_element"],
                item["empty_message"]
            )

        # st.divider()
        # st.subheader("Class Progress")
        # matrix_df = stats_df.set_index("Student").filter(like="(%)")
        # st.dataframe(matrix_df.style.background_gradient(cmap="RdYlGn"), width='stretch')

    else:
        st.info("Awaiting data. Please check credentials and Sync.")


if __name__ == "__main__":
    run_dashboard()
