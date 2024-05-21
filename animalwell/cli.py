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
from .savegame import Savegame, Equipped, Equipment, Inventory, Egg, Bunny, Teleport, \
        QuestState, FlameState, CandleState


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
            raise ValueError('type must be assigned an Enum when using EnumAction')
        if not issubclass(enum_type, enum.Enum):
            raise TypeError('type must be an Enum when using EnumAction')

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

    parser.add_argument('--health',
            type=int,
            help='Sets health (number of hearts)',
            )

    parser.add_argument('--gold-hearts',
            type=int,
            help='Sets the number of gold hearts',
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

    parser.add_argument('--bubbles-popped',
            type=int,
            help="Set the number of bubbles popped",
            )

    parser.add_argument('--egg-enable',
            type=Egg,
            action=EnumSetAction,
            help="Enable the specified egg.  Can be specified more than once, or use 'all' to enable all",
            )

    parser.add_argument('--bunny-enable',
            type=Bunny,
            action=EnumSetAction,
            help="Enable the specified bunny.  Can be specified more than once, or use 'all' to enable all",
            )

    parser.add_argument('--bunny-disable',
            type=Bunny,
            action=EnumSetAction,
            help="Disable the specified bunny.  Can be specified more than once, or use 'all' to enable all",
            )

    parser.add_argument('--respawn-consumables',
            action='store_true',
            help="Respawn map consumables (fruit and firecrackers)",
            )

    ghost = parser.add_mutually_exclusive_group()

    ghost.add_argument('--clear-ghosts',
            action='store_true',
            help="Clear all ghosts from the map",
            )

    ghost.add_argument('--respawn-ghosts',
            action='store_true',
            help="Respawn ghosts to the map",
            )

    parser.add_argument('--respawn-squirrels',
            action='store_true',
            help="Respawn squirrels to the map",
            )

    parser.add_argument('--firecrackers',
            type=int,
            help="Set the number of firecrackers in your inventory.  Will unlock the Firecracker equipment as well, if not already active",
            )

    parser.add_argument('--keys',
            type=int,
            help="Set the number of keys in your inventory",
            )

    parser.add_argument('--matches',
            type=int,
            help="Set the number of matches in your inventory",
            )

    parser.add_argument('--light-candles',
            type=CandleState,
            action=EnumSetAction,
            help="Light the specified candles.  Can be specified more than once, or use 'all' to enable all",
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

    parser.add_argument('--inventory-enable',
            type=Inventory,
            action=EnumSetAction,
            help="Enable the specified inventory item.  Can be specified more than once, or use 'all' to enable all",
            )

    parser.add_argument('--inventory-disable',
            type=Inventory,
            action=EnumSetAction,
            help="Disable the specified inventory item.  Can be specified more than once, or use 'all' to disable all",
            )

    parser.add_argument('--teleport-enable',
            type=Teleport,
            action=EnumSetAction,
            help="Enable the specified teleport.  Can be specified more than once, or use 'all' to enable all",
            )

    parser.add_argument('--map-enable',
            type=QuestState,
            action=EnumSetAction,
            choices=[
                QuestState.UNLOCK_MAP,
                QuestState.UNLOCK_STAMPS,
                QuestState.UNLOCK_PENCIL,
                ],
            help="Enable the specified map feature.  Can be specified more than once, or use 'all' to enable all",
            )

    parser.add_argument('--reveal-map',
            action='store_true',
            help='Reveals the entire map on the minimap',
            )

    parser.add_argument('--clear-map',
            action='store_true',
            help='Clears the entire map on the minimap',
            )

    parser.add_argument('--clear-pencil',
            action='store_true',
            help='Clears any pencil drawings on the minimap',
            )

    parser.add_argument('--clear-stamps',
            action='store_true',
            help='Clears any stamps on the minimap',
            )

    parser.add_argument('--flame-collect',
            type=str,
            choices=['b', 'p', 'v', 'g', 'all'],
            action='append',
            help="Mark the specified flames as collected (but not placed in the pedestals).  Can be specified more than once, or use 'all' to do all at once",
            )

    parser.add_argument('--flame-use',
            type=str,
            choices=['b', 'p', 'v', 'g', 'all'],
            action='append',
            help="Mark the specified flames as used (but not placed in the pedestals).  Can be specified more than once, or use 'all' to do all at once",
            )

    parser.add_argument('--upgrade-wand',
            action='store_true',
            help='Upgrade the B. Wand to B.B. Wand',
            )

    parser.add_argument('--downgrade-wand',
            action='store_true',
            help='Downgrade the B.B. Wand to B. Wand',
            )

    egg65 = parser.add_mutually_exclusive_group()

    egg65.add_argument('--egg65-enable',
            action='store_true',
            help='Enable Egg 65',
            )

    egg65.add_argument('--egg65-disable',
            action='store_true',
            help='Disable Egg 65',
            )

    cring = parser.add_mutually_exclusive_group()

    cring.add_argument('--cring-enable',
            action='store_true',
            help='Enable C. Ring',
            )

    cring.add_argument('--cring-disable',
            action='store_true',
            help='Disable C. Ring',
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
            args.keys is not None,
            args.matches is not None,
            args.light_candles,
            args.equip_enable,
            args.equip_disable,
            args.inventory_enable,
            args.inventory_disable,
            args.teleport_enable,
            args.map_enable,
            args.reveal_map,
            args.clear_map,
            args.clear_pencil,
            args.clear_stamps,
            args.flame_collect,
            args.flame_use,
            args.upgrade_wand,
            args.downgrade_wand,
            args.egg65_enable,
            args.egg65_disable,
            args.cring_enable,
            args.cring_disable,
            args.spawn,
            args.health is not None,
            args.gold_hearts is not None,
            args.respawn_consumables,
            args.clear_ghosts,
            args.respawn_ghosts,
            args.respawn_squirrels,
            args.egg_enable,
            args.bunny_enable,
            args.bunny_disable,
            args.bubbles_popped,
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
                    if slot.elapsed_ticks_ingame == slot.elapsed_ticks_withpause:
                        print(f' - Elapsed Time: {slot.elapsed_ticks_withpause}')
                    else:
                        print(f' - Elapsed Time: {slot.elapsed_ticks_withpause} (ingame: {slot.elapsed_ticks_ingame})')
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
                    print(f'   - Firecrackers Collected: {slot.firecrackers_collected}')
                    print(f'   - Bubbles Popped: {slot.bubbles_popped}')
                    print(f' - Consumables Inventory:')
                    print(f'   - Firecrackers: {slot.firecrackers}')
                    print(f'   - Keys: {slot.keys}')
                    print(f'   - Matches: {slot.matches}')
                    if slot.equipment.enabled:
                        print(' - Equipment Unlocked:')
                        for equip in sorted(slot.equipment.enabled):
                            print(f'   - {equip}')
                        print(f' - Selected Equipment: {slot.selected_equipment}')
                    if slot.inventory.enabled:
                        print(' - Inventory Unlocked:')
                        for inv in sorted(slot.inventory.enabled):
                            print(f'   - {inv}')
                    print(f' - Eggs Collected: {len(slot.eggs.enabled)}')
                    for egg in sorted(slot.eggs.enabled):
                        print(f'   - {egg}')
                    if len(slot.bunnies.enabled) > 0:
                        print(f' - Bunnies Collected: {len(slot.bunnies.enabled)}')
                        for bunny in sorted(slot.bunnies.enabled):
                            print(f'   - {bunny}')
                    if slot.quest_state.enabled:
                        print(f' - Quest State Flags:')
                        for state in sorted(slot.quest_state.enabled):
                            print(f'   - {state}')
                    if any([flame.choice != FlameState.SEALED for flame in slot.flames]):
                        print(f' - Flame States:')
                        for flame in slot.flames:
                            print(f'   - {flame.name}: {flame}')
                    print(f' - Transient Map Data:')
                    print(f'   - Fruit Picked: {slot.picked_fruit}')
                    print(f'   - Firecrackers Picked: {slot.picked_firecrackers}')
                    print(f'   - Ghosts Scared: {slot.ghosts_scared}')
                    if QuestState.UNLOCK_STAMPS in slot.quest_state.enabled:
                        print(f'   - Minimap Stamps: {len(slot.stamps)}')
                    print(f' - Permanent Map Data:')
                    print(f'   - Squirrels Scared: {slot.squirrels_scared}')
                    print(f'   - Chests Opened: {slot.chests_opened}')
                    print(f'   - Yellow Buttons Pressed: {slot.yellow_buttons_pressed}')
                    print(f'   - Button-Activated Doors Opened: {slot.button_doors_opened}')
                    print(f'   - Detonators Triggered: {slot.detonators_triggered}')
                    print(f'   - Walls Blasted: {slot.walls_blasted}')
                    if slot.teleports.enabled:
                        print(f' - Teleports Active: {len(slot.teleports.enabled)}')
                        for teleport in sorted(slot.teleports.enabled):
                            print(f'   - {teleport}')

                    if do_slot_actions:
                        print('')

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

                if args.egg_enable:
                    for egg in sorted(args.egg_enable):
                        if egg not in slot.eggs.enabled:
                            print(f'{slot_label}: Enabling egg: {egg}')
                            slot.eggs.enable(egg)
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

                if args.keys is not None:
                    print(f'{slot_label}: Updating key count to: {args.keys}')
                    slot.keys.value = args.keys
                    do_save = True

                if args.matches is not None:
                    print(f'{slot_label}: Updating match count to: {args.matches}')
                    slot.matches.value = args.matches
                    do_save = True

                if args.light_candles:
                    for candle in sorted(args.light_candles):
                        if candle not in slot.candles.enabled:
                            print(f'{slot_label}: Lighting candle: {candle}')
                            slot.candles.enable(candle)
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

                if args.equip_enable:
                    for equip in sorted(args.equip_enable):
                        if equip not in slot.equipment.enabled:
                            print(f'{slot_label}: Enabling equipment: {equip}')
                            slot.equipment.enable(equip)
                            changed_equipment = True
                            do_save = True

                if args.equip_disable:
                    for equip in sorted(args.equip_disable):
                        if equip in slot.equipment.enabled:
                            print(f'{slot_label}: Disabling equipment: {equip}')
                            slot.equipment.disable(equip)
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

                if args.inventory_disable:
                    for inv in sorted(args.inventory_disable):
                        if inv in slot.inventory.enabled:
                            print(f'{slot_label}: Disabling inventory item: {inv}')
                            slot.inventory.disable(inv)
                            do_save = True

                if args.inventory_enable:
                    for inv in sorted(args.inventory_enable):
                        if inv not in slot.inventory.enabled:
                            print(f'{slot_label}: Enabling inventory item: {inv}')
                            slot.inventory.enable(inv)
                            do_save = True

                if args.teleport_enable:
                    for teleport in sorted(args.teleport_enable):
                        if teleport not in slot.teleports.enabled:
                            print(f'{slot_label}: Enabling teleport: {teleport}')
                            slot.teleports.enable(teleport)
                            do_save = True

                if args.map_enable:
                    for map_var in sorted(args.map_enable):
                        if map_var not in slot.quest_state.enabled:
                            print(f'{slot_label}: Enabling map unlock: {map_var}')
                            slot.quest_state.enable(map_var)
                            do_save = True

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
                        print(f'{slot_label}: Unlocking C. Ring')
                        slot.quest_state.enable(QuestState.CRING)
                        do_save = True

                if args.cring_disable:
                    if QuestState.CRING in slot.quest_state.enabled:
                        print(f'{slot_label}: Removing C. Ring')
                        slot.quest_state.disable(QuestState.CRING)
                        do_save = True

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

        if args.info:
            print('')

        # Write out, if we did anything which needs that
        if do_save:
            save.save()
            print(f'Wrote changes!  New checksum: 0x{save.checksum:02X}')

if __name__ == '__main__':
    main()

