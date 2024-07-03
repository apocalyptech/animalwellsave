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
import struct
import collections

from . import is_debug

# "Generic" data processing for Animal Well savegames.  As usual with my
# homegrown frameworks like this, it's a bit janky, but it does the trick.
# It's set up to allow defining fields either in-line with each other
# (in which cas there's no need to pass in an explicit offset), or by
# specifying an absolute offset.  If passed in, the offset is expected to
# be *relative* to the passed-in parent offset.
#
# The most questionable bit of the design (IMO) is that it currently walks
# through an open filehandle as it goes, setting offsets based on current
# position, and parsing the data as the structure's defined by the
# implementing classes.  C'est la vie!  We are at least doing all that on
# an in-memory `io.BytesIO` object, so whatever.


class Bounds(enum.Enum):
    """
    Types of bounds that we'll check for
    """

    NONE = enum.auto()
    SIGNED = enum.auto()
    UNSIGNED = enum.auto()


# Low-level datatypes we'll be reading from the save file
NumType = collections.namedtuple('NumType', ['num_bytes', 'struct_char', 'bounds'])
UInt8 =  NumType(1, 'B', Bounds.UNSIGNED)
Int8 =   NumType(1, 'b', Bounds.SIGNED)
UInt16 = NumType(2, 'H', Bounds.UNSIGNED)
Int16 =  NumType(2, 'h', Bounds.SIGNED)
UInt32 = NumType(4, 'I', Bounds.UNSIGNED)
Int32 =  NumType(4, 'i', Bounds.SIGNED)
UInt64 = NumType(8, 'Q', Bounds.UNSIGNED)
Int64 =  NumType(8, 'q', Bounds.SIGNED)
Float =  NumType(4, 'f', Bounds.NONE)
Double = NumType(8, 'd', Bounds.NONE)


class Data():
    """
    Base data class to handle knowing where the data is.  The `parent` object
    should have a file-like `df` attribute pointing to the currently open file.
    (This is actually likely to be an in-memory `io.BytesIO` object.)  The
    `parent` object should also have an `offset` attribute, though that's only
    actually used if `offset` is passed in to here.  If no `offset` is passed
    in, the position for this data element will be the current position of
    the filehandle.

    Note that the constructor will automatically seek to the start of the
    data, after doing any offset computation, so that the data can then be
    read by the implementing classes.
    """

    def __init__(self, debug_label, parent, /, offset=None):
        """
        The `parent` object should have `df` (filehandle) and `offset`
        attributes.  `offset`, if passed in, will be computed relative to
        the parent's offset.  If not passed in, our offset will be the
        current filehandle position.
        """
        self.debug_label = debug_label
        self.parent = parent
        self.__indent = None
        self.df = self.parent.df
        if offset is None:
            self.offset = self.df.tell()
        else:
            self.offset = offset
            if self.parent is not None:
                self.offset += self.parent.offset
            self.df.seek(self.offset, os.SEEK_SET)

        # If we've been told to go into debug mode, show our offsets
        if is_debug():
            report = []
            absolute = self.offset
            report.append(f'0x{absolute:X} absolute')
            if self.parent is not None:
                relative = self.offset - self.parent.offset
                if relative != absolute:
                    report.append(f'0x{relative:X} from {self.parent.debug_label}')
            print('{}- {}:\t{}'.format(
                '  '*self._indent,
                self.debug_label,
                ",\t".join(report),
                ), file=sys.stderr)

    @property
    def _indent(self):
        """
        Used for our debug output; determines the indentation so that we can
        report on offsets in a tree-like fashion
        """
        if self.__indent is None:
            self.__indent = 0
            cur = self
            while True:
                try:
                    cur = cur.parent
                    if cur is None:
                        break
                    self.__indent += 1
                except AttributeError:
                    break
        return self.__indent


