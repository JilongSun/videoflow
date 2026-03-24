import os
from dotenv import load_dotenv

load_dotenv()

from videoflow.mcp_server.server import run_server

if __name__ == "__main__":
    run_server()
