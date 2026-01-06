# CodeRunner Dash – Moodle Quiz Monitoring Dashboard

Warning: This project contains substantial amounts of AI-generated code. `:-(`

## Overview
CodeRunner Dash is a real-time monitoring dashboard built with Streamlit to track and visualize student performance on CodeRunner questions within Moodle quizzes. It provides instructors with actionable insights into submission patterns, success rates, and common failure points across an entire class.

## Features
- Secure login via Moodle credentials
- Interactive metrics: student count, total submissions, success distribution
- Automated analytics: identifies top roadblocks and failure patterns
- Visual progress matrix with color-coded success rates
- One-click sync to fetch latest quiz data
- Bar charts and gradient tables for quick interpretation

## Getting Started

### Prerequisites
- Python 3.8+
- Moodle account with access to quiz logs
- Required Python packages:
  ```bash
  streamlit pandas
  ```

### Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/jandermoreira/coderunner-dash.git
cd coderunner-dash
pip install -r requirements.txt
```

### Environment Variables (Optional)
Set Moodle credentials to pre-fill the login form:
```bash
export MOODLE_USER="your_username"
export MOODLE_PASS="your_password"
export MOODLE_QUIZ_ID="quiz_id"
```

### Run the Dashboard
```bash
streamlit run coderunner_dash.py
```

## Usage
1. Open the dashboard in your browser (usually `http://localhost:8501`)
1. Enter Moodle credentials and Quiz ID in the sidebar
1. Click "Sync Now" to fetch the latest data
1. Explore the analytics panels:
   - Success distribution per student
   - Top roadblocks (most failed test cases)
   - Progress matrix with color-coded performance

## Dependencies
- streamlit – Dashboard framework
- pandas – Data manipulation and analysis

## License
This project is provided under the MIT License.

## Contributing
Contributions are welcome. Please open an issue or submit a pull request for any improvements or bug fixes.
