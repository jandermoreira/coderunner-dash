from scraper.parser import parse_step_detail
from datetime import datetime

# Files to be tested
sample_files = ["somente-erro-saida.html"]

for file_name in sample_files:
    with open(f'samples/{file_name}', 'r', encoding='utf-8') as html_file:
        html_content = html_file.read()

    # Parse the HTML content using the updated parser logic
    submission_step = parse_step_detail(html_content, datetime.now(), file_name)

    print(f"\n--- FILE: {file_name} ---")
    print(f"Score: {submission_step.score}")
    print(f"Total Test Cases: {len(submission_step.test_results)}")

    # Check flags directly from the SubmissionStep object
    # (No longer iterating through tests to find compilation errors)
    has_comp_error = submission_step.has_compilation_error
    has_run_error = submission_step.has_runtime_error

    print(f"Compilation Error Detected: {has_comp_error}")
    print(f"Runtime Error Detected: {has_run_error}")

    # Inspecting individual test cases for runtime errors (if any)
    for idx, test_case in enumerate(submission_step.test_results):
        print(f"  Test {idx + 1}: Passed={test_case.passed}, RuntimeErr={test_case.is_runtime_error}")

    # Logic validation: If score is 0 and no technical error was flagged
    if submission_step.score == 0 and not (has_comp_error or has_run_error):
        print("⚠️ WARNING: Score is zero but no technical error was classified!")

    print("-" * 40)