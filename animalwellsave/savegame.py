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
import io
import sys
import enum
import struct
import collections

from .datafile import UInt8, UInt16, UInt32, UInt64, Float, \
        Data, NumData, \
        NumChoiceData, NumBitfieldData, BitCountData, \
        LabelEnum

try:
    from PIL import Image
    has_image_support = True
except ModuleNotFoundError:
    has_image_support = False

# Animal Well savegame descriptions / format

class Equipped(LabelEnum):
    """
    The currently-equipped item
    """

    NONE =        (0x0, 'None')
    FIRECRACKER = (0x1, 'Firecracker')
    FLUTE =       (0x2, 'Flute')
    LANTERN =     (0x3, 'Lantern')
    TOP =         (0x4, 'Top')
    DISC =        (0x5, 'Disc')
    WAND =        (0x6, 'B. Wand')
    YOYO =        (0x7, 'Yoyo')
    SLINK =       (0x8, 'Slink')
    REMOTE =      (0x9, 'Remote')
    BALL =        (0xA, 'Ball')
    WHEEL =       (0xB, 'Wheel')
    UVLIGHT =     (0xC, 'UV Light')


class Equipment(LabelEnum):
    """
    Base Equipment unlocks
    """

    FIRECRACKER = (0x0002, 'Firecracker')
    FLUTE =       (0x0004, 'Flute')
    LANTERN =     (0x0008, 'Lantern')
    TOP =         (0x0010, 'Top')
    DISC =        (0x0020, 'Disc')
    WAND =        (0x0040, 'B. Wand')
    YOYO =        (0x0080, 'Yoyo')
    SLINK =       (0x0100, 'Slink')
    REMOTE =      (0x0200, 'Remote')
    BALL =        (0x0400, 'Ball')
    WHEEL =       (0x0800, 'Wheel')
    UVLIGHT =     (0x1000, 'UV Light')


class Inventory(LabelEnum):
    """
    Inventory unlocks
    """

    MOCK_DISC =  (0x01, 'Mock Disc')
    S_MEDAL =    (0x02, 'S. Medal')
    # Don't bother with this one for now
    #CAKE    =    (0x04, 'Cake')
    HOUSE_KEY =  (0x08, 'House Key')
    OFFICE_KEY = (0x10, 'Office Key')
    # Eh, don't bother with this one for now
    #UNUSED_KEY = (0x20, 'Unused Key')
    E_MEDAL =    (0x40, 'E. Medal')
    PACK =       (0x80, 'F. Pack')


class QuestState(LabelEnum):
    """
    Various quest-related states.  Some of this acts like inventory items,
    but it's a bit of a grab bag.
    """

    HOUSE_OPEN =         (0x00000001, 'House Open')
    OFFICE_OPEN =        (0x00000002, 'Office Open')
    CLOSET_OPEN =        (0x00000004, 'Closet Open')
    # Global switch state -- 0 for left, 1 for right.  Leaving this out for now though
    #SWITCH_STATE =       (0x00000100, 'Switch State')
    UNLOCK_MAP =         (0x00000200, 'Map Unlocked')
    UNLOCK_STAMPS =      (0x00000400, 'Stamps Unlocked')
    UNLOCK_PENCIL =      (0x00000800, 'Pencil Unlocked')
    DEFEATED_CHAMELEON = (0x00001000, 'Defeated Chameleon')
    CRING =              (0x00002000, "Cheater's Ring")
    # Not doing this one either
    #EATEN_BY_CHAMELEON = (0x00004000, "Eaten by Chameleon")
    USED_S_MEDAL =       (0x00008000, "Inserted S. Medal")
    USED_E_MEDAL =       (0x00010000, "Inserted E. Medal")
    WINGS =              (0x00020000, "Wings / Flying Unlocked")
    # Eh, don't bother with this one
    #WOKE_UP =           (0x00040000, 'Woke Up (start of game)')
    BB_WAND =            (0x00080000, 'B.B. Wand Upgrade')
    EGG_65 =             (0x00100000, 'Egg 65')
    # Don't bother with this one; the necessary door opens with
    # just the actual lighting.
    #ALL_CANDLES =       (0x00200000, 'All Candles Lit')
    TORUS =              (0x00400000, 'Teleport Torus Active')
    # Eh, not gonna do this one either; easy enough to just do it.
    #MANTICORE_EGG =     (0x00800000, 'Manticore Egg Placed')
    DEFEATED_BAT =       (0x01000000, 'Defeated Bat')
    FREED_OSTRICH =      (0x02000000, 'Freed Wheel Ostrich')
    DEFEATED_OSTRICH =   (0x04000000, 'Defeated Wheel Ostrich')
    FIGHTING_EEL =       (0x08000000, 'Fighting Eel')
    DEFEATED_EEL =       (0x10000000, 'Defeated Eel')
    SHRINE_NO_DISC =     (0x20000000, 'No Disc in Dog Shrine')
    STATUE_NO_DISC =     (0x40000000, 'No Disc in Dog Head Statue')


class Egg(LabelEnum):
    """
    Eggs!
    """

    REFERENCE = (0x0000000000000001, 'Reference')
    BROWN =     (0x0000000000000002, 'Brown')
    RAW =       (0x0000000000000004, 'Raw')
    PICKLED =   (0x0000000000000008, 'Pickled')
    BIG =       (0x0000000000000010, 'Big')
    SWAN =      (0x0000000000000020, 'Swan')
    FORBIDDEN = (0x0000000000000040, 'Forbidden')
    SHADOW =    (0x0000000000000080, 'Shadow')

    VANITY =      (0x0000000000000100, 'Vanity')
    SERVICE =     (0x0000000000000200, 'Egg as a Service')
    DEPRAVED =    (0x0000000000000400, 'Depraved')
    CHAOS =       (0x0000000000000800, 'Chaos')
    UPSIDE_DOWN = (0x0000000000001000, 'Upside Down')
    EVIL =        (0x0000000000002000, 'Evil')
    SWEET =       (0x0000000000004000, 'Sweet')
    CHOCOLATE =   (0x0000000000008000, 'Chocolate')

    VALUE =           (0x0000000000010000, 'Value')
    PLANT =           (0x0000000000020000, 'Plant')
    RED =             (0x0000000000040000, 'Red')
    ORANGE =          (0x0000000000080000, 'Orange')
    SOUR =            (0x0000000000100000, 'Sour')
    POST_MODERN =     (0x0000000000200000, 'Post Modern')
    UNIVERSAL_BASIC = (0x0000000000400000, 'Universal Basic')
    LAISSEZ_FAIRE =   (0x0000000000800000, 'Laissez-Faire')

    ZEN =            (0x0000000001000000, 'Zen')
    FUTURE =         (0x0000000002000000, 'Future')
    FRIENDSHIP =     (0x0000000004000000, 'Friendship')
    TRUTH =          (0x0000000008000000, 'Truth')
    TRANSCENDENTAL = (0x0000000010000000, 'Transcendental')
    ANCIENT =        (0x0000000020000000, 'Ancient')
    MAGIC =          (0x0000000040000000, 'Magic')
    MYSTIC =         (0x0000000080000000, 'Mystic')

    HOLIDAY =  (0x0000000100000000, 'Holiday')
    RAIN =     (0x0000000200000000, 'Rain')
    RAZZLE =   (0x0000000400000000, 'Razzle')
    DAZZLE =   (0x0000000800000000, 'Dazzle')
    VIRTUAL =  (0x0000001000000000, 'Virtual')
    NORMAL =   (0x0000002000000000, 'Normal')
    GREAT =    (0x0000004000000000, 'Great')
    GORGEOUS = (0x0000008000000000, 'Gorgeous')

    PLANET =    (0x0000010000000000, 'Planet')
    MOON =      (0x0000020000000000, 'Moon')
    GALAXY =    (0x0000040000000000, 'Galaxy')
    SUNSET =    (0x0000080000000000, 'Sunset')
    GOODNIGHT = (0x0000100000000000, 'Goodnight')
    DREAM =     (0x0000200000000000, 'Dream')
    TRAVEL =    (0x0000400000000000, 'Travel')
    PROMISE =   (0x0000800000000000, 'Promise')

    ICE =        (0x0001000000000000, 'Ice')
    FIRE =       (0x0002000000000000, 'Fire')
    BUBBLE =     (0x0004000000000000, 'Bubble')
    DESERT =     (0x0008000000000000, 'Desert')
    CLOVER =     (0x0010000000000000, 'Clover')
    BRICK =      (0x0020000000000000, 'Brick')
    NEON =       (0x0040000000000000, 'Neon')
    IRIDESCENT = (0x0080000000000000, 'Iridescent')

    RUST =     (0x0100000000000000, 'Rust')
    SCARLET =  (0x0200000000000000, 'Scarlet')
    SAPPHIRE = (0x0400000000000000, 'Sapphire')
    RUBY =     (0x0800000000000000, 'Ruby')
    JADE =     (0x1000000000000000, 'Jade')
    OBSIDIAN = (0x2000000000000000, 'Obsidian')
    CRYSTAL =  (0x4000000000000000, 'Crystal')
    GOLDEN =   (0x8000000000000000, 'Golden')


