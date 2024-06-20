import asyncio
import os
import logging
from enum import IntEnum
from typing import Iterable, Any, TYPE_CHECKING

import discord
from discord import Interaction

from ..database import SelfRoleMenu, GuildConfig

if TYPE_CHECKING:
    from spanner.bot import CustomBridgeBot


log = logging.getLogger(__name__)


class SelfRoleMenuType(IntEnum):
    NORMAL = 1
    """As many roles can be selected as the user wants"""

    UNIQUE = 2
    """Only one of the roles can be selected at a time"""

    LIMITED = 3
    """A limited number of roles can be selected"""

    STICKY = 4
    """Roles can be selected and deselected, but at least one must be selected"""

    MINIMUM = 5
    """At least N roles must be selected"""

    MINMAX = 6
    """At least N roles must be selected, but no more than M"""


class SelectRolesDropDown(discord.ui.Select):
    def __init__(
        self,
        roles: list[discord.Role],
        menu_type: SelfRoleMenuType,
        user: discord.Member,
        *,
        minimum: int = 0,
        maximum: int = 25,
    ):
        match menu_type:
            case SelfRoleMenuType.NORMAL:
                minimum = 0
                maximum = 25
            case SelfRoleMenuType.UNIQUE:
                minimum = 0
                maximum = 1
            case SelfRoleMenuType.LIMITED:
                # maximum is already set
                pass
            case SelfRoleMenuType.STICKY:
                minimum = 1
            case SelfRoleMenuType.MINIMUM:
                maximum = 25
            case SelfRoleMenuType.MINMAX:
                # Min and Max is already set
                pass

        super().__init__(
            custom_id="dd_%s" % user.id, placeholder="Select your roles", min_values=minimum, max_values=maximum
        )
        self.roles = roles
        self.menu_type = menu_type
        self.user = user

    def add_roles(self):
        self._underlying.options.clear()
        for role in self.roles:
            self.add_option(label=role.name, value=str(role.id), default=role in self.user.roles)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            return

        if self.menu_type == SelfRoleMenuType.UNIQUE:
            await member.remove_roles(*self.roles, reason="Self-role selection - unique (removal)")

        selected_roles = [role for role in self.roles if str(role.id) in self.values]
        if selected_roles:
            await member.add_roles(*selected_roles, reason="Self-role selection")

        await interaction.followup.send_message("\N{WHITE HEAVY CHECK MARK} Roles updated", ephemeral=True)
        self.add_roles()
        await interaction.edit_original_response(view=self.view)


class SelectSelfRolesView(discord.ui.View):
    def __init__(self, roles: list[discord.Role], db: SelfRoleMenu):
        super().__init__(timeout=None)
        self.roles = roles
        self.menu_type = SelfRoleMenuType(db.mode)
        self.db = db

    @discord.ui.button(
        label="Select Roles", custom_id="select_roles", style=discord.ButtonStyle.primary, emoji="\U00002935\U0000fe0f"
    )
    async def select_roles(self, _, interaction: discord.Interaction):
        select = SelectRolesDropDown(
            roles=self.roles, menu_type=self.menu_type, user=interaction.user, maximum=self.db.maximum
        )
        await interaction.response.send_message("Select your roles", view=select, ephemeral=True)

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            meth = interaction.followup.send
        else:
            await interaction.response.defer(ephemeral=True)
            meth = interaction.response.send_message

        await meth(f"An error occurred while processing your request: {error}", ephemeral=True)
        raise error


