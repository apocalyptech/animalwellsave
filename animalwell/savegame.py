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

    S_MEDAL =    (0x02, 'S. Medal')
    HOUSE_KEY =  (0x08, 'House Key')
    OFFICE_KEY = (0x10, 'Office Key')
    UNUSED_KEY = (0x20, 'Unused Key')
    E_MEDAL =    (0x40, 'E. Medal')
    PACK =       (0x80, 'F. Pack')


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


class Slot():
    """
    A savegame slot.  Obviously this is where the bulk of the game data is
    stored.
    """

    def __init__(self, savegame, index, offset):
        self.savegame = savegame
        self.index = index
        self.df = self.savegame.df
        self.offset = offset
        self.has_data = False
        self.df.seek(offset)

        self.timestamp = Timestamp(self)
        # If the timestamp is all zeroes, assume that the slot is empty
        # (though we'll continue to load the rest of the data anyway)
        self.has_data = self.timestamp.has_data

        self.num_steps = NumData(self, UInt32, 0x108)

        self.picked_fruit = BitCountData(self, UInt64, 2, 0x170)
        self.picked_firecrackers = BitCountData(self, UInt64, 1, 0x180)

        self.num_saves = NumData(self, UInt16, 0x1A8)

        self.firecrackers = NumData(self, UInt8, 0x1B3)
        self.health = NumData(self, UInt8)

        self.elapsed_ticks_ingame = Ticks(self, 0x1BC)
        self.elapsed_ticks_withpause = Ticks(self)

        self.num_deaths = NumData(self, UInt16, 0x1E4)
        self.ghosts_scared = BitCountData(self, UInt16, 1)

        self.selected_equipment = NumChoiceData(self, UInt8, Equipped, 0x1EA)

        self.spawn_room = MapCoord(self, 0x1D4)

        self.equipment = NumBitfieldData(self, UInt16, Equipment, 0x1DC)
        self.inventory = NumBitfieldData(self, UInt8, Inventory)


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

