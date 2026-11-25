FROM python:3.11-slim

WORKDIR /app

# Pin mcp to v1.x for FastMCP compatibility
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY server.py /app/server.py

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["python", "server.py"]
