# Spanner v3

<https://bots.nexy7574.co.uk/spanner/v3> | <https://spanner.nexy7574.co.uk/api/docs>

Version 3 of spanner, with a mildly reduced scope.

v3 will replace all the following:

* [Version 2](https://github.com/nexy7574/spanner-v2)
* [Version 1](https://github.com/nexy7574/spanner-bot)
* [Assistant](https://github.com/nexy7574/spanner-assistant)

v3 is designed to work with discord features, not replace them. As such, some things like moderation are not included
as part of spanner's feature set, unlike in previous releases.

## Installing

You can install spanner with docker:

```bash
openssl rand -hex 32 > jwt_secret_key && \
docker run -it --name spanner-v3 \
-v ./data:/app/data \
-v ./config.toml:/app/config.toml \
-p 1237:1237/tcp \
-e "JWT_SECRET_KEY=$(cat jwt_secret_key)" \
-e "DISCORD_CLIENT_SECRET=<oauth client token>" \
-e "DISCORD_CLIENT_ID=<oauth client ID>" \
ghcr.io/spannerbot/spanner-v3:dev
```

You can also run it without docker:

```bash
# Make sure you've set up config.toml in the PWD
# Need help setting up intents in the config? run `python3 -m spanner intents`
export JWT_SECRET_KEY=$(python3 -m spanner generate-token)
python3 -m spanner run
```

## Configuration
See [config.example.toml](spanner/config.example.toml) for an example configuration file.
All available options are in there.
