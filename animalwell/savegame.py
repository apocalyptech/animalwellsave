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
import io
import sys
import enum
import struct
import collections

from .datafile import UInt8, UInt16, UInt32, UInt64, \
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
    CLOSET_OPEN =        (0x00000004, 'Closet Open')
    UNLOCK_MAP =         (0x00000200, 'Map Unlocked')
    UNLOCK_STAMPS =      (0x00000400, 'Stamps Unlocked')
    UNLOCK_PENCIL =      (0x00000800, 'Pencil Unlocked')
    DEFEATED_CHAMELEON = (0x00001000, 'Defeated Chameleon')
    CRING =              (0x00002000, "Cheater's Ring")
    USED_S_MEDAL =       (0x00008000, "Inserted S. Medal")
    # Eh, don't bother with this one
    #WOKE_UP =            (0x00040000, 'Woke Up (start of game)')
    BB_WAND =            (0x00080000, 'B.B. Wand Upgrade')
    EGG_65 =             (0x00100000, 'Egg 65')
    USED_E_MEDAL =       (0x00200000, 'Inserted E. Medal')
    DEFEATED_BAT =       (0x01000000, 'Defeated Bat')
    FREED_OSTRICH =      (0x02000000, 'Freed Wheel Ostrich')
    DEFEATED_OSTRICH =   (0x04000000, 'Defeated Wheel Ostrich')
    FIGHTING_EEL =       (0x08000000, 'Fighting Eel')
    DEFEATED_EEL =       (0x10000000, 'Defeated Eel')
    SHRINE_NO_DISC =     (0x20000000, 'No Disc in Dog Shrine')
    STATUE_NO_DISC =     (0x40000000, 'No Disc in Ghost Dog Head')


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
    POST_MODERN =     (0x0000000000200000, 'Post-Modern')
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
    Bunnies!  This enum currently omits all the illegal/invalid bunnies.
    It's possible we may want to at least optionally expose those in the
    future, though...
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


