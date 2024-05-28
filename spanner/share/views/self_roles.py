import asyncio
import os
from enum import IntEnum

import discord

from spanner.share.database import SelfRoleMenu


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


class CreateSelfRolesRoleSelect(discord.ui.Select):
    def __init__(self, me: discord.Member, user: discord.Member, mode: int = 0):
        # 0 = add
        # 1 = remove
        # 2 = edit
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
        await interaction.followup.send(f"\N{WHITE HEAVY CHECK MARK} Roles {word}:\n" + "\n".join(ra), ephemeral=True)
        self.view.stop()


class CreateSelfRolesMasterView(discord.ui.View):
    def __init__(self, ctx: discord.ApplicationContext, roles: list[discord.Role] = None, name: str = None):
        super().__init__(timeout=300, disable_on_timeout=True)
        self.ctx = ctx
        self.roles = set(roles) if roles else set()
        self.name = name or f"New Self-Role Menu {os.urandom(3).hex()}"

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
        # TODO: implement name change modal
        await interaction.response.defer(invisible=True)
        self.name = os.urandom(3).hex()
        await interaction.edit_original_response(embed=self.embed(), view=self)

    @discord.ui.button(
        label="Add role", custom_id="add_role", style=discord.ButtonStyle.green, emoji="\U00002795", row=1
    )
    async def create_self_role_menu(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        select = CreateSelfRolesRoleSelect(interaction.guild.me, interaction.user)
        view = discord.ui.View(select, timeout=180, disable_on_timeout=True)
        await interaction.followup.send("Select the roles to add (1-25)", view=view, ephemeral=True)
        await view.wait()
        v: list[discord.Role] = select.values
        self.roles.update(set(v))
        self.update_ui()
        await interaction.edit_original_response(embed=self.embed(), view=self)

    @discord.ui.button(label="Edit role", custom_id="edit_role", emoji="\U0001f501", row=1)
    async def edit_role(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        select = CreateSelfRolesRoleSelect(interaction.guild.me, interaction.user, 2)
        view = discord.ui.View(select, timeout=180, disable_on_timeout=True)
        await interaction.followup.send("Select the role to edit", view=view, ephemeral=True)
        await view.wait()
        await interaction.edit_original_response(embed=self.embed(), view=self)

    @discord.ui.button(
        label="Remove role", custom_id="remove_role", style=discord.ButtonStyle.red, emoji="\U00002796", row=1
    )
    async def remove_role(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        select = CreateSelfRolesRoleSelect(interaction.guild.me, interaction.user, 1)
        view = discord.ui.View(select, timeout=180, disable_on_timeout=True)
        await interaction.followup.send("Select the roles to remove (1-25)", view=view, ephemeral=True)
        await view.wait()
        v: list[discord.Role] = select.values
        for role in v:
            self.roles.remove(role)
        self.update_ui()
        await interaction.edit_original_response(embed=self.embed(), view=self)

    @discord.ui.button(label="Save", custom_id="save", style=discord.ButtonStyle.green, emoji="\U0001f4be", row=2)
    async def save(self, _, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Saving is not yet implemented, sorry!")
        self.update_ui()
        self.disable_all_items()
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
