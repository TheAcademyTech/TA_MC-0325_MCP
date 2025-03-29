"""
Provides MCP (Model Context Protocol) server logic for PostgreSQL.

This server exposes tools to query a PostgreSQL database, list available tables,
and retrieve table schemas. It uses environment variables for configuration.
"""

import os
import sys
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment variables
POSTGRES_CONNECTION_STRING = os.getenv("POSTGRES_CONNECTION_STRING", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
DEBUG = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")

# Configure logging
def setup_logging(debug=False):
    """Configure logging for the application."""
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger("postgres-mcp")

logger = setup_logging(debug=DEBUG)

# Initialize MCP Server
mcp = FastMCP("PostgreSQL-MCP")

def get_connection():
    """
    Create a connection to the PostgreSQL database.
    
    Returns:
        psycopg2.connection: A connection to the PostgreSQL database.
    """
    try:
        if POSTGRES_CONNECTION_STRING:
            logger.debug(f"Connecting using connection string")
            return psycopg2.connect(POSTGRES_CONNECTION_STRING)
        else:
            logger.debug(f"Connecting using individual parameters")
            return psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                dbname=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD
            )
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}", exc_info=True)
        raise


@mcp.tool()
def list_tables() -> str:
    """
    List all available tables in the PostgreSQL database.
    
    Returns:
        str: A JSON-encoded string of available tables.
    """
    logger.debug("Handling list_tables tool.")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query to get all public tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        
        tables = cursor.fetchall()
        logger.debug(f"Found {len(tables)} tables")
        
        return json.dumps([table["table_name"] for table in tables])
    except Exception as e:
        logger.error(f"Error listing tables: {e}", exc_info=True)
        return json.dumps({"error": str(e)})
    finally:
        if conn:
            conn.close()


@mcp.tool()
def get_table_schema(*, table_name: str) -> str:
    """
    Get the schema for a specific table.
    
    Args:
        table_name (str): The name of the table to get the schema for.
        
    Returns:
        str: A JSON-encoded string of the table schema.
    """
    logger.debug(f"Handling get_table_schema tool for table: {table_name}")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query to get column information for the specified table
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns = cursor.fetchall()
        logger.debug(f"Found {len(columns)} columns for table {table_name}")
        
        # Query to get primary key information
        cursor.execute("""
            SELECT c.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage AS ccu USING (constraint_schema, constraint_name)
            JOIN information_schema.columns AS c 
              ON c.table_schema = tc.constraint_schema AND c.table_name = tc.table_name AND c.column_name = ccu.column_name
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_name = %s
        """, (table_name,))
        
        primary_keys = [pk["column_name"] for pk in cursor.fetchall()]
        
        # Create a schema object
        schema = {
            "table_name": table_name,
            "columns": columns,
            "primary_keys": primary_keys
        }
        
        return json.dumps(schema, default=str)
    except Exception as e:
        logger.error(f"Error getting schema for table {table_name}: {e}", exc_info=True)
        return json.dumps({"error": str(e)})
    finally:
        if conn:
            conn.close()


@mcp.tool()
def execute_query(*, sql: str) -> str:
    """
    Execute a read-only SQL query against the PostgreSQL database.
    
    Args:
        sql (str): The SQL query to execute.
        
    Returns:
        str: A JSON-encoded string of the query results.
    """
    logger.debug(f"Handling execute_query tool with SQL: {sql}")
    conn = None
    try:
        conn = get_connection()
        # Set session to read-only
        with conn:
            with conn.cursor() as setup_cursor:
                setup_cursor.execute("SET TRANSACTION READ ONLY")
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(sql)
            
            results = cursor.fetchall()
            logger.debug(f"Query returned {len(results)} rows")
            
            # Convert to a list of dictionaries
            results_list = []
            for row in results:
                # Convert all values to proper JSON serializable format
                processed_row = {}
                for key, value in row.items():
                    if isinstance(value, (int, float, str, bool, type(None))):
                        processed_row[key] = value
                    else:
                        processed_row[key] = str(value)
                results_list.append(processed_row)
            
            return json.dumps(results_list)
    except Exception as e:
        logger.error(f"Error executing query: {e}", exc_info=True)
        return json.dumps({"error": str(e)})
    finally:
        if conn:
            conn.close()


@mcp.tool()
def describe_database() -> str:
    """
    Get a high-level description of the database including tables and their row counts.
    
    Returns:
        str: A JSON-encoded string with database information.
    """
    logger.debug("Handling describe_database tool")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        
        tables = cursor.fetchall()
        database_info = {
            "database_name": POSTGRES_DB,
            "tables": []
        }
        
        # For each table, get the row count and schema
        for table in tables:
            table_name = table["table_name"]
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) as row_count FROM \"{table_name}\"")
            row_count = cursor.fetchone()["row_count"]
            
            # Get column information
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            
            columns = cursor.fetchall()
            
            database_info["tables"].append({
                "name": table_name,
                "row_count": row_count,
                "columns": columns
            })
        
        return json.dumps(database_info, default=str)
    except Exception as e:
        logger.error(f"Error describing database: {e}", exc_info=True)
        return json.dumps({"error": str(e)})
    finally:
        if conn:
            conn.close()


def run_server():
    """
    Run the MCP server for PostgreSQL.
    
    This function ensures proper configuration and handles server initialization.
    """
    if not (POSTGRES_CONNECTION_STRING or (POSTGRES_HOST and POSTGRES_DB and POSTGRES_USER)):
        logger.error("PostgreSQL connection details not provided. Set either POSTGRES_CONNECTION_STRING "
                    "or POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, and POSTGRES_PASSWORD.")
        sys.exit(1)
    
    try:
        # Test database connection before starting the server
        conn = get_connection()
        conn.close()
        logger.info("Successfully connected to PostgreSQL database.")
        
        logger.info("Starting PostgreSQL MCP server...")
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error("Failed to start MCP server.", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_server()