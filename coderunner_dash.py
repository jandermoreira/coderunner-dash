"""
Coderunner dashboard
====================

CodeRunner Dash is a real-time monitoring dashboard built with Streamlit to
track and visualize student performance on CodeRunner questions within Moodle
quizzes. It provides instructors with actionable insights into submission patterns,
success rates, and common failure points across an entire class.
"""

from dashboard.ui import run_dashboard

if __name__ == "__main__":
    run_dashboard()
