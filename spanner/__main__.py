import click
import discord


@click.group()
def cli():
    """Spanner CLI. Mostly utility."""
    pass


@cli.command()
@click.option(
    "--as-table",
    "-T",
    is_flag=True,
    help="Prints the intents as a TOML table, instead of raw bitfield value."
)
def intents(as_table: bool):
    """Generates a value for intents, to put in your configuration."""
    base = discord.Intents.default()
    if click.confirm(
        "Do you want to configure the default (non-privileged) intents? (not recommended)",
        default=False
    ):
        for intent, enabled in base:
            if intent in {"message_content", "members", "presences"}:
                continue  # skip
            setattr(
                base,
                intent,
                click.confirm(
                    f"Do you want to enable {intent!r}?", default=enabled
                )
            )

    base.message_content = click.confirm(
        "Do you want to enable the %s intent? (%s)" % (
            click.style("message content", bold=True),
            click.style("you may need approval", fg="red")
        ),
        default=False
    )
    base.members = click.confirm(
        "Do you want to enable the %s intent? (%s)" % (
            click.style("members", bold=True),
            click.style("you may need approval", fg="red")
        ),
        default=False
    )
    base.presences = click.confirm(
        "Do you want to enable the %s intent? (%s)" % (
            click.style("presences", bold=True),
            click.style("you may need approval", fg="red")
        ),
        default=False
    )

    click.echo("Your intents value is: ", nl=False)
    if as_table:
        click.echo()
        click.secho("[spanner.intents]", fg="cyan")
        for intent, enabled in base:
            click.echo(f"{intent} = {str(enabled).lower()}")
        click.echo()
    else:
        click.secho(str(base.value), fg="cyan")
    click.echo("You should put this in your configuration file, under the `spanner.intents` key (below your token).")


@cli.command()
def run():
    """Runs the bot."""
    from spanner.main import run as run_bot

    click.secho("Starting bot...", fg="green")
    run_bot()


if __name__ == "__main__":
    cli()
