`joyfl` (pronounced `ˈjȯi-fəl`) is a dialect of the programming language Joy.

Joy is a stack-based programming environment that's both functional and concatenative, which results in highly expressive but short programs.  `joyfl` is an implementation of Joy in Python in its early stages; it's not entirely backwards compatible by design.


DIFFERENCES
===========

1. **Symbols vs. Characters** — Individual byte characters are not supported, so it's not possible to extract or combine them with strings.  Instead, the single quote denotes symbols (e.g. ``'alpha``) that can only be compared and added to containers.

2. **Data-Structures** — Sets are not implemented yet, but will be. When they are, the sets will have the functionality of the underlying Python sets. Lists too behave like Python lists.  Dictionaries will likely follow too at some point.

3. **Conditionals** — Functions that return booleans are encouraged to use the ``?`` suffix, for example ``equal?`` or ``list?``.  This change is inspired by Factor, and makes the code more readable so you know when to expect a boolean.

4. **Stackless** - The interpreter does not use the Python callstack: state is stored entirely in data-structures. There's a stack (for data created in the past) and a queue (for code to be executed in the future).  Certain advanced combinators may feel a bit different to write because of this!


REFERENCES
==========

* The `official documentation <https://hypercubed.github.io/joy/joy.html>`__ for Joy by Manfred van Thun.

* The `various C implementations <https://github.com/Wodan58>`__ (joy0, joy1) by Ruurd Wiersma.

* Python implementations, specifically `Joypy <https://github.com/ghosthamlet/Joypy>`__ by @ghosthamlet.

* An entire `book chapter <https://github.com/nickelsworth/sympas/blob/master/text/18-minijoy.org>`_ implementing Joy in Pascal.
