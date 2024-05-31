I should probably bundle this up into a Makefile or something, but for now
it's pretty manual.  Basically just have a venv which has been prepared
like so:

    python -m venv .venv
    . .venv/bin/activate
    pip install -r dev-requirements.txt

Then, to build a new release:

1. Update `animalwellsave/__init__.py` with the new version
2. Update the Changelog in `README.md`
3. Check in, push
4. `python -m build --sdist --wheel`
5. Manually verify that the new packages look good
6. `twine upload dist/*x.x.x*`
7. `git tag v<version>`
8. `git push --tags`
9. Create github release

That should do!  Be sure to check the pypi page to ensure
it looks good there, too.
