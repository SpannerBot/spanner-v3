# Getting Started

Not sure how to get started with spanner? This guide will help you get up and running in no time!

## 1. Installation

The first step to using spanner is actually inviting it. You can do this with one of the following links:

### Server Installation

This will add the bot itself to your server, where you will get access to all the features spanner has to offer.

* [Invite Spanner v3 to your server here](https://discord.com/oauth2/authorize?client_id=1237136674451099820&permissions=17180256320&integration_type=0&scope=bot)

### User Installation

Recently, discord rolled out an update that allowed you to use some bots everywhere (where permissions allow).

As such, a limited number of features are available for use without even needing to invite the bot to a server!
Due to the nature of the bot not actually being *in* the server, some features may not work as expected, or may be
missing information.

* [Authorise Spanner v3 here](https://discord.com/oauth2/authorize?client_id=1237136674451099820&integration_type=1&scope=applications.commands)

## 2. Setting up

Once you have invited spanner to your server, you can start setting it up!

### Configuring permissions

The first thing you should look at is what permissions are set up by default.

For its slash commands, spanner sets a few "reasonable defaults" for permissions, meaning that, for example,
you need `manage roles` in order to use commands related to... managing roles (such as self-roles).

You should check that all of these are set appropriately for your server, **as spanner will NOT validate permissions
beyond what discord allows**.

To get change this, go to **Server Settings** => **Integrations** => (under bots and apps) **Spanner v3**

Here you will see a list of permissions that spanner has, and you can toggle them on or off as you see fit.
You can choose to only allow commands to run in certain channels, or block them from certain channels,
and even allow/deny roles access to commands.

If you click on a command in the commands list, you can see what permissions are required to run that command.
Furthermore, you can add roles to the command to allow or deny it access to the command.

\<Gif Here\>

### Setting up logging

[See guides/features/logging](./features/Logging.md)
