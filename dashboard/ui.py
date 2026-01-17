"""
UI Module
=========

This module implements the dashboard user interface for the CodeRunner Monitoring System.
It provides instructors with real-time insights into student submission patterns.
"""
from datetime import datetime
from pprint import pprint

from analytics.metrics import calculate_analytics
from dashboard.data_management import *
from analytics.pipeline import run_pedagogical_pipeline
from models.quiz_models import InterventionType, StrategyProfile
from streamlit_extras.stylable_container import stylable_container
from streamlit_autorefresh import st_autorefresh

from collections import Counter
import streamlit as st


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


# def render_top_indicators(data):
#     indicators = {
#         "Students": len(data),
#         "Questions": len(data[0].questions),
#     }
#
#     intervene_now = sum([
#         int(len([
#             question.decision.intervention
#             for question in student.questions
#             if question.decision.intervention == InterventionType.INTERVENE_NOW
#         ]) > 0) for student in data
#     ])
#     if intervene_now > 0:
#         indicators[f"Intervene  ({intervene_now / len(data) * 100:.1f}%)"] = f"🚨 {intervene_now}"
#
#     technical = sum([
#         int(len([
#             question.decision.intervention
#             for question in student.questions
#             if question.decision.intervention == InterventionType.TECHNICAL
#         ]) > 0) for student in data
#     ])
#     if technical > 0:
#         indicators[f"Technical  ({technical / len(data) * 100:.1f}%)"] = f"🔧 {technical}"
#
#     cols = st.columns(len(indicators))
#     for idx, (title, value) in enumerate(indicators.items()):
#         with cols[idx]:
#             st.metric(title, value)


def render_top_indicators(data):
    """
    Renders pedagogical metrics dynamically.
    Columns are only created for issues that actually exist (count > 0).
    """
    if not data:
        return

    # --- 1. DATA AGGREGATION ---
    total_students = len(data)
    total_questions = len(data[0].questions) if total_students > 0 else 0

    # We count unique students affected by each intervention type
    tech_student_count = 0
    logic_student_count = 0
    finished_student_count = 0
    problem_spots = Counter()

    for student in data:
        if student.quiz_end_timestamp:
            finished_student_count += 1

        has_tech_issue = False
        has_logic_issue = False

        for idx, q in enumerate(student.questions):
            # Check for Technical Issues
            if q.decision.intervention == InterventionType.TECHNICAL:
                has_tech_issue = True
                problem_spots[f"Q{idx + 1}"] += 1

            # Check for Logical Blocks (Intervene Now)
            if q.decision.intervention == InterventionType.INTERVENE_NOW:
                has_logic_issue = True
                problem_spots[f"Q{idx + 1}"] += 1

        if has_tech_issue:
            tech_student_count += 1
        if has_logic_issue:
            logic_student_count += 1

    # --- 2. DEFINE ACTIVE METRICS ---
    # We always show the general context
    active_metrics = [
        {
            "label": "Quiz Overview",
            "value": f"{total_students} Students",
            "delta": f"{total_questions} Questions",
            "color": "normal"
        }
    ]

    # Add Technical column only if there are issues
    if tech_student_count > 0:
        active_metrics.append({
            "label": "Technical Issues",
            "value": tech_student_count,
            "delta": "Language/coding",
            "color": "inverse"
        })

    # Add Pedagogical column only if there are alerts
    if logic_student_count > 0:
        active_metrics.append({
            "label": "Pedagogical Alerts",
            "value": logic_student_count,
            "delta": "Logical/Plateau",
            "color": "inverse"
        })

    # Add Hotspot column only if there's a specific question causing problems
    if problem_spots:
        hotspot_q, _ = problem_spots.most_common(1)[0]
        active_metrics.append({
            "label": "Critical Hotspot",
            "value": hotspot_q,
            "delta": "Highest friction",
            "color": "off"
        })

    if finished_student_count > 0:
        if finished_student_count == total_students:
            finished_value = "100%"
        else:
            percentage_finished = round(finished_student_count/total_students * 100, 0)
            if percentage_finished > 60:
                finished_value = f"{finished_student_count} ({percentage_finished}%)"
            else:
                finished_value = finished_student_count
        active_metrics.append({
                    "label": "Finished",
                    "value": finished_value,
                    "delta": "Give some attention",
                    "color": "off"
                })

    # --- 3. DYNAMIC RENDERING ---
    # The number of columns is equal to the number of active issues + context
    if active_metrics:
        cols = st.columns(len(active_metrics))
        for i, metric in enumerate(active_metrics):
            with cols[i]:
                st.metric(
                    label=metric["label"],
                    value=metric["value"],
                    delta=metric["delta"],
                    delta_color=metric["color"],
                    delta_arrow="off"
                )

