import discord
from discord.ext import commands

from spanner.share.utils import first_line, get_bool_emoji, humanise_bytes, hyperlink
from spanner.share.views import GenericLabelledEmbedView


class MessageInfoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_message_info(self, message: discord.Message) -> dict[str, discord.Embed]:
        if message.edited_at:
            le = discord.utils.format_dt(message.edited_at, 'R')
        else:
            le = 'Unedited.'
        overview_text = [
            f"**ID:** `{message.id}`",
            f"**Author:** {message.author.mention}",
            f"**Embeds:** {len(message.embeds)}",
            f"**Attachments:** {len(message.attachments)}",
            f"**URL:** {hyperlink(message.jump_url)}",
            f"**Created:** {discord.utils.format_dt(message.created_at, 'R')}",
            f"**Last Edited:** {le}",
            f"**Pinned?** {get_bool_emoji(message.pinned)}",
            f"**TTS?** {get_bool_emoji(message.tts)}",
            f"**System Message?** {get_bool_emoji(message.is_system())}",
        ]
        overview = discord.Embed(
            title=f"Message Overview - {message.id}",
            description="\n".join(overview_text),
            color=message.author.colour
        )
        result = {
            "Overview": overview
        }

        if message.flags.value:
            flags_text = [
                f"**Published?** {get_bool_emoji(message.flags.crossposted)}",
                f"**Cross-posted (from another server/channel)?** {get_bool_emoji(message.flags.is_crossposted)}",
                f"**Embeds suppressed?** {get_bool_emoji(message.flags.suppress_embeds)}",
                f"**Source message deleted?** {get_bool_emoji(message.flags.source_message_deleted)}",
                f"**Urgent message (from discord Trust and Safety)?** {get_bool_emoji(message.flags.urgent)}",
                f"**Associated with thread?** {get_bool_emoji(message.flags.has_thread)}",
                f"**Ephemeral message?** {get_bool_emoji(message.flags.ephemeral)}",
                f"**Loading (thinking)?** {get_bool_emoji(message.flags.loading)}",
                f"**Silent message?** {get_bool_emoji(message.flags.suppress_notifications)}",
                f"**Is a voice message?** {get_bool_emoji(message.flags.is_voice_message)}",
            ]
            flags = discord.Embed(
                title=f"Message Flags - {message.id}",
                description="\n".join(flags_text),
                color=message.author.colour
            )
            result["Flags"] = flags

        # noinspection PyTypeChecker
        _mentioned = len(message.channel_mentions) + len(message.role_mentions) + len(message.mentions) > 0
        if _mentioned or message.mention_everyone:
            mentions_text = [
                f"**Everyone Mentioned?** {get_bool_emoji(message.mention_everyone)}",
                f"**Roles Mentioned:** {', '.join(role.name for role in message.role_mentions)}",
                f"**Channels Mentioned:** {', '.join(channel.mention for channel in message.channel_mentions)}",
                f"**Users Mentioned:** {', '.join(user.mention for user in message.mentions)}",
            ]
            mentions = discord.Embed(
                title=f"Message Mentions - {message.id}",
                description="\n".join(mentions_text)[:4096],  # lazy, will make better later
                color=message.author.colour
            )
            result["Mentions"] = mentions

        if message.application:
            icon_url = "https://cdn.discordapp.com/app-icons/{0[id]}/{0[icon]}.png".format(message.application)
            cover_url = "https://cdn.discordapp.com/app-icons/{0[id]}/{0[cover_icon]}.png".format(message.application)
            application_text = [
                f"**ID:** `{message.application['id']}`",
                f"**Name:** {message.application['name']}",
                f"**Description:** {first_line(message.application['description'])}",
                f"**Icon URL:** {hyperlink(icon_url)}",
                f"**Cover Image URL:** {hyperlink(cover_url)}",
            ]
            application = discord.Embed(
                title=f"Message Application - {message.id}",
                description="\n".join(application_text),
                color=message.author.colour
            )
            result["Application Info"] = application

        if message.attachments:
            attachments = discord.Embed(
                title=f"Message Attachments - {message.id}",
                description=f"Direct takes you to the CDN, which is faster, or "
                            f"proxy takes you to the alternative URL, which hangs around a bit after an attachment is"
                            f" deleted.",
                color=message.author.colour
            )
            for attachment in message.attachments[:25]:
                attachments.add_field(
                    name=attachment.filename,
                    value=f"{hyperlink(attachment.url, '**[Direct]**')} | "
                          f"{hyperlink(attachment.proxy_url, '**[Proxy]**')}\n"
                          f"**Size:** {humanise_bytes(attachment.size)}\n"
                          f"**Height:** {attachment.height or 'N/A'}\n"
                          f"**Width:** {attachment.width or 'N/A'}\n"
                          f"**Content type:** {attachment.content_type}\n"
                )
            result["Attachments"] = attachments

        if message.embeds:
            embeds = discord.Embed(
                title=f"Message Embeds - {message.id}",
                colour=message.author.colour
            )
            for embed in message.embeds[:25]:
                embed_lines = [
                    f"**Type:** {embed.type}",
                    f"**Colour:** {(embed.colour or discord.Colour.default()).value:#06x}",
                    f"**Fields:** {len(embed.fields)}/25",
                    f"**Provider:** {embed.provider.name if embed.provider else 'N/A'}",
                    f"**Timestamp:** {embed.timestamp.isoformat() if embed.timestamp else 'N/A'}",
                ]
                if embed.image:
                    embed_lines.append(f"**Image URL:** {hyperlink(embed.image.proxy_url)}")
                if embed.thumbnail:
                    embed_lines.append(f"**Thumbnail URL:** {hyperlink(embed.thumbnail.proxy_url)}")
                if embed.url:
                    embed_lines.append(f"**URL:** {hyperlink(embed.url)}")
                if embed.author:
                    embed_lines.append("**Author:**")
                    embed_lines.append(f"* **Name:** {embed.author.name}")
                    if embed.author.url:
                        embed_lines.append(f"* **URL:** {hyperlink(embed.author.url)}")
                    if embed.author.icon_url:
                        embed_lines.append(f"* **Icon URL:** {hyperlink(embed.author.icon_url)}")
                if embed.footer:
                    embed_lines.append("**Footer:**")
                    embed_lines.append(f"* **Text:** {embed.footer.text}")
                    if embed.footer.icon_url:
                        embed_lines.append(f"* **Icon URL:** {hyperlink(embed.footer.icon_url)}")

                embeds.add_field(
                    name=embed.title or "No title",
                    value="\n".join(embed_lines),
                )

            result["Embeds"] = embeds

        return result

    @commands.message_command(name="Message Info")
    async def message_info(self, ctx: discord.ApplicationContext, message: discord.Message):
        """Get information about a message."""
        await ctx.defer(ephemeral=True)

        embeds = await self.get_message_info(message)
        await ctx.respond(
            embed=embeds["Overview"],
            view=GenericLabelledEmbedView(ctx, **embeds),
            ephemeral=True
        )


def setup(bot: commands.Bot):
    bot.add_cog(MessageInfoCog(bot))
