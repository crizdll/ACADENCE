# Acadence – Code Quality and Testing Checklist

This checklist is intended to be completed during actual testing. Do not mark a test as passed until it has been run in the target environment.

| Area | Test | Expected result | Actual result |
|---|---|---|---|
| Account | Register with valid details | Account is created and user is logged in | To be tested |
| Account | Register with a duplicate username | Clear error; no duplicate account | To be tested |
| Account | Log in with an incorrect password | Access is denied with an error message | To be tested |
| Access control | Open a protected page while logged out | Redirect to login page | To be tested |
| Subjects | Save a valid subject | Subject is stored and displayed | To be tested |
| Subjects | Submit a blank subject name | Validation error is displayed | To be tested |
| Scores | Enter a score greater than its maximum | Validation error is displayed | To be tested |
| Scores | Leave an assessment score blank | Missing score is excluded from the current estimate | To be tested |
| Weights | Enter category weights totaling 100% | Subject is accepted | To be tested |
| Weights | Enter category weights not totaling 100% | Validation error is displayed | To be tested |
| Assignments | Add an assignment with a valid date | Assignment is saved | To be tested |
| Assignments | Enter an invalid date | Validation error is displayed | To be tested |
| Planner | Add overdue and upcoming tasks | Priority and deadline labels are displayed | To be tested |
| Data isolation | Log in as another account | Only that account's records are displayed | To be tested |

## Static checks completed on the supplied ZIP
- Python syntax compilation of `app.py`: passed.
- Full Flask runtime and browser testing: not performed in the current environment because Flask is not installed.

## Known development considerations
- `app.secret_key` is a placeholder and must be replaced with a private random value before deployment.
- `app.run(debug=True)` is for local development only. Disable debug mode before deployment.
- Add CSRF protection before exposing the application publicly.
- The SQLite database filename remains `acadtrack.db` for compatibility with the existing project database; this does not change the user-facing Acadence branding.