class CreateRoleSelect(discord.ui.Select):
    def __init__(self, me: discord.Member, user: discord.Member, mode: int = 0):
        # 0 = add
        # 1 = remove
        # 2 = edit
        w = "a role" if mode == 2 else "up to 25 roles"
        super().__init__(
            select_type=discord.ComponentType.role_select,
            placeholder="Select a role to add",
            min_values=0 if mode != 2 else 1,
            max_values=25 if mode != 2 else 1,
        )
        self.me = me
        self.user = user
        self.stop = asyncio.Event()
        self.mode = mode

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        v: list[discord.Role] = self.values
        for role in v:
            if self.user.guild.owner != self.user:
                if role >= self.me.top_role:
                    await interaction.followup.send(
                        f"You cannot add roles ({role.mention}) higher than your top role "
                        f"({self.user.top_role}). Try again.",
                        ephemeral=True,
                    )
                    return
                if role >= self.user.top_role:
                    await interaction.followup.send(
                        f"You cannot add roles ({role.mention}) higher than the user's top role "
                        f"({self.user.top_role}). Try again.",
                        ephemeral=True,
                    )
                    return
                if role.permissions.administrator:
                    await interaction.followup.send(
                        f"You cannot add an administrator role ({role.mention}) for security reasons. Try again.",
                        ephemeral=True,
                    )
                    return
            if role.managed:
                await interaction.followup.send(
                    f"You cannot add a managed role ({role.mention}). Try again.", ephemeral=True
                )
                return
        ra = [f"* {role.mention}" for role in v]
        match self.mode:
            case 0:
                word = "added"
            case 1:
                word = "removed"
            case 2:
                word = "selected"
            case _:
                raise ValueError(f"Invalid mode. Expected 0-2, got {self.mode!r}.")

        await interaction.followup.send(
            f"\N{WHITE HEAVY CHECK MARK} Roles {word}:\n" + "\n".join(ra), ephemeral=True, delete_after=5
        )
        self.view.stop()


class CreateChannelSelect(discord.ui.Select):
    def __init__(
        self,
        me: discord.Member,
        user: discord.Member,
        min_n: int = 1,
        max_n: int = 25,
        channel_types: list[discord.ChannelType] = None,
        can_send: Iterable[Any] = None,
    ):
        channel_types = channel_types or [discord.ChannelType.text]
        w = "channels" if max_n != 1 else "a channel"
        super().__init__(
            select_type=discord.ComponentType.channel_select,
            placeholder="Select " + w,
            min_values=min_n,
            max_values=max_n,
            channel_types=channel_types,
        )
        self.me = me
        self.user = user
        self.stop = asyncio.Event()
        self.can_send = can_send or []

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        v: list[discord.abc.GuildChannel] = self.values
        for channel in v:
            if isinstance(channel, discord.abc.Messageable):
                if not channel.can_send(*self.can_send):
                    return await interaction.followup.send(
                        f"\N{CROSS MARK} I cannot send messages in {channel}. Make sure I have `Send Messages`,"
                        f" `Embed Links`, and `Attach Files`."
                    )

        ra = [f"* {channel.mention}" for channel in v]

        await interaction.followup.send(
            f"\N{WHITE HEAVY CHECK MARK} Channel(s) selected:\n" + "\n".join(ra), ephemeral=True, delete_after=5
        )
        self.view.stop()


class ChangeNameModal(discord.ui.Modal):
    def __init__(self, current: str):
        super().__init__(
            discord.ui.InputText(label="Name", placeholder=current, min_length=1, max_length=32, value=current),
            title="Change self-role menu name",
            timeout=120.0,
        )
        self.current = current

    async def callback(self, interaction: Interaction):
        await interaction.response.defer(invisible=True)

    async def run(self) -> str:
        await self.wait()
        return self.children[0].value or self.current