class NumData(Data):
    """
    Class to handle numeric data in the savegame (which is essentially the
    whole file, though we'll have some wrappers around more complex
    structures).  The only additional argument is `num_type`, which should be
    a `NumType` object describing the on-disk format.

    Access to the raw data is via the `value` attribute, which is
    wrapped up in a property.  For just printing/formatting the data
    you should be able to omit `.value`, but to set the value you'll
    need to go through `.value`.  Depending on `num_type`, this will
    perform bounds checking to make sure we don't exceed the byte
    count for the data type.
    """

    def __init__(self, debug_label, parent, num_type, /, offset=None):
        """
        The `parent` object should have `df` (filehandle) and `offset`
        attributes.  `offset`, if passed in, will be computed relative to
        the parent's offset.  If not passed in, our offset will be the
        current filehandle position.

        `num_type` should be a `NumType` structure.
        """
        super().__init__(debug_label, parent, offset=offset)
        self.num_type = num_type
        self.struct_string = f'<{self.num_type.struct_char}'
        match self.num_type.bounds:
            case Bounds.SIGNED:
                self.max_value = 2**((self.num_type.num_bytes*8)-1)-1
                self.min_value = -(2**((self.num_type.num_bytes*8)-1))
            case Bounds.UNSIGNED:
                self.max_value = 2**(self.num_type.num_bytes*8)-1
                self.min_value = 0
            case _:
                self.max_value = None
                self.min_value = None
        self._value = None

        # Read in the values as we go.  This is probably inefficient for most
        # use-cases 'cause there's unlikely to be a reason to read *everything*.
        # It's handy for NumChoiceData and NumBitfieldData, though, so they can
        # populate their extra fields immediately.  (We could, of course, only
        # have *those* classes pre-load like this, or wrap their extra fields
        # around properties to do the dynamic loading, but for now: whatever.)
        self._value = struct.unpack(self.struct_string, self.df.read(self.num_type.num_bytes))[0]
        self._post_value_set()

    @property
    def value(self):
        """
        Returns our raw value.
        """
        # In the future, we may want to dynamically load here, instead of
        # doing so in the constructor.
        return self._value

    @value.setter
    def value(self, new_value):
        """
        Sets our new value, potentially doing bounds checking at the same time.
        Will raise a `ValueError` if the bounds have been exceeded.
        """
        if self.min_value is not None and new_value < self.min_value:
            raise ValueError(f'Minimum value is {self.min_value}')
        if self.max_value is not None and new_value > self.max_value:
            raise ValueError(f'Maximum value is {self.max_value}')
        self.df.seek(self.offset, os.SEEK_SET)
        self.df.write(struct.pack(self.struct_string, new_value))
        self._value = new_value
        self._post_value_set()

    def _post_value_set(self):
        """
        Any actions which need to be performed after setting our value.  Empty for
        this class but can be implemented in subclasses.  Called after the `value`
        setter.
        """
        pass

    @property
    def label(self):
        """
        Returns an appropriate "label" for the data, which for this base class is
        just the raw data itself.  Can be overridden in subclasses for prettier
        display.
        """
        return self.value

    def __str__(self):
        """
        String representation of the value.
        """
        return str(self.label)

    def __format__(self, format_str):
        """
        Support for using this class inside format strings.
        """
        format_str = '{:' + format_str + '}'
        return format_str.format(self.label)

    def __eq__(self, other):
        """
        Compare using our `value` attribute.  This should allow us to test for
        equality versus other `NumData` objects, or by raw numeric values.
        """
        if issubclass(type(other), NumData):
            return self.value == other.value
        else:
            return self.value == other

    def __lt__(self, other):
        """
        Compare using our `value` attribute.  This should allow us to test
        versus other `NumData` objects, or by raw numeric values.
        """
        if issubclass(type(other), NumData):
            return self.value < other.value
        else:
            return self.value < other

    def __gt__(self, other):
        """
        Compare using our `value` attribute.  This should allow us to test
        versus other `NumData` objects, or by raw numeric values.
        """
        if issubclass(type(other), NumData):
            return self.value > other.value
        else:
            return self.value > other

    def __le__(self, other):
        """
        Compare using our `value` attribute.  This should allow us to test
        versus other `NumData` objects, or by raw numeric values.
        """
        if issubclass(type(other), NumData):
            return self.value <= other.value
        else:
            return self.value <= other

    def __ge__(self, other):
        """
        Compare using our `value` attribute.  This should allow us to test
        versus other `NumData` objects, or by raw numeric values.
        """
        if issubclass(type(other), NumData):
            return self.value >= other.value
        else:
            return self.value >= other

    def __add__(self, other):
        """
        Support addition
        """
        return self.value + other

    def __sub__(self, other):
        """
        Support subtraction
        """
        return self.value - other

    def __mod__(self, other):
        """
        Support modulo
        """
        return self.value % other