class Bunny(LabelEnum):
    """
    Bunnies!  This enum omits all the illegal/invalid bunnies, which are
    stored in a separate enum.  The commented number afterwards is the
    pillar next to which the bunny spawns, in Space / Bunny Island.  (Those
    numbers are commonly-reported by online guides, etc.)
    """

    TUTORIAL =      (0x00000001, 'Tutorial') #4
    ORIGAMI =       (0x00000004, 'Origami') #17
    CROW =          (0x00000008, 'Crow') #10
    GHOST =         (0x00000010, 'Ghost') #9
    FISH_MURAL =    (0x00000040, 'Fish Mural') #8
    MAP =           (0x00000080, 'Map Numbers') #5
    TV =            (0x00000100, 'TV') #16
    UV =            (0x00000200, 'UV') #7
    BULB =          (0x00000400, 'Bulb') #13
    CHINCHILLA =    (0x00000800, 'Chinchilla') #2
    BUNNY_MURAL =   (0x00008000, 'Bunny Mural') #1
    DUCK =          (0x00400000, 'Duck') #11
    GHOST_DOG =     (0x02000000, 'Ghost Dog') #18
    DREAM =         (0x10000000, 'Dream') #12
    FLOOR_IS_LAVA = (0x40000000, 'Floor Is Lava') #14
    SPIKE_ROOM =    (0x80000000, 'Spike Room') #20


class IllegalBunny(LabelEnum):
    """
    Illegal Bunnies!  We've got a separate enum for these so that the
    editor can support clearing them from a slot, to recover a save which
    would be otherwise unable to solve BDTP.  At time of writing I'm not
    adding a function to *add* illegal bunnies, though perhaps it'd
    be worth doing.
    """

    ILL_01 = (0x00000002, 'Illegal 1')
    ILL_02 = (0x00000020, 'Illegal 2')
    ILL_03 = (0x00001000, 'Illegal 3')
    ILL_04 = (0x00002000, 'Illegal 4')
    ILL_05 = (0x00004000, 'Illegal 5')
    ILL_06 = (0x00010000, 'Illegal 6')
    ILL_07 = (0x00020000, 'Illegal 7')
    ILL_08 = (0x00040000, 'Illegal 8')
    ILL_09 = (0x00080000, 'Illegal 9')
    ILL_10 = (0x00100000, 'Illegal 10')
    ILL_11 = (0x00200000, 'Illegal 11')
    ILL_12 = (0x00800000, 'Illegal 12')
    ILL_13 = (0x01000000, 'Illegal 13')
    ILL_14 = (0x04000000, 'Illegal 14')
    ILL_15 = (0x08000000, 'Illegal 15')
    ILL_16 = (0x20000000, 'Illegal 16')


class EggDoor(LabelEnum):
    """
    Unlocked doors in the Egg Chamber
    """

    FIRST =  (0x1, 'First (Flute, Portal)')
    SECOND = (0x2, 'Second (Pencil)')
    THIRD =  (0x4, 'Third (Top)')
    FOURTH = (0x8, 'Fourth (65th Egg)')


class Teleport(LabelEnum):
    """
    Active teleporters
    """
    FROG =     (0x02, 'Frog')
    FISH =     (0x04, 'Fish')
    BEAR =     (0x08, 'Bear')
    DOG =      (0x10, 'Dog')
    BIRD =     (0x20, 'Bird')
    SQUIRREL = (0x40, 'Squirrel')
    HIPPO =    (0x80, 'Hippo')


class FlameState(LabelEnum):
    """
    Used for storing the flame states
    """

    SEALED = (0, 'Sealed')
    CRACKED_1 = (1, 'Glass Cracked')
    CRACKED_2 = (2, 'Glass Cracked More')
    BROKEN = (3, 'Glass Broken')
    COLLECTED = (4, 'Collected')
    USED = (5, 'Used')


class CandleState(LabelEnum):
    """
    Used to keep track of which candles are lit in the game.  The
    names are the room coordinates where they're found
    """

    ROOM_04_06 = (0x001, 'Room (4, 6)');
    ROOM_08_06 = (0x002, 'Room (8, 6)');
    ROOM_04_07 = (0x004, 'Room (4, 7)');
    ROOM_06_07 = (0x008, 'Room (6, 7)');
    ROOM_06_09 = (0x010, 'Room (6, 9)');
    ROOM_15_09 = (0x020, 'Room (15, 9)');
    ROOM_05_13 = (0x040, 'Room (5, 13)');
    ROOM_10_13 = (0x080, 'Room (10, 13)');
    ROOM_16_13 = (0x100, 'Room (16, 13)');


class StampIcon(LabelEnum):
    """
    Icons used for minimap stamps
    """

    CHEST =    (0, 'Chest')
    HEART =    (1, 'Heart')
    SKULL =    (2, 'Skull')
    DIAMOND =  (3, 'Diamond')
    SPIRAL =   (4, 'Spiral')
    FLAME =    (5, 'Flame')
    GRID =     (6, 'Grid')
    QUESTION = (7, 'Question')


class Unlockable(LabelEnum):
    """
    Various global unlockables, which apply outside of slots
    """

    STOPWATCH =         (0x00001, 'Stopwatch')
    PEDOMETER =         (0x00002, 'Pedometer')
    PINK_PHONE =        (0x00004, 'Pink Phone')
    SOUVENIR_CUP =      (0x00008, 'Souvenir Cup')
    ORIGAMI =           (0x00010, 'Origami Figurines')
    TWO_RABBITS =       (0x00020, 'Two Rabbits')
    OWL =               (0x00040, 'Owl Figurine')
    CAT =               (0x00080, 'Cat Figurine')
    FISH =              (0x00100, 'Fish Figurine')
    DONKEY =            (0x00200, 'Donkey Figurine')
    DECO_RABBIT =       (0x00400, 'Decorative Rabbit')
    MAMA_CHA =          (0x00800, 'mama cha')
    GIRAFFE =           (0x01000, 'Giraffe Figurine')
    INCENSE =           (0x02000, 'Incense Burner')
    PEACOCK =           (0x04000, 'Peacock Figurine')
    OTTER =             (0x08000, 'Otter Figurine')
    DUCK =              (0x10000, 'Duck Figurine')
    PEDOMETER_UNICODE = (0x40000, 'Pedometer Unicode Chest')


class KangarooShardState(LabelEnum):
    """
    The state that an individual K. Shard can be in
    """

    NONE = (0, 'None')
    DROPPED = (1, 'Dropped')
    COLLECTED = (2, 'Collected')
    INSERTED = (3, 'Inserted')


class PinkButton(LabelEnum):
    """
    Pink buttons that we're willing to set.  This omits the ones associated with
    "illegal" bunnies, since opening up those walls can end up destroying
    savefiles.
    """

    SPIKE =         (0x002, 'Spike Bunny')
    FLOOR_IS_LAVA = (0x004, 'Floor Is Lava Bunny')
    MAP_NUMBER =    (0x010, 'Map Number Bunny')
    DOG_WHEEL =     (0x020, 'Elevator Dog Wheel')
    CHINCHILLA =    (0x040, 'Chinchilla Bunny')
    BULB =          (0x080, 'Bulb Bunny')
    PORTAL =        (0x200, 'Lower Portal Nexus')


class PinkButtonInvalid(LabelEnum):
    """
    Pink buttons that we are *unwilling* to set ourselves, but which we'll
    provide a way to clear out, in case the user had hit them at some point.
    """

    ILL_01 = (0x001, 'Illegal Bunny 1')
    ILL_02 = (0x008, 'Illegal Bunny 2')
    ILL_03 = (0x100, 'Illegal Bunny 3')


class CatStatus(LabelEnum):
    """
    Status of caged cats (and the caged wheel you can get as a reward)
    """

    CAT_16_18_1 = (0x01, 'Caged Cat 1 at 16,18')
    CAT_16_18_2 = (0x02, 'Caged Cat 2 at 16,18')
    CAT_16_18_3 = (0x04, 'Caged Cat 3 at 16,18')
    CAT_14_19_1 = (0x08, 'Caged Cat 1 at 14,19')
    CAT_14_19_2 = (0x10, 'Caged Cat 2 at 14,19')
    WHEEL =       (0x20, 'Caged Wheel')


class ManticoreState(LabelEnum):
    """
    Just a little state enum for what each Manticore is up to.
    """

    DEFAULT =   (0x0, 'Default')
    OVERWORLD = (0x1, 'Overworld')
    SPACE =     (0x2, 'In Space')


class Progress(LabelEnum):
    """
    Various progress flags; these are *mostly* very early-game (and in the
    010 Editor / ImHex patterns they're labelled as StartupState), but
    there's also one in here for the house key being dropped, so I'm using
    a more generic name here.
    """

    # Actually, don't bother reporting on these first two
    #STARTED =   (0x01, 'Game Started')
    #HATCH =     (0x04, 'Ready to Hatch')
    HP_BAR =    (0x08, 'Show HP Bar')
    HOUSE_KEY = (0x10, 'Drop House Key')


class ElevatorDirection(LabelEnum):
    """
    Bitfield which controls which direction the reversible elevators are
    going in the game.
    """

    BLUE_RAT = (0x1, 'Blue Rat (0: down, 1: up)')
    RED_RAT =  (0x2, 'Red Rat (0: right, 1: left)')
    OSTRICH =  (0x4, 'Ostrich (0: right, 1: left)')
    DOG =      (0x8, 'Dog (0: down, 1: up)')


