#!/usr/bin/env python3
# vim: set expandtab tabstop=4 shiftwidth=4:

# Copyright (C) 2024 Christopher J. Kucera
#
# animalwellsave is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import os
import sys
import enum
import math
import argparse
import textwrap
import itertools
import collections
from . import __version__, set_debug
from .savegame import Savegame, Equipped, Equipment, Inventory, Egg, EggDoor, Bunny, Teleport, \
        QuestState, FlameState, CandleState, KangarooShardState, CatStatus, \
        Unlockable, ManticoreState, Progress, ElevatorDisabled, BigStalactiteState, \
        has_image_support


class EnumSetAction(argparse.Action):
    """
    Argparse Action to set Enum members as the arg `choices`, adding them
    to a set as they are chosen by the user.  Also hardcodes an `all`
    choice which can be used to add all available Enum members to the
    argument set.

    When using this action, `choices` can be populated as a sequence of
    enum members, if you want to only allow a *subset* of the enum.  (This
    is useful for our QuestState enum, which includes a bunch of different
    kinds of data.)

    Derived partially from https://stackoverflow.com/a/70124136/2013126
    """

    def __init__(self, **kwargs):

        # Grab the specified argument type and ensure it's an Enum
        enum_type = kwargs.pop('type', None)
        if enum_type is None:
            raise ValueError('type must be assigned an Enum when using EnumSetAction')
        if not issubclass(enum_type, enum.Enum):
            raise TypeError('type must be an Enum when using EnumSetAction')

        # Set the available choices, including the "all" option
        if 'choices' in kwargs:
            self._enum_all_values = kwargs['choices']
        else:
            self._enum_all_values = enum_type
        kwargs['choices'] = tuple(e.name.lower() for e in self._enum_all_values) + ('all',)

        # Finish up
        super().__init__(**kwargs)
        self._enum = enum_type

    def __call__(self, parser, namespace, this_value, option_string):

        # Force the attribute into a set, if it isn't already
        arg_value = getattr(namespace, self.dest)
        if not isinstance(arg_value, set):
            arg_value = set()

        # Convert our new arg to the proper enum member, and add to the set
        if isinstance(this_value, str):
            uppercase = this_value.upper()
            if uppercase == 'ALL':
                for item in self._enum_all_values:
                    arg_value.add(item)
            else:
                this_value = self._enum[uppercase]
                arg_value.add(this_value)
            setattr(namespace, self.dest, arg_value)
        elif value is None:
            raise parser.error(f'You need to pass a value after {option_string}!')
        else:
            raise parser.error(f'Invalid data passed to {option_string}')


class EnumChoiceAction(argparse.Action):
    """
    Argparse Action to set an Enum choice as the arg `choices`, setting
    just a single value as chosen by the user.

    When using this action, `choices` can be populated as a sequence of
    enum members, if you want to only allow a *subset* of the enum.

    Derived partially from https://stackoverflow.com/a/70124136/2013126
    """

    def __init__(self, **kwargs):

        # Grab the specified argument type and ensure it's an Enum
        enum_type = kwargs.pop('type', None)
        if enum_type is None:
            raise ValueError('type must be assigned an Enum when using EnumChoiceAction')
        if not issubclass(enum_type, enum.Enum):
            raise TypeError('type must be an Enum when using EnumChoiceAction')

        # Set the available choices, including the "all" option
        if 'choices' in kwargs:
            self._enum_all_values = kwargs['choices']
        else:
            self._enum_all_values = enum_type
        kwargs['choices'] = tuple(e.name.lower() for e in self._enum_all_values)

        # Finish up
        super().__init__(**kwargs)
        self._enum = enum_type

    def __call__(self, parser, namespace, this_value, option_string):

        # Convert our new arg to the proper enum member and store it
        if isinstance(this_value, str):
            setattr(namespace, self.dest, self._enum[this_value.upper()])
        elif value is None:
            raise parser.error(f'You need to pass a value after {option_string}!')
        else:
            raise parser.error(f'Invalid data passed to {option_string}')


class CoordAction(argparse.Action):
    """
    Argparse action to support passing in a coordinate pair, separated by a comma.
    This will be stored as a namedtuple with `x` and `y` attributes.
    """

    def __call__(self, parser, namespace, value, option_string):

        if ',' not in value:
            raise parser.error(f'{option_string} requires two numbers separated by a comma')
        try:
            parts = [int(p) for p in value.split(',')]
        except ValueError:
            raise parser.error(f'{option_string} requires numbers on both sides of the comma')
        if len(parts) != 2:
            raise parser.error(f'{option_string} only supports two numbers')
        Point = collections.namedtuple('Point', ['x', 'y'])
        setattr(namespace, self.dest, Point(*parts))


def delete_common_set_items(set1, set2):
    """
    Deletes any items in both set1 and set2 which appear in both sets.
    Used to avoid doing flip-flopping when the same value is specified
    in both an `enable` and `disable` option.  (Which presumably could
    happen when using `all` with one of those and then a specific
    override on the other.)
    """
    if set1 is None or set2 is None:
        return
    common = set1 & set2
    set1 -= common
    set2 -= common


def check_file_overwrite(args, filename):
    """
    Checks to see if a file that we intend to write to exists.  If the --force
    option has been specified, there will only be a printed alert about the
    overwrite.  Otherwise, we will ask the user for confirmation.

    Will return `True` if we should go ahead with the save, or `False`
    otherwise.
    """
    do_write = True
    if os.path.exists(filename):
        if args.force:
            print('NOTICE: Overwriting existing file!')
        else:
            do_write = False
            response = input(f'WARNING: Filename "{filename}" already exists.  Overwrite? (y/N)> ')
            if response.strip().lower()[:1] == 'y':
                do_write = True
    return do_write


def column_chunks(l, columns):
    """
    Divide up a given list `l` into the specified number of
    `columns`.  Yields each column in turn, as a list.  (Does
    *not* do any padding.)
    """
    length = len(l)
    if length == 0:
        yield []
    else:
        n = math.ceil(length/columns)
        for i in range(0, length, n):
            yield l[i:i + n]


def print_columns(
        data,
        *,
        minimum_lines=12,
        max_width=79,
        indent='   ',
        padding='  ',
        prefix='- ',
        columns=None,
        ):
    """
    Function to take a list of `data` and output in columns, if we can.

    `minimum_lines` determines how many items there should be before we
    start outputting in columns.

    `max_width` determines how wide the output is allowed to be.

    `indent` is the start-of-line indentation that will be prefixed on
    every line (and is taken into account when computing versus
    `max_width`).

    `padding` is the padding that will be printed between each column.

    `prefix` is a string prefix which will be prefixed on each item to
    be printed.

    `columns` can be used to force a certain number of columns without
    doing any width checking.
    """
    if len(data) == 0:
        return
    str_data = [f'{prefix}{item}' for item in data]
    force_output = False
    if columns is None:
        num_columns = math.ceil(len(str_data)/minimum_lines)
    else:
        num_columns = columns
        force_output = True

    # There might be a better way to do this, but what we're doing is starting
    # at our "ideal" column number, seeing if it fits in our max_width, and
    # then decreasing by one until it actually fits.  We could, instead, take
    # a look at the max length overall and base stuff on that, or take an
    # average and hope for the best, but the upside is that this *will* give
    # us the most number of columns we can fit for the data, if need be.
    while True:
        max_widths = [0]*num_columns
        cols = list(column_chunks(str_data, num_columns))
        for idx, col in enumerate(cols):
            for item in col:
                max_widths[idx] = max(max_widths[idx], len(item))
        total_width = len(indent) + sum(max_widths) + (len(padding)*(num_columns-1))
        if force_output or total_width <= max_width or num_columns == 1:
            format_str = '{}{}'.format(
                    indent,
                    padding.join([f'{{:<{l}}}' for l in max_widths]),
                    )
            for row_data in itertools.zip_longest(*cols, fillvalue=''):
                print(format_str.format(*row_data))
            break
        else:
            num_columns -= 1