def render_sidebar():
    """
    Handles sidebar settings.
    """
    with st.sidebar:
        st.title("📊 CodeRunner Monitor")
        # st.header("Settings")
        user = st.text_input("Moodle User", value=os.getenv("MOODLE_USER", ""))
        pw = st.text_input("Password", type="password", value=os.getenv("MOODLE_PASS", ""))
        qid = st.text_input("Quiz ID", value=os.getenv("MOODLE_QUIZ_ID", ""))
        if has_local_cache(qid):
            if st.button("📂 Load cache", use_container_width=True):
                loaded_cache = load_local_cache(qid)
                if loaded_cache:
                    loaded_data, loaded_steps_urls = loaded_cache
                    st.session_state.raw_data = loaded_data
                    st.session_state.steps_urls = loaded_steps_urls
                    st.session_state.last_sync = "From cache"
                    st.info("Cache loaded.")
                else:
                    st.error("Cache file not found.")

            if has_local_cache(qid):
                if st.button("🗑️ Delete cache", use_container_width=True):
                    st.session_state.confirm_deletion = True
                if st.session_state.get('confirm_deletion'):
                    st.warning("Are you sure?")
                    col_yes, col_no = st.columns(2)
                    if col_yes.button("YES", width="stretch"):
                        reset_local_cache(qid)
                        st.session_state.confirm_deletion = False
                        st.session_state.raw_data = None
                        st.session_state.steps_urls = set()
                        st.rerun()
                    if col_no.button("No", width="stretch"):
                        st.session_state.confirm_deletion = False
                        st.rerun()

        st.divider()
        # st.subheader("Updates")
        enable_auto = st.checkbox("Enable Auto-sync", value=True)
        st.session_state.enable_auto_sync = enable_auto
        if enable_auto:
            sync_interval = st.slider("Sync interval (min)", min_value=1, max_value=10, value=5)
            st.session_state.sync_interval = sync_interval

            refresh_count = st_autorefresh(
                interval=sync_interval * 60 * 1000,
                key="moodle_sync_timer"
            )
            st.session_state.refresh_count = refresh_count

        if st.button("🚀 Sync Now", width='stretch', type="primary"):
            st.session_state.sync_requested = True
            st.rerun()

        if st.button("rerun()"):
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

st.markdown("""
    <style>
    [data-testid="column"] {
        height: 200vh;
    }
    .full {
        height: 100%;
    }
    </style>
""", unsafe_allow_html=True)

box_count = 0


def render_box(markdown):
    """Renders a box with a text"""
    global box_count
    with stylable_container(
            key=f"box_{box_count}",
            css_styles="""
                {
                    # border: 2px solid #467646;
                    border-radius: 8px;
                    padding: 10px;
                    background-color: #46764666;
                    margin-bottom: 10px;
                }
            """,
    ):
        st.markdown(markdown)
        st.text("")
    box_count += 1


def render_intervention_section(enriched_data, intervention_type, title, st_method, empty_msg=None):
    """
    Generic renderer for different types of pedagogical interventions.
    """
    # st.markdown(f"##### {title}")

    count = 0
    number_columns = 5
    style = INTERVENTION_STYLES.get(intervention_type)

    cols = st.columns(number_columns)
    for student in sorted(enriched_data, key=lambda u: u.username.lower()):
        questions_in_type = [(idx, question) for idx, question in enumerate(student.questions)
                             if question.decision.intervention == intervention_type]
        if questions_in_type:
            if count % number_columns == 0:
                cols = st.columns(number_columns)
            with cols[count % number_columns]:
                with stylable_container(
                        key=f"container_{intervention_type}_{student.username}_{count}",
                        css_styles=f"""
                            {{
                                border: 2px solid {style['color']};
                                border-radius: 8px;
                                padding: 10px;
                                background-color: {style['color']}{style['bg_opacity']};
                                margin-bottom: 10px;
                            }}
                        """,
                ):
                    st.markdown(f"**{student.username}**")
                    for idx, question in questions_in_type:
                        st.markdown(f"**{idx + 1}**: {question.decision.justification}")
                    if student.quiz_end_timestamp:
                        render_box(f"🏁 Finished {student.quiz_end_timestamp}")
                count += 1

    # if count == 0 and empty_msg:
    #     st.write(empty_msg)

    return count