class LabelEnum(enum.Enum):
    """
    A custom Enum class which, in addition to the usual `value`, also has
    a `label` field intended to be shown to the user in implementing UIs.
    """

    def __new__(cls, value, label):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.label = label
        return obj

    def __lt__(self, other):
        """
        Sort by our label
        """
        if type(other) == str:
            return self.label.casefold() < other.casefold()
        else:
            return self.label.casefold() < other.label.casefold()

    def __gt__(self, other):
        """
        Sort by our label
        """
        if type(other) == str:
            return self.label.casefold() > other.casefold()
        else:
            return self.label.casefold() > other.label.casefold()

    def __le__(self, other):
        """
        Sort by our label
        """
        if type(other) == str:
            return self.label.casefold() <= other.casefold()
        else:
            return self.label.casefold() <= other.label.casefold()

    def __ge__(self, other):
        """
        Sort by our label
        """
        if type(other) == str:
            return self.label.casefold() >= other.casefold()
        else:
            return self.label.casefold() >= other.label.casefold()

    def __str__(self):
        """
        String representation will be the label, not the value
        """
        return self.label

    def cli_arg_choices(self):
        return sorted([e.name.lower() for e in self])


class NumChoiceData(NumData):
    """
    Numeric data which is (at least theoretically) constrained to a set of
    known data.  For example, the data in the savegame which defines the
    currently-selected equipment should be one of a few known values.

    The choices should be defined via a `LabelEnum` object whose values are
    the numeric save data.

    This class does *not* actually force the value to be a member of the
    specified choices -- the user is permitted to write arbitrary numeric
    values into the field.  (Perhaps it would make sense to have a flag
    whether to allow that kind of thing or not, instead of just allowing?)
    """

    def __init__(self, debug_label, parent, num_type, choices, /, offset=None):
        """
        The `parent` object should have `df` (filehandle) and `offset`
        attributes.  `offset`, if passed in, will be computed relative to
        the parent's offset.  If not passed in, our offset will be the
        current filehandle position.

        `num_type` should be a `NumType` structure.

        `choices` should be a `LabelEnum` class, defining the known values
        for this data.
        """

        self.choices = choices
        self.choice = None
        super().__init__(debug_label, parent, num_type, offset=offset)

    @NumData.value.setter
    def value(self, new_value):
        """
        Sets our raw data.  `new_value` can either be the raw numeric value, or
        an instance of `self.choices`.
        """
        if isinstance(new_value, self.choices):
            new_value = new_value.value
        # Okay this syntax is a bit wild.  Really `super().value = new_value`
        # should do the trick, but it doesn't: https://github.com/python/cpython/issues/59170
        # Other reading:
        #    https://medium.com/@nurettinabaci/python-property-and-inheritance-fa9143201c17
        #    https://gist.github.com/Susensio/979259559e2bebcd0273f1a95d7c1e79
        #    https://github.com/python/cpython/blob/0abf997e75bd3a8b76d920d33cc64d5e6c2d380f/Lib/ssl.py#L546
        super(NumChoiceData, NumChoiceData).value.fset(self, new_value)

    def _post_value_set(self):
        """
        Called after our value is set, and will populate our `self.choice`
        variable if the numeric data is contained within `self.choices`.
        """
        if self.choices is not None:
            # In Python 3.12 we could check `self.value in self.choices`, as I was doing
            # originally, but it turns out that's something added in 3.12, and I'd like
            # to be compatible back to 3.10.  See: https://github.com/python/cpython/issues/88123
            # (not that this method is bad, of course -- more Pythonic, even, probably!)
            try:
                self.choice = self.choices(self.value)
            except ValueError:
                self.choice = None

    @property
    def label(self):
        """
        A label for the data -- if the numeric data is contained within
        `self.choices`, this will use the `label` attribute of the LabelEnum.
        Otherwise it will just return the numeric data as usual.
        """
        if self.choice is None:
            return self.value
        else:
            return self.choice.label

    def __eq__(self, other):
        """
        Compare using our `value` attribute.  This should allow us to test for
        equality versus other `NumData` objects, by `LabelEnum` value, or by
        raw numeric values.
        """
        if issubclass(type(other), NumData):
            return self.value == other.value
        elif issubclass(type(other), LabelEnum):
            return self.value == other.value
        else:
            return self.value == other


