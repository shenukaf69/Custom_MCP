# Copilot Consultant MCP server as a web service (Streamable HTTP at /mcp).
# Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8000
EXPOSE 8000
CMD ["python", "server.py", "--http", "--port", "8000"]
