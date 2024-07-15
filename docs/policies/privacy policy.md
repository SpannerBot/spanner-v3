# Privacy Policy

This document outlines the privacy practices and policies that Spanner adheres to.

Please note that you must be at least 13 in order to use Spanner, as per Discord's terms of service.

Some definitions:
- Server: discord server
- Host: the physical server spanner runs on
- We/Us/I/Developers: the developers of Spanner
- Platform: discord
- Spanner/Bot: the bot itself, including the discord API bot, and the website+API

!!! question "I have questions!"

    If you have any questions or concerns, feel free to join our support server and ask for help. The invite to the
    support server can be found in the bot's "About Me" in the profile.

!!! danger "I am not a lawyer."

    I ([nexy7574](https://github.com/nexy7574)) am not a lawyer - please let me know if you have any concerns or
    suggestions regarding this document.

## 1. How data is collected & data security

When an event happens on discord, the platform will send some data to Spanner over a websocket connection.
This websocket connection is secured via TLS, and as such is encrypted between discord's host and Spanner's host.

Spanner runs on an **unencrypted** hard drive, as such, any data stored is unencrypted. This is a limitation of the
hardware upon which spanner is running, and cannot be easily changed.
However, the host is secure, both physically and digitally - remote access is only possible via a secure VPN
(using WireGuard, more specifically [Tailscale](https://tailscale.com/), which is trusted by industry experts), and
the host only permits external connections to HTTP and HTTPS, which is running in a secure, sandboxed environment.
Furthermore, the host is stored in a secure premises, and itself is locked away in a secure cabinet.

When spanner determines that it needs to store some data, it connects to a Postgresql database, which is stored on
the local server, meaning it does not need to send requests over the network, as such never leaving the device.
This Postgresql server is not remotely accessible, only from the local area network that the server is also on.

## 2. Data retention

Spanner will retain data for as long as it is necessary to provide the service. However, most data can be automatically
deleted by simply removing Spanner from the server, which will delete all data associated with that server, in a
cascading manner.

You can also request that your data be deleted by contacting the developer in the support server.

Please note that the only way to prevent spanner from ever collecting data is to not participate in any servers that
have spanner in it - if you have no servers with spanner, it does not know that you exist.

!!! danger "Deletion is permanent!"

    Please note that once data is deleted, it is gone forever. There is no way to recover it, so please be sure that
    you want to delete your data before requesting it, or removing the bot.


## 3. What data is stored

Almost all data that is stored is related to a server that spanner is in. This is identifiable by the server ID, which
is a unique field that is assigned by discord to each server.
Some additional unique identifiers may be collected where relevant, such as discord message IDs, discord channel IDs,
discord role IDs, and discord channel IDs.
All other identifiers are [uuid](https://en.wikipedia.org/wiki/Universally_unique_identifier)s, which are unique to
spanner. These UUIDs are only used as unique identifiers for rows in the data entry, and are (usually) not actually
identifiable to any specific event.

### General data

You can see all the tables and schemas that spanner uses in the database
[on GitHub](https://github.com/nexy7574/spanner-v3/blob/dev/spanner/share/database.py), however a general summary
of what is personally identifiable is below:

#### Guild Configuration

- Server ID (e.g. `729779146682793984`)
- Log channel ID (e.g. `729779146682793987`)

#### Guild Audit Log

!!! info "This is NOT discord's audit log!"

    In order to maintain a paper trail of changes made to spanner's configuration, each time a setting is changed,
    spanner will create an entry in the database of who changed what, and when.
    This audit log is exclusive to spanner.

- Server ID (e.g. `729779146682793984`)
- Author User ID (e.g. `421698654189912064`)

#### Self-role menus

- Server ID (e.g. `729779146682793984`)
- Menu name
- Menu channel ID
- Menu message ID
- List of role IDs

#### Premium Information (keys, guild)

Premium keys are generated whenever a user purchases a premium key, and are stored in the database.
A "purchase" is either by sending money directly to the developer in exchange for a key, or by purchasing a key
via the Discord store (only the latter can be used once it is enabled).

Premium keys consist of:

- The key itself
- When the key was created
- When the key was redeemed
- The user ID who claimed the key

Once redeemed, a Premium Guild entry is also created. This consists of:

- The server ID
- When the premium was redeemed
- When it expires, if applicable

#### Authentication

When you use the spanner API or dashboard, spanner stores the following information:

- Your OAuth2 access token
- Your OAuth2 refresh token
- When your access token expires
- A secret session key, which is stored in the browser.

When you authenticate spanner, the API will tell your browser to store a cookie called `_token`, which is a signed
JSON web token, which is actually just your User ID. This is used to identify you when you make requests to the API,
and cannot be tampered with. Deleting this cookie will log you out of the dashboard.


#### Starboard

The starboard __configuration__ stores the following information:

- Server ID
- Starboard channel ID
- The custom starboard emoji (may be identifiable if it's a custom discord emoji)

A starboard entry is created once `n` reactions are added to a message, and consists of:

- Source message ID
- Starboard message ID
- Source channel ID
- Starboard config UUID (which can then be used to find the server ID)


### 4. Why is it stored?

Spanner stores this data for exclusively functionality reasons. This means that there is no data used for analysis
or telemetry, and we do not sell or transfer any of this data to third parties (I mean, what benefit would we have?).