class ElevatorDisabled(LabelEnum):
    """
    Bitfield to define if the specified elevators have been disabled.
    There are three elevators marked as disabled at the start of the game:
    5, 6, and 7.  Presumably these are the ones which are *only* moveable
    with manual intervention using the Wheel.

    Elevator 3 is the Wheel Ostrich "elevator," which will get added to
    the disabled list when the ostrich is freed.
    """

    E1 =      (0x01, 'Elevator 1')
    E2 =      (0x02, 'Elevator 2')
    OSTRICH = (0x04, 'Wheel Ostrich Platforms')
    E4 =      (0x08, 'Elevator 4')
    E5 =      (0x10, 'Elevator 5')
    E6 =      (0x20, 'Elevator 6')
    E7 =      (0x40, 'Elevator 7')
    E8 =      (0x80, 'Elevator 8')


class KangarooActivityState(LabelEnum):
    """
    The current state of the kangaroo.

     - State 0: Initial Encounter.  This is only present in the game when
       you have yet to encounter the kangaroo.  In this state the kangaroo's
       room will always be room 4 (16,16).  The kangaroo will likely not
       spawn if it's set to other rooms with this state.

     - State 1: Lurking.  This is the "safest" to set, if you want to force
       the kangaroo to be present in a specific room.  It may not be there from
       the very beginning, but the player should be able to trigger it to go
       into attacking mode (which I believe is just based on passing a physical
       trigger in the room itself).

     - State 2: Attacking.  This is the active attack state.  So long as the
       player remains within 1 room of the kangaroo room, it'll keep attacking
       in that room, but if the player gets further away, the kangaroo despawns
       and moves onto the next room.
    """

    INITIAL = (0, 'Initial Encounter')
    LURKING = (1, 'Lurking')
    ATTACKING = (2, 'Attacking')


class BigStalactiteState(LabelEnum):
    """
    The state of an individual big stalactite.
    """

    INTACT =              (0, 'Intact')
    CRACKED_ONCE =        (1, 'Cracked Once')
    CRACKED_TWICE =       (2, 'Cracked Twice')
    FLOOR =               (3, 'On the Floor')
    FLOOR_CRACKED_ONCE =  (4, 'On the Floor, Cracked Once')
    FLOOR_CRACKED_TWICE = (5, 'On the Floor, Cracked Twice')
    BROKEN =              (6, 'Broken')


class Timestamp(Data):
    """
    Timestamp class -- this is only actually seen at the very beginning of
    each slot, and shown on the "load game" dialog in-game.
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        # Data
        self.year = NumData('Year', self, UInt16)
        self.month = NumData('Month', self, UInt8)
        self.day = NumData('Day', self, UInt8)
        self.hour = NumData('Hour', self, UInt8)
        self.minute = NumData('Minute', self, UInt8)
        self.second = NumData('Second', self, UInt8)

        # If all fields are zero, assume that the slot is empty
        self.has_data = any([
            self.year.value != 0,
            self.month.value != 0,
            self.day.value != 0,
            self.hour.value != 0,
            self.minute.value != 0,
            self.second.value != 0,
            ])

    def __str__(self):
        return f'{self.year:04d}-{self.month:02d}-{self.day:02d} {self.hour:02d}:{self.minute:02d}:{self.second:02d}'


class Flame(NumChoiceData):
    """
    A single flame status.  This is just a NumChoiceData with an explicit
    `name` attribute, so that utilities can report on which flame is
    being used, when iterating over the whole set.
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, UInt8, FlameState)
        self.name = self.debug_label


class Flames(Data):
    """
    Structure to hold information about all the collectible flames in the game.
    Provides iteration and lookup by lowercase letter, in addition to the
    single-letter attributes.
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        # Data
        self.b = Flame('B. Flame', self)
        self.p = Flame('P. Flame', self)
        self.v = Flame('V. Flame', self)
        self.g = Flame('G. Flame', self)

        self.flames = [self.b, self.p, self.v, self.g]
        self._by_letter = {
                'b': self.b,
                'p': self.p,
                'v': self.v,
                'g': self.g,
                }

    def __iter__(self):
        """
        Can iterate over all four flames
        """
        return iter(self.flames)

    def __getitem__(self, key):
        """
        Can also lookup flames by lowercase letter (mostly just to support
        the CLI util a bit more easily)
        """
        return self._by_letter[key]


class Ticks(NumData):
    """
    Number of ticks elapsed since the slot start.  Slots have a couple
    of these -- one for ingame time (which isn't really used by anything
    AFAIK), and one which includes time spent in the pause menu.

    The game runs at 60fps, so we *cannot* just plug this into a `timedelta`
    object as milliseconds -- we'd have to convert back and forth, which
    doesn't seem worth the hassle.

    Datawise this is just a UInt32.
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, UInt32, offset=offset)
        self._last_string = None
        self._stringval = None

    def __str__(self):
        """
        Report the delta in the same format as the game itself
        """
        if self.value != self._last_string:
            self._last_string = self.value
            seconds, ticks = divmod(self.value, 60)
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            self._stringval = f'{hours:d}:{minutes:02d}:{seconds:02d}:{ticks:02d}'
        return self._stringval

    def __format__(self, format_str):
        """
        Format using our string representation instead of raw numeric data
        """
        format_str = '{:' + format_str + '}'
        return format_str.format(str(self))


