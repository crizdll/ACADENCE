ACADENCE - ACADEMIC ORGANIZER WEBSITE

FEATURES
- Create an account, log in, and log out.
- Each account has its own subjects, grades, and assignments.
- Add, edit, and delete subjects.
- Set the number of quizzes, activities, oral presentations, and projects (0 to 50 each).
- Enter scores and maximum points for each quiz, activity, oral presentation, and project.
- Enter separate Preliminary, Midterm, and Final Examination scores.
- Customize the percentage weight for quizzes, activities, oral presentations, projects, prelims, midterms, and finals.
- Any unused grading category can be excluded by setting its percentage to 0%. The percentages of the included categories must total 100%.
- Subjects can omit any assessment type by setting its count and percentage to 0%.
- Add, complete, and delete assignments.
- View deadline reminders and a study-priority planner.

REQUIREMENTS
- Python 3
- Visual Studio Code (recommended)
- Flask

SETUP ON WINDOWS
1. Extract Acadence_Project.zip.
2. Open the extracted Acadence folder in Visual Studio Code.
3. Open Terminal > New Terminal.
4. Create a virtual environment:
   python -m venv venv
5. Activate it:
   venv\Scripts\activate
6. Install Flask:
   python -m pip install flask
7. Run the website:
   python app.py
8. Open this address in your browser:
   http://127.0.0.1:5000
9. Choose Create an account.

GRADING CALCULATION
The website calculates a weighted estimate using the percentages you set for quizzes, activities, oral presentations, projects, and the three examinations. Each assessment percentage is based on points earned divided by maximum points. The categories with entered scores are used for the current estimate, and their weights are temporarily rebalanced. Categories with a percentage of 0% are excluded. All configured category percentages must add up to 100%.

IMPORTANT NOTES
- This is a beginner-friendly local prototype, not a deployed public website.
- Account passwords are stored as password hashes, not plain text.
- Before deploying publicly, configure a long random Flask secret key, add CSRF protection, use HTTPS, and review security settings.
- The grade shown is an estimate based only on the scores and percentages entered. It is not a guaranteed prediction of a final course grade.
- The SQLite database file (acadtrack.db) is created automatically beside app.py.


GRADE TRACKER UPDATE
- Each quiz and activity accepts earned points and its own maximum points.
- Preliminary, Midterm, and Final exams each have editable earned and maximum points.
- Percentages are calculated from earned points divided by maximum possible points.
- For a category with multiple quizzes or activities, Acadence adds the earned points and divides by the sum of maximum points.
- Example: 45/50 and 36/40 gives (81/90) x 100 = 90%.
- Older databases are updated automatically when the app starts; existing assessment maximums default to 100.


IN-PROGRESS GRADE ESTIMATES
- You do not need to wait until the end of the semester to enter grades.
- Leave the earned-score field blank for quizzes, activities, or exams that have not happened or have not been graded yet.
- For quiz/activity score lists, use a blank position between commas for an assessment not taken yet (example: 45, , 28). Keep the maximum-points list in the same order.
- The estimated grade uses only completed assessments. It temporarily rebalances the weights of categories that have scores entered.
- Because future assessments are not included yet, this is an in-progress estimate, not a guaranteed final grade or pass/fail prediction.


OPTIONAL ASSESSMENT TYPES
- Each subject can have quizzes, activities, oral presentations, and projects.
- Set the count to 0 and the weight to 0% for any type that the subject does not use.
- Enter a score list and matching maximum-points list for every assessment type that is used.
- Example: oral presentation scores 18, , 25 with maximum points 20, 30, 30 means the second presentation score has not been entered yet.
- Give each assessment type its own grading percentage; all category percentages must total 100%.