class NumBitfieldData(NumData):
    """
    Numeric data which operates as a bitfield.  The bitfield should be
    defined via a `LabelEnum` object whose values are the bitmask for
    the option.

    Arbitrary numeric values can be written to this field as per usual,
    but the `enable`/`disable` methods to toggle individual bits will
    only accept valid options from the configured enum.

    In addition to an `enabled` set which can be used to enumerate
    enabled items, the class keeps track of a `disabled` set to do
    the opposite.
    """

    def __init__(self, debug_label, parent, num_type, bitfield, /, offset=None):
        """
        The `parent` object should have `df` (filehandle) and `offset`
        attributes.  `offset`, if passed in, will be computed relative to
        the parent's offset.  If not passed in, our offset will be the
        current filehandle position.

        `num_type` should be a `NumType` structure.

        `bitfield` should be a `LabelEnum` class, defining the known values
        for this data.
        """
        self.bitfield = bitfield
        self.enabled = set()
        self.disabled = set()
        super().__init__(debug_label, parent, num_type, offset=offset)

    def _post_value_set(self):
        """
        Called after our value is set, and will populate our `self.enabled`
        set which contains `self.bitfield` members describing what options
        are currently enabled.
        """
        self.enabled = set()
        self.disabled = set()
        if self.bitfield is not None:
            for choice in self.bitfield:
                if self._value & choice.value == choice.value:
                    self.enabled.add(choice)
                else:
                    self.disabled.add(choice)

    def __len__(self):
        """
        Returns how many of our known bitfields are selected.
        """
        return len(self.enabled)

    def count(self):
        """
        Returns how many total items there are in the bitfield
        """
        return len(self.bitfield)

    def enable(self, choice):
        """
        Enables the specified bit within the bitfield.  `choice` can either be
        an instance of the `LabelEnum` applied to the field, or the numeric
        bit mask.  Will raise a `ValueError` if a bitmask is passed in which
        is not a part of the LabelEnum.
        """
        # TODO: this is pretty stupidly inefficient, especially if you're
        # setting a bunch of bitfields in a row.
        if not isinstance(choice, self.bitfield):
            choice = self.bitfield(choice)
        if choice not in self.enabled:
            self.value = self.value | choice.value

    def enable_all(self):
        """
        Enables all known bits in the bitfield.  This doesn't blindly turn
        *all* bits on in case our bitfield mapping is incomplete -- we don't
        want to alter data we don't know about.
        """
        new_value = self.value
        for item in self.bitfield:
            new_value |= item.value
        self.value = new_value

    def disable(self, choice):
        """
        Disables the specified bit within the bitfield.  `choice` can either be
        an instance of the `LabelEnum` applied to the field, or the numeric
        bit mask.  Will raise a `ValueError` if a bitmask is passed in which
        is not a part of the LabelEnum.
        """
        # TODO: this is pretty stupidly inefficient, especially if you're
        # setting a bunch of bitfields in a row.
        if not isinstance(choice, self.bitfield):
            choice = self.bitfield(choice)
        if choice in self.enabled:
            self.value = self.value & ~choice.value

    def disable_all(self):
        """
        Disables all known bits in the bitfield.  This doesn't blindly turn
        *all* bits off in case our bitfield mapping is incomplete -- we don't
        want to alter data we don't know about.
        """
        new_value = self.value
        for item in self.bitfield:
            new_value &= ~item.value
        self.value = new_value


