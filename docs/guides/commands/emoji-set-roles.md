# /emoji set-roles | Emoji Set Roles

!!! warning "Permissions required: user, bot"

    Both yourself and the bot must have the `Manage Expressions` permission in order to use this command.

!!! danger "This command is not available everywhere, despite being visible"

    Due to the way group commands work (notice the space between `emoji` and `set-role`?), either the entire group is
    available in a user context, or none of it is. As such, this command *will show up* in your command list, however,
    if the bot is not in the server, it cannot see any of the server emojis, and definitely cannot edit them.

    You will need to invite the bot into the server in order to use the command.

`/emoji set-role` allows you to change what roles are able to use a given emoji. You can use this, for example,
to lock a set of emojis behind a Nitro Booster role.

## Usage

`/emoji set-role emoji::name:`

`emoji` is the emoji you want to set the roles for. This MUST be a custom emoji, __in the current server__.

After you have picked your emoji and sent the command, you will then be asked to select the roles that can use the emoji
by clicking on the dropdown menu, and clicking on all the roles you want to be able to use the emoji.
Remember, you can type into this box, so you can search for roles if your server has lots of roles.

**You can only pick up to 25 roles.**

After selecting all the roles you want to use, press `apply`. This will then set the roles for the emoji.
You will know if it was successful as the `apply` button will turn green and say "Applied!"
After a few seconds, the menu will unlock and allow you to re-apply changes if you need to.

!!! tip "How do I make the role accessible by all again??"

    If you want to revert the changes, you will need to re-run the command, but when you get to the role selection,
    simply skip it and press apply (or de-select any roles already selected first).
    This will set the allowed roles to "all roles", the default.
