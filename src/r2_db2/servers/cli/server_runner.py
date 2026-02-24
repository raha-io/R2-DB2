"""
CLI for running the R2-DB2 Agents FastAPI server.
"""

import json
from typing import Optional, TextIO, cast

import click


@click.command()
@click.option("--port", default=8000, help="Port to run server on")
@click.option("--host", default="0.0.0.0", help="Host to bind server to")
@click.option(
    "--config", type=click.File("r"), help="JSON config file for server settings"
)
@click.option("--debug", is_flag=True, help="Enable debug mode")
def main(
    port: int,
    host: str,
    config: Optional[click.File],
    debug: bool,
) -> None:
    """Run R2-DB2 Agents FastAPI server."""

    server_config = {}
    if config:
        server_config = json.load(cast(TextIO, config))

    try:
        from ...agents import create_basic_agent
        from ...integrations.mock import MockLlmService

        llm_service = MockLlmService(
            response_content="Hello! I'm a R2-DB2 Agents demo server. How can I help you?"
        )
        agent = create_basic_agent(llm_service)
        click.echo("✓ Using basic demo agent")
    except ImportError as e:
        click.echo(f"Error: Could not create basic agent: {e}", err=True)
        return

    from ..fastapi.app import R2-DB2FastAPIServer

    server = R2-DB2FastAPIServer(agent, config=server_config)
    click.echo(f"🚀 Starting FastAPI server on http://{host}:{port}")
    click.echo(f"📖 API docs available at http://{host}:{port}/docs")

    try:
        server.run(host=host, port=port, log_level="debug" if debug else "info")
    except KeyboardInterrupt:
        click.echo("\n👋 Server stopped")


if __name__ == "__main__":
    main()