class MapCoord(Data):
    """
    Map coordinate, mostly just used for defining the spawnpoint.  This
    is two UInt32s, for X and Y.  Note that the map itself is 20x24,
    even though the playable map is only 16x16.  The playable map is
    centered, so four "padding" rooms on the top and bottom, and two
    "padding" rooms on the left and right.  The upper-left-most playable
    coordinate is (2, 4).
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        self.x = NumData('X', self, UInt32)
        self.y = NumData('Y', self, UInt32)

    def __str__(self):
        """
        String representation should be the full coordinate tuple
        """
        return f'({self.x}, {self.y})'


class Minimap(Data):
    """
    Class to hold minimap information.  At time of writing we don't have
    "generic" drawing functions to let us say "turn pixel x,y on/off".
    The functions are very geared towards filling/clearing big chunks
    of data; the minimum resolution they work with is really whole rooms.
    """

    # Room dimensions in pixels
    ROOM_W = 40
    ROOM_H = 22
    ROOM_BYTE_W = int(ROOM_W/8)

    # Total minimap room dimensions -- this includes "empty" padding
    # rooms on both the top and bottom
    MAP_ROOM_W = 20
    MAP_ROOM_H = 24
    MAP_BYTE_W = ROOM_BYTE_W*MAP_ROOM_W
    MAP_BYTE_ROOM_H = ROOM_BYTE_W*ROOM_H*MAP_ROOM_W
    MAP_BYTE_TOTAL = MAP_BYTE_ROOM_H*MAP_ROOM_H

    # "Playable" minimap room dimensions
    MAP_PLAYABLE_ROOM_W = 16
    MAP_PLAYABLE_ROOM_H = 16
    MAP_PLAYABLE_ROOM_START = (2, 4)
    MAP_PLAYABLE_BYTE_W = ROOM_BYTE_W*MAP_PLAYABLE_ROOM_W

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        # Subsequent data might rely on us having seeked to the end of the
        # data, so do so now.
        self.df.seek(Minimap.MAP_BYTE_TOTAL, os.SEEK_CUR)

    def room_start_offset(self, x, y):
        """
        Computes the starting offset (upper left corner) within our data for
        the given room coordinate
        """
        return self.offset + y*Minimap.MAP_BYTE_ROOM_H + (x*Minimap.ROOM_BYTE_W)

    def _inner_fill(self, initial_location, row_fill, num_pixel_rows):
        """
        Inner function to assist in filling areas of the map.  `initial_location`
        should be the upper-left corner of where to fill.  `row_fill` is the data
        that will be written into each row.  `num_pixel_rows` is the number of
        rows to fill in.
        """
        skip_size = Minimap.MAP_BYTE_W - len(row_fill)
        self.df.seek(initial_location)
        for _ in range(num_pixel_rows):
            self.df.write(row_fill)
            self.df.seek(skip_size, os.SEEK_CUR)

    def fill_room(self, x, y, fill_byte=b'\xFF'):
        """
        Fills in the specified room.
        """
        self._inner_fill(
                self.room_start_offset(x, y),
                fill_byte * Minimap.ROOM_BYTE_W,
                Minimap.ROOM_H,
                )

    def clear_room(self, x, y):
        """
        Fills in the specified room.
        """
        self.fill_room(x, y, fill_byte=b'\x00')

    def fill_map(self, playable_only=True, fill_byte=b'\xFF'):
        """
        Fills in the entire map.  If `playable_only` is `True`, this will be limited
        to the inner playable area.  If `False`, even the outer padding areas
        will be filled.
        """
        if playable_only:
            initial_location = self.room_start_offset(*Minimap.MAP_PLAYABLE_ROOM_START)
            row_fill = fill_byte * Minimap.ROOM_BYTE_W * Minimap.MAP_PLAYABLE_ROOM_W
            num_pixel_rows = Minimap.ROOM_H * Minimap.MAP_PLAYABLE_ROOM_H
        else:
            initial_location = self.room_start_offset(0, 0)
            row_fill = fill_byte * Minimap.ROOM_BYTE_W * Minimap.MAP_ROOM_W
            num_pixel_rows = Minimap.ROOM_H * Minimap.MAP_ROOM_H
        self._inner_fill(initial_location, row_fill, num_pixel_rows)

    def clear_map(self, playable_only=True):
        """
        Clears the entire map.  If `playable_only` is `True`, this will be limited
        to the inner playable area.  If `False`, even the outer padding areas
        will be filled.
        """
        self.fill_map(playable_only=playable_only, fill_byte=b'\x00')

    def import_image(self, filename, full_map=True, invert=False):
        """
        Imports the image stored `filename` into our minimap data.  This method
        only really makes sense for the pencil layer, but it could theoretically
        be used for the main layer as well.  By default, this will import the
        image into the full minimap space (including "padding" rooms).  If
        `full_map` is `False`, it will instead import to just the playable area.

        The image will be rescaled to fit the available space without any
        respect for aspect ratio, and then converted to monochrome with dithering
        if needed.  A correctly-sized pre-dithered monochrome image can be passed
        in to provide a 1:1 pixel mapping.

        If `invert` is `True`, the import will invert pixels.

        Image size for the full map is 800x528.  Image size for the playable area
        is 640x352.
        """
        global has_image_support
        if not has_image_support:
            raise RuntimeError('Pillow module does not seem to be available; import_image is not usable')
        if full_map:
            dim_x = Minimap.ROOM_W*Minimap.MAP_ROOM_W
            dim_y = Minimap.ROOM_H*Minimap.MAP_ROOM_H
            row_skip = 0
            start = 0
        else:
            dim_x = Minimap.ROOM_W*Minimap.MAP_PLAYABLE_ROOM_W
            dim_y = Minimap.ROOM_H*Minimap.MAP_PLAYABLE_ROOM_H
            row_skip = Minimap.MAP_BYTE_W-Minimap.MAP_PLAYABLE_BYTE_W
            start = Minimap.ROOM_BYTE_W*Minimap.MAP_PLAYABLE_ROOM_START[0] + Minimap.MAP_BYTE_ROOM_H*Minimap.MAP_PLAYABLE_ROOM_START[1]

        # Load the image
        im = Image.open(filename)

        # Resize if needed
        if im.width != dim_x or im.height != dim_y:
            im = im.resize((dim_x, dim_y))

        # Convert to mono + dither, if needed
        if im.mode != '1':
            im = im.convert('1', dither=Image.Dither.FLOYDSTEINBERG)

        # Now do the import.
        # TODO: This is probably the least-efficient and terrible way to do this
        self.df.seek(self.offset+start)
        for y in range(im.height):
            x = 0
            for x0 in range(int(im.width/8)):
                byte = 0
                x += 8
                for idx in range(8):
                    x -= 1
                    pixel = im.getpixel((x, y))
                    if pixel > 0:
                        pixel = 1
                    if invert:
                        if pixel == 1:
                            pixel = 0
                        else:
                            pixel = 1
                    byte <<= 1
                    byte |= pixel
                x += 8
                self.df.write(struct.pack('<B', byte))
            self.df.seek(row_skip, os.SEEK_CUR)

    def export_image(self, filename):
        """
        Exports our monochrome image to the filename `filename`.  The format
        should be dynamically decided by Pillow based on the filename
        extension.  The export size is always the "full" minimap, including
        the padded rooms.
        """
        global has_image_support
        if not has_image_support:
            raise RuntimeError('Pillow module does not seem to be available; export_image is not usable')
        self.df.seek(self.offset)
        raw_data = self.df.read(Minimap.MAP_BYTE_TOTAL)
        new_data = []
        for byte in raw_data:
            for _ in range(8):
                new_data.append(byte & 0x1)
                byte >>= 1
        im = Image.new(
                '1',
                (Minimap.ROOM_W*Minimap.MAP_ROOM_W, Minimap.ROOM_H*Minimap.MAP_ROOM_H),
                )
        im.putdata(new_data)
        im.save(filename)



class Stamp(Data):
    """
    Holds information about a single minimap stamp.
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        # Data
        self.x = NumData('X Pos', self, UInt16)
        self.y = NumData('Y Pos', self, UInt16)
        self.icon = NumChoiceData('Icon', self, UInt16, StampIcon)

    def __str__(self):
        return f'{self.icon} at ({self.x}, {self.y})'

    def clear(self):
        """
        Clears ourselves out (ie: removing the stamp)
        """
        self.x.value = 0
        self.y.value = 0
        self.icon.value = 0

    def copy_from(self, other):
        """
        Copies data from another Stamp into ourselves (used when deleting)
        """
        self.x.value = other.x.value
        self.y.value = other.y.value
        self.icon.value = other.icon.value


class Stamps(Data):
    """
    Holds information about map stamps on the minimap, and provides some
    management functions.
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        # Data
        self._num_stamps = NumData('Num Stamps', self, UInt8)
        self.selected_icon = NumChoiceData('Selected Icon', self, UInt16, StampIcon)
        self._stamps = []
        for idx in range(64):
            self._stamps.append(Stamp(f'Stamp {idx}', self))

    def __len__(self):
        """
        Support for `len()`
        """
        return self._num_stamps.value

    def __iter__(self):
        """
        Support iterating over our existing stamps
        """
        return iter(self._stamps[:self._num_stamps.value])

    def __getitem__(self, index):
        """
        Support referencing Stamps by index
        """
        if index < 0:
            # Don't feel like coping with negative indicies
            raise IndexError('negative indicies are not currently supported')
        if index >= self._num_stamps.value:
            # Just copying the stock Python error text for this
            raise IndexError('list index out of range')
        return self._stamps[index]

    def __delitem__(self, index):
        """
        Delete a Stamp from the list.  This mimics what the game does,
        namely: move the last stamp on top of this one, and then remove
        the last stamp from the list.
        """
        if index < 0:
            # Don't feel like coping with negative indicies
            raise IndexError('negative indicies are not currently supported')
        if index >= self._num_stamps.value:
            # Just copying the stock Python error text for this
            raise IndexError('list assignment index out of range')
        self._num_stamps.value -= 1
        if index < self._num_stamps.value:
            self._stamps[index].copy_from(self._stamps[self._num_stamps.value])
        self._stamps[self._num_stamps.value].clear()

    def append(self, x, y, icon):
        """
        Adds a Stamp to the end of the list.
        """
        if self._num_stamps.value >= 64:
            raise IndexError('maximum number of stamps is 64')
        self._stamps[self._num_stamps.value].x.value = x
        self._stamps[self._num_stamps.value].y.value = y
        self._stamps[self._num_stamps.value].icon.value = icon
        self._num_stamps.value += 1

    def clear(self):
        """
        Completely removes all Stamps from the minimap
        """
        for stamp in self:
            stamp.clear()
        self._num_stamps.value = 0


class MuralCoord(Data):
    """
    Mural coordinate, just used to keep track of the last-selected pixel
    while editing.  This is two UInt8s, for X and Y.  The mural size is
    40x20.
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        self.x = NumData('X', self, UInt8)
        self.y = NumData('Y', self, UInt8)

    def __str__(self):
        """
        String representation should be the full coordinate tuple
        """
        return f'({self.x}, {self.y})'