class BitCountData(Data):
    """
    A collection of bitfield data where all we *really* care about is the
    number of bits that are set, and possibly the ability to clear/set them
    en masse.  The primary examples here are picked fruits and firecrackers.

    The individual bits of data in here aren't really meant to be altered
    directly, and the `count` counter won't be automatically updated here
    if any of the child data is altered directly.

    There's sort of no real reason why this functionality couldn't just be
    rolled into NumBitfieldData, especially given that we might eventually
    want to be able to modify bitfields for some of this...  Note too that
    most of these fields include at least one "unknown" bit within our
    `max_bits` count, so the `fill()` method will technically be filling
    in more data than would be likely to have been filled on a vanilla
    save.
    """

    def __init__(self, debug_label, parent, num_type, count, max_bits, offset=None):
        """
        The `parent` object should have `df` (filehandle) and `offset`
        attributes.  `offset`, if passed in, will be computed relative to
        the parent's offset.  If not passed in, our offset will be the
        current filehandle position.

        `num_type` should be a `NumType` structure, and `count` should be
        the number of those structures which make up the bitfield.  `max_bits`
        is the maximum number of known bits which we should set when filling
        up the bitfield.
        """

        super().__init__(debug_label, parent, offset=offset)
        self.num_type = num_type
        if self.num_type.bounds != Bounds.UNSIGNED:
            raise RuntimeError('BitCountData objects can only be populated with unsigned numeric data')
        self._data_count = count
        self.count = 0
        self.max_bits = max_bits

        # Read in data
        self._data = []
        for idx in range(self._data_count):
            self._data.append(NumData(f'Segment {idx}', self, self.num_type))
        self._fix_count()

    def __str__(self):
        """
        When being represented as a string, we'll default to our bit count.
        """
        return str(self.count)

    def __len__(self):
        """
        The number of bits set in our structure
        """
        return self.count

    def __gt__(self, other):
        """
        Compare against other BitCountData objects (probably not much use there)
        or other values, based on our count.
        """
        if issubclass(type(other), BitCountData):
            return self.count > other.count
        else:
            return self.count > other

    def _fix_count(self):
        """
        Resets our internal `count` structure for how many bits are set across
        the entire data length.
        """
        self.count = 0
        for data in self._data:
            self.count += data.value.bit_count()

    def _set_all(self, value):
        """
        Sets all child elements of the structure to the specified `value`.
        Note that this does *not* update our `count` structure; calling
        classes are expected to do that themselves.
        """
        for data in self._data:
            data.value = value

    def fill(self):
        """
        Fill the entire bit structure with 1s (ie: make it maximally-enabled).
        This will honor the `max_bits` parameter, so we don't fill in bits
        that aren't known.

        Note, however, that most of these bitfields include at least one
        "unknown" bit in the middle, so this method will often fill in
        more data than would be seen on a purely vanilla save.
        """
        bits_to_fill = self.max_bits
        individual_bits = self.num_type.num_bytes*8
        for data in self._data:
            this_bits = min(bits_to_fill, individual_bits)
            data.value |= (2**this_bits)-1
            bits_to_fill -= this_bits
        self.count = self.max_bits

    def clear(self):
        """
        Fill the entire bit structure with 0s (ie: make it minimally-enabled).
        Note that this will completely clear all bits in the structure, even
        "unknown" bits after our `max_bits` parameter.
        """
        self._set_all(0)
        self.count = 0

    def set_bit(self, bit):
        """
        Sets the specified bit within the bitfield.  This is starting to verge
        on territory which once again might make more sense to just merge into
        NumBitfieldData instead, but apparently I'm sticking to my guns and
        making it weird.
        """
        if bit >= self.max_bits:
            raise ValueError(f'Cannot alter bit {bit}; only {self.max_bits} are used')
        bits_per_segment = self.num_type.num_bytes*8
        segment = int(bit/bits_per_segment)
        bit -= bits_per_segment*segment
        mask = 1<<bit
        self._data[segment].value |= mask
        self._fix_count()

    def clear_bit(self, bit):
        """
        Clears the specified bit within the bitfield.  This is starting to verge
        on territory which once again might make more sense to just merge into
        NumBitfieldData instead, but apparently I'm sticking to my guns and
        making it weird.
        """
        if bit >= self.max_bits:
            raise ValueError(f'Cannot alter bit {bit}; only {self.max_bits} are used')
        bits_per_segment = self.num_type.num_bytes*8
        segment = int(bit/bits_per_segment)
        bit -= bits_per_segment*segment
        mask = 1<<bit
        self._data[segment].value &= ~mask
        self._fix_count()

