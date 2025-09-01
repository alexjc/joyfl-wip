``joyfl`` (pronounced *ˈjȯi-fəl*) is a dialect of the programming language Joy.

Joy is a stack-based programming environment that's both functional and concatenative, which results in highly expressive but short programs.  ``joyfl`` is an implementation of Joy in Python in its early stages; it's not entirely backwards compatible by design. 


EXAMPLES
========

You can run a simple REPL (read-eval-print loop) by typing: ``python3 joyfl.py repl``.  From there, try typing these statements:

.. code-block:: factor

    1 2 + 3 +
        6 equals? .
    > true

    [7 8 9] [1 -] map reverse .
    > [8 7 6]

    ['a 'b 'c] 'd swap rest cons .
    > ['d 'b 'c]

Also look at the ``#/examples/`` folder and run them with ``python3 joyfl.py <filename>``.


MOTIVATION
==========

While it's fun to implement languages, this project has particular #ML / #LLM research questions in mind...

    **“ What if there was a language for a 'micro-controller' able to process 99% of tokens? ”**

📥 TRAINING: To produce training data, what's the middle ground between a web-template (gasp!) and a synthetic theorem generator (whew!)?  The answer looks more like another language than a hacked-together Python script.

📤 INFERENCE: For output tokens, how can we make sure prompts are followed, any arithmetic is correct, no items are missed, and formatting is right?  The solution isn't more Python but special tokens that can be interpreted as instructions...

The research goal of this project is to find out where and how Joy can shine in these cases!


DIFFERENCES
===========

While some of the tests from the original Joy pass, many also do not.  Here are the design decisions at play:

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
