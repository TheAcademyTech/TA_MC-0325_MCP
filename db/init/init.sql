-- Create the database (this is handled by docker-compose environment variables)
-- The database is already created by the time this script runs

-- Drop existing objects if they exist
DROP VIEW IF EXISTS course_statistics;
DROP VIEW IF EXISTS student_performance_summary;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS education_levels CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS learning_styles CASCADE;
DROP TABLE IF EXISTS engagement_levels CASCADE;

-- Create education_levels table
CREATE TABLE education_levels (
    id SERIAL PRIMARY KEY,
    level VARCHAR(50) UNIQUE NOT NULL
);

-- Create courses table
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

-- Create learning_styles table
CREATE TABLE learning_styles (
    id SERIAL PRIMARY KEY,
    style VARCHAR(50) UNIQUE NOT NULL
);

-- Create engagement_levels table
CREATE TABLE engagement_levels (
    id SERIAL PRIMARY KEY,
    level VARCHAR(20) UNIQUE NOT NULL
);

-- Create students table (main table)
CREATE TABLE students (
    student_id VARCHAR(10) PRIMARY KEY,
    age INT NOT NULL CHECK (age > 0),
    gender VARCHAR(20),
    education_level_id INT,
    course_id INT,
    time_spent_on_videos INT,
    quiz_attempts INT,
    quiz_scores DECIMAL(5,2),
    forum_participation INT,
    assignment_completion_rate DECIMAL(5,2),
    engagement_level_id INT,
    final_exam_score DECIMAL(5,2),
    learning_style_id INT,
    feedback_score INT CHECK (feedback_score BETWEEN 1 AND 5),
    dropout_likelihood VARCHAR(3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (education_level_id) REFERENCES education_levels(id),
    FOREIGN KEY (course_id) REFERENCES courses(id),
    FOREIGN KEY (engagement_level_id) REFERENCES engagement_levels(id),
    FOREIGN KEY (learning_style_id) REFERENCES learning_styles(id)
);

-- Create indexes for better query performance
CREATE INDEX idx_student_course ON students(course_id);
CREATE INDEX idx_student_engagement ON students(engagement_level_id);
CREATE INDEX idx_student_education ON students(education_level_id);
CREATE INDEX idx_student_learning_style ON students(learning_style_id);

-- Insert initial data into lookup tables
INSERT INTO education_levels (level) VALUES 
    ('High School'),
    ('Undergraduate'),
    ('Postgraduate');

INSERT INTO courses (name) VALUES 
    ('Machine Learning'),
    ('Python Basics'),
    ('Data Science'),
    ('Web Development'),
    ('Cybersecurity');

INSERT INTO learning_styles (style) VALUES 
    ('Visual'),
    ('Reading/Writing'),
    ('Kinesthetic');

INSERT INTO engagement_levels (level) VALUES 
    ('Low'),
    ('Medium'),
    ('High');

-- Create a temporary table to load CSV data
CREATE TEMPORARY TABLE temp_students (
    Student_ID VARCHAR(10),
    Age INT,
    Gender VARCHAR(20),
    Education_Level VARCHAR(50),
    Course_Name VARCHAR(100),
    Time_Spent_on_Videos INT,
    Quiz_Attempts INT,
    Quiz_Scores DECIMAL(5,2),
    Forum_Participation INT,
    Assignment_Completion_Rate DECIMAL(5,2),
    Engagement_Level VARCHAR(20),
    Final_Exam_Score DECIMAL(5,2),
    Learning_Style VARCHAR(50),
    Feedback_Score INT,
    Dropout_Likelihood VARCHAR(3)
);

-- Load data from CSV
\copy temp_students FROM '/docker-entrypoint-initdb.d/data/learning_dataset.csv' WITH (FORMAT csv, HEADER true);

-- Insert data from temporary table into the main students table
INSERT INTO students (
    student_id, age, gender, education_level_id, course_id,
    time_spent_on_videos, quiz_attempts, quiz_scores,
    forum_participation, assignment_completion_rate,
    engagement_level_id, final_exam_score,
    learning_style_id, feedback_score, dropout_likelihood
)
SELECT 
    t.Student_ID,
    t.Age,
    t.Gender,
    el.id,
    c.id,
    t.Time_Spent_on_Videos,
    t.Quiz_Attempts,
    t.Quiz_Scores,
    t.Forum_Participation,
    t.Assignment_Completion_Rate,
    eng.id,
    t.Final_Exam_Score,
    ls.id,
    t.Feedback_Score,
    t.Dropout_Likelihood
FROM temp_students t
JOIN education_levels el ON t.Education_Level = el.level
JOIN courses c ON t.Course_Name = c.name
JOIN engagement_levels eng ON t.Engagement_Level = eng.level
JOIN learning_styles ls ON t.Learning_Style = ls.style;

-- Drop temporary table
DROP TABLE temp_students;

-- Create views for common queries
CREATE VIEW student_performance_summary AS
SELECT 
    s.student_id,
    c.name as course_name,
    s.quiz_scores,
    s.final_exam_score,
    s.assignment_completion_rate,
    el.level as engagement_level
FROM students s
JOIN courses c ON s.course_id = c.id
JOIN engagement_levels el ON s.engagement_level_id = el.id;

CREATE VIEW course_statistics AS
SELECT 
    c.name as course_name,
    COUNT(*) as total_students,
    AVG(s.final_exam_score) as avg_final_score,
    AVG(s.quiz_scores) as avg_quiz_score,
    AVG(s.assignment_completion_rate) as avg_completion_rate
FROM students s
JOIN courses c ON s.course_id = c.id
GROUP BY c.name;