def main():
    """
    Main CLI app.  Returns `True` if a file was saved out, or `False`
    otherwise.
    """

    parser = argparse.ArgumentParser(
            description=f'CLI Animal Well Savegame Editor v{__version__}',
            )

    ###
    ### Control options
    ###

    control = parser.add_argument_group('Control Arguments', 'General control of the editing process')

    control.add_argument('-i', '--info',
            action='store_true',
            help='Show known information about the save',
            )

    control.add_argument('-v', '--verbose',
            action='store_true',
            help='Include more information in the info view, including missing items (where possible)',
            )

    control.add_argument('-d', '--debug',
            action='store_true',
            help="""
                Show debugging output, which will show the offsets (both absolute and relative) for
                all data in the savegame we know about.  This info will be written to stderr.
                """,
            )

    control.add_argument('-1', '--single-column',
            dest='single_column',
            action='store_true',
            help="""
                By default, info output will use columns to show longer lists of data.  This option
                will force the output to have one item per line, instead
                """,
            )

    control.add_argument('--fix', '--fix-checksum',
            action='store_true',
            dest='fix_checksum',
            help='Update the savegame checksum, even if no other edit actions have been specified.',
            )

    control.add_argument('--invalid-checksum',
            action='store_true',
            help='Write an intentionally-incorrect checksum to the savefile',
            )

    control.add_argument('-s', '--slot',
            choices=[0, 1, 2, 3],
            type=int,
            help='Operate on the specified slot (specify 0 for "all slots")',
            )

    control.add_argument('--import', '--import-slot',
            type=str,
            dest='import_slot',
            metavar='FILENAME',
            help="""
                Import slot data from a standalone file into the specified slot.  The file must be
                exactly 159,760 bytes, though no other checking is done for validity.  The import
                will be done prior to any other specified actions.
                """,
            )

    control.add_argument('--export', '--export-slot',
            type=str,
            dest='export_slot',
            metavar='FILENAME',
            help="""
                Export the specified slot data to a standalone file.  The file will not be loadable
                by Animal Well directly, but can be imported into a different save.  The export will
                be done after any other specified actions.
                """,
            )

    control.add_argument('-f', '--force',
            action='store_true',
            help='When exporting slot data, do not prompt to confirm overwriting a file',
            )

    ###
    ### Global Options
    ###

    global_options = parser.add_argument_group('Globals', 'Options which apply to the entire savegame')

    global_options.add_argument('--frame-seed',
            type=int,
            help='Set the frame seed in the save header (most obvious effect is the bunny mural fragment shown)',
            )

    global_options.add_argument('--globals-enable',
            type=Unlockable,
            action=EnumSetAction,
            help="Enable the specified global unlockable.  Can be specified more than once, or use 'all' to enable all",
            )

    global_options.add_argument('--globals-disable',
            type=Unlockable,
            action=EnumSetAction,
            help="Disable the specified global unlockable.  Can be specified more than once, or use 'all' to disable all",
            )

    ###
    ### Player Status
    ###

    player = parser.add_argument_group('Player', 'Options to modify the direct player state')

    player.add_argument('--health',
            type=int,
            help='Sets health (number of hearts)',
            )

    player.add_argument('--gold-hearts',
            type=int,
            help='Sets the number of gold hearts',
            )

    player.add_argument('--spawn',
            type=str,
            metavar='X,Y',
            action=CoordAction,
            help='Room coordinates to spawn in.  Specify two numbers with a comma inbetwen them, such as "11,11" for the main hallway.',
            )

    player.add_argument('--steps',
            type=int,
            help="Set the number of steps taken",
            )

    player.add_argument('--deaths',
            type=int,
            help="Set the number of deaths",
            )

    player.add_argument('--saves',
            type=int,
            help="Set the number of times-saved",
            )

    player.add_argument('--bubbles-popped',
            type=int,
            help="Set the number of bubbles popped",
            )

    player.add_argument('--berries-eaten-while-full',
            type=int,
            help="Set the number of berries eaten while full",
            )

    ticks = player.add_mutually_exclusive_group()

    ticks.add_argument('--ticks',
            type=int,
            help="Set the number of ticks that have elapsed in-game (by both internal measures)",
            )

    ticks.add_argument('--ticks-copy-ingame',
            action='store_true',
            help="Overwrite the with-paused tick counter to just ingame time",
            )

    wings = player.add_mutually_exclusive_group()

    wings.add_argument('--wings-enable',
            action='store_true',
            help='Enable Wings / Flying Mode',
            )

    wings.add_argument('--wings-disable',
            action='store_true',
            help='Disable Wings / Flying Mode',
            )

    ###
    ### Inventory
    ###

    inventory = parser.add_argument_group('Inventory', 'Options to alter the player\'s inventory')

    inventory.add_argument('--firecrackers',
            type=int,
            help="Set the number of firecrackers in your inventory.  Will unlock the Firecracker equipment as well, if not already active",
            )

    inventory.add_argument('--keys',
            type=int,
            help="Set the number of keys in your inventory",
            )

    inventory.add_argument('--matches',
            type=int,
            help="Set the number of matches in your inventory",
            )

    inventory.add_argument('--nuts',
            type=int,
            help="Set the number of nuts stolen from squirrels",
            )

    inventory.add_argument('--equip-enable',
            type=Equipment,
            action=EnumSetAction,
            help="Enable the specified equipment.  Can be specified more than once, or use 'all' to enable all",
            )

    inventory.add_argument('--equip-disable',
            type=Equipment,
            action=EnumSetAction,
            help="Disable the specified equipment.  Can be specified more than once, or use 'all' to disable all",
            )

    inventory.add_argument('--inventory-enable',
            type=Inventory,
            action=EnumSetAction,
            help="Enable the specified inventory item.  Can be specified more than once, or use 'all' to enable all",
            )

    inventory.add_argument('--inventory-disable',
            type=Inventory,
            action=EnumSetAction,
            help="Disable the specified inventory item.  Can be specified more than once, or use 'all' to disable all",
            )

    inventory.add_argument('--dont-fix-disc-state',
            dest='fix_disc_state',
            action='store_false',
            help="""
                When enabling the Disc (in equipment) or Mock Disc (in inventory), this
                utility will attempt to normalize the game's quest variables to prevent
                ghost dog spawning and other progression weirdness.  To avoid making these
                corrections, specify this argument.  Without this option, the utility will
                *not* allow you to enable both the Disc and Mock Disc at the same time,
                since there is no valid game state with that combination.  Note that the
                quest state alterations happen *after* this fix, so you can also manually
                set those flags with that option.
                """,
            )

    inventory.add_argument('--prefer-disc-shrine-state',
            action='store_true',
            help="""
                When enabling the Disc equipment, with fixing disc state enabled (see
                `--dont-fix-disc-state` option above), by default this utility will set
                the game state to having swapped the Mock Disc at the first statue.  To
                instead fix the state to having moved the Mock Disc to the M. Disc
                Shrine, specify this option.
                """,
            )

    inventory.add_argument('--map-enable',
            type=QuestState,
            action=EnumSetAction,
            choices=[
                QuestState.UNLOCK_MAP,
                QuestState.UNLOCK_STAMPS,
                QuestState.UNLOCK_PENCIL,
                ],
            help="Enable the specified map feature.  Can be specified more than once, or use 'all' to enable all",
            )

    inventory.add_argument('--upgrade-wand',
            action='store_true',
            help='Upgrade the B. Wand to B.B. Wand',
            )

    inventory.add_argument('--downgrade-wand',
            action='store_true',
            help='Downgrade the B.B. Wand to B. Wand',
            )

    egg65 = inventory.add_mutually_exclusive_group()

    egg65.add_argument('--egg65-enable',
            action='store_true',
            help='Enable Egg 65',
            )

    egg65.add_argument('--egg65-disable',
            action='store_true',
            help='Disable Egg 65',
            )

    cring = inventory.add_mutually_exclusive_group()

    cring.add_argument('--cring-enable',
            action='store_true',
            help="Enable Cheater's Ring",
            )

    cring.add_argument('--cring-disable',
            action='store_true',
            help="Disable Cheater's Ring",
            )

    ###
    ### Progress/Quests
    ###

    progress = parser.add_argument_group('Progress/Quests', 'Options to alter the state of "quests" and general progress')

    progress.add_argument('--progress-enable',
            type=Progress,
            action=EnumSetAction,
            help="Enable the specified progress flag.  Can be specified more than once, or use 'all' to enable all",
            )

    progress.add_argument('--progress-disable',
            type=Progress,
            action=EnumSetAction,
            help="Disables the specified progress flag.  Can be specified more than once, or use 'all' to disable all",
            )

    disc = progress.add_mutually_exclusive_group()

    disc.add_argument('--move-disc-to-shrine',
            action='store_true',
            help="""
                Moves the Mock Disc to the Shrine, if it is not there already.  This will only
                activate if the player has the regular disc, does not have the mock disc, and
                the mock disc is currently in the Dog Head Statue.  Not intended to be used
                in conjunction with arguments which alter Disc and Mock Disc inventory states.
                """,
            )

    disc.add_argument('--move-disc-to-statue',
            action='store_true',
            help="""
                Moves the Mock Disc to the Dog Head Statue, if it is not there already.  This will
                only activate if the player has the regular disc, does not have the mock disc,
                and the mock disc is currently in the Shrine.  Not intended to be used
                in conjunction with arguments which alter Disc and Mock Disc inventory states.
                """,
            )

    progress.add_argument('--cats-free',
            type=CatStatus,
            action=EnumSetAction,
            help="Frees the specified cats, and/or the wheel reward cage.  Can be specified more than once, or use 'all' to free all",
            )

    progress.add_argument('--cats-cage',
            type=CatStatus,
            action=EnumSetAction,
            help="Re-cages the specified cats, and/or the wheel reward cage.  Can be specified more than once, or use 'all' to cage all",
            )

    progress.add_argument('--kangaroo-room',
            type=int,
            choices=[0, 1, 2, 3, 4],
            help="""
                Defines the next room that the kangaroo will spawn in.  The kangaroo will end up
                in an immediately-hostile state in the chosen room.  Coordindates: 0: (6, 6), 1:
                (9, 11), 2: (12, 11), 3: (9, 13), 4: (16, 16)
                """,
            )

    kshard = progress.add_mutually_exclusive_group()

    kshard.add_argument('--kshard-collect',
            type=int,
            choices=[1, 2, 3],
            help="""
                Sets the total number of collected K. Shards to the given number.
                Will remove existing inserted K. Shards if any were present.
                """,
            )

    kshard.add_argument('--kshard-insert',
            type=int,
            choices=[1, 2, 3],
            help="""
                Sets the total number of inserted K. Shards to the given number.
                Will remove existing collected K. Shards if any were present.
                """,
            )

    smedal = progress.add_mutually_exclusive_group()

    smedal.add_argument('--s-medal-insert',
            action='store_true',
            help='Mark the S. Medal as inserted (to open the passageway it was blocking)',
            )

    smedal.add_argument('--s-medal-remove',
            action='store_true',
            help='Mark the S. Medal as not inserted (this will not put the S. Medal in your inventory)',
            )

    emedal = progress.add_mutually_exclusive_group()

    emedal.add_argument('--e-medal-insert',
            action='store_true',
            help='Mark the E. Medal as inserted (to open the passageway it was blocking)',
            )

    emedal.add_argument('--e-medal-remove',
            action='store_true',
            help='Mark the E. Medal as not inserted (this will not put the E. Medal in your inventory)',
            )

    progress.add_argument('--teleport-enable',
            type=Teleport,
            action=EnumSetAction,
            help="Enable the specified teleport.  Can be specified more than once, or use 'all' to enable all",
            )

    progress.add_argument('--teleport-disable',
            type=Teleport,
            action=EnumSetAction,
            help="Disables the specified teleport.  Can be specified more than once, or use 'all' to enable all",
            )

    mural = progress.add_mutually_exclusive_group()

    mural.add_argument('--mural-clear',
            action='store_true',
            help='Clear all mural pixels to the background color',
            )

    mural.add_argument('--mural-default',
            action='store_true',
            help='Revert the mural to its default state',
            )

    mural.add_argument('--mural-solved',
            action='store_true',
            help='Set the mural to its solved state',
            )

    mural2 = progress.add_mutually_exclusive_group()

    mural2.add_argument('--mural-raw-export',
            type=str,
            metavar='FILENAME',
            help='Export the raw mural data to the specified file',
            )

    mural2.add_argument('--mural-raw-import',
            type=str,
            metavar='FILENAME',
            help='Import the specified file as raw mural data',
            )

    if has_image_support:

        mural2.add_argument('--mural-image-export',
                type=str,
                metavar='FILENAME',
                help='Export the bunny mural data as an image file (should be PNG or GIF)',
                )

        mural2.add_argument('--mural-image-import',
                type=str,
                metavar='FILENAME',
                help="""
                    Import the specified image file into the bunny mural data.  The
                    image must be 40x20 and indexed with only four colors.  (The
                    most common file formats to support indexed color are PNG and GIF.
                    A JPEG will not work since those can't be indexed.)
                    """,
                )

    progress.add_argument('--flame-collect',
            type=str,
            choices=['b', 'p', 'v', 'g', 'all'],
            action='append',
            help="Mark the specified flames as collected (but not placed in the pedestals).  Can be specified more than once, or use 'all' to do all at once",
            )

    progress.add_argument('--flame-use',
            type=str,
            choices=['b', 'p', 'v', 'g', 'all'],
            action='append',
            help="Mark the specified flames as used (but not placed in the pedestals).  Can be specified more than once, or use 'all' to do all at once",
            )

    progress.add_argument('--blue-manticore',
            type=ManticoreState,
            action=EnumChoiceAction,
            help="Set the Blue Manticore state",
            )

    progress.add_argument('--red-manticore',
            type=ManticoreState,
            action=EnumChoiceAction,
            help="Set the Red Manticore state",
            )

    torus = progress.add_mutually_exclusive_group()

    torus.add_argument('--torus-enable',
            action='store_true',
            help='Enable Teleportation Torus',
            )

    torus.add_argument('--torus-disable',
            action='store_true',
            help='Disable Teleportation Torus',
            )

    for boss, extra_defeat, extra_respawn in [
            ('chameleon', None, None),
            ('bat', None, None),
            ('ostrich',
                """This affects both ostrich bosses in the game.  Will additionally
                    stop the ostrich-controlled platforms""",
                """This affects both ostrich bosses in the game.  Will set the
                    wheel ostrich to its pre-freed state, restart the platforms, and
                    additionally un-press the purple button so that the ostrich
                    doesn't immediately free itself again.""",
                ),
            ('eel', None, 'Will be set to its pre-awakened state'),
            ]:

        capitalized = boss.replace('-', ' ').title()

        bossgroup = progress.add_mutually_exclusive_group()

        if extra_defeat:
            extra = f'.  {extra_defeat}'
        else:
            extra = ''
        bossgroup.add_argument(f'--{boss}-defeat',
                action='store_true',
                help=f'Mark the {capitalized} boss as defeated{extra}',
                )

        if extra_respawn:
            extra = f'.  {extra_respawn}'
        else:
            extra = ''
        bossgroup.add_argument(f'--{boss}-respawn',
                action='store_true',
                help=f'Respawn the {capitalized} boss{extra}',
                )

    bossgroup = progress.add_mutually_exclusive_group()

    bossgroup.add_argument('--bosses-defeat',
            action='store_true',
            help="""
                Mark all bosses (except for Manticore) as defeated.  Will override any
                previous defeat/respawn arguments for bosses.
                """,
            )

    bossgroup.add_argument('--bosses-respawn',
            action='store_true',
            help="""
                Respawn all bosses (except for Manticore).  Will override any previous
                defeat/respawn arguments for bosses.
                """,
            )

    progress.add_argument('--quest-state-enable',
            type=QuestState,
            action=EnumSetAction,
            help="""
                Enable the specified quest state flag.  These are generally not
                recommended to mess with by hand; practically anything you can
                alter in here can be done with dedicated arguments.  Messing with
                them directly could cause strange behavior ingame.  Caveat emptor!
                Can be specified more than once, or use 'all' to enable all.
                """,
            )

    progress.add_argument('--quest-state-disable',
            type=QuestState,
            action=EnumSetAction,
            help="""
                Disable the specified quest state flag.  These are generally not
                recommended to mess with by hand; practically anything you can
                alter in here can be done with dedicated arguments.  Messing with
                them directly could cause strange behavior ingame.  Caveat emptor!
                Can be specified more than once, or use 'all' to disable all.
                """,
            )

    ###
    ### Map Options
    ###

    map_options = parser.add_argument_group('Map Edits', 'Options to edit the state of the map')

    map_options.add_argument('--egg-enable',
            type=Egg,
            action=EnumSetAction,
            help="Enable the specified egg.  Can be specified more than once, or use 'all' to enable all",
            )

    map_options.add_argument('--egg-disable',
            type=Egg,
            action=EnumSetAction,
            help="Disables the specified egg.  Can be specified more than once, or use 'all' to disable all",
            )

    map_options.add_argument('--bunny-enable',
            type=Bunny,
            action=EnumSetAction,
            help="Enable the specified bunny.  Can be specified more than once, or use 'all' to enable all",
            )

    map_options.add_argument('--bunny-disable',
            type=Bunny,
            action=EnumSetAction,
            help="Disable the specified bunny.  Can be specified more than once, or use 'all' to disable all",
            )

    map_options.add_argument('--illegal-bunny-clear',
            action='store_true',
            help="Clear any 'illegal' bunnies from the slot, so that BDTP can be solved again.",
            )

    map_options.add_argument('--respawn-consumables',
            action='store_true',
            help="Respawn map consumables (fruit and firecrackers)",
            )

    ghost = map_options.add_mutually_exclusive_group()

    ghost.add_argument('--clear-ghosts',
            action='store_true',
            help="Clear all ghosts from the map",
            )

    ghost.add_argument('--respawn-ghosts',
            action='store_true',
            help="Respawn ghosts to the map",
            )

    map_options.add_argument('--respawn-squirrels',
            action='store_true',
            help="Respawn squirrels to the map",
            )

    buttons = map_options.add_mutually_exclusive_group()

    buttons.add_argument('--buttons-press',
            action='store_true',
            help="Sets all buttons in the game to 'pressed' state",
            )

    buttons.add_argument('--buttons-reset',
            action='store_true',
            help="Sets all buttons in the game to their default non-pressed state",
            )

    doors = map_options.add_mutually_exclusive_group()

    doors.add_argument('--doors-open',
            action='store_true',
            help="""
                Opens all button/reservoir doors in the game.  Does NOT open doors which have other
                specific requirements (egg doors, doors which require keys, etc).
                """,
            )

    doors.add_argument('--doors-close',
            action='store_true',
            help="""
                Closes all button/reservoir doors in the game.  Does NOT close doors which have other
                specific requirements (egg doors, doors which require keys, etc).  Note that if
                the door's opening conditions are still met (buttons pressed, etc), the doors will re-open.
                """,
            )

    locked = map_options.add_mutually_exclusive_group()

    locked.add_argument('--lockable-unlock',
            action='store_true',
            help='Unlock all lockable doors in the game (of the sort which are unlocked with a generic key)',
            )

    locked.add_argument('--lockable-lock',
            action='store_true',
            help='Lock all lockable doors in the game (of the sort which are unlocked with a generic key)',
            )

    map_options.add_argument('--eggdoor-open',
            type=EggDoor,
            action=EnumSetAction,
            help="Opens the specified egg doors in the egg chamber.  Can be specified more than once, or use 'all' to open all",
            )

    map_options.add_argument('--eggdoor-close',
            type=EggDoor,
            action=EnumSetAction,
            help="Closes the specified egg doors in the egg chamber.  Can be specified more than once, or use 'all' to close all",
            )

    walls = map_options.add_mutually_exclusive_group()

    walls.add_argument('--walls-open',
            action='store_true',
            help='Opens all moveable walls in the game',
            )

    walls.add_argument('--walls-close',
            action='store_true',
            help='Close all moveable walls in the game',
            )

    map_options.add_argument('--clear-invalid-walls',
            action='store_true',
            help="""
                Use of the Cheater's Ring in the game can allow the player to open walls which
                are not ordinarily openable, which can end up leading to broken savefiles.  This
                option will clear out those opened-wall records.  This will also un-press the
                associated pink buttons so that the walls don't re-open.
                """,
            )

    house = map_options.add_mutually_exclusive_group()

    house.add_argument('--house-open',
            action='store_true',
            help='Open the house/office/closet doors',
            )

    house.add_argument('--house-close',
            action='store_true',
            help='Close the house/office/closet doors',
            )

    chests = map_options.add_mutually_exclusive_group()

    chests.add_argument('--chests-open',
            action='store_true',
            help="""
                Opens all chests in the game.  Note that merely opening chests does NOT give you the
                item contained within the chest.  This option is probably of little use to anyone.
                """,
            )

    chests.add_argument('--chests-close',
            action='store_true',
            help='Closes all chests in the game, allowing their contents to be re-looted',
            )

    map_options.add_argument('--candles-enable',
            type=CandleState,
            action=EnumSetAction,
            help="Light the specified candles.  Can be specified more than once, or use 'all' to enable all",
            )

    map_options.add_argument('--candles-disable',
            type=CandleState,
            action=EnumSetAction,
            help="Blows out the specified candles.  Can be specified more than once, or use 'all' to enable all",
            )

    map_options.add_argument('--solve-cranks',
            action='store_true',
            help="""
                Sets crank status to the 'solved' state for cranks which are involved in puzzles (ie: reservoir
                bounce platforms and the sine wave puzzle)
                """,
            )

    reservoirs = map_options.add_mutually_exclusive_group()

    reservoirs.add_argument('--reservoirs-fill',
            action='store_true',
            help='Fills up all water reservoirs in the game',
            )

    reservoirs.add_argument('--reservoirs-empty',
            action='store_true',
            help='Empties all water reservoirs in the game',
            )

    detonators = map_options.add_mutually_exclusive_group()

    detonators.add_argument('--detonators-activate',
            action='store_true',
            help='Activates all detonators on the map, opening shortcut passages',
            )

    detonators.add_argument('--detonators-rearm',
            action='store_true',
            help="""
                Re-arms all detonators on the map.  Note that you will likely need to also use
                --respawn-destroyed-tiles in order to seal up the actual passages.
                """,
            )

    map_options.add_argument('--respawn-destroyed-tiles',
            action='store_true',
            help='Respawn any destroyed tiles on the map (such as through detonators, top blocks, Manticore glass)',
            )

    map_options.add_argument('--big-stalactites-state',
            type=BigStalactiteState,
            action=EnumChoiceAction,
            help="Set all big stalactites to the chosen state",
            )

    deposits = map_options.add_mutually_exclusive_group()

    deposits.add_argument('--small-deposits-break',
            action='store_true',
            help='Breaks all small stalactites/stalagmites/icicles on the map',
            )

    deposits.add_argument('--small-deposits-respawn',
            action='store_true',
            help='Respawn all small stalactites/stalagmites/icicles on the map',
            )

    ###
    ### Minimap Options
    ###

    minimap = parser.add_argument_group('Minimap', 'Options to alter the state of the minimap')

    minimap.add_argument('--reveal-map',
            action='store_true',
            help='Reveals the entire map on the minimap',
            )

    minimap.add_argument('--clear-map',
            action='store_true',
            help='Clears the entire map on the minimap',
            )

    minimap.add_argument('--clear-pencil',
            action='store_true',
            help='Clears any pencil drawings on the minimap',
            )

    minimap.add_argument('--clear-stamps',
            action='store_true',
            help='Clears any stamps on the minimap',
            )

    if has_image_support:

        minimap.add_argument('--pencil-image-export',
                type=str,
                metavar='FILENAME',
                help="""
                    Exports the current pencil minimap layer as an image with the specified filename.
                    The image export will always be the "full" image size, not just the playable area.
                    """,
                )

        minimap.add_argument('--pencil-image-import',
                type=str,
                metavar='FILENAME',
                help="""
                    Import the specified image filename to the minimap "pencil" layer.  The image
                    will be blindly resized to the minimap size without respect to aspect ratio.
                    The usual import area is 800x528, or 640x352 when using `--pencil-image-playable`.
                    The image will be converted to monochrome and dithered.  To prevent major
                    artifacts when passing in pre-dithered monochrome images, be sure to use the
                    exact image dimensions.
                    """,
                )

        minimap.add_argument('--pencil-image-playable',
                action='store_false',
                dest='pencil_image_full',
                help='When importing an image to the pencil layer, only import into the playable area, rather than the entire map space.',
                )

        minimap.add_argument('--pencil-image-invert',
                action='store_true',
                help='When importing an image to the pencil layer, invert the black/white pixels.',
                )

    parser.add_argument('filename',
            nargs=1,
            type=str,
            help='Savefile to open',
            )

    # Parse args and massage 'em a bit
    args = parser.parse_args()
    args.filename = args.filename[0]
    if args.slot is None:
        slot_indexes = []
    elif args.slot == 0:
        slot_indexes = [0, 1, 2]
    else:
        slot_indexes = [args.slot-1]
    delete_common_set_items(args.progress_enable, args.progress_disable)
    delete_common_set_items(args.egg_enable, args.egg_disable)
    delete_common_set_items(args.eggdoor_open, args.eggdoor_close)
    delete_common_set_items(args.candles_enable, args.candles_disable)
    delete_common_set_items(args.teleport_enable, args.teleport_disable)
    delete_common_set_items(args.bunny_enable, args.bunny_disable)
    delete_common_set_items(args.cats_free, args.cats_cage)
    delete_common_set_items(args.equip_enable, args.equip_disable)
    delete_common_set_items(args.inventory_enable, args.inventory_disable)
    delete_common_set_items(args.quest_state_enable, args.quest_state_disable)

    # Handle aggregate options
    if args.bosses_defeat:
        args.chameleon_defeat = True
        args.bat_defeat = True
        args.ostrich_defeat = True
        args.eel_defeat = True
        args.chameleon_respawn = False
        args.bat_respawn = False
        args.ostrich_respawn = False
        args.eel_respawn = False
    if args.bosses_respawn:
        args.chameleon_defeat = False
        args.bat_defeat = False
        args.ostrich_defeat = False
        args.eel_defeat = False
        args.chameleon_respawn = True
        args.bat_respawn = True
        args.ostrich_respawn = True
        args.eel_respawn = True

    # Figure out if we're restricting column output
    if args.single_column:
        columns = 1
    else:
        columns = None

    # Set our debug flag if we've been told to
    if args.debug:
        set_debug()

    # Find out if we have anything to do
    loop_into_slots = False
    do_slot_actions = False
    do_save = False
    if any([
            args.info,
            ]):
        if slot_indexes:
            loop_into_slots = True
    if any([
            # Control
            args.import_slot,
            args.export_slot,

            # Player
            args.health is not None,
            args.gold_hearts is not None,
            args.spawn,
            args.steps is not None,
            args.deaths is not None,
            args.saves is not None,
            args.bubbles_popped is not None,
            args.berries_eaten_while_full is not None,
            args.ticks is not None,
            args.ticks_copy_ingame,
            args.wings_enable,
            args.wings_disable,

            # Inventory
            args.firecrackers is not None,
            args.keys is not None,
            args.matches is not None,
            args.nuts is not None,
            args.equip_enable,
            args.equip_disable,
            args.inventory_enable,
            args.inventory_disable,
            args.map_enable,
            args.upgrade_wand,
            args.downgrade_wand,
            args.egg65_enable,
            args.egg65_disable,
            args.cring_enable,
            args.cring_disable,

            # Progress/Quests
            args.progress_enable,
            args.progress_disable,
            args.move_disc_to_shrine,
            args.move_disc_to_statue,
            args.cats_free,
            args.cats_cage,
            args.kangaroo_room is not None,
            args.kshard_collect is not None,
            args.kshard_insert is not None,
            args.s_medal_insert,
            args.s_medal_remove,
            args.e_medal_insert,
            args.e_medal_remove,
            args.teleport_enable,
            args.teleport_disable,
            args.mural_clear,
            args.mural_default,
            args.mural_solved,
            args.mural_raw_export,
            args.mural_raw_import,
            has_image_support and args.mural_image_export,
            has_image_support and args.mural_image_import,
            args.flame_collect,
            args.flame_use,
            args.blue_manticore,
            args.red_manticore,
            args.torus_enable,
            args.torus_disable,
            args.chameleon_defeat,
            args.chameleon_respawn,
            args.bat_defeat,
            args.bat_respawn,
            args.ostrich_defeat,
            args.ostrich_respawn,
            args.eel_defeat,
            args.eel_respawn,
            args.quest_state_enable,
            args.quest_state_disable,

            # Map Edits
            args.egg_enable,
            args.egg_disable,
            args.bunny_enable,
            args.bunny_disable,
            args.illegal_bunny_clear,
            args.respawn_consumables,
            args.clear_ghosts,
            args.respawn_ghosts,
            args.respawn_squirrels,
            args.buttons_press,
            args.buttons_reset,
            args.doors_open,
            args.doors_close,
            args.lockable_unlock,
            args.lockable_lock,
            args.eggdoor_open,
            args.eggdoor_close,
            args.walls_open,
            args.walls_close,
            args.clear_invalid_walls,
            args.house_open,
            args.house_close,
            args.chests_open,
            args.chests_close,
            args.candles_enable,
            args.candles_disable,
            args.solve_cranks,
            args.reservoirs_fill,
            args.reservoirs_empty,
            args.detonators_activate,
            args.detonators_rearm,
            args.big_stalactites_state is not None,
            args.small_deposits_break,
            args.small_deposits_respawn,
            args.respawn_destroyed_tiles,

            # Minimap
            args.reveal_map,
            args.clear_map,
            args.clear_pencil,
            args.clear_stamps,
            has_image_support and args.pencil_image_export,
            has_image_support and args.pencil_image_import,
            ]):
        if slot_indexes:
            loop_into_slots = True
            do_slot_actions = True
        else:
            parser.error('Slot actions were specified but no slots were chosen')

    # If the user uses any import/export functions, only allow a single slot
    if len(slot_indexes) > 1:
        if args.import_slot or args.export_slot:
            parser.error('Slot import/export may only be used with a single slot')
        if args.mural_raw_import or args.mural_raw_export:
            parser.error('Mural import/export may only be used with a single slot')
        if has_image_support:
            if args.mural_image_import or args.mural_image_export:
                parser.error('Mural import/export may only be used with a single slot')
            if args.pencil_image_import or args.pencil_image_export:
                parser.error('Pencil minimap import/export may only be used with a single slot')

    # Load the savegame
    if args.debug:
        print('Showing data offsets:', file=sys.stderr)
        print('', file=sys.stderr)
    with Savegame(args.filename) as save:
        if args.debug:
            print('', file=sys.stderr)
        
        if args.info:
            header = f'Animal Well Savegame v{save.version}'
            print(header)
            print('-'*len(header))
            print(f'(processed by animalwellsave v{__version__})')
            print('')
            print(f' - Last-Used Slot: {save.last_used_slot+1}')
            print(f' - Checksum: 0x{save.checksum:02X}')
            print(f' - Frame Seed: {save.frame_seed} (bunny mural: {(save.frame_seed % 50)+1}/50)')
            if save.unlockables.enabled:
                print(' - Unlockables:')
                print_columns(sorted(save.unlockables.enabled), columns=columns)
            if args.verbose and save.unlockables.disabled:
                print(' - Missing Unlockables:')
                print_columns(sorted(save.unlockables.disabled), columns=columns)

        # Make a note of fixing the checksum, if we were told to do so
        if args.fix_checksum:
            do_save = True

        # Process slots, if we've been told to
        if loop_into_slots:
            for slot_idx in slot_indexes:
                slot = save.slots[slot_idx]
                slot_label = f'Slot {slot.index+1}'

                # If we've been told to import slot data, do so now
                if args.import_slot:
                    print(f'{slot_label}: Importing slot data from: {args.import_slot}')
                    with open(args.import_slot, 'rb') as df:
                        slot.import_data(df.read())
                    do_save = True

                # Actions to perform only if we have slot data follow...
                if slot.has_data:

                    # Show general slot info first, if we've been told to
                    if args.info:
                        header = f'{slot_label}: {slot.timestamp}'
                        print('')
                        print(header)
                        print('-'*len(header))
                        print('')
                        if slot.elapsed_ticks_ingame == slot.elapsed_ticks_withpause:
                            print(f' - Elapsed Time: {slot.elapsed_ticks_withpause}')
                        else:
                            print(f' - Elapsed Time: {slot.elapsed_ticks_withpause} (ingame: {slot.elapsed_ticks_ingame})')
                        if len(slot.progress) > 0:
                            print(' - Progress flags: {}'.format(
                                ', '.join(sorted([str(p) for p in slot.progress.enabled])),
                                ))
                        print(f' - Saved in Room: {slot.spawn_room}')
                        if slot.gold_hearts > 0:
                            if slot.gold_hearts == 1:
                                plural = ''
                            else:
                                plural = 's'
                            print(f' - Health: {slot.health} ({slot.gold_hearts} gold heart{plural})')
                        else:
                            print(f' - Health: {slot.health}')
                        print(f' - Counters:')
                        print(f'   - Steps: {slot.num_steps:,}')
                        print(f'   - Times Saved: {slot.num_saves}')
                        print(f'   - Times Died: {slot.num_deaths} (Times Hit: {slot.num_hits})')
                        if Equipment.FIRECRACKER in slot.equipment.enabled:
                            print(f'   - Firecrackers Collected: {slot.firecrackers_collected}')
                        if slot.bubbles_popped > 0:
                            print(f'   - Bubbles Popped: {slot.bubbles_popped}')
                        if slot.berries_eaten_while_full > 0:
                            print(f'   - Berries Eaten While Full: {slot.berries_eaten_while_full}')
                        print(f' - Consumables Inventory:')
                        if Equipment.FIRECRACKER in slot.equipment.enabled:
                            print(f'   - Firecrackers: {slot.firecrackers}')
                        print(f'   - Keys: {slot.keys}')
                        print(f'   - Matches: {slot.matches}')
                        if slot.nuts > 0:
                            print(f'   - Nuts: {slot.nuts}')
                        if slot.equipment.enabled:
                            print(' - Equipment Unlocked:')
                            print_columns(sorted(slot.equipment.enabled), columns=columns)
                            print(f' - Selected Equipment: {slot.selected_equipment}')
                        if args.verbose and slot.equipment.disabled:
                            print(' - Missing Equipment:')
                            print_columns(sorted(slot.equipment.disabled), columns=columns)
                        k_shards_collected = slot.kangaroo_state.num_collected()
                        k_shards_inserted = slot.kangaroo_state.num_inserted()
                        missing_k_shards = 3 - k_shards_collected - k_shards_inserted
                        if slot.inventory.enabled or k_shards_collected:
                            print(' - Inventory Unlocked:')
                            report = list(slot.inventory.enabled)
                            if k_shards_collected > 0:
                                if k_shards_inserted > 0:
                                    suffix = f', plus {k_shards_inserted} inserted'
                                else:
                                    suffix = ''
                                report.append(f'K. Shards ({k_shards_collected}/3{suffix})')
                            print_columns(sorted(report), columns=columns)
                        if args.verbose and (slot.inventory.disabled or missing_k_shards > 0):
                            # Filter out disabled inventory which might not make sense to report on
                            disabled = set()
                            for item in slot.inventory.disabled:
                                if item == Inventory.S_MEDAL and QuestState.USED_S_MEDAL in slot.quest_state.enabled:
                                    continue
                                if item == Inventory.E_MEDAL and QuestState.USED_E_MEDAL in slot.quest_state.enabled:
                                    continue
                                disabled.add(item)
                            if missing_k_shards > 0:
                                disabled.add(f'K. Shards ({missing_k_shards} missing)')
                            print(' - Missing Inventory:')
                            print_columns(sorted(disabled), columns=columns)
                        print(f' - Eggs Collected: {len(slot.eggs.enabled)}')
                        print_columns(sorted(slot.eggs.enabled), columns=columns)
                        if args.verbose and slot.eggs.disabled:
                            print(' - Missing Eggs:')
                            print_columns(sorted(slot.eggs.disabled), columns=columns)
                        if len(slot.bunnies.enabled) > 0:
                            print(f' - Bunnies Collected: {len(slot.bunnies.enabled)}')
                            print_columns(sorted(slot.bunnies.enabled), columns=columns)
                        if len(slot.illegal_bunnies.enabled) > 0:
                            print(f' - Illegal Bunnies Collected: {len(slot.illegal_bunnies.enabled)}')
                            print('   ***WARNING***')
                            print('   Having illegal bunnies collected will cause the BDTP puzzle to be')
                            print('   unsolveable.  We recommend using the --illegal-bunny-clear option')
                            print('   on this save to clean it up.')
                            print('   ***WARNING***')
                        if args.verbose and slot.bunnies.disabled:
                            print(' - Missing Bunnies:')
                            print_columns(sorted(slot.bunnies.disabled), columns=columns)
                        if slot.quest_state.enabled:
                            print(f' - Quest State Flags:')
                            print_columns(sorted(slot.quest_state.enabled), columns=columns)
                        if args.verbose and slot.quest_state.disabled:
                            disabled = set()
                            # Filter out disabled quest states which might not make sense to report on
                            for item in slot.quest_state.disabled:
                                if item == QuestState.SHRINE_NO_DISC and QuestState.STATUE_NO_DISC in slot.quest_state.enabled:
                                    continue
                                if item == QuestState.STATUE_NO_DISC and QuestState.SHRINE_NO_DISC in slot.quest_state.enabled:
                                    continue
                                if item == QuestState.FIGHTING_EEL and QuestState.DEFEATED_EEL in slot.quest_state.enabled:
                                    continue
                                disabled.add(item)
                            if disabled:
                                print(f' - Missing Quest States:')
                                print_columns(sorted(disabled), columns=columns)
                        if any([flame.choice != FlameState.SEALED for flame in slot.flames]):
                            print(f' - Flame States:')
                            for flame in slot.flames:
                                print(f'   - {flame.name}: {flame}')
                        print(f' - Transient Map Data:')
                        print(f'   - Fruit Picked: {slot.picked_fruit}')
                        if slot.picked_fruit.has_stolen_nut:
                            print('     - Also has stolen a nut from a squirrel (counts as a picked fruit!)')
                        if Equipment.FIRECRACKER in slot.equipment.enabled:
                            print(f'   - Firecrackers Picked: {slot.picked_firecrackers}')
                        print(f'   - Ghosts Scared: {slot.ghosts_scared}')
                        if any([s != BigStalactiteState.INTACT for s in slot.big_stalactites]):
                            print('   - Big Stalactite States:')
                            to_report = []
                            for idx, stalactite in enumerate(slot.big_stalactites):
                                if stalactite != BigStalactiteState.INTACT:
                                    to_report.append(f'{stalactite.debug_label}: {stalactite}')
                            print_columns(to_report, columns=columns, indent='     ')
                        if slot.deposit_small_broken > 0:
                            print(f'   - Small Stalactites/Stalagmites Broken: {slot.deposit_small_broken}')
                        if slot.icicles_broken > 0:
                            print(f'   - Icicles Broken: {slot.icicles_broken}')
                        print('   - Next Kangaroo Room: {} {}, in state: {}'.format(
                            slot.kangaroo_state.next_encounter_id,
                            slot.kangaroo_state.get_cur_kangaroo_room_str(),
                            slot.kangaroo_state.state,
                            ))
                        if QuestState.UNLOCK_STAMPS in slot.quest_state.enabled:
                            print(f'   - Minimap Stamps: {len(slot.stamps)}')
                        print(f' - Permanent Map Data:')
                        print(f'   - Chests Opened: {slot.chests_opened}')
                        if slot.layer1_chests_opened > 0:
                            print(f'   - CE Temple Chests Opened: {slot.layer1_chests_opened}')
                        if slot.squirrels_scared > 0:
                            print(f'   - Squirrels Scared: {slot.squirrels_scared}')
                        if slot.yellow_buttons_pressed > 0:
                            print(f'   - Yellow Buttons Pressed: {slot.yellow_buttons_pressed}')
                        if slot.purple_buttons_pressed > 0:
                            print(f'   - Purple Buttons Pressed: {slot.purple_buttons_pressed}')
                        if slot.green_buttons_pressed > 0:
                            print(f'   - Green Buttons Pressed: {slot.green_buttons_pressed}')
                        if len(slot.pink_buttons_pressed) > 0:
                            print(f'   - Valid Pink Buttons Pressed: {len(slot.pink_buttons_pressed)}')
                        if len(slot.invalid_pink_buttons) > 0:
                            print(f'   - Invalid Pink Buttons Pressed: {len(slot.invalid_pink_buttons)}')
                            print('     ***WARNING***')
                            print('       Having invalid pink buttons pressed can end up leading to savefile')
                            print('       corruption!  We recommend using the --clear-invalid-walls option on')
                            print('       this save to clean it up.')
                            print('     ***WARNING***')
                        if slot.layer2_buttons_pressed > 0:
                            print(f'   - Space / Bunny Island Buttons Pressed: {slot.layer2_buttons_pressed}')
                        if slot.button_doors_opened > 0:
                            print(f'   - Button-Activated Doors Opened: {slot.button_doors_opened}')
                        if len(slot.locked_doors) > 0:
                            print(f'   - Doors Unlocked: {len(slot.locked_doors)}')
                        if len(slot.moved_walls) > 0:
                            print(f'   - Walls Moved: {len(slot.moved_walls)}')
                        num_filled = slot.fill_levels.num_filled()
                        if num_filled > 0:
                            print(f'   - Reservoirs Filled: {num_filled}')
                        if len(slot.candles.enabled) > 0:
                            print(f'   - Candles Lit: {len(slot.candles)}/{slot.candles.count()}')
                        if args.verbose and len(slot.candles.disabled) > 0:
                            print('   - Missing Candles-to-Light:')
                            print_columns(sorted(slot.candles.disabled), indent='     ', columns=columns)
                        if slot.detonators_triggered.count > 0:
                            print(f'   - Detonators Triggered: {slot.detonators_triggered}')
                        if slot.walls_blasted.count > 0:
                            print(f'   - Walls Blasted: {slot.walls_blasted}')
                        if len(slot.egg_doors) > 0:
                            print(f'   - Egg Doors Opened: {len(slot.egg_doors)}')
                        if k_shards_inserted > 0:
                            print(f'   - K. Shards Inserted: {k_shards_inserted}/3')
                        if len(slot.cat_status) > 0:
                            cat_count = len(slot.cat_status)
                            has_wheel = False
                            if CatStatus.WHEEL in slot.cat_status.enabled:
                                cat_count -= 1
                                has_wheel = True
                            if cat_count > 0:
                                print(f'   - Cats Rescued: {cat_count}')
                            if has_wheel:
                                print(f'   - Unlocked wheel cage')
                        if slot.blue_manticore.choice != ManticoreState.DEFAULT:
                            print(f'   - Blue Manticore: {slot.blue_manticore}')
                        if slot.red_manticore.choice != ManticoreState.DEFAULT:
                            print(f'   - Red Manticore: {slot.red_manticore}')
                        if slot.teleports.enabled:
                            print(f' - Teleports Active: {len(slot.teleports.enabled)}')
                            print_columns(sorted(slot.teleports.enabled), columns=columns)
                        if args.verbose and slot.teleports.disabled:
                            print(' - Missing Teleports:')
                            print_columns(sorted(slot.teleports.disabled), columns=columns)

                        if do_slot_actions:
                            print('')

                    # Keep track of if we're modifying any disc equipment
                    doing_disc_actions = False

                    ###
                    ### Player
                    ###

                    if args.health:
                        print(f'{slot_label}: Updating health to: {args.health}')
                        slot.health.value = args.health
                        do_save = True

                    if args.gold_hearts:
                        print(f'{slot_label}: Updating gold hearts count to: {args.gold_hearts}')
                        slot.gold_hearts.value = args.gold_hearts
                        do_save = True

                    if args.spawn:
                        print(f'{slot_label}: Setting spawnpoint to ({args.spawn.x}, {args.spawn.y})')
                        slot.spawn_room.x.value = args.spawn.x
                        slot.spawn_room.y.value = args.spawn.y
                        if args.spawn.x == 3 and args.spawn.y == 7:
                            print(textwrap.dedent("""
                                *** WARNING ***

                                Spawning into room (3,7) will cause you to trigger a pink button which
                                can lead to savefile corruption if other "illegal" pink buttons are
                                also pressed.  Those buttons are only available via the Cheater's
                                Ring, and only triggering this one button will not cause corruption by
                                itself.  But if you want to avoid the situation altogether, spawn
                                into a different room!

                                *** WARNING ***
                                """))
                        do_save = True

                    if args.steps is not None:
                        print(f'{slot_label}: Updating steps taken to: {args.steps}')
                        slot.num_steps.value = args.steps
                        do_save = True

                    if args.deaths is not None:
                        print(f'{slot_label}: Updating death count to: {args.deaths}')
                        slot.num_deaths.value = args.deaths
                        do_save = True

                    if args.saves is not None:
                        print(f'{slot_label}: Updating save count to: {args.saves}')
                        slot.num_saves.value = args.saves
                        do_save = True

                    if args.bubbles_popped is not None:
                        print(f'{slot_label}: Updating bubbles-popped count to: {args.bubbles_popped}')
                        slot.bubbles_popped.value = args.bubbles_popped
                        do_save = True

                    if args.berries_eaten_while_full is not None:
                        print(f'{slot_label}: Updating berries eaten while full count to: {args.berries_eaten_while_full}')
                        slot.berries_eaten_while_full.value = args.berries_eaten_while_full
                        do_save = True

                    if args.ticks is not None:
                        print(f'{slot_label}: Updating tick count to: {args.ticks}')
                        slot.elapsed_ticks_ingame.value = args.ticks
                        slot.elapsed_ticks_withpause.value = args.ticks
                        do_save = True

                    if args.ticks_copy_ingame:
                        print(f'{slot_label}: Copying ingame tick count to with-paused tick count')
                        slot.elapsed_ticks_withpause.value = slot.elapsed_ticks_ingame.value
                        do_save = True

                    if args.wings_enable:
                        if QuestState.WINGS not in slot.quest_state.enabled:
                            print(f'{slot_label}: Enabling Wings / Flight Mode')
                            slot.quest_state.enable(QuestState.WINGS)
                            do_save = True

                    if args.wings_disable:
                        if QuestState.WINGS in slot.quest_state.enabled:
                            print(f'{slot_label}: Disabling Wings / Flight Mode')
                            slot.quest_state.disable(QuestState.WINGS)
                            do_save = True

                    ###
                    ### Inventory
                    ###

                    if args.firecrackers is not None:
                        print(f'{slot_label}: Updating firecracker count to: {args.firecrackers}')
                        slot.firecrackers.value = args.firecrackers
                        do_save = True
                        if args.firecrackers > 0 and Equipment.FIRECRACKER not in slot.equipment.enabled:
                            if args.equip_enable is None:
                                args.equip_enable = set()
                            args.equip_enable.add(Equipment.FIRECRACKER)

                    if args.keys is not None:
                        print(f'{slot_label}: Updating key count to: {args.keys}')
                        slot.keys.value = args.keys
                        do_save = True

                    if args.matches is not None:
                        print(f'{slot_label}: Updating match count to: {args.matches}')
                        slot.matches.value = args.matches
                        do_save = True

                    if args.nuts is not None:
                        print(f'{slot_label}: Updating stolen nut count to: {args.nuts}')
                        slot.nuts.value = args.nuts
                        do_save = True

                    changed_equipment = False

                    if args.equip_enable:
                        for equip in sorted(args.equip_enable):
                            if equip not in slot.equipment.enabled:
                                print(f'{slot_label}: Enabling equipment: {equip}')
                                slot.equipment.enable(equip)
                                changed_equipment = True
                                do_save = True
                            if equip == Equipment.DISC:
                                doing_disc_actions = True

                    if args.equip_disable:
                        for equip in sorted(args.equip_disable):
                            if equip in slot.equipment.enabled:
                                print(f'{slot_label}: Disabling equipment: {equip}')
                                slot.equipment.disable(equip)
                                changed_equipment = True
                                do_save = True
                            if equip == Equipment.DISC:
                                doing_disc_actions = True

                    # If we changed enabled equipment, we may need to change the currently-
                    # selected equipment field as well.
                    if changed_equipment:
                        if len(slot.equipment.enabled) == 0:
                            # If there's no equipment enabled, just revert our current selection to None
                            print(f'{slot_label}: Setting currently-equipped item to none')
                            slot.selected_equipment.value = Equipped.NONE
                        else:
                            # Otherwise, we may need to update.  Create a couple mappings between these
                            # two enums so we can update our selected equipment if need be.
                            equipped_to_equipment = {}
                            equipment_to_equipped = {}
                            for item in Equipped:
                                try:
                                    equipped_to_equipment[item] = Equipment[item.name]
                                except KeyError:
                                    pass
                            for item in Equipment:
                                try:
                                    equipment_to_equipped[item] = Equipped[item.name]
                                except KeyError:
                                    pass
                            if slot.selected_equipment.choice == Equipped.NONE \
                                    or equipped_to_equipment[slot.selected_equipment.choice] not in slot.equipment.enabled:
                                # Enable the first equipment we have (alphabetically)
                                to_equip = equipment_to_equipped[sorted(slot.equipment.enabled)[0]]
                                print(f'{slot_label}: Setting currently-equipped item to: {to_equip}')
                                slot.selected_equipment.value = to_equip

                    if args.inventory_disable:
                        for inv in sorted(args.inventory_disable):
                            if inv in slot.inventory.enabled:
                                print(f'{slot_label}: Disabling inventory item: {inv}')
                                slot.inventory.disable(inv)
                                do_save = True
                            if inv == Inventory.MOCK_DISC:
                                doing_disc_actions = True

                    if args.inventory_enable:

                        # Some shenanigans here!  If the user specifies both `--equip-enable all` and
                        # `--inventory-enable all`, it's *likely* that they want to exclude the Mock
                        # Disc.  They could explicitly exclude that with `--inventory-disable mock_disc`
                        # but IMO it makes sense to exclude by default, for this specific case.  We
                        # will *not* do the exclusion if the user specified `--dont-fix-disc-state`,
                        # though.
                        if args.fix_disc_state and args.equip_enable:
                            # The check here is actually a bit ridiculous, since we don't actually retain
                            # information about whether the user selected `all` or individual options.  So
                            # we're manually checking to see if we have the full set.
                            all_equipment = all([e in args.equip_enable for e in Equipment])
                            all_inventory = all([i in args.inventory_enable for i in Inventory])
                            if all_equipment and all_inventory:
                                print('NOTICE: Excluding Mock Disc from inventory unlocks.  (Specify --dont-fix-disc-state to add it anyway.)')
                                args.inventory_enable.remove(Inventory.MOCK_DISC)

                        # Now continue on...
                        for inv in sorted(args.inventory_enable):
                            if inv not in slot.inventory.enabled:
                                print(f'{slot_label}: Enabling inventory item: {inv}')
                                slot.inventory.enable(inv)
                                do_save = True
                            if inv == Inventory.MOCK_DISC:
                                doing_disc_actions = True

                    if args.map_enable:
                        for map_var in sorted(args.map_enable):
                            if map_var not in slot.quest_state.enabled:
                                print(f'{slot_label}: Enabling map unlock: {map_var}')
                                slot.quest_state.enable(map_var)
                                do_save = True

                    if args.upgrade_wand:
                        if QuestState.BB_WAND not in slot.quest_state.enabled:
                            print(f'{slot_label}: Upgrading B. Wand')
                            slot.quest_state.enable(QuestState.BB_WAND)
                            do_save = True

                    if args.downgrade_wand:
                        if QuestState.BB_WAND in slot.quest_state.enabled:
                            print(f'{slot_label}: Downgrading B.B. Wand')
                            slot.quest_state.disable(QuestState.BB_WAND)
                            do_save = True

                    if args.egg65_enable:
                        if QuestState.EGG_65 not in slot.quest_state.enabled:
                            print(f'{slot_label}: Unlocking Egg 65')
                            slot.quest_state.enable(QuestState.EGG_65)
                            do_save = True

                    if args.egg65_disable:
                        if QuestState.EGG_65 in slot.quest_state.enabled:
                            print(f'{slot_label}: Removing Egg 65')
                            slot.quest_state.disable(QuestState.EGG_65)
                            do_save = True

                    if args.cring_enable:
                        if QuestState.CRING not in slot.quest_state.enabled:
                            print(f"{slot_label}: Unlocking Cheater's Ring")
                            slot.quest_state.enable(QuestState.CRING)
                            do_save = True

                    if args.cring_disable:
                        if QuestState.CRING in slot.quest_state.enabled:
                            print(f"{slot_label}: Removing Cheater's Ring")
                            slot.quest_state.disable(QuestState.CRING)
                            do_save = True

                    ###
                    ### Progress/Quests
                    ###

                    if args.progress_enable:
                        for progress in sorted(args.progress_enable):
                            if progress not in slot.progress.enabled:
                                print(f'{slot_label}: Enabling progress flag: {progress}')
                                slot.progress.enable(progress)
                                do_save = True

                    if args.progress_disable:
                        for progress in sorted(args.progress_disable):
                            if progress in slot.progress.enabled:
                                print(f'{slot_label}: Disabling progress flag: {progress}')
                                slot.progress.disable(progress)
                                do_save = True

                    if args.move_disc_to_shrine:
                        if Equipment.DISC in slot.equipment.enabled \
                                and Inventory.MOCK_DISC not in slot.inventory.enabled \
                                and QuestState.STATUE_NO_DISC not in slot.quest_state.enabled \
                                and QuestState.SHRINE_NO_DISC in slot.quest_state.enabled:
                            print(f'{slot_label}: Moving Mock Disc from Dog Head Statue to Shrine')
                            slot.quest_state.enable(QuestState.STATUE_NO_DISC)
                            slot.quest_state.disable(QuestState.SHRINE_NO_DISC)
                            do_save = True
                        else:
                            print('*** WARNING: Conditions not met for --move-disc-to-shrine, skipping. ***')

                    if args.move_disc_to_statue:
                        if Equipment.DISC in slot.equipment.enabled \
                                and Inventory.MOCK_DISC not in slot.inventory.enabled \
                                and QuestState.STATUE_NO_DISC in slot.quest_state.enabled \
                                and QuestState.SHRINE_NO_DISC not in slot.quest_state.enabled:
                            print(f'{slot_label}: Moving Mock Disc from Shrine to Dog Head Statue')
                            slot.quest_state.disable(QuestState.STATUE_NO_DISC)
                            slot.quest_state.enable(QuestState.SHRINE_NO_DISC)
                            do_save = True
                        else:
                            print('*** WARNING: Conditions not met for --move-disc-to-statue, skipping. ***')

                    if args.cats_free:
                        for cat in sorted(args.cats_free):
                            if cat not in slot.cat_status.enabled:
                                print(f'{slot_label}: Freeing cat: {cat}')
                                slot.cat_status.enable(cat)
                                do_save = True

                    if args.cats_cage:
                        for cat in sorted(args.cats_cage):
                            if cat in slot.cat_status.enabled:
                                print(f'{slot_label}: Re-caging cat: {cat}')
                                slot.cat_status.disable(cat)
                                do_save = True

                    if args.kangaroo_room is not None:
                        print(f'{slot_label}: Setting next kangaroo room to: {args.kangaroo_room}')
                        slot.kangaroo_state.force_kangaroo_room(args.kangaroo_room)
                        do_save = True

                    if args.kshard_collect is not None:
                        print(f'{slot_label}: Setting total number of collected K. Shards to: {args.kshard_collect}')
                        slot.kangaroo_state.set_shard_state(args.kshard_collect, KangarooShardState.COLLECTED)
                        do_save = True

                    if args.kshard_insert is not None:
                        print(f'{slot_label}: Setting total number of inserted K. Shards to: {args.kshard_insert}')
                        slot.kangaroo_state.set_shard_state(args.kshard_insert, KangarooShardState.INSERTED)
                        do_save = True

                    if args.s_medal_insert:
                        if QuestState.USED_S_MEDAL not in slot.quest_state.enabled:
                            print(f'{slot_label}: Marking S. Medal as inserted')
                            slot.quest_state.enable(QuestState.USED_S_MEDAL)
                            do_save = True

                    if args.s_medal_remove:
                        if QuestState.USED_S_MEDAL in slot.quest_state.enabled:
                            print(f'{slot_label}: Removing S. Medal from recess')
                            slot.quest_state.disable(QuestState.USED_S_MEDAL)
                            do_save = True

                    if args.e_medal_insert:
                        if QuestState.USED_E_MEDAL not in slot.quest_state.enabled:
                            print(f'{slot_label}: Marking E. Medal as inserted')
                            slot.quest_state.enable(QuestState.USED_E_MEDAL)
                            do_save = True

                    if args.e_medal_remove:
                        if QuestState.USED_E_MEDAL in slot.quest_state.enabled:
                            print(f'{slot_label}: Removing E. Medal from recess')
                            slot.quest_state.disable(QuestState.USED_E_MEDAL)
                            do_save = True

                    if args.teleport_enable:
                        for teleport in sorted(args.teleport_enable):
                            if teleport not in slot.teleports.enabled:
                                print(f'{slot_label}: Enabling teleport: {teleport}')
                                slot.teleports.enable(teleport)
                                do_save = True

                    if args.teleport_disable:
                        for teleport in sorted(args.teleport_disable):
                            if teleport in slot.teleports.enabled:
                                print(f'{slot_label}: Disabling teleport: {teleport}')
                                slot.teleports.disable(teleport)
                                do_save = True

                    if args.mural_clear:
                        print(f'{slot_label}: Clearing all mural pixels')
                        slot.mural.clear()
                        do_save = True

                    if args.mural_default:
                        print(f'{slot_label}: Setting mural to its default state')
                        slot.mural.to_default()
                        do_save = True

                    if args.mural_solved:
                        print(f'{slot_label}: Setting mural to its solved state (NOTE: you will need to activate one pixel to get the door to open)')
                        slot.mural.to_solved()
                        do_save = True

                    if args.mural_raw_import:
                        print(f'{slot_label}: Importing raw bunny mural data in "{args.mural_raw_import}"')
                        slot.mural.import_raw(args.mural_raw_import)
                        do_save = True

                    if args.mural_raw_export:
                        print(f'{slot_label}: Exporting raw bunny mural data to: {args.mural_raw_export}')
                        if check_file_overwrite(args, args.mural_raw_export):
                            slot.mural.export_raw(args.mural_raw_export)
                            print('Raw bunny mural data exported!')
                        else:
                            print('NOTICE: Raw bunny mural data NOT exported')

                    if has_image_support:

                        if args.mural_image_import:
                            print(f'{slot_label}: Importing image "{args.mural_image_import}" to bunny mural')
                            slot.mural.import_image(args.mural_image_import)
                            do_save = True

                        if args.mural_image_export:
                            print(f'{slot_label}: Exporting bunny mural image to: {args.mural_image_export}')
                            if check_file_overwrite(args, args.mural_image_export):
                                slot.mural.export_image(args.mural_image_export)
                                print('Bunny mural exported!')
                            else:
                                print('NOTICE: Bunny mural NOT exported')

                    for arg, status in [
                            (args.flame_collect, FlameState.COLLECTED),
                            (args.flame_use, FlameState.USED),
                            ]:
                        if arg:
                            if 'all' in arg:
                                flames = slot.flames
                            else:
                                flames = []
                                for letter in arg:
                                    flames.append(slot.flames[letter])
                            for flame in flames:
                                print(f'{slot_label}: Updating {flame.name} status to: {status}')
                                flame.value = status
                            do_save = True

                    if args.blue_manticore:
                        if slot.blue_manticore.choice != args.blue_manticore:
                            print(f'{slot_label}: Setting Blue Manticore state to: {args.blue_manticore}')
                            slot.blue_manticore.value = args.blue_manticore
                            do_save = True

                    if args.red_manticore:
                        if slot.red_manticore.choice != args.red_manticore:
                            print(f'{slot_label}: Setting Red Manticore state to: {args.red_manticore}')
                            slot.red_manticore.value = args.red_manticore
                            do_save = True

                    if args.torus_enable:
                        if QuestState.TORUS not in slot.quest_state.enabled:
                            print(f'{slot_label}: Enabling Teleportation Torus')
                            slot.quest_state.enable(QuestState.TORUS)
                            do_save = True

                    if args.torus_disable:
                        if QuestState.TORUS in slot.quest_state.enabled:
                            print(f'{slot_label}: Disabling Teleportation Torus')
                            slot.quest_state.disable(QuestState.TORUS)
                            do_save = True

                    # Boss defeats / respawns.  I'd tried to be clever originally and was looping
                    # over a few vars, but there's enough special-cases for many of these that it
                    # got to be way overengineered.  So, back to dumb hardcoding.  :)

                    if args.chameleon_defeat:
                        if QuestState.DEFEATED_CHAMELEON not in slot.quest_state.enabled:
                            print(f'{slot_label}: Marking Chameleon boss as defeated')
                            slot.quest_state.enable(QuestState.DEFEATED_CHAMELEON)
                            do_save = True

                    if args.chameleon_respawn:
                        if QuestState.DEFEATED_CHAMELEON in slot.quest_state.enabled:
                            print(f'{slot_label}: Respawning Chameleon boss')
                            slot.quest_state.disable(QuestState.DEFEATED_CHAMELEON)
                            do_save = True

                    if args.bat_defeat:
                        if QuestState.DEFEATED_BAT not in slot.quest_state.enabled:
                            print(f'{slot_label}: Marking Bat boss as defeated')
                            slot.quest_state.enable(QuestState.DEFEATED_BAT)
                            do_save = True

                    if args.bat_respawn:
                        if QuestState.DEFEATED_BAT in slot.quest_state.enabled:
                            print(f'{slot_label}: Respawning Bat boss')
                            slot.quest_state.disable(QuestState.DEFEATED_BAT)
                            do_save = True

                    if args.ostrich_defeat:
                        # Vanilla game state implies both "freed" and "defeated" states
                        if QuestState.DEFEATED_OSTRICH not in slot.quest_state.enabled \
                                or QuestState.FREED_OSTRICH not in slot.quest_state.enabled:
                            print(f'{slot_label}: Marking Ostrich bosses as defeated (and stopping platforms, if necessary)')
                            if QuestState.DEFEATED_OSTRICH not in slot.quest_state.enabled:
                                slot.quest_state.enable(QuestState.DEFEATED_OSTRICH)
                            if QuestState.FREED_OSTRICH not in slot.quest_state.enabled:
                                slot.quest_state.enable(QuestState.FREED_OSTRICH)
                            # Also stop the elevator
                            slot.elevators.inactive.enable(ElevatorDisabled.OSTRICH)
                            do_save = True

                    if args.ostrich_respawn:
                        if QuestState.DEFEATED_OSTRICH in slot.quest_state.enabled \
                                or QuestState.FREED_OSTRICH in slot.quest_state.enabled:
                            print(f'{slot_label}: Respawning Ostrich Bosses (to pre-freed state, unpressing purple')
                            print('        button and reactivating platforms if necessary)')
                            if QuestState.DEFEATED_OSTRICH in slot.quest_state.enabled:
                                slot.quest_state.disable(QuestState.DEFEATED_OSTRICH)
                            if QuestState.FREED_OSTRICH in slot.quest_state.enabled:
                                slot.quest_state.disable(QuestState.FREED_OSTRICH)
                            # Also undo the purple button press so that the ostrich doesn't
                            # immediately start attacking again.  Just hardcoding the index here
                            slot.purple_buttons_pressed.clear_bit(22)
                            # Also restart the elevator
                            slot.elevators.inactive.disable(ElevatorDisabled.OSTRICH)
                            do_save = True
                        do_save = True

                    if args.eel_defeat:
                        if QuestState.DEFEATED_EEL not in slot.quest_state.enabled:
                            print(f'{slot_label}: Marking Eel/Bonefish boss as defeated')
                            slot.quest_state.enable(QuestState.DEFEATED_EEL)
                            # Also clear "fighting" state, if we have it
                            if QuestState.FIGHTING_EEL in slot.quest_state.enabled:
                                slot.quest_state.disable(QuestState.FIGHTING_EEL)
                            do_save = True

                    if args.eel_respawn:
                        if QuestState.DEFEATED_EEL in slot.quest_state.enabled:
                            print(f'{slot_label}: Respawning Eel/Bonefish boss (to pre-awakened state)')
                            slot.quest_state.disable(QuestState.DEFEATED_EEL)
                            # Also clear "fighting" state, if we have it
                            if QuestState.FIGHTING_EEL in slot.quest_state.enabled:
                                slot.quest_state.disable(QuestState.FIGHTING_EEL)
                            do_save = True

                    ###
                    ### Map Edits
                    ###

                    if args.egg_enable:
                        for egg in sorted(args.egg_enable):
                            if egg not in slot.eggs.enabled:
                                print(f'{slot_label}: Enabling egg: {egg}')
                                slot.eggs.enable(egg)
                                do_save = True

                    if args.egg_disable:
                        for egg in sorted(args.egg_disable):
                            if egg in slot.eggs.enabled:
                                print(f'{slot_label}: Disabling egg: {egg}')
                                slot.eggs.disable(egg)
                                do_save = True

                    if args.bunny_disable:
                        for bunny in sorted(args.bunny_disable):
                            if bunny in slot.bunnies.enabled:
                                print(f'{slot_label}: Disabling bunny: {bunny}')
                                slot.bunnies.disable(bunny)
                                do_save = True

                    if args.bunny_enable:
                        for bunny in sorted(args.bunny_enable):
                            if bunny not in slot.bunnies.enabled:
                                print(f'{slot_label}: Enabling bunny: {bunny}')
                                slot.bunnies.enable(bunny)
                                do_save = True

                    if args.illegal_bunny_clear:
                        if slot.illegal_bunnies.enabled:
                            print(f'{slot_label}: Clearing illegal bunnies')
                            slot.illegal_bunnies.disable_all()
                            do_save = True

                    if args.respawn_consumables:
                        print(f'{slot_label}: Respawning fruit and firecrackers')
                        slot.picked_fruit.clear()
                        slot.picked_firecrackers.clear()
                        do_save = True

                    if args.clear_ghosts:
                        print(f'{slot_label}: Clearing ghosts')
                        slot.ghosts_scared.fill()
                        do_save = True

                    if args.respawn_ghosts:
                        print(f'{slot_label}: Respawning ghosts')
                        slot.ghosts_scared.clear()
                        do_save = True

                    if args.respawn_squirrels:
                        print(f'{slot_label}: Respawning squirrels')
                        slot.squirrels_scared.clear()
                        do_save = True

                    if args.buttons_press:
                        print(f'{slot_label}: Marking all buttons as pressed')
                        slot.yellow_buttons_pressed.fill()
                        slot.purple_buttons_pressed.fill()
                        slot.green_buttons_pressed.fill()
                        slot.pink_buttons_pressed.enable_all()
                        slot.layer2_buttons_pressed.fill()
                        do_save = True

                    if args.buttons_reset:
                        print(f'{slot_label}: Marking all buttons as not pressed')
                        slot.yellow_buttons_pressed.clear()
                        slot.purple_buttons_pressed.clear()
                        slot.green_buttons_pressed.clear()
                        slot.pink_buttons_pressed.disable_all()
                        slot.layer2_buttons_pressed.clear()
                        do_save = True

                    if args.doors_open:
                        print(f'{slot_label}: Marking all button-controlled doors as opened')
                        slot.button_doors_opened.fill()
                        do_save = True

                    if args.doors_close:
                        print(f'{slot_label}: Marking all button-controlled doors as closed')
                        slot.button_doors_opened.clear()
                        do_save = True

                    if args.lockable_unlock:
                        print(f'{slot_label}: Unlocking all lockable doors')
                        slot.locked_doors.fill()
                        do_save = True

                    if args.lockable_lock:
                        print(f'{slot_label}: Locking all lockable doors')
                        slot.locked_doors.clear()
                        do_save = True

                    if args.eggdoor_open:
                        for eggdoor in sorted(args.eggdoor_open):
                            if eggdoor not in slot.egg_doors.enabled:
                                print(f'{slot_label}: Opening egg door: {eggdoor}')
                                slot.egg_doors.enable(eggdoor)
                                do_save = True

                    if args.eggdoor_close:
                        for eggdoor in sorted(args.eggdoor_close):
                            if eggdoor in slot.egg_doors.enabled:
                                print(f'{slot_label}: Closing egg door: {eggdoor}')
                                slot.egg_doors.disable(eggdoor)
                                do_save = True

                    if args.clear_invalid_walls:
                        print(f'{slot_label}: Clearing invalid wall-opening records')
                        slot.moved_walls.remove_invalid()
                        slot.invalid_pink_buttons.disable_all()
                        do_save = True

                    if args.walls_open:
                        print(f'{slot_label}: Opening all movable walls')
                        slot.moved_walls.fill()
                        do_save = True

                    if args.walls_close:
                        print(f'{slot_label}: Closing all movable walls')
                        slot.moved_walls.clear()
                        do_save = True

                    if args.house_open:
                        print(f'{slot_label}: Marking doors around the house as opened')
                        for state in [
                                QuestState.HOUSE_OPEN,
                                QuestState.OFFICE_OPEN,
                                QuestState.CLOSET_OPEN,
                                ]:
                            if state not in slot.quest_state.enabled:
                                slot.quest_state.enable(state)
                        do_save = True

                    if args.house_close:
                        print(f'{slot_label}: Marking doors around the house as closed')
                        for state in [
                                QuestState.HOUSE_OPEN,
                                QuestState.OFFICE_OPEN,
                                QuestState.CLOSET_OPEN,
                                ]:
                            if state in slot.quest_state.enabled:
                                slot.quest_state.disable(state)
                        do_save = True

                    if args.chests_open:
                        print(f'{slot_label}: Marking all chests as opened')
                        slot.chests_opened.fill()
                        slot.layer1_chests_opened.fill()
                        do_save = True

                    if args.chests_close:
                        print(f'{slot_label}: Marking all chests as closed')
                        slot.chests_opened.clear()
                        slot.layer1_chests_opened.clear()
                        do_save = True

                    if args.candles_enable:
                        for candle in sorted(args.candles_enable):
                            if candle not in slot.candles.enabled:
                                print(f'{slot_label}: Lighting candle: {candle}')
                                slot.candles.enable(candle)
                                do_save = True

                    if args.candles_disable:
                        for candle in sorted(args.candles_disable):
                            if candle in slot.candles.enabled:
                                print(f'{slot_label}: Blowing out candle: {candle}')
                                slot.candles.disable(candle)
                                do_save = True

                    if args.solve_cranks:
                        print(f'{slot_label}: Setting crank puzzles to "solved" states (excluding Seahorse Boss)')
                        # These values are obviously not the *only* values which work
                        # Water reservoir at (7, 11)
                        slot.cranks[7].value = 464
                        slot.cranks[8].value = 64624
                        # Water reservoir at (4, 15)
                        slot.cranks[13].value = 63840
                        slot.cranks[14].value = 1584
                        slot.cranks[15].value = 32
                        # Sine wave puzzle:
                        slot.cranks[19].value = 40
                        slot.cranks[20].value = 168
                        slot.cranks[21].value = 140
                        do_save = True

                    if args.reservoirs_fill:
                        print(f'{slot_label}: Filling all reservoirs')
                        slot.fill_levels.fill()
                        do_save = True

                    if args.reservoirs_empty:
                        print(f'{slot_label}: Emptying all reservoirs')
                        slot.fill_levels.empty()
                        do_save = True

                    if args.detonators_activate:
                        print(f'{slot_label}: Activating all shortcut detonators')
                        slot.walls_blasted.fill()
                        slot.detonators_triggered.fill()
                        do_save = True

                    if args.detonators_rearm:
                        print(f'{slot_label}: Re-arming all shortcut detonators')
                        if not args.respawn_destroyed_tiles:
                            print('NOTICE: In order to fill in destroyed passageways, also specify --respawn-destroyed-tiles')
                        slot.walls_blasted.clear()
                        slot.detonators_triggered.clear()
                        do_save = True

                    if args.respawn_destroyed_tiles:
                        print(f'{slot_label}: Respawning all destroyed tiles')
                        slot.destructionmap.clear_map()
                        do_save = True

                    if args.big_stalactites_state is not None:
                        print(f'{slot_label}: Setting all big stalactites to state: {args.big_stalactites_state}')
                        slot.big_stalactites.set_state(args.big_stalactites_state)
                        do_save = True

                    if args.small_deposits_break:
                        print(f'{slot_label}: Breaking/clearing all small stalactites/stalagmites/icicles')
                        slot.deposit_small_broken.fill()
                        slot.icicles_broken.fill()
                        do_save = True

                    if args.small_deposits_respawn:
                        print(f'{slot_label}: Respawning all small stalactites/stalagmites/icicles')
                        slot.deposit_small_broken.clear()
                        slot.icicles_broken.clear()
                        do_save = True

                    ###
                    ### Minimap
                    ###

                    if args.reveal_map:
                        print(f'{slot_label}: Revealing entire minimap')
                        slot.minimap.fill_map()
                        do_save = True

                    if args.clear_map:
                        print(f'{slot_label}: Clearing entire minimap')
                        slot.minimap.clear_map(playable_only=False)
                        do_save = True

                    if args.clear_pencil:
                        print(f'{slot_label}: Clearing all minimap pencil drawings')
                        slot.pencilmap.clear_map(playable_only=False)
                        do_save = True

                    if args.clear_stamps:
                        print(f'{slot_label}: Clearing all minimap stamps')
                        slot.stamps.clear()
                        do_save = True

                    if has_image_support:

                        if args.pencil_image_import:
                            print(f'{slot_label}: Importing image "{args.pencil_image_import}" to pencil minimap layer')
                            slot.pencilmap.import_image(
                                    args.pencil_image_import,
                                    args.pencil_image_full,
                                    args.pencil_image_invert,
                                    )
                            do_save = True

                        if args.pencil_image_export:
                            print(f'{slot_label}: Exporting pencil minimap layer to: {args.pencil_image_export}')
                            if check_file_overwrite(args, args.pencil_image_export):
                                slot.pencilmap.export_image(args.pencil_image_export)
                                print('Image exported!')
                            else:
                                print('NOTICE: Pencil minimap data NOT exported')

                    ###
                    ### Actions which we're doing out-of-order intentionally because of
                    ### interactions between args + game state
                    ###

                    # Fix game state for Disc / Mock Disc, if we're modifying those,
                    # unless told otherwise.  See:
                    # https://docs.google.com/spreadsheets/d/1HXG7iUJMF4kKN4oZjtEN8KkaN-RdC6qa3zK74F7bHm0/edit?usp=sharing
                    if doing_disc_actions and args.fix_disc_state:

                        do_save = True

                        if Inventory.MOCK_DISC in slot.inventory.enabled \
                                and Equipment.DISC in slot.equipment.enabled:

                            # Both Disc + Mock Disc
                            print(textwrap.dedent("""
                                *** ERROR ***

                                This slot would have both Disc and Mock Disc active in your inventory,
                                which is not a valid gamestate and can lead to weird behavior depending on
                                what the actual quest state is.  By default, this editor prevents writing
                                that combination, so the savegame edits have been aborted.

                                To allow that combination of items anyway, re-run the command with the
                                following argument added:

                                    --dont-fix-disc-state

                                *** ERROR ***
                                """))
                            return False

                        elif Inventory.MOCK_DISC in slot.inventory.enabled:

                            # Just the Mock Disc.  Ony one valid state here
                            print(f'{slot_label}: Fixing Disc Quest State to accomodate Mock Disc in inventory.  (Specify --dont-fix-disc-state to disable this behavior.)')
                            slot.quest_state.enable(QuestState.STATUE_NO_DISC)
                            slot.quest_state.enable(QuestState.SHRINE_NO_DISC)

                        elif Equipment.DISC in slot.equipment.enabled:

                            # Just the Disc.  A couple valid states here
                            if args.prefer_disc_shrine_state:
                                print(f'{slot_label}: Fixing Disc Quest State to Moved-to-shrine status.  (Specify --dont-fix-disc-state to disable this behavior.)')
                                slot.quest_state.enable(QuestState.STATUE_NO_DISC)
                                slot.quest_state.disable(QuestState.SHRINE_NO_DISC)
                            else:
                                print(f'{slot_label}: Fixing Disc Quest State to initial swap status.  (Specify --dont-fix-disc-state to disable this behavior.)')
                                slot.quest_state.disable(QuestState.STATUE_NO_DISC)
                                slot.quest_state.enable(QuestState.SHRINE_NO_DISC)

                        else:

                            # Neither!  Technically there are two valid states for
                            # this -- you can replace the disc at its original location
                            # after having the Mock Disc in the shrine.  We're going to
                            # ignore that possiblity, though, and just essentially
                            # revert to the game-start state.
                            print(f'{slot_label}: Fixing Disc Quest State to game-start conditions.  (Specify --dont-fix-disc-state to disable this behavior.)')
                            slot.quest_state.disable(QuestState.STATUE_NO_DISC)
                            slot.quest_state.disable(QuestState.SHRINE_NO_DISC)

                    # Doing Quest State alterations down here since we'd probably
                    # want to allow the user to manually override our disc-related
                    # states.
                    if args.quest_state_disable:
                        for quest_state in sorted(args.quest_state_disable):
                            if quest_state in slot.quest_state.enabled:
                                print(f'{slot_label}: Disabling quest state: {quest_state}')
                                slot.quest_state.disable(quest_state)
                                do_save = True

                    if args.quest_state_enable:
                        for quest_state in sorted(args.quest_state_enable):
                            if quest_state not in slot.quest_state.enabled:
                                print(f'{slot_label}: Enabling quest state: {quest_state}')
                                slot.quest_state.enable(quest_state)
                                do_save = True

                else:
                    # If we don't actually have any slot data, don't bother doing anything
                    if args.info:
                        header = f'{slot_label}: No data!'
                        print('')
                        print(header)
                        print('-'*len(header))
                    if do_slot_actions:
                        print(f'{slot_label}: No data detected, so slot modifications skipped')

                # Finally, if we've been told to export slot data, do so now
                if args.export_slot:
                    print(f'{slot_label}: Exporting slot data to: {args.export_slot}')
                    if check_file_overwrite(args, args.export_slot):
                        with open(args.export_slot, 'wb') as df:
                            df.write(slot.export_data())
                        print('Slot data exported!')
                    else:
                        print('NOTICE: Slot data NOT exported')

        # Set frame seed
        if args.frame_seed is not None:
            print(f'Globals: Setting frame seed to: {args.frame_seed}')
            save.frame_seed.value = args.frame_seed
            do_save = True

        # Process global unlockables
        if args.globals_disable:
            for unlock in sorted(args.globals_disable):
                if unlock in save.unlockables.enabled:
                    print(f'Globals: Disabling global unlockable: {unlock}')
                    save.unlockables.disable(unlock)
                    do_save = True

        if args.globals_enable:
            for unlock in sorted(args.globals_enable):
                if unlock not in save.unlockables.enabled:
                    print(f'Globals: Enabling global unlockable: {unlock}')
                    save.unlockables.enable(unlock)
                    do_save = True

        if args.info:
            print('')

        # Write out, if we did anything which needs that
        if do_save:
            if args.invalid_checksum:
                print('NOTICE: Intentionally writing an invalid checksum.  Enjoy hanging out with')
                print('        your Manticore friend!')
            save.save(force_invalid_checksum=args.invalid_checksum)
            print(f'Wrote changes!  New checksum: 0x{save.checksum:02X}')
            return True
        else:
            if do_slot_actions:
                print('No file modifications were necessary!')
            return False

if __name__ == '__main__':
    main()

