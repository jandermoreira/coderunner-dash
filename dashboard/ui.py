"""
UI
==

This module implements the dashboard UI.
"""

from dashboard.data_management import *


def format_timedelta(td):
    """Formats timedelta into readable strings: +2s, +1:02, +2:07:03, +2 days"""
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


def lock_page_scroll():
    """Forces the main Streamlit window to be non-scrollable."""
    st.markdown(
        """
        <style>
            /* Alvos específicos do layout interno do Streamlit */
            [data-testid="stAppViewContainer"], 
            [data-testid="stMainViewContainer"], 
            .main {
                overflow: hidden !important;
                height: 100vh;
            }

            /* Ajusta o padding do conteúdo principal */
            [data-testid="stAppViewBlockContainer"] {
                padding-top: 2rem !important;
                padding-bottom: 0rem !important;
                height: 100vh;
            }
        </style>
        """,
        unsafe_allow_html=True
    )


def render_top_indicators(stats_df):
    """Renders top indicators."""
    with st.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("Students", len(stats_df))
        c2.metric("Avg Progress", f"{stats_df.filter(like='(%)').mean().mean():.1f}%")
        c3.metric("Last Sync", st.session_state.last_sync)
        # st.divider()


def render_sidebar():
    with st.sidebar:
        st.title("📊 CodeRunner Monitoring System")
        st.header("Settings")
        user = st.text_input("Moodle User", value=os.getenv("MOODLE_USER", ""))
        pw = st.text_input("Password", type="password", value=os.getenv("MOODLE_PASS", ""))
        qid = st.text_input("Quiz ID", value=os.getenv("MOODLE_QUIZ_ID", "958257"))

        st.divider()
        st.subheader("Data Management")
        if st.button("📂 Load Last Sync"):
            load_local_cache()

        with st.expander("⚠️ Danger Zone"):
            st.write("Resetting history will delete all snapshots for this Quiz ID.")
            if st.button("🗑️ Reset History"):
                st.session_state.confirm_reset = True

            if st.session_state.get('confirm_reset'):
                st.warning("Are you sure?")
                col_yes, col_no = st.columns(2)
                if col_yes.button("Yes, delete"):
                    reset_history(qid)
                    st.session_state.confirm_reset = False
                    st.rerun()
                if col_no.button("Cancel"):
                    st.session_state.confirm_reset = False
                    st.rerun()

        st.divider()
        st.subheader("Update Settings")
        enable_auto_sync = st.checkbox("Enable Auto-sync", value=True)
        interval = st.slider("Interval (minutes)", 2, 10, 5, disabled=not enable_auto_sync)

        if enable_auto_sync:
            refresh_count = st_autorefresh(interval=interval * 60 * 1000, key="moodle_auto_sync")
            if refresh_count > st.session_state.last_auto_refresh:
                st.session_state.last_auto_refresh = refresh_count
                st.session_state.raw_data = "loading"

        if st.button("🚀 Sync Now"):
            st.session_state.raw_data = "loading"
            st.rerun()

    return user, pw, qid


def render_student_evolution(quiz_id, student_name):
    """Renders temporal evolution with a white circle marker for the quiz start time."""
    history_path = get_history_path(quiz_id)
    if not os.path.exists(history_path):
        st.info("No history available.")
        return

    with open(history_path, "rb") as f:
        history = pickle.load(f)

    if not history or not history[0]["data"]:
        return

    # 1. Identify the student's actual start time (quiz_start_date)
    # Search history for the first occurrence of this student with a valid start date
    student_ref = next((s for snap in history for s in snap["data"] if s.username == student_name),
                       None)

    # Fallback to the first snapshot timestamp if parser didn't find the start date
    reference_start_time = (student_ref.quiz_start_date
                            if student_ref and student_ref.quiz_start_date
                            else history[0]["timestamp"])

    student_records = []
    for snap in history:
        student_data = next((s for s in snap["data"] if s.username == student_name), None)
        if student_data:
            student_records.append({
                "timestamp": snap["timestamp"],
                "questions": student_data.questions
            })

    if not student_records:
        return

    num_questions = len(student_records[0]["questions"])

    for q_idx in range(num_questions):
        plot_data = []

        prev_time = reference_start_time

        for record in student_records:
            curr_time = record["timestamp"]
            q_data = record["questions"][q_idx]

            since_start = format_timedelta(curr_time - reference_start_time)
            since_prev = format_timedelta(curr_time - prev_time) if prev_time else "Init"
            axis_label = f"{since_start} / {since_prev}"

            for t_idx, _ in enumerate(q_data.test_results):
                plot_data.append({
                    "Time": reference_start_time,
                    "LapseLabel": reference_start_time.strftime("%d/%m/%Y<br>%H:%M"),
                    "Test Case": f"Test {t_idx + 1}",
                    "Status": "Opened"
                })

            for t_idx, test in enumerate(q_data.test_results):
                plot_data.append({
                    "Time": curr_time,
                    "LapseLabel": axis_label,
                    "Test Case": f"Test {t_idx + 1}",
                    "Status": "Passed" if test.passed else "Failed"
                })
            prev_time = curr_time

        if plot_data:
            with (st.expander(f"📈 Temporal evolution - Question {q_idx + 1}", expanded=False)):
                df_plot = pd.DataFrame(plot_data)

                # Sorting order: "Quiz Start" always comes first (bottom or top depending on scale)["Quiz Start"] +
                test_order = sorted(
                    [t for t in df_plot["Test Case"].unique() if "Test" in t],
                    key=lambda x: int(x.split()[-1])
                )

                fig = px.scatter(
                    df_plot,
                    x="Time",
                    y="Test Case",
                    color="Status",
                    # 3. White color for "Opened" status
                    color_discrete_map={
                        "Passed": "#2ca02c",
                        "Failed": "#d62728",
                        "Opened": "#ffffff"
                    },
                    symbol="Status",
                    category_orders={"Test Case": test_order}
                )

                # Ensure white points have a thin border to be visible on light backgrounds
                fig.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')))

                unique_points = df_plot.drop_duplicates("Time")
                fig.update_layout(
                    xaxis=dict(
                        title=None,
                        tickmode='array',
                        tickvals=unique_points["Time"],
                        ticktext=unique_points["LapseLabel"],
                        tickangle=-75,
                        showgrid=True
                    ),
                    yaxis={'type': 'category'},
                    height=180 + (len(test_order) * 15),
                    margin=dict(l=10, r=10, t=10, b=100),
                    showlegend=False
                )

                st.plotly_chart(fig, width="stretch", key=f"plot_q_{student_name}_{q_idx}")


