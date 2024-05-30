Python-Based CLI Animal Well Savegame Editor
============================================

`pyanimalwell` is a save editor (and data backend) for editing
[Animal Well](https://store.steampowered.com/app/813230/ANIMAL_WELL/) savegames.
It supports editing nearly everything stored in the savegames.  In addition
to the editing features you'd expect, it's got some features you might not
expect, including:

 - Setting the Bunny Mural to its default, solved, or cleared state
 - Forcing Kangaroo spawns to a specific room
 - Respawning consumables (fruit, firecrackers) on the map
 - Clearing ghosts / Lighting Candles
 - Clearing out "illegal" pink-button presses (acquired via cheating) to
   avoid future savefile corruption
 - Image import/export to/from the "pencil" map layer

The utility seems quite safe to use -- I've not ever experienced any problems
with it.  But make sure to bakup your saves before using this!

Work on decoding the savegame structure has mostly been done by
[Kein](https://github.com/Kein/), [just-ero](https://github.com/just-ero),
lipsum, and myself.  My own contributions were mostly at the beginning of
the process; Kein, just-ero, and lipsum have been responsible for the
majority of the save format at this point.  Many thanks to them for filling
things out!

A complete mapping of the savegame data can be found at
[Kein's awsgtools repo](https://github.com/Kein/awsgtools).  At time of
writing the primary format there is an
[010 Editor](https://www.sweetscape.com/010editor/) binary template
plus an [ImHex](https://imhex.werwolv.net/) pattern.  Other translations
may become available over time.  A human-readable document describing the
save format can be found [at the wiki of that repo](https://github.com/Kein/awsgtools/wiki/Format-Description)
as well, though at time of writing it's lagging behind the binary
template by quite a bit.

Running
-------

At the moment there is a temporary script right in the main project dir which
can be launched as so:

    ./aw.py --help

Or you can call the cli module directly, if you prefer:

    python -m animalwell.cli --help

TODO
----

The editor currently does not attempt to support *everything* inside the
savegames.  Some notable bits of data which can't be edited directly:

 - Crank status
 - Elevator status
 - Stalactite/Stalagmite/Icicle destruction
 - Some seemingly-unimportant flags have been omitted from a few areas
 - Achievements *(unsure if setting these in the save would actually make
   them activate on Steam)*

While I don't have any current plans to support the above, there are a
few other things which would be nice eventually:

 - Mapping chests to their unlocks, so unlocking eggs (for instance) would
   mark the relevant chests as opened.  Vice-versa for disabling unlocks;
   it'd be nice to close the associated chest so it could be re-acquired.
   At the moment, chest opening/closing is all-or-nothing.
 - Similarly, mapping buttons/reservoirs to which doors they open would be
   nice, to be able to couple those a bit more closely.  At the moment,
   button/door states are all-or-nothing.

Usage
-----

Documentation is forthcoming...

Library
-------

The data backend should be easily usable on its own, for anyone wishing
to make programmatic changes, or write other frontends.  At the moment
the best docs are just browsing through the code.  I apologize for my
frequent PEP-8 violations, lack of typing hints, and idiosyncratic
coding habits, etc.

A quick example of the kinds of things that would be possible:

```py
from animalwell.savegame import Savegame, Equipment, Equipped

with Savegame('AnimalWell.sav') as save:
    slot = save.slots[0]
    print(f'Editing slot {slot.index+1} ({slot.timestamp})...')
    print('Current equipment unlocked:')
    for equip in sorted(slot.equipment.enabled):
        print(f' - {equip}')
    slot.num_steps.value = 15
    slot.equipment.disable(Equipment.DISC)
    slot.equipment.enable(Equipment.WHEEL)
    slot.selected_equipment.value = Equipped.WHEEL
    save.save()
```

See also `animalwell/cli.py`, which is probably the best place to look for
examples of interacting with the data.

The objects are set up to allow both defining consecutive fields within
the savefile (without specifying manual offsets), and also skipping around
using manual offsets.  When offsets are specified, they are computed relative
to the "parent" object -- so for instance, the absolute offsets used in
the `Slot` class are relative to the start of the slot.  The fields created
while looping through the file are all subclasses of the base `datafile.Data`
class, which will end up computing and storing the *absolute* offset
internally.  The save data is mirrored in an internal `io.BytesIO` object,
which is where all changes are written.  It will not actually write back out
to disk until a `save()` call has been sent.

The data objects (subclasses of `datafile.Data`) try to be easy to read, and
can be interpreted as strings or in format strings, etc.  Subclasses of
`NumData` can often be used just as if they are numbers, supporting various
numerical overloads.  Bitfield classes can generally be acted on like
arrays, at least in terms of looping through the options.  `NumBitfieldData`
keeps an `enabled` set for ease of checking which members are enabled.

*Setting* new data should often be done via the `value` property rather than
setting it directly, though -- note in the example above where the `num_steps`
property is being set that way.  `value` should also be used if you need an
actual number, such as if using it in a list index or the like.

`NumChoiceData` objects are used where the value is expected to be one of
a member of an enum.  In these objects, `value` will always be the raw numeric
value still, but there's also a `choice` attribute which will correspond to
the proper enum item, if possible.  The class technically supports setting
values outside the known enum values, in which case `choice` will end up
being `None`.  Keep in mind that setting a value for these should still be done
via `value` rather than `choice`.

Apart from that, as I say, just looking through `cli.py` or the objects
themselves would probably be the best way to know how to use 'em.

License
-------

`pyanimalwell` is licensed under the [GNU General Public License v3](https://www.gnu.org/licenses/gpl-3.0.en.html).
A copy can be found at [LICENSE.txt](LICENSE.txt).

