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
import enum
import struct
import collections

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

    def __init__(self, parent, /, offset=None):
        """
        The `parent` object should have `df` (filehandle) and `offset`
        attributes.  `offset`, if passed in, will be computed relative to
        the parent's offset.  If not passed in, our offset will be the
        current filehandle position.
        """
        self.parent = parent
        self.df = self.parent.df
        if offset is None:
            self.offset = self.df.tell()
        else:
            self.offset = offset
            if self.parent is not None:
                self.offset += self.parent.offset
            self.df.seek(self.offset, os.SEEK_SET)


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

    def __init__(self, parent, num_type, /, offset=None):
        """
        The `parent` object should have `df` (filehandle) and `offset`
        attributes.  `offset`, if passed in, will be computed relative to
        the parent's offset.  If not passed in, our offset will be the
        current filehandle position.

        `num_type` should be a `NumType` structure.
        """
        super().__init__(parent, offset=offset)
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
        return self.label.casefold() < other.label.casefold()

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

    def __init__(self, parent, num_type, choices, /, offset=None):
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
        super().__init__(parent, num_type, offset=offset)

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
            if self.value in self.choices:
                self.choice = self.choices(self.value)
            else:
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


class NumBitfieldData(NumData):
    """
    Numeric data which operates as a bitfield.  The bitfield should be
    defined via a `LabelEnum` object whose values are the bitmask for
    the option.

    Arbitrary numeric values can be written to this field as per usual,
    but the `enable`/`disable` methods to toggle individual bits will
    only accept valid options from the configured enum.
    """

    def __init__(self, parent, num_type, bitfield, /, offset=None):
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
        super().__init__(parent, num_type, offset=offset)

    def _post_value_set(self):
        """
        Called after our value is set, and will populate our `self.enabled`
        set which contains `self.bitfield` members describing what options
        are currently enabled.
        """
        self.enabled = set()
        if self.bitfield is not None:
            for choice in self.bitfield:
                if self._value & choice.value == choice.value:
                    self.enabled.add(choice)

    def enable(self, choice):
        """
        Enables the specified bit within the bitfield.  `choice` can either be
        an instance of the `LabelEnum` applied to the field, or the numeric
        bit mask.  Will raise a `ValueError` if a bitmask is passed in which
        is not a part of the LabelEnum.
        """
        # TODO: this is pretty stupidly inefficient, especially if you're
        # setting a bunch of bitfields in a row.
        if self.bitfield is None:
            raise RuntimeError('field is not a bitfield')
        if not isinstance(choice, self.bitfield):
            choice = self.bitfield(choice)
        if choice not in self.enabled:
            self.value = self.value | choice.value

    def disable(self, choice):
        """
        Disables the specified bit within the bitfield.  `choice` can either be
        an instance of the `LabelEnum` applied to the field, or the numeric
        bit mask.  Will raise a `ValueError` if a bitmask is passed in which
        is not a part of the LabelEnum.
        """
        # TODO: this is pretty stupidly inefficient, especially if you're
        # setting a bunch of bitfields in a row.
        if self.bitfield is None:
            raise RuntimeError('field is not a bitfield')
        if not isinstance(choice, self.bitfield):
            choice = self.bitfield(choice)
        if choice in self.enabled:
            self.value = self.value & ~choice.value

