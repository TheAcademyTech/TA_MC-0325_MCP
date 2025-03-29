# Learning Analytics MCP Workshop

This repository contains a workshop for building an MCP (Model Context Protocol) server that interfaces with a PostgreSQL database containing educational learning analytics data. The workshop demonstrates how to create an AI-powered analytics system using Groq LLMs and MCP.

## Project Overview

This workshop teaches you how to:
1. Set up a PostgreSQL database with educational data
2. Create an MCP server to interface with the database
3. Use Groq LLMs to query and analyze the data through our MCP client
4. Build AI-powered analytics capabilities using the Model Context Protocol

## Workshop Setup Steps

Follow these steps to set up and run the workshop:

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/ta_mcp.git
cd ta_mcp
```

### 2. Set Up Python Environment with uv

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver that we'll use for dependency management.

If you don't have uv installed:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then create a virtual environment and install dependencies:

```bash
# Create a virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate  # On Linux/macOS
# OR
.venv\Scripts\activate     # On Windows

# Install dependencies
uv pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Create a `.env` file in the project root with your Groq API key:

```bash
echo "GROQ_API_KEY=your-groq-api-key" > .env
echo "GROQ_MODEL=llama-3.3-70b-versatile" >> .env
```

You can get a Groq API key by signing up at [groq.com](https://console.groq.com/keys).

### 4. Start the Database with Docker Compose

We use Docker Compose to manage our PostgreSQL database container:

```bash
# Start just the database container
docker-compose up -d db
```

Wait for the database to initialize (this may take a minute or two).

### 5. Run the MCP Client

The MCP client will automatically start the MCP server when needed. Run the client with:

```bash
# Run the MCP client, which will automatically execute the server
uv run src/mcp_client.py src/mcp_server.py
```

This command passes the path to the MCP server script as a parameter, and the client will handle executing the server whenever needed.

### Optional: Verify MCP Server Separately

If you want to verify that the MCP server works correctly on its own, you can run it separately:

```bash
uv run src/mcp_server.py
```

This step is completely optional and just for verification purposes.

## Using the MCP Client

Once the client is running, you can:
- Enter natural language queries about educational data
- Use commands like `/help` to view available commands
- Try different Groq models with `/model <model_name>`
- Clear conversation history with `/clear`
- Exit with `/quit`

Example queries you can ask:
- "What's the average quiz score for students in the Machine Learning course?"
- "Show me the correlation between video watch time and final exam scores"
- "Which learning style is most effective for the Data Science course?"
- "Identify students at risk of dropping out based on their engagement patterns"

## Database Details

- Database Name: learning_analytics
- Username: admin
- Password: admin123
- Port: 5432

## Data Schema

The database contains normalized tables for educational analytics:

### Main Tables

#### students
- `student_id` (Primary Key)
- `age`
- `gender`
- `education_level_id` (Foreign Key)
- `course_id` (Foreign Key)
- `time_spent_on_videos`
- `quiz_attempts`
- `quiz_scores`
- `forum_participation`
- `assignment_completion_rate`
- `engagement_level_id` (Foreign Key)
- `final_exam_score`
- `learning_style_id` (Foreign Key)
- `feedback_score`
- `dropout_likelihood`

#### Lookup Tables
- `education_levels`
- `courses`
- `learning_styles`
- `engagement_levels`

### Views
- `student_performance_summary`: Quick access to student performance metrics
- `course_statistics`: Course-level analytics and statistics

## Troubleshooting

- **Database Connection Issues**: Ensure Docker is running and the database container is active
- **MCP Server Errors**: Check if PostgreSQL is properly initialized
- **API Key Errors**: Verify your Groq API key in the `.env` file
- **Dependency Issues**: Make sure to use uv to install all dependencies from requirements.txt

## Contributing

This is a workshop repository for The Academy. Feel free to submit issues and enhancement requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