class Mural(Data):
    """
    Class to store information about the Bunny Mural.  This class is
    extremely basic and doesn't support anything remotely resembling
    editing pixel-by-pixel yet.  All it really supports is doing
    mass updates, such as setting it to the default or solved states,
    or wiping all pixels to the "background" color.
    """

    WIDTH = 40
    HEIGHT = 20
    BITS_PER_PIXEL = 2
    BYTES_PER_ROW = int(WIDTH/(8/BITS_PER_PIXEL))
    TOTAL_BYTES = BYTES_PER_ROW*HEIGHT

    DATA_DEFAULT = b'\x00\x00\x00\x00\x00\x00\x0a\x28\x00\x00' + \
            b'\x00\x02\x00\x00\x00\x80\x25\x96\x00\x00' + \
            b'\x80\x08\x00\x00\x00\x80\x24\x86\x00\x00' + \
            b'\x00\x02\x00\x02\x00\x80\x24\x86\x00\x00' + \
            b'\x00\x00\x00\x00\x00\x80\x94\x85\x00\x00' + \
            b'\x00\x00\x00\x00\x00\x80\x55\x25\x00\x08' + \
            b'\x00\x00\x00\x00\x80\x6a\x55\x95\x00\x22' + \
            b'\x00\x00\x00\xa0\x6a\x55\x55\x95\x00\x08' + \
            b'\xc0\x00\x8a\x5a\x55\x55\x54\x91\x00\x00' + \
            b'\x30\x80\x65\x55\x55\x55\x54\x91\x00\x00' + \
            b'\x0c\x80\x65\x55\x55\x55\x55\x95\x00\x00' + \
            b'\x03\x00\x5a\x55\x55\x55\x45\x25\x00\x00' + \
            b'\xc0\x00\x56\x55\x55\x55\x11\x25\x00\x20' + \
            b'\x30\x00\x56\x55\x55\x55\x55\x95\x0a\x00' + \
            b'\x0c\x80\x55\x55\x55\x55\x55\x55\x25\x00' + \
            b'\x03\x83\x55\x55\xa5\x5a\x55\x29\x00\x00' + \
            b'\xc0\x80\x55\x95\x0a\xa0\x5a\x95\x02\x00' + \
            b'\x30\xa0\x55\x25\x00\x00\xa0\x55\x09\x00' + \
            b'\x0c\x60\x55\x02\x00\x00\x00\xaa\x02\x00' + \
            b'\x00\x58\xa5\x00\x00\x00\x00\x00\x00\x00'

    DATA_SOLVED = b'\x37\x00\x00\x00\x40\x01\x05\x00\x00\x00' + \
            b'\x0c\x00\x40\x00\x40\x46\x05\x0c\x18\x09' + \
            b'\x08\x01\x90\x31\x40\x46\x05\x37\xf4\x07' + \
            b'\x48\x04\x40\x0e\x40\x19\x01\x0c\xf0\x03' + \
            b'\x32\x09\x00\x02\x00\x59\x00\x18\xf4\x07' + \
            b'\x02\x48\x00\x02\x00\x54\x05\x44\x98\x09' + \
            b'\x02\x98\x01\x08\x00\x55\x14\x10\x80\x00' + \
            b'\x0e\x42\x00\x58\x05\x15\x52\x20\x8c\x00' + \
            b'\x32\x82\x00\x55\x55\x55\x50\x82\x8c\x08' + \
            b'\x82\x80\x40\x55\x55\x55\x55\x81\x88\x32' + \
            b'\x88\x80\x50\x55\x55\x55\x55\x81\x88\xc0' + \
            b'\x88\x80\x54\x55\x55\x55\x55\x20\x20\x88' + \
            b'\x88\x20\x54\x55\x55\x55\x15\x20\x20\x20' + \
            b'\x8c\x23\x54\x55\x55\x55\xe5\xef\x23\x2c' + \
            b'\xef\xfe\x56\x55\x55\x55\xe5\xff\xef\xef' + \
            b'\xbe\xfd\x56\x55\x55\x55\xe5\xff\xff\xbb' + \
            b'\x7b\xf6\x54\x55\x55\x55\x01\xfc\xe7\xee' + \
            b'\xef\xf9\x50\x55\x55\x55\x00\xf0\x99\xbb' + \
            b'\xbe\xef\x43\x55\x55\x15\x00\xff\xe6\xee' + \
            b'\xfb\xbe\x0f\x00\x00\x00\xfc\xbf\xbb\xbb'

    COLORS = {
            # black
            (0x0A, 0x14, 0x32): 0,
            # blue
            (0x64, 0xC8, 0xFF): 1,
            # red
            (0xFA, 0x64, 0x64): 2,
            # white
            (0xFF, 0xE6, 0xC8): 3,
            }

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        # Subsequent data might rely on us having seeked to the end of the
        # data, so do so now.
        self.df.seek(Mural.TOTAL_BYTES, os.SEEK_CUR)

    def _fill_with_data(self, data):
        """
        Fills the mural with the specified raw data
        """
        if len(data) != Mural.TOTAL_BYTES:
            raise RuntimeError(f'mural data bytes must be {Mural.TOTAL_BYTES} long')
        self.df.seek(self.offset)
        self.df.write(data)

    def to_default(self):
        self._fill_with_data(Mural.DATA_DEFAULT)

    def to_solved(self):
        self._fill_with_data(Mural.DATA_SOLVED)

    def clear(self):
        """
        Clears out the mural entirely
        """
        data = b'\x00'*Mural.TOTAL_BYTES
        self._fill_with_data(data)

    def print_binary_data(self):
        """
        Prints out the binary data in a format easily copied into a Python
        script (as with the DATA_* vars, above).  The last line will require
        trimming off the "+ \" at the end.
        """
        self.df.seek(self.offset)
        data = self.df.read(Mural.TOTAL_BYTES)
        interval = 10
        s = 0
        while s < len(data):
            print("b'{}' + \\".format(
                ''.join([f'\\x{x:02x}' for x in data[s:s+interval]])
                ))
            s += interval

    def import_raw(self, filename):
        """
        Imports raw data from `filename`.  This doesn't really do any
        checking on the data, apart from making sure it's the correct
        length.
        """
        with open(filename, 'rb') as df:
            data = df.read()
            if len(data) != Mural.TOTAL_BYTES:
                raise RuntimeError(f'imported raw bunny mural data must be exactly {Mural.TOTAL_BYTES} bytes')
            self._fill_with_data(data)

    def export_raw(self, filename):
        """
        Exports our raw data into `filename`.
        """
        with open(filename, 'wb') as odf:
            self.df.seek(self.offset)
            data = self.df.read(Mural.TOTAL_BYTES)
            odf.write(data)

    def import_image(self, filename):
        """
        Imports the image at `filename` into our bunny mural.  The image requirements
        are that it be an indexed image with four defined colors, and at a resolution
        of 40x20.  The most common image formats which support indexed colors are
        PNG and GIF.  (JPEG does not use indexed color.)
        """
        global has_image_support
        if not has_image_support:
            raise RuntimeError('Pillow module does not seem to be available; import_png is not usable')

        # Load in the image and make sure it meets our criteria
        im = Image.open(filename)
        if im.mode != 'P':
            raise RuntimeError('imported bunny mural images must use indexed colors')
        if len(im.palette.colors) != 4:
            raise RuntimeError('imported bunny mural images must have exactly four indexed colors')
        if im.width != Mural.WIDTH or im.height != Mural.HEIGHT:
            raise RuntimeError(f'imported bunny mural images must be exactly {Mural.WIDTH}x{Mural.HEIGHT}')

        # Translate color indexes in case the colormap isn't in the
        # same order we expect.  Also attempt to find "closest color" when
        # we have unknown colors, though this is likely to result in
        # bad-looking images unless the colors happen to be quite close
        # to the mural colors.
        color_translate = {}
        for color, index in im.palette.colors.items():
            if color in Mural.COLORS:
                if index != Mural.COLORS[color]:
                    color_translate[index] = Mural.COLORS[color]
            else:
                # Attempt to find the closest color.  Will probably look terrible!
                # Somewhat arbitrarily using the "redmean" technique found at:
                #
                #     https://en.wikipedia.org/wiki/Color_difference#sRGB
                #
                # This is called "overthinking the problem!"
                chosen_index = None
                cur_diff = 99999999999
                for stock_color, stock_index in Mural.COLORS.items():
                    rbar = (color[0] + stock_color[0])*0.5
                    # Omitting the math.sqrt here since it's technically unnecessary
                    diff = (2+(rbar/256))*(color[0]-stock_color[0])**2 + \
                           4*(color[1]-stock_color[1])**2 + \
                           (2+((255-rbar)/256))*(color[2]-stock_color[2])**2
                    if diff < cur_diff:
                        cur_diff = diff
                        chosen_index = stock_index
                if chosen_index is not None:
                    color_translate[index] = chosen_index

        # Now do the import.
        # TODO: This is probably the least-efficient and terrible way to do
        # this.  Adapted from the similarly-terrible pencil image export code.
        self.df.seek(self.offset)
        for y in range(im.height):
            x = 0
            for x0 in range(int(im.width/4)):
                byte = 0
                x += 4
                for idx in range(4):
                    x -= 1
                    pixel = im.getpixel((x, y))
                    byte <<= 2
                    byte |= color_translate.get(pixel, pixel)
                x += 4
                self.df.write(struct.pack('<B', byte))


    def export_image(self, filename):
        """
        Exports the bunny mural to the filename `filename`.  The export format
        will be determined by the filename extension, but it will only work
        if the format supports indexed colors.  The most common formats which
        support that are PNG and GIF.  JPEG does *not* support indexed color.
        """
        global has_image_support
        if not has_image_support:
            raise RuntimeError('Pillow module does not seem to be available; export_png is not usable')

        # Collect the image data in the form that Pillow wants
        self.df.seek(self.offset)
        raw_data = self.df.read(Mural.TOTAL_BYTES)
        new_data = []
        for byte in raw_data:
            for _ in range(4):
                new_data.append(byte & 0x3)
                byte >>= 2

        # Now create the image and write it out
        im = Image.new(
                'P',
                (Mural.WIDTH, Mural.HEIGHT),
                )
        # Relying on the fact that Python dicts remember insertion order, here.
        # I always feel rather itchy when doing that...
        for color in Mural.COLORS.keys():
            im.palette.getcolor(color)
        im.putdata(new_data)
        im.save(filename)


