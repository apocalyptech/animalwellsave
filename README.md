Python-Based CLI Animal Well Savegame Editor
============================================

`pyanimalwell` is a very WIP save editor (and data backend) for editing
[Animal Well](https://store.steampowered.com/app/813230/ANIMAL_WELL/) savegames.
At the moment it's extremely incomplete.  Make backups of your saves before
using this!

Work on decoding the savegame structure has mostly been done by myself,
[Kein](https://github.com/Kein/), and [just-ero](https://github.com/just-ero),
with Kein and just-ero picking up the majority of that workload after the
initial basic discoveries.  Many thanks to them for filling things out!

A far-more-complete mapping of the savegame data can be found at
[Kein's awsgtools repo](https://github.com/Kein/awsgtools).  At time of
writing the primary format there is an
[010 Editor](https://www.sweetscape.com/010editor/) binary template,
but other translations should become available over time.  A
human-readable document describing the save format can be found [at the wiki
of that repo](https://github.com/Kein/awsgtools/wiki/Format-Description)
as well, though at time of writing it's lagging behind the binary
template by quite a bit.

Usage
-----

I'm not planning on documenting this much yet, since much might end up
changing.  There is a temporary script right in the main project dir
which can be launched as so:

    ./aw.py --help

Or you can call the cli module directly, if you prefer:

    python -m animalwell.cli --help

Library
-------

The data backend should be easily usable on its own, for anyone wishing
to make programmatic changes, or write other frontends.  At the moment
the best docs are just browsing through the code.  I apologize for my
frequent PEP-8 violations, lack of typing hints, and idiosyncratic
coding habits, etc.

A quick example of what should be possible (though keep in mind that
this may have changed inbetween writing and release):

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

License
-------

`pyanimalwell` is licensed under the [GNU General Public License v3](https://www.gnu.org/licenses/gpl-3.0.en.html).
A copy can be found at [LICENSE.txt](LICENSE.txt).