class Timestamp(Data):
    """
    Timestamp class -- this is only actually seen at the very beginning of
    each slot, and shown on the "load game" dialog in-game.
    """

    def __init__(self, parent, offset=None):
        super().__init__(parent, offset=offset)

        # Data
        self.year = NumData(self, UInt16)
        self.month = NumData(self, UInt8)
        self.day = NumData(self, UInt8)
        self.hour = NumData(self, UInt8)
        self.minute = NumData(self, UInt8)
        self.second = NumData(self, UInt8)

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
    A single flame status.  This is just a NumChoiceData with an extra
    `name` attribute, so that utilities can report on which flame is
    being used, when iterating over the whole set.
    """

    def __init__(self, parent, name, offset=None):
        super().__init__(parent, UInt8, FlameState)
        self.name = name


class Flames(Data):
    """
    Structure to hold information about all the collectible flames in the game.
    Provides iteration and lookup by lowercase letter, in addition to the
    single-letter attributes.
    """

    def __init__(self, parent, offset=None):
        super().__init__(parent, offset=offset)

        # Data
        self.b = Flame(self, 'B. Flame')
        self.p = Flame(self, 'P. Flame')
        self.v = Flame(self, 'V. Flame')
        self.g = Flame(self, 'G. Flame')

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

    def __init__(self, parent, offset=None):
        super().__init__(parent, UInt32, offset=offset)
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

    def __init__(self, parent, offset=None):
        super().__init__(parent, offset=offset)

        self.x = NumData(self, UInt32)
        self.y = NumData(self, UInt32)

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

    def __init__(self, parent, offset=None):
        super().__init__(parent, offset=offset)

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

    def __init__(self, parent, offset=None):
        super().__init__(parent, offset=offset)

        # Data
        self.x = NumData(self, UInt16)
        self.y = NumData(self, UInt16)
        self.icon = NumChoiceData(self, UInt16, StampIcon)

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

    def __init__(self, parent, offset=None):
        super().__init__(parent, offset=offset)

        # Data
        self._num_stamps = NumData(self, UInt8)
        self.selected_icon = NumChoiceData(self, UInt16, StampIcon)
        self._stamps = []
        for _ in range(64):
            self._stamps.append(Stamp(self))

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

    def __init__(self, parent, offset=None):
        super().__init__(parent, offset=offset)

        # Subsequent data might rely on us having seeked to the end of the
        # data, so do so now.
        self.df.seek(Minimap.MAP_BYTE_TOTAL, os.SEEK_CUR)

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
        trimming off the `+ \` at the end.
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


class Slot():
    """
    A savegame slot.  Obviously this is where the bulk of the game data is
    stored.
    """

    TOTAL_BYTES = 159_760

    def __init__(self, savegame, index, offset):
        self.savegame = savegame
        self.index = index
        self.df = self.savegame.df
        self.offset = offset
        self.has_data = False

        # Actually load in all the data
        self._parse()

    def _parse(self):
        """
        Parses our slot structure
        """
        self.df.seek(self.offset)

        self.timestamp = Timestamp(self)
        # If the timestamp is all zeroes, assume that the slot is empty
        # (though we'll continue to load the rest of the data anyway)
        self.has_data = self.timestamp.has_data

        self.num_steps = NumData(self, UInt32, 0x108)

        self.chests_opened = BitCountData(self, UInt64, 2, 0x120)
        self.button_doors_opened = BitCountData(self, UInt64, 2)
        self.yellow_buttons_pressed = BitCountData(self, UInt64, 3)

        self.picked_fruit = BitCountData(self, UInt64, 2, 0x170)
        self.picked_firecrackers = BitCountData(self, UInt64, 1)
        self.eggs = NumBitfieldData(self, UInt64, Egg)
        self.walls_blasted = BitCountData(self, UInt32, 1)
        self.detonators_triggered = BitCountData(self, UInt32, 1)
        self.bunnies = NumBitfieldData(self, UInt32, Bunny)
        self.squirrels_scared = BitCountData(self, UInt16, 1, 0x19C)

        self.firecrackers_collected = NumData(self, UInt16, 0x1A2)
        self.bubbles_popped = NumData(self, UInt16)

        self.num_saves = NumData(self, UInt16, 0x1A8)

        self.keys = NumData(self, UInt8, 0x1B1)
        self.matches = NumData(self, UInt8)
        self.firecrackers = NumData(self, UInt8)
        self.health = NumData(self, UInt8)
        self.gold_hearts = NumData(self, UInt8)

        self.elapsed_ticks_ingame = Ticks(self, 0x1BC)
        self.elapsed_ticks_withpause = Ticks(self)

        self.spawn_room = MapCoord(self, 0x1D4)

        self.equipment = NumBitfieldData(self, UInt16, Equipment, 0x1DC)
        self.inventory = NumBitfieldData(self, UInt8, Inventory)

        self.candles = NumBitfieldData(self, UInt16, CandleState, 0x1E0)
        self.num_hits = NumData(self, UInt16)
        self.num_deaths = NumData(self, UInt16)
        self.ghosts_scared = BitCountData(self, UInt16, 1)

        self.selected_equipment = NumChoiceData(self, UInt8, Equipped, 0x1EA)

        self.quest_state = NumBitfieldData(self, UInt32, QuestState, 0x1EC)

        self.flames = Flames(self, 0x21E)

        self.teleports = NumBitfieldData(self, UInt8, Teleport, 0x224)
        self.stamps = Stamps(self)

        self.minimap = Minimap(self, 0x3EC)
        self.pencilmap = Minimap(self, 0xD22D)
        self.destructionmap = Minimap(self, 0x1A06E)

        self.mural = Mural(self, 0x26EAF)

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
        self.version = NumData(self, UInt32)
        if self.version.value != 9:
            raise RuntimeError(f'Unknown savefile version: {self.version}')

        self.checksum = NumData(self, UInt8, 0xD)

        self.slots = [
                Slot(self, 0, 0x00018),
                Slot(self, 1, 0x27028),
                Slot(self, 2, 0x4E038),
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