class PersistentSelfRoleView(discord.ui.View):
    class DropDown(discord.ui.Select):
        def __init__(self, source: discord.Interaction, menu: SelfRoleMenu):
            self.source = source
            self.config = menu
            self.guild_config = menu.guild
            self.real_roles = list(
                filter(
                    lambda r: r and r < source.guild.me.top_role and r != source.guild.default_role,
                    [self.source.guild.get_role(x) for x in self.config.roles],
                )
            )
            self.pre_options = [
                discord.SelectOption(
                    label="@" + role.name, value=str(role.id), description=role.name, default=role in source.user.roles
                )
                for role in self.real_roles
            ]
            super().__init__(
                placeholder="Select up to 25 roles here.",
                min_values=0,
                max_values=len(self.real_roles),
                options=self.pre_options.copy(),
            )

            self.gained: list[discord.Role | None] = []
            self.lost: list[discord.Role | None] = []

        async def callback(self, interaction: Interaction):
            await interaction.response.defer(invisible=True)
            self.disabled = True
            await interaction.edit_original_response(view=self.view)
            for option in self.pre_options:
                if option.value in self.values:
                    # Role was selected.
                    if discord.utils.get(interaction.user.roles, id=int(option.value)):
                        # Already had role
                        pass
                    else:
                        # Did not have role, add it to the pending list
                        self.gained.append(interaction.guild.get_role(int(option.value)))
                else:
                    # Role was de-selected.
                    if discord.utils.get(interaction.user.roles, id=int(option.value)):
                        # Already had role
                        self.lost.append(interaction.guild.get_role(int(option.value)))

            self.lost = list(filter(None, self.lost))
            self.gained = list(filter(None, self.gained))
            self.view.stop()

    def __init__(
        self,
        menu: SelfRoleMenu,
    ):
        super().__init__(timeout=None)
        self.menu = menu

    @discord.ui.button(label="Select self-roles", custom_id="select1", style=discord.ButtonStyle.primary)
    async def select_self_roles(self, _, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        dd = self.DropDown(interaction, self.menu)
        view = discord.ui.View(dd, timeout=300, disable_on_timeout=True)
        m = await interaction.followup.send(view=view, ephemeral=True)
        await view.wait()
        await m.edit(embed=discord.Embed(title="Processing..."), view=None)
        if dd.gained:
            try:
                await interaction.user.add_roles(*dd.gained, reason=f"Self-role menu: {self.menu.name!r}", atomic=False)
            except discord.HTTPException as e:
                await interaction.followup.send(f":warning: Failed to add roles: {e!r}")
                log.error(
                    f"Failed to update self-roles for {interaction.user.id} in {interaction.guild.id}", exc_info=e
                )
        if dd.lost:
            try:
                await interaction.user.remove_roles(
                    *dd.lost, reason=f"Self-role menu: {self.menu.name!r}", atomic=False
                )
            except discord.HTTPException as e:
                await interaction.followup.send(f":warning: Failed to remove roles: {e!r}")
                log.error(
                    f"Failed to update self-roles for {interaction.user.id} in {interaction.guild.id}", exc_info=e
                )

        embed = discord.Embed(title="Self-roles registered!")
        if len(dd.gained) > len(dd.lost):
            embed.colour = discord.Colour.green()
        elif len(dd.gained) == len(dd.lost):
            embed.colour = discord.Colour.blurple()
            embed.set_footer(text="No changes made")
        else:
            embed.colour = discord.Colour.brand_red()

        if dd.gained:
            embed.add_field(name="Roles added:", value=", ".join(x.mention for x in dd.gained))
        if dd.lost:
            embed.add_field(name="Roles removed:", value=", ".join(x.mention for x in dd.lost))
        return await m.edit(embed=embed)


class CreateSelfRolesMasterView(discord.ui.View):
    """
    This is the master view, or the entry point for creating a self role menu.

    It can also be used to edit self role menus.
    """

    def __init__(
        self,
        ctx: discord.ApplicationContext,
        guild_config: GuildConfig,
        roles: list[discord.Role] = None,
        name: str = None,
    ):
        super().__init__(timeout=300, disable_on_timeout=True)
        self.ctx = ctx
        self.roles = set(roles) if roles else set()
        self.name = name or f"New Self-Role Menu {os.urandom(3).hex()}"
        self._name_change_task: asyncio.Task | None = None
        self.guild_config = guild_config

        self.update_ui()

    def sorted_roles(self) -> list[discord.Role]:
        return list(sorted(self.roles))

    def embed(self):
        return discord.Embed(
            title=f"Manage: {self.name}",
            description="Roles to hand out:\n" + ", ".join(role.mention for role in self.sorted_roles()) or "N/A",
            color=discord.Color.blurple(),
        )

    def update_ui(self):
        self.get_item("add_role").disabled = len(self.roles) >= 25
        self.get_item("remove_role").disabled = len(self.roles) == 0
        self.get_item("edit_role").disabled = len(self.roles) == 0

    @discord.ui.button(
        label="Change Name",
        custom_id="change_name",
        style=discord.ButtonStyle.primary,
        emoji="\U0000270f\U0000fe0f",
        row=0,
    )
    async def change_name(self, _, interaction: discord.Interaction):
        if self._name_change_task:
            self._name_change_task.cancel()
        modal = ChangeNameModal(self.name)
        await interaction.response.send_modal(modal)
        try:
            self._name_change_task = asyncio.create_task(modal.run())
            self.name = await self._name_change_task
        except asyncio.CancelledError:
            modal.stop()
            return
        else:
            self._name_change_task = None
        await interaction.edit_original_response(embed=self.embed(), view=self)

    @discord.ui.button(
        label="Add role", custom_id="add_role", style=discord.ButtonStyle.green, emoji="\U00002795", row=1
    )
    async def create_self_role_menu(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        select = CreateRoleSelect(interaction.guild.me, interaction.user)
        view = discord.ui.View(select, timeout=180, disable_on_timeout=True)
        f = await interaction.followup.send("Select the roles to add (1-25)", view=view, ephemeral=True)
        await view.wait()
        await f.delete(delay=0.01)
        v: list[discord.Role] = select.values
        self.roles.update(set(v))
        self.update_ui()
        await interaction.edit_original_response(embed=self.embed(), view=self)

    @discord.ui.button(label="Edit role", custom_id="edit_role", emoji="\U0001f501", row=1)
    async def edit_role(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        select = CreateRoleSelect(interaction.guild.me, interaction.user, 2)
        view = discord.ui.View(select, timeout=180, disable_on_timeout=True)
        f = await interaction.followup.send("Select the role to edit", view=view, ephemeral=True)
        await view.wait()
        await f.delete(delay=0.01)
        await interaction.edit_original_response(embed=self.embed(), view=self)

    @discord.ui.button(
        label="Remove role", custom_id="remove_role", style=discord.ButtonStyle.red, emoji="\U00002796", row=1
    )
    async def remove_role(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        select = CreateRoleSelect(interaction.guild.me, interaction.user, 1)
        view = discord.ui.View(select, timeout=180, disable_on_timeout=True)
        f = await interaction.followup.send("Select the roles to remove (1-25)", view=view, ephemeral=True)
        await view.wait()
        await f.delete(delay=0.01)
        v: list[discord.Role] = select.values
        for role in v:
            self.roles.remove(role)
        self.update_ui()
        await interaction.edit_original_response(embed=self.embed(), view=self)

    @discord.ui.button(label="Save", custom_id="save", style=discord.ButtonStyle.green, emoji="\U0001f4be", row=2)
    async def save(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.update_ui()
        self.disable_all_items()
        await interaction.edit_original_response(embed=self.embed(), view=self)

        channel_view = discord.ui.View(
            CreateChannelSelect(
                interaction.guild.me, interaction.user, 1, 1, [discord.ChannelType.text], [discord.Embed()]
            ),
            disable_on_timeout=True,
        )
        fm = await interaction.followup.send(
            "Where should this self-role be accessible? (A drop-down message will be sent to this channel)",
            view=channel_view,
            ephemeral=True,
        )
        await channel_view.wait()
        channel_view.disable_all_items()
        if not channel_view.children[0].values:
            await fm.edit(content="You did not select any channels.", view=channel_view)
            self.enable_all_items()
            self.update_ui()
            return await interaction.edit_original_response(view=self)
        else:
            await fm.delete(delay=0.01)

        channel: discord.TextChannel = channel_view.children[0].values[0]
        _e = discord.Embed(
            title="Self-role menu: " + self.name,
            description="Press my button to select any/all of the following roles:\n",
            colour=discord.Colour.teal(),
        )
        _e.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)

        selector = await channel.send(
            embed=_e,
        )

        try:
            db_entry = SelfRoleMenu(
                guild=self.guild_config,
                author=interaction.user.id,
                name=self.name,
                channel=selector.channel.id,
                message=selector.id,
                mode=SelfRoleMenuType.NORMAL.value,
                roles=[x.id for x in self.roles],
            )
            await db_entry.save()
        except Exception:
            log.exception(
                f"Failed to save self-role menu to database for {interaction.user.id} in {interaction.guild.id}",
                exc_info=True,
            )
            await selector.delete(delay=0.01)
            return await interaction.followup.send(
                "There was an error saving your self-role menu. Please contact support.",
            )
        v = PersistentSelfRoleView(db_entry)
        await selector.edit(view=v)
        self.ctx.bot.add_view(v, message_id=selector.id)

        await interaction.edit_original_response(embed=self.embed(), view=self)
        self.stop()

    @discord.ui.button(label="Cancel", custom_id="cancel", style=discord.ButtonStyle.red, row=2)
    async def cancel(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.update_ui()
        self.disable_all_items()
        await interaction.edit_original_response(embed=self.embed(), view=self)
        self.stop()

    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        if interaction.response.is_done():
            meth = interaction.followup.send
        else:
            await interaction.response.defer(ephemeral=True)
            meth = interaction.response.send_message

        await meth(f"An error occurred while processing your request: {error}", ephemeral=True)
        raise error