class KangarooEncounter(Data):
    """
    Holds information about kangaroo encounters, which is how the game keeps
    track of K. Shard / K. Medal states.
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        # Data
        self.shard_pos_x = NumData('Shard Position X', self, Float)
        self.shard_pos_y = NumData('Shard Position Y', self, Float)
        self.room_x = NumData('Room X', self, UInt8)
        self.room_y = NumData('Room Y', self, UInt8)
        self.state = NumChoiceData('Shard State', self, UInt8, KangarooShardState)
        self.encounter_id = NumData('Encounter ID', self, UInt8)

    def clear(self):
        """
        Clears out our state
        """
        self.shard_pos_x.value = 0
        self.shard_pos_y.value = 0
        self.room_x.value = 0
        self.room_y.value = 0
        self.state.value = KangarooShardState.NONE
        self.encounter_id.value = 0


class KangarooState(Data):
    """
    Holds information about all three kangaroo states
    """

    # Each ID is mapped to a specific room, and if we inject any data in
    # here, it'd probably be nice to set the shard positions as well (though
    # we're only likely to be setting "collected" or "inserted" states,
    # at which time the shard positions are useless).  The positions here
    # were taken from the drop data seen in my own savefiles -- the shard
    # positions on a live game would be different for you depending on
    # where the kangaroo was when it dropped the shard.  For collected +
    # inserted shards, there's really no point to any of this data; the
    # game doesn't care if it's all zeroes.  Still, nice to be proper.
    Preset = collections.namedtuple('Preset',
            ['shard_pos_x', 'shard_pos_y', 'room_x', 'room_y'],
            )
    ID_TO_DATA = {
            0: Preset(38, 104, 6, 6),
            1: Preset(156, 136, 9, 11),
            2: Preset(16, 144, 12, 11),
            3: Preset(147, 144, 9, 13),
            4: Preset(154, 128, 16, 16),
            }

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        self.encounters = []
        self._available_ids = {0, 1, 2, 3, 4}
        for idx in range(3):
            enc = KangarooEncounter(f'Encounter {idx}', self)
            if enc.state.choice != KangarooShardState.NONE:
                self._available_ids -= {enc.encounter_id.value}
            self.encounters.append(enc)
        self.next_encounter_id = NumData('Next Encounter ID', self, UInt8)
        self.state = NumChoiceData('Kangaroo State', self, UInt8, KangarooActivityState)

    def __len__(self):
        return 3

    def __iter__(self):
        return iter(self.encounters)

    def num_collected(self):
        return sum([1 for e in self if e.state == KangarooShardState.COLLECTED])

    def num_inserted(self):
        return sum([1 for e in self if e.state == KangarooShardState.INSERTED])

    def get_cur_kangaroo_room_str(self):
        """
        Returns the current kangaroo room coordinates as a string suitable for
        printing.
        """
        if self.next_encounter_id.value in KangarooState.ID_TO_DATA:
            data = KangarooState.ID_TO_DATA[self.next_encounter_id.value]
            return f'({data.room_x}, {data.room_y})'
        else:
            return 'unknown'

    def force_kangaroo_room(self, room_id):
        """
        Forces the Kangaroo to appear in the specified room, in its "lurking"
        state (ie: it will likely not be immediately present, but once the player
        passes a trigger, the kangaroo will start attacking).
        """
        self.next_encounter_id.value = room_id
        self.state.value = KangarooActivityState.LURKING

    def set_shard_state(self, count, state):
        """
        Sets the specified number of shards to the given state, and will zero
        out any remaining shards afterwards.
        """
        if count < 1:
            raise RuntimeError('count must be at least 1')
        if count > 3:
            raise RuntimeError('count can be at most 3')
        for idx, shard in enumerate(self):
            if idx >= count or state == KangarooShardState.NONE:
                shard.clear()
            else:
                if shard.state == KangarooShardState.NONE:
                    # Invent some data for the shard
                    new_id = sorted(self._available_ids)[0]
                    self._available_ids -= {new_id}
                    shard.encounter_id = new_id
                    shard.shard_pos_x  = KangarooState.ID_TO_DATA[new_id].shard_pos_x
                    shard.shard_pos_y  = KangarooState.ID_TO_DATA[new_id].shard_pos_y
                    shard.room_x  = KangarooState.ID_TO_DATA[new_id].room_x
                    shard.room_y  = KangarooState.ID_TO_DATA[new_id].room_y
                shard.state.value = state


class FillLevels(Data):
    """
    Holds information about the game's various reservoir fill levels (used in three
    room puzzles.  In terms of the data, each value goes from zero (completely empty)
    to 80 (completely full).  There are five of these in the game.  The structure
    apparently technically has room for sixteen, but we'll restrict our activities
    to the first five.

    Room Coordinates by reservoir index:
        0: 7,11
        1: 4,15
        2: 2,17 (middle)
        3: 2,17 (right)
        4: 2,17 (left)
    """

    NUM_RESERVOIRS = 5
    MAX_VALUE = 80

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)
        self.levels = []
        for idx in range(FillLevels.NUM_RESERVOIRS):
            self.levels.append(NumData(f'Reservoir {idx}', self, UInt8))

        # Fudge our location so that a data value that comes after is at
        # the correct spot without needing to specify an absolute pos
        self.df.seek(16-FillLevels.NUM_RESERVOIRS, os.SEEK_CUR)

    def __iter__(self):
        return iter(self.levels)

    def _set_all(self, value):
        """
        Sets the fill level for all reservoirs to the specified value.
        """
        value = min(value, FillLevels.MAX_VALUE)
        for level in self:
            level.value = value

    def fill(self):
        """
        Completely fills all reservoirs in the game.
        """
        self._set_all(FillLevels.MAX_VALUE)

    def empty(self):
        """
        Completely empties all reservoirs in the game.
        """
        self._set_all(0)

    def num_filled(self):
        """
        Returns the number of reservoirs which are totally filled in
        """
        return sum([1 for l in self if l >= FillLevels.MAX_VALUE])


class TileID(Data):
    """
    Class to hold information about a specific Tile ID.  This consists of
    both the room coordinates (x+y) an then the in-room tile coordinates (x+y).

    In addition to the room and tile coordinates, the file format technically
    uses the top two bits of the Tile X coordinate to specify map layer.  The
    game code specifically checks for layer 1 within those two bits.  All
    known instances of the data in the game remain in layer 0, so the class
    is currently just ignoring the fact that it's there.  If anything changes
    in the future (or map mods start getting introduced) we may have to start
    doing things properly.
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        self.room_y = NumData('Room Y', self, UInt8)
        self.room_x = NumData('Room X', self, UInt8)
        self.tile_y = NumData('Tile Y', self, UInt8)
        # Again, the top two bits of tile_x are actually `layer`, which we're
        # ignoring for now.
        self.tile_x = NumData('Tile X', self, UInt8)

    def __str__(self):
        return f'({self.room_x}, {self.room_y}): {self.tile_x}, {self.tile_y}'

    def clear(self):
        """
        Clears out all our data
        """
        self.room_y.value = 0
        self.room_x.value = 0
        self.tile_y.value = 0
        self.tile_x.value = 0

    def to_tuple(self):
        """
        Returns ourself as a tuple which can be compared to the entries in
        TileID's `known_values` set.
        """
        return (self.room_x.value, self.room_y.value, self.tile_x.value, self.tile_y.value)

    def from_tuple(self, data):
        """
        Sets our own data from the given tuple (used by TileIDs to know
        which ones might need to be added to a save).
        """
        self.room_x.value = data[0]
        self.room_y.value = data[1]
        self.tile_x.value = data[2]
        self.tile_y.value = data[3]

    def copy_from(self, other):
        """
        Copies data from another TileID onto ourselves.  Used mostly just while
        clearing out "invalid" wall moves at the moment.
        """
        self.room_x.value = other.room_x.value
        self.room_y.value = other.room_y.value
        self.tile_x.value = other.tile_x.value
        self.tile_y.value = other.tile_y.value


