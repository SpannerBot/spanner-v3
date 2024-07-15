# Logging

Spanner v3 features a rich event logging system that allows you to keep track of what's happening in your server,
super-charged by the discord audit log.

This is the first thing you should do as it is seen as the "entry point" to Spanner. Without it, some commands may not
work.

---

To set up logging, you need to have a channel where you would like to send logs to. It is recommended that you set this
as a channel that is private for staff. The discord auto-moderator channel is likely a good choice for most people.

## 1. Setting the log channel

You can run `/settings set-log-channel` and specify which channel you would like to send logs to. This will set the
channel for all logs to be sent to.

![Example image showing the use of `/settings set-log-channel` with the `channel` argument set to `#logs`](../../img/set_log_channel.webp)

And that's all you need to do! If spanner cannot use the specified channel as a log channel, it will tell you what you
need to do in order to use it. Once you've applied any changes it requests, you can re-run the command.
Alternatively, you can specify another channel.

!!! note
    If you do not have a log channel set, spanner will not log anything.

## 2. Setting up what you want to log

Next, you need to pick what is actually logged to your log channels! Spanner allows you to easily enable or disable
what is logged, using "feature flags", which are actually just "java-style namespaces".

If that sounds a bit technical, here's an example:

??? example "Explanation of flags"

    ```text
    member.join
    ```
    
    Here, there's two parts to this "flag": `member`, and `join`.
    This means when a `member` `join`s, log.
    
    There's also
    
    ```text
    member.roles.update
    ```
    
    There's *three* parts to this flag: `member`, `roles`, `update`.
    Extrapolating from the previously mentioned flag, this means that when a `member`'s `roles` are `update`d, log.

    You can also use wildcards to match multiple events, such as `member.*` to match all member events.

### Enabling logs

You need to use `/settings log-features enable` to enable logging features.

Once you type this command in, discord will bring up a window with a bunch of different feature flags that you can
enable, like below:

![Example image showing the use of `/settings log-features enable`](../../img/settings_log_features_enable_empty.webp)  

If you see the flag you want to enable, click on it, and send the command. If you want to enable multiple flags, you can
either re-run the command with a different flag, or specify multiple flags in the same command. **Specifying multiple
flags in one argument will not work with autocomplete,** so you must know beforehand what you want to enable.

!!! tip "Bulk-enabling via wildcard"

    You can enable loads of features at once by using `name.*`, where `name` is the name of the feature you want to
    enable. For example, `member.*` will enable all member events.

    You can also specify the entire argument as `*`, which will enable all features.

    ![Example image showing the use of `/settings log-features enable` with the `*` argument](../../img/settings_log_features_enable_all.webp)

### Disabling logs

You can disable logs following exactly the same process as [enabling them](#enabling-logs), but using
`/settings log-features disable` instead.

### Toggling logs

If for whatever reason you want to disable a feature that is currently enabled, or enable a feature that is currently
disabled, you can use `/settings log-features toggle`.