def render_student(quiz_id, student_list, stats_df):
    for student in student_list:
        with st.expander(f"{student}", expanded=True):
            student_stats = stats_df[stats_df["Student"] == student]

            # Alert box
            alerts = {}

            total_regressions = int(student_stats.filter(like="Regressions").sum(axis=1).values[0])
            if total_regressions > 0:
                alerts["Regressions"] = total_regressions

            tinkering_columns = student_stats.filter(like="has_tinkering")
            is_tinkering = tinkering_columns.any(axis=1).iloc[0]
            if is_tinkering:
                alerts["Trial and error"] = "Alert"

            if len(alerts) > 0:
                column1, column2 = st.columns([3, 1])
                with column1:
                    render_student_evolution(quiz_id, student)

                with column2:
                    for title, value in alerts.items():
                        st.metric(title, value)
            else:
                render_student_evolution(quiz_id, student)


def render_detailed_test_grid(raw_data):
    st.divider()
    st.header("🔍 Current Status: All Students")
    num_questions = len(raw_data[0].questions)

    for i in range(num_questions):
        with st.expander(f"Question {i + 1} Status", expanded=True):
            results_map = {}
            max_test_count = max(len(s.questions[i].test_results) for s in raw_data)
            for student in raw_data:
                q_data = student.questions[i]
                results_map[student.username] = [
                    ("🟢" if q_data.test_results[idx].passed else "🔴")
                    if idx < len(q_data.test_results) else "⚪"
                    for idx in range(max_test_count)
                ]
            st.dataframe(
                pd.DataFrame(results_map).rename(index=lambda x: f"Test {x + 1}"),
                width="stretch"
            )


def initialize_session_state():
    """Initializes page config and session variables."""
    st.set_page_config(page_title="CodeRunner Dash", layout="wide")

    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = None
    if 'last_sync' not in st.session_state:
        st.session_state.last_sync = None
    if 'last_auto_refresh' not in st.session_state:
        st.session_state.last_auto_refresh = 0


def run_dashboard():
    initialize_session_state()
    lock_page_scroll()

    username, password, quiz_id = render_sidebar()

    if st.session_state.raw_data == "loading":
        sync_with_moodle(username, password, quiz_id)

    if isinstance(st.session_state.raw_data, list) and st.session_state.raw_data:
        history_path = get_history_path(quiz_id)
        history_data = None
        if os.path.exists(history_path):
            with open(history_path, "rb") as f:
                history_data = pickle.load(f)

        stats_df, common_errors = calculate_analytics(st.session_state.raw_data,
                                                      history=history_data)

        # if not common_errors.empty:
        #     st.subheader("🚨 Most Common Failures")
        #     # Mostra os 5 testes que mais falham
        #     st.bar_chart(common_errors.head(5))
        # else:
        #     st.success("No common failures detected!")

        st.text("")
        render_top_indicators(stats_df)

        with st.container(height=610, width='stretch'):
            st.subheader("📈 Evolution")
            student_list = sorted(s.username for s in st.session_state.raw_data)
            render_student(quiz_id, student_list, stats_df)

            render_detailed_test_grid(st.session_state.raw_data)

            st.divider()
            st.subheader("Progress Matrix (Overall %)")
            matrix_df = stats_df.set_index("Student").filter(like="(%)")
            matrix_df = matrix_df[~matrix_df.index.duplicated(keep='first')]

            if not matrix_df.columns.is_unique:
                new_cols = []
                counts = {}
                for col in matrix_df.columns:
                    counts[col] = counts.get(col, 0) + 1
                    new_cols.append(f"{col}_{counts[col]}" if counts[col] > 1 else col)
                matrix_df.columns = new_cols

            st.dataframe(
                matrix_df.style.background_gradient(cmap="RdYlGn", vmin=0, vmax=100),
                width="stretch"
            )
    else:
        st.info("Please enter credentials in the sidebar and click 'Sync Now'.")