class TileIDs(Data):
    """
    Defines a Tile ID in terms of its room coordinates and then in-room tile
    coordinates.  This is used to keep track of which locked doors have been
    unlocked, and which movable walls have been moved.

    Note that this structure has a separate "index" field stored *much* later
    in the slot data, which the game uses to know where the next-opened
    TileID should go.  Specifying the location to this index right during the
    constructor here would be a little annoying given how we're handling
    the objects, so we're leaving that to be populated later on once we
    get to that point in the file.

    Note too that there's a bug in the game where the bounds are *not* checked
    properly.  For walls, there are fourteen "legitimate" entries in this list,
    but there are a further three which can be triggered via cheating.  The
    bounds check for the 16 available slots is not checked properly, and the
    game ends up with a runaway loop of writing to a 17th slot, then 18th, etc.
    This implementation will clamp all operations to the specified number of
    entries a bit more properly.

    The optional argument `invalid` can be specified to define a set of
    coordinates which are considered "invalid" (as in acquired via cheating),
    so that we can support clearing those out of the list (hopefully avoiding
    that runaway overwrite bug described above).
    """

    def __init__(self, debug_label, parent, num_entries, known_values, offset=None, invalid=None):
        super().__init__(debug_label, parent, offset=offset)
        self._num_entries = num_entries
        self.known_values = known_values
        if invalid is None:
            self.invalid = set()
        else:
            self.invalid = invalid
        self._next_index = None
        self._tiles = []
        for idx in range(num_entries):
            self._tiles.append(TileID(f'Tile {idx}', self))

    def __len__(self):
        """
        Cap our length at num_entries, even if we've overflown.
        """
        if self._next_index > self._num_entries:
            return self._num_entries
        else:
            return self._next_index.value

    def __iter__(self):
        """
        Allow iteration over our stored tiles
        """
        return iter(self._tiles[:len(self)])

    def populate_index(self, parent, offset=None):
        """
        Populate our index field, which keeps track of where the next entry
        should be written.  Note that we're passing in a new parent and
        offset here, since this data is *very* divorced from the main array
        in the savegame data.  In the savegame currently there's little
        reason why we couldn't just use our saved parent here, since it'll
        always be the same, but this way we can be pretty explicit about
        offsets in the main slot defintion, so I prefer it this way.

        One other note about this weird index is that technically the Doors
        index is a u16, whereas the Walls one is u8.  We're just using
        u8 for both, because that makes me itchy, and those fields can't
        hold more than 16 items anyway.
        """
        self._next_index = NumData(f'{self.debug_label} Index', parent, UInt8, offset)

    def clear(self):
        """
        Clears out all tiles from ourselves
        """
        self._next_index.value = 0
        for tile in self._tiles:
            tile.clear()

    def fill(self):
        """
        Fills in all known tiles to our structure
        """
        values_to_add = set(self.known_values)
        current_values = set([tile.to_tuple() for tile in self])
        values_to_add -= current_values
        if self._next_index + len(values_to_add) > self._num_entries:
            raise RuntimeError(f'Attempting to add {len(values_to_add)} entries to the existing {self._next_index} would overflow this structure (max size: {self._num_entries})')
        for tile_values in sorted(values_to_add):
            self._tiles[self._next_index.value].from_tuple(tile_values)
            self._next_index.value += 1

    def remove_invalid(self):
        """
        Removes any "invalid" entries found in our set, as optionally
        defined by the constructor.
        """
        to_remove = []
        for idx, tile in enumerate(self):
            if tile.to_tuple() in self.invalid:
                to_remove.append(idx)
        for index in reversed(to_remove):
            self._next_index.value -= 1
            if index < self._next_index.value:
                self._tiles[index].copy_from(self._tiles[self._next_index.value])
            self._tiles[self._next_index.value].clear()


class Cranks(Data):
    """
    Holds data about the various cranks in the save.  We're not actually
    editing these (or even showing data) so this class could use some
    more implementation to make it useful.
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)
        self._cranks = []
        for idx in range(23):
            self._cranks.append(NumData(f'Crank {idx}', self, UInt16))

    def __iter__(self):
        return iter(self._cranks)

    def __len__(self):
        return len(self._cranks)

    def __getitem__(self, idx):
        return self._cranks[idx]


class ElevatorState(Data):
    """
    Class to hold the "state" of a single elevator, meaning just its
    current position and speed.
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        self.position = NumData('Position', self, Float)
        self.speed = NumData('Speed', self, Float)


class Elevators(Data):
    """
    Class to hold all state information about the elevators in the game,
    which also includes some horizontally-moving platforms (though only
    of the sort controlled by animal wheels -- not the smaller
    back-and-forth platforms such as seen in the first few rooms of
    the game).
    """

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)

        self.states = []
        for idx in range(8):
            self.states.append(ElevatorState(f'Elevator {idx} State', self))
        self.directions = NumBitfieldData('Directions', self, UInt8, ElevatorDirection)
        self.inactive = NumBitfieldData('Inactive', self, UInt8, ElevatorDisabled)


class BigStalactites(Data):
    """
    Class to hold state information for all of the big stalactites in the game
    (the ones which can be hit repeatedly to make them drop, and then hit
    more to destroy entirely).
    """

    LABELS = {
            0: 'Stalactite #1 at (7,4)',
            1: 'Stalactite #1 at (4,6)',
            2: 'Stalactite #2 at (4,6)',
            3: 'Stalactite #3 at (4,6)',
            4: 'Stalactite #4 at (4,6)',
            5: 'Stalactite #5 at (4,6)',
            6: 'Stalactite #6 at (4,6)',
            7: 'Stalactite #7 at (4,6)',
            8: 'Stalactite #1 at (5,7)',
            9: 'Stalactite #2 at (5,7)',
            10: 'Stalactite #3 at (5,7)',
            11: 'Stalactite #4 at (5,7)',
            12: 'Stalactite #5 at (5,7)',
            13: 'Stalactite #6 at (5,7)',
            }

    def __init__(self, debug_label, parent, offset=None):
        super().__init__(debug_label, parent, offset=offset)
        self.stalactites = []
        for idx in range(len(self)):
            self.stalactites.append(NumChoiceData(BigStalactites.LABELS[idx], self, UInt8, BigStalactiteState))
        # The structure is apparently 16 long, even though we only have 14.  Seek
        # to the end just in case any other data is chained afterwards.
        self.df.seek(16-len(self), os.SEEK_CUR)

    def __len__(self):
        """
        Just hardcoding the number that's on the map
        """
        return 14

    def __iter__(self):
        """
        Iterate over our values
        """
        return iter(self.stalactites)

    def set_state(self, new_state):
        """
        Sets the state for all big stalactites
        """
        for stalactite in self.stalactites:
            stalactite.value = new_state


class PickedFruitData(BitCountData):
    """
    An overridden BitCountData to deal with a kind of weird edge case:
    stealing a nut from a squirrel apparently counts as having picked
    up a fruit.  It does sort of make sense since you get health by
    doing so, though why the game would keep track of it in the same
    bitfield is beyond me.

    What this does is sets an extra boolean (`has_stolen_nut`) which
    can be read at any time, and it'll decrease the count by 1 if
    that bit is present (since IMO the stolen-nut "fruit" shouldn't
    be considered one of the world fruits picked up).  The CLI will
    then report on it in the info output.

    We *could* override the constructor here (it seems reasonable to
    hardcode debug_label, num_type, count, and max_bits at least) --
    the processing would fail if we don't have at least `2` for `count`,
    for instance.  But, I like having all those definitions out in the
    main Slot class along with everything else, and merely setting the
    new boolean in _fix_count() is enough to ensure that it's always
    present, so we're just leaving it like that.
    """

    STOLEN_NUT_SEGMENT = 1
    STOLEN_NUT_BIT = 0x8000000000000

    def _fix_count(self):
        """
        We are relying on the fact that _fix_count() will always get called
        when the class is instantiated, since it's reading in the data from
        disk.  If that *wasn't* the case, we wouldn't be sure that the
        `has_stolen_nut` attribute is defined (and we should also be
        overriding the constructor and setting it there), but I'm being
        slightly lazier and just letting it happen in here.
        """
        super()._fix_count()
        if self._data[PickedFruitData.STOLEN_NUT_SEGMENT].value & PickedFruitData.STOLEN_NUT_BIT == PickedFruitData.STOLEN_NUT_BIT:
            self.count -= 1
            self.has_stolen_nut = True
        else:
            self.has_stolen_nut = False