# def render_intervene_alerts(enriched_data):
#     """Renders high-priority intervention alerts."""
#     st.subheader("🚨 Priority Interventions")
#     alert_cols = st.columns(4)
#     alert_count = 0
#
#     for student in enriched_data:
#         for question in student.questions:
#             if question.decision.intervention == InterventionType.INTERVENE_NOW:
#                 with alert_cols[alert_count % 4]:
#                     st.error(f"**{student.username}**\n\n{question.decision.justification}")
#                 alert_count += 1
#
#     if alert_count == 0:
#         st.success("No critical logical interventions detected.")


def run_dashboard():
    """Main dashboard entry point."""
    st.set_page_config(
        page_title="Coderunner dashboard",
        layout="wide"
    )

    # Ensure session state initialization
    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = None
    if 'steps_urls' not in st.session_state:
        st.session_state.steps_urls = set()
    if 'last_sync' not in st.session_state:
        st.session_state.last_sync = "N/A"
    if 'sync_requested' not in st.session_state:
        st.session_state.sync_requested = False
    if 'refresh_count' not in st.session_state:
        st.session_state.refresh_count = 0
    if 'last_refresh_count' not in st.session_state:
        st.session_state.last_refresh_count = 0
    if 'enable_auto_sync' not in st.session_state:
        st.session_state.enable_auto_sync = True
    if 'sync_interval' not in st.session_state:
        st.session_state.sync_interval = None
    if 'last_sync_interval' not in st.session_state:
        st.session_state.last_sync_interval = None

    username, password, quiz_id = render_sidebar()

    # Auto-sync on refresh
    if st.session_state.enable_auto_sync:
        interval_changed = st.session_state.sync_interval != st.session_state.last_sync_interval
        st.session_state.last_sync_interval = st.session_state.sync_interval

        if (not interval_changed
                and st.session_state.refresh_count != st.session_state.last_refresh_count):
            st.session_state.last_refresh_count = st.session_state.refresh_count
            sync_with_moodle(username, password, quiz_id)
            st.session_state.last_sync = datetime.now().strftime("%d/%m/%Y %H:%M")
            st.rerun()

    if st.session_state.get('sync_requested'):
        st.session_state.sync_requested = False
        sync_with_moodle(username, password, quiz_id)
        st.session_state.last_sync = datetime.now().strftime("%d/%m/%Y %H:%M")
        st.rerun()

    if isinstance(st.session_state.raw_data, list) and st.session_state.raw_data:
        # Layered Analysis
        enriched_data = run_pedagogical_pipeline(st.session_state.raw_data)
        stats_df, _ = calculate_analytics(st.session_state.raw_data)

        render_top_indicators(enriched_data)

        # UI Components
        intervention_items = [
            {
                "type": InterventionType.INTERVENE_NOW,
                "title": "🚨 Interventions",
                "st_element": st.error,
                "empty_message": "No critical logical interventions detected."
            },
            {
                "type": InterventionType.TECHNICAL,
                "title": "🔧 Technical issues",
                "st_element": st.info,
                "empty_message": "No technical issues"
            },
            {
                "type": InterventionType.MONITOR,
                "title": "⚠️ Under monitoring",
                "st_element": st.warning,
                "empty_message": "No one currently require monitoring."
            },
            {
                "type": InterventionType.NONE,
                "title": "✅ Consistent progress",
                "st_element": st.success,
                "empty_message": "No one is in consistent progress!"
            }
        ]
        with st.container(height=700):
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
