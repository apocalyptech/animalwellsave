#!/usr/bin/env python3
# vim: set expandtab tabstop=4 shiftwidth=4:

# Copyright (C) 2024 Christopher J. Kucera
#
# pyanimalwell is free software: you can redistribute it and/or modify
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
import argparse
import collections
from .savegame import Savegame, Equipped, Equipment


class EnumSetAction(argparse.Action):
    """
    Argparse Action to set Enum members as the arg `choices`, adding them
    to a set as they are chosen by the user.  Also hardcodes an `all`
    choice which can be used to add all available Enum members to the
    argument set.

    Derived partially from https://stackoverflow.com/a/70124136/2013126
    """

    def __init__(self, **kwargs):

        # Grab the specified argument type and ensure it's an Enum
        enum_type = kwargs.pop('type', None)
        if enum_type is None:
            raise ValueError('type must be assigned an Enum when using EnumAction')
        if not issubclass(enum_type, enum.Enum):
            raise TypeError('type must be an Enum when using EnumAction')

        # Set the available choices, including the "all" option
        kwargs.setdefault(
                'choices',
                tuple(e.name.lower() for e in enum_type) + ('all',)
                )

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
                for item in self._enum:
                    arg_value.add(item)
            else:
                this_value = self._enum[uppercase]
                arg_value.add(this_value)
            setattr(namespace, self.dest, arg_value)
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


def main():

    parser = argparse.ArgumentParser(
            description='CLI Animal Well Savegame Editor',
            )

    parser.add_argument('-i', '--info',
            action='store_true',
            help='Show known information about the save',
            )

    parser.add_argument('-s', '--slot',
            choices=[0, 1, 2, 3],
            type=int,
            help='Operate on the specified slot (specify 0 for "all slots")',
            )

    parser.add_argument('--spawn',
            type=str,
            metavar='X,Y',
            action=CoordAction,
            help='Room coordinates to spawn in.  Specify two numbers with a comma inbetwen them, such as "11,11" for the main hallway.',
            )

    parser.add_argument('--steps',
            type=int,
            help="Set the number of steps taken",
            )

    parser.add_argument('--deaths',
            type=int,
            help="Set the number of deaths",
            )

    parser.add_argument('--saves',
            type=int,
            help="Set the number of times-saved",
            )

    parser.add_argument('--firecrackers',
            type=int,
            help="Set the number of firecrackers.  Will unlock the Firecracker equipment as well, if not already active",
            )

    parser.add_argument('--equip-enable',
            type=Equipment,
            action=EnumSetAction,
            help="Enable the specified equipment.  Can be specified more than once, or use 'all' to enable all",
            )

    parser.add_argument('--equip-disable',
            type=Equipment,
            action=EnumSetAction,
            help="Disable the specified equipment.  Can be specified more than once, or use 'all' to disable all",
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
            args.steps is not None,
            args.deaths is not None,
            args.saves is not None,
            args.firecrackers is not None,
            args.equip_enable,
            args.equip_disable,
            args.spawn,
            ]):
        if slot_indexes:
            loop_into_slots = True
            do_slot_actions = True
        else:
            parser.error('Slot actions were specified but no slots were chosen')

    # Load the savegame
    with Savegame(args.filename) as save:
        
        if args.info:
            header = f'Animal Well Savegame v{save.version}'
            print(header)
            print('-'*len(header))
            print('')
            print(f' - Checksum: 0x{save.checksum:02X}')

        # Process slots, if we've been told to
        if loop_into_slots:
            for slot_idx in slot_indexes:
                slot = save.slots[slot_idx]
                slot_label = f'Slot {slot.index+1}'

                # If we don't actually have any slot data, don't bother doing anything
                if not slot.has_data:
                    if args.info:
                        header = f'{slot_label}: No data!'
                        print('')
                        print(header)
                        print('-'*len(header))
                    if do_slot_actions:
                        print(f'{slot_label}: No data detected, so slot modifications skipped')
                    continue

                # Show general slot info first, if we've been told to
                if args.info:
                    header = f'{slot_label}: {slot.timestamp}'
                    print('')
                    print(header)
                    print('-'*len(header))
                    print('')
                    print(f' - Saved in Room: {slot.spawn_room}')
                    print(f' - Times Saved: {slot.num_saves}')
                    print(f' - Times Died: {slot.num_deaths}')
                    print(f' - Steps: {slot.num_steps:,}')
                    print(f' - Health: {slot.health}')
                    if slot.equipment.enabled:
                        print(' - Equipment Unlocked:')
                        for equip in sorted(slot.equipment.enabled):
                            print(f'   - {equip}')
                        print(f' - Selected Equipment: {slot.selected_equipment}')
                    if slot.inventory.enabled:
                        print(' - Inventory Unlocked:')
                        for inv in sorted(slot.inventory.enabled):
                            print(f'   - {inv}')
                    print(f' - Firecrackers: {slot.firecrackers}')
                    if slot.elapsed_ticks_ingame == slot.elapsed_ticks_withpause:
                        print(f' - Elapsed Time: {slot.elapsed_ticks_withpause}')
                    else:
                        print(f' - Elapsed Time: {slot.elapsed_ticks_withpause} (ingame: {slot.elapsed_ticks_ingame})')
                    if do_slot_actions:
                        print('')

                if args.spawn:
                    print(f'{slot_label}: Setting spawnpoint to ({args.spawn.x}, {args.spawn.y})')
                    slot.spawn_room.x.value = args.spawn.x
                    slot.spawn_room.y.value = args.spawn.y
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

                if args.firecrackers is not None:
                    print(f'{slot_label}: Updating firecracker count to: {args.firecrackers}')
                    slot.firecrackers.value = args.firecrackers
                    do_save = True
                    if args.firecrackers > 0 and Equipment.FIRECRACKER not in slot.equipment.enabled:
                        if args.equip_enable is None:
                            args.equip_enable = set()
                        args.equip_enable.add(Equipment.FIRECRACKER)

                changed_equipment = False

                if args.equip_disable:
                    for equip in sorted(args.equip_disable):
                        if equip in slot.equipment.enabled:
                            print(f'{slot_label}: Disabling equipment: {equip}')
                            slot.equipment.disable(equip)
                            changed_equipment = True
                            do_save = True

                if args.equip_enable:
                    for equip in sorted(args.equip_enable):
                        if equip not in slot.equipment.enabled:
                            print(f'{slot_label}: Enabling equipment: {equip}')
                            slot.equipment.enable(equip)
                            changed_equipment = True
                            do_save = True

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

        if args.info:
            print('')

        # Write out, if we did anything which needs that
        if do_save:
            save.save()
            print(f'Wrote changes!  New checksum: 0x{save.checksum:02X}')

if __name__ == '__main__':
    main()