class Slot(Data):
    """
    A savegame slot.  Obviously this is where the bulk of the game data is
    stored.
    """

    TOTAL_BYTES = 159_760

    def __init__(self, debug_label, parent, index, offset):
        super().__init__(debug_label, parent, offset=offset)
        self.savegame = self.parent
        self.index = index
        self.df = self.savegame.df
        self.has_data = False

        # Actually load in all the data
        self._parse()

    def _parse(self):
        """
        Parses our slot structure
        """
        self.df.seek(self.offset)

        self.timestamp = Timestamp('Timestamp', self)
        # If the timestamp is all zeroes, assume that the slot is empty
        # (though we'll continue to load the rest of the data anyway)
        self.has_data = self.timestamp.has_data

        self.cranks = Cranks('Cranks', self, 0x8)

        self.locked_doors = TileIDs('Locked Doors', self, 16, {
                (7, 4, 9, 5),
                (15, 8, 38, 6),
                (16, 10, 4, 5),
                (14, 13, 6, 16),
                (14, 15, 27, 6),
                (14, 15, 32, 6),
            }, 0x88)
        self.moved_walls = TileIDs('Moved Walls', self, 16, {
                (2, 5, 2, 1),
                (15, 5, 6, 3),
                (6, 6, 16, 14),
                (7, 6, 16, 1),
                (7, 6, 5, 14),
                (13, 7, 29, 1),
                (10, 8, 16, 17),
                (2, 9, 1, 6),
                (9, 10, 39, 6),
                (8, 11, 33, 19),
                (13, 11, 39, 17),
                (6, 13, 36, 7),
                (2, 19, 9, 7),
                (2, 19, 31, 7),
            }, invalid={
                (12, 4, 29, 4),
                (3, 7, 5, 3),
                (13, 13, 11, 8),
                })

        self.num_steps = NumData('Num Steps', self, UInt32, 0x108)
        self.fill_levels = FillLevels('Fill Levels', self)

        self.chests_opened = BitCountData('Chests Opened', self, UInt64, 2, 102, 0x120)
        self.button_doors_opened = BitCountData('Button Doors Opened', self, UInt64, 2, 94)
        self.yellow_buttons_pressed = BitCountData('Yellow Buttons Pressed', self, UInt64, 3, 134)

        self.purple_buttons_pressed = BitCountData('Purple Buttons Pressed', self, UInt64, 1, 27, 0x160)
        self.green_buttons_pressed = BitCountData('Green Buttons Pressed', self, UInt64, 1, 7)

        self.picked_fruit = PickedFruitData('Picked Fruit', self, UInt64, 2, 115, 0x170)
        self.picked_firecrackers = BitCountData('Picked Firecrackers', self, UInt64, 1, 64)
        self.eggs = NumBitfieldData('Eggs', self, UInt64, Egg)
        self.walls_blasted = BitCountData('Walls Blasted', self, UInt32, 1, 10)
        self.detonators_triggered = BitCountData('Detonators Triggered', self, UInt32, 1, 9)
        self.bunnies = NumBitfieldData('Bunnies', self, UInt32, Bunny)
        self.illegal_bunnies = NumBitfieldData('Illegal Bunnies', self, UInt32, IllegalBunny, 0x198)
        self.squirrels_scared = BitCountData('Squirrels Scared', self, UInt16, 1, 13, 0x19C)
        self.cat_status = NumBitfieldData('Cat Status', self, UInt16, CatStatus)

        self.firecrackers_collected = NumData('Firecrackers Collected', self, UInt16, 0x1A2)
        self.bubbles_popped = NumData('Bubbles Popped', self, UInt16)

        self.num_saves = NumData('Num Saves', self, UInt16, 0x1A8)
        self.locked_doors.populate_index(self)

        # Kind of playing silly buggers here and defining the same u16 with
        # two separate vars -- one for "valid" pink buttons, and one for
        # invalid ones.  That way we can mess with them separately.  (This
        # is the cleanest way to do it given the restrictions I'd designed
        # into NumBitfieldData and the CLI processing.)
        self.pink_buttons_pressed = NumBitfieldData('Pink Buttons Pressed', self, UInt16, PinkButton, 0x1AC)
        self.invalid_pink_buttons = NumBitfieldData('Invalid Pink Buttons', self, UInt16, PinkButtonInvalid, 0x1AC)
        self.nuts = NumData('Num Nuts', self, UInt8)
        self.layer1_chests_opened = BitCountData('Layer 1 (CE Temple) Chests', self, UInt8, 1, 1)
        self.layer2_buttons_pressed = BitCountData('Layer 2 (Space / Bunny Island) Buttons', self, UInt8, 1, 4)
        self.keys = NumData('Num Keys', self, UInt8)
        self.matches = NumData('Num Matches', self, UInt8)
        self.firecrackers = NumData('Num Firecrackers', self, UInt8)
        self.health = NumData('Health', self, UInt8)
        self.gold_hearts = NumData('Gold Hearts', self, UInt8)
        self.last_groundhog_year = NumData('Last Groundhog Year', self, UInt16)
        self.moved_walls.populate_index(self)
        self.egg_doors = NumBitfieldData('Egg Doors', self, UInt8, EggDoor)

        self.elapsed_ticks_ingame = Ticks('Ingame Ticks', self, 0x1BC)
        self.elapsed_ticks_withpause = Ticks('Total Ticks', self)

        self.spawn_room = MapCoord('Spawn', self, 0x1D4)

        self.equipment = NumBitfieldData('Equipment', self, UInt16, Equipment, 0x1DC)
        self.inventory = NumBitfieldData('Inventory', self, UInt8, Inventory)

        self.candles = NumBitfieldData('Candles', self, UInt16, CandleState, 0x1E0)
        self.num_hits = NumData('Num Hits', self, UInt16)
        self.num_deaths = NumData('Num Deaths', self, UInt16)
        self.ghosts_scared = BitCountData('Ghosts Scared', self, UInt16, 1, 11)

        self.selected_equipment = NumChoiceData('Selected Equipment', self, UInt8, Equipped, 0x1EA)

        self.quest_state = NumBitfieldData('Quest State', self, UInt32, QuestState, 0x1EC)
        self.blue_manticore = NumChoiceData('Blue Manticore', self, UInt8, ManticoreState)
        self.red_manticore = NumChoiceData('Red Manticore', self, UInt8, ManticoreState)

        self.kangaroo_state = KangarooState('Kangaroo State', self, 0x1F4)

        self.progress = NumBitfieldData('Progress', self, UInt16, Progress, 0x21C)
        self.flames = Flames('Flames', self)

        self.teleports_seen = NumBitfieldData('Teleports Seen', self, UInt8, Teleport, 0x223)
        self.teleports = NumBitfieldData('Teleports Active', self, UInt8, Teleport)
        self.stamps = Stamps('Minimap Stamps', self)
        self.elevators = Elevators('Elevators', self)
        self.mural_coords = MuralCoord('Mural Coordinates', self)
        self.minimap = Minimap('Minimap Revealed', self)

        self.pencilmap = Minimap('Minimap Pencil Layer', self, 0xD22D)

        self.destructionmap = Minimap('Destroyed Blocks', self, 0x1A06E)

        self.mural = Mural('Bunny Mural', self, 0x26EAF)
        self.big_stalactites = BigStalactites('Big Stalactites', self)

        self.deposit_small_broken = BitCountData('Small Deposits Broken', self, UInt64, 8, 423, 0x26F98)
        self.icicles_broken = BitCountData('Icicles Broken', self, UInt64, 4, 159)

        self.berries_eaten_while_full = NumData('Berries Eaten While Full', self, UInt16, 0x26FFA)

    def export_data(self):
        """
        Reads in all current slot data as a single bytestring
        """
        self.df.seek(self.offset)
        return self.df.read(Slot.TOTAL_BYTES)

    def import_data(self, data):
        """
        Overwrites slot data with the specified bytestring
        """
        if len(data) != Slot.TOTAL_BYTES:
            raise RuntimeError(f'imported slot data must be exactly {Slot.TOTAL_BYTES} bytes')
        self.df.seek(self.offset)
        self.df.write(data)
        self._parse()


class Savegame():
    """
    The savegame itself.  This consists of a short header (where data like
    figurines, achievements, and a savefile checksum are stored), then three
    save slots, and then a footer where data like game settings is stored.

    The savegame size is fixed (479,360 bytes), so we could technically just
    hardcode every offset without worrying about changes.

    We believe that the first uint32 is a version number, which at time of
    coding is `0x9`.  At the moment we will raise a `RuntimeError` if we see
    anything other than `0x9` in that field.
    """

    def __init__(self, filename, autosave=False):
        """
        Load in an existing savegame from the file `filename`.  We will load
        the savegame into an in-memory `io.BytesIO` object and operate on
        that while viewing/editing.

        The `autosave` boolean is used when this object is used as a context
        manager (ie: `with Savegame(foo, autosave=True) as save:`).  When
        True, we'll automatically save out any changes once the manager exits.
        Otherwise, you must manually call `save()` to save out any changes.

        In order to override the automatic checksum computation, `save()` must
        be called manually (ie: don't enable `autosave`).
        """
        self.filename = filename
        self.autosave = autosave
        self.offset = 0
        with open(self.filename, 'rb') as read_df:
            self.df = io.BytesIO(read_df.read())

        # Pretend to be a Data object
        self.parent = None
        self.offset = 0

        # Read in the savegame
        self._read()

    def __enter__(self):
        """
        Support `with` context manager
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        If we set the `autosave` boolean, automatically save when the
        context manager exits.
        """
        if self.autosave:
            self.save()

    def _read(self):
        """
        Reads in the initial savegame; only really intended to be used once during
        the constructor, but I wanted this in its own function anyway
        """
        self.df.seek(self.offset)
        self.version = NumData('Save Version', self, UInt32)
        if self.version.value != 9:
            raise RuntimeError(f'Unknown savefile version: {self.version}')

        self.frame_seed = NumData('Frame Seed', self, UInt32, 0x8)
        self.last_used_slot = NumData('Last Used Slot', self, UInt8)
        self.checksum = NumData('Checksum', self, UInt8)

        self.unlockables = NumBitfieldData('Globals', self, UInt32, Unlockable, 0x10)

        self.slots = [
                Slot('Slot 1', self, 0, 0x00018),
                Slot('Slot 2', self, 1, 0x27028),
                Slot('Slot 3', self, 2, 0x4E038),
                ]

    def save(self, force_invalid_checksum=False, force_checksum=None):
        """
        Saves any changes out to disk.  This will automatically recompute the
        checksum and change it if needed.  To force writing of an invalid
        checksum, pass `force_invalid_checksum=True` (perhaps you *want* a
        Manticore friend to follow you around?).  To force a specific
        checksum for whatever reason, pass it in with `force_checksum`.
        """
        
        # First, deal with our checksum.
        if force_checksum is None:
            # Compute the checksum -- clear it out first (to zero), which means
            # we don't have to bother skipping the byte while doing the XORs.
            # This feels awfully inefficient (`read()`ing the whole file contents
            # again, even though it's already in memory) but I kept running into
            # weird issues when trying to use getbuffer() to operate on the whole
            # byte buffer as-is.
            self.checksum.value = 0
            self.df.seek(0)
            total = 0
            for byte in self.df.read():
                total ^= byte
            # If we've been told to write an invalid checksum, invert all our
            # bits after the computation.
            if force_invalid_checksum:
                total ^= 0xFF
            self.checksum.value = total
        else:
            self.checksum.value = force_checksum

        # Now write out
        self.df.seek(0)
        with open(self.filename, 'wb') as write_df:
            write_df.write(self.df.read())

