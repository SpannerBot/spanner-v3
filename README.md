# Spanner v3

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
ghcr.io/nexy7574/spanner-v3:dev
```

## Configuration
See [config.example.toml](spanner/config.example.toml) for an example configuration file.
All available options are in there.
